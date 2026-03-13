"""Guardrails that keep primary prompt sources on canonical tool names."""

from __future__ import annotations

import re
from pathlib import Path

from gpd.adapters import get_adapter
from gpd.adapters.install_utils import convert_tool_references_in_body
from gpd.adapters.tool_names import CANONICAL_TOOL_NAMES, build_runtime_alias_map, canonical
from gpd.registry import _parse_frontmatter, _parse_tools

REPO_ROOT = Path(__file__).resolve().parents[2]
PRIMARY_PROMPT_ROOTS = (
    REPO_ROOT / "src/gpd/commands",
    REPO_ROOT / "src/gpd/agents",
)
SHARED_SPEC_ROOTS = (REPO_ROOT / "src/gpd/specs",)
FORBIDDEN_CONTEXTUAL_RUNTIME_ALIAS_PATTERNS = (
    re.compile(r"\*\*Read:\*\*"),
    re.compile(r"(?m)^\s*Read:"),
    re.compile(r"\bthe Read\b"),
    re.compile(r"\bnot Edit\b"),
    re.compile(r"\bthe Edit\b"),
    re.compile(r"\bdirect Edit\b"),
    re.compile(r"\btargeted Edit\b"),
    re.compile(r"\(Edit,"),
    re.compile(r"\bEdit \+"),
    re.compile(r"\bFile Edit\b"),
)

_CLAUDE_ALIAS_MAP = build_runtime_alias_map(get_adapter("claude-code").tool_name_map)


def _iter_markdown_sources(*roots: Path) -> list[Path]:
    files: list[Path] = []
    for root in roots:
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

    for path in _iter_markdown_sources(*PRIMARY_PROMPT_ROOTS):
        meta, _body = _parse_frontmatter(path.read_text(encoding="utf-8"))
        for tool in _frontmatter_tools(meta):
            if tool.startswith("mcp__"):
                continue
            if canonical(tool) != tool or tool not in CANONICAL_TOOL_NAMES:
                invalid.append(f"{path.relative_to(REPO_ROOT)} -> {tool}")

    assert invalid == []


def test_primary_prompt_bodies_use_canonical_tool_references() -> None:
    invalid: list[str] = []

    for path in _iter_markdown_sources(*PRIMARY_PROMPT_ROOTS):
        _meta, body = _parse_frontmatter(path.read_text(encoding="utf-8"))
        if convert_tool_references_in_body(body, _CLAUDE_ALIAS_MAP) != body:
            invalid.append(str(path.relative_to(REPO_ROOT)))

    assert invalid == []


def test_shared_specs_use_canonical_tool_references() -> None:
    invalid: list[str] = []

    for path in _iter_markdown_sources(*SHARED_SPEC_ROOTS):
        content = path.read_text(encoding="utf-8")
        if convert_tool_references_in_body(content, _CLAUDE_ALIAS_MAP) != content:
            invalid.append(str(path.relative_to(REPO_ROOT)))

    assert invalid == []


def test_prompt_sources_avoid_contextual_runtime_alias_spellings() -> None:
    invalid: list[str] = []

    for path in _iter_markdown_sources(*PRIMARY_PROMPT_ROOTS, *SHARED_SPEC_ROOTS):
        content = path.read_text(encoding="utf-8")
        for pattern in FORBIDDEN_CONTEXTUAL_RUNTIME_ALIAS_PATTERNS:
            for match in pattern.finditer(content):
                invalid.append(f"{path.relative_to(REPO_ROOT)} -> {match.group(0)}")

    assert invalid == []
