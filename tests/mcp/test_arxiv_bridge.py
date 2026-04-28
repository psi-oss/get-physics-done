from __future__ import annotations

import runpy
import warnings
from contextlib import asynccontextmanager

import pytest


def test_load_settings_uses_current_home_for_default_storage_root(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    from gpd.mcp.servers.arxiv_bridge import ArxivBridgeConfig, load_settings

    home = tmp_path / "home"
    monkeypatch.setattr("gpd.core.arxiv_source_download.Path.home", lambda: home)

    config = load_settings()
    dataclass_default = ArxivBridgeConfig()

    expected = (home / ".arxiv-mcp-server" / "papers").resolve()
    assert config.storage_path == expected
    assert dataclass_default.storage_path == home / ".arxiv-mcp-server" / "papers"


@pytest.mark.asyncio
async def test_bridge_open_spawns_upstream_server_with_storage_path(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    from gpd.mcp.servers import arxiv_bridge as module
    from gpd.mcp.servers.arxiv_bridge import ArxivBridge, ArxivBridgeConfig

    observed: dict[str, object] = {}

    class FakeSession:
        async def __aenter__(self):
            observed["session_entered"] = True
            return self

        async def __aexit__(self, exc_type, exc, tb):
            observed["session_exited"] = True

        async def initialize(self):
            observed["initialized"] = True

    @asynccontextmanager
    async def fake_stdio_client(server_params, errlog=None):
        observed["command"] = server_params.command
        observed["args"] = list(server_params.args)
        yield ("read-stream", "write-stream")

    monkeypatch.setattr(module, "stdio_client", fake_stdio_client)
    monkeypatch.setattr(module, "ClientSession", lambda read_stream, write_stream: FakeSession())

    bridge = ArxivBridge(ArxivBridgeConfig(storage_path=tmp_path.resolve()))

    async with bridge.open() as opened:
        assert opened is bridge
        assert bridge._session is not None

    assert observed["command"] == module.sys.executable
    assert observed["args"] == ["-m", "arxiv_mcp_server", "--storage-path", str(tmp_path.resolve())]
    assert observed["initialized"] is True
    assert observed["session_entered"] is True
    assert observed["session_exited"] is True


@pytest.mark.asyncio
async def test_bridge_advertises_live_upstream_tools_and_adds_local_download_source() -> None:
    from mcp.types import ListToolsResult, Tool

    from gpd.mcp.servers.arxiv_bridge import ArxivBridge, ArxivBridgeConfig

    class FakeSession:
        async def list_tools(self, cursor=None):
            return ListToolsResult(
                tools=[
                    Tool(name="search_papers", inputSchema={"type": "object"}),
                    Tool(name="download_paper", inputSchema={"type": "object"}),
                    Tool(name="read_paper", inputSchema={"type": "object"}),
                    Tool(name="semantic_search", inputSchema={"type": "object"}),
                    Tool(name="download_source", inputSchema={"type": "object", "properties": {"upstream": {}}}),
                ],
                nextCursor="next-page",
            )

    bridge = ArxivBridge(ArxivBridgeConfig())
    bridge._session = FakeSession()  # type: ignore[assignment]
    try:
        result = await bridge.list_tools()
    finally:
        bridge._session = None

    assert [tool.name for tool in result.tools] == [
        "search_papers",
        "download_paper",
        "read_paper",
        "semantic_search",
        "download_source",
    ]
    assert result.tools[-1].inputSchema["properties"]["paper_id"]["description"].startswith("arXiv paper identifier")
    assert result.tools[-1].annotations is not None
    assert result.tools[-1].annotations.readOnlyHint is False
    assert result.tools[-1].annotations.destructiveHint is True
    assert result.tools[-1].annotations.idempotentHint is False
    assert result.tools[-1].annotations.openWorldHint is True
    assert result.nextCursor == "next-page"


@pytest.mark.asyncio
async def test_download_source_schema_rejects_whitespace_only_paper_id() -> None:
    from jsonschema import Draft202012Validator
    from mcp.types import ListToolsResult, Tool

    from gpd.mcp.servers.arxiv_bridge import ArxivBridge, ArxivBridgeConfig

    class FakeSession:
        async def list_tools(self, cursor=None):
            return ListToolsResult(tools=[Tool(name="search_papers", inputSchema={"type": "object"})])

    bridge = ArxivBridge(ArxivBridgeConfig())
    bridge._session = FakeSession()  # type: ignore[assignment]
    try:
        result = await bridge.list_tools()
    finally:
        bridge._session = None

    schema = next(tool.inputSchema for tool in result.tools if tool.name == "download_source")
    paper_id = schema["properties"]["paper_id"]
    validator = Draft202012Validator(schema)

    assert paper_id["minLength"] == 1
    assert paper_id["pattern"] == r"\S"
    assert not list(validator.iter_errors({"paper_id": "2401.12345"}))
    assert list(validator.iter_errors({"paper_id": "   "}))


@pytest.mark.asyncio
async def test_bridge_preserves_upstream_pagination_and_only_adds_download_source_on_first_page() -> None:
    from mcp.types import ListToolsResult, Tool

    from gpd.mcp.servers.arxiv_bridge import ArxivBridge, ArxivBridgeConfig

    class FakeSession:
        async def list_tools(self, cursor=None):
            return ListToolsResult(
                tools=[Tool(name="list_papers", inputSchema={"type": "object"})],
                nextCursor="cursor-2" if cursor is None else None,
            )

    bridge = ArxivBridge(ArxivBridgeConfig())
    bridge._session = FakeSession()  # type: ignore[assignment]
    try:
        first = await bridge.list_tools()
        second = await bridge.list_tools("cursor-2")
    finally:
        bridge._session = None

    assert [tool.name for tool in first.tools] == ["list_papers", "download_source"]
    assert first.nextCursor == "cursor-2"
    assert [tool.name for tool in second.tools] == ["list_papers"]
    assert second.nextCursor is None


@pytest.mark.asyncio
async def test_first_page_refresh_resets_incomplete_upstream_tool_cache() -> None:
    from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool

    from gpd.mcp.servers.arxiv_bridge import ArxivBridge, ArxivBridgeConfig

    class FakeSession:
        def __init__(self) -> None:
            self.refreshed = False
            self.calls: list[str | None] = []

        async def list_tools(self, cursor=None):
            self.calls.append(cursor)
            if not self.refreshed:
                return ListToolsResult(tools=[Tool(name="search_papers", inputSchema={"type": "object"})])
            if cursor is None:
                return ListToolsResult(
                    tools=[Tool(name="search_papers", inputSchema={"type": "object"})],
                    nextCursor="page-2",
                )
            return ListToolsResult(tools=[Tool(name="semantic_search", inputSchema={"type": "object"})])

        async def call_tool(self, name, arguments):
            return CallToolResult(
                content=[TextContent(type="text", text=f"{name}:{arguments['query']}")],
                structuredContent={"tool": name, "arguments": arguments},
            )

    fake_session = FakeSession()
    bridge = ArxivBridge(ArxivBridgeConfig())
    bridge._session = fake_session  # type: ignore[assignment]
    try:
        await bridge.list_tools()
        assert bridge._upstream_tool_names_complete is True

        fake_session.refreshed = True
        await bridge.list_tools()
        assert bridge._upstream_tool_names_complete is False

        result = await bridge.call_tool("semantic_search", {"query": "qft"})
    finally:
        bridge._session = None

    assert fake_session.calls == [None, None, None, "page-2"]
    assert result.isError is not True
    assert result.structuredContent == {"tool": "semantic_search", "arguments": {"query": "qft"}}


@pytest.mark.asyncio
async def test_bridge_proxies_upstream_tool_calls_without_rewriting() -> None:
    from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool

    from gpd.mcp.servers.arxiv_bridge import ArxivBridge, ArxivBridgeConfig

    class FakeSession:
        async def list_tools(self, cursor=None):
            return ListToolsResult(tools=[Tool(name="download_paper", inputSchema={"type": "object"})])

        async def call_tool(self, name, arguments):
            return CallToolResult(
                content=[TextContent(type="text", text=f"{name}:{arguments['paper_id']}")],
                structuredContent={"tool": name, "arguments": arguments},
            )

    bridge = ArxivBridge(ArxivBridgeConfig())
    bridge._session = FakeSession()  # type: ignore[assignment]
    try:
        result = await bridge.call_tool("download_paper", {"paper_id": "2401.12345"})
    finally:
        bridge._session = None

    assert result.structuredContent == {"tool": "download_paper", "arguments": {"paper_id": "2401.12345"}}


@pytest.mark.asyncio
async def test_bridge_forwards_live_upstream_tool_not_in_static_fallback() -> None:
    from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool

    from gpd.mcp.servers.arxiv_bridge import ArxivBridge, ArxivBridgeConfig

    class FakeSession:
        async def list_tools(self, cursor=None):
            return ListToolsResult(tools=[Tool(name="semantic_search", inputSchema={"type": "object"})])

        async def call_tool(self, name, arguments):
            return CallToolResult(
                content=[TextContent(type="text", text=f"{name}:{arguments['query']}")],
                structuredContent={"tool": name, "arguments": arguments},
            )

    bridge = ArxivBridge(ArxivBridgeConfig())
    bridge._session = FakeSession()  # type: ignore[assignment]
    try:
        result = await bridge.call_tool("semantic_search", {"query": "qft"})
    finally:
        bridge._session = None

    assert result.structuredContent == {"tool": "semantic_search", "arguments": {"query": "qft"}}


@pytest.mark.asyncio
async def test_bridge_rejects_removed_static_upstream_tool_calls() -> None:
    from mcp.types import ListToolsResult, Tool

    from gpd.mcp.servers.arxiv_bridge import ArxivBridge, ArxivBridgeConfig

    class FakeSession:
        called = False

        async def list_tools(self, cursor=None):
            return ListToolsResult(tools=[Tool(name="search_papers", inputSchema={"type": "object"})])

        async def call_tool(self, name, arguments):
            self.called = True
            raise AssertionError("removed static tools must not be proxied")

    fake_session = FakeSession()
    bridge = ArxivBridge(ArxivBridgeConfig())
    bridge._session = fake_session  # type: ignore[assignment]
    try:
        result = await bridge.call_tool("download_paper", {"paper_id": "2401.12345"})
    finally:
        bridge._session = None

    assert result.isError is True
    assert fake_session.called is False
    assert result.structuredContent == {
        "schema_version": 1,
        "error": "Tool 'download_paper' is not advertised by the GPD arXiv bridge",
    }


@pytest.mark.asyncio
async def test_bridge_download_source_returns_structured_metadata(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    from gpd.mcp.servers import arxiv_bridge as module
    from gpd.mcp.servers.arxiv_bridge import ArxivBridge, ArxivBridgeConfig

    bridge = ArxivBridge(ArxivBridgeConfig(storage_path=tmp_path.resolve()))

    class FakeDownload:
        arxiv_id = "2401.12345"
        path = tmp_path / "sources" / "2401.12345-source.zip"
        cached = False

        def as_dict(self):
            return {
                "arxiv_id": self.arxiv_id,
                "path": str(self.path),
                "filename": self.path.name,
                "size_bytes": 123,
                "content_type": "application/zip",
                "download_url": "https://arxiv.org/e-print/2401.12345",
                "cached": self.cached,
            }

    monkeypatch.setattr(module, "download_arxiv_source_archive", lambda *args, **kwargs: FakeDownload())

    result = await bridge.call_tool("download_source", {"paper_id": "2401.12345"})

    assert result.isError is False
    assert result.structuredContent is not None
    assert result.structuredContent["schema_version"] == 1
    assert result.structuredContent["tool"] == "download_source"
    assert result.structuredContent["result"]["arxiv_id"] == "2401.12345"
    assert "Downloaded source archive" in result.content[0].text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ({}, "paper_id must be a non-empty string"),
        ({"paper_id": "   "}, "paper_id must be a non-empty string"),
        ({"paper_id": "2401.12345", "overwrite": "false"}, "overwrite must be a boolean"),
        ({"paper_id": "2401.12345", "extra": True}, "unsupported arguments: extra"),
    ],
)
async def test_bridge_validates_download_source_arguments(
    arguments: dict[str, object],
    message: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from gpd.mcp.servers import arxiv_bridge as module
    from gpd.mcp.servers.arxiv_bridge import ArxivBridge, ArxivBridgeConfig

    def fail_download(*args, **kwargs):
        raise AssertionError("invalid download_source arguments must not call downloader")

    monkeypatch.setattr(module, "download_arxiv_source_archive", fail_download)

    bridge = ArxivBridge(ArxivBridgeConfig())
    result = await bridge.call_tool("download_source", arguments)

    assert result.isError is True
    assert result.structuredContent is not None
    assert result.structuredContent["schema_version"] == 1
    assert message in result.structuredContent["error"]
    assert message in result.content[0].text


@pytest.mark.asyncio
async def test_bridge_proxies_prompts() -> None:
    from mcp.types import GetPromptResult, ListPromptsResult, Prompt

    from gpd.mcp.servers.arxiv_bridge import ArxivBridge, ArxivBridgeConfig

    prompt = Prompt(name="deep-paper-analysis")

    class FakeSession:
        async def list_prompts(self, cursor=None):
            return ListPromptsResult(prompts=[prompt], nextCursor=None)

        async def get_prompt(self, name, arguments=None):
            return GetPromptResult(description=name, messages=[])

    bridge = ArxivBridge(ArxivBridgeConfig())
    bridge._session = FakeSession()  # type: ignore[assignment]
    try:
        prompts = await bridge.list_prompts()
        prompt_result = await bridge.get_prompt("deep-paper-analysis", {"paper_id": "2401.12345"})
    finally:
        bridge._session = None

    assert prompts.prompts == [prompt]
    assert prompt_result.description == "deep-paper-analysis"


def test_build_server_registers_expected_server_name() -> None:
    from gpd.mcp.servers.arxiv_bridge import ArxivBridgeConfig, build_server

    server, bridge = build_server(ArxivBridgeConfig())

    assert server.name == "gpd-arxiv"
    assert bridge.config.storage_path.is_absolute()


def test_module_entrypoint_runs_main(monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio

    called: list[object] = []

    def fake_asyncio_run(coro):
        called.append(coro)
        coro.close()

    monkeypatch.setattr(asyncio, "run", fake_asyncio_run)
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=r"'gpd\.mcp\.servers\.arxiv_bridge' found in sys\.modules .*",
            category=RuntimeWarning,
        )
        runpy.run_module("gpd.mcp.servers.arxiv_bridge", run_name="__main__")

    assert called
