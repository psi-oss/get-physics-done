from __future__ import annotations

from contextlib import asynccontextmanager

import pytest


def test_resolve_api_key_prefers_canonical_env_over_alias() -> None:
    from gpd.mcp.integrations.wolfram_bridge import (
        GPD_WOLFRAM_MCP_API_KEY_ENV,
        WOLFRAM_MCP_SERVICE_API_KEY_ENV,
        resolve_api_key,
    )

    env = {
        GPD_WOLFRAM_MCP_API_KEY_ENV: "canonical-token",
        WOLFRAM_MCP_SERVICE_API_KEY_ENV: "legacy-token",
    }

    assert resolve_api_key(env) == "canonical-token"


def test_resolve_api_key_accepts_compatibility_alias() -> None:
    from gpd.mcp.integrations.wolfram_bridge import WOLFRAM_MCP_SERVICE_API_KEY_ENV, resolve_api_key

    assert resolve_api_key({WOLFRAM_MCP_SERVICE_API_KEY_ENV: "legacy-token"}) == "legacy-token"


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

    with pytest.raises(RuntimeError, match="GPD_WOLFRAM_MCP_API_KEY|WOLFRAM_MCP_SERVICE_API_KEY"):
        load_settings({})


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
async def test_bridge_proxies_remote_results_without_rewriting(monkeypatch) -> None:
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

        async def list_resource_templates(self):
            return ListResourceTemplatesResult(resourceTemplates=[template], nextCursor=None)

    bridge = WolframBridge(WolframBridgeConfig(api_key="bridge-token", endpoint="https://example.invalid/mcp"))
    bridge._session = FakeSession()  # type: ignore[assignment]

    tools_result = await bridge.list_tools()
    call_result = await bridge.call_tool("wolf-tool", {"x": 3})
    resources_result = await bridge.list_resources()
    read_result = await bridge.read_resource("https://example.invalid/resource")
    prompts_result = await bridge.list_prompts()
    prompt_result = await bridge.get_prompt("wolf-prompt", {"x": "1"})
    templates_result = await bridge.list_resource_templates()

    assert tools_result.tools == [tool]
    assert call_result.structuredContent == {"name": "wolf-tool", "arguments": {"x": 3}}
    assert resources_result.resources == [resource]
    assert read_result.contents == [resource_contents]
    assert prompts_result.prompts == [prompt]
    assert prompt_result.description == "wolf-prompt"
    assert prompt_result.messages == [prompt_message]
    assert templates_result.resourceTemplates == [template]


def test_build_server_registers_expected_server_name() -> None:
    from gpd.mcp.integrations.wolfram_bridge import WolframBridgeConfig, build_server

    server, bridge = build_server(WolframBridgeConfig(api_key="bridge-token", endpoint="https://example.invalid/mcp"))

    assert bridge.config.endpoint == "https://example.invalid/mcp"
    assert server.name == "gpd-wolfram"


def test_pyproject_exposes_the_wolfram_console_script() -> None:
    from pathlib import Path

    text = Path("pyproject.toml").read_text(encoding="utf-8")

    assert '"gpd-mcp-wolfram" = "gpd.mcp.integrations.wolfram_bridge:main"' in text
