"""Regression tests for shared workflow-stage manifest loading."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gpd.core.workflow_staging import (
    EXECUTE_PHASE_STAGE_MANIFEST_PATH,
    NEW_PROJECT_STAGE_MANIFEST_PATH,
    invalidate_workflow_stage_manifest_cache,
    known_init_fields_for_workflow,
    load_workflow_stage_manifest,
    load_workflow_stage_manifest_from_path,
    resolve_workflow_stage_manifest_path,
    validate_workflow_stage_manifest_payload,
)


def _workflow_payload(workflow_id: str) -> dict[str, object]:
    manifest_path = resolve_workflow_stage_manifest_path(workflow_id)
    return json.loads(manifest_path.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("workflow_id", "expected_path"),
    [
        ("new-project", NEW_PROJECT_STAGE_MANIFEST_PATH),
        ("plan-phase", NEW_PROJECT_STAGE_MANIFEST_PATH.parent / "plan-phase-stage-manifest.json"),
        ("verify-work", NEW_PROJECT_STAGE_MANIFEST_PATH.parent / "verify-work-stage-manifest.json"),
        ("write-paper", NEW_PROJECT_STAGE_MANIFEST_PATH.parent / "write-paper-stage-manifest.json"),
        ("peer-review", NEW_PROJECT_STAGE_MANIFEST_PATH.parent / "peer-review-stage-manifest.json"),
        ("execute-phase", EXECUTE_PHASE_STAGE_MANIFEST_PATH),
    ],
)
def test_resolve_workflow_stage_manifest_path_matches_canonical_manifest(
    workflow_id: str,
    expected_path: Path,
) -> None:
    assert resolve_workflow_stage_manifest_path(workflow_id) == expected_path


def test_load_workflow_stage_manifest_is_cached() -> None:
    first = load_workflow_stage_manifest("new-project")
    second = load_workflow_stage_manifest("new-project")

    assert first is second
    assert first.stage_ids() == ("scope_intake", "scope_approval", "post_scope")
    assert "references/shared/canonical-schema-discipline.md" in first.stages[0].must_not_eager_load

    execute_phase_manifest = load_workflow_stage_manifest("execute-phase")
    assert execute_phase_manifest.stage_ids() == (
        "phase_bootstrap",
        "phase_classification",
        "wave_planning",
        "pre_execution_specialists",
        "wave_dispatch",
        "checkpoint_resume",
        "aggregate_and_verify",
        "closeout",
    )
    assert execute_phase_manifest.stage("checkpoint_resume").next_stages == ("aggregate_and_verify",)
    assert execute_phase_manifest.stage("aggregate_and_verify").next_stages == ("closeout",)
    assert execute_phase_manifest.stage("closeout").next_stages == ()
    assert execute_phase_manifest.stage("pre_execution_specialists").loaded_authorities == (
        "workflows/execute-phase.md",
        "references/orchestration/agent-delegation.md",
        "references/orchestration/runtime-delegation-note.md",
    )
    assert execute_phase_manifest.stage("pre_execution_specialists").next_stages == ("wave_dispatch",)
    assert "templates/summary.md" in execute_phase_manifest.stage("aggregate_and_verify").loaded_authorities
    assert "templates/contract-results-schema.md" in execute_phase_manifest.stage(
        "aggregate_and_verify"
    ).loaded_authorities
    assert "templates/calculation-log.md" in execute_phase_manifest.stage("aggregate_and_verify").loaded_authorities


def test_validate_workflow_stage_manifest_payload_loads_verify_work_manifest() -> None:
    manifest = validate_workflow_stage_manifest_payload(
        _workflow_payload("verify-work"),
        expected_workflow_id="verify-work",
    )

    assert manifest.workflow_id == "verify-work"
    assert manifest.stage_ids() == (
        "session_router",
        "phase_bootstrap",
        "inventory_build",
        "interactive_validation",
        "gap_repair",
    )
    assert manifest.stages[0].loaded_authorities == ("workflows/verify-work.md",)
    assert "references/verification/core/verification-core.md" in manifest.stages[0].must_not_eager_load
    assert "templates/verification-report.md" in manifest.stages[0].must_not_eager_load
    assert manifest.stages[2].loaded_authorities == (
        "workflows/verify-work.md",
        "references/verification/meta/verification-independence.md",
    )
    assert manifest.stages[3].allowed_tools == (
        "ask_user",
        "file_read",
        "file_edit",
        "file_write",
        "find_files",
        "search_files",
        "shell",
        "task",
    )
    assert manifest.stages[3].writes_allowed == ("GPD/phases/XX-name/XX-VERIFICATION.md",)
    assert manifest.stages[3].checkpoints == (
        "verification file can be written",
        "writer-stage schema is visible",
        "check results remain contract-backed",
    )
    assert manifest.stages[3].loaded_authorities == (
        "workflows/verify-work.md",
        "templates/research-verification.md",
        "templates/verification-report.md",
        "templates/contract-results-schema.md",
        "references/shared/canonical-schema-discipline.md",
    )
    assert manifest.stages[4].allowed_tools == (
        "ask_user",
        "file_read",
        "file_edit",
        "file_write",
        "find_files",
        "search_files",
        "shell",
        "task",
    )
    assert manifest.stages[4].writes_allowed == ("GPD/phases/XX-name/XX-VERIFICATION.md",)
    assert manifest.stages[4].checkpoints == (
        "gaps are diagnosed",
        "repair plans are verified",
        "verification closeout is ready",
    )
    assert manifest.stages[4].loaded_authorities == (
        "workflows/verify-work.md",
        "templates/research-verification.md",
        "templates/verification-report.md",
        "templates/contract-results-schema.md",
        "references/shared/canonical-schema-discipline.md",
        "references/protocols/error-propagation-protocol.md",
    )
    assert manifest.stages[4].next_stages == ()


def test_validate_workflow_stage_manifest_payload_loads_plan_phase_manifest() -> None:
    manifest = validate_workflow_stage_manifest_payload(
        _workflow_payload("plan-phase"),
        expected_workflow_id="plan-phase",
    )

    assert manifest.workflow_id == "plan-phase"
    assert manifest.stage_ids() == (
        "phase_bootstrap",
        "research_routing",
        "planner_authoring",
        "checker_revision",
    )
    assert manifest.stages[0].loaded_authorities == ("workflows/plan-phase.md",)
    assert "templates/plan-contract-schema.md" in manifest.stages[0].must_not_eager_load
    assert "templates/planner-subagent-prompt.md" in manifest.stages[0].must_not_eager_load
    assert manifest.stages[2].loaded_authorities == (
        "workflows/plan-phase.md",
        "templates/planner-subagent-prompt.md",
    )
    assert manifest.stages[3].loaded_authorities == (
        "workflows/plan-phase.md",
        "templates/planner-subagent-prompt.md",
    )
    assert "reference_artifacts_content" in manifest.stages[2].required_init_fields
    assert "reference_artifacts_content" in manifest.stages[3].required_init_fields
    assert "experiment_design_content" in manifest.stages[2].required_init_fields
    assert "experiment_design_content" in manifest.stages[3].required_init_fields
    assert "state_content" not in manifest.stages[3].required_init_fields
    assert "GPD/phases" in manifest.stages[2].writes_allowed


def test_validate_workflow_stage_manifest_payload_loads_write_paper_manifest() -> None:
    manifest = validate_workflow_stage_manifest_payload(
        _workflow_payload("write-paper"),
        expected_workflow_id="write-paper",
    )

    assert manifest.workflow_id == "write-paper"
    assert manifest.stage_ids() == (
        "paper_bootstrap",
        "outline_and_scaffold",
        "figure_and_section_authoring",
        "consistency_and_references",
        "publication_review",
    )
    assert manifest.stages[0].loaded_authorities == ("workflows/write-paper.md",)
    assert "references/publication/publication-pipeline-modes.md" in manifest.stages[0].must_not_eager_load
    assert "references/publication/peer-review-panel.md" in manifest.stages[0].must_not_eager_load
    assert "templates/paper/paper-config-schema.md" in manifest.stages[0].must_not_eager_load
    assert manifest.stages[1].loaded_authorities == (
        "workflows/write-paper.md",
        "references/publication/publication-pipeline-modes.md",
        "templates/paper/paper-config-schema.md",
        "templates/paper/artifact-manifest-schema.md",
    )
    assert manifest.stages[2].loaded_authorities == (
        "workflows/write-paper.md",
        "references/shared/canonical-schema-discipline.md",
        "templates/paper/figure-tracker.md",
    )
    assert manifest.stages[4].loaded_authorities == (
        "workflows/write-paper.md",
        "references/publication/peer-review-panel.md",
        "references/publication/peer-review-reliability.md",
        "templates/paper/review-ledger-schema.md",
        "templates/paper/referee-decision-schema.md",
    )


def test_validate_workflow_stage_manifest_payload_loads_peer_review_manifest() -> None:
    manifest = validate_workflow_stage_manifest_payload(
        _workflow_payload("peer-review"),
        expected_workflow_id="peer-review",
    )

    assert manifest.workflow_id == "peer-review"
    assert manifest.stage_ids() == (
        "bootstrap",
        "preflight",
        "artifact_discovery",
        "panel_stages",
        "final_adjudication",
        "finalize",
    )
    assert manifest.stages[0].loaded_authorities == ("workflows/peer-review.md",)
    assert "references/publication/peer-review-panel.md" in manifest.stages[0].must_not_eager_load
    assert "references/publication/peer-review-reliability.md" in manifest.stages[0].must_not_eager_load
    assert "templates/paper/paper-config-schema.md" in manifest.stages[0].must_not_eager_load
    assert manifest.stages[1].loaded_authorities == (
        "workflows/peer-review.md",
        "references/publication/peer-review-reliability.md",
        "templates/paper/paper-config-schema.md",
        "templates/paper/artifact-manifest-schema.md",
        "templates/paper/bibliography-audit-schema.md",
        "templates/paper/reproducibility-manifest.md",
    )
    assert manifest.stages[3].loaded_authorities == (
        "workflows/peer-review.md",
        "references/publication/peer-review-panel.md",
    )
    assert manifest.stages[4].loaded_authorities == (
        "workflows/peer-review.md",
        "references/publication/peer-review-panel.md",
        "templates/paper/review-ledger-schema.md",
        "templates/paper/referee-decision-schema.md",
    )


def test_known_init_fields_for_execute_phase_include_bootstrap_and_wave_context() -> None:
    known_init_fields = known_init_fields_for_workflow("execute-phase")

    assert known_init_fields is not None
    assert "executor_model" in known_init_fields
    assert "verifier_model" in known_init_fields
    assert "phase_found" in known_init_fields
    assert "plan_count" in known_init_fields
    assert "selected_protocol_bundle_ids" in known_init_fields
    assert "reference_artifacts_content" in known_init_fields
    assert "current_execution" in known_init_fields


def test_validate_workflow_stage_manifest_payload_loads_execute_phase_manifest_shape() -> None:
    manifest = validate_workflow_stage_manifest_payload(
        {
            "schema_version": 1,
            "workflow_id": "execute-phase",
            "stages": [
                {
                    "id": "phase_bootstrap",
                    "order": 1,
                    "purpose": "Load only the bootstrap execution snapshot and route the phase.",
                    "mode_paths": ["workflows/execute-phase.md"],
                    "required_init_fields": [
                        "executor_model",
                        "verifier_model",
                        "commit_docs",
                        "autonomy",
                        "review_cadence",
                        "research_mode",
                        "parallelization",
                        "max_unattended_minutes_per_plan",
                        "max_unattended_minutes_per_wave",
                        "checkpoint_after_n_tasks",
                        "checkpoint_after_first_load_bearing_result",
                        "checkpoint_before_downstream_dependent_tasks",
                        "verifier_enabled",
                        "branching_strategy",
                        "branch_name",
                        "phase_found",
                        "phase_dir",
                        "phase_number",
                        "phase_name",
                        "phase_slug",
                        "plans",
                        "summaries",
                        "incomplete_plans",
                        "plan_count",
                        "incomplete_count",
                        "state_exists",
                        "roadmap_exists",
                        "project_contract",
                        "project_contract_gate",
                        "project_contract_validation",
                        "project_contract_load_info",
                        "state_load_source",
                        "state_integrity_issues",
                        "convention_lock",
                        "convention_lock_count",
                    ],
                    "loaded_authorities": ["workflows/execute-phase.md"],
                    "conditional_authorities": [],
                    "must_not_eager_load": [
                        "references/ui/ui-brand.md",
                        "references/orchestration/artifact-surfacing.md",
                        "templates/contract-results-schema.md",
                        "templates/summary.md",
                    ],
                    "allowed_tools": ["file_read", "shell", "task"],
                    "writes_allowed": [],
                    "produced_state": [],
                    "next_stages": ["wave_planning"],
                    "checkpoints": [],
                },
                {
                    "id": "wave_planning",
                    "order": 2,
                    "purpose": "Load the wave-planning payload only when the orchestrator needs to shape waves.",
                    "mode_paths": ["workflows/execute-phase.md"],
                    "required_init_fields": [
                        "selected_protocol_bundle_ids",
                        "protocol_bundle_context",
                        "active_reference_context",
                        "reference_artifacts_content",
                        "intermediate_results",
                        "intermediate_result_count",
                        "approximations",
                        "approximation_count",
                        "propagated_uncertainties",
                        "propagated_uncertainty_count",
                        "derived_convention_lock",
                        "derived_convention_lock_count",
                        "derived_intermediate_results",
                        "derived_intermediate_result_count",
                        "derived_approximations",
                        "derived_approximation_count",
                    ],
                    "loaded_authorities": [
                        "workflows/execute-phase.md",
                        "references/orchestration/meta-orchestration.md",
                    ],
                    "conditional_authorities": [],
                    "must_not_eager_load": [
                        "references/ui/ui-brand.md",
                        "templates/contract-results-schema.md",
                        "templates/summary.md",
                    ],
                    "allowed_tools": ["file_read", "shell", "task"],
                    "writes_allowed": [],
                    "produced_state": [],
                    "next_stages": ["wave_dispatch"],
                    "checkpoints": [],
                },
                {
                    "id": "wave_dispatch",
                    "order": 3,
                    "purpose": "Load only the late execution context required to spawn and review waves.",
                    "mode_paths": ["workflows/execute-phase.md"],
                    "required_init_fields": [
                        "selected_protocol_bundle_ids",
                        "protocol_bundle_context",
                        "active_reference_context",
                        "reference_artifacts_content",
                    ],
                    "loaded_authorities": [
                        "workflows/execute-phase.md",
                        "references/orchestration/artifact-surfacing.md",
                    ],
                    "conditional_authorities": [],
                    "must_not_eager_load": [
                        "references/ui/ui-brand.md",
                        "templates/summary.md",
                        "templates/contract-results-schema.md",
                    ],
                    "allowed_tools": ["file_read", "shell", "task"],
                    "writes_allowed": [],
                    "produced_state": [],
                    "next_stages": [],
                    "checkpoints": [],
                },
            ],
        },
        expected_workflow_id="execute-phase",
    )

    assert manifest.stage_ids() == ("phase_bootstrap", "wave_planning", "wave_dispatch")
    assert manifest.stages[0].loaded_authorities == ("workflows/execute-phase.md",)
    assert "references/ui/ui-brand.md" in manifest.stages[0].must_not_eager_load
    assert "templates/contract-results-schema.md" in manifest.stages[0].must_not_eager_load
    assert "references/orchestration/meta-orchestration.md" in manifest.stages[1].loaded_authorities
    assert "selected_protocol_bundle_ids" in manifest.stages[1].required_init_fields
    assert "reference_artifacts_content" in manifest.stages[2].required_init_fields
    assert "references/orchestration/artifact-surfacing.md" in manifest.stages[2].loaded_authorities
    assert manifest.staged_loading_payload("phase_bootstrap")["next_stages"] == ["wave_planning"]
    assert manifest.staged_loading_payload("wave_dispatch")["checkpoints"] == []

@pytest.mark.parametrize(
    ("mutator", "message"),
    [
        (lambda payload: payload["stages"][0].__setitem__("loaded_authorities", ["/absolute/path.md"]), "normalized relative POSIX"),
        (
            lambda payload: payload["stages"][0].__setitem__(
                "must_not_eager_load", ["references/research/does-not-exist.md"]
            ),
            "existing markdown file",
        ),
        (lambda payload: payload["stages"][0].__setitem__("allowed_tools", ["file_read", "not-a-tool"]), "unknown tool"),
        (
            lambda payload: payload["stages"][0].__setitem__("required_init_fields", ["researcher_model", "not-a-field"]),
            "unknown field",
        ),
        (
            lambda payload: payload["stages"][0].__setitem__(
                "must_not_eager_load",
                [*payload["stages"][0]["must_not_eager_load"], "workflows/new-project.md"],
            ),
            "overlap with must_not_eager_load",
        ),
        (lambda payload: payload["stages"][1].__setitem__("writes_allowed", ["../escape.txt"]), "normalized relative POSIX path"),
    ],
)
def test_validate_workflow_stage_manifest_payload_rejects_bad_entries(
    mutator,
    message: str,
) -> None:
    payload = _workflow_payload("new-project")
    mutator(payload)

    with pytest.raises(ValueError, match=message):
        validate_workflow_stage_manifest_payload(payload)


@pytest.mark.parametrize("workflow_id", ["new-project"])
def test_load_workflow_stage_manifest_from_path_respects_cache_invalidation(
    workflow_id: str,
    tmp_path: Path,
) -> None:
    payload = _workflow_payload(workflow_id)
    manifest_path = tmp_path / f"{workflow_id}-stage-manifest.json"
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    first = load_workflow_stage_manifest_from_path(manifest_path, expected_workflow_id=workflow_id)
    payload["stages"][0]["purpose"] = "updated purpose"
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    second = load_workflow_stage_manifest_from_path(manifest_path, expected_workflow_id=workflow_id)
    assert second is first
    assert second.stages[0].purpose != "updated purpose"

    invalidate_workflow_stage_manifest_cache()
    third = load_workflow_stage_manifest_from_path(manifest_path, expected_workflow_id=workflow_id)

    assert third is not first
    assert third.stages[0].purpose == "updated purpose"
