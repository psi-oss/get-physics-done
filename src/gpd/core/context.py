"""Context assembly for AI agent commands.

Each function gathers project state and produces a structured dict consumed by agent prompts.

Delegates to :mod:`gpd.core.config` for configuration loading and model-tier
resolution so that defaults and model profiles are defined in exactly one place.
"""

from __future__ import annotations

import json
import logging
import re
import shlex
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError as PydanticValidationError

from gpd.contracts import (
    CONTRACT_CONTEXT_INTAKE_FIELD_NAMES,
    ConventionLock,
    ResearchContract,
    parse_project_contract_data_salvage,
)
from gpd.core import state as _state_module
from gpd.core.config import GPDProjectConfig
from gpd.core.config import load_config as _load_config_structured
from gpd.core.config import resolve_model as _resolve_model_canonical
from gpd.core.constants import (
    AGENT_ID_FILENAME,
    CONFIG_FILENAME,
    CONTEXT_SUFFIX,
    MILESTONES_DIR_NAME,
    MILESTONES_FILENAME,
    PHASES_DIR_NAME,
    PLAN_SUFFIX,
    PLANNING_DIR_NAME,
    PROJECT_FILENAME,
    PUBLICATION_DIR_NAME,
    REQUIREMENTS_FILENAME,
    RESEARCH_MAP_DIR_NAME,
    RESEARCH_SUFFIX,
    ROADMAP_FILENAME,
    STANDALONE_CONTEXT,
    STANDALONE_PLAN,
    STANDALONE_RESEARCH,
    STANDALONE_VALIDATION,
    STATE_JSON_BACKUP_FILENAME,
    STATE_MD_FILENAME,
    TODOS_DIR_NAME,
    VALIDATION_SUFFIX,
    VERIFICATION_SUFFIX,
    ProjectLayout,
)
from gpd.core.context_roots import (
    InitRootPolicy,
    _detect_platform,
    _path_exists,
    _resolve_project_scoped_cwd,
    _start_folder_state,
    _workspace_start_classifier_context,
)
from gpd.core.context_roots import (
    _resolve_cwd_for_root_policy as _resolve_cwd_for_root_policy,
)
from gpd.core.context_roots import (
    _resolve_workspace_locked_cwd as _resolve_workspace_locked_cwd,
)
from gpd.core.context_scan import (
    _discover_research_file_samples as _discover_research_file_samples,
)
from gpd.core.context_scan import (
    _ignore_dirs as _ignore_dirs,
)
from gpd.core.context_scan import (
    _research_scan_max_depth_for_directory as _research_scan_max_depth_for_directory,
)
from gpd.core.context_scan import (
    _runtime_config_dirs as _runtime_config_dirs,
)
from gpd.core.context_scan import (
    _runtime_ignored_scan_paths as _runtime_ignored_scan_paths,
)
from gpd.core.context_scan import (
    _should_skip_research_scan_entry as _should_skip_research_scan_entry,
)
from gpd.core.context_staged_providers import (
    assembly_context_provider as _staged_assembly_context_provider,
)
from gpd.core.context_staged_providers import (
    build_selected_file_context as _build_selected_file_context,
)
from gpd.core.context_staged_providers import (
    context_provider as _staged_context_provider,
)
from gpd.core.context_staged_providers import (
    file_context_provider as _staged_file_context_provider,
)
from gpd.core.context_staged_providers import (
    reference_or_contract_provider as _staged_reference_or_contract_provider,
)
from gpd.core.context_staged_providers import (
    scalar_field_provider as _staged_scalar_field_provider,
)
from gpd.core.context_staged_providers import (
    schema_bridge_provider as _staged_schema_bridge_provider,
)
from gpd.core.context_staged_providers import (
    selected_fields_provider as _staged_selected_fields_provider,
)
from gpd.core.context_todos import (
    _extract_frontmatter_field,
    _read_todo_frontmatter,
)
from gpd.core.context_todos import (
    _looks_like_todo_frontmatter_candidate as _looks_like_todo_frontmatter_candidate,
)
from gpd.core.context_todos import (
    _normalize_todo_frontmatter_text as _normalize_todo_frontmatter_text,
)
from gpd.core.context_todos import (
    _normalize_todo_metadata_value as _normalize_todo_metadata_value,
)
from gpd.core.continuation import (
    RESUMABLE_SEGMENT_STATUSES,
    ContinuationResumeSource,
    ContinuationSource,
    normalize_continuation,
    normalize_continuation_reference,
    resolve_continuation,
)
from gpd.core.conventions import is_bogus_value
from gpd.core.errors import ValidationError
from gpd.core.extras import approximation_list
from gpd.core.knowledge_runtime import discover_knowledge_docs
from gpd.core.manuscript_artifacts import (
    _derive_hashed_publication_subject_slug as derive_hashed_publication_subject_slug,
)
from gpd.core.manuscript_artifacts import (
    _resolve_manuscript_entrypoint_from_root_resolution as resolve_manuscript_entrypoint_from_root_resolution,
)
from gpd.core.manuscript_artifacts import (
    _supported_manuscript_root_for_target as resolve_supported_manuscript_root_for_target,
)
from gpd.core.manuscript_artifacts import (
    resolve_current_manuscript_entrypoint,
    resolve_current_publication_subject,
    resolve_explicit_publication_subject,
    resolve_publication_bootstrap_resolution,
)
from gpd.core.peer_review_mode import (
    PEER_REVIEW_STANDALONE_MODE,
    resolve_peer_review_mode,
)
from gpd.core.phases import _milestone_completion_snapshot, roadmap_analyze
from gpd.core.project_reentry import (
    ProjectReentryCandidate,
    recoverable_project_context,
    resolve_project_reentry,
)
from gpd.core.proof_review import (
    resolve_manuscript_proof_review_status,
    resolve_phase_proof_review_status,
)
from gpd.core.protocol_bundles import (
    ResolvedProtocolBundle,
    build_protocol_bundle_load_manifest,
    render_protocol_bundle_context,
    select_protocol_bundles,
)
from gpd.core.publication_runtime import publication_runtime_snapshot_context
from gpd.core.reference_ingestion import ingest_manuscript_reference_status, ingest_reference_artifacts
from gpd.core.results import result_list
from gpd.core.resume_surface import (
    RESUME_BACKEND_ONLY_FIELDS,
    RESUME_SURFACE_SCHEMA_VERSION,
    build_resume_candidate,
    build_resume_segment_candidate,
    canonicalize_resume_public_payload,
    resume_origin_for_bounded_segment,
    resume_origin_for_handoff,
    resume_origin_for_interrupted_agent,
)
from gpd.core.root_resolution import (
    RootResolutionPolicy,
    resolve_project_roots,
)
from gpd.core.staged_context_fields import (
    ARXIV_SUBMISSION_BOOTSTRAP_FIELDS,
    ARXIV_SUBMISSION_SNAPSHOT_FIELDS,
)
from gpd.core.staged_context_fields import (
    EXECUTE_PHASE_CONTRACT_GATE_FIELDS as _EXECUTE_PHASE_CONTRACT_GATE_FIELDS,
)
from gpd.core.staged_context_fields import (
    EXECUTE_PHASE_EXECUTION_RUNTIME_FIELDS as _EXECUTE_PHASE_EXECUTION_RUNTIME_FIELDS,
)
from gpd.core.staged_context_fields import (
    EXECUTE_PHASE_REFERENCE_RUNTIME_FIELDS as _EXECUTE_PHASE_REFERENCE_RUNTIME_FIELDS,
)
from gpd.core.staged_context_fields import (
    EXECUTE_PHASE_SCHEMA_BRIDGE_FIELDS as _EXECUTE_PHASE_SCHEMA_BRIDGE_FIELDS,
)
from gpd.core.staged_context_fields import (
    EXECUTE_PHASE_STATE_MEMORY_FIELDS as _EXECUTE_PHASE_STATE_MEMORY_FIELDS,
)
from gpd.core.staged_context_fields import (
    EXECUTE_PHASE_STRUCTURED_STATE_FIELDS as _EXECUTE_PHASE_STRUCTURED_STATE_FIELDS,
)
from gpd.core.staged_context_fields import (
    EXECUTE_PHASE_TASK_OVERLAY_FIELDS as _EXECUTE_PHASE_TASK_OVERLAY_FIELDS,
)
from gpd.core.staged_context_fields import (
    NEW_MILESTONE_FILE_CONTENT_FIELDS as _NEW_MILESTONE_FILE_CONTENT_FIELDS,
)
from gpd.core.staged_context_fields import (
    NEW_MILESTONE_REFERENCE_RUNTIME_FIELDS as _NEW_MILESTONE_REFERENCE_RUNTIME_FIELDS,
)
from gpd.core.staged_context_fields import (
    PEER_REVIEW_REFERENCE_RUNTIME_FIELDS as _PEER_REVIEW_REFERENCE_RUNTIME_FIELDS,
)
from gpd.core.staged_context_fields import (
    PLAN_PHASE_CONTRACT_GATE_FIELDS as _PLAN_PHASE_CONTRACT_GATE_FIELDS,
)
from gpd.core.staged_context_fields import (
    PLAN_PHASE_FILE_CONTENT_FIELDS as _PLAN_PHASE_FILE_CONTENT_FIELDS,
)
from gpd.core.staged_context_fields import (
    PLAN_PHASE_REFERENCE_RUNTIME_FIELDS as _PLAN_PHASE_REFERENCE_RUNTIME_FIELDS,
)
from gpd.core.staged_context_fields import (
    PLAN_PHASE_STATE_MEMORY_FIELDS as _PLAN_PHASE_STATE_MEMORY_FIELDS,
)
from gpd.core.staged_context_fields import (
    PLAN_PHASE_STRUCTURED_STATE_FIELDS as _PLAN_PHASE_STRUCTURED_STATE_FIELDS,
)
from gpd.core.staged_context_fields import (
    PROJECT_CONTRACT_GATE_FIELDS as _PROJECT_CONTRACT_GATE_FIELDS,
)
from gpd.core.staged_context_fields import (
    RESEARCH_PHASE_FILE_CONTENT_FIELDS as _RESEARCH_PHASE_FILE_CONTENT_FIELDS,
)
from gpd.core.staged_context_fields import (
    RESUME_FILE_CONTENT_FIELDS as _RESUME_FILE_CONTENT_FIELDS,
)
from gpd.core.staged_context_fields import (
    RESUME_REFERENCE_RUNTIME_FIELDS as _RESUME_REFERENCE_RUNTIME_FIELDS,
)
from gpd.core.staged_context_fields import (
    STAGED_FULL_REFERENCE_RUNTIME_FIELDS as _STAGED_FULL_REFERENCE_RUNTIME_FIELDS,
)
from gpd.core.staged_context_fields import (
    STAGED_REFERENCE_BODY_FIELDS as _STAGED_REFERENCE_BODY_FIELDS,
)
from gpd.core.staged_context_fields import (
    STAGED_REFERENCE_RENDERED_CONTEXT_FIELDS as _STAGED_REFERENCE_RENDERED_CONTEXT_FIELDS,
)
from gpd.core.staged_context_fields import (
    STAGED_REFERENCE_SUMMARY_FIELDS as _STAGED_REFERENCE_SUMMARY_FIELDS,
)
from gpd.core.staged_context_fields import (
    STATE_MEMORY_FIELDS as _STATE_MEMORY_FIELDS,
)
from gpd.core.staged_context_fields import (
    STRUCTURED_STATE_FIELDS as _STRUCTURED_STATE_FIELDS,
)
from gpd.core.staged_context_fields import (
    VERIFY_WORK_CONTRACT_GATE_FIELDS as _VERIFY_WORK_CONTRACT_GATE_FIELDS,
)
from gpd.core.staged_context_fields import (
    VERIFY_WORK_REFERENCE_RUNTIME_FIELDS as _VERIFY_WORK_REFERENCE_RUNTIME_FIELDS,
)
from gpd.core.staged_context_fields import (
    VERIFY_WORK_SCHEMA_BRIDGE_FIELDS as _VERIFY_WORK_SCHEMA_BRIDGE_FIELDS,
)
from gpd.core.staged_context_fields import (
    VERIFY_WORK_STATE_MEMORY_FIELDS as _VERIFY_WORK_STATE_MEMORY_FIELDS,
)
from gpd.core.staged_context_fields import (
    VERIFY_WORK_STRUCTURED_STATE_FIELDS as _VERIFY_WORK_STRUCTURED_STATE_FIELDS,
)
from gpd.core.staged_context_fields import (
    WRITE_PAPER_BOOTSTRAP_REFERENCE_FIELDS as _WRITE_PAPER_BOOTSTRAP_REFERENCE_FIELDS,
)
from gpd.core.staged_context_fields import (
    WRITE_PAPER_FILE_CONTENT_FIELDS as _WRITE_PAPER_FILE_CONTENT_FIELDS,
)
from gpd.core.staged_context_fields import (
    WRITE_PAPER_PUBLICATION_BOOTSTRAP_FIELDS as _WRITE_PAPER_PUBLICATION_BOOTSTRAP_FIELDS,
)
from gpd.core.staged_context_fields import (
    WRITE_PAPER_REFERENCE_RUNTIME_FIELDS as _WRITE_PAPER_REFERENCE_RUNTIME_FIELDS,
)
from gpd.core.staged_init_assembly import (
    assemble_staged_init_payload as _assemble_staged_init_payload,
)
from gpd.core.start_context_choices import start_visible_choices
from gpd.core.state import _current_machine_identity, _finalize_project_contract_gate, backup_only_state_guidance
from gpd.core.state import peek_state_json as _peek_state_json
from gpd.core.task_overlays import build_task_overlay_load_manifest
from gpd.core.utils import (
    generate_slug as _generate_slug_impl,
)
from gpd.core.utils import is_phase_complete as _is_phase_complete
from gpd.core.utils import matching_phase_artifact_count as _matching_phase_artifact_count
from gpd.core.utils import phase_normalize as _phase_normalize_impl
from gpd.core.utils import phase_sort_key as _phase_sort_key
from gpd.core.utils import safe_read_file as _safe_read_file
from gpd.core.utils import safe_read_file_truncated as _safe_read_file_truncated
from gpd.core.verification_status import read_verification_status
from gpd.core.workflow_init.dependencies import WorkflowInitDependencies
from gpd.core.workflow_init.literature_review import init_literature_review as _init_literature_review_builder
from gpd.core.workflow_init.map_research import init_map_research as _init_map_research_builder
from gpd.core.workflow_init.quick import init_quick as _init_quick_builder
from gpd.core.workflow_init.sync_state import init_sync_state as _init_sync_state_builder
from gpd.core.workflow_staging import (
    AUTONOMOUS_INIT_FIELDS as _AUTONOMOUS_INIT_FIELDS,
)
from gpd.core.workflow_staging import (
    LITERATURE_REVIEW_INIT_FIELDS as _LITERATURE_REVIEW_INIT_FIELDS,
)
from gpd.core.workflow_staging import (
    MAP_RESEARCH_INIT_FIELDS as _MAP_RESEARCH_INIT_FIELDS,
)
from gpd.core.workflow_staging import (
    NEW_MILESTONE_INIT_FIELDS as _NEW_MILESTONE_INIT_FIELDS,
)
from gpd.core.workflow_staging import (
    PEER_REVIEW_INIT_FIELDS,
    load_arxiv_submission_stage_contract,
)
from gpd.core.workflow_staging import (
    PLAN_PHASE_INIT_FIELDS as _PLAN_PHASE_INIT_FIELDS,
)
from gpd.core.workflow_staging import (
    QUICK_INIT_FIELDS as _QUICK_INIT_FIELDS,
)
from gpd.core.workflow_staging import (
    RESEARCH_PHASE_INIT_FIELDS as _RESEARCH_PHASE_INIT_FIELDS,
)
from gpd.core.workflow_staging import (
    VERIFY_WORK_INIT_FIELDS as _VERIFY_WORK_INIT_FIELDS,
)
from gpd.core.workflow_staging import (
    WRITE_PAPER_INIT_FIELDS as _WRITE_PAPER_INIT_FIELDS,
)
from gpd.core.write_paper_intake import (
    WritePaperExternalAuthoringIntakeResolution,
    has_write_paper_external_authoring_intake,
    reject_write_paper_intake_inside_project_detail,
    resolve_write_paper_external_authoring_intake,
)

logger = logging.getLogger(__name__)


# Keep these aliases importable while known-init authority moves out of context builders.
_LEGACY_INIT_FIELD_EXPORTS = (
    _LITERATURE_REVIEW_INIT_FIELDS,
    _MAP_RESEARCH_INIT_FIELDS,
    _NEW_MILESTONE_INIT_FIELDS,
    _PLAN_PHASE_INIT_FIELDS,
    _QUICK_INIT_FIELDS,
    _RESEARCH_PHASE_INIT_FIELDS,
    _VERIFY_WORK_INIT_FIELDS,
    _WRITE_PAPER_INIT_FIELDS,
)
_LITERATURE_DIR_NAME = "literature"
_REFERENCE_MAP_DOCS = ("REFERENCES.md", "VALIDATION.md")
_LITERATURE_INCLUDE_LIMIT = 2
_RESEARCH_MAP_INCLUDE_LIMIT = 4
_KNOWLEDGE_INCLUDE_LIMIT = 2
_EXPERIMENT_DESIGN_SUFFIX = "-EXPERIMENT-DESIGN.md"
_REFERENCE_ROLE_PRIORITY = {
    "benchmark": 0,
    "must_consider": 1,
    "definition": 2,
    "method": 3,
    "background": 4,
    "other": 5,
}
_EXECUTE_PHASE_EXECUTOR_TASK_OVERLAY_IDS = ("executor.bounded_segment",)
_EXECUTE_PHASE_TASK_OVERLAY_SELECTION_SOURCE = "execute-phase.executor_dispatch"
_EXECUTE_PHASE_TASK_OVERLAY_POLICY_SUMMARY = (
    "Selected executor.bounded_segment for execute-phase executor_dispatch bounded fanout; "
    "selected entries stay metadata-only."
)
_PLAN_PHASE_PLANNING_FILE_CONTEXT_PATHS = {
    "state_content": f"{PLANNING_DIR_NAME}/{STATE_MD_FILENAME}",
    "roadmap_content": f"{PLANNING_DIR_NAME}/{ROADMAP_FILENAME}",
    "requirements_content": f"{PLANNING_DIR_NAME}/{REQUIREMENTS_FILENAME}",
}
_PLAN_PHASE_ARTIFACT_FIELD_SPECS = {
    "context_content": (CONTEXT_SUFFIX, STANDALONE_CONTEXT),
    "research_content": (RESEARCH_SUFFIX, STANDALONE_RESEARCH),
    "experiment_design_content": (_EXPERIMENT_DESIGN_SUFFIX, None),
    "verification_content": (VERIFICATION_SUFFIX, None),
    "validation_content": (VALIDATION_SUFFIX, STANDALONE_VALIDATION),
}
_PLAN_PHASE_INCLUDE_FILE_FIELDS = {
    "state": "state_content",
    "roadmap": "roadmap_content",
    "requirements": "requirements_content",
    "context": "context_content",
    "research": "research_content",
    "verification": "verification_content",
    "validation": "validation_content",
}
_NEW_MILESTONE_FILE_CONTEXT_PATHS = {
    "project_content": f"{PLANNING_DIR_NAME}/{PROJECT_FILENAME}",
    "state_content": f"{PLANNING_DIR_NAME}/{STATE_MD_FILENAME}",
    "milestones_content": f"{PLANNING_DIR_NAME}/{MILESTONES_FILENAME}",
    "requirements_content": f"{PLANNING_DIR_NAME}/{REQUIREMENTS_FILENAME}",
    "roadmap_content": f"{PLANNING_DIR_NAME}/{ROADMAP_FILENAME}",
}
_RESUME_FILE_CONTEXT_PATHS = {
    "state_content": f"{PLANNING_DIR_NAME}/{STATE_MD_FILENAME}",
    "project_content": f"{PLANNING_DIR_NAME}/{PROJECT_FILENAME}",
    "roadmap_content": f"{PLANNING_DIR_NAME}/{ROADMAP_FILENAME}",
    "derivation_state_content": f"{PLANNING_DIR_NAME}/DERIVATION-STATE.md",
}
_RESEARCH_PHASE_FILE_CONTEXT_PATHS = {
    "state_content": f"{PLANNING_DIR_NAME}/{STATE_MD_FILENAME}",
    "config_content": f"{PLANNING_DIR_NAME}/{CONFIG_FILENAME}",
    "roadmap_content": f"{PLANNING_DIR_NAME}/{ROADMAP_FILENAME}",
}
_RESEARCH_PHASE_INCLUDE_FILE_FIELDS = {
    "state": "state_content",
    "config": "config_content",
    "roadmap": "roadmap_content",
}


__all__ = [
    "init_arxiv_submission",
    "init_autonomous",
    "init_build_persona",
    "init_execute_phase",
    "init_literature_review",
    "init_map_research",
    "init_milestone_op",
    "init_peer_review",
    "init_new_milestone",
    "init_new_project",
    "init_start_context",
    "init_phase_op",
    "init_research_phase",
    "init_plan_phase",
    "init_progress",
    "init_quick",
    "init_respond_to_referees",
    "init_resume",
    "init_todos",
    "init_verify_work",
    "load_config",
]


def _state_exists(cwd: Path) -> bool:
    """Return whether the project has recoverable state from JSON or STATE.md."""
    layout = ProjectLayout(cwd)
    if not (layout.state_json.exists() or layout.state_md.exists()):
        return False
    state, _state_issues, _state_source = _peek_state_json(
        cwd,
        recover_intent=False,
        acquire_lock=False,
    )
    return isinstance(state, dict)


def _backup_only_state_guidance(cwd: Path) -> str | None:
    """Return conservative recovery guidance for a lone backup state file."""

    layout = ProjectLayout(cwd)
    if layout.state_json_backup.exists() and not layout.state_json.exists() and not layout.state_md.exists():
        return backup_only_state_guidance()
    return None


def _structured_state_objects(value: object) -> list[dict[str, object]]:
    """Return only structured mapping entries from a state section."""
    if not isinstance(value, list):
        return []
    structured: list[dict[str, object]] = []
    for item in value:
        if isinstance(item, Mapping):
            structured.append(dict(item))
    return structured


def _has_structured_state_value(value: object) -> bool:
    """Return whether a structured state value is materially set."""
    if value is None:
        return False
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped or stripped == "\u2014" or stripped.casefold() == "[not set]":
            return False
        return not is_bogus_value(stripped)
    if isinstance(value, Mapping):
        return bool(value)
    if isinstance(value, (list, tuple, set)):
        return bool(value)
    return True


def _build_structured_state_runtime_context(cwd: Path) -> dict[str, object]:
    """Build structured canonical state slices for init payloads."""
    state, state_issues, state_source = _peek_state_json(
        cwd,
        recover_intent=False,
        acquire_lock=False,
    )
    source = state_source.as_posix() if isinstance(state_source, Path) else str(state_source) if state_source else None
    if not isinstance(state, dict):
        return {
            "state_load_source": source,
            "state_integrity_issues": list(state_issues or []),
            "convention_lock": {},
            "convention_lock_count": 0,
            "intermediate_results": [],
            "intermediate_result_count": 0,
            "approximations": [],
            "approximation_count": 0,
            "propagated_uncertainties": [],
            "propagated_uncertainty_count": 0,
        }

    convention_lock = state.get("convention_lock")
    intermediate_results = _structured_state_objects(state.get("intermediate_results"))
    approximations = _structured_state_objects(state.get("approximations"))
    propagated_uncertainties = _structured_state_objects(state.get("propagated_uncertainties"))
    structured_convention_lock = dict(convention_lock) if isinstance(convention_lock, Mapping) else {}
    return {
        "state_load_source": source,
        "state_integrity_issues": list(state_issues or []),
        "convention_lock": structured_convention_lock,
        "convention_lock_count": sum(
            1 for value in structured_convention_lock.values() if _has_structured_state_value(value)
        ),
        "intermediate_results": intermediate_results,
        "intermediate_result_count": len(intermediate_results),
        "approximations": approximations,
        "approximation_count": len(approximations),
        "propagated_uncertainties": propagated_uncertainties,
        "propagated_uncertainty_count": len(propagated_uncertainties),
    }


def _explicit_workspace_layout_context(cwd: Path) -> tuple[Path, dict[str, object]] | None:
    """Return local current-workspace metadata when the caller already targets a GPD layout."""

    resolution = resolve_project_roots(cwd)
    if resolution is None:
        return None

    project_root = resolution.project_root
    layout = ProjectLayout(project_root)
    has_execution_resume_surface = (
        layout.current_observability_execution.exists()
        or layout.execution_lineage_head.exists()
        or layout.execution_lineage_ledger.exists()
    )
    has_local_config_surface = resolution.walk_up_steps == 0 and layout.config_json.exists()
    has_local_phase_surface = resolution.walk_up_steps == 0 and layout.phases_dir.exists()
    if (
        not resolution.has_project_layout
        and not has_execution_resume_surface
        and not has_local_config_surface
        and not has_local_phase_surface
    ):
        return None

    state_exists, roadmap_exists, project_exists = recoverable_project_context(project_root)
    recoverable = (
        state_exists
        or roadmap_exists
        or project_exists
        or has_execution_resume_surface
        or has_local_config_surface
        or has_local_phase_surface
    )
    if resolution.walk_up_steps > 0:
        reason = "workspace resolved to ancestor project root"
    elif has_execution_resume_surface and not (state_exists or roadmap_exists or project_exists):
        reason = "workspace carries live execution state"
    elif has_local_config_surface and not (state_exists or roadmap_exists or project_exists):
        reason = "workspace carries local GPD config"
    elif has_local_phase_surface and not (state_exists or roadmap_exists or project_exists):
        reason = "workspace carries local GPD phase directory"
    elif not project_exists and recoverable:
        reason = "workspace carries partial recoverable GPD state"
    else:
        reason = "workspace already points at a GPD project"

    current_candidate = ProjectReentryCandidate(
        source="current_workspace",
        project_root=project_root.as_posix(),
        available=project_root.is_dir(),
        recoverable=recoverable,
        resumable=False,
        confidence=resolution.confidence.value,
        reason=reason,
        summary=reason,
        state_exists=state_exists,
        roadmap_exists=roadmap_exists,
        project_exists=project_exists,
    )
    metadata: dict[str, object] = {
        "workspace_root": resolution.workspace_root.as_posix() if resolution.workspace_root is not None else None,
        "project_root": project_root.as_posix(),
        "project_root_source": "current_workspace",
        "project_root_auto_selected": False,
        "project_reentry_mode": "current-workspace",
        "project_reentry_requires_selection": False,
        "project_reentry_selected_candidate": current_candidate.model_dump(mode="json"),
        "project_reentry_candidates": [current_candidate.model_dump(mode="json")],
    }
    return project_root, metadata


def _resolve_reentry_context(
    cwd: Path,
    *,
    data_root: Path | None = None,
    prefer_workspace_layout: bool = False,
) -> tuple[Path, dict[str, object]]:
    """Return the effective project root plus shared re-entry metadata."""

    if prefer_workspace_layout:
        local_context = _explicit_workspace_layout_context(cwd)
        if local_context is not None:
            return local_context

    resolution = resolve_project_reentry(cwd, data_root=data_root)
    selected_project_root = resolution.resolved_project_root
    effective_cwd = selected_project_root or cwd.expanduser().resolve(strict=False)
    project_root_source = resolution.source if selected_project_root is not None else None
    metadata: dict[str, object] = {
        "workspace_root": resolution.workspace_root,
        "project_root": selected_project_root.as_posix() if selected_project_root is not None else None,
        "project_root_source": project_root_source,
        "project_root_auto_selected": resolution.auto_selected,
        "project_reentry_mode": resolution.mode,
        "project_reentry_requires_selection": resolution.requires_user_selection,
        "project_reentry_selected_candidate": (
            resolution.selected_candidate.model_dump(mode="json") if resolution.selected_candidate is not None else None
        ),
        "project_reentry_candidates": [candidate.model_dump(mode="json") for candidate in resolution.candidates],
    }
    if resolution.diagnostics:
        metadata["project_reentry_diagnostics"] = list(resolution.diagnostics)
    return effective_cwd, metadata


def _generate_slug(text: str | None) -> str | None:
    """Generate a URL-friendly slug from text.

    Thin wrapper around :func:`gpd.core.utils.generate_slug` that also
    accepts ``None`` (returning ``None`` immediately).
    """
    if not text:
        return None
    return _generate_slug_impl(text)


def _normalize_phase_name(phase: str) -> str:
    """Pad top-level phase number to 2 digits. E.g. '3' -> '03', '3.1' -> '03.1'.

    Delegates to :func:`gpd.core.utils.phase_normalize`.
    """
    return _phase_normalize_impl(phase)


def _find_phase_artifact(phase_dir: Path, suffix: str, standalone: str | None = None) -> str | None:
    """Find file content matching a suffix pattern in a phase directory (truncated)."""
    if not phase_dir.is_dir():
        return None
    for f in sorted(phase_dir.iterdir()):
        if f.is_file() and (f.name.endswith(suffix) or (standalone is not None and f.name == standalone)):
            return _safe_read_file_truncated(f)
    return None


def _find_phase_artifact_path(phase_dir: Path, suffix: str, standalone: str | None = None) -> Path | None:
    """Return the full path to the first file in ``phase_dir`` matching ``suffix``
    or ``standalone``, or ``None``. Mirrors :func:`_find_phase_artifact` but
    returns a :class:`Path` for callers that need full content (not truncated).
    """
    if not phase_dir.is_dir():
        return None
    for path in sorted(phase_dir.iterdir()):
        if not path.is_file():
            continue
        if standalone is not None and path.name == standalone:
            return path
        if path.name.endswith(suffix):
            return path
    return None


def _compute_branch_name(
    config: dict,
    phase_number: str | None,
    phase_slug: str | None,
    milestone_version: str,
    milestone_slug: str | None,
) -> str | None:
    """Compute the git branch name based on branching strategy."""
    strategy = config.get("branching_strategy", "none")
    if strategy in ("per-phase", "phase") and phase_number:
        template = config.get("phase_branch_template", "gpd/phase-{phase}-{slug}")
        return template.replace("{phase}", phase_number).replace("{slug}", phase_slug or "phase")
    if strategy in ("per-milestone", "milestone"):
        template = config.get("milestone_branch_template", "gpd/{milestone}-{slug}")
        return template.replace("{milestone}", milestone_version).replace("{slug}", milestone_slug or "milestone")
    return None


def _load_project_contract(cwd: Path) -> tuple[ResearchContract | None, dict[str, object]]:
    """Load the canonical project contract and return load diagnostics."""
    contract, load_info = _state_module._load_project_contract_for_runtime_context(cwd)
    source_path = str(load_info.get("source_path") or "")
    if source_path.endswith(STATE_JSON_BACKUP_FILENAME):
        primary_state_path = ProjectLayout(cwd).state_json
        try:
            primary_payload = json.loads(primary_state_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            logger.warning(
                "Using project_contract from %s because the primary state.json was missing",
                source_path,
            )
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            logger.warning(
                "Using project_contract from %s because the primary state.json was unavailable or unreadable",
                source_path,
            )
        else:
            if not isinstance(primary_payload, dict):
                logger.warning(
                    "Using project_contract from %s because the primary state.json was unavailable or unreadable",
                    source_path,
                )
            elif any(
                "primary state.json was unavailable or unreadable" in str(item)
                for item in load_info.get("warnings") or []
            ):
                logger.warning(
                    "Using project_contract from %s because the primary state.json was unavailable or unreadable",
                    source_path,
                )
            elif any("primary state.json was missing" in str(item) for item in load_info.get("warnings") or []):
                logger.warning(
                    "Using project_contract from %s because the primary state.json was missing",
                    source_path,
                )
            else:
                logger.warning(
                    "Using project_contract from %s because the primary state.json was unavailable or unreadable",
                    source_path,
                )
    return contract, load_info


def _sorted_markdown_files(directory: Path) -> list[Path]:
    """Return markdown files in a directory, sorted by name."""
    try:
        return sorted(path for path in directory.iterdir() if path.is_file() and path.suffix == ".md")
    except FileNotFoundError:
        return []


def _preferred_review_dir(cwd: Path) -> Path | None:
    """Return the literature review directory, or ``None`` if it does not exist."""
    literature_dir = cwd / PLANNING_DIR_NAME / _LITERATURE_DIR_NAME
    if literature_dir.is_dir():
        return literature_dir
    return None


def _relative_posix(cwd: Path, path: Path) -> str:
    """Return a stable repo-relative POSIX path."""
    return path.relative_to(cwd).as_posix()


def _relative_or_absolute_posix(cwd: Path, path: Path | None) -> str | None:
    """Return a project-relative path when possible, else an absolute POSIX path."""

    if path is None:
        return None
    resolved_cwd = cwd.resolve(strict=False)
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(resolved_cwd).as_posix()
    except ValueError:
        return resolved_path.as_posix()


def _serialize_active_references(contract: ResearchContract | None) -> list[dict[str, object]]:
    """Return contract references ordered by planning relevance."""
    if contract is None:
        return []

    refs = sorted(
        contract.references,
        key=lambda ref: (
            0 if ref.must_surface else 1,
            _REFERENCE_ROLE_PRIORITY.get(ref.role, 99),
            ref.id,
        ),
    )
    serialized: list[dict[str, object]] = []
    for ref in refs:
        payload = ref.model_dump(mode="json")
        payload["source_kind"] = "project_contract"
        payload["source_artifacts"] = []
        serialized.append(payload)
    return serialized


def _append_unique_strings(target: list[str], values: list[object] | tuple[object, ...]) -> None:
    """Append string values without duplicating normalized entries."""
    for value in values:
        text = str(value).strip()
        if text and text not in target:
            target.append(text)


def _reference_identity_tokens(values: list[object]) -> set[str]:
    """Return normalized identity tokens for matching related anchor records."""
    tokens: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        normalized = re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()
        if normalized:
            tokens.add(normalized)
    return tokens


def _build_active_reference_lookup(
    active_references: list[dict[str, object]],
) -> tuple[dict[str, dict[str, object]], dict[str, str], set[str]]:
    """Return active-reference lookup tables and ambiguous token markers."""
    by_id: dict[str, dict[str, object]] = {}
    token_matches: dict[str, set[str]] = {}
    for ref in active_references:
        ref_id = str(ref.get("id") or "").strip()
        locator = str(ref.get("locator") or "").strip()
        if ref_id:
            by_id[ref_id] = ref
            token_matches.setdefault(ref_id.casefold(), set()).add(ref_id)
        if ref_id and locator:
            token_matches.setdefault(locator.casefold(), set()).add(ref_id)
        for alias in ref.get("aliases", []):
            alias_text = str(alias).strip()
            if alias_text and ref_id:
                token_matches.setdefault(alias_text.casefold(), set()).add(ref_id)
    token_to_id: dict[str, str] = {}
    ambiguous_tokens: set[str] = set()
    for token, ref_ids in token_matches.items():
        if len(ref_ids) == 1:
            token_to_id[token] = next(iter(ref_ids))
        elif len(ref_ids) > 1:
            ambiguous_tokens.add(token)
    return by_id, token_to_id, ambiguous_tokens


def _resolve_reference_token(
    token: object,
    *,
    token_to_id: dict[str, str],
    ambiguous_tokens: set[str],
) -> str:
    """Resolve a reference token without collapsing ambiguous aliases or locators."""
    token_text = str(token).strip()
    if not token_text:
        return token_text
    token_key = token_text.casefold()
    if token_key in ambiguous_tokens:
        return token_text
    return token_to_id.get(token_key, token_text)


def _must_surface_flag(value: object) -> bool:
    """Return a strict must-surface flag without truthy string coercion."""
    return type(value) is bool and value


def _merge_reference_record(merged: dict[str, dict[str, object]], ref: dict[str, object]) -> None:
    """Merge one active-reference record into the merged registry."""
    ref_id = str(ref.get("id") or "").strip()
    locator = str(ref.get("locator") or "").strip()
    target = merged.get(ref_id) if ref_id else None

    if target is None and locator:
        locator_key = locator.casefold()
        for candidate in merged.values():
            if str(candidate.get("locator") or "").strip().casefold() == locator_key:
                target = candidate
                break
    if target is None:
        payload = dict(ref)
        payload["required_actions"] = list(ref.get("required_actions") or [])
        payload["applies_to"] = list(ref.get("applies_to") or [])
        payload["carry_forward_to"] = list(ref.get("carry_forward_to") or [])
        payload["source_artifacts"] = list(ref.get("source_artifacts") or [])
        payload["aliases"] = list(ref.get("aliases") or [])
        payload["must_surface"] = _must_surface_flag(ref.get("must_surface"))
        if ref_id:
            merged[ref_id] = payload
        else:
            merged[f"derived-{len(merged) + 1:03d}"] = payload
        return

    if ref_id and ref_id != str(target.get("id") or "").strip():
        _append_unique_strings(target.setdefault("aliases", []), [ref_id])

    if str(ref.get("kind") or "").strip() and str(target.get("kind") or "other").strip() == "other":
        incoming_kind = str(ref.get("kind") or "").strip()
        if incoming_kind != "other":
            target["kind"] = incoming_kind
    if str(ref.get("role") or "").strip() and str(target.get("role") or "other").strip() == "other":
        target["role"] = ref.get("role")
    why = str(ref.get("why_it_matters") or "").strip()
    if why:
        existing_why = str(target.get("why_it_matters") or "").strip()
        if existing_why and why not in existing_why:
            target["why_it_matters"] = f"{existing_why}; {why}"
        elif not existing_why:
            target["why_it_matters"] = why
    _append_unique_strings(target.setdefault("required_actions", []), list(ref.get("required_actions") or []))
    _append_unique_strings(target.setdefault("applies_to", []), list(ref.get("applies_to") or []))
    _append_unique_strings(target.setdefault("carry_forward_to", []), list(ref.get("carry_forward_to") or []))
    _append_unique_strings(target.setdefault("source_artifacts", []), list(ref.get("source_artifacts") or []))
    _append_unique_strings(target.setdefault("aliases", []), list(ref.get("aliases") or []))
    target["must_surface"] = _must_surface_flag(target.get("must_surface")) or _must_surface_flag(
        ref.get("must_surface")
    )


def _merge_active_references(
    contract_references: list[dict[str, object]],
    derived_references: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Merge contract-backed and artifact-derived references into one registry."""
    merged: dict[str, dict[str, object]] = {}
    for ref in contract_references:
        _merge_reference_record(merged, ref)
    for ref in derived_references:
        _merge_reference_record(merged, ref)
    return sorted(
        merged.values(),
        key=lambda ref: (
            0 if ref.get("must_surface") else 1,
            _REFERENCE_ROLE_PRIORITY.get(str(ref.get("role") or "other"), 99),
            str(ref.get("id") or ""),
        ),
    )


def _merge_reference_intake(
    contract: ResearchContract | None,
    derived_intake: dict[str, list[str]],
    active_references: list[dict[str, object]],
) -> dict[str, list[str]]:
    """Return the effective carry-forward intake from contract + parsed artifacts."""
    merged = _empty_reference_intake()
    _, token_to_id, ambiguous_tokens = _build_active_reference_lookup(active_references)
    if contract is not None:
        intake = contract.context_intake.model_dump(mode="json")
        for key in merged:
            _append_unique_strings(merged[key], list(intake.get(key) or []))
    for key in merged:
        _append_unique_strings(merged[key], list(derived_intake.get(key) or []))
    canonical_must_read_refs: list[str] = []
    for token in merged["must_read_refs"]:
        resolved = _resolve_reference_token(
            token,
            token_to_id=token_to_id,
            ambiguous_tokens=ambiguous_tokens,
        )
        _append_unique_strings(canonical_must_read_refs, [resolved])
    merged["must_read_refs"] = canonical_must_read_refs
    return merged


def _empty_reference_intake() -> dict[str, list[str]]:
    return {field_name: [] for field_name in CONTRACT_CONTEXT_INTAKE_FIELD_NAMES}


def _canonical_contract_intake(
    contract: ResearchContract,
    *,
    active_references: list[dict[str, object]],
    effective_reference_intake: dict[str, list[str]],
) -> dict[str, list[str]]:
    """Return additive canonical intake with canonicalized reference IDs."""

    del effective_reference_intake  # Artifact-derived intake stays in ``effective_reference_intake`` only.

    intake = contract.context_intake.model_dump(mode="json")
    _, token_to_id, ambiguous_tokens = _build_active_reference_lookup(active_references)
    canonical_must_read_refs: list[str] = []
    for token in list(intake.get("must_read_refs") or []):
        resolved = _resolve_reference_token(
            token,
            token_to_id=token_to_id,
            ambiguous_tokens=ambiguous_tokens,
        )
        _append_unique_strings(canonical_must_read_refs, [resolved])
    intake["must_read_refs"] = canonical_must_read_refs
    return intake


def _canonicalize_project_contract(
    contract: ResearchContract | None,
    *,
    active_references: list[dict[str, object]],
    effective_reference_intake: dict[str, list[str]],
) -> tuple[ResearchContract | None, list[str]]:
    """Return the canonical contract after intake-token normalization."""

    if contract is None:
        return None, []

    payload = contract.model_dump(mode="json")
    payload["context_intake"] = _canonical_contract_intake(
        contract,
        active_references=active_references,
        effective_reference_intake=effective_reference_intake,
    )
    try:
        parsed = parse_project_contract_data_salvage(payload)
    except Exception as exc:
        warning = f"canonical project_contract merge failed unexpectedly; keeping original contract: {exc}"
        logger.warning(warning)
        return contract, [warning]

    if parsed.contract is None or parsed.blocking_errors:
        validation_errors = parsed.blocking_errors or ["project contract could not be normalized"]
        warning = "canonical project_contract merge failed validation; keeping original contract: " + "; ".join(
            validation_errors
        )
        logger.warning(warning)
        return contract, [warning]

    warnings: list[str] = []
    if parsed.recoverable_errors:
        warning = "canonical project_contract merge required salvage; keeping canonicalized contract: " + "; ".join(
            parsed.recoverable_errors
        )
        logger.warning(warning)
        warnings.append(warning)
    return parsed.contract, warnings


def _render_active_reference_context(
    active_references: list[dict[str, object]],
    effective_intake: dict[str, list[str]],
    stable_knowledge_doc_files: list[str],
    knowledge_doc_status_counts: dict[str, int],
    literature_review_files: list[str],
    research_map_reference_files: list[str],
    contract_validation: dict[str, object] | None = None,
    contract_load_info: dict[str, object] | None = None,
) -> str:
    """Render a compact text block of anchors and carry-forward inputs."""
    lines: list[str] = ["## Active Reference Registry"]
    refs_by_id, _, _ = _build_active_reference_lookup(active_references)

    if active_references:
        for ref in active_references:
            actions = ", ".join(str(action) for action in ref.get("required_actions", [])) or "review"
            applies_to = ", ".join(str(item) for item in ref.get("applies_to", [])) or "global"
            carry_forward_to = ", ".join(str(item) for item in ref.get("carry_forward_to", []))
            kind = str(ref.get("kind") or "other")
            must_surface = " | must surface" if ref.get("must_surface") else ""
            carry_forward_note = f" | carry forward: {carry_forward_to}" if carry_forward_to else ""
            source_artifacts = ", ".join(str(item) for item in ref.get("source_artifacts", []) if item)
            source_note = f" | source: {source_artifacts}" if source_artifacts else ""
            lines.append(
                f"- [{ref['id']}] {ref['locator']} | kind: {kind} | role: {ref['role']}{must_surface} | "
                f"actions: {actions} | applies_to: {applies_to}{carry_forward_note} | "
                f"why: {ref['why_it_matters']}{source_note}"
            )
    else:
        if stable_knowledge_doc_files or literature_review_files or research_map_reference_files:
            lines.append("- No structured anchors parsed yet; raw reference artifacts are available below.")
        else:
            lines.append("- None confirmed in `state.json.project_contract.references` yet.")

    if contract_load_info is not None:
        load_status = str(contract_load_info.get("status") or "").strip()
        load_warnings = list(contract_load_info.get("warnings") or [])
        load_errors = list(contract_load_info.get("errors") or [])
        if load_status.startswith("blocked") or load_warnings:
            lines.extend(["", "## Project Contract Intake"])
            lines.append(f"- Load status: {load_status.replace('_', ' ')}")
            source_path = str(contract_load_info.get("source_path") or "").strip()
            if source_path:
                lines.append(f"- Source: {source_path}")
            for error in load_errors:
                lines.append(f"- Blocker: {error}")
            _append_contract_warnings(lines, load_warnings)

    if contract_validation is not None:
        lines.extend(["", "## Project Contract Validation"])
        if contract_validation.get("valid") is True:
            lines.append("- Approval status: ready")
        else:
            lines.append("- Approval status: blocked")
            lines.append(
                "- Carry-forward anchors below remain visible for continuity, but approved-contract scope stays blocked until the contract is repaired."
            )
        for error in list(contract_validation.get("errors") or []):
            lines.append(f"- Blocker: {error}")
        _append_contract_warnings(lines, list(contract_validation.get("warnings") or []))

    lines.extend(
        [
            "",
            "## Carry-Forward Inputs",
            "### Must-Read References",
        ]
    )
    if effective_intake["must_read_refs"]:
        for item in effective_intake["must_read_refs"]:
            ref = refs_by_id.get(item)
            if ref is None:
                lines.append(f"- {item} | unresolved reference token")
                continue
            actions = ", ".join(str(action) for action in ref.get("required_actions", [])) or "review"
            lines.append(f"- [{item}] {ref['locator']} | actions: {actions} | role: {ref.get('role', 'other')}")
    else:
        lines.append("- None confirmed yet.")

    lines.append("")
    lines.append("### Prior Outputs and Baselines")
    if effective_intake["must_include_prior_outputs"]:
        lines.extend(f"- {item}" for item in effective_intake["must_include_prior_outputs"])
    else:
        lines.append("- None confirmed yet.")
    if effective_intake["known_good_baselines"]:
        lines.extend(f"- Baseline: {item}" for item in effective_intake["known_good_baselines"])
    if effective_intake["crucial_inputs"]:
        lines.extend(f"- Crucial input: {item}" for item in effective_intake["crucial_inputs"])

    lines.append("")
    lines.append("### User-Asserted Anchors and Gaps")
    if effective_intake["user_asserted_anchors"]:
        lines.extend(f"- Anchor: {item}" for item in effective_intake["user_asserted_anchors"])
    else:
        lines.append("- No additional user-asserted anchors recorded.")
    if effective_intake["context_gaps"]:
        lines.extend(f"- Gap: {item}" for item in effective_intake["context_gaps"])

    lines.append("")
    lines.append("## Stable Knowledge Documents")
    if stable_knowledge_doc_files:
        lines.extend(f"- Knowledge doc: {path}" for path in stable_knowledge_doc_files)
    else:
        lines.append("- No runtime-active stable knowledge docs found yet.")
    suppressed_count = sum(count for status, count in knowledge_doc_status_counts.items() if status != "stable")
    if suppressed_count:
        lines.append(
            f"- {suppressed_count} non-stable knowledge doc(s) remain inventory-visible only and are excluded from active carry-forward context."
        )

    lines.append("")
    lines.append("## Reference Artifacts Available")
    if stable_knowledge_doc_files:
        lines.extend(f"- Stable knowledge: {path}" for path in stable_knowledge_doc_files)
    if literature_review_files:
        lines.extend(f"- Literature review: {path}" for path in literature_review_files)
    if research_map_reference_files:
        lines.extend(f"- Research map: {path}" for path in research_map_reference_files)
    if not stable_knowledge_doc_files and not literature_review_files and not research_map_reference_files:
        lines.append("- No stable knowledge, literature-review, or research-map anchor artifacts found yet.")

    return "\n".join(lines)


_NON_DURABLE_CONTRACT_WARNING_FRAGMENTS = (
    "entry does not resolve to a project-local artifact:",
    "entry is not an explicit project artifact path:",
    "entry is not concrete enough to preserve as durable guidance:",
    "entry is only a placeholder and does not preserve actionable guidance:",
)


def _append_contract_warnings(lines: list[str], warnings: list[str]) -> None:
    suppressed_nondurable_warnings = 0
    for warning in warnings:
        if any(fragment in warning for fragment in _NON_DURABLE_CONTRACT_WARNING_FRAGMENTS):
            suppressed_nondurable_warnings += 1
            continue
        lines.append(f"- Warning: {warning}")
    if not suppressed_nondurable_warnings:
        return
    noun = "warning" if suppressed_nondurable_warnings == 1 else "warnings"
    verb = "was" if suppressed_nondurable_warnings == 1 else "were"
    lines.append(
        f"- Warning: {suppressed_nondurable_warnings} non-durable contract-intake {noun} {verb} collapsed during normalization."
    )


def _reference_artifact_payload(cwd: Path, *, include_content: bool = True) -> dict[str, object]:
    """Collect durable reference artifacts for downstream planning and verification."""
    review_dir = _preferred_review_dir(cwd)
    literature_paths = _sorted_markdown_files(review_dir) if review_dir is not None else []
    research_map_dir = cwd / PLANNING_DIR_NAME / RESEARCH_MAP_DIR_NAME
    research_map_paths = _sorted_markdown_files(research_map_dir)
    knowledge_inventory = discover_knowledge_docs(cwd)
    prioritized_research_map_paths = [
        research_map_dir / name for name in _REFERENCE_MAP_DOCS if (research_map_dir / name).is_file()
    ]
    prioritized_names = {path.name for path in prioritized_research_map_paths}
    prioritized_research_map_paths.extend(path for path in research_map_paths if path.name not in prioritized_names)

    literature_review_files = [_relative_posix(cwd, path) for path in literature_paths]
    research_map_reference_files = [_relative_posix(cwd, path) for path in prioritized_research_map_paths]
    knowledge_doc_files = [record.path for record in knowledge_inventory.records]
    stable_knowledge_doc_files = [
        record.path for record in knowledge_inventory.records if record.status == "stable" and record.is_fresh_approved
    ]
    stable_knowledge_paths = [cwd / rel_path for rel_path in stable_knowledge_doc_files]
    knowledge_doc_status_counts = knowledge_inventory.status_counts()

    content_sections: list[str] = []
    if include_content:
        selected_artifacts = [
            *stable_knowledge_paths[:_KNOWLEDGE_INCLUDE_LIMIT],
            *prioritized_research_map_paths[:_RESEARCH_MAP_INCLUDE_LIMIT],
            *literature_paths[:_LITERATURE_INCLUDE_LIMIT],
        ]
        for path in selected_artifacts:
            content = _safe_read_file_truncated(path)
            if not content:
                continue
            content_sections.append(f"## {path.relative_to(cwd).as_posix()}\n{content}")

    return {
        "literature_review_files": literature_review_files,
        "literature_review_count": len(literature_review_files),
        "research_map_reference_files": research_map_reference_files,
        "research_map_reference_count": len(research_map_reference_files),
        "knowledge_doc_files": knowledge_doc_files,
        "knowledge_doc_count": len(knowledge_doc_files),
        "stable_knowledge_doc_files": stable_knowledge_doc_files,
        "stable_knowledge_doc_count": len(stable_knowledge_doc_files),
        "knowledge_doc_status_counts": knowledge_doc_status_counts,
        "reference_artifact_files": [
            *stable_knowledge_doc_files,
            *research_map_reference_files,
            *literature_review_files,
        ],
        "reference_artifacts_content": "\n\n".join(content_sections) if content_sections else None,
    }


def _protocol_bundle_verifier_extensions(
    selected_protocol_bundles: list[ResolvedProtocolBundle],
) -> list[dict[str, object]]:
    bundle_verifier_extensions: list[dict[str, object]] = []
    for bundle in selected_protocol_bundles:
        for extension in bundle.verifier_extensions:
            bundle_verifier_extensions.append(
                {
                    "bundle_id": bundle.bundle_id,
                    "bundle_title": bundle.title,
                    **extension.model_dump(mode="json"),
                }
            )
    return bundle_verifier_extensions


def _build_execute_phase_task_overlay_context() -> dict[str, object]:
    """Build the metadata-only executor overlay handles for execute-phase fanout."""
    selected_ids = list(_EXECUTE_PHASE_EXECUTOR_TASK_OVERLAY_IDS)
    return {
        "selected_task_overlay_ids": selected_ids,
        "task_overlay_load_manifest": build_task_overlay_load_manifest(
            selected_ids,
            role="gpd-executor",
            selection_source=_EXECUTE_PHASE_TASK_OVERLAY_SELECTION_SOURCE,
        ),
        "task_overlay_policy_summary": _EXECUTE_PHASE_TASK_OVERLAY_POLICY_SUMMARY,
    }


def _build_reference_runtime_context(
    cwd: Path,
    *,
    include_artifact_content: bool = True,
    include_protocol_context: bool = True,
    include_active_reference_context: bool = True,
    persist_manuscript_proof_review_manifest: bool = False,
) -> dict[str, object]:
    """Build shared reference/anchor context for workflow init payloads."""
    contract, project_contract_load_info = _load_project_contract(cwd)
    state_obj, _state_issues, _state_source = _peek_state_json(
        cwd,
        recover_intent=False,
        acquire_lock=False,
    )
    artifact_payload = _reference_artifact_payload(cwd, include_content=include_artifact_content)
    artifact_ingestion = ingest_reference_artifacts(
        cwd,
        literature_review_files=list(artifact_payload["literature_review_files"]),
        research_map_reference_files=list(artifact_payload["research_map_reference_files"]),
        knowledge_doc_files=list(artifact_payload["stable_knowledge_doc_files"]),
    )
    manuscript_reference_status = ingest_manuscript_reference_status(cwd)
    manuscript_proof_review_status = resolve_manuscript_proof_review_status(
        cwd,
        persist_manifest=persist_manuscript_proof_review_manifest,
    )
    derived_references = [ref.to_context_dict() for ref in artifact_ingestion.references]
    derived_knowledge_docs = [record.to_context_dict() for record in artifact_ingestion.knowledge_docs]
    derived_citation_sources = [item.to_context_dict() for item in artifact_ingestion.citation_sources]
    derived_manuscript_reference_status = {
        record.reference_id: record.to_context_dict() for record in manuscript_reference_status.reference_status
    }
    active_references = _merge_active_references(_serialize_active_references(contract), derived_references)
    effective_reference_intake = _merge_reference_intake(
        contract,
        artifact_ingestion.intake.to_dict(),
        active_references,
    )
    visible_contract, canonicalization_warnings = _canonicalize_project_contract(
        contract,
        active_references=active_references,
        effective_reference_intake=effective_reference_intake,
    )
    if canonicalization_warnings:
        project_contract_load_info = {
            **project_contract_load_info,
            "warnings": [*list(project_contract_load_info.get("warnings") or []), *canonicalization_warnings],
        }
    project_contract_load_info, project_contract_validation, project_contract_gate = _finalize_project_contract_gate(
        cwd,
        visible_contract,
        project_contract_load_info,
        state_obj=state_obj if isinstance(state_obj, dict) else None,
    )
    project_text = _safe_read_file(cwd / PLANNING_DIR_NAME / PROJECT_FILENAME)
    visible_context_contract = None
    if project_contract_gate.get("visible"):
        visible_context_contract = visible_contract if project_contract_gate.get("authoritative") else contract
    surfaced_contract_intake = None
    if project_contract_gate.get("visible") and visible_contract is not None:
        surfaced_contract_intake = visible_contract.context_intake.model_dump(mode="json")
    authoritative_contract = visible_contract if project_contract_gate.get("authoritative") else None
    carry_forward_reference_contract = (
        visible_contract
        if authoritative_contract is not None or project_contract_gate.get("approval_blocked")
        else None
    )
    surfaced_active_references = _merge_active_references(
        _serialize_active_references(carry_forward_reference_contract),
        derived_references,
    )
    surfaced_effective_reference_intake = _merge_reference_intake(
        carry_forward_reference_contract,
        artifact_ingestion.intake.to_dict(),
        surfaced_active_references,
    )
    selected_protocol_bundles = select_protocol_bundles(project_text, authoritative_contract)
    protocol_bundle_load_manifest = build_protocol_bundle_load_manifest(selected_protocol_bundles)
    bundle_verifier_extensions = _protocol_bundle_verifier_extensions(selected_protocol_bundles)

    return {
        "project_contract": visible_context_contract.model_dump(mode="json")
        if visible_context_contract is not None
        else None,
        "project_contract_validation": project_contract_validation,
        "project_contract_load_info": project_contract_load_info,
        "project_contract_gate": project_contract_gate,
        "contract_intake": surfaced_contract_intake,
        "effective_reference_intake": surfaced_effective_reference_intake,
        "derived_active_references": derived_references,
        "derived_active_reference_count": len(derived_references),
        "derived_knowledge_docs": derived_knowledge_docs,
        "derived_knowledge_doc_count": len(derived_knowledge_docs),
        "knowledge_doc_warnings": list(artifact_ingestion.knowledge_doc_warnings),
        "citation_source_files": list(artifact_ingestion.citation_source_files),
        "citation_source_count": len(artifact_ingestion.citation_source_files),
        "citation_source_warnings": list(artifact_ingestion.citation_source_warnings),
        "derived_citation_sources": derived_citation_sources,
        "derived_citation_source_count": len(derived_citation_sources),
        "derived_manuscript_reference_status": derived_manuscript_reference_status,
        "derived_manuscript_reference_status_count": len(derived_manuscript_reference_status),
        "derived_manuscript_proof_review_status": manuscript_proof_review_status.to_context_dict(cwd),
        "active_references": surfaced_active_references,
        "active_reference_count": len(surfaced_active_references),
        "selected_protocol_bundle_ids": [bundle.bundle_id for bundle in selected_protocol_bundles],
        "protocol_bundle_count": len(selected_protocol_bundles),
        "protocol_bundle_load_manifest": protocol_bundle_load_manifest,
        "protocol_bundle_verifier_extensions": bundle_verifier_extensions,
        "protocol_bundle_context": render_protocol_bundle_context(selected_protocol_bundles)
        if include_protocol_context
        else None,
        "active_reference_context": _render_active_reference_context(
            surfaced_active_references,
            surfaced_effective_reference_intake,
            list(artifact_payload["stable_knowledge_doc_files"]),
            dict(artifact_payload["knowledge_doc_status_counts"]),
            artifact_payload["literature_review_files"],
            artifact_payload["research_map_reference_files"],
            project_contract_validation,
            project_contract_load_info,
        )
        if include_active_reference_context
        else "",
        **artifact_payload,
    }


def _build_new_project_contract_runtime_context(cwd: Path) -> dict[str, object]:
    """Build only the contract/gate payload needed during new-project bootstrap."""
    contract, project_contract_load_info = _load_project_contract(cwd)
    project_contract_load_info, project_contract_validation, project_contract_gate = _finalize_project_contract_gate(
        cwd,
        contract,
        project_contract_load_info,
        state_obj=None,
    )
    return {
        "project_contract": contract.model_dump(mode="json") if project_contract_gate.get("visible") else None,
        "project_contract_validation": project_contract_validation,
        "project_contract_load_info": project_contract_load_info,
        "project_contract_gate": project_contract_gate,
    }


def _build_contract_reference_runtime_context(
    cwd: Path,
    *,
    include_protocol_context: bool = True,
    include_active_reference_context: bool = True,
) -> dict[str, object]:
    """Build contract-derived reference context without scanning durable reference artifacts."""
    contract, project_contract_load_info = _load_project_contract(cwd)
    contract_references = _serialize_active_references(contract)
    effective_reference_intake = _merge_reference_intake(contract, {}, contract_references)
    visible_contract, canonicalization_warnings = _canonicalize_project_contract(
        contract,
        active_references=contract_references,
        effective_reference_intake=effective_reference_intake,
    )
    if canonicalization_warnings:
        project_contract_load_info = {
            **project_contract_load_info,
            "warnings": [*list(project_contract_load_info.get("warnings") or []), *canonicalization_warnings],
        }
    project_contract_load_info, project_contract_validation, project_contract_gate = _finalize_project_contract_gate(
        cwd,
        visible_contract,
        project_contract_load_info,
        state_obj=None,
    )

    visible_context_contract = None
    if project_contract_gate.get("visible"):
        visible_context_contract = visible_contract if project_contract_gate.get("authoritative") else contract
    surfaced_contract_intake = None
    if project_contract_gate.get("visible") and visible_contract is not None:
        surfaced_contract_intake = visible_contract.context_intake.model_dump(mode="json")
    authoritative_contract = visible_contract if project_contract_gate.get("authoritative") else None
    carry_forward_reference_contract = (
        visible_contract
        if authoritative_contract is not None or project_contract_gate.get("approval_blocked")
        else None
    )
    surfaced_active_references = _merge_active_references(
        _serialize_active_references(carry_forward_reference_contract),
        [],
    )
    surfaced_effective_reference_intake = _merge_reference_intake(
        carry_forward_reference_contract,
        {},
        surfaced_active_references,
    )
    project_text = _safe_read_file(cwd / PLANNING_DIR_NAME / PROJECT_FILENAME)
    selected_protocol_bundles = select_protocol_bundles(project_text, authoritative_contract)
    protocol_bundle_load_manifest = build_protocol_bundle_load_manifest(selected_protocol_bundles)
    bundle_verifier_extensions = _protocol_bundle_verifier_extensions(selected_protocol_bundles)

    return {
        "project_contract": visible_context_contract.model_dump(mode="json")
        if visible_context_contract is not None
        else None,
        "project_contract_validation": project_contract_validation,
        "project_contract_load_info": project_contract_load_info,
        "project_contract_gate": project_contract_gate,
        "contract_intake": surfaced_contract_intake,
        "effective_reference_intake": surfaced_effective_reference_intake,
        "active_references": surfaced_active_references,
        "active_reference_count": len(surfaced_active_references),
        "selected_protocol_bundle_ids": [bundle.bundle_id for bundle in selected_protocol_bundles],
        "protocol_bundle_count": len(selected_protocol_bundles),
        "protocol_bundle_load_manifest": protocol_bundle_load_manifest,
        "protocol_bundle_verifier_extensions": bundle_verifier_extensions,
        "protocol_bundle_context": render_protocol_bundle_context(selected_protocol_bundles)
        if include_protocol_context
        else None,
        "active_reference_context": _render_active_reference_context(
            surfaced_active_references,
            surfaced_effective_reference_intake,
            [],
            {},
            [],
            [],
            project_contract_validation,
            project_contract_load_info,
        )
        if include_active_reference_context
        else "",
    }


def _build_staged_reference_runtime_context(
    cwd: Path,
    reference_fields: set[str] | frozenset[str],
    *,
    persist_manuscript_proof_review_manifest: bool = False,
) -> dict[str, object]:
    """Build the smallest reference context tier needed by a staged init payload."""
    selected_reference_fields = frozenset(reference_fields)
    if not selected_reference_fields:
        return {}
    rendered_context_fields = selected_reference_fields & _STAGED_REFERENCE_RENDERED_CONTEXT_FIELDS
    include_protocol_context = "protocol_bundle_context" in rendered_context_fields
    include_active_reference_context = "active_reference_context" in rendered_context_fields
    include_artifact_content = bool(selected_reference_fields & _STAGED_REFERENCE_BODY_FIELDS)
    if selected_reference_fields <= _STAGED_REFERENCE_SUMMARY_FIELDS:
        return _build_contract_reference_runtime_context(
            cwd,
            include_protocol_context=include_protocol_context,
            include_active_reference_context=include_active_reference_context,
        )
    # Artifact handle/status fields require artifact discovery and structured
    # status ingestion, but body/rendered hydration remains opt-in per field.
    return _build_reference_runtime_context(
        cwd,
        include_artifact_content=include_artifact_content,
        include_protocol_context=include_protocol_context,
        include_active_reference_context=include_active_reference_context,
        persist_manuscript_proof_review_manifest=persist_manuscript_proof_review_manifest,
    )


def _write_paper_external_authoring_bootstrap_context(
    cwd: Path,
    intake_resolution: WritePaperExternalAuthoringIntakeResolution,
) -> dict[str, object]:
    """Return publication bootstrap fields owned by a validated external intake."""

    subject_slug = intake_resolution.subject_slug
    if not subject_slug:
        raise ValueError("resolved write-paper external authoring intake is missing a subject slug")

    layout = ProjectLayout(cwd)
    managed_publication_root = layout.publication_subject_dir(subject_slug)
    managed_manuscript_root = intake_resolution.manuscript_root or layout.publication_manuscript_dir(subject_slug)
    managed_intake_root = intake_resolution.intake_root or layout.publication_intake_dir(subject_slug)
    selected_roots = _selected_publication_stage_roots(
        publication_subject_slug=subject_slug,
        publication_lane_kind="managed_publication_manuscript",
        managed_publication_root=_relative_or_absolute_posix(cwd, managed_publication_root),
    )
    review_root = selected_roots["selected_review_root"]
    publication_subject = {
        "status": "bootstrap",
        "source": "explicit_intake_manifest",
        "detail": intake_resolution.detail,
        "target_path": _relative_or_absolute_posix(cwd, intake_resolution.intake_path),
        "artifact_base": _relative_or_absolute_posix(cwd, managed_manuscript_root),
        "publication_root": _relative_or_absolute_posix(cwd, managed_publication_root),
        "review_dir": review_root,
        "manuscript_root": _relative_or_absolute_posix(cwd, managed_manuscript_root),
        "manuscript_entrypoint": None,
        "artifact_manifest": None,
        "bibliography_audit": None,
        "reproducibility_manifest": None,
        "publication_subject_slug": subject_slug,
        "publication_lane_kind": "managed_publication_manuscript",
        "publication_lane_owner": "external_authoring_intake",
        "managed_publication_root": _relative_or_absolute_posix(cwd, managed_publication_root),
        "managed_intake_root": _relative_or_absolute_posix(cwd, managed_intake_root),
        "managed_manuscript_root": _relative_or_absolute_posix(cwd, managed_manuscript_root),
        "path_semantics": None,
    }
    bootstrap_payload = {
        "mode": "fresh_project_bootstrap",
        "detail": intake_resolution.detail,
        "bootstrap_root": _relative_or_absolute_posix(cwd, managed_manuscript_root),
    }
    return {
        "publication_subject": publication_subject,
        "publication_subject_status": "bootstrap",
        "publication_subject_source": "explicit_intake_manifest",
        "publication_subject_detail": intake_resolution.detail,
        "publication_subject_slug": subject_slug,
        "publication_lane_kind": "managed_publication_manuscript",
        "publication_lane_owner": "external_authoring_intake",
        "publication_artifact_base": _relative_or_absolute_posix(cwd, managed_manuscript_root),
        "publication_root": _relative_or_absolute_posix(cwd, managed_publication_root),
        "review_dir": review_root,
        "manuscript_resolution_status": "missing",
        "manuscript_resolution_detail": (
            "validated external authoring intake; manuscript scaffold has not been authored yet"
        ),
        "manuscript_root": _relative_or_absolute_posix(cwd, managed_manuscript_root),
        "manuscript_entrypoint": None,
        "artifact_manifest_path": None,
        "bibliography_audit_path": None,
        "reproducibility_manifest_path": None,
        "managed_publication_root": _relative_or_absolute_posix(cwd, managed_publication_root),
        "managed_intake_root": _relative_or_absolute_posix(cwd, managed_intake_root),
        "managed_manuscript_root": _relative_or_absolute_posix(cwd, managed_manuscript_root),
        **selected_roots,
        "publication_intake_root": _relative_or_absolute_posix(cwd, managed_intake_root),
        "publication_bootstrap": bootstrap_payload,
        "publication_bootstrap_mode": bootstrap_payload["mode"],
        "publication_bootstrap_root": bootstrap_payload["bootstrap_root"],
        "publication_bootstrap_detail": bootstrap_payload["detail"],
    }


def _build_publication_bootstrap_runtime_context(
    cwd: Path,
    *,
    external_authoring_intake: WritePaperExternalAuthoringIntakeResolution | None = None,
    include_protocol_context: bool = True,
    include_active_reference_context: bool = True,
    persist_manuscript_proof_review_manifest: bool = False,
) -> dict[str, object]:
    """Build the lightweight contract/bundle/manuscript-status payload for publication bootstrap."""
    publication_subject = resolve_current_publication_subject(cwd, allow_markdown=True)
    publication_bootstrap = resolve_publication_bootstrap_resolution(cwd, allow_markdown=True)
    contract, project_contract_load_info = _load_project_contract(cwd)
    derived_references = _serialize_active_references(contract)
    effective_reference_intake = _merge_reference_intake(contract, {}, derived_references)
    visible_contract, canonicalization_warnings = _canonicalize_project_contract(
        contract,
        active_references=derived_references,
        effective_reference_intake=effective_reference_intake,
    )
    if canonicalization_warnings:
        project_contract_load_info = {
            **project_contract_load_info,
            "warnings": [*list(project_contract_load_info.get("warnings") or []), *canonicalization_warnings],
        }
    project_contract_load_info, project_contract_validation, project_contract_gate = _finalize_project_contract_gate(
        cwd,
        visible_contract,
        project_contract_load_info,
        state_obj=None,
    )
    visible_context_contract = None
    if project_contract_gate.get("visible"):
        visible_context_contract = visible_contract if project_contract_gate.get("authoritative") else contract
    authoritative_contract = visible_contract if project_contract_gate.get("authoritative") else None
    carry_forward_reference_contract = (
        visible_contract
        if authoritative_contract is not None or project_contract_gate.get("approval_blocked")
        else None
    )
    surfaced_active_references = _merge_active_references(
        _serialize_active_references(carry_forward_reference_contract),
        [],
    )
    surfaced_effective_reference_intake = _merge_reference_intake(
        carry_forward_reference_contract,
        {},
        surfaced_active_references,
    )
    project_text = _safe_read_file(cwd / PLANNING_DIR_NAME / PROJECT_FILENAME)
    selected_protocol_bundles = select_protocol_bundles(project_text, authoritative_contract)
    protocol_bundle_load_manifest = build_protocol_bundle_load_manifest(selected_protocol_bundles)
    manuscript_reference_status = ingest_manuscript_reference_status(cwd, publication_subject=publication_subject)
    manuscript_proof_review_status = resolve_manuscript_proof_review_status(
        cwd,
        publication_subject.manuscript_entrypoint,
        persist_manifest=persist_manuscript_proof_review_manifest,
    )
    derived_manuscript_reference_status = {
        record.reference_id: record.to_context_dict() for record in manuscript_reference_status.reference_status
    }
    publication_bootstrap_payload = publication_bootstrap.to_context_dict()
    publication_context = publication_subject.to_bootstrap_context_dict()
    selected_roots = _selected_publication_stage_roots(
        publication_subject_slug=publication_context.get("publication_subject_slug")
        if isinstance(publication_context.get("publication_subject_slug"), str)
        else None,
        publication_lane_kind=publication_context.get("publication_lane_kind")
        if isinstance(publication_context.get("publication_lane_kind"), str)
        else None,
        managed_publication_root=publication_context.get("managed_publication_root")
        if isinstance(publication_context.get("managed_publication_root"), str)
        else None,
    )
    if external_authoring_intake is not None:
        publication_context = _write_paper_external_authoring_bootstrap_context(
            cwd,
            external_authoring_intake,
        )
        publication_bootstrap = publication_context["publication_bootstrap"]
        publication_bootstrap_payload = publication_bootstrap if isinstance(publication_bootstrap, dict) else {}
        selected_roots = {
            "selected_publication_root": publication_context.get("selected_publication_root"),
            "selected_review_root": publication_context.get("selected_review_root"),
        }
    surfaced_contract_intake = None
    if project_contract_gate.get("visible") and visible_contract is not None:
        surfaced_contract_intake = visible_contract.context_intake.model_dump(mode="json")
    publication_intake_root = None
    managed_intake_root = publication_context.get("managed_intake_root")
    managed_publication_root = publication_context.get("managed_publication_root")
    if isinstance(managed_intake_root, str) and managed_intake_root:
        publication_intake_root = managed_intake_root
    elif isinstance(managed_publication_root, str) and managed_publication_root:
        publication_intake_root = f"{managed_publication_root}/intake"
    return {
        "project_contract": visible_context_contract.model_dump(mode="json")
        if visible_context_contract is not None
        else None,
        "project_contract_validation": project_contract_validation,
        "project_contract_load_info": project_contract_load_info,
        "project_contract_gate": project_contract_gate,
        "contract_intake": surfaced_contract_intake,
        "effective_reference_intake": surfaced_effective_reference_intake,
        **publication_context,
        **selected_roots,
        "publication_intake_root": publication_intake_root,
        "publication_bootstrap": publication_bootstrap_payload,
        "publication_bootstrap_mode": publication_bootstrap_payload["mode"],
        "publication_bootstrap_root": publication_bootstrap_payload["bootstrap_root"],
        "publication_bootstrap_detail": publication_bootstrap_payload["detail"],
        "selected_protocol_bundle_ids": [bundle.bundle_id for bundle in selected_protocol_bundles],
        "protocol_bundle_load_manifest": protocol_bundle_load_manifest,
        "protocol_bundle_context": render_protocol_bundle_context(selected_protocol_bundles)
        if include_protocol_context
        else None,
        "active_reference_context": _render_active_reference_context(
            surfaced_active_references,
            surfaced_effective_reference_intake,
            [],
            {},
            [],
            [],
            project_contract_validation,
            project_contract_load_info,
        )
        if include_active_reference_context
        else "",
        "derived_manuscript_reference_status": derived_manuscript_reference_status,
        "derived_manuscript_reference_status_count": len(derived_manuscript_reference_status),
        "derived_manuscript_proof_review_status": manuscript_proof_review_status.to_context_dict(cwd),
    }


def _extract_flag_value(argument_payload: str | None, flag: str) -> str | None:
    """Return the value for a launch flag carried through staged init."""

    if not isinstance(argument_payload, str) or not argument_payload.strip():
        return None
    try:
        tokens = shlex.split(argument_payload)
    except ValueError:
        tokens = argument_payload.split()
    for index, token in enumerate(tokens):
        if token == flag and index + 1 < len(tokens):
            return tokens[index + 1]
        prefix = f"{flag}="
        if token.startswith(prefix):
            return token[len(prefix) :]
    return None


def _write_paper_subject_from_launch_arguments(argument_payload: str | None) -> str | None:
    """Keep staged write-paper init from interpreting intake flags as manuscript paths."""

    if not isinstance(argument_payload, str):
        return None
    stripped = argument_payload.strip()
    if not stripped:
        return None
    try:
        tokens = shlex.split(stripped)
    except ValueError:
        tokens = stripped.split()
    if not tokens or tokens[0].startswith("--"):
        return None
    return stripped


def _respond_to_referees_subject_from_launch_arguments(argument_payload: str | None) -> str | None:
    """Resolve only the manuscript side of response-round launch arguments."""

    manuscript = _extract_flag_value(argument_payload, "--manuscript")
    if manuscript:
        return manuscript
    return None


_ARXIV_SUPPORTED_MANUSCRIPT_ROOTS_DETAIL = (
    "`paper/`, `manuscript/`, `draft/`, or `GPD/publication/<subject_slug>[/manuscript/]`"
)
_ARXIV_INVALID_EXTERNAL_SUBJECT_DETAIL = (
    f"explicit manuscript target must stay under {_ARXIV_SUPPORTED_MANUSCRIPT_ROOTS_DETAIL} inside the current project"
)


def _arxiv_invalid_external_subject_context(
    cwd: Path,
    subject_input: str,
    *,
    launch_cwd: Path,
) -> dict[str, object] | None:
    """Return a fail-closed arXiv context overlay for unsupported explicit targets."""

    if not subject_input.strip():
        return None

    requested_target = Path(subject_input.strip()).expanduser()
    if not requested_target.is_absolute():
        requested_target = launch_cwd / requested_target
    requested_target = requested_target.resolve(strict=False)

    if resolve_supported_manuscript_root_for_target(cwd, requested_target) is not None:
        return None

    target_label = _relative_or_absolute_posix(cwd, requested_target)
    freshness = {
        "policy": "conservative_all_response_artifacts",
        "latest_review_round": None,
        "latest_review_round_suffix": None,
        "latest_response_round": None,
        "latest_response_round_suffix": None,
        "requires_fresh_review": False,
        "required_review_round": None,
        "required_review_round_suffix": None,
        "detail": "no response artifacts considered because the explicit arxiv-submission target is invalid",
    }
    proof_review_status = {
        "scope": "manuscript",
        "state": "not_reviewed",
        "can_rely_on_prior_review": False,
        "detail": "no proof-review freshness is available for an invalid explicit arxiv-submission target",
        "manifest_path": None,
        "anchor_artifact": None,
        "watched_files": [],
        "watched_file_count": 0,
        "changed_files": [],
        "changed_file_count": 0,
        "manifest_bootstrapped": False,
    }
    return {
        "publication_subject": {
            "status": "invalid",
            "source": "explicit_target",
            "detail": _ARXIV_INVALID_EXTERNAL_SUBJECT_DETAIL,
            "target_path": target_label,
            "artifact_base": None,
            "publication_root": None,
            "review_dir": None,
            "manuscript_root": None,
            "manuscript_entrypoint": None,
            "artifact_manifest": None,
            "bibliography_audit": None,
            "reproducibility_manifest": None,
            "publication_subject_slug": None,
            "publication_lane_kind": None,
            "publication_lane_owner": None,
            "managed_publication_root": None,
            "managed_intake_root": None,
            "managed_manuscript_root": None,
            "path_semantics": None,
        },
        "publication_subject_status": "invalid",
        "publication_subject_source": "explicit_target",
        "publication_subject_detail": _ARXIV_INVALID_EXTERNAL_SUBJECT_DETAIL,
        "publication_subject_slug": None,
        "publication_lane_kind": None,
        "publication_lane_owner": None,
        "publication_artifact_base": None,
        "publication_root": None,
        "review_dir": None,
        "managed_publication_root": None,
        "selected_publication_root": None,
        "selected_review_root": None,
        "publication_target_mode": "invalid_explicit_target",
        "publication_target_detail": _ARXIV_INVALID_EXTERNAL_SUBJECT_DETAIL,
        "publication_target_project_context_role": "carry_forward_only",
        "publication_target_path": target_label,
        "publication_target_root": None,
        "manuscript_resolution_status": "invalid",
        "manuscript_resolution_detail": _ARXIV_INVALID_EXTERNAL_SUBJECT_DETAIL,
        "manuscript_root": None,
        "manuscript_entrypoint": None,
        "artifact_manifest_path": None,
        "bibliography_audit_path": None,
        "reproducibility_manifest_path": None,
        "manuscript_reference_status_warnings": [],
        "derived_manuscript_reference_status": {},
        "derived_manuscript_reference_status_count": 0,
        "derived_manuscript_reference_status_warnings": [],
        "manuscript_reference_subject_status": "invalid",
        "manuscript_reference_subject_detail": _ARXIV_INVALID_EXTERNAL_SUBJECT_DETAIL,
        "derived_manuscript_proof_review_status": proof_review_status,
        "publication_blockers": [],
        "publication_blocker_count": 0,
        "latest_review_round": None,
        "latest_review_round_suffix": None,
        "latest_review_ledger": None,
        "latest_referee_decision": None,
        "latest_referee_report_md": None,
        "latest_referee_report_tex": None,
        "latest_proof_redteam": None,
        "latest_review_artifacts": None,
        "latest_response_round": None,
        "latest_response_round_suffix": None,
        "latest_author_response": None,
        "latest_referee_response": None,
        "latest_response_artifacts": None,
        "latest_response_freshness_policy": freshness["policy"],
        "latest_response_requires_fresh_review": freshness["requires_fresh_review"],
        "latest_response_required_review_round": freshness["required_review_round"],
        "latest_response_required_review_round_suffix": freshness["required_review_round_suffix"],
        "latest_response_freshness_detail": freshness["detail"],
        "latest_response_freshness": freshness,
    }


def _selected_publication_stage_roots(
    *,
    publication_subject_slug: str | None,
    publication_lane_kind: str | None,
    managed_publication_root: str | None,
) -> dict[str, str | None]:
    """Return the active publication and review roots for staged publication work."""

    if publication_lane_kind == "canonical_project_manuscript":
        selected_publication_root = PLANNING_DIR_NAME
    elif publication_subject_slug:
        selected_publication_root = managed_publication_root or (
            f"{PLANNING_DIR_NAME}/publication/{publication_subject_slug}"
        )
    else:
        selected_publication_root = None

    if selected_publication_root is None:
        selected_review_root = None
    elif selected_publication_root == PLANNING_DIR_NAME:
        selected_review_root = f"{PLANNING_DIR_NAME}/review"
    else:
        selected_review_root = f"{selected_publication_root}/review"

    return {
        "selected_publication_root": selected_publication_root,
        "selected_review_root": selected_review_root,
    }


def _standalone_peer_review_publication_overrides(
    cwd: Path,
    *,
    result: Mapping[str, object],
    resolved_target: Path | None,
    resolved_root: Path | None,
) -> dict[str, object]:
    """Return subject-owned publication roots for standalone peer-review targets."""

    anchor = resolved_target or resolved_root
    subject_context: dict[str, object] = {}
    if resolved_target is not None and resolved_target.suffix.lower() in {".tex", ".md"}:
        subject = resolve_explicit_publication_subject(
            cwd,
            resolved_target,
            canonical_project_manuscript_allowed=False,
        )
        if subject.publication_subject_slug:
            subject_context = subject.to_context_dict()

    publication_subject_slug = (
        subject_context.get("publication_subject_slug")
        if isinstance(subject_context.get("publication_subject_slug"), str)
        else result.get("publication_subject_slug")
        if isinstance(result.get("publication_subject_slug"), str)
        else None
    )
    if publication_subject_slug is None and anchor is not None:
        publication_subject_slug = derive_hashed_publication_subject_slug(cwd, anchor)

    managed_publication_root = (
        subject_context.get("managed_publication_root")
        if isinstance(subject_context.get("managed_publication_root"), str)
        else result.get("managed_publication_root")
        if isinstance(result.get("managed_publication_root"), str)
        else None
    )
    if managed_publication_root is None and publication_subject_slug:
        managed_publication_root = f"{PLANNING_DIR_NAME}/{PUBLICATION_DIR_NAME}/{publication_subject_slug}"

    selected_review_root = f"{managed_publication_root}/review" if managed_publication_root else None
    managed_intake_root = f"{managed_publication_root}/intake" if managed_publication_root else None
    target_path = _relative_or_absolute_posix(cwd, resolved_target)
    artifact_base = _relative_or_absolute_posix(cwd, resolved_root)

    publication_subject_payload: dict[str, object] = (
        dict(subject_context)
        if subject_context
        else dict(result.get("publication_subject"))
        if isinstance(result.get("publication_subject"), Mapping)
        else {}
    )
    publication_subject_payload.update(
        {
            "status": "resolved",
            "source": "explicit_target",
            "target_path": target_path,
            "artifact_base": artifact_base,
            "publication_root": managed_publication_root,
            "review_dir": selected_review_root,
            "manuscript_root": artifact_base,
            "manuscript_entrypoint": target_path,
            "publication_subject_slug": publication_subject_slug,
            "publication_lane_kind": "external_artifact",
            "publication_lane_owner": "external_artifact",
            "managed_publication_root": managed_publication_root,
            "managed_intake_root": managed_intake_root,
            "managed_manuscript_root": None,
        }
    )

    return {
        "publication_subject": publication_subject_payload,
        "publication_subject_status": "resolved",
        "publication_subject_source": "explicit_target",
        "publication_subject_slug": publication_subject_slug,
        "publication_lane_kind": "external_artifact",
        "publication_lane_owner": "external_artifact",
        "publication_root": managed_publication_root,
        "review_dir": selected_review_root,
        "managed_publication_root": managed_publication_root,
        "managed_intake_root": managed_intake_root,
        "managed_manuscript_root": None,
        "publication_intake_root": managed_intake_root,
        "selected_publication_root": managed_publication_root,
        "selected_review_root": selected_review_root,
    }


def _build_publication_runtime_snapshot_context(
    cwd: Path,
    *,
    subject: str | None = None,
    persist_manuscript_proof_review_manifest: bool = False,
    pin_response_to_review_round: bool = True,
) -> dict[str, object]:
    """Build the canonical publication snapshot payload used by publication commands."""

    snapshot = publication_runtime_snapshot_context(
        cwd,
        subject=subject,
        persist_manuscript_proof_review_manifest=persist_manuscript_proof_review_manifest,
        pin_response_to_review_round=pin_response_to_review_round,
    )
    publication_subject = snapshot.get("publication_subject")
    subject_context = publication_subject if isinstance(publication_subject, Mapping) else {}
    publication_lane_kind = (
        subject_context.get("publication_lane_kind")
        if isinstance(subject_context.get("publication_lane_kind"), str)
        else None
    )
    publication_lane_owner = (
        subject_context.get("publication_lane_owner")
        if isinstance(subject_context.get("publication_lane_owner"), str)
        else None
    )
    managed_publication_root = (
        subject_context.get("managed_publication_root")
        if isinstance(subject_context.get("managed_publication_root"), str)
        else None
    )
    snapshot.update(
        {
            "publication_lane_kind": publication_lane_kind,
            "publication_lane_owner": publication_lane_owner,
            "managed_publication_root": managed_publication_root,
            **_selected_publication_stage_roots(
                publication_subject_slug=snapshot.get("publication_subject_slug")
                if isinstance(snapshot.get("publication_subject_slug"), str)
                else None,
                publication_lane_kind=publication_lane_kind,
                managed_publication_root=managed_publication_root,
            ),
        }
    )
    return snapshot


def _explicit_subject_from_launch_cwd(subject: str | None, launch_cwd: Path) -> str | None:
    """Resolve explicit relative peer-review targets from the launch cwd."""

    if not isinstance(subject, str):
        return subject
    normalized = subject.strip()
    if not normalized:
        return normalized
    target = Path(normalized)
    if target.is_absolute():
        return normalized
    return str((launch_cwd / target).resolve(strict=False))


def _resolve_peer_review_target_context(
    cwd: Path,
    subject: str | None,
) -> tuple[Path | None, Path | None]:
    """Resolve the peer-review target path and root for init/context surfacing."""

    if not isinstance(subject, str) or not subject.strip():
        manuscript_entrypoint = resolve_current_manuscript_entrypoint(cwd)
        return manuscript_entrypoint, manuscript_entrypoint.parent if manuscript_entrypoint is not None else None

    target = Path(subject)
    if not target.is_absolute():
        target = cwd / target
    resolved_target = target.resolve(strict=False)
    if resolved_target.is_file():
        return resolved_target, resolved_target.parent
    if resolved_target.is_dir():
        manuscript_root = resolve_supported_manuscript_root_for_target(cwd, resolved_target) or resolved_target
        resolution = resolve_manuscript_entrypoint_from_root_resolution(manuscript_root, allow_markdown=True)
        if resolution.status == "resolved" and resolution.manuscript_entrypoint is not None:
            return resolution.manuscript_entrypoint.resolve(strict=False), manuscript_root
        return None, manuscript_root
    return None, resolved_target.parent


def _build_peer_review_runtime_context(
    cwd: Path,
    subject: str | None = None,
    *,
    launch_cwd: Path | None = None,
    persist_manuscript_proof_review_manifest: bool = False,
    preserve_standalone_publication_roots: bool = False,
    reference_fields: set[str] | frozenset[str] | None = None,
) -> dict[str, object]:
    """Build the shared publication runtime payload for peer-review init and staging."""

    target_base_cwd = (launch_cwd or cwd).expanduser().resolve(strict=False)
    resolved_subject = _explicit_subject_from_launch_cwd(subject, target_base_cwd)
    if reference_fields is None:
        result = dict(
            _build_reference_runtime_context(
                cwd, persist_manuscript_proof_review_manifest=persist_manuscript_proof_review_manifest
            )
        )
        include_protocol_context = True
        include_active_reference_context = True
    else:
        selected_reference_fields = frozenset(reference_fields)
        result = dict(
            _build_staged_reference_runtime_context(
                cwd,
                selected_reference_fields,
                persist_manuscript_proof_review_manifest=persist_manuscript_proof_review_manifest,
            )
        )
        include_protocol_context = "protocol_bundle_context" in selected_reference_fields
        include_active_reference_context = "active_reference_context" in selected_reference_fields
    result.update(
        _build_publication_bootstrap_runtime_context(
            cwd,
            persist_manuscript_proof_review_manifest=persist_manuscript_proof_review_manifest,
            include_protocol_context=include_protocol_context,
            include_active_reference_context=include_active_reference_context,
        )
    )
    result.update(
        _build_publication_runtime_snapshot_context(
            cwd,
            subject=resolved_subject,
            persist_manuscript_proof_review_manifest=persist_manuscript_proof_review_manifest,
        )
    )
    resolved_mode, mode_reason = resolve_peer_review_mode(cwd, resolved_subject, workspace_cwd=target_base_cwd)
    resolved_target, resolved_root = _resolve_peer_review_target_context(cwd, resolved_subject)
    standalone_contract_suppression_reason = (
        "standalone explicit-artifact review does not use the current project contract as authoritative context"
    )
    standalone_contract_warning = (
        "standalone explicit-artifact review hides current-project contract, bundle, and project-derived reference "
        "context while preserving explicit-target manuscript/publication snapshot fields when they can be resolved"
    )
    result.update(
        {
            "review_target_input": subject.strip() if isinstance(subject, str) else "",
            "review_target_mode": resolved_mode,
            "review_target_mode_reason": mode_reason,
            "resolved_review_target": str(resolved_target) if resolved_target is not None else None,
            "resolved_review_root": str(resolved_root) if resolved_root is not None else None,
        }
    )
    if resolved_mode == PEER_REVIEW_STANDALONE_MODE:
        standalone_publication_overrides: dict[str, object] = {}
        if not preserve_standalone_publication_roots:
            standalone_publication_overrides = {
                "publication_bootstrap": None,
                "publication_bootstrap_mode": None,
                "publication_bootstrap_root": None,
                "publication_bootstrap_detail": None,
                **_standalone_peer_review_publication_overrides(
                    cwd,
                    result=result,
                    resolved_target=resolved_target,
                    resolved_root=resolved_root,
                ),
            }
        gate = {
            "status": "standalone_explicit_artifact",
            "visible": False,
            "blocked": False,
            "load_blocked": False,
            "approval_blocked": False,
            "authoritative": False,
            "repair_required": False,
            "raw_project_contract_classified": False,
            "provenance": None,
            "source_path": None,
            "reason": standalone_contract_suppression_reason,
        }
        load_info = {
            "status": "standalone_explicit_artifact",
            "source_path": None,
            "provenance": None,
            "raw_project_contract_classified": False,
            "errors": [],
            "warnings": [standalone_contract_warning],
            "mode": PEER_REVIEW_STANDALONE_MODE,
        }
        result.update(
            {
                "project_contract": None,
                "project_contract_gate": gate,
                "project_contract_load_info": load_info,
                "project_contract_validation": None,
                "contract_intake": None,
                "effective_reference_intake": _empty_reference_intake(),
                "derived_active_references": [],
                "derived_active_reference_count": 0,
                "active_references": [],
                "active_reference_count": 0,
                "selected_protocol_bundle_ids": [],
                "protocol_bundle_count": 0,
                "protocol_bundle_load_manifest": build_protocol_bundle_load_manifest([]),
                "protocol_bundle_verifier_extensions": [],
                "protocol_bundle_context": None,
                "active_reference_context": "",
                "reference_artifact_files": [],
                "reference_artifacts_content": None,
                "literature_review_files": [],
                "literature_review_count": 0,
                "research_map_reference_files": [],
                "research_map_reference_count": 0,
                "knowledge_doc_files": [],
                "knowledge_doc_count": 0,
                "stable_knowledge_doc_files": [],
                "stable_knowledge_doc_count": 0,
                "knowledge_doc_status_counts": {},
                "knowledge_doc_warnings": [],
                "derived_knowledge_docs": [],
                "derived_knowledge_doc_count": 0,
                "citation_source_files": [],
                "citation_source_count": 0,
                "citation_source_warnings": [],
                "derived_citation_sources": [],
                "derived_citation_source_count": 0,
                **standalone_publication_overrides,
            }
        )
    return result


def _build_state_memory_runtime_context(cwd: Path) -> dict[str, object]:
    """Build shared structured state-memory context for init surfaces."""
    state, _state_issues, _state_source = _peek_state_json(
        cwd,
        recover_intent=False,
        acquire_lock=False,
    )
    if not isinstance(state, dict):
        return {
            "derived_convention_lock": {},
            "derived_convention_lock_count": 0,
            "derived_intermediate_results": [],
            "derived_intermediate_result_count": 0,
            "derived_approximations": [],
            "derived_approximation_count": 0,
        }

    raw_lock = state.get("convention_lock")
    derived_convention_lock: dict[str, object] = {}
    if isinstance(raw_lock, Mapping):
        try:
            normalized_lock = ConventionLock(**raw_lock).model_dump(mode="json", exclude_none=True)
        except PydanticValidationError:
            normalized_lock = {}
        derived_convention_lock = {
            key: value for key, value in normalized_lock.items() if _has_structured_state_value(value)
        }

    derived_results = [result.model_dump(mode="json") for result in result_list(state)]
    derived_approximations = [approx.model_dump(mode="json") for approx in approximation_list(state)]

    return {
        "derived_convention_lock": derived_convention_lock,
        "derived_convention_lock_count": len(derived_convention_lock),
        "derived_intermediate_results": derived_results,
        "derived_intermediate_result_count": len(derived_results),
        "derived_approximations": derived_approximations,
        "derived_approximation_count": len(derived_approximations),
    }


def _build_execution_runtime_context(cwd: Path) -> dict[str, object]:
    """Build shared live execution-state context for orchestration surfaces."""
    from gpd.core.observability import get_current_execution

    snapshot = get_current_execution(cwd)
    state, state_issues, _state_source = _peek_state_json(
        cwd,
        recover_intent=False,
        acquire_lock=False,
    )
    position = state.get("position") if isinstance(state, dict) else {}
    machine = _current_machine_identity()
    current_hostname = machine.get("hostname")
    current_platform = machine.get("platform")
    raw_current_execution_resume_file = snapshot.resume_file if snapshot is not None else None
    if (
        isinstance(raw_current_execution_resume_file, str)
        and raw_current_execution_resume_file.strip().casefold() == "[not set]"
    ):
        raw_current_execution_resume_file = None
    current_execution_resume_file = normalize_continuation_reference(
        cwd,
        raw_current_execution_resume_file,
        require_exists=True,
    )
    current_execution_payload = snapshot.model_dump(mode="json") if snapshot is not None else None
    if isinstance(current_execution_payload, dict):
        current_execution_payload["resume_file"] = current_execution_resume_file
    resume_projection = _resolve_resume_projection(
        cwd,
        state=state,
        current_execution=current_execution_payload,
        state_issues=state_issues,
    )
    continuation = getattr(resume_projection, "continuation", None)
    handoff = getattr(continuation, "handoff", None)
    recorded_machine = getattr(continuation, "machine", None)
    canonical_continuation = normalize_continuation(
        cwd,
        state.get("continuation") if isinstance(state, dict) else None,
    )
    canonical_bounded_segment = canonical_continuation.bounded_segment
    has_active_resume_target = resume_projection.active_resume_source is not None
    active_canonical_bounded_segment = (
        canonical_bounded_segment
        if resume_projection.active_resume_source == ContinuationResumeSource.BOUNDED_SEGMENT
        else None
    )
    session_hostname = getattr(recorded_machine, "hostname", None) if has_active_resume_target else None
    session_platform = getattr(recorded_machine, "platform", None) if has_active_resume_target else None
    session_last_date = (
        (getattr(handoff, "recorded_at", None) or getattr(recorded_machine, "recorded_at", None))
        if has_active_resume_target
        else None
    )
    session_stopped_at = getattr(handoff, "stopped_at", None) if has_active_resume_target else None
    execution_resume_file_source = None
    if resume_projection.active_resume_source == ContinuationResumeSource.BOUNDED_SEGMENT:
        execution_resume_file_source = (
            "current_execution"
            if resume_projection.source == ContinuationSource.DERIVED_EXECUTION
            else "continuation.bounded_segment"
        )
    elif resume_projection.active_resume_source == ContinuationResumeSource.HANDOFF:
        execution_resume_file_source = "handoff_resume_file"

    segment_status = (snapshot.segment_status or "").strip().lower() if snapshot is not None else ""
    bounded_segment_status = (
        (active_canonical_bounded_segment.segment_status or "").strip().lower()
        if active_canonical_bounded_segment is not None
        else ""
    )
    snapshot_review_pending = bool(
        snapshot
        and (
            snapshot.first_result_gate_pending
            or snapshot.pre_fanout_review_pending
            or snapshot.skeptical_requestioning_required
            or snapshot.waiting_for_review
            or segment_status == "waiting_review"
        )
    )
    bounded_segment_review_pending = bool(
        active_canonical_bounded_segment
        and (
            active_canonical_bounded_segment.first_result_gate_pending
            or active_canonical_bounded_segment.pre_fanout_review_pending
            or active_canonical_bounded_segment.skeptical_requestioning_required
            or active_canonical_bounded_segment.waiting_for_review
            or bounded_segment_status == "waiting_review"
        )
    )
    snapshot_pre_fanout_review_pending = bool(snapshot and snapshot.pre_fanout_review_pending)
    bounded_segment_pre_fanout_review_pending = bool(
        active_canonical_bounded_segment and active_canonical_bounded_segment.pre_fanout_review_pending
    )
    snapshot_skeptical_requestioning_required = bool(snapshot and snapshot.skeptical_requestioning_required)
    bounded_segment_skeptical_requestioning_required = bool(
        active_canonical_bounded_segment and active_canonical_bounded_segment.skeptical_requestioning_required
    )
    snapshot_downstream_locked = bool(snapshot and snapshot.downstream_locked)
    bounded_segment_downstream_locked = bool(
        active_canonical_bounded_segment and active_canonical_bounded_segment.downstream_locked
    )
    snapshot_blocked = bool(snapshot and (snapshot.blocked_reason or segment_status == "blocked"))
    bounded_segment_blocked = bool(
        active_canonical_bounded_segment
        and (active_canonical_bounded_segment.blocked_reason or bounded_segment_status == "blocked")
    )
    is_resumable = bool(resume_projection.resumable)
    snapshot_paused_at = (
        snapshot.updated_at if snapshot is not None and segment_status in RESUMABLE_SEGMENT_STATUSES else None
    )
    bounded_segment_paused_at = (
        active_canonical_bounded_segment.updated_at
        if active_canonical_bounded_segment is not None and bounded_segment_status in RESUMABLE_SEGMENT_STATUSES
        else None
    )
    paused_at = (
        snapshot_paused_at
        or bounded_segment_paused_at
        or (position.get("paused_at") if isinstance(position, dict) else None)
    )
    resume_file = resume_projection.active_resume_file
    machine_change_detected = bool(
        has_active_resume_target
        and session_hostname
        and session_platform
        and (session_hostname != current_hostname or session_platform != current_platform)
    )
    machine_change_notice = None
    if machine_change_detected:
        machine_change_notice = (
            "Machine change detected: "
            f"last active on {session_hostname} ({session_platform}); "
            f"current machine {current_hostname} ({current_platform}). "
            "The project state is portable and does not require repair. "
            "Rerun the installer if runtime-local config may be stale on this machine."
        )

    return {
        "current_execution": current_execution_payload,
        "has_live_execution": snapshot is not None,
        "execution_review_pending": snapshot_review_pending or bounded_segment_review_pending,
        "execution_pre_fanout_review_pending": (
            snapshot_pre_fanout_review_pending or bounded_segment_pre_fanout_review_pending
        ),
        "execution_skeptical_requestioning_required": (
            snapshot_skeptical_requestioning_required or bounded_segment_skeptical_requestioning_required
        ),
        "execution_downstream_locked": snapshot_downstream_locked or bounded_segment_downstream_locked,
        "execution_blocked": snapshot_blocked or bounded_segment_blocked,
        "execution_resumable": is_resumable,
        "execution_paused_at": paused_at,
        "current_execution_resume_file": current_execution_resume_file,
        "handoff_resume_file": resume_projection.handoff_resume_file,
        "recorded_handoff_resume_file": resume_projection.recorded_handoff_resume_file,
        "missing_handoff_resume_file": resume_projection.missing_handoff_resume_file,
        "execution_resume_file": resume_file,
        "execution_resume_file_source": execution_resume_file_source,
        "resume_projection": resume_projection,
        "current_hostname": current_hostname,
        "current_platform": current_platform,
        "session_hostname": session_hostname,
        "session_platform": session_platform,
        "session_last_date": session_last_date,
        "session_stopped_at": session_stopped_at,
        "machine_change_detected": machine_change_detected,
        "machine_change_notice": machine_change_notice,
    }


def _resolve_resume_projection(
    cwd: Path,
    *,
    state: dict[str, object] | None,
    current_execution: dict[str, object] | None,
    state_issues: list[str] | None = None,
):
    return resolve_continuation(
        cwd,
        state=state,
        current_execution=current_execution,
        state_issues=state_issues,
    )


def _bounded_segment_resume_origin(resume_projection: object) -> str:
    return resume_origin_for_bounded_segment()


def _handoff_resume_origin(resume_projection: object) -> str:
    return resume_origin_for_handoff()


def _handoff_last_result_id(resume_projection: object) -> str | None:
    continuation = getattr(resume_projection, "continuation", None)
    handoff = getattr(continuation, "handoff", None)
    last_result_id = getattr(handoff, "last_result_id", None)
    if not isinstance(last_result_id, str):
        return None
    stripped = last_result_id.strip()
    return stripped or None


def _build_resume_result_lookup(cwd: Path) -> dict[str, dict[str, object]]:
    """Return canonical results keyed by ID for resume hydration."""
    state, _state_issues, _state_source = _peek_state_json(
        cwd,
        recover_intent=False,
        acquire_lock=False,
    )
    if not isinstance(state, dict):
        return {}
    try:
        return {
            result.id: result.model_dump(mode="json")
            for result in result_list(state)
            if isinstance(result.id, str) and result.id.strip()
        }
    except (PydanticValidationError, TypeError, ValueError) as exc:
        logger.warning("Resume result hydration unavailable: %s", exc)
        return {}


def _hydrate_resume_result(
    candidate: Mapping[str, object],
    result_lookup_by_id: Mapping[str, dict[str, object]],
) -> dict[str, object]:
    """Attach the canonical result payload when a candidate carries `last_result_id`."""
    hydrated = dict(candidate)
    last_result_id = hydrated.get("last_result_id")
    if not isinstance(last_result_id, str):
        return hydrated
    lookup_key = last_result_id.strip()
    if not lookup_key:
        return hydrated
    last_result = result_lookup_by_id.get(lookup_key)
    if isinstance(last_result, Mapping):
        hydrated["last_result"] = dict(last_result)
    return hydrated


def _select_active_resume_candidate(
    resume_candidates: list[dict[str, object]],
    *,
    active_resume_kind: str | None,
    active_resume_pointer: str | None,
) -> dict[str, object] | None:
    """Return the candidate currently selected as the active resume target."""
    if not isinstance(active_resume_kind, str):
        return None
    active_kind = active_resume_kind.strip()
    if not active_kind:
        return None
    active_pointer = (
        active_resume_pointer.strip()
        if isinstance(active_resume_pointer, str) and active_resume_pointer.strip()
        else None
    )

    if active_pointer is not None:
        for candidate in resume_candidates:
            if str(candidate.get("kind") or "").strip() != active_kind:
                continue
            if candidate.get("resume_pointer") != active_pointer:
                continue
            return candidate

    for candidate in resume_candidates:
        if str(candidate.get("kind") or "").strip() == active_kind:
            return candidate
    return None


def _interrupted_agent_resume_origin() -> str:
    return resume_origin_for_interrupted_agent()


def _resume_candidate_from_segment(segment: dict[str, object]) -> dict[str, object]:
    return build_resume_segment_candidate(segment)


def _canonical_resume_candidate(
    candidate: dict[str, object],
    *,
    kind: str,
    origin: str,
    resume_pointer: str | None = None,
) -> dict[str, object]:
    return build_resume_candidate(
        candidate,
        kind=kind,
        origin=origin,
        resume_pointer=resume_pointer,
    )


def _has_resume_candidate(
    resume_candidates: list[dict[str, object]],
    *,
    kind: str,
    resume_pointer: str | None = None,
    agent_id: str | None = None,
) -> bool:
    for candidate in resume_candidates:
        if str(candidate.get("kind") or "").strip() != kind:
            continue
        if resume_pointer is not None and candidate.get("resume_pointer") != resume_pointer:
            continue
        if agent_id is not None and candidate.get("agent_id") != agent_id:
            continue
        return True
    return False


def _build_resume_read_state(
    execution_context: dict[str, object],
    *,
    interrupted_agent_id: str | None,
    result_lookup_by_id: dict[str, dict[str, object]],
) -> dict[str, object]:
    resume_projection = execution_context.get("resume_projection")
    if not hasattr(resume_projection, "continuation"):
        raise RuntimeError("resume_projection missing from execution context")

    current_execution_raw = execution_context.get("current_execution")
    current_execution = current_execution_raw if isinstance(current_execution_raw, dict) else None
    bounded_segment = getattr(resume_projection.continuation, "bounded_segment", None)
    active_resume_source = resume_projection.active_resume_source
    bounded_segment_resume_file = resume_projection.bounded_segment_resume_file
    handoff_resume_file = resume_projection.handoff_resume_file
    handoff_primary = bool(
        resume_projection.source != ContinuationSource.CANONICAL
        and isinstance(handoff_resume_file, str)
        and handoff_resume_file
    )
    bounded_segment_origin = _bounded_segment_resume_origin(resume_projection)
    handoff_origin = _handoff_resume_origin(resume_projection)
    handoff_last_result_id = _handoff_last_result_id(resume_projection)
    active_bounded_segment = None
    if (
        bounded_segment is not None
        and active_resume_source == ContinuationResumeSource.BOUNDED_SEGMENT
        and not handoff_primary
    ):
        active_bounded_segment = bounded_segment.model_dump(mode="json")

    resume_candidates: list[dict[str, object]] = []
    if (
        resume_projection.resumable
        and bounded_segment is not None
        and active_resume_source == ContinuationResumeSource.BOUNDED_SEGMENT
        and not handoff_primary
    ):
        candidate_payload = bounded_segment.model_dump(mode="json")
        candidate_payload["resume_file"] = bounded_segment_resume_file
        candidate = _resume_candidate_from_segment(candidate_payload)
        resume_candidates.append(
            _canonical_resume_candidate(
                candidate,
                kind="bounded_segment",
                origin=bounded_segment_origin,
                resume_pointer=bounded_segment_resume_file,
            )
        )

    if isinstance(resume_projection.handoff_resume_file, str) and resume_projection.handoff_resume_file:
        if not any(
            candidate.get("resume_pointer") == resume_projection.handoff_resume_file for candidate in resume_candidates
        ):
            candidate = {
                "source": "handoff_resume_file",
                "status": "handoff",
                "resume_file": resume_projection.handoff_resume_file,
                "resumable": False,
            }
            if handoff_last_result_id is not None:
                candidate["last_result_id"] = handoff_last_result_id
            resume_candidates.append(
                _canonical_resume_candidate(
                    candidate,
                    kind="continuity_handoff",
                    origin=handoff_origin,
                    resume_pointer=resume_projection.handoff_resume_file,
                )
            )

    if isinstance(resume_projection.missing_handoff_resume_file, str) and resume_projection.missing_handoff_resume_file:
        if not _has_resume_candidate(
            resume_candidates,
            kind="continuity_handoff",
            resume_pointer=resume_projection.missing_handoff_resume_file,
        ):
            candidate = {
                "source": "handoff_resume_file",
                "status": "missing",
                "resume_file": resume_projection.missing_handoff_resume_file,
                "resumable": False,
                "advisory": True,
            }
            if handoff_last_result_id is not None:
                candidate["last_result_id"] = handoff_last_result_id
            resume_candidates.append(
                _canonical_resume_candidate(
                    candidate,
                    kind="continuity_handoff",
                    origin=handoff_origin,
                    resume_pointer=resume_projection.missing_handoff_resume_file,
                )
            )

    if interrupted_agent_id is not None and not _has_resume_candidate(
        resume_candidates,
        kind="interrupted_agent",
        agent_id=interrupted_agent_id,
    ):
        candidate = {
            "source": "interrupted_agent",
            "status": "interrupted",
            "agent_id": interrupted_agent_id,
        }
        resume_candidates.append(
            _canonical_resume_candidate(
                candidate,
                kind="interrupted_agent",
                origin=_interrupted_agent_resume_origin(),
                resume_pointer=interrupted_agent_id,
            )
        )

    hydrated_resume_candidates = [
        _hydrate_resume_result(candidate, result_lookup_by_id) for candidate in resume_candidates
    ]

    if handoff_primary:
        active_resume_kind = "continuity_handoff"
        active_resume_origin = handoff_origin
        active_resume_pointer = handoff_resume_file
    elif active_resume_source == ContinuationResumeSource.BOUNDED_SEGMENT:
        active_resume_kind = "bounded_segment"
        active_resume_origin = bounded_segment_origin
        active_resume_pointer = resume_projection.active_resume_file
    elif active_resume_source == ContinuationResumeSource.HANDOFF:
        active_resume_kind = "continuity_handoff"
        active_resume_origin = handoff_origin
        active_resume_pointer = resume_projection.active_resume_file
    elif interrupted_agent_id is not None:
        active_resume_kind = "interrupted_agent"
        active_resume_origin = _interrupted_agent_resume_origin()
        active_resume_pointer = interrupted_agent_id
    else:
        active_resume_kind = None
        active_resume_origin = None
        active_resume_pointer = None

    active_resume_candidate = _select_active_resume_candidate(
        hydrated_resume_candidates,
        active_resume_kind=active_resume_kind,
        active_resume_pointer=active_resume_pointer,
    )

    result = {
        "resume_surface_schema_version": RESUME_SURFACE_SCHEMA_VERSION,
        "active_bounded_segment": active_bounded_segment,
        "derived_execution_head": current_execution,
        "continuity_handoff_file": resume_projection.handoff_resume_file,
        "recorded_continuity_handoff_file": resume_projection.recorded_handoff_resume_file,
        "missing_continuity_handoff_file": resume_projection.missing_handoff_resume_file,
        "has_continuity_handoff": resume_projection.recorded_handoff_resume_file is not None,
        "resume_candidates": hydrated_resume_candidates,
        "active_resume_kind": active_resume_kind,
        "active_resume_origin": active_resume_origin,
        "active_resume_pointer": active_resume_pointer,
        "has_interrupted_agent": interrupted_agent_id is not None,
        "interrupted_agent_id": interrupted_agent_id,
    }
    if isinstance(active_resume_candidate, dict):
        active_resume_result = active_resume_candidate.get("last_result")
        if isinstance(active_resume_result, Mapping):
            result["active_resume_result"] = dict(active_resume_result)
    return result


def _mapping_text(value: Mapping[str, object] | None, key: str) -> str | None:
    if not isinstance(value, Mapping):
        return None
    candidate = value.get(key)
    if not isinstance(candidate, str):
        return None
    stripped = candidate.strip()
    return stripped or None


def _promote_auto_selected_recent_bounded_segment(
    continuation_state: dict[str, object],
    *,
    reentry_metadata: Mapping[str, object],
    result_lookup_by_id: Mapping[str, Mapping[str, object]],
) -> tuple[dict[str, object], bool]:
    """Promote a stronger auto-selected recent bounded segment over a same-pointer handoff."""

    selected_candidate = reentry_metadata.get("project_reentry_selected_candidate")
    if not isinstance(selected_candidate, Mapping):
        return continuation_state, False
    if not bool(reentry_metadata.get("project_root_auto_selected")):
        return continuation_state, False
    if _mapping_text(selected_candidate, "source") != "recent_project":
        return continuation_state, False
    if _mapping_text(selected_candidate, "resume_target_kind") != "bounded_segment":
        return continuation_state, False
    if not bool(selected_candidate.get("resumable", False)):
        return continuation_state, False

    resume_file = _mapping_text(selected_candidate, "resume_file")
    if resume_file is None:
        return continuation_state, False
    project_root = _mapping_text(reentry_metadata, "project_root") or _mapping_text(selected_candidate, "project_root")
    if project_root is None:
        return continuation_state, False
    normalized_resume_file = normalize_continuation_reference(project_root, resume_file, require_exists=True)
    if normalized_resume_file is None:
        return continuation_state, False
    resume_file = normalized_resume_file

    last_result_id = _mapping_text(selected_candidate, "last_result_id")
    if last_result_id is not None and last_result_id not in result_lookup_by_id:
        last_result_id = None

    active_resume_kind = _mapping_text(continuation_state, "active_resume_kind")
    active_resume_pointer = _mapping_text(continuation_state, "active_resume_pointer")
    if active_resume_kind == "bounded_segment":
        return continuation_state, False
    if active_resume_kind not in {None, "continuity_handoff"}:
        return continuation_state, False
    if active_resume_pointer is not None and active_resume_pointer != resume_file:
        return continuation_state, False

    active_bounded_segment = continuation_state.get("active_bounded_segment")
    if isinstance(active_bounded_segment, dict) and _mapping_text(active_bounded_segment, "resume_file") not in {
        None,
        resume_file,
    }:
        return continuation_state, False

    bounded_segment = {
        "segment_status": "paused",
        "resume_file": resume_file,
        "phase": _mapping_text(selected_candidate, "recovery_phase"),
        "plan": _mapping_text(selected_candidate, "recovery_plan"),
        "segment_id": _mapping_text(selected_candidate, "source_segment_id"),
        "transition_id": _mapping_text(selected_candidate, "source_transition_id"),
        "last_result_id": last_result_id,
        "updated_at": (
            _mapping_text(selected_candidate, "resume_target_recorded_at")
            or _mapping_text(selected_candidate, "source_recorded_at")
        ),
    }
    bounded_segment = {
        key: value
        for key, value in bounded_segment.items()
        if value is not None and (not isinstance(value, str) or value.strip())
    }

    raw_candidate = build_resume_segment_candidate(bounded_segment, source="recent_project")
    raw_candidate["resumable"] = True
    canonical_candidate = build_resume_candidate(
        raw_candidate,
        kind="bounded_segment",
        origin=resume_origin_for_bounded_segment(),
        resume_pointer=resume_file,
    )
    if last_result_id is None:
        canonical_candidate.pop("last_result_id", None)
    canonical_candidate = _hydrate_resume_result(canonical_candidate, result_lookup_by_id)

    def _replace_matching_candidate(
        candidates: object,
        replacement: dict[str, object],
    ) -> list[dict[str, object]]:
        normalized = [item for item in candidates if isinstance(item, dict)] if isinstance(candidates, list) else []
        updated: list[dict[str, object]] = []
        replaced = False
        for item in normalized:
            item_resume_file = _mapping_text(item, "resume_file")
            item_kind = _mapping_text(item, "kind")
            if item_resume_file == resume_file and item_kind in {None, "continuity_handoff"}:
                if not replaced:
                    promoted_replacement = dict(replacement)
                    replacement_last_result_id = _mapping_text(promoted_replacement, "last_result_id")
                    item_last_result_id = _mapping_text(item, "last_result_id")
                    item_last_result = item.get("last_result")
                    if (
                        replacement_last_result_id is not None
                        and replacement_last_result_id == item_last_result_id
                        and isinstance(item_last_result, Mapping)
                        and "last_result" not in promoted_replacement
                    ):
                        promoted_replacement["last_result"] = dict(item_last_result)
                    updated.append(promoted_replacement)
                    replaced = True
                continue
            updated.append(item)
        if not replaced:
            updated.insert(0, dict(replacement))
        return updated

    promoted = dict(continuation_state)
    promoted["active_bounded_segment"] = bounded_segment
    promoted["active_resume_kind"] = "bounded_segment"
    promoted["active_resume_origin"] = resume_origin_for_bounded_segment()
    promoted["active_resume_pointer"] = resume_file
    promoted["resume_candidates"] = _replace_matching_candidate(
        promoted.get("resume_candidates"),
        canonical_candidate,
    )
    active_resume_result = canonical_candidate.get("last_result")
    if isinstance(active_resume_result, Mapping):
        promoted["active_resume_result"] = dict(active_resume_result)
    return promoted, True


def _config_to_dict(cfg: GPDProjectConfig) -> dict:
    """Convert a :class:`GPDProjectConfig` to the plain-dict format used by context callers.

    StrEnum values are converted to plain strings so that downstream template
    code (which does string comparisons) keeps working.
    """
    d: dict[str, object] = {
        "model_profile": str(cfg.model_profile.value),
        "autonomy": str(cfg.autonomy.value),
        "review_cadence": str(cfg.review_cadence.value),
        "research_mode": str(cfg.research_mode.value),
        "commit_docs": cfg.commit_docs,
        "branching_strategy": str(cfg.branching_strategy.value),
        "phase_branch_template": cfg.phase_branch_template,
        "milestone_branch_template": cfg.milestone_branch_template,
        "research": cfg.research,
        "plan_checker": cfg.plan_checker,
        "verifier": cfg.verifier,
        "parallelization": cfg.parallelization,
        "max_unattended_minutes_per_plan": cfg.max_unattended_minutes_per_plan,
        "max_unattended_minutes_per_wave": cfg.max_unattended_minutes_per_wave,
        "project_usd_budget": cfg.project_usd_budget,
        "session_usd_budget": cfg.session_usd_budget,
        "checkpoint_after_n_tasks": cfg.checkpoint_after_n_tasks,
        "checkpoint_after_first_load_bearing_result": cfg.checkpoint_after_first_load_bearing_result,
        "checkpoint_before_downstream_dependent_tasks": cfg.checkpoint_before_downstream_dependent_tasks,
    }
    if cfg.model_overrides:
        d["model_overrides"] = cfg.model_overrides
    return d


def load_config(cwd: Path) -> dict:
    """Load GPD/config.json with defaults.

    Delegates to :func:`gpd.core.config.load_config` (the canonical
    implementation) and converts the result to a plain dict for context
    assembly callers.

    Raises :class:`~gpd.core.errors.ConfigError` on malformed JSON.
    """
    cfg = _load_config_structured(cwd)
    return _config_to_dict(cfg)


def _resolve_model(
    cwd: Path,
    agent_type: str,
    _config: dict | None = None,
    runtime: str | None = None,
) -> str | None:
    """Resolve the runtime-specific model override for an agent type."""

    def _normalize_runtime_local(value: object) -> str | None:
        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None
        return None

    active_runtime = runtime
    runtime_unknown = "unknown"
    normalize_runtime = _normalize_runtime_local
    if active_runtime is None:
        try:
            from gpd.hooks.runtime_detect import RUNTIME_UNKNOWN, normalize_runtime_name

            runtime_unknown = RUNTIME_UNKNOWN
            normalize_runtime = normalize_runtime_name
        except Exception:
            pass
        active_runtime = _detect_platform(cwd)
    else:
        try:
            from gpd.hooks.runtime_detect import RUNTIME_UNKNOWN, normalize_runtime_name

            runtime_unknown = RUNTIME_UNKNOWN
            normalize_runtime = normalize_runtime_name
        except Exception:
            pass
    active_runtime = normalize_runtime(active_runtime)
    if active_runtime == runtime_unknown:
        active_runtime = None

    return _resolve_model_canonical(cwd, agent_type, runtime=active_runtime)


def _workflow_init_dependencies() -> WorkflowInitDependencies:
    """Return current context helper aliases for extracted init builders."""

    return WorkflowInitDependencies(
        load_config=load_config,
        resolve_model=_resolve_model,
        path_exists=_path_exists,
        detect_platform=_detect_platform,
        state_exists=_state_exists,
        backup_only_state_guidance=_backup_only_state_guidance,
        resolve_project_scoped_cwd=_resolve_project_scoped_cwd,
        build_reference_runtime_context=_build_reference_runtime_context,
        build_staged_reference_runtime_context=_build_staged_reference_runtime_context,
        build_state_memory_runtime_context=_build_state_memory_runtime_context,
        build_structured_state_runtime_context=_build_structured_state_runtime_context,
        build_new_project_contract_runtime_context=_build_new_project_contract_runtime_context,
        read_file_truncated=_safe_read_file_truncated,
    )


def _try_find_phase(cwd: Path, phase: str) -> dict | None:
    """Attempt to find phase info. Returns a plain dict or None."""
    from gpd.core.phases import find_phase

    result = find_phase(cwd, phase)
    if result is None:
        return None
    return result.model_dump()


def _verify_work_expected_plan_path(cwd: Path, phase_info: dict | None) -> str | None:
    from gpd.core.verification_report_bridges import expected_phase_plan_path

    return expected_phase_plan_path(cwd, phase_info)


def _verify_work_expected_verification_path(cwd: Path, phase_info: dict | None) -> str | None:
    from gpd.core.verification_report_bridges import expected_phase_verification_path

    return expected_phase_verification_path(cwd, phase_info)


def _verify_work_existing_verification_path(cwd: Path, phase_info: dict | None) -> Path | None:
    expected = _verify_work_expected_verification_path(cwd, phase_info)
    if expected:
        expected_path = Path(expected)
        if expected_path.exists():
            return expected_path
    if not phase_info or not phase_info.get("directory"):
        return None
    phase_dir = cwd / str(phase_info["directory"])
    if not phase_dir.exists():
        return None
    verification_files = sorted(path for path in phase_dir.glob(f"*{VERIFICATION_SUFFIX}") if path.is_file())
    return verification_files[0] if verification_files else None


def _verify_work_status_payload(cwd: Path, phase_info: dict | None) -> tuple[str | None, dict[str, object]]:
    path = _verify_work_existing_verification_path(cwd, phase_info)
    if path is None:
        expected = _verify_work_expected_verification_path(cwd, phase_info)
        return expected, {
            "path": expected,
            "exists": False,
            "readable": False,
            "parseable": False,
            "status": None,
            "session_status": None,
            "score": None,
            "source": None,
            "errors": ["verification report missing"],
            "routing_status": "missing",
        }
    payload = read_verification_status(path).model_dump()
    return path.as_posix(), payload


def _active_verification_sessions(cwd: Path) -> list[dict[str, object]]:
    phases_dir = cwd / PLANNING_DIR_NAME / PHASES_DIR_NAME
    if not phases_dir.exists():
        return []
    active: list[dict[str, object]] = []
    for path in sorted(phases_dir.glob(f"*/*{VERIFICATION_SUFFIX}")):
        status_payload = read_verification_status(path).model_dump()
        if status_payload.get("session_status") not in {"validating", "diagnosed"}:
            continue
        active.append(
            {
                "path": path.as_posix(),
                "phase": path.parent.name.split("-", 1)[0],
                "status": status_payload.get("status"),
                "routing_status": status_payload.get("routing_status"),
                "session_status": status_payload.get("session_status"),
                "score": status_payload.get("score"),
                "errors": status_payload.get("errors", []),
            }
        )
    return active[:5]


def _verify_work_schema_sources() -> list[dict[str, str]]:
    from gpd.core.verification_report_bridges import verification_report_schema_sources

    return verification_report_schema_sources()


def _build_verification_report_skeleton_bridge(cwd: Path, phase_info: dict | None) -> dict[str, object]:
    from gpd.core.verification_report_bridges import build_verification_report_skeleton_bridge

    return build_verification_report_skeleton_bridge(cwd, phase_info)


def _verify_work_expected_proof_redteam_path(cwd: Path, phase_info: dict | None) -> str | None:
    from gpd.core.verification_report_bridges import expected_phase_proof_redteam_path

    return expected_phase_proof_redteam_path(cwd, phase_info)


def _build_verification_report_finalizer_bridge(cwd: Path, phase_info: dict | None) -> dict[str, object]:
    from gpd.core.verification_report_bridges import build_verification_report_finalizer_bridge

    return build_verification_report_finalizer_bridge(cwd, phase_info)


def _build_proof_redteam_finalizer_bridge(cwd: Path, phase_info: dict | None) -> dict[str, object]:
    from gpd.core.verification_report_bridges import build_proof_redteam_finalizer_bridge

    return build_proof_redteam_finalizer_bridge(cwd, phase_info)


def _infer_next_unplanned_roadmap_phase(cwd: Path) -> str | None:
    """Return the first roadmap phase that still needs planning."""

    roadmap = roadmap_analyze(cwd)
    for phase in roadmap.phases:
        if phase.disk_status in {"empty", "no_directory", "discussed", "researched"}:
            return phase.number
    return None


def _roadmap_phase_target_payload(cwd: Path, phase: str) -> dict[str, object] | None:
    """Return phase metadata from ROADMAP.md when no phase directory exists yet."""

    normalized = _normalize_phase_name(phase)
    roadmap = roadmap_analyze(cwd)
    for roadmap_phase in roadmap.phases:
        if _normalize_phase_name(roadmap_phase.number) != normalized:
            continue
        return {
            "phase_number": roadmap_phase.number,
            "phase_name": roadmap_phase.name,
            "phase_slug": _generate_slug(roadmap_phase.name),
        }
    return None


def _try_get_milestone_info(cwd: Path) -> dict:
    """Get milestone info from the canonical phases module."""
    from gpd.core.phases import get_milestone_info

    result = get_milestone_info(cwd)
    return result.model_dump()


def init_execute_phase(
    cwd: Path,
    phase: str | None,
    includes: set[str] | None = None,
    stage: str | None = None,
) -> dict:
    """Assemble context for phase execution.

    Args:
        cwd: Project root directory.
        phase: Phase identifier (e.g. "3", "03", "3.1").
        includes: Optional set of file sections to embed (state, config, roadmap).
        stage: Optional staged execute-phase context identifier.
    """
    if not phase:
        raise ValidationError(
            "phase is required for init execute-phase. Provide a phase identifier such as '1', '03', or '3.1'."
        )

    cwd = _resolve_project_scoped_cwd(cwd)
    includes = includes or set()
    if stage is not None and includes:
        raise ValueError(
            "gpd init execute-phase does not allow --include together with --stage; "
            "stage payloads already declare their required context."
        )
    config = load_config(cwd)
    phase_info = _try_find_phase(cwd, phase)
    milestone = _try_get_milestone_info(cwd)

    result: dict[str, object] = {
        # Models
        "executor_model": _resolve_model(cwd, "gpd-executor", config),
        "verifier_model": _resolve_model(cwd, "gpd-verifier", config),
        # Config flags
        "commit_docs": config["commit_docs"],
        "autonomy": config["autonomy"],
        "review_cadence": config["review_cadence"],
        "research_mode": config["research_mode"],
        "parallelization": config["parallelization"],
        "max_unattended_minutes_per_plan": config["max_unattended_minutes_per_plan"],
        "max_unattended_minutes_per_wave": config["max_unattended_minutes_per_wave"],
        "checkpoint_after_n_tasks": config["checkpoint_after_n_tasks"],
        "checkpoint_after_first_load_bearing_result": config["checkpoint_after_first_load_bearing_result"],
        "checkpoint_before_downstream_dependent_tasks": config["checkpoint_before_downstream_dependent_tasks"],
        "branching_strategy": config["branching_strategy"],
        "phase_branch_template": config["phase_branch_template"],
        "milestone_branch_template": config["milestone_branch_template"],
        "verifier_enabled": config["verifier"],
        # Phase info
        "phase_found": phase_info is not None,
        "phase_dir": phase_info["directory"] if phase_info else None,
        "phase_number": phase_info["phase_number"] if phase_info else None,
        "phase_name": phase_info.get("phase_name") if phase_info else None,
        "phase_slug": phase_info.get("phase_slug") if phase_info else None,
        # Plan inventory
        "plans": phase_info["plans"] if phase_info else [],
        "summaries": phase_info.get("summaries", []) if phase_info else [],
        "incomplete_plans": phase_info.get("incomplete_plans", []) if phase_info else [],
        "plan_count": len(phase_info["plans"]) if phase_info else 0,
        "incomplete_count": len(phase_info.get("incomplete_plans", [])) if phase_info else 0,
        # Branch name
        "branch_name": _compute_branch_name(
            config,
            phase_info.get("phase_number") if phase_info else None,
            phase_info.get("phase_slug") if phase_info else None,
            milestone["version"],
            _generate_slug(milestone["name"]),
        ),
        # Milestone info
        "milestone_version": milestone["version"],
        "milestone_name": milestone["name"],
        "milestone_slug": _generate_slug(milestone["name"]),
        # File existence
        "state_exists": _state_exists(cwd),
        "roadmap_exists": _path_exists(cwd, f"{PLANNING_DIR_NAME}/{ROADMAP_FILENAME}"),
        "config_exists": _path_exists(cwd, f"{PLANNING_DIR_NAME}/{CONFIG_FILENAME}"),
        # Platform
        "platform": _detect_platform(cwd),
    }
    if stage is None:
        result.update(_build_reference_runtime_context(cwd))
        result.update(_build_state_memory_runtime_context(cwd))
        result.update(_build_execution_runtime_context(cwd))

        # Include file contents if requested
        planning = cwd / PLANNING_DIR_NAME
        if "state" in includes:
            result["state_content"] = _safe_read_file_truncated(planning / STATE_MD_FILENAME)
            result.update(_build_structured_state_runtime_context(cwd))
        if "config" in includes:
            result["config_content"] = _safe_read_file_truncated(planning / CONFIG_FILENAME)
        if "roadmap" in includes:
            result["roadmap_content"] = _safe_read_file_truncated(planning / ROADMAP_FILENAME)

        return result

    from gpd.core.workflow_staging import load_execute_phase_stage_contract

    manifest = load_execute_phase_stage_contract()

    return _assemble_staged_init_payload(
        workflow_id="execute-phase",
        stage_id=stage,
        cwd=cwd,
        base_payload=result,
        manifest=manifest,
        providers=(
            _staged_contract_provider(cwd, _EXECUTE_PHASE_CONTRACT_GATE_FIELDS),
            _staged_selected_fields_provider(
                "reference_runtime",
                _EXECUTE_PHASE_REFERENCE_RUNTIME_FIELDS,
                _EXECUTE_PHASE_REFERENCE_RUNTIME_FIELDS,
                lambda selected_fields: _build_staged_reference_runtime_context(cwd, selected_fields),
            ),
            _staged_structured_state_provider(cwd, _EXECUTE_PHASE_STRUCTURED_STATE_FIELDS),
            _staged_state_memory_provider(cwd, _EXECUTE_PHASE_STATE_MEMORY_FIELDS),
            _staged_execution_provider(cwd),
            _staged_context_provider(
                "task_overlays",
                _EXECUTE_PHASE_TASK_OVERLAY_FIELDS,
                _build_execute_phase_task_overlay_context,
            ),
            _staged_schema_bridge_provider(
                _EXECUTE_PHASE_SCHEMA_BRIDGE_FIELDS,
                phase_info=phase_info,
                missing_phase_message=(
                    f"execute-phase stage {stage!r} requires a resolved phase so verification-report bridge commands can be built."
                ),
                bridge_builders={
                    "verification_report_skeleton_bridge": lambda: _build_verification_report_skeleton_bridge(
                        cwd,
                        phase_info,
                    ),
                    "verification_report_finalizer_bridge": lambda: _build_verification_report_finalizer_bridge(
                        cwd,
                        phase_info,
                    ),
                },
            ),
        ),
    )


def _build_plan_phase_file_context(
    cwd: Path,
    phase_info: dict[str, object] | None,
    selected_fields: frozenset[str],
) -> dict[str, object]:
    """Build file-content payloads for plan-phase init surfaces."""
    result = _build_selected_file_context(
        cwd,
        selected_fields,
        _PLAN_PHASE_PLANNING_FILE_CONTEXT_PATHS,
        _safe_read_file_truncated,
    )

    if not phase_info or not phase_info.get("directory"):
        return result

    phase_dir = cwd / str(phase_info["directory"])
    for field, (suffix, standalone) in _PLAN_PHASE_ARTIFACT_FIELD_SPECS.items():
        if field in selected_fields:
            result[field] = _find_phase_artifact(phase_dir, suffix, standalone)
    return result


def _selected_file_fields_from_includes(
    includes: set[str],
    include_to_field: Mapping[str, str],
) -> frozenset[str]:
    """Map legacy include flags onto staged file-content field names."""

    return frozenset(field for include, field in include_to_field.items() if include in includes)


def _staged_reference_provider(
    cwd: Path,
    reference_fields: frozenset[str],
    contract_fields: frozenset[str],
):
    return _staged_reference_or_contract_provider(
        reference_fields=reference_fields,
        contract_fields=contract_fields,
        build_reference=lambda selected_fields: _build_staged_reference_runtime_context(cwd, selected_fields),
        build_contract=lambda: _build_new_project_contract_runtime_context(cwd),
    )


def _staged_contract_provider(cwd: Path, trigger_fields: frozenset[str]):
    return _staged_context_provider(
        "contract_gate",
        trigger_fields,
        lambda: _build_new_project_contract_runtime_context(cwd),
    )


def _staged_structured_state_provider(cwd: Path, trigger_fields: frozenset[str]):
    return _staged_context_provider(
        "structured_state",
        trigger_fields,
        lambda: _build_structured_state_runtime_context(cwd),
    )


def _staged_state_memory_provider(cwd: Path, trigger_fields: frozenset[str]):
    return _staged_context_provider(
        "state_memory",
        trigger_fields,
        lambda: _build_state_memory_runtime_context(cwd),
    )


def _staged_execution_provider(cwd: Path):
    return _staged_context_provider(
        "execution_runtime",
        _EXECUTE_PHASE_EXECUTION_RUNTIME_FIELDS,
        lambda: _build_execution_runtime_context(cwd),
    )


def _build_resume_file_context(
    cwd: Path,
    *,
    continuity_handoff_file: str | None = None,
    selected_fields: frozenset[str],
) -> dict[str, object]:
    """Build file-content payloads for resume-work init surfaces."""
    result = _build_selected_file_context(
        cwd,
        selected_fields,
        _RESUME_FILE_CONTEXT_PATHS,
        _safe_read_file_truncated,
    )

    if "continuity_handoff_content" in selected_fields:
        handoff_path: Path | None = None
        if isinstance(continuity_handoff_file, str) and continuity_handoff_file.strip():
            candidate = Path(continuity_handoff_file).expanduser()
            if not candidate.is_absolute():
                candidate = cwd / candidate
            try:
                candidate.resolve(strict=False).relative_to(cwd.resolve(strict=False))
            except ValueError:
                handoff_path = None
            else:
                handoff_path = candidate
        result["continuity_handoff_content"] = (
            _safe_read_file_truncated(handoff_path) if handoff_path is not None else None
        )

    return result


def _progress_status_from_roadmap_disk_status(disk_status: str) -> str:
    """Map roadmap disk inventory states onto the progress init status vocabulary."""

    if disk_status == "complete":
        return "complete"
    if disk_status in {"planned", "partial"}:
        return "in_progress"
    if disk_status == "researched":
        return "researched"
    return "pending"


def _build_disk_progress_phase_inventory(
    cwd: Path,
) -> tuple[list[dict[str, object]], dict[str, object] | None, dict[str, object] | None]:
    """Build legacy disk-only phase inventory for projects without ROADMAP.md phases."""

    layout = ProjectLayout(cwd)
    phases_dir = layout.phases_dir
    phases: list[dict[str, object]] = []
    current_phase: dict[str, object] | None = None
    next_phase: dict[str, object] | None = None

    try:
        dirs = sorted(
            (d.name for d in phases_dir.iterdir() if d.is_dir()),
            key=_phase_sort_key,
        )
        for dir_name in dirs:
            dir_match = re.match(r"^(\d+(?:\.\d+)*)-?(.*)", dir_name)
            phase_number = dir_match.group(1) if dir_match else dir_name
            phase_name = dir_match.group(2) if dir_match and dir_match.group(2) else None

            phase_path = phases_dir / dir_name
            phase_files = [f.name for f in phase_path.iterdir() if f.is_file()]

            plans = [f for f in phase_files if f.endswith(PLAN_SUFFIX) or f == STANDALONE_PLAN]
            summaries = [f for f in phase_files if layout.is_summary_file(f)]
            has_research = any(f.endswith(RESEARCH_SUFFIX) or f == STANDALONE_RESEARCH for f in phase_files)

            summary_count = _matching_phase_artifact_count(plans, summaries)

            if _is_phase_complete(len(plans), summary_count):
                status = "complete"
            elif plans:
                status = "in_progress"
            elif has_research:
                status = "researched"
            else:
                status = "pending"

            phase_entry: dict[str, object] = {
                "number": phase_number,
                "name": phase_name,
                "directory": f"{PLANNING_DIR_NAME}/{PHASES_DIR_NAME}/{dir_name}",
                "status": status,
                "disk_status": status,
                "plan_count": len(plans),
                "summary_count": summary_count,
                "has_research": has_research,
            }
            phases.append(phase_entry)

            if current_phase is None and status in ("in_progress", "researched"):
                current_phase = phase_entry
            if next_phase is None and status == "pending":
                next_phase = phase_entry
    except FileNotFoundError:
        pass

    return phases, current_phase, next_phase


def _build_progress_phase_inventory(
    cwd: Path,
) -> tuple[list[dict[str, object]], dict[str, object] | None, dict[str, object] | None]:
    """Build progress phase inventory from roadmap analysis, with disk-only fallback."""

    roadmap = roadmap_analyze(cwd)
    if not roadmap.phases:
        return _build_disk_progress_phase_inventory(cwd)

    phases: list[dict[str, object]] = []
    by_number: dict[str, dict[str, object]] = {}
    layout = ProjectLayout(cwd)
    phase_dir_names: list[str] = []
    if layout.phases_dir.is_dir():
        phase_dir_names = [path.name for path in layout.phases_dir.iterdir() if path.is_dir()]

    for phase in roadmap.phases:
        normalized = _normalize_phase_name(str(phase.number))
        dir_match_name = next(
            (name for name in phase_dir_names if name.startswith(normalized + "-") or name == normalized),
            None,
        )
        status = _progress_status_from_roadmap_disk_status(phase.disk_status)
        phase_entry: dict[str, object] = {
            "number": phase.number,
            "name": phase.name,
            "directory": (
                f"{PLANNING_DIR_NAME}/{PHASES_DIR_NAME}/{dir_match_name}" if dir_match_name is not None else None
            ),
            "status": status,
            "disk_status": phase.disk_status,
            "roadmap_complete": phase.roadmap_complete,
            "plan_count": phase.plan_count,
            "summary_count": phase.summary_count,
            "has_research": phase.has_research,
            "has_context": phase.has_context,
        }
        phases.append(phase_entry)
        by_number[normalized] = phase_entry

    def _lookup(number: str | None) -> dict[str, object] | None:
        if not number:
            return None
        return by_number.get(_normalize_phase_name(str(number)))

    return phases, _lookup(roadmap.current_phase), _lookup(roadmap.next_phase)


def init_plan_phase(
    cwd: Path,
    phase: str | None,
    includes: set[str] | None = None,
    stage: str | None = None,
) -> dict:
    """Assemble context for phase planning.

    Args:
        cwd: Project root directory.
        phase: Phase identifier.
        includes: Optional set of file sections to embed
                  (state, roadmap, requirements, context, research, verification, validation).
    """
    includes = includes or set()
    if stage is not None and includes:
        raise ValueError(
            "gpd init plan-phase does not allow --include together with --stage; "
            "stage payloads already declare their required context."
        )
    effective_cwd = _resolve_project_scoped_cwd(cwd)
    config = load_config(effective_cwd)
    selected_phase = phase.strip() if isinstance(phase, str) and phase.strip() else None
    if selected_phase is None:
        selected_phase = _infer_next_unplanned_roadmap_phase(effective_cwd)
        if selected_phase is None:
            raise ValidationError(
                "phase is required for init plan-phase because no unplanned phase could be inferred from ROADMAP.md. "
                "Provide a phase identifier such as '1', '03', or '3.1'."
            )

    phase_info = _try_find_phase(effective_cwd, selected_phase)
    phase_target = (
        phase_info
        or _roadmap_phase_target_payload(effective_cwd, selected_phase)
        or {
            "phase_number": selected_phase,
            "phase_name": None,
            "phase_slug": None,
        }
    )

    result: dict[str, object] = {
        # Models
        "researcher_model": _resolve_model(effective_cwd, "gpd-phase-researcher", config),
        "planner_model": _resolve_model(effective_cwd, "gpd-planner", config),
        "checker_model": _resolve_model(effective_cwd, "gpd-plan-checker", config),
        # Workflow flags
        "research_enabled": config["research"],
        "plan_checker_enabled": config["plan_checker"],
        "commit_docs": config["commit_docs"],
        "autonomy": config["autonomy"],
        "research_mode": config["research_mode"],
        # Phase info
        "phase_found": phase_info is not None,
        "phase_dir": phase_info["directory"] if phase_info else None,
        "phase_number": phase_target["phase_number"],
        "phase_name": phase_target.get("phase_name"),
        "phase_slug": phase_target.get("phase_slug"),
        "padded_phase": _normalize_phase_name(str(phase_target["phase_number"])),
        # Existing artifacts
        "has_research": phase_info.get("has_research", False) if phase_info else False,
        "has_context": phase_info.get("has_context", False) if phase_info else False,
        "has_plans": len(phase_info.get("plans", [])) > 0 if phase_info else False,
        "plan_count": len(phase_info.get("plans", [])) if phase_info else 0,
        # Environment
        "planning_exists": _path_exists(effective_cwd, PLANNING_DIR_NAME),
        "roadmap_exists": _path_exists(effective_cwd, f"{PLANNING_DIR_NAME}/{ROADMAP_FILENAME}"),
        # Platform
        "platform": _detect_platform(effective_cwd),
    }
    if stage is None:
        result.update(_build_reference_runtime_context(effective_cwd))
        result.update(_build_state_memory_runtime_context(effective_cwd))
        result.update(
            _build_plan_phase_file_context(
                effective_cwd,
                phase_info,
                selected_fields=_selected_file_fields_from_includes(includes, _PLAN_PHASE_INCLUDE_FILE_FIELDS),
            )
        )
        if "state" in includes:
            result.update(_build_structured_state_runtime_context(effective_cwd))
        return result

    from gpd.core.workflow_staging import load_workflow_stage_manifest

    manifest = load_workflow_stage_manifest("plan-phase")

    return _assemble_staged_init_payload(
        workflow_id="plan-phase",
        stage_id=stage,
        cwd=effective_cwd,
        base_payload=result,
        manifest=manifest,
        providers=(
            _staged_reference_provider(
                effective_cwd,
                _PLAN_PHASE_REFERENCE_RUNTIME_FIELDS,
                _PLAN_PHASE_CONTRACT_GATE_FIELDS,
            ),
            _staged_state_memory_provider(effective_cwd, _PLAN_PHASE_STATE_MEMORY_FIELDS),
            _staged_structured_state_provider(effective_cwd, _PLAN_PHASE_STRUCTURED_STATE_FIELDS),
            _staged_selected_fields_provider(
                "file_content",
                _PLAN_PHASE_FILE_CONTENT_FIELDS,
                _PLAN_PHASE_FILE_CONTENT_FIELDS,
                lambda selected_fields: _build_plan_phase_file_context(effective_cwd, phase_info, selected_fields),
            ),
        ),
    )


def init_new_project(cwd: Path, stage: str | None = None) -> dict:
    """Assemble context for new project creation."""
    _requested_cwd, project_cwd, base_result = _workspace_start_classifier_context(cwd)
    config = load_config(project_cwd)

    base_result = {
        "commit_docs": config["commit_docs"],
        "autonomy": config["autonomy"],
        "research_mode": config["research_mode"],
        **base_result,
    }

    if stage is None:
        result = dict(base_result)
        result.update(
            {
                # Models
                "researcher_model": _resolve_model(project_cwd, "gpd-project-researcher", config),
                "synthesizer_model": _resolve_model(project_cwd, "gpd-research-synthesizer", config),
                "roadmapper_model": _resolve_model(project_cwd, "gpd-roadmapper", config),
            }
        )
        result.update(_build_new_project_contract_runtime_context(project_cwd))
        return result

    from gpd.core.workflow_staging import load_workflow_stage_manifest

    manifest = load_workflow_stage_manifest("new-project")
    return _assemble_staged_init_payload(
        workflow_id="new-project",
        stage_id=stage,
        cwd=project_cwd,
        base_payload=base_result,
        manifest=manifest,
        providers=(
            _staged_scalar_field_provider(
                "researcher_model",
                lambda: _resolve_model(project_cwd, "gpd-project-researcher", config),
            ),
            _staged_scalar_field_provider(
                "synthesizer_model",
                lambda: _resolve_model(project_cwd, "gpd-research-synthesizer", config),
            ),
            _staged_scalar_field_provider(
                "roadmapper_model",
                lambda: _resolve_model(project_cwd, "gpd-roadmapper", config),
            ),
            _staged_contract_provider(project_cwd, _PROJECT_CONTRACT_GATE_FIELDS),
        ),
    )


def init_start_context(cwd: Path) -> dict[str, object]:
    """Assemble the thin read-only start-router context."""

    _requested_cwd, project_cwd, classifier = _workspace_start_classifier_context(cwd)
    init_progress = {
        "exists": classifier["init_progress_exists"],
        "status": classifier["init_progress_status"],
        "valid": classifier["init_progress_valid"],
        "corrupt": classifier["init_progress_corrupt"],
        "step": classifier["init_progress_step"],
        "description": classifier["init_progress_description"],
        "path": classifier["init_progress_path"],
    }
    folder_state = _start_folder_state(classifier)

    return {
        "schema_version": "start_context.v1",
        "workspace_root": project_cwd.as_posix(),
        "folder_state": folder_state,
        "classification": folder_state,
        **classifier,
        "init_progress": init_progress,
        "visible_choices": start_visible_choices(classifier),
        "raw_diagnostics_command": "gpd --raw init new-project",
    }


def init_new_milestone(cwd: Path, stage: str | None = None) -> dict:
    """Assemble context for new milestone creation."""
    effective_cwd = _resolve_project_scoped_cwd(cwd)
    config = load_config(effective_cwd)
    milestone = _try_get_milestone_info(effective_cwd)
    base_result = {
        "init_root_policy": InitRootPolicy.PROJECT_SCOPED.value,
        # Config
        "commit_docs": config["commit_docs"],
        "autonomy": config["autonomy"],
        "research_mode": config["research_mode"],
        "research_enabled": config["research"],
        # Current milestone
        "current_milestone": milestone["version"],
        "current_milestone_name": milestone["name"],
        # File existence
        "project_exists": _path_exists(effective_cwd, f"{PLANNING_DIR_NAME}/{PROJECT_FILENAME}"),
        "roadmap_exists": _path_exists(effective_cwd, f"{PLANNING_DIR_NAME}/{ROADMAP_FILENAME}"),
        "state_exists": _state_exists(effective_cwd),
        # Platform
        "platform": _detect_platform(effective_cwd),
    }

    if stage is None:
        result = dict(base_result)
        result.update(
            {
                # Models
                "researcher_model": _resolve_model(effective_cwd, "gpd-project-researcher", config),
                "synthesizer_model": _resolve_model(effective_cwd, "gpd-research-synthesizer", config),
                "roadmapper_model": _resolve_model(effective_cwd, "gpd-roadmapper", config),
            }
        )
        result.update(_build_reference_runtime_context(effective_cwd))
        result.update(_build_state_memory_runtime_context(effective_cwd))
        return result

    from gpd.core.workflow_staging import load_workflow_stage_manifest

    manifest = load_workflow_stage_manifest("new-milestone")

    return _assemble_staged_init_payload(
        workflow_id="new-milestone",
        stage_id=stage,
        cwd=effective_cwd,
        base_payload=base_result,
        manifest=manifest,
        providers=(
            _staged_scalar_field_provider(
                "researcher_model",
                lambda: _resolve_model(effective_cwd, "gpd-project-researcher", config),
            ),
            _staged_scalar_field_provider(
                "synthesizer_model",
                lambda: _resolve_model(effective_cwd, "gpd-research-synthesizer", config),
            ),
            _staged_scalar_field_provider(
                "roadmapper_model",
                lambda: _resolve_model(effective_cwd, "gpd-roadmapper", config),
            ),
            _staged_reference_provider(
                effective_cwd,
                _NEW_MILESTONE_REFERENCE_RUNTIME_FIELDS,
                _PROJECT_CONTRACT_GATE_FIELDS,
            ),
            _staged_state_memory_provider(effective_cwd, _STATE_MEMORY_FIELDS),
            _staged_file_context_provider(
                _NEW_MILESTONE_FILE_CONTENT_FIELDS,
                cwd=effective_cwd,
                field_paths=_NEW_MILESTONE_FILE_CONTEXT_PATHS,
                read_file=_safe_read_file_truncated,
            ),
        ),
    )


def init_build_persona(cwd: Path, stage: str | None = None) -> dict:
    """Assemble staged context for the research-persona builder workflow."""
    if stage is None:
        return {
            "storage_policy": "candidate_patch_only",
            "mutation_route": "gpd research-persona apply-patch",
            "raw_profile_prompt_policy": "forbidden",
        }

    from gpd.core.workflow_staging import load_workflow_stage_manifest

    manifest = load_workflow_stage_manifest("build-persona")
    return _assemble_staged_init_payload(
        workflow_id="build-persona",
        stage_id=stage,
        cwd=cwd.expanduser().resolve(strict=False),
        base_payload={},
        manifest=manifest,
    )


def init_quick(cwd: Path, description: str | None = None, stage: str | None = None) -> dict:
    """Assemble context for quick task execution."""
    return _init_quick_builder(cwd, description=description, stage=stage, deps=_workflow_init_dependencies())


def init_resume(cwd: Path, *, data_root: Path | None = None, stage: str | None = None) -> dict:
    """Assemble context for resuming work."""
    requested_cwd = cwd.expanduser().resolve(strict=False)
    workspace_planning_exists = _path_exists(requested_cwd, PLANNING_DIR_NAME)
    workspace_roadmap_exists = _path_exists(requested_cwd, f"{PLANNING_DIR_NAME}/{ROADMAP_FILENAME}")
    workspace_project_exists = _path_exists(requested_cwd, f"{PLANNING_DIR_NAME}/{PROJECT_FILENAME}")
    workspace_state_exists = _state_exists(requested_cwd)
    effective_cwd, reentry_metadata = _resolve_reentry_context(
        requested_cwd,
        data_root=data_root,
        prefer_workspace_layout=True,
    )
    config = load_config(effective_cwd)
    execution_context = _build_execution_runtime_context(effective_cwd)
    result_lookup_by_id = _build_resume_result_lookup(effective_cwd)

    # Check for interrupted agent
    interrupted_agent_id = None
    agent_id_file = effective_cwd / PLANNING_DIR_NAME / AGENT_ID_FILENAME
    try:
        interrupted_agent_id = agent_id_file.read_text(encoding="utf-8").strip() or None
    except (FileNotFoundError, OSError):
        pass

    continuation_state = _build_resume_read_state(
        execution_context,
        interrupted_agent_id=interrupted_agent_id,
        result_lookup_by_id=result_lookup_by_id,
    )
    continuation_state, recent_bounded_segment_promoted = _promote_auto_selected_recent_bounded_segment(
        continuation_state,
        reentry_metadata=reentry_metadata,
        result_lookup_by_id=result_lookup_by_id,
    )
    active_bounded_segment = continuation_state.get("active_bounded_segment")
    if not isinstance(active_bounded_segment, dict):
        active_bounded_segment = None
    has_interrupted_agent = bool(continuation_state.get("has_interrupted_agent"))
    normalized_interrupted_agent_id = continuation_state.get("interrupted_agent_id")
    if not isinstance(normalized_interrupted_agent_id, str) or not normalized_interrupted_agent_id.strip():
        normalized_interrupted_agent_id = interrupted_agent_id

    continuity_handoff_file = continuation_state.get("continuity_handoff_file")
    if not isinstance(continuity_handoff_file, str) or not continuity_handoff_file.strip():
        continuity_handoff_file = None
    recorded_continuity_handoff_file = continuation_state.get("recorded_continuity_handoff_file")
    if not isinstance(recorded_continuity_handoff_file, str) or not recorded_continuity_handoff_file.strip():
        recorded_continuity_handoff_file = None
    missing_continuity_handoff_file = continuation_state.get("missing_continuity_handoff_file")
    if not isinstance(missing_continuity_handoff_file, str) or not missing_continuity_handoff_file.strip():
        missing_continuity_handoff_file = None
    derived_execution_head = continuation_state.get("derived_execution_head")
    if not isinstance(derived_execution_head, dict):
        derived_execution_head = (
            execution_context.get("current_execution")
            if isinstance(execution_context.get("current_execution"), dict)
            else None
        )
    resume_candidates = continuation_state.get("resume_candidates")
    if not isinstance(resume_candidates, list):
        resume_candidates = []
    active_resume_kind = continuation_state.get("active_resume_kind")
    if not isinstance(active_resume_kind, str) or not active_resume_kind.strip():
        active_resume_kind = None
    active_resume_origin = continuation_state.get("active_resume_origin")
    if not isinstance(active_resume_origin, str) or not active_resume_origin.strip():
        active_resume_origin = None
    active_resume_pointer = continuation_state.get("active_resume_pointer")
    if not isinstance(active_resume_pointer, str) or not active_resume_pointer.strip():
        active_resume_pointer = None
    active_resume_result = continuation_state.get("active_resume_result")
    if not isinstance(active_resume_result, dict):
        active_resume_result = None

    base_result = {
        "workspace_root": reentry_metadata["workspace_root"],
        "project_root": reentry_metadata["project_root"],
        "project_root_source": reentry_metadata["project_root_source"],
        "project_root_auto_selected": reentry_metadata["project_root_auto_selected"],
        "init_root_policy": InitRootPolicy.PROJECT_REENTRY_ALLOWED.value,
        "project_reentry_mode": reentry_metadata["project_reentry_mode"],
        "project_reentry_requires_selection": reentry_metadata["project_reentry_requires_selection"],
        "project_reentry_selected_candidate": reentry_metadata.get("project_reentry_selected_candidate"),
        "project_reentry_candidates": reentry_metadata["project_reentry_candidates"],
        # Requested workspace availability.
        "workspace_state_exists": workspace_state_exists,
        "workspace_roadmap_exists": workspace_roadmap_exists,
        "workspace_project_exists": workspace_project_exists,
        "workspace_planning_exists": workspace_planning_exists,
        # Selected project availability.
        "state_exists": _state_exists(effective_cwd),
        "state_json_backup_exists": _path_exists(effective_cwd, f"{PLANNING_DIR_NAME}/{STATE_JSON_BACKUP_FILENAME}"),
        "roadmap_exists": _path_exists(effective_cwd, f"{PLANNING_DIR_NAME}/{ROADMAP_FILENAME}"),
        "project_exists": _path_exists(effective_cwd, f"{PLANNING_DIR_NAME}/{PROJECT_FILENAME}"),
        "planning_exists": _path_exists(effective_cwd, PLANNING_DIR_NAME),
        # Agent state
        "has_interrupted_agent": has_interrupted_agent,
        "interrupted_agent_id": normalized_interrupted_agent_id,
        # Config
        "commit_docs": config["commit_docs"],
        "autonomy": config["autonomy"],
        "review_cadence": config["review_cadence"],
        "research_mode": config["research_mode"],
        "resume_surface_schema_version": continuation_state.get(
            "resume_surface_schema_version",
            RESUME_SURFACE_SCHEMA_VERSION,
        ),
        "active_bounded_segment": active_bounded_segment,
        "derived_execution_head": derived_execution_head,
        "derived_execution_head_resume_file": execution_context.get("current_execution_resume_file"),
        "continuity_handoff_file": continuity_handoff_file if isinstance(continuity_handoff_file, str) else None,
        "recorded_continuity_handoff_file": (
            recorded_continuity_handoff_file if isinstance(recorded_continuity_handoff_file, str) else None
        ),
        "missing_continuity_handoff_file": (
            missing_continuity_handoff_file if isinstance(missing_continuity_handoff_file, str) else None
        ),
        "has_continuity_handoff": bool(continuation_state.get("has_continuity_handoff")),
        "active_resume_kind": active_resume_kind,
        "active_resume_origin": active_resume_origin,
        "active_resume_pointer": active_resume_pointer,
        "active_resume_result": active_resume_result,
        "resume_candidates": resume_candidates,
        # Platform
        "platform": _detect_platform(effective_cwd),
    }
    if reentry_metadata.get("project_reentry_diagnostics"):
        base_result["project_reentry_diagnostics"] = reentry_metadata["project_reentry_diagnostics"]
    execution_public = {
        key: value
        for key, value in execution_context.items()
        if key != "resume_projection" and key not in RESUME_BACKEND_ONLY_FIELDS
    }
    base_result.update(execution_public)
    if recent_bounded_segment_promoted and not bool(base_result.get("execution_resumable")):
        base_result["execution_resumable"] = True

    if stage is None:
        result = dict(base_result)
        result.update(_build_reference_runtime_context(effective_cwd))
        return canonicalize_resume_public_payload(result)

    from gpd.core.workflow_staging import load_workflow_stage_manifest

    manifest = load_workflow_stage_manifest("resume-work")

    def canonicalize_resume_staged_payload(_assembly_context: object, staged_source: dict[str, object]) -> None:
        canonical = canonicalize_resume_public_payload(staged_source)
        staged_source.clear()
        staged_source.update(canonical)

    return _assemble_staged_init_payload(
        workflow_id="resume-work",
        stage_id=stage,
        cwd=effective_cwd,
        base_payload=base_result,
        manifest=manifest,
        providers=(
            _staged_reference_provider(effective_cwd, _RESUME_REFERENCE_RUNTIME_FIELDS, _PROJECT_CONTRACT_GATE_FIELDS),
            _staged_structured_state_provider(effective_cwd, _STRUCTURED_STATE_FIELDS),
            _staged_state_memory_provider(effective_cwd, _STATE_MEMORY_FIELDS),
            _staged_selected_fields_provider(
                "file_content",
                _RESUME_FILE_CONTENT_FIELDS,
                _RESUME_FILE_CONTENT_FIELDS,
                lambda selected_fields: _build_resume_file_context(
                    effective_cwd,
                    continuity_handoff_file=continuity_handoff_file,
                    selected_fields=selected_fields,
                ),
            ),
        ),
        postprocessors=(canonicalize_resume_staged_payload,),
    )


def init_sync_state(cwd: Path, *, stage: str | None = None) -> dict:
    """Assemble context for state reconciliation."""
    return _init_sync_state_builder(cwd, stage=stage, deps=_workflow_init_dependencies())


def init_verify_work(cwd: Path, phase: str | None, stage: str | None = None) -> dict:
    """Assemble context for work verification."""
    if not phase and stage != "session_router":
        raise ValidationError(
            "phase is required for init verify-work. Provide a phase identifier such as '1', '03', or '3.1'."
        )

    cwd = _resolve_project_scoped_cwd(cwd)
    config = load_config(cwd)
    phase_info = _try_find_phase(cwd, phase) if phase else None
    phase_dir = phase_info["directory"] if phase_info else None
    phase_dir_abs = (cwd / str(phase_dir)).as_posix() if phase_dir else None
    verification_report_path, verification_report_status_payload = _verify_work_status_payload(cwd, phase_info)
    phase_proof_review_status = resolve_phase_proof_review_status(
        cwd,
        cwd / phase_dir if phase_dir else None,
        persist_manifest=stage is None,
    )

    base_result = {
        # Models
        "planner_model": _resolve_model(cwd, "gpd-planner", config),
        "checker_model": _resolve_model(cwd, "gpd-plan-checker", config),
        "verifier_model": _resolve_model(cwd, "gpd-verifier", config),
        # Config
        "commit_docs": config["commit_docs"],
        "autonomy": config["autonomy"],
        "research_mode": config["research_mode"],
        "project_root": cwd.as_posix(),
        # Phase info
        "phase_found": phase_info is not None,
        "phase_dir": phase_dir,
        "phase_dir_abs": phase_dir_abs,
        "phase_number": phase_info["phase_number"] if phase_info else None,
        "phase_name": phase_info.get("phase_name") if phase_info else None,
        # Existing artifacts
        "has_verification": phase_info.get("has_verification", False) if phase_info else False,
        "has_validation": phase_info.get("has_validation", False) if phase_info else False,
        "active_verification_sessions": _active_verification_sessions(cwd),
        "verification_report_path": verification_report_path,
        "verification_report_status": verification_report_status_payload["routing_status"],
        "verification_session_status": verification_report_status_payload["session_status"],
        "verification_report_status_payload": verification_report_status_payload,
        "phase_proof_review_status": phase_proof_review_status.to_context_dict(cwd),
        # Platform
        "platform": _detect_platform(cwd),
    }
    if stage is None:
        result = dict(base_result)
        result.update(_build_reference_runtime_context(cwd, persist_manuscript_proof_review_manifest=True))
        result.update(_build_structured_state_runtime_context(cwd))
        result.update(_build_state_memory_runtime_context(cwd))
        return result

    from gpd.core.workflow_staging import load_workflow_stage_manifest

    manifest = load_workflow_stage_manifest("verify-work")

    return _assemble_staged_init_payload(
        workflow_id="verify-work",
        stage_id=stage,
        cwd=cwd,
        base_payload=base_result,
        manifest=manifest,
        providers=(
            _staged_reference_provider(cwd, _VERIFY_WORK_REFERENCE_RUNTIME_FIELDS, _VERIFY_WORK_CONTRACT_GATE_FIELDS),
            _staged_structured_state_provider(cwd, _VERIFY_WORK_STRUCTURED_STATE_FIELDS),
            _staged_state_memory_provider(cwd, _VERIFY_WORK_STATE_MEMORY_FIELDS),
            _staged_schema_bridge_provider(
                _VERIFY_WORK_SCHEMA_BRIDGE_FIELDS,
                phase_info=phase_info,
                missing_phase_message=(
                    f"verify-work stage {stage!r} requires a resolved phase so verification-report bridge commands can be built."
                ),
                bridge_builders={
                    "verification_report_skeleton_bridge": lambda: _build_verification_report_skeleton_bridge(
                        cwd,
                        phase_info,
                    ),
                    "verification_report_finalizer_bridge": lambda: _build_verification_report_finalizer_bridge(
                        cwd,
                        phase_info,
                    ),
                    "proof_redteam_finalizer_bridge": lambda: _build_proof_redteam_finalizer_bridge(
                        cwd,
                        phase_info,
                    ),
                },
            ),
        ),
    )


def _resolve_write_paper_external_authoring_intake_for_init(
    effective_cwd: Path,
    subject: str | None,
    *,
    launch_cwd: Path,
) -> WritePaperExternalAuthoringIntakeResolution | None:
    """Resolve and validate ``write-paper --intake`` before staged context assembly."""

    if not has_write_paper_external_authoring_intake(subject):
        return None
    state_exists, roadmap_exists, project_exists = recoverable_project_context(effective_cwd)
    if state_exists or roadmap_exists or project_exists:
        raise ValueError(reject_write_paper_intake_inside_project_detail())

    resolution = resolve_write_paper_external_authoring_intake(
        effective_cwd,
        subject,
        workspace_cwd=launch_cwd,
    )
    if resolution is None:
        return None
    if resolution.status != "resolved":
        raise ValueError(resolution.detail)
    return resolution


def init_write_paper(cwd: Path, subject: str | None = None, stage: str | None = None) -> dict:
    """Assemble context for manuscript authoring and publication review."""
    launch_cwd = cwd.expanduser().resolve(strict=False)
    effective_cwd = _resolve_project_scoped_cwd(launch_cwd)
    launch_subject = _write_paper_subject_from_launch_arguments(subject)
    external_authoring_intake = _resolve_write_paper_external_authoring_intake_for_init(
        effective_cwd,
        subject,
        launch_cwd=launch_cwd,
    )
    config = load_config(effective_cwd)
    base_result: dict[str, object] = {
        "commit_docs": config["commit_docs"],
        "project_root": effective_cwd.as_posix(),
        "state_exists": _state_exists(effective_cwd),
        "project_exists": _path_exists(effective_cwd, f"{PLANNING_DIR_NAME}/{PROJECT_FILENAME}"),
        "autonomy": config["autonomy"],
        "research_mode": config["research_mode"],
        "platform": _detect_platform(effective_cwd),
    }
    base_result["write_paper_argument_input"] = subject.strip() if isinstance(subject, str) else ""
    if launch_subject:
        base_result["write_paper_launch_subject"] = launch_subject
    if stage is None:
        result = dict(base_result)
        result.update(
            _build_publication_bootstrap_runtime_context(
                effective_cwd,
                external_authoring_intake=external_authoring_intake,
            )
        )
        if external_authoring_intake is None:
            result.update(_build_publication_runtime_snapshot_context(effective_cwd))
        return result

    from gpd.core.workflow_staging import load_workflow_stage_manifest

    manifest = load_workflow_stage_manifest("write-paper")

    def build_write_paper_reference_or_bootstrap(assembly_context: object) -> Mapping[str, object]:
        required_fields = assembly_context.required_fields
        reference_fields = required_fields & _WRITE_PAPER_REFERENCE_RUNTIME_FIELDS
        needs_full_reference_context = bool(reference_fields)
        needs_bootstrap_reference_context = bool(required_fields & _WRITE_PAPER_BOOTSTRAP_REFERENCE_FIELDS)
        needs_contract_gate_context = bool(required_fields & _PROJECT_CONTRACT_GATE_FIELDS)
        needs_publication_bootstrap_context = bool(required_fields & _WRITE_PAPER_PUBLICATION_BOOTSTRAP_FIELDS)
        payload: dict[str, object] = {}
        if needs_full_reference_context:
            payload.update(_build_staged_reference_runtime_context(effective_cwd, reference_fields))
        elif needs_bootstrap_reference_context or needs_contract_gate_context or needs_publication_bootstrap_context:
            payload.update(
                _build_publication_bootstrap_runtime_context(
                    effective_cwd,
                    external_authoring_intake=external_authoring_intake,
                    include_protocol_context="protocol_bundle_context" in required_fields,
                    include_active_reference_context="active_reference_context" in required_fields,
                )
            )
        if needs_full_reference_context and needs_publication_bootstrap_context:
            payload.update(
                _build_publication_bootstrap_runtime_context(
                    effective_cwd,
                    external_authoring_intake=external_authoring_intake,
                    include_protocol_context="protocol_bundle_context" in required_fields,
                    include_active_reference_context="active_reference_context" in required_fields,
                )
            )
        return payload

    return _assemble_staged_init_payload(
        workflow_id="write-paper",
        stage_id=stage,
        cwd=effective_cwd,
        base_payload=base_result,
        manifest=manifest,
        providers=(
            _staged_assembly_context_provider(
                "reference_or_publication_bootstrap",
                _WRITE_PAPER_REFERENCE_RUNTIME_FIELDS
                | _WRITE_PAPER_BOOTSTRAP_REFERENCE_FIELDS
                | _PROJECT_CONTRACT_GATE_FIELDS
                | _WRITE_PAPER_PUBLICATION_BOOTSTRAP_FIELDS,
                build_write_paper_reference_or_bootstrap,
            ),
            _staged_state_memory_provider(effective_cwd, _STATE_MEMORY_FIELDS),
            _staged_file_context_provider(
                _WRITE_PAPER_FILE_CONTENT_FIELDS,
                cwd=effective_cwd,
                field_paths=_PLAN_PHASE_PLANNING_FILE_CONTEXT_PATHS,
                read_file=_safe_read_file_truncated,
            ),
        ),
    )


def init_peer_review(cwd: Path, subject: str | None = None, stage: str | None = None) -> dict:
    """Assemble context for staged manuscript peer review."""
    launch_cwd = cwd.expanduser().resolve(strict=False)
    effective_cwd = _resolve_project_scoped_cwd(launch_cwd)
    config = load_config(effective_cwd)
    base_result: dict[str, object] = {
        "commit_docs": config["commit_docs"],
        "project_root": effective_cwd.as_posix(),
        "state_exists": _state_exists(effective_cwd),
        "project_exists": _path_exists(effective_cwd, f"{PLANNING_DIR_NAME}/{PROJECT_FILENAME}"),
        "autonomy": config["autonomy"],
        "research_mode": config["research_mode"],
        "platform": _detect_platform(effective_cwd),
    }
    if stage is None:
        result = dict(base_result)
        result.update(_build_peer_review_runtime_context(effective_cwd, subject, launch_cwd=launch_cwd))
        return result

    from gpd.core.workflow_staging import load_workflow_stage_manifest

    manifest = load_workflow_stage_manifest("peer-review")
    return _assemble_staged_init_payload(
        workflow_id="peer-review",
        stage_id=stage,
        cwd=effective_cwd,
        base_payload=base_result,
        manifest=manifest,
        providers=(
            _staged_selected_fields_provider(
                "peer_review_runtime",
                PEER_REVIEW_INIT_FIELDS - frozenset(base_result),
                _PEER_REVIEW_REFERENCE_RUNTIME_FIELDS,
                lambda reference_fields: _build_peer_review_runtime_context(
                    effective_cwd,
                    subject,
                    launch_cwd=launch_cwd,
                    reference_fields=reference_fields,
                ),
            ),
        ),
    )


def init_respond_to_referees(cwd: Path, subject: str | None = None, stage: str | None = None) -> dict:
    """Assemble context for staged referee-response revision work."""
    launch_cwd = cwd.expanduser().resolve(strict=False)
    effective_cwd = _resolve_project_scoped_cwd(launch_cwd)
    manuscript_subject = _respond_to_referees_subject_from_launch_arguments(subject)
    config = load_config(effective_cwd)
    base_result: dict[str, object] = {
        "commit_docs": config["commit_docs"],
        "project_root": effective_cwd.as_posix(),
        "state_exists": _state_exists(effective_cwd),
        "project_exists": _path_exists(effective_cwd, f"{PLANNING_DIR_NAME}/{PROJECT_FILENAME}"),
        "autonomy": config["autonomy"],
        "research_mode": config["research_mode"],
        "platform": _detect_platform(effective_cwd),
    }
    base_result["response_intake_input"] = subject.strip() if isinstance(subject, str) else ""
    if stage is None:
        result = dict(base_result)
        result.update(
            _build_peer_review_runtime_context(
                effective_cwd,
                manuscript_subject,
                launch_cwd=launch_cwd,
                preserve_standalone_publication_roots=True,
            )
        )
        return result

    from gpd.core.workflow_staging import load_workflow_stage_manifest

    manifest = load_workflow_stage_manifest("respond-to-referees")
    return _assemble_staged_init_payload(
        workflow_id="respond-to-referees",
        stage_id=stage,
        cwd=effective_cwd,
        base_payload=base_result,
        manifest=manifest,
        providers=(
            _staged_selected_fields_provider(
                "peer_review_runtime",
                PEER_REVIEW_INIT_FIELDS - frozenset(base_result),
                _PEER_REVIEW_REFERENCE_RUNTIME_FIELDS,
                lambda reference_fields: _build_peer_review_runtime_context(
                    effective_cwd,
                    manuscript_subject,
                    launch_cwd=launch_cwd,
                    preserve_standalone_publication_roots=True,
                    reference_fields=reference_fields,
                ),
            ),
        ),
    )


def init_arxiv_submission(cwd: Path, subject: str | None = None, stage: str | None = None) -> dict:
    """Assemble context for arXiv submission packaging."""
    launch_cwd = cwd.expanduser().resolve(strict=False)
    effective_cwd = _resolve_project_scoped_cwd(launch_cwd)
    subject_input = subject.strip() if isinstance(subject, str) else ""
    resolved_subject = _explicit_subject_from_launch_cwd(subject_input, launch_cwd) if subject_input else None
    config = load_config(effective_cwd)
    invalid_external_subject_context = (
        _arxiv_invalid_external_subject_context(
            effective_cwd,
            subject_input,
            launch_cwd=launch_cwd,
        )
        if subject_input
        else None
    )
    base_result: dict[str, object] = {
        "commit_docs": config["commit_docs"],
        "arxiv_submission_argument_input": subject_input,
        "project_root": effective_cwd.as_posix(),
        "state_exists": _state_exists(effective_cwd),
        "project_exists": _path_exists(effective_cwd, f"{PLANNING_DIR_NAME}/{PROJECT_FILENAME}"),
        "autonomy": config["autonomy"],
        "research_mode": config["research_mode"],
        "platform": _detect_platform(effective_cwd),
    }
    if stage is None:
        result = dict(base_result)
        result.update(_build_publication_bootstrap_runtime_context(effective_cwd))
        if invalid_external_subject_context is not None:
            result.update(invalid_external_subject_context)
        else:
            result.update(
                _build_publication_runtime_snapshot_context(
                    effective_cwd,
                    subject=resolved_subject,
                    pin_response_to_review_round=False,
                )
            )
        return result

    manifest = load_arxiv_submission_stage_contract()

    def build_arxiv_snapshot(_assembly_context: object) -> Mapping[str, object]:
        if invalid_external_subject_context is not None:
            return invalid_external_subject_context
        return _build_publication_runtime_snapshot_context(
            effective_cwd,
            subject=resolved_subject,
            pin_response_to_review_round=False,
        )

    return _assemble_staged_init_payload(
        workflow_id="arxiv-submission",
        stage_id=stage,
        cwd=effective_cwd,
        base_payload=base_result,
        manifest=manifest,
        providers=(
            _staged_context_provider(
                "publication_bootstrap",
                ARXIV_SUBMISSION_BOOTSTRAP_FIELDS,
                lambda: _build_publication_bootstrap_runtime_context(effective_cwd),
            ),
            _staged_context_provider(
                "publication_snapshot",
                ARXIV_SUBMISSION_SNAPSHOT_FIELDS,
                lambda: build_arxiv_snapshot(None),
            ),
        ),
    )


def init_phase_op(
    cwd: Path,
    phase: str | None = None,
    includes: set[str] | None = None,
    stage: str | None = None,
) -> dict:
    """Assemble context for generic phase operations (parameter sweep, etc.)."""
    includes = includes or set()
    if stage is not None and includes:
        raise ValueError(
            "gpd init phase-op does not allow --include together with --stage; "
            "stage payloads already declare their required context."
        )
    effective_cwd = _resolve_project_scoped_cwd(cwd)
    config = load_config(effective_cwd)
    phase_info = _try_find_phase(effective_cwd, phase) if phase else None

    result: dict[str, object] = {
        # Models
        "executor_model": _resolve_model(effective_cwd, "gpd-executor", config),
        "verifier_model": _resolve_model(effective_cwd, "gpd-verifier", config),
        "init_root_policy": InitRootPolicy.PROJECT_SCOPED.value,
        # Config
        "commit_docs": config["commit_docs"],
        "autonomy": config["autonomy"],
        "review_cadence": config["review_cadence"],
        "research_mode": config["research_mode"],
        "parallelization": config["parallelization"],
        "max_unattended_minutes_per_plan": config["max_unattended_minutes_per_plan"],
        "max_unattended_minutes_per_wave": config["max_unattended_minutes_per_wave"],
        "checkpoint_after_n_tasks": config["checkpoint_after_n_tasks"],
        "checkpoint_after_first_load_bearing_result": config["checkpoint_after_first_load_bearing_result"],
        "checkpoint_before_downstream_dependent_tasks": config["checkpoint_before_downstream_dependent_tasks"],
        # Phase info
        "phase_found": phase_info is not None,
        "phase_dir": phase_info["directory"] if phase_info else None,
        "phase_number": phase_info["phase_number"] if phase_info else None,
        "phase_name": phase_info.get("phase_name") if phase_info else None,
        "phase_slug": phase_info.get("phase_slug") if phase_info else None,
        "padded_phase": _normalize_phase_name(phase_info["phase_number"]) if phase_info else None,
        # Existing artifacts
        "has_research": phase_info.get("has_research", False) if phase_info else False,
        "has_context": phase_info.get("has_context", False) if phase_info else False,
        "has_plans": len(phase_info.get("plans", [])) > 0 if phase_info else False,
        "has_verification": phase_info.get("has_verification", False) if phase_info else False,
        "has_validation": phase_info.get("has_validation", False) if phase_info else False,
        "plan_count": len(phase_info.get("plans", [])) if phase_info else 0,
        # File existence
        "roadmap_exists": _path_exists(effective_cwd, f"{PLANNING_DIR_NAME}/{ROADMAP_FILENAME}"),
        "state_exists": _state_exists(effective_cwd),
        "planning_exists": _path_exists(effective_cwd, PLANNING_DIR_NAME),
        # Platform
        "platform": _detect_platform(effective_cwd),
    }
    if stage is None:
        result.update(_build_reference_runtime_context(effective_cwd))
        result.update(_build_state_memory_runtime_context(effective_cwd))
        result.update(_build_execution_runtime_context(effective_cwd))
        selected_file_fields = _selected_file_fields_from_includes(includes, _RESEARCH_PHASE_INCLUDE_FILE_FIELDS)
        result.update(
            _build_selected_file_context(
                effective_cwd,
                selected_file_fields,
                _RESEARCH_PHASE_FILE_CONTEXT_PATHS,
                _safe_read_file_truncated,
            )
        )
        if "state_content" in selected_file_fields:
            result.update(_build_structured_state_runtime_context(effective_cwd))
        return result

    from gpd.core.workflow_staging import load_workflow_stage_manifest

    manifest = load_workflow_stage_manifest("research-phase")

    return _assemble_staged_init_payload(
        workflow_id="research-phase",
        stage_id=stage,
        cwd=effective_cwd,
        base_payload=result,
        manifest=manifest,
        providers=(
            _staged_reference_provider(
                effective_cwd,
                _STAGED_FULL_REFERENCE_RUNTIME_FIELDS | _STAGED_REFERENCE_SUMMARY_FIELDS,
                _EXECUTE_PHASE_CONTRACT_GATE_FIELDS,
            ),
            _staged_structured_state_provider(effective_cwd, _EXECUTE_PHASE_STRUCTURED_STATE_FIELDS),
            _staged_state_memory_provider(effective_cwd, _EXECUTE_PHASE_STATE_MEMORY_FIELDS),
            _staged_execution_provider(effective_cwd),
            _staged_file_context_provider(
                _RESEARCH_PHASE_FILE_CONTENT_FIELDS,
                cwd=effective_cwd,
                field_paths=_RESEARCH_PHASE_FILE_CONTEXT_PATHS,
                read_file=_safe_read_file_truncated,
            ),
        ),
    )


def init_research_phase(
    cwd: Path,
    phase: str | None = None,
    includes: set[str] | None = None,
    stage: str | None = None,
) -> dict:
    """Assemble context for research-phase planning and investigation."""
    return init_phase_op(cwd, phase=phase, includes=includes, stage=stage)


def init_literature_review(cwd: Path, topic: str | None = None, stage: str | None = None) -> dict:
    """Assemble context for literature review orchestration."""
    return _init_literature_review_builder(cwd, topic=topic, stage=stage, deps=_workflow_init_dependencies())


def init_todos(cwd: Path, area: str | None = None) -> dict:
    """Assemble context for todo management."""
    requested_cwd = cwd.expanduser().resolve(strict=False)
    resolution = resolve_project_roots(requested_cwd, policy=RootResolutionPolicy.PROJECT_SCOPED)
    project_exists = bool(resolution and resolution.has_project_layout)
    effective_cwd = (
        resolution.project_root if resolution is not None and resolution.has_project_layout else requested_cwd
    )
    config = load_config(effective_cwd)
    now = datetime.now(UTC)

    pending_dir = effective_cwd / PLANNING_DIR_NAME / TODOS_DIR_NAME / "pending"
    todos: list[dict[str, str]] = []

    try:
        for f in sorted(pending_dir.iterdir()):
            if not f.is_file() or not f.name.endswith(".md"):
                continue
            try:
                content = f.read_text(encoding="utf-8")
            except (UnicodeDecodeError, PermissionError, OSError):
                continue
            parsed_frontmatter = _read_todo_frontmatter(content)
            if parsed_frontmatter is None:
                continue
            title = _extract_frontmatter_field(content, "title", parsed_frontmatter=parsed_frontmatter) or "Untitled"
            todo_area = _extract_frontmatter_field(content, "area", parsed_frontmatter=parsed_frontmatter) or "general"
            created = _extract_frontmatter_field(content, "created", parsed_frontmatter=parsed_frontmatter) or "unknown"

            if area and todo_area != area:
                continue

            todos.append(
                {
                    "file": f.name,
                    "created": created,
                    "title": title,
                    "area": todo_area,
                    "path": f"{PLANNING_DIR_NAME}/{TODOS_DIR_NAME}/pending/{f.name}",
                }
            )
    except (FileNotFoundError, PermissionError):
        pass

    return {
        "init_root_policy": InitRootPolicy.PROJECT_SCOPED.value,
        "workspace_root": requested_cwd.as_posix(),
        "project_root": effective_cwd.as_posix(),
        "project_exists": project_exists,
        # Config
        "commit_docs": config["commit_docs"],
        "autonomy": config["autonomy"],
        "research_mode": config["research_mode"],
        # Timestamps
        "date": now.strftime("%Y-%m-%d"),
        "timestamp": now.isoformat(),
        # Todo inventory
        "todo_count": len(todos),
        "todos": todos,
        "pending_todos": todos,
        "area_filter": area,
        # Paths
        "pending_dir": f"{PLANNING_DIR_NAME}/{TODOS_DIR_NAME}/pending",
        "done_dir": f"{PLANNING_DIR_NAME}/{TODOS_DIR_NAME}/done",
        # File existence
        "planning_exists": _path_exists(effective_cwd, PLANNING_DIR_NAME),
        "todos_dir_exists": _path_exists(effective_cwd, f"{PLANNING_DIR_NAME}/{TODOS_DIR_NAME}"),
        "pending_dir_exists": _path_exists(effective_cwd, f"{PLANNING_DIR_NAME}/{TODOS_DIR_NAME}/pending"),
        # Platform
        "platform": _detect_platform(effective_cwd),
    }


def _parse_autonomous_from_phase(argument_input: str, explicit_from_phase: str | None = None) -> str | None:
    """Return the requested autonomous start phase from CLI-style launch input."""

    if explicit_from_phase is not None and explicit_from_phase.strip():
        return explicit_from_phase.strip()
    match = re.search(r"(?:^|\s)--from(?:=|\s+)([0-9]+(?:\.[0-9]+)*)", argument_input)
    if match is None:
        return None
    return match.group(1)


def _autonomous_roadmap_phase_payload(phase: object) -> dict[str, object]:
    """Serialize the compact roadmap fields autonomous needs for routing."""

    return {
        "number": getattr(phase, "number", None),
        "name": getattr(phase, "name", None),
        "goal": getattr(phase, "goal", None),
        "depends_on": getattr(phase, "depends_on", None),
        "disk_status": getattr(phase, "disk_status", None),
        "roadmap_complete": getattr(phase, "roadmap_complete", False),
        "plan_count": getattr(phase, "plan_count", 0),
        "summary_count": getattr(phase, "summary_count", 0),
        "has_context": getattr(phase, "has_context", False),
        "has_research": getattr(phase, "has_research", False),
    }


def _autonomous_selected_phase(phases: list[object], from_phase: str | None) -> object | None:
    """Select the first incomplete roadmap phase at or after ``from_phase``."""

    threshold = _phase_sort_key(from_phase) if from_phase else None
    for phase in sorted(phases, key=lambda item: _phase_sort_key(str(getattr(item, "number", "")))):
        number = str(getattr(phase, "number", ""))
        if threshold is not None and _phase_sort_key(number) < threshold:
            continue
        if getattr(phase, "disk_status", None) != "complete":
            return phase
    return None


def _autonomous_completed_phase_verification_statuses(cwd: Path, phase_numbers: list[str]) -> list[dict[str, object]]:
    """Return compact session-router style status rows for completed phases."""

    statuses: list[dict[str, object]] = []
    for phase_number in phase_numbers:
        phase_info = _try_find_phase(cwd, phase_number)
        _path, payload = _verify_work_status_payload(cwd, phase_info)
        statuses.append(
            {
                "phase_number": phase_number,
                "path": payload.get("path"),
                "exists": payload.get("exists"),
                "routing_status": payload.get("routing_status"),
                "session_status": payload.get("session_status"),
                "score": payload.get("score"),
                "errors": payload.get("errors", []),
            }
        )
    return statuses


def init_autonomous(
    cwd: Path,
    argument_input: str | None = None,
    stage: str | None = None,
    from_phase: str | None = None,
) -> dict:
    """Assemble context for staged autonomous milestone execution."""

    effective_cwd = _resolve_project_scoped_cwd(cwd)
    config = load_config(effective_cwd)
    argument_text = argument_input.strip() if isinstance(argument_input, str) else ""
    parsed_from_phase = _parse_autonomous_from_phase(argument_text, explicit_from_phase=from_phase)

    milestone = _try_get_milestone_info(effective_cwd)
    milestone_snapshot = _milestone_completion_snapshot(effective_cwd)
    roadmap = roadmap_analyze(effective_cwd)
    roadmap_phases = sorted(roadmap.phases, key=lambda phase: _phase_sort_key(phase.number))
    phase_plan = [_autonomous_roadmap_phase_payload(phase) for phase in roadmap_phases]
    completed_phase_numbers = [str(phase.number) for phase in roadmap_phases if phase.disk_status == "complete"]
    current_phase = _autonomous_selected_phase(roadmap_phases, parsed_from_phase)
    current_phase_number = str(current_phase.number) if current_phase is not None else None
    current_phase_name = str(current_phase.name) if current_phase is not None else None
    current_phase_goal = str(current_phase.goal) if current_phase is not None and current_phase.goal else None

    phase_info = _try_find_phase(effective_cwd, current_phase_number) if current_phase_number else None
    phase_dir = phase_info["directory"] if phase_info else None
    phase_dir_path = effective_cwd / phase_dir if phase_dir else None
    verification_report_path, verification_status_payload = _verify_work_status_payload(effective_cwd, phase_info)
    if verification_status_payload.get("path") is None and verification_report_path is not None:
        verification_status_payload["path"] = verification_report_path
    phase_proof_review_status = resolve_phase_proof_review_status(
        effective_cwd,
        phase_dir_path,
        persist_manifest=False,
    )

    if phase_info is not None:
        phase_number = phase_info["phase_number"]
        phase_name = phase_info.get("phase_name")
        phase_slug = phase_info.get("phase_slug")
        padded_phase = _normalize_phase_name(str(phase_number))
        has_context = bool(phase_info.get("has_context", False))
        plan_count = len(phase_info.get("plans", []))
    else:
        phase_number = current_phase_number
        phase_name = current_phase_name
        phase_slug = _generate_slug(current_phase_name)
        padded_phase = _normalize_phase_name(current_phase_number) if current_phase_number else None
        has_context = bool(getattr(current_phase, "has_context", False)) if current_phase is not None else False
        plan_count = int(getattr(current_phase, "plan_count", 0)) if current_phase is not None else 0

    base_result: dict[str, object] = {
        "project_root": effective_cwd.as_posix(),
        "autonomous_argument_input": argument_text,
        "autonomous_from_phase": parsed_from_phase,
        "commit_docs": config["commit_docs"],
        "autonomy": config["autonomy"],
        "research_mode": config["research_mode"],
        "review_cadence": config["review_cadence"],
        "model_profile": config["model_profile"],
        "platform": _detect_platform(effective_cwd),
        "milestone_version": milestone["version"],
        "milestone_name": milestone["name"],
        "milestone_slug": _generate_slug(milestone["name"]),
        "phase_count": milestone_snapshot.phase_count,
        "completed_phases": milestone_snapshot.completed_phases,
        "all_phases_complete": milestone_snapshot.all_phases_complete,
        "project_exists": _path_exists(effective_cwd, f"{PLANNING_DIR_NAME}/{PROJECT_FILENAME}"),
        "roadmap_exists": _path_exists(effective_cwd, f"{PLANNING_DIR_NAME}/{ROADMAP_FILENAME}"),
        "state_exists": _state_exists(effective_cwd),
        "phases_dir_exists": _path_exists(effective_cwd, f"{PLANNING_DIR_NAME}/{PHASES_DIR_NAME}"),
        "autonomous_phase_plan": phase_plan,
        "autonomous_completed_phase_numbers": completed_phase_numbers,
        "autonomous_completed_phase_verification_statuses": _autonomous_completed_phase_verification_statuses(
            effective_cwd,
            completed_phase_numbers,
        ),
        "autonomous_incomplete_phase_count": sum(1 for phase in roadmap_phases if phase.disk_status != "complete"),
        "autonomous_current_phase_number": current_phase_number,
        "autonomous_current_phase_name": current_phase_name,
        "autonomous_current_phase_goal": current_phase_goal,
        "autonomous_current_phase_success_criteria": None,
        "phase_found": phase_info is not None,
        "phase_dir": phase_dir,
        "phase_number": phase_number,
        "phase_name": phase_name,
        "phase_slug": phase_slug,
        "padded_phase": padded_phase,
        "has_context": has_context,
        "has_plans": plan_count > 0,
        "plan_count": plan_count,
        "verification_report_status": verification_status_payload["routing_status"],
        "verification_report_status_payload": verification_status_payload,
        "phase_proof_review_status": phase_proof_review_status.to_context_dict(effective_cwd),
    }
    missing_known_fields = sorted(_AUTONOMOUS_INIT_FIELDS - set(base_result))
    if missing_known_fields:
        raise ValueError(f"autonomous init field source missing known field(s): {', '.join(missing_known_fields)}")

    if stage is None:
        return base_result

    from gpd.core.workflow_staging import load_autonomous_stage_contract

    manifest = load_autonomous_stage_contract()
    return _assemble_staged_init_payload(
        workflow_id="autonomous",
        stage_id=stage,
        cwd=effective_cwd,
        base_payload=base_result,
        manifest=manifest,
    )


def init_milestone_op(cwd: Path) -> dict:
    """Assemble context for milestone operations (complete, archive, etc.)."""
    effective_cwd = _resolve_project_scoped_cwd(cwd)
    config = load_config(effective_cwd)
    milestone = _try_get_milestone_info(effective_cwd)
    reference_runtime_context = _build_reference_runtime_context(effective_cwd)

    milestone_snapshot = _milestone_completion_snapshot(effective_cwd)

    # Check archived milestones
    milestones_dir = effective_cwd / PLANNING_DIR_NAME / MILESTONES_DIR_NAME
    archived_milestones: list[str] = []
    try:
        archived_milestones = sorted(
            entry.name for entry in milestones_dir.iterdir() if entry.is_dir() or entry.is_file()
        )
    except FileNotFoundError:
        pass

    return {
        "init_root_policy": InitRootPolicy.PROJECT_SCOPED.value,
        # Config
        "commit_docs": config["commit_docs"],
        "autonomy": config["autonomy"],
        "research_mode": config["research_mode"],
        "branching_strategy": config["branching_strategy"],
        "phase_branch_template": config["phase_branch_template"],
        "milestone_branch_template": config["milestone_branch_template"],
        # Current milestone
        "milestone_version": milestone["version"],
        "milestone_name": milestone["name"],
        "milestone_slug": _generate_slug(milestone["name"]),
        # Phase counts
        "phase_count": milestone_snapshot.phase_count,
        "completed_phases": milestone_snapshot.completed_phases,
        "all_phases_complete": milestone_snapshot.all_phases_complete,
        # Archive
        "archived_milestones": archived_milestones,
        "archive_count": len(archived_milestones),
        # File existence
        "project_exists": _path_exists(effective_cwd, f"{PLANNING_DIR_NAME}/{PROJECT_FILENAME}"),
        "roadmap_exists": _path_exists(effective_cwd, f"{PLANNING_DIR_NAME}/{ROADMAP_FILENAME}"),
        "state_exists": _state_exists(effective_cwd),
        "milestones_exists": _path_exists(effective_cwd, f"{PLANNING_DIR_NAME}/{MILESTONES_DIR_NAME}"),
        "phases_dir_exists": _path_exists(effective_cwd, f"{PLANNING_DIR_NAME}/{PHASES_DIR_NAME}"),
        # Platform
        "platform": _detect_platform(effective_cwd),
        **reference_runtime_context,
    }


def init_map_research(cwd: Path, focus: str | None = None, stage: str | None = None) -> dict:
    """Assemble context for research mapping."""
    return _init_map_research_builder(cwd, focus=focus, stage=stage, deps=_workflow_init_dependencies())


def init_progress(
    cwd: Path,
    includes: set[str] | None = None,
    *,
    data_root: Path | None = None,
    include_project_reentry: bool = True,
) -> dict:
    """Assemble context for progress checking.

    Args:
        cwd: Project root directory.
        includes: Optional set of file sections to embed (state, roadmap, project, config).
    """
    includes = includes or set()
    requested_cwd = cwd.expanduser().resolve(strict=False)
    if include_project_reentry:
        effective_cwd, reentry_metadata = _resolve_reentry_context(
            requested_cwd,
            data_root=data_root,
            prefer_workspace_layout=True,
        )
        init_root_policy = InitRootPolicy.PROJECT_REENTRY_ALLOWED.value
    else:
        effective_cwd = _resolve_project_scoped_cwd(requested_cwd)
        reentry_metadata = {
            "workspace_root": requested_cwd.as_posix(),
            "project_root": effective_cwd.as_posix(),
            "project_root_source": "workspace",
            "project_root_auto_selected": False,
        }
        init_root_policy = InitRootPolicy.PROJECT_SCOPED.value
    config = load_config(effective_cwd)
    milestone = _try_get_milestone_info(effective_cwd)

    phases, current_phase, next_phase = _build_progress_phase_inventory(effective_cwd)

    # Check for paused work
    paused_at: str | None = None
    state_content = _safe_read_file(effective_cwd / PLANNING_DIR_NAME / STATE_MD_FILENAME)
    if state_content:
        status_match = re.search(r"\*\*Status:\*\*\s*(.+)", state_content)
        if status_match and status_match.group(1).strip().lower() == "paused":
            stopped_match = re.search(r"\*\*Stopped at:\*\*\s*(.+)", state_content)
            paused_at = stopped_match.group(1).strip() if stopped_match else "true"

    result: dict[str, object] = {
        "workspace_root": reentry_metadata["workspace_root"],
        "project_root": reentry_metadata["project_root"],
        "project_root_source": reentry_metadata["project_root_source"],
        "project_root_auto_selected": reentry_metadata["project_root_auto_selected"],
        "init_root_policy": init_root_policy,
        # Models
        "executor_model": _resolve_model(effective_cwd, "gpd-executor", config),
        "planner_model": _resolve_model(effective_cwd, "gpd-planner", config),
        # Config
        "commit_docs": config["commit_docs"],
        "autonomy": config["autonomy"],
        "review_cadence": config["review_cadence"],
        "research_mode": config["research_mode"],
        # Milestone
        "milestone_version": milestone["version"],
        "milestone_name": milestone["name"],
        # Phase overview
        "phases": phases,
        "phase_count": len(phases),
        "completed_count": sum(1 for p in phases if p["status"] == "complete"),
        "in_progress_count": sum(1 for p in phases if p["status"] == "in_progress"),
        # Current state
        "current_phase": current_phase,
        "next_phase": next_phase,
        "paused_at": paused_at,
        "has_work_in_progress": current_phase is not None,
        # File existence
        "project_exists": _path_exists(effective_cwd, f"{PLANNING_DIR_NAME}/{PROJECT_FILENAME}"),
        "roadmap_exists": _path_exists(effective_cwd, f"{PLANNING_DIR_NAME}/{ROADMAP_FILENAME}"),
        "state_exists": _state_exists(effective_cwd),
        "state_recovery_guidance": _backup_only_state_guidance(effective_cwd),
        # Platform
        "platform": _detect_platform(effective_cwd),
    }
    if include_project_reentry:
        result.update(
            {
                "project_reentry_mode": reentry_metadata["project_reentry_mode"],
                "project_reentry_requires_selection": reentry_metadata["project_reentry_requires_selection"],
                "project_reentry_selected_candidate": reentry_metadata.get("project_reentry_selected_candidate"),
                "project_reentry_candidates": reentry_metadata["project_reentry_candidates"],
            }
        )
        if reentry_metadata.get("project_reentry_diagnostics"):
            result["project_reentry_diagnostics"] = reentry_metadata["project_reentry_diagnostics"]
    include_reference_artifact_content = "references" in includes
    include_protocol_context = "protocols" in includes
    result.update(
        _build_reference_runtime_context(
            effective_cwd,
            include_artifact_content=include_reference_artifact_content,
            include_protocol_context=include_protocol_context,
        )
    )
    result.update(_build_state_memory_runtime_context(effective_cwd))
    result.update(_build_execution_runtime_context(effective_cwd))
    if result.get("execution_paused_at"):
        result["paused_at"] = result["execution_paused_at"]
    if result.get("current_execution") and result["current_phase"] is None:
        current_execution = result["current_execution"]
        if isinstance(current_execution, dict) and current_execution.get("phase"):
            result["current_phase"] = {
                "number": current_execution.get("phase"),
                "name": None,
                "directory": None,
                "status": "in_progress",
                "plan_count": None,
                "summary_count": None,
                "has_research": False,
            }
        result["has_work_in_progress"] = True
    execution_resume_file = result.get("execution_resume_file")
    if (
        result.get("execution_resume_file_source") in {"handoff_resume_file", "continuation.bounded_segment"}
        and isinstance(execution_resume_file, str)
        and execution_resume_file.strip()
    ):
        result["has_work_in_progress"] = True

    # Include file contents
    planning = effective_cwd / PLANNING_DIR_NAME
    if "state" in includes:
        result["state_content"] = _safe_read_file_truncated(planning / STATE_MD_FILENAME)
        result.update(_build_structured_state_runtime_context(effective_cwd))
    if "roadmap" in includes:
        result["roadmap_content"] = _safe_read_file_truncated(planning / ROADMAP_FILENAME)
    if "project" in includes:
        result["project_content"] = _safe_read_file_truncated(planning / PROJECT_FILENAME)
    if "config" in includes:
        result["config_content"] = _safe_read_file_truncated(planning / CONFIG_FILENAME)

    return result
