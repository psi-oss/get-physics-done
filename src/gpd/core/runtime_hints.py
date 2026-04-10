"""Shallow runtime hint payload assembly for hook and status consumers.

The helper centralizes the discoverability data already exposed by the core
execution, recovery, cost, and workflow-preset layers without introducing a
deeper schema. It is intentionally explicit so hook-facing callers can forward
one normalized payload instead of stitching together multiple summaries.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from gpd.core.context import init_resume
from gpd.core.costs import build_cost_summary, resolve_cost_advisory
from gpd.core.observability import derive_execution_visibility, get_current_session_id
from gpd.core.project_reentry import (
    project_reentry_candidate_summary,
    recoverable_project_context,
    resolve_project_reentry,
)
from gpd.core.public_surface_contract import recovery_local_snapshot_command
from gpd.core.recent_projects import _strict_bool_value, list_recent_projects
from gpd.core.recovery_advice import (
    RecoveryAdvice,
    build_recovery_advice,
    serialize_recovery_orientation,
)
from gpd.core.resume_surface import (
    RESUME_CANDIDATE_KIND_BOUNDED_SEGMENT,
    RESUME_CANDIDATE_KIND_CONTINUITY_HANDOFF,
    RESUME_CANDIDATE_ORIGIN_CONTINUATION_BOUNDED_SEGMENT,
    RESUME_CANDIDATE_ORIGIN_CONTINUATION_HANDOFF,
    build_resume_candidate,
    build_resume_static_candidate,
    resume_payload_has_local_recovery_target,
)
from gpd.core.root_resolution import normalize_workspace_hint, resolve_project_roots
from gpd.core.runtime_command_surfaces import format_active_runtime_command
from gpd.core.surface_phrases import (
    command_follow_up_action,
    cost_inspect_action,
    recovery_action_lines,
    tangent_branch_later_action,
    tangent_chooser_action,
)
from gpd.core.surface_phrases import (
    workflow_preset_surface_note as _workflow_preset_surface_note_text,
)
from gpd.core.utils import dedupe_preserve_order
from gpd.core.workflow_presets import (
    _normalize_latex_capability,
    resolve_workflow_preset_readiness,
)

__all__ = [
    "RuntimeHintPayload",
    "build_runtime_hint_payload",
    "workflow_preset_surface_note",
]


logger = logging.getLogger(__name__)


class RuntimeHintPayload(BaseModel):
    """Shallow normalized runtime hint payload."""

    model_config = ConfigDict(frozen=True)

    source_meta: dict[str, object] = Field(default_factory=dict)
    execution: dict[str, object] | None = None
    recovery: dict[str, object] = Field(default_factory=dict)
    orientation: dict[str, object] = Field(default_factory=dict)
    cost: dict[str, object] = Field(default_factory=dict)
    workflow_presets: dict[str, object] = Field(default_factory=dict)
    next_actions: list[str] = Field(default_factory=list)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _path_text(value: Path | None) -> str | None:
    return value.as_posix() if value is not None else None


def _model_dump(value: object) -> dict[str, object] | None:
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        try:
            dumped = value.model_dump(mode="json")  # type: ignore[assignment]
        except Exception as exc:
            logger.warning("Runtime hint serialization skipped %s: %s", type(value).__name__, exc)
            return None
        return dumped if isinstance(dumped, dict) else None
    return value if isinstance(value, dict) else None


def workflow_preset_surface_note() -> str:
    """Return the shared workflow-preset surface note."""
    return _workflow_preset_surface_note_text()


def _selected_reentry_candidate(
    reentry: object,
    *,
    workspace_hint: Path | None = None,
    recent_rows: list[object] | None = None,
) -> dict[str, object] | None:
    candidates = list(getattr(reentry, "candidates", []) or [])
    selected_candidate = next(
        (candidate for candidate in candidates if _suggestion_text(candidate, "source") == "current_workspace"),
        getattr(reentry, "selected_candidate", None),
    )
    candidate_payload = _model_dump(selected_candidate)
    if candidate_payload is None and workspace_hint is not None:
        resolution = resolve_project_roots(workspace_hint)
        if resolution is not None and resolution.has_project_layout:
            project_root = resolution.project_root.resolve(strict=False)
            state_exists, roadmap_exists, project_exists = recoverable_project_context(project_root)
            candidate_payload = {
                "source": "current_workspace",
                "project_root": project_root.as_posix(),
                "available": project_root.is_dir(),
                "recoverable": state_exists or roadmap_exists or project_exists,
                "resumable": False,
                "confidence": str(getattr(resolution.confidence, "value", resolution.confidence)),
                "reason": "workspace already points at a GPD project",
                "state_exists": state_exists,
                "roadmap_exists": roadmap_exists,
                "project_exists": project_exists,
            }
            for row in recent_rows or []:
                row_payload = _model_dump(row) if not isinstance(row, dict) else dict(row)
                if not isinstance(row_payload, dict):
                    continue
                if _normalized_row_text(row_payload, "project_root") != project_root.as_posix():
                    continue
                candidate_payload.update(
                    {
                        key: row_payload.get(key)
                        for key in (
                            "resume_file",
                            "last_result_id",
                            "resume_target_kind",
                            "resume_target_recorded_at",
                            "resume_file_available",
                            "resume_file_reason",
                            "hostname",
                            "platform",
                            "availability_reason",
                            "last_session_at",
                            "stopped_at",
                            "source_kind",
                            "source_session_id",
                            "source_segment_id",
                            "source_transition_id",
                            "source_recorded_at",
                            "recovery_phase",
                            "recovery_plan",
                        )
                    }
                )
                if _strict_bool_value(row_payload.get("resume_file_available")) is True or _strict_bool_value(
                    row_payload.get("resumable")
                ) is True:
                    candidate_payload["resumable"] = True
                break
    if not isinstance(candidate_payload, dict):
        return None
    summary = project_reentry_candidate_summary(selected_candidate or candidate_payload)
    candidate_payload["summary"] = summary
    return candidate_payload


def _normalized_row_text(row: dict[str, object] | None, field: str) -> str | None:
    if row is None:
        return None
    value = row.get(field)
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _recent_project_summary(row: dict[str, object] | None) -> str | None:
    return project_reentry_candidate_summary(row)


def _selected_project_summary(reentry: object, current_project: dict[str, object] | None) -> str | None:
    return _recent_project_summary(current_project)


def _project_reentry_summary(
    reentry: object,
    current_project: dict[str, object] | None,
    *,
    recovery_reason: str | None = None,
) -> str | None:
    auto_selected = _strict_bool_value(getattr(reentry, "auto_selected", None)) is True
    requires_selection = _strict_bool_value(getattr(reentry, "requires_user_selection", None)) is True
    mode = _suggestion_text(reentry, "mode")
    candidates = list(getattr(reentry, "candidates", []) or [])
    recent_candidates = [candidate for candidate in candidates if _suggestion_text(candidate, "source") == "recent_project"]

    def _candidate_bool(candidate: object, field: str) -> bool:
        if isinstance(candidate, dict):
            return _strict_bool_value(candidate.get(field)) is True
        return _strict_bool_value(getattr(candidate, field, None)) is True

    if auto_selected:
        summary = "GPD auto-selected the only recoverable recent project on this machine."
        current_project_summary = _selected_project_summary(reentry, current_project)
        if current_project_summary is not None:
            summary = f"{summary} {current_project_summary}."
        return summary
    if requires_selection:
        return "GPD found multiple recoverable recent projects on this machine, so you need to choose one."
    if (
        current_project is not None
        and current_project.get("source") == "current_workspace"
        and _strict_bool_value(current_project.get("recoverable")) is not True
        and (recent_candidates or _recent_project_summary(current_project) is not None)
    ):
        if any(_candidate_bool(candidate, "resumable") for candidate in recent_candidates):
            return "GPD found recent projects on this machine, but none are selected automatically."
        return "GPD found recent projects on this machine, but none are ready to reopen automatically."
    if mode == "recent-projects":
        if current_project is not None and _strict_bool_value(current_project.get("resumable")) is True:
            return "GPD found recent projects on this machine, but none are selected automatically."
        return "GPD found recent projects on this machine, but none are ready to reopen automatically."
    if recovery_reason is not None:
        return recovery_reason
    return None


def _runtime_command(action: str, *, cwd: Path, runtime_name: str | None = None) -> str | None:
    if runtime_name is not None:
        return format_active_runtime_command(
            action,
            cwd=cwd,
            detect_runtime=lambda **kwargs: runtime_name,
            fallback=None,
        )
    return format_active_runtime_command(action, cwd=cwd, fallback=None)


def _installed_runtime_for_surface(cwd: Path) -> str | None:
    try:
        from gpd.hooks.runtime_detect import (
            RUNTIME_UNKNOWN,
            detect_runtime_for_gpd_use,
            detect_runtime_install_target,
        )

        runtime_name = detect_runtime_for_gpd_use(cwd=cwd)
        if (
            not isinstance(runtime_name, str)
            or not runtime_name.strip()
            or runtime_name == RUNTIME_UNKNOWN
            or detect_runtime_install_target(runtime_name, cwd=cwd) is None
        ):
            return None
        return runtime_name
    except Exception:
        return None


def _current_session_id_for_surface(project_root: Path) -> str | None:
    try:
        session_id = get_current_session_id(project_root)
    except Exception:
        return None
    if not isinstance(session_id, str) or not session_id.strip():
        return None
    return session_id


def _resume_context(cwd: Path, *, data_root: Path | None = None) -> dict[str, object]:
    payload = init_resume(cwd, data_root=data_root)
    return payload if isinstance(payload, dict) else {}


def _recent_project_resume_family(
    current_project: dict[str, object],
) -> tuple[str | None, str | None]:
    resume_target_kind = _normalized_row_text(current_project, "resume_target_kind")
    if resume_target_kind is None:
        return (
            RESUME_CANDIDATE_KIND_CONTINUITY_HANDOFF,
            RESUME_CANDIDATE_ORIGIN_CONTINUATION_HANDOFF,
        )
    if resume_target_kind == "bounded_segment":
        return (
            RESUME_CANDIDATE_KIND_BOUNDED_SEGMENT,
            RESUME_CANDIDATE_ORIGIN_CONTINUATION_BOUNDED_SEGMENT,
        )
    if resume_target_kind == "handoff":
        return (
            RESUME_CANDIDATE_KIND_CONTINUITY_HANDOFF,
            RESUME_CANDIDATE_ORIGIN_CONTINUATION_HANDOFF,
        )
    return None, None


def _recent_project_provenance_fields(current_project: dict[str, object]) -> dict[str, object]:
    """Return session/provenance fields derived from one recent-project row."""

    provenance: dict[str, object] = {}
    for target_field, source_field in (
        ("session_hostname", "hostname"),
        ("session_platform", "platform"),
        ("session_last_date", "last_session_at"),
        ("session_stopped_at", "stopped_at"),
    ):
        value = _normalized_row_text(current_project, source_field)
        if value is not None:
            provenance[target_field] = value
    return provenance


def _resume_context_has_local_target(payload: dict[str, object]) -> bool:
    """Return whether one resume payload already exposes a local recovery target."""
    return resume_payload_has_local_recovery_target(payload)


def _hydrate_resume_context_from_recent_project(
    payload: dict[str, object],
    *,
    reentry: object,
    current_project: dict[str, object] | None,
) -> dict[str, object]:
    """Fill the selected-recent-project resume gap when local state has not been loaded yet."""
    if _strict_bool_value(getattr(reentry, "auto_selected", None)) is not True:
        return payload
    if current_project is None:
        return payload
    if _resume_context_has_local_target(payload):
        return payload

    resume_file = current_project.get("resume_file")
    if not isinstance(resume_file, str) or not resume_file.strip():
        return payload
    resume_file = resume_file.strip()
    resume_file_available = _strict_bool_value(current_project.get("resume_file_available")) is True
    hydration_kind, hydration_origin = _recent_project_resume_family(current_project)
    if hydration_kind is None or hydration_origin is None:
        return payload
    candidate_status = "handoff" if resume_file_available else "missing"

    hydrated = dict(payload)
    hydrated.setdefault("project_root", current_project.get("project_root"))
    hydrated.setdefault("project_root_source", "recent_project")
    hydrated.setdefault("project_root_auto_selected", True)
    hydrated.setdefault("project_reentry_mode", getattr(reentry, "mode", None))
    if not str(hydrated.get("active_resume_kind") or "").strip():
        hydrated["active_resume_kind"] = hydration_kind
    if not str(hydrated.get("active_resume_origin") or "").strip():
        hydrated["active_resume_origin"] = hydration_origin
    if resume_file_available and not str(hydrated.get("active_resume_pointer") or "").strip():
        hydrated["active_resume_pointer"] = resume_file
    if hydration_kind == RESUME_CANDIDATE_KIND_CONTINUITY_HANDOFF and resume_file_available:
        if not str(hydrated.get("continuity_handoff_file") or "").strip():
            hydrated["continuity_handoff_file"] = resume_file
        hydrated["has_continuity_handoff"] = True
        if not str(hydrated.get("recorded_continuity_handoff_file") or "").strip():
            hydrated["recorded_continuity_handoff_file"] = resume_file
    elif hydration_kind == RESUME_CANDIDATE_KIND_CONTINUITY_HANDOFF and not resume_file_available:
        if not str(hydrated.get("recorded_continuity_handoff_file") or "").strip():
            hydrated["recorded_continuity_handoff_file"] = resume_file
        if not str(hydrated.get("missing_continuity_handoff_file") or "").strip():
            hydrated["missing_continuity_handoff_file"] = resume_file

    for field_name, field_value in _recent_project_provenance_fields(current_project).items():
        if not str(hydrated.get(field_name) or "").strip():
            hydrated[field_name] = field_value

    resume_candidates = hydrated.get("resume_candidates")
    candidate = build_resume_candidate(
        build_resume_static_candidate(
            source="session_resume_file",
            status=candidate_status,
            resume_file=resume_file,
            resumable=False,
            advisory=not resume_file_available,
        ),
        kind=hydration_kind,
        origin=hydration_origin,
        resume_pointer=resume_file,
    )
    if isinstance(resume_candidates, list):
        if not any(
            isinstance(existing, dict)
            and str(existing.get("resume_file") or "").strip() == resume_file
            for existing in resume_candidates
        ):
            hydrated["resume_candidates"] = [*resume_candidates, candidate]
    else:
        hydrated["resume_candidates"] = [candidate]
    return hydrated


def _recovery_next_actions(
    advice: RecoveryAdvice,
    *,
    existing_actions: list[str] | None = None,
    allow_after_selection: bool = False,
) -> list[str]:
    existing = list(existing_actions or [])
    actions = list(advice.actions)
    local_snapshot_command = recovery_local_snapshot_command()
    if any(f"`{local_snapshot_command}`" in action for action in existing):
        actions = [
            action
            for action in actions
            if not (str(action.kind) == "primary" and str(action.command) == local_snapshot_command)
        ]
    return recovery_action_lines(
        actions=actions,
        mode=advice.mode,
        existing_actions=existing,
        allowed_availability={"now", "after_selection"}
        if allow_after_selection
        or (
            advice.mode == "recent-projects"
            and not bool(getattr(advice, "project_reentry_requires_selection", False))
        )
        else {"now"},
        include_primary=True,
    )


def _suggestion_text(value: object, field: str) -> str | None:
    if isinstance(value, dict):
        candidate = value.get(field)
    else:
        candidate = getattr(value, field, None)
    if not isinstance(candidate, str):
        return None
    stripped = candidate.strip()
    return stripped or None


def _execution_next_actions(execution_visibility: object | None) -> list[str]:
    if execution_visibility is None:
        return []

    raw_suggestions = list(getattr(execution_visibility, "suggested_next_commands", []) or [])
    actions = [
        command_follow_up_action(command=command, reason=reason)
        for suggestion in raw_suggestions
        if (command := _suggestion_text(suggestion, "command")) is not None
        and (reason := _suggestion_text(suggestion, "reason")) is not None
    ]

    tangent_summary = _suggestion_text(execution_visibility, "tangent_summary")
    tangent_decision = _suggestion_text(execution_visibility, "tangent_decision")
    if tangent_summary is not None and tangent_decision is None:
        actions.append(tangent_chooser_action())
    if tangent_summary is not None and tangent_decision == "branch_later":
        actions.append(tangent_branch_later_action())
    return actions


def _workflow_next_actions(*, base_ready: bool) -> list[str]:
    if not base_ready:
        return ["Fix base runtime-readiness issues before relying on workflow presets."]
    return []


def _cost_next_action(advisory: dict[str, object]) -> str | None:
    state = str(advisory.get("state", "") or "").strip()
    if state in {"at_or_over_budget", "near_budget", "mixed"}:
        return cost_inspect_action()
    return None


def _cost_advisory(cost_summary: object) -> dict[str, object] | None:
    structured_advisory = resolve_cost_advisory(cost_summary)
    advisory = _model_dump(structured_advisory)
    if advisory is None:
        return None
    next_action = _cost_next_action(advisory)
    if next_action is not None:
        advisory["next_action"] = next_action
    return advisory


def _cost_project_root(cost_summary: object) -> str | None:
    project_rollup = getattr(cost_summary, "project", None)
    project_root = getattr(project_rollup, "project_root", None)
    if isinstance(project_root, str) and project_root.strip():
        return project_root.strip()
    return None


def _cost_payload(cost_summary: object) -> dict[str, object]:
    payload = _model_dump(cost_summary) or {}
    project_root = _cost_project_root(cost_summary)
    if project_root is not None:
        payload["project_root"] = project_root
    return payload


def build_runtime_hint_payload(
    cwd: Path | None = None,
    *,
    data_root: Path | None = None,
    base_ready: bool = True,
    latex_capability: object | None = None,
    recent_projects_last: int = 5,
    cost_last_sessions: int = 5,
    include_recovery: bool = True,
    include_cost: bool = True,
    include_workflow_presets: bool = True,
) -> RuntimeHintPayload:
    """Build one shallow runtime hint payload from the canonical core summaries."""

    workspace_hint = normalize_workspace_hint(cwd) if cwd is not None else None
    if workspace_hint is None:
        workspace_hint = Path.cwd().resolve(strict=False)
    resolution = resolve_project_roots(workspace_hint)
    workspace_project_root = resolution.project_root if resolution is not None else workspace_hint
    reentry = resolve_project_reentry(workspace_hint, data_root=data_root) if include_recovery else None
    project_root = (
        reentry.resolved_project_root
        if include_recovery and reentry is not None and reentry.resolved_project_root is not None
        else workspace_project_root
    )
    surface_runtime = _installed_runtime_for_surface(project_root)

    execution_visibility = derive_execution_visibility(project_root)
    execution = _model_dump(execution_visibility)

    recent_rows = list_recent_projects(data_root, last=recent_projects_last) if include_recovery else []
    current_project = (
        _selected_reentry_candidate(reentry, workspace_hint=workspace_hint, recent_rows=recent_rows)
        if include_recovery and reentry is not None
        else None
    )
    resume_context = _resume_context(workspace_hint, data_root=data_root) if include_recovery else {}
    if include_recovery and reentry is not None:
        resume_context = _hydrate_resume_context_from_recent_project(
            resume_context,
            reentry=reentry,
            current_project=current_project,
        )
        candidate_payloads = [
            candidate_payload
            for candidate in (getattr(reentry, "candidates", []) or [])
            if isinstance((candidate_payload := _model_dump(candidate)), dict)
        ]
        if isinstance(resume_context, dict):
            if candidate_payloads:
                resume_context["project_reentry_candidates"] = candidate_payloads
                selected_payload = _model_dump(getattr(reentry, "selected_candidate", None))
                if isinstance(selected_payload, dict):
                    resume_context["project_reentry_selected_candidate"] = selected_payload
                else:
                    resume_context.pop("project_reentry_selected_candidate", None)
            else:
                resume_context.pop("project_reentry_candidates", None)
                resume_context.pop("project_reentry_selected_candidate", None)
    cost_summary = build_cost_summary(project_root, data_root=data_root, last_sessions=cost_last_sessions) if include_cost else None
    cost = _cost_payload(cost_summary) if cost_summary is not None else {}
    cost_advisory = _cost_advisory(cost_summary) if cost_summary is not None else None
    if cost_advisory is not None:
        cost["advisory"] = cost_advisory

    resolved_runtime = surface_runtime if surface_runtime is not None else cost_summary.active_runtime if cost_summary is not None else None

    recovery_advice = None
    if include_recovery and reentry is not None:
        recovery_advice = build_recovery_advice(
            project_root,
            data_root=data_root,
            recent_rows=recent_rows,
            resume_payload=resume_context,
            continue_command=_runtime_command("resume-work", cwd=project_root, runtime_name=resolved_runtime),
            fast_next_command=_runtime_command("suggest-next", cwd=project_root, runtime_name=resolved_runtime),
        )
    recovery = (
        {
            "current_project": (
                {
                    **current_project,
                    **_recent_project_provenance_fields(current_project),
                    "summary": _selected_project_summary(reentry, current_project),
                }
                if current_project is not None and reentry is not None
                else None
            ),
            "current_project_summary": _selected_project_summary(reentry, current_project) if reentry is not None else None,
            "project_reentry": _model_dump(reentry),
            "project_reentry_summary": _project_reentry_summary(
                reentry,
                current_project,
                recovery_reason=recovery_advice.project_reentry_reason if recovery_advice is not None else None,
            ),
            "recent_projects": [_model_dump(row) or row for row in recent_rows],
        }
        if include_recovery and reentry is not None
        else {}
    )
    orientation = serialize_recovery_orientation(recovery_advice) if recovery_advice is not None else {}
    if include_recovery and reentry is not None:
        orientation["workspace_root"] = workspace_hint.as_posix()
        orientation["project_root"] = _path_text(reentry.resolved_project_root)
        orientation["project_root_source"] = _suggestion_text(reentry, "source")
        orientation["project_root_auto_selected"] = _strict_bool_value(getattr(reentry, "auto_selected", None)) is True
        orientation["project_reentry_mode"] = _suggestion_text(reentry, "mode")
        if current_project is not None:
            orientation.update(_recent_project_provenance_fields(current_project))
    surface_session_id = _current_session_id_for_surface(project_root)

    normalized_latex_capability = _normalize_latex_capability(latex_capability)

    workflow_presets = (
        resolve_workflow_preset_readiness(base_ready=base_ready, latex_capability=normalized_latex_capability)
        if include_workflow_presets
        else {}
    )

    source_meta = {
        "generated_at": _now_iso(),
        "workspace_root": workspace_hint.as_posix(),
        "project_root": project_root.as_posix(),
        "data_root": _path_text(data_root.expanduser().resolve(strict=False) if data_root is not None else None),
        "current_session_id": (
            surface_session_id if surface_session_id is not None else cost_summary.current_session_id if cost_summary is not None else None
        ),
        "active_runtime": resolved_runtime,
        "model_profile": cost_summary.model_profile if cost_summary is not None else None,
        "base_ready": base_ready,
        "latex_capability": normalized_latex_capability,
        "recent_projects_last": max(recent_projects_last, 0),
        "cost_last_sessions": max(cost_last_sessions, 0),
        "include_recovery": include_recovery,
        "include_cost": include_cost,
        "include_workflow_presets": include_workflow_presets,
    }

    execution_actions = _execution_next_actions(execution_visibility)

    next_action_parts: list[str] = [*execution_actions]
    if recovery_advice is not None:
        next_action_parts.extend(
            _recovery_next_actions(
                recovery_advice,
                existing_actions=execution_actions,
                allow_after_selection=_strict_bool_value(getattr(reentry, "auto_selected", None)) is True,
            )
        )
    if cost_summary is not None:
        if cost_advisory is not None:
            next_action = cost_advisory.get("next_action")
            if isinstance(next_action, str) and next_action.strip():
                next_action_parts.append(next_action.strip())
    if include_workflow_presets:
        next_action_parts.extend(_workflow_next_actions(base_ready=base_ready))
    next_actions = dedupe_preserve_order(next_action_parts)

    return RuntimeHintPayload(
        source_meta=source_meta,
        execution=execution,
        recovery=recovery,
        orientation=orientation,
        cost=cost,
        workflow_presets=workflow_presets,
        next_actions=next_actions,
    )
