"""Smoke tests for previously untested state functions.

Covers the top 5 most critical coverage gaps identified in the core module:
  1. state_add_blocker  (state-mutating, disk I/O)
  2. state_resolve_blocker  (state-mutating, disk I/O)
  3. save_state_json + load_state_json  (core persistence pair)
  4. state_patch  (batch state mutation)
  5. state_snapshot  (critical for routing/progress)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gpd.core.errors import StateError
from gpd.core.state import (
    default_state_dict,
    generate_state_markdown,
    load_state_json,
    save_state_json,
    state_add_blocker,
    state_patch,
    state_resolve_blocker,
    state_snapshot,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _bootstrap_project(tmp_path: Path, state_dict: dict | None = None) -> Path:
    """Create a minimal .gpd/ project with STATE.md + state.json.

    Returns the project root (tmp_path).
    """
    planning = tmp_path / ".gpd"
    planning.mkdir()
    (planning / "phases").mkdir()
    (planning / "PROJECT.md").write_text("# Project\nTest.\n")
    (planning / "ROADMAP.md").write_text("# Roadmap\n")

    state = state_dict or default_state_dict()
    pos = state.setdefault("position", {})
    if pos.get("current_phase") is None:
        pos["current_phase"] = "01"
    if pos.get("status") is None:
        pos["status"] = "Executing"
    if pos.get("current_plan") is None:
        pos["current_plan"] = "1"
    if pos.get("total_plans_in_phase") is None:
        pos["total_plans_in_phase"] = 3
    if pos.get("progress_percent") is None:
        pos["progress_percent"] = 33

    # Write both files
    md = generate_state_markdown(state)
    (planning / "STATE.md").write_text(md, encoding="utf-8")
    (planning / "state.json").write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

    return tmp_path


# ---------------------------------------------------------------------------
# 1. state_add_blocker
# ---------------------------------------------------------------------------


class TestStateAddBlocker:
    def test_add_blocker_appends_to_section(self, tmp_path: Path) -> None:
        cwd = _bootstrap_project(tmp_path)
        result = state_add_blocker(cwd, "Need to verify gauge invariance")
        assert result.added is True
        assert result.blocker == "Need to verify gauge invariance"

        # Verify the blocker appears in STATE.md
        md = (cwd / ".gpd" / "STATE.md").read_text()
        assert "Need to verify gauge invariance" in md

    def test_add_blocker_empty_text_fails(self, tmp_path: Path) -> None:
        cwd = _bootstrap_project(tmp_path)
        result = state_add_blocker(cwd, "")
        assert result.added is False
        assert result.error is not None

    def test_add_blocker_missing_state_md(self, tmp_path: Path) -> None:
        planning = tmp_path / ".gpd"
        planning.mkdir()
        result = state_add_blocker(tmp_path, "some blocker")
        assert result.added is False

    def test_add_multiple_blockers(self, tmp_path: Path) -> None:
        cwd = _bootstrap_project(tmp_path)
        state_add_blocker(cwd, "First blocker")
        result = state_add_blocker(cwd, "Second blocker")
        assert result.added is True

        md = (cwd / ".gpd" / "STATE.md").read_text()
        assert "First blocker" in md
        assert "Second blocker" in md


# ---------------------------------------------------------------------------
# 2. state_resolve_blocker
# ---------------------------------------------------------------------------


class TestStateResolveBlocker:
    def test_resolve_exact_match(self, tmp_path: Path) -> None:
        cwd = _bootstrap_project(tmp_path)
        state_add_blocker(cwd, "Need to verify gauge invariance")
        result = state_resolve_blocker(cwd, "Need to verify gauge invariance")
        assert result.resolved is True

        md = (cwd / ".gpd" / "STATE.md").read_text()
        assert "Need to verify gauge invariance" not in md

    def test_resolve_substring_match(self, tmp_path: Path) -> None:
        cwd = _bootstrap_project(tmp_path)
        state_add_blocker(cwd, "Need to verify gauge invariance of loop integral")
        result = state_resolve_blocker(cwd, "gauge invariance")
        assert result.resolved is True

    def test_resolve_empty_text_fails(self, tmp_path: Path) -> None:
        cwd = _bootstrap_project(tmp_path)
        result = state_resolve_blocker(cwd, "")
        assert result.resolved is False

    def test_resolve_short_text_fails(self, tmp_path: Path) -> None:
        cwd = _bootstrap_project(tmp_path)
        result = state_resolve_blocker(cwd, "ab")
        assert result.resolved is False

    def test_resolve_no_match(self, tmp_path: Path) -> None:
        cwd = _bootstrap_project(tmp_path)
        state_add_blocker(cwd, "Something specific")
        result = state_resolve_blocker(cwd, "completely unrelated text")
        assert result.resolved is False

    def test_resolve_missing_state_md(self, tmp_path: Path) -> None:
        planning = tmp_path / ".gpd"
        planning.mkdir()
        result = state_resolve_blocker(tmp_path, "some blocker")
        assert result.resolved is False


# ---------------------------------------------------------------------------
# 3. save_state_json + load_state_json
# ---------------------------------------------------------------------------


class TestSaveLoadStateJson:
    def test_round_trip(self, tmp_path: Path) -> None:
        cwd = _bootstrap_project(tmp_path)
        state = default_state_dict()
        state["position"]["current_phase"] = "05"
        state["position"]["status"] = "Executing"
        state["decisions"] = [{"phase": "3", "summary": "Use dim-reg", "rationale": "Standard"}]

        save_state_json(cwd, state)
        loaded = load_state_json(cwd)

        assert loaded is not None
        assert loaded["position"]["current_phase"] == "05"
        assert loaded["position"]["status"] == "Executing"
        assert len(loaded["decisions"]) == 1

    def test_load_returns_none_when_no_files(self, tmp_path: Path) -> None:
        planning = tmp_path / ".gpd"
        planning.mkdir()
        result = load_state_json(tmp_path)
        assert result is None

    def test_save_creates_state_md(self, tmp_path: Path) -> None:
        cwd = _bootstrap_project(tmp_path)
        state = default_state_dict()
        state["position"]["current_phase"] = "07"
        save_state_json(cwd, state)

        md_path = cwd / ".gpd" / "STATE.md"
        assert md_path.exists()
        content = md_path.read_text()
        assert "7" in content  # phase number appears in STATE.md

    def test_save_overwrites_existing(self, tmp_path: Path) -> None:
        cwd = _bootstrap_project(tmp_path)
        state1 = default_state_dict()
        state1["position"]["status"] = "Planning"
        save_state_json(cwd, state1)

        state2 = default_state_dict()
        state2["position"]["status"] = "Executing"
        save_state_json(cwd, state2)

        loaded = load_state_json(cwd)
        assert loaded is not None
        assert loaded["position"]["status"] == "Executing"

    def test_load_recovers_from_corrupt_json(self, tmp_path: Path) -> None:
        """When state.json is corrupt, load_state_json falls back to STATE.md."""
        cwd = _bootstrap_project(tmp_path)
        # Corrupt state.json
        (cwd / ".gpd" / "state.json").write_text("NOT VALID JSON {{{")
        loaded = load_state_json(cwd)
        # Should still load from STATE.md fallback
        assert loaded is not None
        assert "position" in loaded


# ---------------------------------------------------------------------------
# 4. state_patch
# ---------------------------------------------------------------------------


class TestStatePatch:
    def test_patch_single_field(self, tmp_path: Path) -> None:
        cwd = _bootstrap_project(tmp_path)
        result = state_patch(cwd, {"Status": "Paused"})
        assert "Status" in result.updated

        md = (cwd / ".gpd" / "STATE.md").read_text()
        assert "Paused" in md

    def test_patch_multiple_fields(self, tmp_path: Path) -> None:
        cwd = _bootstrap_project(tmp_path)
        result = state_patch(cwd, {"Status": "Planning", "Current Plan": "2"})
        assert "Status" in result.updated
        assert "Current Plan" in result.updated

    def test_patch_invalid_status_rejected(self, tmp_path: Path) -> None:
        cwd = _bootstrap_project(tmp_path)
        result = state_patch(cwd, {"Status": "InvalidStatusXYZ"})
        assert "Status" in result.failed
        assert "Status" not in result.updated

    def test_patch_invalid_status_transition_rejected(self, tmp_path: Path) -> None:
        cwd = _bootstrap_project(tmp_path)
        result = state_patch(cwd, {"Status": "Complete"})

        assert "Status" in result.failed
        assert "Status" not in result.updated

        md = (cwd / ".gpd" / "STATE.md").read_text()
        assert "**Status:** Executing" in md

        loaded = load_state_json(cwd)
        assert loaded is not None
        assert loaded["position"]["status"] == "Executing"

    def test_patch_nonexistent_field(self, tmp_path: Path) -> None:
        cwd = _bootstrap_project(tmp_path)
        result = state_patch(cwd, {"NonexistentFieldXYZ123": "value"})
        assert "NonexistentFieldXYZ123" in result.failed

    def test_patch_missing_state_md_raises(self, tmp_path: Path) -> None:
        planning = tmp_path / ".gpd"
        planning.mkdir()
        with pytest.raises(StateError):
            state_patch(tmp_path, {"Status": "Paused"})


# ---------------------------------------------------------------------------
# 5. state_snapshot
# ---------------------------------------------------------------------------


class TestStateSnapshot:
    def test_snapshot_from_json(self, tmp_path: Path) -> None:
        cwd = _bootstrap_project(tmp_path)
        snap = state_snapshot(cwd)
        assert snap.current_phase is not None
        assert snap.status is not None

    def test_snapshot_falls_back_to_md(self, tmp_path: Path) -> None:
        cwd = _bootstrap_project(tmp_path)
        # Remove state.json so it falls back to STATE.md
        (cwd / ".gpd" / "state.json").unlink()
        snap = state_snapshot(cwd)
        assert snap.current_phase is not None

    def test_snapshot_missing_both_files(self, tmp_path: Path) -> None:
        planning = tmp_path / ".gpd"
        planning.mkdir()
        snap = state_snapshot(tmp_path)
        assert snap.error is not None

    def test_snapshot_reads_progress(self, tmp_path: Path) -> None:
        state = default_state_dict()
        state["position"]["current_phase"] = "03"
        state["position"]["status"] = "Executing"
        state["position"]["progress_percent"] = 75
        cwd = _bootstrap_project(tmp_path, state_dict=state)
        snap = state_snapshot(cwd)
        assert snap.progress_percent == 75

    def test_snapshot_reads_blockers(self, tmp_path: Path) -> None:
        state = default_state_dict()
        state["position"]["current_phase"] = "02"
        state["position"]["status"] = "Executing"
        state["blockers"] = ["IR divergence"]
        cwd = _bootstrap_project(tmp_path, state_dict=state)
        snap = state_snapshot(cwd)
        assert snap.blockers is not None
        assert len(snap.blockers) == 1
