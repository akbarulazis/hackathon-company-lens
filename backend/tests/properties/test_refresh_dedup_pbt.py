"""Property-based tests for research refresh and job deduplication.

# Feature: company-lens-rebuild
# Property 38: Job Deduplication
# Property 39: Research Refresh Precondition Enforcement

Validates: Requirements 16.6, 19.2
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.companies.models import ClientStatus, CompanyStatus
from app.jobs.registry import (
    VALID_JOB_TYPES,
    _dedup_key,
    enqueue_job,
    is_job_pending_or_running,
    mark_job_pending,
)
from app.research.worker import validate_refresh_preconditions


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Job types drawn from the valid set
job_type_strategy = st.sampled_from(sorted(VALID_JOB_TYPES))

# Resource identifiers: integers or string representations
resource_id_int_strategy = st.integers(min_value=1, max_value=1_000_000)
resource_id_str_strategy = st.from_regex(r"[a-z0-9_-]{1,50}", fullmatch=True)
resource_id_strategy = st.one_of(resource_id_int_strategy, resource_id_str_strategy)

# Client status enum values
client_status_strategy = st.sampled_from(list(ClientStatus))

# Company status enum values
company_status_strategy = st.sampled_from(list(CompanyStatus))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_mock_redis(existing_status: str | None = None):
    """Create a mock Redis client that simulates dedup key lookup.

    Args:
        existing_status: If provided, the mock redis.get() returns this value
                        (simulating an existing dedup key). None means no key exists.
    """
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=existing_status)
    redis.set = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    return redis


def make_mock_company(client_status: ClientStatus, status: CompanyStatus):
    """Create a mock CompanyProfile with given status fields."""
    company = MagicMock()
    company.id = 1
    company.name = "Test Company"
    company.client_status = client_status
    company.status = status
    return company


# ===========================================================================
# Property 38: Job Deduplication
# **Validates: Requirements 16.6**
#
# For any job_type and resource_id, if an identical job (same type and same
# resource identifier) is already pending or running, the duplicate enqueue
# SHALL be discarded without creating a second job.
# ===========================================================================


@given(job_type=job_type_strategy, resource_id=resource_id_strategy)
@settings(max_examples=100)
async def test_property38_pending_job_duplicate_discarded(
    job_type: str, resource_id: str | int
) -> None:
    """When a job is already pending, enqueue_job returns None (discarded).

    # Feature: company-lens-rebuild, Property 38: Job Deduplication
    """
    # Redis returns "pending" for the dedup key → duplicate exists
    redis = make_mock_redis(existing_status="pending")
    arq_redis = AsyncMock()

    result = await enqueue_job(arq_redis, redis, job_type, resource_id)

    # Duplicate should be discarded
    assert result is None
    # ARQ should never be called (job not enqueued)
    arq_redis.enqueue_job.assert_not_called()


@given(job_type=job_type_strategy, resource_id=resource_id_strategy)
@settings(max_examples=100)
async def test_property38_running_job_duplicate_discarded(
    job_type: str, resource_id: str | int
) -> None:
    """When a job is already running, enqueue_job returns None (discarded).

    # Feature: company-lens-rebuild, Property 38: Job Deduplication
    """
    # Redis returns "running" for the dedup key → duplicate exists
    redis = make_mock_redis(existing_status="running")
    arq_redis = AsyncMock()

    result = await enqueue_job(arq_redis, redis, job_type, resource_id)

    # Duplicate should be discarded
    assert result is None
    # ARQ should never be called (job not enqueued)
    arq_redis.enqueue_job.assert_not_called()


@given(job_type=job_type_strategy, resource_id=resource_id_strategy)
@settings(max_examples=100)
async def test_property38_no_existing_job_enqueued_successfully(
    job_type: str, resource_id: str | int
) -> None:
    """When no pending/running job exists, enqueue_job proceeds and returns job ID.

    # Feature: company-lens-rebuild, Property 38: Job Deduplication
    """
    # Redis returns None → no existing dedup key
    redis = make_mock_redis(existing_status=None)

    # Mock ARQ to return a job object with an ID
    mock_job = MagicMock()
    mock_job.job_id = "test-job-123"
    arq_redis = AsyncMock()
    arq_redis.enqueue_job = AsyncMock(return_value=mock_job)

    result = await enqueue_job(arq_redis, redis, job_type, resource_id)

    # Job should be enqueued successfully
    assert result == "test-job-123"
    # ARQ enqueue_job should have been called
    arq_redis.enqueue_job.assert_called_once()


@given(job_type=job_type_strategy, resource_id=resource_id_strategy)
@settings(max_examples=100)
async def test_property38_is_job_pending_or_running_detects_pending(
    job_type: str, resource_id: str | int
) -> None:
    """is_job_pending_or_running returns True when status is 'pending'.

    # Feature: company-lens-rebuild, Property 38: Job Deduplication
    """
    redis = make_mock_redis(existing_status="pending")

    result = await is_job_pending_or_running(redis, job_type, resource_id)
    assert result is True


@given(job_type=job_type_strategy, resource_id=resource_id_strategy)
@settings(max_examples=100)
async def test_property38_is_job_pending_or_running_detects_running(
    job_type: str, resource_id: str | int
) -> None:
    """is_job_pending_or_running returns True when status is 'running'.

    # Feature: company-lens-rebuild, Property 38: Job Deduplication
    """
    redis = make_mock_redis(existing_status="running")

    result = await is_job_pending_or_running(redis, job_type, resource_id)
    assert result is True


@given(job_type=job_type_strategy, resource_id=resource_id_strategy)
@settings(max_examples=100)
async def test_property38_is_job_pending_or_running_false_when_none(
    job_type: str, resource_id: str | int
) -> None:
    """is_job_pending_or_running returns False when no dedup key exists.

    # Feature: company-lens-rebuild, Property 38: Job Deduplication
    """
    redis = make_mock_redis(existing_status=None)

    result = await is_job_pending_or_running(redis, job_type, resource_id)
    assert result is False


# ===========================================================================
# Property 39: Research Refresh Precondition Enforcement
# **Validates: Requirements 19.2**
#
# For any Company_Profile, a refresh request SHALL be accepted if and only if
# the profile has Client_Status "Prospect" AND status "ready". All other
# combinations SHALL be rejected.
# ===========================================================================


@given(data=st.data())
@settings(max_examples=100)
async def test_property39_valid_precondition_accepted(data: st.DataObject) -> None:
    """Refresh is accepted when Client_Status='prospect' AND status='ready'.

    # Feature: company-lens-rebuild, Property 39: Research Refresh Precondition Enforcement
    """
    company_id = data.draw(st.integers(min_value=1, max_value=100_000))

    # Create a company with the exact valid combination
    company = make_mock_company(
        client_status=ClientStatus.prospect,
        status=CompanyStatus.ready,
    )

    mock_session = AsyncMock()

    with patch(
        "app.research.worker.get_company_by_id",
        new=AsyncMock(return_value=company),
    ):
        result = await validate_refresh_preconditions(mock_session, company_id)

    assert result is True


@given(
    client_status=client_status_strategy,
    company_status=company_status_strategy,
)
@settings(max_examples=100)
async def test_property39_invalid_combinations_rejected(
    client_status: ClientStatus,
    company_status: CompanyStatus,
) -> None:
    """Refresh is rejected for any combination other than prospect+ready.

    # Feature: company-lens-rebuild, Property 39: Research Refresh Precondition Enforcement
    """
    # Skip the single valid combination
    if client_status == ClientStatus.prospect and company_status == CompanyStatus.ready:
        return

    company = make_mock_company(
        client_status=client_status,
        status=company_status,
    )

    mock_session = AsyncMock()

    with patch(
        "app.research.worker.get_company_by_id",
        new=AsyncMock(return_value=company),
    ):
        result = await validate_refresh_preconditions(mock_session, 1)

    assert result is False


@given(company_id=st.integers(min_value=1, max_value=100_000))
@settings(max_examples=100)
async def test_property39_nonexistent_company_rejected(company_id: int) -> None:
    """Refresh is rejected when company does not exist (returns None).

    # Feature: company-lens-rebuild, Property 39: Research Refresh Precondition Enforcement
    """
    mock_session = AsyncMock()

    with patch(
        "app.research.worker.get_company_by_id",
        new=AsyncMock(return_value=None),
    ):
        result = await validate_refresh_preconditions(mock_session, company_id)

    assert result is False


@given(
    client_status=st.sampled_from(
        [cs for cs in ClientStatus if cs != ClientStatus.prospect]
    ),
    company_status=st.just(CompanyStatus.ready),
)
@settings(max_examples=100)
async def test_property39_wrong_client_status_rejected(
    client_status: ClientStatus,
    company_status: CompanyStatus,
) -> None:
    """Refresh rejected when status='ready' but Client_Status != 'prospect'.

    # Feature: company-lens-rebuild, Property 39: Research Refresh Precondition Enforcement
    """
    company = make_mock_company(
        client_status=client_status,
        status=company_status,
    )

    mock_session = AsyncMock()

    with patch(
        "app.research.worker.get_company_by_id",
        new=AsyncMock(return_value=company),
    ):
        result = await validate_refresh_preconditions(mock_session, 1)

    assert result is False


@given(
    client_status=st.just(ClientStatus.prospect),
    company_status=st.sampled_from(
        [cs for cs in CompanyStatus if cs != CompanyStatus.ready]
    ),
)
@settings(max_examples=100)
async def test_property39_wrong_company_status_rejected(
    client_status: ClientStatus,
    company_status: CompanyStatus,
) -> None:
    """Refresh rejected when Client_Status='prospect' but status != 'ready'.

    # Feature: company-lens-rebuild, Property 39: Research Refresh Precondition Enforcement
    """
    company = make_mock_company(
        client_status=client_status,
        status=company_status,
    )

    mock_session = AsyncMock()

    with patch(
        "app.research.worker.get_company_by_id",
        new=AsyncMock(return_value=company),
    ):
        result = await validate_refresh_preconditions(mock_session, 1)

    assert result is False
