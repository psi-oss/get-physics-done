from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from gpd.core.project_reentry import resolve_project_reentry
from gpd.core.runtime_hints import build_runtime_hint_payload
from gpd.core.state import default_state_dict, generate_state_markdown, state_get, state_snapshot

REPO_ROOT = Path(__file__).resolve().parents[1]
HANDOFF_BUNDLE_FIXTURES = REPO_ROOT / "tests" / "fixtures" / "handoff-bundle"


def _copy_fixture_workspace(tmp_path: Path, slug: str, variant: str = "positive") -> Path:
    source = HANDOFF_BUNDLE_FIXTURES / slug / variant / "workspace"
    target = tmp_path / f"{slug}-{variant}"
    shutil.copytree(source, target)
    return target


def _make_partial_current_workspace(root: Path) -> Path:
    gpd_dir = root / "GPD"
    gpd_dir.mkdir(parents=True, exist_ok=True)

    state = default_state_dict()
    state["position"].update(
        {
            "current_phase": "01",
            "current_phase_name": "Continuity check",
            "status": "Paused",
            "paused_at": "Paused after task 2",
        }
    )
    (gpd_dir / "state.json").write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    (gpd_dir / "STATE.md").write_text(generate_state_markdown(state), encoding="utf-8")
    (gpd_dir / "ROADMAP.md").write_text("# Roadmap\n\n## Phase 1: Continuity check\n", encoding="utf-8")
    return root


def _make_stale_session_continuity_markdown(project_root: Path) -> None:
    state_md = project_root / "GPD" / "STATE.md"
    content = state_md.read_text(encoding="utf-8")
    stale_block = (
        "## Session Continuity\n\n"
        "**Last session:** 1999-01-01T00:00:00+00:00\n"
        "**Hostname:** stale-host\n"
        "**Platform:** stale-platform\n"
        "**Stopped at:** Stale stop\n"
        "**Resume file:** stale-resume.md\n"
        "**Last result ID:** stale-result\n"
    )
    content = re.sub(r"## Session Continuity\n\n.*\Z", stale_block, content, flags=re.S)
    state_md.write_text(content, encoding="utf-8")


def test_bug_resume_state_continuity_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Red exact repro: canonical session/continuation/handoff must come from state.json,
    # not from stale session-continuity prose in STATE.md.
    continuity_workspace = _copy_fixture_workspace(tmp_path, "resume-handoff")
    snapshot = state_snapshot(continuity_workspace)
    expected_session = snapshot.session
    assert isinstance(expected_session, dict)

    _make_stale_session_continuity_markdown(continuity_workspace)

    session = state_get(continuity_workspace, "session")
    continuation = state_get(continuity_workspace, "continuation")
    handoff = state_get(continuity_workspace, "handoff")
    session_payload = json.loads(session.value or "{}")
    continuation_payload = json.loads(continuation.value or "{}")
    handoff_payload = json.loads(handoff.value or "{}")

    assert session.error is None
    assert continuation.error is None
    assert handoff.error is None
    assert session_payload["resume_file"] == expected_session["resume_file"]
    assert session_payload["stopped_at"] == expected_session["stopped_at"]
    assert session_payload["last_result_id"] == expected_session["last_result_id"]
    assert session_payload["last_date"] == expected_session["last_date"]
    assert session_payload["hostname"] == expected_session["hostname"]
    assert session_payload["platform"] == expected_session["platform"]
    assert "stale-host" not in (session.value or "")
    assert continuation_payload["handoff"]["resume_file"] == expected_session["resume_file"]
    assert continuation_payload["handoff"]["last_result_id"] == expected_session["last_result_id"]
    assert handoff_payload["resume_file"] == expected_session["resume_file"]
    assert handoff_payload["last_result_id"] == expected_session["last_result_id"]

    # Green exact fix: recent-project selection should beat a partial current workspace,
    # and runtime-hints hydration should preserve the selected recent-project provenance.
    selection_workspace = _make_partial_current_workspace(tmp_path / "selection-workspace")
    strong_recent = _copy_fixture_workspace(tmp_path, "resume-recent-noise")
    resolution = resolve_project_reentry(
        selection_workspace,
        recent_rows=[
            {
                "project_root": strong_recent.resolve(strict=False).as_posix(),
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
            }
        ],
    )

    assert resolution.mode == "auto-recent-project"
    assert resolution.source == "recent_project"
    assert resolution.auto_selected is True
    assert resolution.project_root == strong_recent.resolve(strict=False).as_posix()
    assert resolution.selected_candidate is not None
    assert resolution.selected_candidate.source == "recent_project"
    assert resolution.candidates[0].source == "recent_project"

    data_root = tmp_path / "data"
    recent_project_root = tmp_path / "recent-project"
    recent_project_root.mkdir()
    current_project = {
        "source": "recent_project",
        "project_root": recent_project_root.resolve(strict=False).as_posix(),
        "resume_file": "GPD/phases/04/.continue-here.md",
        "resume_file_available": False,
        "resume_file_reason": "resume file missing",
        "resumable": False,
        "recoverable": False,
        "last_session_at": "2026-03-27T12:05:00+00:00",
        "stopped_at": "Phase 04",
        "hostname": "builder-04",
        "platform": "Linux 6.1 x86_64",
        "resume_target_kind": "handoff",
        "source_kind": "continuation.handoff",
    }
    fake_reentry = SimpleNamespace(
        resolved_project_root=recent_project_root.resolve(strict=False),
        auto_selected=True,
        mode="recent-projects",
        selected_candidate=current_project,
        candidates=[current_project],
    )

    monkeypatch.setattr(
        "gpd.core.runtime_hints._resume_context",
        lambda _cwd, data_root=None: {
            "planning_exists": True,
            "state_exists": True,
            "roadmap_exists": True,
            "project_exists": True,
            "resume_candidates": [],
            "has_live_execution": False,
        },
    )
    monkeypatch.setattr("gpd.core.runtime_hints.resolve_project_reentry", lambda *args, **kwargs: fake_reentry)
    monkeypatch.setattr(
        "gpd.core.runtime_hints._selected_reentry_candidate",
        lambda *args, **kwargs: current_project,
    )

    payload = build_runtime_hint_payload(
        continuity_workspace,
        data_root=data_root,
        include_cost=False,
        include_workflow_presets=False,
    )

    assert payload.recovery["current_project"] is not None
    assert payload.recovery["current_project"]["source"] == "recent_project"
    assert payload.recovery["current_project"]["project_root"] == recent_project_root.resolve(strict=False).as_posix()
    assert payload.recovery["current_project"]["session_hostname"] == "builder-04"
    assert payload.recovery["current_project"]["session_platform"] == "Linux 6.1 x86_64"
    assert payload.recovery["current_project"]["session_last_date"] == "2026-03-27T12:05:00+00:00"
    assert payload.recovery["current_project"]["session_stopped_at"] == "Phase 04"
    assert payload.orientation["session_hostname"] == "builder-04"
    assert payload.orientation["session_platform"] == "Linux 6.1 x86_64"
    assert payload.orientation["session_last_date"] == "2026-03-27T12:05:00+00:00"
    assert payload.orientation["session_stopped_at"] == "Phase 04"
    assert payload.orientation["recorded_continuity_handoff_file"] == "GPD/phases/04/.continue-here.md"
    assert payload.orientation["missing_continuity_handoff_file"] == "GPD/phases/04/.continue-here.md"
