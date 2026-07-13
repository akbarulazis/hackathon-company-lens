"""ARQ job functions for company research.

Defines `run_research` and `refresh_research` job functions that are
executed by the ARQ worker. Both call the research pipeline orchestrator
and handle lifecycle events (status transitions, error handling, dedup).

Timeout: 300s, max 2 attempts (configured in jobs/settings.py).
"""

import logging

# Ensure all models are loaded for SQLAlchemy relationship resolution
import app.models  # noqa: F401

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.companies.models import ClientStatus, CompanyProfile, CompanyStatus
from app.companies.repository import get_company_by_id
from app.config import get_settings
from app.database import create_session_factory
from app.documents.models import TextChunk
from app.jobs.registry import mark_job_completed, mark_job_failed, mark_job_running
from app.research.pipeline import run_pipeline

logger = logging.getLogger(__name__)


async def validate_refresh_preconditions(
    session: AsyncSession, company_id: int
) -> bool:
    """Check if a company is eligible for research refresh.

    A company can be refreshed only if:
    - Client_Status == "Prospect"
    - status == "ready"

    Used by the worker and by the companies router to gate refresh requests.

    Args:
        session: Async database session.
        company_id: ID of the company to check.

    Returns:
        True if the company meets refresh preconditions, False otherwise.
    """
    company = await get_company_by_id(session, company_id)
    if company is None:
        return False

    return (
        company.client_status == ClientStatus.prospect
        and company.status == CompanyStatus.ready
    )


async def run_research(ctx: dict, company_id: int, user_id: int) -> None:
    """ARQ job function: execute the full research pipeline for a company.

    Creates an async database session, loads settings, and delegates to
    `run_pipeline`. On unhandled failure, sets the company status to "failed".

    Args:
        ctx: ARQ worker context dict (contains redis connection).
        company_id: ID of the company to research.
        user_id: ID of the user who initiated research.
    """
    redis = ctx.get("redis")
    job_type = "run_research"

    logger.info("Starting run_research job: company_id=%d, user_id=%d", company_id, user_id)

    # Mark job as running in dedup registry
    if redis:
        await mark_job_running(redis, job_type, str(company_id))

    settings = get_settings()
    session_factory = create_session_factory(settings)

    async with session_factory() as session:
        try:
            await run_pipeline(company_id, user_id, session, settings)

            # Mark job completed in dedup registry
            if redis:
                await mark_job_completed(redis, job_type, str(company_id))

            logger.info("run_research completed: company_id=%d", company_id)

        except Exception as e:
            logger.exception(
                "run_research failed: company_id=%d, error=%s", company_id, e
            )

            # Set company status to failed
            try:
                company = await get_company_by_id(session, company_id)
                if company:
                    company.status = CompanyStatus.failed
                    await session.commit()
            except Exception:
                logger.exception(
                    "Failed to set company status to failed: company_id=%d",
                    company_id,
                )

            # Mark job failed in dedup registry
            if redis:
                await mark_job_failed(redis, job_type, str(company_id))

            raise


async def refresh_research(ctx: dict, company_id: int, user_id: int) -> None:
    """ARQ job function: re-execute research for an existing prospect.

    Preconditions (validated before enqueue, re-validated here):
    - Client_Status == "Prospect"
    - status == "ready"

    On refresh:
    1. Transition status to "researching" (preserves existing data)
    2. Run the full pipeline (which atomically replaces data on success)
    3. On success: delete previous text chunks and regenerate embeddings
    4. Stream progress events via WebSocket (handled by pipeline)

    Args:
        ctx: ARQ worker context dict (contains redis connection).
        company_id: ID of the company to refresh.
        user_id: ID of the user who initiated refresh.
    """
    redis = ctx.get("redis")
    job_type = "refresh_research"  # Dedup key for refresh operations

    logger.info(
        "Starting refresh_research job: company_id=%d, user_id=%d",
        company_id,
        user_id,
    )

    # Mark job as running in dedup registry
    if redis:
        await mark_job_running(redis, job_type, str(company_id))

    settings = get_settings()
    session_factory = create_session_factory(settings)

    async with session_factory() as session:
        try:
            # Re-validate preconditions (defensive check)
            company = await get_company_by_id(session, company_id)
            if company is None:
                raise ValueError(f"Company not found: id={company_id}")

            if (
                company.client_status != ClientStatus.prospect
                or company.status != CompanyStatus.ready
            ):
                raise ValueError(
                    f"Company id={company_id} not eligible for refresh: "
                    f"client_status={company.client_status.value}, "
                    f"status={company.status.value}. "
                    f"Requires client_status='prospect' AND status='ready'."
                )

            # Delete previous research text chunks before pipeline re-run
            # (embeddings will be regenerated by the pipeline or post-processing)
            await session.execute(
                delete(TextChunk).where(
                    TextChunk.company_id == company_id,
                    TextChunk.source_type == "research",
                )
            )
            await session.flush()

            # Run the full pipeline — handles status transitions, data replacement,
            # and WebSocket progress events internally
            await run_pipeline(company_id, user_id, session, settings)

            # Mark job completed in dedup registry
            if redis:
                await mark_job_completed(redis, job_type, str(company_id))

            logger.info("refresh_research completed: company_id=%d", company_id)

        except Exception as e:
            logger.exception(
                "refresh_research failed: company_id=%d, error=%s", company_id, e
            )

            # Set company status to failed (but preserve existing data)
            try:
                company = await get_company_by_id(session, company_id)
                if company:
                    company.status = CompanyStatus.failed
                    await session.commit()
            except Exception:
                logger.exception(
                    "Failed to set company status to failed: company_id=%d",
                    company_id,
                )

            # Mark job failed in dedup registry
            if redis:
                await mark_job_failed(redis, job_type, str(company_id))

            raise
