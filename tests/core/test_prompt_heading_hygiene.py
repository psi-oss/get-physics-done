"""Prompt hygiene tests guarding shared template and return headings."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO_ROOT / "src" / "gpd" / "agents"
TEMPLATES_DIR = REPO_ROOT / "src" / "gpd" / "specs" / "templates"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


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
