"""
Synchronous SQLAlchemy session for the Celery worker. FastAPI uses the async
engine in app.db.session; the worker needs a sync one because it writes
progress events from inside crewai's blocking crew.kickoff() call, where
there is no running event loop to await into. See CLAUDE.md "Sync vs. async
DB access" for the full rationale. Same models (app.models), same database —
only the driver differs (psycopg2 vs. asyncpg).
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

sync_engine = create_engine(settings.sync_database_url, pool_pre_ping=True)

SyncSessionLocal = sessionmaker(bind=sync_engine, expire_on_commit=False, class_=Session)
