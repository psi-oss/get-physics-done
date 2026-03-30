from __future__ import annotations

from pathlib import Path

from gpd.core.project_reentry import resolve_project_reentry


def _make_gpd_workspace(
    root: Path,
    *,
    project: bool = False,
    roadmap: bool = False,
    state: bool = False,
) -> Path:
    gpd_dir = root / "GPD"
    gpd_dir.mkdir(parents=True, exist_ok=True)
    if project:
        (gpd_dir / "PROJECT.md").write_text("# Project\n", encoding="utf-8")
    if roadmap:
        (gpd_dir / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
    if state:
        (gpd_dir / "STATE.md").write_text("# State\n", encoding="utf-8")
    return root


def _recent_row(
    project_root: Path,
    *,
    last_session_at: str,
    resumable: bool = True,
    resume_target_kind: str = "handoff",
    resume_target_recorded_at: str | None = None,
) -> dict[str, object]:
    recorded_at = resume_target_recorded_at or last_session_at
    row: dict[str, object] = {
        "project_root": project_root.resolve(strict=False).as_posix(),
        "last_session_at": last_session_at,
        "stopped_at": "Phase 02",
        "resume_file": "GPD/phases/02/.continue-here.md",
        "resume_target_kind": resume_target_kind,
        "resume_target_recorded_at": recorded_at,
        "resume_file_available": True,
        "resume_file_reason": None,
        "available": True,
        "resumable": resumable,
    }
    if resume_target_kind == "bounded_segment":
        row.update(
            {
                "source_kind": "continuation.bounded_segment",
                "source_segment_id": f"segment-{project_root.name}",
                "source_transition_id": f"transition-{project_root.name}",
                "source_recorded_at": last_session_at,
                "recovery_phase": "02",
                "recovery_plan": "01",
            }
        )
    elif resume_target_kind == "handoff":
        row.update(
            {
                "source_kind": "continuation.handoff",
                "source_recorded_at": last_session_at,
            }
        )
    return row


def test_resolve_project_reentry_prefers_current_workspace_recovery(tmp_path: Path) -> None:
    workspace = _make_gpd_workspace(tmp_path / "workspace", project=True)

    resolution = resolve_project_reentry(workspace, recent_rows=[])

    assert resolution.mode == "current-workspace"
    assert resolution.source == "current_workspace"
    assert resolution.auto_selected is False
    assert resolution.requires_user_selection is False
    assert resolution.has_current_workspace_candidate is True
    assert resolution.has_recoverable_current_workspace is True
    assert resolution.project_root == workspace.resolve(strict=False).as_posix()
    assert resolution.recoverable_candidates_count == 1
    assert len(resolution.candidates) == 1
    assert resolution.selected_candidate is not None
    assert resolution.selected_candidate.source == "current_workspace"
    assert resolution.selected_candidate.project_root == workspace.resolve(strict=False).as_posix()
    assert resolution.candidates[0].source == "current_workspace"
    assert resolution.candidates[0].recoverable is True
    assert resolution.candidates[0].project_exists is True


def test_resolve_project_reentry_walks_up_to_ancestor_project_root(tmp_path: Path) -> None:
    project = _make_gpd_workspace(tmp_path / "project", project=True)
    nested = project / "src" / "notes"
    nested.mkdir(parents=True)

    resolution = resolve_project_reentry(nested, recent_rows=[])

    assert resolution.mode == "current-workspace"
    assert resolution.source == "current_workspace"
    assert resolution.has_current_workspace_candidate is True
    assert resolution.has_recoverable_current_workspace is True
    assert resolution.project_root == project.resolve(strict=False).as_posix()
    assert resolution.recoverable_candidates_count == 1
    assert len(resolution.candidates) == 1
    assert resolution.candidates[0].reason == "workspace resolved to ancestor project root"
    assert resolution.candidates[0].project_root == project.resolve(strict=False).as_posix()


def test_resolve_project_reentry_surfaces_partial_recoverable_workspace(tmp_path: Path) -> None:
    workspace = _make_gpd_workspace(tmp_path / "workspace", roadmap=True, state=True)

    resolution = resolve_project_reentry(workspace, recent_rows=[])

    assert resolution.mode == "current-workspace"
    assert resolution.source == "current_workspace"
    assert resolution.has_current_workspace_candidate is True
    assert resolution.has_recoverable_current_workspace is True
    assert resolution.project_root == workspace.resolve(strict=False).as_posix()
    assert resolution.recoverable_candidates_count == 1
    assert len(resolution.candidates) == 1
    assert resolution.candidates[0].reason == "workspace carries partial recoverable GPD state"
    assert resolution.candidates[0].project_exists is False
    assert resolution.candidates[0].roadmap_exists is True
    assert resolution.candidates[0].state_exists is True


def test_resolve_project_reentry_auto_selects_unique_recoverable_recent_project(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    project = _make_gpd_workspace(tmp_path / "recent-project", project=True)

    resolution = resolve_project_reentry(
        workspace,
        recent_rows=[
            _recent_row(
                project,
                last_session_at="2026-03-28T12:00:00+00:00",
            )
        ],
    )

    assert resolution.mode == "auto-recent-project"
    assert resolution.source == "recent_project"
    assert resolution.auto_selected is True
    assert resolution.requires_user_selection is False
    assert resolution.has_current_workspace_candidate is False
    assert resolution.has_recoverable_current_workspace is False
    assert resolution.project_root == project.resolve(strict=False).as_posix()
    assert resolution.recoverable_candidates_count == 1
    assert len(resolution.candidates) == 1
    assert resolution.selected_candidate is not None
    assert resolution.selected_candidate.source == "recent_project"
    assert resolution.selected_candidate.project_root == project.resolve(strict=False).as_posix()
    assert resolution.selected_candidate.summary == "last seen 2026-03-28T12:00:00+00:00; stopped at Phase 02; resume file ready"
    assert resolution.candidates[0].source == "recent_project"
    assert resolution.candidates[0].auto_selectable is True
    assert resolution.candidates[0].recoverable is True
    assert resolution.candidates[0].resume_target_kind == "handoff"
    assert resolution.candidates[0].reason == "recent project cache entry with projected continuity handoff"


def test_resolve_project_reentry_exposes_selected_candidate_metadata_for_bounded_segment_recent_project(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    project = _make_gpd_workspace(tmp_path / "recent-bounded", project=True)

    resolution = resolve_project_reentry(
        workspace,
        recent_rows=[
            _recent_row(
                project,
                last_session_at="2026-03-28T12:00:00+00:00",
                resume_target_kind="bounded_segment",
            )
        ],
    )

    assert resolution.mode == "auto-recent-project"
    assert resolution.source == "recent_project"
    assert resolution.selected_candidate is not None
    assert resolution.selected_candidate.project_root == project.resolve(strict=False).as_posix()
    assert resolution.selected_candidate.source == "recent_project"
    assert resolution.selected_candidate.auto_selectable is True
    assert resolution.selected_candidate.resume_target_kind == "bounded_segment"
    assert resolution.selected_candidate.resume_target_recorded_at == "2026-03-28T12:00:00+00:00"
    assert resolution.selected_candidate.summary == "last seen 2026-03-28T12:00:00+00:00; stopped at Phase 02; resume file ready"
    assert resolution.selected_candidate.source_kind == "continuation.bounded_segment"
    assert resolution.selected_candidate.source_segment_id == f"segment-{project.name}"
    assert resolution.selected_candidate.source_transition_id == f"transition-{project.name}"
    assert resolution.selected_candidate.recovery_phase == "02"
    assert resolution.selected_candidate.recovery_plan == "01"


def test_resolve_project_reentry_leaves_selected_candidate_empty_for_missing_handoff_only_recent_project(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    project = _make_gpd_workspace(tmp_path / "recent-missing-handoff", project=True)

    resolution = resolve_project_reentry(
        workspace,
        recent_rows=[
            {
                **_recent_row(
                    project,
                    last_session_at="2026-03-28T12:00:00+00:00",
                    resumable=False,
                ),
                "resume_file": None,
                "resume_file_available": False,
            }
        ],
    )

    assert resolution.mode == "recent-projects"
    assert resolution.source is None
    assert resolution.project_root is None
    assert resolution.selected_candidate is None
    assert resolution.recoverable_candidates_count == 1
    assert len(resolution.candidates) == 1
    assert resolution.candidates[0].source == "recent_project"
    assert resolution.candidates[0].resume_target_kind == "handoff"
    assert resolution.candidates[0].resume_file is None
    assert resolution.candidates[0].resume_file_available is False
    assert resolution.candidates[0].auto_selectable is False


def test_resolve_project_reentry_enriches_current_workspace_selected_candidate_from_matching_recent_row(
    tmp_path: Path,
) -> None:
    workspace = _make_gpd_workspace(tmp_path / "workspace", project=True)

    resolution = resolve_project_reentry(
        workspace,
        recent_rows=[
            {
                **_recent_row(workspace, last_session_at="2026-03-28T12:00:00+00:00"),
                "hostname": "builder-01",
                "platform": "Linux 6.1 x86_64",
            }
        ],
    )

    assert resolution.mode == "current-workspace"
    assert resolution.source == "current_workspace"
    assert len(resolution.candidates) == 1
    assert resolution.selected_candidate is not None
    assert resolution.selected_candidate.source == "current_workspace"
    assert resolution.selected_candidate.project_root == workspace.resolve(strict=False).as_posix()
    assert resolution.selected_candidate.resume_file == "GPD/phases/02/.continue-here.md"
    assert resolution.selected_candidate.resume_target_kind == "handoff"
    assert resolution.selected_candidate.resume_file_available is True
    assert resolution.selected_candidate.resumable is True
    assert resolution.selected_candidate.hostname == "builder-01"
    assert resolution.selected_candidate.platform == "Linux 6.1 x86_64"


def test_resolve_project_reentry_prefers_unique_strong_recent_candidate_over_weak_recent_candidate(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    strong = _make_gpd_workspace(tmp_path / "recent-strong", project=True)
    weak = _make_gpd_workspace(tmp_path / "recent-weak", project=True)

    resolution = resolve_project_reentry(
        workspace,
        recent_rows=[
            {
                **_recent_row(weak, last_session_at="2026-03-28T14:00:00+00:00"),
                "resume_file": None,
                "resume_file_available": False,
                "resumable": False,
            },
            _recent_row(
                strong,
                last_session_at="2026-03-28T15:00:00+00:00",
            ),
        ],
    )

    assert resolution.mode == "auto-recent-project"
    assert resolution.source == "recent_project"
    assert resolution.auto_selected is True
    assert resolution.requires_user_selection is False
    assert resolution.project_root == strong.resolve(strict=False).as_posix()
    assert resolution.candidates[0].project_root == strong.resolve(strict=False).as_posix()
    assert resolution.candidates[0].auto_selectable is True
    assert resolution.candidates[0].confidence == "high"
    assert resolution.candidates[0].resume_target_kind == "handoff"
    assert resolution.candidates[1].project_root == weak.resolve(strict=False).as_posix()
    assert resolution.candidates[1].auto_selectable is False
    assert resolution.candidates[1].confidence == "medium"


def test_resolve_project_reentry_keeps_sole_weak_recent_project_explicit(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    weak = _make_gpd_workspace(tmp_path / "recent-weak", project=True)

    resolution = resolve_project_reentry(
        workspace,
        recent_rows=[
            {
                **_recent_row(weak, last_session_at="2026-03-28T15:00:00+00:00"),
                "resume_file": None,
                "resume_file_available": False,
                "resumable": False,
            }
        ],
    )

    assert resolution.mode == "recent-projects"
    assert resolution.source is None
    assert resolution.auto_selected is False
    assert resolution.requires_user_selection is False
    assert resolution.project_root is None
    assert resolution.recoverable_candidates_count == 1
    assert len(resolution.candidates) == 1
    assert resolution.candidates[0].project_root == weak.resolve(strict=False).as_posix()
    assert resolution.candidates[0].auto_selectable is False
    assert resolution.candidates[0].confidence == "medium"


def test_resolve_project_reentry_requires_user_selection_for_ambiguous_recent_projects(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    first = _make_gpd_workspace(tmp_path / "recent-a", project=True)
    second = _make_gpd_workspace(tmp_path / "recent-b", project=True)

    resolution = resolve_project_reentry(
        workspace,
        recent_rows=[
            _recent_row(first, last_session_at="2026-03-28T12:00:00+00:00"),
            _recent_row(second, last_session_at="2026-03-28T13:00:00+00:00"),
        ],
    )

    assert resolution.mode == "ambiguous-recent-projects"
    assert resolution.source is None
    assert resolution.auto_selected is False
    assert resolution.requires_user_selection is True
    assert resolution.project_root is None
    assert resolution.recoverable_candidates_count == 2
    assert len(resolution.candidates) == 2
    assert all(candidate.source == "recent_project" for candidate in resolution.candidates)
    assert all(candidate.auto_selectable is False for candidate in resolution.candidates)
    assert resolution.candidates[0].last_session_at == "2026-03-28T13:00:00+00:00"
    assert resolution.candidates[1].last_session_at == "2026-03-28T12:00:00+00:00"


def test_resolve_project_reentry_orders_recent_projects_by_canonical_recorded_at(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    older_session_newer_recorded = _make_gpd_workspace(tmp_path / "recent-newer-recorded", project=True)
    newer_session_older_recorded = _make_gpd_workspace(tmp_path / "recent-older-recorded", project=True)

    resolution = resolve_project_reentry(
        workspace,
        recent_rows=[
            _recent_row(
                newer_session_older_recorded,
                last_session_at="2026-03-28T14:00:00+00:00",
                resume_target_recorded_at="2026-03-28T12:00:00+00:00",
            ),
            _recent_row(
                older_session_newer_recorded,
                last_session_at="2026-03-28T12:00:00+00:00",
                resume_target_recorded_at="2026-03-28T15:00:00+00:00",
            ),
        ],
    )

    assert resolution.mode == "ambiguous-recent-projects"
    assert resolution.candidates[0].project_root == older_session_newer_recorded.resolve(strict=False).as_posix()
    assert resolution.candidates[0].resume_target_recorded_at == "2026-03-28T15:00:00+00:00"
    assert resolution.candidates[1].project_root == newer_session_older_recorded.resolve(strict=False).as_posix()
    assert resolution.candidates[1].resume_target_recorded_at == "2026-03-28T12:00:00+00:00"


def test_resolve_project_reentry_orders_bounded_recent_target_ahead_of_handoff_without_auto_selecting(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    bounded = _make_gpd_workspace(tmp_path / "recent-bounded", project=True)
    handoff = _make_gpd_workspace(tmp_path / "recent-handoff", project=True)

    resolution = resolve_project_reentry(
        workspace,
        recent_rows=[
            _recent_row(
                handoff,
                last_session_at="2026-03-28T13:00:00+00:00",
                resume_target_kind="handoff",
            ),
            _recent_row(
                bounded,
                last_session_at="2026-03-28T12:00:00+00:00",
                resume_target_kind="bounded_segment",
            ),
        ],
    )

    assert resolution.mode == "ambiguous-recent-projects"
    assert resolution.auto_selected is False
    assert resolution.requires_user_selection is True
    assert resolution.project_root is None
    assert resolution.candidates[0].project_root == bounded.resolve(strict=False).as_posix()
    assert resolution.candidates[0].resume_target_kind == "bounded_segment"
    assert resolution.candidates[0].reason == "recent project cache entry with confirmed bounded segment resume target"
    assert resolution.candidates[1].project_root == handoff.resolve(strict=False).as_posix()
    assert resolution.candidates[1].resume_target_kind == "handoff"
    assert resolution.candidates[1].reason == "recent project cache entry with projected continuity handoff"


def test_resolve_project_reentry_prefers_current_workspace_over_recent_project(tmp_path: Path) -> None:
    workspace = _make_gpd_workspace(tmp_path / "workspace", project=True)
    strong_recent = _make_gpd_workspace(tmp_path / "recent-strong", project=True)

    resolution = resolve_project_reentry(
        workspace,
        recent_rows=[
            _recent_row(strong_recent, last_session_at="2026-03-28T15:00:00+00:00"),
        ],
    )

    assert resolution.mode == "current-workspace"
    assert resolution.source == "current_workspace"
    assert resolution.auto_selected is False
    assert resolution.requires_user_selection is False
    assert resolution.project_root == workspace.resolve(strict=False).as_posix()
    assert resolution.selected_candidate is not None
    assert resolution.selected_candidate.source == "current_workspace"
    assert resolution.selected_candidate.project_root == workspace.resolve(strict=False).as_posix()
    assert resolution.candidates[0].source == "current_workspace"
    assert resolution.candidates[0].project_root == workspace.resolve(strict=False).as_posix()
    assert resolution.candidates[1].source == "recent_project"
    assert resolution.candidates[1].project_root == strong_recent.resolve(strict=False).as_posix()


def test_resolve_project_reentry_dedupes_current_workspace_and_recent_project_rows(tmp_path: Path) -> None:
    workspace = _make_gpd_workspace(tmp_path / "workspace", project=True)

    resolution = resolve_project_reentry(
        workspace,
        recent_rows=[
            _recent_row(
                workspace,
                last_session_at="2026-03-28T12:00:00+00:00",
            )
        ],
    )

    assert resolution.mode == "current-workspace"
    assert resolution.source == "current_workspace"
    assert resolution.project_root == workspace.resolve(strict=False).as_posix()
    assert resolution.recoverable_candidates_count == 1
    assert len(resolution.candidates) == 1
    assert resolution.candidates[0].source == "current_workspace"
