"""Contracts for Phase 4 research-persona source ingestion surfaces."""

from __future__ import annotations

import json
from pathlib import Path

import gpd.registry as registry
from gpd.core.workflow_staging import validate_workflow_stage_manifest_payload
from tests.markdown_test_support import has_line_with_terms

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMAND_NAME = "gpd:build-persona"
WORKFLOW_ID = "build-persona"
SOURCE_STAGE_ID = "source_ingestion"
COMMAND_PATH = REPO_ROOT / "src" / "gpd" / "commands" / "build-persona.md"
WORKFLOW_PATH = REPO_ROOT / "src" / "gpd" / "specs" / "workflows" / "build-persona.md"
MANIFEST_PATH = REPO_ROOT / "src" / "gpd" / "specs" / "workflows" / "build-persona-stage-manifest.json"
STAGE_ROOT = REPO_ROOT / "src" / "gpd" / "specs" / "workflows" / "build-persona"
INTAKE_STAGE_PATH = STAGE_ROOT / "persona-intake.md"
SOURCE_STAGE_PATH = STAGE_ROOT / "source-ingestion.md"
SYNTHESIS_STAGE_PATH = STAGE_ROOT / "persona-synthesis.md"
APPROVAL_STAGE_PATH = STAGE_ROOT / "approval-and-apply.md"

EXPECTED_STAGE_IDS = (
    "persona_intake",
    SOURCE_STAGE_ID,
    "persona_synthesis",
    "approval_and_apply",
)
SOURCE_STAGE_AUTHORITY = "workflows/build-persona/source-ingestion.md"
SOURCE_STAGE_TOOLS = frozenset(
    (
        "ask_user",
        "file_read",
        "file_write",
        "find_files",
        "search_files",
        "shell",
    )
)
SOURCE_STAGE_WRITES = frozenset(
    (
        "GPD/persona/source-candidate-patch.json",
        "GPD/persona/source-ingestion-summary.md",
    )
)
SOURCE_MODE_TERMS = (
    "interview",
    "current project",
    "paper path",
    "BibTeX path",
    "repository scan",
    "manual JSON patch",
    "user statement",
    "project_scan",
    "paper_import",
    "bibtex_import",
    "repo_scan",
    "manual_patch",
    "user_statement",
)
SOURCE_BRIDGE_TERMS = (
    "gpd research-persona ingest-source",
    "source_kind",
    "sources",
    "evidence_refs",
    "confidence",
    "privacy label",
)
APPROVAL_ROUTE_TERMS = (
    "gpd research-persona validate",
    "gpd research-persona diff",
    "explicit user approval",
    "gpd research-persona apply-patch",
)
PROMPT_SAFE_TERMS = (
    "prompt-safe",
    "capsule",
    "raw private profile",
    "never_prompt",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _combined_surface_text() -> str:
    paths = (
        COMMAND_PATH,
        WORKFLOW_PATH,
        INTAKE_STAGE_PATH,
        SOURCE_STAGE_PATH,
        SYNTHESIS_STAGE_PATH,
        APPROVAL_STAGE_PATH,
    )
    return "\n\n".join(_read(path) for path in paths)


def _missing_terms(text: str, terms: tuple[str, ...]) -> list[str]:
    lowered = text.casefold()
    return [term for term in terms if term.casefold() not in lowered]


def _manifest():
    payload = json.loads(_read(MANIFEST_PATH))
    return validate_workflow_stage_manifest_payload(payload, expected_workflow_id=WORKFLOW_ID)


def test_build_persona_source_ingestion_stage_is_manifested_and_schema_valid() -> None:
    manifest = _manifest()
    source_stage = manifest.stage(SOURCE_STAGE_ID)

    assert manifest.stage_ids() == EXPECTED_STAGE_IDS
    assert source_stage.required_init_fields == ()
    assert SOURCE_STAGE_AUTHORITY in source_stage.loaded_authorities
    assert SOURCE_STAGE_AUTHORITY in source_stage.mode_paths
    assert SOURCE_STAGE_TOOLS == frozenset(source_stage.allowed_tools)
    assert SOURCE_STAGE_WRITES == frozenset(source_stage.writes_allowed)
    assert source_stage.next_stages == ("persona_synthesis",)


def test_build_persona_registry_uses_updated_source_ingestion_manifest() -> None:
    registry.invalidate_cache()

    command = registry.get_command(COMMAND_NAME)

    assert command.staged_loading is not None
    assert command.staged_loading.workflow_id == WORKFLOW_ID
    assert command.staged_loading.stage_ids() == EXPECTED_STAGE_IDS


def test_source_ingestion_surfaces_declare_all_supported_modes() -> None:
    missing = _missing_terms(_combined_surface_text(), SOURCE_MODE_TERMS)

    assert not missing, "source ingestion surfaces are missing mode terms: " + ", ".join(missing)


def test_source_ingestion_uses_cli_bridge_before_patch_review() -> None:
    text = _combined_surface_text()
    missing = _missing_terms(text, SOURCE_BRIDGE_TERMS)

    assert not missing, "source ingestion surfaces are missing bridge terms: " + ", ".join(missing)
    assert has_line_with_terms(text, "exact", "source", "category", "path", casefold=True)
    assert has_line_with_terms(text, "No silent memory", casefold=True)


def test_source_ingestion_preserves_validate_diff_approval_apply_route() -> None:
    text = _read(APPROVAL_STAGE_PATH)
    positions = [text.casefold().find(term.casefold()) for term in APPROVAL_ROUTE_TERMS]

    assert all(position >= 0 for position in positions)
    assert positions == sorted(positions)


def test_source_ingestion_keeps_capsules_prompt_safe() -> None:
    text = _combined_surface_text()
    missing = _missing_terms(text, PROMPT_SAFE_TERMS)

    assert not missing, "source ingestion surfaces are missing privacy terms: " + ", ".join(missing)
    assert has_line_with_terms(text, "do not", "raw private", "prompts", casefold=True)
    assert has_line_with_terms(text, "never_prompt", "prompt-visible", casefold=True)
