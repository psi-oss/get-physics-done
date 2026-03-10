"""Tests for adapter registry and tool_names module."""

from __future__ import annotations

import pytest

from gpd.adapters import get_adapter, list_runtimes
from gpd.adapters.base import RuntimeAdapter
from gpd.adapters.tool_names import (
    CLAUDE_CODE,
    CANONICAL_TOOL_NAMES,
    CONTEXTUAL_TOOL_REFERENCE_NAMES,
    CODEX,
    GEMINI,
    OPENCODE,
    RUNTIME_TABLES,
    canonical,
    reference_translation_map,
    translate,
    translate_for_runtime,
)


class TestRegistry:
    """Tests for the adapter registry (get_adapter / list_runtimes)."""

    def test_list_runtimes_returns_all_four(self) -> None:
        runtimes = list_runtimes()
        assert set(runtimes) == {"claude-code", "codex", "gemini", "opencode"}

    def test_list_runtimes_sorted(self) -> None:
        runtimes = list_runtimes()
        assert runtimes == sorted(runtimes)

    @pytest.mark.parametrize("runtime", ["claude-code", "codex", "gemini", "opencode"])
    def test_get_adapter_returns_instance(self, runtime: str) -> None:
        adapter = get_adapter(runtime)
        assert isinstance(adapter, RuntimeAdapter)
        assert adapter.runtime_name == runtime

    def test_get_adapter_unknown_raises_key_error(self) -> None:
        with pytest.raises(KeyError, match="Unknown runtime"):
            get_adapter("nonexistent")

    def test_get_adapter_returns_new_instance_each_call(self) -> None:
        a = get_adapter("claude-code")
        b = get_adapter("claude-code")
        assert a is not b

    @pytest.mark.parametrize(
        ("runtime", "expected"),
        [
            ("claude-code", "npx -y get-physics-done --claude"),
            ("codex", "npx -y get-physics-done --codex"),
            ("gemini", "npx -y get-physics-done --gemini"),
            ("opencode", "npx -y get-physics-done --opencode"),
        ],
    )
    def test_update_command_is_adapter_owned(self, runtime: str, expected: str) -> None:
        assert get_adapter(runtime).update_command == expected


class TestToolNames:
    """Tests for tool_names canonical/translate functions."""

    def test_canonical_identity_for_canonical_names(self) -> None:
        for name in ("file_read", "file_write", "shell", "search_files"):
            assert canonical(name) == name

    @pytest.mark.parametrize(
        ("runtime_alias", "expected"),
        [
            ("Read", "file_read"),
            ("read_file", "file_read"),
            ("Write", "file_write"),
            ("apply_patch", "file_edit"),
            ("Edit", "file_edit"),
            ("Bash", "shell"),
            ("run_shell_command", "shell"),
            ("Grep", "search_files"),
            ("Glob", "find_files"),
            ("WebSearch", "web_search"),
            ("websearch", "web_search"),
            ("WebFetch", "web_fetch"),
            ("AskUserQuestion", "ask_user"),
            ("question", "ask_user"),
            ("skill", "slash_command"),
        ],
    )
    def test_canonical_runtime_aliases(self, runtime_alias: str, expected: str) -> None:
        assert canonical(runtime_alias) == expected

    def test_canonical_unknown_passthrough(self) -> None:
        assert canonical("custom_tool") == "custom_tool"

    @pytest.mark.parametrize(
        ("canon", "runtime", "expected"),
        [
            ("file_read", "claude-code", "Read"),
            ("file_read", "codex", "read_file"),
            ("file_read", "gemini", "read_file"),
            ("file_read", "opencode", "read_file"),
            ("shell", "claude-code", "Bash"),
            ("shell", "gemini", "run_shell_command"),
            ("search_files", "gemini", "search_file_content"),
            ("web_search", "gemini", "google_web_search"),
            ("ask_user", "opencode", "question"),
            ("slash_command", "opencode", "skill"),
        ],
    )
    def test_translate_canonical_to_runtime(self, canon: str, runtime: str, expected: str) -> None:
        assert translate(canon, runtime) == expected

    def test_translate_runtime_alias_auto_canonicalized(self) -> None:
        assert translate("Read", "codex") == "read_file"
        assert translate("Bash", "gemini") == "run_shell_command"

    def test_translate_runtime_native_name_auto_canonicalized(self) -> None:
        assert translate("apply_patch", "claude-code") == "Edit"
        assert translate("question", "codex") == "ask_user"
        assert translate("run_shell_command", "opencode") == "shell"

    def test_translate_unknown_runtime_fallback(self) -> None:
        assert translate("file_read", "unknown-runtime") == "file_read"

    def test_translate_unknown_tool_fallback(self) -> None:
        assert translate("custom_tool", "claude-code") == "custom_tool"

    def test_translate_for_runtime_drops_auto_discovered_tools(self) -> None:
        assert translate_for_runtime("task", "codex") is None
        assert translate_for_runtime("Task", "gemini") is None

    def test_translate_for_runtime_handles_mcp_policy(self) -> None:
        assert translate_for_runtime("mcp__physics", "gemini") is None
        assert translate_for_runtime("mcp__physics", "codex") == "mcp__physics"

    def test_reference_translation_map_uses_only_canonical_source_names(self) -> None:
        mapping = reference_translation_map("opencode")
        assert mapping["ask_user"] == "question"
        assert "AskUserQuestion" not in mapping
        assert "read_file" not in mapping  # identical names are omitted

    def test_contextual_reference_names_cover_common_english_tools(self) -> None:
        assert {"Read", "Write", "Edit", "shell", "task", "agent"} <= CONTEXTUAL_TOOL_REFERENCE_NAMES

    def test_canonical_tool_names_match_runtime_table_keys(self) -> None:
        assert set(CANONICAL_TOOL_NAMES) == set(CLAUDE_CODE)

    def test_all_runtime_tables_present(self) -> None:
        assert set(RUNTIME_TABLES.keys()) == {"claude-code", "codex", "gemini", "opencode"}

    def test_all_tables_have_same_canonical_keys(self) -> None:
        keys = set(CLAUDE_CODE.keys())
        for name, table in [("CODEX", CODEX), ("GEMINI", GEMINI), ("OPENCODE", OPENCODE)]:
            assert set(table.keys()) == keys, f"{name} has different canonical keys than CLAUDE_CODE"
