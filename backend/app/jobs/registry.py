"""Job type registry with deduplication logic.

Deduplication key pattern: "{job_type}:{resource_id}"
If a key exists in Redis with pending/running state, the new enqueue is discarded.
"""

import logging
from enum import Enum
from typing import Any

from arq import ArqRedis
from redis.asyncio import Redis

from app.jobs.settings import MAX_RETRIES, RETRY_DELAY_SECONDS, get_job_timeout

logger = logging.getLogger(__name__)

# Redis key prefix for job deduplication tracking
DEDUP_KEY_PREFIX = "job:dedup:"

# TTL for dedup keys — set to slightly longer than max job timeout + retry delays
# to ensure cleanup even if a job doesn't finish cleanly.
DEDUP_KEY_TTL_SECONDS = 600  # 10 minutes


class JobStatus(str, Enum):
    """Possible job states for deduplication tracking."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# Registered job types
VALID_JOB_TYPES: set[str] = {
    "run_research",
    "refresh_research",
    "score_profile",
    "run_comparison",
    "process_document",
    "ingest_embeddings",
}


def _dedup_key(job_type: str, resource_id: str | int) -> str:
    """Build the Redis deduplication key for a job."""
    return f"{DEDUP_KEY_PREFIX}{job_type}:{resource_id}"


async def is_job_pending_or_running(
    redis: Redis,
    job_type: str,
    resource_id: str | int,
) -> bool:
    """Check if an identical job is already pending or running.

    Returns True if a duplicate exists (enqueue should be discarded).
    """
    key = _dedup_key(job_type, resource_id)
    status = await redis.get(key)
    return status in (JobStatus.PENDING.value, JobStatus.RUNNING.value)


async def mark_job_pending(
    redis: Redis,
    job_type: str,
    resource_id: str | int,
) -> None:
    """Mark a job as pending in the dedup registry."""
    key = _dedup_key(job_type, resource_id)
    await redis.set(key, JobStatus.PENDING.value, ex=DEDUP_KEY_TTL_SECONDS)


async def mark_job_running(
    redis: Redis,
    job_type: str,
    resource_id: str | int,
) -> None:
    """Mark a job as running in the dedup registry."""
    key = _dedup_key(job_type, resource_id)
    await redis.set(key, JobStatus.RUNNING.value, ex=DEDUP_KEY_TTL_SECONDS)


async def mark_job_completed(
    redis: Redis,
    job_type: str,
    resource_id: str | int,
) -> None:
    """Mark a job as completed and remove the dedup key."""
    key = _dedup_key(job_type, resource_id)
    await redis.delete(key)


async def mark_job_failed(
    redis: Redis,
    job_type: str,
    resource_id: str | int,
) -> None:
    """Mark a job as failed and remove the dedup key to allow re-enqueue."""
    key = _dedup_key(job_type, resource_id)
    await redis.delete(key)


async def enqueue_job(
    arq_redis: ArqRedis,
    redis: Redis,
    job_type: str,
    resource_id: str | int,
    **kwargs: Any,
) -> str | None:
    """Enqueue a background job with deduplication.

    Returns the job ID if enqueued, or None if a duplicate was discarded.

    Args:
        arq_redis: ARQ Redis pool for enqueuing jobs.
        redis: Redis client for deduplication state.
        job_type: One of the VALID_JOB_TYPES.
        resource_id: Unique identifier for the resource being processed.
        **kwargs: Additional arguments passed to the job function.

    Raises:
        ValueError: If job_type is not a valid registered type.
    """
    if job_type not in VALID_JOB_TYPES:
        raise ValueError(
            f"Invalid job type '{job_type}'. Must be one of: {sorted(VALID_JOB_TYPES)}"
        )

    # Deduplication check
    if await is_job_pending_or_running(redis, job_type, resource_id):
        logger.info(
            "Discarding duplicate job enqueue: %s:%s (already pending/running)",
            job_type,
            resource_id,
        )
        return None

    # Mark as pending before enqueuing
    await mark_job_pending(redis, job_type, resource_id)

    # Enqueue the job. Timeout and retry behavior are configured on the
    # worker side (WorkerSettings.job_timeout / max_tries), since this
    # version of arq's enqueue_job() does not accept per-job overrides
    # for timeout/retries via kwargs.
    timeout = get_job_timeout(job_type)
    job = await arq_redis.enqueue_job(
        job_type,
        **kwargs,
    )

    if job is None:
        # ARQ returned None — job was not enqueued (e.g., ARQ-level dedup)
        await mark_job_failed(redis, job_type, resource_id)
        logger.warning("ARQ refused to enqueue job %s:%s", job_type, resource_id)
        return None

    logger.info(
        "Enqueued job %s:%s (id=%s, configured_timeout=%ds)",
        job_type,
        resource_id,
        job.job_id,
        timeout,
    )
    return job.job_id
