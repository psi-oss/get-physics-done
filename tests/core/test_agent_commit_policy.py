"""Assertions for agent commit-ownership policy."""

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
SCOPED_DIRECT_SENTENCES = {
    "gpd-executor": (
        "Commit authority: direct for scoped execution artifacts only. In default spawned mode, do not write or "
        "commit `GPD/STATE.md`; return shared-state updates to the orchestrator. Do NOT use raw `git commit` "
        "when `gpd commit` applies."
    ),
    "gpd-planner": (
        "Commit authority: direct for scoped plan artifacts only. In default spawned mode, do not write or commit "
        "`GPD/STATE.md` or `GPD/ROADMAP.md`; return shared-state and roadmap updates to the orchestrator. "
        "Do NOT use raw `git commit` when `gpd commit` applies."
    ),
}
ORCHESTRATOR_SENTENCE = (
    "Commit authority: orchestrator-only. Do NOT run `gpd commit`, `git commit`, or stage files. "
    "Return changed paths in `gpd_return.files_written`."
)
READ_ONLY_ORCHESTRATOR_SENTENCE = (
    "Commit authority: orchestrator-only. Do NOT run `gpd commit`, `git commit`, or stage files. "
    "This is a read-only agent; return `gpd_return.files_written: []`."
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


def test_agent_infrastructure_commit_policy_uses_frontmatter_inventory_instead_of_manual_matrix() -> None:
    infra = INFRA_PATH.read_text(encoding="utf-8")

    assert "Direct-commit allowlist: `gpd-debugger`, `gpd-executor`, `gpd-planner`." in infra
    assert "validated by the registry; do not duplicate a hand-maintained matrix" in infra
    assert "Canonical ownership matrix:" not in infra
    assert not re.search(r"^\| (gpd-[a-z-]+) \| `(?:direct|orchestrator)` \|", infra, re.MULTILINE)


def test_agent_prompts_include_exact_commit_authority_sentence() -> None:
    for name in registry.list_agents():
        path = Path(registry.get_agent(name).path)
        content = path.read_text(encoding="utf-8")
        if name in DIRECT_AGENTS:
            expected = SCOPED_DIRECT_SENTENCES.get(name, DIRECT_SENTENCE)
            unexpected = ORCHESTRATOR_SENTENCE
        else:
            expected = READ_ONLY_ORCHESTRATOR_SENTENCE if name == "gpd-plan-checker" else ORCHESTRATOR_SENTENCE
            unexpected = DIRECT_SENTENCE
        assert content.count(expected) == 1, path.name
        assert unexpected not in content, path.name


def test_agents_do_not_duplicate_stale_commit_ownership_blocks() -> None:
    for path in sorted(AGENTS_DIR.glob("*.md")):
        content = path.read_text(encoding="utf-8")

        assert "## Agent Commit Ownership" not in content, path.name
        assert "Which agents commit their own work vs. return `files_written`" not in content, path.name
