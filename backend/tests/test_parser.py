from pathlib import Path

from app.parser.knwf import parse_knwf
from app.parser.models import WorkflowGraph

SAMPLES_DIR = Path(__file__).resolve().parents[2] / "samples"
SMALL = SAMPLES_DIR / "Retry Database Connection.knwf"
LARGE = SAMPLES_DIR / "Format Multiple Excel Sheets.knwf"

_SECRET_KEYWORDS = ("password", "credential", "secret", "token", "apikey", "api_key")


def _load(path: Path) -> WorkflowGraph:
    return parse_knwf(path.read_bytes())


def test_parses_small_sample_top_level_structure():
    graph = _load(SMALL)
    assert graph.name == "Retry Database Connection"
    assert graph.description and "Retry Database Connection" in graph.description
    assert {n.id for n in graph.nodes} == {186, 194, 195, 196, 199, 200, 201, 203, 206, 210}
    assert len(graph.connections) == 11


def test_identifies_component_and_recurses():
    graph = _load(SMALL)
    component = next(n for n in graph.nodes if n.id == 210)
    assert component.node_type == "SubNode"
    assert component.children is not None
    assert component.children.name == "Fail Workflow"
    assert {n.id for n in component.children.nodes} == {207, 209, 210, 211, 213, 214}


def test_identifies_sources_and_sinks():
    graph = _load(SMALL)
    sqlite_connector = next(n for n in graph.nodes if n.id == 201)
    assert sqlite_connector.is_source is True
    db_reader = next(n for n in graph.nodes if n.id == 206)
    assert db_reader.is_sink is False  # keyword-based: it's a reader, not a writer
    # Table Creator has no incoming connections -> structural source
    assert 186 in graph.source_node_ids


def test_extracts_key_settings_from_db_table_selector():
    graph = _load(SMALL)
    node = next(n for n in graph.nodes if n.id == 199)
    assert node.settings["dbTable"]["table"] == "compound_activity"


def test_captures_flow_variable_usage():
    graph = _load(SMALL)
    node = next(n for n in graph.nodes if n.id == 201)
    assert "SqlitePath" in node.flow_variables
    assert "SqlitePath" in graph.flow_variables


def test_parses_large_sample_with_metanode():
    graph = _load(LARGE)
    assert graph.name == "Format Multiple Excel Sheets"
    metanode = next(n for n in graph.nodes if n.node_type == "MetaNode")
    assert metanode.name == "XLS Formatting"
    assert metanode.children is not None
    assert len(metanode.children.nodes) > 0


def test_rule_engine_expressions_captured():
    graph = _load(LARGE)
    rule_node = next(n for n in graph.nodes if n.factory and "RuleEngine" in n.factory)
    rules = rule_node.settings["rules"]
    assert isinstance(rules, list)
    assert any(isinstance(r, str) and "Row" in r for r in rules)


def test_type_mapping_noise_is_skipped():
    graph = _load(SMALL)
    connector = next(n for n in graph.nodes if n.id == 201)
    assert "external_to_knime_mapping" not in connector.settings
    assert "knime_to_external_mapping" not in connector.settings


def test_no_secrets_survive_redaction():
    for path in (SMALL, LARGE):
        graph = _load(path)
        _assert_no_secrets_in_graph(graph)


def _assert_no_secrets_in_graph(graph: WorkflowGraph):
    for node in graph.nodes:
        _assert_no_secrets_in_value(node.settings)
        if node.children:
            _assert_no_secrets_in_graph(node.children)


def _assert_no_secrets_in_value(value):
    if isinstance(value, dict):
        for key, v in value.items():
            if any(s in key.lower() for s in _SECRET_KEYWORDS):
                assert v == "[REDACTED]", f"secret-like key {key!r} not redacted: {v!r}"
            _assert_no_secrets_in_value(v)
    elif isinstance(value, list):
        for v in value:
            _assert_no_secrets_in_value(v)
