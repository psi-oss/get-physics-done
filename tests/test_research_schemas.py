"""Tests for research DAG schemas: milestone status, plan validation, execution order."""

from __future__ import annotations

from gpd.mcp.research.schemas import (
    ApprovalGate,
    CostEstimate,
    MilestoneStatus,
    PlanEvolution,
    ResearchMilestone,
    ResearchPlan,
)


def _make_milestone(
    milestone_id: str,
    depends_on: list[str] | None = None,
    is_critical: bool = True,
    approval_gate: ApprovalGate = ApprovalGate.NONE,
    status: MilestoneStatus = MilestoneStatus.PENDING,
) -> ResearchMilestone:
    """Helper to create a milestone with minimal required fields."""
    return ResearchMilestone(
        milestone_id=milestone_id,
        description=f"Milestone {milestone_id}",
        depends_on=depends_on or [],
        is_critical=is_critical,
        approval_gate=approval_gate,
        status=status,
    )


def _make_plan(milestones: list[ResearchMilestone]) -> ResearchPlan:
    """Helper to create a plan with given milestones."""
    return ResearchPlan(
        plan_id="test-plan-001",
        query="What is the thermal conductivity of steel at 500K?",
        milestones=milestones,
        reasoning="Test plan reasoning.",
    )


class TestMilestoneStatus:
    """Test MilestoneStatus enum values."""

    def test_all_statuses_exist(self) -> None:
        assert MilestoneStatus.PENDING == "pending"
        assert MilestoneStatus.APPROVED == "approved"
        assert MilestoneStatus.RUNNING == "running"
        assert MilestoneStatus.COMPLETED == "completed"
        assert MilestoneStatus.FAILED == "failed"
        assert MilestoneStatus.SKIPPED == "skipped"
        assert MilestoneStatus.REPLANNED == "replanned"

    def test_status_count(self) -> None:
        assert len(MilestoneStatus) == 7


class TestApprovalGate:
    """Test ApprovalGate enum values."""

    def test_all_gates_exist(self) -> None:
        assert ApprovalGate.NONE == "none"
        assert ApprovalGate.REQUIRED == "required"
        assert ApprovalGate.SUGGESTED == "suggested"


class TestCostEstimate:
    """Test CostEstimate model and cost range property."""

    def test_default_values(self) -> None:
        estimate = CostEstimate()
        assert estimate.gpu_type == ""
        assert estimate.estimated_cost_usd == 0.0
        assert estimate.confidence == "LOW"
        assert estimate.tool_call_estimates == []

    def test_estimated_cost_range(self) -> None:
        estimate = CostEstimate(estimated_cost_usd=1.00)
        low, high = estimate.estimated_cost_range
        assert low == 0.70
        assert high == 1.50

    def test_cost_range_zero(self) -> None:
        estimate = CostEstimate(estimated_cost_usd=0.0)
        low, high = estimate.estimated_cost_range
        assert low == 0.0
        assert high == 0.0

    def test_cost_range_fractional(self) -> None:
        estimate = CostEstimate(estimated_cost_usd=0.10)
        low, high = estimate.estimated_cost_range
        assert abs(low - 0.07) < 1e-9
        assert abs(high - 0.15) < 1e-9


class TestResearchPlanValidation:
    """Test ResearchPlan DAG validation methods."""

    def test_valid_dag_no_cycles(self) -> None:
        milestones = [
            _make_milestone("m1"),
            _make_milestone("m2", depends_on=["m1"]),
            _make_milestone("m3", depends_on=["m1"]),
            _make_milestone("m4", depends_on=["m2", "m3"]),
        ]
        plan = _make_plan(milestones)
        errors = plan.validate_no_cycles()
        assert errors == []

    def test_detects_cycle(self) -> None:
        milestones = [
            _make_milestone("m1", depends_on=["m3"]),
            _make_milestone("m2", depends_on=["m1"]),
            _make_milestone("m3", depends_on=["m2"]),
        ]
        plan = _make_plan(milestones)
        errors = plan.validate_no_cycles()
        assert len(errors) == 1
        assert "Cycle detected" in errors[0]

    def test_detects_unknown_dependency(self) -> None:
        milestones = [
            _make_milestone("m1"),
            _make_milestone("m2", depends_on=["m1", "m_nonexistent"]),
        ]
        plan = _make_plan(milestones)
        errors = plan.validate_no_cycles()
        assert len(errors) == 1
        assert "m_nonexistent" in errors[0]

    def test_single_milestone_valid(self) -> None:
        milestones = [_make_milestone("m1")]
        plan = _make_plan(milestones)
        errors = plan.validate_no_cycles()
        assert errors == []

    def test_self_loop_detected(self) -> None:
        milestones = [_make_milestone("m1", depends_on=["m1"])]
        plan = _make_plan(milestones)
        errors = plan.validate_no_cycles()
        assert len(errors) == 1
        assert "Cycle detected" in errors[0]

    def test_detects_unknown_tool_reference(self) -> None:
        milestones = [
            _make_milestone("m1"),
            _make_milestone("m2"),
        ]
        milestones[1].tools = ["known_tool", "invented_tool"]
        plan = _make_plan(milestones)

        errors = plan.validate_tool_references({"known_tool"})

        assert len(errors) == 1
        assert "invented_tool" in errors[0]


class TestExecutionOrder:
    """Test ResearchPlan.get_execution_order."""

    def test_linear_chain(self) -> None:
        milestones = [
            _make_milestone("m1"),
            _make_milestone("m2", depends_on=["m1"]),
            _make_milestone("m3", depends_on=["m2"]),
        ]
        plan = _make_plan(milestones)
        layers = plan.get_execution_order()
        assert layers == [["m1"], ["m2"], ["m3"]]

    def test_parallel_milestones(self) -> None:
        milestones = [
            _make_milestone("m1"),
            _make_milestone("m2"),
            _make_milestone("m3", depends_on=["m1", "m2"]),
        ]
        plan = _make_plan(milestones)
        layers = plan.get_execution_order()
        assert len(layers) == 2
        assert set(layers[0]) == {"m1", "m2"}
        assert layers[1] == ["m3"]

    def test_diamond_dag(self) -> None:
        milestones = [
            _make_milestone("m1"),
            _make_milestone("m2", depends_on=["m1"]),
            _make_milestone("m3", depends_on=["m1"]),
            _make_milestone("m4", depends_on=["m2", "m3"]),
        ]
        plan = _make_plan(milestones)
        layers = plan.get_execution_order()
        assert layers[0] == ["m1"]
        assert set(layers[1]) == {"m2", "m3"}
        assert layers[2] == ["m4"]

    def test_empty_plan(self) -> None:
        plan = _make_plan([])
        layers = plan.get_execution_order()
        assert layers == []


class TestCriticalPath:
    """Test ResearchPlan.get_critical_path."""

    def test_all_critical(self) -> None:
        milestones = [
            _make_milestone("m1", is_critical=True),
            _make_milestone("m2", depends_on=["m1"], is_critical=True),
        ]
        plan = _make_plan(milestones)
        path = plan.get_critical_path()
        assert set(path) == {"m1", "m2"}

    def test_transitive_dependencies_included(self) -> None:
        milestones = [
            _make_milestone("m1", is_critical=False),
            _make_milestone("m2", depends_on=["m1"], is_critical=False),
            _make_milestone("m3", depends_on=["m2"], is_critical=True),
        ]
        plan = _make_plan(milestones)
        path = plan.get_critical_path()
        # m3 is critical, m2 is its dep, m1 is m2's dep -- all on critical path
        assert set(path) == {"m1", "m2", "m3"}

    def test_non_critical_branch_excluded(self) -> None:
        milestones = [
            _make_milestone("m1", is_critical=True),
            _make_milestone("m2", depends_on=["m1"], is_critical=True),
            _make_milestone("m3", is_critical=False),  # independent non-critical
        ]
        plan = _make_plan(milestones)
        path = plan.get_critical_path()
        assert set(path) == {"m1", "m2"}

    def test_empty_plan_critical_path(self) -> None:
        plan = _make_plan([])
        path = plan.get_critical_path()
        assert path == []


class TestPendingApprovalGates:
    """Test ResearchPlan.get_pending_approval_gates."""

    def test_pending_required_gates(self) -> None:
        milestones = [
            _make_milestone("m1", approval_gate=ApprovalGate.REQUIRED),
            _make_milestone("m2", approval_gate=ApprovalGate.NONE),
            _make_milestone("m3", approval_gate=ApprovalGate.SUGGESTED),
        ]
        plan = _make_plan(milestones)
        gates = plan.get_pending_approval_gates()
        assert set(gates) == {"m1", "m3"}

    def test_completed_gates_excluded(self) -> None:
        milestones = [
            _make_milestone(
                "m1",
                approval_gate=ApprovalGate.REQUIRED,
                status=MilestoneStatus.COMPLETED,
            ),
            _make_milestone("m2", approval_gate=ApprovalGate.REQUIRED),
        ]
        plan = _make_plan(milestones)
        gates = plan.get_pending_approval_gates()
        assert gates == ["m2"]

    def test_no_gates(self) -> None:
        milestones = [
            _make_milestone("m1"),
            _make_milestone("m2"),
        ]
        plan = _make_plan(milestones)
        gates = plan.get_pending_approval_gates()
        assert gates == []


class TestPlanEvolution:
    """Test PlanEvolution serialization."""

    def test_serialization_roundtrip(self) -> None:
        evo = PlanEvolution(
            version=2,
            timestamp="2026-02-25T12:00:00Z",
            change_type="add",
            affected_milestones=["m5", "m6"],
            reason="New data source discovered",
            auto_triggered=True,
        )
        data = evo.model_dump()
        restored = PlanEvolution.model_validate(data)
        assert restored.version == 2
        assert restored.change_type == "add"
        assert restored.affected_milestones == ["m5", "m6"]
        assert restored.reason == "New data source discovered"
        assert restored.auto_triggered is True

    def test_default_values(self) -> None:
        evo = PlanEvolution(
            version=1,
            timestamp="2026-02-25T12:00:00Z",
            change_type="modify",
        )
        assert evo.affected_milestones == []
        assert evo.reason == ""
        assert evo.auto_triggered is False
