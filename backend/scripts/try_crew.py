"""
Parses a sample .knwf workflow and runs the documentation crew against it,
printing progress events as they arrive and the final documentation markdown.

Usage:
    ANTHROPIC_API_KEY=sk-ant-... python scripts/try_crew.py [path/to/file.knwf]

Defaults to samples/Retry Database Connection.knwf if no path is given.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/

from app.crew.events import ProgressEvent
from app.crew.crew import run_doc_crew
from app.parser.knwf import parse_knwf

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SAMPLE = REPO_ROOT / "samples" / "Retry Database Connection.knwf"


def print_event(event: ProgressEvent) -> None:
    ts = event.timestamp.strftime("%H:%M:%S")
    agent = f"[{event.agent}] " if event.agent else ""
    print(f"{ts} {event.type:<15} {agent}{event.message}")


def main() -> None:
    sample_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SAMPLE
    print(f"Parsing {sample_path.name}...")
    graph = parse_knwf(sample_path.read_bytes())
    print(f"Parsed workflow '{graph.name}' — {len(graph.nodes)} top-level nodes.\n")

    print("Running crew...\n")
    doc_markdown = run_doc_crew(graph, on_event=print_event)

    print("\n" + "=" * 80)
    print("FINAL DOCUMENTATION")
    print("=" * 80 + "\n")
    print(doc_markdown)


if __name__ == "__main__":
    main()
