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
        {"id": "R-01", "equation": "A", "phase": "1", "depends_on": []},
        {"id": "R-02", "equation": "B", "phase": "2", "depends_on": ["R-01"]},
        {"id": "R-03", "equation": "C", "phase": "3", "depends_on": ["R-02"]},
    ]
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def test_result_downstream_cli_surfaces_direct_and_transitive_dependents_in_raw_output(
    tmp_path: Path, state_project_factory
) -> None:
    cwd = state_project_factory(tmp_path)
    _write_result_chain(cwd)

    result = runner.invoke(
        app,
        ["--raw", "--cwd", str(cwd), "result", "downstream", "R-01"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["result"]["id"] == "R-01"
    assert payload["result"]["equation"] == "A"
    assert [entry["id"] for entry in payload["direct_dependents"]] == ["R-02"]
    assert [entry["id"] for entry in payload["transitive_dependents"]] == ["R-03"]


def test_result_downstream_cli_renders_named_sections_in_human_output(
    tmp_path: Path, state_project_factory
) -> None:
    cwd = state_project_factory(tmp_path)
    _write_result_chain(cwd)

    result = runner.invoke(
        app,
        ["--cwd", str(cwd), "result", "downstream", "R-01"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    normalized_output = " ".join(result.output.split())
    assert "Result R-01" in normalized_output
    assert "Direct dependents" in normalized_output
    assert "Transitive dependents" in normalized_output
    assert "R-02" in normalized_output
    assert "R-03" in normalized_output


def test_result_downstream_cli_surfaces_missing_result_error_in_raw_output(
    tmp_path: Path, state_project_factory
) -> None:
    cwd = state_project_factory(tmp_path)
    state_path = cwd / "GPD" / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["intermediate_results"] = [
        {"id": "R-01", "equation": "A", "phase": "1", "depends_on": []},
    ]
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    result = runner.invoke(
        app,
        ["--raw", "--cwd", str(cwd), "result", "downstream", "R-missing"],
        catch_exceptions=False,
    )

    assert result.exit_code == 1
    assert json.loads(result.output) == {"error": 'Result "R-missing" not found'}


def test_result_downstream_cli_surfaces_missing_result_error_in_human_output(
    tmp_path: Path, state_project_factory
) -> None:
    cwd = state_project_factory(tmp_path)
    state_path = cwd / "GPD" / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["intermediate_results"] = [
        {"id": "R-01", "equation": "A", "phase": "1", "depends_on": []},
    ]
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    result = runner.invoke(
        app,
        ["--cwd", str(cwd), "result", "downstream", "R-missing"],
        catch_exceptions=False,
    )

    assert result.exit_code == 1
    assert 'Error: Result "R-missing" not found' in " ".join(result.output.split())
