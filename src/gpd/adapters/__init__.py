"""GPD adapters — runtime-specific adapters for AI coding tools.

Provides a common interface for generating skill files, agent definitions,
hook configs, and tool name translations across runtimes.
"""

from __future__ import annotations

from gpd.adapters.base import RuntimeAdapter

_REGISTRY: dict[str, type[RuntimeAdapter]] = {}
_LOADED = False


def _ensure_loaded() -> None:
    global _LOADED  # noqa: PLW0603
    if _LOADED:
        return
    _LOADED = True
    from gpd.adapters.agentic_builder import AgenticBuilderAdapter
    from gpd.adapters.claude_code import ClaudeCodeAdapter
    from gpd.adapters.codex import CodexAdapter
    from gpd.adapters.gemini import GeminiAdapter
    from gpd.adapters.opencode import OpenCodeAdapter

    for cls in (ClaudeCodeAdapter, CodexAdapter, GeminiAdapter, OpenCodeAdapter, AgenticBuilderAdapter):
        _REGISTRY[cls().runtime_name] = cls


def get_adapter(runtime: str) -> RuntimeAdapter:
    """Get an adapter instance for the given runtime name.

    Raises ``KeyError`` if the runtime is not supported.
    """
    _ensure_loaded()
    if runtime not in _REGISTRY:
        supported = ", ".join(sorted(_REGISTRY.keys()))
        raise KeyError(f"Unknown runtime {runtime!r}. Supported: {supported}")
    return _REGISTRY[runtime]()


def list_runtimes() -> list[str]:
    """Return all supported runtime names."""
    _ensure_loaded()
    return sorted(_REGISTRY.keys())


__all__ = ["RuntimeAdapter", "get_adapter", "list_runtimes"]
