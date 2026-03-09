"""GPD command definitions — delegates to gpd.registry for cached parsing."""

from __future__ import annotations

from gpd.registry import COMMANDS_DIR, list_commands  # noqa: F401
from gpd.registry import get_command as _get_command


def get_command(name: str) -> dict[str, object]:
    """Get a command definition by name (dict form for backward compat)."""
    cmd = _get_command(name)
    return {
        "name": cmd.name,
        "description": cmd.description,
        "argument-hint": cmd.argument_hint,
        "requires": cmd.requires,
        "allowed-tools": cmd.allowed_tools,
        "content": cmd.content,
    }


__all__ = ["COMMANDS_DIR", "list_commands", "get_command"]
