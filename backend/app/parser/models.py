from pydantic import BaseModel, Field


class WorkflowConnection(BaseModel):
    source_id: int
    target_id: int
    source_port: int = 0
    target_port: int = 0


class WorkflowNode(BaseModel):
    id: int
    name: str
    node_type: str  # "NativeNode" | "MetaNode" | "SubNode"
    factory: str | None = None
    type_label: str | None = None
    annotation: str | None = None
    description: str | None = None
    state: str | None = None
    is_source: bool = False
    is_sink: bool = False
    settings: dict = Field(default_factory=dict)
    flow_variables: list[str] = Field(default_factory=list)
    children: "WorkflowGraph | None" = None


class WorkflowGraph(BaseModel):
    name: str
    description: str | None = None
    nodes: list[WorkflowNode] = Field(default_factory=list)
    connections: list[WorkflowConnection] = Field(default_factory=list)
    flow_variables: list[str] = Field(default_factory=list)
    source_node_ids: list[int] = Field(default_factory=list)
    sink_node_ids: list[int] = Field(default_factory=list)


WorkflowNode.model_rebuild()
