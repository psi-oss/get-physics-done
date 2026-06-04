"""Help inventory coverage for the research persona builder surface."""

from __future__ import annotations

from pathlib import Path

from gpd import registry as content_registry
from gpd.adapters.runtime_catalog import iter_runtime_descriptors
from gpd.command_labels import runtime_public_command_prefixes
from gpd.core import help_renderer
from tests.markdown_test_support import assert_forbidden_fragments, assert_required_fragments

REPO_ROOT = Path(__file__).resolve().parents[2]
HELP_WRAPPER_PATH = REPO_ROOT / "src" / "gpd" / "commands" / "help.md"
COMPACT_BLOCK_ID = "research-persona-builder-command-index"
DETAILED_BLOCK_ID = "research-persona-builder-detailed-command-reference"


def _read_help_wrapper() -> str:
    return HELP_WRAPPER_PATH.read_text(encoding="utf-8")


def _marker(block_id: str, boundary: str) -> str:
    return f"<!-- gpd-help:{block_id}:{boundary} -->"


def _extract_block(text: str, block_id: str) -> str:
    start_marker = _marker(block_id, "start")
    end_marker = _marker(block_id, "end")
    start = text.index(start_marker) + len(start_marker)
    end = text.index(end_marker, start)
    return text[start:end]


def _runtime_specific_fallback_forbidden_fragments() -> tuple[str, str]:
    prefix = next(prefix for prefix in runtime_public_command_prefixes() if prefix.startswith("/"))
    descriptor = next(
        descriptor for descriptor in iter_runtime_descriptors() if descriptor.public_command_surface_prefix == prefix
    )
    surface_label = descriptor.validated_command_surface.removeprefix("public_runtime_").replace("_", "-")
    return prefix, surface_label


def test_build_persona_help_fallback_inventory_has_compact_and_detailed_entries() -> None:
    help_wrapper = _read_help_wrapper()
    compact = _extract_block(help_wrapper, COMPACT_BLOCK_ID)
    detailed = _extract_block(help_wrapper, DETAILED_BLOCK_ID)

    assert_required_fragments(
        compact,
        (
            "- `gpd:build-persona [focus|--from-current-project|--interview-only]`",
            "private research-persona patch",
        ),
        context="build-persona compact help fallback",
    )
    assert_required_fragments(
        detailed,
        (
            "**`gpd:build-persona [focus|--from-current-project|--interview-only]`**",
            "explicit user consent",
            "gpd research-persona apply-patch",
            "privacy projection",
            "Researcher Doppelganger",
            "Expertise-Aware Explanations",
            "Scientific Taste Model",
        ),
        context="build-persona detailed help fallback",
    )


def test_build_persona_help_fallback_inventory_is_runtime_neutral() -> None:
    help_wrapper = _read_help_wrapper()
    blocks = (
        _extract_block(help_wrapper, COMPACT_BLOCK_ID),
        _extract_block(help_wrapper, DETAILED_BLOCK_ID),
    )
    fallback_inventory = "\n".join(blocks)

    assert_forbidden_fragments(
        fallback_inventory,
        _runtime_specific_fallback_forbidden_fragments(),
        context="build-persona help fallback inventory",
    )


def test_build_persona_renderer_visibility_tracks_command_metadata_when_available() -> None:
    content_registry.invalidate_cache()
    help_renderer.help_command_groups.cache_clear()
    help_renderer._root_detailed_reference_commands.cache_clear()

    labels = set(content_registry.list_commands(name_format="label"))
    command_index = help_renderer.render_command_index_markdown()
    root_detail = help_renderer.render_root_detailed_command_reference_markdown()

    if "gpd:build-persona" not in labels:
        assert_forbidden_fragments(command_index, "`gpd:build-persona", context="build-persona command index")
        assert_forbidden_fragments(root_detail, "**`gpd:build-persona", context="build-persona root detail")
        return

    command = content_registry.get_command("gpd:build-persona")
    assert command.help is not None
    assert_required_fragments(command_index, "`gpd:build-persona", context="build-persona command index")
    if command.help.root_detail_order is not None:
        assert_required_fragments(root_detail, "**`gpd:build-persona", context="build-persona root detail")
