"""Focused assertions for the verify-work checker routing seam."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VERIFY_WORK = REPO_ROOT / "src" / "gpd" / "specs" / "workflows" / "verify-work.md"


def test_verify_work_routes_on_structured_checker_statuses() -> None:
    workflow = VERIFY_WORK.read_text(encoding="utf-8")

    assert "route on `gpd_return.status` and the structured plan lists" in workflow
    assert "- `completed`: treat the fresh fix plans as verified only after the on-disk files still match the planner's `files_written` set." in workflow
    assert (
        "- `checkpoint`: some plans are approved and others need revision; record `approved_plans` and `blocked_plans`"
        in workflow
    )
    assert "- `blocked`: nothing is approved; feed the checker issues and blocked plan IDs back into the revision loop without rewriting approved plans." in workflow
    assert "- `failed`: present the issues and offer retry or manual revision." in workflow


def test_verify_work_references_one_shot_checker_contract_in_the_gap_closure_loop() -> None:
    workflow = VERIFY_WORK.read_text(encoding="utf-8")

    assert "this checker is single-shot." in workflow
    assert "Do not keep the same checker run open across user interaction." in workflow
    assert "use the structured `approved_plans`, `blocked_plans`, and `issues` fields" in workflow
    assert "Use the structured fields, not the human-readable approval table, as the source of truth." in workflow
