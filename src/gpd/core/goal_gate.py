"""Dual-cap gate and goal-criteria evaluation for gpd:goal runs.

Pure decision logic: no I/O. Callers (the ``gpd goal`` CLI surface) supply the
current project-scope spend (``None`` when cost telemetry is unavailable) and
the aggregated plan-contract claim outcomes; these functions return decisions.

Caps:
- USD cap: binds when ``budget_usd`` is set AND a spend figure is available.
- Phase cap: binds whenever ``max_phases`` is set.
- The strictest decision wins (stop > wrap_up > continue).
- If neither cap is enforceable, ``GoalGateError`` is raised — goal runs fail
  closed rather than running uncapped.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from gpd.core.errors import GPDError
from gpd.core.goal_contract import GoalContract

__all__ = [
    "DEFAULT_NEAR_BUDGET_FRACTION",
    "BudgetDecision",
    "CriterionOutcome",
    "GoalCriteriaResult",
    "GoalGateError",
    "GoalGateSummary",
    "budget_gate_decision",
    "evaluate_goal_criteria",
    "goal_gate_summary",
]

DEFAULT_NEAR_BUDGET_FRACTION = 0.85

BudgetDecision = Literal["continue", "wrap_up", "stop"]

_DECISION_SEVERITY = {"continue": 0, "wrap_up": 1, "stop": 2}

# VERIFICATION.md contract_results.claims statuses -> criterion outcomes.
_CLAIM_STATUS_TO_OUTCOME = {
    "passed": "pass",
    "failed": "fail",
    "blocked": "fail",
    "partial": "pending",
    "not_attempted": "pending",
}


class GoalGateError(GPDError, ValueError):
    """Raised when no cap is enforceable — goal runs never run uncapped."""


class CriterionOutcome(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    claim_ref: str
    outcome: Literal["pass", "fail", "pending"]


class GoalCriteriaResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    achieved: bool
    criteria: list[CriterionOutcome] = Field(default_factory=list)


class GoalGateSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    budget_decision: BudgetDecision
    achieved: bool
    budget_usd: float | None
    run_spent_usd: float | None
    remaining_usd: float | None
    usd_cap_enforceable: bool
    max_phases: int | None
    phases_completed: int
    criteria: list[CriterionOutcome] = Field(default_factory=list)


def _run_spent_usd(contract: GoalContract, spent_usd: float | None) -> float | None:
    """Spend attributable to this goal run (project spend minus baseline)."""
    if spent_usd is None:
        return None
    baseline = contract.baseline_spent_usd or 0.0
    return round(max(0.0, spent_usd - baseline), 6)


def _usd_decision(
    contract: GoalContract,
    spent_usd: float | None,
    near_fraction: float,
) -> BudgetDecision | None:
    """USD cap decision, or None when the cap is not enforceable."""
    if contract.budget_usd is None:
        return None
    run_spent = _run_spent_usd(contract, spent_usd)
    if run_spent is None:
        return None
    if run_spent >= contract.budget_usd:
        return "stop"
    if run_spent >= contract.budget_usd * near_fraction:
        return "wrap_up"
    return "continue"


def _phase_decision(contract: GoalContract) -> BudgetDecision | None:
    """Phase cap decision, or None when no phase cap is set.

    ``max_phases = N`` permits exactly N phases: ``wrap_up`` at N-1 completed
    means "execute exactly one final consolidation phase", after which the
    counter reaches N and the gate stops.
    """
    if contract.max_phases is None:
        return None
    if contract.phases_completed >= contract.max_phases:
        return "stop"
    if contract.phases_completed == contract.max_phases - 1:
        return "wrap_up"
    return "continue"


def budget_gate_decision(
    contract: GoalContract,
    *,
    spent_usd: float | None,
    near_fraction: float = DEFAULT_NEAR_BUDGET_FRACTION,
) -> BudgetDecision:
    """Decide whether a goal run may continue, must wrap up, or must stop.

    The strictest enforceable cap wins. Raises :class:`GoalGateError` when
    neither cap is enforceable (fail closed).
    """
    decisions = [
        decision
        for decision in (
            _usd_decision(contract, spent_usd, near_fraction),
            _phase_decision(contract),
        )
        if decision is not None
    ]
    if not decisions:
        raise GoalGateError(
            "No enforceable cap: cost telemetry is unavailable and no max_phases cap is set. "
            "Set --max-phases to run this goal."
        )
    return max(decisions, key=_DECISION_SEVERITY.__getitem__)


def evaluate_goal_criteria(
    contract: GoalContract,
    *,
    claim_outcomes: dict[str, str],
    all_phases_passed: bool = False,
) -> GoalCriteriaResult:
    """Map aggregated plan-contract claim statuses onto the success criteria.

    ``claim_outcomes`` maps claim id -> VERIFICATION.md contract_results claim
    status (``passed``/``partial``/``failed``/``blocked``/``not_attempted``).
    Criteria whose claim id is absent are ``pending``. The goal is achieved
    only when every criterion's outcome is ``pass``.

    Non-strict fallback: when ``contract.strict_criteria`` is False, at least
    one phase has completed, and ``all_phases_passed`` is True (every phase
    verification passed overall), ``pending`` criteria are upgraded to
    ``pass``. ``fail`` outcomes always block, in both modes.
    """
    use_fallback = (
        not contract.strict_criteria and all_phases_passed and contract.phases_completed >= 1
    )
    outcomes: list[CriterionOutcome] = []
    for criterion in contract.success_criteria:
        status = claim_outcomes.get(criterion.claim_ref)
        outcome = _CLAIM_STATUS_TO_OUTCOME.get(status or "", "pending")
        if outcome == "pending" and use_fallback:
            outcome = "pass"
        outcomes.append(
            CriterionOutcome(id=criterion.id, claim_ref=criterion.claim_ref, outcome=outcome)
        )
    achieved = bool(outcomes) and all(c.outcome == "pass" for c in outcomes)
    return GoalCriteriaResult(achieved=achieved, criteria=outcomes)


def goal_gate_summary(
    contract: GoalContract,
    *,
    spent_usd: float | None,
    claim_outcomes: dict[str, str],
    all_phases_passed: bool = False,
    near_fraction: float = DEFAULT_NEAR_BUDGET_FRACTION,
) -> GoalGateSummary:
    """Combined gate verdict used by ``gpd goal gate`` and ``gpd goal status``."""
    run_spent = _run_spent_usd(contract, spent_usd)
    usd_enforceable = contract.budget_usd is not None and run_spent is not None
    remaining: float | None = None
    if usd_enforceable:
        remaining = round(max(0.0, contract.budget_usd - run_spent), 6)
    criteria_result = evaluate_goal_criteria(
        contract, claim_outcomes=claim_outcomes, all_phases_passed=all_phases_passed
    )
    return GoalGateSummary(
        budget_decision=budget_gate_decision(
            contract, spent_usd=spent_usd, near_fraction=near_fraction
        ),
        achieved=criteria_result.achieved,
        budget_usd=contract.budget_usd,
        run_spent_usd=run_spent,
        remaining_usd=remaining,
        usd_cap_enforceable=usd_enforceable,
        max_phases=contract.max_phases,
        phases_completed=contract.phases_completed,
        criteria=criteria_result.criteria,
    )
