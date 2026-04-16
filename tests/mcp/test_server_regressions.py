"""Behavior-focused MCP server regression coverage."""

from __future__ import annotations

import importlib
import json
import logging
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import anyio
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


def test_error_store_rejects_missing_authoritative_catalog(tmp_path: Path) -> None:
    from gpd.mcp.servers.errors_mcp import ErrorStore

    with patch("gpd.mcp.servers.errors_mcp.ERROR_CATALOG_FILES", ["verification/errors/missing.md"]):
        with pytest.raises(OSError, match="Error catalog not found"):
            ErrorStore(tmp_path)


def test_error_store_rejects_duplicate_error_ids(tmp_path: Path) -> None:
    from gpd.mcp.servers.errors_mcp import ErrorStore

    errors_dir = tmp_path / "verification" / "errors"
    errors_dir.mkdir(parents=True)
    (errors_dir / "catalog-a.md").write_text(
        "| # | Error Class | Description | Detection Strategy | Example |\n"
        "|---|---|---|---|---|\n"
        "| 1 | Foo | First description | Detect A | Example A |\n",
        encoding="utf-8",
    )
    (errors_dir / "catalog-b.md").write_text(
        "| # | Error Class | Description | Detection Strategy | Example |\n"
        "|---|---|---|---|---|\n"
        "| 1 | Bar | Second description | Detect B | Example B |\n",
        encoding="utf-8",
    )

    with patch(
        "gpd.mcp.servers.errors_mcp.ERROR_CATALOG_FILES",
        ["verification/errors/catalog-a.md", "verification/errors/catalog-b.md"],
    ), patch("gpd.mcp.servers.errors_mcp.TRACEABILITY_FILE", "verification/errors/traceability.md"):
        with pytest.raises(ValueError, match="Duplicate error class id 1"):
            ErrorStore(tmp_path)


def test_error_store_rejects_duplicate_traceability_rows(tmp_path: Path) -> None:
    from gpd.mcp.servers.errors_mcp import ErrorStore

    errors_dir = tmp_path / "verification" / "errors"
    errors_dir.mkdir(parents=True)
    (errors_dir / "catalog.md").write_text(
        "| # | Error Class | Description | Detection Strategy | Example |\n"
        "|---|---|---|---|---|\n"
        "| 1 | Foo | First description | Detect A | Example A |\n",
        encoding="utf-8",
    )
    (errors_dir / "traceability.md").write_text(
        "| Error Class | Dimensional Analysis |\n"
        "|---|---|\n"
        "| 1. Foo | direct |\n"
        "| 1. Foo | mixed |\n",
        encoding="utf-8",
    )

    with patch("gpd.mcp.servers.errors_mcp.ERROR_CATALOG_FILES", ["verification/errors/catalog.md"]), patch(
        "gpd.mcp.servers.errors_mcp.TRACEABILITY_FILE",
        "verification/errors/traceability.md",
    ):
        with pytest.raises(ValueError, match="Duplicate traceability row for error class 1"):
            ErrorStore(tmp_path)


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

    planning = tmp_path / "GPD"
    planning.mkdir()
    (planning / "state.json").write_text("{}", encoding="utf-8")

    with patch(
        "gpd.mcp.servers.conventions_server._update_lock_in_project",
        side_effect=TimeoutError("lock acquisition timed out"),
    ):
        result = convention_set(str(tmp_path), "metric_signature", "(+,-,-,-)")

    assert "error" in result
    assert "timed out" in result["error"]


@pytest.mark.parametrize(
    ("tool_fn", "kwargs"),
    [
        ("convention_lock_status", {"project_dir": "relative/project"}),
        ("convention_set", {"project_dir": "relative/project", "key": "metric_signature", "value": "(+,-,-,-)"}),
    ],
)
def test_conventions_server_rejects_relative_project_dirs(tool_fn: str, kwargs: dict[str, object]) -> None:
    from gpd.mcp.servers import conventions_server

    result = getattr(conventions_server, tool_fn)(**kwargs)

    assert result == {"error": "project_dir must be an absolute path", "schema_version": 1}


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


def _call_mcp_tool(mcp_server: object, tool_name: str, arguments: dict[str, object]) -> dict[str, object]:
    async def _call() -> dict[str, object]:
        result = await mcp_server.call_tool(tool_name, arguments)
        if isinstance(result, dict):
            return result
        if (
            isinstance(result, tuple)
            and len(result) == 2
            and isinstance(result[1], dict)
        ):
            return result[1]
        if (
            isinstance(result, list)
            and len(result) == 1
            and hasattr(result[0], "text")
            and isinstance(result[0].text, str)
        ):
            return json.loads(result[0].text)
        raise AssertionError(f"Unexpected MCP call result: {result!r}")

    return anyio.run(_call)


@pytest.mark.parametrize(
    ("module_name", "tool_name", "arguments"),
    [
        ("gpd.mcp.servers.conventions_server", "convention_check", {"lock": {}, "unexpected": True}),
        ("gpd.mcp.servers.errors_mcp", "list_error_classes", {"unexpected": True}),
        ("gpd.mcp.servers.patterns_server", "seed_patterns", {"unexpected": True}),
        ("gpd.mcp.servers.protocols_server", "list_protocols", {"unexpected": True}),
        ("gpd.mcp.servers.skills_server", "get_skill_index", {"unexpected": True}),
    ],
)
def test_non_verification_mcp_tools_reject_unknown_arguments(module_name: str, tool_name: str, arguments: dict[str, object]) -> None:
    module = __import__(module_name, fromlist=["mcp"])

    result = _call_mcp_tool(module.mcp, tool_name, arguments)

    assert result == {"error": "Unsupported arguments: unexpected", "schema_version": 1}


@pytest.mark.parametrize(
    "module_name",
    [
        "gpd.mcp.servers.conventions_server",
        "gpd.mcp.servers.errors_mcp",
        "gpd.mcp.servers.patterns_server",
        "gpd.mcp.servers.protocols_server",
        "gpd.mcp.servers.skills_server",
        "gpd.mcp.servers.state_server",
        "gpd.mcp.servers.verification_server",
    ],
)
def test_built_in_mcp_servers_honor_log_level_environment(module_name: str, monkeypatch: pytest.MonkeyPatch) -> None:
    module = importlib.import_module(module_name)
    original_level = module.logger.level
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")

    try:
        reloaded = importlib.reload(module)
        assert reloaded.logger.level == logging.DEBUG
    finally:
        module.logger.setLevel(original_level)


def test_configure_mcp_logging_forces_stderr_and_disables_root_propagation() -> None:
    from gpd.mcp.servers import configure_mcp_logging

    logger = logging.getLogger("gpd-test-configure-mcp-logging")
    configured = logger
    original_handlers = list(logger.handlers)
    original_level = logger.level
    original_propagate = logger.propagate
    root_logger = logging.getLogger()
    root_handler = logging.StreamHandler(sys.stdout)
    root_logger.addHandler(root_handler)

    try:
        configured = configure_mcp_logging("gpd-test-configure-mcp-logging")
        assert configured.propagate is False
        assert configured.handlers
        assert all(
            isinstance(handler, logging.StreamHandler) and handler.stream is sys.stderr
            for handler in configured.handlers
        )
    finally:
        configured.handlers.clear()
        logger.handlers[:] = original_handlers
        logger.setLevel(original_level)
        logger.propagate = original_propagate
        root_logger.removeHandler(root_handler)


def test_state_mcp_tools_reject_unknown_arguments_and_preserve_absolute_path_enforcement(tmp_path: Path) -> None:
    from gpd.core.state import default_state_dict
    from gpd.mcp.servers.state_server import mcp

    planning = tmp_path / "GPD"
    planning.mkdir()
    (planning / "state.json").write_text(json.dumps(default_state_dict(), indent=2), encoding="utf-8")

    result = _call_mcp_tool(mcp, "get_state", {"project_dir": str(tmp_path), "unexpected": True})

    assert result == {"error": "Unsupported arguments: unexpected", "schema_version": 1}


@pytest.mark.parametrize(
    ("tool_name", "arguments"),
    [
        ("get_checklist", {"domain": "qft", "unexpected": True}),
        ("dimensional_check", {"expressions": ["[M] = [M]"], "unexpected": True}),
        ("run_contract_check", {"request": {"check_key": "contract.limit_recovery"}, "unexpected": True}),
        (
            "suggest_contract_checks",
            {
                "contract": {
                    "scope": {"question": "Q?"},
                    "context_intake": {"crucial_inputs": ["Use prior derivation"]},
                    "uncertainty_markers": {
                        "weakest_anchors": ["Missing benchmark"],
                        "disconfirming_observations": ["Fails sanity check"],
                    },
                },
                "unexpected": True,
            },
        ),
        ("get_verification_coverage", {"error_class_ids": [1], "active_checks": ["5.1"], "unexpected": True}),
    ],
)
def test_verification_mcp_tools_reject_unknown_arguments(tool_name: str, arguments: dict[str, object]) -> None:
    from gpd.mcp.servers.verification_server import mcp

    result = _call_mcp_tool(mcp, tool_name, arguments)

    assert result == {"error": "Unsupported arguments: unexpected", "schema_version": 1}


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


def test_limiting_case_check_rejects_duplicate_whitespace_normalized_limit_keys() -> None:
    from gpd.mcp.servers.verification_server import limiting_case_check

    result = limiting_case_check("E = mc^2", {" x ": "classical", "x": "quantum"})

    assert result == {
        "error": "limits must not contain duplicate keys after trimming whitespace",
        "schema_version": 1,
    }


def test_run_contract_check_canonicalizes_returned_binding_payload() -> None:
    from gpd.mcp.servers.verification_server import run_contract_check
    from tests.mcp.test_servers import _load_project_contract_fixture

    result = run_contract_check(
        {
            "check_key": "contract.benchmark_reproduction",
            "contract": _load_project_contract_fixture(),
            "binding": {"claim_ids": [" claim-benchmark "]},
            "observed": {"metric_value": 0.01, "threshold_value": 0.02},
        }
    )

    assert result["status"] == "pass"
    assert result["binding"] == {"claim_ids": ["claim-benchmark"]}


def test_verification_suggest_contract_checks_returns_error_envelope_on_backend_failure() -> None:
    from gpd.mcp.servers.verification_server import suggest_contract_checks

    contract = {
        "schema_version": 1,
        "scope": {"question": "Q?", "in_scope": ["benchmark recovery"]},
        "context_intake": {"crucial_inputs": ["Use the benchmark anchor defined in the contract."]},
        "deliverables": [
            {
                "id": "deliverable-main",
                "description": "Benchmark recovery note",
                "kind": "report",
                "must_contain": ["claim-main", "ref-benchmark"],
            }
        ],
        "acceptance_tests": [
            {
                "id": "test-benchmark",
                "subject": "claim-main",
                "kind": "benchmark",
                "procedure": "Compare against a benchmark",
                "pass_condition": "Agreement",
            }
        ],
        "claims": [
            {
                "id": "claim-main",
                "statement": "Recover the benchmark",
                "deliverables": ["deliverable-main"],
                "acceptance_tests": ["test-benchmark"],
                "references": ["ref-benchmark"],
            }
        ],
        "references": [
            {
                "id": "ref-benchmark",
                "kind": "paper",
                "locator": "doi:10.1234/benchmark-main",
                "role": "benchmark",
                "why_it_matters": "Primary benchmark anchor",
                "applies_to": ["claim-main"],
                "must_surface": True,
                "required_actions": ["compare"],
            }
        ],
        "forbidden_proxies": [
            {
                "id": "fp-main",
                "subject": "claim-main",
                "proxy": "qualitative agreement only",
                "reason": "Need explicit benchmark reproduction.",
            }
        ],
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


def test_verification_get_bundle_checklist_rejects_blank_bundle_ids() -> None:
    from gpd.mcp.servers.verification_server import get_bundle_checklist

    result = get_bundle_checklist(["stat-mech-simulation", "   "])

    assert result == {"error": "bundle_ids[1] must be a non-empty string", "schema_version": 1}


def test_verification_get_bundle_checklist_dedupes_bundle_ids() -> None:
    from gpd.mcp.servers.verification_server import get_bundle_checklist

    result = get_bundle_checklist(["stat-mech-simulation", "stat-mech-simulation"])

    assert result["bundle_count"] == 1
    assert [bundle["bundle_id"] for bundle in result["bundles"]] == ["stat-mech-simulation"]


def test_pattern_lookup_tolerates_missing_default_library(tmp_path: Path) -> None:
    import gpd.mcp.servers.patterns_server as patterns_server

    original_root = patterns_server._DEFAULT_PATTERNS_ROOT
    patterns_server._DEFAULT_PATTERNS_ROOT = tmp_path / "missing"
    try:
        result = patterns_server.lookup_pattern(domain="qft")
    finally:
        patterns_server._DEFAULT_PATTERNS_ROOT = original_root

    assert isinstance(result, dict)


def test_absolute_project_dir_schema_matches_current_host_path_semantics() -> None:
    from gpd.mcp.servers import ABSOLUTE_PROJECT_DIR_SCHEMA, resolve_absolute_project_dir

    if os.name == "nt":
        assert ABSOLUTE_PROJECT_DIR_SCHEMA["pattern"] == r"^(?:[A-Za-z]:[\\/](?:.*)?|\\\\[^\\/]+[\\/][^\\/]+(?:[\\/].*)?)"
    else:
        assert ABSOLUTE_PROJECT_DIR_SCHEMA["pattern"] == r"^/"
        assert resolve_absolute_project_dir(r"C:\repo") is None


def test_protocol_store_rejects_invalid_tier_frontmatter(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from gpd.mcp.servers.protocols_server import ProtocolStore, _load_protocol_domain_manifest

    protocols_dir = tmp_path / "protocols"
    protocols_dir.mkdir()
    domain_manifest = protocols_dir / "protocol-domains.json"
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
    domain_manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "protocol_domains": {
                    "bad-tier": "general",
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("gpd.mcp.servers.protocols_server.PROTOCOL_DOMAINS_MANIFEST", domain_manifest)
    _load_protocol_domain_manifest.cache_clear()
    try:
        with pytest.raises(ValueError, match="bad-tier.*tier must be an integer"):
            ProtocolStore(protocols_dir)
    finally:
        _load_protocol_domain_manifest.cache_clear()

def test_protocol_store_rejects_invalid_load_when_frontmatter(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from gpd.mcp.servers.protocols_server import ProtocolStore, _load_protocol_domain_manifest

    protocols_dir = tmp_path / "protocols"
    protocols_dir.mkdir()
    (protocols_dir / "bad-load-when.md").write_text(
        "---\n"
        "tier: 2\n"
        "load_when:\n"
        "  - asymptotic\n"
        "  - 5\n"
        "---\n"
        "# Bad Load When\n"
        "- First step\n",
        encoding="utf-8",
    )
    domain_manifest = protocols_dir / "protocol-domains.json"
    domain_manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "protocol_domains": {
                    "bad-load-when": "general",
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("gpd.mcp.servers.protocols_server.PROTOCOL_DOMAINS_MANIFEST", domain_manifest)
    _load_protocol_domain_manifest.cache_clear()
    try:
        with pytest.raises(ValueError, match="bad-load-when.*load_when contains non-string entry"):
            ProtocolStore(protocols_dir)
    finally:
        _load_protocol_domain_manifest.cache_clear()


def test_protocol_store_rejects_invalid_context_cost_frontmatter(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from gpd.mcp.servers.protocols_server import ProtocolStore, _load_protocol_domain_manifest

    protocols_dir = tmp_path / "protocols"
    protocols_dir.mkdir()
    (protocols_dir / "bad-context-cost.md").write_text(
        "---\n"
        "tier: 2\n"
        "load_when:\n"
        "  - asymptotic\n"
        "context_cost:\n"
        "  family: expensive\n"
        "---\n"
        "# Bad Context Cost\n"
        "- First step\n",
        encoding="utf-8",
    )
    domain_manifest = protocols_dir / "protocol-domains.json"
    domain_manifest.write_text(
        json.dumps({"schema_version": 1, "protocol_domains": {"bad-context-cost": "general"}}),
        encoding="utf-8",
    )

    monkeypatch.setattr("gpd.mcp.servers.protocols_server.PROTOCOL_DOMAINS_MANIFEST", domain_manifest)
    _load_protocol_domain_manifest.cache_clear()
    try:
        with pytest.raises(ValueError, match="bad-context-cost.*context_cost must be a non-empty string"):
            ProtocolStore(protocols_dir)
    finally:
        _load_protocol_domain_manifest.cache_clear()


def test_protocol_store_rejects_unknown_domain_filters(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from gpd.mcp.servers.protocols_server import ProtocolStore, _load_protocol_domain_manifest

    protocols_dir = tmp_path / "protocols"
    protocols_dir.mkdir()
    (protocols_dir / "good.md").write_text(
        "---\n"
        "tier: 1\n"
        "load_when:\n"
        "  - asymptotic\n"
        "---\n"
        "# Good\n"
        "- First step\n",
        encoding="utf-8",
    )
    domain_manifest = protocols_dir / "protocol-domains.json"
    domain_manifest.write_text(
        json.dumps({"schema_version": 1, "protocol_domains": {"good": "general"}}),
        encoding="utf-8",
    )

    monkeypatch.setattr("gpd.mcp.servers.protocols_server.PROTOCOL_DOMAINS_MANIFEST", domain_manifest)
    _load_protocol_domain_manifest.cache_clear()
    try:
        store = ProtocolStore(protocols_dir)
        with pytest.raises(ValueError, match="Unknown protocol domain: typo-domain"):
            store.list_all("typo-domain")
    finally:
        _load_protocol_domain_manifest.cache_clear()


def test_protocol_store_rejects_boolean_manifest_schema_version(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from gpd.mcp.servers.protocols_server import _load_protocol_domain_manifest

    protocols_dir = tmp_path / "protocols"
    protocols_dir.mkdir()
    domain_manifest = protocols_dir / "protocol-domains.json"
    domain_manifest.write_text(
        json.dumps({"schema_version": True, "protocol_domains": {"demo": "general"}}),
        encoding="utf-8",
    )

    monkeypatch.setattr("gpd.mcp.servers.protocols_server.PROTOCOL_DOMAINS_MANIFEST", domain_manifest)
    _load_protocol_domain_manifest.cache_clear()
    try:
        with pytest.raises(ValueError, match="Unsupported protocol domain manifest schema_version: True"):
            _load_protocol_domain_manifest()
    finally:
        _load_protocol_domain_manifest.cache_clear()


def test_protocol_store_rejects_missing_protocol_directory(tmp_path: Path) -> None:
    from gpd.mcp.servers.protocols_server import ProtocolStore

    with pytest.raises(OSError, match="Protocols directory not found"):
        ProtocolStore(tmp_path / "missing")


def test_protocol_store_rejects_malformed_frontmatter(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from gpd.mcp.servers.protocols_server import ProtocolStore, _load_protocol_domain_manifest

    protocols_dir = tmp_path / "protocols"
    protocols_dir.mkdir()
    (protocols_dir / "good.md").write_text("---\n---\n# Good\n## Procedure\n- Step one\n", encoding="utf-8")
    (protocols_dir / "bad.md").write_text("---\ntier: [broken\n---\n# Bad\n", encoding="utf-8")
    domain_manifest = protocols_dir / "protocol-domains.json"
    domain_manifest.write_text(
        json.dumps({"schema_version": 1, "protocol_domains": {"good": "general", "bad": "general"}}),
        encoding="utf-8",
    )

    monkeypatch.setattr("gpd.mcp.servers.protocols_server.PROTOCOL_DOMAINS_MANIFEST", domain_manifest)
    _load_protocol_domain_manifest.cache_clear()
    try:
        with pytest.raises(ValueError, match="Malformed frontmatter"):
            ProtocolStore(protocols_dir)
    finally:
        _load_protocol_domain_manifest.cache_clear()
