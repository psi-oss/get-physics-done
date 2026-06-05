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
