"""Tests for the shared installed runtime CLI bridge."""

from __future__ import annotations

import json
import os
import shlex
import sys
from pathlib import Path

import pytest

import gpd.cli as cli_module
import gpd.runtime_cli as runtime_cli
from gpd.adapters import get_adapter
from gpd.adapters.install_utils import AGENTS_DIR_NAME, HOOKS_DIR_NAME
from gpd.adapters.runtime_catalog import (
    get_shared_install_metadata,
    iter_runtime_descriptors,
    resolve_global_config_dir,
)
from gpd.core.constants import ENV_GPD_ACTIVE_RUNTIME, ENV_GPD_DISABLE_CHECKOUT_REEXEC
from gpd.hooks.install_metadata import GPD_INSTALL_DIR_NAME
from gpd.runtime_cli import _parse_args, _resolve_cli_cwd_from_argv, main
from tests.runtime_install_helpers import seed_complete_runtime_install

_RUNTIME_DESCRIPTORS = tuple(iter_runtime_descriptors())
_RUNTIME_NAMES = tuple(descriptor.runtime_name for descriptor in _RUNTIME_DESCRIPTORS)
_SHARED_INSTALL = get_shared_install_metadata()
MANIFEST_NAME = _SHARED_INSTALL.manifest_name
BOOTSTRAP_COMMAND = _SHARED_INSTALL.bootstrap_command
_RUNTIME_CANONICALIZATION_TOKENS: list[tuple[str, str, str]] = []
_SEEN_CANONICALIZATION_TOKENS: set[tuple[str, str]] = set()
for descriptor in _RUNTIME_DESCRIPTORS:
    if descriptor.display_name.strip() and descriptor.display_name.casefold() != descriptor.runtime_name.casefold():
        token = (descriptor.runtime_name, descriptor.display_name)
        if token not in _SEEN_CANONICALIZATION_TOKENS:
            _SEEN_CANONICALIZATION_TOKENS.add(token)
            _RUNTIME_CANONICALIZATION_TOKENS.append((descriptor.runtime_name, descriptor.display_name, "display_name"))
    for alias in descriptor.selection_aliases:
        if alias.strip() and alias.casefold() != descriptor.runtime_name.casefold():
            token = (descriptor.runtime_name, alias)
            if token not in _SEEN_CANONICALIZATION_TOKENS:
                _SEEN_CANONICALIZATION_TOKENS.add(token)
                _RUNTIME_CANONICALIZATION_TOKENS.append((descriptor.runtime_name, alias, "selection_alias"))
GPD_ROOT = Path(__file__).resolve().parent.parent / "src" / "gpd"


def _runtime_env_prefixes() -> tuple[str, ...]:
    prefixes: set[str] = set()
    for descriptor in _RUNTIME_DESCRIPTORS:
        for env_var in descriptor.activation_env_vars:
            prefixes.add(env_var)
            prefixes.add(env_var.rsplit("_", 1)[0] if "_" in env_var else env_var)
    return tuple(sorted(prefixes, key=len, reverse=True))


def _runtime_env_vars_to_clear() -> set[str]:
    env_vars = {"GPD_ACTIVE_RUNTIME", "XDG_CONFIG_HOME", "CODEX_SKILLS_DIR"}
    for descriptor in _RUNTIME_DESCRIPTORS:
        global_config = descriptor.global_config
        for env_var in (global_config.env_var, global_config.env_dir_var, global_config.env_file_var):
            if env_var:
                env_vars.add(env_var)
    return env_vars


_RUNTIME_ENV_PREFIXES = _runtime_env_prefixes()
_RUNTIME_ENV_VARS_TO_CLEAR = _runtime_env_vars_to_clear()


@pytest.fixture(autouse=True)
def _reset_runtime_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep runtime-CLI tests isolated from ambient runtime env drift."""
    for key in list(os.environ):
        if key.startswith(_RUNTIME_ENV_PREFIXES) or key in _RUNTIME_ENV_VARS_TO_CLEAR:
            monkeypatch.delenv(key, raising=False)


def _mark_complete_install(
    config_dir: Path,
    *,
    runtime: str,
    install_scope: str = "local",
    explicit_target: bool | None = None,
) -> None:
    adapter = get_adapter(runtime)
    seed_complete_runtime_install(
        config_dir,
        runtime=runtime,
        install_scope=install_scope,
        home=config_dir.parent if install_scope == "global" else None,
        explicit_target=(
            explicit_target if explicit_target is not None else config_dir.name != adapter.config_dir_name
        ),
    )


def _mark_incomplete_install(config_dir: Path, *, runtime: str, install_scope: str = "local") -> None:
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / MANIFEST_NAME).write_text(
        json.dumps({"runtime": runtime, "install_scope": install_scope}),
        encoding="utf-8",
    )


def _run_runtime_cli_with_recording(
    monkeypatch,
    *,
    cwd: Path,
    argv: list[str],
    runtime: str = _RUNTIME_NAMES[0],
) -> tuple[int, dict[str, object]]:
    observed: dict[str, object] = {}
    adapter = get_adapter(runtime)
    original_missing_install_artifacts = adapter.missing_install_artifacts

    def record_missing_install_artifacts(target_dir: Path) -> tuple[str, ...]:
        observed["config_dir"] = target_dir
        return original_missing_install_artifacts(target_dir)

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


def test_runtime_cli_returns_stable_error_for_unknown_runtime(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setattr("gpd.runtime_cli._maybe_reexec_from_checkout", lambda *_args, **_kwargs: None)
    monkeypatch.chdir(tmp_path)

    exit_code = main(
        [
            "--runtime",
            "nonexistent-runtime",
            "--config-dir",
            str(tmp_path / "GPD"),
            "--install-scope",
            "global",
            "state",
            "load",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 127
    assert "Unknown runtime 'nonexistent-runtime'" in captured.err
    assert "Supported:" in captured.err


@pytest.mark.parametrize("descriptor", _RUNTIME_DESCRIPTORS, ids=lambda descriptor: descriptor.runtime_name)
def test_runtime_cli_fails_cleanly_for_incomplete_install(tmp_path: Path, capsys, descriptor) -> None:
    adapter = get_adapter(descriptor.runtime_name)
    config_dir = tmp_path / adapter.config_dir_name
    config_dir.mkdir()

    exit_code = main(
        [
            "--runtime",
            descriptor.runtime_name,
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
    assert f"`{MANIFEST_NAME}`" in captured.err
    assert f"`{_SHARED_INSTALL.install_root_dir_name}`" in captured.err
    assert f"{BOOTSTRAP_COMMAND} {adapter.install_flag} --local" in captured.err


@pytest.mark.parametrize("descriptor", _RUNTIME_DESCRIPTORS, ids=lambda descriptor: descriptor.runtime_name)
def test_runtime_cli_ancestor_local_repair_command_targets_resolved_install(
    monkeypatch,
    tmp_path: Path,
    capsys,
    descriptor,
) -> None:
    adapter = get_adapter(descriptor.runtime_name)
    config_dir = tmp_path / adapter.config_dir_name
    _mark_incomplete_install(config_dir, runtime=descriptor.runtime_name)
    nested_cwd = tmp_path / "research" / "notes"
    nested_cwd.mkdir(parents=True)
    monkeypatch.chdir(nested_cwd)

    exit_code = main(
        [
            "--runtime",
            descriptor.runtime_name,
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
    assert f"--target-dir {shlex.quote(str(config_dir))}" in captured.err
    assert f"{BOOTSTRAP_COMMAND} {adapter.install_flag} --local" in captured.err


@pytest.mark.parametrize("descriptor", _RUNTIME_DESCRIPTORS, ids=lambda descriptor: descriptor.runtime_name)
def test_runtime_cli_prefers_nearest_broken_local_install_over_farther_complete_install(
    monkeypatch,
    tmp_path: Path,
    capsys,
    descriptor,
) -> None:
    adapter = get_adapter(descriptor.runtime_name)
    workspace = tmp_path / "workspace"
    nested_cwd = workspace / "research" / "notes"
    nested_cwd.mkdir(parents=True)

    nearer_config_dir = workspace / adapter.config_dir_name
    farther_config_dir = tmp_path / adapter.config_dir_name
    _mark_incomplete_install(nearer_config_dir, runtime=descriptor.runtime_name)
    _mark_complete_install(farther_config_dir, runtime=descriptor.runtime_name)
    monkeypatch.chdir(nested_cwd)
    monkeypatch.setattr("gpd.version.checkout_root", lambda start=None: None)
    monkeypatch.setattr(
        "gpd.cli.entrypoint",
        lambda: (_ for _ in ()).throw(AssertionError("entrypoint should not run for broken nearest installs")),
    )

    exit_code = main(
        [
            "--runtime",
            descriptor.runtime_name,
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
    assert f"GPD runtime install incomplete for {adapter.display_name} at `{nearer_config_dir}`." in captured.err
    assert f"--target-dir {shlex.quote(str(nearer_config_dir))}" in captured.err
    assert str(farther_config_dir) not in captured.err


@pytest.mark.parametrize("descriptor", _RUNTIME_DESCRIPTORS, ids=lambda descriptor: descriptor.runtime_name)
def test_runtime_cli_preserves_custom_global_target_in_incomplete_install_repair_guidance(
    monkeypatch,
    tmp_path: Path,
    capsys,
    descriptor,
) -> None:
    adapter = get_adapter(descriptor.runtime_name)
    config_dir = tmp_path / "custom-global" / descriptor.config_dir_name
    _mark_incomplete_install(config_dir, runtime=descriptor.runtime_name, install_scope="global")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("gpd.version.checkout_root", lambda start=None: None)

    exit_code = main(
        [
            "--runtime",
            descriptor.runtime_name,
            "--config-dir",
            str(config_dir),
            "--install-scope",
            "global",
            "state",
            "load",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 127
    assert f"GPD runtime install incomplete for {adapter.display_name}" in captured.err
    assert "--global" in captured.err
    assert f"--target-dir {shlex.quote(str(config_dir))}" in captured.err


@pytest.mark.parametrize(
    "descriptor",
    [
        descriptor
        for descriptor in _RUNTIME_DESCRIPTORS
        if descriptor.global_config.env_var or descriptor.global_config.env_dir_var or descriptor.global_config.env_file_var
    ],
    ids=lambda descriptor: descriptor.runtime_name,
)
def test_runtime_cli_treats_env_overridden_global_target_as_global_repair_target(
    monkeypatch,
    tmp_path: Path,
    capsys,
    descriptor,
) -> None:
    adapter = get_adapter(descriptor.runtime_name)
    home = tmp_path / "home"
    home.mkdir()
    override_dir = tmp_path / "override-global"
    override_dir.mkdir()
    env_var = descriptor.global_config.env_var or descriptor.global_config.env_dir_var or descriptor.global_config.env_file_var
    assert env_var is not None
    monkeypatch.setenv(env_var, str(override_dir))
    config_dir = adapter.resolve_global_config_dir(home=home)
    _mark_incomplete_install(config_dir, runtime=descriptor.runtime_name, install_scope="global")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("gpd.version.checkout_root", lambda start=None: None)
    monkeypatch.setattr(
        "gpd.cli.entrypoint",
        lambda: (_ for _ in ()).throw(AssertionError("entrypoint should not run for env-global manifests")),
    )

    exit_code = main(
        [
            "--runtime",
            descriptor.runtime_name,
            "--config-dir",
            str(config_dir),
            "--install-scope",
            "global",
            "state",
            "load",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 127
    assert f"GPD runtime install incomplete for {adapter.display_name}" in captured.err
    assert "--global" in captured.err
    assert f"--target-dir {shlex.quote(str(config_dir))}" not in captured.err


@pytest.mark.parametrize("runtime_value", ["", 123, "not-a-runtime"])
@pytest.mark.parametrize("descriptor", _RUNTIME_DESCRIPTORS, ids=lambda descriptor: descriptor.runtime_name)
def test_runtime_cli_fails_when_manifest_runtime_is_missing_or_unrecognized(
    monkeypatch,
    tmp_path: Path,
    capsys,
    descriptor,
    runtime_value,
) -> None:
    adapter = get_adapter(descriptor.runtime_name)
    config_dir = tmp_path / adapter.config_dir_name
    _mark_complete_install(config_dir, runtime=descriptor.runtime_name)
    manifest_path = config_dir / MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["runtime"] = runtime_value
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("gpd.version.checkout_root", lambda start=None: None)
    monkeypatch.setattr(
        "gpd.cli.entrypoint",
        lambda: (_ for _ in ()).throw(AssertionError("entrypoint should not run for malformed manifests")),
    )

    exit_code = main(
        [
            "--runtime",
            descriptor.runtime_name,
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
    if runtime_value == "not-a-runtime":
        assert "GPD runtime bridge found unsupported runtime `not-a-runtime`" in captured.err
        assert "this GPD version has no adapter for it" in captured.err
    else:
        assert "GPD runtime bridge rejected malformed install manifest" in captured.err
        assert "The manifest `runtime` field must be a recognized non-empty runtime string." in captured.err
    assert "Repair or reinstall with" in captured.err


@pytest.mark.parametrize("descriptor", _RUNTIME_DESCRIPTORS, ids=lambda descriptor: descriptor.runtime_name)
def test_runtime_cli_fails_when_manifest_runtime_field_is_missing(
    monkeypatch,
    tmp_path: Path,
    capsys,
    descriptor,
) -> None:
    adapter = get_adapter(descriptor.runtime_name)
    config_dir = tmp_path / adapter.config_dir_name
    _mark_complete_install(config_dir, runtime=descriptor.runtime_name)
    manifest_path = config_dir / MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.pop("runtime", None)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("gpd.version.checkout_root", lambda start=None: None)
    monkeypatch.setattr(
        "gpd.cli.entrypoint",
        lambda: (_ for _ in ()).throw(AssertionError("entrypoint should not run for runtime-less manifests")),
    )

    exit_code = main(
        [
            "--runtime",
            descriptor.runtime_name,
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
    assert "GPD runtime bridge rejected incomplete install manifest" in captured.err
    assert "The manifest must declare a non-empty `runtime` field." in captured.err
    assert "Repair or reinstall with:" in captured.err


@pytest.mark.parametrize("descriptor", _RUNTIME_DESCRIPTORS, ids=lambda descriptor: descriptor.runtime_name)
def test_runtime_cli_preserves_custom_global_target_in_missing_runtime_repair_guidance(
    monkeypatch,
    tmp_path: Path,
    capsys,
    descriptor,
) -> None:
    config_dir = tmp_path / "custom-global" / descriptor.config_dir_name
    _mark_complete_install(config_dir, runtime=descriptor.runtime_name, install_scope="global")
    manifest_path = config_dir / MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.pop("runtime", None)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("gpd.version.checkout_root", lambda start=None: None)
    monkeypatch.setattr(
        "gpd.cli.entrypoint",
        lambda: (_ for _ in ()).throw(AssertionError("entrypoint should not run for runtime-less manifests")),
    )

    exit_code = main(
        [
            "--runtime",
            descriptor.runtime_name,
            "--config-dir",
            str(config_dir),
            "--install-scope",
            "global",
            "state",
            "load",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 127
    assert "GPD runtime bridge rejected incomplete install manifest" in captured.err
    assert "--global" in captured.err
    assert f"--target-dir {shlex.quote(str(config_dir))}" in captured.err


def test_codex_custom_global_install_seeding_stays_within_temp_root(monkeypatch, tmp_path: Path) -> None:
    outside_root = tmp_path.parent / "codex-skills-leak"
    leak_skills_dir = outside_root / ".agents" / "skills"
    monkeypatch.setenv("CODEX_SKILLS_DIR", str(leak_skills_dir))

    adapter = get_adapter("codex")
    config_dir = tmp_path / "custom-global" / adapter.config_dir_name
    _mark_complete_install(config_dir, runtime=adapter.runtime_name, install_scope="global")

    safe_skills_dir = config_dir.parent / ".agents" / "skills"
    assert safe_skills_dir.is_relative_to(tmp_path)
    assert safe_skills_dir.exists()
    assert not leak_skills_dir.exists()


@pytest.mark.parametrize("descriptor", _RUNTIME_DESCRIPTORS, ids=lambda descriptor: descriptor.runtime_name)
def test_runtime_cli_preserves_custom_global_target_in_malformed_runtime_repair_guidance(
    monkeypatch,
    tmp_path: Path,
    capsys,
    descriptor,
) -> None:
    config_dir = tmp_path / "custom-global" / descriptor.config_dir_name
    _mark_complete_install(config_dir, runtime=descriptor.runtime_name, install_scope="global")
    manifest_path = config_dir / MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["runtime"] = ""
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("gpd.version.checkout_root", lambda start=None: None)
    monkeypatch.setattr(
        "gpd.cli.entrypoint",
        lambda: (_ for _ in ()).throw(AssertionError("entrypoint should not run for malformed manifests")),
    )

    exit_code = main(
        [
            "--runtime",
            descriptor.runtime_name,
            "--config-dir",
            str(config_dir),
            "--install-scope",
            "global",
            "state",
            "load",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 127
    assert "GPD runtime bridge rejected malformed install manifest" in captured.err
    assert "--global" in captured.err
    assert f"--target-dir {shlex.quote(str(config_dir))}" in captured.err


def test_runtime_cli_manifest_scoped_local_candidate_matching_does_not_consult_home(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    adapter = get_adapter("codex")
    local_config_dir = tmp_path / adapter.config_dir_name
    global_config_dir = tmp_path / "custom-global" / adapter.config_dir_name
    local_config_dir.mkdir(parents=True, exist_ok=True)
    global_config_dir.mkdir(parents=True, exist_ok=True)
    (local_config_dir / MANIFEST_NAME).write_text(
        json.dumps(
            {
                "runtime": adapter.runtime_name,
                "install_scope": "local",
                "install_target_dir": str(local_config_dir),
                "explicit_target": False,
            }
        ),
        encoding="utf-8",
    )
    (global_config_dir / MANIFEST_NAME).write_text(
        json.dumps(
            {
                "runtime": adapter.runtime_name,
                "install_scope": "global",
                "install_target_dir": str(global_config_dir),
                "explicit_target": True,
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "gpd.runtime_cli.Path.home",
        lambda: (_ for _ in ()).throw(AssertionError("Path.home should not be consulted")),
    )

    assert runtime_cli._is_matching_local_install_candidate(local_config_dir, runtime=adapter.runtime_name) is True
    assert runtime_cli._is_matching_local_install_candidate(global_config_dir, runtime=adapter.runtime_name) is False


@pytest.mark.parametrize("descriptor", _RUNTIME_DESCRIPTORS, ids=lambda descriptor: descriptor.runtime_name)
def test_runtime_cli_resolves_manifestless_managed_surface_for_diagnostics(
    tmp_path: Path,
    descriptor,
) -> None:
    workspace = tmp_path / "workspace"
    ancestor_config_dir = workspace / descriptor.config_dir_name
    nested_cwd = workspace / "research" / "notes"
    nested_cwd.mkdir(parents=True)

    seed_complete_runtime_install(ancestor_config_dir, runtime=descriptor.runtime_name)
    (ancestor_config_dir / MANIFEST_NAME).unlink()

    resolved = runtime_cli._resolve_local_config_dir(
        f"./{descriptor.config_dir_name}",
        runtime=descriptor.runtime_name,
        cli_cwd=nested_cwd,
    )

    assert resolved == ancestor_config_dir.resolve()
    assert resolved != (nested_cwd / descriptor.config_dir_name).resolve()


@pytest.mark.parametrize("descriptor", _RUNTIME_DESCRIPTORS, ids=lambda descriptor: descriptor.runtime_name)
def test_runtime_cli_uses_manifest_explicit_target_for_repair_guidance(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    descriptor,
) -> None:
    adapter = get_adapter(descriptor.runtime_name)
    config_dir = tmp_path / "custom-global" / adapter.config_dir_name
    config_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = config_dir / MANIFEST_NAME
    manifest_path.write_text(
        json.dumps(
            {
                "install_scope": "global",
                "runtime": adapter.runtime_name,
                "explicit_target": True,
                "install_target_dir": str(config_dir),
            }
        ),
        encoding="utf-8",
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.pop("runtime", None)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    monkeypatch.setattr(
        "gpd.runtime_cli.Path.home",
        lambda: (_ for _ in ()).throw(AssertionError("Path.home should not be consulted")),
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("gpd.version.checkout_root", lambda start=None: None)
    monkeypatch.setattr(
        "gpd.cli.entrypoint",
        lambda: (_ for _ in ()).throw(AssertionError("entrypoint should not run for runtime-less manifests")),
    )

    exit_code = main(
        [
            "--runtime",
            adapter.runtime_name,
            "--config-dir",
            str(config_dir),
            "--install-scope",
            "global",
            "state",
            "load",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 127
    assert "GPD runtime bridge rejected incomplete install manifest" in captured.err
    assert "--target-dir" in captured.err
    assert str(config_dir) in captured.err


@pytest.mark.parametrize("descriptor", _RUNTIME_DESCRIPTORS, ids=lambda descriptor: descriptor.runtime_name)
def test_runtime_cli_infers_target_dir_for_missing_explicit_target_repair_guidance(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    descriptor,
) -> None:
    adapter = get_adapter(descriptor.runtime_name)
    config_dir = tmp_path / "custom-parent" / adapter.config_dir_name
    seed_complete_runtime_install(config_dir, runtime=adapter.runtime_name, explicit_target=True)
    manifest_path = config_dir / MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.pop("runtime", None)
    manifest.pop("explicit_target", None)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("gpd.runtime_cli._maybe_reexec_from_checkout", lambda *_args, **_kwargs: None)

    exit_code = main(
        [
            "--runtime",
            adapter.runtime_name,
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
    assert "GPD runtime bridge rejected incomplete install manifest" in captured.err
    assert "--target-dir" in captured.err
    assert shlex.quote(str(config_dir)) in captured.err


@pytest.mark.parametrize("descriptor", _RUNTIME_DESCRIPTORS, ids=lambda descriptor: descriptor.runtime_name)
def test_runtime_cli_dispatches_with_runtime_pin(monkeypatch, tmp_path: Path, descriptor) -> None:
    adapter = get_adapter(descriptor.runtime_name)
    config_dir = tmp_path / adapter.config_dir_name
    _mark_complete_install(config_dir, runtime=descriptor.runtime_name)
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
            descriptor.runtime_name,
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
    assert observed["runtime"] == descriptor.runtime_name
    assert observed["disable_reexec"] == "1"


@pytest.mark.parametrize(
    ("runtime_name", "runtime_token", "token_kind"),
    _RUNTIME_CANONICALIZATION_TOKENS,
)
def test_runtime_cli_canonicalizes_display_names_and_aliases(
    monkeypatch,
    tmp_path: Path,
    runtime_name: str,
    runtime_token: str,
    token_kind: str,
) -> None:
    adapter = get_adapter(runtime_name)
    config_dir = tmp_path / adapter.config_dir_name
    _mark_complete_install(config_dir, runtime=runtime_name)
    monkeypatch.chdir(tmp_path)
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
            runtime_token,
            "--config-dir",
            f"./{adapter.config_dir_name}",
            "--install-scope",
            "local",
            "state",
            "load",
        ]
    )

    assert exit_code == 0, token_kind
    assert observed["argv"] == ["gpd", "state", "load"]
    assert observed["runtime"] == runtime_name


@pytest.mark.parametrize("descriptor", _RUNTIME_DESCRIPTORS, ids=lambda descriptor: descriptor.runtime_name)
def test_runtime_cli_preserves_subcommand_runtime_flags(monkeypatch, tmp_path: Path, descriptor) -> None:
    adapter = get_adapter(descriptor.runtime_name)
    config_dir = tmp_path / adapter.config_dir_name
    _mark_complete_install(config_dir, runtime=descriptor.runtime_name)
    foreign_runtime = next(name for name in _RUNTIME_NAMES if name != descriptor.runtime_name)

    exit_code, observed = _run_runtime_cli_with_recording(
        monkeypatch,
        cwd=tmp_path,
        argv=[
            "--runtime",
            descriptor.runtime_name,
            "--config-dir",
            str(config_dir),
            "--install-scope",
            "local",
            "resolve-model",
            "gpd-executor",
            "--runtime",
            foreign_runtime,
        ],
        runtime=descriptor.runtime_name,
    )

    assert exit_code == 0
    assert observed["argv"] == ["gpd", "resolve-model", "gpd-executor", "--runtime", foreign_runtime]
    assert observed["runtime"] == descriptor.runtime_name


@pytest.mark.parametrize("descriptor", _RUNTIME_DESCRIPTORS, ids=lambda descriptor: descriptor.runtime_name)
def test_runtime_cli_restores_process_env_after_dispatch(monkeypatch, tmp_path: Path, descriptor) -> None:
    config_dir = tmp_path / descriptor.config_dir_name
    _mark_complete_install(config_dir, runtime=descriptor.runtime_name)
    observed: dict[str, object] = {}

    def fake_entrypoint() -> int:
        observed["runtime"] = os.environ.get(ENV_GPD_ACTIVE_RUNTIME)
        observed["disable_reexec"] = os.environ.get(ENV_GPD_DISABLE_CHECKOUT_REEXEC)
        return 0

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(ENV_GPD_ACTIVE_RUNTIME, "outer-runtime")
    monkeypatch.setenv(ENV_GPD_DISABLE_CHECKOUT_REEXEC, "outer-flag")
    monkeypatch.setattr("gpd.runtime_cli._maybe_reexec_from_checkout", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("gpd.cli.entrypoint", fake_entrypoint)

    exit_code = main(
        [
            "--runtime",
            descriptor.runtime_name,
            "--config-dir",
            str(config_dir),
            "--install-scope",
            "local",
            "state",
            "load",
        ]
    )

    assert exit_code == 0
    assert observed["runtime"] == descriptor.runtime_name
    assert observed["disable_reexec"] == "1"
    assert os.environ[ENV_GPD_ACTIVE_RUNTIME] == "outer-runtime"
    assert os.environ[ENV_GPD_DISABLE_CHECKOUT_REEXEC] == "outer-flag"


def test_runtime_cli_bridge_parse_preserves_passthrough_after_double_dash() -> None:
    descriptor = _RUNTIME_DESCRIPTORS[0]
    options, gpd_args = _parse_args(
        [
            "--runtime",
            descriptor.runtime_name,
            "--config-dir",
            f"./{descriptor.config_dir_name}",
            "--install-scope",
            "local",
            "--",
            "--raw",
            "state",
            "load",
        ]
    )

    assert options.runtime == descriptor.runtime_name
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


@pytest.mark.parametrize("descriptor", _RUNTIME_DESCRIPTORS, ids=lambda descriptor: descriptor.runtime_name)
def test_runtime_cli_preserves_root_global_flags_before_subcommand(
    monkeypatch,
    tmp_path: Path,
    descriptor,
) -> None:
    adapter = get_adapter(descriptor.runtime_name)
    config_dir = tmp_path / adapter.config_dir_name
    _mark_complete_install(config_dir, runtime=descriptor.runtime_name)
    forwarded_cwd = tmp_path / "workspace"
    forwarded_cwd.mkdir()

    exit_code, observed = _run_runtime_cli_with_recording(
        monkeypatch,
        cwd=tmp_path,
        argv=[
            "--runtime",
            descriptor.runtime_name,
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
        runtime=descriptor.runtime_name,
    )

    assert exit_code == 0
    assert observed["argv"] == ["gpd", "--raw", "--cwd", str(forwarded_cwd), "state", "load"]


@pytest.mark.parametrize("descriptor", _RUNTIME_DESCRIPTORS, ids=lambda descriptor: descriptor.runtime_name)
def test_runtime_cli_preserves_forwarded_nested_cwd_for_init_resume(
    monkeypatch,
    tmp_path: Path,
    descriptor,
) -> None:
    adapter = get_adapter(descriptor.runtime_name)
    config_dir = tmp_path / adapter.config_dir_name
    _mark_complete_install(config_dir, runtime=descriptor.runtime_name)
    forwarded_cwd = tmp_path / "workspace" / "nested"
    forwarded_cwd.mkdir(parents=True)

    exit_code, observed = _run_runtime_cli_with_recording(
        monkeypatch,
        cwd=tmp_path,
        argv=[
            "--runtime",
            descriptor.runtime_name,
            "--config-dir",
            str(config_dir),
            "--install-scope",
            "local",
            "--raw",
            "--cwd",
            str(forwarded_cwd),
            "init",
            "resume",
        ],
        runtime=descriptor.runtime_name,
    )

    assert exit_code == 0
    assert observed["argv"] == ["gpd", "--raw", "--cwd", str(forwarded_cwd), "init", "resume"]


@pytest.mark.parametrize("descriptor", _RUNTIME_DESCRIPTORS, ids=lambda descriptor: descriptor.runtime_name)
def test_runtime_cli_keeps_double_dash_passthrough_arguments_verbatim(
    monkeypatch,
    tmp_path: Path,
    descriptor,
) -> None:
    adapter = get_adapter(descriptor.runtime_name)
    config_dir = tmp_path / adapter.config_dir_name
    _mark_complete_install(config_dir, runtime=descriptor.runtime_name)

    exit_code, observed = _run_runtime_cli_with_recording(
        monkeypatch,
        cwd=tmp_path,
        argv=[
            "--runtime",
            descriptor.runtime_name,
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
        runtime=descriptor.runtime_name,
    )

    assert exit_code == 0
    assert observed["argv"] == ["gpd", "state", "load", "--", "--raw", "--cwd", "literal"]


@pytest.mark.parametrize("descriptor", _RUNTIME_DESCRIPTORS, ids=lambda descriptor: descriptor.runtime_name)
def test_runtime_cli_reexecs_from_installed_package_using_forwarded_cli_cwd(
    monkeypatch,
    tmp_path: Path,
    descriptor,
) -> None:
    runtime_cwd = tmp_path / descriptor.runtime_name
    runtime_cwd.mkdir()
    config_dir = runtime_cwd / descriptor.config_dir_name
    _mark_complete_install(config_dir, runtime=descriptor.runtime_name)

    checkout_root = tmp_path / "checkout"
    checkout_src = checkout_root / "src"
    (checkout_src / "gpd").mkdir(parents=True)
    venv_python_rel = Path("Scripts") / "python.exe" if os.name == "nt" else Path("bin") / "python"
    checkout_python = checkout_root / ".venv" / venv_python_rel
    checkout_python.parent.mkdir(parents=True)
    checkout_python.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    forwarded_cwd = checkout_root / "workspace" / "nested"
    forwarded_cwd.mkdir(parents=True)
    installed_gpd = tmp_path / "site-packages" / "gpd"
    installed_gpd.mkdir(parents=True)

    observed: dict[str, object] = {"checkout_calls": []}

    def fake_checkout_root(start=None):
        checkout_calls = observed["checkout_calls"]
        assert isinstance(checkout_calls, list)
        checkout_calls.append(start)
        if start in {forwarded_cwd.resolve(strict=False), checkout_root}:
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
                descriptor.runtime_name,
                "--config-dir",
                f"./{descriptor.config_dir_name}",
                "--install-scope",
                "local",
                "state",
                "load",
                "--cwd",
                str(forwarded_cwd),
            ]
        )

    assert observed["checkout_calls"] == [forwarded_cwd.resolve(strict=False), checkout_root]
    assert observed["execve_executable"] == str(checkout_python)
    assert observed["execve_argv"] == [
        str(checkout_python),
        "-m",
        "gpd.runtime_cli",
        "--runtime",
        descriptor.runtime_name,
        "--config-dir",
        f"./{descriptor.config_dir_name}",
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


@pytest.mark.parametrize("descriptor", _RUNTIME_DESCRIPTORS, ids=lambda descriptor: descriptor.runtime_name)
def test_runtime_cli_resolves_local_config_dir_from_ancestor_workspace(
    monkeypatch,
    tmp_path: Path,
    descriptor,
) -> None:
    config_dir = tmp_path / descriptor.config_dir_name
    _mark_complete_install(config_dir, runtime=descriptor.runtime_name)
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
            descriptor.runtime_name,
            "--config-dir",
            f"./{descriptor.config_dir_name}",
            "--install-scope",
            "local",
            "state",
            "load",
        ]
    )

    assert exit_code == 0
    assert observed["argv"] == ["gpd", "state", "load"]
    assert observed["runtime"] == descriptor.runtime_name


@pytest.mark.parametrize("descriptor", _RUNTIME_DESCRIPTORS, ids=lambda descriptor: descriptor.runtime_name)
def test_runtime_cli_rejects_local_config_dir_from_ancestor_workspace_without_manifest_runtime(
    monkeypatch,
    tmp_path: Path,
    capsys,
    descriptor,
) -> None:
    config_dir = tmp_path / descriptor.config_dir_name
    _mark_complete_install(config_dir, runtime=descriptor.runtime_name)
    manifest_path = config_dir / MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.pop("runtime", None)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    nested_cwd = tmp_path / "research" / "notes"
    nested_cwd.mkdir(parents=True)
    monkeypatch.chdir(nested_cwd)
    monkeypatch.setattr("gpd.version.checkout_root", lambda start=None: None)
    monkeypatch.setattr(
        "gpd.cli.entrypoint",
        lambda: (_ for _ in ()).throw(AssertionError("entrypoint should not run for runtime-less manifests")),
    )

    exit_code = main(
        [
            "--runtime",
            descriptor.runtime_name,
            "--config-dir",
            f"./{descriptor.config_dir_name}",
            "--install-scope",
            "local",
            "state",
            "load",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 127
    assert f"GPD runtime bridge rejected incomplete install manifest at `{config_dir}`." in captured.err
    assert f"--target-dir {shlex.quote(str(config_dir))}" in captured.err
    assert str(nested_cwd / descriptor.config_dir_name) not in captured.err


@pytest.mark.parametrize(
    "descriptor",
    [descriptor for descriptor in _RUNTIME_DESCRIPTORS if descriptor.manifest_file_prefixes],
    ids=lambda descriptor: descriptor.runtime_name,
)
def test_runtime_cli_rejects_local_candidate_with_file_prefixes_but_no_runtime(
    tmp_path: Path,
    descriptor,
) -> None:
    adapter = get_adapter(descriptor.runtime_name)
    candidate = tmp_path / adapter.config_dir_name
    candidate.mkdir()
    manifest_prefix = descriptor.manifest_file_prefixes[0]
    (candidate / MANIFEST_NAME).write_text(
        json.dumps(
            {
                "install_scope": "local",
                "files": {f"{manifest_prefix}artifact.txt": "hash"},
            }
        ),
        encoding="utf-8",
    )

    assert runtime_cli._is_matching_local_install_candidate(
        candidate,
        runtime=descriptor.runtime_name,
    ) is False


@pytest.mark.parametrize("descriptor", _RUNTIME_DESCRIPTORS, ids=lambda descriptor: descriptor.runtime_name)
def test_runtime_cli_rejects_corrupt_manifest_before_dispatch(
    monkeypatch,
    tmp_path: Path,
    capsys,
    descriptor,
) -> None:
    config_dir = tmp_path / descriptor.config_dir_name
    _mark_complete_install(config_dir, runtime=descriptor.runtime_name)
    (config_dir / MANIFEST_NAME).write_text("not-json", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("gpd.version.checkout_root", lambda start=None: None)
    monkeypatch.setattr(
        "gpd.cli.entrypoint",
        lambda: (_ for _ in ()).throw(AssertionError("entrypoint should not run for corrupt manifests")),
    )

    exit_code = main(
        [
            "--runtime",
            descriptor.runtime_name,
            "--config-dir",
            f"./{descriptor.config_dir_name}",
            "--install-scope",
            "local",
            "state",
            "load",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 127
    assert "GPD runtime bridge rejected unreadable install manifest" in captured.err
    assert "must be a JSON object with a non-empty `runtime` field" in captured.err


@pytest.mark.parametrize("descriptor", _RUNTIME_DESCRIPTORS, ids=lambda descriptor: descriptor.runtime_name)
def test_runtime_cli_rejects_missing_manifest_before_dispatch(
    monkeypatch,
    tmp_path: Path,
    capsys,
    descriptor,
) -> None:
    config_dir = tmp_path / descriptor.config_dir_name
    _mark_complete_install(config_dir, runtime=descriptor.runtime_name)
    (config_dir / MANIFEST_NAME).unlink()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("gpd.version.checkout_root", lambda start=None: None)
    monkeypatch.setattr(
        "gpd.cli.entrypoint",
        lambda: (_ for _ in ()).throw(AssertionError("entrypoint should not run for manifestless installs")),
    )

    exit_code = main(
        [
            "--runtime",
            descriptor.runtime_name,
            "--config-dir",
            f"./{descriptor.config_dir_name}",
            "--install-scope",
            "local",
            "state",
            "load",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 127
    assert "GPD runtime bridge rejected missing install manifest" in captured.err
    assert f"`{MANIFEST_NAME}`" in captured.err


@pytest.mark.parametrize("descriptor", _RUNTIME_DESCRIPTORS, ids=lambda descriptor: descriptor.runtime_name)
def test_runtime_cli_rejects_manifestless_ancestor_local_candidate_before_dispatch(
    monkeypatch,
    tmp_path: Path,
    capsys,
    descriptor,
) -> None:
    config_dir = tmp_path / descriptor.config_dir_name
    _mark_complete_install(config_dir, runtime=descriptor.runtime_name)
    (config_dir / MANIFEST_NAME).unlink()
    nested_cwd = tmp_path / "research" / "notes"
    nested_cwd.mkdir(parents=True)
    monkeypatch.chdir(nested_cwd)
    monkeypatch.setattr("gpd.version.checkout_root", lambda start=None: None)
    monkeypatch.setattr(
        "gpd.cli.entrypoint",
        lambda: (_ for _ in ()).throw(AssertionError("entrypoint should not run for manifestless ancestor installs")),
    )

    exit_code = main(
        [
            "--runtime",
            descriptor.runtime_name,
            "--config-dir",
            f"./{descriptor.config_dir_name}",
            "--install-scope",
            "local",
            "state",
            "load",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 127
    assert f"GPD runtime bridge rejected missing install manifest at `{config_dir}`." in captured.err
    assert f"--target-dir {shlex.quote(str(config_dir))}" in captured.err
    assert str(nested_cwd / descriptor.config_dir_name) not in captured.err


@pytest.mark.parametrize("descriptor", _RUNTIME_DESCRIPTORS, ids=lambda descriptor: descriptor.runtime_name)
def test_runtime_cli_prefers_manifest_backed_ancestor_over_nearer_marker_only_candidate(
    monkeypatch,
    tmp_path: Path,
    capsys,
    descriptor,
) -> None:
    adapter = get_adapter(descriptor.runtime_name)
    ancestor_config_dir = tmp_path / descriptor.config_dir_name
    _mark_incomplete_install(ancestor_config_dir, runtime=descriptor.runtime_name)
    nested_cwd = tmp_path / "workspace" / "research" / "notes"
    (nested_cwd / GPD_INSTALL_DIR_NAME).mkdir(parents=True)
    monkeypatch.chdir(nested_cwd)
    monkeypatch.setattr("gpd.version.checkout_root", lambda start=None: None)
    monkeypatch.setattr(
        "gpd.cli.entrypoint",
        lambda: (_ for _ in ()).throw(AssertionError("entrypoint should not run for incomplete manifests")),
    )

    exit_code = main(
        [
            "--runtime",
            descriptor.runtime_name,
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
    assert str(ancestor_config_dir) in captured.err
    assert str(nested_cwd / adapter.config_dir_name) not in captured.err


@pytest.mark.parametrize("managed_surface", [AGENTS_DIR_NAME, HOOKS_DIR_NAME])
@pytest.mark.parametrize("descriptor", _RUNTIME_DESCRIPTORS, ids=lambda descriptor: descriptor.runtime_name)
def test_runtime_cli_rejects_manifestless_torn_managed_surface_before_dispatch(
    monkeypatch,
    tmp_path: Path,
    capsys,
    descriptor,
    managed_surface,
) -> None:
    config_dir = tmp_path / descriptor.config_dir_name
    surface_dir = config_dir / managed_surface
    surface_dir.mkdir(parents=True)
    (surface_dir / "placeholder.txt").write_text("managed-surface", encoding="utf-8")
    nested_cwd = tmp_path / "research" / "notes"
    nested_cwd.mkdir(parents=True)
    monkeypatch.chdir(nested_cwd)
    monkeypatch.setattr("gpd.version.checkout_root", lambda start=None: None)
    monkeypatch.setattr(
        "gpd.cli.entrypoint",
        lambda: (_ for _ in ()).throw(AssertionError("entrypoint should not run for torn managed installs")),
    )

    exit_code = main(
        [
            "--runtime",
            descriptor.runtime_name,
            "--config-dir",
            f"./{descriptor.config_dir_name}",
            "--install-scope",
            "local",
            "state",
            "load",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 127
    assert "GPD runtime install incomplete" in captured.err
    assert descriptor.display_name in captured.err
    assert str(nested_cwd / descriptor.config_dir_name) in captured.err
    assert "GPD runtime bridge rejected missing install manifest" not in captured.err


@pytest.mark.parametrize("descriptor", _RUNTIME_DESCRIPTORS, ids=lambda descriptor: descriptor.runtime_name)
def test_runtime_cli_preserves_custom_global_target_in_untrusted_manifest_repair_guidance(
    monkeypatch,
    tmp_path: Path,
    capsys,
    descriptor,
) -> None:
    config_dir = tmp_path / "custom-global" / descriptor.config_dir_name
    _mark_complete_install(config_dir, runtime=descriptor.runtime_name, install_scope="global")
    (config_dir / MANIFEST_NAME).write_text("not-json", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("gpd.version.checkout_root", lambda start=None: None)
    monkeypatch.setattr(
        "gpd.cli.entrypoint",
        lambda: (_ for _ in ()).throw(AssertionError("entrypoint should not run for corrupt manifests")),
    )

    exit_code = main(
        [
            "--runtime",
            descriptor.runtime_name,
            "--config-dir",
            str(config_dir),
            "--install-scope",
            "global",
            "state",
            "load",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 127
    assert "GPD runtime bridge rejected unreadable install manifest" in captured.err
    assert "--global" in captured.err
    assert f"--target-dir {shlex.quote(str(config_dir))}" in captured.err


@pytest.mark.parametrize("descriptor", _RUNTIME_DESCRIPTORS, ids=lambda descriptor: descriptor.runtime_name)
def test_runtime_cli_rejects_non_utf8_manifest_before_dispatch(
    monkeypatch,
    tmp_path: Path,
    capsys,
    descriptor,
) -> None:
    config_dir = tmp_path / descriptor.config_dir_name
    _mark_complete_install(config_dir, runtime=descriptor.runtime_name)
    (config_dir / MANIFEST_NAME).write_bytes(b"\xff")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("gpd.version.checkout_root", lambda start=None: None)
    monkeypatch.setattr(
        "gpd.cli.entrypoint",
        lambda: (_ for _ in ()).throw(AssertionError("entrypoint should not run for unreadable manifests")),
    )

    exit_code = main(
        [
            "--runtime",
            descriptor.runtime_name,
            "--config-dir",
            f"./{descriptor.config_dir_name}",
            "--install-scope",
            "local",
            "state",
            "load",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 127
    assert "GPD runtime bridge rejected unreadable install manifest" in captured.err
    assert "must be a JSON object with a non-empty `runtime` field" in captured.err


@pytest.mark.parametrize("descriptor", _RUNTIME_DESCRIPTORS, ids=lambda descriptor: descriptor.runtime_name)
def test_runtime_cli_resolves_local_config_dir_from_forwarded_cli_cwd(
    monkeypatch,
    tmp_path: Path,
    descriptor,
) -> None:
    launcher_cwd = tmp_path / "runtime"
    launcher_cwd.mkdir()
    workspace_root = tmp_path / "project"
    config_dir = workspace_root / descriptor.config_dir_name
    _mark_complete_install(config_dir, runtime=descriptor.runtime_name)
    forwarded_cwd = workspace_root / "research" / "notes"
    forwarded_cwd.mkdir(parents=True)

    exit_code, observed = _run_runtime_cli_with_recording(
        monkeypatch,
        cwd=launcher_cwd,
        argv=[
            "--runtime",
            descriptor.runtime_name,
            "--config-dir",
            f"./{descriptor.config_dir_name}",
            "--install-scope",
            "local",
            "state",
            "load",
            "--cwd",
            str(forwarded_cwd),
        ],
        runtime=descriptor.runtime_name,
    )

    assert exit_code == 0
    assert observed["config_dir"] == config_dir
    assert observed["argv"] == ["gpd", "state", "load", "--cwd", str(forwarded_cwd)]
    assert observed["runtime"] == descriptor.runtime_name
    assert observed["disable_reexec"] == "1"


@pytest.mark.parametrize("descriptor", _RUNTIME_DESCRIPTORS, ids=lambda descriptor: descriptor.runtime_name)
def test_runtime_cli_uses_last_repeated_forwarded_cli_cwd_for_bridge_resolution(
    monkeypatch,
    tmp_path: Path,
    descriptor,
) -> None:
    launcher_cwd = tmp_path / "runtime"
    launcher_cwd.mkdir()
    ignored_cwd = tmp_path / "ignored" / "notes"
    ignored_cwd.mkdir(parents=True)
    workspace_root = tmp_path / "project"
    config_dir = workspace_root / descriptor.config_dir_name
    _mark_complete_install(config_dir, runtime=descriptor.runtime_name)
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
            descriptor.runtime_name,
            "--config-dir",
            f"./{descriptor.config_dir_name}",
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
    assert observed["runtime"] == descriptor.runtime_name
    assert observed["disable_reexec"] == "1"


@pytest.mark.parametrize("descriptor", _RUNTIME_DESCRIPTORS, ids=lambda descriptor: descriptor.runtime_name)
def test_runtime_cli_forwarded_cli_cwd_drives_local_repair_guidance(
    monkeypatch,
    tmp_path: Path,
    capsys,
    descriptor,
) -> None:
    launcher_cwd = tmp_path / "runtime"
    launcher_cwd.mkdir()
    workspace_root = tmp_path / "project"
    adapter = get_adapter(descriptor.runtime_name)
    config_dir = workspace_root / descriptor.config_dir_name
    _mark_incomplete_install(config_dir, runtime=descriptor.runtime_name)
    forwarded_cwd = workspace_root / "research" / "notes"
    forwarded_cwd.mkdir(parents=True)

    monkeypatch.chdir(launcher_cwd)
    monkeypatch.setattr("gpd.runtime_cli._maybe_reexec_from_checkout", lambda *_args, **_kwargs: None)

    exit_code = main(
        [
            "--runtime",
            descriptor.runtime_name,
            "--config-dir",
            f"./{descriptor.config_dir_name}",
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
    assert f"--target-dir {shlex.quote(str(config_dir))}" in captured.err
    assert f"{BOOTSTRAP_COMMAND} {adapter.install_flag} --local" in captured.err


@pytest.mark.parametrize("descriptor", _RUNTIME_DESCRIPTORS, ids=lambda descriptor: descriptor.runtime_name)
def test_runtime_cli_fails_when_resolved_local_config_dir_manifest_runtime_mismatches(
    monkeypatch,
    tmp_path: Path,
    capsys,
    descriptor,
) -> None:
    foreign_runtime = next(name for name in _RUNTIME_NAMES if name != descriptor.runtime_name)
    adapter = get_adapter(descriptor.runtime_name)
    config_dir = tmp_path / adapter.config_dir_name
    _mark_complete_install(config_dir, runtime=descriptor.runtime_name)
    manifest_path = config_dir / MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["runtime"] = foreign_runtime
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("gpd.runtime_cli._maybe_reexec_from_checkout", lambda *_args, **_kwargs: None)

    exit_code = main(
        [
            "--runtime",
            descriptor.runtime_name,
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
    assert f"--target-dir {shlex.quote(str(config_dir))}" in captured.err
    assert f"{BOOTSTRAP_COMMAND} {get_adapter(foreign_runtime).install_flag} --local" in captured.err


@pytest.mark.parametrize("descriptor", _RUNTIME_DESCRIPTORS, ids=lambda descriptor: descriptor.runtime_name)
def test_runtime_cli_fails_when_explicit_target_manifest_runtime_mismatches(
    monkeypatch,
    tmp_path: Path,
    capsys,
    descriptor,
) -> None:
    foreign_runtime = next(name for name in _RUNTIME_NAMES if name != descriptor.runtime_name)
    adapter = get_adapter(descriptor.runtime_name)
    config_dir = tmp_path / f"custom-{descriptor.runtime_name}-dir"
    _mark_complete_install(config_dir, runtime=descriptor.runtime_name)
    manifest_path = config_dir / MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["runtime"] = foreign_runtime
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("gpd.runtime_cli._maybe_reexec_from_checkout", lambda *_args, **_kwargs: None)

    exit_code = main(
        [
            "--runtime",
            descriptor.runtime_name,
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
    assert f"--target-dir {shlex.quote(str(config_dir))}" in captured.err
    assert f"{BOOTSTRAP_COMMAND} {get_adapter(foreign_runtime).install_flag} --local" in captured.err


@pytest.mark.parametrize("descriptor", _RUNTIME_DESCRIPTORS, ids=lambda descriptor: descriptor.runtime_name)
def test_runtime_cli_uses_manifest_owner_scope_for_mismatch_repair_guidance(
    monkeypatch,
    tmp_path: Path,
    capsys,
    descriptor,
) -> None:
    foreign_runtime = next(name for name in _RUNTIME_NAMES if name != descriptor.runtime_name)
    config_dir = tmp_path / f"custom-{descriptor.runtime_name}-dir"
    _mark_complete_install(config_dir, runtime=descriptor.runtime_name)
    manifest_path = config_dir / MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["runtime"] = foreign_runtime
    manifest["install_scope"] = "global"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("gpd.runtime_cli._maybe_reexec_from_checkout", lambda *_args, **_kwargs: None)

    exit_code = main(
        [
            "--runtime",
            descriptor.runtime_name,
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
    assert f"GPD runtime bridge mismatch for {get_adapter(descriptor.runtime_name).display_name}" in captured.err
    assert f"{get_adapter(foreign_runtime).display_name} (`{foreign_runtime}`)" in captured.err
    assert f"{BOOTSTRAP_COMMAND} {get_adapter(foreign_runtime).install_flag}" in captured.err
    assert "--global" in captured.err
    assert "--local" not in captured.err


@pytest.mark.parametrize("descriptor", _RUNTIME_DESCRIPTORS, ids=lambda descriptor: descriptor.runtime_name)
def test_runtime_cli_preserves_custom_global_target_in_mismatch_repair_guidance_without_bridge_flag(
    monkeypatch,
    tmp_path: Path,
    capsys,
    descriptor,
) -> None:
    foreign_runtime = next(name for name in _RUNTIME_NAMES if name != descriptor.runtime_name)
    config_dir = tmp_path / "custom-global" / descriptor.config_dir_name
    _mark_complete_install(config_dir, runtime=descriptor.runtime_name, install_scope="global")
    manifest_path = config_dir / MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["runtime"] = foreign_runtime
    manifest["install_scope"] = "global"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("gpd.runtime_cli._maybe_reexec_from_checkout", lambda *_args, **_kwargs: None)

    exit_code = main(
        [
            "--runtime",
            descriptor.runtime_name,
            "--config-dir",
            str(config_dir),
            "--install-scope",
            "global",
            "state",
            "load",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 127
    assert f"GPD runtime bridge mismatch for {get_adapter(descriptor.runtime_name).display_name}" in captured.err
    assert f"{get_adapter(foreign_runtime).display_name} (`{foreign_runtime}`)" in captured.err
    assert "--global" in captured.err
    assert f"--target-dir {shlex.quote(str(config_dir))}" in captured.err


@pytest.mark.parametrize("descriptor", _RUNTIME_DESCRIPTORS, ids=lambda descriptor: descriptor.runtime_name)
def test_runtime_cli_ignores_unrelated_nested_runtime_dirs_when_resolving_ancestor_local_install(
    monkeypatch,
    tmp_path: Path,
    descriptor,
) -> None:
    config_dir = tmp_path / descriptor.config_dir_name
    _mark_complete_install(config_dir, runtime=descriptor.runtime_name)
    for other_descriptor in _RUNTIME_DESCRIPTORS:
        if other_descriptor.runtime_name == descriptor.runtime_name:
            continue
        _mark_complete_install(
            tmp_path / "research" / other_descriptor.config_dir_name,
            runtime=other_descriptor.runtime_name,
        )
    nested_cwd = tmp_path / "research" / "notes" / "drafts"
    nested_cwd.mkdir(parents=True)

    exit_code, observed = _run_runtime_cli_with_recording(
        monkeypatch,
        cwd=nested_cwd,
        argv=[
            "--runtime",
            descriptor.runtime_name,
            "--config-dir",
            f"./{descriptor.config_dir_name}",
            "--install-scope",
            "local",
            "state",
            "load",
        ],
        runtime=descriptor.runtime_name,
    )

    assert exit_code == 0
    assert observed["config_dir"] == config_dir
    assert observed["argv"] == ["gpd", "state", "load"]
    assert observed["runtime"] == descriptor.runtime_name
    assert observed["disable_reexec"] == "1"


@pytest.mark.parametrize("descriptor", _RUNTIME_DESCRIPTORS, ids=lambda descriptor: descriptor.runtime_name)
def test_runtime_cli_skips_stale_partial_nested_local_candidate_when_ancestor_install_exists(
    monkeypatch,
    tmp_path: Path,
    descriptor,
) -> None:
    adapter = get_adapter(descriptor.runtime_name)
    ancestor_config_dir = tmp_path / adapter.config_dir_name
    _mark_complete_install(ancestor_config_dir, runtime=descriptor.runtime_name)
    stale_workspace = tmp_path / "workspace"
    _mark_incomplete_install(stale_workspace / adapter.config_dir_name, runtime=descriptor.runtime_name)
    nested_cwd = stale_workspace / "research" / "notes"
    nested_cwd.mkdir(parents=True)

    exit_code, observed = _run_runtime_cli_with_recording(
        monkeypatch,
        cwd=nested_cwd,
        argv=[
            "--runtime",
            descriptor.runtime_name,
            "--config-dir",
            f"./{adapter.config_dir_name}",
            "--install-scope",
            "local",
            "state",
            "load",
        ],
        runtime=descriptor.runtime_name,
    )

    assert exit_code == 127
    assert observed["config_dir"] == stale_workspace / adapter.config_dir_name
    assert "argv" not in observed
    assert "runtime" not in observed
    assert "disable_reexec" not in observed


@pytest.mark.parametrize("descriptor", _RUNTIME_DESCRIPTORS, ids=lambda descriptor: descriptor.runtime_name)
def test_runtime_cli_ignores_global_scope_candidates_when_resolving_ancestor_local_install(
    monkeypatch,
    tmp_path: Path,
    descriptor,
) -> None:
    config_dir = tmp_path / descriptor.config_dir_name
    _mark_complete_install(config_dir, runtime=descriptor.runtime_name)
    global_dir = tmp_path / "home" / descriptor.config_dir_name
    _mark_complete_install(global_dir, runtime=descriptor.runtime_name, install_scope="global")
    nested_cwd = tmp_path / "research" / "notes"
    nested_cwd.mkdir(parents=True)
    global_config = get_adapter(descriptor.runtime_name).runtime_descriptor.global_config
    env_var = global_config.env_var or global_config.env_dir_var or global_config.env_file_var
    assert env_var is not None
    env_value = str(global_dir / "config.json") if env_var == global_config.env_file_var else str(global_dir)
    monkeypatch.setenv(env_var, env_value)

    exit_code, observed = _run_runtime_cli_with_recording(
        monkeypatch,
        cwd=nested_cwd,
        argv=[
            "--runtime",
            descriptor.runtime_name,
            "--config-dir",
            f"./{descriptor.config_dir_name}",
            "--install-scope",
            "local",
            "state",
            "load",
        ],
        runtime=descriptor.runtime_name,
    )

    assert exit_code == 0
    assert observed["config_dir"] == config_dir
    assert observed["argv"] == ["gpd", "state", "load"]
    assert observed["runtime"] == descriptor.runtime_name
    assert observed["disable_reexec"] == "1"


@pytest.mark.parametrize("descriptor", _RUNTIME_DESCRIPTORS, ids=lambda descriptor: descriptor.runtime_name)
def test_runtime_cli_prefers_manifest_scoped_local_install_when_global_env_points_to_same_dir(
    monkeypatch,
    tmp_path: Path,
    descriptor,
) -> None:
    config_dir = tmp_path / descriptor.config_dir_name
    _mark_complete_install(config_dir, runtime=descriptor.runtime_name, install_scope="local")
    nested_cwd = tmp_path / "research" / "notes"
    nested_cwd.mkdir(parents=True)

    global_config = get_adapter(descriptor.runtime_name).runtime_descriptor.global_config
    env_var = global_config.env_var or global_config.env_dir_var or global_config.env_file_var
    assert env_var is not None
    env_value = str(config_dir / "config.json") if env_var == global_config.env_file_var else str(config_dir)
    monkeypatch.setenv(env_var, env_value)

    exit_code, observed = _run_runtime_cli_with_recording(
        monkeypatch,
        cwd=nested_cwd,
        argv=[
            "--runtime",
            descriptor.runtime_name,
            "--config-dir",
            f"./{descriptor.config_dir_name}",
            "--install-scope",
            "local",
            "state",
            "load",
        ],
        runtime=descriptor.runtime_name,
    )

    assert exit_code == 0
    assert observed["config_dir"] == config_dir
    assert observed["argv"] == ["gpd", "state", "load"]
    assert observed["runtime"] == descriptor.runtime_name
    assert observed["disable_reexec"] == "1"


@pytest.mark.parametrize("descriptor", _RUNTIME_DESCRIPTORS, ids=lambda descriptor: descriptor.runtime_name)
def test_runtime_cli_does_not_treat_canonical_global_dir_as_local_when_runtime_env_overrides_elsewhere(
    monkeypatch,
    tmp_path: Path,
    descriptor,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    canonical_global_dir = resolve_global_config_dir(descriptor, home=home, environ={})
    _mark_complete_install(canonical_global_dir, runtime=descriptor.runtime_name, install_scope="global")

    override_dir = tmp_path / "override" / descriptor.config_dir_name
    override_dir.mkdir(parents=True)
    global_config = descriptor.global_config
    env_var = global_config.env_var or global_config.env_dir_var or global_config.env_file_var
    assert env_var is not None
    env_value = str(override_dir / "config.json") if env_var == global_config.env_file_var else str(override_dir)
    monkeypatch.setenv(env_var, env_value)

    cli_cwd = home / "research" / "notes"
    cli_cwd.mkdir(parents=True)
    expected_missing_target = cli_cwd / descriptor.config_dir_name

    exit_code, observed = _run_runtime_cli_with_recording(
        monkeypatch,
        cwd=cli_cwd,
        argv=[
            "--runtime",
            descriptor.runtime_name,
            "--config-dir",
            f"./{descriptor.config_dir_name}",
            "--install-scope",
            "local",
            "state",
            "load",
        ],
        runtime=descriptor.runtime_name,
    )

    assert exit_code == 127
    assert observed["config_dir"] == expected_missing_target


@pytest.mark.parametrize("descriptor", _RUNTIME_DESCRIPTORS, ids=lambda descriptor: descriptor.runtime_name)
def test_runtime_cli_does_not_treat_marker_only_canonical_global_dir_as_local_when_runtime_env_overrides_elsewhere(
    monkeypatch,
    tmp_path: Path,
    descriptor,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    if os.name == "nt":
        monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setattr(Path, "home", staticmethod(lambda: home))

    canonical_global_dir = resolve_global_config_dir(descriptor, home=home, environ={})
    _mark_complete_install(canonical_global_dir, runtime=descriptor.runtime_name, install_scope="global")
    (canonical_global_dir / MANIFEST_NAME).unlink()

    override_dir = tmp_path / "override" / descriptor.config_dir_name
    override_dir.mkdir(parents=True)
    global_config = descriptor.global_config
    env_var = global_config.env_var or global_config.env_dir_var or global_config.env_file_var
    assert env_var is not None
    env_value = str(override_dir / "config.json") if env_var == global_config.env_file_var else str(override_dir)
    monkeypatch.setenv(env_var, env_value)

    cli_cwd = home / "research" / "notes"
    cli_cwd.mkdir(parents=True)
    expected_missing_target = cli_cwd / descriptor.config_dir_name

    exit_code, observed = _run_runtime_cli_with_recording(
        monkeypatch,
        cwd=cli_cwd,
        argv=[
            "--runtime",
            descriptor.runtime_name,
            "--config-dir",
            f"./{descriptor.config_dir_name}",
            "--install-scope",
            "local",
            "state",
            "load",
        ],
        runtime=descriptor.runtime_name,
    )

    assert exit_code == 127
    assert observed["config_dir"] == expected_missing_target


@pytest.mark.parametrize("descriptor", _RUNTIME_DESCRIPTORS, ids=lambda descriptor: descriptor.runtime_name)
def test_runtime_cli_does_not_treat_marker_only_env_global_dir_as_local_ancestor_candidate(
    monkeypatch,
    tmp_path: Path,
    descriptor,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    if os.name == "nt":
        monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setattr(Path, "home", staticmethod(lambda: home))

    workspace = tmp_path / "workspace"
    override_dir = workspace / descriptor.config_dir_name
    override_dir.mkdir(parents=True)
    _mark_complete_install(override_dir, runtime=descriptor.runtime_name, install_scope="global")
    (override_dir / MANIFEST_NAME).unlink()

    global_config = descriptor.global_config
    env_var = global_config.env_var or global_config.env_dir_var or global_config.env_file_var
    assert env_var is not None
    env_value = str(override_dir / "config.json") if env_var == global_config.env_file_var else str(override_dir)
    monkeypatch.setenv(env_var, env_value)

    cli_cwd = workspace / "research" / "notes"
    cli_cwd.mkdir(parents=True)
    expected_missing_target = cli_cwd / descriptor.config_dir_name

    exit_code, observed = _run_runtime_cli_with_recording(
        monkeypatch,
        cwd=cli_cwd,
        argv=[
            "--runtime",
            descriptor.runtime_name,
            "--config-dir",
            f"./{descriptor.config_dir_name}",
            "--install-scope",
            "local",
            "state",
            "load",
        ],
        runtime=descriptor.runtime_name,
    )

    assert exit_code == 127
    assert observed["config_dir"] == expected_missing_target
