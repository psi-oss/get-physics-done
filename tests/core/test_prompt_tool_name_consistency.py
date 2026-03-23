"""Guardrails that keep primary prompt sources on canonical tool names."""

from __future__ import annotations

import re
from pathlib import Path

from gpd.adapters import iter_adapters
from gpd.adapters.install_utils import convert_tool_references_in_body
from gpd.adapters.tool_names import CANONICAL_TOOL_NAMES, build_canonical_alias_map, canonical
from gpd.registry import _parse_frontmatter, _parse_tools

REPO_ROOT = Path(__file__).resolve().parents[2]
PRIMARY_PROMPT_ROOTS = (
    REPO_ROOT / "src/gpd/commands",
    REPO_ROOT / "src/gpd/agents",
)
SHARED_SPEC_ROOTS = (REPO_ROOT / "src/gpd/specs",)
AMBIGUOUS_RUNTIME_ALIAS_NAMES = frozenset({"question", "replace", "skill", "todo"})
FORBIDDEN_CONTEXTUAL_RUNTIME_ALIAS_PATTERNS = (
    re.compile(r"\*\*Read:\*\*"),
    re.compile(r"\bthe Read\b"),
    re.compile(r"\bnot Edit\b"),
    re.compile(r"\bthe Edit\b"),
    re.compile(r"\bdirect Edit\b"),
    re.compile(r"\btargeted Edit\b"),
    re.compile(r"\(Edit,"),
    re.compile(r"\bEdit \+"),
    re.compile(r"\bFile Edit\b"),
)
_FENCED_CODE_BLOCK_RE = re.compile(r"```[\s\S]*?```")
_INLINE_CODE_RE = re.compile(r"`[^`]*`")
_PATHLIKE_TOKEN_RE = re.compile(r"(?<!\w)(?:\S*/\S+\b)")
_AMBIGUOUS_RUNTIME_ALIAS_TOOL_CONTEXT_RE = re.compile(
    r"`(?:question|replace|skill|todo)(?:\([^`]*\))?`|\b(?:question|replace|skill|todo)\(",
)
_AMBIGUOUS_RUNTIME_ALIAS_PROSE_RE = re.compile(
    r"(?i)\b(?:use|using|call|invoke|run|spawn|ask|present|select|choose)\s+(?:the\s+)?(?:question|replace|skill|todo)\b(?:\s*[\(:][^`\n]*)?"
)
_BODY_TOOL_SECTION_RE = re.compile(r"(?i)(?:\btool\b|\btools\b|available tools|tool availability|tool surface|tool access|tool selection)")
_FENCED_CODE_SEGMENT_RE = re.compile(r"```(?P<info>[^\n`]*)\n(?P<body>[\s\S]*?)```")
_NON_TOOL_FENCE_LANGUAGES = frozenset({"bash", "sh", "shell", "zsh", "python", "json", "yaml", "toml"})

_MERGED_RUNTIME_ALIAS_MAP = build_canonical_alias_map(adapter.tool_name_map for adapter in iter_adapters())
_STRICT_RUNTIME_ALIAS_MAP = {
    source: target for source, target in _MERGED_RUNTIME_ALIAS_MAP.items() if source not in AMBIGUOUS_RUNTIME_ALIAS_NAMES
}
_CODE_TOOL_ALIAS_NAMES = tuple(
    alias
    for alias, target in sorted(_STRICT_RUNTIME_ALIAS_MAP.items(), key=lambda item: len(item[0]), reverse=True)
    if "_" in alias and alias != target
)
_CODE_TOOL_ALIAS_RE = re.compile(
    r"^(?:"
    + "|".join(re.escape(alias) for alias in _CODE_TOOL_ALIAS_NAMES)
    + r")(?:\([^`]*\))?$"
)


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


def _sanitize_body_for_alias_scan(body: str) -> str:
    body = _FENCED_CODE_BLOCK_RE.sub("CODE_BLOCK", body)
    body = _INLINE_CODE_RE.sub("CODE", body)
    return _PATHLIKE_TOKEN_RE.sub("PATH", body)


def _iter_code_segments(body: str) -> list[str]:
    return [*(_FENCED_CODE_BLOCK_RE.findall(body)), *(_INLINE_CODE_RE.findall(body))]


def _fenced_segment_contains_runtime_alias(segment: str) -> bool:
    match = _FENCED_CODE_SEGMENT_RE.fullmatch(segment)
    if match is None:
        return False
    info = match.group("info").strip().lower()
    if info in _NON_TOOL_FENCE_LANGUAGES:
        return False
    for raw_line in match.group("body").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if _CODE_TOOL_ALIAS_RE.fullmatch(line):
            return True
    return False


def _inline_segment_contains_runtime_alias(segment: str) -> bool:
    if _AMBIGUOUS_RUNTIME_ALIAS_TOOL_CONTEXT_RE.fullmatch(segment) is not None:
        return True
    code = segment.strip("`").strip()
    if not code or any(token in code for token in ("/", "{", "}", "$", " ")):
        return False
    return _CODE_TOOL_ALIAS_RE.fullmatch(code) is not None


def _body_contains_runtime_alias_leaks(body: str) -> bool:
    code_segments = _iter_code_segments(body)
    if any(
        _fenced_segment_contains_runtime_alias(segment) or _inline_segment_contains_runtime_alias(segment)
        for segment in code_segments
    ):
        return True
    sanitized = _sanitize_body_for_alias_scan(body)
    return (
        convert_tool_references_in_body(sanitized, _STRICT_RUNTIME_ALIAS_MAP) != sanitized
        or _AMBIGUOUS_RUNTIME_ALIAS_TOOL_CONTEXT_RE.search(sanitized) is not None
        or _AMBIGUOUS_RUNTIME_ALIAS_PROSE_RE.search(sanitized) is not None
    )


def _body_explicit_tool_requirements(body: str) -> set[str]:
    requirements: set[str] = set()
    capture = False
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line:
            capture = False
            continue
        if line.startswith("#") or line.startswith("**") or line.startswith("- ") or line.startswith("* "):
            if _BODY_TOOL_SECTION_RE.search(line) and (line.endswith(":") or line.startswith("#") or line.startswith("**")):
                capture = True
                continue
        if not capture:
            continue
        for tool in CANONICAL_TOOL_NAMES:
            if tool in {"agent", "task", "file_edit"}:
                continue
            if re.search(rf"(?<!\\w){re.escape(tool)}(?!\\w)", line):
                requirements.add(tool)
    return requirements


def test_body_alias_scan_flags_runtime_aliases_inside_inline_code() -> None:
    assert _body_contains_runtime_alias_leaks("Use `run_shell_command` before proceeding.") is True


def test_body_alias_scan_flags_runtime_aliases_inside_fenced_code() -> None:
    body = """```text
search_file_content
```"""
    assert _body_contains_runtime_alias_leaks(body) is True


def test_body_alias_scan_flags_ambiguous_aliases_only_in_tool_like_contexts() -> None:
    assert _body_contains_runtime_alias_leaks("Apply `replace(old, new)` to the artifact.") is True
    assert _body_contains_runtime_alias_leaks("The open question is still unresolved.") is False


def test_body_alias_scan_flags_realistic_alias_invocations_and_prose_instructions() -> None:
    assert _body_contains_runtime_alias_leaks('Use question(header="Ready?") before proceeding.') is True
    assert _body_contains_runtime_alias_leaks("Use question with options before proceeding.") is True


def test_body_alias_scan_does_not_flag_ordinary_imperative_read_prose() -> None:
    assert _body_contains_runtime_alias_leaks("Read: the next section carefully before continuing.") is False


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


def test_primary_prompt_body_tool_requirements_are_declared_in_frontmatter() -> None:
    invalid: list[str] = []

    for path in _iter_markdown_sources(*PRIMARY_PROMPT_ROOTS):
        meta, body = _parse_frontmatter(path.read_text(encoding="utf-8"))
        declared_tools = set(_frontmatter_tools(meta))
        missing = sorted(tool for tool in _body_explicit_tool_requirements(body) if tool not in declared_tools)
        if missing:
            invalid.append(f"{path.relative_to(REPO_ROOT)} -> {', '.join(missing)}")

    assert invalid == []


def test_primary_prompt_bodies_use_canonical_tool_references() -> None:
    invalid: list[str] = []

    for path in _iter_markdown_sources(*PRIMARY_PROMPT_ROOTS):
        _meta, body = _parse_frontmatter(path.read_text(encoding="utf-8"))
        if _body_contains_runtime_alias_leaks(body):
            invalid.append(str(path.relative_to(REPO_ROOT)))

    assert invalid == []


def test_shared_specs_use_canonical_tool_references() -> None:
    invalid: list[str] = []

    for path in _iter_markdown_sources(*SHARED_SPEC_ROOTS):
        content = path.read_text(encoding="utf-8")
        if _body_contains_runtime_alias_leaks(content):
            invalid.append(str(path.relative_to(REPO_ROOT)))

    assert invalid == []


def test_new_project_notation_delegate_omits_model_argument_when_model_is_empty() -> None:
    content = (REPO_ROOT / "src/gpd/specs/workflows/new-project.md").read_text(encoding="utf-8")
    marker = 'NOTATION_MODEL=$(gpd resolve-model gpd-notation-coordinator)'
    start = content.index(marker)
    task_start = content.index('task(prompt="First, read {GPD_AGENTS_DIR}/gpd-notation-coordinator.md', start)
    task_end = content.index('", subagent_type="gpd-notation-coordinator"', task_start)
    notation_block = content[task_start:task_end]

    assert 'model="{notation_model}"' not in notation_block
    assert "If `NOTATION_MODEL` is empty or null, omit `model=` entirely in the spawn call." in content


def test_prompt_sources_avoid_contextual_runtime_alias_spellings() -> None:
    invalid: list[str] = []

    for path in _iter_markdown_sources(*PRIMARY_PROMPT_ROOTS, *SHARED_SPEC_ROOTS):
        content = path.read_text(encoding="utf-8")
        for pattern in FORBIDDEN_CONTEXTUAL_RUNTIME_ALIAS_PATTERNS:
            for match in pattern.finditer(content):
                invalid.append(f"{path.relative_to(REPO_ROOT)} -> {match.group(0)}")

    assert invalid == []
