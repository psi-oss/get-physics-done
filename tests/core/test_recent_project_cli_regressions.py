from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import gpd.cli as cli_module


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
    assert "suggest-next" in output
    assert "/gpd:resume-work" not in output
    assert "$gpd-resume-work" not in output
    assert "/gpd:suggest-next" not in output
    assert "$gpd-suggest-next" not in output


def test_resume_recent_requests_only_the_bounded_recent_picker_window(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _fake_list_recent_projects(store_root=None, last=None):
        captured["last"] = last
        return []

    monkeypatch.setattr("gpd.core.recent_projects.list_recent_projects", _fake_list_recent_projects)

    rows = cli_module._load_recent_projects_rows(last=20)

    assert rows == []
    assert captured["last"] == 20
