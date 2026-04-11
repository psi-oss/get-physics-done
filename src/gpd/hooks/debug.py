"""Shared debug logging helpers for hook surfaces."""

from __future__ import annotations

import os
import sys

from gpd.core.constants import ENV_GPD_DEBUG


def hook_debug(msg: str) -> None:
    """Emit one hook debug line when GPD debug logging is enabled."""
    if os.environ.get(ENV_GPD_DEBUG):
        sys.stderr.write(f"[gpd-debug] {msg}\n")
