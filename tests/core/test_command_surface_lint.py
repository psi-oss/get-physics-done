"""Lint command-surface examples in model-visible command/workflow prompts."""

from __future__ import annotations

import re
import shlex
from pathlib import Path

from gpd import cli, registry

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_DIR = REPO_ROOT / "src/gpd/commands"
WORKFLOWS_DIR = REPO_ROOT / "src/gpd/specs/workflows"

SHELL_FENCE_LANGUAGES = {"bash", "sh", "shell", "zsh"}
ROOT_FLAG_OPTIONS = {"--raw", "--help", "-h", "--version"}
ROOT_OPTIONS_WITH_VALUES = {"--cwd"}
_GPD_INVOCATION_RE = re.compile(r"(?P<prefix>^|[\s(=|;&]|\$\()(?P<command>gpd)(?![:.\w-])")


def _registered_cli_surface() -> tuple[set[str], dict[str, set[str]]]:
    root_commands = {command.name for command in cli.app.registered_commands if command.name}
    command_groups = {
        group.name: {command.name for command in group.typer_instance.registered_commands if command.name}
        for group in cli.app.registered_groups
        if group.name
    }
    return root_commands, command_groups


def _is_inside_quotes(line: str, index: int) -> bool:
    quote: str | None = None
    escaped = False
    for char in line[:index]:
        if escaped:
            escaped = False
            continue
        if char == "\\" and quote != "'":
            escaped = True
            continue
        if quote is None:
            if char in {"'", '"'}:
                quote = char
        elif char == quote:
            quote = None
    return quote is not None


def _command_segment(line: str, start: int) -> str:
    quote: str | None = None
    escaped = False
    in_command_substitution = "$(" in line[:start]
    for index in range(start, len(line)):
        char = line[index]
        if escaped:
            escaped = False
            continue
        if char == "\\" and quote != "'":
            escaped = True
            continue
        if quote is None:
            if char in {"'", '"'}:
                quote = char
                continue
            if char in {";", "|", "&", "#"}:
                return line[start:index]
            if char == ")" and in_command_substitution:
                return line[start:index]
        elif char == quote:
            quote = None
    return line[start:]


def _gpd_invocations(line: str) -> list[str]:
    if line.lstrip().startswith("#"):
        return []

    invocations: list[str] = []
    for match in _GPD_INVOCATION_RE.finditer(line):
        start = match.start("command")
        if _is_inside_quotes(line, start) and line[max(0, start - 2) : start] != "$(":
            continue
        invocations.append(_command_segment(line, start).strip())
    return invocations


def _shell_fenced_lines(path: Path) -> list[tuple[int, str]]:
    lines: list[tuple[int, str]] = []
    in_shell_fence = False

    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.lstrip()
        if stripped.startswith("```"):
            if in_shell_fence:
                in_shell_fence = False
            else:
                in_shell_fence = stripped[3:].strip().lower() in SHELL_FENCE_LANGUAGES
            continue
        if in_shell_fence:
            lines.append((line_number, line))

    return lines


def _validate_gpd_invocation(
    invocation: str,
    *,
    root_commands: set[str],
    command_groups: dict[str, set[str]],
    runtime_command_slugs: set[str],
) -> str | None:
    parse_target = invocation.rstrip()
    while parse_target.endswith("\\"):
        parse_target = parse_target[:-1].rstrip()

    try:
        tokens = shlex.split(parse_target, posix=True)
    except ValueError as exc:
        return f"could not parse shell snippet `{invocation}`: {exc}"

    if not tokens or tokens[0] != "gpd":
        return None

    index = 1
    while index < len(tokens):
        token = tokens[index]
        if token in ROOT_FLAG_OPTIONS:
            index += 1
            continue
        if token in ROOT_OPTIONS_WITH_VALUES:
            index += 2
            continue
        if any(token.startswith(f"{option}=") for option in ROOT_OPTIONS_WITH_VALUES):
            index += 1
            continue
        break

    if index >= len(tokens):
        if any(token in {"--help", "-h", "--version"} for token in tokens[1:]):
            return None
        return f"`{invocation}` does not name a local CLI command"

    command = tokens[index]
    if command in root_commands:
        return None

    if command in command_groups:
        if index + 1 >= len(tokens) or tokens[index + 1].startswith("-"):
            return f"`{invocation}` names CLI group `gpd {command}` without a subcommand"
        subcommand = tokens[index + 1]
        if subcommand not in command_groups[command]:
            return f"`{invocation}` uses unknown local CLI subcommand `gpd {command} {subcommand}`"
        return None

    if command in runtime_command_slugs:
        return (
            f"`{invocation}` is a runtime command surface; use `gpd:{command}` outside the shell fence "
            "or replace it with a real local CLI command"
        )

    return f"`{invocation}` uses unknown local CLI command `gpd {command}`"


def test_shell_fenced_gpd_commands_use_registered_local_cli_surface() -> None:
    root_commands, command_groups = _registered_cli_surface()
    runtime_command_slugs = set(registry.list_commands())
    errors: list[str] = []

    for path in [*sorted(COMMANDS_DIR.glob("*.md")), *sorted(WORKFLOWS_DIR.glob("*.md"))]:
        for line_number, line in _shell_fenced_lines(path):
            for invocation in _gpd_invocations(line):
                error = _validate_gpd_invocation(
                    invocation,
                    root_commands=root_commands,
                    command_groups=command_groups,
                    runtime_command_slugs=runtime_command_slugs,
                )
                if error is not None:
                    errors.append(f"{path.relative_to(REPO_ROOT)}:{line_number}: {error}")

    assert not errors, "Invalid fenced-shell GPD command snippets:\n" + "\n".join(errors)
