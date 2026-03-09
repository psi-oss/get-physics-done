"""Reference loading system for GPD bundles.

Loads markdown reference files from specs/references/, parses YAML frontmatter
metadata (load_when, tier, context_cost), and provides indexed access to
protocols, error classes, verification checklists, and subfield guides.

Indexes are built lazily from shared-protocols.md, llm-physics-errors.md,
and physics-subfields.md markdown tables. LRU cache with configurable max size.

Layer 1 code: stdlib + pathlib + pydantic + yaml only.
"""

from __future__ import annotations

import logging
import re
from collections import OrderedDict
from enum import StrEnum
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from gpd.core.constants import (
    DEFAULT_LOADER_CACHE_SIZE,
    REF_ERROR_CATALOG_PREFIX,
    REF_PROTOCOL_PREFIX,
    REF_SUBFIELD_GUIDE_FALLBACK,
    REF_SUBFIELD_PREFIX,
    REF_VERIFICATION_DOMAIN_PREFIX,
    SPECS_REFERENCES_DIR,
)
from gpd.core.errors import LoaderError
from gpd.core.frontmatter import FrontmatterParseError, extract_frontmatter
from gpd.core.observability import gpd_span
from gpd.specs import SPECS_DIR

logger = logging.getLogger(__name__)


# ─── Models ─────────────────────────────────────────────────────────────────────


class ContextCost(StrEnum):
    """How much context budget a reference file consumes."""

    SMALL = "small"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    LARGE = "large"


class ReferenceMeta(BaseModel):
    """Metadata extracted from a reference file's YAML frontmatter."""

    model_config = ConfigDict(frozen=True)

    path: Path
    name: str
    tier: int = 2
    context_cost: ContextCost = ContextCost.MEDIUM
    load_when: list[str] = Field(default_factory=list)


class ErrorClassDetail(BaseModel):
    """A single error class from the LLM physics error catalog."""

    model_config = ConfigDict(frozen=True)

    id: int
    name: str
    description: str
    detection_strategy: str
    example: str = ""
    source_file: str = ""


class ProtocolEntry(BaseModel):
    """Index entry mapping a protocol to its file and usage context."""

    model_config = ConfigDict(frozen=True)

    name: str
    file: str
    when_to_use: str = ""
    category: str = ""


class ErrorFileRange(BaseModel):
    """Maps error ID ranges to the file containing their details."""

    model_config = ConfigDict(frozen=True)

    id_start: int
    id_end: int
    file: str
    domain: str = ""


class ErrorClassSummary(BaseModel):
    """Summary info for an error class (from the traceability table)."""

    model_config = ConfigDict(frozen=True)

    id: int
    name: str


class VerificationDomainEntry(BaseModel):
    """Maps a physics domain to its verification checklist file."""

    model_config = ConfigDict(frozen=True)

    domain: str
    file: str
    coverage: str = ""


class SubfieldEntry(BaseModel):
    """Maps a physics subfield to its guide file."""

    model_config = ConfigDict(frozen=True)

    name: str
    file: str
    key_topics: str = ""


# ─── Frontmatter Parsing ────────────────────────────────────────────────────────


def _parse_frontmatter(content: str) -> dict:
    """Extract YAML frontmatter from markdown content. Returns {} if none found.

    Delegates to gpd.core.frontmatter.extract_frontmatter for actual parsing.
    """
    try:
        meta, _ = extract_frontmatter(content)
        return meta
    except FrontmatterParseError:
        return {}


def _strip_frontmatter(content: str) -> str:
    """Remove YAML frontmatter from markdown content."""
    try:
        _, body = extract_frontmatter(content)
        return body
    except FrontmatterParseError:
        return content


# ─── Markdown Table Parsing ──────────────────────────────────────────────────────

_SEPARATOR_RE = re.compile(r"^[\s|:\-]+$")


def _split_table_cells(line: str) -> list[str]:
    """Split a markdown table row into cells, respecting escaped pipes (\\|)."""
    line = line.strip()
    if not line.startswith("|") or not line.endswith("|"):
        return []
    inner = line[1:-1]
    cells = re.split(r"(?<!\\)\|", inner)
    return [c.replace("\\|", "|").strip() for c in cells]


def _parse_markdown_table(text: str) -> list[list[str]]:
    """Parse a markdown table into data rows (header and separator skipped).

    Each row is a list of cell strings. Stops at the first non-table line
    after data rows have been found.
    """
    rows: list[list[str]] = []
    header_seen = False
    separator_seen = False

    for line in text.splitlines():
        cells = _split_table_cells(line)
        if not cells:
            if rows:
                break
            continue

        if not header_seen:
            header_seen = True
            continue

        if not separator_seen:
            raw = line.strip()[1:-1]
            if _SEPARATOR_RE.match(raw):
                separator_seen = True
                continue

        rows.append(cells)

    return rows


def _strip_bold(text: str) -> str:
    return text.replace("**", "")


def _strip_backticks(text: str) -> str:
    return text.strip("`")


def _strip_link(text: str) -> str:
    """Extract display text from [text](url) links."""
    m = re.match(r"\[([^\]]+)\]\([^)]+\)", text)
    return m.group(1) if m else text


def _normalize_ref_path(path: str) -> str:
    """Normalize a reference file path to be relative to the references directory."""
    _refs_prefix = SPECS_REFERENCES_DIR + "/"
    path = path.strip().strip("`")
    if path.startswith(_refs_prefix):
        path = path[len(_refs_prefix) :]
    return path


def _normalize_domain_key(domain: str) -> str:
    """Normalize a physics domain name for index lookup.

    "QFT / Particle / GR" -> "qft-particle-gr"
    "Quantum Field Theory" -> "quantum-field-theory"
    """
    return re.sub(r"[^a-z0-9]+", "-", domain.lower()).strip("-")


def _protocol_key(name: str) -> str:
    """Generate a normalized key for protocol lookup."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


# ─── Reference Loader ───────────────────────────────────────────────────────────


class ReferenceLoader:
    """Loads and indexes GPD reference files from specs/references/.

    Parses YAML frontmatter for metadata (tier, load_when, context_cost).
    Builds sub-indexes lazily from markdown table content in index files.
    Uses an LRU cache (OrderedDict) with configurable max size.
    """

    def __init__(self, specs_dir: Path | None = None, max_cache_size: int = DEFAULT_LOADER_CACHE_SIZE) -> None:
        self._specs_dir = specs_dir or SPECS_DIR
        self._refs_dir = self._specs_dir / SPECS_REFERENCES_DIR
        self._max_cache_size = max_cache_size

        # Metadata index: name -> ReferenceMeta (built by build_index)
        self._index: dict[str, ReferenceMeta] = {}
        # LRU content cache: name -> stripped content
        self._content_cache: OrderedDict[str, str] = OrderedDict()

        # Simple sub-indexes (built by build_index, by file naming convention)
        self._protocol_names: dict[str, str] = {}  # protocol-name -> ref-name
        self._verification_domain_names: dict[str, str] = {}  # domain -> ref-name
        self._error_file_names: dict[str, str] = {}  # catalog-name -> ref-name

        # Rich sub-indexes (built lazily from markdown table content)
        self._protocol_index: dict[str, ProtocolEntry] | None = None
        self._error_file_ranges: list[ErrorFileRange] | None = None
        self._error_summaries: list[ErrorClassSummary] | None = None
        self._verification_index: dict[str, VerificationDomainEntry] | None = None
        self._subfield_index: dict[str, SubfieldEntry] | None = None

        self._built = False

    def build_index(self) -> None:
        """Scan all reference files and build the metadata index."""
        if self._built:
            return
        if not self._refs_dir.is_dir():
            logger.warning("References directory not found: %s", self._refs_dir)
            self._built = True
            return

        with gpd_span("loader.build_index", refs_dir=str(self._refs_dir)):
            self._build_index_internal()

    def _build_index_internal(self) -> None:
        """Internal index builder (separated for instrumentation)."""
        for md_file in sorted(self._refs_dir.rglob("*.md")):
            rel = md_file.relative_to(self._refs_dir)
            name = str(rel).removesuffix(".md")
            try:
                content = md_file.read_text(encoding="utf-8")
            except OSError:
                continue
            fm = _parse_frontmatter(content)
            meta = ReferenceMeta(
                path=md_file,
                name=name,
                tier=fm.get("tier", 2),
                context_cost=fm.get("context_cost", "medium"),
                load_when=fm.get("load_when", []),
            )
            self._index[name] = meta

            # Build simple sub-indexes by file naming convention
            if name.startswith(REF_PROTOCOL_PREFIX):
                protocol_name = name.removeprefix(REF_PROTOCOL_PREFIX)
                self._protocol_names[protocol_name] = name

            if name.startswith(REF_VERIFICATION_DOMAIN_PREFIX):
                domain = name.removeprefix(REF_VERIFICATION_DOMAIN_PREFIX)
                self._verification_domain_names[domain] = name

            if name.startswith(REF_ERROR_CATALOG_PREFIX):
                self._error_file_names[name] = name

            if name.startswith(REF_SUBFIELD_PREFIX):
                subfield_name = name.removeprefix(REF_SUBFIELD_PREFIX)
                self._verification_domain_names.setdefault(subfield_name, name)

        self._built = True

    def _ensure_built(self) -> None:
        if not self._built:
            self.build_index()

    # ─── Properties ────────────────────────────────────────────────────────────

    @property
    def reference_names(self) -> list[str]:
        """All indexed reference names."""
        self._ensure_built()
        return sorted(self._index.keys())

    @property
    def protocol_names(self) -> list[str]:
        """All indexed protocol names (without 'protocols/' prefix)."""
        self._ensure_built()
        return sorted(self._protocol_names.keys())

    @property
    def verification_domains(self) -> list[str]:
        """All indexed verification domain names."""
        self._ensure_built()
        return sorted(self._verification_domain_names.keys())

    @property
    def cache_stats(self) -> tuple[int, int]:
        """Return (current_entries, max_entries) for the LRU cache."""
        return len(self._content_cache), self._max_cache_size

    # ─── Metadata Access ───────────────────────────────────────────────────────

    def get_meta(self, name: str) -> ReferenceMeta | None:
        """Get metadata for a reference by name."""
        self._ensure_built()
        return self._index.get(name)

    def get_tier1_refs(self) -> list[ReferenceMeta]:
        """Get all tier-1 (always loaded) references."""
        self._ensure_built()
        return [m for m in self._index.values() if m.tier == 1]

    # ─── Content Loading ───────────────────────────────────────────────────────

    def load(self, name: str) -> str | None:
        """Load reference content by name. Returns None if not found.

        Uses LRU cache with eviction when max_cache_size is exceeded.
        """
        self._ensure_built()
        if name in self._content_cache:
            self._content_cache.move_to_end(name)
            return self._content_cache[name]
        meta = self._index.get(name)
        if meta is None:
            return None
        try:
            content = meta.path.read_text(encoding="utf-8")
            body = _strip_frontmatter(content)
            self._cache_put(name, body)
            return body
        except OSError:
            return None

    def _cache_put(self, key: str, content: str) -> None:
        """Insert into LRU cache, evicting oldest if at capacity."""
        if key in self._content_cache:
            self._content_cache.move_to_end(key)
        self._content_cache[key] = content
        while len(self._content_cache) > self._max_cache_size:
            self._content_cache.popitem(last=False)

    def load_protocol(self, protocol_name: str) -> str | None:
        """Load a protocol by name (e.g., 'perturbation-theory')."""
        self._ensure_built()
        ref_name = self._protocol_names.get(protocol_name)
        if ref_name is None:
            return None
        return self.load(ref_name)

    def load_verification_checklist(self, domain: str) -> str | None:
        """Load a verification domain checklist (e.g., 'qft', 'condmat')."""
        self._ensure_built()
        ref_name = self._verification_domain_names.get(domain)
        if ref_name is None:
            return None
        return self.load(ref_name)

    def load_subfield_guide(self, domain: str) -> str | None:
        """Load the subfield guide for a domain (e.g., 'qft', 'condensed-matter').

        Uses the physics-subfields.md index to map domain names to guide files.
        Falls back to executor-subfield-guide if available.
        """
        self._ensure_built()
        index = self._ensure_subfield_index()

        key = _normalize_domain_key(domain)
        entry = index.get(key)
        if entry is None:
            for k, v in index.items():
                if key in k or k in key:
                    entry = v
                    break

        if entry is not None:
            ref_name = entry.file.removesuffix(".md")
            return self.load(ref_name)

        # Fall back to executor-subfield-guide
        return self.load(REF_SUBFIELD_GUIDE_FALLBACK)

    def load_error_catalog(self, catalog_name: str) -> str | None:
        """Load an error catalog file (e.g., 'llm-errors-core')."""
        self._ensure_built()
        ref_name = self._error_file_names.get(catalog_name)
        if ref_name is None:
            return None
        return self.load(ref_name)

    def load_error_class(self, error_id: int) -> ErrorClassDetail:
        """Load and parse a specific error class by ID.

        Uses the error file range index to find the right catalog file,
        then parses the markdown table to extract the specific error class.

        Raises KeyError if the error class is not found.
        """
        ranges = self._ensure_error_file_ranges()
        catalog_name: str | None = None
        for entry in ranges:
            if entry.id_start <= error_id <= entry.id_end:
                catalog_name = entry.file.removesuffix(".md")
                break

        if catalog_name is None:
            raise LoaderError(
                f"Error class #{error_id} not in any file. Ranges: {[(e.id_start, e.id_end, e.file) for e in ranges]}"
            )

        content = self.load_error_catalog(catalog_name)
        if content is None:
            raise LoaderError(f"Error catalog file not found: {catalog_name}")

        return _parse_error_class_from_content(error_id, content, catalog_name)

    # ─── Tier-1 Preloading ─────────────────────────────────────────────────────

    def preload_tier1(self) -> list[str]:
        """Load all tier-1 references into the cache. Returns loaded names."""
        self._ensure_built()
        loaded: list[str] = []
        for meta in self._index.values():
            if meta.tier == 1:
                content = self.load(meta.name)
                if content is not None:
                    loaded.append(meta.name)
        return loaded

    # ─── Rich Index Access ─────────────────────────────────────────────────────

    @property
    def protocol_index(self) -> dict[str, ProtocolEntry]:
        """Protocol index built from shared-protocols.md tables."""
        return dict(self._ensure_protocol_index())

    @property
    def verification_domain_index(self) -> dict[str, VerificationDomainEntry]:
        """Verification domain index built from shared-protocols.md tables."""
        return dict(self._ensure_verification_index())

    @property
    def subfield_guide_index(self) -> dict[str, SubfieldEntry]:
        """Subfield guide index built from physics-subfields.md."""
        return dict(self._ensure_subfield_index())

    @property
    def error_file_ranges(self) -> list[ErrorFileRange]:
        """Error file ranges built from llm-physics-errors.md."""
        return list(self._ensure_error_file_ranges())

    @property
    def error_summaries(self) -> list[ErrorClassSummary]:
        """Error class summaries from the traceability table."""
        return list(self._ensure_error_summaries())

    # ─── Search ────────────────────────────────────────────────────────────────

    def search_by_keywords(self, keywords: list[str]) -> list[ReferenceMeta]:
        """Find references whose load_when keywords match any of the given keywords.

        Matching is case-insensitive substring.
        """
        self._ensure_built()
        if not keywords:
            return []
        lower_keywords = [k.lower() for k in keywords]
        results: list[ReferenceMeta] = []
        for meta in self._index.values():
            for load_kw in meta.load_when:
                load_kw_lower = load_kw.lower()
                if any(kw in load_kw_lower for kw in lower_keywords):
                    results.append(meta)
                    break
        return results

    def clear_cache(self) -> None:
        """Clear the content cache."""
        self._content_cache.clear()

    # ─── Internal: Rich Index Building ─────────────────────────────────────────

    def _ensure_protocol_index(self) -> dict[str, ProtocolEntry]:
        if self._protocol_index is None:
            self._protocol_index = self._build_protocol_index()
        return self._protocol_index

    def _ensure_error_file_ranges(self) -> list[ErrorFileRange]:
        if self._error_file_ranges is None:
            self._error_file_ranges = self._build_error_file_ranges()
        return self._error_file_ranges

    def _ensure_error_summaries(self) -> list[ErrorClassSummary]:
        if self._error_summaries is None:
            self._error_summaries = self._build_error_summaries()
        return self._error_summaries

    def _ensure_verification_index(self) -> dict[str, VerificationDomainEntry]:
        if self._verification_index is None:
            self._verification_index = self._build_verification_index()
        return self._verification_index

    def _ensure_subfield_index(self) -> dict[str, SubfieldEntry]:
        if self._subfield_index is None:
            self._subfield_index = self._build_subfield_index()
        return self._subfield_index

    def _build_protocol_index(self) -> dict[str, ProtocolEntry]:
        """Build protocol index from shared-protocols.md markdown tables."""
        content = self.load("shared-protocols")
        if content is None:
            return {}

        index: dict[str, ProtocolEntry] = {}
        categories = [
            ("Core Derivation", "### Core Derivation Protocols"),
            ("Computational Method", "### Computational Method Protocols"),
            ("Mathematical Method", "### Mathematical Method Protocols"),
            ("Domain-Specific Verification", "### Domain-Specific Verification"),
            ("Numerical", "### Numerical and Translation Protocols"),
            ("LLM Error Guards", "### LLM-Specific Error Guards"),
        ]

        for category, header in categories:
            start = content.find(header)
            if start == -1:
                continue

            section = content[start:]
            next_header = re.search(r"\n### ", section[len(header) :])
            if next_header:
                section = section[: len(header) + next_header.start()]

            rows = _parse_markdown_table(section)
            for row in rows:
                if len(row) < 3:
                    continue
                name = _strip_bold(row[0].strip())
                file_path = _strip_backticks(row[1].strip())
                when = row[2].strip()

                file_path = _normalize_ref_path(file_path)
                key = _protocol_key(name)
                index[key] = ProtocolEntry(name=name, file=file_path, when_to_use=when, category=category)

        return index

    def _build_error_file_ranges(self) -> list[ErrorFileRange]:
        """Build error file ranges from llm-physics-errors.md index table."""
        content = self.load("llm-physics-errors")
        if content is None:
            return []

        ranges: list[ErrorFileRange] = []
        table_start = content.find("| File |")
        if table_start == -1:
            return ranges

        rows = _parse_markdown_table(content[table_start:])
        for row in rows:
            if len(row) < 3:
                continue

            file_text = _strip_link(row[0].strip())
            classes_text = row[1].strip()
            domain = row[2].strip()

            for range_match in re.finditer(r"#(\d+)-(\d+)", classes_text):
                ranges.append(
                    ErrorFileRange(
                        id_start=int(range_match.group(1)),
                        id_end=int(range_match.group(2)),
                        file=file_text,
                        domain=domain,
                    )
                )

        return ranges

    def _build_error_summaries(self) -> list[ErrorClassSummary]:
        """Build error class summaries from llm-physics-errors.md traceability table."""
        content = self.load("llm-physics-errors")
        if content is None:
            return []

        summaries: list[ErrorClassSummary] = []
        table_start = content.find("| Error Class |")
        if table_start == -1:
            return summaries

        rows = _parse_markdown_table(content[table_start:])
        for row in rows:
            if not row:
                continue
            cell = row[0].strip()
            m = re.match(r"(\d+)\.\s*(.+)", cell)
            if m:
                summaries.append(ErrorClassSummary(id=int(m.group(1)), name=m.group(2).strip()))

        return summaries

    def _build_verification_index(self) -> dict[str, VerificationDomainEntry]:
        """Build verification domain index from shared-protocols.md."""
        content = self.load("shared-protocols")
        if content is None:
            return {}

        index: dict[str, VerificationDomainEntry] = {}
        section_header = "### Domain-Specific Verification"
        start = content.find(section_header)
        if start == -1:
            return index

        section = content[start:]
        next_header = re.search(r"\n### ", section[len(section_header) :])
        if next_header:
            section = section[: len(section_header) + next_header.start()]

        rows = _parse_markdown_table(section)
        for row in rows:
            if len(row) < 3:
                continue

            domain = _strip_bold(row[0].strip())
            file_path = _strip_backticks(row[1].strip())
            coverage = row[2].strip()

            file_path = _normalize_ref_path(file_path)
            key = _normalize_domain_key(domain)
            index[key] = VerificationDomainEntry(domain=domain, file=file_path, coverage=coverage)

        return index

    def _build_subfield_index(self) -> dict[str, SubfieldEntry]:
        """Build subfield guide index from physics-subfields.md."""
        content = self.load("physics-subfields")
        if content is None:
            return {}

        index: dict[str, SubfieldEntry] = {}
        table_start = content.find("| Subfield |")
        if table_start == -1:
            return index

        rows = _parse_markdown_table(content[table_start:])
        for row in rows:
            if len(row) < 3:
                continue

            name = row[0].strip()
            file_path = row[1].strip()
            topics = row[2].strip()

            if file_path.startswith(SPECS_REFERENCES_DIR + "/"):
                file_path = file_path[len(SPECS_REFERENCES_DIR) + 1 :]

            key = _normalize_domain_key(name)
            index[key] = SubfieldEntry(name=name, file=file_path, key_topics=topics)

        return index


# ─── Error Class Parsing ─────────────────────────────────────────────────────────


def _parse_error_class_from_content(error_id: int, content: str, source_file: str) -> ErrorClassDetail:
    """Parse a specific error class from a catalog file's content.

    The error tables have format: | # | **Name** | Description | Detection Strategy | Example |
    """
    for line in content.splitlines():
        cells = _split_table_cells(line)
        if len(cells) < 5:
            continue

        try:
            row_id = int(cells[0].strip())
        except ValueError:
            continue

        if row_id == error_id:
            return ErrorClassDetail(
                id=error_id,
                name=_strip_bold(cells[1]),
                description=cells[2],
                detection_strategy=cells[3],
                example=cells[4] if len(cells) > 4 else "",
                source_file=source_file,
            )

    raise LoaderError(f"Error class #{error_id} not found in {source_file}")


# ─── Module-level singleton ─────────────────────────────────────────────────────


@lru_cache(maxsize=1)
def get_loader(specs_dir: Path | None = None) -> ReferenceLoader:
    """Get or create the singleton ReferenceLoader."""
    loader = ReferenceLoader(specs_dir)
    loader.build_index()
    return loader
