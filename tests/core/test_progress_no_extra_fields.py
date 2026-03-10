"""Regression test: ProgressJsonResult should not have misleading extra fields."""
from __future__ import annotations

from gpd.core.phases import ProgressJsonResult


def test_progress_json_result_no_total_plans_in_phase_field():
    """The model should not define or accept total_plans_in_phase as it's misleading.

    The field was previously set to the total across ALL phases, not per-phase.
    It was removed as a bug fix. This test prevents regression.
    """
    result = ProgressJsonResult(
        milestone_version="1.0",
        milestone_name="Test",
        total_plans=5,
        total_summaries=3,
        percent=60,
    )
    dumped = result.model_dump()
    assert "total_plans_in_phase" not in dumped, (
        "total_plans_in_phase should not be in ProgressJsonResult — "
        "it was a misleading extra field (stored total across ALL phases)"
    )


def test_progress_json_result_defined_fields():
    """ProgressJsonResult should only have these explicit fields."""
    expected = {"milestone_version", "milestone_name", "phases", "total_plans", "total_summaries", "percent"}
    actual = set(ProgressJsonResult.model_fields.keys())
    assert actual == expected
