"""TDD tests for data_quality domain module.

Tests are written first (RED phase) and must fail before implementation.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from gpd.exp.contracts.data import QualityStatus
from gpd.exp.domain.data_quality import run_quality_checks

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(tz=UTC)


# ---------------------------------------------------------------------------
# Individual check: attention
# ---------------------------------------------------------------------------


class TestCheckAttention:
    """Tests for attention check behavior inside run_quality_checks."""

    def test_response_containing_4_passes(self) -> None:
        """Response containing '4' passes the attention check."""
        result = run_quality_checks(
            response_text="4",
            accepted_at=None,
            submitted_at=None,
            expected_duration_minutes=None,
            worker_id=None,
            existing_worker_ids=set(),
            value=None,
            expected_range=None,
        )
        assert result.passed is True
        assert result.status == QualityStatus.VALIDATED

    def test_response_containing_4_in_sentence_passes(self) -> None:
        """'The answer is 4.' passes the attention check."""
        result = run_quality_checks(
            response_text="The answer is 4.",
            accepted_at=None,
            submitted_at=None,
            expected_duration_minutes=None,
            worker_id=None,
            existing_worker_ids=set(),
            value=None,
            expected_range=None,
        )
        assert result.passed is True

    def test_response_without_4_fails(self) -> None:
        """Response 'I don't know' fails attention check with a reason string."""
        result = run_quality_checks(
            response_text="I don't know",
            accepted_at=None,
            submitted_at=None,
            expected_duration_minutes=None,
            worker_id=None,
            existing_worker_ids=set(),
            value=None,
            expected_range=None,
        )
        assert result.passed is False
        assert result.status == QualityStatus.REJECTED
        assert isinstance(result.failure_reason, str)
        assert len(result.failure_reason) > 0
        assert "attention" in result.checks_run


# ---------------------------------------------------------------------------
# Individual check: response_time
# ---------------------------------------------------------------------------


class TestCheckResponseTime:
    """Tests for response_time check behavior inside run_quality_checks."""

    def test_reasonable_time_passes(self) -> None:
        """accepted_at=T, submitted_at=T+20min, expected_duration=10min -> passes."""
        t = _now()
        result = run_quality_checks(
            response_text="4",
            accepted_at=t,
            submitted_at=t + timedelta(minutes=20),
            expected_duration_minutes=10,
            worker_id=None,
            existing_worker_ids=set(),
            value=None,
            expected_range=None,
        )
        assert result.passed is True

    def test_too_fast_fails(self) -> None:
        """Submitted after only 1 minute on a 10-minute task fails."""
        t = _now()
        result = run_quality_checks(
            response_text="4",
            accepted_at=t,
            submitted_at=t + timedelta(minutes=1),
            expected_duration_minutes=10,
            worker_id=None,
            existing_worker_ids=set(),
            value=None,
            expected_range=None,
        )
        assert result.passed is False
        assert result.status == QualityStatus.REJECTED
        assert "response_time" in result.checks_run

    def test_no_accepted_at_skips_check(self) -> None:
        """accepted_at=None skips response_time check (passes)."""
        result = run_quality_checks(
            response_text="4",
            accepted_at=None,
            submitted_at=_now(),
            expected_duration_minutes=10,
            worker_id=None,
            existing_worker_ids=set(),
            value=None,
            expected_range=None,
        )
        assert result.passed is True

    def test_no_expected_duration_skips_check(self) -> None:
        """expected_duration_minutes=None skips response_time check (passes)."""
        t = _now()
        result = run_quality_checks(
            response_text="4",
            accepted_at=t,
            submitted_at=t + timedelta(seconds=5),  # Very fast, but no duration hint
            expected_duration_minutes=None,
            worker_id=None,
            existing_worker_ids=set(),
            value=None,
            expected_range=None,
        )
        assert result.passed is True


# ---------------------------------------------------------------------------
# Individual check: duplicate_worker
# ---------------------------------------------------------------------------


class TestCheckNoDuplicateWorker:
    """Tests for duplicate_worker check behavior inside run_quality_checks."""

    def test_new_worker_passes(self) -> None:
        """worker_id not in existing_worker_ids passes."""
        result = run_quality_checks(
            response_text="4",
            accepted_at=None,
            submitted_at=None,
            expected_duration_minutes=None,
            worker_id="worker-001",
            existing_worker_ids={"worker-002", "worker-003"},
            value=None,
            expected_range=None,
        )
        assert result.passed is True

    def test_duplicate_worker_fails(self) -> None:
        """worker_id in existing_worker_ids fails with a reason."""
        result = run_quality_checks(
            response_text="4",
            accepted_at=None,
            submitted_at=None,
            expected_duration_minutes=None,
            worker_id="worker-001",
            existing_worker_ids={"worker-001"},
            value=None,
            expected_range=None,
        )
        assert result.passed is False
        assert result.status == QualityStatus.REJECTED
        assert isinstance(result.failure_reason, str)

    def test_none_worker_id_skips_check(self) -> None:
        """worker_id=None skips duplicate check (passes)."""
        result = run_quality_checks(
            response_text="4",
            accepted_at=None,
            submitted_at=None,
            expected_duration_minutes=None,
            worker_id=None,
            existing_worker_ids={"worker-001"},
            value=None,
            expected_range=None,
        )
        assert result.passed is True


# ---------------------------------------------------------------------------
# Individual check: measurement_range
# ---------------------------------------------------------------------------


class TestCheckMeasurementRange:
    """Tests for measurement_range check behavior inside run_quality_checks."""

    def test_in_range_passes(self) -> None:
        """value=5.0, expected_range=(0.0, 10.0) passes."""
        result = run_quality_checks(
            response_text="4",
            accepted_at=None,
            submitted_at=None,
            expected_duration_minutes=None,
            worker_id=None,
            existing_worker_ids=set(),
            value=5.0,
            expected_range=(0.0, 10.0),
        )
        assert result.passed is True

    def test_out_of_range_fails(self) -> None:
        """value=15.0, expected_range=(0.0, 10.0) fails."""
        result = run_quality_checks(
            response_text="4",
            accepted_at=None,
            submitted_at=None,
            expected_duration_minutes=None,
            worker_id=None,
            existing_worker_ids=set(),
            value=15.0,
            expected_range=(0.0, 10.0),
        )
        assert result.passed is False
        assert result.status == QualityStatus.REJECTED
        assert isinstance(result.failure_reason, str)

    def test_none_value_skips_check(self) -> None:
        """value=None skips range check (passes)."""
        result = run_quality_checks(
            response_text="4",
            accepted_at=None,
            submitted_at=None,
            expected_duration_minutes=None,
            worker_id=None,
            existing_worker_ids=set(),
            value=None,
            expected_range=(0.0, 10.0),
        )
        assert result.passed is True

    def test_none_expected_range_skips_check(self) -> None:
        """expected_range=None skips range check (passes)."""
        result = run_quality_checks(
            response_text="4",
            accepted_at=None,
            submitted_at=None,
            expected_duration_minutes=None,
            worker_id=None,
            existing_worker_ids=set(),
            value=99999.0,
            expected_range=None,
        )
        assert result.passed is True


# ---------------------------------------------------------------------------
# run_quality_checks composite behavior
# ---------------------------------------------------------------------------


class TestRunQualityChecks:
    """Integration tests for run_quality_checks short-circuit behavior."""

    def test_all_passing_returns_validated(self) -> None:
        """All-passing inputs produce QualityCheckResult(passed=True, status=VALIDATED)."""
        t = _now()
        result = run_quality_checks(
            response_text="The answer is 4",
            accepted_at=t,
            submitted_at=t + timedelta(minutes=15),
            expected_duration_minutes=10,
            worker_id="w-new",
            existing_worker_ids={"w-old"},
            value=5.0,
            expected_range=(0.0, 10.0),
        )
        assert result.passed is True
        assert result.status == QualityStatus.VALIDATED
        assert result.failure_reason is None

    def test_failed_attention_returns_rejected(self) -> None:
        """Failed attention check -> REJECTED; checks_run includes 'attention'."""
        result = run_quality_checks(
            response_text="I skipped it",
            accepted_at=None,
            submitted_at=None,
            expected_duration_minutes=None,
            worker_id=None,
            existing_worker_ids=set(),
            value=None,
            expected_range=None,
        )
        assert result.passed is False
        assert result.status == QualityStatus.REJECTED
        assert "attention" in result.checks_run

    def test_failed_response_time_includes_both_checks_in_run(self) -> None:
        """Failed response_time -> REJECTED; checks_run includes 'attention' and 'response_time'."""
        t = _now()
        result = run_quality_checks(
            response_text="4",
            accepted_at=t,
            submitted_at=t + timedelta(seconds=30),
            expected_duration_minutes=10,
            worker_id=None,
            existing_worker_ids=set(),
            value=None,
            expected_range=None,
        )
        assert result.passed is False
        assert result.status == QualityStatus.REJECTED
        assert "attention" in result.checks_run
        assert "response_time" in result.checks_run

    def test_failure_reason_none_on_pass(self) -> None:
        """QualityCheckResult.failure_reason is None when all checks pass."""
        result = run_quality_checks(
            response_text="4",
            accepted_at=None,
            submitted_at=None,
            expected_duration_minutes=None,
            worker_id=None,
            existing_worker_ids=set(),
            value=None,
            expected_range=None,
        )
        assert result.failure_reason is None

    def test_failure_reason_str_on_fail(self) -> None:
        """QualityCheckResult.failure_reason is a str when a check fails."""
        result = run_quality_checks(
            response_text="no number here",
            accepted_at=None,
            submitted_at=None,
            expected_duration_minutes=None,
            worker_id=None,
            existing_worker_ids=set(),
            value=None,
            expected_range=None,
        )
        assert isinstance(result.failure_reason, str)
