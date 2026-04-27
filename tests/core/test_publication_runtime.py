from __future__ import annotations

import json
from pathlib import Path

from gpd.core.manuscript_artifacts import resolve_explicit_publication_subject
from gpd.core.publication_rounds import (
    publication_review_round_path_maps,
    resolve_latest_publication_review_round_artifacts,
)
from gpd.core.publication_runtime import publication_runtime_snapshot_context, resolve_publication_runtime_snapshot
from gpd.core.referee_policy import RefereeDecisionInput
from gpd.mcp.paper.models import ReviewConfidence, ReviewLedger, ReviewRecommendation
from gpd.mcp.paper.review_artifacts import write_referee_decision, write_review_ledger


def _write(path: Path, content: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_review_round(review_dir: Path, *, manuscript_path: str, round_number: int) -> None:
    round_suffix = "" if round_number <= 1 else f"-R{round_number}"
    write_review_ledger(
        ReviewLedger(round=round_number, manuscript_path=manuscript_path, issues=[]),
        review_dir / f"REVIEW-LEDGER{round_suffix}.json",
    )
    write_referee_decision(
        RefereeDecisionInput(
            manuscript_path=manuscript_path,
            final_recommendation=ReviewRecommendation.minor_revision,
            final_confidence=ReviewConfidence.medium,
        ),
        review_dir / f"REFEREE-DECISION{round_suffix}.json",
    )


def _response_metadata(
    *,
    manuscript_path: str,
    round_number: int,
    round_suffix: str,
    review_dir: Path | None = None,
    project_root: Path | None = None,
) -> str:
    review_ledger = f"REVIEW-LEDGER{round_suffix}.json"
    referee_decision = f"REFEREE-DECISION{round_suffix}.json"
    if review_dir is not None and project_root is not None:
        review_ledger_path = review_dir / review_ledger
        referee_decision_path = review_dir / referee_decision
        review_ledger = review_ledger_path.relative_to(project_root).as_posix()
        referee_decision = referee_decision_path.relative_to(project_root).as_posix()
    return (
        "---\n"
        f"response_to: REFEREE-REPORT{round_suffix}.md\n"
        f"round: {round_number}\n"
        f"manuscript_path: {manuscript_path}\n"
        f"review_ledger: {review_ledger}\n"
        f"referee_decision: {referee_decision}\n"
        "---\n\n"
    )


def _write_response_pair(
    publication_root: Path,
    review_dir: Path,
    *,
    manuscript_path: str,
    round_number: int,
    project_root: Path,
    author_root: Path | None = None,
) -> None:
    round_suffix = "" if round_number <= 1 else f"-R{round_number}"
    metadata = _response_metadata(
        manuscript_path=manuscript_path,
        round_number=round_number,
        round_suffix=round_suffix,
        review_dir=review_dir,
        project_root=project_root,
    )
    _write((author_root or publication_root) / f"AUTHOR-RESPONSE{round_suffix}.md", metadata + "# Author Response\n")
    _write(review_dir / f"REFEREE_RESPONSE{round_suffix}.md", metadata + "# Referee Response\n")


def _write_artifact_manifest(manuscript_root: Path, entrypoint_name: str) -> None:
    _write(
        manuscript_root / "ARTIFACT-MANIFEST.json",
        json.dumps(
            {
                "version": 1,
                "paper_title": "Main Paper",
                "journal": "prl",
                "created_at": "2026-04-02T00:00:00+00:00",
                "artifacts": [
                    {
                        "artifact_id": "tex-paper",
                        "category": "tex",
                        "path": entrypoint_name,
                        "sha256": "0" * 64,
                        "produced_by": "test",
                        "sources": [],
                        "metadata": {},
                    }
                ],
            },
            indent=2,
        )
        + "\n",
    )


def _write_bibliography_audit(manuscript_root: Path) -> None:
    _write(
        manuscript_root / "BIBLIOGRAPHY-AUDIT.json",
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
                        "key": "benchmark2024",
                        "source_type": "paper",
                        "reference_id": "ref-benchmark",
                        "title": "Benchmark Paper",
                        "resolution_status": "provided",
                        "verification_status": "verified",
                        "verification_sources": ["manual"],
                        "canonical_identifiers": ["doi:10.1000/example"],
                        "missing_core_fields": [],
                        "enriched_fields": [],
                        "warnings": [],
                        "errors": [],
                    }
                ],
            },
            indent=2,
        )
        + "\n",
    )


def test_publication_round_helpers_index_round_suffixed_artifacts(tmp_path: Path) -> None:
    review_dir = tmp_path / "GPD" / "review"
    _write(review_dir / "REVIEW-LEDGER.json", "{}\n")
    _write(review_dir / "REFEREE-DECISION-R2.json", "{}\n")
    _write(review_dir / "REVIEW-LEDGER-R3.json", "{}\n")

    review_ledgers, referee_decisions = publication_review_round_path_maps(tmp_path)
    latest = resolve_latest_publication_review_round_artifacts(tmp_path)

    assert review_ledgers == {
        1: review_dir / "REVIEW-LEDGER.json",
        3: review_dir / "REVIEW-LEDGER-R3.json",
    }
    assert referee_decisions == {2: review_dir / "REFEREE-DECISION-R2.json"}
    assert latest is not None
    assert latest.round_number == 3
    assert latest.round_suffix == "-R3"
    assert latest.review_ledger == review_dir / "REVIEW-LEDGER-R3.json"
    assert latest.referee_decision is None


def test_publication_runtime_snapshot_uses_the_matching_review_round_for_an_explicit_subject(
    tmp_path: Path,
) -> None:
    _write(tmp_path / "paper" / "main.tex", "\\documentclass{article}\\begin{document}Paper\\end{document}\n")
    _write_artifact_manifest(tmp_path / "paper", "main.tex")
    _write(tmp_path / "draft" / "other.tex", "\\documentclass{article}\\begin{document}Other\\end{document}\n")

    review_dir = tmp_path / "GPD" / "review"
    planning_dir = tmp_path / "GPD"
    review_dir.mkdir(parents=True)
    _write_review_round(review_dir, manuscript_path="paper/main.tex", round_number=2)
    _write_review_round(review_dir, manuscript_path="draft/other.tex", round_number=3)
    _write(planning_dir / "REFEREE-REPORT-R2.md", "# Referee Report R2\n")
    _write(planning_dir / "REFEREE-REPORT-R2.tex", "\\section*{Referee Report R2}\n")
    _write_response_pair(
        planning_dir,
        review_dir,
        manuscript_path="paper/main.tex",
        round_number=2,
        project_root=tmp_path,
    )
    _write(review_dir / "REFEREE-REPORT-R3.md", "# Legacy Referee Report R3\n")
    _write(review_dir / "AUTHOR-RESPONSE-R3.md", "# Legacy Author Response R3\n")
    _write(review_dir / "REFEREE_RESPONSE-R3.md", "# Referee Response R3\n")

    subject = resolve_explicit_publication_subject(tmp_path, "paper/main.tex")
    snapshot = resolve_publication_runtime_snapshot(tmp_path, publication_subject=subject)
    context = publication_runtime_snapshot_context(tmp_path, publication_subject=subject)

    assert snapshot.publication_subject.source == "explicit_target"
    assert snapshot.latest_review_artifacts is not None
    assert snapshot.latest_review_artifacts.round_number == 2
    assert snapshot.latest_review_artifacts.referee_report_md == planning_dir / "REFEREE-REPORT-R2.md"
    assert snapshot.latest_review_artifacts.referee_report_tex == planning_dir / "REFEREE-REPORT-R2.tex"
    assert snapshot.latest_response_artifacts is not None
    assert snapshot.latest_response_artifacts.round_number == 2
    assert snapshot.latest_response_artifacts.author_response == planning_dir / "AUTHOR-RESPONSE-R2.md"
    assert snapshot.latest_response_artifacts.referee_response == review_dir / "REFEREE_RESPONSE-R2.md"
    assert context["publication_subject_source"] == "explicit_target"
    assert context["latest_review_round"] == 2
    assert context["latest_response_round"] == 2
    assert context["latest_referee_report_md"] == "GPD/REFEREE-REPORT-R2.md"
    assert context["latest_author_response"] == "GPD/AUTHOR-RESPONSE-R2.md"
    assert context["publication_subject"]["manuscript_entrypoint"] == "paper/main.tex"


def test_publication_runtime_marks_review_round_invalid_when_ledger_content_round_disagrees(
    tmp_path: Path,
) -> None:
    _write(tmp_path / "paper" / "main.tex", "\\documentclass{article}\\begin{document}Paper\\end{document}\n")
    _write_artifact_manifest(tmp_path / "paper", "main.tex")
    review_dir = tmp_path / "GPD" / "review"
    review_dir.mkdir(parents=True)
    write_review_ledger(
        ReviewLedger(round=1, manuscript_path="paper/main.tex", issues=[]),
        review_dir / "REVIEW-LEDGER-R2.json",
    )
    write_referee_decision(
        RefereeDecisionInput(
            manuscript_path="paper/main.tex",
            final_recommendation=ReviewRecommendation.minor_revision,
            final_confidence=ReviewConfidence.medium,
        ),
        review_dir / "REFEREE-DECISION-R2.json",
    )

    subject = resolve_explicit_publication_subject(tmp_path, "paper/main.tex")
    snapshot = resolve_publication_runtime_snapshot(tmp_path, publication_subject=subject)

    assert snapshot.latest_review_artifacts is not None
    assert snapshot.latest_review_artifacts.round_number == 2
    assert snapshot.latest_review_artifacts.state == "invalid"
    assert "review ledger round 1 does not match review artifact round 2" in snapshot.latest_review_artifacts.detail


def test_publication_runtime_does_not_fall_back_past_malformed_latest_review_round(
    tmp_path: Path,
) -> None:
    _write(tmp_path / "paper" / "main.tex", "\\documentclass{article}\\begin{document}Paper\\end{document}\n")
    _write_artifact_manifest(tmp_path / "paper", "main.tex")
    review_dir = tmp_path / "GPD" / "review"
    _write_review_round(review_dir, manuscript_path="paper/main.tex", round_number=2)
    _write(review_dir / "REVIEW-LEDGER-R3.json", "{malformed json")

    subject = resolve_explicit_publication_subject(tmp_path, "paper/main.tex")
    snapshot = resolve_publication_runtime_snapshot(tmp_path, publication_subject=subject)

    assert snapshot.latest_review_artifacts is not None
    assert snapshot.latest_review_artifacts.round_number == 3
    assert snapshot.latest_review_artifacts.complete is False
    assert snapshot.latest_review_artifacts.state == "invalid"
    assert "review ledger could not be loaded" in snapshot.latest_review_artifacts.detail


def test_publication_runtime_reference_status_uses_canonical_subject_fields_for_invalid_explicit_target(
    tmp_path: Path,
) -> None:
    manuscript_root = tmp_path / "submission"
    manuscript_root.mkdir()
    _write_bibliography_audit(manuscript_root)

    snapshot = resolve_publication_runtime_snapshot(tmp_path, subject="submission/missing.tex")
    context = publication_runtime_snapshot_context(tmp_path, subject="submission/missing.tex")

    status = snapshot.manuscript_reference_status
    assert status.manuscript_root == "submission"
    assert status.bibliography_audit_path == "submission/BIBLIOGRAPHY-AUDIT.json"
    assert status.subject_resolution_status == "invalid"
    assert status.subject_resolution_detail == "missing explicit manuscript target ./submission/missing.tex"
    assert [record.reference_id for record in status.reference_status] == ["ref-benchmark"]
    assert context["manuscript_reference_subject_status"] == "invalid"
    assert (
        context["manuscript_reference_subject_detail"] == "missing explicit manuscript target ./submission/missing.tex"
    )


def test_publication_runtime_invalid_explicit_target_does_not_fall_back_to_current_project_manuscript(
    tmp_path: Path,
) -> None:
    _write(tmp_path / "paper" / "main.tex", "\\documentclass{article}\\begin{document}Paper\\end{document}\n")
    _write_artifact_manifest(tmp_path / "paper", "main.tex")
    _write_bibliography_audit(tmp_path / "paper")
    submission = tmp_path / "submission"
    submission.mkdir()
    _write_bibliography_audit(submission)

    snapshot = resolve_publication_runtime_snapshot(tmp_path, subject="submission/missing.tex")

    status = snapshot.manuscript_reference_status
    assert status.manuscript_root == "submission"
    assert status.bibliography_audit_path == "submission/BIBLIOGRAPHY-AUDIT.json"
    assert status.subject_resolution_status == "invalid"
    assert [record.manuscript_root for record in status.reference_status] == ["submission"]


def test_publication_runtime_snapshot_accepts_legacy_review_dir_report_and_author_response_during_migration(
    tmp_path: Path,
) -> None:
    _write(tmp_path / "paper" / "main.tex", "\\documentclass{article}\\begin{document}Paper\\end{document}\n")
    _write_artifact_manifest(tmp_path / "paper", "main.tex")

    review_dir = tmp_path / "GPD" / "review"
    review_dir.mkdir(parents=True)
    _write_review_round(review_dir, manuscript_path="paper/main.tex", round_number=2)
    _write(review_dir / "REFEREE-REPORT-R2.md", "# Legacy Referee Report R2\n")
    _write(review_dir / "REFEREE-REPORT-R2.tex", "\\section*{Legacy Referee Report R2}\n")
    _write_response_pair(
        tmp_path / "GPD",
        review_dir,
        manuscript_path="paper/main.tex",
        round_number=2,
        project_root=tmp_path,
        author_root=review_dir,
    )

    subject = resolve_explicit_publication_subject(tmp_path, "paper/main.tex")
    snapshot = resolve_publication_runtime_snapshot(tmp_path, publication_subject=subject)

    assert snapshot.latest_review_artifacts is not None
    assert snapshot.latest_review_artifacts.referee_report_md == review_dir / "REFEREE-REPORT-R2.md"
    assert snapshot.latest_review_artifacts.referee_report_tex == review_dir / "REFEREE-REPORT-R2.tex"
    assert snapshot.latest_response_artifacts is not None
    assert snapshot.latest_response_artifacts.author_response == review_dir / "AUTHOR-RESPONSE-R2.md"
    assert snapshot.latest_response_artifacts.referee_response == review_dir / "REFEREE_RESPONSE-R2.md"


def test_publication_runtime_keeps_default_project_response_files_metadata_optional(tmp_path: Path) -> None:
    _write(tmp_path / "GPD" / "PROJECT.md", "# Project\n")
    _write(tmp_path / "paper" / "main.tex", "\\documentclass{article}\\begin{document}Paper\\end{document}\n")
    _write_artifact_manifest(tmp_path / "paper", "main.tex")

    review_dir = tmp_path / "GPD" / "review"
    _write_review_round(review_dir, manuscript_path="paper/main.tex", round_number=2)
    _write(tmp_path / "GPD" / "AUTHOR-RESPONSE-R2.md", "# Author Response R2\n")
    _write(review_dir / "REFEREE_RESPONSE-R2.md", "# Referee Response R2\n")

    snapshot = resolve_publication_runtime_snapshot(tmp_path)

    assert snapshot.publication_subject.source == "current_project"
    assert snapshot.latest_response_artifacts is not None
    assert snapshot.latest_response_artifacts.complete is True
    assert snapshot.latest_response_artifacts.state == "complete"


def test_publication_runtime_snapshot_uses_subject_owned_roots_for_explicit_external_subject(
    tmp_path: Path,
) -> None:
    manuscript_root = tmp_path / "submission"
    _write(manuscript_root / "external-subject.tex", "\\documentclass{article}\\begin{document}Paper\\end{document}\n")
    _write_artifact_manifest(manuscript_root, "external-subject.tex")

    subject = resolve_explicit_publication_subject(tmp_path, "submission/external-subject.tex")
    assert subject.publication_subject_slug is not None

    publication_root = tmp_path / "GPD" / "publication" / subject.publication_subject_slug
    review_dir = publication_root / "review"
    review_dir.mkdir(parents=True)
    _write_review_round(review_dir, manuscript_path="submission/external-subject.tex", round_number=2)
    _write(publication_root / "REFEREE-REPORT-R2.md", "# Referee Report R2\n")
    _write(publication_root / "REFEREE-REPORT-R2.tex", "\\section*{Referee Report R2}\n")
    _write_response_pair(
        publication_root,
        review_dir,
        manuscript_path="submission/external-subject.tex",
        round_number=2,
        project_root=tmp_path,
    )
    _write(review_dir / "PROOF-REDTEAM-R2.md", "# Proof Redteam R2\n")

    global_review_dir = tmp_path / "GPD" / "review"
    global_review_dir.mkdir(parents=True, exist_ok=True)
    _write_review_round(global_review_dir, manuscript_path="submission/external-subject.tex", round_number=4)
    _write(tmp_path / "GPD" / "REFEREE-REPORT-R4.md", "# Referee Report R4\n")
    _write(tmp_path / "GPD" / "AUTHOR-RESPONSE-R4.md", "# Author Response R4\n")
    _write(global_review_dir / "REFEREE_RESPONSE-R4.md", "# Referee Response R4\n")

    snapshot = resolve_publication_runtime_snapshot(tmp_path, publication_subject=subject)
    context = publication_runtime_snapshot_context(tmp_path, publication_subject=subject)

    assert snapshot.latest_review_artifacts is not None
    assert snapshot.latest_review_artifacts.round_number == 2
    assert snapshot.latest_review_artifacts.review_ledger == review_dir / "REVIEW-LEDGER-R2.json"
    assert snapshot.latest_review_artifacts.referee_report_md == publication_root / "REFEREE-REPORT-R2.md"
    assert snapshot.latest_review_artifacts.referee_report_tex == publication_root / "REFEREE-REPORT-R2.tex"
    assert snapshot.latest_review_artifacts.proof_redteam == review_dir / "PROOF-REDTEAM-R2.md"
    assert snapshot.latest_response_artifacts is not None
    assert snapshot.latest_response_artifacts.round_number == 2
    assert snapshot.latest_response_artifacts.author_response == publication_root / "AUTHOR-RESPONSE-R2.md"
    assert snapshot.latest_response_artifacts.referee_response == review_dir / "REFEREE_RESPONSE-R2.md"
    assert context["latest_referee_report_md"] == (
        f"GPD/publication/{subject.publication_subject_slug}/REFEREE-REPORT-R2.md"
    )
    assert context["latest_author_response"] == (
        f"GPD/publication/{subject.publication_subject_slug}/AUTHOR-RESPONSE-R2.md"
    )
    assert context["latest_referee_response"] == (
        f"GPD/publication/{subject.publication_subject_slug}/review/REFEREE_RESPONSE-R2.md"
    )


def test_publication_runtime_snapshot_reuses_managed_publication_subject_slug_for_manuscript_lane(
    tmp_path: Path,
) -> None:
    _write(tmp_path / "GPD" / "PROJECT.md", "# Project\n")
    manuscript_root = tmp_path / "GPD" / "publication" / "ising-bootstrap" / "manuscript"
    _write(manuscript_root / "main.tex", "\\documentclass{article}\\begin{document}Paper\\end{document}\n")
    _write_artifact_manifest(manuscript_root, "main.tex")
    _write(manuscript_root / "BIBLIOGRAPHY-AUDIT.json", "{}\n")
    _write(manuscript_root / "reproducibility-manifest.json", "{}\n")

    publication_root = tmp_path / "GPD" / "publication" / "ising-bootstrap"
    review_dir = publication_root / "review"
    review_dir.mkdir(parents=True)
    _write_review_round(
        review_dir,
        manuscript_path="GPD/publication/ising-bootstrap/manuscript/main.tex",
        round_number=2,
    )
    _write(publication_root / "REFEREE-REPORT-R2.md", "# Referee Report R2\n")
    _write(publication_root / "REFEREE-REPORT-R2.tex", "\\section*{Referee Report R2}\n")
    _write_response_pair(
        publication_root,
        review_dir,
        manuscript_path="GPD/publication/ising-bootstrap/manuscript/main.tex",
        round_number=2,
        project_root=tmp_path,
    )

    stale_global_review_dir = tmp_path / "GPD" / "review"
    stale_global_review_dir.mkdir(parents=True)
    _write_review_round(
        stale_global_review_dir,
        manuscript_path="GPD/publication/ising-bootstrap/manuscript/main.tex",
        round_number=4,
    )

    subject = resolve_explicit_publication_subject(tmp_path, "GPD/publication/ising-bootstrap/manuscript/main.tex")
    snapshot = resolve_publication_runtime_snapshot(tmp_path, publication_subject=subject)
    context = publication_runtime_snapshot_context(tmp_path, publication_subject=subject)

    assert snapshot.publication_subject.artifact_base == manuscript_root
    assert snapshot.latest_review_artifacts is not None
    assert snapshot.latest_review_artifacts.round_number == 2
    assert snapshot.latest_review_artifacts.review_ledger == review_dir / "REVIEW-LEDGER-R2.json"
    assert snapshot.latest_response_artifacts is not None
    assert context["publication_subject_slug"] == "ising-bootstrap"
    assert context["publication_artifact_base"] == "GPD/publication/ising-bootstrap/manuscript"
    assert context["publication_lineage_mode"] == "subject_owned"
    assert context["publication_lineage_root"] == "GPD/publication/ising-bootstrap"
    assert context["publication_lineage_review_dir"] == "GPD/publication/ising-bootstrap/review"
    assert context["publication_subject"]["artifact_base"] == "GPD/publication/ising-bootstrap/manuscript"
    assert context["publication_subject"]["publication_root"] == "GPD/publication/ising-bootstrap"
    assert context["publication_subject"]["review_dir"] == "GPD/publication/ising-bootstrap/review"
    assert (
        context["publication_subject"]["manuscript_entrypoint"] == "GPD/publication/ising-bootstrap/manuscript/main.tex"
    )


def test_publication_runtime_snapshot_uses_subject_owned_review_roots_for_standalone_managed_lane(
    tmp_path: Path,
) -> None:
    manuscript_root = tmp_path / "GPD" / "publication" / "ising-bootstrap" / "manuscript"
    _write(manuscript_root / "main.tex", "\\documentclass{article}\\begin{document}Paper\\end{document}\n")
    _write_artifact_manifest(manuscript_root, "main.tex")
    _write(manuscript_root / "BIBLIOGRAPHY-AUDIT.json", "{}\n")
    _write(manuscript_root / "reproducibility-manifest.json", "{}\n")

    publication_root = tmp_path / "GPD" / "publication" / "ising-bootstrap"
    review_dir = publication_root / "review"
    review_dir.mkdir(parents=True)
    _write_review_round(
        review_dir,
        manuscript_path="GPD/publication/ising-bootstrap/manuscript/main.tex",
        round_number=2,
    )
    _write(publication_root / "REFEREE-REPORT-R2.md", "# Referee Report R2\n")
    _write(publication_root / "REFEREE-REPORT-R2.tex", "\\section*{Referee Report R2}\n")
    _write_response_pair(
        publication_root,
        review_dir,
        manuscript_path="GPD/publication/ising-bootstrap/manuscript/main.tex",
        round_number=2,
        project_root=tmp_path,
    )

    global_review_dir = tmp_path / "GPD" / "review"
    global_review_dir.mkdir(parents=True, exist_ok=True)
    _write_review_round(
        global_review_dir,
        manuscript_path="GPD/publication/ising-bootstrap/manuscript/main.tex",
        round_number=4,
    )
    _write(tmp_path / "GPD" / "REFEREE-REPORT-R4.md", "# Referee Report R4\n")
    _write(tmp_path / "GPD" / "AUTHOR-RESPONSE-R4.md", "# Author Response R4\n")
    _write(global_review_dir / "REFEREE_RESPONSE-R4.md", "# Referee Response R4\n")

    subject = resolve_explicit_publication_subject(tmp_path, "GPD/publication/ising-bootstrap/manuscript/main.tex")
    snapshot = resolve_publication_runtime_snapshot(tmp_path, publication_subject=subject)
    context = publication_runtime_snapshot_context(tmp_path, publication_subject=subject)

    assert snapshot.latest_review_artifacts is not None
    assert snapshot.latest_review_artifacts.round_number == 2
    assert snapshot.latest_review_artifacts.review_ledger == review_dir / "REVIEW-LEDGER-R2.json"
    assert snapshot.latest_review_artifacts.referee_report_md == publication_root / "REFEREE-REPORT-R2.md"
    assert snapshot.latest_response_artifacts is not None
    assert snapshot.latest_response_artifacts.round_number == 2
    assert snapshot.latest_response_artifacts.author_response == publication_root / "AUTHOR-RESPONSE-R2.md"
    assert snapshot.latest_response_artifacts.referee_response == review_dir / "REFEREE_RESPONSE-R2.md"
    assert context["publication_lineage_mode"] == "subject_owned"
    assert context["publication_lineage_root"] == "GPD/publication/ising-bootstrap"
    assert context["publication_lineage_review_dir"] == "GPD/publication/ising-bootstrap/review"
    assert context["latest_referee_report_md"] == "GPD/publication/ising-bootstrap/REFEREE-REPORT-R2.md"
    assert context["latest_author_response"] == "GPD/publication/ising-bootstrap/AUTHOR-RESPONSE-R2.md"


def test_publication_runtime_rejects_unbound_same_round_response_for_explicit_subject(
    tmp_path: Path,
) -> None:
    manuscript_root = tmp_path / "submission"
    _write(manuscript_root / "external-subject.tex", "\\documentclass{article}\\begin{document}Paper\\end{document}\n")
    _write_artifact_manifest(manuscript_root, "external-subject.tex")

    subject = resolve_explicit_publication_subject(tmp_path, "submission/external-subject.tex")
    assert subject.publication_subject_slug is not None
    publication_root = tmp_path / "GPD" / "publication" / subject.publication_subject_slug
    review_dir = publication_root / "review"
    _write_review_round(review_dir, manuscript_path="submission/external-subject.tex", round_number=2)
    _write(publication_root / "AUTHOR-RESPONSE-R2.md", "# Author Response R2\n")
    _write(review_dir / "REFEREE_RESPONSE-R2.md", "# Referee Response R2\n")

    snapshot = resolve_publication_runtime_snapshot(tmp_path, publication_subject=subject)

    assert snapshot.latest_response_artifacts is not None
    assert snapshot.latest_response_artifacts.round_number == 2
    assert snapshot.latest_response_artifacts.complete is False
    assert snapshot.latest_response_artifacts.state == "unbound"
    assert "no response frontmatter binding" in snapshot.latest_response_artifacts.detail


def test_publication_runtime_rejects_mismatched_same_round_response_metadata(
    tmp_path: Path,
) -> None:
    manuscript_root = tmp_path / "submission"
    _write(manuscript_root / "external-subject.tex", "\\documentclass{article}\\begin{document}Paper\\end{document}\n")
    _write_artifact_manifest(manuscript_root, "external-subject.tex")

    subject = resolve_explicit_publication_subject(tmp_path, "submission/external-subject.tex")
    assert subject.publication_subject_slug is not None
    publication_root = tmp_path / "GPD" / "publication" / subject.publication_subject_slug
    review_dir = publication_root / "review"
    _write_review_round(review_dir, manuscript_path="submission/external-subject.tex", round_number=2)
    stale_metadata = _response_metadata(
        manuscript_path="submission/old-subject.tex",
        round_number=2,
        round_suffix="-R2",
        review_dir=review_dir,
        project_root=tmp_path,
    )
    _write(publication_root / "AUTHOR-RESPONSE-R2.md", stale_metadata + "# Author Response R2\n")
    _write(review_dir / "REFEREE_RESPONSE-R2.md", stale_metadata + "# Referee Response R2\n")

    snapshot = resolve_publication_runtime_snapshot(tmp_path, publication_subject=subject)

    assert snapshot.latest_response_artifacts is not None
    assert snapshot.latest_response_artifacts.complete is False
    assert snapshot.latest_response_artifacts.state == "mismatched"
    assert "manuscript_path does not match the active manuscript" in snapshot.latest_response_artifacts.detail
