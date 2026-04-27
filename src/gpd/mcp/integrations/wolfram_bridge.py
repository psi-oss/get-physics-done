"""GPD-owned stdio bridge for the Wolfram remote MCP service."""

from __future__ import annotations

import asyncio
import base64
import os
from collections.abc import Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

import mcp.types as types
from mcp import ClientSession
from mcp.client.sse import sse_client
from mcp.server.lowlevel import NotificationOptions, Server
from mcp.server.lowlevel.helper_types import ReadResourceContents
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server

from gpd.mcp import managed_integrations as _managed_integrations
from gpd.version import __version__ as GPD_VERSION

WOLFRAM_MANAGED_INTEGRATION = _managed_integrations.WOLFRAM_MANAGED_INTEGRATION
WOLFRAM_MCP_API_KEY_ENV_VAR = _managed_integrations.WOLFRAM_MCP_API_KEY_ENV_VAR
WOLFRAM_MCP_DEFAULT_ENDPOINT = _managed_integrations.WOLFRAM_MCP_DEFAULT_ENDPOINT
WOLFRAM_MCP_ENDPOINT_ENV_VAR = _managed_integrations.WOLFRAM_MCP_ENDPOINT_ENV_VAR

DEFAULT_WOLFRAM_MCP_ENDPOINT = WOLFRAM_MCP_DEFAULT_ENDPOINT
GPD_WOLFRAM_MCP_API_KEY_ENV = WOLFRAM_MCP_API_KEY_ENV_VAR

_CONNECT_TIMEOUT_SECONDS = 10.0
_READ_TIMEOUT_SECONDS = 300.0


def resolve_endpoint(env: Mapping[str, str] | None = None) -> str:
    """Return the Wolfram MCP endpoint URL, defaulting to the official service."""
    source = os.environ if env is None else env
    return WOLFRAM_MANAGED_INTEGRATION.resolved_endpoint(source)


def resolve_api_key(env: Mapping[str, str] | None = None) -> str:
    """Return the bearer token for the Wolfram MCP service.

    The canonical env var is the only supported auth source.
    """
    source = os.environ if env is None else env
    return WOLFRAM_MANAGED_INTEGRATION.resolve_api_key(source)


def build_auth_headers(api_key: str) -> dict[str, str]:
    """Build the bearer-token headers used for the remote MCP connection."""
    return {"Authorization": f"Bearer {api_key}"}


@dataclass(frozen=True, slots=True)
class WolframBridgeConfig:
    """Runtime configuration for the Wolfram bridge."""

    api_key: str = field(repr=False)
    endpoint: str = DEFAULT_WOLFRAM_MCP_ENDPOINT


def load_settings(env: Mapping[str, str] | None = None) -> WolframBridgeConfig:
    """Load bridge settings from the environment without persisting secrets."""
    source = os.environ if env is None else env
    return WolframBridgeConfig(endpoint=resolve_endpoint(source), api_key=resolve_api_key(source))


class WolframBridge:
    """Thin proxy around the remote Wolfram MCP service."""

    def __init__(self, config: WolframBridgeConfig) -> None:
        self.config = config
        self._session: ClientSession | None = None

    @property
    def session(self) -> ClientSession:
        if self._session is None:
            raise RuntimeError("Wolfram bridge session is not open")
        return self._session

    @asynccontextmanager
    async def open(self):
        headers = build_auth_headers(self.config.api_key)
        async with sse_client(
            self.config.endpoint,
            headers=headers,
            timeout=_CONNECT_TIMEOUT_SECONDS,
            sse_read_timeout=_READ_TIMEOUT_SECONDS,
        ) as streams:
            async with ClientSession(*streams) as session:
                await session.initialize()
                self._session = session
                try:
                    yield self
                finally:
                    self._session = None

    async def list_tools(self, cursor: str | None = None) -> types.ListToolsResult:
        return await self.session.list_tools(cursor)

    async def call_tool(self, name: str, arguments: dict[str, object] | None) -> types.CallToolResult:
        return await self.session.call_tool(name, arguments)

    async def list_resources(self, cursor: str | None = None) -> types.ListResourcesResult:
        return await self.session.list_resources(cursor)

    async def read_resource(self, uri: str) -> types.ReadResourceResult:
        return await self.session.read_resource(uri)

    async def list_prompts(self, cursor: str | None = None) -> types.ListPromptsResult:
        return await self.session.list_prompts(cursor)

    async def get_prompt(self, name: str, arguments: dict[str, str] | None) -> types.GetPromptResult:
        return await self.session.get_prompt(name, arguments)

    async def list_resource_templates(self, cursor: str | None = None) -> types.ListResourceTemplatesResult:
        return await self.session.list_resource_templates(cursor)


def _as_lowlevel_resource_content(content: object) -> ReadResourceContents:
    """Convert remote MCP resource content into the low-level server helper shape."""
    mime_type = getattr(content, "mimeType", None)
    meta = getattr(content, "meta", None)
    if isinstance(content, types.TextResourceContents):
        return ReadResourceContents(content=content.text, mime_type=mime_type, meta=meta)
    if isinstance(content, types.BlobResourceContents):
        return ReadResourceContents(content=base64.b64decode(content.blob), mime_type=mime_type, meta=meta)
    if hasattr(content, "text"):
        return ReadResourceContents(content=str(content.text), mime_type=mime_type, meta=meta)
    if hasattr(content, "blob"):
        return ReadResourceContents(content=base64.b64decode(str(content.blob)), mime_type=mime_type, meta=meta)
    raise RuntimeError(f"Unsupported Wolfram resource content type: {type(content).__name__}")


def build_server(config: WolframBridgeConfig) -> tuple[Server, WolframBridge]:
    """Build the local stdio MCP server that proxies the remote Wolfram service."""
    bridge = WolframBridge(config)

    @asynccontextmanager
    async def lifespan(_server: Server):
        async with bridge.open():
            yield bridge

    server = Server("gpd-wolfram", version=GPD_VERSION, lifespan=lifespan)

    @server.list_tools()
    async def _list_tools(request: types.ListToolsRequest) -> types.ListToolsResult:
        cursor = getattr(request.params, "cursor", None)
        return await bridge.list_tools(cursor)

    @server.call_tool()
    async def _call_tool(name: str, arguments: dict | None) -> types.CallToolResult:
        return await bridge.call_tool(name, arguments)

    @server.list_resources()
    async def _list_resources(request: types.ListResourcesRequest) -> types.ListResourcesResult:
        cursor = getattr(request.params, "cursor", None)
        return await bridge.list_resources(cursor)

    @server.read_resource()
    async def _read_resource(uri: str):
        result = await bridge.read_resource(uri)
        return [_as_lowlevel_resource_content(content) for content in result.contents]

    @server.list_prompts()
    async def _list_prompts(request: types.ListPromptsRequest) -> types.ListPromptsResult:
        cursor = getattr(request.params, "cursor", None)
        return await bridge.list_prompts(cursor)

    @server.get_prompt()
    async def _get_prompt(name: str, arguments: dict[str, str] | None) -> types.GetPromptResult:
        return await bridge.get_prompt(name, arguments)

    @server.list_resource_templates()
    async def _list_resource_templates() -> list[types.ResourceTemplate]:
        return (await bridge.list_resource_templates()).resourceTemplates

    return server, bridge


async def _run() -> None:
    config = load_settings()
    server, _bridge = build_server(config)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="gpd-wolfram",
                server_version=GPD_VERSION,
                capabilities=server.get_capabilities(NotificationOptions(), {}),
            ),
        )


def main() -> None:
    """Console entry point for the Wolfram MCP bridge."""
    try:
        asyncio.run(_run())
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc


__all__ = [
    "DEFAULT_WOLFRAM_MCP_ENDPOINT",
    "GPD_WOLFRAM_MCP_API_KEY_ENV",
    "WolframBridge",
    "WolframBridgeConfig",
    "build_auth_headers",
    "build_server",
    "load_settings",
    "main",
    "resolve_api_key",
    "resolve_endpoint",
]
