"""Freshness coverage for reviewed knowledge-doc content hashes."""

from __future__ import annotations

from pathlib import Path

from gpd.core import knowledge_docs as knowledge_docs_module
from gpd.core.frontmatter import extract_frontmatter, validate_frontmatter


def _knowledge_content_sha256(content: str) -> str:
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


def _review_block(*, reviewed_content_sha256: str) -> str:
    return "\n".join(
        [
            "review:",
            "  reviewed_at: 2026-04-07T12:00:00Z",
            "  review_round: 1",
            "  reviewer_kind: human",
            "  reviewer_id: gpd-reviewer",
            "  decision: approved",
            "  summary: Reviewed and accepted for downstream use",
            "  approval_artifact_path: GPD/knowledge/reviews/K-renormalization-group-fixed-points-R1-REVIEW.md",
            "  approval_artifact_sha256: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            f"  reviewed_content_sha256: {reviewed_content_sha256}",
            "  stale: false",
        ]
    )


def _knowledge_markdown(
    *,
    knowledge_id: str = "K-renormalization-group-fixed-points",
    status: str = "stable",
    title: str = "Renormalization Group Fixed Points",
    topic: str = "renormalization-group",
    body: str = "Knowledge doc body.",
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
    lines.extend(sources.splitlines())
    lines.extend(coverage_summary.splitlines())
    if review is not None:
        lines.extend(review.splitlines())
    lines.extend(
        [
            "---",
            "",
            body,
            "",
        ]
    )
    return "\n".join(lines)


def test_stable_knowledge_doc_accepts_current_reviewed_content_hash(tmp_path: Path) -> None:
    base_content = _knowledge_markdown()
    reviewed_content_sha256 = _knowledge_content_sha256(base_content)
    content = _knowledge_markdown(review=_review_block(reviewed_content_sha256=reviewed_content_sha256))
    path = tmp_path / "K-renormalization-group-fixed-points.md"
    path.write_text(content, encoding="utf-8")

    result = validate_frontmatter(content, "knowledge", source_path=path)

    assert result.valid is True
    assert result.errors == []


def test_stable_knowledge_doc_becomes_stale_after_body_edit(tmp_path: Path) -> None:
    base_content = _knowledge_markdown()
    reviewed_content_sha256 = _knowledge_content_sha256(base_content)
    content = _knowledge_markdown(
        body="Knowledge doc body.\n\nEdited body sentence.",
        review=_review_block(reviewed_content_sha256=reviewed_content_sha256),
    )
    path = tmp_path / "K-renormalization-group-fixed-points.md"
    path.write_text(content, encoding="utf-8")

    result = validate_frontmatter(content, "knowledge", source_path=path)

    assert result.valid is False
    assert any("reviewed_content_sha256" in error or "stale" in error for error in result.errors)


def test_stable_knowledge_doc_becomes_stale_after_trusted_metadata_edit(tmp_path: Path) -> None:
    base_content = _knowledge_markdown()
    reviewed_content_sha256 = _knowledge_content_sha256(base_content)
    content = _knowledge_markdown(
        title="Renormalization Group Fixed Points, Revised",
        review=_review_block(reviewed_content_sha256=reviewed_content_sha256),
    )
    path = tmp_path / "K-renormalization-group-fixed-points.md"
    path.write_text(content, encoding="utf-8")

    result = validate_frontmatter(content, "knowledge", source_path=path)

    assert result.valid is False
    assert any("reviewed_content_sha256" in error or "stale" in error for error in result.errors)
