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


def test_show_events_falls_back_to_session_streams_when_global_stream_missing(tmp_path: Path) -> None:
    project = _bootstrap_project(tmp_path)
    sessions_dir = project / ".gpd" / "observability" / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    (sessions_dir / "session-a.jsonl").write_text(
        json.dumps(
            {
                "timestamp": "2026-03-10T00:00:00+00:00",
                "session_id": "session-a",
                "category": "cli",
                "name": "command",
                "action": "finish",
                "status": "ok",
                "command": "timestamp",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    from gpd.core.observability import show_events

    result = show_events(project, category="cli", command="timestamp")

    assert result.count == 1
    assert result.events[0]["session_id"] == "session-a"


def test_show_events_falls_back_when_global_stream_has_no_matching_records(tmp_path: Path) -> None:
    """When global events file exists, show_events uses it as authoritative source.

    It should NOT fall back to session events just because the filter yields no
    matches from the global file.  This prevents non-deterministic data source
    switching.
    """
    project = _bootstrap_project(tmp_path)
    obs_dir = project / ".gpd" / "observability"
    obs_dir.mkdir(parents=True, exist_ok=True)
    (obs_dir / "events.jsonl").write_text(
        json.dumps(
            {
                "timestamp": "2026-03-10T00:00:00+00:00",
                "session_id": "cli-observe",
                "category": "cli",
                "name": "command",
                "action": "start",
                "status": "active",
                "command": "observe show",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    sessions_dir = obs_dir / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    (sessions_dir / "session-a.jsonl").write_text(
        json.dumps(
            {
                "timestamp": "2026-03-10T00:00:01+00:00",
                "session_id": "session-a",
                "category": "cli",
                "name": "command",
                "action": "finish",
                "status": "ok",
                "command": "timestamp",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    from gpd.core.observability import show_events

    result = show_events(project, category="cli", command="timestamp")

    # Global file exists but has no events matching command="timestamp".
    # The fix ensures we do NOT fall back to session events in this case.
    assert result.count == 0


def test_prefixed_attrs_renames_cwd_to_gpd_cwd():
    """Verify _prefixed_attrs renames 'cwd' -> 'gpd.cwd', so only gpd.cwd exists."""
    from gpd.core.observability import _prefixed_attrs

    result = _prefixed_attrs({"cwd": "/some/path"})
    assert "gpd.cwd" in result
    assert "cwd" not in result
    assert result["gpd.cwd"] == "/some/path"


def test_gpd_span_cwd_uses_only_gpd_cwd_key(tmp_path: Path, monkeypatch) -> None:
    """After removing the dead 'cwd' fallback branch, gpd_span must still
    correctly resolve cwd when the caller passes 'cwd' (without prefix).

    _prefixed_attrs renames 'cwd' to 'gpd.cwd', so only the gpd.cwd lookup
    is needed in gpd_span.
    """
    project = _bootstrap_project(tmp_path)
    monkeypatch.chdir(project)

    from gpd.core.observability import gpd_span

    # Passing bare "cwd" — _prefixed_attrs will rename it to "gpd.cwd"
    with gpd_span("test.cwd_resolution", cwd=str(project)):
        pass

    events_path = project / ".gpd" / "observability" / "events.jsonl"
    assert events_path.exists()
    events = _read_jsonl(events_path)
    assert any(_event_name(e) == "test.cwd_resolution" for e in events)


def test_gpd_span_cwd_with_prefixed_key(tmp_path: Path, monkeypatch) -> None:
    """gpd_span should work when caller passes 'gpd.cwd' directly."""
    project = _bootstrap_project(tmp_path)
    monkeypatch.chdir(project)

    from gpd.core.observability import gpd_span

    with gpd_span("test.prefixed_cwd", **{"gpd.cwd": str(project)}):
        pass

    events_path = project / ".gpd" / "observability" / "events.jsonl"
    assert events_path.exists()
    events = _read_jsonl(events_path)
    assert any(_event_name(e) == "test.prefixed_cwd" for e in events)
