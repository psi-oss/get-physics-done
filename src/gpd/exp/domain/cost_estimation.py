"""Layer 1 cost estimation domain functions.

Produces itemized cost breakdowns with confidence ranges using integer cents.
Pure domain logic: no framework imports, no side effects.

All monetary arithmetic uses integer cents to prevent floating-point errors.
"""

from __future__ import annotations

from gpd.exp.contracts.cost_estimate import CostCategory, CostEstimate, CostLineItem


def estimate_experiment_cost(
    sample_size: int,
    base_bounty_price_cents: int,
    num_bounty_types: int = 1,
    retry_probability: float = 0.15,
    retry_price_premium: float = 0.20,
) -> CostEstimate:
    """Estimate the cost of running an experiment with confidence range.

    All arithmetic uses integer cents -- no floating point in money paths.

    Args:
        sample_size: Number of participants/data points needed.
        base_bounty_price_cents: Price per bounty in integer cents.
        num_bounty_types: Number of distinct bounty types (default 1).
        retry_probability: Expected fraction of bounties needing retry (0.0-1.0).
        retry_price_premium: Price premium for retry bounties (0.20 = 20% more).

    Returns:
        CostEstimate with itemized line items and confidence range.
    """
    # Base data collection cost
    base_total = sample_size * base_bounty_price_cents * num_bounty_types

    # Retry cost estimation
    expected_retries = int(sample_size * retry_probability)
    retry_unit_price = int(base_bounty_price_cents * (1 + retry_price_premium))
    retry_cost = expected_retries * retry_unit_price

    # Total estimate
    estimated_total = base_total + retry_cost

    # Confidence range
    # Best case: no retries needed
    confidence_low = base_total
    # Worst case: double the expected retries
    confidence_high = base_total + int(expected_retries * 2 * base_bounty_price_cents * (1 + retry_price_premium))

    # Build line items
    line_items: list[CostLineItem] = [
        CostLineItem(
            description="Data collection bounties",
            unit_price_cents=base_bounty_price_cents,
            quantity=sample_size * num_bounty_types,
            subtotal_cents=base_total,
            category=CostCategory.DATA_COLLECTION,
        ),
    ]

    if expected_retries > 0:
        line_items.append(
            CostLineItem(
                description="Expected retry bounties",
                unit_price_cents=retry_unit_price,
                quantity=expected_retries,
                subtotal_cents=retry_cost,
                category=CostCategory.RETRIES,
            ),
        )

    reasoning = (
        f"Base: {sample_size} participants x {base_bounty_price_cents} cents/bounty"
        f" x {num_bounty_types} type(s) = {base_total} cents."
        f" Retries: {expected_retries} expected at {retry_price_premium:.0%} premium = {retry_cost} cents."
        f" Range: [{confidence_low}, {confidence_high}] cents."
    )

    return CostEstimate(
        line_items=line_items,
        estimated_total_cents=estimated_total,
        confidence_low_cents=confidence_low,
        confidence_high_cents=confidence_high,
        reasoning=reasoning,
    )
