"""Focused contract coverage for knowledge-doc frontmatter."""

from __future__ import annotations

from pathlib import Path

import pytest

from gpd.core import knowledge_docs as knowledge_docs_module
from gpd.core.frontmatter import extract_frontmatter, validate_frontmatter


def _knowledge_content_sha256(content: str) -> str:
    """Resolve the repo's canonical knowledge-content hash helper."""

    meta, body = extract_frontmatter(content)
    candidate_names = sorted(
        (name for name in dir(knowledge_docs_module) if "sha256" in name.lower()),
        key=lambda name: (
            0 if any(token in name.lower() for token in ("knowledge", "review", "content")) else 1,
            name,
        ),
    )
    for name in candidate_names:
        helper = getattr(knowledge_docs_module, name, None)
        if not callable(helper):
            continue
        for args in ((content,), (meta, body)):
            try:
                result = helper(*args)
            except TypeError:
                continue
            if isinstance(result, str) and result.strip():
                return result.strip()
        try:
            result = helper(meta=meta, body=body)
        except TypeError:
            continue
        if isinstance(result, str) and result.strip():
            return result.strip()
    raise AssertionError("expected a knowledge-doc content sha256 helper in gpd.core.knowledge_docs")


def _review_block(
    *,
    reviewed_content_sha256: str | None,
    decision: str = "approved",
    stale: bool = False,
    review_round: int | None = 1,
    reviewer_kind: str = "human",
    reviewer_id: str = "gpd-reviewer",
    summary: str = "Reviewed and accepted for downstream use",
    approval_artifact_path: str | None = "GPD/knowledge/reviews/K-renormalization-group-fixed-points-R1-REVIEW.md",
    approval_artifact_sha256: str | None = "a" * 64,
    reviewed_at: str = "2026-04-07T12:00:00Z",
) -> str:
    lines = [
        "review:",
        f"  reviewed_at: {reviewed_at}",
    ]
    if review_round is not None:
        lines.append(f"  review_round: {review_round}")
    lines.extend(
        [
            f"  reviewer_kind: {reviewer_kind}",
            f"  reviewer_id: {reviewer_id}",
            f"  decision: {decision}",
            f"  summary: {summary}",
        ]
    )
    if approval_artifact_path is not None:
        lines.append(f"  approval_artifact_path: {approval_artifact_path}")
    if approval_artifact_sha256 is not None:
        lines.append(f"  approval_artifact_sha256: {approval_artifact_sha256}")
    if reviewed_content_sha256 is not None:
        lines.append(f"  reviewed_content_sha256: {reviewed_content_sha256}")
    lines.append(f"  stale: {'true' if stale else 'false'}")
    return "\n".join(lines)


def _knowledge_markdown(
    *,
    knowledge_id: str = "K-renormalization-group-fixed-points",
    status: str = "draft",
    title: str = "Renormalization Group Fixed Points",
    topic: str = "renormalization-group",
    body: str = "Knowledge doc body.",
    extra_frontmatter: str = "",
    sources: str = """
sources:
  - source_id: source-main
    kind: paper
    locator: Doe et al., 2024
    title: Renormalization Group Fixed Points
    why_it_matters: Reviewed source that anchors the topic
""".strip(),
    coverage_summary: str = """
coverage_summary:
  covered_topics: [fixed points, scaling]
  excluded_topics: [numerical implementation details]
  open_gaps: [none]
""".strip(),
    review: str | None = None,
    superseded_by: str | None = "superseded_by: K-renormalization-group-critical-exponents",
) -> str:
    lines = [
        "---",
        "knowledge_schema_version: 1",
        f"knowledge_id: {knowledge_id}",
        f"title: {title}",
        f"topic: {topic}",
        f"status: {status}",
        "created_at: 2026-04-07T12:00:00Z",
        "updated_at: 2026-04-07T12:00:00Z",
    ]
    if extra_frontmatter.strip():
        lines.extend(line.rstrip() for line in extra_frontmatter.strip().splitlines())
    lines.extend(sources.splitlines())
    lines.extend(coverage_summary.splitlines())
    if review is not None:
        lines.extend(review.splitlines())
    if status == "superseded" and superseded_by:
        lines.append(superseded_by)
    lines.extend(
        [
            "---",
            "",
            body,
            "",
        ]
    )
    return "\n".join(lines)


def _stable_reviewed_content_sha256() -> str:
    base_content = _knowledge_markdown(status="stable")
    return _knowledge_content_sha256(base_content)


def test_validate_frontmatter_accepts_draft_knowledge_doc(tmp_path: Path) -> None:
    path = tmp_path / "K-renormalization-group-fixed-points.md"
    content = _knowledge_markdown()
    path.write_text(content, encoding="utf-8")

    result = validate_frontmatter(content, "knowledge", source_path=path)

    assert result.valid is True
    assert result.errors == []
    assert result.missing == []


def test_validate_frontmatter_accepts_in_review_knowledge_doc_with_needs_changes_review(
    tmp_path: Path,
) -> None:
    path = tmp_path / "K-renormalization-group-fixed-points.md"
    content = _knowledge_markdown(
        status="in_review",
        review=_review_block(
            reviewed_content_sha256=_stable_reviewed_content_sha256(),
            decision="needs_changes",
            stale=False,
        ),
    )
    path.write_text(content, encoding="utf-8")

    result = validate_frontmatter(content, "knowledge", source_path=path)

    assert result.valid is True
    assert result.errors == []


def test_validate_frontmatter_accepts_in_review_knowledge_doc_with_stale_approved_review(
    tmp_path: Path,
) -> None:
    path = tmp_path / "K-renormalization-group-fixed-points.md"
    content = _knowledge_markdown(
        status="in_review",
        review=_review_block(
            reviewed_content_sha256=_stable_reviewed_content_sha256(),
            stale=True,
        ),
    )
    path.write_text(content, encoding="utf-8")

    result = validate_frontmatter(content, "knowledge", source_path=path)

    assert result.valid is True
    assert result.errors == []


def test_validate_frontmatter_accepts_stable_knowledge_doc_with_fresh_review(tmp_path: Path) -> None:
    path = tmp_path / "K-renormalization-group-fixed-points.md"
    reviewed_content_sha256 = _stable_reviewed_content_sha256()
    content = _knowledge_markdown(
        status="stable",
        review=_review_block(
            reviewed_content_sha256=reviewed_content_sha256,
            stale=False,
        ),
    )
    path.write_text(content, encoding="utf-8")

    result = validate_frontmatter(content, "knowledge", source_path=path)

    assert result.valid is True
    assert result.errors == []


def test_validate_frontmatter_accepts_superseded_knowledge_doc_with_successor(tmp_path: Path) -> None:
    path = tmp_path / "K-renormalization-group-fixed-points.md"
    reviewed_content_sha256 = _stable_reviewed_content_sha256()
    content = _knowledge_markdown(
        status="superseded",
        review=_review_block(
            reviewed_content_sha256=reviewed_content_sha256,
        ),
    )
    path.write_text(content, encoding="utf-8")

    result = validate_frontmatter(content, "knowledge", source_path=path)

    assert result.valid is True
    assert result.errors == []


@pytest.mark.parametrize(
    ("content", "expected_error"),
    [
        (
            _knowledge_markdown().replace("knowledge_schema_version: 1", "knowledge_schema_version: 2"),
            "knowledge_schema_version",
        ),
        (
            _knowledge_markdown(knowledge_id="K-renormalization-group-fixed-points")
            .replace("knowledge_id: K-renormalization-group-fixed-points", "knowledge_id: K-other"),
            "knowledge_id",
        ),
        (
            _knowledge_markdown().replace(
                "created_at: 2026-04-07T12:00:00Z",
                "created_at: not-a-timestamp",
            ),
            "created_at",
        ),
        (
            _knowledge_markdown().replace(
                "updated_at: 2026-04-07T12:00:00Z",
                "updated_at: not-a-timestamp",
            ),
            "updated_at",
        ),
        (
            _knowledge_markdown().replace(
                "updated_at: 2026-04-07T12:00:00Z",
                "updated_at: 2026-04-06T12:00:00Z",
            ),
            "updated_at",
        ),
        (
            _knowledge_markdown().replace(
                "status: draft",
                "status: under_review",
            ),
            "status",
        ),
        (
            _knowledge_markdown().replace(
                "coverage_summary:\n  covered_topics: [fixed points, scaling]\n  excluded_topics: [numerical implementation details]\n  open_gaps: [none]",
                "coverage_summary: reviewed in prose only",
            ),
            "coverage_summary",
        ),
        (
            _knowledge_markdown().replace(
                "sources:\n  - source_id: source-main\n    kind: paper\n    locator: Doe et al., 2024\n    title: Renormalization Group Fixed Points\n    why_it_matters: Reviewed source that anchors the topic",
                "sources: [reviewed-source]",
            ),
            "sources",
        ),
    ],
)
def test_validate_frontmatter_rejects_invalid_knowledge_doc_inputs(
    content: str,
    expected_error: str,
    tmp_path: Path,
) -> None:
    path = tmp_path / "K-renormalization-group-fixed-points.md"
    path.write_text(content, encoding="utf-8")

    result = validate_frontmatter(content, "knowledge", source_path=path)

    assert result.valid is False
    assert any(expected_error in error for error in result.errors)


def test_validate_frontmatter_rejects_filename_and_id_mismatch(tmp_path: Path) -> None:
    path = tmp_path / "K-renormalization-group-critical-exponents.md"
    content = _knowledge_markdown()
    path.write_text(content, encoding="utf-8")

    result = validate_frontmatter(content, "knowledge", source_path=path)

    assert result.valid is False
    assert any("knowledge_id" in error for error in result.errors)


def test_validate_frontmatter_rejects_draft_with_review(tmp_path: Path) -> None:
    path = tmp_path / "K-renormalization-group-fixed-points.md"
    content = _knowledge_markdown(
        review=_review_block(
            reviewed_content_sha256=_stable_reviewed_content_sha256(),
        ),
    )
    path.write_text(content, encoding="utf-8")

    result = validate_frontmatter(content, "knowledge", source_path=path)

    assert result.valid is False
    assert any("review" in error for error in result.errors)


def test_validate_frontmatter_rejects_stable_without_review(tmp_path: Path) -> None:
    path = tmp_path / "K-renormalization-group-fixed-points.md"
    content = _knowledge_markdown(status="stable")
    path.write_text(content, encoding="utf-8")

    result = validate_frontmatter(content, "knowledge", source_path=path)

    assert result.valid is False
    assert any("review" in error for error in result.errors)


@pytest.mark.parametrize(
    ("review", "expected_error"),
    [
        (
            _review_block(
                reviewed_content_sha256=_stable_reviewed_content_sha256(),
                review_round=None,
            ),
            "review_round",
        ),
        (
            _review_block(
                reviewed_content_sha256=_stable_reviewed_content_sha256(),
                approval_artifact_path=None,
            ),
            "approval_artifact_path",
        ),
        (
            _review_block(
                reviewed_content_sha256=_stable_reviewed_content_sha256(),
                approval_artifact_sha256=None,
            ),
            "approval_artifact_sha256",
        ),
        (
            _review_block(
                reviewed_content_sha256=None,
            ),
            "reviewed_content_sha256",
        ),
    ],
)
def test_validate_frontmatter_rejects_stable_without_required_review_fields(
    review: str,
    expected_error: str,
    tmp_path: Path,
) -> None:
    path = tmp_path / "K-renormalization-group-fixed-points.md"
    content = _knowledge_markdown(status="stable", review=review)
    path.write_text(content, encoding="utf-8")

    result = validate_frontmatter(content, "knowledge", source_path=path)

    assert result.valid is False
    assert any(expected_error in error for error in result.errors)


@pytest.mark.parametrize(
    ("review", "expected_error"),
    [
        (
            _review_block(
                reviewed_content_sha256="A" * 64,
            ),
            "approval_artifact_sha256",
        ),
        (
            _review_block(
                reviewed_content_sha256="deadbeef",
            ),
            "reviewed_content_sha256",
        ),
    ],
)
def test_validate_frontmatter_rejects_stable_with_invalid_review_sha256_fields(
    review: str,
    expected_error: str,
    tmp_path: Path,
) -> None:
    path = tmp_path / "K-renormalization-group-fixed-points.md"
    content = _knowledge_markdown(status="stable", review=review)
    path.write_text(content, encoding="utf-8")

    result = validate_frontmatter(content, "knowledge", source_path=path)

    assert result.valid is False
    assert any(expected_error in error for error in result.errors)


def test_validate_frontmatter_rejects_stable_review_with_absolute_artifact_path(tmp_path: Path) -> None:
    path = tmp_path / "K-renormalization-group-fixed-points.md"
    content = _knowledge_markdown(
        status="stable",
        review=_review_block(
            reviewed_content_sha256=_stable_reviewed_content_sha256(),
            approval_artifact_path="/tmp/K-renormalization-group-fixed-points-R1-REVIEW.md",
        ),
    )
    path.write_text(content, encoding="utf-8")

    result = validate_frontmatter(content, "knowledge", source_path=path)

    assert result.valid is False
    assert any("approval_artifact_path" in error for error in result.errors)


def test_validate_frontmatter_rejects_approved_in_review_with_stale_false(tmp_path: Path) -> None:
    path = tmp_path / "K-renormalization-group-fixed-points.md"
    content = _knowledge_markdown(
        status="in_review",
        review=_review_block(
            reviewed_content_sha256=_stable_reviewed_content_sha256(),
            stale=False,
        ),
    )
    path.write_text(content, encoding="utf-8")

    result = validate_frontmatter(content, "knowledge", source_path=path)

    assert result.valid is False
    assert any("stale" in error or "in_review" in error for error in result.errors)


def test_validate_frontmatter_rejects_superseded_without_successor(tmp_path: Path) -> None:
    path = tmp_path / "K-renormalization-group-fixed-points.md"
    content = _knowledge_markdown(status="superseded", superseded_by=None)
    path.write_text(content, encoding="utf-8")

    result = validate_frontmatter(content, "knowledge", source_path=path)

    assert result.valid is False
    assert any("superseded_by" in error for error in result.errors)
