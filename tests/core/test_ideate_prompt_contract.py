"""Phase 0 contract guardrails for the ideate prompt surfaces."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_DIR = REPO_ROOT / "src" / "gpd" / "commands"
WORKFLOWS_DIR = REPO_ROOT / "src" / "gpd" / "specs" / "workflows"
IDEATE_COMMAND_PATH = COMMANDS_DIR / "ideate.md"
IDEATE_WORKFLOW_PATH = WORKFLOWS_DIR / "ideate.md"
HELP_WORKFLOW_PATH = WORKFLOWS_DIR / "help.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _contains_any(content: str, *phrases: str) -> bool:
    return any(phrase in content for phrase in phrases)


def _contains_any_lower(content: str, *phrases: str) -> bool:
    lowered = content.lower()
    return any(phrase.lower() in lowered for phrase in phrases)


def _contains_all_lower(content: str, *phrases: str) -> bool:
    lowered = content.lower()
    return all(phrase.lower() in lowered for phrase in phrases)


def _step_body(content: str, step_name: str) -> str:
    marker = f'<step name="{step_name}">'
    start = content.index(marker) + len(marker)
    end = content.index("</step>", start)
    return content[start:end]


def _help_command_entry(content: str, command_name: str) -> str:
    marker = f"**`{command_name}`**"
    start = content.index(marker)
    next_heading = content.find("\n**`", start + len(marker))
    if next_heading == -1:
        return content[start:]
    return content[start:next_heading]


def test_ideate_surfaces_land_together() -> None:
    assert IDEATE_COMMAND_PATH.exists() == IDEATE_WORKFLOW_PATH.exists()
    assert HELP_WORKFLOW_PATH.exists()


def test_ideate_command_is_registered_and_projectless_when_present() -> None:
    if not IDEATE_COMMAND_PATH.exists():
        pytest.skip("ideate command/workflow has not landed yet")

    raw_command = _read(IDEATE_COMMAND_PATH)

    assert "name: gpd:ideate" in raw_command
    assert "@{GPD_INSTALL_DIR}/workflows/ideate.md" in raw_command
    assert "context_mode: projectless" in raw_command
    assert "allowed-tools:" in raw_command
    for tool in ("ask_user", "file_read", "shell"):
        assert f"  - {tool}" in raw_command


def test_ideate_public_contract_is_projectless_non_durable_and_pre_project() -> None:
    if not IDEATE_COMMAND_PATH.exists():
        pytest.skip("ideate command/workflow has not landed yet")

    help_entry = _help_command_entry(_read(HELP_WORKFLOW_PATH), "gpd:ideate")

    assert _contains_all_lower(help_entry, "projectless", "non-durable", "multi-agent")
    assert _contains_any_lower(
        help_entry,
        "conversational multi-agent research session",
        "multi-agent research discussion",
    )
    assert _contains_any_lower(
        help_entry,
        "before committing to durable project artifacts",
        "pre-project refinement",
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


def test_ideate_contract_keeps_project_context_opt_in_and_user_named() -> None:
    if not IDEATE_COMMAND_PATH.exists():
        pytest.skip("ideate command/workflow has not landed yet")

    command = _read(IDEATE_COMMAND_PATH)
    workflow = _read(IDEATE_WORKFLOW_PATH)
    help_entry = _help_command_entry(_read(HELP_WORKFLOW_PATH), "gpd:ideate")

    assert _contains_any_lower(
        command,
        "opt-in context only",
        "must not be auto-ingested unless the user explicitly asks for specific context",
        "opt-in context instead of auto-loaded session state",
    )
    assert _contains_any_lower(
        workflow,
        "do not auto-read project files or local documents",
        "do not silently widen scope by loading broad project context",
    )
    assert _contains_any_lower(
        workflow,
        "only if the user explicitly asks to include existing context",
        "read only those named artifacts",
    )
    assert _contains_any_lower(
        help_entry,
        "keeps project context opt-in rather than auto-loading project state into the session",
        "project context opt-in",
    )


def test_ideate_contract_makes_persistence_non_goals_explicit_and_routes_outward() -> None:
    if not IDEATE_COMMAND_PATH.exists():
        pytest.skip("ideate command/workflow has not landed yet")

    command = _read(IDEATE_COMMAND_PATH)
    workflow = _read(IDEATE_WORKFLOW_PATH)
    help_entry = _help_command_entry(_read(HELP_WORKFLOW_PATH), "gpd:ideate")
    ideate_surfaces = f"{command}\n{workflow}\n{help_entry}"

    assert _contains_any_lower(
        ideate_surfaces,
        "keep orchestration in memory",
        "in-memory session",
    )
    assert _contains_any_lower(
        ideate_surfaces,
        "do not claim durable ideation session storage",
        "do not create durable session artifacts",
        "no durable ideation session files",
    )
    assert _contains_any_lower(
        help_entry,
        "does not create `research.md`",
        "does not create `gpd/ideation/`",
        "session transcripts",
        "resumable ideate state",
    )
    assert _contains_any_lower(
        ideate_surfaces,
        "subgroup transcripts",
        "subgroup promotion",
    )
    assert _contains_any_lower(
        ideate_surfaces,
        "do not add spawn-contract blocks",
        "spawn contracts",
    )
    assert "\n<spawn_contract>\n" not in ideate_surfaces
    assert "\n</spawn_contract>\n" not in ideate_surfaces
    assert _contains_any_lower(
        ideate_surfaces,
        "resume-work",
        "staged init",
        "artifact freshness gating",
    )
    assert _contains_all_lower(
        help_entry,
        "gpd:new-project",
        "gpd:discover",
        "gpd:research-phase",
    )
    assert _contains_any_lower(
        help_entry,
        "when you want durable artifacts",
        "more structured investigation flow",
    )


def test_ideate_closeout_stays_structured_non_durable_and_next_step_oriented_when_present() -> None:
    if not IDEATE_WORKFLOW_PATH.exists():
        pytest.skip("ideate command/workflow has not landed yet")

    command = _read(IDEATE_COMMAND_PATH)
    workflow = _read(IDEATE_WORKFLOW_PATH)

    if '<step name="session_finish">' not in workflow:
        pytest.skip("ideate closeout contract has not landed yet")

    session_finish = _step_body(workflow, "session_finish")

    assert _contains_any_lower(
        session_finish,
        "structured closeout summary",
        "structured summary",
    )
    assert _contains_any_lower(
        session_finish,
        "lightweight and conversational",
        "compact structured closeout",
    )
    assert _contains_any_lower(
        session_finish,
        "what do you want to do next?",
        "what-next",
    )
    assert _contains_any_lower(
        session_finish,
        "in-memory only",
        "do not add or imply durable ideation history",
    )
    assert _contains_any_lower(
        command,
        "explicit what-next prompt",
        "non-gpd next steps",
    )
    assert _contains_any(
        session_finish,
        "suggested follow-up actions",
        "promising next steps",
    )
