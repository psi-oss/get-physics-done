"""Typed goal contract for gpd:goal runs.

The goal contract is a first-class ``ResearchState`` field (mirroring
``project_contract``), serialized in ``GPD/state.json``. It records the goal
statement, success criteria tied to plan-contract claim ids, the binding caps
(USD budget and/or phase count), and the run status.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

__all__ = [
    "GOAL_STATUSES",
    "GoalContract",
    "GoalCriterion",
    "validate_goal_contract_payload",
]

GOAL_STATUSES = ("active", "achieved", "budget_stopped", "blocked")


class GoalCriterion(BaseModel):
    """One success criterion, tied to a plan-contract claim id.

    The goal workflow requires phase plans to carry a contract claim with id
    ``claim_ref``; the verification machinery records its outcome in the phase
    VERIFICATION.md ``contract_results.claims`` frontmatter, which is the only
    evidence source the goal gate accepts.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    claim_ref: str = Field(min_length=1)
    expected: Literal["pass"] = "pass"


class GoalContract(BaseModel):
    """Schema for the ``goal_contract`` field of state.json."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    statement: str = Field(min_length=1)
    success_criteria: list[GoalCriterion] = Field(min_length=1)
    budget_usd: float | None = Field(default=None, gt=0)
    max_phases: int | None = Field(default=None, gt=0)
    baseline_spent_usd: float | None = Field(default=None, ge=0)
    phases_completed: int = Field(default=0, ge=0)
    # strict_criteria=True (default): only per-claim_ref verified outcomes can
    # achieve the goal. False: when every completed phase's verification passed
    # overall, still-pending criteria count as pass (demo-robustness fallback
    # for claim-id threading flakiness; failed criteria still block).
    strict_criteria: bool = True
    status: Literal["active", "achieved", "budget_stopped", "blocked"] = "active"
    created: str | None = None
    updated: str | None = None


def validate_goal_contract_payload(payload: object) -> list[str]:
    """Validate a goal-contract payload; return stable issue strings."""
    if not isinstance(payload, dict):
        return ["goal_contract: payload must be a JSON object"]
    try:
        contract = GoalContract.model_validate(payload)
    except ValidationError as exc:
        issues: list[str] = []
        for error in exc.errors():
            location = ".".join(str(part) for part in error.get("loc", ())) or "goal_contract"
            issues.append(f"goal_contract.{location}: {error.get('msg', 'invalid value')}")
        return issues
    issues = []
    if contract.budget_usd is None and contract.max_phases is None:
        issues.append(
            "goal_contract: at least one cap is required (budget_usd or max_phases) — goal runs never run uncapped"
        )
    seen_ids: set[str] = set()
    seen_refs: set[str] = set()
    for criterion in contract.success_criteria:
        if criterion.id in seen_ids:
            issues.append(f"goal_contract.success_criteria: duplicate criterion id {criterion.id}")
        if criterion.claim_ref in seen_refs:
            issues.append(
                f"goal_contract.success_criteria: duplicate claim_ref {criterion.claim_ref}"
            )
        seen_ids.add(criterion.id)
        seen_refs.add(criterion.claim_ref)
    return issues
