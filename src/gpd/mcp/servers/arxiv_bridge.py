"""GPD-owned bridge for the optional arxiv_mcp_server integration."""

from __future__ import annotations

import argparse
import asyncio
import sys
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path

import mcp.types as types
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.server.lowlevel import NotificationOptions, Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server

from gpd.core.arxiv_source_download import (
    default_arxiv_source_storage_path,
    download_arxiv_source_archive,
)
from gpd.version import __version__ as GPD_VERSION

UPSTREAM_ARXIV_MODULE = "arxiv_mcp_server"
UPSTREAM_CORE_TOOL_NAMES = (
    "search_papers",
    "download_paper",
    "list_papers",
    "read_paper",
)
DOWNLOAD_SOURCE_TOOL_NAME = "download_source"
ADVERTISED_TOOL_NAMES = (*UPSTREAM_CORE_TOOL_NAMES, DOWNLOAD_SOURCE_TOOL_NAME)

_DOWNLOAD_SOURCE_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "paper_id": {
            "type": "string",
            "minLength": 1,
            "pattern": r"\S",
            "description": "arXiv paper identifier, for example 2401.12345 or hep-th/9901001.",
        },
        "overwrite": {
            "type": "boolean",
            "description": "Overwrite an existing archive for the same paper_id if it already exists locally.",
            "default": False,
        },
    },
    "required": ["paper_id"],
    "additionalProperties": False,
}

_DOWNLOAD_SOURCE_TOOL = types.Tool(
    name=DOWNLOAD_SOURCE_TOOL_NAME,
    description=(
        "Download the raw arXiv source archive for a paper and store it locally. "
        "Returns the saved path and metadata for the downloaded archive."
    ),
    inputSchema=_DOWNLOAD_SOURCE_SCHEMA,
)


@dataclass(frozen=True, slots=True)
class ArxivBridgeConfig:
    """Runtime configuration for the bridge."""

    storage_path: Path = field(default_factory=default_arxiv_source_storage_path)


def load_settings(*, storage_path: str | Path | None = None) -> ArxivBridgeConfig:
    """Load bridge settings for the upstream server and local source archive storage."""

    resolved = default_arxiv_source_storage_path() if storage_path is None else Path(storage_path)
    return ArxivBridgeConfig(storage_path=resolved.expanduser().resolve(strict=False))


class ArxivBridge:
    """Proxy around the upstream arxiv_mcp_server plus one local tool."""

    def __init__(self, config: ArxivBridgeConfig) -> None:
        self.config = config
        self._session: ClientSession | None = None

    @property
    def session(self) -> ClientSession:
        if self._session is None:
            raise RuntimeError("arXiv bridge session is not open")
        return self._session

    @asynccontextmanager
    async def open(self):
        server = StdioServerParameters(
            command=sys.executable,
            args=["-m", UPSTREAM_ARXIV_MODULE, "--storage-path", str(self.config.storage_path)],
        )
        async with stdio_client(server) as streams:
            async with ClientSession(*streams) as session:
                await session.initialize()
                self._session = session
                try:
                    yield self
                finally:
                    self._session = None

    async def list_tools(self, cursor: str | None = None) -> types.ListToolsResult:
        upstream = await self.session.list_tools(cursor)
        filtered = [tool for tool in upstream.tools if tool.name in UPSTREAM_CORE_TOOL_NAMES]
        if cursor in (None, ""):
            filtered.append(_DOWNLOAD_SOURCE_TOOL)
        return types.ListToolsResult(tools=filtered, nextCursor=upstream.nextCursor)

    async def call_tool(self, name: str, arguments: dict[str, object] | None) -> types.CallToolResult:
        if name not in ADVERTISED_TOOL_NAMES:
            return _tool_error(f"Tool {name!r} is not advertised by the GPD arXiv bridge")
        if name == DOWNLOAD_SOURCE_TOOL_NAME:
            return await self._call_download_source(arguments or {})
        return await self.session.call_tool(name, arguments or {})

    async def list_prompts(self, cursor: str | None = None) -> types.ListPromptsResult:
        return await self.session.list_prompts(cursor)

    async def get_prompt(self, name: str, arguments: dict[str, str] | None) -> types.GetPromptResult:
        return await self.session.get_prompt(name, arguments)

    async def _call_download_source(self, arguments: dict[str, object]) -> types.CallToolResult:
        extra_args = sorted(set(arguments) - set(_DOWNLOAD_SOURCE_SCHEMA["properties"]))
        if extra_args:
            return _tool_error(f"download_source got unsupported arguments: {', '.join(extra_args)}")

        paper_id = arguments.get("paper_id")
        if not isinstance(paper_id, str) or not paper_id.strip():
            return _tool_error("paper_id must be a non-empty string")

        overwrite = arguments.get("overwrite", False)
        if not isinstance(overwrite, bool):
            return _tool_error("overwrite must be a boolean")

        try:
            result = download_arxiv_source_archive(
                paper_id,
                storage_path=self.config.storage_path,
                overwrite=overwrite,
            )
        except Exception as exc:
            return _tool_error(str(exc))

        summary = (
            f"Downloaded source archive for {result.arxiv_id} to {result.path}"
            if not result.cached
            else f"Using existing source archive for {result.arxiv_id} at {result.path}"
        )
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=summary)],
            structuredContent={
                "schema_version": 1,
                "tool": DOWNLOAD_SOURCE_TOOL_NAME,
                "result": result.as_dict(),
            },
        )


def _tool_error(message: str) -> types.CallToolResult:
    """Return a stable MCP tool-error result."""

    return types.CallToolResult(
        isError=True,
        content=[types.TextContent(type="text", text=f"Error: {message}")],
        structuredContent={"schema_version": 1, "error": message},
    )


def build_server(config: ArxivBridgeConfig) -> tuple[Server, ArxivBridge]:
    """Build the local stdio MCP server."""

    bridge = ArxivBridge(config)

    @asynccontextmanager
    async def lifespan(_server: Server):
        async with bridge.open():
            yield bridge

    server = Server("gpd-arxiv", version=GPD_VERSION, lifespan=lifespan)

    @server.list_tools()
    async def _list_tools(request: types.ListToolsRequest) -> types.ListToolsResult:
        cursor = getattr(request.params, "cursor", None)
        return await bridge.list_tools(cursor)

    @server.call_tool()
    async def _call_tool(name: str, arguments: dict | None) -> types.CallToolResult:
        return await bridge.call_tool(name, arguments)

    @server.list_prompts()
    async def _list_prompts(request: types.ListPromptsRequest) -> types.ListPromptsResult:
        cursor = getattr(request.params, "cursor", None)
        return await bridge.list_prompts(cursor)

    @server.get_prompt()
    async def _get_prompt(name: str, arguments: dict[str, str] | None = None) -> types.GetPromptResult:
        return await bridge.get_prompt(name, arguments)

    return server, bridge


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="GPD arXiv MCP bridge")
    parser.add_argument("--transport", choices=["stdio"], default="stdio")
    parser.add_argument("--storage-path", default=None)
    return parser.parse_args()


async def _run() -> None:
    args = _parse_args()
    config = load_settings(storage_path=args.storage_path)
    server, _bridge = build_server(config)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="gpd-arxiv",
                server_version=GPD_VERSION,
                capabilities=server.get_capabilities(NotificationOptions(), {}),
            ),
        )


def main() -> None:
    """Console entry point for the GPD arXiv MCP bridge."""

    asyncio.run(_run())


__all__ = [
    "ADVERTISED_TOOL_NAMES",
    "ArxivBridge",
    "ArxivBridgeConfig",
    "DOWNLOAD_SOURCE_TOOL_NAME",
    "UPSTREAM_CORE_TOOL_NAMES",
    "build_server",
    "load_settings",
    "main",
]


if __name__ == "__main__":
    main()
