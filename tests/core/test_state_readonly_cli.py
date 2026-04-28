"""Regression tests for read-only state-backed CLI commands."""

from __future__ import annotations

import json
import re
from pathlib import Path

from typer.testing import CliRunner

from gpd.cli import app
from gpd.core.constants import STATE_JSON_BACKUP_FILENAME
from gpd.core.state import default_state_dict, generate_state_markdown


class _StableCliRunner(CliRunner):
    def invoke(self, *args, **kwargs):
        kwargs.setdefault("color", False)
        return super().invoke(*args, **kwargs)


runner = _StableCliRunner()
_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def _strip_ansi(text: str) -> str:
    return _ANSI_ESCAPE_RE.sub("", text)


def _write_backup_only_project(tmp_path: Path) -> Path:
    planning = tmp_path / "GPD"
    planning.mkdir()
    state = default_state_dict()
    state["position"].update(
        {
            "current_phase": "02",
            "current_phase_name": "Read Only",
            "status": "Executing",
        }
    )
    state["contract_alignment"] = {
        "confirmed_at": "2026-04-28T00:00:00+00:00",
        "confirmed_contract_hash": "sha256:" + "a" * 64,
        "confirmed_context_hash": "sha256:" + "b" * 64,
    }
    (planning / STATE_JSON_BACKUP_FILENAME).write_text(json.dumps(state, indent=2), encoding="utf-8")
    (planning / "STATE.md").write_text(generate_state_markdown(state), encoding="utf-8")
    return tmp_path


def _assert_no_recovery_write(project_root: Path) -> None:
    planning = project_root / "GPD"
    assert not (planning / "state.json").exists()
    assert not (planning / "state.json.lock").exists()
    assert (planning / STATE_JSON_BACKUP_FILENAME).exists()


def test_state_load_cli_is_read_only_for_fallback_recovery(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project_root = _write_backup_only_project(tmp_path)
    monkeypatch.chdir(project_root)

    result = runner.invoke(app, ["--raw", "state", "load"], catch_exceptions=False)

    assert result.exit_code == 0, _strip_ansi(result.output)
    payload = json.loads(_strip_ansi(result.output))
    assert payload["state_source"] == "state.json.bak"
    assert payload["state"]["position"]["current_phase"] == "02"
    _assert_no_recovery_write(project_root)


def test_state_get_include_cli_is_read_only_for_fallback_recovery(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project_root = _write_backup_only_project(tmp_path)
    monkeypatch.chdir(project_root)

    result = runner.invoke(app, ["--raw", "state", "get", "--include", "position"], catch_exceptions=False)

    assert result.exit_code == 0, _strip_ansi(result.output)
    payload = json.loads(_strip_ansi(result.output))
    assert payload["position"]["current_phase"] == "02"
    _assert_no_recovery_write(project_root)


def test_state_get_cli_is_read_only_for_markdown_state(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project_root = _write_backup_only_project(tmp_path)
    monkeypatch.chdir(project_root)

    result = runner.invoke(app, ["--raw", "state", "get"], catch_exceptions=False)

    assert result.exit_code == 0, _strip_ansi(result.output)
    payload = json.loads(_strip_ansi(result.output))
    assert "# Research State" in payload["content"]
    _assert_no_recovery_write(project_root)


def test_state_snapshot_cli_is_read_only_for_fallback_recovery(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project_root = _write_backup_only_project(tmp_path)
    monkeypatch.chdir(project_root)

    result = runner.invoke(app, ["--raw", "state", "snapshot"], catch_exceptions=False)

    assert result.exit_code == 0, _strip_ansi(result.output)
    payload = json.loads(_strip_ansi(result.output))
    assert payload["current_phase"] == "02"
    _assert_no_recovery_write(project_root)


def test_contract_alignment_status_cli_is_read_only_for_fallback_recovery(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project_root = _write_backup_only_project(tmp_path)
    monkeypatch.chdir(project_root)

    result = runner.invoke(app, ["contract", "alignment-status"], catch_exceptions=False)

    assert result.exit_code == 0, _strip_ansi(result.output)
    payload = json.loads(_strip_ansi(result.output))
    assert payload == {
        "confirmed_at": "2026-04-28T00:00:00+00:00",
        "confirmed_contract_hash": "sha256:" + "a" * 64,
        "confirmed_context_hash": "sha256:" + "b" * 64,
    }
    _assert_no_recovery_write(project_root)


def test_contract_context_fingerprint_cli_is_read_only_for_fallback_recovery(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project_root = _write_backup_only_project(tmp_path)
    state = json.loads((project_root / "GPD" / STATE_JSON_BACKUP_FILENAME).read_text(encoding="utf-8"))
    state["position"]["current_phase"] = "01"
    (project_root / "GPD" / STATE_JSON_BACKUP_FILENAME).write_text(json.dumps(state, indent=2), encoding="utf-8")
    phase_dir = project_root / "GPD" / "phases" / "01-test"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-test-CONTEXT.md").write_text("phase context\n", encoding="utf-8")
    monkeypatch.chdir(project_root)

    result = runner.invoke(app, ["--raw", "contract", "context-fingerprint"], catch_exceptions=False)

    assert result.exit_code == 0, _strip_ansi(result.output)
    assert json.loads(_strip_ansi(result.output))["result"].startswith("sha256:")
    _assert_no_recovery_write(project_root)
