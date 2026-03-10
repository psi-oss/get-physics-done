"""Abstract tool taxonomy for canonical GPD tool names.

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
    "web_search": "websearch",
    "web_fetch": "webfetch",
    "notebook_edit": "notebookedit",
    "agent": "agent",
    "ask_user": "question",
    "todo_write": "todowrite",
    "task": "task",
    "slash_command": "skill",
    "tool_search": "toolsearch",
}


RUNTIME_TABLES: dict[str, dict[str, str]] = {
    "claude-code": CLAUDE_CODE,
    "codex": CODEX,
    "gemini": GEMINI,
    "opencode": OPENCODE,
}

CANONICAL_TOOL_NAMES: tuple[str, ...] = tuple(CLAUDE_CODE)
"""Canonical GPD tool names supported across runtimes."""

CONTEXTUAL_TOOL_REFERENCE_NAMES: frozenset[str] = frozenset(
    {
        "Read",
        "Write",
        "Edit",
        "Bash",
        "Grep",
        "Glob",
        "Task",
        "Agent",
        "shell",
        "task",
        "agent",
    }
)
"""Tool names that should only be rewritten in tool-like prose contexts."""

_AUTO_DISCOVERED_TOOLS: dict[str, frozenset[str]] = {
    "codex": frozenset({"task"}),
    "gemini": frozenset({"task"}),
}
_DROP_MCP_FRONTMATTER_TOOLS: frozenset[str] = frozenset({"gemini"})

# Non-canonical runtime spellings → canonical names.
# Start with the inverse of every runtime table so adapter-native names
# canonicalize correctly regardless of which adapter produced them.
_RUNTIME_ALIASES: dict[str, str] = {
    runtime_name: canonical_name
    for table in RUNTIME_TABLES.values()
    for canonical_name, runtime_name in table.items()
}


def canonical(name: str) -> str:
    """Normalize a tool name to its canonical GPD form.

    Accepts any runtime-specific tool name and returns
    the canonical GPD name (e.g. ``"Read"`` → ``"file_read"``).
    """
    if name in CANONICAL_TOOL_NAMES:
        return name
    return _RUNTIME_ALIASES.get(name, name)


def translate(name: str, runtime: str) -> str:
    """Translate a canonical GPD tool name to the given runtime's name.

    Falls back to the canonical name if no mapping exists.
    """
    table = RUNTIME_TABLES.get(runtime, {})
    canon = canonical(name)
    return table.get(canon, canon)


def translate_for_runtime(name: str, runtime: str) -> str | None:
    """Translate a tool for runtime frontmatter/body conversion.

    Unlike ``translate()``, this respects runtime-specific omission rules for
    auto-discovered tools such as ``task`` and Gemini's MCP tools.
    """
    if name.startswith("mcp__"):
        return None if runtime in _DROP_MCP_FRONTMATTER_TOOLS else name

    canon = canonical(name)
    if canon in _AUTO_DISCOVERED_TOOLS.get(runtime, frozenset()):
        return None
    return translate(canon, runtime)


def translate_list(names: list[str], runtime: str) -> list[str]:
    """Translate a list of tool names to a runtime."""
    return [translate(n, runtime) for n in names]


def reference_translation_map(runtime: str) -> dict[str, str]:
    """Build a source-to-runtime mapping for prompt body tool references."""
    mapping: dict[str, str | None] = {
        name: translate_for_runtime(name, runtime) for name in CANONICAL_TOOL_NAMES
    }
    return {source: target for source, target in mapping.items() if target and source != target}


__all__ = [
    "CLAUDE_CODE",
    "CANONICAL_TOOL_NAMES",
    "CONTEXTUAL_TOOL_REFERENCE_NAMES",
    "CODEX",
    "GEMINI",
    "OPENCODE",
    "RUNTIME_TABLES",
    "canonical",
    "reference_translation_map",
    "translate",
    "translate_for_runtime",
    "translate_list",
]
