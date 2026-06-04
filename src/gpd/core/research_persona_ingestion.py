"""Deterministic source ingestion for Research Persona candidate patches.

The helpers in this module are intentionally patch-only. They turn explicit,
user-approved source material into strict ``ResearchPersonaPatch`` objects and
bounded evidence summaries, but they never load or mutate the durable persona
store.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from gpd.core.research_persona import (
    RESEARCH_PERSONA_PRIVACY_VALUES,
    RESEARCH_PERSONA_SCHEMA_VERSION,
    RESEARCH_PERSONA_SOURCE_KIND_VALUES,
    ResearchPersonaEvidence,
    ResearchPersonaFact,
    ResearchPersonaPatch,
    ResearchPersonaPatchOperation,
)
from gpd.core.utils import normalize_ascii_slug

__all__ = [
    "RESEARCH_PERSONA_INGESTION_SOURCE_KIND_VALUES",
    "ResearchPersonaEvidencePacket",
    "ResearchPersonaSourceDocument",
    "build_research_persona_evidence_packet_from_sources",
    "build_research_persona_ingestion_payload",
    "build_research_persona_patch_from_sources",
    "build_research_persona_source_patch",
    "build_research_persona_source_patch_payload",
    "normalize_research_persona_source_document",
    "summarize_research_persona_evidence_packet",
]


RESEARCH_PERSONA_INGESTION_SOURCE_KIND_VALUES: tuple[str, ...] = (
    "interview",
    "project_scan",
    "paper_import",
    "bibtex_import",
    "repo_scan",
    "manual_patch",
    "user_statement",
)

ResearchPersonaIngestionSourceKind = Literal[*RESEARCH_PERSONA_INGESTION_SOURCE_KIND_VALUES]
ResearchPersonaIngestionPrivacy = Literal[*RESEARCH_PERSONA_PRIVACY_VALUES]

_SUMMARY_LIMIT = 320
_VALUE_LIMIT = 360
_FACT_SLUG_LIMIT = 56
_REFERENCE_CATEGORIES = {"paper", "reference"}
_PAPER_SOURCE_KINDS = {"paper_import", "bibtex_import"}
_PROJECT_SOURCE_KINDS = {"project_scan", "repo_scan"}
_LOCAL_SOURCE_KINDS = {"interview", "user_statement", "manual_patch"}
_PRIVACY_RESTRICTIVENESS = {
    "never_prompt": 0,
    "private_local": 1,
    "project_private": 2,
    "session_only": 3,
    "safe_to_share": 4,
}
_CONFIDENCE_RANK = {
    "confirmed": 0,
    "inferred": 1,
    "stale": 2,
    "disputed": 3,
}

_LABELS_BY_CATEGORY: dict[str, frozenset[str]] = {
    "research_area": frozenset(
        {
            "area",
            "areas",
            "field",
            "fields",
            "research",
            "research area",
            "research areas",
            "research topics",
            "topics",
        }
    ),
    "tool": frozenset({"tool", "tools", "software", "stack", "tooling"}),
    "paper": frozenset({"paper", "papers", "publication", "publications", "manuscripts"}),
    "reference": frozenset({"reference", "references", "citation", "citations"}),
    "collaborator": frozenset({"collaborator", "collaborators", "coauthor", "coauthors", "team"}),
    "expertise": frozenset({"expertise", "skills", "strengths", "specialties", "specialty"}),
    "workstyle": frozenset({"workstyle", "work style", "working style", "workflow"}),
    "scientific_taste": frozenset(
        {
            "scientific taste",
            "taste",
            "taste model",
            "research taste",
            "aesthetic",
            "aesthetics",
        }
    ),
    "standing_preference": frozenset({"preference", "preferences", "standing preference", "standing preferences"}),
    "negative_preference": frozenset({"avoid", "avoids", "negative preference", "negative preferences", "dislikes"}),
}
_CATEGORY_BY_LABEL = {label: category for category, labels in _LABELS_BY_CATEGORY.items() for label in labels}
_SOURCE_KIND_ALIASES = {
    "bib": "bibtex_import",
    "bibtex": "bibtex_import",
    "manual": "manual_patch",
    "paper": "paper_import",
    "project": "project_scan",
    "publication": "paper_import",
    "repo": "repo_scan",
    "repository": "repo_scan",
    "statement": "user_statement",
    "user": "user_statement",
}
_TEXT_ALIAS_KEYS = ("summary", "content", "body", "statement")
_LINE_LABEL_RE = re.compile(r"^\s*(?:[-*]\s*)?(?P<label>[A-Za-z][A-Za-z0-9 _/\-]{1,64})\s*[:=]\s*(?P<value>.+?)\s*$")
_BIBTEX_ENTRY_FALLBACK_RE = re.compile(
    r"@\w+\s*\{\s*(?P<key>[^,\s]+)\s*,(?P<body>.*?)(?=^\s*@|\Z)",
    re.IGNORECASE | re.MULTILINE | re.DOTALL,
)
_BIBTEX_FIELD_FALLBACK_RE = re.compile(
    r"(?P<key>[A-Za-z][A-Za-z0-9_-]*)\s*=\s*(?P<value>\{[^{}]*\}|\"[^\"]*\"|[^,\n]+)",
    re.MULTILINE,
)

_KNOWN_TOOL_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\bpython\b", "Python"),
    (r"\bpytorch\b", "PyTorch"),
    (r"\bjax\b", "JAX"),
    (r"\bnumpy\b", "NumPy"),
    (r"\bscipy\b", "SciPy"),
    (r"\bmathematica\b", "Mathematica"),
    (r"\bwolfram\b", "Wolfram"),
    (r"\bjulia\b", "Julia"),
    (r"\bc\+\+\b|(?<!\w)c\+\+(?!\w)", "C++"),
    (r"\brust\b", "Rust"),
    (r"\blatex\b", "LaTeX"),
    (r"\bpytest\b", "pytest"),
    (r"(?<![A-Za-z0-9])uv(?![A-Za-z0-9])", "uv"),
    (r"\bmodal\b", "Modal"),
    (r"\bgithub\b", "GitHub"),
    (r"\bgit\b", "Git"),
)

_RESEARCH_AREA_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("algebraic geometry", "algebraic geometry"),
    ("condensed matter", "condensed matter physics"),
    ("conformal bootstrap", "conformal bootstrap"),
    ("cosmology", "cosmology"),
    ("differential geometry", "differential geometry"),
    ("general relativity", "general relativity"),
    ("lattice gauge", "lattice gauge theory"),
    ("machine learning", "machine learning"),
    ("numerical relativity", "numerical relativity"),
    ("particle physics", "particle physics"),
    ("quantum field theory", "quantum field theory"),
    ("quantum gravity", "quantum gravity"),
    ("quantum information", "quantum information"),
    ("scattering amplitude", "scattering amplitudes"),
    ("statistical mechanics", "statistical mechanics"),
    ("string theory", "string theory"),
)

_WORKSTYLE_CUES: tuple[tuple[str, str], ...] = (
    ("concise", "Prefers concise plans and explanations."),
    ("rigorous", "Prefers rigorous arguments with explicit assumptions."),
    ("proof", "Values proof-level reasoning and derivations."),
    ("derivation", "Values proof-level reasoning and derivations."),
    ("test", "Values test-backed code changes."),
    ("experiment", "Values experimental or numerical validation."),
    ("numerical", "Values experimental or numerical validation."),
    ("code", "Values concrete code artifacts."),
    ("implementation", "Values concrete code artifacts."),
)

_SCIENTIFIC_TASTE_CUES: tuple[tuple[str, str], ...] = (
    ("applied", "Values applied consequences."),
    ("black-box", "Prefers mechanistic explanations over black-box answers."),
    ("experiment", "Values experimental grounding."),
    ("fundamental", "Leans toward fundamental questions."),
    ("mechanistic", "Prefers mechanistic explanations over black-box answers."),
    ("simple model", "Values simple models and solvable limits."),
    ("solvable", "Values simple models and solvable limits."),
    ("theoretical", "Leans theoretical when framing research."),
    ("toy model", "Values simple models and solvable limits."),
)


class _StrictIngestionModel(BaseModel):
    model_config = ConfigDict(validate_assignment=True, extra="forbid")


def _schema_version(value: object) -> int:
    if type(value) is not int or value != RESEARCH_PERSONA_SCHEMA_VERSION:
        raise ValueError("schema_version must be the integer 1")
    return value


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("must be a string or null")
    text = _compact_text(value)
    return text or None


def _strict_bool(value: object) -> bool:
    if type(value) is bool:
        return value
    raise ValueError("must be a boolean")


def _literal_choice(value: object, choices: tuple[str, ...]) -> object:
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text:
        raise ValueError("must not be blank")
    for choice in choices:
        if text.casefold() == choice.casefold():
            return choice
    return text


def _normalize_metadata_value(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = _compact_text(value)
        return text or None
    if type(value) is bool or isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            normalized = _normalize_metadata_value(item)
            if normalized:
                parts.append(normalized)
        return ", ".join(parts) or None
    raise ValueError("metadata values must be scalar strings, numbers, booleans, lists, or null")


def _normalize_metadata(value: object) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError("metadata must be an object")
    normalized: dict[str, str] = {}
    for raw_key, raw_value in value.items():
        if not isinstance(raw_key, str):
            raise ValueError("metadata keys must be strings")
        key = _compact_text(raw_key).casefold().replace("-", "_").replace(" ", "_")
        if not key:
            continue
        text = _normalize_metadata_value(raw_value)
        if text:
            normalized[key] = text
    return normalized


def _strict_model_list(value: object) -> object:
    if not isinstance(value, list):
        raise ValueError("must be a list")
    return value


def _strict_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        raise ValueError("must be a list of strings")
    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            raise ValueError("must contain only strings")
        text = _compact_text(item)
        if not text or text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    return normalized


def _compact_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value).replace("\x00", " ")).strip()


def _normalize_multiline_text(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("must be a string or null")
    text = value.replace("\x00", " ").replace("\r\n", "\n").replace("\r", "\n").strip()
    return text or None


def _bounded_text(value: object, *, limit: int = _VALUE_LIMIT) -> str:
    text = _compact_text(value)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def _slug(value: object, *, fallback: str, limit: int = _FACT_SLUG_LIMIT) -> str:
    slug = normalize_ascii_slug(value) or fallback
    return slug[:limit].rstrip("-") or fallback


def _stable_digest(*parts: object, length: int = 12) -> str:
    payload = json.dumps(parts, sort_keys=True, ensure_ascii=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:length]


class ResearchPersonaSourceDocument(_StrictIngestionModel):
    """One explicit source artifact approved for persona ingestion."""

    schema_version: int = RESEARCH_PERSONA_SCHEMA_VERSION
    source_kind: ResearchPersonaIngestionSourceKind
    text: str | None = None
    path: str | None = None
    locator: str | None = None
    title: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)
    privacy: ResearchPersonaIngestionPrivacy | None = None
    safe_to_share: bool = False
    confirmed: bool = False

    @field_validator("schema_version", mode="before")
    @classmethod
    def _normalize_schema_version(cls, value: object) -> int:
        return _schema_version(value)

    @field_validator("source_kind", mode="before")
    @classmethod
    def _normalize_source_kind(cls, value: object) -> object:
        return _literal_choice(value, RESEARCH_PERSONA_INGESTION_SOURCE_KIND_VALUES)

    @field_validator("text", mode="before")
    @classmethod
    def _normalize_text(cls, value: object) -> str | None:
        return _normalize_multiline_text(value)

    @field_validator("path", "locator", "title", mode="before")
    @classmethod
    def _normalize_optional_text(cls, value: object) -> str | None:
        return _optional_string(value)

    @field_validator("metadata", mode="before")
    @classmethod
    def _normalize_metadata(cls, value: object) -> dict[str, str]:
        return _normalize_metadata(value)

    @field_validator("privacy", mode="before")
    @classmethod
    def _normalize_privacy(cls, value: object) -> object:
        if value is None:
            return None
        return _literal_choice(value, RESEARCH_PERSONA_PRIVACY_VALUES)

    @field_validator("safe_to_share", "confirmed", mode="before")
    @classmethod
    def _normalize_bool(cls, value: object) -> bool:
        return _strict_bool(value)

    @model_validator(mode="after")
    def _validate_has_source_material(self) -> ResearchPersonaSourceDocument:
        if self.source_kind not in RESEARCH_PERSONA_SOURCE_KIND_VALUES:
            raise ValueError("source_kind is not supported by the research persona schema")
        if any((self.text, self.path, self.locator, self.title, self.metadata)):
            return self
        raise ValueError("source document requires text, path, locator, title, or metadata")


class ResearchPersonaEvidencePacket(_StrictIngestionModel):
    """Bounded provenance and candidate facts derived from source documents."""

    schema_version: int = RESEARCH_PERSONA_SCHEMA_VERSION
    documents: list[ResearchPersonaSourceDocument] = Field(default_factory=list)
    evidence: list[ResearchPersonaEvidence] = Field(default_factory=list)
    facts: list[ResearchPersonaFact] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @field_validator("schema_version", mode="before")
    @classmethod
    def _normalize_schema_version(cls, value: object) -> int:
        return _schema_version(value)

    @field_validator("documents", "evidence", "facts", mode="before")
    @classmethod
    def _normalize_model_lists(cls, value: object) -> object:
        return _strict_model_list(value)

    @field_validator("warnings", mode="before")
    @classmethod
    def _normalize_warnings(cls, value: object) -> list[str]:
        return _strict_string_list(value)


def normalize_research_persona_source_document(
    source: ResearchPersonaSourceDocument | Mapping[str, object],
) -> ResearchPersonaSourceDocument:
    """Return a strict, normalized source document without reading files."""

    if isinstance(source, ResearchPersonaSourceDocument):
        return ResearchPersonaSourceDocument.model_validate(source.model_dump(mode="python"))
    if not isinstance(source, Mapping):
        raise ValueError("source document must be an object")
    return ResearchPersonaSourceDocument.model_validate(_normalize_document_aliases(dict(source)))


def build_research_persona_evidence_packet_from_sources(
    sources: Iterable[ResearchPersonaSourceDocument | Mapping[str, object]],
) -> ResearchPersonaEvidencePacket:
    """Derive bounded evidence and candidate facts from explicit sources."""

    documents = [normalize_research_persona_source_document(source) for source in sources]
    evidence: list[ResearchPersonaEvidence] = []
    facts: list[ResearchPersonaFact] = []
    warnings: list[str] = []

    for index, document in enumerate(documents):
        evidence_id = _evidence_id(document, index=index)
        candidates = _fact_candidates_for_document(document, evidence_id=evidence_id)
        categories = tuple(candidate["category"] for candidate in candidates)
        evidence.append(
            ResearchPersonaEvidence(
                id=evidence_id,
                source_kind=document.source_kind,
                summary=_evidence_summary(document, categories=categories),
                locator=_evidence_locator(document),
            )
        )
        for candidate in candidates:
            facts.append(_candidate_to_fact(document, candidate, evidence_id=evidence_id))
        if not candidates:
            warnings.append(_no_fact_warning(document, index=index))

    return ResearchPersonaEvidencePacket(
        documents=documents,
        evidence=evidence,
        facts=_dedupe_facts(facts),
        warnings=warnings,
    )


def build_research_persona_patch_from_sources(
    sources: Iterable[ResearchPersonaSourceDocument | Mapping[str, object]],
    *,
    reason: str | None = None,
) -> ResearchPersonaPatch:
    """Build a strict candidate patch from explicit source documents."""

    packet = build_research_persona_evidence_packet_from_sources(sources)
    source_kind = _patch_source_kind(packet.documents)
    patch_reason = _optional_string(reason) or (
        f"Candidate research persona patch from {len(packet.documents)} approved source document"
        + ("" if len(packet.documents) == 1 else "s")
        + "."
    )
    return ResearchPersonaPatch(
        source_kind=source_kind,
        reason=patch_reason,
        evidence=packet.evidence,
        operations=[
            ResearchPersonaPatchOperation(op="upsert_fact", fact=fact)
            for fact in sorted(packet.facts, key=lambda item: (item.category, item.value.casefold(), item.id))
        ],
    )


def build_research_persona_ingestion_payload(
    *,
    source_document: object | None = None,
    document: object | None = None,
    sources: object | None = None,
    source_path: str | None = None,
    privacy_default: str | None = None,
    reason: str | None = None,
    **_: object,
) -> dict[str, object]:
    """Return a JSON-ready candidate patch payload for CLI ingestion.

    This adapter accepts a single normalized source document, a list of source
    documents, or the common ``{"sources": [...]}`` / ``{"documents": [...]}``
    wrapper shape. It still treats paths as provenance only; file reads belong
    to the caller after explicit consent.
    """

    raw_sources = _coerce_source_collection(
        sources if sources is not None else source_document if source_document is not None else document
    )
    normalized_sources = [
        _apply_cli_source_defaults(source, source_path=source_path, privacy_default=privacy_default)
        for source in raw_sources
    ]
    packet = build_research_persona_evidence_packet_from_sources(normalized_sources)
    patch = build_research_persona_patch_from_sources(
        normalized_sources,
        reason=reason,
    )
    return {
        "schema_version": RESEARCH_PERSONA_SCHEMA_VERSION,
        "patch": patch.model_dump(mode="json"),
        "evidence_summary": summarize_research_persona_evidence_packet(packet),
        "privacy_defaults": _privacy_defaults_payload(privacy_default),
        "source_count": len(normalized_sources),
        "warnings": list(packet.warnings),
    }


def build_research_persona_source_patch_payload(**kwargs: object) -> dict[str, object]:
    """Compatibility alias for candidate source-ingestion payloads."""

    return build_research_persona_ingestion_payload(**kwargs)


def build_research_persona_source_patch(
    sources: Iterable[ResearchPersonaSourceDocument | Mapping[str, object]],
    *,
    reason: str | None = None,
) -> ResearchPersonaPatch:
    """Compatibility alias for patch-only source ingestion."""

    return build_research_persona_patch_from_sources(sources, reason=reason)


def summarize_research_persona_evidence_packet(
    packet: ResearchPersonaEvidencePacket | Mapping[str, object],
) -> dict[str, object]:
    """Return a prompt-facing packet summary without fact values."""

    normalized = (
        packet
        if isinstance(packet, ResearchPersonaEvidencePacket)
        else ResearchPersonaEvidencePacket.model_validate(packet)
    )
    facts_by_category: dict[str, int] = {}
    privacy_counts: dict[str, int] = {}
    for fact in normalized.facts:
        facts_by_category[fact.category] = facts_by_category.get(fact.category, 0) + 1
        privacy_counts[fact.privacy] = privacy_counts.get(fact.privacy, 0) + 1

    return {
        "schema_version": normalized.schema_version,
        "document_count": len(normalized.documents),
        "evidence_count": len(normalized.evidence),
        "fact_count": len(normalized.facts),
        "facts_by_category": dict(sorted(facts_by_category.items())),
        "privacy_counts": dict(sorted(privacy_counts.items())),
        "evidence": [
            {
                "id": item.id,
                "source_kind": item.source_kind,
                "summary": _bounded_text(item.summary or "", limit=_SUMMARY_LIMIT),
                "has_locator": bool(item.locator),
            }
            for item in normalized.evidence
        ],
        "warnings": list(normalized.warnings),
    }


def _coerce_source_collection(raw: object) -> list[Mapping[str, object]]:
    if raw is None:
        raise ValueError("source ingestion requires a source document or sources list")
    if isinstance(raw, ResearchPersonaSourceDocument):
        return [raw.model_dump(mode="python")]
    if isinstance(raw, list):
        if not all(isinstance(item, Mapping) for item in raw):
            raise ValueError("source list must contain only objects")
        return [_normalize_document_aliases(dict(item)) for item in raw]
    if isinstance(raw, Mapping):
        for key in ("sources", "documents"):
            value = raw.get(key)
            if isinstance(value, list):
                if not all(isinstance(item, Mapping) for item in value):
                    raise ValueError(f"{key} must contain only objects")
                return [_normalize_document_aliases(dict(item)) for item in value]
        return [_normalize_document_aliases(dict(raw))]
    raise ValueError("source ingestion input must be an object or list of objects")


def _normalize_document_aliases(document: dict[str, object]) -> dict[str, object]:
    raw_kind = document.pop("kind", None)
    raw_type = document.pop("type", None)
    if "source_kind" not in document:
        raw_kind = raw_kind or raw_type
        if isinstance(raw_kind, str):
            document["source_kind"] = _source_kind_alias(raw_kind)
    if "text" not in document:
        for key in _TEXT_ALIAS_KEYS:
            value = document.pop(key, None)
            if isinstance(value, str) and value.strip():
                document["text"] = value
                break
    else:
        for key in _TEXT_ALIAS_KEYS:
            document.pop(key, None)
    return document


def _source_kind_alias(value: str) -> str:
    normalized = value.strip().casefold().replace("-", "_").replace(" ", "_")
    aliases = {
        **_SOURCE_KIND_ALIASES,
    }
    return aliases.get(normalized, normalized)


def _apply_cli_source_defaults(
    source: Mapping[str, object],
    *,
    source_path: str | None,
    privacy_default: str | None,
) -> dict[str, object]:
    payload = dict(source)
    if source_path and source_path != "-" and not payload.get("path"):
        payload["path"] = source_path
    if privacy_default and privacy_default != "private_local" and not payload.get("privacy"):
        payload["privacy"] = privacy_default
    return payload


def _privacy_defaults_payload(privacy_default: str | None) -> dict[str, object]:
    return {
        "requested_default": privacy_default or "source_kind_default",
        "interview": "private_local",
        "user_statement": "private_local",
        "manual_patch": "private_local",
        "project_scan": "project_private",
        "repo_scan": "project_private",
        "paper_import": "safe_to_share for citations, project_private for notes",
        "bibtex_import": "safe_to_share for citations, project_private for notes",
        "never_prompt": "explicit only",
    }


def _patch_source_kind(documents: list[ResearchPersonaSourceDocument]) -> str:
    source_kinds = {document.source_kind for document in documents}
    if len(source_kinds) == 1:
        return next(iter(source_kinds))
    return "manual_patch"


def _evidence_id(document: ResearchPersonaSourceDocument, *, index: int) -> str:
    locator = document.locator or document.path or document.title or f"source-{index + 1}"
    prefix = _slug(locator, fallback=document.source_kind, limit=32)
    return (
        f"evidence.ingested.{document.source_kind}.{prefix}.{_stable_digest(document.model_dump(mode='json'), index)}"
    )


def _evidence_locator(document: ResearchPersonaSourceDocument) -> str | None:
    if document.privacy == "never_prompt":
        return "never_prompt_source"
    parts = [part for part in (document.path, document.locator) if part]
    if not parts:
        return None
    return _bounded_text(" :: ".join(parts), limit=_SUMMARY_LIMIT)


def _evidence_summary(document: ResearchPersonaSourceDocument, *, categories: Iterable[str]) -> str:
    if document.privacy == "never_prompt":
        return f"{document.source_kind} source redacted for never_prompt privacy; candidate categories only."

    signals: list[str] = [document.source_kind]
    if document.title:
        signals.append(f"title={_bounded_text(document.title, limit=96)}")
    elif document.path:
        signals.append(f"path={_bounded_text(document.path, limit=96)}")
    elif document.locator:
        signals.append(f"locator={_bounded_text(document.locator, limit=96)}")
    if document.metadata:
        keys = ", ".join(sorted(document.metadata)[:8])
        signals.append(f"metadata={keys}")
    category_text = ", ".join(sorted(set(categories))) or "none"
    return _bounded_text(
        f"Research persona {', '.join(signals)}; inferred categories: {category_text}.", limit=_SUMMARY_LIMIT
    )


def _no_fact_warning(document: ResearchPersonaSourceDocument, *, index: int) -> str:
    locator = document.title or document.locator or document.path or f"source {index + 1}"
    if document.privacy == "never_prompt":
        locator = "redacted never_prompt source"
    return f"No persona facts inferred from {document.source_kind} document: {_bounded_text(locator, limit=96)}"


def _fact_candidates_for_document(document: ResearchPersonaSourceDocument, *, evidence_id: str) -> list[dict[str, str]]:
    text = _document_search_text(document)
    candidates: list[dict[str, str]] = []

    for category, value in _extract_label_candidates(text):
        _append_candidate(candidates, category=category, value=value)

    for category, value in _extract_metadata_candidates(document):
        _append_candidate(candidates, category=category, value=value)

    for value in _extract_known_tools(text):
        _append_candidate(candidates, category="tool", value=value)

    for value in _extract_research_area_keywords(text):
        _append_candidate(candidates, category="research_area", value=value)

    for value in _extract_workstyle_cues(text):
        _append_candidate(candidates, category="workstyle", value=value)

    for value in _extract_scientific_taste_cues(text):
        _append_candidate(candidates, category="scientific_taste", value=value)

    if document.source_kind in _PAPER_SOURCE_KINDS:
        for category, value in _extract_paper_reference_candidates(document):
            _append_candidate(candidates, category=category, value=value)
        if document.source_kind == "bibtex_import" and document.text:
            for category, value in _extract_bibtex_candidates(document.text):
                _append_candidate(candidates, category=category, value=value)

    for candidate in candidates:
        candidate["evidence_id"] = evidence_id
    return candidates


def _document_search_text(document: ResearchPersonaSourceDocument) -> str:
    parts = [document.text or "", document.title or ""]
    parts.extend(document.metadata.values())
    return "\n".join(part for part in parts if part)


def _extract_label_candidates(text: str) -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []
    for line in text.splitlines():
        match = _LINE_LABEL_RE.match(line)
        if not match:
            continue
        label = _normalize_label(match.group("label"))
        category = _CATEGORY_BY_LABEL.get(label)
        if category is None:
            continue
        for value in _split_labeled_values(match.group("value"), category=category):
            candidates.append((category, value))
    return candidates


def _normalize_label(value: str) -> str:
    return re.sub(r"[\s_\-/]+", " ", value.casefold()).strip()


def _split_labeled_values(raw_value: str, *, category: str) -> list[str]:
    text = _compact_text(raw_value)
    if not text:
        return []
    separators = r";|\||\n"
    if category in {"research_area", "tool", "reference", "collaborator", "paper"}:
        separators = r",|;|\||\n"
    values = [_bounded_text(part) for part in re.split(separators, text) if _compact_text(part)]
    if len(values) == 1 and category in {"research_area", "tool", "collaborator"}:
        values = [
            _bounded_text(part) for part in re.split(r"\s+and\s+", values[0], flags=re.IGNORECASE) if part.strip()
        ]
    return values


def _extract_metadata_candidates(document: ResearchPersonaSourceDocument) -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []
    for raw_key, raw_value in document.metadata.items():
        label = _normalize_label(raw_key)
        category = _CATEGORY_BY_LABEL.get(label)
        if category is None:
            continue
        for value in _split_labeled_values(raw_value, category=category):
            candidates.append((category, value))
    return candidates


def _extract_known_tools(text: str) -> list[str]:
    candidates: list[str] = []
    for pattern, value in _KNOWN_TOOL_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE) and value not in candidates:
            candidates.append(value)
    return candidates


def _extract_research_area_keywords(text: str) -> list[str]:
    lowered = text.casefold()
    candidates: list[str] = []
    for keyword, value in _RESEARCH_AREA_KEYWORDS:
        if keyword in lowered and value not in candidates:
            candidates.append(value)
    return candidates


def _extract_workstyle_cues(text: str) -> list[str]:
    lowered = text.casefold()
    candidates: list[str] = []
    for keyword, value in _WORKSTYLE_CUES:
        if keyword in lowered and value not in candidates:
            candidates.append(value)
    return candidates


def _extract_scientific_taste_cues(text: str) -> list[str]:
    lowered = text.casefold()
    candidates: list[str] = []
    for keyword, value in _SCIENTIFIC_TASTE_CUES:
        if keyword in lowered and value not in candidates:
            candidates.append(value)
    return candidates


def _extract_paper_reference_candidates(document: ResearchPersonaSourceDocument) -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []
    title = document.title or _metadata_first(document.metadata, "title", "paper_title")
    if title:
        candidates.append(("paper", _paper_value(title=title, metadata=document.metadata)))

    citation_key = _metadata_first(document.metadata, "citation_key", "bibtex_key", "key")
    doi = _metadata_first(document.metadata, "doi")
    arxiv_id = _metadata_first(document.metadata, "arxiv_id", "arxiv", "eprint")
    url = _metadata_first(document.metadata, "url")
    for reference in _reference_values(citation_key=citation_key, doi=doi, arxiv_id=arxiv_id, url=url):
        candidates.append(("reference", reference))
    return candidates


def _paper_value(*, title: str, metadata: Mapping[str, str]) -> str:
    authors = _metadata_first(metadata, "authors", "author")
    year = _metadata_first(metadata, "year")
    suffix = ""
    if authors and year:
        suffix = f" ({authors}, {year})"
    elif authors:
        suffix = f" ({authors})"
    elif year:
        suffix = f" ({year})"
    return _bounded_text(f"{title}{suffix}")


def _reference_values(
    *,
    citation_key: str | None,
    doi: str | None,
    arxiv_id: str | None,
    url: str | None,
) -> list[str]:
    values: list[str] = []
    if citation_key:
        values.append(f"BibTeX key: {citation_key}")
    if doi:
        values.append(f"DOI: {doi}")
    if arxiv_id:
        values.append(f"arXiv: {arxiv_id}")
    if url:
        values.append(f"URL: {url}")
    return [_bounded_text(value) for value in values]


def _metadata_first(metadata: Mapping[str, str], *keys: str) -> str | None:
    for key in keys:
        value = metadata.get(key)
        if value:
            return value
    return None


def _extract_bibtex_candidates(text: str) -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []
    for entry in _parse_bibtex_entries(text):
        title = entry.get("title")
        if title:
            candidates.append(("paper", _paper_value(title=title, metadata=entry)))
        for reference in _reference_values(
            citation_key=entry.get("citation_key"),
            doi=entry.get("doi"),
            arxiv_id=entry.get("arxiv_id") or entry.get("eprint"),
            url=entry.get("url"),
        ):
            candidates.append(("reference", reference))
    return candidates


def _parse_bibtex_entries(text: str) -> list[dict[str, str]]:
    try:
        from pybtex.database import parse_string

        bibliography = parse_string(text, "bibtex")
    except Exception:  # noqa: BLE001
        return _parse_bibtex_entries_fallback(text)

    entries: list[dict[str, str]] = []
    for key, entry in sorted(bibliography.entries.items()):
        fields = {
            field_key.casefold().replace("-", "_"): _compact_text(value) for field_key, value in entry.fields.items()
        }
        fields["citation_key"] = _compact_text(key)
        authors = [_compact_text(person) for person in entry.persons.get("author", [])]
        if authors:
            fields["authors"] = ", ".join(authors)
        if "eprint" in fields and "arxiv" in fields.get("archiveprefix", "").casefold():
            fields["arxiv_id"] = fields["eprint"]
        entries.append({field_key: field_value for field_key, field_value in fields.items() if field_value})
    return entries


def _parse_bibtex_entries_fallback(text: str) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for entry_match in _BIBTEX_ENTRY_FALLBACK_RE.finditer(text):
        fields: dict[str, str] = {"citation_key": _compact_text(entry_match.group("key"))}
        body = entry_match.group("body")
        for field_match in _BIBTEX_FIELD_FALLBACK_RE.finditer(body):
            key = field_match.group("key").casefold().replace("-", "_")
            value = field_match.group("value").strip().strip('{}"')
            normalized = _compact_text(value)
            if normalized:
                fields[key] = normalized
        if "eprint" in fields and "arxiv" in fields.get("archiveprefix", "").casefold():
            fields["arxiv_id"] = fields["eprint"]
        entries.append(fields)
    return entries


def _append_candidate(candidates: list[dict[str, str]], *, category: str, value: str) -> None:
    normalized = _bounded_text(value)
    if not normalized:
        return
    key = (category.casefold(), normalized.casefold())
    for existing in candidates:
        if (existing["category"].casefold(), existing["value"].casefold()) == key:
            return
    candidates.append({"category": category, "value": normalized})


def _candidate_to_fact(
    document: ResearchPersonaSourceDocument,
    candidate: Mapping[str, str],
    *,
    evidence_id: str,
) -> ResearchPersonaFact:
    category = candidate["category"]
    value = candidate["value"]
    return ResearchPersonaFact(
        id=_fact_id(category=category, value=value),
        category=category,
        value=value,
        confidence="confirmed" if document.confirmed else "inferred",
        privacy=_fact_privacy(document, category=category),
        sources=[document.source_kind],
        evidence_refs=[evidence_id],
    )


def _fact_id(*, category: str, value: str) -> str:
    return f"fact.ingested.{category}.{_slug(value, fallback=category)}.{_stable_digest(category, value.casefold())}"


def _fact_privacy(document: ResearchPersonaSourceDocument, *, category: str) -> str:
    if document.privacy is not None:
        return document.privacy
    if document.safe_to_share:
        return "safe_to_share"
    if document.source_kind in _PAPER_SOURCE_KINDS and category in _REFERENCE_CATEGORIES:
        return "safe_to_share"
    if document.source_kind in _PAPER_SOURCE_KINDS or document.source_kind in _PROJECT_SOURCE_KINDS:
        return "project_private"
    if document.source_kind in _LOCAL_SOURCE_KINDS:
        return "private_local"
    return "private_local"


def _dedupe_facts(facts: list[ResearchPersonaFact]) -> list[ResearchPersonaFact]:
    merged: dict[tuple[str, str], ResearchPersonaFact] = {}
    for fact in facts:
        key = (fact.category, fact.value.casefold())
        existing = merged.get(key)
        if existing is None:
            merged[key] = fact
            continue
        merged[key] = ResearchPersonaFact(
            id=existing.id,
            category=existing.category,
            value=existing.value,
            confidence=_merge_confidence(existing.confidence, fact.confidence),
            privacy=_merge_privacy(existing.privacy, fact.privacy),
            sources=_dedupe_strings([*existing.sources, *fact.sources]),
            evidence_refs=_dedupe_strings([*existing.evidence_refs, *fact.evidence_refs]),
        )
    return list(merged.values())


def _merge_privacy(first: str, second: str) -> str:
    return min((first, second), key=lambda item: _PRIVACY_RESTRICTIVENESS.get(item, 99))


def _merge_confidence(first: str, second: str) -> str:
    return min((first, second), key=lambda item: _CONFIDENCE_RANK.get(item, 99))


def _dedupe_strings(values: Iterable[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped
