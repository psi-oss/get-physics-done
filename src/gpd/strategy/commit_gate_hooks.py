"""CommitGate invariant check hooks for GPD convention and physics enforcement.

These hooks plug into the agentic-builder CommitGate to enforce convention
consistency and catch common physics errors during MCTS search.

CommitGate InvariantCheck signature:
    Callable[[dict[str, object], dict[str, object]], list[str]]
    Args: (payload_json, ctx) -> list of violation strings (empty = pass)

The factory function ``create_gpd_invariant_checks`` returns bound closures
matching this signature for direct injection into CommitGate.invariant_checks.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable

from gpd.contracts import ConventionLock, ErrorClass

from gpd.core.conventions import (
    KNOWN_CONVENTIONS,
    normalize_key,
    normalize_value,
    parse_assert_conventions,
)
from gpd.core.observability import gpd_span

logger = logging.getLogger(__name__)

# CommitGate invariant check type alias (matches agentic_builder.engine.state.commit_gate)
InvariantCheck = Callable[[dict[str, object], dict[str, object]], list[str]]

# --- Constants ---

# Minimum string length to consider for text extraction (skip keys, enum values, etc.)
_MIN_TEXT_LENGTH = 6

# Minimum example length for error catalog substring matching (avoid false positives)
_MIN_EXAMPLE_LENGTH = 11

# Minimum meaningful word length for error name matching
_MIN_WORD_LENGTH = 4

# Minimum number of matching words from error name required to trigger
_MIN_NAME_WORD_MATCHES = 2

# --- Metric Sign Patterns ---

# Known sign-sensitive conventions and their expected diag() patterns
_METRIC_SIGN_PATTERNS: dict[str, re.Pattern[str]] = {
    "mostly-plus": re.compile(r"diag\s*\(\s*-\s*,\s*\+\s*,\s*\+\s*,\s*\+\s*\)"),
    "mostly-minus": re.compile(r"diag\s*\(\s*\+\s*,\s*-\s*,\s*-\s*,\s*-\s*\)"),
}

# --- Common Physics Error Patterns ---

_COMMON_ERROR_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"\b1/2\b.*\b2\b|\b2\b.*\b1/2\b", re.IGNORECASE),
        "potential factor-of-2 inconsistency",
    ),
    (
        re.compile(r"(?<!\d)4\s*\\?pi\s*r\^2|4\s*pi\s*r\^2", re.IGNORECASE),
        "verify 4*pi*r^2 factor",
    ),
    (
        re.compile(r"e\^?\{?\s*\+\s*i|exp\s*\(\s*\+\s*i", re.IGNORECASE),
        "check sign in exponential (e^{+i} vs e^{-i})",
    ),
]

# --- Natural Units Patterns ---

_NATURAL_UNIT_DECLARATION = re.compile(
    r"\b(?:hbar|\\hbar|ℏ)\s*=\s*1\b|\bc\s*=\s*1\b|\bk_B\s*=\s*1\b",
    re.IGNORECASE,
)
_EXPLICIT_UNIT_SYMBOL = re.compile(
    r"\b(?:kg|meter|second|joule|eV|GeV|MeV|keV|TeV)\b",
    re.IGNORECASE,
)

# Keywords in natural_units lock value that indicate natural units are active
_NATURAL_UNIT_KEYWORDS = ("c=hbar=1", "hbar=c=1", "natural")


# --- Text Extraction ---


def _extract_text_values(payload: dict[str, object]) -> list[str]:
    """Recursively extract all string values from a payload dict.

    Skips strings shorter than ``_MIN_TEXT_LENGTH`` to avoid noise from
    keys, enum values, and other short metadata strings.
    """
    texts: list[str] = []
    _walk_strings(payload, texts)
    return texts


def _walk_strings(obj: object, out: list[str]) -> None:
    """Recursively walk a nested dict/list and collect string values."""
    if isinstance(obj, str):
        if len(obj) >= _MIN_TEXT_LENGTH:
            out.append(obj)
    elif isinstance(obj, dict):
        for v in obj.values():
            _walk_strings(v, out)
    elif isinstance(obj, list):
        for item in obj:
            _walk_strings(item, out)


# --- Convention Invariant Check ---


def convention_invariant_check(
    payload: dict[str, object],
    ctx: dict[str, object],
    convention_lock: ConventionLock,
) -> list[str]:
    """Check convention consistency in committed payload state.

    1. Parse ASSERT_CONVENTION directives from text content
    2. Validate each assertion against the convention lock
    3. Check metric sign pattern consistency
    4. Check natural units consistency

    Returns list of violation strings (empty = pass).
    """
    with gpd_span("commit_gate.convention_check"):
        violations: list[str] = []
        texts = _extract_text_values(payload)
        combined = "\n".join(texts)

        _check_assert_conventions(combined, convention_lock, violations)
        _check_metric_sign_patterns(combined, convention_lock, violations)
        _check_natural_units(combined, convention_lock, violations)

        if violations:
            logger.info(
                "convention_invariant_violations",
                extra={"count": len(violations), "action_id": ctx.get("action_id")},
            )

        return violations


def _check_assert_conventions(content: str, lock: ConventionLock, violations: list[str]) -> None:
    """Validate ASSERT_CONVENTION directives against the lock."""
    assertions = parse_assert_conventions(content)
    for key, asserted_value in assertions:
        lock_value = _get_lock_value(lock, key)
        if lock_value is None:
            continue
        norm_lock = normalize_value(key, lock_value)
        norm_asserted = normalize_value(key, asserted_value)
        if norm_lock != norm_asserted:
            violations.append(
                f"ASSERT_CONVENTION mismatch: {key}={asserted_value} but convention lock has {key}={lock_value}"
            )


def _check_metric_sign_patterns(content: str, lock: ConventionLock, violations: list[str]) -> None:
    """Check that diag() patterns in content match the locked metric signature."""
    if not lock.metric_signature:
        return
    norm_metric = normalize_value("metric_signature", lock.metric_signature)
    for sig_name, pattern in _METRIC_SIGN_PATTERNS.items():
        if sig_name != norm_metric and pattern.search(content):
            violations.append(
                f"Metric sign inconsistency: content uses {sig_name} pattern "
                f"but convention lock specifies metric_signature={lock.metric_signature}"
            )


def _check_natural_units(content: str, lock: ConventionLock, violations: list[str]) -> None:
    """Check that content doesn't mix natural unit declarations with explicit units."""
    if not lock.natural_units:
        return
    lock_units = lock.natural_units.lower()
    has_natural = any(kw in lock_units for kw in _NATURAL_UNIT_KEYWORDS)
    if has_natural and _NATURAL_UNIT_DECLARATION.search(content) and _EXPLICIT_UNIT_SYMBOL.search(content):
        violations.append(
            "Natural units inconsistency: content mixes natural units (hbar=1, c=1) "
            "with explicit unit symbols (eV, kg, etc.)"
        )


def _get_lock_value(lock: ConventionLock, key: str) -> str | None:
    """Get the locked value for a convention key (canonical or custom)."""
    canonical = normalize_key(key)
    if canonical in KNOWN_CONVENTIONS:
        val = getattr(lock, canonical, None)
        if val is not None:
            return str(val)
    return lock.custom_conventions.get(canonical)


# --- Physics Invariant Check ---


def physics_invariant_check(
    payload: dict[str, object],
    ctx: dict[str, object],
    error_catalog: list[ErrorClass],
) -> list[str]:
    """Scan committed payload for potential physics errors.

    1. Match against error catalog detection strategies
    2. Check common error patterns (factors of 2, pi, sign)

    Returns list of violation strings (empty = pass).
    """
    with gpd_span("commit_gate.physics_check", catalog_size=len(error_catalog)):
        violations: list[str] = []
        texts = _extract_text_values(payload)
        combined = "\n".join(texts)

        if not combined.strip():
            return violations

        _check_error_catalog(combined, error_catalog, violations)
        _check_common_patterns(combined, violations)

        if violations:
            logger.info(
                "physics_invariant_violations",
                extra={"count": len(violations), "action_id": ctx.get("action_id")},
            )

        return violations


def _check_error_catalog(content: str, error_catalog: list[ErrorClass], violations: list[str]) -> None:
    """Match content against error catalog detection strategies."""
    for error_cls in error_catalog:
        if _matches_detection_strategy(content, error_cls):
            violations.append(f"Potential physics error [{error_cls.id}] {error_cls.name}: {error_cls.description}")


def _check_common_patterns(content: str, violations: list[str]) -> None:
    """Check content against common physics error patterns."""
    for pattern, description in _COMMON_ERROR_PATTERNS:
        if pattern.search(content):
            violations.append(f"Physics warning: {description}")


def _matches_detection_strategy(content: str, error_cls: ErrorClass) -> bool:
    """Check if content triggers an error class's detection strategy.

    Uses two heuristics:
    1. Exact substring match against the error's example text
    2. Multi-word match against the error's name words
    """
    content_lower = content.lower()

    if error_cls.example:
        example_lower = error_cls.example.lower()
        if len(example_lower) >= _MIN_EXAMPLE_LENGTH and example_lower in content_lower:
            return True

    if error_cls.name:
        name_words = error_cls.name.lower().split()
        # Filter out generic stop-words that appear in normal physics text
        _STOP_WORDS = frozenset(
            {
                "errors",
                "wrong",
                "common",
                "potential",
                "model",
                "state",
                "limit",
                "field",
                "order",
                "ordering",
                "units",
                "formula",
            }
        )
        significant_words = [w for w in name_words if len(w) >= _MIN_WORD_LENGTH and w not in _STOP_WORDS]
        if len(significant_words) >= _MIN_NAME_WORD_MATCHES:
            matches = sum(1 for w in significant_words if w in content_lower)
            if matches >= _MIN_NAME_WORD_MATCHES:
                return True

    return False


# --- Factory ---


def create_gpd_invariant_checks(
    convention_lock: ConventionLock,
    error_catalog: list[ErrorClass],
) -> list[InvariantCheck]:
    """Create bound CommitGate invariant check functions.

    Returns a list of callables matching the CommitGate InvariantCheck signature:
        ``Callable[[dict[str, object], dict[str, object]], list[str]]``

    These close over the convention_lock and error_catalog so CommitGate
    can call them with just ``(payload, ctx)``.
    """
    checks: list[InvariantCheck] = []

    if _has_any_convention(convention_lock):

        def _convention_check(payload: dict[str, object], ctx: dict[str, object]) -> list[str]:
            return convention_invariant_check(payload, ctx, convention_lock)

        checks.append(_convention_check)

    if error_catalog:

        def _physics_check(payload: dict[str, object], ctx: dict[str, object]) -> list[str]:
            return physics_invariant_check(payload, ctx, error_catalog)

        checks.append(_physics_check)

    logger.info(
        "gpd_invariant_checks_created",
        extra={
            "convention_check": _has_any_convention(convention_lock),
            "physics_check": bool(error_catalog),
            "error_catalog_size": len(error_catalog),
        },
    )

    return checks


def _has_any_convention(lock: ConventionLock) -> bool:
    """Return True if at least one convention is set in the lock."""
    for key in KNOWN_CONVENTIONS:
        if getattr(lock, key, None) is not None:
            return True
    return bool(lock.custom_conventions)
