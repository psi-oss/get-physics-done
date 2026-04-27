"""Optional GPD-managed MCP integrations."""

from importlib import import_module

__all__ = [
    "DEFAULT_WOLFRAM_MCP_ENDPOINT",
    "GPD_WOLFRAM_MCP_API_KEY_ENV",
    "WolframBridge",
    "WolframBridgeConfig",
    "build_server",
    "load_settings",
    "main",
]


def __getattr__(name: str) -> object:
    if name in __all__:
        module = import_module(".wolfram_bridge", __name__)
        return getattr(module, name)
    raise AttributeError(name)
