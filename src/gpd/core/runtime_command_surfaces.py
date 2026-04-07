"""Shared active-runtime command lookup helpers."""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from gpd.adapters.runtime_catalog import RuntimeDescriptor, get_runtime_descriptor, normalize_runtime_name
from gpd.command_labels import validated_public_command_prefix

__all__ = ["format_active_runtime_command", "resolve_active_runtime_descriptor"]

logger = logging.getLogger(__name__)


def resolve_active_runtime_descriptor(
    *,
    cwd: Path | None = None,
    detect_runtime: Callable[..., str | None] | None = None,
) -> RuntimeDescriptor | None:
    """Return the active runtime descriptor, or ``None`` when resolution fails."""
    from gpd.hooks.runtime_detect import RUNTIME_UNKNOWN, detect_runtime_for_gpd_use

    detector = detect_runtime or detect_runtime_for_gpd_use
    try:
        runtime_name = detector(cwd=cwd)
    except Exception as exc:
        logger.warning("Active runtime resolution failed: %s", exc)
        return None
    if runtime_name in (None, RUNTIME_UNKNOWN):
        return None

    normalized_runtime = normalize_runtime_name(runtime_name)
    if normalized_runtime is None:
        return None
    try:
        return get_runtime_descriptor(normalized_runtime)
    except KeyError:
        return None


def format_active_runtime_command(
    action: str,
    *,
    cwd: Path | None = None,
    detect_runtime: Callable[..., str | None] | None = None,
    fallback: str | None = None,
) -> str | None:
    """Return the active runtime's formatted public command, or *fallback* when no runtime is detected."""
    descriptor = resolve_active_runtime_descriptor(cwd=cwd, detect_runtime=detect_runtime)
    if descriptor is None:
        return fallback
    return f"{validated_public_command_prefix(descriptor)}{action}"
