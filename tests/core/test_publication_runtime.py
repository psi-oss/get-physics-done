from __future__ import annotations

from pathlib import Path

from gpd.core.publication_runtime import PublicationResponseArtifacts, PublicationReviewArtifacts


def test_publication_runtime_artifact_context_uses_project_relative_labels_with_external_fallback(
    tmp_path: Path,
) -> None:
    outside_path = tmp_path.parent / "external-proof.md"

    review_payload = PublicationReviewArtifacts(
        round_number=2,
        round_suffix="-R2",
        review_ledger=tmp_path / "GPD" / "review" / "REVIEW-LEDGER-R2.json",
        referee_decision=tmp_path / "GPD" / "review" / "REFEREE-DECISION-R2.json",
        referee_report_md=outside_path,
        state="complete",
    ).to_context_dict(tmp_path)

    response_payload = PublicationResponseArtifacts(
        round_number=2,
        round_suffix="-R2",
        author_response=tmp_path / "paper" / "AUTHOR-RESPONSE-R2.md",
        referee_response=outside_path,
        state="complete",
    ).to_context_dict(tmp_path)

    assert review_payload["review_ledger"] == "GPD/review/REVIEW-LEDGER-R2.json"
    assert review_payload["referee_decision"] == "GPD/review/REFEREE-DECISION-R2.json"
    assert review_payload["referee_report_md"] == outside_path.as_posix()
    assert response_payload["author_response"] == "paper/AUTHOR-RESPONSE-R2.md"
    assert response_payload["referee_response"] == outside_path.as_posix()
