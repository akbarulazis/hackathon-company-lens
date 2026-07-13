"""Tests for ARQ worker infrastructure: settings and job registry."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.jobs.settings import (
    DEFAULT_JOB_TIMEOUT,
    JOB_TIMEOUTS,
    MAX_RETRIES,
    RETRY_DELAY_SECONDS,
    get_job_timeout,
)
from app.jobs.registry import (
    DEDUP_KEY_PREFIX,
    DEDUP_KEY_TTL_SECONDS,
    VALID_JOB_TYPES,
    JobStatus,
    _dedup_key,
    enqueue_job,
    is_job_pending_or_running,
    mark_job_completed,
    mark_job_failed,
    mark_job_pending,
    mark_job_running,
)


class TestJobTimeouts:
    """Test job timeout configuration."""

    def test_run_research_timeout_is_300s(self):
        assert get_job_timeout("run_research") == 300

    def test_score_profile_timeout_is_120s(self):
        assert get_job_timeout("score_profile") == 120

    def test_run_comparison_timeout_is_120s(self):
        assert get_job_timeout("run_comparison") == 120

    def test_process_document_timeout_is_120s(self):
        assert get_job_timeout("process_document") == 120

    def test_ingest_embeddings_timeout_is_120s(self):
        assert get_job_timeout("ingest_embeddings") == 120

    def test_unknown_job_type_returns_default_timeout(self):
        assert get_job_timeout("unknown_job") == DEFAULT_JOB_TIMEOUT

    def test_default_timeout_is_120s(self):
        assert DEFAULT_JOB_TIMEOUT == 120


class TestRetryConfig:
    """Test retry configuration."""

    def test_max_retries_is_2(self):
        assert MAX_RETRIES == 2

    def test_retry_delay_is_10s(self):
        assert RETRY_DELAY_SECONDS == 10


class TestValidJobTypes:
    """Test valid job type registry."""

    def test_all_expected_job_types_registered(self):
        expected = {
            "run_research",
            "refresh_research",
            "score_profile",
            "run_comparison",
            "process_document",
            "ingest_embeddings",
        }
        assert VALID_JOB_TYPES == expected


class TestDedupKey:
    """Test deduplication key generation."""

    def test_dedup_key_format(self):
        key = _dedup_key("run_research", "123")
        assert key == f"{DEDUP_KEY_PREFIX}run_research:123"

    def test_dedup_key_with_int_resource_id(self):
        key = _dedup_key("score_profile", 456)
        assert key == f"{DEDUP_KEY_PREFIX}score_profile:456"

    def test_dedup_key_with_string_resource_id(self):
        key = _dedup_key("run_comparison", "abc-def")
        assert key == f"{DEDUP_KEY_PREFIX}run_comparison:abc-def"


class TestIsPendingOrRunning:
    """Test deduplication check logic."""

    @pytest.fixture
    def mock_redis(self):
        return AsyncMock()

    async def test_returns_true_when_pending(self, mock_redis):
        mock_redis.get.return_value = JobStatus.PENDING.value
        result = await is_job_pending_or_running(mock_redis, "run_research", "123")
        assert result is True

    async def test_returns_true_when_running(self, mock_redis):
        mock_redis.get.return_value = JobStatus.RUNNING.value
        result = await is_job_pending_or_running(mock_redis, "run_research", "123")
        assert result is True

    async def test_returns_false_when_no_key(self, mock_redis):
        mock_redis.get.return_value = None
        result = await is_job_pending_or_running(mock_redis, "run_research", "123")
        assert result is False

    async def test_returns_false_when_completed(self, mock_redis):
        mock_redis.get.return_value = JobStatus.COMPLETED.value
        result = await is_job_pending_or_running(mock_redis, "run_research", "123")
        assert result is False

    async def test_returns_false_when_failed(self, mock_redis):
        mock_redis.get.return_value = JobStatus.FAILED.value
        result = await is_job_pending_or_running(mock_redis, "run_research", "123")
        assert result is False


class TestMarkJobStatus:
    """Test job status marking operations."""

    @pytest.fixture
    def mock_redis(self):
        return AsyncMock()

    async def test_mark_pending_sets_key_with_ttl(self, mock_redis):
        await mark_job_pending(mock_redis, "run_research", "123")
        expected_key = _dedup_key("run_research", "123")
        mock_redis.set.assert_called_once_with(
            expected_key, JobStatus.PENDING.value, ex=DEDUP_KEY_TTL_SECONDS
        )

    async def test_mark_running_sets_key_with_ttl(self, mock_redis):
        await mark_job_running(mock_redis, "run_research", "123")
        expected_key = _dedup_key("run_research", "123")
        mock_redis.set.assert_called_once_with(
            expected_key, JobStatus.RUNNING.value, ex=DEDUP_KEY_TTL_SECONDS
        )

    async def test_mark_completed_deletes_key(self, mock_redis):
        await mark_job_completed(mock_redis, "run_research", "123")
        expected_key = _dedup_key("run_research", "123")
        mock_redis.delete.assert_called_once_with(expected_key)

    async def test_mark_failed_deletes_key(self, mock_redis):
        await mark_job_failed(mock_redis, "run_research", "123")
        expected_key = _dedup_key("run_research", "123")
        mock_redis.delete.assert_called_once_with(expected_key)


class TestEnqueueJob:
    """Test job enqueue with deduplication."""

    @pytest.fixture
    def mock_redis(self):
        redis = AsyncMock()
        redis.get.return_value = None  # No existing job by default
        return redis

    @pytest.fixture
    def mock_arq_redis(self):
        arq = AsyncMock()
        job = MagicMock()
        job.job_id = "test-job-id-123"
        arq.enqueue_job.return_value = job
        return arq

    async def test_enqueues_job_successfully(self, mock_arq_redis, mock_redis):
        job_id = await enqueue_job(mock_arq_redis, mock_redis, "run_research", "42")
        assert job_id == "test-job-id-123"
        mock_arq_redis.enqueue_job.assert_called_once_with(
            "run_research",
            resource_id="42",
            _job_timeout=300,
            _max_retries=2,
            _retry_delay=10,
        )

    async def test_discards_duplicate_pending_job(self, mock_arq_redis, mock_redis):
        mock_redis.get.return_value = JobStatus.PENDING.value
        job_id = await enqueue_job(mock_arq_redis, mock_redis, "run_research", "42")
        assert job_id is None
        mock_arq_redis.enqueue_job.assert_not_called()

    async def test_discards_duplicate_running_job(self, mock_arq_redis, mock_redis):
        mock_redis.get.return_value = JobStatus.RUNNING.value
        job_id = await enqueue_job(mock_arq_redis, mock_redis, "run_research", "42")
        assert job_id is None
        mock_arq_redis.enqueue_job.assert_not_called()

    async def test_allows_enqueue_after_completion(self, mock_arq_redis, mock_redis):
        mock_redis.get.return_value = JobStatus.COMPLETED.value
        job_id = await enqueue_job(mock_arq_redis, mock_redis, "run_research", "42")
        assert job_id == "test-job-id-123"

    async def test_allows_enqueue_after_failure(self, mock_arq_redis, mock_redis):
        mock_redis.get.return_value = JobStatus.FAILED.value
        job_id = await enqueue_job(mock_arq_redis, mock_redis, "run_research", "42")
        assert job_id == "test-job-id-123"

    async def test_raises_for_invalid_job_type(self, mock_arq_redis, mock_redis):
        with pytest.raises(ValueError, match="Invalid job type"):
            await enqueue_job(mock_arq_redis, mock_redis, "invalid_job", "42")

    async def test_marks_pending_before_enqueue(self, mock_arq_redis, mock_redis):
        await enqueue_job(mock_arq_redis, mock_redis, "score_profile", "99")
        expected_key = _dedup_key("score_profile", "99")
        # Verify set was called with pending status
        mock_redis.set.assert_called_once_with(
            expected_key, JobStatus.PENDING.value, ex=DEDUP_KEY_TTL_SECONDS
        )

    async def test_uses_correct_timeout_per_job_type(self, mock_arq_redis, mock_redis):
        await enqueue_job(mock_arq_redis, mock_redis, "process_document", "7")
        mock_arq_redis.enqueue_job.assert_called_once_with(
            "process_document",
            resource_id="7",
            _job_timeout=120,
            _max_retries=2,
            _retry_delay=10,
        )

    async def test_passes_additional_kwargs(self, mock_arq_redis, mock_redis):
        await enqueue_job(
            mock_arq_redis, mock_redis, "run_research", "5", user_id=10, workspace_id=3
        )
        mock_arq_redis.enqueue_job.assert_called_once_with(
            "run_research",
            resource_id="5",
            _job_timeout=300,
            _max_retries=2,
            _retry_delay=10,
            user_id=10,
            workspace_id=3,
        )

    async def test_handles_arq_returning_none(self, mock_arq_redis, mock_redis):
        mock_arq_redis.enqueue_job.return_value = None
        job_id = await enqueue_job(mock_arq_redis, mock_redis, "run_research", "42")
        assert job_id is None
        # Should clean up the dedup key
        expected_key = _dedup_key("run_research", "42")
        mock_redis.delete.assert_called_once_with(expected_key)
