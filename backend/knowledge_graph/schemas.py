from typing import Any

from pydantic import BaseModel, Field


class GraphNode(BaseModel):
    id: str
    label: str
    type: str
    attributes: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    source: str
    target: str
    relation: str
    display_label: str | None = None
    provenance: dict[str, Any] = Field(default_factory=dict)


class KnowledgeGraphResponse(BaseModel):
    student_id: int
    student_code: str
    nodes: list[GraphNode]
    edges: list[GraphEdge]
