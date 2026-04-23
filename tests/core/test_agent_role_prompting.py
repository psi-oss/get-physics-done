"""Prompt assertions for agent taxonomy and execution routing."""

from __future__ import annotations

from pathlib import Path

from gpd import registry

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO_ROOT / "src" / "gpd" / "agents"


def _read_agent(name: str) -> str:
    return (AGENTS_DIR / f"{name}.md").read_text(encoding="utf-8")


def test_executor_prompt_describes_default_writable_scoped_task_role() -> None:
    executor = _read_agent("gpd-executor")

    assert "default writable implementation agent" in executor
    assert "Scoped-task mode" in executor
    assert "the prompt itself is the execution contract" in executor
    assert "route it to gpd-paper-writer" in executor
    assert "route it to gpd-notation-coordinator" in executor


def test_planner_debugger_and_explainer_route_work_to_specialized_agents() -> None:
    planner = _read_agent("gpd-planner")
    debugger = _read_agent("gpd-debugger")
    explainer = _read_agent("gpd-explainer")

    assert "go to `gpd-executor`" in planner
    assert "goes to `gpd-paper-writer`" in planner
    assert "goes to `gpd-notation-coordinator`" in planner

    assert "hand it to `gpd-executor`" in debugger
    assert "hand it to `gpd-paper-writer`" in debugger
    assert "hand it to `gpd-notation-coordinator`" in debugger

    assert "not the default writable implementation agent" in explainer
    assert "route that work to `gpd-executor`" in explainer
    assert "route it to `gpd-paper-writer`" in explainer
    assert "route it to `gpd-notation-coordinator`" in explainer


def test_public_worker_prompts_identify_writable_production_surface() -> None:
    executor = _read_agent("gpd-executor")
    debugger = _read_agent("gpd-debugger")
    paper_writer = _read_agent("gpd-paper-writer")

    assert "Agent surface: public writable production agent." in executor
    assert "Agent surface: public writable production agent specialized for discrepancy investigation" in debugger
    assert "Agent surface: public writable production agent for manuscript sections" in paper_writer
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
        assert "Do not act as the default writable implementation agent" in content, name


def test_source_agent_surface_boilerplate_does_not_conflict_with_frontmatter() -> None:
    for name in registry.list_agents():
        agent = registry.get_agent(name)
        content = _read_agent(name)
        if agent.surface == "internal":
            assert "Agent surface: public writable production agent" not in content, name
        if agent.surface == "public":
            assert "Agent surface: internal specialist subagent." not in content, name


def test_consistency_checker_stays_one_shot_and_does_not_claim_resolution_work() -> None:
    source = _read_agent("gpd-consistency-checker")

    assert "This is a one-shot handoff: inspect once, write once, return once." in source
    assert "gpd_return.status: checkpoint" in source
    assert "status: completed | checkpoint | blocked | failed" in source
    assert "Do not act as the default writable implementation agent." in source
    assert "Do not claim ownership of code fixes, commits, convention-authoring, or pattern-library updates." in source
    assert "Create it from the template" not in source
    assert "gpd pattern add" not in source
