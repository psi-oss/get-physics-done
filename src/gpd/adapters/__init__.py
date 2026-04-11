"""GPD adapters — runtime-specific adapters for AI agents.

Provides a common interface for generating skill files, agent definitions,
hook configs, and tool name translations across runtimes.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

from gpd.adapters.runtime_catalog import (
    get_runtime_descriptor,
    iter_runtime_descriptors,
    list_runtime_names,
    normalize_runtime_name,
)

if TYPE_CHECKING:
    from gpd.adapters.base import RuntimeAdapter

_REGISTRY: dict[str, type[RuntimeAdapter]] = {}
_LOADED = False


def _module_name_for_runtime(runtime_name: str) -> str:
    """Return the catalog-owned adapter module path segment for a runtime id."""
    return get_runtime_descriptor(runtime_name).adapter_module


def _load_adapter_class(runtime_name: str, *, adapter_module: str | None = None) -> type[RuntimeAdapter]:
    """Import and return the adapter class that owns *runtime_name*."""
    from gpd.adapters.base import RuntimeAdapter

    module = import_module(f"gpd.adapters.{adapter_module or _module_name_for_runtime(runtime_name)}")

    matches: list[type[RuntimeAdapter]] = []
    for value in vars(module).values():
        if not isinstance(value, type) or not issubclass(value, RuntimeAdapter) or value is RuntimeAdapter:
            continue
        matches.append(value)

    if len(matches) == 1:
        adapter_runtime_name = matches[0]().runtime_name
        if adapter_runtime_name != runtime_name:
            raise RuntimeError(
                f"Adapter runtime_name mismatch for catalog runtime {runtime_name!r}: "
                f"loaded {adapter_runtime_name!r}"
            )
        return matches[0]
    if not matches:
        raise RuntimeError(f"No RuntimeAdapter implementation found for runtime {runtime_name!r}")
    raise RuntimeError(f"Multiple RuntimeAdapter implementations found for runtime {runtime_name!r}")


def _ensure_loaded() -> None:
    global _LOADED  # noqa: PLW0603
    if _LOADED:
        return

    registry: dict[str, type[RuntimeAdapter]] = {}
    seen_runtime_names: set[str] = set()
    for descriptor in iter_runtime_descriptors():
        if descriptor.runtime_name in seen_runtime_names:
            raise RuntimeError(f"Duplicate runtime name in runtime catalog: {descriptor.runtime_name!r}")
        seen_runtime_names.add(descriptor.runtime_name)
        registry[descriptor.runtime_name] = _load_adapter_class(
            descriptor.runtime_name,
            adapter_module=descriptor.adapter_module,
        )

    _REGISTRY.clear()
    _REGISTRY.update(registry)
    _LOADED = True


def _ensure_runtime_loaded(runtime_name: str) -> type[RuntimeAdapter]:
    """Return the adapter class for one runtime, loading only that runtime if needed."""

    runtime_name = normalize_runtime_name(runtime_name) or runtime_name

    if runtime_name in _REGISTRY:
        return _REGISTRY[runtime_name]

    supported_runtime_names = list_runtimes()
    if runtime_name not in supported_runtime_names:
        supported = ", ".join(sorted(supported_runtime_names))
        raise KeyError(f"Unknown runtime {runtime_name!r}. Supported: {supported}")

    adapter_class = _load_adapter_class(runtime_name)
    _REGISTRY[runtime_name] = adapter_class
    return adapter_class


def get_adapter(runtime: str) -> RuntimeAdapter:
    """Get an adapter instance for the given runtime name.

    Accepts canonical runtime ids plus catalog display names, aliases, and install flags.
    Raises ``KeyError`` if the runtime is not supported.
    """
    adapter_class = _ensure_runtime_loaded(runtime)
    return adapter_class()


def iter_adapters() -> list[RuntimeAdapter]:
    """Return adapter instances in registry order."""
    return [get_adapter(runtime_name) for runtime_name in list_runtimes()]


def list_runtimes() -> list[str]:
    """Return all supported runtime names."""
    return [descriptor.runtime_name for descriptor in iter_runtime_descriptors()]


def __getattr__(name: str):
    if name == "RuntimeAdapter":
        from gpd.adapters.base import RuntimeAdapter

        return RuntimeAdapter
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "RuntimeAdapter",
    "get_adapter",
    "get_runtime_descriptor",
    "iter_adapters",
    "iter_runtime_descriptors",
    "list_runtime_names",
    "list_runtimes",
]
