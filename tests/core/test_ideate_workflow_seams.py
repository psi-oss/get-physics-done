"""Focused regressions for the Phase 2 ideate workflow seam."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_DIR = REPO_ROOT / "src" / "gpd" / "commands"
WORKFLOWS_DIR = REPO_ROOT / "src" / "gpd" / "specs" / "workflows"
IDEATE_COMMAND = COMMANDS_DIR / "ideate.md"
IDEATE_WORKFLOW = WORKFLOWS_DIR / "ideate.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _contains_any(content: str, *phrases: str) -> bool:
    return any(phrase in content for phrase in phrases)


def _contains_all(content: str, *phrases: str) -> bool:
    return all(phrase in content for phrase in phrases)


def _step_body(content: str, step_name: str) -> str:
    marker = f'<step name="{step_name}">'
    start = content.index(marker) + len(marker)
    end = content.index("</step>", start)
    return content[start:end]


def test_ideate_command_stays_thin_and_leaves_round_orchestration_to_the_workflow() -> None:
    command = _read(IDEATE_COMMAND)

    assert "@{GPD_INSTALL_DIR}/workflows/ideate.md" in command
    assert "Execute the ideate workflow from @{GPD_INSTALL_DIR}/workflows/ideate.md end-to-end." in command
    assert "Keep the wrapper thin." in command
    assert "The execution context owns round orchestration, worker fan-out, synthesis, and user gating." in command
    assert "<spawn_contract>" not in command
    assert 'subagent_type="gpd-ideation-worker"' not in command
    assert "fresh continuation" not in command
    assert "gpd_return.status" not in command
    assert "shareable_thoughts" not in command
    assert "GPD/ideation/" not in command


def test_ideate_workflow_keeps_the_launch_summary_and_approval_surface_before_rounds() -> None:
    workflow = _read(IDEATE_WORKFLOW)

    assert _contains_any(workflow, "## Phase 2: Ideation Launch", "## Ideation Launch")

    for fragment in (
        "| Idea |",
        "| Outcome |",
        "| Anchors |",
        "| Constraints |",
        "| Risks / Open Questions |",
        "| Execution Preferences |",
    ):
        assert fragment in workflow

    assert _contains_any(
        workflow,
        'question: "Does this look right before I start the ideation rounds?"',
        'question: "Does this look right before I start the bounded ideation round?"',
    )

    for fragment in ("Start ideation", "Adjust launch", "Review raw context", "Stop here"):
        assert fragment in workflow

    assert _contains_any(
        workflow,
        "Continue directly into the bounded round loop. Do not stop at a launch-packet-only state.",
        "continue immediately into the bounded multi-agent round loop",
    )


def test_ideate_workflow_owns_bounded_rounds_one_shot_workers_and_the_default_hard_critic() -> None:
    workflow = _read(IDEATE_WORKFLOW)

    assert _contains_any(
        workflow,
        "Run one bounded ideation round at a time.",
        "The bounded ideation round structure is:",
    )
    assert _contains_any(
        workflow,
        "Spawn ideation workers as one-shot handoffs.",
        "2. `round_fanout` -- spawn the one-shot ideation workers for this round",
        "2. fan out to one-shot ideation workers",
    )
    assert 'subagent_type="gpd-ideation-worker"' in workflow
    assert _contains_any(
        workflow,
        "ideation workers are one-shot handoffs",
        "This is a one-shot handoff.",
    )
    assert _contains_any(
        workflow,
        "Reserve one default hard-critic lane unless the user overrides it.",
        "Keep one lane reserved as the hard critic by default unless the user explicitly overrides it.",
        "if the user did not override it, assign one agent as the hard critic for every round",
    )
    assert _contains_any(
        workflow,
        "If you are the hard critic, pressure-test assumptions, contradictions, missing baselines, and weak causal stories.",
        "Rounds are one-shot, use a default hard critic unless overridden",
    )


def test_ideate_workflow_keeps_the_round_user_gate_and_fresh_continuation_contract() -> None:
    workflow = _read(IDEATE_WORKFLOW)

    assert _contains_any(
        workflow,
        "After each round, present the compact round synthesis first. Raw round details are review-on-demand.",
        "After each round, present a compact round summary and route through the bounded review gate.",
    )

    for fragment in (
        "Continue to next round",
        "Add my thoughts",
        "Adjust configuration",
        "Review raw round",
        "Pause/Stop",
    ):
        assert fragment in workflow

    assert "If the user adds thoughts or adjusts configuration, treat that as a fresh continuation" in workflow
    assert _contains_any(
        workflow,
        "rather than resuming workers in place.",
        "Do not resume a prior child run.",
    )
    assert _contains_any(
        workflow,
        "Rebuild the next round brief from the approved launch brief, prior round syntheses, and the new user input, then spawn a fresh set of one-shot workers.",
        "if user input is required, surface it at the parent round gate and spawn a fresh worker on the next round",
    )


def test_ideate_phase2_stays_fileless_and_does_not_claim_durable_session_artifacts() -> None:
    workflow = _read(IDEATE_WORKFLOW)

    assert _contains_any(
        workflow,
        "This phase keeps orchestration in memory and does not create durable session artifacts or ideation files.",
        "Keep orchestration in memory for this run.",
        "Keep orchestration in memory for this phase.",
    )
    assert _contains_any(
        workflow,
        "Do not create durable ideation session files or artifact directories in this phase.",
        "Do not create durable ideation session files, dedicated ideation directories under `GPD/`, tag ledgers, or document-library state in this phase.",
        "Do not create durable session artifacts",
    )
    assert _contains_any(
        workflow,
        "Approval starts bounded ideation rounds, but it does not create durable session files.",
        "This run keeps ideation state in memory. It does not create or update durable session files in this phase.",
    )
    assert _contains_any(
        workflow,
        "Do not add `<spawn_contract>` blocks for Phase 2.",
        "Do not create files or claim durable session ownership in this phase.",
    )
    assert _contains_any(
        workflow,
        "Child work is fileless and return-only here.",
        "Do not rely on `gpd_return.files_written` in this phase.",
        "Do not invent durable artifact checks here because this phase intentionally avoids file-producing ideation workers.",
    )
    assert "\n<spawn_contract>\n" not in workflow
    assert "\n</spawn_contract>\n" not in workflow
    assert "session.json" not in workflow
    assert _contains_any(
        workflow,
        "Do not create durable ideation session files or artifact directories in this phase.",
        "Do not create durable ideation session files, subgroup files, or artifact directories in this phase.",
        "Do not promise durable subgroup transcripts, promotion, spawn contracts, `GPD/ideation/` state, resumable subgroup persistence, GPD/ideation state, or ideation files in this phase.",
    )
    assert _contains_any(
        workflow,
        "The summary in this phase is conversational and in-memory only. Do not claim durable ideation history, resumable session files, tags, imported-document state, or archived artifacts.",
        "The summary in this phase is conversational and in-memory only. Do not claim durable ideation history, subgroup transcripts, resumable session files, tags, imported-document state, or archived artifacts.",
        "No durable ideation session files, artifact directories, tag ledgers, or document-library claims are required in Phase 2",
    )


def test_ideate_workflow_allows_temporary_subgroup_creation_only_from_the_parent_round_gate() -> None:
    workflow = _read(IDEATE_WORKFLOW)
    gate = _step_body(workflow, "round_review_gate")
    subgroup_loop = _step_body(workflow, "subgroup_micro_loop")

    assert "Adjust configuration" in gate
    assert "temporary subgroup batch" in gate
    assert _contains_all(
        subgroup_loop,
        "existing parent round gate",
        "Adjust configuration",
        "Do not create them at launch, mid-worker, or automatically.",
    )
    assert _contains_any(
        subgroup_loop,
        "Subgroups are optional and only user-initiated from the existing parent round gate.",
        "only user-initiated from the existing parent round gate",
    )
    assert _contains_any(
        subgroup_loop,
        "Route subgroup setup through `Adjust configuration` so the main gate stays stable.",
        "Route subgroup setup through `Adjust configuration`",
    )


def test_ideate_workflow_runs_subgroups_as_bounded_nested_one_shot_rounds() -> None:
    workflow = _read(IDEATE_WORKFLOW)
    subgroup_loop = _step_body(workflow, "subgroup_micro_loop")

    assert _contains_all(
        subgroup_loop,
        "subgroup rounds must stay bounded",
        "default to `2`",
        "`1-3` rounds",
    )
    assert _contains_all(
        subgroup_loop,
        "pause main-loop progression",
        "reuse fresh one-shot `gpd-ideation-worker` handoffs for subgroup lanes",
        "do not create a long-lived child conversation",
    )
    assert _contains_all(
        subgroup_loop,
        "Keep one active subgroup batch at a time in this phase.",
        "return to the parent gate",
        "launch another subgroup batch explicitly",
    )
    assert _contains_any(
        subgroup_loop,
        "if a subgroup lane needs user input, surface it at the parent gate as a fresh continuation rather than waiting in place",
        "surface it at the parent gate as a fresh continuation rather than waiting in place",
    )
    assert "subgroup rounds" in workflow
    assert "one-shot" in workflow


def test_ideate_workflow_reintegrates_subgroup_output_by_summary_without_persistence_or_promotion() -> None:
    workflow = _read(IDEATE_WORKFLOW)
    subgroup_loop = _step_body(workflow, "subgroup_micro_loop")

    assert _contains_all(
        subgroup_loop,
        "At subgroup completion, synthesize one compact rejoin packet instead of replaying raw subgroup transcripts.",
        "Rejoin is summary-only in this phase.",
        "Fold only that subgroup summary into the main shared discussion",
    )
    for fragment in (
        "strongest idea",
        "strongest critique",
        "what changed for the main discussion",
        "remaining open question",
    ):
        assert fragment in subgroup_loop
    assert _contains_any(
        subgroup_loop,
        "Do not auto-start the next main round after subgroup completion.",
        "Do not auto-start the next main round",
    )
    assert _contains_all(
        subgroup_loop,
        "Subgroup execution stays fileless in this phase.",
        "do not create durable subgroup transcripts",
        "subgroup promotion",
    )
    assert "\n<spawn_contract>\n" not in workflow
    assert _contains_any(
        subgroup_loop,
        "independent subgroup sessions",
        "promotion to independent sessions",
    )
    assert "gpd_return.files_written" not in workflow
