"""Regression tests for extras.py bug fixes (round 4 audit).

Fix 1: question_list / calculation_list return type annotation corrected to list[str | dict].
Fix 2: double-bounded ranges with << / >> operators now apply "much less/greater" semantics.
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Fix 1: question_list and calculation_list return type annotations
# ---------------------------------------------------------------------------


class TestQuestionListMixedTypes:
    """question_list should return items faithfully, including dicts."""

    def test_returns_mixed_str_and_dict(self) -> None:
        """question_list returns correctly with mixed str and dict items."""
        from gpd.core.extras import question_list

        state: dict = {
            "open_questions": [
                "Why does the coupling diverge?",
                {"text": "Is the vacuum stable?", "priority": "high"},
                "What about unitarity?",
            ]
        }
        result = question_list(state)
        assert len(result) == 3
        assert result[0] == "Why does the coupling diverge?"
        assert isinstance(result[1], dict)
        assert result[1]["text"] == "Is the vacuum stable?"
        assert result[2] == "What about unitarity?"

    def test_returns_empty_list_when_no_questions(self) -> None:
        """question_list returns [] when state has no open_questions key."""
        from gpd.core.extras import question_list

        assert question_list({}) == []


class TestCalculationListMixedTypes:
    """calculation_list should return items faithfully, including dicts."""

    def test_returns_mixed_str_and_dict(self) -> None:
        """calculation_list returns correctly with mixed str and dict items."""
        from gpd.core.extras import calculation_list

        state: dict = {
            "active_calculations": [
                "Compute one-loop correction",
                {"text": "Evaluate path integral", "status": "in-progress"},
                "Check Ward identity",
            ]
        }
        result = calculation_list(state)
        assert len(result) == 3
        assert result[0] == "Compute one-loop correction"
        assert isinstance(result[1], dict)
        assert result[1]["text"] == "Evaluate path integral"
        assert result[2] == "Check Ward identity"

    def test_returns_empty_list_when_no_calculations(self) -> None:
        """calculation_list returns [] when state has no active_calculations key."""
        from gpd.core.extras import calculation_list

        assert calculation_list({}) == []


# ---------------------------------------------------------------------------
# Fix 2: << / >> operators in double-bounded ranges
# ---------------------------------------------------------------------------


class TestDoubleBoundedMuchLessGreater:
    """Double-bounded ranges with << / >> should apply strict thresholds."""

    def test_val_not_much_greater_than_lower_bound(self) -> None:
        """'0.1 << x << 100' with val=1.0: val is NOT >> 0.1 by the strict threshold.

        Lower bound: 0.1 << x means val >> 0.1.
          val > 10 * 0.1 = 1.0? No (not strictly greater). => not valid
          val > 2 * 0.1 = 0.2? Yes. => marginal
        Upper bound: x << 100 means val << 100.
          abs(1.0) < 0.1 * 100 = 10? Yes. => valid
        Worst of (marginal, valid) = marginal.
        Before the fix this returned "valid" (plain < semantics).
        """
        from gpd.core.extras import check_approximation_validity

        result = check_approximation_validity(val=1.0, range_str="0.1 << x << 100")
        assert result == "marginal"

    def test_val_below_lower_bound_invalid(self) -> None:
        """'0.1 << x << 100' with val=0.005: val is below the lower bound entirely.

        Lower bound: 0.1 << x means val >> 0.1.
          val=0.005 > 10 * 0.1 = 1.0? No.
          val=0.005 > 2 * 0.1 = 0.2? No. => invalid
        """
        from gpd.core.extras import check_approximation_validity

        result = check_approximation_validity(val=0.005, range_str="0.1 << x << 100")
        assert result == "invalid"

    def test_simple_operators_unchanged(self) -> None:
        """'1 < x < 10' with val=5 should return 'valid' (no << or >> operators)."""
        from gpd.core.extras import check_approximation_validity

        result = check_approximation_validity(val=5, range_str="1 < x < 10")
        assert result == "valid"

    def test_wide_range_valid(self) -> None:
        """'0.01 << x << 1000' with val=0.5 should return 'valid'.

        Lower: val=0.5 > 10 * 0.01 = 0.1 => valid.
        Upper: abs(0.5) < 0.1 * 1000 = 100 => valid.
        Both valid => valid.
        """
        from gpd.core.extras import check_approximation_validity

        result = check_approximation_validity(val=0.5, range_str="0.01 << x << 1000")
        assert result == "valid"

    def test_marginal_near_threshold(self) -> None:
        """Value near the 'much greater' threshold should be marginal."""
        from gpd.core.extras import check_approximation_validity

        # 1 << x << 1000, val=5
        # Lower: val > 10*1 = 10? No. val > 2*1 = 2? Yes => marginal.
        # Upper: abs(5) < 0.1*1000 = 100? Yes => valid.
        # Worst = marginal.
        result = check_approximation_validity(val=5, range_str="1 << x << 1000")
        assert result == "marginal"

    def test_clearly_invalid_below_lower(self) -> None:
        """Value not even marginally greater than lower bound should be invalid."""
        from gpd.core.extras import check_approximation_validity

        # 10 << x << 1000, val=5
        # Lower: val > 10*10 = 100? No. val > 2*10 = 20? No => invalid.
        result = check_approximation_validity(val=5, range_str="10 << x << 1000")
        assert result == "invalid"
