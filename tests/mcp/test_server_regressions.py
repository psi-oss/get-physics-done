"""Behavior-focused MCP server regression coverage."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def test_parse_table_rows_handles_escaped_pipes() -> None:
    from gpd.mcp.servers.errors_mcp import _parse_table_rows

    rows = _parse_table_rows("| 1 | Foo \\| Bar | Baz |")

    assert rows == [["1", "Foo | Bar", "Baz"]]


def test_parse_table_rows_skips_separator_rows() -> None:
    from gpd.mcp.servers.errors_mcp import _parse_table_rows

    rows = _parse_table_rows("| Header1 | Header2 |\n|---|---|\n| val1 | val2 |")

    assert len(rows) == 2


def test_symmetry_short_names_do_not_substring_match_longer_strategies() -> None:
    from gpd.mcp.servers.verification_server import _symmetry_check_inner

    time_reversal = _symmetry_check_inner("expr", ["T"])["results"][0]
    charge = _symmetry_check_inner("expr", ["C"])["results"][0]
    lorentz = _symmetry_check_inner("expr", ["Lorentz invariance"])["results"][0]

    assert time_reversal.get("matched_type") != "lorentz"
    assert charge.get("matched_type") != "conformal"
    assert lorentz.get("matched_type") == "lorentz"


def test_traceability_responses_always_include_verification_checks() -> None:
    from gpd.mcp.servers.errors_mcp import ErrorStore, get_traceability

    with patch("gpd.mcp.servers.errors_mcp._get_store") as mock_store_fn:
        store = MagicMock(spec=ErrorStore)
        store.get.return_value = {"id": 999, "name": "TestError"}
        store.get_traceability.return_value = None
        mock_store_fn.return_value = store

        no_data = get_traceability(999)

    with patch("gpd.mcp.servers.errors_mcp._get_store") as mock_store_fn:
        store = MagicMock(spec=ErrorStore)
        store.get.return_value = {"id": 1, "name": "TestError"}
        store.get_traceability.return_value = {"Dimensional Analysis": "direct"}
        mock_store_fn.return_value = store

        with_data = get_traceability(1)

    assert no_data["verification_checks"] == {}
    assert with_data["verification_checks"] == {"Dimensional Analysis": "direct"}


def test_errors_mcp_returns_error_dict_on_store_os_error() -> None:
    from gpd.mcp.servers.errors_mcp import get_error_class

    with patch("gpd.mcp.servers.errors_mcp._get_store") as mock_store_fn:
        store = MagicMock()
        store.get.side_effect = OSError("cannot read catalog")
        mock_store_fn.return_value = store

        result = get_error_class(1)

    assert "error" in result
    assert "cannot read catalog" in result["error"]


def test_convention_handlers_return_error_for_invalid_lock_data() -> None:
    from gpd.mcp.servers.conventions_server import (
        assert_convention_validate,
        convention_check,
        convention_diff,
    )

    assert "error" in convention_check({"custom_conventions": "not-a-dict"})
    assert "error" in convention_diff({"custom_conventions": "not-a-dict"}, {})
    assert "error" in assert_convention_validate("content", {"custom_conventions": 123})


def test_convention_set_returns_error_on_timeout(tmp_path: Path) -> None:
    from gpd.mcp.servers.conventions_server import convention_set

    planning = tmp_path / ".gpd"
    planning.mkdir()
    (planning / "state.json").write_text("{}", encoding="utf-8")

    with patch(
        "gpd.mcp.servers.conventions_server._update_lock_in_project",
        side_effect=TimeoutError("lock acquisition timed out"),
    ):
        result = convention_set(str(tmp_path), "metric_signature", "(+,-,-,-)")

    assert "error" in result
    assert "timed out" in result["error"]


def test_add_pattern_returns_error_on_pattern_error() -> None:
    from gpd.core.errors import PatternError
    from gpd.mcp.servers.patterns_server import add_pattern

    with patch("gpd.mcp.servers.patterns_server.pattern_add", side_effect=PatternError("Invalid domain")):
        result = add_pattern(domain="invalid", title="Test")

    assert "error" in result
    assert "Invalid domain" in result["error"]


def test_lookup_pattern_filters_keyword_matches_by_domain() -> None:
    from gpd.mcp.servers.patterns_server import lookup_pattern

    match_qft = MagicMock()
    match_qft.domain = "qft"
    match_qft.model_dump.return_value = {"id": "p1", "domain": "qft"}

    match_other = MagicMock()
    match_other.domain = "condensed-matter"
    match_other.model_dump.return_value = {"id": "p2", "domain": "condensed-matter"}

    mock_result = MagicMock()
    mock_result.count = 2
    mock_result.matches = [match_qft, match_other]
    mock_result.query = "sign"
    mock_result.library_exists = True

    with patch("gpd.mcp.servers.patterns_server.pattern_search", return_value=mock_result):
        result = lookup_pattern(keywords="sign", domain="qft")

    assert result["count"] == 1
    assert result["patterns"][0]["domain"] == "qft"


@pytest.mark.parametrize("side_effect", [OSError("permission denied"), pytest.param(None, id="pattern-error")])
def test_lookup_pattern_returns_error_for_backend_failures(side_effect: Exception | None) -> None:
    from gpd.core.errors import PatternError
    from gpd.mcp.servers.patterns_server import lookup_pattern

    if side_effect is None:
        side_effect = PatternError("library corrupt")

    with patch("gpd.mcp.servers.patterns_server.pattern_list", side_effect=side_effect):
        result = lookup_pattern(domain="qft")

    assert "error" in result


def test_patterns_server_exposes_classical_mechanics_domain() -> None:
    from gpd.mcp.servers.verification_server import DOMAIN_CHECKLISTS

    checks = DOMAIN_CHECKLISTS["classical_mechanics"]

    assert "classical_mechanics" in DOMAIN_CHECKLISTS
    assert any("energy" in check["check"].lower() or "hamilton" in check["check"].lower() for check in checks)


def test_verification_run_check_returns_error_envelope_on_backend_failure() -> None:
    from gpd.mcp.servers.verification_server import run_check

    with patch("gpd.mcp.servers.verification_server.get_verification_check", side_effect=OSError("catalog offline")):
        result = run_check("5.1", "qft", "artifact")

    assert result == {"error": "catalog offline", "schema_version": 1}


def test_verification_run_contract_check_returns_error_envelope_on_backend_failure() -> None:
    from gpd.mcp.servers.verification_server import run_contract_check

    with patch("gpd.mcp.servers.verification_server.get_verification_check", side_effect=OSError("catalog offline")):
        result = run_contract_check({"check_key": "contract.limit_recovery"})

    assert result == {"error": "catalog offline", "schema_version": 1}


def test_verification_suggest_contract_checks_returns_error_envelope_on_backend_failure() -> None:
    from gpd.mcp.servers.verification_server import suggest_contract_checks

    contract = {
        "schema_version": 1,
        "scope": {"question": "Q?", "in_scope": ["benchmark recovery"]},
        "acceptance_tests": [
            {
                "id": "test-benchmark",
                "subject": "claim-main",
                "kind": "benchmark",
                "procedure": "Compare against a benchmark",
                "pass_condition": "Agreement",
            }
        ],
        "claims": [{"id": "claim-main", "statement": "Recover the benchmark"}],
        "uncertainty_markers": {
            "weakest_anchors": ["benchmark meaning"],
            "disconfirming_observations": ["benchmark mismatch"],
        },
    }

    with patch("gpd.mcp.servers.verification_server.get_verification_check", side_effect=OSError("catalog offline")):
        result = suggest_contract_checks(contract)

    assert result == {"error": "catalog offline", "schema_version": 1}


def test_verification_get_checklist_returns_error_envelope_on_backend_failure() -> None:
    from gpd.mcp.servers.verification_server import get_checklist

    with patch("gpd.mcp.servers.verification_server.list_verification_checks", side_effect=OSError("catalog offline")):
        result = get_checklist("qft")

    assert result == {"error": "catalog offline", "schema_version": 1}


def test_verification_get_bundle_checklist_returns_error_envelope_on_backend_failure() -> None:
    from gpd.mcp.servers.verification_server import get_bundle_checklist

    with patch("gpd.mcp.servers.verification_server.get_protocol_bundle", side_effect=OSError("bundle store offline")):
        result = get_bundle_checklist(["stat-mech-simulation"])

    assert result == {"error": "bundle store offline", "schema_version": 1}


def test_pattern_lookup_tolerates_missing_default_library(tmp_path: Path) -> None:
    import gpd.mcp.servers.patterns_server as patterns_server

    original_root = patterns_server._DEFAULT_PATTERNS_ROOT
    patterns_server._DEFAULT_PATTERNS_ROOT = tmp_path / "missing"
    try:
        result = patterns_server.lookup_pattern(domain="qft")
    finally:
        patterns_server._DEFAULT_PATTERNS_ROOT = original_root

    assert isinstance(result, dict)


def test_protocol_store_defaults_invalid_tier_for_sorting(tmp_path: Path) -> None:
    from gpd.mcp.servers.protocols_server import ProtocolStore

    protocols_dir = tmp_path / "protocols"
    protocols_dir.mkdir()
    (protocols_dir / "bad-tier.md").write_text(
        "---\n"
        "tier: high\n"
        "load_when:\n"
        "  - asymptotic\n"
        "---\n"
        "# Bad Tier\n"
        "- First step\n",
        encoding="utf-8",
    )
    (protocols_dir / "good-tier.md").write_text(
        "---\n"
        "tier: 1\n"
        "load_when:\n"
        "  - perturbative\n"
        "---\n"
        "# Good Tier\n"
        "- First step\n",
        encoding="utf-8",
    )

    store = ProtocolStore(protocols_dir)
    listed = store.list_all()

    assert [protocol["name"] for protocol in listed] == ["good-tier", "bad-tier"]
    assert listed[1]["tier"] == 2


def test_protocol_not_found_tolerates_invalid_tier_catalog(tmp_path: Path) -> None:
    from gpd.mcp.servers.protocols_server import ProtocolStore, get_protocol

    protocols_dir = tmp_path / "protocols"
    protocols_dir.mkdir()
    (protocols_dir / "bad-tier.md").write_text(
        "---\n"
        "tier: high\n"
        "---\n"
        "# Bad Tier\n"
        "- First step\n",
        encoding="utf-8",
    )
    store = ProtocolStore(protocols_dir)

    with patch("gpd.mcp.servers.protocols_server._get_store", return_value=store):
        result = get_protocol("missing-protocol")

    assert result["error"] == "Protocol 'missing-protocol' not found"
    assert result["available"] == ["bad-tier"]
