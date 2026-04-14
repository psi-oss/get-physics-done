"""Direct strict-parser regressions for knowledge-doc path validation."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from gpd.core.knowledge_docs import parse_knowledge_doc_data_strict

_SOURCE_PATH = Path("K-strict-parser-paths.md")


def _knowledge_doc_data(
    *,
    source_artifact: str = "GPD/source-artifacts/reference.pdf",
    approval_artifact_path: str = "GPD/knowledge/reviews/K-strict-parser-paths-R1-REVIEW.md",
    status: str = "draft",
) -> dict[str, object]:
    data: dict[str, object] = {
        "knowledge_schema_version": 1,
        "knowledge_id": "K-strict-parser-paths",
        "title": "Strict Parser Path Validation",
        "topic": "knowledge-doc-path-validation",
        "status": status,
        "created_at": "2026-04-07T12:00:00Z",
        "updated_at": "2026-04-07T12:00:00Z",
        "sources": [
            {
                "source_id": "source-main",
                "kind": "paper",
                "locator": "Doe et al., 2026",
                "title": "Strict Parser Path Validation",
                "why_it_matters": "Provides the canonical provenance anchor for the doc",
                "source_artifacts": [source_artifact],
            }
        ],
        "coverage_summary": {
            "covered_topics": ["strict validation"],
            "excluded_topics": ["migration semantics"],
            "open_gaps": ["none"],
        },
    }
    if status == "stable":
        data["review"] = {
            "reviewed_at": "2026-04-07T12:00:00Z",
            "review_round": 1,
            "reviewer_kind": "human",
            "reviewer_id": "gpd-reviewer",
            "decision": "approved",
            "summary": "Approved after strict parser review",
            "approval_artifact_path": approval_artifact_path,
            "approval_artifact_sha256": "a" * 64,
            "reviewed_content_sha256": "b" * 64,
            "stale": False,
        }
    return data


@pytest.mark.parametrize(
    "artifact_path",
    [
        pytest.param("C:/tmp/reference.pdf", id="windows-drive-letter"),
        pytest.param(r"\\server\share\reference.pdf", id="windows-unc"),
    ],
)
def test_parse_knowledge_doc_data_strict_rejects_windows_absolute_source_artifacts(
    artifact_path: str,
) -> None:
    with pytest.raises(ValidationError, match="source_artifacts entry must be a project-relative path"):
        parse_knowledge_doc_data_strict(
            _knowledge_doc_data(source_artifact=artifact_path),
            source_path=_SOURCE_PATH,
        )


@pytest.mark.parametrize(
    "artifact_path",
    [
        pytest.param("C:/tmp/review.md", id="windows-drive-letter"),
        pytest.param(r"\\server\share\review.md", id="windows-unc"),
    ],
)
def test_parse_knowledge_doc_data_strict_rejects_windows_absolute_approval_artifact_path(
    artifact_path: str,
) -> None:
    with pytest.raises(ValidationError, match="approval_artifact_path must be a project-relative path"):
        parse_knowledge_doc_data_strict(
            _knowledge_doc_data(
                status="stable",
                approval_artifact_path=artifact_path,
            ),
            source_path=_SOURCE_PATH,
        )
