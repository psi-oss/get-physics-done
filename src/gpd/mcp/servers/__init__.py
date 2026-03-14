"""MCP servers for GPD — conventions, verification, protocols, errors, patterns, state, skills."""

from __future__ import annotations

import argparse

from gpd.core.frontmatter import FrontmatterParseError, extract_frontmatter


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
    if args.port:
        mcp.settings.port = args.port  # type: ignore[union-attr]
    mcp.run(transport=args.transport)  # type: ignore[union-attr]


__all__ = ["parse_frontmatter_safe", "run_mcp_server"]
