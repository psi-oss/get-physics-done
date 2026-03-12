"""GPD Protocols MCP server — exposes physics computation protocols via MCP tools.

Loads protocol files from specs/references/protocols/, parses YAML frontmatter
and markdown body, and serves them via FastMCP tools.

Entry point: python -m gpd.mcp.servers.protocols_server
Console script: gpd-mcp-protocols
"""

import logging
import re
import sys
import threading
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from gpd.core.observability import gpd_span
from gpd.mcp.servers import parse_frontmatter_safe, run_mcp_server
from gpd.specs import SPECS_DIR

# MCP stdio uses stdout for JSON-RPC — redirect logging to stderr
logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(name)s %(levelname)s: %(message)s")
logger = logging.getLogger("gpd-protocols")

PROTOCOLS_DIR = SPECS_DIR / "references" / "protocols"

# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

_HEADING_RE = re.compile(r"^(#{1,4})\s+(.+)$", re.MULTILINE)


def _extract_sections(body: str) -> list[dict[str, str | int]]:
    """Extract H2/H3 sections from markdown body."""
    sections: list[dict[str, str | int]] = []
    matches = list(_HEADING_RE.finditer(body))
    for i, match in enumerate(matches):
        level = len(match.group(1))
        title = match.group(2).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        content = body[start:end].strip()
        sections.append({"level": level, "title": title, "content": content})
    return sections


def _extract_steps_and_checkpoints(body: str) -> tuple[list[str], list[str]]:
    """Extract procedural steps and verification checkpoints from the body.

    Parses sections once and extracts both in a single pass (avoids
    duplicate ``_extract_sections`` calls).
    """
    steps: list[str] = []
    checkpoints: list[str] = []
    for section in _extract_sections(body):
        title_lower = section["title"].lower()
        if any(kw in title_lower for kw in ("step", "procedure", "method", "organization", "approach")):
            for line in section["content"].split("\n"):
                stripped = line.strip()
                if re.match(r"^(\d+\.|[-*])\s+", stripped):
                    steps.append(re.sub(r"^(\d+\.|[-*])\s+", "", stripped).strip())
        elif any(kw in title_lower for kw in ("verification", "checkpoint", "check", "common pitfall", "common error")):
            for line in section["content"].split("\n"):
                stripped = line.strip()
                if re.match(r"^(\d+\.|[-*])\s+", stripped):
                    checkpoints.append(re.sub(r"^(\d+\.|[-*])\s+", "", stripped).strip())
    return steps, checkpoints


def _infer_domain(name: str, _load_when: list[str]) -> str:
    """Infer a domain category from the protocol name and load_when keywords."""
    # Domain mapping based on shared-protocols.md categories
    core_derivation = {
        "derivation-discipline",
        "integral-evaluation",
        "perturbation-theory",
        "renormalization-group",
        "path-integrals",
        "effective-field-theory",
        "electrodynamics",
        "analytic-continuation",
        "order-of-limits",
        "classical-mechanics",
        "hamiltonian-mechanics",
        "scattering-theory",
        "supersymmetry",
        "string-field-theory",
        "cosmological-perturbation-theory",
        "holography-ads-cft",
        "quantum-error-correction",
        "resummation",
        "asymptotic-symmetries",
        "generalized-symmetries",
    }
    computational = {
        "monte-carlo",
        "variational-methods",
        "density-functional-theory",
        "lattice-gauge-theory",
        "tensor-networks",
        "symmetry-analysis",
        "non-equilibrium-transport",
        "finite-temperature-field-theory",
        "conformal-bootstrap",
        "numerical-relativity",
        "exact-diagonalization",
        "many-body-perturbation-theory",
        "molecular-dynamics",
        "machine-learning-physics",
        "stochastic-processes",
        "kinetic-theory",
        "bethe-ansatz",
        "random-matrix-theory",
    }
    mathematical = {
        "algebraic-qft",
        "group-theory",
        "topological-methods",
        "green-functions",
        "wkb-semiclassical",
        "large-n-expansion",
        "statistical-inference",
    }
    numerical = {"numerical-computation", "symbolic-to-numerical"}
    domain_standalone = {
        "general-relativity": "gr_cosmology",
        "fluid-dynamics-mhd": "fluid_plasma",
        "open-quantum-systems": "quantum_info",
        "quantum-many-body": "condensed_matter",
        "de-sitter-space": "gr_cosmology",
        "phenomenology": "nuclear_particle",
    }

    if name in domain_standalone:
        return domain_standalone[name]
    if name in core_derivation:
        return "core_derivation"
    if name in computational:
        return "computational_methods"
    if name in mathematical:
        return "mathematical_methods"
    if name in numerical:
        return "numerical_translation"
    return "general"


def _normalize_protocol_tier(raw: object, *, protocol_name: str) -> int:
    """Return a safe integer tier for protocol sorting and ranking."""
    if isinstance(raw, int):
        return raw
    if isinstance(raw, str):
        stripped = raw.strip()
        if stripped:
            try:
                return int(stripped)
            except ValueError:
                pass

    logger.warning("Protocol %s has invalid tier %r; defaulting to 2", protocol_name, raw)
    return 2


# ---------------------------------------------------------------------------
# Protocol Store
# ---------------------------------------------------------------------------


class ProtocolStore:
    """In-memory store of parsed protocol files."""

    def __init__(self, protocols_dir: Path) -> None:
        self._protocols: dict[str, dict[str, object]] = {}
        self._load_all(protocols_dir)

    def _load_all(self, protocols_dir: Path) -> None:
        with gpd_span("protocols.load_all", protocols_dir=str(protocols_dir)):
            self._do_load(protocols_dir)

    def _do_load(self, protocols_dir: Path) -> None:
        if not protocols_dir.is_dir():
            logger.warning("Protocols directory not found: %s", protocols_dir)
            return
        for path in sorted(protocols_dir.glob("*.md")):
            name = path.stem
            try:
                text = path.read_text(encoding="utf-8")
            except OSError as exc:
                logger.warning("Failed to read %s: %s", path, exc)
                continue

            meta, body = parse_frontmatter_safe(text)
            load_when = meta.get("load_when", [])
            if not isinstance(load_when, list):
                load_when = []
            tier = _normalize_protocol_tier(meta.get("tier", 2), protocol_name=name)
            context_cost = meta.get("context_cost", "medium")

            domain = _infer_domain(name, load_when)
            steps, checkpoints = _extract_steps_and_checkpoints(body)

            # Extract title from first H1
            title_match = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
            title = title_match.group(1).strip() if title_match else name.replace("-", " ").title()

            self._protocols[name] = {
                "name": name,
                "title": title,
                "domain": domain,
                "tier": tier,
                "context_cost": context_cost,
                "load_when": load_when,
                "steps": steps,
                "checkpoints": checkpoints,
                "body": body,
            }

        logger.info("Loaded %d protocols from %s", len(self._protocols), protocols_dir)

    def get(self, name: str) -> dict[str, object] | None:
        """Get a protocol by name (stem of the .md file)."""
        return self._protocols.get(name)

    def list_all(self, domain: str | None = None) -> list[dict[str, object]]:
        """List protocols, optionally filtered by domain."""
        result = []
        for p in self._protocols.values():
            if domain and p["domain"] != domain:
                continue
            result.append(
                {
                    "name": p["name"],
                    "title": p["title"],
                    "domain": p["domain"],
                    "tier": p["tier"],
                    "context_cost": p["context_cost"],
                    "load_when": p["load_when"],
                }
            )
        return sorted(result, key=lambda x: (x["tier"], str(x["name"])))

    def route(self, computation_type: str) -> list[dict[str, object]]:
        """Find protocols matching a computation type description.

        Matches against load_when keywords using case-insensitive substring matching.
        """
        query = computation_type.lower()
        scored: list[tuple[int, dict[str, object]]] = []

        for p in self._protocols.values():
            score = 0
            # Check load_when keywords
            for keyword in p["load_when"]:
                if isinstance(keyword, str) and keyword.lower() in query:
                    score += 10
                elif isinstance(keyword, str) and any(w in query for w in keyword.lower().split()):
                    score += 3

            # Check protocol name
            name_words = str(p["name"]).replace("-", " ").split()
            for w in name_words:
                if w.lower() in query:
                    score += 5

            # Tier 1 protocols get a bonus
            if p["tier"] == 1:
                score += 2

            if score > 0:
                scored.append(
                    (
                        score,
                        {
                            "name": p["name"],
                            "title": p["title"],
                            "domain": p["domain"],
                            "tier": p["tier"],
                            "context_cost": p["context_cost"],
                            "relevance_score": score,
                        },
                    )
                )

        scored.sort(key=lambda x: -x[0])
        return [item for _, item in scored]

    @property
    def domains(self) -> list[str]:
        """List all unique domains."""
        return sorted({str(p["domain"]) for p in self._protocols.values()})


# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------

_store: ProtocolStore | None = None
_store_lock = threading.Lock()


def _get_store() -> ProtocolStore:
    """Return the lazily-initialised protocol store (thread-safe)."""
    global _store  # noqa: PLW0603
    if _store is not None:
        return _store
    with _store_lock:
        if _store is None:
            _store = ProtocolStore(PROTOCOLS_DIR)
        return _store


mcp = FastMCP("gpd-protocols")


@mcp.tool()
def get_protocol(name: str) -> dict[str, object]:
    """Get a physics computation protocol by name.

    Returns the full protocol content including steps, checkpoints,
    and the raw markdown body.

    Args:
        name: Protocol name (e.g., "perturbation-theory", "renormalization-group").
              Use the stem of the .md filename without extension.
    """
    with gpd_span("mcp.protocols.get", protocol_name=name):
        store = _get_store()
        protocol = store.get(name)
        if protocol is None:
            available = [str(p["name"]) for p in store.list_all()]
            return {"error": f"Protocol '{name}' not found", "available": available}
        return {
            "name": protocol["name"],
            "title": protocol["title"],
            "domain": protocol["domain"],
            "tier": protocol["tier"],
            "context_cost": protocol["context_cost"],
            "load_when": protocol["load_when"],
            "steps": protocol["steps"],
            "checkpoints": protocol["checkpoints"],
            "content": protocol["body"],
        }


@mcp.tool()
def list_protocols(domain: str | None = None) -> dict[str, object]:
    """List available physics computation protocols.

    Args:
        domain: Optional domain filter. Available domains include:
                "core_derivation", "computational_methods", "mathematical_methods",
                "numerical_translation", "gr_cosmology", "fluid_plasma",
                "quantum_info", "condensed_matter", "general".
    """
    with gpd_span("mcp.protocols.list", domain=domain or "all"):
        store = _get_store()
        protocols = store.list_all(domain)
        return {
            "count": len(protocols),
            "protocols": protocols,
            "available_domains": store.domains,
        }


@mcp.tool()
def route_protocol(computation_type: str) -> dict[str, object]:
    """Auto-select the best protocols for a computation type.

    Given a description of the computation being performed, finds the most
    relevant protocols by matching against load_when keywords and protocol names.

    Args:
        computation_type: Description of the computation (e.g., "perturbative QCD
                         calculation of vacuum polarization at one loop").
    """
    with gpd_span("mcp.protocols.route"):
        store = _get_store()
        matches = store.route(computation_type)
        return {
            "query": computation_type,
            "match_count": len(matches),
            "protocols": matches[:10],  # Top 10 matches
        }


@mcp.tool()
def get_protocol_checkpoints(name: str) -> dict[str, object]:
    """Get verification checkpoints for a specific protocol.

    Returns the list of checkpoint/verification steps that should be performed
    during or after applying this protocol.

    Args:
        name: Protocol name (e.g., "perturbation-theory").
    """
    with gpd_span("mcp.protocols.checkpoints", protocol_name=name):
        store = _get_store()
        protocol = store.get(name)
        if protocol is None:
            available = [str(p["name"]) for p in store.list_all()]
            return {"error": f"Protocol '{name}' not found", "available": available}
        return {
            "name": protocol["name"],
            "title": protocol["title"],
            "checkpoints": protocol["checkpoints"],
            "checkpoint_count": len(protocol["checkpoints"]),
        }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the gpd-protocols MCP server."""
    run_mcp_server(mcp, "GPD Protocols MCP Server")


if __name__ == "__main__":
    main()
