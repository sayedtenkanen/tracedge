from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator

NodeID = str
HarnessID = str
SkillID = str


class EdgeKind(str):
    sequential = "sequential"
    branch = "branch"
    fallthrough = "fallthrough"


class Edge(BaseModel):
    from_: NodeID = Field(..., alias="from")
    to: NodeID
    kind: str

    model_config = {"populate_by_name": True}


class UPIRNode(BaseModel):
    kind: str
    node_id: NodeID
    # Allow extra fields for node-specific attributes (query, tool, prompt, etc.)
    model_config = {"extra": "allow"}


class UPIR(BaseModel):
    entry: NodeID
    nodes: dict[NodeID, UPIRNode]
    edges: list[Edge] = []
    harness_table: dict[str, Any] = {}
    skill_table: dict[str, Any] = {}
    ir_schema: str = Field(default="typed-executable-graph", alias="schema")

    model_config = {"populate_by_name": True}

    @property
    def schema(self) -> str:
        return self.ir_schema

    @model_validator(mode="after")
    def validate_graph(self) -> UPIR:
        if not self.nodes:
            raise ValueError("nodes must not be empty")
        if self.entry not in self.nodes:
            raise ValueError(f"entry '{self.entry}' not found in nodes")
        for edge in self.edges:
            if edge.from_ not in self.nodes:
                raise ValueError(f"edge source '{edge.from_}' not found in nodes")
            if edge.to not in self.nodes:
                raise ValueError(f"edge target '{edge.to}' not found in nodes")
        return self
