"""Shared active-runtime command lookup helpers."""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

__all__ = ["format_active_runtime_command", "resolve_active_runtime_descriptor"]

logger = logging.getLogger(__name__)


def resolve_active_runtime_descriptor(
    *,
    cwd: Path | None = None,
    detect_runtime: Callable[..., str | None] | None = None,
) -> object | None:
    """Return the active runtime descriptor, or ``None`` when resolution fails."""
    from gpd.adapters import get_adapter
    from gpd.hooks.runtime_detect import RUNTIME_UNKNOWN, detect_runtime_for_gpd_use

    detector = detect_runtime or detect_runtime_for_gpd_use
    try:
        runtime_name = detector(cwd=cwd)
        if runtime_name in (None, RUNTIME_UNKNOWN):
            return None
        return get_adapter(runtime_name).runtime_descriptor
    except Exception as exc:
        logger.warning("Active runtime resolution failed: %s", exc)
        return None


def format_active_runtime_command(
    action: str,
    *,
    cwd: Path | None = None,
    detect_runtime: Callable[..., str | None] | None = None,
    fallback: str | None = None,
) -> str | None:
    """Return the active runtime's formatted public command, or *fallback*."""
    from gpd.adapters import get_adapter

    descriptor = resolve_active_runtime_descriptor(cwd=cwd, detect_runtime=detect_runtime)
    if descriptor is None:
        return fallback
    try:
        return get_adapter(descriptor.runtime_name).format_command(action)
    except Exception as exc:
        logger.warning("Active runtime command formatting failed for %s: %s", action, exc)
        return fallback
