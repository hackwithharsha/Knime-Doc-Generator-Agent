"""
Size guard for a parsed WorkflowGraph before it's embedded in the crew's
prompt. Nothing in the KNIME format caps how much a single node's `settings`
can hold (e.g. a manually-mapped column list with hundreds of rows) or how
many nodes a workflow can have, so a large enough workflow could make the
analysis task's prompt uncomfortably large even after the parser's existing
noise-stripping (see CLAUDE.md "model settings are noisy"). MAX_JSON_CHARS
isn't a hard model limit — Claude Sonnet's context window is far bigger than
this — it's a cost/latency budget: keep the prompt reasonably sized
regardless of how large a workflow export gets. Trimming only ever touches
`settings` values; node names, annotations, connections, and flow variables
(the facts a doc must state accurately) are never touched.
"""

from collections.abc import Iterator

from app.parser.models import WorkflowGraph, WorkflowNode

MAX_JSON_CHARS = 60_000

# Progressively stricter (max_items, max_str_len) pairs. A single pass isn't
# guaranteed to work — a workflow with many nodes can still exceed budget
# even with each node's settings cut to a handful of short values, so each
# level is retried (from each node's *original* settings, not the previous
# level's already-trimmed result) until the graph fits or levels run out.
_TRIM_LEVELS = [(5, 200), (3, 80), (1, 40), (0, 0)]


def enforce_size_budget(graph: WorkflowGraph, max_chars: int = MAX_JSON_CHARS) -> bool:
    """Trims per-node `settings` in place if the graph's JSON exceeds max_chars.
    Returns True if anything was trimmed, so the caller can note it in the doc."""
    if len(graph.model_dump_json()) <= max_chars:
        return False

    nodes = list(_iter_nodes(graph))
    original_settings = [node.settings for node in nodes]

    for max_items, max_str_len in _TRIM_LEVELS:
        for node, original in zip(nodes, original_settings):
            node.settings = _trim_value(original, max_items, max_str_len)
        if len(graph.model_dump_json()) <= max_chars:
            break

    return True


def _iter_nodes(graph: WorkflowGraph) -> Iterator[WorkflowNode]:
    for node in graph.nodes:
        yield node
        if node.children is not None:
            yield from _iter_nodes(node.children)


def _trim_value(value: object, max_items: int, max_str_len: int) -> object:
    if isinstance(value, dict):
        if max_items == 0:
            return {"_truncated_keys": len(value)} if value else {}
        trimmed = {key: _trim_value(value[key], max_items, max_str_len) for key in list(value)[:max_items]}
        if len(value) > max_items:
            trimmed["_truncated_keys"] = len(value) - max_items
        return trimmed
    if isinstance(value, list):
        if max_items == 0:
            return [f"…({len(value)} items)"] if value else []
        trimmed_list = [_trim_value(v, max_items, max_str_len) for v in value[:max_items]]
        if len(value) > max_items:
            trimmed_list.append(f"…(+{len(value) - max_items} more items)")
        return trimmed_list
    if isinstance(value, str) and len(value) > max_str_len:
        return value[:max_str_len] + "…" if max_str_len > 0 else "…"
    return value
