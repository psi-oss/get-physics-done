"""Tests for gpd.strategy.router — ReferenceRouter protocol/domain/error routing."""

from __future__ import annotations

from unittest.mock import MagicMock, PropertyMock

import pytest

from gpd.core.constants import REF_DEFAULT_ERROR_CATALOG, REF_SUBFIELD_GUIDE_FALLBACK, UNIVERSAL_ERROR_IDS
from gpd.strategy.loader import ProtocolEntry, ReferenceMeta
from gpd.strategy.router import (
    COMPUTATION_TO_PROTOCOL,
    DOMAIN_TO_VERIFICATION,
    ERROR_KEYWORD_TO_CATALOG,
    ReferenceRouter,
    _score_text_match,
    _tokenize,
    get_router,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_loader(protocol_index=None, search_results=None):
    """Build a mock ReferenceLoader."""
    loader = MagicMock()
    type(loader).protocol_index = PropertyMock(return_value=protocol_index or {})
    loader.search_by_keywords.return_value = search_results or []
    loader._protocol_names = {}
    return loader


# ---------------------------------------------------------------------------
# route_protocol
# ---------------------------------------------------------------------------


class TestRouteProtocol:
    def test_exact_match(self):
        router = ReferenceRouter(loader=_mock_loader())
        assert router.route_protocol("perturbation") == "perturbation-theory"

    def test_case_insensitive(self):
        router = ReferenceRouter(loader=_mock_loader())
        assert router.route_protocol("PATH INTEGRAL") == "path-integrals"

    def test_substring_match(self):
        router = ReferenceRouter(loader=_mock_loader())
        result = router.route_protocol("loop integral calculation")
        assert result == "perturbation-theory"

    def test_no_match_returns_none(self):
        router = ReferenceRouter(loader=_mock_loader())
        result = router.route_protocol("basket weaving")
        assert result is None

    def test_falls_back_to_protocol_index(self):
        index = {
            "custom-method": ProtocolEntry(
                name="Custom Method",
                file="protocols/custom-method.md",
                when_to_use="custom exotic physics method",
            )
        }
        loader = _mock_loader(protocol_index=index)
        loader._protocol_names = {"custom-method": "protocols/custom-method"}
        router = ReferenceRouter(loader=loader)
        result = router.route_protocol("custom exotic physics")
        assert result is not None

    @pytest.mark.parametrize(
        "input_type,expected_protocol",
        [
            ("renormalization", "renormalization-group"),
            ("eft", "effective-field-theory"),
            ("monte carlo", "monte-carlo"),
            ("wkb", "wkb-semiclassical"),
            ("lattice qcd", "lattice-gauge-theory"),
            ("susy", "supersymmetry"),
            ("ads/cft", "holography-ads-cft"),
        ],
    )
    def test_known_mappings(self, input_type: str, expected_protocol: str):
        router = ReferenceRouter(loader=_mock_loader())
        assert router.route_protocol(input_type) == expected_protocol

    def test_whitespace_stripped(self):
        router = ReferenceRouter(loader=_mock_loader())
        assert router.route_protocol("  renormalization  ") == "renormalization-group"


# ---------------------------------------------------------------------------
# route_verification
# ---------------------------------------------------------------------------


class TestRouteVerification:
    def test_exact_match(self):
        router = ReferenceRouter(loader=_mock_loader())
        assert router.route_verification("qft") == ["qft"]

    def test_substring_match(self):
        router = ReferenceRouter(loader=_mock_loader())
        result = router.route_verification("condensed matter physics")
        assert "condmat" in result

    def test_no_match_returns_empty(self):
        router = ReferenceRouter(loader=_mock_loader())
        assert router.route_verification("basket weaving") == []

    @pytest.mark.parametrize(
        "domain,expected",
        [
            ("cosmology", ["gr-cosmology"]),
            ("nuclear", ["nuclear-particle"]),
            ("quantum information", ["quantum-info"]),
        ],
    )
    def test_known_domains(self, domain: str, expected: list[str]):
        router = ReferenceRouter(loader=_mock_loader())
        assert router.route_verification(domain) == expected


# ---------------------------------------------------------------------------
# route_errors
# ---------------------------------------------------------------------------


class TestRouteErrors:
    def test_keyword_match(self):
        router = ReferenceRouter(loader=_mock_loader())
        result = router.route_errors("green function calculation")
        assert 3 in result

    def test_multiple_keywords(self):
        router = ReferenceRouter(loader=_mock_loader())
        result = router.route_errors("cg coefficient and green function")
        assert 1 in result
        assert 3 in result

    def test_no_match_returns_universal(self):
        router = ReferenceRouter(loader=_mock_loader())
        result = router.route_errors("something generic")
        assert set(result) == set(UNIVERSAL_ERROR_IDS)

    def test_result_is_sorted(self):
        router = ReferenceRouter(loader=_mock_loader())
        result = router.route_errors("partition function and angular momentum")
        assert result == sorted(result)


# ---------------------------------------------------------------------------
# route_errors_to_catalogs
# ---------------------------------------------------------------------------


class TestRouteErrorsToCatalogs:
    def test_known_keyword(self):
        router = ReferenceRouter(loader=_mock_loader())
        result = router.route_errors_to_catalogs("green function")
        assert "llm-errors-core" in result

    def test_no_match_returns_default(self):
        router = ReferenceRouter(loader=_mock_loader())
        result = router.route_errors_to_catalogs("generic thing")
        assert result == [REF_DEFAULT_ERROR_CATALOG]

    def test_multiple_catalogs(self):
        router = ReferenceRouter(loader=_mock_loader())
        result = router.route_errors_to_catalogs("nuclear shell and superconductivity")
        assert "llm-errors-deep" in result


# ---------------------------------------------------------------------------
# route_subfield
# ---------------------------------------------------------------------------


class TestRouteSubfield:
    def test_exact_match(self):
        router = ReferenceRouter(loader=_mock_loader())
        result = router.route_subfield("qft")
        assert result is not None
        assert "qft" in result

    def test_no_match_returns_fallback(self):
        router = ReferenceRouter(loader=_mock_loader())
        result = router.route_subfield("basket weaving")
        assert result == REF_SUBFIELD_GUIDE_FALLBACK

    def test_substring_match(self):
        router = ReferenceRouter(loader=_mock_loader())
        result = router.route_subfield("condensed matter physics")
        assert result is not None
        assert "condensed-matter" in result


# ---------------------------------------------------------------------------
# route_all
# ---------------------------------------------------------------------------


class TestRouteAll:
    def test_returns_all_keys(self):
        router = ReferenceRouter(loader=_mock_loader())
        result = router.route_all("perturbation", "qft")
        assert set(result.keys()) == {"protocols", "verification", "errors", "error_ids", "subfield"}

    def test_protocol_and_domain(self):
        router = ReferenceRouter(loader=_mock_loader())
        result = router.route_all("path integral", "cosmology")
        assert "path-integrals" in result["protocols"]
        assert "gr-cosmology" in result["verification"]


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------


class TestSearch:
    def test_delegates_to_loader(self):
        meta = MagicMock(spec=ReferenceMeta)
        meta.name = "my-ref"
        loader = _mock_loader(search_results=[meta])
        router = ReferenceRouter(loader=loader)
        result = router.search(["perturbation"])
        assert result == ["my-ref"]
        loader.search_by_keywords.assert_called_once_with(["perturbation"])


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


class TestHelpers:
    def test_tokenize(self):
        tokens = _tokenize("Path Integral Calculation")
        assert "path" in tokens
        assert "integral" in tokens
        assert "calculation" in tokens

    def test_score_text_match(self):
        tokens = {"path", "integral"}
        assert _score_text_match(tokens, "path integral methods") == 2
        assert _score_text_match(tokens, "completely unrelated") == 0


# ---------------------------------------------------------------------------
# get_router factory
# ---------------------------------------------------------------------------


class TestGetRouter:
    def test_returns_router_instance(self):
        loader = _mock_loader()
        router = get_router(loader)
        assert isinstance(router, ReferenceRouter)


# ---------------------------------------------------------------------------
# Routing table coverage
# ---------------------------------------------------------------------------


class TestRoutingTableCompleteness:
    def test_computation_table_values_are_strings(self):
        for key, val in COMPUTATION_TO_PROTOCOL.items():
            assert isinstance(key, str)
            assert isinstance(val, str)

    def test_domain_table_values_are_lists(self):
        for key, val in DOMAIN_TO_VERIFICATION.items():
            assert isinstance(key, str)
            assert isinstance(val, list)
            assert all(isinstance(v, str) for v in val)

    def test_error_catalog_table_values_are_strings(self):
        for key, val in ERROR_KEYWORD_TO_CATALOG.items():
            assert isinstance(key, str)
            assert isinstance(val, str)
