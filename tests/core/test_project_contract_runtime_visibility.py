"""Regression tests for runtime visibility of draft project contracts."""

from __future__ import annotations

import json
from pathlib import Path

from gpd.core.context import init_progress
from gpd.core.contract_validation import validate_project_contract
from gpd.core.state import default_state_dict, save_state_json

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "stage0"


def _setup_project(tmp_path: Path) -> None:
    planning = tmp_path / ".gpd"
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
        "context_gaps": [],
        "crucial_inputs": [],
    }
    state = default_state_dict()
    state["project_contract"] = contract
    save_state_json(tmp_path, state)
    return contract


def test_runtime_context_surfaces_structurally_valid_draft_project_contract_with_validation_metadata(
    tmp_path: Path,
) -> None:
    _setup_project(tmp_path)
    contract = _write_draft_project_contract_state(tmp_path)

    approval_validation = validate_project_contract(contract, mode="approved")
    assert approval_validation.valid is False
    assert approval_validation.mode == "approved"

    ctx = init_progress(tmp_path)

    assert ctx["project_contract"] is not None
    assert ctx["project_contract"]["scope"]["question"] == contract["scope"]["question"]
    assert ctx["project_contract"]["references"][0]["role"] == "background"
    assert ctx["project_contract"]["references"][0]["must_surface"] is False
    assert ctx["project_contract_load_info"]["status"] == "loaded_with_approval_blockers"
    assert ctx["project_contract_validation"]["valid"] is False
    assert ctx["project_contract_validation"]["mode"] == "approved"
    assert any(
        "references must include at least one must_surface=true anchor" in error
        for error in ctx["project_contract_validation"]["errors"]
    )
