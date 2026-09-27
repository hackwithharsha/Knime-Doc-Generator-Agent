"""
Redis pub/sub channel naming and event JSON shape, shared between the Celery
worker (sync publisher, app.services.doc_pipeline) and the FastAPI SSE
endpoint (async subscriber, app.api.routes.doc).
"""

import json
from datetime import datetime, timezone
from typing import Any

TERMINAL_EVENT_TYPES = {"crew_completed", "error"}


def job_channel(job_id: str) -> str:
    return f"job:{job_id}"


def serialize_event(event_type: str, agent: str | None, message: str, created_at: datetime | None = None) -> str:
    payload: dict[str, Any] = {
        "type": event_type,
        "agent": agent,
        "message": message,
        "created_at": (created_at or datetime.now(timezone.utc)).isoformat(),
    }
    return json.dumps(payload)
