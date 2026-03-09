"""SessionManager with atomic JSON writes for crash-resilient persistence."""

from __future__ import annotations

import hashlib
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from gpd.mcp.session.models import SessionState
from gpd.mcp.session.search import SearchIndex


class SessionManager:
    """Manages session lifecycle: create, save, load, resume, close.

    JSON files in sessions_dir are the source of truth. Every save
    uses atomic write (tempfile + os.replace) to prevent corruption
    on SIGINT. The search index is updated alongside every write.
    """

    def __init__(self, sessions_dir: Path, search_index: SearchIndex) -> None:
        self._sessions_dir = sessions_dir
        self._search_index = search_index
        self._active_session: SessionState | None = None
        self._sessions_dir.mkdir(parents=True, exist_ok=True)

    @property
    def active_session(self) -> SessionState | None:
        """Return the currently active session, if any."""
        return self._active_session

    def create(
        self,
        project_name: str,
        session_name: str,
        tags: list[str] | None = None,
    ) -> SessionState:
        """Create a new session and persist it immediately."""
        now = datetime.now(tz=UTC)
        session_id = hashlib.sha256(f"{project_name}:{session_name}:{now.isoformat()}".encode()).hexdigest()[:12]

        session = SessionState.new(
            session_id=session_id,
            project_name=project_name,
            session_name=session_name,
            tags=tags,
        )
        self._active_session = session
        self.save(session)
        return session

    def save(self, session: SessionState | None = None) -> None:
        """Save session state atomically to JSON and update search index."""
        target = session or self._active_session
        if target is None:
            msg = "No session to save"
            raise ValueError(msg)

        target.updated_at = datetime.now(tz=UTC)
        path = self._sessions_dir / f"{target.session_id}.json"
        self._atomic_write(path, target.model_dump_json(indent=2))
        self._search_index.index_session(target)

    def _atomic_write(self, path: Path, data: str) -> None:
        """Write data to path using tempfile + os.replace for atomicity.

        This prevents JSON corruption when the process is interrupted
        mid-write (e.g., by SIGINT). The temp file is created in the
        same directory so os.replace is guaranteed to be atomic on
        the same filesystem.
        """
        fd = None
        tmp_path = None
        try:
            fd, tmp_path = tempfile.mkstemp(
                prefix=".session-",
                suffix=".tmp",
                dir=str(path.parent),
            )
            os.write(fd, data.encode())
            os.fsync(fd)
            os.close(fd)
            fd = None  # Mark as closed
            os.replace(tmp_path, str(path))
        except BaseException:
            if fd is not None:
                os.close(fd)
            if tmp_path is not None and Path(tmp_path).exists():
                os.unlink(tmp_path)
            raise

    def load(self, session_id: str) -> SessionState:
        """Load a session from its JSON file and set it as active."""
        path = self._sessions_dir / f"{session_id}.json"
        if not path.exists():
            msg = f"Session file not found: {path}"
            raise FileNotFoundError(msg)

        session = SessionState.model_validate_json(path.read_text(encoding="utf-8"))
        self._active_session = session
        return session

    def save_checkpoint(self, reason: str = "manual") -> None:
        """Save a checkpoint of the active session.

        Updates status to 'interrupted' for SIGINT, preserves current
        status for other reasons.
        """
        if self._active_session is None:
            return

        if reason == "interrupted":
            self._active_session.status = "interrupted"

        self._active_session.last_checkpoint_at = datetime.now(tz=UTC)
        self.save()

    def close(self) -> None:
        """Save final state and release the active session."""
        if self._active_session is not None:
            self.save()
            self._active_session = None

    def get_latest_session(self) -> SessionState | None:
        """Return the most recently modified session, or None."""
        json_files = sorted(
            self._sessions_dir.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for f in json_files:
            try:
                return SessionState.model_validate_json(f.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
        return None

    def list_sessions(self, limit: int = 50) -> list[SessionState]:
        """List sessions sorted by modification time (newest first)."""
        json_files = sorted(
            self._sessions_dir.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        sessions: list[SessionState] = []
        for path in json_files[:limit]:
            try:
                sessions.append(SessionState.model_validate_json(path.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                continue
        return sessions
