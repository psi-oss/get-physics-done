"""Prompt-visible Next Up heading invariants."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_DIR = REPO_ROOT / "src/gpd/commands"
AGENTS_DIR = REPO_ROOT / "src/gpd/agents"
WORKFLOWS_DIR = REPO_ROOT / "src/gpd/specs/workflows"
TEMPLATES_DIR = REPO_ROOT / "src/gpd/specs/templates"


def test_prompt_markdown_uses_canonical_next_up_heading() -> None:
    offenders: list[str] = []

    for root in (COMMANDS_DIR, AGENTS_DIR, WORKFLOWS_DIR, TEMPLATES_DIR):
        for path in sorted(root.rglob("*.md")):
            for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                stripped = line.strip()
                if stripped.startswith("##") and "Next Up" in stripped and stripped != "## > Next Up":
                    offenders.append(f"{path.relative_to(REPO_ROOT)}:{line_number}:{line}")

    assert offenders == []


def test_prompt_markdown_avoids_bang_bang_headings() -> None:
    offenders: list[str] = []

    for root in (COMMANDS_DIR, AGENTS_DIR, WORKFLOWS_DIR, TEMPLATES_DIR):
        for path in sorted(root.rglob("*.md")):
            for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if line.strip().startswith("## !!"):
                    offenders.append(f"{path.relative_to(REPO_ROOT)}:{line_number}:{line}")

    assert offenders == []
