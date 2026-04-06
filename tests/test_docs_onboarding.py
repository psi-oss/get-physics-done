"""Focused regression coverage for beginner onboarding docs."""

from __future__ import annotations

from pathlib import Path

import pytest

from gpd.adapters.runtime_catalog import get_shared_install_metadata
from gpd.core.onboarding_surfaces import beginner_runtime_surfaces
from tests.doc_surface_contracts import assert_beginner_hub_preflight_contract, assert_beginner_startup_routing_contract
from tests.runtime_test_support import runtime_onboarding_doc_filename

REPO_ROOT = Path(__file__).resolve().parents[1]
_SHARED_INSTALL = get_shared_install_metadata()


def _read(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def _assert_fragments(content: str, fragments: tuple[str, ...]) -> None:
    for fragment in fragments:
        assert fragment in content


def _assert_in_order(content: str, fragments: tuple[str, ...]) -> None:
    positions = [content.index(fragment) for fragment in fragments]
    assert positions == sorted(positions)


def _normalize_markdown_table(content: str) -> str:
    return content.replace("`", "")


def _markdown_section(content: str, heading: str) -> str:
    marker = f"{heading}\n"
    start = content.index(marker)
    next_heading = content.find("\n## ", start + len(marker))
    if next_heading == -1:
        return content[start:]
    return content[start:next_heading]


def _expected_install_row(surface) -> str:
    return f"| {surface.display_name} | `npx -y get-physics-done {surface.install_flag} --local` |"


@pytest.mark.parametrize("surface", beginner_runtime_surfaces(), ids=lambda surface: surface.runtime_name)
def test_runtime_quickstarts_surface_the_beginner_next_steps(surface) -> None:
    content = _read(f"docs/{runtime_onboarding_doc_filename(surface.runtime_name)}")
    fragments = (
        surface.help_command,
        surface.start_command,
        surface.tour_command,
        surface.new_project_minimal_command,
        surface.map_research_command,
        surface.resume_work_command,
        surface.settings_command,
    )
    _assert_fragments(content, fragments)
    _assert_in_order(content, fragments[:3])
    assert "Back to the onboarding hub: [GPD Onboarding Hub](./README.md)." in content
    assert "## Choose this runtime if" in content
    assert "## What must already be true" in content
    assert "## Return to work" in content


@pytest.mark.parametrize(
    "doc_name",
    ["macos.md", "windows.md", "linux.md"],
)
def test_os_quickstarts_install_matrix_matches_runtime_catalog(doc_name: str) -> None:
    content = _read(f"docs/{doc_name}")
    install_section = _markdown_section(content, "## Install GPD")

    for surface in beginner_runtime_surfaces():
        assert _expected_install_row(surface) in install_section


@pytest.mark.parametrize(
    "doc_name",
    ["macos.md", "windows.md", "linux.md"],
)
def test_os_quickstarts_link_runtime_guides_and_post_install_help(doc_name: str) -> None:
    content = _read(f"docs/{doc_name}")
    runtime_commands = tuple(
        dict.fromkeys(
            command
            for surface in beginner_runtime_surfaces()
            for command in (surface.start_command, surface.tour_command, surface.resume_work_command)
        )
    )

    _assert_fragments(
        content,
        (
            "Confirm success",
            "gpd --help",
            "Not sure which path fits this folder",
            "Want a guided overview",
            "Start a new project",
            "Map an existing folder",
            "Rediscover the workspace in your normal terminal",
            "Continue in the reopened runtime",
            "gpd resume",
            "gpd resume --recent",
            "resume-work",
            *runtime_commands,
        ),
    )
    assert "Back to the onboarding hub: [GPD Onboarding Hub](./README.md)." in content
    for surface in beginner_runtime_surfaces():
        assert f"./{runtime_onboarding_doc_filename(surface.runtime_name)}" in content


def test_docs_onboarding_hub_links_os_and_runtime_guides() -> None:
    content = _read("docs/README.md")
    assert_beginner_hub_preflight_contract(content)

    _assert_fragments(
        content,
        (
            "# GPD Onboarding Hub",
            "Show the full beginner path on one page",
            "## First: terminal vs runtime",
            "Your **normal terminal**",
            "Your **runtime**",
            "Common beginner terms",
            "./macos.md",
            "./windows.md",
            "./linux.md",
            "## After the guides",
        ),
    )
    assert_beginner_startup_routing_contract(content)
    for surface in beginner_runtime_surfaces():
        guide = runtime_onboarding_doc_filename(surface.runtime_name)
        assert f"./{guide}" in content
        assert f"{_SHARED_INSTALL.bootstrap_command} {surface.install_flag} --local" in content
    _assert_in_order(
        content,
        (
            "## Before you open the guides",
            "## First: terminal vs runtime",
            "## Choose your OS",
            "## Choose your runtime",
            "## After the guides",
        ),
    )


def test_root_readme_start_here_links_to_docs_onboarding_hub() -> None:
    content = _read("README.md")
    start_here = _markdown_section(content, "## Start Here")

    _assert_fragments(
        start_here,
        (
            "[Beginner Onboarding Hub](./docs/README.md)",
            "If you are new to terminals, start with the [Beginner Onboarding Hub](./docs/README.md).",
            "Use the hub as the single beginner path",
            "There are two places you type commands:",
            "In your normal system terminal:",
            "Inside your AI runtime:",
        ),
    )


def test_root_readme_supported_runtimes_table_matches_beginner_runtime_surfaces() -> None:
    content = _read("README.md")
    supported_runtimes = _markdown_section(content, "## Supported Runtimes")
    normalized_supported_runtimes = _normalize_markdown_table(supported_runtimes)

    for surface in beginner_runtime_surfaces():
        expected_row = (
            f"| {surface.display_name} | {surface.install_flag} | {surface.help_command} | "
            f"{surface.start_command} | {surface.tour_command} | {surface.new_project_minimal_command} | "
            f"{surface.map_research_command} | {surface.resume_work_command} |"
        )
        assert expected_row in normalized_supported_runtimes

    assert "Config path overrides" not in content
    assert "CLAUDE_CONFIG_DIR" not in content
    assert "CODEX_SKILLS_DIR" not in content
    assert "GEMINI_CONFIG_DIR" not in content
    assert "OPENCODE_CONFIG_DIR" not in content


def test_runtime_quickstarts_keep_current_provider_specific_setup_notes() -> None:
    docs = {
        surface.runtime_name: _read(f"docs/{runtime_onboarding_doc_filename(surface.runtime_name)}")
        for surface in beginner_runtime_surfaces()
    }

    assert any("Pro, Max, Teams, Enterprise, or Console account" in content for content in docs.values())
    assert any("GOOGLE_CLOUD_PROJECT" in content for content in docs.values())
    assert any("/connect" in content for content in docs.values())


def test_progress_docs_do_not_reference_nonexistent_list_todos_command() -> None:
    for relative_path in ("src/gpd/commands/progress.md", "src/gpd/specs/workflows/progress.md"):
        content = _read(relative_path)
        assert "list-todos" not in content
        assert "gpd --raw init todos" in content


def test_progress_workflow_reconcile_mode_uses_supported_state_snapshot_fields() -> None:
    content = _read("src/gpd/specs/workflows/progress.md")

    assert "gpd --raw state snapshot" in content
    assert ".current_phase --default \"\"" in content
    assert ".current_plan --default \"\"" in content
    assert ".current_phase.number" not in content
    assert ".current_execution.plan" not in content
