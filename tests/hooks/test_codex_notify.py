"""Tests for gpd/hooks/codex_notify.py."""

from __future__ import annotations

import io
import json
from pathlib import Path
from unittest.mock import patch

from gpd.hooks.codex_notify import _check_and_notify_update
from gpd.hooks.runtime_detect import RUNTIME_CLAUDE


def test_notify_uses_latest_local_cache_and_valid_install_command(tmp_path: Path) -> None:
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
        patch("gpd.hooks.runtime_detect.detect_active_runtime", return_value=RUNTIME_CLAUDE),
        patch("sys.stderr", stderr),
    ):
        _check_and_notify_update()

    output = stderr.getvalue()
    assert "Update available: v1.2.3" in output
    assert "v1.3.0" in output
    assert "Run: npx github:physicalsuperintelligence/get-physics-done --claude" in output
