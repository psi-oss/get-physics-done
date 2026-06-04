"""High-level acceptance contracts for the complete Research Persona system."""

from __future__ import annotations

import importlib
import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from types import ModuleType

from tests.markdown_test_support import has_line_with_terms, normalize_text

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src" / "gpd"
CORE_ROOT = SRC_ROOT / "core"

CORE_MODULE_REQUIREMENTS: Mapping[str, tuple[str, ...]] = {
    "research_persona": (
        "ResearchPersona",
        "ResearchPersonaPatch",
        "ResearchPersonaCapsule",
        "build_research_persona_capsule",
        "project_research_persona",
        "load_research_persona",
        "save_research_persona",
    ),
    "research_persona_cli": (
        "build_show_payload",
        "build_validate_payload",
        "build_diff_payload",
        "build_apply_patch_payload",
        "build_forget_payload",
        "build_export_capsule_payload",
        "build_ingest_source_payload",
        "build_doppelganger_payload",
        "build_explain_plan_payload",
        "build_taste_check_payload",
    ),
    "research_persona_ingestion": (
        "ResearchPersonaSourceDocument",
        "ResearchPersonaEvidencePacket",
        "build_research_persona_ingestion_payload",
        "build_research_persona_patch_from_sources",
    ),
    "research_persona_applications": (
        "PersonaApplicationPromptSafety",
        "build_doppelganger_brief",
        "build_expertise_explanation_plan",
        "build_scientific_taste_assessment",
    ),
}
OPTIONAL_CORE_MODULES = (
    "research_persona_runtime",
    "research_persona_audit",
    "research_persona_audit_log",
    "research_persona_runtime_audit",
)

CLI_GROUP_NAME = "research-persona"
REQUIRED_CLI_COMMANDS = {
    "show",
    "validate",
    "diff",
    "apply-patch",
    "forget",
    "export-capsule",
    "ingest-source",
    "doppelganger",
    "explain-plan",
    "taste-check",
}
AUDIT_COMMAND_HINTS = ("audit", "audit-log", "runtime-audit")

COMMAND_PATH = SRC_ROOT / "commands" / "build-persona.md"
HELP_PATH = SRC_ROOT / "commands" / "help.md"
WORKFLOW_PATH = SRC_ROOT / "specs" / "workflows" / "build-persona.md"
WORKFLOW_MANIFEST_PATH = SRC_ROOT / "specs" / "workflows" / "build-persona-stage-manifest.json"
WORKFLOW_STAGE_DIR = SRC_ROOT / "specs" / "workflows" / "build-persona"
WORKFLOW_STAGE_FILES = (
    WORKFLOW_STAGE_DIR / "persona-intake.md",
    WORKFLOW_STAGE_DIR / "source-ingestion.md",
    WORKFLOW_STAGE_DIR / "persona-synthesis.md",
    WORKFLOW_STAGE_DIR / "approval-and-apply.md",
)
REFERENCE_PATH = SRC_ROOT / "specs" / "references" / "research" / "research-persona-applications.md"
BUILDER_AGENT_PATH = SRC_ROOT / "agents" / "gpd-persona-builder.md"
APPLICATION_AGENT_PATHS: Mapping[str, Path] = {
    "doppelganger": SRC_ROOT / "agents" / "gpd-researcher-doppelganger.md",
    "explainer": SRC_ROOT / "agents" / "gpd-expertise-explainer.md",
    "taste": SRC_ROOT / "agents" / "gpd-scientific-taste.md",
}

PROMPT_SURFACE_PATHS = (
    COMMAND_PATH,
    HELP_PATH,
    WORKFLOW_PATH,
    WORKFLOW_MANIFEST_PATH,
    REFERENCE_PATH,
    BUILDER_AGENT_PATH,
    *WORKFLOW_STAGE_FILES,
    *APPLICATION_AGENT_PATHS.values(),
)
PATCH_ONLY_TERMS = ("candidate", "patch", "apply-patch")
SOURCE_INGESTION_TERMS = ("source", "ingestion", "ingest-source")
APPROVAL_TERMS = ("explicit", "approval", "apply-patch")
CAPSULE_TERMS = ("prompt-safe", "capsule")
NO_RAW_STORAGE_TERMS = ("do not", "read", "raw persona storage")
NO_MUTATION_TERMS = ("do not", "mutate", "persona storage")
FEATURE_TERMS: Mapping[str, tuple[str, ...]] = {
    "doppelganger": ("doppelganger", "objections", "questions"),
    "explainer": ("explainer", "math", "code", "experiment", "theory", "applied"),
    "taste": ("taste", "novelty", "tractability", "risk"),
}
REPORT_TRACEABILITY_TERMS = (
    "Research Persona",
    "patch-only",
    "source ingestion",
    "Researcher Doppelganger",
    "Expertise-Aware Explanations",
    "Scientific Taste Model",
)

PRIVATE_STORE_MARKERS = (
    "raw persona storage",
    "raw profile",
    "raw private profile",
    "raw research persona",
    "research-persona/profile.json",
    "research_persona/profile.json",
    "~/.gpd/research-persona",
    "$GPD_DATA_DIR/research-persona",
    "${GPD_DATA_DIR:-~/.gpd}/research-persona",
    "load_research_persona(",
    "save_research_persona(",
    "research_persona_path(",
)
RAW_PROFILE_VERBS = (
    "copy",
    "embed",
    "expose",
    "include",
    "inject",
    "inspect",
    "load",
    "open",
    "paste",
    "read",
    "summarize",
)
DURABLE_MUTATION_VERBS = (
    "append",
    "create",
    "edit",
    "modify",
    "mutate",
    "overwrite",
    "persist",
    "save",
    "update",
    "write",
)
NEGATION_TERMS = (
    "do not",
    "don't",
    "forbid",
    "forbidden",
    "must not",
    "never",
    "not ",
    "not a license",
    "no direct",
    "not directly",
    "not raw",
    "without",
)
ALLOWED_ROUTE_TERMS = (
    "apply-patch",
    "export-capsule",
    "prompt-safe capsule",
    "privacy-filtered",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _rel(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _message(prefix: str, values: Iterable[object]) -> str:
    rendered = "\n".join(str(value) for value in values)
    return f"{prefix}:\n{rendered}"


def _public_names(module: ModuleType) -> set[str]:
    exported = getattr(module, "__all__", ())
    names = {str(name) for name in exported}
    names.update(name for name in dir(module) if not name.startswith("_"))
    return names


def _missing(required: Iterable[str], observed: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted(set(required) - set(observed)))


def _contains_terms(text: str, terms: Iterable[str]) -> bool:
    normalized = normalize_text(text).casefold()
    return all(term.casefold() in normalized for term in terms)


def _has_line(text: str, terms: Iterable[str]) -> bool:
    return has_line_with_terms(text, *terms, casefold=True)


def _existing_optional_modules() -> tuple[str, ...]:
    return tuple(stem for stem in OPTIONAL_CORE_MODULES if (CORE_ROOT / f"{stem}.py").is_file())


def _registered_research_persona_commands() -> set[str]:
    import gpd.cli as cli

    for group in cli.app.registered_groups:
        if group.name == CLI_GROUP_NAME:
            return {command.name for command in group.typer_instance.registered_commands if command.name}
    return set()


def _line_is_negated_or_routed(line: str) -> bool:
    lowered = line.casefold()
    return any(term in lowered for term in NEGATION_TERMS) or any(term in lowered for term in ALLOWED_ROUTE_TERMS)


def _unsafe_private_profile_lines(path: Path) -> tuple[str, ...]:
    lines: list[str] = []
    source_lines = _read(path).splitlines()
    for index, line in enumerate(source_lines):
        line_number = index + 1
        lowered = line.casefold()
        if not any(marker.casefold() in lowered for marker in PRIVATE_STORE_MARKERS):
            continue
        previous = source_lines[index - 1] if index > 0 else ""
        if _line_is_negated_or_routed(f"{previous} {line}"):
            continue
        has_raw_profile_read = any(verb in lowered for verb in RAW_PROFILE_VERBS)
        has_durable_mutation = any(verb in lowered for verb in DURABLE_MUTATION_VERBS)
        if has_raw_profile_read or has_durable_mutation:
            lines.append(f"{_rel(path)}:{line_number}: {line.strip()}")
    return tuple(lines)


def test_research_persona_core_modules_expose_complete_system_api() -> None:
    missing_by_module: list[str] = []
    for module_stem, required_names in CORE_MODULE_REQUIREMENTS.items():
        module = importlib.import_module(f"gpd.core.{module_stem}")
        missing = _missing(required_names, _public_names(module))
        if missing:
            missing_by_module.append(f"{module_stem}: {', '.join(missing)}")

    for module_stem in _existing_optional_modules():
        module = importlib.import_module(f"gpd.core.{module_stem}")
        public_names = _public_names(module)
        if not public_names:
            missing_by_module.append(module_stem)

    assert not missing_by_module, _message("missing Research Persona public API", missing_by_module)


def test_research_persona_cli_group_registers_local_controls_and_previews() -> None:
    command_names = _registered_research_persona_commands()
    missing = _missing(REQUIRED_CLI_COMMANDS, command_names)

    assert command_names, _message("missing CLI group", (CLI_GROUP_NAME,))
    assert not missing, _message("missing CLI commands", missing)

    if _existing_optional_modules():
        has_audit_command = any(any(hint in command for hint in AUDIT_COMMAND_HINTS) for command in command_names)
        assert has_audit_command, _message("missing optional audit CLI command", command_names)


def test_build_persona_workflow_is_patch_only_and_source_ingestion_aware() -> None:
    paths = (COMMAND_PATH, WORKFLOW_PATH, WORKFLOW_MANIFEST_PATH, *WORKFLOW_STAGE_FILES)
    missing_paths = tuple(_rel(path) for path in paths if not path.is_file())
    assert not missing_paths, _message("missing build-persona workflow paths", missing_paths)

    manifest = json.loads(_read(WORKFLOW_MANIFEST_PATH))
    stages = manifest.get("stages")
    stage_ids = {stage.get("id") for stage in stages if isinstance(stage, dict)} if isinstance(stages, list) else set()
    workflow_text = "\n\n".join(_read(path) for path in paths)

    missing_stages = _missing(
        ("persona_intake", "source_ingestion", "persona_synthesis", "approval_and_apply"), stage_ids
    )
    assert not missing_stages, _message("missing build-persona stages", missing_stages)
    assert _contains_terms(workflow_text, PATCH_ONLY_TERMS)
    assert _contains_terms(workflow_text, SOURCE_INGESTION_TERMS)
    assert _contains_terms(workflow_text, APPROVAL_TERMS)
    assert _contains_terms(workflow_text, CAPSULE_TERMS)


def test_application_agents_and_reference_use_prompt_safe_capsules() -> None:
    missing_paths = tuple(
        _rel(path) for path in (*APPLICATION_AGENT_PATHS.values(), REFERENCE_PATH) if not path.is_file()
    )
    assert not missing_paths, _message("missing application surfaces", missing_paths)

    reference_text = _read(REFERENCE_PATH)
    assert _contains_terms(reference_text, CAPSULE_TERMS)

    for role, path in APPLICATION_AGENT_PATHS.items():
        text = _read(path)
        assert _contains_terms(text, CAPSULE_TERMS)
        assert _contains_terms(text, FEATURE_TERMS[role])
        assert _has_line(text, NO_RAW_STORAGE_TERMS)
        assert _has_line(text, NO_MUTATION_TERMS)


def test_prompt_workflow_and_agent_surfaces_do_not_bypass_apply_patch_boundary() -> None:
    missing_paths = tuple(_rel(path) for path in PROMPT_SURFACE_PATHS if not path.is_file())
    assert not missing_paths, _message("missing persona prompt surfaces", missing_paths)

    unsafe_lines = [line for path in PROMPT_SURFACE_PATHS for line in _unsafe_private_profile_lines(path)]
    assert not unsafe_lines, _message("unsafe private-profile handling lines", unsafe_lines)


def test_tracked_surfaces_cover_the_system_and_final_acceptance() -> None:
    combined = "\n\n".join(_read(path) for path in PROMPT_SURFACE_PATHS if path.is_file())
    missing_terms = tuple(term for term in REPORT_TRACEABILITY_TERMS if term.casefold() not in combined.casefold())
    assert not missing_terms, _message("missing tracked-surface traceability terms", missing_terms)
