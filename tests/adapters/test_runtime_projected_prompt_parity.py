"""Runtime-projected prompt parity for contract-heavy command and agent surfaces."""

from __future__ import annotations

from pathlib import Path

import pytest

from gpd import registry
from gpd.adapters.install_utils import project_markdown_for_runtime
from gpd.adapters.runtime_catalog import get_runtime_descriptor, iter_runtime_descriptors
from gpd.core.model_visible_text import (
    agent_visibility_note,
    command_visibility_note,
    review_contract_visibility_note,
)
from gpd.registry import _frontmatter_parts, _load_frontmatter_mapping, _parse_spawn_contracts

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_DIR = REPO_ROOT / "src/gpd/commands"
AGENTS_DIR = REPO_ROOT / "src/gpd/agents"

RUNTIMES = tuple(descriptor.runtime_name for descriptor in iter_runtime_descriptors())
SPAWN_CONTRACT_COMMANDS = tuple(
    command_name
    for command_name in registry.list_commands()
    if "<spawn_contract>" in registry.get_command(command_name).content
)
VERIFIER_BUDGET_BY_NATIVE_INCLUDE_SUPPORT = {
    True: (900, 60_000),
    False: (6_500, 430_000),
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")

def _command_frontmatter(command_name: str) -> dict[str, object]:
    frontmatter, _body = _frontmatter_parts(_read(COMMANDS_DIR / f"{command_name}.md"))
    assert frontmatter is not None, f"{command_name} is missing command frontmatter"
    return _load_frontmatter_mapping(frontmatter, error_prefix=f"Malformed frontmatter for {command_name}")


def _contract_bearing_command_surfaces() -> dict[str, tuple[str, ...]]:
    surfaces: dict[str, tuple[str, ...]] = {}
    for command_name in registry.list_commands():
        meta = _command_frontmatter(command_name)
        fragments = [command_visibility_note()]
        review_contract = meta.get("review-contract")
        if isinstance(review_contract, dict):
            fragments.append(review_contract_visibility_note())
            if "required_state" in review_contract:
                fragments.append("required_state:")
        if meta.get("agent") or "review-contract" in meta or "allowed-tools" in meta or "requires" in meta:
            surfaces[command_name] = tuple(fragments)
    return surfaces


COMMAND_SURFACES = _contract_bearing_command_surfaces()
PLAN_AGENT_SURFACES = {
    "gpd-planner": (
        agent_visibility_note(),
        "tool_requirements",
        "must_surface",
        "`wolfram` and `command`",
    ),
}
RESULT_AGENT_SURFACES = {
    "gpd-verifier": (
        agent_visibility_note(),
        "contract_results",
        "comparison_verdicts",
        "suggested_contract_checks",
        "completed_actions",
        "missing_actions",
        "inconclusive` / `tension`",
    ),
    "gpd-executor": (
        agent_visibility_note(),
        "plan_contract_ref",
        "contract_results",
        "comparison_verdicts",
    ),
}


def _project_markdown(path: Path, runtime: str, *, is_agent: bool) -> str:
    return project_markdown_for_runtime(
        _read(path),
        runtime=runtime,
        path_prefix="/runtime/",
        surface_kind="agent" if is_agent else "command",
        src_root=REPO_ROOT / "src/gpd",
        protect_agent_prompt_body=is_agent,
        command_name=path.stem,
    )


def _assert_fragments_visible(text: str, fragments: tuple[str, ...], *, label: str) -> None:
    missing = sorted(fragment for fragment in fragments if fragment not in text)
    assert not missing, f"{label} is missing contract-bearing fragments: {', '.join(missing)}"


def _extract_spawn_contracts(text: str) -> list[dict[str, object]]:
    return list(_parse_spawn_contracts(text, owner_name="runtime-projected"))


@pytest.mark.parametrize("runtime", RUNTIMES)
@pytest.mark.parametrize(("command_name", "expected_fragments"), tuple(COMMAND_SURFACES.items()))
def test_runtime_projected_commands_keep_model_visible_contract_wrappers(command_name: str, expected_fragments: tuple[str, ...], runtime: str) -> None:
    projected = _project_markdown(COMMANDS_DIR / f"{command_name}.md", runtime, is_agent=False)

    for fragment in expected_fragments:
        assert fragment in projected, f"{runtime} {command_name} missing {fragment!r}"


@pytest.mark.parametrize("runtime", RUNTIMES)
@pytest.mark.parametrize(("agent_name", "expected_fragments"), tuple(PLAN_AGENT_SURFACES.items()))
def test_runtime_projected_planner_agent_keeps_plan_contract_guidance_visible(
    agent_name: str,
    expected_fragments: tuple[str, ...],
    runtime: str,
) -> None:
    projected = _project_markdown(AGENTS_DIR / f"{agent_name}.md", runtime, is_agent=True)

    _assert_fragments_visible(projected, expected_fragments, label=f"{runtime} {agent_name}")


@pytest.mark.parametrize("runtime", RUNTIMES)
@pytest.mark.parametrize(("agent_name", "expected_fragments"), tuple(RESULT_AGENT_SURFACES.items()))
def test_runtime_projected_agents_keep_contract_results_guidance_visible(
    agent_name: str,
    expected_fragments: tuple[str, ...],
    runtime: str,
) -> None:
    projected = _project_markdown(AGENTS_DIR / f"{agent_name}.md", runtime, is_agent=True)

    _assert_fragments_visible(projected, expected_fragments, label=f"{runtime} {agent_name}")


@pytest.mark.parametrize("runtime", RUNTIMES)
def test_runtime_projected_verifier_surface_keeps_one_wrapper_and_stays_within_budget(runtime: str) -> None:
    projected = _project_markdown(AGENTS_DIR / "gpd-verifier.md", runtime, is_agent=True)
    descriptor = get_runtime_descriptor(runtime)
    line_budget, char_budget = VERIFIER_BUDGET_BY_NATIVE_INCLUDE_SUPPORT[descriptor.native_include_support]

    assert projected.count("## Agent Requirements") == 1
    assert projected.index("## Agent Requirements") < projected.index("## Bootstrap Discipline")
    if descriptor.native_include_support:
        assert projected.count("verification-report.md") == 1
        assert projected.count("contract-results-schema.md") == 1
        assert projected.count("canonical-schema-discipline.md") == 1
    else:
        assert projected.count("# Verification Report Template") == 1
        assert projected.count("# Contract Results Schema") == 1
        assert projected.count("# Canonical Schema Discipline") == 1
    assert len(projected.splitlines()) <= line_budget
    assert len(projected) <= char_budget


@pytest.mark.parametrize("runtime", RUNTIMES)
@pytest.mark.parametrize("command_name", SPAWN_CONTRACT_COMMANDS)
def test_runtime_projected_spawn_contract_blocks_match_canonical_command_content(
    command_name: str,
    runtime: str,
) -> None:
    command = registry.get_command(command_name)
    projected = _project_markdown(COMMANDS_DIR / f"{command_name}.md", runtime, is_agent=False)
    descriptor = get_runtime_descriptor(runtime)
    projected_contracts = _extract_spawn_contracts(projected)
    expanded_contracts = _extract_spawn_contracts(command.content)
    source_contracts = _extract_spawn_contracts(_read(COMMANDS_DIR / f"{command_name}.md"))

    if descriptor.native_include_support:
        assert projected_contracts == source_contracts
        if not source_contracts and expanded_contracts:
            assert "@/runtime/get-physics-done/workflows/" in projected
        return

    assert projected_contracts == expanded_contracts
