"""Prompt assertions for agent taxonomy and execution routing."""

from __future__ import annotations

from pathlib import Path

from gpd import registry
from gpd.core.model_visible_text import (
    INTERNAL_AGENT_BOUNDARY_POINTER,
    READ_ONLY_INTERNAL_AGENT_BOUNDARY_POINTER,
)

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

    assert "Public production boundary: public writable production agent for bounded implementation work" in executor
    assert "Public production boundary: public writable production agent specialized for discrepancy investigation" in debugger
    assert "Public production boundary: public writable production agent for manuscript sections" in paper_writer
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
        expected = (
            READ_ONLY_INTERNAL_AGENT_BOUNDARY_POINTER
            if agent.artifact_write_authority == "read_only"
            else INTERNAL_AGENT_BOUNDARY_POINTER
        )
        assert content.count(expected) == 1, name
        assert f"surface: {agent.surface}" in agent.system_prompt, name


def test_source_agent_surface_boilerplate_does_not_conflict_with_frontmatter() -> None:
    for name in registry.list_agents():
        agent = registry.get_agent(name)
        content = _read_agent(name)
        assert "Agent surface:" not in content, name
        if agent.surface == "internal":
            assert "Public production boundary:" not in content, name
        if agent.surface == "public":
            assert INTERNAL_AGENT_BOUNDARY_POINTER not in content, name
            assert READ_ONLY_INTERNAL_AGENT_BOUNDARY_POINTER not in content, name


def test_consistency_checker_stays_one_shot_and_does_not_claim_resolution_work() -> None:
    source = _read_agent("gpd-consistency-checker")

    assert "This is a one-shot handoff: inspect once, write once, return once." in source
    assert "gpd_return.status: checkpoint" in source
    assert "status: completed | checkpoint | blocked | failed" in source
    assert INTERNAL_AGENT_BOUNDARY_POINTER in source
    assert "Do not claim ownership of code fixes, commits, convention-authoring, or pattern-library updates." in source
    assert "Create it from the template" not in source
    assert "gpd pattern add" not in source


def test_executor_checkpoint_frequency_guidance_is_consistent() -> None:
    source = _read_agent("gpd-executor")

    assert "**checkpoint:human-verify (90% of checkpoints)**" in source
    assert "**checkpoint:decision (9% of checkpoints)**" in source
    assert "**checkpoint:human-action (1% -- rare)**" in source
    assert "**checkpoint:decision (25%)**" not in source
    assert "**checkpoint:human-action (5%)**" not in source


def test_roadmapper_shallow_mode_keeps_contract_identity_visible() -> None:
    source = _read_agent("gpd-roadmapper")

    assert "shallow_mode=true" in source
    assert "objective IDs" in source
    assert "decisive contract items" in source
    assert "required anchors/baselines" in source
    assert "forbidden proxies" in source
    assert "Phase 1 only under `shallow_mode=true`" in source
    assert "Phase 2+ stubs defer detailed success criteria" in source
    assert "Phases 2+ may defer contract-coverage detail" not in source
    assert "only their one-line Goal and phase title" not in source


def test_planner_backtracks_guidance_is_capped_before_injection() -> None:
    source = _read_agent("gpd-planner")

    assert "awk -F'|'" in source
    assert 'row_stage != stage' in source
    assert "tail -n 10" in source
    assert "head -n 30" in source
    assert "do not inject the full file or an unfiltered tail" in source
    assert "for f in GPD/INSIGHTS.md GPD/ERROR-PATTERNS.md GPD/BACKTRACKS.md; do" not in source
    assert "tail -n 30 GPD/BACKTRACKS.md" not in source
