"""Companies API router.

Provides endpoints for company search, detail retrieval,
research initiation, and research refresh. All endpoints
require authentication via get_current_user dependency.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.companies.schemas import (
    CompanyDetailResponse,
    ResearchRequest,
    SearchResponse,
)
from app.companies.service import CompanyError, get_company_detail, initiate_research, search
from app.dependencies import get_db, get_redis
from app.jobs.registry import enqueue_job, is_job_pending_or_running
from app.research.worker import validate_refresh_preconditions

router = APIRouter(prefix="/api/companies", tags=["companies"])


class ErrorResponse(BaseModel):
    """Standard error response."""

    detail: str


class ResearchInitiatedResponse(BaseModel):
    """Response after successfully initiating research."""

    id: int
    name: str
    status: str
    message: str


class RefreshResponse(BaseModel):
    """Response for research refresh request."""

    id: int
    message: str


@router.get(
    "/search",
    response_model=SearchResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid or expired token"},
    },
)
async def search_companies(
    q: str = Query(default="", description="Search query (min 2 characters)"),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SearchResponse:
    """Search companies by name with fuzzy matching.

    Returns up to 10 matching Company_Profiles ranked by pg_trgm
    similarity score descending. Returns an empty result set without
    performing a database search if the query is fewer than 2 characters.
    Sets can_research=True when no matches are found for a valid query.
    """
    return await search(session, q)


@router.get(
    "/{company_id}",
    response_model=CompanyDetailResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid or expired token"},
        404: {"model": ErrorResponse, "description": "Company not found"},
    },
)
async def get_company(
    company_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CompanyDetailResponse:
    """Get full company profile detail by ID."""
    try:
        return await get_company_detail(session, company_id)
    except CompanyError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.post(
    "/research",
    response_model=ResearchInitiatedResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid or expired token"},
        409: {"model": ErrorResponse, "description": "Company already exists"},
    },
)
async def research_company(
    data: ResearchRequest,
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: User = Depends(get_current_user),
) -> ResearchInitiatedResponse:
    """Initiate research for a new company.

    Creates the company record and enqueues the research pipeline ARQ job.
    """
    try:
        company = await initiate_research(session, data.company_name)
        await session.commit()

        # Enqueue the research pipeline job
        from arq import ArqRedis
        arq_redis = ArqRedis(pool_or_conn=redis.connection_pool)
        await enqueue_job(
            arq_redis=arq_redis,
            redis=redis,
            job_type="run_research",
            resource_id=str(company.id),
            company_id=company.id,
            user_id=current_user.id,
        )

        return ResearchInitiatedResponse(
            id=company.id,
            name=company.name,
            status=company.status.value if hasattr(company.status, "value") else str(company.status),
            message=f"Research initiated for '{company.name}'",
        )
    except CompanyError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.post(
    "/{company_id}/refresh",
    response_model=RefreshResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid or expired token"},
        404: {"model": ErrorResponse, "description": "Company not found"},
        409: {"model": ErrorResponse, "description": "Company not eligible for refresh"},
    },
)
async def refresh_company_research(
    company_id: int,
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: User = Depends(get_current_user),
) -> RefreshResponse:
    """Re-execute research pipeline for an existing company.

    Validates that the company has Client_Status="Prospect" AND status="ready".
    Returns 409 if preconditions are not met or if a refresh is already in progress.
    On success, enqueues the refresh_research ARQ job.
    """
    # Verify company exists
    try:
        company = await get_company_detail(session, company_id)
    except CompanyError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

    # Validate refresh preconditions
    eligible = await validate_refresh_preconditions(session, company_id)
    if not eligible:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Company '{company.name}' is not eligible for refresh. "
                "Requires client_status='prospect' AND status='ready'."
            ),
        )

    # Check if a research job is already in progress (deduplication)
    # Both run_research and refresh_research are mutually exclusive for same company
    if await is_job_pending_or_running(
        redis, "run_research", str(company_id)
    ) or await is_job_pending_or_running(
        redis, "refresh_research", str(company_id)
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A research job is already in progress for company '{company.name}'.",
        )

    # Enqueue the refresh research job
    from arq import ArqRedis

    arq_redis = ArqRedis(pool_or_conn=redis.connection_pool)
    job_id = await enqueue_job(
        arq_redis=arq_redis,
        redis=redis,
        job_type="refresh_research",
        resource_id=str(company_id),
        company_id=company_id,
        user_id=current_user.id,
    )

    if job_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Failed to enqueue refresh job for company '{company.name}'.",
        )

    return RefreshResponse(
        id=company.id,
        message=f"Research refresh queued for '{company.name}' (job_id={job_id})",
    )
