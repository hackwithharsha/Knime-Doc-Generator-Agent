"""
Parses a KNIME .knwf workflow export into a WorkflowGraph. See CLAUDE.md for the
verified format notes this implementation relies on.
"""

import io
import zipfile
from pathlib import PurePosixPath
from xml.etree.ElementTree import Element

from app.parser.models import WorkflowConnection, WorkflowGraph, WorkflowNode
from app.parser.xmlconfig import JsonValue, config_to_value, get_config, get_entry, iter_configs, parse_config_xml

_SOURCE_KEYWORDS = ("reader", "connector", "loader", "generator", "creator", "importer")
_SINK_KEYWORDS = ("writer", "exporter", "uploader", " sink")
_VIRTUAL_FACTORY_MARKER = "VirtualSubNode"


def _classify_io(display_name: str, factory: str | None) -> tuple[bool, bool]:
    if factory and _VIRTUAL_FACTORY_MARKER in factory:
        return False, False
    text = f"{display_name} {factory or ''}".lower()
    is_source = any(kw in text for kw in _SOURCE_KEYWORDS)
    is_sink = any(kw in text for kw in _SINK_KEYWORDS)
    return is_source, is_sink


def _collect_flow_variables(value: JsonValue) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, v in value.items():
            if key in ("used_variable", "exposed_variable") and isinstance(v, str) and v:
                found.add(v)
            found |= _collect_flow_variables(v)
    elif isinstance(value, list):
        for v in value:
            found |= _collect_flow_variables(v)
    return found


def _read_xml(zf: zipfile.ZipFile, path: str) -> Element:
    return parse_config_xml(zf.read(path))


def _workflow_annotations_text(root: Element) -> str | None:
    annotations_cfg = get_config(root, "annotations")
    if annotations_cfg is None:
        return None
    texts = [text for ann in iter_configs(annotations_cfg) if (text := get_entry(ann, "text"))]
    return "\n\n".join(texts) if texts else None


def _parse_node_settings(zf: zipfile.ZipFile, settings_path: str, node_id: int) -> WorkflowNode:
    root = _read_xml(zf, settings_path)

    # A SubNode (component) has no factory/name of its own; it points at a nested
    # workflow.knime in the same folder, whose `name` entry is the true display name.
    workflow_file = get_entry(root, "workflow-file")
    children: WorkflowGraph | None = None
    if workflow_file:
        subdir = settings_path.rsplit("/", 1)[0]
        children = _parse_workflow_dir(zf, subdir)

    factory = get_entry(root, "factory")
    type_label = get_entry(root, "node-name")
    display_name = get_entry(root, "name") or type_label or (children.name if children else None) or "Unknown"

    annotation_cfg = get_config(root, "nodeAnnotation")
    annotation = get_entry(annotation_cfg, "text") or None
    description = get_entry(root, "customDescription") or None

    model_cfg = get_config(root, "model")
    settings = config_to_value(model_cfg) if model_cfg is not None else {}

    # Flow-variable overrides (Flow Variables tab) live in a separate top-level
    # `variables/tree` block that mirrors `model`'s shape, not inside `model` itself.
    variable_tree = get_config(get_config(root, "variables"), "tree")
    variable_overrides = config_to_value(variable_tree) if variable_tree is not None else {}
    flow_variables = sorted(_collect_flow_variables(settings) | _collect_flow_variables(variable_overrides))
    is_source, is_sink = _classify_io(display_name, factory)

    return WorkflowNode(
        id=node_id,
        name=display_name,
        node_type="SubNode" if workflow_file else "NativeNode",
        factory=factory,
        type_label=type_label,
        annotation=annotation,
        description=description,
        state=get_entry(root, "state"),
        is_source=is_source,
        is_sink=is_sink,
        settings=settings,
        flow_variables=flow_variables,
        children=children,
    )


def _parse_workflow_dir(zf: zipfile.ZipFile, dir_path: str) -> WorkflowGraph:
    root = _read_xml(zf, f"{dir_path}/workflow.knime")
    name = get_entry(root, "name") or PurePosixPath(dir_path).name
    description = _workflow_annotations_text(root)

    nodes: list[WorkflowNode] = []
    for node_cfg in iter_configs(get_config(root, "nodes")):
        node_id = get_entry(node_cfg, "id")
        settings_file = get_entry(node_cfg, "node_settings_file")
        node_type = get_entry(node_cfg, "node_type", "NativeNode")
        full_settings_path = f"{dir_path}/{settings_file}"

        if node_type == "MetaNode":
            # node_settings_file points directly at a nested workflow.knime (no wrapping settings.xml).
            child_dir = full_settings_path.rsplit("/workflow.knime", 1)[0]
            child_graph = _parse_workflow_dir(zf, child_dir)
            nodes.append(
                WorkflowNode(
                    id=node_id,
                    name=child_graph.name,
                    node_type="MetaNode",
                    children=child_graph,
                )
            )
        else:
            nodes.append(_parse_node_settings(zf, full_settings_path, node_id))

    connections = [
        WorkflowConnection(
            source_id=get_entry(c, "sourceID"),
            target_id=get_entry(c, "destID"),
            source_port=get_entry(c, "sourcePort", 0),
            target_port=get_entry(c, "destPort", 0),
        )
        for c in iter_configs(get_config(root, "connections"))
    ]

    incoming = {c.target_id for c in connections}
    outgoing = {c.source_id for c in connections}
    node_ids = [n.id for n in nodes]

    flow_variables: set[str] = set()
    for n in nodes:
        flow_variables |= set(n.flow_variables)

    return WorkflowGraph(
        name=name,
        description=description,
        nodes=nodes,
        connections=connections,
        flow_variables=sorted(flow_variables),
        source_node_ids=[nid for nid in node_ids if nid not in incoming],
        sink_node_ids=[nid for nid in node_ids if nid not in outgoing],
    )


def parse_knwf(file_bytes: bytes) -> WorkflowGraph:
    """
    Parse a .knwf export into a WorkflowGraph. Reads zip entries into memory only
    (never extracts to disk) to avoid zip-slip, and parses XML with defusedxml.
    """
    with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
        candidates = [n for n in zf.namelist() if n.endswith("workflow.knime")]
        if not candidates:
            raise ValueError("Not a valid KNIME workflow export: no workflow.knime found")
        root_path = min(candidates, key=lambda n: n.count("/"))
        root_dir = root_path.rsplit("/", 1)[0]
        return _parse_workflow_dir(zf, root_dir)
