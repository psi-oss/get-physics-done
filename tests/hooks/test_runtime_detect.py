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
    RUNTIME_CLAUDE,
    RUNTIME_CODEX,
    RUNTIME_GEMINI,
    RUNTIME_OPENCODE,
    RUNTIME_UNKNOWN,
    SCOPE_GLOBAL,
    SCOPE_LOCAL,
    _has_gpd_install,
    all_runtime_dirs,
    detect_install_scope,
    detect_active_runtime,
    get_cache_dirs,
    get_gpd_install_dirs,
    get_todo_dirs,
    get_update_cache_files,
    update_command_for_runtime,
)

# ─── detect_active_runtime ─────────────────────────────────────────────────


class TestDetectActiveRuntime:
    """Tests for detect_active_runtime with various env/dir states."""

    def test_no_env_no_dirs_returns_unknown(self, tmp_path: Path) -> None:
        """When no env vars set and no runtime dirs exist → 'unknown'."""
        env = {k: v for k, v in os.environ.items() if not k.startswith(("CLAUDE_CODE", "CODEX", "GEMINI", "OPENCODE"))}
        with (
            patch.dict(os.environ, env, clear=True),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
        ):
            assert detect_active_runtime() == RUNTIME_UNKNOWN

    def test_claude_env_var_detected(self) -> None:
        """CLAUDE_CODE_SESSION env var → 'claude'."""
        env = {k: v for k, v in os.environ.items() if not k.startswith(("CLAUDE_CODE", "CODEX", "GEMINI", "OPENCODE"))}
        env["CLAUDE_CODE_SESSION"] = "abc123"
        with patch.dict(os.environ, env, clear=True):
            assert detect_active_runtime() == RUNTIME_CLAUDE

    def test_codex_env_var_detected(self) -> None:
        """CODEX_SESSION env var → 'codex'."""
        env = {k: v for k, v in os.environ.items() if not k.startswith(("CLAUDE_CODE", "CODEX", "GEMINI", "OPENCODE"))}
        env["CODEX_SESSION"] = "xyz"
        with patch.dict(os.environ, env, clear=True):
            assert detect_active_runtime() == RUNTIME_CODEX

    def test_gemini_env_var_detected(self) -> None:
        """GEMINI_CLI env var → 'gemini'."""
        env = {k: v for k, v in os.environ.items() if not k.startswith(("CLAUDE_CODE", "CODEX", "GEMINI", "OPENCODE"))}
        env["GEMINI_CLI"] = "1"
        with patch.dict(os.environ, env, clear=True):
            assert detect_active_runtime() == RUNTIME_GEMINI

    def test_opencode_env_var_detected(self) -> None:
        """OPENCODE_SESSION env var → 'opencode'."""
        env = {k: v for k, v in os.environ.items() if not k.startswith(("CLAUDE_CODE", "CODEX", "GEMINI", "OPENCODE"))}
        env["OPENCODE_SESSION"] = "sess"
        with patch.dict(os.environ, env, clear=True):
            assert detect_active_runtime() == RUNTIME_OPENCODE

    def test_env_var_takes_priority_over_dirs(self, tmp_path: Path) -> None:
        """Env var signal wins even if multiple runtime dirs exist."""
        # Create codex dir but set claude env var
        (tmp_path / ".codex").mkdir()
        env = {k: v for k, v in os.environ.items() if not k.startswith(("CLAUDE_CODE", "CODEX", "GEMINI", "OPENCODE"))}
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

        env = {k: v for k, v in os.environ.items() if not k.startswith(("CLAUDE_CODE", "CODEX", "GEMINI", "OPENCODE"))}
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

        env = {k: v for k, v in os.environ.items() if not k.startswith(("CLAUDE_CODE", "CODEX", "GEMINI", "OPENCODE"))}
        with (
            patch.dict(os.environ, env, clear=True),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=tmp_path),
        ):
            assert detect_active_runtime() == RUNTIME_CLAUDE

    def test_only_opencode_dir(self, tmp_path: Path) -> None:
        """When only .config/opencode exists, detects opencode."""
        oc_dir = tmp_path / ".config" / "opencode"
        oc_dir.mkdir(parents=True)

        env = {k: v for k, v in os.environ.items() if not k.startswith(("CLAUDE_CODE", "CODEX", "GEMINI", "OPENCODE"))}
        with (
            patch.dict(os.environ, env, clear=True),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
        ):
            assert detect_active_runtime() == RUNTIME_OPENCODE

    def test_multiple_env_vars_first_wins(self) -> None:
        """When multiple env vars set, first in signal list wins (claude > codex)."""
        env = {k: v for k, v in os.environ.items() if not k.startswith(("CLAUDE_CODE", "CODEX", "GEMINI", "OPENCODE"))}
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

        env = {k: v for k, v in os.environ.items() if not k.startswith(("CLAUDE_CODE", "CODEX", "GEMINI", "OPENCODE"))}
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

        env = {k: v for k, v in os.environ.items() if not k.startswith(("CLAUDE_CODE", "CODEX", "GEMINI", "OPENCODE"))}
        with (
            patch.dict(os.environ, env, clear=True),
            patch("gpd.hooks.runtime_detect.Path.cwd", return_value=tmp_path),
            patch("gpd.hooks.runtime_detect.Path.home", return_value=home),
        ):
            assert detect_active_runtime() == RUNTIME_GEMINI

# ─── all_runtime_dirs ──────────────────────────────────────────────────────


class TestAllRuntimeDirs:
    """Tests for all_runtime_dirs."""

    def test_returns_all_four_dirs(self) -> None:
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

        dirs = get_todo_dirs(cwd=workspace, home=home)

        assert workspace / ".claude" / "todos" in dirs
        assert workspace / ".codex" / "todos" in dirs
        assert home / ".claude" / "todos" in dirs
        assert home / ".config" / "opencode" / "todos" in dirs


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


class TestUpdateCacheFiles:
    """Tests for get_update_cache_files."""

    def test_preferred_runtime_uses_explicit_workspace_cwd(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        home = tmp_path / "home"
        workspace.mkdir()

        files = get_update_cache_files(cwd=workspace, home=home, preferred_runtime=RUNTIME_CODEX)

        assert files[0] == workspace / ".codex" / "cache" / "gpd-update-check.json"
        assert files[1] == home / ".codex" / "cache" / "gpd-update-check.json"


class TestUpdateCommand:
    """Tests for update_command_for_runtime."""

    def test_known_runtime_commands_are_adapter_derived(self) -> None:
        for runtime in (RUNTIME_CLAUDE, RUNTIME_CODEX, RUNTIME_GEMINI, RUNTIME_OPENCODE):
            assert update_command_for_runtime(runtime) == get_adapter(runtime).update_command

    def test_unknown_runtime_uses_plain_bootstrap_command(self) -> None:
        assert update_command_for_runtime(RUNTIME_UNKNOWN) == "npx -y get-physics-done@latest"

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
