"""ARQ job function for company comparison.

Defines `run_comparison` job function that is executed by the ARQ worker.
Calls the comparison service to generate an LLM-powered (or fallback)
comparison report, then pushes a WebSocket event on completion.

Timeout: 120s, max 2 attempts (configured in jobs/settings.py).
"""

import logging

from app.comparison.service import execute_comparison
from app.config import get_settings
from app.database import create_session_factory
from app.jobs.registry import mark_job_completed, mark_job_failed, mark_job_running
from app.notifications.events import ComparisonResultEvent
from app.notifications.manager import get_notification_manager

logger = logging.getLogger(__name__)


async def run_comparison(
    ctx: dict, report_id: int, workspace_id: int, user_id: int
) -> None:
    """ARQ job function: execute a company comparison and push result event.

    Creates an async database session, invokes execute_comparison to generate
    the LLM comparison (with fallback), and pushes a WebSocket event on
    completion.

    Args:
        ctx: ARQ worker context dict (contains redis connection).
        report_id: ID of the ComparisonReport to populate.
        workspace_id: ID of the workspace (for the result event).
        user_id: ID of the user who initiated the comparison.
    """
    redis = ctx.get("redis")
    job_type = "run_comparison"
    resource_id = str(report_id)

    logger.info(
        "Starting run_comparison job: report_id=%d, workspace_id=%d, user_id=%d",
        report_id,
        workspace_id,
        user_id,
    )

    # Mark job as running in dedup registry
    if redis:
        await mark_job_running(redis, job_type, resource_id)

    settings = get_settings()
    session_factory = create_session_factory(settings)

    async with session_factory() as session:
        try:
            # Execute the comparison (handles LLM call + fallback internally)
            report = await execute_comparison(session, report_id, settings)
            await session.commit()

            # Push WebSocket event to notify user
            try:
                manager = get_notification_manager()
                event = ComparisonResultEvent(
                    workspace_id=workspace_id,
                    report_id=report.id,
                )
                await manager.publish(user_id, event)
            except Exception as ws_err:
                # WebSocket failure should not fail the job
                logger.warning(
                    "Failed to push comparison result event: report_id=%d, error=%s",
                    report_id,
                    ws_err,
                )

            # Mark job completed in dedup registry
            if redis:
                await mark_job_completed(redis, job_type, resource_id)

            logger.info(
                "run_comparison completed: report_id=%d, is_fallback=%s",
                report_id,
                report.is_fallback,
            )

        except Exception as e:
            logger.exception(
                "run_comparison failed: report_id=%d, error=%s", report_id, e
            )

            # Mark job failed in dedup registry
            if redis:
                await mark_job_failed(redis, job_type, resource_id)

            raise
