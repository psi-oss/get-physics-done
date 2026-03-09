"""Tests for gpd/ablations.py — ablation overrides, guards, decorators, and reporting.

Covers: apply_ablation_overrides with GPD_DISABLE_X env vars, guarded() decorator
(sync + async), skip_when_disabled, ablation_guard context manager, report_ablations,
AblationReport, flag mutations, and edge cases.
"""

from __future__ import annotations

import asyncio

import pytest

from gpd.ablations import (
    ABLATION_POINTS,
    AblationReport,
    ablation_guard,
    apply_ablation_overrides,
    guarded,
    report_ablations,
    skip_when_disabled,
)
from gpd.core.observability import (
    GPD_FEATURE_FLAGS,
    FeatureFlags,
    init_feature_flags,
    reset_feature_flags,
)


@pytest.fixture(autouse=True)
def _reset_flags() -> None:
    """Reset the global feature flags singleton before each test."""
    reset_feature_flags()


def _all_enabled_flags() -> dict[str, bool]:
    """Return a copy of default flags with gpd.enabled=True."""
    flags = dict(GPD_FEATURE_FLAGS)
    flags["gpd.enabled"] = True
    return flags


# ─── apply_ablation_overrides ──────────────────────────────────────────────


class TestApplyAblationOverrides:
    """Tests for apply_ablation_overrides with GPD_DISABLE_X env vars."""

    def test_no_env_vars_no_change(self) -> None:
        """Without any GPD_DISABLE_ env vars, flags are unchanged."""
        flags = _all_enabled_flags()
        original = dict(flags)
        result = apply_ablation_overrides(flags, env={})
        assert result == original
        assert result is flags  # mutates in place

    def test_disable_conventions(self) -> None:
        """GPD_DISABLE_CONVENTIONS=1 disables all convention flags."""
        flags = _all_enabled_flags()
        apply_ablation_overrides(flags, env={"GPD_DISABLE_CONVENTIONS": "1"})
        assert flags["gpd.conventions.enabled"] is False
        assert flags["gpd.conventions.commit_gate"] is False
        assert flags["gpd.conventions.assert_check"] is False
        assert flags["gpd.conventions.drift_detection"] is False
        # Other subsystems remain enabled
        assert flags["gpd.verification.enabled"] is True

    def test_disable_verification(self) -> None:
        """GPD_DISABLE_VERIFICATION=1 disables all verification flags."""
        flags = _all_enabled_flags()
        apply_ablation_overrides(flags, env={"GPD_DISABLE_VERIFICATION": "1"})
        assert flags["gpd.verification.enabled"] is False
        assert flags["gpd.verification.checks.dimensional"] is False
        assert flags["gpd.verification.checks.limiting_cases"] is False
        assert flags["gpd.verification.checks.symmetry"] is False
        assert flags["gpd.verification.checks.conservation"] is False
        assert flags["gpd.verification.checks.numerical"] is False
        assert flags["gpd.verification.checks.sign_convention"] is False
        assert flags["gpd.verification.checks.index_consistency"] is False

    def test_disable_single_check(self) -> None:
        """GPD_DISABLE_DIMENSIONAL=1 disables only dimensional check."""
        flags = _all_enabled_flags()
        apply_ablation_overrides(flags, env={"GPD_DISABLE_DIMENSIONAL": "1"})
        assert flags["gpd.verification.checks.dimensional"] is False
        # Other verification checks remain enabled
        assert flags["gpd.verification.checks.symmetry"] is True
        assert flags["gpd.verification.enabled"] is True

    def test_disable_patterns(self) -> None:
        """GPD_DISABLE_PATTERNS=1 disables pattern library flags."""
        flags = _all_enabled_flags()
        apply_ablation_overrides(flags, env={"GPD_DISABLE_PATTERNS": "1"})
        assert flags["gpd.patterns.enabled"] is False
        assert flags["gpd.patterns.cross_project"] is False

    def test_disable_commit_gate_only(self) -> None:
        """GPD_DISABLE_COMMIT_GATE=1 disables only CommitGate hook."""
        flags = _all_enabled_flags()
        apply_ablation_overrides(flags, env={"GPD_DISABLE_COMMIT_GATE": "1"})
        assert flags["gpd.conventions.commit_gate"] is False
        # Rest of conventions still enabled
        assert flags["gpd.conventions.enabled"] is True
        assert flags["gpd.conventions.assert_check"] is True

    def test_master_kill_switch(self) -> None:
        """GPD_DISABLE_GPD=1 disables the master switch."""
        flags = _all_enabled_flags()
        apply_ablation_overrides(flags, env={"GPD_DISABLE_GPD": "1"})
        assert flags["gpd.enabled"] is False

    def test_multiple_disable_vars(self) -> None:
        """Multiple GPD_DISABLE_ vars stack."""
        flags = _all_enabled_flags()
        apply_ablation_overrides(
            flags,
            env={
                "GPD_DISABLE_CONVENTIONS": "1",
                "GPD_DISABLE_PATTERNS": "1",
                "GPD_DISABLE_TRACING": "1",
            },
        )
        assert flags["gpd.conventions.enabled"] is False
        assert flags["gpd.patterns.enabled"] is False
        assert flags["gpd.diagnostics.tracing"] is False
        # Verification still enabled
        assert flags["gpd.verification.enabled"] is True

    def test_truthy_values(self) -> None:
        """Various truthy values: '1', 'true', 'yes', 'on' (case-insensitive)."""
        for value in ("1", "true", "True", "TRUE", "yes", "YES", "on", "ON"):
            flags = _all_enabled_flags()
            apply_ablation_overrides(flags, env={"GPD_DISABLE_TRACING": value})
            assert flags["gpd.diagnostics.tracing"] is False, f"Failed for value: {value}"

    def test_non_truthy_values_ignored(self) -> None:
        """Values like '0', 'false', 'no', '' don't trigger disable."""
        for value in ("0", "false", "no", "off", "", " "):
            flags = _all_enabled_flags()
            apply_ablation_overrides(flags, env={"GPD_DISABLE_TRACING": value})
            assert flags["gpd.diagnostics.tracing"] is True, f"Should not disable for value: {value!r}"

    def test_unknown_env_var_ignored(self) -> None:
        """GPD_DISABLE_NONEXISTENT=1 is silently ignored."""
        flags = _all_enabled_flags()
        original = dict(flags)
        apply_ablation_overrides(flags, env={"GPD_DISABLE_NONEXISTENT": "1"})
        assert flags == original

    def test_flag_key_not_in_dict_skipped(self) -> None:
        """If flag_keys reference a key not in the flags dict, that key is skipped."""
        # Use a minimal dict with only some keys
        flags = {"gpd.conventions.enabled": True}
        apply_ablation_overrides(flags, env={"GPD_DISABLE_CONVENTIONS": "1"})
        assert flags["gpd.conventions.enabled"] is False
        # Other convention keys weren't in dict, so not added
        assert "gpd.conventions.commit_gate" not in flags

    def test_returns_same_dict(self) -> None:
        """Returns the same dict object (mutates in place)."""
        flags = _all_enabled_flags()
        result = apply_ablation_overrides(flags, env={"GPD_DISABLE_TRACING": "1"})
        assert result is flags

    def test_defaults_to_os_environ(self) -> None:
        """When env=None, reads from os.environ (default behavior)."""
        import os
        from unittest.mock import patch

        flags = _all_enabled_flags()
        env = dict(os.environ)
        # Remove any existing GPD_DISABLE_ vars
        env = {k: v for k, v in env.items() if not k.startswith("GPD_DISABLE_")}
        with patch.dict(os.environ, env, clear=True):
            apply_ablation_overrides(flags)
        # No changes since no GPD_DISABLE_ vars
        assert flags["gpd.conventions.enabled"] is True

    def test_whitespace_in_value_trimmed(self) -> None:
        """Leading/trailing whitespace in env value is trimmed."""
        flags = _all_enabled_flags()
        apply_ablation_overrides(flags, env={"GPD_DISABLE_TRACING": "  1  "})
        assert flags["gpd.diagnostics.tracing"] is False


# ─── ablation_guard context manager ────────────────────────────────────────


class TestAblationGuard:
    """Tests for ablation_guard context manager."""

    def test_guard_yields_false_when_disabled(self) -> None:
        """When flags not initialized, is_enabled returns False → guard yields False."""
        with ablation_guard("gpd.conventions.commit_gate", subsystem="commit_gate") as active:
            assert active is False

    def test_guard_yields_true_when_enabled(self) -> None:
        """When flag is enabled, guard yields True."""
        init_feature_flags(env={}, preset="gpd_full")
        with ablation_guard("gpd.conventions.commit_gate", subsystem="commit_gate") as active:
            assert active is True

    def test_guard_with_disabled_flag(self) -> None:
        """Specific flag disabled → guard yields False."""
        init_feature_flags(
            env={},
            preset="gpd_full",
            yaml_overrides={"gpd.conventions.commit_gate": False},
        )
        with ablation_guard("gpd.conventions.commit_gate", subsystem="commit_gate") as active:
            assert active is False

    def test_guard_without_subsystem(self) -> None:
        """Guard without subsystem uses flag_path as span name."""
        # Should not crash
        with ablation_guard("gpd.verification.checks.dimensional") as active:
            assert isinstance(active, bool)


# ─── guarded() decorator — sync ───────────────────────────────────────────


class TestGuardedSync:
    """Tests for guarded() decorator with sync functions."""

    def test_sync_returns_default_when_disabled(self) -> None:
        """When flag is off, sync function returns default."""

        @guarded("gpd.verification.checks.dimensional", default=[])
        def check_dimensions() -> list[str]:
            return ["violation_1"]

        # Flags not initialized → is_enabled returns False
        result = check_dimensions()
        assert result == []

    def test_sync_executes_when_enabled(self) -> None:
        """When flag is on, sync function executes normally."""
        init_feature_flags(env={}, preset="gpd_full")

        @guarded("gpd.verification.checks.dimensional", default=[])
        def check_dimensions() -> list[str]:
            return ["violation_1"]

        result = check_dimensions()
        assert result == ["violation_1"]

    def test_sync_passes_args(self) -> None:
        """Sync wrapper passes args and kwargs through."""
        init_feature_flags(env={}, preset="gpd_full")

        @guarded("gpd.conventions.enabled", default=0)
        def add(a: int, b: int, *, extra: int = 0) -> int:
            return a + b + extra

        assert add(3, 4, extra=5) == 12

    def test_sync_preserves_function_name(self) -> None:
        """functools.wraps preserves function metadata."""

        @guarded("gpd.conventions.enabled", default=None)
        def my_important_function() -> None:
            pass

        assert my_important_function.__name__ == "my_important_function"

    def test_sync_default_none(self) -> None:
        """Default value of None when not specified via skip_when_disabled."""

        @skip_when_disabled("gpd.conventions.enabled")
        def do_work() -> str:
            return "done"

        # Flags not initialized → returns None
        assert do_work() is None

    def test_sync_default_custom_type(self) -> None:
        """Custom default types like dict, tuple."""

        @guarded("gpd.conventions.enabled", default={"status": "skipped"})
        def analyze() -> dict[str, str]:
            return {"status": "ok"}

        result = analyze()
        assert result == {"status": "skipped"}


# ─── guarded() decorator — async ──────────────────────────────────────────


class TestGuardedAsync:
    """Tests for guarded() decorator with async functions."""

    def test_async_returns_default_when_disabled(self) -> None:
        """When flag is off, async function returns default."""

        @guarded("gpd.verification.checks.dimensional", default=[])
        async def check_dimensions() -> list[str]:
            return ["violation_1"]

        result = asyncio.new_event_loop().run_until_complete(check_dimensions())
        assert result == []

    def test_async_executes_when_enabled(self) -> None:
        """When flag is on, async function executes normally."""
        init_feature_flags(env={}, preset="gpd_full")

        @guarded("gpd.verification.checks.dimensional", default=[])
        async def check_dimensions() -> list[str]:
            return ["violation_1"]

        result = asyncio.new_event_loop().run_until_complete(check_dimensions())
        assert result == ["violation_1"]

    def test_async_passes_args(self) -> None:
        """Async wrapper passes args and kwargs through."""
        init_feature_flags(env={}, preset="gpd_full")

        @guarded("gpd.conventions.enabled", default=0)
        async def add(a: int, b: int, *, extra: int = 0) -> int:
            return a + b + extra

        result = asyncio.new_event_loop().run_until_complete(add(3, 4, extra=5))
        assert result == 12

    def test_async_preserves_function_name(self) -> None:
        """functools.wraps preserves function metadata for async."""

        @guarded("gpd.conventions.enabled", default=None)
        async def my_async_function() -> None:
            pass

        assert my_async_function.__name__ == "my_async_function"

    def test_async_is_still_coroutine(self) -> None:
        """Wrapped async function is still detected as coroutine function."""
        import asyncio as aio

        @guarded("gpd.conventions.enabled", default=None)
        async def coro_func() -> None:
            pass

        assert aio.iscoroutinefunction(coro_func)


# ─── skip_when_disabled shorthand ──────────────────────────────────────────


class TestSkipWhenDisabled:
    """Tests for skip_when_disabled shorthand decorator."""

    def test_sync_returns_none_when_disabled(self) -> None:

        @skip_when_disabled("gpd.patterns.enabled")
        def find_patterns() -> list[str]:
            return ["pattern_1"]

        assert find_patterns() is None

    def test_sync_executes_when_enabled(self) -> None:
        init_feature_flags(env={}, preset="gpd_full")

        @skip_when_disabled("gpd.patterns.enabled")
        def find_patterns() -> list[str]:
            return ["pattern_1"]

        assert find_patterns() == ["pattern_1"]

    def test_async_returns_none_when_disabled(self) -> None:

        @skip_when_disabled("gpd.patterns.enabled")
        async def find_patterns() -> list[str]:
            return ["pattern_1"]

        result = asyncio.new_event_loop().run_until_complete(find_patterns())
        assert result is None


# ─── AblationReport ────────────────────────────────────────────────────────


class TestAblationReport:
    """Tests for AblationReport dataclass."""

    def test_empty_report(self) -> None:
        report = AblationReport()
        assert report.active == []
        assert report.disabled == []
        assert report.env_overrides == []

    def test_summary_no_env(self) -> None:
        report = AblationReport(active=["A", "B", "C"], disabled=["D"])
        assert report.summary == "3/4 subsystems active, 1 disabled"

    def test_summary_with_env(self) -> None:
        report = AblationReport(active=["A"], disabled=["B", "C"], env_overrides=["B", "C"])
        assert report.summary == "1/3 subsystems active, 2 disabled, 2 via env"

    def test_to_dict(self) -> None:
        report = AblationReport(active=["A"], disabled=["B"], env_overrides=["B"])
        d = report.to_dict()
        assert d["active"] == ["A"]
        assert d["disabled"] == ["B"]
        assert d["env_overrides"] == ["B"]
        assert "summary" in d

    def test_all_active(self) -> None:
        report = AblationReport(active=["A", "B", "C"], disabled=[])
        assert "3/3 subsystems active, 0 disabled" == report.summary

    def test_all_disabled(self) -> None:
        report = AblationReport(active=[], disabled=["A", "B"])
        assert "0/2 subsystems active, 2 disabled" == report.summary


# ─── report_ablations ─────────────────────────────────────────────────────


class TestReportAblations:
    """Tests for report_ablations function."""

    def test_no_flags_returns_empty_report(self) -> None:
        """When flags not initialized and none passed, returns empty report."""
        report = report_ablations(flags=None, env={})
        assert report.active == []
        assert report.disabled == []

    def test_all_enabled(self) -> None:
        """With gpd_full preset, all subsystems should be active."""
        ff = init_feature_flags(env={}, preset="gpd_full")
        report = report_ablations(flags=ff, env={})
        assert len(report.disabled) == 0
        assert len(report.active) == len(ABLATION_POINTS)

    def test_conventions_disabled(self) -> None:
        """Disabling conventions shows them in disabled list."""
        flags = _all_enabled_flags()
        flags["gpd.conventions.enabled"] = False
        flags["gpd.conventions.commit_gate"] = False
        flags["gpd.conventions.assert_check"] = False
        flags["gpd.conventions.drift_detection"] = False
        ff = FeatureFlags(flags)
        report = report_ablations(flags=ff, env={})
        assert "CONVENTIONS" in report.disabled
        assert "COMMIT_GATE" in report.disabled

    def test_env_overrides_detected(self) -> None:
        """Env overrides appear in report.env_overrides."""
        ff = init_feature_flags(env={}, preset="gpd_full")
        report = report_ablations(
            flags=ff,
            env={"GPD_DISABLE_CONVENTIONS": "1", "GPD_DISABLE_TRACING": "yes"},
        )
        assert "CONVENTIONS" in report.env_overrides
        assert "TRACING" in report.env_overrides

    def test_env_overrides_non_truthy_ignored(self) -> None:
        """Non-truthy env values don't show in overrides."""
        ff = init_feature_flags(env={}, preset="gpd_full")
        report = report_ablations(
            flags=ff,
            env={"GPD_DISABLE_CONVENTIONS": "0", "GPD_DISABLE_TRACING": "false"},
        )
        assert report.env_overrides == []

    def test_report_with_explicit_flags_object(self) -> None:
        """Passing a FeatureFlags directly works."""
        flags = _all_enabled_flags()
        flags["gpd.diagnostics.tracing"] = False
        ff = FeatureFlags(flags)
        report = report_ablations(flags=ff, env={})
        assert "TRACING" in report.disabled
        # GPD still active overall
        assert "GPD" in report.active

    def test_master_disabled_cascades(self) -> None:
        """When gpd.enabled=False, FeatureFlags.is_enabled returns False for everything."""
        flags = _all_enabled_flags()
        flags["gpd.enabled"] = False
        ff = FeatureFlags(flags)
        report = report_ablations(flags=ff, env={})
        # All subsystems disabled because master switch is off
        assert len(report.active) == 0
        assert len(report.disabled) == len(ABLATION_POINTS)


# ─── ABLATION_POINTS registry integrity ───────────────────────────────────


class TestAblationPointsRegistry:
    """Tests for the ABLATION_POINTS constant integrity."""

    def test_all_flag_keys_exist_in_defaults(self) -> None:
        """Every flag_key referenced in ABLATION_POINTS exists in GPD_FEATURE_FLAGS."""
        for name, point in ABLATION_POINTS.items():
            for flag_key in point.flag_keys:
                assert flag_key in GPD_FEATURE_FLAGS, (
                    f"ABLATION_POINTS[{name!r}] references flag {flag_key!r} which is not in GPD_FEATURE_FLAGS"
                )

    def test_ablation_point_frozen(self) -> None:
        """AblationPoint is frozen — cannot mutate."""
        point = ABLATION_POINTS["CONVENTIONS"]
        with pytest.raises(AttributeError):
            point.subsystem = "HACKED"  # type: ignore[misc]

    def test_all_points_have_required_fields(self) -> None:
        """Every AblationPoint has non-empty subsystem, flag_keys, description, layer."""
        for name, point in ABLATION_POINTS.items():
            assert point.subsystem, f"{name}: empty subsystem"
            assert point.flag_keys, f"{name}: empty flag_keys"
            assert point.description, f"{name}: empty description"
            assert point.layer in ("core", "strategy", "mcp"), f"{name}: unknown layer {point.layer!r}"

    def test_subsystem_matches_dict_key(self) -> None:
        """Dict key matches the subsystem field on each AblationPoint."""
        for name, point in ABLATION_POINTS.items():
            assert name == point.subsystem, f"Key {name!r} != point.subsystem {point.subsystem!r}"


# ─── Flag mutation behavior ───────────────────────────────────────────────


class TestFlagMutations:
    """Tests for flag mutation semantics in apply_ablation_overrides."""

    def test_override_already_disabled_flag_stays_disabled(self) -> None:
        """Disabling an already-disabled flag is a no-op."""
        flags = _all_enabled_flags()
        flags["gpd.diagnostics.tracing"] = False
        apply_ablation_overrides(flags, env={"GPD_DISABLE_TRACING": "1"})
        assert flags["gpd.diagnostics.tracing"] is False

    def test_override_does_not_add_new_keys(self) -> None:
        """apply_ablation_overrides only modifies existing keys, never adds."""
        flags: dict[str, bool] = {}
        apply_ablation_overrides(flags, env={"GPD_DISABLE_CONVENTIONS": "1"})
        assert len(flags) == 0

    def test_cascade_disable_then_re_enable(self) -> None:
        """Disable via ablation, then manually re-enable flag — final state is enabled."""
        flags = _all_enabled_flags()
        apply_ablation_overrides(flags, env={"GPD_DISABLE_TRACING": "1"})
        assert flags["gpd.diagnostics.tracing"] is False
        flags["gpd.diagnostics.tracing"] = True
        assert flags["gpd.diagnostics.tracing"] is True

    def test_empty_env_dict(self) -> None:
        """Empty env dict is valid and produces no changes."""
        flags = _all_enabled_flags()
        original = dict(flags)
        apply_ablation_overrides(flags, env={})
        assert flags == original
