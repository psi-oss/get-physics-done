"""Shared helpers for root-global CLI argv parsing."""

from __future__ import annotations

from pathlib import Path

__all__ = [
    "normalize_root_global_cli_options",
    "resolve_root_global_cli_cwd_from_argv",
    "split_root_global_cli_options",
    "validate_root_global_cli_passthrough",
]

_ROOT_GLOBAL_FLAG_TOKENS = frozenset({"--raw", "--version", "-v"})


def validate_root_global_cli_passthrough(argv: list[str]) -> None:
    """Validate root-global GPD flags before the downstream command token.

    The runtime bridge uses this shared validator so it stays aligned with the
    canonical root-global flag grammar owned by this module.
    """

    index = 0
    while index < len(argv):
        arg = str(argv[index])
        if arg == "--":
            return
        if not arg.startswith("-"):
            return
        if arg in _ROOT_GLOBAL_FLAG_TOKENS or arg == "--help":
            index += 1
            continue
        if arg == "--cwd":
            if index + 1 >= len(argv):
                raise ValueError("argument --cwd: expected one argument")
            index += 2
            continue
        if arg.startswith("--cwd="):
            index += 1
            continue
        raise ValueError(f"unrecognized forwarded gpd root flag: {arg}")


def split_root_global_cli_options(argv: list[str]) -> tuple[list[str], list[str]]:
    """Partition root-global CLI options from the rest of the argv stream."""
    global_args: list[str] = []
    remaining_args: list[str] = []
    passthrough = False
    index = 0

    while index < len(argv):
        arg = str(argv[index])
        if passthrough:
            remaining_args.append(arg)
            index += 1
            continue

        if arg == "--":
            passthrough = True
            remaining_args.append(arg)
            index += 1
            continue

        if arg in _ROOT_GLOBAL_FLAG_TOKENS:
            global_args.append(arg)
            index += 1
            continue

        if arg == "--cwd":
            global_args.append(arg)
            if index + 1 < len(argv):
                global_args.append(str(argv[index + 1]))
                index += 2
            else:
                index += 1
            continue

        if arg.startswith("--cwd="):
            global_args.append(arg)
            index += 1
            continue

        remaining_args.append(arg)
        index += 1

    return global_args, remaining_args


def normalize_root_global_cli_options(argv: list[str]) -> list[str]:
    """Move root-global options to the front of the argv stream."""
    global_args, remaining_args = split_root_global_cli_options(argv)
    return [*global_args, *remaining_args]


def resolve_root_global_cli_cwd_from_argv(argv: list[str]) -> Path:
    """Resolve the effective CLI cwd from raw argv before Typer parses it."""
    raw_cwd = "."
    global_args, _ = split_root_global_cli_options(argv)
    for index, arg in enumerate(global_args):
        if arg == "--cwd" and index + 1 < len(global_args):
            raw_cwd = global_args[index + 1]
            continue
        if arg.startswith("--cwd="):
            raw_cwd = arg.split("=", 1)[1]

    candidate = Path(raw_cwd).expanduser()
    if candidate.is_absolute():
        return candidate.resolve(strict=False)
    return (Path.cwd() / candidate).resolve(strict=False)
