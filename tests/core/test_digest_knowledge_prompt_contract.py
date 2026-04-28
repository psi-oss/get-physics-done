"""Prompt-contract guardrails for the knowledge-digest authoring/update MVP."""

from __future__ import annotations

from pathlib import Path

from gpd import registry

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_DIR = REPO_ROOT / "src/gpd/commands"
WORKFLOWS_DIR = REPO_ROOT / "src/gpd/specs/workflows"
TEMPLATES_DIR = REPO_ROOT / "src/gpd/specs/templates"
HELP_COMMAND_PATH = COMMANDS_DIR / "help.md"
HELP_WORKFLOW_PATH = WORKFLOWS_DIR / "help.md"
DIGEST_COMMAND_PATH = COMMANDS_DIR / "digest-knowledge.md"
DIGEST_WORKFLOW_PATH = WORKFLOWS_DIR / "digest-knowledge.md"
KNOWLEDGE_TEMPLATE_PATH = TEMPLATES_DIR / "knowledge.md"
KNOWLEDGE_SCHEMA_PATH = TEMPLATES_DIR / "knowledge-schema.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _section(content: str, start_marker: str, end_marker: str) -> str:
    start = content.index(start_marker) + len(start_marker)
    end = content.index(end_marker, start)
    return content[start:end]


def _contains_any(content: str, *phrases: str) -> bool:
    lowered = content.lower()
    return any(phrase.lower() in lowered for phrase in phrases)


def test_digest_knowledge_is_same_stem_wired_and_help_indexed() -> None:
    command = _read(DIGEST_COMMAND_PATH)
    help_workflow = _read(HELP_WORKFLOW_PATH)
    parsed = registry.get_command("digest-knowledge")

    assert "name: gpd:digest-knowledge" in command
    assert "context_mode: project-aware" in command
    assert "command-policy:" in command
    assert "@{GPD_INSTALL_DIR}/workflows/digest-knowledge.md" in command
    assert "current workspace" in command
    assert parsed.command_policy == registry.CommandPolicy(
        schema_version=1,
        subject_policy=registry.CommandSubjectPolicy(
            subject_kind="knowledge_document",
            resolution_mode="explicit_input_to_canonical_current_workspace_target",
            explicit_input_kinds=["knowledge_document_path", "source_path", "arxiv_id", "topic"],
            allow_external_subjects=True,
        ),
        supporting_context_policy=registry.CommandSupportingContextPolicy(
            project_context_mode="project-aware",
            project_reentry_mode="disallowed",
            optional_file_patterns=[
                "GPD/knowledge/*.md",
                "GPD/literature/*.md",
                "GPD/research-map/*.md",
            ],
        ),
        output_policy=registry.CommandOutputPolicy(
            output_mode="managed",
            managed_root_kind="gpd_managed_durable",
            default_output_subtree="GPD/knowledge",
            stage_artifact_policy="gpd_owned_outputs_only",
        ),
    )

    command_index = _section(help_workflow, "## Command Index", "## Detailed Command Reference")
    detailed_reference = _section(help_workflow, "## Detailed Command Reference", "### Optional Local CLI Add-Ons")

    assert "gpd:digest-knowledge" in command_index
    assert "gpd:digest-knowledge" in detailed_reference
    assert "gpd:review-knowledge" in command_index
    assert "gpd:review-knowledge" in detailed_reference


def test_digest_knowledge_workflow_remains_draft_only_and_routes_review_requests() -> None:
    workflow = _read(DIGEST_WORKFLOW_PATH)

    assert _contains_any(workflow, "draft-authoring half", "draft-only", "draft authoring")
    assert _contains_any(workflow, "create a new draft", "update an existing draft", "update existing draft")
    assert _contains_any(workflow, "route approval", "route the user to `gpd:review-knowledge`", "review-knowledge")
    assert _contains_any(workflow, "stable or superseded", "stable target", "superseded target")
    assert _contains_any(workflow, "does not claim downstream runtime ingestion", "planner/verifier trust propagation")


def test_digest_knowledge_workflow_documents_deterministic_target_resolution_and_input_validation() -> None:
    command = _read(DIGEST_COMMAND_PATH)
    workflow = _read(DIGEST_WORKFLOW_PATH)

    assert "External source material may live anywhere." in command
    assert "current workspace `GPD/knowledge/`" in workflow
    assert "The canonical standalone/current-workspace durable target always lives under `./GPD/knowledge/`" in workflow
    assert "Reject lookalike `K-*.md` paths outside `GPD/knowledge/` as canonical targets." in workflow
    assert "GPD/knowledge/{knowledge_id}.md" in workflow
    assert _contains_any(workflow, "explicit file path", "existing file path", "file path must exist", "must exist before")
    assert "accepted prefixes handled by the shared arXiv normalizer" in workflow
    assert "2401.12345" in workflow
    assert "2401.12345v2" in workflow
    assert "hep-th/9901001" in workflow
    assert "legacy arxiv" not in workflow.lower()


def test_digest_knowledge_templates_keep_non_runtime_deferrals_explicit() -> None:
    knowledge_template = _read(KNOWLEDGE_TEMPLATE_PATH)
    knowledge_schema = _read(KNOWLEDGE_SCHEMA_PATH)

    deferral_markers = (
        "migration/backfill",
        "alias repair",
        "beginner onboarding",
        "automatic promotion of a draft to stable without review",
    )

    assert _contains_any(knowledge_template, *deferral_markers)
    assert _contains_any(knowledge_schema, *deferral_markers)
    assert not _contains_any(
        knowledge_template,
        "runtime ingestion into planner, verifier, or executor context",
        "downstream runtime consumption",
    )
    assert not _contains_any(
        knowledge_schema,
        "runtime ingestion into planner, verifier, or executor context",
        "downstream runtime consumption",
    )
    assert _contains_any(knowledge_template, "review-knowledge", "review approval", "stable promotion")
    assert _contains_any(knowledge_schema, "review-knowledge", "review approval", "stable promotion")
