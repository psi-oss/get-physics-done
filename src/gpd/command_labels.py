"""Shared normalization for runtime-native GPD command labels."""

from __future__ import annotations

import re
from functools import lru_cache

CANONICAL_COMMAND_PREFIX = "gpd:"
CANONICAL_SKILL_PREFIX = "gpd-"


def _prefix_variants(prefix: str) -> tuple[str, ...]:
    variants: list[str] = []
    for candidate in (
        prefix,
        prefix[1:] if prefix.startswith(("/", "$")) else None,
    ):
        if candidate and candidate not in variants:
            variants.append(candidate)
    return tuple(variants)


@lru_cache(maxsize=1)
def runtime_command_prefixes() -> tuple[str, ...]:
    """Return supported runtime-native command prefixes, longest-first."""

    from gpd.adapters.runtime_catalog import iter_runtime_descriptors

    prefixes: list[str] = []
    seen: set[str] = set()
    for descriptor in iter_runtime_descriptors():
        prefix = descriptor.command_prefix
        for prefix_variant in _prefix_variants(prefix):
            if prefix_variant in seen:
                continue
            seen.add(prefix_variant)
            prefixes.append(prefix_variant)

    for prefix in (CANONICAL_COMMAND_PREFIX, CANONICAL_SKILL_PREFIX):
        if prefix not in seen:
            prefixes.append(prefix)

    prefixes.sort(key=len, reverse=True)
    return tuple(prefixes)


def command_slug_from_label(label: str) -> str:
    """Return the shared command slug from a runtime-native or canonical label."""

    normalized = label.strip()
    if not normalized:
        return ""

    for prefix in runtime_command_prefixes():
        if normalized.startswith(prefix):
            return normalized[len(prefix) :].strip()
    return normalized


def canonical_command_label(label: str) -> str:
    """Return the canonical ``gpd:`` command label for *label*."""

    slug = command_slug_from_label(label)
    return f"{CANONICAL_COMMAND_PREFIX}{slug}" if slug else CANONICAL_COMMAND_PREFIX


def canonical_skill_label(label: str) -> str:
    """Return the canonical ``gpd-`` skill label for *label*."""

    slug = command_slug_from_label(label)
    return f"{CANONICAL_SKILL_PREFIX}{slug}" if slug else CANONICAL_SKILL_PREFIX


@lru_cache(maxsize=1)
def runtime_command_surface_pattern() -> re.Pattern[str]:
    """Return a regex that matches any runtime-native GPD command surface."""

    escaped_prefixes = "|".join(re.escape(prefix) for prefix in runtime_command_prefixes())
    return re.compile(rf"(?<![A-Za-z0-9_-])(?:{escaped_prefixes})(?P<slug>[a-z0-9][a-z0-9-]*)(?!\.md\b)")


def rewrite_runtime_command_surfaces(content: str, *, canonical: str = "skill") -> str:
    """Rewrite runtime-native command surfaces to a canonical shared form."""

    if canonical not in {"command", "skill"}:
        raise ValueError(f"Unsupported canonical surface {canonical!r}")

    replacement_prefix = CANONICAL_COMMAND_PREFIX if canonical == "command" else CANONICAL_SKILL_PREFIX

    def _replace(match: re.Match[str]) -> str:
        return f"{replacement_prefix}{match.group('slug')}"

    return runtime_command_surface_pattern().sub(_replace, content)


__all__ = [
    "CANONICAL_COMMAND_PREFIX",
    "CANONICAL_SKILL_PREFIX",
    "canonical_command_label",
    "canonical_skill_label",
    "command_slug_from_label",
    "rewrite_runtime_command_surfaces",
    "runtime_command_prefixes",
    "runtime_command_surface_pattern",
]
