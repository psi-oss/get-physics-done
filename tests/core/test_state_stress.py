"""Lean stress coverage for state parsing and loading edge cases."""

from __future__ import annotations

import json
import threading
from contextlib import contextmanager
from itertools import count
from pathlib import Path

from gpd.core import state as state_module
from gpd.core.state import (
    default_state_dict,
    ensure_state_schema,
    generate_state_markdown,
    load_state_json,
    parse_state_md,
    save_state_json,
    state_snapshot,
)


def _bootstrap_project(tmp_path: Path, state_dict: dict | None = None) -> Path:
    """Create a minimal GPD project with STATE.md + state.json."""
    planning = tmp_path / "GPD"
    planning.mkdir(exist_ok=True)
    (planning / "phases").mkdir(exist_ok=True)
    (planning / "PROJECT.md").write_text("# Project\nTest.\n", encoding="utf-8")
    (planning / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")

    state = state_dict or default_state_dict()
    position = state.setdefault("position", {})
    position.setdefault("current_phase", "01")
    position.setdefault("status", "Executing")
    position.setdefault("current_plan", "1")
    position.setdefault("total_plans_in_phase", 3)
    position.setdefault("progress_percent", 33)

    (planning / "STATE.md").write_text(generate_state_markdown(state), encoding="utf-8")
    (planning / "state.json").write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    return tmp_path


def test_parse_empty_state_md() -> None:
    parsed = parse_state_md("# State\n")
    assert isinstance(parsed, dict)
    assert parsed["decisions"] == []
    assert parsed["blockers"] == []
    assert parsed["position"]["current_phase"] is None
    assert parsed["position"]["status"] is None


def test_state_snapshot_with_minimal_state_md(tmp_path: Path) -> None:
    planning = tmp_path / "GPD"
    planning.mkdir()
    (planning / "phases").mkdir()
    (planning / "STATE.md").write_text("# State\n", encoding="utf-8")

    snap = state_snapshot(tmp_path)

    assert snap.current_phase is None
    assert snap.status is None


def test_parse_frontmatter_only() -> None:
    content = "---\ntitle: Research\n---\n"
    parsed = parse_state_md(content)
    assert isinstance(parsed, dict)
    assert parsed["decisions"] == []
    assert parsed["blockers"] == []
    assert parsed["position"]["current_phase"] is None


def test_load_all_null_state_json(tmp_path: Path) -> None:
    planning = tmp_path / "GPD"
    planning.mkdir()
    (planning / "phases").mkdir()
    null_state = dict.fromkeys(default_state_dict())
    (planning / "state.json").write_text(json.dumps(null_state), encoding="utf-8")
    (planning / "STATE.md").write_text("# State\n", encoding="utf-8")

    loaded = load_state_json(tmp_path)

    assert loaded is not None
    assert "position" in loaded
    assert "session" in loaded


def test_extra_fields_survive_state_schema_normalization() -> None:
    state = default_state_dict()
    state["position"]["current_phase"] = "01"
    state["position"]["status"] = "Executing"
    state["_experiment_id"] = "EXP-42"
    state["custom_notes"] = "Important note"

    result = ensure_state_schema(state)

    assert result["_experiment_id"] == "EXP-42"
    assert result["custom_notes"] == "Important note"


def test_missing_sections_get_default_shape() -> None:
    raw = {"decisions": [{"phase": "1", "summary": "Use dim-reg"}], "blockers": []}
    result = ensure_state_schema(raw)
    assert "position" in result
    assert result["position"]["current_phase"] is None
    assert result["position"]["progress_percent"] == 0

    raw = {"position": {"current_phase": "05", "status": "Executing"}}
    result = ensure_state_schema(raw)
    assert "session" in result
    assert isinstance(result["session"], dict)


class TestConcurrentAccess:
    def test_concurrent_save_does_not_corrupt(self, tmp_path: Path) -> None:
        """Concurrent writes may queue or time out, but they must never corrupt state.json."""
        cwd = _bootstrap_project(tmp_path)
        errors: list[str] = []

        def _writer(thread_id: int) -> None:
            try:
                state = default_state_dict()
                state["position"]["current_phase"] = f"{thread_id:02d}"
                state["position"]["status"] = "Executing"
                state["position"]["current_plan"] = "1"
                state["position"]["total_plans_in_phase"] = 3
                save_state_json(cwd, state)
            except Exception as exc:
                errors.append(f"Thread {thread_id}: {exc}")

        threads = [threading.Thread(target=_writer, args=(i,)) for i in range(5)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)

        non_timeout_errors = [error for error in errors if "Timeout acquiring lock" not in error]
        assert not non_timeout_errors, f"Concurrent writes produced unexpected errors: {non_timeout_errors}"

        loaded = json.loads((cwd / "GPD" / "state.json").read_text(encoding="utf-8"))
        assert loaded["position"]["current_phase"] in {f"{index:02d}" for index in range(5)}
        assert "position" in loaded

    def test_concurrent_save_waits_out_realistic_lock_contention(self, tmp_path: Path, monkeypatch) -> None:
        """A second state writer should wait through a slow in-flight write instead of timing out."""
        cwd = _bootstrap_project(tmp_path)
        original_save_locked = state_module.save_state_json_locked
        original_state_lock = state_module._state_lock
        first_writer_entered = threading.Event()
        release_first_writer = threading.Event()
        second_lock_attempted = threading.Event()
        second_lock_acquired = threading.Event()
        lock_counter = count()
        errors: list[str] = []

        @contextmanager
        def instrumented_state_lock(cwd_arg: Path, timeout: float = state_module._STATE_LOCK_TIMEOUT_SECONDS):
            attempt = next(lock_counter)
            if attempt == 1:
                second_lock_attempted.set()
            with original_state_lock(cwd_arg, timeout=timeout):
                if attempt == 1:
                    second_lock_acquired.set()
                yield

        def slow_save_locked(
            cwd_arg: Path,
            state_obj: dict,
            *,
            preserve_visible_project_contract: bool = True,
        ) -> None:
            if not first_writer_entered.is_set():
                first_writer_entered.set()
                assert release_first_writer.wait(timeout=10), "first writer never released"
            original_save_locked(
                cwd_arg,
                state_obj,
                preserve_visible_project_contract=preserve_visible_project_contract,
            )

        def _writer(phase: str) -> None:
            try:
                state = default_state_dict()
                state["position"]["current_phase"] = phase
                state["position"]["status"] = "Executing"
                state["position"]["current_plan"] = "1"
                state["position"]["total_plans_in_phase"] = 3
                save_state_json(cwd, state)
            except Exception as exc:
                errors.append(f"Phase {phase}: {exc}")

        monkeypatch.setattr(state_module, "save_state_json_locked", slow_save_locked)
        monkeypatch.setattr(state_module, "_state_lock", instrumented_state_lock)

        first = threading.Thread(target=_writer, args=("01",))
        second = threading.Thread(target=_writer, args=("02",))
        first.start()
        assert first_writer_entered.wait(timeout=2), "first writer never acquired the state lock"
        second.start()
        assert second_lock_attempted.wait(timeout=2), "second writer never attempted the state lock"
        assert not second_lock_acquired.is_set(), "second writer should block on the state lock"
        release_first_writer.set()
        assert second_lock_acquired.wait(timeout=5), "second writer never acquired the state lock"
        first.join(timeout=10)
        second.join(timeout=10)

        assert not errors, f"Contended writes should queue instead of timing out: {errors}"
