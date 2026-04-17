"""Inventory and resolution coverage for runtime-visible knowledge docs."""

from __future__ import annotations

from pathlib import Path

import pytest

from gpd.core.frontmatter import compute_knowledge_reviewed_content_sha256, extract_frontmatter
from gpd.core.knowledge_runtime import (
    discover_knowledge_docs,
    iter_knowledge_supersession_chain,
    resolve_knowledge_doc,
    search_knowledge_docs,
)


def _write_knowledge_doc(
    tmp_path: Path,
    *,
    knowledge_id: str,
    title: str = "Renormalization Group Fixed Points",
    topic: str = "renormalization-group",
    status: str = "stable",
    superseded_by: str | None = None,
) -> Path:
    knowledge_dir = tmp_path / "GPD" / "knowledge"
    knowledge_dir.mkdir(parents=True, exist_ok=True)
    path = knowledge_dir / f"{knowledge_id}.md"
    base_content = (
        "---\n"
        "knowledge_schema_version: 1\n"
        f"knowledge_id: {knowledge_id}\n"
        f"title: {title}\n"
        f"topic: {topic}\n"
        f"status: {status}\n"
        "created_at: 2026-04-07T12:00:00Z\n"
        "updated_at: 2026-04-07T12:00:00Z\n"
        "sources:\n"
        "  - source_id: source-main\n"
        "    kind: paper\n"
        "    locator: Author et al., 2024\n"
        "    title: Benchmark Reference\n"
        "    why_it_matters: Trusted source for the topic\n"
        "coverage_summary:\n"
        "  covered_topics: [fixed points]\n"
        "  excluded_topics: [implementation]\n"
        "  open_gaps: [none]\n"
    )
    if superseded_by is not None:
        base_content += f"superseded_by: {superseded_by}\n"
    base_content += "---\n\nTrusted knowledge body.\n"
    reviewed_content_sha256 = compute_knowledge_reviewed_content_sha256(base_content)
    if status in {"stable", "in_review", "superseded"}:
        review_block = (
            "review:\n"
            "  reviewed_at: 2026-04-07T13:00:00Z\n"
            "  review_round: 1\n"
            "  reviewer_kind: workflow\n"
            "  reviewer_id: gpd-review-knowledge\n"
            "  decision: approved\n"
            "  summary: Stable review approved.\n"
            f"  approval_artifact_path: GPD/knowledge/reviews/{knowledge_id}-R1-REVIEW.md\n"
            f"  approval_artifact_sha256: {'a' * 64}\n"
            f"  reviewed_content_sha256: {reviewed_content_sha256}\n"
            f"  stale: {'false' if status != 'in_review' else 'true'}\n"
        )
        content = base_content.replace("---\n\n", review_block + "---\n\n")
    else:
        content = base_content
    path.write_text(content, encoding="utf-8")
    return path


_TOLERANT_ENVELOPE_VARIANTS = (
    "leading_blank_lines",
    "bom",
    "crlf",
    "closing_delimiter_at_eof",
)


def _render_tolerant_stable_knowledge_doc(
    *,
    knowledge_id: str,
    variant: str,
    reviewed_content_sha256: str | None = None,
) -> str:
    newline = "\r\n" if variant == "crlf" else "\n"
    prefix = ""
    body = "Trusted knowledge body.\n"
    if variant == "leading_blank_lines":
        prefix = f"{newline}{newline}"
    elif variant == "bom":
        prefix = "\ufeff"
    elif variant == "closing_delimiter_at_eof":
        body = ""

    lines = [
        "---",
        "knowledge_schema_version: 1",
        f"knowledge_id: {knowledge_id}",
        "title: Renormalization Group Fixed Points",
        "topic: renormalization-group",
        "status: stable",
        "created_at: 2026-04-07T12:00:00Z",
        "updated_at: 2026-04-07T12:00:00Z",
        "sources:",
        "  - source_id: source-main",
        "    kind: paper",
        "    locator: Author et al., 2024",
        "    title: Benchmark Reference",
        "    why_it_matters: Trusted source for the topic",
        "coverage_summary:",
        "  covered_topics: [fixed points]",
        "  excluded_topics: [implementation]",
        "  open_gaps: [none]",
    ]
    if reviewed_content_sha256 is not None:
        lines.extend(
            [
                "review:",
                "  reviewed_at: 2026-04-07T13:00:00Z",
                "  review_round: 1",
                "  reviewer_kind: workflow",
                "  reviewer_id: gpd-review-knowledge",
                "  decision: approved",
                "  summary: Stable review approved.",
                f"  approval_artifact_path: GPD/knowledge/reviews/{knowledge_id}-R1-REVIEW.md",
                f"  approval_artifact_sha256: {'a' * 64}",
                f"  reviewed_content_sha256: {reviewed_content_sha256}",
                "  stale: false",
            ]
        )

    frontmatter = newline.join([*lines, "---"])
    if variant == "closing_delimiter_at_eof":
        return prefix + frontmatter
    normalized_body = body.replace("\r\n", "\n").replace("\n", newline)
    return prefix + frontmatter + newline + newline + normalized_body


def _write_stable_knowledge_doc_with_tolerant_envelope(
    tmp_path: Path,
    *,
    knowledge_id: str,
    variant: str,
) -> Path:
    knowledge_dir = tmp_path / "GPD" / "knowledge"
    knowledge_dir.mkdir(parents=True, exist_ok=True)
    path = knowledge_dir / f"{knowledge_id}.md"
    base_content = _render_tolerant_stable_knowledge_doc(knowledge_id=knowledge_id, variant=variant)
    meta, body = extract_frontmatter(base_content)
    reviewed_content_sha256 = compute_knowledge_reviewed_content_sha256(meta, body=body)
    path.write_text(
        _render_tolerant_stable_knowledge_doc(
            knowledge_id=knowledge_id,
            variant=variant,
            reviewed_content_sha256=reviewed_content_sha256,
        ),
        encoding="utf-8",
    )
    return path


def test_load_knowledge_doc_inventory_surfaces_status_counts_and_fresh_approval(tmp_path: Path) -> None:
    _write_knowledge_doc(tmp_path, knowledge_id="K-active", status="stable")
    _write_knowledge_doc(tmp_path, knowledge_id="K-reviewing", status="in_review")
    _write_knowledge_doc(tmp_path, knowledge_id="K-draft", status="draft")

    inventory = discover_knowledge_docs(tmp_path)

    assert [record.knowledge_id for record in inventory.records] == ["K-active", "K-draft", "K-reviewing"]
    assert inventory.status_counts()["stable"] == 1
    assert inventory.status_counts()["in_review"] == 1
    assert inventory.status_counts()["draft"] == 1
    active = inventory.by_id()["K-active"]
    assert active.is_fresh_approved is True
    assert inventory.warnings == []


@pytest.mark.parametrize("variant", _TOLERANT_ENVELOPE_VARIANTS)
def test_discover_knowledge_docs_keeps_fresh_approved_state_for_tolerant_frontmatter_envelopes(
    tmp_path: Path,
    variant: str,
) -> None:
    knowledge_id = f"K-{variant.replace('_', '-')}"
    _write_stable_knowledge_doc_with_tolerant_envelope(
        tmp_path,
        knowledge_id=knowledge_id,
        variant=variant,
    )

    inventory = discover_knowledge_docs(tmp_path)

    assert inventory.warnings == []
    assert [record.knowledge_id for record in inventory.records] == [knowledge_id]
    record = inventory.by_id()[knowledge_id]
    assert record.review_fresh is True
    assert record.runtime_active is True
    assert record.is_fresh_approved is True


def test_search_knowledge_docs_prefers_exact_path_and_id_matches(tmp_path: Path) -> None:
    exact_doc = _write_knowledge_doc(tmp_path, knowledge_id="K-active", status="stable", topic="renormalization-group")
    _write_knowledge_doc(
        tmp_path,
        knowledge_id="K-legacy",
        status="superseded",
        topic="renormalization-group",
        superseded_by="K-active",
    )

    path_token = exact_doc.relative_to(tmp_path).as_posix()

    by_path = search_knowledge_docs(tmp_path, token=path_token)
    by_id = search_knowledge_docs(tmp_path, token="K-active")
    by_missing_explicit_id = search_knowledge_docs(tmp_path, token="K-missing")

    assert [record.knowledge_id for record in by_path] == ["K-active"]
    assert [record.knowledge_id for record in by_id] == ["K-active"]
    assert by_missing_explicit_id == ()


def test_resolve_knowledge_doc_fails_closed_on_ambiguous_topic_matches(tmp_path: Path) -> None:
    _write_knowledge_doc(tmp_path, knowledge_id="K-active", status="stable", topic="renormalization-group")
    _write_knowledge_doc(
        tmp_path,
        knowledge_id="K-legacy",
        status="superseded",
        topic="renormalization-group",
        superseded_by="K-active",
    )

    resolution = resolve_knowledge_doc(tmp_path, "renormalization-group")

    assert resolution.resolved is False
    assert resolution.record is None
    assert len(resolution.candidates) == 2


def test_resolve_knowledge_doc_reports_ambiguous_active_topic_matches(tmp_path: Path) -> None:
    _write_knowledge_doc(tmp_path, knowledge_id="K-active-a", status="stable", topic="renormalization-group")
    _write_knowledge_doc(tmp_path, knowledge_id="K-active-b", status="stable", topic="renormalization-group")

    resolution = resolve_knowledge_doc(tmp_path, "renormalization-group")

    assert resolution.resolved is False
    assert resolution.record is None
    assert len(resolution.candidates) == 2
    assert resolution.reason is not None


def test_resolve_knowledge_doc_allows_unique_active_only_topic_match_when_explicit(tmp_path: Path) -> None:
    _write_knowledge_doc(tmp_path, knowledge_id="K-active", status="stable", topic="renormalization-group")
    _write_knowledge_doc(
        tmp_path,
        knowledge_id="K-legacy",
        status="superseded",
        topic="renormalization-group",
        superseded_by="K-active",
    )

    resolution = resolve_knowledge_doc(tmp_path, "renormalization-group", active_only=True)

    assert resolution.resolved is True
    assert resolution.record is not None
    assert resolution.record.knowledge_id == "K-active"
    assert len(resolution.candidates) == 1


def test_iter_knowledge_supersession_chain_follows_successor_links(tmp_path: Path) -> None:
    _write_knowledge_doc(
        tmp_path,
        knowledge_id="K-v1",
        status="superseded",
        topic="renormalization-group",
        superseded_by="K-v2",
    )
    _write_knowledge_doc(
        tmp_path,
        knowledge_id="K-v2",
        status="superseded",
        topic="renormalization-group",
        superseded_by="K-v3",
    )
    _write_knowledge_doc(tmp_path, knowledge_id="K-v3", status="stable", topic="renormalization-group")

    chain = iter_knowledge_supersession_chain(tmp_path, "K-v1")

    assert [record.knowledge_id for record in chain] == ["K-v1", "K-v2", "K-v3"]
