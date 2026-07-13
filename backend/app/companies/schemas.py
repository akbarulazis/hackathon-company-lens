"""Company search and detail response schemas.

Pydantic models for company search results, search responses,
and company detail views.
"""

from datetime import date, datetime

from pydantic import BaseModel

from app.companies.models import ClientStatus, CompanyStatus


class SearchResult(BaseModel):
    """Individual company search result."""

    id: int
    name: str
    client_status: ClientStatus
    industry: str | None = None
    overall_score: float | None = None
    similarity: float

    model_config = {"from_attributes": True}


class SearchResponse(BaseModel):
    """Search response with results list and research availability flag."""

    results: list[SearchResult]
    can_research: bool = False
    query: str


class CompanyDetailResponse(BaseModel):
    """Full company profile detail response."""

    id: int
    name: str
    status: CompanyStatus
    client_status: ClientStatus
    acquisition_brief: str | None = None
    industry: str | None = None
    founded_year: int | None = None
    headquarters: str | None = None
    employee_count: int | None = None
    annual_revenue: float | None = None
    funding_total: float | None = None
    market_cap: float | None = None
    company_website: str | None = None
    linkedin_url: str | None = None
    ticker: str | None = None
    overall_score: float | None = None
    financial_health: float | None = None
    business_risk: float | None = None
    growth_potential: float | None = None
    product_fit: float | None = None
    relationship_accessibility: float | None = None
    financial_health_insight: str | None = None
    business_risk_insight: str | None = None
    growth_potential_insight: str | None = None
    product_fit_insight: str | None = None
    relationship_accessibility_insight: str | None = None
    overall_insight: str | None = None
    revenue_projection: dict | None = None
    client_since: date | None = None
    products_held: list | dict | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ResearchRequest(BaseModel):
    """Request to initiate research for a new company."""

    company_name: str


class DuplicateCheckResult(BaseModel):
    """Result of a case-insensitive duplicate check."""

    is_duplicate: bool
    existing_company_id: int | None = None
    existing_company_name: str | None = None
