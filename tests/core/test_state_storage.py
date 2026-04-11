from __future__ import annotations

import json
from pathlib import Path

from gpd.core.constants import STATE_WRITE_INTENT_FILENAME
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
        planning = tmp_path / "GPD"
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

    def test_sync_core_uses_backup_when_primary_json_is_corrupt(
        self, tmp_path: Path, state_project_factory
    ) -> None:
        cwd = state_project_factory(tmp_path)
        planning = cwd / "GPD"

        backup = json.loads((planning / "state.json").read_text(encoding="utf-8"))
        backup["from_backup"] = True
        (planning / "state.json.bak").write_text(json.dumps(backup), encoding="utf-8")
        (planning / "state.json").write_text("{corrupt!", encoding="utf-8")

        result = sync_state_json_core(cwd, (planning / "STATE.md").read_text(encoding="utf-8"))

        assert result["from_backup"] is True


class TestSaveStateJsonLocked:
    def test_save_writes_json_markdown_and_backup(self, tmp_path: Path) -> None:
        planning = tmp_path / "GPD"
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

    def test_save_does_not_leave_stale_backup_before_intent_cleanup(self, tmp_path: Path, monkeypatch) -> None:
        planning = tmp_path / "GPD"
        planning.mkdir()
        (planning / "phases").mkdir()

        old_state = default_state_dict()
        old_state["position"]["current_phase"] = "01"
        new_state = default_state_dict()
        new_state["position"]["current_phase"] = "02"

        json_path = planning / "state.json"
        with file_lock(json_path):
            save_state_json_locked(tmp_path, old_state)

        import gpd.core.state as state_module

        original_unlink = Path.unlink

        def fail_intent_unlink(path: Path, *args, **kwargs):
            if path.name == STATE_WRITE_INTENT_FILENAME:
                raise OSError("simulated intent cleanup failure")
            return original_unlink(path, *args, **kwargs)

        monkeypatch.setattr(state_module.Path, "unlink", fail_intent_unlink)
        with file_lock(json_path):
            save_state_json_locked(tmp_path, new_state)

        stored = json.loads(json_path.read_text(encoding="utf-8"))
        backup = json.loads((planning / "state.json.bak").read_text(encoding="utf-8"))

        assert stored["position"]["current_phase"] == "02"
        assert backup["position"]["current_phase"] == "02"

    def test_recover_intent_ignores_temp_paths_outside_same_gpd_dir(self, tmp_path: Path) -> None:
        planning = tmp_path / "GPD"
        planning.mkdir()
        (planning / "phases").mkdir()

        state = default_state_dict()
        state["position"]["current_phase"] = "01"
        json_path = planning / "state.json"
        with file_lock(json_path):
            save_state_json_locked(tmp_path, state)

        outside_json = tmp_path / "state.json.tmp.outside"
        outside_md = tmp_path / "STATE.md.tmp.outside"
        outside_json.write_text(json.dumps({"outside": True}) + "\n", encoding="utf-8")
        outside_md.write_text("# Outside\n", encoding="utf-8")
        (planning / STATE_WRITE_INTENT_FILENAME).write_text(f"{outside_json}\n{outside_md}\n", encoding="utf-8")

        with file_lock(json_path):
            save_state_json_locked(tmp_path, state)

        stored = json.loads(json_path.read_text(encoding="utf-8"))

        assert stored["position"]["current_phase"] == "01"
        assert outside_json.exists()
        assert outside_md.exists()
        assert not (planning / STATE_WRITE_INTENT_FILENAME).exists()


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

        archive = (cwd / "GPD" / "STATE-ARCHIVE.md").read_text(encoding="utf-8")
        markdown = (cwd / "GPD" / "STATE.md").read_text(encoding="utf-8")

        assert result.compacted is True
        assert "Old decision" in archive
        assert "Current phase decision" in markdown
