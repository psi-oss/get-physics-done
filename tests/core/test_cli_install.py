"""Tests for CLI install/uninstall edge cases.

Covers:
1. Install to non-existent directory — creates it
2. Upgrade over existing install — works correctly
3. --all with partial failures — continues and reports
4. Uninstall without manifest — graceful
5. Non-TTY interactive mode — uses defaults
6. --raw output — clean JSON, no rich text
7. is_global forwarded to adapters
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from gpd.cli import app

runner = CliRunner()


# ─── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture()
def gpd_root(tmp_path: Path) -> Path:
    """Minimal GPD package data directory for install tests."""
    root = tmp_path / "gpd_pkg"
    for d in ("commands", "agents", "hooks"):
        (root / d).mkdir(parents=True)
    (root / "commands" / "help.md").write_text(
        "---\nname: gpd:help\ndescription: Help\n---\nHelp body.\n",
        encoding="utf-8",
    )
    (root / "agents" / "gpd-verifier.md").write_text(
        "---\nname: gpd-verifier\ndescription: Verifier\n---\nVerifier body.\n",
        encoding="utf-8",
    )
    (root / "hooks" / "statusline.py").write_text("print('ok')\n", encoding="utf-8")
    (root / "hooks" / "check_update.py").write_text("print('ok')\n", encoding="utf-8")
    for subdir in ("references", "templates", "workflows"):
        d = root / "specs" / subdir
        d.mkdir(parents=True)
        (d / f"{subdir[:3]}.md").write_text(f"# {subdir}\n", encoding="utf-8")
    return root


# ─── 1. Install to non-existent directory ────────────────────────────────────


def test_install_creates_nonexistent_target_dir(gpd_root: Path, tmp_path: Path):
    """Install to a directory that doesn't exist yet — should create it."""
    target = tmp_path / "does" / "not" / "exist" / ".claude"
    assert not target.exists()

    from gpd.adapters.claude_code import ClaudeCodeAdapter

    adapter = ClaudeCodeAdapter()
    result = adapter.install(gpd_root, target)
    assert target.exists()
    assert (target / "commands" / "gpd").is_dir()
    assert result["commands"] >= 1


# ─── 2. Upgrade over existing install ────────────────────────────────────────


def test_install_upgrades_existing(gpd_root: Path, tmp_path: Path):
    """Install over an existing GPD install — replaces files correctly."""
    from gpd.adapters.claude_code import ClaudeCodeAdapter

    target = tmp_path / ".claude"
    adapter = ClaudeCodeAdapter()

    # First install
    result1 = adapter.install(gpd_root, target)
    assert result1["commands"] >= 1

    # Modify an installed file to simulate user edit
    commands_dir = target / "commands" / "gpd"
    first_md = next(commands_dir.rglob("*.md"))
    first_md.write_text("user modified content", encoding="utf-8")

    # Second install (upgrade)
    result2 = adapter.install(gpd_root, target)
    assert result2["commands"] >= 1

    # File should be overwritten by upgrade (atomic swap)
    content = first_md.read_text(encoding="utf-8")
    assert content != "user modified content"


# ─── 3. --all with partial failures ─────────────────────────────────────────


def test_install_all_continues_on_failure(tmp_path: Path):
    """--all install continues when some runtimes fail and sets exit code 1."""

    def mock_install_single(runtime_name, *, is_global, target_dir_override=None):
        if runtime_name == "claude-code":
            return {"runtime": "claude-code", "commands": 5, "agents": 3, "target": str(tmp_path)}
        raise RuntimeError(f"Simulated failure for {runtime_name}")

    with (
        patch("gpd.cli._install_single_runtime", side_effect=mock_install_single),
        patch("gpd.adapters.get_adapter") as mock_get,
    ):
        mock_adapter = MagicMock()
        mock_adapter.display_name = "Test"
        mock_get.return_value = mock_adapter

        result = runner.invoke(app, ["install", "--all", "--local"])

    # Should exit with code 1 because some runtimes failed
    assert result.exit_code == 1


def test_install_all_success_exits_0(tmp_path: Path):
    """--all install exits 0 when all runtimes succeed."""

    def mock_install_single(runtime_name, *, is_global, target_dir_override=None):
        return {"runtime": runtime_name, "commands": 5, "agents": 3, "target": str(tmp_path)}

    with (
        patch("gpd.cli._install_single_runtime", side_effect=mock_install_single),
        patch("gpd.adapters.get_adapter") as mock_get,
    ):
        mock_adapter = MagicMock()
        mock_adapter.display_name = "Test"
        mock_get.return_value = mock_adapter

        result = runner.invoke(app, ["install", "claude-code", "--local"])

    assert result.exit_code == 0


def test_install_banner_uses_display_names(tmp_path: Path):
    """Install banner should show human-friendly runtime names."""

    def mock_install_single(runtime_name, *, is_global, target_dir_override=None):
        return {"runtime": runtime_name, "commands": 5, "agents": 3, "target": str(tmp_path / ".claude")}

    with (
        patch("gpd.cli._install_single_runtime", side_effect=mock_install_single),
        patch("gpd.adapters.get_adapter") as mock_get,
    ):
        mock_adapter = MagicMock()
        mock_adapter.display_name = "Claude Code"
        mock_adapter.help_command = "/gpd:help"
        mock_get.return_value = mock_adapter

        result = runner.invoke(app, ["--cwd", str(tmp_path), "install", "claude-code", "--local"])

    assert result.exit_code == 0
    assert "Installing GPD (local) for: Claude Code" in result.output
    assert "Installing GPD (local) for: claude-code" not in result.output


def test_install_summary_formats_target_relative_to_cwd(tmp_path: Path):
    """Install summary should show a compact target path."""
    target = tmp_path / ".claude"

    def mock_install_single(runtime_name, *, is_global, target_dir_override=None):
        return {"runtime": runtime_name, "commands": 5, "agents": 3, "target": str(target)}

    with (
        patch("gpd.cli._install_single_runtime", side_effect=mock_install_single),
        patch("gpd.adapters.get_adapter") as mock_get,
    ):
        mock_adapter = MagicMock()
        mock_adapter.display_name = "Claude Code"
        mock_adapter.help_command = "/gpd:help"
        mock_get.return_value = mock_adapter

        result = runner.invoke(app, ["--cwd", str(tmp_path), "install", "claude-code", "--local"])

    assert result.exit_code == 0
    assert "./.claude" in result.output
    assert str(target) not in result.output


def test_install_summary_leaves_blank_line_after_help_hint(tmp_path: Path):
    """Install output should leave a blank line after the help hint."""
    target = tmp_path / ".claude"

    def mock_install_single(runtime_name, *, is_global, target_dir_override=None):
        return {"runtime": runtime_name, "commands": 5, "agents": 3, "target": str(target)}

    with (
        patch("gpd.cli._install_single_runtime", side_effect=mock_install_single),
        patch("gpd.adapters.get_adapter") as mock_get,
    ):
        mock_adapter = MagicMock()
        mock_adapter.display_name = "Claude Code"
        mock_adapter.help_command = "/gpd:help"
        mock_get.return_value = mock_adapter

        result = runner.invoke(app, ["--cwd", str(tmp_path), "install", "claude-code", "--local"])

    assert result.exit_code == 0
    assert "Run /gpd:help to see available commands.\n\n" in result.output


# ─── 4. Uninstall without manifest ──────────────────────────────────────────


def test_uninstall_no_manifest_graceful(tmp_path: Path):
    """Uninstall when no manifest exists — should not crash."""
    target = tmp_path / ".claude"
    target.mkdir()
    # Create some GPD files but no manifest
    gpd_dir = target / "get-physics-done"
    gpd_dir.mkdir()
    (gpd_dir / "test.md").write_text("test", encoding="utf-8")

    from gpd.adapters.claude_code import ClaudeCodeAdapter

    adapter = ClaudeCodeAdapter()
    result = adapter.uninstall(target)

    # Should succeed and report what was removed
    assert result["runtime"] == "claude-code"
    assert "get-physics-done/" in result["removed"]


def test_uninstall_empty_target_nothing_to_remove(tmp_path: Path):
    """Uninstall from an empty directory — gracefully reports nothing to remove."""
    target = tmp_path / ".claude"
    target.mkdir()

    from gpd.adapters.claude_code import ClaudeCodeAdapter

    adapter = ClaudeCodeAdapter()
    result = adapter.uninstall(target)

    assert result["runtime"] == "claude-code"
    assert result["removed"] == []


def test_uninstall_nonexistent_target_skips(tmp_path: Path):
    """Uninstall when target dir doesn't exist — skip with message."""
    result = runner.invoke(
        app,
        ["uninstall", "claude-code", "--local", "--target-dir", str(tmp_path / "nonexistent")],
    )
    assert result.exit_code == 0


# ─── 5. Non-TTY interactive mode ────────────────────────────────────────────


def test_install_no_args_uses_interactive_defaults(tmp_path: Path):
    """Install with no args enters interactive mode (defaults to choice 1 in CliRunner)."""

    def mock_install_single(runtime_name, *, is_global, target_dir_override=None):
        return {"runtime": runtime_name, "commands": 5, "agents": 3, "target": str(tmp_path)}

    with (
        patch("gpd.cli._install_single_runtime", side_effect=mock_install_single),
        patch("gpd.adapters.get_adapter") as mock_get,
    ):
        mock_adapter = MagicMock()
        mock_adapter.display_name = "Test"
        mock_get.return_value = mock_adapter

        # CliRunner provides input='1\n1\n' to simulate interactive choices
        result = runner.invoke(app, ["install"], input="1\n1\n")

    assert result.exit_code == 0


# ─── 6. --raw output ────────────────────────────────────────────────────────


def test_install_raw_outputs_json(tmp_path: Path):
    """--raw flag outputs clean JSON without rich formatting."""

    def mock_install_single(runtime_name, *, is_global, target_dir_override=None):
        return {"runtime": runtime_name, "commands": 5, "agents": 3, "target": str(tmp_path)}

    with (
        patch("gpd.cli._install_single_runtime", side_effect=mock_install_single),
        patch("gpd.adapters.get_adapter") as mock_get,
    ):
        mock_adapter = MagicMock()
        mock_adapter.display_name = "Claude Code"
        mock_get.return_value = mock_adapter

        result = runner.invoke(app, ["--raw", "install", "claude-code", "--local"])

    assert result.exit_code == 0
    # Output should contain valid JSON with "installed" key
    assert '"installed"' in result.output
    # Should NOT contain rich table formatting
    assert "Install Summary" not in result.output


def test_install_raw_includes_failures(tmp_path: Path):
    """--raw output includes both installed and failed runtimes."""
    call_count = 0

    def mock_install_single(runtime_name, *, is_global, target_dir_override=None):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return {"runtime": runtime_name, "commands": 5, "agents": 3, "target": str(tmp_path)}
        raise RuntimeError("boom")

    with (
        patch("gpd.cli._install_single_runtime", side_effect=mock_install_single),
        patch("gpd.adapters.get_adapter") as mock_get,
        patch("gpd.adapters.list_runtimes", return_value=["claude-code", "gemini"]),
    ):
        mock_adapter = MagicMock()
        mock_adapter.display_name = "Test"
        mock_get.return_value = mock_adapter

        result = runner.invoke(app, ["--raw", "install", "--all", "--local"])

    assert result.exit_code == 1
    # Should report both installed and failed
    assert '"installed"' in result.output
    assert '"failed"' in result.output


def test_uninstall_raw_outputs_json(tmp_path: Path):
    """--raw flag on uninstall outputs clean JSON."""
    target = tmp_path / ".claude"
    target.mkdir()

    result = runner.invoke(
        app,
        ["--raw", "uninstall", "claude-code", "--local", "--target-dir", str(target)],
    )

    assert result.exit_code == 0
    assert '"uninstalled"' in result.output


# ─── 7. is_global forwarding ────────────────────────────────────────────────


def test_install_single_runtime_passes_is_global(tmp_path: Path):
    """compute_path_prefix still distinguishes global vs local installs."""
    from gpd.adapters.install_utils import compute_path_prefix

    # Global install should produce absolute path prefix
    target = tmp_path / ".claude"
    global_prefix = compute_path_prefix(target, ".claude", is_global=True)
    assert global_prefix.startswith("/") or global_prefix.startswith("C:")  # absolute path
    assert not global_prefix.startswith("./")

    # Local install should produce relative path prefix
    local_prefix = compute_path_prefix(target, ".claude", is_global=False)
    assert local_prefix == "./.claude/"


def test_install_single_runtime_forwards_is_global(tmp_path: Path):
    """_install_single_runtime correctly calls adapter.install with is_global when supported."""
    from gpd.cli import _install_single_runtime

    captured_calls: list[dict[str, object]] = []

    class SpyAdapter:
        runtime_name = "claude-code"
        display_name = "Claude Code"
        config_dir_name = ".claude"
        help_command = "/gpd:help"

        def resolve_target_dir(self, is_global, cwd=None):
            return tmp_path / ".claude"

        def install(self, gpd_root, target_dir, *, is_global=False, explicit_target=False):
            captured_calls.append({"is_global": is_global, "explicit_target": explicit_target})
            return {"runtime": "claude-code", "commands": 0, "agents": 0}

        def finalize_install(self, install_result, *, force_statusline=False):
            return None

    with (
        patch("gpd.adapters.get_adapter", return_value=SpyAdapter()),
        patch("gpd.cli._get_cwd", return_value=tmp_path),
    ):
        _install_single_runtime("claude-code", is_global=True)

    assert len(captured_calls) == 1
    assert captured_calls[0]["is_global"] is True
    assert captured_calls[0]["explicit_target"] is False

    captured_calls.clear()
    with (
        patch("gpd.adapters.get_adapter", return_value=SpyAdapter()),
        patch("gpd.cli._get_cwd", return_value=tmp_path),
    ):
        _install_single_runtime("claude-code", is_global=False)

    assert len(captured_calls) == 1
    assert captured_calls[0]["is_global"] is False
    assert captured_calls[0]["explicit_target"] is False


def test_install_single_runtime_marks_explicit_target(tmp_path: Path):
    """_install_single_runtime forwards explicit_target when --target-dir is used."""
    from gpd.cli import _install_single_runtime

    captured_calls: list[dict[str, object]] = []
    target = tmp_path / "custom-runtime-dir"

    class SpyAdapter:
        runtime_name = "claude-code"
        display_name = "Claude Code"
        config_dir_name = ".claude"
        help_command = "/gpd:help"

        def resolve_target_dir(self, is_global, cwd=None):
            return tmp_path / ".claude"

        def install(self, gpd_root, target_dir, *, is_global=False, explicit_target=False):
            captured_calls.append(
                {
                    "is_global": is_global,
                    "explicit_target": explicit_target,
                    "target_dir": target_dir,
                }
            )
            return {"runtime": "claude-code", "commands": 0, "agents": 0}

        def finalize_install(self, install_result, *, force_statusline=False):
            return None

    with patch("gpd.adapters.get_adapter", return_value=SpyAdapter()):
        _install_single_runtime("claude-code", is_global=False, target_dir_override=str(target))

    assert len(captured_calls) == 1
    assert captured_calls[0]["is_global"] is False
    assert captured_calls[0]["explicit_target"] is True
    assert captured_calls[0]["target_dir"] == target


# ─── Validation edge cases ───────────────────────────────────────────────────


def test_install_unknown_runtime():
    """Install with an unknown runtime name errors."""
    result = runner.invoke(app, ["install", "nonexistent-runtime", "--local"])
    assert result.exit_code == 1
    assert "Unknown runtime" in result.output


def test_install_global_and_local_conflict():
    """--global and --local together errors."""
    result = runner.invoke(app, ["install", "claude-code", "--global", "--local"])
    assert result.exit_code == 1
    assert "Cannot specify both" in result.output


def test_uninstall_global_and_local_conflict():
    """--global and --local together on uninstall errors."""
    result = runner.invoke(app, ["uninstall", "claude-code", "--global", "--local"])
    assert result.exit_code == 1
    assert "Cannot specify both" in result.output
