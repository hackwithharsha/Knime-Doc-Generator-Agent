"""
Tests for app/services/doc_pipeline.py's failure-handling helpers and the
fail-fast missing-API-key guard. The full happy path (real crew run) is only
exercised by a live end-to-end run (see CLAUDE.md progress log) — these cover
the error paths that must produce a clear result instead of hanging.
"""

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.doc import DocJob, JobStatus
from app.services.doc_pipeline import _insert_note, _sanitize_error, generate_doc


def test_sanitize_error_redacts_api_keys():
    message = "AuthenticationError: invalid x-api-key sk-ant-api03-abcDEF1234567890"
    sanitized = _sanitize_error(message)
    assert "sk-ant-api03-abcDEF1234567890" not in sanitized
    assert "REDACTED" in sanitized


def test_sanitize_error_caps_long_messages():
    sanitized = _sanitize_error("BadResponse: " + "x" * 2000)
    assert len(sanitized) <= 501  # _MAX_ERROR_LEN + the trailing ellipsis char
    assert sanitized.endswith("…")


def test_insert_note_under_existing_notes_heading():
    markdown = "## Purpose\n\nText.\n\n## Notes\n\n- Existing note.\n"
    result = _insert_note(markdown, "New note.")
    notes_section = result.split("## Notes", 1)[1]
    assert "New note." in notes_section
    assert notes_section.index("New note.") < notes_section.index("Existing note.")


def test_insert_note_adds_section_when_missing():
    markdown = "## Purpose\n\nText.\n"
    result = _insert_note(markdown, "New note.")
    assert "## Notes" in result
    assert "New note." in result


async def test_generate_doc_fails_fast_without_api_key(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "")

    async with AsyncSessionLocal() as session:
        job = DocJob(filename="demo.knwf", status=JobStatus.QUEUED)
        session.add(job)
        await session.commit()
        job_id = job.id

    generate_doc(job_id)  # sync call — safe to invoke directly in an async test

    async with AsyncSessionLocal() as session:
        refreshed = await session.get(DocJob, job_id)
        assert refreshed is not None
        assert refreshed.status == JobStatus.FAILED
        assert "API key" in refreshed.error
