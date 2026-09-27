import asyncio
import json
import logging
import uuid
from collections.abc import AsyncGenerator
from typing import Literal
from urllib.parse import quote

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.exporters import build_docx, build_pdf, safe_filename
from app.models.doc import DocDocument, DocEvent, DocJob, JobStatus
from app.schemas.doc import JobDetailOut, JobOut
from app.services.pubsub import TERMINAL_EVENT_TYPES, job_channel, serialize_event
from app.services.storage import save_upload
from app.tasks.doc import generate_doc

_EXPORT_CONTENT_TYPES = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pdf": "application/pdf",
}

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/doc", tags=["doc"])

KEEPALIVE_SECONDS = 15
ENQUEUE_TIMEOUT_SECONDS = 5


def _to_job_out(job: DocJob) -> JobOut:
    return JobOut(
        id=job.id,
        workflow_name=job.workflow_name,
        filename=job.filename,
        status=job.status,
        error=job.error,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


@router.post("/jobs", response_model=JobOut, status_code=status.HTTP_201_CREATED)
async def create_job(file: UploadFile, db: AsyncSession = Depends(get_db)) -> JobOut:
    job = DocJob(filename=file.filename or "upload.knwf", status=JobStatus.QUEUED)
    db.add(job)
    await db.flush()  # populate job.id before the file is saved under it

    await save_upload(file, job.id)
    await db.commit()
    await db.refresh(job)

    try:
        # generate_doc.delay() is a blocking call — run it in a thread so an
        # unreachable broker can't freeze this single-process async server for
        # every other request while it retries. wait_for adds a hard wall-clock
        # bound on top: found live that a stopped Redis container makes the
        # underlying kombu connection fail via DNS resolution retries that took
        # ~20s on their own — a plain try/except around the call never even got
        # a chance to run for that long, and explicit socket_connect_timeout
        # settings don't help since the delay was in DNS lookups, not the TCP
        # connect. Abandoning the thread on timeout leaves it to finish (or
        # fail) on its own in the background; it holds no shared state.
        await asyncio.wait_for(asyncio.to_thread(generate_doc.delay, str(job.id)), timeout=ENQUEUE_TIMEOUT_SECONDS)
    except Exception:
        # The broker (Redis) being unreachable at enqueue time would otherwise
        # leave the job stuck at "queued" forever with no worker ever able to
        # pick it up. Fail it immediately with a clear, actionable message
        # instead of a silent hang.
        logger.exception("Could not enqueue generate_doc for job %s", job.id)
        job.status = JobStatus.FAILED
        job.error = "Could not queue the job — the background worker is unavailable. Try again shortly."
        await db.commit()
        await db.refresh(job)

    return _to_job_out(job)


@router.get("/jobs", response_model=list[JobOut])
async def list_jobs(db: AsyncSession = Depends(get_db)) -> list[JobOut]:
    result = await db.execute(select(DocJob).order_by(DocJob.created_at.desc()).limit(50))
    return [_to_job_out(job) for job in result.scalars().all()]


@router.get("/jobs/{job_id}", response_model=JobDetailOut)
async def get_job(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> JobDetailOut:
    job = await db.get(DocJob, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")

    markdown = None
    if job.status == JobStatus.COMPLETED:
        result = await db.execute(select(DocDocument).where(DocDocument.job_id == job_id))
        doc = result.scalar_one_or_none()
        markdown = doc.markdown if doc else None

    return JobDetailOut(**_to_job_out(job).model_dump(), markdown=markdown)


@router.get("/jobs/{job_id}/export")
async def export_job(
    job_id: uuid.UUID, format: Literal["docx", "pdf"], db: AsyncSession = Depends(get_db)
) -> Response:
    job = await db.get(DocJob, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Documentation is not ready yet.")

    result = await db.execute(select(DocDocument).where(DocDocument.job_id == job_id))
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documentation not found.")

    workflow_name = job.workflow_name or job.filename
    if format == "docx":
        content = build_docx(workflow_name, doc.created_at, doc.markdown)
    else:
        content = build_pdf(workflow_name, doc.created_at, doc.markdown)

    filename = f"{safe_filename(workflow_name)}.{format}"
    return Response(
        content=content,
        media_type=_EXPORT_CONTENT_TYPES[format],
        headers={
            "Content-Disposition": f"attachment; filename=\"{filename}\"; filename*=UTF-8''{quote(filename)}"
        },
    )


@router.get("/jobs/{job_id}/events")
async def stream_events(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> StreamingResponse:
    job = await db.get(DocJob, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")

    result = await db.execute(select(DocEvent).where(DocEvent.job_id == job_id).order_by(DocEvent.created_at))
    replay_events = list(result.scalars().all())
    already_terminal = job.status in (JobStatus.COMPLETED, JobStatus.FAILED)

    async def event_stream() -> AsyncGenerator[str, None]:
        for row in replay_events:
            yield _sse(serialize_event(row.type, row.agent, row.message, row.created_at))

        if already_terminal:
            return  # replay already contains the terminal event; nothing more will ever publish

        # Explicit socket timeouts: without them, subscribing to (or reading
        # from) an unreachable Redis can hang at the TCP layer well past this
        # generator's own except-block below ever getting a chance to run —
        # found live by stopping the redis container. A bounded connect/read
        # timeout is what actually makes this fail fast instead of hanging.
        redis_client = aioredis.from_url(settings.redis_url, socket_connect_timeout=5, socket_timeout=5)
        pubsub = redis_client.pubsub()
        channel = job_channel(str(job_id))
        try:
            await pubsub.subscribe(channel)
            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=KEEPALIVE_SECONDS)
                if message is None:
                    yield ": keepalive\n\n"
                    continue
                data = message["data"]
                if isinstance(data, bytes):
                    data = data.decode()
                yield _sse(data)
                if json.loads(data)["type"] in TERMINAL_EVENT_TYPES:
                    break
        except Exception:
            # Redis dropping mid-stream (or being unreachable for the initial
            # subscribe) would otherwise propagate out of this generator and
            # just cut the connection — EventSource's onerror fires with no
            # information, so the UI is left showing stale progress forever.
            # Emitting a real "error" event first means the frontend's normal
            # terminal-event handling picks it up instead of silently hanging.
            logger.exception("SSE stream lost its Redis connection for job %s", job_id)
            yield _sse(
                serialize_event(
                    "error",
                    None,
                    "Lost connection to the live progress stream. Refresh the page to check the current status.",
                )
            )
        finally:
            try:
                await pubsub.unsubscribe(channel)
                await pubsub.aclose()
                await redis_client.aclose()
            except Exception:
                pass  # best-effort cleanup; the connection may already be gone

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _sse(data: str) -> str:
    return f"data: {data}\n\n"
