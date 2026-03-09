"""Configuration paths and directory initialization for GPD session tooling."""

from __future__ import annotations

from pathlib import Path

GPD_HOME_DIR: Path = Path.home() / ".gpd"
"""Root configuration directory for GPD session and MCP state."""

SESSIONS_DIR: Path = GPD_HOME_DIR / "sessions"
"""Directory for session JSON files."""

CACHE_DIR: Path = GPD_HOME_DIR / "cache"
"""Directory for cached MCP counts and other transient data."""

DB_PATH: Path = GPD_HOME_DIR / "search.db"
"""Path to the SQLite FTS5 search database."""

MCP_SOURCES_PATH: Path = GPD_HOME_DIR / "mcp-sources.yaml"
"""Path to YAML config defining MCP tool sources (Modal, local, external, custom)."""


def ensure_dirs() -> None:
    """Create all GPD session directories if they do not exist."""
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
