"""Dry-run migration classification for knowledge documents."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from gpd.core.frontmatter import extract_frontmatter
from gpd.core.knowledge_docs import KnowledgeReviewRecord, KnowledgeSourceRecord, parse_knowledge_doc_data_strict
from gpd.core.utils import normalize_ascii_slug

__all__ = [
    "KnowledgeDocMigrationRecord",
    "KnowledgeDocMigrationInventory",
    "KnowledgeMigrationClassification",
    "classify_knowledge_doc_migration",
    "discover_knowledge_migration",
]


class KnowledgeMigrationClassification(StrEnum):
    """Lifecycle of a migration assessment."""

    CANONICAL = "canonical"
    UPGRADEABLE = "upgradeable"
    BLOCKED = "blocked"


def _relative_posix(root: Path, path: Path) -> str:
    resolved_root = root.resolve(strict=False)
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(resolved_root).as_posix()
    except ValueError:
        return resolved_path.as_posix()


def _text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _canonical_knowledge_id(value: object) -> str | None:
    text = _text(value)
    if text is None:
        return None
    slug = text[2:] if text.startswith("K-") else text
    normalized = normalize_ascii_slug(slug)
    if not normalized:
        return None
    return f"K-{normalized}"


def _canonical_knowledge_path(project_root: Path, knowledge_id: str) -> str:
    from gpd.core.constants import ProjectLayout

    layout = ProjectLayout(project_root)
    return _relative_posix(project_root, layout.knowledge_dir / f"{knowledge_id}.md")


def _normalize_source_record(raw: object, *, index: int) -> tuple[dict[str, object] | None, str | None]:
    if not isinstance(raw, dict):
        return None, f"knowledge.sources[{index}]: expected an object"

    try:
        record = KnowledgeSourceRecord.model_validate(raw)
    except Exception:
        candidate: dict[str, object] = {}

        def pick(*keys: str) -> object | None:
            for key in keys:
                if key in raw and raw[key] is not None:
                    value = raw[key]
                    if isinstance(value, str):
                        stripped = value.strip()
                        if stripped:
                            return stripped
                    elif isinstance(value, list):
                        return value
            return None

        candidate["source_id"] = pick("source_id", "id", "source", "name", "key")
        candidate["kind"] = pick("kind", "type") or "other"
        candidate["locator"] = pick("locator", "citation", "reference", "label")
        candidate["title"] = pick("title", "label", "name")
        candidate["why_it_matters"] = pick("why_it_matters", "why", "summary", "notes", "description")
        candidate["source_artifacts"] = pick("source_artifacts", "artifacts", "files") or []
        candidate["reference_id"] = pick("reference_id", "ref_id")
        candidate["arxiv_id"] = pick("arxiv_id")
        candidate["doi"] = pick("doi")
        candidate["url"] = pick("url")
        if not all(candidate.get(field) for field in ("source_id", "locator", "title", "why_it_matters")):
            return None, f"knowledge.sources[{index}]: missing required source fields"
        try:
            record = KnowledgeSourceRecord.model_validate(candidate)
        except Exception as exc:  # pragma: no cover - handled through deterministic blockers
            return None, f"knowledge.sources[{index}]: {exc}"
        return record.model_dump(mode="python"), "knowledge.sources[{index}]: normalized from legacy keys"

    return record.model_dump(mode="python"), None


def _normalize_sources(raw_sources: object) -> tuple[list[dict[str, object]] | None, list[str], list[str]]:
    if not isinstance(raw_sources, list):
        return None, [], ["knowledge.sources: expected a list"]

    normalized: list[dict[str, object]] = []
    notes: list[str] = []
    blockers: list[str] = []
    for index, raw_source in enumerate(raw_sources):
        record, detail = _normalize_source_record(raw_source, index=index)
        if record is None:
            blockers.append(detail or f"knowledge.sources[{index}]: could not be normalized")
            continue
        normalized.append(record)
        if detail:
            notes.append(detail.format(index=index))

    if blockers:
        return None, notes, blockers
    if not normalized:
        return None, notes, ["knowledge.sources: must contain at least one source record"]
    return normalized, notes, []


def _normalize_review(raw_review: object, *, status: str) -> tuple[dict[str, object] | None, str, list[str]]:
    if not isinstance(raw_review, dict):
        if status == "stable":
            return None, "missing", ["stable doc has no canonical review evidence"]
        if status == "in_review":
            return None, "missing", ["in_review doc has no review evidence"]
        return None, "missing", []

    try:
        review = KnowledgeReviewRecord.model_validate(raw_review)
    except Exception as exc:
        if status == "stable":
            return None, "legacy", [f"stable doc review block is non-canonical and must be re-reviewed: {exc}"]
        if status == "in_review":
            return None, "legacy", [f"in_review doc review block is non-canonical and must be rebuilt: {exc}"]
        return None, "legacy", [f"legacy review block will be dropped during migration: {exc}"]

    if status == "draft":
        return None, "canonical", ["draft docs must not keep review evidence during migration"]
    return review.model_dump(mode="python"), "canonical", []


def _derive_canonical_id(meta: dict[str, object], path: Path) -> tuple[str | None, str | None]:
    raw_id = _canonical_knowledge_id(meta.get("knowledge_id"))
    if raw_id is not None:
        return raw_id, "knowledge_id"

    for field_name in ("stem", "topic", "title"):
        candidate = _canonical_knowledge_id(path.stem if field_name == "stem" else meta.get(field_name))
        if candidate is not None:
            return candidate, field_name
    return None, None


def _build_normalized_meta(
    meta: dict[str, object],
    *,
    canonical_knowledge_id: str,
    suggested_status: str,
    normalized_sources: list[dict[str, object]],
    normalized_review: dict[str, object] | None,
) -> dict[str, object]:
    normalized = dict(meta)
    normalized["knowledge_schema_version"] = 1
    normalized["knowledge_id"] = canonical_knowledge_id
    normalized["status"] = suggested_status
    normalized["sources"] = normalized_sources
    if normalized_review is None:
        normalized.pop("review", None)
    else:
        normalized["review"] = normalized_review
    superseded_by = _canonical_knowledge_id(normalized.get("superseded_by"))
    if normalized.get("status") == "superseded":
        if superseded_by is None:
            raise ValueError("knowledge.superseded_by: must be a canonical K-{ascii-hyphen-slug} identifier")
        normalized["superseded_by"] = superseded_by
    elif "superseded_by" in normalized:
        normalized.pop("superseded_by", None)
    return normalized


@dataclass(frozen=True, slots=True)
class KnowledgeDocMigrationRecord:
    """Dry-run migration assessment for one knowledge document."""

    path: str
    classification: KnowledgeMigrationClassification
    knowledge_id: str | None
    canonical_knowledge_id: str | None
    canonical_path: str | None
    current_status: str | None
    suggested_status: str | None
    review_state: str
    source_count: int
    normalized_source_count: int
    can_rewrite: bool
    needs_review_refresh: bool
    reasons: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    @property
    def is_canonical(self) -> bool:
        return self.classification == KnowledgeMigrationClassification.CANONICAL

    @property
    def is_upgradeable(self) -> bool:
        return self.classification == KnowledgeMigrationClassification.UPGRADEABLE

    @property
    def is_blocked(self) -> bool:
        return self.classification == KnowledgeMigrationClassification.BLOCKED

    def summary(self) -> str:
        if self.classification == KnowledgeMigrationClassification.CANONICAL:
            return f"{self.path}: canonical knowledge doc"
        target = self.canonical_path or self.path
        pieces = [f"{self.path}: {self.classification}"]
        if target and target != self.path:
            pieces.append(f"-> {target}")
        if self.suggested_status and self.suggested_status != self.current_status:
            pieces.append(f"status {self.current_status or 'unknown'} -> {self.suggested_status}")
        if self.notes:
            pieces.append("; ".join(self.notes))
        if self.blockers:
            pieces.append("; ".join(self.blockers))
        return " ".join(pieces)

    def to_context_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "classification": self.classification.value,
            "knowledge_id": self.knowledge_id,
            "canonical_knowledge_id": self.canonical_knowledge_id,
            "canonical_path": self.canonical_path,
            "current_status": self.current_status,
            "suggested_status": self.suggested_status,
            "review_state": self.review_state,
            "source_count": self.source_count,
            "normalized_source_count": self.normalized_source_count,
            "can_rewrite": self.can_rewrite,
            "needs_review_refresh": self.needs_review_refresh,
            "reasons": list(self.reasons),
            "blockers": list(self.blockers),
            "notes": list(self.notes),
        }


@dataclass
class KnowledgeDocMigrationInventory:
    """Collection of migration assessments for a project."""

    records: list[KnowledgeDocMigrationRecord] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def classification_counts(self) -> dict[str, int]:
        counts = {
            KnowledgeMigrationClassification.CANONICAL.value: 0,
            KnowledgeMigrationClassification.UPGRADEABLE.value: 0,
            KnowledgeMigrationClassification.BLOCKED.value: 0,
        }
        for record in self.records:
            counts[record.classification.value] += 1
        return counts


def classify_knowledge_doc_migration(
    project_root: Path,
    path: Path,
    *,
    content: str | None = None,
) -> KnowledgeDocMigrationRecord:
    """Classify one knowledge doc for dry-run migration reporting."""

    resolved_root = project_root.resolve(strict=False)
    resolved_path = path if path.is_absolute() else (resolved_root / path)
    rel_path = _relative_posix(resolved_root, resolved_path)
    notes: list[str] = []
    blockers: list[str] = []

    if content is None:
        try:
            content = resolved_path.read_text(encoding="utf-8")
        except OSError as exc:
            return KnowledgeDocMigrationRecord(
                path=rel_path,
                classification=KnowledgeMigrationClassification.BLOCKED,
                knowledge_id=None,
                canonical_knowledge_id=None,
                canonical_path=None,
                current_status=None,
                suggested_status=None,
                review_state="blocked",
                source_count=0,
                normalized_source_count=0,
                can_rewrite=False,
                needs_review_refresh=False,
                blockers=(f"could not read knowledge doc: {exc}",),
            )

    try:
        meta, _body = extract_frontmatter(content)
    except Exception as exc:
        return KnowledgeDocMigrationRecord(
            path=rel_path,
            classification=KnowledgeMigrationClassification.BLOCKED,
            knowledge_id=None,
            canonical_knowledge_id=None,
            canonical_path=None,
            current_status=None,
            suggested_status=None,
            review_state="blocked",
            source_count=0,
            normalized_source_count=0,
            can_rewrite=False,
            needs_review_refresh=False,
            blockers=(f"frontmatter parse failed: {exc}",),
        )

    if not isinstance(meta, dict):
        return KnowledgeDocMigrationRecord(
            path=rel_path,
            classification=KnowledgeMigrationClassification.BLOCKED,
            knowledge_id=None,
            canonical_knowledge_id=None,
            canonical_path=None,
            current_status=None,
            suggested_status=None,
            review_state="blocked",
            source_count=0,
            normalized_source_count=0,
            can_rewrite=False,
            needs_review_refresh=False,
            blockers=("knowledge frontmatter must be an object",),
        )

    knowledge_id = _text(meta.get("knowledge_id"))
    current_status = _text(meta.get("status"))
    canonical_knowledge_id, canonical_source = _derive_canonical_id(meta, resolved_path)
    if canonical_knowledge_id is None:
        blockers.append("could not derive a canonical knowledge_id from the file")

    canonical_path = _canonical_knowledge_path(resolved_root, canonical_knowledge_id) if canonical_knowledge_id else None
    normalized_sources, source_notes, source_blockers = _normalize_sources(meta.get("sources"))
    notes.extend(source_notes)
    blockers.extend(source_blockers)

    raw_review = meta.get("review")
    normalized_review, review_state, review_notes = _normalize_review(raw_review, status=current_status or "")
    notes.extend(review_notes)
    needs_review_refresh = review_state != "canonical" and current_status in {"stable", "in_review"}

    suggested_status = current_status
    if current_status == "stable" and review_state != "canonical":
        suggested_status = "in_review" if raw_review is not None else "draft"
        notes.append("stable status requires canonical review evidence; migration would downgrade trust")
    elif current_status == "in_review" and review_state != "canonical":
        suggested_status = "draft"
        notes.append("in_review status cannot retain non-canonical review evidence; migration would downgrade trust")
    elif current_status == "draft" and review_state != "canonical":
        suggested_status = "draft"
        if raw_review is not None:
            notes.append("draft docs do not carry review evidence in the canonical schema")
    elif current_status == "superseded" and normalized_review is None and raw_review is not None:
        notes.append("legacy review evidence on superseded docs is dropped during migration")

    normalized_meta: dict[str, object] | None = None
    if canonical_knowledge_id is not None and current_status is not None and normalized_sources is not None:
        try:
            normalized_meta = _build_normalized_meta(
                meta,
                canonical_knowledge_id=canonical_knowledge_id,
                suggested_status=suggested_status or current_status,
                normalized_sources=normalized_sources,
                normalized_review=normalized_review,
            )
            canonicalized_path = resolved_path.with_name(f"{canonical_knowledge_id}.md")
            parse_knowledge_doc_data_strict(normalized_meta, source_path=canonicalized_path)
        except Exception as exc:
            blockers.append(str(exc))
            normalized_meta = None

    classification: KnowledgeMigrationClassification
    reasons: list[str] = []
    can_rewrite = False
    normalized_source_count = 0

    if canonical_knowledge_id is not None and normalized_meta is not None:
        try:
            parse_knowledge_doc_data_strict(meta, source_path=resolved_path)
        except Exception:
            classification = KnowledgeMigrationClassification.UPGRADEABLE
            reasons.append("canonical id/path and schema can be normalized without fabricating trust")
            can_rewrite = True
            normalized_source_count = len(normalized_sources or [])
            if canonical_source and canonical_source != "knowledge_id":
                notes.append(f"canonical id derived from {canonical_source}")
            if canonical_path is not None and canonical_path != rel_path:
                notes.append(f"canonical path should become {canonical_path}")
        else:
            classification = KnowledgeMigrationClassification.CANONICAL
            reasons.append("already satisfies the canonical v1 knowledge schema")
            can_rewrite = True
            normalized_source_count = len(normalized_sources or [])
            if canonical_path is not None and canonical_path != rel_path:
                notes.append(f"filename stem should be renamed to match {canonical_knowledge_id}")
    else:
        classification = KnowledgeMigrationClassification.BLOCKED
        if canonical_knowledge_id is not None and normalized_meta is None:
            reasons.append("canonical id/path was derivable, but the doc could not be rewritten safely")
        elif canonical_knowledge_id is None:
            reasons.append("no canonical knowledge_id could be derived")
        if not blockers and normalized_sources is None:
            blockers.append("knowledge sources are not safely normalizable")

    if classification != KnowledgeMigrationClassification.CANONICAL and canonical_path is not None:
        can_rewrite = True if normalized_meta is not None else can_rewrite

    if classification == KnowledgeMigrationClassification.BLOCKED and not blockers:
        blockers.append("migration cannot proceed without an unambiguous canonical target")

    return KnowledgeDocMigrationRecord(
        path=rel_path,
        classification=classification,
        knowledge_id=knowledge_id,
        canonical_knowledge_id=canonical_knowledge_id,
        canonical_path=canonical_path,
        current_status=current_status,
        suggested_status=suggested_status if classification != KnowledgeMigrationClassification.BLOCKED else None,
        review_state=review_state,
        source_count=len(meta.get("sources")) if isinstance(meta.get("sources"), list) else 0,
        normalized_source_count=normalized_source_count,
        can_rewrite=can_rewrite,
        needs_review_refresh=needs_review_refresh,
        reasons=tuple(reasons),
        blockers=tuple(blockers),
        notes=tuple(notes),
    )


def discover_knowledge_migration(project_root: Path) -> KnowledgeDocMigrationInventory:
    """Discover all knowledge docs and classify them for dry-run migration."""

    layout_root = project_root.resolve(strict=False)
    knowledge_dir = layout_root / "GPD" / "knowledge"
    inventory = KnowledgeDocMigrationInventory()
    if not knowledge_dir.is_dir():
        return inventory

    for path in sorted(knowledge_dir.glob("*.md")):
        record = classify_knowledge_doc_migration(layout_root, path)
        inventory.records.append(record)
        if record.classification != KnowledgeMigrationClassification.CANONICAL:
            inventory.warnings.append(record.summary())
    return inventory
