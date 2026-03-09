"""Tests for gpd.cli — unified CLI entry point.

Tests use typer.testing.CliRunner which invokes the CLI in-process.
We mock the underlying gpd.core.* functions since those modules may not
be fully ported yet and have their own test suites.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from gpd.cli import app

runner = CliRunner()


# ─── version & help ─────────────────────────────────────────────────────────


def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "gpd" in result.output


def test_version_subcommand():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "gpd" in result.output


def test_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "state" in result.output
    assert "phase" in result.output
    assert "health" in result.output


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
    mock_result.passed = True
    mock_result.model_dump.return_value = {"passed": True, "errors": []}
    mock_validate.return_value = mock_result
    result = runner.invoke(app, ["state", "validate"])
    assert result.exit_code == 0


@patch("gpd.core.state.state_validate")
def test_state_validate_fail(mock_validate):
    mock_result = MagicMock()
    mock_result.passed = False
    mock_result.model_dump.return_value = {"passed": False, "errors": ["bad"]}
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


# ─── raw output ─────────────────────────────────────────────────────────────


@patch("gpd.core.state.state_load")
def test_raw_json_output(mock_load):
    mock_load.return_value = {"position": {"current_phase": "42"}}
    result = runner.invoke(app, ["--raw", "state", "load"])
    assert result.exit_code == 0
    assert "current_phase" in result.output


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
    assert "sign convention" in args[0][1]


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


@patch("gpd.core.commands.cmd_scaffold")
def test_scaffold_subcommand(mock_scaffold):
    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"created": True, "path": "test"}
    mock_scaffold.return_value = mock_result
    result = runner.invoke(app, ["scaffold", "phase-dir", "--phase", "1", "--name", "Setup"])
    assert result.exit_code == 0
    mock_scaffold.assert_called_once()


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
