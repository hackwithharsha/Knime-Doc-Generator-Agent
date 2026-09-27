from crewai import LLM

from app.core.config import settings


def build_llm() -> LLM:
    """
    Anthropic Claude LLM for crew agents, configured via LLM_MODEL/ANTHROPIC_API_KEY.
    No `temperature` — Claude Sonnet 5 rejects it outright (verified live:
    "`temperature` is deprecated for this model", HTTP 400), unlike older
    Claude models where it was accepted.
    """
    return LLM(
        model=settings.llm_model,
        api_key=settings.anthropic_api_key,
        max_tokens=4096,
        # Bounds a single hung network call well under Celery's soft_time_limit
        # (see app/tasks/doc.py) so a stalled request fails on its own instead
        # of relying entirely on the task-level backstop.
        timeout=60,
    )
