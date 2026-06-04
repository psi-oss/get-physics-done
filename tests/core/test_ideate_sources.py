"""Tests for ``gpd:ideate`` source manifest intake."""

from __future__ import annotations

from pathlib import Path

from gpd.core.ideate_sources import normalize_ideate_sources, parse_ideate_arguments
from tests.assertion_taxonomy_support import assert_prompt_contracts, semantic_concept


def _write_knowledge_doc(
    root: Path,
    *,
    knowledge_id: str = "K-demo-source",
    arxiv_id: str = "hep-th/9901001",
    source_artifacts: tuple[str, ...] = (),
) -> Path:
    path = root / "GPD" / "knowledge" / f"{knowledge_id}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    artifact_block = (
        "    source_artifacts:\n" + "".join(f"      - {artifact}\n" for artifact in source_artifacts)
        if source_artifacts
        else "    source_artifacts: []\n"
    )
    path.write_text(
        "---\n"
        "knowledge_schema_version: 1\n"
        f"knowledge_id: {knowledge_id}\n"
        "title: Demo source\n"
        "topic: demo\n"
        "status: draft\n"
        "created_at: 2026-06-04T00:00:00Z\n"
        "updated_at: 2026-06-04T00:00:00Z\n"
        "sources:\n"
        "  - source_id: S-001\n"
        "    kind: paper\n"
        f"    locator: arXiv:{arxiv_id}\n"
        "    title: Demo paper\n"
        "    why_it_matters: Demo source grounding.\n"
        f"{artifact_block}"
        f"    arxiv_id: {arxiv_id}\n"
        "coverage_summary:\n"
        "  covered_topics:\n"
        "    - demo\n"
        "  excluded_topics:\n"
        "    - none\n"
        "  open_gaps:\n"
        "    - none\n"
        "---\n\n"
        "# Demo source\n",
        encoding="utf-8",
    )
    return path


def test_normalize_ideate_sources_uses_shared_arxiv_normalizer_for_ids_and_urls(tmp_path: Path) -> None:
    manifest = normalize_ideate_sources(
        ["2301.12345", "hep-th/9901001", "https://arxiv.org/abs/2407.08593v2"],
        workspace_root=tmp_path,
    )

    assert [source.source_id for source in manifest.sources] == ["SRC-001", "SRC-002", "SRC-003"]
    assert [source.kind for source in manifest.sources] == ["arxiv", "arxiv", "arxiv"]
    assert [source.normalized_ref for source in manifest.sources] == [
        "2301.12345",
        "hep-th/9901001",
        "2407.08593v2",
    ]
    assert [source.status for source in manifest.sources] == ["pending", "pending", "pending"]


def test_normalize_ideate_sources_classifies_explicit_pdf_and_tex_paths(tmp_path: Path) -> None:
    papers = tmp_path / "papers"
    papers.mkdir()
    (papers / "paper.pdf").write_text("pdf", encoding="utf-8")
    (papers / "main.tex").write_text("tex", encoding="utf-8")

    manifest = normalize_ideate_sources(["papers/paper.pdf", "papers/main.tex"], workspace_root=tmp_path)

    assert [(source.kind, source.normalized_ref, source.status) for source in manifest.sources] == [
        ("pdf", "papers/paper.pdf", "pending"),
        ("tex", "papers/main.tex", "pending"),
    ]
    assert manifest.source_inputs == ("papers/paper.pdf", "papers/main.tex")


def test_normalize_ideate_sources_topic_only_creates_blocked_context_row(tmp_path: Path) -> None:
    manifest = normalize_ideate_sources(["matrix model chaos"], workspace_root=tmp_path)

    assert len(manifest.sources) == 1
    source = manifest.sources[0]
    assert source.source_id == "SRC-001"
    assert source.kind == "topic"
    assert source.normalized_ref == "matrix model chaos"
    assert source.status == "blocked"
    assert source.digest_path == ""
    assert_prompt_contracts(
        source.warnings[0],
        *semantic_concept("ideate topic-only grounding warning", required="source-grounded claims"),
    )
    assert manifest.source_inputs == ()
    assert manifest.blocked is True


def test_normalize_ideate_sources_reuses_existing_knowledge_doc_input(tmp_path: Path) -> None:
    _write_knowledge_doc(tmp_path)

    manifest = normalize_ideate_sources(["GPD/knowledge/K-demo-source.md"], workspace_root=tmp_path)

    assert len(manifest.sources) == 1
    source = manifest.sources[0]
    assert source.kind == "knowledge_doc"
    assert source.normalized_ref == "GPD/knowledge/K-demo-source.md"
    assert source.status == "reused"
    assert source.digest_path == "GPD/knowledge/K-demo-source.md"
    assert manifest.knowledge_docs == ("GPD/knowledge/K-demo-source.md",)


def test_normalize_ideate_sources_reuses_knowledge_doc_matched_by_arxiv_and_source_artifact(
    tmp_path: Path,
) -> None:
    papers = tmp_path / "papers"
    papers.mkdir()
    (papers / "demo.tex").write_text("tex", encoding="utf-8")
    _write_knowledge_doc(tmp_path, source_artifacts=("papers/demo.tex",))

    by_arxiv = normalize_ideate_sources(["hep-th/9901001"], workspace_root=tmp_path)
    by_path = normalize_ideate_sources(["papers/demo.tex"], workspace_root=tmp_path)

    assert by_arxiv.sources[0].kind == "arxiv"
    assert by_arxiv.sources[0].status == "reused"
    assert by_arxiv.sources[0].digest_path == "GPD/knowledge/K-demo-source.md"
    assert by_path.sources[0].kind == "tex"
    assert by_path.sources[0].status == "reused"
    assert by_path.sources[0].digest_path == "GPD/knowledge/K-demo-source.md"


def test_normalize_ideate_sources_directory_scan_prefers_same_stem_tex_over_pdf(tmp_path: Path) -> None:
    papers = tmp_path / "papers"
    papers.mkdir()
    (papers / "paper.pdf").write_text("pdf", encoding="utf-8")
    (papers / "paper.tex").write_text("tex", encoding="utf-8")

    manifest = normalize_ideate_sources(["papers"], workspace_root=tmp_path)

    assert len(manifest.sources) == 1
    source = manifest.sources[0]
    assert source.kind == "directory_item"
    assert source.normalized_ref == "papers/paper.tex"
    assert source.status == "pending"
    assert any("same stem" in warning and ".tex is preferred" in warning for warning in manifest.warnings)
    assert source.warnings == manifest.warnings


def test_normalize_ideate_sources_records_duplicate_source_warning(tmp_path: Path) -> None:
    manifest = normalize_ideate_sources(
        ["2301.12345", "https://arxiv.org/abs/2301.12345"],
        workspace_root=tmp_path,
    )

    assert len(manifest.sources) == 1
    assert manifest.sources[0].normalized_ref == "2301.12345"
    assert manifest.warnings == ("Duplicate ideate source skipped: https://arxiv.org/abs/2301.12345",)
    assert manifest.sources[0].warnings == manifest.warnings


def test_normalize_ideate_sources_enforces_max_papers_by_skipping_extra_directory_items(tmp_path: Path) -> None:
    papers = tmp_path / "papers"
    papers.mkdir()
    for name in ("a.pdf", "b.tex", "c.pdf"):
        (papers / name).write_text(name, encoding="utf-8")

    manifest = normalize_ideate_sources(["papers"], workspace_root=tmp_path, max_papers=2)

    assert [source.source_id for source in manifest.sources] == ["SRC-001", "SRC-002"]
    assert [source.normalized_ref for source in manifest.sources] == ["papers/a.pdf", "papers/b.tex"]
    assert [source.kind for source in manifest.sources] == ["directory_item", "directory_item"]
    assert any("--max-papers 2" in warning and "papers/c.pdf" in warning for warning in manifest.warnings)
    assert manifest.blocked is False


def test_parse_ideate_arguments_extracts_max_papers_and_combines_topic_words() -> None:
    parsed = parse_ideate_arguments("matrix model chaos --max-papers 3")
    mixed = parse_ideate_arguments("matrix model chaos 2301.12345 --max-papers 2")

    assert parsed.source_inputs == ("matrix model chaos",)
    assert parsed.max_papers == 3
    assert parsed.warnings == ()
    assert mixed.source_inputs == ("matrix model chaos", "2301.12345")
    assert mixed.max_papers == 2
