from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    database_url: str = "postgresql+asyncpg://knime:knime_dev@localhost:5432/knime_sop"

    @property
    def sync_database_url(self) -> str:
        """Sync (psycopg2) variant of database_url, for the Celery worker.
        See CLAUDE.md "Sync vs. async DB access" for why the worker needs this."""
        return self.database_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Celery
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # LLM
    anthropic_api_key: str = ""
    llm_model: str = "anthropic/claude-sonnet-5"

    # App
    upload_dir: str = "/tmp/knime_uploads"
    max_upload_mb: int = 50


settings = Settings()
