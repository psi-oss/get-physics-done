from __future__ import annotations

import copy
import json
from pathlib import Path

import anyio
import pytest

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "stage0"


def _load_project_contract_fixture() -> dict[str, object]:
    return json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))


def _call_verification_tool(tool_name: str, arguments: dict[str, object]) -> dict[str, object]:
    from gpd.mcp.servers.verification_server import mcp

    async def _call() -> dict[str, object]:
        result = await mcp.call_tool(tool_name, arguments)
        if isinstance(result, dict):
            return result
        if (
            isinstance(result, list)
            and len(result) == 1
            and hasattr(result[0], "text")
            and isinstance(result[0].text, str)
        ):
            return json.loads(result[0].text)
        raise AssertionError(f"Unexpected MCP call result: {result!r}")

    return anyio.run(_call)


def _derived_template_contract() -> dict[str, object]:
    contract = copy.deepcopy(_load_project_contract_fixture())
    contract["observables"][0]["regime"] = "large-k"
    contract["approach_policy"] = {
        "allowed_fit_families": ["power_law"],
        "forbidden_fit_families": ["polynomial"],
        "allowed_estimator_families": ["bootstrap"],
        "forbidden_estimator_families": ["jackknife"],
    }
    contract["acceptance_tests"].extend(
        [
            {
                "id": "test-limit",
                "subject": "claim-benchmark",
                "kind": "limiting_case",
                "procedure": "Evaluate the large-k limit against the asymptotic target.",
                "pass_condition": "Recovers the contracted large-k scaling",
                "evidence_required": ["deliv-figure"],
                "automation": "automated",
            },
            {
                "id": "test-fit",
                "subject": "claim-benchmark",
                "kind": "other",
                "procedure": "Compare fit residuals across the approved ansatz families.",
                "pass_condition": "Selected fit stays inside the allowed family",
                "evidence_required": ["deliv-figure"],
                "automation": "hybrid",
            },
            {
                "id": "test-estimator",
                "subject": "claim-benchmark",
                "kind": "other",
                "procedure": "Bootstrap estimator diagnostics must resolve bias and variance.",
                "pass_condition": "Bootstrap estimator remains calibrated",
                "evidence_required": ["deliv-figure"],
                "automation": "hybrid",
            },
        ]
    )
    return contract


def _multi_limit_contract() -> dict[str, object]:
    contract = copy.deepcopy(_load_project_contract_fixture())
    contract["observables"][0]["regime"] = "large-k"
    contract["claims"][0]["acceptance_tests"].append("test-limit-large-k")
    contract["acceptance_tests"].append(
        {
            "id": "test-limit-large-k",
            "subject": "claim-benchmark",
            "kind": "limiting_case",
            "procedure": "Evaluate the large-k limit against the asymptotic target.",
            "pass_condition": "Recovers the contracted large-k scaling",
            "evidence_required": ["deliv-figure"],
            "automation": "automated",
        }
    )
    contract["observables"].append(
        {
            "id": "obs-small-k",
            "name": "small-k observable",
            "kind": "scalar",
            "definition": "Secondary observable tracked in the small-k regime",
            "regime": "small-k",
        }
    )
    contract["deliverables"].append(
        {
            "id": "deliv-small-k",
            "kind": "figure",
            "path": "figures/small-k.png",
            "description": "Small-k comparison figure",
            "must_contain": ["small-k branch"],
        }
    )
    contract["claims"].append(
        {
            "id": "claim-small-k",
            "statement": "Recover the small-k limiting behavior",
            "observables": ["obs-small-k"],
            "deliverables": ["deliv-small-k"],
            "acceptance_tests": ["test-limit-small-k"],
            "references": [],
        }
    )
    contract["acceptance_tests"].append(
        {
            "id": "test-limit-small-k",
            "subject": "claim-small-k",
            "kind": "limiting_case",
            "procedure": "Evaluate the small-k limit against the asymptotic target.",
            "pass_condition": "Recovers the contracted small-k scaling",
            "evidence_required": ["deliv-small-k"],
            "automation": "automated",
        }
    )
    return contract


def _ambiguous_request_template_contract() -> dict[str, object]:
    contract = _multi_limit_contract()
    contract["references"].append(
        {
            "id": "ref-benchmark-2",
            "locator": "doi:10.1000/second-benchmark",
            "role": "benchmark",
            "why_it_matters": "Second benchmark anchor for ambiguity coverage",
            "required_actions": ["compare"],
            "applies_to": ["claim-benchmark"],
            "must_surface": True,
        }
    )
    contract["acceptance_tests"].append(
        {
            "id": "test-benchmark-2",
            "subject": "claim-benchmark",
            "kind": "benchmark",
            "procedure": "Compare against the second benchmark reference.",
            "pass_condition": "Matches the second benchmark within tolerance",
            "evidence_required": ["ref-benchmark-2"],
            "automation": "automated",
        }
    )
    contract["claims"][0]["acceptance_tests"].append("test-benchmark-2")
    contract["approach_policy"] = {
        "allowed_fit_families": ["power_law", "spline"],
        "forbidden_fit_families": ["polynomial"],
        "allowed_estimator_families": ["bootstrap", "jackknife"],
        "forbidden_estimator_families": [],
    }
    return contract


def _ambiguous_benchmark_binding_contract() -> dict[str, object]:
    contract = _derived_template_contract()
    contract["references"].append(
        {
            "id": "ref-benchmark-2",
            "locator": "doi:10.1000/second-benchmark",
            "role": "benchmark",
            "why_it_matters": "Second benchmark anchor without a second benchmark test",
            "required_actions": ["compare"],
            "applies_to": ["claim-benchmark"],
            "must_surface": True,
        }
    )
    return contract


def _ambiguous_limit_binding_contract() -> dict[str, object]:
    contract = _derived_template_contract()
    contract["observables"].append(
        {
            "id": "obs-small-k",
            "name": "small-k observable",
            "kind": "scalar",
            "definition": "Secondary observable tracked in the small-k regime",
            "regime": "small-k",
        }
    )
    return contract


def _binding_inconsistency_contract() -> dict[str, object]:
    contract = _ambiguous_request_template_contract()
    contract["forbidden_proxies"].append(
        {
            "id": "fp-benchmark",
            "subject": "claim-benchmark",
            "proxy": "proxy-benchmark",
            "reason": "Benchmark proxy must not stand in for direct evidence",
        }
    )
    return contract


def _assert_contract_tools_reject(contract: dict[str, object], expected_error: str) -> None:
    from gpd.mcp.servers.verification_server import run_contract_check, suggest_contract_checks

    run_result = run_contract_check(
        {
            "check_key": "contract.benchmark_reproduction",
            "contract": contract,
            "binding": {"claim_ids": ["claim-benchmark"]},
            "metadata": {"source_reference_id": "ref-benchmark"},
            "observed": {"metric_value": 0.01, "threshold_value": 0.02},
        }
    )
    suggest_result = suggest_contract_checks(contract)

    expected = {"error": f"Invalid contract payload: {expected_error}", "schema_version": 1}
    assert run_result == expected
    assert suggest_result == expected


@pytest.mark.parametrize(
    ("check_key", "request_payload"),
    [
        (
            "contract.benchmark_reproduction",
            {
                "binding": {
                    "claim_ids": ["claim-benchmark"],
                    "deliverable_ids": ["deliv-small-k"],
                    "acceptance_test_ids": ["test-limit-small-k"],
                    "reference_ids": ["ref-benchmark"],
                },
                "metadata": {"source_reference_id": "ref-benchmark"},
                "observed": {"metric_value": 0.01, "threshold_value": 0.02},
            },
        ),
        (
            "contract.direct_proxy_consistency",
            {
                "binding": {
                    "claim_ids": ["claim-benchmark"],
                    "deliverable_ids": ["deliv-small-k"],
                    "acceptance_test_ids": ["test-limit-small-k"],
                    "forbidden_proxy_ids": ["fp-benchmark"],
                },
                "observed": {"direct_available": True, "proxy_available": False},
            },
        ),
        (
            "contract.fit_family_mismatch",
            {
                "binding": {
                    "claim_ids": ["claim-benchmark"],
                    "deliverable_ids": ["deliv-small-k"],
                    "acceptance_test_ids": ["test-limit-small-k"],
                },
                "metadata": {
                    "declared_family": "power_law",
                    "allowed_families": ["power_law", "spline"],
                    "forbidden_families": ["polynomial"],
                },
                "observed": {"selected_family": "power_law", "competing_family_checked": True},
            },
        ),
        (
            "contract.estimator_family_mismatch",
            {
                "binding": {
                    "claim_ids": ["claim-benchmark"],
                    "deliverable_ids": ["deliv-small-k"],
                    "acceptance_test_ids": ["test-limit-small-k"],
                },
                "metadata": {
                    "declared_family": "bootstrap",
                    "allowed_families": ["bootstrap", "jackknife"],
                    "forbidden_families": [],
                },
                "observed": {"selected_family": "bootstrap", "bias_checked": True, "calibration_checked": True},
            },
        ),
    ],
)
def test_run_contract_check_blocks_decisive_pass_for_inconsistent_binding_contexts(
    check_key: str,
    request_payload: dict[str, object],
) -> None:
    from gpd.mcp.servers.verification_server import run_contract_check

    result = run_contract_check(
        {
            "check_key": check_key,
            "contract": _binding_inconsistency_contract(),
            **request_payload,
        }
    )

    assert result["status"] == "insufficient_evidence"
    assert any("binding contexts disagree on claim targets" in issue for issue in result["automated_issues"])


@pytest.mark.parametrize(
    ("schema_version", "expected_error"),
    [
        (2, "Invalid contract payload: schema_version must be 1"),
        ("1", "Invalid contract payload: schema_version must be the integer 1"),
        (True, "Invalid contract payload: schema_version must be the integer 1"),
    ],
)
def test_contract_tools_reject_invalid_schema_versions(schema_version: object, expected_error: str) -> None:
    from gpd.mcp.servers.verification_server import run_contract_check, suggest_contract_checks

    contract = _load_project_contract_fixture()
    contract["schema_version"] = schema_version
    contract["context_intake"] = "not-a-dict"

    run_result = run_contract_check(
        {
            "check_key": "contract.benchmark_reproduction",
            "contract": contract,
            "binding": {"claim_ids": ["claim-benchmark"]},
            "metadata": {"source_reference_id": "ref-benchmark"},
            "observed": {"metric_value": 0.01, "threshold_value": 0.02},
        }
    )

    suggest_result = suggest_contract_checks(contract)

    assert run_result == {"error": expected_error, "schema_version": 1}
    assert suggest_result == {"error": expected_error, "schema_version": 1}


def test_contract_tools_reject_coercive_contract_scalars() -> None:
    from gpd.mcp.servers.verification_server import run_contract_check, suggest_contract_checks

    contract = _load_project_contract_fixture()
    contract["references"][0]["must_surface"] = "yes"

    run_result = run_contract_check(
        {
            "check_key": "contract.benchmark_reproduction",
            "contract": contract,
            "binding": {"claim_ids": ["claim-benchmark"]},
            "metadata": {"source_reference_id": "ref-benchmark"},
            "observed": {"metric_value": 0.01, "threshold_value": 0.02},
        }
    )

    suggest_result = suggest_contract_checks(contract)

    expected = {
        "error": "Invalid contract payload: references.0.must_surface must be a boolean",
        "schema_version": 1,
    }
    assert run_result == expected
    assert suggest_result == expected


@pytest.mark.parametrize(
    ("path", "value"),
    [
        ("claims.0.references", "ref-benchmark"),
        ("references.0.aliases", "benchmark-paper"),
        ("references.0.required_actions", "read"),
    ],
)
def test_contract_tools_accept_recoverable_scalar_to_list_contract_drift(
    path: str,
    value: object,
) -> None:
    contract = _load_project_contract_fixture()

    if path == "claims.0.references":
        contract["claims"][0]["references"] = value
    elif path == "references.0.aliases":
        contract["references"][0]["aliases"] = value
    elif path == "references.0.required_actions":
        contract["references"][0]["required_actions"] = value
    else:  # pragma: no cover - defensive guard for future test edits
        raise AssertionError(f"Unhandled path: {path}")

    from gpd.mcp.servers.verification_server import run_contract_check, suggest_contract_checks

    request = {
        "check_key": "contract.benchmark_reproduction",
        "contract": contract,
        "binding": {"claim_ids": ["claim-benchmark"]},
        "metadata": {"source_reference_id": "ref-benchmark"},
        "observed": {"metric_value": 0.01, "threshold_value": 0.02},
    }

    run_result = run_contract_check(request)
    suggest_result = suggest_contract_checks(contract)

    assert run_result["status"] == "pass"
    assert suggest_result["suggested_count"] > 0
    assert "error" not in run_result
    assert "error" not in suggest_result


def test_suggest_contract_checks_derives_request_templates_from_contract() -> None:
    from gpd.mcp.servers.verification_server import suggest_contract_checks

    result = suggest_contract_checks(_derived_template_contract())
    checks = {entry["check_key"]: entry for entry in result["suggested_checks"]}
    assert all(entry["request_template"]["check_key"] == entry["check_key"] for entry in result["suggested_checks"])

    benchmark = checks["contract.benchmark_reproduction"]["request_template"]
    assert benchmark["binding"]["claim_ids"] == ["claim-benchmark"]
    assert benchmark["binding"]["acceptance_test_ids"] == ["test-benchmark"]
    assert benchmark["binding"]["reference_ids"] == ["ref-benchmark"]
    assert benchmark["metadata"]["source_reference_id"] == "ref-benchmark"
    assert benchmark["observed"]["metric_value"] is None
    assert benchmark["observed"]["threshold_value"] is None
    assert benchmark["artifact_content"] is None

    limit = checks["contract.limit_recovery"]["request_template"]
    assert limit["binding"]["claim_ids"] == ["claim-benchmark"]
    assert limit["binding"]["acceptance_test_ids"] == ["test-limit"]
    assert limit["binding"]["observable_ids"] == ["obs-benchmark"]
    assert limit["metadata"]["regime_label"] == "large-k"
    assert limit["metadata"]["expected_behavior"] == "Recovers the contracted large-k scaling"
    assert limit["observed"]["limit_passed"] is None
    assert limit["observed"]["observed_limit"] is None
    assert limit["artifact_content"] is None

    direct_proxy = checks["contract.direct_proxy_consistency"]["request_template"]
    assert direct_proxy["binding"]["claim_ids"] == ["claim-benchmark"]
    assert direct_proxy["binding"]["forbidden_proxy_ids"] == ["fp-01"]
    assert direct_proxy["observed"]["proxy_only"] is None
    assert direct_proxy["observed"]["direct_available"] is None
    assert direct_proxy["observed"]["proxy_available"] is None
    assert direct_proxy["observed"]["consistency_passed"] is None
    assert direct_proxy["artifact_content"] is None

    fit = checks["contract.fit_family_mismatch"]["request_template"]
    assert fit["binding"]["claim_ids"] == ["claim-benchmark"]
    assert fit["binding"]["acceptance_test_ids"] == ["test-fit"]
    assert fit["binding"]["observable_ids"] == ["obs-benchmark"]
    assert fit["metadata"]["declared_family"] == "power_law"
    assert fit["metadata"]["allowed_families"] == ["power_law"]
    assert fit["metadata"]["forbidden_families"] == ["polynomial"]
    assert fit["observed"]["selected_family"] is None
    assert fit["observed"]["competing_family_checked"] is None
    assert fit["artifact_content"] is None

    estimator = checks["contract.estimator_family_mismatch"]["request_template"]
    assert estimator["binding"]["claim_ids"] == ["claim-benchmark"]
    assert estimator["binding"]["acceptance_test_ids"] == ["test-estimator"]
    assert estimator["binding"]["observable_ids"] == ["obs-benchmark"]
    assert estimator["metadata"]["declared_family"] == "bootstrap"
    assert estimator["metadata"]["allowed_families"] == ["bootstrap"]
    assert estimator["metadata"]["forbidden_families"] == ["jackknife"]
    assert estimator["observed"]["selected_family"] is None
    assert estimator["observed"]["bias_checked"] is None
    assert estimator["observed"]["calibration_checked"] is None
    assert estimator["artifact_content"] is None
    assert checks["contract.benchmark_reproduction"]["supported_binding_fields"] == [
        "binding.claim_id",
        "binding.claim_ids",
        "binding.deliverable_id",
        "binding.deliverable_ids",
        "binding.acceptance_test_id",
        "binding.acceptance_test_ids",
        "binding.reference_id",
        "binding.reference_ids",
    ]


def test_suggest_contract_checks_templates_do_not_pass_when_reused_unchanged() -> None:
    from gpd.mcp.servers.verification_server import run_contract_check, suggest_contract_checks

    contract = _derived_template_contract()
    result = suggest_contract_checks(contract)

    for entry in result["suggested_checks"]:
        request = {
            "check_key": entry["check_key"],
            "contract": contract,
            **copy.deepcopy(entry["request_template"]),
        }
        run_result = run_contract_check(request)
        assert run_result["status"] == "insufficient_evidence", entry["check_key"]


def test_run_contract_check_reuses_contract_derived_limit_and_family_defaults() -> None:
    from gpd.mcp.servers.verification_server import run_contract_check

    contract = _derived_template_contract()

    limit = run_contract_check(
        {
            "check_key": "contract.limit_recovery",
            "contract": contract,
            "observed": {"limit_passed": True, "observed_limit": "large-k"},
        }
    )
    fit = run_contract_check(
        {
            "check_key": "contract.fit_family_mismatch",
            "contract": contract,
            "observed": {"selected_family": "power_law", "competing_family_checked": True},
        }
    )
    estimator = run_contract_check(
        {
            "check_key": "contract.estimator_family_mismatch",
            "contract": contract,
            "observed": {
                "selected_family": "bootstrap",
                "bias_checked": True,
                "calibration_checked": True,
            },
        }
    )

    assert limit["status"] == "pass"
    assert fit["status"] == "pass"
    assert estimator["status"] == "pass"


def test_run_contract_check_limit_recovery_uses_bound_acceptance_test_pass_condition() -> None:
    from gpd.mcp.servers.verification_server import run_contract_check

    result = run_contract_check(
        {
            "check_key": "contract.limit_recovery",
            "contract": _multi_limit_contract(),
            "binding": {"acceptance_test_ids": ["test-limit-small-k"]},
            "observed": {"limit_passed": True, "observed_limit": "small-k"},
        }
    )

    assert result["status"] == "pass"
    assert result["missing_inputs"] == []
    assert result["metrics"]["regime_label"] == "small-k"


def test_run_contract_check_direct_proxy_consistency_marks_missing_direct_anchor_as_missing_evidence() -> None:
    from gpd.mcp.servers.verification_server import run_contract_check

    result = run_contract_check(
        {
            "check_key": "contract.direct_proxy_consistency",
            "observed": {"proxy_available": True},
        }
    )

    assert result["status"] == "insufficient_evidence"
    assert result["missing_inputs"] == ["observed.direct_available"]
    assert result["automated_issues"] == []


def test_run_contract_check_direct_proxy_consistency_passes_on_direct_evidence_alone() -> None:
    from gpd.mcp.servers.verification_server import run_contract_check

    result = run_contract_check(
        {
            "check_key": "contract.direct_proxy_consistency",
            "observed": {"direct_available": True},
        }
    )

    assert result["status"] == "pass"
    assert result["evidence_directness"] == "direct"
    assert result["missing_inputs"] == []
    assert result["automated_issues"] == []


def test_run_contract_check_direct_proxy_consistency_requires_consistency_comparison_when_both_sources_exist() -> None:
    from gpd.mcp.servers.verification_server import run_contract_check

    result = run_contract_check(
        {
            "check_key": "contract.direct_proxy_consistency",
            "observed": {"direct_available": True, "proxy_available": True},
        }
    )

    assert result["status"] == "insufficient_evidence"
    assert result["missing_inputs"] == ["observed.consistency_passed"]


def test_run_contract_check_estimator_negative_diagnostics_are_not_treated_as_missing_inputs() -> None:
    from gpd.mcp.servers.verification_server import run_contract_check

    result = run_contract_check(
        {
            "check_key": "contract.estimator_family_mismatch",
            "contract": _derived_template_contract(),
            "observed": {
                "selected_family": "bootstrap",
                "bias_checked": False,
                "calibration_checked": False,
            },
        }
    )

    assert result["status"] == "warning"
    assert result["missing_inputs"] == []
    assert "Estimator family is missing bias or calibration diagnostics" in result["automated_issues"]


def test_suggest_contract_checks_leaves_ambiguous_metadata_placeholders_unresolved() -> None:
    from gpd.mcp.servers.verification_server import suggest_contract_checks

    result = suggest_contract_checks(_ambiguous_request_template_contract())
    checks = {entry["check_key"]: entry for entry in result["suggested_checks"]}

    benchmark = checks["contract.benchmark_reproduction"]["request_template"]
    limit = checks["contract.limit_recovery"]["request_template"]
    fit = checks["contract.fit_family_mismatch"]["request_template"]
    estimator = checks["contract.estimator_family_mismatch"]["request_template"]

    assert benchmark["metadata"]["source_reference_id"] is None
    assert limit["metadata"]["regime_label"] is None
    assert limit["metadata"]["expected_behavior"] is None
    assert fit["metadata"]["declared_family"] is None
    assert estimator["metadata"]["declared_family"] is None


def test_suggest_contract_checks_leaves_ambiguous_subject_bindings_unresolved() -> None:
    from gpd.mcp.servers.verification_server import suggest_contract_checks

    benchmark_result = suggest_contract_checks(_ambiguous_benchmark_binding_contract())
    benchmark_checks = {entry["check_key"]: entry for entry in benchmark_result["suggested_checks"]}
    benchmark = benchmark_checks["contract.benchmark_reproduction"]["request_template"]
    assert benchmark["binding"] == {}
    assert benchmark["metadata"]["source_reference_id"] is None

    limit_result = suggest_contract_checks(_ambiguous_limit_binding_contract())
    limit_checks = {entry["check_key"]: entry for entry in limit_result["suggested_checks"]}
    limit = limit_checks["contract.limit_recovery"]["request_template"]
    assert limit["binding"] == {}
    assert limit["metadata"]["regime_label"] is None
    assert limit["metadata"]["expected_behavior"] is None


def test_run_contract_check_ambiguous_context_requires_explicit_subject_selector() -> None:
    from gpd.mcp.servers.verification_server import run_contract_check

    benchmark = run_contract_check(
        {
            "check_key": "contract.benchmark_reproduction",
            "contract": _ambiguous_benchmark_binding_contract(),
            "observed": {"metric_value": 0.01, "threshold_value": 0.02},
        }
    )
    limit = run_contract_check(
        {
            "check_key": "contract.limit_recovery",
            "contract": _ambiguous_limit_binding_contract(),
            "observed": {"limit_passed": True, "observed_limit": "large-k"},
        }
    )

    assert benchmark["status"] == "insufficient_evidence"
    assert "metadata.source_reference_id" in benchmark["missing_inputs"]
    assert "Ambiguous benchmark context requires an explicit benchmark reference" in benchmark["automated_issues"]

    assert limit["status"] == "insufficient_evidence"
    assert "metadata.regime_label" in limit["missing_inputs"]
    assert "Ambiguous limit context requires an explicit regime selection" in limit["automated_issues"]


def test_run_contract_check_ambiguous_context_accepts_explicit_metadata_selector() -> None:
    from gpd.mcp.servers.verification_server import run_contract_check

    benchmark = run_contract_check(
        {
            "check_key": "contract.benchmark_reproduction",
            "contract": _ambiguous_benchmark_binding_contract(),
            "metadata": {"source_reference_id": "ref-benchmark"},
            "observed": {"metric_value": 0.01, "threshold_value": 0.02},
        }
    )
    limit = run_contract_check(
        {
            "check_key": "contract.limit_recovery",
            "contract": _ambiguous_limit_binding_contract(),
            "metadata": {
                "regime_label": "large-k",
                "expected_behavior": "Recovers the contracted large-k scaling",
            },
            "observed": {"limit_passed": True, "observed_limit": "large-k"},
        }
    )

    assert benchmark["status"] == "pass"
    assert benchmark["missing_inputs"] == []
    assert benchmark["automated_issues"] == []

    assert limit["status"] == "pass"
    assert limit["missing_inputs"] == []
    assert limit["automated_issues"] == []


def test_run_contract_check_keyword_fallback_reaches_warning_when_prose_evidence_is_present() -> None:
    from gpd.mcp.servers.verification_server import run_contract_check

    limit = run_contract_check(
        {
            "check_key": "contract.limit_recovery",
            "artifact_content": "Observed asymptotic limit and scaling discussion.",
        }
    )
    benchmark = run_contract_check(
        {
            "check_key": "contract.benchmark_reproduction",
            "artifact_content": "Published benchmark baseline comparison appears in prose.",
        }
    )

    assert limit["status"] == "insufficient_evidence"
    assert "metadata.regime_label" in limit["missing_inputs"]
    assert "metadata.expected_behavior" in limit["missing_inputs"]
    assert benchmark["status"] == "warning"
    assert benchmark["evidence_directness"] == "mixed"
    assert "metadata.source_reference_id" in benchmark["missing_inputs"]
    assert "observed.metric_value" in benchmark["missing_inputs"]


def test_suggest_contract_checks_surfaces_salvage_warnings() -> None:
    from gpd.mcp.servers.verification_server import suggest_contract_checks

    contract = _load_project_contract_fixture()
    contract["references"][0]["notes"] = "legacy extra field"

    result = suggest_contract_checks(contract)

    assert "error" not in result
    assert result["contract_salvaged"] is True
    assert result["contract_salvage_findings"] == ["references.0.notes: Extra inputs are not permitted"]
    assert any("salvaged before check suggestion" in warning for warning in result["contract_warnings"])
    assert any(entry["check_key"] == "contract.benchmark_reproduction" for entry in result["suggested_checks"])


def test_contract_tools_salvage_unknown_top_level_contract_fields() -> None:
    from gpd.mcp.servers.verification_server import run_contract_check, suggest_contract_checks

    contract = _load_project_contract_fixture()
    contract["legacy_notes"] = "forwarded from a prior schema revision"

    run_result = run_contract_check(
        {
            "check_key": "contract.benchmark_reproduction",
            "contract": contract,
            "binding": {"claim_ids": ["claim-benchmark"]},
            "metadata": {"source_reference_id": "ref-benchmark"},
            "observed": {"metric_value": 0.01, "threshold_value": 0.02},
        }
    )
    suggest_result = suggest_contract_checks(contract)

    assert run_result["contract_salvaged"] is True
    assert "legacy_notes: Extra inputs are not permitted" in run_result["contract_salvage_findings"]
    assert suggest_result["contract_salvaged"] is True
    assert "legacy_notes: Extra inputs are not permitted" in suggest_result["contract_salvage_findings"]


@pytest.mark.parametrize("payload", ["not-a-dict", ["claim-benchmark"], 3])
def test_suggest_contract_checks_rejects_non_mapping_payloads(payload: object) -> None:
    from gpd.mcp.servers.verification_server import suggest_contract_checks

    result = suggest_contract_checks(payload)  # type: ignore[arg-type]

    assert result == {"error": "contract must be an object", "schema_version": 1}


@pytest.mark.parametrize("active_checks", ["5.16", 5, {"5.16": True}])
def test_suggest_contract_checks_rejects_non_list_active_checks(active_checks: object) -> None:
    from gpd.mcp.servers.verification_server import suggest_contract_checks

    result = suggest_contract_checks(_derived_template_contract(), active_checks=active_checks)  # type: ignore[arg-type]

    assert result == {"error": "active_checks must be a list of strings", "schema_version": 1}


@pytest.mark.parametrize(
    ("tool_name", "arguments", "expected"),
    [
        (
            "run_contract_check",
            {"request": "not-a-dict"},
            {"error": "request must be an object", "schema_version": 1},
        ),
        (
            "run_contract_check",
            {
                "request": {
                    "check_key": "contract.benchmark_reproduction",
                    "binding": {"claim_ids": ["claim-benchmark", 9]},
                    "observed": {"metric_value": 0.01, "threshold_value": 0.02},
                }
            },
            {"error": "binding.claim_ids[1] must be a non-empty string", "schema_version": 1},
        ),
        (
            "suggest_contract_checks",
            {"contract": "not-a-dict"},
            {"error": "contract must be an object", "schema_version": 1},
        ),
        (
            "suggest_contract_checks",
            {"contract": _derived_template_contract(), "active_checks": 5},
            {"error": "active_checks must be a list of strings", "schema_version": 1},
        ),
    ],
)
def test_contract_tools_preserve_stable_error_envelopes_at_mcp_boundary(
    tool_name: str,
    arguments: dict[str, object],
    expected: dict[str, object],
) -> None:
    assert _call_verification_tool(tool_name, arguments) == expected


@pytest.mark.parametrize(
    ("mutator", "expected_error"),
    [
        (
            lambda contract: contract["claims"][0]["observables"].append(" "),
            "claims.0.observables[1] must be a non-empty string",
        ),
        (
            lambda contract: contract["references"][0]["required_actions"].append(17),
            "references.0.required_actions[3] must be a non-empty string",
        ),
    ],
)
def test_contract_tools_reject_blank_or_malformed_contract_list_members_at_mcp_boundary(
    mutator,
    expected_error: str,
) -> None:
    contract = _load_project_contract_fixture()
    mutator(contract)

    expected = {"error": f"Invalid contract payload: {expected_error}", "schema_version": 1}

    assert (
        _call_verification_tool(
            "run_contract_check",
            {
                "request": {
                    "check_key": "contract.benchmark_reproduction",
                    "contract": contract,
                    "binding": {"claim_ids": ["claim-benchmark"]},
                    "metadata": {"source_reference_id": "ref-benchmark"},
                    "observed": {"metric_value": 0.01, "threshold_value": 0.02},
                }
            },
        )
        == expected
    )
    assert _call_verification_tool("suggest_contract_checks", {"contract": contract}) == expected


@pytest.mark.parametrize(
    ("mutator", "expected_error"),
    [
        (
            lambda contract: contract["claims"][0].__setitem__("references", "   "),
            "claims.0.references must not be blank",
        ),
        (
            lambda contract: contract["scope"].__setitem__("in_scope", "   "),
            "scope.in_scope must not be blank",
        ),
    ],
)
def test_contract_tools_reject_blank_scalar_to_list_contract_drift(
    mutator,
    expected_error: str,
) -> None:
    from gpd.mcp.servers.verification_server import run_contract_check, suggest_contract_checks

    contract = _load_project_contract_fixture()
    mutator(contract)

    expected = {"error": f"Invalid contract payload: {expected_error}", "schema_version": 1}

    request = {
        "check_key": "contract.benchmark_reproduction",
        "contract": contract,
        "binding": {"claim_ids": ["claim-benchmark"]},
        "metadata": {"source_reference_id": "ref-benchmark"},
        "observed": {"metric_value": 0.01, "threshold_value": 0.02},
    }

    assert run_contract_check(request) == expected
    assert suggest_contract_checks(contract) == expected


@pytest.mark.parametrize("payload", ["not-a-dict", ["claim-benchmark"], 3])
def test_run_contract_check_rejects_non_mapping_payloads(payload: object) -> None:
    from gpd.mcp.servers.verification_server import run_contract_check

    result = run_contract_check(payload)  # type: ignore[arg-type]

    assert result == {"error": "request must be an object", "schema_version": 1}


@pytest.mark.parametrize(
    ("request_payload", "expected_error"),
    [
        (
            {
                "check_key": "contract.benchmark_reproduction",
                "binding": {"claim_ids": ["claim-benchmark", None]},
                "observed": {"metric_value": 0.01, "threshold_value": 0.02},
            },
            "binding.claim_ids[1] must be a non-empty string",
        ),
        (
            {
                "check_key": "contract.benchmark_reproduction",
                "binding": {"reference_ids": ["ref-benchmark", "   "]},
                "observed": {"metric_value": 0.01, "threshold_value": 0.02},
            },
            "binding.reference_ids[1] must be a non-empty string",
        ),
        (
            {
                "check_key": "contract.fit_family_mismatch",
                "metadata": {"allowed_families": ["power_law", 5]},
                "observed": {"selected_family": "power_law", "competing_family_checked": True},
            },
            "metadata.allowed_families[1] must be a non-empty string",
        ),
        (
            {
                "check_key": "contract.estimator_family_mismatch",
                "metadata": {"forbidden_families": ["", "jackknife"]},
                "observed": {
                    "selected_family": "bootstrap",
                    "bias_checked": True,
                    "calibration_checked": True,
                },
            },
            "metadata.forbidden_families[0] must be a non-empty string",
        ),
        (
            {
                "check_key": "contract.benchmark_reproduction",
                "binding": {"claim_ids": {"primary": "claim-benchmark"}},
                "observed": {"metric_value": 0.01, "threshold_value": 0.02},
            },
            "binding.claim_ids must be a string or list of strings",
        ),
        (
            {
                "check_key": "contract.fit_family_mismatch",
                "metadata": {"allowed_families": "power_law"},
                "observed": {"selected_family": "power_law", "competing_family_checked": True},
            },
            "metadata.allowed_families must be a list of strings",
        ),
    ],
)
def test_run_contract_check_rejects_malformed_binding_and_metadata_list_members(
    request_payload: dict[str, object], expected_error: str
) -> None:
    from gpd.mcp.servers.verification_server import run_contract_check

    result = run_contract_check(request_payload)

    assert result == {"error": expected_error, "schema_version": 1}


@pytest.mark.parametrize(
    ("request_payload", "expected_error"),
    [
        (
            {
                "check_key": "contract.benchmark_reproduction",
                "metadata": {"source_reference_id": "ref-benchmark"},
                "observed": {"metric_value": True, "threshold_value": 0.02},
            },
            "observed.metric_value must be a number",
        ),
        (
            {
                "check_key": "contract.benchmark_reproduction",
                "metadata": {"source_reference_id": "ref-benchmark"},
                "observed": {"metric_value": 0.01, "threshold_value": False},
            },
            "observed.threshold_value must be a number",
        ),
        (
            {
                "check_key": "contract.direct_proxy_consistency",
                "observed": {"proxy_only": "true"},
            },
            "observed.proxy_only must be a boolean",
        ),
        (
            {
                "check_key": "contract.fit_family_mismatch",
                "metadata": {"declared_family": "power_law"},
                "observed": {"selected_family": "power_law", "competing_family_checked": "false"},
            },
            "observed.competing_family_checked must be a boolean",
        ),
        (
            {
                "check_key": "contract.estimator_family_mismatch",
                "metadata": {"declared_family": "bootstrap"},
                "observed": {
                    "selected_family": "bootstrap",
                    "bias_checked": "true",
                    "calibration_checked": True,
                },
            },
            "observed.bias_checked must be a boolean",
        ),
    ],
)
def test_run_contract_check_rejects_coercive_numeric_and_boolean_fields(
    request_payload: dict[str, object],
    expected_error: str,
) -> None:
    from gpd.mcp.servers.verification_server import run_contract_check

    result = run_contract_check(request_payload)

    assert result == {"error": expected_error, "schema_version": 1}


@pytest.mark.parametrize(
    ("request_payload", "expected_error"),
    [
        (
            {
                "check_key": "contract.limit_recovery",
                "metadata": {"expected_behavior": 5},
                "observed": {"limit_passed": True, "observed_limit": "large-k"},
            },
            "metadata.expected_behavior must be a string",
        ),
        (
            {
                "check_key": "contract.benchmark_reproduction",
                "metadata": {"source_reference_id": 5},
                "observed": {"metric_value": 0.01, "threshold_value": 0.02},
            },
            "metadata.source_reference_id must be a string",
        ),
        (
            {
                "check_key": "contract.fit_family_mismatch",
                "metadata": {"declared_family": 5},
                "observed": {"selected_family": "power_law", "competing_family_checked": True},
            },
            "metadata.declared_family must be a string",
        ),
        (
            {
                "check_key": "contract.limit_recovery",
                "metadata": {"regime_label": "large-k", "expected_behavior": "matches"},
                "observed": {"limit_passed": True, "observed_limit": 9},
            },
            "observed.observed_limit must be a string",
        ),
        (
            {
                "check_key": "contract.fit_family_mismatch",
                "metadata": {"declared_family": "power_law"},
                "observed": {"selected_family": 9, "competing_family_checked": True},
            },
            "observed.selected_family must be a string",
        ),
        (
            {
                "check_key": "contract.benchmark_reproduction",
                "metadata": {"source_reference_id": "ref-benchmark"},
                "observed": {"metric_value": 0.01, "threshold_value": 0.02},
                "artifact_content": {"text": "benchmark"},
            },
            "artifact_content must be a string",
        ),
    ],
)
def test_run_contract_check_rejects_non_string_request_fields(
    request_payload: dict[str, object],
    expected_error: str,
) -> None:
    from gpd.mcp.servers.verification_server import run_contract_check

    result = run_contract_check(request_payload)

    assert result == {"error": expected_error, "schema_version": 1}


def test_contract_tools_reject_blocking_salvage_schema_drift() -> None:
    from gpd.mcp.servers.verification_server import run_contract_check, suggest_contract_checks

    contract = _load_project_contract_fixture()
    contract["acceptance_tests"] = "not-a-list"

    run_result = run_contract_check(
        {
            "check_key": "contract.benchmark_reproduction",
            "contract": contract,
            "binding": {"claim_ids": ["claim-benchmark"]},
            "metadata": {"source_reference_id": "ref-benchmark"},
            "observed": {"metric_value": 0.01, "threshold_value": 0.02},
        }
    )
    suggest_result = suggest_contract_checks(contract)

    expected = {
        "error": "Invalid contract payload: acceptance_tests must be a list, not str",
        "schema_version": 1,
    }
    assert run_result == expected
    assert suggest_result == expected


def test_contract_tool_responses_copy_binding_targets_lists() -> None:
    from gpd.mcp.servers.verification_server import run_contract_check, suggest_contract_checks

    request = {
        "check_key": "contract.benchmark_reproduction",
        "contract": _load_project_contract_fixture(),
        "binding": {"claim_ids": ["claim-benchmark"]},
        "metadata": {"source_reference_id": "ref-benchmark"},
        "observed": {"metric_value": 0.01, "threshold_value": 0.02},
    }

    first_run = run_contract_check(request)
    first_run["binding_targets"].append("poisoned")

    second_run = run_contract_check(request)
    assert second_run["binding_targets"] == ["claim", "deliverable", "acceptance_test", "reference"]

    first_suggest = suggest_contract_checks(_load_project_contract_fixture())
    benchmark = next(entry for entry in first_suggest["suggested_checks"] if entry["check_key"] == "contract.benchmark_reproduction")
    benchmark["binding_targets"].append("poisoned")

    second_suggest = suggest_contract_checks(_load_project_contract_fixture())
    fresh_benchmark = next(
        entry for entry in second_suggest["suggested_checks"] if entry["check_key"] == "contract.benchmark_reproduction"
    )
    assert fresh_benchmark["binding_targets"] == ["claim", "deliverable", "acceptance_test", "reference"]


@pytest.mark.parametrize(
    ("mutator", "expected_error"),
    [
        (
            lambda contract: contract["claims"].append(dict(contract["claims"][0])),
            "duplicate claim id claim-benchmark",
        ),
        (
            lambda contract: contract["deliverables"][0].__setitem__("id", "claim-benchmark"),
            "contract id claim-benchmark is reused across claim, deliverable; target resolution is ambiguous",
        ),
        (
            lambda contract: contract["references"][0].__setitem__("carry_forward_to", ["claim-benchmark"]),
            "reference ref-benchmark carry_forward_to must name workflow scope, not contract id claim-benchmark",
        ),
    ],
)
def test_contract_tools_reject_shared_contract_integrity_errors(
    mutator,
    expected_error: str,
) -> None:
    contract = _load_project_contract_fixture()

    mutator(contract)

    _assert_contract_tools_reject(contract, expected_error)


def test_contract_tools_reject_shared_integrity_errors_after_salvage() -> None:
    contract = _load_project_contract_fixture()
    contract["references"][0]["notes"] = "legacy extra field"
    contract["deliverables"][0]["id"] = "claim-benchmark"

    _assert_contract_tools_reject(
        contract,
        "contract id claim-benchmark is reused across claim, deliverable; target resolution is ambiguous",
    )


def test_verification_server_success_responses_keep_stable_envelope_equality() -> None:
    from gpd.mcp.servers.verification_server import get_checklist, run_contract_check, suggest_contract_checks

    run_result = run_contract_check(
        {
            "check_key": "contract.benchmark_reproduction",
            "binding": {"claim_ids": ["claim-benchmark"], "reference_ids": ["ref-benchmark"]},
            "metadata": {"source_reference_id": "ref-benchmark"},
            "observed": {"metric_value": 0.01, "threshold_value": 0.02},
        }
    )
    run_expected = dict(run_result)
    run_expected.pop("schema_version")
    assert run_result == run_expected

    suggest_result = suggest_contract_checks(_derived_template_contract())
    suggest_expected = dict(suggest_result)
    suggest_expected.pop("schema_version")
    assert suggest_result == suggest_expected

    checklist_result = get_checklist("qft")
    checklist_expected = dict(checklist_result)
    checklist_expected.pop("schema_version")
    assert checklist_result == checklist_expected


def test_checklist_helpers_return_defensive_copies() -> None:
    from gpd.mcp.servers.verification_server import get_bundle_checklist, get_checklist

    checklist = get_checklist("qft")
    checklist["domain_checks"][0]["check"] = "poisoned"

    fresh_checklist = get_checklist("qft")
    assert fresh_checklist["domain_checks"][0]["check"] != "poisoned"

    bundle_checklist = get_bundle_checklist(["stat-mech-simulation"])
    bundle_checklist["bundle_checks"][0]["check_ids"].append("poisoned")

    fresh_bundle_checklist = get_bundle_checklist(["stat-mech-simulation"])
    assert "poisoned" not in fresh_bundle_checklist["bundle_checks"][0]["check_ids"]


def test_run_contract_check_surfaces_machine_readable_contract_salvage_findings() -> None:
    from gpd.mcp.servers.verification_server import run_contract_check

    contract = _load_project_contract_fixture()
    contract["claims"][0]["notes"] = "legacy extra field"

    result = run_contract_check(
        {
            "check_key": "contract.benchmark_reproduction",
            "contract": contract,
            "binding": {"claim_ids": ["claim-benchmark"], "reference_ids": ["ref-benchmark"]},
            "metadata": {"source_reference_id": "ref-benchmark"},
            "observed": {"metric_value": 0.01, "threshold_value": 0.02},
        }
    )

    assert result["contract_salvaged"] is True
    assert result["contract_salvage_findings"] == ["claims.0.notes: Extra inputs are not permitted"]
    assert result["supported_binding_fields"] == [
        "binding.claim_id",
        "binding.claim_ids",
        "binding.deliverable_id",
        "binding.deliverable_ids",
        "binding.acceptance_test_id",
        "binding.acceptance_test_ids",
        "binding.reference_id",
        "binding.reference_ids",
    ]


def test_verification_server_pure_success_tools_return_stable_envelopes() -> None:
    from gpd.mcp.servers import StableMCPEnvelope
    from gpd.mcp.servers.verification_server import (
        dimensional_check,
        get_verification_coverage,
        limiting_case_check,
        symmetry_check,
    )

    assert isinstance(dimensional_check(["[M] = [M]"]), StableMCPEnvelope)
    assert isinstance(limiting_case_check("E = m c^2", {"c -> infinity": "non-rel"}), StableMCPEnvelope)
    assert isinstance(symmetry_check("M(s,t)", ["parity"]), StableMCPEnvelope)
    assert isinstance(get_verification_coverage([15], ["5.1"]), StableMCPEnvelope)
