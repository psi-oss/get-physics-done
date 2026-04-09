"""Routing regressions for the `plan-phase` checker seam."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PLAN_PHASE = REPO_ROOT / "src/gpd/specs/workflows/plan-phase.md"


def test_plan_phase_separates_planner_checkpoint_handling_from_checker_revision() -> None:
    source = PLAN_PHASE.read_text(encoding="utf-8")

    assert "## 9b. Handle Planner Checkpoint" in source
    assert "spawn a fresh `gpd-planner` continuation handoff" in source
    assert "Do not route planner checkpoints into the checker revision loop." in source
    assert "Only after the planner returns `completed` should the workflow advance to checker review." in source
    assert "Present to user, get response, spawn continuation (step 12)" not in source


def test_plan_phase_routes_checker_statuses_through_structured_fields() -> None:
    source = PLAN_PHASE.read_text(encoding="utf-8")

    assert "`gpd_return.status: completed`" in source
    assert "`gpd_return.status: checkpoint`" in source
    assert "`gpd_return.status: blocked`" in source
    assert "`gpd_return.status: failed`" in source
    assert "Record approved plans from the structured `approved_plans` list only." in source
    assert "Record blocked plans from the structured `blocked_plans` list only." in source
    assert "Approved Plans (ready for execution)" not in source
    assert 'Approved Plans" table' not in source
    assert "plan-ID reconciliation" in source


def test_plan_phase_fails_closed_on_plan_id_mismatch_before_accepting_checker_success() -> None:
    source = PLAN_PHASE.read_text(encoding="utf-8")

    assert "`approved_plans` names only readable `*-PLAN.md` artifacts in `FRESH_PLAN_FILES`" in source
    assert "`blocked_plans` is empty" in source
    assert "every approved plan file still exists and matches the approved plan IDs" in source
    assert "Reject the return if any listed plan ID does not map to a readable `*-PLAN.md` file in `FRESH_PLAN_FILES`." in source
    assert "send the checker output back through the revision loop as a fail-closed mismatch" in source


def test_plan_phase_reloads_each_stage_and_validates_only_fresh_plan_files() -> None:
    source = PLAN_PHASE.read_text(encoding="utf-8")

    assert "bind_plan_phase_init() {" in source
    assert 'bind_plan_phase_init "$INIT"' in source
    assert 'gpd --raw init plan-phase "$PHASE" --stage research_routing' in source
    assert 'gpd --raw init plan-phase "$PHASE" --stage planner_authoring' in source
    assert 'gpd --raw init plan-phase "$PHASE" --stage checker_revision' in source
    assert 'FRESH_PLAN_FILES=$(echo "$PLANNER_RETURN" | gpd json list .gpd_return.files_written --default "")' in source
    assert 'for plan_file in $FRESH_PLAN_FILES;' in source
    assert 'PLANS_CONTENT=""' in source
    assert "Before the checker loop, validate only the fresh plan artifacts named by the planner return:" in source


def test_plan_phase_researcher_checkpoint_path_is_a_fresh_continuation_handoff() -> None:
    source = PLAN_PHASE.read_text(encoding="utf-8")

    assert "## 5.1 Handle Researcher Checkpoint" in source
    assert "Continue research as a fresh continuation handoff for Phase {phase_number}: {phase_name}" in source
    assert "<checkpoint_response>" in source
    assert 'description="Continue research Phase {phase_number}"' in source
    assert "{phase_dir}/{phase_number}-RESEARCH.md" in source
    assert "{phase_dir}/{phase}-RESEARCH.md" not in source
    assert "After the continuation returns, rerun the same `gpd_return.files_written` and on-disk artifact gate above before advancing." in source


def test_plan_phase_wrapper_stays_routing_only() -> None:
    command = (REPO_ROOT / "src/gpd/commands/plan-phase.md").read_text(encoding="utf-8")

    assert "@{GPD_INSTALL_DIR}/workflows/plan-phase.md" in command
    assert "Canonical contract schema and hard validation rules load later at the staged planner and checker handoffs" not in command
    assert "For proof-bearing work, every proof-bearing plan must surface the theorem statement" not in command
