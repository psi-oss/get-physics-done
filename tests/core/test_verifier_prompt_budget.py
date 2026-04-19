"""Prompt budget regressions for the `gpd-verifier` agent surface."""

from __future__ import annotations

from pathlib import Path

import pytest

from gpd.adapters.install_utils import project_markdown_for_runtime
from gpd.adapters.runtime_catalog import iter_runtime_descriptors
from tests.prompt_metrics_support import measure_prompt_surface

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO_ROOT / "src" / "gpd" / "agents"
SOURCE_ROOT = REPO_ROOT / "src" / "gpd"
PATH_PREFIX = "/runtime/"
RUNTIMES = tuple(descriptor.runtime_name for descriptor in iter_runtime_descriptors())


def _projected_budget_for_runtime(runtime: str) -> tuple[int, int]:
    descriptor = next(descriptor for descriptor in iter_runtime_descriptors() if descriptor.runtime_name == runtime)
    if descriptor.native_include_support:
        return (1000, 60000)
    return (6500, 430000)


def _projected_verifier_prompt(runtime: str) -> str:
    return project_markdown_for_runtime(
        (AGENTS_DIR / "gpd-verifier.md").read_text(encoding="utf-8"),
        runtime=runtime,
        path_prefix=PATH_PREFIX,
        surface_kind="agent",
        src_root=SOURCE_ROOT,
        protect_agent_prompt_body=True,
        command_name="gpd-verifier",
    )


def test_gpd_verifier_prompt_surface_stays_within_expected_budget() -> None:
    metrics = measure_prompt_surface(
        AGENTS_DIR / "gpd-verifier.md",
        src_root=SOURCE_ROOT,
        path_prefix=PATH_PREFIX,
    )

    assert metrics.raw_include_count <= 10
    assert metrics.expanded_line_count <= 6500
    assert metrics.expanded_char_count <= 430000
    source = (AGENTS_DIR / "gpd-verifier.md").read_text(encoding="utf-8")
    assert "@{GPD_INSTALL_DIR}/references/verification/domains/" not in source
    assert "@{GPD_INSTALL_DIR}/references/physics-subfields.md" not in source


@pytest.mark.parametrize("runtime", RUNTIMES)
def test_projected_gpd_verifier_prompt_surface_stays_within_runtime_budget(runtime: str) -> None:
    projected = _projected_verifier_prompt(runtime)
    max_lines, max_chars = _projected_budget_for_runtime(runtime)

    assert projected.count("## Agent Requirements") == 1
    assert projected.count("## Bootstrap Discipline") == 1
    assert projected.count("## Canonical LLM Error References") == 1
    assert projected.index("## Agent Requirements") < projected.index("## Bootstrap Discipline")
    assert projected.index("## Bootstrap Discipline") < projected.index("## Canonical LLM Error References")
    assert len(projected.splitlines()) <= max_lines
    assert len(projected) <= max_chars
