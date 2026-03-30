"""Shallow runtime hint payload assembly for hook and status consumers.

The helper centralizes the discoverability data already exposed by the core
execution, recovery, cost, and workflow-preset layers without introducing a
deeper schema. It is intentionally explicit so hook-facing callers can forward
one normalized payload instead of stitching together multiple summaries.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from gpd.core.context import init_resume
from gpd.core.costs import build_cost_summary, resolve_cost_advisory
from gpd.core.observability import derive_execution_visibility
from gpd.core.project_reentry import project_reentry_candidate_summary, resolve_project_reentry
from gpd.core.recent_projects import list_recent_projects
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
    resume_payload_has_local_target,
)
from gpd.core.root_resolution import normalize_workspace_hint, resolve_project_roots
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
from gpd.core.workflow_presets import (
    _normalize_latex_capability,
    resolve_workflow_preset_readiness,
)

__all__ = [
    "RuntimeHintPayload",
    "build_runtime_hint_payload",
    "workflow_preset_surface_note",
]


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
        except Exception:
            return None
        return dumped if isinstance(dumped, dict) else None
    return value if isinstance(value, dict) else None


def _dedupe_text(items: list[str]) -> list[str]:
    seen: set[str] = set()
    merged: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        merged.append(item)
    return merged


def workflow_preset_surface_note() -> str:
    """Return the shared workflow-preset surface note."""
    return _workflow_preset_surface_note_text()


def _selected_reentry_candidate(reentry: object) -> dict[str, object] | None:
    candidates = list(getattr(reentry, "candidates", []) or [])
    selected_candidate = next(
        (candidate for candidate in candidates if _suggestion_text(candidate, "source") == "current_workspace"),
        getattr(reentry, "selected_candidate", None),
    )
    candidate_payload = _model_dump(selected_candidate)
    if not isinstance(candidate_payload, dict):
        return None
    summary = project_reentry_candidate_summary(selected_candidate)
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
    auto_selected = bool(getattr(reentry, "auto_selected", False))
    requires_selection = bool(getattr(reentry, "requires_user_selection", False))
    mode = _suggestion_text(reentry, "mode")
    candidates = list(getattr(reentry, "candidates", []) or [])
    recent_candidates = [candidate for candidate in candidates if _suggestion_text(candidate, "source") == "recent_project"]

    def _candidate_bool(candidate: object, field: str) -> bool:
        if isinstance(candidate, dict):
            return bool(candidate.get(field))
        return bool(getattr(candidate, field, False))

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
        and not bool(current_project.get("recoverable"))
        and (recent_candidates or _recent_project_summary(current_project) is not None)
    ):
        if any(_candidate_bool(candidate, "resumable") for candidate in recent_candidates):
            return "GPD found recent projects on this machine, but none are selected automatically."
        return "GPD found recent projects on this machine, but none are ready to reopen automatically."
    if mode == "recent-projects":
        if current_project is not None and bool(current_project.get("resumable")):
            return "GPD found recent projects on this machine, but none are selected automatically."
        return "GPD found recent projects on this machine, but none are ready to reopen automatically."
    if recovery_reason is not None:
        return recovery_reason
    return None


def _runtime_command(action: str, *, cwd: Path) -> str | None:
    try:
        from gpd.adapters import get_adapter
        from gpd.hooks.runtime_detect import detect_runtime_for_gpd_use

        runtime_name = detect_runtime_for_gpd_use(cwd=cwd)
        return str(get_adapter(runtime_name).format_command(action)).strip()
    except Exception:
        return None


def _resume_context(cwd: Path, *, data_root: Path | None = None) -> dict[str, object]:
    payload = init_resume(cwd, data_root=data_root)
    return payload if isinstance(payload, dict) else {}


def _recent_project_resume_family(
    current_project: dict[str, object],
) -> tuple[str, str]:
    resume_target_kind = _normalized_row_text(current_project, "resume_target_kind")
    if resume_target_kind == "bounded_segment":
        return (
            RESUME_CANDIDATE_KIND_BOUNDED_SEGMENT,
            RESUME_CANDIDATE_ORIGIN_CONTINUATION_BOUNDED_SEGMENT,
        )
    return (
        RESUME_CANDIDATE_KIND_CONTINUITY_HANDOFF,
        RESUME_CANDIDATE_ORIGIN_CONTINUATION_HANDOFF,
    )


def _resume_context_has_local_target(payload: dict[str, object]) -> bool:
    """Return whether one resume payload already exposes a local recovery target."""
    return resume_payload_has_local_target(payload)


def _hydrate_resume_context_from_recent_project(
    payload: dict[str, object],
    *,
    reentry: object,
    current_project: dict[str, object] | None,
) -> dict[str, object]:
    """Fill the selected-recent-project resume gap when local state has not been loaded yet."""
    if not bool(getattr(reentry, "auto_selected", False)):
        return payload
    if current_project is None:
        return payload
    if _resume_context_has_local_target(payload):
        return payload

    resume_file = current_project.get("resume_file")
    if not isinstance(resume_file, str) or not resume_file.strip():
        return payload
    resume_file = resume_file.strip()
    resume_file_available = bool(current_project.get("resume_file_available"))
    candidate_status = "handoff" if resume_file_available else "missing"
    hydration_kind, hydration_origin = _recent_project_resume_family(current_project)

    hydrated = dict(payload)
    hydrated.setdefault("project_root", current_project.get("project_root"))
    hydrated.setdefault("project_root_source", "recent_project")
    hydrated.setdefault("project_root_auto_selected", True)
    hydrated.setdefault("project_reentry_mode", getattr(reentry, "mode", None))
    if not str(hydrated.get("active_resume_kind") or "").strip():
        hydrated["active_resume_kind"] = hydration_kind
    if not str(hydrated.get("active_resume_origin") or "").strip():
        hydrated["active_resume_origin"] = hydration_origin
    if not str(hydrated.get("active_resume_pointer") or "").strip():
        hydrated["active_resume_pointer"] = resume_file
    if hydration_kind == RESUME_CANDIDATE_KIND_CONTINUITY_HANDOFF and resume_file_available:
        if not str(hydrated.get("continuity_handoff_file") or "").strip():
            hydrated["continuity_handoff_file"] = resume_file
        hydrated["has_continuity_handoff"] = True
        if not str(hydrated.get("recorded_continuity_handoff_file") or "").strip():
            hydrated["recorded_continuity_handoff_file"] = resume_file
    elif not resume_file_available:
        if not str(hydrated.get("missing_continuity_handoff_file") or "").strip():
            hydrated["missing_continuity_handoff_file"] = resume_file

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
    if any("`gpd resume`" in action for action in existing):
        actions = [
            action
            for action in actions
            if not (str(action.kind) == "primary" and str(action.command) == "gpd resume")
        ]
    return recovery_action_lines(
        actions=actions,
        mode=advice.mode,
        existing_actions=existing,
        allowed_availability={"now", "after_selection"} if allow_after_selection else {"now"},
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
    latex_available: bool | None = None,
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
    reentry = resolve_project_reentry(workspace_hint, data_root=data_root)
    resolution = resolve_project_roots(workspace_hint)
    project_root = (
        reentry.resolved_project_root
        or (resolution.project_root if resolution is not None else workspace_hint)
    )

    execution_visibility = derive_execution_visibility(project_root)
    execution = _model_dump(execution_visibility)

    recent_rows = list_recent_projects(data_root, last=recent_projects_last) if include_recovery else []
    current_project = _selected_reentry_candidate(reentry) if include_recovery else None
    resume_context = _resume_context(workspace_hint, data_root=data_root) if include_recovery else {}
    if include_recovery:
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
        has_recent_project_candidate = any(
            _suggestion_text(candidate_payload, "source") == "recent_project"
            for candidate_payload in candidate_payloads
        )
        if isinstance(resume_context, dict):
            if candidate_payloads and (has_recent_project_candidate or not recent_rows):
                resume_context["project_reentry_candidates"] = candidate_payloads
                selected_payload = _model_dump(getattr(reentry, "selected_candidate", None))
                if isinstance(selected_payload, dict):
                    resume_context["project_reentry_selected_candidate"] = selected_payload
                else:
                    resume_context.pop("project_reentry_selected_candidate", None)
            else:
                resume_context.pop("project_reentry_candidates", None)
                resume_context.pop("project_reentry_selected_candidate", None)
    recovery_advice = (
        build_recovery_advice(
            project_root,
            data_root=data_root,
            recent_rows=recent_rows,
            resume_payload=resume_context,
            continue_command=_runtime_command("resume-work", cwd=project_root),
            fast_next_command=_runtime_command("suggest-next", cwd=project_root),
        )
        if include_recovery
        else None
    )
    recovery = (
        {
            "current_project": (
                {**current_project, "summary": _selected_project_summary(reentry, current_project)}
                if current_project is not None
                else None
            ),
            "current_project_summary": _selected_project_summary(reentry, current_project),
            "project_reentry": _model_dump(reentry),
            "project_reentry_summary": _project_reentry_summary(
                reentry,
                current_project,
                recovery_reason=recovery_advice.project_reentry_reason if recovery_advice is not None else None,
            ),
            "recent_projects": [_model_dump(row) or row for row in recent_rows],
        }
        if include_recovery
        else {}
    )
    orientation = serialize_recovery_orientation(recovery_advice) if recovery_advice is not None else {}
    if include_recovery:
        orientation["workspace_root"] = workspace_hint.as_posix()
        orientation["project_root"] = _path_text(reentry.resolved_project_root)
        orientation["project_root_source"] = reentry.source
        orientation["project_root_auto_selected"] = bool(reentry.auto_selected)
        orientation["project_reentry_mode"] = reentry.mode
    cost_summary = build_cost_summary(project_root, data_root=data_root, last_sessions=cost_last_sessions) if include_cost else None
    cost = _cost_payload(cost_summary) if cost_summary is not None else {}
    cost_advisory = _cost_advisory(cost_summary) if cost_summary is not None else None
    if cost_advisory is not None:
        cost["advisory"] = cost_advisory

    normalized_latex_capability = _normalize_latex_capability(latex_capability, legacy_available=latex_available)

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
        "current_session_id": cost_summary.current_session_id if cost_summary is not None else None,
        "active_runtime": cost_summary.active_runtime if cost_summary is not None else None,
        "model_profile": cost_summary.model_profile if cost_summary is not None else None,
        "base_ready": base_ready,
        "latex_capability": normalized_latex_capability,
        "latex_available": bool(normalized_latex_capability.get("compiler_available")),
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
                allow_after_selection=bool(getattr(reentry, "auto_selected", False)),
            )
        )
    if cost_summary is not None:
        if cost_advisory is not None:
            next_action = cost_advisory.get("next_action")
            if isinstance(next_action, str) and next_action.strip():
                next_action_parts.append(next_action.strip())
    if include_workflow_presets:
        next_action_parts.extend(_workflow_next_actions(base_ready=base_ready))
    next_actions = _dedupe_text(next_action_parts)

    return RuntimeHintPayload(
        source_meta=source_meta,
        execution=execution,
        recovery=recovery,
        orientation=orientation,
        cost=cost,
        workflow_presets=workflow_presets,
        next_actions=next_actions,
    )
