"""Feasibility and ethics screening contract models.

Defines RejectionCategory, FeasibilityResult, and EthicsScreeningResult
for the Phase 2 feasibility pre-screening pipeline.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class RejectionCategory(StrEnum):
    """Categories for feasibility rejection decisions.

    FEASIBLE means the question passed screening.
    The four rejection categories cover the main failure modes:
    non-empirical, trivially answered, intractable, or ethically problematic.
    """

    FEASIBLE = "feasible"
    NON_EMPIRICAL = "non_empirical"
    TRIVIALLY_ANSWERED = "trivially_answered"
    INTRACTABLE = "intractable"
    ETHICALLY_PROBLEMATIC = "ethically_problematic"


class FeasibilityResult(BaseModel):
    """Result of a feasibility screening for a research question."""

    category: RejectionCategory
    is_feasible: bool
    explanation: str
    suggested_modification: str | None = None


class EthicsScreeningResult(BaseModel):
    """Result of an ethics keyword screening pass."""

    ethics_passed: bool
    concerns: list[str]
    severity: str  # "none", "low", "medium", "high", "critical"
    reasoning: str
