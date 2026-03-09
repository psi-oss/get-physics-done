"""Tests for gpd.core.model_defaults.resolve_model_and_settings().

Covers the full matrix of provider-specific effort mappings:
- OpenAI: reasoning_effort settings
- Anthropic adaptive (4.6): adaptive thinking + effort
- Anthropic native effort (Opus 4.5): enabled thinking + budget + effort
- Anthropic legacy budget (Sonnet 4.5, Haiku 4.5): enabled thinking + budget
- Google budget (Gemini 2.5): thinking_budget
- Google level (Gemini 3+): thinking_level
- No effort suffix: baseline settings
- Malformed specs: graceful handling
- Missing/unknown provider: empty settings
"""

from __future__ import annotations

import pytest

from gpd.core.model_defaults import (
    GPD_DEFAULT_FAST_MODEL,
    GPD_DEFAULT_MODEL,
    resolve_model_and_settings,
)

# =============================================================================
# Module-level constants
# =============================================================================


class TestModuleConstants:
    """Verify module-level model defaults are sensible."""

    def test_default_model_is_anthropic_sonnet(self):
        assert "anthropic:" in GPD_DEFAULT_MODEL
        assert "sonnet" in GPD_DEFAULT_MODEL

    def test_fast_model_is_anthropic_haiku(self):
        assert "anthropic:" in GPD_DEFAULT_FAST_MODEL
        assert "haiku" in GPD_DEFAULT_FAST_MODEL


# =============================================================================
# OpenAI — reasoning_effort
# =============================================================================


class TestOpenAIEffort:
    """OpenAI models use openai_reasoning_effort."""

    def test_openai_low(self):
        model, settings = resolve_model_and_settings("openai:gpt-5.2-low")
        assert model == "openai:gpt-5.2"
        assert settings["openai_reasoning_effort"] == "low"

    def test_openai_high(self):
        model, settings = resolve_model_and_settings("openai:gpt-5.2-high")
        assert model == "openai:gpt-5.2"
        assert settings["openai_reasoning_effort"] == "high"

    def test_openai_medium(self):
        model, settings = resolve_model_and_settings("openai:gpt-5.2-medium")
        assert model == "openai:gpt-5.2"
        assert settings["openai_reasoning_effort"] == "medium"

    def test_openai_xhigh(self):
        model, settings = resolve_model_and_settings("openai:gpt-5.2-xhigh")
        assert model == "openai:gpt-5.2"
        assert settings["openai_reasoning_effort"] == "xhigh"

    def test_openai_none(self):
        model, settings = resolve_model_and_settings("openai:gpt-5.2-none")
        assert model == "openai:gpt-5.2"
        # "none" effort produces no reasoning_effort key (or empty)
        assert settings.get("openai_reasoning_effort") == "none"

    def test_openai_reasoning_summary_for_active_effort(self):
        """Reasoning models with active effort get detailed summaries."""
        _, settings = resolve_model_and_settings("openai:gpt-5.2-high")
        assert settings.get("openai_reasoning_summary") == "detailed"

    def test_openai_no_reasoning_summary_for_none(self):
        """No reasoning summary when effort is 'none'."""
        _, settings = resolve_model_and_settings("openai:gpt-5.2-none")
        assert "openai_reasoning_summary" not in settings

    def test_openai_unsupported_effort(self):
        """gpt-5 doesn't support 'none' — should raise ValueError."""
        with pytest.raises(ValueError, match="Unsupported effort"):
            resolve_model_and_settings("openai:gpt-5-none")

    def test_openai_no_effort(self):
        """OpenAI without effort suffix returns empty settings."""
        model, settings = resolve_model_and_settings("openai:gpt-5.2")
        assert model == "openai:gpt-5.2"
        assert settings == {}


# =============================================================================
# Anthropic adaptive thinking (Opus 4.6, Sonnet 4.6)
# =============================================================================


class TestAnthropicAdaptive:
    """Anthropic 4.6 models use adaptive thinking + anthropic_effort."""

    def test_adaptive_low(self):
        model, settings = resolve_model_and_settings("anthropic:claude-opus-4-6-low")
        assert model == "anthropic:claude-opus-4-6"
        assert settings["anthropic_thinking"] == {"type": "adaptive"}
        assert settings["anthropic_effort"] == "low"

    def test_adaptive_medium(self):
        _, settings = resolve_model_and_settings("anthropic:claude-opus-4-6-medium")
        assert settings["anthropic_thinking"] == {"type": "adaptive"}
        assert settings["anthropic_effort"] == "medium"

    def test_adaptive_high(self):
        _, settings = resolve_model_and_settings("anthropic:claude-opus-4-6-high")
        assert settings["anthropic_thinking"] == {"type": "adaptive"}
        assert settings["anthropic_effort"] == "high"

    def test_adaptive_xhigh_opus(self):
        """Opus 4.6 supports xhigh → effort='max'."""
        _, settings = resolve_model_and_settings("anthropic:claude-opus-4-6-xhigh")
        assert settings["anthropic_thinking"] == {"type": "adaptive"}
        assert settings["anthropic_effort"] == "max"

    def test_adaptive_xhigh_not_on_sonnet(self):
        """Sonnet 4.6 does NOT support xhigh."""
        with pytest.raises(ValueError, match="Unsupported effort"):
            resolve_model_and_settings("anthropic:claude-sonnet-4-6-xhigh")

    def test_adaptive_none(self):
        """'none' effort disables thinking entirely."""
        _, settings = resolve_model_and_settings("anthropic:claude-opus-4-6-none")
        assert settings["anthropic_thinking"] == {"type": "disabled"}

    def test_adaptive_max_tokens_set(self):
        """Adaptive models include max_tokens."""
        _, settings = resolve_model_and_settings("anthropic:claude-opus-4-6-high")
        assert settings["max_tokens"] == 128_000

    def test_adaptive_sonnet_max_tokens(self):
        _, settings = resolve_model_and_settings("anthropic:claude-sonnet-4-6-high")
        assert settings["max_tokens"] == 64_000


# =============================================================================
# Anthropic adaptive — budget variant
# =============================================================================


class TestAnthropicBudgetVariant:
    """The '-budget' suffix forces manual budget on adaptive models."""

    def test_budget_variant_high(self):
        model, settings = resolve_model_and_settings("anthropic:claude-opus-4-6-high-budget")
        assert model == "anthropic:claude-opus-4-6"
        # Budget variant overrides to type=enabled with explicit budget_tokens
        assert settings["anthropic_thinking"]["type"] == "enabled"
        assert isinstance(settings["anthropic_thinking"]["budget_tokens"], int)
        assert settings["anthropic_thinking"]["budget_tokens"] > 0

    def test_budget_variant_none_raises(self):
        """'none-budget' is not allowed."""
        with pytest.raises(ValueError, match="none-budget"):
            resolve_model_and_settings("anthropic:claude-opus-4-6-none-budget")

    def test_budget_variant_on_legacy_raises(self):
        """Budget variant only works on adaptive (4.6) models."""
        with pytest.raises(ValueError, match="budget.*suffix"):
            resolve_model_and_settings("anthropic:claude-sonnet-4-5-high-budget")


# =============================================================================
# Anthropic native effort (Opus 4.5)
# =============================================================================


class TestAnthropicNativeEffort:
    """Opus 4.5 uses enabled thinking + budget + anthropic_effort."""

    def test_native_low(self):
        model, settings = resolve_model_and_settings("anthropic:claude-opus-4-5-low")
        assert model == "anthropic:claude-opus-4-5"
        assert settings["anthropic_thinking"]["type"] == "enabled"
        assert isinstance(settings["anthropic_thinking"]["budget_tokens"], int)
        assert settings["anthropic_effort"] == "low"

    def test_native_high(self):
        _, settings = resolve_model_and_settings("anthropic:claude-opus-4-5-high")
        assert settings["anthropic_thinking"]["type"] == "enabled"
        assert settings["anthropic_effort"] == "high"

    def test_native_none(self):
        _, settings = resolve_model_and_settings("anthropic:claude-opus-4-5-none")
        assert settings["anthropic_thinking"] == {"type": "disabled"}

    def test_native_max_tokens(self):
        _, settings = resolve_model_and_settings("anthropic:claude-opus-4-5-medium")
        assert settings["max_tokens"] == 64_000


# =============================================================================
# Anthropic legacy budget (Sonnet 4.5, Haiku 4.5)
# =============================================================================


class TestAnthropicLegacyBudget:
    """Legacy models use enabled thinking with explicit budget_tokens."""

    def test_legacy_low(self):
        model, settings = resolve_model_and_settings("anthropic:claude-sonnet-4-5-low")
        assert model == "anthropic:claude-sonnet-4-5"
        assert settings["anthropic_thinking"]["type"] == "enabled"
        assert settings["anthropic_thinking"]["budget_tokens"] == 8_000

    def test_legacy_medium(self):
        _, settings = resolve_model_and_settings("anthropic:claude-sonnet-4-5-medium")
        assert settings["anthropic_thinking"]["budget_tokens"] == 32_000

    def test_legacy_high(self):
        _, settings = resolve_model_and_settings("anthropic:claude-sonnet-4-5-high")
        assert settings["anthropic_thinking"]["budget_tokens"] == 62_000

    def test_legacy_minimal(self):
        _, settings = resolve_model_and_settings("anthropic:claude-sonnet-4-5-minimal")
        assert settings["anthropic_thinking"]["budget_tokens"] == 1024

    def test_legacy_none(self):
        _, settings = resolve_model_and_settings("anthropic:claude-sonnet-4-5-none")
        assert settings["anthropic_thinking"] == {"type": "disabled"}

    def test_legacy_haiku(self):
        model, settings = resolve_model_and_settings("anthropic:claude-haiku-4-5-medium")
        assert model == "anthropic:claude-haiku-4-5"
        assert settings["anthropic_thinking"]["type"] == "enabled"

    def test_legacy_no_anthropic_effort(self):
        """Legacy models do NOT set anthropic_effort (only budget_tokens)."""
        _, settings = resolve_model_and_settings("anthropic:claude-sonnet-4-5-high")
        assert "anthropic_effort" not in settings


# =============================================================================
# Anthropic context features (prompt caching, betas)
# =============================================================================


class TestAnthropicContextFeatures:
    """All Anthropic models with effort get prompt caching + betas."""

    def test_prompt_caching_enabled(self):
        _, settings = resolve_model_and_settings("anthropic:claude-opus-4-6-high")
        assert settings["anthropic_cache_instructions"] is True
        assert settings["anthropic_cache_tool_definitions"] is True

    def test_1m_context_beta(self):
        """Opus 4.6 and Sonnet 4.6 support 1M context beta."""
        _, settings = resolve_model_and_settings("anthropic:claude-opus-4-6-high")
        betas = settings.get("anthropic_betas", [])
        assert "context-1m-2025-08-07" in betas

    def test_compaction_beta(self):
        """Opus 4.6 and Sonnet 4.6 support server-side compaction."""
        _, settings = resolve_model_and_settings("anthropic:claude-sonnet-4-6-high")
        betas = settings.get("anthropic_betas", [])
        assert "compact-2026-01-12" in betas

    def test_compaction_extra_body(self):
        """Compaction sets extra_body context_management."""
        _, settings = resolve_model_and_settings("anthropic:claude-opus-4-6-high")
        extra_body = settings.get("extra_body", {})
        cm = extra_body.get("context_management", {})
        edits = cm.get("edits", [])
        assert any(e.get("type") == "compact_20260112" for e in edits)

    def test_no_compaction_for_legacy(self):
        """Legacy models (Sonnet 4.5) do NOT get compaction beta."""
        _, settings = resolve_model_and_settings("anthropic:claude-sonnet-4-5-high")
        betas = settings.get("anthropic_betas", [])
        assert "compact-2026-01-12" not in betas

    def test_baseline_settings_include_caching(self):
        """Anthropic models without effort still get prompt caching."""
        _, settings = resolve_model_and_settings("anthropic:claude-opus-4-6")
        assert settings["anthropic_cache_instructions"] is True


# =============================================================================
# Google — Gemini 2.5 (budget-based)
# =============================================================================


class TestGoogleBudget:
    """Gemini 2.5 models use google_thinking_config with thinking_budget."""

    def test_gemini_25_pro_low(self):
        model, settings = resolve_model_and_settings("google:gemini-2.5-pro-low")
        assert model == "google:gemini-2.5-pro"
        tc = settings["google_thinking_config"]
        assert tc["thinking_budget"] == 4096
        assert tc["include_thoughts"] is True

    def test_gemini_25_pro_high(self):
        _, settings = resolve_model_and_settings("google:gemini-2.5-pro-high")
        tc = settings["google_thinking_config"]
        assert tc["thinking_budget"] == 32768

    def test_gemini_25_flash_none(self):
        """Gemini 2.5 Flash supports 'none' → budget=0."""
        model, settings = resolve_model_and_settings("google:gemini-2.5-flash-none")
        assert model == "google:gemini-2.5-flash"
        tc = settings["google_thinking_config"]
        assert tc["thinking_budget"] == 0

    def test_gemini_25_pro_no_none(self):
        """Gemini 2.5 Pro does NOT support 'none' effort."""
        with pytest.raises(ValueError, match="Unsupported effort"):
            resolve_model_and_settings("google:gemini-2.5-pro-none")

    def test_gemini_25_no_effort(self):
        """Google models without effort get empty settings."""
        model, settings = resolve_model_and_settings("google:gemini-2.5-pro")
        assert model == "google:gemini-2.5-pro"
        assert settings == {}


# =============================================================================
# Google — Gemini 3+ (level-based)
# =============================================================================


class TestGoogleLevel:
    """Gemini 3+ models use google_thinking_config with thinking_level."""

    def test_gemini_3_pro_low(self):
        model, settings = resolve_model_and_settings("google:gemini-3-pro-preview-low")
        assert model == "google:gemini-3-pro-preview"
        tc = settings["google_thinking_config"]
        assert tc["thinking_level"] == "low"
        assert tc["include_thoughts"] is True

    def test_gemini_3_pro_high(self):
        _, settings = resolve_model_and_settings("google:gemini-3-pro-preview-high")
        assert settings["google_thinking_config"]["thinking_level"] == "high"

    def test_gemini_3_flash_medium(self):
        model, settings = resolve_model_and_settings("google:gemini-3-flash-preview-medium")
        assert model == "google:gemini-3-flash-preview"
        assert settings["google_thinking_config"]["thinking_level"] == "medium"

    def test_gemini_3_flash_no_none(self):
        """Gemini 3 Flash cannot disable thinking."""
        with pytest.raises(ValueError, match="Unsupported effort"):
            resolve_model_and_settings("google:gemini-3-flash-preview-none")


# =============================================================================
# No effort suffix — baseline settings
# =============================================================================


class TestNoEffortSuffix:
    """Models without effort suffix return baseline settings."""

    def test_anthropic_baseline_has_max_tokens(self):
        model, settings = resolve_model_and_settings("anthropic:claude-sonnet-4-5-20250929")
        assert model == "anthropic:claude-sonnet-4-5-20250929"
        assert "max_tokens" in settings

    def test_anthropic_baseline_has_caching(self):
        _, settings = resolve_model_and_settings("anthropic:claude-opus-4-6")
        assert settings.get("anthropic_cache_instructions") is True

    def test_openai_baseline_empty(self):
        model, settings = resolve_model_and_settings("openai:gpt-5.2")
        assert model == "openai:gpt-5.2"
        assert settings == {}

    def test_google_baseline_empty(self):
        model, settings = resolve_model_and_settings("google:gemini-2.5-pro")
        assert model == "google:gemini-2.5-pro"
        assert settings == {}


# =============================================================================
# Malformed and edge-case specs
# =============================================================================


class TestMalformedSpecs:
    """Graceful handling of unusual model spec strings."""

    def test_no_provider_prefix(self):
        """Bare model name without 'provider:' prefix."""
        model, settings = resolve_model_and_settings("gpt-5.2")
        assert model == "gpt-5.2"
        assert settings == {}

    def test_no_provider_with_effort(self):
        """Bare model with effort suffix — empty provider can't look up catalog."""
        with pytest.raises(ValueError, match="Unknown model"):
            resolve_model_and_settings("gpt-5.2-low")

    def test_unknown_provider(self):
        """Unknown provider returns empty settings."""
        model, settings = resolve_model_and_settings("unknownprovider:some-model")
        assert model == "unknownprovider:some-model"
        assert settings == {}

    def test_unknown_provider_with_effort(self):
        """Unknown provider with effort suffix → ValueError from effort_to_model_settings."""
        with pytest.raises(ValueError, match="Unknown model"):
            resolve_model_and_settings("unknownprovider:some-model-high")

    def test_invalid_effort_level(self):
        """Effort string that isn't in EFFORT_LEVELS isn't parsed as effort."""
        # "turbo" is not a recognized effort level, so parse_model_spec treats
        # the whole string as the model name → no effort → empty settings
        model, settings = resolve_model_and_settings("openai:gpt-5.2-turbo")
        assert model == "openai:gpt-5.2-turbo"
        assert settings == {}

    def test_empty_string(self):
        """Empty spec returns identity."""
        model, settings = resolve_model_and_settings("")
        assert model == ""
        assert settings == {}

    def test_provider_only(self):
        """'openai:' (empty model part) — returns as-is with empty settings."""
        model, settings = resolve_model_and_settings("openai:")
        assert model == "openai:"
        assert settings == {}


# =============================================================================
# Settings are copies (mutation safety)
# =============================================================================


class TestSettingsIsolation:
    """Verify that returned settings are independent copies."""

    def test_mutation_does_not_affect_registry(self):
        """Mutating returned settings must not affect future calls."""
        _, settings1 = resolve_model_and_settings("openai:gpt-5.2-high")
        settings1["openai_reasoning_effort"] = "MUTATED"

        _, settings2 = resolve_model_and_settings("openai:gpt-5.2-high")
        assert settings2["openai_reasoning_effort"] == "high"

    def test_anthropic_mutation_safe(self):
        _, settings1 = resolve_model_and_settings("anthropic:claude-opus-4-6-high")
        settings1["anthropic_thinking"] = "MUTATED"

        _, settings2 = resolve_model_and_settings("anthropic:claude-opus-4-6-high")
        assert settings2["anthropic_thinking"] == {"type": "adaptive"}


# =============================================================================
# Integration: provider-specific key correctness
# =============================================================================

# Canonical PydanticAI key names per provider — if these ever change upstream,
# the tests below will catch the silent breakage.
_OPENAI_EFFORT_KEYS = frozenset({"openai_reasoning_effort", "openai_reasoning_summary"})
_ANTHROPIC_EFFORT_KEYS = frozenset(
    {
        "anthropic_thinking",
        "anthropic_effort",
        "max_tokens",
        "anthropic_cache_instructions",
        "anthropic_cache_tool_definitions",
        "anthropic_betas",
        "extra_body",
    }
)
_GOOGLE_EFFORT_KEYS = frozenset({"google_thinking_config"})


class TestProviderKeyExclusivity:
    """Verify that each provider produces ONLY its own keys — no cross-provider leakage."""

    @pytest.mark.parametrize(
        "spec",
        [
            "openai:gpt-5.2-low",
            "openai:gpt-5.2-medium",
            "openai:gpt-5.2-high",
            "openai:gpt-5.2-xhigh",
        ],
    )
    def test_openai_keys_never_contain_anthropic_or_google(self, spec: str):
        _, settings = resolve_model_and_settings(spec)
        for key in settings:
            assert not key.startswith("anthropic_"), f"OpenAI settings leaked Anthropic key: {key}"
            assert not key.startswith("google_"), f"OpenAI settings leaked Google key: {key}"
            assert key in _OPENAI_EFFORT_KEYS, f"Unexpected key {key!r} in OpenAI settings"

    @pytest.mark.parametrize(
        "spec",
        [
            "anthropic:claude-opus-4-6-low",
            "anthropic:claude-opus-4-6-high",
            "anthropic:claude-sonnet-4-5-medium",
            "anthropic:claude-opus-4-5-high",
            "anthropic:claude-haiku-4-5-medium",
        ],
    )
    def test_anthropic_keys_never_contain_openai_or_google(self, spec: str):
        _, settings = resolve_model_and_settings(spec)
        for key in settings:
            assert not key.startswith("openai_"), f"Anthropic settings leaked OpenAI key: {key}"
            assert not key.startswith("google_"), f"Anthropic settings leaked Google key: {key}"
            assert key in _ANTHROPIC_EFFORT_KEYS, f"Unexpected key {key!r} in Anthropic settings"

    @pytest.mark.parametrize(
        "spec",
        [
            "google:gemini-2.5-pro-low",
            "google:gemini-2.5-pro-high",
            "google:gemini-3-pro-preview-low",
            "google:gemini-3-flash-preview-low",
        ],
    )
    def test_google_keys_never_contain_openai_or_anthropic(self, spec: str):
        _, settings = resolve_model_and_settings(spec)
        for key in settings:
            assert not key.startswith("openai_"), f"Google settings leaked OpenAI key: {key}"
            assert not key.startswith("anthropic_"), f"Google settings leaked Anthropic key: {key}"
            assert key in _GOOGLE_EFFORT_KEYS, f"Unexpected key {key!r} in Google settings"


class TestExactProviderKeyNames:
    """Verify resolve_model_and_settings produces the EXACT PydanticAI key names.

    These tests catch silent API changes — if PydanticAI renames a settings key
    or if a refactor introduces a typo, these will fail immediately.
    """

    def test_openai_produces_openai_reasoning_effort_key(self):
        """The EXACT key must be 'openai_reasoning_effort', not 'reasoning_effort'."""
        _, settings = resolve_model_and_settings("openai:gpt-5.2-high")
        assert "openai_reasoning_effort" in settings, (
            "Missing 'openai_reasoning_effort' — PydanticAI requires the provider-prefixed key"
        )
        # Must NOT contain the generic non-prefixed key
        assert "reasoning_effort" not in settings, (
            "Found generic 'reasoning_effort' — PydanticAI silently drops this for OpenAI"
        )

    def test_anthropic_produces_anthropic_thinking_key(self):
        """The EXACT key must be 'anthropic_thinking', not 'thinking'."""
        _, settings = resolve_model_and_settings("anthropic:claude-opus-4-6-high")
        assert "anthropic_thinking" in settings, (
            "Missing 'anthropic_thinking' — PydanticAI requires the provider-prefixed key"
        )
        assert "thinking" not in settings, "Found generic 'thinking' — PydanticAI silently drops this for Anthropic"

    def test_anthropic_adaptive_thinking_shape(self):
        """Adaptive thinking must be {'type': 'adaptive'}, not just a string."""
        _, settings = resolve_model_and_settings("anthropic:claude-sonnet-4-6-medium")
        thinking = settings["anthropic_thinking"]
        assert isinstance(thinking, dict), f"Expected dict, got {type(thinking).__name__}"
        assert thinking["type"] == "adaptive"

    def test_anthropic_legacy_thinking_shape(self):
        """Legacy thinking must be {'type': 'enabled', 'budget_tokens': <int>}."""
        _, settings = resolve_model_and_settings("anthropic:claude-sonnet-4-5-high")
        thinking = settings["anthropic_thinking"]
        assert isinstance(thinking, dict), f"Expected dict, got {type(thinking).__name__}"
        assert thinking["type"] == "enabled"
        assert "budget_tokens" in thinking
        assert isinstance(thinking["budget_tokens"], int)

    def test_anthropic_disabled_thinking_shape(self):
        """Disabled thinking must be {'type': 'disabled'}, nothing else."""
        _, settings = resolve_model_and_settings("anthropic:claude-opus-4-6-none")
        thinking = settings["anthropic_thinking"]
        assert thinking == {"type": "disabled"}

    def test_anthropic_effort_key_for_adaptive(self):
        """Adaptive models must produce 'anthropic_effort', not 'effort'."""
        _, settings = resolve_model_and_settings("anthropic:claude-opus-4-6-medium")
        assert "anthropic_effort" in settings, "Missing 'anthropic_effort' — required for adaptive thinking models"
        assert "effort" not in settings

    def test_anthropic_effort_key_for_native(self):
        """Native effort models (Opus 4.5) must also produce 'anthropic_effort'."""
        _, settings = resolve_model_and_settings("anthropic:claude-opus-4-5-high")
        assert "anthropic_effort" in settings

    def test_google_produces_google_thinking_config_key(self):
        """The EXACT key must be 'google_thinking_config', not 'thinking_config'."""
        _, settings = resolve_model_and_settings("google:gemini-2.5-pro-high")
        assert "google_thinking_config" in settings, (
            "Missing 'google_thinking_config' — PydanticAI requires the provider-prefixed key"
        )
        assert "thinking_config" not in settings, (
            "Found generic 'thinking_config' — PydanticAI silently drops this for Google"
        )

    def test_google_budget_thinking_config_shape(self):
        """Gemini 2.5 must produce {'thinking_budget': <int>, 'include_thoughts': True}."""
        _, settings = resolve_model_and_settings("google:gemini-2.5-pro-low")
        tc = settings["google_thinking_config"]
        assert isinstance(tc, dict), f"Expected dict, got {type(tc).__name__}"
        assert "thinking_budget" in tc
        assert isinstance(tc["thinking_budget"], int)
        assert tc["include_thoughts"] is True

    def test_google_level_thinking_config_shape(self):
        """Gemini 3+ must produce {'thinking_level': <str>, 'include_thoughts': True}."""
        _, settings = resolve_model_and_settings("google:gemini-3-pro-preview-high")
        tc = settings["google_thinking_config"]
        assert isinstance(tc, dict), f"Expected dict, got {type(tc).__name__}"
        assert "thinking_level" in tc
        assert isinstance(tc["thinking_level"], str)
        assert tc["include_thoughts"] is True


class TestCrossProviderConsistency:
    """Verify the same effort level produces structurally different but correct
    settings for each provider — exercising the full resolve_model_and_settings
    pipeline end-to-end across all three providers simultaneously.
    """

    @pytest.mark.parametrize("effort", ["low", "medium", "high"])
    def test_same_effort_produces_correct_keys_per_provider(self, effort: str):
        """For a given effort, all three providers must produce their own key shape."""
        _, openai_settings = resolve_model_and_settings(f"openai:gpt-5.2-{effort}")
        _, anthropic_settings = resolve_model_and_settings(f"anthropic:claude-opus-4-6-{effort}")
        _, google_settings = resolve_model_and_settings(f"google:gemini-2.5-pro-{effort}")

        # OpenAI: must have openai_reasoning_effort
        assert "openai_reasoning_effort" in openai_settings
        assert openai_settings["openai_reasoning_effort"] == effort

        # Anthropic: must have anthropic_thinking + anthropic_effort
        assert "anthropic_thinking" in anthropic_settings
        assert "anthropic_effort" in anthropic_settings

        # Google: must have google_thinking_config
        assert "google_thinking_config" in google_settings

        # Cross-check: no key overlap between OpenAI and Google
        assert not set(openai_settings) & set(google_settings), (
            f"OpenAI and Google settings share keys: {set(openai_settings) & set(google_settings)}"
        )
