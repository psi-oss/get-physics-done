"""Assertions for agent commit-ownership policy."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from gpd import registry
from gpd.core.model_visible_text import AGENT_FRONTMATTER_AUTHORITY_POINTER

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO_ROOT / "src/gpd/agents"
INFRA_PATH = REPO_ROOT / "src/gpd/specs/references/orchestration/agent-infrastructure.md"

DIRECT_AGENTS = {"gpd-debugger", "gpd-executor", "gpd-planner"}


@pytest.fixture(autouse=True)
def _clean_registry_cache():
    registry.invalidate_cache()
    yield
    registry.invalidate_cache()


def test_every_agent_frontmatter_declares_commit_authority() -> None:
    pattern = re.compile(r"^commit_authority:\s*(direct|orchestrator)\s*$", re.MULTILINE)

    for path in sorted(AGENTS_DIR.glob("*.md")):
        content = path.read_text(encoding="utf-8")
        assert pattern.search(content), path.name


def test_registry_exposes_exact_direct_commit_allowlist() -> None:
    direct = {name for name in registry.list_agents() if registry.get_agent(name).commit_authority == "direct"}

    assert direct == DIRECT_AGENTS


def test_registry_agent_commit_authority_values_are_valid() -> None:
    valid = {"direct", "orchestrator"}

    for name in registry.list_agents():
        assert registry.get_agent(name).commit_authority in valid


def test_agent_infrastructure_commit_policy_uses_frontmatter_inventory_instead_of_manual_matrix() -> None:
    infra = INFRA_PATH.read_text(encoding="utf-8")

    assert "named allowlist" in infra
    assert "Direct-commit allowlist:" not in infra
    assert "validated by the registry; do not duplicate a hand-maintained matrix" in infra
    assert "Canonical ownership matrix:" not in infra
    assert not re.search(r"^\| (gpd-[a-z-]+) \| `(?:direct|orchestrator)` \|", infra, re.MULTILINE)


def test_agent_prompts_use_generated_agent_requirements_as_single_authority_surface() -> None:
    for name in registry.list_agents():
        agent = registry.get_agent(name)
        path = Path(agent.path)
        content = path.read_text(encoding="utf-8")

        assert AGENT_FRONTMATTER_AUTHORITY_POINTER not in content, path.name
        assert agent.system_prompt.startswith("## Agent Requirements\n"), path.name
        assert agent.system_prompt.count("## Agent Requirements") == 1, path.name
        assert f"commit_authority: {agent.commit_authority}" in agent.system_prompt, path.name
        assert f"surface: {agent.surface}" in agent.system_prompt, path.name
        assert f"artifact_write_authority: {agent.artifact_write_authority}" in agent.system_prompt, path.name
        assert f"shared_state_authority: {agent.shared_state_authority}" in agent.system_prompt, path.name
        assert not re.search(r"^Commit authority:", content, re.MULTILINE), path.name


def test_agents_do_not_duplicate_stale_commit_ownership_blocks() -> None:
    for path in sorted(AGENTS_DIR.glob("*.md")):
        content = path.read_text(encoding="utf-8")

        assert "## Agent Commit Ownership" not in content, path.name
        assert "Which agents commit their own work vs. return `files_written`" not in content, path.name
        assert "Do NOT use raw `git commit` when `gpd commit` applies." not in content, path.name
        assert "Do NOT run `gpd commit`, `git commit`, or stage files." not in content, path.name
