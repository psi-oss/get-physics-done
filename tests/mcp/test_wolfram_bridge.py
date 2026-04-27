from __future__ import annotations

import os
import subprocess
import sys
from contextlib import asynccontextmanager

import pytest


def test_resolve_api_key_prefers_canonical_env_over_alias() -> None:
    from gpd.mcp.integrations.wolfram_bridge import (
        GPD_WOLFRAM_MCP_API_KEY_ENV,
        resolve_api_key,
    )

    env = {
        GPD_WOLFRAM_MCP_API_KEY_ENV: "canonical-token",
        "WOLFRAM_MCP_SERVICE_API_KEY": "legacy-token",
    }

    assert resolve_api_key(env) == "canonical-token"


def test_resolve_api_key_rejects_compatibility_alias() -> None:
    from gpd.mcp.integrations.wolfram_bridge import resolve_api_key

    with pytest.raises(RuntimeError, match="GPD_WOLFRAM_MCP_API_KEY"):
        resolve_api_key({"WOLFRAM_MCP_SERVICE_API_KEY": "legacy-token"})


def test_module_entrypoint_invokes_main_without_eager_package_import_warning() -> None:
    env = os.environ.copy()
    env.pop("GPD_WOLFRAM_MCP_API_KEY", None)
    env.pop("WOLFRAM_MCP_SERVICE_API_KEY", None)

    result = subprocess.run(
        [sys.executable, "-m", "gpd.mcp.integrations.wolfram_bridge"],
        capture_output=True,
        env=env,
        text=True,
        timeout=5,
        check=False,
    )
    combined_output = result.stdout + result.stderr

    assert result.returncode != 0
    assert "GPD_WOLFRAM_MCP_API_KEY" in combined_output
    assert "RuntimeWarning" not in combined_output


def test_resolve_endpoint_and_api_key_use_the_managed_descriptor_path(monkeypatch: pytest.MonkeyPatch) -> None:
    from gpd.mcp.integrations import wolfram_bridge as module

    observed: dict[str, object] = {}

    class FakeManagedIntegration:
        def resolved_endpoint(self, source):
            observed["endpoint_source"] = dict(source)
            return "https://managed.example.invalid/mcp"

        def resolve_api_key(self, source):
            observed["api_key_source"] = dict(source)
            return "managed-token"

    monkeypatch.setattr(module, "WOLFRAM_MANAGED_INTEGRATION", FakeManagedIntegration())

    assert module.resolve_endpoint({"GPD_WOLFRAM_MCP_ENDPOINT": "ignored"}) == "https://managed.example.invalid/mcp"
    assert module.resolve_api_key({"GPD_WOLFRAM_MCP_API_KEY": "ignored"}) == "managed-token"
    assert observed["endpoint_source"] == {"GPD_WOLFRAM_MCP_ENDPOINT": "ignored"}
    assert observed["api_key_source"] == {"GPD_WOLFRAM_MCP_API_KEY": "ignored"}


def test_load_settings_uses_default_endpoint_and_hides_secret_in_repr() -> None:
    from gpd.mcp.integrations.wolfram_bridge import (
        DEFAULT_WOLFRAM_MCP_ENDPOINT,
        GPD_WOLFRAM_MCP_API_KEY_ENV,
        load_settings,
    )

    config = load_settings({GPD_WOLFRAM_MCP_API_KEY_ENV: "secret-token"})

    assert config.endpoint == DEFAULT_WOLFRAM_MCP_ENDPOINT
    assert "secret-token" not in repr(config)


def test_load_settings_requires_a_nonempty_api_key() -> None:
    from gpd.mcp.integrations.wolfram_bridge import load_settings

    with pytest.raises(RuntimeError, match="GPD_WOLFRAM_MCP_API_KEY"):
        load_settings({})


def test_load_settings_rejects_an_empty_endpoint_override() -> None:
    from gpd.mcp.integrations.wolfram_bridge import (
        GPD_WOLFRAM_MCP_API_KEY_ENV,
        WOLFRAM_MCP_ENDPOINT_ENV_VAR,
        load_settings,
    )

    with pytest.raises(RuntimeError, match="GPD_WOLFRAM_MCP_ENDPOINT is set but empty"):
        load_settings(
            {
                GPD_WOLFRAM_MCP_API_KEY_ENV: "secret-token",
                WOLFRAM_MCP_ENDPOINT_ENV_VAR: "   ",
            }
        )


def test_load_settings_rejects_a_non_https_endpoint_override() -> None:
    from gpd.mcp.integrations.wolfram_bridge import (
        GPD_WOLFRAM_MCP_API_KEY_ENV,
        WOLFRAM_MCP_ENDPOINT_ENV_VAR,
        load_settings,
    )

    with pytest.raises(RuntimeError, match="GPD_WOLFRAM_MCP_ENDPOINT must be an HTTPS URL"):
        load_settings(
            {
                GPD_WOLFRAM_MCP_API_KEY_ENV: "secret-token",
                WOLFRAM_MCP_ENDPOINT_ENV_VAR: "http://example.invalid/api/mcp",
            }
        )


def test_load_settings_uses_process_environment_when_no_mapping_is_passed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from gpd.mcp.integrations.wolfram_bridge import GPD_WOLFRAM_MCP_API_KEY_ENV, load_settings

    monkeypatch.setenv(GPD_WOLFRAM_MCP_API_KEY_ENV, "process-secret")

    config = load_settings()

    assert config.api_key == "process-secret"


@pytest.mark.asyncio
async def test_bridge_open_uses_bearer_token_and_initializes_session(monkeypatch) -> None:
    from gpd.mcp.integrations import wolfram_bridge as module
    from gpd.mcp.integrations.wolfram_bridge import WolframBridge, WolframBridgeConfig

    observed: dict[str, object] = {}

    class FakeSession:
        def __init__(self) -> None:
            self.initialized = False

        async def __aenter__(self):
            observed["session_entered"] = True
            return self

        async def __aexit__(self, exc_type, exc, tb):
            observed["session_exited"] = True

        async def initialize(self):
            self.initialized = True
            observed["initialized"] = True

    @asynccontextmanager
    async def fake_sse_client(endpoint: str, *, headers: dict[str, str], timeout: float, sse_read_timeout: float):
        observed["endpoint"] = endpoint
        observed["headers"] = headers
        observed["timeout"] = timeout
        observed["sse_read_timeout"] = sse_read_timeout
        yield ("read-stream", "write-stream")

    monkeypatch.setattr(module, "sse_client", fake_sse_client)
    monkeypatch.setattr(module, "ClientSession", lambda read_stream, write_stream: FakeSession())

    bridge = WolframBridge(WolframBridgeConfig(endpoint="https://example.invalid/mcp", api_key="bridge-token"))

    async with bridge.open() as opened:
        assert opened is bridge
        assert bridge._session is not None
        assert bridge._session.initialized is True

    assert bridge._session is None
    assert observed["endpoint"] == "https://example.invalid/mcp"
    assert observed["headers"] == {"Authorization": "Bearer bridge-token"}
    assert observed["initialized"] is True
    assert observed["session_entered"] is True
    assert observed["session_exited"] is True


@pytest.mark.asyncio
async def test_bridge_proxies_remote_results_without_rewriting() -> None:
    from mcp.types import (
        CallToolResult,
        GetPromptResult,
        ListPromptsResult,
        ListResourcesResult,
        ListResourceTemplatesResult,
        ListToolsResult,
        Prompt,
        PromptArgument,
        PromptMessage,
        ReadResourceResult,
        Resource,
        ResourceTemplate,
        TextContent,
        TextResourceContents,
        Tool,
    )

    from gpd.mcp.integrations.wolfram_bridge import WolframBridge, WolframBridgeConfig

    tool = Tool(name="wolf-tool", inputSchema={"type": "object", "properties": {"x": {"type": "number"}}})
    resource = Resource(name="wolf-resource", uri="https://example.invalid/resource")
    prompt = Prompt(name="wolf-prompt", arguments=[PromptArgument(name="x")])
    template = ResourceTemplate(name="wolf-template", uriTemplate="wolfram://{name}")
    text = TextContent(type="text", text="ok")
    resource_contents = TextResourceContents(uri="https://example.invalid/resource", text="content")
    prompt_message = PromptMessage(role="user", content=text)

    class FakeSession:
        async def list_tools(self, cursor=None):
            return ListToolsResult(tools=[tool], nextCursor=None)

        async def call_tool(self, name, arguments):
            return CallToolResult(content=[text], structuredContent={"name": name, "arguments": arguments})

        async def list_resources(self, cursor=None):
            return ListResourcesResult(resources=[resource], nextCursor=None)

        async def read_resource(self, uri):
            return ReadResourceResult(contents=[resource_contents])

        async def list_prompts(self, cursor=None):
            return ListPromptsResult(prompts=[prompt], nextCursor=None)

        async def get_prompt(self, name, arguments=None):
            return GetPromptResult(description=name, messages=[prompt_message])

        async def list_resource_templates(self, cursor=None):
            return ListResourceTemplatesResult(resourceTemplates=[template], nextCursor=cursor)

    bridge = WolframBridge(WolframBridgeConfig(api_key="bridge-token", endpoint="https://example.invalid/mcp"))
    bridge._session = FakeSession()  # type: ignore[assignment]

    try:
        tools_result = await bridge.list_tools()
        call_result = await bridge.call_tool("wolf-tool", {"x": 3})
        resources_result = await bridge.list_resources()
        read_result = await bridge.read_resource("https://example.invalid/resource")
        prompts_result = await bridge.list_prompts()
        prompt_result = await bridge.get_prompt("wolf-prompt", {"x": "1"})
        templates_result = await bridge.list_resource_templates("cursor-1")
    finally:
        bridge._session = None

    assert tools_result.tools == [tool]
    assert call_result.structuredContent == {"name": "wolf-tool", "arguments": {"x": 3}}
    assert resources_result.resources == [resource]
    assert read_result.contents == [resource_contents]
    assert prompts_result.prompts == [prompt]
    assert prompt_result.description == "wolf-prompt"
    assert prompt_result.messages == [prompt_message]
    assert templates_result.resourceTemplates == [template]
    assert templates_result.nextCursor == "cursor-1"


@pytest.mark.asyncio
async def test_bridge_list_resource_templates_preserves_cursor_and_next_cursor() -> None:
    from mcp.types import ListResourceTemplatesResult, ResourceTemplate

    from gpd.mcp.integrations.wolfram_bridge import WolframBridge, WolframBridgeConfig

    observed: dict[str, object] = {}
    template = ResourceTemplate(name="wolf-template", uriTemplate="wolfram://{name}")

    class FakeSession:
        async def list_resource_templates(self, cursor=None):
            observed["cursor"] = cursor
            return ListResourceTemplatesResult(resourceTemplates=[template], nextCursor="cursor-2")

    bridge = WolframBridge(WolframBridgeConfig(api_key="bridge-token", endpoint="https://example.invalid/mcp"))
    bridge._session = FakeSession()  # type: ignore[assignment]

    try:
        result = await bridge.list_resource_templates("cursor-1")
    finally:
        bridge._session = None

    assert observed["cursor"] == "cursor-1"
    assert result.resourceTemplates == [template]
    assert result.nextCursor == "cursor-2"


def test_build_server_registers_expected_server_name() -> None:
    from gpd.mcp.integrations.wolfram_bridge import WOLFRAM_MANAGED_SERVER_KEY, WolframBridgeConfig, build_server

    server, bridge = build_server(WolframBridgeConfig(api_key="bridge-token", endpoint="https://example.invalid/mcp"))

    assert bridge.config.endpoint == "https://example.invalid/mcp"
    assert server.name == WOLFRAM_MANAGED_SERVER_KEY


@pytest.mark.asyncio
async def test_build_server_resource_handlers_match_lowlevel_server_api(monkeypatch: pytest.MonkeyPatch) -> None:
    from mcp import types

    from gpd.mcp.integrations.wolfram_bridge import WolframBridgeConfig, build_server

    server, bridge = build_server(WolframBridgeConfig(api_key="bridge-token", endpoint="https://example.invalid/mcp"))
    template = types.ResourceTemplate(name="wolf-template", uriTemplate="wolfram://{name}")

    async def fake_read_resource(uri: str):
        return types.ReadResourceResult(
            contents=[types.TextResourceContents(uri=uri, text="content", mimeType="text/plain")]
        )

    async def fake_list_resource_templates(cursor: str | None = None):
        assert cursor == "cursor-1"
        return types.ListResourceTemplatesResult(resourceTemplates=[template], nextCursor="cursor-ignored")

    monkeypatch.setattr(bridge, "read_resource", fake_read_resource)
    monkeypatch.setattr(bridge, "list_resource_templates", fake_list_resource_templates)

    read_response = await server.request_handlers[types.ReadResourceRequest](
        types.ReadResourceRequest(params=types.ReadResourceRequestParams(uri="https://example.invalid/resource"))
    )
    templates_response = await server.request_handlers[types.ListResourceTemplatesRequest](
        types.ListResourceTemplatesRequest(params=types.PaginatedRequestParams(cursor="cursor-1"))
    )

    assert read_response.root.contents[0].text == "content"
    assert read_response.root.contents[0].mimeType == "text/plain"
    assert templates_response.root.resourceTemplates == [template]
    assert templates_response.root.nextCursor == "cursor-ignored"


def test_pyproject_exposes_the_wolfram_console_script() -> None:
    from pathlib import Path

    text = Path("pyproject.toml").read_text(encoding="utf-8")

    assert '"gpd-mcp-wolfram" = "gpd.mcp.integrations.wolfram_bridge:main"' in text
