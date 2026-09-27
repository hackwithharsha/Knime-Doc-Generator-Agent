import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.doc import JobStatus


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workflow_name: str | None
    filename: str
    status: JobStatus
    error: str | None
    created_at: datetime
    updated_at: datetime


class JobDetailOut(JobOut):
    markdown: str | None = None
