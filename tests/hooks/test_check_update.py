"""Tests for gpd/hooks/check_update.py edge cases.

Covers: npm registry unreachable, cache locked, version comparison, throttle
logic, background spawn failure, and graceful degradation.
"""

from __future__ import annotations

import inspect
import json
import os
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from gpd.adapters import get_adapter
from gpd.adapters.runtime_catalog import iter_runtime_descriptors
from gpd.hooks.check_update import (
    UPDATE_CHECK_TTL_SECONDS,
    _do_check,
    _is_older_than,
    _read_installed_version,
    _version_files,
    main,
)
from gpd.hooks.runtime_detect import UpdateCacheCandidate

_RUNTIME_DESCRIPTORS = iter_runtime_descriptors()


def _runtime_env_prefixes() -> tuple[str, ...]:
    prefixes: set[str] = set()
    for descriptor in _RUNTIME_DESCRIPTORS:
        for env_var in descriptor.activation_env_vars:
            prefixes.add(env_var)
            prefixes.add(env_var.rsplit("_", 1)[0] if "_" in env_var else env_var)
    return tuple(sorted(prefixes, key=len, reverse=True))


_RUNTIME_ENV_PREFIXES = _runtime_env_prefixes()


def _runtime_env_vars_to_clear() -> set[str]:
    env_vars = {"GPD_ACTIVE_RUNTIME", "XDG_CONFIG_HOME"}
    for descriptor in _RUNTIME_DESCRIPTORS:
        global_config = descriptor.global_config
        for env_var in (global_config.env_var, global_config.env_dir_var, global_config.env_file_var):
            if env_var:
                env_vars.add(env_var)
    return env_vars


_RUNTIME_ENV_VARS_TO_CLEAR = _runtime_env_vars_to_clear()


@pytest.fixture(autouse=True)
def _reset_runtime_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep update-hook tests isolated from prior runtime env overrides."""
    for key in list(os.environ):
        if key.startswith(_RUNTIME_ENV_PREFIXES) or key in _RUNTIME_ENV_VARS_TO_CLEAR:
            monkeypatch.delenv(key, raising=False)


def _cache_candidate(path: Path) -> UpdateCacheCandidate:
    return UpdateCacheCandidate(path=path)


def _mark_complete_install(config_dir: Path, *, runtime: str, install_scope: str = "local") -> None:
    adapter = get_adapter(runtime)
    config_dir.mkdir(parents=True, exist_ok=True)
    for relpath in adapter.install_completeness_relpaths():
        if relpath == "gpd-file-manifest.json":
            continue
        artifact = config_dir / relpath
        artifact.parent.mkdir(parents=True, exist_ok=True)
        if artifact.suffix:
            artifact.write_text("{}\n" if artifact.suffix == ".json" else "# test\n", encoding="utf-8")
        else:
            artifact.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, object] = {"install_scope": install_scope, "runtime": runtime}
    if runtime == "codex":
        skills_dir = config_dir.parent / ".agents" / "skills"
        (skills_dir / "gpd-help").mkdir(parents=True, exist_ok=True)
        manifest["codex_skills_dir"] = str(skills_dir)
    (config_dir / "gpd-file-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

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

    def test_short_version_string_normalizes_to_equal_release(self) -> None:
        assert _is_older_than("1.0", "1.0.0") is False

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

    def test_version_file_fallback_prefers_prioritized_runtime_candidate(self, tmp_path: Path) -> None:
        """Fallback VERSION scan checks the prioritized runtime candidate before unrelated runtimes."""
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

    def test_version_file_fallback_should_ignore_uninstalled_higher_priority_runtime(self, tmp_path: Path) -> None:
        """Install-aware expectation: a stale higher-priority runtime must not mask the installed runtime's VERSION."""
        home = tmp_path / "home"
        stale_claude_version = tmp_path / ".claude" / "get-physics-done" / "VERSION"
        installed_codex_dir = tmp_path / ".codex"
        installed_codex_version = installed_codex_dir / "get-physics-done" / "VERSION"
        stale_claude_version.parent.mkdir(parents=True)
        installed_codex_version.parent.mkdir(parents=True)
        stale_claude_version.write_text("1.0.0\n")
        installed_codex_version.write_text("2.0.0\n")
        _mark_complete_install(installed_codex_dir, runtime="codex")

        with (
            patch("gpd.version.__version__", "0.0.0-dev"),
            patch("gpd.hooks.runtime_detect.detect_active_runtime", return_value="claude-code"),
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
        ):
            assert _read_installed_version() == "2.0.0"

    def test_version_file_fallback_uses_hook_owning_install_for_explicit_target(self, tmp_path: Path) -> None:
        """When running from an explicit-target hook install, VERSION lookup stays under that install."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        home = tmp_path / "home"
        explicit_target = tmp_path / "custom-runtime-dir"
        hook_path = explicit_target / "hooks" / "check_update.py"
        hook_path.parent.mkdir(parents=True)
        hook_path.write_text("# hook\n", encoding="utf-8")
        _mark_complete_install(explicit_target, runtime="codex")
        (explicit_target / "get-physics-done" / "VERSION").write_text("7.7.7\n", encoding="utf-8")

        stale_workspace_version = workspace / ".claude" / "get-physics-done" / "VERSION"
        stale_workspace_version.parent.mkdir(parents=True)
        stale_workspace_version.write_text("1.0.0\n", encoding="utf-8")

        with (
            patch("gpd.version.__version__", "0.0.0-dev"),
            patch("gpd.hooks.check_update.__file__", str(hook_path)),
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=workspace),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
        ):
            assert _read_installed_version() == "7.7.7"

    def test_version_files_use_public_runtime_detect_surface(self) -> None:
        source = inspect.getsource(_version_files)

        assert "_detect_runtime_install_target" not in source
        assert "_local_runtime_dir" not in source
        assert "_global_runtime_dir" not in source
        assert "get_gpd_install_dirs" in source


# ─── _do_check — npm registry unreachable ────────────────────────────────


class TestDoCheck:
    """Tests for _do_check with network and filesystem edge cases."""

    def test_registry_unreachable_writes_no_update(self, tmp_path: Path) -> None:
        """When the npm registry is unreachable, writes cache with update_available=False."""
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

    def test_registry_returns_newer_version(self, tmp_path: Path) -> None:
        """When the npm registry returns a newer version, update_available=True."""
        cache_file = tmp_path / "gpd-update-check.json"
        registry_response = json.dumps({"version": "2.0.0"}).encode()

        mock_resp = MagicMock()
        mock_resp.read.return_value = registry_response
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
        assert mock_urlopen.call_args.args[0] == "https://registry.npmjs.org/get-physics-done/latest"

    def test_registry_returns_same_version(self, tmp_path: Path) -> None:
        """When the npm registry returns the same version, update_available=False."""
        cache_file = tmp_path / "gpd-update-check.json"
        registry_response = json.dumps({"version": "1.0.0"}).encode()

        mock_resp = MagicMock()
        mock_resp.read.return_value = registry_response
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
        cache_dir = tmp_path / "GPD" / "cache"
        cache_dir.mkdir(parents=True)
        cache_file = cache_dir / "gpd-update-check.json"
        cache_file.write_text(json.dumps({"checked": int(time.time()), "update_available": False}))

        with (
            patch(
                "gpd.hooks.runtime_detect.get_update_cache_candidates",
                return_value=[_cache_candidate(cache_file)],
            ),
            patch("gpd.hooks.check_update.Path.home", return_value=tmp_path),
            patch("subprocess.Popen") as mock_popen,
        ):
            main()

        mock_popen.assert_not_called()

    def test_stale_cache_spawns_check(self, tmp_path: Path) -> None:
        """If cache is stale (older than TTL), main() spawns background check."""
        cache_dir = tmp_path / "GPD" / "cache"
        cache_dir.mkdir(parents=True)
        cache_file = cache_dir / "gpd-update-check.json"
        stale_time = int(time.time()) - UPDATE_CHECK_TTL_SECONDS - 100
        cache_file.write_text(json.dumps({"checked": stale_time, "update_available": False}))

        with (
            patch(
                "gpd.hooks.runtime_detect.get_update_cache_candidates",
                return_value=[_cache_candidate(cache_file)],
            ),
            patch("gpd.hooks.check_update.Path.home", return_value=tmp_path),
            patch("subprocess.Popen") as mock_popen,
        ):
            main()

        mock_popen.assert_called_once()

    def test_no_cache_file_spawns_check(self, tmp_path: Path) -> None:
        """If no cache file exists, main() spawns background check."""
        with (
            patch(
                "gpd.hooks.runtime_detect.get_update_cache_candidates",
                return_value=[_cache_candidate(tmp_path / "nonexistent.json")],
            ),
            patch("gpd.hooks.check_update.Path.home", return_value=tmp_path),
            patch("subprocess.Popen") as mock_popen,
        ):
            main()

        mock_popen.assert_called_once()

    def test_corrupt_cache_spawns_check(self, tmp_path: Path) -> None:
        """If cache file is corrupt JSON, main() spawns background check."""
        cache_dir = tmp_path / "GPD" / "cache"
        cache_dir.mkdir(parents=True)
        cache_file = cache_dir / "gpd-update-check.json"
        cache_file.write_text("not json!")

        with (
            patch(
                "gpd.hooks.runtime_detect.get_update_cache_candidates",
                return_value=[_cache_candidate(cache_file)],
            ),
            patch("gpd.hooks.check_update.Path.home", return_value=tmp_path),
            patch("subprocess.Popen") as mock_popen,
        ):
            main()

        mock_popen.assert_called_once()

    def test_popen_failure_no_crash(self, tmp_path: Path) -> None:
        """If Popen fails (e.g., no Python executable), no crash."""
        cache_file = tmp_path / "nonexistent.json"
        with (
            patch(
                "gpd.hooks.runtime_detect.get_update_cache_candidates",
                return_value=[_cache_candidate(cache_file)],
            ),
            patch("gpd.hooks.check_update.Path.home", return_value=tmp_path),
            patch("subprocess.Popen", side_effect=OSError("exec failed")),
        ):
            main()  # Should not raise

        assert not cache_file.with_name("nonexistent.json.inflight").exists()

    def test_cache_with_missing_checked_field_spawns(self, tmp_path: Path) -> None:
        """Cache JSON without 'checked' field → spawns check."""
        cache_dir = tmp_path / "GPD" / "cache"
        cache_dir.mkdir(parents=True)
        cache_file = cache_dir / "gpd-update-check.json"
        cache_file.write_text(json.dumps({"update_available": False}))

        with (
            patch(
                "gpd.hooks.runtime_detect.get_update_cache_candidates",
                return_value=[_cache_candidate(cache_file)],
            ),
            patch("gpd.hooks.check_update.Path.home", return_value=tmp_path),
            patch("subprocess.Popen") as mock_popen,
        ):
            main()

        mock_popen.assert_called_once()

    def test_cache_with_non_numeric_checked_spawns(self, tmp_path: Path) -> None:
        """Cache with non-numeric 'checked' → isinstance check fails → spawns."""
        cache_dir = tmp_path / "GPD" / "cache"
        cache_dir.mkdir(parents=True)
        cache_file = cache_dir / "gpd-update-check.json"
        cache_file.write_text(json.dumps({"checked": "not-a-number"}))

        with (
            patch(
                "gpd.hooks.runtime_detect.get_update_cache_candidates",
                return_value=[_cache_candidate(cache_file)],
            ),
            patch("gpd.hooks.check_update.Path.home", return_value=tmp_path),
            patch("subprocess.Popen") as mock_popen,
        ):
            main()

        mock_popen.assert_called_once()

    def test_fresh_local_runtime_cache_suppresses_spawn(self, tmp_path: Path) -> None:
        """Any fresh runtime cache should satisfy throttle, not just the home GPD cache."""
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

    def test_fresh_unrelated_runtime_cache_does_not_suppress_preferred_runtime_refresh(self, tmp_path: Path) -> None:
        """A fresher cache for another runtime must not throttle the preferred runtime refresh."""
        home = tmp_path / "home"
        stale_codex_cache = tmp_path / ".codex" / "cache"
        stale_codex_cache.mkdir(parents=True)
        (stale_codex_cache / "gpd-update-check.json").write_text(
            json.dumps({"checked": int(time.time()) - UPDATE_CHECK_TTL_SECONDS - 100, "update_available": False}),
            encoding="utf-8",
        )

        fresh_claude_cache = home / ".claude" / "cache"
        fresh_claude_cache.mkdir(parents=True)
        (fresh_claude_cache / "gpd-update-check.json").write_text(
            json.dumps({"checked": int(time.time()), "update_available": False}),
            encoding="utf-8",
        )

        with (
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
            patch("gpd.hooks.check_update.Path.home", return_value=home),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
            patch("gpd.hooks.runtime_detect.detect_active_runtime", return_value="codex"),
            patch("subprocess.Popen") as mock_popen,
        ):
            main()

        mock_popen.assert_called_once()

    def test_fresh_preferred_runtime_global_cache_still_suppresses_spawn(self, tmp_path: Path) -> None:
        """A fresh cache for the preferred runtime should still satisfy throttle."""
        home = tmp_path / "home"
        fresh_codex_cache = home / ".codex" / "cache"
        fresh_codex_cache.mkdir(parents=True)
        (fresh_codex_cache / "gpd-update-check.json").write_text(
            json.dumps({"checked": int(time.time()), "update_available": False}),
            encoding="utf-8",
        )

        stale_claude_cache = home / ".claude" / "cache"
        stale_claude_cache.mkdir(parents=True)
        (stale_claude_cache / "gpd-update-check.json").write_text(
            json.dumps({"checked": int(time.time()) - UPDATE_CHECK_TTL_SECONDS - 100, "update_available": False}),
            encoding="utf-8",
        )

        with (
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
            patch("gpd.hooks.check_update.Path.home", return_value=home),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
            patch("gpd.hooks.runtime_detect.detect_active_runtime", return_value="codex"),
            patch("subprocess.Popen") as mock_popen,
        ):
            main()

        mock_popen.assert_not_called()

    def test_runtime_neutral_fallback_cache_does_not_suppress_preferred_refresh(self, tmp_path: Path) -> None:
        """A runtime-neutral fallback cache must not short-circuit the preferred runtime refresh."""
        home = tmp_path / "home"
        preferred_cache = tmp_path / ".codex" / "cache" / "gpd-update-check.json"
        preferred_cache.parent.mkdir(parents=True)
        preferred_cache.write_text(
            json.dumps({"checked": int(time.time()) - UPDATE_CHECK_TTL_SECONDS - 100, "update_available": False}),
            encoding="utf-8",
        )

        fallback_cache = home / "GPD" / "cache" / "gpd-update-check.json"
        fallback_cache.parent.mkdir(parents=True)
        fallback_cache.write_text(
            json.dumps({"checked": int(time.time()), "update_available": False}),
            encoding="utf-8",
        )

        with (
            patch(
                "gpd.hooks.runtime_detect.get_update_cache_candidates",
                return_value=[
                    UpdateCacheCandidate(path=preferred_cache, runtime="codex", scope="local"),
                    UpdateCacheCandidate(path=fallback_cache, runtime=None, scope=None),
                ],
            ),
            patch("gpd.hooks.runtime_detect.detect_active_runtime_with_gpd_install", return_value="unknown"),
            patch("gpd.hooks.runtime_detect.detect_runtime_for_gpd_use", return_value="codex"),
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
            patch("gpd.hooks.check_update.Path.home", return_value=home),
            patch("subprocess.Popen") as mock_popen,
        ):
            main()

        mock_popen.assert_called_once()
        spawned_cache = Path(mock_popen.call_args.args[0][-1])
        assert spawned_cache == preferred_cache

    def test_fresh_wrong_scope_cache_should_not_suppress_global_install_refresh(self, tmp_path: Path) -> None:
        """Install-aware expectation: a fresh cache from the wrong scope must not suppress refresh for the live install."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        home = tmp_path / "home"

        local_cache = workspace / ".codex" / "cache"
        local_cache.mkdir(parents=True)
        (local_cache / "gpd-update-check.json").write_text(
            json.dumps({"checked": int(time.time()), "update_available": False}),
            encoding="utf-8",
        )

        global_runtime_dir = home / ".codex"
        global_cache = global_runtime_dir / "cache"
        global_cache.mkdir(parents=True)
        _mark_complete_install(global_runtime_dir, runtime="codex", install_scope="global")
        (global_cache / "gpd-update-check.json").write_text(
            json.dumps({"checked": int(time.time()) - UPDATE_CHECK_TTL_SECONDS - 100, "update_available": False}),
            encoding="utf-8",
        )

        with (
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=workspace),
            patch("gpd.hooks.check_update.Path.home", return_value=home),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
            patch("gpd.hooks.runtime_detect.detect_active_runtime", return_value="codex"),
            patch("subprocess.Popen") as mock_popen,
        ):
            main()

        mock_popen.assert_called_once()

    def test_non_dict_cache_json_spawns_check(self, tmp_path: Path) -> None:
        """If cache file contains valid JSON but not a dict (e.g. a list), main() spawns background check."""
        cache_dir = tmp_path / "GPD" / "cache"
        cache_dir.mkdir(parents=True)
        cache_file = cache_dir / "gpd-update-check.json"
        cache_file.write_text(json.dumps([1, 2, 3]))

        with (
            patch(
                "gpd.hooks.runtime_detect.get_update_cache_candidates",
                return_value=[_cache_candidate(cache_file)],
            ),
            patch("gpd.hooks.check_update.Path.home", return_value=tmp_path),
            patch("subprocess.Popen") as mock_popen,
        ):
            main()

        mock_popen.assert_called_once()

    def test_string_cache_json_spawns_check(self, tmp_path: Path) -> None:
        """If cache file contains a JSON string instead of a dict, main() spawns background check."""
        cache_dir = tmp_path / "GPD" / "cache"
        cache_dir.mkdir(parents=True)
        cache_file = cache_dir / "gpd-update-check.json"
        cache_file.write_text(json.dumps("just a string"))

        with (
            patch(
                "gpd.hooks.runtime_detect.get_update_cache_candidates",
                return_value=[_cache_candidate(cache_file)],
            ),
            patch("gpd.hooks.check_update.Path.home", return_value=tmp_path),
            patch("subprocess.Popen") as mock_popen,
        ):
            main()

        mock_popen.assert_called_once()

    def test_fresh_inflight_marker_suppresses_duplicate_spawn(self, tmp_path: Path) -> None:
        cache_file = tmp_path / "GPD" / "cache" / "gpd-update-check.json"
        cache_file.parent.mkdir(parents=True)
        cache_file.with_name("gpd-update-check.json.inflight").write_text(str(int(time.time())), encoding="utf-8")

        with (
            patch(
                "gpd.hooks.runtime_detect.get_update_cache_candidates",
                return_value=[_cache_candidate(cache_file)],
            ),
            patch("gpd.hooks.check_update.Path.home", return_value=tmp_path),
            patch("subprocess.Popen") as mock_popen,
        ):
            main()

        mock_popen.assert_not_called()

    def test_stale_inflight_marker_is_replaced_before_spawning(self, tmp_path: Path) -> None:
        cache_file = tmp_path / "GPD" / "cache" / "gpd-update-check.json"
        cache_file.parent.mkdir(parents=True)
        marker = cache_file.with_name("gpd-update-check.json.inflight")
        marker.write_text(str(int(time.time()) - 1000), encoding="utf-8")

        with (
            patch(
                "gpd.hooks.runtime_detect.get_update_cache_candidates",
                return_value=[_cache_candidate(cache_file)],
            ),
            patch("gpd.hooks.check_update.Path.home", return_value=tmp_path),
            patch("subprocess.Popen") as mock_popen,
        ):
            main()

        mock_popen.assert_called_once()
        assert marker.exists()

    def test_explicit_target_hook_uses_own_cache_instead_of_workspace_candidates(self, tmp_path: Path) -> None:
        """Explicit-target hook refresh should always target its own cache path."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        home = tmp_path / "home"
        home.mkdir()
        explicit_target = tmp_path / "custom-runtime-dir"
        hook_path = explicit_target / "hooks" / "check_update.py"
        hook_path.parent.mkdir(parents=True)
        hook_path.write_text("# hook\n", encoding="utf-8")
        _mark_complete_install(explicit_target, runtime="codex")

        fresh_workspace_cache = workspace / ".claude" / "cache"
        fresh_workspace_cache.mkdir(parents=True)
        (fresh_workspace_cache / "gpd-update-check.json").write_text(
            json.dumps({"checked": int(time.time()), "update_available": False}),
            encoding="utf-8",
        )

        with (
            patch("gpd.hooks.check_update.__file__", str(hook_path)),
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=workspace),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
            patch("gpd.hooks.check_update.Path.cwd", return_value=workspace),
            patch("gpd.hooks.check_update.Path.home", return_value=home),
            patch("subprocess.Popen") as mock_popen,
        ):
            main()

        mock_popen.assert_called_once()
        spawned_argv = mock_popen.call_args.args[0]
        assert str(explicit_target / "cache" / "gpd-update-check.json") == spawned_argv[-1]
