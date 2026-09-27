from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "knime_doc",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks.workflow", "app.tasks.doc"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    # Without an explicit socket timeout, redis-py/kombu can hang at the TCP
    # layer for well over a minute when the broker is unreachable — found
    # live by stopping the redis container and watching `generate_doc.delay()`
    # block instead of raising the exception app/api/routes/doc.py expects to
    # catch. This makes a broker outage fail in ~5s instead.
    broker_transport_options={"socket_connect_timeout": 5, "socket_timeout": 5},
    broker_connection_timeout=5,
    # Default publish retries (3 attempts with backoff) would otherwise still
    # add up to a slow, multi-attempt failure on top of the timeout above —
    # one fast, clear failure is what app/api/routes/doc.py's try/except needs.
    task_publish_retry=False,
)
