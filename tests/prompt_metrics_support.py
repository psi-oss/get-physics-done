"""Test-only prompt-surface measurement helpers."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from math import ceil
from pathlib import Path

from gpd.adapters import get_adapter
from gpd.adapters.install_utils import expand_at_includes, parse_at_include_path, project_markdown_for_runtime
from gpd.core.model_visible_text import command_visibility_note

DEFAULT_PROMPT_BUDGET_MARGIN = 0.03

__all__ = [
    "DEFAULT_PROMPT_BUDGET_MARGIN",
    "MarkdownFence",
    "PromptSurfaceMetrics",
    "budget_from_baseline",
    "count_raw_includes",
    "count_unfenced_heading",
    "expanded_include_markers",
    "expanded_prompt_text",
    "first_line_containing_any",
    "iter_markdown_fences",
    "iter_unfenced_lines",
    "line_number_for_fragment",
    "measure_prompt_surface",
    "measure_projected_prompt_surface",
    "parse_at_include_path",
    "projected_prompt_text",
    "runtime_command_visibility_note",
]


@dataclass(frozen=True, slots=True)
class PromptSurfaceMetrics:
    """Compact measurements for one expanded prompt surface."""

    source_path: Path
    raw_include_count: int
    expanded_line_count: int
    expanded_char_count: int
    first_question_line: int | None = None
    first_question_marker: str | None = None


@dataclass(frozen=True, slots=True)
class MarkdownFence:
    """One fenced code block with source line metadata."""

    info: str
    body: str
    start_line: int
    end_line: int


def budget_from_baseline(
    value: int,
    *,
    minimum_margin: int,
    margin: float = DEFAULT_PROMPT_BUDGET_MARGIN,
) -> int:
    """Return a stable prompt budget with a small growth allowance."""

    return value + max(minimum_margin, ceil(value * margin))


def runtime_command_visibility_note(runtime: str) -> str:
    """Return the canonical command wrapper note after runtime command translation."""

    return get_adapter(runtime).translate_shared_command_references(command_visibility_note())


def expanded_prompt_text(
    path: Path,
    *,
    src_root: Path,
    path_prefix: str,
    runtime: str | None = None,
) -> str:
    """Return one prompt file with runtime includes expanded."""

    content = path.read_text(encoding="utf-8")
    return expand_at_includes(content, src_root, path_prefix, runtime=runtime)


def projected_prompt_text(
    path: Path,
    *,
    runtime: str,
    src_root: Path,
    path_prefix: str,
    surface_kind: str = "command",
    command_name: str | None = None,
) -> str:
    """Return one prompt file as the final runtime-visible projected text."""

    content = path.read_text(encoding="utf-8")
    return project_markdown_for_runtime(
        content,
        runtime=runtime,
        path_prefix=path_prefix,
        surface_kind=surface_kind,
        src_root=src_root,
        protect_agent_prompt_body=surface_kind == "agent",
        command_name=command_name or path.stem,
    )


def _markdown_fence_marker(stripped_line: str) -> str | None:
    if stripped_line.startswith("```"):
        return "```"
    if stripped_line.startswith("~~~"):
        return "~~~"
    return None


def iter_markdown_fences(text: str) -> Sequence[MarkdownFence]:
    """Return fenced code blocks with 1-based source line metadata."""

    fences: list[MarkdownFence] = []
    active_fence_marker: str | None = None
    active_info = ""
    active_start_line = 0
    active_body: list[str] = []

    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        fence_marker = _markdown_fence_marker(stripped)
        if fence_marker is None:
            if active_fence_marker is not None:
                active_body.append(line)
            continue

        if active_fence_marker is None:
            active_fence_marker = fence_marker
            active_info = stripped[len(fence_marker) :].strip()
            active_start_line = line_number
            active_body = []
            continue

        if fence_marker == active_fence_marker:
            fences.append(
                MarkdownFence(
                    info=active_info,
                    body="\n".join(active_body),
                    start_line=active_start_line,
                    end_line=line_number,
                )
            )
            active_fence_marker = None
            active_info = ""
            active_start_line = 0
            active_body = []
            continue

        active_body.append(line)

    return fences


def count_raw_includes(text: str) -> int:
    """Count raw ``@`` include lines recognized by the installer."""

    include_count = 0
    active_fence_marker: str | None = None

    for line in text.splitlines():
        stripped = line.strip()
        fence_marker = _markdown_fence_marker(stripped)
        if fence_marker is not None:
            if active_fence_marker is None:
                active_fence_marker = fence_marker
            elif fence_marker == active_fence_marker:
                active_fence_marker = None
            continue
        if active_fence_marker is not None:
            continue
        if parse_at_include_path(stripped) is not None:
            include_count += 1
    return include_count


def expanded_include_markers(text: str) -> tuple[str, ...]:
    """Return include marker filenames from an expanded prompt surface."""

    return tuple(re.findall(r"<!-- \[included: ([^\]]+)\] -->", text))


def iter_unfenced_lines(text: str) -> Sequence[str]:
    """Return lines outside fenced code blocks."""

    lines: list[str] = []
    active_fence_marker: str | None = None

    for line in text.splitlines():
        stripped = line.strip()
        fence_marker = _markdown_fence_marker(stripped)
        if fence_marker is not None:
            if active_fence_marker is None:
                active_fence_marker = fence_marker
            elif fence_marker == active_fence_marker:
                active_fence_marker = None
            continue
        if active_fence_marker is not None:
            continue
        lines.append(line)
    return lines


def count_unfenced_heading(text: str, heading: str) -> int:
    """Count exact markdown heading lines outside fenced code blocks."""

    return sum(1 for line in iter_unfenced_lines(text) if line.strip() == heading)


def line_number_for_fragment(text: str, fragment: str, *, start: int = 1) -> int | None:
    """Return the first 1-based line number containing *fragment*."""

    for line_number, line in enumerate(text.splitlines(), start=1):
        if line_number < start:
            continue
        if fragment in line:
            return line_number
    return None


def first_line_containing_any(text: str, fragments: Sequence[str], *, start: int = 1) -> tuple[int, str] | None:
    """Return the first line number and matched fragment among *fragments*."""

    if not fragments:
        return None
    for line_number, line in enumerate(text.splitlines(), start=1):
        if line_number < start:
            continue
        for fragment in fragments:
            if fragment in line:
                return line_number, fragment
    return None


def measure_prompt_surface(
    path: Path,
    *,
    src_root: Path,
    path_prefix: str,
    runtime: str | None = None,
    first_question_fragments: Sequence[str] = (),
) -> PromptSurfaceMetrics:
    """Measure prompt weight and first-question anchors for one prompt file."""

    raw_text = path.read_text(encoding="utf-8")
    expanded_text = expand_at_includes(raw_text, src_root, path_prefix, runtime=runtime)
    first_question_line = None
    first_question_marker = None

    if first_question_fragments:
        match = first_line_containing_any(expanded_text, first_question_fragments)
        if match is not None:
            first_question_line, first_question_marker = match

    return PromptSurfaceMetrics(
        source_path=path,
        raw_include_count=count_raw_includes(raw_text),
        expanded_line_count=len(expanded_text.splitlines()),
        expanded_char_count=len(expanded_text),
        first_question_line=first_question_line,
        first_question_marker=first_question_marker,
    )


def measure_projected_prompt_surface(
    path: Path,
    *,
    runtime: str,
    src_root: Path,
    path_prefix: str,
    surface_kind: str = "command",
    command_name: str | None = None,
) -> PromptSurfaceMetrics:
    """Measure the final runtime-visible projected prompt surface."""

    raw_text = path.read_text(encoding="utf-8")
    projected_text = projected_prompt_text(
        path,
        runtime=runtime,
        src_root=src_root,
        path_prefix=path_prefix,
        surface_kind=surface_kind,
        command_name=command_name,
    )
    return PromptSurfaceMetrics(
        source_path=path,
        raw_include_count=count_raw_includes(raw_text),
        expanded_line_count=len(projected_text.splitlines()),
        expanded_char_count=len(projected_text),
    )
