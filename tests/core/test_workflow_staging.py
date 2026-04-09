"""Regression tests for shared workflow-stage manifest loading."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gpd.core.context import init_write_paper
from gpd.core.workflow_staging import (
    EXECUTE_PHASE_STAGE_MANIFEST_PATH,
    LITERATURE_REVIEW_STAGE_MANIFEST_PATH,
    MAP_RESEARCH_STAGE_MANIFEST_PATH,
    NEW_PROJECT_STAGE_MANIFEST_PATH,
    PLAN_PHASE_STAGE_MANIFEST_PATH,
    QUICK_STAGE_MANIFEST_PATH,
    RESEARCH_PHASE_STAGE_MANIFEST_PATH,
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
        ("plan-phase", PLAN_PHASE_STAGE_MANIFEST_PATH),
        ("quick", QUICK_STAGE_MANIFEST_PATH),
        ("literature-review", LITERATURE_REVIEW_STAGE_MANIFEST_PATH),
        ("research-phase", RESEARCH_PHASE_STAGE_MANIFEST_PATH),
        ("map-research", MAP_RESEARCH_STAGE_MANIFEST_PATH),
        ("verify-work", NEW_PROJECT_STAGE_MANIFEST_PATH.parent / "verify-work-stage-manifest.json"),
        ("write-paper", NEW_PROJECT_STAGE_MANIFEST_PATH.parent / "write-paper-stage-manifest.json"),
        ("peer-review", NEW_PROJECT_STAGE_MANIFEST_PATH.parent / "peer-review-stage-manifest.json"),
        ("arxiv-submission", NEW_PROJECT_STAGE_MANIFEST_PATH.parent / "arxiv-submission-stage-manifest.json"),
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
    assert first.stages[0].required_init_fields == (
        "researcher_model",
        "synthesizer_model",
        "commit_docs",
        "autonomy",
        "research_mode",
        "project_exists",
        "has_research_map",
        "planning_exists",
        "has_research_files",
        "has_project_manifest",
        "needs_research_map",
        "has_git",
        "platform",
        "project_contract",
        "project_contract_gate",
        "project_contract_load_info",
        "project_contract_validation",
    )
    assert first.stages[0].produced_state == ("intake routing state", "scoping-contract gate state")
    assert first.stages[0].checkpoints == (
        "detect existing workspace state",
        "surface the first scoping question",
        "preserve contract gate visibility without assuming approval-stage authority",
    )
    assert first.stages[1].produced_state == ("approved project contract", "approval-state persistence")
    assert first.stages[1].checkpoints == (
        "approval gate has passed",
        "project contract is ready for persistence",
    )
    assert first.stages[2].produced_state == (
        "project artifacts",
        "workflow preferences",
        "downstream stage handoff",
    )
    assert first.stages[2].checkpoints == (
        "approval gate has passed",
        "stage-aware deferred reads are now allowed",
    )
    assert first.stages[2].loaded_authorities == (
        "references/ui/ui-brand.md",
        "templates/project.md",
        "templates/requirements.md",
    )
    assert first.stages[2].must_not_eager_load == ()
    assert first.stages[2].writes_allowed == (
        "GPD/PROJECT.md",
        "GPD/REQUIREMENTS.md",
        "GPD/ROADMAP.md",
        "GPD/STATE.md",
        "GPD/state.json",
        "GPD/config.json",
        "GPD/CONVENTIONS.md",
        "GPD/literature/PRIOR-WORK.md",
        "GPD/literature/METHODS.md",
        "GPD/literature/COMPUTATIONAL.md",
        "GPD/literature/PITFALLS.md",
        "GPD/literature/SUMMARY.md",
    )
    assert first.stages[2].next_stages == ()

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
    assert "phase_proof_review_status" in manifest.stages[0].required_init_fields
    assert "project_contract_gate" in manifest.stages[0].required_init_fields
    assert "project_contract_load_info" in manifest.stages[0].required_init_fields
    assert "project_contract_validation" in manifest.stages[0].required_init_fields
    assert "references/verification/core/verification-core.md" in manifest.stages[1].must_not_eager_load
    assert "phase_proof_review_status" in manifest.stages[1].required_init_fields
    assert manifest.stages[2].loaded_authorities == (
        "workflows/verify-work.md",
        "references/verification/meta/verification-independence.md",
    )
    assert "protocol_bundle_verifier_extensions" in manifest.stages[2].required_init_fields
    assert "active_reference_context" in manifest.stages[2].required_init_fields
    assert "reference_artifacts_content" not in manifest.stages[2].required_init_fields
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
    assert "reference_artifact_files" in manifest.stages[3].required_init_fields
    assert "reference_artifacts_content" not in manifest.stages[3].required_init_fields
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
    assert "reference_artifact_files" in manifest.stages[4].required_init_fields
    assert "reference_artifacts_content" in manifest.stages[4].required_init_fields
    assert manifest.stages[4].loaded_authorities == (
        "workflows/verify-work.md",
        "templates/research-verification.md",
        "templates/verification-report.md",
        "templates/contract-results-schema.md",
        "references/shared/canonical-schema-discipline.md",
        "references/protocols/error-propagation-protocol.md",
    )


def test_known_init_fields_for_verify_work_include_proof_gate_and_artifact_context() -> None:
    known_init_fields = known_init_fields_for_workflow("verify-work")

    assert known_init_fields is not None
    assert "phase_proof_review_status" in known_init_fields
    assert "project_contract_gate" in known_init_fields
    assert "project_contract_load_info" in known_init_fields
    assert "project_contract_validation" in known_init_fields
    assert "selected_protocol_bundle_ids" in known_init_fields
    assert "protocol_bundle_verifier_extensions" in known_init_fields
    assert "derived_manuscript_proof_review_status" in known_init_fields
    assert "reference_artifact_files" in known_init_fields
    assert "reference_artifacts_content" in known_init_fields


def test_write_paper_staged_init_fields_match_manifest_required_fields(tmp_path: Path) -> None:
    manifest = validate_workflow_stage_manifest_payload(
        _workflow_payload("write-paper"),
        expected_workflow_id="write-paper",
    )

    gpd_dir = tmp_path / "GPD"
    gpd_dir.mkdir()
    (gpd_dir / "config.json").write_text("{}", encoding="utf-8")
    (gpd_dir / "state.json").write_text("{}", encoding="utf-8")

    for stage_id in manifest.stage_ids():
        payload = init_write_paper(tmp_path, stage=stage_id)
        stage = manifest.stage(stage_id)

        assert "staged_loading" in payload
        assert tuple(field for field in payload if field != "staged_loading") == stage.required_init_fields
        assert set(payload) == set(stage.required_init_fields) | {"staged_loading"}
        assert payload["staged_loading"]["workflow_id"] == "write-paper"
        assert payload["staged_loading"]["stage_id"] == stage_id


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


def test_validate_workflow_stage_manifest_payload_loads_quick_manifest() -> None:
    manifest = validate_workflow_stage_manifest_payload(
        _workflow_payload("quick"),
        expected_workflow_id="quick",
    )

    assert manifest.workflow_id == "quick"
    assert manifest.stage_ids() == ("task_bootstrap", "task_authoring")
    assert manifest.stages[0].loaded_authorities == ("workflows/quick.md",)
    assert "references/ui/ui-brand.md" in manifest.stages[0].must_not_eager_load
    assert "project_contract_gate" in manifest.stages[0].required_init_fields
    assert "project_contract_validation" in manifest.stages[0].required_init_fields
    assert "contract_intake" in manifest.stages[1].required_init_fields
    assert "effective_reference_intake" in manifest.stages[1].required_init_fields
    assert "reference_artifacts_content" in manifest.stages[1].required_init_fields
    assert "templates/planner-subagent-prompt.md" in manifest.stages[1].must_not_eager_load
    assert manifest.stages[1].writes_allowed == ("GPD/quick/NNN-slug/PLAN.md",)


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
    assert "workflows/write-paper.md" in manifest.stages[0].loaded_authorities
    assert "references/publication/publication-review-round-artifacts.md" in manifest.stages[0].must_not_eager_load
    assert "references/publication/publication-response-artifacts.md" in manifest.stages[0].must_not_eager_load
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
        "references/publication/publication-review-round-artifacts.md",
        "references/publication/publication-response-artifacts.md",
        "references/publication/peer-review-panel.md",
        "references/publication/peer-review-reliability.md",
        "templates/paper/review-ledger-schema.md",
        "templates/paper/referee-decision-schema.md",
    )


def test_known_init_fields_for_write_paper_cover_bootstrap_and_deferred_publication_context() -> None:
    known_init_fields = known_init_fields_for_workflow("write-paper")

    assert known_init_fields is not None
    assert "commit_docs" in known_init_fields
    assert "project_contract_gate" in known_init_fields
    assert "project_contract_load_info" in known_init_fields
    assert "project_contract_validation" in known_init_fields
    assert "selected_protocol_bundle_ids" in known_init_fields
    assert "protocol_bundle_context" in known_init_fields
    assert "active_reference_context" in known_init_fields
    assert "reference_artifacts_content" in known_init_fields
    assert "state_content" in known_init_fields
    assert "requirements_content" in known_init_fields


def test_known_init_fields_for_quick_cover_task_bootstrap_and_reference_context() -> None:
    known_init_fields = known_init_fields_for_workflow("quick")

    assert known_init_fields is not None
    assert "executor_model" in known_init_fields
    assert "next_num" in known_init_fields
    assert "task_dir" in known_init_fields
    assert "project_contract_gate" in known_init_fields
    assert "contract_intake" in known_init_fields
    assert "reference_artifacts_content" in known_init_fields


@pytest.mark.parametrize(
    ("workflow_id", "expected_fields"),
    [
        (
            "literature-review",
            {
                "topic",
                "slug",
                "commit_docs",
                "project_contract_gate",
                "contract_intake",
                "effective_reference_intake",
                "active_reference_context",
                "reference_artifacts_content",
                "derived_manuscript_proof_review_status",
            },
        ),
        (
            "research-phase",
            {
                "executor_model",
                "phase_found",
                "phase_dir",
                "phase_number",
                "phase_name",
                "phase_slug",
                "padded_phase",
                "commit_docs",
                "autonomy",
                "research_mode",
                "project_contract_gate",
                "project_contract_load_info",
                "project_contract_validation",
                "contract_intake",
                "effective_reference_intake",
                "active_reference_context",
                "reference_artifact_files",
                "reference_artifacts_content",
                "selected_protocol_bundle_ids",
                "protocol_bundle_context",
                "protocol_bundle_verifier_extensions",
                "current_execution",
                "derived_manuscript_proof_review_status",
                "literature_review_files",
                "research_map_reference_files",
                "config_content",
                "state_content",
                "roadmap_content",
            },
        ),
        (
            "new-milestone",
            {
                "researcher_model",
                "synthesizer_model",
                "commit_docs",
                "autonomy",
                "research_mode",
                "research_enabled",
                "current_milestone",
                "current_milestone_name",
                "project_exists",
                "roadmap_exists",
                "state_exists",
                "project_contract",
                "project_contract_gate",
                "project_contract_load_info",
                "project_contract_validation",
                "contract_intake",
                "effective_reference_intake",
                "active_reference_context",
                "reference_artifact_files",
                "reference_artifacts_content",
                "literature_review_files",
                "literature_review_count",
                "research_map_reference_files",
                "research_map_reference_count",
                "derived_convention_lock",
                "derived_convention_lock_count",
                "derived_intermediate_results",
                "derived_intermediate_result_count",
                "derived_approximations",
                "derived_approximation_count",
                "project_content",
                "state_content",
                "milestones_content",
                "platform",
            },
        ),
        (
            "map-research",
            {
                "mapper_model",
                "research_map_dir",
                "existing_maps",
                "project_contract_gate",
                "active_reference_context",
                "reference_artifacts_content",
                "derived_manuscript_proof_review_status",
            },
        ),
    ],
)
def test_known_init_fields_for_new_stage_aware_workflows_cover_required_context(
    workflow_id: str,
    expected_fields: set[str],
) -> None:
    known_init_fields = known_init_fields_for_workflow(workflow_id)

    assert known_init_fields is not None
    for field in expected_fields:
        assert field in known_init_fields
    if workflow_id == "new-milestone":
        assert "planning_exists" not in known_init_fields


def test_validate_workflow_stage_manifest_payload_loads_research_phase_manifest() -> None:
    manifest = validate_workflow_stage_manifest_payload(
        _workflow_payload("research-phase"),
        expected_workflow_id="research-phase",
    )

    assert manifest.workflow_id == "research-phase"
    assert manifest.stage_ids() == ("phase_bootstrap", "research_handoff")
    assert manifest.stage("phase_bootstrap").loaded_authorities == (
        "workflows/research-phase.md",
        "references/orchestration/model-profile-resolution.md",
    )
    assert "references/orchestration/runtime-delegation-note.md" in manifest.stage(
        "phase_bootstrap"
    ).must_not_eager_load
    assert "reference_artifacts_content" not in manifest.stage("phase_bootstrap").required_init_fields
    assert manifest.stage("research_handoff").loaded_authorities == (
        "workflows/research-phase.md",
        "references/orchestration/model-profile-resolution.md",
        "references/orchestration/runtime-delegation-note.md",
    )
    assert manifest.stage("research_handoff").required_init_fields[:4] == (
        "commit_docs",
        "autonomy",
        "review_cadence",
        "research_mode",
    )
    assert "contract_intake" in manifest.stage("research_handoff").required_init_fields
    assert "effective_reference_intake" in manifest.stage("research_handoff").required_init_fields
    assert "reference_artifact_files" in manifest.stage("research_handoff").required_init_fields
    assert "reference_artifacts_content" in manifest.stage("research_handoff").required_init_fields
    assert "selected_protocol_bundle_ids" in manifest.stage("research_handoff").required_init_fields
    assert "protocol_bundle_context" in manifest.stage("research_handoff").required_init_fields
    assert "protocol_bundle_verifier_extensions" in manifest.stage("research_handoff").required_init_fields
    assert "current_execution" in manifest.stage("research_handoff").required_init_fields
    assert "derived_manuscript_proof_review_status" in manifest.stage("research_handoff").required_init_fields
    assert "config_content" in manifest.stage("research_handoff").required_init_fields
    assert "state_content" in manifest.stage("research_handoff").required_init_fields
    assert "roadmap_content" in manifest.stage("research_handoff").required_init_fields
    assert manifest.stage("research_handoff").writes_allowed == ("GPD/phases/XX-name/XX-RESEARCH.md",)
    assert manifest.stage("research_handoff").checkpoints == (
        "reference and contract context are visible to the handoff",
        "runtime delegation note is loaded only for the child handoff",
        "fresh RESEARCH artifact is required before completion",
    )


def test_validate_workflow_stage_manifest_payload_loads_new_milestone_manifest() -> None:
    manifest = validate_workflow_stage_manifest_payload(
        _workflow_payload("new-milestone"),
        expected_workflow_id="new-milestone",
    )

    assert manifest.workflow_id == "new-milestone"
    assert manifest.stage_ids() == ("milestone_bootstrap", "survey_objectives", "roadmap_authoring")
    assert manifest.stage("milestone_bootstrap").loaded_authorities == ("workflows/new-milestone.md",)
    assert "references/research/questioning.md" in manifest.stage("milestone_bootstrap").must_not_eager_load
    assert "templates/project.md" in manifest.stage("milestone_bootstrap").must_not_eager_load
    assert "templates/requirements.md" in manifest.stage("milestone_bootstrap").must_not_eager_load
    assert "roadmapper_model" not in manifest.stage("milestone_bootstrap").required_init_fields
    assert manifest.stage("survey_objectives").loaded_authorities == (
        "workflows/new-milestone.md",
        "references/research/questioning.md",
    )
    assert "roadmapper_model" not in manifest.stage("survey_objectives").required_init_fields
    assert "contract_intake" in manifest.stage("survey_objectives").required_init_fields
    assert "effective_reference_intake" in manifest.stage("survey_objectives").required_init_fields
    assert "reference_artifacts_content" in manifest.stage("survey_objectives").required_init_fields
    assert manifest.stage("survey_objectives").writes_allowed == (
        "GPD/PROJECT.md",
        "GPD/STATE.md",
        "GPD/literature",
    )
    assert manifest.stage("survey_objectives").checkpoints == (
        "prior milestone context reviewed",
        "survey choice and objective scope captured",
    )
    assert manifest.stage("roadmap_authoring").loaded_authorities == (
        "workflows/new-milestone.md",
        "templates/project.md",
        "templates/requirements.md",
    )
    assert "requirements_content" in manifest.stage("roadmap_authoring").required_init_fields
    assert "roadmap_content" in manifest.stage("roadmap_authoring").required_init_fields
    assert manifest.stage("roadmap_authoring").writes_allowed == (
        "GPD/PROJECT.md",
        "GPD/STATE.md",
        "GPD/REQUIREMENTS.md",
        "GPD/ROADMAP.md",
    )
    assert manifest.stage("roadmap_authoring").checkpoints == (
        "objectives finalized",
        "roadmap authored",
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
    assert "workflows/peer-review.md" in manifest.stages[0].loaded_authorities
    assert "references/publication/publication-review-round-artifacts.md" in manifest.stages[0].must_not_eager_load
    assert "references/publication/peer-review-panel.md" in manifest.stages[0].must_not_eager_load
    assert "references/publication/peer-review-reliability.md" in manifest.stages[0].must_not_eager_load
    assert "templates/paper/paper-config-schema.md" in manifest.stages[0].must_not_eager_load
    assert manifest.stages[1].loaded_authorities == (
        "workflows/peer-review.md",
        "templates/paper/publication-manuscript-root-preflight.md",
        "references/publication/peer-review-reliability.md",
        "templates/paper/paper-config-schema.md",
        "templates/paper/artifact-manifest-schema.md",
        "templates/paper/bibliography-audit-schema.md",
        "templates/paper/reproducibility-manifest.md",
    )
    assert manifest.stages[2].loaded_authorities == (
        "workflows/peer-review.md",
        "references/publication/publication-review-round-artifacts.md",
        "references/publication/publication-response-artifacts.md",
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


def test_arxiv_submission_stage_manifest_path_is_reserved_for_staged_loading() -> None:
    manifest_path = resolve_workflow_stage_manifest_path("arxiv-submission")

    assert manifest_path == NEW_PROJECT_STAGE_MANIFEST_PATH.parent / "arxiv-submission-stage-manifest.json"


def test_arxiv_submission_stage_manifest_can_be_loaded_when_present() -> None:
    manifest_path = resolve_workflow_stage_manifest_path("arxiv-submission")

    if not manifest_path.exists():
        pytest.skip("arxiv-submission stage manifest has not landed yet")

    manifest = validate_workflow_stage_manifest_payload(
        json.loads(manifest_path.read_text(encoding="utf-8")),
        expected_workflow_id="arxiv-submission",
    )

    assert manifest.stage_ids() == (
        "bootstrap",
        "manuscript_preflight",
        "review_gate",
        "package",
        "finalize",
    )
    assert "references/publication/publication-bootstrap-preflight.md" in manifest.stage("bootstrap").loaded_authorities
    assert "references/publication/publication-review-round-artifacts.md" in manifest.stage("review_gate").loaded_authorities
    assert "references/publication/peer-review-reliability.md" in manifest.stage("review_gate").loaded_authorities
    assert "references/publication/publication-response-writer-handoff.md" not in manifest.stage("review_gate").loaded_authorities

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
        (
            lambda payload: payload["stages"][0].__setitem__(
                "loaded_authorities",
                [*payload["stages"][0]["loaded_authorities"], "references/shared/canonical-schema-discipline.md"],
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
