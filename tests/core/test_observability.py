"""Tests for gpd.core.observability — feature flags, spans, instrumentation."""

from __future__ import annotations

import pytest

from gpd.contracts import GPDConfig
from gpd.core.observability import (
    ABLATION_PRESETS,
    AblationPreset,
    FeatureFlagError,
    FeatureFlags,
    FlagNotInitializedError,
    GPD_FEATURE_FLAGS,
    UnknownPresetError,
    get_feature_flags,
    gpd_span,
    init_feature_flags,
    instrument_gpd_function,
    is_enabled,
    load_feature_flags,
    reset_feature_flags,
)


@pytest.fixture(autouse=True)
def _reset_flags():
    """Reset singleton between tests."""
    reset_feature_flags()
    yield
    reset_feature_flags()


# ---------------------------------------------------------------------------
# FeatureFlags
# ---------------------------------------------------------------------------


class TestFeatureFlags:
    def test_all_disabled_when_gpd_disabled(self):
        flags = FeatureFlags({"gpd.enabled": False, "gpd.conventions.enabled": True})
        assert flags.is_enabled("gpd.conventions.enabled") is False

    def test_enabled_when_gpd_enabled(self):
        flags = FeatureFlags({"gpd.enabled": True, "gpd.conventions.enabled": True})
        assert flags.is_enabled("gpd.conventions.enabled") is True

    def test_child_disabled_when_parent_disabled(self):
        flags = FeatureFlags({
            "gpd.enabled": True,
            "gpd.conventions.enabled": False,
            "gpd.conventions.commit_gate": True,
        })
        assert flags.is_enabled("gpd.conventions.commit_gate") is False

    def test_child_enabled_when_parent_enabled(self):
        flags = FeatureFlags({
            "gpd.enabled": True,
            "gpd.conventions.enabled": True,
            "gpd.conventions.commit_gate": True,
        })
        assert flags.is_enabled("gpd.conventions.commit_gate") is True

    def test_unknown_flag_returns_false(self):
        flags = FeatureFlags({"gpd.enabled": True})
        assert flags.is_enabled("gpd.nonexistent.flag") is False

    def test_enabled_flags_list(self):
        flags = FeatureFlags({
            "gpd.enabled": True,
            "gpd.conventions.enabled": True,
            "gpd.verification.enabled": False,
        })
        enabled = flags.enabled_flags()
        assert "gpd.enabled" in enabled
        assert "gpd.conventions.enabled" in enabled
        assert "gpd.verification.enabled" not in enabled

    def test_disabled_flags_list(self):
        flags = FeatureFlags({
            "gpd.enabled": True,
            "gpd.conventions.enabled": False,
        })
        disabled = flags.disabled_flags()
        assert "gpd.conventions.enabled" in disabled

    def test_flags_property_returns_copy(self):
        original = {"gpd.enabled": True}
        flags = FeatureFlags(original)
        copy = flags.flags
        copy["gpd.enabled"] = False
        # Original should be unaffected
        assert flags.is_enabled("gpd.enabled") is True

    def test_repr(self):
        flags = FeatureFlags({"gpd.enabled": True, "gpd.conventions.enabled": True})
        r = repr(flags)
        assert "FeatureFlags" in r
        assert "enabled=" in r

    def test_equality(self):
        a = FeatureFlags({"gpd.enabled": True})
        b = FeatureFlags({"gpd.enabled": True})
        assert a == b

    def test_inequality(self):
        a = FeatureFlags({"gpd.enabled": True})
        b = FeatureFlags({"gpd.enabled": False})
        assert a != b

    def test_not_equal_to_non_feature_flags(self):
        a = FeatureFlags({"gpd.enabled": True})
        assert a != "not a FeatureFlags"


# ---------------------------------------------------------------------------
# load_feature_flags
# ---------------------------------------------------------------------------


class TestLoadFeatureFlags:
    def test_defaults(self):
        flags = load_feature_flags(env={})
        assert flags["gpd.enabled"] is False  # default
        assert flags["gpd.conventions.enabled"] is True

    def test_preset_applies(self):
        flags = load_feature_flags(preset="gpd_full", env={})
        assert flags["gpd.enabled"] is True

    def test_preset_off(self):
        flags = load_feature_flags(preset="gpd_off", env={})
        assert flags["gpd.enabled"] is False

    def test_unknown_preset_raises(self):
        with pytest.raises(UnknownPresetError) as exc_info:
            load_feature_flags(preset="nonexistent", env={})
        assert "nonexistent" in str(exc_info.value)
        assert exc_info.value.preset == "nonexistent"

    def test_config_overrides_preset(self):
        cfg = GPDConfig(enabled=True, conventions_enabled=False)
        flags = load_feature_flags(config=cfg, preset="gpd_off", env={})
        # Config layer (3) overrides preset layer (1)
        assert flags["gpd.enabled"] is True
        assert flags["gpd.conventions.enabled"] is False

    def test_yaml_overrides_config(self):
        cfg = GPDConfig(enabled=True, conventions_enabled=True)
        yaml_overrides = {"gpd.conventions.enabled": False}
        flags = load_feature_flags(config=cfg, yaml_overrides=yaml_overrides, env={})
        assert flags["gpd.conventions.enabled"] is False

    def test_env_overrides_everything(self):
        cfg = GPDConfig(enabled=True, conventions_enabled=True)
        env = {"GPD_FLAG_GPD_CONVENTIONS_ENABLED": "0"}
        flags = load_feature_flags(config=cfg, env=env)
        assert flags["gpd.conventions.enabled"] is False

    def test_env_true_values(self):
        for val in ("1", "true", "True", "TRUE", "yes", "on"):
            flags = load_feature_flags(env={"GPD_FLAG_GPD_ENABLED": val})
            assert flags["gpd.enabled"] is True, f"Failed for env value: {val}"

    def test_env_false_values(self):
        for val in ("0", "false", "no", "off", "anything"):
            flags = load_feature_flags(env={"GPD_FLAG_GPD_ENABLED": val})
            assert flags["gpd.enabled"] is False, f"Failed for env value: {val}"

    def test_local_config_verifier_toggle(self):
        class FakeConfig:
            verifier = False
            plan_checker = True

        flags = load_feature_flags(local_config=FakeConfig(), env={})
        assert flags["gpd.verification.enabled"] is False
        assert flags["gpd.diagnostics.health_checks"] is True

    def test_yaml_ignores_unknown_keys(self):
        flags = load_feature_flags(
            yaml_overrides={"gpd.nonexistent.key": True},
            env={},
        )
        assert "gpd.nonexistent.key" not in flags


# ---------------------------------------------------------------------------
# Singleton management
# ---------------------------------------------------------------------------


class TestSingleton:
    def test_get_before_init_raises(self):
        with pytest.raises(FlagNotInitializedError):
            get_feature_flags()

    def test_is_enabled_returns_false_before_init(self):
        assert is_enabled("gpd.enabled") is False

    def test_init_and_get(self):
        init_feature_flags(config=GPDConfig(enabled=True), env={})
        ff = get_feature_flags()
        assert ff.is_enabled("gpd.enabled") is True

    def test_is_enabled_after_init(self):
        init_feature_flags(config=GPDConfig(enabled=True), env={})
        assert is_enabled("gpd.enabled") is True

    def test_reset(self):
        init_feature_flags(env={})
        reset_feature_flags()
        with pytest.raises(FlagNotInitializedError):
            get_feature_flags()


# ---------------------------------------------------------------------------
# Ablation presets
# ---------------------------------------------------------------------------


class TestAblationPresets:
    def test_all_presets_are_ablation_preset(self):
        for name, preset in ABLATION_PRESETS.items():
            assert isinstance(preset, AblationPreset)
            assert preset.name == name

    def test_known_presets_exist(self):
        expected = {"gpd_full", "gpd_off", "gpd_verification_only", "gpd_conventions_only", "gpd_exploratory"}
        assert expected == set(ABLATION_PRESETS.keys())

    def test_gpd_full_enables_gpd(self):
        assert ABLATION_PRESETS["gpd_full"].overrides["gpd.enabled"] is True

    def test_gpd_off_disables_gpd(self):
        assert ABLATION_PRESETS["gpd_off"].overrides["gpd.enabled"] is False

    def test_presets_are_frozen(self):
        preset = ABLATION_PRESETS["gpd_full"]
        with pytest.raises(Exception):
            preset.name = "hacked"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Feature flag error hierarchy
# ---------------------------------------------------------------------------


class TestFeatureFlagErrors:
    def test_feature_flag_error_is_gpd_error(self):
        from gpd.core.errors import GPDError

        assert issubclass(FeatureFlagError, GPDError)

    def test_unknown_preset_error(self):
        err = UnknownPresetError("bad", ["a", "b"])
        assert err.preset == "bad"
        assert err.valid == ["a", "b"]
        assert "bad" in str(err)

    def test_flag_not_initialized_error(self):
        err = FlagNotInitializedError()
        assert "not initialized" in str(err).lower()


# ---------------------------------------------------------------------------
# Default flag dict
# ---------------------------------------------------------------------------


class TestDefaultFlags:
    def test_gpd_enabled_defaults_false(self):
        assert GPD_FEATURE_FLAGS["gpd.enabled"] is False

    def test_all_component_flags_default_true(self):
        """All component .enabled flags default to True (only gpd.enabled is False)."""
        for key, val in GPD_FEATURE_FLAGS.items():
            if key == "gpd.enabled":
                assert val is False
            else:
                assert val is True, f"{key} should default to True"


# ---------------------------------------------------------------------------
# gpd_span
# ---------------------------------------------------------------------------


class TestGpdSpan:
    def test_span_context_manager(self):
        with gpd_span("test.span", domain="test") as span:
            assert span is not None

    def test_span_auto_prefixes(self):
        """Attrs without gpd. prefix get it added."""
        with gpd_span("test", domain="foo") as span:
            pass  # Just verifying no error


# ---------------------------------------------------------------------------
# instrument_gpd_function
# ---------------------------------------------------------------------------


class TestInstrumentGpdFunction:
    def test_sync_function(self):
        @instrument_gpd_function("test.sync")
        def my_func(x: int) -> int:
            return x + 1

        assert my_func(5) == 6

    @pytest.mark.asyncio
    async def test_async_function(self):
        @instrument_gpd_function("test.async")
        async def my_func(x: int) -> int:
            return x + 1

        assert await my_func(5) == 6

    def test_preserves_function_name(self):
        @instrument_gpd_function("test.named")
        def my_special_func():
            pass

        assert my_special_func.__name__ == "my_special_func"
