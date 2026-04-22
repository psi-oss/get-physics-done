"""Current public-contract guardrails for the post-Phase-10 public ideate surfaces."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_DIR = REPO_ROOT / "src" / "gpd" / "commands"
WORKFLOWS_DIR = REPO_ROOT / "src" / "gpd" / "specs" / "workflows"
PUBLIC_COMMAND_NAME = "gpd:agentic-discussion"
PUBLIC_COMMAND_PATH = COMMANDS_DIR / "agentic-discussion.md"
IDEATE_WORKFLOW_PATH = WORKFLOWS_DIR / "ideate.md"
HELP_WORKFLOW_PATH = WORKFLOWS_DIR / "help.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _contains_any_lower(content: str, *phrases: str) -> bool:
    lowered = content.lower()
    return any(phrase.lower() in lowered for phrase in phrases)


def _contains_all_lower(content: str, *phrases: str) -> bool:
    lowered = content.lower()
    return all(phrase.lower() in lowered for phrase in phrases)


def _help_command_entry(content: str, command_name: str) -> str:
    marker = f"**`{command_name}`**"
    start = content.index(marker)
    next_heading = content.find("\n**`", start + len(marker))
    if next_heading == -1:
        return content[start:]
    return content[start:next_heading]


def _assert_ideate_surfaces_exist() -> None:
    assert PUBLIC_COMMAND_PATH.exists()
    assert IDEATE_WORKFLOW_PATH.exists()
    assert HELP_WORKFLOW_PATH.exists()


def test_ideate_surfaces_land_together() -> None:
    assert PUBLIC_COMMAND_PATH.exists() == IDEATE_WORKFLOW_PATH.exists()
    assert HELP_WORKFLOW_PATH.exists()


def test_ideate_command_exposes_a_projectless_public_entrypoint() -> None:
    _assert_ideate_surfaces_exist()

    command = _read(PUBLIC_COMMAND_PATH)

    assert f"name: {PUBLIC_COMMAND_NAME}" in command
    assert 'argument-hint: "[topic, question, or domain] [--preset fast|balanced|deep]"' in command
    assert "context_mode: projectless" in command
    assert "@{GPD_INSTALL_DIR}/workflows/ideate.md" in command
    assert _contains_all_lower(
        command,
        "description:",
        "projectless",
        "conversational multi-agent research session",
    )
    assert _contains_any_lower(
        command,
        "before durable project work",
        "before committing to durable project artifacts",
    )
    assert _contains_any_lower(
        command,
        "live conversational session",
        "in-memory conversational research session",
    )
    assert _contains_all_lower(
        command,
        "internal approval loops",
        "bounded rounds",
        "review gates",
    )


def test_ideate_public_contract_is_projectless_non_durable_and_pre_project() -> None:
    _assert_ideate_surfaces_exist()

    help_entry = _help_command_entry(_read(HELP_WORKFLOW_PATH), PUBLIC_COMMAND_NAME)

    assert _contains_all_lower(help_entry, "projectless", "non-durable", "multi-agent")
    assert _contains_any_lower(
        help_entry,
        "conversational multi-agent research session",
        "multi-agent research discussion",
    )
    assert _contains_any_lower(
        help_entry,
        "optional pre-project",
        "before you open a durable gpd project",
        "before durable project work",
    )
    assert _contains_any_lower(
        help_entry,
        "works from any folder",
        "do not need an initialized gpd project first",
    )
    assert _contains_any_lower(
        help_entry,
        "pressure-test assumptions",
        "pressure-testing",
    )
    assert _contains_any_lower(
        help_entry,
        "concrete question",
        "broader research brief",
        "rough starting direction",
    )
    assert _contains_any_lower(
        help_entry,
        "usage: `gpd:agentic-discussion`",
        "usage: `gpd:agentic-discussion [topic, question, or domain] [--preset fast|balanced|deep]`",
    )


def test_ideate_contract_keeps_project_context_opt_in_and_user_named() -> None:
    _assert_ideate_surfaces_exist()

    command = _read(PUBLIC_COMMAND_PATH)
    help_entry = _help_command_entry(_read(HELP_WORKFLOW_PATH), PUBLIC_COMMAND_NAME)

    assert _contains_any_lower(
        command,
        "opt-in context only",
        "must not be auto-ingested unless the user explicitly asks for specific context",
        "opt-in context instead of auto-loaded session state",
    )
    assert _contains_any_lower(
        command,
        "existing `gpd/` project files are optional supporting context only",
        "existing gpd project files are optional supporting context only",
    )
    assert _contains_any_lower(
        command,
        "do not read them unless the user explicitly asks for specific files or artifacts to be included",
        "do not read them unless the user explicitly asks for specific files",
    )
    assert _contains_any_lower(
        help_entry,
        "keeps project context opt-in rather than auto-loading project state into the session",
        "project context opt-in",
    )


def test_ideate_contract_makes_persistence_non_goals_explicit_and_routes_outward() -> None:
    _assert_ideate_surfaces_exist()

    command = _read(PUBLIC_COMMAND_PATH)
    help_entry = _help_command_entry(_read(HELP_WORKFLOW_PATH), PUBLIC_COMMAND_NAME)

    assert _contains_any_lower(
        command,
        "do not claim durable ideation session storage",
        "durable ideation artifacts",
        "resumable session state",
    )
    assert _contains_any_lower(
        help_entry,
        "does not create `project.md`",
        "does not create `research.md`",
        "does not create `roadmap.md`",
        "does not create `gpd/ideation/`",
        "does not create `gpd/quick/`",
        "session transcripts",
        "resumable ideate state",
    )
    assert _contains_all_lower(
        help_entry,
        "gpd:new-project",
        "gpd:discover",
        "gpd:research-phase",
        "gpd:quick",
    )
    assert _contains_any_lower(help_entry, "durable project setup", "roadmap")
    assert _contains_any_lower(help_entry, "durable survey artifacts", "conversational pre-project session")
    assert _contains_any_lower(help_entry, "bounded task", "durable quick-task outputs")
