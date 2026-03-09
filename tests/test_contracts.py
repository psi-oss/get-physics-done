"""Round-trip serialization tests for all GPD-Exp contract models.

Validates Phase 1 success criterion: All Pydantic models can be instantiated,
serialized to JSON, and round-tripped without data loss.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import TypeAdapter

from gpd.exp.contracts import (
    BetweenSubjectsDesign,
    BountyRecord,
    BountySpec,
    BountyStatus,
    CategoricalDataPoint,
    Currency,
    DataPoint,
    ExperimentBudget,
    ExperimentProtocol,
    ExperimentSpec,
    ExperimentVariable,
    FactorialDesign,
    Hypothesis,
    LedgerAction,
    LedgerEntry,
    NumericDataPoint,
    ObservationDataPoint,
    StudyDesign,
    TimingDataPoint,
    VariableRole,
    VariableType,
    WithinSubjectsDesign,
)
from gpd.exp.domain.budget_arithmetic import can_reserve, cents_to_display, compute_available


def test_experiment_protocol_round_trip() -> None:
    """Full ExperimentProtocol with BetweenSubjectsDesign round-trips through JSON."""
    protocol = ExperimentProtocol(
        id=uuid4(),
        question="Does ambient temperature affect reaction time?",
        hypotheses=[
            Hypothesis(
                null_hypothesis="Temperature has no effect on reaction time",
                alternative_hypothesis="Higher temperature increases reaction time",
                direction="greater",
                predicted_effect_size=0.5,
            ),
        ],
        variables=[
            ExperimentVariable(
                name="ambient_temperature",
                role=VariableRole.INDEPENDENT,
                variable_type=VariableType.CONTINUOUS,
                unit="celsius",
                expected_range=(15.0, 35.0),
            ),
            ExperimentVariable(
                name="reaction_time_ms",
                role=VariableRole.DEPENDENT,
                variable_type=VariableType.CONTINUOUS,
                unit="milliseconds",
            ),
        ],
        study_design=BetweenSubjectsDesign(
            groups=["cold_room", "warm_room"],
            assignment_method="random",
        ),
        sample_size_target=60,
        control_condition="cold_room",
        randomization_seed=42,
        materials_required=["thermometer", "reaction_time_app"],
        measurement_procedure="Participants complete 10 reaction time trials on tablet app",
        expected_duration_minutes=30,
        ethics_screening_passed=True,
        ethics_screening_notes="IRB approved 2026-01-15",
    )

    json_str = protocol.model_dump_json()
    restored = ExperimentProtocol.model_validate_json(json_str)

    assert restored.id == protocol.id
    assert restored.question == protocol.question
    assert len(restored.hypotheses) == 1
    assert restored.hypotheses[0].direction == "greater"
    assert len(restored.variables) == 2
    assert restored.variables[0].expected_range == (15.0, 35.0)
    assert restored.study_design.design_type == "between_subjects"
    assert restored.sample_size_target == 60
    assert restored.randomization_seed == 42
    assert restored.ethics_screening_passed is True


@pytest.mark.parametrize(
    "design,expected_type",
    [
        (
            BetweenSubjectsDesign(groups=["a", "b"], assignment_method="random"),
            "between_subjects",
        ),
        (
            WithinSubjectsDesign(conditions=["baseline", "treatment"], counterbalance=True),
            "within_subjects",
        ),
        (
            FactorialDesign(
                factors=["temperature", "humidity"],
                levels_per_factor={"temperature": ["low", "high"], "humidity": ["low", "high"]},
            ),
            "factorial",
        ),
    ],
    ids=["between_subjects", "within_subjects", "factorial"],
)
def test_study_design_discriminated_union(design: object, expected_type: str) -> None:
    """Each StudyDesign variant round-trips and restores correct subtype."""
    adapter = TypeAdapter(StudyDesign)
    json_str = adapter.dump_json(design)
    restored = adapter.validate_json(json_str)

    assert restored.design_type == expected_type
    assert type(restored) is type(design)


@pytest.mark.parametrize(
    "data_point,expected_type",
    [
        (
            NumericDataPoint(
                id=uuid4(),
                run_id=uuid4(),
                bounty_id="bounty-001",
                timestamp=datetime.now(UTC),
                value=9.81,
                unit="m/s^2",
                uncertainty=0.02,
            ),
            "numeric",
        ),
        (
            CategoricalDataPoint(
                id=uuid4(),
                run_id=uuid4(),
                bounty_id="bounty-002",
                timestamp=datetime.now(UTC),
                category="red",
                confidence=0.95,
            ),
            "categorical",
        ),
        (
            TimingDataPoint(
                id=uuid4(),
                run_id=uuid4(),
                bounty_id="bounty-003",
                timestamp=datetime.now(UTC),
                duration_seconds=4.5,
                start_time=datetime(2026, 1, 1, 10, 0, 0),
                end_time=datetime(2026, 1, 1, 10, 0, 4),
            ),
            "timing",
        ),
        (
            ObservationDataPoint(
                id=uuid4(),
                run_id=uuid4(),
                bounty_id="bounty-004",
                timestamp=datetime.now(UTC),
                description="Pendulum swings 10 times in 20.3 seconds",
                attachments=["video_001.mp4"],
            ),
            "observation",
        ),
    ],
    ids=["numeric", "categorical", "timing", "observation"],
)
def test_data_point_discriminated_union(data_point: object, expected_type: str) -> None:
    """Each DataPoint variant round-trips via the union type and restores correct subtype."""
    adapter = TypeAdapter(DataPoint)
    json_str = adapter.dump_json(data_point)
    restored = adapter.validate_json(json_str)

    assert restored.measurement_type == expected_type
    assert type(restored) is type(data_point)
    assert restored.id == data_point.id
    assert restored.bounty_id == data_point.bounty_id


def test_ledger_entry_round_trip() -> None:
    """LedgerEntry with all fields round-trips including UUIDs."""
    reservation_id = uuid4()
    entry = LedgerEntry(
        id=uuid4(),
        experiment_id=uuid4(),
        action=LedgerAction.RESERVE,
        amount_cents=5000,
        currency=Currency.USD,
        description="Reserve for bounty-001",
        bounty_id="bounty-001",
        idempotency_key="idem-key-abc",
        reservation_id=reservation_id,
    )

    json_str = entry.model_dump_json()
    restored = LedgerEntry.model_validate_json(json_str)

    assert restored.id == entry.id
    assert restored.experiment_id == entry.experiment_id
    assert restored.action == LedgerAction.RESERVE
    assert restored.amount_cents == 5000
    assert restored.currency == Currency.USD
    assert restored.reservation_id == reservation_id
    assert restored.idempotency_key == "idem-key-abc"


def test_experiment_budget_available_cents() -> None:
    """ExperimentBudget.available_cents computes correctly including edge case of zero."""
    budget = ExperimentBudget(
        budget_cap_cents=10000,
        budget_spent_cents=3000,
        budget_reserved_cents=2000,
    )
    assert budget.available_cents == 5000

    # Edge case: exactly at cap
    full_budget = ExperimentBudget(
        budget_cap_cents=10000,
        budget_spent_cents=7000,
        budget_reserved_cents=3000,
    )
    assert full_budget.available_cents == 0


def test_experiment_budget_integer_only() -> None:
    """ExperimentBudget fields are integers and budget_cap_display returns correct float."""
    budget = ExperimentBudget(budget_cap_cents=10050)

    assert isinstance(budget.budget_cap_cents, int)
    assert isinstance(budget.budget_spent_cents, int)
    assert isinstance(budget.budget_reserved_cents, int)
    assert budget.budget_cap_display == 100.50

    # Pydantic coerces compatible values to int
    budget2 = ExperimentBudget(budget_cap_cents=500)
    assert budget2.budget_cap_display == 5.0


def test_experiment_budget_round_trip() -> None:
    """ExperimentBudget round-trips through JSON serialization."""
    budget = ExperimentBudget(
        budget_cap_cents=50000,
        budget_spent_cents=10000,
        budget_reserved_cents=5000,
        currency=Currency.EUR,
    )

    json_str = budget.model_dump_json()
    restored = ExperimentBudget.model_validate_json(json_str)

    assert restored.budget_cap_cents == 50000
    assert restored.budget_spent_cents == 10000
    assert restored.budget_reserved_cents == 5000
    assert restored.currency == Currency.EUR
    assert restored.available_cents == 35000


def test_bounty_record_round_trip() -> None:
    """BountyRecord with nested BountySpec round-trips through JSON."""
    now = datetime.now(UTC)
    record = BountyRecord(
        id=uuid4(),
        experiment_id=uuid4(),
        platform_bounty_id="platform-123",
        status=BountyStatus.ACTIVE,
        specification=BountySpec(
            title="Measure pendulum period",
            description="Use a stopwatch to time 10 pendulum swings",
            price_cents=500,
            currency=Currency.USD,
            skills_needed=["physics", "timing"],
            requirements=["Must have a stopwatch"],
            spots_available=3,
        ),
        amount_cents=500,
        currency=Currency.USD,
        reservation_id=uuid4(),
        idempotency_key="idem-bounty-001",
        deadline=now,
        created_at=now,
        updated_at=now,
    )

    json_str = record.model_dump_json()
    restored = BountyRecord.model_validate_json(json_str)

    assert restored.id == record.id
    assert restored.status == BountyStatus.ACTIVE
    assert restored.specification.title == "Measure pendulum period"
    assert restored.specification.price_cents == 500
    assert restored.specification.spots_available == 3
    assert len(restored.specification.skills_needed) == 2


def test_budget_arithmetic_pure_functions() -> None:
    """Test can_reserve, compute_available, cents_to_display with edge cases."""
    # can_reserve: normal cases
    assert can_reserve(10000, 5000, 2000, 2000) is True
    assert can_reserve(10000, 5000, 2000, 3000) is True  # exactly at cap
    assert can_reserve(10000, 5000, 2000, 4000) is False  # exceeds cap

    # can_reserve: zero budget
    assert can_reserve(0, 0, 0, 0) is True
    assert can_reserve(0, 0, 0, 1) is False

    # can_reserve: exact cap match
    assert can_reserve(10000, 10000, 0, 0) is True
    assert can_reserve(10000, 10000, 0, 1) is False

    # compute_available
    assert compute_available(10000, 5000, 2000) == 3000
    assert compute_available(10000, 10000, 0) == 0
    assert compute_available(0, 0, 0) == 0

    # cents_to_display
    assert cents_to_display(1250) == "$12.50"
    assert cents_to_display(0) == "$0.00"
    assert cents_to_display(100) == "$1.00"
    assert cents_to_display(1) == "$0.01"
    assert cents_to_display(99999) == "$999.99"


def test_experiment_spec_round_trip() -> None:
    """ExperimentSpec round-trips through JSON."""
    spec = ExperimentSpec(
        question="How does gravity vary at different altitudes?",
        budget_cap_cents=25000,
        currency=Currency.USD,
        deadline=datetime(2026, 6, 1),
    )

    json_str = spec.model_dump_json()
    restored = ExperimentSpec.model_validate_json(json_str)

    assert restored.question == spec.question
    assert restored.budget_cap_cents == 25000
    assert restored.currency == Currency.USD


def test_budget_exceeded_exception() -> None:
    """BudgetExceeded exception carries correct attributes."""
    from gpd.exp.contracts import BudgetExceeded

    exc = BudgetExceeded(
        experiment_id="exp-001",
        requested_cents=5000,
        available_cents=3000,
    )

    assert exc.experiment_id == "exp-001"
    assert exc.requested_cents == 5000
    assert exc.available_cents == 3000
    assert "5000" in str(exc)
    assert "3000" in str(exc)
