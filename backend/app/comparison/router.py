"""Comparison API router.

Provides REST endpoints for initiating company comparisons and
retrieving comparison reports. All endpoints require authentication
via JWT bearer token and workspace ownership verification.
"""

from arq import ArqRedis
from fastapi import APIRouter, Depends, HTTPException, status
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.comparison.schemas import (
    CompareRequest,
    ComparisonReportResponse,
)
from app.comparison.service import ComparisonError, initiate
from app.dependencies import get_db, get_redis
from app.jobs.registry import enqueue_job
from app.workspaces.models import ComparisonReport, Workspace

router = APIRouter(prefix="/api/workspaces", tags=["comparison"])


@router.post(
    "/{workspace_id}/compare",
    response_model=ComparisonReportResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def initiate_comparison(
    workspace_id: int,
    data: CompareRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> ComparisonReportResponse:
    """Initiate a comparison for 2-3 companies in a workspace.

    Validates preconditions via the comparison service, creates a pending
    comparison report, then enqueues the run_comparison ARQ job.

    Returns:
        The created comparison report (with html_content=None initially).

    Raises:
        HTTPException(422): If company count is not 2 or 3.
        HTTPException(404): If workspace not found or not owned by user.
        HTTPException(409): If any company does not have status "ready".
    """
    try:
        report = await initiate(
            session=session,
            workspace_id=workspace_id,
            company_ids=data.company_ids,
            user_id=current_user.id,
        )
        await session.commit()
    except ComparisonError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

    # Enqueue the comparison background job
    arq_redis = ArqRedis(pool_or_conn=redis.connection_pool)
    job_id = await enqueue_job(
        arq_redis=arq_redis,
        redis=redis,
        job_type="run_comparison",
        resource_id=str(report.id),
        report_id=report.id,
        workspace_id=workspace_id,
        user_id=current_user.id,
    )

    if job_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A comparison job is already in progress for this report.",
        )

    return ComparisonReportResponse.model_validate(report)


@router.get(
    "/{workspace_id}/reports/{report_id}",
    response_model=ComparisonReportResponse,
)
async def get_comparison_report(
    workspace_id: int,
    report_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ComparisonReportResponse:
    """Get a comparison report by ID.

    Verifies workspace ownership before returning the report.
    Returns 404 if the workspace is not owned by the user or
    the report does not exist within the workspace.

    Returns:
        The comparison report with HTML content (if completed).

    Raises:
        HTTPException(404): If workspace not owned or report not found.
    """
    # Verify workspace ownership
    result = await session.execute(
        select(Workspace).where(
            Workspace.id == workspace_id,
            Workspace.user_id == current_user.id,
        )
    )
    workspace = result.scalar_one_or_none()
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )

    # Fetch the report scoped to this workspace
    result = await session.execute(
        select(ComparisonReport).where(
            ComparisonReport.id == report_id,
            ComparisonReport.workspace_id == workspace_id,
        )
    )
    report = result.scalar_one_or_none()
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comparison report not found",
        )

    return ComparisonReportResponse.model_validate(report)
