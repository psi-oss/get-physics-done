"""Shared project re-entry resolution for recovery-oriented GPD surfaces.

This layer sits above low-level root resolution and recent-project discovery.
It answers one question: given the current workspace, can GPD safely recover a
project root to continue from, and if not, why not?
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from gpd.core.constants import ProjectLayout
from gpd.core.recent_projects import (
    _strict_bool_value,
    classify_recent_project_recovery,
    list_recent_projects,
)
from gpd.core.root_resolution import (
    RootResolutionConfidence,
    normalize_workspace_hint,
    resolve_project_roots,
)

__all__ = [
    "ProjectReentryCandidate",
    "ProjectReentryResolution",
    "project_reentry_candidate_summary",
    "recoverable_project_context",
    "resolve_project_reentry",
]


class ProjectReentryCandidate(BaseModel):
    """One possible project root for projectless recovery."""

    model_config = ConfigDict(frozen=True)

    source: str
    project_root: str
    available: bool
    recoverable: bool
    resumable: bool
    confidence: str
    reason: str
    summary: str | None = None
    state_exists: bool = False
    roadmap_exists: bool = False
    project_exists: bool = False
    resume_file: str | None = None
    last_result_id: str | None = None
    resume_target_kind: str | None = None
    resume_target_recorded_at: str | None = None
    resume_file_available: bool | None = None
    resume_file_reason: str | None = None
    hostname: str | None = None
    platform: str | None = None
    availability_reason: str | None = None
    last_session_at: str | None = None
    stopped_at: str | None = None
    source_kind: str | None = None
    source_session_id: str | None = None
    source_segment_id: str | None = None
    source_transition_id: str | None = None
    source_recorded_at: str | None = None
    recovery_phase: str | None = None
    recovery_plan: str | None = None
    auto_selectable: bool = False

class ProjectReentryResolution(BaseModel):
    """Shared re-entry decision payload for recovery/status commands."""

    model_config = ConfigDict(frozen=True)

    workspace_root: str | None = None
    project_root: str | None = None
    source: str | None = None
    mode: str = "no-recovery"
    auto_selected: bool = False
    requires_user_selection: bool = False
    has_current_workspace_candidate: bool = False
    has_recoverable_current_workspace: bool = False
    recoverable_candidates_count: int = 0
    candidates: list[ProjectReentryCandidate] = Field(default_factory=list)

    @property
    def resolved_project_root(self) -> Path | None:
        if not isinstance(self.project_root, str) or not self.project_root.strip():
            return None
        return Path(self.project_root).expanduser().resolve(strict=False)

    @property
    def selected_candidate(self) -> ProjectReentryCandidate | None:
        if not isinstance(self.project_root, str) or not self.project_root.strip():
            return None
        selected_root = self.project_root.strip()
        if isinstance(self.source, str) and self.source.strip():
            selected_source = self.source.strip()
            for candidate in self.candidates:
                if candidate.project_root == selected_root and candidate.source == selected_source:
                    return candidate
        return next((candidate for candidate in self.candidates if candidate.project_root == selected_root), None)

def recoverable_project_context(project_root: Path) -> tuple[bool, bool, bool]:
    """Return whether a project root has enough durable state for recovery.

    This helper is read-only. It can inspect state snapshots to determine
    recoverability, but it must not trigger intent recovery or mutate the
    workspace while discovery is running.
    """

    layout = ProjectLayout(project_root)
    state_files_exist = any(path.exists() for path in (layout.state_json, layout.state_json_backup, layout.state_md))
    state_exists = False
    if state_files_exist:
        from gpd.core.state import peek_state_json

        try:
            state_obj, _integrity_issues, _state_source = peek_state_json(
                project_root,
                recover_intent=False,
                surface_blocked_project_contract=True,
                acquire_lock=False,
            )
        except OSError:
            state_obj = None
        state_exists = isinstance(state_obj, dict)
    roadmap_exists = layout.roadmap.exists()
    project_exists = layout.project_md.exists()
    return state_exists, roadmap_exists, project_exists


def _summary_value(candidate: ProjectReentryCandidate | Mapping[str, object] | None, field: str) -> object:
    if candidate is None:
        return None
    if isinstance(candidate, Mapping):
        return candidate.get(field)
    return getattr(candidate, field, None)


def _summary_text(candidate: ProjectReentryCandidate | Mapping[str, object] | None, *fields: str) -> str | None:
    for field in fields:
        value = _summary_value(candidate, field)
        if not isinstance(value, str):
            continue
        stripped = value.strip()
        if stripped:
            return stripped
    return None


def project_reentry_candidate_summary(
    candidate: ProjectReentryCandidate | Mapping[str, object] | None,
) -> str | None:
    if candidate is None:
        return None

    bits: list[str] = []
    last_seen = _summary_text(candidate, "last_session_at", "last_seen_at")
    stopped_at = _summary_text(candidate, "stopped_at")
    hostname = _summary_text(candidate, "hostname")
    platform = _summary_text(candidate, "platform")
    resume_file_reason = _summary_text(candidate, "resume_file_reason")
    availability_reason = _summary_text(candidate, "availability_reason")

    if last_seen is not None:
        bits.append(f"last seen {last_seen}")
    if stopped_at is not None:
        bits.append(f"stopped at {stopped_at}")
    if hostname is not None and platform is not None:
        bits.append(f"on {hostname} ({platform})")
    elif hostname is not None:
        bits.append(f"on {hostname}")
    elif platform is not None:
        bits.append(f"on {platform}")

    resumable = _strict_bool_value(_summary_value(candidate, "resumable")) is True
    if resumable:
        bits.append("resume file ready")
    elif resume_file_reason is not None:
        bits.append(resume_file_reason)
    elif availability_reason is not None:
        bits.append(availability_reason)

    if not bits:
        return None
    return "; ".join(bits)


def _candidate_sort_key(candidate: ProjectReentryCandidate) -> tuple[int, int, int, int, int, str, str]:
    recovery = classify_recent_project_recovery(candidate)
    source_rank = 0
    if candidate.source == "current_workspace":
        source_rank = 3
    elif _candidate_has_concrete_target(candidate):
        source_rank = 2
    elif candidate.recoverable:
        source_rank = 1

    return (
        source_rank,
        recovery.target_priority,
        1 if _candidate_has_concrete_target(candidate) else 0,
        1 if candidate.resumable else 0,
        1 if candidate.available else 0,
        recovery.resume_target_recorded_at or candidate.source_recorded_at or candidate.last_session_at or "",
        candidate.project_root,
    )


def _candidate_has_concrete_target(candidate: ProjectReentryCandidate) -> bool:
    if candidate.source == "current_workspace":
        return candidate.recoverable
    if not candidate.recoverable:
        return False
    if candidate.resume_file is None:
        return False
    if candidate.resume_file_available is False:
        return False
    return candidate.resumable or candidate.resume_file_available is True


def _current_workspace_is_verified(candidate: ProjectReentryCandidate | None) -> bool:
    return candidate is not None and candidate.source == "current_workspace" and candidate.project_exists is True


def _normalize_recent_text(row: Mapping[str, object], *keys: str) -> str | None:
    for key in keys:
        value = row.get(key)
        if not isinstance(value, str):
            continue
        stripped = value.strip()
        if stripped:
            return stripped
    return None


def _recent_project_summary(row: Mapping[str, object]) -> str | None:
    return project_reentry_candidate_summary(row)


def _candidate_from_recent_row(row: Mapping[str, object]) -> ProjectReentryCandidate | None:
    project_root_text = _normalize_recent_text(row, "project_root")
    if project_root_text is None:
        return None

    project_root = Path(project_root_text).expanduser().resolve(strict=False)
    state_exists, roadmap_exists, project_exists = recoverable_project_context(project_root)
    available_value = row.get("available")
    if available_value is None:
        available = project_root.is_dir()
    else:
        available = _strict_bool_value(available_value) is True
    recoverable = available and (state_exists or roadmap_exists or project_exists)
    resume_file = _normalize_recent_text(row, "resume_file")
    resume_file_available = _strict_bool_value(row.get("resume_file_available"))
    resumable = _strict_bool_value(row.get("resumable")) is True or resume_file_available is True
    recovery = classify_recent_project_recovery(row)
    candidate = ProjectReentryCandidate(
        source="recent_project",
        project_root=project_root.as_posix(),
        available=available,
        recoverable=recoverable,
        resumable=resumable,
        confidence="medium" if recoverable else "low",
        reason="recent project cache entry",
        summary=_recent_project_summary(row),
        state_exists=state_exists,
        roadmap_exists=roadmap_exists,
        project_exists=project_exists,
        resume_file=resume_file,
        last_result_id=_normalize_recent_text(row, "last_result_id"),
        resume_target_kind=recovery.resume_target_kind,
        resume_target_recorded_at=recovery.resume_target_recorded_at,
        resume_file_available=resume_file_available,
        resume_file_reason=_normalize_recent_text(row, "resume_file_reason"),
        hostname=_normalize_recent_text(row, "hostname"),
        platform=_normalize_recent_text(row, "platform"),
        availability_reason=_normalize_recent_text(row, "availability_reason"),
        last_session_at=_normalize_recent_text(row, "last_session_at", "last_seen_at"),
        stopped_at=_normalize_recent_text(row, "stopped_at"),
        source_kind=_normalize_recent_text(row, "source_kind"),
        source_session_id=_normalize_recent_text(row, "source_session_id"),
        source_segment_id=_normalize_recent_text(row, "source_segment_id"),
        source_transition_id=_normalize_recent_text(row, "source_transition_id"),
        source_recorded_at=_normalize_recent_text(row, "source_recorded_at"),
        recovery_phase=_normalize_recent_text(row, "recovery_phase"),
        recovery_plan=_normalize_recent_text(row, "recovery_plan"),
    )
    concrete_target = _candidate_has_concrete_target(candidate)
    return candidate.model_copy(
        update={
            "confidence": "high" if concrete_target else "medium" if recoverable else "low",
            "reason": recovery.candidate_reason(recoverable=recoverable),
            "summary": _recent_project_summary(row),
        }
    )


def _current_workspace_candidate(workspace: Path | None) -> ProjectReentryCandidate | None:
    resolution = resolve_project_roots(workspace)
    if resolution is None:
        return None

    project_root = resolution.project_root.expanduser().resolve(strict=False)
    state_exists, roadmap_exists, project_exists = recoverable_project_context(project_root)
    recoverable = state_exists or roadmap_exists or project_exists
    if not recoverable:
        return None

    if resolution.basis == "workspace" and resolution.has_project_layout and resolution.walk_up_steps > 0:
        reason = "workspace resolved to ancestor project root"
    elif resolution.has_project_layout and not project_exists and recoverable:
        reason = "workspace carries partial recoverable GPD state"
    elif resolution.has_project_layout:
        reason = "workspace already points at a GPD project"
    else:
        reason = "workspace carries partial recoverable GPD state"

    return ProjectReentryCandidate(
        source="current_workspace",
        project_root=project_root.as_posix(),
        available=project_root.is_dir(),
        recoverable=recoverable,
        resumable=False,
        confidence=resolution.confidence.value if isinstance(resolution.confidence, RootResolutionConfidence) else str(resolution.confidence),
        reason=reason,
        summary=reason,
        state_exists=state_exists,
        roadmap_exists=roadmap_exists,
        project_exists=project_exists,
    )


def resolve_project_reentry(
    workspace: Path | str | None,
    *,
    data_root: Path | None = None,
    recent_rows: Sequence[Mapping[str, object] | object] | None = None,
) -> ProjectReentryResolution:
    """Resolve the shared re-entry decision for one workspace."""

    workspace_root = normalize_workspace_hint(workspace)
    current_candidate = _current_workspace_candidate(workspace_root)

    seen_roots: set[str] = set()
    candidates: list[ProjectReentryCandidate] = []
    if current_candidate is not None:
        candidates.append(current_candidate)
        seen_roots.add(current_candidate.project_root)

    if recent_rows is None:
        recent_project_rows = [] if current_candidate is not None else list_recent_projects(data_root)
    else:
        recent_project_rows = list(recent_rows)
    for row in recent_project_rows:
        row_payload = row.model_dump(mode="json") if hasattr(row, "model_dump") else row
        if not isinstance(row_payload, Mapping):
            continue
        candidate = _candidate_from_recent_row(row_payload)
        if candidate is None:
            continue
        if candidate.project_root in seen_roots:
            continue
        candidates.append(candidate)
        seen_roots.add(candidate.project_root)

    recent_candidates = [candidate for candidate in candidates if candidate.source == "recent_project"]
    strong_recent = [candidate for candidate in recent_candidates if _candidate_has_concrete_target(candidate)]

    selected_project_root: str | None = None
    selected_source: str | None = None
    mode = "no-recovery"
    auto_selected = False
    requires_user_selection = False

    if _current_workspace_is_verified(current_candidate):
        selected_project_root = current_candidate.project_root
        selected_source = current_candidate.source
        mode = "current-workspace"
    elif len(strong_recent) == 1:
        auto_candidate = strong_recent[0]
        selected_project_root = auto_candidate.project_root
        selected_source = auto_candidate.source
        mode = "auto-recent-project"
        auto_selected = True
    elif len(strong_recent) > 1:
        mode = "ambiguous-recent-projects"
        requires_user_selection = True
    elif current_candidate is not None:
        selected_project_root = current_candidate.project_root
        selected_source = current_candidate.source
        mode = "current-workspace"
    elif recent_candidates:
        mode = "recent-projects"

    auto_selectable_roots = {selected_project_root} if auto_selected and selected_project_root is not None else set()
    normalized_candidates = [
        candidate.model_copy(update={"auto_selectable": candidate.project_root in auto_selectable_roots})
        for candidate in sorted(candidates, key=_candidate_sort_key, reverse=True)
    ]

    if selected_project_root is not None and selected_source is not None:
        for index, candidate in enumerate(normalized_candidates):
            if candidate.project_root == selected_project_root and candidate.source == selected_source:
                if index != 0:
                    selected_candidate = normalized_candidates.pop(index)
                    normalized_candidates.insert(0, selected_candidate)
                break

    return ProjectReentryResolution(
        workspace_root=workspace_root.as_posix() if workspace_root is not None else None,
        project_root=selected_project_root,
        source=selected_source,
        mode=mode,
        auto_selected=auto_selected,
        requires_user_selection=requires_user_selection,
        has_current_workspace_candidate=current_candidate is not None,
        has_recoverable_current_workspace=bool(current_candidate and current_candidate.recoverable),
        recoverable_candidates_count=sum(1 for candidate in normalized_candidates if candidate.recoverable),
        candidates=normalized_candidates,
    )
