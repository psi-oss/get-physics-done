"""Focused regressions for the public `gpd result show` CLI surface."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from gpd.cli import app

runner = CliRunner()


def _write_result_chain(cwd: Path) -> None:
    state_path = cwd / "GPD" / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["intermediate_results"] = [
        {
            "id": "R-01",
            "equation": "A",
            "description": "seed result",
            "phase": "1",
            "depends_on": [],
        },
        {
            "id": "R-02",
            "equation": "B",
            "description": "bridge result",
            "phase": "2",
            "depends_on": ["R-01"],
        },
        {
            "id": "R-03",
            "equation": "C",
            "description": "target result",
            "phase": "3",
            "depends_on": ["R-02"],
        },
    ]
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def test_result_show_cli_surfaces_result_and_dependency_chain_in_raw_output(
    tmp_path: Path, state_project_factory
) -> None:
    cwd = state_project_factory(tmp_path)
    _write_result_chain(cwd)

    result = runner.invoke(
        app,
        ["--raw", "--cwd", str(cwd), "result", "show", "R-03"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["result"]["id"] == "R-03"
    assert payload["result"]["equation"] == "C"
    assert payload["result"]["description"] == "target result"
    assert payload["depends_on"] == ["R-02"]
    assert [entry["id"] for entry in payload["direct_deps"]] == ["R-02"]
    assert [entry["id"] for entry in payload["transitive_deps"]] == ["R-01"]


def test_result_show_cli_human_output_mentions_result_and_equation(
    tmp_path: Path, state_project_factory
) -> None:
    cwd = state_project_factory(tmp_path)
    _write_result_chain(cwd)

    result = runner.invoke(
        app,
        ["--cwd", str(cwd), "result", "show", "R-03"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    assert "R-03" in result.output
    assert "C" in result.output
    assert "target result" in result.output
