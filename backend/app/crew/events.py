"""
Progress events emitted while a crew runs, and the CrewAI event-bus listener
that produces them. Uses CrewAI's event bus (crewai.events) rather than
step_callback/task_callback: the bus gives finer-grained, per-event-type
signals (agent started, LLM call started, tool used, task/crew done or
failed) and step_callback has open reliability reports upstream, whereas the
event bus is the actively maintained mechanism (verified against the
installed crewai==1.15.22 package — see CLAUDE.md).
"""

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

from crewai.events import (
    AgentExecutionErrorEvent,
    AgentExecutionStartedEvent,
    BaseEventListener,
    CrewKickoffCompletedEvent,
    CrewKickoffFailedEvent,
    LLMCallStartedEvent,
    TaskCompletedEvent,
    TaskFailedEvent,
    ToolUsageStartedEvent,
    crewai_event_bus,
)

_RoleBearingEvent = (
    AgentExecutionStartedEvent
    | LLMCallStartedEvent
    | ToolUsageStartedEvent
    | TaskCompletedEvent
    | TaskFailedEvent
    | AgentExecutionErrorEvent
)

EventType = Literal[
    "agent_started",
    "agent_thinking",
    "tool_used",
    "task_completed",
    "crew_completed",
    "error",
]


class ProgressEvent(BaseModel):
    type: EventType
    agent: str | None = None
    message: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


OnEvent = Callable[[ProgressEvent], None]


class ProgressListener(BaseEventListener):
    """Translates CrewAI bus events into short, human-readable ProgressEvents."""

    def __init__(self, on_event: OnEvent) -> None:
        self._on_event = on_event
        super().__init__()

    def setup_listeners(self, bus: object) -> None:
        # `bus` is crewai's CrewAIEventsBus, but that class lives in a private
        # submodule (crewai.events.event_bus) not re-exported from crewai.events
        # — only the singleton instance is public. Typing it as `object` avoids
        # importing from crewai's internals, which CLAUDE.md already flags as
        # changing often between versions.
        @bus.on(AgentExecutionStartedEvent)
        def _(source, event):
            role = self._agent_role(event)
            self._emit("agent_started", role, f"{role} started working")

        @bus.on(LLMCallStartedEvent)
        def _(source, event):
            role = self._agent_role(event)
            self._emit("agent_thinking", role, f"{role} is thinking...")

        @bus.on(ToolUsageStartedEvent)
        def _(source, event):
            role = self._agent_role(event)
            self._emit("tool_used", role, f"{role} used tool '{event.tool_name}'")

        @bus.on(TaskCompletedEvent)
        def _(source, event):
            task_label = event.task_name or "task"
            self._emit("task_completed", self._agent_role(event), f"'{task_label}' completed")

        @bus.on(TaskFailedEvent)
        def _(source, event):
            self._emit("error", self._agent_role(event), f"Task failed: {event.error}")

        @bus.on(AgentExecutionErrorEvent)
        def _(source, event):
            role = self._agent_role(event)
            self._emit("error", role, f"{role} hit an error: {event.error}")

        @bus.on(CrewKickoffCompletedEvent)
        def _(source, event):
            self._emit("crew_completed", None, "Crew finished — doc generated")

        @bus.on(CrewKickoffFailedEvent)
        def _(source, event):
            self._emit("error", None, f"Crew failed: {event.error}")

    @staticmethod
    def _agent_role(event: _RoleBearingEvent) -> str | None:
        """event.agent_role is unpopulated for several event types (verified
        against the installed crewai==1.15.22); fall back to the nested
        agent/task objects, which are reliable."""
        if getattr(event, "agent_role", None):
            return event.agent_role
        agent = getattr(event, "agent", None)
        if agent is not None:
            return agent.role
        task = getattr(event, "task", None)
        if task is not None and getattr(task, "agent", None) is not None:
            return task.agent.role
        return None

    def _emit(self, event_type: EventType, agent: str | None, message: str) -> None:
        try:
            self._on_event(ProgressEvent(type=event_type, agent=agent, message=message))
        except Exception:
            # Progress reporting is best-effort; a broken callback (e.g. a
            # dropped Redis connection) must never take down the crew run.
            pass
