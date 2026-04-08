"""Direct tests for shared root-global CLI argv parsing."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from gpd.core.cli_args import (
    normalize_root_global_cli_options,
    resolve_root_global_cli_cwd_from_argv,
    split_root_global_cli_options,
    validate_root_global_cli_passthrough,
)


def test_split_root_global_cli_options_moves_global_options_before_subcommand_and_keeps_passthrough() -> None:
    argv = [
        "validate",
        "command-context",
        "gpd:new-project",
        "--help",
        "--version",
        "-v",
        "--cwd",
        "/tmp/workspace",
        "--raw",
        "--",
        "--help",
        "--version",
        "-v",
        "--cwd",
        "/tmp/ignored",
        "--raw",
    ]

    global_args, remaining_args = split_root_global_cli_options(argv)

    assert global_args == ["--version", "-v", "--cwd", "/tmp/workspace", "--raw"]
    assert remaining_args == [
        "validate",
        "command-context",
        "gpd:new-project",
        "--help",
        "--",
        "--help",
        "--version",
        "-v",
        "--cwd",
        "/tmp/ignored",
        "--raw",
    ]


def test_normalize_root_global_cli_options_preserves_root_global_prefix_order() -> None:
    argv = [
        "validate",
        "command-context",
        "gpd:new-project",
        "--help",
        "--version",
        "-v",
        "--cwd",
        "/tmp/workspace",
        "--raw",
    ]

    assert normalize_root_global_cli_options(argv) == [
        "--version",
        "-v",
        "--cwd",
        "/tmp/workspace",
        "--raw",
        "validate",
        "command-context",
        "gpd:new-project",
        "--help",
    ]


def test_normalize_root_global_cli_options_preserves_trailing_root_flags() -> None:
    argv = ["progress", "bar", "--help", "--version", "-v"]

    assert normalize_root_global_cli_options(argv) == ["--version", "-v", "progress", "bar", "--help"]


def test_resolve_root_global_cli_cwd_from_argv_uses_last_pre_passthrough_cwd(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()

    argv = [
        "validate",
        "command-context",
        "--cwd",
        "first",
        "--raw",
        "--cwd",
        "second",
        "--",
        "--cwd",
        "ignored",
    ]

    with patch("gpd.core.cli_args.Path.cwd", return_value=tmp_path):
        resolved = resolve_root_global_cli_cwd_from_argv(argv)

    assert resolved == second.resolve(strict=False)


def test_validate_root_global_cli_passthrough_accepts_shared_root_flags() -> None:
    validate_root_global_cli_passthrough(
        ["--raw", "--cwd", "workspace", "--help", "-v", "--version", "resume"]
    )


def test_validate_root_global_cli_passthrough_rejects_unknown_root_flags() -> None:
    with pytest.raises(ValueError, match=r"unrecognized forwarded gpd root flag: --bogus"):
        validate_root_global_cli_passthrough(["--bogus", "resume"])


def test_validate_root_global_cli_passthrough_rejects_missing_cwd_value() -> None:
    with pytest.raises(ValueError, match=r"argument --cwd: expected one argument"):
        validate_root_global_cli_passthrough(["--cwd"])
