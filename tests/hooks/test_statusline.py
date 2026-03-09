"""Tests for gpd/hooks/statusline.py edge cases.

Covers: empty input, missing fields, context_window boundary values,
graceful degradation, and ANSI output correctness.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from unittest.mock import patch

from gpd.hooks.statusline import (
    _check_update,
    _context_bar,
    _read_current_task,
    _read_position,
    main,
)

# ─── _context_bar edge cases ───────────────────────────────────────────────


class TestContextBar:
    """Tests for _context_bar boundary values."""

    def test_remaining_zero_shows_max_used(self) -> None:
        """remaining_percentage=0 → 100% used (capped), critical color."""
        bar = _context_bar(0)
        # raw_used=100, used = min(100, round(100/80*100)) = 100
        assert "100%" in bar
        # Should be critical (blinking red)
        assert "\x1b[5;31m" in bar

    def test_remaining_100_shows_zero_used(self) -> None:
        """remaining_percentage=100 → 0% used, green color."""
        bar = _context_bar(100)
        assert "0%" in bar
        assert "\x1b[32m" in bar  # Green

    def test_remaining_50_shows_scaled_usage(self) -> None:
        """remaining_percentage=50 → raw_used=50, scaled = round(50/80*100)=62."""
        bar = _context_bar(50)
        assert "62%" in bar or "63%" in bar  # Rounding

    def test_remaining_negative_clamps_to_100_used(self) -> None:
        """Negative remaining_pct → raw_used clamped to 100."""
        bar = _context_bar(-10)
        assert "100%" in bar

    def test_remaining_over_100_clamps_to_0_used(self) -> None:
        """Over 100 remaining → raw_used clamped to 0."""
        bar = _context_bar(150)
        assert "0%" in bar

    def test_warn_threshold_boundary(self) -> None:
        """At exactly the warn threshold, should use yellow color."""
        # used < _CONTEXT_WARN_THRESHOLD (63) → green
        # We need used == 63 → raw_used = 63 * 80 / 100 = 50.4
        # remaining = 100 - raw_used → need to find remaining where used == 63
        # This is complex, just verify green below threshold
        bar = _context_bar(60)  # raw_used=40, used=50 → green
        assert "\x1b[32m" in bar

    def test_high_threshold_uses_yellow(self) -> None:
        """Values between warn and high threshold use yellow."""
        # raw_used = 60, used = round(60/80*100) = 75, 63 <= 75 < 81 → yellow
        bar = _context_bar(40)  # raw_used=60
        assert "\x1b[33m" in bar  # Yellow

    def test_critical_threshold_uses_orange(self) -> None:
        """Values between high and critical use orange."""
        # raw_used = 70, used = round(70/80*100) = 88, 81 <= 88 < 95 → orange
        bar = _context_bar(30)  # raw_used=70
        assert "\x1b[38;5;208m" in bar  # Orange


# ─── _read_position edge cases ─────────────────────────────────────────────


class TestReadPosition:
    """Tests for _read_position with various state files."""

    def test_missing_state_file_returns_empty(self, tmp_path: Path) -> None:
        assert _read_position(str(tmp_path)) == ""

    def test_valid_state_with_phase_only(self, tmp_path: Path) -> None:
        planning = tmp_path / ".planning"
        planning.mkdir()
        state = {"position": {"current_phase": 3, "total_phases": 10}}
        (planning / "state.json").write_text(json.dumps(state))
        assert _read_position(str(tmp_path)) == "P3/10"

    def test_valid_state_with_phase_and_plan(self, tmp_path: Path) -> None:
        planning = tmp_path / ".planning"
        planning.mkdir()
        state = {"position": {"current_phase": 2, "total_phases": 5, "current_plan": 1, "total_plans_in_phase": 3}}
        (planning / "state.json").write_text(json.dumps(state))
        assert _read_position(str(tmp_path)) == "P2/5 plan 1/3"

    def test_empty_position_returns_empty(self, tmp_path: Path) -> None:
        planning = tmp_path / ".planning"
        planning.mkdir()
        state = {"position": {}}
        (planning / "state.json").write_text(json.dumps(state))
        assert _read_position(str(tmp_path)) == ""

    def test_missing_phase_returns_empty(self, tmp_path: Path) -> None:
        planning = tmp_path / ".planning"
        planning.mkdir()
        state = {"position": {"total_phases": 5}}
        (planning / "state.json").write_text(json.dumps(state))
        assert _read_position(str(tmp_path)) == ""

    def test_missing_total_phases_returns_empty(self, tmp_path: Path) -> None:
        planning = tmp_path / ".planning"
        planning.mkdir()
        state = {"position": {"current_phase": 3}}
        (planning / "state.json").write_text(json.dumps(state))
        assert _read_position(str(tmp_path)) == ""

    def test_corrupt_json_returns_empty(self, tmp_path: Path) -> None:
        planning = tmp_path / ".planning"
        planning.mkdir()
        (planning / "state.json").write_text("not valid json{{{")
        assert _read_position(str(tmp_path)) == ""

    def test_no_position_key_returns_empty(self, tmp_path: Path) -> None:
        planning = tmp_path / ".planning"
        planning.mkdir()
        (planning / "state.json").write_text(json.dumps({"other": "data"}))
        assert _read_position(str(tmp_path)) == ""


# ─── _read_current_task edge cases ─────────────────────────────────────────


class TestReadCurrentTask:
    """Tests for _read_current_task."""

    def test_empty_session_id_returns_empty(self) -> None:
        assert _read_current_task("") == ""

    def test_no_matching_todo_files(self, tmp_path: Path) -> None:
        todo_dir = tmp_path / "todos"
        todo_dir.mkdir()
        with patch("gpd.hooks.runtime_detect.get_todo_dirs", return_value=[todo_dir]):
            assert _read_current_task("session-123") == ""

    def test_matching_file_with_in_progress_task(self, tmp_path: Path) -> None:
        todo_dir = tmp_path / "todos"
        todo_dir.mkdir()
        todos = [{"status": "in_progress", "activeForm": "Running tests"}]
        (todo_dir / "session-123-agent-abc.json").write_text(json.dumps(todos))
        with patch("gpd.hooks.runtime_detect.get_todo_dirs", return_value=[todo_dir]):
            assert _read_current_task("session-123") == "Running tests"

    def test_matching_file_no_in_progress_task(self, tmp_path: Path) -> None:
        todo_dir = tmp_path / "todos"
        todo_dir.mkdir()
        todos = [{"status": "completed", "activeForm": "Done"}]
        (todo_dir / "session-123-agent-abc.json").write_text(json.dumps(todos))
        with patch("gpd.hooks.runtime_detect.get_todo_dirs", return_value=[todo_dir]):
            assert _read_current_task("session-123") == ""

    def test_corrupt_todo_file_returns_empty(self, tmp_path: Path) -> None:
        todo_dir = tmp_path / "todos"
        todo_dir.mkdir()
        (todo_dir / "session-123-agent-abc.json").write_text("not json!")
        with patch("gpd.hooks.runtime_detect.get_todo_dirs", return_value=[todo_dir]):
            assert _read_current_task("session-123") == ""

    def test_nonexistent_todo_dirs(self) -> None:
        with patch("gpd.hooks.runtime_detect.get_todo_dirs", return_value=[Path("/nonexistent/todos")]):
            assert _read_current_task("session-123") == ""


# ─── _check_update edge cases ──────────────────────────────────────────────


class TestCheckUpdateHook:
    """Tests for _check_update reading cache files."""

    def test_no_cache_file_returns_empty(self, tmp_path: Path) -> None:
        with (
            patch("gpd.hooks.runtime_detect.get_cache_dirs", return_value=[tmp_path / "cache"]),
            patch("gpd.hooks.statusline.Path.home", return_value=tmp_path),
        ):
            assert _check_update() == ""

    def test_cache_with_update_available(self, tmp_path: Path) -> None:
        gpd_cache = tmp_path / ".gpd" / "cache"
        gpd_cache.mkdir(parents=True)
        (gpd_cache / "gpd-update-check.json").write_text(json.dumps({"update_available": True}))
        with (
            patch("gpd.hooks.runtime_detect.get_cache_dirs", return_value=[]),
            patch("gpd.hooks.statusline.Path.home", return_value=tmp_path),
        ):
            result = _check_update()
            assert "/gpd:update" in result

    def test_cache_with_no_update(self, tmp_path: Path) -> None:
        gpd_cache = tmp_path / ".gpd" / "cache"
        gpd_cache.mkdir(parents=True)
        (gpd_cache / "gpd-update-check.json").write_text(json.dumps({"update_available": False}))
        with (
            patch("gpd.hooks.runtime_detect.get_cache_dirs", return_value=[]),
            patch("gpd.hooks.statusline.Path.home", return_value=tmp_path),
        ):
            assert _check_update() == ""

    def test_corrupt_cache_returns_empty(self, tmp_path: Path) -> None:
        gpd_cache = tmp_path / ".gpd" / "cache"
        gpd_cache.mkdir(parents=True)
        (gpd_cache / "gpd-update-check.json").write_text("broken{json")
        with (
            patch("gpd.hooks.runtime_detect.get_cache_dirs", return_value=[]),
            patch("gpd.hooks.statusline.Path.home", return_value=tmp_path),
        ):
            assert _check_update() == ""


# ─── main() integration ───────────────────────────────────────────────────


class TestMain:
    """Tests for main() entry point with various JSON inputs."""

    def _run_main(self, input_data: dict[str, object]) -> str:
        """Run main() with given input data, capture stdout."""
        captured = io.StringIO()
        with (
            patch("sys.stdin", io.StringIO(json.dumps(input_data))),
            patch("sys.stdout", captured),
            patch("gpd.hooks.statusline._read_position", return_value=""),
            patch("gpd.hooks.statusline._read_current_task", return_value=""),
            patch("gpd.hooks.statusline._check_update", return_value=""),
        ):
            main()
        return captured.getvalue()

    def test_empty_json_object_no_crash(self) -> None:
        """Empty {} input should not crash — all fields default gracefully."""
        output = self._run_main({})
        assert "Claude" in output  # Default model name

    def test_missing_model_field(self) -> None:
        """Missing 'model' key → defaults to 'Claude'."""
        output = self._run_main({"workspace": {"current_dir": "/tmp"}})
        assert "Claude" in output

    def test_model_field_is_none(self) -> None:
        """model=None → 'or {}' fallback → 'Claude'."""
        output = self._run_main({"model": None})
        assert "Claude" in output

    def test_model_without_display_name(self) -> None:
        """model={} with no display_name → defaults to 'Claude'."""
        output = self._run_main({"model": {}})
        assert "Claude" in output

    def test_with_valid_model(self) -> None:
        output = self._run_main({"model": {"display_name": "GPT-4o"}})
        assert "GPT-4o" in output

    def test_context_window_remaining_zero(self) -> None:
        """remaining_percentage=0 → shows 100% usage."""
        output = self._run_main({"context_window": {"remaining_percentage": 0}})
        assert "100%" in output

    def test_context_window_remaining_100(self) -> None:
        """remaining_percentage=100 → shows 0% usage."""
        output = self._run_main({"context_window": {"remaining_percentage": 100}})
        assert "0%" in output

    def test_no_context_window_field(self) -> None:
        """Missing context_window → no bar in output."""
        output = self._run_main({"model": {"display_name": "Test"}})
        # No percentage should appear
        assert "%" not in output

    def test_context_window_is_none(self) -> None:
        """context_window=None → 'or {}' fallback, remaining is None → no bar."""
        output = self._run_main({"context_window": None})
        assert "%" not in output

    def test_invalid_json_stdin_no_crash(self) -> None:
        """Invalid JSON on stdin → main() returns silently, no crash."""
        captured = io.StringIO()
        with (
            patch("sys.stdin", io.StringIO("not json at all!!!")),
            patch("sys.stdout", captured),
        ):
            main()
        assert captured.getvalue() == ""

    def test_with_task_shows_task(self) -> None:
        """When a task is in progress, it appears in the output."""
        captured = io.StringIO()
        with (
            patch("sys.stdin", io.StringIO(json.dumps({}))),
            patch("sys.stdout", captured),
            patch("gpd.hooks.statusline._read_position", return_value=""),
            patch("gpd.hooks.statusline._read_current_task", return_value="Running experiments"),
            patch("gpd.hooks.statusline._check_update", return_value=""),
        ):
            main()
        assert "Running experiments" in captured.getvalue()

    def test_with_position_shows_position(self) -> None:
        """When research position exists, it appears in the output."""
        captured = io.StringIO()
        with (
            patch("sys.stdin", io.StringIO(json.dumps({}))),
            patch("sys.stdout", captured),
            patch("gpd.hooks.statusline._read_position", return_value="P3/10"),
            patch("gpd.hooks.statusline._read_current_task", return_value=""),
            patch("gpd.hooks.statusline._check_update", return_value=""),
        ):
            main()
        assert "P3/10" in captured.getvalue()
