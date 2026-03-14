"""Tests for metadata-driven protocol bundle selection."""

from __future__ import annotations

from gpd.contracts import ResearchContract
from gpd.core.protocol_bundles import (
    get_protocol_bundle,
    list_protocol_bundles,
    render_protocol_bundle_context,
    select_protocol_bundles,
)


def _stat_mech_contract() -> ResearchContract:
    return ResearchContract.model_validate(
        {
            "scope": {
                "question": "What critical exponents and finite-size scaling collapse does the simulation recover?",
            },
            "observables": [
                {
                    "id": "obs-binder",
                    "name": "Binder cumulant crossing",
                    "kind": "curve",
                    "definition": "Binder cumulant across temperature and system size",
                }
            ],
            "claims": [
                {
                    "id": "claim-critical",
                    "statement": "The model exhibits the expected universality class",
                    "deliverables": ["deliv-dataset", "deliv-figure"],
                    "acceptance_tests": ["test-benchmark"],
                    "references": ["ref-benchmark"],
                }
            ],
            "deliverables": [
                {
                    "id": "deliv-dataset",
                    "kind": "dataset",
                    "path": "results/raw-measurements.csv",
                    "description": "Raw Monte Carlo measurements with metadata",
                },
                {
                    "id": "deliv-figure",
                    "kind": "figure",
                    "path": "figures/finite-size-collapse.png",
                    "description": "Finite-size scaling collapse figure",
                },
            ],
            "acceptance_tests": [
                {
                    "id": "test-benchmark",
                    "subject": "claim-critical",
                    "kind": "benchmark",
                    "procedure": "Compare finite-size scaling and critical exponents against high-precision literature benchmarks",
                    "pass_condition": "Recovered exponents match benchmark within uncertainty",
                }
            ],
            "references": [
                {
                    "id": "ref-benchmark",
                    "kind": "paper",
                    "locator": "High-precision Monte Carlo benchmark paper",
                    "role": "benchmark",
                    "why_it_matters": "Decisive benchmark for universality and finite-size behavior",
                    "required_actions": ["read", "compare", "cite"],
                }
            ],
            "forbidden_proxies": [
                {
                    "id": "fp-trend",
                    "subject": "claim-critical",
                    "proxy": "Qualitative agreement without benchmarked scaling analysis",
                    "reason": "Would allow false progress through pretty plots alone",
                }
            ],
            "uncertainty_markers": {
                "weakest_anchors": ["Autocorrelation estimate near criticality"],
                "disconfirming_observations": ["Finite-size crossings drift outside the expected universality window"],
            },
        }
    )


def _benchmark_only_contract() -> ResearchContract:
    return ResearchContract.model_validate(
        {
            "scope": {
                "question": "Does the output match a benchmark?",
            },
            "acceptance_tests": [
                {
                    "id": "test-benchmark",
                    "subject": "claim-generic",
                    "kind": "benchmark",
                    "procedure": "Compare against a benchmark.",
                    "pass_condition": "Matches benchmark.",
                }
            ],
            "references": [
                {
                    "id": "ref-benchmark",
                    "kind": "paper",
                    "locator": "Benchmark paper",
                    "role": "benchmark",
                    "why_it_matters": "Reference comparison.",
                }
            ],
        }
    )


def test_bundle_registry_lists_exemplar_bundle() -> None:
    bundle_ids = {bundle.bundle_id for bundle in list_protocol_bundles()}
    assert "stat-mech-simulation" in bundle_ids


def test_get_protocol_bundle_returns_verifier_extensions() -> None:
    bundle = get_protocol_bundle("stat-mech-simulation")

    assert bundle is not None
    assert bundle.trigger.min_term_matches == 2
    assert bundle.trigger.min_tag_matches == 1
    assert bundle.assets.subfield_guides[0].path == "references/subfields/stat-mech.md"
    assert bundle.verifier_extensions[0].check_ids == ["5.4", "5.14", "5.16"]


def test_select_protocol_bundles_uses_project_metadata_and_contract() -> None:
    project_text = """
    # Test Project

    ## What This Is
    Monte Carlo study of a statistical mechanics lattice model near the critical point.

    ## Research Context

    ### Theoretical Framework
    Statistical mechanics

    ### Known Results
    Compare Binder cumulants, autocorrelation times, and finite-size scaling to benchmark data.
    """

    selected = select_protocol_bundles(project_text, _stat_mech_contract())

    assert [bundle.bundle_id for bundle in selected] == ["stat-mech-simulation"]
    assert "acceptance-kind:benchmark" in selected[0].matched_tags
    assert "finite-size scaling" in selected[0].matched_terms
    assert "references/protocols/monte-carlo.md" in selected[0].asset_paths


def test_render_protocol_bundle_context_is_explicit_when_none_selected() -> None:
    rendered = render_protocol_bundle_context([])

    assert "None selected from project metadata" in rendered


def test_render_protocol_bundle_context_surfaces_guidance() -> None:
    selected = select_protocol_bundles(
        "Statistical mechanics Monte Carlo with autocorrelation and finite-size scaling benchmarks.",
        _stat_mech_contract(),
    )

    rendered = render_protocol_bundle_context(selected)

    assert "Statistical Mechanics Simulation [stat-mech-simulation]" in rendered
    assert "Estimator policies:" in rendered
    assert "Verifier extensions:" in rendered
    assert "{GPD_INSTALL_DIR}/references/protocols/monte-carlo.md" in rendered


def test_select_protocol_bundles_rejects_weak_text_only_overlap() -> None:
    selected = select_protocol_bundles(
        "Monte Carlo autocorrelation study with some benchmark notes.",
        None,
    )

    assert selected == []


def test_select_protocol_bundles_rejects_benchmark_tags_without_enough_distinctive_terms() -> None:
    selected = select_protocol_bundles(
        "Monte Carlo benchmark comparison for a generic model.",
        _benchmark_only_contract(),
    )

    assert selected == []
