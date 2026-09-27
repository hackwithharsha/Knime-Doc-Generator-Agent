from app.tasks.celery_app import celery_app


@celery_app.task(name="tasks.ping", bind=True)
def ping(self: object) -> str:
    """Smoke-test task — verifies the worker is alive and reachable."""
    return "pong"
