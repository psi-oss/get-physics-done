"""Tests for metadata-driven protocol bundle selection."""

from __future__ import annotations

import pytest

from gpd.contracts import ResearchContract
from gpd.core.protocol_bundles import (
    get_protocol_bundle,
    invalidate_protocol_bundle_cache,
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


def _project_text(what_this_is: str, framework: str, known_results: str) -> str:
    return f"""
    # Test Project

    ## What This Is
    {what_this_is}

    ## Research Context

    ### Theoretical Framework
    {framework}

    ### Known Results
    {known_results}
    """


def _bundle_contract(
    *,
    question: str,
    observable_name: str,
    observable_kind: str,
    observable_definition: str,
    claim_statement: str,
    dataset_path: str,
    figure_path: str,
    procedure: str,
    pass_condition: str,
    reference_locator: str,
    reference_why: str,
    forbidden_proxy: str,
) -> ResearchContract:
    return ResearchContract.model_validate(
        {
            "scope": {
                "question": question,
            },
            "observables": [
                {
                    "id": "obs-primary",
                    "name": observable_name,
                    "kind": observable_kind,
                    "definition": observable_definition,
                }
            ],
            "claims": [
                {
                    "id": "claim-primary",
                    "statement": claim_statement,
                    "deliverables": ["deliv-data", "deliv-figure"],
                    "acceptance_tests": ["test-benchmark"],
                    "references": ["ref-benchmark"],
                }
            ],
            "deliverables": [
                {
                    "id": "deliv-data",
                    "kind": "dataset",
                    "path": dataset_path,
                    "description": "Primary dataset or checkpoint artifact",
                },
                {
                    "id": "deliv-figure",
                    "kind": "figure",
                    "path": figure_path,
                    "description": "Primary benchmark or comparison figure",
                },
            ],
            "acceptance_tests": [
                {
                    "id": "test-benchmark",
                    "subject": "claim-primary",
                    "kind": "benchmark",
                    "procedure": procedure,
                    "pass_condition": pass_condition,
                }
            ],
            "references": [
                {
                    "id": "ref-benchmark",
                    "kind": "paper",
                    "locator": reference_locator,
                    "role": "benchmark",
                    "why_it_matters": reference_why,
                    "required_actions": ["read", "compare", "cite"],
                    "must_surface": True,
                    "applies_to": ["claim-primary"],
                }
            ],
            "forbidden_proxies": [
                {
                    "id": "fp-proxy",
                    "subject": "claim-primary",
                    "proxy": forbidden_proxy,
                    "reason": "Would allow reporting success without the decisive benchmark-backed observable.",
                }
            ],
            "uncertainty_markers": {
                "weakest_anchors": ["Benchmark comparability under the stated conventions"],
                "disconfirming_observations": ["Benchmark agreement fails once the decisive comparison is made explicit"],
            },
        }
    )


def test_bundle_registry_lists_curated_bundles() -> None:
    bundle_ids = {bundle.bundle_id for bundle in list_protocol_bundles()}
    assert {
        "stat-mech-simulation",
        "numerical-relativity",
        "lattice-gauge-monte-carlo",
        "tensor-network-dynamics",
        "cosmological-perturbation-cmb",
        "fluid-mhd-dynamics",
        "density-functional-electronic-structure",
    } <= bundle_ids


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
    assert "Fall back to shared protocols and on-demand routing." in rendered


def test_render_protocol_bundle_context_surfaces_guidance() -> None:
    selected = select_protocol_bundles(
        "Statistical mechanics Monte Carlo with autocorrelation and finite-size scaling benchmarks.",
        _stat_mech_contract(),
    )

    rendered = render_protocol_bundle_context(selected)

    assert "Statistical Mechanics Simulation [stat-mech-simulation]" in rendered
    assert "Usage contract: additive specialized guidance only." in rendered
    assert "Selection tags:" in rendered
    assert "Estimator policies:" in rendered
    assert "Verifier extensions:" in rendered
    assert "{GPD_INSTALL_DIR}/references/protocols/monte-carlo.md" in rendered


def test_select_protocol_bundles_lattice_gauge_excludes_stat_mech_when_both_match() -> None:
    project_text = _project_text(
        "Hybrid Monte Carlo lattice QCD study with Wilson fermion ensembles and finite-size scaling diagnostics.",
        "Gauge theory",
        "Scale setting, continuum extrapolation, autocorrelation, topology freezing, and benchmark comparisons are all required.",
    )
    contract = _bundle_contract(
        question="Does the lattice-QCD analysis recover benchmark observables after continuum extrapolation?",
        observable_name="Continuum-extrapolated hadron mass",
        observable_kind="scalar",
        observable_definition="Hadronic observable extracted from lattice correlators and extrapolated to the continuum limit",
        claim_statement="The lattice calculation reproduces benchmark hadronic behavior with controlled topology and continuum systematics.",
        dataset_path="results/lattice-ensembles.csv",
        figure_path="figures/lattice-continuum-fit.png",
        procedure="Compare continuum-extrapolated observables and topology diagnostics against trusted lattice benchmarks.",
        pass_condition="Continuum-fit result and topology diagnostics agree with benchmark expectations within uncertainty.",
        reference_locator="Trusted lattice-QCD benchmark ensemble and scale-setting paper",
        reference_why="Benchmark ensembles and reference scales anchor the lattice comparison.",
        forbidden_proxy="Pretty correlator plateaus without topology, scale-setting, or continuum checks",
    )

    selected = select_protocol_bundles(project_text, contract)

    assert [bundle.bundle_id for bundle in selected] == ["lattice-gauge-monte-carlo"]
    assert "lattice qcd" in selected[0].matched_terms


def test_select_protocol_bundles_matches_heading_derived_tags(tmp_path) -> None:
    bundles_dir = tmp_path / "bundles"
    bundles_dir.mkdir()
    (bundles_dir / "heading-tag-bundle.md").write_text(
        """---
bundle_id: heading-tag-bundle
bundle_version: 1
title: Heading Tag Bundle
summary: Test bundle for heading-derived project tags.
trigger:
  any_tags:
    - theoretical-framework:statistical-mechanics
  min_tag_matches: 1
  min_score: 4
---

# Heading Tag Bundle
""",
        encoding="utf-8",
    )

    try:
        selected = select_protocol_bundles(
            _project_text(
                "Monte Carlo study of a statistical mechanics model.",
                "Statistical mechanics",
                "Finite-size scaling is benchmarked.",
            ),
            None,
            bundles_dir=bundles_dir,
        )
    finally:
        invalidate_protocol_bundle_cache()

    assert [bundle.bundle_id for bundle in selected] == ["heading-tag-bundle"]
    assert selected[0].matched_tags == ["theoretical-framework:statistical-mechanics"]


@pytest.mark.parametrize(
    ("bundle_id", "project_text", "contract", "expected_asset", "expected_term"),
    [
        (
            "numerical-relativity",
            _project_text(
                "BSSN numerical relativity study of a binary black hole system with moving-puncture evolution.",
                "General relativity",
                "Track apparent horizon properties, constraint propagation, and gravitational waveform benchmarks.",
            ),
            _bundle_contract(
                question="What waveform and remnant properties does the BSSN evolution recover?",
                observable_name="Waveform phase difference",
                observable_kind="curve",
                observable_definition="Phase-aligned gravitational waveform comparison against trusted reference data",
                claim_statement="The evolution reproduces benchmark waveform structure with controlled constraint growth.",
                dataset_path="results/nr-constraints.csv",
                figure_path="figures/nr-waveform-comparison.png",
                procedure="Compare waveform phase, remnant properties, and constraint convergence against a trusted numerical-relativity benchmark.",
                pass_condition="Waveform and remnant metrics agree within the stated numerical uncertainty.",
                reference_locator="SXS-style numerical-relativity benchmark waveform catalog",
                reference_why="Benchmark waveform and remnant data anchor the strong-field result.",
                forbidden_proxy="Smooth-looking waveforms without converged constraints or benchmark agreement",
            ),
            "references/protocols/numerical-relativity.md",
            "bssn",
        ),
        (
            "lattice-gauge-monte-carlo",
            _project_text(
                "Hybrid Monte Carlo lattice QCD study with Wilson fermion ensembles and gradient-flow diagnostics.",
                "Gauge theory",
                "Scale setting, continuum extrapolation, and topology freezing checks are benchmarked against trusted ensembles.",
            ),
            _bundle_contract(
                question="Does the lattice-QCD analysis recover benchmark hadronic observables after continuum extrapolation?",
                observable_name="Continuum-extrapolated hadron mass",
                observable_kind="scalar",
                observable_definition="Hadronic observable extracted from lattice correlators and extrapolated to the continuum limit",
                claim_statement="The lattice calculation reproduces benchmark hadronic behavior with controlled topology and continuum systematics.",
                dataset_path="results/lattice-ensembles.csv",
                figure_path="figures/lattice-continuum-fit.png",
                procedure="Compare continuum-extrapolated observables and topology diagnostics against trusted lattice benchmarks.",
                pass_condition="Continuum-fit result and topology diagnostics agree with benchmark expectations within uncertainty.",
                reference_locator="Trusted lattice-QCD benchmark ensemble and scale-setting paper",
                reference_why="Benchmark ensembles and reference scales anchor the lattice comparison.",
                forbidden_proxy="Pretty correlator plateaus without topology, scale-setting, or continuum checks",
            ),
            "references/protocols/lattice-gauge-theory.md",
            "lattice qcd",
        ),
        (
            "tensor-network-dynamics",
            _project_text(
                "Tensor network quench study using MPS and TEBD with explicit bond-dimension growth control.",
                "Condensed matter",
                "Benchmark the entanglement growth window and compare observables against trusted DMRG or exact-diagonalization baselines.",
            ),
            _bundle_contract(
                question="How long does the tensor-network evolution remain reliable before entanglement saturation dominates?",
                observable_name="Post-quench magnetization",
                observable_kind="curve",
                observable_definition="Time-dependent many-body observable extracted from a tensor-network simulation",
                claim_statement="The tensor-network calculation captures benchmark dynamics within the declared reliable bond-dimension window.",
                dataset_path="results/tensor-network-time-series.csv",
                figure_path="figures/tensor-network-convergence.png",
                procedure="Compare bond-dimension convergence and benchmark observables against trusted tensor-network or ED references.",
                pass_condition="Decisive observables remain benchmark-consistent inside the declared reliable time window.",
                reference_locator="Published DMRG or exact-diagonalization benchmark for the same quench setup",
                reference_why="Benchmark data anchors the reliable finite-chi time window.",
                forbidden_proxy="Late-time traces shown after entanglement saturation without benchmarked validity window",
            ),
            "references/protocols/tensor-networks.md",
            "tebd",
        ),
        (
            "cosmological-perturbation-cmb",
            _project_text(
                "Cosmological perturbation calculation of the CMB power spectrum using CLASS transfer functions and Bardeen potentials.",
                "Cosmology",
                "Cross-check acoustic-peak structure, transfer functions, and Planck-normalized observables against code baselines.",
            ),
            _bundle_contract(
                question="Do the perturbation equations recover benchmark CMB and transfer-function behavior?",
                observable_name="CMB TT power spectrum",
                observable_kind="curve",
                observable_definition="Angular power spectrum computed from cosmological perturbation evolution",
                claim_statement="The cosmological perturbation pipeline reproduces benchmark CMB structure with consistent gauge and normalization choices.",
                dataset_path="results/cmb-spectrum.csv",
                figure_path="figures/cmb-class-comparison.png",
                procedure="Compare transfer functions and CMB spectra against CLASS or CAMB benchmark outputs and analytic limits.",
                pass_condition="Benchmark CMB observables and analytic limits agree within the stated tolerance.",
                reference_locator="Planck and CLASS benchmark cosmology reference",
                reference_why="Benchmark spectra and conventions anchor the cosmological comparison.",
                forbidden_proxy="Background-only agreement without transfer-function or CMB benchmark parity",
            ),
            "references/protocols/cosmological-perturbation-theory.md",
            "class",
        ),
        (
            "fluid-mhd-dynamics",
            _project_text(
                "Magnetohydrodynamics simulation of Alfven-wave propagation and turbulence spectra with explicit div B control.",
                "Fluid dynamics",
                "Reynolds-number, Lundquist-number, and CFL-sensitive behavior is benchmarked against analytic and literature expectations.",
            ),
            _bundle_contract(
                question="Does the fluid or MHD simulation reproduce benchmark wave speeds and turbulence behavior in the intended regime?",
                observable_name="Alfven-wave phase speed",
                observable_kind="scalar",
                observable_definition="Measured phase speed or growth rate from the simulated fluid or MHD system",
                claim_statement="The simulation reproduces benchmark wave or instability behavior in the declared flow regime.",
                dataset_path="results/fluid-benchmarks.csv",
                figure_path="figures/fluid-spectrum-comparison.png",
                procedure="Compare wave speeds, conservation diagnostics, and turbulence spectra against analytic or literature benchmarks.",
                pass_condition="Decisive fluid or MHD observables agree with regime-appropriate benchmark expectations.",
                reference_locator="Trusted CFD or MHD benchmark reference for the chosen setup",
                reference_why="Benchmark flow behavior anchors regime-specific validation.",
                forbidden_proxy="Visually plausible flow fields without regime checks, conservation diagnostics, or benchmark comparisons",
            ),
            "references/protocols/fluid-dynamics-mhd.md",
            "alfven wave",
        ),
        (
            "density-functional-electronic-structure",
            _project_text(
                "Density functional theory calculation of electronic structure with Kohn-Sham states, pseudopotentials, and k-point mesh convergence.",
                "Condensed matter",
                "Benchmark band-gap and structural observables while tracking exchange-correlation and plane-wave cutoff choices.",
            ),
            _bundle_contract(
                question="Does the DFT workflow recover benchmark electronic-structure observables with converged numerical settings?",
                observable_name="Band gap",
                observable_kind="scalar",
                observable_definition="Electronic-structure observable extracted from a DFT or DFT+U calculation",
                claim_statement="The electronic-structure workflow reproduces benchmark observables with explicit functional and convergence discipline.",
                dataset_path="results/dft-convergence.csv",
                figure_path="figures/dft-benchmark-comparison.png",
                procedure="Compare converged observables against experiment or trusted higher-level references while reporting functional sensitivity.",
                pass_condition="Benchmark observables agree within the stated uncertainty after convergence and functional-family checks.",
                reference_locator="Electronic-structure benchmark paper or trusted experimental reference",
                reference_why="Benchmark observables anchor the DFT comparison and expose proxy-versus-direct gaps.",
                forbidden_proxy="Single-shot Kohn-Sham output treated as final without convergence or benchmark comparison",
            ),
            "references/protocols/density-functional-theory.md",
            "kohn sham",
        ),
    ],
)
def test_select_protocol_bundles_identifies_curated_bundle(
    bundle_id: str,
    project_text: str,
    contract: ResearchContract,
    expected_asset: str,
    expected_term: str,
) -> None:
    selected = select_protocol_bundles(project_text, contract)

    assert [bundle.bundle_id for bundle in selected] == [bundle_id]
    assert expected_asset in selected[0].asset_paths
    assert expected_term in selected[0].matched_terms


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


def test_mismatched_project_metadata_keeps_bundle_context_in_generic_fallback_mode() -> None:
    selected = select_protocol_bundles(
        """
        # Test Project

        ## What This Is
        Quantum-gravity saddle bookkeeping with Page-curve comparisons and holographic entropy arguments.
        """,
        _benchmark_only_contract(),
    )

    assert selected == []
    rendered = render_protocol_bundle_context(selected)
    assert "Usage contract: additive specialized guidance only." in rendered
    assert "None selected from project metadata" in rendered
    assert "Fall back to shared protocols and on-demand routing." in rendered
