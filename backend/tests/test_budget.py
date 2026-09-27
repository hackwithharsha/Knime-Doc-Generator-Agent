"""
Tests for the size guard (app/parser/budget.py) that trims per-node `settings`
when a parsed WorkflowGraph's JSON would otherwise be too large for a
comfortable crew prompt. Our two real samples in samples/ never actually hit
this (see CLAUDE.md's Stage 7 note — the largest is ~21KB serialized), so
this is exercised with a synthetic oversized graph instead.
"""

from app.parser.budget import MAX_JSON_CHARS, enforce_size_budget
from app.parser.models import WorkflowGraph, WorkflowNode


def _big_node(node_id: int) -> WorkflowNode:
    # A single node with a wide, deep settings dict — the kind a manually
    # mapped column list or a large SQL query node could plausibly produce.
    return WorkflowNode(
        id=node_id,
        name=f"Node {node_id}",
        node_type="NativeNode",
        factory="org.example.SomeFactory",
        settings={f"column_{i}": "x" * 300 for i in range(30)},
    )


def test_small_graph_is_not_trimmed():
    graph = WorkflowGraph(name="Small", nodes=[_big_node(1)])
    # One node alone is well under budget.
    assert len(graph.model_dump_json()) < MAX_JSON_CHARS
    was_trimmed = enforce_size_budget(graph)
    assert was_trimmed is False
    assert graph.nodes[0].settings == _big_node(1).settings


def test_large_graph_is_trimmed_below_budget():
    graph = WorkflowGraph(name="Big", nodes=[_big_node(i) for i in range(50)])
    assert len(graph.model_dump_json()) > MAX_JSON_CHARS

    was_trimmed = enforce_size_budget(graph)

    assert was_trimmed is True
    assert len(graph.model_dump_json()) < MAX_JSON_CHARS
    # Facts a doc must state accurately are untouched by trimming.
    assert graph.name == "Big"
    assert len(graph.nodes) == 50
    assert [n.id for n in graph.nodes] == list(range(50))
    assert all(n.name == f"Node {n.id}" for n in graph.nodes)
    # Settings themselves were shortened, not just left alone.
    assert graph.nodes[0].settings != _big_node(0).settings
    assert "_truncated_keys" in graph.nodes[0].settings


def test_trimming_recurses_into_children():
    child = WorkflowGraph(name="Child", nodes=[_big_node(i) for i in range(50)])
    parent = WorkflowGraph(
        name="Parent",
        nodes=[WorkflowNode(id=0, name="Component", node_type="SubNode", children=child)],
    )
    assert len(parent.model_dump_json()) > MAX_JSON_CHARS

    was_trimmed = enforce_size_budget(parent)

    assert was_trimmed is True
    assert len(parent.model_dump_json()) < MAX_JSON_CHARS
    assert parent.nodes[0].children is not None
    assert "_truncated_keys" in parent.nodes[0].children.nodes[0].settings
