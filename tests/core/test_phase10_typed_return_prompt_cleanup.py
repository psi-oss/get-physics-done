"""Focused regressions for Phase 10 typed-return prompt cleanup."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ROADMAPPER = REPO_ROOT / "src/gpd/agents/gpd-roadmapper.md"
PLANNER = REPO_ROOT / "src/gpd/agents/gpd-planner.md"
PHASE_RESEARCHER = REPO_ROOT / "src/gpd/agents/gpd-phase-researcher.md"
EXECUTOR_COMPLETION = REPO_ROOT / "src/gpd/specs/references/execution/executor-completion.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_roadmapper_prompt_example_includes_required_base_return_fields() -> None:
    roadmapper = _read(ROADMAPPER)

    assert "gpd_return:" in roadmapper
    assert "status: completed | checkpoint | blocked | failed" in roadmapper
    assert "files_written: [GPD/ROADMAP.md, GPD/STATE.md]" in roadmapper
    assert "issues: [list of issues encountered, if any]" in roadmapper
    assert "next_actions: [list of recommended follow-up actions]" in roadmapper
    assert "phases_created: {count}" in roadmapper
    assert "base fields (status, files_written, issues, next_actions)" not in roadmapper


def test_planner_tangent_guidance_routes_on_typed_checkpoint_status() -> None:
    planner = _read(PLANNER)

    assert "return `gpd_return.status: checkpoint` with the four options above instead of silently branching." in planner
    assert (
        "create the recommended main-line plan only and set `gpd_return.status: checkpoint` when multiple live alternatives still matter."
        in planner
    )
    assert "return `## CHECKPOINT REACHED` with the four options above instead of silently branching." not in planner
    assert "return `## CHECKPOINT REACHED` when multiple live alternatives still matter." not in planner


def test_phase_researcher_machine_readable_return_is_typed_first() -> None:
    researcher = _read(PHASE_RESEARCHER)

    assert "gpd_return:" in researcher
    assert "status: completed | checkpoint | blocked | failed" in researcher
    assert "files_written: [$PHASE_DIR/$PADDED_PHASE-RESEARCH.md]" in researcher
    assert "issues: [list of issues encountered, if any]" in researcher
    assert "next_actions: [list of recommended follow-up actions]" in researcher
    assert "confidence: HIGH | MEDIUM | LOW" in researcher
    assert "Mapping: RESEARCH COMPLETE → completed, RESEARCH BLOCKED → blocked" not in researcher
    assert "Headings above are presentation only; route on gpd_return.status." in researcher


def test_executor_completion_spawned_handoff_example_keeps_base_fields_and_extensions() -> None:
    completion = _read(EXECUTOR_COMPLETION)

    assert "status: completed | checkpoint | blocked | failed" in completion
    assert 'files_written: ["GPD/phases/XX-name/{phase}-{plan}-SUMMARY.md"]' in completion
    assert "issues: [list of issues encountered, if any]" in completion
    assert "next_actions: [list of recommended follow-up actions]" in completion
    assert "state_updates: [...]" in completion
    assert "contract_updates: [...]" in completion
    assert "decisions: [...]" in completion
    assert "blockers: [...]" in completion
    assert "continuation_update: {...}" in completion
