"""Tests for gpd.cli — unified CLI entry point.

Tests use typer.testing.CliRunner which invokes the CLI in-process.
We mock the underlying gpd.core.* functions since those modules may not
be fully ported yet and have their own test suites.
"""

from __future__ import annotations

import builtins
import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from typer.testing import CliRunner

import gpd.cli as cli_module
from gpd.adapters import list_runtimes
from gpd.cli import app

runner = CliRunner()


def _make_checkout(tmp_path: Path, version: str = "9.9.9") -> Path:
    """Create a minimal GPD source checkout for CLI version tests."""
    repo_root = tmp_path / "checkout"
    repo_root.mkdir(parents=True, exist_ok=True)
    (repo_root / "package.json").write_text(
        json.dumps(
            {
                "name": "get-physics-done",
                "version": version,
                "gpdPythonVersion": version,
            }
        ),
        encoding="utf-8",
    )
    (repo_root / "pyproject.toml").write_text(
        f'[project]\nname = "get-physics-done"\nversion = "{version}"\n',
        encoding="utf-8",
    )
    gpd_root = repo_root / "src" / "gpd"
    for subdir in ("commands", "agents", "hooks", "specs"):
        (gpd_root / subdir).mkdir(parents=True, exist_ok=True)
    return repo_root


# ─── version & help ─────────────────────────────────────────────────────────


def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "gpd" in result.output


def test_version_subcommand():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "gpd" in result.output


def test_version_subcommand_prefers_checkout_version(tmp_path: Path):
    checkout = _make_checkout(tmp_path, "9.9.9")

    result = runner.invoke(app, ["--cwd", str(checkout), "version"])

    assert result.exit_code == 0
    assert "9.9.9" in result.output


def test_raw_version_option_outputs_json():
    result = runner.invoke(app, ["--raw", "--version"])
    assert result.exit_code == 0
    assert json.loads(result.output)["result"].startswith("gpd ")


def test_raw_version_subcommand_outputs_json():
    result = runner.invoke(app, ["--raw", "version"])
    assert result.exit_code == 0
    assert json.loads(result.output)["result"].startswith("gpd ")


def test_entrypoint_reexecs_from_checkout_when_running_outside_checkout(tmp_path: Path, monkeypatch) -> None:
    checkout = _make_checkout(tmp_path, "9.9.9")
    managed_cli = tmp_path / "managed" / "site-packages" / "gpd" / "cli.py"
    managed_cli.parent.mkdir(parents=True, exist_ok=True)
    managed_cli.write_text("# managed copy placeholder\n", encoding="utf-8")

    monkeypatch.chdir(checkout)
    monkeypatch.setattr(cli_module, "__file__", str(managed_cli))
    monkeypatch.setattr(cli_module.sys, "argv", ["gpd", "version"])

    captured: dict[str, object] = {}

    def fake_execve(executable: str, argv: list[str], env: dict[str, str]) -> None:
        captured["executable"] = executable
        captured["argv"] = argv
        captured["env"] = env
        raise SystemExit(0)

    monkeypatch.setattr(cli_module.os, "execve", fake_execve)

    with patch.object(cli_module, "app", side_effect=AssertionError("entrypoint should re-exec before running app")):
        with patch.dict(os.environ, {}, clear=True):
            try:
                cli_module.entrypoint()
            except SystemExit as exc:
                assert exc.code == 0

    assert captured["argv"] == [cli_module.sys.executable, "-m", "gpd.cli", "version"]
    env = captured["env"]
    assert isinstance(env, dict)
    assert env["GPD_DISABLE_CHECKOUT_REEXEC"] == "1"
    assert env["PYTHONPATH"].split(os.pathsep)[0] == str(checkout / "src")


def test_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "observe" in result.output
    assert "state" in result.output
    assert "phase" in result.output
    assert "health" in result.output
    assert "paper-build" in result.output


def test_resolve_model_help_lists_supported_runtime_ids():
    result = runner.invoke(app, ["resolve-model", "--help"])
    assert result.exit_code == 0
    for runtime_name in list_runtimes():
        assert runtime_name in result.output


def test_state_help():
    result = runner.invoke(app, ["state", "--help"])
    assert result.exit_code == 0
    assert "load" in result.output
    assert "get" in result.output
    assert "update" in result.output


def test_phase_help():
    result = runner.invoke(app, ["phase", "--help"])
    assert result.exit_code == 0
    assert "list" in result.output
    assert "add" in result.output
    assert "complete" in result.output


def test_session_command_is_not_exposed():
    result = runner.invoke(app, ["session", "--help"])
    assert result.exit_code != 0
    assert "No such command 'session'" in result.output


def test_view_command_is_not_exposed():
    result = runner.invoke(app, ["view", "--help"])
    assert result.exit_code != 0
    assert "No such command 'view'" in result.output


# ─── state subcommands ──────────────────────────────────────────────────────


@patch("gpd.core.state.state_load")
def test_state_load(mock_load):
    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"position": {"current_phase": "42"}}
    mock_load.return_value = mock_result
    result = runner.invoke(app, ["state", "load"])
    assert result.exit_code == 0
    mock_load.assert_called_once()


@patch("gpd.core.state.state_get")
def test_state_get_section(mock_get):
    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"section": "position", "data": {}}
    mock_get.return_value = mock_result
    result = runner.invoke(app, ["state", "get", "position"])
    assert result.exit_code == 0
    mock_get.assert_called_once()


@patch("gpd.core.state.state_update")
def test_state_update(mock_update):
    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"updated": True}
    mock_update.return_value = mock_result
    result = runner.invoke(app, ["state", "update", "status", "executing"])
    assert result.exit_code == 0
    mock_update.assert_called_once()


@patch("gpd.core.state.state_validate")
def test_state_validate_pass(mock_validate):
    mock_result = MagicMock()
    mock_result.valid = True
    mock_result.model_dump.return_value = {"valid": True, "issues": []}
    mock_validate.return_value = mock_result
    result = runner.invoke(app, ["state", "validate"])
    assert result.exit_code == 0


@patch("gpd.core.state.state_validate")
def test_state_validate_fail(mock_validate):
    mock_result = MagicMock()
    mock_result.valid = False
    mock_result.model_dump.return_value = {"valid": False, "issues": ["bad"]}
    mock_validate.return_value = mock_result
    result = runner.invoke(app, ["state", "validate"])
    assert result.exit_code == 1


# ─── phase subcommands ──────────────────────────────────────────────────────


@patch("gpd.core.phases.list_phases")
def test_phase_list(mock_list):
    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"phases": []}
    mock_list.return_value = mock_result
    result = runner.invoke(app, ["phase", "list"])
    assert result.exit_code == 0
    mock_list.assert_called_once()


@patch("gpd.core.phases.phase_add")
def test_phase_add(mock_add):
    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"phase": "43", "added": True}
    mock_add.return_value = mock_result
    result = runner.invoke(app, ["phase", "add", "Compute", "cross", "section"])
    assert result.exit_code == 0
    # Verify the description was joined
    args = mock_add.call_args
    assert "Compute cross section" in args[0][1]


@patch("gpd.core.phases.phase_complete")
def test_phase_complete(mock_complete):
    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"completed": True}
    mock_complete.return_value = mock_result
    result = runner.invoke(app, ["phase", "complete", "42"])
    assert result.exit_code == 0
    mock_complete.assert_called_once()


@patch("gpd.core.phases.validate_phase_waves")
def test_phase_validate_waves_pass(mock_validate):
    mock_result = MagicMock()
    mock_result.validation.valid = True
    mock_result.model_dump.return_value = {"phase": "42", "validation": {"valid": True, "errors": []}}
    mock_validate.return_value = mock_result

    result = runner.invoke(app, ["phase", "validate-waves", "42"])

    assert result.exit_code == 0
    mock_validate.assert_called_once()


@patch("gpd.core.phases.validate_phase_waves")
def test_phase_validate_waves_fail(mock_validate):
    mock_result = MagicMock()
    mock_result.validation.valid = False
    mock_result.model_dump.return_value = {"phase": "42", "validation": {"valid": False, "errors": ["cycle"]}}
    mock_validate.return_value = mock_result

    result = runner.invoke(app, ["phase", "validate-waves", "42"])

    assert result.exit_code == 1
    mock_validate.assert_called_once()


# ─── raw output ─────────────────────────────────────────────────────────────


@patch("gpd.core.state.state_load")
def test_raw_json_output(mock_load):
    mock_load.return_value = {"position": {"current_phase": "42"}}
    result = runner.invoke(app, ["--raw", "state", "load"])
    assert result.exit_code == 0
    assert "current_phase" in result.output


def test_raw_json_get_outputs_literal_json_value():
    result = runner.invoke(app, ["--raw", "json", "get", ".x"], input='{"x": 1}\n')
    assert result.exit_code == 0
    assert json.loads(result.output) == "1"


def test_raw_json_get_error_outputs_json():
    result = runner.invoke(app, ["--raw", "json", "get", ".x"], input="not json\n")
    assert result.exit_code == 1
    assert "Invalid JSON input" in json.loads(result.output)["error"]


def test_normalize_global_cli_options_moves_trailing_root_options(tmp_path: Path) -> None:
    argv = ["progress", "bar", "--cwd", str(tmp_path), "--raw"]

    assert cli_module._normalize_global_cli_options(argv) == [
        "--cwd",
        str(tmp_path),
        "--raw",
        "progress",
        "bar",
    ]


def test_normalize_global_cli_options_respects_double_dash() -> None:
    argv = ["json", "get", ".x", "--", "--raw"]

    assert cli_module._normalize_global_cli_options(argv) == argv


def test_resolve_cli_cwd_from_argv_supports_trailing_cwd(tmp_path: Path) -> None:
    resolved = cli_module._resolve_cli_cwd_from_argv(["progress", "bar", "--cwd", str(tmp_path)])

    assert resolved == tmp_path.resolve()


def test_entrypoint_normalizes_trailing_global_options(monkeypatch) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(cli_module, "_maybe_reexec_from_checkout", lambda: None)
    monkeypatch.setattr(cli_module.sys, "argv", ["gpd", "progress", "bar", "--cwd", "/tmp/demo", "--raw"])

    def fake_app(*, args: list[str] | None = None) -> int:
        captured["args"] = args
        return 0

    monkeypatch.setattr(cli_module, "app", fake_app)

    assert cli_module.entrypoint() == 0
    assert captured["args"] == ["--cwd", "/tmp/demo", "--raw", "progress", "bar"]


@patch("gpd.core.phases.progress_render")
def test_app_call_accepts_trailing_raw_and_cwd(mock_progress, tmp_path: Path, capsys) -> None:
    mock_progress.return_value = {"bar": "ok"}

    try:
        cli_module.app(args=["progress", "bar", "--cwd", str(tmp_path), "--raw"])
    except SystemExit as exc:
        assert exc.code == 0

    captured = capsys.readouterr()
    assert json.loads(captured.out)["bar"] == "ok"
    mock_progress.assert_called_once_with(tmp_path.resolve(), "bar")


def test_validate_command_context_accepts_tokenized_standalone_arguments(tmp_path: Path) -> None:
    empty_dir = tmp_path / "empty-context"
    empty_dir.mkdir()

    result = runner.invoke(
        app,
        [
            "--raw",
            "--cwd",
            str(empty_dir),
            "validate",
            "command-context",
            "discover",
            "finite-temperature",
            "RG",
            "flow",
            "--depth",
            "deep",
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["command"] == "gpd:discover"
    assert payload["context_mode"] == "project-aware"
    assert payload["passed"] is True


def test_validate_command_context_accepts_tokenized_explain_arguments(tmp_path: Path) -> None:
    empty_dir = tmp_path / "empty-context"
    empty_dir.mkdir()

    result = runner.invoke(
        app,
        [
            "--raw",
            "--cwd",
            str(empty_dir),
            "validate",
            "command-context",
            "explain",
            "Berry",
            "curvature",
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["command"] == "gpd:explain"
    assert payload["context_mode"] == "project-aware"
    assert payload["passed"] is True


def test_pre_commit_check_recurses_into_directory_inputs(tmp_path: Path) -> None:
    directory = tmp_path / "docs"
    directory.mkdir()
    (directory / "state.md").write_text("# ok\n", encoding="utf-8")

    result = runner.invoke(
        app,
        ["--raw", "--cwd", str(tmp_path), "pre-commit-check", "--files", str(directory)],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["passed"] is True
    assert payload["files_checked"] == 1
    assert payload["details"][0]["file"].endswith("docs/state.md")


def test_pre_commit_check_fails_for_unreadable_inputs(tmp_path: Path) -> None:
    target = tmp_path / "state.md"
    target.write_text("# ok\n", encoding="utf-8")

    with patch("gpd.core.git_ops.Path.read_text", side_effect=OSError("denied")):
        result = runner.invoke(
            app,
            ["--raw", "--cwd", str(tmp_path), "pre-commit-check", "--files", str(target)],
            catch_exceptions=False,
        )

    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    assert payload["passed"] is False
    assert payload["details"][0]["readable"] is False


# ─── convention subcommands ─────────────────────────────────────────────────


@patch("gpd.core.conventions.convention_list")
def test_convention_list(mock_list):
    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"conventions": {}}
    mock_list.return_value = mock_result
    result = runner.invoke(app, ["convention", "list"])
    assert result.exit_code == 0
    mock_list.assert_called_once()


# ─── query subcommands ──────────────────────────────────────────────────────


@patch("gpd.core.query.query_deps")
def test_query_deps(mock_deps):
    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"deps": []}
    mock_deps.return_value = mock_result
    result = runner.invoke(app, ["query", "deps", "42"])
    assert result.exit_code == 0
    mock_deps.assert_called_once()


# ─── health / doctor ────────────────────────────────────────────────────────


@patch("gpd.core.health.run_health")
def test_health(mock_health):
    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"passed": True, "checks": []}
    mock_health.return_value = mock_result
    result = runner.invoke(app, ["health"])
    assert result.exit_code == 0
    mock_health.assert_called_once()


@patch("gpd.core.health.run_doctor")
def test_doctor(mock_doctor):
    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"ok": True}
    mock_doctor.return_value = mock_result
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    mock_doctor.assert_called_once()


# ─── trace subcommands ──────────────────────────────────────────────────────


@patch("gpd.core.trace.trace_start")
def test_trace_start(mock_start):
    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"started": True}
    mock_start.return_value = mock_result
    result = runner.invoke(app, ["trace", "start", "42", "plan-a"])
    assert result.exit_code == 0
    mock_start.assert_called_once()


@patch("gpd.core.trace.trace_stop")
def test_trace_stop(mock_stop):
    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"stopped": True}
    mock_stop.return_value = mock_result
    result = runner.invoke(app, ["trace", "stop"])
    assert result.exit_code == 0
    mock_stop.assert_called_once()


def test_observe_sessions_reads_local_metadata(tmp_path: Path) -> None:
    planning = tmp_path / ".gpd" / "observability" / "sessions"
    planning.mkdir(parents=True)
    (planning / "cli-session-1.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "timestamp": "2026-03-10T00:00:00+00:00",
                        "event_id": "evt-1",
                        "session_id": "cli-session-1",
                        "category": "session",
                        "name": "lifecycle",
                        "action": "start",
                        "status": "active",
                        "command": "timestamp",
                        "data": {"cwd": str(tmp_path), "source": "cli", "pid": 123, "metadata": {}},
                    }
                ),
                json.dumps(
                    {
                        "timestamp": "2026-03-10T00:00:01+00:00",
                        "event_id": "evt-2",
                        "session_id": "cli-session-1",
                        "category": "session",
                        "name": "lifecycle",
                        "action": "finish",
                        "status": "ok",
                        "command": "timestamp",
                        "data": {"ended_at": "2026-03-10T00:00:01+00:00", "ended_by": {"name": "command"}},
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["--raw", "--cwd", str(tmp_path), "observe", "sessions"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["count"] >= 1
    assert any(session["session_id"] == "cli-session-1" for session in payload["sessions"])
    assert any(session.get("command") == "timestamp" for session in payload["sessions"])


def test_observe_show_filters_events(tmp_path: Path) -> None:
    sessions_dir = tmp_path / ".gpd" / "observability" / "sessions"
    sessions_dir.mkdir(parents=True)
    (sessions_dir / "cli-a.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "timestamp": "2026-03-10T00:00:00+00:00",
                        "event_id": "evt-1",
                        "session_id": "cli-a",
                        "category": "cli",
                        "name": "command",
                        "action": "start",
                        "status": "active",
                        "command": "timestamp",
                    }
                ),
                json.dumps(
                    {
                        "timestamp": "2026-03-10T00:00:01+00:00",
                        "event_id": "evt-2",
                        "session_id": "cli-a",
                        "category": "trace",
                        "name": "trace_start",
                        "action": "log",
                        "status": "ok",
                        "command": "trace start",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        ["--raw", "--cwd", str(tmp_path), "observe", "show", "--category", "cli", "--command", "timestamp"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["events"][0]["category"] == "cli"
    assert payload["events"][0]["command"] == "timestamp"


def test_observe_show_falls_back_to_session_logs(tmp_path: Path) -> None:
    """show_events reads per-session logs when filtering observability data."""
    sessions_dir = tmp_path / ".gpd" / "observability" / "sessions"
    sessions_dir.mkdir(parents=True)
    (sessions_dir / "cli-a.jsonl").write_text(
        json.dumps(
            {
                "timestamp": "2026-03-10T00:00:00+00:00",
                "event_id": "evt-1",
                "session_id": "cli-a",
                "category": "cli",
                "name": "command",
                "action": "start",
                "status": "active",
                "command": "timestamp",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    # The CLI invocation may create a global events file as a side effect of
    # its own observability, so test the core function directly instead.
    from gpd.core.observability import show_events

    result = show_events(tmp_path, category="cli", command="timestamp")
    assert result.count == 1
    assert result.events[0]["session_id"] == "cli-a"


def test_observe_event_appends_event(tmp_path: Path) -> None:
    (tmp_path / ".gpd").mkdir()

    result = runner.invoke(
        app,
        [
            "--raw",
            "--cwd",
            str(tmp_path),
            "observe",
            "event",
            "workflow",
            "wave-start",
            "--action",
            "start",
            "--status",
            "active",
            "--command",
            "execute-phase",
            "--phase",
            "03",
            "--plan",
            "01",
            "--data",
            '{"wave": 2}',
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["category"] == "workflow"
    assert payload["name"] == "wave-start"
    assert payload["data"]["wave"] == 2
    sessions_dir = tmp_path / ".gpd" / "observability" / "sessions"
    session_logs = sorted(sessions_dir.glob("*.jsonl"))
    assert len(session_logs) == 1
    events = [json.loads(line) for line in session_logs[0].read_text(encoding="utf-8").splitlines() if line.strip()]
    assert any(event["category"] == "workflow" and event["name"] == "wave-start" for event in events)
    assert not (tmp_path / ".gpd" / "observability" / "events.jsonl").exists()


def test_cli_invocation_does_not_write_observability_files_without_explicit_events(tmp_path: Path) -> None:
    (tmp_path / ".gpd").mkdir()

    result = runner.invoke(app, ["--cwd", str(tmp_path), "timestamp"])

    assert result.exit_code == 0
    obs_dir = tmp_path / ".gpd" / "observability"
    assert not obs_dir.exists()


# ─── suggest ────────────────────────────────────────────────────────────────


@patch("gpd.core.suggest.suggest_next")
def test_suggest(mock_suggest):
    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"suggestions": []}
    mock_suggest.return_value = mock_result
    result = runner.invoke(app, ["suggest"])
    assert result.exit_code == 0
    mock_suggest.assert_called_once()


# ─── pattern subcommands ────────────────────────────────────────────────────


@patch("gpd.core.patterns.pattern_init")
def test_pattern_init(mock_init):
    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"initialized": True}
    mock_init.return_value = mock_result
    result = runner.invoke(app, ["pattern", "init"])
    assert result.exit_code == 0
    mock_init.assert_called_once()


@patch("gpd.core.patterns.pattern_search")
def test_pattern_search(mock_search):
    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"results": []}
    mock_search.return_value = mock_result
    result = runner.invoke(app, ["pattern", "search", "sign", "convention"])
    assert result.exit_code == 0
    # Verify query was joined
    args = mock_search.call_args
    assert "sign convention" in args[0][0]


# ─── init subcommands ───────────────────────────────────────────────────────


@patch("gpd.core.context.init_execute_phase")
def test_init_execute_phase(mock_init):
    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"context": "..."}
    mock_init.return_value = mock_result
    result = runner.invoke(app, ["init", "execute-phase", "42"])
    assert result.exit_code == 0
    mock_init.assert_called_once()


@patch("gpd.core.context.init_new_project")
def test_init_new_project(mock_init):
    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"context": "..."}
    mock_init.return_value = mock_result
    result = runner.invoke(app, ["init", "new-project"])
    assert result.exit_code == 0
    mock_init.assert_called_once()


def test_paper_build_uses_default_config_surface(tmp_path: Path):
    paper_dir = tmp_path / "paper"
    paper_dir.mkdir()
    (paper_dir / "PAPER-CONFIG.json").write_text(
        json.dumps(
            {
                "title": "Configured Paper",
                "authors": [{"name": "A. Researcher"}],
                "abstract": "Abstract.",
                "sections": [{"title": "Intro", "content": "Hello."}],
                "figures": [{"path": "figures/plot.png", "caption": "Plot", "label": "plot"}],
            }
        ),
        encoding="utf-8",
    )
    references_dir = tmp_path / "references"
    references_dir.mkdir()
    (references_dir / "references.bib").write_text(
        "@article{einstein1905,\n  author={Einstein, Albert},\n  title={Relativity},\n  year={1905}\n}\n",
        encoding="utf-8",
    )

    result_payload = MagicMock()
    result_payload.manifest_path = paper_dir / "ARTIFACT-MANIFEST.json"
    result_payload.bibliography_audit_path = None
    result_payload.pdf_path = paper_dir / "main.pdf"
    result_payload.success = True
    result_payload.errors = []

    with patch("gpd.mcp.paper.compiler.build_paper", new=AsyncMock(return_value=result_payload)) as mock_build:
        result = runner.invoke(app, ["--raw", "--cwd", str(tmp_path), "paper-build"], catch_exceptions=False)

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["config_path"] == "./paper/PAPER-CONFIG.json"
    assert payload["output_dir"] == "./paper"
    assert payload["tex_path"] == "./paper/main.tex"
    assert payload["bibliography_source"] == "./references/references.bib"
    assert payload["manifest_path"] == "./paper/ARTIFACT-MANIFEST.json"
    assert payload["pdf_path"] == "./paper/main.pdf"

    args = mock_build.await_args.args
    kwargs = mock_build.await_args.kwargs
    assert args[1] == paper_dir.resolve(strict=False)
    assert args[0].figures[0].path == (paper_dir / "figures" / "plot.png").resolve(strict=False)
    assert kwargs["bib_data"] is not None
    assert kwargs["citation_sources"] is None
    assert kwargs["enrich_bibliography"] is True


def test_paper_build_prefers_paper_dir_before_later_config_roots(tmp_path: Path) -> None:
    paper_dir = tmp_path / "paper"
    paper_dir.mkdir()
    manuscript_dir = tmp_path / "manuscript"
    manuscript_dir.mkdir()
    draft_dir = tmp_path / "draft"
    draft_dir.mkdir()

    (paper_dir / "PAPER-CONFIG.json").write_text(
        json.dumps(
            {
                "title": "paper-uppercase",
                "authors": [{"name": "A. Researcher"}],
                "abstract": "Abstract.",
                "sections": [{"title": "Intro", "content": "Hello."}],
                "figures": [],
            }
        ),
        encoding="utf-8",
    )
    (manuscript_dir / "PAPER-CONFIG.json").write_text(
        json.dumps(
            {
                "title": "manuscript-uppercase",
                "authors": [{"name": "B. Researcher"}],
                "abstract": "Abstract.",
                "sections": [{"title": "Intro", "content": "Hello."}],
                "figures": [],
            }
        ),
        encoding="utf-8",
    )
    (draft_dir / "PAPER-CONFIG.json").write_text(
        json.dumps(
            {
                "title": "draft-uppercase",
                "authors": [{"name": "D. Researcher"}],
                "abstract": "Abstract.",
                "sections": [{"title": "Intro", "content": "Hello."}],
                "figures": [],
            }
        ),
        encoding="utf-8",
    )

    result_payload = MagicMock()
    result_payload.manifest_path = paper_dir / "ARTIFACT-MANIFEST.json"
    result_payload.bibliography_audit_path = None
    result_payload.pdf_path = paper_dir / "main.pdf"
    result_payload.success = True
    result_payload.errors = []

    with patch("gpd.mcp.paper.compiler.build_paper", new=AsyncMock(return_value=result_payload)) as mock_build:
        result = runner.invoke(app, ["--raw", "--cwd", str(tmp_path), "paper-build"], catch_exceptions=False)

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["config_path"] == "./paper/PAPER-CONFIG.json"
    assert mock_build.await_args.args[0].title == "paper-uppercase"


def test_paper_build_prefers_manuscript_before_draft(tmp_path: Path) -> None:
    manuscript_dir = tmp_path / "manuscript"
    manuscript_dir.mkdir()
    draft_dir = tmp_path / "draft"
    draft_dir.mkdir()

    (manuscript_dir / "PAPER-CONFIG.json").write_text(
        json.dumps(
            {
                "title": "manuscript-uppercase",
                "authors": [{"name": "A. Researcher"}],
                "abstract": "Abstract.",
                "sections": [{"title": "Intro", "content": "Hello."}],
                "figures": [],
            }
        ),
        encoding="utf-8",
    )
    (draft_dir / "PAPER-CONFIG.json").write_text(
        json.dumps(
            {
                "title": "draft-uppercase",
                "authors": [{"name": "B. Researcher"}],
                "abstract": "Abstract.",
                "sections": [{"title": "Intro", "content": "Hello."}],
                "figures": [],
            }
        ),
        encoding="utf-8",
    )

    result_payload = MagicMock()
    result_payload.manifest_path = manuscript_dir / "ARTIFACT-MANIFEST.json"
    result_payload.bibliography_audit_path = None
    result_payload.pdf_path = manuscript_dir / "main.pdf"
    result_payload.success = True
    result_payload.errors = []

    with patch("gpd.mcp.paper.compiler.build_paper", new=AsyncMock(return_value=result_payload)) as mock_build:
        result = runner.invoke(app, ["--raw", "--cwd", str(tmp_path), "paper-build"], catch_exceptions=False)

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["config_path"] == "./manuscript/PAPER-CONFIG.json"
    assert mock_build.await_args.args[0].title == "manuscript-uppercase"


def test_paper_build_does_not_discover_legacy_planning_configs(tmp_path: Path, capsys) -> None:
    planning_paper_dir = tmp_path / ".gpd" / "paper"
    planning_paper_dir.mkdir(parents=True)
    (planning_paper_dir / "PAPER-CONFIG.json").write_text(
        json.dumps(
            {
                "title": "planning-uppercase",
                "authors": [{"name": "A. Researcher"}],
                "abstract": "Abstract.",
                "sections": [{"title": "Intro", "content": "Hello."}],
                "figures": [],
            }
        ),
        encoding="utf-8",
    )

    try:
        cli_module.app(args=["--raw", "--cwd", str(tmp_path), "paper-build"])
    except SystemExit as exc:
        assert exc.code == 1

    captured = capsys.readouterr()
    payload = json.loads(captured.err)
    assert "No paper config found" in payload["error"]
    assert ".gpd/paper" not in payload["error"]


def test_paper_build_rejects_explicit_legacy_planning_config_path(tmp_path: Path, capsys) -> None:
    planning_paper_dir = tmp_path / ".gpd" / "paper"
    planning_paper_dir.mkdir(parents=True)
    (planning_paper_dir / "PAPER-CONFIG.json").write_text(
        json.dumps(
            {
                "title": "planning-uppercase",
                "authors": [{"name": "A. Researcher"}],
                "abstract": "Abstract.",
                "sections": [{"title": "Intro", "content": "Hello."}],
                "figures": [],
            }
        ),
        encoding="utf-8",
    )

    try:
        cli_module.app(args=["--raw", "--cwd", str(tmp_path), "paper-build", ".gpd/paper/PAPER-CONFIG.json"])
    except SystemExit as exc:
        assert exc.code == 1

    captured = capsys.readouterr()
    payload = json.loads(captured.err)
    assert "no longer supported" in payload["error"]


def test_paper_build_prefers_config_dir_bibliography_before_output_and_references(tmp_path: Path) -> None:
    paper_dir = tmp_path / "paper"
    paper_dir.mkdir()
    (paper_dir / "PAPER-CONFIG.json").write_text(
        json.dumps(
            {
                "title": "Configured Paper",
                "authors": [{"name": "A. Researcher"}],
                "abstract": "Abstract.",
                "sections": [{"title": "Intro", "content": "Hello."}],
                "figures": [],
            }
        ),
        encoding="utf-8",
    )
    (paper_dir / "references.bib").write_text(
        "@article{configsource,\n  author={Config, Source},\n  title={Config},\n  year={1905}\n}\n",
        encoding="utf-8",
    )

    output_dir = tmp_path / "output"
    output_dir.mkdir()
    (output_dir / "references.bib").write_text(
        "@article{outsource,\n  author={Output, Source},\n  title={Output},\n  year={1906}\n}\n",
        encoding="utf-8",
    )

    references_dir = tmp_path / "references"
    references_dir.mkdir()
    (references_dir / "references.bib").write_text(
        "@article{refsource,\n  author={References, Source},\n  title={References},\n  year={1907}\n}\n",
        encoding="utf-8",
    )

    result_payload = MagicMock()
    result_payload.manifest_path = output_dir / "ARTIFACT-MANIFEST.json"
    result_payload.bibliography_audit_path = None
    result_payload.pdf_path = output_dir / "main.pdf"
    result_payload.success = True
    result_payload.errors = []

    with patch("gpd.mcp.paper.compiler.build_paper", new=AsyncMock(return_value=result_payload)) as mock_build:
        result = runner.invoke(
            app,
            ["--raw", "--cwd", str(tmp_path), "paper-build", "--output-dir", str(output_dir)],
            catch_exceptions=False,
        )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["bibliography_source"] == "./paper/references.bib"
    assert "configsource" in mock_build.await_args.kwargs["bib_data"].entries


def test_paper_build_without_bibliography_does_not_import_pybtex(tmp_path: Path, monkeypatch) -> None:
    paper_dir = tmp_path / "paper"
    paper_dir.mkdir()
    (paper_dir / "PAPER-CONFIG.json").write_text(
        json.dumps(
            {
                "title": "Configured Paper",
                "authors": [{"name": "A. Researcher"}],
                "abstract": "Abstract.",
                "sections": [{"title": "Intro", "content": "Hello."}],
                "figures": [],
            }
        ),
        encoding="utf-8",
    )

    real_import = builtins.__import__

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):  # type: ignore[no-untyped-def]
        if name.startswith("pybtex"):
            raise AssertionError("pybtex should not be imported when no bibliography source exists")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded_import)

    result_payload = MagicMock()
    result_payload.manifest_path = paper_dir / "ARTIFACT-MANIFEST.json"
    result_payload.bibliography_audit_path = None
    result_payload.pdf_path = paper_dir / "main.pdf"
    result_payload.success = True
    result_payload.errors = []

    with patch("gpd.mcp.paper.compiler.build_paper", new=AsyncMock(return_value=result_payload)) as mock_build:
        result = runner.invoke(app, ["--raw", "--cwd", str(tmp_path), "paper-build"], catch_exceptions=False)

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["bibliography_source"] == ""
    assert mock_build.await_args.kwargs["bib_data"] is None


# ─── ported command subcommands ─────────────────────────────────────────────


@patch("gpd.core.commands.cmd_current_timestamp")
def test_timestamp_subcommand(mock_ts):
    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"timestamp": "2026-03-04T12:00:00+00:00"}
    mock_ts.return_value = mock_result
    result = runner.invoke(app, ["timestamp", "full"])
    assert result.exit_code == 0
    mock_ts.assert_called_once_with("full")


@patch("gpd.core.commands.cmd_generate_slug")
def test_slug_subcommand(mock_slug):
    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"slug": "hello-world"}
    mock_slug.return_value = mock_result
    result = runner.invoke(app, ["slug", "Hello World"])
    assert result.exit_code == 0
    mock_slug.assert_called_once_with("Hello World")


@patch("gpd.core.commands.cmd_verify_path_exists")
def test_verify_path_subcommand(mock_verify):
    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"exists": True, "type": "file"}
    mock_verify.return_value = mock_result
    result = runner.invoke(app, ["verify-path", "some/path"])
    assert result.exit_code == 0
    mock_verify.assert_called_once()


@patch("gpd.core.commands.cmd_history_digest")
def test_history_digest_subcommand(mock_digest):
    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"phases": {}, "decisions": [], "methods": []}
    mock_digest.return_value = mock_result
    result = runner.invoke(app, ["history-digest"])
    assert result.exit_code == 0
    mock_digest.assert_called_once()


@patch("gpd.core.checkpoints.sync_phase_checkpoints")
def test_sync_phase_checkpoints_subcommand(mock_sync):
    mock_result = MagicMock()
    mock_result.model_dump.return_value = {
        "generated": True,
        "phase_count": 1,
        "checkpoint_dir": "phase-checkpoints",
        "root_index": "CHECKPOINTS.md",
        "updated_files": ["phase-checkpoints/01-test-phase.md", "CHECKPOINTS.md"],
        "removed_files": [],
    }
    mock_sync.return_value = mock_result
    result = runner.invoke(app, ["sync-phase-checkpoints"])
    assert result.exit_code == 0
    mock_sync.assert_called_once()


@patch("gpd.core.commands.cmd_regression_check")
def test_regression_check_subcommand_passing(mock_check):
    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"passed": True, "issues": [], "phases_checked": 2}
    mock_result.passed = True
    mock_check.return_value = mock_result
    result = runner.invoke(app, ["regression-check"])
    assert result.exit_code == 0


@patch("gpd.core.commands.cmd_regression_check")
def test_regression_check_subcommand_failing(mock_check):
    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"passed": False, "issues": [{"type": "conflict"}], "phases_checked": 2}
    mock_result.passed = False
    mock_check.return_value = mock_result
    result = runner.invoke(app, ["regression-check"])
    assert result.exit_code == 1
