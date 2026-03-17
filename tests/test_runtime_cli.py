"""Tests for the shared installed runtime CLI bridge."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

import gpd.cli as cli_module
import gpd.runtime_cli as runtime_cli
from gpd.adapters import get_adapter
from gpd.core.constants import ENV_GPD_ACTIVE_RUNTIME, ENV_GPD_DISABLE_CHECKOUT_REEXEC
from gpd.runtime_cli import _parse_args, _resolve_cli_cwd_from_argv, main


def _mark_complete_install(config_dir: Path, *, runtime: str, install_scope: str = "local") -> None:
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "get-physics-done").mkdir(parents=True, exist_ok=True)
    (config_dir / "gpd-file-manifest.json").write_text(
        json.dumps({"runtime": runtime, "install_scope": install_scope}),
        encoding="utf-8",
    )
    if runtime == "codex":
        skills_dir = config_dir.parent / ".agents" / "skills" / "gpd-dummy"
        skills_dir.mkdir(parents=True, exist_ok=True)
        (skills_dir / "SKILL.md").write_text(
            "---\nname: gpd-dummy\ndescription: dummy\n---\n",
            encoding="utf-8",
        )
        (config_dir / "config.toml").write_text("[agents]\n", encoding="utf-8")
    elif runtime == "gemini":
        (config_dir / "settings.json").write_text(
            json.dumps({"experimental": {"enableAgents": True}}),
            encoding="utf-8",
        )
        policy_dir = config_dir / "policies"
        policy_dir.mkdir(parents=True, exist_ok=True)
        (policy_dir / "gpd-auto-edit.toml").write_text("[[rule]]\n", encoding="utf-8")


def _mark_incomplete_install(config_dir: Path, *, runtime: str, install_scope: str = "local") -> None:
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "gpd-file-manifest.json").write_text(
        json.dumps({"runtime": runtime, "install_scope": install_scope}),
        encoding="utf-8",
    )


def _run_runtime_cli_with_recording(
    monkeypatch,
    *,
    cwd: Path,
    argv: list[str],
    runtime: str = "codex",
) -> tuple[int, dict[str, object]]:
    observed: dict[str, object] = {}
    adapter = get_adapter(runtime)

    def record_missing_install_artifacts(target_dir: Path) -> tuple[str, ...]:
        observed["config_dir"] = target_dir
        return ()

    def fake_entrypoint() -> int:
        observed["argv"] = list(sys.argv)
        observed["runtime"] = os.environ.get(ENV_GPD_ACTIVE_RUNTIME)
        observed["disable_reexec"] = os.environ.get(ENV_GPD_DISABLE_CHECKOUT_REEXEC)
        return 0

    monkeypatch.chdir(cwd)
    monkeypatch.delenv(ENV_GPD_ACTIVE_RUNTIME, raising=False)
    monkeypatch.delenv(ENV_GPD_DISABLE_CHECKOUT_REEXEC, raising=False)
    monkeypatch.setattr(adapter, "missing_install_artifacts", record_missing_install_artifacts)
    monkeypatch.setattr("gpd.runtime_cli.get_adapter", lambda runtime_name: adapter)
    monkeypatch.setattr("gpd.runtime_cli._maybe_reexec_from_checkout", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("gpd.cli.entrypoint", fake_entrypoint)

    return main(argv), observed


@pytest.mark.parametrize("runtime", ["codex", "gemini"])
def test_runtime_cli_fails_cleanly_for_incomplete_install(tmp_path: Path, capsys, runtime: str) -> None:
    adapter = get_adapter(runtime)
    config_dir = tmp_path / adapter.config_dir_name
    config_dir.mkdir()

    exit_code = main(
        [
            "--runtime",
            runtime,
            "--config-dir",
            str(config_dir),
            "--install-scope",
            "local",
            "state",
            "load",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 127
    assert f"GPD runtime install incomplete for {adapter.display_name}" in captured.err
    assert "`gpd-file-manifest.json`" in captured.err
    assert "`get-physics-done`" in captured.err
    assert f"npx -y get-physics-done --{runtime} --local" in captured.err


@pytest.mark.parametrize("runtime", ["codex", "gemini"])
def test_runtime_cli_ancestor_local_repair_command_targets_resolved_install(
    monkeypatch,
    tmp_path: Path,
    capsys,
    runtime: str,
) -> None:
    adapter = get_adapter(runtime)
    config_dir = tmp_path / adapter.config_dir_name
    _mark_incomplete_install(config_dir, runtime=runtime)
    nested_cwd = tmp_path / "research" / "notes"
    nested_cwd.mkdir(parents=True)
    monkeypatch.chdir(nested_cwd)

    exit_code = main(
        [
            "--runtime",
            runtime,
            "--config-dir",
            f"./{adapter.config_dir_name}",
            "--install-scope",
            "local",
            "state",
            "load",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 127
    assert f"--target-dir {config_dir}" in captured.err
    assert f"npx -y get-physics-done --{runtime} --local" in captured.err


@pytest.mark.parametrize("runtime", ["codex", "gemini"])
def test_runtime_cli_dispatches_with_runtime_pin(monkeypatch, tmp_path: Path, runtime: str) -> None:
    adapter = get_adapter(runtime)
    config_dir = tmp_path / adapter.config_dir_name
    _mark_complete_install(config_dir, runtime=runtime)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("gpd.version.checkout_root", lambda start=None: None)

    observed: dict[str, object] = {}

    def fake_entrypoint() -> int:
        observed["argv"] = list(sys.argv)
        observed["runtime"] = os.environ.get(ENV_GPD_ACTIVE_RUNTIME)
        observed["disable_reexec"] = os.environ.get(ENV_GPD_DISABLE_CHECKOUT_REEXEC)
        return 0

    monkeypatch.setattr("gpd.cli.entrypoint", fake_entrypoint)

    exit_code = main(
        [
            "--runtime",
            runtime,
            "--config-dir",
            f"./{adapter.config_dir_name}",
            "--install-scope",
            "local",
            "state",
            "load",
        ]
    )

    assert exit_code == 0
    assert observed["argv"] == ["gpd", "state", "load"]
    assert observed["runtime"] == runtime
    assert observed["disable_reexec"] == "1"


@pytest.mark.parametrize("runtime", ["codex", "gemini"])
def test_runtime_cli_preserves_subcommand_runtime_flags(monkeypatch, tmp_path: Path, runtime: str) -> None:
    adapter = get_adapter(runtime)
    config_dir = tmp_path / adapter.config_dir_name
    _mark_complete_install(config_dir, runtime=runtime)

    exit_code, observed = _run_runtime_cli_with_recording(
        monkeypatch,
        cwd=tmp_path,
        argv=[
            "--runtime",
            runtime,
            "--config-dir",
            str(config_dir),
            "--install-scope",
            "local",
            "resolve-model",
            "gpd-executor",
            "--runtime",
            "gemini",
        ],
        runtime=runtime,
    )

    assert exit_code == 0
    assert observed["argv"] == ["gpd", "resolve-model", "gpd-executor", "--runtime", "gemini"]
    assert observed["runtime"] == runtime


def test_runtime_cli_bridge_parse_preserves_passthrough_after_double_dash() -> None:
    options, gpd_args = _parse_args(
        [
            "--runtime",
            "codex",
            "--config-dir",
            "./.codex",
            "--install-scope",
            "local",
            "--",
            "--raw",
            "state",
            "load",
        ]
    )

    assert options.runtime == "codex"
    assert gpd_args == ["--raw", "state", "load"]


def test_runtime_cli_resolves_cli_cwd_from_equals_style_flag(monkeypatch, tmp_path: Path) -> None:
    launcher_cwd = tmp_path / "launcher"
    launcher_cwd.mkdir()
    forwarded_cwd = tmp_path / "workspace" / "nested"
    forwarded_cwd.mkdir(parents=True)
    monkeypatch.chdir(launcher_cwd)

    assert _resolve_cli_cwd_from_argv(["--cwd=" + str(forwarded_cwd), "state", "load"]) == forwarded_cwd


def test_cli_resolves_cli_cwd_from_last_repeated_flag(monkeypatch, tmp_path: Path) -> None:
    launcher_cwd = tmp_path / "launcher"
    launcher_cwd.mkdir()
    first_cwd = tmp_path / "workspace-a"
    first_cwd.mkdir()
    final_cwd = tmp_path / "workspace-b" / "nested"
    final_cwd.mkdir(parents=True)
    monkeypatch.chdir(launcher_cwd)

    assert cli_module._resolve_cli_cwd_from_argv(
        ["state", "load", "--cwd", str(first_cwd), "--cwd", str(final_cwd)]
    ) == final_cwd


@pytest.mark.parametrize("runtime", ["codex", "gemini"])
def test_runtime_cli_preserves_root_global_flags_before_subcommand(
    monkeypatch,
    tmp_path: Path,
    runtime: str,
) -> None:
    adapter = get_adapter(runtime)
    config_dir = tmp_path / adapter.config_dir_name
    _mark_complete_install(config_dir, runtime=runtime)
    forwarded_cwd = tmp_path / "workspace"
    forwarded_cwd.mkdir()

    exit_code, observed = _run_runtime_cli_with_recording(
        monkeypatch,
        cwd=tmp_path,
        argv=[
            "--runtime",
            runtime,
            "--config-dir",
            str(config_dir),
            "--install-scope",
            "local",
            "--raw",
            "--cwd",
            str(forwarded_cwd),
            "state",
            "load",
        ],
    )

    assert exit_code == 0
    assert observed["argv"] == ["gpd", "--raw", "--cwd", str(forwarded_cwd), "state", "load"]


@pytest.mark.parametrize("runtime", ["codex", "gemini"])
def test_runtime_cli_keeps_double_dash_passthrough_arguments_verbatim(
    monkeypatch,
    tmp_path: Path,
    runtime: str,
) -> None:
    adapter = get_adapter(runtime)
    config_dir = tmp_path / adapter.config_dir_name
    _mark_complete_install(config_dir, runtime=runtime)

    exit_code, observed = _run_runtime_cli_with_recording(
        monkeypatch,
        cwd=tmp_path,
        argv=[
            "--runtime",
            runtime,
            "--config-dir",
            str(config_dir),
            "--install-scope",
            "local",
            "state",
            "load",
            "--",
            "--raw",
            "--cwd",
            "literal",
        ],
    )

    assert exit_code == 0
    assert observed["argv"] == ["gpd", "state", "load", "--", "--raw", "--cwd", "literal"]


def test_runtime_cli_reexecs_from_installed_package_using_forwarded_cli_cwd(monkeypatch, tmp_path: Path) -> None:
    runtime_cwd = tmp_path / "runtime"
    runtime_cwd.mkdir()
    config_dir = runtime_cwd / ".codex"
    _mark_complete_install(config_dir, runtime="codex")

    checkout_root = tmp_path / "checkout"
    checkout_src = checkout_root / "src"
    (checkout_src / "gpd").mkdir(parents=True)
    forwarded_cwd = checkout_root / "workspace" / "nested"
    forwarded_cwd.mkdir(parents=True)
    installed_gpd = tmp_path / "site-packages" / "gpd"
    installed_gpd.mkdir(parents=True)

    observed: dict[str, object] = {}

    def fake_checkout_root(start=None):
        observed["checkout_start"] = start
        if start == forwarded_cwd.resolve(strict=False):
            return checkout_root
        return None

    def fake_execve(executable: str, argv: list[str], env: dict[str, str]) -> None:
        observed["execve_executable"] = executable
        observed["execve_argv"] = argv
        observed["execve_env"] = env
        raise RuntimeError("runtime-cli-reexec")

    monkeypatch.chdir(runtime_cwd)
    monkeypatch.delenv(ENV_GPD_DISABLE_CHECKOUT_REEXEC, raising=False)
    monkeypatch.setenv("PYTHONPATH", "/managed/site-packages")
    monkeypatch.setattr(runtime_cli, "__file__", str(installed_gpd / "runtime_cli.py"))
    monkeypatch.setattr("gpd.version.checkout_root", fake_checkout_root)
    monkeypatch.setattr("gpd.runtime_cli.os.execve", fake_execve)

    with pytest.raises(RuntimeError, match="runtime-cli-reexec"):
        main(
            [
                "--runtime",
                "codex",
                "--config-dir",
                "./.codex",
                "--install-scope",
                "local",
                "state",
                "load",
                "--cwd",
                str(forwarded_cwd),
            ]
        )

    assert observed["checkout_start"] == forwarded_cwd.resolve(strict=False)
    assert observed["execve_executable"] == sys.executable
    assert observed["execve_argv"] == [
        sys.executable,
        "-m",
        "gpd.runtime_cli",
        "--runtime",
        "codex",
        "--config-dir",
        "./.codex",
        "--install-scope",
        "local",
        "state",
        "load",
        "--cwd",
        str(forwarded_cwd),
    ]
    assert observed["execve_env"][ENV_GPD_DISABLE_CHECKOUT_REEXEC] == "1"
    assert observed["execve_env"]["PYTHONPATH"].split(os.pathsep)[:2] == [
        str(checkout_src.resolve(strict=False)),
        "/managed/site-packages",
    ]


def test_runtime_cli_resolves_local_config_dir_from_ancestor_workspace(monkeypatch, tmp_path: Path) -> None:
    config_dir = tmp_path / ".codex"
    _mark_complete_install(config_dir, runtime="codex")
    nested_cwd = tmp_path / "research" / "notes"
    nested_cwd.mkdir(parents=True)
    monkeypatch.chdir(nested_cwd)
    monkeypatch.setattr("gpd.version.checkout_root", lambda start=None: None)

    observed: dict[str, object] = {}

    def fake_entrypoint() -> int:
        observed["argv"] = list(sys.argv)
        observed["runtime"] = os.environ.get(ENV_GPD_ACTIVE_RUNTIME)
        return 0

    monkeypatch.setattr("gpd.cli.entrypoint", fake_entrypoint)

    exit_code = main(
        [
            "--runtime",
            "codex",
            "--config-dir",
            "./.codex",
            "--install-scope",
            "local",
            "state",
            "load",
        ]
    )

    assert exit_code == 0
    assert observed["argv"] == ["gpd", "state", "load"]
    assert observed["runtime"] == "codex"


def test_runtime_cli_resolves_local_config_dir_from_forwarded_cli_cwd(monkeypatch, tmp_path: Path) -> None:
    launcher_cwd = tmp_path / "runtime"
    launcher_cwd.mkdir()
    workspace_root = tmp_path / "project"
    config_dir = workspace_root / ".codex"
    _mark_complete_install(config_dir, runtime="codex")
    forwarded_cwd = workspace_root / "research" / "notes"
    forwarded_cwd.mkdir(parents=True)

    exit_code, observed = _run_runtime_cli_with_recording(
        monkeypatch,
        cwd=launcher_cwd,
        argv=[
            "--runtime",
            "codex",
            "--config-dir",
            "./.codex",
            "--install-scope",
            "local",
            "state",
            "load",
            "--cwd",
            str(forwarded_cwd),
        ],
    )

    assert exit_code == 0
    assert observed["config_dir"] == config_dir
    assert observed["argv"] == ["gpd", "state", "load", "--cwd", str(forwarded_cwd)]
    assert observed["runtime"] == "codex"
    assert observed["disable_reexec"] == "1"


def test_runtime_cli_uses_last_repeated_forwarded_cli_cwd_for_bridge_resolution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    launcher_cwd = tmp_path / "runtime"
    launcher_cwd.mkdir()
    ignored_cwd = tmp_path / "ignored" / "notes"
    ignored_cwd.mkdir(parents=True)
    workspace_root = tmp_path / "project"
    config_dir = workspace_root / ".codex"
    _mark_complete_install(config_dir, runtime="codex")
    final_cwd = workspace_root / "research" / "notes"
    final_cwd.mkdir(parents=True)

    observed: dict[str, object] = {}

    def fake_entrypoint() -> int:
        observed["argv"] = list(sys.argv)
        observed["runtime"] = os.environ.get(ENV_GPD_ACTIVE_RUNTIME)
        observed["disable_reexec"] = os.environ.get(ENV_GPD_DISABLE_CHECKOUT_REEXEC)
        return 0

    monkeypatch.chdir(launcher_cwd)
    monkeypatch.setattr("gpd.runtime_cli._maybe_reexec_from_checkout", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("gpd.cli.entrypoint", fake_entrypoint)

    exit_code = main(
        [
            "--runtime",
            "codex",
            "--config-dir",
            "./.codex",
            "--install-scope",
            "local",
            "state",
            "load",
            "--cwd",
            str(ignored_cwd),
            "--cwd",
            str(final_cwd),
        ]
    )

    assert exit_code == 0
    assert observed["argv"] == ["gpd", "state", "load", "--cwd", str(ignored_cwd), "--cwd", str(final_cwd)]
    assert observed["runtime"] == "codex"
    assert observed["disable_reexec"] == "1"


def test_runtime_cli_forwarded_cli_cwd_drives_local_repair_guidance(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    launcher_cwd = tmp_path / "runtime"
    launcher_cwd.mkdir()
    workspace_root = tmp_path / "project"
    config_dir = workspace_root / ".codex"
    _mark_incomplete_install(config_dir, runtime="codex")
    forwarded_cwd = workspace_root / "research" / "notes"
    forwarded_cwd.mkdir(parents=True)

    monkeypatch.chdir(launcher_cwd)
    monkeypatch.setattr("gpd.runtime_cli._maybe_reexec_from_checkout", lambda *_args, **_kwargs: None)

    exit_code = main(
        [
            "--runtime",
            "codex",
            "--config-dir",
            "./.codex",
            "--install-scope",
            "local",
            "state",
            "load",
            "--cwd",
            str(forwarded_cwd),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 127
    assert f"--target-dir {config_dir}" in captured.err
    assert "npx -y get-physics-done --codex --local" in captured.err


@pytest.mark.parametrize("runtime, foreign_runtime", [("codex", "claude-code"), ("gemini", "opencode")])
def test_runtime_cli_fails_when_resolved_local_config_dir_manifest_runtime_mismatches(
    monkeypatch,
    tmp_path: Path,
    capsys,
    runtime: str,
    foreign_runtime: str,
) -> None:
    adapter = get_adapter(runtime)
    config_dir = tmp_path / adapter.config_dir_name
    _mark_complete_install(config_dir, runtime=foreign_runtime)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("gpd.runtime_cli._maybe_reexec_from_checkout", lambda *_args, **_kwargs: None)

    exit_code = main(
        [
            "--runtime",
            runtime,
            "--config-dir",
            f"./{adapter.config_dir_name}",
            "--install-scope",
            "local",
            "state",
            "load",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 127
    assert f"GPD runtime bridge mismatch for {adapter.display_name}" in captured.err
    assert f"{get_adapter(foreign_runtime).display_name} (`{foreign_runtime}`)" in captured.err
    assert f"npx -y get-physics-done --{runtime} --local" in captured.err


@pytest.mark.parametrize("runtime, foreign_runtime", [("codex", "claude-code"), ("gemini", "opencode")])
def test_runtime_cli_fails_when_explicit_target_manifest_runtime_mismatches(
    monkeypatch,
    tmp_path: Path,
    capsys,
    runtime: str,
    foreign_runtime: str,
) -> None:
    adapter = get_adapter(runtime)
    config_dir = tmp_path / f"custom-{runtime}-dir"
    _mark_complete_install(config_dir, runtime=foreign_runtime)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("gpd.runtime_cli._maybe_reexec_from_checkout", lambda *_args, **_kwargs: None)

    exit_code = main(
        [
            "--runtime",
            runtime,
            "--config-dir",
            str(config_dir),
            "--install-scope",
            "local",
            "--explicit-target",
            "state",
            "load",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 127
    assert f"GPD runtime bridge mismatch for {adapter.display_name}" in captured.err
    assert f"{get_adapter(foreign_runtime).display_name} (`{foreign_runtime}`)" in captured.err
    assert f"--target-dir {config_dir}" in captured.err


def test_runtime_cli_ignores_unrelated_nested_runtime_dirs_when_resolving_ancestor_local_install(
    monkeypatch,
    tmp_path: Path,
) -> None:
    config_dir = tmp_path / ".codex"
    _mark_complete_install(config_dir, runtime="codex")
    _mark_complete_install(tmp_path / "research" / ".claude", runtime="claude-code")
    _mark_complete_install(tmp_path / "research" / "notes" / ".gemini", runtime="gemini")
    nested_cwd = tmp_path / "research" / "notes" / "drafts"
    nested_cwd.mkdir(parents=True)

    exit_code, observed = _run_runtime_cli_with_recording(
        monkeypatch,
        cwd=nested_cwd,
        argv=[
            "--runtime",
            "codex",
            "--config-dir",
            "./.codex",
            "--install-scope",
            "local",
            "state",
            "load",
        ],
    )

    assert exit_code == 0
    assert observed["config_dir"] == config_dir
    assert observed["argv"] == ["gpd", "state", "load"]
    assert observed["runtime"] == "codex"
    assert observed["disable_reexec"] == "1"


def test_runtime_cli_ignores_global_scope_candidates_when_resolving_ancestor_local_install(
    monkeypatch,
    tmp_path: Path,
) -> None:
    config_dir = tmp_path / ".codex"
    _mark_complete_install(config_dir, runtime="codex")
    global_dir = tmp_path / "home" / ".codex"
    _mark_complete_install(global_dir, runtime="codex", install_scope="global")
    nested_cwd = tmp_path / "research" / "notes"
    nested_cwd.mkdir(parents=True)
    monkeypatch.setenv("CODEX_CONFIG_DIR", str(global_dir))

    exit_code, observed = _run_runtime_cli_with_recording(
        monkeypatch,
        cwd=nested_cwd,
        argv=[
            "--runtime",
            "codex",
            "--config-dir",
            "./.codex",
            "--install-scope",
            "local",
            "state",
            "load",
        ],
    )

    assert exit_code == 0
    assert observed["config_dir"] == config_dir
    assert observed["argv"] == ["gpd", "state", "load"]
    assert observed["runtime"] == "codex"
    assert observed["disable_reexec"] == "1"
