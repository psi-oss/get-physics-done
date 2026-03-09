"""Session persistence layer for GPD.

Provides Pydantic models for session state, a SessionManager with
atomic JSON writes, and a SQLite FTS5 search index for session history.
"""

from __future__ import annotations

from gpd.mcp.session.manager import SessionManager
from gpd.mcp.session.models import MilestoneState, SessionState
from gpd.mcp.session.search import SearchIndex

__all__ = ["MilestoneState", "SearchIndex", "SessionManager", "SessionState"]
