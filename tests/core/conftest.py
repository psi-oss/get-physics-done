"""Shared test fixtures for gpd/core tests.

Provides reusable project scaffolding so individual test modules don't
duplicate .planning/ directory setup.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture()
def planning_dir(tmp_path: Path) -> Path:
    """Create a mock .planning/ directory with required structure.

    Returns the project root (tmp_path), not .planning/ itself.
    The layout matches what ProjectLayout expects:
      .planning/
        ROADMAP.md
        STATE.md
        state.json
        PROJECT.md
        config.json
        phases/
    """
    planning = tmp_path / ".planning"
    planning.mkdir()

    # Required files
    (planning / "ROADMAP.md").write_text(
        "# Roadmap\n\n## Phase 1: Setup\nInitial setup.\n\n## Phase 2: Core\nCore work.\n"
    )
    (planning / "STATE.md").write_text("# State\n\n## Current Phase\nPhase 01\n\n## Status\nIn progress\n")
    (planning / "state.json").write_text(
        json.dumps(
            {
                "position": {"current_phase": "01", "milestone": "M1"},
                "convention_lock": {},
            },
            indent=2,
        )
    )
    (planning / "PROJECT.md").write_text("# Project\n\nTest project.\n")

    # Optional files
    (planning / "config.json").write_text(json.dumps({"model_profile": "balanced"}, indent=2))

    # Required directories
    (planning / "phases").mkdir()

    return tmp_path


@pytest.fixture()
def sample_state() -> dict[str, object]:
    """Return a minimal valid state dict matching state.json schema."""
    return {
        "position": {
            "current_phase": "01",
            "milestone": "M1",
            "status": "in_progress",
        },
        "convention_lock": {
            "metric_signature": "(-, +, +, +)",
            "natural_units": "c = hbar = 1",
        },
        "history": [],
    }


@pytest.fixture()
def sample_phase_dir(planning_dir: Path) -> Path:
    """Create a phase directory with PLAN.md and SUMMARY.md files.

    Returns the phase directory path.
    """
    phase = planning_dir / ".planning" / "phases" / "01-setup"
    phase.mkdir(parents=True, exist_ok=True)

    (phase / "01-setup-01-PLAN.md").write_text("---\nwave: 1\ngoal: Initial setup\n---\n\n# Plan\n\nSetup steps.\n")
    (phase / "01-setup-01-SUMMARY.md").write_text(
        "# Summary\n\nSetup complete.\n\n```yaml\ngpd_return:\n  status: done\n  tasks_completed: 3\n  tasks_total: 3\n```\n"
    )

    return phase


@pytest.fixture()
def mock_roadmap(planning_dir: Path) -> Path:
    """Create a ROADMAP.md with sample phases and matching phase directories.

    Returns the ROADMAP.md path.
    """
    roadmap = planning_dir / ".planning" / "ROADMAP.md"
    roadmap.write_text(
        "# Roadmap\n\n"
        "## Phase 1: Setup\nProject initialization.\n\n"
        "## Phase 2: Core\nCore implementation.\n\n"
        "## Phase 3: Validation\nResult validation.\n"
    )

    phases_dir = planning_dir / ".planning" / "phases"
    for name in ("1-setup", "2-core", "3-validation"):
        (phases_dir / name).mkdir(parents=True, exist_ok=True)

    return roadmap
