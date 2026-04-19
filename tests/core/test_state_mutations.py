from __future__ import annotations

import json
from pathlib import Path

from gpd.core.state import (
    default_state_dict,
    generate_state_markdown,
    load_state_json,
    save_state_json,
    state_add_decision,
    state_record_session,
    state_update,
)


def _bootstrap_markdown_recovery_project(tmp_path: Path, *, state: dict[str, object] | None = None) -> Path:
    cwd = tmp_path
    gpd_dir = cwd / "GPD"
    gpd_dir.mkdir(parents=True, exist_ok=True)
    (gpd_dir / "PROJECT.md").write_text("# Project\n", encoding="utf-8")
    (gpd_dir / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")

    phase_dir = gpd_dir / "phases" / "03-phase"
    phase_dir.mkdir(parents=True, exist_ok=True)
    (phase_dir / "PLAN.md").write_text("# Plan\n", encoding="utf-8")
    (phase_dir / "SUMMARY.md").write_text("# Summary\n", encoding="utf-8")

    state_obj = state or default_state_dict()
    position = state_obj.setdefault("position", {})
    if position.get("current_phase") is None:
        position["current_phase"] = "03"
    if position.get("status") is None:
        position["status"] = "Executing"
    if position.get("current_plan") is None:
        position["current_plan"] = "1"
    if position.get("total_plans_in_phase") is None:
        position["total_plans_in_phase"] = 3
    if position.get("progress_percent") is None:
        position["progress_percent"] = 33
    save_state_json(cwd, state_obj)
    return cwd


class TestStateAddDecision:
    def test_add_decision_persists_to_markdown_and_json(
        self, tmp_path: Path, state_project_factory
    ) -> None:
        cwd = state_project_factory(tmp_path)

        result = state_add_decision(
            cwd,
            summary="Use SI units",
            phase="1",
            rationale="Keep the canonical convention consistent",
        )

        assert result.added is True
        assert result.decision == "- [Phase 1]: Use SI units — Keep the canonical convention consistent"

        markdown = (cwd / "GPD" / "STATE.md").read_text(encoding="utf-8")
        stored = json.loads((cwd / "GPD" / "state.json").read_text(encoding="utf-8"))

        assert "Use SI units" in markdown
        assert "Keep the canonical convention consistent" in markdown
        assert stored["decisions"] == [
            {
                "phase": "1",
                "summary": "Use SI units",
                "rationale": "Keep the canonical convention consistent",
            }
        ]

class TestStateRecordSession:
    def test_record_session_updates_markdown_and_json(
        self, tmp_path: Path, session_state_project_factory
    ) -> None:
        cwd = session_state_project_factory(tmp_path)

        result = state_record_session(cwd, stopped_at="Phase 03 Plan 2", resume_file="next-step.md")

        assert result.recorded is True
        assert set(result.updated) >= {"Last session", "Stopped at", "Resume file"}

        markdown = (cwd / "GPD" / "STATE.md").read_text(encoding="utf-8")
        stored = json.loads((cwd / "GPD" / "state.json").read_text(encoding="utf-8"))

        assert "Phase 03 Plan 2" in markdown
        assert "next-step.md" in markdown
        assert stored["session"]["stopped_at"] == "Phase 03 Plan 2"
        assert stored["session"]["resume_file"] == "next-step.md"
        assert stored["session"]["last_date"] is not None
        assert stored["continuation"]["handoff"]["recorded_at"] == stored["session"]["last_date"]
        assert stored["continuation"]["handoff"]["stopped_at"] == "Phase 03 Plan 2"
        assert stored["continuation"]["handoff"]["resume_file"] == "next-step.md"
        assert stored["continuation"]["handoff"]["recorded_by"] == "state_record_session"
        assert stored["continuation"]["machine"]["recorded_at"] == stored["session"]["last_date"]
        assert stored["continuation"]["machine"]["hostname"] == stored["session"]["hostname"]
        assert stored["continuation"]["machine"]["platform"] == stored["session"]["platform"]


def test_markdown_mutator_recovers_missing_state_markdown_from_state_json(
    tmp_path: Path,
) -> None:
    cwd = _bootstrap_markdown_recovery_project(tmp_path)
    state_md = cwd / "GPD" / "STATE.md"
    state_md.unlink()

    result = state_update(cwd, "Current Phase Name", "Recovered phase name")

    assert result.updated is True
    assert state_md.exists()
    regenerated = generate_state_markdown(load_state_json(cwd) or default_state_dict())
    assert regenerated.startswith("# Research State")


def test_state_update_prefers_literal_dotted_field_before_dot_stripping(tmp_path: Path) -> None:
    cwd = _bootstrap_markdown_recovery_project(tmp_path)
    state_md = cwd / "GPD" / "STATE.md"
    content = state_md.read_text(encoding="utf-8")
    import re as _re

    content = _re.sub(
        r"(## Session Continuity)",
        "**custom.field.status:** old_value\n\n\\1",
        content,
        count=1,
        flags=_re.IGNORECASE,
    )
    state_md.write_text(content, encoding="utf-8")

    result = state_update(cwd, "custom.field.status", "new_value")

    assert result.updated is True
    updated_content = state_md.read_text(encoding="utf-8")
    assert "**custom.field.status:** new_value" in updated_content
    assert "**Status:** Executing" in updated_content


def test_state_update_strips_dot_prefix_after_underscore_resolution(tmp_path: Path) -> None:
    cwd = _bootstrap_markdown_recovery_project(tmp_path)

    result = state_update(cwd, "position.status", "Paused")

    assert result.updated is True
    stored = load_state_json(cwd)
    assert stored is not None
    assert stored["position"]["status"] == "Paused"


def test_state_update_rejects_invalid_dotted_status_after_resolution(tmp_path: Path) -> None:
    state = default_state_dict()
    state["position"]["status"] = "Paused"
    cwd = _bootstrap_markdown_recovery_project(tmp_path, state=state)

    result = state_update(cwd, "position.status", "banana")

    assert result.updated is False
    assert 'Invalid status: "banana"' in (result.reason or "")
    stored = load_state_json(cwd)
    assert stored is not None
    assert stored["position"]["status"] == "Paused"


def test_state_update_rejects_dotted_session_continuity_mirror_field(tmp_path: Path) -> None:
    cwd = _bootstrap_markdown_recovery_project(tmp_path)
    state_record_session(cwd, stopped_at="Phase 03 Plan 2", resume_file="canonical-handoff.md")

    result = state_update(cwd, "continuation.handoff.resume_file", "edited-in-markdown.md")

    assert result.updated is False
    assert "mirror field" in (result.reason or "").lower()
    stored = load_state_json(cwd)
    assert stored is not None
    assert stored["continuation"]["handoff"]["resume_file"] == "canonical-handoff.md"
