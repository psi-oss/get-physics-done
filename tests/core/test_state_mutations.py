from __future__ import annotations

import json
from pathlib import Path

import pytest

from gpd.core.state import (
    default_state_dict,
    load_state_json,
    save_state_json,
    state_add_decision,
    state_clear_continuation_bounded_segment,
    state_record_metric,
    state_record_session,
    state_set_continuation_bounded_segment,
)


class TestStateAddDecision:
    def test_add_decision_persists_to_markdown_and_json(
        self, tmp_path: Path, state_project_factory
    ) -> None:
        cwd = state_project_factory(tmp_path)

        result = state_add_decision(cwd, summary="Use SI units", phase="1")

        assert result.added is True
        assert result.decision == "- [Phase 1]: Use SI units"

        markdown = (cwd / "GPD" / "STATE.md").read_text(encoding="utf-8")
        stored = json.loads((cwd / "GPD" / "state.json").read_text(encoding="utf-8"))

        assert "Use SI units" in markdown
        assert stored["decisions"] == [{"phase": "1", "summary": "Use SI units", "rationale": None}]

    def test_add_decision_with_rationale_persists_rationale(
        self, tmp_path: Path, state_project_factory
    ) -> None:
        cwd = state_project_factory(tmp_path)

        result = state_add_decision(
            cwd,
            summary="Choose RK4 integrator",
            phase="2",
            rationale="Better stability",
        )

        assert result.added is True

        markdown = (cwd / "GPD" / "STATE.md").read_text(encoding="utf-8")
        stored = json.loads((cwd / "GPD" / "state.json").read_text(encoding="utf-8"))

        assert "Choose RK4 integrator" in markdown
        assert "Better stability" in markdown
        assert stored["decisions"][0]["rationale"] == "Better stability"

    def test_add_decision_without_phase_uses_placeholder(
        self, tmp_path: Path, state_project_factory
    ) -> None:
        cwd = state_project_factory(tmp_path)

        result = state_add_decision(cwd, summary="Adopt natural units")

        assert result.added is True
        assert result.decision == "- [Phase ?]: Adopt natural units"

    @pytest.mark.parametrize("summary", [None, ""])
    def test_add_decision_requires_summary(
        self, tmp_path: Path, state_project_factory, summary: str | None
    ) -> None:
        cwd = state_project_factory(tmp_path)

        result = state_add_decision(cwd, summary=summary)

        assert result.added is False
        assert result.error is not None

    def test_add_decision_missing_state_file(self, tmp_path: Path) -> None:
        result = state_add_decision(tmp_path, summary="Something")

        assert result.added is False
        assert "not found" in (result.error or "").lower()

    def test_add_multiple_decisions_appends_entries(
        self, tmp_path: Path, state_project_factory
    ) -> None:
        cwd = state_project_factory(tmp_path)

        state_add_decision(cwd, summary="Decision A", phase="1")
        state_add_decision(cwd, summary="Decision B", phase="2")

        stored = json.loads((cwd / "GPD" / "state.json").read_text(encoding="utf-8"))
        summaries = [entry["summary"] for entry in stored["decisions"]]

        assert summaries == ["Decision A", "Decision B"]

    def test_add_decision_removes_decision_placeholder(
        self, tmp_path: Path, state_project_factory
    ) -> None:
        cwd = state_project_factory(tmp_path)
        before = (cwd / "GPD" / "STATE.md").read_text(encoding="utf-8")
        assert "None yet." in before

        state_add_decision(cwd, summary="First decision", phase="1")

        after = (cwd / "GPD" / "STATE.md").read_text(encoding="utf-8")
        decisions_start = after.find("### Decisions")
        decisions_end = after.find("\n###", decisions_start + 1)
        if decisions_end == -1:
            decisions_end = after.find("\n##", decisions_start + 1)
        if decisions_end == -1:
            decisions_end = len(after)

        assert "None yet." not in after[decisions_start:decisions_end]


class TestStateRecordMetric:
    def test_record_metric_persists_to_markdown_and_json(
        self, tmp_path: Path, state_project_factory
    ) -> None:
        cwd = state_project_factory(tmp_path)

        result = state_record_metric(
            cwd,
            phase="03",
            plan="01",
            duration="45min",
            tasks="5",
            files="3",
        )

        assert result.recorded is True
        assert result.phase == "03"
        assert result.plan == "01"
        assert result.duration == "45min"

        markdown = (cwd / "GPD" / "STATE.md").read_text(encoding="utf-8")
        stored = json.loads((cwd / "GPD" / "state.json").read_text(encoding="utf-8"))

        assert "Phase 03 P01" in markdown
        assert "45min" in markdown
        assert "5 tasks" in markdown
        assert "3 files" in markdown
        assert stored["performance_metrics"]["rows"] == [
            {"label": "Phase 03 P01", "duration": "45min", "tasks": "5", "files": "3"}
        ]

    @pytest.mark.parametrize(
        ("phase", "plan", "duration"),
        [
            (None, "01", "10min"),
            ("03", None, "10min"),
            ("03", "01", None),
        ],
    )
    def test_record_metric_requires_phase_plan_and_duration(
        self,
        tmp_path: Path,
        state_project_factory,
        phase: str | None,
        plan: str | None,
        duration: str | None,
    ) -> None:
        cwd = state_project_factory(tmp_path)

        result = state_record_metric(cwd, phase=phase, plan=plan, duration=duration)

        assert result.recorded is False
        assert result.error is not None

    def test_record_metric_missing_state_file(self, tmp_path: Path) -> None:
        result = state_record_metric(tmp_path, phase="01", plan="01", duration="5min")

        assert result.recorded is False
        assert "not found" in (result.error or "").lower()

    def test_record_multiple_metrics_keeps_existing_rows(
        self, tmp_path: Path, state_project_factory
    ) -> None:
        cwd = state_project_factory(tmp_path)

        state_record_metric(cwd, phase="03", plan="01", duration="20min")
        state_record_metric(cwd, phase="03", plan="02", duration="30min")

        stored = json.loads((cwd / "GPD" / "state.json").read_text(encoding="utf-8"))
        labels = [row["label"] for row in stored["performance_metrics"]["rows"]]

        assert labels == ["Phase 03 P01", "Phase 03 P02"]

    def test_record_metric_uses_dash_placeholders_for_missing_optional_values(
        self, tmp_path: Path, state_project_factory
    ) -> None:
        cwd = state_project_factory(tmp_path)

        result = state_record_metric(cwd, phase="03", plan="01", duration="15min", tasks=None, files=None)

        assert result.recorded is True
        markdown = (cwd / "GPD" / "STATE.md").read_text(encoding="utf-8")
        stored = json.loads((cwd / "GPD" / "state.json").read_text(encoding="utf-8"))

        assert "| Phase 03 P01 | 15min | - tasks | - files |" in markdown
        assert stored["performance_metrics"]["rows"][0]["tasks"] == "-"
        assert stored["performance_metrics"]["rows"][0]["files"] == "-"


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
        assert stored["continuation"]["machine"]["recorded_at"] == stored["session"]["last_date"]
        assert stored["continuation"]["machine"]["hostname"] == stored["session"]["hostname"]
        assert stored["continuation"]["machine"]["platform"] == stored["session"]["platform"]

    def test_record_session_preserves_resume_file_when_omitted(
        self, tmp_path: Path, session_state_project_factory
    ) -> None:
        cwd = session_state_project_factory(tmp_path)

        result = state_record_session(cwd, stopped_at="Done")

        assert result.recorded is True

        markdown = (cwd / "GPD" / "STATE.md").read_text(encoding="utf-8")
        stored = json.loads((cwd / "GPD" / "state.json").read_text(encoding="utf-8"))

        assert "Done" in markdown
        assert "**Resume file:** resume.md" in markdown
        assert stored["session"]["resume_file"] == "resume.md"
        assert stored["continuation"]["handoff"]["resume_file"] == "resume.md"

    @pytest.mark.parametrize("clear_value", ["", "  ", "—", "None", "null"])
    def test_record_session_clears_resume_file_when_placeholder_is_passed(
        self,
        tmp_path: Path,
        session_state_project_factory,
        clear_value: str,
    ) -> None:
        cwd = session_state_project_factory(tmp_path)

        result = state_record_session(cwd, stopped_at="Done", resume_file=clear_value)

        assert result.recorded is True
        stored = json.loads((cwd / "GPD" / "state.json").read_text(encoding="utf-8"))
        markdown = (cwd / "GPD" / "STATE.md").read_text(encoding="utf-8")

        assert stored["session"]["resume_file"] is None
        assert stored["continuation"]["handoff"]["resume_file"] is None
        assert "**Resume file:** —" in markdown

    def test_record_session_missing_state_file(self, tmp_path: Path) -> None:
        result = state_record_session(tmp_path, stopped_at="Task 1")

        assert result.recorded is False
        assert "not found" in (result.error or "").lower()


class TestStateContinuationBoundedSegment:
    def test_set_continuation_bounded_segment_persists_json_only_and_preserves_session(
        self, tmp_path: Path
    ) -> None:
        state = default_state_dict()
        state["session"]["last_date"] = "2026-03-29T00:00:00+00:00"
        state["session"]["stopped_at"] = "Phase 03 Plan 2"
        state["session"]["resume_file"] = "resume.md"
        save_state_json(tmp_path, state)

        layout = tmp_path / "GPD"
        before_markdown = (layout / "STATE.md").read_text(encoding="utf-8")
        resume_path = layout / "phases" / "03-analysis" / ".continue-here.md"
        resume_path.parent.mkdir(parents=True, exist_ok=True)
        resume_path.write_text("continue", encoding="utf-8")

        result = state_set_continuation_bounded_segment(
            tmp_path,
            {
                "resume_file": str(resume_path),
                "phase": 3,
                "plan": "02",
                "segment_id": "segment-03-02",
                "segment_status": "blocked",
                "waiting_for_review": True,
            },
        )

        stored = load_state_json(tmp_path)
        after_markdown = (layout / "STATE.md").read_text(encoding="utf-8")

        assert result.updated is True
        assert stored is not None
        assert stored["session"]["resume_file"] == "resume.md"
        assert stored["continuation"]["handoff"]["resume_file"] == "resume.md"
        assert stored["continuation"]["bounded_segment"]["resume_file"] == "GPD/phases/03-analysis/.continue-here.md"
        assert stored["continuation"]["bounded_segment"]["phase"] == "03"
        assert stored["continuation"]["bounded_segment"]["plan"] == "02"
        assert stored["continuation"]["bounded_segment"]["segment_id"] == "segment-03-02"
        assert stored["continuation"]["bounded_segment"]["segment_status"] == "blocked"
        assert stored["continuation"]["bounded_segment"]["waiting_for_review"] is True
        assert after_markdown == before_markdown

    def test_clear_continuation_bounded_segment_is_idempotent(self, tmp_path: Path) -> None:
        state = default_state_dict()
        state["session"]["resume_file"] = "resume.md"
        state["continuation"]["bounded_segment"] = {
            "resume_file": "GPD/phases/03-analysis/.continue-here.md",
            "phase": "03",
            "plan": "02",
            "segment_id": "segment-03-02",
            "segment_status": "blocked",
            "waiting_for_review": True,
        }
        save_state_json(tmp_path, state)

        result = state_clear_continuation_bounded_segment(tmp_path)
        stored = load_state_json(tmp_path)
        second = state_clear_continuation_bounded_segment(tmp_path)

        assert result.updated is True
        assert stored is not None
        assert stored["continuation"]["bounded_segment"] is None
        assert stored["continuation"]["handoff"]["resume_file"] == "resume.md"
        assert stored["session"]["resume_file"] == "resume.md"
        assert second.updated is False
        assert second.reason == "Continuation bounded_segment already clear"

    def test_clear_continuation_bounded_segment_recovers_backup_after_primary_corruption(
        self, tmp_path: Path
    ) -> None:
        state = default_state_dict()
        state["session"]["last_date"] = "2026-03-29T12:00:00+00:00"
        state["session"]["stopped_at"] = "Phase 03 Plan 2"
        state["session"]["resume_file"] = "resume.md"
        state["continuation"]["handoff"]["recorded_at"] = "2026-03-29T12:00:00+00:00"
        state["continuation"]["handoff"]["stopped_at"] = "Phase 03 Plan 2"
        state["continuation"]["bounded_segment"] = {
            "resume_file": "GPD/phases/03-analysis/.continue-here.md",
            "phase": "03",
            "plan": "02",
            "segment_id": "segment-03-02",
            "segment_status": "blocked",
            "waiting_for_review": True,
        }
        save_state_json(tmp_path, state)

        layout = tmp_path / "GPD"
        (layout / "state.json").write_text("{\"broken\":", encoding="utf-8")

        result = state_clear_continuation_bounded_segment(tmp_path)
        stored = load_state_json(tmp_path)

        assert result.updated is True
        assert stored is not None
        assert stored["continuation"]["handoff"]["resume_file"] == "resume.md"
        assert stored["continuation"]["handoff"]["stopped_at"] == "Phase 03 Plan 2"
        assert stored["continuation"]["bounded_segment"] is None
