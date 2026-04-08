"""Prompt-contract guardrails for the knowledge-digest authoring/update MVP."""

from __future__ import annotations

from pathlib import Path

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

    assert "name: gpd:digest-knowledge" in command
    assert "context_mode: project-aware" in command
    assert "@{GPD_INSTALL_DIR}/workflows/digest-knowledge.md" in command

    command_index = _section(help_workflow, "## Command Index", "## Detailed Command Reference")
    detailed_reference = _section(help_workflow, "## Detailed Command Reference", "### Optional Local CLI Add-Ons")

    assert "gpd:digest-knowledge" in command_index
    assert "gpd:digest-knowledge" in detailed_reference


def test_digest_knowledge_workflow_requires_explicit_create_or_update_branching() -> None:
    workflow = _read(DIGEST_WORKFLOW_PATH)

    assert _contains_any(workflow, "create new draft", "create draft", "create")
    assert _contains_any(workflow, "update existing draft", "update draft", "update")
    assert _contains_any(workflow, "stop on ambiguity", "ambiguous", "multiple plausible", "ask the user")
    assert _contains_any(workflow, "draft", "existing target", "existing doc")


def test_digest_knowledge_workflow_documents_deterministic_target_resolution_and_input_validation() -> None:
    workflow = _read(DIGEST_WORKFLOW_PATH)

    assert "GPD/knowledge/{knowledge_id}.md" in workflow
    assert _contains_any(workflow, "explicit file path", "existing file path", "file path must exist", "must exist before")
    assert _contains_any(workflow, "2401.12345", "modern arxiv", "modern arXiv")
    assert _contains_any(workflow, "hep-th/9901001", "legacy arxiv", "legacy arXiv")


def test_digest_knowledge_templates_keep_runtime_ingestion_deferred_but_not_public_exposure_deferred() -> None:
    knowledge_template = _read(KNOWLEDGE_TEMPLATE_PATH)
    knowledge_schema = _read(KNOWLEDGE_SCHEMA_PATH)

    runtime_deferral_markers = (
        "runtime ingestion into planner, verifier, or executor context",
        "runtime ingestion",
        "downstream runtime consumption",
    )

    assert _contains_any(knowledge_template, *runtime_deferral_markers)
    assert _contains_any(knowledge_schema, *runtime_deferral_markers)
    assert "public command registration" not in knowledge_template
    assert "help inventory exposure" not in knowledge_template
    assert "public command registration" not in knowledge_schema
    assert "help inventory exposure" not in knowledge_schema
