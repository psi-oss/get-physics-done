"""Behavior-focused hook regression coverage."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.parametrize(
    "cache_content",
    [
        "null",
        "[1, 2, 3]",
        '"just a string"',
        "{not valid json",
    ],
)
def test_notify_update_skips_non_dict_or_invalid_cache_files(tmp_path: Path, cache_content: str) -> None:
    from gpd.hooks.notify import _check_and_notify_update

    cache_file = tmp_path / "gpd-update-check.json"
    cache_file.write_text(cache_content, encoding="utf-8")

    with patch("gpd.hooks.runtime_detect.get_update_cache_files", return_value=[cache_file]), patch(
        "gpd.hooks.runtime_detect.detect_active_runtime",
        return_value="unknown",
    ):
        _check_and_notify_update()


def test_check_update_passes_cache_file_via_sys_argv() -> None:
    from gpd.hooks.check_update import main

    cache_path = Path("/tmp/test-cache.json")

    with patch("gpd.hooks.runtime_detect.get_update_cache_files", return_value=[cache_path]), patch(
        "gpd.hooks.check_update.subprocess.Popen"
    ) as mock_popen, patch.object(Path, "exists", return_value=False):
        mock_popen.return_value = MagicMock()
        main()

    args = mock_popen.call_args[0][0]

    assert "sys.argv[1]" in args[2]
    assert args[3] == str(cache_path)


def test_short_form_prerelease_is_older_than_final_release() -> None:
    from gpd.hooks.check_update import _is_older_than

    assert _is_older_than("1.0.0a1", "1.0.0") is True


def test_statusline_read_position_returns_empty_for_non_dict_state(tmp_path: Path) -> None:
    from gpd.hooks.statusline import _read_position

    gpd_dir = tmp_path / ".gpd"
    gpd_dir.mkdir()
    state_file = gpd_dir / "state.json"

    state_file.write_text("[]", encoding="utf-8")
    assert _read_position(str(tmp_path)) == ""

    state_file.write_text('"hello"', encoding="utf-8")
    assert _read_position(str(tmp_path)) == ""
