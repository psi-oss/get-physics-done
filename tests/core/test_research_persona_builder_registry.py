"""Registry guardrails for the research persona builder workflow."""

from __future__ import annotations

from pathlib import Path

import gpd.registry as registry
from tests.markdown_test_support import assert_required_fragments

COMMAND_NAME = "gpd:build-persona"
COMMAND_SLUG = "build-persona"
AGENT_NAME = "gpd-persona-builder"
PATCH_APPROVAL_COMMAND = "gpd research-persona apply-patch"

COMMAND_PATH = registry.COMMANDS_DIR / f"{COMMAND_SLUG}.md"
AGENT_PATH = registry.AGENTS_DIR / f"{AGENT_NAME}.md"
WORKFLOW_INDEX_PATH = registry.SPECS_DIR / "workflows" / f"{COMMAND_SLUG}.md"
WORKFLOW_MANIFEST_PATH = registry.SPECS_DIR / "workflows" / f"{COMMAND_SLUG}-stage-manifest.json"

PRIVATE_STORE_MARKERS = (
    "~/.gpd/research-persona",
    "${GPD_DATA_DIR}/research-persona",
    "$GPD_DATA_DIR/research-persona",
    "research-persona/profile.json",
    "load_research_persona(",
    "save_research_persona(",
    "research_persona_path(",
)
DIRECT_MUTATION_VERBS = ("append", "edit", "modify", "mutate", "overwrite", "patch", "save", "update", "write")
NEGATION_MARKERS = ("do not", "don't", "must not", "never", "no direct", "without")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _persona_builder_texts() -> dict[str, str]:
    paths = {
        "command": COMMAND_PATH,
        "agent": AGENT_PATH,
        "workflow": WORKFLOW_INDEX_PATH,
    }
    return {name: _read(path) for name, path in paths.items() if path.is_file()}


def _direct_private_store_mutation_lines(text: str, marker: str) -> list[str]:
    marker_lower = marker.lower()
    matches: list[str] = []
    for line in text.splitlines():
        lowered = line.lower()
        if marker_lower not in lowered:
            continue
        if not any(verb in lowered for verb in DIRECT_MUTATION_VERBS):
            continue
        if any(negation in lowered for negation in NEGATION_MARKERS):
            continue
        matches.append(line.strip())
    return matches


def test_build_persona_command_file_and_workflow_sidecars_exist() -> None:
    assert COMMAND_PATH.is_file()
    assert WORKFLOW_INDEX_PATH.is_file()
    assert WORKFLOW_MANIFEST_PATH.is_file()


def test_build_persona_command_is_registry_discoverable_and_workflow_backed() -> None:
    registry.invalidate_cache()

    command = registry.get_command(COMMAND_NAME)

    assert command.name == COMMAND_NAME
    assert command.path == str(COMMAND_PATH)
    assert command.context_mode == "project-aware"
    assert command.staged_loading is not None
    assert command.staged_loading.workflow_id == COMMAND_SLUG
    assert COMMAND_NAME in registry.list_commands(name_format="label")


def test_build_persona_help_metadata_is_owned_by_registry_frontmatter() -> None:
    registry.invalidate_cache()

    command = registry.get_command(COMMAND_NAME)

    assert command.description
    assert_required_fragments(command.description.lower(), "research persona", context="build-persona description")
    assert command.argument_hint
    assert command.help is not None
    assert_required_fragments(command.help.group.lower(), "memory", context="build-persona help group")
    assert command.help.display_signature.startswith(COMMAND_NAME)
    assert command.help.detail_signature.startswith(COMMAND_NAME)
    assert command.help.compact_description is not None
    assert_required_fragments(
        command.help.compact_description.lower(),
        "persona",
        context="build-persona compact description",
    )
    assert command.help.examples


def test_persona_builder_agent_is_registry_discoverable() -> None:
    registry.invalidate_cache()

    agent = registry.get_agent(AGENT_NAME)

    assert agent.name == AGENT_NAME
    assert agent.path == str(AGENT_PATH)
    assert_required_fragments(
        agent.description.lower(), "research persona", context="persona builder agent description"
    )
    assert agent.shared_state_authority == "return_only"
    assert AGENT_NAME in registry.list_agents()


def test_command_and_agent_route_profile_changes_through_patch_approval() -> None:
    texts = _persona_builder_texts()

    assert texts.keys() >= {"command", "agent"}
    for surface, text in texts.items():
        assert PATCH_APPROVAL_COMMAND in text, f"{surface} must route durable profile changes through CLI approval"


def test_persona_builder_text_avoids_direct_private_store_mutation_instructions() -> None:
    texts = _persona_builder_texts()

    assert texts.keys() >= {"command", "agent"}
    for surface, text in texts.items():
        for marker in PRIVATE_STORE_MARKERS:
            direct_mutation_lines = _direct_private_store_mutation_lines(text, marker)
            assert direct_mutation_lines == [], (
                f"{surface} should not instruct direct private-store mutation via {marker!r}: {direct_mutation_lines}"
            )
