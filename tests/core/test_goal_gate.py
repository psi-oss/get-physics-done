"""Tests for gpd:goal dual-cap gate and criteria evaluation decisions."""

import pytest

from gpd.core.goal_contract import GoalContract
from gpd.core.goal_gate import (
    GoalGateError,
    budget_gate_decision,
    evaluate_goal_criteria,
    goal_gate_summary,
)


def _contract(**overrides) -> GoalContract:
    payload = {
        "statement": "Derive and verify the dispersion relation",
        "success_criteria": [
            {"id": "GC-1", "description": "main claim verified", "claim_ref": "goal-gc-1"},
            {"id": "GC-2", "description": "limit claim verified", "claim_ref": "goal-gc-2"},
        ],
        "budget_usd": 5.0,
        "max_phases": 6,
        "baseline_spent_usd": 10.0,
        "phases_completed": 0,
    }
    payload.update(overrides)
    return GoalContract.model_validate(payload)


# ── USD cap ──────────────────────────────────────────────────────────────────

def test_usd_continue_when_spend_is_low() -> None:
    assert budget_gate_decision(_contract(), spent_usd=11.0) == "continue"


def test_usd_wrap_up_near_budget() -> None:
    # baseline 10 + budget 5 => run spend 4.5/5.0 = 90% >= default 85%
    assert budget_gate_decision(_contract(), spent_usd=14.5) == "wrap_up"


def test_usd_stop_at_or_over_budget() -> None:
    assert budget_gate_decision(_contract(), spent_usd=15.0) == "stop"
    assert budget_gate_decision(_contract(), spent_usd=20.0) == "stop"


def test_usd_ignores_spend_before_baseline() -> None:
    assert budget_gate_decision(_contract(), spent_usd=3.0) == "continue"


# ── Phase cap ────────────────────────────────────────────────────────────────

def test_phase_cap_stops_at_max_phases() -> None:
    contract = _contract(phases_completed=6)
    assert budget_gate_decision(contract, spent_usd=11.0) == "stop"


def test_phase_cap_wraps_up_on_last_phase() -> None:
    contract = _contract(phases_completed=5)
    assert budget_gate_decision(contract, spent_usd=11.0) == "wrap_up"


def test_strictest_decision_wins() -> None:
    # USD says stop, phases say continue -> stop
    assert budget_gate_decision(_contract(phases_completed=1), spent_usd=15.0) == "stop"
    # USD says continue, phases say wrap_up -> wrap_up
    assert budget_gate_decision(_contract(phases_completed=5), spent_usd=11.0) == "wrap_up"


# ── Telemetry availability ───────────────────────────────────────────────────

def test_phases_only_contract_ignores_unavailable_usd() -> None:
    contract = _contract(budget_usd=None, baseline_spent_usd=None)
    assert budget_gate_decision(contract, spent_usd=None) == "continue"


def test_usd_cap_with_unavailable_spend_falls_back_to_phase_cap() -> None:
    # budget_usd set but telemetry unavailable mid-run: phase cap still governs
    contract = _contract(phases_completed=6)
    assert budget_gate_decision(contract, spent_usd=None) == "stop"


def test_no_enforceable_cap_raises_fail_closed() -> None:
    contract = _contract(max_phases=None)
    with pytest.raises(GoalGateError):
        budget_gate_decision(contract, spent_usd=None)


# ── Criteria evaluation ──────────────────────────────────────────────────────

def test_criteria_all_passed_means_achieved() -> None:
    result = evaluate_goal_criteria(
        _contract(), claim_outcomes={"goal-gc-1": "passed", "goal-gc-2": "passed"}
    )
    assert result.achieved is True
    assert {c.id: c.outcome for c in result.criteria} == {"GC-1": "pass", "GC-2": "pass"}


def test_criteria_missing_claim_is_pending_not_achieved() -> None:
    result = evaluate_goal_criteria(_contract(), claim_outcomes={"goal-gc-1": "passed"})
    assert result.achieved is False
    assert {c.id: c.outcome for c in result.criteria} == {"GC-1": "pass", "GC-2": "pending"}


def test_criteria_failed_or_blocked_claim_is_fail() -> None:
    result = evaluate_goal_criteria(
        _contract(), claim_outcomes={"goal-gc-1": "failed", "goal-gc-2": "blocked"}
    )
    assert result.achieved is False
    assert {c.id: c.outcome for c in result.criteria} == {"GC-1": "fail", "GC-2": "fail"}


def test_criteria_partial_or_not_attempted_is_pending() -> None:
    result = evaluate_goal_criteria(
        _contract(), claim_outcomes={"goal-gc-1": "partial", "goal-gc-2": "not_attempted"}
    )
    assert result.achieved is False
    assert {c.id: c.outcome for c in result.criteria} == {"GC-1": "pending", "GC-2": "pending"}


# ── Non-strict fallback (demo robustness for claim-id threading) ─────────────

def test_non_strict_pending_criteria_pass_when_all_phases_passed() -> None:
    contract = _contract(strict_criteria=False, phases_completed=2)
    result = evaluate_goal_criteria(
        contract, claim_outcomes={"goal-gc-1": "passed"}, all_phases_passed=True
    )
    assert result.achieved is True
    assert {c.id: c.outcome for c in result.criteria} == {"GC-1": "pass", "GC-2": "pass"}


def test_non_strict_failed_criterion_still_blocks() -> None:
    contract = _contract(strict_criteria=False, phases_completed=2)
    result = evaluate_goal_criteria(
        contract, claim_outcomes={"goal-gc-1": "failed"}, all_phases_passed=True
    )
    assert result.achieved is False
    assert {c.id: c.outcome for c in result.criteria}["GC-1"] == "fail"


def test_non_strict_requires_completed_phases_and_all_passed() -> None:
    contract = _contract(strict_criteria=False, phases_completed=0)
    result = evaluate_goal_criteria(contract, claim_outcomes={}, all_phases_passed=True)
    assert result.achieved is False
    strict = _contract(phases_completed=2)  # strict default ignores the fallback
    result = evaluate_goal_criteria(strict, claim_outcomes={}, all_phases_passed=True)
    assert result.achieved is False


# ── Combined summary ─────────────────────────────────────────────────────────

def test_goal_gate_summary_combines_caps_and_criteria() -> None:
    summary = goal_gate_summary(
        _contract(phases_completed=2),
        spent_usd=11.0,
        claim_outcomes={"goal-gc-1": "passed", "goal-gc-2": "passed"},
    )
    assert summary.budget_decision == "continue"
    assert summary.achieved is True
    assert summary.run_spent_usd == 1.0
    assert summary.remaining_usd == 4.0
    assert summary.phases_completed == 2
    assert summary.max_phases == 6
    assert summary.usd_cap_enforceable is True


def test_goal_gate_summary_reports_unavailable_usd() -> None:
    contract = _contract(budget_usd=None, baseline_spent_usd=None, phases_completed=1)
    summary = goal_gate_summary(contract, spent_usd=None, claim_outcomes={})
    assert summary.budget_decision == "continue"
    assert summary.run_spent_usd is None
    assert summary.remaining_usd is None
    assert summary.usd_cap_enforceable is False
