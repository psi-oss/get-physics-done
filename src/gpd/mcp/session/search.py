"""SQLite FTS5 search index for session history."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from gpd.mcp.session.models import SessionState

logger = logging.getLogger(__name__)


class SearchIndex:
    """SQLite FTS5 search index maintained alongside JSON session files.

    Provides full-text search across session metadata (project names,
    milestone descriptions, research findings, tool outputs, error
    messages, and tags). Falls back to LIKE queries if FTS5 is not
    available in the SQLite build.
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._fts5_available = True
        self._conn: sqlite3.Connection | None = None
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the database schema with FTS5 and metadata tables."""
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.row_factory = sqlite3.Row

        # Create metadata table first (always available)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS session_meta (
                session_id TEXT PRIMARY KEY,
                project_name TEXT NOT NULL,
                session_name TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                elapsed_seconds REAL DEFAULT 0,
                mcp_count INTEGER DEFAULT 0
            )
        """)

        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_meta_project
            ON session_meta(project_name)
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_meta_status
            ON session_meta(status)
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_meta_created
            ON session_meta(created_at)
        """)

        # Try to create FTS5 virtual table
        try:
            self._conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS session_search USING fts5(
                    session_id UNINDEXED,
                    project_name,
                    session_name,
                    milestone_text,
                    research_text,
                    tool_text,
                    error_text,
                    tags,
                    tokenize = 'porter unicode61',
                    prefix = '2,3'
                )
            """)
        except sqlite3.OperationalError:
            self._fts5_available = False
            logger.warning("FTS5 not available in this SQLite build; falling back to LIKE queries")

        self._conn.commit()

    def index_session(self, session: SessionState) -> None:
        """Index or re-index a session in both FTS5 and metadata tables."""
        if self._conn is None:
            msg = "SearchIndex is closed"
            raise RuntimeError(msg)

        # Delete existing rows for this session
        self._conn.execute(
            "DELETE FROM session_meta WHERE session_id = ?",
            (session.session_id,),
        )

        if self._fts5_available:
            self._conn.execute(
                "DELETE FROM session_search WHERE session_id = ?",
                (session.session_id,),
            )

        # Insert metadata
        self._conn.execute(
            """INSERT INTO session_meta
               (session_id, project_name, session_name, status, created_at,
                updated_at, elapsed_seconds, mcp_count)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                session.session_id,
                session.project_name,
                session.session_name,
                session.status,
                session.created_at.isoformat(),
                session.updated_at.isoformat(),
                session.elapsed_seconds,
                session.mcp_count,
            ),
        )

        # Insert FTS5 row
        if self._fts5_available:
            milestone_text = "\n".join(f"{m.name}: {m.description}" for m in session.milestones)
            self._conn.execute(
                """INSERT INTO session_search
                   (session_id, project_name, session_name, milestone_text,
                    research_text, tool_text, error_text, tags)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    session.session_id,
                    session.project_name,
                    session.session_name,
                    milestone_text,
                    "\n".join(session.research_findings),
                    "\n".join(session.tool_outputs),
                    "\n".join(session.error_messages),
                    "\n".join(session.tags),
                ),
            )

        self._conn.commit()

    def search(self, query: str, limit: int = 20) -> list[dict[str, object]]:
        """Full-text search across session content.

        Uses FTS5 MATCH with BM25 ranking when available, falls back
        to LIKE queries on session_meta otherwise.
        """
        if self._conn is None:
            msg = "SearchIndex is closed"
            raise RuntimeError(msg)

        if self._fts5_available:
            rows = self._conn.execute(
                """SELECT
                       s.session_id,
                       m.project_name,
                       m.session_name,
                       snippet(session_search, 3, '<b>', '</b>', '...', 32) AS context_snippet,
                       bm25(session_search) AS rank
                   FROM session_search s
                   JOIN session_meta m ON s.session_id = m.session_id
                   WHERE session_search MATCH ?
                   ORDER BY rank
                   LIMIT ?""",
                (query, limit),
            ).fetchall()
        else:
            like_pattern = f"%{query}%"
            rows = self._conn.execute(
                """SELECT
                       session_id,
                       project_name,
                       session_name,
                       '' AS context_snippet,
                       0 AS rank
                   FROM session_meta
                   WHERE project_name LIKE ? OR session_name LIKE ?
                   ORDER BY created_at DESC
                   LIMIT ?""",
                (like_pattern, like_pattern, limit),
            ).fetchall()

        return [
            {
                "session_id": row["session_id"],
                "project_name": row["project_name"],
                "session_name": row["session_name"],
                "context_snippet": row["context_snippet"],
                "rank": row["rank"],
            }
            for row in rows
        ]

    def search_structured(
        self,
        project: str = "",
        status: str = "",
        after: str = "",
        before: str = "",
    ) -> list[dict[str, object]]:
        """Query sessions by structured metadata filters."""
        if self._conn is None:
            msg = "SearchIndex is closed"
            raise RuntimeError(msg)

        conditions: list[str] = []
        params: list[str] = []

        if project:
            conditions.append("project_name = ?")
            params.append(project)
        if status:
            conditions.append("status = ?")
            params.append(status)
        if after:
            conditions.append("created_at >= ?")
            params.append(after)
        if before:
            conditions.append("created_at <= ?")
            params.append(before)

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        rows = self._conn.execute(
            f"SELECT * FROM session_meta WHERE {where_clause} ORDER BY created_at DESC",  # noqa: S608
            params,
        ).fetchall()

        return [dict(row) for row in rows]

    def rebuild_index(self, sessions_dir: Path) -> int:
        """Rebuild the FTS5 index from all JSON session files on disk."""
        if self._conn is None:
            msg = "SearchIndex is closed"
            raise RuntimeError(msg)

        count = 0
        for path in sessions_dir.glob("*.json"):
            try:
                session = SessionState.model_validate_json(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            self.index_session(session)
            count += 1
        return count

    def close(self) -> None:
        """Close the SQLite connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None
