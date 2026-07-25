"""Published tool schemas must stay portable across MCP client schema dialects.

Regression guard for issue #239: Gemini's OpenAPI schema subset rejects the
JSON Schema ``const`` keyword and types ``enum`` values as strings, so a
``{"const": 1}`` fragment published by any GPD server surfaces as an
``Invalid value ... (TYPE_STRING), 1`` error in Gemini-backed runtimes.

The ``arxiv_bridge`` server builds a lowlevel ``mcp.Server`` inside its entry
point rather than a module-level FastMCP instance, so it is exercised by its
own suite; its hand-written tool schemas contain no draft-only keywords.
"""

from __future__ import annotations

import importlib

import anyio

from gpd.mcp.servers import portable_published_schema

_FASTMCP_SERVER_MODULES = (
    "conventions_server",
    "errors_mcp",
    "patterns_server",
    "protocols_server",
    "skills_server",
    "state_server",
    "verification_server",
)

# Subtree keywords whose contents draft-aware validators evaluate conditionally;
# clients targeting restricted dialects drop these subtrees wholesale, so
# non-string enum members inside them never reach a provider's schema proto.
_CONDITIONAL_KEYWORDS = frozenset({"if", "then", "else", "not"})


def _collect_violations(fragment: object, path: str, *, in_conditional: bool, violations: list[str]) -> None:
    """Append a dotted-path complaint for each restricted-dialect violation under ``fragment``.

    Flags any surviving ``const`` keyword, and non-string ``enum`` members
    outside the conditional subtrees listed in ``_CONDITIONAL_KEYWORDS``.
    """

    if isinstance(fragment, dict):
        if "const" in fragment:
            violations.append(f"{path}: draft-only `const` keyword in published schema")
        enum_values = fragment.get("enum")
        if isinstance(enum_values, list) and not in_conditional:
            non_string = [value for value in enum_values if not isinstance(value, str)]
            if non_string:
                violations.append(f"{path}: non-string enum members {non_string!r} outside a conditional subtree")
        for key, value in fragment.items():
            _collect_violations(
                value,
                f"{path}.{key}",
                in_conditional=in_conditional or key in _CONDITIONAL_KEYWORDS,
                violations=violations,
            )
    elif isinstance(fragment, list):
        for index, item in enumerate(fragment):
            _collect_violations(item, f"{path}[{index}]", in_conditional=in_conditional, violations=violations)


def _published_tool_schemas(module_name: str) -> list[tuple[str, dict[str, object]]]:
    """Return ``(tool_name, inputSchema)`` pairs as the named server actually publishes them.

    Reads through ``list_tools()`` rather than the in-process registry so the
    assertion covers the payload a client receives.
    """

    module = importlib.import_module(f"gpd.mcp.servers.{module_name}")

    async def _load() -> list[tuple[str, dict[str, object]]]:
        tools = await module.mcp.list_tools()
        return [(str(tool.name), tool.inputSchema) for tool in tools]

    return anyio.run(_load)


def test_all_published_tool_schemas_are_runtime_portable() -> None:
    """Every FastMCP server publishes schemas a restricted-dialect client can encode."""

    violations: list[str] = []
    for module_name in _FASTMCP_SERVER_MODULES:
        for tool_name, schema in _published_tool_schemas(module_name):
            _collect_violations(
                schema,
                f"{module_name}.{tool_name}",
                in_conditional=False,
                violations=violations,
            )
    assert not violations, "Published schemas contain keywords Gemini-dialect clients reject:\n" + "\n".join(violations)


def test_portable_schema_rewrites_string_const_to_enum() -> None:
    """A string ``const`` becomes a single-member ``enum``, leaving the input untouched."""

    schema = {"type": "object", "properties": {"mode": {"type": "string", "const": "strict"}}}
    portable = portable_published_schema(schema)
    assert portable["properties"]["mode"] == {"type": "string", "enum": ["strict"]}
    # The input schema is never mutated.
    assert schema["properties"]["mode"]["const"] == "strict"


def test_portable_schema_rewrites_integer_const_to_bounds() -> None:
    """A numeric ``const`` becomes equal ``minimum``/``maximum`` bounds, not a typed enum."""

    schema = {"type": "object", "properties": {"schema_version": {"type": "integer", "const": 1}}}
    portable = portable_published_schema(schema)
    assert portable["properties"]["schema_version"] == {"type": "integer", "minimum": 1, "maximum": 1}


def test_portable_schema_rewrites_boolean_const_to_single_member_enum() -> None:
    """A boolean ``const`` inside a conditional subtree becomes a single-member ``enum``."""

    schema = {"if": {"properties": {"must_surface": {"const": True}}}, "then": {"required": ["applies_to"]}}
    portable = portable_published_schema(schema)
    assert portable["if"]["properties"]["must_surface"] == {"enum": [True]}
    assert portable["then"] == {"required": ["applies_to"]}


def test_portable_schema_walks_nested_structures() -> None:
    """Rewriting reaches ``const`` nested under ``anyOf`` members and ``items``."""

    schema = {
        "type": "object",
        "properties": {
            "payload": {
                "anyOf": [
                    {"type": "array", "items": {"const": "fixed"}},
                    {"type": "null"},
                ]
            }
        },
    }
    portable = portable_published_schema(schema)
    assert portable["properties"]["payload"]["anyOf"][0]["items"] == {"enum": ["fixed"]}


def test_portable_schema_documents_unrepresentable_const_values() -> None:
    """Values with no keyword equivalent are dropped and described in prose instead."""

    schema = {"properties": {"marker": {"const": None, "description": "Sentinel."}}}
    portable = portable_published_schema(schema)
    marker = portable["properties"]["marker"]
    assert "const" not in marker
    assert marker["description"] == "Sentinel. Must be exactly null."
