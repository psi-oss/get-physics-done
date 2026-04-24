"""Tests for the `gpd progress --watch` polling heartbeat loop."""

from __future__ import annotations

import datetime as _dt
import io
import json
from pathlib import Path

from rich.console import Console
from typer.testing import CliRunner

from gpd import cli as cli_module
from gpd.cli import app

runner = CliRunner()


def _bootstrap_project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    (project / "GPD").mkdir(parents=True)
    return project


def _write_current_execution(project: Path, **fields) -> Path:
    observability_dir = project / "GPD" / "observability"
    observability_dir.mkdir(parents=True, exist_ok=True)
    path = observability_dir / "current-execution.json"
    payload = {
        "session_id": fields.get("session_id", "sess-p6"),
        "phase": fields.get("phase", "01"),
        "plan": fields.get("plan", "a"),
        "segment_status": fields.get("segment_status", "active"),
        "current_task": fields.get("current_task", "task-1"),
        "updated_at": fields.get(
            "updated_at",
            _dt.datetime.now(tz=_dt.UTC).isoformat(),
        ),
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _parse_json_lines(stdout: str) -> list[dict]:
    lines = []
    for raw in stdout.splitlines():
        stripped = raw.strip()
        if not stripped:
            continue
        lines.append(json.loads(stripped))
    return lines


def test_progress_watch_redraws_on_mtime_change(tmp_path: Path, monkeypatch) -> None:
    project = _bootstrap_project(tmp_path)
    _write_current_execution(project, current_task="task-1")

    monkeypatch.setattr(cli_module, "_stdout_is_interactive", lambda: False)

    calls = {"n": 0}

    def _fake_sleep(_interval: float) -> None:
        calls["n"] += 1
        if calls["n"] == 2:
            # Rewriting current-execution.json naturally bumps mtime via the
            # write, *and* produces a distinguishable payload — so the redraw
            # test asserts frame-content distinctness, not merely frame count.
            _write_current_execution(project, current_task="task-2")
        if calls["n"] >= 3:
            raise KeyboardInterrupt

    monkeypatch.setattr(cli_module, "_progress_watch_sleep", _fake_sleep)

    result = runner.invoke(
        app,
        ["--cwd", str(project), "progress", "json", "--watch", "--interval", "0.1"],
    )

    assert result.exit_code == 0, result.stdout + (result.stderr or "")
    emitted = _parse_json_lines(result.stdout)
    assert len(emitted) >= 2, (
        f"expected >=2 JSON frames (one initial + one after rewrite); "
        f"got {len(emitted)}: {result.stdout!r}"
    )
    assert emitted[0]["live_execution"]["current_task"] == "task-1"
    assert emitted[-1]["live_execution"]["current_task"] == "task-2"
    # Proves frames are distinct content-wise, not just counted.
    assert emitted[0] != emitted[-1]
    assert calls["n"] >= 2


def test_progress_watch_honors_interval_without_mtime_change(
    tmp_path: Path, monkeypatch
) -> None:
    project = _bootstrap_project(tmp_path)
    _write_current_execution(project)

    monkeypatch.setattr(cli_module, "_stdout_is_interactive", lambda: False)

    calls = {"n": 0}

    def _fake_sleep(_interval: float) -> None:
        calls["n"] += 1
        if calls["n"] >= 2:
            raise KeyboardInterrupt

    monkeypatch.setattr(cli_module, "_progress_watch_sleep", _fake_sleep)

    result = runner.invoke(
        app,
        ["--cwd", str(project), "progress", "json", "--watch", "--interval", "0.1"],
    )

    assert result.exit_code == 0, result.stdout + (result.stderr or "")
    emitted = _parse_json_lines(result.stdout)
    assert len(emitted) >= 1, (
        f"first tick should always render; got {len(emitted)} frames: {result.stdout!r}"
    )


def test_progress_watch_exit_on_idle_flag(tmp_path: Path, monkeypatch) -> None:
    project = _bootstrap_project(tmp_path)
    # Intentionally no current-execution.json: the project is idle.

    monkeypatch.setattr(cli_module, "_stdout_is_interactive", lambda: False)

    # Force the idle branch: we are testing the loop's --exit-on-idle wiring,
    # not the internal idle-detection heuristic. ``progress_render`` may return
    # a non-None live_execution shell for empty projects, so we override
    # ``_is_idle`` to reflect the contract ("no active execution = idle").
    monkeypatch.setattr(cli_module, "_is_idle", lambda _result: True)

    def _fail_if_called(_interval: float) -> None:  # pragma: no cover - should not run
        raise AssertionError("sleep should not be reached when --exit-on-idle fires on tick 1")

    monkeypatch.setattr(cli_module, "_progress_watch_sleep", _fail_if_called)

    result = runner.invoke(
        app,
        [
            "--cwd",
            str(project),
            "progress",
            "json",
            "--watch",
            "--exit-on-idle",
            "--interval",
            "0.1",
        ],
    )

    assert result.exit_code == 0, result.stdout + (result.stderr or "")
    emitted = _parse_json_lines(result.stdout)
    assert len(emitted) >= 1, (
        f"expected at least one JSON emission before idle exit; got: {result.stdout!r}"
    )
    # Either live_execution is None (spec-ideal) or it's a shell object with
    # no populated live fields (E1's actual shape for empty projects).
    live = emitted[0].get("live_execution")
    if live is not None:
        populated_live_fields = {
            "phase",
            "plan",
            "wave",
            "current_task",
            "current_task_index",
            "current_task_total",
            "segment_status",
            "waiting_reason",
            "last_result_label",
            "last_artifact_path",
            "last_updated_age_label",
        }
        for name in populated_live_fields:
            assert live.get(name) is None, (
                f"expected idle live_execution to have no populated live field "
                f"{name!r}; got: {live!r}"
            )


def test_progress_watch_emits_plain_json_when_not_tty(
    tmp_path: Path, monkeypatch
) -> None:
    project = _bootstrap_project(tmp_path)
    _write_current_execution(project)

    monkeypatch.setattr(cli_module, "_stdout_is_interactive", lambda: False)
    # Force first-tick idle exit so the loop terminates deterministically
    # without relying on fake sleeps for this assertion.
    monkeypatch.setattr(cli_module, "_is_idle", lambda _result: True)

    def _fail_if_called(_interval: float) -> None:  # pragma: no cover - should not run
        raise AssertionError("sleep should not be reached when --exit-on-idle fires immediately")

    monkeypatch.setattr(cli_module, "_progress_watch_sleep", _fail_if_called)

    result = runner.invoke(
        app,
        [
            "--cwd",
            str(project),
            "progress",
            "json",
            "--watch",
            "--exit-on-idle",
            "--interval",
            "0.1",
        ],
    )

    assert result.exit_code == 0, result.stdout + (result.stderr or "")
    stdout = result.stdout
    assert "\x1b" not in stdout, (
        f"non-TTY watch output must be free of ANSI escape bytes; got: {stdout!r}"
    )
    for raw in stdout.splitlines():
        stripped = raw.strip()
        if not stripped:
            continue
        # Each non-empty line must be a standalone JSON object.
        parsed = json.loads(stripped)
        assert isinstance(parsed, dict)


def test_progress_watch_tty_renders_live_table(tmp_path: Path, monkeypatch) -> None:
    """TTY branch renders a rich.Live table against the module-level console.

    We swap ``cli_module.console`` with a recording Console whose file is a
    StringIO buffer, force the TTY branch, then raise KeyboardInterrupt on the
    first ``_progress_watch_sleep`` call so the loop exits cleanly after its
    initial Live render. The TTY path must not emit JSON on stdout.
    """
    project = _bootstrap_project(tmp_path)
    _write_current_execution(project, current_task="task-1")
    monkeypatch.chdir(project)

    # Force the TTY branch in _run_progress_watch_loop.
    monkeypatch.setattr(cli_module, "_stdout_is_interactive", lambda: True)

    # Swap the module-level console with a recording one so rich.Live writes
    # into an in-memory buffer rather than touching the test runner's stdout.
    # width=120 keeps the table columns stable regardless of host terminal.
    fake_console = Console(
        record=True,
        force_terminal=True,
        file=io.StringIO(),
        width=120,
    )
    monkeypatch.setattr(cli_module, "console", fake_console)

    calls = {"n": 0}

    def _fake_sleep(_seconds: float) -> None:
        calls["n"] += 1
        raise KeyboardInterrupt

    monkeypatch.setattr(cli_module, "_progress_watch_sleep", _fake_sleep)

    result = runner.invoke(
        app,
        ["progress", "json", "--watch", "--interval", "0.1"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, (result.stdout or "") + (result.stderr or "")
    # Live's enter/exit pair refreshes at least once, so the table — which
    # includes the current_task value — must appear in the recorded buffer.
    captured = fake_console.export_text()
    assert "task-1" in captured, (
        f"expected current_task 'task-1' in recorded Live output; got: {captured!r}"
    )
    # TTY path must NOT emit JSON lines on stdout — Live drives rendering
    # via the (fake) console, and _render_progress_watch_frame is a no-op.
    emitted = _parse_json_lines(result.stdout)
    assert emitted == [], (
        f"TTY watch path must not emit JSON on stdout; got: {result.stdout!r}"
    )
    assert calls["n"] == 1
