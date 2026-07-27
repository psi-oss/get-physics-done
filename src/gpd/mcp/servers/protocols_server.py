"""GPD Protocols MCP server — exposes physics computation protocols via MCP tools.

The protocol catalog itself (loading, parsing, routing, query payloads) lives in
``gpd.core.protocol_catalog``; this module is the MCP transport surface only:
tool registration, published input contracts, and stable response envelopes.

Entry point: python -m gpd.mcp.servers.protocols_server
Console script: gpd-mcp-protocols
"""

import threading
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from gpd.core.observability import gpd_span
from gpd.core.protocol_catalog import (
    PROTOCOL_DOMAINS_MANIFEST,
    PROTOCOL_USAGE_CAUTION,
    PROTOCOLS_DIR,
    available_protocol_names,
    extract_protocol_sections,
    extract_protocol_steps_and_checkpoints,
    parse_protocol_domain_manifest,
    protocol_checkpoints_payload,
    protocol_detail_payload,
    protocol_domain_values,
    protocol_listing_payload,
    protocol_route_payload,
)
from gpd.core.protocol_catalog import (
    ProtocolStore as CoreProtocolStore,
)
from gpd.mcp.servers import (
    configure_mcp_logging,
    published_tool_input_schema,
    read_only_tool_annotations,
    refresh_string_enum_property_schema,
    run_mcp_server,
    set_registered_and_published_tool_input_schema,
    stable_mcp_error,
    stable_mcp_response,
    tighten_registered_tool_contracts,
)

logger = configure_mcp_logging("gpd-protocols", ("gpd.core.protocol_catalog",))

# Catalog names kept on this module so the MCP surface (tools, schema refresh,
# and their tests) has one import site; the implementations live in core.
_PROTOCOL_USAGE_CAUTION = PROTOCOL_USAGE_CAUTION
_extract_sections = extract_protocol_sections
_extract_steps_and_checkpoints = extract_protocol_steps_and_checkpoints


@lru_cache(maxsize=1)
def _load_protocol_domain_manifest() -> dict[str, str]:
    """Load the authoritative protocol-domain manifest for this server."""
    return parse_protocol_domain_manifest(PROTOCOL_DOMAINS_MANIFEST)


def _protocol_domain_values() -> tuple[str, ...]:
    """Return the authoritative protocol-domain enum values."""

    return protocol_domain_values(_load_protocol_domain_manifest())


class ProtocolStore(CoreProtocolStore):
    """Protocol store bound to this server's protocol-domain manifest."""

    def __init__(self, protocols_dir: Path) -> None:
        super().__init__(protocols_dir, domain_manifest_loader=_load_protocol_domain_manifest)


ProtocolDomainFilter = str


def _schema_with_refreshed_protocol_domain_enum(schema: dict[str, object]) -> dict[str, object]:
    """Return one published schema with the live protocol-domain enum refreshed."""

    return refresh_string_enum_property_schema(
        schema,
        property_name="domain",
        enum_values=list(_protocol_domain_values()),
    )


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


@mcp.tool(annotations=read_only_tool_annotations())
def get_protocol(name: Annotated[str, Field(min_length=1, pattern=r"\S")]) -> dict[str, object]:
    """Get a physics computation protocol by name.

    Returns the full protocol content including steps, checkpoints,
    and the raw markdown body.

    Args:
        name: Protocol name (e.g., "perturbation-theory", "renormalization-group").
              Use the stem of the .md filename without extension.
    """
    if not isinstance(name, str) or not name.strip():
        return stable_mcp_response(error="name must be a non-empty string")

    with gpd_span("mcp.protocols.get", protocol_name=name):
        try:
            store = _get_store()
            payload = protocol_detail_payload(store, name)
            if payload is None:
                return stable_mcp_response(
                    {"available": available_protocol_names(store)},
                    error=f"Protocol '{name}' not found",
                )
            return stable_mcp_response(payload)
        except Exception as exc:  # pragma: no cover - defensive envelope
            return stable_mcp_error(exc)


@mcp.tool(annotations=read_only_tool_annotations())
def list_protocols(
    domain: Annotated[ProtocolDomainFilter, Field(min_length=1, pattern=r"\S")] | None = None,
) -> dict[str, object]:
    """List available physics computation protocols.

    Args:
        domain: Optional domain filter. Use one of the values returned in
                ``available_domains``.
    """
    if domain is not None and (not isinstance(domain, str) or not domain.strip()):
        return stable_mcp_response(error="domain must be a non-empty string when provided")

    with gpd_span("mcp.protocols.list", domain=domain or "all"):
        try:
            return stable_mcp_response(protocol_listing_payload(_get_store(), domain))
        except Exception as exc:  # pragma: no cover - defensive envelope
            return stable_mcp_error(exc)


@mcp.tool(annotations=read_only_tool_annotations())
def route_protocol(
    computation_type: Annotated[str, Field(min_length=1, pattern=r"\S")],
) -> dict[str, object]:
    """Auto-select the best protocols for a computation type.

    Given a description of the computation being performed, finds the most
    relevant protocols by matching against load_when keywords and protocol names.

    Args:
        computation_type: Description of the computation (e.g., "perturbative QCD
                         calculation of vacuum polarization at one loop").
    """
    if not isinstance(computation_type, str) or not computation_type.strip():
        return stable_mcp_response(error="computation_type must be a non-empty string")

    with gpd_span("mcp.protocols.route"):
        try:
            return stable_mcp_response(protocol_route_payload(_get_store(), computation_type))
        except Exception as exc:  # pragma: no cover - defensive envelope
            return stable_mcp_error(exc)


@mcp.tool(annotations=read_only_tool_annotations())
def get_protocol_checkpoints(name: Annotated[str, Field(min_length=1, pattern=r"\S")]) -> dict[str, object]:
    """Get verification checkpoints for a specific protocol.

    Returns the list of checkpoint/verification steps that should be performed
    during or after applying this protocol.

    Args:
        name: Protocol name (e.g., "perturbation-theory").
    """
    if not isinstance(name, str) or not name.strip():
        return stable_mcp_response(error="name must be a non-empty string")

    with gpd_span("mcp.protocols.checkpoints", protocol_name=name):
        try:
            store = _get_store()
            payload = protocol_checkpoints_payload(store, name)
            if payload is None:
                return stable_mcp_response(
                    {"available": available_protocol_names(store)},
                    error=f"Protocol '{name}' not found",
                )
            return stable_mcp_response(payload)
        except Exception as exc:  # pragma: no cover - defensive envelope
            return stable_mcp_error(exc)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the gpd-protocols MCP server."""
    run_mcp_server(mcp, "GPD Protocols MCP Server")


tighten_registered_tool_contracts(mcp)

_BASE_LIST_TOOLS = mcp.list_tools


async def _list_tools_with_fresh_protocol_schema():
    tools = await _BASE_LIST_TOOLS()
    for tool in tools:
        if tool.name != "list_protocols":
            continue
        schema = published_tool_input_schema(tool)
        if schema is None:
            continue
        set_registered_and_published_tool_input_schema(
            mcp,
            tool,
            _schema_with_refreshed_protocol_domain_enum(schema),
        )
    return tools


mcp.list_tools = _list_tools_with_fresh_protocol_schema


if __name__ == "__main__":
    main()
