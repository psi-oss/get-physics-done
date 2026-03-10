"""Tests for gpd/hooks/runtime_detect.py edge cases.

Covers: no runtime dirs, multiple runtime dirs, env var detection,
priority ordering, helper functions, and unknown runtime fallback.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

from gpd.hooks.runtime_detect import (
    RUNTIME_CLAUDE,
    RUNTIME_CODEX,
    RUNTIME_GEMINI,
    RUNTIME_OPENCODE,
    RUNTIME_UNKNOWN,
    all_runtime_dirs,
    detect_active_runtime,
    get_cache_dirs,
    get_gpd_install_dirs,
    get_todo_dirs,
    runtime_dir,
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


# ─── runtime_dir ───────────────────────────────────────────────────────────


class TestRuntimeDir:
    """Tests for runtime_dir helper."""

    def test_known_runtimes(self) -> None:
        home = Path.home()
        assert runtime_dir(RUNTIME_CLAUDE) == home / ".claude"
        assert runtime_dir(RUNTIME_CODEX) == home / ".codex"
        assert runtime_dir(RUNTIME_GEMINI) == home / ".gemini"
        assert runtime_dir(RUNTIME_OPENCODE) == home / ".config" / "opencode"

    def test_unknown_runtime_defaults_to_claude(self) -> None:
        """Unknown runtime string falls back to claude dir."""
        assert runtime_dir("nonexistent") == Path.home() / ".claude"

    def test_env_overrides_take_precedence(self, tmp_path: Path) -> None:
        env = {
            "CLAUDE_CONFIG_DIR": str(tmp_path / "claude-custom"),
            "CODEX_CONFIG_DIR": str(tmp_path / "codex-custom"),
            "GEMINI_CONFIG_DIR": str(tmp_path / "gemini-custom"),
            "OPENCODE_CONFIG_DIR": str(tmp_path / "opencode-custom"),
        }
        with patch.dict(os.environ, env, clear=False):
            assert runtime_dir(RUNTIME_CLAUDE) == tmp_path / "claude-custom"
            assert runtime_dir(RUNTIME_CODEX) == tmp_path / "codex-custom"
            assert runtime_dir(RUNTIME_GEMINI) == tmp_path / "gemini-custom"
            assert runtime_dir(RUNTIME_OPENCODE) == tmp_path / "opencode-custom"

    def test_opencode_config_file_env_resolves_parent_dir(self, tmp_path: Path) -> None:
        config_file = tmp_path / "custom-opencode" / "config.toml"
        with patch.dict(os.environ, {"OPENCODE_CONFIG": str(config_file)}, clear=False):
            assert runtime_dir(RUNTIME_OPENCODE) == config_file.parent


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


# ─── update_command_for_runtime ────────────────────────────────────────────


class TestUpdateCommand:
    """Tests for update_command_for_runtime."""

    def test_unknown_runtime(self) -> None:
        assert update_command_for_runtime(RUNTIME_UNKNOWN) == "npx -y github:physicalsuperintelligence/get-physics-done"

    def test_claude_runtime(self) -> None:
        assert (
            update_command_for_runtime(RUNTIME_CLAUDE)
            == "npx -y github:physicalsuperintelligence/get-physics-done --claude"
        )

    def test_codex_runtime(self) -> None:
        assert update_command_for_runtime(RUNTIME_CODEX) == "npx -y github:physicalsuperintelligence/get-physics-done --codex"

    def test_gemini_runtime(self) -> None:
        assert (
            update_command_for_runtime(RUNTIME_GEMINI)
            == "npx -y github:physicalsuperintelligence/get-physics-done --gemini"
        )

    def test_opencode_runtime(self) -> None:
        assert (
            update_command_for_runtime(RUNTIME_OPENCODE)
            == "npx -y github:physicalsuperintelligence/get-physics-done --opencode"
        )
