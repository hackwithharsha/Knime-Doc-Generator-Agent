"""
Core documentation-generation pipeline: load the uploaded file, parse it, run
the crew, and persist status/events/document. Runs entirely synchronously —
see CLAUDE.md "Sync vs. async DB access": crew.kickoff() is a blocking call
that fires progress events synchronously mid-call, with no event loop
available to await into from inside those callbacks, so the whole pipeline
uses a sync DB session and a sync Redis client instead of mixing in asyncio.

Every DB write opens its own short-lived session (the standard SQLAlchemy
"session per unit of work" pattern) rather than sharing one session across
the whole task. This isn't just tidiness: crew.kickoff() runs its internal
agent loop via asyncio.to_thread() (verified in Stage 2), so on_event can
fire from a different thread than the one that started the task. A shared
Session is not thread-safe, and a live run surfaced exactly that —
concurrent commits on one session corrupted its transaction state
(ResourceClosedError: "This transaction is closed"). A fresh session per
write has no cross-thread shared mutable state, so the race can't happen.
"""

import logging
import re
from pathlib import Path
from uuid import UUID

import redis
from celery.exceptions import SoftTimeLimitExceeded

from app.core.config import settings
from app.crew.crew import run_doc_crew
from app.crew.events import ProgressEvent
from app.db.sync_session import SyncSessionLocal
from app.models.doc import DocDocument, DocEvent, DocJob, JobStatus
from app.parser.budget import enforce_size_budget
from app.parser.knwf import parse_knwf
from app.services.pubsub import job_channel, serialize_event

logger = logging.getLogger(__name__)

_SECRET_PATTERN = re.compile(r"sk-[A-Za-z0-9_-]{10,}")
_MAX_ERROR_LEN = 500

_SIZE_BUDGET_NOTE = (
    "This workflow is large enough that some node configuration details were "
    "shortened before analysis to keep the request a reasonable size. Node "
    "names, connections, and overall structure above are complete; some "
    "deeply nested settings values may be abbreviated."
)


def _record_event(
    redis_client: redis.Redis, job_id: UUID, event_type: str, agent: str | None, message: str
) -> None:
    with SyncSessionLocal() as session:
        row = DocEvent(job_id=job_id, type=event_type, agent=agent, message=message)
        session.add(row)
        session.commit()
        created_at = row.created_at
    redis_client.publish(job_channel(str(job_id)), serialize_event(event_type, agent, message, created_at))


def _set_status(
    job_id: UUID,
    status_: JobStatus,
    *,
    workflow_name: str | None = None,
    error: str | None = None,
) -> None:
    with SyncSessionLocal() as session:
        job = session.get(DocJob, job_id)
        if job is None:
            return
        job.status = status_
        if workflow_name is not None:
            job.workflow_name = workflow_name
        if error is not None:
            job.error = error
        session.commit()


def _sanitize_error(message: str) -> str:
    """Redacts anything shaped like an API key and caps overly long provider
    error text (some LLM client libraries return large JSON error bodies) so
    job.error — logged and shown verbatim in the UI — stays a short, safe
    string instead of leaking a credential or dumping a wall of JSON."""
    redacted = _SECRET_PATTERN.sub("sk-***REDACTED***", message)
    if len(redacted) > _MAX_ERROR_LEN:
        redacted = redacted[:_MAX_ERROR_LEN].rstrip() + "…"
    return redacted


def _insert_note(markdown: str, note: str) -> str:
    """Inserts `note` as the first bullet under the '## Notes' heading (or
    appends a Notes section if the LLM somehow omitted it) — used for
    programmatic notes the model itself doesn't know to write, like the size
    guard below."""
    marker = "## Notes"
    idx = markdown.find(marker)
    if idx == -1:
        return markdown.rstrip("\n") + f"\n\n{marker}\n\n- {note}\n"
    insert_at = idx + len(marker)
    return markdown[:insert_at] + f"\n\n- {note}" + markdown[insert_at:]


def _fail(redis_client: redis.Redis, job_id: UUID, error_message: str) -> None:
    """Records a failure. Best-effort: if the DB write itself fails, log it
    rather than letting a second exception mask the original failure."""
    error_message = _sanitize_error(error_message)
    try:
        _set_status(job_id, JobStatus.FAILED, error=error_message)
        _record_event(redis_client, job_id, "error", None, error_message)
    except Exception:
        logger.exception("generate_doc: failed to record failure for job %s", job_id)


def generate_doc(job_id: UUID) -> None:
    # Explicit socket timeouts: without them a Redis outage mid-run can hang
    # a publish() call at the TCP layer for well over a minute instead of
    # raising — found live by stopping the redis container mid-task. A hung
    # publish here would stall the whole crew run, not just fail one event.
    redis_client = redis.Redis.from_url(settings.redis_url, socket_connect_timeout=5, socket_timeout=5)

    def on_event(event: ProgressEvent) -> None:
        _record_event(redis_client, job_id, event.type, event.agent, event.message)

    try:
        with SyncSessionLocal() as session:
            if session.get(DocJob, job_id) is None:
                logger.error("generate_doc: job %s not found", job_id)
                return

        # A missing key is a deployment/config problem, not something a retry
        # fixes — checked before doing any work so it fails in milliseconds
        # with a clear message instead of only surfacing once the crew makes
        # its first (slow, timeout-bound) call to Anthropic.
        if not settings.anthropic_api_key:
            _fail(redis_client, job_id, "The AI service isn't configured (missing API key). Contact an administrator.")
            return

        file_path = Path(settings.upload_dir) / f"{job_id}.knwf"

        _set_status(job_id, JobStatus.PARSING)
        graph = parse_knwf(file_path.read_bytes())
        was_trimmed = enforce_size_budget(graph)

        _set_status(job_id, JobStatus.RUNNING, workflow_name=graph.name)
        markdown = run_doc_crew(graph, on_event=on_event)
        if was_trimmed:
            markdown = _insert_note(markdown, _SIZE_BUDGET_NOTE)

        with SyncSessionLocal() as session:
            session.add(DocDocument(job_id=job_id, markdown=markdown))
            session.commit()
        _set_status(job_id, JobStatus.COMPLETED)

    except SoftTimeLimitExceeded:
        logger.exception("generate_doc timed out for job %s", job_id)
        _fail(redis_client, job_id, "Documentation generation timed out.")

    except Exception as exc:
        # Sanitize before logging, not just before storing: some provider
        # client libraries echo the request's own API key back in an auth
        # error's message, and logger.exception's traceback would otherwise
        # print that raw exception message straight into the worker's logs.
        message = _sanitize_error(f"{type(exc).__name__}: {exc}")
        logger.error("generate_doc failed for job %s: %s", job_id, message)
        _fail(redis_client, job_id, message)

    finally:
        redis_client.close()
