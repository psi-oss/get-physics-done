"""Ensure runtimes aren\'t hard-coded outside \"adapters\" boundaries."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path

import pytest

from gpd.adapters.runtime_catalog import list_runtime_names


def _non_adapter_python_files(project_root: Path) -> Iterable[Path]:
    src_gpd = project_root / "src" / "gpd"
    adapters_dir = src_gpd / "adapters"
    for path in src_gpd.rglob("*.py"):
        if adapters_dir in path.parents:
            continue
        yield path


def _format_matches(matches: Sequence[tuple[Path, str]], project_root: Path) -> str:
    snippets = []
    for path, runtime in matches[:8]:
        snippets.append(f"{path.relative_to(project_root)} contains '{runtime}'")
    if len(matches) > 8:
        snippets.append(f"... plus {len(matches) - 8} more matches")
    return "\n".join(snippets)


def test_runtime_names_only_appear_in_adapters() -> None:
    project_root = Path(__file__).resolve().parents[2]
    runtime_names = tuple(list_runtime_names())
    if not runtime_names:
        pytest.skip("No runtimes registered in the catalog")

    matches: list[tuple[Path, str]] = []
    for path in _non_adapter_python_files(project_root):
        content = path.read_text(encoding="utf-8")
        for runtime in runtime_names:
            if runtime in content:
                matches.append((path, runtime))
    assert not matches, (
        "Canonical runtime identifiers may only be referenced inside "
        "src/gpd/adapters. \n" + _format_matches(matches, project_root)
    )
