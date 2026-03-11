"""Tests for gpd/hooks/check_update.py edge cases.

Covers: PyPI unreachable, cache locked, version comparison, throttle logic,
background spawn failure, and graceful degradation.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

from gpd.hooks.check_update import (
    UPDATE_CHECK_TTL_SECONDS,
    _do_check,
    _is_older_than,
    _read_installed_version,
    main,
)

# ─── _is_older_than ────────────────────────────────────────────────────────


class TestIsOlderThan:
    """Tests for semver comparison."""

    def test_older_patch(self) -> None:
        assert _is_older_than("1.0.0", "1.0.1") is True

    def test_older_minor(self) -> None:
        assert _is_older_than("1.0.0", "1.1.0") is True

    def test_older_major(self) -> None:
        assert _is_older_than("1.0.0", "2.0.0") is True

    def test_same_version(self) -> None:
        assert _is_older_than("1.0.0", "1.0.0") is False

    def test_newer_version(self) -> None:
        assert _is_older_than("2.0.0", "1.0.0") is False

    def test_short_version_string(self) -> None:
        assert _is_older_than("1.0", "1.0.1") is True

    def test_single_segment(self) -> None:
        assert _is_older_than("1", "2") is True

    def test_dev_version_always_older(self) -> None:
        # "0.0.0" vs any real version
        assert _is_older_than("0.0.0", "0.1.0") is True

    def test_pep440_dev_release_is_older_than_final(self) -> None:
        assert _is_older_than("1.2.3.dev4", "1.2.3") is True

    def test_pep440_rc_is_older_than_final(self) -> None:
        assert _is_older_than("2.0.0rc1", "2.0.0") is True

    def test_pep440_post_release_is_not_older_than_base_release(self) -> None:
        assert _is_older_than("1.2.3.post1", "1.2.3") is False


# ─── _read_installed_version ───────────────────────────────────────────────


class TestReadInstalledVersion:
    """Tests for reading installed version from metadata or VERSION files."""

    def test_reads_from_version_module(self) -> None:
        """When gpd.version.__version__ is set to a real version, uses that."""
        with patch("gpd.version.__version__", "3.5.1"):
            version = _read_installed_version()
        assert version == "3.5.1"

    def test_fallback_to_version_file(self, tmp_path: Path) -> None:
        """When metadata returns dev version, falls back to VERSION file."""
        version_file = tmp_path / "VERSION"
        version_file.write_text("1.2.3\n")

        with (
            patch("gpd.version.__version__", "0.0.0-dev"),
            patch("gpd.hooks.check_update._version_files", return_value=[version_file]),
        ):
            assert _read_installed_version() == "1.2.3"

    def test_no_version_sources_returns_zero(self) -> None:
        """When all version sources fail, returns '0.0.0'."""
        with (
            patch("gpd.version.__version__", "0.0.0-dev"),
            patch("gpd.hooks.check_update._version_files", return_value=[]),
        ):
            assert _read_installed_version() == "0.0.0"

    def test_pep440_dev_metadata_version_is_retained(self) -> None:
        """Real PEP 440 dev releases are valid installed versions, not fallback sentinels."""
        with patch("gpd.version.__version__", "1.2.3.dev4"):
            assert _read_installed_version() == "1.2.3.dev4"

    def test_version_file_fallback_prefers_active_runtime(self, tmp_path: Path) -> None:
        """Fallback VERSION scan checks the active runtime's install before unrelated runtimes."""
        home = tmp_path / "home"
        claude_version = tmp_path / ".claude" / "get-physics-done" / "VERSION"
        codex_version = home / ".codex" / "get-physics-done" / "VERSION"
        claude_version.parent.mkdir(parents=True)
        codex_version.parent.mkdir(parents=True)
        claude_version.write_text("1.0.0\n")
        codex_version.write_text("2.0.0\n")

        with (
            patch("gpd.version.__version__", "0.0.0-dev"),
            patch("gpd.hooks.runtime_detect.detect_active_runtime", return_value="codex"),
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
        ):
            assert _read_installed_version() == "2.0.0"


# ─── _do_check — PyPI unreachable ─────────────────────────────────────────


class TestDoCheck:
    """Tests for _do_check with network and filesystem edge cases."""

    def test_pypi_unreachable_writes_no_update(self, tmp_path: Path) -> None:
        """When PyPI is unreachable, writes cache with update_available=False."""
        cache_file = tmp_path / "gpd-update-check.json"

        with (
            patch("gpd.hooks.check_update._read_installed_version", return_value="1.0.0"),
            patch("urllib.request.urlopen", side_effect=TimeoutError("Connection timed out")),
        ):
            _do_check(cache_file)

        assert cache_file.exists()
        cache = json.loads(cache_file.read_text())
        assert cache["update_available"] is False
        assert cache["installed"] == "1.0.0"
        assert cache["latest"] == "unknown"

    def test_pypi_returns_newer_version(self, tmp_path: Path) -> None:
        """When PyPI returns a newer version, update_available=True."""
        cache_file = tmp_path / "gpd-update-check.json"
        pypi_response = json.dumps({"info": {"version": "2.0.0"}}).encode()

        mock_resp = MagicMock()
        mock_resp.read.return_value = pypi_response
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with (
            patch("gpd.hooks.check_update._read_installed_version", return_value="1.0.0"),
            patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen,
        ):
            _do_check(cache_file)

        cache = json.loads(cache_file.read_text())
        assert cache["update_available"] is True
        assert cache["latest"] == "2.0.0"
        assert mock_urlopen.call_args.args[0] == "https://pypi.org/pypi/get-physics-done/json"

    def test_pypi_returns_same_version(self, tmp_path: Path) -> None:
        """When PyPI returns same version, update_available=False."""
        cache_file = tmp_path / "gpd-update-check.json"
        pypi_response = json.dumps({"info": {"version": "1.0.0"}}).encode()

        mock_resp = MagicMock()
        mock_resp.read.return_value = pypi_response
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with (
            patch("gpd.hooks.check_update._read_installed_version", return_value="1.0.0"),
            patch("urllib.request.urlopen", return_value=mock_resp),
        ):
            _do_check(cache_file)

        cache = json.loads(cache_file.read_text())
        assert cache["update_available"] is False

    def test_cache_dir_creation(self, tmp_path: Path) -> None:
        """Parent directories are created if missing."""
        cache_file = tmp_path / "deep" / "nested" / "gpd-update-check.json"

        with (
            patch("gpd.hooks.check_update._read_installed_version", return_value="1.0.0"),
            patch("urllib.request.urlopen", side_effect=OSError("no network")),
        ):
            _do_check(cache_file)

        assert cache_file.exists()

    def test_cache_write_failure_no_crash(self, tmp_path: Path) -> None:
        """If cache file write fails (e.g., permissions), no crash."""
        # Point to a path that can't be written (parent is a file, not dir)
        blocker = tmp_path / "blocker"
        blocker.write_text("I am a file")
        cache_file = blocker / "subdir" / "gpd-update-check.json"

        with (
            patch("gpd.hooks.check_update._read_installed_version", return_value="1.0.0"),
            patch("urllib.request.urlopen", side_effect=OSError("no network")),
        ):
            # Should not raise
            _do_check(cache_file)


# ─── main() — throttle and spawn ──────────────────────────────────────────


class TestMainThrottle:
    """Tests for main() throttle and background spawn logic."""

    def test_recent_cache_skips_check(self, tmp_path: Path) -> None:
        """If cache was checked recently, main() returns without spawning."""
        cache_dir = tmp_path / ".gpd" / "cache"
        cache_dir.mkdir(parents=True)
        cache_file = cache_dir / "gpd-update-check.json"
        cache_file.write_text(json.dumps({"checked": int(time.time()), "update_available": False}))

        with (
            patch("gpd.hooks.runtime_detect.get_update_cache_files", return_value=[cache_file]),
            patch("gpd.hooks.check_update.Path.home", return_value=tmp_path),
            patch("subprocess.Popen") as mock_popen,
        ):
            main()

        mock_popen.assert_not_called()

    def test_stale_cache_spawns_check(self, tmp_path: Path) -> None:
        """If cache is stale (older than TTL), main() spawns background check."""
        cache_dir = tmp_path / ".gpd" / "cache"
        cache_dir.mkdir(parents=True)
        cache_file = cache_dir / "gpd-update-check.json"
        stale_time = int(time.time()) - UPDATE_CHECK_TTL_SECONDS - 100
        cache_file.write_text(json.dumps({"checked": stale_time, "update_available": False}))

        with (
            patch("gpd.hooks.runtime_detect.get_update_cache_files", return_value=[cache_file]),
            patch("gpd.hooks.check_update.Path.home", return_value=tmp_path),
            patch("subprocess.Popen") as mock_popen,
        ):
            main()

        mock_popen.assert_called_once()

    def test_no_cache_file_spawns_check(self, tmp_path: Path) -> None:
        """If no cache file exists, main() spawns background check."""
        with (
            patch("gpd.hooks.runtime_detect.get_update_cache_files", return_value=[tmp_path / "nonexistent.json"]),
            patch("gpd.hooks.check_update.Path.home", return_value=tmp_path),
            patch("subprocess.Popen") as mock_popen,
        ):
            main()

        mock_popen.assert_called_once()

    def test_corrupt_cache_spawns_check(self, tmp_path: Path) -> None:
        """If cache file is corrupt JSON, main() spawns background check."""
        cache_dir = tmp_path / ".gpd" / "cache"
        cache_dir.mkdir(parents=True)
        cache_file = cache_dir / "gpd-update-check.json"
        cache_file.write_text("not json!")

        with (
            patch("gpd.hooks.runtime_detect.get_update_cache_files", return_value=[cache_file]),
            patch("gpd.hooks.check_update.Path.home", return_value=tmp_path),
            patch("subprocess.Popen") as mock_popen,
        ):
            main()

        mock_popen.assert_called_once()

    def test_popen_failure_no_crash(self, tmp_path: Path) -> None:
        """If Popen fails (e.g., no Python executable), no crash."""
        with (
            patch("gpd.hooks.runtime_detect.get_update_cache_files", return_value=[tmp_path / "nonexistent.json"]),
            patch("gpd.hooks.check_update.Path.home", return_value=tmp_path),
            patch("subprocess.Popen", side_effect=OSError("exec failed")),
        ):
            main()  # Should not raise

    def test_cache_with_missing_checked_field_spawns(self, tmp_path: Path) -> None:
        """Cache JSON without 'checked' field → spawns check."""
        cache_dir = tmp_path / ".gpd" / "cache"
        cache_dir.mkdir(parents=True)
        cache_file = cache_dir / "gpd-update-check.json"
        cache_file.write_text(json.dumps({"update_available": False}))

        with (
            patch("gpd.hooks.runtime_detect.get_update_cache_files", return_value=[cache_file]),
            patch("gpd.hooks.check_update.Path.home", return_value=tmp_path),
            patch("subprocess.Popen") as mock_popen,
        ):
            main()

        mock_popen.assert_called_once()

    def test_cache_with_non_numeric_checked_spawns(self, tmp_path: Path) -> None:
        """Cache with non-numeric 'checked' → isinstance check fails → spawns."""
        cache_dir = tmp_path / ".gpd" / "cache"
        cache_dir.mkdir(parents=True)
        cache_file = cache_dir / "gpd-update-check.json"
        cache_file.write_text(json.dumps({"checked": "not-a-number"}))

        with (
            patch("gpd.hooks.runtime_detect.get_update_cache_files", return_value=[cache_file]),
            patch("gpd.hooks.check_update.Path.home", return_value=tmp_path),
            patch("subprocess.Popen") as mock_popen,
        ):
            main()

        mock_popen.assert_called_once()

    def test_fresh_local_runtime_cache_suppresses_spawn(self, tmp_path: Path) -> None:
        """Any fresh runtime cache should satisfy throttle, not just the home .gpd cache."""
        home = tmp_path / "home"
        local_cache = tmp_path / ".codex" / "cache"
        local_cache.mkdir(parents=True)
        (local_cache / "gpd-update-check.json").write_text(
            json.dumps({"checked": int(time.time()), "update_available": False}),
            encoding="utf-8",
        )

        with (
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
            patch("gpd.hooks.runtime_detect.detect_active_runtime", return_value="codex"),
            patch("subprocess.Popen") as mock_popen,
        ):
            main()

        mock_popen.assert_not_called()

    def test_non_dict_cache_json_spawns_check(self, tmp_path: Path) -> None:
        """If cache file contains valid JSON but not a dict (e.g. a list), main() spawns background check."""
        cache_dir = tmp_path / ".gpd" / "cache"
        cache_dir.mkdir(parents=True)
        cache_file = cache_dir / "gpd-update-check.json"
        cache_file.write_text(json.dumps([1, 2, 3]))

        with (
            patch("gpd.hooks.runtime_detect.get_update_cache_files", return_value=[cache_file]),
            patch("gpd.hooks.check_update.Path.home", return_value=tmp_path),
            patch("subprocess.Popen") as mock_popen,
        ):
            main()

        mock_popen.assert_called_once()

    def test_string_cache_json_spawns_check(self, tmp_path: Path) -> None:
        """If cache file contains a JSON string instead of a dict, main() spawns background check."""
        cache_dir = tmp_path / ".gpd" / "cache"
        cache_dir.mkdir(parents=True)
        cache_file = cache_dir / "gpd-update-check.json"
        cache_file.write_text(json.dumps("just a string"))

        with (
            patch("gpd.hooks.runtime_detect.get_update_cache_files", return_value=[cache_file]),
            patch("gpd.hooks.check_update.Path.home", return_value=tmp_path),
            patch("subprocess.Popen") as mock_popen,
        ):
            main()

        mock_popen.assert_called_once()
