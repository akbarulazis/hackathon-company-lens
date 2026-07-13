"""Pydantic schemas for the comparison module.

Defines request/response models for initiating comparisons and
retrieving comparison reports.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class CompareRequest(BaseModel):
    """Request schema for initiating a company comparison.

    Requires exactly 2 or 3 company IDs that are in the workspace
    and have status "ready".
    """

    company_ids: list[int] = Field(
        ...,
        min_length=2,
        max_length=3,
        description="List of 2-3 company IDs to compare",
    )


class ComparisonReportResponse(BaseModel):
    """Response schema for a comparison report."""

    id: int
    workspace_id: int
    company_ids: list[int]
    html_content: str | None = None
    is_fallback: bool
    created_at: datetime

    model_config = {"from_attributes": True}
