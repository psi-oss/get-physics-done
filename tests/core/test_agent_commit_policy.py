"""Regression tests for agent commit-ownership policy."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from gpd import registry

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO_ROOT / "src/gpd/agents"
INFRA_PATH = REPO_ROOT / "src/gpd/specs/references/orchestration/agent-infrastructure.md"

DIRECT_AGENTS = {"gpd-debugger", "gpd-executor", "gpd-planner"}
DIRECT_SENTENCE = (
    "Commit authority: direct. You may use `gpd commit` for your own scoped artifacts only. "
    "Do NOT use raw `git commit` when `gpd commit` applies."
)
ORCHESTRATOR_SENTENCE = (
    "Commit authority: orchestrator-only. Do NOT run `gpd commit`, `git commit`, or stage files. "
    "Return changed paths in `gpd_return.files_written`."
)


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
    direct = {
        name
        for name in registry.list_agents()
        if registry.get_agent(name).commit_authority == "direct"
    }

    assert direct == DIRECT_AGENTS


def test_registry_agent_commit_authority_values_are_valid() -> None:
    valid = {"direct", "orchestrator"}

    for name in registry.list_agents():
        assert registry.get_agent(name).commit_authority in valid


def test_agent_infrastructure_commit_matrix_covers_full_agent_inventory() -> None:
    infra = INFRA_PATH.read_text(encoding="utf-8")
    matrix_agents = set(re.findall(r"^\| (gpd-[a-z-]+) \| `(?:direct|orchestrator)` \|", infra, re.MULTILINE))

    assert matrix_agents == set(registry.list_agents())


def test_agent_prompts_include_exact_commit_authority_sentence() -> None:
    for name in registry.list_agents():
        path = Path(registry.get_agent(name).path)
        content = path.read_text(encoding="utf-8")
        expected = DIRECT_SENTENCE if name in DIRECT_AGENTS else ORCHESTRATOR_SENTENCE
        assert expected in content, path.name


def test_verifier_does_not_duplicate_stale_commit_ownership_block() -> None:
    verifier = (AGENTS_DIR / "gpd-verifier.md").read_text(encoding="utf-8")

    assert "## Agent Commit Ownership" not in verifier
    assert "Which agents commit their own work vs. return `files_written`" not in verifier
