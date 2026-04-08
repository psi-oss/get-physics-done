"""Tests for RES-565: community contribution prompts in paper workflows."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / "src" / "gpd" / "specs" / "workflows"


def _read(name: str) -> str:
    return (WORKFLOWS_DIR / name).read_text(encoding="utf-8")


def test_arxiv_submission_has_community_contribution_prompt() -> None:
    content = _read("arxiv-submission.md")
    assert "<community_contribution>" in content
    assert 'README.md "Papers Using GPD" list' in content
    assert "psi-oss/get-physics-done#papers-using-gpd" in content
    assert "examples gallery" not in content.lower()


def test_write_paper_has_community_contribution_prompt() -> None:
    content = _read("write-paper.md")
    assert "<community_contribution>" in content
    assert 'README.md "Papers Using GPD" list' in content
    assert "psi-oss/get-physics-done#papers-using-gpd" in content
    assert "examples gallery" not in content.lower()


def test_contribution_prompts_are_non_blocking() -> None:
    for name in ("arxiv-submission.md", "write-paper.md"):
        content = _read(name)
        assert "informational only" in content.lower()
        assert "do not block" in content.lower()


def test_contributing_guide_points_to_readme_papers_list() -> None:
    content = (REPO_ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    assert "Papers Using GPD" in content
    assert "examples gallery" not in content.lower()
