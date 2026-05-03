"""Artifact handoff validation for spawned-agent returns."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

from typer.testing import CliRunner

from gpd.cli import app
from gpd.core.handoff_artifacts import validate_handoff_artifacts_markdown


def _return_block(files_written: list[str]) -> str:
    files_written_yaml = (
        "  files_written: []\n"
        if not files_written
        else "  files_written:\n" + "\n".join(f"    - {json.dumps(path)}" for path in files_written) + "\n"
    )
    return (
        "```yaml\n"
        "gpd_return:\n"
        "  status: completed\n"
        f"{files_written_yaml}"
        "  issues: []\n"
        "  next_actions: []\n"
        "```\n"
    )


def test_handoff_artifact_validator_accepts_fresh_in_scope_expected_plan(tmp_path: Path) -> None:
    plan_path = tmp_path / "GPD" / "phases" / "01-test" / "01-01-PLAN.md"
    plan_path.parent.mkdir(parents=True)
    plan_path.write_text("---\nplan_id: 01-01\n---\n", encoding="utf-8")

    result = validate_handoff_artifacts_markdown(
        tmp_path,
        _return_block(["GPD/phases/01-test/01-01-PLAN.md"]),
        expected_artifacts=["GPD/phases/01-test/01-01-PLAN.md"],
        expected_globs=["GPD/phases/01-test/*-PLAN.md"],
        allowed_roots=["GPD/phases/01-test"],
        required_suffixes=["-PLAN.md"],
        require_files_written=True,
        fresh_after=datetime.now(tz=UTC) - timedelta(minutes=1),
    )

    assert result.passed is True
    assert result.checked_files == ["GPD/phases/01-test/01-01-PLAN.md"]


def test_handoff_artifact_validator_rejects_missing_claimed_artifact(tmp_path: Path) -> None:
    result = validate_handoff_artifacts_markdown(
        tmp_path,
        _return_block(["GPD/phases/01-test/01-01-PLAN.md"]),
        allowed_roots=["GPD/phases/01-test"],
        required_suffixes=["-PLAN.md"],
        require_files_written=True,
    )

    assert result.passed is False
    assert "artifact is missing or not a file: GPD/phases/01-test/01-01-PLAN.md" in result.errors


def test_handoff_artifact_validator_rejects_out_of_scope_and_absolute_paths(tmp_path: Path) -> None:
    out_of_scope = tmp_path / "GPD" / "other" / "01-01-PLAN.md"
    out_of_scope.parent.mkdir(parents=True)
    out_of_scope.write_text("plan\n", encoding="utf-8")

    result = validate_handoff_artifacts_markdown(
        tmp_path,
        _return_block(["GPD/other/01-01-PLAN.md", str(out_of_scope)]),
        allowed_roots=["GPD/phases/01-test"],
        required_suffixes=["-PLAN.md"],
    )

    assert result.passed is False
    assert "artifact path is outside allowed roots: GPD/other/01-01-PLAN.md" in result.errors
    assert any("artifact path must be project-local, not absolute" in error for error in result.errors)


def test_handoff_artifact_validator_rejects_expected_artifact_omitted_from_files_written(tmp_path: Path) -> None:
    plan_path = tmp_path / "GPD" / "phases" / "01-test" / "01-01-PLAN.md"
    plan_path.parent.mkdir(parents=True)
    plan_path.write_text("plan\n", encoding="utf-8")

    result = validate_handoff_artifacts_markdown(
        tmp_path,
        _return_block([]),
        expected_artifacts=["GPD/phases/01-test/01-01-PLAN.md"],
        allowed_roots=["GPD/phases/01-test"],
        required_suffixes=["-PLAN.md"],
        require_files_written=True,
    )

    assert result.passed is False
    assert "gpd_return.files_written is empty" in result.errors
    assert (
        "expected artifact not named in gpd_return.files_written: GPD/phases/01-test/01-01-PLAN.md" in result.errors
    )


def test_handoff_artifact_validator_rejects_stale_artifact(tmp_path: Path) -> None:
    plan_path = tmp_path / "GPD" / "phases" / "01-test" / "01-01-PLAN.md"
    plan_path.parent.mkdir(parents=True)
    plan_path.write_text("plan\n", encoding="utf-8")
    stale_time = datetime.now(tz=UTC) - timedelta(hours=2)
    os.utime(plan_path, (stale_time.timestamp(), stale_time.timestamp()))

    result = validate_handoff_artifacts_markdown(
        tmp_path,
        _return_block(["GPD/phases/01-test/01-01-PLAN.md"]),
        allowed_roots=["GPD/phases/01-test"],
        required_suffixes=["-PLAN.md"],
        fresh_after=datetime.now(tz=UTC) - timedelta(minutes=1),
    )

    assert result.passed is False
    assert "artifact is stale relative to --fresh-after: GPD/phases/01-test/01-01-PLAN.md" in result.errors


def test_validate_handoff_artifacts_cli_accepts_stdin_return(tmp_path: Path) -> None:
    plan_path = tmp_path / "GPD" / "phases" / "01-test" / "01-01-PLAN.md"
    plan_path.parent.mkdir(parents=True)
    plan_path.write_text("plan\n", encoding="utf-8")

    result = CliRunner().invoke(
        app,
        [
            "--raw",
            "--cwd",
            str(tmp_path),
            "validate",
            "handoff-artifacts",
            "-",
            "--allowed-root",
            "GPD/phases/01-test",
            "--expected-glob",
            "GPD/phases/01-test/*-PLAN.md",
            "--required-suffix=-PLAN.md",
            "--require-files-written",
        ],
        input=_return_block(["GPD/phases/01-test/01-01-PLAN.md"]),
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["passed"] is True
