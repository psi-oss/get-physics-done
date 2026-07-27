"""CLI parity tests for the ``gpd convention`` subcommands that closed MCP gaps."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from gpd.cli import app

runner = CliRunner()

_LOCK = {
    "metric_signature": "mostly-plus",
    "fourier_convention": "physics",
    "natural_units": "natural",
}
_MATCHING_ARTIFACT = (
    "% ASSERT_CONVENTION: metric_signature=mostly-plus, fourier_convention=physics, natural_units=natural\n"
    "The derivation body.\n"
)
_MISMATCHED_ARTIFACT = (
    "% ASSERT_CONVENTION: metric_signature=mostly-minus, fourier_convention=physics, natural_units=natural\n"
    "The derivation body.\n"
)


def _invoke(args: list[str]) -> object:
    return runner.invoke(app, ["--raw", *args], catch_exceptions=False)


def test_subfield_defaults_matches_mcp_tool_payload() -> None:
    from gpd.mcp.servers.conventions_server import subfield_defaults

    expected = subfield_defaults("qft")
    result = _invoke(["convention", "subfield-defaults", "qft"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == expected
    assert expected["found"] is True
    assert expected["defaults"]["metric_signature"] == "mostly-minus"
    assert expected["field_count"] == len(expected["defaults"])


def test_subfield_defaults_unknown_domain_lists_available_domains_and_exits_one() -> None:
    from gpd.mcp.servers.conventions_server import subfield_defaults

    expected = subfield_defaults("not-a-subfield")
    result = _invoke(["convention", "subfield-defaults", "not-a-subfield"])

    assert result.exit_code == 1
    assert json.loads(result.output) == expected
    assert expected["found"] is False
    assert "qft" in expected["available_domains"]


def test_validate_assert_with_lock_file_matches_mcp_tool_payload(tmp_path: Path) -> None:
    from gpd.mcp.servers.conventions_server import assert_convention_validate

    artifact = tmp_path / "derivation.tex"
    artifact.write_text(_MATCHING_ARTIFACT, encoding="utf-8")
    lock_path = tmp_path / "lock.json"
    lock_path.write_text(json.dumps(_LOCK), encoding="utf-8")

    expected = assert_convention_validate(_MATCHING_ARTIFACT, dict(_LOCK))
    result = _invoke(["convention", "validate-assert", str(artifact), "--lock", str(lock_path)])

    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == expected
    assert expected["valid"] is True
    assert expected["assertions_found"] == 3
    assert expected["mismatches"] == []


def test_validate_assert_reports_mismatch_and_exits_one(tmp_path: Path) -> None:
    from gpd.mcp.servers.conventions_server import assert_convention_validate

    artifact = tmp_path / "derivation.tex"
    artifact.write_text(_MISMATCHED_ARTIFACT, encoding="utf-8")
    lock_path = tmp_path / "lock.json"
    lock_path.write_text(json.dumps(_LOCK), encoding="utf-8")

    expected = assert_convention_validate(_MISMATCHED_ARTIFACT, dict(_LOCK))
    result = _invoke(["convention", "validate-assert", str(artifact), "--lock", str(lock_path)])

    assert result.exit_code == 1
    assert json.loads(result.output) == expected
    assert expected["valid"] is False
    assert expected["mismatches"][0]["key"] == "metric_signature"
    assert expected["mismatches"][0]["lock_value"] == "mostly-plus"


def test_validate_assert_reads_lock_from_project_state(tmp_path: Path) -> None:
    from gpd.mcp.servers.conventions_server import assert_convention_validate

    project_root = tmp_path / "project"
    (project_root / "GPD").mkdir(parents=True)
    (project_root / "GPD" / "state.json").write_text(
        json.dumps({"convention_lock": dict(_LOCK)}),
        encoding="utf-8",
    )
    artifact = tmp_path / "derivation.tex"
    artifact.write_text(_MATCHING_ARTIFACT, encoding="utf-8")

    expected = assert_convention_validate(_MATCHING_ARTIFACT, dict(_LOCK))
    result = _invoke(["convention", "validate-assert", str(artifact), "--project-dir", str(project_root)])

    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == expected


def test_validate_assert_keeps_an_empty_lock_valid_inside_a_real_gpd_project(tmp_path: Path) -> None:
    """A project that simply has no conventions locked yet is a legitimate pass."""
    project_root = tmp_path / "project"
    (project_root / "GPD").mkdir(parents=True)
    (project_root / "GPD" / "state.json").write_text(json.dumps({"convention_lock": {}}), encoding="utf-8")
    artifact = tmp_path / "derivation.tex"
    artifact.write_text(_MATCHING_ARTIFACT, encoding="utf-8")

    result = _invoke(["convention", "validate-assert", str(artifact), "--project-dir", str(project_root)])

    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["valid"] is True


def test_validate_assert_fails_closed_when_no_lock_is_resolvable(tmp_path: Path) -> None:
    """Outside a GPD project there is no lock, so assertions must not pass vacuously."""
    project_root = tmp_path / "not-a-gpd-project"
    project_root.mkdir()
    artifact = tmp_path / "derivation.tex"
    artifact.write_text(_MATCHING_ARTIFACT, encoding="utf-8")

    result = _invoke(["convention", "validate-assert", str(artifact), "--project-dir", str(project_root)])

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["schema_version"] == 1
    assert payload["error"].startswith("No convention lock is resolvable")
    assert "valid" not in payload, "a missing lock must not be reported as a validation verdict"


def test_validate_assert_lock_stdin_marker_fails_fast_when_stdin_is_a_tty(tmp_path: Path, monkeypatch, capsys) -> None:
    import sys

    import typer.main

    artifact = tmp_path / "derivation.tex"
    artifact.write_text(_MATCHING_ARTIFACT, encoding="utf-8")
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)

    command = typer.main.get_command(app)
    with pytest.raises(SystemExit) as exit_info:
        command.main(
            ["convention", "validate-assert", str(artifact), "--lock", "-"],
            prog_name="gpd",
            standalone_mode=True,
        )

    assert int(exit_info.value.code or 0) != 0
    stderr = capsys.readouterr().err
    assert "Usage" in stderr
    assert "piped on stdin" in stderr


def test_validate_assert_rejects_both_lock_and_project_dir(tmp_path: Path) -> None:
    artifact = tmp_path / "derivation.tex"
    artifact.write_text(_MATCHING_ARTIFACT, encoding="utf-8")
    lock_path = tmp_path / "lock.json"
    lock_path.write_text(json.dumps(_LOCK), encoding="utf-8")

    result = _invoke(
        [
            "convention",
            "validate-assert",
            str(artifact),
            "--lock",
            str(lock_path),
            "--project-dir",
            str(tmp_path),
        ]
    )

    assert result.exit_code == 1
    assert "not both" in result.output


def test_validate_assert_without_assertions_reports_missing_lines_and_exits_one(tmp_path: Path) -> None:
    from gpd.mcp.servers.conventions_server import assert_convention_validate

    artifact = tmp_path / "derivation.tex"
    artifact.write_text("A derivation with no convention header.\n", encoding="utf-8")
    lock_path = tmp_path / "lock.json"
    lock_path.write_text(json.dumps(_LOCK), encoding="utf-8")

    expected = assert_convention_validate("A derivation with no convention header.\n", dict(_LOCK))
    result = _invoke(["convention", "validate-assert", str(artifact), "--lock", str(lock_path)])

    assert result.exit_code == 1
    assert json.loads(result.output) == expected
    assert expected["assertions_found"] == 0
    assert expected["message"].startswith("No ASSERT_CONVENTION lines found")
