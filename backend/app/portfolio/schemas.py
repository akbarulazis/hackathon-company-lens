"""Pydantic schemas for portfolio API endpoints.

Defines request/response models for portfolio import, suggestion queue,
and company portfolio data retrieval.
"""

from datetime import date, datetime

from pydantic import BaseModel, Field


class ImportResponse(BaseModel):
    """Response after importing a portfolio file."""

    matched: int
    unmatched: int
    total: int
    errors: list[str] = Field(default_factory=list)
    message: str


class SuggestionResponse(BaseModel):
    """Response schema for a single portfolio suggestion."""

    id: int
    raw_name: str
    matched_company_id: int | None = None
    similarity_score: float | None = None
    status: str
    as_of_date: date | None = None
    raw_metrics: dict | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SuggestionListResponse(BaseModel):
    """Response schema for listing pending suggestions."""

    suggestions: list[SuggestionResponse]
    total: int


class ResolveRequest(BaseModel):
    """Request body for resolving a suggestion."""

    resolution: str = Field(
        ..., description="Either 'accepted' or 'rejected'"
    )
    company_id: int | None = Field(
        None, description="Company to link to (required for 'accepted')"
    )


class ResolveResponse(BaseModel):
    """Response after resolving a suggestion."""

    id: int
    raw_name: str
    status: str
    matched_company_id: int | None = None
    message: str


class SnapshotData(BaseModel):
    """A single portfolio snapshot."""

    id: int
    as_of_date: str
    metrics: dict


class PortfolioResponse(BaseModel):
    """Response for company portfolio data."""

    company_id: int
    company_name: str
    client_status: str
    latest_snapshot: SnapshotData | None = None
    history: list[SnapshotData] = Field(default_factory=list)
    products_held: list = Field(default_factory=list)
    message: str | None = None
