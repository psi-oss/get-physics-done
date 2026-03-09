"""Feature flag ablation system for GPD subsystems.

Builds on ``gpd.core.observability.FeatureFlags`` to provide:

- **Simplified env var overrides**: ``GPD_DISABLE_CONVENTIONS=1`` disables all convention
  enforcement in one shot (vs the lower-level ``GPD_FLAG_GPD_CONVENTIONS_ENABLED=0``).
- **Ablation guards**: Decorators and context managers that skip work when a subsystem
  is disabled, with Logfire span annotations for observability.
- **Ablation point documentation**: Single source of truth for every GPD subsystem that
  can be toggled, what flags control it, and what the expected effect is.
- **Env var integration**: ``apply_ablation_overrides`` merges simplified env vars
  into the feature flag dict before ``FeatureFlags`` is constructed.

Env var convention
------------------
``GPD_DISABLE_<SUBSYSTEM>=1`` disables the subsystem.  The mapping from subsystem
names to flag keys is defined in ``ABLATION_POINTS``.

Example::

    GPD_DISABLE_CONVENTIONS=1      # turns off all convention enforcement
    GPD_DISABLE_VERIFICATION=1     # turns off all verification checks
    GPD_DISABLE_PATTERNS=1         # turns off pattern library
    GPD_DISABLE_COMMIT_GATE=1      # turns off CommitGate convention hooks only
    GPD_DISABLE_DIMENSIONAL=1      # turns off dimensional analysis check only
"""

from __future__ import annotations

import functools
import logging
import os
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass, field

from gpd.core.observability import (
    FeatureFlags,
    gpd_span,
    is_enabled,
)

logger = logging.getLogger(__name__)

__all__ = [
    "ABLATION_POINTS",
    "AblationPoint",
    "AblationReport",
    "ablation_guard",
    "apply_ablation_overrides",
    "guarded",
    "report_ablations",
    "skip_when_disabled",
]

# ---------------------------------------------------------------------------
# Env var prefix for simplified disable overrides
# ---------------------------------------------------------------------------

_DISABLE_PREFIX = "GPD_DISABLE_"


# ---------------------------------------------------------------------------
# Ablation point registry — single source of truth for all toggleable subsystems
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AblationPoint:
    """Describes a single ablation point in the GPD system.

    Attributes:
        subsystem: Short uppercase name used in env vars (e.g. ``"CONVENTIONS"``).
        flag_keys: Feature flag keys disabled when this ablation fires.
        description: Human-readable description of what gets disabled.
        layer: Architecture layer (``"core"``, ``"mcp"``).
    """

    subsystem: str
    flag_keys: list[str]
    description: str
    layer: str


# Every ablation point in the system. Add new entries here when adding new
# toggleable subsystems. Order matches the flag hierarchy in observability.py.
ABLATION_POINTS: dict[str, AblationPoint] = {
    # --- Top-level kill switch ---
    "GPD": AblationPoint(
        subsystem="GPD",
        flag_keys=["gpd.enabled"],
        description="Master kill switch — disables ALL GPD components",
        layer="core",
    ),
    # --- Convention enforcement ---
    "CONVENTIONS": AblationPoint(
        subsystem="CONVENTIONS",
        flag_keys=[
            "gpd.conventions.enabled",
            "gpd.conventions.commit_gate",
            "gpd.conventions.assert_check",
            "gpd.conventions.drift_detection",
        ],
        description="All convention enforcement (lock validation, assertion checks, drift detection)",
        layer="core",
    ),
    "COMMIT_GATE": AblationPoint(
        subsystem="COMMIT_GATE",
        flag_keys=["gpd.conventions.commit_gate"],
        description="CommitGate convention invariant hooks only",
        layer="core",
    ),
    "ASSERT_CHECK": AblationPoint(
        subsystem="ASSERT_CHECK",
        flag_keys=["gpd.conventions.assert_check"],
        description="ASSERT_CONVENTION directive validation only",
        layer="core",
    ),
    "DRIFT_DETECTION": AblationPoint(
        subsystem="DRIFT_DETECTION",
        flag_keys=["gpd.conventions.drift_detection"],
        description="Convention drift detection across phases",
        layer="core",
    ),
    # --- Verification checks ---
    "VERIFICATION": AblationPoint(
        subsystem="VERIFICATION",
        flag_keys=[
            "gpd.verification.enabled",
            "gpd.verification.checks.dimensional",
            "gpd.verification.checks.limiting_cases",
            "gpd.verification.checks.symmetry",
            "gpd.verification.checks.conservation",
            "gpd.verification.checks.numerical",
            "gpd.verification.checks.sign_convention",
            "gpd.verification.checks.index_consistency",
        ],
        description="All verification checks (dimensional, limiting cases, symmetry, etc.)",
        layer="core",
    ),
    "DIMENSIONAL": AblationPoint(
        subsystem="DIMENSIONAL",
        flag_keys=["gpd.verification.checks.dimensional"],
        description="Dimensional analysis verification check",
        layer="core",
    ),
    "LIMITING_CASES": AblationPoint(
        subsystem="LIMITING_CASES",
        flag_keys=["gpd.verification.checks.limiting_cases"],
        description="Limiting case verification check",
        layer="core",
    ),
    "SYMMETRY": AblationPoint(
        subsystem="SYMMETRY",
        flag_keys=["gpd.verification.checks.symmetry"],
        description="Symmetry verification check",
        layer="core",
    ),
    "CONSERVATION": AblationPoint(
        subsystem="CONSERVATION",
        flag_keys=["gpd.verification.checks.conservation"],
        description="Conservation law verification check",
        layer="core",
    ),
    "NUMERICAL": AblationPoint(
        subsystem="NUMERICAL",
        flag_keys=["gpd.verification.checks.numerical"],
        description="Numerical consistency verification check",
        layer="core",
    ),
    "SIGN_CONVENTION": AblationPoint(
        subsystem="SIGN_CONVENTION",
        flag_keys=["gpd.verification.checks.sign_convention"],
        description="Sign convention verification check",
        layer="core",
    ),
    "INDEX_CONSISTENCY": AblationPoint(
        subsystem="INDEX_CONSISTENCY",
        flag_keys=["gpd.verification.checks.index_consistency"],
        description="Index consistency verification check",
        layer="core",
    ),
    # --- Protocols ---
    "PROTOCOLS": AblationPoint(
        subsystem="PROTOCOLS",
        flag_keys=["gpd.protocols.enabled", "gpd.protocols.checkpoint_enforcement"],
        description="All protocol enforcement (checkpoint gates, protocol loading)",
        layer="core",
    ),
    "CHECKPOINT": AblationPoint(
        subsystem="CHECKPOINT",
        flag_keys=["gpd.protocols.checkpoint_enforcement"],
        description="Checkpoint enforcement within protocols",
        layer="core",
    ),
    # --- Error detection ---
    "ERRORS": AblationPoint(
        subsystem="ERRORS",
        flag_keys=["gpd.errors.enabled", "gpd.errors.classification"],
        description="Error detection and classification system",
        layer="core",
    ),
    # --- Pattern library ---
    "PATTERNS": AblationPoint(
        subsystem="PATTERNS",
        flag_keys=["gpd.patterns.enabled", "gpd.patterns.cross_project"],
        description="Error pattern library (intra- and cross-project)",
        layer="core",
    ),
    "CROSS_PROJECT": AblationPoint(
        subsystem="CROSS_PROJECT",
        flag_keys=["gpd.patterns.cross_project"],
        description="Cross-project pattern sharing only",
        layer="core",
    ),
    # --- Diagnostics ---
    "TRACING": AblationPoint(
        subsystem="TRACING",
        flag_keys=["gpd.diagnostics.tracing"],
        description="JSONL execution tracing",
        layer="core",
    ),
    "HEALTH_CHECKS": AblationPoint(
        subsystem="HEALTH_CHECKS",
        flag_keys=["gpd.diagnostics.health_checks"],
        description="Diagnostic health check dashboard",
        layer="core",
    ),
}


# ---------------------------------------------------------------------------
# Env var → flag override resolution
# ---------------------------------------------------------------------------


def apply_ablation_overrides(
    flags: dict[str, bool],
    env: dict[str, str] | None = None,
) -> dict[str, bool]:
    """Apply simplified ``GPD_DISABLE_<SUBSYSTEM>=1`` env var overrides to a flag dict.

    This runs *after* ``load_feature_flags`` has assembled the base flag dict
    and *before* it is wrapped in ``FeatureFlags``.  It provides a user-friendly
    shorthand on top of the lower-level ``GPD_FLAG_`` prefix.

    Args:
        flags: Mutable flag dict (modified in place and returned).
        env: Environment dict (defaults to ``os.environ``).

    Returns:
        The same ``flags`` dict, mutated with any disable overrides applied.
    """
    env_dict = env if env is not None else dict(os.environ)
    applied: list[str] = []

    for subsystem, point in ABLATION_POINTS.items():
        env_key = _DISABLE_PREFIX + subsystem
        env_val = env_dict.get(env_key, "").strip().lower()
        if env_val in ("1", "true", "yes", "on"):
            for flag_key in point.flag_keys:
                if flag_key in flags:
                    flags[flag_key] = False
            applied.append(subsystem)

    if applied:
        logger.info(
            "ablation_overrides_applied",
            extra={"disabled_subsystems": applied, "count": len(applied)},
        )

    return flags


# ---------------------------------------------------------------------------
# Ablation guards — decorators and context managers
# ---------------------------------------------------------------------------


@contextmanager
def ablation_guard(
    flag_path: str,
    *,
    subsystem: str = "",
) -> Generator[bool, None, None]:
    """Context manager that checks a feature flag and yields whether work should proceed.

    Usage::

        with ablation_guard("gpd.conventions.commit_gate", subsystem="commit_gate") as active:
            if not active:
                return []  # skip work
            violations = run_convention_checks(...)

    The span is annotated with ``gpd.ablation_skipped=True`` when the flag is off,
    making ablation decisions visible in Logfire traces.
    """
    active = is_enabled(flag_path)
    span_name = f"ablation.{subsystem}" if subsystem else f"ablation.{flag_path}"

    with gpd_span(span_name, ablation_flag=flag_path, ablation_active=active) as span:
        if not active:
            span.set_attribute("gpd.ablation_skipped", True)
            logger.debug("ablation_guard_skipped", extra={"flag": flag_path, "subsystem": subsystem})
        yield active


def guarded(
    flag_path: str,
    *,
    default: object = None,
) -> Callable:
    """Decorator that skips the function body when a feature flag is disabled.

    The decorated function returns ``default`` when the flag is off.
    Works with both sync and async functions.

    Usage::

        @guarded("gpd.verification.checks.dimensional", default=[])
        def check_dimensions(equations: list[Equation]) -> list[Violation]:
            ...

        @guarded("gpd.conventions.enabled", default=None)
        async def validate_lock(lock: ConventionLock) -> Report | None:
            ...
    """

    def decorator(func: Callable) -> Callable:
        import inspect

        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: object, **kwargs: object) -> object:
                with ablation_guard(flag_path, subsystem=func.__qualname__) as active:
                    if not active:
                        return default
                    return await func(*args, **kwargs)

            return async_wrapper

        @functools.wraps(func)
        def sync_wrapper(*args: object, **kwargs: object) -> object:
            with ablation_guard(flag_path, subsystem=func.__qualname__) as active:
                if not active:
                    return default
                return func(*args, **kwargs)

        return sync_wrapper

    return decorator


def skip_when_disabled(flag_path: str) -> Callable:
    """Decorator that makes a function a no-op (returns ``None``) when disabled.

    Shorthand for ``@guarded(flag_path, default=None)``.
    """
    return guarded(flag_path, default=None)


# ---------------------------------------------------------------------------
# Ablation report — diagnostics
# ---------------------------------------------------------------------------


@dataclass
class AblationReport:
    """Diagnostic report showing which subsystems are active/disabled."""

    active: list[str] = field(default_factory=list)
    disabled: list[str] = field(default_factory=list)
    env_overrides: list[str] = field(default_factory=list)

    @property
    def summary(self) -> str:
        """One-line summary: ``"18/22 subsystems active, 4 disabled via env"``."""
        total = len(self.active) + len(self.disabled)
        env_note = f", {len(self.env_overrides)} via env" if self.env_overrides else ""
        return f"{len(self.active)}/{total} subsystems active, {len(self.disabled)} disabled{env_note}"

    def to_dict(self) -> dict[str, object]:
        """Serialize for JSON/logging."""
        return {
            "active": self.active,
            "disabled": self.disabled,
            "env_overrides": self.env_overrides,
            "summary": self.summary,
        }


def report_ablations(
    flags: FeatureFlags | None = None,
    env: dict[str, str] | None = None,
) -> AblationReport:
    """Generate an ablation report from the current (or given) feature flags.

    Args:
        flags: FeatureFlags instance. If None, uses the module-level singleton
            from ``gpd.core.observability``. Returns an empty report if flags
            are not initialized.
        env: Environment dict for detecting env var overrides.

    Returns:
        AblationReport with active/disabled subsystems and env override list.
    """
    if flags is None:
        from gpd.core.observability import _active_flags

        flags = _active_flags

    if flags is None:
        return AblationReport()

    env_dict = env if env is not None else dict(os.environ)

    report = AblationReport()

    for subsystem, point in ABLATION_POINTS.items():
        # A subsystem is "active" if ALL its flag_keys are enabled
        all_active = all(flags.is_enabled(k) for k in point.flag_keys)
        if all_active:
            report.active.append(subsystem)
        else:
            report.disabled.append(subsystem)

        # Check if an env var override is responsible
        env_key = _DISABLE_PREFIX + subsystem
        if env_dict.get(env_key, "").strip().lower() in ("1", "true", "yes", "on"):
            report.env_overrides.append(subsystem)

    return report
