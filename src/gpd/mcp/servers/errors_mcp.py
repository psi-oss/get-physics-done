"""GPD Errors MCP server — exposes physics error catalog and traceability via MCP tools.

Transport layer only: the catalog parsing and query logic lives in
``gpd.core.error_catalog``. This module binds that core to FastMCP tools and
the stable MCP response envelope.

Entry point: python -m gpd.mcp.servers.errors_mcp
Console script: gpd-mcp-errors
"""

from pathlib import Path
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field, WithJsonSchema

from gpd.core import error_catalog

# Catalog layout constants and parsing helpers are re-exported so this module
# stays the stable import surface for the gpd-errors server.
from gpd.core.error_catalog import (  # noqa: F401
    ERROR_CATALOG_FILE_RANGES,
    ERROR_CATALOG_FILES,
    ERROR_DOMAIN_RANGES,
    KNOWN_ERROR_DOMAINS,
    REFERENCES_DIR,
    TRACEABILITY_FILE,
    _error_id_in_declared_ranges,
    _infer_domain_from_id,
    _parse_table_rows,
    _strip_bold,
)
from gpd.core.error_catalog import ErrorStore as CoreErrorStore
from gpd.core.error_catalog import get_error_store as _get_store
from gpd.core.observability import gpd_span
from gpd.mcp.servers import (
    configure_mcp_logging,
    read_only_tool_annotations,
    run_mcp_server,
    stable_mcp_error,
    stable_mcp_response,
    tighten_registered_tool_contracts,
)

logger = configure_mcp_logging("gpd-errors", ("gpd.core.error_catalog",))


class ErrorStore(CoreErrorStore):
    """Test seam binding the core error store to this module's catalog layout constants.

    Tests monkeypatch the module-level layout constants and build this subclass to
    exercise malformed-catalog paths; the runtime store served by the tools is
    ``gpd.core.error_catalog``'s shared default.
    """

    def __init__(self, references_dir: Path) -> None:
        super().__init__(
            references_dir,
            catalog_files=ERROR_CATALOG_FILES,
            catalog_file_ranges=ERROR_CATALOG_FILE_RANGES,
            traceability_file=TRACEABILITY_FILE,
        )


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
            return stable_mcp_response(error_catalog.get_error_class(_get_store(), error_id))
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
            description = error_catalog.normalize_computation_description(computation_desc)
            return stable_mcp_response(error_catalog.check_error_classes(_get_store(), description))
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
            return stable_mcp_response(error_catalog.get_detection_strategy(_get_store(), error_id))
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
            return stable_mcp_response(error_catalog.get_traceability(_get_store(), error_id))
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
            normalized_domain = error_catalog.normalize_error_domain(domain)
            return stable_mcp_response(error_catalog.list_error_classes(_get_store(), normalized_domain))
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
