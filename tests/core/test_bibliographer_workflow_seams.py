from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / "src" / "gpd" / "specs" / "workflows"


def _workflow(name: str) -> str:
    return (WORKFLOWS_DIR / name).read_text(encoding="utf-8")


def test_write_paper_bibliographer_step_routes_on_typed_return_contract() -> None:
    workflow = _workflow("write-paper.md")

    assert "Return BIBLIOGRAPHY UPDATED or CITATION ISSUES FOUND." not in workflow
    assert "Return a typed `gpd_return` envelope." in workflow
    assert "Use `status: completed` when the bibliography task finished" in workflow
    assert "Do not proceed to strict review, reproducibility-manifest generation, or final review until" in workflow
    assert "Bibliography: `{ACTIVE_BIBLIOGRAPHY_PATH}`" in workflow
    assert "A completed return must always list `${PAPER_DIR}/CITATION-AUDIT.md` and `GPD/references-status.json` in `gpd_return.files_written`; list `{ACTIVE_BIBLIOGRAPHY_PATH}` only when the bibliography file changed." in workflow
    assert "**If the bibliographer completed with issues recorded in the audit report or `GPD/references-status.json`:**" in workflow
    assert "**If the bibliographer completed cleanly with no remaining citation issues:**" in workflow


def test_literature_review_bibliographer_step_routes_on_typed_return_contract() -> None:
    workflow = _workflow("literature-review.md")

    assert "Return BIBLIOGRAPHY UPDATED or CITATION ISSUES FOUND." not in workflow
    assert "Return a typed `gpd_return` envelope." in workflow
    assert "Use `status: completed` when the bibliography task finished" in workflow
    assert "**If the bibliographer completed with issues recorded in the audit report:**" in workflow
    assert "Proceed only after the fresh citation-audit gate passes." in workflow
    assert "**If BIBLIOGRAPHY UPDATED:**" not in workflow


def test_explain_bibliographer_step_routes_on_typed_return_contract() -> None:
    workflow = _workflow("explain.md")

    assert "Return `BIBLIOGRAPHY UPDATED` if all references are verified or corrected." not in workflow
    assert "Return `CITATION ISSUES FOUND` if any references remain uncertain or invalid." not in workflow
    assert "Return a typed `gpd_return` envelope." in workflow
    assert "Use `status: completed` when the audit finished" in workflow
    assert "If the bibliographer completed with issues recorded in the audit report:" in workflow
