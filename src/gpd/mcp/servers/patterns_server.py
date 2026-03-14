"""MCP server for GPD cross-project pattern library.

Thin MCP wrapper around gpd.core.patterns. Exposes pattern CRUD
and search as MCP tools for solver agents.

Usage:
    python -m gpd.mcp.servers.patterns_server
    # or via entry point:
    gpd-mcp-patterns
"""

import logging
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from gpd.core.errors import PatternError
from gpd.core.observability import gpd_span
from gpd.core.patterns import (
    VALID_CATEGORIES,
    VALID_DOMAINS,
    VALID_SEVERITIES,
    pattern_add,
    pattern_list,
    pattern_promote,
    pattern_search,
    pattern_seed,
    patterns_root,
)

logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(name)s %(levelname)s: %(message)s")
logger = logging.getLogger("gpd-patterns")

mcp = FastMCP("gpd-patterns")

# Default patterns library root — used when GPD_PATTERNS_ROOT / GPD_DATA_DIR
# env vars are not set. Falls back to the global ~/.gpd data directory.
_DEFAULT_PATTERNS_ROOT: Path | None = None


def _get_patterns_root() -> Path:
    global _DEFAULT_PATTERNS_ROOT
    if _DEFAULT_PATTERNS_ROOT is None:
        _DEFAULT_PATTERNS_ROOT = patterns_root()
    return _DEFAULT_PATTERNS_ROOT


@mcp.tool()
def lookup_pattern(
    domain: str | None = None,
    category: str | None = None,
    keywords: str | None = None,
) -> dict:
    """Search the GPD pattern library for physics error patterns.

    Searches by domain, category, or free-text keywords. Returns matching
    patterns sorted by severity and confidence.

    Args:
        domain: Filter by physics domain (e.g., "qft", "condensed-matter").
        category: Filter by error category (e.g., "sign-error", "factor-error").
        keywords: Free-text search across titles, domains, categories, and tags.
    """
    with gpd_span("mcp.patterns.lookup", domain=domain or "", category=category or ""):
        try:
            if keywords:
                result = pattern_search(keywords, root=_get_patterns_root())
                matches = result.matches
                if domain:
                    matches = [p for p in matches if p.domain == domain]
                if category:
                    matches = [p for p in matches if p.category == category]
                return {
                    "count": len(matches),
                    "patterns": [p.model_dump() for p in matches],
                    "query": result.query,
                    "library_exists": result.library_exists,
                }

            result = pattern_list(domain=domain, category=category, root=_get_patterns_root())
            return {
                "count": result.count,
                "patterns": [p.model_dump() for p in result.patterns],
                "query": None,
                "library_exists": result.library_exists,
            }
        except (PatternError, OSError) as e:
            return {"error": str(e)}


@mcp.tool()
def add_pattern(
    domain: str,
    title: str,
    category: str = "conceptual-error",
    severity: str = "medium",
    description: str = "",
    detection: str = "",
    prevention: str = "",
    example: str = "",
    test_value: str = "",
) -> dict:
    """Record a new physics error pattern in the library.

    Patterns capture recurring issues (sign errors, factor mistakes, convention
    pitfalls) that persist across physics research projects.

    Args:
        domain: Physics domain (qft, condensed-matter, stat-mech, gr, amo, nuclear, classical, fluid, plasma, astro, mathematical, soft-matter, quantum-info).
        title: Short descriptive title for the pattern.
        category: Error category (sign-error, factor-error, convention-pitfall, convergence-issue, approximation-failure, numerical-instability, conceptual-error, dimensional-error).
        severity: Severity level (critical, high, medium, low).
        description: What goes wrong.
        detection: How to detect this error.
        prevention: How to prevent it.
        example: A concrete example illustrating the pattern.
        test_value: A test value or expression for automated checks.
    """
    with gpd_span("mcp.patterns.add", domain=domain, category=category):
        try:
            result = pattern_add(
                domain=domain,
                title=title,
                category=category,
                severity=severity,
                description=description,
                detection=detection,
                prevention=prevention,
                example=example,
                test_value=test_value,
                root=_get_patterns_root(),
            )
            return result.model_dump()
        except (PatternError, OSError) as e:
            return {"error": str(e)}


@mcp.tool()
def promote_pattern(pattern_id: str) -> dict:
    """Promote a pattern's confidence level.

    Confidence progression: single_observation → confirmed → systematic.
    Also increments the occurrence count.

    Args:
        pattern_id: Pattern ID (e.g., "qft-sign-error-fourier-convention-switch").
    """
    with gpd_span("mcp.patterns.promote", pattern_id=pattern_id):
        try:
            result = pattern_promote(pattern_id, root=_get_patterns_root())
            return result.model_dump()
        except (PatternError, OSError) as e:
            return {"error": str(e)}


@mcp.tool()
def seed_patterns() -> dict:
    """Initialize the pattern library with canonical physics patterns.

    Seeds 8 bootstrap patterns covering common sign errors, factor errors,
    convention pitfalls, and dimensional mistakes in QFT, condensed matter,
    and statistical mechanics. Idempotent — safe to call multiple times.
    """
    with gpd_span("mcp.patterns.seed"):
        try:
            result = pattern_seed(root=_get_patterns_root())
            return result.model_dump()
        except (PatternError, OSError) as e:
            return {"error": str(e)}


@mcp.tool()
def list_domains() -> dict:
    """List all available physics domains and error categories.

    Returns the valid domains, categories, and severity levels for use
    when adding new patterns.
    """
    with gpd_span("mcp.patterns.list_domains"):
        return {
            "domains": sorted(VALID_DOMAINS),
            "categories": sorted(VALID_CATEGORIES),
            "severities": list(VALID_SEVERITIES),
        }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the gpd-patterns MCP server."""
    from gpd.mcp.servers import run_mcp_server

    run_mcp_server(mcp, "GPD Patterns MCP Server")


if __name__ == "__main__":
    main()
