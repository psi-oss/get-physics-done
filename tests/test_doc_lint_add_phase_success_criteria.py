"""Fast doc-lint ensuring add-phase command docs document success criteria."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_add_phase_has_success_criteria() -> None:
    text = (REPO_ROOT / "src/gpd/commands/add-phase.md").read_text(encoding="utf-8")
    assert "<success_criteria>" in text
    assert "</success_criteria>" in text
