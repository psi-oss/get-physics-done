"""Edge case tests for GPD strategy and MCP layers.

Tests:
1. GPDMCTSStrategy with gpd_enabled=False — bypasses cleanly
2. GPDMCTSStrategy with no convention lock — graceful
3. GPDMCTSStrategy with missing specs directory — clear error
4. ReferenceLoader with empty specs/references/ — returns None gracefully
5. BundleLoader with invalid YAML — clear error
6. PhysicsCurator with GPD_FAST_MODEL=openai:gpt-4o-mini — works
7. model_defaults.resolve_model_and_settings("invalid-provider:model") — graceful
8. model_defaults.resolve_model_and_settings("anthropic:claude-sonnet-4-5-high") — correct effort
9. ablations.apply_ablation_overrides with GPD_DISABLE_CONVENTIONS=1 — works
10. Convention lock with empty custom_conventions — no crash
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
from psi_contracts.gpd import ConventionLock
from psi_contracts.solving import CandidateSolution, Run

from gpd.ablations import apply_ablation_overrides
from gpd.core.model_defaults import resolve_model_and_settings
from gpd.strategy.bundle_loader import (
    BundleLoader,
    BundleManifestError,
    BundleNotFoundError,
    load_bundle,
    load_bundle_manifest,
)
from gpd.strategy.commit_gate_hooks import create_gpd_invariant_checks
from gpd.strategy.loader import ReferenceLoader
from gpd.strategy.mcts import (
    GPDMCTSStrategy,
    _extract_convention_lock,
    convention_lock_consistency_check,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# 1. GPDMCTSStrategy with gpd_enabled=False — bypasses cleanly
# ---------------------------------------------------------------------------


class TestGPDDisabledBypass:
    """Verify zero GPD overhead when gpd_enabled=False."""

    async def test_no_gpd_events_emitted(self):
        """gpd_enabled=False must not emit any gpd_* events."""
        run = _make_run()

        async def _mock_solve(*args, **kwargs) -> AsyncIterator[Run]:
            yield run

        with patch.object(
            __import__("pipeline.strategies.mcts", fromlist=["MCTSStrategy"]).MCTSStrategy,
            "solve",
            side_effect=_mock_solve,
        ):
            strategy = GPDMCTSStrategy()
            events = _make_events()

            runs = []
            async for r in strategy.solve(
                problem=_make_problem(),
                verifier=_make_verifier(),
                capabilities=_make_capabilities(),
                config=_make_config(gpd_enabled=False),
                memory=_make_memory(),
                events=events,
            ):
                runs.append(r)

        assert len(runs) == 1
        # No gpd_* events should have been emitted
        for call in events.emit.call_args_list:
            assert not call.args[0].startswith("gpd_"), f"Unexpected GPD event: {call.args[0]}"

    async def test_providers_not_passed_when_disabled(self):
        """When gpd_enabled=False, MCTSStrategy should NOT receive provider dict."""
        run = _make_run()

        async def _mock_solve(*args, **kwargs) -> AsyncIterator[Run]:
            yield run

        with patch.object(
            __import__("pipeline.strategies.mcts", fromlist=["MCTSStrategy"]).MCTSStrategy,
            "solve",
            side_effect=_mock_solve,
        ) as mock:
            strategy = GPDMCTSStrategy()
            async for _ in strategy.solve(
                problem=_make_problem(),
                verifier=_make_verifier(),
                capabilities=_make_capabilities(),
                config=_make_config(gpd_enabled=False),
                memory=_make_memory(),
                events=_make_events(),
            ):
                pass

        # providers kwarg should be None (the default), not a dict with GPD providers
        call_kwargs = mock.call_args.kwargs
        providers = call_kwargs.get("providers")
        assert providers is None or providers == {}  # Either None or empty


# ---------------------------------------------------------------------------
# 2. GPDMCTSStrategy with no convention lock — graceful
# ---------------------------------------------------------------------------


class TestNoConventionLock:
    """When the problem has no ASSERT_CONVENTION directives, the strategy
    should still run cleanly with an empty ConventionLock."""

    def test_extract_convention_lock_empty_problem(self):
        problem = _make_problem(problem_statement="Just a plain physics problem, no conventions.")
        lock = _extract_convention_lock(problem)
        assert lock.metric_signature is None
        assert lock.fourier_convention is None
        assert lock.custom_conventions == {}

    def test_consistency_check_no_conventions_no_config(self):
        problem = _make_problem(problem_statement="No conventions here.")
        lock = convention_lock_consistency_check(problem, config_lock=None)
        assert lock.metric_signature is None
        assert lock.custom_conventions == {}

    def test_create_invariant_checks_empty_lock(self):
        """Empty convention lock should produce no invariant checks."""
        lock = ConventionLock()
        checks = create_gpd_invariant_checks(lock, [])
        assert checks == []

    async def test_strategy_with_no_conventions_runs(self):
        """Full strategy run with no conventions should complete without errors."""
        run = _make_run()

        async def _mock_solve(*args, **kwargs) -> AsyncIterator[Run]:
            yield run

        with patch.object(
            __import__("pipeline.strategies.mcts", fromlist=["MCTSStrategy"]).MCTSStrategy,
            "solve",
            side_effect=_mock_solve,
        ):
            strategy = GPDMCTSStrategy()
            events = _make_events()
            memory = _make_memory()

            runs = []
            async for r in strategy.solve(
                problem=_make_problem(problem_statement="Plain problem, no conventions"),
                verifier=_make_verifier(),
                capabilities=_make_capabilities(),
                config=_make_config(gpd_enabled=True),
                memory=memory,
                events=events,
            ):
                runs.append(r)

        assert len(runs) == 1
        # Convention lock recorded in memory should have all None fields
        memory.record_hypothesis.assert_called_once()
        hypo = memory.record_hypothesis.call_args[0][0]
        assert hypo["convention_lock"]["metric_signature"] is None


# ---------------------------------------------------------------------------
# 3. GPDMCTSStrategy with missing specs directory — clear error
# ---------------------------------------------------------------------------


class TestMissingSpecsDir:
    """When the specs directory doesn't exist, BundleLoader should handle
    gracefully (empty bundle) and the strategy should still function."""

    def test_bundle_loader_missing_base_dir(self, tmp_path):
        """BundleLoader.load with non-existent base dir uses empty bundle."""
        loader = BundleLoader(specs_dir=tmp_path)
        result = loader.load(base_name="nonexistent")
        # Should fall back to empty bundle, not crash
        assert result.actors == {}
        assert result.actions == {}
        assert result.skills == {}

    def test_bundle_loader_missing_overlay_dir(self, tmp_path):
        """Missing overlay dir is skipped with a warning, not a crash."""
        base_dir = tmp_path / "base"
        base_dir.mkdir()
        loader = BundleLoader(specs_dir=tmp_path)
        result = loader.load(base_name="base", overlay_names=["nonexistent_overlay"])
        assert result is not None

    def test_reference_loader_missing_refs_dir(self, tmp_path):
        """ReferenceLoader with no references directory returns empty results."""
        loader = ReferenceLoader(specs_dir=tmp_path)
        loader.build_index()
        assert loader.reference_names == []
        assert loader.load("anything") is None


# ---------------------------------------------------------------------------
# 4. ReferenceLoader with empty specs/references/ — returns None gracefully
# ---------------------------------------------------------------------------


class TestReferenceLoaderEmpty:
    """ReferenceLoader with an empty references/ dir should not crash."""

    def test_empty_refs_dir(self, tmp_path):
        refs_dir = tmp_path / "references"
        refs_dir.mkdir()
        loader = ReferenceLoader(specs_dir=tmp_path)
        loader.build_index()
        assert loader.reference_names == []
        assert loader.protocol_names == []
        assert loader.verification_domains == []

    def test_load_nonexistent_ref(self, tmp_path):
        refs_dir = tmp_path / "references"
        refs_dir.mkdir()
        loader = ReferenceLoader(specs_dir=tmp_path)
        loader.build_index()
        assert loader.load("nonexistent") is None

    def test_load_protocol_nonexistent(self, tmp_path):
        refs_dir = tmp_path / "references"
        refs_dir.mkdir()
        loader = ReferenceLoader(specs_dir=tmp_path)
        loader.build_index()
        assert loader.load_protocol("nonexistent") is None

    def test_load_error_catalog_nonexistent(self, tmp_path):
        refs_dir = tmp_path / "references"
        refs_dir.mkdir()
        loader = ReferenceLoader(specs_dir=tmp_path)
        loader.build_index()
        assert loader.load_error_catalog("nonexistent") is None

    def test_search_by_keywords_empty(self, tmp_path):
        refs_dir = tmp_path / "references"
        refs_dir.mkdir()
        loader = ReferenceLoader(specs_dir=tmp_path)
        loader.build_index()
        assert loader.search_by_keywords(["qft", "renormalization"]) == []

    def test_cache_stats_on_empty(self, tmp_path):
        refs_dir = tmp_path / "references"
        refs_dir.mkdir()
        loader = ReferenceLoader(specs_dir=tmp_path)
        current, max_size = loader.cache_stats
        assert current == 0
        assert max_size > 0


# ---------------------------------------------------------------------------
# 5. BundleLoader with invalid YAML — clear error
# ---------------------------------------------------------------------------


class TestBundleLoaderInvalidYAML:
    """BundleLoader should raise clear errors for malformed YAML."""

    def test_malformed_bundle_manifest(self, tmp_path):
        """Malformed bundle.yaml should raise BundleManifestError."""
        bundle_dir = tmp_path / "bad_bundle"
        bundle_dir.mkdir()
        manifest = bundle_dir / "bundle.yaml"
        manifest.write_text(":::invalid yaml{{{\n  - broken: [unclosed")

        with pytest.raises(BundleManifestError, match="YAML parse error"):
            load_bundle_manifest(bundle_dir)

    def test_non_dict_manifest(self, tmp_path):
        """bundle.yaml that is a list should raise BundleManifestError."""
        bundle_dir = tmp_path / "list_bundle"
        bundle_dir.mkdir()
        manifest = bundle_dir / "bundle.yaml"
        manifest.write_text("- item1\n- item2\n")

        with pytest.raises(BundleManifestError, match="Expected a YAML mapping"):
            load_bundle_manifest(bundle_dir)

    def test_invalid_actor_yaml_skipped(self, tmp_path):
        """Invalid actor YAML files should be silently skipped (returns {})."""
        bundle_dir = tmp_path / "actor_bundle"
        bundle_dir.mkdir()
        actors_dir = bundle_dir / "actors"
        actors_dir.mkdir()
        bad_actor = actors_dir / "broken.yaml"
        bad_actor.write_text(":::not valid yaml{{{")

        # Should not crash — bad YAML files are skipped
        bundle = load_bundle(bundle_dir)
        assert "broken" not in bundle.actors

    def test_bundle_not_found_error(self, tmp_path):
        """Loading a bundle from nonexistent dir raises BundleNotFoundError."""
        with pytest.raises(BundleNotFoundError):
            load_bundle(tmp_path / "does_not_exist")


# ---------------------------------------------------------------------------
# 6. PhysicsCurator with GPD_FAST_MODEL=openai:gpt-4o-mini — works
# ---------------------------------------------------------------------------


class TestPhysicsCuratorModelSelection:
    """PhysicsCurator should accept arbitrary model IDs."""

    def test_curator_accepts_openai_model(self):
        """PhysicsCurator instantiation with openai model should not crash."""
        from gpd.strategy.curator import PhysicsCurator

        curator = PhysicsCurator(model_id="openai:gpt-4o-mini")
        assert curator._model_id == "openai:gpt-4o-mini"

    def test_curator_accepts_anthropic_model(self):
        from gpd.strategy.curator import PhysicsCurator

        curator = PhysicsCurator(model_id="anthropic:claude-haiku-4-5-20251001")
        assert curator._model_id == "anthropic:claude-haiku-4-5-20251001"

    def test_curator_with_env_override(self, monkeypatch):
        """GPD_FAST_MODEL env var should change the default model."""
        monkeypatch.setenv("GPD_FAST_MODEL", "openai:gpt-4o-mini")
        # Re-import to pick up env var
        import importlib

        import gpd.core.model_defaults as md

        importlib.reload(md)
        try:
            assert md.GPD_DEFAULT_FAST_MODEL == "openai:gpt-4o-mini"
        finally:
            # Restore
            monkeypatch.delenv("GPD_FAST_MODEL", raising=False)
            importlib.reload(md)

    def test_curator_build_prompt_static(self):
        """PhysicsCurator._build_prompt should work with empty state."""
        from psi_contracts.blackboard import BlackboardWriteRequest

        from gpd.strategy.curator import PhysicsCurator

        request = BlackboardWriteRequest(
            kind="result",
            content="The ground state energy is E_0 = -J",
            confidence=0.9,
        )
        prompt = PhysicsCurator._build_prompt([request], {})
        assert "Proposed Writes" in prompt
        assert "ground state energy" in prompt


# ---------------------------------------------------------------------------
# 7. model_defaults.resolve_model_and_settings with invalid provider — graceful
# ---------------------------------------------------------------------------


class TestResolveModelAndSettingsInvalid:
    """resolve_model_and_settings should handle unknown models gracefully."""

    def test_unknown_provider_no_effort(self):
        """Unknown provider with no effort suffix returns spec as-is with empty settings."""
        model_id, settings = resolve_model_and_settings("unknown-provider:some-model")
        # parse_model_spec should parse it without effort
        assert model_id == "unknown-provider:some-model"
        assert settings == {}

    def test_no_provider_prefix(self):
        """Spec without provider prefix should still parse."""
        model_id, settings = resolve_model_and_settings("gpt-4o")
        assert model_id == "gpt-4o"
        assert settings == {}

    def test_unknown_provider_with_effort(self):
        """Unknown provider with effort suffix raises ValueError from effort_to_model_settings."""
        with pytest.raises(ValueError, match="Unknown model"):
            resolve_model_and_settings("fakeprovider:fake-model-high")


# ---------------------------------------------------------------------------
# 8. model_defaults.resolve_model_and_settings with Anthropic effort — correct
# ---------------------------------------------------------------------------


class TestResolveModelAndSettingsEffort:
    """resolve_model_and_settings should produce correct provider-specific settings."""

    def test_anthropic_sonnet_high_effort(self):
        """anthropic:claude-sonnet-4-5-high should produce anthropic-specific settings."""
        model_id, settings = resolve_model_and_settings("anthropic:claude-sonnet-4-5-20250929-high")
        assert model_id == "anthropic:claude-sonnet-4-5-20250929"
        # Anthropic high effort should include thinking settings
        assert "anthropic_thinking" in settings or "max_tokens" in settings

    def test_anthropic_no_effort_returns_baseline(self):
        """anthropic:claude-sonnet-4-5 with no effort should return baseline settings."""
        model_id, settings = resolve_model_and_settings("anthropic:claude-sonnet-4-5-20250929")
        assert model_id == "anthropic:claude-sonnet-4-5-20250929"
        # Should have prompt caching enabled at minimum
        assert settings.get("anthropic_cache_instructions") is True

    def test_openai_low_effort(self):
        """openai:o3-mini-low should produce openai reasoning_effort settings."""
        model_id, settings = resolve_model_and_settings("openai:o3-mini-low")
        assert model_id == "openai:o3-mini"
        assert settings.get("openai_reasoning_effort") == "low"


# ---------------------------------------------------------------------------
# 9. ablations.apply_ablation_overrides with GPD_DISABLE_CONVENTIONS=1
# ---------------------------------------------------------------------------


class TestAblationOverrides:
    """apply_ablation_overrides should correctly disable subsystems."""

    def test_disable_conventions(self):
        """GPD_DISABLE_CONVENTIONS=1 should disable all convention flags."""
        flags = {
            "gpd.enabled": True,
            "gpd.conventions.enabled": True,
            "gpd.conventions.commit_gate": True,
            "gpd.conventions.assert_check": True,
            "gpd.conventions.drift_detection": True,
            "gpd.verification.enabled": True,
        }
        env = {"GPD_DISABLE_CONVENTIONS": "1"}
        result = apply_ablation_overrides(flags, env=env)

        assert result["gpd.conventions.enabled"] is False
        assert result["gpd.conventions.commit_gate"] is False
        assert result["gpd.conventions.assert_check"] is False
        assert result["gpd.conventions.drift_detection"] is False
        # Other flags should be unchanged
        assert result["gpd.enabled"] is True
        assert result["gpd.verification.enabled"] is True

    def test_disable_verification(self):
        """GPD_DISABLE_VERIFICATION=1 should disable all verification flags."""
        flags = {
            "gpd.enabled": True,
            "gpd.verification.enabled": True,
            "gpd.verification.checks.dimensional": True,
            "gpd.verification.checks.limiting_cases": True,
            "gpd.verification.checks.symmetry": True,
            "gpd.verification.checks.conservation": True,
            "gpd.verification.checks.numerical": True,
            "gpd.verification.checks.sign_convention": True,
            "gpd.verification.checks.index_consistency": True,
        }
        env = {"GPD_DISABLE_VERIFICATION": "1"}
        result = apply_ablation_overrides(flags, env=env)

        assert result["gpd.verification.enabled"] is False
        assert result["gpd.verification.checks.dimensional"] is False
        assert result["gpd.verification.checks.limiting_cases"] is False

    def test_no_env_overrides_leaves_flags_unchanged(self):
        """When no GPD_DISABLE_* env vars are set, flags stay the same."""
        flags = {
            "gpd.enabled": True,
            "gpd.conventions.enabled": True,
        }
        result = apply_ablation_overrides(dict(flags), env={})
        assert result == flags

    def test_truthy_values_accepted(self):
        """Various truthy values (true, yes, on) should all work."""
        for val in ("1", "true", "True", "YES", "on", "ON"):
            flags = {"gpd.conventions.enabled": True, "gpd.conventions.commit_gate": True}
            env = {"GPD_DISABLE_COMMIT_GATE": val}
            result = apply_ablation_overrides(dict(flags), env=env)
            assert result["gpd.conventions.commit_gate"] is False, f"Failed for value: {val}"

    def test_falsy_values_ignored(self):
        """Non-truthy values (0, false, empty) should NOT disable."""
        for val in ("0", "false", "no", "off", ""):
            flags = {"gpd.conventions.enabled": True, "gpd.conventions.commit_gate": True}
            env = {"GPD_DISABLE_COMMIT_GATE": val}
            result = apply_ablation_overrides(dict(flags), env=env)
            assert result["gpd.conventions.commit_gate"] is True, f"Disabled for value: {val}"

    def test_master_kill_switch(self):
        """GPD_DISABLE_GPD=1 should disable the master flag."""
        flags = {"gpd.enabled": True}
        env = {"GPD_DISABLE_GPD": "1"}
        result = apply_ablation_overrides(flags, env=env)
        assert result["gpd.enabled"] is False

    def test_multiple_overrides(self):
        """Multiple GPD_DISABLE_ env vars should all be applied."""
        flags = {
            "gpd.enabled": True,
            "gpd.conventions.enabled": True,
            "gpd.conventions.commit_gate": True,
            "gpd.conventions.assert_check": True,
            "gpd.conventions.drift_detection": True,
            "gpd.verification.enabled": True,
            "gpd.verification.checks.dimensional": True,
        }
        env = {"GPD_DISABLE_CONVENTIONS": "1", "GPD_DISABLE_DIMENSIONAL": "1"}
        result = apply_ablation_overrides(flags, env=env)

        assert result["gpd.conventions.enabled"] is False
        assert result["gpd.verification.checks.dimensional"] is False
        # Verification top-level should still be enabled
        assert result["gpd.verification.enabled"] is True


# ---------------------------------------------------------------------------
# 10. Convention lock with empty custom_conventions — no crash
# ---------------------------------------------------------------------------


class TestConventionLockEmptyCustom:
    """Convention lock with empty custom_conventions should not cause issues."""

    def test_empty_custom_conventions(self):
        lock = ConventionLock(custom_conventions={})
        assert lock.custom_conventions == {}

    def test_invariant_checks_empty_custom(self):
        """create_gpd_invariant_checks with empty custom conventions returns no checks."""
        lock = ConventionLock(custom_conventions={})
        checks = create_gpd_invariant_checks(lock, [])
        assert checks == []

    def test_consistency_check_empty_custom_plus_config(self):
        """convention_lock_consistency_check merges config into empty custom_conventions."""
        problem = _make_problem(problem_statement="Plain problem.")
        lock = convention_lock_consistency_check(
            problem,
            config_lock={"some_custom_key": "some_value"},
        )
        assert lock.custom_conventions["some_custom_key"] == "some_value"

    def test_convention_lock_with_only_custom(self):
        """Lock with only custom conventions should produce a convention check."""
        lock = ConventionLock(custom_conventions={"my_convention": "my_value"})
        checks = create_gpd_invariant_checks(lock, [])
        # Should produce a convention check since custom_conventions is non-empty
        assert len(checks) == 1

    def test_convention_check_custom_assertion_mismatch(self):
        """Convention check should detect mismatch in custom convention."""
        lock = ConventionLock(custom_conventions={"my_convention": "expected_value"})
        checks = create_gpd_invariant_checks(lock, [])
        assert len(checks) == 1

        # Payload containing a mismatched ASSERT_CONVENTION directive
        payload = {"solution": {"text": "# ASSERT_CONVENTION: my_convention=wrong_value\nSome physics work."}}
        violations = checks[0](payload, {})
        assert len(violations) >= 1
        assert "mismatch" in violations[0].lower() or "ASSERT_CONVENTION" in violations[0]

    def test_convention_check_custom_assertion_match(self):
        """Convention check should pass when custom convention matches."""
        lock = ConventionLock(custom_conventions={"my_convention": "correct_value"})
        checks = create_gpd_invariant_checks(lock, [])
        assert len(checks) == 1

        payload = {"solution": {"text": "# ASSERT_CONVENTION: my_convention=correct_value\nSome physics work."}}
        violations = checks[0](payload, {})
        assert violations == []
