"""Workspace request/response schemas.

Provides Pydantic models for workspace CRUD endpoints including
workspace creation, update, list, detail, and company management.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class WorkspaceCreate(BaseModel):
    """Schema for creating or updating a workspace."""

    name: str = Field(..., min_length=1, max_length=100)


class WorkspaceUpdate(BaseModel):
    """Schema for updating a workspace name."""

    name: str = Field(..., min_length=1, max_length=100)


class CompanyInWorkspace(BaseModel):
    """Brief company info for workspace detail view."""

    id: int
    name: str
    status: str
    client_status: str
    industry: str | None = None
    overall_score: float | None = None
    added_at: datetime

    class Config:
        from_attributes = True


class WorkspaceResponse(BaseModel):
    """Response schema for workspace list items."""

    id: int
    name: str
    company_count: int
    company_limit: int
    created_at: datetime

    class Config:
        from_attributes = True


class WorkspaceDetail(BaseModel):
    """Detailed workspace response including companies."""

    id: int
    name: str
    company_count: int
    company_limit: int
    created_at: datetime
    updated_at: datetime
    companies: list[CompanyInWorkspace] = []

    class Config:
        from_attributes = True


class AddCompanyRequest(BaseModel):
    """Request to add a company to a workspace."""

    company_id: int
