"""Charts and analytics API router.

Provides endpoints for score history per company and workspace-level
analytics data (grouped bar/radar comparison + leaderboard).
All endpoints require authentication.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.charts.schemas import (
    CompanyScores,
    LeaderboardEntry,
    ScoreHistoryItem,
    ScoreHistoryResponse,
    WorkspaceAnalyticsResponse,
)
from app.companies.models import CompanyProfile, ScoreSnapshot
from app.dependencies import get_db
from app.workspaces.models import Workspace, WorkspaceCompany

router = APIRouter(prefix="/api", tags=["charts"])


@router.get(
    "/companies/{company_id}/scores/history",
    response_model=ScoreHistoryResponse,
)
async def get_score_history(
    company_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ScoreHistoryResponse:
    """Return all score snapshots for a company, ordered by scored_at ascending.

    Used for rendering score history line charts on the frontend.
    """
    # Verify company exists
    result = await session.execute(
        select(CompanyProfile).where(CompanyProfile.id == company_id)
    )
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company not found",
        )

    # Fetch all score snapshots ordered by scored_at ascending
    result = await session.execute(
        select(ScoreSnapshot)
        .where(ScoreSnapshot.company_id == company_id)
        .order_by(ScoreSnapshot.scored_at.asc())
    )
    snapshots = result.scalars().all()

    history = [
        ScoreHistoryItem(
            overall_score=float(s.overall_score) if s.overall_score is not None else None,
            financial_health=float(s.financial_health) if s.financial_health is not None else None,
            business_risk=float(s.business_risk) if s.business_risk is not None else None,
            growth_potential=float(s.growth_potential) if s.growth_potential is not None else None,
            product_fit=float(s.product_fit) if s.product_fit is not None else None,
            relationship_accessibility=(
                float(s.relationship_accessibility)
                if s.relationship_accessibility is not None
                else None
            ),
            scored_at=s.scored_at,
        )
        for s in snapshots
    ]

    return ScoreHistoryResponse(
        company_id=company.id,
        company_name=company.name,
        history=history,
    )


@router.get(
    "/workspaces/{workspace_id}/analytics",
    response_model=WorkspaceAnalyticsResponse,
)
async def get_workspace_analytics(
    workspace_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> WorkspaceAnalyticsResponse:
    """Return workspace analytics: company scores for comparison charts and leaderboard.

    Requires workspace ownership. Returns all workspace company scores
    for grouped bar/radar chart rendering, plus a leaderboard sorted by
    overall_score descending.
    """
    # Verify workspace exists and is owned by current user
    result = await session.execute(
        select(Workspace).where(
            Workspace.id == workspace_id,
            Workspace.user_id == current_user.id,
        )
    )
    workspace = result.scalar_one_or_none()
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )

    # Fetch all companies in the workspace
    result = await session.execute(
        select(CompanyProfile)
        .join(
            WorkspaceCompany,
            CompanyProfile.id == WorkspaceCompany.company_id,
        )
        .where(WorkspaceCompany.workspace_id == workspace_id)
        .order_by(CompanyProfile.name.asc())
    )
    companies = result.scalars().all()

    # Build company scores list
    company_scores = [
        CompanyScores(
            id=c.id,
            name=c.name,
            overall_score=float(c.overall_score) if c.overall_score is not None else None,
            financial_health=float(c.financial_health) if c.financial_health is not None else None,
            business_risk=float(c.business_risk) if c.business_risk is not None else None,
            growth_potential=float(c.growth_potential) if c.growth_potential is not None else None,
            product_fit=float(c.product_fit) if c.product_fit is not None else None,
            relationship_accessibility=(
                float(c.relationship_accessibility)
                if c.relationship_accessibility is not None
                else None
            ),
        )
        for c in companies
    ]

    # Build leaderboard sorted by overall_score descending
    # Companies without scores go to the end
    sorted_companies = sorted(
        companies,
        key=lambda c: float(c.overall_score) if c.overall_score is not None else -1.0,
        reverse=True,
    )

    leaderboard = [
        LeaderboardEntry(
            rank=idx + 1,
            id=c.id,
            name=c.name,
            overall_score=float(c.overall_score) if c.overall_score is not None else None,
        )
        for idx, c in enumerate(sorted_companies)
    ]

    return WorkspaceAnalyticsResponse(
        workspace_id=workspace_id,
        companies=company_scores,
        leaderboard=leaderboard,
    )
