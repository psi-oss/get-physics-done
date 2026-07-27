"""Assertions for shared workflow-stage manifest loading."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

import pytest

from gpd.core import context as context_module
from gpd.core.context import (
    init_arxiv_submission,
    init_autonomous,
    init_execute_phase,
    init_literature_review,
    init_map_research,
    init_new_milestone,
    init_new_project,
    init_peer_review,
    init_plan_phase,
    init_quick,
    init_research_phase,
    init_respond_to_referees,
    init_resume,
    init_sync_state,
    init_verify_work,
    init_write_paper,
)
from gpd.core.task_overlays import TASK_OVERLAY_REFERENCE_PATH
from gpd.core.workflow_staging import (
    AUTONOMOUS_INIT_FIELDS,
    AUTONOMOUS_STAGE_MANIFEST_PATH,
    EXECUTE_PHASE_STAGE_MANIFEST_PATH,
    LITERATURE_REVIEW_STAGE_MANIFEST_PATH,
    MAP_RESEARCH_STAGE_MANIFEST_PATH,
    NEW_PROJECT_STAGE_MANIFEST_PATH,
    PLAN_PHASE_STAGE_MANIFEST_PATH,
    QUICK_STAGE_MANIFEST_PATH,
    RESEARCH_PHASE_STAGE_MANIFEST_PATH,
    VERIFY_WORK_INIT_FIELDS,
    WORKFLOW_STAGE_MANIFEST_DIR,
    WORKFLOW_STAGE_MANIFEST_SUFFIX,
    WRITE_PAPER_MANAGED_INTAKE_ROOT,
    WRITE_PAPER_MANAGED_MANUSCRIPT_ROOT,
    allowed_tools_for_workflow,
    expanded_required_init_fields_by_stage,
    expanded_required_init_fields_for_workflow,
    invalidate_workflow_stage_manifest_cache,
    known_init_fields_for_workflow,
    load_workflow_stage_manifest,
    load_workflow_stage_manifest_from_path,
    resolve_workflow_stage_manifest_path,
    validate_workflow_stage_manifest_payload,
)
from tests.workflow_stage_test_support import assert_staged_payload_matches_manifest

REPO_ROOT = Path(__file__).resolve().parents[2]
NEW_PROJECT_ROOT_AUTHORITY = "workflows/new-project.md"
NEW_PROJECT_STAGE_IDS = (
    "scope_intake",
    "scope_approval",
    "minimal_artifacts",
    "workflow_preferences",
    "project_artifacts",
    "literature_survey",
    "requirements_authoring",
    "roadmap_authoring",
    "conventions_handoff",
    "completion",
)
NEW_PROJECT_SPLIT_AUTHORITIES = {
    "minimal_artifacts": "workflows/new-project/minimal-artifacts.md",
    "workflow_preferences": "workflows/new-project/workflow-preferences.md",
    "project_artifacts": "workflows/new-project/project-artifacts.md",
    "literature_survey": "workflows/new-project/literature-survey.md",
    "requirements_authoring": "workflows/new-project/requirements-authoring.md",
    "roadmap_authoring": "workflows/new-project/roadmap-authoring.md",
    "conventions_handoff": "workflows/new-project/conventions-handoff.md",
    "completion": "workflows/new-project/completion.md",
}
PHASE3_MANIFEST_DERIVED_KNOWN_FIELD_WORKFLOWS = (
    "literature-review",
    "new-project",
    "research-phase",
    "resume-work",
    "sync-state",
)


def _workflow_payload(workflow_id: str) -> dict[str, object]:
    manifest_path = resolve_workflow_stage_manifest_path(workflow_id)
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _stage_source_with_defaults(payload: dict[str, object], raw_stage: dict[str, object]) -> dict[str, object]:
    defaults = payload.get("stage_defaults", {})
    merged = dict(defaults) if isinstance(defaults, dict) else {}
    merged.update(raw_stage)
    return merged


def _with_protocol_bundle_load_manifest(fields: list[str]) -> list[str]:
    if "protocol_bundle_context" not in fields or "protocol_bundle_load_manifest" in fields:
        return fields
    expanded = list(fields)
    for anchor in ("protocol_bundle_count", "selected_protocol_bundle_ids"):
        if anchor in expanded:
            expanded.insert(expanded.index(anchor) + 1, "protocol_bundle_load_manifest")
            return expanded
    expanded.insert(expanded.index("protocol_bundle_context"), "protocol_bundle_load_manifest")
    return expanded


def _stable_field_union(field_sequences: Iterable[Iterable[str]]) -> tuple[str, ...]:
    fields: list[str] = []
    seen: set[str] = set()
    for sequence in field_sequences:
        for field_name in sequence:
            if field_name in seen:
                continue
            seen.add(field_name)
            fields.append(field_name)
    return tuple(fields)


def _setup_generic_staged_init_project(cwd: Path) -> None:
    gpd_dir = cwd / "GPD"
    phase_dir = gpd_dir / "phases" / "01-test"
    manuscript_dir = cwd / "paper"
    phase_dir.mkdir(parents=True, exist_ok=True)
    manuscript_dir.mkdir(parents=True, exist_ok=True)
    (gpd_dir / "config.json").write_text("{}", encoding="utf-8")
    (gpd_dir / "state.json").write_text("{}", encoding="utf-8")
    (gpd_dir / "PROJECT.md").write_text("# Project\n", encoding="utf-8")
    (gpd_dir / "ROADMAP.md").write_text("## Milestone\n\n### Phase 1: Test\n", encoding="utf-8")
    (gpd_dir / "STATE.md").write_text("# State\n", encoding="utf-8")
    manuscript = manuscript_dir / "main.tex"
    manuscript.write_text(
        "\\documentclass{article}\\begin{document}Draft manuscript.\\end{document}\n",
        encoding="utf-8",
    )
    (manuscript_dir / "ARTIFACT-MANIFEST.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "title": "Generic Staged Init Test",
                "manuscript": "main.tex",
                "artifacts": [{"path": "main.tex", "kind": "tex", "role": "manuscript"}],
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _staged_init_payload_for_workflow(cwd: Path, workflow_id: str, stage_id: str) -> dict[str, object]:
    if workflow_id == "execute-phase":
        return init_execute_phase(cwd, "1", stage=stage_id)
    if workflow_id == "plan-phase":
        return init_plan_phase(cwd, "1", stage=stage_id)
    if workflow_id == "autonomous":
        return init_autonomous(cwd, stage=stage_id)
    if workflow_id == "new-project":
        return init_new_project(cwd, stage=stage_id)
    if workflow_id == "new-milestone":
        return init_new_milestone(cwd, stage=stage_id)
    if workflow_id == "quick":
        return init_quick(cwd, "Test quick task", stage=stage_id)
    if workflow_id == "map-research":
        return init_map_research(cwd, stage=stage_id)
    if workflow_id == "literature-review":
        return init_literature_review(cwd, topic="Curvature flow bounds", stage=stage_id)
    if workflow_id == "research-phase":
        return init_research_phase(cwd, phase="1", stage=stage_id)
    if workflow_id == "verify-work":
        return init_verify_work(cwd, "1", stage=stage_id)
    if workflow_id == "resume-work":
        return init_resume(cwd, stage=stage_id)
    if workflow_id == "sync-state":
        return init_sync_state(cwd, stage=stage_id)
    if workflow_id == "write-paper":
        return init_write_paper(cwd, stage=stage_id)
    if workflow_id == "peer-review":
        return init_peer_review(cwd, stage=stage_id)
    raise AssertionError(f"Unhandled staged init workflow {workflow_id}")


@pytest.mark.parametrize(
    ("workflow_id", "expected_path"),
    [
        ("new-project", NEW_PROJECT_STAGE_MANIFEST_PATH),
        ("autonomous", AUTONOMOUS_STAGE_MANIFEST_PATH),
        ("plan-phase", PLAN_PHASE_STAGE_MANIFEST_PATH),
        ("quick", QUICK_STAGE_MANIFEST_PATH),
        ("literature-review", LITERATURE_REVIEW_STAGE_MANIFEST_PATH),
        ("research-phase", RESEARCH_PHASE_STAGE_MANIFEST_PATH),
        ("map-research", MAP_RESEARCH_STAGE_MANIFEST_PATH),
        ("verify-work", NEW_PROJECT_STAGE_MANIFEST_PATH.parent / "verify-work-stage-manifest.json"),
        ("write-paper", NEW_PROJECT_STAGE_MANIFEST_PATH.parent / "write-paper-stage-manifest.json"),
        ("peer-review", NEW_PROJECT_STAGE_MANIFEST_PATH.parent / "peer-review-stage-manifest.json"),
        ("respond-to-referees", NEW_PROJECT_STAGE_MANIFEST_PATH.parent / "respond-to-referees-stage-manifest.json"),
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
    assert first.stage_ids() == NEW_PROJECT_STAGE_IDS
    assert "references/shared/canonical-schema-discipline.md" in first.stages[0].must_not_eager_load
    scope_intake_fields = first.stage("scope_intake").required_init_fields
    assert scope_intake_fields[:3] == ("commit_docs", "autonomy", "research_mode")
    assert {
        "project_exists",
        "state_exists",
        "roadmap_exists",
        "recoverable_project_exists",
        "partial_project_exists",
        "project_recovery_status",
        "init_progress_status",
        "has_research_map",
        "needs_research_map",
        "has_git",
        "platform",
        "project_contract_gate",
        "project_contract_load_info",
        "project_contract_validation",
    }.issubset(scope_intake_fields)
    assert scope_intake_fields.index("project_contract") < scope_intake_fields.index("project_contract_gate")
    assert "researcher_model" not in scope_intake_fields
    assert "roadmapper_model" not in scope_intake_fields
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
    assert first.stages[1].next_stages == ("minimal_artifacts", "workflow_preferences")

    for stage in first.stages:
        assert NEW_PROJECT_ROOT_AUTHORITY not in stage.mode_paths
        assert NEW_PROJECT_ROOT_AUTHORITY not in stage.loaded_authorities

    for stage_id, authority_path in NEW_PROJECT_SPLIT_AUTHORITIES.items():
        stage = first.stage(stage_id)
        assert stage.mode_paths == (authority_path,)
        assert stage.loaded_authorities == (authority_path,)

    minimal = first.stage("minimal_artifacts")
    assert "researcher_model" not in minimal.required_init_fields
    assert "synthesizer_model" not in minimal.required_init_fields
    assert "roadmapper_model" not in minimal.required_init_fields
    assert "GPD/literature/SUMMARY.md" not in minimal.writes_allowed
    assert "GPD/CONVENTIONS.md" not in minimal.writes_allowed
    assert minimal.writes_allowed == (
        "GPD/PROJECT.md",
        "GPD/config.json",
        "GPD/REQUIREMENTS.md",
        "GPD/ROADMAP.md",
        "GPD/STATE.md",
        "GPD/state.json",
        "GPD/state.json.bak",
        "GPD/state.json.lock",
    )
    assert minimal.next_stages == ("completion",)
    assert first.stage("workflow_preferences").next_stages == ("project_artifacts",)
    assert first.stage("project_artifacts").next_stages == ("literature_survey",)
    assert first.stage("literature_survey").next_stages == ("requirements_authoring",)
    assert first.stage("requirements_authoring").next_stages == ("roadmap_authoring",)
    assert first.stage("roadmap_authoring").next_stages == ("conventions_handoff",)
    assert first.stage("conventions_handoff").next_stages == ("completion",)
    assert first.stage("completion").next_stages == ()

    execute_phase_manifest = load_workflow_stage_manifest("execute-phase")
    assert execute_phase_manifest.stage_ids() == (
        "phase_bootstrap",
        "phase_classification",
        "wave_planning",
        "pre_execution_specialists",
        "wave_dispatch",
        "executor_dispatch",
        "proof_critic_dispatch",
        "wave_return_checkpoint",
        "wave_failure_menu",
        "checkpoint_resume",
        "aggregate_and_verify",
        "verification_handoff",
        "gap_reverification",
        "consistency_check",
        "closeout",
    )
    assert execute_phase_manifest.stage("wave_dispatch").next_stages == ("executor_dispatch",)
    assert execute_phase_manifest.stage("executor_dispatch").next_stages == ("proof_critic_dispatch",)
    assert execute_phase_manifest.stage("proof_critic_dispatch").next_stages == ("wave_return_checkpoint",)
    assert execute_phase_manifest.stage("wave_return_checkpoint").next_stages == ("wave_failure_menu",)
    assert execute_phase_manifest.stage("wave_failure_menu").next_stages == ("checkpoint_resume",)
    assert execute_phase_manifest.stage("checkpoint_resume").next_stages == ("aggregate_and_verify",)
    assert execute_phase_manifest.stage("aggregate_and_verify").next_stages == ("verification_handoff",)
    assert execute_phase_manifest.stage("verification_handoff").next_stages == ("gap_reverification",)
    assert execute_phase_manifest.stage("gap_reverification").next_stages == ("consistency_check",)
    assert execute_phase_manifest.stage("consistency_check").next_stages == ("closeout",)
    assert execute_phase_manifest.stage("closeout").next_stages == ()
    closeout = execute_phase_manifest.stage("closeout")
    closeout_conditionals = {
        authority for conditional in closeout.conditional_authorities for authority in conditional.authorities
    }
    assert closeout.loaded_authorities == ("workflows/execute-phase/closeout.md",)
    for authority in (
        "workflows/transition.md",
        "templates/state-machine.md",
        "references/orchestration/state-portability.md",
        "references/ui/ui-brand.md",
        "references/orchestration/continuous-execution.md",
    ):
        assert authority in closeout_conditionals
        assert authority in closeout.must_not_eager_load
    assert "active_reference_context" not in closeout.required_init_fields
    assert "reference_artifacts_content" not in closeout.required_init_fields
    assert execute_phase_manifest.stage("pre_execution_specialists").loaded_authorities == (
        "workflows/execute-phase/pre-execution-specialists.md",
        "references/orchestration/agent-delegation.md",
        "references/orchestration/runtime-delegation-note.md",
    )
    assert execute_phase_manifest.stage("pre_execution_specialists").next_stages == ("wave_dispatch",)
    assert "workflows/execute-plan.md" not in execute_phase_manifest.stage("executor_dispatch").loaded_authorities
    assert "workflows/execute-plan.md" in execute_phase_manifest.stage("executor_dispatch").must_not_eager_load
    assert (
        "references/orchestration/checkpoints.md"
        not in execute_phase_manifest.stage("wave_dispatch").loaded_authorities
    )
    assert (
        "references/orchestration/agent-infrastructure.md"
        not in execute_phase_manifest.stage("wave_failure_menu").loaded_authorities
    )
    assert "templates/summary.md" in execute_phase_manifest.stage("aggregate_and_verify").loaded_authorities
    assert (
        "templates/contract-results-schema.md"
        not in execute_phase_manifest.stage("aggregate_and_verify").loaded_authorities
    )
    assert (
        "templates/contract-results-schema.md"
        in execute_phase_manifest.stage("verification_handoff").must_not_eager_load
    )
    assert "templates/calculation-log.md" in execute_phase_manifest.stage("aggregate_and_verify").loaded_authorities
    assert (
        "templates/paper/figure-tracker.md"
        not in execute_phase_manifest.stage("aggregate_and_verify").loaded_authorities
    )
    assert (
        "templates/paper/experimental-comparison.md"
        not in execute_phase_manifest.stage("aggregate_and_verify").loaded_authorities
    )
    assert "workflows/verify-phase.md" not in execute_phase_manifest.stage("verification_handoff").loaded_authorities
    assert "workflows/verify-phase.md" in execute_phase_manifest.stage("verification_handoff").must_not_eager_load
    assert (
        "references/verification/core/verification-core.md"
        not in execute_phase_manifest.stage("verification_handoff").loaded_authorities
    )
    assert (
        "references/verification/core/verification-core.md"
        in execute_phase_manifest.stage("verification_handoff").must_not_eager_load
    )
    assert (
        "verification_report_skeleton_bridge"
        not in execute_phase_manifest.stage("aggregate_and_verify").required_init_fields
    )
    assert (
        "verification_report_finalizer_bridge"
        not in execute_phase_manifest.stage("aggregate_and_verify").required_init_fields
    )
    assert (
        "verification_report_skeleton_bridge"
        in execute_phase_manifest.stage("verification_handoff").required_init_fields
    )
    assert (
        "verification_report_finalizer_bridge"
        in execute_phase_manifest.stage("verification_handoff").required_init_fields
    )
    assert (
        "verification_report_skeleton_bridge"
        not in execute_phase_manifest.stage("phase_bootstrap").required_init_fields
    )
    assert execute_phase_manifest.stage("wave_dispatch").writes_allowed == ("GPD/phases",)
    assert execute_phase_manifest.stage("executor_dispatch").writes_allowed == ("GPD/phases",)
    assert execute_phase_manifest.stage("wave_return_checkpoint").writes_allowed == ("GPD/phases",)
    assert execute_phase_manifest.stage("aggregate_and_verify").writes_allowed == ("GPD/phases",)
    assert execute_phase_manifest.stage("verification_handoff").writes_allowed == ("GPD/phases", "GPD/STATE.md")
    assert execute_phase_manifest.stage("gap_reverification").writes_allowed == ("GPD/phases", "GPD/STATE.md")


def test_new_project_split_stages_do_not_load_root_index_as_authority() -> None:
    manifest = load_workflow_stage_manifest("new-project")

    assert manifest.stage_ids() == NEW_PROJECT_STAGE_IDS
    for stage in manifest.stages:
        assert NEW_PROJECT_ROOT_AUTHORITY not in stage.mode_paths
        assert NEW_PROJECT_ROOT_AUTHORITY not in stage.loaded_authorities
        staged_payload = manifest.staged_loading_payload(stage.id)
        assert NEW_PROJECT_ROOT_AUTHORITY not in staged_payload["mode_paths"]
        assert NEW_PROJECT_ROOT_AUTHORITY not in staged_payload["loaded_authorities"]
        assert NEW_PROJECT_ROOT_AUTHORITY not in staged_payload["eager_authorities"]


def test_validate_workflow_stage_manifest_payload_loads_verify_work_manifest() -> None:
    manifest = validate_workflow_stage_manifest_payload(
        _workflow_payload("verify-work"),
        expected_workflow_id="verify-work",
    )

    assert manifest.workflow_id == "verify-work"
    assert manifest.prompt_usage == "staged_init"
    assert manifest.stage_ids() == (
        "session_router",
        "phase_bootstrap",
        "inventory_build",
        "interactive_validation",
        "gap_repair",
    )
    assert manifest.stages[0].mode_paths == ("workflows/verify-work/session-router.md",)
    assert manifest.stages[0].loaded_authorities == ("workflows/verify-work/session-router.md",)
    assert "workflows/verify-work.md" in manifest.stages[0].must_not_eager_load
    assert "workflows/verify-work/gap-repair.md" in manifest.stages[0].must_not_eager_load
    assert "references/verification/core/proof-redteam-workflow-gate.md" in manifest.stages[0].must_not_eager_load
    assert "references/verification/core/verification-core.md" in manifest.stages[0].must_not_eager_load
    assert "templates/verification-report.md" in manifest.stages[0].must_not_eager_load
    assert "phase_proof_review_status" in manifest.stages[0].required_init_fields
    assert "active_verification_sessions" in manifest.stages[0].required_init_fields
    assert "verification_report_status_payload" in manifest.stages[0].required_init_fields
    assert "project_contract_gate" in manifest.stages[0].required_init_fields
    assert "project_contract_load_info" in manifest.stages[0].required_init_fields
    assert "project_contract_validation" in manifest.stages[0].required_init_fields
    assert "references/verification/core/verification-core.md" in manifest.stages[1].must_not_eager_load
    assert manifest.stages[1].mode_paths == ("workflows/verify-work/phase-bootstrap.md",)
    assert manifest.stages[1].loaded_authorities == (
        "workflows/verify-work/phase-bootstrap.md",
        "references/verification/core/proof-redteam-workflow-gate.md",
    )
    assert "phase_proof_review_status" in manifest.stages[1].required_init_fields
    assert "proof_redteam_finalizer_bridge" in manifest.stages[1].required_init_fields
    assert "proof-bearing work detected" not in manifest.stages[1].checkpoints
    assert (
        "proof-readiness context loaded; classify proof-bearing status from inspected proof metadata"
        in manifest.stages[1].checkpoints
    )
    assert manifest.stages[2].loaded_authorities == ("workflows/verify-work/inventory-build.md",)
    assert {
        conditional.when: conditional.authorities for conditional in manifest.stages[2].conditional_authorities
    } == {"full_independence_policy_check": ("references/verification/meta/verification-independence.md",)}
    assert "references/verification/meta/verification-independence.md" in manifest.stages[2].must_not_eager_load
    assert "templates/verification-report.md" not in manifest.stages[2].eager_authorities()
    assert "workflows/verify-work/gap-repair.md" in manifest.stages[2].must_not_eager_load
    assert "protocol_bundle_verifier_extensions" in manifest.stages[2].required_init_fields
    assert "protocol_bundle_load_manifest" in manifest.stages[2].required_init_fields
    assert "project_root" in manifest.stages[2].required_init_fields
    assert "phase_dir_abs" in manifest.stages[2].required_init_fields
    assert "phase_number" in manifest.stages[2].required_init_fields
    assert "phase_proof_review_status" in manifest.stages[2].required_init_fields
    assert "active_verification_sessions" not in manifest.stages[2].required_init_fields
    assert "verification_report_status_payload" not in manifest.stages[2].required_init_fields
    assert "verification_report_path" not in manifest.stages[2].required_init_fields
    assert "protocol_bundle_context" not in manifest.stages[2].required_init_fields
    assert "active_reference_context" not in manifest.stages[2].required_init_fields
    assert "active_references" in manifest.stages[2].required_init_fields
    assert "verification_report_finalizer_bridge" in manifest.stages[2].required_init_fields
    assert "verification_report_skeleton_bridge" in manifest.stages[2].required_init_fields
    assert "reference_artifacts_content" not in manifest.stages[2].required_init_fields
    assert all(not tool.startswith("mcp__gpd_") for stage in manifest.stages for tool in stage.allowed_tools)
    assert "shell" in manifest.stages[2].allowed_tools
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
        "writer-stage schema deferral barrier is visible",
        "check results remain contract-backed",
    )
    assert "reference_artifact_files" in manifest.stages[3].required_init_fields
    assert "active_reference_context" not in manifest.stages[3].required_init_fields
    assert "reference_artifacts_content" not in manifest.stages[3].required_init_fields
    assert "protocol_bundle_context" not in manifest.stages[3].required_init_fields
    assert "protocol_bundle_verifier_extensions" not in manifest.stages[3].required_init_fields
    assert manifest.stages[3].loaded_authorities == ("workflows/verify-work/interactive-validation.md",)
    interactive_schema_pack = (
        "templates/research-verification.md",
        "templates/verification-report.md",
        "templates/contract-results-schema.md",
        "references/shared/canonical-schema-discipline.md",
    )
    interactive_conditionals = {
        conditional.when: conditional.authorities for conditional in manifest.stages[3].conditional_authorities
    }
    assert interactive_conditionals["session_overlay_write_or_repair"] == interactive_schema_pack
    assert interactive_conditionals["custom_verifier_continuation"] == (
        "templates/verification-report.md",
        "templates/contract-results-schema.md",
        "references/shared/canonical-schema-discipline.md",
    )
    for authority in interactive_schema_pack:
        assert authority in manifest.stages[3].must_not_eager_load
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
    assert "reference_artifacts_content" not in manifest.stages[4].required_init_fields
    assert "contract_intake" in manifest.stages[4].required_init_fields
    assert "effective_reference_intake" in manifest.stages[4].required_init_fields
    assert "selected_protocol_bundle_ids" in manifest.stages[4].required_init_fields
    assert "protocol_bundle_load_manifest" in manifest.stages[4].required_init_fields
    assert "protocol_bundle_context" not in manifest.stages[4].required_init_fields
    assert "active_reference_context" not in manifest.stages[4].required_init_fields
    assert "protocol_bundle_verifier_extensions" in manifest.stages[4].required_init_fields
    assert manifest.stages[4].loaded_authorities == ("workflows/verify-work/gap-repair.md",)
    gap_schema_pack = (
        "templates/research-verification.md",
        "templates/verification-report.md",
        "templates/contract-results-schema.md",
        "references/shared/canonical-schema-discipline.md",
    )
    gap_conditionals = {
        conditional.when: conditional.authorities for conditional in manifest.stages[4].conditional_authorities
    }
    assert gap_conditionals["gap_report_write_or_schema_repair"] == gap_schema_pack
    assert gap_conditionals["error_propagation_gap"] == ("references/protocols/error-propagation-protocol.md",)
    for authority in (*gap_schema_pack, "references/protocols/error-propagation-protocol.md"):
        assert authority in manifest.stages[4].must_not_eager_load


def test_verify_work_context_uses_workflow_staging_init_field_source() -> None:
    assert context_module._VERIFY_WORK_INIT_FIELDS == VERIFY_WORK_INIT_FIELDS
    assert context_module._VERIFY_WORK_CONTRACT_GATE_FIELDS <= VERIFY_WORK_INIT_FIELDS
    assert context_module._VERIFY_WORK_REFERENCE_RUNTIME_FIELDS <= VERIFY_WORK_INIT_FIELDS
    assert context_module._VERIFY_WORK_STRUCTURED_STATE_FIELDS <= VERIFY_WORK_INIT_FIELDS
    assert context_module._VERIFY_WORK_STATE_MEMORY_FIELDS <= VERIFY_WORK_INIT_FIELDS
    assert {
        "derived_knowledge_docs",
        "derived_knowledge_doc_count",
        "knowledge_doc_files",
        "stable_knowledge_doc_files",
        "knowledge_doc_status_counts",
    } <= VERIFY_WORK_INIT_FIELDS


def test_autonomous_context_uses_workflow_staging_init_field_source() -> None:
    assert context_module._AUTONOMOUS_INIT_FIELDS == AUTONOMOUS_INIT_FIELDS
    assert "autonomous_argument_input" in AUTONOMOUS_INIT_FIELDS
    assert "autonomous_completed_phase_verification_statuses" in AUTONOMOUS_INIT_FIELDS
    assert "verification_report_status_payload" in AUTONOMOUS_INIT_FIELDS


def test_stage_manifests_are_prompt_used_or_cli_reachable() -> None:
    cli_text = (REPO_ROOT / "src" / "gpd" / "cli.py").read_text(encoding="utf-8")

    for manifest_path in sorted(WORKFLOW_STAGE_MANIFEST_DIR.glob(f"*{WORKFLOW_STAGE_MANIFEST_SUFFIX}")):
        workflow_id = manifest_path.name.removesuffix(WORKFLOW_STAGE_MANIFEST_SUFFIX)
        manifest = load_workflow_stage_manifest(workflow_id)
        workflow_text = (WORKFLOW_STAGE_MANIFEST_DIR / f"{workflow_id}.md").read_text(encoding="utf-8")

        init_command = "resume" if workflow_id == "resume-work" else workflow_id
        prompt_uses_staged_init = f"gpd --raw init {init_command}" in workflow_text and "--stage" in workflow_text
        cli_init_reachable = f'@init_app.command("{workflow_id}")' in cli_text

        assert manifest.prompt_usage == "staged_init"
        assert prompt_uses_staged_init or cli_init_reachable, (
            f"{manifest_path.name} must be used by its prompt or reachable through gpd init"
        )


def test_verify_work_manifest_uses_cli_shell_not_mcp_verification_tools() -> None:
    manifest = validate_workflow_stage_manifest_payload(
        _workflow_payload("verify-work"),
        expected_workflow_id="verify-work",
    )

    inventory = manifest.stage("inventory_build")
    assert "shell" in inventory.allowed_tools
    assert all(not tool.startswith("mcp__gpd_") for tool in inventory.allowed_tools)


def test_workflow_allowed_tool_defaults_cover_all_stage_manifests() -> None:
    fallback_tools = allowed_tools_for_workflow("__synthetic__")

    for manifest_path in sorted(WORKFLOW_STAGE_MANIFEST_DIR.glob(f"*{WORKFLOW_STAGE_MANIFEST_SUFFIX}")):
        workflow_id = manifest_path.name.removesuffix(WORKFLOW_STAGE_MANIFEST_SUFFIX)
        manifest = load_workflow_stage_manifest(workflow_id)
        stage_tools = {tool for stage in manifest.stages for tool in stage.allowed_tools}
        workflow_default = allowed_tools_for_workflow(workflow_id)

        assert workflow_default != fallback_tools, f"{workflow_id} must have a workflow-specific tool default"
        assert stage_tools <= workflow_default


def test_workflow_allowed_tool_defaults_reject_policy_forbidden_canonical_tool() -> None:
    payload = _workflow_payload("quick")
    stage = payload["stages"][0]
    stage_source = _stage_source_with_defaults(payload, stage)
    stage["allowed_tools"] = [*stage_source["allowed_tools"], "web_search"]

    with pytest.raises(ValueError, match="unknown tool name"):
        validate_workflow_stage_manifest_payload(payload, expected_workflow_id="quick")


def test_explicit_allowed_tool_override_still_supports_synthetic_manifest() -> None:
    manifest = validate_workflow_stage_manifest_payload(
        {
            "schema_version": 1,
            "workflow_id": "synthetic",
            "stages": [
                {
                    "id": "probe",
                    "order": 1,
                    "purpose": "Load a synthetic stage.",
                    "mode_paths": ["workflows/quick.md"],
                    "required_init_fields": [],
                    "loaded_authorities": ["workflows/quick.md"],
                    "conditional_authorities": [],
                    "must_not_eager_load": [],
                    "allowed_tools": ["special_probe"],
                    "writes_allowed": [],
                    "produced_state": [],
                    "next_stages": [],
                    "checkpoints": [],
                },
            ],
        },
        expected_workflow_id="synthetic",
        allowed_tools={"special_probe"},
    )

    assert manifest.stage("probe").allowed_tools == ("special_probe",)


def test_staged_loading_payload_exposes_eager_authority_metadata() -> None:
    manifest = validate_workflow_stage_manifest_payload(
        _workflow_payload("verify-work"),
        expected_workflow_id="verify-work",
    )
    stage = manifest.stage("inventory_build")

    payload = manifest.staged_loading_payload(stage.id)

    assert payload["mode_paths"] == list(stage.mode_paths)
    assert payload["loaded_authorities"] == list(stage.loaded_authorities)
    assert payload["eager_authorities"] == list(stage.eager_authorities())
    assert payload["eager_authorities"] == ["workflows/verify-work/inventory-build.md"]
    assert payload["conditional_authorities"] == [
        {
            "when": "full_independence_policy_check",
            "authorities": ["references/verification/meta/verification-independence.md"],
        }
    ]
    assert payload["required_init_fields"] == list(stage.required_init_fields)
    assert payload["produced_state"] == list(stage.produced_state)


def test_workflow_stage_manifest_expands_required_init_field_groups() -> None:
    manifest = validate_workflow_stage_manifest_payload(
        {
            "schema_version": 1,
            "workflow_id": "quick",
            "required_init_field_groups": {
                "bootstrap": ["executor_model", "commit_docs"],
            },
            "stages": [
                {
                    "id": "task_bootstrap",
                    "order": 1,
                    "purpose": "Load task bootstrap context.",
                    "mode_paths": ["workflows/quick.md"],
                    "required_init_field_groups": ["bootstrap"],
                    "required_init_fields": ["autonomy"],
                    "loaded_authorities": ["workflows/quick.md"],
                    "conditional_authorities": [],
                    "must_not_eager_load": [],
                    "allowed_tools": ["file_read"],
                    "writes_allowed": [],
                    "produced_state": [],
                    "next_stages": [],
                    "checkpoints": [],
                },
            ],
        },
        expected_workflow_id="quick",
    )

    stage = manifest.stage("task_bootstrap")
    assert stage.required_init_fields == ("executor_model", "commit_docs", "autonomy")
    assert manifest.staged_loading_payload(stage.id)["required_init_fields"] == [
        "executor_model",
        "commit_docs",
        "autonomy",
    ]
    assert "required_init_field_groups" not in manifest.to_payload()["stages"][0]


def test_workflow_stage_manifest_adds_protocol_bundle_load_manifest_with_context_fields() -> None:
    manifest = validate_workflow_stage_manifest_payload(
        {
            "schema_version": 1,
            "workflow_id": "quick",
            "stages": [
                {
                    "id": "reference_context",
                    "order": 1,
                    "purpose": "Load reference context.",
                    "mode_paths": ["workflows/quick.md"],
                    "required_init_fields": [
                        "selected_protocol_bundle_ids",
                        "protocol_bundle_count",
                        "protocol_bundle_context",
                    ],
                    "loaded_authorities": ["workflows/quick.md"],
                    "conditional_authorities": [],
                    "must_not_eager_load": [],
                    "allowed_tools": ["file_read"],
                    "writes_allowed": [],
                    "produced_state": [],
                    "next_stages": [],
                    "checkpoints": [],
                },
            ],
        },
        expected_workflow_id="quick",
    )

    assert manifest.stage("reference_context").required_init_fields == (
        "selected_protocol_bundle_ids",
        "protocol_bundle_count",
        "protocol_bundle_load_manifest",
        "protocol_bundle_context",
    )


def test_load_workflow_stage_manifest_from_local_specs_root_expands_groups_and_separates_cache(
    tmp_path: Path,
) -> None:
    specs_root = tmp_path / "src" / "gpd" / "specs"
    (specs_root / "workflows").mkdir(parents=True)
    (specs_root / "templates").mkdir(parents=True)
    (specs_root / "workflows" / "probe.md").write_text("Probe bootstrap.\n", encoding="utf-8")
    (specs_root / "templates" / "deferred.md").write_text("Deferred authority.\n", encoding="utf-8")
    manifest_path = specs_root / "workflows" / "probe-stage-manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "workflow_id": "probe",
                "required_init_field_groups": {
                    "reference_runtime": [
                        "selected_protocol_bundle_ids",
                        "protocol_bundle_count",
                        "protocol_bundle_context",
                    ],
                },
                "stages": [
                    {
                        "id": "bootstrap",
                        "order": 1,
                        "purpose": "Load local bootstrap authority.",
                        "mode_paths": ["workflows/probe.md"],
                        "required_init_field_groups": ["reference_runtime"],
                        "required_init_fields": ["autonomy"],
                        "loaded_authorities": ["workflows/probe.md"],
                        "conditional_authorities": [
                            {"when": "need_deferred", "authorities": ["templates/deferred.md"]},
                        ],
                        "must_not_eager_load": ["templates/deferred.md"],
                        "allowed_tools": [],
                        "writes_allowed": [],
                        "produced_state": [],
                        "next_stages": [],
                        "checkpoints": [],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    manifest = load_workflow_stage_manifest_from_path(
        manifest_path,
        expected_workflow_id="probe",
        specs_root=specs_root,
    )
    manifest_by_id = load_workflow_stage_manifest("probe", specs_root=specs_root)

    expected_fields = (
        "selected_protocol_bundle_ids",
        "protocol_bundle_count",
        "protocol_bundle_load_manifest",
        "protocol_bundle_context",
        "autonomy",
    )
    assert manifest_by_id is manifest
    assert manifest.stage("bootstrap").required_init_fields == expected_fields
    assert manifest.staged_loading_payload("bootstrap")["required_init_fields"] == list(expected_fields)

    other_specs_root = tmp_path / "other" / "specs"
    other_specs_root.mkdir(parents=True)
    with pytest.raises(ValueError, match="existing markdown file"):
        load_workflow_stage_manifest_from_path(
            manifest_path,
            expected_workflow_id="probe",
            specs_root=other_specs_root,
        )


@pytest.mark.parametrize("workflow_id", PHASE3_MANIFEST_DERIVED_KNOWN_FIELD_WORKFLOWS)
def test_expanded_required_init_field_helpers_expose_stable_manifest_order(workflow_id: str) -> None:
    manifest = load_workflow_stage_manifest(workflow_id)
    fields_by_stage = expanded_required_init_fields_by_stage(manifest)

    assert fields_by_stage == tuple((stage.id, stage.required_init_fields) for stage in manifest.stages)
    assert expanded_required_init_fields_for_workflow(workflow_id) == _stable_field_union(
        fields for _, fields in fields_by_stage
    )


@pytest.mark.parametrize("workflow_id", PHASE3_MANIFEST_DERIVED_KNOWN_FIELD_WORKFLOWS)
def test_known_init_fields_for_phase3_targets_are_manifest_derived(workflow_id: str) -> None:
    fields_by_stage = expanded_required_init_fields_by_stage(load_workflow_stage_manifest(workflow_id))

    assert known_init_fields_for_workflow(workflow_id) == frozenset(
        _stable_field_union(fields for _, fields in fields_by_stage)
    )


def test_explicit_known_init_fields_still_validate_synthetic_manifest_fields() -> None:
    payload = {
        "schema_version": 1,
        "workflow_id": "quick",
        "required_init_field_groups": {
            "bootstrap": ["executor_model", "commit_docs"],
        },
        "stages": [
            {
                "id": "task_bootstrap",
                "order": 1,
                "purpose": "Load task bootstrap context.",
                "mode_paths": ["workflows/quick.md"],
                "required_init_field_groups": ["bootstrap"],
                "required_init_fields": ["autonomy"],
                "loaded_authorities": ["workflows/quick.md"],
                "conditional_authorities": [],
                "must_not_eager_load": [],
                "allowed_tools": ["file_read"],
                "writes_allowed": [],
                "produced_state": [],
                "next_stages": [],
                "checkpoints": [],
            },
        ],
    }

    with pytest.raises(ValueError, match="unknown field name.*autonomy"):
        validate_workflow_stage_manifest_payload(
            payload,
            expected_workflow_id="quick",
            known_init_fields={"executor_model", "commit_docs"},
        )


@pytest.mark.parametrize("workflow_id", ["new-project", "quick"])
def test_workflow_stage_manifest_serialized_payload_round_trips_expanded_fields(workflow_id: str) -> None:
    manifest = validate_workflow_stage_manifest_payload(
        _workflow_payload(workflow_id),
        expected_workflow_id=workflow_id,
    )
    serialized = manifest.to_payload()

    assert "required_init_field_groups" not in serialized
    assert all("required_init_field_groups" not in stage for stage in serialized["stages"])
    assert (
        validate_workflow_stage_manifest_payload(
            serialized,
            expected_workflow_id=workflow_id,
        ).to_payload()
        == serialized
    )


@pytest.mark.parametrize(
    "workflow_id",
    [
        "arxiv-submission",
        "execute-phase",
        "map-research",
        "plan-phase",
        "quick",
        "verify-work",
    ],
)
def test_stage_manifests_use_real_required_init_field_groups(workflow_id: str) -> None:
    payload = _workflow_payload(workflow_id)
    groups = payload.get("required_init_field_groups")

    assert isinstance(groups, dict)
    assert groups

    manifest = validate_workflow_stage_manifest_payload(payload, expected_workflow_id=workflow_id)
    grouped_stage_count = 0
    for raw_stage in payload["stages"]:
        assert isinstance(raw_stage, dict)
        stage_source = _stage_source_with_defaults(payload, raw_stage)
        group_names = stage_source.get("required_init_field_groups", [])
        if group_names:
            grouped_stage_count += 1
        assert isinstance(group_names, list)

        expanded_fields: list[str] = []
        for group_name in group_names:
            assert isinstance(group_name, str)
            expanded_fields.extend(groups[group_name])
        expanded_fields.extend(stage_source.get("required_init_fields", []))

        assert manifest.stage(str(raw_stage["id"])).required_init_fields == tuple(
            _with_protocol_bundle_load_manifest(expanded_fields)
        )

    assert grouped_stage_count == len(payload["stages"])


def test_workflow_stage_manifest_rejects_unknown_required_init_field_groups() -> None:
    payload = _workflow_payload("quick")
    payload["stages"][0]["required_init_field_groups"] = ["missing"]

    with pytest.raises(ValueError, match="unknown group"):
        validate_workflow_stage_manifest_payload(payload, expected_workflow_id="quick")


def test_load_workflow_stage_manifest_from_path_without_expected_id_uses_manifest_workflow_id(
    tmp_path: Path,
) -> None:
    payload = _workflow_payload("execute-phase")
    manifest_path = tmp_path / "custom-stage-manifest.json"
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    manifest = load_workflow_stage_manifest_from_path(manifest_path)

    assert manifest.workflow_id == "execute-phase"
    assert manifest.stage_ids()[0] == "phase_bootstrap"


def test_load_workflow_stage_manifest_from_path_validates_inferred_workflow_init_fields(
    tmp_path: Path,
) -> None:
    payload = _workflow_payload("execute-phase")
    payload["stages"][0].setdefault("required_init_fields", []).append("not_an_execute_phase_field")
    manifest_path = tmp_path / "custom-stage-manifest.json"
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="unknown field name"):
        load_workflow_stage_manifest_from_path(manifest_path)


def test_load_verify_work_manifest_from_path_uses_workflow_tool_defaults(tmp_path: Path) -> None:
    payload = _workflow_payload("verify-work")
    manifest_path = tmp_path / "verify-work-stage-manifest.json"
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    manifest = load_workflow_stage_manifest_from_path(manifest_path)

    assert manifest.workflow_id == "verify-work"
    assert "shell" in manifest.stage("inventory_build").allowed_tools


def test_known_init_fields_for_verify_work_include_proof_gate_and_artifact_context() -> None:
    known_init_fields = known_init_fields_for_workflow("verify-work")

    assert known_init_fields is not None
    assert known_init_fields <= context_module._VERIFY_WORK_INIT_FIELDS
    assert "phase_proof_review_status" in known_init_fields
    assert "project_contract_gate" in known_init_fields
    assert "project_contract_load_info" in known_init_fields
    assert "project_contract_validation" in known_init_fields
    assert "selected_protocol_bundle_ids" in known_init_fields
    assert "protocol_bundle_load_manifest" in known_init_fields
    assert "protocol_bundle_verifier_extensions" in known_init_fields
    assert "proof_redteam_finalizer_bridge" in known_init_fields
    assert "verification_report_finalizer_bridge" in known_init_fields
    assert "verification_report_skeleton_bridge" in known_init_fields
    assert "verification_report_status_payload" in known_init_fields
    assert "reference_artifact_files" in known_init_fields


@pytest.mark.parametrize(
    "workflow_id",
    [
        "autonomous",
        "execute-phase",
        "literature-review",
        "map-research",
        "new-project",
        "new-milestone",
        "peer-review",
        "plan-phase",
        "quick",
        "research-phase",
        "resume-work",
        "sync-state",
        "verify-work",
        "write-paper",
    ],
)
def test_staged_init_payloads_match_manifest_required_fields_and_loading_metadata(
    tmp_path: Path,
    workflow_id: str,
) -> None:
    manifest = load_workflow_stage_manifest(workflow_id)
    _setup_generic_staged_init_project(tmp_path)

    for stage_id in manifest.stage_ids():
        payload = _staged_init_payload_for_workflow(tmp_path, workflow_id, stage_id)

        assert_staged_payload_matches_manifest(
            payload,
            manifest,
            workflow_id=workflow_id,
            stage_id=stage_id,
        )


def test_new_milestone_known_init_fields_are_manifest_subset_of_context_assembly_fields() -> None:
    known_init_fields = known_init_fields_for_workflow("new-milestone")
    fields_by_stage = expanded_required_init_fields_by_stage(load_workflow_stage_manifest("new-milestone"))

    assert known_init_fields == frozenset(_stable_field_union(fields for _, fields in fields_by_stage))
    assert known_init_fields <= context_module._NEW_MILESTONE_INIT_FIELDS
    assert "init_root_policy" in context_module._NEW_MILESTONE_INIT_FIELDS


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
    assert manifest.stages[0].loaded_authorities == ("workflows/plan-phase/phase-bootstrap.md",)
    assert manifest.stages[0].mode_paths == ("workflows/plan-phase/phase-bootstrap.md",)
    assert "workflows/plan-phase.md" in manifest.stages[0].must_not_eager_load
    assert "workflows/plan-phase/research-routing.md" in manifest.stages[0].must_not_eager_load
    assert "workflows/plan-phase/planner-authoring.md" in manifest.stages[0].must_not_eager_load
    assert "workflows/plan-phase/checker-revision.md" in manifest.stages[0].must_not_eager_load
    assert "references/orchestration/runtime-delegation-note.md" in manifest.stages[0].must_not_eager_load
    assert "templates/plan-contract-schema.md" in manifest.stages[0].must_not_eager_load
    assert "templates/planner-subagent-prompt.md" in manifest.stages[0].must_not_eager_load
    assert manifest.stages[1].loaded_authorities == (
        "workflows/plan-phase/research-routing.md",
        "references/orchestration/runtime-delegation-note.md",
    )
    assert manifest.stages[2].loaded_authorities == (
        "workflows/plan-phase/planner-authoring.md",
        "templates/planner-subagent-prompt.md",
    )
    assert manifest.stages[3].loaded_authorities == ("workflows/plan-phase/checker-revision.md",)
    checker_conditionals = {
        authority for conditional in manifest.stages[3].conditional_authorities for authority in conditional.authorities
    }
    assert "templates/planner-subagent-prompt.md" in checker_conditionals
    assert "templates/planner-subagent-prompt.md" in manifest.stages[3].must_not_eager_load
    assert "reference_artifacts_content" not in manifest.stages[2].required_init_fields
    assert "reference_artifacts_content" not in manifest.stages[3].required_init_fields
    assert "reference_artifact_files" in manifest.stages[2].required_init_fields
    assert "reference_artifact_files" in manifest.stages[3].required_init_fields
    assert "protocol_bundle_load_manifest" in manifest.stages[2].required_init_fields
    assert "protocol_bundle_load_manifest" in manifest.stages[3].required_init_fields
    assert "protocol_bundle_context" not in manifest.stages[2].required_init_fields
    assert "protocol_bundle_context" not in manifest.stages[3].required_init_fields
    assert "active_reference_context" in manifest.stages[2].required_init_fields
    assert "active_reference_context" not in manifest.stages[3].required_init_fields
    for core_evidence_field in (
        "state_content",
        "roadmap_content",
        "requirements_content",
        "context_content",
        "research_content",
    ):
        assert core_evidence_field in manifest.stages[2].required_init_fields
        assert core_evidence_field not in manifest.stages[3].required_init_fields
    for artifact_specific_field in (
        "experiment_design_content",
        "verification_content",
        "validation_content",
    ):
        assert artifact_specific_field not in manifest.stages[2].required_init_fields
        assert artifact_specific_field not in manifest.stages[3].required_init_fields
    assert "requirements_content" not in manifest.stages[3].required_init_fields
    assert "context_content" not in manifest.stages[3].required_init_fields
    assert "state_content" not in manifest.stages[3].required_init_fields
    assert "GPD/phases" in manifest.stages[2].writes_allowed


def test_validate_workflow_stage_manifest_payload_loads_quick_manifest() -> None:
    manifest = validate_workflow_stage_manifest_payload(
        _workflow_payload("quick"),
        expected_workflow_id="quick",
    )

    assert manifest.workflow_id == "quick"
    assert manifest.stage_ids() == ("task_bootstrap", "task_authoring", "reference_context")

    bootstrap = manifest.stage("task_bootstrap")
    authoring = manifest.stage("task_authoring")
    reference_context = manifest.stage("reference_context")

    expected_init_spec_ids = {
        "task_bootstrap": "quick.task_bootstrap.v1",
        "task_authoring": "quick.task_authoring.v1",
        "reference_context": "quick.reference_context.v1",
    }
    for stage_id, init_spec_id in expected_init_spec_ids.items():
        stage = manifest.stage(stage_id)
        assert stage.init_spec_id == init_spec_id
        assert stage.to_payload()["init_spec_id"] == init_spec_id
        assert manifest.staged_loading_payload(stage_id)["init_spec_id"] == init_spec_id

    round_trip = validate_workflow_stage_manifest_payload(
        manifest.to_payload(),
        expected_workflow_id="quick",
    )
    assert {
        stage_id: round_trip.stage(stage_id).init_spec_id for stage_id in expected_init_spec_ids
    } == expected_init_spec_ids

    assert bootstrap.loaded_authorities == (
        "workflows/quick/task-bootstrap.md",
        "references/quick/quick-mode-boundary.md",
        "references/quick/quick-durability-minimum.md",
        "references/quick/quick-reroute-rules.md",
    )
    assert bootstrap.next_stages == ("task_authoring", "reference_context")
    assert "workflows/quick.md" in bootstrap.must_not_eager_load
    assert "workflows/quick/task-authoring.md" in bootstrap.must_not_eager_load
    assert "references/orchestration/runtime-delegation-note.md" in bootstrap.must_not_eager_load
    assert "references/ui/ui-brand.md" in bootstrap.must_not_eager_load
    assert "references/publication/publication-pipeline-modes.md" in bootstrap.must_not_eager_load
    assert "references/verification/core/proof-redteam-workflow-gate.md" in bootstrap.must_not_eager_load
    assert "project_contract_gate" in bootstrap.required_init_fields
    assert "project_contract_validation" in bootstrap.required_init_fields

    assert "project_contract_gate" in authoring.required_init_fields
    assert "contract_intake" not in authoring.required_init_fields
    assert "effective_reference_intake" not in authoring.required_init_fields
    assert "reference_artifacts_content" not in authoring.required_init_fields
    assert "derived_manuscript_proof_review_status" not in authoring.required_init_fields
    assert "templates/planner-subagent-prompt.md" in authoring.must_not_eager_load
    assert authoring.writes_allowed == ("GPD/quick/NNN-slug/NNN-PLAN.md",)

    assert "contract_intake" in reference_context.required_init_fields
    assert reference_context.loaded_authorities[0] == "workflows/quick/reference-context.md"
    assert reference_context.mode_paths == ("workflows/quick/reference-context.md",)
    assert "effective_reference_intake" in reference_context.required_init_fields
    assert "reference_artifact_files" in reference_context.required_init_fields
    assert "protocol_bundle_load_manifest" in reference_context.required_init_fields
    assert "active_reference_context" not in reference_context.required_init_fields
    assert "protocol_bundle_context" not in reference_context.required_init_fields
    assert "reference_artifacts_content" not in reference_context.required_init_fields
    assert "derived_manuscript_proof_review_status" in reference_context.required_init_fields
    assert reference_context.writes_allowed == ("GPD/quick/NNN-slug/NNN-PLAN.md",)


@pytest.mark.parametrize(
    "workflow_id",
    [
        manifest_path.name[: -len(WORKFLOW_STAGE_MANIFEST_SUFFIX)]
        for manifest_path in sorted(WORKFLOW_STAGE_MANIFEST_DIR.glob(f"*{WORKFLOW_STAGE_MANIFEST_SUFFIX}"))
        if manifest_path.name != f"quick{WORKFLOW_STAGE_MANIFEST_SUFFIX}"
    ],
)
def test_non_quick_manifests_do_not_emit_init_spec_id(workflow_id: str) -> None:
    raw_payload = _workflow_payload(workflow_id)
    assert all("init_spec_id" not in stage for stage in raw_payload["stages"])

    manifest = load_workflow_stage_manifest(workflow_id)
    for stage_id in manifest.stage_ids():
        stage = manifest.stage(stage_id)
        assert stage.init_spec_id is None
        assert "init_spec_id" not in stage.to_payload()
        assert "init_spec_id" not in manifest.staged_loading_payload(stage_id)


def test_validate_workflow_stage_manifest_payload_loads_write_paper_manifest() -> None:
    manifest = validate_workflow_stage_manifest_payload(
        _workflow_payload("write-paper"),
        expected_workflow_id="write-paper",
    )
    bootstrap = manifest.stage("paper_bootstrap")
    outline = manifest.stage("outline_and_scaffold")
    authoring = manifest.stage("figure_and_section_authoring")
    consistency = manifest.stage("consistency_and_references")
    publication_review = manifest.stage("publication_review")

    assert manifest.workflow_id == "write-paper"
    assert manifest.stage_ids() == (
        "paper_bootstrap",
        "outline_and_scaffold",
        "figure_and_section_authoring",
        "consistency_and_references",
        "publication_review",
    )
    assert "workflows/write-paper/paper-bootstrap.md" in bootstrap.loaded_authorities
    assert "references/publication/publication-review-round-artifacts.md" in bootstrap.must_not_eager_load
    assert "references/publication/publication-response-artifacts.md" in bootstrap.must_not_eager_load
    assert "references/publication/publication-pipeline-modes.md" in bootstrap.must_not_eager_load
    assert "references/publication/peer-review-panel.md" in bootstrap.must_not_eager_load
    assert "references/publication/stage-recovery-gate.md" in bootstrap.must_not_eager_load
    assert "templates/paper/paper-config-schema.md" in bootstrap.must_not_eager_load
    assert bootstrap.writes_allowed == ()
    assert "contract_intake" not in bootstrap.required_init_fields
    assert "effective_reference_intake" in bootstrap.required_init_fields
    assert "publication_subject_slug" in bootstrap.required_init_fields
    assert "publication_lane_kind" in bootstrap.required_init_fields
    assert "publication_lane_owner" in bootstrap.required_init_fields
    assert "selected_publication_root" in bootstrap.required_init_fields
    assert "publication_intake_root" in bootstrap.required_init_fields
    assert "managed_publication_root" in bootstrap.required_init_fields
    assert "managed_manuscript_root" in bootstrap.required_init_fields
    assert outline.loaded_authorities == ("workflows/write-paper/outline-scaffold.md",)
    assert {conditional.when: conditional.authorities for conditional in outline.conditional_authorities} == {
        "publication_lane_or_builder_config_selection": ("references/publication/publication-pipeline-modes.md",),
        "paper_builder_config_or_artifact_manifest_write": (
            "templates/paper/paper-config-schema.md",
            "templates/paper/artifact-manifest-schema.md",
        ),
    }
    assert "references/publication/publication-pipeline-modes.md" in outline.must_not_eager_load
    assert "templates/paper/paper-config-schema.md" in outline.must_not_eager_load
    assert "templates/paper/artifact-manifest-schema.md" in outline.must_not_eager_load
    assert outline.writes_allowed == (
        WRITE_PAPER_MANAGED_MANUSCRIPT_ROOT,
        WRITE_PAPER_MANAGED_INTAKE_ROOT,
        "GPD/PROJECT.md",
        "GPD/REQUIREMENTS.md",
        "GPD/ROADMAP.md",
        "GPD/STATE.md",
        "GPD/state.json",
        "GPD/config.json",
    )
    assert authoring.loaded_authorities == (
        "workflows/write-paper/authoring.md",
        "references/publication/stage-recovery-gate.md",
        "references/shared/canonical-schema-discipline.md",
        "templates/paper/figure-tracker.md",
    )
    assert authoring.writes_allowed == (
        WRITE_PAPER_MANAGED_MANUSCRIPT_ROOT,
        "GPD/phases",
        "GPD/ROADMAP.md",
        "GPD/STATE.md",
        "GPD/state.json",
    )
    assert "reference_artifact_files" in authoring.required_init_fields
    assert "reference_artifacts_content" not in authoring.required_init_fields
    assert "protocol_bundle_load_manifest" in authoring.required_init_fields
    assert "protocol_bundle_context" not in authoring.required_init_fields
    assert "active_reference_context" not in authoring.required_init_fields
    assert consistency.writes_allowed == (
        WRITE_PAPER_MANAGED_MANUSCRIPT_ROOT,
        "GPD/references-status.json",
        "GPD/STATE.md",
        "GPD/state.json",
        "GPD/review",
        "GPD/CONVENTIONS.md",
    )
    assert "reference_artifact_files" in consistency.required_init_fields
    assert "protocol_bundle_load_manifest" in consistency.required_init_fields
    assert "derived_manuscript_reference_status" in consistency.required_init_fields
    assert "citation_source_files" in consistency.required_init_fields
    assert "reference_artifacts_content" not in consistency.required_init_fields
    assert "active_reference_context" not in consistency.required_init_fields
    assert "protocol_bundle_context" not in consistency.required_init_fields
    assert publication_review.loaded_authorities == (
        "workflows/write-paper/publication-review-finalization.md",
        "references/publication/publication-review-round-artifacts.md",
    )
    assert publication_review.conditional_authorities[0].when == "response_pair_authoring"
    assert publication_review.conditional_authorities[0].authorities == (
        "references/publication/publication-response-writer-handoff.md",
        "references/publication/publication-response-artifacts.md",
        "references/publication/stage-recovery-gate.md",
        "templates/paper/author-response.md",
        "templates/paper/referee-response.md",
    )
    assert "references/publication/peer-review-panel.md" in publication_review.must_not_eager_load
    assert "references/publication/peer-review-reliability.md" in publication_review.must_not_eager_load
    assert "templates/paper/review-ledger-schema.md" in publication_review.must_not_eager_load
    assert "templates/paper/referee-decision-schema.md" in publication_review.must_not_eager_load
    assert publication_review.writes_allowed == (
        WRITE_PAPER_MANAGED_MANUSCRIPT_ROOT,
        "GPD/review",
        "GPD/publication/{subject_slug}/AUTHOR-RESPONSE{round_suffix}.md",
        "GPD/publication/{subject_slug}/review/REFEREE_RESPONSE{round_suffix}.md",
        "GPD/publication/{subject_slug}/REFEREE-REPORT{round_suffix}.md",
        "GPD/publication/{subject_slug}/REFEREE-REPORT{round_suffix}.tex",
        "GPD/AUTHOR-RESPONSE.md",
        "GPD/AUTHOR-RESPONSE-R2.md",
        "GPD/AUTHOR-RESPONSE-R3.md",
        "GPD/REFEREE-REPORT.md",
        "GPD/REFEREE-REPORT.tex",
        "GPD/REFEREE-REPORT-R2.md",
        "GPD/REFEREE-REPORT-R2.tex",
        "GPD/REFEREE-REPORT-R3.md",
        "GPD/REFEREE-REPORT-R3.tex",
    )
    assert "reference_artifact_files" in publication_review.required_init_fields
    assert "protocol_bundle_load_manifest" in publication_review.required_init_fields
    assert "derived_manuscript_reference_status" in publication_review.required_init_fields
    assert "citation_source_files" in publication_review.required_init_fields
    assert "reference_artifacts_content" not in publication_review.required_init_fields
    assert "active_reference_context" not in publication_review.required_init_fields
    assert "protocol_bundle_context" not in publication_review.required_init_fields


def test_known_init_fields_for_write_paper_cover_bootstrap_and_deferred_publication_context() -> None:
    known_init_fields = known_init_fields_for_workflow("write-paper")

    assert known_init_fields is not None
    assert known_init_fields <= context_module._WRITE_PAPER_INIT_FIELDS
    assert "project_root" in known_init_fields
    assert "project_contract_gate" in known_init_fields
    assert "project_contract_load_info" in known_init_fields
    assert "project_contract_validation" in known_init_fields
    assert "selected_protocol_bundle_ids" in known_init_fields
    assert "protocol_bundle_load_manifest" in known_init_fields
    assert "effective_reference_intake" in known_init_fields
    assert "publication_subject_status" in known_init_fields
    assert "publication_subject_slug" in known_init_fields
    assert "publication_lane_kind" in known_init_fields
    assert "publication_lane_owner" in known_init_fields
    assert "publication_bootstrap_mode" in known_init_fields
    assert "publication_bootstrap_root" in known_init_fields
    assert "selected_publication_root" in known_init_fields
    assert "selected_review_root" in known_init_fields
    assert "publication_intake_root" in known_init_fields
    assert "managed_publication_root" in known_init_fields
    assert "managed_manuscript_root" in known_init_fields


def test_publication_workflow_bootstrap_manifests_keep_project_root_in_required_fields() -> None:
    write_paper_manifest = load_workflow_stage_manifest("write-paper")
    respond_manifest = load_workflow_stage_manifest("respond-to-referees")
    arxiv_manifest = load_workflow_stage_manifest("arxiv-submission")

    assert "project_root" in write_paper_manifest.stage("paper_bootstrap").required_init_fields
    assert "project_root" in write_paper_manifest.stage("outline_and_scaffold").required_init_fields
    assert "project_root" in respond_manifest.stage("bootstrap").required_init_fields
    assert "project_root" in arxiv_manifest.stage("bootstrap").required_init_fields


def test_publication_staged_init_preserves_explicit_launch_arguments(tmp_path: Path) -> None:
    gpd_dir = tmp_path / "GPD"
    gpd_dir.mkdir()
    (gpd_dir / "config.json").write_text("{}", encoding="utf-8")
    (gpd_dir / "state.json").write_text("{}", encoding="utf-8")
    intake = "--manuscript paper/main.tex --report reviews/referee-1.md"

    respond_manifest = load_workflow_stage_manifest("respond-to-referees")
    for stage_id in respond_manifest.stage_ids():
        payload = init_respond_to_referees(tmp_path, subject=intake, stage=stage_id)
        assert payload["response_intake_input"] == intake

    arxiv_manifest = load_workflow_stage_manifest("arxiv-submission")
    for stage_id in arxiv_manifest.stage_ids():
        payload = init_arxiv_submission(tmp_path, subject="paper/main.tex", stage=stage_id)
        assert payload["arxiv_submission_argument_input"] == "paper/main.tex"

    write_paper_manifest = load_workflow_stage_manifest("write-paper")
    for stage_id in write_paper_manifest.stage_ids():
        payload = init_write_paper(tmp_path, subject="paper/main.tex", stage=stage_id)
        assert payload["write_paper_argument_input"] == "paper/main.tex"


def test_known_init_fields_for_quick_cover_task_bootstrap_and_reference_context() -> None:
    known_init_fields = known_init_fields_for_workflow("quick")
    manifest = load_workflow_stage_manifest("quick")

    assert known_init_fields is not None
    assert known_init_fields <= context_module._QUICK_INIT_FIELDS
    assert "executor_model" in known_init_fields
    assert "next_num" in known_init_fields
    assert "task_dir" in known_init_fields
    assert "project_contract_gate" in known_init_fields
    assert "contract_intake" in known_init_fields
    assert "protocol_bundle_load_manifest" in known_init_fields
    assert "contract_intake" not in manifest.stage("task_authoring").required_init_fields
    assert "reference_artifacts_content" not in manifest.stage("task_authoring").required_init_fields
    assert "contract_intake" in manifest.stage("reference_context").required_init_fields
    assert "reference_artifact_files" in manifest.stage("reference_context").required_init_fields
    assert "protocol_bundle_load_manifest" in manifest.stage("reference_context").required_init_fields
    assert "reference_artifacts_content" not in manifest.stage("reference_context").required_init_fields
    assert manifest.stage("reference_context").loaded_authorities[0] == "workflows/quick/reference-context.md"


def test_quick_reference_context_is_only_bundle_capable_stage() -> None:
    manifest = load_workflow_stage_manifest("quick")
    quick_text = "\n\n".join(
        [
            (WORKFLOW_STAGE_MANIFEST_DIR / "quick.md").read_text(encoding="utf-8"),
            (WORKFLOW_STAGE_MANIFEST_DIR / "quick" / "task-bootstrap.md").read_text(encoding="utf-8"),
            (WORKFLOW_STAGE_MANIFEST_DIR / "quick" / "task-authoring.md").read_text(encoding="utf-8"),
            (WORKFLOW_STAGE_MANIFEST_DIR / "quick" / "reference-context.md").read_text(encoding="utf-8"),
        ]
    )

    bundle_fields = {
        "selected_protocol_bundle_ids",
        "protocol_bundle_load_manifest",
        "protocol_bundle_verifier_extensions",
    }
    body_fields = {
        "active_reference_context",
        "protocol_bundle_context",
        "reference_artifacts_content",
    }

    assert bundle_fields.isdisjoint(manifest.stage("task_bootstrap").required_init_fields)
    assert bundle_fields.isdisjoint(manifest.stage("task_authoring").required_init_fields)
    assert bundle_fields.issubset(manifest.stage("reference_context").required_init_fields)
    assert body_fields.isdisjoint(manifest.stage("reference_context").required_init_fields)
    assert "`reference_context` only for targeted source lookup or tasks that need active project anchors" in quick_text
    assert "Default Reference Runtime:** not loaded for `task_authoring`" in quick_text
    assert "If `TASK_AUTHORING_INIT.staged_loading.stage_id` is `reference_context`" in quick_text
    assert "<selected_protocol_bundle_ids>" in quick_text
    assert "<protocol_bundle_load_manifest>" in quick_text
    assert "<protocol_bundle_verifier_extensions>" in quick_text
    assert "reference_artifacts_content" not in quick_text
    assert "active_reference_context" not in quick_text
    assert "protocol_bundle_context" not in quick_text


@pytest.mark.parametrize(
    ("workflow_id", "expected_fields"),
    [
        (
            "new-milestone",
            {
                "researcher_model",
                "synthesizer_model",
                "autonomy",
                "research_mode",
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
                "reference_artifact_files",
                "literature_review_files",
                "research_map_reference_files",
            },
        ),
        (
            "map-research",
            {
                "mapper_model",
                "research_map_dir",
                "existing_maps",
                "project_contract_gate",
                "reference_artifact_files",
                "selected_protocol_bundle_ids",
                "protocol_bundle_load_manifest",
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
        "workflows/research-phase/phase-bootstrap.md",
        "references/orchestration/model-profile-resolution.md",
    )
    assert "workflows/research-phase.md" in manifest.stage("phase_bootstrap").must_not_eager_load
    assert "workflows/research-phase/research-handoff.md" in manifest.stage("phase_bootstrap").must_not_eager_load
    assert (
        "references/orchestration/runtime-delegation-note.md" in manifest.stage("phase_bootstrap").must_not_eager_load
    )
    assert "reference_artifacts_content" not in manifest.stage("phase_bootstrap").required_init_fields
    assert manifest.stage("research_handoff").loaded_authorities == (
        "workflows/research-phase/research-handoff.md",
        "references/orchestration/model-profile-resolution.md",
        "references/orchestration/runtime-delegation-note.md",
    )
    assert manifest.stage("research_handoff").required_init_fields[:4] == (
        "autonomy",
        "review_cadence",
        "research_mode",
        "phase_found",
    )
    assert "contract_intake" in manifest.stage("research_handoff").required_init_fields
    assert "effective_reference_intake" in manifest.stage("research_handoff").required_init_fields
    assert "active_references" in manifest.stage("research_handoff").required_init_fields
    assert "reference_artifact_files" in manifest.stage("research_handoff").required_init_fields
    assert "reference_artifacts_content" not in manifest.stage("research_handoff").required_init_fields
    assert "selected_protocol_bundle_ids" in manifest.stage("research_handoff").required_init_fields
    assert "protocol_bundle_count" in manifest.stage("research_handoff").required_init_fields
    assert "protocol_bundle_load_manifest" in manifest.stage("research_handoff").required_init_fields
    assert "protocol_bundle_context" not in manifest.stage("research_handoff").required_init_fields
    assert "protocol_bundle_verifier_extensions" in manifest.stage("research_handoff").required_init_fields
    assert "current_execution" in manifest.stage("research_handoff").required_init_fields
    assert "derived_manuscript_proof_review_status" in manifest.stage("research_handoff").required_init_fields
    assert "config_content" not in manifest.stage("research_handoff").required_init_fields
    assert "state_content" not in manifest.stage("research_handoff").required_init_fields
    assert "roadmap_content" not in manifest.stage("research_handoff").required_init_fields
    assert manifest.stage("research_handoff").writes_allowed == ("GPD/phases/XX-name/XX-RESEARCH.md",)
    assert manifest.stage("research_handoff").checkpoints == (
        "reference, contract, and protocol handles are visible to the handoff",
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
    assert manifest.stage("milestone_bootstrap").loaded_authorities == (
        "workflows/new-milestone/milestone-bootstrap.md",
    )
    assert "workflows/new-milestone/survey-objectives.md" in manifest.stage("milestone_bootstrap").must_not_eager_load
    assert "workflows/new-milestone/roadmap-authoring.md" in manifest.stage("milestone_bootstrap").must_not_eager_load
    assert "references/research/questioning.md" in manifest.stage("milestone_bootstrap").must_not_eager_load
    assert "templates/project.md" in manifest.stage("milestone_bootstrap").must_not_eager_load
    assert "templates/requirements.md" in manifest.stage("milestone_bootstrap").must_not_eager_load
    assert "roadmapper_model" not in manifest.stage("milestone_bootstrap").required_init_fields
    assert manifest.stage("survey_objectives").loaded_authorities == (
        "workflows/new-milestone/survey-objectives.md",
        "references/orchestration/runtime-delegation-note.md",
        "references/research/questioning.md",
    )
    assert "roadmapper_model" not in manifest.stage("survey_objectives").required_init_fields
    assert "contract_intake" in manifest.stage("survey_objectives").required_init_fields
    assert "effective_reference_intake" in manifest.stage("survey_objectives").required_init_fields
    assert "reference_artifact_files" in manifest.stage("survey_objectives").required_init_fields
    assert "reference_artifacts_content" not in manifest.stage("survey_objectives").required_init_fields
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
        "workflows/new-milestone/roadmap-authoring.md",
        "references/orchestration/runtime-delegation-note.md",
    )
    assert {
        conditional.when: conditional.authorities
        for conditional in manifest.stage("roadmap_authoring").conditional_authorities
    } == {"roadmap_artifact_template_write": ("templates/project.md", "templates/requirements.md")}
    assert "templates/project.md" in manifest.stage("roadmap_authoring").must_not_eager_load
    assert "templates/requirements.md" in manifest.stage("roadmap_authoring").must_not_eager_load
    assert "requirements_content" not in manifest.stage("roadmap_authoring").required_init_fields
    assert "roadmap_content" not in manifest.stage("roadmap_authoring").required_init_fields
    assert "project_content" not in manifest.stage("roadmap_authoring").required_init_fields
    assert "state_content" not in manifest.stage("roadmap_authoring").required_init_fields
    assert "reference_artifact_files" in manifest.stage("roadmap_authoring").required_init_fields
    assert "reference_artifacts_content" not in manifest.stage("roadmap_authoring").required_init_fields
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
    bootstrap = manifest.stage("bootstrap")
    preflight = manifest.stage("preflight")
    artifact_discovery = manifest.stage("artifact_discovery")
    panel_stages = manifest.stage("panel_stages")
    final_adjudication = manifest.stage("final_adjudication")
    finalize = manifest.stage("finalize")

    assert manifest.workflow_id == "peer-review"
    assert manifest.stage_ids() == (
        "bootstrap",
        "preflight",
        "artifact_discovery",
        "panel_stages",
        "final_adjudication",
        "finalize",
    )
    assert "workflows/peer-review/bootstrap.md" in bootstrap.loaded_authorities
    assert "references/publication/publication-review-round-artifacts.md" in bootstrap.must_not_eager_load
    assert "references/publication/peer-review-panel.md" in bootstrap.must_not_eager_load
    assert "references/publication/peer-review-reliability.md" in bootstrap.must_not_eager_load
    assert "references/publication/stage-recovery-gate.md" in bootstrap.must_not_eager_load
    assert "templates/paper/paper-config-schema.md" in bootstrap.must_not_eager_load
    assert "review_target_input" in bootstrap.required_init_fields
    assert "review_target_mode" in bootstrap.required_init_fields
    assert "review_target_mode_reason" in bootstrap.required_init_fields
    assert "resolved_review_target" in bootstrap.required_init_fields
    assert "resolved_review_root" in bootstrap.required_init_fields
    assert "publication_subject_slug" in bootstrap.required_init_fields
    assert "publication_lane_kind" in bootstrap.required_init_fields
    assert "publication_lane_owner" in bootstrap.required_init_fields
    assert "managed_publication_root" in bootstrap.required_init_fields
    assert "selected_publication_root" in bootstrap.required_init_fields
    assert "selected_review_root" in bootstrap.required_init_fields
    assert preflight.loaded_authorities == (
        "workflows/peer-review/preflight.md",
        "templates/paper/publication-manuscript-root-preflight.md",
    )
    preflight_conditionals = {
        authority for conditional in preflight.conditional_authorities for authority in conditional.authorities
    }
    assert "references/publication/peer-review-reliability.md" in preflight_conditionals
    assert "templates/paper/paper-config-schema.md" in preflight_conditionals
    assert "templates/paper/artifact-manifest-schema.md" in preflight_conditionals
    assert "templates/paper/bibliography-audit-schema.md" in preflight_conditionals
    assert "templates/paper/reproducibility-manifest.md" in preflight_conditionals
    assert "references/publication/peer-review-reliability.md" in preflight.must_not_eager_load
    assert "templates/paper/paper-config-schema.md" in preflight.must_not_eager_load
    assert "review_target_input" in preflight.required_init_fields
    assert "review_target_mode" in preflight.required_init_fields
    assert "review_target_mode_reason" in preflight.required_init_fields
    assert "resolved_review_target" in preflight.required_init_fields
    assert "resolved_review_root" in preflight.required_init_fields
    assert artifact_discovery.loaded_authorities == (
        "workflows/peer-review/artifact-discovery.md",
        "references/publication/publication-review-round-artifacts.md",
        "references/publication/publication-response-artifacts.md",
    )
    assert "review_target_input" in artifact_discovery.required_init_fields
    assert "review_target_mode" in artifact_discovery.required_init_fields
    assert "resolved_review_target" in artifact_discovery.required_init_fields
    assert panel_stages.loaded_authorities == (
        "workflows/peer-review/panel-stages.md",
        "references/publication/peer-review-panel.md",
    )
    panel_conditionals = {
        authority for conditional in panel_stages.conditional_authorities for authority in conditional.authorities
    }
    assert "references/publication/peer-review-panel-playbook.md" in panel_conditionals
    panel_conditionals = {
        authority for conditional in panel_stages.conditional_authorities for authority in conditional.authorities
    }
    assert "references/publication/stage-recovery-gate.md" in panel_conditionals
    assert "references/verification/core/proof-redteam-workflow-gate.md" in panel_conditionals
    assert "references/verification/core/proof-redteam-protocol.md" in panel_conditionals
    assert "templates/proof-redteam-schema.md" in panel_conditionals
    assert "references/publication/stage-recovery-gate.md" in panel_stages.must_not_eager_load
    assert "templates/proof-redteam-schema.md" in panel_stages.must_not_eager_load
    assert "GPD/review/CLAIMS{round_suffix}.json" in panel_stages.writes_allowed
    assert "GPD/publication/{subject_slug}/review/CLAIMS{round_suffix}.json" in panel_stages.writes_allowed
    assert "GPD/publication/{subject_slug}/review/PROOF-REDTEAM{round_suffix}.md" in panel_stages.writes_allowed
    assert final_adjudication.loaded_authorities == (
        "workflows/peer-review/final-adjudication.md",
        "references/publication/publication-final-adjudication-boundary.md",
        "references/publication/stage-recovery-gate.md",
        "templates/paper/review-ledger-schema.md",
        "templates/paper/referee-decision-schema.md",
    )
    final_conditionals = {
        authority for conditional in final_adjudication.conditional_authorities for authority in conditional.authorities
    }
    assert "references/publication/peer-review-panel.md" in final_conditionals
    assert "references/publication/peer-review-panel.md" in final_adjudication.must_not_eager_load
    assert "review_target_input" in final_adjudication.required_init_fields
    assert "review_target_mode" in final_adjudication.required_init_fields
    assert "resolved_review_target" in final_adjudication.required_init_fields
    assert "GPD/review/REVIEW-LEDGER{round_suffix}.json" in final_adjudication.writes_allowed
    assert "GPD/publication/{subject_slug}/review/REVIEW-LEDGER{round_suffix}.json" in final_adjudication.writes_allowed
    assert "GPD/publication/{subject_slug}/REFEREE-REPORT{round_suffix}.md" in final_adjudication.writes_allowed
    assert "selected_review_root" in finalize.required_init_fields


def test_known_init_fields_for_peer_review_include_publication_routing_and_review_target_state() -> None:
    known_init_fields = known_init_fields_for_workflow("peer-review")

    assert known_init_fields is not None
    assert "review_target_input" in known_init_fields
    assert "review_target_mode" in known_init_fields
    assert "review_target_mode_reason" in known_init_fields
    assert "resolved_review_target" in known_init_fields
    assert "resolved_review_root" in known_init_fields
    assert "publication_subject_slug" in known_init_fields
    assert "publication_lane_kind" in known_init_fields
    assert "publication_lane_owner" in known_init_fields
    assert "managed_publication_root" in known_init_fields
    assert "selected_publication_root" in known_init_fields
    assert "selected_review_root" in known_init_fields


def test_known_init_fields_for_execute_phase_include_bootstrap_and_wave_context() -> None:
    known_init_fields = known_init_fields_for_workflow("execute-phase")

    assert known_init_fields is not None
    assert "executor_model" in known_init_fields
    assert "verifier_model" in known_init_fields
    assert "phase_found" in known_init_fields
    assert "plan_count" in known_init_fields
    assert "selected_protocol_bundle_ids" in known_init_fields
    assert "protocol_bundle_load_manifest" in known_init_fields
    assert "selected_task_overlay_ids" in known_init_fields
    assert "task_overlay_load_manifest" in known_init_fields
    assert "task_overlay_policy_summary" in known_init_fields
    assert "current_execution" in known_init_fields
    assert "verification_report_skeleton_bridge" in known_init_fields
    assert "verification_report_finalizer_bridge" in known_init_fields


def test_execute_phase_executor_dispatch_staged_init_includes_task_overlay_handles(tmp_path: Path) -> None:
    _setup_generic_staged_init_project(tmp_path)

    manifest = load_workflow_stage_manifest("execute-phase")
    stage = manifest.stage("executor_dispatch")
    payload = init_execute_phase(tmp_path, "1", stage="executor_dispatch")
    load_manifest = payload["task_overlay_load_manifest"]

    assert "selected_task_overlay_ids" in stage.required_init_fields
    assert "task_overlay_load_manifest" in stage.required_init_fields
    assert "task_overlay_policy_summary" in stage.required_init_fields
    assert payload["selected_task_overlay_ids"] == ["executor.bounded_segment"]
    assert isinstance(load_manifest, dict)
    assert load_manifest["selection_source"] == "execute-phase.executor_dispatch"
    assert load_manifest["role"] == "gpd-executor"
    assert load_manifest["selected_task_overlay_ids"] == ["executor.bounded_segment"]
    assert load_manifest["overlay_count"] == 1
    overlays = load_manifest["overlays"]
    assert isinstance(overlays, list)
    assert overlays[0]["path"] == TASK_OVERLAY_REFERENCE_PATH
    assert overlays[0]["portable_path"] == f"@{{GPD_INSTALL_DIR}}/{TASK_OVERLAY_REFERENCE_PATH}"
    assert overlays[0]["body_loaded"] is False
    assert "\n" not in payload["task_overlay_policy_summary"]
    assert set(payload) == set(stage.required_init_fields) | {"staged_loading"}


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
    assert "protocol_bundle_load_manifest" in manifest.stages[1].required_init_fields
    assert "reference_artifacts_content" in manifest.stages[2].required_init_fields
    assert "references/orchestration/artifact-surfacing.md" in manifest.stages[2].loaded_authorities
    assert manifest.staged_loading_payload("phase_bootstrap")["next_stages"] == ["wave_planning"]
    assert manifest.staged_loading_payload("wave_dispatch")["checkpoints"] == []


def test_arxiv_submission_stage_manifest_path_is_reserved_for_staged_loading() -> None:
    manifest_path = resolve_workflow_stage_manifest_path("arxiv-submission")

    assert manifest_path == NEW_PROJECT_STAGE_MANIFEST_PATH.parent / "arxiv-submission-stage-manifest.json"


def test_arxiv_submission_stage_manifest_can_be_loaded() -> None:
    manifest_path = resolve_workflow_stage_manifest_path("arxiv-submission")

    assert manifest_path.exists()

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
    bootstrap = manifest.stage("bootstrap")
    review_gate = manifest.stage("review_gate")
    package = manifest.stage("package")
    assert "references/publication/publication-bootstrap-preflight.md" in bootstrap.loaded_authorities
    assert "publication_subject_slug" in bootstrap.required_init_fields
    assert "publication_lane_kind" in bootstrap.required_init_fields
    assert "publication_lane_owner" in bootstrap.required_init_fields
    assert "managed_publication_root" in bootstrap.required_init_fields
    assert "selected_publication_root" in bootstrap.required_init_fields
    assert "selected_review_root" in bootstrap.required_init_fields
    assert "latest_response_round" in bootstrap.required_init_fields
    assert "latest_response_freshness_policy" in bootstrap.required_init_fields
    assert "latest_response_requires_fresh_review" in bootstrap.required_init_fields
    assert "latest_response_freshness" in bootstrap.required_init_fields
    assert "references/publication/publication-review-round-artifacts.md" in review_gate.loaded_authorities
    review_gate_conditionals = {
        authority for conditional in review_gate.conditional_authorities for authority in conditional.authorities
    }
    assert "references/publication/peer-review-reliability.md" not in review_gate.loaded_authorities
    assert "references/publication/peer-review-reliability.md" in review_gate_conditionals
    assert "references/publication/publication-response-writer-handoff.md" not in review_gate.loaded_authorities
    assert package.writes_allowed == ("GPD/publication/{subject_slug}/arxiv",)


def test_known_init_fields_for_arxiv_submission_include_publication_routing() -> None:
    known_init_fields = known_init_fields_for_workflow("arxiv-submission")

    assert known_init_fields is not None
    assert "project_root" in known_init_fields
    assert "publication_subject_slug" in known_init_fields
    assert "publication_lane_kind" in known_init_fields
    assert "publication_lane_owner" in known_init_fields
    assert "managed_publication_root" in known_init_fields
    assert "selected_publication_root" in known_init_fields
    assert "selected_review_root" in known_init_fields
    assert "latest_response_round" in known_init_fields
    assert "latest_response_freshness_policy" in known_init_fields
    assert "latest_response_requires_fresh_review" in known_init_fields
    assert "latest_response_freshness" in known_init_fields


@pytest.mark.parametrize(
    ("mutator", "message"),
    [
        (
            lambda payload: payload["stages"][0].__setitem__("loaded_authorities", ["/absolute/path.md"]),
            "normalized relative POSIX",
        ),
        (
            lambda payload: payload["stages"][0].__setitem__(
                "must_not_eager_load", ["references/research/does-not-exist.md"]
            ),
            "existing markdown file",
        ),
        (
            lambda payload: payload["stages"][0].__setitem__("allowed_tools", ["file_read", "not-a-tool"]),
            "unknown tool",
        ),
        (
            lambda payload: payload["stages"][0].__setitem__(
                "required_init_fields", ["researcher_model", "not-a-field"]
            ),
            "unknown field",
        ),
        (
            lambda payload: payload["stages"][0].__setitem__(
                "must_not_eager_load",
                [*payload["stages"][0]["must_not_eager_load"], "workflows/new-project/scope-intake.md"],
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
        (
            lambda payload: payload["stages"][1].__setitem__("writes_allowed", ["../escape.txt"]),
            "normalized relative POSIX path",
        ),
        (
            lambda payload: payload["stages"][0].__setitem__("init_spec_id", " "),
            "init_spec_id must be a non-empty string",
        ),
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


def test_validate_workflow_stage_manifest_payload_rejects_duplicate_must_not_eager_load_entries() -> None:
    payload = _workflow_payload("new-project")
    duplicate_authority = payload["stages"][0]["must_not_eager_load"][0]
    payload["stages"][0]["must_not_eager_load"] = [duplicate_authority, f" {duplicate_authority} "]

    with pytest.raises(
        ValueError,
        match=r"stages\[0\]\.must_not_eager_load must not contain duplicate entries",
    ):
        validate_workflow_stage_manifest_payload(payload)


def test_validate_workflow_stage_manifest_payload_rejects_unknown_next_stages_before_order_checks() -> None:
    payload = _workflow_payload("new-project")
    payload["stages"][0]["next_stages"] = ["does_not_exist"]
    payload["stages"][0]["order"] = 99

    with pytest.raises(ValueError, match="next_stages contains unknown stage id"):
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
