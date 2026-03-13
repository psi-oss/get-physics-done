"""Runtime-agnostic helpers for canonical GPD tool translation."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from importlib import import_module

CANONICAL_TOOL_NAMES: tuple[str, ...] = (
    "file_read",
    "file_write",
    "file_edit",
    "shell",
    "search_files",
    "find_files",
    "web_search",
    "web_fetch",
    "notebook_edit",
    "agent",
    "ask_user",
    "todo_write",
    "task",
    "slash_command",
    "tool_search",
)
"""Canonical GPD tool names supported across runtimes."""

CONTEXTUAL_TOOL_REFERENCE_NAMES: frozenset[str] = frozenset(
    {
        "Read",
        "Write",
        "Edit",
        "Task",
        "Agent",
        "shell",
        "task",
        "agent",
    }
)
"""Tool names that should only be rewritten in tool-like prose contexts."""


@dataclass(frozen=True, slots=True)
class RuntimeToolPolicy:
    runtime_name: str
    tool_name_map: Mapping[str, str]
    auto_discovered_tools: frozenset[str] = frozenset()
    drop_mcp_frontmatter_tools: bool = False


_DEFAULT_POLICIES: dict[str, RuntimeToolPolicy] | None = None


def _load_default_policies() -> dict[str, RuntimeToolPolicy]:
    from gpd.adapters.base import RuntimeAdapter
    from gpd.adapters.runtime_catalog import iter_runtime_descriptors

    policies: dict[str, RuntimeToolPolicy] = {}
    for descriptor in iter_runtime_descriptors():
        module = import_module(f"gpd.adapters.{descriptor.runtime_name.replace('-', '_')}")
        for value in module.__dict__.values():
            if not isinstance(value, type) or not issubclass(value, RuntimeAdapter) or value is RuntimeAdapter:
                continue
            adapter = value()
            if adapter.runtime_name != descriptor.runtime_name:
                continue
            policies[adapter.runtime_name] = RuntimeToolPolicy(
                runtime_name=adapter.runtime_name,
                tool_name_map=getattr(adapter, "tool_name_map", {}),
                auto_discovered_tools=frozenset(getattr(adapter, "auto_discovered_tools", frozenset())),
                drop_mcp_frontmatter_tools=bool(getattr(adapter, "drop_mcp_frontmatter_tools", False)),
            )
            break
    return policies


def _default_policies() -> dict[str, RuntimeToolPolicy]:
    global _DEFAULT_POLICIES  # noqa: PLW0603
    if _DEFAULT_POLICIES is None:
        _DEFAULT_POLICIES = _load_default_policies()
    return _DEFAULT_POLICIES


def _default_alias_map() -> dict[str, str]:
    return build_canonical_alias_map(policy.tool_name_map for policy in _default_policies().values())


def _policy_from_runtime(runtime: str) -> RuntimeToolPolicy | None:
    return _default_policies().get(runtime)


def _coerce_policy(
    tool_name_map_or_runtime: Mapping[str, str] | str,
    *,
    auto_discovered_tools: frozenset[str],
    drop_mcp_frontmatter_tools: bool,
) -> RuntimeToolPolicy:
    if isinstance(tool_name_map_or_runtime, str):
        policy = _policy_from_runtime(tool_name_map_or_runtime)
        if policy is not None:
            return policy
        return RuntimeToolPolicy(
            runtime_name=tool_name_map_or_runtime,
            tool_name_map={},
            auto_discovered_tools=auto_discovered_tools,
            drop_mcp_frontmatter_tools=drop_mcp_frontmatter_tools,
        )
    return RuntimeToolPolicy(
        runtime_name="",
        tool_name_map=tool_name_map_or_runtime,
        auto_discovered_tools=auto_discovered_tools,
        drop_mcp_frontmatter_tools=drop_mcp_frontmatter_tools,
    )


def build_runtime_alias_map(tool_name_map: Mapping[str, str]) -> dict[str, str]:
    """Build runtime-native alias -> canonical-name mapping."""
    return {runtime_name: canonical_name for canonical_name, runtime_name in tool_name_map.items()}


def build_canonical_alias_map(tool_name_maps: Iterable[Mapping[str, str]]) -> dict[str, str]:
    """Merge one or more runtime alias maps into a canonical lookup table."""
    aliases: dict[str, str] = {}
    for tool_name_map in tool_name_maps:
        aliases.update(build_runtime_alias_map(tool_name_map))
    return aliases


def canonical(name: str, alias_map: Mapping[str, str] | None = None) -> str:
    """Normalize a tool name to its canonical GPD form."""
    if name in CANONICAL_TOOL_NAMES:
        return name
    resolved_alias_map = _default_alias_map() if alias_map is None else alias_map
    return resolved_alias_map.get(name, name)


def translate(
    name: str,
    tool_name_map: Mapping[str, str] | str,
    *,
    alias_map: Mapping[str, str] | None = None,
) -> str:
    """Translate a canonical GPD tool name using one runtime's tool map."""
    policy = _coerce_policy(
        tool_name_map,
        auto_discovered_tools=frozenset(),
        drop_mcp_frontmatter_tools=False,
    )
    resolved_alias_map = _default_alias_map() if alias_map is None else alias_map
    canon = canonical(name, resolved_alias_map)
    return policy.tool_name_map.get(canon, canon)


def translate_for_runtime(
    name: str,
    tool_name_map: Mapping[str, str] | str,
    *,
    alias_map: Mapping[str, str] | None = None,
    auto_discovered_tools: frozenset[str] = frozenset(),
    drop_mcp_frontmatter_tools: bool = False,
) -> str | None:
    """Translate a tool for runtime frontmatter/body conversion."""
    policy = _coerce_policy(
        tool_name_map,
        auto_discovered_tools=auto_discovered_tools,
        drop_mcp_frontmatter_tools=drop_mcp_frontmatter_tools,
    )
    resolved_alias_map = _default_alias_map() if alias_map is None else alias_map
    if name.startswith("mcp__"):
        return None if policy.drop_mcp_frontmatter_tools else name

    canon = canonical(name, resolved_alias_map)
    if canon in policy.auto_discovered_tools:
        return None
    return translate(canon, policy.tool_name_map, alias_map=resolved_alias_map)


def reference_translation_map(
    tool_name_map: Mapping[str, str] | str,
    *,
    alias_map: Mapping[str, str] | None = None,
    auto_discovered_tools: frozenset[str] = frozenset(),
    drop_mcp_frontmatter_tools: bool = False,
) -> dict[str, str]:
    """Build a canonical-source -> runtime-target translation map."""
    resolved_alias_map = _default_alias_map() if alias_map is None else alias_map
    mapping: dict[str, str | None] = {
        name: translate_for_runtime(
            name,
            tool_name_map,
            alias_map=resolved_alias_map,
            auto_discovered_tools=auto_discovered_tools,
            drop_mcp_frontmatter_tools=drop_mcp_frontmatter_tools,
        )
        for name in CANONICAL_TOOL_NAMES
    }
    return {source: target for source, target in mapping.items() if target and source != target}


__all__ = [
    "CANONICAL_TOOL_NAMES",
    "CONTEXTUAL_TOOL_REFERENCE_NAMES",
    "RuntimeToolPolicy",
    "build_canonical_alias_map",
    "build_runtime_alias_map",
    "canonical",
    "reference_translation_map",
    "translate",
    "translate_for_runtime",
]
