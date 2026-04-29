"""GPD Errors MCP server — exposes physics error catalog and traceability via MCP tools.

Loads the error catalog files and traceability matrix from
specs/references/verification/errors/, parses markdown tables, and serves them
via FastMCP tools.

Entry point: python -m gpd.mcp.servers.errors_mcp
Console script: gpd-mcp-errors
"""

import re
import threading
from pathlib import Path
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field, WithJsonSchema

from gpd.core.observability import gpd_span
from gpd.mcp.servers import (
    configure_mcp_logging,
    parse_frontmatter_with_error,
    read_only_tool_annotations,
    run_mcp_server,
    stable_mcp_error,
    stable_mcp_response,
    tighten_registered_tool_contracts,
)
from gpd.specs import SPECS_DIR

logger = configure_mcp_logging("gpd-errors")

REFERENCES_DIR = SPECS_DIR / "references"

ERROR_CATALOG_FILE_RANGES: tuple[tuple[str, tuple[tuple[int, int], ...]], ...] = (
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

# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

# Matches markdown table rows: | value | value | ... |
_TABLE_ROW_RE = re.compile(r"^\|(.+)\|$")

# Matches the separator line: |---|---|...|
_TABLE_SEP_RE = re.compile(r"^\|[\s\-:|]+\|$")


def _declared_ranges_for_catalog(filename: str) -> tuple[tuple[int, int], ...]:
    """Return the authoritative error ID ranges declared for one catalog file."""
    for declared_filename, ranges in ERROR_CATALOG_FILE_RANGES:
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


def _normalize_error_domain(domain: object) -> str | None:
    """Normalize and validate a list_error_classes domain filter."""
    if domain is None:
        return None
    if not isinstance(domain, str) or not domain.strip():
        raise ValueError("domain must be a non-empty string")
    normalized = domain.strip()
    if normalized not in ERROR_DOMAIN_RANGES:
        allowed = ", ".join(KNOWN_ERROR_DOMAINS)
        raise ValueError(f"unknown domain '{normalized}'; expected one of: {allowed}")
    return normalized


def _load_authoritative_markdown_body(path: Path, *, label: str) -> str:
    """Read an authoritative markdown document or fail closed."""
    if not path.is_file():
        raise OSError(f"{label} not found: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise OSError(f"Failed to read {path}: {exc}") from exc

    _meta, body, parse_error = parse_frontmatter_with_error(text)
    if parse_error is not None:
        raise ValueError(f"Malformed frontmatter in {path}: {parse_error}")
    return body


# ---------------------------------------------------------------------------
# Error Store
# ---------------------------------------------------------------------------


class ErrorStore:
    """In-memory store of parsed error classes and traceability data."""

    def __init__(self, references_dir: Path) -> None:
        self._errors: dict[int, dict[str, object]] = {}
        self._traceability: dict[int, dict[str, str]] = {}
        self._load_catalogs(references_dir)
        self._load_traceability(references_dir)

    def _load_catalogs(self, references_dir: Path) -> None:
        """Load all 4 error catalog files."""
        with gpd_span("errors.load_catalogs", references_dir=str(references_dir)):
            self._do_load_catalogs(references_dir)

    def _do_load_catalogs(self, references_dir: Path) -> None:
        for filename in ERROR_CATALOG_FILES:
            path = references_dir / filename
            body = _load_authoritative_markdown_body(path, label="Error catalog")
            rows = _parse_table_rows(body)
            loaded_rows = 0
            declared_ranges = _declared_ranges_for_catalog(filename)

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
        path = references_dir / TRACEABILITY_FILE
        body = _load_authoritative_markdown_body(path, label="Traceability matrix")
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
                    f"Duplicate traceability row for error class {error_id} in {Path(TRACEABILITY_FILE).name}"
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

            # Score based on word overlap
            common = query_words & searchable_words
            # Filter out very common words
            stopwords = {"the", "a", "an", "is", "in", "of", "for", "and", "or", "to", "with", "that", "this"}
            meaningful = common - stopwords
            score += len(meaningful) * 3

            # Bonus for phrase matches in the name
            name_lower = str(e["name"]).lower()
            for word in query_words - stopwords:
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
        return len(self._errors)


# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------

_store: ErrorStore | None = None
_store_lock = threading.Lock()


def _get_store() -> ErrorStore:
    """Return the lazily-initialised error store (thread-safe)."""
    global _store  # noqa: PLW0603
    if _store is not None:
        return _store
    with _store_lock:
        if _store is None:
            _store = ErrorStore(REFERENCES_DIR)
        return _store


mcp = FastMCP("gpd-errors")

ComputationDescriptionInput = Annotated[
    str,
    Field(min_length=1, pattern=r"\S"),
    WithJsonSchema(
        {
            "type": "string",
            "minLength": 1,
            "pattern": r"\S",
            "description": "Non-empty physics computation description.",
        }
    ),
]

_ERROR_DOMAIN_SCHEMA = {
    "type": "string",
    "enum": list(KNOWN_ERROR_DOMAINS),
    "minLength": 1,
    "pattern": r"\S",
    "description": "Known error-catalog domain filter.",
}

ErrorDomainFilterInput = Annotated[
    str | None,
    WithJsonSchema({"anyOf": [_ERROR_DOMAIN_SCHEMA, {"type": "null"}]}),
]


@mcp.tool(annotations=read_only_tool_annotations())
def get_error_class(error_id: int) -> dict[str, object]:
    """Get full details of a physics error class by ID.

    Returns the error name, description, detection strategy, and example.

    Args:
        error_id: Numeric error class ID (1-104).
    """
    with gpd_span("mcp.errors.get", error_class_id=error_id):
        try:
            store = _get_store()
            error = store.get(error_id)
            if error is None:
                return stable_mcp_response(
                    {
                        "valid_range": "1-104",
                        "total_classes": store.count,
                    },
                    error=f"Error class #{error_id} not found",
                )
            return stable_mcp_response(dict(error))
        except (OSError, ValueError, KeyError) as exc:
            return stable_mcp_error(exc)
        except Exception as exc:  # pragma: no cover - defensive envelope
            return stable_mcp_error(exc)


@mcp.tool(annotations=read_only_tool_annotations())
def check_error_classes(computation_desc: ComputationDescriptionInput) -> dict[str, object]:
    """Identify error classes relevant to a computation description.

    Given a description of the physics computation being performed, finds the
    most relevant error classes by matching against error names and descriptions.

    Args:
        computation_desc: Description of the computation (e.g., "perturbative QCD
                         vacuum polarization at one loop with dimensional regularization").
    """
    with gpd_span("mcp.errors.check"):
        try:
            if not isinstance(computation_desc, str) or not computation_desc.strip():
                return stable_mcp_error("computation_desc must be a non-empty string")
            computation_desc = computation_desc.strip()
            store = _get_store()
            matches = store.check_relevant(computation_desc)
            return stable_mcp_response(
                {
                    "query": computation_desc,
                    "match_count": len(matches),
                    "error_classes": matches[:15],  # Top 15 matches
                }
            )
        except (OSError, ValueError, KeyError) as exc:
            return stable_mcp_error(exc)
        except Exception as exc:  # pragma: no cover - defensive envelope
            return stable_mcp_error(exc)


@mcp.tool(annotations=read_only_tool_annotations())
def get_detection_strategy(error_id: int) -> dict[str, object]:
    """Get the detection strategy for a specific error class.

    Returns the specific tests and checks to detect this type of physics error.

    Args:
        error_id: Numeric error class ID (1-104).
    """
    with gpd_span("mcp.errors.detection_strategy", error_class_id=error_id):
        try:
            store = _get_store()
            error = store.get(error_id)
            if error is None:
                return stable_mcp_response({"valid_range": "1-104"}, error=f"Error class #{error_id} not found")
            return stable_mcp_response(
                {
                    "id": error["id"],
                    "name": error["name"],
                    "detection_strategy": error["detection_strategy"],
                    "example": error["example"],
                }
            )
        except (OSError, ValueError, KeyError) as exc:
            return stable_mcp_error(exc)
        except Exception as exc:  # pragma: no cover - defensive envelope
            return stable_mcp_error(exc)


@mcp.tool(annotations=read_only_tool_annotations())
def get_traceability(error_id: int) -> dict[str, object]:
    """Get the verification check coverage for an error class.

    Returns which verification checks (dimensional analysis, limiting cases,
    symmetry, conservation, etc.) can detect this error class, from the
    traceability matrix.

    Args:
        error_id: Numeric error class ID (1-104).
    """
    with gpd_span("mcp.errors.traceability", error_class_id=error_id):
        try:
            store = _get_store()
            error = store.get(error_id)
            if error is None:
                return stable_mcp_response({"valid_range": "1-104"}, error=f"Error class #{error_id} not found")

            traceability = store.get_traceability(error_id)
            if traceability is None:
                return stable_mcp_response(
                    {
                        "id": error_id,
                        "name": error["name"],
                        "verification_checks": {},
                        "covered_by": [],
                        "coverage_count": 0,
                        "note": "No traceability data available for this error class",
                    }
                )

            return stable_mcp_response(
                {
                    "id": error_id,
                    "name": error["name"],
                    "verification_checks": traceability,
                    "covered_by": [col for col, val in traceability.items() if val],
                    "coverage_count": len([v for v in traceability.values() if v]),
                }
            )
        except (OSError, ValueError, KeyError) as exc:
            return stable_mcp_error(exc)
        except Exception as exc:  # pragma: no cover - defensive envelope
            return stable_mcp_error(exc)


@mcp.tool(annotations=read_only_tool_annotations())
def list_error_classes(domain: ErrorDomainFilterInput = None) -> dict[str, object]:
    """List all physics error classes, optionally filtered by domain.

    Args:
        domain: Optional domain filter. Available domains:
                "core" (#1-25), "field_theory" (#26-51), "extended" (#52-71),
                "deep_domain" (#72-81), "cross_domain" (#82-101),
                "newly_identified" (#102-104).
    """
    with gpd_span("mcp.errors.list", domain=domain or "all"):
        try:
            normalized_domain = _normalize_error_domain(domain)
            store = _get_store()
            errors = store.list_all(normalized_domain)
            return stable_mcp_response(
                {
                    "count": len(errors),
                    "error_classes": errors,
                    "available_domains": store.domains,
                    "total_classes": store.count,
                }
            )
        except (OSError, ValueError, KeyError) as exc:
            return stable_mcp_error(exc)
        except Exception as exc:  # pragma: no cover - defensive envelope
            return stable_mcp_error(exc)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the gpd-errors MCP server."""
    run_mcp_server(mcp, "GPD Errors MCP Server")


tighten_registered_tool_contracts(mcp)


if __name__ == "__main__":
    main()
