"""Assertions for shared workflow-stage manifest loading."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gpd.core import context as context_module
from gpd.core.context import (
    init_arxiv_submission,
    init_respond_to_referees,
    init_resume,
    init_sync_state,
    init_write_paper,
)
from gpd.core.workflow_staging import (
    EXECUTE_PHASE_STAGE_MANIFEST_PATH,
    LITERATURE_REVIEW_STAGE_MANIFEST_PATH,
    MAP_RESEARCH_STAGE_MANIFEST_PATH,
    NEW_PROJECT_STAGE_MANIFEST_PATH,
    PLAN_PHASE_STAGE_MANIFEST_PATH,
    QUICK_STAGE_MANIFEST_PATH,
    RESEARCH_PHASE_STAGE_MANIFEST_PATH,
    VERIFY_WORK_INIT_FIELDS,
    VERIFY_WORK_MCP_VERIFICATION_TOOLS,
    VERIFY_WORK_STAGE_ALLOWED_TOOLS,
    WORKFLOW_STAGE_MANIFEST_DIR,
    WORKFLOW_STAGE_MANIFEST_SUFFIX,
    WRITE_PAPER_MANAGED_INTAKE_ROOT,
    WRITE_PAPER_MANAGED_MANUSCRIPT_ROOT,
    invalidate_workflow_stage_manifest_cache,
    known_init_fields_for_workflow,
    load_workflow_stage_manifest,
    load_workflow_stage_manifest_from_path,
    resolve_workflow_stage_manifest_path,
    validate_workflow_stage_manifest_payload,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


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
    assert first.stage_ids() == ("scope_intake", "scope_approval", "post_scope")
    assert "references/shared/canonical-schema-discipline.md" in first.stages[0].must_not_eager_load
    assert first.stages[0].required_init_fields == (
        "researcher_model",
        "synthesizer_model",
        "commit_docs",
        "autonomy",
        "research_mode",
        "project_exists",
        "state_exists",
        "roadmap_exists",
        "recoverable_project_exists",
        "partial_project_exists",
        "project_recovery_status",
        "init_progress_exists",
        "init_progress_status",
        "init_progress_valid",
        "init_progress_corrupt",
        "init_progress_step",
        "init_progress_description",
        "init_progress_path",
        "has_research_map",
        "planning_exists",
        "has_research_files",
        "research_file_samples",
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
        "templates/state.md",
    )
    assert first.stages[2].must_not_eager_load == ()
    assert first.stages[2].writes_allowed == (
        "GPD/PROJECT.md",
        "GPD/REQUIREMENTS.md",
        "GPD/ROADMAP.md",
        "GPD/STATE.md",
        "GPD/state.json",
        "GPD/state.json.bak",
        "GPD/state.json.lock",
        "GPD/config.json",
        "GPD/CONVENTIONS.md",
        "GPD/init-progress.json",
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
    assert (
        "templates/contract-results-schema.md"
        in execute_phase_manifest.stage("aggregate_and_verify").loaded_authorities
    )
    assert "templates/calculation-log.md" in execute_phase_manifest.stage("aggregate_and_verify").loaded_authorities


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
    assert set(VERIFY_WORK_MCP_VERIFICATION_TOOLS).issubset(manifest.stages[2].allowed_tools)
    assert set(VERIFY_WORK_MCP_VERIFICATION_TOOLS).isdisjoint(manifest.stages[0].allowed_tools)
    assert set(VERIFY_WORK_MCP_VERIFICATION_TOOLS).isdisjoint(manifest.stages[1].allowed_tools)
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
    assert "contract_intake" in manifest.stages[4].required_init_fields
    assert "effective_reference_intake" in manifest.stages[4].required_init_fields
    assert "selected_protocol_bundle_ids" in manifest.stages[4].required_init_fields
    assert "protocol_bundle_context" in manifest.stages[4].required_init_fields
    assert "protocol_bundle_verifier_extensions" in manifest.stages[4].required_init_fields
    assert manifest.stages[4].loaded_authorities == (
        "workflows/verify-work.md",
        "templates/research-verification.md",
        "templates/verification-report.md",
        "templates/contract-results-schema.md",
        "references/shared/canonical-schema-discipline.md",
        "references/protocols/error-propagation-protocol.md",
    )


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


def test_verify_work_manifest_accepts_declared_mcp_verification_tools() -> None:
    manifest = validate_workflow_stage_manifest_payload(
        _workflow_payload("verify-work"),
        expected_workflow_id="verify-work",
        allowed_tools=VERIFY_WORK_STAGE_ALLOWED_TOOLS,
    )

    inventory = manifest.stage("inventory_build")
    assert set(VERIFY_WORK_MCP_VERIFICATION_TOOLS).issubset(inventory.allowed_tools)


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
    assert payload["eager_authorities"] == [
        "workflows/verify-work.md",
        "references/verification/meta/verification-independence.md",
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
        group_names = raw_stage.get("required_init_field_groups", [])
        if group_names:
            grouped_stage_count += 1
        assert isinstance(group_names, list)

        expanded_fields: list[str] = []
        for group_name in group_names:
            assert isinstance(group_name, str)
            expanded_fields.extend(groups[group_name])
        expanded_fields.extend(raw_stage.get("required_init_fields", []))

        assert manifest.stage(str(raw_stage["id"])).required_init_fields == tuple(expanded_fields)

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
    payload["stages"][0]["required_init_fields"] = [
        *payload["stages"][0]["required_init_fields"],
        "not_an_execute_phase_field",
    ]
    manifest_path = tmp_path / "custom-stage-manifest.json"
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="unknown field name"):
        load_workflow_stage_manifest_from_path(manifest_path)


def test_load_verify_work_manifest_from_path_uses_workflow_mcp_tool_defaults(tmp_path: Path) -> None:
    payload = _workflow_payload("verify-work")
    manifest_path = tmp_path / "verify-work-stage-manifest.json"
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    manifest = load_workflow_stage_manifest_from_path(manifest_path)

    assert manifest.workflow_id == "verify-work"
    assert set(VERIFY_WORK_MCP_VERIFICATION_TOOLS).issubset(manifest.stage("inventory_build").allowed_tools)


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


@pytest.mark.parametrize(
    ("workflow_id", "initializer"),
    [
        ("resume-work", init_resume),
        ("sync-state", init_sync_state),
        ("write-paper", init_write_paper),
    ],
)
def test_staged_init_fields_match_manifest_required_fields_for_resume_sync_and_write_paper(
    tmp_path: Path,
    workflow_id: str,
    initializer,
) -> None:
    manifest = validate_workflow_stage_manifest_payload(
        _workflow_payload(workflow_id),
        expected_workflow_id=workflow_id,
    )

    gpd_dir = tmp_path / "GPD"
    gpd_dir.mkdir()
    (gpd_dir / "config.json").write_text("{}", encoding="utf-8")
    (gpd_dir / "state.json").write_text("{}", encoding="utf-8")

    for stage_id in manifest.stage_ids():
        payload = initializer(tmp_path, stage=stage_id)
        stage = manifest.stage(stage_id)

        assert "staged_loading" in payload
        assert tuple(field for field in payload if field != "staged_loading") == stage.required_init_fields
        assert set(payload) == set(stage.required_init_fields) | {"staged_loading"}
        assert payload["staged_loading"]["workflow_id"] == workflow_id
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
    assert "workflows/write-paper.md" in bootstrap.loaded_authorities
    assert "references/publication/publication-review-round-artifacts.md" in bootstrap.must_not_eager_load
    assert "references/publication/publication-response-artifacts.md" in bootstrap.must_not_eager_load
    assert "references/publication/publication-pipeline-modes.md" in bootstrap.must_not_eager_load
    assert "references/publication/peer-review-panel.md" in bootstrap.must_not_eager_load
    assert "templates/paper/paper-config-schema.md" in bootstrap.must_not_eager_load
    assert bootstrap.writes_allowed == ()
    assert "contract_intake" in bootstrap.required_init_fields
    assert "effective_reference_intake" in bootstrap.required_init_fields
    assert "publication_subject_slug" in bootstrap.required_init_fields
    assert "publication_lane_kind" in bootstrap.required_init_fields
    assert "publication_lane_owner" in bootstrap.required_init_fields
    assert "selected_publication_root" in bootstrap.required_init_fields
    assert "publication_intake_root" in bootstrap.required_init_fields
    assert "managed_publication_root" in bootstrap.required_init_fields
    assert "managed_manuscript_root" in bootstrap.required_init_fields
    assert outline.loaded_authorities == (
        "workflows/write-paper.md",
        "references/publication/publication-pipeline-modes.md",
        "templates/paper/paper-config-schema.md",
        "templates/paper/artifact-manifest-schema.md",
    )
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
        "workflows/write-paper.md",
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
    assert consistency.writes_allowed == (
        WRITE_PAPER_MANAGED_MANUSCRIPT_ROOT,
        "GPD/references-status.json",
        "GPD/STATE.md",
        "GPD/state.json",
        "GPD/review",
        "GPD/CONVENTIONS.md",
    )
    assert publication_review.loaded_authorities == (
        "workflows/write-paper.md",
        "references/publication/publication-review-round-artifacts.md",
        "references/publication/publication-response-artifacts.md",
        "references/publication/peer-review-panel.md",
        "references/publication/peer-review-reliability.md",
        "templates/paper/review-ledger-schema.md",
        "templates/paper/referee-decision-schema.md",
    )
    assert publication_review.writes_allowed == (
        WRITE_PAPER_MANAGED_MANUSCRIPT_ROOT,
        "GPD/review",
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


def test_known_init_fields_for_write_paper_cover_bootstrap_and_deferred_publication_context() -> None:
    known_init_fields = known_init_fields_for_workflow("write-paper")

    assert known_init_fields is not None
    assert "commit_docs" in known_init_fields
    assert "project_root" in known_init_fields
    assert "project_contract_gate" in known_init_fields
    assert "project_contract_load_info" in known_init_fields
    assert "project_contract_validation" in known_init_fields
    assert "selected_protocol_bundle_ids" in known_init_fields
    assert "protocol_bundle_context" in known_init_fields
    assert "active_reference_context" in known_init_fields
    assert "contract_intake" in known_init_fields
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
    assert "reference_artifacts_content" in known_init_fields
    assert "state_content" in known_init_fields
    assert "requirements_content" in known_init_fields


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
    assert (
        "references/orchestration/runtime-delegation-note.md" in manifest.stage("phase_bootstrap").must_not_eager_load
    )
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
    assert "workflows/peer-review.md" in bootstrap.loaded_authorities
    assert "references/publication/publication-review-round-artifacts.md" in bootstrap.must_not_eager_load
    assert "references/publication/peer-review-panel.md" in bootstrap.must_not_eager_load
    assert "references/publication/peer-review-reliability.md" in bootstrap.must_not_eager_load
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
        "workflows/peer-review.md",
        "templates/paper/publication-manuscript-root-preflight.md",
        "references/publication/peer-review-reliability.md",
        "templates/paper/paper-config-schema.md",
        "templates/paper/artifact-manifest-schema.md",
        "templates/paper/bibliography-audit-schema.md",
        "templates/paper/reproducibility-manifest.md",
    )
    assert "review_target_input" in preflight.required_init_fields
    assert "review_target_mode" in preflight.required_init_fields
    assert "review_target_mode_reason" in preflight.required_init_fields
    assert "resolved_review_target" in preflight.required_init_fields
    assert "resolved_review_root" in preflight.required_init_fields
    assert artifact_discovery.loaded_authorities == (
        "workflows/peer-review.md",
        "references/publication/publication-review-round-artifacts.md",
        "references/publication/publication-response-artifacts.md",
    )
    assert "review_target_input" in artifact_discovery.required_init_fields
    assert "review_target_mode" in artifact_discovery.required_init_fields
    assert "resolved_review_target" in artifact_discovery.required_init_fields
    assert panel_stages.loaded_authorities == (
        "workflows/peer-review.md",
        "references/publication/peer-review-panel.md",
    )
    assert "GPD/review/CLAIMS{round_suffix}.json" in panel_stages.writes_allowed
    assert "GPD/publication/{subject_slug}/review/CLAIMS{round_suffix}.json" in panel_stages.writes_allowed
    assert "GPD/publication/{subject_slug}/review/PROOF-REDTEAM{round_suffix}.md" in panel_stages.writes_allowed
    assert final_adjudication.loaded_authorities == (
        "workflows/peer-review.md",
        "references/publication/peer-review-panel.md",
        "templates/paper/review-ledger-schema.md",
        "templates/paper/referee-decision-schema.md",
    )
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
    assert "references/publication/peer-review-reliability.md" in review_gate.loaded_authorities
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
        (
            lambda payload: payload["stages"][1].__setitem__("writes_allowed", ["../escape.txt"]),
            "normalized relative POSIX path",
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
