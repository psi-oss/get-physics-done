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

from gpd.cli import _format_install_header_lines, _render_install_option_line, app

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


def test_format_install_header_lines_uses_psi_branding() -> None:
    """Interactive install header should use the branded PSI wording."""
    assert _format_install_header_lines("1.0.0") == (
        "GPD v1.0.0 - Get Physics Done",
        "© 2026 Physical Superintelligence PBC (PSI)",
    )


def test_render_install_option_line_uses_single_line_bracketed_layout() -> None:
    """Interactive install options should use the compact bracketed layout."""
    assert _render_install_option_line(1, "Claude Code", "claude-code", label_width=12).plain == (
        "  [1] Claude Code   · claude-code"
    )
    assert _render_install_option_line(1, "Local", "current project only", "./.claude", label_width=6).plain == (
        "  [1] Local   · current project only · ./.claude"
    )


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


def test_install_summary_leaves_blank_line_after_next_steps(tmp_path: Path):
    """Install output should leave a blank line after the next-steps block."""
    target = tmp_path / ".claude"

    def mock_install_single(runtime_name, *, is_global, target_dir_override=None):
        return {"runtime": runtime_name, "commands": 5, "agents": 3, "target": str(target)}

    with (
        patch("gpd.cli._install_single_runtime", side_effect=mock_install_single),
        patch("gpd.adapters.get_adapter") as mock_get,
    ):
        mock_adapter = MagicMock()
        mock_adapter.display_name = "Claude Code"
        mock_adapter.launch_command = "claude"
        mock_adapter.help_command = "/gpd:help"
        mock_adapter.new_project_command = "/gpd:new-project"
        mock_adapter.map_research_command = "/gpd:map-research"
        mock_get.return_value = mock_adapter

        result = runner.invoke(app, ["--cwd", str(tmp_path), "install", "claude-code", "--local"])

    assert result.exit_code == 0
    assert "Next steps" in result.output
    assert "1. Open Claude Code from your system terminal (claude)." in result.output
    assert "2. Run /gpd:help for the command list." in result.output
    assert (
        "3. Start with /gpd:new-project for a new project or /gpd:map-research for existing work.\n\n"
        in result.output
    )


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
        "claude-code": MagicMock(
            display_name="Claude Code",
            launch_command="claude",
            help_command="/gpd:claude-help",
            new_project_command="/gpd:claude-new-project",
            map_research_command="/gpd:claude-map-research",
        ),
        "gemini": MagicMock(
            display_name="Gemini CLI",
            launch_command="gemini",
            help_command="/gpd:gemini-help",
            new_project_command="/gpd:gemini-new-project",
            map_research_command="/gpd:gemini-map-research",
        ),
    }

    with (
        patch("gpd.cli._install_single_runtime", side_effect=mock_install_single),
        patch("gpd.adapters.get_adapter", side_effect=lambda runtime: adapters[runtime]),
    ):
        result = runner.invoke(app, ["install", "claude-code", "gemini", "--local"])

    assert result.exit_code == 0
    assert "Next steps" in result.output
    assert (
        "- Claude Code (claude), then /gpd:claude-help, then /gpd:claude-new-project or /gpd:claude-map-research"
        in result.output
    )
    assert (
        "- Gemini CLI (gemini), then /gpd:gemini-help, then /gpd:gemini-new-project or /gpd:gemini-map-research"
        in result.output
    )
    assert "1. From your system terminal" not in result.output


# ─── 4. Uninstall without manifest ──────────────────────────────────────────


def test_uninstall_rejects_manifestless_managed_surface(tmp_path: Path):
    """Uninstall refuses managed surfaces when ownership cannot be proven."""
    target = tmp_path / ".claude"
    target.mkdir()
    # Create some GPD files but no manifest
    gpd_dir = target / "get-physics-done"
    gpd_dir.mkdir()
    (gpd_dir / "test.md").write_text("test", encoding="utf-8")

    from gpd.adapters.claude_code import ClaudeCodeAdapter

    adapter = ClaudeCodeAdapter()
    with pytest.raises(RuntimeError, match="contains GPD artifacts but no manifest"):
        adapter.uninstall(target)


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


def test_uninstall_all_continues_after_one_runtime_failure(tmp_path: Path) -> None:
    """A failure in one runtime uninstall must not stop later runtimes."""

    removed_target = tmp_path / ".claude"
    removed_target.mkdir()
    failed_target = tmp_path / ".codex"
    failed_target.mkdir()

    claude_adapter = MagicMock()
    claude_adapter.display_name = "Claude Code"
    claude_adapter.resolve_target_dir.return_value = removed_target
    claude_adapter.uninstall.return_value = {"removed": ["commands"]}

    codex_adapter = MagicMock()
    codex_adapter.display_name = "Codex"
    codex_adapter.resolve_target_dir.return_value = failed_target
    codex_adapter.uninstall.side_effect = RuntimeError("boom")

    with (
        patch("gpd.adapters.list_runtimes", return_value=["claude-code", "codex"]),
        patch("gpd.adapters.get_adapter", side_effect=lambda runtime: claude_adapter if runtime == "claude-code" else codex_adapter),
    ):
        result = runner.invoke(app, ["uninstall", "--all", "--local"], input="y\n")

    assert result.exit_code == 1
    claude_adapter.uninstall.assert_called_once_with(removed_target)
    codex_adapter.uninstall.assert_called_once_with(failed_target)
    assert "boom" in result.output
    assert "Claude Code" in result.output
    assert "Codex" in result.output


def test_uninstall_raw_outputs_structured_outcomes(tmp_path: Path) -> None:
    """--raw uninstall should report removed, skipped, and failed outcomes explicitly."""

    removed_target = tmp_path / ".claude"
    removed_target.mkdir()
    failed_target = tmp_path / ".codex"
    failed_target.mkdir()
    skipped_target = tmp_path / ".gemini"

    claude_adapter = MagicMock()
    claude_adapter.display_name = "Claude Code"
    claude_adapter.resolve_target_dir.return_value = removed_target
    claude_adapter.uninstall.return_value = {"removed": ["commands", "agents"]}

    codex_adapter = MagicMock()
    codex_adapter.display_name = "Codex"
    codex_adapter.resolve_target_dir.return_value = failed_target
    codex_adapter.uninstall.side_effect = RuntimeError("boom")

    gemini_adapter = MagicMock()
    gemini_adapter.display_name = "Gemini CLI"
    gemini_adapter.resolve_target_dir.return_value = skipped_target
    gemini_adapter.uninstall.return_value = {"removed": []}

    with (
        patch("gpd.adapters.list_runtimes", return_value=["claude-code", "codex", "gemini"]),
        patch(
            "gpd.adapters.get_adapter",
            side_effect=lambda runtime: {
                "claude-code": claude_adapter,
                "codex": codex_adapter,
                "gemini": gemini_adapter,
            }[runtime],
        ),
    ):
        result = runner.invoke(app, ["--raw", "uninstall", "--all", "--local"])

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["uninstalled"] == [
        {
            "runtime": "claude-code",
            "status": "removed",
            "target": str(removed_target),
            "removed": ["commands", "agents"],
        },
        {
            "runtime": "codex",
            "status": "failed",
            "target": str(failed_target),
            "error": "boom",
        },
        {
            "runtime": "gemini",
            "status": "skipped",
            "target": str(skipped_target),
            "reason": f"not installed at {skipped_target.as_posix()}",
        },
    ]


def test_uninstall_raw_continues_after_adapter_lookup_failure(tmp_path: Path) -> None:
    removed_target = tmp_path / ".claude"
    removed_target.mkdir()

    claude_adapter = MagicMock()
    claude_adapter.display_name = "Claude Code"
    claude_adapter.resolve_target_dir.return_value = removed_target
    claude_adapter.uninstall.return_value = {"removed": ["commands"]}

    def fake_get_adapter(runtime: str):
        if runtime == "codex":
            raise RuntimeError("registry offline")
        return claude_adapter

    with (
        patch("gpd.adapters.list_runtimes", return_value=["codex", "claude-code"]),
        patch("gpd.adapters.get_adapter", side_effect=fake_get_adapter),
    ):
        result = runner.invoke(app, ["--raw", "uninstall", "--all", "--local"])

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["uninstalled"] == [
        {
            "runtime": "codex",
            "status": "failed",
            "target": "",
            "error": "Runtime adapter unavailable for 'codex' during uninstall: registry offline",
        },
        {
            "runtime": "claude-code",
            "status": "removed",
            "target": str(removed_target),
            "removed": ["commands"],
        },
    ]


# ─── 5. Non-TTY interactive mode ────────────────────────────────────────────


def test_install_no_args_uses_interactive_defaults(tmp_path: Path):
    """Install with no args enters interactive mode (defaults to choice 1 in CliRunner)."""

    def mock_install_single(runtime_name, *, is_global, target_dir_override=None):
        return {"runtime": runtime_name, "commands": 5, "agents": 3, "target": str(tmp_path)}

    with (
        patch("gpd.cli._install_single_runtime", side_effect=mock_install_single),
        patch("gpd.adapters.get_adapter") as mock_get,
        patch("gpd.adapters.list_runtimes", return_value=["claude-code"]),
    ):
        mock_adapter = MagicMock()
        mock_adapter.display_name = "Claude Code"
        mock_adapter.help_command = "/gpd:help"
        mock_adapter.resolve_target_dir.side_effect = (
            lambda is_global, cwd=None: tmp_path / (".claude-global" if is_global else ".claude")
        )
        mock_get.return_value = mock_adapter

        # CliRunner provides input='1\n1\n' to simulate interactive choices
        result = runner.invoke(app, ["install"], input="1\n1\n")

    assert result.exit_code == 0
    assert "GPD v" in result.output
    assert "© 2026 Physical Superintelligence PBC (PSI)" in result.output
    assert "[1] Claude Code" in result.output
    assert "· claude-code" in result.output
    assert "Enter choice [1]" in result.output
    assert "[1] Local" in result.output
    assert "· current project only ·" in result.output
    assert "Get Physics Done, by Physical Superintelligence PBC (PSI)" not in result.output
    assert "██████" in result.output


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
    payload = json.loads(result.output)
    assert payload["uninstalled"][0]["runtime"] == "claude-code"
    assert payload["uninstalled"][0]["status"] == "skipped"
    assert payload["uninstalled"][0]["target"] == str(target)
    assert payload["uninstalled"][0]["reason"] == "nothing to remove"
    assert payload["uninstalled"][0]["removed"] == []


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


def test_install_target_dir_preserves_explicit_global_scope(tmp_path: Path) -> None:
    """A global install should stay global even when a target dir is explicit."""
    captured_calls: list[dict[str, object]] = []
    target = tmp_path / "custom-runtime-dir"

    def mock_install_single(runtime_name, *, is_global, target_dir_override=None):
        captured_calls.append(
            {
                "runtime": runtime_name,
                "is_global": is_global,
                "target_dir_override": target_dir_override,
            }
        )
        return {"runtime": runtime_name, "commands": 5, "agents": 3, "target": str(target)}

    mock_adapter = MagicMock(
        display_name="Claude Code",
        help_command="/gpd:help",
        launch_command="claude",
        new_project_command="/gpd:new-project",
        map_research_command="/gpd:map-research",
    )

    with (
        patch("gpd.cli._install_single_runtime", side_effect=mock_install_single),
        patch("gpd.adapters.get_adapter", return_value=mock_adapter),
    ):
        result = runner.invoke(
            app,
            ["install", "Claude Code", "--global", "--target-dir", str(target)],
        )

    assert result.exit_code == 0
    assert captured_calls == [
        {
            "runtime": "claude-code",
            "is_global": True,
            "target_dir_override": str(target),
        }
    ]


def test_install_target_dir_uses_canonical_global_path_when_runtime_env_overrides_global_dir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Canonical global targets should stay global even when runtime env overrides drift."""
    from gpd.adapters import get_adapter
    from gpd.adapters.runtime_catalog import resolve_global_config_dir

    captured_calls: list[dict[str, object]] = []
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    override_dir = tmp_path / "override-global"
    override_dir.mkdir()

    runtime_name = "codex"
    adapter = get_adapter(runtime_name)
    descriptor = adapter.runtime_descriptor
    canonical_target = resolve_global_config_dir(descriptor, home=home, environ={})
    canonical_target.mkdir(parents=True)

    env_var = descriptor.global_config.env_var or descriptor.global_config.env_dir_var or descriptor.global_config.env_file_var
    assert env_var is not None
    env_value = str(override_dir / "config.json") if env_var == descriptor.global_config.env_file_var else str(override_dir)
    monkeypatch.setenv(env_var, env_value)

    mock_adapter = MagicMock(
        runtime_descriptor=descriptor,
        display_name=adapter.display_name,
        help_command=adapter.help_command,
        launch_command=adapter.launch_command,
        new_project_command=adapter.new_project_command,
        map_research_command=adapter.map_research_command,
    )
    mock_adapter.finalize_install.return_value = None

    def mock_install_single(runtime_name, *, is_global, target_dir_override=None):
        captured_calls.append(
            {
                "runtime": runtime_name,
                "is_global": is_global,
                "target_dir_override": target_dir_override,
            }
        )
        return {"runtime": runtime_name, "commands": 5, "agents": 3, "target": str(canonical_target)}

    with (
        patch("gpd.cli._install_single_runtime", side_effect=mock_install_single),
        patch("gpd.adapters.get_adapter", return_value=mock_adapter),
        patch("gpd.cli._get_cwd", return_value=workspace),
        patch("gpd.cli.Path.home", return_value=home),
    ):
        result = runner.invoke(app, ["install", runtime_name, "--target-dir", str(canonical_target)])

    assert result.exit_code == 0, result.output
    assert captured_calls == [
        {
            "runtime": runtime_name,
            "is_global": True,
            "target_dir_override": str(canonical_target),
        }
    ]


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


def test_install_single_runtime_rejects_explicit_target_with_foreign_manifest(
    gpd_root: Path,
    tmp_path: Path,
) -> None:
    """Explicit target installs must not clean up a config dir owned by another runtime."""
    from gpd.adapters.claude_code import ClaudeCodeAdapter
    from gpd.cli import _install_single_runtime

    target = tmp_path / "shared-runtime-dir"
    target.mkdir()
    (target / "get-physics-done").mkdir()
    preserved = target / "get-physics-done" / "keep.md"
    preserved.write_text("preserve", encoding="utf-8")
    manifest_path = target / "gpd-file-manifest.json"
    manifest_path.write_text(
        json.dumps({"runtime": "gemini", "install_scope": "local", "explicit_target": True}),
        encoding="utf-8",
    )

    with (
        patch("gpd.adapters.get_adapter", return_value=ClaudeCodeAdapter()),
        patch("gpd.version.resolve_install_gpd_root", return_value=gpd_root),
        patch("gpd.cli._get_cwd", return_value=tmp_path),
    ):
        with pytest.raises(RuntimeError, match="Gemini CLI \\(`gemini`\\), not Claude Code \\(`claude-code`\\)"):
            _install_single_runtime("claude-code", is_global=False, target_dir_override=str(target))

    assert preserved.read_text(encoding="utf-8") == "preserve"
    assert json.loads(manifest_path.read_text(encoding="utf-8"))["runtime"] == "gemini"


def test_local_install_manifest_stays_non_explicit_outside_process_cwd(gpd_root: Path, tmp_path: Path):
    """Default local installs should not become explicit targets just because cwd differs."""
    from gpd.adapters.claude_code import ClaudeCodeAdapter
    from gpd.hooks.install_metadata import installed_update_command

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target = workspace / ".claude"

    adapter = ClaudeCodeAdapter()
    adapter.install(gpd_root, target, is_global=False, explicit_target=False)

    manifest = json.loads((target / "gpd-file-manifest.json").read_text(encoding="utf-8"))
    command = installed_update_command(target)

    assert manifest["install_scope"] == "local"
    assert manifest["install_target_dir"] == str(target)
    assert manifest["explicit_target"] is False
    assert command is not None
    assert "--local" in command
    assert "--target-dir" not in command


def test_hook_install_metadata_uses_adapter_detection_rules(tmp_path: Path):
    """Shared hook metadata should defer install detection checks to the owning adapter."""
    from gpd.hooks.install_metadata import config_dir_has_complete_install

    config_dir = tmp_path / ".claude"
    config_dir.mkdir()
    (config_dir / "get-physics-done").mkdir()
    (config_dir / "gpd-file-manifest.json").write_text(
        json.dumps({"runtime": "claude-code", "install_scope": "local"}),
        encoding="utf-8",
    )

    adapter = MagicMock()
    adapter.has_complete_install.return_value = False

    with patch("gpd.hooks.install_metadata.get_adapter", return_value=adapter):
        assert config_dir_has_complete_install(config_dir) is False

    adapter.has_complete_install.assert_called_once_with(config_dir)


def test_hook_install_metadata_rejects_codex_surface_missing_config_toml(tmp_path: Path):
    """A half-installed Codex tree should not count as complete just because markers exist."""
    from gpd.hooks.install_metadata import config_dir_has_complete_install

    config_dir = tmp_path / ".codex"
    config_dir.mkdir()
    (config_dir / "get-physics-done").mkdir()
    (config_dir / "gpd-file-manifest.json").write_text(
        json.dumps({"runtime": "codex", "install_scope": "local"}),
        encoding="utf-8",
    )

    assert config_dir_has_complete_install(config_dir) is False


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


def test_uninstall_rejects_target_dir_with_foreign_manifest(tmp_path: Path) -> None:
    """Explicit target uninstalls must not remove another runtime's install."""
    target = tmp_path / "shared-runtime-dir"
    target.mkdir()
    (target / "get-physics-done").mkdir()
    preserved = target / "get-physics-done" / "keep.md"
    preserved.write_text("preserve", encoding="utf-8")
    manifest_path = target / "gpd-file-manifest.json"
    manifest_path.write_text(
        json.dumps({"runtime": "gemini", "install_scope": "local", "explicit_target": True}),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["uninstall", "claude-code", "--target-dir", str(target)])

    assert result.exit_code == 1
    assert "Gemini CLI (`gemini`), not Claude Code (`claude-code`)" in result.output
    assert preserved.read_text(encoding="utf-8") == "preserve"
    assert json.loads(manifest_path.read_text(encoding="utf-8"))["runtime"] == "gemini"


def test_uninstall_rejects_target_dir_with_foreign_manifest_without_wrapping(tmp_path: Path) -> None:
    """Foreign-manifest ownership errors should stay stable under narrow terminals."""
    target = tmp_path / "shared-runtime-dir"
    target.mkdir()
    (target / "get-physics-done").mkdir()
    (target / "gpd-file-manifest.json").write_text(
        json.dumps({"runtime": "gemini", "install_scope": "local", "explicit_target": True}),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        ["uninstall", "claude-code", "--target-dir", str(target)],
        terminal_width=80,
    )

    assert result.exit_code == 1
    assert "Gemini CLI (`gemini`), not Claude Code (`claude-code`)" in result.output


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


def test_install_interactive_accepts_unique_fuzzy_runtime_name(tmp_path: Path):
    """A unique substring match should select that runtime and continue."""

    captured_calls: list[dict[str, object]] = []

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
        patch("gpd.adapters.list_runtimes", return_value=["claude-code", "codex", "opencode"]),
        patch("gpd.adapters.get_adapter") as mock_get,
    ):
        adapters = {
            "claude-code": MagicMock(display_name="Claude Code", selection_aliases=("claude", "claude code")),
            "codex": MagicMock(display_name="Codex", selection_aliases=("codex",)),
            "opencode": MagicMock(display_name="OpenCode", selection_aliases=("opencode", "open code")),
        }
        for adapter in adapters.values():
            adapter.help_command = "/gpd:help"
        mock_get.side_effect = lambda runtime: adapters[runtime]

        result = runner.invoke(app, ["install"], input="open\n1\n")

    assert result.exit_code == 0
    assert captured_calls == [
        {
            "runtime": "opencode",
            "is_global": False,
            "target_dir_override": None,
        }
    ]


def test_install_accepts_runtime_display_name_alias(tmp_path: Path) -> None:
    """Non-interactive install should accept runtime display-name aliases."""
    captured_calls: list[dict[str, object]] = []

    def mock_install_single(runtime_name, *, is_global, target_dir_override=None):
        captured_calls.append(
            {
                "runtime": runtime_name,
                "is_global": is_global,
                "target_dir_override": target_dir_override,
            }
        )
        return {"runtime": runtime_name, "commands": 5, "agents": 3, "target": str(tmp_path / runtime_name)}

    mock_adapter = MagicMock(
        display_name="Claude Code",
        help_command="/gpd:help",
        launch_command="claude",
        new_project_command="/gpd:new-project",
        map_research_command="/gpd:map-research",
    )

    with (
        patch("gpd.cli._install_single_runtime", side_effect=mock_install_single),
        patch("gpd.adapters.get_adapter", return_value=mock_adapter),
    ):
        result = runner.invoke(app, ["install", "Claude Code", "--local"])

    assert result.exit_code == 0
    assert captured_calls == [
        {
            "runtime": "claude-code",
            "is_global": False,
            "target_dir_override": None,
        }
    ]


def test_uninstall_accepts_runtime_selection_alias(tmp_path: Path) -> None:
    """Non-interactive uninstall should accept runtime selection aliases."""
    target = tmp_path / ".opencode"
    target.mkdir()
    captured_targets: list[Path] = []

    class SpyAdapter:
        display_name = "OpenCode"

        def uninstall(self, target_dir):
            captured_targets.append(target_dir)
            return {"runtime": "opencode", "removed": []}

    with patch("gpd.adapters.get_adapter", return_value=SpyAdapter()):
        result = runner.invoke(app, ["uninstall", "open code", "--target-dir", str(target)])

    assert result.exit_code == 0
    assert captured_targets == [target]


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
