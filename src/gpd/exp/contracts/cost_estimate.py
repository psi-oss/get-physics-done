"""Cost estimation contract models.

Defines CostCategory, CostLineItem, and CostEstimate for the
Phase 2 experiment cost estimation pipeline.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from gpd.exp.domain.budget_arithmetic import cents_to_display


class CostCategory(StrEnum):
    """Categories for cost line items."""

    DATA_COLLECTION = "data_collection"
    RETRIES = "retries"
    PLATFORM_FEES = "platform_fees"


class CostLineItem(BaseModel):
    """A single line item in a cost estimate."""

    description: str
    unit_price_cents: int = Field(ge=0)
    quantity: int = Field(ge=1)
    subtotal_cents: int = Field(ge=0)
    category: CostCategory


class CostEstimate(BaseModel):
    """Full cost estimate with confidence range.

    All monetary values are integer cents to prevent floating-point errors.
    """

    line_items: list[CostLineItem]
    estimated_total_cents: int = Field(ge=0)
    confidence_low_cents: int = Field(ge=0)
    confidence_high_cents: int = Field(ge=0)
    reasoning: str

    @property
    def display_total(self) -> str:
        """Format as '$X +/- $Y' using budget_arithmetic.cents_to_display."""
        midpoint = self.estimated_total_cents
        margin = (self.confidence_high_cents - self.confidence_low_cents) // 2
        return f"{cents_to_display(midpoint)} +/- {cents_to_display(margin)}"
