from __future__ import annotations

import re
import shlex
from pathlib import Path

from typer.testing import CliRunner

from gpd.adapters.runtime_catalog import iter_runtime_descriptors
from gpd.cli import app
from gpd.core.public_surface_contract import load_public_surface_contract

_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def _example_runtime_name() -> str:
    return iter_runtime_descriptors()[0].runtime_name


def _bridge_command_help_args(command: str, *, tmp_path: Path) -> list[str]:
    args = shlex.split(command)
    assert args and args[0] == "gpd"
    tail = args[1:]
    if tail == ["--help"]:
        return tail

    placeholder_values = {
        "<runtime>": _example_runtime_name(),
        "<mode>": "review",
        "<PLAN.md>": str(tmp_path / "PLAN.md"),
    }
    return [placeholder_values.get(arg, arg) for arg in tail] + ["--help"]


def test_public_surface_contract_smoke_surfaces_current_resume_authority_phrase() -> None:
    contract = load_public_surface_contract()

    assert (
        contract.resume_authority.public_vocabulary_intro
        == "Canonical continuation fields define the public resume vocabulary"
    )


def test_public_surface_contract_smoke_keeps_bridge_commands_and_named_commands_aligned() -> None:
    contract = load_public_surface_contract()

    assert contract.local_cli_bridge.commands == contract.local_cli_bridge.named_commands.ordered()
    assert contract.local_cli_bridge.named_commands.help == "gpd --help"
    assert contract.local_cli_bridge.named_commands.resume == "gpd resume"
    assert contract.local_cli_bridge.install_local_example == "gpd install <runtime> --local"
    assert contract.local_cli_bridge.doctor_local_command == "gpd doctor --runtime <runtime> --local"
    assert contract.local_cli_bridge.doctor_global_command == "gpd doctor --runtime <runtime> --global"
    assert (
        contract.local_cli_bridge.validate_command_context_command
        == "gpd validate command-context gpd:<name>"
    )


def test_public_surface_contract_bridge_commands_parse_live_cli_help(tmp_path: Path) -> None:
    contract = load_public_surface_contract()
    (tmp_path / "PLAN.md").write_text("# Plan\n", encoding="utf-8")
    runner = CliRunner()
    failures: list[str] = []

    for command in contract.local_cli_bridge.commands:
        args = _bridge_command_help_args(command, tmp_path=tmp_path)
        result = runner.invoke(app, ["--cwd", str(tmp_path), *args])
        output = _ANSI_ESCAPE_RE.sub("", result.output)
        if result.exit_code != 0 or "Usage: gpd" not in output:
            failures.append(f"{command!r} via {args!r}: exit={result.exit_code}\n{result.output}")

    assert failures == []
