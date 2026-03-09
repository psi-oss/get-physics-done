"""Observability and feature flags for GPD.

Provides:
- Feature flag system with ablation presets for fine-grained GPD control
- Logfire span helpers with GPD-specific attributes
- Decorator factory for instrumented functions
- Cost tracking attributes

Flag resolution priority: env vars > YAML overrides > GPDConfig (contracts) > local config > preset > defaults.
"""

from __future__ import annotations

import asyncio
import functools
import logging
import os
from collections.abc import Callable, Generator
from contextlib import contextmanager

import logfire

from gpd.contracts import GPDConfig
from pydantic import BaseModel, ConfigDict, Field

from gpd.core.errors import GPDError

logger = logging.getLogger(__name__)

__all__ = [
    "ABLATION_PRESETS",
    "AblationPreset",
    "FeatureFlagError",
    "FeatureFlags",
    "FlagNotInitializedError",
    "GPD_ATTR_CHECK_RESULT",
    "GPD_ATTR_CHECK_TYPE",
    "GPD_ATTR_CONVENTION_KEY",
    "GPD_ATTR_DOMAIN",
    "GPD_ATTR_ERROR_CLASS_ID",
    "GPD_ATTR_OVERHEAD_COST_USD",
    "GPD_ATTR_OVERHEAD_TOKENS",
    "GPD_ATTR_PHASE",
    "GPD_ATTR_PROTOCOL_NAME",
    "GPD_FEATURE_FLAGS",
    "UnknownPresetError",
    "get_feature_flags",
    "gpd_checks_failed",
    "gpd_checks_passed",
    "gpd_checks_run",
    "gpd_convention_violations",
    "gpd_overhead_cost",
    "gpd_overhead_tokens",
    "gpd_span",
    "init_feature_flags",
    "instrument_gpd_function",
    "is_enabled",
    "load_feature_flags",
    "reset_feature_flags",
]

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class FeatureFlagError(GPDError):
    """Base error for feature flag operations."""


class UnknownPresetError(FeatureFlagError):
    """Raised when an unrecognized ablation preset is requested."""

    def __init__(self, preset: str, valid: list[str]) -> None:
        self.preset = preset
        self.valid = valid
        super().__init__(f"Unknown ablation preset: {preset!r}. Valid: {valid}")


class FlagNotInitializedError(FeatureFlagError):
    """Raised when feature flags are accessed before initialization."""

    def __init__(self) -> None:
        super().__init__("Feature flags not initialized — call init_feature_flags() first")


# ---------------------------------------------------------------------------
# Default feature flags — every GPD component can be individually toggled
# ---------------------------------------------------------------------------

GPD_FEATURE_FLAGS: dict[str, bool] = {
    # Top-level
    "gpd.enabled": False,
    # Convention enforcement
    "gpd.conventions.enabled": True,
    "gpd.conventions.commit_gate": True,
    "gpd.conventions.assert_check": True,
    "gpd.conventions.drift_detection": True,
    # Verification checks
    "gpd.verification.enabled": True,
    "gpd.verification.checks.dimensional": True,
    "gpd.verification.checks.limiting_cases": True,
    "gpd.verification.checks.symmetry": True,
    "gpd.verification.checks.conservation": True,
    "gpd.verification.checks.numerical": True,
    "gpd.verification.checks.sign_convention": True,
    "gpd.verification.checks.index_consistency": True,
    # Protocols
    "gpd.protocols.enabled": True,
    "gpd.protocols.checkpoint_enforcement": True,
    # Error detection
    "gpd.errors.enabled": True,
    "gpd.errors.classification": True,
    # Pattern library
    "gpd.patterns.enabled": True,
    "gpd.patterns.cross_project": True,
    # Diagnostics
    "gpd.diagnostics.tracing": True,
    "gpd.diagnostics.health_checks": True,
}

# Environment variable prefix for flag overrides
_ENV_PREFIX = "GPD_FLAG_"


# ---------------------------------------------------------------------------
# Ablation presets
# ---------------------------------------------------------------------------


class AblationPreset(BaseModel):
    """Named preset that overrides a subset of feature flags."""

    model_config = ConfigDict(frozen=True)

    name: str
    description: str
    overrides: dict[str, bool] = Field(default_factory=dict)


ABLATION_PRESETS: dict[str, AblationPreset] = {
    "gpd_full": AblationPreset(
        name="gpd_full",
        description="All GPD components enabled",
        overrides={"gpd.enabled": True},
    ),
    "gpd_verification_only": AblationPreset(
        name="gpd_verification_only",
        description="Only verification checks, conventions and patterns disabled",
        overrides={
            "gpd.enabled": True,
            "gpd.verification.enabled": True,
            "gpd.conventions.enabled": False,
            "gpd.conventions.commit_gate": False,
            "gpd.conventions.assert_check": False,
            "gpd.conventions.drift_detection": False,
            "gpd.patterns.enabled": False,
            "gpd.patterns.cross_project": False,
            "gpd.protocols.enabled": False,
            "gpd.protocols.checkpoint_enforcement": False,
        },
    ),
    "gpd_conventions_only": AblationPreset(
        name="gpd_conventions_only",
        description="Only convention enforcement, verification and patterns disabled",
        overrides={
            "gpd.enabled": True,
            "gpd.conventions.enabled": True,
            "gpd.verification.enabled": False,
            "gpd.verification.checks.dimensional": False,
            "gpd.verification.checks.limiting_cases": False,
            "gpd.verification.checks.symmetry": False,
            "gpd.verification.checks.conservation": False,
            "gpd.verification.checks.numerical": False,
            "gpd.verification.checks.sign_convention": False,
            "gpd.verification.checks.index_consistency": False,
            "gpd.patterns.enabled": False,
            "gpd.patterns.cross_project": False,
            "gpd.protocols.enabled": False,
            "gpd.protocols.checkpoint_enforcement": False,
        },
    ),
    "gpd_off": AblationPreset(
        name="gpd_off",
        description="All GPD components disabled",
        overrides={"gpd.enabled": False},
    ),
    "gpd_exploratory": AblationPreset(
        name="gpd_exploratory",
        description="Lighter verification for exploratory research (7-check floor)",
        overrides={
            "gpd.enabled": True,
            "gpd.conventions.enabled": True,
            "gpd.conventions.commit_gate": False,
            "gpd.conventions.drift_detection": False,
            "gpd.verification.enabled": True,
            "gpd.verification.checks.numerical": False,
            "gpd.patterns.enabled": True,
            "gpd.patterns.cross_project": False,
            "gpd.protocols.enabled": True,
            "gpd.protocols.checkpoint_enforcement": False,
        },
    ),
}


# ---------------------------------------------------------------------------
# Feature flag loading and resolution
# ---------------------------------------------------------------------------


def load_feature_flags(
    config: GPDConfig | None = None,
    env: dict[str, str] | None = None,
    yaml_overrides: dict[str, bool] | None = None,
    preset: str | None = None,
    local_config: object | None = None,
) -> dict[str, bool]:
    """Resolve feature flags with priority: env > YAML > config > local_config > preset > defaults.

    Args:
        config: GPDConfig from psi_contracts (feature flag fields).
        env: Environment dict (defaults to os.environ).
        yaml_overrides: YAML config file overrides.
        preset: Name of an ablation preset to apply as base.
        local_config: Local GPDConfig from gpd.core.config (workflow toggles).
            Accepts any object with verifier/plan_checker attributes to avoid
            circular imports.

    Returns:
        Fully resolved feature flag dict.

    Raises:
        UnknownPresetError: If preset name is not recognized.
    """
    with logfire.span("gpd.load_feature_flags", preset=preset or "none"):
        resolved = dict(GPD_FEATURE_FLAGS)

        # Layer 1: Apply ablation preset (lowest priority after defaults)
        if preset:
            if preset not in ABLATION_PRESETS:
                raise UnknownPresetError(preset, sorted(ABLATION_PRESETS))
            resolved.update(ABLATION_PRESETS[preset].overrides)

        # Layer 2: Apply local project config (workflow toggles → feature flags)
        if local_config is not None:
            _apply_local_config(resolved, local_config)

        # Layer 3: Apply GPDConfig from psi_contracts
        if config is not None:
            resolved["gpd.enabled"] = config.enabled
            resolved["gpd.conventions.enabled"] = config.conventions_enabled
            resolved["gpd.verification.enabled"] = config.verification_enabled
            resolved["gpd.protocols.enabled"] = config.protocols_enabled
            resolved["gpd.errors.enabled"] = config.errors_enabled
            resolved["gpd.patterns.enabled"] = config.patterns_enabled
        # Layer 4: Apply YAML overrides
        if yaml_overrides:
            for key, value in yaml_overrides.items():
                if key in resolved:
                    resolved[key] = value

        # Layer 5: Apply environment variables (highest priority)
        env_dict = env if env is not None else dict(os.environ)
        for key in resolved:
            env_key = _ENV_PREFIX + key.upper().replace(".", "_")
            if env_key in env_dict:
                resolved[key] = _parse_bool_env(env_dict[env_key])

        return resolved


def _apply_local_config(resolved: dict[str, bool], local_config: object) -> None:
    """Map local GPDConfig workflow toggles to feature flags.

    Accepts any object with the right attributes (duck typing) to avoid
    circular imports with gpd.core.config.
    """
    # verifier toggle → verification.enabled
    verifier = getattr(local_config, "verifier", None)
    if verifier is not None:
        resolved["gpd.verification.enabled"] = bool(verifier)

    # plan_checker toggle — not a direct flag but informs diagnostics
    plan_checker = getattr(local_config, "plan_checker", None)
    if plan_checker is not None:
        resolved["gpd.diagnostics.health_checks"] = bool(plan_checker)


def _parse_bool_env(value: str) -> bool:
    """Parse a boolean from an environment variable string."""
    return value.strip().lower() in ("1", "true", "yes", "on")


# ---------------------------------------------------------------------------
# FeatureFlags — resolved, immutable flag store
# ---------------------------------------------------------------------------


class FeatureFlags:
    """Resolved feature flag store with hierarchical short-circuit logic.

    When a parent flag is disabled, all children are implicitly disabled
    regardless of their individual settings. The hierarchy walks from the
    top-level ``gpd.enabled`` down through category-level
    ``.enabled`` gates.
    """

    __slots__ = ("_flags",)

    def __init__(self, flags: dict[str, bool]) -> None:
        self._flags: dict[str, bool] = dict(flags)

    def is_enabled(self, flag_path: str) -> bool:
        """Check if a specific flag is active.

        Respects hierarchy: if ``gpd.enabled`` is False, everything is off.
        If ``gpd.conventions.enabled`` is False, all convention sub-flags are off.
        """
        # Top-level kill switch
        if not self._flags.get("gpd.enabled", False):
            return False

        # Walk the hierarchy: check each ancestor's .enabled gate
        parts = flag_path.split(".")
        for i in range(2, len(parts)):
            candidate = ".".join(parts[:i])
            parent_enabled_key = candidate + ".enabled"
            if parent_enabled_key in self._flags and parent_enabled_key != flag_path:
                if not self._flags[parent_enabled_key]:
                    return False

        return self._flags.get(flag_path, False)

    def enabled_flags(self) -> list[str]:
        """Return the list of effectively enabled flags (respecting hierarchy)."""
        return [k for k in self._flags if self.is_enabled(k)]

    def disabled_flags(self) -> list[str]:
        """Return the list of effectively disabled flags (respecting hierarchy)."""
        return [k for k in self._flags if not self.is_enabled(k)]

    @property
    def flags(self) -> dict[str, bool]:
        """Return a copy of the raw flags dict."""
        return dict(self._flags)

    def __repr__(self) -> str:
        enabled_count = sum(1 for k in self._flags if self.is_enabled(k))
        return f"FeatureFlags(enabled={enabled_count}/{len(self._flags)})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, FeatureFlags):
            return NotImplemented
        return self._flags == other._flags


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_active_flags: FeatureFlags | None = None


def init_feature_flags(
    config: GPDConfig | None = None,
    env: dict[str, str] | None = None,
    yaml_overrides: dict[str, bool] | None = None,
    preset: str | None = None,
    local_config: object | None = None,
) -> FeatureFlags:
    """Initialize the module-level feature flag singleton.

    Args:
        config: GPDConfig from psi_contracts (feature flag fields).
        env: Environment dict (defaults to os.environ).
        yaml_overrides: YAML config file overrides.
        preset: Name of an ablation preset to apply as base.
        local_config: Local GPDConfig from gpd.core.config (workflow toggles).

    Returns:
        The initialized FeatureFlags instance.

    Raises:
        UnknownPresetError: If preset name is not recognized.
    """
    global _active_flags
    with logfire.span("gpd.init_feature_flags", preset=preset or "none"):
        flags = load_feature_flags(
            config=config,
            env=env,
            yaml_overrides=yaml_overrides,
            preset=preset,
            local_config=local_config,
        )
        _active_flags = FeatureFlags(flags)
        logger.info("gpd_feature_flags_initialized", extra={"preset": preset, "flags": repr(_active_flags)})
        return _active_flags


def get_feature_flags() -> FeatureFlags:
    """Get the active feature flags.

    Raises:
        FlagNotInitializedError: If ``init_feature_flags()`` has not been called.
    """
    if _active_flags is None:
        raise FlagNotInitializedError
    return _active_flags


def is_enabled(flag_path: str) -> bool:
    """Check if a specific flag is active. Returns False if flags not initialized."""
    if _active_flags is None:
        return False
    return _active_flags.is_enabled(flag_path)


def reset_feature_flags() -> None:
    """Reset the module-level singleton (for testing)."""
    global _active_flags
    _active_flags = None


# ---------------------------------------------------------------------------
# Logfire span helpers
# ---------------------------------------------------------------------------

# GPD-specific span attribute keys (OpenTelemetry semantic conventions style)
GPD_ATTR_DOMAIN = "gpd.domain"
GPD_ATTR_PHASE = "gpd.phase"
GPD_ATTR_CHECK_TYPE = "gpd.check_type"
GPD_ATTR_CHECK_RESULT = "gpd.check_result"
GPD_ATTR_CONVENTION_KEY = "gpd.convention_key"
GPD_ATTR_ERROR_CLASS_ID = "gpd.error_class_id"
GPD_ATTR_PROTOCOL_NAME = "gpd.protocol_name"
GPD_ATTR_OVERHEAD_TOKENS = "gpd.overhead_tokens"
GPD_ATTR_OVERHEAD_COST_USD = "gpd.overhead_cost_usd"


@contextmanager
def gpd_span(name: str, **attrs: object) -> Generator[logfire.LogfireSpan, None, None]:
    """Create a Logfire span with GPD-specific attributes.

    Usage::

        with gpd_span("verify.dimensional", domain="qft", check_type="dimensional") as span:
            result = run_check(...)
            span.set_attribute("gpd.check_result", result.status)

    All keyword args are set as span attributes with ``gpd.`` prefix
    (unless they already have it).
    """
    prefixed: dict[str, object] = {}
    for key, value in attrs.items():
        attr_key = key if key.startswith("gpd.") else f"gpd.{key}"
        prefixed[attr_key] = value

    with logfire.span("gpd.{name}", name=name, **prefixed) as span:
        yield span


def instrument_gpd_function(
    span_name: str | None = None,
    **default_attrs: object,
) -> Callable:
    """Decorator factory for Logfire instrumentation of GPD functions.

    Usage::

        @instrument_gpd_function("conventions.validate", domain="qft")
        async def validate_conventions(lock: ConventionLock) -> bool:
            ...

    The decorated function is wrapped in a ``gpd_span``. Works with both
    sync and async functions (detected at decoration time).
    """

    def decorator(func: Callable) -> Callable:
        name = span_name or f"{func.__module__}.{func.__qualname__}"

        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: object, **kwargs: object) -> object:
                with gpd_span(name, **default_attrs):
                    return await func(*args, **kwargs)

            return async_wrapper

        @functools.wraps(func)
        def sync_wrapper(*args: object, **kwargs: object) -> object:
            with gpd_span(name, **default_attrs):
                return func(*args, **kwargs)

        return sync_wrapper

    return decorator


# ---------------------------------------------------------------------------
# Metrics — pre-built counters for GPD overhead tracking
# ---------------------------------------------------------------------------

gpd_checks_run = logfire.metric_counter(
    "gpd.checks_run",
    description="Total GPD verification checks executed",
    unit="checks",
)

gpd_checks_passed = logfire.metric_counter(
    "gpd.checks_passed",
    description="GPD verification checks that passed",
    unit="checks",
)

gpd_checks_failed = logfire.metric_counter(
    "gpd.checks_failed",
    description="GPD verification checks that failed",
    unit="checks",
)

gpd_convention_violations = logfire.metric_counter(
    "gpd.convention_violations",
    description="Convention lock violations detected",
    unit="violations",
)

gpd_overhead_tokens = logfire.metric_counter(
    "gpd.overhead_tokens",
    description="Tokens consumed by GPD overhead (verification, conventions, protocols)",
    unit="tokens",
)

gpd_overhead_cost = logfire.metric_counter(
    "gpd.overhead_cost_usd",
    description="Cost in USD of GPD overhead",
    unit="usd",
)
