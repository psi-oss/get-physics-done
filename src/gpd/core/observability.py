"""Observability helpers for GPD."""

from __future__ import annotations

import functools
import inspect
from collections.abc import Callable, Generator
from contextlib import contextmanager

import logfire

__all__ = [
    "gpd_span",
    "instrument_gpd_function",
]


@contextmanager
def gpd_span(name: str, **attrs: object) -> Generator[logfire.LogfireSpan, None, None]:
    """Create a Logfire span with GPD-specific attributes."""
    prefixed: dict[str, object] = {}
    for key, value in attrs.items():
        attr_key = key if key.startswith("gpd.") else f"gpd.{key}"
        prefixed[attr_key] = value

    with logfire.span(f"gpd.{name}", name=name, **prefixed) as span:
        yield span


def instrument_gpd_function(
    span_name: str | None = None,
    **default_attrs: object,
) -> Callable:
    """Decorator factory for Logfire instrumentation of GPD functions."""

    def decorator(func: Callable) -> Callable:
        name = span_name or f"{func.__module__}.{func.__qualname__}"

        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: object, **kwargs: object) -> object:
                with gpd_span(name, **default_attrs):
                    return await func(*args, **kwargs)

            return async_wrapper

        @functools.wraps(func)
        def sync_wrapper(*args: object, **kwargs: object) -> object:
            with gpd_span(name, **default_attrs):
                return func(*args, **kwargs)

        return sync_wrapper

    return decorator
