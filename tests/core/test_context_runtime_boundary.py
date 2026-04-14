"""Regression tests for context/runtime abstraction boundaries."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

from gpd.adapters.runtime_catalog import iter_runtime_descriptors
from gpd.core.workflow_staging import load_workflow_stage_manifest


def test_context_import_does_not_require_adapter_instantiation(
    tmp_path: Path,
    monkeypatch,
) -> None:
    import gpd.adapters as adapters

    def _boom():
        raise AssertionError("iter_adapters should not be needed for gpd.core.context import")

    monkeypatch.setattr(adapters, "iter_adapters", _boom)
    sys.modules.pop("gpd.core.context", None)

    context = importlib.import_module("gpd.core.context")
    payload = context.init_new_project(tmp_path)

    expected_runtime_dirs = {descriptor.config_dir_name for descriptor in iter_runtime_descriptors()}
    assert expected_runtime_dirs <= context._runtime_config_dirs()
    assert expected_runtime_dirs <= context._ignore_dirs()
    assert payload["has_research_files"] is False


def test_write_paper_outline_stage_does_not_require_bootstrap_overlay_when_full_reference_runtime_is_needed(
    tmp_path: Path,
    monkeypatch,
) -> None:
    context = importlib.import_module("gpd.core.context")
    stage = load_workflow_stage_manifest("write-paper").get_stage("outline_and_scaffold")

    monkeypatch.setattr(
        context,
        "load_context_config_dict",
        lambda cwd: {"commit_docs": False, "autonomy": "ask", "research_mode": "normal"},
    )
    monkeypatch.setattr(context, "_state_exists", lambda cwd: True)
    monkeypatch.setattr(context, "_path_exists", lambda cwd, path: True)
    monkeypatch.setattr(context, "_detect_platform", lambda cwd: "test")

    monkeypatch.setattr(
        context,
        "_build_reference_runtime_context",
        lambda cwd: {
            "project_contract": {"scope": {"question": "blocked question"}},
            "project_contract_gate": {
                "status": "loaded_with_approval_blockers",
                "visible": True,
                "blocked": True,
                "load_blocked": False,
                "approval_blocked": True,
                "authoritative": False,
                "repair_required": True,
                "raw_project_contract_classified": True,
                "provenance": "raw",
                "source_path": str(cwd / "GPD" / "state.json"),
            },
            "project_contract_load_info": {
                "status": "loaded_with_approval_blockers",
                "source_path": str(cwd / "GPD" / "state.json"),
                "provenance": "raw",
                "raw_project_contract_classified": True,
                "errors": [],
                "warnings": ["approval blocker: references must include at least one must_surface=true anchor"],
            },
            "project_contract_validation": {
                "valid": False,
                "mode": "approved",
                "errors": ["references must include at least one must_surface=true anchor"],
                "warnings": [],
            },
            "selected_protocol_bundle_ids": ["bundle-a"],
            "protocol_bundle_context": "full bundle context",
            "active_reference_context": "full reference context",
            "derived_manuscript_reference_status": {"ref-benchmark": {"verification_status": "verified"}},
            "derived_manuscript_reference_status_count": 1,
            "derived_manuscript_proof_review_status": {"state": "fresh"},
            "reference_artifact_files": ["GPD/literature/benchmark-REVIEW.md"],
            "reference_artifacts_content": "review content",
            "literature_review_files": ["GPD/literature/benchmark-REVIEW.md"],
            "literature_review_count": 1,
            "research_map_reference_files": ["GPD/research-map/REFERENCES.md"],
            "research_map_reference_count": 1,
        },
    )

    def _bootstrap_should_not_run(cwd: Path, **kwargs) -> dict[str, object]:
        raise AssertionError("outline_and_scaffold should not overlay publication bootstrap onto full reference runtime")

    monkeypatch.setattr(context, "_build_publication_bootstrap_runtime_context", _bootstrap_should_not_run)
    monkeypatch.setattr(
        context,
        "_build_state_memory_runtime_context",
        lambda cwd: {
            "derived_convention_lock": {"metric_signature": "mostly-plus"},
            "derived_convention_lock_count": 1,
            "derived_intermediate_results": [{"id": "R-01"}],
            "derived_intermediate_result_count": 1,
            "derived_approximations": [{"name": "weak coupling"}],
            "derived_approximation_count": 1,
        },
    )
    monkeypatch.setattr(
        context,
        "_build_publication_file_context",
        lambda cwd, **kwargs: {
            "roadmap_content": "# Roadmap",
            "requirements_content": "# Requirements",
            "state_content": "# State",
        },
    )

    payload = context.init_write_paper(tmp_path, stage="outline_and_scaffold")

    assert set(payload) == set(stage.required_init_fields) | {"staged_loading"}
    assert payload["project_contract_gate"]["authoritative"] is False
    assert payload["active_reference_context"] == "full reference context"
    assert payload["reference_artifact_files"] == ["GPD/literature/benchmark-REVIEW.md"]
    assert payload["staged_loading"]["stage_id"] == "outline_and_scaffold"
