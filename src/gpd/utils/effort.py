"""Provider-specific effort and output token mappings (standalone).

Inlined from ``inference_providers.effort`` + ``inference_providers.models``
so GPD can resolve model specs standalone.

Core API:
    parse_model_spec(spec) -> (provider, base_model, effort_or_None)
    effort_to_model_settings(provider, model, effort) -> dict
    base_model_settings(provider, model) -> dict
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field

# =============================================================================
# ModelSpec types (from inference_providers.models.spec)
# =============================================================================


class ThinkingMode(enum.Enum):
    """How a model implements reasoning/thinking."""

    DISABLED = "disabled"
    ADAPTIVE = "adaptive"
    NATIVE_EFFORT = "native_effort"
    LEGACY_BUDGET = "legacy_budget"
    OPENAI_EFFORT = "openai_effort"
    GEMINI_BUDGET = "gemini_budget"
    GEMINI_LEVEL = "gemini_level"
    SUPPRESSED = "suppressed"


def _dict_signature(d: dict[str, object]) -> str:
    return repr(sorted((k, repr(v)) for k, v in d.items()))


@dataclass(frozen=True)
class ModelSpec:
    """Single source of truth for one model's capabilities."""

    name: str
    provider: str
    thinking_mode: ThinkingMode
    max_output_tokens: int | None
    valid_efforts: tuple[str, ...]
    effort_settings: dict[str, dict[str, object]] = field(default_factory=dict)
    supports_code: bool = True
    supports_web: bool = True
    aliases: tuple[str, ...] = ()
    inspect_model: str = ""
    pricing_fallback: tuple[str, str] | None = None

    def __post_init__(self) -> None:
        for e in self.valid_efforts:
            if e not in self.effort_settings:
                raise ValueError(
                    f"ModelSpec({self.name!r}): effort {e!r} in valid_efforts but missing from effort_settings"
                )
        seen: dict[str, str] = {}
        for e in self.valid_efforts:
            key = _dict_signature(self.effort_settings[e])
            if key in seen:
                raise ValueError(
                    f"ModelSpec({self.name!r}): efforts {seen[key]!r} and {e!r} produce identical settings"
                )
            seen[key] = e


# =============================================================================
# Budget constants
# =============================================================================

ANTHROPIC_THINKING_BUDGET_MINIMAL = 1024
ANTHROPIC_THINKING_BUDGET_LOW = 8_000
ANTHROPIC_THINKING_BUDGET_MEDIUM = 32_000
ANTHROPIC_THINKING_BUDGET_HIGH = 62_000
ANTHROPIC_DEFAULT_MAX_OUTPUT_TOKENS = 64_000
ANTHROPIC_THINKING_BUDGET_HEADROOM_TOKENS = 2_000

_LEGACY_BUDGETS: dict[str, int] = {
    "minimal": ANTHROPIC_THINKING_BUDGET_MINIMAL,
    "low": ANTHROPIC_THINKING_BUDGET_LOW,
    "medium": ANTHROPIC_THINKING_BUDGET_MEDIUM,
    "high": ANTHROPIC_THINKING_BUDGET_HIGH,
}

# =============================================================================
# Anthropic context window betas
# =============================================================================

ANTHROPIC_BETA_CONTEXT_1M = "context-1m-2025-08-07"
ANTHROPIC_BETA_COMPACTION = "compact-2026-01-12"
ANTHROPIC_COMPACTION_EDIT_TYPE = "compact_20260112"

_ANTHROPIC_1M_CONTEXT_SPECS: frozenset[str] = frozenset(
    {"claude-opus-4-6", "claude-sonnet-4-6", "claude-sonnet-4-5", "claude-sonnet-4-0"}
)

_ANTHROPIC_COMPACTION_SPECS: frozenset[str] = frozenset({"claude-opus-4-6", "claude-sonnet-4-6"})


def _append_unique_str(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)


def _apply_anthropic_context_features(settings: dict[str, object], *, spec_name: str) -> None:
    """Mutate *settings* to enable Anthropic context features (where supported)."""
    settings["anthropic_cache_instructions"] = True
    settings["anthropic_cache_tool_definitions"] = True

    if spec_name in _ANTHROPIC_1M_CONTEXT_SPECS:
        betas = settings.get("anthropic_betas")
        if not isinstance(betas, list):
            betas = []
        betas = [str(b) for b in betas]
        _append_unique_str(betas, ANTHROPIC_BETA_CONTEXT_1M)
        settings["anthropic_betas"] = betas

    if spec_name in _ANTHROPIC_COMPACTION_SPECS:
        betas = settings.get("anthropic_betas")
        if not isinstance(betas, list):
            betas = []
        betas = [str(b) for b in betas]
        _append_unique_str(betas, ANTHROPIC_BETA_COMPACTION)
        settings["anthropic_betas"] = betas

        extra_body = settings.get("extra_body")
        if not isinstance(extra_body, dict):
            extra_body = {}
        extra_body = dict(extra_body)

        cm = extra_body.get("context_management")
        if not isinstance(cm, dict):
            cm = {}
        cm = dict(cm)

        edits = cm.get("edits")
        if not isinstance(edits, list):
            edits = []
        edits = list(edits)

        has_compact = any(isinstance(e, dict) and e.get("type") == ANTHROPIC_COMPACTION_EDIT_TYPE for e in edits)
        if not has_compact:
            edits.append({"type": ANTHROPIC_COMPACTION_EDIT_TYPE})

        cm["edits"] = edits
        extra_body["context_management"] = cm
        settings["extra_body"] = extra_body


# =============================================================================
# Anthropic builder helpers (from catalog.py)
# =============================================================================

_ANTHROPIC_EFFORT_MAP: dict[str, str] = {"low": "low", "medium": "medium", "high": "high"}


def _anthropic_max_budget_tokens(max_output: int) -> int:
    return max(1, max_output - ANTHROPIC_THINKING_BUDGET_HEADROOM_TOKENS)


def _anthropic_adaptive_spec(
    name: str,
    max_output: int,
    *,
    supports_max: bool = False,
    aliases: tuple[str, ...] = (),
    inspect_model: str = "",
) -> ModelSpec:
    settings: dict[str, dict[str, object]] = {
        "none": {"anthropic_thinking": {"type": "disabled"}, "max_tokens": max_output},
    }
    efforts = ["none"]
    for effort_level, api_effort in _ANTHROPIC_EFFORT_MAP.items():
        settings[effort_level] = {
            "anthropic_thinking": {"type": "adaptive"},
            "max_tokens": max_output,
            "anthropic_effort": api_effort,
        }
        efforts.append(effort_level)
    if supports_max:
        settings["xhigh"] = {
            "anthropic_thinking": {"type": "adaptive"},
            "max_tokens": max_output,
            "anthropic_effort": "max",
        }
        efforts.append("xhigh")
    return ModelSpec(
        name=name,
        provider="anthropic",
        thinking_mode=ThinkingMode.ADAPTIVE,
        max_output_tokens=max_output,
        valid_efforts=tuple(efforts),
        effort_settings=settings,
        aliases=aliases,
        inspect_model=inspect_model,
    )


def _anthropic_native_effort_spec(
    name: str,
    max_output: int,
    *,
    aliases: tuple[str, ...] = (),
    inspect_model: str = "",
) -> ModelSpec:
    budget = _anthropic_max_budget_tokens(max_output)
    settings: dict[str, dict[str, object]] = {
        "none": {"anthropic_thinking": {"type": "disabled"}, "max_tokens": max_output},
    }
    efforts = ["none"]
    for effort_level, api_effort in _ANTHROPIC_EFFORT_MAP.items():
        settings[effort_level] = {
            "anthropic_thinking": {"type": "enabled", "budget_tokens": budget},
            "max_tokens": max_output,
            "anthropic_effort": api_effort,
        }
        efforts.append(effort_level)
    return ModelSpec(
        name=name,
        provider="anthropic",
        thinking_mode=ThinkingMode.NATIVE_EFFORT,
        max_output_tokens=max_output,
        valid_efforts=tuple(efforts),
        effort_settings=settings,
        aliases=aliases,
        inspect_model=inspect_model,
    )


def _anthropic_legacy_spec(
    name: str,
    max_output: int,
    *,
    aliases: tuple[str, ...] = (),
    inspect_model: str = "",
) -> ModelSpec:
    settings: dict[str, dict[str, object]] = {
        "none": {"anthropic_thinking": {"type": "disabled"}, "max_tokens": max_output},
    }
    efforts = ["none"]
    seen_budgets: dict[int, str] = {}
    for effort_level in ("minimal", "low", "medium", "high"):
        raw = _LEGACY_BUDGETS[effort_level]
        capped = min(raw, _anthropic_max_budget_tokens(max_output))
        if capped in seen_budgets:
            continue
        seen_budgets[capped] = effort_level
        settings[effort_level] = {
            "anthropic_thinking": {"type": "enabled", "budget_tokens": capped},
            "max_tokens": max_output,
        }
        efforts.append(effort_level)
    return ModelSpec(
        name=name,
        provider="anthropic",
        thinking_mode=ThinkingMode.LEGACY_BUDGET,
        max_output_tokens=max_output,
        valid_efforts=tuple(efforts),
        effort_settings=settings,
        aliases=aliases,
        inspect_model=inspect_model,
    )


# =============================================================================
# OpenAI builder helpers
# =============================================================================


def _openai_spec(
    name: str,
    allowed_efforts: frozenset[str],
    *,
    aliases: tuple[str, ...] = (),
    inspect_model: str = "",
    supports_code: bool = True,
    supports_web: bool = True,
) -> ModelSpec:
    settings: dict[str, dict[str, object]] = {}
    efforts: list[str] = []
    is_single = len(allowed_efforts) == 1
    for e in ("none", "minimal", "low", "medium", "high", "xhigh"):
        if e not in allowed_efforts:
            continue
        if is_single:
            settings[e] = {}
        else:
            s: dict[str, object] = {"openai_reasoning_effort": e}
            is_non_reasoning = allowed_efforts == frozenset({"none"})
            if not is_non_reasoning and e != "none":
                s["openai_reasoning_summary"] = "detailed"
            settings[e] = s
        efforts.append(e)
    if allowed_efforts == frozenset({"none"}):
        mode = ThinkingMode.DISABLED
    elif is_single:
        mode = ThinkingMode.SUPPRESSED
    else:
        mode = ThinkingMode.OPENAI_EFFORT
    return ModelSpec(
        name=name,
        provider="openai",
        thinking_mode=mode,
        max_output_tokens=None,
        valid_efforts=tuple(efforts),
        effort_settings=settings,
        supports_code=supports_code,
        supports_web=supports_web,
        aliases=aliases,
        inspect_model=inspect_model,
    )


# =============================================================================
# Google builder helpers
# =============================================================================


def _google_budget_spec(
    name: str,
    budgets: dict[str, int],
    *,
    aliases: tuple[str, ...] = (),
    inspect_model: str = "",
) -> ModelSpec:
    settings: dict[str, dict[str, object]] = {}
    efforts: list[str] = []
    for e in ("none", "minimal", "low", "medium", "high"):
        if e not in budgets:
            continue
        budget = budgets[e]
        config: dict[str, object] = {"thinking_budget": budget}
        if budget > 0:
            config["include_thoughts"] = True
        settings[e] = {"google_thinking_config": config}
        efforts.append(e)
    return ModelSpec(
        name=name,
        provider="google",
        thinking_mode=ThinkingMode.GEMINI_BUDGET,
        max_output_tokens=None,
        valid_efforts=tuple(efforts),
        effort_settings=settings,
        aliases=aliases,
        inspect_model=inspect_model,
    )


def _google_level_spec(
    name: str,
    levels: dict[str, str],
    *,
    aliases: tuple[str, ...] = (),
    inspect_model: str = "",
    pricing_fallback: tuple[str, str] | None = None,
) -> ModelSpec:
    settings: dict[str, dict[str, object]] = {}
    efforts: list[str] = []
    seen_levels: dict[str, str] = {}
    for e in ("none", "minimal", "low", "medium", "high"):
        if e not in levels:
            continue
        level = levels[e]
        if level in seen_levels:
            continue
        seen_levels[level] = e
        settings[e] = {"google_thinking_config": {"thinking_level": level, "include_thoughts": True}}
        efforts.append(e)
    return ModelSpec(
        name=name,
        provider="google",
        thinking_mode=ThinkingMode.GEMINI_LEVEL,
        max_output_tokens=None,
        valid_efforts=tuple(efforts),
        effort_settings=settings,
        aliases=aliases,
        inspect_model=inspect_model,
        pricing_fallback=pricing_fallback,
    )


# =============================================================================
# Suppressed-effort builder (xAI, DeepSeek, Moonshot)
# =============================================================================

MOONSHOT_128K_CONTEXT_TOKENS = 131_072
MOONSHOT_256K_CONTEXT_TOKENS = 262_144


def _suppressed_spec(
    name: str,
    provider: str,
    *,
    canonical_effort: str = "high",
    max_output_tokens: int | None = None,
    aliases: tuple[str, ...] = (),
    inspect_model: str = "",
    supports_code: bool = False,
    supports_web: bool = False,
    pricing_fallback: tuple[str, str] | None = None,
) -> ModelSpec:
    mode = ThinkingMode.SUPPRESSED if canonical_effort != "none" else ThinkingMode.DISABLED
    settings = {"max_tokens": max_output_tokens} if max_output_tokens is not None else {}
    return ModelSpec(
        name=name,
        provider=provider,
        thinking_mode=mode,
        max_output_tokens=max_output_tokens,
        valid_efforts=(canonical_effort,),
        effort_settings={canonical_effort: settings},
        supports_code=supports_code,
        supports_web=supports_web,
        aliases=aliases,
        inspect_model=inspect_model,
        pricing_fallback=pricing_fallback,
    )


# =============================================================================
# The catalog — every supported model
# =============================================================================

_ALL_SPECS: list[ModelSpec] = [
    # Anthropic — adaptive thinking
    _anthropic_adaptive_spec("claude-opus-4-6", 128_000, supports_max=True, aliases=("opus-4.6",)),
    _anthropic_adaptive_spec("claude-sonnet-4-6", 64_000, aliases=("sonnet-4.6",)),
    # Anthropic — native effort
    _anthropic_native_effort_spec("claude-opus-4-5", 64_000, aliases=("opus-4.5",)),
    # Anthropic — legacy budget
    _anthropic_legacy_spec("claude-sonnet-4-5", 64_000, aliases=("sonnet-4.5",)),
    _anthropic_legacy_spec("claude-haiku-4-5", 64_000, aliases=("haiku-4.5",)),
    _anthropic_legacy_spec("claude-opus-4-1", 32_000, aliases=("opus-4.1",)),
    _anthropic_legacy_spec("claude-opus-4-0", 32_000, aliases=("opus-4.0", "opus-4")),
    _anthropic_legacy_spec("claude-sonnet-4-0", 64_000, aliases=("sonnet-4.0", "sonnet-4")),
    # OpenAI
    _openai_spec("gpt-5", frozenset({"minimal", "low", "medium", "high"}), aliases=("gpt-5",)),
    _openai_spec("gpt-5.1", frozenset({"none", "low", "medium", "high"}), aliases=("gpt-5.1",)),
    _openai_spec("gpt-5.2", frozenset({"none", "low", "medium", "high", "xhigh"}), aliases=("gpt-5.2",)),
    _openai_spec("gpt-5.4", frozenset({"none", "low", "medium", "high", "xhigh"}), aliases=("gpt-5.4",)),
    _openai_spec("gpt-5-mini", frozenset({"minimal", "low", "medium", "high"}), aliases=("gpt-5-mini",)),
    _openai_spec("gpt-5-nano", frozenset({"minimal", "low", "medium", "high"}), supports_web=False, aliases=("gpt-5-nano",)),
    _openai_spec("gpt-5-pro", frozenset({"high"}), supports_code=False, aliases=("gpt-5-pro",)),
    _openai_spec("gpt-5.4-pro", frozenset({"medium", "high", "xhigh"}), supports_code=False, aliases=("gpt-5.4-pro",)),
    _openai_spec("gpt-4o", frozenset({"none"}), aliases=("gpt-4o",)),
    _openai_spec("o3", frozenset({"low", "medium", "high"}), aliases=("o3",)),
    _openai_spec("o3-pro", frozenset({"high"}), aliases=("o3-pro",)),
    _openai_spec("o4-mini", frozenset({"low", "medium", "high"}), aliases=("o4-mini",)),
    _openai_spec("gpt-5-chat", frozenset({"none"})),
    _openai_spec("gpt-5-codex", frozenset({"low", "medium", "high"})),
    _openai_spec("gpt-5.1-codex-max", frozenset({"none", "low", "medium", "high", "xhigh"})),
    _openai_spec("gpt-5.1-codex-mini", frozenset({"none", "low", "medium", "high", "xhigh"})),
    _openai_spec("gpt-5.1-codex", frozenset({"none", "low", "medium", "high", "xhigh"})),
    _openai_spec("gpt-5.1-chat", frozenset({"none"})),
    _openai_spec("gpt-5.2-pro", frozenset({"medium", "high", "xhigh"})),
    _openai_spec("gpt-5.2-codex", frozenset({"low", "medium", "high", "xhigh"})),
    _openai_spec("gpt-5.2-chat", frozenset({"medium"})),
    _openai_spec("gpt-5.3-codex-spark", frozenset({"low", "medium", "high", "xhigh"})),
    _openai_spec("gpt-5.3-codex", frozenset({"low", "medium", "high", "xhigh"})),
    _openai_spec("o3-mini", frozenset({"low", "medium", "high"})),
    _openai_spec("o1", frozenset({"low", "medium", "high"})),
    # Google — Gemini 2.5 (budget-based)
    _google_budget_spec("gemini-2.5-pro", {"minimal": 128, "low": 4096, "medium": 16384, "high": 32768}, aliases=("gemini-2.5-pro",)),
    _google_budget_spec("gemini-2.5-flash", {"none": 0, "minimal": 128, "low": 4096, "medium": 16384, "high": 24576}, aliases=("gemini-2.5-flash",)),
    _google_budget_spec("gemini-2.5-flash-lite", {"none": 0, "minimal": 512, "low": 4096, "medium": 16384, "high": 24576}),
    # Google — Gemini 3+ (level-based)
    _google_level_spec("gemini-3-pro-preview", {"low": "low", "high": "high"}, aliases=("gemini-3-pro",)),
    _google_level_spec("gemini-3-flash-preview", {"minimal": "minimal", "low": "low", "medium": "medium", "high": "high"}, aliases=("gemini-3-flash",)),
    _google_level_spec("gemini-3.1-pro-preview", {"low": "low", "medium": "medium", "high": "high"}, aliases=("gemini-3.1-pro",)),
    # xAI — suppressed effort
    _suppressed_spec("grok-4", "xai", canonical_effort="high", aliases=("grok-4",)),
    _suppressed_spec("grok-4-fast", "xai", canonical_effort="high", aliases=("grok-4-fast",)),
    _suppressed_spec("grok-3-mini", "xai", canonical_effort="high", aliases=("grok-3-mini",)),
    _suppressed_spec("grok-4-1-fast", "xai", canonical_effort="high"),
    _suppressed_spec("grok-4-1-fast-reasoning", "xai", canonical_effort="high"),
    _suppressed_spec("grok-4-1-fast-non-reasoning", "xai", canonical_effort="none"),
    _suppressed_spec("grok-4-fast-non-reasoning", "xai", canonical_effort="none"),
    _suppressed_spec("grok-4-fast-reasoning", "xai", canonical_effort="high"),
    _suppressed_spec("grok-code-fast", "xai", canonical_effort="high"),
    _suppressed_spec("grok-3-mini-fast", "xai", canonical_effort="high"),
    _suppressed_spec("grok-3-fast", "xai", canonical_effort="none"),
    _suppressed_spec("grok-3", "xai", canonical_effort="none"),
    # DeepSeek — suppressed effort
    _suppressed_spec("deepseek-reasoner", "deepseek", canonical_effort="high", max_output_tokens=64_000, aliases=("deepseek-r1",)),
    _suppressed_spec("deepseek-chat", "deepseek", canonical_effort="none", max_output_tokens=8_000, aliases=("deepseek-chat",)),
    # Moonshot — suppressed effort
    _suppressed_spec("kimi-k2.5", "moonshotai", canonical_effort="high", max_output_tokens=MOONSHOT_256K_CONTEXT_TOKENS, aliases=("kimi-k2.5",), pricing_fallback=("openrouter", "moonshotai/kimi-k2.5")),
    _suppressed_spec("kimi-k2-thinking", "moonshotai", canonical_effort="high", max_output_tokens=MOONSHOT_256K_CONTEXT_TOKENS, pricing_fallback=("groq", "moonshotai/kimi-k2-thinking")),
    _suppressed_spec("kimi-k2-0905", "moonshotai", canonical_effort="none", max_output_tokens=MOONSHOT_256K_CONTEXT_TOKENS, pricing_fallback=("groq", "moonshotai/kimi-k2-instruct")),
    _suppressed_spec("kimi-k2-instruct", "moonshotai", canonical_effort="none", max_output_tokens=MOONSHOT_128K_CONTEXT_TOKENS, pricing_fallback=("groq", "moonshotai/kimi-k2-instruct")),
    _suppressed_spec("kimi-k2-0711-preview", "moonshotai", canonical_effort="none", max_output_tokens=MOONSHOT_128K_CONTEXT_TOKENS, aliases=("kimi-k2",), pricing_fallback=("groq", "moonshotai/kimi-k2-instruct")),
]

# =============================================================================
# Registry lookups
# =============================================================================

MODEL_REGISTRY: dict[str, ModelSpec] = {spec.name: spec for spec in _ALL_SPECS}


def _api_model_name(inspect_model: str) -> str:
    inner = inspect_model[4:] if inspect_model.startswith("gpd/") else inspect_model
    return inner.split(":", 1)[1] if ":" in inner else inner


_PREFIX_INDEX: list[tuple[str, ModelSpec]] = sorted(
    [(spec.name, spec) for spec in _ALL_SPECS]
    + [(alias, spec) for spec in _ALL_SPECS for alias in spec.aliases]
    + [(_api_model_name(spec.inspect_model), spec) for spec in _ALL_SPECS if spec.inspect_model],
    key=lambda x: len(x[0]),
    reverse=True,
)

_PROVIDER_NORMALIZE: dict[str, str] = {
    "google-gla": "google",
    "google-vertex": "google",
    "openai-responses": "openai",
}


def lookup_spec(provider: str, model: str) -> ModelSpec | None:
    """Find the ModelSpec for a provider/model pair (longest-prefix match)."""
    norm_provider = _PROVIDER_NORMALIZE.get(provider, provider)
    m = model.lower()
    for prefix, spec in _PREFIX_INDEX:
        if m.startswith(prefix.lower()) and spec.provider == norm_provider:
            return spec
    return None


# =============================================================================
# Canonical effort levels
# =============================================================================

EFFORT_LEVELS: frozenset[str] = frozenset(("none", "minimal", "low", "medium", "high", "xhigh"))

_BUDGET_VARIANT_SUFFIX = "budget"


def _split_effort_variant(effort: str) -> tuple[str, bool]:
    raw = effort.strip().lower()
    parts = raw.rsplit("-", 1)
    if len(parts) == 2 and parts[1] == _BUDGET_VARIANT_SUFFIX:
        return parts[0], True
    return raw, False


# =============================================================================
# Core functions
# =============================================================================


def effort_to_model_settings(provider: str, model: str, effort: str) -> dict[str, object]:
    """Map a canonical effort label to provider-specific PydanticAI model_settings dict.

    Raises ``ValueError`` if the effort/model combination is not supported.
    """
    base_effort, use_budget_variant = _split_effort_variant(effort)
    if base_effort not in EFFORT_LEVELS:
        raise ValueError(f"Unknown effort level {effort!r}. Valid: {sorted(EFFORT_LEVELS)}")

    spec = lookup_spec(provider, model)
    if spec is not None:
        if base_effort not in spec.effort_settings:
            raise ValueError(
                f"Unsupported effort {base_effort!r} for {provider}:{model!r}. "
                f"Valid values: {sorted(spec.valid_efforts)}"
            )
        settings = dict(spec.effort_settings[base_effort])
        if use_budget_variant and spec.provider != "anthropic":
            raise ValueError(
                f"Unsupported effort variant {effort!r} for {provider}:{model!r}. "
                "The '-budget' suffix is only supported for Anthropic models."
            )
        if spec.provider == "anthropic":
            _apply_anthropic_context_features(settings, spec_name=spec.name)
            if use_budget_variant:
                if base_effort == "none":
                    raise ValueError("Unsupported effort 'none-budget' for Anthropic models")
                if spec.thinking_mode != ThinkingMode.ADAPTIVE:
                    raise ValueError(
                        f"Unsupported effort variant {effort!r} for {provider}:{model!r}. "
                        "The '-budget' suffix is only supported for Anthropic 4.6 models."
                    )
                max_tokens = settings.get("max_tokens")
                if not isinstance(max_tokens, int) or max_tokens <= ANTHROPIC_THINKING_BUDGET_HEADROOM_TOKENS:
                    raise ValueError(f"Invalid max_tokens={max_tokens!r} for budget variant")
                settings["anthropic_thinking"] = {
                    "type": "enabled",
                    "budget_tokens": max_tokens - ANTHROPIC_THINKING_BUDGET_HEADROOM_TOKENS,
                }
        return settings

    raise ValueError(
        f"Unknown model {provider}:{model!r} — not in the model catalog, so effort settings cannot be built. "
        "Remove the effort suffix or add the model to gpd.utils.effort."
    )


def base_model_settings(provider: str, model: str) -> dict[str, object]:
    """Return baseline PydanticAI model_settings for a provider/model pair.

    Used when a model spec has no effort suffix but we still want
    provider-specific settings like max_tokens and Anthropic betas.
    """
    spec = lookup_spec(provider, model)
    if spec is None:
        return {}
    settings: dict[str, object] = {}
    if spec.max_output_tokens is not None:
        settings["max_tokens"] = spec.max_output_tokens
    if spec.provider == "anthropic":
        _apply_anthropic_context_features(settings, spec_name=spec.name)
    return settings


# =============================================================================
# parse_model_spec
# =============================================================================


def parse_model_spec(spec: str) -> tuple[str, str, str | None]:
    """Parse a model spec into ``(provider, base_model, effort_or_None)``.

    Examples::

        "openai:gpt-5.2-low"    -> ("openai", "gpt-5.2", "low")
        "gpt-4o"                 -> ("", "gpt-4o", None)
        "anthropic:claude-sonnet-4-5-20250929" -> ("anthropic", "claude-sonnet-4-5-20250929", None)
    """
    if ":" in spec:
        provider, model_part = spec.split(":", 1)
    else:
        provider, model_part = "", spec

    # Optional suffix: "-<effort>-budget"
    maybe_budget = model_part.rsplit("-", 2)
    if len(maybe_budget) == 3 and maybe_budget[2].strip().lower() == _BUDGET_VARIANT_SUFFIX:
        base, effort_raw = maybe_budget[0].strip(), maybe_budget[1].strip().lower()
        if effort_raw in EFFORT_LEVELS:
            return provider, base, f"{effort_raw}-{_BUDGET_VARIANT_SUFFIX}"

    pieces = model_part.rsplit("-", 1)
    if len(pieces) == 2 and pieces[1].strip().lower() in EFFORT_LEVELS:
        return provider, pieces[0].strip(), pieces[1].strip().lower()

    return provider, model_part, None
