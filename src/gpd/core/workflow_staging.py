"""Shared workflow-stage manifest loading and validation."""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from functools import cache
from pathlib import Path, PurePosixPath

from gpd.adapters.tool_names import CANONICAL_TOOL_NAMES, canonical
from gpd.specs import SPECS_DIR

WORKFLOW_STAGE_MANIFEST_DIR = SPECS_DIR / "workflows"
WORKFLOW_STAGE_MANIFEST_SUFFIX = "-stage-manifest.json"
NEW_PROJECT_STAGE_MANIFEST_PATH = WORKFLOW_STAGE_MANIFEST_DIR / f"new-project{WORKFLOW_STAGE_MANIFEST_SUFFIX}"
EXECUTE_PHASE_STAGE_MANIFEST_PATH = WORKFLOW_STAGE_MANIFEST_DIR / f"execute-phase{WORKFLOW_STAGE_MANIFEST_SUFFIX}"
NEW_PROJECT_INIT_FIELDS = frozenset(
    {
        "researcher_model",
        "synthesizer_model",
        "roadmapper_model",
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
        "project_contract",
        "project_contract_gate",
        "project_contract_validation",
        "project_contract_load_info",
        "contract_intake",
        "effective_reference_intake",
        "active_reference_context",
        "reference_artifact_files",
        "reference_artifacts_content",
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
        "derived_convention_lock",
        "derived_convention_lock_count",
        "derived_intermediate_results",
        "derived_intermediate_result_count",
        "derived_approximations",
        "derived_approximation_count",
        "selected_protocol_bundle_ids",
        "protocol_bundle_count",
        "protocol_bundle_context",
        "protocol_bundle_verifier_extensions",
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
        "literature_review_files",
        "literature_review_count",
        "research_map_reference_files",
        "research_map_reference_count",
        "derived_active_references",
        "derived_active_reference_count",
        "citation_source_files",
        "citation_source_count",
        "citation_source_warnings",
        "derived_citation_sources",
        "derived_citation_source_count",
        "active_references",
        "active_reference_count",
        "derived_manuscript_reference_status",
        "derived_manuscript_reference_status_count",
        "derived_manuscript_proof_review_status",
        "platform",
    }
)
PLAN_PHASE_INIT_FIELDS = frozenset(
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
        "project_contract",
        "project_contract_gate",
        "project_contract_load_info",
        "project_contract_validation",
        "contract_intake",
        "effective_reference_intake",
        "selected_protocol_bundle_ids",
        "protocol_bundle_count",
        "protocol_bundle_context",
        "protocol_bundle_verifier_extensions",
        "active_reference_context",
        "reference_artifact_files",
        "reference_artifacts_content",
        "literature_review_files",
        "literature_review_count",
        "research_map_reference_files",
        "research_map_reference_count",
        "derived_manuscript_proof_review_status",
        "state_content",
        "roadmap_content",
        "requirements_content",
        "context_content",
        "research_content",
        "experiment_design_content",
        "verification_content",
        "validation_content",
    }
)
VERIFY_WORK_INIT_FIELDS = frozenset(
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
        "platform",
        "phase_proof_review_status",
        "project_contract",
        "project_contract_validation",
        "project_contract_load_info",
        "project_contract_gate",
        "contract_intake",
        "effective_reference_intake",
        "derived_active_references",
        "derived_active_reference_count",
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
        "literature_review_files",
        "literature_review_count",
        "research_map_reference_files",
        "research_map_reference_count",
        "reference_artifact_files",
        "reference_artifacts_content",
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
        "derived_convention_lock",
        "derived_convention_lock_count",
        "derived_intermediate_results",
        "derived_intermediate_result_count",
        "derived_approximations",
        "derived_approximation_count",
    }
)
_DEFAULT_KNOWN_INIT_FIELDS_BY_WORKFLOW = {
    "new-project": NEW_PROJECT_INIT_FIELDS,
    "plan-phase": PLAN_PHASE_INIT_FIELDS,
    "verify-work": VERIFY_WORK_INIT_FIELDS,
    "execute-phase": EXECUTE_PHASE_INIT_FIELDS,
}
_WORKFLOW_STAGE_REQUIRED_INIT_FIELD_OVERRIDES = {
    "plan-phase": {
        "planner_authoring": ("experiment_design_content",),
        "checker_revision": ("experiment_design_content",),
    }
}

_ALLOWED_TOP_LEVEL_KEYS = frozenset({"schema_version", "workflow_id", "stages"})
_ALLOWED_STAGE_KEYS = frozenset(
    {
        "id",
        "order",
        "purpose",
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
    }
)
_ALLOWED_CONDITIONAL_KEYS = frozenset({"when", "authorities"})
_AUTHORITY_ROOTS = ("workflows/", "references/", "templates/")


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

    def to_payload(self) -> dict[str, object]:
        return {
            "id": self.id,
            "order": self.order,
            "purpose": self.purpose,
            "mode_paths": list(self.mode_paths),
            "required_init_fields": list(self.required_init_fields),
            "loaded_authorities": list(self.loaded_authorities),
            "conditional_authorities": [entry.to_payload() for entry in self.conditional_authorities],
            "must_not_eager_load": list(self.must_not_eager_load),
            "allowed_tools": list(self.allowed_tools),
            "writes_allowed": list(self.writes_allowed),
            "produced_state": list(self.produced_state),
            "next_stages": list(self.next_stages),
            "checkpoints": list(self.checkpoints),
        }

    def to_staged_loading_payload(self, workflow_id: str) -> dict[str, object]:
        return {
            "workflow_id": workflow_id,
            "stage_id": self.id,
            "order": self.order,
            "loaded_authorities": list(self.loaded_authorities),
            "conditional_authorities": [entry.to_payload() for entry in self.conditional_authorities],
            "must_not_eager_load": list(self.must_not_eager_load),
            "allowed_tools": list(self.allowed_tools),
            "writes_allowed": list(self.writes_allowed),
            "next_stages": list(self.next_stages),
            "checkpoints": list(self.checkpoints),
        }


@dataclass(frozen=True, slots=True)
class WorkflowStageManifest:
    schema_version: int
    workflow_id: str
    stages: tuple[WorkflowStage, ...]

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
        return {
            "schema_version": self.schema_version,
            "workflow_id": self.workflow_id,
            "stages": [stage.to_payload() for stage in self.stages],
        }


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


def _normalize_manifest_doc_path(raw: object, *, label: str) -> str:
    value = _require_string(raw, label=label)
    if "\\" in value:
        raise ValueError(f"{label} must be a normalized relative POSIX path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {".", ".."} for part in path.parts):
        raise ValueError(f"{label} must be a normalized relative POSIX path")
    normalized = path.as_posix()
    if normalized != value:
        raise ValueError(f"{label} must be a normalized relative POSIX path")
    if path.suffix != ".md":
        raise ValueError(f"{label} must reference an existing markdown file: {value}")
    if not normalized.startswith(_AUTHORITY_ROOTS):
        raise ValueError(f"{label} must reference an authority path under workflows/, references/, or templates/")
    if not (SPECS_DIR / normalized).is_file():
        raise ValueError(f"{label} must reference an existing markdown file: {normalized}")
    return normalized


def _normalize_write_path(raw: object, *, label: str) -> str:
    value = _require_string(raw, label=label)
    if "\\" in value:
        raise ValueError(f"{label} must be a normalized relative POSIX path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {".", ".."} for part in path.parts):
        raise ValueError(f"{label} must be a normalized relative POSIX path")
    normalized = path.as_posix()
    if normalized != value or not normalized.startswith("GPD/"):
        raise ValueError(f"{label} must be a normalized relative POSIX path")
    return normalized


def _normalize_tool_set(values: Iterable[str] | None) -> frozenset[str]:
    if values is None:
        return frozenset(CANONICAL_TOOL_NAMES)
    normalized: set[str] = set()
    for value in values:
        if not isinstance(value, str):
            raise ValueError("allowed_tools must be strings")
        tool = canonical(value.strip())
        if not tool:
            raise ValueError("allowed_tools must not contain blank entries")
        normalized.add(tool)
    return frozenset(normalized)


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
    return _DEFAULT_KNOWN_INIT_FIELDS_BY_WORKFLOW.get(normalized_workflow_id)


def _validate_conditional_authorities(raw: object, *, stage_index: int) -> tuple[WorkflowStageConditionalAuthority, ...]:
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
            _normalize_manifest_doc_path(authority, label=f"{entry_label}.authorities[{authority_index}]")
            for authority_index, authority in enumerate(
                _require_string_tuple(entry["authorities"], label=f"{entry_label}.authorities")
            )
        )
        items.append(WorkflowStageConditionalAuthority(when=when, authorities=authorities))
    return tuple(items)


def _validate_stage(
    raw: object,
    *,
    index: int,
    workflow_id: str,
    allowed_tools: frozenset[str],
    known_init_fields: frozenset[str] | None,
) -> WorkflowStage:
    if not isinstance(raw, dict):
        raise ValueError(f"stages[{index}] must be a JSON object")

    unknown_keys = sorted(str(key) for key in raw if str(key) not in _ALLOWED_STAGE_KEYS)
    if unknown_keys:
        raise ValueError(f"stages[{index}] contains unexpected key(s): {', '.join(unknown_keys)}")

    missing_keys = sorted(key for key in _ALLOWED_STAGE_KEYS if key not in raw)
    if missing_keys:
        raise ValueError(f"stages[{index}] is missing required key(s): {', '.join(missing_keys)}")

    stage_id = _require_string(raw["id"], label=f"stages[{index}].id")
    order = _require_int(raw["order"], label=f"stages[{index}].order")
    purpose = _require_string(raw["purpose"], label=f"stages[{index}].purpose")
    mode_paths = tuple(
        _normalize_manifest_doc_path(mode_path, label=f"stages[{index}].mode_paths[{mode_index}]")
        for mode_index, mode_path in enumerate(
            _require_string_tuple(raw["mode_paths"], label=f"stages[{index}].mode_paths")
        )
    )
    required_init_fields = _require_string_tuple(
        raw["required_init_fields"],
        label=f"stages[{index}].required_init_fields",
        allow_empty=True,
    )
    required_init_fields = _augment_required_init_fields(
        workflow_id=workflow_id,
        stage_id=stage_id,
        required_init_fields=required_init_fields,
    )
    loaded_authorities = tuple(
        _normalize_manifest_doc_path(authority, label=f"stages[{index}].loaded_authorities[{authority_index}]")
        for authority_index, authority in enumerate(
            _require_string_tuple(raw["loaded_authorities"], label=f"stages[{index}].loaded_authorities", allow_empty=True)
        )
    )
    conditional_authorities = _validate_conditional_authorities(
        raw.get("conditional_authorities", []),
        stage_index=index,
    )
    must_not_eager_load = tuple(
        _normalize_manifest_doc_path(authority, label=f"stages[{index}].must_not_eager_load[{authority_index}]")
        for authority_index, authority in enumerate(
            _require_string_tuple(raw["must_not_eager_load"], label=f"stages[{index}].must_not_eager_load", allow_empty=True)
        )
    )
    allowed_tools_values = tuple(
        canonical(tool.strip())
        for tool in _require_string_tuple(raw["allowed_tools"], label=f"stages[{index}].allowed_tools", allow_empty=True)
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
    )


def _augment_required_init_fields(
    *,
    workflow_id: str,
    stage_id: str,
    required_init_fields: tuple[str, ...],
) -> tuple[str, ...]:
    overrides = _WORKFLOW_STAGE_REQUIRED_INIT_FIELD_OVERRIDES.get(workflow_id, {}).get(stage_id, ())
    if not overrides:
        return required_init_fields

    combined = list(required_init_fields)
    seen = set(required_init_fields)
    for field_name in overrides:
        if field_name in seen:
            continue
        seen.add(field_name)
        combined.append(field_name)
    return tuple(combined)


def validate_workflow_stage_manifest_payload(
    raw: object,
    *,
    expected_workflow_id: str | None = None,
    allowed_tools: Iterable[str] | None = None,
    known_init_fields: Iterable[str] | None = None,
) -> WorkflowStageManifest:
    if not isinstance(raw, dict):
        raise ValueError("workflow stage manifest must be a JSON object")

    unknown_keys = sorted(str(key) for key in raw if str(key) not in _ALLOWED_TOP_LEVEL_KEYS)
    if unknown_keys:
        raise ValueError(f"workflow stage manifest contains unexpected key(s): {', '.join(unknown_keys)}")

    missing_keys = sorted(key for key in _ALLOWED_TOP_LEVEL_KEYS if key not in raw)
    if missing_keys:
        raise ValueError(f"workflow stage manifest is missing required key(s): {', '.join(missing_keys)}")

    schema_version = _require_int(raw["schema_version"], label="schema_version")
    if schema_version != 1:
        raise ValueError("workflow stage manifest schema_version must be 1")

    workflow_id = _normalize_workflow_id(raw["workflow_id"])
    if expected_workflow_id is not None and workflow_id != expected_workflow_id:
        raise ValueError(
            f"workflow stage manifest workflow_id must be {expected_workflow_id!r}, got {workflow_id!r}"
        )

    stages_raw = raw["stages"]
    if not isinstance(stages_raw, list) or not stages_raw:
        raise ValueError("stages must be a non-empty list")

    normalized_allowed_tools = _normalize_tool_set(allowed_tools)
    normalized_known_init_fields = _normalize_init_field_set(known_init_fields, workflow_id=workflow_id)
    stages = tuple(
        _validate_stage(
            stage,
            index=index,
            workflow_id=workflow_id,
            allowed_tools=normalized_allowed_tools,
            known_init_fields=normalized_known_init_fields,
        )
        for index, stage in enumerate(stages_raw)
    )

    stage_ids = [stage.id for stage in stages]
    if len(set(stage_ids)) != len(stage_ids):
        raise ValueError("stage ids must be unique")

    stage_orders = [stage.order for stage in stages]
    if len(set(stage_orders)) != len(stage_orders):
        raise ValueError("stage order values must be unique")
    if stage_orders != list(range(1, len(stages) + 1)):
        raise ValueError("stage order values must start at 1 and increase by 1")

    stage_id_set = set(stage_ids)
    order_by_id = {stage.id: stage.order for stage in stages}
    for stage in stages:
        backward_next = sorted(
            next_stage
            for next_stage in stage.next_stages
            if next_stage in stage_id_set and order_by_id[next_stage] <= stage.order
        )
        if backward_next:
            raise ValueError(
                f"stage {stage.id!r} must only point to later stages; got {', '.join(backward_next)}"
            )

    return WorkflowStageManifest(schema_version=schema_version, workflow_id=workflow_id, stages=stages)


def _cache_key_tools(values: Iterable[str] | None) -> tuple[str, ...]:
    return tuple(sorted(_normalize_tool_set(values)))


def _cache_key_init_fields(values: Iterable[str] | None, *, workflow_id: str) -> tuple[str, ...] | None:
    normalized = _normalize_init_field_set(values, workflow_id=workflow_id)
    return tuple(sorted(normalized)) if normalized is not None else None


@cache
def _load_workflow_stage_manifest_cached(
    manifest_path: str,
    expected_workflow_id: str | None,
    allowed_tools_key: tuple[str, ...],
    known_init_fields_key: tuple[str, ...] | None,
) -> WorkflowStageManifest:
    path = Path(manifest_path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Failed to read workflow stage manifest {path}: {exc}") from exc
    return validate_workflow_stage_manifest_payload(
        payload,
        expected_workflow_id=expected_workflow_id,
        allowed_tools=allowed_tools_key,
        known_init_fields=known_init_fields_key,
    )


def load_workflow_stage_manifest(
    workflow_id: str,
    *,
    allowed_tools: Iterable[str] | None = None,
    known_init_fields: Iterable[str] | None = None,
) -> WorkflowStageManifest:
    workflow_id = _normalize_workflow_id(workflow_id)
    manifest_path = resolve_workflow_stage_manifest_path(workflow_id)
    return _load_workflow_stage_manifest_cached(
        manifest_path.as_posix(),
        workflow_id,
        _cache_key_tools(allowed_tools),
        _cache_key_init_fields(known_init_fields, workflow_id=workflow_id),
    )


def load_workflow_stage_manifest_from_path(
    manifest_path: Path,
    *,
    expected_workflow_id: str | None = None,
    allowed_tools: Iterable[str] | None = None,
    known_init_fields: Iterable[str] | None = None,
) -> WorkflowStageManifest:
    workflow_id = _normalize_workflow_id(expected_workflow_id) if expected_workflow_id is not None else None
    normalized_init_fields = _cache_key_init_fields(
        known_init_fields if known_init_fields is not None else known_init_fields_for_workflow(workflow_id),
        workflow_id=workflow_id or "new-project",
    )
    return _load_workflow_stage_manifest_cached(
        manifest_path.as_posix(),
        workflow_id,
        _cache_key_tools(allowed_tools),
        normalized_init_fields,
    )


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


def load_execute_phase_stage_contract() -> WorkflowStageManifest:
    return load_workflow_stage_manifest("execute-phase")


def load_execute_phase_stage_contract_from_path(manifest_path: Path) -> WorkflowStageManifest:
    return load_workflow_stage_manifest_from_path(manifest_path, expected_workflow_id="execute-phase")


def validate_execute_phase_stage_contract_payload(raw: object) -> WorkflowStageManifest:
    return validate_workflow_stage_manifest_payload(raw, expected_workflow_id="execute-phase")


__all__ = [
    "NEW_PROJECT_INIT_FIELDS",
    "NEW_PROJECT_STAGE_MANIFEST_PATH",
    "EXECUTE_PHASE_INIT_FIELDS",
    "EXECUTE_PHASE_STAGE_MANIFEST_PATH",
    "NewProjectConditionalAuthority",
    "NewProjectStage",
    "NewProjectStageContract",
    "PLAN_PHASE_INIT_FIELDS",
    "WORKFLOW_STAGE_MANIFEST_DIR",
    "WORKFLOW_STAGE_MANIFEST_SUFFIX",
    "VERIFY_WORK_INIT_FIELDS",
    "WorkflowStage",
    "WorkflowStageConditionalAuthority",
    "WorkflowStageManifest",
    "invalidate_workflow_stage_manifest_cache",
    "load_new_project_stage_contract",
    "load_new_project_stage_contract_from_path",
    "load_execute_phase_stage_contract",
    "load_execute_phase_stage_contract_from_path",
    "load_workflow_stage_manifest",
    "load_workflow_stage_manifest_from_path",
    "known_init_fields_for_workflow",
    "resolve_workflow_stage_manifest_path",
    "validate_new_project_stage_contract_payload",
    "validate_execute_phase_stage_contract_payload",
    "validate_workflow_stage_manifest_payload",
]
