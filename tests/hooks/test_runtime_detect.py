"""Tests for gpd/hooks/runtime_detect.py edge cases.

Covers: no runtime dirs, multiple runtime dirs, env var detection,
priority ordering, helper functions, and unknown runtime fallback.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

from gpd.adapters import get_adapter
from gpd.hooks.runtime_detect import (
    RUNTIME_UNKNOWN,
    SCOPE_GLOBAL,
    SCOPE_LOCAL,
    SOURCE_ENV,
    SOURCE_GLOBAL,
    SOURCE_LOCAL,
    TodoCandidate,
    UpdateCacheCandidate,
    _has_gpd_install,
    all_runtime_dirs,
    detect_active_runtime,
    detect_active_runtime_with_gpd_install,
    detect_install_scope,
    detect_runtime_for_gpd_use,
    get_cache_dirs,
    get_gpd_install_dirs,
    get_todo_candidates,
    get_todo_dirs,
    get_update_cache_candidates,
    get_update_cache_files,
    resolve_effective_runtime,
    should_consider_todo_candidate,
    should_consider_update_cache_candidate,
    update_command_for_runtime,
)

RUNTIME_CLAUDE = "claude-code"
RUNTIME_CODEX = "codex"
RUNTIME_GEMINI = "gemini"
RUNTIME_OPENCODE = "opencode"
_RUNTIME_ENV_PREFIXES = ("CLAUDE_CODE", "CODEX", "GEMINI", "OPENCODE")
_RUNTIME_ENV_VARS_TO_CLEAR = {"GPD_ACTIVE_RUNTIME", "XDG_CONFIG_HOME"}


def _clean_runtime_env() -> dict[str, str]:
    """Return a deterministic env baseline for runtime-detection tests."""
    return {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(_RUNTIME_ENV_PREFIXES) and key not in _RUNTIME_ENV_VARS_TO_CLEAR
    }


def _mark_gpd_install(config_dir: Path) -> None:
    """Mark a runtime directory as containing a GPD install."""
    (config_dir / "get-physics-done").mkdir(parents=True, exist_ok=True)


def _write_install_manifest(config_dir: Path, *, install_scope: str) -> None:
    """Write a minimal manifest describing the install scope."""
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "gpd-file-manifest.json").write_text(
        json.dumps({"install_scope": install_scope}),
        encoding="utf-8",
    )

# ─── detect_active_runtime ─────────────────────────────────────────────────


class TestDetectActiveRuntime:
    """Tests for detect_active_runtime with various env/dir states."""

    def test_no_env_no_dirs_returns_unknown(self, tmp_path: Path) -> None:
        """When no env vars set and no runtime dirs exist → 'unknown'."""
        env = _clean_runtime_env()
        with (
            patch.dict(os.environ, env, clear=True),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
        ):
            assert detect_active_runtime() == RUNTIME_UNKNOWN

    def test_claude_env_var_detected(self) -> None:
        """CLAUDE_CODE_SESSION env var → 'claude'."""
        env = _clean_runtime_env()
        env["CLAUDE_CODE_SESSION"] = "abc123"
        with patch.dict(os.environ, env, clear=True):
            assert detect_active_runtime() == RUNTIME_CLAUDE

    def test_codex_env_var_detected(self) -> None:
        """CODEX_SESSION env var → 'codex'."""
        env = _clean_runtime_env()
        env["CODEX_SESSION"] = "xyz"
        with patch.dict(os.environ, env, clear=True):
            assert detect_active_runtime() == RUNTIME_CODEX

    def test_explicit_gpd_runtime_override_detected(self) -> None:
        """GPD_ACTIVE_RUNTIME env var → canonical runtime."""
        env = _clean_runtime_env()
        env["GPD_ACTIVE_RUNTIME"] = "Codex"
        with patch.dict(os.environ, env, clear=True):
            assert detect_active_runtime() == RUNTIME_CODEX

    def test_gemini_env_var_detected(self) -> None:
        """GEMINI_CLI env var → 'gemini'."""
        env = _clean_runtime_env()
        env["GEMINI_CLI"] = "1"
        with patch.dict(os.environ, env, clear=True):
            assert detect_active_runtime() == RUNTIME_GEMINI

    def test_opencode_env_var_detected(self) -> None:
        """OPENCODE_SESSION env var → 'opencode'."""
        env = _clean_runtime_env()
        env["OPENCODE_SESSION"] = "sess"
        with patch.dict(os.environ, env, clear=True):
            assert detect_active_runtime() == RUNTIME_OPENCODE

    def test_env_var_takes_priority_over_dirs(self, tmp_path: Path) -> None:
        """Env var signal wins even if multiple runtime dirs exist."""
        # Create codex dir but set claude env var
        (tmp_path / ".codex").mkdir()
        env = _clean_runtime_env()
        env["CLAUDE_CODE"] = "1"
        with (
            patch.dict(os.environ, env, clear=True),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=tmp_path),
        ):
            assert detect_active_runtime() == RUNTIME_CLAUDE

    def test_multiple_dirs_picks_first_in_priority(self, tmp_path: Path) -> None:
        """When multiple runtime dirs exist, picks first in priority order (claude > codex > gemini > opencode)."""
        (tmp_path / ".codex").mkdir()
        (tmp_path / ".gemini").mkdir()
        # No .claude dir → codex is first match in ALL_RUNTIMES priority

        env = _clean_runtime_env()
        with (
            patch.dict(os.environ, env, clear=True),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
        ):
            assert detect_active_runtime() == RUNTIME_CODEX

    def test_claude_dir_wins_over_codex(self, tmp_path: Path) -> None:
        """When both .claude and .codex exist, .claude wins (first in priority)."""
        (tmp_path / ".claude").mkdir()
        (tmp_path / ".codex").mkdir()

        env = _clean_runtime_env()
        with (
            patch.dict(os.environ, env, clear=True),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=tmp_path),
        ):
            assert detect_active_runtime() == RUNTIME_CLAUDE

    def test_only_opencode_dir(self, tmp_path: Path) -> None:
        """When only .config/opencode exists, detects opencode."""
        oc_dir = tmp_path / ".config" / "opencode"
        oc_dir.mkdir(parents=True)

        env = _clean_runtime_env()
        with (
            patch.dict(os.environ, env, clear=True),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
        ):
            assert detect_active_runtime() == RUNTIME_OPENCODE

    def test_multiple_env_vars_first_wins(self) -> None:
        """When multiple env vars set, first in signal list wins (claude > codex)."""
        env = _clean_runtime_env()
        env["CLAUDE_CODE_SESSION"] = "1"
        env["CODEX_SESSION"] = "1"
        with patch.dict(os.environ, env, clear=True):
            assert detect_active_runtime() == RUNTIME_CLAUDE

    def test_explicit_cwd_overrides_process_cwd_for_runtime_detection(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / ".gemini").mkdir()

        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        (elsewhere / ".claude").mkdir()

        env = _clean_runtime_env()
        with (
            patch.dict(os.environ, env, clear=True),
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=elsewhere),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=tmp_path / "home"),
        ):
            assert detect_active_runtime(cwd=workspace) == RUNTIME_GEMINI

    def test_local_runtime_dirs_outrank_global_runtime_dirs(self, tmp_path: Path) -> None:
        """Local runtime detection wins even when the global runtime has higher name priority."""
        home = tmp_path / "home"
        (tmp_path / ".gemini").mkdir()
        (home / ".claude").mkdir(parents=True)

        env = _clean_runtime_env()
        with (
            patch.dict(os.environ, env, clear=True),
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
        ):
            assert detect_active_runtime() == RUNTIME_GEMINI


class TestResolveEffectiveRuntime:
    def test_reports_env_source(self) -> None:
        env = _clean_runtime_env()
        env["CODEX_SESSION"] = "xyz"
        with patch.dict(os.environ, env, clear=True):
            result = resolve_effective_runtime()

        assert result.runtime == RUNTIME_CODEX
        assert result.source == SOURCE_ENV

    def test_reports_local_source_and_install_scope(self, tmp_path: Path) -> None:
        _mark_gpd_install(tmp_path / ".gemini")

        env = _clean_runtime_env()
        with (
            patch.dict(os.environ, env, clear=True),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=tmp_path / "home"),
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
        ):
            result = resolve_effective_runtime()

        assert result.runtime == RUNTIME_GEMINI
        assert result.source == SOURCE_LOCAL
        assert result.has_gpd_install is True
        assert result.install_scope == SCOPE_LOCAL

    def test_reports_global_source_without_install(self, tmp_path: Path) -> None:
        (tmp_path / "home" / ".claude").mkdir(parents=True)
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        env = _clean_runtime_env()
        with (
            patch.dict(os.environ, env, clear=True),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=tmp_path / "home"),
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=workspace),
        ):
            result = resolve_effective_runtime()

        assert result.runtime == RUNTIME_CLAUDE
        assert result.source == SOURCE_GLOBAL
        assert result.has_gpd_install is False

    def test_require_gpd_install_returns_unknown_when_runtime_has_no_install(self, tmp_path: Path) -> None:
        (tmp_path / ".codex").mkdir()

        env = _clean_runtime_env()
        with (
            patch.dict(os.environ, env, clear=True),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=tmp_path / "home"),
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
        ):
            result = resolve_effective_runtime(require_gpd_install=True)

        assert result.runtime == RUNTIME_UNKNOWN


class TestDetectActiveRuntimeWithInstall:
    """Tests for the install-aware runtime detection helper used by hooks."""

    def test_plain_runtime_dirs_without_gpd_install_do_not_count(self, tmp_path: Path) -> None:
        (tmp_path / ".claude").mkdir()
        (tmp_path / ".codex").mkdir()
        (tmp_path / ".gemini").mkdir()
        (tmp_path / ".config" / "opencode").mkdir(parents=True)

        env = _clean_runtime_env()
        with (
            patch.dict(os.environ, env, clear=True),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
        ):
            assert detect_active_runtime_with_gpd_install() == RUNTIME_UNKNOWN

    def test_installed_runtime_is_detected(self, tmp_path: Path) -> None:
        _mark_gpd_install(tmp_path / ".codex")

        env = _clean_runtime_env()
        with (
            patch.dict(os.environ, env, clear=True),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
        ):
            assert detect_active_runtime_with_gpd_install() == RUNTIME_CODEX

    def test_higher_priority_runtime_without_install_does_not_mask_lower_installed_runtime(self, tmp_path: Path) -> None:
        (tmp_path / ".claude").mkdir()
        _mark_gpd_install(tmp_path / ".codex")

        env = _clean_runtime_env()
        with (
            patch.dict(os.environ, env, clear=True),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
        ):
            assert detect_active_runtime_with_gpd_install() == RUNTIME_CODEX


class TestDetectRuntimeForGpdUse:
    """Tests for the install-aware runtime selection used by GPD-owned surfaces."""

    def test_prefers_installed_runtime_over_uninstalled_higher_priority_runtime(self, tmp_path: Path) -> None:
        (tmp_path / ".claude").mkdir()
        _mark_gpd_install(tmp_path / ".codex")

        env = _clean_runtime_env()
        with (
            patch.dict(os.environ, env, clear=True),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
        ):
            assert detect_runtime_for_gpd_use() == RUNTIME_CODEX

    def test_falls_back_to_plain_active_runtime_when_no_install_is_found(self, tmp_path: Path) -> None:
        (tmp_path / ".gemini").mkdir()

        env = _clean_runtime_env()
        with (
            patch.dict(os.environ, env, clear=True),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=tmp_path / "home"),
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
        ):
            assert detect_runtime_for_gpd_use() == RUNTIME_GEMINI

    def test_explicit_target_install_is_detected_for_gpd_surfaces(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        home = tmp_path / "home"
        custom_dir = tmp_path / "custom-codex"
        _mark_gpd_install(custom_dir)
        _write_install_manifest(custom_dir, install_scope=SCOPE_LOCAL)

        env = _clean_runtime_env()
        env["CODEX_CONFIG_DIR"] = str(custom_dir)
        with patch.dict(os.environ, env, clear=True):
            assert detect_runtime_for_gpd_use(cwd=workspace, home=home) == RUNTIME_CODEX

    def test_explicit_runtime_override_wins_when_multiple_installed_runtimes_exist(self, tmp_path: Path) -> None:
        _mark_gpd_install(tmp_path / ".claude")
        _mark_gpd_install(tmp_path / ".codex")

        env = _clean_runtime_env()
        env["GPD_ACTIVE_RUNTIME"] = "codex"
        with (
            patch.dict(os.environ, env, clear=True),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
        ):
            assert detect_runtime_for_gpd_use() == RUNTIME_CODEX

# ─── all_runtime_dirs ──────────────────────────────────────────────────────


class TestAllRuntimeDirs:
    """Tests for all_runtime_dirs."""

    def test_returns_all_four_dirs(self) -> None:
        with patch.dict(os.environ, _clean_runtime_env(), clear=True):
            dirs = all_runtime_dirs()

            assert len(dirs) == 4
            home = Path.home()
            assert home / ".claude" in dirs
            assert home / ".codex" in dirs
            assert home / ".gemini" in dirs
            assert home / ".config" / "opencode" in dirs

    def test_uses_env_override_paths(self, tmp_path: Path) -> None:
        home = tmp_path / "home"
        env = {
            "CLAUDE_CONFIG_DIR": str(tmp_path / "claude-custom"),
            "CODEX_CONFIG_DIR": str(tmp_path / "codex-custom"),
            "GEMINI_CONFIG_DIR": str(tmp_path / "gemini-custom"),
            "OPENCODE_CONFIG_DIR": str(tmp_path / "opencode-custom"),
        }
        with (
            patch.dict(os.environ, env, clear=False),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
        ):
            dirs = all_runtime_dirs()

        assert tmp_path / "claude-custom" in dirs
        assert tmp_path / "codex-custom" in dirs
        assert tmp_path / "gemini-custom" in dirs
        assert tmp_path / "opencode-custom" in dirs


# ─── get_todo_dirs / get_cache_dirs ────────────────────────────────────────


class TestHelperDirs:
    """Tests for get_todo_dirs and get_cache_dirs."""

    def test_todo_dirs_include_local_and_global_runtime_paths(self, tmp_path: Path) -> None:
        home = tmp_path / "home"
        with (
            patch.dict(os.environ, _clean_runtime_env(), clear=True),
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
        ):
            dirs = get_todo_dirs()

        assert all(d.name == "todos" for d in dirs)
        assert len(dirs) == 8
        assert tmp_path / ".codex" / "todos" in dirs
        assert tmp_path / ".opencode" / "todos" in dirs
        assert home / ".codex" / "todos" in dirs
        assert home / ".config" / "opencode" / "todos" in dirs

    def test_cache_dirs_include_local_and_global_runtime_paths(self, tmp_path: Path) -> None:
        home = tmp_path / "home"
        with (
            patch.dict(os.environ, _clean_runtime_env(), clear=True),
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
        ):
            dirs = get_cache_dirs()

        assert all(d.name == "cache" for d in dirs)
        assert len(dirs) == 8
        assert tmp_path / ".claude" / "cache" in dirs
        assert tmp_path / ".opencode" / "cache" in dirs
        assert home / ".claude" / "cache" in dirs
        assert home / ".config" / "opencode" / "cache" in dirs

    def test_todo_dirs_use_explicit_workspace_cwd(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        home = tmp_path / "home"
        workspace.mkdir()

        with patch.dict(os.environ, _clean_runtime_env(), clear=True):
            dirs = get_todo_dirs(cwd=workspace, home=home)

        assert workspace / ".claude" / "todos" in dirs
        assert workspace / ".codex" / "todos" in dirs
        assert home / ".claude" / "todos" in dirs
        assert home / ".config" / "opencode" / "todos" in dirs

    def test_todo_dirs_can_prioritize_active_runtime(self, tmp_path: Path) -> None:
        home = tmp_path / "home"
        env = _clean_runtime_env()
        env["CODEX_SESSION"] = "active"

        with (
            patch.dict(os.environ, env, clear=True),
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
        ):
            dirs = get_todo_dirs(prefer_active=True)

        assert dirs[0] == tmp_path / ".codex" / "todos"
        assert dirs[1] == home / ".codex" / "todos"

    def test_todo_dirs_prefer_installed_runtime_when_higher_priority_runtime_is_uninstalled(self, tmp_path: Path) -> None:
        home = tmp_path / "home"
        (tmp_path / ".claude").mkdir()
        _mark_gpd_install(tmp_path / ".codex")

        with (
            patch.dict(os.environ, _clean_runtime_env(), clear=True),
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
        ):
            dirs = get_todo_dirs(prefer_active=True)

        assert dirs[0] == tmp_path / ".codex" / "todos"
        assert dirs[1] == home / ".codex" / "todos"

    def test_todo_candidates_prioritize_explicit_target_install(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        home = tmp_path / "home"
        custom_dir = tmp_path / "custom-codex"
        _mark_gpd_install(custom_dir)
        _write_install_manifest(custom_dir, install_scope=SCOPE_LOCAL)

        env = _clean_runtime_env()
        env["CODEX_CONFIG_DIR"] = str(custom_dir)
        with patch.dict(os.environ, env, clear=True):
            candidates = get_todo_candidates(cwd=workspace, home=home, preferred_runtime=RUNTIME_UNKNOWN)

        assert candidates[0].path == custom_dir / "todos"
        assert candidates[0].runtime == RUNTIME_CODEX
        assert candidates[0].scope == SCOPE_LOCAL


class TestDetectInstallScope:
    """Tests for local/global install-scope detection."""

    def test_prefers_local_scope_when_local_runtime_dir_exists(self, tmp_path: Path) -> None:
        home = tmp_path / "home"
        (tmp_path / ".codex").mkdir()
        (home / ".codex").mkdir(parents=True)
        (tmp_path / ".codex" / "get-physics-done").mkdir(parents=True)

        with (
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
        ):
            assert detect_install_scope(RUNTIME_CODEX) == SCOPE_LOCAL

    def test_returns_global_scope_when_only_global_runtime_dir_exists(self, tmp_path: Path) -> None:
        home = tmp_path / "home"
        (home / ".gemini").mkdir(parents=True)
        (home / ".gemini" / "get-physics-done").mkdir(parents=True)

        with (
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
        ):
            assert detect_install_scope(RUNTIME_GEMINI) == SCOPE_GLOBAL

    def test_manifest_scope_overrides_env_global_dir_for_explicit_target(self, tmp_path: Path) -> None:
        custom_dir = tmp_path / "custom-codex"
        custom_dir.mkdir()
        (custom_dir / "gpd-file-manifest.json").write_text(
            json.dumps({"install_scope": SCOPE_LOCAL}),
            encoding="utf-8",
        )

        elsewhere = tmp_path / "workspace"
        elsewhere.mkdir()
        home = tmp_path / "home"

        with (
            patch.dict(os.environ, {"CODEX_CONFIG_DIR": str(custom_dir)}, clear=False),
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=elsewhere),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
        ):
            assert detect_install_scope(RUNTIME_CODEX) == SCOPE_LOCAL

    def test_ignores_workspace_runtime_dir_without_gpd_install_when_global_install_exists(self, tmp_path: Path) -> None:
        home = tmp_path / "home"
        (tmp_path / ".codex").mkdir()
        global_dir = home / ".codex"
        global_dir.mkdir(parents=True)
        (global_dir / "gpd-file-manifest.json").write_text(
            json.dumps({"install_scope": SCOPE_GLOBAL}),
            encoding="utf-8",
        )

        with (
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
        ):
            assert detect_install_scope(RUNTIME_CODEX) == SCOPE_GLOBAL

    def test_returns_none_when_runtime_dirs_have_no_gpd_install_markers(self, tmp_path: Path) -> None:
        home = tmp_path / "home"
        (tmp_path / ".claude").mkdir()
        (home / ".claude").mkdir(parents=True)

        with (
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
        ):
            assert detect_install_scope(RUNTIME_CLAUDE) is None


# ─── get_gpd_install_dirs ──────────────────────────────────────────────────


class TestGPDInstallDirs:
    """Tests for get_gpd_install_dirs."""

    def test_returns_both_local_and_global(self, tmp_path: Path) -> None:
        home = tmp_path / "home"
        with (
            patch.dict(os.environ, _clean_runtime_env(), clear=True),
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
        ):
            dirs = get_gpd_install_dirs()

        # 4 runtimes × 2 locations (cwd + home) = 8
        assert len(dirs) == 8
        assert all("get-physics-done" in str(d) for d in dirs)
        assert tmp_path / ".opencode" / "get-physics-done" in dirs
        assert home / ".config" / "opencode" / "get-physics-done" in dirs

    def test_prefers_env_override_global_dirs(self, tmp_path: Path) -> None:
        home = tmp_path / "home"
        env = {
            "CLAUDE_CONFIG_DIR": str(tmp_path / "claude-custom"),
            "CODEX_CONFIG_DIR": str(tmp_path / "codex-custom"),
            "GEMINI_CONFIG_DIR": str(tmp_path / "gemini-custom"),
            "OPENCODE_CONFIG_DIR": str(tmp_path / "opencode-custom"),
        }
        with (
            patch.dict(os.environ, env, clear=False),
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
        ):
            dirs = get_gpd_install_dirs()

        assert tmp_path / "claude-custom" / "get-physics-done" in dirs
        assert tmp_path / "codex-custom" / "get-physics-done" in dirs
        assert tmp_path / "gemini-custom" / "get-physics-done" in dirs
        assert tmp_path / "opencode-custom" / "get-physics-done" in dirs

    def test_prefer_active_uses_installed_runtime_when_higher_priority_runtime_is_uninstalled(self, tmp_path: Path) -> None:
        home = tmp_path / "home"
        (tmp_path / ".claude").mkdir()
        _mark_gpd_install(tmp_path / ".codex")

        with (
            patch.dict(os.environ, _clean_runtime_env(), clear=True),
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
        ):
            dirs = get_gpd_install_dirs(prefer_active=True)

        assert dirs[0] == tmp_path / ".codex" / "get-physics-done"
        assert dirs[1] == home / ".codex" / "get-physics-done"


class TestUpdateCacheFiles:
    """Tests for get_update_cache_files."""

    def test_preferred_runtime_uses_explicit_workspace_cwd(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        home = tmp_path / "home"
        workspace.mkdir()

        files = get_update_cache_files(cwd=workspace, home=home, preferred_runtime=RUNTIME_CODEX)

        assert files[0] == workspace / ".codex" / "cache" / "gpd-update-check.json"
        assert files[1] == home / ".codex" / "cache" / "gpd-update-check.json"

    def test_unknown_preferred_runtime_falls_back_to_detected_workspace_runtime(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        home = tmp_path / "home"
        workspace.mkdir()
        (workspace / ".codex" / "cache").mkdir(parents=True)
        (home / ".claude" / "cache").mkdir(parents=True)

        files = get_update_cache_files(cwd=workspace, home=home, preferred_runtime=RUNTIME_UNKNOWN)

        assert files[0] == workspace / ".codex" / "cache" / "gpd-update-check.json"
        assert files[1] == home / ".codex" / "cache" / "gpd-update-check.json"

    def test_unknown_preferred_runtime_uses_installed_runtime_for_gpd_surfaces(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        home = tmp_path / "home"
        workspace.mkdir()
        (workspace / ".claude" / "cache").mkdir(parents=True)
        _mark_gpd_install(workspace / ".codex")

        files = get_update_cache_files(cwd=workspace, home=home, preferred_runtime=RUNTIME_UNKNOWN)

        assert files[0] == workspace / ".codex" / "cache" / "gpd-update-check.json"
        assert files[1] == home / ".codex" / "cache" / "gpd-update-check.json"

    def test_explicit_target_install_is_prioritized_for_update_cache_lookup(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        home = tmp_path / "home"
        custom_dir = tmp_path / "custom-codex"
        _mark_gpd_install(custom_dir)
        _write_install_manifest(custom_dir, install_scope=SCOPE_LOCAL)

        env = _clean_runtime_env()
        env["CODEX_CONFIG_DIR"] = str(custom_dir)
        with patch.dict(os.environ, env, clear=True):
            files = get_update_cache_files(cwd=workspace, home=home, preferred_runtime=RUNTIME_UNKNOWN)

        assert files[0] == custom_dir / "cache" / "gpd-update-check.json"
        assert files[1] == workspace / ".codex" / "cache" / "gpd-update-check.json"


class TestUpdateCacheCandidates:
    """Tests for update-cache candidate filtering."""

    def test_candidate_from_wrong_scope_is_rejected_when_runtime_install_scope_is_known(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        home = tmp_path / "home"

        global_runtime_dir = home / ".codex"
        global_runtime_dir.mkdir(parents=True)
        (global_runtime_dir / "gpd-file-manifest.json").write_text(
            json.dumps({"install_scope": SCOPE_GLOBAL}),
            encoding="utf-8",
        )

        stale_local_candidate = UpdateCacheCandidate(
            workspace / ".codex" / "cache" / "gpd-update-check.json",
            runtime=RUNTIME_CODEX,
            scope=SCOPE_LOCAL,
        )
        live_global_candidate = UpdateCacheCandidate(
            global_runtime_dir / "cache" / "gpd-update-check.json",
            runtime=RUNTIME_CODEX,
            scope=SCOPE_GLOBAL,
        )

        with patch("gpd.hooks.runtime_detect.Path.home", return_value=home):
            assert should_consider_update_cache_candidate(stale_local_candidate, cwd=workspace, home=home) is False
            assert should_consider_update_cache_candidate(live_global_candidate, cwd=workspace, home=home) is True

    def test_candidate_listing_keeps_installed_scope_ahead_of_stale_other_scope(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        home = tmp_path / "home"
        (workspace / ".codex" / "cache").mkdir(parents=True)

        global_runtime_dir = home / ".codex"
        global_runtime_dir.mkdir(parents=True)
        (global_runtime_dir / "gpd-file-manifest.json").write_text(
            json.dumps({"install_scope": SCOPE_GLOBAL}),
            encoding="utf-8",
        )

        candidates = get_update_cache_candidates(cwd=workspace, home=home, preferred_runtime=RUNTIME_CODEX)

        assert candidates[0].runtime == RUNTIME_CODEX
        assert candidates[0].scope == SCOPE_GLOBAL
        assert candidates[1].runtime == RUNTIME_CODEX
        assert candidates[1].scope == SCOPE_LOCAL

    def test_candidate_from_default_path_is_rejected_when_explicit_target_serves_runtime(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        home = tmp_path / "home"
        custom_dir = tmp_path / "custom-codex"
        _mark_gpd_install(custom_dir)
        _write_install_manifest(custom_dir, install_scope=SCOPE_LOCAL)

        stale_local_candidate = UpdateCacheCandidate(
            workspace / ".codex" / "cache" / "gpd-update-check.json",
            runtime=RUNTIME_CODEX,
            scope=SCOPE_LOCAL,
        )
        explicit_target_candidate = UpdateCacheCandidate(
            custom_dir / "cache" / "gpd-update-check.json",
            runtime=RUNTIME_CODEX,
            scope=SCOPE_LOCAL,
        )

        env = _clean_runtime_env()
        env["CODEX_CONFIG_DIR"] = str(custom_dir)
        with patch.dict(os.environ, env, clear=True):
            assert should_consider_update_cache_candidate(stale_local_candidate, cwd=workspace, home=home) is False
            assert should_consider_update_cache_candidate(explicit_target_candidate, cwd=workspace, home=home) is True


class TestTodoCandidates:
    def test_candidate_from_wrong_scope_is_rejected_when_runtime_install_scope_is_known(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        home = tmp_path / "home"

        global_runtime_dir = home / ".codex"
        global_runtime_dir.mkdir(parents=True)
        (global_runtime_dir / "gpd-file-manifest.json").write_text(
            json.dumps({"install_scope": SCOPE_GLOBAL}),
            encoding="utf-8",
        )

        stale_local_candidate = TodoCandidate(
            workspace / ".codex" / "todos",
            runtime=RUNTIME_CODEX,
            scope=SCOPE_LOCAL,
        )
        live_global_candidate = TodoCandidate(
            global_runtime_dir / "todos",
            runtime=RUNTIME_CODEX,
            scope=SCOPE_GLOBAL,
        )

        with patch("gpd.hooks.runtime_detect.Path.home", return_value=home):
            assert should_consider_todo_candidate(stale_local_candidate, cwd=workspace, home=home) is False
            assert should_consider_todo_candidate(live_global_candidate, cwd=workspace, home=home) is True

    def test_candidate_from_default_path_is_rejected_when_explicit_target_serves_runtime(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        home = tmp_path / "home"
        custom_dir = tmp_path / "custom-codex"
        _mark_gpd_install(custom_dir)
        _write_install_manifest(custom_dir, install_scope=SCOPE_LOCAL)

        stale_local_candidate = TodoCandidate(
            workspace / ".codex" / "todos",
            runtime=RUNTIME_CODEX,
            scope=SCOPE_LOCAL,
        )
        explicit_target_candidate = TodoCandidate(
            custom_dir / "todos",
            runtime=RUNTIME_CODEX,
            scope=SCOPE_LOCAL,
        )

        env = _clean_runtime_env()
        env["CODEX_CONFIG_DIR"] = str(custom_dir)
        with patch.dict(os.environ, env, clear=True):
            assert should_consider_todo_candidate(stale_local_candidate, cwd=workspace, home=home) is False
            assert should_consider_todo_candidate(explicit_target_candidate, cwd=workspace, home=home) is True


class TestUpdateCommand:
    """Tests for update_command_for_runtime."""

    def test_known_runtime_commands_are_adapter_derived(self) -> None:
        for runtime in (RUNTIME_CLAUDE, RUNTIME_CODEX, RUNTIME_GEMINI, RUNTIME_OPENCODE):
            assert update_command_for_runtime(runtime) == get_adapter(runtime).update_command

    def test_unknown_runtime_uses_plain_bootstrap_command(self) -> None:
        assert update_command_for_runtime(RUNTIME_UNKNOWN) == "npx -y get-physics-done"

    def test_claude_runtime_uses_claude_flag(self) -> None:
        assert update_command_for_runtime(RUNTIME_CLAUDE).endswith(" --claude")

    def test_codex_runtime_uses_codex_flag(self) -> None:
        assert update_command_for_runtime(RUNTIME_CODEX).endswith(" --codex")

    def test_gemini_runtime_uses_gemini_flag(self) -> None:
        assert update_command_for_runtime(RUNTIME_GEMINI).endswith(" --gemini")

    def test_opencode_runtime_uses_opencode_flag(self) -> None:
        assert update_command_for_runtime(RUNTIME_OPENCODE).endswith(" --opencode")

    def test_local_scope_adds_local_flag(self) -> None:
        assert update_command_for_runtime(RUNTIME_CLAUDE, scope=SCOPE_LOCAL).endswith(" --claude --local")

    def test_global_scope_adds_global_flag(self) -> None:
        assert update_command_for_runtime(RUNTIME_OPENCODE, scope=SCOPE_GLOBAL).endswith(" --opencode --global")


# ─── _has_gpd_install ──────────────────────────────────────────────────────


class TestHasGpdInstall:
    """Tests for _has_gpd_install directory detection."""

    def test_returns_true_when_gpd_directory_exists(self, tmp_path: Path) -> None:
        """_has_gpd_install returns True when get-physics-done dir is present."""
        (tmp_path / "get-physics-done").mkdir()
        assert _has_gpd_install(tmp_path) is True

    def test_returns_false_when_gpd_directory_missing(self, tmp_path: Path) -> None:
        """_has_gpd_install returns False when get-physics-done dir is absent."""
        assert _has_gpd_install(tmp_path) is False
