"""Experiment contracts for the GPD-Exp pipeline.

Defines ExperimentSpec, ExperimentProtocol, Hypothesis, ExperimentVariable,
and the StudyDesign discriminated union.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from gpd.exp.contracts.budget import Currency


class VariableRole(StrEnum):
    """Role of a variable in the experiment."""

    INDEPENDENT = "independent"
    DEPENDENT = "dependent"
    CONFOUND = "confound"
    CONTROL = "control"


class VariableType(StrEnum):
    """Measurement scale of a variable."""

    CONTINUOUS = "continuous"
    CATEGORICAL = "categorical"
    ORDINAL = "ordinal"
    BINARY = "binary"


class ExperimentVariable(BaseModel):
    """A single variable in the experiment design."""

    name: str
    role: VariableRole
    variable_type: VariableType
    levels: list[str] | None = None
    unit: str | None = None
    expected_range: tuple[float, float] | None = None


class Hypothesis(BaseModel):
    """A testable hypothesis with directional prediction."""

    null_hypothesis: str
    alternative_hypothesis: str
    direction: Literal["two_tailed", "greater", "less"] = "two_tailed"
    predicted_effect_size: float | None = None


class BetweenSubjectsDesign(BaseModel):
    """Between-subjects experiment design with independent groups."""

    design_type: Literal["between_subjects"] = "between_subjects"
    groups: list[str]
    assignment_method: Literal["random", "matched", "convenience"] = "random"


class WithinSubjectsDesign(BaseModel):
    """Within-subjects (repeated measures) experiment design."""

    design_type: Literal["within_subjects"] = "within_subjects"
    conditions: list[str]
    counterbalance: bool = True


class FactorialDesign(BaseModel):
    """Factorial experiment design with crossed factors."""

    design_type: Literal["factorial"] = "factorial"
    factors: list[str]
    levels_per_factor: dict[str, list[str]]


StudyDesign = Annotated[
    BetweenSubjectsDesign | WithinSubjectsDesign | FactorialDesign,
    Field(discriminator="design_type"),
]


class ExperimentSpec(BaseModel):
    """Initial user input before experiment design."""

    question: str
    budget_cap_cents: int = Field(ge=0, default=0)
    currency: Currency = Currency.USD
    deadline: datetime | None = None


class ExperimentProtocol(BaseModel):
    """Single source of truth for all downstream agents. Maximally typed."""

    id: UUID
    question: str
    hypotheses: list[Hypothesis]
    variables: list[ExperimentVariable]
    study_design: StudyDesign
    sample_size_target: int
    control_condition: str
    randomization_seed: int | None = None
    materials_required: list[str] = Field(default_factory=list)
    measurement_procedure: str
    expected_duration_minutes: int | None = None
    ethics_screening_passed: bool = False
    ethics_screening_notes: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
