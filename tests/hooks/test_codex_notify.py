"""Tests for gpd/hooks/codex_notify.py."""

from __future__ import annotations

import io
import json
import os
from pathlib import Path
from unittest.mock import patch

from gpd.hooks.codex_notify import _check_and_notify_update, main
from gpd.hooks.runtime_detect import RUNTIME_CODEX


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
        patch("gpd.hooks.runtime_detect.detect_active_runtime", return_value=RUNTIME_CODEX),
        patch("sys.stderr", stderr),
    ):
        _check_and_notify_update()

    output = stderr.getvalue()
    assert "Update available: v1.2.3" in output
    assert "v1.3.0" in output
    assert "Run: npx -y get-physics-done@latest --codex --local" in output


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
    assert "Run: npx -y get-physics-done@latest --codex --local" in output


def test_main_accepts_workspace_mapping_with_cwd_field() -> None:
    with (
        patch("sys.stdin", io.StringIO(json.dumps({"type": "agent-turn-complete", "workspace": {"cwd": "/tmp/project"}}))),
        patch("gpd.hooks.codex_notify._trigger_update_check") as mock_trigger,
        patch("gpd.hooks.codex_notify._check_and_notify_update") as mock_notify,
    ):
        main()

    mock_trigger.assert_called_once_with("/tmp/project")
    mock_notify.assert_called_once_with("/tmp/project")


def test_main_accepts_string_workspace_payload() -> None:
    with (
        patch("sys.stdin", io.StringIO(json.dumps({"type": "agent-turn-complete", "workspace": "/tmp/project"}))),
        patch("gpd.hooks.codex_notify._trigger_update_check") as mock_trigger,
        patch("gpd.hooks.codex_notify._check_and_notify_update") as mock_notify,
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
        patch("gpd.hooks.codex_notify._trigger_update_check", side_effect=RuntimeError("boom")),
        patch.dict("os.environ", {"GPD_DEBUG": "1"}),
        patch("sys.stderr", stderr),
    ):
        # Should not raise — the exception is caught and logged
        main()

    output = stderr.getvalue()
    assert "codex-notify handler failed: boom" in output
