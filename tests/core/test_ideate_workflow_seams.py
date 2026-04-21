"""Focused regressions for the Phase 7 ideate workflow seams."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_DIR = REPO_ROOT / "src" / "gpd" / "commands"
AGENTS_DIR = REPO_ROOT / "src" / "gpd" / "agents"
WORKFLOWS_DIR = REPO_ROOT / "src" / "gpd" / "specs" / "workflows"
IDEATE_COMMAND = COMMANDS_DIR / "ideate.md"
IDEATION_WORKER = AGENTS_DIR / "gpd-ideation-worker.md"
IDEATE_WORKFLOW = WORKFLOWS_DIR / "ideate.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _contains_any(content: str, *phrases: str) -> bool:
    return any(phrase in content for phrase in phrases)


def _contains_any_lower(content: str, *phrases: str) -> bool:
    lowered = content.lower()
    return any(phrase.lower() in lowered for phrase in phrases)


def _contains_all_lower(content: str, *phrases: str) -> bool:
    lowered = content.lower()
    return all(phrase.lower() in lowered for phrase in phrases)


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


def _tag_body(content: str, tag_name: str) -> str:
    start_marker = f"<{tag_name}>"
    end_marker = f"</{tag_name}>"
    start = content.index(start_marker) + len(start_marker)
    end = content.index(end_marker, start)
    return content[start:end]


def _bullet_list_after_marker(content: str, marker: str) -> list[str]:
    lowered = content.lower()
    start = lowered.index(marker.lower()) + len(marker)
    bullets: list[str] = []

    for line in content[start:].splitlines():
        stripped = line.strip()
        if not stripped:
            if bullets:
                break
            continue
        if stripped.startswith("- "):
            bullets.append(stripped[2:])
            continue
        if bullets:
            break

    return bullets


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


def test_ideate_workflow_keeps_a_light_launch_seam_before_rounds() -> None:
    workflow = _read(IDEATE_WORKFLOW)
    launch_summary = _step_body(workflow, "draft_launch_summary")

    assert _contains_any_lower(
        launch_summary,
        "keeps the launch light",
        "short paraphrase",
        "short launch line",
        "short launch restatement",
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
        "working frame internal",
        "keep the working frame internal",
        "internal working frame",
        "move directly into the first agent turn",
        "move directly into the first bounded discussion turn",
    )
    assert _contains_any_lower(
        launch_summary,
        "only mention execution defaults here if the user explicitly shaped them",
        "only surface execution preferences if the user explicitly shaped them",
        "execution preferences",
        "keep preset, posture, worker count, and roster defaults backstage",
    )
    assert _contains_any_lower(
        launch_summary,
        "launch line",
        "short paraphrase",
        "start a first bounded discussion turn",
        "start the first agent turn",
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
        "short paraphrase",
        "short launch line",
        "compact restatement",
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
        "raw-context review remains available on demand",
        "raw launch details remain available on demand",
        "do not force it as a standard visible option",
        "do not make raw review a default visible option",
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
        "move directly into the first agent turn",
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
    draft_launch_summary = _step_body(workflow, "draft_launch_summary")
    intake = "\n".join(
        (
            orient_and_parse,
            capture_core_brief,
            adaptive_clarification,
            resolve_launch_preferences,
        )
    )
    config_surface = "\n".join((resolve_launch_preferences, draft_launch_summary))

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
    assert (
        _contains_all_lower(adaptive_clarification, "deep", "exploration")
        or _contains_all_lower(adaptive_clarification, "deep", "agent work")
        or _contains_all_lower(adaptive_clarification, "deep", "richer")
        or _contains_all_lower(adaptive_clarification, "deep", "slower")
        or _contains_all_lower(adaptive_clarification, "deep", "more thorough")
    )
    assert "fuller synthesis before each user checkpoint" not in adaptive_clarification.lower()
    assert "heavier rounds with fuller synthesis" not in adaptive_clarification.lower()

    assert _contains_any_lower(
        resolve_launch_preferences,
        "first-pass preferences",
        "launch preferences",
        "preferences",
        "lock now",
    )
    assert _contains_any_lower(
        resolve_launch_preferences,
        "stronger skepticism",
        "skepticism",
        "looser exploratory posture",
        "creativity",
        "specific number of perspectives",
        "number of participants",
        "worker count",
        "specialized roles",
        "specialization",
    )
    assert _contains_any_lower(
        config_surface,
        "keep preset, posture, worker count, and roster defaults backstage",
        "keep preset, posture, participant count, and stance defaults backstage",
        "keep preset, posture, participant count, and participant-mix defaults backstage",
        "keep participant defaults backstage",
        "keep the defaults backstage",
    )
    assert "temporary subgroup work should stay available" not in resolve_launch_preferences.lower()
    assert "specific next-round tasks" not in resolve_launch_preferences.lower()


def test_ideate_workflow_keeps_bounded_parent_owned_turns_agent_first_and_recap_on_demand() -> None:
    workflow = _read(IDEATE_WORKFLOW)
    round_loop = _step_body(workflow, "run_round_loop")
    task_objective = _tag_body(round_loop, "objective")
    task_contract = _tag_body(round_loop, "contract")

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
    assert _contains_any_lower(
        round_loop,
        "agent contributions are the primary visible unit",
        "surface the first-pass agent messages before any orchestrator recap",
    )
    assert _contains_in_order_lower(
        round_loop,
        "contributions may include grounded hypotheses, critiques, evidence checks, computational checks",
        "surface the first-pass agent messages first",
    )
    assert _contains_any_lower(
        round_loop,
        "each active agent contributes a short research-facing message in the first pass",
        "each active agent visibly contributes a short message",
    )
    assert _contains_any_lower(
        round_loop,
        "allow one bounded optional reaction layer",
        "optional reaction layer",
    )
    assert _contains_any_lower(
        round_loop,
        "structured research contributions",
        "`research_contributions`",
        "research contributions plus `gpd_return.status`",
        "typed research-contribution list",
    )
    assert _contains_any_lower(
        round_loop,
        "respond directly to prior agent output",
        "respond directly to earlier agent output",
        "prior agent output from the shared discussion",
        "`responds_to`",
    )
    assert _contains_any_lower(
        round_loop,
        "no automatic recap after a clean turn",
        "do not add an automatic recap after a clean turn",
        "clean turns do not require a visible recap",
        "clean turns should default to agent exchange plus a short natural handoff",
        "agent exchange plus a short natural handoff",
    )
    assert _contains_any_lower(
        round_loop,
        "visible synthesis only on explicit request",
        "visible synthesis only when the user asks",
        "visible synthesis only when needed for blocker routing",
        "visible synthesis only when needed for divergence routing",
        "visible synthesis only when needed to route a blocker or divergence",
    )
    assert _contains_any_lower(
        round_loop,
        "end the turn with a conversational handoff",
        "conversational handoff",
    )
    assert _contains_any_lower(
        task_objective,
        "contribute one bounded research contribution",
        "contribute one bounded research-turn contribution",
        "contribute one bounded research-session contribution",
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
        "participant in the discussion",
        "participant in the discussion, not a hidden lane feeding an orchestrator summary",
        "visible participant contributions",
        "short message that feels like a participant in the discussion",
    )
    assert _contains_any_lower(
        round_loop,
        "varying prompt-level posture, skepticism, creativity, and assignment instructions as needed",
        "posture, skepticism, creativity",
        "current configuration",
    )
    assert _contains_any_lower(
        task_contract,
        "typed `gpd_return` envelope",
        "route on typed `gpd_return.status`",
    )
    assert _contains_any_lower(
        task_contract,
        "structured research contributions",
        "`research_contributions`",
        "research contributions plus `gpd_return.status`",
    )
    assert _contains_any_lower(
        f"{task_objective}\n{task_contract}",
        "respond directly to prior agent output",
        "respond directly to earlier agent output",
        "prior agent output from the shared discussion",
        "`responds_to`",
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

    for legacy in ("shareable ideas", "shareable critiques"):
        assert legacy not in round_loop.lower()
        assert legacy not in task_contract.lower()


def test_ideate_workflow_keeps_checks_and_calculations_as_normal_visible_turn_work() -> None:
    workflow = _read(IDEATE_WORKFLOW)
    round_loop = _step_body(workflow, "run_round_loop")
    task_contract = _tag_body(round_loop, "contract")
    visible_turn_contract = f"{round_loop}\n{task_contract}"

    assert _contains_any_lower(
        round_loop,
        "evidence checks, computational checks",
        "evidence checks or literature comparison",
        "computational or analytic check",
    )
    assert _contains_any_lower(
        task_contract,
        "`evidence_check`",
        "`computational_check`",
        "evidence_check",
        "computational_check",
    )
    assert _contains_in_order_lower(
        visible_turn_contract,
        "evidence checks",
        "computational checks",
        "surface the first-pass agent messages first",
    )
    assert _contains_any_lower(
        round_loop,
        "if a claim is cheaply checkable, at least one lane should check it instead of only discussing it",
        "at least one lane should check it instead of only discussing it",
        "first-pass visible agent messages may be literature results, evidence checks, or calculation results",
        "each active agent should visibly contribute a short message",
    )


def test_ideate_workflow_contract_mirrors_worker_provenance_and_failure_rules_when_they_land() -> None:
    worker = _read(IDEATION_WORKER).lower()
    workflow = _read(IDEATE_WORKFLOW)
    round_loop = _step_body(workflow, "run_round_loop")
    task_contract = _tag_body(round_loop, "contract")
    workflow_contract = f"{round_loop}\n{task_contract}".lower()

    assert _contains_any_lower(
        workflow_contract,
        "`checkpoint`, `blocked`, or `failed` lane becomes a parent-owned ambiguity",
        "`gpd_return.status: checkpoint`",
        "do not wait in place",
    )

    phase7_provenance_groups = (
        ("sourced",),
        ("computed",),
        ("mixed",),
        ("source_refs", "source refs"),
        ("computation_note", "computation note"),
    )
    for group in phase7_provenance_groups:
        if any(option in worker for option in group):
            assert any(option in workflow_contract for option in group)

    phase7_failure_groups = (
        ("web search/fetch fails", "search/fetch fails", "web search fails"),
        ("paywalled",),
        ("garbled",),
        ("shell is unavailable", "shell unavailable"),
        ("binary", "interpreter", "library"),
        ("cannot be completed trustworthily", "cannot complete it trustworthily"),
        ("install packages", "install package"),
        ("helper files", "write helper files"),
    )
    for group in phase7_failure_groups:
        if any(option in worker for option in group):
            assert any(option in workflow_contract for option in group)

    if "never pretend a search/fetch/computation succeeded" in worker:
        assert _contains_any_lower(
            workflow_contract,
            "never pretend a search/fetch/computation succeeded",
            "never pretend a search, fetch, or computation succeeded",
        )


def test_ideate_turn_checkpoint_preserves_user_control_reaction_layer_and_fresh_continuations() -> None:
    workflow = _read(IDEATE_WORKFLOW)
    round_loop = _step_body(workflow, "run_round_loop")
    round_review_gate = _step_body(workflow, "round_review_gate")
    capabilities = _bullet_list_after_marker(
        round_review_gate, "capabilities available in natural language:"
    )
    handoff_examples = _bullet_list_after_marker(round_review_gate, "Prefer handoff language such as:")

    assert _contains_any_lower(
        round_review_gate,
        "after each conversational turn, keep the user handoff light and natural.",
        "agent messages should already be on screen",
        "raw turn details remain review-on-demand.",
        "raw worker detail remains available on demand.",
    )
    assert _contains_any_lower(
        round_review_gate,
        "do not present a rigid fixed menu by default",
        "makes these capabilities available in natural language",
    )
    assert any("continue" in item.lower() for item in capabilities)
    assert any("add" in item.lower() or "redirect" in item.lower() for item in capabilities)
    assert any(
        "adjust" in item.lower() or "tune" in item.lower()
        for item in capabilities
    )
    assert any("synthesis" in item.lower() or "recap" in item.lower() for item in capabilities)
    assert any("stop" in item.lower() or "pause" in item.lower() for item in capabilities)
    assert all("raw" not in item.lower() for item in capabilities)
    assert any("synthesis" in item.lower() or "recap" in item.lower() for item in handoff_examples)
    assert all("raw" not in item.lower() for item in handoff_examples)
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
        "ask for synthesis",
        "request synthesis",
        "show a brief synthesis",
        "return to the same conversational handoff",
    )
    assert _contains_any_lower(
        round_review_gate,
        "pause or stop cleanly without claiming durable persistence",
        "pause or stop cleanly",
    )
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


def test_ideate_round_review_surface_keeps_synthesis_on_demand_and_updates_success_criteria() -> None:
    workflow = _read(IDEATE_WORKFLOW)
    round_loop = _step_body(workflow, "run_round_loop")
    round_review_gate = _step_body(workflow, "round_review_gate")
    success_criteria = _tag_body(workflow, "success_criteria")

    assert _contains_any_lower(
        round_loop,
        "no automatic recap after a clean turn",
        "do not add an automatic recap after a clean turn",
        "clean turns do not require a visible recap",
        "clean turns should default to agent exchange plus a short natural handoff",
        "agent exchange plus a short natural handoff",
    )
    assert _contains_any_lower(
        round_review_gate,
        "agent messages should already be on screen",
        "ask for synthesis",
        "request synthesis",
        "raw turn details remain review-on-demand",
        "raw worker detail remains available on demand",
    )
    assert _contains_any_lower(
        round_loop,
        "visible synthesis only on explicit request",
        "visible synthesis only when the user asks",
        "visible synthesis only when needed for blocker routing",
        "visible synthesis only when needed for divergence routing",
    )
    assert _contains_any_lower(
        success_criteria,
        "a strong first message can reach the first bounded discussion turn with substantially less launch ceremony",
        "can reach the first bounded discussion turn with less launch ceremony",
    )
    assert _contains_any_lower(
        success_criteria,
        "visible synthesis happens on demand",
        "visible synthesis is on-demand or exception-driven",
        "no automatic recap after a clean turn",
        "clean turns should default to agent exchange plus a short natural handoff",
    )
    assert _contains_any_lower(
        success_criteria,
        "continue, add or redirect, adjust configuration, ask for synthesis, and pause-stop",
        "continue, add or redirect, adjust configuration, ask for synthesis, and stop",
        "continue, add or redirect, setup tuning, ask for synthesis, and stop",
        "ask for synthesis while raw details stay available on demand",
    )
    assert _contains_any_lower(
        success_criteria,
        "raw details remain available on demand",
        "raw review remains available on request",
        "raw worker detail stays request-only",
    )


def test_ideate_non_durable_contract_covers_rounds_focused_follow_up_and_closeout() -> None:
    workflow = _read(IDEATE_WORKFLOW)
    orient_and_parse = _step_body(workflow, "orient_and_parse")
    round_loop = _step_body(workflow, "run_round_loop")
    round_review_gate = _step_body(workflow, "round_review_gate")
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
        round_review_gate,
        "no files were created",
        "pause or stop cleanly without claiming durable persistence",
        "pause or stop cleanly",
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


def test_ideate_focused_follow_up_stays_parent_owned_fileless_and_summary_first() -> None:
    workflow = _read(IDEATE_WORKFLOW)
    round_review_gate = _step_body(workflow, "round_review_gate")
    focused_follow_up_note = _step_body(workflow, "focused_follow_up_note")
    success_criteria = _tag_body(workflow, "success_criteria")
    combined = f"{round_review_gate}\n{focused_follow_up_note}\n{success_criteria}"

    assert 'name="subgroup_micro_loop"' not in workflow
    assert "subgroup rounds" not in workflow.lower()
    assert "subgroup members" not in workflow.lower()
    assert "temporary subgroup batch" not in combined.lower()
    assert _contains_any_lower(
        combined,
        "focused follow-up",
        "focused fan-out",
        "targeted check",
        "narrower follow-up",
        "selective fan-out",
    )
    assert _contains_any_lower(
        combined,
        "user asks",
        "user-directed",
        "user-initiated",
        "when the user wants",
    )
    assert _contains_any_lower(
        combined,
        "fresh continuation",
        "parent handoff",
        "parent-owned",
        "do not resume",
    )
    assert _contains_any_lower(
        combined,
        "fileless",
        "no files were created",
        "in-memory",
        "non-durable",
    )
    assert _contains_any_lower(
        combined,
        "short reintegration note",
        "short summary",
        "summary-only",
        "fold the result back",
        "fold back",
    )
    assert not _contains_any_lower(
        combined,
        "subgroup recap",
        "breakout recap",
        "subgroup objective",
        "subgroup rounds completed",
    )


def test_ideate_closeout_keeps_a_clean_non_durable_optional_next_step_exit() -> None:
    workflow = _read(IDEATE_WORKFLOW)
    round_review_gate = _step_body(workflow, "round_review_gate")
    session_finish = _step_body(workflow, "session_finish")

    assert _contains_any_lower(
        session_finish,
        "if the user simply wants to stop, end cleanly",
        "end cleanly in a short conversational way",
        "short conversational stop",
        "stop cleanly",
        "end cleanly",
    )
    assert _contains_any_lower(
        session_finish,
        "offer a compact summary when it would help",
        "compact summary when it would help",
        "summary when it would help",
        "optional synthesis",
        "synthesis optional",
        "optional helpful summary",
        "when the user ends the session and wants one",
    )
    assert _contains_any_lower(
        session_finish,
        "next moves available rather than mandatory",
        "keep next moves available rather than mandatory",
        "ability to suggest next moves",
        "next-step suggestions available",
        "available rather than mandatory",
    )
    assert _contains_any_lower(
        session_finish,
        "non-gpd next step",
        "non-gpd next steps",
        "non-gpd next move",
        "non-gpd next moves",
        "ask for a non-gpd next step instead",
    )
    assert _contains_any_lower(
        session_finish,
        "gpd:suggest-next",
        "gpd:new-project",
        "gpd:research-phase",
        "gpd:help --all",
        "gpd:ideate [topic or question]",
    )

    for forbidden in (
        "Immediately after the summary, ask this exact short closing question:",
        "ask this exact short closing question",
        "End with:",
        "## > Next Up",
    ):
        assert forbidden not in session_finish

    assert _contains_any_lower(
        session_finish,
        "ask what the user wants to do next when that is useful",
        "do not pin every stop to one exact closing question",
        "remains available as a strong default",
    )

    assert _contains_any_lower(
        round_review_gate,
        "keep the user handoff light and natural",
        "conversational handoff",
        "if you want, i can keep pushing on this line",
    )

    assert _contains_any_lower(
        session_finish,
        "this v1 closeout is in-memory only.",
        "this projectless research-session closeout is in-memory only.",
        "do not add or imply durable ideation history",
        "non-durable boundary",
        "in-memory only",
    )
