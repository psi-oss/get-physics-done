"""MCP servers for GPD — arxiv, conventions, verification, protocols, errors, patterns, state, skills."""

from __future__ import annotations

import argparse
import copy
import importlib
import logging
import os
import re
import signal
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Mapping
from pathlib import Path

from mcp.types import ToolAnnotations
from pydantic import ConfigDict, create_model
from pydantic import ValidationError as PydanticValidationError

from gpd.contracts import _format_pydantic_validation_errors
from gpd.core.frontmatter import FrontmatterParseError, extract_frontmatter

MCP_SCHEMA_VERSION = 1

ABSOLUTE_PROJECT_DIR_SCHEMA = {
    "type": "string",
    "minLength": 1,
    "pattern": r"^(?:[A-Za-z]:[\\/](?:.*)?|\\\\[^\\/]+[\\/][^\\/]+(?:[\\/].*)?)" if os.name == "nt" else r"^/",
    "description": "Absolute filesystem path to the project root directory on the current host OS.",
}


def mcp_tool_annotations(
    *,
    read_only: bool,
    destructive: bool,
    idempotent: bool,
    open_world: bool = False,
) -> ToolAnnotations:
    """Return MCP tool annotations with one shared naming convention."""

    return ToolAnnotations(
        readOnlyHint=read_only,
        destructiveHint=destructive,
        idempotentHint=idempotent,
        openWorldHint=open_world,
    )


def read_only_tool_annotations(*, open_world: bool = False) -> ToolAnnotations:
    """Return annotations for deterministic read-only built-in MCP tools."""

    return mcp_tool_annotations(
        read_only=True,
        destructive=False,
        idempotent=True,
        open_world=open_world,
    )


def mutating_tool_annotations(
    *,
    destructive: bool,
    idempotent: bool,
    open_world: bool = False,
) -> ToolAnnotations:
    """Return annotations for MCP tools that may change local or external state."""

    return mcp_tool_annotations(
        read_only=False,
        destructive=destructive,
        idempotent=idempotent,
        open_world=open_world,
    )


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
        payload_schema_version = payload.get("schema_version")
        if payload_schema_version is not None and payload_schema_version != MCP_SCHEMA_VERSION:
            response["payload_schema_version"] = payload_schema_version
    if error is not None:
        response["error"] = str(error)
    response["schema_version"] = MCP_SCHEMA_VERSION
    return response


def stable_mcp_error(error: object) -> StableMCPEnvelope:
    """Return a stable MCP error envelope."""

    if isinstance(error, PydanticValidationError):
        error = "; ".join(_format_pydantic_validation_errors(error))
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
    candidate = re.sub(r"^(?:[ \t]*\r?\n)+(?=---[ \t]*\r?\n)", "", text.lstrip("\ufeff"), count=1)
    if re.match(r"^---[ \t]*(?:\r?\n|$)", candidate) and not re.match(
        r"^---[ \t]*\r?\n(?:[\s\S]*?\r?\n)?---[ \t]*(?:\r?\n|$)",
        candidate,
    ):
        return {}, text, "Unclosed frontmatter block"
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


_LIFECYCLE_POLL_SECONDS = 5.0


def _client_pid_dir() -> Path | None:
    """Return a private per-user directory for client-lifetime pid files, or ``None`` when unsafe."""
    base = Path(tempfile.gettempdir()) / f"gpd-mcp-{os.getuid()}"
    try:
        base.mkdir(mode=0o700, exist_ok=True)
        if base.is_symlink() or base.stat().st_uid != os.getuid():
            return None
    except OSError:
        return None
    return base


def _word_names_entry_point(word: str, invocation_token: str) -> bool:
    """Return whether one command-line word names ``invocation_token`` exactly.

    Exact comparison against the word's path basename and its dot-split halves
    covers console scripts (``.../gpd-mcp-state``), dotted modules
    (``gpd.mcp.servers.state_server``), and script files (``state_server.py``)
    without admitting prefix collisions such as ``state_server_extra``.
    """
    tail = word.rsplit("/", 1)[-1]
    head, _, last = tail.rpartition(".")
    return invocation_token in (tail, head, last)


def _is_gpd_server_spawned_by(pid: int, parent_pid: int, invocation_token: str) -> bool:
    """Return whether ``pid`` is a live GPD MCP server whose parent is ``parent_pid``.

    ``invocation_token`` (the replacement instance's own entry-point name) must
    exactly name a word of the candidate's command line so that a recycled pid
    pointing at a *different* GPD server under the same client — including one
    whose name merely extends ours — is never treated as ours.
    """
    try:
        listing = subprocess.run(
            ["ps", "-o", "ppid=,command=", "-p", str(pid)],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    if listing.returncode != 0:
        return False
    reported = listing.stdout.strip().split(None, 1)
    if len(reported) != 2:
        return False
    return (
        reported[0] == str(parent_pid)
        and "gpd.mcp.servers" in reported[1]
        and any(_word_names_entry_point(word, invocation_token) for word in reported[1].split())
    )


def _terminate_superseded_instance(
    server_name: str,
    parent_pid: int,
    pid_dir: Path,
    invocation_token: str,
) -> None:
    """SIGTERM the previous instance of ``server_name`` that the same client spawned and abandoned.

    MCP clients that restart their stdio servers (startup-timeout retries,
    reconnects) can leave the previous instance running with its pipes held
    open, so it never sees EOF and outlives every session. Each instance
    records its pid in a file keyed by (server, client pid); the next instance
    verifies the recorded process is still that client's instance of the same
    server before terminating it. Stale files from exited instances fail
    verification and are simply overwritten. The whole read-verify-kill-record
    sequence holds a per-key lock so concurrent replacements cannot interleave
    and leave a live instance unrecorded.
    """
    import fcntl  # POSIX-only, matching the guard's platform gate

    pid_file = pid_dir / f"{server_name}-client{parent_pid}.pid"
    try:
        lock_handle = open(pid_dir / f"{server_name}-client{parent_pid}.lock", "w")
    except OSError:
        return
    try:
        try:
            fcntl.flock(lock_handle, fcntl.LOCK_EX)
        except OSError:
            # Locking is unavailable (e.g. NFS-backed tmp); skip the takeover
            # rather than crash startup — the reparent watchdog still guards.
            return
        try:
            previous_pid = int(pid_file.read_text().strip())
        except (OSError, ValueError):
            previous_pid = None
        if (
            previous_pid is not None
            and previous_pid != os.getpid()
            and _is_gpd_server_spawned_by(previous_pid, parent_pid, invocation_token)
        ):
            try:
                os.kill(previous_pid, signal.SIGTERM)
            except OSError:
                pass
        try:
            staging = pid_file.parent / f"{pid_file.name}.{os.getpid()}.tmp"
            staging.write_text(str(os.getpid()))
            staging.replace(pid_file)
        except OSError:
            pass
    finally:
        lock_handle.close()


def _exit_when_reparented(initial_parent_pid: int, poll_seconds: float) -> None:
    """Block until the spawning client process dies, then force-exit this process.

    Covers clients that die without our stdin ever reaching EOF (fds leaked
    to other processes, transport regressions). An ``initial_parent_pid`` of 1
    means the client already died during our startup — exit immediately rather
    than guard init/launchd, which never dies. ``os._exit`` is deliberate:
    the client is gone, so graceful shutdown paths that touch the dead
    transport could block forever.
    """
    while initial_parent_pid != 1 and os.getppid() == initial_parent_pid:
        time.sleep(poll_seconds)
    os._exit(0)


def _install_stdio_lifecycle_guard(server_name: str) -> None:
    """Bind this stdio server's lifetime to the client process that spawned it (POSIX only)."""
    if os.name != "posix":
        return
    parent_pid = os.getppid()
    pid_dir = _client_pid_dir()
    # The watchdog must be running before the takeover: the takeover blocks on
    # a per-key lock, and a starter waiting behind a hung holder still needs
    # to exit when its own client dies.
    threading.Thread(
        target=_exit_when_reparented,
        args=(parent_pid, _LIFECYCLE_POLL_SECONDS),
        daemon=True,
        name="gpd-mcp-lifecycle-guard",
    ).start()
    if parent_pid != 1 and pid_dir is not None:
        # The entry-point name identifies this server type in a predecessor's
        # command line for both `python -m gpd.mcp.servers.X` and console-
        # script invocations, since the same client uses the same registration.
        _terminate_superseded_instance(server_name, parent_pid, pid_dir, Path(sys.argv[0]).stem)


def run_mcp_server(mcp: object, description: str) -> None:
    """Run an MCP server with standard CLI arguments (transport, host, port).

    Every MCP server in this package uses the same entry-point pattern.
    This function eliminates that boilerplate. For the stdio transport it
    also binds the server's lifetime to the spawning client so abandoned
    instances cannot accumulate (see ``_install_stdio_lifecycle_guard``).

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
    if args.transport == "stdio":
        _install_stdio_lifecycle_guard(getattr(mcp, "name", None) or Path(sys.argv[0]).stem)
    mcp.run(transport=args.transport)  # type: ignore[union-attr]


def published_tool_input_schema(tool: object) -> dict[str, object] | None:
    """Return the currently published input schema for a FastMCP tool-like object."""

    for attribute in ("inputSchema", "parameters"):
        schema = getattr(tool, attribute, None)
        if isinstance(schema, dict):
            return schema
    return None


def _set_tool_attribute(tool: object, attribute: str, value: object) -> None:
    try:
        setattr(tool, attribute, value)
    except (AttributeError, TypeError):
        object.__setattr__(tool, attribute, value)


def set_published_tool_input_schema(tool: object, schema: dict[str, object]) -> None:
    """Write a published input schema onto both public and private FastMCP surfaces."""

    if hasattr(tool, "inputSchema"):
        _set_tool_attribute(tool, "inputSchema", copy.deepcopy(schema))
    if hasattr(tool, "parameters"):
        _set_tool_attribute(tool, "parameters", copy.deepcopy(schema))


def set_registered_and_published_tool_input_schema(mcp: object, tool: object, schema: dict[str, object]) -> None:
    """Write one schema onto the public tool descriptor and its registered counterpart."""

    set_published_tool_input_schema(tool, schema)
    tool_name = getattr(tool, "name", None)
    if not isinstance(tool_name, str):
        return
    tool_manager = getattr(mcp, "_tool_manager", None)
    if tool_manager is None:
        return
    try:
        registered_tools = tool_manager.list_tools()
    except AttributeError:
        return
    for registered_tool in registered_tools:
        if getattr(registered_tool, "name", None) == tool_name:
            set_published_tool_input_schema(registered_tool, schema)


def refresh_string_enum_property_schema(
    schema: dict[str, object],
    *,
    property_name: str,
    enum_values: list[str],
) -> dict[str, object]:
    """Refresh one string enum property regardless of anyOf branch order."""

    refreshed = copy.deepcopy(schema)
    properties = refreshed.get("properties") if isinstance(refreshed, dict) else None
    if not isinstance(properties, dict):
        return refreshed
    property_schema = properties.get(property_name)
    if not isinstance(property_schema, dict):
        return refreshed

    enum_schema: dict[str, object] | None = None
    any_of = property_schema.get("anyOf")
    if isinstance(any_of, list):
        for branch in any_of:
            if not isinstance(branch, dict):
                continue
            if branch.get("type") == "string" or "enum" in branch:
                enum_schema = branch
                break
    elif property_schema.get("type") == "string" or "enum" in property_schema:
        enum_schema = property_schema

    if enum_schema is None:
        return refreshed

    enum_schema["enum"] = list(enum_values)
    return refreshed


def tighten_registered_tool_contracts(mcp: object) -> None:
    """Publish strict top-level tool schemas and stable validation envelopes."""

    strict_schemas_by_name: dict[str, dict[str, object]] = {}

    def _build_strict_call(original_call, allowed_keys):
        async def _strict_call_fn_with_arg_validation(
            fn, fn_is_async, arguments_to_validate, arguments_to_pass_directly
        ):
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
        strict_schema = strict_model.model_json_schema(by_alias=True)
        strict_schemas_by_name[str(tool.name)] = strict_schema
        set_published_tool_input_schema(tool, strict_schema)
        allowed_keys = {
            key
            for field_name, field_info in arg_model.model_fields.items()
            for key in (field_name, field_info.alias)
            if key is not None
        }
        original_call = tool.fn_metadata.call_fn_with_arg_validation
        object.__setattr__(
            tool.fn_metadata, "call_fn_with_arg_validation", _build_strict_call(original_call, allowed_keys)
        )

    original_list_tools = mcp.list_tools

    async def _list_tools_with_strict_schemas():
        tools = await original_list_tools()
        for tool in tools:
            strict_schema = strict_schemas_by_name.get(str(getattr(tool, "name", "")))
            if strict_schema is None:
                continue
            set_published_tool_input_schema(tool, strict_schema)
        return tools

    mcp.list_tools = _list_tools_with_strict_schemas


__all__ = [
    "ABSOLUTE_PROJECT_DIR_SCHEMA",
    "MCP_SCHEMA_VERSION",
    "StableMCPEnvelope",
    "arxiv_bridge",
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
    "published_tool_input_schema",
    "set_published_tool_input_schema",
    "stable_mcp_error",
    "stable_mcp_response",
    "tighten_registered_tool_contracts",
    "verification_server",
]

_SERVER_MODULE_NAMES = {
    "arxiv_bridge",
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
