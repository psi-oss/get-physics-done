"""Regression coverage for malformed runtime bridge invocations."""

from __future__ import annotations

import json
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
    "argv, expected_fragment",
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
            "invalid choice: 'sideways' (choose from 'local', 'global')",
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
    expected_fragment: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = runtime_cli.main(argv)

    captured = capsys.readouterr()
    assert exit_code == 127
    assert "GPD runtime bridge rejected malformed bridge invocation." in captured.err
    assert expected_fragment in captured.err
    assert "usage:" not in captured.err.lower()
