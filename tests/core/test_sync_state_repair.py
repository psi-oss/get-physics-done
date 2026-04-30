"""Regression coverage for sync-state backend repair paths."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from gpd.cli import app
from gpd.core.context import init_new_project, init_sync_state
from gpd.core.state import default_state_dict, save_state_json, state_repair_sync

runner = CliRunner()
FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "stage0"


def _state_with_phase(phase: str, *, status: str = "Executing") -> dict:
    state = default_state_dict()
    state["position"]["current_phase"] = phase
    state["position"]["status"] = status
    state["position"]["current_plan"] = "1"
    state["position"]["progress_percent"] = 50
    return state


def _stored_state(root: Path) -> dict:
    return json.loads((root / "GPD" / "state.json").read_text(encoding="utf-8"))


def _ensure_phase_dir(root: Path, phase: str) -> None:
    (root / "GPD" / "phases" / phase).mkdir(parents=True, exist_ok=True)


def _write_lone_backup(root: Path, state: dict) -> None:
    planning = root / "GPD"
    planning.mkdir()
    (planning / "state.json.bak").write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def test_sync_state_repair_uses_valid_backup_when_primary_json_is_corrupt_and_markdown_missing(
    tmp_path: Path,
) -> None:
    backup_state = _state_with_phase("07")
    save_state_json(tmp_path, backup_state)
    _ensure_phase_dir(tmp_path, "07")
    planning = tmp_path / "GPD"
    (planning / "STATE.md").unlink()
    (planning / "state.json").write_text("{bad json\n", encoding="utf-8")

    bootstrap = init_sync_state(tmp_path, stage="sync_bootstrap")
    result = state_repair_sync(tmp_path)

    assert bootstrap["state_json_exists"] is True
    assert bootstrap["state_md_exists"] is False
    assert bootstrap["state_json_backup_exists"] is True
    assert bootstrap["state_load_source"] == "state.json.bak"
    assert result.repaired is True
    assert result.source_used == "state.json.bak"
    assert result.validation_valid is True
    assert _stored_state(tmp_path)["position"]["current_phase"] == "07"
    assert "**Current Phase:** 07" in (planning / "STATE.md").read_text(encoding="utf-8")


def test_sync_state_repair_prefers_valid_backup_over_malformed_markdown_when_json_is_missing(
    tmp_path: Path,
) -> None:
    backup_state = _state_with_phase("11", status="Paused")
    save_state_json(tmp_path, backup_state)
    _ensure_phase_dir(tmp_path, "11")
    planning = tmp_path / "GPD"
    (planning / "state.json").unlink()
    (planning / "STATE.md").write_text("not a canonical state document\n", encoding="utf-8")

    bootstrap = init_sync_state(tmp_path, stage="sync_bootstrap")
    result = state_repair_sync(tmp_path)

    assert bootstrap["state_json_exists"] is False
    assert bootstrap["state_md_exists"] is True
    assert bootstrap["state_json_backup_exists"] is True
    assert bootstrap["state_load_source"] == "state.json.bak"
    assert result.repaired is True
    assert result.source_used == "state.json.bak"
    assert result.validation_valid is True
    stored = _stored_state(tmp_path)
    assert stored["position"]["current_phase"] == "11"
    assert stored["position"]["status"] == "Paused"
    repaired_markdown = (planning / "STATE.md").read_text(encoding="utf-8")
    assert repaired_markdown.startswith("# Research State")
    assert "not a canonical state document" not in repaired_markdown


def test_sync_state_repair_fails_closed_on_backup_without_primary_state_surface(tmp_path: Path) -> None:
    backup_state = _state_with_phase("13", status="Paused")
    backup_state["project_contract"] = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    _write_lone_backup(tmp_path, backup_state)

    bootstrap = init_sync_state(tmp_path, stage="sync_bootstrap")
    new_project = init_new_project(tmp_path, stage="scope_intake")
    result = state_repair_sync(tmp_path)

    assert bootstrap["state_json_exists"] is False
    assert bootstrap["state_md_exists"] is False
    assert bootstrap["state_json_backup_exists"] is True
    assert bootstrap["state_load_source"] is None
    assert "will not promote the backup automatically" in bootstrap["state_recovery_guidance"]
    assert any(
        "state.json.bak exists without primary state.json or STATE.md" in issue
        for issue in bootstrap["state_integrity_issues"]
    )

    assert new_project["state_exists"] is False
    assert new_project["recoverable_project_exists"] is False
    assert new_project["project_contract"] is None
    assert new_project["project_contract_load_info"]["status"] == "missing"
    assert new_project["project_contract_gate"]["visible"] is False
    assert new_project["project_contract_gate"]["authoritative"] is False

    assert result.repaired is False
    assert result.reason == "missing_or_unrecoverable_state"
    assert any(
        "state.json.bak exists without primary state.json or STATE.md" in issue for issue in result.integrity_issues
    )
    assert not (tmp_path / "GPD" / "state.json").exists()
    assert not (tmp_path / "GPD" / "STATE.md").exists()


def test_sync_state_repair_fails_closed_on_malformed_markdown_without_json_or_backup(tmp_path: Path) -> None:
    planning = tmp_path / "GPD"
    planning.mkdir()
    (planning / "STATE.md").write_text("not a canonical state document\n", encoding="utf-8")

    result = state_repair_sync(tmp_path)

    assert result.repaired is False
    assert result.source_used == "STATE.md"
    assert result.reason == "state_md_malformed"
    assert not (planning / "state.json").exists()


def test_state_repair_sync_cli_repairs_root_selected_by_cwd_option(tmp_path: Path) -> None:
    backup_state = _state_with_phase("05")
    save_state_json(tmp_path, backup_state)
    _ensure_phase_dir(tmp_path, "05")
    planning = tmp_path / "GPD"
    (planning / "STATE.md").unlink()
    (planning / "state.json").write_text("{bad json\n", encoding="utf-8")

    result = runner.invoke(
        app,
        ["--raw", "--cwd", str(tmp_path), "state", "repair-sync"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["project_root"] == tmp_path.resolve().as_posix()
    assert payload["source_used"] == "state.json.bak"
    assert payload["validation_valid"] is True
    assert _stored_state(tmp_path)["position"]["current_phase"] == "05"
