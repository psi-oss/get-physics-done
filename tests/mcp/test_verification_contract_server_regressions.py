from __future__ import annotations

import copy
import json
from pathlib import Path

import anyio
import pytest

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "stage0"


def _load_project_contract_fixture() -> dict[str, object]:
    return json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))


def _project_local_contract_fixture(project_root: Path) -> dict[str, object]:
    contract = copy.deepcopy(_load_project_contract_fixture())
    reference = contract["references"][0]
    assert isinstance(reference, dict)
    reference["kind"] = "prior_artifact"
    reference["locator"] = "artifacts/benchmark/report.json"
    contract["context_intake"]["must_read_refs"] = []
    contract["context_intake"]["must_include_prior_outputs"] = ["GPD/phases/01-setup/01-01-SUMMARY.md"]
    contract["context_intake"]["user_asserted_anchors"] = []
    contract["context_intake"]["known_good_baselines"] = []

    artifact = project_root / "artifacts" / "benchmark" / "report.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text("{}\n", encoding="utf-8")
    baseline = project_root / "GPD" / "phases" / "01-setup" / "01-01-SUMMARY.md"
    baseline.parent.mkdir(parents=True, exist_ok=True)
    baseline.write_text("baseline summary\n", encoding="utf-8")
    return contract


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


def _run_contract_check_input_schema() -> dict[str, object]:
    from gpd.mcp.servers.verification_server import mcp

    async def _load() -> dict[str, object]:
        tools = await mcp.list_tools()
        tool = next(tool for tool in tools if tool.name == "run_contract_check")
        return tool.inputSchema

    return anyio.run(_load)


def _suggest_contract_checks_input_schema() -> dict[str, object]:
    from gpd.mcp.servers.verification_server import mcp

    async def _load() -> dict[str, object]:
        tools = await mcp.list_tools()
        tool = next(tool for tool in tools if tool.name == "suggest_contract_checks")
        return tool.inputSchema

    return anyio.run(_load)


def _schema_error_messages(schema: dict[str, object], payload: dict[str, object]) -> list[str]:
    from jsonschema import Draft202012Validator

    return [error.message for error in Draft202012Validator(schema).iter_errors(payload)]


def test_contract_check_tool_schemas_publish_optional_absolute_project_dir() -> None:
    from gpd.mcp.servers import ABSOLUTE_PROJECT_DIR_SCHEMA

    run_project_dir = _run_contract_check_input_schema()["properties"]["project_dir"]
    suggest_project_dir = _suggest_contract_checks_input_schema()["properties"]["project_dir"]

    for schema in (run_project_dir, suggest_project_dir):
        assert schema["anyOf"] == [ABSOLUTE_PROJECT_DIR_SCHEMA, {"type": "null"}]
        assert schema["default"] is None


def test_contract_check_tools_reject_relative_project_dir() -> None:
    from gpd.mcp.servers.verification_server import run_contract_check, suggest_contract_checks

    expected = {"error": "project_dir must be an absolute path", "schema_version": 1}

    assert run_contract_check({"check_key": "contract.limit_recovery"}, project_dir="relative/project") == expected
    assert suggest_contract_checks(_load_project_contract_fixture(), project_dir="relative/project") == expected


def test_run_contract_check_accepts_project_local_contract_when_project_dir_supplied(tmp_path: Path) -> None:
    from gpd.mcp.servers.verification_server import run_contract_check

    contract = _project_local_contract_fixture(tmp_path)
    request = {
        "check_key": "contract.benchmark_reproduction",
        "contract": contract,
        "binding": {"claim_ids": ["claim-benchmark"], "reference_ids": ["ref-benchmark"]},
        "metadata": {"source_reference_id": "ref-benchmark"},
        "observed": {"metric_value": 0.01, "threshold_value": 0.02},
    }

    missing_root = run_contract_check(request)
    rooted = run_contract_check(request, project_dir=tmp_path.resolve(strict=False).as_posix())

    assert "must_surface=true anchor" in missing_root["error"]
    assert rooted["status"] == "pass"


def test_suggest_contract_checks_accepts_project_local_contract_when_project_dir_supplied(tmp_path: Path) -> None:
    from gpd.mcp.servers.verification_server import suggest_contract_checks

    contract = _project_local_contract_fixture(tmp_path)

    missing_root = suggest_contract_checks(contract)
    rooted = suggest_contract_checks(contract, project_dir=tmp_path.resolve(strict=False).as_posix())

    assert "must_surface=true anchor" in missing_root["error"]
    assert "contract.benchmark_reproduction" in {entry["check_key"] for entry in rooted["suggested_checks"]}


def test_suggest_contract_checks_rejects_placeholder_only_context_intake(tmp_path: Path) -> None:
    from gpd.mcp.servers.verification_server import suggest_contract_checks

    contract = _project_local_contract_fixture(tmp_path)
    contract["context_intake"] = {
        "must_read_refs": [],
        "must_include_prior_outputs": [],
        "user_asserted_anchors": [],
        "known_good_baselines": [],
        "context_gaps": ["TBD"],
        "crucial_inputs": ["placeholder"],
    }

    result = suggest_contract_checks(contract, project_dir=tmp_path.resolve(strict=False).as_posix())

    assert "context_intake must not be empty" in result["error"]


def test_run_contract_check_accepts_non_must_surface_reference_when_project_dir_supplied(tmp_path: Path) -> None:
    from gpd.mcp.servers.verification_server import run_contract_check

    contract = _project_local_contract_fixture(tmp_path)
    reference = contract["references"][0]
    assert isinstance(reference, dict)
    reference["must_surface"] = False
    prior_output = contract["context_intake"]["must_include_prior_outputs"][0]
    assert isinstance(prior_output, str)
    grounded_output = tmp_path / prior_output
    grounded_output.parent.mkdir(parents=True, exist_ok=True)
    grounded_output.write_text("baseline summary\n", encoding="utf-8")

    request = {
        "check_key": "contract.benchmark_reproduction",
        "contract": contract,
        "binding": {"claim_ids": ["claim-benchmark"], "reference_ids": ["ref-benchmark"]},
        "metadata": {"source_reference_id": "ref-benchmark"},
        "observed": {"metric_value": 0.01, "threshold_value": 0.02},
    }

    rooted = run_contract_check(request, project_dir=tmp_path.resolve(strict=False).as_posix())

    assert rooted["status"] == "pass"


def test_suggest_contract_checks_accepts_rootless_prior_output_as_visible_context_intake() -> None:
    from gpd.mcp.servers.verification_server import suggest_contract_checks

    contract = _load_project_contract_fixture()
    contract["context_intake"] = {
        "must_read_refs": [],
        "must_include_prior_outputs": ["./RESULTS.md"],
        "user_asserted_anchors": [],
        "known_good_baselines": [],
        "context_gaps": [],
        "crucial_inputs": [],
    }

    result = suggest_contract_checks(contract)

    assert "error" not in result
    assert "suggested_checks" in result


def test_contract_server_singleton_drift_classifier_matches_core_contract_policy() -> None:
    from gpd.mcp.servers.verification_server import _is_defaultable_singleton_contract_error

    assert _is_defaultable_singleton_contract_error("context_intake must be an object, not list") is False
    assert _is_defaultable_singleton_contract_error("uncertainty_markers must be an object, not list") is False
    assert _is_defaultable_singleton_contract_error("approach_policy must be an object, not list") is False


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


def _ambiguous_direct_proxy_contract() -> dict[str, object]:
    contract = _binding_inconsistency_contract()
    contract["forbidden_proxies"].append(
        {
            "id": "fp-02",
            "subject": "claim-small-k",
            "proxy": "proxy-small-k",
            "reason": "Second proxy keeps the direct/proxy check ambiguous",
        }
    )
    return contract


def _mismatched_direct_proxy_template_contract() -> dict[str, object]:
    contract = copy.deepcopy(_load_project_contract_fixture())
    contract["deliverables"].append(
        {
            "id": "deliv-small-k",
            "kind": "figure",
            "path": "figures/small-k.png",
            "description": "Small-k proxy comparison figure",
            "must_contain": ["small-k proxy branch"],
        }
    )
    contract["claims"].append(
        {
            "id": "claim-small-k",
            "statement": "Track the small-k proxy branch",
            "observables": [],
            "deliverables": ["deliv-small-k"],
            "acceptance_tests": ["test-proxy-small-k"],
            "references": [],
        }
    )
    contract["acceptance_tests"].append(
        {
            "id": "test-proxy-small-k",
            "subject": "claim-small-k",
            "kind": "proxy",
            "procedure": "Compare the small-k proxy against the direct observable.",
            "pass_condition": "Proxy agrees with direct evidence in the small-k branch",
            "evidence_required": ["deliv-small-k"],
            "automation": "automated",
        }
    )
    return contract


def _proof_obligation_contract() -> dict[str, object]:
    return {
        "schema_version": 1,
        "scope": {"question": "Does the proof cover every named parameter and hypothesis?"},
        "context_intake": {
            "must_read_refs": ["ref-proof-outline"],
            "must_include_prior_outputs": ["GPD/phases/00-baseline/00-01-SUMMARY.md"],
        },
        "observables": [
            {
                "id": "obs-proof",
                "name": "Theorem proof obligation",
                "kind": "proof_obligation",
                "definition": "Prove the theorem for every declared parameter and regime.",
            }
        ],
        "claims": [
            {
                "id": "claim-proof",
                "statement": "For every r_0 >= 0 and chi > 0, the profile remains bounded.",
                "claim_kind": "theorem",
                "observables": ["obs-proof"],
                "deliverables": ["deliv-proof"],
                "acceptance_tests": [
                    "test-proof-params",
                    "test-proof-hypotheses",
                    "test-proof-alignment",
                    "test-proof-counterexample",
                ],
                "references": [],
                "parameters": [
                    {"symbol": "r_0", "domain_or_type": "nonnegative real"},
                    {"symbol": "chi", "domain_or_type": "positive real"},
                ],
                "hypotheses": [
                    {
                        "id": "hyp-chi",
                        "text": "chi > 0",
                        "symbols": ["chi"],
                        "category": "assumption",
                    }
                ],
                "quantifiers": ["for every r_0 >= 0", "for every chi > 0"],
                "conclusion_clauses": [
                    {"id": "concl-main", "text": "The profile remains bounded."},
                    {"id": "concl-uniform", "text": "The bound is uniform in r_0."},
                ],
                "proof_deliverables": ["deliv-proof"],
            }
        ],
        "references": [
            {
                "id": "ref-proof-outline",
                "kind": "other",
                "locator": "doi:10.1234/proof-outline",
                "aliases": [],
                "role": "background",
                "why_it_matters": "Anchors the theorem statement audited by the proof checks.",
                "applies_to": ["claim-proof"],
                "carry_forward_to": [],
                "must_surface": True,
                "required_actions": ["read"],
            }
        ],
        "deliverables": [
            {
                "id": "deliv-proof",
                "kind": "derivation",
                "path": "derivations/theorem-proof.tex",
                "description": "Full theorem proof",
            }
        ],
        "acceptance_tests": [
            {
                "id": "test-proof-params",
                "subject": "claim-proof",
                "kind": "proof_parameter_coverage",
                "procedure": "Audit every declared theorem parameter.",
                "pass_condition": "Every named theorem parameter is covered explicitly.",
                "evidence_required": ["deliv-proof"],
            },
            {
                "id": "test-proof-hypotheses",
                "subject": "claim-proof",
                "kind": "proof_hypothesis_coverage",
                "procedure": "Audit every declared theorem hypothesis.",
                "pass_condition": "Every named theorem hypothesis is covered explicitly.",
                "evidence_required": ["deliv-proof"],
            },
            {
                "id": "test-proof-alignment",
                "subject": "claim-proof",
                "kind": "claim_to_proof_alignment",
                "procedure": "Check the proof against every conclusion clause.",
                "pass_condition": "The proof establishes the theorem exactly as stated.",
                "evidence_required": ["deliv-proof"],
            },
            {
                "id": "test-proof-counterexample",
                "subject": "claim-proof",
                "kind": "counterexample_search",
                "procedure": "Search for special cases that escape the theorem scope.",
                "pass_condition": "No counterexample or narrowed subcase survives scrutiny.",
                "evidence_required": ["deliv-proof"],
            },
        ],
        "forbidden_proxies": [
            {
                "id": "fp-proof",
                "subject": "claim-proof",
                "proxy": "Centered special case only",
                "reason": "A centered proof would silently drop r_0 from the theorem.",
            }
        ],
        "uncertainty_markers": {
            "weakest_anchors": ["The proof audit must stay aligned with the current theorem statement."],
            "disconfirming_observations": ["A proof that drops r_0 or narrows the claim invalidates the theorem."],
        },
    }


def _proof_claim_without_proof_fields_contract() -> dict[str, object]:
    contract = _proof_contract()
    claim = contract["claims"][0]
    for key in ("proof_deliverables", "parameters", "hypotheses", "conclusion_clauses"):
        claim.pop(key, None)
    return contract


def _proof_obligation_claim_contract(*, include_proof_fields: bool) -> dict[str, object]:
    contract = _proof_obligation_contract()
    claim = contract["claims"][0]
    claim["claim_kind"] = "claim"
    if not include_proof_fields:
        for key in ("proof_deliverables", "parameters", "hypotheses", "conclusion_clauses"):
            claim.pop(key, None)
    return contract


def _proof_contract() -> dict[str, object]:
    return {
        "schema_version": 1,
        "scope": {
            "question": "Does the theorem proof establish the full claimed classification for all r_0 > 0?",
            "in_scope": ["proof-obligation auditing", "theorem statement alignment"],
        },
        "context_intake": {
            "must_read_refs": ["ref-proof"],
            "crucial_inputs": ["Track every theorem parameter, hypothesis, quantifier, and conclusion clause."],
        },
        "observables": [
            {
                "id": "obs-proof",
                "name": "main theorem proof obligation",
                "kind": "proof_obligation",
                "definition": "Formal proof obligation for the main classification theorem",
            }
        ],
        "claims": [
            {
                "id": "claim-theorem",
                "statement": "For all r_0 > 0 and every admissible solution obeying hyp-positive and hyp-decay, the full classification theorem holds.",
                "claim_kind": "theorem",
                "observables": ["obs-proof"],
                "deliverables": ["deliv-summary"],
                "acceptance_tests": [
                    "test-proof-hyp",
                    "test-proof-param",
                    "test-proof-quant",
                    "test-proof-align",
                    "test-proof-counterexample",
                ],
                "references": ["ref-proof"],
                "parameters": [
                    {
                        "symbol": "r_0",
                        "domain_or_type": "positive real",
                        "aliases": ["r0"],
                        "required_in_proof": True,
                    },
                    {
                        "symbol": "n",
                        "domain_or_type": "integer",
                        "required_in_proof": True,
                    },
                ],
                "hypotheses": [
                    {
                        "id": "hyp-positive",
                        "text": "r_0 > 0",
                        "symbols": ["r_0"],
                        "category": "assumption",
                        "required_in_proof": True,
                    },
                    {
                        "id": "hyp-decay",
                        "text": "the solution decays at infinity",
                        "category": "regime",
                        "required_in_proof": True,
                    },
                ],
                "quantifiers": ["for all r_0 > 0", "for every admissible solution"],
                "conclusion_clauses": [
                    {
                        "id": "conclusion-classification",
                        "text": "the full classification theorem holds",
                    },
                    {
                        "id": "conclusion-uniqueness",
                        "text": "the solution is unique",
                    },
                ],
                "proof_deliverables": ["deliv-proof"],
            }
        ],
        "deliverables": [
            {
                "id": "deliv-summary",
                "kind": "report",
                "description": "Summary note for the theorem statement",
                "must_contain": ["theorem statement"],
            },
            {
                "id": "deliv-proof",
                "kind": "derivation",
                "path": "proofs/main-theorem.tex",
                "description": "Formal proof for the main theorem",
                "must_contain": ["proof audit"],
            },
        ],
        "acceptance_tests": [
            {
                "id": "test-proof-hyp",
                "subject": "claim-theorem",
                "kind": "proof_hypothesis_coverage",
                "procedure": "Audit every named hypothesis against the proof body.",
                "pass_condition": "All required hypotheses are explicitly covered.",
                "evidence_required": ["deliv-proof"],
                "automation": "hybrid",
            },
            {
                "id": "test-proof-param",
                "subject": "claim-theorem",
                "kind": "proof_parameter_coverage",
                "procedure": "Audit every theorem parameter against the proof body.",
                "pass_condition": "All required theorem parameters remain present in the proof.",
                "evidence_required": ["deliv-proof"],
                "automation": "hybrid",
            },
            {
                "id": "test-proof-quant",
                "subject": "claim-theorem",
                "kind": "proof_quantifier_domain",
                "procedure": "Check that all quantifiers and domains survive to the proof conclusion.",
                "pass_condition": "No quantifier or domain narrowing occurs.",
                "evidence_required": ["deliv-proof"],
                "automation": "hybrid",
            },
            {
                "id": "test-proof-align",
                "subject": "claim-theorem",
                "kind": "claim_to_proof_alignment",
                "procedure": "Audit the theorem statement against the proof conclusion clause-by-clause.",
                "pass_condition": "The proof establishes the theorem exactly as stated.",
                "evidence_required": ["deliv-proof"],
                "automation": "hybrid",
            },
            {
                "id": "test-proof-counterexample",
                "subject": "claim-theorem",
                "kind": "counterexample_search",
                "procedure": "Attempt an adversarial counterexample search across dropped assumptions and parameter edges.",
                "pass_condition": "No counterexample or narrowed claim is found.",
                "evidence_required": ["deliv-proof"],
                "automation": "hybrid",
            },
        ],
        "references": [
            {
                "id": "ref-proof",
                "kind": "paper",
                "locator": "doi:10.1000/proof",
                "role": "definition",
                "why_it_matters": "Defines the theorem statement and notation for the proof audit.",
                "applies_to": ["claim-theorem"],
                "must_surface": True,
                "required_actions": ["read", "cite"],
            }
        ],
        "forbidden_proxies": [
            {
                "id": "fp-proof",
                "subject": "claim-theorem",
                "proxy": "Algebraic consistency without statement-to-proof alignment",
                "reason": "A locally consistent proof is not enough if the theorem statement is narrower or misaligned.",
            }
        ],
        "links": [],
        "uncertainty_markers": {
            "weakest_anchors": ["A hidden parameter drop could still survive a superficial audit."],
            "disconfirming_observations": ["A theorem parameter such as r_0 disappears from the proof body."],
        },
    }


def _ambiguous_proof_contract() -> dict[str, object]:
    contract = _proof_contract()
    contract["observables"].append(
        {
            "id": "obs-proof-2",
            "name": "secondary theorem proof obligation",
            "kind": "proof_obligation",
            "definition": "Formal proof obligation for a second theorem",
        }
    )
    contract["claims"].append(
        {
            "id": "claim-theorem-2",
            "statement": "For all s > 0 and every admissible branch obeying hyp-branch and hyp-regular, the auxiliary theorem holds.",
            "claim_kind": "theorem",
            "observables": ["obs-proof-2"],
            "deliverables": ["deliv-summary-2"],
            "acceptance_tests": [
                "test-proof-hyp-2",
                "test-proof-param-2",
                "test-proof-quant-2",
                "test-proof-align-2",
                "test-proof-counterexample-2",
            ],
            "references": ["ref-proof-2"],
            "parameters": [{"symbol": "s", "domain_or_type": "positive real", "required_in_proof": True}],
            "hypotheses": [
                {
                    "id": "hyp-branch",
                    "text": "the admissible branch is selected",
                    "category": "assumption",
                    "required_in_proof": True,
                },
                {
                    "id": "hyp-regular",
                    "text": "the branch remains regular",
                    "category": "regime",
                    "required_in_proof": True,
                },
            ],
            "quantifiers": ["for all s > 0"],
            "conclusion_clauses": [{"id": "conclusion-aux", "text": "the auxiliary theorem holds"}],
            "proof_deliverables": ["deliv-proof-2"],
        }
    )
    contract["deliverables"].extend(
        [
            {
                "id": "deliv-summary-2",
                "kind": "report",
                "description": "Summary note for the auxiliary theorem",
                "must_contain": ["auxiliary theorem statement"],
            },
            {
                "id": "deliv-proof-2",
                "kind": "derivation",
                "path": "proofs/aux-theorem.tex",
                "description": "Formal proof for the auxiliary theorem",
                "must_contain": ["proof audit"],
            },
        ]
    )
    contract["acceptance_tests"].extend(
        [
            {
                "id": "test-proof-hyp-2",
                "subject": "claim-theorem-2",
                "kind": "proof_hypothesis_coverage",
                "procedure": "Audit every named auxiliary hypothesis against the proof body.",
                "pass_condition": "All required auxiliary hypotheses are explicitly covered.",
                "evidence_required": ["deliv-proof-2"],
                "automation": "hybrid",
            },
            {
                "id": "test-proof-param-2",
                "subject": "claim-theorem-2",
                "kind": "proof_parameter_coverage",
                "procedure": "Audit every auxiliary theorem parameter against the proof body.",
                "pass_condition": "All required auxiliary theorem parameters remain present in the proof.",
                "evidence_required": ["deliv-proof-2"],
                "automation": "hybrid",
            },
            {
                "id": "test-proof-quant-2",
                "subject": "claim-theorem-2",
                "kind": "proof_quantifier_domain",
                "procedure": "Check that all auxiliary quantifiers and domains survive to the proof conclusion.",
                "pass_condition": "No auxiliary quantifier or domain narrowing occurs.",
                "evidence_required": ["deliv-proof-2"],
                "automation": "hybrid",
            },
            {
                "id": "test-proof-align-2",
                "subject": "claim-theorem-2",
                "kind": "claim_to_proof_alignment",
                "procedure": "Audit the auxiliary theorem statement against the proof conclusion clause-by-clause.",
                "pass_condition": "The proof establishes the auxiliary theorem exactly as stated.",
                "evidence_required": ["deliv-proof-2"],
                "automation": "hybrid",
            },
            {
                "id": "test-proof-counterexample-2",
                "subject": "claim-theorem-2",
                "kind": "counterexample_search",
                "procedure": "Attempt an adversarial counterexample search for the auxiliary theorem.",
                "pass_condition": "No auxiliary counterexample or narrowed claim is found.",
                "evidence_required": ["deliv-proof-2"],
                "automation": "hybrid",
            },
        ]
    )
    contract["references"].append(
        {
            "id": "ref-proof-2",
            "kind": "paper",
            "locator": "doi:10.1000/proof-2",
            "role": "definition",
            "why_it_matters": "Defines the auxiliary theorem statement and notation.",
            "applies_to": ["claim-theorem-2"],
            "must_surface": True,
            "required_actions": ["read"],
        }
    )
    contract["forbidden_proxies"].append(
        {
            "id": "fp-proof-2",
            "subject": "claim-theorem-2",
            "proxy": "Algebraic consistency without theorem alignment",
            "reason": "The auxiliary theorem still requires statement-to-proof alignment.",
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

    for result in (run_result, suggest_result):
        assert result["schema_version"] == 1
        assert result["error"].startswith(f"Invalid contract payload: {expected_error}")
        details = result.get("contract_error_details")
        if details is not None:
            assert expected_error in details


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


def test_contract_tools_reject_missing_schema_version() -> None:
    from gpd.mcp.servers.verification_server import run_contract_check, suggest_contract_checks

    contract = _load_project_contract_fixture()
    contract.pop("schema_version")

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

    expected = {"error": "Invalid contract payload: schema_version is required", "schema_version": 1}
    assert run_result == expected
    assert suggest_result == expected


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
    ("field_name", "expected_error", "expected_salvage_success"),
    [
        (
            "context_intake",
            "Invalid contract payload: context_intake must be an object, not list",
            False,
        ),
        (
            "approach_policy",
            "Invalid contract payload: approach_policy must be an object, not list",
            False,
        ),
        (
            "uncertainty_markers",
            "Invalid contract payload: uncertainty_markers must be an object, not list",
            False,
        ),
    ],
)
def test_contract_tools_salvage_lossy_singleton_section(
    field_name: str,
    expected_error: str | None,
    expected_salvage_success: bool,
) -> None:
    from gpd.mcp.servers.verification_server import run_contract_check, suggest_contract_checks

    contract = _load_project_contract_fixture()
    contract[field_name] = []

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

    if expected_salvage_success:
        assert run_result["status"] == "pass"
        assert run_result["contract_salvaged"] is True
        assert "approach_policy must be an object, not list" in run_result["contract_salvage_findings"]
        assert suggest_result["contract_salvaged"] is True
        assert any("approach_policy must be an object, not list" in warning for warning in suggest_result["contract_warnings"])
        return

    for result in (run_result, suggest_result):
        assert result["schema_version"] == 1
        assert result["error"] == expected_error


def test_contract_tools_reject_missing_context_intake() -> None:
    contract = _load_project_contract_fixture()
    contract.pop("context_intake", None)

    _assert_contract_tools_reject(contract, "context_intake is required")


def test_contract_tools_reject_empty_context_intake() -> None:
    contract = _load_project_contract_fixture()
    contract["context_intake"] = {}

    _assert_contract_tools_reject(contract, "context_intake must not be empty")


def test_contract_tools_reject_missing_uncertainty_marker_subfields() -> None:
    from gpd.mcp.servers.verification_server import run_contract_check, suggest_contract_checks

    contract = _load_project_contract_fixture()
    contract["uncertainty_markers"] = {}

    expected_details = [
        "uncertainty_markers.disconfirming_observations is required",
        "uncertainty_markers.weakest_anchors is required",
    ]
    expected_error = (
        "Invalid contract payload: uncertainty_markers.disconfirming_observations is required; "
        "uncertainty_markers.weakest_anchors is required"
    )

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

    for result in (run_result, suggest_result):
        assert result["schema_version"] == 1
        assert result["error"] == expected_error
        assert result["contract_error_details"] == expected_details


@pytest.mark.parametrize("field_name", ["regime", "units"])
def test_contract_tools_reject_blank_observable_regime_and_units(field_name: str) -> None:
    from gpd.mcp.servers.verification_server import run_contract_check, suggest_contract_checks

    contract = _load_project_contract_fixture()
    contract["observables"][0][field_name] = " "

    expected = {
        "error": f"Invalid contract payload: observables.0.{field_name} must be a non-empty string",
        "schema_version": 1,
    }

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

    assert run_result == expected
    assert suggest_result == expected


@pytest.mark.parametrize(
    ("path", "value"),
    [
        ("claims.0.references", "ref-benchmark"),
        ("deliverables.0.must_contain", "benchmark curve"),
        ("acceptance_tests.0.evidence_required", "ref-benchmark"),
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
    elif path == "deliverables.0.must_contain":
        contract["deliverables"][0]["must_contain"] = value
    elif path == "acceptance_tests.0.evidence_required":
        contract["acceptance_tests"][0]["evidence_required"] = value
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


@pytest.mark.parametrize(
    ("mutator", "expected_finding"),
    [
        (
            lambda contract: contract["scope"].__setitem__("in_scope", "benchmarking"),
            "scope.in_scope must be a list, not str",
        ),
        (
            lambda contract: contract["context_intake"].__setitem__("must_read_refs", "ref-benchmark"),
            "context_intake.must_read_refs must be a list, not str",
        ),
        (
            lambda contract: contract.setdefault("approach_policy", {}).__setitem__("allowed_fit_families", "power_law"),
            "approach_policy.allowed_fit_families must be a list, not str",
        ),
    ],
)
def test_contract_tools_accept_recoverable_mapping_scalar_to_list_contract_drift(
    mutator,
    expected_finding: str,
) -> None:
    from gpd.mcp.servers.verification_server import run_contract_check, suggest_contract_checks

    contract = _load_project_contract_fixture()
    mutator(contract)

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
    assert run_result["contract_salvaged"] is True
    assert expected_finding in run_result["contract_salvage_findings"]
    assert suggest_result["suggested_count"] > 0
    assert suggest_result["contract_salvaged"] is True
    assert expected_finding in suggest_result["contract_salvage_findings"]


def test_contract_tools_surface_recoverable_enum_case_drift() -> None:
    from gpd.mcp.servers.verification_server import run_contract_check, suggest_contract_checks

    contract = _load_project_contract_fixture()
    contract["acceptance_tests"][0]["kind"] = "Benchmark"

    request = {
        "check_key": "contract.benchmark_reproduction",
        "contract": contract,
        "binding": {"claim_ids": ["claim-benchmark"]},
        "metadata": {"source_reference_id": "ref-benchmark"},
        "observed": {"metric_value": 0.01, "threshold_value": 0.02},
    }

    run_result = run_contract_check(request)
    suggest_result = suggest_contract_checks(contract)

    expected_finding = "acceptance_tests.0.kind must use exact canonical value: benchmark"

    assert run_result["status"] == "pass"
    assert run_result["contract_salvaged"] is True
    assert expected_finding in run_result["contract_salvage_findings"]
    assert suggest_result["contract_salvaged"] is True
    assert expected_finding in suggest_result["contract_salvage_findings"]


def test_contract_tools_preserve_non_string_list_member_parse_error() -> None:
    contract = _load_project_contract_fixture()
    contract["context_intake"]["must_read_refs"] = [{"id": "ref-benchmark"}]

    _assert_contract_tools_reject(contract, "context_intake.must_read_refs.0: Input should be a valid string")


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
    assert "artifact_content" not in benchmark

    limit = checks["contract.limit_recovery"]["request_template"]
    assert limit["binding"]["claim_ids"] == ["claim-benchmark"]
    assert limit["binding"]["acceptance_test_ids"] == ["test-limit"]
    assert limit["binding"]["observable_ids"] == ["obs-benchmark"]
    assert limit["metadata"]["regime_label"] == "large-k"
    assert limit["metadata"]["expected_behavior"] == "Recovers the contracted large-k scaling"
    assert limit["observed"]["limit_passed"] is None
    assert limit["observed"]["observed_limit"] is None
    assert "artifact_content" not in limit

    direct_proxy = checks["contract.direct_proxy_consistency"]["request_template"]
    assert direct_proxy["binding"]["claim_ids"] == ["claim-benchmark"]
    assert direct_proxy["binding"]["forbidden_proxy_ids"] == ["fp-01"]
    assert direct_proxy["observed"]["proxy_only"] is None
    assert direct_proxy["observed"]["direct_available"] is None
    assert direct_proxy["observed"]["proxy_available"] is None
    assert direct_proxy["observed"]["consistency_passed"] is None
    assert "artifact_content" not in direct_proxy

    fit = checks["contract.fit_family_mismatch"]["request_template"]
    assert fit["binding"]["claim_ids"] == ["claim-benchmark"]
    assert fit["binding"]["acceptance_test_ids"] == ["test-fit"]
    assert fit["binding"]["observable_ids"] == ["obs-benchmark"]
    assert fit["metadata"]["declared_family"] == "power_law"
    assert fit["metadata"]["allowed_families"] == ["power_law"]
    assert fit["metadata"]["forbidden_families"] == ["polynomial"]
    assert fit["observed"]["selected_family"] is None
    assert fit["observed"]["competing_family_checked"] is None
    assert "artifact_content" not in fit

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
    assert "artifact_content" not in estimator
    assert checks["contract.benchmark_reproduction"]["supported_binding_fields"] == [
        "binding.claim_ids",
        "binding.deliverable_ids",
        "binding.acceptance_test_ids",
        "binding.reference_ids",
    ]


def test_suggest_contract_checks_derives_proof_request_templates_from_unique_proof_contract() -> None:
    from gpd.mcp.servers.verification_server import suggest_contract_checks

    result = suggest_contract_checks(_proof_contract())
    checks = {entry["check_key"]: entry for entry in result["suggested_checks"]}

    hypothesis = checks["contract.proof_hypothesis_coverage"]
    assert hypothesis["binding_targets"] == ["observable", "claim", "deliverable", "acceptance_test"]
    assert hypothesis["required_request_fields"] == ["contract", "observed.covered_hypothesis_ids"]
    assert hypothesis["request_template"]["contract"] is None
    assert hypothesis["request_template"]["binding"]["claim_ids"] == ["claim-theorem"]
    assert hypothesis["request_template"]["binding"]["deliverable_ids"] == ["deliv-proof"]
    assert hypothesis["request_template"]["binding"]["acceptance_test_ids"] == ["test-proof-hyp"]
    assert hypothesis["request_template"]["binding"]["observable_ids"] == ["obs-proof"]
    assert hypothesis["request_template"]["metadata"]["hypothesis_ids"] == ["hyp-positive", "hyp-decay"]
    assert hypothesis["request_template"]["observed"]["covered_hypothesis_ids"] is None
    assert hypothesis["request_template"]["observed"]["missing_hypothesis_ids"] is None

    parameter = checks["contract.proof_parameter_coverage"]
    assert parameter["required_request_fields"] == ["contract", "observed.covered_parameter_symbols"]
    assert parameter["request_template"]["contract"] is None
    assert parameter["request_template"]["binding"]["acceptance_test_ids"] == ["test-proof-param"]
    assert parameter["request_template"]["metadata"]["theorem_parameter_symbols"] == ["r_0", "n"]
    assert parameter["request_template"]["observed"]["covered_parameter_symbols"] is None

    quantifier = checks["contract.proof_quantifier_domain"]
    assert quantifier["required_request_fields"] == ["contract", "observed.quantifier_status", "observed.scope_status"]
    assert "metadata.quantifiers" in quantifier["optional_request_fields"]
    assert "observed.uncovered_quantifiers" in quantifier["optional_request_fields"]
    assert "metadata.quantifiers[]" not in quantifier["optional_request_fields"]
    assert quantifier["request_template"]["binding"]["acceptance_test_ids"] == ["test-proof-quant"]
    assert quantifier["request_template"]["contract"] is None
    assert quantifier["request_template"]["metadata"]["quantifiers"] == [
        "for all r_0 > 0",
        "for every admissible solution",
    ]
    assert quantifier["request_template"]["observed"]["quantifier_status"] is None
    assert quantifier["request_template"]["observed"]["scope_status"] is None

    alignment = checks["contract.claim_to_proof_alignment"]
    assert alignment["required_request_fields"] == ["contract", "observed.scope_status"]
    assert "metadata.conclusion_clause_ids" in alignment["optional_request_fields"]
    assert "metadata.conclusion_clause_ids[]" not in alignment["optional_request_fields"]
    assert alignment["request_template"]["binding"]["acceptance_test_ids"] == ["test-proof-align"]
    assert alignment["request_template"]["contract"] is None
    assert alignment["request_template"]["metadata"]["claim_statement"].startswith("For all r_0 > 0")
    assert alignment["request_template"]["metadata"]["conclusion_clause_ids"] is None
    assert alignment["request_template"]["observed"]["uncovered_conclusion_clause_ids"] is None

    counterexample = checks["contract.counterexample_search"]
    assert counterexample["required_request_fields"] == ["contract", "observed.counterexample_status"]
    assert counterexample["request_template"]["contract"] is None
    assert counterexample["request_template"]["binding"]["acceptance_test_ids"] == ["test-proof-counterexample"]
    assert counterexample["request_template"]["metadata"]["claim_statement"].startswith("For all r_0 > 0")
    assert counterexample["request_template"]["observed"]["counterexample_status"] is None


def test_suggest_contract_checks_requires_proof_claim_binding_when_proof_contract_is_ambiguous() -> None:
    from gpd.mcp.servers.verification_server import suggest_contract_checks

    result = suggest_contract_checks(_ambiguous_proof_contract())
    checks = {entry["check_key"]: entry for entry in result["suggested_checks"]}

    parameter = checks["contract.proof_parameter_coverage"]
    alignment = checks["contract.claim_to_proof_alignment"]

    assert parameter["required_request_fields"][:2] == ["contract", "binding.claim_ids"]
    assert parameter["request_template"]["binding"] == {}
    assert parameter["request_template"]["contract"] is None
    assert parameter["request_template"]["metadata"]["theorem_parameter_symbols"] is None

    assert alignment["required_request_fields"][:2] == ["contract", "binding.claim_ids"]
    assert alignment["request_template"]["binding"] == {}
    assert alignment["request_template"]["contract"] is None
    assert alignment["request_template"]["metadata"]["claim_statement"] is None


def test_suggest_contract_checks_omits_contract_derived_metadata_from_required_fields() -> None:
    from gpd.mcp.servers.verification_server import suggest_contract_checks

    result = suggest_contract_checks(_derived_template_contract())
    checks = {entry["check_key"]: entry for entry in result["suggested_checks"]}

    benchmark = checks["contract.benchmark_reproduction"]
    limit = checks["contract.limit_recovery"]
    direct_proxy = checks["contract.direct_proxy_consistency"]

    assert "metadata.source_reference_id" not in benchmark["required_request_fields"]
    assert "metadata.source_reference_id" in benchmark["optional_request_fields"]
    assert benchmark["request_template"]["metadata"]["source_reference_id"] == "ref-benchmark"

    assert "metadata.regime_label" not in limit["required_request_fields"]
    assert "metadata.expected_behavior" not in limit["required_request_fields"]
    assert limit["request_template"]["metadata"]["regime_label"] == "large-k"
    assert limit["request_template"]["metadata"]["expected_behavior"] == "Recovers the contracted large-k scaling"

    assert direct_proxy["required_request_fields"] == []
    assert direct_proxy["request_template"]["binding"]["forbidden_proxy_ids"] == ["fp-01"]


def test_suggest_contract_checks_requires_forbidden_proxy_binding_when_contract_is_ambiguous() -> None:
    from gpd.mcp.servers.verification_server import suggest_contract_checks

    result = suggest_contract_checks(_ambiguous_direct_proxy_contract())
    direct_proxy = next(entry for entry in result["suggested_checks"] if entry["check_key"] == "contract.direct_proxy_consistency")

    assert direct_proxy["required_request_fields"] == ["binding.forbidden_proxy_ids"]
    assert direct_proxy["request_template"]["binding"] == {}


def test_suggest_contract_checks_ambiguous_direct_proxy_template_round_trips_to_insufficient_evidence() -> None:
    from gpd.mcp.servers.verification_server import run_contract_check, suggest_contract_checks

    contract = _ambiguous_direct_proxy_contract()
    result = suggest_contract_checks(contract)
    direct_proxy = next(entry for entry in result["suggested_checks"] if entry["check_key"] == "contract.direct_proxy_consistency")

    run_result = run_contract_check(
        {
            "check_key": direct_proxy["check_key"],
            "contract": contract,
            **copy.deepcopy(direct_proxy["request_template"]),
        }
    )

    assert "error" not in run_result
    assert run_result["status"] == "insufficient_evidence"
    assert "binding.forbidden_proxy_ids" in run_result["missing_inputs"]


def test_suggest_contract_checks_direct_proxy_template_does_not_mix_subject_bindings() -> None:
    from gpd.mcp.servers.verification_server import suggest_contract_checks

    result = suggest_contract_checks(_mismatched_direct_proxy_template_contract())
    direct_proxy = next(entry for entry in result["suggested_checks"] if entry["check_key"] == "contract.direct_proxy_consistency")
    binding = direct_proxy["request_template"]["binding"]

    assert binding["forbidden_proxy_ids"] == ["fp-01"]
    assert binding["claim_ids"] == ["claim-benchmark"]
    assert "acceptance_test_ids" not in binding


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


def test_suggest_contract_checks_proof_templates_do_not_pass_when_reused_unchanged() -> None:
    from gpd.mcp.servers.verification_server import run_contract_check, suggest_contract_checks

    contract = _proof_contract()
    result = suggest_contract_checks(contract)

    for entry in result["suggested_checks"]:
        if not entry["check_key"].startswith("contract.proof_") and entry["check_key"] not in {
            "contract.claim_to_proof_alignment",
            "contract.counterexample_search",
        }:
            continue
        request = {
            **copy.deepcopy(entry["request_template"]),
            "check_key": entry["check_key"],
            "contract": contract,
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


def test_run_contract_check_proof_parameter_coverage_accepts_contract_aliases() -> None:
    from gpd.mcp.servers.verification_server import run_contract_check

    result = run_contract_check(
        {
            "check_key": "contract.proof_parameter_coverage",
            "contract": _proof_contract(),
            "observed": {
                "covered_parameter_symbols": ["r0", "n"],
            },
        }
    )

    assert result["status"] == "pass"
    assert result["metrics"]["proof_claim_id"] == "claim-theorem"
    assert result["metrics"]["missing_parameter_symbols"] == []


def test_run_contract_check_proof_parameter_coverage_fails_when_theorem_parameter_disappears() -> None:
    from gpd.mcp.servers.verification_server import run_contract_check

    result = run_contract_check(
        {
            "check_key": "contract.proof_parameter_coverage",
            "contract": _proof_contract(),
            "observed": {
                "covered_parameter_symbols": ["n"],
            },
        }
    )

    assert result["status"] == "fail"
    assert "Proof audit reports missing theorem parameters" in result["automated_issues"]
    assert result["metrics"]["missing_parameter_symbols"] == ["r_0"]


def test_run_contract_check_proof_hypothesis_coverage_fails_when_hypothesis_is_missing() -> None:
    from gpd.mcp.servers.verification_server import run_contract_check

    result = run_contract_check(
        {
            "check_key": "contract.proof_hypothesis_coverage",
            "contract": _proof_contract(),
            "observed": {
                "covered_hypothesis_ids": ["hyp-positive"],
            },
        }
    )

    assert result["status"] == "fail"
    assert result["metrics"]["missing_hypothesis_ids"] == ["hyp-decay"]


def test_run_contract_check_proof_quantifier_domain_fails_on_scope_narrowing() -> None:
    from gpd.mcp.servers.verification_server import run_contract_check

    result = run_contract_check(
        {
            "check_key": "contract.proof_quantifier_domain",
            "contract": _proof_contract(),
            "observed": {
                "quantifier_status": "narrowed",
                "scope_status": "narrower_than_claim",
                "uncovered_quantifiers": ["for all r_0 > 0"],
            },
        }
    )

    assert result["status"] == "fail"
    assert "quantifiers/domains" in " ".join(result["automated_issues"]).lower()


def test_run_contract_check_claim_to_proof_alignment_fails_on_uncovered_clause() -> None:
    from gpd.mcp.servers.verification_server import run_contract_check

    result = run_contract_check(
        {
            "check_key": "contract.claim_to_proof_alignment",
            "contract": _proof_contract(),
            "observed": {
                "scope_status": "matched",
                "uncovered_conclusion_clause_ids": ["conclusion-uniqueness"],
            },
        }
    )

    assert result["status"] == "fail"
    assert result["metrics"]["claim_statement"].startswith("For all r_0 > 0")


def test_run_contract_check_counterexample_search_fails_when_counterexample_is_found() -> None:
    from gpd.mcp.servers.verification_server import run_contract_check

    result = run_contract_check(
        {
            "check_key": "contract.counterexample_search",
            "contract": _proof_contract(),
            "observed": {
                "counterexample_status": "counterexample_found",
            },
        }
    )

    assert result["status"] == "fail"
    assert "counterexample" in " ".join(result["automated_issues"]).lower()


def test_run_contract_check_backfills_contract_impacts_for_decisive_passes_without_explicit_binding() -> None:
    from gpd.mcp.servers.verification_server import run_contract_check

    contract = _derived_template_contract()

    benchmark = run_contract_check(
        {
            "check_key": "contract.benchmark_reproduction",
            "contract": contract,
            "observed": {"metric_value": 0.01, "threshold_value": 0.02},
        }
    )
    limit = run_contract_check(
        {
            "check_key": "contract.limit_recovery",
            "contract": contract,
            "observed": {"limit_passed": True, "observed_limit": "large-k"},
        }
    )
    direct_proxy = run_contract_check(
        {
            "check_key": "contract.direct_proxy_consistency",
            "contract": contract,
            "observed": {"direct_available": True},
        }
    )
    fit = run_contract_check(
        {
            "check_key": "contract.fit_family_mismatch",
            "contract": contract,
            "observed": {
                "selected_family": "power_law",
                "competing_family_checked": True,
            },
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

    assert benchmark["status"] == "pass"
    assert benchmark["contract_impacts"] == ["ref-benchmark"]

    assert limit["status"] == "pass"
    assert limit["contract_impacts"] == ["claim-benchmark", "obs-benchmark"]

    assert direct_proxy["status"] == "pass"
    assert direct_proxy["contract_impacts"] == ["fp-01"]

    assert fit["status"] == "pass"
    assert fit["contract_impacts"] == ["power_law"]

    assert estimator["status"] == "pass"
    assert estimator["contract_impacts"] == ["bootstrap"]


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

    benchmark = checks["contract.benchmark_reproduction"]
    limit = checks["contract.limit_recovery"]
    fit = checks["contract.fit_family_mismatch"]
    estimator = checks["contract.estimator_family_mismatch"]

    assert "metadata.source_reference_id" in benchmark["required_request_fields"]
    assert benchmark["request_template"]["metadata"]["source_reference_id"] is None
    assert limit["request_template"]["metadata"]["regime_label"] is None
    assert limit["request_template"]["metadata"]["expected_behavior"] is None
    assert "metadata.declared_family" in fit["required_request_fields"]
    assert fit["request_template"]["metadata"]["declared_family"] is None
    assert "metadata.declared_family" in estimator["required_request_fields"]
    assert estimator["request_template"]["metadata"]["declared_family"] is None


def test_suggest_contract_checks_leaves_ambiguous_subject_bindings_unresolved() -> None:
    from gpd.mcp.servers.verification_server import suggest_contract_checks

    benchmark_result = suggest_contract_checks(_ambiguous_benchmark_binding_contract())
    benchmark_checks = {entry["check_key"]: entry for entry in benchmark_result["suggested_checks"]}
    benchmark = benchmark_checks["contract.benchmark_reproduction"]
    assert "metadata.source_reference_id" in benchmark["required_request_fields"]
    assert benchmark["request_template"]["binding"] == {}
    assert benchmark["request_template"]["metadata"]["source_reference_id"] is None

    limit_result = suggest_contract_checks(_ambiguous_limit_binding_contract())
    limit_checks = {entry["check_key"]: entry for entry in limit_result["suggested_checks"]}
    limit = limit_checks["contract.limit_recovery"]["request_template"]
    assert limit["binding"] == {}
    assert limit["metadata"]["regime_label"] is None
    assert limit["metadata"]["expected_behavior"] is None


def test_suggest_contract_checks_request_templates_validate_against_advertised_run_contract_schema() -> None:
    from gpd.mcp.servers.verification_server import suggest_contract_checks

    result = suggest_contract_checks(_derived_template_contract())
    checks = {entry["check_key"]: entry for entry in result["suggested_checks"]}

    benchmark = checks["contract.benchmark_reproduction"]["request_template"]
    limit = checks["contract.limit_recovery"]["request_template"]
    fit = checks["contract.fit_family_mismatch"]["request_template"]
    estimator = checks["contract.estimator_family_mismatch"]["request_template"]

    assert benchmark["check_key"] == "contract.benchmark_reproduction"
    assert checks["contract.benchmark_reproduction"]["check"] == "contract.benchmark_reproduction"
    assert benchmark["metadata"]["source_reference_id"] == "ref-benchmark"
    assert checks["contract.benchmark_reproduction"]["schema_required_request_fields"] == [
        "observed.metric_value",
        "observed.threshold_value",
    ]
    assert checks["contract.benchmark_reproduction"]["schema_required_request_anyof_fields"] == [
        ["metadata.source_reference_id"],
        ["contract"],
    ]
    assert benchmark["observed"]["metric_value"] is None
    assert benchmark["observed"]["threshold_value"] is None

    assert limit["metadata"]["regime_label"] == "large-k"
    assert limit["metadata"]["expected_behavior"] == "Recovers the contracted large-k scaling"
    assert limit["observed"]["limit_passed"] is None
    assert limit["observed"]["observed_limit"] is None

    assert fit["metadata"]["declared_family"] == "power_law"
    assert fit["metadata"]["allowed_families"] == ["power_law"]
    assert estimator["metadata"]["declared_family"] == "bootstrap"
    assert estimator["metadata"]["allowed_families"] == ["bootstrap"]


def test_suggest_contract_checks_proof_request_templates_validate_against_advertised_run_contract_schema() -> None:
    from gpd.mcp.servers.verification_server import suggest_contract_checks

    result = suggest_contract_checks(_proof_contract())
    checks = {entry["check_key"]: entry for entry in result["suggested_checks"]}

    hypothesis = checks["contract.proof_hypothesis_coverage"]["request_template"]
    parameter = checks["contract.proof_parameter_coverage"]["request_template"]
    alignment = checks["contract.claim_to_proof_alignment"]["request_template"]

    assert checks["contract.proof_hypothesis_coverage"]["check"] == "contract.proof_hypothesis_coverage"
    assert checks["contract.proof_parameter_coverage"]["check"] == "contract.proof_parameter_coverage"
    assert checks["contract.claim_to_proof_alignment"]["check"] == "contract.claim_to_proof_alignment"
    assert hypothesis["check_key"] == "contract.proof_hypothesis_coverage"
    assert hypothesis["contract"] is None
    assert hypothesis["metadata"]["hypothesis_ids"] == ["hyp-positive", "hyp-decay"]
    assert hypothesis["observed"]["covered_hypothesis_ids"] is None

    assert parameter["check_key"] == "contract.proof_parameter_coverage"
    assert parameter["contract"] is None
    assert parameter["metadata"]["theorem_parameter_symbols"] == ["r_0", "n"]
    assert parameter["observed"]["covered_parameter_symbols"] is None

    assert alignment["check_key"] == "contract.claim_to_proof_alignment"
    assert alignment["contract"] is None
    assert alignment["metadata"]["claim_statement"].startswith("For all r_0 > 0")
    assert alignment["metadata"]["conclusion_clause_ids"] is None
    assert alignment["observed"]["uncovered_conclusion_clause_ids"] is None


def test_run_contract_check_schema_rejects_benchmark_requests_without_source_reference_id() -> None:
    from jsonschema import Draft202012Validator

    schema = _run_contract_check_input_schema()
    validator = Draft202012Validator(schema)

    request = {
        "request": {
            "check_key": "contract.benchmark_reproduction",
            "observed": {"metric_value": 0.01, "threshold_value": 0.02},
        }
    }

    messages = [error.message for error in validator.iter_errors(request)]

    assert messages
    assert any("any of the given schemas" in message for message in messages)


def test_run_contract_check_schema_allows_benchmark_requests_without_source_reference_id_when_contract_is_present() -> None:
    from jsonschema import Draft202012Validator

    schema = _run_contract_check_input_schema()
    validator = Draft202012Validator(schema)

    request = {
        "request": {
            "check_key": "contract.benchmark_reproduction",
            "contract": _derived_template_contract(),
            "observed": {"metric_value": 0.01, "threshold_value": 0.02},
        }
    }

    messages = [error.message for error in validator.iter_errors(request)]

    assert messages == []


def test_run_contract_check_schema_rejects_contract_derived_limit_and_family_metadata_when_missing_metadata() -> None:
    from jsonschema import Draft202012Validator

    schema = _run_contract_check_input_schema()
    validator = Draft202012Validator(schema)

    requests = (
        {
            "request": {
                "check_key": "contract.limit_recovery",
                "observed": {"limit_passed": True, "observed_limit": "large-k"},
            }
        },
        {
            "request": {
                "check_key": "contract.fit_family_mismatch",
                "observed": {"selected_family": "power_law"},
            }
        },
        {
            "request": {
                "check_key": "contract.estimator_family_mismatch",
                "observed": {
                    "selected_family": "bootstrap",
                    "bias_checked": True,
                    "calibration_checked": True,
                },
            }
        },
    )

    for request in requests:
        messages = [error.message for error in validator.iter_errors(request)]

        assert messages
        assert any("metadata" in message for message in messages)


@pytest.mark.parametrize(
    ("check_key", "expected_required_fragments"),
    [
        ("contract.benchmark_reproduction", ("metadata", "observed")),
        ("contract.limit_recovery", ("metadata", "observed")),
        ("contract.fit_family_mismatch", ("metadata", "observed")),
        ("contract.estimator_family_mismatch", ("metadata", "observed")),
        ("contract.proof_parameter_coverage", ("contract", "metadata", "observed")),
        ("contract.claim_to_proof_alignment", ("contract", "observed")),
        ("contract.counterexample_search", ("contract", "observed")),
    ],
)
def test_run_contract_check_schema_rejects_identifier_only_requests_for_mandatory_sections(
    check_key: str,
    expected_required_fragments: tuple[str, ...],
) -> None:
    schema = _run_contract_check_input_schema()
    request = {"request": {"check_key": check_key}}

    messages = _schema_error_messages(schema, request)
    combined_messages = "\n".join(messages)

    assert messages
    assert any("required" in message for message in messages)
    assert any(fragment in combined_messages for fragment in expected_required_fragments)


def test_run_contract_check_schema_rejects_soft_missing_proof_audit_fields() -> None:
    from jsonschema import Draft202012Validator

    schema = _run_contract_check_input_schema()
    validator = Draft202012Validator(schema)

    requests = (
        {
            "request": {
                "check_key": "contract.proof_parameter_coverage",
                "contract": _proof_obligation_contract(),
                "metadata": {"theorem_parameter_symbols": ["r_0", "n"]},
            }
        },
        {
            "request": {
                "check_key": "contract.claim_to_proof_alignment",
                "contract": _proof_obligation_contract(),
                "observed": {"scope_status": "matched"},
            }
        },
    )

    for request in requests:
        messages = [error.message for error in validator.iter_errors(request)]

        assert messages
        assert any(fragment in "\n".join(messages) for fragment in ("metadata", "observed", "contract"))


@pytest.mark.parametrize(
    ("request_factory", "expected_valid"),
    [
        (
            lambda: {
                "request": {
                    "check_key": "contract.proof_parameter_coverage",
                    "contract": _proof_contract(),
                    "metadata": {"theorem_parameter_symbols": ["r_0", "n"]},
                    "observed": {"covered_parameter_symbols": ["r0", "n"]},
                }
            },
            True,
        ),
        (
            lambda: {
                "request": {
                    "check_key": "contract.proof_parameter_coverage",
                    "contract": _proof_claim_without_proof_fields_contract(),
                    "metadata": {"theorem_parameter_symbols": ["r_0", "n"]},
                    "observed": {"covered_parameter_symbols": ["r0", "n"]},
                }
            },
            False,
        ),
        (
            lambda: {
                "request": {
                    "check_key": "contract.proof_quantifier_domain",
                    "contract": _proof_obligation_claim_contract(include_proof_fields=True),
                    "observed": {"quantifier_status": "matched", "scope_status": "matched"},
                }
            },
            True,
        ),
        (
            lambda: {
                "request": {
                    "check_key": "contract.proof_quantifier_domain",
                    "contract": _proof_obligation_claim_contract(include_proof_fields=False),
                    "observed": {"quantifier_status": "matched", "scope_status": "matched"},
                }
            },
            False,
        ),
    ],
)
def test_run_contract_check_schema_and_runtime_stay_in_lockstep_for_proof_bearing_claims(
    request_factory,
    expected_valid: bool,
) -> None:
    schema = _run_contract_check_input_schema()
    request = request_factory()
    schema_messages = _schema_error_messages(schema, request)
    runtime_result = _call_verification_tool("run_contract_check", request)

    assert (not schema_messages) is expected_valid
    assert (runtime_result.get("status") == "pass") is expected_valid


def test_run_contract_check_blocks_proof_checks_for_repair_relevant_salvaged_contracts() -> None:
    from gpd.mcp.servers.verification_server import run_contract_check

    contract = _proof_contract()
    contract["context_intake"]["must_read_refs"] = "ref-proof"

    result = run_contract_check(
        {
            "check_key": "contract.proof_parameter_coverage",
            "contract": contract,
            "metadata": {"theorem_parameter_symbols": ["r_0", "n"]},
            "observed": {"covered_parameter_symbols": ["r0", "n"]},
        }
    )

    assert result == {"error": "Proof checks require an authoritative contract payload", "schema_version": 1}


def test_run_contract_check_allows_case_only_salvage_for_proof_checks() -> None:
    from gpd.mcp.servers.verification_server import run_contract_check

    contract = _proof_contract()
    contract["acceptance_tests"][0]["kind"] = "Proof_Parameter_Coverage"

    result = run_contract_check(
        {
            "check_key": "contract.proof_parameter_coverage",
            "contract": contract,
            "metadata": {"theorem_parameter_symbols": ["r_0", "n"]},
            "observed": {"covered_parameter_symbols": ["r0", "n"]},
        }
    )

    assert result["status"] == "pass"
    assert result["contract_salvaged"] is True


def test_run_contract_check_schema_and_runtime_stay_in_lockstep_for_recoverable_contract_payload_drift() -> None:
    contract = _load_project_contract_fixture()
    contract["context_intake"]["must_read_refs"] = "ref-benchmark"
    contract["deliverables"][0]["kind"] = "Figure"
    contract["references"][0]["required_actions"] = "Read"

    request = {
        "request": {
            "check_key": "contract.benchmark_reproduction",
            "contract": contract,
            "binding": {"claim_ids": ["claim-benchmark"]},
            "metadata": {"source_reference_id": "ref-benchmark"},
            "observed": {"metric_value": 0.01, "threshold_value": 0.02},
        }
    }

    schema_messages = _schema_error_messages(_run_contract_check_input_schema(), request)
    result = _call_verification_tool("run_contract_check", request)

    assert schema_messages != []
    assert result["status"] == "pass"
    assert result["contract_salvaged"] is True
    assert "context_intake.must_read_refs must be a list, not str" in result["contract_salvage_findings"]
    assert "deliverables.0.kind must use exact canonical value: figure" in result["contract_salvage_findings"]
    assert "references.0.required_actions must be a list, not str" in result["contract_salvage_findings"]


def test_suggest_contract_checks_schema_and_runtime_stay_in_lockstep_for_nested_proof_field_salvage() -> None:
    contract = _proof_contract()
    contract["claims"][0]["parameters"][0]["aliases"] = "r0"
    contract["claims"][0]["hypotheses"][0]["symbols"] = "r_0"
    contract["acceptance_tests"][0]["kind"] = "Proof_Parameter_Coverage"

    payload = {"contract": contract}

    schema_messages = _schema_error_messages(_suggest_contract_checks_input_schema(), payload)
    result = _call_verification_tool("suggest_contract_checks", payload)

    assert schema_messages != []
    assert result["suggested_count"] > 0
    assert result["contract_salvaged"] is True
    assert "claims.0.parameters.0.aliases must be a list, not str" in result["contract_salvage_findings"]
    assert "claims.0.hypotheses.0.symbols must be a list, not str" in result["contract_salvage_findings"]
    assert "acceptance_tests.0.kind must use exact canonical value: proof_parameter_coverage" in result[
        "contract_salvage_findings"
    ]


def test_run_contract_check_schema_rejects_explicit_empty_optional_contract_collections_when_metadata_is_missing() -> None:
    from jsonschema import Draft202012Validator

    schema = _run_contract_check_input_schema()
    validator = Draft202012Validator(schema)

    request = {
        "request": {
            "check_key": "contract.limit_recovery",
            "contract": {
                "schema_version": 1,
                "scope": {"question": "What is the asymptotic limit?"},
                "context_intake": {"context_gaps": ["Need benchmark reconciliation."]},
                "claims": [],
                "deliverables": [],
                "acceptance_tests": [],
                "references": [],
                "forbidden_proxies": [],
                "links": [],
                "uncertainty_markers": {
                    "weakest_anchors": ["No validated benchmark yet."],
                    "disconfirming_observations": ["Large-k behavior could still flip sign."],
                },
            },
        }
    }

    messages = [error.message for error in validator.iter_errors(request)]

    assert messages
    assert any("metadata" in message for message in messages)


def test_run_contract_check_schema_surfaces_duplicate_contract_string_list_rejection() -> None:
    request = {
        "request": {
            "check_key": "contract.limit_recovery",
            "contract": {
                "schema_version": 1,
                "scope": {"question": "What is the large-k limit?"},
                "context_intake": {"must_read_refs": ["ref-main", " ref-main "]},
                "uncertainty_markers": {
                    "weakest_anchors": ["Benchmark still tentative"],
                    "disconfirming_observations": ["Limit fails against the published asymptote"],
                },
            },
            "metadata": {"regime_label": "large-k", "expected_behavior": "approaches benchmark asymptote"},
            "observed": {"limit_passed": True, "observed_limit": "large-k"},
        }
    }

    messages = _schema_error_messages(_run_contract_check_input_schema(), request)
    runtime_result = _call_verification_tool("run_contract_check", request)

    assert messages
    assert runtime_result == {
        "error": "Invalid contract payload: context_intake.must_read_refs.1 is a duplicate",
        "schema_version": 1,
    }


def test_run_contract_check_schema_requires_one_trimmed_identifier() -> None:
    from jsonschema import Draft202012Validator

    schema = _run_contract_check_input_schema()
    validator = Draft202012Validator(schema)

    invalid_requests = (
        {},
        {"check_key": None},
        {"check_key": " contract.limit_recovery"},
    )

    for request in invalid_requests:
        assert list(validator.iter_errors({"request": request})) != []

    assert list(validator.iter_errors({"request": {"check_key": "contract.direct_proxy_consistency"}})) == []


def test_suggest_contract_checks_unique_context_drops_redundant_selector_metadata_without_policy_defaults() -> None:
    from gpd.mcp.servers.verification_server import suggest_contract_checks

    contract = _derived_template_contract()
    contract.pop("approach_policy", None)

    result = suggest_contract_checks(contract)
    checks = {entry["check_key"]: entry for entry in result["suggested_checks"]}

    benchmark = checks["contract.benchmark_reproduction"]
    limit = checks["contract.limit_recovery"]

    assert benchmark["required_request_fields"] == [
        "observed.metric_value",
        "observed.threshold_value",
    ]
    assert benchmark["request_template"]["metadata"]["source_reference_id"] == "ref-benchmark"

    assert limit["required_request_fields"] == []
    assert limit["request_template"]["metadata"]["regime_label"] == "large-k"
    assert limit["request_template"]["metadata"]["expected_behavior"] == "Recovers the contracted large-k scaling"


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


def test_run_contract_check_unique_bound_context_does_not_require_redundant_selector_metadata() -> None:
    from gpd.mcp.servers.verification_server import run_contract_check

    benchmark = run_contract_check(
        {
            "check_key": "contract.benchmark_reproduction",
            "contract": _ambiguous_benchmark_binding_contract(),
            "binding": {"acceptance_test_ids": ["test-benchmark"]},
            "observed": {"metric_value": 0.01, "threshold_value": 0.02},
        }
    )
    limit = run_contract_check(
        {
            "check_key": "contract.limit_recovery",
            "contract": _multi_limit_contract(),
            "binding": {"claim_ids": ["claim-small-k"]},
            "observed": {"limit_passed": True, "observed_limit": "small-k"},
        }
    )

    assert benchmark["status"] == "pass"
    assert benchmark["missing_inputs"] == []
    assert benchmark["automated_issues"] == []
    assert benchmark["metrics"]["source_reference_id"] == "ref-benchmark"

    assert limit["status"] == "pass"
    assert limit["missing_inputs"] == []
    assert limit["automated_issues"] == []
    assert limit["metrics"]["regime_label"] == "small-k"


def test_run_contract_check_direct_proxy_consistency_ambiguous_contract_requires_binding() -> None:
    from gpd.mcp.servers.verification_server import run_contract_check

    result = run_contract_check(
        {
            "check_key": "contract.direct_proxy_consistency",
            "contract": _binding_inconsistency_contract(),
            "observed": {
                "direct_available": True,
                "proxy_available": True,
                "consistency_passed": True,
            },
        }
    )

    assert result["status"] == "insufficient_evidence"
    assert "binding.forbidden_proxy_ids" in result["missing_inputs"]
    assert "Ambiguous direct/proxy context requires an explicit forbidden proxy binding" in result["automated_issues"]


def test_run_contract_check_direct_proxy_consistency_bound_proxy_can_resolve_ambiguous_contract() -> None:
    from gpd.mcp.servers.verification_server import run_contract_check

    result = run_contract_check(
        {
            "check_key": "contract.direct_proxy_consistency",
            "contract": _binding_inconsistency_contract(),
            "binding": {"forbidden_proxy_ids": ["fp-01"]},
            "observed": {
                "direct_available": True,
                "proxy_available": True,
                "consistency_passed": True,
            },
        }
    )

    assert result["status"] == "pass"
    assert result["missing_inputs"] == []
    assert result["automated_issues"] == []
    assert result["contract_impacts"] == ["fp-01"]


def test_run_contract_check_direct_proxy_consistency_rejects_mixed_forbidden_proxy_and_acceptance_test_subjects() -> None:
    from gpd.mcp.servers.verification_server import run_contract_check

    result = run_contract_check(
        {
            "check_key": "contract.direct_proxy_consistency",
            "contract": _mismatched_direct_proxy_template_contract(),
            "binding": {
                "forbidden_proxy_ids": ["fp-01"],
                "acceptance_test_ids": ["test-proxy-small-k"],
            },
            "observed": {"direct_available": True},
        }
    )

    assert "error" not in result
    assert result["status"] == "insufficient_evidence"
    assert any("binding contexts disagree on claim targets" in issue for issue in result["automated_issues"])


def test_run_contract_check_limit_recovery_derives_expected_behavior_from_regime_metadata() -> None:
    from gpd.mcp.servers.verification_server import run_contract_check

    result = run_contract_check(
        {
            "check_key": "contract.limit_recovery",
            "contract": _multi_limit_contract(),
            "metadata": {"regime_label": "small-k"},
            "observed": {"limit_passed": True, "observed_limit": "small-k"},
        }
    )

    assert result["status"] == "pass"
    assert result["missing_inputs"] == []
    assert result["automated_issues"] == []
    assert result["metrics"]["regime_label"] == "small-k"


def test_run_contract_check_limit_recovery_rejects_mismatched_expected_behavior() -> None:
    from gpd.mcp.servers.verification_server import run_contract_check

    result = run_contract_check(
        {
            "check_key": "contract.limit_recovery",
            "contract": _multi_limit_contract(),
            "metadata": {"regime_label": "small-k", "expected_behavior": "WRONG"},
            "observed": {"limit_passed": True, "observed_limit": "small-k"},
        }
    )

    assert result["status"] == "insufficient_evidence"
    assert "metadata.expected_behavior" in result["missing_inputs"]
    assert any(
        issue.startswith("metadata.expected_behavior does not match the resolved contract context; expected")
        for issue in result["automated_issues"]
    )


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


def test_contract_tools_reject_unknown_nested_contract_fields() -> None:
    from gpd.contracts import parse_project_contract_data_salvage
    from gpd.mcp.servers.verification_server import run_contract_check, suggest_contract_checks

    contract = _load_project_contract_fixture()
    contract["references"][0]["notes"] = "legacy extra field"
    salvage_result = parse_project_contract_data_salvage(copy.deepcopy(contract))

    request = {
        "check_key": "contract.benchmark_reproduction",
        "contract": contract,
        "binding": {"claim_ids": ["claim-benchmark"]},
        "metadata": {"source_reference_id": "ref-benchmark"},
        "observed": {"metric_value": 0.01, "threshold_value": 0.02},
    }

    run_result = run_contract_check(request)
    suggest_result = suggest_contract_checks(contract)

    expected = {
        "error": "Invalid contract payload: references.0.notes: Extra inputs are not permitted",
        "schema_version": 1,
    }

    assert salvage_result.recoverable_errors == ["references.0.notes: Extra inputs are not permitted"]
    assert run_result == expected
    assert suggest_result == expected


def test_suggest_contract_checks_rejects_unknown_nested_contract_field_salvage_metadata() -> None:
    from gpd.contracts import parse_project_contract_data_salvage
    from gpd.mcp.servers.verification_server import suggest_contract_checks

    contract = _load_project_contract_fixture()
    contract["references"][0]["notes"] = "legacy extra field"
    salvage_result = parse_project_contract_data_salvage(copy.deepcopy(contract))

    result = suggest_contract_checks(contract)

    assert salvage_result.recoverable_errors == ["references.0.notes: Extra inputs are not permitted"]
    assert result == {
        "error": "Invalid contract payload: references.0.notes: Extra inputs are not permitted",
        "schema_version": 1,
    }


def test_contract_from_data_drops_nested_unknown_scope_fields() -> None:
    from gpd.contracts import parse_project_contract_data_salvage

    contract = _load_project_contract_fixture()
    contract["scope"]["legacy_notes"] = "nested extra field"

    parsed = parse_project_contract_data_salvage(contract)

    assert parsed is not None
    assert parsed.contract is not None
    assert parsed.contract.scope.question == contract["scope"]["question"]
    assert "legacy_notes" not in parsed.contract.scope.model_dump()


def test_contract_from_data_strict_probe_rejects_nested_unknown_scope_fields() -> None:
    from gpd.contracts import contract_from_data

    contract = _load_project_contract_fixture()
    contract["scope"]["legacy_notes"] = "nested extra field"

    assert contract_from_data(contract, allow_recoverable_warnings=False) is None


def test_contract_tools_reject_unknown_top_level_contract_fields() -> None:
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

    expected_error = {
        "error": "Invalid contract payload: legacy_notes: Extra inputs are not permitted",
        "schema_version": 1,
    }
    assert run_result == expected_error
    assert suggest_result == expected_error


@pytest.mark.parametrize(
    ("mutator", "getter", "expected_value", "expected_salvage_findings", "expected_error"),
    [
        (
            lambda contract: contract["deliverables"][0].__setitem__("kind", "Figure"),
            lambda parsed: parsed.deliverables[0].kind,
            "figure",
            ["deliverables.0.kind must use exact canonical value: figure"],
            None,
        ),
        (
            lambda contract: contract["acceptance_tests"][0].__setitem__("automation", "Automated"),
            lambda parsed: parsed.acceptance_tests[0].automation,
            "automated",
            ["acceptance_tests.0.automation must use exact canonical value: automated"],
            None,
        ),
        (
            lambda contract: contract["references"][0].__setitem__("required_actions", "Read"),
            lambda parsed: parsed.references[0].required_actions,
            ["read"],
            ["references.0.required_actions must be a list, not str"],
            None,
        ),
    ],
)
def test_contract_tools_normalize_recoverable_enum_literals(
    mutator,
    getter,
    expected_value,
    expected_salvage_findings: list[str],
    expected_error: str | None,
) -> None:
    from gpd.contracts import contract_from_data_salvage
    from gpd.mcp.servers.verification_server import run_contract_check, suggest_contract_checks

    contract = _load_project_contract_fixture()
    mutator(contract)

    parsed = contract_from_data_salvage(copy.deepcopy(contract))

    assert parsed is not None
    assert getter(parsed) == expected_value

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

    if expected_error is None:
        assert run_result["status"] == "pass"
        assert run_result["contract_salvaged"] is bool(expected_salvage_findings)
        assert run_result["contract_salvage_findings"] == expected_salvage_findings
        assert suggest_result["suggested_count"] > 0
        assert suggest_result["contract_salvaged"] is bool(expected_salvage_findings)
        assert suggest_result["contract_salvage_findings"] == expected_salvage_findings
    else:
        expected = {"error": expected_error, "schema_version": 1}
        assert run_result == expected
        assert suggest_result == expected


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
            "run_contract_check",
            {"request": {}},
            {"error": "Missing check_key", "schema_version": 1},
        ),
        (
            "run_contract_check",
            {"request": {"check_key": " contract.limit_recovery"}},
            {"error": "check_key must not include leading or trailing whitespace", "schema_version": 1},
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
    ("tool_name", "arguments", "expected"),
    [
        ("run_contract_check", {}, {"error": "request is required", "schema_version": 1}),
        ("suggest_contract_checks", {}, {"error": "contract is required", "schema_version": 1}),
    ],
)
def test_contract_tools_normalize_missing_top_level_mcp_arguments(
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
            "references.0.required_actions.3: Input should be 'read', 'use', 'compare', 'cite' or 'avoid'",
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
    ("mutator", "expected_error", "expected_details"),
    [
        (
            lambda contract: contract["claims"][0].__setitem__("references", "   "),
            (
                "claims.0.references must not be blank; "
                "claims.0.references was normalized from blank string to empty list"
            ),
            [
                "claims.0.references must not be blank",
                "claims.0.references was normalized from blank string to empty list",
            ],
        ),
        (
            lambda contract: contract["scope"].__setitem__("in_scope", "   "),
            (
                "scope.in_scope must not be blank; "
                "scope.in_scope was normalized from blank string to empty list"
            ),
            [
                "scope.in_scope must not be blank",
                "scope.in_scope was normalized from blank string to empty list",
            ],
        ),
    ],
)
def test_contract_tools_reject_blank_scalar_to_list_contract_drift(
    mutator,
    expected_error: str,
    expected_details: list[str],
) -> None:
    from gpd.mcp.servers.verification_server import run_contract_check, suggest_contract_checks

    contract = _load_project_contract_fixture()
    mutator(contract)

    request = {
        "check_key": "contract.benchmark_reproduction",
        "contract": contract,
        "binding": {"claim_ids": ["claim-benchmark"]},
        "metadata": {"source_reference_id": "ref-benchmark"},
        "observed": {"metric_value": 0.01, "threshold_value": 0.02},
    }

    for result in (run_contract_check(request), suggest_contract_checks(contract)):
        assert result["schema_version"] == 1
        assert result["error"].startswith(f"Invalid contract payload: {expected_error}")
        assert result["contract_error_details"] == expected_details


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
            "binding.claim_ids must be a list of strings",
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


def test_contract_tools_reject_cross_link_invalid_contracts() -> None:
    from gpd.mcp.servers.verification_server import run_contract_check, suggest_contract_checks

    contract = _load_project_contract_fixture()
    contract["claims"][0]["references"] = ["missing-ref"]

    request = {
        "check_key": "contract.benchmark_reproduction",
        "contract": contract,
        "binding": {"claim_ids": ["claim-benchmark"]},
        "metadata": {"source_reference_id": "ref-benchmark"},
        "observed": {"metric_value": 0.01, "threshold_value": 0.02},
    }

    expected = {
        "error": "Invalid contract payload: claim claim-benchmark references unknown reference missing-ref",
        "schema_version": 1,
    }
    assert run_contract_check(request) == expected
    assert suggest_contract_checks(contract) == expected


def test_contract_tools_surface_full_contract_error_details_for_multi_error_payloads() -> None:
    from gpd.mcp.servers.verification_server import run_contract_check, suggest_contract_checks

    contract = _load_project_contract_fixture()
    contract["scope"]["in_scope"] = "   "
    contract["claims"][0]["references"] = "   "
    contract["references"][0]["aliases"] = "   "
    contract["references"][0]["required_actions"].append(17)

    request = {
        "check_key": "contract.benchmark_reproduction",
        "contract": contract,
        "binding": {"claim_ids": ["claim-benchmark"]},
        "metadata": {"source_reference_id": "ref-benchmark"},
        "observed": {"metric_value": 0.01, "threshold_value": 0.02},
    }

    run_result = run_contract_check(request)
    suggest_result = suggest_contract_checks(contract)

    expected_details = [
        "scope.in_scope must not be blank",
        "scope.in_scope was normalized from blank string to empty list",
        "claims.0.references must not be blank",
        "claims.0.references was normalized from blank string to empty list",
        "references.0.aliases must not be blank",
        "references.0.aliases was normalized from blank string to empty list",
        "references.0.required_actions.3: Input should be 'read', 'use', 'compare', 'cite' or 'avoid'",
    ]

    assert run_result["error"] == (
        "Invalid contract payload: scope.in_scope must not be blank; "
        "scope.in_scope was normalized from blank string to empty list; "
        "claims.0.references must not be blank; +4 more"
    )
    assert run_result["contract_error_details"] == expected_details
    assert suggest_result["error"] == run_result["error"]
    assert suggest_result["contract_error_details"] == expected_details


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
    from gpd.mcp.servers.verification_server import run_contract_check, suggest_contract_checks

    contract = _load_project_contract_fixture()
    contract["references"][0]["notes"] = "legacy extra field"
    contract["deliverables"][0]["id"] = "claim-benchmark"

    request = {
        "check_key": "contract.benchmark_reproduction",
        "contract": contract,
        "binding": {"claim_ids": ["claim-benchmark"]},
        "metadata": {"source_reference_id": "ref-benchmark"},
        "observed": {"metric_value": 0.01, "threshold_value": 0.02},
    }
    expected_details = [
        "references.0.notes: Extra inputs are not permitted",
        "contract id claim-benchmark is reused across claim, deliverable; target resolution is ambiguous",
    ]
    expected_error = (
        "Invalid contract payload: references.0.notes: Extra inputs are not permitted; "
        "contract id claim-benchmark is reused across claim, deliverable; target resolution is ambiguous"
    )

    run_result = run_contract_check(request)
    suggest_result = suggest_contract_checks(contract)

    for result in (run_result, suggest_result):
        assert result["schema_version"] == 1
        assert result["error"] == expected_error
        assert result["contract_error_details"] == expected_details


def test_verification_server_success_responses_keep_strict_stable_envelopes() -> None:
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
    assert run_result != run_expected
    assert run_result == {"schema_version": 1, **run_expected}

    suggest_result = suggest_contract_checks(_derived_template_contract())
    suggest_expected = dict(suggest_result)
    suggest_expected.pop("schema_version")
    assert suggest_result != suggest_expected
    assert suggest_result == {"schema_version": 1, **suggest_expected}

    checklist_result = get_checklist("qft")
    checklist_expected = dict(checklist_result)
    checklist_expected.pop("schema_version")
    assert checklist_result != checklist_expected
    assert checklist_result == {"schema_version": 1, **checklist_expected}


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


def test_run_contract_check_surfaces_unknown_nested_contract_field_salvage_metadata() -> None:
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

    assert result == {
        "error": "Invalid contract payload: claims.0.notes: Extra inputs are not permitted",
        "schema_version": 1,
    }


def test_suggest_contract_checks_includes_proof_redteam_checks_for_proof_obligations() -> None:
    result = _call_verification_tool("suggest_contract_checks", {"contract": _proof_obligation_contract()})

    suggested = {entry["check_key"] for entry in result["suggested_checks"]}

    assert {
        "contract.proof_hypothesis_coverage",
        "contract.proof_parameter_coverage",
        "contract.proof_quantifier_domain",
        "contract.claim_to_proof_alignment",
        "contract.counterexample_search",
    } <= suggested


def test_run_contract_check_proof_parameter_coverage_fails_when_r0_disappears_from_the_proof() -> None:
    result = _call_verification_tool(
        "run_contract_check",
        {
            "request": {
                "check_key": "contract.proof_parameter_coverage",
                "contract": _proof_obligation_contract(),
                "binding": {"claim_ids": ["claim-proof"]},
                "metadata": {"theorem_parameter_symbols": ["r_0", "chi"]},
                "observed": {
                    "covered_parameter_symbols": ["chi"],
                    "missing_parameter_symbols": [],
                },
            }
        },
    )

    assert result["status"] == "fail"
    assert "Proof audit reports missing theorem parameters" in result["automated_issues"]
    assert result["metrics"]["missing_parameter_symbols"] == ["r_0"]


def test_run_contract_check_claim_to_proof_alignment_fails_for_narrower_theorem_subcases() -> None:
    result = _call_verification_tool(
        "run_contract_check",
        {
            "request": {
                "check_key": "contract.claim_to_proof_alignment",
                "contract": _proof_obligation_contract(),
                "binding": {"claim_ids": ["claim-proof"]},
                "metadata": {"conclusion_clause_ids": ["concl-main", "concl-uniform"]},
                "observed": {
                    "uncovered_conclusion_clause_ids": ["concl-uniform"],
                    "scope_status": "narrower_than_claim",
                },
            }
        },
    )

    assert result["status"] == "fail"
    assert "Proof establishes a narrower claim or leaves conclusion clauses uncovered" in result["automated_issues"]
    assert result["metrics"]["uncovered_conclusion_clause_ids"] == ["concl-uniform"]


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
