"""SessionManager with atomic JSON writes for crash-resilient persistence."""

from __future__ import annotations

import hashlib
import logging
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from gpd.mcp.session.models import SessionState
from gpd.mcp.session.search import SearchIndex

logger = logging.getLogger(__name__)


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
        project_root: str,
        session_name: str,
        tags: list[str] | None = None,
        *,
        persist: bool = True,
    ) -> SessionState:
        """Create a new session and persist it immediately."""
        now = datetime.now(tz=UTC)
        session_id = hashlib.sha256(f"{project_name}:{session_name}:{now.isoformat()}".encode()).hexdigest()[:12]

        session = SessionState.new(
            session_id=session_id,
            project_name=project_name,
            project_root=project_root,
            session_name=session_name,
            tags=tags,
        )
        self._active_session = session
        if persist:
            self.save(session)
        return session

    def activate(self, session: SessionState) -> None:
        """Mark an already-loaded session as the current active session."""
        self._active_session = session

    def discard_active_session(self) -> None:
        """Drop the in-memory active session without persisting changes."""
        self._active_session = None

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

        try:
            session = SessionState.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValidationError, ValueError) as exc:
            msg = f"Session file is corrupt: {path}"
            raise ValueError(msg) from exc

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

    def finalize(self, status: str = "paused") -> None:
        """Persist the active session with a terminal non-active status."""
        if self._active_session is None:
            return

        self._active_session.status = status
        self.save()
        self._active_session = None

    def get_latest_session(
        self,
        project_name: str | None = None,
        project_root: str | None = None,
    ) -> SessionState | None:
        """Return the most recently modified valid session, optionally scoped to a project."""
        for session in self._iter_sessions(project_name=project_name, project_root=project_root, limit=1):
            return session
        return None

    def list_sessions(
        self,
        limit: int = 50,
        project_name: str | None = None,
        project_root: str | None = None,
    ) -> list[SessionState]:
        """List valid sessions sorted by modification time (newest first)."""
        return list(self._iter_sessions(project_name=project_name, project_root=project_root, limit=limit))

    def _iter_sessions(
        self,
        *,
        project_name: str | None = None,
        project_root: str | None = None,
        limit: int | None = None,
    ) -> list[SessionState]:
        """Yield valid sessions in newest-first order, skipping unreadable files."""
        exact_matches: list[SessionState] = []
        legacy_matches: list[SessionState] = []
        sessions: list[SessionState] = []
        for path in self._sorted_session_files():
            session = self._read_session_file(path)
            if session is None:
                continue
            match_score = self._project_match_score(
                session,
                project_name=project_name,
                project_root=project_root,
            )
            if match_score < 0:
                continue
            if match_score == 2:
                exact_matches.append(session)
            elif match_score == 1:
                legacy_matches.append(session)
            else:
                sessions.append(session)

        combined = [*exact_matches, *legacy_matches, *sessions]
        return combined[:limit] if limit is not None else combined

    def _project_match_score(
        self,
        session: SessionState,
        *,
        project_name: str | None,
        project_root: str | None,
    ) -> int:
        """Return how strongly a session matches the requested project scope."""
        if project_name is None and project_root is None:
            return 0

        if project_root is not None:
            if session.project_root == project_root:
                return 2
            if not session.project_root and project_name is not None and session.project_name == project_name:
                return 1
            return -1

        if project_name is not None and session.project_name == project_name:
            return 1
        return -1

    def _sorted_session_files(self) -> list[Path]:
        """Return session files ordered by newest mtime first."""
        dated_paths: list[tuple[float, Path]] = []
        for path in self._sessions_dir.glob("*.json"):
            try:
                dated_paths.append((path.stat().st_mtime, path))
            except OSError:
                logger.warning("Skipping unreadable session file metadata: %s", path)
        dated_paths.sort(key=lambda item: item[0], reverse=True)
        return [path for _, path in dated_paths]

    def _read_session_file(self, path: Path) -> SessionState | None:
        """Read a session file, returning None when the file is corrupt."""
        try:
            return SessionState.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValidationError, ValueError):
            logger.warning("Skipping corrupt session file: %s", path)
            return None
