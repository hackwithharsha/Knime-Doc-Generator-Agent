"""
Shared test fixtures. Tests run against the real Postgres/Redis configured
via settings — i.e. inside the api container, where DATABASE_URL/REDIS_URL
already point at the docker-compose services — rather than a mocked or
sqlite substitute, matching this project's small, Postgres-only stack.
Requires migrations to already be applied (`alembic upgrade head`).
"""

import asyncio

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db.session import AsyncSessionLocal
from app.main import app


@pytest.fixture(scope="session")
def event_loop():
    """Session-scoped event loop. app.db.session's async engine is created
    once at import time and its asyncpg connections are bound to whatever
    loop existed then; pytest-asyncio's default per-test loop would make
    every test after the first fail with "Future attached to a different
    loop". One loop for the whole session keeps it consistent throughout."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
async def clean_tables():
    """Truncates the doc_* tables before each test so tests don't see each other's rows."""
    async with AsyncSessionLocal() as session:
        await session.execute(text("TRUNCATE doc_documents, doc_events, doc_jobs CASCADE"))
        await session.commit()
    yield


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
