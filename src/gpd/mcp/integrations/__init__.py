"""Optional GPD-managed MCP integrations."""

from .wolfram_bridge import (
    DEFAULT_WOLFRAM_MCP_ENDPOINT,
    GPD_WOLFRAM_MCP_API_KEY_ENV,
    WolframBridge,
    WolframBridgeConfig,
    build_server,
    load_settings,
    main,
)

__all__ = [
    "DEFAULT_WOLFRAM_MCP_ENDPOINT",
    "GPD_WOLFRAM_MCP_API_KEY_ENV",
    "WolframBridge",
    "WolframBridgeConfig",
    "build_server",
    "load_settings",
    "main",
]
