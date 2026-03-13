from __future__ import annotations

import json
from pathlib import Path

from gpd.core.paper_quality_artifacts import build_paper_quality_input

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "stage4"


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
                "journal": "prd",
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
                "entries": [],
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
        tmp_path / ".gpd" / "phases" / "01-benchmark" / "01-SUMMARY.md",
        (FIXTURES_DIR / "summary_with_contract_results.md").read_text(encoding="utf-8"),
    )
    _write(
        tmp_path / ".gpd" / "phases" / "01-benchmark" / "01-VERIFICATION.md",
        (FIXTURES_DIR / "verification_with_contract_results.md").read_text(encoding="utf-8"),
    )

    result = build_paper_quality_input(tmp_path)

    assert result.title == "Benchmark Paper"
    assert result.journal == "prd"
    assert result.completeness.required_sections_present.satisfied == 3
    assert result.citations.missing_placeholders.passed is True
    assert result.citations.citation_keys_resolve.satisfied == 1
    assert result.verification.report_passed.passed is True
    assert result.verification.contract_targets_verified.satisfied == 3
    assert result.verification.contract_targets_verified.total == 3
    assert result.figures.decisive_artifact_roles_clear.satisfied == 1
    assert result.results.decisive_artifacts_with_explicit_verdicts.satisfied == 1
    assert result.results.decisive_artifacts_benchmark_anchored.satisfied == 1


def test_build_paper_quality_input_is_conservative_when_artifacts_are_missing(tmp_path: Path) -> None:
    _write(
        tmp_path / "paper" / "main.tex",
        "\\documentclass{article}\\begin{document}\\section{Introduction}Only intro.\\end{document}\n",
    )

    result = build_paper_quality_input(tmp_path)

    assert result.journal == "generic"
    assert result.verification.report_passed.passed is False
    assert result.results.decisive_artifacts_with_explicit_verdicts.not_applicable is True
    assert result.completeness.required_sections_present.satisfied == 1
