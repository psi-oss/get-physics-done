from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_DIR = REPO_ROOT / "src/gpd/commands"
WORKFLOWS_DIR = REPO_ROOT / "src/gpd/specs/workflows"


def test_regression_check_wrapper_marks_quick_as_local_cli_only() -> None:
    text = (COMMANDS_DIR / "regression-check.md").read_text(encoding="utf-8")

    assert 'argument-hint: "[phase] [--quick]"' in text
    assert "local CLI `--quick` flag is a wrapper-only scope reducer" in text
    assert "Local CLI flag `--quick` additionally limits the scan" in text


def test_export_logs_wrapper_surfaces_passthrough_filters() -> None:
    text = (COMMANDS_DIR / "export-logs.md").read_text(encoding="utf-8")

    assert '--command <label>' in text
    assert '--phase <phase>' in text
    assert '--category <name>' in text
    assert "local-only CLI passthrough filters `--command`, `--phase`, and `--category`" in text
    assert 'gpd --raw observe export $ARGUMENTS' in text


def test_export_logs_workflow_parses_and_forwards_passthrough_filters() -> None:
    text = (WORKFLOWS_DIR / "export-logs.md").read_text(encoding="utf-8")

    for flag in ("--command <label>", "--phase <phase>", "--category <name>"):
        assert flag in text

    assert '--command $COMMAND' in text
    assert '--phase $PHASE' in text
    assert '--category $CATEGORY' in text
