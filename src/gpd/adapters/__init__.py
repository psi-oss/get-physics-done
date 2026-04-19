"""GPD adapters — runtime-specific adapters for AI agents.

Provides a common interface for generating skill files, agent definitions,
hook configs, and tool name translations across runtimes.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

from gpd.adapters.runtime_catalog import (
    RuntimeDescriptor,
    get_runtime_descriptor,
    iter_runtime_descriptors,
    list_runtime_names,
)

if TYPE_CHECKING:
    from gpd.adapters.base import RuntimeAdapter

_REGISTRY: dict[str, type[RuntimeAdapter]] = {}
_LOADED = False


def _load_adapter_class(descriptor: RuntimeDescriptor) -> type[RuntimeAdapter]:
    """Import and return the adapter class declared by *descriptor*."""
    from gpd.adapters.base import RuntimeAdapter

    module = import_module(descriptor.adapter_module)
    try:
        adapter_class = getattr(module, descriptor.adapter_class)
    except AttributeError as exc:
        raise RuntimeError(
            f"Adapter class {descriptor.adapter_class!r} not found in module {descriptor.adapter_module!r} "
            f"for runtime {descriptor.runtime_name!r}"
        ) from exc

    if not isinstance(adapter_class, type) or not issubclass(adapter_class, RuntimeAdapter) or adapter_class is RuntimeAdapter:
        raise RuntimeError(
            f"Adapter class {descriptor.adapter_class!r} in module {descriptor.adapter_module!r} "
            f"for runtime {descriptor.runtime_name!r} is not a RuntimeAdapter subclass"
        )
    return adapter_class


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
        registry[descriptor.runtime_name] = _load_adapter_class(descriptor)

    _REGISTRY.clear()
    _REGISTRY.update(registry)
    _LOADED = True


def _ensure_runtime_loaded(runtime_name: str) -> type[RuntimeAdapter]:
    """Return the adapter class for one runtime, loading only that runtime if needed."""

    if runtime_name in _REGISTRY:
        return _REGISTRY[runtime_name]

    supported_runtime_names = list_runtimes()
    if runtime_name not in supported_runtime_names:
        supported = ", ".join(sorted(supported_runtime_names))
        raise KeyError(f"Unknown runtime {runtime_name!r}. Supported: {supported}")

    descriptor = get_runtime_descriptor(runtime_name)
    adapter_class = _load_adapter_class(descriptor)
    _REGISTRY[runtime_name] = adapter_class
    return adapter_class


def get_adapter(runtime: str) -> RuntimeAdapter:
    """Get an adapter instance for the given runtime name.

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
