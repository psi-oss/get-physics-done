"""Pure integer budget arithmetic for the GPD-Exp pipeline.

Layer 1 domain logic: no framework imports, no side effects.
All monetary values are integer cents to prevent floating-point errors.
"""

from __future__ import annotations


def can_reserve(cap_cents: int, spent_cents: int, reserved_cents: int, amount_cents: int) -> bool:
    """Check if a reservation of amount_cents is within budget.

    Returns True if spent + reserved + amount <= cap.
    """
    return spent_cents + reserved_cents + amount_cents <= cap_cents


def compute_available(cap_cents: int, spent_cents: int, reserved_cents: int) -> int:
    """Compute available budget in cents: cap - spent - reserved."""
    return cap_cents - spent_cents - reserved_cents


def cents_to_display(cents: int) -> str:
    """Format integer cents as a display string like '$12.50'."""
    dollars = cents // 100
    remainder = cents % 100
    return f"${dollars}.{remainder:02d}"


def cents_to_dollars(cents: int) -> float:
    """Convert integer cents to a float USD amount.

    Examples:
        cents_to_dollars(500) == 5.0
        cents_to_dollars(1) == 0.01
        cents_to_dollars(0) == 0.0
    """
    return cents / 100
