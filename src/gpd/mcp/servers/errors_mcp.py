"""GPD Errors MCP server — exposes physics error catalog and traceability via MCP tools.

Loads the error catalog files and traceability matrix from
specs/references/verification/errors/, parses markdown tables, and serves them
via FastMCP tools.

Entry point: python -m gpd.mcp.servers.errors_mcp
Console script: gpd-mcp-errors
"""

import logging
import re
import sys
import threading
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from gpd.core.observability import gpd_span
from gpd.mcp.servers import (
    parse_frontmatter_safe,
    run_mcp_server,
    stable_mcp_error,
    stable_mcp_response,
)
from gpd.specs import SPECS_DIR

# MCP stdio uses stdout for JSON-RPC — redirect logging to stderr
logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(name)s %(levelname)s: %(message)s")
logger = logging.getLogger("gpd-errors")

REFERENCES_DIR = SPECS_DIR / "references"

# The 4 error catalog part files (ordered by error ID range)
ERROR_CATALOG_FILES = [
    "verification/errors/llm-errors-core.md",  # #1-25
    "verification/errors/llm-errors-field-theory.md",  # #26-51
    "verification/errors/llm-errors-extended.md",  # #52-81, #102-104
    "verification/errors/llm-errors-deep.md",  # #82-101
]

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
    if 1 <= error_id <= 25:
        return "core"
    if 26 <= error_id <= 51:
        return "field_theory"
    if 52 <= error_id <= 71:
        return "extended"
    if 72 <= error_id <= 81:
        return "deep_domain"
    if 82 <= error_id <= 101:
        return "cross_domain"
    if 102 <= error_id <= 104:
        return "newly_identified"
    return "unknown"


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
            if not path.is_file():
                logger.warning("Error catalog not found: %s", path)
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except OSError as exc:
                logger.warning("Failed to read %s: %s", path, exc)
                continue

            _, body = parse_frontmatter_safe(text)
            rows = _parse_table_rows(body)

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

                name = _strip_bold(row[1].strip())
                description = row[2].strip()
                detection_strategy = row[3].strip()
                example = row[4].strip()

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

        logger.info("Loaded %d error classes from catalogs", len(self._errors))

    def _load_traceability(self, references_dir: Path) -> None:
        """Load the traceability matrix mapping errors to verification checks."""
        with gpd_span("errors.load_traceability"):
            self._do_load_traceability(references_dir)

    def _do_load_traceability(self, references_dir: Path) -> None:
        path = references_dir / TRACEABILITY_FILE
        if not path.is_file():
            logger.warning("Traceability matrix not found: %s", path)
            return
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            logger.warning("Failed to read %s: %s", path, exc)
            return

        _, body = parse_frontmatter_safe(text)
        rows = _parse_table_rows(body)

        for row in rows:
            if len(row) < 2:
                continue
            # First cell format: "1. Wrong CG coefficients" or "# Error Class"
            first = row[0].strip()
            id_match = re.match(r"(\d+)\.", first)
            if not id_match:
                continue
            error_id = int(id_match.group(1))

            # Map remaining cells to traceability columns
            checks: dict[str, str] = {}
            for i, col_name in enumerate(TRACEABILITY_COLUMNS):
                cell_idx = i + 1  # offset past the first column
                if cell_idx < len(row):
                    value = row[cell_idx].strip()
                    if value:
                        checks[col_name] = value

            self._traceability[error_id] = checks

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


@mcp.tool()
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


@mcp.tool()
def check_error_classes(computation_desc: str) -> dict[str, object]:
    """Identify error classes relevant to a computation description.

    Given a description of the physics computation being performed, finds the
    most relevant error classes by matching against error names and descriptions.

    Args:
        computation_desc: Description of the computation (e.g., "perturbative QCD
                         vacuum polarization at one loop with dimensional regularization").
    """
    with gpd_span("mcp.errors.check"):
        try:
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


@mcp.tool()
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


@mcp.tool()
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


@mcp.tool()
def list_error_classes(domain: str | None = None) -> dict[str, object]:
    """List all physics error classes, optionally filtered by domain.

    Args:
        domain: Optional domain filter. Available domains:
                "core" (#1-25), "field_theory" (#26-51), "extended" (#52-71),
                "deep_domain" (#72-81), "cross_domain" (#82-101),
                "newly_identified" (#102-104).
    """
    with gpd_span("mcp.errors.list", domain=domain or "all"):
        try:
            store = _get_store()
            errors = store.list_all(domain)
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


if __name__ == "__main__":
    main()
