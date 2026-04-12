"""Prompt hygiene tests guarding terminal prompt sections and return headings."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO_ROOT / "src" / "gpd" / "agents"
TEMPLATES_DIR = REPO_ROOT / "src" / "gpd" / "specs" / "templates"
ISSUE_04_TERMINAL_SECTION_CASES = [
    ("src/gpd/specs/workflows/verify-work.md", "</success_criteria>"),
    ("src/gpd/agents/gpd-project-researcher.md", "</success_criteria>"),
    ("src/gpd/specs/workflows/derive-equation.md", "</success_criteria>"),
    ("src/gpd/specs/workflows/plan-phase.md", "</success_criteria>"),
    ("src/gpd/specs/workflows/execute-phase.md", "</resumption>"),
    ("src/gpd/commands/new-project.md", "</output>"),
]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _tail_after_terminal_marker(content: str, marker: str) -> str:
    _, found, tail = content.rpartition(marker)
    assert found, f"missing terminal marker {marker!r}"
    return tail


def _marker_position(content: str, marker: str) -> int:
    position = content.find(marker)
    assert position != -1, f"missing marker {marker!r}"
    return position


def test_continuation_prompt_template_heading_is_unique() -> None:
    content = _read(TEMPLATES_DIR / "continuation-prompt.md")
    assert content.count("## Continuation Template") == 1


@pytest.mark.parametrize(
    ("agent", "heading"),
    [
        ("gpd-experiment-designer.md", "## Experiment Design Return Format"),
        ("gpd-notation-coordinator.md", "## Convention Return Format"),
    ],
)
def test_agent_return_headings_are_unique(agent: str, heading: str) -> None:
    content = _read(AGENTS_DIR / agent)
    assert content.count(heading) == 1


@pytest.mark.parametrize(
    ("relative_path", "terminal_marker"),
    ISSUE_04_TERMINAL_SECTION_CASES,
)
def test_issue_04_prompt_sources_end_at_terminal_sections(
    relative_path: str,
    terminal_marker: str,
) -> None:
    content = _read(REPO_ROOT / relative_path)
    live_tail = _tail_after_terminal_marker(content, terminal_marker).strip()
    assert not live_tail, (
        f"{relative_path} leaks model-visible trailing content after "
        f"{terminal_marker!r}: {live_tail[:120]!r}"
    )


def test_project_researcher_shared_infrastructure_stays_outside_structured_returns() -> None:
    content = _read(AGENTS_DIR / "gpd-project-researcher.md")
    structured_returns_open = _marker_position(content, "<structured_returns>")
    structured_returns_close = _marker_position(content, "</structured_returns>")
    shared_infrastructure_open = _marker_position(content, "<shared_infrastructure>")
    shared_infrastructure_close = _marker_position(content, "</shared_infrastructure>")
    success_criteria_open = _marker_position(content, "<success_criteria>")

    assert (
        structured_returns_open
        < structured_returns_close
        < shared_infrastructure_open
        < shared_infrastructure_close
        < success_criteria_open
    )
