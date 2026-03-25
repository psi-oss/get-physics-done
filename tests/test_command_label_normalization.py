from __future__ import annotations

from pathlib import Path

import pytest

from gpd import registry
from gpd.adapters.runtime_catalog import iter_runtime_descriptors
from gpd.cli import _canonical_command_name
from gpd.command_labels import (
    canonical_command_label,
    canonical_skill_label,
    command_slug_from_label,
    rewrite_runtime_command_surfaces,
    runtime_command_prefixes,
)
from gpd.mcp.servers.skills_server import _canonicalize_command_surface


@pytest.fixture(autouse=True)
def _clean_registry_cache() -> None:
    registry.invalidate_cache()
    yield
    registry.invalidate_cache()


@pytest.fixture
def _registry_roots(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    commands_dir = tmp_path / "commands"
    agents_dir = tmp_path / "agents"
    commands_dir.mkdir()
    agents_dir.mkdir()
    monkeypatch.setattr(registry, "COMMANDS_DIR", commands_dir)
    monkeypatch.setattr(registry, "AGENTS_DIR", agents_dir)
    registry.invalidate_cache()
    return commands_dir, agents_dir


def _command_label(prefix: str, slug: str) -> str:
    return f"{prefix}{slug}"


def test_runtime_command_prefixes_are_derived_from_the_runtime_catalog() -> None:
    expected_prefixes: list[str] = []
    seen: set[str] = set()
    for descriptor in iter_runtime_descriptors():
        for candidate in (descriptor.command_prefix, descriptor.command_prefix[1:] if descriptor.command_prefix[:1] in {"/", "$"} else None):
            if candidate and candidate not in seen:
                seen.add(candidate)
                expected_prefixes.append(candidate)
    for canonical_prefix in ("gpd:", "gpd-"):
        if canonical_prefix not in seen:
            seen.add(canonical_prefix)
            expected_prefixes.append(canonical_prefix)
    expected_prefixes.sort(key=len, reverse=True)

    assert runtime_command_prefixes() == tuple(expected_prefixes)


@pytest.mark.parametrize("descriptor", iter_runtime_descriptors(), ids=lambda item: item.runtime_name)
def test_registry_accepts_runtime_native_command_labels(
    _registry_roots: tuple[Path, Path],
    descriptor: object,
) -> None:
    commands_dir, _ = _registry_roots
    (commands_dir / "execute-phase.md").write_text(
        "---\nname: gpd:execute-phase\ndescription: Execute\n---\nExecute body.\n",
        encoding="utf-8",
    )

    command = registry.get_command(_command_label(descriptor.command_prefix, "execute-phase"))

    assert command.name == "gpd:execute-phase"


@pytest.mark.parametrize("descriptor", iter_runtime_descriptors(), ids=lambda item: item.runtime_name)
def test_registry_accepts_runtime_native_skill_labels(
    _registry_roots: tuple[Path, Path],
    descriptor: object,
) -> None:
    commands_dir, _ = _registry_roots
    (commands_dir / "execute-phase.md").write_text(
        "---\nname: gpd:execute-phase\ndescription: Execute\n---\nExecute body.\n",
        encoding="utf-8",
    )

    skill = registry.get_skill(_command_label(descriptor.command_prefix, "execute-phase"))

    assert skill.name == "gpd-execute-phase"


@pytest.mark.parametrize("descriptor", iter_runtime_descriptors(), ids=lambda item: item.runtime_name)
def test_runtime_native_command_labels_canonicalize_across_shared_surfaces(descriptor: object) -> None:
    label = _command_label(descriptor.command_prefix, "execute-phase")

    assert canonical_command_label(label) == "gpd:execute-phase"
    assert canonical_skill_label(label) == "gpd-execute-phase"
    assert _canonical_command_name(label) == "gpd:execute-phase"


@pytest.mark.parametrize("descriptor", iter_runtime_descriptors(), ids=lambda item: item.runtime_name)
def test_runtime_native_command_surfaces_rewrite_to_canonical_skill_labels(descriptor: object) -> None:
    content = (
        f"Run {_command_label(descriptor.command_prefix, 'execute-phase')} first.\n"
        f"Then try {_command_label(descriptor.command_prefix, 'help')}.\n"
    )

    rewritten = rewrite_runtime_command_surfaces(content, canonical="skill")

    assert "gpd-execute-phase" in rewritten
    assert "gpd-help" in rewritten
    assert _canonicalize_command_surface(content) == rewritten


def test_runtime_command_surface_rewrite_does_not_mutate_markdown_paths() -> None:
    content = "Read /tmp/specs/gpd-help.md and /tmp/agents/gpd-executor.md before continuing."

    assert rewrite_runtime_command_surfaces(content, canonical="skill") == content


def test_foreign_bare_slash_command_is_not_canonicalized_into_gpd() -> None:
    assert command_slug_from_label("/help") == "/help"
    assert canonical_command_label("/help") == "gpd:/help"
    assert canonical_skill_label("/help") == "gpd-/help"
