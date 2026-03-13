"""GPD adapters — runtime-specific adapters for AI agents.

Provides a common interface for generating skill files, agent definitions,
hook configs, and tool name translations across runtimes.
"""

from __future__ import annotations

from importlib import import_module

from gpd.adapters.base import RuntimeAdapter
from gpd.adapters.runtime_catalog import (
    get_runtime_descriptor,
    iter_runtime_descriptors,
    list_runtime_names,
)

_REGISTRY: dict[str, type[RuntimeAdapter]] = {}
_LOADED = False


def _module_name_for_runtime(runtime_name: str) -> str:
    """Return the adapter module path segment for a runtime id."""
    return runtime_name.replace("-", "_")


def _load_adapter_class(runtime_name: str) -> type[RuntimeAdapter]:
    """Import and return the adapter class that owns *runtime_name*."""
    module = import_module(f"gpd.adapters.{_module_name_for_runtime(runtime_name)}")

    matches: list[type[RuntimeAdapter]] = []
    for value in vars(module).values():
        if not isinstance(value, type) or not issubclass(value, RuntimeAdapter) or value is RuntimeAdapter:
            continue
        try:
            if value().runtime_name == runtime_name:
                matches.append(value)
        except Exception:
            continue

    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise RuntimeError(f"No RuntimeAdapter implementation found for runtime {runtime_name!r}")
    raise RuntimeError(f"Multiple RuntimeAdapter implementations found for runtime {runtime_name!r}")


def _ensure_loaded() -> None:
    global _LOADED  # noqa: PLW0603
    if _LOADED:
        return

    registry: dict[str, type[RuntimeAdapter]] = {}
    for descriptor in iter_runtime_descriptors():
        registry[descriptor.runtime_name] = _load_adapter_class(descriptor.runtime_name)

    _REGISTRY.clear()
    _REGISTRY.update(registry)
    _LOADED = True


def get_adapter(runtime: str) -> RuntimeAdapter:
    """Get an adapter instance for the given runtime name.

    Raises ``KeyError`` if the runtime is not supported.
    """
    _ensure_loaded()
    if runtime not in _REGISTRY:
        supported = ", ".join(sorted(_REGISTRY.keys()))
        raise KeyError(f"Unknown runtime {runtime!r}. Supported: {supported}")
    return _REGISTRY[runtime]()


def iter_adapters() -> list[RuntimeAdapter]:
    """Return adapter instances in registry order."""
    _ensure_loaded()
    return [adapter_cls() for adapter_cls in _REGISTRY.values()]


def list_runtimes() -> list[str]:
    """Return all supported runtime names."""
    _ensure_loaded()
    return [descriptor.runtime_name for descriptor in iter_runtime_descriptors() if descriptor.runtime_name in _REGISTRY]


__all__ = [
    "RuntimeAdapter",
    "get_adapter",
    "get_runtime_descriptor",
    "iter_adapters",
    "iter_runtime_descriptors",
    "list_runtime_names",
    "list_runtimes",
]
