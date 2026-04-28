from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from gpd.core.reproducibility import compute_sha256

CANONICAL_MANUSCRIPT_STEM = "curvature_flow_bounds"
_CREATED_AT = "2026-03-10T00:00:00+00:00"


def manuscript_path(project_root: Path, *, stem: str = CANONICAL_MANUSCRIPT_STEM) -> Path:
    return project_root / "paper" / f"{stem}.tex"


def manuscript_pdf_path(project_root: Path, *, stem: str = CANONICAL_MANUSCRIPT_STEM) -> Path:
    return project_root / "paper" / f"{stem}.pdf"


def manuscript_relpath(*, stem: str = CANONICAL_MANUSCRIPT_STEM) -> str:
    return f"paper/{stem}.tex"


@dataclass(frozen=True)
class ProofReviewPackage:
    manuscript_path: Path
    manuscript_relpath: str
    manuscript_sha256: str
    manuscript_pdf_path: Path
    proof_artifact_path: Path
    proof_artifact_relpath: str


def _write_artifact_manifest(
    project_root: Path,
    *,
    stem: str,
    title: str,
    manuscript: Path,
    manuscript_pdf: Path,
) -> None:
    paper_dir = manuscript.parent
    bibliography_path = paper_dir / "BIBLIOGRAPHY-AUDIT.json"
    manuscript_sha256 = compute_sha256(manuscript)
    (paper_dir / "ARTIFACT-MANIFEST.json").write_text(
        json.dumps(
            {
                "version": 1,
                "paper_title": title,
                "journal": "jhep",
                "created_at": _CREATED_AT,
                "manuscript_sha256": manuscript_sha256,
                "manuscript_mtime_ns": manuscript.stat().st_mtime_ns,
                "artifacts": [
                    {
                        "artifact_id": "manuscript-tex",
                        "category": "tex",
                        "path": f"{stem}.tex",
                        "sha256": manuscript_sha256,
                        "produced_by": "tests.manuscript_test_support",
                        "sources": [],
                        "metadata": {"role": "manuscript"},
                    },
                    {
                        "artifact_id": "manuscript-pdf",
                        "category": "pdf",
                        "path": f"{stem}.pdf",
                        "sha256": compute_sha256(manuscript_pdf),
                        "produced_by": "tests.manuscript_test_support",
                        "sources": [{"path": f"{stem}.tex", "role": "compiled_from"}],
                        "metadata": {"role": "compiled_manuscript"},
                    },
                    {
                        "artifact_id": "bibliography-audit",
                        "category": "audit",
                        "path": "BIBLIOGRAPHY-AUDIT.json",
                        "sha256": compute_sha256(bibliography_path),
                        "produced_by": "tests.manuscript_test_support",
                        "sources": [{"path": f"{stem}.tex", "role": "cites"}],
                        "metadata": {"role": "bibliography_audit"},
                    },
                ],
            }
        ),
        encoding="utf-8",
    )


def _write_bibliography_audit(project_root: Path, *, title: str) -> None:
    (project_root / "paper" / "BIBLIOGRAPHY-AUDIT.json").write_text(
        json.dumps(
            {
                "generated_at": _CREATED_AT,
                "total_sources": 1,
                "resolved_sources": 1,
                "partial_sources": 0,
                "unverified_sources": 0,
                "failed_sources": 0,
                "entries": [
                    {
                        "key": "Ref2026",
                        "source_type": "paper",
                        "reference_id": "ref-main",
                        "title": title,
                        "resolution_status": "provided",
                        "verification_status": "verified",
                        "verification_sources": ["phase-summary"],
                        "canonical_identifiers": ["doi:10.1000/test"],
                        "missing_core_fields": [],
                        "enriched_fields": [],
                        "warnings": [],
                        "errors": [],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def _write_stage_report(
    review_dir: Path,
    *,
    stage_id: str,
    round_number: int,
    round_suffix: str,
    manuscript_rel: str,
    manuscript_sha256: str,
    claims_reviewed: list[str] | None = None,
    proof_audits: list[dict[str, object]] | None = None,
) -> str:
    artifact_name = f"STAGE-{stage_id}{round_suffix}.json"
    (review_dir / artifact_name).write_text(
        json.dumps(
            {
                "version": 1,
                "round": round_number,
                "stage_id": stage_id,
                "stage_kind": stage_id,
                "manuscript_path": manuscript_rel,
                "manuscript_sha256": manuscript_sha256,
                "claims_reviewed": claims_reviewed or [],
                "summary": f"{stage_id} review",
                "strengths": ["checked manuscript"],
                "findings": [],
                "proof_audits": proof_audits or [],
                "confidence": "high",
                "recommendation_ceiling": "minor_revision",
            }
        ),
        encoding="utf-8",
    )
    return f"GPD/review/{artifact_name}"


def write_proof_review_package(
    project_root: Path,
    *,
    theorem_bearing: bool,
    review_report: bool = False,
    proof_redteam_status: str | None = "passed",
    proof_redteam_reviewer: str = "gpd-check-proof",
    proof_redteam_sha256: str | None = None,
    round_number: int = 1,
    manuscript_stem: str = CANONICAL_MANUSCRIPT_STEM,
    proof_artifact_relpath: str | None = None,
) -> ProofReviewPackage:
    manuscript_body = (
        "\\begin{theorem}For every r_0 > 0, the orbit intersects the target annulus.\\end{theorem}\n\\begin{proof}Carry r_0 through the argument.\\end{proof}"
        if theorem_bearing
        else "Submission draft."
    )
    manuscript = manuscript_path(project_root, stem=manuscript_stem)
    manuscript.parent.mkdir(parents=True, exist_ok=True)
    manuscript.write_text(
        "\\documentclass{article}\n"
        "\\begin{document}\n"
        f"{manuscript_body}\n"
        "\\end{document}\n",
        encoding="utf-8",
    )
    manuscript_rel = manuscript_relpath(stem=manuscript_stem)
    manuscript_pdf = manuscript_pdf_path(project_root, stem=manuscript_stem)
    manuscript_pdf.write_bytes(b"%PDF-1.4\n% topic-specific manuscript pdf\n")
    title = " ".join(part.capitalize() for part in manuscript_stem.split("_"))

    _write_bibliography_audit(project_root, title=title)
    _write_artifact_manifest(
        project_root,
        stem=manuscript_stem,
        title=title,
        manuscript=manuscript,
        manuscript_pdf=manuscript_pdf,
    )

    proof_artifact_rel = proof_artifact_relpath or manuscript_rel
    proof_artifact = project_root / proof_artifact_rel
    proof_artifact.parent.mkdir(parents=True, exist_ok=True)
    if proof_artifact != manuscript:
        proof_artifact.write_text(
            "\\documentclass{article}\n\\begin{document}\nExternal proof.\n\\end{document}\n",
            encoding="utf-8",
        )

    manuscript_sha256 = compute_sha256(manuscript)
    review_dir = project_root / "GPD" / "review"
    review_dir.mkdir(parents=True, exist_ok=True)
    round_suffix = "" if round_number <= 1 else f"-R{round_number}"
    claim_text = (
        "For every r_0 > 0, the orbit intersects the target annulus."
        if theorem_bearing
        else "The manuscript reports a descriptive result."
    )
    theorem_assumptions = ["chi > 0"] if theorem_bearing else []
    theorem_parameters = ["r_0"] if theorem_bearing else []
    proof_audits = (
        [
            {
                "claim_id": "CLM-001",
                "theorem_assumptions_checked": theorem_assumptions,
                "theorem_parameters_checked": theorem_parameters,
                "proof_locations": [f"{proof_artifact_rel}:1"],
                "uncovered_assumptions": [],
                "uncovered_parameters": [],
                "coverage_gaps": [],
                "alignment_status": "aligned",
                "notes": "Complete coverage.",
            }
        ]
        if theorem_bearing
        else []
    )

    (review_dir / f"CLAIMS{round_suffix}.json").write_text(
        json.dumps(
            {
                "version": 1,
                "manuscript_path": manuscript_rel,
                "manuscript_sha256": manuscript_sha256,
                "claims": [
                    {
                        "claim_id": "CLM-001",
                        "claim_type": "main_result",
                        "claim_kind": "theorem" if theorem_bearing else "other",
                        "text": claim_text,
                        "artifact_path": proof_artifact_rel,
                        "section": "Main Result",
                        "equation_refs": [],
                        "figure_refs": [],
                        "supporting_artifacts": [],
                        "theorem_assumptions": theorem_assumptions,
                        "theorem_parameters": theorem_parameters,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    stage_artifacts = [
        _write_stage_report(
            review_dir,
            stage_id=stage_id,
            round_number=round_number,
            round_suffix=round_suffix,
            manuscript_rel=manuscript_rel,
            manuscript_sha256=manuscript_sha256,
            claims_reviewed=["CLM-001"] if theorem_bearing and stage_id == "math" else [],
            proof_audits=proof_audits if stage_id == "math" else [],
        )
        for stage_id in ("reader", "literature", "math", "physics", "interestingness")
    ]

    (review_dir / f"REVIEW-LEDGER{round_suffix}.json").write_text(
        json.dumps(
            {
                "version": 1,
                "round": round_number,
                "manuscript_path": manuscript_rel,
                "issues": [],
            }
        ),
        encoding="utf-8",
    )
    (review_dir / f"REFEREE-DECISION{round_suffix}.json").write_text(
        json.dumps(
            {
                "manuscript_path": manuscript_rel,
                "target_journal": "jhep",
                "final_recommendation": "accept",
                "final_confidence": "high",
                "stage_artifacts": stage_artifacts,
                "central_claims_supported": True,
                "claim_scope_proportionate_to_evidence": True,
                "physical_assumptions_justified": True,
                "proof_audit_coverage_complete": True,
                "theorem_proof_alignment_adequate": True,
                "unsupported_claims_are_central": False,
                "reframing_possible_without_new_results": True,
                "mathematical_correctness": "adequate",
                "novelty": "adequate",
                "significance": "adequate",
                "venue_fit": "adequate",
                "literature_positioning": "adequate",
                "unresolved_major_issues": 0,
                "unresolved_minor_issues": 0,
                "blocking_issue_ids": [],
            }
        ),
        encoding="utf-8",
    )

    if theorem_bearing and review_report and proof_redteam_status is not None:
        proof_redteam_artifact_paths = f"  - {proof_artifact_rel}\n"
        if proof_artifact_rel != manuscript_rel:
            proof_redteam_artifact_paths += f"  - {manuscript_rel}\n"

        (review_dir / f"PROOF-REDTEAM{round_suffix}.md").write_text(
            (
                "---\n"
                f"status: {proof_redteam_status}\n"
                f"reviewer: {proof_redteam_reviewer}\n"
                "claim_ids:\n"
                "  - CLM-001\n"
                "proof_artifact_paths:\n"
                f"{proof_redteam_artifact_paths}"
                f"manuscript_path: {manuscript_rel}\n"
                f"manuscript_sha256: {proof_redteam_sha256 or manuscript_sha256}\n"
                f"round: {round_number}\n"
                "missing_parameter_symbols: []\n"
                "missing_hypothesis_ids: []\n"
                "coverage_gaps: []\n"
                "scope_status: matched\n"
                "quantifier_status: matched\n"
                "counterexample_status: none_found\n"
                "---\n\n"
                "# Proof Redteam\n"
                "## Proof Inventory\n"
                "- Exact claim / theorem text: For every r_0 > 0, the orbit intersects the target annulus.\n"
                "- Claim / theorem target: Annulus intersection for every target radius.\n"
                "- Named parameters:\n"
                "  - `r_0`: target radius\n"
                "- Hypotheses:\n"
                "  - `H1`: chi > 0\n"
                "- Quantifier / domain obligations:\n"
                "  - for every r_0 > 0\n"
                "- Conclusion clauses:\n"
                "  - annulus intersection holds\n"
                "## Coverage Ledger\n"
                "### Named-Parameter Coverage\n"
                "| Parameter | Role / Domain | Proof Location | Status | Notes |\n"
                "| --- | --- | --- | --- |\n"
                f"| `r_0` | target radius | {proof_artifact_rel}:1 | covered | Carried through the argument. |\n"
                "### Hypothesis Coverage\n"
                "| Hypothesis | Proof Location | Status | Notes |\n"
                "| --- | --- | --- | --- |\n"
                f"| `H1` | {proof_artifact_rel}:1 | covered | Used in the positivity step. |\n"
                "### Quantifier / Domain Coverage\n"
                "| Obligation | Proof Location | Status | Notes |\n"
                "| --- | --- | --- | --- |\n"
                f"| `for every r_0 > 0` | {proof_artifact_rel}:1 | covered | No specialization introduced. |\n"
                "### Conclusion-Clause Coverage\n"
                "| Clause | Proof Location | Status | Notes |\n"
                "| --- | --- | --- | --- |\n"
                f"| annulus intersection holds | {proof_artifact_rel}:1 | covered | Final sentence states it. |\n"
                "## Adversarial Probe\n"
                "- Probe type: dropped-parameter test\n"
                "- Result: The proof still references r_0, so the theorem remains global in the target radius.\n"
                "## Verdict\n"
                "- Scope status: `matched`\n"
                "- Quantifier status: `matched`\n"
                "- Counterexample status: `none_found`\n"
                "- Blocking gaps:\n"
                "  - None.\n"
                "## Required Follow-Up\n"
                "- None.\n"
            ),
            encoding="utf-8",
        )

    return ProofReviewPackage(
        manuscript_path=manuscript,
        manuscript_relpath=manuscript_rel,
        manuscript_sha256=manuscript_sha256,
        manuscript_pdf_path=manuscript_pdf,
        proof_artifact_path=proof_artifact,
        proof_artifact_relpath=proof_artifact_rel,
    )
