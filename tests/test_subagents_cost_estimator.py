"""Tests for cost estimation and fix-vs-substitute decision engine."""

from __future__ import annotations

from gpd.mcp.subagents.cost_estimator import (
    FixComplexity,
    estimate_fix_cost,
    get_timeout_for_complexity,
    should_spawn_mcp_builder,
)


def test_simple_error_with_substitute_recommends_fix():
    """Simple ImportError with substitute available -> recommend fix (2min fix < 3min substitute)."""
    estimate = estimate_fix_cost("ImportError", "module not found", "openfoam", has_substitute=True)
    assert estimate.recommendation == "fix"
    assert estimate.fix_complexity == FixComplexity.simple
    assert estimate.substitute_minutes == 3.0


def test_simple_error_without_substitute_recommends_fix():
    """Simple ImportError without substitute -> recommend fix."""
    estimate = estimate_fix_cost("ImportError", "module not found", "openfoam", has_substitute=False)
    assert estimate.recommendation == "fix"


def test_complex_error_without_substitute_recommends_fix():
    """Complex TimeoutError without substitute -> recommend fix."""
    estimate = estimate_fix_cost("TimeoutError", "request timed out", "openfoam", has_substitute=False)
    assert estimate.recommendation == "fix"
    assert estimate.fix_complexity == FixComplexity.complex


def test_complex_error_with_substitute_recommends_substitute():
    """Complex MemoryError with substitute -> recommend substitute (3min < 10min)."""
    estimate = estimate_fix_cost("MemoryError", "out of memory", "openfoam", has_substitute=True)
    assert estimate.recommendation == "substitute"


def test_moderate_error_classification():
    """RuntimeError with generic message -> classify as moderate."""
    estimate = estimate_fix_cost("RuntimeError", "unexpected value", "openfoam", has_substitute=False)
    assert estimate.fix_complexity == FixComplexity.moderate


def test_timeout_includes_buffer():
    """Verify all timeouts include 50% buffer."""
    simple = estimate_fix_cost("ImportError", "not found", "x", has_substitute=False)
    assert simple.timeout_seconds == 180  # 120 * 1.5

    moderate = estimate_fix_cost("RuntimeError", "generic", "x", has_substitute=False)
    assert moderate.timeout_seconds == 450  # 300 * 1.5

    complex_ = estimate_fix_cost("TimeoutError", "timed out", "x", has_substitute=False)
    assert complex_.timeout_seconds == 900  # 600 * 1.5


def test_case_insensitive_pattern_matching():
    """Error patterns should match case-insensitively."""
    estimate = estimate_fix_cost("importerror", "MODULE NOT FOUND", "openfoam", has_substitute=False)
    assert estimate.fix_complexity == FixComplexity.simple


def test_pattern_matches_in_message():
    """Patterns in error_message (not just error_type) should be detected."""
    estimate = estimate_fix_cost("RuntimeError", "missing module xyz", "openfoam", has_substitute=False)
    assert estimate.fix_complexity == FixComplexity.simple


def test_should_spawn_mcp_builder():
    """Fix -> True, substitute -> False."""
    fix_estimate = estimate_fix_cost("ImportError", "err", "x", has_substitute=False)
    assert should_spawn_mcp_builder(fix_estimate) is True

    # Moderate error with substitute -> substitute (3min < 5min)
    sub_estimate = estimate_fix_cost("RuntimeError", "generic error", "x", has_substitute=True)
    assert should_spawn_mcp_builder(sub_estimate) is False


def test_reasoning_string_populated():
    """Reasoning string should contain fix_minutes and recommendation."""
    estimate = estimate_fix_cost("ImportError", "err", "openfoam", has_substitute=True)
    assert "2.0" in estimate.reasoning
    assert "fix" in estimate.reasoning
    assert len(estimate.reasoning) > 0


def test_get_timeout_for_complexity():
    """Verify all three complexity levels return correct buffered timeouts."""
    assert get_timeout_for_complexity(FixComplexity.simple) == 180
    assert get_timeout_for_complexity(FixComplexity.moderate) == 450
    assert get_timeout_for_complexity(FixComplexity.complex) == 900
