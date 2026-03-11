from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from gpd.core.state import default_state_dict, generate_state_markdown


def _write_state_project(
    tmp_path: Path,
    state_dict: dict | None = None,
    *,
    current_phase: str = "03",
    status: str = "Executing",
    extra_lines: int = 0,
) -> Path:
    planning = tmp_path / ".gpd"
    planning.mkdir(exist_ok=True)
    (planning / "phases").mkdir(exist_ok=True)
    (planning / "PROJECT.md").write_text("# Project\nTest.\n", encoding="utf-8")
    (planning / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")

    state = copy.deepcopy(state_dict) if state_dict is not None else default_state_dict()
    position = state.setdefault("position", {})
    defaults = {
        "current_phase": current_phase,
        "status": status,
        "current_plan": "1",
        "total_plans_in_phase": 3,
        "progress_percent": 33,
    }
    for key, value in defaults.items():
        if position.get(key) is None:
            position[key] = value

    markdown = generate_state_markdown(state)
    if extra_lines > 0:
        padding = "\n".join(f"<!-- padding line {index} -->" for index in range(extra_lines))
        markdown = f"{markdown}\n{padding}"

    (planning / "STATE.md").write_text(markdown, encoding="utf-8")
    (planning / "state.json").write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    return tmp_path


@pytest.fixture
def state_project_factory():
    def factory(
        tmp_path: Path,
        state_dict: dict | None = None,
        *,
        current_phase: str = "03",
        status: str = "Executing",
        extra_lines: int = 0,
    ) -> Path:
        return _write_state_project(
            tmp_path,
            state_dict,
            current_phase=current_phase,
            status=status,
            extra_lines=extra_lines,
        )

    return factory


@pytest.fixture
def session_state_project_factory(state_project_factory):
    def factory(tmp_path: Path) -> Path:
        state = default_state_dict()
        state["position"]["current_phase"] = "01"
        state["position"]["status"] = "Executing"
        state["position"]["current_plan"] = "1"
        state["position"]["total_plans_in_phase"] = 2
        state["position"]["progress_percent"] = 50
        state["session"]["last_date"] = "2025-01-01T00:00:00+00:00"
        state["session"]["stopped_at"] = "Task 3"
        state["session"]["resume_file"] = "resume.md"
        return state_project_factory(tmp_path, state_dict=state, current_phase="01", status="Executing")

    return factory


@pytest.fixture
def large_state_project_factory(state_project_factory):
    def factory(
        tmp_path: Path,
        *,
        n_old_decisions: int = 30,
        n_resolved_blockers: int = 10,
        current_phase: str = "05",
        extra_lines: int = 0,
    ) -> Path:
        state = default_state_dict()
        position = state["position"]
        position["current_phase"] = current_phase
        position["status"] = "Executing"
        position["current_plan"] = "1"
        position["total_plans_in_phase"] = 3
        position["progress_percent"] = 50

        decisions = []
        for index in range(n_old_decisions):
            phase = str((index % 3) + 1)
            decisions.append({"phase": phase, "summary": f"Old decision {index}"})
        decisions.append({"phase": "5", "summary": "Current phase decision"})
        decisions.append({"phase": "4", "summary": "Recent phase decision"})
        state["decisions"] = decisions

        blockers = [f"Resolved issue {index} [resolved]" for index in range(n_resolved_blockers)]
        blockers.append("Active blocker still open")
        state["blockers"] = blockers

        return state_project_factory(
            tmp_path,
            state_dict=state,
            current_phase=current_phase,
            status="Executing",
            extra_lines=extra_lines,
        )

    return factory
