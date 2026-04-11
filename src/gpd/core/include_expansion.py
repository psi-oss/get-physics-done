"""Model-visible ``@`` include expansion shared by registry and adapters."""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

MAX_INCLUDE_EXPANSION_DEPTH = 10

_AT_INCLUDE_LINE_RE = re.compile(r"^(?:[-*+]\s+|\d+\.\s+)?`?(@[^\s`]+)`?(?:\s+.*)?$")
_MARKDOWN_FRONTMATTER_RE = re.compile(
    r"^(?P<preamble>\ufeff?(?:[ \t]*\r?\n)*)---[ \t]*\r?\n(?P<frontmatter>[\s\S]*?)(?P<separator>\r?\n)---[ \t]*(?P<body_separator>\r?\n|$)"
)


class RuntimeConfigDirDescriptor(Protocol):
    config_dir_name: str


def split_markdown_frontmatter(content: str) -> tuple[str, str, str, str]:
    """Return ``(preamble, frontmatter, separator, body)`` for Markdown content."""

    match = _MARKDOWN_FRONTMATTER_RE.match(content)
    if match is None:
        return "", "", "", content
    preamble = match.group("preamble") or ""
    frontmatter = match.group("frontmatter")
    separator = match.group("separator") + "---" + match.group("body_separator")
    body = content[match.end() :]
    return preamble, frontmatter, separator, body


def expand_at_includes(
    content: str,
    src_root: str | Path,
    path_prefix: str,
    *,
    runtime: str | None = None,
    install_scope: str | None = None,
    depth: int = 0,
    include_stack: set[str] | None = None,
    runtime_config_dir_names: frozenset[str] | None = None,
    placeholder_replacer: Callable[[str, str, str | None, str | None], str] | None = None,
) -> str:
    """Inline model-visible ``@{GPD_INSTALL_DIR}/...`` include directives."""

    if depth > MAX_INCLUDE_EXPANSION_DEPTH:
        return content

    if include_stack is None:
        include_stack = set()
    if runtime_config_dir_names is None:
        runtime_config_dir_names = frozenset()

    src_root = Path(src_root)
    lines = content.split("\n")
    result: list[str] = []
    in_code_fence = False

    for line in lines:
        trimmed = line.strip()
        if trimmed.startswith("```"):
            in_code_fence = not in_code_fence
            result.append(line)
            continue
        if in_code_fence:
            result.append(line)
            continue

        include_match = _AT_INCLUDE_LINE_RE.match(trimmed)
        if not include_match:
            result.append(line)
            continue

        include_candidate = include_match.group(1)
        if len(include_candidate) < 3 or include_candidate[1] == " " or re.match(r"^@\w+\{", include_candidate):
            result.append(line)
            continue

        include_path = include_candidate[1:]
        include_path = include_path.split(" (see")[0]
        include_path = include_path.split(" -> ")[0]
        include_path = re.sub(r"\s+\([^)]*\)\s*$", "", include_path).strip()

        if "/" not in include_path or include_path.startswith(("GPD/", "path/")):
            result.append(line)
            continue

        src_path = _resolve_include_source_path(src_root, include_path, runtime_config_dir_names)
        if src_path and src_path.exists():
            abs_key = str(src_path.resolve())
            if abs_key in include_stack:
                result.append(f"<!-- @ include cycle detected: {include_path} -->")
                continue
            if depth == MAX_INCLUDE_EXPANSION_DEPTH:
                result.append(f"<!-- @ include depth limit reached: {include_path} -->")
                continue

            include_stack.add(abs_key)
            try:
                included = src_path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError) as exc:
                result.append(f"<!-- @ include read error: {include_path} ({exc.__class__.__name__}) -->")
                include_stack.discard(abs_key)
                continue

            _preamble, frontmatter, _separator, body = split_markdown_frontmatter(included)
            if not frontmatter:
                body = included
            body = expand_at_includes(
                body.strip() if frontmatter else body,
                src_root,
                path_prefix,
                runtime=runtime,
                install_scope=install_scope,
                depth=depth + 1,
                include_stack=include_stack,
                runtime_config_dir_names=runtime_config_dir_names,
                placeholder_replacer=placeholder_replacer,
            )
            replacer = placeholder_replacer or replace_placeholders
            body = replacer(body, path_prefix, runtime, install_scope)

            result.append("")
            result.append(f"<!-- [included: {src_path.name}] -->")
            result.append(body)
            result.append("<!-- [end included] -->")
            result.append("")
            include_stack.discard(abs_key)
        else:
            result.append(f"<!-- @ include not resolved: {include_path} -->")

    return "\n".join(result)


def replace_placeholders(
    content: str,
    path_prefix: str,
    runtime: str | None,
    install_scope: str | None = None,
) -> str:
    """Replace install placeholders used inside expanded include bodies."""

    config_dir = path_prefix.rstrip("/")
    install_dir = f"{config_dir}/get-physics-done"
    global_config_dir = config_dir
    update_command = "$GPD_UPDATE_COMMAND"
    patch_meta = "$GPD_PATCH_META"
    patches_dir_name = "patches"
    replacements = {
        "GPD_INSTALL_DIR": install_dir,
        "GPD_CONFIG_DIR": config_dir,
        "GPD_GLOBAL_CONFIG_DIR": global_config_dir,
        "GPD_UPDATE_COMMAND": update_command,
        "GPD_PATCH_META": patch_meta,
        "GPD_PATCHES_DIR": f"{config_dir}/{patches_dir_name}",
        "GPD_GLOBAL_PATCHES_DIR": f"{global_config_dir}/{patches_dir_name}",
        "PATCHES_DIR": f"{config_dir}/{patches_dir_name}",
        "GLOBAL_PATCHES_DIR": f"{global_config_dir}/{patches_dir_name}",
    }
    for var, value in replacements.items():
        content = content.replace(f"{{{var}}}", value)
    return content


def _resolve_include_source_path(
    src_root: Path,
    include_path: str,
    runtime_config_dir_names: frozenset[str],
) -> Path | None:
    specs_root = _specs_source_root(src_root)
    agents_root = _agents_source_root(src_root)
    resolved_specs_root = specs_root.resolve(strict=False)
    resolved_agents_root = agents_root.resolve(strict=False)

    def _safe_relative_path(raw_path: str | Path) -> Path | None:
        relative = Path(raw_path)
        if not relative.parts or relative.is_absolute() or ".." in relative.parts:
            return None
        return relative

    def _source_relative_path(candidate: Path, *, resolved_root: Path) -> Path | None:
        resolved_candidate = candidate.expanduser().resolve(strict=False)
        try:
            relative = resolved_candidate.relative_to(resolved_root)
        except ValueError:
            return None
        return _safe_relative_path(relative)

    candidate = Path(include_path).expanduser()
    if candidate.is_absolute():
        relative = _source_relative_path(candidate, resolved_root=resolved_specs_root)
        if relative is not None:
            return specs_root / relative
        relative = _source_relative_path(candidate, resolved_root=resolved_agents_root)
        if relative is not None:
            return agents_root / relative

    if include_path.startswith("{GPD_INSTALL_DIR}/"):
        relative = _safe_relative_path(include_path[len("{GPD_INSTALL_DIR}/") :])
        return specs_root / relative if relative is not None else None
    if include_path.startswith("{GPD_AGENTS_DIR}/"):
        relative = _safe_relative_path(include_path[len("{GPD_AGENTS_DIR}/") :])
        return agents_root / relative if relative is not None else None

    include_parts = Path(include_path).parts
    if "get-physics-done" in include_parts:
        root_index = include_parts.index("get-physics-done")
        relative_parts = include_parts[root_index + 1 :]
        if root_index > 0 and include_parts[root_index - 1] not in runtime_config_dir_names:
            return None
        relative = _safe_relative_path(Path(*relative_parts)) if relative_parts else None
        return specs_root / relative if relative is not None else None
    for agents_index, part in enumerate(include_parts):
        if part != "agents":
            continue
        if agents_index == 0 or include_parts[agents_index - 1] not in runtime_config_dir_names:
            continue
        relative_parts = include_parts[agents_index + 1 :]
        relative = _safe_relative_path(Path(*relative_parts)) if relative_parts else None
        return agents_root / relative if relative is not None else None
    return None


def _specs_source_root(src_root: Path) -> Path:
    specs_root = src_root / "specs"
    if specs_root.is_dir():
        return specs_root
    return src_root


def _agents_source_root(src_root: Path) -> Path:
    specs_root = _specs_source_root(src_root)
    sibling_agents = specs_root.parent / "agents"
    if sibling_agents.is_dir():
        return sibling_agents
    direct_agents = src_root / "agents"
    if direct_agents.is_dir():
        return direct_agents
    return sibling_agents
