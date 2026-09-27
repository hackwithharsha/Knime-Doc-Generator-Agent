"""Validates and persists uploaded .knwf files to UPLOAD_DIR."""

import uuid
from pathlib import Path

import aiofiles
from fastapi import HTTPException, UploadFile, status

from app.core.config import settings

ALLOWED_EXTENSION = ".knwf"
CHUNK_SIZE = 1024 * 1024


async def save_upload(file: UploadFile, job_id: uuid.UUID) -> Path:
    """Validates extension + size, then streams the upload to UPLOAD_DIR/{job_id}.knwf.
    Raises HTTPException(400) for a bad extension or empty file, 413 if it exceeds
    MAX_UPLOAD_MB. Streams in chunks so an oversized file is rejected without
    buffering the whole thing in memory first."""
    if not file.filename or not file.filename.lower().endswith(ALLOWED_EXTENSION):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only {ALLOWED_EXTENSION} files are accepted.",
        )

    max_bytes = settings.max_upload_mb * 1024 * 1024
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest_path = upload_dir / f"{job_id}.knwf"

    size = 0
    try:
        async with aiofiles.open(dest_path, "wb") as out:
            while chunk := await file.read(CHUNK_SIZE):
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"File exceeds the {settings.max_upload_mb} MB limit.",
                    )
                await out.write(chunk)
    except HTTPException:
        dest_path.unlink(missing_ok=True)
        raise
    finally:
        await file.close()

    if size == 0:
        dest_path.unlink(missing_ok=True)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty.")

    return dest_path
