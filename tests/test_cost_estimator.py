"""Tests for Modal cost estimation: per-milestone, plan aggregation, display formatting."""

from __future__ import annotations

from gpd.mcp.research.cost_estimator import (
    COLD_START_OVERHEAD_SECONDS,
    MODAL_RATES_USD_PER_SECOND,
    NON_PREEMPTIBLE_MULTIPLIER,
    REGIONAL_MULTIPLIER,
    estimate_milestone_cost,
    estimate_plan_cost,
    format_cost_display,
)
from gpd.mcp.research.schemas import (
    CostEstimate,
    ResearchMilestone,
    ResearchPlan,
)


def _make_milestone(
    milestone_id: str,
    depends_on: list[str] | None = None,
) -> ResearchMilestone:
    """Helper to create a minimal milestone for cost testing."""
    return ResearchMilestone(
        milestone_id=milestone_id,
        description=f"Milestone {milestone_id}",
        depends_on=depends_on or [],
    )


class TestEstimateMilestoneCost:
    """Test estimate_milestone_cost with various GPU types."""

    def test_known_gpu_type_a10g(self) -> None:
        milestone = _make_milestone("m1")
        metadata: dict[str, object] = {"gpu_type": "A10G", "estimated_seconds": 30.0}
        estimate = estimate_milestone_cost(milestone, metadata)

        expected_seconds = 30.0 + COLD_START_OVERHEAD_SECONDS
        expected_rate = MODAL_RATES_USD_PER_SECOND["A10G"] * REGIONAL_MULTIPLIER * NON_PREEMPTIBLE_MULTIPLIER
        expected_cost = expected_seconds * expected_rate

        assert estimate.gpu_type == "A10G"
        assert estimate.estimated_seconds == expected_seconds
        assert abs(estimate.rate_per_second - expected_rate) < 1e-9
        assert abs(estimate.estimated_cost_usd - expected_cost) < 1e-9
        assert estimate.confidence == "MEDIUM"

    def test_known_gpu_type_h100(self) -> None:
        milestone = _make_milestone("m1")
        metadata: dict[str, object] = {"gpu_type": "H100", "estimated_seconds": 60.0}
        estimate = estimate_milestone_cost(milestone, metadata)

        expected_seconds = 60.0 + COLD_START_OVERHEAD_SECONDS
        expected_rate = MODAL_RATES_USD_PER_SECOND["H100"] * REGIONAL_MULTIPLIER * NON_PREEMPTIBLE_MULTIPLIER
        expected_cost = expected_seconds * expected_rate

        assert estimate.gpu_type == "H100"
        assert abs(estimate.estimated_cost_usd - expected_cost) < 1e-9
        assert estimate.confidence == "MEDIUM"

    def test_unknown_gpu_falls_back_to_cpu(self) -> None:
        milestone = _make_milestone("m1")
        metadata: dict[str, object] = {"gpu_type": "V100", "estimated_seconds": 10.0}
        estimate = estimate_milestone_cost(milestone, metadata)

        expected_rate = MODAL_RATES_USD_PER_SECOND["CPU"] * REGIONAL_MULTIPLIER * NON_PREEMPTIBLE_MULTIPLIER

        assert estimate.gpu_type == "V100"
        assert abs(estimate.rate_per_second - expected_rate) < 1e-9
        assert estimate.confidence == "LOW"

    def test_default_cpu_when_no_gpu_type(self) -> None:
        milestone = _make_milestone("m1")
        metadata: dict[str, object] = {"estimated_seconds": 15.0}
        estimate = estimate_milestone_cost(milestone, metadata)

        assert estimate.gpu_type == "CPU"
        assert estimate.confidence == "MEDIUM"

    def test_cold_start_overhead_added(self) -> None:
        milestone = _make_milestone("m1")
        metadata: dict[str, object] = {"gpu_type": "T4", "estimated_seconds": 10.0}
        estimate = estimate_milestone_cost(milestone, metadata)

        assert estimate.estimated_seconds == 10.0 + COLD_START_OVERHEAD_SECONDS

    def test_default_estimated_seconds(self) -> None:
        milestone = _make_milestone("m1")
        metadata: dict[str, object] = {"gpu_type": "CPU"}
        estimate = estimate_milestone_cost(milestone, metadata)

        # Default 30s + cold start
        assert estimate.estimated_seconds == 30.0 + COLD_START_OVERHEAD_SECONDS


class TestEstimatePlanCost:
    """Test estimate_plan_cost aggregation across milestones."""

    def test_single_milestone_plan(self) -> None:
        milestones = [_make_milestone("m1")]
        plan = ResearchPlan(
            plan_id="test",
            query="test query",
            milestones=milestones,
            reasoning="test",
        )
        registry: dict[str, dict[str, object]] = {
            "m1": {"gpu_type": "A10G", "estimated_seconds": 30.0},
        }
        total = estimate_plan_cost(plan, registry)

        assert total.estimated_cost_usd > 0
        assert total.confidence == "MEDIUM"
        assert total.gpu_type == "A10G"

    def test_multi_milestone_aggregation(self) -> None:
        milestones = [
            _make_milestone("m1"),
            _make_milestone("m2", depends_on=["m1"]),
        ]
        plan = ResearchPlan(
            plan_id="test",
            query="test query",
            milestones=milestones,
            reasoning="test",
        )
        registry: dict[str, dict[str, object]] = {
            "m1": {"gpu_type": "A10G", "estimated_seconds": 30.0},
            "m2": {"gpu_type": "H100", "estimated_seconds": 60.0},
        }
        total = estimate_plan_cost(plan, registry)

        # Total should be sum of both milestones
        m1_cost = estimate_milestone_cost(milestones[0], registry["m1"])
        m2_cost = estimate_milestone_cost(milestones[1], registry["m2"])
        expected_total = m1_cost.estimated_cost_usd + m2_cost.estimated_cost_usd
        assert abs(total.estimated_cost_usd - expected_total) < 1e-9
        assert total.gpu_type == "mixed"

    def test_min_confidence_propagated(self) -> None:
        milestones = [
            _make_milestone("m1"),
            _make_milestone("m2"),
        ]
        plan = ResearchPlan(
            plan_id="test",
            query="test query",
            milestones=milestones,
            reasoning="test",
        )
        registry: dict[str, dict[str, object]] = {
            "m1": {"gpu_type": "A10G", "estimated_seconds": 30.0},  # MEDIUM
            "m2": {"gpu_type": "V100", "estimated_seconds": 30.0},  # LOW (unknown)
        }
        total = estimate_plan_cost(plan, registry)

        assert total.confidence == "LOW"

    def test_empty_plan(self) -> None:
        plan = ResearchPlan(
            plan_id="test",
            query="test query",
            milestones=[],
            reasoning="test",
        )
        total = estimate_plan_cost(plan, {})
        assert total.estimated_cost_usd == 0.0
        assert total.confidence == "LOW"

    def test_milestone_costs_set_on_plan_milestones(self) -> None:
        milestones = [_make_milestone("m1")]
        plan = ResearchPlan(
            plan_id="test",
            query="test query",
            milestones=milestones,
            reasoning="test",
        )
        registry: dict[str, dict[str, object]] = {
            "m1": {"gpu_type": "T4", "estimated_seconds": 20.0},
        }
        estimate_plan_cost(plan, registry)

        # Verify milestone's cost_estimate was updated
        assert plan.milestones[0].cost_estimate.gpu_type == "T4"
        assert plan.milestones[0].cost_estimate.estimated_cost_usd > 0


class TestFormatCostDisplay:
    """Test format_cost_display output formatting."""

    def test_typical_format(self) -> None:
        estimate = CostEstimate(
            gpu_type="A10G",
            estimated_seconds=50.0,
            rate_per_second=0.001148,
            estimated_cost_usd=0.0574,
            confidence="MEDIUM",
        )
        display = format_cost_display(estimate)

        assert "$" in display
        assert "A10G" in display
        assert "~50s" in display
        assert "MEDIUM confidence" in display

    def test_cpu_format(self) -> None:
        estimate = CostEstimate(
            gpu_type="",
            estimated_seconds=30.0,
            estimated_cost_usd=0.001,
            confidence="LOW",
        )
        display = format_cost_display(estimate)

        assert "CPU" in display
        assert "LOW confidence" in display

    def test_range_in_display(self) -> None:
        estimate = CostEstimate(estimated_cost_usd=1.00)
        display = format_cost_display(estimate)

        # Should show range: $0.70-$1.50
        assert "$0.70" in display
        assert "$1.50" in display
