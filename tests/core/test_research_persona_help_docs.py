"""Docs and help coverage for the complete Research Persona surface."""

from __future__ import annotations

import re
from pathlib import Path

from tests.assertion_taxonomy_support import MatchMode, assert_prompt_contracts, semantic_concept
from tests.markdown_test_support import extract_markdown_section, normalize_text

REPO_ROOT = Path(__file__).resolve().parents[2]
README_PATH = REPO_ROOT / "README.md"
HELP_WRAPPER_PATH = REPO_ROOT / "src" / "gpd" / "commands" / "help.md"
CLI_PATH = REPO_ROOT / "src" / "gpd" / "cli.py"
BUILD_PERSONA_WORKFLOW_PATH = REPO_ROOT / "src" / "gpd" / "specs" / "workflows" / "build-persona.md"
PERSONA_APPLICATIONS_REFERENCE_PATH = (
    REPO_ROOT / "src" / "gpd" / "specs" / "references" / "research" / "research-persona-applications.md"
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _research_persona_cli_commands() -> tuple[str, ...]:
    cli = _read(CLI_PATH)
    start_match = re.search(r"research_persona_app\s*=\s*typer[.]Typer", cli)
    assert start_match is not None
    start = start_match.start()
    end = cli.index("def _integrations_config_path", start)
    block = cli[start:end]
    return tuple(re.findall(r'@research_persona_app\.command\("([^"]+)"\)', block))


def _combined_user_docs() -> str:
    return "\n\n".join((_read(README_PATH), _read(HELP_WRAPPER_PATH)))


def _non_negated_prompt_profile_lines(text: str) -> list[str]:
    negations = ("do not", "don't", "must not", "never", "not ", "without", "rather than")
    prompt_markers = ("prompt", "runtime context", "agent context")
    profile_markers = ("full private profile", "raw profile", "raw private profile")
    action_markers = ("copy", "embed", "include", "inject", "load", "paste", "place", "summarize")
    hits: list[str] = []
    for line in text.splitlines():
        lowered = line.casefold()
        if not any(prompt in lowered for prompt in prompt_markers):
            continue
        if not any(profile in lowered for profile in profile_markers):
            continue
        if not any(action in lowered for action in action_markers):
            continue
        if any(negation in lowered for negation in negations):
            continue
        hits.append(line.strip())
    return hits


def test_research_persona_docs_cover_local_private_patch_and_audit_flow() -> None:
    readme = _read(README_PATH)
    section = extract_markdown_section(readme, "## Advanced CLI Utilities", context="README.md")

    assert_prompt_contracts(
        section,
        *semantic_concept(
            "research persona local private storage",
            required=("Research Persona", "local-private", "machine-local", "not project state"),
            match=MatchMode.CASEFOLD_NORMALIZED,
        ),
        *semantic_concept(
            "research persona consented patch flow",
            required=("explicitly consented", "patch-only", "candidate", "explicit approval"),
            match=MatchMode.CASEFOLD_NORMALIZED,
        ),
        *semantic_concept(
            "research persona audit trail",
            required=("diff", "apply-patch", "history", "tombstone"),
            match=MatchMode.CASEFOLD_NORMALIZED,
        ),
        *semantic_concept(
            "research persona source ingestion",
            required=("current-project", "paper", "BibTeX", "repository", "user statement"),
            match=MatchMode.CASEFOLD_NORMALIZED,
        ),
    )


def test_research_persona_docs_list_actual_cli_subcommands() -> None:
    docs = _combined_user_docs()
    missing = [command for command in _research_persona_cli_commands() if f"gpd research-persona {command}" not in docs]

    assert missing == []


def test_research_persona_docs_explain_capsule_applications_without_profile_prompting() -> None:
    docs = _combined_user_docs()
    normalized = normalize_text(docs)

    assert_prompt_contracts(
        normalized,
        *semantic_concept(
            "research persona capsule applications",
            required=("prompt-safe", "capsule", "Doppelganger", "Explanations", "Taste"),
            match=MatchMode.CASEFOLD_NORMALIZED,
        ),
        *semantic_concept(
            "research persona no silent memory",
            required=("should not create silent memory",),
            match=MatchMode.CASEFOLD_NORMALIZED,
        ),
    )
    assert _non_negated_prompt_profile_lines(docs) == []


def test_research_persona_tracked_docs_cover_complete_system_and_review_flow() -> None:
    combined = normalize_text(
        "\n\n".join(
            (
                _read(README_PATH),
                _read(HELP_WRAPPER_PATH),
                _read(CLI_PATH),
                _read(BUILD_PERSONA_WORKFLOW_PATH),
                _read(PERSONA_APPLICATIONS_REFERENCE_PATH),
            )
        )
    )

    assert_prompt_contracts(
        combined,
        *semantic_concept(
            "research persona tracked system inventory",
            required=("Research Persona", "build-persona", "ingest-source", "export-capsule", "apply-patch"),
            match=MatchMode.CASEFOLD_NORMALIZED,
        ),
        *semantic_concept(
            "research persona ambitious features",
            required=("Researcher Doppelganger", "Expertise-Aware Explanations", "Scientific Taste Model"),
            match=MatchMode.CASEFOLD_NORMALIZED,
        ),
        *semantic_concept(
            "research persona explicit review flow",
            required=("validate", "diff", "explicit approval", "candidate patch"),
            match=MatchMode.CASEFOLD_NORMALIZED,
        ),
    )
