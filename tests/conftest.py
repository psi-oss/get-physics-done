"""Shared test fixtures for gpd-plus tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture()
def tmp_gpdplus_dir(tmp_path: Path) -> Path:
    """Create a temporary .gpdplus/ directory structure for isolated tests."""
    gpdplus = tmp_path / ".gpdplus"
    (gpdplus / "sessions").mkdir(parents=True)
    (gpdplus / "cache").mkdir(parents=True)
    return gpdplus


@pytest.fixture()
def mock_gpd_install(tmp_path: Path) -> Path:
    """Create a fake GPD installation directory with minimal structure.

    Layout mirrors a real GPD install under ~/.claude/:
      get-physics-done/package.json
      commands/gpd/example-cmd.md
      agents/gpd-researcher.md
    """
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()

    # Core GPD directory with package.json
    core_dir = claude_dir / "get-physics-done"
    core_dir.mkdir()
    (core_dir / "package.json").write_text(json.dumps({"name": "get-physics-done-cc", "version": "0.1.0"}))

    # Workflows directory
    workflows_dir = core_dir / "workflows"
    workflows_dir.mkdir()
    (workflows_dir / "research.md").write_text("# Research Workflow\nSteps for research.")

    # Commands directory
    commands_dir = claude_dir / "commands" / "gpd"
    commands_dir.mkdir(parents=True)
    (commands_dir / "example-cmd.md").write_text("---\nname: example-cmd\n---\nAn example command.")
    (commands_dir / "plan.md").write_text("---\nname: plan\n---\nPlanning command.")

    # Agents directory
    agents_dir = claude_dir / "agents"
    agents_dir.mkdir()
    (agents_dir / "gpd-researcher.md").write_text("# GPD Researcher Agent")
    (agents_dir / "gpd-analyst.md").write_text("# GPD Analyst Agent")
    # Non-GPD agent (should NOT be discovered)
    (agents_dir / "custom-agent.md").write_text("# Custom Agent")

    return claude_dir
