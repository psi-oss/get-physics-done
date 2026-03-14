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

import json
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


def _make_checkout(tmp_path: Path, version: str = "9.9.9") -> Path:
    """Create a minimal GPD source checkout."""
    repo_root = tmp_path / "checkout"
    repo_root.mkdir(parents=True, exist_ok=True)
    (repo_root / "package.json").write_text(
        json.dumps(
            {
                "name": "get-physics-done",
                "version": version,
                "gpdPythonVersion": version,
            }
        ),
        encoding="utf-8",
    )
    (repo_root / "pyproject.toml").write_text(
        f'[project]\nname = "get-physics-done"\nversion = "{version}"\n',
        encoding="utf-8",
    )
    gpd_root = repo_root / "src" / "gpd"
    for subdir in ("commands", "agents", "hooks", "specs"):
        (gpd_root / subdir).mkdir(parents=True, exist_ok=True)
    return repo_root


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


def test_install_summary_lists_runtime_specific_help_for_multi_runtime_install(tmp_path: Path):
    """Multi-runtime installs should print runtime-specific help hints."""

    def mock_install_single(runtime_name, *, is_global, target_dir_override=None):
        return {
            "runtime": runtime_name,
            "commands": 5,
            "agents": 3,
            "target": str(tmp_path / runtime_name),
        }

    adapters = {
        "claude-code": MagicMock(display_name="Claude Code", help_command="/gpd:claude-help"),
        "gemini": MagicMock(display_name="Gemini CLI", help_command="/gpd:gemini-help"),
    }

    with (
        patch("gpd.cli._install_single_runtime", side_effect=mock_install_single),
        patch("gpd.adapters.get_adapter", side_effect=lambda runtime: adapters[runtime]),
    ):
        result = runner.invoke(app, ["install", "claude-code", "gemini", "--local"])

    assert result.exit_code == 0
    assert "Run the runtime-specific help command to see available commands:" in result.output
    assert "- Claude Code: /gpd:claude-help" in result.output
    assert "- Gemini CLI: /gpd:gemini-help" in result.output
    assert "Run /gpd:claude-help to see available commands." not in result.output


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


def test_install_raw_finalize_failure_not_reported_as_installed(tmp_path: Path):
    """A finalize_install failure must only surface in the failed list."""

    def mock_install_single(runtime_name, *, is_global, target_dir_override=None):
        return {"runtime": runtime_name, "commands": 5, "agents": 3, "target": str(tmp_path / runtime_name)}

    class FailingFinalizeAdapter:
        display_name = "Claude Code"
        help_command = "/gpd:help"

        def finalize_install(self, install_result, *, force_statusline=False):
            raise RuntimeError("finalize boom")

    with (
        patch("gpd.cli._install_single_runtime", side_effect=mock_install_single),
        patch("gpd.adapters.get_adapter", return_value=FailingFinalizeAdapter()),
    ):
        result = runner.invoke(app, ["--raw", "install", "claude-code", "--local"])

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["installed"] == []
    assert payload["failed"] == [{"runtime": "claude-code", "error": "finalize boom"}]


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


def test_install_single_runtime_prefers_checkout_source_tree(tmp_path: Path):
    """When invoked inside the repo, install should use that checkout's src/gpd tree."""
    from gpd.cli import _install_single_runtime

    checkout = _make_checkout(tmp_path, "9.9.9")
    captured_calls: list[dict[str, object]] = []

    class SpyAdapter:
        runtime_name = "claude-code"
        display_name = "Claude Code"
        config_dir_name = ".claude"
        help_command = "/gpd:help"

        def resolve_target_dir(self, is_global, cwd=None):
            return tmp_path / ".claude"

        def install(self, gpd_root, target_dir, *, is_global=False, explicit_target=False):
            captured_calls.append({"gpd_root": gpd_root, "target_dir": target_dir})
            return {"runtime": "claude-code", "commands": 0, "agents": 0}

        def finalize_install(self, install_result, *, force_statusline=False):
            return None

    with (
        patch("gpd.adapters.get_adapter", return_value=SpyAdapter()),
        patch("gpd.cli._get_cwd", return_value=checkout),
    ):
        _install_single_runtime("claude-code", is_global=False)

    assert len(captured_calls) == 1
    assert captured_calls[0]["gpd_root"] == checkout / "src" / "gpd"


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


def test_install_single_runtime_resolves_relative_target_dir_against_cli_cwd(tmp_path: Path):
    """Relative --target-dir should be anchored to --cwd, not the process cwd."""
    from gpd.cli import _install_single_runtime

    captured_calls: list[Path] = []
    cli_cwd = tmp_path / "workspace"
    cli_cwd.mkdir()

    class SpyAdapter:
        runtime_name = "claude-code"
        display_name = "Claude Code"
        config_dir_name = ".claude"
        help_command = "/gpd:help"

        def resolve_target_dir(self, is_global, cwd=None):
            return tmp_path / ".claude"

        def install(self, gpd_root, target_dir, *, is_global=False, explicit_target=False):
            captured_calls.append(target_dir)
            return {"runtime": "claude-code", "commands": 0, "agents": 0}

        def finalize_install(self, install_result, *, force_statusline=False):
            return None

    with (
        patch("gpd.adapters.get_adapter", return_value=SpyAdapter()),
        patch("gpd.cli._get_cwd", return_value=cli_cwd),
    ):
        _install_single_runtime("claude-code", is_global=False, target_dir_override="relative-target")

    assert captured_calls == [cli_cwd / "relative-target"]


def test_uninstall_resolves_relative_target_dir_against_cli_cwd(tmp_path: Path):
    """Relative uninstall --target-dir should be anchored to --cwd."""
    cli_cwd = tmp_path / "workspace"
    cli_cwd.mkdir()
    target = cli_cwd / "relative-target"
    target.mkdir()
    captured_targets: list[Path] = []

    class SpyAdapter:
        display_name = "Claude Code"

        def resolve_target_dir(self, is_global, cwd=None):
            return tmp_path / ".claude"

        def uninstall(self, target_dir):
            captured_targets.append(target_dir)
            return {"runtime": "claude-code", "removed": []}

    with (
        patch("gpd.adapters.get_adapter", return_value=SpyAdapter()),
        patch("gpd.cli._get_cwd", return_value=cli_cwd),
    ):
        result = runner.invoke(app, ["uninstall", "claude-code", "--target-dir", "relative-target"])

    assert result.exit_code == 0
    assert captured_targets == [target]


def test_install_interactive_rejects_ambiguous_runtime_name(tmp_path: Path):
    """Substring matches that hit multiple runtimes should fail closed."""
    with (
        patch("gpd.adapters.list_runtimes", return_value=["claude-code", "codex", "opencode"]),
        patch("gpd.adapters.get_adapter") as mock_get,
    ):
        adapters = {
            "claude-code": MagicMock(display_name="Claude Code", selection_aliases=("claude", "claude code")),
            "codex": MagicMock(display_name="Codex", selection_aliases=("codex",)),
            "opencode": MagicMock(display_name="OpenCode", selection_aliases=("opencode", "open code")),
        }
        mock_get.side_effect = lambda runtime: adapters[runtime]

        result = runner.invoke(app, ["install"], input="code\n")

    assert result.exit_code == 1
    assert "Ambiguous selection: 'code'" in result.output


def test_install_interactive_rejects_invalid_location_choice(tmp_path: Path):
    """Interactive location selection should reject invalid choices instead of defaulting to local."""

    def mock_install_single(runtime_name, *, is_global, target_dir_override=None):
        return {"runtime": runtime_name, "commands": 5, "agents": 3, "target": str(tmp_path / runtime_name)}

    with (
        patch("gpd.cli._install_single_runtime", side_effect=mock_install_single),
        patch("gpd.adapters.get_adapter") as mock_get,
        patch("gpd.adapters.list_runtimes", return_value=["claude-code"]),
    ):
        mock_adapter = MagicMock()
        mock_adapter.display_name = "Claude Code"
        mock_adapter.selection_aliases = ("claude", "claude code")
        mock_get.return_value = mock_adapter

        result = runner.invoke(app, ["install"], input="1\n9\n")

    assert result.exit_code == 1
    assert "Invalid selection: '9'" in result.output


@pytest.mark.parametrize(
    ("argv_suffix", "supported_runtimes", "expected_runtimes", "uses_target_dir"),
    [
        (["claude-code", "--local"], ["claude-code"], ["claude-code"], False),
        (["--all", "--local"], ["claude-code", "gemini"], ["claude-code", "gemini"], False),
        (["claude-code", "--local", "--force-statusline"], ["claude-code"], ["claude-code"], False),
        (["claude-code", "--local", "--target-dir", "__TARGET__"], ["claude-code"], ["claude-code"], True),
    ],
)
def test_install_local_option_never_forwards_global_scope(
    tmp_path: Path,
    argv_suffix: list[str],
    supported_runtimes: list[str],
    expected_runtimes: list[str],
    uses_target_dir: bool,
):
    """Every local install variant must forward is_global=False."""

    captured_calls: list[dict[str, object]] = []
    explicit_target = tmp_path / "custom-runtime-dir"
    argv = ["install", *[str(explicit_target) if token == "__TARGET__" else token for token in argv_suffix]]

    def mock_install_single(runtime_name, *, is_global, target_dir_override=None):
        captured_calls.append(
            {
                "runtime": runtime_name,
                "is_global": is_global,
                "target_dir_override": target_dir_override,
            }
        )
        return {"runtime": runtime_name, "commands": 5, "agents": 3, "target": str(tmp_path / runtime_name)}

    with (
        patch("gpd.cli._install_single_runtime", side_effect=mock_install_single),
        patch("gpd.adapters.get_adapter") as mock_get,
        patch("gpd.adapters.list_runtimes", return_value=supported_runtimes),
    ):
        mock_adapter = MagicMock()
        mock_adapter.display_name = "Test"
        mock_adapter.help_command = "/gpd:help"
        mock_get.return_value = mock_adapter

        result = runner.invoke(app, argv)

    assert result.exit_code == 0
    assert [call["runtime"] for call in captured_calls] == expected_runtimes
    assert all(call["is_global"] is False for call in captured_calls)
    if uses_target_dir:
        assert captured_calls[0]["target_dir_override"] == str(explicit_target)
    else:
        assert all(call["target_dir_override"] is None for call in captured_calls)


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


def test_install_rejects_explicit_runtimes_with_all() -> None:
    """`--all` cannot be combined with explicit runtime arguments on install."""
    with (
        patch("gpd.cli._install_single_runtime") as mock_install_single,
        patch("gpd.adapters.list_runtimes") as mock_list_runtimes,
    ):
        result = runner.invoke(app, ["install", "claude-code", "--all", "--local"])

    assert result.exit_code == 1
    assert "Cannot combine explicit runtimes with --all for install" in result.output
    mock_install_single.assert_not_called()
    mock_list_runtimes.assert_not_called()


def test_install_target_dir_rejects_multiple_runtimes(tmp_path: Path):
    """Explicit target dirs are only safe for a single runtime."""
    result = runner.invoke(
        app,
        ["install", "claude-code", "gemini", "--target-dir", str(tmp_path / "shared")],
    )

    assert result.exit_code == 1
    assert "--target-dir requires exactly one runtime for install" in result.output


def test_install_target_dir_rejects_all_runtimes(tmp_path: Path):
    """`--all` plus an explicit target dir is also unsafe."""
    with patch("gpd.adapters.list_runtimes", return_value=["claude-code", "gemini"]):
        result = runner.invoke(
            app,
            ["install", "--all", "--target-dir", str(tmp_path / "shared")],
        )

    assert result.exit_code == 1
    assert "--target-dir requires exactly one runtime for install" in result.output


def test_install_deduplicates_repeated_runtime_args(tmp_path: Path) -> None:
    """Repeated runtime args should only install once per runtime."""
    install_calls: list[str] = []

    def mock_install_single(runtime_name, *, is_global, target_dir_override=None):
        install_calls.append(runtime_name)
        return {"runtime": runtime_name, "commands": 5, "agents": 3, "target": str(tmp_path / ".claude")}

    with (
        patch("gpd.adapters.list_runtimes", return_value=["claude-code", "gemini"]),
        patch("gpd.cli._install_single_runtime", side_effect=mock_install_single),
        patch("gpd.adapters.get_adapter") as mock_get_adapter,
    ):
        mock_adapter = MagicMock()
        mock_adapter.display_name = "Claude Code"
        mock_adapter.help_command = "/gpd:help"
        mock_get_adapter.return_value = mock_adapter

        result = runner.invoke(app, ["install", "claude-code", "claude-code", "--local"])

    assert result.exit_code == 0
    assert install_calls == ["claude-code"]


def test_uninstall_global_and_local_conflict():
    """--global and --local together on uninstall errors."""
    result = runner.invoke(app, ["uninstall", "claude-code", "--global", "--local"])
    assert result.exit_code == 1
    assert "Cannot specify both" in result.output


def test_uninstall_rejects_explicit_runtimes_with_all() -> None:
    """`--all` cannot be combined with explicit runtime arguments on uninstall."""
    with (
        patch("gpd.adapters.get_adapter") as mock_get_adapter,
        patch("gpd.adapters.list_runtimes") as mock_list_runtimes,
    ):
        result = runner.invoke(app, ["uninstall", "claude-code", "--all", "--local"])

    assert result.exit_code == 1
    assert "Cannot combine explicit runtimes with --all for uninstall" in result.output
    mock_get_adapter.assert_not_called()
    mock_list_runtimes.assert_not_called()


def test_uninstall_target_dir_rejects_multiple_runtimes(tmp_path: Path):
    """Explicit target dirs are only safe for a single runtime on uninstall too."""
    result = runner.invoke(
        app,
        ["uninstall", "claude-code", "gemini", "--target-dir", str(tmp_path / "shared")],
        input="n\n",
    )

    assert result.exit_code == 1
    assert "--target-dir requires exactly one runtime for uninstall" in result.output


def test_uninstall_deduplicates_repeated_runtime_args(tmp_path: Path) -> None:
    """Repeated runtime args should only uninstall once per runtime."""
    target = tmp_path / "installed"
    target.mkdir()

    mock_adapter = MagicMock()
    mock_adapter.display_name = "Claude Code"
    mock_adapter.uninstall.return_value = {"removed": ["commands"]}

    with (
        patch("gpd.adapters.list_runtimes", return_value=["claude-code", "gemini"]),
        patch("gpd.adapters.get_adapter", return_value=mock_adapter),
    ):
        result = runner.invoke(
            app,
            ["--raw", "uninstall", "claude-code", "claude-code", "--target-dir", str(target)],
        )

    assert result.exit_code == 0
    mock_adapter.uninstall.assert_called_once_with(target)
