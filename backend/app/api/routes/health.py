from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.core.config import settings

import redis.asyncio as aioredis

router = APIRouter()


@router.get("/health")
async def health(db: AsyncSession = Depends(get_db)) -> dict[str, object]:
    checks: dict[str, str] = {}

    # DB check. Only the exception's type name is surfaced, not str(exc) — this
    # is an unauthenticated public endpoint, and a driver-level connection error
    # can otherwise echo back the DSN (including credentials) in its message.
    try:
        await db.execute(text("SELECT 1"))
        checks["db"] = "ok"
    except Exception as exc:
        checks["db"] = f"error: {type(exc).__name__}"

    # Redis check
    try:
        r = aioredis.from_url(settings.redis_url)
        await r.ping()
        await r.aclose()
        checks["redis"] = "ok"
    except Exception as exc:
        checks["redis"] = f"error: {type(exc).__name__}"

    ok = all(v == "ok" for v in checks.values())
    return {"status": "ok" if ok else "degraded", "checks": checks}
