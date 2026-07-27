"""Physics error-catalog domain logic (transport-neutral).

Loads the error-catalog part files and the traceability matrix from
``specs/references/verification/errors/``, parses their markdown tables, and
answers catalog queries. Nothing here knows about MCP, CLI, or any other
transport: every query returns plain dicts/lists that a caller can render or
wrap in its own envelope.

Storage layout::

    {SPECS_DIR}/references/verification/errors/
        llm-errors-core.md           (#1-25)
        llm-errors-field-theory.md   (#26-51)
        llm-errors-extended.md       (#52-81, #102-104)
        llm-errors-deep.md           (#82-101)
        llm-errors-traceability.md

Public API
----------
ErrorStore                        — parsed catalog + traceability matrix
get_error_store                   — lazily built, thread-safe shared store
get_error_class                   — full record for one error class
check_error_classes               — error classes relevant to a computation
get_detection_strategy            — detection strategy for one error class
get_traceability                  — verification-check coverage for one class
list_error_classes                — catalog listing with optional domain filter
normalize_error_domain            — validate a domain filter
normalize_computation_description — validate a computation description
"""

from __future__ import annotations

import logging
import re
import threading
from collections.abc import Sequence
from pathlib import Path

from gpd.core.frontmatter import FrontmatterParseError, extract_frontmatter
from gpd.core.observability import gpd_span
from gpd.specs import SPECS_DIR

logger = logging.getLogger(__name__)

__all__ = [
    "ERROR_CATALOG_FILES",
    "ERROR_CATALOG_FILE_RANGES",
    "ERROR_DOMAIN_RANGES",
    "ERROR_ID_RANGE_LABEL",
    "KNOWN_ERROR_DOMAINS",
    "MAX_ERROR_CLASS_MATCHES",
    "REFERENCES_DIR",
    "TRACEABILITY_COLUMNS",
    "TRACEABILITY_FILE",
    "ErrorStore",
    "check_error_classes",
    "get_detection_strategy",
    "get_error_class",
    "get_error_store",
    "get_traceability",
    "list_error_classes",
    "normalize_computation_description",
    "normalize_error_domain",
]

# ---------------------------------------------------------------------------
# Catalog constants
# ---------------------------------------------------------------------------

REFERENCES_DIR = SPECS_DIR / "references"

CatalogFileRanges = tuple[tuple[str, tuple[tuple[int, int], ...]], ...]

ERROR_CATALOG_FILE_RANGES: CatalogFileRanges = (
    ("verification/errors/llm-errors-core.md", ((1, 25),)),
    ("verification/errors/llm-errors-field-theory.md", ((26, 51),)),
    ("verification/errors/llm-errors-extended.md", ((52, 81), (102, 104))),
    ("verification/errors/llm-errors-deep.md", ((82, 101),)),
)

# The 4 error catalog part files, ordered by their authoritative ID ranges.
ERROR_CATALOG_FILES = [filename for filename, _ranges in ERROR_CATALOG_FILE_RANGES]

ERROR_DOMAIN_RANGES: dict[str, tuple[int, int]] = {
    "core": (1, 25),
    "field_theory": (26, 51),
    "extended": (52, 71),
    "deep_domain": (72, 81),
    "cross_domain": (82, 101),
    "newly_identified": (102, 104),
}
KNOWN_ERROR_DOMAINS: tuple[str, ...] = tuple(ERROR_DOMAIN_RANGES)

# Human-readable span of valid error class IDs, derived from the domain map.
ERROR_ID_RANGE_LABEL = (
    f"{min(start for start, _end in ERROR_DOMAIN_RANGES.values())}"
    f"-{max(end for _start, end in ERROR_DOMAIN_RANGES.values())}"
)

TRACEABILITY_FILE = "verification/errors/llm-errors-traceability.md"

# Traceability matrix column names
TRACEABILITY_COLUMNS = [
    "Dimensional Analysis",
    "Limiting Cases",
    "Symmetry",
    "Conservation",
    "Sum Rules / Ward",
    "Numerical Convergence",
    "Cross-Check Literature",
    "Positivity / Unitarity",
]

# Maximum number of relevance matches returned by check_error_classes.
MAX_ERROR_CLASS_MATCHES = 15

# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

# Matches markdown table rows: | value | value | ... |
_TABLE_ROW_RE = re.compile(r"^\|(.+)\|$")

# Matches the separator line: |---|---|...|
_TABLE_SEP_RE = re.compile(r"^\|[\s\-:|]+\|$")

# Frontmatter shape checks: an opening delimiter with no closing delimiter.
_FRONTMATTER_OPEN_RE = re.compile(r"^---[ \t]*(?:\r?\n|$)")
_FRONTMATTER_BLOCK_RE = re.compile(r"^---[ \t]*\r?\n(?:[\s\S]*?\r?\n)?---[ \t]*(?:\r?\n|$)")
_LEADING_BLANK_LINES_RE = re.compile(r"^(?:[ \t]*\r?\n)+(?=---[ \t]*\r?\n)")

# Words too common to carry relevance signal in check_error_classes.
_RELEVANCE_STOPWORDS = frozenset({"the", "a", "an", "is", "in", "of", "for", "and", "or", "to", "with", "that", "this"})


def _declared_ranges_for_catalog(filename: str, catalog_file_ranges: CatalogFileRanges) -> tuple[tuple[int, int], ...]:
    """Return the authoritative error ID ranges declared for one catalog file."""
    for declared_filename, ranges in catalog_file_ranges:
        if declared_filename == filename:
            return ranges
    return ()


def _error_id_in_declared_ranges(error_id: int, ranges: tuple[tuple[int, int], ...]) -> bool:
    """Return whether an error ID belongs to one of a catalog's declared ranges."""
    return any(start <= error_id <= end for start, end in ranges)


def _format_error_id_ranges(ranges: tuple[tuple[int, int], ...]) -> str:
    """Render compact human-readable ID ranges for validation errors."""
    return ", ".join(str(start) if start == end else f"{start}-{end}" for start, end in ranges)


def _parse_table_rows(body: str) -> list[list[str]]:
    """Parse all markdown table rows from a body, skipping headers and separators."""
    rows: list[list[str]] = []
    for line in body.split("\n"):
        line = line.strip()
        if not line or _TABLE_SEP_RE.match(line):
            continue
        m = _TABLE_ROW_RE.match(line)
        if not m:
            continue
        cells = [cell.strip().replace("\\|", "|") for cell in re.split(r"(?<!\\)\|", m.group(1))]
        rows.append(cells)
    return rows


def _strip_bold(text: str) -> str:
    """Remove markdown bold markers."""
    return re.sub(r"\*\*(.+?)\*\*", r"\1", text)


def _infer_domain_from_id(error_id: int) -> str:
    """Infer a domain category from error class ID range."""
    for domain, (start, end) in ERROR_DOMAIN_RANGES.items():
        if start <= error_id <= end:
            return domain
    return "unknown"


def normalize_error_domain(domain: object) -> str | None:
    """Normalize and validate a catalog domain filter.

    Returns ``None`` for an absent filter, otherwise the stripped domain name.

    Raises:
        ValueError: If the filter is blank or not a known catalog domain.
    """
    if domain is None:
        return None
    if not isinstance(domain, str) or not domain.strip():
        raise ValueError("domain must be a non-empty string")
    normalized = domain.strip()
    if normalized not in ERROR_DOMAIN_RANGES:
        allowed = ", ".join(KNOWN_ERROR_DOMAINS)
        raise ValueError(f"unknown domain '{normalized}'; expected one of: {allowed}")
    return normalized


def normalize_computation_description(computation_desc: object) -> str:
    """Normalize and validate a computation description.

    Raises:
        ValueError: If the description is blank or not a string.
    """
    if not isinstance(computation_desc, str) or not computation_desc.strip():
        raise ValueError("computation_desc must be a non-empty string")
    return computation_desc.strip()


def _markdown_body(path: Path, *, label: str) -> str:
    """Read an authoritative markdown document body or fail closed."""
    if not path.is_file():
        raise OSError(f"{label} not found: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise OSError(f"Failed to read {path}: {exc}") from exc

    candidate = _LEADING_BLANK_LINES_RE.sub("", text.lstrip("\ufeff"), count=1)
    if _FRONTMATTER_OPEN_RE.match(candidate) and not _FRONTMATTER_BLOCK_RE.match(candidate):
        raise ValueError(f"Malformed frontmatter in {path}: Unclosed frontmatter block")
    try:
        _meta, body = extract_frontmatter(text)
    except FrontmatterParseError as exc:
        raise ValueError(f"Malformed frontmatter in {path}: {exc}") from exc
    return body


# ---------------------------------------------------------------------------
# Error store
# ---------------------------------------------------------------------------


class ErrorStore:
    """In-memory store of parsed error classes and traceability data.

    The catalog layout constants are injectable so a caller can bind a
    different set of part files without redefining the parsing rules.
    """

    def __init__(
        self,
        references_dir: Path,
        *,
        catalog_files: Sequence[str] | None = None,
        catalog_file_ranges: CatalogFileRanges | None = None,
        traceability_file: str | None = None,
    ) -> None:
        self._catalog_files: tuple[str, ...] = tuple(ERROR_CATALOG_FILES if catalog_files is None else catalog_files)
        self._catalog_file_ranges: CatalogFileRanges = tuple(
            ERROR_CATALOG_FILE_RANGES if catalog_file_ranges is None else catalog_file_ranges
        )
        self._traceability_file: str = TRACEABILITY_FILE if traceability_file is None else traceability_file
        self._errors: dict[int, dict[str, object]] = {}
        self._traceability: dict[int, dict[str, str]] = {}
        self._load_catalogs(references_dir)
        self._load_traceability(references_dir)

    def _load_catalogs(self, references_dir: Path) -> None:
        """Load every configured error catalog part file."""
        with gpd_span("errors.load_catalogs", references_dir=str(references_dir)):
            self._do_load_catalogs(references_dir)

    def _do_load_catalogs(self, references_dir: Path) -> None:
        for filename in self._catalog_files:
            path = references_dir / filename
            body = _markdown_body(path, label="Error catalog")
            rows = _parse_table_rows(body)
            loaded_rows = 0
            declared_ranges = _declared_ranges_for_catalog(filename, self._catalog_file_ranges)

            for row in rows:
                # Skip header rows (first cell is "#" or "Error Class")
                if len(row) < 5:
                    continue
                id_str = row[0].strip()
                # Extract numeric ID
                id_match = re.match(r"(\d+)", id_str)
                if not id_match:
                    continue
                error_id = int(id_match.group(1))
                if declared_ranges and not _error_id_in_declared_ranges(error_id, declared_ranges):
                    expected = _format_error_id_ranges(declared_ranges)
                    raise ValueError(
                        f"Error catalog {Path(filename).name} declares ID range(s) {expected}; "
                        f"found out-of-range error class id {error_id}"
                    )

                name = _strip_bold(row[1].strip())
                description = row[2].strip()
                detection_strategy = row[3].strip()
                example = row[4].strip()

                existing = self._errors.get(error_id)
                if existing is not None:
                    raise ValueError(
                        f"Duplicate error class id {error_id} in {Path(filename).name}; "
                        f"already defined in {existing['source_file']}"
                    )

                self._errors[error_id] = {
                    "id": error_id,
                    "name": name,
                    "description": description,
                    "detection_strategy": detection_strategy,
                    "example": example,
                    "domain": _infer_domain_from_id(error_id),
                    # Preserve the stable basename in the public response.
                    "source_file": Path(filename).name,
                }
                loaded_rows += 1

            if loaded_rows == 0:
                raise ValueError(f"Error catalog {path} did not contain any error-class rows")

        logger.info("Loaded %d error classes from catalogs", len(self._errors))

    def _load_traceability(self, references_dir: Path) -> None:
        """Load the traceability matrix mapping errors to verification checks."""
        with gpd_span("errors.load_traceability"):
            self._do_load_traceability(references_dir)

    def _do_load_traceability(self, references_dir: Path) -> None:
        path = references_dir / self._traceability_file
        body = _markdown_body(path, label="Traceability matrix")
        rows = _parse_table_rows(body)
        loaded_rows = 0

        for row in rows:
            if len(row) < 2:
                continue
            # First cell format: "1. Wrong CG coefficients" or "# Error Class"
            first = row[0].strip()
            id_match = re.match(r"(\d+)\.", first)
            if not id_match:
                continue
            error_id = int(id_match.group(1))
            if error_id in self._traceability:
                raise ValueError(
                    f"Duplicate traceability row for error class {error_id} in {Path(self._traceability_file).name}"
                )

            # Map remaining cells to traceability columns
            checks: dict[str, str] = {}
            for i, col_name in enumerate(TRACEABILITY_COLUMNS):
                cell_idx = i + 1  # offset past the first column
                if cell_idx < len(row):
                    value = row[cell_idx].strip()
                    if value:
                        checks[col_name] = value

            self._traceability[error_id] = checks
            loaded_rows += 1

        if loaded_rows == 0:
            raise ValueError(f"Traceability matrix {path} did not contain any error-class rows")

        logger.info("Loaded traceability data for %d error classes", len(self._traceability))

    def get(self, error_id: int) -> dict[str, object] | None:
        """Get an error class by numeric ID."""
        return self._errors.get(error_id)

    def get_traceability(self, error_id: int) -> dict[str, str] | None:
        """Get traceability mapping for an error class."""
        return self._traceability.get(error_id)

    def list_all(self, domain: str | None = None) -> list[dict[str, object]]:
        """List error classes, optionally filtered by domain."""
        result = []
        for e in self._errors.values():
            if domain and e["domain"] != domain:
                continue
            result.append(
                {
                    "id": e["id"],
                    "name": e["name"],
                    "domain": e["domain"],
                }
            )
        return sorted(result, key=lambda x: int(str(x["id"])))

    def check_relevant(self, computation_desc: str) -> list[dict[str, object]]:
        """Find error classes relevant to a computation description.

        Matches against error names, descriptions, and detection strategies
        using case-insensitive keyword matching.
        """
        query = computation_desc.lower()
        query_words = set(re.findall(r"[a-z]+", query))

        scored: list[tuple[int, dict[str, object]]] = []

        for e in self._errors.values():
            score = 0
            searchable = f"{e['name']} {e['description']}".lower()
            searchable_words = set(re.findall(r"[a-z]+", searchable))

            # Score based on word overlap, ignoring very common words
            meaningful = (query_words & searchable_words) - _RELEVANCE_STOPWORDS
            score += len(meaningful) * 3

            # Bonus for phrase matches in the name
            name_lower = str(e["name"]).lower()
            for word in query_words - _RELEVANCE_STOPWORDS:
                if len(word) > 3 and word in name_lower:
                    score += 5

            if score > 0:
                scored.append(
                    (
                        score,
                        {
                            "id": e["id"],
                            "name": e["name"],
                            "domain": e["domain"],
                            "relevance_score": score,
                            "description_preview": str(e["description"])[:200],
                        },
                    )
                )

        scored.sort(key=lambda x: -x[0])
        return [item for _, item in scored]

    @property
    def domains(self) -> list[str]:
        """List all unique domains."""
        return sorted({str(e["domain"]) for e in self._errors.values()})

    @property
    def count(self) -> int:
        """Number of error classes loaded from the catalogs."""
        return len(self._errors)


_store: ErrorStore | None = None
_store_lock = threading.Lock()


def get_error_store() -> ErrorStore:
    """Return the lazily-initialised shared error store (thread-safe)."""
    global _store  # noqa: PLW0603
    if _store is not None:
        return _store
    with _store_lock:
        if _store is None:
            _store = ErrorStore(REFERENCES_DIR)
        return _store


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------


def get_error_class(store: ErrorStore, error_id: int) -> dict[str, object]:
    """Return the full record for one error class.

    An unknown ID yields a payload carrying an ``error`` key plus the valid
    range, so callers can render the miss without a second lookup.
    """
    error = store.get(error_id)
    if error is None:
        return {
            "valid_range": ERROR_ID_RANGE_LABEL,
            "total_classes": store.count,
            "error": f"Error class #{error_id} not found",
        }
    return dict(error)


def check_error_classes(store: ErrorStore, computation_desc: object) -> dict[str, object]:
    """Return the error classes most relevant to a computation description.

    Raises:
        ValueError: If the description is blank or not a string.
    """
    query = normalize_computation_description(computation_desc)
    matches = store.check_relevant(query)
    return {
        "query": query,
        "match_count": len(matches),
        "error_classes": matches[:MAX_ERROR_CLASS_MATCHES],
    }


def get_detection_strategy(store: ErrorStore, error_id: int) -> dict[str, object]:
    """Return the detection strategy and example for one error class."""
    error = store.get(error_id)
    if error is None:
        return {
            "valid_range": ERROR_ID_RANGE_LABEL,
            "error": f"Error class #{error_id} not found",
        }
    return {
        "id": error["id"],
        "name": error["name"],
        "detection_strategy": error["detection_strategy"],
        "example": error["example"],
    }


def get_traceability(store: ErrorStore, error_id: int) -> dict[str, object]:
    """Return the verification-check coverage for one error class."""
    error = store.get(error_id)
    if error is None:
        return {
            "valid_range": ERROR_ID_RANGE_LABEL,
            "error": f"Error class #{error_id} not found",
        }

    traceability = store.get_traceability(error_id)
    if traceability is None:
        return {
            "id": error_id,
            "name": error["name"],
            "verification_checks": {},
            "covered_by": [],
            "coverage_count": 0,
            "note": "No traceability data available for this error class",
        }

    return {
        "id": error_id,
        "name": error["name"],
        "verification_checks": traceability,
        "covered_by": [col for col, val in traceability.items() if val],
        "coverage_count": len([v for v in traceability.values() if v]),
    }


def list_error_classes(store: ErrorStore, domain: object = None) -> dict[str, object]:
    """Return the catalog listing, optionally filtered by domain.

    Raises:
        ValueError: If the domain filter is blank or unknown.
    """
    normalized_domain = normalize_error_domain(domain)
    errors = store.list_all(normalized_domain)
    return {
        "count": len(errors),
        "error_classes": errors,
        "available_domains": store.domains,
        "total_classes": store.count,
    }
