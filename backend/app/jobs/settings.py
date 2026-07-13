"""ARQ worker settings and configuration.

Startable via: arq app.jobs.settings.WorkerSettings
"""

from __future__ import annotations

from arq.connections import RedisSettings

# Job timeout configuration (in seconds)
JOB_TIMEOUTS: dict[str, int] = {
    "run_research": 300,
    "refresh_research": 300,
    "score_profile": 120,
    "run_comparison": 120,
    "process_document": 120,
    "ingest_embeddings": 120,
}

# Default timeout for any unregistered job type
DEFAULT_JOB_TIMEOUT: int = 120

# Retry configuration
MAX_RETRIES: int = 2
RETRY_DELAY_SECONDS: int = 10


def get_redis_settings() -> RedisSettings:
    """Parse REDIS_URL into ARQ RedisSettings.

    Called lazily at worker startup, not at import time.
    """
    from app.config import get_settings

    settings = get_settings()
    return RedisSettings.from_dsn(settings.REDIS_URL)


def get_job_timeout(job_type: str) -> int:
    """Return the configured timeout in seconds for a given job type."""
    return JOB_TIMEOUTS.get(job_type, DEFAULT_JOB_TIMEOUT)


def get_worker_functions() -> list:
    """Import and return all registered ARQ job functions.

    Uses lazy imports to avoid requiring environment variables at
    module import time (important for tests and CLI tools). Each
    function is wrapped with `arq.worker.func()` to apply its
    per-job-type timeout and retry configuration.
    """
    from arq.worker import func

    from app.comparison.worker import run_comparison
    from app.documents.worker import process_document
    from app.research.worker import refresh_research, run_research

    return [
        func(run_research, timeout=get_job_timeout("run_research"), max_tries=MAX_RETRIES + 1),
        func(refresh_research, timeout=get_job_timeout("refresh_research"), max_tries=MAX_RETRIES + 1),
        func(run_comparison, timeout=get_job_timeout("run_comparison"), max_tries=MAX_RETRIES + 1),
        func(process_document, timeout=get_job_timeout("process_document"), max_tries=MAX_RETRIES + 1),
    ]


async def on_startup(ctx: dict) -> None:
    """Worker startup hook — initialize shared resources."""
    from redis.asyncio import Redis

    from app.config import get_settings

    # Ensure all models are imported so SQLAlchemy resolves relationships
    import app.models  # noqa: F401

    settings = get_settings()
    ctx["redis"] = Redis.from_url(settings.REDIS_URL, decode_responses=True)


async def on_shutdown(ctx: dict) -> None:
    """Worker shutdown hook — clean up shared resources."""
    redis = ctx.get("redis")
    if redis:
        await redis.aclose()


class WorkerSettings:
    """ARQ WorkerSettings class.

    Start the worker with: arq app.jobs.settings.WorkerSettings
    """

    redis_settings = get_redis_settings()

    on_startup = on_startup
    on_shutdown = on_shutdown

    max_jobs = 10
    job_timeout = DEFAULT_JOB_TIMEOUT
    retry_jobs = True

    @classmethod
    def create_worker(cls):
        """Called by arq CLI to get functions — avoids circular imports."""
        cls.functions = get_worker_functions()
        return cls


# Set functions after all imports are resolved by arq CLI
# arq loads this module, then reads WorkerSettings.functions
# We defer the import to avoid circular dependency
try:
    WorkerSettings.functions = get_worker_functions()
except ImportError:
    # During tests or partial imports, functions can be empty
    WorkerSettings.functions = []
