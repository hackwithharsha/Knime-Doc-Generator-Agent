"""
Tests for upload validation and the doc job endpoints. These hit the real
Postgres/Redis (see conftest.py) and enqueue the real Celery task via
.delay(), but never wait for a worker to process it — full pipeline
execution is exercised separately by a live end-to-end run (see CLAUDE.md
progress log), not by this test suite.
"""

import io
import uuid
import zipfile

from app.db.session import AsyncSessionLocal
from app.models.doc import DocEvent, DocJob, JobStatus


def _fake_knwf_bytes() -> bytes:
    """A minimal valid zip with a workflow.knime entry — enough to pass upload
    validation. Parsing correctness itself is covered by tests/test_parser.py."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("Demo/workflow.knime", "<config/>")
    return buf.getvalue()


async def test_upload_rejects_wrong_extension(client):
    resp = await client.post(
        "/api/doc/jobs",
        files={"file": ("workflow.txt", b"not a knwf", "text/plain")},
    )
    assert resp.status_code == 400


async def test_upload_rejects_oversized_file(client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "max_upload_mb", 0)
    resp = await client.post(
        "/api/doc/jobs",
        files={"file": ("workflow.knwf", b"x" * 1024, "application/octet-stream")},
    )
    assert resp.status_code == 413


async def test_upload_rejects_empty_file(client):
    resp = await client.post(
        "/api/doc/jobs",
        files={"file": ("workflow.knwf", b"", "application/octet-stream")},
    )
    assert resp.status_code == 400


async def test_create_and_get_job(client):
    resp = await client.post(
        "/api/doc/jobs",
        files={"file": ("Demo.knwf", _fake_knwf_bytes(), "application/octet-stream")},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "queued"
    assert body["filename"] == "Demo.knwf"
    job_id = body["id"]

    detail = await client.get(f"/api/doc/jobs/{job_id}")
    assert detail.status_code == 200
    detail_body = detail.json()
    assert detail_body["id"] == job_id
    assert detail_body["markdown"] is None  # not completed yet


async def test_get_job_not_found(client):
    resp = await client.get(f"/api/doc/jobs/{uuid.uuid4()}")
    assert resp.status_code == 404


async def test_list_jobs_returns_recent_first(client):
    for name in ("A.knwf", "B.knwf"):
        await client.post(
            "/api/doc/jobs",
            files={"file": (name, _fake_knwf_bytes(), "application/octet-stream")},
        )
    resp = await client.get("/api/doc/jobs")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) >= 2
    assert body[0]["created_at"] >= body[1]["created_at"]


async def test_events_stream_replays_terminal_job_without_hanging(client):
    """A job that already reached a terminal status should replay its stored
    events and close immediately, without waiting on Redis."""
    async with AsyncSessionLocal() as session:
        job = DocJob(filename="Demo.knwf", status=JobStatus.COMPLETED)
        session.add(job)
        await session.flush()
        session.add(DocEvent(job_id=job.id, type="agent_started", agent="Analyst", message="started"))
        session.add(DocEvent(job_id=job.id, type="crew_completed", agent=None, message="done"))
        await session.commit()
        job_id = job.id

    async with client.stream("GET", f"/api/doc/jobs/{job_id}/events") as resp:
        assert resp.status_code == 200
        body = "".join([chunk async for chunk in resp.aiter_text()])

    assert "agent_started" in body
    assert "crew_completed" in body


async def test_upload_still_returns_a_failed_job_if_enqueue_fails(client, monkeypatch):
    """If the Celery broker (Redis) is unreachable at enqueue time, the job
    must not sit at 'queued' forever with no worker ever able to pick it up —
    it should come back already marked failed, with a clear reason."""
    from app.api.routes import doc as doc_routes

    def _boom(*args, **kwargs):
        raise ConnectionError("redis down")

    monkeypatch.setattr(doc_routes.generate_doc, "delay", _boom)

    resp = await client.post(
        "/api/doc/jobs",
        files={"file": ("Demo.knwf", _fake_knwf_bytes(), "application/octet-stream")},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "failed"
    assert "unavailable" in body["error"].lower()


async def test_events_stream_emits_error_on_redis_failure(client, monkeypatch):
    """A Redis outage (initial subscribe failing, or the connection dropping
    mid-stream) must surface as a real 'error' SSE event, not an unhandled
    exception that just cuts the connection and leaves the UI hanging."""
    from app.api.routes import doc as doc_routes

    class _BoomPubSub:
        async def subscribe(self, channel):
            raise ConnectionError("redis down")

        async def unsubscribe(self, channel):
            pass

        async def aclose(self):
            pass

    class _BoomRedisClient:
        def pubsub(self):
            return _BoomPubSub()

        async def aclose(self):
            pass

    monkeypatch.setattr(doc_routes.aioredis, "from_url", lambda *a, **kw: _BoomRedisClient())

    async with AsyncSessionLocal() as session:
        job = DocJob(filename="Demo.knwf", status=JobStatus.RUNNING)
        session.add(job)
        await session.commit()
        job_id = job.id

    async with client.stream("GET", f"/api/doc/jobs/{job_id}/events") as resp:
        assert resp.status_code == 200
        body = "".join([chunk async for chunk in resp.aiter_text()])

    assert '"type": "error"' in body
    assert "connection" in body.lower()
