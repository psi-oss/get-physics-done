"""Tests for gpd.strategy.rubric_provider — PhysicsRubricProvider."""

from __future__ import annotations

import pytest

from gpd.strategy.rubric_provider import (
    BASE_CRITERIA,
    BASE_WEIGHT,
    DOMAIN_RUBRIC_WEIGHTS,
    PHYSICS_CRITERIA,
    PhysicsRubricProvider,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


class TestConstants:
    def test_base_criteria_count(self):
        assert len(BASE_CRITERIA) == 5

    def test_physics_criteria_count(self):
        assert len(PHYSICS_CRITERIA) == 5

    def test_no_overlap(self):
        assert set(BASE_CRITERIA).isdisjoint(set(PHYSICS_CRITERIA))

    def test_domain_weights_only_reference_physics_criteria(self):
        for domain, overrides in DOMAIN_RUBRIC_WEIGHTS.items():
            for criterion in overrides:
                assert criterion in PHYSICS_CRITERIA, f"Domain '{domain}' references unknown criterion '{criterion}'"


# ---------------------------------------------------------------------------
# PhysicsRubricProvider — no domain (base only)
# ---------------------------------------------------------------------------


class TestBasicRubric:
    def test_no_domain_returns_base_only(self):
        provider = PhysicsRubricProvider()
        rubric = provider.build_rubric(domain=None)
        assert rubric.criteria == BASE_CRITERIA
        assert rubric.weights == [BASE_WEIGHT] * len(BASE_CRITERIA)

    def test_no_domain_length_match(self):
        provider = PhysicsRubricProvider()
        rubric = provider.build_rubric(domain=None)
        assert len(rubric.criteria) == len(rubric.weights)


# ---------------------------------------------------------------------------
# PhysicsRubricProvider — with domain
# ---------------------------------------------------------------------------


class TestPhysicsRubric:
    def test_domain_includes_physics_criteria(self):
        provider = PhysicsRubricProvider()
        rubric = provider.build_rubric(domain="qft")
        assert len(rubric.criteria) == len(BASE_CRITERIA) + len(PHYSICS_CRITERIA)
        for c in PHYSICS_CRITERIA:
            assert c in rubric.criteria

    def test_domain_weights_applied(self):
        provider = PhysicsRubricProvider()
        rubric = provider.build_rubric(domain="qft")
        qft_overrides = DOMAIN_RUBRIC_WEIGHTS["qft"]
        for criterion, weight in zip(rubric.criteria, rubric.weights, strict=False):
            if criterion in qft_overrides:
                assert weight == qft_overrides[criterion]

    def test_unknown_domain_uses_uniform_weights(self):
        provider = PhysicsRubricProvider()
        rubric = provider.build_rubric(domain="underwater_basket_physics")
        assert all(w == BASE_WEIGHT for w in rubric.weights)

    def test_length_match(self):
        provider = PhysicsRubricProvider()
        rubric = provider.build_rubric(domain="condensed_matter")
        assert len(rubric.criteria) == len(rubric.weights)

    @pytest.mark.parametrize("domain", list(DOMAIN_RUBRIC_WEIGHTS.keys()))
    def test_all_known_domains(self, domain: str):
        provider = PhysicsRubricProvider()
        rubric = provider.build_rubric(domain=domain)
        assert len(rubric.criteria) == len(BASE_CRITERIA) + len(PHYSICS_CRITERIA)
        assert len(rubric.weights) == len(rubric.criteria)

    def test_base_criteria_come_first(self):
        provider = PhysicsRubricProvider()
        rubric = provider.build_rubric(domain="qft")
        assert rubric.criteria[: len(BASE_CRITERIA)] == BASE_CRITERIA

    def test_physics_criteria_come_after_base(self):
        provider = PhysicsRubricProvider()
        rubric = provider.build_rubric(domain="qft")
        assert rubric.criteria[len(BASE_CRITERIA) :] == PHYSICS_CRITERIA

    def test_non_overridden_physics_criteria_get_base_weight(self):
        provider = PhysicsRubricProvider()
        rubric = provider.build_rubric(domain="qft")
        qft_overrides = DOMAIN_RUBRIC_WEIGHTS["qft"]
        for criterion, weight in zip(rubric.criteria, rubric.weights, strict=False):
            if criterion in PHYSICS_CRITERIA and criterion not in qft_overrides:
                assert weight == BASE_WEIGHT
