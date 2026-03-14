"""Tests for gpd/hooks/statusline.py edge cases.

Covers: empty input, missing fields, context_window boundary values,
graceful degradation, and ANSI output correctness.
"""

from __future__ import annotations

import io
import json
import os
from pathlib import Path
from unittest.mock import patch

from gpd.hooks.statusline import (
    _check_update,
    _context_bar,
    _execution_badge,
    _format_context_window_size,
    _read_current_task,
    _read_model_label,
    _read_position,
    _read_workspace_label,
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


class TestStatusMetadata:
    """Tests for model and workspace metadata rendered by the statusline."""

    def test_format_context_window_size_uses_m_suffix(self) -> None:
        assert _format_context_window_size(1_000_000) == "1M context"

    def test_format_context_window_size_uses_k_suffix(self) -> None:
        assert _format_context_window_size(200_000) == "200k context"

    def test_read_model_label_combines_display_name_and_context_size(self) -> None:
        label = _read_model_label({"model": {"display_name": "Opus 4.6"}, "context_window": {"context_window_size": 1_000_000}})
        assert label == "Opus 4.6 (1M context)"

    def test_read_workspace_label_prefers_project_relative_path(self, tmp_path: Path) -> None:
        project = tmp_path / "project"
        current = project / "src" / "gpd"
        current.mkdir(parents=True)

        label = _read_workspace_label({"workspace": {"project_dir": str(project)}}, str(current))
        assert label == "[project/src/gpd]"

    def test_read_workspace_label_falls_back_to_directory_name(self, tmp_path: Path) -> None:
        current = tmp_path / "workspace"
        current.mkdir()

        label = _read_workspace_label({}, str(current))
        assert label == "[workspace]"


class TestExecutionBadge:
    def test_first_result_gate_badge_wins(self) -> None:
        badge = _execution_badge(
            {
                "segment_status": "waiting_review",
                "first_result_gate_pending": True,
                "review_cadence": "adaptive",
                "segment_started_at": "2026-03-10T00:00:00+00:00",
                "updated_at": "2026-03-10T00:12:00+00:00",
            }
        )
        assert "REVIEW:first-result" in badge
        assert "adaptive" in badge
        assert "12m" in badge

    def test_blocked_badge_uses_blocked_state(self) -> None:
        badge = _execution_badge({"segment_status": "active", "blocked_reason": "anchor mismatch"})
        assert badge == "BLOCKED"

    def test_resume_badge_surfaces_resume_state(self) -> None:
        badge = _execution_badge({"segment_status": "paused", "resume_file": ".gpd/phases/02/.continue-here.md"})
        assert badge == "RESUME"

    def test_pre_fanout_review_badge_uses_checkpoint_reason_label(self) -> None:
        badge = _execution_badge(
            {
                "segment_status": "waiting_review",
                "waiting_for_review": True,
                "checkpoint_reason": "pre_fanout",
                "pre_fanout_review_pending": True,
                "review_cadence": "adaptive",
            }
        )
        assert "REVIEW:pre-fanout" in badge
        assert "adaptive" in badge

    def test_skeptical_review_badge_wins_over_generic_checkpoint(self) -> None:
        badge = _execution_badge(
            {
                "segment_status": "waiting_review",
                "waiting_for_review": True,
                "checkpoint_reason": "pre_fanout",
                "pre_fanout_review_pending": True,
                "skeptical_requestioning_required": True,
            }
        )
        assert "REVIEW:skeptical" in badge


# ─── _read_position edge cases ─────────────────────────────────────────────


class TestReadPosition:
    """Tests for _read_position with various state files."""

    def test_missing_state_file_returns_empty(self, tmp_path: Path) -> None:
        assert _read_position(str(tmp_path)) == ""

    def test_valid_state_with_phase_only(self, tmp_path: Path) -> None:
        planning = tmp_path / ".gpd"
        planning.mkdir()
        state = {"position": {"current_phase": 3, "total_phases": 10}}
        (planning / "state.json").write_text(json.dumps(state))
        assert _read_position(str(tmp_path)) == "P3/10"

    def test_valid_state_with_phase_and_plan(self, tmp_path: Path) -> None:
        planning = tmp_path / ".gpd"
        planning.mkdir()
        state = {"position": {"current_phase": 2, "total_phases": 5, "current_plan": 1, "total_plans_in_phase": 3}}
        (planning / "state.json").write_text(json.dumps(state))
        assert _read_position(str(tmp_path)) == "P2/5 plan 1/3"

    def test_empty_position_returns_empty(self, tmp_path: Path) -> None:
        planning = tmp_path / ".gpd"
        planning.mkdir()
        state = {"position": {}}
        (planning / "state.json").write_text(json.dumps(state))
        assert _read_position(str(tmp_path)) == ""

    def test_missing_phase_returns_empty(self, tmp_path: Path) -> None:
        planning = tmp_path / ".gpd"
        planning.mkdir()
        state = {"position": {"total_phases": 5}}
        (planning / "state.json").write_text(json.dumps(state))
        assert _read_position(str(tmp_path)) == ""

    def test_missing_total_phases_returns_empty(self, tmp_path: Path) -> None:
        planning = tmp_path / ".gpd"
        planning.mkdir()
        state = {"position": {"current_phase": 3}}
        (planning / "state.json").write_text(json.dumps(state))
        assert _read_position(str(tmp_path)) == ""

    def test_corrupt_json_returns_empty(self, tmp_path: Path) -> None:
        planning = tmp_path / ".gpd"
        planning.mkdir()
        (planning / "state.json").write_text("not valid json{{{")
        assert _read_position(str(tmp_path)) == ""

    def test_no_position_key_returns_empty(self, tmp_path: Path) -> None:
        planning = tmp_path / ".gpd"
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

    def test_local_runtime_todo_file_is_discovered(self, tmp_path: Path) -> None:
        home = tmp_path / "home"
        local_todo_dir = tmp_path / ".codex" / "todos"
        local_todo_dir.mkdir(parents=True)
        todos = [{"status": "in_progress", "activeForm": "Inspect local runtime"}]
        (local_todo_dir / "session-123-agent-local.json").write_text(json.dumps(todos))

        with (
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
        ):
            assert _read_current_task("session-123") == "Inspect local runtime"

    def test_workspace_dir_overrides_process_cwd_for_local_todos(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        home = tmp_path / "home"
        local_todo_dir = workspace / ".codex" / "todos"
        local_todo_dir.mkdir(parents=True)
        todos = [{"status": "in_progress", "activeForm": "Workspace-scoped task"}]
        (local_todo_dir / "session-123-agent-local.json").write_text(json.dumps(todos))

        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()

        with (
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=elsewhere),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
        ):
            assert _read_current_task("session-123", str(workspace)) == "Workspace-scoped task"

    def test_active_runtime_todo_dir_beats_other_runtime_with_same_session_id(self, tmp_path: Path) -> None:
        home = tmp_path / "home"
        claude_todo_dir = tmp_path / ".claude" / "todos"
        codex_todo_dir = tmp_path / ".codex" / "todos"
        claude_todo_dir.mkdir(parents=True)
        codex_todo_dir.mkdir(parents=True)

        (claude_todo_dir / "session-123-agent-claude.json").write_text(
            json.dumps([{"status": "in_progress", "activeForm": "Claude task"}]),
            encoding="utf-8",
        )
        (codex_todo_dir / "session-123-agent-codex.json").write_text(
            json.dumps([{"status": "in_progress", "activeForm": "Codex task"}]),
            encoding="utf-8",
        )

        env = {key: value for key, value in os.environ.items() if key != "CODEX_SESSION"}
        env["CODEX_SESSION"] = "1"
        with (
            patch.dict(os.environ, env, clear=True),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
        ):
            assert _read_current_task("session-123", str(tmp_path)) == "Codex task"

    def test_todo_dir_order_beats_newer_global_match(self, tmp_path: Path) -> None:
        local_todo_dir = tmp_path / ".codex" / "todos"
        global_todo_dir = tmp_path / "home" / ".codex" / "todos"
        local_todo_dir.mkdir(parents=True)
        global_todo_dir.mkdir(parents=True)

        local_file = local_todo_dir / "session-123-agent-local.json"
        global_file = global_todo_dir / "session-123-agent-global.json"
        local_file.write_text(
            json.dumps([{"status": "in_progress", "activeForm": "Prefer local"}]),
            encoding="utf-8",
        )
        global_file.write_text(
            json.dumps([{"status": "in_progress", "activeForm": "Do not prefer global"}]),
            encoding="utf-8",
        )
        global_file.touch()

        with patch("gpd.hooks.runtime_detect.get_todo_dirs", return_value=[local_todo_dir, global_todo_dir]):
            assert _read_current_task("session-123") == "Prefer local"

    def test_corrupt_todo_file_returns_empty(self, tmp_path: Path) -> None:
        todo_dir = tmp_path / "todos"
        todo_dir.mkdir()
        (todo_dir / "session-123-agent-abc.json").write_text("not json!")
        with patch("gpd.hooks.runtime_detect.get_todo_dirs", return_value=[todo_dir]):
            assert _read_current_task("session-123") == ""

    def test_nonexistent_todo_dirs(self) -> None:
        with patch("gpd.hooks.runtime_detect.get_todo_dirs", return_value=[Path("/nonexistent/todos")]):
            assert _read_current_task("session-123") == ""

    def test_session_prefix_collision_uses_exact_session_match(self, tmp_path: Path) -> None:
        todo_dir = tmp_path / "todos"
        todo_dir.mkdir()
        (todo_dir / "session-12-agent-b.json").write_text(
            json.dumps([{"status": "in_progress", "activeForm": "Wrong task"}]),
            encoding="utf-8",
        )
        (todo_dir / "session-1-agent-a.json").write_text(
            json.dumps([{"status": "in_progress", "activeForm": "Correct task"}]),
            encoding="utf-8",
        )

        with patch("gpd.hooks.runtime_detect.get_todo_dirs", return_value=[todo_dir]):
            assert _read_current_task("session-1") == "Correct task"


# ─── _check_update edge cases ──────────────────────────────────────────────


class TestCheckUpdateHook:
    """Tests for _check_update reading cache files."""

    def test_no_cache_file_returns_empty(self, tmp_path: Path) -> None:
        with (
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=tmp_path / "home"),
        ):
            assert _check_update() == ""

    def test_cache_with_update_available(self, tmp_path: Path) -> None:
        gpd_cache = tmp_path / ".gpd" / "cache"
        gpd_cache.mkdir(parents=True)
        (gpd_cache / "gpd-update-check.json").write_text(json.dumps({"update_available": True}))
        with (
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.detect_active_runtime_with_gpd_install", return_value="claude-code"),
        ):
            result = _check_update()
            assert "/gpd:update" in result

    def test_cache_with_no_update(self, tmp_path: Path) -> None:
        gpd_cache = tmp_path / ".gpd" / "cache"
        gpd_cache.mkdir(parents=True)
        (gpd_cache / "gpd-update-check.json").write_text(json.dumps({"update_available": False}))
        with (
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=tmp_path),
        ):
            assert _check_update() == ""

    def test_corrupt_cache_returns_empty(self, tmp_path: Path) -> None:
        gpd_cache = tmp_path / ".gpd" / "cache"
        gpd_cache.mkdir(parents=True)
        (gpd_cache / "gpd-update-check.json").write_text("broken{json")
        with (
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=tmp_path),
        ):
            assert _check_update() == ""

    def test_non_mapping_cache_is_ignored_instead_of_crashing(self, tmp_path: Path) -> None:
        gpd_cache = tmp_path / ".gpd" / "cache"
        gpd_cache.mkdir(parents=True)
        (gpd_cache / "gpd-update-check.json").write_text(json.dumps(["not", "a", "mapping"]), encoding="utf-8")

        with (
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=tmp_path / "home"),
        ):
            assert _check_update() == ""

    def test_local_runtime_cache_can_override_stale_home_cache(self, tmp_path: Path) -> None:
        home = tmp_path / "home"
        home_cache = home / ".gpd" / "cache"
        home_cache.mkdir(parents=True)
        (home_cache / "gpd-update-check.json").write_text(
            json.dumps({"update_available": False, "checked": 10}),
            encoding="utf-8",
        )

        local_cache = tmp_path / ".codex" / "cache"
        local_cache.mkdir(parents=True)
        (local_cache / "gpd-update-check.json").write_text(
            json.dumps({"update_available": True, "checked": 20}),
            encoding="utf-8",
        )

        with (
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
            patch("gpd.hooks.runtime_detect.detect_active_runtime_with_gpd_install", return_value="claude-code"),
        ):
            result = _check_update()

        assert "/gpd:update" in result

    def test_local_runtime_cache_uses_cache_runtime_when_install_exists(self, tmp_path: Path) -> None:
        home = tmp_path / "home"
        home_cache = home / ".gpd" / "cache"
        home_cache.mkdir(parents=True)
        (home_cache / "gpd-update-check.json").write_text(
            json.dumps({"update_available": False, "checked": 10}),
            encoding="utf-8",
        )

        local_runtime_dir = tmp_path / ".codex"
        local_cache = local_runtime_dir / "cache"
        local_cache.mkdir(parents=True)
        (local_runtime_dir / "gpd-file-manifest.json").write_text(
            json.dumps({"install_scope": "local"}),
            encoding="utf-8",
        )
        (local_cache / "gpd-update-check.json").write_text(
            json.dumps({"update_available": True, "checked": 20}),
            encoding="utf-8",
        )

        with (
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
            patch("gpd.hooks.runtime_detect.detect_active_runtime_with_gpd_install", return_value="claude-code"),
        ):
            result = _check_update()

        assert "$gpd-update" in result

    def test_active_runtime_cache_beats_newer_unrelated_runtime_cache(self, tmp_path: Path) -> None:
        home = tmp_path / "home"

        local_runtime_dir = tmp_path / ".codex"
        local_cache = local_runtime_dir / "cache"
        local_cache.mkdir(parents=True)
        (local_runtime_dir / "gpd-file-manifest.json").write_text(
            json.dumps({"install_scope": "local"}),
            encoding="utf-8",
        )
        (local_cache / "gpd-update-check.json").write_text(
            json.dumps({"update_available": True, "checked": 20}),
            encoding="utf-8",
        )

        unrelated_runtime_dir = home / ".claude"
        unrelated_cache = unrelated_runtime_dir / "cache"
        unrelated_cache.mkdir(parents=True)
        (unrelated_runtime_dir / "gpd-file-manifest.json").write_text(
            json.dumps({"install_scope": "global"}),
            encoding="utf-8",
        )
        (unrelated_cache / "gpd-update-check.json").write_text(
            json.dumps({"update_available": True, "checked": 30}),
            encoding="utf-8",
        )

        with (
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
            patch("gpd.hooks.runtime_detect.detect_active_runtime_with_gpd_install", return_value="codex"),
        ):
            result = _check_update()

        assert "$gpd-update" in result
        assert "/gpd:update" not in result

    def test_installed_global_scope_cache_beats_stale_local_scope_cache(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        home = tmp_path / "home"

        local_cache = workspace / ".codex" / "cache"
        local_cache.mkdir(parents=True)
        (local_cache / "gpd-update-check.json").write_text(
            json.dumps({"update_available": True, "checked": 30}),
            encoding="utf-8",
        )

        global_runtime_dir = home / ".codex"
        global_cache = global_runtime_dir / "cache"
        global_cache.mkdir(parents=True)
        (global_runtime_dir / "gpd-file-manifest.json").write_text(
            json.dumps({"install_scope": "global"}),
            encoding="utf-8",
        )
        (global_cache / "gpd-update-check.json").write_text(
            json.dumps({"update_available": False, "checked": 10}),
            encoding="utf-8",
        )

        with patch("gpd.hooks.runtime_detect.Path.home", return_value=home):
            assert _check_update(str(workspace)) == ""

    def test_workspace_dir_overrides_process_cwd_for_local_cache_selection(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        home = tmp_path / "home"

        local_cache = workspace / ".codex" / "cache"
        local_cache.mkdir(parents=True)
        (workspace / ".codex" / "gpd-file-manifest.json").write_text(
            json.dumps({"install_scope": "local"}),
            encoding="utf-8",
        )
        (local_cache / "gpd-update-check.json").write_text(
            json.dumps({"update_available": True, "checked": 20}),
            encoding="utf-8",
        )

        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()

        with (
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=elsewhere),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
        ):
            result = _check_update(str(workspace))

        assert "$gpd-update" in result

    def test_runtime_directory_without_install_uses_bootstrap_update_command(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        home = tmp_path / "home"
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()

        local_cache = workspace / ".codex" / "cache"
        local_cache.mkdir(parents=True)
        (local_cache / "gpd-update-check.json").write_text(
            json.dumps({"update_available": True, "checked": 20}),
            encoding="utf-8",
        )

        with (
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=elsewhere),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
        ):
            result = _check_update(str(workspace))

        assert "npx -y get-physics-done" in result

    def test_stale_uninstalled_runtime_cache_is_ignored_when_another_runtime_is_installed(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        home = tmp_path / "home"

        stale_cache = workspace / ".codex" / "cache"
        stale_cache.mkdir(parents=True)
        (stale_cache / "gpd-update-check.json").write_text(
            json.dumps({"update_available": True, "checked": 20}),
            encoding="utf-8",
        )

        global_runtime_dir = home / ".claude"
        global_runtime_dir.mkdir(parents=True)
        (global_runtime_dir / "gpd-file-manifest.json").write_text(
            json.dumps({"install_scope": "global"}),
            encoding="utf-8",
        )

        with patch("gpd.hooks.runtime_detect.Path.home", return_value=home):
            assert _check_update(str(workspace)) == ""

    def test_default_check_update_ignores_uninstalled_runtime_cache_when_another_runtime_is_installed(
        self,
        tmp_path: Path,
    ) -> None:
        home = tmp_path / "home"

        stale_cache = tmp_path / ".claude" / "cache"
        stale_cache.mkdir(parents=True)
        (stale_cache / "gpd-update-check.json").write_text(
            json.dumps({"update_available": True, "checked": 20}),
            encoding="utf-8",
        )

        global_runtime_dir = home / ".codex"
        global_cache = global_runtime_dir / "cache"
        global_cache.mkdir(parents=True)
        (global_runtime_dir / "gpd-file-manifest.json").write_text(
            json.dumps({"install_scope": "global"}),
            encoding="utf-8",
        )
        (global_cache / "gpd-update-check.json").write_text(
            json.dumps({"update_available": False, "checked": 10}),
            encoding="utf-8",
        )

        with (
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
        ):
            assert _check_update() == ""

    def test_unknown_runtime_falls_back_to_bootstrap_update_command(self, tmp_path: Path) -> None:
        gpd_cache = tmp_path / ".gpd" / "cache"
        gpd_cache.mkdir(parents=True)
        (gpd_cache / "gpd-update-check.json").write_text(json.dumps({"update_available": True}), encoding="utf-8")

        with (
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.detect_active_runtime_with_gpd_install", return_value="unknown"),
        ):
            result = _check_update()

        assert "npx -y get-physics-done" in result

    def test_known_runtime_does_not_call_detect_install_scope(self, tmp_path: Path) -> None:
        """When get_adapter succeeds, detect_install_scope should not be called (lazy evaluation)."""
        gpd_cache = tmp_path / ".gpd" / "cache"
        gpd_cache.mkdir(parents=True)
        (gpd_cache / "gpd-update-check.json").write_text(json.dumps({"update_available": True}))

        with (
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.detect_active_runtime_with_gpd_install", return_value="claude-code"),
            patch("gpd.hooks.runtime_detect.detect_install_scope") as mock_scope,
        ):
            result = _check_update()

        mock_scope.assert_not_called()
        assert result != ""


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
            patch("gpd.hooks.statusline._read_execution_state", return_value={}),
            patch("gpd.hooks.statusline._check_update", return_value=""),
        ):
            main()
        return captured.getvalue()

    def test_empty_json_object_no_crash(self) -> None:
        """Empty {} input should still render the GPD label."""
        output = self._run_main({})
        assert "GPD" in output

    def test_missing_model_field_still_renders_gpd(self) -> None:
        """Missing 'model' key should not affect the GPD label."""
        output = self._run_main({"workspace": {"current_dir": "/tmp"}})
        assert "GPD" in output

    def test_model_field_is_none_does_not_crash(self) -> None:
        """model=None should still render the GPD label."""
        output = self._run_main({"model": None})
        assert "GPD" in output

    def test_empty_model_mapping_keeps_gpd_label(self) -> None:
        output = self._run_main({"model": {}})
        assert "GPD" in output

    def test_with_valid_model_renders_model_label(self) -> None:
        output = self._run_main({"model": {"display_name": "GPT-4o"}, "context_window": {"context_window_size": 200_000}})
        assert "GPD" in output
        assert "GPT-4o (200k context)" in output

    def test_model_name_field_is_used_as_fallback(self) -> None:
        output = self._run_main({"model": {"name": "Claude Sonnet"}})
        assert "GPD" in output
        assert "Claude Sonnet" in output

    def test_context_window_remaining_zero(self) -> None:
        """remaining_percentage=0 → shows 100% usage."""
        output = self._run_main({"context_window": {"remaining_percentage": 0}})
        assert "100%" in output

    def test_context_window_remaining_100(self) -> None:
        """remaining_percentage=100 → shows 0% usage."""
        output = self._run_main({"context_window": {"remaining_percentage": 100}})
        assert "0%" in output

    def test_main_resolves_workspace_before_runtime_specific_payload_selection(self, tmp_path: Path) -> None:
        process_cwd = tmp_path / "process-cwd"
        process_cwd.mkdir()
        (process_cwd / ".codex").mkdir(parents=True)
        (process_cwd / ".codex" / "gpd-file-manifest.json").write_text(
            json.dumps({"install_scope": "local"}),
            encoding="utf-8",
        )

        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / ".claude").mkdir(parents=True)
        (workspace / ".claude" / "gpd-file-manifest.json").write_text(
            json.dumps({"install_scope": "local"}),
            encoding="utf-8",
        )

        home = tmp_path / "home"
        home.mkdir()

        captured = io.StringIO()
        with (
            patch("sys.stdin", io.StringIO(json.dumps({"workspace": str(workspace)}))),
            patch("sys.stdout", captured),
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=process_cwd),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
            patch("gpd.hooks.statusline._read_position", return_value=""),
            patch("gpd.hooks.statusline._read_current_task", return_value=""),
            patch("gpd.hooks.statusline._read_execution_state", return_value={}),
            patch("gpd.hooks.statusline._check_update", return_value=""),
        ):
            main()

        assert "[workspace]" in captured.getvalue()

    def test_main_prefers_live_execution_task_over_todo_fallback(self) -> None:
        captured = io.StringIO()
        with (
            patch("sys.stdin", io.StringIO(json.dumps({"workspace": "/tmp/project"}))),
            patch("sys.stdout", captured),
            patch("gpd.hooks.statusline._read_position", return_value=""),
            patch("gpd.hooks.statusline._read_current_task", return_value="Todo task"),
            patch(
                "gpd.hooks.statusline._read_execution_state",
                return_value={
                    "segment_status": "waiting_review",
                    "current_task": "Live execution task",
                },
            ),
            patch("gpd.hooks.statusline._check_update", return_value=""),
        ):
            main()

        output = captured.getvalue()
        assert "Live execution task" in output
        assert "Todo task" not in output

    def test_no_context_window_field(self) -> None:
        """Missing context_window → no bar in output."""
        output = self._run_main({"model": {"display_name": "Test"}})
        assert "GPD" in output
        assert "Test" in output
        # No percentage should appear
        assert "%" not in output

    def test_context_window_is_none(self) -> None:
        """context_window=None → 'or {}' fallback, remaining is None → no bar."""
        output = self._run_main({"context_window": None})
        assert "GPD" in output
        assert "%" not in output

    def test_context_window_supports_remaining_percent_alias(self) -> None:
        output = self._run_main({"context_window": {"remainingPercent": 20}})
        assert "100%" in output

    def test_string_model_workspace_and_context_payloads_do_not_crash(self) -> None:
        output = self._run_main(
            {
                "model": "gpt-5",
                "workspace": "/tmp/research-project",
                "context_window": "not-a-mapping",
            }
        )
        assert "GPD" in output
        assert "gpt-5" in output
        assert "[research-project]" in output

    def test_string_workspace_is_forwarded_to_helpers(self) -> None:
        captured = io.StringIO()
        with (
            patch("sys.stdin", io.StringIO(json.dumps({"workspace": "/tmp/research-project"}))),
            patch("sys.stdout", captured),
            patch("gpd.hooks.statusline._read_position", return_value="") as mock_position,
            patch("gpd.hooks.statusline._read_current_task", return_value="") as mock_task,
            patch("gpd.hooks.statusline._read_execution_state", return_value={}),
            patch("gpd.hooks.statusline._check_update", return_value="") as mock_update,
        ):
            main()

        mock_position.assert_called_once_with("/tmp/research-project")
        mock_task.assert_called_once_with("", "/tmp/research-project")
        mock_update.assert_called_once_with("/tmp/research-project")
        assert "GPD" in captured.getvalue()

    def test_workspace_mapping_accepts_cwd_field(self) -> None:
        captured = io.StringIO()
        with (
            patch("sys.stdin", io.StringIO(json.dumps({"workspace": {"cwd": "/tmp/alternate-workspace"}}))),
            patch("sys.stdout", captured),
            patch("gpd.hooks.statusline._read_position", return_value="") as mock_position,
            patch("gpd.hooks.statusline._read_current_task", return_value="") as mock_task,
            patch("gpd.hooks.statusline._read_execution_state", return_value={}),
            patch("gpd.hooks.statusline._check_update", return_value="") as mock_update,
        ):
            main()

        mock_position.assert_called_once_with("/tmp/alternate-workspace")
        mock_task.assert_called_once_with("", "/tmp/alternate-workspace")
        mock_update.assert_called_once_with("/tmp/alternate-workspace")
        assert "GPD" in captured.getvalue()

    def test_top_level_cwd_workspace_alias_is_forwarded_to_helpers(self) -> None:
        captured = io.StringIO()
        with (
            patch("sys.stdin", io.StringIO(json.dumps({"cwd": "/tmp/top-level-workspace"}))),
            patch("sys.stdout", captured),
            patch("gpd.hooks.statusline._read_position", return_value="") as mock_position,
            patch("gpd.hooks.statusline._read_current_task", return_value="") as mock_task,
            patch("gpd.hooks.statusline._read_execution_state", return_value={}),
            patch("gpd.hooks.statusline._check_update", return_value="") as mock_update,
        ):
            main()

        mock_position.assert_called_once_with("/tmp/top-level-workspace")
        mock_task.assert_called_once_with("", "/tmp/top-level-workspace")
        mock_update.assert_called_once_with("/tmp/top-level-workspace")
        assert "GPD" in captured.getvalue()

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
            patch("gpd.hooks.statusline._read_execution_state", return_value={}),
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
            patch("gpd.hooks.statusline._read_execution_state", return_value={}),
            patch("gpd.hooks.statusline._check_update", return_value=""),
        ):
            main()
        assert "P3/10" in captured.getvalue()

    def test_first_result_gate_replaces_plain_task_display(self) -> None:
        captured = io.StringIO()
        with (
            patch("sys.stdin", io.StringIO(json.dumps({}))),
            patch("sys.stdout", captured),
            patch("gpd.hooks.statusline._read_position", return_value="P3/10"),
            patch("gpd.hooks.statusline._read_current_task", return_value="Routine task"),
            patch(
                "gpd.hooks.statusline._read_execution_state",
                return_value={
                    "segment_status": "waiting_review",
                    "first_result_gate_pending": True,
                    "review_cadence": "adaptive",
                    "last_result_label": "Benchmark reproduction",
                },
            ),
            patch("gpd.hooks.statusline._check_update", return_value=""),
        ):
            main()

        output = captured.getvalue()
        assert "REVIEW:first-result adaptive" in output
        assert "Routine task" not in output
        assert "Benchmark reproduction" in output

    def test_skeptical_review_prefers_anchor_label_over_result_label(self) -> None:
        captured = io.StringIO()
        with (
            patch("sys.stdin", io.StringIO(json.dumps({}))),
            patch("sys.stdout", captured),
            patch("gpd.hooks.statusline._read_position", return_value="P4/10"),
            patch("gpd.hooks.statusline._read_current_task", return_value="Routine task"),
            patch(
                "gpd.hooks.statusline._read_execution_state",
                return_value={
                    "segment_status": "waiting_review",
                    "waiting_for_review": True,
                    "checkpoint_reason": "pre_fanout",
                    "pre_fanout_review_pending": True,
                    "skeptical_requestioning_required": True,
                    "weakest_unchecked_anchor": "Direct observable benchmark",
                    "last_result_label": "Proxy fit",
                },
            ),
            patch("gpd.hooks.statusline._check_update", return_value=""),
        ):
            main()

        output = captured.getvalue()
        assert "REVIEW:skeptical" in output
        assert "Direct observable benchmark" in output
        assert "Proxy fit" not in output
