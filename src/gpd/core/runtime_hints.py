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

from gpd.core.costs import build_cost_summary
from gpd.core.observability import derive_execution_visibility, resolve_project_root
from gpd.core.recent_projects import list_recent_projects
from gpd.core.workflow_presets import (
    _normalize_latex_capability,
    list_workflow_presets,
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
    preset_labels = ", ".join(preset.id for preset in list_workflow_presets())
    return (
        "Use `gpd presets list` to inspect the workflow preset catalog "
        f"({preset_labels}), `gpd presets show <preset>` to preview one bundle, "
        "and `gpd presets apply <preset> --dry-run` to preview the merged config "
        "before writing it."
    )


def _row_value(row: object, field: str, default: object = None) -> object:
    return getattr(row, field, default)


def _current_project_row(
    rows: list[object],
    *,
    project_root: str,
) -> dict[str, object] | None:
    for row in rows:
        if _row_value(row, "project_root") == project_root:
            return _model_dump(row)
        if isinstance(row, dict) and row.get("project_root") == project_root:
            return dict(row)
    return None


def _recovery_next_actions(recovery: dict[str, object], current_project: dict[str, object] | None) -> list[str]:
    actions: list[str] = []
    if current_project is not None:
        if bool(current_project.get("resumable")):
            actions.append("Run `gpd resume` to inspect the current recovery snapshot for this project.")
        elif current_project.get("resume_file"):
            actions.append("Run `gpd resume --recent` to rediscover a resumable project on this machine.")
    elif recovery.get("recent_projects"):
        actions.append("Run `gpd resume --recent` to rediscover a resumable project on this machine.")
    return actions


def _workflow_next_actions(details: dict[str, object], *, base_ready: bool, latex_capability: dict[str, object]) -> list[str]:
    actions: list[str] = []
    if not base_ready:
        actions.append("Fix base runtime-readiness issues before relying on workflow presets.")
    else:
        compiler_available = bool(latex_capability.get("compiler_available"))
        bibtex_available = bool(latex_capability.get("bibtex_available"))
        latexmk_available = latex_capability.get("latexmk_available")
        kpsewhich_available = latex_capability.get("kpsewhich_available")
        if not compiler_available:
            actions.append("Install or enable a LaTeX compiler to unblock publication and manuscript presets.")
        elif not bibtex_available:
            actions.append("Install or enable BibTeX support to fully unblock publication and manuscript presets.")
        if compiler_available and bibtex_available and latexmk_available is False:
            actions.append("Install latexmk to speed up paper builds; manual multipass compilation is still available.")
        if compiler_available and bibtex_available and kpsewhich_available is False:
            actions.append("Install kpsewhich/TeX resource lookup support to improve journal and class checks.")
        ready_ids = [
            str(preset.get("id"))
            for preset in details.get("presets", [])
            if isinstance(preset, dict) and preset.get("status") == "ready" and preset.get("id")
        ]
        if ready_ids:
            actions.append(f"Workflow presets ready: {', '.join(ready_ids)}.")
    return actions


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

    workspace_hint = cwd.expanduser().resolve(strict=False) if cwd is not None else Path.cwd().resolve(strict=False)
    project_root = resolve_project_root(cwd) if cwd is not None else None
    if project_root is None:
        project_root = workspace_hint

    execution_visibility = derive_execution_visibility(project_root)
    execution = _model_dump(execution_visibility)

    recent_rows = list_recent_projects(data_root, last=recent_projects_last) if include_recovery else []
    current_project = _current_project_row(recent_rows, project_root=project_root.as_posix()) if include_recovery else None
    recovery = (
        {
            "current_project": current_project,
            "recent_projects": [_model_dump(row) or row for row in recent_rows],
            "recent_projects_count": len(recent_rows),
            "resumable_projects": sum(
                1
                for row in recent_rows
                if bool(row.get("resumable") if isinstance(row, dict) else _row_value(row, "resumable", False))
            ),
            "available_projects": sum(
                1
                for row in recent_rows
                if bool(row.get("available") if isinstance(row, dict) else _row_value(row, "available", False))
            ),
        }
        if include_recovery
        else {}
    )

    cost_summary = build_cost_summary(project_root, data_root=data_root, last_sessions=cost_last_sessions) if include_cost else None
    cost = (_model_dump(cost_summary) or {}) if cost_summary is not None else {}

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

    execution_actions = []
    if execution_visibility is not None:
        execution_actions = list(execution_visibility.suggested_next_steps)

    next_action_parts: list[str] = [*execution_actions]
    if include_recovery:
        next_action_parts.extend(_recovery_next_actions(recovery, current_project))
    if cost_summary is not None:
        next_action_parts.extend(cost_summary.guidance or [])
    if include_workflow_presets:
        next_action_parts.extend(_workflow_next_actions(workflow_presets, base_ready=base_ready, latex_capability=normalized_latex_capability))
    next_actions = _dedupe_text(next_action_parts)

    return RuntimeHintPayload(
        source_meta=source_meta,
        execution=execution,
        recovery=recovery,
        cost=cost,
        workflow_presets=workflow_presets,
        next_actions=next_actions,
    )
