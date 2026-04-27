"""Seam assertions for the `literature-review` workflow vertical."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_DIR = REPO_ROOT / "src" / "gpd" / "commands"
WORKFLOWS_DIR = REPO_ROOT / "src" / "gpd" / "specs" / "workflows"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_literature_review_command_stays_thin_and_leaves_routing_to_the_workflow() -> None:
    command = _read(COMMANDS_DIR / "literature-review.md")

    assert "Follow the included literature-review workflow exactly." in command
    assert "The workflow owns staged loading, scope fixing, artifact gating, and citation verification." in command
    assert "explicit topic or research question" in command
    assert "under `GPD/literature/` rooted at the current workspace" in command
    assert "Standalone empty invocations should already have failed preflight." in command
    assert "gpd-literature-reviewer" not in command
    assert "gpd-bibliographer" not in command
    assert "gpd commit" not in command


def test_literature_review_workflow_requires_reviewer_and_bibliographer_spawn_contracts() -> None:
    workflow = _read(WORKFLOWS_DIR / "literature-review.md")

    assert 'subagent_type="gpd-literature-reviewer"' in workflow
    assert 'subagent_type="gpd-bibliographer"' in workflow
    assert workflow.count("<spawn_contract>") >= 2
    assert "shared_state_policy: return_only" in workflow
    assert "GPD/literature/{slug}-REVIEW.md" in workflow
    assert "GPD/literature/{slug}-CITATION-SOURCES.json" in workflow
    assert "GPD/literature/{slug}-CITATION-AUDIT.md" in workflow
    assert "gpd_return.files_written" in workflow
    assert "fresh continuation handoff" in workflow
    assert "checkpoint_response" in workflow
    assert "Do not trust the runtime handoff status by itself." in workflow
    assert "Keep all durable review artifacts rooted under `GPD/literature/` in the current workspace." in workflow
    assert "If `topic` is empty, do not invent or auto-derive it from project state" in workflow
    assert "The review topic must already be explicit or newly clarified" in workflow
    assert "Proceed without citation audit." not in workflow


def test_literature_review_workflow_removes_legacy_commit_ownership_and_keeps_completion_fail_closed() -> None:
    workflow = _read(WORKFLOWS_DIR / "literature-review.md")

    assert "gpd commit" not in workflow
    assert "Return to orchestrator through the typed child-return contract." in workflow
    assert "Route on `gpd_return.status` and the artifact gate" in workflow
    assert "If the review is incomplete or blocked, use `gpd_return.status: blocked` or `failed`" in workflow
    assert "spawn a fresh continuation run after the response" in workflow
