"""Abstract tool taxonomy — maps canonical GPD tool names to runtime-specific names.

GPD specs use canonical tool names (e.g. ``file_read``, ``file_write``, ``shell``).
Each runtime (Claude Code, Codex, Gemini CLI, OpenCode) has its own tool naming.
This module provides the translation tables and lookup functions.
"""

from __future__ import annotations

# Canonical GPD tool name → runtime-specific tool name
# Each runtime maps the same abstract capability to its own tool interface.

CLAUDE_CODE: dict[str, str] = {
    "file_read": "Read",
    "file_write": "Write",
    "file_edit": "Edit",
    "shell": "Bash",
    "search_files": "Grep",
    "find_files": "Glob",
    "web_search": "WebSearch",
    "web_fetch": "WebFetch",
    "notebook_edit": "NotebookEdit",
    "agent": "Agent",
    "ask_user": "AskUserQuestion",
    "todo_write": "TodoWrite",
    "task": "Task",
    "slash_command": "SlashCommand",
    "tool_search": "ToolSearch",
}

CODEX: dict[str, str] = {
    "file_read": "read_file",
    "file_write": "write_file",
    "file_edit": "apply_patch",
    "shell": "shell",
    "search_files": "grep",
    "find_files": "glob",
    "web_search": "web_search",
    "web_fetch": "web_fetch",
    "notebook_edit": "notebook_edit",
    "agent": "agent",
    "ask_user": "ask_user",
    "todo_write": "todo",
    "task": "task",
    "slash_command": "slash_command",
    "tool_search": "tool_search",
}

GEMINI: dict[str, str] = {
    "file_read": "read_file",
    "file_write": "write_file",
    "file_edit": "replace",
    "shell": "run_shell_command",
    "search_files": "search_file_content",
    "find_files": "glob",
    "web_search": "google_web_search",
    "web_fetch": "web_fetch",
    "notebook_edit": "notebook_edit",
    "agent": "agent",
    "ask_user": "ask_user",
    "todo_write": "write_todos",
    "task": "task",
    "slash_command": "slash_command",
    "tool_search": "tool_search",
}

OPENCODE: dict[str, str] = {
    "file_read": "read_file",
    "file_write": "write_file",
    "file_edit": "edit_file",
    "shell": "shell",
    "search_files": "grep",
    "find_files": "glob",
    "web_search": "web_search",
    "web_fetch": "web_fetch",
    "notebook_edit": "notebook_edit",
    "agent": "agent",
    "ask_user": "question",
    "todo_write": "todowrite",
    "task": "task",
    "slash_command": "skill",
    "tool_search": "tool_search",
}

AGENTIC_BUILDER: dict[str, str] = {
    "file_read": "file_read",
    "file_write": "file_write",
    "file_edit": "file_edit",
    "shell": "shell",
    "search_files": "search_files",
    "find_files": "find_files",
    "web_search": "web_search",
    "web_fetch": "web_fetch",
    "notebook_edit": "notebook_edit",
    "agent": "agent",
    "ask_user": "ask_user",
    "todo_write": "todo_write",
    "task": "task",
    "slash_command": "slash_command",
    "tool_search": "tool_search",
}

RUNTIME_TABLES: dict[str, dict[str, str]] = {
    "claude-code": CLAUDE_CODE,
    "codex": CODEX,
    "gemini": GEMINI,
    "opencode": OPENCODE,
    "agentic-builder": AGENTIC_BUILDER,
}

# Legacy Claude Code names found in existing specs → canonical names
_LEGACY_ALIASES: dict[str, str] = {
    "read_file": "file_read",
    "write_file": "file_write",
    "edit_file": "file_edit",
    "Read": "file_read",
    "Write": "file_write",
    "Edit": "file_edit",
    "Bash": "shell",
    "Grep": "search_files",
    "Glob": "find_files",
    "WebSearch": "web_search",
    "WebFetch": "web_fetch",
    "NotebookEdit": "notebook_edit",
    "Agent": "agent",
    "AskUserQuestion": "ask_user",
    "TodoWrite": "todo_write",
    "Task": "task",
    "SlashCommand": "slash_command",
    "ToolSearch": "tool_search",
}


def canonical(name: str) -> str:
    """Normalize a tool name to its canonical GPD form.

    Accepts any runtime-specific name or legacy alias and returns
    the canonical GPD name (e.g. ``"Read"`` → ``"file_read"``).
    """
    return _LEGACY_ALIASES.get(name, name)


def translate(name: str, runtime: str) -> str:
    """Translate a canonical GPD tool name to the given runtime's name.

    Falls back to the canonical name if no mapping exists.
    """
    table = RUNTIME_TABLES.get(runtime, {})
    canon = canonical(name)
    return table.get(canon, canon)


def translate_list(names: list[str], runtime: str) -> list[str]:
    """Translate a list of tool names to a runtime."""
    return [translate(n, runtime) for n in names]


__all__ = [
    "RUNTIME_TABLES",
    "canonical",
    "translate",
    "translate_list",
]
