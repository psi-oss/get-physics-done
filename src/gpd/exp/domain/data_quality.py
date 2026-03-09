"""Data quality domain module.

Layer 1 pure domain logic: no framework imports, no side effects, no I/O.
Implements four quality checks and a composite run_quality_checks function
that applies them in order with short-circuit failure.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from gpd.exp.contracts.data import QualityStatus

#: Token that workers must include in their response to pass the attention check.
#: Shared with bounty_translator.ATTENTION_TOKEN (same value by design).
ATTENTION_TOKEN = "4"

#: Minimum fraction of expected duration that a valid response must take.
_MIN_RESPONSE_TIME_FRACTION = 0.30

#: Absolute floor for minimum response time in minutes.
_MIN_RESPONSE_TIME_FLOOR_MINUTES = 3.0


@dataclass(frozen=True)
class QualityCheckResult:
    """Result of running one or more quality checks on a data point.

    Attributes:
        passed: True if all checks passed.
        status: QualityStatus enum value reflecting the outcome.
        failure_reason: Human-readable explanation on failure, None on pass.
        checks_run: List of check names that were executed (in order).
    """

    passed: bool
    status: QualityStatus
    failure_reason: str | None
    checks_run: list[str]


def _check_attention(response_text: str) -> str | None:
    """Check that the response contains the attention token '4'.

    Returns None on pass, a failure reason string on failure.
    """
    if ATTENTION_TOKEN in response_text.lower():
        return None
    return f"Attention check failed: response did not contain '{ATTENTION_TOKEN}'."


def _check_response_time(
    accepted_at: datetime | None,
    submitted_at: datetime | None,
    expected_duration_minutes: int | None,
) -> str | None:
    """Check that submission took at least 30% of expected duration (floor: 3 min).

    Skips the check if accepted_at or expected_duration_minutes is None.
    Returns None on pass, a failure reason string on failure.
    """
    if accepted_at is None or expected_duration_minutes is None:
        return None

    if submitted_at is None:
        return None

    # Ensure both datetimes are comparable (both aware or both naive)
    actual_seconds = (submitted_at - accepted_at).total_seconds()
    floor_seconds = max(expected_duration_minutes * _MIN_RESPONSE_TIME_FRACTION, _MIN_RESPONSE_TIME_FLOOR_MINUTES) * 60

    if actual_seconds < floor_seconds:
        actual_min = actual_seconds / 60
        floor_min = floor_seconds / 60
        return (
            f"Response time check failed: submitted in {actual_min:.1f} minutes "
            f"but minimum is {floor_min:.1f} minutes "
            f"(30% of expected {expected_duration_minutes} minutes)."
        )
    return None


def _check_no_duplicate_worker(
    worker_id: str | None,
    existing_worker_ids: set[str],
) -> str | None:
    """Check that this worker has not already submitted a response.

    Skips the check if worker_id is None.
    Returns None on pass, a failure reason string on failure.
    """
    if worker_id is None:
        return None
    if worker_id in existing_worker_ids:
        return f"Duplicate worker check failed: worker '{worker_id}' has already submitted."
    return None


def _check_measurement_range(
    value: float | None,
    expected_range: tuple[float, float] | None,
) -> str | None:
    """Check that the measured value is within the expected range [lo, hi].

    Skips the check if value or expected_range is None.
    Returns None on pass, a failure reason string on failure.
    """
    if value is None or expected_range is None:
        return None
    lo, hi = expected_range
    if lo <= value <= hi:
        return None
    return f"Measurement range check failed: value {value} is outside expected range [{lo}, {hi}]."


def run_quality_checks(
    response_text: str,
    accepted_at: datetime | None,
    submitted_at: datetime | None,
    expected_duration_minutes: int | None,
    worker_id: str | None,
    existing_worker_ids: set[str],
    value: float | None,
    expected_range: tuple[float, float] | None,
) -> QualityCheckResult:
    """Run all four quality checks in order, short-circuiting on first failure.

    Check order:
      1. attention       — Did the worker include the attention token?
      2. response_time   — Did the worker take a plausible amount of time?
      3. duplicate_worker — Has this worker already submitted?
      4. measurement_range — Is the reported value within the expected range?

    Args:
        response_text: Free-text response from the worker.
        accepted_at: When the worker accepted the task (timezone-aware).
        submitted_at: When the worker submitted the response.
        expected_duration_minutes: Expected task duration for time validation.
        worker_id: Unique identifier for the submitting worker.
        existing_worker_ids: Set of worker_ids that have already submitted.
        value: Numeric measurement value (may be None if categorical).
        expected_range: (min, max) tuple for measurement validation.

    Returns:
        QualityCheckResult with outcome and all checks that were attempted.
    """
    checks_run: list[str] = []

    # --- Check 1: Attention ---
    checks_run.append("attention")
    reason = _check_attention(response_text)
    if reason is not None:
        return QualityCheckResult(
            passed=False,
            status=QualityStatus.REJECTED,
            failure_reason=reason,
            checks_run=checks_run,
        )

    # --- Check 2: Response time ---
    checks_run.append("response_time")
    reason = _check_response_time(accepted_at, submitted_at, expected_duration_minutes)
    if reason is not None:
        return QualityCheckResult(
            passed=False,
            status=QualityStatus.REJECTED,
            failure_reason=reason,
            checks_run=checks_run,
        )

    # --- Check 3: Duplicate worker ---
    checks_run.append("duplicate_worker")
    reason = _check_no_duplicate_worker(worker_id, existing_worker_ids)
    if reason is not None:
        return QualityCheckResult(
            passed=False,
            status=QualityStatus.REJECTED,
            failure_reason=reason,
            checks_run=checks_run,
        )

    # --- Check 4: Measurement range ---
    checks_run.append("measurement_range")
    reason = _check_measurement_range(value, expected_range)
    if reason is not None:
        return QualityCheckResult(
            passed=False,
            status=QualityStatus.REJECTED,
            failure_reason=reason,
            checks_run=checks_run,
        )

    # All checks passed
    return QualityCheckResult(
        passed=True,
        status=QualityStatus.VALIDATED,
        failure_reason=None,
        checks_run=checks_run,
    )
