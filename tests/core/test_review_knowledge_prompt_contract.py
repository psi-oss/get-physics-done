"""Prompt-contract guardrails for the knowledge review/promotion workflow."""

from __future__ import annotations

from pathlib import Path

from gpd import registry

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
    parsed = registry.get_command("review-knowledge")
    review_contract = parsed.review_contract

    assert "name: gpd:review-knowledge" in command
    assert "context_mode: project-aware" in command
    assert "command-policy:" in command
    assert "@{GPD_INSTALL_DIR}/workflows/review-knowledge.md" in command
    assert "current workspace" in command
    assert parsed.command_policy == registry.CommandPolicy(
        schema_version=1,
        subject_policy=registry.CommandSubjectPolicy(
            subject_kind="knowledge_document",
            resolution_mode="explicit_current_workspace_canonical_target",
            explicit_input_kinds=["knowledge_document_path", "knowledge_id"],
            allow_external_subjects=False,
            supported_roots=["GPD/knowledge"],
            allowed_suffixes=[".md"],
        ),
        supporting_context_policy=registry.CommandSupportingContextPolicy(
            project_context_mode="project-aware",
            project_reentry_mode="disallowed",
            optional_file_patterns=[
                "GPD/knowledge/*.md",
                "GPD/knowledge/reviews/*.md",
                "GPD/STATE.md",
            ],
        ),
        output_policy=registry.CommandOutputPolicy(
            output_mode="managed",
            managed_root_kind="gpd_managed_durable",
            default_output_subtree="GPD/knowledge",
            stage_artifact_policy="gpd_owned_outputs_only",
        ),
    )
    assert review_contract is not None
    assert review_contract.required_evidence[0] == "current-workspace canonical knowledge document"
    assert "missing project state" not in review_contract.blocking_conditions
    assert review_contract.preflight_checks == [
        "command_context",
        "knowledge_target",
        "knowledge_document",
        "knowledge_review_freshness",
    ]

    command_index = _section(help_workflow, "## Command Index", "## Detailed Command Reference")
    detailed_reference = _section(help_workflow, "## Detailed Command Reference", "### Optional Local CLI Add-Ons")

    assert "gpd:review-knowledge" in command_index
    assert "gpd:review-knowledge" in detailed_reference


def test_review_knowledge_workflow_documents_exact_target_resolution_and_review_promotion_contract() -> None:
    command = _read(REVIEW_COMMAND_PATH)
    workflow = _read(REVIEW_WORKFLOW_PATH)

    assert "non-canonical knowledge target" in command
    assert "Strict knowledge review preflight is anchored to the explicit current-workspace knowledge target" in command
    assert "Missing `STATE.md` alone is advisory background context, not a standalone blocker." in workflow
    assert "Reject lookalikes such as `notes/K-foo.md`" in workflow
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
