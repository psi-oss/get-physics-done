"""Focused regressions for state/context project-contract loading parity."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from gpd.core.constants import STATE_JSON_BACKUP_FILENAME, ProjectLayout
from gpd.core.context import _load_project_contract, init_progress
from gpd.core.state import default_state_dict, generate_state_markdown, load_state_json, save_state_json, state_load

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "stage0"


def _setup_project(tmp_path: Path) -> None:
    planning = tmp_path / "GPD"
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


def test_state_and_context_keep_primary_state_when_primary_root_is_dict_but_schema_corrupt(
    tmp_path: Path,
) -> None:
    _setup_project(tmp_path)
    save_state_json(tmp_path, default_state_dict())

    layout = ProjectLayout(tmp_path)
    primary_state = json.loads(layout.state_json.read_text(encoding="utf-8"))
    primary_state["position"] = []
    layout.state_json.write_text(json.dumps(primary_state, indent=2) + "\n", encoding="utf-8")

    backup_state = default_state_dict()
    backup_state["position"]["current_phase"] = "09"
    backup_state["position"]["status"] = "Executing"
    backup_contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    backup_contract["scope"]["question"] = "Recovered from schema-corrupt backup state"
    backup_state["project_contract"] = backup_contract
    layout.state_json_backup.write_text(json.dumps(backup_state, indent=2) + "\n", encoding="utf-8")

    ctx = init_progress(tmp_path)
    loaded = state_load(tmp_path)

    assert loaded.state["position"]["current_phase"] is None
    assert loaded.state["position"]["status"] is None
    assert loaded.integrity_status == "warning"
    assert any("position" in issue for issue in loaded.integrity_issues)
    assert loaded.state.get("project_contract") is None
    assert ctx["project_contract"] is None
    assert ctx["project_contract_load_info"]["status"] == "missing"
    assert ctx["project_contract_load_info"]["source_path"].endswith("GPD/state.json")


def test_state_and_context_surface_blocked_primary_project_contract_when_primary_needs_blocking_normalization(
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

    ctx = init_progress(tmp_path)
    loaded = state_load(tmp_path)

    assert loaded.state["project_contract"] is None
    assert ctx["project_contract"] is None
    assert ctx["project_contract_load_info"]["status"] == "blocked_schema"
    assert ctx["project_contract_load_info"]["source_path"].endswith("GPD/state.json")
    assert any("context_intake" in error for error in ctx["project_contract_load_info"]["errors"])
    assert json.loads(layout.state_json.read_text(encoding="utf-8"))["project_contract"]["context_intake"] == "not-a-dict"


def test_state_and_context_surface_blocked_primary_project_contract_when_primary_contract_is_not_an_object(
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
    loaded = state_load(tmp_path)

    assert loaded.state["project_contract"] is None
    assert ctx["project_contract"] is None
    assert ctx["project_contract_load_info"]["status"] == "blocked_type"
    assert ctx["project_contract_load_info"]["source_path"].endswith("GPD/state.json")
    assert ctx["project_contract_load_info"]["errors"] == ["project contract must be a JSON object"]


@pytest.mark.parametrize(
    "primary_state_contents",
    [
        None,
        "{",
    ],
)
def test_state_and_context_restore_backup_project_contract_when_primary_state_is_missing_or_unreadable(
    tmp_path: Path,
    primary_state_contents: str | None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _setup_project(tmp_path)

    layout = ProjectLayout(tmp_path)
    backup_state = default_state_dict()
    backup_contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    backup_contract["scope"]["question"] = "Recovered from backup-only state"
    backup_state["project_contract"] = backup_contract
    layout.state_json_backup.write_text(json.dumps(backup_state, indent=2) + "\n", encoding="utf-8")
    if primary_state_contents is not None:
        layout.state_json.write_text(primary_state_contents, encoding="utf-8")

    with caplog.at_level(logging.WARNING, logger="gpd.core.context"):
        ctx = init_progress(tmp_path)

    assert ctx["project_contract"] is not None
    assert ctx["project_contract"]["scope"]["question"] == "Recovered from backup-only state"
    assert ctx["project_contract_load_info"]["source_path"].endswith(STATE_JSON_BACKUP_FILENAME)
    assert ctx["project_contract_load_info"]["status"].startswith("loaded")
    assert any(
        "the primary state.json was unavailable or unreadable" in record.message
        for record in caplog.records
    )


def test_project_contract_loader_recovers_intent_backed_state_and_persists_it(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    save_state_json(tmp_path, default_state_dict())

    layout = ProjectLayout(tmp_path)
    stale_state = json.loads(layout.state_json.read_text(encoding="utf-8"))
    stale_contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    stale_contract["scope"]["question"] = "Stale contract"
    stale_state["project_contract"] = stale_contract
    layout.state_json.write_text(json.dumps(stale_state, indent=2) + "\n", encoding="utf-8")

    recovered_state = json.loads(layout.state_json.read_text(encoding="utf-8"))
    recovered_contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    recovered_contract["scope"]["question"] = "Recovered from intent-backed write"
    recovered_state["project_contract"] = recovered_contract
    json_tmp = layout.gpd / ".state-json-tmp"
    md_tmp = layout.gpd / ".state-md-tmp"
    json_tmp.write_text(json.dumps(recovered_state, indent=2) + "\n", encoding="utf-8")
    md_tmp.write_text(generate_state_markdown(recovered_state), encoding="utf-8")
    layout.state_intent.write_text(f"{json_tmp}\n{md_tmp}\n", encoding="utf-8")

    contract, load_info = _load_project_contract(tmp_path)

    assert contract is not None
    assert contract.model_dump(mode="json")["scope"]["question"] == "Recovered from intent-backed write"
    assert load_info["status"].startswith("loaded")
    assert load_info["source_path"].endswith("state.json")
    assert not layout.state_intent.exists()
    assert json.loads(layout.state_json.read_text(encoding="utf-8"))["project_contract"]["scope"]["question"] == "Recovered from intent-backed write"


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

    ctx = init_progress(tmp_path)
    loaded = state_load(tmp_path)

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
