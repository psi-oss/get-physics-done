from __future__ import annotations

import json
from pathlib import Path

from gpd.core.manuscript_artifacts import resolve_explicit_publication_subject
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


def test_publication_runtime_snapshot_uses_the_matching_review_round_for_an_explicit_subject(
    tmp_path: Path,
) -> None:
    _write(tmp_path / "paper" / "main.tex", "\\documentclass{article}\\begin{document}Paper\\end{document}\n")
    _write(
        tmp_path / "paper" / "ARTIFACT-MANIFEST.json",
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
                        "path": "main.tex",
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
    _write(tmp_path / "draft" / "other.tex", "\\documentclass{article}\\begin{document}Other\\end{document}\n")

    review_dir = tmp_path / "GPD" / "review"
    review_dir.mkdir(parents=True)
    _write_review_round(review_dir, manuscript_path="paper/main.tex", round_number=2)
    _write_review_round(review_dir, manuscript_path="draft/other.tex", round_number=3)
    _write(review_dir / "AUTHOR-RESPONSE-R2.md", "# Author Response R2\n")
    _write(review_dir / "REFEREE_RESPONSE-R2.md", "# Referee Response R2\n")
    _write(review_dir / "AUTHOR-RESPONSE-R3.md", "# Author Response R3\n")
    _write(review_dir / "REFEREE_RESPONSE-R3.md", "# Referee Response R3\n")

    subject = resolve_explicit_publication_subject(tmp_path, "paper/main.tex")
    snapshot = resolve_publication_runtime_snapshot(tmp_path, publication_subject=subject)
    context = publication_runtime_snapshot_context(tmp_path, publication_subject=subject)

    assert snapshot.publication_subject.source == "explicit_target"
    assert snapshot.latest_review_artifacts is not None
    assert snapshot.latest_review_artifacts.round_number == 2
    assert snapshot.latest_response_artifacts is not None
    assert snapshot.latest_response_artifacts.round_number == 2
    assert context["publication_subject_source"] == "explicit_target"
    assert context["latest_review_round"] == 2
    assert context["latest_response_round"] == 2
    assert context["publication_subject"]["manuscript_entrypoint"] == "paper/main.tex"
