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
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from gpd.adapters import get_adapter
from gpd.adapters.install_utils import MANIFEST_NAME
from gpd.adapters.runtime_catalog import iter_runtime_descriptors
from gpd.cli import _format_install_header_lines, _render_install_option_line, app
from gpd.core.health import CheckStatus, DoctorReport, HealthCheck, HealthSummary
from gpd.core.onboarding_surfaces import beginner_startup_ladder_text
from gpd.core.public_surface_contract import beginner_onboarding_hub_url
from gpd.core.surface_phrases import recovery_ladder_note
from tests.doc_surface_contracts import (
    assert_install_summary_runtime_follow_up_contract,
    assert_recovery_ladder_contract,
)


class _StableCliRunner(CliRunner):
    def invoke(self, *args, **kwargs):
        kwargs.setdefault("color", False)
        return super().invoke(*args, **kwargs)


runner = _StableCliRunner()

_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def _normalize_cli_output(text: str) -> str:
    return " ".join(_ANSI_ESCAPE_RE.sub("", text).split())


_INSTALL_TEST_DESCRIPTORS = iter_runtime_descriptors()
_PRIMARY_INSTALL_DESCRIPTOR = _INSTALL_TEST_DESCRIPTORS[0]
_SECONDARY_INSTALL_DESCRIPTOR = _INSTALL_TEST_DESCRIPTORS[1]
_TERTIARY_INSTALL_DESCRIPTOR = _INSTALL_TEST_DESCRIPTORS[2]
_ENV_OVERRIDE_INSTALL_DESCRIPTOR = next(
    descriptor
    for descriptor in _INSTALL_TEST_DESCRIPTORS
    if (
        descriptor.global_config.env_var
        or descriptor.global_config.env_dir_var
        or descriptor.global_config.env_file_var
    )
)


def _descriptors_with_uninstall_counter(tmp_path: Path, counter_name: str) -> tuple[object, ...]:
    matches: list[object] = []
    probe_root = tmp_path / "runtime-uninstall-counter-probe"
    for descriptor in _INSTALL_TEST_DESCRIPTORS:
        target = probe_root / descriptor.config_dir_name
        target.mkdir(parents=True, exist_ok=True)
        result = get_adapter(descriptor.runtime_name).uninstall(target)
        if counter_name in result:
            matches.append(descriptor)
    if not matches:
        raise AssertionError(f"Expected at least one runtime uninstall result to expose {counter_name!r}")
    return tuple(matches)


def _descriptor_with_selection_alias_fragment(fragment: str):
    matches = [
        descriptor
        for descriptor in _INSTALL_TEST_DESCRIPTORS
        if any(fragment in alias for alias in descriptor.selection_aliases)
    ]
    if len(matches) != 1:
        raise AssertionError(f"Expected exactly one runtime descriptor to match '{fragment}', got {len(matches)}")
    return matches[0]


def _descriptors_with_selection_alias_fragment(fragment: str) -> tuple:
    return tuple(
        descriptor
        for descriptor in _INSTALL_TEST_DESCRIPTORS
        if any(fragment in alias for alias in descriptor.selection_aliases)
    )


def _descriptor_with_spaced_selection_alias() -> tuple[object, str]:
    matches: list[tuple[object, str]] = []
    for descriptor in _INSTALL_TEST_DESCRIPTORS:
        normalized_display_name = descriptor.display_name.lower().replace("-", " ").replace("cli", "cli")
        alias = next(
            (
                item
                for item in descriptor.selection_aliases
                if " " in item and item != normalized_display_name and item != descriptor.runtime_name.replace("-", " ")
            ),
            None,
        )
        if alias is not None:
            matches.append((descriptor, alias))
    if len(matches) != 1:
        raise AssertionError(f"Expected exactly one runtime descriptor with a spaced alias, got {len(matches)}")
    return matches[0]


def _descriptor_with_runtime_selection_flag() -> tuple[object, str]:
    for descriptor in _INSTALL_TEST_DESCRIPTORS:
        flag_inputs = tuple(dict.fromkeys((descriptor.install_flag, *descriptor.selection_flags)))
        if flag_inputs:
            return descriptor, flag_inputs[0]
    raise AssertionError("Expected at least one runtime descriptor with a catalog selection flag")


def _install_target(tmp_path: Path, descriptor=_PRIMARY_INSTALL_DESCRIPTOR) -> Path:
    return tmp_path / descriptor.config_dir_name


def _install_nested_target(tmp_path: Path, descriptor=_PRIMARY_INSTALL_DESCRIPTOR) -> Path:
    return tmp_path / "does" / "not" / "exist" / descriptor.config_dir_name


def _install_adapter(descriptor=_PRIMARY_INSTALL_DESCRIPTOR):
    return get_adapter(descriptor.runtime_name)


def _install_adapter_surface(descriptor=_PRIMARY_INSTALL_DESCRIPTOR) -> dict[str, object]:
    adapter = _install_adapter(descriptor)
    return {
        "display_name": descriptor.display_name,
        "format_command": adapter.format_command,
        "launch_command": adapter.launch_command,
        "help_command": adapter.help_command,
        "new_project_command": adapter.new_project_command,
        "map_research_command": adapter.map_research_command,
        "selection_aliases": descriptor.selection_aliases,
    }


def _mock_install_adapter(descriptor=_PRIMARY_INSTALL_DESCRIPTOR, **overrides):
    surface = _install_adapter_surface(descriptor)
    surface.update(overrides)
    return MagicMock(**surface)


def _doctor_report(
    *,
    overall: CheckStatus = CheckStatus.OK,
    runtime: str | None = None,
    install_scope: str | None = None,
    target: str | None = None,
    checks: list[HealthCheck] | None = None,
) -> DoctorReport:
    report_checks = checks or [HealthCheck(status=CheckStatus.OK, label="Runtime Launcher")]
    fail_count = sum(1 for check in report_checks if check.status == CheckStatus.FAIL)
    warn_count = sum(1 for check in report_checks if check.status == CheckStatus.WARN)
    ok_count = sum(1 for check in report_checks if check.status == CheckStatus.OK)
    return DoctorReport(
        overall=overall,
        mode="runtime-readiness",
        runtime=runtime,
        install_scope=install_scope,
        target=target,
        summary=HealthSummary(ok=ok_count, warn=warn_count, fail=fail_count, total=len(report_checks)),
        checks=report_checks,
    )


@pytest.fixture(autouse=True)
def _mock_install_preflight_doctor(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_run_doctor(*args, **kwargs):
        target_dir = kwargs.get("target_dir")
        target_text = str(target_dir) if target_dir is not None else None
        return _doctor_report(
            runtime=kwargs.get("runtime"),
            install_scope=kwargs.get("install_scope"),
            target=target_text,
        )

    monkeypatch.setattr("gpd.core.health.run_doctor", _fake_run_doctor)


def _assert_install_return_state(target: Path, *, adapter) -> None:
    for relpath in adapter.install_verification_relpaths():
        assert (target / relpath).exists()


def _first_overwritable_installed_file(target: Path) -> Path:
    return next(
        path
        for path in target.rglob("*")
        if path.is_file() and path.name != "gpd-file-manifest.json" and "hooks" not in path.relative_to(target).parts
    )


def _assert_single_runtime_next_steps(
    output: str,
    descriptor=_PRIMARY_INSTALL_DESCRIPTOR,
) -> None:
    adapter = _install_adapter(descriptor)
    resume_work_command = adapter.format_command("resume-work")
    suggest_next_command = adapter.format_command("suggest-next")
    pause_work_command = adapter.format_command("pause-work")
    ordered_patterns = (
        re.escape("After install"),
        re.escape(f"Beginner path: {beginner_onboarding_hub_url()}"),
        re.escape(
            f"Runtime surface: Run {adapter.help_command} for the command list. "
            f"First-run order is {beginner_startup_ladder_text()}."
        ),
        re.escape(f"Selected runtime: {descriptor.display_name} ({adapter.launch_command});"),
        re.escape(f"help {adapter.help_command};"),
        re.escape(f"start {adapter.format_command('start')};"),
        re.escape(f"tour {adapter.format_command('tour')};"),
        re.escape(f"new work {adapter.new_project_command};"),
        re.escape(f"existing work {adapter.map_research_command}."),
        re.escape(f"Fast bootstrap: {adapter.new_project_command} --minimal; return later with {resume_work_command}. "),
        re.escape(
            recovery_ladder_note(
                resume_work_phrase=f"`{resume_work_command}`",
                suggest_next_phrase=f"`{suggest_next_command}`",
                pause_work_phrase=f"`{pause_work_command}`",
            )
        ),
        re.escape("Use gpd --help for local diagnostics and later setup."),
    )
    cursor = 0
    for pattern in ordered_patterns:
        match = re.search(pattern, output[cursor:], re.S)
        assert match, output
        cursor += match.end()
    assert "--local|--global" not in output
    assert beginner_startup_ladder_text() in output
    assert_install_summary_runtime_follow_up_contract(
        output,
        runtime_help_fragments=(f"Run {adapter.help_command} for the command list.",),
    )


def _assert_multi_runtime_next_step_line(output: str, descriptor) -> None:
    adapter = get_adapter(descriptor.runtime_name)
    pattern = re.compile(
        rf"- {re.escape(descriptor.display_name)}.*?"
        rf"{re.escape(adapter.launch_command)}.*?"
        rf"{re.escape(adapter.help_command)}.*?"
        rf"{re.escape(adapter.format_command('start'))}.*?"
        rf"{re.escape(adapter.format_command('tour'))}.*?"
        rf"{re.escape(adapter.new_project_command)}.*?"
        rf"{re.escape(adapter.map_research_command)}.*?"
        rf"{re.escape(adapter.format_command('resume-work'))}",
        re.S,
    )
    assert pattern.search(output), output
    assert re.search(r"Fast bootstrap: use .*? --minimal", output, re.S), output


def _assert_install_summary_recovery_contract(
    output: str,
    *,
    descriptor=_PRIMARY_INSTALL_DESCRIPTOR,
    runtime_specific: bool = False,
) -> None:
    if runtime_specific:
        resume_work_fragments = ("your runtime-specific `resume-work` command",)
        suggest_next_fragments = ("your runtime-specific `suggest-next` command",)
        pause_work_fragments = ("your runtime-specific `pause-work` command",)
    else:
        adapter = _install_adapter(descriptor)
        resume_work_fragments = (f"`{adapter.format_command('resume-work')}`",)
        suggest_next_fragments = (f"`{adapter.format_command('suggest-next')}`",)
        pause_work_fragments = (f"`{adapter.format_command('pause-work')}`",)

    assert_recovery_ladder_contract(
        output,
        resume_work_fragments=resume_work_fragments,
        suggest_next_fragments=suggest_next_fragments,
        pause_work_fragments=pause_work_fragments,
    )


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
    (root / "hooks" / "notify.py").write_text("print('ok')\n", encoding="utf-8")
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
    target = _install_nested_target(tmp_path)
    assert not target.exists()

    adapter = _install_adapter()
    result = adapter.install(gpd_root, target)
    assert target.exists()
    _assert_install_return_state(target, adapter=adapter)
    assert result["commands"] >= 1


# ─── 2. Upgrade over existing install ────────────────────────────────────────


def test_install_upgrades_existing(gpd_root: Path, tmp_path: Path):
    """Install over an existing GPD install — replaces files correctly."""
    target = _install_target(tmp_path)
    adapter = _install_adapter()

    # First install
    result1 = adapter.install(gpd_root, target)
    assert result1["commands"] >= 1

    # Modify an installed file to simulate user edit
    first_file = _first_overwritable_installed_file(target)
    first_file.write_text("user modified content", encoding="utf-8")

    # Second install (upgrade)
    result2 = adapter.install(gpd_root, target)
    assert result2["commands"] >= 1

    # File should be overwritten by upgrade (atomic swap)
    content = first_file.read_text(encoding="utf-8")
    assert content != "user modified content"


# ─── 3. --all with partial failures ─────────────────────────────────────────


def test_install_all_continues_on_failure(tmp_path: Path):
    """--all install continues when some runtimes fail and sets exit code 1."""

    def mock_install_single(runtime_name, *, is_global, target_dir_override=None):
        if runtime_name == _PRIMARY_INSTALL_DESCRIPTOR.runtime_name:
            return {"runtime": runtime_name, "commands": 5, "agents": 3, "target": str(tmp_path)}
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
    assert "Install Summary" in result.output
    assert "Install failures:" in result.output
    assert "After install" not in result.output
    assert "Beginner path:" not in result.output
    assert "Use gpd --help for local diagnostics and later setup." not in result.output


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

        result = runner.invoke(app, ["install", _PRIMARY_INSTALL_DESCRIPTOR.runtime_name, "--local"])

    assert result.exit_code == 0


def test_install_banner_uses_display_names(tmp_path: Path):
    """Install banner should show human-friendly runtime names."""

    def mock_install_single(runtime_name, *, is_global, target_dir_override=None):
        return {"runtime": runtime_name, "commands": 5, "agents": 3, "target": str(_install_target(tmp_path))}

    with (
        patch("gpd.cli._install_single_runtime", side_effect=mock_install_single),
        patch("gpd.adapters.get_adapter") as mock_get,
    ):
        mock_get.return_value = _mock_install_adapter(_PRIMARY_INSTALL_DESCRIPTOR)

        result = runner.invoke(
            app, ["--cwd", str(tmp_path), "install", _PRIMARY_INSTALL_DESCRIPTOR.runtime_name, "--local"]
        )

    assert result.exit_code == 0
    assert "GPD v" in result.output
    assert "© 2026 Physical Superintelligence PBC (PSI)" in result.output
    assert "██████" in result.output
    assert f"Installing GPD (local) for: {_PRIMARY_INSTALL_DESCRIPTOR.display_name}" in result.output
    assert f"Installing GPD (local) for: {_PRIMARY_INSTALL_DESCRIPTOR.runtime_name}" not in result.output


def test_format_install_header_lines_uses_psi_branding() -> None:
    """Interactive install header should use the branded PSI wording."""
    assert _format_install_header_lines("1.0.0") == (
        "GPD v1.0.0 - Get Physics Done",
        "© 2026 Physical Superintelligence PBC (PSI)",
    )


def test_render_install_option_line_uses_single_line_bracketed_layout() -> None:
    """Interactive install options should use the compact bracketed layout."""
    runtime_line = _render_install_option_line(
        1,
        _PRIMARY_INSTALL_DESCRIPTOR.display_name,
        _PRIMARY_INSTALL_DESCRIPTOR.runtime_name,
        label_width=12,
    )
    assert runtime_line.plain.startswith(f"  [1] {_PRIMARY_INSTALL_DESCRIPTOR.display_name}")
    assert runtime_line.plain.endswith(f"· {_PRIMARY_INSTALL_DESCRIPTOR.runtime_name}")
    local_target = f"./{_PRIMARY_INSTALL_DESCRIPTOR.config_dir_name}"
    assert _render_install_option_line(1, "Local", "current project only", local_target, label_width=6).plain == (
        f"  [1] Local   · current project only · {local_target}"
    )


def test_install_summary_formats_target_relative_to_cwd(tmp_path: Path):
    """Install summary should show a compact target path."""
    target = _install_target(tmp_path)

    def mock_install_single(runtime_name, *, is_global, target_dir_override=None):
        return {"runtime": runtime_name, "commands": 5, "agents": 3, "target": str(target)}

    with (
        patch("gpd.cli._install_single_runtime", side_effect=mock_install_single),
        patch("gpd.adapters.get_adapter") as mock_get,
    ):
        mock_get.return_value = _mock_install_adapter(_PRIMARY_INSTALL_DESCRIPTOR)

        result = runner.invoke(
            app, ["--cwd", str(tmp_path), "install", _PRIMARY_INSTALL_DESCRIPTOR.runtime_name, "--local"]
        )

    assert result.exit_code == 0
    assert f"./{_PRIMARY_INSTALL_DESCRIPTOR.config_dir_name}" in result.output
    assert str(target) not in result.output


def test_install_summary_surfaces_help_then_new_or_existing_entry_points(tmp_path: Path):
    """Single-runtime install summaries should lead with help, then project entry points."""
    target = _install_target(tmp_path)

    def mock_install_single(runtime_name, *, is_global, target_dir_override=None):
        return {"runtime": runtime_name, "commands": 5, "agents": 3, "target": str(target)}

    with (
        patch("gpd.cli._install_single_runtime", side_effect=mock_install_single),
        patch("gpd.adapters.get_adapter") as mock_get,
    ):
        mock_get.return_value = _mock_install_adapter(_PRIMARY_INSTALL_DESCRIPTOR)

        result = runner.invoke(
            app, ["--cwd", str(tmp_path), "install", _PRIMARY_INSTALL_DESCRIPTOR.runtime_name, "--local"]
        )

    assert result.exit_code == 0
    _assert_single_runtime_next_steps(result.output)
    _assert_install_summary_recovery_contract(result.output, descriptor=_PRIMARY_INSTALL_DESCRIPTOR)


def test_install_summary_lists_runtime_specific_help_for_multi_runtime_install(tmp_path: Path):
    """Multi-runtime installs should print runtime-specific help hints."""
    descriptors = (_PRIMARY_INSTALL_DESCRIPTOR, _SECONDARY_INSTALL_DESCRIPTOR)

    def mock_install_single(runtime_name, *, is_global, target_dir_override=None):
        return {
            "runtime": runtime_name,
            "commands": 5,
            "agents": 3,
            "target": str(tmp_path / runtime_name),
        }

    adapters = {}
    for descriptor in descriptors:
        adapter = get_adapter(descriptor.runtime_name)
        adapters[descriptor.runtime_name] = MagicMock(
            display_name=descriptor.display_name,
            launch_command=adapter.launch_command,
            help_command=adapter.help_command,
            new_project_command=adapter.new_project_command,
            map_research_command=adapter.map_research_command,
            format_command=adapter.format_command,
        )

    with (
        patch("gpd.cli._install_single_runtime", side_effect=mock_install_single),
        patch("gpd.adapters.get_adapter", side_effect=lambda runtime: adapters[runtime]),
    ):
        result = runner.invoke(app, ["install", *(descriptor.runtime_name for descriptor in descriptors), "--local"])

    assert result.exit_code == 0
    assert "After install" in result.output
    assert beginner_startup_ladder_text() in result.output
    for descriptor in descriptors:
        _assert_multi_runtime_next_step_line(result.output, descriptor)
    assert "1. From your system terminal" not in result.output
    _assert_install_summary_recovery_contract(result.output, runtime_specific=True)
    assert_install_summary_runtime_follow_up_contract(result.output)


def test_install_help_surfaces_interactive_batch_and_targeting_guidance() -> None:
    """Install help should keep local/global targeting and interactive guidance visible."""
    result = runner.invoke(app, ["install", "--help"])
    normalized_output = _normalize_cli_output(result.output)

    assert result.exit_code == 0
    assert "Install GPD skills, agents, and hooks into runtime config directories." in normalized_output
    assert "Run without arguments for interactive mode." in normalized_output
    assert "Specify runtime name(s) or --all for batch mode." in normalized_output
    assert "gpd install --all --global" in normalized_output
    assert "Runtime(s) to install. Omit for interactive" in normalized_output
    assert "--local" in normalized_output
    assert "--global" in normalized_output
    assert "--target-dir" in normalized_output
    assert "Override the runtime config directory;" in normalized_output
    assert "defaults" in normalized_output
    assert "local scope" in normalized_output
    assert "runtime's canonical" in normalized_output
    assert "global config dir" in normalized_output


def test_uninstall_help_aligns_target_dir_wording() -> None:
    result = runner.invoke(app, ["uninstall", "--help"])
    normalized_output = _normalize_cli_output(result.output)

    assert result.exit_code == 0
    assert "--target-dir" in normalized_output
    assert "Override the runtime config directory;" in normalized_output
    assert "defaults" in normalized_output
    assert "local scope" in normalized_output
    assert "runtime's canonical" in normalized_output
    assert "global config dir" in normalized_output


# ─── 4. Uninstall without manifest ──────────────────────────────────────────


def test_uninstall_rejects_manifestless_managed_surface(tmp_path: Path):
    """Uninstall refuses managed surfaces when ownership cannot be proven."""
    target = _install_target(tmp_path)
    target.mkdir()
    # Create some GPD files but no manifest
    gpd_dir = target / "get-physics-done"
    gpd_dir.mkdir()
    (gpd_dir / "test.md").write_text("test", encoding="utf-8")

    adapter = _install_adapter()
    with pytest.raises(RuntimeError, match="contains GPD artifacts but no manifest"):
        adapter.uninstall(target)


def test_uninstall_empty_target_nothing_to_remove(tmp_path: Path):
    """Uninstall from an empty directory — gracefully reports nothing to remove."""
    target = _install_target(tmp_path)
    target.mkdir()

    adapter = _install_adapter()
    result = adapter.uninstall(target)

    assert result["runtime"] == _PRIMARY_INSTALL_DESCRIPTOR.runtime_name
    assert result["removed"] == []


def test_uninstall_nonexistent_target_skips(tmp_path: Path):
    """Uninstall when target dir doesn't exist — skip with message."""
    target = tmp_path / "nonexistent"
    result = runner.invoke(
        app,
        ["uninstall", _PRIMARY_INSTALL_DESCRIPTOR.runtime_name, "--local", "--target-dir", str(target), "--yes"],
    )
    assert result.exit_code == 0


def test_uninstall_missing_codex_target_still_removes_marker_backed_skills(tmp_path: Path) -> None:
    """Codex uninstall must delegate to the adapter even when .codex/ is gone."""
    descriptor = next(
        descriptor
        for descriptor in _INSTALL_TEST_DESCRIPTORS
        if any(prefix.rstrip("/") == "skills" for prefix in descriptor.manifest_file_prefixes)
    )
    workspace = tmp_path / "workspace"
    target = workspace / descriptor.config_dir_name
    skills_dir = workspace / ".agents" / "skills"
    managed_skill = skills_dir / "gpd-help"
    managed_skill.mkdir(parents=True)
    (managed_skill / "SKILL.md").write_text(
        "<!-- Managed by Get Physics Done (GPD). -->\n# Help\n",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        ["--raw", "uninstall", descriptor.runtime_name, "--local", "--target-dir", str(target)],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    outcome = payload["uninstalled"][0]
    assert outcome["runtime"] == descriptor.runtime_name
    assert outcome["status"] == "removed"
    assert any("GPD skills" in item for item in outcome["removed"])
    assert not managed_skill.exists()


def test_uninstall_all_continues_after_one_runtime_failure(tmp_path: Path) -> None:
    """A failure in one runtime uninstall must not stop later runtimes."""

    removed_target = _install_target(tmp_path, _PRIMARY_INSTALL_DESCRIPTOR)
    removed_target.mkdir()
    failed_target = _install_target(tmp_path, _SECONDARY_INSTALL_DESCRIPTOR)
    failed_target.mkdir()

    primary_adapter = MagicMock()
    primary_adapter.display_name = _PRIMARY_INSTALL_DESCRIPTOR.display_name
    primary_adapter.resolve_target_dir.return_value = removed_target
    primary_adapter.uninstall.return_value = {"removed": ["commands"]}

    secondary_adapter = MagicMock()
    secondary_adapter.display_name = _SECONDARY_INSTALL_DESCRIPTOR.display_name
    secondary_adapter.resolve_target_dir.return_value = failed_target
    secondary_adapter.uninstall.side_effect = RuntimeError("boom")

    with (
        patch(
            "gpd.adapters.list_runtimes",
            return_value=[_PRIMARY_INSTALL_DESCRIPTOR.runtime_name, _SECONDARY_INSTALL_DESCRIPTOR.runtime_name],
        ),
        patch(
            "gpd.adapters.get_adapter",
            side_effect=lambda runtime: (
                primary_adapter if runtime == _PRIMARY_INSTALL_DESCRIPTOR.runtime_name else secondary_adapter
            ),
        ),
    ):
        result = runner.invoke(app, ["uninstall", "--all", "--local"], input="y\n")

    assert result.exit_code == 1
    primary_adapter.uninstall.assert_called_once_with(removed_target)
    secondary_adapter.uninstall.assert_called_once_with(failed_target)
    assert "boom" in result.output
    assert _PRIMARY_INSTALL_DESCRIPTOR.display_name in result.output
    assert _SECONDARY_INSTALL_DESCRIPTOR.display_name in result.output


def test_uninstall_raw_outputs_structured_outcomes(tmp_path: Path) -> None:
    """--raw uninstall should report removed, skipped, and failed outcomes explicitly."""

    removed_target = _install_target(tmp_path, _PRIMARY_INSTALL_DESCRIPTOR)
    removed_target.mkdir()
    failed_target = _install_target(tmp_path, _SECONDARY_INSTALL_DESCRIPTOR)
    failed_target.mkdir()
    skipped_target = _install_target(tmp_path, _TERTIARY_INSTALL_DESCRIPTOR)

    primary_adapter = MagicMock()
    primary_adapter.display_name = _PRIMARY_INSTALL_DESCRIPTOR.display_name
    primary_adapter.resolve_target_dir.return_value = removed_target
    primary_adapter.uninstall.return_value = {"removed": ["commands", "agents"]}

    secondary_adapter = MagicMock()
    secondary_adapter.display_name = _SECONDARY_INSTALL_DESCRIPTOR.display_name
    secondary_adapter.resolve_target_dir.return_value = failed_target
    secondary_adapter.uninstall.side_effect = RuntimeError("boom")

    tertiary_adapter = MagicMock()
    tertiary_adapter.display_name = _TERTIARY_INSTALL_DESCRIPTOR.display_name
    tertiary_adapter.resolve_target_dir.return_value = skipped_target
    tertiary_adapter.uninstall.return_value = {"removed": []}

    with (
        patch(
            "gpd.adapters.list_runtimes",
            return_value=[
                _PRIMARY_INSTALL_DESCRIPTOR.runtime_name,
                _SECONDARY_INSTALL_DESCRIPTOR.runtime_name,
                _TERTIARY_INSTALL_DESCRIPTOR.runtime_name,
            ],
        ),
        patch(
            "gpd.adapters.get_adapter",
            side_effect=lambda runtime: {
                _PRIMARY_INSTALL_DESCRIPTOR.runtime_name: primary_adapter,
                _SECONDARY_INSTALL_DESCRIPTOR.runtime_name: secondary_adapter,
                _TERTIARY_INSTALL_DESCRIPTOR.runtime_name: tertiary_adapter,
            }[runtime],
        ),
    ):
        result = runner.invoke(app, ["--raw", "uninstall", "--all", "--local"])

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["uninstalled"][0] == {
        "runtime": _PRIMARY_INSTALL_DESCRIPTOR.runtime_name,
        "status": "removed",
        "target": str(removed_target),
        "removed": ["commands", "agents"],
    }
    assert payload["uninstalled"][1] == {
        "runtime": _SECONDARY_INSTALL_DESCRIPTOR.runtime_name,
        "status": "failed",
        "target": str(failed_target),
        "error": "boom",
    }
    skipped = payload["uninstalled"][2]
    assert skipped["runtime"] == _TERTIARY_INSTALL_DESCRIPTOR.runtime_name
    assert skipped["status"] == "skipped"
    assert skipped["target"] == str(skipped_target)
    assert skipped["reason"].startswith("not installed at ")


def test_uninstall_raw_continues_after_adapter_lookup_failure(tmp_path: Path) -> None:
    removed_target = _install_target(tmp_path, _PRIMARY_INSTALL_DESCRIPTOR)
    removed_target.mkdir()

    primary_adapter = MagicMock()
    primary_adapter.display_name = _PRIMARY_INSTALL_DESCRIPTOR.display_name
    primary_adapter.resolve_target_dir.return_value = removed_target
    primary_adapter.uninstall.return_value = {"removed": ["commands"]}

    def fake_get_adapter(runtime: str):
        if runtime == _SECONDARY_INSTALL_DESCRIPTOR.runtime_name:
            raise RuntimeError("registry offline")
        return primary_adapter

    with (
        patch(
            "gpd.adapters.list_runtimes",
            return_value=[_SECONDARY_INSTALL_DESCRIPTOR.runtime_name, _PRIMARY_INSTALL_DESCRIPTOR.runtime_name],
        ),
        patch("gpd.adapters.get_adapter", side_effect=fake_get_adapter),
    ):
        result = runner.invoke(app, ["--raw", "uninstall", "--all", "--local"])

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["uninstalled"] == [
        {
            "runtime": _SECONDARY_INSTALL_DESCRIPTOR.runtime_name,
            "status": "failed",
            "target": "",
            "error": (
                f"Runtime adapter unavailable for '{_SECONDARY_INSTALL_DESCRIPTOR.runtime_name}' during uninstall: "
                "registry offline"
            ),
        },
        {
            "runtime": _PRIMARY_INSTALL_DESCRIPTOR.runtime_name,
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
        patch("gpd.adapters.list_runtimes", return_value=[_PRIMARY_INSTALL_DESCRIPTOR.runtime_name]),
    ):
        mock_adapter = MagicMock()
        mock_adapter.display_name = _PRIMARY_INSTALL_DESCRIPTOR.display_name
        mock_adapter.help_command = _install_adapter().help_command
        mock_adapter.resolve_target_dir.side_effect = lambda is_global, cwd=None: (
            tmp_path
            / (
                f"{_PRIMARY_INSTALL_DESCRIPTOR.config_dir_name}-global"
                if is_global
                else _PRIMARY_INSTALL_DESCRIPTOR.config_dir_name
            )
        )
        mock_get.return_value = mock_adapter

        # CliRunner provides input='1\n1\n' to simulate interactive choices
        result = runner.invoke(app, ["install"], input="1\n1\n")

    assert result.exit_code == 0
    assert "GPD v" in result.output
    assert "© 2026 Physical Superintelligence PBC (PSI)" in result.output
    assert f"[1] {_PRIMARY_INSTALL_DESCRIPTOR.display_name}" in result.output
    assert f"· {_PRIMARY_INSTALL_DESCRIPTOR.runtime_name}" in result.output
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
        mock_adapter.display_name = _PRIMARY_INSTALL_DESCRIPTOR.display_name
        mock_get.return_value = mock_adapter

        result = runner.invoke(app, ["--raw", "install", _PRIMARY_INSTALL_DESCRIPTOR.runtime_name, "--local"])

    assert result.exit_code == 0
    # Output should contain valid JSON with "installed" key
    assert '"installed"' in result.output
    # Should NOT contain rich table formatting
    assert "Install Summary" not in result.output
    assert "GPD v" not in result.output


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
        patch(
            "gpd.adapters.list_runtimes",
            return_value=[_PRIMARY_INSTALL_DESCRIPTOR.runtime_name, _SECONDARY_INSTALL_DESCRIPTOR.runtime_name],
        ),
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
        display_name = _PRIMARY_INSTALL_DESCRIPTOR.display_name
        help_command = _install_adapter().help_command

        def finalize_install(self, install_result, *, force_statusline=False):
            raise RuntimeError("finalize boom")

    with (
        patch("gpd.cli._install_single_runtime", side_effect=mock_install_single),
        patch("gpd.adapters.get_adapter", return_value=FailingFinalizeAdapter()),
    ):
        result = runner.invoke(app, ["--raw", "install", _PRIMARY_INSTALL_DESCRIPTOR.runtime_name, "--local"])

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["installed"] == []
    assert payload["failed"] == [{"runtime": _PRIMARY_INSTALL_DESCRIPTOR.runtime_name, "error": "finalize boom"}]


def test_install_raw_finalize_failure_rolls_back_new_cli_target(gpd_root: Path, tmp_path: Path) -> None:
    """CLI install finalization failure must not leave a fresh target looking installed."""
    descriptor = _PRIMARY_INSTALL_DESCRIPTOR
    target = tmp_path / descriptor.config_dir_name
    real_adapter = get_adapter(descriptor.runtime_name)

    class FinalizeFailingAdapter:
        def __getattr__(self, name):
            return getattr(real_adapter, name)

        def install(self, *args, **kwargs):
            return real_adapter.install(*args, **kwargs)

        def finalize_install(self, install_result, *, force_statusline=False):
            raise RuntimeError("finalize boom")

    with (
        patch("gpd.adapters.get_adapter", return_value=FinalizeFailingAdapter()),
        patch("gpd.version.resolve_install_gpd_root", return_value=gpd_root),
        patch("gpd.cli._get_cwd", return_value=tmp_path),
    ):
        result = runner.invoke(
            app,
            [
                "--raw",
                "install",
                descriptor.runtime_name,
                "--target-dir",
                str(target),
                "--skip-readiness-check",
            ],
        )

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["installed"] == []
    failure = payload["failed"][0]
    assert failure["runtime"] == descriptor.runtime_name
    assert "finalize boom" in failure["error"]
    assert "Rolled back partial install" in failure["error"]
    assert not target.exists()


def test_install_raw_finalize_failure_restores_existing_cli_target(gpd_root: Path, tmp_path: Path) -> None:
    """CLI finalization failure should restore an existing complete install."""
    descriptor = _PRIMARY_INSTALL_DESCRIPTOR
    target = tmp_path / descriptor.config_dir_name
    real_adapter = get_adapter(descriptor.runtime_name)
    seed_result = real_adapter.install(gpd_root, target, is_global=False, explicit_target=True)
    real_adapter.finalize_install(seed_result)
    manifest_before = (target / MANIFEST_NAME).read_text(encoding="utf-8")
    settings_before = (target / "settings.json").read_text(encoding="utf-8")

    class FinalizeFailingAdapter:
        def __getattr__(self, name):
            return getattr(real_adapter, name)

        def install(self, *args, **kwargs):
            return real_adapter.install(*args, **kwargs)

        def finalize_install(self, install_result, *, force_statusline=False):
            raise RuntimeError("finalize boom")

    with (
        patch("gpd.adapters.get_adapter", return_value=FinalizeFailingAdapter()),
        patch("gpd.version.resolve_install_gpd_root", return_value=gpd_root),
        patch("gpd.cli._get_cwd", return_value=tmp_path),
    ):
        result = runner.invoke(
            app,
            [
                "--raw",
                "install",
                descriptor.runtime_name,
                "--target-dir",
                str(target),
                "--skip-readiness-check",
            ],
        )

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["installed"] == []
    assert "Rolled back partial install" in payload["failed"][0]["error"]
    assert (target / MANIFEST_NAME).read_text(encoding="utf-8") == manifest_before
    assert (target / "settings.json").read_text(encoding="utf-8") == settings_before
    assert not (target / "gpd-install-incomplete.json").exists()


def test_install_raw_finalizes_same_adapter_instance_used_for_install(tmp_path: Path) -> None:
    """Deferred finalization must keep adapter instance state from install()."""
    descriptor = _PRIMARY_INSTALL_DESCRIPTOR
    target = _install_target(tmp_path, descriptor)
    gpd_root = tmp_path / "gpd-root"
    instances: list[object] = []

    class SpyAdapter:
        runtime_name = descriptor.runtime_name
        display_name = descriptor.display_name
        config_dir_name = descriptor.config_dir_name
        help_command = _install_adapter(descriptor).help_command

        def __init__(self) -> None:
            self.installed = False
            self.finalized = False
            instances.append(self)

        def resolve_target_dir(self, is_global, cwd=None):
            return target

        def install(self, gpd_root_arg, target_dir, *, is_global=False, explicit_target=False):
            assert gpd_root_arg == gpd_root
            assert target_dir == target
            self.installed = True
            return {"runtime": descriptor.runtime_name, "commands": 0, "agents": 0, "target": str(target)}

        def finalize_install(self, install_result, *, force_statusline=False):
            if not self.installed:
                raise AssertionError("finalized a different adapter instance")
            self.finalized = True

    with (
        patch("gpd.adapters.get_adapter", side_effect=lambda _runtime: SpyAdapter()),
        patch("gpd.version.resolve_install_gpd_root", return_value=gpd_root),
        patch("gpd.cli._get_cwd", return_value=tmp_path),
    ):
        result = runner.invoke(
            app,
            ["--raw", "install", descriptor.runtime_name, "--local", "--skip-readiness-check"],
            catch_exceptions=False,
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["failed"] == []
    assert "__gpd_install_adapter_instance__" not in json.dumps(payload)
    assert any(getattr(instance, "installed", False) and getattr(instance, "finalized", False) for instance in instances)


def test_install_human_reports_failures_after_progress_exits(tmp_path: Path):
    """Human install failures should remain visible after Rich progress exits."""

    def mock_install_single(runtime_name, *, is_global, target_dir_override=None):
        raise RuntimeError("install boom")

    mock_adapter = MagicMock()
    mock_adapter.display_name = _PRIMARY_INSTALL_DESCRIPTOR.display_name

    with (
        patch("gpd.cli._install_single_runtime", side_effect=mock_install_single),
        patch("gpd.adapters.get_adapter", return_value=mock_adapter),
    ):
        result = runner.invoke(app, ["install", _PRIMARY_INSTALL_DESCRIPTOR.runtime_name, "--local"])

    assert result.exit_code == 1
    normalized_output = _normalize_cli_output(result.output)
    assert "Install failures:" in normalized_output
    assert (
        f"{_PRIMARY_INSTALL_DESCRIPTOR.display_name} ({_PRIMARY_INSTALL_DESCRIPTOR.runtime_name}): install boom"
        in normalized_output
    )


@patch("gpd.core.health.run_doctor")
def test_install_raw_reports_preflight_failures_without_changing_raw_schema(mock_run_doctor, tmp_path: Path) -> None:
    mock_run_doctor.return_value = _doctor_report(
        overall=CheckStatus.FAIL,
        runtime=_PRIMARY_INSTALL_DESCRIPTOR.runtime_name,
        install_scope="local",
        checks=[
            HealthCheck(
                status=CheckStatus.FAIL,
                label="Runtime Launcher",
                issues=["launcher missing"],
            )
        ],
    )

    with patch("gpd.cli._install_single_runtime") as mock_install_single:
        result = runner.invoke(app, ["--raw", "install", _PRIMARY_INSTALL_DESCRIPTOR.runtime_name, "--local"])

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload == {
        "installed": [],
        "failed": [{"runtime": _PRIMARY_INSTALL_DESCRIPTOR.runtime_name, "error": "launcher missing"}],
    }
    mock_install_single.assert_not_called()


@patch("gpd.core.health.run_doctor")
def test_install_preflight_aggregates_blockers_and_skips_all_runtime_installs(mock_run_doctor, tmp_path: Path) -> None:
    mock_run_doctor.side_effect = [
        _doctor_report(
            runtime=_PRIMARY_INSTALL_DESCRIPTOR.runtime_name,
            install_scope="local",
            checks=[
                HealthCheck(
                    status=CheckStatus.OK,
                    label="Runtime Launcher",
                )
            ],
        ),
        _doctor_report(
            overall=CheckStatus.FAIL,
            runtime=_SECONDARY_INSTALL_DESCRIPTOR.runtime_name,
            install_scope="local",
            checks=[
                HealthCheck(
                    status=CheckStatus.FAIL,
                    label="Runtime Config Target",
                    issues=["secondary target not writable"],
                )
            ],
        ),
    ]

    with (
        patch(
            "gpd.adapters.list_runtimes",
            return_value=[_PRIMARY_INSTALL_DESCRIPTOR.runtime_name, _SECONDARY_INSTALL_DESCRIPTOR.runtime_name],
        ),
        patch("gpd.cli._install_single_runtime") as mock_install_single,
    ):
        result = runner.invoke(app, ["install", "--all", "--local"])

    assert result.exit_code == 1
    mock_install_single.assert_not_called()
    assert _SECONDARY_INSTALL_DESCRIPTOR.display_name in result.output
    assert "secondary target not writable" in result.output
    assert "readiness check passed" not in result.output


@patch("gpd.core.health.run_doctor")
def test_install_raw_reports_all_preflight_failures_for_multi_runtime_install(mock_run_doctor, tmp_path: Path) -> None:
    mock_run_doctor.side_effect = [
        _doctor_report(
            overall=CheckStatus.FAIL,
            runtime=_PRIMARY_INSTALL_DESCRIPTOR.runtime_name,
            install_scope="local",
            checks=[
                HealthCheck(
                    status=CheckStatus.FAIL,
                    label="Runtime Launcher",
                    issues=["primary launcher missing"],
                )
            ],
        ),
        _doctor_report(
            overall=CheckStatus.FAIL,
            runtime=_SECONDARY_INSTALL_DESCRIPTOR.runtime_name,
            install_scope="local",
            checks=[
                HealthCheck(
                    status=CheckStatus.FAIL,
                    label="Runtime Config Target",
                    issues=["secondary target not writable"],
                )
            ],
        ),
    ]

    with (
        patch(
            "gpd.adapters.list_runtimes",
            return_value=[_PRIMARY_INSTALL_DESCRIPTOR.runtime_name, _SECONDARY_INSTALL_DESCRIPTOR.runtime_name],
        ),
        patch("gpd.cli._install_single_runtime") as mock_install_single,
    ):
        result = runner.invoke(app, ["--raw", "install", "--all", "--local"])

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload == {
        "installed": [],
        "failed": [
            {"runtime": _PRIMARY_INSTALL_DESCRIPTOR.runtime_name, "error": "primary launcher missing"},
            {"runtime": _SECONDARY_INSTALL_DESCRIPTOR.runtime_name, "error": "secondary target not writable"},
        ],
    }
    mock_install_single.assert_not_called()


@patch("gpd.core.health.run_doctor")
def test_install_preflight_forwards_scope_and_explicit_target_dir(mock_run_doctor, tmp_path: Path) -> None:
    runtime_name = _PRIMARY_INSTALL_DESCRIPTOR.runtime_name
    target_dir = tmp_path / "target-config"
    mock_run_doctor.return_value = _doctor_report(
        runtime=runtime_name,
        install_scope="local",
        target=str(target_dir),
    )

    def mock_install_single(runtime_name, *, is_global, target_dir_override=None):
        return {"runtime": runtime_name, "commands": 5, "agents": 3, "target": str(target_dir)}

    with (
        patch("gpd.cli._install_single_runtime", side_effect=mock_install_single),
        patch("gpd.adapters.get_adapter") as mock_get,
    ):
        mock_get.return_value = _mock_install_adapter(_PRIMARY_INSTALL_DESCRIPTOR)
        result = runner.invoke(app, ["install", runtime_name, "--target-dir", str(target_dir)])

    assert result.exit_code == 0
    mock_run_doctor.assert_called_once()
    _, kwargs = mock_run_doctor.call_args
    assert kwargs["runtime"] == runtime_name
    assert kwargs["install_scope"] == "local"
    assert kwargs["target_dir"] == target_dir.resolve(strict=False)


@patch("gpd.core.health.run_doctor")
def test_install_skip_readiness_check_reports_skipped_not_passed(mock_run_doctor, tmp_path: Path) -> None:
    runtime_name = _PRIMARY_INSTALL_DESCRIPTOR.runtime_name
    target_dir = tmp_path / "target-config"

    def mock_install_single(runtime_name, *, is_global, target_dir_override=None):
        return {"runtime": runtime_name, "commands": 5, "agents": 3, "target": str(target_dir)}

    with (
        patch("gpd.cli._install_single_runtime", side_effect=mock_install_single),
        patch("gpd.adapters.get_adapter") as mock_get,
    ):
        mock_get.return_value = _mock_install_adapter(_PRIMARY_INSTALL_DESCRIPTOR)
        result = runner.invoke(app, ["install", runtime_name, "--local", "--skip-readiness-check"])

    assert result.exit_code == 0
    mock_run_doctor.assert_not_called()
    assert "readiness check skipped" in result.output
    assert "readiness check passed" not in result.output


def test_uninstall_raw_outputs_json(tmp_path: Path):
    """--raw flag on uninstall outputs clean JSON."""
    target = _install_target(tmp_path)
    target.mkdir()

    result = runner.invoke(
        app,
        ["--raw", "uninstall", _PRIMARY_INSTALL_DESCRIPTOR.runtime_name, "--local", "--target-dir", str(target)],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["uninstalled"][0]["runtime"] == _PRIMARY_INSTALL_DESCRIPTOR.runtime_name
    assert payload["uninstalled"][0]["status"] == "skipped"
    assert payload["uninstalled"][0]["target"] == str(target)
    assert payload["uninstalled"][0]["reason"] == "nothing to remove"
    assert payload["uninstalled"][0]["removed"] == []


def test_uninstall_human_reports_managed_mcp_server_removal(gpd_root: Path, tmp_path: Path) -> None:
    for descriptor in _descriptors_with_uninstall_counter(tmp_path, "mcpServers"):
        adapter = get_adapter(descriptor.runtime_name)
        target = tmp_path / "human-uninstall" / descriptor.config_dir_name
        target.mkdir(parents=True)
        adapter.install(gpd_root, target, is_global=False)

        result = runner.invoke(app, ["uninstall", descriptor.runtime_name, "--target-dir", str(target), "--yes"])

        assert result.exit_code == 0
        assert "GPD" in result.output
        assert "MCP servers" in result.output


def test_uninstall_raw_reports_managed_mcp_server_removal(gpd_root: Path, tmp_path: Path) -> None:
    for descriptor in _descriptors_with_uninstall_counter(tmp_path, "mcpServers"):
        adapter = get_adapter(descriptor.runtime_name)
        target = tmp_path / "raw-uninstall" / descriptor.config_dir_name
        target.mkdir(parents=True)
        adapter.install(gpd_root, target, is_global=False)

        result = runner.invoke(app, ["--raw", "uninstall", descriptor.runtime_name, "--target-dir", str(target)])

        assert result.exit_code == 0
        payload = json.loads(result.output)
        outcome = payload["uninstalled"][0]
        assert any("GPD MCP servers" in item for item in outcome["removed"])
        assert outcome["mcpServers"] > 0


@patch("gpd.core.health.run_doctor")
def test_doctor_raw_outputs_structured_readiness_payload(mock_doctor) -> None:
    """The readiness entrypoint should preserve doctor payloads in raw mode."""
    mock_result = MagicMock()
    mock_result.model_dump.return_value = {
        "ok": True,
        "checks": [{"label": "Python", "status": "ok"}],
    }
    mock_doctor.return_value = mock_result

    result = runner.invoke(app, ["--raw", "doctor"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload == {
        "ok": True,
        "checks": [{"label": "Python", "status": "ok"}],
    }
    mock_doctor.assert_called_once()


# ─── 7. is_global forwarding ────────────────────────────────────────────────


def test_install_single_runtime_passes_is_global(tmp_path: Path):
    """compute_path_prefix still distinguishes global vs local installs."""
    from gpd.adapters.install_utils import compute_path_prefix

    # Global install should produce absolute path prefix
    target = _install_target(tmp_path)
    global_prefix = compute_path_prefix(target, _PRIMARY_INSTALL_DESCRIPTOR.config_dir_name, is_global=True)
    assert global_prefix.startswith("/") or global_prefix.startswith("C:")  # absolute path
    assert not global_prefix.startswith("./")

    # Local install should produce relative path prefix
    local_prefix = compute_path_prefix(target, _PRIMARY_INSTALL_DESCRIPTOR.config_dir_name, is_global=False)
    assert local_prefix == f"./{_PRIMARY_INSTALL_DESCRIPTOR.config_dir_name}/"


def test_install_single_runtime_forwards_is_global(tmp_path: Path):
    """_install_single_runtime correctly calls adapter.install with is_global when supported."""
    from gpd.cli import _install_single_runtime

    captured_calls: list[dict[str, object]] = []
    descriptor = _PRIMARY_INSTALL_DESCRIPTOR

    class SpyAdapter:
        runtime_name = descriptor.runtime_name
        display_name = descriptor.display_name
        config_dir_name = descriptor.config_dir_name
        help_command = _install_adapter(descriptor).help_command

        def resolve_target_dir(self, is_global, cwd=None):
            return _install_target(tmp_path, descriptor)

        def install(self, gpd_root, target_dir, *, is_global=False, explicit_target=False):
            captured_calls.append({"is_global": is_global, "explicit_target": explicit_target})
            return {"runtime": descriptor.runtime_name, "commands": 0, "agents": 0}

        def finalize_install(self, install_result, *, force_statusline=False):
            return None

    with (
        patch("gpd.adapters.get_adapter", return_value=SpyAdapter()),
        patch("gpd.cli._get_cwd", return_value=tmp_path),
    ):
        _install_single_runtime(descriptor.runtime_name, is_global=True)

    assert len(captured_calls) == 1
    assert captured_calls[0]["is_global"] is True
    assert captured_calls[0]["explicit_target"] is False

    captured_calls.clear()
    with (
        patch("gpd.adapters.get_adapter", return_value=SpyAdapter()),
        patch("gpd.cli._get_cwd", return_value=tmp_path),
    ):
        _install_single_runtime(descriptor.runtime_name, is_global=False)

    assert len(captured_calls) == 1
    assert captured_calls[0]["is_global"] is False
    assert captured_calls[0]["explicit_target"] is False


def test_install_single_runtime_prefers_checkout_source_tree(tmp_path: Path):
    """When invoked inside the repo, install should use that checkout's src/gpd tree."""
    from gpd.cli import _install_single_runtime

    checkout = _make_checkout(tmp_path, "9.9.9")
    captured_calls: list[dict[str, object]] = []
    descriptor = _PRIMARY_INSTALL_DESCRIPTOR

    class SpyAdapter:
        runtime_name = descriptor.runtime_name
        display_name = descriptor.display_name
        config_dir_name = descriptor.config_dir_name
        help_command = _install_adapter(descriptor).help_command

        def resolve_target_dir(self, is_global, cwd=None):
            return _install_target(tmp_path, descriptor)

        def install(self, gpd_root, target_dir, *, is_global=False, explicit_target=False):
            captured_calls.append({"gpd_root": gpd_root, "target_dir": target_dir})
            return {"runtime": descriptor.runtime_name, "commands": 0, "agents": 0}

        def finalize_install(self, install_result, *, force_statusline=False):
            return None

    with (
        patch("gpd.adapters.get_adapter", return_value=SpyAdapter()),
        patch("gpd.cli._get_cwd", return_value=checkout),
    ):
        _install_single_runtime(descriptor.runtime_name, is_global=False)

    assert len(captured_calls) == 1
    assert captured_calls[0]["gpd_root"] == checkout / "src" / "gpd"


def test_install_single_runtime_marks_explicit_target(tmp_path: Path):
    """_install_single_runtime forwards explicit_target when --target-dir is used."""
    from gpd.cli import _install_single_runtime

    captured_calls: list[dict[str, object]] = []
    target = tmp_path / "custom-runtime-dir"
    descriptor = _PRIMARY_INSTALL_DESCRIPTOR

    class SpyAdapter:
        runtime_name = descriptor.runtime_name
        display_name = descriptor.display_name
        config_dir_name = descriptor.config_dir_name
        help_command = _install_adapter(descriptor).help_command

        def resolve_target_dir(self, is_global, cwd=None):
            return _install_target(tmp_path, descriptor)

        def install(self, gpd_root, target_dir, *, is_global=False, explicit_target=False):
            captured_calls.append(
                {
                    "is_global": is_global,
                    "explicit_target": explicit_target,
                    "target_dir": target_dir,
                }
            )
            return {"runtime": descriptor.runtime_name, "commands": 0, "agents": 0}

        def finalize_install(self, install_result, *, force_statusline=False):
            return None

    with patch("gpd.adapters.get_adapter", return_value=SpyAdapter()):
        _install_single_runtime(descriptor.runtime_name, is_global=False, target_dir_override=str(target))

    assert len(captured_calls) == 1
    assert captured_calls[0]["is_global"] is False
    assert captured_calls[0]["explicit_target"] is True
    assert captured_calls[0]["target_dir"] == target


def test_install_target_dir_preserves_explicit_global_scope(tmp_path: Path) -> None:
    """A global install should stay global even when a target dir is explicit."""
    target_descriptor = _PRIMARY_INSTALL_DESCRIPTOR
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

    mock_adapter = _mock_install_adapter(target_descriptor)

    with (
        patch("gpd.cli._install_single_runtime", side_effect=mock_install_single),
        patch("gpd.adapters.get_adapter", return_value=mock_adapter),
    ):
        result = runner.invoke(
            app,
            ["install", _PRIMARY_INSTALL_DESCRIPTOR.display_name, "--global", "--target-dir", str(target)],
        )

    assert result.exit_code == 0
    assert captured_calls == [
        {
            "runtime": _PRIMARY_INSTALL_DESCRIPTOR.runtime_name,
            "is_global": True,
            "target_dir_override": str(target),
        }
    ]


def test_install_target_dir_uses_canonical_global_path_when_runtime_env_overrides_global_dir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both default and env-overridden global paths should classify as global."""
    from gpd.adapters import get_adapter
    from gpd.adapters.runtime_catalog import resolve_global_config_dir

    captured_calls: list[dict[str, object]] = []
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    override_dir = tmp_path / "override-global"
    override_dir.mkdir()

    runtime_name = _ENV_OVERRIDE_INSTALL_DESCRIPTOR.runtime_name
    adapter = get_adapter(runtime_name)
    descriptor = adapter.runtime_descriptor
    canonical_target = resolve_global_config_dir(descriptor, home=home, environ={})
    canonical_target.mkdir(parents=True)

    env_var = (
        descriptor.global_config.env_var
        or descriptor.global_config.env_dir_var
        or descriptor.global_config.env_file_var
    )
    assert env_var is not None
    env_value = (
        str(override_dir / "config.json") if env_var == descriptor.global_config.env_file_var else str(override_dir)
    )
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


def test_install_target_dir_uses_env_overridden_global_path_as_global_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Env-overridden global config dirs should still classify as global install targets."""
    from gpd.adapters import get_adapter

    captured_calls: list[dict[str, object]] = []
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    override_dir = tmp_path / "override-global"
    override_dir.mkdir()

    runtime_name = _ENV_OVERRIDE_INSTALL_DESCRIPTOR.runtime_name
    adapter = get_adapter(runtime_name)
    descriptor = adapter.runtime_descriptor
    env_var = (
        descriptor.global_config.env_var
        or descriptor.global_config.env_dir_var
        or descriptor.global_config.env_file_var
    )
    assert env_var is not None
    monkeypatch.setenv(env_var, str(override_dir))

    mock_adapter = MagicMock(
        runtime_descriptor=descriptor,
        display_name=adapter.display_name,
        help_command=adapter.help_command,
        launch_command=adapter.launch_command,
        new_project_command=adapter.new_project_command,
        map_research_command=adapter.map_research_command,
    )
    mock_adapter.finalize_install.return_value = None
    mock_adapter.resolve_target_dir.side_effect = lambda is_global, cwd=None: (
        override_dir if is_global else workspace / descriptor.config_dir_name
    )
    captured_preflight: list[dict[str, object]] = []

    def mock_install_single(runtime_name, *, is_global, target_dir_override=None):
        captured_calls.append(
            {
                "runtime": runtime_name,
                "is_global": is_global,
                "target_dir_override": target_dir_override,
            }
        )
        return {"runtime": runtime_name, "commands": 5, "agents": 3, "target": str(override_dir)}

    def mock_run_doctor(*, specs_dir=None, version=None, runtime=None, install_scope=None, target_dir=None, cwd=None):
        captured_preflight.append(
            {
                "runtime": runtime,
                "install_scope": install_scope,
                "target_dir": target_dir,
            }
        )
        target_text = str(target_dir) if target_dir is not None else None
        return _doctor_report(runtime=runtime, install_scope=install_scope, target=target_text)

    with (
        patch("gpd.core.health.run_doctor", side_effect=mock_run_doctor),
        patch("gpd.cli._install_single_runtime", side_effect=mock_install_single),
        patch("gpd.adapters.get_adapter", return_value=mock_adapter),
        patch("gpd.cli._get_cwd", return_value=workspace),
        patch("gpd.cli.Path.home", return_value=home),
    ):
        result = runner.invoke(app, ["install", runtime_name, "--target-dir", str(override_dir)])

    assert result.exit_code == 0, result.output
    assert captured_calls == [
        {
            "runtime": runtime_name,
            "is_global": True,
            "target_dir_override": str(override_dir),
        }
    ]
    assert captured_preflight == [
        {
            "runtime": runtime_name,
            "install_scope": "global",
            "target_dir": override_dir.resolve(strict=False),
        }
    ]


def test_install_single_runtime_resolves_relative_target_dir_against_cli_cwd(tmp_path: Path):
    """Relative --target-dir should be anchored to --cwd, not the process cwd."""
    from gpd.cli import _install_single_runtime

    captured_calls: list[Path] = []
    cli_cwd = tmp_path / "workspace"
    cli_cwd.mkdir()

    class SpyAdapter:
        runtime_name = _PRIMARY_INSTALL_DESCRIPTOR.runtime_name
        display_name = _PRIMARY_INSTALL_DESCRIPTOR.display_name
        config_dir_name = _PRIMARY_INSTALL_DESCRIPTOR.config_dir_name
        help_command = _install_adapter().help_command

        def resolve_target_dir(self, is_global, cwd=None):
            return _install_target(tmp_path)

        def install(self, gpd_root, target_dir, *, is_global=False, explicit_target=False):
            captured_calls.append(target_dir)
            return {"runtime": _PRIMARY_INSTALL_DESCRIPTOR.runtime_name, "commands": 0, "agents": 0}

        def finalize_install(self, install_result, *, force_statusline=False):
            return None

    with (
        patch("gpd.adapters.get_adapter", return_value=SpyAdapter()),
        patch("gpd.cli._get_cwd", return_value=cli_cwd),
    ):
        _install_single_runtime(
            _PRIMARY_INSTALL_DESCRIPTOR.runtime_name, is_global=False, target_dir_override="relative-target"
        )

    assert captured_calls == [cli_cwd / "relative-target"]


def test_install_single_runtime_rejects_explicit_target_with_foreign_manifest(
    gpd_root: Path,
    tmp_path: Path,
) -> None:
    """Explicit target installs must not clean up a config dir owned by another runtime."""
    from gpd.cli import _install_single_runtime

    runtime_descriptor = _PRIMARY_INSTALL_DESCRIPTOR
    foreign_descriptor = _SECONDARY_INSTALL_DESCRIPTOR
    target = tmp_path / "shared-runtime-dir"
    target.mkdir()
    (target / "get-physics-done").mkdir()
    preserved = target / "get-physics-done" / "keep.md"
    preserved.write_text("preserve", encoding="utf-8")
    manifest_path = target / "gpd-file-manifest.json"
    manifest_path.write_text(
        json.dumps({"runtime": foreign_descriptor.runtime_name, "install_scope": "local", "explicit_target": True}),
        encoding="utf-8",
    )

    with (
        patch("gpd.adapters.get_adapter", return_value=_install_adapter(runtime_descriptor)),
        patch("gpd.version.resolve_install_gpd_root", return_value=gpd_root),
        patch("gpd.cli._get_cwd", return_value=tmp_path),
    ):
        foreign_label = _install_adapter(foreign_descriptor).display_name
        runtime_label = _install_adapter(runtime_descriptor).display_name
        expected_message = (
            rf"{foreign_label} \(`{foreign_descriptor.runtime_name}`\), "
            rf"not {runtime_label} \(`{runtime_descriptor.runtime_name}`\)"
        )
        with pytest.raises(RuntimeError, match=expected_message):
            _install_single_runtime(runtime_descriptor.runtime_name, is_global=False, target_dir_override=str(target))

    assert preserved.read_text(encoding="utf-8") == "preserve"
    assert json.loads(manifest_path.read_text(encoding="utf-8"))["runtime"] == foreign_descriptor.runtime_name


def test_local_install_manifest_stays_non_explicit_outside_process_cwd(gpd_root: Path, tmp_path: Path):
    """Default local installs should not become explicit targets just because cwd differs."""
    from gpd.hooks.install_metadata import installed_update_command

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target = workspace / _PRIMARY_INSTALL_DESCRIPTOR.config_dir_name

    adapter = _install_adapter()
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

    config_dir = _install_target(tmp_path)
    config_dir.mkdir()
    (config_dir / "get-physics-done").mkdir()
    (config_dir / "gpd-file-manifest.json").write_text(
        json.dumps({"runtime": _PRIMARY_INSTALL_DESCRIPTOR.runtime_name, "install_scope": "local"}),
        encoding="utf-8",
    )

    adapter = MagicMock()
    adapter.has_complete_install.return_value = False

    with patch("gpd.hooks.install_metadata.get_adapter", return_value=adapter):
        assert config_dir_has_complete_install(config_dir) is False


def test_hook_install_metadata_rejects_missing_runtime_specific_completeness_artifact(tmp_path: Path):
    """Half-installed runtime trees should not count as complete when strict artifacts are missing."""
    from gpd.hooks.install_metadata import config_dir_has_complete_install

    descriptor = next(
        descriptor
        for descriptor in _INSTALL_TEST_DESCRIPTORS
        if len(_install_adapter(descriptor).install_completeness_relpaths())
        > len(_install_adapter(descriptor).install_detection_relpaths())
    )
    config_dir = _install_target(tmp_path, descriptor)
    config_dir.mkdir()
    (config_dir / "get-physics-done").mkdir()
    (config_dir / "gpd-file-manifest.json").write_text(
        json.dumps({"runtime": descriptor.runtime_name, "install_scope": "local"}),
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
        display_name = _PRIMARY_INSTALL_DESCRIPTOR.display_name

        def resolve_target_dir(self, is_global, cwd=None):
            return _install_target(tmp_path)

        def uninstall(self, target_dir):
            captured_targets.append(target_dir)
            return {"runtime": _PRIMARY_INSTALL_DESCRIPTOR.runtime_name, "removed": []}

    with (
        patch("gpd.adapters.get_adapter", return_value=SpyAdapter()),
        patch("gpd.cli._get_cwd", return_value=cli_cwd),
    ):
        result = runner.invoke(
            app,
            ["uninstall", _PRIMARY_INSTALL_DESCRIPTOR.runtime_name, "--target-dir", "relative-target", "--yes"],
        )

    assert result.exit_code == 0
    assert captured_targets == [target]


def test_uninstall_target_dir_prompts_with_resolved_path(tmp_path: Path) -> None:
    target = tmp_path / "installed"
    target.mkdir()
    mock_adapter = MagicMock()
    mock_adapter.display_name = _PRIMARY_INSTALL_DESCRIPTOR.display_name
    mock_adapter.uninstall.return_value = {"runtime": _PRIMARY_INSTALL_DESCRIPTOR.runtime_name, "removed": ["commands"]}

    with patch("gpd.adapters.get_adapter", return_value=mock_adapter):
        result = runner.invoke(
            app,
            ["uninstall", _PRIMARY_INSTALL_DESCRIPTOR.runtime_name, "--target-dir", str(target)],
            input="n\n",
            terminal_width=1000,
        )

    assert result.exit_code == 0
    assert str(target) in result.output.replace("\n", "")
    assert "Cancelled." in result.output
    mock_adapter.uninstall.assert_not_called()


@pytest.mark.parametrize("confirm_flag", ["--yes", "--force"])
def test_uninstall_target_dir_confirm_flags_skip_prompt(tmp_path: Path, confirm_flag: str) -> None:
    target = tmp_path / "installed"
    target.mkdir()
    mock_adapter = MagicMock()
    mock_adapter.display_name = _PRIMARY_INSTALL_DESCRIPTOR.display_name
    mock_adapter.uninstall.return_value = {"runtime": _PRIMARY_INSTALL_DESCRIPTOR.runtime_name, "removed": ["commands"]}

    with patch("gpd.adapters.get_adapter", return_value=mock_adapter):
        result = runner.invoke(
            app,
            ["uninstall", _PRIMARY_INSTALL_DESCRIPTOR.runtime_name, "--target-dir", str(target), confirm_flag],
        )

    assert result.exit_code == 0
    assert "Remove GPD from" not in result.output
    mock_adapter.uninstall.assert_called_once_with(target)


def test_uninstall_rejects_target_dir_with_foreign_manifest(tmp_path: Path) -> None:
    """Explicit target uninstalls must not remove another runtime's install."""
    runtime_descriptor = _PRIMARY_INSTALL_DESCRIPTOR
    foreign_descriptor = _SECONDARY_INSTALL_DESCRIPTOR
    target = tmp_path / "shared-runtime-dir"
    target.mkdir()
    (target / "get-physics-done").mkdir()
    preserved = target / "get-physics-done" / "keep.md"
    preserved.write_text("preserve", encoding="utf-8")
    manifest_path = target / "gpd-file-manifest.json"
    manifest_path.write_text(
        json.dumps({"runtime": foreign_descriptor.runtime_name, "install_scope": "local", "explicit_target": True}),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        ["uninstall", runtime_descriptor.runtime_name, "--target-dir", str(target)],
        input="y\n",
    )

    assert result.exit_code == 1
    foreign_label = _install_adapter(foreign_descriptor).display_name
    runtime_label = _install_adapter(runtime_descriptor).display_name
    assert (
        f"{foreign_label} (`{foreign_descriptor.runtime_name}`), "
        f"not {runtime_label} (`{runtime_descriptor.runtime_name}`)"
    ) in result.output
    assert preserved.read_text(encoding="utf-8") == "preserve"
    assert json.loads(manifest_path.read_text(encoding="utf-8"))["runtime"] == foreign_descriptor.runtime_name


def test_uninstall_rejects_target_dir_with_foreign_manifest_without_wrapping(tmp_path: Path) -> None:
    """Foreign-manifest ownership errors should stay stable under narrow terminals."""
    runtime_descriptor = _PRIMARY_INSTALL_DESCRIPTOR
    foreign_descriptor = _SECONDARY_INSTALL_DESCRIPTOR
    target = tmp_path / "shared-runtime-dir"
    target.mkdir()
    (target / "get-physics-done").mkdir()
    (target / "gpd-file-manifest.json").write_text(
        json.dumps({"runtime": foreign_descriptor.runtime_name, "install_scope": "local", "explicit_target": True}),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        ["uninstall", runtime_descriptor.runtime_name, "--target-dir", str(target)],
        input="y\n",
        terminal_width=80,
    )

    assert result.exit_code == 1
    foreign_label = _install_adapter(foreign_descriptor).display_name
    runtime_label = _install_adapter(runtime_descriptor).display_name
    assert (
        f"{foreign_label} (`{foreign_descriptor.runtime_name}`), "
        f"not {runtime_label} (`{runtime_descriptor.runtime_name}`)"
    ) in result.output


def test_install_interactive_rejects_ambiguous_runtime_name(tmp_path: Path):
    """Substring matches that hit multiple runtimes should fail closed."""
    ambiguous_descriptors = _descriptors_with_selection_alias_fragment("code")
    with (
        patch(
            "gpd.adapters.list_runtimes", return_value=[descriptor.runtime_name for descriptor in ambiguous_descriptors]
        ),
        patch("gpd.adapters.get_adapter") as mock_get,
    ):
        adapters = {
            descriptor.runtime_name: MagicMock(
                display_name=descriptor.display_name,
                selection_aliases=descriptor.selection_aliases,
            )
            for descriptor in ambiguous_descriptors
        }
        mock_get.side_effect = lambda runtime: adapters[runtime]

        result = runner.invoke(app, ["install"], input="code\n")

    assert result.exit_code == 1
    assert "Ambiguous selection: 'code'" in result.output


def test_install_interactive_accepts_unique_fuzzy_runtime_name(tmp_path: Path):
    """A unique substring match should select that runtime and continue."""
    target_descriptor = _descriptor_with_selection_alias_fragment("open")

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
        patch(
            "gpd.adapters.list_runtimes",
            return_value=[descriptor.runtime_name for descriptor in _INSTALL_TEST_DESCRIPTORS],
        ),
        patch("gpd.adapters.get_adapter") as mock_get,
    ):
        adapters = {
            descriptor.runtime_name: _mock_install_adapter(descriptor) for descriptor in _INSTALL_TEST_DESCRIPTORS
        }
        mock_get.side_effect = lambda runtime: adapters[runtime]

        result = runner.invoke(app, ["install"], input="open\n1\n")

    assert result.exit_code == 0
    assert captured_calls == [
        {
            "runtime": target_descriptor.runtime_name,
            "is_global": False,
            "target_dir_override": None,
        }
    ]


def test_install_interactive_accepts_catalog_runtime_flag(tmp_path: Path) -> None:
    """Interactive install should reuse the shared runtime normalizer for catalog flags."""
    target_descriptor, selection_flag = _descriptor_with_runtime_selection_flag()
    competing_descriptor = next(
        descriptor
        for descriptor in _INSTALL_TEST_DESCRIPTORS
        if descriptor.runtime_name != target_descriptor.runtime_name
    )

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
        patch(
            "gpd.adapters.list_runtimes",
            return_value=[target_descriptor.runtime_name, competing_descriptor.runtime_name],
        ),
        patch("gpd.adapters.get_adapter") as mock_get,
    ):
        adapters = {
            descriptor.runtime_name: _mock_install_adapter(descriptor)
            for descriptor in (target_descriptor, competing_descriptor)
        }
        mock_get.side_effect = lambda runtime: adapters[runtime]

        result = runner.invoke(app, ["install"], input=f"{selection_flag}\n1\n")

    assert result.exit_code == 0
    assert captured_calls == [
        {
            "runtime": target_descriptor.runtime_name,
            "is_global": False,
            "target_dir_override": None,
        }
    ]


def test_install_interactive_accepts_exact_runtime_display_name_before_fuzzy(tmp_path: Path) -> None:
    """An exact display-name match should win before any fuzzy fallback."""
    target_descriptor = _PRIMARY_INSTALL_DESCRIPTOR
    competing_descriptor = _SECONDARY_INSTALL_DESCRIPTOR
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

    target_adapter = _mock_install_adapter(target_descriptor, display_name="Open Code")
    competing_adapter = _mock_install_adapter(competing_descriptor, display_name="Open Code Plus")

    with (
        patch("gpd.cli._install_single_runtime", side_effect=mock_install_single),
        patch(
            "gpd.adapters.list_runtimes",
            return_value=[target_descriptor.runtime_name, competing_descriptor.runtime_name],
        ),
        patch("gpd.adapters.get_adapter") as mock_get,
    ):
        mock_get.side_effect = lambda runtime: {
            target_descriptor.runtime_name: target_adapter,
            competing_descriptor.runtime_name: competing_adapter,
        }[runtime]

        result = runner.invoke(app, ["install"], input="Open Code\n1\n")

    assert result.exit_code == 0
    assert captured_calls == [
        {
            "runtime": target_descriptor.runtime_name,
            "is_global": False,
            "target_dir_override": None,
        }
    ]


def test_install_interactive_accepts_exact_runtime_selection_alias_before_fuzzy(tmp_path: Path) -> None:
    """An exact selection alias should win before any fuzzy fallback."""
    target_descriptor, selection_alias = _descriptor_with_spaced_selection_alias()
    competing_descriptor = _SECONDARY_INSTALL_DESCRIPTOR
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

    target_adapter = _mock_install_adapter(
        target_descriptor,
        display_name=target_descriptor.display_name,
        selection_aliases=(selection_alias,),
    )
    competing_adapter = _mock_install_adapter(
        competing_descriptor,
        display_name=f"{target_descriptor.display_name} Plus",
    )

    with (
        patch("gpd.cli._install_single_runtime", side_effect=mock_install_single),
        patch(
            "gpd.adapters.list_runtimes",
            return_value=[target_descriptor.runtime_name, competing_descriptor.runtime_name],
        ),
        patch("gpd.adapters.get_adapter") as mock_get,
    ):
        mock_get.side_effect = lambda runtime: {
            target_descriptor.runtime_name: target_adapter,
            competing_descriptor.runtime_name: competing_adapter,
        }[runtime]

        result = runner.invoke(app, ["install"], input=f"{selection_alias}\n1\n")

    assert result.exit_code == 0
    assert captured_calls == [
        {
            "runtime": target_descriptor.runtime_name,
            "is_global": False,
            "target_dir_override": None,
        }
    ]


def test_install_accepts_runtime_display_name_alias(tmp_path: Path) -> None:
    """Non-interactive install should accept runtime display-name aliases."""
    target_descriptor = _PRIMARY_INSTALL_DESCRIPTOR
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

    mock_adapter = _mock_install_adapter(target_descriptor)

    with (
        patch("gpd.cli._install_single_runtime", side_effect=mock_install_single),
        patch("gpd.adapters.get_adapter", return_value=mock_adapter),
    ):
        result = runner.invoke(app, ["install", target_descriptor.display_name, "--local"])

    assert result.exit_code == 0
    assert captured_calls == [
        {
            "runtime": target_descriptor.runtime_name,
            "is_global": False,
            "target_dir_override": None,
        }
    ]


def test_uninstall_accepts_runtime_selection_alias(tmp_path: Path) -> None:
    """Non-interactive uninstall should accept runtime selection aliases."""
    target_descriptor, selection_alias = _descriptor_with_spaced_selection_alias()
    target = tmp_path / target_descriptor.config_dir_name
    target.mkdir()
    captured_targets: list[Path] = []

    class SpyAdapter:
        display_name = target_descriptor.display_name

        def uninstall(self, target_dir):
            captured_targets.append(target_dir)
            return {"runtime": target_descriptor.runtime_name, "removed": []}

    with patch("gpd.adapters.get_adapter", return_value=SpyAdapter()):
        result = runner.invoke(app, ["uninstall", selection_alias, "--target-dir", str(target), "--yes"])

    assert result.exit_code == 0
    assert captured_targets == [target]


def test_install_interactive_rejects_invalid_location_choice(tmp_path: Path):
    """Interactive location selection should reject invalid choices instead of defaulting to local."""

    def mock_install_single(runtime_name, *, is_global, target_dir_override=None):
        return {"runtime": runtime_name, "commands": 5, "agents": 3, "target": str(tmp_path / runtime_name)}

    with (
        patch("gpd.cli._install_single_runtime", side_effect=mock_install_single),
        patch("gpd.adapters.get_adapter") as mock_get,
        patch("gpd.adapters.list_runtimes", return_value=[_PRIMARY_INSTALL_DESCRIPTOR.runtime_name]),
    ):
        mock_adapter = MagicMock()
        mock_adapter.display_name = _PRIMARY_INSTALL_DESCRIPTOR.display_name
        mock_adapter.selection_aliases = _install_adapter().selection_aliases
        mock_get.return_value = mock_adapter

        result = runner.invoke(app, ["install"], input="1\n9\n")

    assert result.exit_code == 1
    assert "Invalid selection: '9'" in result.output


@pytest.mark.parametrize(
    ("argv_suffix", "supported_runtimes", "expected_runtimes", "uses_target_dir"),
    [
        (
            [_PRIMARY_INSTALL_DESCRIPTOR.runtime_name, "--local"],
            [_PRIMARY_INSTALL_DESCRIPTOR.runtime_name],
            [_PRIMARY_INSTALL_DESCRIPTOR.runtime_name],
            False,
        ),
        (
            ["--all", "--local"],
            [_PRIMARY_INSTALL_DESCRIPTOR.runtime_name, _SECONDARY_INSTALL_DESCRIPTOR.runtime_name],
            [_PRIMARY_INSTALL_DESCRIPTOR.runtime_name, _SECONDARY_INSTALL_DESCRIPTOR.runtime_name],
            False,
        ),
        (
            [_PRIMARY_INSTALL_DESCRIPTOR.runtime_name, "--local", "--force-statusline"],
            [_PRIMARY_INSTALL_DESCRIPTOR.runtime_name],
            [_PRIMARY_INSTALL_DESCRIPTOR.runtime_name],
            False,
        ),
        (
            [_PRIMARY_INSTALL_DESCRIPTOR.runtime_name, "--local", "--target-dir", "__TARGET__"],
            [_PRIMARY_INSTALL_DESCRIPTOR.runtime_name],
            [_PRIMARY_INSTALL_DESCRIPTOR.runtime_name],
            True,
        ),
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
        mock_adapter = _mock_install_adapter(_PRIMARY_INSTALL_DESCRIPTOR, display_name="Test")
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
    result = runner.invoke(app, ["install", _PRIMARY_INSTALL_DESCRIPTOR.runtime_name, "--global", "--local"])
    assert result.exit_code == 1
    assert "Cannot specify both" in result.output


def test_install_rejects_explicit_runtimes_with_all() -> None:
    """`--all` cannot be combined with explicit runtime arguments on install."""
    with (
        patch("gpd.cli._install_single_runtime") as mock_install_single,
        patch("gpd.adapters.list_runtimes") as mock_list_runtimes,
    ):
        result = runner.invoke(app, ["install", _PRIMARY_INSTALL_DESCRIPTOR.runtime_name, "--all", "--local"])

    assert result.exit_code == 1
    assert "Cannot combine explicit runtimes with --all for install" in result.output
    mock_install_single.assert_not_called()
    mock_list_runtimes.assert_not_called()


def test_install_target_dir_rejects_multiple_runtimes(tmp_path: Path):
    """Explicit target dirs are only safe for a single runtime."""
    result = runner.invoke(
        app,
        [
            "install",
            _PRIMARY_INSTALL_DESCRIPTOR.runtime_name,
            _SECONDARY_INSTALL_DESCRIPTOR.runtime_name,
            "--target-dir",
            str(tmp_path / "shared"),
        ],
    )

    assert result.exit_code == 1
    assert "--target-dir requires exactly one runtime for install" in result.output


def test_install_target_dir_rejects_all_runtimes(tmp_path: Path):
    """`--all` plus an explicit target dir is also unsafe."""
    with patch(
        "gpd.adapters.list_runtimes",
        return_value=[_PRIMARY_INSTALL_DESCRIPTOR.runtime_name, _SECONDARY_INSTALL_DESCRIPTOR.runtime_name],
    ):
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
        return {"runtime": runtime_name, "commands": 5, "agents": 3, "target": str(_install_target(tmp_path))}

    with (
        patch(
            "gpd.adapters.list_runtimes",
            return_value=[_PRIMARY_INSTALL_DESCRIPTOR.runtime_name, _SECONDARY_INSTALL_DESCRIPTOR.runtime_name],
        ),
        patch("gpd.cli._install_single_runtime", side_effect=mock_install_single),
        patch("gpd.adapters.get_adapter") as mock_get_adapter,
    ):
        mock_adapter = MagicMock()
        mock_adapter.display_name = _PRIMARY_INSTALL_DESCRIPTOR.display_name
        mock_adapter.help_command = _install_adapter().help_command
        mock_get_adapter.return_value = mock_adapter

        result = runner.invoke(
            app,
            ["install", _PRIMARY_INSTALL_DESCRIPTOR.runtime_name, _PRIMARY_INSTALL_DESCRIPTOR.runtime_name, "--local"],
        )

    assert result.exit_code == 0
    assert install_calls == [_PRIMARY_INSTALL_DESCRIPTOR.runtime_name]


def test_uninstall_global_and_local_conflict():
    """--global and --local together on uninstall errors."""
    result = runner.invoke(app, ["uninstall", _PRIMARY_INSTALL_DESCRIPTOR.runtime_name, "--global", "--local"])
    assert result.exit_code == 1
    assert "Cannot specify both" in result.output


def test_uninstall_rejects_explicit_runtimes_with_all() -> None:
    """`--all` cannot be combined with explicit runtime arguments on uninstall."""
    with (
        patch("gpd.adapters.get_adapter") as mock_get_adapter,
        patch("gpd.adapters.list_runtimes") as mock_list_runtimes,
    ):
        result = runner.invoke(app, ["uninstall", _PRIMARY_INSTALL_DESCRIPTOR.runtime_name, "--all", "--local"])

    assert result.exit_code == 1
    assert "Cannot combine explicit runtimes with --all for uninstall" in result.output
    mock_get_adapter.assert_not_called()
    mock_list_runtimes.assert_not_called()


def test_uninstall_target_dir_rejects_multiple_runtimes(tmp_path: Path):
    """Explicit target dirs are only safe for a single runtime on uninstall too."""
    result = runner.invoke(
        app,
        [
            "uninstall",
            _PRIMARY_INSTALL_DESCRIPTOR.runtime_name,
            _SECONDARY_INSTALL_DESCRIPTOR.runtime_name,
            "--target-dir",
            str(tmp_path / "shared"),
        ],
        input="n\n",
    )

    assert result.exit_code == 1
    assert "--target-dir requires exactly one runtime for uninstall" in result.output


def test_uninstall_deduplicates_repeated_runtime_args(tmp_path: Path) -> None:
    """Repeated runtime args should only uninstall once per runtime."""
    target = tmp_path / "installed"
    target.mkdir()

    mock_adapter = MagicMock()
    mock_adapter.display_name = _PRIMARY_INSTALL_DESCRIPTOR.display_name
    mock_adapter.uninstall.return_value = {"removed": ["commands"]}

    with (
        patch(
            "gpd.adapters.list_runtimes",
            return_value=[_PRIMARY_INSTALL_DESCRIPTOR.runtime_name, _SECONDARY_INSTALL_DESCRIPTOR.runtime_name],
        ),
        patch("gpd.adapters.get_adapter", return_value=mock_adapter),
    ):
        result = runner.invoke(
            app,
            [
                "--raw",
                "uninstall",
                _PRIMARY_INSTALL_DESCRIPTOR.runtime_name,
                _PRIMARY_INSTALL_DESCRIPTOR.runtime_name,
                "--target-dir",
                str(target),
            ],
        )

    assert result.exit_code == 0
    mock_adapter.uninstall.assert_called_once_with(target)
