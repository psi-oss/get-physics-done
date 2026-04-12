"""Fast smoke tests for runtime install/update wiring."""

from __future__ import annotations

import shlex
from pathlib import Path

import pytest

from gpd.adapters import get_adapter
from gpd.adapters.runtime_catalog import iter_runtime_descriptors
from gpd.runtime_cli import (
    _build_repair_command,
    _is_matching_local_install_candidate,
    _resolve_local_config_dir,
    main,
)
from tests.runtime_install_helpers import seed_complete_runtime_install

_DESCRIPTORS = tuple(iter_runtime_descriptors())
if len(_DESCRIPTORS) < 2:
    pytest.skip("Need at least two runtimes for install smoke coverage", allow_module_level=True)

_PRIMARY_RUNTIME = _DESCRIPTORS[0].runtime_name
_SECONDARY_RUNTIME = _DESCRIPTORS[1].runtime_name


def _disable_checkout_reexec(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("gpd.runtime_cli._maybe_reexec_from_checkout", lambda *_args, **_kwargs: None)


def _guard_entrypoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "gpd.cli.entrypoint",
        lambda: (_ for _ in ()).throw(AssertionError("entrypoint should not run")),
    )


def test_resolve_local_config_dir_prefers_matching_ancestor(tmp_path: Path) -> None:
    adapter = get_adapter(_PRIMARY_RUNTIME)
    workspace = tmp_path / "workspace"
    ancestor = workspace / adapter.config_dir_name
    nested_cwd = workspace / "research" / "notes"
    nested_cwd.mkdir(parents=True)

    seed_complete_runtime_install(ancestor, runtime=_PRIMARY_RUNTIME)

    assert _resolve_local_config_dir(f"./{adapter.config_dir_name}", runtime=_PRIMARY_RUNTIME, cli_cwd=nested_cwd) == ancestor.resolve()


def test_resolve_local_config_dir_rejects_marker_only_candidate(tmp_path: Path) -> None:
    adapter = get_adapter(_PRIMARY_RUNTIME)
    workspace = tmp_path / "workspace"
    ancestor = workspace / adapter.config_dir_name
    nested_cwd = workspace / "research" / "notes"
    nested_cwd.mkdir(parents=True)
    ancestor.mkdir(parents=True)

    (ancestor / "get-physics-done").mkdir(parents=True)
    (ancestor / "get-physics-done" / "VERSION").write_text("1.0.0\n", encoding="utf-8")

    relative = f"./{adapter.config_dir_name}"
    assert _is_matching_local_install_candidate(ancestor, runtime=_PRIMARY_RUNTIME) is False
    resolved = _resolve_local_config_dir(relative, runtime=_PRIMARY_RUNTIME, cli_cwd=nested_cwd)
    expected = (nested_cwd.resolve(strict=False) / adapter.config_dir_name).resolve(strict=False)
    assert resolved == expected


def test_runtime_cli_rejects_manifestless_ancestor_install(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys) -> None:
    adapter = get_adapter(_PRIMARY_RUNTIME)
    workspace = tmp_path / "workspace"
    ancestor = workspace / adapter.config_dir_name
    nested_cwd = workspace / "research" / "notes"
    nested_cwd.mkdir(parents=True)

    seed_complete_runtime_install(ancestor, runtime=_PRIMARY_RUNTIME)
    (ancestor / "gpd-file-manifest.json").unlink()

    _disable_checkout_reexec(monkeypatch)
    _guard_entrypoint(monkeypatch)
    monkeypatch.chdir(nested_cwd)

    exit_code = main(
        [
            "--runtime",
            _PRIMARY_RUNTIME,
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
    assert f"GPD runtime install incomplete for {adapter.display_name}" in captured.err
    assert adapter.config_dir_name in captured.err
    assert "Missing required install artifacts:" in captured.err
    assert "gpd-file-manifest.json" in captured.err


def test_runtime_cli_rejects_wrong_runtime_manifest_for_explicit_target(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys,
) -> None:
    primary_adapter = get_adapter(_PRIMARY_RUNTIME)
    secondary_adapter = get_adapter(_SECONDARY_RUNTIME)
    target_dir = tmp_path / "explicit-target" / primary_adapter.config_dir_name

    seed_complete_runtime_install(
        target_dir,
        runtime=_SECONDARY_RUNTIME,
        explicit_target=True,
    )

    _disable_checkout_reexec(monkeypatch)
    _guard_entrypoint(monkeypatch)
    monkeypatch.chdir(tmp_path)

    exit_code = main(
        [
            "--runtime",
            _PRIMARY_RUNTIME,
            "--config-dir",
            str(target_dir),
            "--install-scope",
            "local",
            "--explicit-target",
            "state",
            "load",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 127
    assert f"GPD runtime bridge mismatch for {primary_adapter.display_name} at `{target_dir}`." in captured.err
    assert f"pins {secondary_adapter.display_name} (`{_SECONDARY_RUNTIME}`)" in captured.err
    assert f"--target-dir {shlex.quote(str(target_dir))}" in captured.err


def test_repair_command_projects_target_dir_only_for_explicit_targets(tmp_path: Path) -> None:
    adapter = get_adapter(_PRIMARY_RUNTIME)
    cli_cwd = tmp_path / "workspace" / "notes"
    cli_cwd.mkdir(parents=True)
    implicit_target = cli_cwd / adapter.config_dir_name
    explicit_target = tmp_path / "explicit-target" / adapter.config_dir_name

    implicit_command = _build_repair_command(
        runtime=_PRIMARY_RUNTIME,
        config_dir=implicit_target,
        install_scope="local",
        explicit_target=False,
        cli_cwd=cli_cwd,
    )
    explicit_command = _build_repair_command(
        runtime=_PRIMARY_RUNTIME,
        config_dir=explicit_target,
        install_scope="local",
        explicit_target=True,
        cli_cwd=cli_cwd,
    )

    assert implicit_command == f"{adapter.update_command} --local"
    assert "--target-dir" not in implicit_command
    assert explicit_command == f"{adapter.update_command} --local --target-dir {shlex.quote(str(explicit_target))}"
