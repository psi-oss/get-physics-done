"""Focused regressions for the Phase 4 ideate workflow seam."""

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


def _contains_any_lower(content: str, *phrases: str) -> bool:
    lowered = content.lower()
    return any(phrase.lower() in lowered for phrase in phrases)


def _contains_in_order_lower(content: str, *phrases: str) -> bool:
    lowered = content.lower()
    cursor = 0
    for phrase in phrases:
        idx = lowered.find(phrase.lower(), cursor)
        if idx < 0:
            return False
        cursor = idx + len(phrase)
    return True


def _step_body(content: str, step_name: str) -> str:
    marker = f'<step name="{step_name}"'
    start = content.index(marker)
    start = content.index(">", start) + 1
    end = content.index("</step>", start)
    return content[start:end]


def test_ideate_command_stays_thin_projectless_and_workflow_owned() -> None:
    command = _read(IDEATE_COMMAND)

    assert "name: gpd:ideate" in command
    assert "context_mode: projectless" in command
    assert "@{GPD_INSTALL_DIR}/workflows/ideate.md" in command
    assert "Execute the ideate workflow from @{GPD_INSTALL_DIR}/workflows/ideate.md end-to-end." in command
    assert _contains_any_lower(
        command,
        "keep the wrapper thin and public-facing.",
        "keep the wrapper thin.",
    )
    assert _contains_any_lower(
        command,
        "the execution context owns orchestration details, worker fan-out, synthesis, and any internal control flow.",
        "the execution context owns round orchestration, worker fan-out, synthesis, and user gating.",
        "the execution context owns orchestration",
    )
    assert _contains_any_lower(
        command,
        "do not center or enumerate internal approval loops, bounded rounds, review gates, subgroup mechanics, or other workflow-specific control surfaces in the public command contract.",
        "the public wrapper does not foreground internal approval loops",
    )

    for forbidden in (
        "<spawn_contract>",
        'subagent_type="gpd-ideation-worker"',
        "gpd_return.status",
        "shareable_thoughts",
    ):
        assert forbidden not in command


def test_ideate_surface_locks_the_projectless_opt_in_context_and_non_durable_boundary() -> None:
    command = _read(IDEATE_COMMAND)
    workflow = _read(IDEATE_WORKFLOW)
    optional_context_pull = _step_body(workflow, "optional_context_pull")
    combined = f"{command}\n{workflow}"

    assert "context_mode: projectless" in command
    assert _contains_any_lower(
        command,
        "existing `gpd/` project files are optional supporting context only.",
        "existing gpd project files are optional supporting context only.",
    )
    assert _contains_any_lower(
        command,
        "do not read them unless the user explicitly asks for specific files or artifacts to be included.",
        "do not read them unless the user explicitly asks",
    )
    assert "Do not auto-read project files or local documents." in optional_context_pull
    assert _contains_any_lower(
        optional_context_pull,
        "only if the user explicitly asks to include existing context",
        "read only those named artifacts",
    )
    assert _contains_any_lower(
        combined,
        "projectless conversational multi-agent research session",
        "conversational multi-agent research session",
        "keep orchestration in memory",
        "in-memory session",
        "does not create durable session artifacts",
        "do not create durable ideation session files",
    )
    assert _contains_any_lower(
        combined,
        "`research.md`",
        "`gpd/ideation/`",
        "transcript storage or replay",
        "session ids",
        "`resume-work`",
        "resume-work integration",
    )
    assert "session.json" not in combined.lower()
    assert "\n<spawn_contract>\n" not in workflow
    assert "\n</spawn_contract>\n" not in workflow


def test_ideate_surface_keeps_room_for_research_style_discussion_without_auto_promoting_to_project_work() -> None:
    command = _read(IDEATE_COMMAND)
    workflow = _read(IDEATE_WORKFLOW)
    combined = f"{command}\n{workflow}"

    assert _contains_any_lower(
        combined,
        "scientific problem or open discussion space",
        "open-ended discussion space",
        "open-ended discussion instead of a sharply scoped problem",
        "shared discussion",
    )
    assert _contains_any_lower(
        combined,
        "research-oriented",
        "literature-aware",
        "scientific question or domain",
    )
    assert _contains_any_lower(
        combined,
        "before durable project work",
        "before committing to durable project artifacts",
        "before deciding whether it should become durable project work",
    )
    assert _contains_any_lower(
        combined,
        "projectless and lightweight",
        "starts projectlessly from any folder",
        "context_mode: projectless",
    )


def test_ideate_workflow_keeps_a_launch_brief_seam_before_rounds() -> None:
    workflow = _read(IDEATE_WORKFLOW)
    launch_summary = _step_body(workflow, "draft_launch_summary")

    assert _contains_any_lower(
        launch_summary,
        "pre-round launch brief",
        "working frame",
        "session brief",
    )
    assert _contains_any_lower(
        launch_summary,
        "focus",
        "core question",
        "open discussion framing",
    )
    assert _contains_any_lower(
        launch_summary,
        "outcome",
        "useful result",
    )
    assert _contains_any_lower(
        launch_summary,
        "anchors",
        "references",
        "prior outputs",
    )
    assert _contains_any_lower(
        launch_summary,
        "constraints",
        "boundaries",
        "exclusions",
    )
    assert _contains_any_lower(
        launch_summary,
        "risks / watchouts",
        "risks / open questions",
        "open questions",
        "weakest assumptions",
        "misleading directions",
    )
    assert _contains_any_lower(
        launch_summary,
        "only mention execution defaults here if the user explicitly shaped them",
        "execution preferences",
        "keep preset, posture, worker count, and roster defaults backstage",
    )
    assert _contains_any_lower(
        launch_summary,
        "keep the initial agent shape concise when shown",
        "initial agent shape concise",
        "roster defaults backstage",
    )
    assert _contains_any_lower(
        launch_summary,
        "starts the bounded multi-agent discussion turns",
        "starts the bounded discussion turns",
        "start a first bounded discussion turn",
        "starts ideation",
        "before i start the bounded multi-agent rounds",
    )
    assert _contains_any_lower(
        launch_summary,
        "does not create durable session files",
        "does not create durable ideation files",
    )


def test_ideate_launch_gate_stays_user_owned_allows_fast_start_and_can_be_lighter() -> None:
    workflow = _read(IDEATE_WORKFLOW)
    adaptive_clarification = _step_body(workflow, "adaptive_clarification")
    draft_launch_summary = _step_body(workflow, "draft_launch_summary")
    approval_gate = _step_body(workflow, "approval_gate")
    launch_path = "\n".join((adaptive_clarification, draft_launch_summary, approval_gate))

    assert _contains_any_lower(
        launch_path,
        "fast-start",
        "fast start",
        "i have enough to start a first bounded ideation round from this frame",
        "starting round 1",
    )
    assert _contains_any_lower(
        approval_gate,
        "two-path launch rule",
        "do not present a launch menu",
        "restat the short working frame compactly",
        "restate the short working frame compactly",
    )
    assert _contains_any_lower(
        approval_gate,
        "lighter fallback gate",
        "lightweight gate",
        "lighter gate",
        "keep the gate light",
    )
    assert _contains_any_lower(
        approval_gate,
        "raw launch details",
        "raw context",
        "review raw",
    )
    assert _contains_any_lower(
        approval_gate,
        "reopen only the section the user wants to revise",
        "preserve all unchanged sections by default",
        "adjust launch",
        "revise",
    )
    assert _contains_any_lower(
        approval_gate,
        "stop here",
        "stop cleanly",
        "end cleanly",
    )
    assert _contains_any_lower(
        approval_gate,
        "continue directly into the bounded round loop",
        "continue directly into the bounded multi-agent round loop",
        "say you are starting the first discussion turn",
        "start the first bounded round",
        "move straight into the bounded round loop",
    )
    assert _contains_any_lower(
        approval_gate,
        "what do you want to do before the first turn",
        "minimum pre-first-turn decision",
        "approved for launch",
    )
    assert _contains_any_lower(
        approval_gate,
        "rebuild the summary and return to the approval gate",
        "reopen only the section the user wants to revise",
    )
    assert _contains_any_lower(
        approval_gate,
        "no files were created and the research brief was not finalized",
        "no files were created",
    )


def test_ideate_intake_stays_research_native_and_keeps_early_config_secondary() -> None:
    workflow = _read(IDEATE_WORKFLOW)
    orient_and_parse = _step_body(workflow, "orient_and_parse")
    capture_core_brief = _step_body(workflow, "capture_core_brief")
    adaptive_clarification = _step_body(workflow, "adaptive_clarification")
    resolve_launch_preferences = _step_body(workflow, "resolve_launch_preferences")
    intake = "\n".join(
        (
            orient_and_parse,
            capture_core_brief,
            adaptive_clarification,
            resolve_launch_preferences,
        )
    )

    assert _contains_any_lower(
        orient_and_parse,
        "sharpen the question",
        "sharpen the research question",
        "clarify the research target",
        "clarify the question",
    )
    assert _contains_any_lower(
        orient_and_parse,
        "keep constraints in view",
        "keep constraints visible",
        "constraints in view",
    )
    assert "lock the brief" not in orient_and_parse.lower()

    assert _contains_any_lower(
        capture_core_brief,
        "scientific question or domain",
        "question or domain",
    )
    assert _contains_any_lower(
        capture_core_brief,
        "what outcome would be useful",
        "useful outcome",
    )
    assert _contains_any_lower(
        capture_core_brief,
        "references/examples/prior outputs",
        "references, examples, or prior outputs",
        "anchors / references / examples",
    )
    assert _contains_any_lower(
        capture_core_brief,
        "constraints or boundaries",
        "constraints / approximations / boundaries",
        "constraints or approximations",
    )
    assert "false progress" not in intake.lower()
    assert "real progress" not in intake.lower()
    assert _contains_any_lower(
        intake,
        "mislead",
        "miss the point",
        "dead end",
        "weak point",
    )

    assert _contains_any_lower(
        adaptive_clarification,
        "no clear outcome or useful end product",
        "no clear outcome",
    )
    assert _contains_any_lower(
        adaptive_clarification,
        "no anchor, baseline, reference, or prior output to keep visible",
        "no anchor",
    )
    assert _contains_any_lower(
        adaptive_clarification,
        "no explicit constraint or boundary",
        "no explicit constraint",
    )
    assert _contains_any_lower(
        adaptive_clarification,
        "weak point",
        "mislead",
        "dead end",
    )
    assert "no initial execution posture" not in adaptive_clarification.lower()
    assert "no usable agent count" not in adaptive_clarification.lower()
    assert "first, resolve the preset" not in adaptive_clarification.lower()
    assert "then resolve the worker count" not in adaptive_clarification.lower()

    assert _contains_any_lower(
        resolve_launch_preferences,
        "first-pass preferences",
        "launch preferences",
        "preferences",
        "lock now",
    )
    assert "temporary subgroup work should stay available" not in resolve_launch_preferences.lower()
    assert "specific next-round tasks" not in resolve_launch_preferences.lower()


def test_ideate_workflow_keeps_bounded_parent_owned_turns_agent_first_and_default_skepticism() -> None:
    workflow = _read(IDEATE_WORKFLOW)
    round_loop = _step_body(workflow, "run_round_loop")

    assert _contains_any_lower(
        round_loop,
        "begin the conversational multi-agent research session using the current bounded round engine.",
        "run one bounded ideation round at a time.",
        "run one bounded ideation round at a time under the hood.",
        "run one bounded round at a time.",
    )
    assert _contains_any_lower(
        round_loop,
        "present each bounded segment to the user as a conversational turn",
        "agent-first conversational turn loop",
        "conversational turn rather than a moderator-led round ceremony",
    )
    assert _contains_any_lower(
        round_loop,
        "spawn ideation workers as one-shot handoffs.",
        "one-shot handoffs",
    )
    assert 'subagent_type="gpd-ideation-worker"' in round_loop
    assert _contains_in_order_lower(
        round_loop,
        "round_bootstrap",
        "round_fanout",
        "round_collect",
        "bounded optional reaction handling",
        "synthesis/state update",
        "user handoff",
    )
    assert _contains_in_order_lower(
        round_loop,
        "agent contributions are the primary visible unit",
        "each active agent contributes a short research-facing message in the first pass",
        "allow one bounded optional reaction layer",
        "visible synthesis is secondary and lightweight",
        "end the turn with a conversational handoff",
    )
    assert _contains_any_lower(
        round_loop,
        "contribute one bounded agent perspective for discussion turn {round_number}",
        "bounded agent perspective",
    )
    assert _contains_any_lower(
        round_loop,
        "the parent workflow owns the launch brief, round counter, shared discussion, current configuration, and any fresh continuation handoff.",
        "the parent workflow owns the research brief, round counter, shared discussion, current configuration, and any fresh continuation handoff.",
        "the parent workflow owns the launch brief",
        "the parent workflow owns the research brief",
    )
    assert _contains_any_lower(
        round_loop,
        "hard critic",
        "skeptical reviewer",
    )
    assert _contains_any_lower(
        round_loop,
        "pressure-test assumptions, contradictions, missing baselines, and weak causal stories.",
        "high skepticism",
    )
    assert _contains_any_lower(
        round_loop,
        "typed `gpd_return` envelope",
        "route on typed `gpd_return.status`",
    )
    assert _contains_any_lower(
        round_loop,
        "no worker waits for user input in place.",
        "do not wait in place.",
    )
    assert _contains_any_lower(
        round_loop,
        "end each turn with a lightweight conversational handoff",
        "conversational handoff",
    )


def test_ideate_turn_checkpoint_preserves_user_control_reaction_layer_and_fresh_continuations() -> None:
    workflow = _read(IDEATE_WORKFLOW)
    round_loop = _step_body(workflow, "run_round_loop")
    round_review_gate = _step_body(workflow, "round_review_gate")

    assert _contains_any_lower(
        round_review_gate,
        "after each conversational turn, keep the user handoff light and natural.",
        "agent messages should already be on screen",
        "raw turn details remain review-on-demand.",
    )
    assert _contains_any_lower(
        round_review_gate,
        "do not present a rigid fixed menu by default",
        "makes these capabilities available in natural language",
    )
    assert _contains_any_lower(
        round_review_gate,
        "continue to the next bounded turn",
        "increment the round counter and run the next bounded ideation round",
        "run the next bounded ideation round under the hood",
    )
    assert _contains_any_lower(
        round_review_gate,
        "add or redirect with the user's own thoughts",
        "capture the user's injection",
        "user's injection",
        "include it in the next turn brief",
    )
    assert _contains_any_lower(
        round_review_gate,
        "capture only the requested changes",
        "preserve everything else",
        "requested changes such as preset",
    )
    assert _contains_any_lower(
        round_review_gate,
        "review raw turn details",
        "show the raw worker takeaways plus any compact synthesized view",
        "raw worker takeaways",
        "return to the same conversational handoff",
    )
    assert _contains_any_lower(
        round_review_gate,
        "pause or stop cleanly without claiming durable persistence",
        "pause or stop cleanly",
    )
    assert "temporary subgroup batch" in round_review_gate
    assert _contains_any_lower(
        round_review_gate,
        "treat that as a fresh continuation",
        "do not resume a prior child run.",
    )
    assert _contains_any_lower(
        round_review_gate,
        "rebuild the next round brief",
        "rebuild the next turn brief",
        "spawn a fresh worker on the next round",
    )
    assert _contains_any_lower(
        round_review_gate,
        "surface the ambiguity at the parent handoff",
        "surface the ambiguity in the conversational handoff",
    )
    assert _contains_any_lower(
        round_loop,
        "allow one bounded optional reaction layer",
        "fold in your reaction",
        "optional reaction layer",
    )


def test_ideate_round_review_surface_stays_synthesis_first_with_optional_raw_details() -> None:
    workflow = _read(IDEATE_WORKFLOW)
    round_loop = _step_body(workflow, "run_round_loop")
    round_review_gate = _step_body(workflow, "round_review_gate")
    subgroup_loop = _step_body(workflow, "subgroup_micro_loop")

    assert _contains_in_order_lower(
        round_loop,
        "each active agent contributes a short research-facing message in the first pass",
        "allow one bounded optional reaction layer",
        "visible synthesis is secondary and lightweight",
        "end the turn with a conversational handoff",
    )
    assert _contains_any_lower(
        round_loop,
        "synthesis/state update",
        "visible synthesis is secondary and lightweight",
    )
    assert _contains_any_lower(
        round_review_gate,
        "agent messages should already be on screen",
        "if a brief recap is helpful, make it compact and secondary",
        "raw turn details remain review-on-demand",
    )
    assert _contains_any_lower(
        round_review_gate,
        "raw worker takeaways plus any compact synthesized view",
        "return to the same conversational handoff",
    )
    assert _contains_any_lower(
        subgroup_loop,
        "synthesize one compact breakout recap instead of replaying raw subgroup transcripts",
        "rejoin is summary-only in this phase",
    )


def test_ideate_non_durable_contract_covers_rounds_subgroups_and_closeout() -> None:
    workflow = _read(IDEATE_WORKFLOW)
    orient_and_parse = _step_body(workflow, "orient_and_parse")
    round_loop = _step_body(workflow, "run_round_loop")
    subgroup_loop = _step_body(workflow, "subgroup_micro_loop")
    session_finish = _step_body(workflow, "session_finish")

    assert _contains_any_lower(
        orient_and_parse,
        "this phase keeps orchestration in memory and does not create durable session artifacts or ideation files.",
        "this is a projectless, in-memory research session",
    )
    assert _contains_any_lower(
        round_loop,
        "keep orchestration in memory for this phase.",
        "do not create durable ideation session files or artifact directories in this phase.",
        "do not create durable ideation session files, `research.md`, `gpd/ideation/`, or artifact directories in this phase.",
    )
    assert _contains_any_lower(
        subgroup_loop,
        "subgroup execution stays fileless in this phase.",
        "do not create durable subgroup transcripts",
    )
    assert _contains_any_lower(
        session_finish,
        "this v1 closeout is in-memory only.",
        "this projectless research-session closeout is in-memory only.",
        "do not add or imply durable ideation history",
    )

    for forbidden in ("session.json", "gpd_return.files_written"):
        assert forbidden not in workflow.lower()

    assert "\n<spawn_contract>\n" not in workflow
    assert "\n</spawn_contract>\n" not in workflow


def test_ideate_subgroups_stay_optional_parent_owned_bounded_and_summary_only() -> None:
    workflow = _read(IDEATE_WORKFLOW)
    subgroup_loop = _step_body(workflow, "subgroup_micro_loop")

    assert _contains_any_lower(
        subgroup_loop,
        "subgroups are optional focused breakouts and only user-initiated from the existing parent handoff.",
        "only user-initiated from the existing parent handoff",
    )
    assert _contains_any_lower(
        subgroup_loop,
        "route subgroup setup through the configuration-adjustment path so the main handoff stays stable.",
        "configuration-adjustment path",
    )
    assert _contains_any_lower(
        subgroup_loop,
        "subgroup rounds must stay bounded",
        "keep each subgroup batch to `1-3` rounds in this phase",
    )
    assert _contains_any_lower(
        subgroup_loop,
        "keep one active subgroup batch at a time in this phase.",
        "temporary parent-owned configuration change",
    )
    assert _contains_any_lower(
        subgroup_loop,
        "reuse fresh one-shot `gpd-ideation-worker` handoffs for subgroup lanes",
        "do not create a long-lived child conversation",
    )
    assert _contains_any_lower(
        subgroup_loop,
        "rejoin is summary-only in this phase.",
        "fold only that subgroup summary into the main shared discussion",
        "compact rejoin packet",
    )
    assert _contains_any_lower(
        subgroup_loop,
        "do not auto-start the next main round after subgroup completion.",
        "return to the normal parent handoff",
    )
    assert _contains_any_lower(
        subgroup_loop,
        "do not claim subgroup resumability",
        "independent subgroup sessions",
        "subgroup promotion",
    )


def test_ideate_closeout_keeps_a_structured_non_durable_next_step_exit() -> None:
    workflow = _read(IDEATE_WORKFLOW)
    round_review_gate = _step_body(workflow, "round_review_gate")
    session_finish = _step_body(workflow, "session_finish")

    assert _contains_any_lower(
        session_finish,
        "compact structured closeout summary",
        "structured closeout summary",
    )
    for fragment in (
        "main ideas explored",
        "unresolved disagreements or confusions",
        "promising next steps",
        "open questions",
        "suggested follow-up actions",
    ):
        assert fragment in session_finish

    assert "`What do you want to do next?`" in session_finish
    assert "non-GPD next step" in session_finish
    assert _contains_any_lower(
        round_review_gate,
        "keep the user handoff light and natural",
        "conversational handoff",
        "if you want, i can keep pushing on this line",
    )

    for fragment in ("gpd:suggest-next", "gpd:ideate [topic or question]", "gpd:new-project", "gpd:help --all"):
        assert fragment in session_finish

    assert _contains_any_lower(
        session_finish,
        "this v1 closeout is in-memory only.",
        "do not add or imply durable ideation history",
    )
    assert _contains_any_lower(
        session_finish,
        "lightweight and conversational",
        "also say plainly that the user can ask for a non-gpd next step instead",
    )
