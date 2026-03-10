"""Focused regression tests for local gpd.core.observability behavior."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path


def _bootstrap_project(tmp_path: Path) -> Path:
    planning = tmp_path / ".gpd"
    planning.mkdir()
    return tmp_path


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _event_name(event: dict[str, object]) -> str | None:
    for key in ("name", "span_name", "event", "event_name"):
        value = event.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def test_gpd_span_writes_local_observability_artifacts(tmp_path: Path, monkeypatch) -> None:
    project = _bootstrap_project(tmp_path)
    monkeypatch.chdir(project)

    from gpd.core.observability import gpd_span

    with gpd_span("test.span", domain="physics"):
        pass

    observability_dir = project / ".gpd" / "observability"
    events_path = observability_dir / "events.jsonl"
    current_session_path = observability_dir / "current-session.json"
    sessions_dir = observability_dir / "sessions"

    assert events_path.exists()
    assert current_session_path.exists()
    assert sessions_dir.is_dir()

    current_session = json.loads(current_session_path.read_text(encoding="utf-8"))
    session_files = sorted(sessions_dir.glob("*.jsonl"))
    assert len(session_files) == 1

    session_events = _read_jsonl(session_files[0])
    assert session_events
    assert any(_event_name(event) == "test.span" for event in session_events)
    assert any(event.get("session_id") == current_session.get("session_id") for event in session_events)


def test_instrument_gpd_function_sync_emits_local_events(tmp_path: Path, monkeypatch) -> None:
    project = _bootstrap_project(tmp_path)
    monkeypatch.chdir(project)

    from gpd.core.observability import instrument_gpd_function

    @instrument_gpd_function("test.func")
    def my_func(x: int) -> int:
        return x * 2

    assert my_func(5) == 10

    events = _read_jsonl(project / ".gpd" / "observability" / "events.jsonl")
    assert any(_event_name(event) == "test.func" for event in events)


def test_instrument_gpd_function_async_emits_local_events(tmp_path: Path, monkeypatch) -> None:
    project = _bootstrap_project(tmp_path)
    monkeypatch.chdir(project)

    from gpd.core.observability import instrument_gpd_function

    @instrument_gpd_function("test.async_func")
    async def my_async_func(x: int) -> int:
        return x + 1

    result = asyncio.run(my_async_func(3))
    assert result == 4

    events = _read_jsonl(project / ".gpd" / "observability" / "events.jsonl")
    assert any(_event_name(event) == "test.async_func" for event in events)
