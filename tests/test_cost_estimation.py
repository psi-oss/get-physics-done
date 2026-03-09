"""TDD tests for cost estimation domain functions.

Tests validate that cost estimates produce valid itemized breakdowns
with confidence ranges using integer cents arithmetic.
"""

from __future__ import annotations

from gpd.exp.domain.cost_estimation import estimate_experiment_cost


class TestCostEstimation:
    """Tests for estimate_experiment_cost."""

    def test_basic_cost_estimate(self) -> None:
        """Basic cost estimate returns CostEstimate with valid confidence range."""
        result = estimate_experiment_cost(sample_size=30, base_bounty_price_cents=500)
        assert result.confidence_low_cents <= result.estimated_total_cents <= result.confidence_high_cents

    def test_confidence_range_ordering(self) -> None:
        """confidence_low <= estimated_total <= confidence_high always."""
        result = estimate_experiment_cost(sample_size=100, base_bounty_price_cents=1000)
        assert result.confidence_low_cents <= result.estimated_total_cents
        assert result.estimated_total_cents <= result.confidence_high_cents

    def test_zero_retry_probability(self) -> None:
        """retry_probability=0.0 means no retries: low == total == high."""
        result = estimate_experiment_cost(
            sample_size=30,
            base_bounty_price_cents=500,
            retry_probability=0.0,
        )
        assert result.estimated_total_cents == result.confidence_low_cents
        assert result.estimated_total_cents == result.confidence_high_cents

    def test_line_items_sum(self) -> None:
        """Sum of line_item subtotals equals estimated_total_cents."""
        result = estimate_experiment_cost(sample_size=50, base_bounty_price_cents=300)
        total_from_items = sum(item.subtotal_cents for item in result.line_items)
        assert total_from_items == result.estimated_total_cents

    def test_integer_cents(self) -> None:
        """All amounts are integers, no float contamination."""
        result = estimate_experiment_cost(sample_size=33, base_bounty_price_cents=777)
        assert isinstance(result.estimated_total_cents, int)
        assert isinstance(result.confidence_low_cents, int)
        assert isinstance(result.confidence_high_cents, int)
        for item in result.line_items:
            assert isinstance(item.subtotal_cents, int)
            assert isinstance(item.unit_price_cents, int)
            assert isinstance(item.quantity, int)

    def test_display_total_format(self) -> None:
        """display_total property contains '$' and '+/-'."""
        result = estimate_experiment_cost(sample_size=30, base_bounty_price_cents=500)
        display = result.display_total
        assert "$" in display
        assert "+/-" in display
