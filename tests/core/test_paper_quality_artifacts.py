from __future__ import annotations

import json
from pathlib import Path

import pytest

from gpd.core.errors import GPDError
from gpd.core.paper_quality import score_paper_quality
from gpd.core.paper_quality_artifacts import build_paper_quality_input

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "stage4"
STAGE0_FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "stage0"


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _full_convention_lock() -> dict[str, str]:
    return {
        "metric_signature": "mostly-plus",
        "fourier_convention": "physics",
        "natural_units": "natural",
        "gauge_choice": "Lorenz",
        "regularization_scheme": "dim-reg",
        "renormalization_scheme": "MS-bar",
        "coordinate_system": "spherical",
        "spin_basis": "helicity",
        "state_normalization": "relativistic",
        "coupling_convention": "alpha",
        "index_positioning": "NW-SE",
        "time_ordering": "T-product",
        "commutation_convention": "canonical",
        "levi_civita_sign": "+1",
        "generator_normalization": "standard",
        "covariant_derivative_sign": "+",
        "gamma_matrix_convention": "Dirac",
        "creation_annihilation_order": "normal",
    }


def _paper_config_payload(title: str, journal: str, *, output_filename: str | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "title": title,
        "authors": [{"name": "A. Researcher"}],
        "abstract": f"{title} abstract.",
        "sections": [{"heading": "Introduction", "content": "Intro."}],
        "journal": journal,
    }
    if output_filename is not None:
        payload["output_filename"] = output_filename
    return payload


def _project_local_benchmark_plan_contract() -> str:
    return """---
phase: 01-benchmark
plan: 01
type: execute
wave: 1
depends_on: []
files_modified: []
interactive: false
contract:
  schema_version: 1
  scope:
    question: What benchmark must this plan recover?
  context_intake:
    must_read_refs: [ref-benchmark]
    must_include_prior_outputs: [GPD/phases/00-baseline/00-01-SUMMARY.md]
  claims:
    - id: claim-benchmark
      statement: Recover the benchmark comparison
      deliverables: [deliv-figure]
      acceptance_tests: [test-benchmark]
      references: [ref-benchmark]
  deliverables:
    - id: deliv-figure
      kind: figure
      path: figures/benchmark.png
      description: Benchmark figure
  references:
    - id: ref-benchmark
      kind: prior_artifact
      locator: artifacts/benchmark/report.json
      role: benchmark
      why_it_matters: Project-local benchmark artifact
      applies_to: [claim-benchmark]
      must_surface: true
      required_actions: [read, compare, cite]
  acceptance_tests:
    - id: test-benchmark
      subject: claim-benchmark
      kind: benchmark
      procedure: Compare against the benchmark artifact
      pass_condition: Matches reference within tolerance
      evidence_required: [deliv-figure, ref-benchmark]
  forbidden_proxies:
    - id: fp-benchmark
      subject: claim-benchmark
      proxy: qualitative trend agreement without the benchmark artifact
      reason: Would miss the decisive local anchor
  uncertainty_markers:
    weakest_anchors: [Reference tolerance interpretation]
    disconfirming_observations: [Benchmark agreement disappears after normalization fix]
---

Body.
"""


def test_build_paper_quality_input_reads_contract_and_comparison_artifacts(tmp_path: Path) -> None:
    _write(
        tmp_path / "paper" / "benchmark_paper.tex",
        r"""
\documentclass{article}
\begin{document}
\begin{abstract}
Benchmark result with explicit comparison.
\end{abstract}
\section{Introduction}
See Fig.~\ref{fig:benchmark} and \cite{bench2026}.
\section{Conclusion}
The benchmark was recovered within tolerance.
\end{document}
""".strip()
        + "\n",
    )
    _write(
        tmp_path / "paper" / "ARTIFACT-MANIFEST.json",
        json.dumps(
            {
                "version": 1,
                "paper_title": "Benchmark Paper",
                "journal": "jhep",
                "created_at": "2026-03-13T00:00:00+00:00",
                "artifacts": [
                    {
                        "artifact_id": "tex-paper",
                        "category": "tex",
                        "path": "benchmark_paper.tex",
                        "sha256": "0" * 64,
                        "produced_by": "test",
                        "sources": [],
                        "metadata": {},
                    }
                ],
            }
        ),
    )
    _write(
        tmp_path / "paper" / "BIBLIOGRAPHY-AUDIT.json",
        json.dumps(
            {
                "generated_at": "2026-03-13T00:00:00+00:00",
                "total_sources": 1,
                "resolved_sources": 1,
                "partial_sources": 0,
                "unverified_sources": 0,
                "failed_sources": 0,
                "entries": [
                    {
                        "key": "bench2026",
                        "source_type": "paper",
                        "title": "Benchmark",
                        "resolution_status": "provided",
                        "verification_status": "verified",
                    }
                ],
            }
        ),
    )
    _write(
        tmp_path / "paper" / "PAPER-CONFIG.json",
        json.dumps(_paper_config_payload("Benchmark Paper", "jhep")),
    )
    _write(
        tmp_path / "paper" / "FIGURE_TRACKER.md",
        """---
figure_registry:
  - id: fig-benchmark
    label: "Fig. 1"
    kind: figure
    role: benchmark
    path: paper/figures/benchmark.pdf
    contract_ids: [claim-benchmark, deliv-figure]
    decisive: true
    has_units: true
    has_uncertainty: true
    referenced_in_text: true
    caption_self_contained: true
    colorblind_safe: true
    comparison_sources:
      - GPD/comparisons/benchmark-COMPARISON.md
---

# Figure Tracker
""",
    )
    _write(
        tmp_path / "GPD" / "comparisons" / "benchmark-COMPARISON.md",
        """---
comparison_kind: benchmark
comparison_sources:
  - label: theory
    kind: summary
    path: GPD/phases/01-benchmark/01-SUMMARY.md
  - label: benchmark
    kind: verification
    path: GPD/phases/01-benchmark/01-VERIFICATION.md
protocol_bundle_ids:
  - stat-mech-simulation
bundle_expectations:
  - Keep benchmark comparison visible in the manuscript main text
comparison_verdicts:
  - subject_id: claim-benchmark
    subject_kind: claim
    subject_role: decisive
    reference_id: ref-benchmark
    comparison_kind: benchmark
    metric: relative_error
    threshold: "<= 0.01"
    verdict: pass
    recommended_action: Keep benchmark figure in manuscript
---

# Internal Comparison
""",
    )
    _write(
        tmp_path / "GPD" / "phases" / "01-benchmark" / "01-01-PLAN.md",
        (STAGE0_FIXTURES_DIR / "plan_with_contract.md").read_text(encoding="utf-8"),
    )
    _write(
        tmp_path / "GPD" / "phases" / "01-benchmark" / "01-SUMMARY.md",
        (FIXTURES_DIR / "summary_with_contract_results.md").read_text(encoding="utf-8"),
    )
    _write(
        tmp_path / "GPD" / "phases" / "01-benchmark" / "01-VERIFICATION.md",
        (FIXTURES_DIR / "verification_with_contract_results.md").read_text(encoding="utf-8"),
    )

    result = build_paper_quality_input(tmp_path)

    assert result.title == "Benchmark Paper"
    assert result.journal == "jhep"
    assert result.completeness.required_sections_present.satisfied == 3
    assert result.citations.missing_placeholders.passed is True
    assert result.citations.citation_keys_resolve.satisfied == 1
    assert result.verification.report_passed.passed is True
    assert result.verification.contract_targets_verified.satisfied == 3
    assert result.verification.contract_targets_verified.total == 3
    assert result.figures.decisive_artifact_roles_clear.satisfied == 1
    assert result.results.decisive_artifacts_with_explicit_verdicts.satisfied == 1
    assert result.results.decisive_artifacts_benchmark_anchored.satisfied == 1


def test_build_paper_quality_input_preserves_project_local_contract_anchors_through_verified_ledgers(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / "paper" / "benchmark_paper.tex",
        r"""
\documentclass{article}
\begin{document}
\begin{abstract}
Benchmark result with explicit comparison.
\end{abstract}
\section{Introduction}
See Fig.~\ref{fig:benchmark} and \cite{bench2026}.
\section{Conclusion}
The benchmark was recovered within tolerance.
\end{document}
""".strip()
        + "\n",
    )
    _write(
        tmp_path / "paper" / "PAPER-CONFIG.json",
        json.dumps(_paper_config_payload("Benchmark Paper", "jhep")),
    )
    _write(tmp_path / "artifacts" / "benchmark" / "report.json", "{}\n")
    _write(tmp_path / "GPD" / "phases" / "00-baseline" / "00-01-SUMMARY.md", "baseline summary\n")
    _write(
        tmp_path / "GPD" / "phases" / "01-benchmark" / "01-01-PLAN.md",
        _project_local_benchmark_plan_contract(),
    )
    _write(
        tmp_path / "GPD" / "phases" / "01-benchmark" / "01-SUMMARY.md",
        (FIXTURES_DIR / "summary_with_contract_results.md").read_text(encoding="utf-8"),
    )
    _write(
        tmp_path / "GPD" / "phases" / "01-benchmark" / "01-VERIFICATION.md",
        (FIXTURES_DIR / "verification_with_contract_results.md").read_text(encoding="utf-8"),
    )

    result = build_paper_quality_input(tmp_path)

    assert result.verification.contract_targets_verified.satisfied == 3
    assert result.verification.contract_targets_verified.total == 3
    assert result.verification.report_passed.passed is True


def test_build_paper_quality_input_marks_uninferred_checks_not_applicable(tmp_path: Path) -> None:
    _write(
        tmp_path / "paper" / "minimal.tex",
        r"""
\documentclass{article}
\begin{document}
\begin{abstract}
Minimal abstract.
\end{abstract}
\section{Introduction}
Intro.
\section{Conclusion}
Done.
\end{document}
""".strip()
        + "\n",
    )
    _write(
        tmp_path / "paper" / "PAPER-CONFIG.json",
        json.dumps(_paper_config_payload("Minimal Paper", "jhep")),
    )

    result = build_paper_quality_input(tmp_path)

    assert result.conventions.notation_consistent.not_applicable is True
    assert result.completeness.abstract_written_last.not_applicable is True
    assert result.results.physical_interpretation_present.not_applicable is True


def test_build_paper_quality_input_counts_project_local_plan_contract_targets(tmp_path: Path) -> None:
    _write(
        tmp_path / "paper" / "minimal.tex",
        r"""
\documentclass{article}
\begin{document}
\begin{abstract}
Minimal abstract.
\end{abstract}
\section{Introduction}
Intro.
\section{Conclusion}
Done.
\end{document}
""".strip()
        + "\n",
    )
    _write(
        tmp_path / "paper" / "PAPER-CONFIG.json",
        json.dumps(_paper_config_payload("Minimal Paper", "jhep")),
    )
    _write(tmp_path / "artifacts" / "benchmark" / "report.json", "{}\n")
    _write(tmp_path / "GPD" / "phases" / "00-baseline" / "00-01-SUMMARY.md", "baseline summary\n")
    _write(
        tmp_path / "GPD" / "phases" / "01-benchmark" / "01-01-PLAN.md",
        _project_local_benchmark_plan_contract(),
    )

    result = build_paper_quality_input(tmp_path)

    assert result.verification.contract_targets_verified.total == 3
    assert result.verification.contract_targets_verified.satisfied == 0


def test_build_paper_quality_input_recurses_into_nested_manuscript_files(tmp_path: Path) -> None:
    _write(
        tmp_path / "paper" / "topic_specific_stem.tex",
        r"""
\documentclass{article}
\begin{document}
\section{Introduction}
Root introduction only.
\end{document}
""".strip()
        + "\n",
    )
    _write(
        tmp_path / "paper" / "sections" / "analysis.tex",
        r"""
\begin{abstract}
Nested abstract with \cite{bench2026}.
\end{abstract}
\section{Abstract}
Nested methods body.
\section{Methods}
Nested methods body.
""".strip()
        + "\n",
    )
    _write(
        tmp_path / "paper" / "appendix" / "conclusion.md",
        """# Conclusion

TODO finalize the nested conclusion.
""",
    )
    _write(
        tmp_path / "paper" / "ARTIFACT-MANIFEST.json",
        json.dumps(
            {
                "version": 1,
                "paper_title": "Recursive Manuscript",
                "journal": "generic",
                "created_at": "2026-04-02T00:00:00+00:00",
                "artifacts": [
                    {
                        "artifact_id": "tex-paper",
                        "category": "tex",
                        "path": "topic_specific_stem.tex",
                        "sha256": "0" * 64,
                        "produced_by": "test",
                        "sources": [],
                        "metadata": {},
                    }
                ],
            }
        ),
    )
    _write(
        tmp_path / "paper" / "BIBLIOGRAPHY-AUDIT.json",
        json.dumps(
            {
                "generated_at": "2026-04-02T00:00:00+00:00",
                "total_sources": 1,
                "resolved_sources": 1,
                "partial_sources": 0,
                "unverified_sources": 0,
                "failed_sources": 0,
                "entries": [
                    {
                        "key": "bench2026",
                        "source_type": "paper",
                        "title": "Benchmark",
                        "resolution_status": "provided",
                        "verification_status": "verified",
                    }
                ],
            }
        ),
    )
    _write(
        tmp_path / "paper" / "PAPER-CONFIG.json",
        json.dumps(_paper_config_payload("Recursive Manuscript", "jhep", output_filename="topic_specific_stem")),
    )

    result = build_paper_quality_input(tmp_path)

    assert result.completeness.required_sections_present.satisfied == 3
    assert result.citations.citation_keys_resolve.satisfied == 1
    assert result.citations.citation_keys_resolve.total == 1
    assert result.citations.missing_placeholders.passed is True
    assert result.completeness.placeholders_cleared.passed is False


def test_build_paper_quality_input_falls_back_to_supported_config_journal_when_manifest_is_unsupported(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / "paper" / "config_fallback_title.tex",
        "\\documentclass{article}\\begin{document}\\begin{abstract}Fallback test.\\end{abstract}\\section{Introduction}Intro.\\section{Conclusion}Done.\\end{document}\n",
    )
    _write(
        tmp_path / "paper" / "PAPER-CONFIG.json",
        json.dumps(_paper_config_payload("Config Fallback Title", "jhep")),
    )
    _write(
        tmp_path / "paper" / "ARTIFACT-MANIFEST.json",
        json.dumps(
            {
                "version": 1,
                "paper_title": "Manifest Title",
                "journal": "prd",
                "created_at": "2026-03-13T00:00:00+00:00",
                "artifacts": [],
            }
        ),
    )

    result = build_paper_quality_input(tmp_path)

    assert result.title == "Config Fallback Title"
    assert result.journal == "jhep"


def test_build_paper_quality_input_normalizes_empty_contract_results_reference_lists(tmp_path: Path) -> None:
    plan_dir = tmp_path / "GPD" / "phases" / "01-benchmark"
    _write(
        plan_dir / "01-01-PLAN.md",
        (STAGE0_FIXTURES_DIR / "plan_with_contract.md")
        .read_text(encoding="utf-8")
        .replace("    must_read_refs: [ref-benchmark]\n", "    must_read_refs: []\n", 1)
        .replace("      references: [ref-benchmark]\n", "      references: []\n", 1)
        .replace(
            """  references:
    - id: ref-benchmark
      kind: paper
      locator: Author et al., Journal, 2024
      role: benchmark
      why_it_matters: Published comparison target
      applies_to: [claim-benchmark]
      must_surface: true
      required_actions: [read, compare, cite]
""",
            "  references: []\n",
            1,
        )
        .replace("      kind: benchmark\n", "      kind: consistency\n", 1)
        .replace(
            "      procedure: Compare against the benchmark reference\n",
            "      procedure: Compare against the internal baseline calculation\n",
            1,
        )
        .replace(
            "      pass_condition: Matches reference within tolerance\n",
            "      pass_condition: Matches internal baseline within tolerance\n",
            1,
        )
        .replace("      evidence_required: [deliv-figure, ref-benchmark]\n", "      evidence_required: [deliv-figure]\n", 1),
    )
    _write(
        plan_dir / "01-SUMMARY.md",
        """---
phase: 01-benchmark
plan: 01
depth: full
provides: [benchmark comparison]
completed: 2026-03-15
plan_contract_ref: GPD/phases/01-benchmark/01-01-PLAN.md#/contract
contract_results:
  claims:
    claim-benchmark:
      status: passed
      summary: Benchmark reproduced within tolerance.
      linked_ids: [deliv-figure, test-benchmark]
      evidence:
        - verifier: gpd-verifier
          method: internal baseline comparison
          confidence: high
          claim_id: claim-benchmark
          deliverable_id: deliv-figure
          acceptance_test_id: test-benchmark
          evidence_path: GPD/phases/01-benchmark/01-VERIFICATION.md
  deliverables:
    deliv-figure:
      status: passed
      path: figures/benchmark.png
      summary: Figure produced with uncertainty band and benchmark overlay.
      linked_ids: [claim-benchmark, test-benchmark]
      evidence:
        - verifier: gpd-verifier
          method: internal baseline comparison
          confidence: high
          claim_id: claim-benchmark
          deliverable_id: deliv-figure
          acceptance_test_id: test-benchmark
          evidence_path: GPD/phases/01-benchmark/01-VERIFICATION.md
  acceptance_tests:
    test-benchmark:
      status: passed
      summary: Internal baseline reproduced within the contracted tolerance.
      linked_ids: [claim-benchmark, deliv-figure]
      evidence:
        - verifier: gpd-verifier
          method: internal baseline comparison
          confidence: high
          claim_id: claim-benchmark
          deliverable_id: deliv-figure
          acceptance_test_id: test-benchmark
          evidence_path: GPD/phases/01-benchmark/01-VERIFICATION.md
  references: []
  forbidden_proxies:
    fp-benchmark:
      status: rejected
      notes: Qualitative trend agreement was not accepted without the numerical benchmark check.
  uncertainty_markers:
    weakest_anchors: [Reference tolerance interpretation]
    disconfirming_observations: [Benchmark agreement disappears once normalization is fixed]
---

# Summary
""",
    )

    result = build_paper_quality_input(tmp_path)

    assert result.verification.contract_targets_verified.satisfied == 0
    assert result.verification.contract_targets_verified.total == 3
    assert result.verification.key_result_confidences == []


def test_build_paper_quality_input_is_conservative_when_artifacts_are_missing(tmp_path: Path) -> None:
    _write(
        tmp_path / "paper" / "curvature_flow_bounds.tex",
        "\\documentclass{article}\\begin{document}\\section{Introduction}Only intro.\\end{document}\n",
    )

    result = build_paper_quality_input(tmp_path)

    assert result.journal == "generic"
    assert result.verification.report_passed.passed is False
    assert result.verification.contract_targets_verified.not_applicable is True
    assert result.conventions.assert_convention_coverage.not_applicable is True
    assert result.results.decisive_artifacts_with_explicit_verdicts.not_applicable is True
    assert result.completeness.required_sections_present.satisfied == 1

    report = score_paper_quality(result)
    assert report.categories["verification"].checks["contract_targets_verified"] == 5.0


def test_build_paper_quality_input_does_not_fall_back_to_paper_root_when_manuscript_resolution_is_ambiguous(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / "paper" / "curvature_flow_bounds.tex",
        "\\documentclass{article}\\begin{document}Paper root.\\end{document}\n",
    )
    _write(
        tmp_path / "paper" / "PAPER-CONFIG.json",
        json.dumps(
            {
                "title": "Paper Root Title",
                "output_filename": "curvature_flow_bounds",
                "authors": [{"name": "A. Researcher"}],
                "abstract": "Abstract.",
                "sections": [{"heading": "Intro", "content": "Hello."}],
            }
        ),
    )
    _write(
        tmp_path / "manuscript" / "curvature_flow_bounds.tex",
        "\\documentclass{article}\\begin{document}Manuscript root.\\end{document}\n",
    )
    _write(
        tmp_path / "manuscript" / "PAPER-CONFIG.json",
        json.dumps(
            {
                "title": "Manuscript Root Title",
                "output_filename": "curvature_flow_bounds",
                "authors": [{"name": "B. Researcher"}],
                "abstract": "Abstract.",
                "sections": [{"heading": "Intro", "content": "Hello."}],
            }
        ),
    )

    with pytest.raises(GPDError, match="paper-quality artifact resolution requires an unambiguous manuscript root"):
        build_paper_quality_input(tmp_path)


def test_build_paper_quality_input_prefers_valid_config_when_manifest_is_invalid(
    tmp_path: Path,
) -> None:
    _write(tmp_path / "paper" / "config-entry.tex", "\\documentclass{article}\\begin{document}Config.\\end{document}\n")
    _write(
        tmp_path / "paper" / "manifest-entry.tex",
        "\\documentclass{article}\\begin{document}Manifest.\\end{document}\n",
    )
    _write(
        tmp_path / "paper" / "PAPER-CONFIG.json",
        json.dumps(
            {
                "title": "Config Title",
                "output_filename": "config-entry",
                "authors": [{"name": "A. Researcher"}],
                "abstract": "Abstract.",
                "sections": [{"heading": "Intro", "content": "Hello."}],
            }
        ),
    )
    _write(
        tmp_path / "paper" / "ARTIFACT-MANIFEST.json",
        json.dumps(
            {
                "version": 1,
                "paper_title": "Paper Root Title",
                "journal": "prd",
                "created_at": "2026-03-13T00:00:00+00:00",
                "artifacts": [
                    {
                        "artifact_id": "main-tex",
                        "category": "tex",
                        "path": "manifest-entry.tex",
                        "sha256": "a" * 64,
                        "produced_by": "paper-compiler",
                        "sources": [],
                        "metadata": {},
                    }
                ],
            }
            ),
        )

    result = build_paper_quality_input(tmp_path)

    assert result.title == "Config Title"


def test_build_paper_quality_input_ignores_stale_manifest_metadata_when_config_entrypoint_is_active(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / "paper" / "config-entry.tex",
        "\\documentclass{article}\\begin{document}\\begin{abstract}A.\\end{abstract}\\section{Introduction}Intro.\\section{Conclusion}Done.\\end{document}\n",
    )
    _write(
        tmp_path / "paper" / "PAPER-CONFIG.json",
        json.dumps(_paper_config_payload("Config Title", "jhep") | {"output_filename": "config-entry"}),
    )
    _write(
        tmp_path / "paper" / "ARTIFACT-MANIFEST.json",
        json.dumps(
            {
                "version": 1,
                "paper_title": "Stale Manifest Title",
                "journal": "prd",
                "created_at": "2026-03-13T00:00:00+00:00",
                "artifacts": [
                    {
                        "artifact_id": "main-tex",
                        "category": "tex",
                        "path": "missing-entry.tex",
                        "sha256": "b" * 64,
                        "produced_by": "paper-compiler",
                        "sources": [],
                        "metadata": {},
                    }
                ],
            }
        ),
    )

    result = build_paper_quality_input(tmp_path)

    assert result.title == "Config Title"
    assert result.journal == "jhep"


def test_build_paper_quality_input_surfaces_convention_lock_and_derivation_assertion_coverage(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / "paper" / "curvature_flow_bounds.tex",
        "\\documentclass{article}\\begin{document}\\section{Introduction}Intro.\\section{Conclusion}Done.\\end{document}\n",
    )
    _write(
        tmp_path / "GPD" / "state.json",
        json.dumps({"convention_lock": _full_convention_lock()}, indent=2),
    )
    _write(
        tmp_path / "GPD" / "analysis" / "derivation-dispersion.md",
        "<!-- ASSERT_CONVENTION: metric_signature=mostly-plus, fourier_convention=physics -->\n\n# Derivation\n",
    )
    _write(
        tmp_path / "GPD" / "phases" / "01-benchmark" / "derivation-threshold.md",
        "<!-- ASSERT_CONVENTION: metric_signature=mostly-plus, fourier_convention=physics -->\n\n# Derivation\n",
    )

    result = build_paper_quality_input(tmp_path)

    assert result.conventions.convention_lock_complete.passed is True
    assert result.conventions.assert_convention_coverage.satisfied == 2
    assert result.conventions.assert_convention_coverage.total == 2


def test_build_paper_quality_input_counts_only_matching_derivation_assertions(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / "paper" / "curvature_flow_bounds.tex",
        "\\documentclass{article}\\begin{document}\\section{Introduction}Intro.\\section{Conclusion}Done.\\end{document}\n",
    )
    _write(
        tmp_path / "GPD" / "state.json",
        json.dumps({"convention_lock": _full_convention_lock()}, indent=2),
    )
    _write(
        tmp_path / "GPD" / "analysis" / "derivation-valid.md",
        "<!-- ASSERT_CONVENTION: metric_signature=mostly-plus, fourier_convention=physics -->\n\n# Derivation\n",
    )
    _write(
        tmp_path / "GPD" / "analysis" / "derivation-mismatch.md",
        "<!-- ASSERT_CONVENTION: metric_signature=mostly-minus, fourier_convention=physics -->\n\n# Derivation\n",
    )
    _write(
        tmp_path / "GPD" / "phases" / "01-benchmark" / "derivation-missing.md",
        "# Derivation\n",
    )

    result = build_paper_quality_input(tmp_path)

    assert result.conventions.convention_lock_complete.passed is True
    assert result.conventions.assert_convention_coverage.satisfied == 1
    assert result.conventions.assert_convention_coverage.total == 3


def test_build_paper_quality_input_counts_python_and_tex_derivation_artifacts(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / "paper" / "curvature_flow_bounds.tex",
        "\\documentclass{article}\\begin{document}\\section{Introduction}Intro.\\section{Conclusion}Done.\\end{document}\n",
    )
    _write(
        tmp_path / "GPD" / "state.json",
        json.dumps({"convention_lock": _full_convention_lock()}, indent=2),
    )
    _write(
        tmp_path / "GPD" / "analysis" / "derivation-shell.py",
        "# ASSERT_CONVENTION: metric_signature=mostly-plus, fourier_convention=physics\n\nprint('ok')\n",
    )
    _write(
        tmp_path / "GPD" / "analysis" / "derivation-notes.tex",
        "% ASSERT_CONVENTION: metric_signature=mostly-plus, fourier_convention=physics\n\n\\section{Derivation}\n",
    )
    _write(
        tmp_path / "GPD" / "analysis" / "derivation-outline.md",
        "<!-- ASSERT_CONVENTION: metric_signature=mostly-plus, fourier_convention=physics -->\n\n# Derivation\n",
    )

    result = build_paper_quality_input(tmp_path)

    assert result.conventions.convention_lock_complete.passed is True
    assert result.conventions.assert_convention_coverage.satisfied == 3
    assert result.conventions.assert_convention_coverage.total == 3


def test_build_paper_quality_input_ignores_invalid_artifact_manifest_and_falls_back_to_config(tmp_path: Path) -> None:
    _write(
        tmp_path / "paper" / "curvature_flow_bounds.tex",
        "\\documentclass{article}\\begin{document}\\section{Introduction}Intro.\\section{Conclusion}Done.\\end{document}\n",
    )
    _write(
        tmp_path / "paper" / "PAPER-CONFIG.json",
        json.dumps({"title": "Config Fallback Title", "journal": "jhep"}),
    )
    _write(
        tmp_path / "paper" / "ARTIFACT-MANIFEST.json",
        json.dumps(
            {
                "version": 2,
                "paper_title": "Broken Manifest Title",
                "journal": "prd",
                "created_at": "2026-03-13T00:00:00+00:00",
                "artifacts": [],
            }
        ),
    )

    result = build_paper_quality_input(tmp_path)

    assert result.title == "Config Fallback Title"
    assert result.journal == "jhep"


def test_build_paper_quality_input_ignores_invalid_bibliography_audit(tmp_path: Path) -> None:
    _write(
        tmp_path / "paper" / "curvature_flow_bounds.tex",
        r"""
\documentclass{article}
\begin{document}
\section{Introduction}
See \cite{bench2026}.
\section{Conclusion}
Done.
\end{document}
""".strip()
        + "\n",
    )
    _write(
        tmp_path / "paper" / "refs.bib",
        "@article{bench2026,\n  title={Benchmark},\n  author={Doe, Jane},\n  year={2026}\n}\n",
    )
    _write(
        tmp_path / "paper" / "BIBLIOGRAPHY-AUDIT.json",
        json.dumps(
            {
                "generated_at": "2026-03-13T00:00:00+00:00",
                "total_sources": "one",
                "resolved_sources": 1,
                "partial_sources": 0,
                "unverified_sources": 0,
                "failed_sources": 0,
                "entries": "not-a-list",
            }
        ),
    )

    result = build_paper_quality_input(tmp_path)

    assert result.citations.citation_keys_resolve.satisfied == 1
    assert result.citations.citation_keys_resolve.total == 1
    assert result.citations.hallucination_free.passed is False
    assert result.citations.hallucination_free.not_applicable is False


def test_build_paper_quality_input_marks_missing_bibliography_audit_applicable_when_citations_are_present(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / "paper" / "citation_audit_required.tex",
        r"""
\documentclass{article}
\begin{document}
\section{Introduction}
See \cite{bench2026}.
\section{Conclusion}
Done.
\end{document}
""".strip()
        + "\n",
    )
    _write(
        tmp_path / "paper" / "refs.bib",
        "@article{bench2026,\n  title={Benchmark},\n  author={Doe, Jane},\n  year={2026}\n}\n",
    )

    result = build_paper_quality_input(tmp_path)

    assert result.citations.citation_keys_resolve.satisfied == 1
    assert result.citations.citation_keys_resolve.total == 1
    assert result.citations.hallucination_free.passed is False
    assert result.citations.hallucination_free.not_applicable is False


def test_build_paper_quality_input_requires_decisive_verdicts_for_decisive_artifact_coverage(tmp_path: Path) -> None:
    _write(
        tmp_path / "paper" / "FIGURE_TRACKER.md",
        """---
figure_registry:
  - id: fig-benchmark
    label: "Fig. 1"
    kind: figure
    role: benchmark
    path: paper/figures/benchmark.pdf
    contract_ids: [claim-benchmark, deliv-figure]
    decisive: true
    has_units: true
    has_uncertainty: true
    referenced_in_text: true
    caption_self_contained: true
    colorblind_safe: true
    comparison_sources:
      - GPD/comparisons/benchmark-COMPARISON.md
---

# Figure Tracker
""",
    )
    _write(
        tmp_path / "GPD" / "comparisons" / "benchmark-COMPARISON.md",
        """---
comparison_kind: benchmark
comparison_verdicts:
  - subject_id: claim-benchmark
    subject_kind: claim
    subject_role: supporting
    reference_id: ref-benchmark
    comparison_kind: benchmark
    metric: relative_error
    threshold: "<= 0.01"
    verdict: pass
---

# Internal Comparison
""",
    )
    _write(
        tmp_path / "GPD" / "phases" / "01-benchmark" / "01-01-PLAN.md",
        (STAGE0_FIXTURES_DIR / "plan_with_contract.md").read_text(encoding="utf-8"),
    )

    result = build_paper_quality_input(tmp_path)

    assert result.results.decisive_artifacts_with_explicit_verdicts.satisfied == 0
    assert result.results.decisive_artifacts_with_explicit_verdicts.total == 1
    assert result.results.decisive_artifacts_benchmark_anchored.satisfied == 0
    assert result.results.decisive_artifacts_benchmark_anchored.total == 1


def test_build_paper_quality_input_blocks_required_decisive_comparison_without_figure_inventory(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / "paper" / "comparison_only.tex",
        r"""
\documentclass{article}
\begin{document}
\begin{abstract}
Comparison inventory test.
\end{abstract}
\section{Introduction}
Intro.
\section{Conclusion}
Done.
\end{document}
""".strip()
        + "\n",
    )
    _write(
        tmp_path / "paper" / "PAPER-CONFIG.json",
        json.dumps(_paper_config_payload("Comparison Only", "jhep")),
    )
    _write(
        tmp_path / "GPD" / "phases" / "01-benchmark" / "01-01-PLAN.md",
        (STAGE0_FIXTURES_DIR / "plan_with_contract.md").read_text(encoding="utf-8"),
    )

    result = build_paper_quality_input(tmp_path)

    assert result.results.comparison_with_prior_work_present.passed is False
    assert result.results.comparison_with_prior_work_present.not_applicable is False
    assert result.results.decisive_artifacts_with_explicit_verdicts.not_applicable is False
    assert result.results.decisive_artifacts_with_explicit_verdicts.total == 0
    assert result.results.decisive_artifacts_benchmark_anchored.not_applicable is False
    assert result.results.decisive_artifacts_benchmark_anchored.total == 0
    assert result.results.decisive_comparison_failures_scoped.not_applicable is False
    assert result.figures.decisive_artifacts_labeled_with_units.not_applicable is False
    assert result.figures.decisive_artifacts_uncertainty_qualified.not_applicable is False
    assert result.figures.decisive_artifacts_referenced_in_text.not_applicable is False
    assert result.figures.decisive_artifact_roles_clear.not_applicable is False


def test_build_paper_quality_input_reads_manuscript_dir_and_config_title(tmp_path: Path) -> None:
    _write(
        tmp_path / "manuscript" / "config_title.tex",
        r"""
\documentclass{article}
\begin{document}
\begin{abstract}
Manuscript directory test.
\end{abstract}
\section{Introduction}
See \cite{bench2026}.
\section{Conclusion}
Done.
\end{document}
""".strip()
        + "\n",
    )
    _write(
        tmp_path / "manuscript" / "PAPER-CONFIG.json",
        json.dumps(_paper_config_payload("Config Title", "jhep")),
    )
    _write(
        tmp_path / "manuscript" / "refs.bib",
        "@article{bench2026,\n  title={Benchmark},\n  author={Doe, Jane},\n  year={2026}\n}\n",
    )

    result = build_paper_quality_input(tmp_path)

    assert result.title == "Config Title"
    assert result.journal == "jhep"
    assert result.citations.citation_keys_resolve.satisfied == 1
    assert result.citations.citation_keys_resolve.total == 1


def test_build_paper_quality_input_uses_active_manuscript_root_and_canonical_config(tmp_path: Path) -> None:
    (tmp_path / "paper").mkdir()
    _write(
        tmp_path / "manuscript" / "lowercase_config_title.tex",
        r"""
\documentclass{article}
\begin{document}
\begin{abstract}
Active manuscript root test.
\end{abstract}
\section{Introduction}
See \cite{bench2026}.
\section{Conclusion}
Done.
\end{document}
""".strip()
        + "\n",
    )
    _write(
        tmp_path / "manuscript" / "PAPER-CONFIG.json",
        json.dumps(_paper_config_payload("Lowercase Config Title", "jhep")),
    )
    _write(
        tmp_path / "manuscript" / "refs.bib",
        "@article{bench2026,\n  title={Benchmark},\n  author={Doe, Jane},\n  year={2026}\n}\n",
    )
    _write(
        tmp_path / "manuscript" / "FIGURE_TRACKER.md",
        """---
figure_registry:
  - id: fig-benchmark
    label: "Fig. 1"
    kind: figure
    role: benchmark
    path: figures/benchmark.pdf
    contract_ids: [claim-benchmark]
    decisive: true
    has_units: true
    has_uncertainty: true
    referenced_in_text: true
    caption_self_contained: true
    colorblind_safe: true
---

# Figure Tracker
""",
    )

    result = build_paper_quality_input(tmp_path)

    assert result.title == "Lowercase Config Title"
    assert result.journal == "jhep"
    assert result.citations.citation_keys_resolve.satisfied == 1
    assert result.citations.citation_keys_resolve.total == 1
    assert result.figures.decisive_artifact_roles_clear.satisfied == 1


def test_build_paper_quality_input_reads_topic_specific_markdown_entrypoint(tmp_path: Path) -> None:
    _write(
        tmp_path / "paper" / "curvature_flow_bounds.md",
        """
# Curvature Flow Bounds

## Abstract
Markdown manuscript test.

## Introduction
See \\cite{bench2026}.

## Conclusion
Done.
""".strip()
        + "\n",
    )
    _write(
        tmp_path / "paper" / "PAPER-CONFIG.json",
        json.dumps(_paper_config_payload("Curvature Flow Bounds", "jhep")),
    )
    _write(
        tmp_path / "paper" / "refs.bib",
        "@article{bench2026,\n  title={Benchmark},\n  author={Doe, Jane},\n  year={2026}\n}\n",
    )

    result = build_paper_quality_input(tmp_path)

    assert result.title == "Curvature Flow Bounds"
    assert result.journal == "jhep"
    assert result.citations.citation_keys_resolve.satisfied == 1
    assert result.citations.citation_keys_resolve.total == 1
    assert result.completeness.required_sections_present.satisfied == 3
    assert result.completeness.required_sections_present.total == 3


def test_build_paper_quality_input_detects_empty_citation_and_reference_commands(tmp_path: Path) -> None:
    _write(
        tmp_path / "paper" / "curvature_flow_bounds.md",
        """
# Curvature Flow Bounds

## Abstract
Markdown manuscript test.

## Introduction
See \\cite{} and Eq.~\\ref{}.

## Conclusion
Done.
""".strip()
        + "\n",
    )
    _write(
        tmp_path / "paper" / "PAPER-CONFIG.json",
        json.dumps(_paper_config_payload("Curvature Flow Bounds", "jhep")),
    )

    result = build_paper_quality_input(tmp_path)
    report = score_paper_quality(result)

    assert result.journal_extra_checks["empty_citation_commands_absent"] is False
    assert result.journal_extra_checks["empty_reference_commands_absent"] is False
    blocker_checks = {issue.check for issue in report.blocking_issues}
    assert "empty_citation_commands_absent" in blocker_checks
    assert "empty_reference_commands_absent" in blocker_checks


def test_build_paper_quality_input_collects_comparison_verdicts_from_active_manuscript_root(tmp_path: Path) -> None:
    _write(
        tmp_path / "manuscript" / "curvature_flow_bounds.tex",
        "\\documentclass{article}\\begin{document}\\begin{abstract}A.\\end{abstract}\\section{Introduction}Intro.\\section{Conclusion}Done.\\end{document}\n",
    )
    _write(
        tmp_path / "manuscript" / "PAPER-CONFIG.json",
        json.dumps(_paper_config_payload("Curvature Flow Bounds", "jhep")),
    )
    _write(
        tmp_path / "manuscript" / "ARTIFACT-MANIFEST.json",
        json.dumps(
            {
                "version": 1,
                "paper_title": "Curvature Flow Bounds",
                "journal": "jhep",
                "created_at": "2026-03-13T00:00:00+00:00",
                "artifacts": [
                    {
                        "artifact_id": "tex-paper",
                        "category": "tex",
                        "path": "curvature_flow_bounds.tex",
                        "sha256": "0" * 64,
                        "produced_by": "test",
                        "sources": [],
                        "metadata": {},
                    }
                ],
            }
        ),
    )
    _write(
        tmp_path / "manuscript" / "BIBLIOGRAPHY-AUDIT.json",
        json.dumps(
            {
                "generated_at": "2026-03-13T00:00:00+00:00",
                "total_sources": 0,
                "resolved_sources": 0,
                "partial_sources": 0,
                "unverified_sources": 0,
                "failed_sources": 0,
                "entries": [],
            }
        ),
    )
    _write(
        tmp_path / "manuscript" / "FIGURE_TRACKER.md",
        """---
figure_registry:
  - id: fig-benchmark
    label: "Fig. 1"
    kind: figure
    role: benchmark
    path: manuscript/figures/benchmark.pdf
    contract_ids: [claim-benchmark]
    decisive: true
    has_units: true
    has_uncertainty: true
    referenced_in_text: true
    caption_self_contained: true
    colorblind_safe: true
---

# Figure Tracker
""",
    )
    _write(
        tmp_path / "manuscript" / "RESULTS-NOTE.md",
        """---
comparison_verdicts:
  - subject_id: claim-benchmark
    subject_kind: claim
    subject_role: decisive
    reference_id: ref-benchmark
    comparison_kind: benchmark
    metric: relative_error
    threshold: "<= 0.01"
    verdict: pass
---

# Results Note
""",
    )

    result = build_paper_quality_input(tmp_path)

    assert result.figures.decisive_artifact_roles_clear.satisfied == 1
    assert result.results.decisive_artifacts_with_explicit_verdicts.satisfied == 1


def test_build_paper_quality_input_surfaces_current_manuscript_reference_status(tmp_path: Path) -> None:
    _write(
        tmp_path / "paper" / "reference_bridge_test.tex",
        r"""
\documentclass{article}
\begin{document}
\begin{abstract}
Reference bridge test.
\end{abstract}
\section{Introduction}
See \cite{bench2026}.
\section{Conclusion}
Done.
\end{document}
""".strip()
        + "\n",
    )
    _write(
        tmp_path / "paper" / "PAPER-CONFIG.json",
        json.dumps(_paper_config_payload("Reference Bridge Test", "jhep")),
    )
    _write(
        tmp_path / "paper" / "BIBLIOGRAPHY-AUDIT.json",
        json.dumps(
            {
                "generated_at": "2026-03-13T00:00:00+00:00",
                "total_sources": 1,
                "resolved_sources": 1,
                "partial_sources": 0,
                "unverified_sources": 0,
                "failed_sources": 0,
                "entries": [
                    {
                        "key": "bench2026",
                        "reference_id": "ref-benchmark",
                        "source_type": "paper",
                        "title": "Benchmark",
                        "resolution_status": "provided",
                        "verification_status": "verified",
                    }
                ],
            }
        ),
    )

    result = build_paper_quality_input(tmp_path)

    assert result.journal_extra_checks["manuscript_reference_status_present"] is True
    assert result.journal_extra_checks["manuscript_reference_bridge_complete"] is True
    assert result.citations.citation_keys_resolve.satisfied == 1
    assert result.citations.citation_keys_resolve.total == 1
    assert result.citations.hallucination_free.passed is True


def test_build_paper_quality_input_checks_cited_keys_against_available_bibliography(tmp_path: Path) -> None:
    _write(
        tmp_path / "paper" / "benchmark_result.tex",
        r"""
\documentclass{article}
\begin{document}
\begin{abstract}
Benchmark result.
\end{abstract}
\section{Introduction}
See \cite{missing2026}.
\section{Conclusion}
Done.
\end{document}
""".strip()
        + "\n",
    )
    _write(
        tmp_path / "paper" / "PAPER-CONFIG.json",
        json.dumps(_paper_config_payload("Benchmark Result", "jhep")),
    )
    _write(
        tmp_path / "paper" / "BIBLIOGRAPHY-AUDIT.json",
        json.dumps(
            {
                "generated_at": "2026-03-13T00:00:00+00:00",
                "total_sources": 1,
                "resolved_sources": 1,
                "partial_sources": 0,
                "unverified_sources": 0,
                "failed_sources": 0,
                "entries": [
                    {
                        "key": "bench2026",
                        "source_type": "paper",
                        "title": "Benchmark",
                        "resolution_status": "provided",
                        "verification_status": "verified",
                    }
                ],
            }
        ),
    )

    result = build_paper_quality_input(tmp_path)

    assert result.citations.citation_keys_resolve.satisfied == 0
    assert result.citations.citation_keys_resolve.total == 1


def test_build_paper_quality_input_merges_comparison_artifact_scope_details(tmp_path: Path) -> None:
    _write(
        tmp_path / "paper" / "comparison_summary.tex",
        r"""
\documentclass{article}
\begin{document}
\begin{abstract}
Comparison summary.
\end{abstract}
\section{Introduction}
See Fig.~\ref{fig:benchmark}.
\section{Conclusion}
The benchmark remains under active tension.
\end{document}
""".strip()
        + "\n",
    )
    _write(
        tmp_path / "paper" / "PAPER-CONFIG.json",
        json.dumps(_paper_config_payload("Comparison Summary", "jhep")),
    )
    _write(
        tmp_path / "paper" / "FIGURE_TRACKER.md",
        """---
figure_registry:
  - id: fig-benchmark
    label: "Fig. 1"
    kind: figure
    role: benchmark
    path: paper/figures/benchmark.pdf
    contract_ids: [claim-benchmark]
    decisive: true
    has_units: true
    has_uncertainty: true
    referenced_in_text: true
    caption_self_contained: true
    colorblind_safe: true
    comparison_sources:
      - GPD/comparisons/benchmark-COMPARISON.md
---

# Figure Tracker
""",
    )
    _write(
        tmp_path / "GPD" / "phases" / "01-benchmark" / "01-SUMMARY.md",
        """---
phase: 01-benchmark
plan: 01
depth: full
provides: [benchmark comparison]
completed: 2026-03-13
comparison_verdicts:
  - subject_id: claim-benchmark
    subject_kind: claim
    subject_role: decisive
    reference_id: ref-benchmark
    comparison_kind: benchmark
    metric: relative_error
    threshold: "<= 0.01"
    verdict: fail
---

# Summary
""",
    )
    _write(
        tmp_path / "GPD" / "comparisons" / "benchmark-COMPARISON.md",
        """---
comparison_kind: benchmark
comparison_verdicts:
  - subject_id: claim-benchmark
    subject_kind: claim
    subject_role: decisive
    reference_id: ref-benchmark
    comparison_kind: benchmark
    metric: relative_error
    threshold: "<= 0.01"
    verdict: fail
    recommended_action: Narrow the claim to the verified regime.
---

# Internal Comparison
""",
    )

    result = build_paper_quality_input(tmp_path)

    assert result.results.decisive_artifacts_with_explicit_verdicts.satisfied == 1
    assert result.results.decisive_artifacts_benchmark_anchored.satisfied == 1
    assert result.results.decisive_comparison_failures_scoped.passed is True


def test_build_paper_quality_input_ignores_partial_summary_ledger_for_verified_coverage(tmp_path: Path) -> None:
    plan_dir = tmp_path / "GPD" / "phases" / "01-benchmark"
    _write(plan_dir / "01-01-PLAN.md", (STAGE0_FIXTURES_DIR / "plan_with_contract.md").read_text(encoding="utf-8"))
    _write(
        plan_dir / "01-01-SUMMARY.md",
        """---
phase: 01-benchmark
plan: 01
depth: full
provides: [benchmark comparison]
completed: 2026-03-13
plan_contract_ref: GPD/phases/01-benchmark/01-01-PLAN.md#/contract
contract_results:
  claims:
    claim-benchmark:
      status: passed
      summary: Benchmark reproduced
---

# Summary
""",
    )

    result = build_paper_quality_input(tmp_path)

    assert result.verification.contract_targets_verified.satisfied == 0
    assert result.verification.contract_targets_verified.total == 3
    assert result.verification.key_result_confidences == []


def test_build_paper_quality_input_marks_mixed_contract_results_ledger_alignment_failure(
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / "GPD" / "phases" / "01-benchmark"
    _write(plan_dir / "01-01-PLAN.md", (STAGE0_FIXTURES_DIR / "plan_with_contract.md").read_text(encoding="utf-8"))

    summary = (FIXTURES_DIR / "summary_with_contract_results.md").read_text(encoding="utf-8")
    summary = summary.replace(
        "  deliverables:\n",
        """    claim-made-up:
      status: passed
      summary: Invalid claim id
  deliverables:
""",
        1,
    )
    _write(plan_dir / "01-SUMMARY.md", summary)

    result = build_paper_quality_input(tmp_path)

    assert result.verification.contract_targets_verified.satisfied == 0
    assert result.verification.contract_targets_verified.total == 3
    assert result.verification.key_result_confidences == []
    assert result.journal_extra_checks["contract_results_parse_ok"] is True
    assert result.journal_extra_checks["contract_results_alignment_ok"] is False


def test_build_paper_quality_input_accepts_contract_results_artifact_salvage_drift(
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / "GPD" / "phases" / "01-benchmark"
    _write(plan_dir / "01-01-PLAN.md", (STAGE0_FIXTURES_DIR / "plan_with_contract.md").read_text(encoding="utf-8"))

    summary = (FIXTURES_DIR / "summary_with_contract_results.md").read_text(encoding="utf-8")
    summary = summary.replace("      status: passed\n", "      status: Passed\n", 1)
    summary = summary.replace(
        "      completed_actions: [read, compare, cite]\n",
        "      completed_actions: [Read, Compare, Cite]\n",
        1,
    )
    summary = summary.replace(
        "    weakest_anchors: [Reference tolerance interpretation]\n",
        "    weakest_anchors: Reference tolerance interpretation\n",
        1,
    )
    summary = summary.replace(
        "    disconfirming_observations: [Benchmark agreement disappears once normalization is fixed]\n",
        "    disconfirming_observations: Benchmark agreement disappears once normalization is fixed\n",
        1,
    )
    _write(plan_dir / "01-SUMMARY.md", summary)

    result = build_paper_quality_input(tmp_path)

    assert result.verification.contract_targets_verified.satisfied == 3
    assert result.verification.contract_targets_verified.total == 3
    assert result.journal_extra_checks["contract_results_parse_ok"] is True
    assert result.journal_extra_checks["contract_results_alignment_ok"] is True


def test_build_paper_quality_input_marks_invalid_contract_results_ledger_parse_failure(
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / "GPD" / "phases" / "01-benchmark"
    _write(plan_dir / "01-01-PLAN.md", (STAGE0_FIXTURES_DIR / "plan_with_contract.md").read_text(encoding="utf-8"))

    summary = (FIXTURES_DIR / "summary_with_contract_results.md").read_text(encoding="utf-8")
    summary = summary.replace(
        "  uncertainty_markers:\n    weakest_anchors: [Reference tolerance interpretation]\n    disconfirming_observations: [Benchmark agreement disappears once normalization is fixed]\n",
        "",
        1,
    )
    _write(plan_dir / "01-SUMMARY.md", summary)

    result = build_paper_quality_input(tmp_path)

    assert result.verification.contract_targets_verified.satisfied == 0
    assert result.verification.contract_targets_verified.total == 3
    assert result.verification.key_result_confidences == []
    assert result.journal_extra_checks["contract_results_parse_ok"] is False
    assert result.journal_extra_checks["contract_results_alignment_ok"] is False


def test_build_paper_quality_input_marks_malformed_contract_results_frontmatter_failure(
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / "GPD" / "phases" / "01-benchmark"
    _write(plan_dir / "01-01-PLAN.md", (STAGE0_FIXTURES_DIR / "plan_with_contract.md").read_text(encoding="utf-8"))

    summary = (
        "---\n"
        "phase: 01-benchmark\n"
        "plan: 01\n"
        "depth: full\n"
        "provides: [benchmark comparison]\n"
        "completed: 2026-03-15\n"
        "plan_contract_ref: GPD/phases/01-benchmark/01-01-PLAN.md#/contract\n"
        "contract_results:\n"
        "  claims:\n"
        "    claim-benchmark: [unterminated\n"
        "---\n\n"
        "# Summary\n"
    )
    _write(plan_dir / "01-SUMMARY.md", summary)

    result = build_paper_quality_input(tmp_path)

    assert result.journal_extra_checks["contract_results_parse_ok"] is False
    assert result.journal_extra_checks["contract_results_alignment_ok"] is False


def test_build_paper_quality_input_ignores_unrelated_phase_markdown_frontmatter_errors(
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / "GPD" / "phases" / "01-benchmark"
    _write(plan_dir / "01-01-PLAN.md", (STAGE0_FIXTURES_DIR / "plan_with_contract.md").read_text(encoding="utf-8"))
    _write(plan_dir / "01-SUMMARY.md", (FIXTURES_DIR / "summary_with_contract_results.md").read_text(encoding="utf-8"))
    _write(
        plan_dir / "README.md",
        """---
notes: [unterminated
---

# Notes
""",
    )

    result = build_paper_quality_input(tmp_path)

    assert result.journal_extra_checks["contract_results_parse_ok"] is True
    assert result.journal_extra_checks["contract_results_alignment_ok"] is True
    assert result.journal_extra_checks["comparison_verdicts_valid"] is True


def test_build_paper_quality_input_marks_explicit_null_contract_results_ledger_parse_failure(
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / "GPD" / "phases" / "01-benchmark"
    _write(plan_dir / "01-01-PLAN.md", (STAGE0_FIXTURES_DIR / "plan_with_contract.md").read_text(encoding="utf-8"))

    summary = (FIXTURES_DIR / "summary_with_contract_results.md").read_text(encoding="utf-8").replace(
        "contract_results:\n"
        "  claims:\n"
        "    claim-benchmark:\n"
        "      status: passed\n"
        "      summary: Benchmark claim verified against the decisive anchor.\n"
        "      linked_ids: [deliv-figure, test-benchmark, ref-benchmark]\n"
        "      evidence:\n"
        "        - verifier: gpd-verifier\n"
        "          method: benchmark reproduction\n"
        "          confidence: high\n"
        "          claim_id: claim-benchmark\n"
        "          deliverable_id: deliv-figure\n"
        "          acceptance_test_id: test-benchmark\n"
        "          reference_id: ref-benchmark\n"
        "          evidence_path: GPD/phases/01-benchmark/01-VERIFICATION.md\n"
        "  deliverables:\n"
        "    deliv-figure:\n"
        "      status: passed\n"
        "      path: figures/benchmark.png\n"
        "      summary: Figure produced with uncertainty band and benchmark overlay.\n"
        "      linked_ids: [claim-benchmark, test-benchmark]\n"
        "  acceptance_tests:\n"
        "    test-benchmark:\n"
        "      status: passed\n"
        "      summary: Benchmark reproduced within the contracted tolerance.\n"
        "      linked_ids: [claim-benchmark, deliv-figure, ref-benchmark]\n"
        "  references:\n"
        "    ref-benchmark:\n"
        "      status: completed\n"
        "      completed_actions: [read, compare, cite]\n"
        "      missing_actions: []\n"
        "      summary: Benchmark anchor surfaced in the comparison figure and manuscript text.\n"
        "  forbidden_proxies:\n"
        "    fp-benchmark:\n"
        "      status: rejected\n"
        "      notes: Qualitative trend agreement was not accepted without the numerical benchmark check.\n"
        "  uncertainty_markers:\n"
        "    weakest_anchors: [Reference tolerance interpretation]\n"
        "    disconfirming_observations: [Benchmark agreement disappears once normalization is fixed]\n",
        "contract_results:\n",
        1,
    )
    _write(plan_dir / "01-SUMMARY.md", summary)

    result = build_paper_quality_input(tmp_path)

    assert result.journal_extra_checks["contract_results_parse_ok"] is False
    assert result.journal_extra_checks["contract_results_alignment_ok"] is False


def test_build_paper_quality_input_ignores_mixed_comparison_verdict_ledger_for_coverage_and_confidence(
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / "GPD" / "phases" / "01-benchmark"
    _write(plan_dir / "01-01-PLAN.md", (STAGE0_FIXTURES_DIR / "plan_with_contract.md").read_text(encoding="utf-8"))

    summary = (FIXTURES_DIR / "summary_with_contract_results.md").read_text(encoding="utf-8")
    summary = summary.replace(
        "---\n\n# Summary\n",
        """  - subject_id: claim-made-up
    subject_kind: claim
    subject_role: decisive
    reference_id: ref-benchmark
    comparison_kind: benchmark
    metric: relative_error
    threshold: "<= 0.02"
    verdict: pass
---

# Summary
""",
        1,
    )
    _write(plan_dir / "01-SUMMARY.md", summary)

    result = build_paper_quality_input(tmp_path)

    assert result.verification.contract_targets_verified.satisfied == 0
    assert result.verification.contract_targets_verified.total == 3
    assert result.verification.key_result_confidences == []
    assert result.journal_extra_checks["comparison_verdicts_valid"] is False


def test_build_paper_quality_input_marks_malformed_comparison_frontmatter_failure(
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / "GPD" / "phases" / "01-benchmark"
    _write(plan_dir / "01-01-PLAN.md", (STAGE0_FIXTURES_DIR / "plan_with_contract.md").read_text(encoding="utf-8"))
    _write(
        tmp_path / "GPD" / "comparisons" / "benchmark-COMPARISON.md",
        """---
comparison_verdicts:
  - subject_id: claim-benchmark
    subject_kind: claim
    subject_role: decisive
    reference_id: ref-benchmark
    comparison_kind: benchmark
    metric: relative_error
    threshold: "<= 0.01"
    verdict: pass
    notes: [unterminated
---

# Internal Comparison
""",
    )

    result = build_paper_quality_input(tmp_path)

    assert result.journal_extra_checks["comparison_verdicts_valid"] is False


def test_build_paper_quality_input_marks_invalid_active_manuscript_root_comparison_verdicts(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / "manuscript" / "curvature_flow_bounds.tex",
        "\\documentclass{article}\\begin{document}\\begin{abstract}A.\\end{abstract}\\section{Introduction}Intro.\\section{Conclusion}Done.\\end{document}\n",
    )
    _write(
        tmp_path / "manuscript" / "PAPER-CONFIG.json",
        json.dumps(_paper_config_payload("Curvature Flow Bounds", "jhep")),
    )
    _write(
        tmp_path / "manuscript" / "INVALID-COMPARISON.md",
        """---
comparison_verdicts: invalid
---

# Invalid Comparison
""",
    )

    result = build_paper_quality_input(tmp_path)

    assert result.journal_extra_checks["comparison_verdicts_valid"] is False


def test_build_paper_quality_input_marks_invalid_verification_ledger_alignment_failure(tmp_path: Path) -> None:
    plan_dir = tmp_path / "GPD" / "phases" / "01-benchmark"
    _write(plan_dir / "01-01-PLAN.md", (STAGE0_FIXTURES_DIR / "plan_with_contract.md").read_text(encoding="utf-8"))
    _write(
        plan_dir / "01-VERIFICATION.md",
        """---
phase: 01-benchmark
verified: 2026-03-13T00:00:00Z
status: passed
score: 0.9
plan_contract_ref: GPD/phases/01-benchmark/01-01-PLAN.md#/contract
contract_results:
  claims:
    claim-made-up:
      status: passed
      summary: Invalid claim id
---

# Verification
""",
    )

    result = build_paper_quality_input(tmp_path)

    assert result.verification.report_passed.passed is False
    assert result.verification.contract_targets_verified.satisfied == 0
    assert result.verification.contract_targets_verified.total == 3
    assert result.journal_extra_checks["contract_results_parse_ok"] is False
    assert result.journal_extra_checks["contract_results_alignment_ok"] is False


def test_build_paper_quality_input_marks_unresolved_summary_contract_ledger_alignment_failure(
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / "GPD" / "phases" / "01-benchmark"
    _write(plan_dir / "01-01-PLAN.md", (STAGE0_FIXTURES_DIR / "plan_with_contract.md").read_text(encoding="utf-8"))
    _write(
        plan_dir / "01-01-SUMMARY.md",
        """---
phase: 01-benchmark
plan: 01
depth: full
provides: [benchmark comparison]
completed: 2026-03-13
plan_contract_ref: GPD/phases/01-benchmark/01-99-PLAN.md#/contract
contract_results:
  claims:
    claim-benchmark:
      status: passed
      summary: Benchmark reproduced
---

# Summary
""",
    )

    result = build_paper_quality_input(tmp_path)

    assert result.verification.contract_targets_verified.satisfied == 0
    assert result.verification.contract_targets_verified.total == 3
    assert result.journal_extra_checks["contract_results_parse_ok"] is False
    assert result.journal_extra_checks["contract_results_alignment_ok"] is False


def test_publication_review_surfaces_keep_protocol_bundle_guidance_additive() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    write_paper = (repo_root / "src/gpd/specs/workflows/write-paper.md").read_text(encoding="utf-8")
    peer_review = (repo_root / "src/gpd/specs/workflows/peer-review.md").read_text(encoding="utf-8")
    respond = (repo_root / "src/gpd/specs/workflows/respond-to-referees.md").read_text(encoding="utf-8")
    internal_template = (repo_root / "src/gpd/specs/templates/paper/internal-comparison.md").read_text(
        encoding="utf-8"
    )
    experimental_template = (repo_root / "src/gpd/specs/templates/paper/experimental-comparison.md").read_text(
        encoding="utf-8"
    )

    assert "protocol_bundle_context" in write_paper
    assert "additive specialized-publication guidance" in write_paper
    assert "GPD/comparisons/*-COMPARISON.md" in write_paper
    assert "Do **not** let bundle guidance invent new claims" in write_paper
    assert "Missing generic `verification_status` / `confidence` tags alone are not blockers." in write_paper
    assert "Treat paper-support artifacts as scaffolding, not as proof that a claim is established." in write_paper

    assert "protocol_bundle_context" in peer_review
    assert "${MANUSCRIPT_ROOT}/FIGURE_TRACKER.md" in peer_review
    assert "GPD/comparisons/*-COMPARISON.md" in peer_review
    assert "Treat bundle guidance as additive skepticism only" in peer_review
    assert "review-support artifacts are scaffolding, not substitutes for contract-backed evidence" in peer_review

    assert "protocol_bundle_context" in respond
    assert "missing decisive evidence we already owed" in respond
    assert "prefer fulfilling that existing obligation or narrowing the claim" in respond
    assert "Treat referee requests beyond the manuscript's honest scope as optional unless they expose a real support gap" in respond

    assert "protocol_bundle_ids (optional):" not in internal_template
    assert "bundle_expectations (optional):" not in internal_template
    assert "omit `protocol_bundle_ids` and `bundle_expectations` entirely" in internal_template.lower()
    assert "additive provenance" in internal_template
    assert "protocol_bundle_ids (optional):" not in experimental_template
    assert "bundle_expectations (optional):" not in experimental_template
    assert "omit `protocol_bundle_ids` and `bundle_expectations` entirely" in experimental_template.lower()
    assert "additive provenance" in experimental_template
