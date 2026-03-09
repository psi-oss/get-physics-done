"""Budget contracts for the GPD-Exp experiment pipeline.

Defines ExperimentBudget, LedgerEntry, and supporting types for
the reserve-then-confirm budget flow using integer cents.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class Currency(StrEnum):
    """Supported currencies matching rent-a-human platforms."""

    USD = "USD"
    EUR = "EUR"
    ETH = "ETH"
    BTC = "BTC"
    USDC = "USDC"


class LedgerAction(StrEnum):
    """Actions recorded in the budget ledger."""

    RESERVE = "reserve"
    CONFIRM = "confirm"
    RELEASE = "release"
    REFUND = "refund"


class LedgerEntry(BaseModel):
    """A single entry in the budget ledger audit trail."""

    id: UUID
    experiment_id: UUID
    action: LedgerAction
    amount_cents: int = Field(ge=0)
    currency: Currency
    description: str
    bounty_id: str | None = None
    idempotency_key: str
    reservation_id: UUID | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ExperimentBudget(BaseModel):
    """Budget state for a GPD-Exp experiment.

    All monetary values are stored as integer cents to prevent
    floating-point precision errors with real money.
    """

    budget_cap_cents: int = Field(ge=0)
    budget_spent_cents: int = Field(ge=0, default=0)
    budget_reserved_cents: int = Field(ge=0, default=0)
    currency: Currency = Currency.USD

    @property
    def available_cents(self) -> int:
        """Compute available budget: cap - spent - reserved."""
        return self.budget_cap_cents - self.budget_spent_cents - self.budget_reserved_cents

    @property
    def budget_cap_display(self) -> float:
        """Display-friendly budget cap (e.g. 100.50 for 10050 cents)."""
        return self.budget_cap_cents / 100.0


class BudgetExceeded(Exception):
    """Raised when a budget operation would exceed the cap."""

    def __init__(self, experiment_id: str, requested_cents: int, available_cents: int) -> None:
        self.experiment_id = experiment_id
        self.requested_cents = requested_cents
        self.available_cents = available_cents
        super().__init__(
            f"Budget exceeded for experiment {experiment_id}: "
            f"requested {requested_cents} cents but only {available_cents} available"
        )
