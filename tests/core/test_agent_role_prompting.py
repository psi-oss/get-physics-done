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


def _research_discussant_names() -> list[str]:
    names: list[str] = []
    for name in registry.list_agents():
        agent = registry.get_agent(name)
        if agent.surface != "internal":
            continue

        content = _read_agent(name)
        lowered = content.lower()
        if "discussant" in lowered and "research" in lowered:
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


def test_research_discussants_preserve_one_shot_checkpoint_and_fileless_contract() -> None:
    names = _research_discussant_names()
    assert names, "expected at least one research discussant-style prompt"

    saw_discussant_framing = False
    for name in names:
        content = _read_agent(name)
        lowered = content.lower()

        _assert_not_default_worker(content)
        _assert_mentions_handoff(content, "gpd-executor")
        assert "one-shot" in lowered, name
        assert "checkpoint" in lowered, name

        saw_discussant_framing = True
        _assert_contains_any(
            lowered,
            "fileless",
            "do not write files",
            "no files are written",
            "return no files",
            "no artifact is written",
            "without writing files",
            "files_written: []",
        )
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
        _assert_has_return_field(content, "lane_id")
        _assert_has_return_field(content, "lane_role")
        _assert_has_return_field(content, "stance")
        _assert_has_return_field(content, "research_contributions")
        _assert_has_return_field(content, "assignment_status")

    assert saw_discussant_framing, "expected research discussant framing in at least one prompt"


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
