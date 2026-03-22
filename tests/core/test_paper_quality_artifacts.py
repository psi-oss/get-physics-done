from __future__ import annotations

import json
from pathlib import Path

from gpd.core.paper_quality import score_paper_quality
from gpd.core.paper_quality_artifacts import build_paper_quality_input

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "stage4"
STAGE0_FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "stage0"


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_build_paper_quality_input_reads_contract_and_comparison_artifacts(tmp_path: Path) -> None:
    _write(
        tmp_path / "paper" / "main.tex",
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
                "artifacts": [],
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
        tmp_path / ".gpd" / "paper" / "FIGURE_TRACKER.md",
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
      - .gpd/comparisons/benchmark-COMPARISON.md
---

# Figure Tracker
""",
    )
    _write(
        tmp_path / ".gpd" / "comparisons" / "benchmark-COMPARISON.md",
        """---
comparison_kind: benchmark
comparison_sources:
  - label: theory
    kind: summary
    path: .gpd/phases/01-benchmark/01-SUMMARY.md
  - label: benchmark
    kind: verification
    path: .gpd/phases/01-benchmark/01-VERIFICATION.md
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
        tmp_path / ".gpd" / "phases" / "01-benchmark" / "01-01-PLAN.md",
        (STAGE0_FIXTURES_DIR / "plan_with_contract.md").read_text(encoding="utf-8"),
    )
    _write(
        tmp_path / ".gpd" / "phases" / "01-benchmark" / "01-SUMMARY.md",
        (FIXTURES_DIR / "summary_with_contract_results.md").read_text(encoding="utf-8"),
    )
    _write(
        tmp_path / ".gpd" / "phases" / "01-benchmark" / "01-VERIFICATION.md",
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


def test_build_paper_quality_input_falls_back_to_supported_config_journal_when_manifest_is_unsupported(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / "paper" / "main.tex",
        "\\documentclass{article}\\begin{document}\\begin{abstract}Fallback test.\\end{abstract}\\section{Introduction}Intro.\\section{Conclusion}Done.\\end{document}\n",
    )
    _write(
        tmp_path / "paper" / "PAPER-CONFIG.json",
        json.dumps({"title": "Config Fallback Title", "journal": "jhep"}),
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

    assert result.title == "Manifest Title"
    assert result.journal == "jhep"


def test_build_paper_quality_input_normalizes_empty_contract_results_reference_lists(tmp_path: Path) -> None:
    plan_dir = tmp_path / ".gpd" / "phases" / "01-benchmark"
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
plan_contract_ref: .gpd/phases/01-benchmark/01-01-PLAN.md#/contract
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
          evidence_path: .gpd/phases/01-benchmark/01-VERIFICATION.md
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
          evidence_path: .gpd/phases/01-benchmark/01-VERIFICATION.md
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
          evidence_path: .gpd/phases/01-benchmark/01-VERIFICATION.md
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
        tmp_path / "paper" / "main.tex",
        "\\documentclass{article}\\begin{document}\\section{Introduction}Only intro.\\end{document}\n",
    )

    result = build_paper_quality_input(tmp_path)

    assert result.journal == "generic"
    assert result.verification.report_passed.passed is False
    assert result.verification.contract_targets_verified.not_applicable is True
    assert result.results.decisive_artifacts_with_explicit_verdicts.not_applicable is True
    assert result.completeness.required_sections_present.satisfied == 1

    report = score_paper_quality(result)
    assert report.categories["verification"].checks["contract_targets_verified"] == 5.0


def test_build_paper_quality_input_ignores_invalid_artifact_manifest_and_falls_back_to_config(tmp_path: Path) -> None:
    _write(
        tmp_path / "paper" / "main.tex",
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
        tmp_path / "paper" / "main.tex",
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
    assert result.citations.hallucination_free.not_applicable is True


def test_build_paper_quality_input_requires_decisive_verdicts_for_decisive_artifact_coverage(tmp_path: Path) -> None:
    _write(
        tmp_path / ".gpd" / "paper" / "FIGURE_TRACKER.md",
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
      - .gpd/comparisons/benchmark-COMPARISON.md
---

# Figure Tracker
""",
    )
    _write(
        tmp_path / ".gpd" / "comparisons" / "benchmark-COMPARISON.md",
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
        tmp_path / ".gpd" / "phases" / "01-benchmark" / "01-01-PLAN.md",
        (STAGE0_FIXTURES_DIR / "plan_with_contract.md").read_text(encoding="utf-8"),
    )

    result = build_paper_quality_input(tmp_path)

    assert result.results.decisive_artifacts_with_explicit_verdicts.satisfied == 0
    assert result.results.decisive_artifacts_with_explicit_verdicts.total == 1
    assert result.results.decisive_artifacts_benchmark_anchored.satisfied == 0
    assert result.results.decisive_artifacts_benchmark_anchored.total == 1


def test_build_paper_quality_input_reads_manuscript_dir_and_config_title(tmp_path: Path) -> None:
    _write(
        tmp_path / "manuscript" / "main.tex",
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
        json.dumps({"title": "Config Title", "journal": "jhep"}),
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


def test_build_paper_quality_input_checks_cited_keys_against_available_bibliography(tmp_path: Path) -> None:
    _write(
        tmp_path / "paper" / "main.tex",
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
        tmp_path / "paper" / "main.tex",
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
        tmp_path / ".gpd" / "paper" / "FIGURE_TRACKER.md",
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
      - .gpd/comparisons/benchmark-COMPARISON.md
---

# Figure Tracker
""",
    )
    _write(
        tmp_path / ".gpd" / "phases" / "01-benchmark" / "01-SUMMARY.md",
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
        tmp_path / ".gpd" / "comparisons" / "benchmark-COMPARISON.md",
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
    plan_dir = tmp_path / ".gpd" / "phases" / "01-benchmark"
    _write(plan_dir / "01-01-PLAN.md", (STAGE0_FIXTURES_DIR / "plan_with_contract.md").read_text(encoding="utf-8"))
    _write(
        plan_dir / "01-01-SUMMARY.md",
        """---
phase: 01-benchmark
plan: 01
depth: full
provides: [benchmark comparison]
completed: 2026-03-13
plan_contract_ref: .gpd/phases/01-benchmark/01-01-PLAN.md#/contract
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


def test_build_paper_quality_input_ignores_mixed_contract_results_ledger_for_coverage_and_confidence(
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / ".gpd" / "phases" / "01-benchmark"
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


def test_build_paper_quality_input_ignores_invalid_contract_results_ledger_for_coverage_and_confidence(
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / ".gpd" / "phases" / "01-benchmark"
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


def test_build_paper_quality_input_ignores_mixed_comparison_verdict_ledger_for_coverage_and_confidence(
    tmp_path: Path,
) -> None:
    plan_dir = tmp_path / ".gpd" / "phases" / "01-benchmark"
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


def test_build_paper_quality_input_ignores_invalid_verification_ledger_for_report_passed(tmp_path: Path) -> None:
    plan_dir = tmp_path / ".gpd" / "phases" / "01-benchmark"
    _write(plan_dir / "01-01-PLAN.md", (STAGE0_FIXTURES_DIR / "plan_with_contract.md").read_text(encoding="utf-8"))
    _write(
        plan_dir / "01-VERIFICATION.md",
        """---
phase: 01-benchmark
verified: 2026-03-13
status: passed
score: 0.9
plan_contract_ref: .gpd/phases/01-benchmark/01-01-PLAN.md#/contract
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


def test_build_paper_quality_input_ignores_unresolved_summary_contract_ledger_for_coverage(tmp_path: Path) -> None:
    plan_dir = tmp_path / ".gpd" / "phases" / "01-benchmark"
    _write(plan_dir / "01-01-PLAN.md", (STAGE0_FIXTURES_DIR / "plan_with_contract.md").read_text(encoding="utf-8"))
    _write(
        plan_dir / "01-01-SUMMARY.md",
        """---
phase: 01-benchmark
plan: 01
depth: full
provides: [benchmark comparison]
completed: 2026-03-13
plan_contract_ref: .gpd/phases/01-benchmark/01-99-PLAN.md#/contract
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
    assert ".gpd/comparisons/*-COMPARISON.md" in write_paper
    assert "Do **not** let bundle guidance invent new claims" in write_paper
    assert "Missing generic `verification_status` / `confidence` tags alone are not blockers." in write_paper
    assert "Treat paper-support artifacts as scaffolding, not as proof that a claim is established." in write_paper

    assert "protocol_bundle_context" in peer_review
    assert ".gpd/paper/FIGURE_TRACKER.md" in peer_review
    assert ".gpd/comparisons/*-COMPARISON.md" in peer_review
    assert "Treat bundle guidance as additive skepticism only." in peer_review
    assert "Review-support artifacts are scaffolding, not substitutes for contract-backed evidence." in peer_review

    assert "protocol_bundle_context" in respond
    assert "missing decisive evidence we already owed" in respond
    assert "prefer fulfilling that existing obligation or narrowing the claim" in respond
    assert "Treat referee requests beyond the manuscript's honest scope as optional unless they expose a real support gap" in respond

    assert "protocol_bundle_ids (optional):" in internal_template
    assert "bundle_expectations (optional):" in internal_template
    assert "additive provenance" in internal_template
    assert "protocol_bundle_ids (optional):" in experimental_template
    assert "bundle_expectations (optional):" in experimental_template
    assert "additive provenance" in experimental_template
