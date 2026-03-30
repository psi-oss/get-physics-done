"""Focused regressions for the public `gpd result deps` CLI surface."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from gpd.cli import app

runner = CliRunner()


def test_result_deps_cli_surfaces_direct_and_transitive_dependencies(
    tmp_path: Path, state_project_factory
) -> None:
    cwd = state_project_factory(tmp_path)
    state_path = cwd / "GPD" / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["intermediate_results"] = [
        {"id": "R-01", "equation": "A", "phase": "1", "depends_on": []},
        {"id": "R-02", "equation": "B", "phase": "2", "depends_on": ["R-01"]},
        {"id": "R-03", "equation": "C", "phase": "3", "depends_on": ["R-02"]},
    ]
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    result = runner.invoke(
        app,
        ["--raw", "--cwd", str(cwd), "result", "deps", "R-03"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["result"]["id"] == "R-03"
    assert payload["depends_on"] == ["R-02"]
    assert [entry["id"] for entry in payload["direct_deps"]] == ["R-02"]
    assert [entry["id"] for entry in payload["transitive_deps"]] == ["R-01"]


def test_result_deps_cli_surfaces_missing_dependencies(
    tmp_path: Path, state_project_factory
) -> None:
    cwd = state_project_factory(tmp_path)
    state_path = cwd / "GPD" / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["intermediate_results"] = [
        {"id": "R-02", "equation": "B", "phase": "2", "depends_on": ["R-missing"]},
    ]
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    result = runner.invoke(
        app,
        ["--raw", "--cwd", str(cwd), "result", "deps", "R-02"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["result"]["id"] == "R-02"
    assert payload["depends_on"] == ["R-missing"]
    assert payload["direct_deps"] == [{"id": "R-missing", "missing": True}]
    assert payload["transitive_deps"] == []
