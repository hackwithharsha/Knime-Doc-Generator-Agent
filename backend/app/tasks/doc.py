from uuid import UUID

from app.services.doc_pipeline import generate_doc as _generate_doc
from app.tasks.celery_app import celery_app

# soft_time_limit gives the pipeline a chance to record a clean "timed out"
# failure; time_limit is the hard kill switch shortly after.
@celery_app.task(name="tasks.generate_doc", bind=True, soft_time_limit=240, time_limit=300)
def generate_doc(self, job_id: str) -> None:
    _generate_doc(UUID(job_id))
