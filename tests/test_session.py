"""Tests for session persistence: models, manager, and search index."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from gpd.mcp.session.manager import SessionManager
from gpd.mcp.session.models import MilestoneState, SessionState
from gpd.mcp.session.search import SearchIndex


@pytest.fixture()
def search_index(tmp_path: Path) -> SearchIndex:
    """Create a SearchIndex backed by a temp database."""
    idx = SearchIndex(db_path=tmp_path / "search.db")
    yield idx
    idx.close()


@pytest.fixture()
def session_manager(tmp_path: Path, search_index: SearchIndex) -> SessionManager:
    """Create a SessionManager backed by temp directories."""
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    return SessionManager(sessions_dir=sessions_dir, search_index=search_index)


class TestSessionModels:
    """Tests for Pydantic session data models."""

    def test_milestone_state_defaults(self) -> None:
        ms = MilestoneState(name="setup")
        assert ms.status == "pending"
        assert ms.progress_pct == 0.0
        assert ms.started_at is None
        assert ms.description == ""

    def test_session_state_new(self) -> None:
        session = SessionState.new(
            session_id="abc123",
            project_name="test-project",
            project_root="/tmp/test-project",
            session_name="session-1",
            tags=["physics", "cfd"],
        )
        assert session.schema_version == 1
        assert session.session_id == "abc123"
        assert session.status == "active"
        assert session.tags == ["physics", "cfd"]
        assert session.project_root == "/tmp/test-project"
        assert session.created_at is not None
        assert session.milestones == []


class TestSessionManager:
    """Tests for SessionManager CRUD and atomic writes."""

    def test_create_produces_json_file(self, session_manager: SessionManager, tmp_path: Path) -> None:
        session = session_manager.create("my-project", str(tmp_path / "my-project"), "run-1")
        path = tmp_path / "sessions" / f"{session.session_id}.json"
        assert path.exists()

        data = json.loads(path.read_text())
        assert data["schema_version"] == 1
        assert data["project_name"] == "my-project"
        assert data["project_root"] == str(tmp_path / "my-project")
        assert data["session_name"] == "run-1"
        assert data["status"] == "active"

    def test_save_atomic_write(self, session_manager: SessionManager, tmp_path: Path) -> None:
        session = session_manager.create("proj", str(tmp_path / "proj"), "sess")
        path = tmp_path / "sessions" / f"{session.session_id}.json"

        # Modify and save again
        session.research_findings.append("found something")
        session_manager.save(session)

        # File should be valid JSON after atomic write
        data = json.loads(path.read_text())
        assert "found something" in data["research_findings"]

    def test_load_round_trips(self, session_manager: SessionManager) -> None:
        original = session_manager.create(
            "round-trip-project",
            str(Path("/tmp/round-trip-project")),
            "round-trip-session",
            tags=["test"],
        )
        original.milestones.append(MilestoneState(name="milestone-1", status="complete", progress_pct=100.0))
        original.research_findings.append("important finding")
        session_manager.save(original)

        loaded = session_manager.load(original.session_id)
        assert loaded.session_id == original.session_id
        assert loaded.project_name == original.project_name
        assert loaded.tags == ["test"]
        assert len(loaded.milestones) == 1
        assert loaded.milestones[0].name == "milestone-1"
        assert loaded.research_findings == ["important finding"]

    def test_get_latest_session(self, session_manager: SessionManager) -> None:
        session_manager.create("proj", "/tmp/proj", "first")
        # Force a time gap so mtimes differ
        time.sleep(0.05)
        s2 = session_manager.create("proj", "/tmp/proj", "second")

        latest = session_manager.get_latest_session()
        assert latest is not None
        assert latest.session_id == s2.session_id

    def test_get_latest_session_prefers_exact_project_root(self, session_manager: SessionManager) -> None:
        session_manager.create("proj", "/tmp/other", "other")
        time.sleep(0.05)
        exact = session_manager.create("proj", "/tmp/current", "current")

        latest = session_manager.get_latest_session(project_name="proj", project_root="/tmp/current")
        assert latest is not None
        assert latest.session_id == exact.session_id

    def test_save_checkpoint_updates_timestamp(self, session_manager: SessionManager) -> None:
        session = session_manager.create("proj", "/tmp/proj", "ckpt-test")
        assert session.last_checkpoint_at is None

        session_manager.save_checkpoint("manual")
        assert session_manager.active_session is not None
        assert session_manager.active_session.last_checkpoint_at is not None

    def test_save_checkpoint_interrupted_sets_status(self, session_manager: SessionManager) -> None:
        session = session_manager.create("proj", "/tmp/proj", "interrupt-test")
        assert session.status == "active"

        session_manager.save_checkpoint("interrupted")
        assert session_manager.active_session is not None
        assert session_manager.active_session.status == "interrupted"

    def test_list_sessions(self, session_manager: SessionManager) -> None:
        session_manager.create("proj", "/tmp/proj", "s1")
        time.sleep(0.05)
        session_manager.create("proj", "/tmp/proj", "s2")

        sessions = session_manager.list_sessions()
        assert len(sessions) == 2
        # Most recent first
        assert sessions[0].session_name == "s2"

    def test_close_clears_active_session(self, session_manager: SessionManager) -> None:
        session_manager.create("proj", "/tmp/proj", "close-test")
        assert session_manager.active_session is not None

        session_manager.close()
        assert session_manager.active_session is None

    def test_load_nonexistent_raises(self, session_manager: SessionManager) -> None:
        with pytest.raises(FileNotFoundError):
            session_manager.load("does-not-exist")

    def test_atomic_write_produces_valid_json(self, session_manager: SessionManager, tmp_path: Path) -> None:
        session = session_manager.create("valid-json", str(tmp_path / "valid-json"), "test")
        path = tmp_path / "sessions" / f"{session.session_id}.json"

        # Should parse without error
        parsed = json.loads(path.read_text())
        assert parsed["session_id"] == session.session_id

    def test_create_without_persist_defers_initial_write(self, session_manager: SessionManager, tmp_path: Path) -> None:
        session = session_manager.create(
            "deferred-project",
            str(tmp_path / "deferred-project"),
            "deferred-session",
            persist=False,
        )

        path = tmp_path / "sessions" / f"{session.session_id}.json"
        assert not path.exists()
        assert session_manager.active_session is not None

    def test_finalize_marks_session_paused(self, session_manager: SessionManager, tmp_path: Path) -> None:
        session = session_manager.create("proj", str(tmp_path / "proj"), "finalize-test", persist=False)

        session_manager.finalize("paused")

        path = tmp_path / "sessions" / f"{session.session_id}.json"
        saved = SessionState.model_validate_json(path.read_text(encoding="utf-8"))
        assert saved.status == "paused"
        assert session_manager.active_session is None

    def test_load_corrupt_session_raises_value_error(self, session_manager: SessionManager, tmp_path: Path) -> None:
        path = tmp_path / "sessions" / "broken.json"
        path.write_text("{not-valid-json", encoding="utf-8")

        with pytest.raises(ValueError, match="corrupt"):
            session_manager.load("broken")

    def test_get_latest_session_scopes_to_project_and_skips_corrupt(self, session_manager: SessionManager, tmp_path: Path) -> None:
        stale = SessionState.new(
            session_id="stale001",
            project_name="project-alpha",
            project_root=str(tmp_path / "project-alpha"),
            session_name="older-valid",
        )
        other = SessionState.new(
            session_id="other001",
            project_name="project-beta",
            project_root=str(tmp_path / "project-beta"),
            session_name="newest-other-project",
        )

        stale_path = tmp_path / "sessions" / "stale001.json"
        other_path = tmp_path / "sessions" / "other001.json"
        broken_path = tmp_path / "sessions" / "broken001.json"
        stale_path.write_text(stale.model_dump_json(indent=2), encoding="utf-8")
        time.sleep(0.05)
        other_path.write_text(other.model_dump_json(indent=2), encoding="utf-8")
        time.sleep(0.05)
        broken_path.write_text("{not-valid-json", encoding="utf-8")

        latest = session_manager.get_latest_session("project-alpha", str(tmp_path / "project-alpha"))

        assert latest is not None
        assert latest.session_id == "stale001"

    def test_list_sessions_skips_corrupt_files_before_limit(self, session_manager: SessionManager, tmp_path: Path) -> None:
        valid = SessionState.new(
            session_id="valid001",
            project_name="physics",
            project_root=str(tmp_path / "physics"),
            session_name="valid-session",
        )

        broken_path = tmp_path / "sessions" / "broken001.json"
        valid_path = tmp_path / "sessions" / "valid001.json"
        valid_path.write_text(valid.model_dump_json(indent=2), encoding="utf-8")
        time.sleep(0.05)
        broken_path.write_text("{not-valid-json", encoding="utf-8")

        sessions = session_manager.list_sessions(limit=1)

        assert [session.session_id for session in sessions] == ["valid001"]


class TestSearchIndex:
    """Tests for SQLite FTS5 search index."""

    def test_init_creates_fts5_table(self, search_index: SearchIndex) -> None:
        assert search_index._conn is not None
        # Check that the session_search table exists
        row = search_index._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='session_search'"
        ).fetchone()
        assert row is not None

    def test_index_and_search_by_keyword(self, search_index: SearchIndex) -> None:
        session = SessionState.new(
            session_id="search001",
            project_name="quantum-gravity",
            project_root="/tmp/quantum-gravity",
            session_name="black-hole-sim",
            tags=["cosmology"],
        )
        session.research_findings.append("discovered graviton emission pattern")
        search_index.index_session(session)

        results = search_index.search("graviton")
        assert len(results) >= 1
        assert results[0]["session_id"] == "search001"

    def test_search_empty_for_no_match(self, search_index: SearchIndex) -> None:
        session = SessionState.new(
            session_id="nomatch001",
            project_name="optics",
            project_root="/tmp/optics",
            session_name="laser-test",
        )
        search_index.index_session(session)

        results = search_index.search("xyznonexistent")
        assert results == []

    def test_search_treats_raw_query_as_literal_terms(self, search_index: SearchIndex) -> None:
        session = SessionState.new(
            session_id="search002",
            project_name="quantum-gravity",
            project_root="/tmp/quantum-gravity",
            session_name="operator-test",
        )
        session.research_findings.append("discovered graviton emission pattern")
        search_index.index_session(session)

        results = search_index.search('graviton OR "pattern"')

        assert len(results) == 1
        assert results[0]["session_id"] == "search002"

    def test_search_empty_for_symbol_only_query(self, search_index: SearchIndex) -> None:
        session = SessionState.new(
            session_id="search003",
            project_name="symbols",
            project_root="/tmp/symbols",
            session_name="wildcards",
        )
        session.research_findings.append("100% stable _value output")
        search_index.index_session(session)

        assert search_index.search('"""') == []

    def test_search_structured_filters(self, search_index: SearchIndex) -> None:
        s1 = SessionState.new(
            session_id="struct001",
            project_name="thermo",
            project_root="/tmp/thermo",
            session_name="heat-transfer",
        )
        s2 = SessionState.new(
            session_id="struct002",
            project_name="optics",
            project_root="/tmp/optics",
            session_name="refraction",
        )
        s2.status = "completed"
        search_index.index_session(s1)
        search_index.index_session(s2)

        # Filter by project
        results = search_index.search_structured(project="thermo")
        assert len(results) == 1
        assert results[0]["session_id"] == "struct001"

        # Filter by status
        results = search_index.search_structured(status="completed")
        assert len(results) == 1
        assert results[0]["session_id"] == "struct002"

    def test_rebuild_index_from_json(self, search_index: SearchIndex, tmp_path: Path) -> None:
        sessions_dir = tmp_path / "rebuild_sessions"
        sessions_dir.mkdir()

        # Write two session JSON files to disk
        for i in range(2):
            session = SessionState.new(
                session_id=f"rebuild{i:03d}",
                project_name=f"project-{i}",
                project_root=f"/tmp/project-{i}",
                session_name=f"session-{i}",
            )
            (sessions_dir / f"rebuild{i:03d}.json").write_text(session.model_dump_json(indent=2))

        count = search_index.rebuild_index(sessions_dir)
        assert count == 2

        # Verify we can find them
        results = search_index.search_structured(project="project-0")
        assert len(results) == 1

    def test_rebuild_index_removes_deleted_sessions(self, search_index: SearchIndex, tmp_path: Path) -> None:
        sessions_dir = tmp_path / "rebuild_sessions"
        sessions_dir.mkdir()

        stale = SessionState.new(
            session_id="stale001",
            project_name="stale-project",
            project_root="/tmp/stale-project",
            session_name="old-session",
        )
        fresh = SessionState.new(
            session_id="fresh001",
            project_name="fresh-project",
            project_root="/tmp/fresh-project",
            session_name="new-session",
        )

        stale_path = sessions_dir / "stale001.json"
        fresh_path = sessions_dir / "fresh001.json"
        stale_path.write_text(stale.model_dump_json(indent=2), encoding="utf-8")
        fresh_path.write_text(fresh.model_dump_json(indent=2), encoding="utf-8")

        assert search_index.rebuild_index(sessions_dir) == 2
        stale_path.unlink()

        assert search_index.rebuild_index(sessions_dir) == 1
        assert search_index.search_structured(project="stale-project") == []
        assert len(search_index.search_structured(project="fresh-project")) == 1

    def test_reindex_updates_existing(self, search_index: SearchIndex) -> None:
        session = SessionState.new(
            session_id="reindex001",
            project_name="physics",
            project_root="/tmp/physics",
            session_name="sim-1",
        )
        search_index.index_session(session)

        # Update and re-index
        session.status = "completed"
        search_index.index_session(session)

        results = search_index.search_structured(project="physics", status="completed")
        assert len(results) == 1
