"""Tests for the compare_phase_numbers zero-padding bug fix.

The fallback comparison must only compare non-numeric suffixes, not the
full original strings.  This ensures that numerically identical phases
with different zero-padding (e.g. "02" vs "2") are treated as equal.
"""

from __future__ import annotations

from gpd.core.utils import compare_phase_numbers


class TestZeroPaddingEquality:
    """Zero-padded phase numbers that are numerically identical must compare equal."""

    def test_zero_padded_phases_are_equal(self) -> None:
        assert compare_phase_numbers("02", "2") == 0

    def test_zero_padded_symmetric(self) -> None:
        assert compare_phase_numbers("2", "02") == 0


class TestBasicOrdering:
    """Standard numeric ordering must still work after the fix."""

    def test_less_than(self) -> None:
        assert compare_phase_numbers("1", "2") < 0

    def test_identical_subphases(self) -> None:
        assert compare_phase_numbers("2.1", "2.1") == 0

    def test_subphase_ordering(self) -> None:
        assert compare_phase_numbers("2.1", "2.2") < 0

    def test_numeric_not_lexicographic(self) -> None:
        assert compare_phase_numbers("10", "2") > 0


class TestSuffixComparison:
    """Non-numeric suffixes should still be compared lexicographically."""

    def test_different_suffixes(self) -> None:
        assert compare_phase_numbers("1a", "1b") < 0

    def test_same_suffix_is_equal(self) -> None:
        assert compare_phase_numbers("1a", "1a") == 0
