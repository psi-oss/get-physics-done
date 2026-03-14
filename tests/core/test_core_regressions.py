"""Behavior-focused core regression coverage."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest


def _setup_project_with_summary(tmp_path: Path, yaml_block: str) -> Path:
    from gpd.core.constants import PHASES_DIR_NAME, PLANNING_DIR_NAME

    gpd_dir = tmp_path / PLANNING_DIR_NAME
    phases_dir = gpd_dir / PHASES_DIR_NAME / "01-test"
    phases_dir.mkdir(parents=True)
    summary = phases_dir / "plan-01-SUMMARY.md"
    summary.write_text(f"---\ntitle: test\n---\n\n```yaml\n{yaml_block}\n```\n", encoding="utf-8")
    return tmp_path


def _write_state_md(tmp_path: Path, decisions_body: str) -> Path:
    planning = tmp_path / ".gpd"
    planning.mkdir(exist_ok=True)
    (planning / "STATE.md").write_text(
        "# State\n\n"
        "## Position\n\n"
        "Current Phase: 05\n\n"
        "### Decisions\n"
        f"{decisions_body}\n\n"
        "### Blockers\n\n"
        "None.\n",
        encoding="utf-8",
    )
    return tmp_path


def test_safe_read_file_returns_none_for_binary_files(tmp_path: Path) -> None:
    from gpd.core.utils import safe_read_file

    binary_file = tmp_path / "data.bin"
    binary_file.write_bytes(b"\x80\x81\x82\xff\xfe")

    assert safe_read_file(binary_file) is None
    assert safe_read_file(tmp_path / "missing.txt") is None
    assert safe_read_file(tmp_path) is None


def test_result_not_found_error_str_has_no_surrounding_quotes() -> None:
    from gpd.core.errors import ResultNotFoundError

    err = ResultNotFoundError("R-1")

    assert str(err) == 'Result "R-1" not found'
    assert not str(err).startswith("'")
    assert not str(err).endswith("'")
    assert str(err) == Exception.__str__(err)


def test_question_list_preserves_mixed_string_and_dict_items() -> None:
    from gpd.core.extras import question_list

    result = question_list(
        {
            "open_questions": [
                "Why does the coupling diverge?",
                {"text": "Is the vacuum stable?", "priority": "high"},
                "What about unitarity?",
            ]
        }
    )

    assert result[0] == "Why does the coupling diverge?"
    assert isinstance(result[1], dict)
    assert result[1]["text"] == "Is the vacuum stable?"
    assert result[2] == "What about unitarity?"


def test_calculation_list_preserves_mixed_string_and_dict_items() -> None:
    from gpd.core.extras import calculation_list

    result = calculation_list(
        {
            "active_calculations": [
                "Compute one-loop correction",
                {"text": "Evaluate path integral", "status": "in-progress"},
                "Check Ward identity",
            ]
        }
    )

    assert result[0] == "Compute one-loop correction"
    assert isinstance(result[1], dict)
    assert result[1]["text"] == "Evaluate path integral"
    assert result[2] == "Check Ward identity"


def test_approximation_list_skips_corrupt_entries() -> None:
    from gpd.core.extras import approximation_list

    result = approximation_list(
        {
            "approximations": [
                {
                    "name": "small-x",
                    "validity_range": "x << 1",
                    "controlling_param": "x",
                    "current_value": "0.01",
                    "status": "valid",
                },
                "corrupt-string-entry",
                None,
                42,
            ]
        }
    )

    assert len(result) == 1
    assert result[0].name == "small-x"


def test_check_approximation_handles_edge_cases() -> None:
    from gpd.core.extras import check_approximation_validity

    assert check_approximation_validity(-1000, "x >> 0") == "invalid"
    assert check_approximation_validity(1.0, "0.1 << x << 100") == "marginal"
    assert check_approximation_validity(-50, "-100 << x << -1") == "invalid"


def test_json_set_reports_type_mismatch_errors(tmp_path: Path) -> None:
    from gpd.core.json_utils import json_set

    fp = tmp_path / "data.json"
    fp.write_text(json.dumps({"items": [1, 2, 3]}), encoding="utf-8")

    result = json_set(str(fp), "items.foo", '"bar"')

    assert result["updated"] is False
    assert "error" in result


@pytest.mark.parametrize(
    "yaml_block",
    [
        "gpd_return: completed",
        "gpd_return:\n  - a\n  - b",
        "gpd_return: null",
    ],
)
def test_check_latest_return_tolerates_non_dict_gpd_return(tmp_path: Path, yaml_block: str) -> None:
    from gpd.core.health import check_latest_return

    result = check_latest_return(_setup_project_with_summary(tmp_path, yaml_block))

    assert result.label == "Latest Return Envelope"


def test_apply_fixes_resets_config_on_parse_error(tmp_path: Path) -> None:
    from gpd.core.health import CheckStatus, HealthCheck, _apply_fixes

    gpd_dir = tmp_path / ".gpd"
    gpd_dir.mkdir()

    fixes = _apply_fixes(
        tmp_path,
        [
            HealthCheck(
                status=CheckStatus.FAIL,
                label="Config",
                issues=["config.json parse error: Expecting value: line 1 column 1 (char 0)"],
            )
        ],
    )

    assert any("config.json" in fix.lower() or "default" in fix.lower() for fix in fixes)
    assert (gpd_dir / "config.json").exists()


def test_decision_count_regex_counts_unbracketed_entries(tmp_path: Path) -> None:
    from gpd.core.health import CheckStatus, check_compaction_needed

    decisions = "\n".join(f"- Phase {idx % 5 + 1}: Decision {idx + 1}" for idx in range(5))
    result = check_compaction_needed(_write_state_md(tmp_path, decisions))

    assert result.details["decisions"] == 5
    assert result.status == CheckStatus.OK


def test_verify_output_checksum_trims_whitespace(tmp_path: Path) -> None:
    from gpd.core.reproducibility import compute_sha256, verify_output_checksum

    test_file = tmp_path / "data.txt"
    test_file.write_text("hello world", encoding="utf-8")
    expected = compute_sha256(test_file)

    assert verify_output_checksum(test_file, f"  {expected}  ") is True
    assert verify_output_checksum(test_file, f"\n{expected}\n") is True


def test_empty_manifest_has_full_checksum_coverage() -> None:
    from gpd.core.reproducibility import validate_reproducibility_manifest

    manifest = {
        "paper_title": "Test Paper",
        "date": "2025-01-01",
        "environment": {
            "python_version": "3.12",
            "package_manager": "pip",
            "required_packages": [{"package": "numpy", "version": "1.26.0", "purpose": "numerics"}],
            "lock_file": "requirements.txt",
        },
        "execution_steps": [{"name": "run", "command": "python run.py"}],
        "expected_results": [
            {
                "quantity": "energy",
                "expected_value": "42.0",
                "tolerance": "0.1",
                "script": "run.py",
            }
        ],
    }

    result = validate_reproducibility_manifest(manifest)

    assert result.checksum_coverage_percent == 100.0


def test_result_update_wraps_validation_error_as_result_error() -> None:
    from gpd.core.errors import ResultError
    from gpd.core.results import result_update

    state = {
        "intermediate_results": [
            {"result_id": "R-01-001", "description": "test", "value": "1.0", "phase": "01"}
        ]
    }

    with pytest.raises(ResultError):
        result_update(state, "R-01-001", depends_on=[123])


def test_result_add_auto_id_uses_explicit_phase_override() -> None:
    from gpd.core.results import result_add

    state = {
        "position": {"current_phase": "01"},
        "intermediate_results": [
            {"id": "R-02-01-seed", "description": "existing", "phase": "02", "depends_on": [], "verified": False}
        ],
    }

    result = result_add(state, description="new result", phase="02")

    assert result.phase == "02"
    assert result.id.startswith("R-02-02-")


def test_verify_summary_marks_invalid_commits_as_failed(tmp_path: Path) -> None:
    from gpd.core.frontmatter import verify_summary

    summary = tmp_path / "SUMMARY.md"
    summary.write_text("---\nphase: '01'\n---\ncommit `deadbeef1234`\n", encoding="utf-8")

    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=False)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True, check=False)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True, check=False)

    result = verify_summary(tmp_path, summary)

    assert result.errors
    assert result.passed is False


def test_check_environment_timeout_still_reports_git_version_key(monkeypatch: pytest.MonkeyPatch) -> None:
    from gpd.core.health import check_environment

    original_run = subprocess.run

    def mock_run(*args: object, **kwargs: object) -> object:
        if args and args[0] and args[0][0] == "git":
            raise subprocess.TimeoutExpired(cmd="git", timeout=5)
        return original_run(*args, **kwargs)

    monkeypatch.setattr(subprocess, "run", mock_run)
    result = check_environment()

    assert "git_version" in result.details
    assert result.details["git_version"] is None


def test_safe_parse_int_accepts_bool_and_float_inputs() -> None:
    from gpd.core.utils import safe_parse_int

    assert safe_parse_int(True) == 1
    assert safe_parse_int(False) == 0
    assert safe_parse_int(3.14) == 3


def test_verification_checks_api_handles_valid_and_invalid_ids() -> None:
    from gpd.core.verification_checks import get_verification_check, list_verification_checks

    assert get_verification_check("5.1") is not None
    assert get_verification_check("contract.benchmark_reproduction") is not None
    assert get_verification_check("99.99") is None
    assert len(list_verification_checks()) >= 15


def test_error_class_3_maps_to_expected_primary_checks() -> None:
    from gpd.core.verification_checks import ERROR_CLASS_COVERAGE_DEFS

    error_class = next((entry for entry in ERROR_CLASS_COVERAGE_DEFS if entry.error_class_id == 3), None)

    assert error_class is not None
    assert error_class.primary_checks == ["5.11", "5.13"]


def test_pre_commit_nonfinite_detection_avoids_limit_notation_false_positives(tmp_path) -> None:
    from gpd.core.git_ops import cmd_pre_commit_check

    good = tmp_path / "good.md"
    good.write_text(
        "---\nstatus: active\n---\n\n"
        "As x approaches infinity the bound remains finite.\n"
        "Thermodynamic limit: T -> inf.\n"
        "Branch cut on (-infinity, 0].\n",
        encoding="utf-8",
    )
    bad = tmp_path / "bad.md"
    bad.write_text("---\nstatus: done\n---\n\nResult: .NaN\n", encoding="utf-8")

    good_result = cmd_pre_commit_check(tmp_path, ["good.md"])
    bad_result = cmd_pre_commit_check(tmp_path, ["bad.md"])

    assert good_result.passed is True
    assert good_result.details[0].has_nan is False
    assert bad_result.passed is False
    assert bad_result.details[0].has_nan is True


def test_summary_extract_result_accepts_supported_conventions_types() -> None:
    from gpd.core.commands import SummaryExtractResult

    assert SummaryExtractResult(path="test.md", conventions={"metric": "mostly-minus"}).conventions == {
        "metric": "mostly-minus"
    }
    assert SummaryExtractResult(path="test.md", conventions=["metric=mostly-minus"]).conventions == [
        "metric=mostly-minus"
    ]
    assert SummaryExtractResult(path="test.md", conventions="mostly-minus").conventions == "mostly-minus"
    assert SummaryExtractResult(path="test.md", conventions=None).conventions is None


def test_summary_extract_result_rejects_arbitrary_objects() -> None:
    from pydantic import ValidationError as PydanticValidationError

    from gpd.core.commands import SummaryExtractResult

    with pytest.raises(PydanticValidationError):
        SummaryExtractResult(path="test.md", conventions=object())


def test_body_one_liner_regex_ignores_mid_document_frontmatter() -> None:
    from gpd.core.commands import _BODY_ONE_LINER_RE

    content = "---\ntitle: test\n---\n\n**First line**\n\n---\n\n**Second line**"
    match = _BODY_ONE_LINER_RE.search(content)

    assert match is not None
    assert match.group(1) == "First line"


def test_show_events_returns_empty_when_session_logs_have_no_matches(tmp_path: Path) -> None:
    from gpd.core.observability import show_events

    sessions_dir = tmp_path / ".gpd" / "observability" / "sessions"
    sessions_dir.mkdir(parents=True)
    (sessions_dir / "session-a.jsonl").write_text(
        '{"event_id": "e1", "timestamp": "2026-03-10T00:00:00+00:00", "session_id": "session-a", "action": "log", "category": "test", "name": "demo", "status": "ok"}\n',
        encoding="utf-8",
    )

    result = show_events(tmp_path, category="nonexistent")
    events = result.events if hasattr(result, "events") else result.get("events", [])

    assert events == []


def test_coverage_metric_rejects_nonzero_satisfied_with_zero_total() -> None:
    from gpd.core.paper_quality import CoverageMetric

    with pytest.raises(ValueError):
        CoverageMetric(satisfied=5, total=0)


def test_suggest_next_handles_non_utf8_state_json(tmp_path: Path) -> None:
    from gpd.core.suggest import suggest_next

    gpd_dir = tmp_path / ".gpd"
    gpd_dir.mkdir()
    (gpd_dir / "state.json").write_bytes(b'{"position": "\x80\x81\x82"}')

    assert suggest_next(tmp_path) is not None


def test_regression_check_detects_standalone_verification_files(tmp_path: Path) -> None:
    from gpd.core.commands import cmd_regression_check
    from gpd.core.constants import STANDALONE_VERIFICATION

    phase_dir = tmp_path / ".gpd" / "phases" / "01-setup"
    phase_dir.mkdir(parents=True)
    (phase_dir / "task-1-PLAN.md").write_text("plan", encoding="utf-8")
    (phase_dir / "task-1-SUMMARY.md").write_text("---\nphase: 1\n---\n# Summary\n", encoding="utf-8")
    (phase_dir / STANDALONE_VERIFICATION).write_text(
        "---\nstatus: gaps_found\nscore: 3/5\n---\n# Verification\nSome gaps here.\n",
        encoding="utf-8",
    )

    result = cmd_regression_check(tmp_path)

    assert result.phases_checked == 1
    assert any(issue.type == "unresolved_verification_issues" for issue in result.issues)
