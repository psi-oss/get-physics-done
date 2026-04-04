"""MCP servers for GPD — conventions, verification, protocols, errors, patterns, state, skills."""

from __future__ import annotations

import argparse
import importlib
import logging
import os
import sys
from collections.abc import Mapping
from pathlib import Path

from pydantic import ConfigDict, create_model
from pydantic import ValidationError as PydanticValidationError

from gpd.core.frontmatter import FrontmatterParseError, extract_frontmatter

MCP_SCHEMA_VERSION = 1

ABSOLUTE_PROJECT_DIR_SCHEMA = {
    "type": "string",
    "minLength": 1,
    "pattern": r"^(?:[A-Za-z]:[\\/](?:.*)?|\\\\[^\\/]+[\\/][^\\/]+(?:[\\/].*)?)" if os.name == "nt" else r"^/",
    "description": "Absolute filesystem path to the project root directory on the current host OS.",
}


class StableMCPEnvelope(dict[str, object]):
    """Schema-versioned MCP envelope for all server responses."""


class _DynamicStderrHandler(logging.StreamHandler):
    """Stream handler that always emits to the current ``sys.stderr``."""

    def emit(self, record: logging.LogRecord) -> None:
        self.setStream(sys.stderr)
        super().emit(record)


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


def configure_mcp_logging(logger_name: str) -> logging.Logger:
    """Configure a built-in MCP server logger from the advertised LOG_LEVEL env var."""

    raw_level = os.environ.get("LOG_LEVEL", "WARNING")
    level_name = raw_level.strip().upper() if isinstance(raw_level, str) else "WARNING"
    level = getattr(logging, level_name, None)
    if not isinstance(level, int):
        try:
            level = int(str(raw_level).strip())
        except (TypeError, ValueError):
            level = logging.WARNING

    logger = logging.getLogger(logger_name)
    logger.setLevel(level)
    logger.handlers.clear()
    handler = _DynamicStderrHandler(sys.stderr)
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter("%(name)s %(levelname)s: %(message)s"))
    logger.addHandler(handler)
    logger.propagate = False
    return logger


def resolve_absolute_project_dir(project_dir: str) -> Path | None:
    """Return an absolute project root path or ``None`` when the contract is violated."""

    cwd = Path(project_dir)
    if not cwd.is_absolute():
        return None
    return cwd


def parse_frontmatter_with_error(text: str) -> tuple[dict[str, object], str, str | None]:
    """Split YAML frontmatter from markdown body and surface parse failures."""
    try:
        meta, body = extract_frontmatter(text)
    except FrontmatterParseError as exc:
        return {}, text, str(exc)
    return meta, body, None


def parse_frontmatter_safe(text: str) -> tuple[dict[str, object], str]:
    """Split YAML frontmatter from markdown body, returning ({}, text) on parse error.

    Shared helper for MCP servers that bulk-load markdown files and need
    graceful handling of malformed YAML.
    """
    meta, body, _error = parse_frontmatter_with_error(text)
    return meta, body


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


def tighten_registered_tool_contracts(mcp: object) -> None:
    """Publish strict top-level tool schemas and stable validation envelopes."""

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


__all__ = [
    "ABSOLUTE_PROJECT_DIR_SCHEMA",
    "MCP_SCHEMA_VERSION",
    "StableMCPEnvelope",
    "conventions_server",
    "configure_mcp_logging",
    "errors_mcp",
    "parse_frontmatter_safe",
    "parse_frontmatter_with_error",
    "patterns_server",
    "protocols_server",
    "resolve_absolute_project_dir",
    "run_mcp_server",
    "skills_server",
    "state_server",
    "stable_mcp_error",
    "stable_mcp_response",
    "tighten_registered_tool_contracts",
    "verification_server",
]

_SERVER_MODULE_NAMES = {
    "conventions_server",
    "errors_mcp",
    "patterns_server",
    "protocols_server",
    "skills_server",
    "state_server",
    "verification_server",
}


def __getattr__(name: str) -> object:
    if name in _SERVER_MODULE_NAMES:
        module = importlib.import_module(f"{__name__}.{name}")
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
