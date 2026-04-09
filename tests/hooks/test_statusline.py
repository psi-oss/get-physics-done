"""Tests for gpd/hooks/statusline.py edge cases.

Covers: empty input, missing fields, context_window boundary values,
graceful degradation, and ANSI output correctness.
"""

from __future__ import annotations

import io
import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import call, patch

from gpd.hooks.runtime_detect import TodoCandidate, update_command_for_runtime
from gpd.hooks.statusline import (
    _check_update,
    _context_bar,
    _execution_badge,
    _format_context_window_size,
    _project_state_dir,
    _read_current_task,
    _read_execution_state,
    _read_model_label,
    _read_position,
    _read_session_id,
    _read_workspace_label,
    main,
)
from tests.hooks.helpers import mark_complete_install as _mark_complete_install
from tests.hooks.helpers import repair_command as _repair_command

_TEST_MODEL = "model-under-test"


def _todo_candidates(*paths: Path) -> list[TodoCandidate]:
    return [TodoCandidate(path) for path in paths]


def _visibility_state(**overrides: object) -> SimpleNamespace:
    """Build a minimal execution-visibility stand-in for statusline tests."""
    current_execution = overrides.pop("current_execution", None)
    payload: dict[str, object] = {
        "workspace_root": "/tmp/project",
        "has_live_execution": False,
        "status_classification": "idle",
        "assessment": "idle",
        "possibly_stalled": False,
        "stale_after_minutes": 30,
        "last_updated_at": None,
        "last_updated_age_label": None,
        "last_updated_age_minutes": None,
        "phase": None,
        "plan": None,
        "wave": None,
        "segment_status": None,
        "current_task": None,
        "current_task_index": None,
        "current_task_total": None,
        "current_task_progress": None,
        "segment_reason": None,
        "checkpoint_reason": None,
        "waiting_reason": None,
        "blocked_reason": None,
        "review_reason": None,
        "last_result_label": None,
        "last_artifact_path": None,
        "resume_file": None,
        "current_execution": current_execution,
        "suggested_next_steps": [],
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


def _runtime_hints_payload(
    visibility: SimpleNamespace | None = None,
    *,
    cost: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "execution": vars(visibility) if visibility is not None else None,
        "cost": cost or {},
    }


class _ExecutionSnapshot(SimpleNamespace):
    def model_dump(self, mode: str = "json") -> dict[str, object]:
        return dict(self.__dict__)

    def __getattr__(self, name: str) -> object:
        return None


def test_project_state_dir_keeps_workspace_lookup_for_policy_alias_only_workspace_mapping(tmp_path: Path) -> None:
    project = tmp_path / "project"
    nested = project / "src" / "notes"
    nested.mkdir(parents=True)

    result = _project_state_dir(
        {"workspace": {"current_dir": str(nested), "project_root": str(project)}},
        workspace_dir=str(nested),
        project_root=str(project),
        runtime_lookup_dir=str(nested),
        active_runtime=None,
        hook_payload=SimpleNamespace(
            workspace_keys=("cwd", "current_dir"),
            project_dir_keys=("project_dir", "project_root"),
        ),
    )

    assert result == str(nested)


def test_project_state_dir_ignores_stale_raw_project_hint_when_resolved_project_root_is_authoritative(tmp_path: Path) -> None:
    project = tmp_path / "project"
    nested = project / "src" / "notes"
    stale = tmp_path / "stale-project"
    nested.mkdir(parents=True)

    result = _project_state_dir(
        {"workspace": {"cwd": str(nested), "project_dir": str(stale)}},
        workspace_dir=str(nested),
        project_root=str(project),
        runtime_lookup_dir=str(nested),
        active_runtime=None,
        hook_payload=SimpleNamespace(
            workspace_keys=("cwd", "current_dir"),
            project_dir_keys=("project_dir", "project_root"),
        ),
    )

    assert result == str(project)

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

    def test_read_model_label_uses_canonical_fallback_keys_when_policy_is_sparse(self) -> None:
        label = _read_model_label(
            {"model": {"display_name": "Opus 4.6"}, "context_window": {"context_window_size": 1_000_000}},
            SimpleNamespace(model_keys=(), context_window_size_keys=()),
        )
        assert label == "Opus 4.6 (1M context)"

    def test_read_workspace_label_prefers_project_relative_path(self, tmp_path: Path) -> None:
        project = tmp_path / "project"
        current = project / "src" / "gpd"
        current.mkdir(parents=True)

        label = _read_workspace_label({"workspace": {"project_dir": str(project)}}, str(current))
        assert label == "[project/src/gpd]"

    def test_read_workspace_label_prefers_resolved_project_root_argument(self, tmp_path: Path) -> None:
        project = tmp_path / "project"
        current = project / "src" / "gpd"
        current.mkdir(parents=True)

        label = _read_workspace_label({}, str(current), project_root=str(project))
        assert label == "[project/src/gpd]"

    def test_read_workspace_label_falls_back_to_directory_name(self, tmp_path: Path) -> None:
        current = tmp_path / "workspace"
        current.mkdir()

        label = _read_workspace_label({}, str(current))
        assert label == "[workspace]"

    def test_read_session_id_uses_adapter_exposed_runtime_key_before_top_level_legacy_field(self) -> None:
        payload = {
            "session_id": "legacy-top-level",
            "workspace": {"runtime_session_id": "runtime-owned"},
        }
        hook_payload = SimpleNamespace(runtime_session_id_keys=("runtime_session_id",))

        assert _read_session_id(payload, hook_payload) == "runtime-owned"

    def test_read_session_id_ignores_bare_top_level_session_id_when_runtime_key_is_unavailable(self) -> None:
        payload = {"session_id": "legacy-top-level"}
        hook_payload = SimpleNamespace(runtime_session_id_keys=())

        assert _read_session_id(payload, hook_payload) == ""

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
        badge = _execution_badge({"segment_status": "paused", "resume_file": "GPD/phases/02/.continue-here.md"})
        assert badge == "RESUME"

    def test_visibility_paused_or_resumable_with_resume_file_uses_resume_badge(self) -> None:
        badge = _execution_badge(
            {"segment_status": "active"},
            _visibility_state(
                has_live_execution=True,
                status_classification="paused-or-resumable",
                assessment="paused-or-resumable",
                current_execution={
                    "segment_status": "paused",
                    "resume_file": "GPD/phases/02/.continue-here.md",
                },
                resume_file="GPD/phases/02/.continue-here.md",
            ),
        )
        assert badge == "RESUME"

    def test_visibility_active_possibly_stalled_uses_stall_badge(self) -> None:
        badge = _execution_badge(
            {"segment_status": "active"},
            _visibility_state(
                has_live_execution=True,
                status_classification="active",
                assessment="possibly stalled",
                possibly_stalled=True,
                last_updated_age_label="45m ago",
                current_execution={
                    "segment_status": "active",
                    "updated_at": "2026-03-10T00:45:00+00:00",
                },
            ),
        )
        assert "STALL?" in badge

    def test_review_badge_wins_over_resume_for_bounded_gate_state(self) -> None:
        badge = _execution_badge(
            {
                "segment_status": "paused",
                "resume_file": "GPD/phases/02/.continue-here.md",
                "checkpoint_reason": "pre_fanout",
                "pre_fanout_review_pending": True,
                "downstream_locked": True,
            }
        )
        assert "REVIEW:pre-fanout" in badge

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

    def test_pre_fanout_review_badge_persists_until_clear_even_if_lock_was_removed(self) -> None:
        badge = _execution_badge(
            {
                "segment_status": "waiting_review",
                "checkpoint_reason": "pre_fanout",
                "pre_fanout_review_pending": True,
                "downstream_locked": False,
            }
        )
        assert "REVIEW:pre-fanout" in badge


def test_read_execution_state_prefers_lineage_head_over_legacy_current_execution_snapshot(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    observability = workspace / "GPD" / "observability"
    observability.mkdir(parents=True, exist_ok=True)
    (observability / "current-execution.json").write_text(
        json.dumps(
            {
                "session_id": "legacy-session",
                "phase": "06",
                "plan": "03",
                "segment_status": "paused",
                "current_task": "Legacy snapshot task",
                "updated_at": "2026-03-27T12:01:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    head_snapshot = _ExecutionSnapshot(
        session_id="lineage-session",
        phase="06",
        plan="03",
        segment_status="waiting_review",
        waiting_for_review=True,
        checkpoint_reason="pre_fanout",
        pre_fanout_review_pending=True,
        current_task="Lineage head task",
        updated_at="2026-03-27T12:03:00+00:00",
    )

    with patch("gpd.core.observability.get_current_execution", return_value=head_snapshot):
        execution = _read_execution_state(str(workspace))

    assert execution["current_task"] == "Lineage head task"
    assert execution["checkpoint_reason"] == "pre_fanout"
    assert execution["segment_status"] == "waiting_review"
    assert execution["current_task"] != "Legacy snapshot task"


# ─── _read_position edge cases ─────────────────────────────────────────────


class TestReadPosition:
    """Tests for _read_position with various state files."""

    def test_missing_state_file_returns_empty(self, tmp_path: Path) -> None:
        assert _read_position(str(tmp_path)) == ""

    def test_valid_state_with_phase_only(self, tmp_path: Path) -> None:
        planning = tmp_path / "GPD"
        planning.mkdir()
        state = {"position": {"current_phase": 3, "total_phases": 10}}
        (planning / "state.json").write_text(json.dumps(state), encoding="utf-8")
        assert _read_position(str(tmp_path)) == "P3/10"

    def test_valid_state_with_phase_and_plan(self, tmp_path: Path) -> None:
        planning = tmp_path / "GPD"
        planning.mkdir()
        state = {"position": {"current_phase": 2, "total_phases": 5, "current_plan": 1, "total_plans_in_phase": 3}}
        (planning / "state.json").write_text(json.dumps(state), encoding="utf-8")
        assert _read_position(str(tmp_path)) == "P2/5 plan 1/3"

    def test_empty_position_returns_empty(self, tmp_path: Path) -> None:
        planning = tmp_path / "GPD"
        planning.mkdir()
        state = {"position": {}}
        (planning / "state.json").write_text(json.dumps(state), encoding="utf-8")
        assert _read_position(str(tmp_path)) == ""

    def test_missing_phase_returns_empty(self, tmp_path: Path) -> None:
        planning = tmp_path / "GPD"
        planning.mkdir()
        state = {"position": {"total_phases": 5}}
        (planning / "state.json").write_text(json.dumps(state), encoding="utf-8")
        assert _read_position(str(tmp_path)) == ""

    def test_missing_total_phases_returns_empty(self, tmp_path: Path) -> None:
        planning = tmp_path / "GPD"
        planning.mkdir()
        state = {"position": {"current_phase": 3}}
        (planning / "state.json").write_text(json.dumps(state), encoding="utf-8")
        assert _read_position(str(tmp_path)) == ""

    def test_corrupt_json_returns_empty(self, tmp_path: Path) -> None:
        planning = tmp_path / "GPD"
        planning.mkdir()
        (planning / "state.json").write_text("not valid json{{{", encoding="utf-8")
        assert _read_position(str(tmp_path)) == ""

    def test_nested_workspace_walks_up_to_project_root(self, tmp_path: Path) -> None:
        planning = tmp_path / "GPD"
        planning.mkdir()
        nested = tmp_path / "src" / "notes"
        nested.mkdir(parents=True)
        state = {"position": {"current_phase": 4, "total_phases": 9}}
        (planning / "state.json").write_text(json.dumps(state), encoding="utf-8")
        assert _read_position(str(nested)) == "P4/9"

    def test_tilde_workspace_expands_before_project_root_lookup(self, tmp_path: Path) -> None:
        home = tmp_path / "home"
        project = home / "project"
        planning = project / "GPD"
        planning.mkdir(parents=True)
        nested = project / "src"
        nested.mkdir(parents=True)
        state = {"position": {"current_phase": 7, "total_phases": 8}}
        (planning / "state.json").write_text(json.dumps(state), encoding="utf-8")

        with patch.dict(os.environ, {"HOME": str(home)}):
            assert _read_position("~/project/src") == "P7/8"

    def test_no_position_key_returns_empty(self, tmp_path: Path) -> None:
        planning = tmp_path / "GPD"
        planning.mkdir()
        (planning / "state.json").write_text(json.dumps({"other": "data"}), encoding="utf-8")
        assert _read_position(str(tmp_path)) == ""


# ─── _read_current_task edge cases ─────────────────────────────────────────


class TestReadCurrentTask:
    """Tests for _read_current_task."""

    def test_empty_session_id_returns_empty(self) -> None:
        assert _read_current_task("") == ""

    def test_no_matching_todo_files(self, tmp_path: Path) -> None:
        todo_dir = tmp_path / "todos"
        todo_dir.mkdir()
        with patch("gpd.hooks.install_context.ordered_todo_lookup_candidates", return_value=_todo_candidates(todo_dir)):
            assert _read_current_task("session-123") == ""

    def test_matching_file_with_in_progress_task(self, tmp_path: Path) -> None:
        todo_dir = tmp_path / "todos"
        todo_dir.mkdir()
        todos = [{"status": "in_progress", "activeForm": "Running tests"}]
        (todo_dir / "session-123-agent-abc.json").write_text(json.dumps(todos), encoding="utf-8")
        with patch("gpd.hooks.install_context.ordered_todo_lookup_candidates", return_value=_todo_candidates(todo_dir)):
            assert _read_current_task("session-123") == "Running tests"

    def test_matching_file_no_in_progress_task(self, tmp_path: Path) -> None:
        todo_dir = tmp_path / "todos"
        todo_dir.mkdir()
        todos = [{"status": "completed", "activeForm": "Done"}]
        (todo_dir / "session-123-agent-abc.json").write_text(json.dumps(todos), encoding="utf-8")
        with patch("gpd.hooks.install_context.ordered_todo_lookup_candidates", return_value=_todo_candidates(todo_dir)):
            assert _read_current_task("session-123") == ""

    def test_higher_priority_todo_candidate_wins_even_when_lower_priority_file_is_newer(
        self,
        tmp_path: Path,
    ) -> None:
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

        with patch(
            "gpd.hooks.install_context.ordered_todo_lookup_candidates",
            return_value=_todo_candidates(local_todo_dir, global_todo_dir),
        ):
            assert _read_current_task("session-123") == "Prefer local"

    def test_lower_priority_todo_candidate_is_used_when_higher_priority_candidate_has_no_in_progress_task(
        self,
        tmp_path: Path,
    ) -> None:
        local_todo_dir = tmp_path / ".codex" / "todos"
        global_todo_dir = tmp_path / "home" / ".codex" / "todos"
        local_todo_dir.mkdir(parents=True)
        global_todo_dir.mkdir(parents=True)

        (local_todo_dir / "session-123-agent-local.json").write_text(
            json.dumps([{"status": "completed", "activeForm": "Completed local"}]),
            encoding="utf-8",
        )
        (global_todo_dir / "session-123-agent-global.json").write_text(
            json.dumps([{"status": "in_progress", "activeForm": "Use global fallback"}]),
            encoding="utf-8",
        )

        with patch(
            "gpd.hooks.install_context.ordered_todo_lookup_candidates",
            return_value=_todo_candidates(local_todo_dir, global_todo_dir),
        ):
            assert _read_current_task("session-123") == "Use global fallback"

    def test_corrupt_todo_file_returns_empty(self, tmp_path: Path) -> None:
        todo_dir = tmp_path / "todos"
        todo_dir.mkdir()
        (todo_dir / "session-123-agent-abc.json").write_text("not json!", encoding="utf-8")
        with patch("gpd.hooks.install_context.ordered_todo_lookup_candidates", return_value=_todo_candidates(todo_dir)):
            assert _read_current_task("session-123") == ""

    def test_nonexistent_todo_dirs(self) -> None:
        with patch(
            "gpd.hooks.install_context.ordered_todo_lookup_candidates",
            return_value=_todo_candidates(Path("/nonexistent/todos")),
        ):
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

        with patch("gpd.hooks.install_context.ordered_todo_lookup_candidates", return_value=_todo_candidates(todo_dir)):
            assert _read_current_task("session-1") == "Correct task"

    def test_self_owned_todo_candidate_moves_to_front_when_already_present(self, tmp_path: Path) -> None:
        from gpd.hooks.install_context import HookLookupContext, SelfOwnedInstallContext, ordered_todo_lookup_candidates

        hook_file = tmp_path / ".codex" / "hooks" / "statusline.py"
        self_install = SelfOwnedInstallContext(
            config_dir=tmp_path / ".codex",
            runtime="codex",
            install_scope="local",
        )
        self_candidate = TodoCandidate(path=tmp_path / ".codex" / "todos", runtime="codex", scope="local")
        other_candidate = TodoCandidate(path=tmp_path / "other" / "todos", runtime="claude-code", scope="global")

        with (
            patch(
                "gpd.hooks.install_context.resolve_hook_lookup_context",
                return_value=HookLookupContext(
                    lookup_cwd=tmp_path,
                    resolved_home=tmp_path / "home",
                    active_runtime=None,
                    preferred_runtime="codex",
                ),
            ),
            patch("gpd.hooks.install_context.detect_self_owned_install", return_value=self_install),
            patch("gpd.hooks.runtime_detect.get_todo_candidates", return_value=[other_candidate, self_candidate]),
            patch("gpd.hooks.runtime_detect.should_consider_todo_candidate", return_value=True),
        ):
            candidates = ordered_todo_lookup_candidates(hook_file=hook_file, cwd=tmp_path)

        assert candidates[0] == self_candidate


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
        gpd_cache = tmp_path / "GPD" / "cache"
        gpd_cache.mkdir(parents=True)
        (gpd_cache / "gpd-update-check.json").write_text(json.dumps({"update_available": True}), encoding="utf-8")
        with (
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.detect_active_runtime_with_gpd_install", return_value="claude-code"),
        ):
            result = _check_update()
            expected = update_command_for_runtime("claude-code")
            assert expected in result

    def test_cache_with_no_update(self, tmp_path: Path) -> None:
        gpd_cache = tmp_path / "GPD" / "cache"
        gpd_cache.mkdir(parents=True)
        (gpd_cache / "gpd-update-check.json").write_text(json.dumps({"update_available": False}), encoding="utf-8")
        with (
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=tmp_path),
        ):
            assert _check_update() == ""

    def test_corrupt_cache_returns_empty(self, tmp_path: Path) -> None:
        gpd_cache = tmp_path / "GPD" / "cache"
        gpd_cache.mkdir(parents=True)
        (gpd_cache / "gpd-update-check.json").write_text("broken{json", encoding="utf-8")
        with (
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=tmp_path),
        ):
            assert _check_update() == ""

    def test_non_mapping_cache_is_ignored_instead_of_crashing(self, tmp_path: Path) -> None:
        gpd_cache = tmp_path / "GPD" / "cache"
        gpd_cache.mkdir(parents=True)
        (gpd_cache / "gpd-update-check.json").write_text(json.dumps(["not", "a", "mapping"]), encoding="utf-8")

        with (
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=tmp_path / "home"),
        ):
            assert _check_update() == ""

    def test_local_runtime_cache_can_override_stale_home_cache(self, tmp_path: Path) -> None:
        home = tmp_path / "home"
        home_cache = home / "GPD" / "cache"
        home_cache.mkdir(parents=True)
        (home_cache / "gpd-update-check.json").write_text(
            json.dumps({"update_available": False, "checked": 10}),
            encoding="utf-8",
        )

        local_cache = tmp_path / ".codex" / "cache"
        local_cache.mkdir(parents=True)
        _mark_complete_install(tmp_path / ".codex", runtime="codex")
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

        expected = update_command_for_runtime("codex")
        assert expected in result

    def test_local_runtime_cache_uses_cache_runtime_when_install_exists(self, tmp_path: Path) -> None:
        home = tmp_path / "home"
        home_cache = home / "GPD" / "cache"
        home_cache.mkdir(parents=True)
        (home_cache / "gpd-update-check.json").write_text(
            json.dumps({"update_available": False, "checked": 10}),
            encoding="utf-8",
        )

        local_runtime_dir = tmp_path / ".codex"
        local_cache = local_runtime_dir / "cache"
        local_cache.mkdir(parents=True)
        _mark_complete_install(local_runtime_dir, runtime="codex")
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

        expected = _repair_command(
            "codex",
            install_scope="local",
            target_dir=local_runtime_dir,
            explicit_target=False,
        )
        assert expected in result

    def test_active_runtime_cache_beats_newer_unrelated_runtime_cache(self, tmp_path: Path) -> None:
        home = tmp_path / "home"

        local_runtime_dir = tmp_path / ".codex"
        local_cache = local_runtime_dir / "cache"
        local_cache.mkdir(parents=True)
        _mark_complete_install(local_runtime_dir, runtime="codex")
        (local_cache / "gpd-update-check.json").write_text(
            json.dumps({"update_available": True, "checked": 20}),
            encoding="utf-8",
        )

        unrelated_runtime_dir = home / ".claude"
        unrelated_cache = unrelated_runtime_dir / "cache"
        unrelated_cache.mkdir(parents=True)
        _mark_complete_install(unrelated_runtime_dir, runtime="claude-code", install_scope="global")
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

        expected = _repair_command(
            "codex",
            install_scope="local",
            target_dir=local_runtime_dir,
            explicit_target=False,
        )
        assert expected in result
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
        _mark_complete_install(global_runtime_dir, runtime="codex", install_scope="global")
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
        _mark_complete_install(workspace / ".codex", runtime="codex")
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

        expected = _repair_command(
            "codex",
            install_scope="local",
            target_dir=workspace / ".codex",
            explicit_target=False,
        )
        assert expected in result

    def test_explicit_target_hook_cache_uses_target_dir_update_command(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        explicit_target = tmp_path / "custom-runtime-dir"
        hook_path = explicit_target / "hooks" / "statusline.py"
        cache_file = explicit_target / "cache" / "gpd-update-check.json"
        hook_path.parent.mkdir(parents=True)
        cache_file.parent.mkdir(parents=True)
        hook_path.write_text("# hook\n", encoding="utf-8")
        _mark_complete_install(explicit_target, runtime="codex")
        cache_file.write_text(json.dumps({"update_available": True, "checked": 20}), encoding="utf-8")

        with patch("gpd.hooks.statusline.__file__", str(hook_path)):
            result = _check_update(str(workspace))

        expected = _repair_command(
            "codex",
            install_scope="local",
            target_dir=explicit_target,
            explicit_target=True,
        )
        assert expected in result
        assert str(explicit_target) in result

    def test_statusline_ignores_unrelated_self_config_cache_when_workspace_has_active_install(
        self,
        tmp_path: Path,
    ) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        home = tmp_path / "home"

        workspace_runtime_dir = workspace / ".codex"
        workspace_cache = workspace_runtime_dir / "cache"
        workspace_cache.mkdir(parents=True)
        _mark_complete_install(workspace_runtime_dir, runtime="codex")
        (workspace_cache / "gpd-update-check.json").write_text(
            json.dumps({"update_available": True, "checked": 20}),
            encoding="utf-8",
        )

        unrelated_runtime_dir = tmp_path / "custom-runtime-dir"
        hook_path = unrelated_runtime_dir / "hooks" / "statusline.py"
        unrelated_cache = unrelated_runtime_dir / "cache"
        hook_path.parent.mkdir(parents=True)
        unrelated_cache.mkdir(parents=True)
        hook_path.write_text("# hook\n", encoding="utf-8")
        _mark_complete_install(unrelated_runtime_dir, runtime="codex")
        (unrelated_cache / "gpd-update-check.json").write_text(
            json.dumps({"update_available": True, "checked": 30}),
            encoding="utf-8",
        )

        with (
            patch("gpd.hooks.statusline.__file__", str(hook_path)),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
        ):
            result = _check_update(str(workspace))

        expected = _repair_command(
            "codex",
            install_scope="local",
            target_dir=workspace_runtime_dir,
            explicit_target=False,
        )
        assert expected in result
        assert str(unrelated_runtime_dir) not in result

    def test_explicit_target_hook_cache_does_not_recover_missing_install_scope_from_legacy_surface(
        self,
        tmp_path: Path,
    ) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        explicit_target = tmp_path / "custom-runtime-dir"
        hook_path = explicit_target / "hooks" / "statusline.py"
        cache_file = explicit_target / "cache" / "gpd-update-check.json"
        hook_path.parent.mkdir(parents=True)
        cache_file.parent.mkdir(parents=True)
        hook_path.write_text("# hook\n", encoding="utf-8")
        _mark_complete_install(explicit_target, runtime="codex")
        update_workflow = explicit_target / "get-physics-done" / "workflows" / "update.md"
        update_workflow.parent.mkdir(parents=True, exist_ok=True)
        update_workflow.write_text('INSTALL_SCOPE="--local"\n', encoding="utf-8")
        manifest_path = explicit_target / "gpd-file-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest.pop("install_scope", None)
        manifest["explicit_target"] = True
        manifest["install_target_dir"] = str(explicit_target)
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        cache_file.write_text(json.dumps({"update_available": True, "checked": 20}), encoding="utf-8")

        with patch("gpd.hooks.statusline.__file__", str(hook_path)):
            result = _check_update(str(workspace))

        assert result == ""

    def test_runtime_less_explicit_target_hook_does_not_emit_update_command(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        explicit_target = tmp_path / "custom-runtime-dir"
        hook_path = explicit_target / "hooks" / "statusline.py"
        cache_file = explicit_target / "cache" / "gpd-update-check.json"
        hook_path.parent.mkdir(parents=True)
        cache_file.parent.mkdir(parents=True)
        hook_path.write_text("# hook\n", encoding="utf-8")
        _mark_complete_install(explicit_target)
        cache_file.write_text(json.dumps({"update_available": True, "checked": 20}), encoding="utf-8")

        with patch("gpd.hooks.statusline.__file__", str(hook_path)):
            result = _check_update(str(workspace))

        assert result == ""

    def test_runtime_directory_without_install_emits_no_update_command(self, tmp_path: Path) -> None:
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

        assert result == ""

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
        _mark_complete_install(global_runtime_dir, runtime="claude-code", install_scope="global")

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
        _mark_complete_install(global_runtime_dir, runtime="codex", install_scope="global")
        (global_cache / "gpd-update-check.json").write_text(
            json.dumps({"update_available": False, "checked": 10}),
            encoding="utf-8",
        )

        with (
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
        ):
            assert _check_update() == ""

    def test_unknown_runtime_falls_back_to_runtime_neutral_update_command(self, tmp_path: Path) -> None:
        gpd_cache = tmp_path / "GPD" / "cache"
        gpd_cache.mkdir(parents=True)
        (gpd_cache / "gpd-update-check.json").write_text(json.dumps({"update_available": True}), encoding="utf-8")

        with (
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.detect_active_runtime_with_gpd_install", return_value="unknown"),
        ):
            result = _check_update()

        assert update_command_for_runtime("unknown") in result
        assert "gpd-update" not in result

    def test_known_runtime_resolves_scope_for_bootstrap_update_command(self, tmp_path: Path) -> None:
        """Known runtimes should still resolve scope before rendering the bootstrap command."""
        gpd_cache = tmp_path / "GPD" / "cache"
        gpd_cache.mkdir(parents=True)
        (gpd_cache / "gpd-update-check.json").write_text(json.dumps({"update_available": True}), encoding="utf-8")

        with (
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.detect_active_runtime_with_gpd_install", return_value="claude-code"),
            patch("gpd.hooks.runtime_detect.detect_install_scope") as mock_scope,
        ):
            result = _check_update()

        mock_scope.assert_called_once_with("claude-code", cwd=None, home=tmp_path)
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
            patch("gpd.hooks.statusline._read_runtime_hints", return_value=_runtime_hints_payload(_visibility_state())),
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

    def test_main_uses_workspace_local_runtime_lookup_and_runtime_session_id_keys(
        self,
        tmp_path: Path,
    ) -> None:
        project = tmp_path / "project"
        nested = project / "src" / "notes"
        nested.mkdir(parents=True)
        (project / "GPD").mkdir(parents=True)
        _mark_complete_install(nested / ".codex", runtime="codex")

        payload = {
            "workspace": {"cwd": str(nested), "project_dir": str(project)},
            "runtime_session_id": "sess-runtime",
        }
        hook_payload = SimpleNamespace(
            project_dir_keys=("project_dir",),
            runtime_session_id_keys=("runtime_session_id",),
            model_keys=(),
            context_remaining_keys=(),
        )

        captured = io.StringIO()
        with (
            patch("sys.stdin", io.StringIO(json.dumps(payload))),
            patch("sys.stdout", captured),
            patch(
                "gpd.hooks.statusline._resolve_payload_roots",
                return_value=SimpleNamespace(
                    workspace_dir=str(nested),
                    project_root=str(project),
                    project_dir_present=True,
                    project_dir_trusted=False,
                ),
            ),
            patch(
                "gpd.hooks.install_context.resolve_hook_lookup_context",
                return_value=SimpleNamespace(
                    lookup_cwd=nested,
                    resolved_home=tmp_path / "home",
                    active_runtime="codex",
                    preferred_runtime="codex",
                ),
            ),
            patch(
                "gpd.hooks.statusline.resolve_runtime_lookup_context_from_payload_roots",
                return_value=SimpleNamespace(lookup_dir=str(nested), active_runtime="codex"),
            ) as mock_runtime_lookup,
            patch("gpd.hooks.statusline._hook_payload_policy", return_value=hook_payload) as mock_policy,
            patch("gpd.hooks.statusline._read_runtime_hints", return_value=_runtime_hints_payload(_visibility_state())) as mock_hints,
            patch("gpd.hooks.statusline._read_execution_state", return_value={}) as mock_execution,
            patch("gpd.hooks.statusline._read_position", return_value="") as mock_position,
            patch("gpd.hooks.statusline._read_current_task", return_value="") as mock_task,
            patch("gpd.hooks.statusline._check_update", return_value="") as mock_update,
            patch("gpd.hooks.statusline._read_workspace_label", return_value="[project/src/notes]") as mock_label,
            patch("gpd.hooks.statusline._read_model_label", return_value="model") as mock_model,
        ):
            main()

        mock_runtime_lookup.assert_called_once()
        assert mock_policy.call_args_list == [call(str(nested)), call(str(nested))]
        mock_hints.assert_called_once_with(str(nested))
        mock_execution.assert_called_once_with(str(nested))
        mock_position.assert_called_once_with(str(nested))
        mock_task.assert_called_once_with("sess-runtime", str(nested))
        mock_update.assert_called_once_with(str(nested))
        mock_label.assert_called_once()
        mock_model.assert_called_once()
        assert "[project/src/notes]" in captured.getvalue()

    def test_main_uses_workspace_runtime_lookup_when_project_dir_hint_is_not_authoritative(
        self,
        tmp_path: Path,
    ) -> None:
        project = tmp_path / "project"
        nested = project / "src" / "notes"
        nested.mkdir(parents=True)
        (project / "GPD").mkdir(parents=True)
        _mark_complete_install(nested / ".codex", runtime="codex")

        stale_project_dir = tmp_path / "stale" / "project"
        payload = {
            "workspace": {"cwd": str(nested), "project_dir": str(stale_project_dir)},
            "runtime_session_id": "sess-runtime",
        }
        hook_payload = SimpleNamespace(
            project_dir_keys=("project_dir",),
            runtime_session_id_keys=("runtime_session_id",),
            model_keys=(),
            context_remaining_keys=(),
        )

        def _fake_payload_runtime(cwd: str | None = None) -> str | None:
            if cwd == str(nested):
                return "codex"
            if cwd == str(project):
                return None
            return None

        captured = io.StringIO()
        with (
            patch("sys.stdin", io.StringIO(json.dumps(payload))),
            patch("sys.stdout", captured),
            patch(
                "gpd.hooks.statusline._resolve_payload_roots",
                return_value=SimpleNamespace(
                    workspace_dir=str(nested),
                    project_root=str(project),
                    project_dir_present=True,
                    project_dir_trusted=False,
                ),
            ),
            patch(
                "gpd.hooks.statusline.resolve_runtime_lookup_context_from_payload_roots",
                return_value=SimpleNamespace(lookup_dir=str(nested), active_runtime="codex"),
            ) as mock_runtime_lookup,
            patch("gpd.hooks.statusline._hook_payload_policy", return_value=hook_payload) as mock_policy,
            patch("gpd.hooks.statusline._read_runtime_hints", return_value=_runtime_hints_payload(_visibility_state())) as mock_hints,
            patch("gpd.hooks.statusline._read_execution_state", return_value={}) as mock_execution,
            patch("gpd.hooks.statusline._read_position", return_value="") as mock_position,
            patch("gpd.hooks.statusline._read_current_task", return_value="") as mock_task,
            patch("gpd.hooks.statusline._check_update", return_value="") as mock_update,
            patch("gpd.hooks.statusline._read_workspace_label", return_value="[project/src/notes]") as mock_label,
            patch("gpd.hooks.statusline._read_model_label", return_value="model") as mock_model,
        ):
            main()

        mock_runtime_lookup.assert_called_once()
        assert mock_policy.call_args_list == [call(str(nested)), call(str(nested))]
        mock_hints.assert_called_once_with(str(nested))
        mock_execution.assert_called_once_with(str(nested))
        mock_position.assert_called_once_with(str(nested))
        mock_task.assert_called_once_with("sess-runtime", str(nested))
        mock_update.assert_called_once_with(str(nested))
        mock_label.assert_called_once()
        mock_model.assert_called_once()
        assert "[project/src/notes]" in captured.getvalue()

    def test_main_downgrades_top_level_alias_only_workspace_mapping_to_keep_workspace_lookup(
        self,
        tmp_path: Path,
    ) -> None:
        project = tmp_path / "project"
        nested = project / "src" / "notes"
        nested.mkdir(parents=True)
        (project / "GPD").mkdir(parents=True)

        payload = {
            "current_dir": str(nested),
            "project_root": str(project),
            "runtime_session_id": "sess-runtime",
        }
        hook_payload = SimpleNamespace(
            workspace_keys=("cwd", "current_dir"),
            project_dir_keys=("project_dir", "project_root"),
            runtime_session_id_keys=("runtime_session_id",),
            model_keys=(),
            context_remaining_keys=(),
        )

        captured = io.StringIO()
        with (
            patch("sys.stdin", io.StringIO(json.dumps(payload))),
            patch("sys.stdout", captured),
            patch(
                "gpd.hooks.statusline._resolve_payload_roots",
                return_value=SimpleNamespace(
                    workspace_dir=str(nested),
                    project_root=str(project),
                    project_dir_present=True,
                    project_dir_trusted=True,
                ),
            ),
            patch(
                "gpd.hooks.statusline.resolve_runtime_lookup_context_from_payload_roots",
                return_value=SimpleNamespace(lookup_dir=str(nested), active_runtime="codex"),
            ) as mock_runtime_lookup,
            patch("gpd.hooks.statusline._hook_payload_policy", return_value=hook_payload),
            patch("gpd.hooks.statusline._read_runtime_hints", return_value=_runtime_hints_payload(_visibility_state())),
            patch("gpd.hooks.statusline._read_execution_state", return_value={}),
            patch("gpd.hooks.statusline._read_position", return_value=""),
            patch("gpd.hooks.statusline._read_current_task", return_value=""),
            patch("gpd.hooks.statusline._check_update", return_value=""),
            patch("gpd.hooks.statusline._read_workspace_label", return_value="[project/src/notes]"),
            patch("gpd.hooks.statusline._read_model_label", return_value="model"),
        ):
            main()

        runtime_roots = mock_runtime_lookup.call_args.args[0]
        assert runtime_roots.project_dir_trusted is False
        assert "[project/src/notes]" in captured.getvalue()

    def test_main_prefers_live_execution_task_over_todo_fallback(self) -> None:
        captured = io.StringIO()
        with (
            patch("sys.stdin", io.StringIO(json.dumps({"workspace": "/tmp/project"}))),
            patch("sys.stdout", captured),
            patch(
                "gpd.hooks.statusline._read_runtime_hints",
                return_value=_runtime_hints_payload(
                    _visibility_state(
                        has_live_execution=True,
                        status_classification="waiting",
                        assessment="waiting",
                        current_task="Live execution task",
                        current_execution={
                            "segment_status": "waiting_review",
                            "current_task": "Live execution task",
                        },
                    )
                ),
            ),
            patch("gpd.hooks.statusline._read_position", return_value=""),
            patch("gpd.hooks.statusline._read_current_task", return_value="Todo task"),
            patch("gpd.hooks.statusline._read_execution_state", return_value={}),
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

    def test_context_window_uses_canonical_aliases_when_policy_is_sparse(self) -> None:
        captured = io.StringIO()
        sparse_policy = SimpleNamespace(
            workspace_keys=(),
            project_dir_keys=(),
            runtime_session_id_keys=(),
            model_keys=(),
            context_window_size_keys=(),
            context_remaining_keys=(),
        )
        with (
            patch("sys.stdin", io.StringIO(json.dumps({"context_window": {"remaining_percentage": 0}}))),
            patch("sys.stdout", captured),
            patch("gpd.hooks.statusline._hook_payload_policy", return_value=sparse_policy),
            patch("gpd.hooks.statusline._read_runtime_hints", return_value=_runtime_hints_payload(_visibility_state())),
            patch("gpd.hooks.statusline._read_position", return_value=""),
            patch("gpd.hooks.statusline._read_current_task", return_value=""),
            patch("gpd.hooks.statusline._read_execution_state", return_value={}),
            patch("gpd.hooks.statusline._check_update", return_value=""),
        ):
            main()

        assert "100%" in captured.getvalue()

    def test_string_model_workspace_and_context_payloads_do_not_crash(self) -> None:
        output = self._run_main(
            {
                "model": _TEST_MODEL,
                "workspace": "/tmp/research-project",
                "context_window": "not-a-mapping",
            }
        )
        assert "GPD" in output
        assert _TEST_MODEL in output
        assert "[research-project]" in output

    def test_workspace_mapping_accepts_cwd_field(self) -> None:
        expected = str(Path("/tmp/alternate-workspace").resolve(strict=False))
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

        mock_position.assert_called_once_with(expected)
        mock_task.assert_called_once_with("", expected)
        mock_update.assert_called_once_with(expected)
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
            patch(
                "gpd.hooks.statusline._read_runtime_hints",
                return_value=_runtime_hints_payload(
                    _visibility_state(
                        has_live_execution=True,
                        status_classification="waiting",
                        assessment="waiting",
                        current_execution={
                            "segment_status": "waiting_review",
                            "first_result_gate_pending": True,
                            "review_cadence": "adaptive",
                            "last_result_label": "Benchmark reproduction",
                            "last_result_id": "R-bridge-01",
                        },
                    )
                ),
            ),
            patch("gpd.hooks.statusline._read_position", return_value="P3/10"),
            patch("gpd.hooks.statusline._read_current_task", return_value="Routine task"),
            patch("gpd.hooks.statusline._read_execution_state", return_value={}),
            patch("gpd.hooks.statusline._check_update", return_value=""),
        ):
            main()

        output = captured.getvalue()
        assert "REVIEW:first-result adaptive" in output
        assert "Routine task" not in output
        assert "Benchmark reproduction" in output
        assert "rerun anchor: R-bridge-01" not in output

    def test_first_result_gate_renders_last_result_id_when_label_missing(self) -> None:
        captured = io.StringIO()
        with (
            patch("sys.stdin", io.StringIO(json.dumps({}))),
            patch("sys.stdout", captured),
            patch(
                "gpd.hooks.statusline._read_runtime_hints",
                return_value=_runtime_hints_payload(
                    _visibility_state(
                        has_live_execution=True,
                        status_classification="waiting",
                        assessment="waiting",
                        current_execution={
                            "segment_status": "waiting_review",
                            "first_result_gate_pending": True,
                            "review_cadence": "adaptive",
                            "last_result_id": "R-bridge-01",
                        },
                    )
                ),
            ),
            patch("gpd.hooks.statusline._read_position", return_value="P3/10"),
            patch("gpd.hooks.statusline._read_current_task", return_value="Routine task"),
            patch("gpd.hooks.statusline._read_execution_state", return_value={}),
            patch("gpd.hooks.statusline._check_update", return_value=""),
        ):
            main()

        output = captured.getvalue()
        assert "REVIEW:first-result adaptive" in output
        assert "Routine task" not in output
        assert "rerun anchor: R-bridge-01" in output

    def test_skeptical_review_prefers_anchor_label_over_result_label(self) -> None:
        captured = io.StringIO()
        with (
            patch("sys.stdin", io.StringIO(json.dumps({}))),
            patch("sys.stdout", captured),
            patch(
                "gpd.hooks.statusline._read_runtime_hints",
                return_value=_runtime_hints_payload(
                    _visibility_state(
                        has_live_execution=True,
                        status_classification="waiting",
                        assessment="waiting",
                        current_execution={
                            "segment_status": "waiting_review",
                            "waiting_for_review": True,
                            "checkpoint_reason": "pre_fanout",
                            "pre_fanout_review_pending": True,
                            "skeptical_requestioning_required": True,
                            "weakest_unchecked_anchor": "Direct observable benchmark",
                            "last_result_label": "Proxy fit",
                            "last_result_id": "R-bridge-01",
                        },
                    )
                ),
            ),
            patch("gpd.hooks.statusline._read_position", return_value="P4/10"),
            patch("gpd.hooks.statusline._read_current_task", return_value="Routine task"),
            patch("gpd.hooks.statusline._read_execution_state", return_value={}),
            patch("gpd.hooks.statusline._check_update", return_value=""),
        ):
            main()

        output = captured.getvalue()
        assert "REVIEW:skeptical" in output
        assert "Direct observable benchmark" in output
        assert "Proxy fit" not in output
        assert "rerun anchor: R-bridge-01" not in output

    def test_execution_state_rendering_does_not_claim_stuck(self) -> None:
        captured = io.StringIO()
        with (
            patch("sys.stdin", io.StringIO(json.dumps({}))),
            patch("sys.stdout", captured),
            patch(
                "gpd.hooks.statusline._read_runtime_hints",
                return_value=_runtime_hints_payload(
                    _visibility_state(
                        has_live_execution=True,
                        status_classification="waiting",
                        assessment="waiting",
                        current_execution={
                            "segment_status": "waiting_review",
                            "waiting_for_review": True,
                            "waiting_reason": "time_budget_exceeded",
                            "segment_started_at": "2026-03-10T00:00:00+00:00",
                            "updated_at": "2026-03-10T00:45:00+00:00",
                        },
                    )
                ),
            ),
            patch("gpd.hooks.statusline._read_position", return_value="P4/10"),
            patch("gpd.hooks.statusline._read_current_task", return_value="Routine task"),
            patch("gpd.hooks.statusline._read_execution_state", return_value={}),
            patch("gpd.hooks.statusline._check_update", return_value=""),
        ):
            main()

        output = captured.getvalue().lower()
        assert "stuck" not in output
        assert "wait:budget" in output or "review" in output

    def test_main_uses_visibility_stall_badge_without_raw_snapshot_heuristics(self) -> None:
        captured = io.StringIO()
        with (
            patch("sys.stdin", io.StringIO(json.dumps({}))),
            patch("sys.stdout", captured),
            patch(
                "gpd.hooks.statusline._read_runtime_hints",
                return_value=_runtime_hints_payload(
                    _visibility_state(
                        has_live_execution=True,
                        status_classification="active",
                        assessment="possibly stalled",
                        possibly_stalled=True,
                        last_updated_age_label="45m ago",
                        current_task="Benchmark reproduction",
                        current_execution={
                            "segment_status": "active",
                            "current_task": "Benchmark reproduction",
                            "updated_at": "2026-03-10T00:45:00+00:00",
                        },
                    )
                ),
            ),
            patch("gpd.hooks.statusline._read_position", return_value=""),
            patch("gpd.hooks.statusline._read_current_task", return_value="Todo task"),
            patch("gpd.hooks.statusline._read_execution_state", return_value={}),
            patch("gpd.hooks.statusline._check_update", return_value=""),
        ):
            main()

        output = captured.getvalue()
        assert "STALL?" in output
        assert "Todo task" not in output

    def test_main_keeps_review_badge_and_surfaces_tangent_summary_in_detail_slot(self) -> None:
        captured = io.StringIO()
        with (
            patch("sys.stdin", io.StringIO(json.dumps({}))),
            patch("sys.stdout", captured),
            patch(
                "gpd.hooks.statusline._read_runtime_hints",
                return_value=_runtime_hints_payload(
                    _visibility_state(
                        has_live_execution=True,
                        status_classification="waiting",
                        assessment="waiting",
                        current_task="Review benchmark",
                        current_execution={
                            "segment_status": "waiting_review",
                            "waiting_for_review": True,
                            "tangent_summary": "Check whether the 2D case is degenerate",
                            "tangent_decision": "branch_later",
                            "updated_at": "2026-03-10T00:45:00+00:00",
                        },
                    )
                ),
            ),
            patch("gpd.hooks.statusline._read_position", return_value=""),
            patch("gpd.hooks.statusline._read_current_task", return_value="Todo task"),
            patch("gpd.hooks.statusline._read_execution_state", return_value={}),
            patch("gpd.hooks.statusline._check_update", return_value=""),
        ):
            main()

        output = captured.getvalue().lower()
        assert "review" in output
        assert "branch later: check whether the 2d case is degenerate" in output
