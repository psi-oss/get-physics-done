"""Guardrails that keep primary prompt sources on canonical tool names."""

from __future__ import annotations

from pathlib import Path

from gpd.adapters.install_utils import convert_tool_references_in_body
from gpd.adapters.tool_names import CANONICAL_TOOL_NAMES, CLAUDE_CODE, canonical
from gpd.registry import _parse_frontmatter, _parse_tools

REPO_ROOT = Path(__file__).resolve().parents[2]
PROMPT_ROOTS = (
    REPO_ROOT / "src/gpd/commands",
    REPO_ROOT / "src/gpd/agents",
)


def _iter_prompt_sources() -> list[Path]:
    files: list[Path] = []
    for root in PROMPT_ROOTS:
        files.extend(sorted(root.rglob("*.md")))
    return files


def _frontmatter_tools(meta: dict[str, object]) -> list[str]:
    tools: list[str] = []
    if "tools" in meta:
        tools.extend(_parse_tools(meta.get("tools")))
    allowed_tools = meta.get("allowed-tools", [])
    if isinstance(allowed_tools, list):
        tools.extend(str(tool) for tool in allowed_tools)
    return tools


def test_primary_prompt_frontmatter_uses_canonical_tool_names() -> None:
    invalid: list[str] = []

    for path in _iter_prompt_sources():
        meta, _body = _parse_frontmatter(path.read_text(encoding="utf-8"))
        for tool in _frontmatter_tools(meta):
            if tool.startswith("mcp__"):
                continue
            if canonical(tool) != tool or tool not in CANONICAL_TOOL_NAMES:
                invalid.append(f"{path.relative_to(REPO_ROOT)} -> {tool}")

    assert invalid == []


def test_primary_prompt_bodies_use_canonical_tool_references() -> None:
    invalid: list[str] = []
    runtime_alias_map = {runtime_name: canonical_name for canonical_name, runtime_name in CLAUDE_CODE.items()}

    for path in _iter_prompt_sources():
        _meta, body = _parse_frontmatter(path.read_text(encoding="utf-8"))
        if convert_tool_references_in_body(body, runtime_alias_map) != body:
            invalid.append(str(path.relative_to(REPO_ROOT)))

    assert invalid == []
