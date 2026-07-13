"""Pydantic schemas for the graph module.

Defines request/response models for relationship graph queries,
manual edge creation, and warm path computation.
"""

from pydantic import BaseModel, Field

from app.companies.models import ClientStatus, CompanyStatus, RelationType


class GraphNode(BaseModel):
    """A node in the relationship graph representing a company."""

    id: int
    name: str
    client_status: ClientStatus
    status: CompanyStatus

    model_config = {"from_attributes": True}


class GraphEdge(BaseModel):
    """An edge in the relationship graph representing a relationship."""

    id: int
    source_id: int
    target_id: int
    relation_type: RelationType
    origin: str | None = None
    confidence: float | None = None

    model_config = {"from_attributes": True}


class GraphResponse(BaseModel):
    """Response containing a subgraph centered on a company."""

    nodes: list[GraphNode]
    edges: list[GraphEdge]
    center_node_id: int


class EdgeCreate(BaseModel):
    """Request to manually create a relationship edge."""

    source_id: int
    target_id: int
    relation_type: RelationType = Field(
        ...,
        description="Relationship type: parent, subsidiary, vendor, customer, partner, group_member",
    )


class WarmPathResponse(BaseModel):
    """Response for warm path query from a prospect to the nearest Client."""

    path: list[GraphNode] | None = None
    edges: list[GraphEdge] | None = None
    path_length: int | None = None
    available: bool
