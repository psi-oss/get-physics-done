"""Assertions for runtime visibility of draft project contracts."""

from __future__ import annotations

import json
from pathlib import Path

from gpd.core.context import init_progress
from gpd.core.contract_validation import validate_project_contract
from gpd.core.state import default_state_dict, save_state_json, state_load, state_set_project_contract

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "stage0"


def _setup_project(tmp_path: Path) -> None:
    planning = tmp_path / "GPD"
    planning.mkdir(parents=True, exist_ok=True)
    (planning / "phases").mkdir(exist_ok=True)
    (planning / "PROJECT.md").write_text("# Test Project\n", encoding="utf-8")
    (planning / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")


def _write_draft_project_contract_state(tmp_path: Path) -> dict[str, object]:
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["claims"][0]["references"] = []
    contract["acceptance_tests"][0]["evidence_required"] = ["deliv-figure"]
    contract["references"][0]["role"] = "background"
    contract["references"][0]["must_surface"] = False
    contract["references"][0]["applies_to"] = []
    contract["references"][0]["required_actions"] = []
    contract["context_intake"] = {
        "must_read_refs": [],
        "must_include_prior_outputs": [],
        "user_asserted_anchors": [],
        "known_good_baselines": [],
        "context_gaps": ["Need a concrete must-surface anchor before approval."],
        "crucial_inputs": [],
    }
    save_state_json(tmp_path, default_state_dict())
    result = state_set_project_contract(tmp_path, contract)
    assert result.updated is True
    assert any(
        warning.startswith("approval blocker: references must include at least one must_surface=true anchor")
        for warning in result.warnings
    )
    return contract


def _write_repair_required_project_contract_state(tmp_path: Path) -> dict[str, object]:
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["claims"][0]["notes"] = "recoverable but not authoritative until repaired"
    state = default_state_dict()
    state["project_contract"] = contract
    (tmp_path / "GPD" / "state.json").write_text(json.dumps(state), encoding="utf-8")
    return contract


def _assert_state_load_progress_contract_gate_parity(tmp_path: Path, *, expected_status: str) -> tuple[dict, dict]:
    loaded = state_load(tmp_path)
    ctx = init_progress(tmp_path)

    assert loaded.project_contract_load_info is not None
    assert loaded.project_contract_gate is not None
    assert loaded.project_contract_load_info["status"] == expected_status
    assert ctx["project_contract_load_info"]["status"] == expected_status
    for key in (
        "status",
        "visible",
        "blocked",
        "load_blocked",
        "approval_blocked",
        "authoritative",
        "repair_required",
        "raw_project_contract_classified",
        "provenance",
        "source_path",
    ):
        assert ctx["project_contract_gate"].get(key) == loaded.project_contract_gate.get(key)
    for key in ("status", "source_path", "provenance", "raw_project_contract_classified"):
        assert ctx["project_contract_load_info"].get(key) == loaded.project_contract_load_info.get(key)
    return loaded.project_contract_gate, ctx["project_contract_gate"]


def test_runtime_context_surfaces_approval_blocked_project_contract_payload_with_validation_metadata(
    tmp_path: Path,
) -> None:
    _setup_project(tmp_path)
    contract = _write_draft_project_contract_state(tmp_path)

    approval_validation = validate_project_contract(contract, mode="approved")
    assert approval_validation.valid is False
    assert approval_validation.mode == "approved"

    ctx = init_progress(tmp_path)

    assert ctx["project_contract"] is not None
    assert ctx["project_contract"]["references"][0]["must_surface"] is False
    assert ctx["contract_intake"]["context_gaps"] == ["Need a concrete must-surface anchor before approval."]
    assert ctx["project_contract_load_info"]["status"] == "loaded_with_approval_blockers"
    assert ctx["project_contract_validation"]["valid"] is False
    assert ctx["project_contract_validation"]["mode"] == "approved"
    assert ctx["project_contract_gate"]["visible"] is True
    assert ctx["project_contract_gate"]["blocked"] is True
    assert ctx["project_contract_gate"]["approval_blocked"] is True
    assert ctx["project_contract_gate"]["authoritative"] is False
    assert ctx["effective_reference_intake"]["context_gaps"] == ["Need a concrete must-surface anchor before approval."]
    assert ctx["active_reference_count"] == 1
    assert ctx["active_references"][0]["id"] == "ref-benchmark"
    assert "Need a concrete must-surface anchor before approval." in ctx["active_reference_context"]
    assert "ref-benchmark" in ctx["active_reference_context"]
    assert ctx["selected_protocol_bundle_ids"] == []
    assert any(
        "references must include at least one must_surface=true anchor" in error
        for error in ctx["project_contract_validation"]["errors"]
    )


def test_state_load_and_progress_contract_gate_match_for_approval_blocked_contract(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    _write_draft_project_contract_state(tmp_path)

    loaded_gate, progress_gate = _assert_state_load_progress_contract_gate_parity(
        tmp_path,
        expected_status="loaded_with_approval_blockers",
    )

    for gate in (loaded_gate, progress_gate):
        assert gate["visible"] is True
        assert gate["blocked"] is True
        assert gate["approval_blocked"] is True
        assert gate["authoritative"] is False
        assert gate["repair_required"] is True


def test_state_load_and_progress_contract_gate_match_for_repair_required_contract(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    _write_repair_required_project_contract_state(tmp_path)

    loaded_gate, progress_gate = _assert_state_load_progress_contract_gate_parity(
        tmp_path,
        expected_status="loaded_with_schema_normalization",
    )

    for gate in (loaded_gate, progress_gate):
        assert gate["visible"] is True
        assert gate["blocked"] is False
        assert gate["approval_blocked"] is False
        assert gate["authoritative"] is False
        assert gate["repair_required"] is True
