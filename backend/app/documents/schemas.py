"""Pydantic schemas for document upload and response models.

Defines request/response models for the documents API endpoints.
"""

from datetime import datetime

from pydantic import BaseModel


class DocumentResponse(BaseModel):
    """Response schema for a single document."""

    id: int
    company_id: int
    filename: str
    status: str
    key_points: str | None = None
    page_count: int | None = None
    chunk_count: int | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    """Response schema for listing documents."""

    documents: list[DocumentResponse]


class DocumentUploadResponse(BaseModel):
    """Response after successfully uploading a document."""

    id: int
    company_id: int
    filename: str
    status: str
    message: str
