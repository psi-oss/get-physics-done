from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from gpd.core.constants import KNOWLEDGE_DIR_NAME, KNOWLEDGE_REVIEWS_DIR_NAME, PLANNING_DIR_NAME
from gpd.core.knowledge_docs import KnowledgeReviewRecord


def _base_review_payload(*, approval_artifact_path: str) -> dict[str, object]:
    return {
        "reviewed_at": datetime(2026, 4, 7, 12, 0, tzinfo=timezone.utc),
        "review_round": 1,
        "reviewer_kind": "human",
        "reviewer_id": "gpd-reviewer",
        "decision": "approved",
        "summary": "Approved for downstream use",
        "approval_artifact_path": approval_artifact_path,
        "approval_artifact_sha256": "a" * 64,
        "reviewed_content_sha256": "b" * 64,
        "stale": False,
    }


def _canonical_review_path(knowledge_id: str) -> str:
    return f"{PLANNING_DIR_NAME}/{KNOWLEDGE_DIR_NAME}/{KNOWLEDGE_REVIEWS_DIR_NAME}/{knowledge_id}-R1-REVIEW.md"


def test_knowledge_review_record_rejects_non_review_paths() -> None:
    payload = _base_review_payload(
        approval_artifact_path=f"{PLANNING_DIR_NAME}/{KNOWLEDGE_DIR_NAME}/other/K-renormalization-group-fixed-points-R1-REVIEW.md"
    )

    with pytest.raises(ValidationError) as excinfo:
        KnowledgeReviewRecord(**payload)

    assert "approval_artifact_path" in str(excinfo.value)


def test_knowledge_review_record_accepts_canonical_review_path() -> None:
    payload = _base_review_payload(approval_artifact_path=_canonical_review_path("K-renormalization-group-fixed-points"))

    record = KnowledgeReviewRecord(**payload)

    assert record.approval_artifact_path == _canonical_review_path("K-renormalization-group-fixed-points")
