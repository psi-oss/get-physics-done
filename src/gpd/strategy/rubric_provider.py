"""Physics rubric provider — builds domain-aware rubric specs for BT rater.

Implements the RubricProvider protocol from engine/extension_protocols.py.
When a physics domain is specified, extends the base rubric criteria with
physics-specific dimensions (dimensional consistency, limiting cases, etc.)
and applies domain-specific weight adjustments.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agentic_builder.engine.models import RubricSpec

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Base criteria (always present)
# ---------------------------------------------------------------------------

BASE_CRITERIA: list[str] = [
    "correctness",
    "progress",
    "quality",
    "efficiency",
    "innovation",
]

BASE_WEIGHT = 1.0

# ---------------------------------------------------------------------------
# Physics criteria (added when domain is specified)
# ---------------------------------------------------------------------------

PHYSICS_CRITERIA: list[str] = [
    "dimensional_consistency",
    "limiting_cases",
    "conservation_laws",
    "physical_plausibility",
    "literature_agreement",
]

# Domain-specific weight overrides for physics criteria.
# Keys are physics criteria names; values are weight multipliers.
# Criteria not listed get the default weight of 1.0.
DOMAIN_RUBRIC_WEIGHTS: dict[str, dict[str, float]] = {
    "qft": {
        "conservation_laws": 1.5,
        "dimensional_consistency": 1.2,
    },
    "condensed_matter": {
        "limiting_cases": 1.5,
        "physical_plausibility": 1.2,
    },
    "stat_mech": {
        "physical_plausibility": 1.3,
        "limiting_cases": 1.2,
    },
    "gr_cosmology": {
        "conservation_laws": 1.3,
        "dimensional_consistency": 1.3,
    },
}


def _build_rubric_spec(criteria: list[str], weights: list[float]) -> RubricSpec:
    """Construct a RubricSpec from criteria and weights lists."""
    from agentic_builder.engine.models import RubricSpec

    return RubricSpec(criteria=criteria, weights=weights)


class PhysicsRubricProvider:
    """Builds domain-aware rubric specs for the BT rater.

    Satisfies the ``RubricProvider`` protocol defined in
    ``agentic_builder.engine.extension_protocols``.

    When *domain* is ``None``, returns a base rubric with the five standard
    criteria (correctness, progress, quality, efficiency, innovation).

    When *domain* is specified, appends five physics-specific criteria and
    applies domain-specific weight adjustments from ``DOMAIN_RUBRIC_WEIGHTS``.
    """

    def build_rubric(self, domain: str | None) -> RubricSpec:
        """Build a rubric spec, optionally enriched with physics criteria.

        Args:
            domain: Physics subdomain (e.g. ``"qft"``, ``"condensed_matter"``).
                    ``None`` returns the base rubric only.

        Returns:
            RubricSpec with criteria names and corresponding weights.
        """
        if domain is None:
            return _build_rubric_spec(
                criteria=list(BASE_CRITERIA),
                weights=[BASE_WEIGHT] * len(BASE_CRITERIA),
            )

        # Build combined criteria list: base + physics
        criteria = list(BASE_CRITERIA) + list(PHYSICS_CRITERIA)

        # Start with uniform weights
        weights = [BASE_WEIGHT] * len(criteria)

        # Apply domain-specific overrides for physics criteria
        domain_overrides = DOMAIN_RUBRIC_WEIGHTS.get(domain, {})
        for i, criterion in enumerate(criteria):
            if criterion in domain_overrides:
                weights[i] = domain_overrides[criterion]

        logger.info(
            "physics_rubric_built",
            extra={
                "domain": domain,
                "criteria_count": len(criteria),
                "overrides_applied": len(domain_overrides),
            },
        )

        return _build_rubric_spec(criteria=criteria, weights=weights)
