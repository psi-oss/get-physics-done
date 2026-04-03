"""Focused regression coverage for beginner onboarding docs."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from gpd.adapters.runtime_catalog import get_shared_install_metadata
from gpd.core.onboarding_surfaces import beginner_runtime_surfaces
from tests.doc_surface_contracts import assert_beginner_hub_preflight_contract, assert_beginner_startup_routing_contract

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


def _markdown_section(content: str, heading: str) -> str:
    marker = f"{heading}\n"
    start = content.index(marker)
    next_heading = content.find("\n## ", start + len(marker))
    if next_heading == -1:
        return content[start:]
    return content[start:next_heading]


def _runtime_doc_filename(display_name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", display_name.lower()).strip("-")
    return f"{slug}.md"


@pytest.mark.parametrize("surface", beginner_runtime_surfaces(), ids=lambda surface: surface.runtime_name)
def test_runtime_quickstarts_surface_the_beginner_next_steps(surface) -> None:
    content = _read(f"docs/{_runtime_doc_filename(surface.display_name)}")
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
def test_os_quickstarts_link_runtime_guides_and_post_install_help(doc_name: str) -> None:
    content = _read(f"docs/{doc_name}")

    _assert_fragments(
        content,
        (
            "Confirm success",
            "gpd --help",
            "Not sure which path fits this folder",
            "Want a guided overview",
            "/gpd:start",
            "$gpd-start",
            "/gpd-start",
            "/gpd:tour",
            "$gpd-tour",
            "/gpd-tour",
            "Start a new project",
            "Map an existing folder",
            "Reopen work from your normal terminal",
            "gpd resume --recent",
            "resume-work",
        ),
    )
    assert "Back to the onboarding hub: [GPD Onboarding Hub](./README.md)." in content

    for guide in ("claude-code.md", "codex.md", "gemini-cli.md", "opencode.md"):
        assert f"./{guide}" in content


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
            "./claude-code.md",
            "./codex.md",
            "./gemini-cli.md",
            "./opencode.md",
            f"{_SHARED_INSTALL.bootstrap_command} --claude --local",
            f"{_SHARED_INSTALL.bootstrap_command} --codex --local",
            f"{_SHARED_INSTALL.bootstrap_command} --gemini --local",
            f"{_SHARED_INSTALL.bootstrap_command} --opencode --local",
            "## After the guides",
        ),
    )
    assert_beginner_startup_routing_contract(content)
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


def test_runtime_quickstarts_keep_current_provider_specific_setup_notes() -> None:
    claude = _read("docs/claude-code.md")
    gemini = _read("docs/gemini-cli.md")
    opencode = _read("docs/opencode.md")

    assert "Pro, Max, Teams, Enterprise, or Console account" in claude
    assert "GOOGLE_CLOUD_PROJECT" in gemini
    assert "/connect" in opencode
