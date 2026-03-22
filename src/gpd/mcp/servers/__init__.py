"""MCP servers for GPD — conventions, verification, protocols, errors, patterns, state, skills."""

from __future__ import annotations

import argparse
from collections.abc import Mapping

from gpd.core.frontmatter import FrontmatterParseError, extract_frontmatter

MCP_SCHEMA_VERSION = 1


class StableMCPEnvelope(dict[str, object]):
    """Dict envelope that remains comparable to legacy payload-only mappings."""

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Mapping):
            return super().__eq__(other)

        envelope = dict(self)
        other_mapping = dict(other)
        if "schema_version" not in other_mapping:
            envelope.pop("schema_version", None)
        return envelope == other_mapping


def stable_mcp_response(
    payload: Mapping[str, object] | None = None,
    *,
    error: object | None = None,
) -> StableMCPEnvelope:
    """Return a stable MCP response envelope without nesting the payload."""

    response = StableMCPEnvelope()
    if payload is not None:
        response.update(payload)
    if error is not None:
        response["error"] = str(error)
    response["schema_version"] = MCP_SCHEMA_VERSION
    return response


def stable_mcp_error(error: object) -> StableMCPEnvelope:
    """Return a stable MCP error envelope."""

    return stable_mcp_response(error=error)


def parse_frontmatter_safe(text: str) -> tuple[dict[str, object], str]:
    """Split YAML frontmatter from markdown body, returning ({}, text) on parse error.

    Shared helper for MCP servers that bulk-load markdown files and need
    graceful handling of malformed YAML.
    """
    try:
        return extract_frontmatter(text)
    except FrontmatterParseError:
        return {}, text


def run_mcp_server(mcp: object, description: str) -> None:
    """Run an MCP server with standard CLI arguments (transport, host, port).

    Every MCP server in this package uses the same entry-point pattern.
    This function eliminates that boilerplate.

    Args:
        mcp: A FastMCP instance.
        description: CLI description string.
    """
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--transport", choices=["stdio", "sse", "streamable-http"], default="stdio")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args()
    if args.host:
        mcp.settings.host = args.host  # type: ignore[union-attr]
    if args.port is not None:
        mcp.settings.port = args.port  # type: ignore[union-attr]
    mcp.run(transport=args.transport)  # type: ignore[union-attr]


__all__ = [
    "MCP_SCHEMA_VERSION",
    "StableMCPEnvelope",
    "parse_frontmatter_safe",
    "run_mcp_server",
    "stable_mcp_error",
    "stable_mcp_response",
]
