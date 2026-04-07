"""Test-only prompt-surface measurement helpers."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from gpd.adapters.install_utils import expand_at_includes

__all__ = [
    "PromptSurfaceMetrics",
    "count_raw_includes",
    "expanded_prompt_text",
    "first_line_containing_any",
    "line_number_for_fragment",
    "measure_prompt_surface",
]

_AT_INCLUDE_LINE_RE = re.compile(r"^\s*@\{[^}]+\}/\S+")


@dataclass(frozen=True, slots=True)
class PromptSurfaceMetrics:
    """Compact measurements for one expanded prompt surface."""

    source_path: Path
    raw_include_count: int
    expanded_line_count: int
    expanded_char_count: int
    first_question_line: int | None = None
    first_question_marker: str | None = None


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


def count_raw_includes(text: str) -> int:
    """Count top-level ``@`` include lines in markdown content."""

    include_count = 0
    in_code_fence = False

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code_fence = not in_code_fence
            continue
        if in_code_fence:
            continue
        if _AT_INCLUDE_LINE_RE.match(stripped):
            include_count += 1
    return include_count


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
