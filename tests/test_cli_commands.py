"""Smoke tests for EVERY `gpd` CLI command.

Ensures every command can be invoked without crashing in a valid project
directory. This catches the class of bug where CLI functions pass a Path to
core functions that expect a domain object (e.g. convention_check receiving
a Path instead of ConventionLock).

Each test invokes the command with minimal valid arguments. If the command
exits 0, the type plumbing is correct. These are NOT functional tests —
they verify the CLI → core function argument wiring works.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from gpd.cli import app

runner = CliRunner()


@pytest.fixture()
def gpd_project(tmp_path: Path) -> Path:
    """Create a minimal GPD project with all files commands might touch."""
    planning = tmp_path / ".gpd"
    planning.mkdir()

    state = {
        "convention_lock": {
            "metric_signature": "(-,+,+,+)",
            "coordinate_system": "Cartesian",
            "custom_conventions": {"my_custom": "value"},
        },
        "phases": [
            {"number": "1", "name": "test-phase", "status": "planned"},
            {"number": "2", "name": "phase-two", "status": "planned"},
        ],
        "current_phase": "1",
        "current_plan": None,
        "decisions": [],
        "blockers": [],
        "sessions": [],
        "metrics": [],
    }
    (planning / "state.json").write_text(json.dumps(state, indent=2))
    (planning / "STATE.md").write_text("# State\n\n## Current Phase\n1\n\n## Decisions\n\n## Blockers\n")
    (planning / "PROJECT.md").write_text("# Test Project\n\n## Core Research Question\nWhat is physics?\n")
    (planning / "REQUIREMENTS.md").write_text("# Requirements\n\n- [ ] **REQ-01**: Do the thing\n")
    (planning / "ROADMAP.md").write_text(
        "# Roadmap\n\n## Phase 1: Test Phase\nGoal: Test\nRequirements: REQ-01\n"
        "\n## Phase 2: Phase Two\nGoal: More tests\nRequirements: REQ-01\n"
    )
    (planning / "CONVENTIONS.md").write_text("# Conventions\n\n- Metric: (-,+,+,+)\n- Coordinates: Cartesian\n")
    (planning / "config.json").write_text(json.dumps({"mode": "yolo", "depth": "standard"}))

    # Phase directories
    p1 = planning / "phases" / "01-test-phase"
    p1.mkdir(parents=True)
    (p1 / "README.md").write_text("# Phase 1: Test Phase\n")
    p2 = planning / "phases" / "02-phase-two"
    p2.mkdir(parents=True)
    (p2 / "README.md").write_text("# Phase 2: Phase Two\n")

    return tmp_path


@pytest.fixture(autouse=True)
def _chdir(gpd_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """All tests run from the project directory."""
    monkeypatch.chdir(gpd_project)


def _invoke(*args: str, expect_ok: bool = True) -> None:
    """Invoke a gpd CLI command and assert it doesn't crash."""
    result = runner.invoke(app, list(args), catch_exceptions=False)
    if expect_ok:
        assert result.exit_code == 0, f"gpd {' '.join(args)} failed:\n{result.output}"


# ═══════════════════════════════════════════════════════════════════════════
# Convention commands — the original bug class
# ═══════════════════════════════════════════════════════════════════════════


class TestConventionCommands:
    def test_check(self) -> None:
        _invoke("convention", "check")

    def test_list(self) -> None:
        _invoke("convention", "list")

    def test_set(self) -> None:
        _invoke("convention", "set", "natural_units", "SI")

    def test_set_force(self) -> None:
        _invoke("convention", "set", "metric_signature", "(+,-,-,-)", "--force")

    def test_check_empty_state(self, gpd_project: Path) -> None:
        (gpd_project / ".gpd" / "state.json").write_text("{}")
        _invoke("convention", "check")

    def test_check_no_state_file(self, gpd_project: Path) -> None:
        (gpd_project / ".gpd" / "state.json").unlink()
        _invoke("convention", "check")

    def test_set_persists(self, gpd_project: Path) -> None:
        _invoke("convention", "set", "fourier_convention", "physics")
        state = json.loads((gpd_project / ".gpd" / "state.json").read_text())
        assert state["convention_lock"]["fourier_convention"] == "physics"


# ═══════════════════════════════════════════════════════════════════════════
# State commands
# ═══════════════════════════════════════════════════════════════════════════


class TestStateCommands:
    def test_load(self) -> None:
        _invoke("state", "load")

    def test_get(self) -> None:
        _invoke("state", "get")

    def test_get_section(self) -> None:
        _invoke("state", "get", "current_phase")

    def test_validate(self) -> None:
        # May exit 1 if issues found, but must not crash
        result = runner.invoke(app, ["state", "validate"], catch_exceptions=False)
        assert result.exit_code in (0, 1)

    def test_snapshot(self) -> None:
        _invoke("state", "snapshot")

    def test_compact(self) -> None:
        _invoke("state", "compact")

    def test_add_decision(self) -> None:
        _invoke("state", "add-decision", "--summary", "Use SI units", "--rationale", "Standard")

    def test_add_blocker(self) -> None:
        _invoke("state", "add-blocker", "--text", "Need reference data")


# ═══════════════════════════════════════════════════════════════════════════
# Init commands
# ═══════════════════════════════════════════════════════════════════════════


class TestInitCommands:
    def test_new_project(self) -> None:
        _invoke("init", "new-project")

    def test_plan_phase(self) -> None:
        _invoke("init", "plan-phase", "1")

    def test_execute_phase(self) -> None:
        _invoke("init", "execute-phase", "1")


# ═══════════════════════════════════════════════════════════════════════════
# Phase commands
# ═══════════════════════════════════════════════════════════════════════════


class TestPhaseCommands:
    def test_list(self) -> None:
        _invoke("phase", "list")

    def test_index(self) -> None:
        _invoke("phase", "index", "1")


# ═══════════════════════════════════════════════════════════════════════════
# Roadmap commands
# ═══════════════════════════════════════════════════════════════════════════


class TestRoadmapCommands:
    def test_get_phase(self) -> None:
        _invoke("roadmap", "get-phase", "1")

    def test_analyze(self) -> None:
        _invoke("roadmap", "analyze")


# ═══════════════════════════════════════════════════════════════════════════
# Progress command
# ═══════════════════════════════════════════════════════════════════════════


class TestProgressCommand:
    def test_progress(self) -> None:
        _invoke("progress")


# ═══════════════════════════════════════════════════════════════════════════
# Verify commands
# ═══════════════════════════════════════════════════════════════════════════


class TestVerifyCommands:
    def test_phase(self) -> None:
        _invoke("verify", "phase", "1")


# ═══════════════════════════════════════════════════════════════════════════
# Result commands
# ═══════════════════════════════════════════════════════════════════════════


class TestResultCommands:
    def test_list(self) -> None:
        _invoke("result", "list")


# ═══════════════════════════════════════════════════════════════════════════
# Approximation commands
# ═══════════════════════════════════════════════════════════════════════════


class TestApproximationCommands:
    def test_list(self) -> None:
        _invoke("approximation", "list")

    def test_add(self) -> None:
        _invoke("approximation", "add", "Born approx", "--validity-range", "x << 1")

    def test_add_minimal(self) -> None:
        """Add with only the name — optional params must not pass None to core."""
        _invoke("approximation", "add", "WKB approx")

    def test_check(self) -> None:
        _invoke("approximation", "check")


# ═══════════════════════════════════════════════════════════════════════════
# Uncertainty commands
# ═══════════════════════════════════════════════════════════════════════════


class TestUncertaintyCommands:
    def test_list(self) -> None:
        _invoke("uncertainty", "list")

    def test_add(self) -> None:
        _invoke("uncertainty", "add", "mass", "--value", "1.0", "--uncertainty", "0.1")

    def test_add_minimal(self) -> None:
        """Add with only the quantity — optional params must not pass None to core."""
        _invoke("uncertainty", "add", "charge")


# ═══════════════════════════════════════════════════════════════════════════
# Question commands
# ═══════════════════════════════════════════════════════════════════════════


class TestQuestionCommands:
    def test_list(self) -> None:
        _invoke("question", "list")

    def test_add(self) -> None:
        _invoke("question", "add", "What is the coupling constant?")

    def test_resolve(self) -> None:
        _invoke("question", "add", "What is the coupling constant?")
        _invoke("question", "resolve", "coupling constant")


# ═══════════════════════════════════════════════════════════════════════════
# Calculation commands
# ═══════════════════════════════════════════════════════════════════════════


class TestCalculationCommands:
    def test_list(self) -> None:
        _invoke("calculation", "list")

    def test_add(self) -> None:
        _invoke("calculation", "add", "Loop integral computation")

    def test_complete(self) -> None:
        _invoke("calculation", "add", "Loop integral computation")
        _invoke("calculation", "complete", "Loop integral")


# ═══════════════════════════════════════════════════════════════════════════
# Utility commands
# ═══════════════════════════════════════════════════════════════════════════


class TestUtilityCommands:
    def test_timestamp(self) -> None:
        _invoke("timestamp")

    def test_slug(self) -> None:
        _invoke("slug", "Hello World Test")
