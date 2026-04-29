from __future__ import annotations

import copy
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

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "stage0"


def _load_contract_fixture() -> dict:
    return json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))


def _write_recoverable_state_intent(cwd: Path, state_obj: dict) -> None:
    planning = cwd / "GPD"
    json_tmp = planning / ".state-json-tmp"
    md_tmp = planning / ".state-md-tmp"
    json_tmp.write_text(json.dumps(state_obj, indent=2) + "\n", encoding="utf-8")
    md_tmp.write_text("# Recovered State\n", encoding="utf-8")
    (planning / ".state-write-intent").write_text(f"{json_tmp}\n{md_tmp}\n", encoding="utf-8")


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

    def test_sync_core_uses_backup_when_primary_json_is_corrupt(self, tmp_path: Path, state_project_factory) -> None:
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


class TestStateProjectContractStorage:
    def test_set_project_contract_noop_check_happens_after_intent_recovery(
        self, tmp_path: Path, state_project_factory
    ) -> None:
        from gpd.core.state import state_set_project_contract

        cwd = state_project_factory(tmp_path)
        requested = _load_contract_fixture()
        initial_result = state_set_project_contract(cwd, requested)
        assert initial_result.updated is True

        planning = cwd / "GPD"
        persisted_state = json.loads((planning / "state.json").read_text(encoding="utf-8"))
        requested_contract = copy.deepcopy(persisted_state["project_contract"])
        stale_state = copy.deepcopy(persisted_state)
        stale_state["project_contract"]["scope"]["question"] = "Stale interrupted contract"
        _write_recoverable_state_intent(cwd, stale_state)

        result = state_set_project_contract(cwd, requested_contract)

        stored = json.loads((planning / "state.json").read_text(encoding="utf-8"))
        assert result.updated is True
        assert result.unchanged is False
        assert stored["project_contract"] == requested_contract
        assert not (planning / ".state-write-intent").exists()


class TestStateValidateStorage:
    def test_state_validate_is_read_only_by_default(self, tmp_path: Path, state_project_factory) -> None:
        from gpd.core.state import state_validate

        cwd = state_project_factory(tmp_path)
        planning = cwd / "GPD"
        before_state_json = (planning / "state.json").read_text(encoding="utf-8")

        recovered_state = json.loads(before_state_json)
        recovered_state["position"]["current_phase"] = "05"
        _write_recoverable_state_intent(cwd, recovered_state)
        before_intent = (planning / ".state-write-intent").read_text(encoding="utf-8")
        before_json_tmp = (planning / ".state-json-tmp").read_text(encoding="utf-8")
        before_md_tmp = (planning / ".state-md-tmp").read_text(encoding="utf-8")

        result = state_validate(cwd)

        assert result.state_source == "state.json"
        assert (planning / "state.json").read_text(encoding="utf-8") == before_state_json
        assert (planning / ".state-write-intent").read_text(encoding="utf-8") == before_intent
        assert (planning / ".state-json-tmp").read_text(encoding="utf-8") == before_json_tmp
        assert (planning / ".state-md-tmp").read_text(encoding="utf-8") == before_md_tmp


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
