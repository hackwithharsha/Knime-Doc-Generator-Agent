"""
Builds and runs the two-agent documentation-generation crew (Workflow
Analyst -> Documentation Writer). Agent/task roles, goals, and descriptions
live in config/*.yaml so they can be tuned without touching code.
"""

from pathlib import Path

import yaml
from crewai import LLM, Agent, Crew, Process, Task
from crewai.events import crewai_event_bus

from app.crew.events import OnEvent, ProgressListener
from app.crew.llm import build_llm
from app.parser.models import WorkflowGraph

CONFIG_DIR = Path(__file__).parent / "config"


def _load_yaml(name: str) -> dict:
    with open(CONFIG_DIR / name, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _build_agents(agents_config: dict, llm: LLM) -> dict[str, Agent]:
    return {key: Agent(config=cfg, llm=llm, verbose=False) for key, cfg in agents_config.items()}


def _build_tasks(tasks_config: dict, agents: dict[str, Agent]) -> dict[str, Task]:
    """Builds Task objects in YAML declaration order, resolving each task's
    `context` (a list of task-name strings, our own YAML convention — not a
    crewai-native field) into references to already-built Task objects."""
    tasks: dict[str, Task] = {}
    for key, cfg in tasks_config.items():
        cfg = dict(cfg)
        agent_key = cfg.pop("agent")
        context_keys = cfg.pop("context", [])
        kwargs = {"config": cfg, "agent": agents[agent_key]}
        if context_keys:
            kwargs["context"] = [tasks[k] for k in context_keys]
        tasks[key] = Task(**kwargs)
    return tasks


def build_crew() -> Crew:
    llm = build_llm()
    agents = _build_agents(_load_yaml("agents.yaml"), llm)
    tasks = _build_tasks(_load_yaml("tasks.yaml"), agents)

    return Crew(
        agents=list(agents.values()),
        tasks=list(tasks.values()),
        process=Process.sequential,
        verbose=False,
    )


def run_doc_crew(graph: WorkflowGraph, on_event: OnEvent) -> str:
    """Runs the crew against a parsed workflow and returns the final documentation
    markdown. Progress is reported via on_event for the duration of this call only —
    listener registration is scoped so it can't leak into other crew runs."""
    crew = build_crew()
    workflow_json = graph.model_dump_json(indent=2)

    with crewai_event_bus.scoped_handlers():
        ProgressListener(on_event)
        result = crew.kickoff(inputs={"workflow_json": workflow_json})

    return str(result.raw)
