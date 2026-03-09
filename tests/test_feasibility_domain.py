"""TDD tests for feasibility pre-screen and ethics keyword domain functions.

Tests validate the Layer 1 keyword scanning for ethics flags and
intractability detection.
"""

from __future__ import annotations

from gpd.exp.domain.ethics_rules import check_ethics_keywords
from gpd.exp.domain.feasibility import keyword_feasibility_prescreen


class TestEthicsKeywords:
    """Tests for check_ethics_keywords."""

    def test_ethics_keyword_catches_minors(self) -> None:
        """'children' in question triggers ethics flag."""
        result = check_ethics_keywords("test with children", "")
        assert len(result) > 0
        assert any("children" in pattern for pattern in result)

    def test_ethics_keyword_catches_pii(self) -> None:
        """'social security' in procedure triggers flag."""
        result = check_ethics_keywords("", "collect social security numbers")
        assert len(result) > 0
        assert any("social" in pattern for pattern in result)

    def test_ethics_keyword_clean(self) -> None:
        """Benign question + procedure returns empty list."""
        result = check_ethics_keywords(
            "Does ambient temperature affect reaction time?",
            "Participants press a button when they see a light",
        )
        assert result == []


class TestFeasibilityPrescreen:
    """Tests for keyword_feasibility_prescreen."""

    def test_feasibility_prescreen_clean(self) -> None:
        """Clean research question returns empty list."""
        result = keyword_feasibility_prescreen("Does the color of a cup affect perceived temperature of coffee?")
        assert result == []
