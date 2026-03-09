"""Tests for GPDMCTSStrategy."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

pytest.importorskip("pipeline")

from psi_contracts.campaign import CampaignConfig, StrategyParams
from psi_contracts.common import Score
from psi_contracts.formalization import FormalProblem, Verifier
from psi_contracts.solving import CandidateSolution, Run

from gpd.strategy.mcts import (
    GPDMCTSStrategy,
    _extract_convention_lock,
    _infer_domain,
    _parse_error_classes_from_markdown,
    _resolve_gpd_mcp_tools,
    _run_invariant_checks,
    convention_lock_consistency_check,
)

# --- Fixtures ---


def _make_problem(**kwargs: object) -> FormalProblem:
    defaults: dict[str, object] = {
        "title": "Test Problem",
        "objective": "Compute the partition function",
        "system_setup": "Consider a 2D Ising model",
        "evaluation_summary": "Check thermodynamic consistency",
        "problem_statement": "Calculate Z for the 2D Ising model",
        "domain": None,
    }
    defaults.update(kwargs)
    return FormalProblem(**defaults)


def _make_verifier() -> Verifier:
    return Verifier(code="def verify(solution): return 0.8")


def _make_config(gpd_enabled: bool = False, **gpd_kwargs: object) -> CampaignConfig:
    sp_kwargs: dict[str, object] = {"gpd_enabled": gpd_enabled}
    sp_kwargs.update(gpd_kwargs)
    return CampaignConfig(strategy_params=StrategyParams(**sp_kwargs))


def _make_run(score: float = 75.0, solution_text: str = "x = 42") -> Run:
    return Run(
        id=uuid4(),
        campaign_id=uuid4(),
        sequence_number=1,
        score=Score(value=score),
        cost_usd=0.01,
        duration_seconds=1.0,
        solution=CandidateSolution(
            summary="Test solution",
            approach_description="MCTS node 1",
            code=solution_text,
        ),
        summary="Test solution",
        tool_calls=[],
        created_at=datetime.now(UTC),
    )


def _make_memory() -> MagicMock:
    memory = MagicMock()
    memory.record_hypothesis = AsyncMock()
    memory.record_attempt = AsyncMock()
    memory.update_best_run = AsyncMock()
    memory.get_attempts = AsyncMock(return_value=[])
    memory.get_best_run = AsyncMock(return_value=None)
    memory.get_verification_feedback = AsyncMock(return_value=[])
    memory.get_latest_verification_feedback = AsyncMock(return_value=None)
    memory.is_approach_exhausted = AsyncMock(return_value=False)
    return memory


def _make_events() -> MagicMock:
    events = MagicMock()
    events.emit = AsyncMock()
    return events


def _make_capabilities() -> MagicMock:
    caps = MagicMock()
    caps.is_available = MagicMock(return_value=False)
    return caps


# --- _extract_convention_lock ---


class TestExtractConventionLock:
    def test_empty_problem(self):
        problem = _make_problem()
        lock = _extract_convention_lock(problem)
        assert lock.metric_signature is None

    def test_convention_in_problem_statement(self):
        problem = _make_problem(problem_statement="# ASSERT_CONVENTION: metric_signature=mostly-plus\nCalculate Z.")
        lock = _extract_convention_lock(problem)
        assert lock.metric_signature == "mostly-plus"

    def test_convention_in_hard_constraints(self):
        problem = _make_problem(
            hard_constraints=["# ASSERT_CONVENTION: natural_units=c=hbar=1"],
        )
        lock = _extract_convention_lock(problem)
        assert lock.natural_units == "c=hbar=1"

    def test_custom_convention(self):
        problem = _make_problem(problem_statement="# ASSERT_CONVENTION: my_custom_key=my_value\nDo work.")
        lock = _extract_convention_lock(problem)
        assert lock.custom_conventions.get("my_custom_key") == "my_value"


# --- convention_lock_consistency_check ---


class TestConventionLockConsistencyCheck:
    def test_no_config_lock_returns_problem_lock(self):
        problem = _make_problem(problem_statement="# ASSERT_CONVENTION: metric_signature=mostly-plus\nZ = ...")
        lock = convention_lock_consistency_check(problem, config_lock=None)
        assert lock.metric_signature == "mostly-plus"

    def test_empty_config_lock_returns_problem_lock(self):
        problem = _make_problem(problem_statement="# ASSERT_CONVENTION: natural_units=natural\nZ = ...")
        lock = convention_lock_consistency_check(problem, config_lock={})
        assert lock.natural_units == "natural"

    def test_config_override_on_conflict(self):
        problem = _make_problem(problem_statement="# ASSERT_CONVENTION: metric_signature=mostly-plus\nZ = ...")
        lock = convention_lock_consistency_check(problem, config_lock={"metric_signature": "(-,+,+,+)"})
        assert lock.metric_signature == "(-,+,+,+)"

    def test_config_adds_missing_field(self):
        problem = _make_problem()
        lock = convention_lock_consistency_check(problem, config_lock={"fourier_convention": "physics"})
        assert lock.fourier_convention == "physics"

    def test_no_conflict_when_values_agree(self, caplog):
        problem = _make_problem(problem_statement="# ASSERT_CONVENTION: natural_units=natural\nZ = ...")
        with caplog.at_level("WARNING"):
            lock = convention_lock_consistency_check(problem, config_lock={"natural_units": "natural"})
        assert lock.natural_units == "natural"
        assert "convention_lock_conflict" not in caplog.text

    def test_conflict_logs_warning(self, caplog):
        problem = _make_problem(problem_statement="# ASSERT_CONVENTION: metric_signature=mostly-plus\nZ = ...")
        with caplog.at_level("WARNING", logger="gpd.strategy.mcts"):
            lock = convention_lock_consistency_check(problem, config_lock={"metric_signature": "mostly-minus"})
        assert lock.metric_signature == "mostly-minus"
        assert "convention_lock_conflict" in caplog.text

    def test_custom_convention_override(self):
        problem = _make_problem(problem_statement="# ASSERT_CONVENTION: my_key=val_a\nZ = ...")
        lock = convention_lock_consistency_check(problem, config_lock={"my_key": "val_b"})
        assert lock.custom_conventions["my_key"] == "val_b"

    def test_empty_config_values_skipped(self):
        problem = _make_problem(problem_statement="# ASSERT_CONVENTION: metric_signature=mostly-plus\nZ = ...")
        lock = convention_lock_consistency_check(
            problem, config_lock={"metric_signature": "", "fourier_convention": "  "}
        )
        assert lock.metric_signature == "mostly-plus"
        assert lock.fourier_convention is None

    def test_mixed_sources_merge(self):
        problem = _make_problem(
            problem_statement="# ASSERT_CONVENTION: metric_signature=mostly-plus\nZ = ...",
            hard_constraints=["# ASSERT_CONVENTION: natural_units=natural"],
        )
        lock = convention_lock_consistency_check(
            problem,
            config_lock={"fourier_convention": "physics", "gauge_choice": "Lorenz"},
        )
        assert lock.metric_signature == "mostly-plus"
        assert lock.natural_units == "natural"
        assert lock.fourier_convention == "physics"
        assert lock.gauge_choice == "Lorenz"


# --- _infer_domain ---


class TestInferDomain:
    def test_none_domain(self):
        problem = _make_problem(domain=None)
        assert _infer_domain(problem) is None

    def test_with_domain(self):
        from psi_contracts.common import PhysicsDomain

        problem = _make_problem(domain=PhysicsDomain.CONDENSED_MATTER)
        assert _infer_domain(problem) == "condensed_matter"


# --- _parse_error_classes_from_markdown ---


class TestParseErrorClassesFromMarkdown:
    def test_empty_content(self):
        assert _parse_error_classes_from_markdown("") == []

    def test_valid_table(self):
        content = (
            "| ID | Name | Description | Detection | Example | Domains |\n"
            "| --- | --- | --- | --- | --- | --- |\n"
            "| 1 | Sign error | Wrong sign in expression | Check sign conventions | exp(+i omega t) | qft, condensed_matter |\n"
            "| 2 | Missing 2pi | Forgot 2pi factor | Check Fourier transform | | general |\n"
        )
        errors = _parse_error_classes_from_markdown(content)
        assert len(errors) == 2
        assert errors[0].id == 1
        assert errors[0].name == "Sign error"
        assert "qft" in errors[0].domains
        assert errors[1].id == 2
        assert errors[1].example == ""

    def test_no_table_rows(self):
        content = "# Error Catalog\n\nSome text without any table rows.\n"
        assert _parse_error_classes_from_markdown(content) == []


# --- _resolve_gpd_mcp_tools ---


class TestResolveGPDMCPTools:
    """Tests for _resolve_gpd_mcp_tools using StrategyParams (gpd_* fields)."""

    def _make_params(self, **overrides) -> StrategyParams:
        defaults = {
            "gpd_enabled": True,
            "gpd_conventions": True,
            "gpd_verification": True,
            "gpd_protocols": True,
            "gpd_errors": True,
            "gpd_patterns": True,
            "gpd_state": True,
            "gpd_skills": True,
        }
        defaults.update(overrides)
        return StrategyParams(**defaults)

    def test_basic_tools(self):
        params = self._make_params()
        tools = _resolve_gpd_mcp_tools(params, [])
        assert "gpd-conventions" in tools
        assert "gpd-verification" in tools
        assert "gpd-state" in tools
        assert "gpd-skills" in tools
        assert "gpd-blackboard" in tools

    def test_disabled_flags_excluded(self):
        params = self._make_params(gpd_conventions=False, gpd_protocols=False)
        tools = _resolve_gpd_mcp_tools(params, [])
        assert "gpd-conventions" not in tools
        assert "gpd-protocols" not in tools
        assert "gpd-verification" in tools

    def test_deduplication(self):
        params = self._make_params()
        tools = _resolve_gpd_mcp_tools(params, ["gpd-conventions"])
        assert tools.count("gpd-conventions") == 0
        assert "gpd-verification" in tools

    def test_all_existing_returns_only_new(self):
        params = self._make_params()
        existing = [
            "gpd-conventions",
            "gpd-verification",
            "gpd-protocols",
            "gpd-errors",
            "gpd-patterns",
            "gpd-state",
            "gpd-skills",
            "gpd-blackboard",
        ]
        tools = _resolve_gpd_mcp_tools(params, existing)
        assert tools == []


# --- _run_invariant_checks ---


class TestRunInvariantChecks:
    def test_no_checks(self):
        assert _run_invariant_checks([], "x = 1") == []

    def test_passing_check(self):
        check = MagicMock(return_value=[])
        assert _run_invariant_checks([check], "x = 1") == []
        check.assert_called_once()

    def test_failing_check(self):
        check = MagicMock(return_value=["violation: sign mismatch"])
        violations = _run_invariant_checks([check], "x = 1")
        assert len(violations) == 1
        assert "sign mismatch" in violations[0]

    def test_multiple_checks(self):
        check1 = MagicMock(return_value=["v1"])
        check2 = MagicMock(return_value=[])
        check3 = MagicMock(return_value=["v2", "v3"])
        violations = _run_invariant_checks([check1, check2, check3], "x = 1")
        assert len(violations) == 3

    def test_non_list_result_ignored(self):
        check = MagicMock(return_value="not a list")
        violations = _run_invariant_checks([check], "x = 1")
        assert violations == []


# --- GPDMCTSStrategy ---


class TestGPDMCTSStrategy:
    """Tests for the full strategy, mocking MCTSStrategy.solve."""

    @pytest.fixture()
    def strategy(self):
        return GPDMCTSStrategy()

    @pytest.fixture()
    def mock_mcts_solve(self):
        """Patch MCTSStrategy.solve to yield a single Run."""
        run = _make_run()

        async def _mock_solve(*args, **kwargs) -> AsyncIterator[Run]:
            yield run

        with patch.object(
            __import__("pipeline.strategies.mcts", fromlist=["MCTSStrategy"]).MCTSStrategy,
            "solve",
            side_effect=_mock_solve,
        ) as mock:
            mock._test_run = run
            yield mock

    async def test_gpd_disabled_delegates_directly(self, strategy, mock_mcts_solve):
        config = _make_config(gpd_enabled=False)
        problem = _make_problem()
        verifier = _make_verifier()
        memory = _make_memory()
        events = _make_events()
        caps = _make_capabilities()

        runs = []
        async for run in strategy.solve(
            problem=problem,
            verifier=verifier,
            capabilities=caps,
            config=config,
            memory=memory,
            events=events,
        ):
            runs.append(run)

        assert len(runs) == 1
        mock_mcts_solve.assert_called_once()

    async def test_gpd_enabled_emits_events(self, strategy, mock_mcts_solve):
        config = _make_config(gpd_enabled=True)
        problem = _make_problem()
        verifier = _make_verifier()
        memory = _make_memory()
        events = _make_events()
        caps = _make_capabilities()

        runs = []
        async for run in strategy.solve(
            problem=problem,
            verifier=verifier,
            capabilities=caps,
            config=config,
            memory=memory,
            events=events,
        ):
            runs.append(run)

        assert len(runs) == 1

        # Check GPD-specific events were emitted
        event_types = [call.args[0] for call in events.emit.call_args_list]
        assert "gpd_strategy_started" in event_types
        assert "gpd_strategy_completed" in event_types

    async def test_gpd_records_convention_lock_hypothesis(self, strategy, mock_mcts_solve):
        config = _make_config(gpd_enabled=True)
        problem = _make_problem(problem_statement="# ASSERT_CONVENTION: metric_signature=mostly-plus\nZ = ...")
        verifier = _make_verifier()
        memory = _make_memory()
        events = _make_events()
        caps = _make_capabilities()

        runs = []
        async for run in strategy.solve(
            problem=problem,
            verifier=verifier,
            capabilities=caps,
            config=config,
            memory=memory,
            events=events,
        ):
            runs.append(run)

        # Memory should have recorded the convention lock
        memory.record_hypothesis.assert_called_once()
        hypo = memory.record_hypothesis.call_args[0][0]
        assert hypo["type"] == "gpd_convention_lock"
        assert hypo["convention_lock"]["metric_signature"] == "mostly-plus"

    async def test_gpd_mcp_tools_injected(self, strategy, mock_mcts_solve):
        config = _make_config(gpd_enabled=True)
        problem = _make_problem()
        verifier = _make_verifier()
        memory = _make_memory()
        events = _make_events()
        caps = _make_capabilities()

        runs = []
        async for run in strategy.solve(
            problem=problem,
            verifier=verifier,
            capabilities=caps,
            config=config,
            memory=memory,
            events=events,
        ):
            runs.append(run)

        # The MCTSStrategy.solve call should have enriched mcp_tools
        call_kwargs = mock_mcts_solve.call_args
        passed_config = call_kwargs.kwargs.get("config") or call_kwargs[1].get("config")
        if passed_config:
            assert "gpd-conventions" in passed_config.strategy_params.mcp_tools

    async def test_invariant_violations_emitted(self, strategy):
        """When invariant checks find violations, events should be emitted."""
        run = _make_run(solution_text="# ASSERT_CONVENTION: metric_signature=mostly-minus\ndiag(+,-,-,-)")

        async def _mock_solve(*args, **kwargs) -> AsyncIterator[Run]:
            yield run

        config = _make_config(gpd_enabled=True, gpd_conventions=True)
        problem = _make_problem(problem_statement="# ASSERT_CONVENTION: metric_signature=mostly-plus\nZ = ...")
        verifier = _make_verifier()
        memory = _make_memory()
        events = _make_events()
        caps = _make_capabilities()

        with patch.object(
            __import__("pipeline.strategies.mcts", fromlist=["MCTSStrategy"]).MCTSStrategy,
            "solve",
            side_effect=_mock_solve,
        ):
            runs = []
            async for r in strategy.solve(
                problem=problem,
                verifier=verifier,
                capabilities=caps,
                config=config,
                memory=memory,
                events=events,
            ):
                runs.append(r)

        # Should have emitted gpd_invariant_violations event
        event_types = [call.args[0] for call in events.emit.call_args_list]
        assert "gpd_invariant_violations" in event_types
