"""Schema-versioned response envelopes shared by GPD tool transports.

The MCP servers and the ``gpd`` CLI build the same envelope dictionaries for the
same inputs — the MCP tools return them as tool results, the CLI renders them as
JSON under ``--raw`` — so the envelope shape and the absolute-project-dir
contract live here rather than inside any one transport. ``gpd.mcp.servers``
re-exports these names so existing MCP imports keep working.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from pydantic import ValidationError as PydanticValidationError

from gpd.contracts import _format_pydantic_validation_errors

MCP_SCHEMA_VERSION = 1


class StableMCPEnvelope(dict[str, object]):
    """Schema-versioned envelope for all tool responses."""


def stable_mcp_response(
    payload: Mapping[str, object] | None = None,
    *,
    error: object | None = None,
) -> StableMCPEnvelope:
    """Return a stable response envelope without nesting the payload."""

    response = StableMCPEnvelope()
    if payload is not None:
        response.update(payload)
        payload_schema_version = payload.get("schema_version")
        if payload_schema_version is not None and payload_schema_version != MCP_SCHEMA_VERSION:
            response["payload_schema_version"] = payload_schema_version
    if error is not None:
        response["error"] = str(error)
    response["schema_version"] = MCP_SCHEMA_VERSION
    return response


def stable_mcp_error(error: object) -> StableMCPEnvelope:
    """Return a stable error envelope."""

    if isinstance(error, PydanticValidationError):
        error = "; ".join(_format_pydantic_validation_errors(error))
    return stable_mcp_response(error=error)


def resolve_absolute_project_dir(project_dir: str) -> Path | None:
    """Return an absolute project root path or ``None`` when the contract is violated."""

    cwd = Path(project_dir)
    if not cwd.is_absolute():
        return None
    return cwd
