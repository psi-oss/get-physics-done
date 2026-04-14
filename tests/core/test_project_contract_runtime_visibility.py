"""Regression tests for runtime visibility of draft project contracts."""

from __future__ import annotations

import json
from pathlib import Path

from gpd.core.context import _build_reference_runtime_context, init_peer_review, init_progress, init_write_paper
from gpd.core.contract_validation import (
    CONTEXT_INTAKE_DEFAULT_WARNING,
    UNCERTAINTY_MARKERS_DEFAULT_WARNING,
    validate_project_contract,
)
from gpd.core.state import default_state_dict, save_state_json, state_set_project_contract

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
        "crucial_inputs": ["Need the user-selected benchmark anchor."],
    }
    prior_output = tmp_path / "GPD" / "phases" / "01-setup" / "01-01-SUMMARY.md"
    prior_output.parent.mkdir(parents=True, exist_ok=True)
    prior_output.write_text("summary\n", encoding="utf-8")
    save_state_json(tmp_path, default_state_dict())
    result = state_set_project_contract(tmp_path, contract)
    assert result.updated is True
    assert any(
        warning.startswith("approval blocker: references must include at least one must_surface=true anchor")
        for warning in result.warnings
    )
    return contract


def _write_raw_project_contract_state(tmp_path: Path, contract: dict[str, object]) -> None:
    save_state_json(tmp_path, default_state_dict())
    state_path = tmp_path / "GPD" / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["project_contract"] = contract
    state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def _write_publication_authoring_files(tmp_path: Path) -> None:
    planning = tmp_path / "GPD"
    (planning / "PROJECT.md").write_text("# Test Project\n\nPaper target.\n", encoding="utf-8")
    (planning / "STATE.md").write_text("# State\n\nReady.\n", encoding="utf-8")
    (planning / "ROADMAP.md").write_text("# Roadmap\n\n## Milestone v1.0\n", encoding="utf-8")
    (planning / "REQUIREMENTS.md").write_text("# Requirements\n\n- Verified evidence\n", encoding="utf-8")


def _write_structured_state_memory(tmp_path: Path) -> None:
    state_path = tmp_path / "GPD" / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state.setdefault("convention_lock", {}).update(
        {
            "metric_signature": "mostly-plus",
            "coordinate_system": "Cartesian",
        }
    )
    state["intermediate_results"] = [
        {
            "id": "R-01",
            "equation": "E = mc^2",
            "description": "Mass-energy relation",
            "phase": "1",
            "depends_on": [],
            "verified": True,
            "verification_records": [],
        }
    ]
    state["approximations"] = [
        {
            "name": "weak coupling",
            "validity_range": "g << 1",
            "controlling_param": "g",
            "current_value": "0.1",
            "status": "valid",
        }
    ]
    state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def _write_reference_artifacts(tmp_path: Path) -> None:
    literature_dir = tmp_path / "GPD" / "literature"
    literature_dir.mkdir(parents=True, exist_ok=True)
    (literature_dir / "benchmark-REVIEW.md").write_text(
        """# Literature Review: Benchmark Survey

## Active Anchor Registry

| Anchor | Type | Why It Matters | Required Action | Downstream Use |
| ------ | ---- | -------------- | --------------- | -------------- |
| Benchmark Ref 2024 | benchmark | Published benchmark curve for the primary quantity | read/compare/cite | planning/execution |
""",
        encoding="utf-8",
    )
    (literature_dir / "benchmark-CITATION-SOURCES.json").write_text(
        json.dumps(
            [
                {
                    "reference_id": "ref-benchmark",
                    "source_type": "paper",
                    "title": "Benchmark Ref 2024",
                    "authors": ["A. Author", "B. Benchmarker"],
                    "year": "2024",
                    "bibtex_key": "benchmark2024",
                }
            ]
        ),
        encoding="utf-8",
    )

    map_dir = tmp_path / "GPD" / "research-map"
    map_dir.mkdir(parents=True, exist_ok=True)
    (map_dir / "REFERENCES.md").write_text(
        """# Reference and Anchor Map

## Prior Artifacts and Baselines

- `GPD/phases/01-test-phase/01-SUMMARY.md`: Prior baseline summary that later phases must keep visible

## Benchmarks and Comparison Targets

- Universal crossing window
  - Source: Author et al., Journal, 2024
""",
        encoding="utf-8",
    )


def _assert_visible_non_authoritative_contract(payload: dict[str, object]) -> None:
    assert payload["project_contract"] is not None
    assert payload["project_contract"]["references"][0]["must_surface"] is False
    assert payload["project_contract_load_info"]["status"] == "loaded_with_approval_blockers"
    assert payload["project_contract_validation"]["valid"] is False
    assert payload["project_contract_validation"]["mode"] == "approved"
    assert payload["project_contract_gate"]["visible"] is True
    assert payload["project_contract_gate"]["blocked"] is True
    assert payload["project_contract_gate"]["load_blocked"] is False
    assert payload["project_contract_gate"]["approval_blocked"] is True
    assert payload["project_contract_gate"]["authoritative"] is False
    assert payload["project_contract_gate"]["repair_required"] is True


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
    assert ctx["project_contract_gate"]["load_blocked"] is False
    assert ctx["project_contract_gate"]["approval_blocked"] is True
    assert ctx["project_contract_gate"]["authoritative"] is False
    assert ctx["project_contract_gate"]["repair_required"] is True
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


def test_runtime_context_keeps_defaulted_legacy_contract_visible_when_context_intake_is_empty(
    tmp_path: Path,
) -> None:
    _setup_project(tmp_path)
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract.pop("context_intake", None)
    contract.pop("uncertainty_markers", None)
    _write_raw_project_contract_state(tmp_path, contract)

    ctx = init_progress(tmp_path)

    assert ctx["project_contract"] is not None
    assert ctx["project_contract"]["references"][0]["id"] == "ref-benchmark"
    assert ctx["contract_intake"] == {
        "must_read_refs": [],
        "must_include_prior_outputs": [],
        "user_asserted_anchors": [],
        "known_good_baselines": [],
        "context_gaps": [],
        "crucial_inputs": [],
    }
    assert ctx["project_contract_load_info"]["status"] == "blocked_integrity"
    assert any(CONTEXT_INTAKE_DEFAULT_WARNING in warning for warning in ctx["project_contract_load_info"]["warnings"])
    assert any(
        UNCERTAINTY_MARKERS_DEFAULT_WARNING in warning for warning in ctx["project_contract_load_info"]["warnings"]
    )
    assert ctx["project_contract_validation"]["valid"] is False
    assert "context_intake must not be empty" in ctx["project_contract_validation"]["errors"]
    assert (
        "uncertainty_markers.weakest_anchors must identify what is least certain"
        in ctx["project_contract_validation"]["errors"]
    )
    assert (
        "uncertainty_markers.disconfirming_observations must identify what would force a rethink"
        in ctx["project_contract_validation"]["errors"]
    )
    assert ctx["project_contract_gate"]["visible"] is True
    assert ctx["project_contract_gate"]["blocked"] is True
    assert ctx["project_contract_gate"]["load_blocked"] is True
    assert ctx["project_contract_gate"]["approval_blocked"] is True
    assert ctx["project_contract_gate"]["authoritative"] is False
    assert ctx["project_contract_gate"]["repair_required"] is True
    assert ctx["active_reference_count"] == 1
    assert ctx["active_references"][0]["id"] == "ref-benchmark"


def test_write_paper_stage_keeps_visible_non_authoritative_contract_on_full_reference_runtime(
    tmp_path: Path,
) -> None:
    _setup_project(tmp_path)
    _write_publication_authoring_files(tmp_path)
    _write_draft_project_contract_state(tmp_path)
    _write_structured_state_memory(tmp_path)
    _write_reference_artifacts(tmp_path)

    expected = _build_reference_runtime_context(tmp_path)
    ctx = init_write_paper(tmp_path, stage="outline_and_scaffold")

    _assert_visible_non_authoritative_contract(ctx)
    assert ctx["project_contract"] == expected["project_contract"]
    assert ctx["project_contract_load_info"] == expected["project_contract_load_info"]
    assert ctx["project_contract_validation"] == expected["project_contract_validation"]
    assert ctx["project_contract_gate"] == expected["project_contract_gate"]
    assert ctx["selected_protocol_bundle_ids"] == expected["selected_protocol_bundle_ids"]
    assert ctx["protocol_bundle_context"] == expected["protocol_bundle_context"]
    assert ctx["active_reference_context"] == expected["active_reference_context"]
    assert ctx["reference_artifact_files"] == expected["reference_artifact_files"]
    assert "GPD/literature/benchmark-REVIEW.md" in ctx["reference_artifact_files"]
    assert "No stable knowledge, literature-review, or research-map anchor artifacts found yet." not in ctx[
        "active_reference_context"
    ]


def test_peer_review_preflight_keeps_visible_non_authoritative_contract_on_full_reference_runtime(
    tmp_path: Path,
) -> None:
    _setup_project(tmp_path)
    _write_publication_authoring_files(tmp_path)
    _write_draft_project_contract_state(tmp_path)
    _write_reference_artifacts(tmp_path)

    expected = _build_reference_runtime_context(tmp_path)
    ctx = init_peer_review(tmp_path, stage="preflight")

    _assert_visible_non_authoritative_contract(ctx)
    assert ctx["project_contract"] == expected["project_contract"]
    assert ctx["project_contract_load_info"] == expected["project_contract_load_info"]
    assert ctx["project_contract_validation"] == expected["project_contract_validation"]
    assert ctx["project_contract_gate"] == expected["project_contract_gate"]
    assert ctx["contract_intake"] == expected["contract_intake"]
    assert ctx["effective_reference_intake"] == expected["effective_reference_intake"]
    assert ctx["selected_protocol_bundle_ids"] == expected["selected_protocol_bundle_ids"]
    assert ctx["protocol_bundle_context"] == expected["protocol_bundle_context"]
    assert ctx["active_reference_context"] == expected["active_reference_context"]
    assert ctx["reference_artifact_files"] == expected["reference_artifact_files"]
    assert "GPD/literature/benchmark-REVIEW.md" in ctx["reference_artifact_files"]
    assert "Need a concrete must-surface anchor before approval." in ctx["active_reference_context"]
    assert "No stable knowledge, literature-review, or research-map anchor artifacts found yet." not in ctx[
        "active_reference_context"
    ]
