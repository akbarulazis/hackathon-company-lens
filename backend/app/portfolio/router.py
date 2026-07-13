"""Portfolio API router.

Provides endpoints for:
- POST /api/portfolio/import — Upload CSV/TSV portfolio extract
- GET /api/portfolio/queue — List pending reconciliation suggestions
- POST /api/portfolio/queue/{id}/resolve — Resolve a suggestion (accept/reject)
- GET /api/companies/{id}/portfolio — Get company portfolio data

All endpoints require authentication. Portfolio data is NEVER sent to LLMs.
"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.dependencies import get_db
from app.portfolio.schemas import (
    ImportResponse,
    PortfolioResponse,
    ResolveRequest,
    ResolveResponse,
    SnapshotData,
    SuggestionListResponse,
    SuggestionResponse,
)
from app.portfolio.service import PortfolioError, get_portfolio, import_file, resolve_suggestion

router = APIRouter(tags=["portfolio"])


class ErrorResponse(BaseModel):
    """Standard error response."""

    detail: str


@router.post(
    "/api/portfolio/import",
    response_model=ImportResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid file format"},
        401: {"model": ErrorResponse, "description": "Invalid or expired token"},
    },
)
async def upload_portfolio(
    file: UploadFile,
    as_of_date: date | None = Query(
        None, description="Snapshot date (defaults to today)"
    ),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ImportResponse:
    """Upload a CSV/TSV portfolio extract for import.

    Parses the file, reconciles company names against existing profiles,
    stores portfolio snapshots for matched companies, and queues
    unmatched names for manual resolution.
    """
    filename = file.filename or ""

    # Validate file extension
    if not filename.lower().endswith((".csv", ".tsv", ".xlsx", ".xls")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be CSV (.csv), TSV (.tsv), or Excel (.xlsx/.xls)",
        )

    # Read file content
    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File is empty",
        )

    try:
        result = await import_file(
            session=session,
            file_content=content,
            filename=filename,
            as_of_date=as_of_date,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Import failed: {str(e)}",
        )

    return ImportResponse(
        matched=result["matched"],
        unmatched=result["unmatched"],
        total=result["total"],
        errors=result.get("errors", []),
        message=(
            f"Import complete: {result['matched']} matched, "
            f"{result['unmatched']} queued for review, "
            f"{result['total']} total rows processed."
        ),
    )


@router.get(
    "/api/portfolio/queue",
    response_model=SuggestionListResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid or expired token"},
    },
)
async def list_queue(
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SuggestionListResponse:
    """List pending portfolio reconciliation suggestions.

    Returns all unresolved suggestions for manual review, ordered
    by creation date descending (newest first).
    """
    from app.portfolio import repository

    suggestions = await repository.list_pending_suggestions(session)

    return SuggestionListResponse(
        suggestions=[
            SuggestionResponse.model_validate(s) for s in suggestions
        ],
        total=len(suggestions),
    )


@router.post(
    "/api/portfolio/queue/{suggestion_id}/resolve",
    response_model=ResolveResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid or expired token"},
        404: {"model": ErrorResponse, "description": "Suggestion not found"},
        409: {"model": ErrorResponse, "description": "Suggestion already resolved"},
        422: {"model": ErrorResponse, "description": "Invalid resolution"},
    },
)
async def resolve_queue_item(
    suggestion_id: int,
    body: ResolveRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ResolveResponse:
    """Resolve a pending portfolio suggestion.

    Accepts or rejects a suggestion. If accepted with a company_id,
    the suggestion's raw metrics are stored as a portfolio snapshot
    for the linked company, and the company is promoted to Client status.
    """
    try:
        result = await resolve_suggestion(
            session=session,
            suggestion_id=suggestion_id,
            resolution=body.resolution,
            company_id=body.company_id,
        )
    except PortfolioError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

    return ResolveResponse(
        id=result["id"],
        raw_name=result["raw_name"],
        status=result["status"],
        matched_company_id=result["matched_company_id"],
        message=result["message"],
    )


@router.get(
    "/api/companies/{company_id}/portfolio",
    response_model=PortfolioResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Not a client company"},
        401: {"model": ErrorResponse, "description": "Invalid or expired token"},
        404: {"model": ErrorResponse, "description": "Company not found"},
    },
)
async def get_company_portfolio(
    company_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PortfolioResponse:
    """Get company portfolio data (latest snapshot + history).

    Returns KPI data, snapshot history, and products-held for clients.
    Returns an error for non-client companies or missing companies.
    """
    try:
        data = await get_portfolio(session=session, company_id=company_id)
    except PortfolioError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

    latest = None
    if data["latest_snapshot"]:
        latest = SnapshotData(**data["latest_snapshot"])

    history = [SnapshotData(**s) for s in data["history"]]

    return PortfolioResponse(
        company_id=data["company_id"],
        company_name=data["company_name"],
        client_status=data["client_status"],
        latest_snapshot=latest,
        history=history,
        products_held=data["products_held"],
        message=data["message"],
    )
