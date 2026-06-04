"""Prompt contract coverage for the `gpd:ideate` command and workflow."""

from __future__ import annotations

from pathlib import Path

from gpd import registry
from gpd.registry import _parse_spawn_contracts
from tests.assertion_taxonomy_support import assert_prompt_contracts, semantic_concept

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMAND = REPO_ROOT / "src/gpd/commands/ideate.md"
WORKFLOW = REPO_ROOT / "src/gpd/specs/workflows/ideate.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_ideate_command_is_project_aware_thin_and_managed_under_blackboards() -> None:
    command = registry.get_command("ideate")
    text = _read(COMMAND)

    assert command.name == "gpd:ideate"
    assert command.context_mode == "project-aware"
    assert command.help is not None
    assert command.command_policy is not None
    assert command.command_policy.output_policy is not None
    assert command.command_policy.output_policy.output_mode == "managed"
    assert command.command_policy.output_policy.managed_root_kind == "gpd_managed_durable"
    assert command.command_policy.output_policy.default_output_subtree == "GPD/blackboards"
    assert_prompt_contracts(
        text,
        *semantic_concept(
            "ideate wrapper routing",
            required=(
                "gpd --raw validate command-context ideate",
                "@{GPD_INSTALL_DIR}/workflows/ideate.md",
                "GPD/blackboards/",
            ),
        ),
    )

    for tool in ("file_read", "file_write", "file_edit", "shell", "task", "web_search", "web_fetch", "ask_user"):
        assert tool in command.allowed_tools

    for agent in ("gpd-paper-digester", "gpd-ideator", "gpd-ideation-critic"):
        assert agent not in text


def test_ideate_workflow_enforces_source_gate_and_artifact_contract() -> None:
    workflow = _read(WORKFLOW)

    assert_prompt_contracts(
        workflow,
        *semantic_concept(
            "ideate source gate and artifact contract",
            required=(
                "GPD/blackboards/ideate-YYYY-MM-DD-<topic-slug>.md",
                "GPD/blackboards/ideate-YYYY-MM-DD-<topic-slug>-transcript.md",
                "GPD/blackboards/ideate-YYYY-MM-DD-<topic-slug>-report.md",
                "source_manifest:",
                "source_id: SRC-001",
                "status: pending | completed | reused | blocked",
                "Topic rows are useful context",
                "never evidence.",
                "do not produce ranked source-grounded ideas",
                "paper/arXiv/PDF/folder sources",
                "search for candidate papers",
                "Final ranked ideas cite",
                "completed/reused non-topic `SRC-NNN` rows",
            ),
        ),
    )

    assert_prompt_contracts(
        workflow,
        *semantic_concept(
            "ideate report sections",
            required=(
                "## Source Manifest",
                "## Candidate Ideas",
                "## Critic Notes",
                "## Vetoed Ideas",
                "## Ranked Questions",
                "## Ranked Research Questions",
                "## Next Best Experiments Or Calculations",
            ),
        ),
    )


def test_ideate_workflow_defines_depth_modes_and_steering_checkpoints() -> None:
    workflow = _read(WORKFLOW)

    assert_prompt_contracts(
        workflow,
        *semantic_concept(
            "ideate depth and steering options",
            required=(
                "`fast`",
                "`balanced`",
                "`deep`",
                "| `fast` | 1 |",
                "| `balanced` | 2 |",
                "| `deep` | 3 |",
                "after round 1",
                "after rounds 1 and 2",
                "continue, narrow, broaden",
                "add sources",
                "stop early",
            ),
        ),
    )


def test_ideate_workflow_has_three_spawn_contracts_for_new_internal_agents() -> None:
    workflow = _read(WORKFLOW)
    contracts = list(_parse_spawn_contracts(workflow, owner_name="ideate workflow"))

    assert len(contracts) == 3
    for agent in ("gpd-paper-digester", "gpd-ideator", "gpd-ideation-critic"):
        assert f'subagent_type="{agent}"' in workflow
        assert f"First, read {{GPD_AGENTS_DIR}}/{agent}.md for your role and instructions." in workflow

    for contract in contracts:
        assert contract["write_scope"]["mode"] == "scoped_write"
        assert contract["write_scope"]["allowed_paths"] == ["${SESSION_BLACKBOARD}", "${SESSION_TRANSCRIPT}"]
        assert contract["expected_artifacts"] == ["${SESSION_BLACKBOARD}", "${SESSION_TRANSCRIPT}"]
        assert contract["shared_state_policy"] == "return_only"


def test_ideate_report_contract_hides_class_labels_and_requires_source_ids() -> None:
    workflow = _read(WORKFLOW)
    report_step = workflow.split('<step name="write_final_report">', 1)[1].split("</step>", 1)[0]

    assert_prompt_contracts(
        report_step,
        *semantic_concept(
            "ideate report ranking contract",
            required=(
                "source_ids:",
                "score:",
                "novelty: 1-5",
                "physics_importance: 1-5",
                "feasibility: 1-5",
                "next_best_experiment:",
                "possible_issues:",
                "Do not expose the words",
                "`grounded`, `mixed`, or `speculative`",
                "classification labels",
            ),
        ),
    )
    assert_prompt_contracts(
        report_step,
        *semantic_concept("ideate absent report labels", forbidden=("grounding_label:", "classification:")),
    )
