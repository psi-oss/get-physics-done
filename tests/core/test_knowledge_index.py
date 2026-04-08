"""Inventory and resolution coverage for runtime-visible knowledge docs."""

from __future__ import annotations

from pathlib import Path

from gpd.core.frontmatter import compute_knowledge_reviewed_content_sha256
from gpd.core.knowledge_index import (
    iter_knowledge_supersession_chain,
    load_knowledge_doc_inventory,
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


def test_load_knowledge_doc_inventory_surfaces_status_counts_and_fresh_approval(tmp_path: Path) -> None:
    _write_knowledge_doc(tmp_path, knowledge_id="K-active", status="stable")
    _write_knowledge_doc(tmp_path, knowledge_id="K-reviewing", status="in_review")
    _write_knowledge_doc(tmp_path, knowledge_id="K-draft", status="draft")

    inventory = load_knowledge_doc_inventory(tmp_path)

    assert [record.knowledge_id for record in inventory.records] == ["K-active", "K-draft", "K-reviewing"]
    assert inventory.status_counts()["stable"] == 1
    assert inventory.status_counts()["in_review"] == 1
    assert inventory.status_counts()["draft"] == 1
    active = inventory.by_id()["K-active"]
    assert active.is_fresh_approved is True
    assert inventory.warnings == []


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
