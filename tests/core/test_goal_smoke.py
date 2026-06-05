"""End-to-end gate-plumbing smoke: toy project from goal start to achieved.

Simulates exactly what the goal workflow does between agent turns: seed the
contract, complete phases (verifier writes contract_results), increment the
counter, and shell the gate. No LLM, no network.
"""

import json
from pathlib import Path

import tests.helpers.cli as cli_helpers
from gpd.cli import app

# The unified gpd CLI routes --raw JSON (and error envelopes) to stderr, so use
# the same harness Task 4's CLI tests adopted: StableCliRunner plus
# raw_payload_from_result (which reads stdout or stderr).
runner = cli_helpers.StableCliRunner()
_raw_payload_from_result = cli_helpers.raw_payload_from_result

_VERIFICATION = """---
phase: {phase}
verified: 2026-06-04T12:00:00Z
status: passed
contract_results:
  claims:
    {claim_id}:
      status: passed
      summary: Claim independently verified.
---

# Verification Report
"""


def _seed_project(project_root: Path, *, max_phases: int) -> None:
    gpd_dir = project_root / "GPD"
    gpd_dir.mkdir(parents=True)
    contract = {
        "schema_version": 1,
        "statement": "Toy goal: verify two claims",
        "success_criteria": [
            {"id": "GC-1", "description": "first claim", "claim_ref": "goal-gc-1", "expected": "pass"},
            {"id": "GC-2", "description": "second claim", "claim_ref": "goal-gc-2", "expected": "pass"},
        ],
        "budget_usd": None,
        "max_phases": max_phases,
        "baseline_spent_usd": None,
        "phases_completed": 0,
        "status": "active",
    }
    (gpd_dir / "state.json").write_text(json.dumps({"goal_contract": contract}), encoding="utf-8")


def _complete_phase(project_root: Path, number: str, name: str, claim_id: str) -> None:
    phase_dir = project_root / "GPD" / "phases" / f"{number}-{name}"
    phase_dir.mkdir(parents=True)
    (phase_dir / f"{number}-VERIFICATION.md").write_text(
        _VERIFICATION.format(phase=f"{number}-{name}", claim_id=claim_id), encoding="utf-8"
    )
    # The workflow increments phases_completed after each verified phase.
    state_path = project_root / "GPD" / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["goal_contract"]["phases_completed"] += 1
    state_path.write_text(json.dumps(state), encoding="utf-8")


def _gate(project_root: Path) -> dict:
    result = runner.invoke(app, ["--raw", "--cwd", str(project_root), "goal", "gate"])
    assert result.exit_code == 0, result.output
    return _raw_payload_from_result(result)


def test_toy_goal_run_reaches_achieved_within_phase_cap(tmp_path: Path) -> None:
    _seed_project(tmp_path, max_phases=3)

    gate = _gate(tmp_path)
    assert gate["budget_decision"] == "continue"
    assert gate["achieved"] is False  # nothing verified yet

    _complete_phase(tmp_path, "01", "first", "goal-gc-1")
    gate = _gate(tmp_path)
    assert gate["achieved"] is False  # GC-2 still pending
    assert gate["budget_decision"] == "continue"

    _complete_phase(tmp_path, "02", "second", "goal-gc-2")
    gate = _gate(tmp_path)
    assert gate["achieved"] is True  # verifier-recorded claims, not self-claims
    assert {c["id"]: c["outcome"] for c in gate["criteria"]} == {"GC-1": "pass", "GC-2": "pass"}


def test_toy_goal_run_budget_stops_at_phase_cap(tmp_path: Path) -> None:
    _seed_project(tmp_path, max_phases=2)
    _complete_phase(tmp_path, "01", "first", "goal-gc-1")
    assert _gate(tmp_path)["budget_decision"] == "wrap_up"  # one final phase allowed
    _complete_phase(tmp_path, "02", "second", "unrelated-claim")
    gate = _gate(tmp_path)
    assert gate["budget_decision"] == "stop"
    assert gate["achieved"] is False  # GC-2 never verified; stop wins, no rubber stamp


def test_receipt_renders_for_humans(tmp_path: Path) -> None:
    _seed_project(tmp_path, max_phases=3)
    _complete_phase(tmp_path, "01", "first", "goal-gc-1")
    result = runner.invoke(app, ["--cwd", str(tmp_path), "goal", "status"])
    assert result.exit_code == 0, result.output
    assert "GC-1" in result.output
    assert "GC-2" in result.output
