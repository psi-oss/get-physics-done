"""Focused regressions for state/context project-contract loading parity."""

from __future__ import annotations

import json
from pathlib import Path

from gpd.core.constants import STATE_JSON_BACKUP_FILENAME, ProjectLayout
from gpd.core.context import init_progress
from gpd.core.state import default_state_dict, load_state_json, save_state_json, state_load

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "stage0"


def _setup_project(tmp_path: Path) -> None:
    planning = tmp_path / ".gpd"
    planning.mkdir(parents=True, exist_ok=True)
    (planning / "phases").mkdir(exist_ok=True)
    (planning / "PROJECT.md").write_text("# Test Project\n", encoding="utf-8")
    (planning / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")


def test_load_state_json_uses_backup_when_primary_root_is_not_an_object(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    save_state_json(tmp_path, default_state_dict())

    layout = ProjectLayout(tmp_path)
    recovered = default_state_dict()
    recovered["position"]["current_phase"] = "09"
    recovered["position"]["status"] = "Planning"

    layout.state_json.write_text("[]\n", encoding="utf-8")
    (layout.gpd / STATE_JSON_BACKUP_FILENAME).write_text(json.dumps(recovered, indent=2) + "\n", encoding="utf-8")

    loaded = load_state_json(tmp_path)

    assert loaded is not None
    assert loaded["position"]["current_phase"] == "09"
    assert json.loads(layout.state_json.read_text(encoding="utf-8"))["position"]["current_phase"] == "09"


def test_state_and_context_restore_backup_project_contract_when_primary_needs_blocking_normalization(
    tmp_path: Path,
) -> None:
    _setup_project(tmp_path)
    save_state_json(tmp_path, default_state_dict())

    layout = ProjectLayout(tmp_path)
    primary_state = json.loads(layout.state_json.read_text(encoding="utf-8"))
    primary_contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    primary_contract["context_intake"] = "not-a-dict"
    primary_state["project_contract"] = primary_contract
    layout.state_json.write_text(json.dumps(primary_state, indent=2) + "\n", encoding="utf-8")

    backup_state = default_state_dict()
    backup_contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    backup_contract["scope"]["question"] = "Recovered from backup contract"
    backup_state["project_contract"] = backup_contract
    layout.state_json_backup.write_text(json.dumps(backup_state, indent=2) + "\n", encoding="utf-8")

    loaded = state_load(tmp_path)
    ctx = init_progress(tmp_path)

    assert loaded.state["project_contract"] is not None
    assert loaded.state["project_contract"]["scope"]["question"] == "Recovered from backup contract"
    assert ctx["project_contract"] is not None
    assert ctx["project_contract"]["scope"]["question"] == "Recovered from backup contract"
    assert loaded.state["project_contract"] == ctx["project_contract"]
    assert ctx["project_contract_load_info"]["source_path"].endswith(STATE_JSON_BACKUP_FILENAME)


def test_state_and_context_restore_backup_project_contract_when_primary_contract_is_not_an_object(
    tmp_path: Path,
) -> None:
    _setup_project(tmp_path)
    save_state_json(tmp_path, default_state_dict())

    layout = ProjectLayout(tmp_path)
    primary_state = json.loads(layout.state_json.read_text(encoding="utf-8"))
    primary_state["project_contract"] = "not-a-dict"
    layout.state_json.write_text(json.dumps(primary_state, indent=2) + "\n", encoding="utf-8")

    backup_state = default_state_dict()
    backup_contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    backup_contract["scope"]["question"] = "Recovered from backup contract"
    backup_state["project_contract"] = backup_contract
    layout.state_json_backup.write_text(json.dumps(backup_state, indent=2) + "\n", encoding="utf-8")

    ctx = init_progress(tmp_path)

    assert ctx["project_contract"] is not None
    assert ctx["project_contract"]["scope"]["question"] == "Recovered from backup contract"
    assert ctx["project_contract_load_info"]["source_path"].endswith(STATE_JSON_BACKUP_FILENAME)


def test_state_and_context_drop_integrity_invalid_backup_project_contract(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    save_state_json(tmp_path, default_state_dict())

    layout = ProjectLayout(tmp_path)
    layout.state_json.write_text("[]\n", encoding="utf-8")

    backup_state = default_state_dict()
    backup_contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    backup_contract["claims"].append(dict(backup_contract["claims"][0]))
    backup_state["project_contract"] = backup_contract
    layout.state_json_backup.write_text(json.dumps(backup_state, indent=2) + "\n", encoding="utf-8")

    ctx = init_progress(tmp_path)
    loaded = state_load(tmp_path)

    assert ctx["project_contract"] is None
    assert ctx["project_contract_load_info"]["status"] == "blocked_integrity"
    assert loaded.state["project_contract"] is None
    assert json.loads(layout.state_json.read_text(encoding="utf-8"))["project_contract"] is None


def test_state_and_context_hide_project_contract_when_raw_singleton_section_is_invalid(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    save_state_json(tmp_path, default_state_dict())

    layout = ProjectLayout(tmp_path)
    raw_state = json.loads(layout.state_json.read_text(encoding="utf-8"))
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["context_intake"] = "not-a-dict"
    raw_state["project_contract"] = contract
    layout.state_json.write_text(json.dumps(raw_state, indent=2) + "\n", encoding="utf-8")

    loaded = state_load(tmp_path)
    ctx = init_progress(tmp_path)

    assert loaded.state["project_contract"] is None
    assert ctx["project_contract"] is None
    assert ctx["project_contract_load_info"]["status"] == "blocked_schema"
    assert any("context_intake" in error for error in ctx["project_contract_load_info"]["errors"])
    assert "## Project Contract Intake" in ctx["active_reference_context"]
    assert "None confirmed in `state.json.project_contract.references` yet." in ctx["active_reference_context"]


def test_state_contract_remains_visible_in_runtime_context_with_approval_blockers(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    save_state_json(tmp_path, default_state_dict())

    layout = ProjectLayout(tmp_path)
    raw_state = json.loads(layout.state_json.read_text(encoding="utf-8"))
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["context_intake"] = {
        "must_read_refs": [],
        "must_include_prior_outputs": [],
        "user_asserted_anchors": [],
        "known_good_baselines": [],
        "context_gaps": [],
        "crucial_inputs": [],
    }
    contract["references"][0]["role"] = "background"
    contract["references"][0]["must_surface"] = False
    raw_state["project_contract"] = contract
    layout.state_json.write_text(json.dumps(raw_state, indent=2) + "\n", encoding="utf-8")

    loaded = state_load(tmp_path)
    ctx = init_progress(tmp_path)

    assert loaded.state["project_contract"] is not None
    assert loaded.state["project_contract"]["references"][0]["role"] == "background"
    assert ctx["project_contract"] is not None
    assert ctx["project_contract"]["references"][0]["role"] == "background"
    assert ctx["project_contract_load_info"]["status"] == "loaded_with_approval_blockers"
    assert ctx["project_contract_validation"]["valid"] is False
    assert "Approval status: blocked" in ctx["active_reference_context"]
