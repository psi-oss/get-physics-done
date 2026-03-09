"""TDD tests for bounty_translator domain module and cents_to_dollars helper.

Tests are written first (RED phase) and must fail before implementation.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from gpd.exp.contracts.experiment import (
    BetweenSubjectsDesign,
    ExperimentProtocol,
    ExperimentVariable,
    Hypothesis,
    VariableRole,
    VariableType,
)
from gpd.exp.domain.bounty_translator import (
    compute_bounty_deadline,
    compute_protocol_hash,
    translate_protocol_to_bounty_spec,
)
from gpd.exp.domain.budget_arithmetic import cents_to_dollars

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_protocol(
    question: str = "Does ambient light affect reading speed?",
    measurement_procedure: str = "Record time taken to read a 500-word passage.",
    materials_required: list[str] | None = None,
    variables: list[ExperimentVariable] | None = None,
    expected_duration_minutes: int | None = 10,
) -> ExperimentProtocol:
    """Build a minimal but valid ExperimentProtocol for testing."""
    if materials_required is None:
        materials_required = ["Stopwatch", "Printed passage", "Lamp"]
    if variables is None:
        variables = [
            ExperimentVariable(
                name="light_level",
                role=VariableRole.INDEPENDENT,
                variable_type=VariableType.CATEGORICAL,
                levels=["bright", "dim"],
            ),
            ExperimentVariable(
                name="reading_time",
                role=VariableRole.DEPENDENT,
                variable_type=VariableType.CONTINUOUS,
                unit="seconds",
            ),
        ]
    return ExperimentProtocol(
        id=uuid.uuid4(),
        question=question,
        hypotheses=[
            Hypothesis(
                null_hypothesis="Light level does not affect reading speed.",
                alternative_hypothesis="Bright light improves reading speed.",
                direction="two_tailed",
            )
        ],
        variables=variables,
        study_design=BetweenSubjectsDesign(groups=["bright", "dim"]),
        sample_size_target=30,
        control_condition="dim light",
        measurement_procedure=measurement_procedure,
        materials_required=materials_required,
        expected_duration_minutes=expected_duration_minutes,
        ethics_screening_passed=True,
    )


# ---------------------------------------------------------------------------
# cents_to_dollars
# ---------------------------------------------------------------------------


class TestCentsToDollars:
    """Tests for cents_to_dollars helper."""

    def test_five_dollars(self) -> None:
        """500 cents == 5.0 USD."""
        assert cents_to_dollars(500) == 5.0

    def test_one_cent(self) -> None:
        """1 cent == 0.01 USD."""
        assert cents_to_dollars(1) == 0.01

    def test_zero_cents(self) -> None:
        """0 cents == 0.0 USD."""
        assert cents_to_dollars(0) == 0.0

    def test_twelve_dollars_34(self) -> None:
        """1234 cents == 12.34 USD."""
        assert cents_to_dollars(1234) == 12.34


# ---------------------------------------------------------------------------
# compute_protocol_hash
# ---------------------------------------------------------------------------


class TestComputeProtocolHash:
    """Tests for compute_protocol_hash."""

    def test_deterministic(self) -> None:
        """Same protocol input produces same hash (deterministic)."""
        protocol = _make_protocol()
        h1 = compute_protocol_hash(protocol)
        h2 = compute_protocol_hash(protocol)
        assert h1 == h2

    def test_different_protocol_different_hash(self) -> None:
        """Different protocol (question changed) produces different hash."""
        p1 = _make_protocol(question="Does X affect Y?")
        p2 = _make_protocol(question="Does A affect B?")
        assert compute_protocol_hash(p1) != compute_protocol_hash(p2)

    def test_hash_is_16_char_hex(self) -> None:
        """Hash is a 16-character hexadecimal string."""
        protocol = _make_protocol()
        h = compute_protocol_hash(protocol)
        assert len(h) == 16
        # Must be valid hex
        int(h, 16)


# ---------------------------------------------------------------------------
# compute_bounty_deadline
# ---------------------------------------------------------------------------


class TestComputeBountyDeadline:
    """Tests for compute_bounty_deadline."""

    def test_returns_before_experiment_deadline(self) -> None:
        """Returned deadline is earlier than the experiment deadline."""
        future = datetime.now(tz=UTC) + timedelta(hours=10)
        result = compute_bounty_deadline(future, expected_duration_minutes=10)
        assert result < future

    def test_respects_90_minute_buffer(self) -> None:
        """Returned deadline is at most experiment_deadline minus 90 minutes."""
        future = datetime.now(tz=UTC) + timedelta(hours=10)
        result = compute_bounty_deadline(future, expected_duration_minutes=10)
        latest_allowed = future - timedelta(minutes=90)
        assert result <= latest_allowed

    def test_raises_when_buffer_not_satisfied(self) -> None:
        """Raises ValueError when experiment_deadline is within buffer time."""
        close_deadline = datetime.now(tz=UTC) + timedelta(minutes=60)
        with pytest.raises(ValueError):
            compute_bounty_deadline(close_deadline, expected_duration_minutes=10)

    def test_none_duration_uses_hard_cap(self) -> None:
        """When expected_duration_minutes=None, uses hard cap (deadline = latest_allowed)."""
        future = datetime.now(tz=UTC) + timedelta(hours=10)
        result = compute_bounty_deadline(future, expected_duration_minutes=None)
        latest_allowed = future - timedelta(minutes=90)
        # Should equal latest_allowed when no duration hint
        assert result == latest_allowed


# ---------------------------------------------------------------------------
# translate_protocol_to_bounty_spec
# ---------------------------------------------------------------------------


class TestTranslateProtocolToBountySpec:
    """Tests for translate_protocol_to_bounty_spec."""

    def _deadline(self) -> datetime:
        return datetime.now(tz=UTC) + timedelta(hours=10)

    def test_price_cents_matches(self) -> None:
        """BountySpec.price_cents matches the provided price_cents."""
        protocol = _make_protocol()
        spec = translate_protocol_to_bounty_spec(protocol, self._deadline(), price_cents=750)
        assert spec.price_cents == 750

    def test_description_starts_with_attention_check(self) -> None:
        """BountySpec.description starts with 'ATTENTION CHECK:'."""
        protocol = _make_protocol()
        spec = translate_protocol_to_bounty_spec(protocol, self._deadline(), price_cents=500)
        assert spec.description.startswith("ATTENTION CHECK:")

    def test_description_contains_measurement_procedure(self) -> None:
        """BountySpec.description contains verbatim measurement_procedure text."""
        procedure = "Record time taken to read a 500-word passage."
        protocol = _make_protocol(measurement_procedure=procedure)
        spec = translate_protocol_to_bounty_spec(protocol, self._deadline(), price_cents=500)
        assert procedure in spec.description

    def test_deadline_respects_experiment_deadline(self) -> None:
        """BountySpec.deadline <= experiment_deadline (BUDGET-02 hard invariant)."""
        experiment_deadline = self._deadline()
        protocol = _make_protocol()
        spec = translate_protocol_to_bounty_spec(protocol, experiment_deadline, price_cents=500)
        assert spec.deadline is not None
        assert spec.deadline <= experiment_deadline

    def test_description_contains_controls_section_when_control_variables(self) -> None:
        """Description contains CONTROLS section when protocol has CONTROL-role variables."""
        variables = [
            ExperimentVariable(
                name="room_temperature",
                role=VariableRole.CONTROL,
                variable_type=VariableType.CONTINUOUS,
                unit="Celsius",
            ),
            ExperimentVariable(
                name="outcome",
                role=VariableRole.DEPENDENT,
                variable_type=VariableType.CONTINUOUS,
            ),
        ]
        protocol = _make_protocol(variables=variables)
        spec = translate_protocol_to_bounty_spec(protocol, self._deadline(), price_cents=500)
        assert "CONTROLS" in spec.description or "control" in spec.description.lower()

    def test_description_contains_materials_list(self) -> None:
        """BountySpec.description contains materials from protocol.materials_required."""
        materials = ["Thermometer", "Glass of water", "Timer"]
        protocol = _make_protocol(materials_required=materials)
        spec = translate_protocol_to_bounty_spec(protocol, self._deadline(), price_cents=500)
        for material in materials:
            assert material in spec.description

    def test_title_starts_with_research_task(self) -> None:
        """BountySpec.title starts with 'Research Task:'."""
        protocol = _make_protocol()
        spec = translate_protocol_to_bounty_spec(protocol, self._deadline(), price_cents=500)
        assert spec.title.startswith("Research Task:")

    def test_title_max_200_chars(self) -> None:
        """BountySpec.title is <= 200 characters."""
        long_question = "X" * 300
        protocol = _make_protocol(question=long_question)
        spec = translate_protocol_to_bounty_spec(protocol, self._deadline(), price_cents=500)
        assert len(spec.title) <= 200

    def test_no_controls_section_without_control_variables(self) -> None:
        """Description does not contain CONTROLS section when there are no CONTROL variables."""
        variables = [
            ExperimentVariable(
                name="light_level",
                role=VariableRole.INDEPENDENT,
                variable_type=VariableType.CATEGORICAL,
            ),
            ExperimentVariable(
                name="reading_time",
                role=VariableRole.DEPENDENT,
                variable_type=VariableType.CONTINUOUS,
            ),
        ]
        protocol = _make_protocol(variables=variables)
        spec = translate_protocol_to_bounty_spec(protocol, self._deadline(), price_cents=500)
        # No CONTROLS header should appear
        assert "CONTROLS" not in spec.description
