"""Shared workflow-stage manifest loading and validation."""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from functools import cache
from pathlib import Path, PurePosixPath

from gpd.adapters.tool_names import CANONICAL_TOOL_NAMES, canonical
from gpd.core.staged_context_fields import (
    ARXIV_SUBMISSION_BOOTSTRAP_FIELDS,
    ARXIV_SUBMISSION_SNAPSHOT_FIELDS,
    EXECUTE_PHASE_EXECUTION_RUNTIME_FIELDS,
    EXECUTE_PHASE_REFERENCE_RUNTIME_FIELDS,
    EXECUTE_PHASE_SCHEMA_BRIDGE_FIELDS,
    EXECUTE_PHASE_STATE_MEMORY_FIELDS,
    EXECUTE_PHASE_STRUCTURED_STATE_FIELDS,
    EXECUTE_PHASE_TASK_OVERLAY_FIELDS,
    NEW_MILESTONE_FILE_CONTENT_FIELDS,
    NEW_MILESTONE_REFERENCE_RUNTIME_FIELDS,
    PLAN_PHASE_CONTRACT_GATE_FIELDS,
    PLAN_PHASE_FILE_CONTENT_FIELDS,
    PLAN_PHASE_REFERENCE_RUNTIME_FIELDS,
    PLAN_PHASE_STATE_MEMORY_FIELDS,
    PLAN_PHASE_STRUCTURED_STATE_FIELDS,
    PROJECT_CONTRACT_GATE_FIELDS,
    PUBLICATION_REVIEW_SNAPSHOT_FIELDS,
    QUICK_CONTRACT_GATE_FIELDS,
    QUICK_REFERENCE_RUNTIME_FIELDS,
    RESEARCH_PHASE_FILE_CONTENT_FIELDS,
    RESUME_FILE_CONTENT_FIELDS,
    RESUME_REFERENCE_RUNTIME_FIELDS,
    STAGED_BODY_FIELDS,
    STAGED_REFERENCE_HANDLE_STATUS_FIELDS,
    STAGED_REFERENCE_RENDERED_CONTEXT_FIELDS,
    STAGED_REFERENCE_RUNTIME_FIELDS,
    STATE_MEMORY_FIELDS,
    STRUCTURED_STATE_FIELDS,
    SYNC_STATE_FILE_CONTENT_FIELDS,
    SYNC_STATE_STRUCTURED_STATE_FIELDS,
    VERIFY_WORK_CONTRACT_GATE_FIELDS,
    VERIFY_WORK_REFERENCE_RUNTIME_FIELDS,
    VERIFY_WORK_SCHEMA_BRIDGE_FIELDS,
    VERIFY_WORK_STATE_MEMORY_FIELDS,
    VERIFY_WORK_STRUCTURED_STATE_FIELDS,
    WRITE_PAPER_FILE_CONTENT_FIELDS,
    WRITE_PAPER_PUBLICATION_BOOTSTRAP_FIELDS,
    WRITE_PAPER_REFERENCE_RUNTIME_FIELDS,
)
from gpd.core.workflow_manifest_compaction import canonicalize_workflow_stage_manifest_payload
from gpd.specs import SPECS_DIR

WORKFLOW_STAGE_MANIFEST_DIR = SPECS_DIR / "workflows"
WORKFLOW_STAGE_MANIFEST_SUFFIX = "-stage-manifest.json"
NEW_PROJECT_STAGE_MANIFEST_PATH = WORKFLOW_STAGE_MANIFEST_DIR / f"new-project{WORKFLOW_STAGE_MANIFEST_SUFFIX}"
NEW_MILESTONE_STAGE_MANIFEST_PATH = WORKFLOW_STAGE_MANIFEST_DIR / f"new-milestone{WORKFLOW_STAGE_MANIFEST_SUFFIX}"
EXECUTE_PHASE_STAGE_MANIFEST_PATH = WORKFLOW_STAGE_MANIFEST_DIR / f"execute-phase{WORKFLOW_STAGE_MANIFEST_SUFFIX}"
PLAN_PHASE_STAGE_MANIFEST_PATH = WORKFLOW_STAGE_MANIFEST_DIR / f"plan-phase{WORKFLOW_STAGE_MANIFEST_SUFFIX}"
QUICK_STAGE_MANIFEST_PATH = WORKFLOW_STAGE_MANIFEST_DIR / f"quick{WORKFLOW_STAGE_MANIFEST_SUFFIX}"
LITERATURE_REVIEW_STAGE_MANIFEST_PATH = (
    WORKFLOW_STAGE_MANIFEST_DIR / f"literature-review{WORKFLOW_STAGE_MANIFEST_SUFFIX}"
)
RESEARCH_PHASE_STAGE_MANIFEST_PATH = WORKFLOW_STAGE_MANIFEST_DIR / f"research-phase{WORKFLOW_STAGE_MANIFEST_SUFFIX}"
MAP_RESEARCH_STAGE_MANIFEST_PATH = WORKFLOW_STAGE_MANIFEST_DIR / f"map-research{WORKFLOW_STAGE_MANIFEST_SUFFIX}"
AUTONOMOUS_STAGE_MANIFEST_PATH = WORKFLOW_STAGE_MANIFEST_DIR / f"autonomous{WORKFLOW_STAGE_MANIFEST_SUFFIX}"
WRITE_PAPER_MANAGED_MANUSCRIPT_ROOT = "GPD/publication/{subject_slug}/manuscript"
WRITE_PAPER_MANAGED_INTAKE_ROOT = "GPD/publication/{subject_slug}/intake"
RESUME_WORK_INIT_FIELDS = frozenset(
    {
        "workspace_root",
        "project_root",
        "project_root_source",
        "project_root_auto_selected",
        "project_reentry_mode",
        "project_reentry_requires_selection",
        "project_reentry_selected_candidate",
        "project_reentry_candidates",
        "workspace_state_exists",
        "workspace_roadmap_exists",
        "workspace_project_exists",
        "workspace_planning_exists",
        "state_exists",
        "state_json_backup_exists",
        "roadmap_exists",
        "project_exists",
        "planning_exists",
        "has_interrupted_agent",
        "interrupted_agent_id",
        "commit_docs",
        "autonomy",
        "review_cadence",
        "research_mode",
        "resume_surface_schema_version",
        "active_bounded_segment",
        "derived_execution_head_resume_file",
        "active_resume_kind",
        "active_resume_origin",
        "active_resume_pointer",
        "active_resume_result",
        "resume_candidates",
        *EXECUTE_PHASE_EXECUTION_RUNTIME_FIELDS,
        *PROJECT_CONTRACT_GATE_FIELDS,
        *RESUME_REFERENCE_RUNTIME_FIELDS,
        *STRUCTURED_STATE_FIELDS,
        *STATE_MEMORY_FIELDS,
        *RESUME_FILE_CONTENT_FIELDS,
        "platform",
    }
)
SYNC_STATE_INIT_FIELDS = frozenset(
    {
        "workspace_root",
        "project_root",
        "project_root_source",
        "project_root_auto_selected",
        "init_root_policy",
        "project_reentry_mode",
        "project_reentry_guidance",
        "state_md_exists",
        "state_json_exists",
        "state_json_backup_exists",
        "state_recovery_guidance",
        *SYNC_STATE_FILE_CONTENT_FIELDS,
        *SYNC_STATE_STRUCTURED_STATE_FIELDS,
        *PROJECT_CONTRACT_GATE_FIELDS,
        "platform",
    }
)
NEW_PROJECT_INIT_FIELDS = frozenset(
    {
        "researcher_model",
        "synthesizer_model",
        "roadmapper_model",
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
        *PROJECT_CONTRACT_GATE_FIELDS,
    }
)
NEW_MILESTONE_INIT_FIELDS = frozenset(
    {
        "researcher_model",
        "synthesizer_model",
        "roadmapper_model",
        "commit_docs",
        "autonomy",
        "init_root_policy",
        "research_mode",
        "research_enabled",
        "current_milestone",
        "current_milestone_name",
        "project_exists",
        "roadmap_exists",
        "state_exists",
        *PROJECT_CONTRACT_GATE_FIELDS,
        *NEW_MILESTONE_REFERENCE_RUNTIME_FIELDS,
        *STATE_MEMORY_FIELDS,
        *NEW_MILESTONE_FILE_CONTENT_FIELDS,
        "platform",
    }
)
EXECUTE_PHASE_INIT_FIELDS = frozenset(
    {
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
        *PROJECT_CONTRACT_GATE_FIELDS,
        *EXECUTE_PHASE_REFERENCE_RUNTIME_FIELDS,
        *EXECUTE_PHASE_STRUCTURED_STATE_FIELDS,
        *EXECUTE_PHASE_STATE_MEMORY_FIELDS,
        *EXECUTE_PHASE_TASK_OVERLAY_FIELDS,
        *EXECUTE_PHASE_EXECUTION_RUNTIME_FIELDS,
        *EXECUTE_PHASE_SCHEMA_BRIDGE_FIELDS,
        "platform",
    }
)
PLAN_PHASE_BASE_INIT_FIELDS = frozenset(
    {
        "researcher_model",
        "planner_model",
        "checker_model",
        "research_enabled",
        "plan_checker_enabled",
        "commit_docs",
        "autonomy",
        "research_mode",
        "phase_found",
        "phase_dir",
        "phase_number",
        "phase_name",
        "phase_slug",
        "padded_phase",
        "has_research",
        "has_context",
        "has_plans",
        "plan_count",
        "planning_exists",
        "roadmap_exists",
        "platform",
    }
)
PLAN_PHASE_INIT_FIELDS = frozenset(
    {
        *PLAN_PHASE_BASE_INIT_FIELDS,
        *PLAN_PHASE_CONTRACT_GATE_FIELDS,
        *PLAN_PHASE_REFERENCE_RUNTIME_FIELDS,
        *PLAN_PHASE_STRUCTURED_STATE_FIELDS,
        *PLAN_PHASE_STATE_MEMORY_FIELDS,
        *PLAN_PHASE_FILE_CONTENT_FIELDS,
    }
)
QUICK_BASE_INIT_FIELDS = frozenset(
    {
        "planner_model",
        "executor_model",
        "commit_docs",
        "autonomy",
        "research_mode",
        "next_num",
        "slug",
        "description",
        "date",
        "timestamp",
        "quick_dir",
        "task_dir",
        "roadmap_exists",
        "project_exists",
        "planning_exists",
        "platform",
    }
)
QUICK_INIT_FIELDS = frozenset(
    {
        *QUICK_BASE_INIT_FIELDS,
        *QUICK_CONTRACT_GATE_FIELDS,
        *QUICK_REFERENCE_RUNTIME_FIELDS,
    }
)
LITERATURE_REVIEW_INIT_FIELDS = frozenset(
    {
        "commit_docs",
        "project_root",
        "state_exists",
        "project_exists",
        "roadmap_exists",
        "topic",
        "slug",
        "research_mode",
        "autonomy",
        "platform",
        *PROJECT_CONTRACT_GATE_FIELDS,
        *STAGED_REFERENCE_RUNTIME_FIELDS,
    }
)
RESEARCH_PHASE_INIT_FIELDS = frozenset(
    {
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
        "phase_found",
        "phase_dir",
        "phase_number",
        "phase_name",
        "phase_slug",
        "padded_phase",
        "plans",
        "summaries",
        "incomplete_plans",
        "plan_count",
        "incomplete_count",
        "has_research",
        "has_context",
        "has_plans",
        "has_verification",
        "has_validation",
        "state_exists",
        "roadmap_exists",
        "planning_exists",
        *PROJECT_CONTRACT_GATE_FIELDS,
        *STAGED_REFERENCE_RUNTIME_FIELDS,
        *STRUCTURED_STATE_FIELDS,
        *STATE_MEMORY_FIELDS,
        *EXECUTE_PHASE_EXECUTION_RUNTIME_FIELDS,
        "platform",
        *RESEARCH_PHASE_FILE_CONTENT_FIELDS,
    }
)
MAP_RESEARCH_INIT_FIELDS = frozenset(
    {
        "mapper_model",
        "workspace_root",
        "project_root",
        "project_root_source",
        "project_root_auto_selected",
        "commit_docs",
        "autonomy",
        "research_mode",
        "map_focus",
        "map_focus_provided",
        "parallelization",
        "research_map_dir",
        "research_map_dir_absolute",
        "existing_maps",
        "has_maps",
        "planning_exists",
        "research_map_dir_exists",
        "platform",
        *PROJECT_CONTRACT_GATE_FIELDS,
        *STAGED_REFERENCE_RUNTIME_FIELDS,
    }
)
_READ_WRITE_SEARCH_TOOLS = frozenset(
    {
        "file_read",
        "file_write",
        "find_files",
        "search_files",
        "shell",
    }
)
_READ_WRITE_SEARCH_TASK_TOOLS = frozenset(
    {
        *_READ_WRITE_SEARCH_TOOLS,
        "task",
    }
)
_ASK_READ_SHELL_TASK_TOOLS = frozenset(
    {
        "ask_user",
        "file_read",
        "shell",
        "task",
    }
)
_ASK_READ_WRITE_SHELL_TASK_TOOLS = frozenset(
    {
        "ask_user",
        "file_read",
        "file_write",
        "shell",
        "task",
    }
)
_ASK_READ_SEARCH_TASK_TOOLS = frozenset(
    {
        "ask_user",
        "file_read",
        "find_files",
        "search_files",
        "shell",
        "task",
    }
)
_ASK_READ_WRITE_SEARCH_TASK_TOOLS = frozenset(
    {
        *_READ_WRITE_SEARCH_TASK_TOOLS,
        "ask_user",
    }
)
_ASK_FULL_FILE_TASK_TOOLS = frozenset(
    {
        *_ASK_READ_WRITE_SEARCH_TASK_TOOLS,
        "file_edit",
    }
)
_PLAN_PHASE_STAGE_ALLOWED_TOOLS = frozenset(
    {
        *_READ_WRITE_SEARCH_TASK_TOOLS,
        "web_fetch",
    }
)
_LITERATURE_REVIEW_STAGE_ALLOWED_TOOLS = frozenset(
    {
        *_ASK_READ_SEARCH_TASK_TOOLS,
        "web_fetch",
        "web_search",
    }
)
_PEER_REVIEW_STAGE_ALLOWED_TOOLS = frozenset(
    {
        *_ASK_READ_WRITE_SEARCH_TASK_TOOLS,
        "web_search",
    }
)
_WRITE_PAPER_STAGE_ALLOWED_TOOLS = frozenset(
    {
        *_ASK_FULL_FILE_TASK_TOOLS,
        "web_search",
    }
)
VERIFY_WORK_MCP_VERIFICATION_TOOLS = frozenset(
    {
        "mcp__gpd_verification__get_bundle_checklist",
        "mcp__gpd_verification__suggest_contract_checks",
        "mcp__gpd_verification__run_contract_check",
    }
)
VERIFY_WORK_STAGE_ALLOWED_TOOLS = frozenset(
    {
        "ask_user",
        "file_read",
        "file_edit",
        "file_write",
        "find_files",
        "search_files",
        "shell",
        "task",
        *VERIFY_WORK_MCP_VERIFICATION_TOOLS,
    }
)
VERIFY_WORK_BASE_INIT_FIELDS = frozenset(
    {
        "planner_model",
        "checker_model",
        "verifier_model",
        "commit_docs",
        "autonomy",
        "research_mode",
        "project_root",
        "phase_found",
        "phase_dir",
        "phase_dir_abs",
        "phase_number",
        "phase_name",
        "has_verification",
        "has_validation",
        "active_verification_sessions",
        "verification_report_path",
        "verification_report_status",
        "verification_session_status",
        "verification_report_status_payload",
        "phase_proof_review_status",
        "platform",
    }
)
VERIFY_WORK_INIT_FIELDS = frozenset(
    {
        *VERIFY_WORK_BASE_INIT_FIELDS,
        *VERIFY_WORK_CONTRACT_GATE_FIELDS,
        *VERIFY_WORK_REFERENCE_RUNTIME_FIELDS,
        *VERIFY_WORK_STRUCTURED_STATE_FIELDS,
        *VERIFY_WORK_STATE_MEMORY_FIELDS,
        *VERIFY_WORK_SCHEMA_BRIDGE_FIELDS,
    }
)
_DEFAULT_ALLOWED_TOOLS_BY_WORKFLOW = {
    "arxiv-submission": _READ_WRITE_SEARCH_TASK_TOOLS,
    "autonomous": _ASK_READ_SHELL_TASK_TOOLS,
    "build-persona": _ASK_READ_WRITE_SEARCH_TASK_TOOLS,
    "execute-phase": _ASK_FULL_FILE_TASK_TOOLS,
    "literature-review": _LITERATURE_REVIEW_STAGE_ALLOWED_TOOLS,
    "map-research": _ASK_READ_WRITE_SEARCH_TASK_TOOLS,
    "new-milestone": _ASK_READ_WRITE_SHELL_TASK_TOOLS,
    "new-project": _ASK_READ_WRITE_SHELL_TASK_TOOLS,
    "peer-review": _PEER_REVIEW_STAGE_ALLOWED_TOOLS,
    "plan-phase": _PLAN_PHASE_STAGE_ALLOWED_TOOLS,
    "quick": _ASK_READ_WRITE_SEARCH_TASK_TOOLS,
    "research-phase": _ASK_READ_SHELL_TASK_TOOLS,
    "respond-to-referees": _ASK_FULL_FILE_TASK_TOOLS,
    "resume-work": frozenset({"ask_user", "file_read", "file_write", "shell"}),
    "sync-state": _READ_WRITE_SEARCH_TOOLS,
    "verify-work": VERIFY_WORK_STAGE_ALLOWED_TOOLS,
    "write-paper": _WRITE_PAPER_STAGE_ALLOWED_TOOLS,
}
WRITE_PAPER_INIT_FIELDS = frozenset(
    {
        "commit_docs",
        "project_root",
        "state_exists",
        "project_exists",
        "autonomy",
        "research_mode",
        "write_paper_argument_input",
        *PROJECT_CONTRACT_GATE_FIELDS,
        *WRITE_PAPER_PUBLICATION_BOOTSTRAP_FIELDS,
        *WRITE_PAPER_REFERENCE_RUNTIME_FIELDS,
        *STATE_MEMORY_FIELDS,
        *WRITE_PAPER_FILE_CONTENT_FIELDS,
        "platform",
    }
)
PEER_REVIEW_INIT_FIELDS = frozenset(
    {
        "project_exists",
        "project_root",
        "state_exists",
        "commit_docs",
        "autonomy",
        "research_mode",
        "response_intake_input",
        "review_target_input",
        "review_target_mode",
        "review_target_mode_reason",
        "resolved_review_target",
        "resolved_review_root",
        *PROJECT_CONTRACT_GATE_FIELDS,
        *WRITE_PAPER_REFERENCE_RUNTIME_FIELDS,
        *PUBLICATION_REVIEW_SNAPSHOT_FIELDS,
        "platform",
    }
)
ARXIV_SUBMISSION_INIT_FIELDS = frozenset(
    {
        *ARXIV_SUBMISSION_BOOTSTRAP_FIELDS,
        *ARXIV_SUBMISSION_SNAPSHOT_FIELDS,
    }
)
AUTONOMOUS_INIT_FIELDS = frozenset(
    {
        "project_root",
        "autonomous_argument_input",
        "autonomous_from_phase",
        "commit_docs",
        "autonomy",
        "research_mode",
        "review_cadence",
        "model_profile",
        "platform",
        "milestone_version",
        "milestone_name",
        "milestone_slug",
        "phase_count",
        "completed_phases",
        "all_phases_complete",
        "project_exists",
        "roadmap_exists",
        "state_exists",
        "phases_dir_exists",
        "autonomous_phase_plan",
        "autonomous_completed_phase_numbers",
        "autonomous_completed_phase_verification_statuses",
        "autonomous_incomplete_phase_count",
        "autonomous_current_phase_number",
        "autonomous_current_phase_name",
        "autonomous_current_phase_goal",
        "autonomous_current_phase_success_criteria",
        "phase_found",
        "phase_dir",
        "phase_number",
        "phase_name",
        "phase_slug",
        "padded_phase",
        "has_context",
        "has_plans",
        "plan_count",
        "verification_report_status",
        "verification_report_status_payload",
        "phase_proof_review_status",
    }
)
_DEFAULT_KNOWN_INIT_FIELDS_BY_WORKFLOW = {
    "autonomous": AUTONOMOUS_INIT_FIELDS,
    "resume-work": RESUME_WORK_INIT_FIELDS,
    "sync-state": SYNC_STATE_INIT_FIELDS,
    "new-project": NEW_PROJECT_INIT_FIELDS,
    "new-milestone": NEW_MILESTONE_INIT_FIELDS,
    "literature-review": LITERATURE_REVIEW_INIT_FIELDS,
    "research-phase": RESEARCH_PHASE_INIT_FIELDS,
    "map-research": MAP_RESEARCH_INIT_FIELDS,
    "peer-review": PEER_REVIEW_INIT_FIELDS,
    "respond-to-referees": PEER_REVIEW_INIT_FIELDS,
    "arxiv-submission": ARXIV_SUBMISSION_INIT_FIELDS,
    "plan-phase": PLAN_PHASE_INIT_FIELDS,
    "quick": QUICK_INIT_FIELDS,
    "verify-work": VERIFY_WORK_INIT_FIELDS,
    "write-paper": WRITE_PAPER_INIT_FIELDS,
    "execute-phase": EXECUTE_PHASE_INIT_FIELDS,
}
_MANIFEST_DERIVED_KNOWN_INIT_FIELD_WORKFLOWS = frozenset(
    {
        "arxiv-submission",
        "autonomous",
        "build-persona",
        "execute-phase",
        "literature-review",
        "map-research",
        "new-milestone",
        "new-project",
        "peer-review",
        "plan-phase",
        "quick",
        "research-phase",
        "respond-to-referees",
        "resume-work",
        "sync-state",
        "verify-work",
        "write-paper",
    }
)

_ALLOWED_TOP_LEVEL_KEYS = frozenset(
    {
        "schema_version",
        "workflow_id",
        "prompt_usage",
        "required_init_field_groups",
        "stages",
    }
)
_REQUIRED_TOP_LEVEL_KEYS = frozenset({"schema_version", "workflow_id", "stages"})
_ALLOWED_PROMPT_USAGE_VALUES = frozenset({"staged_init", "metadata_only"})
_ALLOWED_STAGE_KEYS = frozenset(
    {
        "id",
        "order",
        "purpose",
        "init_spec_id",
        "mode_paths",
        "required_init_field_groups",
        "required_init_fields",
        "loaded_authorities",
        "conditional_authorities",
        "must_not_eager_load",
        "allowed_tools",
        "writes_allowed",
        "produced_state",
        "next_stages",
        "checkpoints",
    }
)
_OPTIONAL_STAGE_KEYS = frozenset({"init_spec_id", "required_init_field_groups", "required_init_fields"})
_REQUIRED_STAGE_KEYS = _ALLOWED_STAGE_KEYS - _OPTIONAL_STAGE_KEYS
_ALLOWED_CONDITIONAL_KEYS = frozenset({"when", "authorities"})
_AUTHORITY_ROOTS = ("workflows/", "references/", "templates/")
_STAGE_MANIFEST_PAYLOAD_FIELDS = (
    "mode_paths",
    "required_init_fields",
    "loaded_authorities",
    "conditional_authorities",
    "must_not_eager_load",
    "allowed_tools",
    "writes_allowed",
    "produced_state",
    "next_stages",
    "checkpoints",
)
_STAGED_LOADING_PAYLOAD_FIELDS = (
    "required_init_fields",
    "mode_paths",
    "loaded_authorities",
    "conditional_authorities",
    "must_not_eager_load",
    "allowed_tools",
    "writes_allowed",
    "produced_state",
    "next_stages",
    "checkpoints",
)
_BODY_FIELD_SUFFIX = "_content"
_HANDLE_STATUS_SUFFIXES = (
    "_count",
    "_counts",
    "_file",
    "_files",
    "_ids",
    "_load_info",
    "_manifest",
    "_status",
    "_statuses",
    "_summary",
    "_warnings",
)
_PROTOCOL_BUNDLE_HANDLE_FIELDS = frozenset({"selected_protocol_bundle_ids", "protocol_bundle_load_manifest"})


def render_staged_field_access_instruction(
    workflow_id: str,
    stage: WorkflowStage,
    *,
    init_reference: str = "<INIT>",
) -> str:
    """Render the compact active-stage field-access instruction."""

    raw_command = f"gpd --raw stage field-access {workflow_id} --stage {stage.id} --style instruction"
    required_marker = f"`{init_reference}.staged_loading.required_init_fields`"
    parts = [
        (
            f"Field access ({workflow_id}.{stage.id}): run `{raw_command}` for the selected-field "
            f"inventory or aliases; read only selected init keys listed in {required_marker}. "
            "Selected fields stay structured there, not repeated as prose. "
            "Treat unlisted init/body fields as unavailable for this active stage. "
            "Reject stale/older init payloads and shell variables from another stage."
        )
    ]

    body_fields = _selected_body_fields(stage.required_init_fields)
    handle_status_fields = _selected_handle_status_fields(stage.required_init_fields)
    if body_fields:
        parts.append(
            "Body fields: selected body fields are target-scoped "
            f"({', '.join(body_fields)}); read them only after choosing the concrete section, issue, "
            "artifact, gap, handoff, or reference target; use handles/status/load manifests first."
        )
    elif handle_status_fields:
        parts.append(
            "Body fields: no staged body fields are selected; selected handle/status fields are handles "
            "only, so use handles/status/load manifests first."
        )
    else:
        parts.append("Body fields: no staged body fields are selected for this stage.")

    rendered_context_fields = _selected_rendered_context_fields(stage.required_init_fields)
    if rendered_context_fields:
        parts.append(
            "Rendered context fields selected for this stage "
            f"({', '.join(rendered_context_fields)}) do not make unselected body fields available."
        )
    if _PROTOCOL_BUNDLE_HANDLE_FIELDS.intersection(stage.required_init_fields):
        parts.append(
            "Protocol bundles: selected IDs/load manifests are handles until needed; for domain judgments, "
            "open only relevant verification_domains/execution_guides portable_path entries from "
            "protocol_bundle_load_manifest; keep unselected assets absent."
        )
    return " ".join(parts)


def _selected_body_fields(selected_fields: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(
        field for field in selected_fields if field in STAGED_BODY_FIELDS or field.endswith(_BODY_FIELD_SUFFIX)
    )


def _selected_handle_status_fields(selected_fields: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(
        field
        for field in selected_fields
        if field in STAGED_REFERENCE_HANDLE_STATUS_FIELDS or field.endswith(_HANDLE_STATUS_SUFFIXES)
    )


def _selected_rendered_context_fields(selected_fields: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(field for field in selected_fields if field in STAGED_REFERENCE_RENDERED_CONTEXT_FIELDS)


@dataclass(frozen=True, slots=True)
class WorkflowStageConditionalAuthority:
    when: str
    authorities: tuple[str, ...]

    def to_payload(self) -> dict[str, object]:
        return {
            "when": self.when,
            "authorities": list(self.authorities),
        }


@dataclass(frozen=True, slots=True)
class WorkflowStage:
    id: str
    order: int
    purpose: str
    mode_paths: tuple[str, ...]
    required_init_fields: tuple[str, ...]
    loaded_authorities: tuple[str, ...]
    conditional_authorities: tuple[WorkflowStageConditionalAuthority, ...]
    must_not_eager_load: tuple[str, ...]
    allowed_tools: tuple[str, ...]
    writes_allowed: tuple[str, ...]
    produced_state: tuple[str, ...]
    next_stages: tuple[str, ...]
    checkpoints: tuple[str, ...]
    init_spec_id: str | None = None

    def eager_authorities(self, *, selected_conditions: Iterable[str] = ()) -> tuple[str, ...]:
        selected = {condition for condition in selected_conditions if condition}
        combined: list[str] = []
        seen: set[str] = set()

        for authority in (*self.mode_paths, *self.loaded_authorities):
            if authority in seen:
                continue
            seen.add(authority)
            combined.append(authority)

        for conditional in self.conditional_authorities:
            if conditional.when not in selected:
                continue
            for authority in conditional.authorities:
                if authority in seen:
                    continue
                seen.add(authority)
                combined.append(authority)
        return tuple(combined)

    def _sequence_payload_fields(self, field_names: tuple[str, ...]) -> dict[str, object]:
        payload: dict[str, object] = {}
        for field_name in field_names:
            if field_name == "conditional_authorities":
                payload[field_name] = [entry.to_payload() for entry in self.conditional_authorities]
            else:
                payload[field_name] = list(getattr(self, field_name))
        return payload

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "id": self.id,
            "order": self.order,
            "purpose": self.purpose,
        }
        if self.init_spec_id is not None:
            payload["init_spec_id"] = self.init_spec_id
        payload.update(self._sequence_payload_fields(_STAGE_MANIFEST_PAYLOAD_FIELDS))
        return payload

    def to_staged_loading_payload(self, workflow_id: str) -> dict[str, object]:
        payload: dict[str, object] = {
            "workflow_id": workflow_id,
            "stage_id": self.id,
            "order": self.order,
            "required_init_fields": list(self.required_init_fields),
            "field_access_instruction": render_staged_field_access_instruction(workflow_id, self),
            **self._sequence_payload_fields(_STAGED_LOADING_PAYLOAD_FIELDS[1:3]),
            "eager_authorities": list(self.eager_authorities()),
        }
        if self.init_spec_id is not None:
            payload["init_spec_id"] = self.init_spec_id
        payload.update(self._sequence_payload_fields(_STAGED_LOADING_PAYLOAD_FIELDS[3:]))
        return payload


@dataclass(frozen=True, slots=True)
class WorkflowStageManifest:
    schema_version: int
    workflow_id: str
    stages: tuple[WorkflowStage, ...]
    prompt_usage: str = "staged_init"

    def stage_ids(self) -> tuple[str, ...]:
        return tuple(stage.id for stage in self.stages)

    def stage(self, stage_id: str) -> WorkflowStage:
        for stage in self.stages:
            if stage.id == stage_id:
                return stage
        raise KeyError(f"Unknown stage id {stage_id!r} for workflow {self.workflow_id!r}")

    def stage_by_id(self, stage_id: str) -> WorkflowStage:
        return self.stage(stage_id)

    def get_stage(self, stage_id: str) -> WorkflowStage:
        return self.stage(stage_id)

    def staged_loading_payload(self, stage_id: str) -> dict[str, object]:
        return self.stage(stage_id).to_staged_loading_payload(self.workflow_id)

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "schema_version": self.schema_version,
            "workflow_id": self.workflow_id,
            "stages": [stage.to_payload() for stage in self.stages],
        }
        if self.prompt_usage != "staged_init":
            payload["prompt_usage"] = self.prompt_usage
        return payload


def staged_loading_payload_contract_keys(manifest: WorkflowStageManifest) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return staged-loading keys required for every stage and keys used only sometimes."""

    payloads = tuple(stage.to_staged_loading_payload(manifest.workflow_id) for stage in manifest.stages)
    if not payloads:
        return (), ()

    required_key_set = set(payloads[0])
    for payload in payloads[1:]:
        required_key_set.intersection_update(payload)

    required_keys = tuple(key for key in payloads[0] if key in required_key_set)
    seen = set(required_keys)
    optional_keys: list[str] = []
    for payload in payloads:
        for key in payload:
            if key in seen:
                continue
            seen.add(key)
            optional_keys.append(key)
    return required_keys, tuple(optional_keys)


def staged_protocol_bundle_required_init_fields(manifest: WorkflowStageManifest) -> tuple[str, ...]:
    """Return protocol-bundle init fields selected by any stage in manifest order."""

    fields: list[str] = []
    seen: set[str] = set()
    for stage in manifest.stages:
        for field in stage.required_init_fields:
            if not _is_protocol_bundle_required_init_field(field) or field in seen:
                continue
            seen.add(field)
            fields.append(field)
    return tuple(fields)


def staged_ids_requiring_init_fields(
    manifest: WorkflowStageManifest,
    field_names: Iterable[str],
) -> tuple[str, ...]:
    """Return stage ids whose required init fields intersect *field_names*."""

    selected = set(field_names)
    if not selected:
        return ()
    return tuple(stage.id for stage in manifest.stages if selected.intersection(stage.required_init_fields))


def _is_protocol_bundle_required_init_field(field: str) -> bool:
    return field == "selected_protocol_bundle_ids" or field.startswith("protocol_bundle_")


def _require_string(raw: object, *, label: str) -> str:
    if not isinstance(raw, str):
        raise ValueError(f"{label} must be a non-empty string")
    value = raw.strip()
    if not value:
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _require_int(raw: object, *, label: str) -> int:
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise ValueError(f"{label} must be an integer")
    return raw


def _require_string_tuple(raw: object, *, label: str, allow_empty: bool = False) -> tuple[str, ...]:
    if not isinstance(raw, list):
        raise ValueError(f"{label} must be a list of non-empty strings")
    if not raw and not allow_empty:
        raise ValueError(f"{label} must be a non-empty list of non-empty strings")

    items: list[str] = []
    seen: set[str] = set()
    for entry in raw:
        if not isinstance(entry, str):
            raise ValueError(f"{label} entries must be non-empty strings")
        value = entry.strip()
        if not value:
            raise ValueError(f"{label} entries must be non-empty strings")
        if value in seen:
            raise ValueError(f"{label} must not contain duplicate entries")
        seen.add(value)
        items.append(value)
    return tuple(items)


def _normalize_workflow_id(raw: object) -> str:
    workflow_id = _require_string(raw, label="workflow_id")
    if "/" in workflow_id or "\\" in workflow_id:
        raise ValueError("workflow_id must be a simple workflow stem")
    return workflow_id


def resolve_workflow_stage_manifest_path(workflow_id: str) -> Path:
    workflow_slug = _normalize_workflow_id(workflow_id)
    return WORKFLOW_STAGE_MANIFEST_DIR / f"{workflow_slug}{WORKFLOW_STAGE_MANIFEST_SUFFIX}"


def _normalize_specs_root(specs_root: Path | None = None) -> Path:
    root = SPECS_DIR if specs_root is None else specs_root
    return root.expanduser().resolve(strict=False)


def _specs_root_cache_key(specs_root: Path | None = None) -> str:
    return _normalize_specs_root(specs_root).as_posix()


def _workflow_stage_manifest_path(workflow_id: str, *, specs_root: Path | None = None) -> Path:
    workflow_slug = _normalize_workflow_id(workflow_id)
    root = _normalize_specs_root(specs_root)
    return root / "workflows" / f"{workflow_slug}{WORKFLOW_STAGE_MANIFEST_SUFFIX}"


def _normalize_manifest_doc_path(raw: object, *, label: str, specs_root: Path) -> str:
    normalized = _normalize_relative_posix_path(raw, label=label)
    path = PurePosixPath(normalized)
    if path.suffix != ".md":
        raise ValueError(f"{label} must reference an existing markdown file: {normalized}")
    if not normalized.startswith(_AUTHORITY_ROOTS):
        raise ValueError(f"{label} must reference an authority path under workflows/, references/, or templates/")
    if not (specs_root / normalized).is_file():
        raise ValueError(f"{label} must reference an existing markdown file: {normalized}")
    return normalized


def _normalize_write_path(raw: object, *, label: str) -> str:
    normalized = _normalize_relative_posix_path(raw, label=label)
    if not normalized.startswith("GPD/"):
        raise ValueError(f"{label} must be a normalized relative POSIX path")
    return normalized


def _normalize_relative_posix_path(raw: object, *, label: str) -> str:
    value = _require_string(raw, label=label)
    if "\\" in value:
        raise ValueError(f"{label} must be a normalized relative POSIX path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {".", ".."} for part in path.parts):
        raise ValueError(f"{label} must be a normalized relative POSIX path")
    normalized = path.as_posix()
    if normalized != value:
        raise ValueError(f"{label} must be a normalized relative POSIX path")
    return normalized


def _normalize_tool_set(values: Iterable[str] | None, *, workflow_id: str) -> frozenset[str]:
    if values is None:
        return allowed_tools_for_workflow(workflow_id)
    normalized: set[str] = set()
    for value in values:
        if not isinstance(value, str):
            raise ValueError("allowed_tools must be strings")
        tool = canonical(value.strip())
        if not tool:
            raise ValueError("allowed_tools must not contain blank entries")
        normalized.add(tool)
    return frozenset(normalized)


def allowed_tools_for_workflow(workflow_id: str | None) -> frozenset[str]:
    if workflow_id is None:
        return frozenset(CANONICAL_TOOL_NAMES)
    normalized_workflow_id = _normalize_workflow_id(workflow_id)
    return _DEFAULT_ALLOWED_TOOLS_BY_WORKFLOW.get(normalized_workflow_id, frozenset(CANONICAL_TOOL_NAMES))


def _normalize_init_field_set(values: Iterable[str] | None, *, workflow_id: str) -> frozenset[str] | None:
    if values is None:
        return _DEFAULT_KNOWN_INIT_FIELDS_BY_WORKFLOW.get(workflow_id)
    normalized: set[str] = set()
    for value in values:
        if not isinstance(value, str):
            raise ValueError("known_init_fields must be strings")
        field_name = value.strip()
        if not field_name:
            raise ValueError("known_init_fields must not contain blank entries")
        normalized.add(field_name)
    return frozenset(normalized)


def known_init_fields_for_workflow(workflow_id: str | None) -> frozenset[str] | None:
    if workflow_id is None:
        return None
    normalized_workflow_id = _normalize_workflow_id(workflow_id)
    if normalized_workflow_id in _MANIFEST_DERIVED_KNOWN_INIT_FIELD_WORKFLOWS:
        return frozenset(_manifest_expanded_required_init_field_union(normalized_workflow_id))
    return _DEFAULT_KNOWN_INIT_FIELDS_BY_WORKFLOW.get(normalized_workflow_id)


def _validate_conditional_authorities(
    raw: object, *, stage_index: int, specs_root: Path
) -> tuple[WorkflowStageConditionalAuthority, ...]:
    if not isinstance(raw, list):
        raise ValueError(f"stages[{stage_index}].conditional_authorities must be a list")

    items: list[WorkflowStageConditionalAuthority] = []
    seen_conditions: set[str] = set()
    for conditional_index, entry in enumerate(raw):
        entry_label = f"stages[{stage_index}].conditional_authorities[{conditional_index}]"
        if not isinstance(entry, dict):
            raise ValueError(f"{entry_label} must be a JSON object")
        unknown_conditional_keys = sorted(str(key) for key in entry if str(key) not in _ALLOWED_CONDITIONAL_KEYS)
        if unknown_conditional_keys:
            raise ValueError(f"{entry_label} contains unexpected key(s): {', '.join(unknown_conditional_keys)}")
        if "when" not in entry or "authorities" not in entry:
            raise ValueError(f"{entry_label} must define when and authorities")
        when = _require_string(entry["when"], label=f"{entry_label}.when")
        if when in seen_conditions:
            raise ValueError(f"stages[{stage_index}].conditional_authorities must not contain duplicate when values")
        seen_conditions.add(when)
        authorities = tuple(
            _normalize_manifest_doc_path(
                authority,
                label=f"{entry_label}.authorities[{authority_index}]",
                specs_root=specs_root,
            )
            for authority_index, authority in enumerate(
                _require_string_tuple(entry["authorities"], label=f"{entry_label}.authorities")
            )
        )
        items.append(WorkflowStageConditionalAuthority(when=when, authorities=authorities))
    return tuple(items)


def _validate_required_init_field_groups(raw: object) -> dict[str, tuple[str, ...]]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError("required_init_field_groups must be an object")

    groups: dict[str, tuple[str, ...]] = {}
    for raw_name, raw_fields in raw.items():
        name = _require_string(raw_name, label="required_init_field_groups key")
        if name in groups:
            raise ValueError("required_init_field_groups must not contain duplicate names")
        groups[name] = _require_string_tuple(
            raw_fields,
            label=f"required_init_field_groups.{name}",
        )
    return groups


def _expand_required_init_fields(
    raw: dict[str, object],
    *,
    index: int,
    groups: dict[str, tuple[str, ...]],
) -> tuple[str, ...]:
    group_names = _require_string_tuple(
        raw.get("required_init_field_groups", []),
        label=f"stages[{index}].required_init_field_groups",
        allow_empty=True,
    )
    explicit_fields = _require_string_tuple(
        raw.get("required_init_fields", []),
        label=f"stages[{index}].required_init_fields",
        allow_empty=True,
    )

    fields: list[str] = []
    seen: set[str] = set()
    for group_name in group_names:
        group_fields = groups.get(group_name)
        if group_fields is None:
            raise ValueError(f"stages[{index}].required_init_field_groups references unknown group: {group_name}")
        for field_name in group_fields:
            if field_name in seen:
                raise ValueError(f"stages[{index}].required_init_fields contains duplicate field: {field_name}")
            seen.add(field_name)
            fields.append(field_name)

    for field_name in explicit_fields:
        if field_name in seen:
            raise ValueError(f"stages[{index}].required_init_fields contains duplicate field: {field_name}")
        seen.add(field_name)
        fields.append(field_name)

    return tuple(fields)


def _read_workflow_stage_manifest_payload(workflow_id: str, *, specs_root: Path | None = None) -> object:
    path = _workflow_stage_manifest_path(workflow_id, specs_root=specs_root)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Failed to read workflow stage manifest {path}: {exc}") from exc


def _expanded_required_init_fields_by_stage_from_payload(
    raw: object,
    *,
    expected_workflow_id: str | None = None,
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    if not isinstance(raw, dict):
        raise ValueError("workflow stage manifest must be a JSON object")
    raw = canonicalize_workflow_stage_manifest_payload(raw)
    if not isinstance(raw, dict):
        raise ValueError("workflow stage manifest must be a JSON object")
    if expected_workflow_id is not None:
        workflow_id = _normalize_workflow_id(raw.get("workflow_id"))
        if workflow_id != expected_workflow_id:
            raise ValueError(
                f"workflow stage manifest workflow_id must be {expected_workflow_id!r}, got {workflow_id!r}"
            )

    stages_raw = raw.get("stages")
    if not isinstance(stages_raw, list) or not stages_raw:
        raise ValueError("stages must be a non-empty list")

    groups = _validate_required_init_field_groups(raw.get("required_init_field_groups"))
    fields_by_stage: list[tuple[str, tuple[str, ...]]] = []
    for index, raw_stage in enumerate(stages_raw):
        if not isinstance(raw_stage, dict):
            raise ValueError(f"stages[{index}] must be a JSON object")
        if "required_init_fields" not in raw_stage and "required_init_field_groups" not in raw_stage:
            raise ValueError(f"stages[{index}] is missing required key(s): required_init_fields")
        stage_id = _require_string(raw_stage.get("id"), label=f"stages[{index}].id")
        fields_by_stage.append(
            (
                stage_id,
                _expand_required_init_fields(
                    raw_stage,
                    index=index,
                    groups=groups,
                ),
            )
        )
    return tuple(fields_by_stage)


def _stable_required_init_field_union(field_sequences: Iterable[Iterable[str]]) -> tuple[str, ...]:
    fields: list[str] = []
    seen: set[str] = set()
    for sequence in field_sequences:
        for field_name in sequence:
            if field_name in seen:
                continue
            seen.add(field_name)
            fields.append(field_name)
    return tuple(fields)


def _manifest_expanded_required_init_field_union(
    workflow_id: str,
    *,
    specs_root: Path | None = None,
) -> tuple[str, ...]:
    payload = _read_workflow_stage_manifest_payload(workflow_id, specs_root=specs_root)
    return _stable_required_init_field_union(
        fields
        for _, fields in _expanded_required_init_fields_by_stage_from_payload(
            payload,
            expected_workflow_id=workflow_id,
        )
    )


def _validate_stage(
    raw: object,
    *,
    index: int,
    workflow_id: str,
    allowed_tools: frozenset[str],
    known_init_fields: frozenset[str] | None,
    required_init_field_groups: dict[str, tuple[str, ...]],
    specs_root: Path,
) -> WorkflowStage:
    if not isinstance(raw, dict):
        raise ValueError(f"stages[{index}] must be a JSON object")

    unknown_keys = sorted(str(key) for key in raw if str(key) not in _ALLOWED_STAGE_KEYS)
    if unknown_keys:
        raise ValueError(f"stages[{index}] contains unexpected key(s): {', '.join(unknown_keys)}")

    missing_keys = sorted(key for key in _REQUIRED_STAGE_KEYS if key not in raw)
    if "required_init_fields" not in raw and "required_init_field_groups" not in raw:
        missing_keys.append("required_init_fields")
    if missing_keys:
        raise ValueError(f"stages[{index}] is missing required key(s): {', '.join(missing_keys)}")

    stage_id = _require_string(raw["id"], label=f"stages[{index}].id")
    order = _require_int(raw["order"], label=f"stages[{index}].order")
    purpose = _require_string(raw["purpose"], label=f"stages[{index}].purpose")
    init_spec_id = None
    if "init_spec_id" in raw:
        init_spec_id = _require_string(raw["init_spec_id"], label=f"stages[{index}].init_spec_id")
    mode_paths = tuple(
        _normalize_manifest_doc_path(
            mode_path,
            label=f"stages[{index}].mode_paths[{mode_index}]",
            specs_root=specs_root,
        )
        for mode_index, mode_path in enumerate(
            _require_string_tuple(raw["mode_paths"], label=f"stages[{index}].mode_paths")
        )
    )
    required_init_fields = _expand_required_init_fields(
        raw,
        index=index,
        groups=required_init_field_groups,
    )
    loaded_authorities = tuple(
        _normalize_manifest_doc_path(
            authority,
            label=f"stages[{index}].loaded_authorities[{authority_index}]",
            specs_root=specs_root,
        )
        for authority_index, authority in enumerate(
            _require_string_tuple(
                raw["loaded_authorities"], label=f"stages[{index}].loaded_authorities", allow_empty=True
            )
        )
    )
    conditional_authorities = _validate_conditional_authorities(
        raw.get("conditional_authorities", []),
        stage_index=index,
        specs_root=specs_root,
    )
    must_not_eager_load = tuple(
        _normalize_manifest_doc_path(
            authority,
            label=f"stages[{index}].must_not_eager_load[{authority_index}]",
            specs_root=specs_root,
        )
        for authority_index, authority in enumerate(
            _require_string_tuple(
                raw["must_not_eager_load"], label=f"stages[{index}].must_not_eager_load", allow_empty=True
            )
        )
    )
    allowed_tools_values = tuple(
        canonical(tool.strip())
        for tool in _require_string_tuple(
            raw["allowed_tools"], label=f"stages[{index}].allowed_tools", allow_empty=True
        )
    )
    writes_allowed = tuple(
        _normalize_write_path(write_path, label=f"stages[{index}].writes_allowed[{write_index}]")
        for write_index, write_path in enumerate(
            _require_string_tuple(raw["writes_allowed"], label=f"stages[{index}].writes_allowed", allow_empty=True)
        )
    )
    produced_state = _require_string_tuple(
        raw["produced_state"],
        label=f"stages[{index}].produced_state",
        allow_empty=True,
    )
    next_stages = _require_string_tuple(
        raw["next_stages"],
        label=f"stages[{index}].next_stages",
        allow_empty=True,
    )
    checkpoints = _require_string_tuple(
        raw.get("checkpoints", []),
        label=f"stages[{index}].checkpoints",
        allow_empty=True,
    )

    if known_init_fields is not None:
        unknown_init_fields = sorted(field for field in required_init_fields if field not in known_init_fields)
        if unknown_init_fields:
            raise ValueError(
                f"stages[{index}].required_init_fields contains unknown field name(s): {', '.join(unknown_init_fields)}"
            )

    unknown_tools = sorted(tool for tool in allowed_tools_values if tool not in allowed_tools)
    if unknown_tools:
        raise ValueError(f"stages[{index}].allowed_tools contains unknown tool name(s): {', '.join(unknown_tools)}")

    unconditional_eager = set(mode_paths)
    unconditional_eager.update(loaded_authorities)
    overlap = sorted(unconditional_eager.intersection(must_not_eager_load))
    if overlap:
        raise ValueError(f"stages[{index}] overlap with must_not_eager_load: {', '.join(overlap)}")

    return WorkflowStage(
        id=stage_id,
        order=order,
        purpose=purpose,
        mode_paths=mode_paths,
        required_init_fields=required_init_fields,
        loaded_authorities=loaded_authorities,
        conditional_authorities=conditional_authorities,
        must_not_eager_load=must_not_eager_load,
        allowed_tools=allowed_tools_values,
        writes_allowed=writes_allowed,
        produced_state=produced_state,
        next_stages=next_stages,
        checkpoints=checkpoints,
        init_spec_id=init_spec_id,
    )


def validate_workflow_stage_manifest_payload(
    raw: object,
    *,
    expected_workflow_id: str | None = None,
    allowed_tools: Iterable[str] | None = None,
    known_init_fields: Iterable[str] | None = None,
    specs_root: Path | None = None,
) -> WorkflowStageManifest:
    if not isinstance(raw, dict):
        raise ValueError("workflow stage manifest must be a JSON object")
    raw = canonicalize_workflow_stage_manifest_payload(raw)
    if not isinstance(raw, dict):
        raise ValueError("workflow stage manifest must be a JSON object")

    unknown_keys = sorted(str(key) for key in raw if str(key) not in _ALLOWED_TOP_LEVEL_KEYS)
    if unknown_keys:
        raise ValueError(f"workflow stage manifest contains unexpected key(s): {', '.join(unknown_keys)}")

    missing_keys = sorted(key for key in _REQUIRED_TOP_LEVEL_KEYS if key not in raw)
    if missing_keys:
        raise ValueError(f"workflow stage manifest is missing required key(s): {', '.join(missing_keys)}")

    schema_version = _require_int(raw["schema_version"], label="schema_version")
    if schema_version != 1:
        raise ValueError("workflow stage manifest schema_version must be 1")

    workflow_id = _normalize_workflow_id(raw["workflow_id"])
    if expected_workflow_id is not None and workflow_id != expected_workflow_id:
        raise ValueError(f"workflow stage manifest workflow_id must be {expected_workflow_id!r}, got {workflow_id!r}")

    prompt_usage = _require_string(raw.get("prompt_usage", "staged_init"), label="prompt_usage")
    if prompt_usage not in _ALLOWED_PROMPT_USAGE_VALUES:
        raise ValueError(
            f"workflow stage manifest prompt_usage must be one of: {', '.join(sorted(_ALLOWED_PROMPT_USAGE_VALUES))}"
        )

    stages_raw = raw["stages"]
    if not isinstance(stages_raw, list) or not stages_raw:
        raise ValueError("stages must be a non-empty list")

    normalized_allowed_tools = _normalize_tool_set(allowed_tools, workflow_id=workflow_id)
    normalized_known_init_fields = _normalize_init_field_set(known_init_fields, workflow_id=workflow_id)
    normalized_specs_root = _normalize_specs_root(specs_root)
    required_init_field_groups = _validate_required_init_field_groups(raw.get("required_init_field_groups"))
    stages = tuple(
        _validate_stage(
            stage,
            index=index,
            workflow_id=workflow_id,
            allowed_tools=normalized_allowed_tools,
            known_init_fields=normalized_known_init_fields,
            required_init_field_groups=required_init_field_groups,
            specs_root=normalized_specs_root,
        )
        for index, stage in enumerate(stages_raw)
    )

    stage_ids = [stage.id for stage in stages]
    if len(set(stage_ids)) != len(stage_ids):
        raise ValueError("stage ids must be unique")

    stage_id_set = set(stage_ids)
    unknown_next_stages = {
        next_stage for stage in stages for next_stage in stage.next_stages if next_stage not in stage_id_set
    }
    if unknown_next_stages:
        raise ValueError(f"next_stages contains unknown stage id(s): {', '.join(sorted(unknown_next_stages))}")

    stage_orders = [stage.order for stage in stages]
    if len(set(stage_orders)) != len(stage_orders):
        raise ValueError("stage order values must be unique")
    if stage_orders != list(range(1, len(stages) + 1)):
        raise ValueError("stage order values must start at 1 and increase by 1")

    order_by_id = {stage.id: stage.order for stage in stages}
    for stage in stages:
        backward_next = sorted(
            next_stage
            for next_stage in stage.next_stages
            if next_stage in stage_id_set and order_by_id[next_stage] <= stage.order
        )
        if backward_next:
            raise ValueError(f"stage {stage.id!r} must only point to later stages; got {', '.join(backward_next)}")

    return WorkflowStageManifest(
        schema_version=schema_version,
        workflow_id=workflow_id,
        stages=stages,
        prompt_usage=prompt_usage,
    )


def _cache_key_tools(values: Iterable[str] | None, *, workflow_id: str) -> tuple[str, ...] | None:
    if values is None:
        return None
    return tuple(sorted(_normalize_tool_set(values, workflow_id=workflow_id)))


def _cache_key_init_fields(values: Iterable[str] | None, *, workflow_id: str) -> tuple[str, ...] | None:
    normalized = _normalize_init_field_set(values, workflow_id=workflow_id)
    return tuple(sorted(normalized)) if normalized is not None else None


def _infer_known_init_fields_cache_key_from_payload(raw: object) -> tuple[str, ...] | None:
    if not isinstance(raw, dict):
        return None
    raw_workflow_id = raw.get("workflow_id")
    if not isinstance(raw_workflow_id, str):
        return None
    return _cache_key_init_fields(None, workflow_id=_normalize_workflow_id(raw_workflow_id))


@cache
def _load_workflow_stage_manifest_cached(
    manifest_path: str,
    specs_root_key: str,
    expected_workflow_id: str | None,
    allowed_tools_key: tuple[str, ...] | None,
    known_init_fields_key: tuple[str, ...] | None,
) -> WorkflowStageManifest:
    path = Path(manifest_path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Failed to read workflow stage manifest {path}: {exc}") from exc
    known_init_fields_for_validation = known_init_fields_key
    if expected_workflow_id is None and known_init_fields_for_validation is None:
        known_init_fields_for_validation = _infer_known_init_fields_cache_key_from_payload(payload)
    return validate_workflow_stage_manifest_payload(
        payload,
        expected_workflow_id=expected_workflow_id,
        allowed_tools=allowed_tools_key,
        known_init_fields=known_init_fields_for_validation,
        specs_root=Path(specs_root_key),
    )


def load_workflow_stage_manifest(
    workflow_id: str,
    *,
    allowed_tools: Iterable[str] | None = None,
    known_init_fields: Iterable[str] | None = None,
    specs_root: Path | None = None,
) -> WorkflowStageManifest:
    workflow_id = _normalize_workflow_id(workflow_id)
    manifest_path = _workflow_stage_manifest_path(workflow_id, specs_root=specs_root)
    specs_root_key = _specs_root_cache_key(specs_root)
    return _load_workflow_stage_manifest_cached(
        manifest_path.as_posix(),
        specs_root_key,
        workflow_id,
        _cache_key_tools(allowed_tools, workflow_id=workflow_id),
        _cache_key_init_fields(known_init_fields, workflow_id=workflow_id),
    )


def load_workflow_stage_manifest_from_path(
    manifest_path: Path,
    *,
    expected_workflow_id: str | None = None,
    allowed_tools: Iterable[str] | None = None,
    known_init_fields: Iterable[str] | None = None,
    specs_root: Path | None = None,
) -> WorkflowStageManifest:
    workflow_id = _normalize_workflow_id(expected_workflow_id) if expected_workflow_id is not None else None
    if known_init_fields is not None:
        normalized = _normalize_init_field_set(known_init_fields, workflow_id=workflow_id or "")
        normalized_init_fields = tuple(sorted(normalized)) if normalized is not None else None
    elif workflow_id is not None:
        normalized_init_fields = _cache_key_init_fields(None, workflow_id=workflow_id)
    else:
        normalized_init_fields = None
    specs_root_key = _specs_root_cache_key(specs_root)
    return _load_workflow_stage_manifest_cached(
        manifest_path.as_posix(),
        specs_root_key,
        workflow_id,
        _cache_key_tools(allowed_tools, workflow_id=workflow_id or ""),
        normalized_init_fields,
    )


def expanded_required_init_fields_by_stage(
    manifest: WorkflowStageManifest,
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Return expanded required init fields keyed by stage in manifest order."""

    return tuple((stage.id, stage.required_init_fields) for stage in manifest.stages)


def expanded_required_init_fields_for_workflow(
    workflow_id: str,
    *,
    specs_root: Path | None = None,
) -> tuple[str, ...]:
    """Return the stable first-seen union of expanded required init fields."""

    manifest = load_workflow_stage_manifest(workflow_id, specs_root=specs_root)
    return _stable_required_init_field_union(stage.required_init_fields for stage in manifest.stages)


def invalidate_workflow_stage_manifest_cache() -> None:
    _load_workflow_stage_manifest_cached.cache_clear()


NewProjectConditionalAuthority = WorkflowStageConditionalAuthority
NewProjectStage = WorkflowStage
NewProjectStageContract = WorkflowStageManifest


def load_new_project_stage_contract() -> WorkflowStageManifest:
    return load_workflow_stage_manifest("new-project")


def load_new_project_stage_contract_from_path(manifest_path: Path) -> WorkflowStageManifest:
    return load_workflow_stage_manifest_from_path(manifest_path, expected_workflow_id="new-project")


def validate_new_project_stage_contract_payload(raw: object) -> WorkflowStageManifest:
    return validate_workflow_stage_manifest_payload(raw, expected_workflow_id="new-project")


def load_new_milestone_stage_contract() -> WorkflowStageManifest:
    return load_workflow_stage_manifest("new-milestone")


def load_new_milestone_stage_contract_from_path(manifest_path: Path) -> WorkflowStageManifest:
    return load_workflow_stage_manifest_from_path(manifest_path, expected_workflow_id="new-milestone")


def validate_new_milestone_stage_contract_payload(raw: object) -> WorkflowStageManifest:
    return validate_workflow_stage_manifest_payload(raw, expected_workflow_id="new-milestone")


def load_execute_phase_stage_contract() -> WorkflowStageManifest:
    return load_workflow_stage_manifest("execute-phase")


def load_execute_phase_stage_contract_from_path(manifest_path: Path) -> WorkflowStageManifest:
    return load_workflow_stage_manifest_from_path(manifest_path, expected_workflow_id="execute-phase")


def validate_execute_phase_stage_contract_payload(raw: object) -> WorkflowStageManifest:
    return validate_workflow_stage_manifest_payload(raw, expected_workflow_id="execute-phase")


def load_arxiv_submission_stage_contract() -> WorkflowStageManifest:
    return load_workflow_stage_manifest("arxiv-submission")


def validate_arxiv_submission_stage_contract_payload(raw: object) -> WorkflowStageManifest:
    return validate_workflow_stage_manifest_payload(raw, expected_workflow_id="arxiv-submission")


def load_autonomous_stage_contract() -> WorkflowStageManifest:
    return load_workflow_stage_manifest("autonomous")


def validate_autonomous_stage_contract_payload(raw: object) -> WorkflowStageManifest:
    return validate_workflow_stage_manifest_payload(raw, expected_workflow_id="autonomous")


def load_literature_review_stage_contract() -> WorkflowStageManifest:
    return load_workflow_stage_manifest("literature-review")


def load_literature_review_stage_contract_from_path(manifest_path: Path) -> WorkflowStageManifest:
    return load_workflow_stage_manifest_from_path(manifest_path, expected_workflow_id="literature-review")


def validate_literature_review_stage_contract_payload(raw: object) -> WorkflowStageManifest:
    return validate_workflow_stage_manifest_payload(raw, expected_workflow_id="literature-review")


def load_research_phase_stage_contract() -> WorkflowStageManifest:
    return load_workflow_stage_manifest("research-phase")


def load_research_phase_stage_contract_from_path(manifest_path: Path) -> WorkflowStageManifest:
    return load_workflow_stage_manifest_from_path(manifest_path, expected_workflow_id="research-phase")


def validate_research_phase_stage_contract_payload(raw: object) -> WorkflowStageManifest:
    return validate_workflow_stage_manifest_payload(raw, expected_workflow_id="research-phase")


def load_map_research_stage_contract() -> WorkflowStageManifest:
    return load_workflow_stage_manifest("map-research")


def load_map_research_stage_contract_from_path(manifest_path: Path) -> WorkflowStageManifest:
    return load_workflow_stage_manifest_from_path(manifest_path, expected_workflow_id="map-research")


def validate_map_research_stage_contract_payload(raw: object) -> WorkflowStageManifest:
    return validate_workflow_stage_manifest_payload(raw, expected_workflow_id="map-research")


__all__ = [
    "ARXIV_SUBMISSION_BOOTSTRAP_FIELDS",
    "ARXIV_SUBMISSION_INIT_FIELDS",
    "ARXIV_SUBMISSION_SNAPSHOT_FIELDS",
    "AUTONOMOUS_INIT_FIELDS",
    "AUTONOMOUS_STAGE_MANIFEST_PATH",
    "NEW_PROJECT_INIT_FIELDS",
    "NEW_PROJECT_STAGE_MANIFEST_PATH",
    "NEW_MILESTONE_INIT_FIELDS",
    "NEW_MILESTONE_STAGE_MANIFEST_PATH",
    "LITERATURE_REVIEW_INIT_FIELDS",
    "LITERATURE_REVIEW_STAGE_MANIFEST_PATH",
    "MAP_RESEARCH_INIT_FIELDS",
    "MAP_RESEARCH_STAGE_MANIFEST_PATH",
    "EXECUTE_PHASE_INIT_FIELDS",
    "EXECUTE_PHASE_SCHEMA_BRIDGE_FIELDS",
    "EXECUTE_PHASE_STAGE_MANIFEST_PATH",
    "EXECUTE_PHASE_TASK_OVERLAY_FIELDS",
    "PLAN_PHASE_BASE_INIT_FIELDS",
    "PLAN_PHASE_CONTRACT_GATE_FIELDS",
    "PLAN_PHASE_FILE_CONTENT_FIELDS",
    "PLAN_PHASE_INIT_FIELDS",
    "PLAN_PHASE_REFERENCE_RUNTIME_FIELDS",
    "PLAN_PHASE_STAGE_MANIFEST_PATH",
    "PLAN_PHASE_STATE_MEMORY_FIELDS",
    "PLAN_PHASE_STRUCTURED_STATE_FIELDS",
    "QUICK_BASE_INIT_FIELDS",
    "QUICK_CONTRACT_GATE_FIELDS",
    "QUICK_INIT_FIELDS",
    "QUICK_REFERENCE_RUNTIME_FIELDS",
    "QUICK_STAGE_MANIFEST_PATH",
    "RESEARCH_PHASE_INIT_FIELDS",
    "RESEARCH_PHASE_STAGE_MANIFEST_PATH",
    "VERIFY_WORK_BASE_INIT_FIELDS",
    "VERIFY_WORK_CONTRACT_GATE_FIELDS",
    "NewProjectConditionalAuthority",
    "NewProjectStage",
    "NewProjectStageContract",
    "WRITE_PAPER_INIT_FIELDS",
    "WRITE_PAPER_MANAGED_INTAKE_ROOT",
    "WRITE_PAPER_MANAGED_MANUSCRIPT_ROOT",
    "WORKFLOW_STAGE_MANIFEST_DIR",
    "WORKFLOW_STAGE_MANIFEST_SUFFIX",
    "VERIFY_WORK_INIT_FIELDS",
    "VERIFY_WORK_MCP_VERIFICATION_TOOLS",
    "VERIFY_WORK_REFERENCE_RUNTIME_FIELDS",
    "VERIFY_WORK_SCHEMA_BRIDGE_FIELDS",
    "VERIFY_WORK_STAGE_ALLOWED_TOOLS",
    "VERIFY_WORK_STATE_MEMORY_FIELDS",
    "VERIFY_WORK_STRUCTURED_STATE_FIELDS",
    "PEER_REVIEW_INIT_FIELDS",
    "WorkflowStage",
    "WorkflowStageConditionalAuthority",
    "WorkflowStageManifest",
    "allowed_tools_for_workflow",
    "expanded_required_init_fields_by_stage",
    "expanded_required_init_fields_for_workflow",
    "invalidate_workflow_stage_manifest_cache",
    "load_new_project_stage_contract",
    "load_new_project_stage_contract_from_path",
    "load_new_milestone_stage_contract",
    "load_new_milestone_stage_contract_from_path",
    "load_arxiv_submission_stage_contract",
    "load_autonomous_stage_contract",
    "load_literature_review_stage_contract",
    "load_literature_review_stage_contract_from_path",
    "load_execute_phase_stage_contract",
    "load_execute_phase_stage_contract_from_path",
    "load_map_research_stage_contract",
    "load_map_research_stage_contract_from_path",
    "load_research_phase_stage_contract",
    "load_research_phase_stage_contract_from_path",
    "load_workflow_stage_manifest",
    "load_workflow_stage_manifest_from_path",
    "known_init_fields_for_workflow",
    "render_staged_field_access_instruction",
    "resolve_workflow_stage_manifest_path",
    "validate_new_project_stage_contract_payload",
    "validate_new_milestone_stage_contract_payload",
    "validate_arxiv_submission_stage_contract_payload",
    "validate_autonomous_stage_contract_payload",
    "validate_literature_review_stage_contract_payload",
    "validate_map_research_stage_contract_payload",
    "validate_execute_phase_stage_contract_payload",
    "validate_research_phase_stage_contract_payload",
    "validate_workflow_stage_manifest_payload",
]
