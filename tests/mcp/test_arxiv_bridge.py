from __future__ import annotations

import importlib
import runpy
import warnings
from contextlib import asynccontextmanager

import pytest


def test_load_settings_uses_default_storage_root() -> None:
    from gpd.core.arxiv_source_download import ARXIV_DEFAULT_STORAGE_PATH
    from gpd.mcp.servers.arxiv_bridge import load_settings

    config = load_settings()

    assert config.storage_path == ARXIV_DEFAULT_STORAGE_PATH.resolve()


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
    monkeypatch.setattr(module, "hook_python_interpreter", lambda: "/opt/gpd/bin/python")

    bridge = ArxivBridge(ArxivBridgeConfig(storage_path=tmp_path.resolve()))

    async with bridge.open() as opened:
        assert opened is bridge
        assert bridge._session is not None

    assert observed["command"] == "/opt/gpd/bin/python"
    assert observed["args"] == ["-m", "arxiv_mcp_server", "--storage-path", str(tmp_path.resolve())]
    assert observed["initialized"] is True
    assert observed["session_entered"] is True
    assert observed["session_exited"] is True


@pytest.mark.asyncio
async def test_bridge_filters_upstream_tools_and_adds_download_source() -> None:
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
                ],
                nextCursor=None,
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
        "download_source",
    ]


@pytest.mark.asyncio
async def test_bridge_preserves_list_tools_pagination() -> None:
    from mcp.types import ListToolsResult, Tool

    from gpd.mcp.servers.arxiv_bridge import ArxivBridge, ArxivBridgeConfig

    class FakeSession:
        async def list_tools(self, cursor=None):
            assert cursor == "page-2"
            return ListToolsResult(
                tools=[Tool(name="search_papers", inputSchema={"type": "object"})],
                nextCursor="page-3",
            )

    bridge = ArxivBridge(ArxivBridgeConfig())
    bridge._session = FakeSession()  # type: ignore[assignment]
    try:
        result = await bridge.list_tools("page-2")
    finally:
        bridge._session = None

    assert [tool.name for tool in result.tools] == ["search_papers"]
    assert result.nextCursor == "page-3"


@pytest.mark.asyncio
async def test_bridge_rejects_unknown_tool_calls() -> None:
    from gpd.mcp.servers.arxiv_bridge import ArxivBridge, ArxivBridgeConfig

    class FakeSession:
        async def call_tool(self, name, arguments):
            raise AssertionError("call_tool should not be invoked for unknown tools")

    bridge = ArxivBridge(ArxivBridgeConfig())
    bridge._session = FakeSession()  # type: ignore[assignment]
    try:
        result = await bridge.call_tool("semantic_search", {})
    finally:
        bridge._session = None

    assert result.isError is True

    expected = "Supported tools"
    assert expected in result.content[0].text


@pytest.mark.asyncio
async def test_bridge_proxies_upstream_tool_calls_without_rewriting() -> None:
    from mcp.types import CallToolResult, TextContent

    from gpd.mcp.servers.arxiv_bridge import ArxivBridge, ArxivBridgeConfig

    class FakeSession:
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
    assert result.structuredContent["arxiv_id"] == "2401.12345"
    assert "Downloaded source archive" in result.content[0].text


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


def test_build_server_registers_expected_server_name(monkeypatch: pytest.MonkeyPatch) -> None:
    from gpd.mcp.servers.arxiv_bridge import UPSTREAM_ARXIV_MODULE, ArxivBridgeConfig, build_server

    def fake_find_spec(name: str) -> object:
        assert name == UPSTREAM_ARXIV_MODULE
        return object()

    monkeypatch.setattr(importlib.util, "find_spec", fake_find_spec)

    server, bridge = build_server(ArxivBridgeConfig())

    assert server.name == "gpd-arxiv"
    assert bridge.config.storage_path.is_absolute()


def test_build_server_requires_arxiv_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    from gpd.mcp.servers.arxiv_bridge import UPSTREAM_ARXIV_MODULE, ArxivBridgeConfig, build_server

    def fake_find_spec(name: str) -> None:
        assert name == UPSTREAM_ARXIV_MODULE
        return None

    monkeypatch.setattr(importlib.util, "find_spec", fake_find_spec)

    with pytest.raises(ModuleNotFoundError) as exc_info:
        build_server(ArxivBridgeConfig())

    assert 'pip install "get-physics-done[arxiv]"' in str(exc_info.value)


def test_parse_args_rejects_unsupported_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys

    from gpd.mcp.servers.arxiv_bridge import _parse_args

    monkeypatch.setattr(sys, "argv", ["gpd-mcp-arxiv", "--transport", "sse"])

    with pytest.raises(SystemExit):
        _parse_args()


def test_parse_args_help_surfaces_stdio_transport(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    import sys

    from gpd.mcp.servers.arxiv_bridge import _parse_args

    monkeypatch.setattr(sys, "argv", ["gpd-mcp-arxiv", "--help"])

    with pytest.raises(SystemExit) as exc_info:
        _parse_args()

    assert exc_info.value.code == 0
    assert "--transport {stdio}" in capsys.readouterr().out


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
