"""GPD-owned bridge for the optional no-network ``gpd-compute`` MCP server.

``gpd-compute`` is a separate public package that provides a sandboxed,
no-network numeric evaluator (mpmath/numpy) used by GPD's executed
numeric-oracle verification. This thin bridge launches that package's MCP
server so GPD can register it as an optional built-in server, exactly as
``gpd-arxiv`` bridges the optional ``arxiv-mcp-server`` package.

The external package is imported lazily inside :func:`main` so this module stays
importable for descriptor and metadata introspection even when the optional
``compute`` extra is not installed. It performs no network access and requires
no API keys.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("gpd.compute_bridge")

#: Name of the external package this bridge launches. Used as the optional
#: ``module_check`` so the server is only advertised when the extra is present.
UPSTREAM_COMPUTE_MODULE = "gpd_compute"

#: Tools advertised by the ``gpd-compute`` MCP server. The public descriptor's
#: capabilities are derived from this tuple, so it must track the external
#: package's published tool surface.
ADVERTISED_TOOL_NAMES: tuple[str, ...] = (
    "evaluate_expression",
    "evaluator_hash",
    "probe_capability",
    "describe_runtime",
)

_MISSING_DEPENDENCY_MESSAGE = (
    "gpd-compute is not installed. Install GPD with the 'compute' extra "
    "(for example: pip install 'get-physics-done[compute]') to enable the "
    "gpd-compute MCP server."
)


def main() -> None:
    """Console entry point: launch the external ``gpd-compute`` MCP server."""
    try:
        from gpd_compute.server import main as _compute_main
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise SystemExit(_MISSING_DEPENDENCY_MESSAGE) from exc
    _compute_main()


if __name__ == "__main__":
    main()
