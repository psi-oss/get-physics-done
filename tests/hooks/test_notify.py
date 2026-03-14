"""Tests for gpd/hooks/notify.py."""

from __future__ import annotations

import io
import json
from pathlib import Path
from unittest.mock import patch

from gpd.hooks.notify import _check_and_notify_update, _emit_execution_notification, _hook_payload_policy, main


def _write_current_execution(workspace: Path, payload: dict[str, object]) -> None:
    observability = workspace / ".gpd" / "observability"
    observability.mkdir(parents=True, exist_ok=True)
    (observability / "current-execution.json").write_text(json.dumps(payload), encoding="utf-8")


def test_notify_uses_latest_local_cache_and_scoped_codex_install_command(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home_cache = home / ".gpd" / "cache"
    home_cache.mkdir(parents=True)
    (home_cache / "gpd-update-check.json").write_text(
        json.dumps({"update_available": False, "checked": 10}),
        encoding="utf-8",
    )

    local_cache = tmp_path / ".codex" / "cache"
    local_cache.mkdir(parents=True)
    (tmp_path / ".codex" / "gpd-file-manifest.json").write_text(
        json.dumps({"install_scope": "local"}),
        encoding="utf-8",
    )
    (local_cache / "gpd-update-check.json").write_text(
        json.dumps(
            {
                "update_available": True,
                "installed": "1.2.3",
                "latest": "1.3.0",
                "checked": 20,
            }
        ),
        encoding="utf-8",
    )

    stderr = io.StringIO()
    with (
        patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
        patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
        patch("gpd.hooks.runtime_detect.detect_active_runtime", return_value="codex"),
        patch("sys.stderr", stderr),
    ):
        _check_and_notify_update()

    output = stderr.getvalue()
    assert "Update available: v1.2.3" in output
    assert "v1.3.0" in output
    assert "Run: npx -y get-physics-done --codex --local" in output


def test_notify_prefers_active_runtime_cache_over_newer_unrelated_runtime_cache(tmp_path: Path) -> None:
    home = tmp_path / "home"

    local_runtime_dir = tmp_path / ".codex"
    local_cache = local_runtime_dir / "cache"
    local_cache.mkdir(parents=True)
    (local_runtime_dir / "gpd-file-manifest.json").write_text(
        json.dumps({"install_scope": "local"}),
        encoding="utf-8",
    )
    (local_cache / "gpd-update-check.json").write_text(
        json.dumps(
            {
                "update_available": True,
                "installed": "1.2.3",
                "latest": "1.3.0",
                "checked": 20,
            }
        ),
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
        json.dumps(
            {
                "update_available": True,
                "installed": "9.0.0",
                "latest": "9.1.0",
                "checked": 30,
            }
        ),
        encoding="utf-8",
    )

    stderr = io.StringIO()
    with (
        patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
        patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
        patch("gpd.hooks.runtime_detect.detect_active_runtime_with_gpd_install", return_value="codex"),
        patch("sys.stderr", stderr),
    ):
        _check_and_notify_update()

    output = stderr.getvalue()
    assert "Update available: v1.2.3" in output
    assert "v9.0.0" not in output
    assert "Run: npx -y get-physics-done --codex --local" in output


def test_notify_prefers_installed_global_scope_cache_over_stale_local_scope_cache(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    home = tmp_path / "home"

    local_cache = workspace / ".codex" / "cache"
    local_cache.mkdir(parents=True)
    (local_cache / "gpd-update-check.json").write_text(
        json.dumps(
            {
                "update_available": True,
                "installed": "1.2.3",
                "latest": "1.3.0",
                "checked": 30,
            }
        ),
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
        json.dumps(
            {
                "update_available": False,
                "installed": "9.0.0",
                "latest": "9.1.0",
                "checked": 10,
            }
        ),
        encoding="utf-8",
    )

    stderr = io.StringIO()
    with (
        patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
        patch("sys.stderr", stderr),
    ):
        _check_and_notify_update(str(workspace))

    assert stderr.getvalue() == ""


def test_notify_uses_explicit_workspace_cwd_over_process_cwd(tmp_path: Path) -> None:
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
        json.dumps(
            {
                "update_available": True,
                "installed": "2.0.0",
                "latest": "2.1.0",
                "checked": 30,
            }
        ),
        encoding="utf-8",
    )

    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / ".claude" / "cache").mkdir(parents=True)

    stderr = io.StringIO()
    with (
        patch("gpd.hooks.runtime_detect.Path.cwd", return_value=elsewhere),
        patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
        patch("sys.stderr", stderr),
    ):
        _check_and_notify_update(str(workspace))

    output = stderr.getvalue()
    assert "Update available: v2.0.0" in output
    assert "Run: npx -y get-physics-done --codex --local" in output


def test_notify_runtime_directory_without_install_uses_bootstrap_command(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    home = tmp_path / "home"

    local_cache = workspace / ".codex" / "cache"
    local_cache.mkdir(parents=True)
    (local_cache / "gpd-update-check.json").write_text(
        json.dumps(
            {
                "update_available": True,
                "installed": "2.0.0",
                "latest": "2.1.0",
                "checked": 30,
            }
        ),
        encoding="utf-8",
    )

    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()

    stderr = io.StringIO()
    with (
        patch("gpd.hooks.runtime_detect.Path.cwd", return_value=elsewhere),
        patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
        patch("sys.stderr", stderr),
    ):
        _check_and_notify_update(str(workspace))

    output = stderr.getvalue()
    assert "Update available: v2.0.0" in output
    assert "Run: npx -y get-physics-done" in output


def test_notify_ignores_stale_uninstalled_runtime_cache_when_other_runtime_is_installed(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    home = tmp_path / "home"

    stale_cache = workspace / ".codex" / "cache"
    stale_cache.mkdir(parents=True)
    (stale_cache / "gpd-update-check.json").write_text(
        json.dumps(
            {
                "update_available": True,
                "installed": "2.0.0",
                "latest": "2.1.0",
                "checked": 30,
            }
        ),
        encoding="utf-8",
    )

    global_runtime_dir = home / ".claude"
    global_runtime_dir.mkdir(parents=True)
    (global_runtime_dir / "gpd-file-manifest.json").write_text(
        json.dumps({"install_scope": "global"}),
        encoding="utf-8",
    )

    stderr = io.StringIO()
    with (
        patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
        patch("sys.stderr", stderr),
    ):
        _check_and_notify_update(str(workspace))

    assert stderr.getvalue() == ""


def test_hook_payload_policy_prefers_installed_runtime_over_stale_local_runtime_dir(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / ".codex").mkdir(parents=True)

    home = tmp_path / "home"
    global_runtime_dir = home / ".claude"
    global_runtime_dir.mkdir(parents=True)
    (global_runtime_dir / "gpd-file-manifest.json").write_text(
        json.dumps({"install_scope": "global"}),
        encoding="utf-8",
    )

    with patch("gpd.hooks.runtime_detect.Path.home", return_value=home):
        policy = _hook_payload_policy(str(workspace))

    assert policy.notify_event_types == ()


def test_main_resolves_workspace_before_filtering_event_types(tmp_path: Path) -> None:
    process_cwd = tmp_path / "process-cwd"
    process_cwd.mkdir()
    process_runtime_dir = process_cwd / ".codex"
    process_runtime_dir.mkdir(parents=True)
    (process_runtime_dir / "gpd-file-manifest.json").write_text(
        json.dumps({"install_scope": "local"}),
        encoding="utf-8",
    )

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    workspace_runtime_dir = workspace / ".claude"
    workspace_runtime_dir.mkdir(parents=True)
    (workspace_runtime_dir / "gpd-file-manifest.json").write_text(
        json.dumps({"install_scope": "local"}),
        encoding="utf-8",
    )

    home = tmp_path / "home"
    home.mkdir()
    payload = json.dumps({"type": "session-end", "workspace": str(workspace)})
    with (
        patch("sys.stdin", io.StringIO(payload)),
        patch("gpd.hooks.runtime_detect.Path.cwd", return_value=process_cwd),
        patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
        patch("gpd.hooks.notify._trigger_update_check") as mock_trigger,
        patch("gpd.hooks.notify._check_and_notify_update") as mock_notify,
    ):
        main()

    mock_trigger.assert_called_once_with(str(workspace))
    mock_notify.assert_called_once_with(str(workspace))


def test_main_accepts_workspace_mapping_with_cwd_field() -> None:
    with (
        patch("sys.stdin", io.StringIO(json.dumps({"type": "agent-turn-complete", "workspace": {"cwd": "/tmp/project"}}))),
        patch("gpd.hooks.notify._trigger_update_check") as mock_trigger,
        patch("gpd.hooks.notify._check_and_notify_update") as mock_notify,
    ):
        main()

    mock_trigger.assert_called_once_with("/tmp/project")
    mock_notify.assert_called_once_with("/tmp/project")


def test_main_accepts_top_level_cwd_workspace_alias() -> None:
    with (
        patch("sys.stdin", io.StringIO(json.dumps({"type": "agent-turn-complete", "cwd": "/tmp/project"}))),
        patch("gpd.hooks.notify._trigger_update_check") as mock_trigger,
        patch("gpd.hooks.notify._check_and_notify_update") as mock_notify,
    ):
        main()

    mock_trigger.assert_called_once_with("/tmp/project")
    mock_notify.assert_called_once_with("/tmp/project")


def test_main_accepts_string_workspace_payload() -> None:
    with (
        patch("sys.stdin", io.StringIO(json.dumps({"type": "agent-turn-complete", "workspace": "/tmp/project"}))),
        patch("gpd.hooks.notify._trigger_update_check") as mock_trigger,
        patch("gpd.hooks.notify._check_and_notify_update") as mock_notify,
    ):
        main()

    mock_trigger.assert_called_once_with("/tmp/project")
    mock_notify.assert_called_once_with("/tmp/project")


def test_main_logs_handler_exception_instead_of_swallowing(tmp_path: Path) -> None:
    """Exceptions in _trigger_update_check / _check_and_notify_update are logged via _debug."""
    payload = json.dumps({"type": "agent-turn-complete", "workspace": "/tmp/project"})
    stderr = io.StringIO()
    with (
        patch("sys.stdin", io.StringIO(payload)),
        patch("gpd.hooks.notify._trigger_update_check", side_effect=RuntimeError("boom")),
        patch.dict("os.environ", {"GPD_DEBUG": "1"}),
        patch("sys.stderr", stderr),
    ):
        # Should not raise — the exception is caught and logged
        main()

    output = stderr.getvalue()
    assert "notify handler failed: boom" in output


def test_emit_execution_notification_for_first_result_gate(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _write_current_execution(
        workspace,
        {
            "phase": "03",
            "plan": "01",
            "segment_id": "seg-1",
            "first_result_gate_pending": True,
            "last_result_label": "Benchmark reproduction",
        },
    )

    stderr = io.StringIO()
    with patch("sys.stderr", stderr):
        _emit_execution_notification(str(workspace))

    assert "First-result review due for 03-01" in stderr.getvalue()
    assert "Benchmark reproduction" in stderr.getvalue()


def test_emit_execution_notification_for_pre_fanout_review(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _write_current_execution(
        workspace,
        {
            "phase": "05",
            "plan": "03",
            "segment_id": "seg-9",
            "segment_status": "waiting_review",
            "waiting_for_review": True,
            "checkpoint_reason": "pre_fanout",
            "pre_fanout_review_pending": True,
        },
    )

    stderr = io.StringIO()
    with patch("sys.stderr", stderr):
        _emit_execution_notification(str(workspace))

    assert "Pre-fanout review due for 05-03" in stderr.getvalue()


def test_emit_execution_notification_for_skeptical_review_uses_anchor_focus(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _write_current_execution(
        workspace,
        {
            "phase": "05",
            "plan": "04",
            "segment_id": "seg-10",
            "segment_status": "waiting_review",
            "waiting_for_review": True,
            "checkpoint_reason": "pre_fanout",
            "pre_fanout_review_pending": True,
            "skeptical_requestioning_required": True,
            "weakest_unchecked_anchor": "Direct observable benchmark",
        },
    )

    stderr = io.StringIO()
    with patch("sys.stderr", stderr):
        _emit_execution_notification(str(workspace))

    output = stderr.getvalue()
    assert "Skeptical pre-fanout review due for 05-04" in output
    assert "Direct observable benchmark" in output


def test_emit_execution_notification_dedupes_repeated_resume_state(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _write_current_execution(
        workspace,
        {
            "phase": "04",
            "plan": "02",
            "segment_id": "seg-2",
            "segment_status": "paused",
            "resume_file": ".gpd/phases/04/.continue-here.md",
        },
    )

    stderr = io.StringIO()
    with patch("sys.stderr", stderr):
        _emit_execution_notification(str(workspace))
        _emit_execution_notification(str(workspace))

    output = stderr.getvalue()
    assert output.count("Resume ready for 04-02") == 1
