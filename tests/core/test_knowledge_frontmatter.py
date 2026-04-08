"""Focused contract coverage for knowledge-doc frontmatter."""

from __future__ import annotations

from pathlib import Path

import pytest

from gpd.core.frontmatter import validate_frontmatter


def _knowledge_markdown(
    *,
    knowledge_id: str = "K-renormalization-group-fixed-points",
    status: str = "draft",
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
    review: str | None = """
review:
  reviewed_at: 2026-04-07T12:00:00Z
  reviewer: gpd-reviewer
  decision: approved
  summary: Reviewed and accepted for downstream use
  evidence_path: GPD/phases/01-benchmark/01-VERIFICATION.md
  evidence_sha256: deadbeef
""".strip(),
    superseded_by: str | None = "superseded_by: K-renormalization-group-critical-exponents",
) -> str:
    lines = [
        "---",
        "knowledge_schema_version: 1",
        f"knowledge_id: {knowledge_id}",
        "title: Renormalization Group Fixed Points",
        "topic: renormalization group",
        f"status: {status}",
        "created_at: 2026-04-07T12:00:00Z",
        "updated_at: 2026-04-07T12:00:00Z",
    ]
    if extra_frontmatter.strip():
        lines.extend(line.rstrip() for line in extra_frontmatter.strip().splitlines())
    lines.extend(sources.splitlines())
    lines.extend(coverage_summary.splitlines())
    if status in {"stable", "superseded"} and review:
        lines.extend(review.splitlines())
    if status == "superseded" and superseded_by:
        lines.append(superseded_by)
    lines.extend(
        [
            "---",
            "",
            "Knowledge doc body.",
            "",
        ]
    )
    return "\n".join(lines)


def test_validate_frontmatter_accepts_draft_knowledge_doc(tmp_path: Path) -> None:
    path = tmp_path / "K-renormalization-group-fixed-points.md"
    path.write_text(_knowledge_markdown(), encoding="utf-8")

    result = validate_frontmatter(path.read_text(encoding="utf-8"), "knowledge", source_path=path)

    assert result.valid is True
    assert result.errors == []
    assert result.missing == []


def test_validate_frontmatter_accepts_stable_knowledge_doc_with_review(tmp_path: Path) -> None:
    path = tmp_path / "K-renormalization-group-fixed-points.md"
    path.write_text(_knowledge_markdown(status="stable"), encoding="utf-8")

    result = validate_frontmatter(path.read_text(encoding="utf-8"), "knowledge", source_path=path)

    assert result.valid is True
    assert result.errors == []


def test_validate_frontmatter_accepts_superseded_knowledge_doc_with_successor(tmp_path: Path) -> None:
    path = tmp_path / "K-renormalization-group-fixed-points.md"
    path.write_text(_knowledge_markdown(status="superseded"), encoding="utf-8")

    result = validate_frontmatter(path.read_text(encoding="utf-8"), "knowledge", source_path=path)

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
    assert any(expected_error in error or expected_error in missing for error in result.errors for missing in [error])


def test_validate_frontmatter_rejects_filename_and_id_mismatch(tmp_path: Path) -> None:
    path = tmp_path / "K-renormalization-group-critical-exponents.md"
    path.write_text(_knowledge_markdown(), encoding="utf-8")

    result = validate_frontmatter(path.read_text(encoding="utf-8"), "knowledge", source_path=path)

    assert result.valid is False
    assert any("knowledge_id" in error for error in result.errors)


def test_validate_frontmatter_rejects_stable_without_review(tmp_path: Path) -> None:
    path = tmp_path / "K-renormalization-group-fixed-points.md"
    content = _knowledge_markdown(status="stable", review=None)
    path.write_text(content, encoding="utf-8")

    result = validate_frontmatter(content, "knowledge", source_path=path)

    assert result.valid is False
    assert any("review" in error or "review" in missing for error in result.errors for missing in [error])


def test_validate_frontmatter_rejects_draft_with_review(tmp_path: Path) -> None:
    path = tmp_path / "K-renormalization-group-fixed-points.md"
    content = _knowledge_markdown(status="draft", extra_frontmatter="""
review:
  reviewed_at: 2026-04-07T12:00:00Z
  reviewer: gpd-reviewer
  decision: approved
  summary: Draft should not carry approval evidence
  evidence_path: GPD/phases/01-benchmark/01-VERIFICATION.md
""")
    path.write_text(content, encoding="utf-8")

    result = validate_frontmatter(content, "knowledge", source_path=path)

    assert result.valid is False
    assert any("review" in error for error in result.errors)


def test_validate_frontmatter_rejects_superseded_without_successor(tmp_path: Path) -> None:
    path = tmp_path / "K-renormalization-group-fixed-points.md"
    content = _knowledge_markdown(status="superseded", superseded_by=None)
    path.write_text(content, encoding="utf-8")

    result = validate_frontmatter(content, "knowledge", source_path=path)

    assert result.valid is False
    assert any("superseded_by" in error for error in result.errors)


def test_validate_frontmatter_rejects_review_without_concrete_evidence_pointer(tmp_path: Path) -> None:
    path = tmp_path / "K-renormalization-group-fixed-points.md"
    content = _knowledge_markdown(
        status="stable",
        review="""
review:
  reviewed_at: 2026-04-07T12:00:00Z
  reviewer: gpd-reviewer
  decision: approved
  summary: Missing concrete evidence pointer
  evidence_sha256: deadbeef
""".strip(),
    )
    path.write_text(content, encoding="utf-8")

    result = validate_frontmatter(content, "knowledge", source_path=path)

    assert result.valid is False
    assert any("review" in error for error in result.errors)


def test_validate_frontmatter_rejects_malformed_sources_and_coverage_summary(tmp_path: Path) -> None:
    path = tmp_path / "K-renormalization-group-fixed-points.md"
    content = _knowledge_markdown().replace(
        "  - source_id: source-main\n    kind: paper\n    locator: Doe et al., 2024\n    title: Renormalization Group Fixed Points\n    why_it_matters: Reviewed source that anchors the topic\n",
        "  - source_id: source-main\n    kind: paper\n",
    ).replace(
        "coverage_summary:\n  covered_topics: [fixed points, scaling]\n  excluded_topics: [numerical implementation details]\n  open_gaps: [none]\n",
        "coverage_summary: reviewed in prose only\n",
    )
    path.write_text(content, encoding="utf-8")

    result = validate_frontmatter(content, "knowledge", source_path=path)

    assert result.valid is False
    assert any("sources" in error or "coverage_summary" in error for error in result.errors)


def test_validate_frontmatter_rejects_invalid_knowledge_id_format(tmp_path: Path) -> None:
    path = tmp_path / "invalid.md"
    content = _knowledge_markdown(knowledge_id="renormalization-group-fixed-points")
    path.write_text(content, encoding="utf-8")

    result = validate_frontmatter(content, "knowledge", source_path=path)

    assert result.valid is False
    assert any("knowledge_id" in error for error in result.errors)
