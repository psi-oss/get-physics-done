from __future__ import annotations

import json
from pathlib import Path

from gpd.core.state import (
    default_state_dict,
    generate_state_markdown,
    save_state_json_locked,
    state_compact,
    sync_state_json,
    sync_state_json_core,
)
from gpd.core.utils import file_lock


class TestSyncStateJson:
    def test_sync_creates_state_json_from_markdown(self, tmp_path: Path) -> None:
        planning = tmp_path / ".gpd"
        planning.mkdir()

        state = default_state_dict()
        state["position"]["current_phase"] = "01"
        state["position"]["status"] = "Planning"
        markdown = generate_state_markdown(state)
        (planning / "STATE.md").write_text(markdown, encoding="utf-8")

        result = sync_state_json(tmp_path, markdown)

        stored = json.loads((planning / "state.json").read_text(encoding="utf-8"))
        assert isinstance(result, dict)
        assert isinstance(stored, dict)
        assert stored["position"]["current_phase"] == "01"

    def test_sync_preserves_json_only_fields(self, tmp_path: Path, state_project_factory) -> None:
        cwd = state_project_factory(tmp_path)
        json_path = cwd / ".gpd" / "state.json"

        existing = json.loads(json_path.read_text(encoding="utf-8"))
        existing["custom_field"] = "preserved"
        json_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")

        markdown = (cwd / ".gpd" / "STATE.md").read_text(encoding="utf-8")
        result = sync_state_json(cwd, markdown)

        assert result["custom_field"] == "preserved"

    def test_sync_core_creates_backup(self, tmp_path: Path, state_project_factory) -> None:
        cwd = state_project_factory(tmp_path)
        markdown = (cwd / ".gpd" / "STATE.md").read_text(encoding="utf-8")

        sync_state_json_core(cwd, markdown)

        assert (cwd / ".gpd" / "state.json.bak").exists()

    def test_sync_core_recovers_from_corrupt_json(self, tmp_path: Path, state_project_factory) -> None:
        cwd = state_project_factory(tmp_path)
        planning = cwd / ".gpd"
        (planning / "state.json").write_text("NOT VALID JSON {{{", encoding="utf-8")

        backup_path = planning / "state.json.bak"
        if backup_path.exists():
            backup_path.unlink()

        result = sync_state_json_core(cwd, (planning / "STATE.md").read_text(encoding="utf-8"))
        stored = json.loads((planning / "state.json").read_text(encoding="utf-8"))

        assert isinstance(result, dict)
        assert isinstance(stored, dict)

    def test_sync_core_uses_backup_when_primary_json_is_corrupt(
        self, tmp_path: Path, state_project_factory
    ) -> None:
        cwd = state_project_factory(tmp_path)
        planning = cwd / ".gpd"

        backup = json.loads((planning / "state.json").read_text(encoding="utf-8"))
        backup["from_backup"] = True
        (planning / "state.json.bak").write_text(json.dumps(backup), encoding="utf-8")
        (planning / "state.json").write_text("{corrupt!", encoding="utf-8")

        result = sync_state_json_core(cwd, (planning / "STATE.md").read_text(encoding="utf-8"))

        assert result["from_backup"] is True

    def test_sync_updates_position_from_markdown(
        self, tmp_path: Path, state_project_factory
    ) -> None:
        cwd = state_project_factory(tmp_path, status="Planning")

        result = sync_state_json(cwd, (cwd / ".gpd" / "STATE.md").read_text(encoding="utf-8"))

        assert result["position"]["status"] == "Planning"


class TestSaveStateJsonLocked:
    def test_save_writes_json_markdown_and_backup(self, tmp_path: Path) -> None:
        planning = tmp_path / ".gpd"
        planning.mkdir()
        (planning / "phases").mkdir()

        state = default_state_dict()
        state["position"]["current_phase"] = "01"
        state["position"]["status"] = "Planning"

        json_path = planning / "state.json"
        with file_lock(json_path):
            save_state_json_locked(tmp_path, state)

        stored = json.loads(json_path.read_text(encoding="utf-8"))
        markdown = (planning / "STATE.md").read_text(encoding="utf-8")

        assert stored["position"]["current_phase"] == "01"
        assert "Planning" in markdown
        assert (planning / "state.json.bak").exists()

    def test_save_overwrites_existing_content(self, tmp_path: Path, state_project_factory) -> None:
        cwd = state_project_factory(tmp_path)
        json_path = cwd / ".gpd" / "state.json"

        state = default_state_dict()
        state["position"]["current_phase"] = "99"
        state["position"]["status"] = "Complete"

        with file_lock(json_path):
            save_state_json_locked(cwd, state)

        stored = json.loads(json_path.read_text(encoding="utf-8"))
        assert stored["position"]["current_phase"] == "99"
        assert stored["position"]["status"] == "Complete"

    def test_save_removes_intent_marker_after_success(self, tmp_path: Path) -> None:
        planning = tmp_path / ".gpd"
        planning.mkdir()

        json_path = planning / "state.json"
        with file_lock(json_path):
            save_state_json_locked(tmp_path, default_state_dict())

        assert not (planning / ".state-write-intent").exists()


class TestStateCompact:
    def test_compact_is_noop_within_budget(self, tmp_path: Path, state_project_factory) -> None:
        cwd = state_project_factory(tmp_path)

        result = state_compact(cwd)

        assert result.compacted is False
        assert result.reason == "within_budget"

    def test_compact_missing_state_file(self, tmp_path: Path) -> None:
        result = state_compact(tmp_path)

        assert result.compacted is False
        assert "not found" in (result.error or "").lower()

    def test_compact_archives_old_decisions_and_keeps_recent_context(
        self, tmp_path: Path, large_state_project_factory
    ) -> None:
        cwd = large_state_project_factory(tmp_path, n_old_decisions=50, extra_lines=80)

        result = state_compact(cwd)

        archive = (cwd / ".gpd" / "STATE-ARCHIVE.md").read_text(encoding="utf-8")
        markdown = (cwd / ".gpd" / "STATE.md").read_text(encoding="utf-8")

        assert result.compacted is True
        assert "Old decision" in archive
        assert "Current phase decision" in markdown

    def test_compact_archives_resolved_blockers(self, tmp_path: Path, large_state_project_factory) -> None:
        cwd = large_state_project_factory(
            tmp_path,
            n_old_decisions=40,
            n_resolved_blockers=20,
            extra_lines=80,
        )

        result = state_compact(cwd)

        archive = (cwd / ".gpd" / "STATE-ARCHIVE.md").read_text(encoding="utf-8")
        markdown = (cwd / ".gpd" / "STATE.md").read_text(encoding="utf-8")

        assert result.compacted is True
        assert "Resolved" in archive or "Old decision" in archive
        assert "Active blocker still open" in markdown

    def test_compact_appends_to_existing_archive(self, tmp_path: Path, large_state_project_factory) -> None:
        cwd = large_state_project_factory(tmp_path, n_old_decisions=50, extra_lines=80)
        archive_path = cwd / ".gpd" / "STATE-ARCHIVE.md"
        archive_path.write_text("# STATE Archive\n\nPrevious entries.\n\n", encoding="utf-8")

        result = state_compact(cwd)

        assert result.compacted is True
        assert "Previous entries." in archive_path.read_text(encoding="utf-8")

    def test_compact_leaves_valid_state_json(self, tmp_path: Path, large_state_project_factory) -> None:
        cwd = large_state_project_factory(tmp_path, n_old_decisions=50, extra_lines=80)

        state_compact(cwd)

        stored = json.loads((cwd / ".gpd" / "state.json").read_text(encoding="utf-8"))
        assert "position" in stored or "project_reference" in stored

    def test_compact_reports_line_counts(self, tmp_path: Path, large_state_project_factory) -> None:
        cwd = large_state_project_factory(tmp_path, n_old_decisions=50, extra_lines=100)

        result = state_compact(cwd)

        if result.compacted:
            assert result.original_lines > 0
            assert result.new_lines > 0
            assert result.new_lines < result.original_lines
            assert result.archived_lines == result.original_lines - result.new_lines
