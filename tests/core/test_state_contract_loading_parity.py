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


def _draft_invalid_project_contract() -> dict[str, object]:
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["claims"][0]["references"] = ["missing-ref"]
    return contract


def _write_stage0_project_contract_state(tmp_path: Path) -> None:
    state = default_state_dict()
    state["project_contract"] = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    (tmp_path / "GPD" / "state.json").write_text(json.dumps(state), encoding="utf-8")


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
    (layout.phases_dir / "09").mkdir(parents=True, exist_ok=True)

    ctx = init_progress(tmp_path)
    loaded = state_load(tmp_path)

    assert loaded.state["position"]["current_phase"] == "09"
    assert loaded.state["position"]["status"] == "Executing"
    assert loaded.integrity_status == "warning"
    assert (
        "state.json position was recovered from state.json.bak after primary position required normalization"
        in loaded.integrity_issues
    )
    assert loaded.state.get("project_contract") is None
    assert loaded.project_contract_gate is not None
    assert loaded.project_contract_gate["visible"] is False
    assert loaded.project_contract_gate["status"] == "missing"
    assert ctx["project_contract"] is None
    assert ctx["project_contract_load_info"]["status"] == "missing"
    assert ctx["project_contract_load_info"]["source_path"].endswith("GPD/state.json")
    persisted = json.loads(layout.state_json.read_text(encoding="utf-8"))
    assert persisted["position"]["current_phase"] == "09"
    assert persisted["position"]["status"] == "Executing"


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
    assert loaded.project_contract_gate is not None
    assert loaded.project_contract_gate["status"] == "blocked_schema"
    assert loaded.project_contract_gate["visible"] is False
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
    assert loaded.project_contract_gate is not None
    assert loaded.project_contract_gate["status"] == "blocked_type"
    assert loaded.project_contract_gate["visible"] is False
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
    assert ctx["project_contract_load_info"]["status"] == "loaded"
    assert ctx["project_contract_gate"]["authoritative"] is True
    assert any(
        "the primary state.json was missing" in record.message
        or "the primary state.json was unavailable or unreadable" in record.message
        for record in caplog.records
    )


def test_state_and_context_keep_fallback_project_contract_visible_but_non_authoritative(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_project(tmp_path)

    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["context_intake"]["must_read_refs"] = ["ref-benchmark"]

    from gpd.core.state import ensure_state_schema

    normalized_state = ensure_state_schema({"project_contract": contract})
    monkeypatch.setattr(
        "gpd.core.state.peek_state_json",
        lambda cwd, **kwargs: (normalized_state, [], "state.json"),
    )
    monkeypatch.setattr("gpd.core.state._load_raw_project_contract_payload", lambda cwd: None)

    loaded = state_load(tmp_path)
    ctx = init_progress(tmp_path)

    assert loaded.project_contract_load_info["provenance"] == "fallback"
    assert loaded.project_contract_gate["raw_project_contract_classified"] is False
    assert loaded.project_contract_gate["authoritative"] is False
    assert loaded.project_contract_gate["repair_required"] is True
    assert ctx["project_contract"] is not None
    assert ctx["project_contract_load_info"]["provenance"] == "fallback"
    assert ctx["project_contract_gate"]["raw_project_contract_classified"] is False
    assert ctx["project_contract_gate"]["authoritative"] is False
    assert ctx["project_contract_gate"]["repair_required"] is True


def test_project_contract_loader_does_not_warn_about_backup_use_without_a_loaded_backup(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _setup_project(tmp_path)
    layout = ProjectLayout(tmp_path)
    layout.state_json.unlink(missing_ok=True)
    layout.state_json_backup.unlink(missing_ok=True)

    with caplog.at_level(logging.WARNING):
        contract, load_info = _load_project_contract(tmp_path)

    assert contract is None
    assert load_info["status"] == "missing"
    assert not any("Using project_contract from" in record.message for record in caplog.records)


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
    assert load_info["status"] == "loaded"
    assert load_info["source_path"].endswith("state.json")
    assert not layout.state_intent.exists()
    assert json.loads(layout.state_json.read_text(encoding="utf-8"))["project_contract"]["scope"]["question"] == "Recovered from intent-backed write"


def test_state_and_context_surface_visible_blocked_integrity_backup_project_contract(tmp_path: Path) -> None:
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

    assert ctx["project_contract"] is not None
    assert ctx["project_contract"]["claims"][1]["id"] == "claim-benchmark"
    assert ctx["project_contract_load_info"]["status"] == "blocked_integrity"
    assert loaded.project_contract_gate is not None
    assert ctx["project_contract_gate"] is not None
    assert {
        key: value for key, value in loaded.project_contract_gate.items() if key != "source_path"
    } == {
        key: value for key, value in ctx["project_contract_gate"].items() if key != "source_path"
    }
    assert loaded.project_contract_gate["source_path"] == "GPD/state.json.bak"
    assert ctx["project_contract_gate"]["source_path"] == "GPD/state.json.bak"
    assert loaded.state["project_contract"] is not None
    assert loaded.state["project_contract"]["claims"][1]["id"] == "claim-benchmark"
    assert json.loads(layout.state_json.read_text(encoding="utf-8"))["project_contract"]["claims"][1][
        "id"
    ] == "claim-benchmark"


def test_state_and_context_surface_draft_invalid_primary_project_contract_after_state_load(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    save_state_json(tmp_path, default_state_dict())

    layout = ProjectLayout(tmp_path)
    raw_state = json.loads(layout.state_json.read_text(encoding="utf-8"))
    raw_state["project_contract"] = _draft_invalid_project_contract()
    layout.state_json.write_text(json.dumps(raw_state, indent=2) + "\n", encoding="utf-8")

    loaded = state_load(tmp_path)
    ctx = init_progress(tmp_path)

    assert loaded.state["project_contract"] is not None
    assert loaded.state["project_contract"]["claims"][0]["references"] == ["missing-ref"]
    assert any("unknown reference missing-ref" in issue for issue in loaded.integrity_issues)
    assert ctx["project_contract"] is not None
    assert ctx["project_contract"]["claims"][0]["references"] == ["missing-ref"]
    assert ctx["project_contract_load_info"]["status"] == "blocked_integrity"
    assert loaded.project_contract_gate == ctx["project_contract_gate"]
    assert any(
        "unknown reference missing-ref" in error
        for error in ctx["project_contract_load_info"]["errors"]
    )


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
    assert loaded.project_contract_gate is not None
    assert loaded.project_contract_gate["status"] == "blocked_schema"
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
        "context_gaps": ["Need a concrete must-surface anchor before approval."],
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
    assert loaded.project_contract_gate == ctx["project_contract_gate"]
    assert loaded.project_contract_gate["status"] == "loaded_with_approval_blockers"
    assert loaded.project_contract_gate["load_blocked"] is False
    assert loaded.project_contract_gate["approval_blocked"] is True
    assert loaded.project_contract_gate["authoritative"] is False
    assert "Approval status: blocked" in ctx["active_reference_context"]


def test_state_and_context_keep_salvaged_project_contract_visible_but_non_authoritative(
    tmp_path: Path,
) -> None:
    _setup_project(tmp_path)
    save_state_json(tmp_path, default_state_dict())

    layout = ProjectLayout(tmp_path)
    raw_state = json.loads(layout.state_json.read_text(encoding="utf-8"))
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["context_intake"]["must_read_refs"] = "ref-benchmark"
    raw_state["project_contract"] = contract
    layout.state_json.write_text(json.dumps(raw_state, indent=2) + "\n", encoding="utf-8")

    loaded = state_load(tmp_path)
    ctx = init_progress(tmp_path)

    assert loaded.state["project_contract"] is not None
    assert loaded.state["project_contract"]["context_intake"]["must_read_refs"] == ["ref-benchmark"]
    assert ctx["project_contract"] is not None
    assert ctx["project_contract"]["context_intake"]["must_read_refs"] == ["ref-benchmark"]
    assert ctx["project_contract_load_info"]["status"] == "loaded_with_schema_normalization"
    assert loaded.project_contract_gate["status"] == "loaded_with_schema_normalization"
    assert loaded.project_contract_gate["visible"] is True
    assert loaded.project_contract_gate["load_blocked"] is False
    assert loaded.project_contract_gate["approval_blocked"] is False
    assert loaded.project_contract_gate["repair_required"] is True
    assert loaded.project_contract_gate["authoritative"] is False
    assert ctx["project_contract_gate"] == loaded.project_contract_gate


def test_state_and_context_canonicalize_reference_aliases_before_final_contract_gate(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    _write_stage0_project_contract_state(tmp_path)

    state_path = tmp_path / "GPD" / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["project_contract"]["references"][0]["aliases"] = ["benchmark-paper"]
    state["project_contract"]["context_intake"]["must_read_refs"] = ["benchmark-paper"]
    state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

    loaded = state_load(tmp_path)
    ctx = init_progress(tmp_path)

    assert loaded.project_contract_load_info == ctx["project_contract_load_info"]
    assert loaded.project_contract_validation == ctx["project_contract_validation"]
    assert loaded.project_contract_gate == ctx["project_contract_gate"]
    assert loaded.project_contract_load_info["status"] == "loaded"
    assert loaded.project_contract_validation["valid"] is True
    assert loaded.project_contract_gate["status"] == "loaded"
    assert loaded.project_contract_gate["authoritative"] is True
    assert ctx["project_contract"]["context_intake"]["must_read_refs"] == ["ref-benchmark"]


def test_state_and_context_surface_duplicate_and_blank_project_contract_list_members(
    tmp_path: Path,
) -> None:
    _setup_project(tmp_path)
    save_state_json(tmp_path, default_state_dict())

    layout = ProjectLayout(tmp_path)
    raw_state = json.loads(layout.state_json.read_text(encoding="utf-8"))
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["context_intake"]["must_read_refs"] = ["ref-benchmark", "ref-benchmark", " "]
    contract["references"][0]["required_actions"] = ["read", "read", " "]
    raw_state["project_contract"] = contract
    layout.state_json.write_text(json.dumps(raw_state, indent=2) + "\n", encoding="utf-8")

    loaded = state_load(tmp_path)
    ctx = init_progress(tmp_path)

    assert loaded.state["project_contract"] is not None
    assert loaded.state["project_contract"]["context_intake"]["must_read_refs"] == ["ref-benchmark"]
    assert loaded.state["project_contract"]["references"][0]["required_actions"] == ["read"]
    assert ctx["project_contract"] is not None
    assert ctx["project_contract"]["context_intake"]["must_read_refs"] == ["ref-benchmark"]
    assert ctx["project_contract"]["references"][0]["required_actions"] == ["read"]
    assert ctx["project_contract_load_info"]["status"] == "loaded_with_schema_normalization"
    assert loaded.project_contract_gate["status"] == "loaded_with_schema_normalization"
    assert loaded.project_contract_gate["visible"] is True
    assert loaded.project_contract_gate["repair_required"] is True
    assert any("must_read_refs.1 is a duplicate" in warning for warning in ctx["project_contract_load_info"]["warnings"])
    assert any("must_read_refs.2 must not be blank" in warning for warning in ctx["project_contract_load_info"]["warnings"])
    assert any("required_actions.1 is a duplicate" in warning for warning in ctx["project_contract_load_info"]["warnings"])
    assert any("required_actions.2 must not be blank" in warning for warning in ctx["project_contract_load_info"]["warnings"])
