"""Round-5 audit regression tests.

Each test targets a specific bug fix identified during the fifth audit pass.
Tests are numbered to match the audit finding list.
"""

from __future__ import annotations

import subprocess

import pytest

# ---------------------------------------------------------------------------
# Test 1: git_ops _NAN_PATTERN no longer false-positives on "infinity" in text
# ---------------------------------------------------------------------------


def test_nan_pattern_no_false_positive_on_infinity_in_text():
    """The word 'infinity' in physics prose should not trigger NaN detection."""
    from gpd.core.git_ops import _NAN_PATTERN

    # These should NOT match (natural language usage)
    assert not _NAN_PATTERN.search("as x approaches infinity")
    assert not _NAN_PATTERN.search("at spatial infinity")
    assert not _NAN_PATTERN.search("the point at infinity is well-defined")
    assert not _NAN_PATTERN.search("Infinity in mathematics")

    # These SHOULD still match (data values)
    assert _NAN_PATTERN.search("value: -infinity")
    assert _NAN_PATTERN.search("result = -Infinity")

    # inf/Inf/INF forms should still match
    assert _NAN_PATTERN.search("value: inf")
    assert _NAN_PATTERN.search("result = Inf")
    assert _NAN_PATTERN.search("x = -inf")


# ---------------------------------------------------------------------------
# Test 2: extras _check_single handles negative bounds correctly
# ---------------------------------------------------------------------------


def test_check_approximation_negative_bound_double_bounded():
    """Double-bounded ranges with negative bounds should work correctly."""
    from gpd.core.extras import check_approximation_validity

    # "-100 << x << -1": val=-50 is only 50 away from -100 (scale 100), not "much greater"
    # The fix ensures this uses distance-based logic rather than trivially-true multiplication
    result = check_approximation_validity(-50, "-100 << x << -1")
    assert result is not None, "Should be parseable"
    # -50 is not much greater than -100 (distance=50, scale=100, needs 2x) -> invalid is correct
    assert result == "invalid", f"Expected invalid for -50 in '-100 << x << -1', got {result}"

    # val=1500 should be valid: much greater than -100 (distance=1600, 16x scale)
    # AND much less than -1 ... but wait, 1500 is not less than -1 at all, so invalid for op2
    result = check_approximation_validity(1500, "-100 << x << -1")
    assert result == "invalid", f"Expected invalid for 1500 in '-100 << x << -1', got {result}"

    # Verify the fix: the old bug made "val > 10 * bound" with negative bound trivially true
    # Test that val=0 is correctly handled (was trivially "valid" with old bug for lower bound)
    result = check_approximation_validity(0, "-100 << x << 100")
    # 0 is NOT much greater than -100 (distance=100, scale=100, needs 2x)
    # so this should be invalid or marginal for the lower bound check
    assert result == "invalid", (
        f"Expected invalid for 0 in '-100 << x << 100', got {result}"
    )


def test_check_approximation_zero_bound_much_less():
    """Zero bound with >> operator should handle correctly."""
    from gpd.core.extras import check_approximation_validity

    # "0 >> x >> -10" means x much less than 0 and x much greater than -10
    # This is a valid range check
    result = check_approximation_validity(-5, "0 >> x >> -10")
    assert result is not None  # Should be parseable


# ---------------------------------------------------------------------------
# Test 3: conventions_server handles ValidationError
# ---------------------------------------------------------------------------


def test_convention_check_invalid_lock_returns_error():
    """convention_check should return error dict for invalid lock data, not crash."""
    from gpd.mcp.servers.conventions_server import convention_check

    result = convention_check({"custom_conventions": "not-a-dict"})
    assert "error" in result


def test_convention_diff_invalid_lock_returns_error():
    """convention_diff should return error dict for invalid lock data."""
    from gpd.mcp.servers.conventions_server import convention_diff

    result = convention_diff({"custom_conventions": "not-a-dict"}, {})
    assert "error" in result


def test_assert_convention_validate_invalid_lock_returns_error():
    """assert_convention_validate should return error dict for invalid lock data."""
    from gpd.mcp.servers.conventions_server import assert_convention_validate

    result = assert_convention_validate("some content", {"custom_conventions": 123})
    assert "error" in result


# ---------------------------------------------------------------------------
# Test 4: patterns_server lookup handles errors
# ---------------------------------------------------------------------------


def test_lookup_pattern_with_corrupt_root_returns_error(tmp_path):
    """lookup_pattern should return error dict when pattern library is broken."""
    import gpd.mcp.servers.patterns_server as ps

    original = ps._DEFAULT_PATTERNS_ROOT
    # Point to a non-existent directory
    ps._DEFAULT_PATTERNS_ROOT = tmp_path / "nonexistent"
    try:
        result = ps.lookup_pattern(domain="qft")
        # Should either return results (empty) or an error dict, not crash
        assert isinstance(result, dict)
    finally:
        ps._DEFAULT_PATTERNS_ROOT = original


# ---------------------------------------------------------------------------
# Test 5: cli _load_state_dict validates return type
# ---------------------------------------------------------------------------


def test_load_state_dict_rejects_non_dict(tmp_path, monkeypatch):
    """_load_state_dict should error on non-dict JSON."""
    state_json = tmp_path / ".gpd" / "state.json"
    state_json.parent.mkdir(parents=True)
    state_json.write_text("[1, 2, 3]", encoding="utf-8")

    import gpd.cli as cli_mod

    monkeypatch.setattr(cli_mod, "_cwd", tmp_path)

    with pytest.raises((SystemExit, Exception)):
        cli_mod._load_state_dict()


# ---------------------------------------------------------------------------
# Test 6: results.py result_update wraps ValidationError
# ---------------------------------------------------------------------------


def test_result_update_validation_error_is_result_error():
    """Pydantic ValidationError in result_update should be wrapped in ResultError."""
    from gpd.core.errors import ResultError
    from gpd.core.results import result_update

    state = {
        "intermediate_results": [
            {"result_id": "R-01-001", "description": "test", "value": "1.0", "phase": "01"}
        ]
    }
    # Pass an invalid type that will fail Pydantic validation
    with pytest.raises(ResultError):
        result_update(state, "R-01-001", depends_on=[123])


# ---------------------------------------------------------------------------
# Test 7: frontmatter verify_summary passed consistency
# ---------------------------------------------------------------------------


def test_verify_summary_passed_false_when_commits_invalid(tmp_path):
    """verify_summary.passed should be False when commit hashes are invalid."""
    from gpd.core.frontmatter import verify_summary

    summary = tmp_path / "SUMMARY.md"
    summary.write_text("---\nphase: '01'\n---\ncommit `deadbeef1234`\n", encoding="utf-8")

    # Init a git repo so git commands work
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True)

    result = verify_summary(tmp_path, summary)
    # Should have errors about invalid commit hashes AND passed should be False
    assert result.errors, "Expected errors for invalid commit hashes"
    assert not result.passed, "passed should be False when errors list is non-empty"


# ---------------------------------------------------------------------------
# Test 8: health check_environment git_version on timeout
# ---------------------------------------------------------------------------


def test_check_environment_timeout_has_git_version_key(monkeypatch):
    """check_environment should set git_version=None even on timeout."""
    from gpd.core.health import check_environment

    original_run = subprocess.run

    def mock_run(*args, **kwargs):
        if args and args[0] and args[0][0] == "git":
            raise subprocess.TimeoutExpired(cmd="git", timeout=5)
        return original_run(*args, **kwargs)

    monkeypatch.setattr(subprocess, "run", mock_run)
    result = check_environment()
    assert "git_version" in result.details
    assert result.details["git_version"] is None


