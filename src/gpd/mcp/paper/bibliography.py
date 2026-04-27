"""Bibliography generation pipeline: pybtex + arXiv enrichment.

Creates BibTeX entries from research provenance data, enriches them
via arXiv APIs, and writes .bib files using pybtex.

The module also exposes machine-readable audit helpers so higher-level
review and publication workflows can reason about citation quality
without reparsing BibTeX.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pybtex.database import BibliographyData, Entry
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic import ValidationError as PydanticValidationError

logger = logging.getLogger(__name__)

_BIBTEX_KEY_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]*$")


class CitationSource(BaseModel):
    """A citation source from the research provenance chain."""

    model_config = ConfigDict(extra="forbid")

    source_type: Literal["paper", "tool", "data", "website"]
    reference_id: str | None = None
    bibtex_key: str | None = None
    title: str
    authors: list[str] = Field(default_factory=list)
    year: str = ""
    arxiv_id: str | None = None
    doi: str | None = None
    url: str | None = None
    journal: str = ""
    volume: str = ""
    pages: str = ""

    @field_validator("authors", mode="before")
    @classmethod
    def _normalize_authors(cls, value: object) -> object:
        if not isinstance(value, list):
            return value
        normalized: list[object] = []
        for item in value:
            if not isinstance(item, str):
                normalized.append(item)
                continue
            stripped = item.strip()
            if not stripped:
                raise ValueError("authors must not contain blank entries")
            normalized.append(stripped)
        return normalized


def _citation_source_label(source_path: str | None = None, index: int | None = None) -> str:
    label = "citation source"
    if source_path:
        label = f"{label} {source_path}"
    if index is not None:
        label = f"{label}[{index}]"
    return label


def parse_citation_source_payload(
    payload: object,
    *,
    source_path: str | None = None,
    index: int | None = None,
) -> CitationSource:
    """Parse one strict citation-source payload.

    The model boundary stays closed through :class:`CitationSource` itself;
    this helper only adds the non-blank ``reference_id`` requirement that the
    sidecar contract imposes on project-local reuse.
    """

    label = _citation_source_label(source_path, index)
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")

    try:
        source = CitationSource.model_validate(payload)
    except PydanticValidationError as exc:
        details: list[str] = []
        for error in exc.errors()[:3]:
            location = ".".join(str(part) for part in error.get("loc", ()))
            prefix = f"{label}.{location}" if location else label
            message = str(error.get("msg", "validation failed")).strip() or "validation failed"
            details.append(f"{prefix}: {message}")
        raise ValueError("; ".join(details)) from exc

    reference_id = source.reference_id.strip() if isinstance(source.reference_id, str) else ""
    if not reference_id:
        raise ValueError(f"{label}.reference_id must be a non-empty string")
    if not source.title.strip():
        raise ValueError(f"{label}.title must be a non-empty string")
    if any(not author.strip() for author in source.authors):
        raise ValueError(f"{label}.authors entries must be non-empty strings")

    return source.model_copy(update={"reference_id": reference_id})


def parse_citation_source_sidecar_payload(
    payload: object,
    *,
    source_path: str | None = None,
) -> list[CitationSource]:
    """Parse a citation-source sidecar payload from a JSON array."""

    label = source_path or "citation source sidecar"
    if not isinstance(payload, list):
        raise ValueError(f"{label} must be a JSON array")

    sources: list[CitationSource] = []
    seen_reference_ids: dict[str, int] = {}
    for index, item in enumerate(payload):
        source = parse_citation_source_payload(item, source_path=source_path, index=index)
        reference_id = source.reference_id or ""
        if reference_id in seen_reference_ids:
            raise ValueError(
                f"{label}[{index}].reference_id duplicates {reference_id!r} "
                f"from entry {seen_reference_ids[reference_id]}"
            )
        seen_reference_ids[reference_id] = index
        sources.append(source)
    return sources


CitationResolutionStatus = Literal["provided", "enriched", "incomplete", "failed"]
CitationVerificationStatus = Literal["verified", "partial", "unverified"]


class CitationAuditRecord(BaseModel):
    """Machine-readable audit record for a citation source."""

    model_config = ConfigDict(extra="forbid")

    key: str
    source_type: Literal["paper", "tool", "data", "website"]
    reference_id: str | None = None
    title: str
    resolution_status: CitationResolutionStatus
    verification_status: CitationVerificationStatus
    verification_sources: list[str] = Field(default_factory=list)
    canonical_identifiers: list[str] = Field(default_factory=list)
    missing_core_fields: list[str] = Field(default_factory=list)
    enriched_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class BibliographyAudit(BaseModel):
    """Summary audit artifact for a bibliography emission batch."""

    model_config = ConfigDict(extra="forbid")

    generated_at: str
    total_sources: int
    resolved_sources: int
    partial_sources: int
    unverified_sources: int
    failed_sources: int
    entries: list[CitationAuditRecord]


# ---- BibTeX entry creation ----


def _preferred_bibtex_key(source: CitationSource) -> str | None:
    """Return the preferred BibTeX key when one is provided."""
    if source.bibtex_key is None:
        return None

    preferred = source.bibtex_key.strip()
    if not preferred:
        return None
    if not _BIBTEX_KEY_RE.fullmatch(preferred):
        raise ValueError(
            "preferred bibtex_key must start with an ASCII letter and contain only "
            "ASCII letters, digits, '.', '_', ':', or '-'"
        )
    return preferred


def _safe_bibtex_key_suffix(value: str) -> str:
    """Return a BibTeX-key-safe suffix component."""

    return re.sub(r"[^A-Za-z0-9_.:-]", "", value)


def _validate_unique_reference_ids(sources: list[CitationSource]) -> None:
    """Reject duplicate citation reference ids before a mapping can overwrite them."""

    seen: dict[str, int] = {}
    for index, source in enumerate(sources):
        reference_id = source.reference_id.strip() if isinstance(source.reference_id, str) else ""
        if not reference_id:
            continue
        if reference_id in seen:
            raise ValueError(
                f"citation source reference_id {reference_id!r} duplicates entries {seen[reference_id]} and {index}"
            )
        seen[reference_id] = index


def _create_bib_key(source: CitationSource, existing_keys: set[str]) -> str:
    """Generate a BibTeX key from a preferred key or first author last name + year.

    Deduplicates by appending a/b/c suffix.
    """
    preferred_key = _preferred_bibtex_key(source)
    if preferred_key:
        base_key = preferred_key
    elif source.authors:
        # Extract last name from first author (handle "First Last" and "Last, First")
        first_author = source.authors[0]
        if "," in first_author:
            last_name = first_author.split(",")[0].strip()
        else:
            parts = first_author.strip().split()
            last_name = parts[-1] if parts else "unknown"
        base_key = re.sub(r"[^a-zA-Z]", "", last_name).lower() or "unknown"
    else:
        base_key = "unknown"

    if not preferred_key:
        base_key = f"{base_key}{_safe_bibtex_key_suffix(source.year)}"
        if not _BIBTEX_KEY_RE.fullmatch(base_key):
            raise ValueError("generated BibTeX key is not safe")

    if base_key not in existing_keys:
        return base_key

    # Deduplicate with a/b/c suffix, then numeric suffixes for 27+
    for suffix in "abcdefghijklmnopqrstuvwxyz":
        candidate = f"{base_key}{suffix}"
        if candidate not in existing_keys:
            return candidate

    n = 27
    while True:
        candidate = f"{base_key}_{n}"
        if candidate not in existing_keys:
            return candidate
        n += 1


_SOURCE_TYPE_TO_BIBTEX = {
    "paper": "article",
    "tool": "misc",
    "data": "misc",
    "website": "misc",
}


# ---- Author field sanitization ----

# Patterns that match "et al." variants (with optional leading comma/and)
_ET_AL_RE = re.compile(
    r",?\s*\band\s+(?:et\s*al\.?)\b"  # "and et al."
    r"|,?\s*\bet\s*\.?\s*al\.?\b"  # "et al." / "etal." / "et. al."
    r"|,?\s*\bet\s+alia\b",  # "et alia"
    re.IGNORECASE,
)

# Characters safe in BibTeX author fields: Basic Latin, Latin Extended-A/B,
# common punctuation.  Anything outside this set is stripped.
_SAFE_BIB_CHAR_RE = re.compile(r"[^\x20-\x7E\u00C0-\u024F]")

_LATEX_UNICODE_REPLACEMENTS: dict[str, str] = {
    "Α": r"{\ensuremath{A}}",
    "Β": r"{\ensuremath{B}}",
    "Γ": r"{\ensuremath{\Gamma}}",
    "Δ": r"{\ensuremath{\Delta}}",
    "Ε": r"{\ensuremath{E}}",
    "Ζ": r"{\ensuremath{Z}}",
    "Η": r"{\ensuremath{H}}",
    "Θ": r"{\ensuremath{\Theta}}",
    "Ι": r"{\ensuremath{I}}",
    "Κ": r"{\ensuremath{K}}",
    "Λ": r"{\ensuremath{\Lambda}}",
    "Μ": r"{\ensuremath{M}}",
    "Ν": r"{\ensuremath{N}}",
    "Ξ": r"{\ensuremath{\Xi}}",
    "Ο": r"{\ensuremath{O}}",
    "Π": r"{\ensuremath{\Pi}}",
    "Ρ": r"{\ensuremath{P}}",
    "Σ": r"{\ensuremath{\Sigma}}",
    "Τ": r"{\ensuremath{T}}",
    "Υ": r"{\ensuremath{\Upsilon}}",
    "Φ": r"{\ensuremath{\Phi}}",
    "Χ": r"{\ensuremath{X}}",
    "Ψ": r"{\ensuremath{\Psi}}",
    "Ω": r"{\ensuremath{\Omega}}",
    "α": r"{\ensuremath{\alpha}}",
    "β": r"{\ensuremath{\beta}}",
    "γ": r"{\ensuremath{\gamma}}",
    "δ": r"{\ensuremath{\delta}}",
    "ε": r"{\ensuremath{\epsilon}}",
    "ζ": r"{\ensuremath{\zeta}}",
    "η": r"{\ensuremath{\eta}}",
    "θ": r"{\ensuremath{\theta}}",
    "ι": r"{\ensuremath{\iota}}",
    "κ": r"{\ensuremath{\kappa}}",
    "λ": r"{\ensuremath{\lambda}}",
    "μ": r"{\ensuremath{\mu}}",
    "ν": r"{\ensuremath{\nu}}",
    "ξ": r"{\ensuremath{\xi}}",
    "ο": r"{\ensuremath{o}}",
    "π": r"{\ensuremath{\pi}}",
    "ρ": r"{\ensuremath{\rho}}",
    "σ": r"{\ensuremath{\sigma}}",
    "ς": r"{\ensuremath{\sigma}}",
    "τ": r"{\ensuremath{\tau}}",
    "υ": r"{\ensuremath{\upsilon}}",
    "φ": r"{\ensuremath{\phi}}",
    "χ": r"{\ensuremath{\chi}}",
    "ψ": r"{\ensuremath{\psi}}",
    "ω": r"{\ensuremath{\omega}}",
    "ϵ": r"{\ensuremath{\epsilon}}",
    "ϑ": r"{\ensuremath{\vartheta}}",
    "ϕ": r"{\ensuremath{\varphi}}",
    "ℏ": r"{\ensuremath{\hbar}}",
    "ħ": r"{\ensuremath{\hbar}}",
    "∂": r"{\ensuremath{\partial}}",
    "∇": r"{\ensuremath{\nabla}}",
    "∞": r"{\ensuremath{\infty}}",
    "±": r"{\ensuremath{\pm}}",
    "∓": r"{\ensuremath{\mp}}",
    "×": r"{\ensuremath{\times}}",
    "·": r"{\ensuremath{\cdot}}",
    "≤": r"{\ensuremath{\leq}}",
    "≥": r"{\ensuremath{\geq}}",
    "≠": r"{\ensuremath{\neq}}",
    "≈": r"{\ensuremath{\approx}}",
    "≃": r"{\ensuremath{\simeq}}",
    "∼": r"{\ensuremath{\sim}}",
    "∝": r"{\ensuremath{\propto}}",
    "∈": r"{\ensuremath{\in}}",
    "∉": r"{\ensuremath{\notin}}",
    "⊂": r"{\ensuremath{\subset}}",
    "⊃": r"{\ensuremath{\supset}}",
    "⊆": r"{\ensuremath{\subseteq}}",
    "⊇": r"{\ensuremath{\supseteq}}",
    "∑": r"{\ensuremath{\sum}}",
    "∏": r"{\ensuremath{\prod}}",
    "∫": r"{\ensuremath{\int}}",
    "⟨": r"{\ensuremath{\langle}}",
    "⟩": r"{\ensuremath{\rangle}}",
    "→": r"{\ensuremath{\to}}",
    "←": r"{\ensuremath{\leftarrow}}",
    "↔": r"{\ensuremath{\leftrightarrow}}",
    "⇒": r"{\ensuremath{\Rightarrow}}",
    "⇔": r"{\ensuremath{\Leftrightarrow}}",
    "†": r"{\ensuremath{\dagger}}",
    "‡": r"{\ensuremath{\ddagger}}",
    "′": r"{\ensuremath{'}}",
    "″": r"{\ensuremath{''}}",
    "°": r"{\ensuremath{^\circ}}",
    "¹": r"{\ensuremath{^1}}",
    "²": r"{\ensuremath{^2}}",
    "³": r"{\ensuremath{^3}}",
    "⁰": r"{\ensuremath{^0}}",
    "⁴": r"{\ensuremath{^4}}",
    "⁵": r"{\ensuremath{^5}}",
    "⁶": r"{\ensuremath{^6}}",
    "⁷": r"{\ensuremath{^7}}",
    "⁸": r"{\ensuremath{^8}}",
    "⁹": r"{\ensuremath{^9}}",
    "₀": r"{\ensuremath{_0}}",
    "₁": r"{\ensuremath{_1}}",
    "₂": r"{\ensuremath{_2}}",
    "₃": r"{\ensuremath{_3}}",
    "₄": r"{\ensuremath{_4}}",
    "₅": r"{\ensuremath{_5}}",
    "₆": r"{\ensuremath{_6}}",
    "₇": r"{\ensuremath{_7}}",
    "₈": r"{\ensuremath{_8}}",
    "₉": r"{\ensuremath{_9}}",
    "–": "--",
    "—": "---",
    "−": "-",
    "‐": "-",
    "‑": "-",
    "“": "``",
    "”": "''",
    "‘": "`",
    "’": "'",
    "…": r"\ldots{}",
    "\u00a0": " ",
}

_LATEX_ACCENT_COMMANDS: dict[str, str] = {
    "\u0300": r"\`",
    "\u0301": r"\'",
    "\u0302": r"\^",
    "\u0303": r"\~",
    "\u0304": r"\=",
    "\u0306": r"\u",
    "\u0307": r"\.",
    "\u0308": '\\"',
    "\u030a": r"\r",
    "\u030b": r"\H",
    "\u030c": r"\v",
    "\u0327": r"\c",
    "\u0328": r"\k",
}


def sanitize_bib_author_field(author_string: str) -> str:
    """Sanitize a BibTeX author field to prevent LaTeX compilation errors.

    - Replaces ``et al.`` variants with ``and others`` (proper BibTeX).
    - Strips characters outside the Basic Latin + Latin Extended range that
      would cause ``Unicode character ... not set up for use with LaTeX``.
    - Collapses resulting whitespace.
    """
    # Replace "et al." with "and others"
    cleaned = _ET_AL_RE.sub("", author_string)
    # If "et al." was at the end, append "and others"
    if _ET_AL_RE.search(author_string):
        cleaned = cleaned.rstrip().rstrip(",.").rstrip()
        if not cleaned.endswith("and others"):
            cleaned = cleaned + " and others"

    # Strip non-Latin characters that would break pdflatex
    sanitized = _SAFE_BIB_CHAR_RE.sub("", cleaned)
    if sanitized != cleaned:
        logger.warning(
            "Stripped non-Latin characters from BibTeX author field: %r -> %r",
            cleaned,
            sanitized,
        )

    # Collapse whitespace
    return re.sub(r"\s{2,}", " ", sanitized).strip()


def sanitize_bib_authors(authors: list[str]) -> list[str]:
    """Sanitize a list of author names for BibTeX.

    Handles per-author ``et al.`` replacement and non-Latin character
    stripping, then returns the cleaned list with ``others`` appended
    if any author contained an ``et al.`` marker.
    """
    cleaned: list[str] = []
    has_et_al = False

    for author in authors:
        if _ET_AL_RE.search(author):
            has_et_al = True
            # Strip the "et al." portion from this author name
            name = _ET_AL_RE.sub("", author).strip().rstrip(",.").strip()
            if name:
                name = _SAFE_BIB_CHAR_RE.sub("", name)
                if name.strip():
                    cleaned.append(name.strip())
        else:
            sanitized = _SAFE_BIB_CHAR_RE.sub("", author)
            if sanitized != author:
                logger.warning(
                    "Stripped non-Latin characters from author name: %r -> %r",
                    author,
                    sanitized,
                )
            if sanitized.strip():
                cleaned.append(sanitized.strip())

    if has_et_al and not any(a.lower() == "others" for a in cleaned):
        cleaned.append("others")

    return cleaned


def _latex_accented_ascii(char: str) -> str | None:
    decomposed = unicodedata.normalize("NFD", char)
    if not decomposed:
        return ""

    base = decomposed[0]
    accents = decomposed[1:]
    if not accents or not base.isascii():
        return None

    rendered = base
    for accent in accents:
        command = _LATEX_ACCENT_COMMANDS.get(accent)
        if command is None:
            return None
        rendered = f"{command}{{{rendered}}}"
    return f"{{{rendered}}}"


def _ascii_fallback_for_unicode(char: str) -> str:
    accented = _latex_accented_ascii(char)
    if accented is not None:
        return accented

    normalized = unicodedata.normalize("NFKD", char).encode("ascii", "ignore").decode("ascii")
    return normalized


def sanitize_bibtex_text_field(value: str, *, field_name: str) -> str:
    """Sanitize prose BibTeX fields that LaTeX will typeset directly."""
    rendered: list[str] = []
    changed = False

    for char in value:
        if "\x20" <= char <= "\x7e":
            rendered.append(char)
            continue

        replacement = _LATEX_UNICODE_REPLACEMENTS.get(char)
        if replacement is None:
            replacement = _ascii_fallback_for_unicode(char)
        if replacement != char:
            changed = True
        rendered.append(replacement)

    sanitized = "".join(rendered)
    if changed:
        logger.warning(
            "Sanitized unsupported Unicode from BibTeX %s field: %r -> %r",
            field_name,
            value,
            sanitized,
        )
    return sanitized


def _source_to_entry(source: CitationSource, existing_keys: set[str]) -> tuple[str, Entry]:
    """Convert a CitationSource to a pybtex Entry."""
    key = _create_bib_key(source, existing_keys)
    entry_type = _SOURCE_TYPE_TO_BIBTEX[source.source_type]

    fields: list[tuple[str, str]] = []
    if source.authors:
        safe_authors = sanitize_bib_authors(source.authors)
        fields.append(("author", " and ".join(safe_authors)))
    fields.append(("title", sanitize_bibtex_text_field(source.title, field_name="title")))
    if source.journal:
        fields.append(("journal", sanitize_bibtex_text_field(source.journal, field_name="journal")))
    if source.year:
        fields.append(("year", source.year))
    if source.volume:
        fields.append(("volume", source.volume))
    if source.pages:
        fields.append(("pages", source.pages))
    if source.doi:
        fields.append(("doi", source.doi))
    if source.url:
        fields.append(("url", source.url))
    if source.arxiv_id:
        fields.append(("note", sanitize_bibtex_text_field(f"arXiv:{source.arxiv_id}", field_name="note")))

    return key, Entry(entry_type, fields)


def _core_missing_fields(source: CitationSource) -> list[str]:
    """Return the minimal fields needed for a trustworthy paper-style citation."""
    missing: list[str] = []
    if not source.title.strip():
        missing.append("title")
    if not source.authors:
        missing.append("authors")
    if not source.year.strip():
        missing.append("year")
    return missing


def _canonical_identifiers(source: CitationSource) -> list[str]:
    """Return normalized identifiers usable by audit/reporting layers."""
    identifiers: list[str] = []
    if source.doi:
        identifiers.append(f"doi:{source.doi}")
    if source.arxiv_id:
        identifiers.append(f"arxiv:{source.arxiv_id}")
    if source.url:
        identifiers.append(f"url:{source.url}")
    return identifiers


def audit_citation_source(
    source: CitationSource,
    existing_keys: set[str] | None = None,
    *,
    enrich: bool = True,
) -> tuple[CitationSource, CitationAuditRecord]:
    """Audit one source and optionally enrich it before bibliography emission."""
    existing = existing_keys or set()
    original_missing = _core_missing_fields(source)
    resolved = source
    resolution_status: CitationResolutionStatus = "provided"
    verification_status: CitationVerificationStatus = "unverified"
    verification_sources: list[str] = []
    warnings: list[str] = []
    errors: list[str] = []
    enriched_fields: list[str] = []

    if original_missing:
        resolution_status = "incomplete"

    should_enrich = bool(enrich and source.arxiv_id and original_missing)
    if should_enrich:
        try:
            resolved = enrich_from_arxiv(source)
        except Exception as exc:
            resolution_status = "failed"
            errors.append(str(exc))
        else:
            verification_sources.append("arXiv")
            enriched_fields = [
                field
                for field in ("title", "authors", "year")
                if (
                    (field == "authors" and not getattr(source, field) and getattr(resolved, field))
                    or (
                        field != "authors"
                        and not str(getattr(source, field)).strip()
                        and str(getattr(resolved, field)).strip()
                    )
                )
            ]
            resolution_status = "enriched" if not _core_missing_fields(resolved) else "incomplete"
            verification_status = "verified" if resolution_status == "enriched" else "partial"

    missing_after = _core_missing_fields(resolved)
    identifiers = _canonical_identifiers(resolved)

    if resolution_status == "provided":
        if missing_after:
            resolution_status = "incomplete"
        elif identifiers:
            verification_status = "partial"
            warnings.append("Canonical identifiers were provided by the caller but not externally verified")

    if resolution_status == "incomplete" and not errors:
        warnings.append(f"Missing core citation fields: {', '.join(missing_after)}")
    if not identifiers:
        warnings.append("No canonical identifier available")

    key = _create_bib_key(resolved, existing)
    record = CitationAuditRecord(
        key=key,
        source_type=resolved.source_type,
        reference_id=resolved.reference_id,
        title=resolved.title,
        resolution_status=resolution_status,
        verification_status=verification_status,
        verification_sources=verification_sources,
        canonical_identifiers=identifiers,
        missing_core_fields=missing_after,
        enriched_fields=enriched_fields,
        warnings=warnings,
        errors=errors,
    )
    return resolved, record


def _resolve_sources_for_bibliography(
    sources: list[CitationSource],
    *,
    enrich: bool,
    existing_keys: set[str] | None = None,
) -> tuple[list[CitationSource], list[CitationAuditRecord]]:
    """Resolve citation sources and reserve keys exactly as bibliography emission will."""
    _validate_unique_reference_ids(sources)

    audited_sources: list[CitationSource] = []
    audit_entries: list[CitationAuditRecord] = []
    reserved_keys = set(existing_keys or ())

    for source in sources:
        resolved, audit_record = audit_citation_source(source, reserved_keys, enrich=enrich)
        audited_sources.append(resolved)
        audit_entries.append(audit_record)
        reserved_keys.add(audit_record.key)

    return audited_sources, audit_entries


def bibliography_entries_from_sources(
    sources: list[CitationSource],
    existing_keys: set[str] | None = None,
) -> list[tuple[str, Entry]]:
    """Build ordered `(key, entry)` pairs for citation sources.

    This is the single key-generation path for bibliography emission so
    other parts of the pipeline can reuse the exact emitted citation keys.
    """
    _validate_unique_reference_ids(sources)

    entries: list[tuple[str, Entry]] = []
    reserved_keys = set(existing_keys or ())

    for source in sources:
        key, entry = _source_to_entry(source, reserved_keys)
        reserved_keys.add(key)
        entries.append((key, entry))

    return entries


def citation_keys_for_sources(
    sources: list[CitationSource],
    *,
    enrich: bool = False,
    existing_keys: set[str] | None = None,
) -> list[str]:
    """Return bibliography keys in the exact order they will be emitted."""
    resolved_sources = sources
    if enrich:
        resolved_sources, _audit_entries = _resolve_sources_for_bibliography(
            sources,
            enrich=True,
            existing_keys=existing_keys,
        )
    return [key for key, _entry in bibliography_entries_from_sources(resolved_sources, existing_keys=existing_keys)]


def create_bibliography(
    sources: list[CitationSource],
    existing_keys: set[str] | None = None,
) -> BibliographyData:
    """Convert all citation sources to a BibliographyData object."""
    bib = BibliographyData()
    for key, entry in bibliography_entries_from_sources(sources, existing_keys=existing_keys):
        bib.entries[key] = entry

    return bib


def write_bib_file(bib_data: BibliographyData, output_path: Path) -> None:
    """Write a .bib file using pybtex."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    bib_data.to_file(str(output_path), "bibtex")


def write_bibliography_audit(audit: BibliographyAudit, output_path: Path) -> None:
    """Write a machine-readable bibliography audit artifact as JSON."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(audit.model_dump_json(indent=2), encoding="utf-8")


def _entry_field(entry: Entry, field_name: str) -> str:
    """Return a normalized BibTeX field value."""
    value = entry.fields.get(field_name, "")
    return str(value).strip()


def _entry_authors(entry: Entry) -> list[str]:
    """Return author strings from a pybtex entry."""
    persons = entry.persons.get("author", [])
    if persons:
        return [str(person).strip() for person in persons if str(person).strip()]

    author_field = _entry_field(entry, "author")
    if not author_field:
        return []

    return [part.strip() for part in author_field.split(" and ") if part.strip()]


def _entry_core_missing_fields(entry: Entry) -> list[str]:
    """Return the core fields missing from an emitted BibTeX entry."""
    missing: list[str] = []
    if not _entry_field(entry, "title"):
        missing.append("title")
    if not _entry_authors(entry):
        missing.append("authors")
    if not _entry_field(entry, "year"):
        missing.append("year")
    return missing


def _entry_canonical_identifiers(entry: Entry) -> list[str]:
    """Return normalized identifiers extracted from a BibTeX entry."""
    identifiers: list[str] = []
    doi = _entry_field(entry, "doi")
    if doi:
        identifiers.append(f"doi:{doi}")

    eprint = _entry_field(entry, "eprint")
    archive_prefix = (_entry_field(entry, "archiveprefix") or _entry_field(entry, "archivePrefix")).lower()
    if eprint and archive_prefix == "arxiv":
        identifiers.append(f"arxiv:{eprint}")
    else:
        note = _entry_field(entry, "note")
        match = re.search(r"arXiv[:\s]+([^\s,;]+)", note, re.IGNORECASE)
        if match:
            identifiers.append(f"arxiv:{match.group(1)}")

    url = _entry_field(entry, "url")
    if url:
        identifiers.append(f"url:{url}")

    return identifiers


def _entry_source_type(entry: Entry) -> Literal["paper", "tool", "data", "website"]:
    """Coarsely classify a plain BibTeX entry for audit reporting."""
    entry_type = entry.type.lower()
    if entry_type == "misc":
        if _entry_field(entry, "url") and not _entry_authors(entry):
            return "website"
        return "tool"

    if entry_type in {
        "article",
        "inproceedings",
        "proceedings",
        "book",
        "incollection",
        "phdthesis",
        "mastersthesis",
        "techreport",
        "manual",
    }:
        return "paper"

    return "paper"


def _bibliography_audit_record_from_entry(
    key: str,
    entry: Entry,
) -> CitationAuditRecord:
    """Build an audit record for a plain BibTeX entry."""
    missing_core_fields = _entry_core_missing_fields(entry)
    canonical_identifiers = _entry_canonical_identifiers(entry)
    warnings: list[str] = []
    if missing_core_fields:
        warnings.append(f"Missing core citation fields: {', '.join(missing_core_fields)}")
    if not canonical_identifiers:
        warnings.append("No canonical identifier available")

    return CitationAuditRecord(
        key=key,
        source_type=_entry_source_type(entry),
        reference_id=None,
        title=_entry_field(entry, "title"),
        resolution_status="provided" if not missing_core_fields else "incomplete",
        verification_status="unverified",
        verification_sources=[],
        canonical_identifiers=canonical_identifiers,
        missing_core_fields=missing_core_fields,
        enriched_fields=[],
        warnings=warnings,
        errors=[],
    )


def _bibliography_audit_from_entries(
    bib_data: BibliographyData,
    source_records_by_key: dict[str, CitationAuditRecord] | None = None,
) -> BibliographyAudit:
    """Summarize the emitted bibliography as a machine-readable audit."""
    audit_entries: list[CitationAuditRecord] = []

    for key, entry in bib_data.entries.items():
        source_record = source_records_by_key.get(key) if source_records_by_key else None
        if source_record is not None:
            audit_entries.append(
                source_record if source_record.key == key else source_record.model_copy(update={"key": key})
            )
        else:
            audit_entries.append(_bibliography_audit_record_from_entry(key, entry))

    return BibliographyAudit(
        generated_at=datetime.now(UTC).isoformat(),
        total_sources=len(audit_entries),
        resolved_sources=sum(1 for entry in audit_entries if entry.resolution_status in {"provided", "enriched"}),
        partial_sources=sum(1 for entry in audit_entries if entry.verification_status == "partial"),
        unverified_sources=sum(1 for entry in audit_entries if entry.verification_status == "unverified"),
        failed_sources=sum(1 for entry in audit_entries if entry.resolution_status == "failed"),
        entries=audit_entries,
    )


def audit_bibliography(
    bib_data: BibliographyData,
    citation_sources: list[CitationSource] | None = None,
    source_audit_entries: list[CitationAuditRecord] | None = None,
    enrich: bool = True,
    existing_keys: set[str] | None = None,
) -> BibliographyAudit:
    """Audit a final bibliography, mixing source-backed and plain BibTeX entries.

    Plain BibTeX entries are treated as provided, unverified citations.
    Citation-source inputs, when supplied, are resolved first so the audit
    preserves their existing verification and enrichment metadata.
    """
    source_records_by_key: dict[str, CitationAuditRecord] | None = None
    if source_audit_entries is not None:
        source_records_by_key = {entry.key: entry for entry in source_audit_entries}
    elif citation_sources is not None:
        _audited_sources, audit_entries = _resolve_sources_for_bibliography(
            citation_sources,
            enrich=enrich,
            existing_keys=existing_keys,
        )
        source_records_by_key = {entry.key: entry for entry in audit_entries}

    return _bibliography_audit_from_entries(bib_data, source_records_by_key)


# ---- arXiv metadata to BibTeX ----


def enrich_from_arxiv(source: CitationSource) -> CitationSource:
    """Enrich a citation source with arXiv metadata if available.

    If source has arxiv_id but missing title/authors/year, look up via
    the ``arxiv`` Python package and fill in missing fields.  Returns
    updated source.  Raises on failure.
    """
    if not source.arxiv_id:
        return source

    if source.title and source.authors and source.year:
        return source  # Already complete

    import arxiv

    search = arxiv.Search(id_list=[source.arxiv_id], max_results=1)
    client = arxiv.Client(delay_seconds=0.0, num_retries=1)
    results = list(client.results(search))
    if not results:
        raise LookupError(f"arXiv returned no results for {source.arxiv_id}")

    paper = results[0]
    return source.model_copy(
        update={
            "title": source.title or paper.title,
            "authors": source.authors or [a.name for a in paper.authors],
            "year": source.year or (str(paper.published.year) if paper.published else ""),
        }
    )


# ---- Orchestrator ----


def build_bibliography_with_audit(
    sources: list[CitationSource],
    enrich: bool = True,
    existing_keys: set[str] | None = None,
) -> tuple[BibliographyData, BibliographyAudit]:
    """Build both the BibTeX payload and a machine-readable audit artifact."""
    audited_sources, audit_entries = _resolve_sources_for_bibliography(
        sources,
        enrich=enrich,
        existing_keys=existing_keys,
    )
    emitted_entries = bibliography_entries_from_sources(audited_sources, existing_keys=existing_keys)
    normalized_audit_entries: list[CitationAuditRecord] = []
    bib = BibliographyData()
    for audit_entry, (key, entry) in zip(audit_entries, emitted_entries, strict=False):
        bib.entries[key] = entry
        if audit_entry.key == key:
            normalized_audit_entries.append(audit_entry)
        else:
            normalized_audit_entries.append(audit_entry.model_copy(update={"key": key}))

    source_records_by_key = {entry.key: entry for entry in normalized_audit_entries}
    return bib, _bibliography_audit_from_entries(bib, source_records_by_key)


def build_bibliography(sources: list[CitationSource], enrich: bool = True) -> BibliographyData:
    """Build a BibliographyData from citation sources with optional enrichment.

    This is the main public API for the bibliography module.

    Args:
        sources: List of citation sources from the provenance chain.
        enrich: If True, attempt arXiv enrichment for incomplete sources.
    """
    bib, _audit = build_bibliography_with_audit(sources, enrich=enrich)
    return bib
