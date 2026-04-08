"""Prompt-contract guardrails for the knowledge review/promotion workflow."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_DIR = REPO_ROOT / "src/gpd/commands"
WORKFLOWS_DIR = REPO_ROOT / "src/gpd/specs/workflows"
HELP_WORKFLOW_PATH = WORKFLOWS_DIR / "help.md"
REVIEW_COMMAND_PATH = COMMANDS_DIR / "review-knowledge.md"
REVIEW_WORKFLOW_PATH = WORKFLOWS_DIR / "review-knowledge.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _section(content: str, start_marker: str, end_marker: str) -> str:
    start = content.index(start_marker) + len(start_marker)
    end = content.index(end_marker, start)
    return content[start:end]


def _contains_any(content: str, *phrases: str) -> bool:
    lowered = content.lower()
    return any(phrase.lower() in lowered for phrase in phrases)


def test_review_knowledge_is_same_stem_wired_and_help_indexed() -> None:
    command = _read(REVIEW_COMMAND_PATH)
    help_workflow = _read(HELP_WORKFLOW_PATH)

    assert "name: gpd:review-knowledge" in command
    assert "context_mode: project-aware" in command
    assert "@{GPD_INSTALL_DIR}/workflows/review-knowledge.md" in command

    command_index = _section(help_workflow, "## Command Index", "## Detailed Command Reference")
    detailed_reference = _section(help_workflow, "## Detailed Command Reference", "### Optional Local CLI Add-Ons")

    assert "gpd:review-knowledge" in command_index
    assert "gpd:review-knowledge" in detailed_reference


def test_review_knowledge_workflow_documents_exact_target_resolution_and_review_promotion_contract() -> None:
    workflow = _read(REVIEW_WORKFLOW_PATH)

    assert _contains_any(workflow, "exact existing knowledge doc", "exact target", "canonical target", "knowledge_id")
    assert _contains_any(workflow, "GPD/knowledge/reviews/", "deterministic review artifact", "review artifact")
    assert _contains_any(
        workflow,
        "review_round",
        "reviewer_kind",
        "reviewer_id",
        "approval_artifact_path",
        "approval_artifact_sha256",
        "reviewed_content_sha256",
        "stale",
    )
    assert _contains_any(workflow, "approved", "needs_changes", "rejected")
    assert _contains_any(workflow, "stable", "in_review")
    assert _contains_any(workflow, "does not claim runtime ingestion", "planner/verifier trust propagation")
