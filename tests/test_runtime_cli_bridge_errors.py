"""Regression coverage for malformed runtime bridge invocations."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

import gpd.runtime_cli as runtime_cli
from gpd.adapters.install_utils import build_runtime_install_repair_command
from gpd.adapters.runtime_catalog import iter_runtime_descriptors

_BRIDGE_RUNTIME_DESCRIPTOR = iter_runtime_descriptors()[0]


def test_runtime_cli_allows_help_passthrough_as_root_flag(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runtime_name = _BRIDGE_RUNTIME_DESCRIPTOR.runtime_name
    adapter = runtime_cli.get_adapter(runtime_name)
    config_dir = tmp_path / _BRIDGE_RUNTIME_DESCRIPTOR.config_dir_name
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / runtime_cli.get_shared_install_metadata().manifest_name).write_text(
        json.dumps(
            {
                "runtime": runtime_name,
                "install_scope": "local",
                "install_target_dir": str(config_dir),
            }
        ),
        encoding="utf-8",
    )

    observed: dict[str, object] = {}

    def fake_entrypoint() -> int:
        observed["argv"] = list(runtime_cli.sys.argv)
        return 0

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("gpd.runtime_cli._maybe_reexec_from_checkout", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(adapter, "missing_install_artifacts", lambda target_dir: ())
    monkeypatch.setattr("gpd.runtime_cli.get_adapter", lambda runtime_name: adapter)
    monkeypatch.setattr("gpd.cli.entrypoint", fake_entrypoint)

    exit_code = runtime_cli.main(
        [
            "--runtime",
            runtime_name,
            "--config-dir",
            str(config_dir),
            "--install-scope",
            "local",
            "--help",
        ]
    )

    assert exit_code == 0
    assert observed["argv"] == ["gpd", "--help"]


@pytest.mark.parametrize("root_flag", ["--version", "-v"])
def test_runtime_cli_allows_version_passthrough_as_root_flag(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    root_flag: str,
) -> None:
    runtime_name = _BRIDGE_RUNTIME_DESCRIPTOR.runtime_name
    adapter = runtime_cli.get_adapter(runtime_name)
    config_dir = tmp_path / _BRIDGE_RUNTIME_DESCRIPTOR.config_dir_name
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / runtime_cli.get_shared_install_metadata().manifest_name).write_text(
        json.dumps(
            {
                "runtime": runtime_name,
                "install_scope": "local",
                "install_target_dir": str(config_dir),
            }
        ),
        encoding="utf-8",
    )

    observed: dict[str, object] = {}

    def fake_entrypoint() -> int:
        observed["argv"] = list(runtime_cli.sys.argv)
        return 0

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("gpd.runtime_cli._maybe_reexec_from_checkout", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(adapter, "missing_install_artifacts", lambda target_dir: ())
    monkeypatch.setattr("gpd.runtime_cli.get_adapter", lambda runtime_name: adapter)
    monkeypatch.setattr("gpd.cli.entrypoint", fake_entrypoint)

    exit_code = runtime_cli.main(
        [
            "--runtime",
            runtime_name,
            "--config-dir",
            str(config_dir),
            "--install-scope",
            "local",
            root_flag,
        ]
    )

    assert exit_code == 0
    assert observed["argv"] == ["gpd", root_flag]


@pytest.mark.parametrize(
    ("manifest_scope", "expected_phrase"),
    [
        (None, "The manifest must declare a non-empty `install_scope` field."),
        ("workspace", "The manifest `install_scope` field must be exactly `local` or `global`."),
    ],
)
def test_runtime_cli_rejects_missing_or_malformed_install_scope(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    manifest_scope: str | None,
    expected_phrase: str,
) -> None:
    runtime_name = _BRIDGE_RUNTIME_DESCRIPTOR.runtime_name
    config_dir = tmp_path / _BRIDGE_RUNTIME_DESCRIPTOR.config_dir_name
    config_dir.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, object] = {
        "runtime": runtime_name,
        "install_target_dir": str(config_dir),
    }
    if manifest_scope is not None:
        manifest["install_scope"] = manifest_scope
    (config_dir / runtime_cli.get_shared_install_metadata().manifest_name).write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )

    expected_repair_command = build_runtime_install_repair_command(
        runtime_name,
        install_scope="local",
        target_dir=config_dir,
        explicit_target=False,
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("gpd.runtime_cli._maybe_reexec_from_checkout", lambda *_args, **_kwargs: None)

    exit_code = runtime_cli.main(
        [
            "--runtime",
            runtime_name,
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
    assert expected_phrase in captured.err
    assert expected_repair_command in captured.err


@pytest.mark.parametrize(
    ("install_scope", "config_dir_factory", "expected_target_dir_flag"),
    [
        ("local", lambda tmp_path, descriptor: tmp_path / descriptor.config_dir_name, False),
        (
            "global",
            lambda tmp_path, descriptor: tmp_path / "custom-global" / descriptor.config_dir_name,
            True,
        ),
    ],
)
def test_runtime_cli_repair_command_projection_respects_local_and_custom_global_targets(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    install_scope: str,
    config_dir_factory,
    expected_target_dir_flag: bool,
) -> None:
    runtime_name = _BRIDGE_RUNTIME_DESCRIPTOR.runtime_name
    adapter = runtime_cli.get_adapter(runtime_name)
    config_dir = config_dir_factory(tmp_path, _BRIDGE_RUNTIME_DESCRIPTOR)
    home_dir = tmp_path / "home"
    home_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("gpd.runtime_cli.Path.home", lambda: home_dir)

    repair_command = runtime_cli._build_repair_command(
        runtime=runtime_name,
        config_dir=config_dir,
        install_scope=install_scope,
        explicit_target=False,
        cli_cwd=tmp_path,
    )

    expected = build_runtime_install_repair_command(
        runtime_name,
        install_scope=install_scope,
        target_dir=config_dir,
        explicit_target=expected_target_dir_flag,
    )
    assert repair_command == expected
    assert ("--target-dir" in repair_command) is expected_target_dir_flag
    if install_scope == "local":
        assert f"{adapter.install_flag} --local" in repair_command
    else:
        assert "--global" in repair_command


def test_runtime_cli_repair_command_projection_respects_env_overridden_global_targets(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    descriptor = next(
        item
        for item in iter_runtime_descriptors()
        if item.global_config.env_var or item.global_config.env_dir_var or item.global_config.env_file_var
    )
    runtime_name = descriptor.runtime_name
    override_dir = tmp_path / "override-global"
    override_dir.mkdir(parents=True, exist_ok=True)
    home_dir = tmp_path / "home"
    home_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("gpd.runtime_cli.Path.home", lambda: home_dir)
    env_var = descriptor.global_config.env_var or descriptor.global_config.env_dir_var or descriptor.global_config.env_file_var
    assert env_var is not None
    monkeypatch.setenv(env_var, str(override_dir))

    config_dir = runtime_cli.get_adapter(runtime_name).resolve_global_config_dir(home=home_dir)
    repair_command = runtime_cli._build_repair_command(
        runtime=runtime_name,
        config_dir=config_dir,
        install_scope="global",
        explicit_target=False,
        cli_cwd=tmp_path,
    )

    expected = build_runtime_install_repair_command(
        runtime_name,
        install_scope="global",
        target_dir=config_dir,
        explicit_target=False,
    )
    assert repair_command == expected
    assert "--global" in repair_command
    assert "--target-dir" not in repair_command


@pytest.mark.parametrize(
    ("manifest_state", "artifact_override", "expected_kind", "expected_phrase"),
    [
        (
            {"runtime": _BRIDGE_RUNTIME_DESCRIPTOR.runtime_name},
            None,
            runtime_cli._BridgeFailureKind.MISSING_INSTALL_SCOPE,
            "The manifest must declare a non-empty `install_scope` field.",
        ),
        (
            {
                "runtime": next(
                    item.runtime_name
                    for item in iter_runtime_descriptors()
                    if item.runtime_name != _BRIDGE_RUNTIME_DESCRIPTOR.runtime_name
                ),
                "install_scope": "local",
            },
            None,
            runtime_cli._BridgeFailureKind.RUNTIME_MISMATCH,
            "GPD runtime bridge mismatch",
        ),
        (
            {"runtime": _BRIDGE_RUNTIME_DESCRIPTOR.runtime_name, "install_scope": "local"},
            ("missing-artifact.txt",),
            runtime_cli._BridgeFailureKind.MISSING_INSTALL_ARTIFACTS,
            "Missing required install artifacts",
        ),
    ],
)
def test_runtime_cli_classifies_bridge_failures_with_stable_kinds(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    manifest_state: dict[str, object],
    artifact_override: tuple[str, ...] | None,
    expected_kind: runtime_cli._BridgeFailureKind,
    expected_phrase: str,
) -> None:
    runtime_name = _BRIDGE_RUNTIME_DESCRIPTOR.runtime_name
    adapter = runtime_cli.get_adapter(runtime_name)
    config_dir = tmp_path / _BRIDGE_RUNTIME_DESCRIPTOR.config_dir_name
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / runtime_cli.get_shared_install_metadata().manifest_name).write_text(
        json.dumps(manifest_state),
        encoding="utf-8",
    )

    if artifact_override is not None:
        monkeypatch.setattr(adapter, "missing_install_artifacts", lambda target_dir: artifact_override)
    monkeypatch.setattr("gpd.runtime_cli._maybe_reexec_from_checkout", lambda *_args, **_kwargs: None)
    monkeypatch.chdir(tmp_path)

    manifest_status, _manifest_payload, manifest_runtime = runtime_cli.load_install_manifest_runtime_status(config_dir)
    manifest_scope_status, manifest_scope_payload, manifest_install_scope = runtime_cli.load_install_manifest_scope_status(
        config_dir
    )
    if manifest_scope_status == "ok":
        manifest_install_scope = manifest_scope_payload.get("install_scope")
        if not isinstance(manifest_install_scope, str):
            manifest_install_scope = None

    failure = runtime_cli._classify_bridge_failure(
        runtime=runtime_name,
        config_dir=config_dir,
        install_scope="local",
        explicit_target=False,
        cli_cwd=tmp_path,
        manifest_status=manifest_status,
        manifest_runtime=manifest_runtime,
        manifest_scope_status=manifest_scope_status,
        manifest_install_scope=manifest_install_scope,
        missing=artifact_override,
        has_managed_install_markers=runtime_cli.config_dir_has_managed_install_markers(config_dir),
    )

    assert failure is not None
    assert failure.kind is expected_kind
    assert expected_phrase in failure.message


@pytest.mark.parametrize(
    ("manifest_scope", "bridge_scope"),
    [("local", "global"), ("global", "local")],
)
def test_runtime_cli_rejects_manifest_install_scope_mismatch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    manifest_scope: str,
    bridge_scope: str,
) -> None:
    runtime_name = _BRIDGE_RUNTIME_DESCRIPTOR.runtime_name
    config_dir = tmp_path / _BRIDGE_RUNTIME_DESCRIPTOR.config_dir_name
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / runtime_cli.get_shared_install_metadata().manifest_name).write_text(
        json.dumps(
            {
                "runtime": runtime_name,
                "install_scope": manifest_scope,
                "install_target_dir": str(config_dir),
            }
        ),
        encoding="utf-8",
    )

    expected_repair_command = build_runtime_install_repair_command(
        runtime_name,
        install_scope=manifest_scope,
        target_dir=config_dir,
        explicit_target=False,
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("gpd.runtime_cli._maybe_reexec_from_checkout", lambda *_args, **_kwargs: None)

    exit_code = runtime_cli.main(
        [
            "--runtime",
            runtime_name,
            "--config-dir",
            str(config_dir),
            "--install-scope",
            bridge_scope,
            "state",
            "load",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 127
    assert "GPD runtime bridge scope mismatch" in captured.err
    assert f"pins `{manifest_scope}`" in captured.err
    assert f"launched as `{bridge_scope}`" in captured.err
    assert expected_repair_command in captured.err


def test_runtime_cli_rejects_missing_bridge_arguments_without_argparse_abort(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = runtime_cli.main(["state", "load"])

    captured = capsys.readouterr()
    assert exit_code == 127
    assert "GPD runtime bridge rejected malformed bridge invocation." in captured.err
    assert "the following arguments are required: --runtime, --config-dir, --install-scope" in captured.err
    assert "usage:" not in captured.err.lower()


@pytest.mark.parametrize(
    ("argv", "expected_fragment"),
    [
        (
            [
                "--runtime",
                _BRIDGE_RUNTIME_DESCRIPTOR.runtime_name,
                "--config-dir",
                "/tmp/GPD",
                "--install-scope",
                "sideways",
                "state",
                "load",
            ],
            re.compile(r"invalid choice: 'sideways' \(choose from '?local'?,\s*'?global'?\)"),
        ),
        (
            [
                "--runtime",
                _BRIDGE_RUNTIME_DESCRIPTOR.runtime_name,
                "--config-dir",
                "/tmp/GPD",
                "--install-scope",
            ],
            "argument --install-scope: expected one argument",
        ),
        (
            [
                "--runtime",
                _BRIDGE_RUNTIME_DESCRIPTOR.runtime_name,
                "--config-dir",
                "/tmp/GPD",
                "--install-scope",
                "local",
                "--runtime",
            ],
            "argument --runtime: expected one argument",
        ),
        (
            [
                "--runtime",
                _BRIDGE_RUNTIME_DESCRIPTOR.runtime_name,
                "--config-dir",
                "/tmp/GPD",
                "--install-scope",
                "local",
                "--bogus",
                "state",
                "load",
            ],
            "unrecognized forwarded gpd root flag: --bogus",
        ),
        (
            [
                "--runtime",
                _BRIDGE_RUNTIME_DESCRIPTOR.runtime_name,
                "--config-dir",
                "/tmp/GPD",
                "--install-scope",
                "local",
                "--configdir",
                "/tmp/GPD",
                "state",
                "load",
            ],
            "unrecognized forwarded gpd root flag: --configdir",
        ),
    ],
)
def test_runtime_cli_rejects_malformed_bridge_invocations(
    argv: list[str],
    expected_fragment: str | re.Pattern[str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = runtime_cli.main(argv)

    captured = capsys.readouterr()
    assert exit_code == 127
    assert "GPD runtime bridge rejected malformed bridge invocation." in captured.err
    if isinstance(expected_fragment, re.Pattern):
        assert expected_fragment.search(captured.err), (
            f"Regex {expected_fragment.pattern!r} not found in stderr:\n{captured.err}"
        )
    else:
        assert expected_fragment in captured.err
    assert "usage:" not in captured.err.lower()
