"""Configuration paths and directory initialization for GPD+."""

from __future__ import annotations

from pathlib import Path

GPDPLUS_DIR: Path = Path.home() / ".gpdplus"
"""Root configuration directory for GPD+."""

SESSIONS_DIR: Path = GPDPLUS_DIR / "sessions"
"""Directory for session JSON files."""

CACHE_DIR: Path = GPDPLUS_DIR / "cache"
"""Directory for cached MCP counts and other transient data."""

DB_PATH: Path = GPDPLUS_DIR / "search.db"
"""Path to the SQLite FTS5 search database."""

MCP_SOURCES_PATH: Path = GPDPLUS_DIR / "mcp-sources.yaml"
"""Path to YAML config defining MCP tool sources (Modal, local, external, custom)."""


def ensure_dirs() -> None:
    """Create all GPD+ directories if they do not exist."""
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
