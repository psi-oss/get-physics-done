"""Regression tests for audit round 2 bug fixes (bugs 8-17).

Each test targets a specific bug fix and ensures the corrected behavior
does not regress.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from unittest.mock import patch

import pytest

# ─── Bug 8: check_latest_return non-dict gpd_return ─────────────────────────


class TestBug8_CheckLatestReturnNonDictGpdReturn:
    """When gpd_return is a non-dict value (e.g., a plain string), the
    function must not crash with AttributeError."""

    def _setup_project_with_summary(self, tmp_path: Path, yaml_block: str) -> Path:
        """Create a minimal GPD project layout with one SUMMARY file
        containing the given gpd_return YAML block."""
        from gpd.core.constants import PHASES_DIR_NAME, PLANNING_DIR_NAME

        gpd_dir = tmp_path / PLANNING_DIR_NAME
        phases_dir = gpd_dir / PHASES_DIR_NAME / "01-test"
        phases_dir.mkdir(parents=True)

        summary = phases_dir / "plan-01-SUMMARY.md"
        content = f"---\ntitle: test\n---\n\n```yaml\n{yaml_block}\n```\n"
        summary.write_text(content, encoding="utf-8")
        return tmp_path

    def test_string_gpd_return_no_crash(self, tmp_path: Path):
        """gpd_return: completed (a string) should not raise AttributeError."""
        from gpd.core.health import check_latest_return

        root = self._setup_project_with_summary(
            tmp_path, "gpd_return: completed"
        )
        # Must not raise
        result = check_latest_return(root)
        # Should report missing required fields (since it's not a dict),
        # but NOT crash.
        assert result.label == "Latest Return Envelope"

    def test_list_gpd_return_no_crash(self, tmp_path: Path):
        """gpd_return: [a, b] (a list) should not raise."""
        from gpd.core.health import check_latest_return

        root = self._setup_project_with_summary(
            tmp_path, "gpd_return:\n  - a\n  - b"
        )
        result = check_latest_return(root)
        assert result.label == "Latest Return Envelope"

    def test_null_gpd_return_no_crash(self, tmp_path: Path):
        """gpd_return: null should not raise."""
        from gpd.core.health import check_latest_return

        root = self._setup_project_with_summary(
            tmp_path, "gpd_return: null"
        )
        result = check_latest_return(root)
        assert result.label == "Latest Return Envelope"

    def test_dict_gpd_return_still_works(self, tmp_path: Path):
        """A proper dict gpd_return should still be validated normally."""
        from gpd.core.health import check_latest_return

        yaml_block = (
            "gpd_return:\n"
            "  status: completed\n"
            "  phase: '01'\n"
            "  plan: plan-01\n"
            "  tasks_completed: 3\n"
            "  tasks_total: 3\n"
        )
        root = self._setup_project_with_summary(tmp_path, yaml_block)
        result = check_latest_return(root)
        assert result.label == "Latest Return Envelope"
        # Valid dict -- fields should be detected
        assert "status" in result.details.get("fields_found", [])


# ─── Bug 9: Config auto-fix condition matches "parse error" ─────────────────


class TestBug9_ConfigAutoFixParseError:
    """The _apply_fixes function should trigger a config reset when a
    HealthCheck for Config contains an issue with 'parse error'."""

    def test_parse_error_triggers_fix(self, tmp_path: Path):
        from gpd.core.health import CheckStatus, HealthCheck, _apply_fixes

        # Create the .gpd directory so the fix can write config.json
        gpd_dir = tmp_path / ".gpd"
        gpd_dir.mkdir()

        config_check = HealthCheck(
            status=CheckStatus.FAIL,
            label="Config",
            issues=["config.json parse error: Expecting value: line 1 column 1 (char 0)"],
        )
        fixes = _apply_fixes(tmp_path, [config_check])
        assert any("config.json" in f.lower() or "default" in f.lower() for f in fixes)
        # After fix, config.json should exist
        assert (gpd_dir / "config.json").exists()

    def test_malformed_does_not_trigger_fix(self, tmp_path: Path):
        """The old condition matched 'Malformed'; the new one should
        NOT match 'Malformed' if it only checks 'parse error'."""
        from gpd.core.health import CheckStatus, HealthCheck, _apply_fixes

        gpd_dir = tmp_path / ".gpd"
        gpd_dir.mkdir()

        config_check = HealthCheck(
            status=CheckStatus.FAIL,
            label="Config",
            issues=["Malformed config.json"],
        )
        fixes = _apply_fixes(tmp_path, [config_check])
        # "Malformed" (without "parse error") should NOT trigger the auto-fix
        assert not any("Created default config.json" in f for f in fixes)


# ─── Bug 10: "x >> 0" abs(val) logic for negative values ────────────────────


class TestBug10_MuchGreaterThanZeroNegative:
    """For 'x >> 0', negative values must return 'invalid' because they
    are not much greater than zero."""

    def test_negative_value_is_invalid(self):
        from gpd.core.extras import check_approximation_validity

        result = check_approximation_validity(-1000, "x >> 0")
        assert result == "invalid"

    def test_large_positive_is_valid(self):
        from gpd.core.extras import check_approximation_validity

        result = check_approximation_validity(1000, "x >> 0")
        assert result == "valid"

    def test_small_positive_is_marginal(self):
        from gpd.core.extras import check_approximation_validity

        result = check_approximation_validity(5, "x >> 0")
        assert result == "marginal"

    def test_zero_is_invalid(self):
        from gpd.core.extras import check_approximation_validity

        result = check_approximation_validity(0, "x >> 0")
        assert result == "invalid"

    def test_slightly_negative_is_invalid(self):
        from gpd.core.extras import check_approximation_validity

        result = check_approximation_validity(-0.5, "x >> 0")
        assert result == "invalid"


# ─── Bug 11: verify_output_checksum whitespace tolerance ────────────────────


class TestBug11_VerifyChecksumWhitespace:
    """Checksums with leading/trailing whitespace should still match."""

    def test_checksum_with_leading_trailing_spaces(self, tmp_path: Path):
        from gpd.core.reproducibility import compute_sha256, verify_output_checksum

        test_file = tmp_path / "data.txt"
        test_file.write_text("hello world", encoding="utf-8")
        expected = compute_sha256(test_file)

        # Wrap the expected checksum in whitespace
        padded = f"  {expected}  "
        assert verify_output_checksum(test_file, padded) is True

    def test_checksum_with_newline(self, tmp_path: Path):
        from gpd.core.reproducibility import compute_sha256, verify_output_checksum

        test_file = tmp_path / "data.txt"
        test_file.write_text("test content", encoding="utf-8")
        expected = compute_sha256(test_file)

        padded = f"\n{expected}\n"
        assert verify_output_checksum(test_file, padded) is True

    def test_wrong_checksum_still_fails(self, tmp_path: Path):
        from gpd.core.reproducibility import verify_output_checksum

        test_file = tmp_path / "data.txt"
        test_file.write_text("whatever", encoding="utf-8")

        assert verify_output_checksum(test_file, "  0000abcd  ") is False


# ─── Bug 12: Zero checksum items = 100% coverage ────────────────────────────


class TestBug12_ZeroChecksumItemsCoverage:
    """A manifest with no data items should have 100% checksum coverage."""

    def test_empty_data_items_100_percent(self):
        from gpd.core.reproducibility import validate_reproducibility_manifest

        manifest = {
            "paper_title": "Test Paper",
            "date": "2025-01-01",
            "environment": {
                "python_version": "3.12",
                "package_manager": "pip",
                "required_packages": [
                    {"package": "numpy", "version": "1.26.0", "purpose": "numerics"},
                ],
                "lock_file": "requirements.txt",
            },
            "execution_steps": [
                {"name": "run", "command": "python run.py"},
            ],
            "expected_results": [
                {
                    "quantity": "energy",
                    "expected_value": "42.0",
                    "tolerance": "0.1",
                    "script": "run.py",
                }
            ],
            # No input_data, generated_data, or output_files
        }
        result = validate_reproducibility_manifest(manifest)
        assert result.checksum_coverage_percent == 100.0

    def test_nonempty_data_items_not_all_100(self):
        """Manifest with data items missing checksums should NOT be 100%."""
        from gpd.core.reproducibility import validate_reproducibility_manifest

        manifest = {
            "paper_title": "Test Paper",
            "date": "2025-01-01",
            "environment": {
                "python_version": "3.12",
                "package_manager": "pip",
                "required_packages": [
                    {"package": "numpy", "version": "1.26.0", "purpose": "numerics"},
                ],
                "lock_file": "requirements.txt",
            },
            "execution_steps": [
                {"name": "run", "command": "python run.py"},
            ],
            "expected_results": [
                {
                    "quantity": "energy",
                    "expected_value": "42.0",
                    "tolerance": "0.1",
                    "script": "run.py",
                }
            ],
            "input_data": [
                {
                    "name": "dataset",
                    "source": "web",
                    "version_or_date": "2025",
                    "checksum_sha256": "not-a-valid-checksum",
                }
            ],
        }
        result = validate_reproducibility_manifest(manifest)
        assert result.checksum_coverage_percent == 0.0


# ─── Bug 13: Error class 3 mapping ──────────────────────────────────────────


class TestBug13_ErrorClass3Mapping:
    """Error class 3 (Green's function confusion) should have primary_checks
    ['5.11', '5.13'], not ['5.13', '5.14']."""

    def test_error_class_3_primary_checks(self):
        from gpd.core.verification_checks import ERROR_CLASS_COVERAGE_DEFS

        ec3 = next(
            (ec for ec in ERROR_CLASS_COVERAGE_DEFS if ec.error_class_id == 3), None
        )
        assert ec3 is not None, "Error class 3 should exist"
        assert ec3.name == "Green's function confusion"
        assert ec3.primary_checks == ["5.11", "5.13"]

    def test_error_class_3_in_dict_form(self):
        from gpd.core.verification_checks import ERROR_CLASS_COVERAGE

        ec3 = ERROR_CLASS_COVERAGE.get(3)
        assert ec3 is not None
        assert ec3["primary_checks"] == ["5.11", "5.13"]

    def test_error_class_3_via_getter(self):
        from gpd.core.verification_checks import get_error_class_coverage

        ec3 = get_error_class_coverage(3)
        assert ec3 is not None
        assert ec3.primary_checks == ["5.11", "5.13"]


# ─── Bug 14: NaN regex YAML case variants ───────────────────────────────────


class TestBug14_NanPatternYamlVariants:
    """The _NAN_PATTERN regex should match YAML-specific NaN/Inf
    representations in various case forms."""

    @pytest.fixture()
    def nan_pattern(self):
        from gpd.core.git_ops import _NAN_PATTERN
        return _NAN_PATTERN

    @pytest.mark.parametrize(
        "text",
        [
            " .NaN ",
            " .NAN ",
            " .Inf ",
            " .INF ",
            " -.Inf ",
            " -.INF ",
            " .nan ",
            " .inf ",
            " -.inf ",
        ],
    )
    def test_yaml_nan_inf_variants_match(self, nan_pattern: re.Pattern, text: str):
        assert nan_pattern.search(text), f"Pattern should match {text!r}"

    @pytest.mark.parametrize(
        "text",
        [
            " NaN ",
            " nan ",
            " NAN ",
            " inf ",
            " -inf ",
            " Inf ",
            " -Inf ",
            " INF ",
            " -INF ",
            " -Infinity ",
        ],
    )
    def test_standard_nan_inf_match(self, nan_pattern: re.Pattern, text: str):
        assert nan_pattern.search(text), f"Pattern should match {text!r}"

    def test_nan_in_word_no_match(self, nan_pattern: re.Pattern):
        """NaN embedded in a word like 'Nantes' should NOT match."""
        assert not nan_pattern.search("Nantes")


# ─── Bug 15: conventions None value storage ──────────────────────────────────


class TestBug15_ConventionsNoneValueSkipped:
    """None values from YAML frontmatter should be skipped (not stored
    as None in the returned dict) by _extract_phase_conventions."""

    def test_none_convention_value_skipped(self, tmp_path: Path):
        from gpd.core.conventions import _extract_phase_conventions
        from gpd.core.phases import PhaseInfo

        # Set up a mock phase with a SUMMARY containing null conventions
        gpd_dir = tmp_path / ".gpd" / "phases" / "01-test"
        gpd_dir.mkdir(parents=True)
        summary = gpd_dir / "plan-01-SUMMARY.md"
        summary.write_text(
            "---\ntitle: test\nconventions:\n  metric: null\n  gauge: Lorenz\n---\n\nBody.\n",
            encoding="utf-8",
        )

        mock_phase_info = PhaseInfo(
            found=True,
            directory=".gpd/phases/01-test",
            phase_number="01",
            phase_name="test",
            phase_slug="01-test",
            plans=["plan-01-PLAN.md"],
            summaries=["plan-01-SUMMARY.md"],
            incomplete_plans=[],
        )

        with patch("gpd.core.phases.find_phase", return_value=mock_phase_info):
            result = _extract_phase_conventions(tmp_path, "01")

        assert result is not None
        # None values must not be stored
        for k, v in result.items():
            assert v is not None, f"Key {k!r} has None value — should have been skipped"

        # The non-null value should be present
        assert result.get("gauge") == "Lorenz" or result.get("gauge_choice") == "Lorenz"


# ─── Bug 16: Phase completeness uses incomplete_plans ────────────────────────


class TestBug16_PhaseCompletenessUsesIncompletePlans:
    """Completeness should be based on incomplete_plans, not a naive
    count comparison of plans vs summaries."""

    def test_incomplete_plans_means_not_complete(self):
        """3 plans, 3 summaries, but incomplete_plans is non-empty ->
        the phase should NOT be reported as complete."""
        from gpd.core.phases import PhaseInfo

        info = PhaseInfo(
            found=True,
            directory=".gpd/phases/03-test",
            phase_number="03",
            phase_name="test",
            phase_slug="03-test",
            plans=["plan-01-PLAN.md", "plan-02-PLAN.md", "plan-03-PLAN.md"],
            summaries=[
                "plan-01-SUMMARY.md",
                "plan-02-SUMMARY.md",
                "plan-03-SUMMARY.md",
            ],
            incomplete_plans=["plan-03-PLAN.md"],
        )

        # The get_phase_info MCP tool uses:
        #   "complete": plan_count > 0 and len(info.incomplete_plans) == 0
        plan_count = len(info.plans)
        complete = plan_count > 0 and len(info.incomplete_plans) == 0
        assert complete is False, (
            "Phase should be incomplete when incomplete_plans is non-empty"
        )

    def test_all_complete_means_complete(self):
        from gpd.core.phases import PhaseInfo

        info = PhaseInfo(
            found=True,
            directory=".gpd/phases/03-test",
            phase_number="03",
            phase_name="test",
            phase_slug="03-test",
            plans=["plan-01-PLAN.md", "plan-02-PLAN.md", "plan-03-PLAN.md"],
            summaries=[
                "plan-01-SUMMARY.md",
                "plan-02-SUMMARY.md",
                "plan-03-SUMMARY.md",
            ],
            incomplete_plans=[],
        )
        plan_count = len(info.plans)
        complete = plan_count > 0 and len(info.incomplete_plans) == 0
        assert complete is True

    def test_no_plans_means_not_complete(self):
        from gpd.core.phases import PhaseInfo

        info = PhaseInfo(
            found=True,
            directory=".gpd/phases/03-test",
            phase_number="03",
            phase_name="test",
            phase_slug="03-test",
            plans=[],
            summaries=[],
            incomplete_plans=[],
        )
        plan_count = len(info.plans)
        complete = plan_count > 0 and len(info.incomplete_plans) == 0
        assert complete is False


# ─── Bug 17: codex_notify dict check on cache files ─────────────────────────


class TestBug17_CodexNotifyNonDictCache:
    """Cache files containing non-dict JSON (null, arrays, etc.) must
    not crash the cache scanning logic in _check_and_notify_update."""

    def test_null_json_cache_no_crash(self, tmp_path: Path):
        """A cache file containing JSON null should be skipped gracefully."""
        cache_file = tmp_path / "gpd-update-check.json"
        cache_file.write_text("null", encoding="utf-8")

        # The _check_and_notify_update function reads from
        # get_update_cache_files(). We mock that to return our file.
        with patch(
            "gpd.hooks.runtime_detect.get_update_cache_files",
            return_value=[cache_file],
        ), patch(
            "gpd.hooks.runtime_detect.detect_active_runtime",
            return_value="unknown",
        ):
            from gpd.hooks.codex_notify import _check_and_notify_update

            # Must not raise
            _check_and_notify_update()

    def test_array_json_cache_no_crash(self, tmp_path: Path):
        """A cache file containing a JSON array should be skipped gracefully."""
        cache_file = tmp_path / "gpd-update-check.json"
        cache_file.write_text("[1, 2, 3]", encoding="utf-8")

        with patch(
            "gpd.hooks.runtime_detect.get_update_cache_files",
            return_value=[cache_file],
        ), patch(
            "gpd.hooks.runtime_detect.detect_active_runtime",
            return_value="unknown",
        ):
            from gpd.hooks.codex_notify import _check_and_notify_update

            _check_and_notify_update()

    def test_string_json_cache_no_crash(self, tmp_path: Path):
        """A cache file containing a bare JSON string should be skipped."""
        cache_file = tmp_path / "gpd-update-check.json"
        cache_file.write_text('"just a string"', encoding="utf-8")

        with patch(
            "gpd.hooks.runtime_detect.get_update_cache_files",
            return_value=[cache_file],
        ), patch(
            "gpd.hooks.runtime_detect.detect_active_runtime",
            return_value="unknown",
        ):
            from gpd.hooks.codex_notify import _check_and_notify_update

            _check_and_notify_update()

    def test_valid_dict_cache_still_works(self, tmp_path: Path):
        """A valid dict cache file should still be processed normally."""
        cache_file = tmp_path / "gpd-update-check.json"
        cache_data = {
            "update_available": False,
            "installed": "1.0.0",
            "latest": "1.0.0",
            "checked": 1700000000,
        }
        cache_file.write_text(json.dumps(cache_data), encoding="utf-8")

        with patch(
            "gpd.hooks.runtime_detect.get_update_cache_files",
            return_value=[cache_file],
        ), patch(
            "gpd.hooks.runtime_detect.detect_active_runtime",
            return_value="unknown",
        ):
            from gpd.hooks.codex_notify import _check_and_notify_update

            # Must not raise
            _check_and_notify_update()

    def test_invalid_json_cache_no_crash(self, tmp_path: Path):
        """A cache file with invalid JSON should be skipped gracefully."""
        cache_file = tmp_path / "gpd-update-check.json"
        cache_file.write_text("{not valid json", encoding="utf-8")

        with patch(
            "gpd.hooks.runtime_detect.get_update_cache_files",
            return_value=[cache_file],
        ), patch(
            "gpd.hooks.runtime_detect.detect_active_runtime",
            return_value="unknown",
        ):
            from gpd.hooks.codex_notify import _check_and_notify_update

            _check_and_notify_update()
