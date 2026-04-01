"""GPD Protocols MCP server — exposes physics computation protocols via MCP tools.

Loads protocol files from specs/references/protocols/, parses YAML frontmatter
and markdown body, and serves them via FastMCP tools.

Entry point: python -m gpd.mcp.servers.protocols_server
Console script: gpd-mcp-protocols
"""

import json
import logging
import re
import sys
import threading
from functools import lru_cache
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from pydantic import ConfigDict, create_model
from pydantic import ValidationError as PydanticValidationError

from gpd.core.observability import gpd_span
from gpd.mcp.servers import (
    parse_frontmatter_with_error,
    run_mcp_server,
    stable_mcp_error,
    stable_mcp_response,
)
from gpd.specs import SPECS_DIR

# MCP stdio uses stdout for JSON-RPC — redirect logging to stderr
logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(name)s %(levelname)s: %(message)s")
logger = logging.getLogger("gpd-protocols")

PROTOCOLS_DIR = SPECS_DIR / "references" / "protocols"
PROTOCOL_DOMAINS_MANIFEST = PROTOCOLS_DIR / "protocol-domains.json"

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


@lru_cache(maxsize=1)
def _load_protocol_domain_manifest() -> dict[str, str]:
    """Load the authoritative protocol-domain manifest."""
    try:
        raw = json.loads(PROTOCOL_DOMAINS_MANIFEST.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Failed to read protocol domain manifest {PROTOCOL_DOMAINS_MANIFEST}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ValueError("Protocol domain manifest must be a JSON object")

    allowed_keys = {"schema_version", "protocol_domains"}
    extra_keys = sorted(str(key) for key in raw if str(key) not in allowed_keys)
    if extra_keys:
        raise ValueError(f"Protocol domain manifest has unexpected keys: {', '.join(extra_keys)}")

    schema_version = raw.get("schema_version")
    if not isinstance(schema_version, int) or isinstance(schema_version, bool) or schema_version != 1:
        raise ValueError(f"Unsupported protocol domain manifest schema_version: {raw.get('schema_version')!r}")

    protocol_domains = raw.get("protocol_domains")
    if not isinstance(protocol_domains, dict) or not protocol_domains:
        raise ValueError("Protocol domain manifest must include a non-empty protocol_domains object")

    domains: dict[str, str] = {}
    for protocol_name, domain in protocol_domains.items():
        if not isinstance(protocol_name, str) or not protocol_name.strip():
            raise ValueError("Protocol domain manifest contains a blank protocol name")
        if not isinstance(domain, str) or not domain.strip():
            raise ValueError(f"Protocol domain manifest for {protocol_name!r} must be a non-empty string")
        normalized_name = protocol_name.strip()
        normalized_domain = domain.strip()
        if normalized_name in domains:
            raise ValueError(f"Protocol domain manifest contains duplicate protocol {normalized_name!r}")
        domains[normalized_name] = normalized_domain
    return domains


def _protocol_domain(name: str) -> str:
    """Return the authoritative domain for one protocol name."""
    domains = _load_protocol_domain_manifest()
    try:
        return domains[name]
    except KeyError as exc:
        raise ValueError(f"Protocol {name!r} is missing domain metadata in {PROTOCOL_DOMAINS_MANIFEST.name}") from exc


def _normalize_protocol_tier(raw: object, *, protocol_name: str) -> int:
    """Return a safe integer tier for protocol sorting and ranking."""
    if isinstance(raw, bool):
        logger.warning("Protocol %s has invalid tier %r; defaulting to 2", protocol_name, raw)
        return 2
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


def _normalize_protocol_load_when(raw: object, *, protocol_name: str) -> list[str]:
    """Return a safe ``load_when`` keyword list for protocol routing."""
    if raw is None:
        return []
    if not isinstance(raw, list):
        logger.warning("Protocol %s has invalid load_when %r; defaulting to []", protocol_name, raw)
        return []

    cleaned: list[str] = []
    invalid_item_seen = False
    for item in raw:
        if isinstance(item, str):
            stripped = item.strip()
            if stripped:
                cleaned.append(stripped)
                continue
        invalid_item_seen = True

    if invalid_item_seen:
        logger.warning("Protocol %s has invalid load_when entries %r; dropping non-string items", protocol_name, raw)
    return cleaned


def _normalize_protocol_context_cost(raw: object, *, protocol_name: str) -> str:
    """Return a safe string ``context_cost`` label for protocol metadata."""
    if isinstance(raw, str):
        stripped = raw.strip()
        if stripped:
            return stripped

    logger.warning("Protocol %s has invalid context_cost %r; defaulting to 'medium'", protocol_name, raw)
    return "medium"


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
        domain_manifest = _load_protocol_domain_manifest()
        protocol_files = sorted(protocols_dir.glob("*.md"))
        protocol_names = {path.stem for path in protocol_files}
        for path in protocol_files:
            name = path.stem
            try:
                text = path.read_text(encoding="utf-8")
            except OSError as exc:
                logger.warning("Failed to read %s: %s", path, exc)
                continue

            meta, body, parse_error = parse_frontmatter_with_error(text)
            if parse_error is not None:
                logger.warning("Skipping protocol %s: malformed frontmatter (%s)", path, parse_error)
                continue
            load_when = _normalize_protocol_load_when(meta.get("load_when", []), protocol_name=name)
            tier = _normalize_protocol_tier(meta.get("tier", 2), protocol_name=name)
            context_cost = _normalize_protocol_context_cost(meta.get("context_cost", "medium"), protocol_name=name)

            domain = _protocol_domain(name)
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

        unused_manifest_entries = sorted(name for name in domain_manifest if name not in protocol_names)
        if unused_manifest_entries:
            raise ValueError(
                "Protocol domain manifest has entries without protocol files: " + ", ".join(unused_manifest_entries)
            )

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


def _tighten_registered_tool_contracts() -> None:
    def _build_strict_call(original_call, allowed_keys):
        async def _strict_call_fn_with_arg_validation(fn, fn_is_async, arguments_to_validate, arguments_to_pass_directly):
            unknown_keys = sorted(str(key) for key in arguments_to_validate if key not in allowed_keys)
            if unknown_keys:
                return stable_mcp_error(f"Unsupported arguments: {', '.join(unknown_keys)}")
            try:
                return await original_call(fn, fn_is_async, arguments_to_validate, arguments_to_pass_directly)
            except PydanticValidationError as exc:
                return stable_mcp_error(exc)

        return _strict_call_fn_with_arg_validation

    for tool in mcp._tool_manager.list_tools():  # type: ignore[attr-defined]
        arg_model = tool.fn_metadata.arg_model
        strict_model = create_model(
            f"{arg_model.__name__}Strict",
            __base__=arg_model,
            __config__=ConfigDict(extra="forbid", arbitrary_types_allowed=True),
        )
        tool.parameters = strict_model.model_json_schema(by_alias=True)
        allowed_keys = {
            key
            for field_name, field_info in arg_model.model_fields.items()
            for key in (field_name, field_info.alias)
            if key is not None
        }
        original_call = tool.fn_metadata.call_fn_with_arg_validation
        object.__setattr__(tool.fn_metadata, "call_fn_with_arg_validation", _build_strict_call(original_call, allowed_keys))


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
        try:
            store = _get_store()
            protocol = store.get(name)
            if protocol is None:
                available = [str(p["name"]) for p in store.list_all()]
                return stable_mcp_response({"available": available}, error=f"Protocol '{name}' not found")
            return stable_mcp_response(
                {
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
            )
        except Exception as exc:  # pragma: no cover - defensive envelope
            return stable_mcp_error(exc)


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
        try:
            store = _get_store()
            protocols = store.list_all(domain)
            return stable_mcp_response(
                {
                    "count": len(protocols),
                    "protocols": protocols,
                    "available_domains": store.domains,
                }
            )
        except Exception as exc:  # pragma: no cover - defensive envelope
            return stable_mcp_error(exc)


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
        try:
            store = _get_store()
            matches = store.route(computation_type)
            return stable_mcp_response(
                {
                    "query": computation_type,
                    "match_count": len(matches),
                    "protocols": matches[:10],  # Top 10 matches
                }
            )
        except Exception as exc:  # pragma: no cover - defensive envelope
            return stable_mcp_error(exc)


@mcp.tool()
def get_protocol_checkpoints(name: str) -> dict[str, object]:
    """Get verification checkpoints for a specific protocol.

    Returns the list of checkpoint/verification steps that should be performed
    during or after applying this protocol.

    Args:
        name: Protocol name (e.g., "perturbation-theory").
    """
    with gpd_span("mcp.protocols.checkpoints", protocol_name=name):
        try:
            store = _get_store()
            protocol = store.get(name)
            if protocol is None:
                available = [str(p["name"]) for p in store.list_all()]
                return stable_mcp_response({"available": available}, error=f"Protocol '{name}' not found")
            return stable_mcp_response(
                {
                    "name": protocol["name"],
                    "title": protocol["title"],
                    "checkpoints": protocol["checkpoints"],
                    "checkpoint_count": len(protocol["checkpoints"]),
                }
            )
        except Exception as exc:  # pragma: no cover - defensive envelope
            return stable_mcp_error(exc)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the gpd-protocols MCP server."""
    run_mcp_server(mcp, "GPD Protocols MCP Server")


_tighten_registered_tool_contracts()


if __name__ == "__main__":
    main()
