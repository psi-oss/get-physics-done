from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from gpd.cli import app

runner = CliRunner()


def test_result_search_cli_matches_transitive_depends_on(tmp_path: Path, state_project_factory) -> None:
    cwd = state_project_factory(tmp_path)
    state_path = cwd / "GPD" / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["intermediate_results"] = [
        {"id": "R-01", "equation": "A", "phase": "1", "depends_on": []},
        {"id": "R-02", "equation": "B", "phase": "2", "depends_on": ["R-01"]},
        {"id": "R-03", "equation": "C", "phase": "3", "depends_on": ["R-02"]},
    ]
    state_path.write_text(json.dumps(state), encoding="utf-8")

    result = runner.invoke(
        app,
        ["--raw", "--cwd", str(cwd), "result", "search", "--depends-on", "r 01"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert [entry["id"] for entry in payload["matches"]] == ["R-02", "R-03"]
    assert payload["total"] == 2
