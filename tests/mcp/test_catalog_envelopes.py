"""Regression coverage for schema-versioned MCP catalog envelopes."""

from __future__ import annotations

from unittest.mock import MagicMock, patch


def _assert_legacy_envelope(result: object, expected_payload: dict[str, object]) -> None:
    from gpd.mcp.servers import StableMCPEnvelope

    assert isinstance(result, StableMCPEnvelope)
    assert result["schema_version"] == 1
    assert result == expected_payload
    assert dict(result) == {"schema_version": 1, **expected_payload}


def test_protocols_success_envelope() -> None:
    from gpd.mcp.servers.protocols_server import get_protocol

    store = MagicMock()
    store.get.return_value = {
        "name": "perturbation-theory",
        "title": "Perturbation Theory Protocol",
        "domain": "core_derivation",
        "tier": 1,
        "context_cost": "high",
        "load_when": ["perturbation"],
        "steps": ["Identify small parameter"],
        "checkpoints": ["Verify limiting cases"],
        "body": "# Perturbation Theory Protocol\n",
    }

    with patch("gpd.mcp.servers.protocols_server._get_store", return_value=store):
        result = get_protocol("perturbation-theory")

    _assert_legacy_envelope(
        result,
        {
            "name": "perturbation-theory",
            "title": "Perturbation Theory Protocol",
            "domain": "core_derivation",
            "tier": 1,
            "context_cost": "high",
            "load_when": ["perturbation"],
            "steps": ["Identify small parameter"],
            "checkpoints": ["Verify limiting cases"],
            "content": "# Perturbation Theory Protocol\n",
        },
    )


def test_protocols_error_envelope() -> None:
    from gpd.mcp.servers.protocols_server import get_protocol

    with patch("gpd.mcp.servers.protocols_server._get_store", side_effect=OSError("protocol catalog offline")):
        result = get_protocol("perturbation-theory")

    _assert_legacy_envelope(result, {"error": "protocol catalog offline"})


def test_patterns_success_envelope() -> None:
    from gpd.mcp.servers.patterns_server import lookup_pattern

    listing = MagicMock()
    listing.count = 1
    pattern = MagicMock()
    pattern.model_dump.return_value = {"id": "p1", "domain": "qft"}
    listing.patterns = [pattern]
    listing.library_exists = True

    with patch("gpd.mcp.servers.patterns_server.pattern_list", return_value=listing):
        result = lookup_pattern(domain="qft")

    _assert_legacy_envelope(
        result,
        {
            "count": 1,
            "patterns": [{"id": "p1", "domain": "qft"}],
            "query": None,
            "library_exists": True,
        },
    )


def test_patterns_error_envelope() -> None:
    from gpd.mcp.servers.patterns_server import lookup_pattern

    with patch("gpd.mcp.servers.patterns_server.pattern_list", side_effect=OSError("pattern store offline")):
        result = lookup_pattern(domain="qft")

    _assert_legacy_envelope(result, {"error": "pattern store offline"})


def test_errors_success_envelope() -> None:
    from gpd.mcp.servers.errors_mcp import get_error_class

    store = MagicMock()
    store.get.return_value = {
        "id": 1,
        "name": "Wrong CG coefficients",
        "description": "Incorrect Clebsch-Gordan coefficients",
        "detection_strategy": "Verify against angular momentum identities",
        "example": "3j-symbol mismatch",
        "domain": "core",
        "source_file": "llm-errors-core.md",
    }

    with patch("gpd.mcp.servers.errors_mcp._get_store", return_value=store):
        result = get_error_class(1)

    _assert_legacy_envelope(
        result,
        {
            "id": 1,
            "name": "Wrong CG coefficients",
            "description": "Incorrect Clebsch-Gordan coefficients",
            "detection_strategy": "Verify against angular momentum identities",
            "example": "3j-symbol mismatch",
            "domain": "core",
            "source_file": "llm-errors-core.md",
        },
    )


def test_errors_error_envelope() -> None:
    from gpd.mcp.servers.errors_mcp import get_error_class

    with patch("gpd.mcp.servers.errors_mcp._get_store", side_effect=OSError("error catalog offline")):
        result = get_error_class(1)

    _assert_legacy_envelope(result, {"error": "error catalog offline"})


def test_conventions_success_envelope() -> None:
    from gpd.mcp.servers.conventions_server import KNOWN_CONVENTIONS, SUBFIELD_DEFAULTS, subfield_defaults

    result = subfield_defaults("qft")

    defaults = SUBFIELD_DEFAULTS["qft"]
    _assert_legacy_envelope(
        result,
        {
            "found": True,
            "domain": "qft",
            "defaults": defaults,
            "field_count": len(defaults),
            "unset_fields": [field for field in KNOWN_CONVENTIONS if field not in defaults],
            "message": (
                f"Recommended conventions for qft. "
                f"Sets {len(defaults)} of {len(KNOWN_CONVENTIONS)} standard fields."
            ),
        },
    )


def test_conventions_error_envelope() -> None:
    from gpd.mcp.servers.conventions_server import convention_set

    with patch(
        "gpd.mcp.servers.conventions_server._update_lock_in_project",
        side_effect=TimeoutError("lock acquisition timed out"),
    ):
        result = convention_set("/tmp/project", "metric_signature", "(+,-,-,-)")

    _assert_legacy_envelope(result, {"error": "lock acquisition timed out"})
