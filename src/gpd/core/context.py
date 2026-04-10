"""Context assembly for AI agent commands.

Each function gathers project state and produces a structured dict consumed by agent prompts.

Delegates to :mod:`gpd.core.config` for configuration loading and model-tier
resolution so that defaults and model profiles are defined in exactly one place.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Mapping
from datetime import UTC, date, datetime
from pathlib import Path

from pydantic import ValidationError as PydanticValidationError

from gpd.adapters.install_utils import GPD_INSTALL_DIR_NAME
from gpd.adapters.runtime_catalog import iter_runtime_descriptors
from gpd.contracts import ConventionLock, ResearchContract, parse_project_contract_data_salvage
from gpd.core import state as _state_module
from gpd.core.config import GPDProjectConfig
from gpd.core.config import load_config as _load_config_structured
from gpd.core.config import resolve_model as _resolve_model_canonical
from gpd.core.constants import (
    AGENT_ID_FILENAME,
    CONFIG_FILENAME,
    CONTEXT_SUFFIX,
    ENV_GPD_ACTIVE_RUNTIME,
    MILESTONES_DIR_NAME,
    MILESTONES_FILENAME,
    PHASES_DIR_NAME,
    PLAN_SUFFIX,
    PLANNING_DIR_NAME,
    PROJECT_FILENAME,
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
from gpd.core.continuation import (
    ContinuationResumeSource,
    ContinuationSource,
    normalize_continuation_reference,
    resolve_continuation,
)
from gpd.core.conventions import is_bogus_value
from gpd.core.errors import ValidationError
from gpd.core.extras import approximation_list
from gpd.core.knowledge_runtime import discover_knowledge_docs
from gpd.core.manuscript_artifacts import resolve_current_manuscript_entrypoint
from gpd.core.phases import _milestone_completion_snapshot
from gpd.core.project_reentry import (
    ProjectReentryCandidate,
    recoverable_project_context,
    resolve_project_reentry,
)
from gpd.core.proof_review import (
    resolve_manuscript_proof_review_status,
    resolve_phase_proof_review_status,
)
from gpd.core.protocol_bundles import render_protocol_bundle_context, select_protocol_bundles
from gpd.core.publication_runtime import publication_runtime_snapshot_context
from gpd.core.reference_ingestion import ingest_manuscript_reference_status, ingest_reference_artifacts
from gpd.core.results import result_list
from gpd.core.resume_surface import (
    RESUME_COMPATIBILITY_ALIAS_FIELDS,
    RESUME_SURFACE_SCHEMA_VERSION,
    build_resume_candidate,
    build_resume_segment_candidate,
    canonicalize_resume_public_payload,
    resume_origin_for_bounded_segment,
    resume_origin_for_handoff,
    resume_origin_for_interrupted_agent,
)
from gpd.core.root_resolution import resolve_project_root, resolve_project_roots
from gpd.core.state import _current_machine_identity, _finalize_project_contract_gate
from gpd.core.state import peek_state_json as _peek_state_json
from gpd.core.utils import (
    generate_slug as _generate_slug_impl,
)
from gpd.core.utils import is_phase_complete as _is_phase_complete
from gpd.core.utils import matching_phase_artifact_count as _matching_phase_artifact_count
from gpd.core.utils import phase_normalize as _phase_normalize_impl
from gpd.core.utils import phase_sort_key as _phase_sort_key
from gpd.core.utils import safe_read_file as _safe_read_file
from gpd.core.utils import safe_read_file_truncated as _safe_read_file_truncated
from gpd.core.workflow_staging import (
    ARXIV_SUBMISSION_BOOTSTRAP_FIELDS,
    ARXIV_SUBMISSION_SNAPSHOT_FIELDS,
    PEER_REVIEW_INIT_FIELDS,
    load_arxiv_submission_stage_contract,
)
from gpd.core.workflow_staging import (
    LITERATURE_REVIEW_INIT_FIELDS as _LITERATURE_REVIEW_INIT_FIELDS,
)
from gpd.core.workflow_staging import (
    MAP_RESEARCH_INIT_FIELDS as _MAP_RESEARCH_INIT_FIELDS,
)
from gpd.core.workflow_staging import (
    PLAN_PHASE_CONTRACT_GATE_FIELDS as _PLAN_PHASE_CONTRACT_GATE_FIELDS,
)
from gpd.core.workflow_staging import (
    PLAN_PHASE_FILE_CONTENT_FIELDS as _PLAN_PHASE_FILE_CONTENT_FIELDS,
)
from gpd.core.workflow_staging import (
    PLAN_PHASE_INIT_FIELDS as _PLAN_PHASE_INIT_FIELDS,
)
from gpd.core.workflow_staging import (
    PLAN_PHASE_REFERENCE_RUNTIME_FIELDS as _PLAN_PHASE_REFERENCE_RUNTIME_FIELDS,
)
from gpd.core.workflow_staging import (
    PLAN_PHASE_STATE_MEMORY_FIELDS as _PLAN_PHASE_STATE_MEMORY_FIELDS,
)
from gpd.core.workflow_staging import (
    PLAN_PHASE_STRUCTURED_STATE_FIELDS as _PLAN_PHASE_STRUCTURED_STATE_FIELDS,
)
from gpd.core.workflow_staging import (
    QUICK_CONTRACT_GATE_FIELDS as _QUICK_CONTRACT_GATE_FIELDS,
)
from gpd.core.workflow_staging import (
    QUICK_INIT_FIELDS as _QUICK_INIT_FIELDS,
)
from gpd.core.workflow_staging import (
    QUICK_REFERENCE_RUNTIME_FIELDS as _QUICK_REFERENCE_RUNTIME_FIELDS,
)
from gpd.core.workflow_staging import (
    RESEARCH_PHASE_INIT_FIELDS as _RESEARCH_PHASE_INIT_FIELDS,
)

logger = logging.getLogger(__name__)


# Research file extensions for project detection.
_RESEARCH_EXTENSIONS = frozenset({".tex", ".ipynb", ".py", ".jl", ".f90"})
_LITERATURE_DIR_NAME = "literature"
_LEGACY_RESEARCH_DIR_NAME = "research"
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
_PLAN_PHASE_STAGE_ALLOWED_TOOLS = frozenset(
    {
        "file_read",
        "file_write",
        "shell",
        "find_files",
        "search_files",
        "task",
        "web_fetch",
    }
)
_QUICK_STAGE_ALLOWED_TOOLS = frozenset(
    {
        "ask_user",
        "file_read",
        "file_write",
        "find_files",
        "search_files",
        "shell",
        "task",
    }
)
_RESUME_BASE_INIT_FIELDS = frozenset(
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
        "derived_execution_head",
        "derived_execution_head_resume_file",
        "continuity_handoff_file",
        "recorded_continuity_handoff_file",
        "missing_continuity_handoff_file",
        "has_continuity_handoff",
        "active_resume_kind",
        "active_resume_origin",
        "active_resume_pointer",
        "active_resume_result",
        "resume_candidates",
        "current_hostname",
        "current_platform",
        "session_hostname",
        "session_platform",
        "session_last_date",
        "session_stopped_at",
        "machine_change_detected",
        "machine_change_notice",
        "execution_review_pending",
        "execution_pre_fanout_review_pending",
        "execution_skeptical_requestioning_required",
        "execution_downstream_locked",
        "execution_blocked",
        "execution_resumable",
        "execution_paused_at",
        "current_execution_resume_file",
        "session_resume_file",
        "recorded_session_resume_file",
        "missing_session_resume_file",
        "execution_resume_file",
        "execution_resume_file_source",
        "platform",
    }
)
_RESUME_CONTRACT_GATE_FIELDS = frozenset(
    {
        "project_contract",
        "project_contract_gate",
        "project_contract_load_info",
        "project_contract_validation",
    }
)
_RESUME_REFERENCE_RUNTIME_FIELDS = frozenset(
    {
        "contract_intake",
        "effective_reference_intake",
        "active_reference_context",
        "reference_artifact_files",
        "reference_artifacts_content",
    }
)
_RESUME_STRUCTURED_STATE_FIELDS = frozenset(
    {
        "state_load_source",
        "state_integrity_issues",
        "convention_lock",
        "convention_lock_count",
        "intermediate_results",
        "intermediate_result_count",
        "approximations",
        "approximation_count",
        "propagated_uncertainties",
        "propagated_uncertainty_count",
    }
)
_RESUME_STATE_MEMORY_FIELDS = frozenset(
    {
        "derived_convention_lock",
        "derived_convention_lock_count",
        "derived_intermediate_results",
        "derived_intermediate_result_count",
        "derived_approximations",
        "derived_approximation_count",
    }
)
_RESUME_FILE_CONTENT_FIELDS = frozenset(
    {
        "state_content",
        "project_content",
        "roadmap_content",
        "derivation_state_content",
        "continuity_handoff_content",
    }
)
_SYNC_STATE_BASE_INIT_FIELDS = frozenset(
    {
        "prefer_mode",
        "state_md_exists",
        "state_json_exists",
        "state_json_backup_exists",
        "platform",
    }
)
_SYNC_STATE_FILE_CONTENT_FIELDS = frozenset(
    {
        "state_md_content",
        "state_json_content",
        "state_json_backup_content",
    }
)
_SYNC_STATE_STRUCTURED_STATE_FIELDS = frozenset({"state_load_source", "state_integrity_issues"})
_SYNC_STATE_CONTRACT_GATE_FIELDS = frozenset(
    {
        "project_contract",
        "project_contract_gate",
        "project_contract_load_info",
        "project_contract_validation",
    }
)
_WRITE_PAPER_STAGE_ALLOWED_TOOLS = frozenset(
    {
        "ask_user",
        "file_edit",
        "file_read",
        "file_write",
        "find_files",
        "search_files",
        "shell",
        "task",
        "web_search",
    }
)
_WRITE_PAPER_BASE_INIT_FIELDS = frozenset(
    {
        "commit_docs",
        "state_exists",
        "project_exists",
        "autonomy",
        "research_mode",
        "platform",
    }
)
_WRITE_PAPER_CONTRACT_GATE_FIELDS = frozenset(
    {
        "project_contract",
        "project_contract_gate",
        "project_contract_load_info",
        "project_contract_validation",
    }
)
_WRITE_PAPER_BOOTSTRAP_REFERENCE_FIELDS = frozenset(
    {
        "selected_protocol_bundle_ids",
        "protocol_bundle_context",
        "active_reference_context",
        "derived_manuscript_reference_status",
        "derived_manuscript_reference_status_count",
        "derived_manuscript_proof_review_status",
    }
)
_WRITE_PAPER_REFERENCE_RUNTIME_FIELDS = frozenset(
    {
        *_WRITE_PAPER_BOOTSTRAP_REFERENCE_FIELDS,
        "reference_artifact_files",
        "reference_artifacts_content",
        "literature_review_files",
        "literature_review_count",
        "research_map_reference_files",
        "research_map_reference_count",
        "citation_source_files",
        "citation_source_count",
        "citation_source_warnings",
        "derived_citation_sources",
        "derived_citation_source_count",
    }
)
_WRITE_PAPER_STATE_MEMORY_FIELDS = frozenset(
    {
        "derived_convention_lock",
        "derived_convention_lock_count",
        "derived_intermediate_results",
        "derived_intermediate_result_count",
        "derived_approximations",
        "derived_approximation_count",
    }
)
_WRITE_PAPER_FILE_CONTENT_FIELDS = frozenset(
    {
        "state_content",
        "roadmap_content",
        "requirements_content",
    }
)
_WRITE_PAPER_INIT_FIELDS = frozenset(
    {
        *_WRITE_PAPER_BASE_INIT_FIELDS,
        *_WRITE_PAPER_CONTRACT_GATE_FIELDS,
        *_WRITE_PAPER_REFERENCE_RUNTIME_FIELDS,
        *_WRITE_PAPER_STATE_MEMORY_FIELDS,
        *_WRITE_PAPER_FILE_CONTENT_FIELDS,
    }
)
_PEER_REVIEW_STAGE_ALLOWED_TOOLS = frozenset(
    {
        "ask_user",
        "file_read",
        "file_write",
        "find_files",
        "search_files",
        "shell",
        "task",
        "web_search",
    }
)
_PEER_REVIEW_REFERENCE_RUNTIME_FIELDS = frozenset(
    {
        "project_contract",
        "project_contract_gate",
        "project_contract_load_info",
        "project_contract_validation",
        "contract_intake",
        "effective_reference_intake",
        "selected_protocol_bundle_ids",
        "protocol_bundle_context",
        "active_reference_context",
        "derived_manuscript_reference_status",
        "derived_manuscript_reference_status_count",
        "derived_manuscript_proof_review_status",
        "reference_artifact_files",
        "reference_artifacts_content",
        "literature_review_files",
        "literature_review_count",
        "research_map_reference_files",
        "research_map_reference_count",
        "citation_source_files",
        "citation_source_count",
        "citation_source_warnings",
        "derived_citation_sources",
        "derived_citation_source_count",
    }
)
_PEER_REVIEW_PUBLICATION_RUNTIME_FIELDS = frozenset(
    {
        "manuscript_resolution_status",
        "manuscript_resolution_detail",
        "manuscript_root",
        "manuscript_entrypoint",
        "artifact_manifest_path",
        "bibliography_audit_path",
        "reproducibility_manifest_path",
        "publication_blockers",
        "publication_blocker_count",
        "latest_review_round",
        "latest_review_round_suffix",
        "latest_review_ledger",
        "latest_referee_decision",
        "latest_referee_report_md",
        "latest_referee_report_tex",
        "latest_proof_redteam",
        "latest_review_artifacts",
        "latest_response_round",
        "latest_response_round_suffix",
        "latest_author_response",
        "latest_referee_response",
        "latest_response_artifacts",
    }
)
_NEW_MILESTONE_STAGE_ALLOWED_TOOLS = frozenset(
    {
        "ask_user",
        "file_read",
        "file_write",
        "shell",
        "task",
    }
)
_NEW_MILESTONE_BASE_INIT_FIELDS = frozenset(
    {
        "researcher_model",
        "synthesizer_model",
        "roadmapper_model",
        "commit_docs",
        "autonomy",
        "research_mode",
        "research_enabled",
        "current_milestone",
        "current_milestone_name",
        "project_exists",
        "roadmap_exists",
        "state_exists",
        "platform",
    }
)
_NEW_MILESTONE_CONTRACT_GATE_FIELDS = frozenset(
    {
        "project_contract",
        "project_contract_gate",
        "project_contract_load_info",
        "project_contract_validation",
    }
)
_NEW_MILESTONE_REFERENCE_RUNTIME_FIELDS = frozenset(
    {
        "contract_intake",
        "effective_reference_intake",
        "active_reference_context",
        "reference_artifact_files",
        "reference_artifacts_content",
        "literature_review_files",
        "literature_review_count",
        "research_map_reference_files",
        "research_map_reference_count",
    }
)
_NEW_MILESTONE_STATE_MEMORY_FIELDS = frozenset(
    {
        "derived_convention_lock",
        "derived_convention_lock_count",
        "derived_intermediate_results",
        "derived_intermediate_result_count",
        "derived_approximations",
        "derived_approximation_count",
    }
)
_NEW_MILESTONE_FILE_CONTENT_FIELDS = frozenset(
    {
        "project_content",
        "state_content",
        "milestones_content",
        "requirements_content",
        "roadmap_content",
    }
)
_NEW_MILESTONE_INIT_FIELDS = frozenset(
    {
        *_NEW_MILESTONE_BASE_INIT_FIELDS,
        *_NEW_MILESTONE_CONTRACT_GATE_FIELDS,
        *_NEW_MILESTONE_REFERENCE_RUNTIME_FIELDS,
        *_NEW_MILESTONE_STATE_MEMORY_FIELDS,
        *_NEW_MILESTONE_FILE_CONTENT_FIELDS,
    }
)
_VERIFY_WORK_STAGE_ALLOWED_TOOLS = frozenset(
    {
        "ask_user",
        "file_read",
        "file_edit",
        "file_write",
        "find_files",
        "search_files",
        "shell",
        "task",
    }
)
_VERIFY_WORK_BASE_INIT_FIELDS = frozenset(
    {
        "planner_model",
        "checker_model",
        "verifier_model",
        "commit_docs",
        "autonomy",
        "research_mode",
        "phase_found",
        "phase_dir",
        "phase_number",
        "phase_name",
        "has_verification",
        "has_validation",
        "phase_proof_review_status",
        "platform",
    }
)
_VERIFY_WORK_CONTRACT_GATE_FIELDS = frozenset(
    {
        "project_contract",
        "project_contract_validation",
        "project_contract_load_info",
        "project_contract_gate",
    }
)
_VERIFY_WORK_REFERENCE_RUNTIME_FIELDS = frozenset(
    {
        "contract_intake",
        "effective_reference_intake",
        "derived_active_references",
        "derived_active_reference_count",
        "derived_knowledge_docs",
        "derived_knowledge_doc_count",
        "knowledge_doc_warnings",
        "citation_source_files",
        "citation_source_count",
        "citation_source_warnings",
        "derived_citation_sources",
        "derived_citation_source_count",
        "derived_manuscript_reference_status",
        "derived_manuscript_reference_status_count",
        "derived_manuscript_proof_review_status",
        "active_references",
        "active_reference_count",
        "selected_protocol_bundle_ids",
        "protocol_bundle_count",
        "protocol_bundle_verifier_extensions",
        "protocol_bundle_context",
        "active_reference_context",
        "knowledge_doc_files",
        "knowledge_doc_count",
        "stable_knowledge_doc_files",
        "stable_knowledge_doc_count",
        "knowledge_doc_status_counts",
        "literature_review_files",
        "literature_review_count",
        "research_map_reference_files",
        "research_map_reference_count",
        "reference_artifact_files",
        "reference_artifacts_content",
    }
)
_VERIFY_WORK_STRUCTURED_STATE_FIELDS = frozenset(
    {
        "state_load_source",
        "state_integrity_issues",
        "convention_lock",
        "convention_lock_count",
        "intermediate_results",
        "intermediate_result_count",
        "approximations",
        "approximation_count",
        "propagated_uncertainties",
        "propagated_uncertainty_count",
    }
)
_VERIFY_WORK_STATE_MEMORY_FIELDS = frozenset(
    {
        "derived_convention_lock",
        "derived_convention_lock_count",
        "derived_intermediate_results",
        "derived_intermediate_result_count",
        "derived_approximations",
        "derived_approximation_count",
    }
)
_VERIFY_WORK_INIT_FIELDS = frozenset(
    {
        *_VERIFY_WORK_BASE_INIT_FIELDS,
        *_VERIFY_WORK_CONTRACT_GATE_FIELDS,
        *_VERIFY_WORK_REFERENCE_RUNTIME_FIELDS,
        *_VERIFY_WORK_STRUCTURED_STATE_FIELDS,
        *_VERIFY_WORK_STATE_MEMORY_FIELDS,
    }
)

_EXECUTE_PHASE_STAGE_ALLOWED_TOOLS = frozenset(
    {
        "ask_user",
        "file_edit",
        "file_read",
        "file_write",
        "find_files",
        "search_files",
        "shell",
        "task",
    }
)
_EXECUTE_PHASE_CONTRACT_GATE_FIELDS = frozenset(
    {
        "project_contract",
        "project_contract_gate",
        "project_contract_load_info",
        "project_contract_validation",
    }
)
_EXECUTE_PHASE_REFERENCE_RUNTIME_FIELDS = frozenset(
    {
        "contract_intake",
        "effective_reference_intake",
        "derived_active_references",
        "derived_active_reference_count",
        "derived_knowledge_docs",
        "derived_knowledge_doc_count",
        "knowledge_doc_warnings",
        "citation_source_files",
        "citation_source_count",
        "citation_source_warnings",
        "derived_citation_sources",
        "derived_citation_source_count",
        "derived_manuscript_reference_status",
        "derived_manuscript_reference_status_count",
        "selected_protocol_bundle_ids",
        "protocol_bundle_count",
        "protocol_bundle_verifier_extensions",
        "protocol_bundle_context",
        "active_reference_context",
        "active_references",
        "active_reference_count",
        "knowledge_doc_files",
        "knowledge_doc_count",
        "stable_knowledge_doc_files",
        "stable_knowledge_doc_count",
        "knowledge_doc_status_counts",
        "reference_artifact_files",
        "reference_artifacts_content",
        "literature_review_files",
        "literature_review_count",
        "research_map_reference_files",
        "research_map_reference_count",
        "derived_manuscript_proof_review_status",
    }
)
_EXECUTE_PHASE_STRUCTURED_STATE_FIELDS = frozenset(
    {
        "state_load_source",
        "state_integrity_issues",
        "convention_lock",
        "convention_lock_count",
        "intermediate_results",
        "intermediate_result_count",
        "approximations",
        "approximation_count",
        "propagated_uncertainties",
        "propagated_uncertainty_count",
    }
)
_EXECUTE_PHASE_STATE_MEMORY_FIELDS = frozenset(
    {
        "derived_convention_lock",
        "derived_convention_lock_count",
        "derived_intermediate_results",
        "derived_intermediate_result_count",
        "derived_approximations",
        "derived_approximation_count",
    }
)
_EXECUTE_PHASE_EXECUTION_RUNTIME_FIELDS = frozenset(
    {
        "current_execution",
        "has_live_execution",
        "execution_review_pending",
        "execution_pre_fanout_review_pending",
        "execution_skeptical_requestioning_required",
        "execution_downstream_locked",
        "execution_blocked",
        "execution_resumable",
        "execution_paused_at",
        "current_execution_resume_file",
        "session_resume_file",
        "recorded_session_resume_file",
        "missing_session_resume_file",
        "execution_resume_file",
        "execution_resume_file_source",
        "resume_projection",
        "current_hostname",
        "current_platform",
        "session_hostname",
        "session_platform",
        "session_last_date",
        "session_stopped_at",
        "machine_change_detected",
        "machine_change_notice",
        "derived_execution_head",
        "continuity_handoff_file",
        "recorded_continuity_handoff_file",
        "missing_continuity_handoff_file",
        "has_continuity_handoff",
    }
)
# Directories to skip when scanning for research files.
_LEADING_BLANK_LINES_BEFORE_FRONTMATTER_RE = re.compile(r"^(?:[ \t]*\r?\n)+(?=---[ \t]*\r?\n)")


def _runtime_config_dirs() -> frozenset[str]:
    """Return the live runtime config-dir inventory."""

    return frozenset(descriptor.config_dir_name for descriptor in iter_runtime_descriptors())


def _runtime_ignored_scan_paths() -> frozenset[tuple[str, ...]]:
    """Return runtime-owned path suffixes to skip during research scans."""

    return frozenset((descriptor.config_dir_name,) for descriptor in iter_runtime_descriptors())


def _ignore_dirs() -> frozenset[str]:
    """Return directory names excluded from research-file scans."""

    return frozenset(
        {
            ".git",
            PLANNING_DIR_NAME,
            *_runtime_config_dirs(),
            ".venv",
            ".tox",
            ".pytest_cache",
            ".mypy_cache",
            ".ruff_cache",
            ".vscode",
            ".idea",
            "node_modules",
            "__pycache__",
            GPD_INSTALL_DIR_NAME,
        }
    )


__all__ = [
    "init_arxiv_submission",
    "init_execute_phase",
    "init_literature_review",
    "init_map_research",
    "init_milestone_op",
    "init_peer_review",
    "init_new_milestone",
    "init_new_project",
    "init_phase_op",
    "init_research_phase",
    "init_plan_phase",
    "init_progress",
    "init_quick",
    "init_resume",
    "init_todos",
    "init_verify_work",
    "load_config",
]


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _path_exists(cwd: Path, target: str) -> bool:
    """Check if a relative path exists under cwd."""
    return (cwd / target).exists()


def _state_exists(cwd: Path) -> bool:
    """Return whether the project has recoverable state from JSON or STATE.md."""
    state, _state_issues, _state_source = _peek_state_json(
        cwd,
        recover_intent=False,
        acquire_lock=False,
    )
    return isinstance(state, dict)


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
    state, state_issues, state_source = _peek_state_json(cwd, recover_intent=False)
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
    if resolution is None or not resolution.has_project_layout:
        return None

    project_root = resolution.project_root
    state_exists, roadmap_exists, project_exists = recoverable_project_context(project_root)
    recoverable = state_exists or roadmap_exists or project_exists
    if resolution.walk_up_steps > 0:
        reason = "workspace resolved to ancestor project root"
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
    metadata: dict[str, object] = {
        "workspace_root": resolution.workspace_root,
        "project_root": selected_project_root.as_posix() if selected_project_root is not None else None,
        "project_root_source": resolution.source or "workspace",
        "project_root_auto_selected": resolution.auto_selected,
        "project_reentry_mode": resolution.mode,
        "project_reentry_requires_selection": resolution.requires_user_selection,
        "project_reentry_selected_candidate": (
            resolution.selected_candidate.model_dump(mode="json") if resolution.selected_candidate is not None else None
        ),
        "project_reentry_candidates": [candidate.model_dump(mode="json") for candidate in resolution.candidates],
    }
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


def _normalize_todo_metadata_value(value: object, *, allow_typed_scalars: bool = False) -> str | None:
    """Return a normalized todo metadata value from a todo metadata block."""
    if allow_typed_scalars:
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, date):
            return value.isoformat()
    if not isinstance(value, str):
        return None
    val = value.strip()
    if len(val) >= 2 and val[0] in ('"', "'") and val[-1] == val[0]:
        val = val[1:-1]
    return val or None


def _normalize_todo_frontmatter_text(content: str) -> str:
    """Return a todo text view that preserves valid frontmatter after blank lines."""
    text = content.lstrip("\ufeff")
    return _LEADING_BLANK_LINES_BEFORE_FRONTMATTER_RE.sub("", text, count=1)


def _read_todo_frontmatter(content: str) -> dict[str, object] | None:
    """Read one todo's YAML frontmatter, returning ``None`` when it is malformed."""
    text = _normalize_todo_frontmatter_text(content)
    if not text.startswith("---"):
        return {}

    from gpd.core.frontmatter import FrontmatterParseError, extract_frontmatter

    try:
        meta, body = extract_frontmatter(text)
    except FrontmatterParseError:
        return None
    if body == text and _looks_like_todo_frontmatter_candidate(text):
        return None
    return meta if isinstance(meta, dict) else {}


def _looks_like_todo_frontmatter_candidate(text: str) -> bool:
    """Return whether a leading ``---`` block appears to be attempted metadata."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return False
    for raw_line in lines[1:]:
        stripped = raw_line.strip()
        if not stripped:
            return False
        if stripped == "---":
            return True
        return re.fullmatch(r"[A-Za-z0-9_-]+:[ \t]*(.*)", raw_line) is not None
    return False


def _extract_frontmatter_field(
    content: str,
    field: str,
    *,
    parsed_frontmatter: dict[str, object] | None = None,
) -> str | None:
    """Extract a bare field from the leading todo metadata block only."""
    text = _normalize_todo_frontmatter_text(content)

    if text.startswith("---"):
        meta = parsed_frontmatter if parsed_frontmatter is not None else _read_todo_frontmatter(text)
        if not isinstance(meta, dict):
            return None
        raw_value = meta.get(field)
        return _normalize_todo_metadata_value(raw_value, allow_typed_scalars=field == "created")

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            break
        match = re.fullmatch(r"([A-Za-z0-9_-]+):[ \t]*(.*)", line)
        if not match:
            break
        if match.group(1) != field:
            continue
        return _normalize_todo_metadata_value(match.group(2))

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
    """Return the canonical review directory, falling back to legacy research only when needed."""
    literature_dir = cwd / PLANNING_DIR_NAME / _LITERATURE_DIR_NAME
    if literature_dir.is_dir():
        return literature_dir
    legacy_research_dir = cwd / PLANNING_DIR_NAME / _LEGACY_RESEARCH_DIR_NAME
    if legacy_research_dir.is_dir():
        return legacy_research_dir
    return None


def _relative_posix(cwd: Path, path: Path) -> str:
    """Return a stable repo-relative POSIX path."""
    return path.relative_to(cwd).as_posix()


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


def _should_skip_research_scan_entry(cwd: Path, entry: Path) -> bool:
    """Return whether *entry* should be skipped during research-file discovery."""

    if entry.name in _ignore_dirs():
        return True

    try:
        relative_parts = entry.relative_to(cwd).parts
    except ValueError:
        return False
    for ignored_parts in _runtime_ignored_scan_paths():
        ignored_length = len(ignored_parts)
        if ignored_length == 0 or len(relative_parts) < ignored_length:
            continue
        for offset in range(len(relative_parts) - ignored_length + 1):
            if relative_parts[offset : offset + ignored_length] == ignored_parts:
                return True
    return False


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
    merged = {
        "must_read_refs": [],
        "must_include_prior_outputs": [],
        "user_asserted_anchors": [],
        "known_good_baselines": [],
        "context_gaps": [],
        "crucial_inputs": [],
    }
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


def _reference_artifact_payload(cwd: Path) -> dict[str, object]:
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


def _build_reference_runtime_context(
    cwd: Path,
    *,
    persist_manuscript_proof_review_manifest: bool = False,
) -> dict[str, object]:
    """Build shared reference/anchor context for workflow init payloads."""
    contract, project_contract_load_info = _load_project_contract(cwd)
    artifact_payload = _reference_artifact_payload(cwd)
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
        "protocol_bundle_verifier_extensions": bundle_verifier_extensions,
        "protocol_bundle_context": render_protocol_bundle_context(selected_protocol_bundles),
        "active_reference_context": _render_active_reference_context(
            surfaced_active_references,
            surfaced_effective_reference_intake,
            list(artifact_payload["stable_knowledge_doc_files"]),
            dict(artifact_payload["knowledge_doc_status_counts"]),
            artifact_payload["literature_review_files"],
            artifact_payload["research_map_reference_files"],
            project_contract_validation,
            project_contract_load_info,
        ),
        **artifact_payload,
    }


def _build_new_project_contract_runtime_context(cwd: Path) -> dict[str, object]:
    """Build only the contract/gate payload needed during new-project bootstrap."""
    contract, project_contract_load_info = _load_project_contract(cwd)
    project_contract_load_info, project_contract_validation, project_contract_gate = _finalize_project_contract_gate(
        cwd,
        contract,
        project_contract_load_info,
    )
    return {
        "project_contract": contract.model_dump(mode="json") if project_contract_gate.get("visible") else None,
        "project_contract_validation": project_contract_validation,
        "project_contract_load_info": project_contract_load_info,
        "project_contract_gate": project_contract_gate,
    }


def _build_publication_bootstrap_runtime_context(
    cwd: Path,
    *,
    persist_manuscript_proof_review_manifest: bool = False,
) -> dict[str, object]:
    """Build the lightweight contract/bundle/manuscript-status payload for publication bootstrap."""
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
    manuscript_reference_status = ingest_manuscript_reference_status(cwd)
    manuscript_proof_review_status = resolve_manuscript_proof_review_status(
        cwd,
        persist_manifest=persist_manuscript_proof_review_manifest,
    )
    derived_manuscript_reference_status = {
        record.reference_id: record.to_context_dict() for record in manuscript_reference_status.reference_status
    }
    return {
        "project_contract": visible_context_contract.model_dump(mode="json")
        if visible_context_contract is not None
        else None,
        "project_contract_validation": project_contract_validation,
        "project_contract_load_info": project_contract_load_info,
        "project_contract_gate": project_contract_gate,
        "selected_protocol_bundle_ids": [bundle.bundle_id for bundle in selected_protocol_bundles],
        "protocol_bundle_context": render_protocol_bundle_context(selected_protocol_bundles),
        "active_reference_context": _render_active_reference_context(
            surfaced_active_references,
            surfaced_effective_reference_intake,
            [],
            {},
            [],
            [],
            project_contract_validation,
            project_contract_load_info,
        ),
        "derived_manuscript_reference_status": derived_manuscript_reference_status,
        "derived_manuscript_reference_status_count": len(derived_manuscript_reference_status),
        "derived_manuscript_proof_review_status": manuscript_proof_review_status.to_context_dict(cwd),
    }


def _build_publication_runtime_snapshot_context(
    cwd: Path,
    *,
    persist_manuscript_proof_review_manifest: bool = False,
) -> dict[str, object]:
    """Build the canonical publication snapshot payload used by publication commands."""

    return publication_runtime_snapshot_context(
        cwd,
        persist_manuscript_proof_review_manifest=persist_manuscript_proof_review_manifest,
    )


def _build_peer_review_runtime_context(
    cwd: Path,
    *,
    persist_manuscript_proof_review_manifest: bool = False,
) -> dict[str, object]:
    """Build the shared publication runtime payload for peer-review init and staging."""

    result = dict(
        _build_reference_runtime_context(
            cwd, persist_manuscript_proof_review_manifest=persist_manuscript_proof_review_manifest
        )
    )
    result.update(
        _build_publication_bootstrap_runtime_context(
            cwd, persist_manuscript_proof_review_manifest=persist_manuscript_proof_review_manifest
        )
    )
    result.update(
        _build_publication_runtime_snapshot_context(
            cwd,
            persist_manuscript_proof_review_manifest=persist_manuscript_proof_review_manifest,
        )
    )
    return result


def _build_state_memory_runtime_context(cwd: Path) -> dict[str, object]:
    """Build shared structured state-memory context for init surfaces."""
    state, _state_issues, _state_source = _peek_state_json(cwd, recover_intent=False)
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
    state, state_issues, _state_source = _peek_state_json(cwd, recover_intent=False)
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
    has_active_resume_target = resume_projection.active_resume_source is not None
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
        execution_resume_file_source = "current_execution"
    elif resume_projection.active_resume_source == ContinuationResumeSource.HANDOFF:
        execution_resume_file_source = "session_resume_file"

    paused_states = {"paused", "awaiting_user", "ready_to_continue", "waiting_review", "blocked"}
    segment_status = (snapshot.segment_status or "").lower() if snapshot is not None else ""
    is_resumable = bool(resume_projection.resumable)
    paused_at = (
        snapshot.updated_at
        if snapshot is not None and segment_status in paused_states
        else (position.get("paused_at") if isinstance(position, dict) else None)
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
        "execution_review_pending": bool(
            snapshot
            and (
                snapshot.first_result_gate_pending
                or snapshot.pre_fanout_review_pending
                or snapshot.skeptical_requestioning_required
                or snapshot.waiting_for_review
            )
        ),
        "execution_pre_fanout_review_pending": bool(snapshot and snapshot.pre_fanout_review_pending),
        "execution_skeptical_requestioning_required": bool(snapshot and snapshot.skeptical_requestioning_required),
        "execution_downstream_locked": bool(snapshot and snapshot.downstream_locked),
        "execution_blocked": bool(snapshot and snapshot.blocked_reason),
        "execution_resumable": is_resumable,
        "execution_paused_at": paused_at,
        "current_execution_resume_file": current_execution_resume_file,
        "session_resume_file": resume_projection.handoff_resume_file,
        "recorded_session_resume_file": resume_projection.recorded_handoff_resume_file,
        "missing_session_resume_file": resume_projection.missing_handoff_resume_file,
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
    state, _state_issues, _state_source = _peek_state_json(cwd, recover_intent=False)
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


def _has_candidate(
    segment_candidates: list[dict[str, object]],
    *,
    source: str,
    resume_file: str | None = None,
    agent_id: str | None = None,
) -> bool:
    for candidate in segment_candidates:
        if str(candidate.get("source") or "").strip() != source:
            continue
        if resume_file is not None and candidate.get("resume_file") != resume_file:
            continue
        if agent_id is not None and candidate.get("agent_id") != agent_id:
            continue
        return True
    return False


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
                "source": "session_resume_file",
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
                "source": "session_resume_file",
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

    if interrupted_agent_id is not None and not _has_candidate(
        resume_candidates,
        source="interrupted_agent",
        agent_id=interrupted_agent_id,
    ):
        candidate = {
            "source": "interrupted_agent",
            "status": "interrupted",
            "agent_id": interrupted_agent_id,
        }
        if not _has_resume_candidate(
            resume_candidates,
            kind="interrupted_agent",
            agent_id=interrupted_agent_id,
        ):
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
        "last_result_id": _mapping_text(selected_candidate, "last_result_id"),
        "updated_at": (
            _mapping_text(selected_candidate, "resume_target_recorded_at")
            or _mapping_text(selected_candidate, "source_recorded_at")
        ),
    }
    bounded_segment = {
        key: value for key, value in bounded_segment.items() if not isinstance(value, str) or value.strip()
    }

    raw_candidate = build_resume_segment_candidate(bounded_segment, source="recent_project")
    raw_candidate["resumable"] = True
    canonical_candidate = build_resume_candidate(
        raw_candidate,
        kind="bounded_segment",
        origin=resume_origin_for_bounded_segment(),
        resume_pointer=resume_file,
    )

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
    return promoted, True


# ─── Config Loader ────────────────────────────────────────────────────────────


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


# ─── Resolve Model ────────────────────────────────────────────────────────────

# Concrete model selection is runtime-scoped. When no override is configured
# for the active runtime, callers should omit the runtime model parameter and
# allow the platform to use its default model.


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


# ─── Phase Info Helper ────────────────────────────────────────────────────────


def _try_find_phase(cwd: Path, phase: str) -> dict | None:
    """Attempt to find phase info. Returns a plain dict or None."""
    from gpd.core.phases import find_phase

    result = find_phase(cwd, phase)
    if result is None:
        return None
    return result.model_dump()


def _try_get_milestone_info(cwd: Path) -> dict:
    """Get milestone info from the canonical phases module."""
    from gpd.core.phases import get_milestone_info

    result = get_milestone_info(cwd)
    return result.model_dump()


# ─── Platform Detection ──────────────────────────────────────────────────────


def _detect_platform(cwd: Path | None = None) -> str:
    """Detect the active AI runtime, if any."""
    resolved_cwd = cwd or Path.cwd()
    resolved_home = Path.home()
    runtime_unknown = "unknown"
    try:
        import os

        from gpd.adapters.runtime_catalog import normalize_runtime_name
        from gpd.hooks.runtime_detect import RUNTIME_UNKNOWN, detect_runtime_for_gpd_use

        runtime_unknown = RUNTIME_UNKNOWN
        explicit_override = normalize_runtime_name(os.environ.get(ENV_GPD_ACTIVE_RUNTIME))
        if explicit_override:
            return explicit_override
        for descriptor in iter_runtime_descriptors():
            if any(os.environ.get(env_var) for env_var in descriptor.activation_env_vars):
                return descriptor.runtime_name
        detected = detect_runtime_for_gpd_use(cwd=resolved_cwd, home=resolved_home)
        if isinstance(detected, str) and detected.strip():
            return detected
    except Exception:
        pass

    return runtime_unknown


# ─── Context Assemblers ──────────────────────────────────────────────────────


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
    try:
        stage_def = manifest.stage_by_id(stage)
    except KeyError as exc:
        raise ValueError(
            f"Unknown execute-phase stage {stage!r}. Allowed values: {', '.join(manifest.stage_ids())}."
        ) from exc

    required_fields = set(stage_def.required_init_fields)
    staged_source = dict(result)

    if required_fields & _EXECUTE_PHASE_CONTRACT_GATE_FIELDS:
        staged_source.update(_build_new_project_contract_runtime_context(cwd))

    if required_fields & _EXECUTE_PHASE_REFERENCE_RUNTIME_FIELDS:
        staged_source.update(_build_reference_runtime_context(cwd))

    if required_fields & _EXECUTE_PHASE_STRUCTURED_STATE_FIELDS:
        staged_source.update(_build_structured_state_runtime_context(cwd))

    if required_fields & _EXECUTE_PHASE_STATE_MEMORY_FIELDS:
        staged_source.update(_build_state_memory_runtime_context(cwd))

    if required_fields & _EXECUTE_PHASE_EXECUTION_RUNTIME_FIELDS:
        staged_source.update(_build_execution_runtime_context(cwd))

    missing_fields = [field for field in stage_def.required_init_fields if field not in staged_source]
    if missing_fields:
        raise ValueError(
            f"execute-phase stage {stage!r} requires unavailable init field(s): {', '.join(missing_fields)}"
        )

    staged_payload = {field: staged_source[field] for field in stage_def.required_init_fields}
    staged_payload["staged_loading"] = manifest.staged_loading_payload(stage_def.id)
    return staged_payload


def _build_plan_phase_file_context(
    cwd: Path,
    phase_info: dict[str, object] | None,
    *,
    include_state: bool = False,
    include_roadmap: bool = False,
    include_requirements: bool = False,
    include_context: bool = False,
    include_research: bool = False,
    include_experiment_design: bool = False,
    include_verification: bool = False,
    include_validation: bool = False,
) -> dict[str, object]:
    """Build file-content payloads for plan-phase init surfaces."""
    result: dict[str, object] = {}
    planning = cwd / PLANNING_DIR_NAME

    if include_state:
        result["state_content"] = _safe_read_file_truncated(planning / STATE_MD_FILENAME)
    if include_roadmap:
        result["roadmap_content"] = _safe_read_file_truncated(planning / ROADMAP_FILENAME)
    if include_requirements:
        result["requirements_content"] = _safe_read_file_truncated(planning / REQUIREMENTS_FILENAME)

    if not phase_info or not phase_info.get("directory"):
        return result

    phase_dir = cwd / str(phase_info["directory"])
    if include_context:
        result["context_content"] = _find_phase_artifact(phase_dir, CONTEXT_SUFFIX, STANDALONE_CONTEXT)
    if include_research:
        result["research_content"] = _find_phase_artifact(phase_dir, RESEARCH_SUFFIX, STANDALONE_RESEARCH)
    if include_experiment_design:
        result["experiment_design_content"] = _find_phase_artifact(phase_dir, _EXPERIMENT_DESIGN_SUFFIX)
    if include_verification:
        result["verification_content"] = _find_phase_artifact(phase_dir, VERIFICATION_SUFFIX)
    if include_validation:
        result["validation_content"] = _find_phase_artifact(phase_dir, VALIDATION_SUFFIX, STANDALONE_VALIDATION)
    return result


def _build_publication_file_context(
    cwd: Path,
    *,
    include_state: bool = False,
    include_roadmap: bool = False,
    include_requirements: bool = False,
) -> dict[str, object]:
    """Build planning-file content payloads for publication workflows."""
    result: dict[str, object] = {}
    planning = cwd / PLANNING_DIR_NAME
    if include_state:
        result["state_content"] = _safe_read_file_truncated(planning / STATE_MD_FILENAME)
    if include_roadmap:
        result["roadmap_content"] = _safe_read_file_truncated(planning / ROADMAP_FILENAME)
    if include_requirements:
        result["requirements_content"] = _safe_read_file_truncated(planning / REQUIREMENTS_FILENAME)
    return result


def _build_new_milestone_file_context(
    cwd: Path,
    *,
    include_project: bool = False,
    include_state: bool = False,
    include_milestones: bool = False,
    include_requirements: bool = False,
    include_roadmap: bool = False,
) -> dict[str, object]:
    """Build planning-file content payloads for new-milestone init surfaces."""
    result: dict[str, object] = {}
    planning = cwd / PLANNING_DIR_NAME

    if include_project:
        result["project_content"] = _safe_read_file_truncated(planning / PROJECT_FILENAME)
    if include_state:
        result["state_content"] = _safe_read_file_truncated(planning / STATE_MD_FILENAME)
    if include_milestones:
        result["milestones_content"] = _safe_read_file_truncated(planning / MILESTONES_FILENAME)
    if include_requirements:
        result["requirements_content"] = _safe_read_file_truncated(planning / REQUIREMENTS_FILENAME)
    if include_roadmap:
        result["roadmap_content"] = _safe_read_file_truncated(planning / ROADMAP_FILENAME)
    return result


def _build_resume_file_context(
    cwd: Path,
    *,
    continuity_handoff_file: str | None = None,
    include_state: bool = False,
    include_project: bool = False,
    include_roadmap: bool = False,
    include_derivation_state: bool = False,
    include_continuity_handoff: bool = False,
) -> dict[str, object]:
    """Build file-content payloads for resume-work init surfaces."""
    result: dict[str, object] = {}
    planning = cwd / PLANNING_DIR_NAME

    if include_state:
        result["state_content"] = _safe_read_file_truncated(planning / STATE_MD_FILENAME)
    if include_project:
        result["project_content"] = _safe_read_file_truncated(planning / PROJECT_FILENAME)
    if include_roadmap:
        result["roadmap_content"] = _safe_read_file_truncated(planning / ROADMAP_FILENAME)
    if include_derivation_state:
        result["derivation_state_content"] = _safe_read_file_truncated(planning / "DERIVATION-STATE.md")

    if include_continuity_handoff:
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


def _build_sync_state_file_context(
    cwd: Path,
    *,
    include_state_md: bool = False,
    include_state_json: bool = False,
    include_state_json_backup: bool = False,
) -> dict[str, object]:
    """Build file-content payloads for sync-state init surfaces."""
    result: dict[str, object] = {}
    planning = cwd / PLANNING_DIR_NAME

    if include_state_md:
        result["state_md_content"] = _safe_read_file_truncated(planning / STATE_MD_FILENAME)
    if include_state_json:
        result["state_json_content"] = _safe_read_file_truncated(planning / "state.json")
    if include_state_json_backup:
        result["state_json_backup_content"] = _safe_read_file_truncated(planning / STATE_JSON_BACKUP_FILENAME)

    return result


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
    if not phase:
        raise ValidationError(
            "phase is required for init plan-phase. Provide a phase identifier such as '1', '03', or '3.1'."
        )

    includes = includes or set()
    if stage is not None and includes:
        raise ValueError(
            "gpd init plan-phase does not allow --include together with --stage; "
            "stage payloads already declare their required context."
        )
    config = load_config(cwd)
    phase_info = _try_find_phase(cwd, phase)

    result: dict[str, object] = {
        # Models
        "researcher_model": _resolve_model(cwd, "gpd-phase-researcher", config),
        "planner_model": _resolve_model(cwd, "gpd-planner", config),
        "checker_model": _resolve_model(cwd, "gpd-plan-checker", config),
        # Workflow flags
        "research_enabled": config["research"],
        "plan_checker_enabled": config["plan_checker"],
        "commit_docs": config["commit_docs"],
        "autonomy": config["autonomy"],
        "research_mode": config["research_mode"],
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
        "plan_count": len(phase_info.get("plans", [])) if phase_info else 0,
        # Environment
        "planning_exists": _path_exists(cwd, PLANNING_DIR_NAME),
        "roadmap_exists": _path_exists(cwd, f"{PLANNING_DIR_NAME}/{ROADMAP_FILENAME}"),
        # Platform
        "platform": _detect_platform(cwd),
    }
    if stage is None:
        result.update(_build_reference_runtime_context(cwd))
        result.update(_build_state_memory_runtime_context(cwd))
        result.update(
            _build_plan_phase_file_context(
                cwd,
                phase_info,
                include_state="state" in includes,
                include_roadmap="roadmap" in includes,
                include_requirements="requirements" in includes,
                include_context="context" in includes,
                include_research="research" in includes,
                include_experiment_design=False,
                include_verification="verification" in includes,
                include_validation="validation" in includes,
            )
        )
        if "state" in includes:
            result.update(_build_structured_state_runtime_context(cwd))
        return result

    from gpd.core.workflow_staging import load_workflow_stage_manifest

    manifest = load_workflow_stage_manifest(
        "plan-phase",
        allowed_tools=_PLAN_PHASE_STAGE_ALLOWED_TOOLS,
        known_init_fields=_PLAN_PHASE_INIT_FIELDS,
    )
    try:
        stage_def = manifest.stage_by_id(stage)
    except KeyError as exc:
        raise ValueError(
            f"Unknown plan-phase stage {stage!r}. Allowed values: {', '.join(manifest.stage_ids())}."
        ) from exc

    required_fields = set(stage_def.required_init_fields)
    staged_source = dict(result)
    needs_full_reference_context = bool(required_fields & _PLAN_PHASE_REFERENCE_RUNTIME_FIELDS)
    needs_contract_gate_context = bool(required_fields & _PLAN_PHASE_CONTRACT_GATE_FIELDS)

    if needs_full_reference_context:
        staged_source.update(_build_reference_runtime_context(cwd))
    elif needs_contract_gate_context:
        staged_source.update(_build_new_project_contract_runtime_context(cwd))

    if required_fields & _PLAN_PHASE_STATE_MEMORY_FIELDS:
        staged_source.update(_build_state_memory_runtime_context(cwd))

    if required_fields & _PLAN_PHASE_STRUCTURED_STATE_FIELDS:
        staged_source.update(_build_structured_state_runtime_context(cwd))

    if required_fields & _PLAN_PHASE_FILE_CONTENT_FIELDS:
        staged_source.update(
            _build_plan_phase_file_context(
                cwd,
                phase_info,
                include_state="state_content" in required_fields,
                include_roadmap="roadmap_content" in required_fields,
                include_requirements="requirements_content" in required_fields,
                include_context="context_content" in required_fields,
                include_research="research_content" in required_fields,
                include_experiment_design="experiment_design_content" in required_fields,
                include_verification="verification_content" in required_fields,
                include_validation="validation_content" in required_fields,
            )
        )

    missing_fields = [field for field in stage_def.required_init_fields if field not in staged_source]
    if missing_fields:
        raise ValueError(f"plan-phase stage {stage!r} requires unavailable init field(s): {', '.join(missing_fields)}")

    staged_payload = {field: staged_source[field] for field in stage_def.required_init_fields}
    staged_payload["staged_loading"] = manifest.staged_loading_payload(stage_def.id)
    return staged_payload


def init_new_project(cwd: Path, stage: str | None = None) -> dict:
    """Assemble context for new project creation."""
    config = load_config(cwd)

    # Detect existing research files (walk up to depth 3, max 5 files)
    has_research_files = False
    found_count = 0

    def _walk(directory: Path, depth: int) -> None:
        nonlocal has_research_files, found_count
        if depth > 3 or found_count >= 5:
            return
        try:
            entries = sorted(directory.iterdir())
        except (PermissionError, FileNotFoundError):
            return
        for entry in entries:
            if found_count >= 5:
                return
            if _should_skip_research_scan_entry(cwd, entry):
                continue
            if entry.is_dir():
                _walk(entry, depth + 1)
            elif entry.is_file() and entry.suffix in _RESEARCH_EXTENSIONS:
                found_count += 1
                has_research_files = True

    _walk(cwd, 0)

    has_project_manifest = (
        _path_exists(cwd, "requirements.txt")
        or _path_exists(cwd, "pyproject.toml")
        or _path_exists(cwd, "Makefile")
        or resolve_current_manuscript_entrypoint(cwd) is not None
    )

    result = {
        # Models
        "researcher_model": _resolve_model(cwd, "gpd-project-researcher", config),
        "synthesizer_model": _resolve_model(cwd, "gpd-research-synthesizer", config),
        "roadmapper_model": _resolve_model(cwd, "gpd-roadmapper", config),
        # Config
        "commit_docs": config["commit_docs"],
        "autonomy": config["autonomy"],
        "research_mode": config["research_mode"],
        # Existing state
        "project_exists": _path_exists(cwd, f"{PLANNING_DIR_NAME}/{PROJECT_FILENAME}"),
        "has_research_map": _path_exists(cwd, f"{PLANNING_DIR_NAME}/{RESEARCH_MAP_DIR_NAME}"),
        "planning_exists": _path_exists(cwd, PLANNING_DIR_NAME),
        # Existing project detection
        "has_research_files": has_research_files,
        "has_project_manifest": has_project_manifest,
        "needs_research_map": (has_research_files or has_project_manifest)
        and not _path_exists(cwd, f"{PLANNING_DIR_NAME}/{RESEARCH_MAP_DIR_NAME}"),
        # Git state
        "has_git": _path_exists(cwd, ".git"),
        # Bootstrap only needs the scoping contract gate, not the full reference ledger.
        **_build_new_project_contract_runtime_context(cwd),
        # Platform
        "platform": _detect_platform(cwd),
    }

    if stage is None:
        return result

    from gpd.core.workflow_staging import load_workflow_stage_manifest

    manifest = load_workflow_stage_manifest(
        "new-project",
        allowed_tools={"ask_user", "file_read", "file_write", "shell", "task"},
        known_init_fields=set(result),
    )
    try:
        stage_def = manifest.stage_by_id(stage)
    except KeyError as exc:
        raise ValueError(
            f"Unknown new-project stage {stage!r}. Allowed values: {', '.join(manifest.stage_ids())}."
        ) from exc

    missing_fields = [field for field in stage_def.required_init_fields if field not in result]
    if missing_fields:
        raise ValueError(f"new-project stage {stage!r} requires unavailable init field(s): {', '.join(missing_fields)}")

    staged_payload = {field: result[field] for field in stage_def.required_init_fields}
    staged_payload["staged_loading"] = manifest.staged_loading_payload(stage_def.id)
    return staged_payload


def init_new_milestone(cwd: Path, stage: str | None = None) -> dict:
    """Assemble context for new milestone creation."""
    config = load_config(cwd)
    milestone = _try_get_milestone_info(cwd)
    base_result = {
        # Config
        "commit_docs": config["commit_docs"],
        "autonomy": config["autonomy"],
        "research_mode": config["research_mode"],
        "research_enabled": config["research"],
        # Current milestone
        "current_milestone": milestone["version"],
        "current_milestone_name": milestone["name"],
        # File existence
        "project_exists": _path_exists(cwd, f"{PLANNING_DIR_NAME}/{PROJECT_FILENAME}"),
        "roadmap_exists": _path_exists(cwd, f"{PLANNING_DIR_NAME}/{ROADMAP_FILENAME}"),
        "state_exists": _state_exists(cwd),
        # Platform
        "platform": _detect_platform(cwd),
    }

    if stage is None:
        result = dict(base_result)
        result.update(
            {
                # Models
                "researcher_model": _resolve_model(cwd, "gpd-project-researcher", config),
                "synthesizer_model": _resolve_model(cwd, "gpd-research-synthesizer", config),
                "roadmapper_model": _resolve_model(cwd, "gpd-roadmapper", config),
            }
        )
        result.update(_build_reference_runtime_context(cwd))
        result.update(_build_state_memory_runtime_context(cwd))
        return result

    from gpd.core.workflow_staging import load_workflow_stage_manifest

    manifest = load_workflow_stage_manifest(
        "new-milestone",
        allowed_tools=_NEW_MILESTONE_STAGE_ALLOWED_TOOLS,
        known_init_fields=_NEW_MILESTONE_INIT_FIELDS,
    )
    try:
        stage_def = manifest.stage_by_id(stage)
    except KeyError as exc:
        raise ValueError(
            f"Unknown new-milestone stage {stage!r}. Allowed values: {', '.join(manifest.stage_ids())}."
        ) from exc

    required_fields = set(stage_def.required_init_fields)
    staged_source = dict(base_result)
    staged_source["researcher_model"] = _resolve_model(cwd, "gpd-project-researcher", config)
    if "synthesizer_model" in required_fields:
        staged_source["synthesizer_model"] = _resolve_model(cwd, "gpd-research-synthesizer", config)
    if "roadmapper_model" in required_fields:
        staged_source["roadmapper_model"] = _resolve_model(cwd, "gpd-roadmapper", config)

    needs_full_reference_context = bool(required_fields & _NEW_MILESTONE_REFERENCE_RUNTIME_FIELDS)
    needs_contract_gate_context = bool(required_fields & _NEW_MILESTONE_CONTRACT_GATE_FIELDS)

    if needs_full_reference_context:
        staged_source.update(_build_reference_runtime_context(cwd))
    elif needs_contract_gate_context:
        staged_source.update(_build_new_project_contract_runtime_context(cwd))

    if required_fields & _NEW_MILESTONE_STATE_MEMORY_FIELDS:
        staged_source.update(_build_state_memory_runtime_context(cwd))

    if required_fields & _NEW_MILESTONE_FILE_CONTENT_FIELDS:
        staged_source.update(
            _build_new_milestone_file_context(
                cwd,
                include_project="project_content" in required_fields,
                include_state="state_content" in required_fields,
                include_milestones="milestones_content" in required_fields,
                include_requirements="requirements_content" in required_fields,
                include_roadmap="roadmap_content" in required_fields,
            )
        )

    missing_fields = [field for field in stage_def.required_init_fields if field not in staged_source]
    if missing_fields:
        raise ValueError(
            f"new-milestone stage {stage!r} requires unavailable init field(s): {', '.join(missing_fields)}"
        )

    staged_payload = {field: staged_source[field] for field in stage_def.required_init_fields}
    staged_payload["staged_loading"] = manifest.staged_loading_payload(stage_def.id)
    return staged_payload


def init_quick(cwd: Path, description: str | None = None, stage: str | None = None) -> dict:
    """Assemble context for quick task execution."""
    config = load_config(cwd)
    now = datetime.now(UTC)
    normalized_description = description.strip() if isinstance(description, str) else description
    slug = _generate_slug(normalized_description)
    if normalized_description and slug is None:
        slug = "task"
    if slug:
        slug = slug[:40]

    # Find next quick task number
    quick_dir = cwd / PLANNING_DIR_NAME / "quick"
    next_num = 1
    try:
        existing = []
        for entry in quick_dir.iterdir():
            match = re.match(r"^(\d+)-", entry.name)
            if match:
                existing.append(int(match.group(1)))
        if existing:
            next_num = max(existing) + 1
    except (FileNotFoundError, PermissionError):
        pass

    result = {
        # Models
        "planner_model": _resolve_model(cwd, "gpd-planner", config),
        "executor_model": _resolve_model(cwd, "gpd-executor", config),
        # Config
        "commit_docs": config["commit_docs"],
        "autonomy": config["autonomy"],
        "research_mode": config["research_mode"],
        # Quick task info
        "next_num": next_num,
        "slug": slug,
        "description": normalized_description,
        # Timestamps
        "date": now.strftime("%Y-%m-%d"),
        "timestamp": now.isoformat(),
        # Paths
        "quick_dir": f"{PLANNING_DIR_NAME}/quick",
        "task_dir": f"{PLANNING_DIR_NAME}/quick/{next_num}-{slug}" if slug else None,
        # File existence
        "roadmap_exists": _path_exists(cwd, f"{PLANNING_DIR_NAME}/{ROADMAP_FILENAME}"),
        "project_exists": _path_exists(cwd, f"{PLANNING_DIR_NAME}/{PROJECT_FILENAME}"),
        "planning_exists": _path_exists(cwd, PLANNING_DIR_NAME),
        # Platform
        "platform": _detect_platform(cwd),
    }

    if stage is None:
        result.update(_build_reference_runtime_context(cwd))
        result.update(_build_state_memory_runtime_context(cwd))
        return result

    from gpd.core.workflow_staging import load_workflow_stage_manifest

    manifest = load_workflow_stage_manifest(
        "quick",
        allowed_tools=_QUICK_STAGE_ALLOWED_TOOLS,
        known_init_fields=_QUICK_INIT_FIELDS,
    )
    try:
        stage_def = manifest.stage_by_id(stage)
    except KeyError as exc:
        raise ValueError(f"Unknown quick stage {stage!r}. Allowed values: {', '.join(manifest.stage_ids())}.") from exc

    required_fields = set(stage_def.required_init_fields)
    staged_source = dict(result)

    if required_fields & _QUICK_REFERENCE_RUNTIME_FIELDS:
        staged_source.update(_build_reference_runtime_context(cwd))
    elif required_fields & _QUICK_CONTRACT_GATE_FIELDS:
        staged_source.update(_build_new_project_contract_runtime_context(cwd))

    missing_fields = [field for field in stage_def.required_init_fields if field not in staged_source]
    if missing_fields:
        raise ValueError(f"quick stage {stage!r} requires unavailable init field(s): {', '.join(missing_fields)}")

    staged_payload = {field: staged_source[field] for field in stage_def.required_init_fields}
    staged_payload["staged_loading"] = manifest.staged_loading_payload(stage_def.id)
    return staged_payload


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
    execution_public = {
        key: value
        for key, value in execution_context.items()
        if key != "resume_projection" and key not in RESUME_COMPATIBILITY_ALIAS_FIELDS
    }
    base_result.update(execution_public)
    if recent_bounded_segment_promoted and not bool(base_result.get("execution_resumable")):
        base_result["execution_resumable"] = True

    if stage is None:
        result = dict(base_result)
        result.update(_build_reference_runtime_context(effective_cwd))
        return canonicalize_resume_public_payload(result)

    from gpd.core.workflow_staging import load_workflow_stage_manifest

    manifest = load_workflow_stage_manifest(
        "resume-work",
        allowed_tools={"ask_user", "file_read", "file_write", "shell"},
    )
    try:
        stage_def = manifest.stage_by_id(stage)
    except KeyError as exc:
        raise ValueError(
            f"Unknown resume-work stage {stage!r}. Allowed values: {', '.join(manifest.stage_ids())}."
        ) from exc

    required_fields = set(stage_def.required_init_fields)
    staged_source = dict(base_result)
    needs_full_reference_context = bool(required_fields & _RESUME_REFERENCE_RUNTIME_FIELDS)
    needs_contract_gate_context = bool(required_fields & _RESUME_CONTRACT_GATE_FIELDS)

    if needs_full_reference_context:
        staged_source.update(_build_reference_runtime_context(effective_cwd))
    elif needs_contract_gate_context:
        staged_source.update(_build_new_project_contract_runtime_context(effective_cwd))

    if required_fields & _RESUME_STRUCTURED_STATE_FIELDS:
        staged_source.update(_build_structured_state_runtime_context(effective_cwd))

    if required_fields & _RESUME_STATE_MEMORY_FIELDS:
        staged_source.update(_build_state_memory_runtime_context(effective_cwd))

    if required_fields & _RESUME_FILE_CONTENT_FIELDS:
        staged_source.update(
            _build_resume_file_context(
                effective_cwd,
                continuity_handoff_file=continuity_handoff_file,
                include_state="state_content" in required_fields,
                include_project="project_content" in required_fields,
                include_roadmap="roadmap_content" in required_fields,
                include_derivation_state="derivation_state_content" in required_fields,
                include_continuity_handoff="continuity_handoff_content" in required_fields,
            )
        )

    staged_source = canonicalize_resume_public_payload(staged_source)
    missing_fields = [field for field in stage_def.required_init_fields if field not in staged_source]
    if missing_fields:
        raise ValueError(f"resume-work stage {stage!r} requires unavailable init field(s): {', '.join(missing_fields)}")

    staged_payload = {field: staged_source[field] for field in stage_def.required_init_fields}
    staged_payload["staged_loading"] = manifest.staged_loading_payload(stage_def.id)
    return staged_payload


def init_sync_state(cwd: Path, *, prefer_mode: str | None = None, stage: str | None = None) -> dict:
    """Assemble context for state reconciliation."""
    normalized_prefer = prefer_mode.strip() if isinstance(prefer_mode, str) and prefer_mode.strip() else None
    if normalized_prefer not in {None, "md", "json"}:
        raise ValueError("sync-state prefer mode must be one of: md, json")

    base_result = {
        "prefer_mode": normalized_prefer,
        "state_md_exists": _path_exists(cwd, f"{PLANNING_DIR_NAME}/{STATE_MD_FILENAME}"),
        "state_json_exists": _path_exists(cwd, f"{PLANNING_DIR_NAME}/state.json"),
        "state_json_backup_exists": _path_exists(cwd, f"{PLANNING_DIR_NAME}/{STATE_JSON_BACKUP_FILENAME}"),
        "platform": _detect_platform(cwd),
    }

    if stage is None:
        result = dict(base_result)
        result.update(_build_structured_state_runtime_context(cwd))
        result.update(_build_new_project_contract_runtime_context(cwd))
        result.update(
            _build_sync_state_file_context(
                cwd,
                include_state_md=True,
                include_state_json=True,
                include_state_json_backup=True,
            )
        )
        return result

    from gpd.core.workflow_staging import load_workflow_stage_manifest

    manifest = load_workflow_stage_manifest(
        "sync-state",
        allowed_tools={"ask_user", "file_read", "file_write", "shell", "find_files", "search_files"},
    )
    try:
        stage_def = manifest.stage_by_id(stage)
    except KeyError as exc:
        raise ValueError(
            f"Unknown sync-state stage {stage!r}. Allowed values: {', '.join(manifest.stage_ids())}."
        ) from exc

    required_fields = set(stage_def.required_init_fields)
    staged_source = dict(base_result)

    if required_fields & _SYNC_STATE_STRUCTURED_STATE_FIELDS:
        staged_source.update(_build_structured_state_runtime_context(cwd))

    if required_fields & _SYNC_STATE_CONTRACT_GATE_FIELDS:
        staged_source.update(_build_new_project_contract_runtime_context(cwd))

    if required_fields & _SYNC_STATE_FILE_CONTENT_FIELDS:
        staged_source.update(
            _build_sync_state_file_context(
                cwd,
                include_state_md="state_md_content" in required_fields,
                include_state_json="state_json_content" in required_fields,
                include_state_json_backup="state_json_backup_content" in required_fields,
            )
        )

    missing_fields = [field for field in stage_def.required_init_fields if field not in staged_source]
    if missing_fields:
        raise ValueError(f"sync-state stage {stage!r} requires unavailable init field(s): {', '.join(missing_fields)}")

    staged_payload = {field: staged_source[field] for field in stage_def.required_init_fields}
    staged_payload["staged_loading"] = manifest.staged_loading_payload(stage_def.id)
    return staged_payload


def init_verify_work(cwd: Path, phase: str | None, stage: str | None = None) -> dict:
    """Assemble context for work verification."""
    if not phase:
        raise ValidationError(
            "phase is required for init verify-work. Provide a phase identifier such as '1', '03', or '3.1'."
        )

    config = load_config(cwd)
    phase_info = _try_find_phase(cwd, phase)
    phase_proof_review_status = resolve_phase_proof_review_status(
        cwd,
        cwd / phase_info["directory"] if phase_info else None,
        persist_manifest=True,
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
        # Phase info
        "phase_found": phase_info is not None,
        "phase_dir": phase_info["directory"] if phase_info else None,
        "phase_number": phase_info["phase_number"] if phase_info else None,
        "phase_name": phase_info.get("phase_name") if phase_info else None,
        # Existing artifacts
        "has_verification": phase_info.get("has_verification", False) if phase_info else False,
        "has_validation": phase_info.get("has_validation", False) if phase_info else False,
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

    manifest = load_workflow_stage_manifest(
        "verify-work",
        allowed_tools=_VERIFY_WORK_STAGE_ALLOWED_TOOLS,
        known_init_fields=_VERIFY_WORK_INIT_FIELDS,
    )
    try:
        stage_def = manifest.stage_by_id(stage)
    except KeyError as exc:
        raise ValueError(
            f"Unknown verify-work stage {stage!r}. Allowed values: {', '.join(manifest.stage_ids())}."
        ) from exc

    required_fields = set(stage_def.required_init_fields)
    staged_source = dict(base_result)
    needs_full_reference_context = bool(required_fields & _VERIFY_WORK_REFERENCE_RUNTIME_FIELDS)
    needs_contract_gate_context = bool(required_fields & _VERIFY_WORK_CONTRACT_GATE_FIELDS)

    if needs_full_reference_context:
        staged_source.update(_build_reference_runtime_context(cwd))
    elif needs_contract_gate_context:
        staged_source.update(_build_new_project_contract_runtime_context(cwd))

    if required_fields & _VERIFY_WORK_STRUCTURED_STATE_FIELDS:
        staged_source.update(_build_structured_state_runtime_context(cwd))

    if required_fields & _VERIFY_WORK_STATE_MEMORY_FIELDS:
        staged_source.update(_build_state_memory_runtime_context(cwd))

    missing_fields = [field for field in stage_def.required_init_fields if field not in staged_source]
    if missing_fields:
        raise ValueError(f"verify-work stage {stage!r} requires unavailable init field(s): {', '.join(missing_fields)}")

    staged_payload = {field: staged_source[field] for field in stage_def.required_init_fields}
    staged_payload["staged_loading"] = manifest.staged_loading_payload(stage_def.id)
    return staged_payload


def init_write_paper(cwd: Path, stage: str | None = None) -> dict:
    """Assemble context for manuscript authoring and publication review."""
    config = load_config(cwd)
    base_result: dict[str, object] = {
        "commit_docs": config["commit_docs"],
        "state_exists": _state_exists(cwd),
        "project_exists": _path_exists(cwd, f"{PLANNING_DIR_NAME}/{PROJECT_FILENAME}"),
        "autonomy": config["autonomy"],
        "research_mode": config["research_mode"],
        "platform": _detect_platform(cwd),
    }
    if stage is None:
        result = dict(base_result)
        result.update(_build_publication_bootstrap_runtime_context(cwd))
        result.update(_build_publication_runtime_snapshot_context(cwd))
        return result

    from gpd.core.workflow_staging import load_workflow_stage_manifest

    manifest = load_workflow_stage_manifest(
        "write-paper",
        allowed_tools=_WRITE_PAPER_STAGE_ALLOWED_TOOLS,
        known_init_fields=_WRITE_PAPER_INIT_FIELDS,
    )
    try:
        stage_def = manifest.stage_by_id(stage)
    except KeyError as exc:
        raise ValueError(
            f"Unknown write-paper stage {stage!r}. Allowed values: {', '.join(manifest.stage_ids())}."
        ) from exc

    required_fields = set(stage_def.required_init_fields)
    staged_source = dict(base_result)
    needs_full_reference_context = bool(required_fields & _WRITE_PAPER_REFERENCE_RUNTIME_FIELDS)
    needs_bootstrap_reference_context = bool(required_fields & _WRITE_PAPER_BOOTSTRAP_REFERENCE_FIELDS)
    needs_contract_gate_context = bool(required_fields & _WRITE_PAPER_CONTRACT_GATE_FIELDS)

    if needs_full_reference_context:
        staged_source.update(_build_reference_runtime_context(cwd))
    elif needs_bootstrap_reference_context or needs_contract_gate_context:
        staged_source.update(_build_publication_bootstrap_runtime_context(cwd))

    if required_fields & _WRITE_PAPER_STATE_MEMORY_FIELDS:
        staged_source.update(_build_state_memory_runtime_context(cwd))

    if required_fields & _WRITE_PAPER_FILE_CONTENT_FIELDS:
        staged_source.update(
            _build_publication_file_context(
                cwd,
                include_state="state_content" in required_fields,
                include_roadmap="roadmap_content" in required_fields,
                include_requirements="requirements_content" in required_fields,
            )
        )

    missing_fields = [field for field in stage_def.required_init_fields if field not in staged_source]
    if missing_fields:
        raise ValueError(f"write-paper stage {stage!r} requires unavailable init field(s): {', '.join(missing_fields)}")

    staged_payload = {field: staged_source[field] for field in stage_def.required_init_fields}
    staged_payload["staged_loading"] = manifest.staged_loading_payload(stage_def.id)
    return staged_payload


def init_peer_review(cwd: Path, stage: str | None = None) -> dict:
    """Assemble context for staged manuscript peer review."""
    config = load_config(cwd)
    base_result: dict[str, object] = {
        "commit_docs": config["commit_docs"],
        "state_exists": _state_exists(cwd),
        "project_exists": _path_exists(cwd, f"{PLANNING_DIR_NAME}/{PROJECT_FILENAME}"),
        "autonomy": config["autonomy"],
        "research_mode": config["research_mode"],
        "platform": _detect_platform(cwd),
    }
    if stage is None:
        result = dict(base_result)
        result.update(_build_reference_runtime_context(cwd))
        result.update(_build_publication_bootstrap_runtime_context(cwd))
        result.update(_build_publication_runtime_snapshot_context(cwd))
        return result

    from gpd.core.workflow_staging import load_workflow_stage_manifest

    manifest = load_workflow_stage_manifest(
        "peer-review",
        allowed_tools=_PEER_REVIEW_STAGE_ALLOWED_TOOLS,
        known_init_fields=PEER_REVIEW_INIT_FIELDS,
    )
    try:
        stage_def = manifest.stage_by_id(stage)
    except KeyError as exc:
        raise ValueError(
            f"Unknown peer-review stage {stage!r}. Allowed values: {', '.join(manifest.stage_ids())}."
        ) from exc

    required_fields = set(stage_def.required_init_fields)
    staged_source = dict(base_result)
    if required_fields & _PEER_REVIEW_REFERENCE_RUNTIME_FIELDS:
        staged_source.update(_build_reference_runtime_context(cwd))
    if required_fields & _PEER_REVIEW_PUBLICATION_RUNTIME_FIELDS:
        staged_source.update(_build_publication_runtime_snapshot_context(cwd))

    missing_fields = [field for field in stage_def.required_init_fields if field not in staged_source]
    if missing_fields:
        raise ValueError(f"peer-review stage {stage!r} requires unavailable init field(s): {', '.join(missing_fields)}")

    staged_payload = {field: staged_source[field] for field in stage_def.required_init_fields}
    staged_payload["staged_loading"] = manifest.staged_loading_payload(stage_def.id)
    return staged_payload


def init_arxiv_submission(cwd: Path, stage: str | None = None) -> dict:
    """Assemble context for arXiv submission packaging."""
    config = load_config(cwd)
    base_result: dict[str, object] = {
        "commit_docs": config["commit_docs"],
        "state_exists": _state_exists(cwd),
        "project_exists": _path_exists(cwd, f"{PLANNING_DIR_NAME}/{PROJECT_FILENAME}"),
        "autonomy": config["autonomy"],
        "research_mode": config["research_mode"],
        "platform": _detect_platform(cwd),
    }
    if stage is None:
        result = dict(base_result)
        result.update(_build_publication_bootstrap_runtime_context(cwd))
        result.update(_build_publication_runtime_snapshot_context(cwd))
        return result

    manifest = load_arxiv_submission_stage_contract()
    try:
        stage_def = manifest.stage_by_id(stage)
    except KeyError as exc:
        raise ValueError(
            f"Unknown arxiv-submission stage {stage!r}. Allowed values: {', '.join(manifest.stage_ids())}."
        ) from exc

    required_fields = set(stage_def.required_init_fields)
    staged_source = dict(base_result)

    if required_fields & ARXIV_SUBMISSION_BOOTSTRAP_FIELDS:
        staged_source.update(_build_publication_bootstrap_runtime_context(cwd))
    if required_fields & ARXIV_SUBMISSION_SNAPSHOT_FIELDS:
        staged_source.update(_build_publication_runtime_snapshot_context(cwd))

    missing_fields = [field for field in stage_def.required_init_fields if field not in staged_source]
    if missing_fields:
        raise ValueError(
            f"arxiv-submission stage {stage!r} requires unavailable init field(s): {', '.join(missing_fields)}"
        )

    staged_payload = {field: staged_source[field] for field in stage_def.required_init_fields}
    staged_payload["staged_loading"] = manifest.staged_loading_payload(stage_def.id)
    return staged_payload


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
    config = load_config(cwd)
    phase_info = _try_find_phase(cwd, phase) if phase else None

    result: dict[str, object] = {
        # Models
        "executor_model": _resolve_model(cwd, "gpd-executor", config),
        "verifier_model": _resolve_model(cwd, "gpd-verifier", config),
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
        "roadmap_exists": _path_exists(cwd, f"{PLANNING_DIR_NAME}/{ROADMAP_FILENAME}"),
        "state_exists": _state_exists(cwd),
        "planning_exists": _path_exists(cwd, PLANNING_DIR_NAME),
        # Platform
        "platform": _detect_platform(cwd),
    }
    result.update(_build_reference_runtime_context(cwd))
    result.update(_build_state_memory_runtime_context(cwd))
    result.update(_build_execution_runtime_context(cwd))

    planning = cwd / PLANNING_DIR_NAME
    if "state" in includes:
        result["state_content"] = _safe_read_file_truncated(planning / STATE_MD_FILENAME)
        result.update(_build_structured_state_runtime_context(cwd))
    if "config" in includes:
        result["config_content"] = _safe_read_file_truncated(planning / CONFIG_FILENAME)
    if "roadmap" in includes:
        result["roadmap_content"] = _safe_read_file_truncated(planning / ROADMAP_FILENAME)

    if stage is None:
        return result

    from gpd.core.workflow_staging import load_workflow_stage_manifest

    manifest = load_workflow_stage_manifest("research-phase", known_init_fields=_RESEARCH_PHASE_INIT_FIELDS)
    try:
        stage_def = manifest.stage_by_id(stage)
    except KeyError as exc:
        raise ValueError(
            f"Unknown research-phase stage {stage!r}. Allowed values: {', '.join(manifest.stage_ids())}."
        ) from exc

    missing_fields = [field for field in stage_def.required_init_fields if field not in result]
    if missing_fields:
        raise ValueError(
            f"research-phase stage {stage!r} requires unavailable init field(s): {', '.join(missing_fields)}"
        )

    staged_payload = {field: result[field] for field in stage_def.required_init_fields}
    staged_payload["staged_loading"] = manifest.staged_loading_payload(stage_def.id)
    return staged_payload


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
    config = load_config(cwd)
    normalized_topic = topic.strip() if isinstance(topic, str) and topic.strip() else None
    slug = _generate_slug(normalized_topic)
    if normalized_topic and slug is None:
        slug = "literature-review"
    if slug:
        slug = slug[:40]

    result: dict[str, object] = {
        "topic": normalized_topic,
        "slug": slug,
        "commit_docs": config["commit_docs"],
        "state_exists": _state_exists(cwd),
        "project_exists": _path_exists(cwd, f"{PLANNING_DIR_NAME}/{PROJECT_FILENAME}"),
        "research_mode": config["research_mode"],
        "autonomy": config["autonomy"],
        "roadmap_exists": _path_exists(cwd, f"{PLANNING_DIR_NAME}/{ROADMAP_FILENAME}"),
        "platform": _detect_platform(cwd),
    }
    result.update(_build_reference_runtime_context(cwd))

    if stage is None:
        return result

    from gpd.core.workflow_staging import load_workflow_stage_manifest

    manifest = load_workflow_stage_manifest("literature-review", known_init_fields=_LITERATURE_REVIEW_INIT_FIELDS)
    try:
        stage_def = manifest.stage_by_id(stage)
    except KeyError as exc:
        raise ValueError(
            f"Unknown literature-review stage {stage!r}. Allowed values: {', '.join(manifest.stage_ids())}."
        ) from exc

    missing_fields = [field for field in stage_def.required_init_fields if field not in result]
    if missing_fields:
        raise ValueError(
            f"literature-review stage {stage!r} requires unavailable init field(s): {', '.join(missing_fields)}"
        )

    staged_payload = {field: result[field] for field in stage_def.required_init_fields}
    staged_payload["staged_loading"] = manifest.staged_loading_payload(stage_def.id)
    return staged_payload


def init_todos(cwd: Path, area: str | None = None) -> dict:
    """Assemble context for todo management."""
    config = load_config(cwd)
    now = datetime.now(UTC)

    pending_dir = cwd / PLANNING_DIR_NAME / TODOS_DIR_NAME / "pending"
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
        "planning_exists": _path_exists(cwd, PLANNING_DIR_NAME),
        "todos_dir_exists": _path_exists(cwd, f"{PLANNING_DIR_NAME}/{TODOS_DIR_NAME}"),
        "pending_dir_exists": _path_exists(cwd, f"{PLANNING_DIR_NAME}/{TODOS_DIR_NAME}/pending"),
        # Platform
        "platform": _detect_platform(cwd),
    }


def init_milestone_op(cwd: Path) -> dict:
    """Assemble context for milestone operations (complete, archive, etc.)."""
    config = load_config(cwd)
    milestone = _try_get_milestone_info(cwd)
    reference_runtime_context = _build_reference_runtime_context(cwd)

    milestone_snapshot = _milestone_completion_snapshot(cwd)

    # Check archived milestones
    milestones_dir = cwd / PLANNING_DIR_NAME / MILESTONES_DIR_NAME
    archived_milestones: list[str] = []
    try:
        archived_milestones = sorted(
            entry.name for entry in milestones_dir.iterdir() if entry.is_dir() or entry.is_file()
        )
    except FileNotFoundError:
        pass

    return {
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
        "project_exists": _path_exists(cwd, f"{PLANNING_DIR_NAME}/{PROJECT_FILENAME}"),
        "roadmap_exists": _path_exists(cwd, f"{PLANNING_DIR_NAME}/{ROADMAP_FILENAME}"),
        "state_exists": _state_exists(cwd),
        "milestones_exists": _path_exists(cwd, f"{PLANNING_DIR_NAME}/{MILESTONES_DIR_NAME}"),
        "phases_dir_exists": _path_exists(cwd, f"{PLANNING_DIR_NAME}/{PHASES_DIR_NAME}"),
        # Platform
        "platform": _detect_platform(cwd),
        **reference_runtime_context,
    }


def init_map_research(cwd: Path, stage: str | None = None) -> dict:
    """Assemble context for research mapping."""
    config = load_config(cwd)

    # Check for existing research maps
    research_map_dir = cwd / PLANNING_DIR_NAME / RESEARCH_MAP_DIR_NAME
    existing_maps: list[str] = []
    try:
        existing_maps = sorted(f.name for f in research_map_dir.iterdir() if f.is_file() and f.name.endswith(".md"))
    except FileNotFoundError:
        pass

    result = {
        # Models
        "mapper_model": _resolve_model(cwd, "gpd-research-mapper", config),
        # Config
        "commit_docs": config["commit_docs"],
        "autonomy": config["autonomy"],
        "research_mode": config["research_mode"],
        "parallelization": config["parallelization"],
        # Paths
        "research_map_dir": f"{PLANNING_DIR_NAME}/{RESEARCH_MAP_DIR_NAME}",
        # Existing maps
        "existing_maps": existing_maps,
        "has_maps": len(existing_maps) > 0,
        # File existence
        "planning_exists": _path_exists(cwd, PLANNING_DIR_NAME),
        "research_map_dir_exists": _path_exists(cwd, f"{PLANNING_DIR_NAME}/{RESEARCH_MAP_DIR_NAME}"),
        # Platform
        "platform": _detect_platform(cwd),
    }
    result.update(_build_reference_runtime_context(cwd))

    if stage is None:
        return result

    from gpd.core.workflow_staging import load_workflow_stage_manifest

    manifest = load_workflow_stage_manifest("map-research", known_init_fields=_MAP_RESEARCH_INIT_FIELDS)
    try:
        stage_def = manifest.stage_by_id(stage)
    except KeyError as exc:
        raise ValueError(f"Unknown map-research stage {stage!r}. Allowed values: {', '.join(manifest.stage_ids())}.") from exc

    missing_fields = [field for field in stage_def.required_init_fields if field not in result]
    if missing_fields:
        raise ValueError(f"map-research stage {stage!r} requires unavailable init field(s): {', '.join(missing_fields)}")

    staged_payload = {field: result[field] for field in stage_def.required_init_fields}
    staged_payload["staged_loading"] = manifest.staged_loading_payload(stage_def.id)
    return staged_payload


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
    else:
        effective_cwd = resolve_project_root(requested_cwd, require_layout=True) or requested_cwd
        reentry_metadata = {
            "workspace_root": requested_cwd.as_posix(),
            "project_root": effective_cwd.as_posix(),
            "project_root_source": "workspace",
            "project_root_auto_selected": False,
        }
    config = load_config(effective_cwd)
    milestone = _try_get_milestone_info(effective_cwd)

    # Analyze phases
    layout = ProjectLayout(effective_cwd)
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
    result.update(_build_reference_runtime_context(effective_cwd))
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
