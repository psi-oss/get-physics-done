"""Cost-based fix-vs-substitute decision engine.

Estimates fix complexity and time for broken tools, compares against
substitute availability, and recommends the optimal action: fix, substitute,
or skip.
"""

from __future__ import annotations

import logging
from enum import StrEnum

from pydantic import BaseModel

logger = logging.getLogger(__name__)

SIMPLE_PATTERNS: list[str] = [
    "ImportError",
    "TypeError",
    "KeyError",
    "ConfigError",
    "not installed",
    "missing module",
    "AttributeError",
    "NameError",
    "SyntaxError",
]
"""Error patterns indicating simple, fast-to-fix issues."""

COMPLEX_PATTERNS: list[str] = [
    "TimeoutError",
    "MemoryError",
    "DeploymentError",
    "logic error",
    "incorrect output",
    "segfault",
    "core dump",
    "OOM",
]
"""Error patterns indicating complex, time-consuming issues."""

# ── Timeout constants ────────────────────────────────────────────────────────

TIMEOUT_BUFFER_MULTIPLIER: float = 1.5
"""Multiplier applied to base timeouts (50% buffer per research pitfall 5)."""

BASE_TIMEOUT_SIMPLE: int = 120
"""Base timeout in seconds for simple fixes (e.g. ImportError, missing module)."""

BASE_TIMEOUT_MODERATE: int = 300
"""Base timeout in seconds for moderate-complexity fixes."""

BASE_TIMEOUT_COMPLEX: int = 600
"""Base timeout in seconds for complex fixes (e.g. MemoryError, segfault)."""

FIX_MINUTES_SIMPLE: float = 2.0
"""Estimated fix time in minutes for simple errors."""

FIX_MINUTES_MODERATE: float = 5.0
"""Estimated fix time in minutes for moderate errors."""

FIX_MINUTES_COMPLEX: float = 10.0
"""Estimated fix time in minutes for complex errors."""


class FixComplexity(StrEnum):
    """Complexity classification for tool fixes."""

    simple = "simple"
    moderate = "moderate"
    complex = "complex"


class FixEstimate(BaseModel):
    """Cost estimate for fixing a broken tool."""

    fix_minutes: float
    substitute_minutes: float | None
    recommendation: str
    fix_complexity: FixComplexity
    timeout_seconds: int
    reasoning: str


def estimate_fix_cost(
    error_type: str,
    error_message: str,
    mcp_name: str,
    has_substitute: bool,
) -> FixEstimate:
    """Estimate the cost of fixing vs. substituting a broken tool.

    Uses case-insensitive pattern matching against both error_type and
    error_message to classify complexity. Applies 50% timeout buffer
    per research pitfall 5.
    """
    combined_lower = f"{error_type} {error_message}".lower()

    is_simple = _matches_patterns(combined_lower, SIMPLE_PATTERNS)
    is_complex = _matches_patterns(combined_lower, COMPLEX_PATTERNS)

    if is_simple:
        fix_minutes = FIX_MINUTES_SIMPLE
        fix_complexity = FixComplexity.simple
        base_timeout = BASE_TIMEOUT_SIMPLE
    elif is_complex:
        fix_minutes = FIX_MINUTES_COMPLEX
        fix_complexity = FixComplexity.complex
        base_timeout = BASE_TIMEOUT_COMPLEX
    else:
        fix_minutes = FIX_MINUTES_MODERATE
        fix_complexity = FixComplexity.moderate
        base_timeout = BASE_TIMEOUT_MODERATE

    substitute_minutes = 3.0 if has_substitute else None

    # Decision logic
    if substitute_minutes is not None and substitute_minutes < fix_minutes:
        recommendation = "substitute"
    elif fix_minutes <= FIX_MINUTES_COMPLEX:
        recommendation = "fix"
    else:
        recommendation = "skip"

    timeout_seconds = int(base_timeout * TIMEOUT_BUFFER_MULTIPLIER)

    sub_desc = f"available at {substitute_minutes}min" if substitute_minutes is not None else "not available"
    reasoning = (
        f"Fix estimated at {fix_minutes}min ({fix_complexity}). "
        f"Substitute {sub_desc}. "
        f"Recommendation: {recommendation}."
    )

    return FixEstimate(
        fix_minutes=fix_minutes,
        substitute_minutes=substitute_minutes,
        recommendation=recommendation,
        fix_complexity=fix_complexity,
        timeout_seconds=timeout_seconds,
        reasoning=reasoning,
    )


def should_spawn_mcp_builder(estimate: FixEstimate) -> bool:
    """Return True if the estimate recommends fixing via MCP Builder."""
    return estimate.recommendation == "fix"


def get_timeout_for_complexity(complexity: FixComplexity) -> int:
    """Return the buffered timeout in seconds for a given complexity level."""
    base_timeouts = {
        FixComplexity.simple: BASE_TIMEOUT_SIMPLE,
        FixComplexity.moderate: BASE_TIMEOUT_MODERATE,
        FixComplexity.complex: BASE_TIMEOUT_COMPLEX,
    }
    return int(base_timeouts[complexity] * TIMEOUT_BUFFER_MULTIPLIER)


def _matches_patterns(text_lower: str, patterns: list[str]) -> bool:
    """Check if any pattern matches case-insensitively in the text."""
    return any(p.lower() in text_lower for p in patterns)
