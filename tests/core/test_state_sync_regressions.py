from __future__ import annotations

import json
from pathlib import Path

from gpd.core.state import (
    default_state_dict,
    generate_state_markdown,
    save_state_markdown,
    state_update_progress,
    state_validate,
    sync_state_json_core,
)


def _bootstrap_project(tmp_path: Path) -> Path:
    planning = tmp_path / ".gpd"
    planning.mkdir()
    (planning / "phases").mkdir()
    return tmp_path


def test_sync_state_json_core_uses_markdown_bullet_sections_as_authority(tmp_path: Path) -> None:
    cwd = _bootstrap_project(tmp_path)
    planning = cwd / ".gpd"

    existing = default_state_dict()
    existing["position"]["current_phase"] = "03"
    existing["position"]["status"] = "Executing"
    existing["active_calculations"] = ["stale calculation"]
    existing["intermediate_results"] = ["stale result"]
    existing["open_questions"] = ["stale question"]
    (planning / "state.json").write_text(json.dumps(existing, indent=2), encoding="utf-8")

    markdown_state = default_state_dict()
    markdown_state["position"]["current_phase"] = "03"
    markdown_state["position"]["status"] = "Executing"
    markdown_state["active_calculations"] = ["fresh calculation"]
    markdown_state["intermediate_results"] = ["fresh result"]
    markdown_state["open_questions"] = []
    md_content = generate_state_markdown(markdown_state)

    result = sync_state_json_core(cwd, md_content)
    stored = json.loads((planning / "state.json").read_text(encoding="utf-8"))

    assert result["active_calculations"] == ["fresh calculation"]
    assert result["intermediate_results"] == ["fresh result"]
    assert result["open_questions"] == []
    assert stored["active_calculations"] == ["fresh calculation"]
    assert stored["intermediate_results"] == ["fresh result"]
    assert stored["open_questions"] == []


def test_sync_state_json_core_bootstrap_preserves_progress_and_metrics(tmp_path: Path) -> None:
    cwd = _bootstrap_project(tmp_path)
    planning = cwd / ".gpd"

    state = default_state_dict()
    state["position"]["current_phase"] = "03"
    state["position"]["status"] = "Executing"
    state["position"]["progress_percent"] = 42
    state["project_reference"]["project_md_updated"] = "2026-03-10"
    state["performance_metrics"]["rows"] = [
        {"label": "Phase 03 P01", "duration": "12m", "tasks": "3", "files": "2"}
    ]

    result = sync_state_json_core(cwd, generate_state_markdown(state))
    stored = json.loads((planning / "state.json").read_text(encoding="utf-8"))

    assert result["position"]["progress_percent"] == 42
    assert stored["position"]["progress_percent"] == 42
    assert stored["project_reference"]["project_md_updated"] == "2026-03-10"
    assert stored["performance_metrics"]["rows"] == [
        {"label": "Phase 03 P01", "duration": "12m", "tasks": "3", "files": "2"}
    ]


def test_sync_state_json_core_placeholder_fields_clear_stale_json_values(tmp_path: Path) -> None:
    cwd = _bootstrap_project(tmp_path)
    planning = cwd / ".gpd"

    existing = default_state_dict()
    existing["position"]["current_phase"] = "03"
    existing["position"]["status"] = "Executing"
    existing["project_reference"]["core_research_question"] = "Old question"
    existing["project_reference"]["current_focus"] = "Old focus"
    existing["session"]["last_date"] = "2026-03-01T10:00:00+00:00"
    existing["session"]["stopped_at"] = "Old stop"
    existing["session"]["resume_file"] = "resume.md"
    existing["performance_metrics"]["rows"] = [
        {"label": "Phase 03 P01", "duration": "20m", "tasks": "4", "files": "2"}
    ]
    (planning / "state.json").write_text(json.dumps(existing, indent=2), encoding="utf-8")

    markdown_state = default_state_dict()
    markdown_state["position"]["current_phase"] = "03"
    markdown_state["position"]["status"] = "Executing"

    result = sync_state_json_core(cwd, generate_state_markdown(markdown_state))

    assert result["project_reference"]["core_research_question"] is None
    assert result["project_reference"]["current_focus"] is None
    assert result["session"]["last_date"] is None
    assert result["session"]["stopped_at"] is None
    assert result["session"]["resume_file"] is None
    assert result["performance_metrics"]["rows"] == []


def test_save_state_markdown_updates_markdown_and_json_together(tmp_path: Path) -> None:
    cwd = _bootstrap_project(tmp_path)
    planning = cwd / ".gpd"

    existing = default_state_dict()
    existing["position"]["current_phase"] = "01"
    existing["position"]["status"] = "Ready to plan"
    (planning / "state.json").write_text(json.dumps(existing, indent=2), encoding="utf-8")
    (planning / "STATE.md").write_text(generate_state_markdown(existing), encoding="utf-8")

    updated = default_state_dict()
    updated["position"]["current_phase"] = "02"
    updated["position"]["status"] = "Executing"
    md_content = generate_state_markdown(updated)

    result = save_state_markdown(cwd, md_content)
    stored = json.loads((planning / "state.json").read_text(encoding="utf-8"))

    assert (planning / "STATE.md").read_text(encoding="utf-8") == md_content
    assert result["position"]["current_phase"] == "02"
    assert stored["position"]["current_phase"] == "02"
    assert stored["position"]["status"] == "Executing"


def test_state_update_progress_ignores_orphan_summaries_and_caps_percent(tmp_path: Path) -> None:
    cwd = _bootstrap_project(tmp_path)
    planning = cwd / ".gpd"
    state = default_state_dict()
    state["position"]["current_phase"] = "01"
    state["position"]["total_phases"] = 2
    state["position"]["status"] = "Executing"
    (planning / "STATE.md").write_text(generate_state_markdown(state), encoding="utf-8")

    phase_one = planning / "phases" / "01-foundations"
    phase_one.mkdir(parents=True)
    (phase_one / "PLAN.md").write_text("# plan\n", encoding="utf-8")
    (phase_one / "SUMMARY.md").write_text("# summary\n", encoding="utf-8")

    phase_two = planning / "phases" / "02-orphan-summary"
    phase_two.mkdir(parents=True)
    (phase_two / "SUMMARY.md").write_text("# orphan summary\n", encoding="utf-8")

    result = state_update_progress(cwd)

    assert result.updated is True
    assert result.completed == 1
    assert result.total == 1
    assert result.percent == 100


def test_state_validate_allows_pristine_default_convention_lock(tmp_path: Path) -> None:
    cwd = _bootstrap_project(tmp_path)
    planning = cwd / ".gpd"
    state = default_state_dict()
    (planning / "STATE.md").write_text(generate_state_markdown(state), encoding="utf-8")
    (planning / "state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")

    result = state_validate(cwd)

    assert result.valid is True
    assert not any("convention_lock" in issue for issue in result.issues)
    assert not any("convention_lock" in warning for warning in result.warnings)
