# `gpd:goal` Command Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `gpd:goal "<statement>" [--budget-usd X] [--max-phases N]` — a goal-directed autonomous run under a binding dual cap (USD where cost telemetry exists, phase count everywhere), with completion gated on verified plan-contract claims, plus a `gpd goal status` receipt.

**Architecture:** Pure-Python core modules hold the typed goal contract (`goal_contract.py`), the dual-cap gate + criteria decisions (`goal_gate.py`), and the VERIFICATION.md claim-outcome aggregator (`goal_evidence.py`). A typed `goal_contract` field is added to `ResearchState` (mirroring `project_contract`). A `gpd goal` Typer sub-app exposes `status` and `gate`; `gpd validate goal-contract` follows the JSON+pydantic validator pattern of `review-ledger`/`referee-decision`. A new `goal.md` command descriptor delegates to its own `workflows/goal/goal-bootstrap.md` (the `autonomous` workflow and its stage manifest are NOT modified — its topology tests forbid that). No staged-init registration in v1.

**Tech Stack:** Python 3.11+, pydantic v2, typer, pytest (`-n 0` for targeted runs). Spec: `docs/superpowers/specs/2026-06-04-goal-command-design.md` (amended revision).

**Verified integration facts (do not re-derive):**
- `ResearchState` (`src/gpd/core/state.py:481`) has `model_config = {"extra": "allow"}` and the precedent field `project_contract: ResearchContract | None = None`.
- Project spend: `from gpd.core.costs import build_cost_summary`; `build_cost_summary(cwd, last_sessions=0).project.cost_usd` is `float | None`; `cost_status` ∈ {`unavailable`, `measured`, `estimated`, `mixed`} (costs.py:150-180, 823-832). Under Claude Code the ledger is empty → `cost_usd is None`.
- VERIFICATION.md frontmatter records per-claim outcomes at `contract_results.claims.<id>.status` with statuses `passed|partial|failed|blocked|not_attempted` (see `src/gpd/specs/templates/contract-results-schema.md` and fixture `tests/fixtures/stage4/verification_with_contract_results.md`).
- Public frontmatter parser: `from gpd.core.frontmatter import extract_frontmatter` → `(meta: dict, body: str)` (frontmatter.py:141).
- CLI conventions: lazy imports inside command bodies, `_get_cwd()`, `_raw` + `_output(payload)`, `_error(str)`; `cost` command at `src/gpd/cli.py:4459`; `validate_app` JSON validators at cli.py:9924+ (`review-ledger`, `referee-decision`).
- Workflow `.md` files under `src/gpd/specs/workflows/` install automatically (`install_utils.py:2812-2844`, `GPD_CONTENT_DIRS`); no manifest registration required for v1 (no staged init).
- Phase layout: `GPD/phases/NN-name/NN-VERIFICATION.md` (per ProjectLayout).

**Minimal demoable slice and demo floor:** Tasks 1-4 + the Task 6 smoke test
are the minimal demoable slice (gate plumbing provably reaches `achieved` and
`budget_stopped` with a real receipt); Task 5 makes it installable as a runtime
command. The cost ledger on the dev machine is empty (`~/.gpd/cost/usage.jsonl`
absent — codex telemetry has never recorded there), so treat the USD receipt as
**unverified stretch**: the phase-cap receipt is the demo floor, and the USD
path must be smoke-checked on codex before being promised on stage.

**Phase-cap semantics (intentional):** `--max-phases N` permits exactly N
phases. The gate returns `wrap_up` when `phases_completed == N - 1`, meaning
"execute exactly one final consolidation phase (verify, close threads — no new
exploratory work), after which the gate stops." It returns `stop` at
`phases_completed >= N`.

**Working rules for every task:**
- Run commands from the repo root (the worktree).
- Inside Claude Code, always run pytest as `env -u FORCE_COLOR uv run pytest ...` — the harness injects `FORCE_COLOR=3`, which breaks rich-output string assertions.
- The pre-commit hook runs ruff `--fix --unsafe-fixes` on staged Python files; if it modifies files, `git add` and commit again.
- Do not bump package versions (repo guardrail). Do not modify anything under `src/gpd/specs/workflows/autonomous/` or `autonomous-stage-manifest.json`.

---

## Task 1: Goal contract models and state field

**Files:**
- Create: `src/gpd/core/goal_contract.py`
- Modify: `src/gpd/core/state.py` (one field on `ResearchState`, after `contract_alignment` around line 503; one import)
- Test: `tests/core/test_goal_contract.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/core/test_goal_contract.py`:

```python
"""Tests for the gpd:goal goal-contract models and validation."""

from gpd.core.goal_contract import (
    GoalContract,
    validate_goal_contract_payload,
)


def _valid_payload(**overrides) -> dict:
    payload = {
        "schema_version": 1,
        "statement": "Derive the dispersion relation and verify the long-wavelength limit",
        "success_criteria": [
            {
                "id": "GC-1",
                "description": "Dispersion relation claim verified",
                "claim_ref": "goal-gc-1",
                "expected": "pass",
            }
        ],
        "budget_usd": 5.0,
        "max_phases": 6,
        "baseline_spent_usd": 0.0,
        "phases_completed": 0,
        "strict_criteria": True,
        "status": "active",
    }
    payload.update(overrides)
    return payload


def test_goal_contract_parses_valid_payload() -> None:
    contract = GoalContract.model_validate(_valid_payload())
    assert contract.statement.startswith("Derive")
    assert contract.success_criteria[0].claim_ref == "goal-gc-1"
    assert contract.status == "active"


def test_goal_contract_allows_usd_only_and_phases_only_caps() -> None:
    assert validate_goal_contract_payload(_valid_payload(max_phases=None)) == []
    assert validate_goal_contract_payload(_valid_payload(budget_usd=None, baseline_spent_usd=None)) == []


def test_goal_contract_requires_at_least_one_cap() -> None:
    issues = validate_goal_contract_payload(
        _valid_payload(budget_usd=None, max_phases=None, baseline_spent_usd=None)
    )
    assert any("budget_usd" in issue and "max_phases" in issue for issue in issues)


def test_goal_contract_rejects_unknown_status() -> None:
    issues = validate_goal_contract_payload(_valid_payload(status="victorious"))
    assert any("status" in issue for issue in issues)


def test_goal_contract_rejects_non_positive_caps() -> None:
    assert any("budget_usd" in i for i in validate_goal_contract_payload(_valid_payload(budget_usd=0)))
    assert any("max_phases" in i for i in validate_goal_contract_payload(_valid_payload(max_phases=0)))


def test_goal_contract_requires_at_least_one_criterion() -> None:
    issues = validate_goal_contract_payload(_valid_payload(success_criteria=[]))
    assert any("success_criteria" in issue for issue in issues)


def test_goal_contract_criterion_ids_and_claim_refs_must_be_unique() -> None:
    criterion = _valid_payload()["success_criteria"][0]
    issues = validate_goal_contract_payload(
        _valid_payload(success_criteria=[criterion, dict(criterion)])
    )
    assert any("GC-1" in issue for issue in issues)


def test_validate_returns_no_issues_for_valid_payload() -> None:
    assert validate_goal_contract_payload(_valid_payload()) == []


def test_validate_rejects_non_mapping_payload() -> None:
    assert validate_goal_contract_payload(["not", "a", "dict"])


def test_research_state_round_trips_goal_contract() -> None:
    from gpd.core.state import ResearchState

    state = ResearchState.model_validate({"goal_contract": _valid_payload()})
    assert state.goal_contract is not None
    assert state.goal_contract.budget_usd == 5.0
    dumped = state.model_dump(mode="json")
    assert dumped["goal_contract"]["statement"].startswith("Derive")


def test_research_state_defaults_to_no_goal_contract() -> None:
    from gpd.core.state import ResearchState

    assert ResearchState().goal_contract is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `env -u FORCE_COLOR uv run pytest tests/core/test_goal_contract.py -n 0 -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'gpd.core.goal_contract'`

- [ ] **Step 3: Write the implementation**

Create `src/gpd/core/goal_contract.py`:

```python
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
```

Modify `src/gpd/core/state.py` — in `ResearchState`, directly after the
`contract_alignment` field, add:

```python
    goal_contract: GoalContract | None = None
```

and add the import next to the other `gpd.core.*` imports at the top:

```python
from gpd.core.goal_contract import GoalContract
```

(`goal_contract.py` imports nothing from `state.py`, so no import cycle.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `env -u FORCE_COLOR uv run pytest tests/core/test_goal_contract.py -n 0 -v`
Expected: 11 passed

- [ ] **Step 5: Run state regression tests**

Run: `env -u FORCE_COLOR uv run pytest tests/core -n 0 -q -k "state"`
Expected: all pass — the new optional field must not break existing state
handling, sync, or salvage logic.

- [ ] **Step 6: Commit**

```bash
git add src/gpd/core/goal_contract.py src/gpd/core/state.py tests/core/test_goal_contract.py
git commit -m "feat: add typed goal contract and ResearchState.goal_contract field"
```

---

## Task 2: Dual-cap budget gate and criteria evaluation

**Files:**
- Create: `src/gpd/core/goal_gate.py`
- Test: `tests/core/test_goal_gate.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/core/test_goal_gate.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `env -u FORCE_COLOR uv run pytest tests/core/test_goal_gate.py -n 0 -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'gpd.core.goal_gate'`

- [ ] **Step 3: Write the implementation**

Create `src/gpd/core/goal_gate.py`:

```python
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
```

Note: check `src/gpd/core/errors.py` for the actual base error class name; if
it is not `GPDError`, use the module's established base (the goal is a
catchable, GPD-branded error type consistent with `FrontmatterParseError`'s
base in `frontmatter.py:110`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `env -u FORCE_COLOR uv run pytest tests/core/test_goal_gate.py tests/core/test_goal_contract.py -n 0 -v`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add src/gpd/core/goal_gate.py tests/core/test_goal_gate.py
git commit -m "feat: add dual-cap goal gate and criteria evaluation logic"
```

---

## Task 3: Claim-outcome aggregation from VERIFICATION.md files

**Files:**
- Create: `src/gpd/core/goal_evidence.py`
- Test: `tests/core/test_goal_evidence.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/core/test_goal_evidence.py`:

```python
"""Tests for aggregating plan-contract claim outcomes for the goal gate."""

from pathlib import Path

from gpd.core.goal_evidence import collect_claim_outcomes

_VERIFICATION_TEMPLATE = """---
phase: {phase}
verified: 2026-06-04T12:00:00Z
status: passed
contract_results:
  claims:
    {claim_id}:
      status: {claim_status}
      summary: Claim checked by verifier.
---

# Verification Report
"""


def _write_verification(project_root: Path, phase_dir: str, claim_id: str, claim_status: str) -> None:
    phase_path = project_root / "GPD" / "phases" / phase_dir
    phase_path.mkdir(parents=True, exist_ok=True)
    number = phase_dir.split("-", 1)[0]
    (phase_path / f"{number}-VERIFICATION.md").write_text(
        _VERIFICATION_TEMPLATE.format(phase=phase_dir, claim_id=claim_id, claim_status=claim_status),
        encoding="utf-8",
    )


def test_collects_claim_statuses_across_phases(tmp_path: Path) -> None:
    _write_verification(tmp_path, "01-derivation", "goal-gc-1", "passed")
    _write_verification(tmp_path, "02-limits", "goal-gc-2", "failed")
    outcomes = collect_claim_outcomes(tmp_path)
    assert outcomes == {"goal-gc-1": "passed", "goal-gc-2": "failed"}


def test_later_phase_supersedes_earlier_status_for_same_claim(tmp_path: Path) -> None:
    _write_verification(tmp_path, "01-derivation", "goal-gc-1", "failed")
    _write_verification(tmp_path, "02-revision", "goal-gc-1", "passed")
    outcomes = collect_claim_outcomes(tmp_path)
    assert outcomes == {"goal-gc-1": "passed"}


def test_returns_empty_for_missing_phases_dir(tmp_path: Path) -> None:
    assert collect_claim_outcomes(tmp_path) == {}


def test_ignores_verification_files_without_contract_results(tmp_path: Path) -> None:
    phase_path = tmp_path / "GPD" / "phases" / "01-derivation"
    phase_path.mkdir(parents=True)
    (phase_path / "01-VERIFICATION.md").write_text(
        "---\nphase: 01-derivation\nstatus: passed\n---\n\n# Report\n", encoding="utf-8"
    )
    assert collect_claim_outcomes(tmp_path) == {}


def test_ignores_malformed_frontmatter_instead_of_raising(tmp_path: Path) -> None:
    phase_path = tmp_path / "GPD" / "phases" / "01-derivation"
    phase_path.mkdir(parents=True)
    (phase_path / "01-VERIFICATION.md").write_text(
        "---\n: not yaml :\n---\n", encoding="utf-8"
    )
    assert collect_claim_outcomes(tmp_path) == {}


def test_collects_phase_statuses(tmp_path: Path) -> None:
    from gpd.core.goal_evidence import collect_phase_statuses

    _write_verification(tmp_path, "01-derivation", "goal-gc-1", "passed")
    _write_verification(tmp_path, "02-limits", "goal-gc-2", "failed")
    statuses = collect_phase_statuses(tmp_path)
    # top-level frontmatter status of each VERIFICATION.md (template uses "passed")
    assert statuses == {"01-derivation": "passed", "02-limits": "passed"}


def test_phase_statuses_empty_for_missing_phases_dir(tmp_path: Path) -> None:
    from gpd.core.goal_evidence import collect_phase_statuses

    assert collect_phase_statuses(tmp_path) == {}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `env -u FORCE_COLOR uv run pytest tests/core/test_goal_evidence.py -n 0 -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'gpd.core.goal_evidence'`

- [ ] **Step 3: Write the implementation**

Create `src/gpd/core/goal_evidence.py`:

```python
"""Aggregate plan-contract claim outcomes from phase VERIFICATION.md files.

The goal gate's only accepted evidence source: ``contract_results.claims``
frontmatter written by the verification machinery. Phases are scanned in
sorted order, so a later phase's status for the same claim id supersedes an
earlier one (revision phases can repair a previously failed claim).
"""

from __future__ import annotations

from pathlib import Path

from gpd.core.frontmatter import extract_frontmatter

__all__ = ["collect_claim_outcomes", "collect_phase_statuses"]


def _iter_verification_meta(project_root: Path):
    """Yield (phase_dir_name, frontmatter_meta) for each parseable VERIFICATION.md."""
    phases_dir = project_root / "GPD" / "phases"
    if not phases_dir.is_dir():
        return
    for verification_path in sorted(phases_dir.glob("*/*-VERIFICATION.md")):
        try:
            meta, _body = extract_frontmatter(verification_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(meta, dict):
            yield verification_path.parent.name, meta


def collect_claim_outcomes(project_root: Path) -> dict[str, str]:
    """Map claim id -> latest contract_results claim status across phases."""
    outcomes: dict[str, str] = {}
    for _phase_name, meta in _iter_verification_meta(project_root):
        contract_results = meta.get("contract_results")
        if not isinstance(contract_results, dict):
            continue
        claims = contract_results.get("claims")
        if not isinstance(claims, dict):
            continue
        for claim_id, claim_payload in claims.items():
            if not isinstance(claim_payload, dict):
                continue
            status = claim_payload.get("status")
            if isinstance(status, str) and status:
                outcomes[str(claim_id)] = status
    return outcomes


def collect_phase_statuses(project_root: Path) -> dict[str, str]:
    """Map phase directory name -> top-level VERIFICATION.md frontmatter status."""
    statuses: dict[str, str] = {}
    for phase_name, meta in _iter_verification_meta(project_root):
        status = meta.get("status")
        if isinstance(status, str) and status:
            statuses[phase_name] = status
    return statuses
```

Note: if `extract_frontmatter` raises a different exception type for malformed
YAML (check `FrontmatterParseError` in `gpd/core/frontmatter.py:110`), include
it in the `except` tuple. Check the actual phase-directory layout constant in
`gpd.core.constants` / ProjectLayout — if VERIFICATION files are named
differently (e.g. `NN-VERIFICATION.md` vs `VERIFICATION.md`), match the real
glob used by existing phase scanners (search for `VERIFICATION.md` globs in
`src/gpd/core/`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `env -u FORCE_COLOR uv run pytest tests/core/test_goal_evidence.py -n 0 -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add src/gpd/core/goal_evidence.py tests/core/test_goal_evidence.py
git commit -m "feat: aggregate plan-contract claim outcomes for the goal gate"
```

---

## Task 4: CLI surface — `gpd goal status`, `gpd goal gate`, `gpd validate goal-contract`

**Files:**
- Modify: `src/gpd/cli.py` (new `goal_app` sub-app near the `stage_app` block around line 4477; new `@validate_app.command("goal-contract")` next to the JSON validators around line 9924)
- Test: `tests/core/test_cli_goal.py`
- Regenerate: public surface contract, help surface, repo graph contract

**Pattern notes (verified):** lazy imports in command bodies; `_get_cwd()`;
`_raw` + `_output(payload)`; `_error(str)`. Mirror `cost` (cli.py:4459) and the
JSON validators `review-ledger`/`referee-decision` (cli.py:9924+) — copy their
exit-code and payload conventions exactly, including how they load a JSON
document from a path-or-stdin argument (`_load_json_document_or_error` or the
local equivalent — read those validators first and reuse their helper).

- [ ] **Step 1: Write the failing tests**

Before writing, read the top 80 lines of `tests/core/test_cli.py` and reuse its
runner harness (CliRunner instance or invoke helper) and any project-scaffold
fixture. Create `tests/core/test_cli_goal.py`:

```python
"""CLI tests for gpd goal status/gate and gpd validate goal-contract."""

import json
from pathlib import Path

# Adapt these two imports to the actual harness in tests/core/test_cli.py
# (it defines a CliRunner and/or an invoke helper for the gpd typer app).
from typer.testing import CliRunner

from gpd.cli import app

runner = CliRunner()

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
    payload = json.loads(result.output)
    assert payload["valid"] is True
    assert payload["issues"] == []


def test_validate_goal_contract_reports_issues(tmp_path: Path) -> None:
    contract_file = tmp_path / "goal.json"
    contract_file.write_text(
        json.dumps({**GOAL_CONTRACT, "budget_usd": None, "max_phases": None}), encoding="utf-8"
    )
    result = runner.invoke(app, ["--raw", "validate", "goal-contract", str(contract_file)])
    assert result.exit_code != 0
    payload = json.loads(result.output)
    assert payload["valid"] is False
    assert any("max_phases" in issue for issue in payload["issues"])


def test_goal_status_errors_cleanly_without_goal_contract(tmp_path: Path) -> None:
    _write_project_state(tmp_path, goal_contract=None)
    result = runner.invoke(app, ["--raw", "--cwd", str(tmp_path), "goal", "status"])
    assert result.exit_code != 0
    assert "goal" in result.output.lower()
    assert "Traceback" not in result.output


def test_goal_gate_emits_machine_decision(tmp_path: Path) -> None:
    _write_project_state(tmp_path, goal_contract=GOAL_CONTRACT)
    result = runner.invoke(app, ["--raw", "--cwd", str(tmp_path), "goal", "gate"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["budget_decision"] in ("continue", "wrap_up", "stop")
    assert payload["achieved"] is False  # no VERIFICATION.md evidence yet
    assert payload["max_phases"] == 6
    assert payload["criteria"][0]["outcome"] == "pending"


def test_goal_gate_fails_closed_without_enforceable_cap(tmp_path: Path) -> None:
    # No max_phases; cost telemetry is empty in a fresh tmp project -> no caps.
    _write_project_state(tmp_path, goal_contract={**GOAL_CONTRACT, "max_phases": None})
    result = runner.invoke(app, ["--raw", "--cwd", str(tmp_path), "goal", "gate"])
    assert result.exit_code != 0
    assert "max-phases" in result.output.lower() or "max_phases" in result.output.lower()
```

Adjustment note: if `state.json` written as `{}`/partial by the test scaffolds
trips state-integrity checks, look at how existing CLI tests scaffold a minimal
valid project (search `state.json` in `tests/core/test_cli.py` and reuse that
helper) — the tests above must seed whatever minimal valid state the loader
requires, plus the `goal_contract` key.

- [ ] **Step 2: Run tests to verify they fail**

Run: `env -u FORCE_COLOR uv run pytest tests/core/test_cli_goal.py -n 0 -v`
Expected: FAIL — "No such command 'goal'" (and the validator missing).

- [ ] **Step 3: Implement the CLI surface**

In `src/gpd/cli.py`, after the `cost` command block (~line 4473), add:

```python
# ═══════════════════════════════════════════════════════════════════════════
# goal — Goal-contract status and gate decisions for gpd:goal runs
# ═══════════════════════════════════════════════════════════════════════════

goal_app = typer.Typer(help="Goal-contract status and gate decisions for gpd:goal runs")
app.add_typer(goal_app, name="goal")


def _goal_gate_payload() -> dict:
    from gpd.core.costs import build_cost_summary
    from gpd.core.goal_contract import GoalContract, validate_goal_contract_payload
    from gpd.core.goal_evidence import collect_claim_outcomes, collect_phase_statuses
    from gpd.core.goal_gate import GoalGateError, goal_gate_summary
    from gpd.core.state import state_load

    cwd = _get_cwd()
    loaded = state_load(cwd)
    payload = (loaded.state or {}).get("goal_contract")
    if payload is None:
        _error(
            'No goal contract found. Start one with /gpd:goal "<statement>" '
            "--budget-usd <amount> and/or --max-phases <n>."
        )
    issues = validate_goal_contract_payload(payload)
    if issues:
        _error("Invalid goal contract: " + "; ".join(issues))
    contract = GoalContract.model_validate(payload)
    spent_usd = build_cost_summary(cwd, last_sessions=0).project.cost_usd
    claim_outcomes = collect_claim_outcomes(cwd)
    phase_statuses = collect_phase_statuses(cwd)
    all_phases_passed = bool(phase_statuses) and all(
        status == "passed" for status in phase_statuses.values()
    )
    try:
        summary = goal_gate_summary(
            contract,
            spent_usd=spent_usd,
            claim_outcomes=claim_outcomes,
            all_phases_passed=all_phases_passed,
        )
    except GoalGateError as exc:
        _error(str(exc))
    return summary.model_dump(mode="json")


@goal_app.command("gate")
def goal_gate() -> None:
    """Emit the gate decision for the active goal run (caps + criteria)."""
    _output(_goal_gate_payload())


@goal_app.command("status")
def goal_status() -> None:
    """Show the goal run receipt: spend, phases, criteria, and status."""
    payload = _goal_gate_payload()
    if _raw:
        _output(payload)
        return
    _render_goal_status(payload)
```

Adaptation notes for this step (one-line lookups, not design choices):
- `state_load` — confirm the exact load entry name in `gpd.core.state` (it is
  the function returning `StateLoadResult` with a `.state` dict; search
  `def state_load` in state.py) and how other CLI commands resolve
  project-rooted state from `_get_cwd()` (some commands resolve the project
  root first via a `root_resolution` helper — mirror the closest reader, e.g.
  whatever `gpd resume` or `gpd cost` uses).
- `collect_claim_outcomes(cwd)` expects the project root; if state resolution
  yields a different root than `cwd`, pass the resolved root.

Add `_render_goal_status` next to `_render_cost_summary`, matching its rich
style (find the console object name used there and reuse it):

```python
def _render_goal_status(payload: dict) -> None:
    from rich.table import Table

    if payload["usd_cap_enforceable"]:
        percent = round(payload["run_spent_usd"] / payload["budget_usd"] * 100.0, 1)
        _console.print(
            f"Budget: ${payload['run_spent_usd']:.2f} of ${payload['budget_usd']:.2f} used "
            f"({percent}%) — decision: {payload['budget_decision']}"
        )
    else:
        _console.print(
            f"Budget: USD spend unavailable on this runtime — decision: {payload['budget_decision']}"
        )
    if payload["max_phases"] is not None:
        _console.print(f"Phases: {payload['phases_completed']} of {payload['max_phases']} used")
    table = Table("Criterion", "Claim", "Outcome")
    for criterion in payload["criteria"]:
        table.add_row(criterion["id"], criterion["claim_ref"], criterion["outcome"])
    _console.print(table)
    _console.print("Goal achieved." if payload["achieved"] else "Goal not yet achieved.")
```

In the `validate_app` JSON-validator section (~cli.py:9924, next to
`review-ledger`), add — copying the document-loading and exit conventions of
the adjacent validators verbatim:

```python
@validate_app.command("goal-contract")
def validate_goal_contract(
    file: str = typer.Argument(..., help="Path to a goal-contract JSON file, or - for stdin"),
) -> None:
    """Validate a gpd:goal goal-contract payload."""
    from gpd.core.goal_contract import validate_goal_contract_payload

    payload = _load_json_document_or_error(file)  # reuse the same helper review-ledger uses
    issues = validate_goal_contract_payload(payload)
    _output({"valid": not issues, "issues": issues})
    if issues:
        raise typer.Exit(code=1)
```

- [ ] **Step 4: Run the new tests, then the full CLI suite**

Run: `env -u FORCE_COLOR uv run pytest tests/core/test_cli_goal.py -n 0 -v`
Expected: 5 passed

Run: `env -u FORCE_COLOR uv run pytest tests/core/test_cli.py -n 0 -q`
Expected: all pass (no regressions)

- [ ] **Step 5: Regenerate generated surfaces and run their checks**

```bash
uv run python scripts/render_public_surface.py
uv run python scripts/render_help_surface.py
uv run python scripts/sync_repo_graph_contract.py
uv run python scripts/render_public_surface.py --check
uv run python scripts/render_help_surface.py --check
uv run python scripts/sync_repo_graph_contract.py --check
env -u FORCE_COLOR uv run pytest tests/core -n 0 -q -k "public_surface or help_surface or generated_surface"
```

Expected: regen rewrites generated artifacts (diff should only contain
goal-command/goal-CLI additions); all checks and tests pass. Also search the
docs for where `gpd validate` subcommands are listed (CONTRIBUTING.md mentions
validation docs alignment; `grep -rn "review-ledger" README.md docs/`) and add
`goal-contract` wherever siblings are enumerated.

- [ ] **Step 6: Commit**

```bash
git add src/gpd/cli.py tests/core/test_cli_goal.py <regenerated files> <doc updates>
git commit -m "feat: add gpd goal status/gate CLI and validate goal-contract"
```

---

## Task 5: Command descriptor and goal workflow

**Files:**
- Create: `src/gpd/commands/goal.md`
- Create: `src/gpd/specs/workflows/goal/goal-bootstrap.md`
- Test: existing suites (`tests/adapters/test_registry.py`, `tests/adapters/test_install_roundtrip.py`, `tests/test_metadata_consistency.py`)

Do NOT touch `src/gpd/specs/workflows/autonomous/` or any stage manifest.

- [ ] **Step 1: Write the command descriptor**

Create `src/gpd/commands/goal.md`:

```markdown
---
name: gpd:goal
description: Run toward a stated goal under binding caps (USD budget and/or phase count) until achieved, budget-stopped, or blocked
argument-hint: "\"<goal statement>\" [--budget-usd <amount>] [--max-phases <n>] | --resume [--budget-usd <amount>] [--max-phases <n>]"
context_mode: project-required
requires:
  files: ["GPD/ROADMAP.md", "GPD/STATE.md"]
allowed-tools:
  - file_read
  - shell
  - find_files
  - search_files
  - ask_user
  - task
help:
  group: Planning and execution
  order: 205
  compact_description: Goal-directed autonomous run with binding caps and verifier-gated completion
  display_signature: gpd:goal "<goal>" [--budget-usd <amount>] [--max-phases <n>]
---

<objective>
Run the project toward an explicit goal contract under binding caps. The run
continues itself through a goal loop modeled on the autonomous workflow and
terminates in exactly one state: achieved (every success criterion's
plan-contract claim verified passed), budget_stopped (a cap bound; clean
checkpoint with receipt), or blocked.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/goal/goal-bootstrap.md
</execution_context>

<context>
`--budget-usd <amount>` sets a binding USD cap (enforced when the runtime
records cost telemetry). `--max-phases <n>` sets a binding phase-count cap
(enforced everywhere). At least one cap is required. `--resume` re-enters a
stopped goal run on the existing contract, optionally replacing the caps.
</context>

<process>
Follow the included goal-bootstrap authority. The goal may only be marked
achieved by the verification-gated criteria check (`gpd --raw goal gate`) —
never by self-assessment.
</process>
```

Frontmatter conformance check: before committing, compare field-by-field with
`src/gpd/commands/autonomous.md` and `quick.md`; `context_mode` must be one of
the registry-valid values (`tests/test_metadata_consistency.py::test_every_command_declares_valid_context_mode`).

- [ ] **Step 2: Write the workflow bootstrap**

Create `src/gpd/specs/workflows/goal/goal-bootstrap.md`. First read
`src/gpd/specs/workflows/quick/task-bootstrap.md` for the conventions of a
bootstrap authority file (heading style, how it references `gpd` CLI calls,
stage-authority phrasing) and mirror that style. Content:

```markdown
# Goal Run Bootstrap

## Stage authority

This stage owns: goal-contract creation or resume, baseline snapshot, criteria
confirmation, the goal loop with its gates, and terminal-state handling. Phase
work inside each loop iteration follows the same discipline as the autonomous
workflow (discuss -> plan -> execute -> verify), but this workflow never
modifies autonomous stage files and goal runs never skip verification.

## 1. Resolve mode

- With a goal statement argument: new goal run. If `state.json` already has a
  `goal_contract` with status `active`, stop and tell the user to `--resume`
  or finish that goal first (one active goal per project).
- With `--resume`: load the existing contract via `gpd --raw goal status`.
  Keep `baseline_spent_usd` and `phases_completed` (caps measure the whole
  goal run across resumes). If `--budget-usd` / `--max-phases` were provided,
  replace those caps in the contract. Set status back to `active`.

## 2. Create the goal contract (new runs)

1. Snapshot the baseline: run `gpd --raw cost` and read
   `project.cost_usd`. If it is a number, record it as `baseline_spent_usd`;
   if it is null (no cost telemetry on this runtime), record null and require
   `--max-phases` — if the user did not provide one, ask for it now (this is
   part of the single upfront interaction). Never start an uncapped run.
2. Draft 2-5 success criteria from the goal statement. Each criterion gets an
   id (GC-1, GC-2, ...) and a `claim_ref` (goal-gc-1, goal-gc-2, ...): a
   plan-contract claim id that future phase plans MUST carry in their
   contracts so the verifier records its outcome in VERIFICATION.md
   `contract_results.claims`. Prefer fewer, decisive criteria.
3. Present the drafted criteria and the caps to the user for confirmation
   (single upfront interaction). Apply edits.
4. Validate before writing: pipe the contract JSON through
   `gpd --raw validate goal-contract -`. Fix any issues it reports.
5. Write the contract into `state.json` under the `goal_contract` key using
   the structured state update commands, and mirror a two-line summary into
   STATE.md.
6. Record the start event:
   `gpd observe event goal start --status ok --data '{"budget_usd": <amount or null>, "max_phases": <n or null>}'`.

## 3. Goal loop

Repeat until a terminal state:

1. **Gate.** Run `gpd --raw goal gate`.
   - Exit code non-zero (no enforceable cap, telemetry failure, invalid
     contract): FAIL CLOSED — surface the error to the user and stop. Never
     continue an ungated run.
   - `achieved: true` -> go to step 4 (achieved).
   - `budget_decision: stop` -> go to step 5 (budget stop).
   - `budget_decision: wrap_up` -> execute exactly one final consolidation
     phase in step 2 (verify and close existing threads decisively; no new
     exploratory work). `--max-phases N` therefore permits exactly N phases.
   - `budget_decision: continue` -> proceed to step 2.
   - Record: `gpd observe event goal budget_gate --status ok --data '<gate payload>'`.
2. **Phase iteration.** Execute exactly one phase through the standard
   discuss -> plan -> execute -> verify cycle (same child-command discipline
   as the autonomous workflow). The phase PLAN contract MUST include every
   still-pending goal criterion's `claim_ref` that this phase can decisively
   address; never invent claim outcomes — the verifier writes them.
3. **Account.** After the phase's verification completes, increment
   `goal_contract.phases_completed` by 1 via the structured state update
   commands, and record
   `gpd observe event goal criteria_check --status ok --data '<gate payload>'`.
   Loop to step 1.
4. **Achieved.** Set `goal_contract.status` to `achieved`, record
   `gpd observe event goal stop --status ok --data '{"terminal": "achieved"}'`,
   show the receipt (`gpd goal status`), and stop.
5. **Budget stop.** Checkpoint cleanly (same checkpoint discipline as the
   autonomous workflow's stop path), set `goal_contract.status` to
   `budget_stopped`, record
   `gpd observe event goal stop --status ok --data '{"terminal": "budget_stopped"}'`,
   and show the receipt plus resume instructions:
   `/gpd:goal --resume [--budget-usd <new>] [--max-phases <new>]`.
6. **Blocked.** If a phase iteration reports an unrecoverable block, set
   `goal_contract.status` to `blocked`, record the stop event with
   `"terminal": "blocked"`, and surface the blocker with the receipt.
```

- [ ] **Step 3: Regenerate generated surfaces**

```bash
uv run python scripts/sync_repo_graph_contract.py
uv run python scripts/render_public_surface.py
uv run python scripts/render_help_surface.py
uv run python scripts/sync_repo_graph_contract.py --check
uv run python scripts/render_public_surface.py --check
uv run python scripts/render_help_surface.py --check
```

Expected: regen rewrites generated files (review the diff — only goal
additions); all `--check` runs exit 0.

- [ ] **Step 4: Run the cross-runtime and metadata suites**

```bash
env -u FORCE_COLOR uv run pytest -n 0 tests/test_metadata_consistency.py -q
env -u FORCE_COLOR uv run pytest -n 0 tests/adapters/test_registry.py tests/adapters/test_install_roundtrip.py -q
env -u FORCE_COLOR uv run pytest -n 0 tests/core/test_autonomous_stage_topology.py -q
```

Expected: all pass. The topology test run proves the autonomous workflow was
not disturbed. If a registry/metadata test fails, read its assertion — it
names exactly which surface (frontmatter field, inventory, help group) needs
fixing; fix forward.

- [ ] **Step 5: Commit**

```bash
git add src/gpd/commands/goal.md src/gpd/specs/workflows/goal/ <regenerated files>
git commit -m "feat: add gpd:goal command descriptor and goal run workflow"
```

---

## Task 6: End-to-end gate-plumbing smoke test

**Files:**
- Test: `tests/core/test_goal_smoke.py`

This is the demo floor: prove, hermetically, that the full plumbing — state
contract → cost summary → claim aggregation → gate → receipt — reaches both
`achieved` and the budget-stop decision on a toy project, with no LLM involved.

- [ ] **Step 1: Write the smoke test**

Create `tests/core/test_goal_smoke.py`:

```python
"""End-to-end gate-plumbing smoke: toy project from goal start to achieved.

Simulates exactly what the goal workflow does between agent turns: seed the
contract, complete phases (verifier writes contract_results), increment the
counter, and shell the gate. No LLM, no network.
"""

import json
from pathlib import Path

from typer.testing import CliRunner

from gpd.cli import app

runner = CliRunner()

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
    return json.loads(result.output)


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
```

Note: run with `env -u FORCE_COLOR` like everything else; the human receipt
assertion checks only criterion ids (single tokens rich won't split with ANSI
codes mid-word in table cells — if ANSI still interferes, assert on the
`--raw` payload instead and keep a minimal "exit_code == 0" check for the
human rendering). If minimal `state.json` seeding trips integrity checks in
`state_load`, reuse the scaffold helper adopted in Task 4's tests.

- [ ] **Step 2: Run the smoke test**

Run: `env -u FORCE_COLOR uv run pytest tests/core/test_goal_smoke.py -n 0 -v`
Expected: 3 passed

- [ ] **Step 3: Commit**

```bash
git add tests/core/test_goal_smoke.py
git commit -m "test: add end-to-end gate-plumbing smoke for gpd:goal"
```

---

## Task 7: Changelog, full suite, and PR

**Files:**
- Modify: `CHANGELOG.md` (add under `## vNEXT`)

- [ ] **Step 1: Add the release note**

Under the `## vNEXT` heading in `CHANGELOG.md` (create the section at the top
if absent — match the existing entry style):

```markdown
- Added `gpd:goal`: goal-directed autonomous runs under binding caps. A typed
  goal contract (statement, success criteria tied to plan-contract claims, USD
  budget and/or phase-count cap) drives a goal loop; runs terminate as achieved
  (verifier-gated via VERIFICATION.md contract results), budget_stopped (clean
  checkpoint + receipt), or blocked. New CLI surfaces: `gpd goal status`,
  `gpd goal gate`, `gpd validate goal-contract`.
```

- [ ] **Step 2: Run the full fast suite**

Run: `env -u FORCE_COLOR uv run pytest tests/ -q`
Expected: 0 failures (baseline on this machine before this work:
12,941 passed, 7 skipped, ~85s)

- [ ] **Step 3: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs: add vNEXT release note for gpd:goal"
```

- [ ] **Step 4: Push branch and open PR**

`main` is protected; work goes through a PR with the required `tests` workflow.

```bash
git push -u origin worktree-goal-command
gh pr create --title "feat: add gpd:goal — goal-directed autonomous runs under binding caps" --body "$(cat <<'EOF'
## Summary
- New `gpd:goal "<statement>" [--budget-usd X] [--max-phases N]` command: a goal loop modeled on the autonomous workflow, under binding caps — USD where the runtime records cost telemetry (codex today), phase count everywhere
- Verifier-gated completion: criteria reference plan-contract claim ids; only VERIFICATION.md `contract_results.claims` outcomes written by the verification machinery can mark the goal achieved
- Fail-closed: goal runs never run uncapped or ungated
- New CLI surfaces: `gpd goal status` (receipt), `gpd goal gate` (machine decision), `gpd validate goal-contract`
- The `autonomous` workflow and its stage manifest are untouched
- Design spec (with adversarial-review amendments): docs/superpowers/specs/2026-06-04-goal-command-design.md

## Test plan
- [x] `tests/core/test_goal_contract.py`, `test_goal_gate.py`, `test_goal_evidence.py`, `test_cli_goal.py`
- [x] `tests/adapters/test_registry.py`, `tests/adapters/test_install_roundtrip.py`, `tests/test_metadata_consistency.py`, `tests/core/test_autonomous_stage_topology.py`
- [x] Full suite `uv run pytest tests/ -q`
- [x] Generated-surface checks (repo graph, public surface, help surface)

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Self-review notes

- **Spec coverage:** dual-cap user surface (Tasks 1, 2, 4, 5), goal contract +
  typed validator (Tasks 1, 4), claim-based verifier-gated criteria (Tasks 2,
  3, 5), fail-closed no-cap/no-gate behavior (Tasks 2, 4, 5), receipt (Task 4),
  observability events via existing `gpd observe event` CLI (Task 5 workflow),
  resume semantics incl. cap replacement + kept baseline (Task 5 workflow
  step 1), generated-surface regen + docs alignment (Tasks 4-5), autonomous
  workflow untouched + topology proof (Task 5 step 4), scope cuts respected
  (no staged init, no new agents, one goal per project).
- **Known adaptation points (flagged inline where they appear, each a one-line
  lookup at implementation time):** exact `state_load`/root-resolution entry
  used by sibling CLI readers; the JSON-document loader helper shared by
  `review-ledger`; the rich console object name; the GPD base error class
  name; the exact VERIFICATION.md filename glob; the CLI test harness helpers.
  The surrounding code is complete in every case.
- **Type consistency:** `GoalContract`/`GoalCriterion` (Task 1) are consumed in
  Tasks 2-4; claim-status vocabulary (`passed|partial|failed|blocked|not_attempted`)
  is identical in Tasks 2, 3, and 5; decision literals
  (`continue|wrap_up|stop`) and status literals
  (`active|achieved|budget_stopped|blocked`) match the spec everywhere;
  `collect_claim_outcomes` (Task 3) is the function imported in Task 4.
