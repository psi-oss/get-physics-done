"""Prompt regressions for agent taxonomy and execution routing."""

from __future__ import annotations

import re
from pathlib import Path

from gpd import registry

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO_ROOT / "src" / "gpd" / "agents"


def _read_agent(name: str) -> str:
    return (AGENTS_DIR / f"{name}.md").read_text(encoding="utf-8")


def _assert_contains_any(content: str, *needles: str) -> None:
    assert any(needle in content for needle in needles), needles


def _assert_contains_any_lower(content: str, *needles: str) -> None:
    lowered = content.lower()
    assert any(needle.lower() in lowered for needle in needles), needles


def _agent_body(content: str) -> str:
    if not content.startswith("---"):
        return content

    parts = content.split("---", 2)
    if len(parts) != 3:
        return content
    return parts[2]


def _assert_mentions_handoff(content: str, target: str) -> None:
    assert target in content
    pattern = re.compile(
        rf"(route|hand|go(?:es)? to|should go to|delegate|send)[\s\S]{{0,160}}?`?{re.escape(target)}`?",
        re.IGNORECASE,
    )
    assert pattern.search(content), target


def _assert_has_return_field(content: str, *field_names: str) -> None:
    for field_name in field_names:
        if re.search(
            rf"(^|[\r\n])\s*{re.escape(field_name)}\s*:",
            content,
            re.MULTILINE,
        ):
            return
    raise AssertionError(f"missing return field from {field_names!r}")


def _assert_not_default_worker(content: str) -> None:
    _assert_contains_any(
        content,
        "Do not act as the default writable implementation agent",
        "not the default writable implementation agent",
        "Do not act as the default writable production agent",
    )


def _ideation_research_turn_names() -> list[str]:
    names: list[str] = []
    for name in registry.list_agents():
        agent = registry.get_agent(name)
        if agent.surface != "internal":
            continue

        content = _read_agent(name)
        lowered = content.lower()
        if (
            "gpd:ideate" in lowered
            and "research" in lowered
            and (
                any(
                    needle in lowered
                    for needle in (
                        "discussant",
                        "participant",
                        "discussion turn",
                        "participant group",
                    )
                )
                or re.search(
                    r"\b(literature-aware skeptic|technical calculator|skeptic|calculator)\b",
                    lowered,
                )
            )
        ):
            names.append(name)
    return sorted(set(names))


def test_executor_prompt_describes_default_writable_scoped_task_role() -> None:
    executor = _read_agent("gpd-executor")

    assert "default writable implementation agent" in executor
    assert "Scoped-task mode" in executor
    _assert_contains_any(
        executor,
        "the prompt itself is the execution contract",
        "the prompt's objective, constraints, expected artifacts",
    )
    _assert_mentions_handoff(executor, "gpd-paper-writer")
    _assert_mentions_handoff(executor, "gpd-notation-coordinator")


def test_planner_debugger_and_explainer_route_work_to_specialized_agents() -> None:
    for name in ("gpd-planner", "gpd-debugger", "gpd-explainer"):
        content = _read_agent(name)
        _assert_mentions_handoff(content, "gpd-executor")
        _assert_mentions_handoff(content, "gpd-paper-writer")
        _assert_mentions_handoff(content, "gpd-notation-coordinator")

    _assert_not_default_worker(_read_agent("gpd-explainer"))


def test_public_worker_prompts_identify_writable_production_surface() -> None:
    executor = _read_agent("gpd-executor")
    debugger = _read_agent("gpd-debugger")
    paper_writer = _read_agent("gpd-paper-writer")

    assert "Agent surface: public writable production agent." in executor
    assert "Agent surface: public writable production agent" in debugger
    assert "discrepancy investigation" in debugger
    assert "Agent surface: public writable production agent" in paper_writer
    assert "manuscript" in paper_writer
    assert (
        "On demand only: shared protocols, verification core, physics subfields, agent infrastructure, and cross-project patterns."
        in debugger
    )
    assert "@{GPD_INSTALL_DIR}/references/shared/shared-protocols.md" not in debugger
    assert "@{GPD_INSTALL_DIR}/references/orchestration/agent-infrastructure.md" not in debugger


def test_internal_agents_explicitly_identify_internal_specialist_surface() -> None:
    for name in registry.list_agents():
        agent = registry.get_agent(name)
        if agent.surface != "internal":
            continue

        content = _read_agent(name)
        assert content.count("Agent surface: internal specialist subagent.") == 1, name
        _assert_not_default_worker(content)


def test_source_agent_surface_boilerplate_does_not_conflict_with_frontmatter() -> None:
    for name in registry.list_agents():
        agent = registry.get_agent(name)
        content = _read_agent(name)
        if agent.surface == "internal":
            assert "Agent surface: public writable production agent" not in content, name
        if agent.surface == "public":
            assert "Agent surface: internal specialist subagent." not in content, name


def test_ideation_research_participants_preserve_one_shot_checkpoint_and_fileless_contract() -> None:
    names = _ideation_research_turn_names()
    assert names, "expected at least one ideation research turn prompt"

    saw_turn_framing = False
    for name in names:
        content = _read_agent(name)
        lowered = content.lower()

        _assert_not_default_worker(content)
        _assert_mentions_handoff(content, "gpd-executor")
        assert "one-shot" in lowered, name
        assert "checkpoint" in lowered, name
        assert re.search(
            r"(participant|discussant|discussion turn|participant group|literature-aware skeptic|technical calculator|\bskeptic\b|\bcalculator\b)",
            lowered,
        ), name
        assert (
            "Treat those as temporary prompt-level stance instructions for the current turn, not as a permanent persona or cast slot."
            in content
        ), name
        assert (
            "Do not invent a separate persona taxonomy, stable panel role, or durable lane identity."
            in content
        ), name
        assert (
            "Treat `lane_id` and `lane_role` as orchestrator bookkeeping fields when provided, not as evidence of a permanent persona."
            in content
        ), name

        saw_turn_framing = True
        assert (
            "This is a one-shot handoff. If user input is needed, return `gpd_return.status: checkpoint` and stop. Do not wait inside the same run."
            in content
        ), name
        assert (
            "For this fileless research turn, keep `files_written: []`"
            in content
        ), name
        assert (
            "Do not write files in this phase. Do not claim ownership of continuation, synthesis, or future rounds."
            in content
        ), name
        assert (
            "The orchestrator owns any deeper-check detour routing. Do not invent detour state or wait in place."
            in content
        ), name
        if "files_written:" in content:
            assert re.search(
                r"(^|[\r\n])\s*files_written:\s*\[\s*\]",
                content,
                re.MULTILINE,
            ), name

        _assert_has_return_field(content, "status")
        _assert_has_return_field(content, "issues")
        _assert_has_return_field(content, "next_actions")
        _assert_has_return_field(content, "round")
        _assert_has_return_field(content, "lane_id", "participant_id")
        _assert_has_return_field(content, "lane_role", "participant_role")
        _assert_has_return_field(content, "stance")
        _assert_has_return_field(content, "research_contributions")
        _assert_has_return_field(content, "assignment_status")

    assert saw_turn_framing, "expected research turn framing in at least one prompt"


def test_ideation_worker_makes_web_and_shell_checks_first_class_turn_operations() -> None:
    source = _read_agent("gpd-ideation-worker")
    body = _agent_body(source)

    assert "web_search" in body
    assert "web_fetch" in body
    assert "shell" in body
    assert re.search(
        r"(materially improve|materially advance|cheaply resolve|cheaply settle|prefer the lightest tool)",
        body,
        re.IGNORECASE,
    )
    assert re.search(
        r"`?web_search`?[\s\S]{0,220}?(recent|unstable|paper|benchmark|evidence|check)",
        body,
        re.IGNORECASE,
    )
    assert re.search(
        r"`?web_fetch`?[\s\S]{0,220}?(source-specific|citation|claim|source|fetch)",
        body,
        re.IGNORECASE,
    )
    assert re.search(
        r"`?shell`?[\s\S]{0,220}?(calculation|analytic|estimate|unit conversion|inline script|compute)",
        body,
        re.IGNORECASE,
    )
    assert re.search(
        r"cheap[\s\S]{0,120}?inline",
        body,
        re.IGNORECASE,
    )
    assert re.search(
        r"meaningfully longer pass[\s\S]{0,180}?checkpoint[\s\S]{0,160}?deeper check",
        body,
        re.IGNORECASE,
    )


def test_ideation_worker_requires_provenance_and_honest_tool_failure_reporting() -> None:
    source = _read_agent("gpd-ideation-worker")
    body = _agent_body(source)

    assert re.search(
        r"provenance[\s\S]{0,220}?(sourced|computed|speculative|mixed)",
        body,
        re.IGNORECASE,
    )
    _assert_contains_any(body, "`source_refs`", "source_refs")
    _assert_contains_any(body, "`computation_note`", "computation_note")
    _assert_contains_any(body, "`assumptions`", "assumptions")

    assert re.search(
        r"(web_search|web_fetch)[\s\S]{0,260}?(fail|fails|failed|paywall|garbled|unavailable)",
        body,
        re.IGNORECASE,
    )
    assert re.search(
        r"`?shell`?[\s\S]{0,260}?(unavailable|missing|binary|interpreter|library|cannot be completed)",
        body,
        re.IGNORECASE,
    )
    assert re.search(
        r"(fail|fails|failed|paywall|garbled|unavailable|missing|cannot be completed)[\s\S]{0,220}?(confidence|partial|blocked|checkpoint|explicit)",
        body,
        re.IGNORECASE,
    )
    assert re.search(
        r"(never|do not)[\s\S]{0,120}?(pretend|bluff)[\s\S]{0,160}?(search|fetch|computation|calculation)",
        body,
        re.IGNORECASE,
    )
    assert re.search(
        r"(never|do not)[\s\S]{0,140}?(install packages|install libraries|write helper files|write files to rescue)",
        body,
        re.IGNORECASE,
    )
    _assert_contains_any_lower(
        body,
        "one-shot",
        "fileless",
        "do not write files",
        "without writing files",
    )
    _assert_contains_any_lower(
        body,
        "follow-on deeper check",
        "stand-alone report-back",
        "report-back turn",
    )


def test_consistency_checker_stays_one_shot_and_does_not_claim_resolution_work() -> None:
    source = _read_agent("gpd-consistency-checker")

    assert "one-shot" in source.lower()
    _assert_contains_any(
        source,
        "gpd_return.status: checkpoint",
        "status: completed | checkpoint | blocked | failed",
    )
    _assert_not_default_worker(source)
    assert "Do not claim ownership of code fixes, commits, convention-authoring, or pattern-library updates." in source
    assert "Create it from the template" not in source
    assert "gpd pattern add" not in source

    _assert_has_return_field(source, "status")
    _assert_has_return_field(source, "files_written")
    _assert_has_return_field(source, "issues")
    _assert_has_return_field(source, "next_actions")
    _assert_has_return_field(source, "phase_checked", "scope_checked", "milestone_checked")
    _assert_has_return_field(source, "checks_performed", "check_count")
    _assert_has_return_field(source, "issues_found", "issue_count")
