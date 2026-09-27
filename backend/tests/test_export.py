"""
Tests for the DOCX/PDF export endpoint. Inserts a fake COMPLETED job +
DocDocument directly (bypassing the crew, same approach as the SSE
replay-of-terminal-job test) so these run fast and without a live LLM call —
real document quality is verified separately by an end-to-end run (see
CLAUDE.md progress log).
"""

import uuid

from app.db.session import AsyncSessionLocal
from app.models.doc import DocDocument, DocJob, JobStatus

_SAMPLE_MARKDOWN = """## Purpose

To be confirmed by workflow owner.

## Inputs

- **Table Creator** (id 1): dummy input.

## Outputs

- **DB Reader** (id 2): reads `demo_table`.

## Transformation Steps

1. **Step one** — does the thing.
   - a sub-detail
2. Step two

## Notes

None.
"""


async def _make_completed_job(workflow_name: str = "Demo Workflow") -> uuid.UUID:
    async with AsyncSessionLocal() as session:
        job = DocJob(filename="demo.knwf", status=JobStatus.COMPLETED, workflow_name=workflow_name)
        session.add(job)
        await session.flush()
        session.add(DocDocument(job_id=job.id, markdown=_SAMPLE_MARKDOWN))
        await session.commit()
        return job.id


async def test_export_not_found(client):
    resp = await client.get(f"/api/doc/jobs/{uuid.uuid4()}/export?format=docx")
    assert resp.status_code == 404


async def test_export_bad_format(client):
    job_id = await _make_completed_job()
    resp = await client.get(f"/api/doc/jobs/{job_id}/export?format=txt")
    assert resp.status_code == 422


async def test_export_not_ready(client):
    async with AsyncSessionLocal() as session:
        job = DocJob(filename="demo.knwf", status=JobStatus.RUNNING)
        session.add(job)
        await session.commit()
        job_id = job.id

    resp = await client.get(f"/api/doc/jobs/{job_id}/export?format=pdf")
    assert resp.status_code == 409


async def test_export_docx(client):
    job_id = await _make_completed_job("My Workflow")
    resp = await client.get(f"/api/doc/jobs/{job_id}/export?format=docx")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert "My Workflow.docx" in resp.headers["content-disposition"]
    assert resp.content[:2] == b"PK"  # DOCX is a zip archive


async def test_export_pdf(client):
    job_id = await _make_completed_job("My Workflow")
    resp = await client.get(f"/api/doc/jobs/{job_id}/export?format=pdf")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert "My Workflow.pdf" in resp.headers["content-disposition"]
    assert resp.content[:5] == b"%PDF-"
