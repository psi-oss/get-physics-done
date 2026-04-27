from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from gpd.contracts import PROOF_AUDIT_REVIEWER
from gpd.core.artifact_text import ArtifactTextError, ArtifactTextSurface
from gpd.core.proof_review import (
    manuscript_has_theorem_bearing_claim_inventory,
    manuscript_has_theorem_bearing_language,
    manuscript_has_theorem_bearing_review_anchor,
    manuscript_proof_review_manifest_path,
    manuscript_requires_theorem_bearing_review,
    phase_proof_review_manifest_path,
    publication_subject_slug,
    resolve_manuscript_proof_review_status,
    resolve_phase_proof_review_status,
)
from gpd.core.reproducibility import compute_sha256
from tests.manuscript_test_support import CANONICAL_MANUSCRIPT_STEM, write_proof_review_package


def _write_external_manuscript_review_anchor(project_root: Path) -> Path:
    manuscript_path = project_root / "submission" / "external-subject.tex"
    manuscript_path.parent.mkdir(parents=True, exist_ok=True)
    manuscript_path.write_text(
        "\\documentclass{article}\n\\begin{document}\nExternal submission draft.\n\\end{document}\n",
        encoding="utf-8",
    )
    (manuscript_path.parent / "references.bib").write_text("@article{demo,title={External Demo}}\n", encoding="utf-8")
    manuscript_rel = "submission/external-subject.tex"
    manuscript_sha256 = compute_sha256(manuscript_path)

    review_dir = project_root / "GPD" / "publication" / publication_subject_slug(project_root, manuscript_path) / "review"
    review_dir.mkdir(parents=True, exist_ok=True)
    (review_dir / "CLAIMS.json").write_text(
        json.dumps(
            {
                "version": 1,
                "manuscript_path": manuscript_rel,
                "manuscript_sha256": manuscript_sha256,
                "claims": [
                    {
                        "claim_id": "CLM-EXT-001",
                        "claim_type": "main_result",
                        "claim_kind": "other",
                        "text": "The manuscript reports a descriptive external result.",
                        "artifact_path": manuscript_rel,
                        "section": "Main Result",
                        "equation_refs": [],
                        "figure_refs": [],
                        "supporting_artifacts": [],
                        "theorem_assumptions": [],
                        "theorem_parameters": [],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (review_dir / "STAGE-math.json").write_text(
        json.dumps(
            {
                "version": 1,
                "round": 1,
                "stage_id": "math",
                "stage_kind": "math",
                "manuscript_path": manuscript_rel,
                "manuscript_sha256": manuscript_sha256,
                "claims_reviewed": [],
                "summary": "math review",
                "strengths": ["checked manuscript"],
                "findings": [],
                "proof_audits": [],
                "confidence": "high",
                "recommendation_ceiling": "minor_revision",
            }
        ),
        encoding="utf-8",
    )
    return manuscript_path


def _write_external_theorem_bearing_review_anchor(project_root: Path) -> tuple[Path, Path]:
    manuscript_path = project_root / "submission" / "external-theorem.tex"
    manuscript_path.parent.mkdir(parents=True, exist_ok=True)
    manuscript_path.write_text(
        "\\documentclass{article}\n"
        "\\begin{document}\n"
        "\\begin{theorem}For every r_0 > 0, the orbit intersects the target annulus.\\end{theorem}\n"
        "\\begin{proof}Carry r_0 through the argument.\\end{proof}\n"
        "\\end{document}\n",
        encoding="utf-8",
    )
    (manuscript_path.parent / "references.bib").write_text("@article{demo,title={External Theorem Demo}}\n", encoding="utf-8")
    manuscript_rel = "submission/external-theorem.tex"
    manuscript_sha256 = compute_sha256(manuscript_path)
    review_dir = project_root / "GPD" / "publication" / publication_subject_slug(project_root, manuscript_path) / "review"
    review_dir.mkdir(parents=True, exist_ok=True)

    (review_dir / "CLAIMS.json").write_text(
        json.dumps(
            {
                "version": 1,
                "manuscript_path": manuscript_rel,
                "manuscript_sha256": manuscript_sha256,
                "claims": [
                    {
                        "claim_id": "CLM-EXT-001",
                        "claim_type": "main_result",
                        "claim_kind": "theorem",
                        "text": "For every r_0 > 0, the orbit intersects the target annulus.",
                        "artifact_path": manuscript_rel,
                        "section": "Main Result",
                        "equation_refs": [],
                        "figure_refs": [],
                        "supporting_artifacts": [],
                        "theorem_assumptions": ["chi > 0"],
                        "theorem_parameters": ["r_0"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (review_dir / "STAGE-math.json").write_text(
        json.dumps(
            {
                "version": 1,
                "round": 1,
                "stage_id": "math",
                "stage_kind": "math",
                "manuscript_path": manuscript_rel,
                "manuscript_sha256": manuscript_sha256,
                "claims_reviewed": ["CLM-EXT-001"],
                "summary": "math review",
                "strengths": ["checked theorem coverage"],
                "findings": [],
                "proof_audits": [
                    {
                        "claim_id": "CLM-EXT-001",
                        "theorem_assumptions_checked": ["chi > 0"],
                        "theorem_parameters_checked": ["r_0"],
                        "proof_locations": [f"{manuscript_rel}:1"],
                        "uncovered_assumptions": [],
                        "uncovered_parameters": [],
                        "coverage_gaps": [],
                        "alignment_status": "aligned",
                        "notes": "Complete coverage.",
                    }
                ],
                "confidence": "high",
                "recommendation_ceiling": "minor_revision",
            }
        ),
        encoding="utf-8",
    )
    proof_redteam_path = review_dir / "PROOF-REDTEAM.md"
    proof_redteam_path.write_text(
        (
            "---\n"
            "status: passed\n"
            f"reviewer: {PROOF_AUDIT_REVIEWER}\n"
            "claim_ids:\n"
            "  - CLM-EXT-001\n"
            "proof_artifact_paths:\n"
            f"  - {manuscript_rel}\n"
            f"manuscript_path: {manuscript_rel}\n"
            f"manuscript_sha256: {manuscript_sha256}\n"
            "round: 1\n"
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
            f"| `r_0` | target radius | {manuscript_rel}:1 | covered | Carried through the argument. |\n"
            "### Hypothesis Coverage\n"
            "| Hypothesis | Proof Location | Status | Notes |\n"
            "| --- | --- | --- | --- |\n"
            f"| `H1` | {manuscript_rel}:1 | covered | Used in the positivity step. |\n"
            "### Quantifier / Domain Coverage\n"
            "| Obligation | Proof Location | Status | Notes |\n"
            "| --- | --- | --- | --- |\n"
            f"| `for every r_0 > 0` | {manuscript_rel}:1 | covered | No specialization introduced. |\n"
            "### Conclusion-Clause Coverage\n"
            "| Clause | Proof Location | Status | Notes |\n"
            "| --- | --- | --- | --- |\n"
            f"| annulus intersection holds | {manuscript_rel}:1 | covered | Final sentence states it. |\n"
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
    return manuscript_path, proof_redteam_path


def _write_managed_manuscript_review_anchor(project_root: Path, *, project_backed: bool) -> Path:
    manuscript_path = project_root / "GPD" / "publication" / "ising-bootstrap" / "manuscript" / "main.tex"
    manuscript_path.parent.mkdir(parents=True, exist_ok=True)
    manuscript_path.write_text(
        "\\documentclass{article}\n\\begin{document}\nManaged publication draft.\n\\end{document}\n",
        encoding="utf-8",
    )
    (manuscript_path.parent / "references.bib").write_text("@article{demo,title={Managed Demo}}\n", encoding="utf-8")
    manuscript_rel = "GPD/publication/ising-bootstrap/manuscript/main.tex"
    manuscript_sha256 = compute_sha256(manuscript_path)

    if project_backed:
        (project_root / "GPD" / "PROJECT.md").write_text("# Project\n", encoding="utf-8")
    review_dir = project_root / "GPD" / "publication" / "ising-bootstrap" / "review"
    review_dir.mkdir(parents=True, exist_ok=True)
    (review_dir / "CLAIMS.json").write_text(
        json.dumps(
            {
                "version": 1,
                "manuscript_path": manuscript_rel,
                "manuscript_sha256": manuscript_sha256,
                "claims": [
                    {
                        "claim_id": "CLM-MANAGED-001",
                        "claim_type": "main_result",
                        "claim_kind": "other",
                        "text": "The manuscript reports a managed publication result.",
                        "artifact_path": manuscript_rel,
                        "section": "Main Result",
                        "equation_refs": [],
                        "figure_refs": [],
                        "supporting_artifacts": [],
                        "theorem_assumptions": [],
                        "theorem_parameters": [],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (review_dir / "STAGE-math.json").write_text(
        json.dumps(
            {
                "version": 1,
                "round": 1,
                "stage_id": "math",
                "stage_kind": "math",
                "manuscript_path": manuscript_rel,
                "manuscript_sha256": manuscript_sha256,
                "claims_reviewed": [],
                "summary": "math review",
                "strengths": ["checked manuscript"],
                "findings": [],
                "proof_audits": [],
                "confidence": "high",
                "recommendation_ceiling": "minor_revision",
            }
        ),
        encoding="utf-8",
    )
    return manuscript_path


def _write_binary_pdf(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n"
        b"1 0 obj\n<< /Type /Catalog >>\nendobj\n"
        b"2 0 obj\n<< /Length 5 >>\nstream\n\x80\x81\xff\x00\xfe\nendstream\nendobj\n"
        b"trailer\n<< /Root 1 0 R >>\n%%EOF\n"
    )
    return path


def _fake_pdftotext_run(extracted_text: str):
    def _run(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str] | subprocess.CompletedProcess[bytes]:
        output_arg = next(
            (
                Path(str(argument))
                for argument in command[1:]
                if isinstance(argument, str) and argument not in {"-"} and str(argument).endswith(".txt")
            ),
            None,
        )
        if output_arg is not None:
            output_arg.parent.mkdir(parents=True, exist_ok=True)
            output_arg.write_text(extracted_text, encoding="utf-8")

        text_mode = bool(kwargs.get("text"))
        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout=extracted_text if text_mode else extracted_text.encode("utf-8"),
            stderr="" if text_mode else b"",
        )

    return _run


def _rewrite_claim_index_claim(path: Path, **claim_updates: object) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["claims"][0].update(claim_updates)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_phase_proof_review_bootstraps_manifest_and_turns_stale_after_edit(tmp_path: Path) -> None:
    phase_dir = tmp_path / "GPD" / "phases" / "01-proofs"
    phase_dir.mkdir(parents=True)
    summary_path = phase_dir / "01-SUMMARY.md"
    summary_path.write_text("# Summary\n", encoding="utf-8")
    verification_path = phase_dir / "01-VERIFICATION.md"
    verification_path.write_text("# Verification\n", encoding="utf-8")

    fresh = resolve_phase_proof_review_status(tmp_path, phase_dir, persist_manifest=True)

    assert fresh.state == "fresh"
    assert fresh.manifest_bootstrapped is True
    assert phase_proof_review_manifest_path(verification_path).exists()

    summary_path.write_text("# Summary\n\nUpdated theorem proof.\n", encoding="utf-8")

    stale = resolve_phase_proof_review_status(tmp_path, phase_dir)

    assert stale.state == "stale"
    assert stale.can_rely_on_prior_review is False
    assert summary_path in stale.changed_files


def test_manuscript_proof_review_bootstraps_manifest_and_turns_stale_after_edit(tmp_path: Path) -> None:
    manuscript_path = write_proof_review_package(tmp_path, theorem_bearing=False, review_report=False).manuscript_path

    fresh = resolve_manuscript_proof_review_status(tmp_path, manuscript_path, persist_manifest=True)

    assert fresh.state == "fresh"
    assert fresh.manifest_bootstrapped is True
    assert manuscript_proof_review_manifest_path(manuscript_path).exists()

    manuscript_path.write_text(
        "\\documentclass{article}\n\\begin{document}\nRevised proof.\n\\end{document}\n",
        encoding="utf-8",
    )

    stale = resolve_manuscript_proof_review_status(tmp_path, manuscript_path)

    assert stale.state == "stale"
    assert stale.can_rely_on_prior_review is False
    assert manuscript_path in stale.changed_files


def test_manuscript_proof_review_requires_proof_redteam_artifact_for_proof_bearing_manuscript(tmp_path: Path) -> None:
    manuscript_path = write_proof_review_package(
        tmp_path, theorem_bearing=True, review_report=False, proof_redteam_status=None
    ).manuscript_path

    status = resolve_manuscript_proof_review_status(tmp_path, manuscript_path)

    assert status.state == "missing_required_artifact"
    assert status.can_rely_on_prior_review is False
    assert status.anchor_artifact == tmp_path / "GPD" / "review" / "PROOF-REDTEAM.md"


def test_manuscript_theorem_claim_inventory_ignores_generic_claim_kind_without_theorem_markers(
    tmp_path: Path,
) -> None:
    manuscript_path = write_proof_review_package(tmp_path, theorem_bearing=False, review_report=False).manuscript_path
    claim_index_path = tmp_path / "GPD" / "review" / "CLAIMS.json"
    _rewrite_claim_index_claim(claim_index_path, claim_kind="claim")

    assert manuscript_has_theorem_bearing_claim_inventory(tmp_path, manuscript_path) is False
    assert manuscript_has_theorem_bearing_review_anchor(tmp_path, manuscript_path) is False
    assert manuscript_requires_theorem_bearing_review(tmp_path, manuscript_path) is False


def test_manuscript_theorem_claim_inventory_accepts_theorem_like_text_for_generic_claim_kind(
    tmp_path: Path,
) -> None:
    manuscript_path = write_proof_review_package(tmp_path, theorem_bearing=False, review_report=False).manuscript_path
    claim_index_path = tmp_path / "GPD" / "review" / "CLAIMS.json"
    _rewrite_claim_index_claim(
        claim_index_path,
        claim_kind="claim",
        text="For every r_0 > 0, the orbit intersects the target annulus.",
    )

    assert manuscript_has_theorem_bearing_claim_inventory(tmp_path, manuscript_path) is True
    assert manuscript_has_theorem_bearing_review_anchor(tmp_path, manuscript_path) is True
    assert manuscript_requires_theorem_bearing_review(tmp_path, manuscript_path) is True


def test_manuscript_theorem_claim_inventory_accepts_theorem_metadata_for_generic_claim_kind(
    tmp_path: Path,
) -> None:
    manuscript_path = write_proof_review_package(tmp_path, theorem_bearing=False, review_report=False).manuscript_path
    claim_index_path = tmp_path / "GPD" / "review" / "CLAIMS.json"
    _rewrite_claim_index_claim(
        claim_index_path,
        claim_kind="claim",
        theorem_parameters=["r_0"],
    )

    assert manuscript_has_theorem_bearing_claim_inventory(tmp_path, manuscript_path) is True
    assert manuscript_has_theorem_bearing_review_anchor(tmp_path, manuscript_path) is True
    assert manuscript_requires_theorem_bearing_review(tmp_path, manuscript_path) is True


def test_manuscript_theorem_language_scan_follows_nested_section_files(tmp_path: Path) -> None:
    manuscript_path = write_proof_review_package(tmp_path, theorem_bearing=False, review_report=False).manuscript_path
    manuscript_path.write_text(
        "\\documentclass{article}\n\\begin{document}\n\\input{sections/results}\n\\end{document}\n",
        encoding="utf-8",
    )
    section_path = tmp_path / "paper" / "sections" / "results.tex"
    section_path.parent.mkdir(parents=True, exist_ok=True)
    section_path.write_text(
        "\\begin{theorem}For every r_0 > 0, the orbit intersects the target annulus.\\end{theorem}\n"
        "\\begin{proof}Nested section proof.\\end{proof}\n",
        encoding="utf-8",
    )

    assert manuscript_path.name == f"{CANONICAL_MANUSCRIPT_STEM}.tex"
    assert manuscript_has_theorem_bearing_language(tmp_path, manuscript_path) is True


def test_manuscript_theorem_language_scan_reads_binary_pdf_companion_text(tmp_path: Path) -> None:
    (tmp_path / "GPD" / "review").mkdir(parents=True, exist_ok=True)
    manuscript_path = _write_binary_pdf(tmp_path / "paper" / f"{CANONICAL_MANUSCRIPT_STEM}.pdf")
    manuscript_path.with_suffix(".txt").write_text(
        "Theorem. For every r_0 > 0, the orbit intersects the target annulus.\n"
        "Proof. The companion text preserves the theorem statement.\n",
        encoding="utf-8",
    )

    assert manuscript_has_theorem_bearing_language(tmp_path, manuscript_path) is True


def test_manuscript_theorem_language_scan_uses_pypdf_for_binary_pdf(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "GPD" / "review").mkdir(parents=True, exist_ok=True)
    manuscript_path = _write_binary_pdf(tmp_path / "paper" / f"{CANONICAL_MANUSCRIPT_STEM}.pdf")
    extracted_text = (
        "Theorem. Every admissible orbit reaches the annulus.\nProof. The extractor preserves the proof body.\n"
    )

    class _FakePage:
        def __init__(self, text: str) -> None:
            self._text = text

        def extract_text(self) -> str:
            return self._text

    class _FakeReader:
        def __init__(self, text: str) -> None:
            self.pages = [_FakePage(text)]

    import sys as _sys
    import types as _types

    fake_pypdf = _types.ModuleType("pypdf")
    fake_pypdf.PdfReader = lambda _p: _FakeReader(extracted_text)  # type: ignore[attr-defined]
    monkeypatch.setitem(_sys.modules, "pypdf", fake_pypdf)

    assert manuscript_has_theorem_bearing_language(tmp_path, manuscript_path) is True


def test_manuscript_theorem_language_scan_returns_false_for_binary_pdf_without_text_support(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "GPD" / "review").mkdir(parents=True, exist_ok=True)
    manuscript_path = _write_binary_pdf(tmp_path / "paper" / f"{CANONICAL_MANUSCRIPT_STEM}.pdf")

    monkeypatch.setattr("gpd.mcp.paper.compiler.find_latex_compiler", lambda compiler: None)

    assert manuscript_has_theorem_bearing_language(tmp_path, manuscript_path) is False


def test_manuscript_theorem_language_scan_for_explicit_pdf_uses_text_surface_and_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manuscript_path = _write_binary_pdf(tmp_path / "standalone-review" / "draft.pdf")
    load_calls: list[Path] = []

    def _load_theorem_surface(path: Path) -> ArtifactTextSurface:
        load_calls.append(path)
        return ArtifactTextSurface(
            source_path=path,
            text=(
                "Theorem. For every r_0 > 0, the orbit intersects the target annulus.\n"
                "Proof. The explicit PDF review target stays on the text surface.\n"
            ),
            detail="generated text surface",
            surface_kind="generated",
        )

    monkeypatch.setattr("gpd.core.proof_review.load_artifact_text_surface", _load_theorem_surface)

    assert manuscript_has_theorem_bearing_language(tmp_path, manuscript_path) is True
    assert load_calls == [manuscript_path]

    def _raise_text_surface_error(path: Path) -> ArtifactTextSurface:
        load_calls.append(path)
        raise ArtifactTextError("generated PDF text surface unavailable")

    monkeypatch.setattr("gpd.core.proof_review.load_artifact_text_surface", _raise_text_surface_error)

    assert manuscript_has_theorem_bearing_language(tmp_path, manuscript_path) is False
    assert load_calls == [manuscript_path, manuscript_path]


def test_manuscript_proof_review_rejects_nonpassing_proof_redteam_artifact(tmp_path: Path) -> None:
    manuscript_path = write_proof_review_package(
        tmp_path, theorem_bearing=True, review_report=True, proof_redteam_status="gaps_found"
    ).manuscript_path

    status = resolve_manuscript_proof_review_status(tmp_path, manuscript_path)

    assert status.state == "open_required_artifact"
    assert status.can_rely_on_prior_review is False
    assert status.anchor_artifact == tmp_path / "GPD" / "review" / "PROOF-REDTEAM.md"


def test_manuscript_proof_review_rejects_noncanonical_reviewer(tmp_path: Path) -> None:
    manuscript_path = write_proof_review_package(
        tmp_path,
        theorem_bearing=True,
        review_report=True,
        proof_redteam_status="passed",
        proof_redteam_reviewer="someone-else",
    ).manuscript_path

    status = resolve_manuscript_proof_review_status(tmp_path, manuscript_path)

    assert status.state == "invalid_required_artifact"
    assert status.can_rely_on_prior_review is False
    assert PROOF_AUDIT_REVIEWER in status.detail


def test_manuscript_proof_review_rejects_mismatched_proof_redteam_snapshot(tmp_path: Path) -> None:
    manuscript_path = write_proof_review_package(
        tmp_path,
        theorem_bearing=True,
        review_report=True,
        proof_redteam_status="passed",
        proof_redteam_sha256="a" * 64,
    ).manuscript_path

    status = resolve_manuscript_proof_review_status(tmp_path, manuscript_path)

    assert status.state == "invalid_required_artifact"
    assert status.can_rely_on_prior_review is False
    assert "manuscript_sha256" in status.detail


def test_manuscript_proof_review_rejects_incomplete_proof_redteam_body(tmp_path: Path) -> None:
    package = write_proof_review_package(
        tmp_path, theorem_bearing=True, review_report=True, proof_redteam_status="passed"
    )
    manuscript_path = package.manuscript_path
    (tmp_path / "GPD" / "review" / "PROOF-REDTEAM.md").write_text(
        (
            "---\n"
            "status: passed\n"
            "reviewer: gpd-check-proof\n"
            "claim_ids:\n"
            "  - CLM-001\n"
            "proof_artifact_paths:\n"
            "  - paper/curvature_flow_bounds.tex\n"
            "manuscript_path: paper/curvature_flow_bounds.tex\n"
            f"manuscript_sha256: {package.manuscript_sha256}\n"
            "round: 1\n"
            "missing_parameter_symbols: []\n"
            "missing_hypothesis_ids: []\n"
            "coverage_gaps: []\n"
            "scope_status: matched\n"
            "quantifier_status: matched\n"
            "counterexample_status: none_found\n"
            "---\n\n"
            "# Proof Redteam\n"
        ),
        encoding="utf-8",
    )

    status = resolve_manuscript_proof_review_status(tmp_path, manuscript_path)

    assert status.state == "invalid_required_artifact"
    assert status.can_rely_on_prior_review is False
    assert "missing required sections" in status.detail


def test_manuscript_proof_review_rejects_passed_artifact_missing_structured_audit_fields(
    tmp_path: Path,
) -> None:
    package = write_proof_review_package(
        tmp_path, theorem_bearing=True, review_report=True, proof_redteam_status="passed"
    )
    proof_redteam_path = tmp_path / "GPD" / "review" / "PROOF-REDTEAM.md"
    proof_redteam_path.write_text(
        (
            "---\n"
            "status: passed\n"
            "reviewer: gpd-check-proof\n"
            "claim_ids:\n"
            "  - CLM-001\n"
            "proof_artifact_paths:\n"
            "  - paper/curvature_flow_bounds.tex\n"
            "manuscript_path: paper/curvature_flow_bounds.tex\n"
            f"manuscript_sha256: {package.manuscript_sha256}\n"
            "round: 1\n"
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
            "| `r_0` | target radius | paper/curvature_flow_bounds.tex:1 | covered |  |\n"
            "### Hypothesis Coverage\n"
            "| Hypothesis | Proof Location | Status | Notes |\n"
            "| --- | --- | --- | --- |\n"
            "| `H1` | paper/curvature_flow_bounds.tex:1 | covered |  |\n"
            "### Quantifier / Domain Coverage\n"
            "| Obligation | Proof Location | Status | Notes |\n"
            "| --- | --- | --- | --- |\n"
            "| `for every r_0 > 0` | paper/curvature_flow_bounds.tex:1 | covered |  |\n"
            "### Conclusion-Clause Coverage\n"
            "| Clause | Proof Location | Status | Notes |\n"
            "| --- | --- | --- | --- |\n"
            "| annulus intersection holds | paper/curvature_flow_bounds.tex:1 | covered |  |\n"
            "## Adversarial Probe\n"
            "- Probe type: dropped-parameter test\n"
            "- Result: The body looks complete, but the structured audit fields are missing.\n"
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

    status = resolve_manuscript_proof_review_status(tmp_path, package.manuscript_path)

    assert status.state == "invalid_required_artifact"
    assert status.can_rely_on_prior_review is False
    assert "missing_parameter_symbols" in status.detail


def test_manuscript_proof_review_trusts_structured_audit_over_prose_hints(tmp_path: Path) -> None:
    package = write_proof_review_package(
        tmp_path, theorem_bearing=True, review_report=True, proof_redteam_status="passed"
    )
    proof_redteam_path = tmp_path / "GPD" / "review" / "PROOF-REDTEAM.md"
    proof_redteam_path.write_text(
        (
            "---\n"
            "status: passed\n"
            "reviewer: gpd-check-proof\n"
            "claim_ids:\n"
            "  - CLM-001\n"
            "proof_artifact_paths:\n"
            "  - paper/curvature_flow_bounds.tex\n"
            "manuscript_path: paper/curvature_flow_bounds.tex\n"
            f"manuscript_sha256: {package.manuscript_sha256}\n"
            "round: 1\n"
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
            "| `r_0` | target radius | paper/curvature_flow_bounds.tex:1 | covered | Prose mentions a missing r_0-like case, but the structured audit is clean. |\n"
            "### Hypothesis Coverage\n"
            "| Hypothesis | Proof Location | Status | Notes |\n"
            "| --- | --- | --- | --- |\n"
            "| `H1` | paper/curvature_flow_bounds.tex:1 | covered |  |\n"
            "### Quantifier / Domain Coverage\n"
            "| Obligation | Proof Location | Status | Notes |\n"
            "| --- | --- | --- | --- |\n"
            "| `for every r_0 > 0` | paper/curvature_flow_bounds.tex:1 | covered |  |\n"
            "### Conclusion-Clause Coverage\n"
            "| Clause | Proof Location | Status | Notes |\n"
            "| --- | --- | --- | --- |\n"
            "| annulus intersection holds | paper/curvature_flow_bounds.tex:1 | covered |  |\n"
            "## Adversarial Probe\n"
            "- Probe type: dropped-parameter test\n"
            "- Result: The prose mentions a missing r_0-like special case, but the structured audit still records full coverage.\n"
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

    status = resolve_manuscript_proof_review_status(tmp_path, package.manuscript_path)

    assert status.state == "fresh"
    assert status.can_rely_on_prior_review is True


@pytest.mark.parametrize(
    ("field_name", "field_value", "expected_fragment"),
    [
        ("missing_parameter_symbols", ["r_0"], "missing_parameter_symbols"),
        ("missing_hypothesis_ids", ["H1"], "missing_hypothesis_ids"),
        ("coverage_gaps", ["Proof only establishes the centered case."], "coverage_gaps"),
        ("scope_status", "narrower_than_claim", "scope_status"),
        ("quantifier_status", "narrowed", "quantifier_status"),
        ("counterexample_status", "not_attempted", "counterexample_status"),
        ("counterexample_status", "counterexample_found", "counterexample_status"),
    ],
)
def test_manuscript_proof_review_rejects_passed_artifact_with_structured_gap(
    tmp_path: Path,
    field_name: str,
    field_value: object,
    expected_fragment: str,
) -> None:
    package = write_proof_review_package(
        tmp_path, theorem_bearing=True, review_report=True, proof_redteam_status="passed"
    )
    proof_redteam_path = tmp_path / "GPD" / "review" / "PROOF-REDTEAM.md"

    structured_fields = {
        "missing_parameter_symbols": [],
        "missing_hypothesis_ids": [],
        "coverage_gaps": [],
        "scope_status": "matched",
        "quantifier_status": "matched",
        "counterexample_status": "none_found",
    }
    structured_fields[field_name] = field_value
    proof_redteam_path.write_text(
        (
            "---\n"
            "status: passed\n"
            "reviewer: gpd-check-proof\n"
            "claim_ids:\n"
            "  - CLM-001\n"
            "proof_artifact_paths:\n"
            "  - paper/curvature_flow_bounds.tex\n"
            "manuscript_path: paper/curvature_flow_bounds.tex\n"
            f"manuscript_sha256: {package.manuscript_sha256}\n"
            "round: 1\n"
            f"missing_parameter_symbols: {structured_fields['missing_parameter_symbols']}\n"
            f"missing_hypothesis_ids: {structured_fields['missing_hypothesis_ids']}\n"
            f"coverage_gaps: {structured_fields['coverage_gaps']}\n"
            f"scope_status: {structured_fields['scope_status']}\n"
            f"quantifier_status: {structured_fields['quantifier_status']}\n"
            f"counterexample_status: {structured_fields['counterexample_status']}\n"
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
            "| `r_0` | target radius | paper/curvature_flow_bounds.tex:1 | covered |  |\n"
            "### Hypothesis Coverage\n"
            "| Hypothesis | Proof Location | Status | Notes |\n"
            "| --- | --- | --- | --- |\n"
            "| `H1` | paper/curvature_flow_bounds.tex:1 | covered |  |\n"
            "### Quantifier / Domain Coverage\n"
            "| Obligation | Proof Location | Status | Notes |\n"
            "| --- | --- | --- | --- |\n"
            "| `for every r_0 > 0` | paper/curvature_flow_bounds.tex:1 | covered |  |\n"
            "### Conclusion-Clause Coverage\n"
            "| Clause | Proof Location | Status | Notes |\n"
            "| --- | --- | --- | --- |\n"
            "| annulus intersection holds | paper/curvature_flow_bounds.tex:1 | covered |  |\n"
            "## Adversarial Probe\n"
            "- Probe type: dropped-parameter test\n"
            f"- Result: This artifact includes {expected_fragment}, which must block a passed status.\n"
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

    status = resolve_manuscript_proof_review_status(tmp_path, package.manuscript_path)

    assert status.state == "invalid_required_artifact"
    assert status.can_rely_on_prior_review is False
    assert expected_fragment in status.detail


def test_manuscript_proof_review_anchors_to_passed_proof_redteam_artifact(tmp_path: Path) -> None:
    manuscript_path = write_proof_review_package(
        tmp_path, theorem_bearing=True, review_report=True, proof_redteam_status="passed"
    ).manuscript_path

    status = resolve_manuscript_proof_review_status(tmp_path, manuscript_path, persist_manifest=True)

    assert status.state == "fresh"
    assert status.can_rely_on_prior_review is True
    assert status.anchor_artifact == tmp_path / "GPD" / "review" / "PROOF-REDTEAM.md"
    assert manuscript_proof_review_manifest_path(manuscript_path).exists()


def test_external_manuscript_proof_review_bootstraps_manifest_under_gpd_publication_root(tmp_path: Path) -> None:
    manuscript_path = _write_external_manuscript_review_anchor(tmp_path)

    manifest_path = manuscript_proof_review_manifest_path(manuscript_path, project_root=tmp_path)
    fresh = resolve_manuscript_proof_review_status(tmp_path, manuscript_path, persist_manifest=True)

    assert fresh.state == "fresh"
    assert fresh.manifest_bootstrapped is True
    assert fresh.manifest_path == manifest_path
    assert manifest_path.exists()
    assert manifest_path.is_relative_to(tmp_path / "GPD" / "publication")
    assert not (manuscript_path.parent / "PROOF-REVIEW-MANIFEST.json").exists()


def test_external_theorem_bearing_manuscript_proof_review_anchors_to_subject_owned_proof_redteam(
    tmp_path: Path,
) -> None:
    manuscript_path, proof_redteam_path = _write_external_theorem_bearing_review_anchor(tmp_path)

    status = resolve_manuscript_proof_review_status(tmp_path, manuscript_path)

    assert status.state == "fresh"
    assert status.can_rely_on_prior_review is True
    assert status.anchor_artifact == proof_redteam_path
    assert proof_redteam_path.is_relative_to(tmp_path / "GPD" / "publication")


def test_managed_publication_manuscript_proof_review_reuses_existing_subject_slug(tmp_path: Path) -> None:
    manuscript_path = _write_managed_manuscript_review_anchor(tmp_path, project_backed=True)

    manifest_path = manuscript_proof_review_manifest_path(manuscript_path, project_root=tmp_path)
    fresh = resolve_manuscript_proof_review_status(tmp_path, manuscript_path, persist_manifest=True)

    assert publication_subject_slug(tmp_path, manuscript_path) == "ising-bootstrap"
    assert manifest_path == (
        tmp_path / "GPD" / "publication" / "ising-bootstrap" / "proof-review" / "PROOF-REVIEW-MANIFEST.json"
    )
    assert fresh.state == "fresh"
    assert fresh.manifest_bootstrapped is True
    assert fresh.manifest_path == manifest_path
    assert manifest_path.exists()
    assert not (manuscript_path.parent / "PROOF-REVIEW-MANIFEST.json").exists()


def test_standalone_managed_publication_manuscript_proof_review_uses_subject_owned_review_roots(
    tmp_path: Path,
) -> None:
    manuscript_path = _write_managed_manuscript_review_anchor(tmp_path, project_backed=False)

    status = resolve_manuscript_proof_review_status(tmp_path, manuscript_path)

    assert status.state == "fresh"
    assert status.can_rely_on_prior_review is True
    assert status.anchor_artifact == tmp_path / "GPD" / "publication" / "ising-bootstrap" / "review" / "STAGE-math.json"


def test_manuscript_proof_review_uses_latest_matching_round_specific_proof_redteam(tmp_path: Path) -> None:
    manuscript_path = write_proof_review_package(
        tmp_path,
        theorem_bearing=True,
        review_report=True,
        proof_redteam_status="passed",
        round_number=1,
    ).manuscript_path
    write_proof_review_package(
        tmp_path,
        theorem_bearing=True,
        review_report=False,
        proof_redteam_status=None,
        round_number=2,
    )

    status = resolve_manuscript_proof_review_status(tmp_path, manuscript_path)

    assert status.state == "missing_required_artifact"
    assert status.can_rely_on_prior_review is False
    assert status.anchor_artifact == tmp_path / "GPD" / "review" / "PROOF-REDTEAM-R2.md"


def test_manuscript_proof_review_rejects_invalid_latest_round_anchor_without_falling_back(tmp_path: Path) -> None:
    manuscript_path = write_proof_review_package(
        tmp_path,
        theorem_bearing=True,
        review_report=True,
        proof_redteam_status="passed",
        round_number=1,
    ).manuscript_path
    write_proof_review_package(
        tmp_path,
        theorem_bearing=True,
        review_report=True,
        proof_redteam_status="passed",
        round_number=2,
    )
    (tmp_path / "GPD" / "review" / "CLAIMS-R2.json").write_text("{}", encoding="utf-8")

    status = resolve_manuscript_proof_review_status(tmp_path, manuscript_path)

    assert status.state == "invalid_required_artifact"
    assert status.can_rely_on_prior_review is False
    assert status.anchor_artifact == tmp_path / "GPD" / "review" / "STAGE-math-R2.json"
    assert "STAGE-math-R2.json" in status.detail


def test_manuscript_proof_review_rejects_unreadable_latest_stage_math_without_falling_back(tmp_path: Path) -> None:
    manuscript_path = write_proof_review_package(
        tmp_path,
        theorem_bearing=True,
        review_report=True,
        proof_redteam_status="passed",
        round_number=1,
    ).manuscript_path
    write_proof_review_package(
        tmp_path,
        theorem_bearing=True,
        review_report=True,
        proof_redteam_status="passed",
        round_number=2,
    )
    (tmp_path / "GPD" / "review" / "STAGE-math-R2.json").write_text("{not json", encoding="utf-8")

    status = resolve_manuscript_proof_review_status(tmp_path, manuscript_path)

    assert status.state == "invalid_required_artifact"
    assert status.can_rely_on_prior_review is False
    assert status.anchor_artifact == tmp_path / "GPD" / "review" / "STAGE-math-R2.json"
    assert "STAGE-math-R2.json" in status.detail


def test_manuscript_proof_review_turns_stale_after_bibliography_edit(tmp_path: Path) -> None:
    manuscript_path = write_proof_review_package(
        tmp_path, theorem_bearing=True, review_report=True, proof_redteam_status="passed"
    ).manuscript_path
    bibliography_path = tmp_path / "paper" / "references.bib"

    fresh = resolve_manuscript_proof_review_status(tmp_path, manuscript_path, persist_manifest=True)

    assert fresh.state == "fresh"

    bibliography_path.write_text("@article{demo,title={Updated Demo}}\n", encoding="utf-8")

    stale = resolve_manuscript_proof_review_status(tmp_path, manuscript_path)

    assert stale.state == "stale"
    assert stale.can_rely_on_prior_review is False
    assert bibliography_path in stale.changed_files


def test_manuscript_proof_review_turns_stale_after_proof_redteam_edit(tmp_path: Path) -> None:
    manuscript_path = write_proof_review_package(
        tmp_path, theorem_bearing=True, review_report=True, proof_redteam_status="passed"
    ).manuscript_path
    proof_redteam_path = tmp_path / "GPD" / "review" / "PROOF-REDTEAM.md"

    fresh = resolve_manuscript_proof_review_status(tmp_path, manuscript_path, persist_manifest=True)

    assert fresh.state == "fresh"

    proof_redteam_path.write_text(
        proof_redteam_path.read_text(encoding="utf-8") + "\n<!-- drift -->\n", encoding="utf-8"
    )

    stale = resolve_manuscript_proof_review_status(tmp_path, manuscript_path)

    assert stale.state == "stale"
    assert stale.can_rely_on_prior_review is False
    assert proof_redteam_path in stale.changed_files


def test_manuscript_proof_review_turns_stale_after_external_proof_artifact_edit(tmp_path: Path) -> None:
    manuscript_path = write_proof_review_package(
        tmp_path,
        theorem_bearing=True,
        review_report=True,
        proof_redteam_status="passed",
        proof_artifact_relpath="proofs/external-proof.tex",
    ).manuscript_path
    external_proof_path = tmp_path / "proofs" / "external-proof.tex"

    fresh = resolve_manuscript_proof_review_status(tmp_path, manuscript_path, persist_manifest=True)

    assert fresh.state == "fresh"
    assert external_proof_path in fresh.watched_files

    external_proof_path.write_text(
        "\\documentclass{article}\n\\begin{document}\nRevised external proof.\n\\end{document}\n",
        encoding="utf-8",
    )

    stale = resolve_manuscript_proof_review_status(tmp_path, manuscript_path)

    assert stale.state == "stale"
    assert stale.can_rely_on_prior_review is False
    assert external_proof_path in stale.changed_files
