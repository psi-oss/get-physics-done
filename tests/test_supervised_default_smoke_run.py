"""Phase 9 — shallow-mode roadmap and standard-mode Next-Up ordering contract.

All other supervised-default invariants are covered by dedicated phase tests
(see test_config.py, test_onboarding_surfaces.py, test_planner_backtracks_
consultation.py, test_execute_phase_claim_deliverable_precheck.py,
test_dense_cadence_gates.py, test_checkpoint_ux_convention.py,
test_progress_watch.py, test_record_backtrack.py, test_undo_backtrack_hook.py,
test_cli_contract_alignment.py).
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS_DIR = REPO_ROOT / "src" / "gpd" / "specs" / "workflows"


def _section_from_last_marker(text: str, marker: str) -> str:
    start = text.rindex(marker)
    next_heading = text.find("\n## ", start + len(marker))
    if next_heading == -1:
        return text[start:]
    return text[start:next_heading]


def test_new_project_emits_shallow_roadmap_and_standard_next_up_order() -> None:
    """gpd:new-project must (a) offer shallow-mode where Phase 1 is detailed
    and Phases 2+ are stubs, and (b) in standard mode prioritize
    ``gpd:plan-phase 1`` over ``gpd:discuss-phase 1`` in the Next-Up block."""
    new_project = (WORKFLOWS_DIR / "new-project.md").read_text(encoding="utf-8")

    assert "<shallow_mode>true</shallow_mode>" in new_project

    standard_next_up = _section_from_last_marker(new_project, "## > Next Up")
    plan_idx = standard_next_up.index("`gpd:plan-phase 1`")
    discuss_idx = standard_next_up.index("`gpd:discuss-phase 1`")
    assert plan_idx < discuss_idx
