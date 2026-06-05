"""CLI tests for gpd goal status/gate and gpd validate goal-contract."""

import json
from pathlib import Path

import tests.helpers.cli as cli_helpers
from gpd.cli import app

# The unified gpd CLI routes errors to stderr (and JSON error envelopes to
# stderr under --raw), so mirror the harness used by tests/core/test_cli.py:
# StableCliRunner plus raw_payload_from_result (which reads stdout or stderr).
runner = cli_helpers.StableCliRunner()
_raw_payload_from_result = cli_helpers.raw_payload_from_result

GOAL_CONTRACT = {
    "schema_version": 1,
    "statement": "Derive and verify the dispersion relation",
    "success_criteria": [
        {"id": "GC-1", "description": "main claim", "claim_ref": "goal-gc-1", "expected": "pass"}
    ],
    "budget_usd": 5.0,
    "max_phases": 6,
    "baseline_spent_usd": 0.0,
    "phases_completed": 0,
    "status": "active",
}


def _write_project_state(project_root: Path, goal_contract: dict | None) -> None:
    gpd_dir = project_root / "GPD"
    gpd_dir.mkdir(parents=True, exist_ok=True)
    state: dict = {}
    if goal_contract is not None:
        state["goal_contract"] = goal_contract
    (gpd_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")


def test_validate_goal_contract_accepts_valid_payload(tmp_path: Path) -> None:
    contract_file = tmp_path / "goal.json"
    contract_file.write_text(json.dumps(GOAL_CONTRACT), encoding="utf-8")
    result = runner.invoke(app, ["--raw", "validate", "goal-contract", str(contract_file)])
    assert result.exit_code == 0, result.output
    payload = _raw_payload_from_result(result)
    assert payload["valid"] is True
    assert payload["issues"] == []


def test_validate_goal_contract_reports_issues(tmp_path: Path) -> None:
    contract_file = tmp_path / "goal.json"
    contract_file.write_text(
        json.dumps({**GOAL_CONTRACT, "budget_usd": None, "max_phases": None}), encoding="utf-8"
    )
    result = runner.invoke(app, ["--raw", "validate", "goal-contract", str(contract_file)])
    assert result.exit_code != 0
    payload = _raw_payload_from_result(result)
    assert payload["valid"] is False
    assert any("max_phases" in issue for issue in payload["issues"])


def test_goal_status_errors_cleanly_without_goal_contract(tmp_path: Path) -> None:
    _write_project_state(tmp_path, goal_contract=None)
    result = runner.invoke(app, ["--raw", "--cwd", str(tmp_path), "goal", "status"])
    assert result.exit_code != 0
    combined = (result.output + result.stderr).lower()
    assert "goal" in combined
    assert "Traceback" not in result.output + result.stderr


def test_goal_gate_emits_machine_decision(tmp_path: Path) -> None:
    _write_project_state(tmp_path, goal_contract=GOAL_CONTRACT)
    result = runner.invoke(app, ["--raw", "--cwd", str(tmp_path), "goal", "gate"])
    assert result.exit_code == 0, result.output
    payload = _raw_payload_from_result(result)
    assert payload["budget_decision"] in ("continue", "wrap_up", "stop")
    assert payload["achieved"] is False  # no VERIFICATION.md evidence yet
    assert payload["max_phases"] == 6
    assert payload["criteria"][0]["outcome"] == "pending"


def test_goal_gate_fails_closed_without_enforceable_cap(tmp_path: Path) -> None:
    # No max_phases; cost telemetry is empty in a fresh tmp project -> no caps.
    _write_project_state(tmp_path, goal_contract={**GOAL_CONTRACT, "max_phases": None})
    result = runner.invoke(app, ["--raw", "--cwd", str(tmp_path), "goal", "gate"])
    assert result.exit_code != 0
    combined = (result.output + result.stderr).lower()
    assert "max-phases" in combined or "max_phases" in combined


def test_goal_gate_resolves_project_root_from_nested_directory(tmp_path: Path) -> None:
    # goal gate/status are project inspectors: like `gpd state load`, they must
    # walk up to the enclosing project root instead of reading the launch cwd.
    _write_project_state(tmp_path, goal_contract=GOAL_CONTRACT)
    # Root markers so ancestor walk-up can verify the project root.
    (tmp_path / "GPD" / "PROJECT.md").write_text("# Project\n", encoding="utf-8")
    (tmp_path / "GPD" / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
    nested = tmp_path / "analysis" / "notebooks"
    nested.mkdir(parents=True)
    result = runner.invoke(app, ["--raw", "--cwd", str(nested), "goal", "gate"])
    assert result.exit_code == 0, result.output + result.stderr
    payload = _raw_payload_from_result(result)
    assert payload["max_phases"] == 6
    assert payload["criteria"][0]["claim_ref"] == "goal-gc-1"
