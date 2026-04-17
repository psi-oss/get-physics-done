from __future__ import annotations

import shutil
from pathlib import Path
from types import SimpleNamespace

import gpd.cli as cli_module
from gpd.core.project_reentry import resolve_project_reentry

REPO_ROOT = Path(__file__).resolve().parents[2]
HANDOFF_BUNDLE_FIXTURES = REPO_ROOT / "tests" / "fixtures" / "handoff-bundle"


def _copy_handoff_bundle_workspace(tmp_path: Path, slug: str, variant: str = "positive") -> Path:
    source = HANDOFF_BUNDLE_FIXTURES / slug / variant / "workspace"
    target = tmp_path / f"{slug}-{variant}"
    shutil.copytree(source, target)
    return target


def test_load_recent_projects_rows_ignores_additive_fields(tmp_path: Path, monkeypatch) -> None:
    project_root = (tmp_path / "recent-project").resolve(strict=False)
    project_root.mkdir(parents=True, exist_ok=True)
    row = SimpleNamespace(
        model_dump=lambda mode="json": {
            "project_root": str(project_root),
            "last_session_at": "2026-03-28T12:00:00+00:00",
            "available": True,
            "workspace_root": str(project_root),
            "future_field": {"nested": "value"},
        }
    )
    monkeypatch.setattr("gpd.core.recent_projects.list_recent_projects", lambda store_root=None, last=None: [row])

    rows = cli_module._load_recent_projects_rows()

    assert len(rows) == 1
    assert rows[0]["project_root"] == str(project_root)
    assert rows[0]["available"] is True
    assert "workspace_root" not in rows[0]
    assert "future_field" not in rows[0]


def test_normalize_recent_project_row_marks_unavailable_rows_without_command(tmp_path: Path) -> None:
    project_root = (tmp_path / "missing-project").resolve(strict=False)
    normalized = cli_module._normalize_recent_project_row(
        {
            "project_root": str(project_root),
            "available": False,
            "resume_file": "GPD/phases/01/.continue-here.md",
        }
    )

    assert normalized is not None
    assert normalized["available"] is False
    assert normalized["command"] == "unavailable"


def test_render_recent_resume_summary_keeps_runtime_specific_commands_generic(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    project_root = (tmp_path / "recent-project").resolve(strict=False)
    project_root.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "project_root": str(project_root),
            "available": True,
            "resumable": True,
            "last_session_at": "2026-03-28T12:00:00+00:00",
            "stopped_at": "Phase 1",
        }
    ]

    monkeypatch.setattr(cli_module, "_recent_project_recovery_view", lambda row: None)

    cli_module._render_recent_resume_summary(rows)

    output = capsys.readouterr().out
    assert "Recent Projects" in output
    assert "Select a workspace above" in output
    assert "resume-work" in output
    assert "gpd suggest" in output
    assert "/gpd:resume-work" not in output
    assert "$gpd-resume-work" not in output
    assert "/gpd:suggest-next" not in output
    assert "$gpd-suggest-next" not in output


def test_resume_recent_noise_positive_fixture_still_auto_selects_the_recoverable_recent_project(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    recoverable_recent = _copy_handoff_bundle_workspace(tmp_path, "resume-recent-noise")
    noisy_recent = tmp_path / "noise"
    noisy_recent.mkdir()

    resolution = resolve_project_reentry(
        workspace,
        recent_rows=[
            {
                "project_root": recoverable_recent.resolve(strict=False).as_posix(),
                "last_session_at": "2026-04-09T12:00:00+00:00",
                "stopped_at": "Phase 01",
                "resume_file": "HANDOFF.md",
                "resume_target_kind": "handoff",
                "resume_target_recorded_at": "2026-04-09T12:00:00+00:00",
                "resume_file_available": True,
                "available": True,
                "resumable": True,
                "source_kind": "continuation.handoff",
                "source_recorded_at": "2026-04-09T12:00:00+00:00",
            },
            {
                "project_root": noisy_recent.resolve(strict=False).as_posix(),
                "last_session_at": "2026-04-09T11:00:00+00:00",
                "resume_file": None,
                "resume_file_available": False,
                "available": False,
                "resumable": False,
            },
        ],
    )

    assert resolution.mode == "auto-recent-project"
    assert resolution.source == "recent_project"
    assert resolution.auto_selected is True
    assert resolution.project_root == recoverable_recent.resolve(strict=False).as_posix()
    assert resolution.selected_candidate is not None
    assert resolution.selected_candidate.project_root == recoverable_recent.resolve(strict=False).as_posix()
    assert resolution.selected_candidate.auto_selectable is True
    assert resolution.candidates[0].project_root == recoverable_recent.resolve(strict=False).as_posix()
def test_resume_recent_requests_only_the_bounded_recent_picker_window(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _fake_list_recent_projects(store_root=None, last=None):
        captured["last"] = last
        return []

    monkeypatch.setattr("gpd.core.recent_projects.list_recent_projects", _fake_list_recent_projects)

    rows = cli_module._load_recent_projects_rows(last=20)

    assert rows == []
    assert captured["last"] == 20
