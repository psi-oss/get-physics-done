"""Tests for GPD content injection functions in launch.py.

Tests failure-mode behavior of _load_gpd_questioning and _build_tool_catalog_summary
for the bundled questioning reference and MCP catalog fallbacks.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from gpd.mcp.launch import (
    _build_auto_startup,
    _build_tool_catalog_summary,
    _build_work_dir_rules,
    _load_gpd_questioning,
)

# ---------------------------------------------------------------------------
# _load_gpd_questioning tests
# ---------------------------------------------------------------------------


def test_load_gpd_questioning_when_reference_missing(tmp_path: Path):
    """When the bundled questioning reference is missing, fallback content is returned."""
    with patch("gpd.mcp.launch._questioning_reference_path", return_value=tmp_path / "missing.md"):
        result = _load_gpd_questioning()

    assert isinstance(result, str)
    assert "thinking partner" in result.lower()
    assert "Stage 2" in result


def test_load_gpd_questioning_when_file_corrupt(tmp_path: Path):
    """When questioning.md has garbage content, fallback content is returned."""
    corrupt_file = tmp_path / "questioning.md"
    corrupt_file.write_text("This is just plain text with no XML tags at all.\nNothing useful here.\n", encoding="utf-8")

    with patch("gpd.mcp.launch._questioning_reference_path", return_value=corrupt_file):
        result = _load_gpd_questioning()

    assert isinstance(result, str)
    assert "thinking partner" in result.lower()
    assert "Stage 2" in result


def test_load_gpd_questioning_happy_path(tmp_path: Path):
    """When questioning.md exists and is well-formed, real content is returned."""
    questioning = tmp_path / "questioning.md"
    questioning.write_text(
        "<philosophy>\nYou are a thinking partner, not an interviewer.\n</philosophy>\n"
        "<how_to_question>\nAsk one question at a time.\n</how_to_question>\n"
        "<question_types>\n- Scope\n- Physics target\n</question_types>\n"
        "<anti_patterns>\n- Dumping 4+ questions as text\n</anti_patterns>\n",
        encoding="utf-8",
    )

    with patch("gpd.mcp.launch._questioning_reference_path", return_value=questioning):
        result = _load_gpd_questioning()

    assert isinstance(result, str)
    assert "Stage 2" in result
    assert "physical" in result.lower() or "physics" in result.lower()
    assert "thinking partner" in result.lower()


# ---------------------------------------------------------------------------
# _build_tool_catalog_summary tests
# ---------------------------------------------------------------------------


def test_build_tool_catalog_when_import_fails():
    """When ToolCatalog import raises ImportError, fallback message is returned."""
    with (
        patch(
            "gpd.mcp.discovery.catalog.ToolCatalog",
            side_effect=ImportError("mocked import error"),
        ),
        patch("gpd.mcp.launch.get_cached_mcp_count", return_value=42),
    ):
        result = _build_tool_catalog_summary()

    assert isinstance(result, str)
    assert "MCP" in result
    assert "tool" in result.lower()


def test_build_tool_catalog_when_catalog_empty():
    """When ToolCatalog returns empty tools, informative message is returned."""
    mock_catalog = MagicMock()
    mock_catalog.get_all_tools.return_value = {}

    with (
        patch("gpd.mcp.discovery.catalog.ToolCatalog", return_value=mock_catalog),
        patch("gpd.mcp.discovery.sources.load_sources_config", return_value=MagicMock()),
    ):
        result = _build_tool_catalog_summary()

    assert isinstance(result, str)
    assert "No MCP tools" in result or "gpd pipeline discover" in result


def test_build_tool_catalog_when_config_fails():
    """When load_sources_config raises OSError, fallback message is returned."""
    with (
        patch(
            "gpd.mcp.discovery.sources.load_sources_config",
            side_effect=OSError("Config file not found"),
        ),
        patch("gpd.mcp.launch.get_cached_mcp_count", return_value=10),
    ):
        result = _build_tool_catalog_summary()

    assert isinstance(result, str)
    assert "MCP" in result
    assert "tool" in result.lower()


def test_auto_startup_avoids_repair_workflows():
    """Startup instructions should defer to discovery instead of hidden repair flows."""
    result = _build_auto_startup()
    assert "gpd pipeline discover" in result
    assert "do not run background repair" in result.lower()
    assert "do not attempt autonomous redeployment" in result.lower()


def test_work_dir_rules_match_runtime_behavior():
    """WORK_DIR guidance should use a generic writable directory, not session JSON storage."""
    result = _build_work_dir_rules()
    assert "any writable work_dir" in result.lower()
    assert ".gpd-mcp-work" in result
    assert "tools.json" in result
