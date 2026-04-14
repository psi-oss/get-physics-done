"""Adapter-owned tool translation policy coverage."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from gpd.adapters import get_adapter, list_runtimes
from gpd.adapters import tool_names as tool_names_module
from gpd.adapters.runtime_defaults import AUTO_DISCOVERED_TOOL_DEFAULTS
from gpd.adapters.tool_names import (
    CANONICAL_TOOL_NAMES,
    build_canonical_alias_map,
    build_runtime_alias_map,
    reference_translation_map,
    translate,
    translate_for_runtime,
)


def _runtime_tool_maps() -> dict[str, dict[str, str]]:
    return {runtime: get_adapter(runtime).tool_name_map for runtime in list_runtimes()}


def _alias_map() -> dict[str, str]:
    return build_canonical_alias_map(_runtime_tool_maps().values())


def test_every_adapter_owns_a_full_tool_name_map() -> None:
    for runtime, tool_name_map in _runtime_tool_maps().items():
        assert set(tool_name_map) == set(CANONICAL_TOOL_NAMES), runtime


def test_runtime_alias_maps_come_from_adapter_owned_tables() -> None:
    codex_aliases = build_runtime_alias_map(get_adapter("codex").tool_name_map)
    gemini_aliases = build_runtime_alias_map(get_adapter("gemini").tool_name_map)
    opencode_aliases = build_runtime_alias_map(get_adapter("opencode").tool_name_map)

    assert codex_aliases["apply_patch"] == "file_edit"
    assert gemini_aliases["run_shell_command"] == "shell"
    assert opencode_aliases["question"] == "ask_user"


@pytest.mark.parametrize(
    ("runtime", "tool_name", "expected"),
    [
        ("claude-code", "file_read", "Read"),
        ("codex", "Read", "read_file"),
        ("gemini", "Bash", "run_shell_command"),
        ("opencode", "AskUserQuestion", "question"),
    ],
)
def test_translate_uses_adapter_owned_maps(runtime: str, tool_name: str, expected: str) -> None:
    assert translate(tool_name, get_adapter(runtime).tool_name_map, alias_map=_alias_map()) == expected


def test_translate_for_runtime_uses_adapter_owned_omission_policy() -> None:
    codex = get_adapter("codex")
    gemini = get_adapter("gemini")

    assert codex.auto_discovered_tools is AUTO_DISCOVERED_TOOL_DEFAULTS
    assert gemini.auto_discovered_tools is AUTO_DISCOVERED_TOOL_DEFAULTS

    assert translate_for_runtime(
        "task",
        codex.tool_name_map,
        alias_map=_alias_map(),
        auto_discovered_tools=codex.auto_discovered_tools,
    ) is None
    assert translate_for_runtime(
        "mcp__physics",
        gemini.tool_name_map,
        alias_map=_alias_map(),
        auto_discovered_tools=gemini.auto_discovered_tools,
        drop_mcp_frontmatter_tools=gemini.drop_mcp_frontmatter_tools,
    ) is None


def test_reference_translation_map_comes_from_adapter_policy() -> None:
    mapping = reference_translation_map(get_adapter("opencode").tool_name_map, alias_map=_alias_map())

    assert mapping["ask_user"] == "question"
    assert mapping["slash_command"] == "skill"
    assert mapping["file_read"] == "read_file"


def test_runtime_string_policy_comes_from_live_adapter_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_map = {name: f"fake_{name}" for name in CANONICAL_TOOL_NAMES}
    fake_adapter = SimpleNamespace(
        runtime_name="fake-runtime",
        tool_name_map=fake_map,
        auto_discovered_tools=frozenset({"task"}),
        drop_mcp_frontmatter_tools=True,
    )
    monkeypatch.setattr("gpd.adapters.iter_adapters", lambda: [fake_adapter])
    monkeypatch.setattr(tool_names_module, "_DEFAULT_POLICIES", None)

    assert translate("file_read", "fake-runtime", alias_map={}) == "fake_file_read"
    assert translate_for_runtime("task", "fake-runtime", alias_map={}) is None
    assert translate_for_runtime("mcp__physics", "fake-runtime", alias_map={}) is None
