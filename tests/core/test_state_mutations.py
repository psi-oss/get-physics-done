from __future__ import annotations

import json
from pathlib import Path

import pytest

from gpd.core.state import state_add_decision, state_record_metric, state_record_session


class TestStateAddDecision:
    def test_add_decision_persists_to_markdown_and_json(
        self, tmp_path: Path, state_project_factory
    ) -> None:
        cwd = state_project_factory(tmp_path)

        result = state_add_decision(cwd, summary="Use SI units", phase="1")

        assert result.added is True
        assert result.decision == "- [Phase 1]: Use SI units"

        markdown = (cwd / ".gpd" / "STATE.md").read_text(encoding="utf-8")
        stored = json.loads((cwd / ".gpd" / "state.json").read_text(encoding="utf-8"))

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

        markdown = (cwd / ".gpd" / "STATE.md").read_text(encoding="utf-8")
        stored = json.loads((cwd / ".gpd" / "state.json").read_text(encoding="utf-8"))

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

        stored = json.loads((cwd / ".gpd" / "state.json").read_text(encoding="utf-8"))
        summaries = [entry["summary"] for entry in stored["decisions"]]

        assert summaries == ["Decision A", "Decision B"]

    def test_add_decision_removes_decision_placeholder(
        self, tmp_path: Path, state_project_factory
    ) -> None:
        cwd = state_project_factory(tmp_path)
        before = (cwd / ".gpd" / "STATE.md").read_text(encoding="utf-8")
        assert "None yet." in before

        state_add_decision(cwd, summary="First decision", phase="1")

        after = (cwd / ".gpd" / "STATE.md").read_text(encoding="utf-8")
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

        markdown = (cwd / ".gpd" / "STATE.md").read_text(encoding="utf-8")
        stored = json.loads((cwd / ".gpd" / "state.json").read_text(encoding="utf-8"))

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

        stored = json.loads((cwd / ".gpd" / "state.json").read_text(encoding="utf-8"))
        labels = [row["label"] for row in stored["performance_metrics"]["rows"]]

        assert labels == ["Phase 03 P01", "Phase 03 P02"]

    def test_record_metric_uses_dash_placeholders_for_missing_optional_values(
        self, tmp_path: Path, state_project_factory
    ) -> None:
        cwd = state_project_factory(tmp_path)

        result = state_record_metric(cwd, phase="03", plan="01", duration="15min", tasks=None, files=None)

        assert result.recorded is True
        markdown = (cwd / ".gpd" / "STATE.md").read_text(encoding="utf-8")
        stored = json.loads((cwd / ".gpd" / "state.json").read_text(encoding="utf-8"))

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

        markdown = (cwd / ".gpd" / "STATE.md").read_text(encoding="utf-8")
        stored = json.loads((cwd / ".gpd" / "state.json").read_text(encoding="utf-8"))

        assert "Phase 03 Plan 2" in markdown
        assert "next-step.md" in markdown
        assert stored["session"]["stopped_at"] == "Phase 03 Plan 2"
        assert stored["session"]["resume_file"] == "next-step.md"
        assert stored["session"]["last_date"] is not None

    def test_record_session_clears_resume_file_when_omitted(
        self, tmp_path: Path, session_state_project_factory
    ) -> None:
        cwd = session_state_project_factory(tmp_path)

        result = state_record_session(cwd, stopped_at="Done")

        assert result.recorded is True

        markdown = (cwd / ".gpd" / "STATE.md").read_text(encoding="utf-8")
        stored = json.loads((cwd / ".gpd" / "state.json").read_text(encoding="utf-8"))

        assert "Done" in markdown
        assert "**Resume file:**" in markdown
        assert stored["session"]["resume_file"] is None

    def test_record_session_missing_state_file(self, tmp_path: Path) -> None:
        result = state_record_session(tmp_path, stopped_at="Task 1")

        assert result.recorded is False
        assert "not found" in (result.error or "").lower()
