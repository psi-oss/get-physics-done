from __future__ import annotations

import json
from pathlib import Path

import pytest

from gpd.core.constants import HOME_DATA_DIR_NAME
from gpd.core.recent_projects import (
    RecentProjectsError,
    classify_recent_project_recovery,
    list_recent_projects,
    load_recent_projects_index,
    recent_projects_index_path,
    recent_projects_root,
    record_recent_project,
)


class TestRecentProjectsRootResolution:
    def test_prefers_explicit_data_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        explicit = tmp_path / "explicit-data"
        monkeypatch.setenv("GPD_DATA_DIR", str(tmp_path / "ignored"))
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")

        assert recent_projects_root(explicit) == explicit / "recent-projects"

    def test_uses_data_dir_env(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        data_dir = tmp_path / "data"
        monkeypatch.setenv("GPD_DATA_DIR", str(data_dir))
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")

        assert recent_projects_root() == data_dir / "recent-projects"

    def test_defaults_to_home_gpd_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        fake_home = tmp_path / "home"
        fake_home.mkdir()
        monkeypatch.delenv("GPD_DATA_DIR", raising=False)
        monkeypatch.setattr(Path, "home", lambda: fake_home)

        assert recent_projects_root() == fake_home / HOME_DATA_DIR_NAME / "recent-projects"


class TestRecentProjectsIndexPersistence:
    def test_save_and_load_round_trip(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GPD_DATA_DIR", raising=False)
        store_root = tmp_path / "cache"
        project_root = tmp_path / "project"
        project_root.mkdir()

        updated = record_recent_project(
            project_root,
            session_data={
                "last_date": "2026-03-26T12:00:00+00:00",
                "stopped_at": "Phase 03 Plan 2",
                "resume_file": "GPD/phases/03/.continue-here.md",
                "hostname": "builder-01",
                "platform": "Linux 6.1 x86_64",
            },
            store_root=store_root,
        )

        index_path = recent_projects_index_path(store_root)
        stored = json.loads(index_path.read_text(encoding="utf-8"))
        loaded = load_recent_projects_index(store_root)

        assert updated.project_root == project_root.resolve(strict=False).as_posix()
        assert set(stored) == {"rows"}
        assert stored["rows"][0]["schema_version"] == 1
        assert stored["rows"][0]["stopped_at"] == "Phase 03 Plan 2"
        assert "projects" not in stored
        assert "entries" not in stored
        assert "workspace_root" not in stored["rows"][0]
        assert "cwd" not in stored["rows"][0]
        assert "path" not in stored["rows"][0]
        assert "state" not in stored["rows"][0]
        assert "can_resume" not in stored["rows"][0]
        assert loaded.rows[0].resume_file == "GPD/phases/03/.continue-here.md"
        assert loaded.rows[0].resume_target_kind == "handoff"
        assert loaded.rows[0].resume_target_recorded_at == "2026-03-26T12:00:00+00:00"
        assert loaded.rows[0].last_session_at == "2026-03-26T12:00:00+00:00"
        assert loaded.rows[0].schema_version == 1

    def test_load_rejects_legacy_projects_container(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GPD_DATA_DIR", raising=False)
        store_root = tmp_path / "cache"
        project_root = tmp_path / "project"
        project_root.mkdir()

        index_path = recent_projects_index_path(store_root)
        index_path.parent.mkdir(parents=True, exist_ok=True)
        index_path.write_text(
            json.dumps(
                {
                    "projects": [
                        {
                            "project_root": project_root.resolve(strict=False).as_posix(),
                            "last_session_at": "2026-03-26T12:00:00+00:00",
                            "stopped_at": "Phase 3",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

        with pytest.raises(RecentProjectsError, match="recent-project index must contain only rows"):
            load_recent_projects_index(store_root)

    def test_load_rejects_alias_row_keys(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GPD_DATA_DIR", raising=False)
        store_root = tmp_path / "cache"
        project_root = tmp_path / "project"
        project_root.mkdir()

        index_path = recent_projects_index_path(store_root)
        index_path.parent.mkdir(parents=True, exist_ok=True)
        index_path.write_text(
            json.dumps(
                {
                    "rows": [
                        {
                            "project_root": project_root.resolve(strict=False).as_posix(),
                            "workspace_root": project_root.resolve(strict=False).as_posix(),
                            "last_session_at": "2026-03-26T12:00:00+00:00",
                            "resume_file": "GPD/phases/03/.continue-here.md",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

        with pytest.raises(RecentProjectsError, match="workspace_root"):
            load_recent_projects_index(store_root)

    def test_load_round_trip_keeps_canonical_rows_only(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("GPD_DATA_DIR", raising=False)
        store_root = tmp_path / "cache"
        project_root = tmp_path / "project"
        handoff_file = project_root / "GPD" / "phases" / "03" / ".continue-here.md"
        project_root.mkdir()
        handoff_file.parent.mkdir(parents=True, exist_ok=True)
        handoff_file.write_text("resume\n", encoding="utf-8")

        index_path = recent_projects_index_path(store_root)
        index_path.parent.mkdir(parents=True, exist_ok=True)
        index_path.write_text(
            json.dumps(
                {
                    "rows": [
                        {
                            "project_root": project_root.resolve(strict=False).as_posix(),
                            "last_session_at": "2026-03-26T12:00:00+00:00",
                            "last_seen_at": "2026-03-26T12:00:00+00:00",
                            "stopped_at": "Phase 3",
                            "resume_file": "GPD/phases/03/.continue-here.md",
                            "hostname": "builder-01",
                            "platform": "Linux 6.1 x86_64",
                            "source_kind": "segment.pause",
                            "source_session_id": "session-123",
                            "source_segment_id": "segment-7",
                            "source_transition_id": "transition-9",
                            "source_event_id": "event-11",
                            "source_recorded_at": "2026-03-26T12:34:56+00:00",
                            "recovery_phase": "Phase 03",
                            "recovery_plan": "Plan 2",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

        loaded = load_recent_projects_index(store_root)

        assert len(loaded.rows) == 1
        row = loaded.rows[0]
        assert row.project_root == project_root.resolve(strict=False).as_posix()
        assert row.schema_version == 1
        assert row.last_session_at == "2026-03-26T12:00:00+00:00"
        assert row.last_seen_at == "2026-03-26T12:00:00+00:00"
        assert row.source_kind == "segment.pause"
        assert row.source_session_id == "session-123"
        assert row.source_segment_id == "segment-7"
        assert row.source_transition_id == "transition-9"
        assert row.source_event_id == "event-11"
        assert row.source_recorded_at == "2026-03-26T12:34:56+00:00"
        assert row.recovery_phase == "Phase 03"
        assert row.recovery_plan == "Plan 2"
        assert row.resume_target_kind == "bounded_segment"
        assert row.resume_target_recorded_at == "2026-03-26T12:34:56+00:00"
        assert row.resume_file_available is True
        assert row.resumable is True
        assert "projects" not in json.loads(index_path.read_text(encoding="utf-8"))
        assert "entries" not in json.loads(index_path.read_text(encoding="utf-8"))

    def test_load_rejects_malformed_index(self, tmp_path: Path) -> None:
        store_root = tmp_path / "cache"
        index_path = recent_projects_index_path(store_root)
        index_path.parent.mkdir(parents=True, exist_ok=True)
        index_path.write_text("{ not-json", encoding="utf-8")

        with pytest.raises(RecentProjectsError, match="Malformed"):
            load_recent_projects_index(store_root)

    def test_save_then_reload_retains_single_project_row(self, tmp_path: Path) -> None:
        store_root = tmp_path / "cache"
        project_root = tmp_path / "project"
        project_root.mkdir()

        record_recent_project(
            project_root,
            session_data={"last_date": "2026-03-26T12:00:00+00:00", "stopped_at": "Phase 1"},
            store_root=store_root,
        )
        record_recent_project(
            project_root,
            session_data={
                "last_date": "2026-03-26T13:00:00+00:00",
                "stopped_at": "Phase 2",
                "resume_file": "—",
            },
            store_root=store_root,
        )

        loaded = load_recent_projects_index(store_root)

        assert len(loaded.rows) == 1
        assert loaded.rows[0].stopped_at == "Phase 2"
        assert loaded.rows[0].resume_file is None

    def test_record_preserves_existing_optional_fields_when_not_repeated(
        self, tmp_path: Path
    ) -> None:
        store_root = tmp_path / "cache"
        project_root = tmp_path / "project"
        project_root.mkdir()

        record_recent_project(
            project_root,
            session_data={
                "last_date": "2026-03-26T12:00:00+00:00",
                "stopped_at": "Phase 1",
                "resume_file": "resume.md",
                "hostname": "builder-01",
                "platform": "Linux 6.1 x86_64",
            },
            store_root=store_root,
        )
        record_recent_project(
            project_root,
            session_data={"last_date": "2026-03-26T13:00:00+00:00", "stopped_at": "Phase 2"},
            store_root=store_root,
        )

        loaded = load_recent_projects_index(store_root)

        assert len(loaded.rows) == 1
        assert loaded.rows[0].stopped_at == "Phase 2"
        assert loaded.rows[0].resume_file == "resume.md"
        assert loaded.rows[0].hostname == "builder-01"
        assert loaded.rows[0].platform == "Linux 6.1 x86_64"

    def test_record_preserves_explicit_recovery_classification_fields(self, tmp_path: Path) -> None:
        store_root = tmp_path / "cache"
        project_root = tmp_path / "project"
        project_root.mkdir()
        resume_file = project_root / "GPD" / "phases" / "03" / ".continue-here.md"
        resume_file.parent.mkdir(parents=True, exist_ok=True)
        resume_file.write_text("resume\n", encoding="utf-8")

        record_recent_project(
            project_root,
            session_data={
                "last_date": "2026-03-26T12:00:00+00:00",
                "resume_file": "GPD/phases/03/.continue-here.md",
                "resume_target_kind": "bounded_segment",
                "resume_target_recorded_at": "2026-03-26T12:01:00+00:00",
                "source_kind": "continuation.handoff",
                "source_session_id": "session-123",
                "source_segment_id": "segment-7",
                "source_transition_id": "transition-9",
                "source_recorded_at": "2026-03-26T12:01:00+00:00",
                "recovery_phase": "03",
                "recovery_plan": "02",
            },
            store_root=store_root,
        )

        loaded = load_recent_projects_index(store_root)

        assert len(loaded.rows) == 1
        row = loaded.rows[0]
        assert row.resume_target_kind == "bounded_segment"
        assert row.resume_target_recorded_at == "2026-03-26T12:01:00+00:00"
        assert row.source_kind == "continuation.handoff"
        assert row.source_session_id == "session-123"
        assert row.source_segment_id == "segment-7"
        assert row.source_transition_id == "transition-9"
        assert row.source_recorded_at == "2026-03-26T12:01:00+00:00"
        assert row.recovery_phase == "03"
        assert row.recovery_plan == "02"

    def test_classify_recent_project_recovery_prioritizes_bounded_segment_targets(self) -> None:
        bounded = classify_recent_project_recovery(
            {
                "available": True,
                "resume_file": "GPD/phases/03/.continue-here.md",
                "resume_target_kind": "bounded_segment",
                "source_kind": "continuation.handoff",
                "resume_file_available": True,
            }
        )
        handoff = classify_recent_project_recovery(
            {
                "available": True,
                "resume_file": "GPD/phases/03/.continue-here.md",
                "resume_target_kind": "handoff",
                "source_kind": "continuation.bounded_segment",
                "resume_file_available": True,
            }
        )

        assert bounded.target_priority > handoff.target_priority
        assert bounded.candidate_reason(recoverable=True) == "recent project cache entry with confirmed bounded segment resume target"
        assert handoff.candidate_reason(recoverable=True) == "recent project cache entry with projected continuity handoff"

    def test_classify_recent_project_recovery_does_not_promote_stale_source_ids_without_explicit_segment_kind(
        self,
    ) -> None:
        classification = classify_recent_project_recovery(
            {
                "available": True,
                "resume_file": "GPD/phases/03/.continue-here.md",
                "source_segment_id": "segment-7",
                "source_transition_id": "transition-9",
                "resume_file_available": True,
            }
        )

        assert classification.resume_target_kind == "handoff"
        assert classification.target_priority == 1
        assert classification.candidate_reason(recoverable=True) == "recent project cache entry with projected continuity handoff"


class TestRecentProjectsListing:
    def test_list_sorts_newest_first_and_preserves_missing_projects(self, tmp_path: Path) -> None:
        store_root = tmp_path / "cache"
        older = tmp_path / "older-project"
        newer = tmp_path / "newer-project"
        older.mkdir()
        newer.mkdir()

        record_recent_project(
            older,
            session_data={"last_date": "2026-03-26T10:00:00+00:00", "stopped_at": "Phase 1"},
            store_root=store_root,
        )
        record_recent_project(
            newer,
            session_data={"last_date": "2026-03-26T12:00:00+00:00", "stopped_at": "Phase 2"},
            store_root=store_root,
        )

        older.rmdir()

        rows = list_recent_projects(store_root)

        assert [row.project_root for row in rows] == [
            newer.resolve(strict=False).as_posix(),
            older.resolve(strict=False).as_posix(),
        ]
        assert rows[0].available is True
        assert rows[0].resumable is False
        assert rows[1].available is False
        assert rows[1].availability_reason == "project root missing"

    def test_list_marks_resumable_rows_when_resume_file_exists(self, tmp_path: Path) -> None:
        store_root = tmp_path / "cache"
        project_root = tmp_path / "project"
        project_root.mkdir()
        resume_file = project_root / "GPD" / "phases" / "03" / ".continue-here.md"
        resume_file.parent.mkdir(parents=True, exist_ok=True)
        resume_file.write_text("resume\n", encoding="utf-8")

        record_recent_project(
            project_root,
            session_data={
                "last_date": "2026-03-26T12:00:00+00:00",
                "stopped_at": "Phase 3",
                "resume_file": "GPD/phases/03/.continue-here.md",
            },
            store_root=store_root,
        )

        rows = list_recent_projects(store_root)

        assert len(rows) == 1
        assert rows[0].available is True
        assert rows[0].resume_file_available is True
        assert rows[0].resumable is True

    def test_list_keeps_missing_handoff_rows_but_marks_them_non_resumable(self, tmp_path: Path) -> None:
        store_root = tmp_path / "cache"
        project_root = tmp_path / "project"
        project_root.mkdir()

        record_recent_project(
            project_root,
            session_data={
                "last_date": "2026-03-26T12:00:00+00:00",
                "stopped_at": "Phase 3",
                "resume_file": "GPD/phases/03/.continue-here.md",
            },
            store_root=store_root,
        )

        rows = list_recent_projects(store_root)

        assert len(rows) == 1
        assert rows[0].available is True
        assert rows[0].resume_file == "GPD/phases/03/.continue-here.md"
        assert rows[0].resume_file_available is False
        assert rows[0].resume_file_reason == "resume file missing"
        assert rows[0].resumable is False
