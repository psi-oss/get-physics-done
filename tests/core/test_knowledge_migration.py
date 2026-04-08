"""Coverage for dry-run knowledge-doc migration classification."""

from __future__ import annotations

import shutil
from pathlib import Path

from gpd.core.knowledge_migration import (
    KnowledgeMigrationClassification,
    classify_knowledge_doc_migration,
    discover_knowledge_migration,
)

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "knowledge"


def _copy_fixture_tree(tmp_path: Path, fixture_name: str) -> Path:
    fixture_root = FIXTURES_DIR / fixture_name
    knowledge_dir = tmp_path / "GPD" / "knowledge"
    shutil.copytree(fixture_root, knowledge_dir, dirs_exist_ok=True)
    return knowledge_dir


def test_classify_knowledge_doc_migration_recognizes_canonical_fixture(tmp_path: Path) -> None:
    knowledge_dir = _copy_fixture_tree(tmp_path, "canonical")
    path = knowledge_dir / "K-renormalization-group-fixed-points.md"

    record = classify_knowledge_doc_migration(tmp_path, path)

    assert record.classification == KnowledgeMigrationClassification.CANONICAL
    assert record.knowledge_id == "K-renormalization-group-fixed-points"
    assert record.canonical_knowledge_id == "K-renormalization-group-fixed-points"
    assert record.canonical_path == "GPD/knowledge/K-renormalization-group-fixed-points.md"
    assert record.can_rewrite is True
    assert record.needs_review_refresh is False


def test_classify_knowledge_doc_migration_marks_upgradeable_fixture_without_fabricating_review(
    tmp_path: Path,
) -> None:
    knowledge_dir = _copy_fixture_tree(tmp_path, "upgradeable")
    path = knowledge_dir / "legacy-renormalization-group-fixed-points.md"

    record = classify_knowledge_doc_migration(tmp_path, path)

    assert record.classification == KnowledgeMigrationClassification.UPGRADEABLE
    assert record.knowledge_id == "renormalization-group-fixed-points"
    assert record.canonical_knowledge_id == "K-renormalization-group-fixed-points"
    assert record.canonical_path == "GPD/knowledge/K-renormalization-group-fixed-points.md"
    assert record.suggested_status == "draft"
    assert record.needs_review_refresh is True
    assert any("downgrade trust" in note for note in record.notes)


def test_classify_knowledge_doc_migration_blocks_free_form_sources(tmp_path: Path) -> None:
    knowledge_dir = _copy_fixture_tree(tmp_path, "blocked")
    path = knowledge_dir / "legacy-free-form-sources.md"

    record = classify_knowledge_doc_migration(tmp_path, path)

    assert record.classification == KnowledgeMigrationClassification.BLOCKED
    assert record.canonical_knowledge_id == "K-renormalization-group-fixed-points"
    assert record.canonical_path == "GPD/knowledge/K-renormalization-group-fixed-points.md"
    assert any("knowledge.sources" in blocker for blocker in record.blockers)
    assert record.can_rewrite is False


def test_discover_knowledge_migration_counts_canonical_upgradeable_and_blocked_docs(
    tmp_path: Path,
) -> None:
    _copy_fixture_tree(tmp_path, "canonical")
    _copy_fixture_tree(tmp_path, "upgradeable")
    _copy_fixture_tree(tmp_path, "blocked")

    inventory = discover_knowledge_migration(tmp_path)

    counts = inventory.classification_counts()
    assert counts["canonical"] == 1
    assert counts["upgradeable"] == 1
    assert counts["blocked"] == 1
    assert len(inventory.warnings) == 2
