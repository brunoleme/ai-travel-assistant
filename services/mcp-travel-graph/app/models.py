"""Contract and request/response models for graph_rag.schema.json."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


GRAPH_NODE_TYPES = frozenset(
    {
        "city",
        "place",
        "poi",
        "itinerary",
        "dayplan",
        "activity_type",
        "advice",
        "constraint",
    }
)


class GraphRAGRequest(BaseModel):
    """Request payload nested inside the main request."""

    user_query: str = Field(min_length=1)
    destination: Optional[str] = None
    lang: Optional[str] = None
    limit: Optional[int] = Field(default=None, ge=1, le=50)
    debug: bool = False


class RetrieveTravelGraphPayload(BaseModel):
    """Top-level request payload matching contract schema."""

    x_contract_version: str = Field(default="1.0")
    request: GraphRAGRequest


class Evidence(BaseModel):
    """Evidence for an edge (video segment)."""

    videoUrl: str = Field(min_length=8)
    timestampUrl: str = Field(min_length=8)
    startSec: int = Field(ge=0)
    endSec: int = Field(ge=0)
    chunkIdx: Optional[int] = None


class GraphNode(BaseModel):
    """Node in the subgraph matching contract schema."""

    id: str = Field(min_length=2)
    type: str = Field(
        description="One of city, place, poi, itinerary, dayplan, activity_type, advice, constraint"
    )
    name: str = Field(min_length=1)
    aliases: list[str] = Field(default_factory=list)
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    """Edge in the subgraph with evidence."""

    source: str
    type: str
    target: str
    properties: dict[str, Any] = Field(default_factory=dict)
    evidence: Evidence


class Subgraph(BaseModel):
    """Subgraph: nodes and edges."""

    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)


class PathItem(BaseModel):
    """One path (e.g. itinerary day sequence) for narrative answers."""

    path_id: str
    label: Optional[str] = None
    nodes: list[str] = Field(default_factory=list)
    edges: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)


class RetrieveTravelGraphResponse(BaseModel):
    """Response matching contract schema."""

    x_contract_version: str = "1.0"
    request: GraphRAGRequest
    subgraph: Subgraph
    paths: Optional[list[PathItem]] = None
    debug: Optional[dict[str, Any]] = None
