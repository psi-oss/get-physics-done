"""Tests for the LLM-driven research planner: plan generation, evolution, display."""

from __future__ import annotations

from io import StringIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from rich.console import Console

from gpd.mcp.research.planner import (
    PlanValidationError,
    ResearchPlanner,
    display_plan,
    display_plan_evolution,
)
from gpd.mcp.research.schemas import (
    ApprovalGate,
    CostEstimate,
    MilestoneResult,
    MilestoneStatus,
    PlanEvolution,
    ResearchMilestone,
    ResearchPlan,
)


def _make_test_plan(
    milestones: list[ResearchMilestone] | None = None,
    version: int = 1,
) -> ResearchPlan:
    """Create a test plan with sensible defaults."""
    if milestones is None:
        milestones = [
            ResearchMilestone(
                milestone_id="m1",
                description="Gather thermal conductivity data for steel alloys",
                depends_on=[],
                tools=["materials_db"],
                expected_outputs=["thermal_data.json"],
                success_criteria="Retrieved data for at least 3 steel alloys",
                is_critical=True,
            ),
            ResearchMilestone(
                milestone_id="m2",
                description="Run CFD simulation at 500K",
                depends_on=["m1"],
                tools=["openfoam"],
                expected_outputs=["temperature_field.vtk"],
                success_criteria="Simulation converges within 1000 iterations",
                is_critical=True,
            ),
            ResearchMilestone(
                milestone_id="m3",
                description="Compare simulation results with literature values",
                depends_on=["m1", "m2"],
                tools=["analysis"],
                expected_outputs=["comparison_table.json"],
                success_criteria="Results within 10% of published values",
                approval_gate=ApprovalGate.SUGGESTED,
                is_critical=True,
            ),
        ]
    return ResearchPlan(
        plan_id="test-plan-001",
        query="What is the thermal conductivity of steel at 500K?",
        milestones=milestones,
        reasoning="Decomposed into data gathering, simulation, and validation steps.",
        version=version,
    )


def _make_mock_agent_result(plan: ResearchPlan) -> MagicMock:
    """Create a mock result object that mimics PydanticAI Agent.run output."""
    mock_result = MagicMock()
    mock_result.output = plan
    return mock_result


class TestResearchPlannerGeneratePlan:
    """Test ResearchPlanner.generate_plan with mocked LLM agent."""

    @pytest.mark.asyncio
    @patch("gpd.mcp.research.planner.Agent")
    async def test_generate_plan_adds_cost_estimates(self, _mock_agent_cls: MagicMock) -> None:
        planner = ResearchPlanner()
        test_plan = _make_test_plan()

        with patch.object(planner._plan_agent, "run", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = _make_mock_agent_result(test_plan)

            result = await planner.generate_plan(
                query="Test question",
                available_tools=[
                    {"name": "openfoam", "description": "CFD solver"},
                    {"name": "materials_db", "description": "Materials database"},
                    {"name": "analysis", "description": "Analysis toolkit"},
                ],
                tool_metadata_registry={
                    "m1": {"gpu_type": "CPU", "estimated_seconds": 10.0},
                    "m2": {"gpu_type": "A10G", "estimated_seconds": 60.0},
                    "m3": {"gpu_type": "CPU", "estimated_seconds": 5.0},
                },
            )

        # Cost estimates should be set on milestones
        assert result.total_cost_estimate.estimated_cost_usd > 0
        for milestone in result.milestones:
            assert milestone.cost_estimate.estimated_cost_usd > 0

    @pytest.mark.asyncio
    @patch("gpd.mcp.research.planner.Agent")
    async def test_generate_plan_sets_plan_id(self, _mock_agent_cls: MagicMock) -> None:
        planner = ResearchPlanner()
        test_plan = _make_test_plan()

        with patch.object(planner._plan_agent, "run", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = _make_mock_agent_result(test_plan)

            result = await planner.generate_plan(
                query="Test",
                available_tools=[],
                tool_metadata_registry={},
            )

        # plan_id should be set (12 hex chars)
        assert len(result.plan_id) == 12
        assert result.plan_id != "test-plan-001"  # Should be regenerated

    @pytest.mark.asyncio
    @patch("gpd.mcp.research.planner.Agent")
    async def test_generate_plan_validates_dag(self, _mock_agent_cls: MagicMock) -> None:
        planner = ResearchPlanner()
        test_plan = _make_test_plan()

        with patch.object(planner._plan_agent, "run", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = _make_mock_agent_result(test_plan)

            result = await planner.generate_plan(
                query="Test",
                available_tools=[],
                tool_metadata_registry={},
            )

        # Should be a valid DAG
        errors = result.validate_no_cycles()
        assert errors == []

    @pytest.mark.asyncio
    @patch("gpd.mcp.research.planner.Agent")
    async def test_generate_plan_retries_on_cycles(self, _mock_agent_cls: MagicMock) -> None:
        planner = ResearchPlanner()

        # First call returns cyclic plan, second returns valid plan
        cyclic_plan = ResearchPlan(
            plan_id="bad",
            query="Test",
            milestones=[
                ResearchMilestone(milestone_id="m1", description="step 1", depends_on=["m2"]),
                ResearchMilestone(milestone_id="m2", description="step 2", depends_on=["m1"]),
            ],
            reasoning="Bad plan",
        )
        valid_plan = _make_test_plan()

        with patch.object(planner._plan_agent, "run", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = [
                _make_mock_agent_result(cyclic_plan),
                _make_mock_agent_result(valid_plan),
            ]

            result = await planner.generate_plan(
                query="Test",
                available_tools=[],
                tool_metadata_registry={},
            )

        # Should have retried and returned valid plan
        assert mock_run.call_count == 2
        errors = result.validate_no_cycles()
        assert errors == []

    @pytest.mark.asyncio
    @patch("gpd.mcp.research.planner.Agent")
    async def test_generate_plan_revalidates_tools_after_dag_retry(self, _mock_agent_cls: MagicMock) -> None:
        planner = ResearchPlanner()

        cyclic_plan = ResearchPlan(
            plan_id="bad",
            query="Test",
            milestones=[
                ResearchMilestone(milestone_id="m1", description="step 1", depends_on=["m2"], tools=["analysis"]),
                ResearchMilestone(milestone_id="m2", description="step 2", depends_on=["m1"], tools=["analysis"]),
            ],
            reasoning="Bad DAG",
        )
        invalid_tool_plan = ResearchPlan(
            plan_id="bad-tools",
            query="Test",
            milestones=[
                ResearchMilestone(milestone_id="m1", description="step 1", tools=["invented_tool"]),
            ],
            reasoning="Bad tools",
        )
        valid_plan = _make_test_plan()

        with patch.object(planner._plan_agent, "run", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = [
                _make_mock_agent_result(cyclic_plan),
                _make_mock_agent_result(invalid_tool_plan),
                _make_mock_agent_result(valid_plan),
            ]

            result = await planner.generate_plan(
                query="Test",
                available_tools=[
                    {"name": "openfoam", "description": "CFD solver"},
                    {"name": "materials_db", "description": "Materials database"},
                    {"name": "analysis", "description": "Analysis toolkit"},
                ],
                tool_metadata_registry={},
            )

        assert mock_run.call_count == 3
        assert result.validate_no_cycles() == []
        assert result.validate_tool_references({"openfoam", "materials_db", "analysis"}) == []

    @pytest.mark.asyncio
    @patch("gpd.mcp.research.planner.Agent")
    async def test_generate_plan_raises_after_repeated_invalid_tools(self, _mock_agent_cls: MagicMock) -> None:
        planner = ResearchPlanner()
        invalid_tool_plan = ResearchPlan(
            plan_id="bad-tools",
            query="Test",
            milestones=[
                ResearchMilestone(milestone_id="m1", description="step 1", tools=["invented_tool"]),
            ],
            reasoning="Bad tools",
        )

        with patch.object(planner._plan_agent, "run", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = [_make_mock_agent_result(invalid_tool_plan)] * 3

            with pytest.raises(PlanValidationError):
                await planner.generate_plan(
                    query="Test",
                    available_tools=[{"name": "analysis", "description": "Analysis toolkit"}],
                    tool_metadata_registry={},
                )

        assert mock_run.call_count == 3

    @pytest.mark.asyncio
    @patch("gpd.mcp.research.planner.Agent")
    async def test_generate_plan_sets_default_approval_gates(self, _mock_agent_cls: MagicMock) -> None:
        planner = ResearchPlanner()
        test_plan = _make_test_plan()
        # Clear any existing gates
        for m in test_plan.milestones:
            m.approval_gate = ApprovalGate.NONE

        with patch.object(planner._plan_agent, "run", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = _make_mock_agent_result(test_plan)

            result = await planner.generate_plan(
                query="Test",
                available_tools=[],
                tool_metadata_registry={},
            )

        # First milestone should get SUGGESTED gate by default
        assert result.milestones[0].approval_gate == ApprovalGate.SUGGESTED


class TestResearchPlannerEvolvePlan:
    """Test ResearchPlanner.evolve_plan with mocked LLM agent."""

    @pytest.mark.asyncio
    @patch("gpd.mcp.research.planner.Agent")
    async def test_evolve_plan_detects_added_milestones(self, _mock_agent_cls: MagicMock) -> None:
        planner = ResearchPlanner()
        original_plan = _make_test_plan()
        original_plan.milestones[0].status = MilestoneStatus.COMPLETED

        # Evolved plan adds a new milestone
        evolved_milestones = [*original_plan.milestones]
        evolved_milestones.append(
            ResearchMilestone(
                milestone_id="m4",
                description="Additional analysis step",
                depends_on=["m2"],
                tools=["analysis"],
            )
        )
        evolved_plan = _make_test_plan(milestones=evolved_milestones)

        with patch.object(planner._evolution_agent, "run", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = _make_mock_agent_result(evolved_plan)

            result, evolutions = await planner.evolve_plan(
                plan=original_plan,
                completed_results={"m1": MilestoneResult(milestone_id="m1", result_summary="Found data")},
                latest_milestone_id="m1",
                tool_metadata_registry={},
            )

        # Should detect the addition
        add_evos = [e for e in evolutions if e.change_type == "add"]
        assert len(add_evos) == 1
        assert "m4" in add_evos[0].affected_milestones

    @pytest.mark.asyncio
    @patch("gpd.mcp.research.planner.Agent")
    async def test_evolve_plan_increments_version(self, _mock_agent_cls: MagicMock) -> None:
        planner = ResearchPlanner()
        original_plan = _make_test_plan(version=1)

        with patch.object(planner._evolution_agent, "run", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = _make_mock_agent_result(_make_test_plan())

            result, _ = await planner.evolve_plan(
                plan=original_plan,
                completed_results={},
                latest_milestone_id="m1",
                tool_metadata_registry={},
            )

        assert result.version == 2

    @pytest.mark.asyncio
    @patch("gpd.mcp.research.planner.Agent")
    async def test_evolve_plan_preserves_approval_gates(self, _mock_agent_cls: MagicMock) -> None:
        planner = ResearchPlanner()
        original_plan = _make_test_plan()
        original_plan.milestones[0].approval_gate = ApprovalGate.REQUIRED

        # Return same plan (no changes)
        returned_plan = _make_test_plan()
        returned_plan.milestones[0].approval_gate = ApprovalGate.NONE  # LLM might reset this

        with patch.object(planner._evolution_agent, "run", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = _make_mock_agent_result(returned_plan)

            result, _ = await planner.evolve_plan(
                plan=original_plan,
                completed_results={},
                latest_milestone_id="m1",
                tool_metadata_registry={},
            )

        # Should preserve the REQUIRED gate from original
        assert result.milestones[0].approval_gate == ApprovalGate.REQUIRED

    @pytest.mark.asyncio
    @patch("gpd.mcp.research.planner.Agent")
    async def test_evolve_plan_sets_suggested_gate_on_new_milestones(self, _mock_agent_cls: MagicMock) -> None:
        planner = ResearchPlanner()
        original_plan = _make_test_plan()

        evolved_milestones = [*original_plan.milestones]
        evolved_milestones.append(
            ResearchMilestone(
                milestone_id="m_new",
                description="Brand new milestone",
                depends_on=[],
                tools=[],
                approval_gate=ApprovalGate.NONE,
            )
        )
        evolved_plan = _make_test_plan(milestones=evolved_milestones)

        with patch.object(planner._evolution_agent, "run", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = _make_mock_agent_result(evolved_plan)

            result, _ = await planner.evolve_plan(
                plan=original_plan,
                completed_results={},
                latest_milestone_id="m1",
                tool_metadata_registry={},
            )

        # New milestone should get SUGGESTED gate
        new_m = next(m for m in result.milestones if m.milestone_id == "m_new")
        assert new_m.approval_gate == ApprovalGate.SUGGESTED

    @pytest.mark.asyncio
    @patch("gpd.mcp.research.planner.Agent")
    async def test_evolve_plan_revalidates_after_invalid_tool_output(self, _mock_agent_cls: MagicMock) -> None:
        planner = ResearchPlanner()
        original_plan = _make_test_plan()
        invalid_tool_plan = _make_test_plan(
            milestones=[
                ResearchMilestone(
                    milestone_id="m1",
                    description="step 1",
                    tools=["invented_tool"],
                ),
            ]
        )

        with patch.object(planner._evolution_agent, "run", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = [
                _make_mock_agent_result(invalid_tool_plan),
                _make_mock_agent_result(_make_test_plan()),
            ]

            result, _ = await planner.evolve_plan(
                plan=original_plan,
                completed_results={},
                latest_milestone_id="m1",
                tool_metadata_registry={},
            )

        assert mock_run.call_count == 2
        assert result.validate_tool_references({"materials_db", "openfoam", "analysis"}) == []

    @pytest.mark.asyncio
    @patch("gpd.mcp.research.planner.Agent")
    async def test_evolve_plan_revalidates_dag(self, _mock_agent_cls: MagicMock) -> None:
        planner = ResearchPlanner()
        original_plan = _make_test_plan()
        cyclic_plan = ResearchPlan(
            plan_id="bad",
            query="Test",
            milestones=[
                ResearchMilestone(milestone_id="m1", description="step 1", depends_on=["m2"], tools=["materials_db"]),
                ResearchMilestone(milestone_id="m2", description="step 2", depends_on=["m1"], tools=["analysis"]),
            ],
            reasoning="Bad DAG",
        )

        with patch.object(planner._evolution_agent, "run", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = [
                _make_mock_agent_result(cyclic_plan),
                _make_mock_agent_result(_make_test_plan()),
            ]

            result, _ = await planner.evolve_plan(
                plan=original_plan,
                completed_results={},
                latest_milestone_id="m1",
                tool_metadata_registry={},
            )

        assert mock_run.call_count == 2
        assert result.validate_no_cycles() == []


class TestDisplayPlan:
    """Test display_plan renders without error."""

    def test_display_plan_renders(self) -> None:
        plan = _make_test_plan()
        # Set cost estimates so display has data
        for m in plan.milestones:
            m.cost_estimate = CostEstimate(
                gpu_type="A10G",
                estimated_seconds=50.0,
                rate_per_second=0.001,
                estimated_cost_usd=0.05,
                confidence="MEDIUM",
            )
        plan.total_cost_estimate = CostEstimate(
            gpu_type="mixed",
            estimated_seconds=150.0,
            estimated_cost_usd=0.15,
            confidence="MEDIUM",
        )

        output = StringIO()
        console = Console(file=output, force_terminal=True, width=120)
        display_plan(plan, console)

        rendered = output.getvalue()
        assert "Research Plan" in rendered
        assert "thermal conductivity" in rendered.lower() or "Thermal" in rendered

    def test_display_plan_handles_empty_plan(self) -> None:
        plan = _make_test_plan(milestones=[])
        plan.total_cost_estimate = CostEstimate()

        output = StringIO()
        console = Console(file=output, force_terminal=True, width=120)
        display_plan(plan, console)

        rendered = output.getvalue()
        assert "0 milestones" in rendered

    def test_display_plan_truncates_long_descriptions(self) -> None:
        milestones = [
            ResearchMilestone(
                milestone_id="m1",
                description="A" * 100,  # Very long description
                cost_estimate=CostEstimate(estimated_cost_usd=0.01),
            ),
        ]
        plan = _make_test_plan(milestones=milestones)
        plan.total_cost_estimate = CostEstimate(estimated_cost_usd=0.01)

        output = StringIO()
        console = Console(file=output, force_terminal=True, width=120)
        display_plan(plan, console)

        rendered = output.getvalue()
        # Should truncate -- either our "..." or Rich's Unicode ellipsis
        assert "..." in rendered or "\u2026" in rendered
        # Full 100-char string should NOT appear
        assert "A" * 100 not in rendered


class TestDisplayPlanEvolution:
    """Test display_plan_evolution rendering."""

    def test_displays_added_milestones_in_green(self) -> None:
        evolutions = [
            PlanEvolution(
                version=2,
                timestamp="2026-02-25T12:00:00Z",
                change_type="add",
                affected_milestones=["m4"],
                reason="New analysis needed",
            ),
        ]

        output = StringIO()
        console = Console(file=output, force_terminal=True, width=120)
        display_plan_evolution(evolutions, console)

        rendered = output.getvalue()
        assert "m4" in rendered
        assert "Plan Evolution" in rendered

    def test_displays_removed_milestones(self) -> None:
        evolutions = [
            PlanEvolution(
                version=2,
                timestamp="2026-02-25T12:00:00Z",
                change_type="remove",
                affected_milestones=["m2"],
                reason="No longer needed",
            ),
        ]

        output = StringIO()
        console = Console(file=output, force_terminal=True, width=120)
        display_plan_evolution(evolutions, console)

        rendered = output.getvalue()
        assert "m2" in rendered

    def test_displays_modified_milestones(self) -> None:
        evolutions = [
            PlanEvolution(
                version=2,
                timestamp="2026-02-25T12:00:00Z",
                change_type="modify",
                affected_milestones=["m1"],
                reason="Tools updated",
            ),
        ]

        output = StringIO()
        console = Console(file=output, force_terminal=True, width=120)
        display_plan_evolution(evolutions, console)

        rendered = output.getvalue()
        assert "m1" in rendered

    def test_empty_evolution_list(self) -> None:
        output = StringIO()
        console = Console(file=output, force_terminal=True, width=120)
        display_plan_evolution([], console)

        rendered = output.getvalue()
        assert "No plan changes" in rendered
