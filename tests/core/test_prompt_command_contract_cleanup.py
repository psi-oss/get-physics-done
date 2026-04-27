"""Focused prompt/command contract cleanup invariants."""

from __future__ import annotations

from pathlib import Path

from tests.core.test_spawn_contracts import _find_single_task

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_DIR = REPO_ROOT / "src/gpd/commands"
WORKFLOWS_DIR = REPO_ROOT / "src/gpd/specs/workflows"
REFERENCES_DIR = REPO_ROOT / "src/gpd/specs/references"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _between(text: str, start_marker: str, end_marker: str) -> str:
    start = text.index(start_marker) + len(start_marker)
    end = text.index(end_marker, start)
    return text[start:end]


def test_discover_managed_outputs_have_write_capability_and_documented_route() -> None:
    command_text = _read(COMMANDS_DIR / "discover.md")
    workflow_text = _read(WORKFLOWS_DIR / "discover.md")

    assert "output_policy:" in command_text
    assert "output_mode: managed" in command_text
    assert "managed_root_kind: gpd_managed_durable" in command_text
    assert "default_output_subtree: GPD/analysis" in command_text
    assert "  - file_write" in command_text
    assert "documented write route" in command_text
    assert "workflow-owned Level 2-3 discovery artifact path" in command_text
    assert "This workflow is the documented write route for `gpd:discover` managed outputs." in workflow_text


def test_owned_project_aware_commands_use_validated_context_instead_of_raw_gpd_includes() -> None:
    command_files = (
        "discover.md",
        "sensitivity-analysis.md",
        "derive-equation.md",
        "review-knowledge.md",
    )

    for command_file in command_files:
        text = _read(COMMANDS_DIR / command_file)
        assert "@GPD/" not in text, command_file
        assert "Validated command-context" in text, command_file


def test_help_reference_stays_static_and_delegates_next_action_routing() -> None:
    help_workflow = _read(WORKFLOWS_DIR / "help.md")
    success_criteria = _between(help_workflow, "<success_criteria>", "</success_criteria>")

    assert "Next action guidance provided based on current project state" not in success_criteria
    assert "Static reference stays project-independent" in success_criteria
    assert (
        "current-state routing is delegated to `gpd:start`, `gpd:progress`, or `gpd:suggest-next`" in success_criteria
    )
    assert "Run `gpd:start` when you need the safest route for this folder" in help_workflow
    assert "Run `gpd:suggest-next` when you only need the next action" in help_workflow


def test_peer_review_file_producing_stage_prompts_carry_spawn_contracts() -> None:
    workflow_path = WORKFLOWS_DIR / "peer-review.md"
    for agent_name in (
        "gpd-review-reader",
        "gpd-review-literature",
        "gpd-review-math",
        "gpd-check-proof",
        "gpd-review-physics",
        "gpd-review-significance",
        "gpd-referee",
    ):
        task = _find_single_task(workflow_path, agent_name)
        assert "<spawn_contract>" in task.text, agent_name
        assert "write_scope:" in task.text, agent_name
        assert "expected_artifacts:" in task.text, agent_name
        assert "shared_state_policy: return_only" in task.text, agent_name


def test_delegation_reference_requires_contract_or_tight_exemption() -> None:
    text = _read(REFERENCES_DIR / "orchestration/agent-delegation.md")

    assert "File-producing or state-sensitive spawned prompts must include this block directly" in text
    assert "adjacent documented exemption" in text
    assert "read-only, produces no artifacts, and returns no shared-state update" in text
