"""Full-chain integration test for GPDMCTSStrategy after unification.

Verifies the entire GPD strategy stack can be instantiated and would
run correctly with mocked LLM calls. Covers:

1. Import from gpd.strategy.api
2. All provider classes instantiate
3. Convention lock extraction
4. Invariant check creation
5. MCP tool resolution (resolve_gpd_tools)
6. Blackboard adapter
7. Reference loader finds files in gpd.specs
8. Full GPDMCTSStrategy.solve() with mocked MCTSStrategy
"""

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
from psi_contracts.gpd import ConventionLock, ErrorClass
from psi_contracts.solving import CandidateSolution, Run

# ── 1. Import from gpd.strategy.api ─────────────────────────────────────────


class TestAPIImports:
    """Verify all public symbols import from gpd.strategy.api."""

    def test_strategy_import(self):
        from gpd.strategy.api import GPDMCTSStrategy

        assert GPDMCTSStrategy is not None

    def test_provider_imports(self):
        from gpd.strategy.api import (
            BlackboardStoreAdapter,
            BundleLoader,
            PhaseConfigProvider,
            PhysicsCurator,
            PhysicsRubricProvider,
            PhysicsTriageContext,
            ReferenceLoader,
            ReferenceRouter,
            WriteGateAdapter,
        )

        assert all(
            cls is not None
            for cls in [
                BundleLoader,
                PhysicsTriageContext,
                PhysicsRubricProvider,
                PhysicsCurator,
                PhaseConfigProvider,
                WriteGateAdapter,
                BlackboardStoreAdapter,
                ReferenceLoader,
                ReferenceRouter,
            ]
        )

    def test_factory_imports(self):
        from gpd.strategy.api import (
            create_gpd_invariant_checks,
            detect_phase,
            get_infra_dir,
            get_loader,
            get_router,
            load_phase_configs,
        )

        assert all(
            fn is not None
            for fn in [
                create_gpd_invariant_checks,
                get_loader,
                get_router,
                detect_phase,
                load_phase_configs,
                get_infra_dir,
            ]
        )

    def test_bundle_imports(self):
        from gpd.strategy.api import (
            ActionSpec,
            ActorSpec,
            Bundle,
            BundleManifest,
            MergedBundle,
            SkillEntry,
            get_bundle_loader,
            init_bundle_loader,
            load_bundle,
            merge_bundles,
            resolve_placeholders,
        )

        assert all(
            sym is not None
            for sym in [
                ActionSpec,
                ActorSpec,
                Bundle,
                BundleManifest,
                MergedBundle,
                SkillEntry,
                get_bundle_loader,
                init_bundle_loader,
                load_bundle,
                merge_bundles,
                resolve_placeholders,
            ]
        )

    def test_error_imports(self):
        from gpd.strategy.api import BundleError, GPDError, LoaderError

        assert all(cls is not None for cls in [GPDError, BundleError, LoaderError])

    def test_type_bridge_imports(self):
        from gpd.strategy.api import BlackboardStoreAdapter, WriteGateAdapter, dict_to_engine_entry

        assert all(sym is not None for sym in [BlackboardStoreAdapter, WriteGateAdapter, dict_to_engine_entry])


# ── 2. Provider instantiation ────────────────────────────────────────────────


class TestProviderInstantiation:
    """Verify all provider classes can be instantiated without error."""

    def test_physics_rubric_provider(self):
        from gpd.strategy.api import PhysicsRubricProvider

        provider = PhysicsRubricProvider()
        assert provider is not None

        # Verify it produces a rubric
        rubric = provider.build_rubric(None)
        assert rubric is not None
        assert len(rubric.criteria) == 5

        # Physics-enriched rubric
        physics_rubric = provider.build_rubric("qft")
        assert len(physics_rubric.criteria) == 10

    def test_phase_config_provider(self):
        from gpd.strategy.api import PhaseConfigProvider

        provider = PhaseConfigProvider()
        assert provider is not None
        assert provider.last_phase is None

        configs = provider.configs
        assert "formulation" in configs
        assert "derivation" in configs
        assert "validation" in configs

    def test_phase_config_provider_get_overrides(self):
        from gpd.strategy.api import PhaseConfigProvider

        provider = PhaseConfigProvider()

        # Early stage → formulation
        overrides = provider.get_overrides({"budget_fraction_remaining": 0.9, "avg_score": 0.0, "node_count": 2})
        assert overrides is not None
        assert "c_puct" in overrides
        assert provider.last_phase == "formulation"

        # Same phase again → None (no change)
        same = provider.get_overrides({"budget_fraction_remaining": 0.85, "avg_score": 0.0, "node_count": 3})
        assert same is None

    def test_physics_curator_instantiation(self):
        from gpd.strategy.api import PhysicsCurator

        curator = PhysicsCurator(model_id="anthropic:claude-haiku-4-5-20251001")
        assert curator is not None

    def test_write_gate_adapter_instantiation(self):
        from gpd.strategy.api import PhysicsCurator, WriteGateAdapter

        curator = PhysicsCurator(model_id="anthropic:claude-haiku-4-5-20251001")
        adapter = WriteGateAdapter(curator)
        assert adapter is not None

    def test_bundle_loader_instantiation(self):
        from gpd.strategy.api import BundleLoader

        loader = BundleLoader()
        assert loader is not None

    def test_bundle_loader_load_base(self):
        from gpd.strategy.api import BundleLoader

        loader = BundleLoader()
        loader.load(base_name="base")
        merged = loader.merged
        assert merged is not None
        assert len(merged.actions) > 0
        assert len(merged.actors) > 0

    def test_bundle_loader_load_physics_overlay(self):
        from gpd.strategy.api import BundleLoader

        loader = BundleLoader()
        loader.load(base_name="base", overlay_names=["physics"])
        merged = loader.merged
        assert merged is not None
        # Physics overlay should add/modify actions
        assert "PhysicsWork" in merged.actions or "Work" in merged.actions

    def test_triage_context_instantiation(self):
        from gpd.strategy.api import BundleLoader, PhysicsTriageContext, ReferenceLoader, ReferenceRouter

        # Build required dependencies
        loader = BundleLoader()
        loader.load(base_name="base", overlay_names=["physics"])
        ref_loader = ReferenceLoader()
        ref_loader.build_index()
        router = ReferenceRouter(ref_loader)

        triage = PhysicsTriageContext(bundle_loader=loader, reference_router=router, domain="qft")
        assert triage is not None

        # Verify it builds context
        context = triage.build_context(
            state={"convention_lock": {"metric_signature": "mostly-plus"}},
            node_id="test-node",
            dag_stats={"budget_fraction_remaining": 0.8, "avg_score": 0.1, "total_visits": 3},
        )
        assert "mode_descriptions" in context
        assert "phase_signal" in context
        assert context["phase_signal"]["phase"] == "formulation"


# ── 3. Convention lock extraction ────────────────────────────────────────────


class TestConventionLockFullChain:
    """Verify convention lock extraction and consistency check work end-to-end."""

    def test_extract_from_problem_with_assertions(self):
        from gpd.strategy.mcts import _extract_convention_lock

        problem = FormalProblem(
            title="QFT Problem",
            objective="Calculate scattering amplitude",
            system_setup="4D QFT",
            evaluation_summary="Check unitarity",
            problem_statement=(
                "# ASSERT_CONVENTION: metric_signature=mostly-minus\n"
                "# ASSERT_CONVENTION: fourier_convention=physics\n"
                "Calculate the tree-level amplitude."
            ),
        )
        lock = _extract_convention_lock(problem)
        assert lock.metric_signature == "mostly-minus"
        assert lock.fourier_convention == "physics"

    def test_convention_lock_consistency_merge(self):
        from gpd.strategy.mcts import convention_lock_consistency_check

        problem = FormalProblem(
            title="Test",
            objective="Test",
            system_setup="Test",
            evaluation_summary="Test",
            problem_statement="# ASSERT_CONVENTION: metric_signature=mostly-plus\nDo work.",
            hard_constraints=["# ASSERT_CONVENTION: natural_units=c=hbar=1"],
        )
        lock = convention_lock_consistency_check(
            problem,
            config_lock={
                "gauge_choice": "Lorenz",
                "regularization_scheme": "dim-reg",
            },
        )
        assert lock.metric_signature == "mostly-plus"
        assert lock.natural_units == "c=hbar=1"
        assert lock.gauge_choice == "Lorenz"
        assert lock.regularization_scheme == "dim-reg"


# ── 4. Invariant check creation ──────────────────────────────────────────────


class TestInvariantCheckCreation:
    """Verify CommitGate invariant checks are created and function correctly."""

    def test_create_checks_with_conventions(self):
        from gpd.strategy.api import create_gpd_invariant_checks

        lock = ConventionLock(metric_signature="mostly-plus")
        checks = create_gpd_invariant_checks(lock, [])
        assert len(checks) == 1  # convention check only, no error catalog

    def test_create_checks_with_error_catalog(self):
        from gpd.strategy.api import create_gpd_invariant_checks

        lock = ConventionLock(metric_signature="mostly-plus")
        catalog = [
            ErrorClass(
                id=1,
                name="Sign error in exponential",
                description="Wrong sign in exp(i omega t)",
                detection_strategy="Check Fourier convention",
                example="exp(+i omega t) vs exp(-i omega t)",
                domains=["qft"],
            ),
        ]
        checks = create_gpd_invariant_checks(lock, catalog)
        assert len(checks) == 2  # convention + physics

    def test_convention_check_detects_mismatch(self):
        from gpd.strategy.api import create_gpd_invariant_checks

        lock = ConventionLock(metric_signature="mostly-plus")
        checks = create_gpd_invariant_checks(lock, [])

        # Payload with wrong metric signature
        payload = {
            "solution": {"text": "# ASSERT_CONVENTION: metric_signature=mostly-minus\nUsing diag(+,-,-,-) metric."}
        }
        violations = checks[0](payload, {})
        assert len(violations) > 0
        assert any("metric_signature" in v for v in violations)

    def test_convention_check_passes_correct(self):
        from gpd.strategy.api import create_gpd_invariant_checks

        lock = ConventionLock(metric_signature="mostly-plus")
        checks = create_gpd_invariant_checks(lock, [])

        payload = {
            "solution": {"text": "# ASSERT_CONVENTION: metric_signature=mostly-plus\nUsing diag(-,+,+,+) metric."}
        }
        violations = checks[0](payload, {})
        assert violations == []

    def test_empty_lock_creates_no_checks(self):
        from gpd.strategy.api import create_gpd_invariant_checks

        lock = ConventionLock()
        checks = create_gpd_invariant_checks(lock, [])
        assert len(checks) == 0


# ── 5. MCP tool resolution ───────────────────────────────────────────────────


class TestMCPToolResolution:
    """Verify resolve_gpd_tools derives correct MCP tool names."""

    def test_all_tools_enabled(self):
        from agentic_builder.tools.manifest import resolve_gpd_tools

        params = StrategyParams(
            gpd_enabled=True,
            gpd_conventions=True,
            gpd_verification=True,
            gpd_protocols=True,
            gpd_errors=True,
            gpd_patterns=True,
            gpd_state=True,
            gpd_skills=True,
            gpd_blackboard=True,
        )
        tools = resolve_gpd_tools(params)
        expected = {
            "gpd-conventions",
            "gpd-verification",
            "gpd-protocols",
            "gpd-errors",
            "gpd-patterns",
            "gpd-state",
            "gpd-skills",
            "gpd-blackboard",
        }
        assert set(tools) == expected

    def test_gpd_disabled_returns_empty(self):
        from agentic_builder.tools.manifest import resolve_gpd_tools

        params = StrategyParams(gpd_enabled=False)
        tools = resolve_gpd_tools(params)
        assert tools == []

    def test_selective_flags(self):
        from agentic_builder.tools.manifest import resolve_gpd_tools

        params = StrategyParams(
            gpd_enabled=True,
            gpd_conventions=True,
            gpd_verification=False,
            gpd_protocols=False,
        )
        tools = resolve_gpd_tools(params)
        assert "gpd-conventions" in tools
        assert "gpd-verification" not in tools
        assert "gpd-protocols" not in tools

    def test_strategy_mcts_tool_injection(self):
        """Verify _resolve_gpd_mcp_tools deduplicates against existing tools."""
        from gpd.strategy.mcts import _resolve_gpd_mcp_tools

        params = StrategyParams(gpd_enabled=True, gpd_conventions=True, gpd_verification=True)
        new_tools = _resolve_gpd_mcp_tools(params, ["gpd-conventions"])
        assert "gpd-conventions" not in new_tools
        assert "gpd-verification" in new_tools


# ── 6. Blackboard adapter ────────────────────────────────────────────────────


class TestBlackboardAdapter:
    """Verify BlackboardStoreAdapter bridges engine protocols correctly."""

    def test_adapter_instantiation(self):
        from gpd.strategy.api import BlackboardStoreAdapter

        store = MagicMock()
        adapter = BlackboardStoreAdapter(store, campaign_id="test-campaign")
        assert adapter is not None

    def test_adapter_query(self):
        from gpd.strategy.api import BlackboardStoreAdapter

        store = MagicMock()
        store.query_nodes = MagicMock(
            return_value=[
                {
                    "node_id": "n1",
                    "node_type": "insight",
                    "content": "Symmetry found: SU(2)",
                    "tags": '["symmetry", "su2"]',
                    "confidence": 0.9,
                    "branch_node_id": "b1",
                },
            ]
        )
        adapter = BlackboardStoreAdapter(store)
        results = adapter.query(tags=["symmetry"])
        assert len(results) == 1
        assert results[0].entry_id == "n1"
        assert results[0].kind == "insight"
        assert results[0].confidence == 0.9

    def test_adapter_get(self):
        from gpd.strategy.api import BlackboardStoreAdapter

        store = MagicMock()
        store.get_node = MagicMock(
            return_value={
                "node_id": "n2",
                "node_type": "equation",
                "content": "E = mc^2",
                "tags": '["energy", "relativity"]',
                "confidence": 1.0,
                "branch_node_id": "",
            }
        )
        adapter = BlackboardStoreAdapter(store)
        entry = adapter.get("n2")
        assert entry is not None
        assert entry.content == "E = mc^2"

    def test_adapter_get_missing(self):
        from gpd.strategy.api import BlackboardStoreAdapter

        store = MagicMock()
        store.get_node = MagicMock(return_value=None)
        adapter = BlackboardStoreAdapter(store)
        assert adapter.get("nonexistent") is None

    def test_adapter_search(self):
        from gpd.strategy.api import BlackboardStoreAdapter

        store = MagicMock()
        store.search_text = MagicMock(return_value=[])
        adapter = BlackboardStoreAdapter(store)
        results = adapter.search("symmetry")
        assert results == []
        store.search_text.assert_called_once_with("symmetry", limit=10)

    def test_adapter_request_write(self):
        from agentic_builder.engine.blackboard_protocol import BlackboardWriteRequest

        from gpd.strategy.api import BlackboardStoreAdapter

        store = MagicMock()
        store.add_node = MagicMock()
        adapter = BlackboardStoreAdapter(store)

        request = BlackboardWriteRequest(
            kind="insight",
            content="Conservation of angular momentum holds",
            tags=["conservation", "angular-momentum"],
            confidence=0.85,
        )
        entry_id = adapter.request_write(request)
        assert entry_id is not None
        store.add_node.assert_called_once()

    def test_type_bridge_dict_to_engine(self):
        from gpd.strategy.api import dict_to_engine_entry

        row = {
            "node_id": "abc",
            "node_type": "hypothesis",
            "content": "The coupling constant runs",
            "tags": '["rg", "coupling"]',
            "confidence": 0.7,
            "branch_node_id": "branch-1",
        }
        entry = dict_to_engine_entry(row)
        assert entry.entry_id == "abc"
        assert entry.kind == "hypothesis"
        assert entry.tags == ["rg", "coupling"]
        assert entry.confidence == 0.7


# ── 7. Reference loader finds files in gpd.specs ────────────────────────────


class TestReferenceLoader:
    """Verify the reference loader can find and index files in gpd.specs."""

    def test_loader_builds_index(self):
        from gpd.strategy.api import ReferenceLoader

        loader = ReferenceLoader()
        loader.build_index()
        assert loader._built is True
        assert len(loader._index) > 0

    def test_loader_finds_protocol_references(self):
        from gpd.strategy.api import ReferenceLoader

        loader = ReferenceLoader()
        loader.build_index()
        # Should find protocol files like perturbation-theory, renormalization-group, etc.
        protocol_refs = [name for name in loader._index if name.startswith("protocols/")]
        assert len(protocol_refs) > 0

    def test_reference_router_routes_domain(self):
        from gpd.strategy.api import ReferenceLoader, ReferenceRouter

        loader = ReferenceLoader()
        loader.build_index()
        router = ReferenceRouter(loader)

        # Route a computation type to a protocol
        protocol = router.route_protocol("perturbation")
        assert protocol is not None

    def test_get_loader_singleton(self):
        from gpd.strategy.api import get_loader

        # Clear LRU cache to avoid state leakage
        get_loader.cache_clear()
        loader = get_loader()
        assert loader is not None
        assert loader._built is True

    def test_specs_dir_exists(self):
        from gpd.specs import SPECS_DIR

        assert SPECS_DIR.is_dir()
        assert (SPECS_DIR / "references").is_dir()
        assert (SPECS_DIR / "base").is_dir()
        assert (SPECS_DIR / "physics").is_dir()

    def test_infra_dir_exists(self):
        from gpd.strategy.api import get_infra_dir

        infra = get_infra_dir()
        assert infra.is_dir()
        # Should contain MCP server configs
        json_files = list(infra.glob("*.json"))
        assert len(json_files) > 0

    def test_key_reference_files_exist(self):
        from gpd.specs import SPECS_DIR

        key_files = [
            SPECS_DIR / "physics" / "agents" / "curator.md",
            SPECS_DIR / "physics" / "config" / "phase_defaults.yaml",
            SPECS_DIR / "physics" / "schemas" / "payload_overlay.json",
            SPECS_DIR / "base" / "bundle.yaml",
            SPECS_DIR / "physics" / "bundle.yaml",
        ]
        for f in key_files:
            assert f.is_file(), f"Missing key reference file: {f}"

    def test_error_catalog_files_exist(self):
        from gpd.specs import SPECS_DIR

        errors_dir = SPECS_DIR / "physics" / "errors"
        assert errors_dir.is_dir()
        yaml_files = list(errors_dir.glob("*.yaml"))
        assert len(yaml_files) > 0


# ── 8. Full strategy solve() with mocked MCTSStrategy ───────────────────────


def _make_problem(**kwargs: object) -> FormalProblem:
    defaults: dict[str, object] = {
        "title": "Full Chain Test",
        "objective": "Verify end-to-end GPD campaign",
        "system_setup": "2D Ising model on a lattice",
        "evaluation_summary": "Check thermodynamic limits",
        "problem_statement": (
            "# ASSERT_CONVENTION: metric_signature=mostly-plus\n"
            "# ASSERT_CONVENTION: natural_units=c=hbar=1\n"
            "Calculate the partition function for the 2D Ising model."
        ),
        "domain": None,
    }
    defaults.update(kwargs)
    return FormalProblem(**defaults)


def _make_config(gpd_enabled: bool = True, **gpd_kwargs: object) -> CampaignConfig:
    sp_kwargs: dict[str, object] = {"gpd_enabled": gpd_enabled}
    sp_kwargs.update(gpd_kwargs)
    return CampaignConfig(strategy_params=StrategyParams(**sp_kwargs))


def _make_run(score: float = 75.0, solution_text: str = "Z = sum_sigma exp(-beta H)") -> Run:
    return Run(
        id=uuid4(),
        campaign_id=uuid4(),
        sequence_number=1,
        score=Score(value=score),
        cost_usd=0.01,
        duration_seconds=1.0,
        solution=CandidateSolution(
            summary="Partition function calculation",
            approach_description="Transfer matrix method",
            code=solution_text,
        ),
        summary="Ising partition function",
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


class TestFullChainSolve:
    """End-to-end test: GPDMCTSStrategy.solve() with mocked LLM calls."""

    @pytest.fixture()
    def strategy(self):
        from gpd.strategy.api import GPDMCTSStrategy

        return GPDMCTSStrategy()

    @pytest.fixture()
    def mock_mcts_solve(self):
        """Patch MCTSStrategy.solve to yield a single run."""
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

    async def test_full_chain_gpd_enabled(self, strategy, mock_mcts_solve):
        """Full chain: GPD enabled → convention lock, MCP tools, providers, invariant checks."""
        config = _make_config(gpd_enabled=True)
        problem = _make_problem()
        verifier = Verifier(code="def verify(s): return 0.8")
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

        # Verify runs were yielded
        assert len(runs) == 1

        # Verify GPD lifecycle events were emitted
        event_types = [call.args[0] for call in events.emit.call_args_list]
        assert "gpd_strategy_started" in event_types
        assert "gpd_providers_configured" in event_types
        assert "gpd_strategy_completed" in event_types

        # Verify convention lock was recorded in memory
        memory.record_hypothesis.assert_called_once()
        hypo = memory.record_hypothesis.call_args[0][0]
        assert hypo["type"] == "gpd_convention_lock"
        assert hypo["convention_lock"]["metric_signature"] == "mostly-plus"
        assert hypo["convention_lock"]["natural_units"] == "c=hbar=1"

    async def test_full_chain_mcp_tools_injected(self, strategy, mock_mcts_solve):
        """Verify MCP tool names are injected into the config passed to MCTSStrategy."""
        config = _make_config(gpd_enabled=True)
        problem = _make_problem()
        verifier = Verifier(code="def verify(s): return 0.8")
        memory = _make_memory()
        events = _make_events()
        caps = _make_capabilities()

        async for _run in strategy.solve(
            problem=problem,
            verifier=verifier,
            capabilities=caps,
            config=config,
            memory=memory,
            events=events,
        ):
            pass

        # MCTSStrategy.solve was called with enriched config
        call_kwargs = mock_mcts_solve.call_args
        passed_config = call_kwargs.kwargs.get("config") or call_kwargs[1].get("config")
        if passed_config:
            mcp_tools = passed_config.strategy_params.mcp_tools
            assert "gpd-conventions" in mcp_tools
            assert "gpd-verification" in mcp_tools

    async def test_full_chain_providers_passed_to_mcts(self, strategy, mock_mcts_solve):
        """Verify provider dict is passed through to MCTSStrategy.solve."""
        config = _make_config(gpd_enabled=True)
        problem = _make_problem()
        verifier = Verifier(code="def verify(s): return 0.8")
        memory = _make_memory()
        events = _make_events()
        caps = _make_capabilities()

        async for _run in strategy.solve(
            problem=problem,
            verifier=verifier,
            capabilities=caps,
            config=config,
            memory=memory,
            events=events,
        ):
            pass

        call_kwargs = mock_mcts_solve.call_args
        providers = call_kwargs.kwargs.get("providers")
        assert providers is not None
        assert "rubric_provider" in providers
        assert "phase_config_provider" in providers
        assert "write_gate_provider" in providers

    async def test_full_chain_gpd_disabled_fast_path(self, strategy, mock_mcts_solve):
        """When GPD disabled, delegates directly without enrichment."""
        config = _make_config(gpd_enabled=False)
        problem = _make_problem()
        verifier = Verifier(code="def verify(s): return 0.8")
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

        # No GPD events emitted
        event_types = [call.args[0] for call in events.emit.call_args_list]
        assert "gpd_strategy_started" not in event_types

        # Memory should NOT have recorded convention lock
        memory.record_hypothesis.assert_not_called()

    async def test_full_chain_invariant_violation_detected(self, strategy):
        """When solution violates conventions, invariant violations are emitted."""
        # Solution that contradicts the convention lock
        violation_text = (
            "# ASSERT_CONVENTION: metric_signature=mostly-minus\nUsing diag(+,-,-,-) metric for the calculation."
        )
        run = _make_run(solution_text=violation_text)

        async def _mock_solve(*args, **kwargs) -> AsyncIterator[Run]:
            yield run

        config = _make_config(gpd_enabled=True)
        problem = _make_problem()
        verifier = Verifier(code="def verify(s): return 0.8")
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

        assert len(runs) == 1

        # Should have emitted invariant violation event
        event_types = [call.args[0] for call in events.emit.call_args_list]
        assert "gpd_invariant_violations" in event_types

    async def test_full_chain_no_domain_still_works(self, strategy, mock_mcts_solve):
        """Strategy works even when FormalProblem has no physics domain."""
        config = _make_config(gpd_enabled=True)
        problem = _make_problem(domain=None, problem_statement="Just a generic problem.")
        verifier = Verifier(code="def verify(s): return 0.8")
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
        event_types = [call.args[0] for call in events.emit.call_args_list]
        assert "gpd_strategy_completed" in event_types


# ── 9. Cross-layer type bridge round-trip ────────────────────────────────────


class TestTypeBridgeRoundTrip:
    """Verify engine ↔ contract type conversions are lossless where expected."""

    def test_engine_entry_roundtrip(self):
        from agentic_builder.engine.blackboard_protocol import BlackboardEntry as EngineEntry

        from gpd.strategy.api import contract_entry_to_engine, engine_entry_to_contract

        original = EngineEntry(
            entry_id="e1",
            kind="symmetry",
            content="SU(3) gauge symmetry",
            tags=["gauge", "su3"],
            source_branch="branch-42",
            confidence=0.95,
        )
        contract = engine_entry_to_contract(original)
        roundtripped = contract_entry_to_engine(contract)

        assert roundtripped.entry_id == original.entry_id
        assert roundtripped.kind == original.kind
        assert roundtripped.content == original.content
        assert roundtripped.tags == original.tags
        assert roundtripped.confidence == original.confidence

    def test_curation_decision_roundtrip(self):
        from agentic_builder.engine.blackboard_protocol import CurationDecision as EngineDecision

        from gpd.strategy.api import contract_decision_to_engine, engine_decision_to_contract

        original = EngineDecision(approved=True, reason="Well-supported by calculation")
        contract = engine_decision_to_contract(original)
        roundtripped = contract_decision_to_engine(contract)

        assert roundtripped.approved == original.approved
        assert roundtripped.reason == original.reason


# ── 10. Phase detection ──────────────────────────────────────────────────────


class TestPhaseDetectionIntegration:
    """Verify phase detection integrates with phase config provider."""

    def test_phase_progression(self):
        from gpd.strategy.api import PhaseConfigProvider, detect_phase

        provider = PhaseConfigProvider()

        # Formulation phase
        assert detect_phase({"budget_fraction_remaining": 0.9, "avg_score": 0.0, "node_count": 3}) == "formulation"

        # Derivation phase
        assert detect_phase({"budget_fraction_remaining": 0.5, "avg_score": 0.3, "node_count": 15}) == "derivation"

        # Validation phase
        assert detect_phase({"budget_fraction_remaining": 0.2, "avg_score": 0.7, "node_count": 30}) == "validation"

        # Provider tracks transitions
        provider.get_overrides({"budget_fraction_remaining": 0.9, "avg_score": 0.0, "node_count": 3})
        assert provider.last_phase == "formulation"

        provider.get_overrides({"budget_fraction_remaining": 0.2, "avg_score": 0.7, "node_count": 30})
        assert provider.last_phase == "validation"
