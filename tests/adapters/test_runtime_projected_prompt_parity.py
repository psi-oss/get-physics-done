"""Runtime-projected prompt parity for contract-heavy command and agent surfaces."""

from __future__ import annotations

from pathlib import Path

import pytest

from gpd.adapters.install_utils import project_markdown_for_runtime
from gpd.adapters.runtime_catalog import iter_runtime_descriptors
from gpd.core.model_visible_text import (
    REVIEW_CONTRACT_REQUIRED_STATES,
    command_visibility_note,
    review_contract_visibility_note,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_DIR = REPO_ROOT / "src/gpd/commands"
AGENTS_DIR = REPO_ROOT / "src/gpd/agents"

RUNTIMES = tuple(descriptor.runtime_name for descriptor in iter_runtime_descriptors())
COMMAND_SURFACES = {
    "plan-phase": (command_visibility_note(),),
    "new-project": (command_visibility_note(),),
    "execute-phase": (command_visibility_note(),),
    "verify-work": (
        command_visibility_note(),
        review_contract_visibility_note(),
        f"required_state: {REVIEW_CONTRACT_REQUIRED_STATES[0]}",
    ),
}
PLAN_AGENT_SURFACES = {
    "gpd-planner": (
        "tool_requirements",
        "must_surface",
        "`wolfram` and `command`",
    ),
}
RESULT_AGENT_SURFACES = {
    "gpd-verifier": (
        "contract_results",
        "comparison_verdicts",
        "suggested_contract_checks",
        "completed_actions",
        "missing_actions",
        "inconclusive` / `tension`",
    ),
    "gpd-executor": (
        "plan_contract_ref",
        "contract_results",
        "comparison_verdicts",
    ),
}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


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
