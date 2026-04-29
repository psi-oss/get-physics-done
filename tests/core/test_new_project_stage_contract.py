"""Assertions for the staged `new-project` contract."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests import new_project_stage_contract_support as stage_contract_module

REPO_ROOT = Path(__file__).resolve().parents[2]
NEW_PROJECT_COMMAND_PATH = REPO_ROOT / "src" / "gpd" / "commands" / "new-project.md"
NEW_PROJECT_WORKFLOW_PATH = REPO_ROOT / "src" / "gpd" / "specs" / "workflows" / "new-project.md"


def _read_new_project_command() -> str:
    return NEW_PROJECT_COMMAND_PATH.read_text(encoding="utf-8")


def _read_new_project_workflow() -> str:
    return NEW_PROJECT_WORKFLOW_PATH.read_text(encoding="utf-8")


def _tagged_block(text: str, tag: str) -> str:
    start = text.index(f"<{tag}>")
    end = text.index(f"</{tag}>", start)
    return text[start:end]


def _tagged_blocks(text: str, tag: str) -> list[str]:
    blocks: list[str] = []
    cursor = 0
    while True:
        start = text.find(f"<{tag}>", cursor)
        if start == -1:
            return blocks
        end = text.index(f"</{tag}>", start)
        blocks.append(text[start:end])
        cursor = end + len(f"</{tag}>")


def test_new_project_stage_contract_loads_and_preserves_stage_order() -> None:
    contract = stage_contract_module.load_new_project_stage_contract()

    assert contract.schema_version == 1
    assert contract.workflow_id == "new-project"
    assert contract.stage_ids() == ("scope_intake", "scope_approval", "post_scope")
    assert contract.stages[0].order == 1
    assert contract.stages[1].order == 2
    assert contract.stages[2].order == 3
    assert contract.stages[0].mode_paths == ("workflows/new-project.md",)
    assert contract.stages[0].loaded_authorities == ("workflows/new-project.md",)
    assert contract.stages[0].required_init_fields == (
        "researcher_model",
        "synthesizer_model",
        "commit_docs",
        "autonomy",
        "research_mode",
        "project_exists",
        "state_exists",
        "roadmap_exists",
        "recoverable_project_exists",
        "partial_project_exists",
        "project_recovery_status",
        "has_research_map",
        "planning_exists",
        "has_research_files",
        "research_file_samples",
        "has_project_manifest",
        "needs_research_map",
        "has_git",
        "platform",
        "project_contract",
        "project_contract_gate",
        "project_contract_load_info",
        "project_contract_validation",
    )
    assert "project_contract_gate" in contract.stages[0].required_init_fields
    assert "needs_research_map" in contract.stages[0].required_init_fields
    assert contract.stages[0].conditional_authorities[0].when == "full_questioning_path"
    assert contract.stages[0].conditional_authorities[0].authorities == ("references/research/questioning.md",)
    assert "references/research/questioning.md" in contract.stages[0].must_not_eager_load
    assert "references/shared/canonical-schema-discipline.md" in contract.stages[0].must_not_eager_load
    assert "templates/project-contract-schema.md" in contract.stages[0].must_not_eager_load
    assert "templates/project-contract-grounding-linkage.md" in contract.stages[0].must_not_eager_load
    assert contract.stages[0].produced_state == ("intake routing state", "scoping-contract gate state")
    assert contract.stages[0].checkpoints == (
        "detect existing workspace state",
        "surface the first scoping question",
        "preserve contract gate visibility without assuming approval-stage authority",
    )
    assert contract.stages[0].writes_allowed == ()
    assert contract.stages[1].required_init_fields == (
        "project_contract",
        "project_contract_gate",
        "project_contract_load_info",
        "project_contract_validation",
    )
    assert contract.stages[1].loaded_authorities == (
        "templates/project-contract-schema.md",
        "templates/project-contract-grounding-linkage.md",
        "references/shared/canonical-schema-discipline.md",
    )
    assert contract.stages[1].conditional_authorities == ()
    assert contract.stages[1].produced_state == ("approved project contract", "approval-state persistence")
    assert contract.stages[1].checkpoints == (
        "approval gate has passed",
        "project contract is ready for persistence",
    )
    assert contract.stages[1].writes_allowed == (
        "GPD/state.json",
        "GPD/STATE.md",
        "GPD/state.json.bak",
        "GPD/state.json.lock",
    )
    assert contract.stages[2].required_init_fields == (
        "researcher_model",
        "synthesizer_model",
        "roadmapper_model",
        "commit_docs",
        "autonomy",
        "research_mode",
        "project_contract",
        "project_contract_gate",
        "project_contract_load_info",
        "project_contract_validation",
    )
    assert contract.stages[2].loaded_authorities == (
        "references/ui/ui-brand.md",
        "templates/project.md",
        "templates/requirements.md",
        "templates/state.md",
    )
    assert contract.stages[2].conditional_authorities == ()
    assert contract.stages[2].writes_allowed == (
        "GPD/PROJECT.md",
        "GPD/REQUIREMENTS.md",
        "GPD/ROADMAP.md",
        "GPD/STATE.md",
        "GPD/state.json",
        "GPD/state.json.bak",
        "GPD/state.json.lock",
        "GPD/config.json",
        "GPD/CONVENTIONS.md",
        "GPD/init-progress.json",
        "GPD/literature/PRIOR-WORK.md",
        "GPD/literature/METHODS.md",
        "GPD/literature/COMPUTATIONAL.md",
        "GPD/literature/PITFALLS.md",
        "GPD/literature/SUMMARY.md",
    )
    assert "references/research/questioning.md" not in contract.stages[2].loaded_authorities
    assert contract.stages[2].produced_state == (
        "project artifacts",
        "workflow preferences",
        "downstream stage handoff",
    )
    assert contract.stages[2].checkpoints == (
        "approval gate has passed",
        "stage-aware deferred reads are now allowed",
    )


def test_new_project_post_scope_loads_templates_for_every_template_written_artifact() -> None:
    contract = stage_contract_module.load_new_project_stage_contract()
    post_scope = contract.stages[2]
    command_text = _read_new_project_command()
    required_template_by_output = {
        "GPD/PROJECT.md": "templates/project.md",
        "GPD/REQUIREMENTS.md": "templates/requirements.md",
        "GPD/STATE.md": "templates/state.md",
    }

    for output_path, template_path in required_template_by_output.items():
        assert output_path in post_scope.writes_allowed
        assert template_path in post_scope.loaded_authorities
        assert f"Read {{GPD_INSTALL_DIR}}/{template_path} only when writing `{output_path}`." in command_text


def test_new_project_stage_contract_loader_is_cached() -> None:
    first = stage_contract_module.load_new_project_stage_contract()
    second = stage_contract_module.load_new_project_stage_contract()

    assert first is second


def test_new_project_command_mentions_approval_time_grounding_linkage() -> None:
    command_text = _read_new_project_command()

    assert "project-contract-schema.md" in command_text
    assert "project-contract-grounding-linkage.md" in command_text


def test_new_project_defines_auto_minimal_conflict_as_prewrite_gate() -> None:
    command_text = _read_new_project_command()
    workflow_text = _read_new_project_workflow()

    expected_error = "Error: --auto and --minimal cannot be combined."
    assert expected_error in command_text
    assert expected_error in workflow_text
    assert "This conflict stop happens before git initialization" in command_text
    assert "Do not initialize git, create `GPD/`, write state" in workflow_text
    assert workflow_text.index(expected_error) < workflow_text.index("## 1. Setup")


def test_new_project_recovery_gate_precedes_generic_project_hard_stops() -> None:
    workflow_text = _read_new_project_workflow()

    progress_gate = workflow_text.index(
        "**Check for previous initialization attempt before generic project/recovery hard-stops:**"
    )
    project_stop = workflow_text.index("**If `project_exists` is true:**")
    recoverable_stop = workflow_text.index("**If `recoverable_project_exists` is true")

    assert progress_gate < project_stop
    assert progress_gate < recoverable_stop
    assert "Do not delete it automatically" in workflow_text
    assert "If start fresh: delete `init-progress.json` only after the user explicitly chooses" in workflow_text


def test_new_project_defers_git_until_first_mutation_gate() -> None:
    workflow_text = _read_new_project_workflow()

    setup_start = workflow_text.index("## 1. Setup")
    existing_work_start = workflow_text.index("## 2. Existing Work Offer")
    first_mutation_gate = workflow_text.index("Before persistence, cross the **First Mutation Gate**")
    git_init = workflow_text.index("```bash\ngit init\n```")
    state_persistence = workflow_text.index("gpd state set-project-contract -")
    minimal_parse_failure = workflow_text.index("Error: Could not extract research context from the provided file.")
    auto_doc_failure = workflow_text.index("Error: --auto requires a research document via @ reference.")

    assert "```bash\ngit init\n```" not in workflow_text[setup_start:existing_work_start]
    assert auto_doc_failure < git_init
    assert minimal_parse_failure < git_init
    assert first_mutation_gate < git_init < state_persistence


def test_new_project_notation_contracts_split_checkpoint_from_artifact_write() -> None:
    workflow_text = _read_new_project_workflow()
    auto_contract = next(
        block for block in _tagged_blocks(workflow_text, "spawn_contract") if "GPD/CONVENTIONS.md" in block
    )
    interactive_contract = _tagged_block(workflow_text, "spawn_contract_interactive")

    assert "GPD/CONVENTIONS.md" in auto_contract
    assert "expected_artifacts: []" in interactive_contract
    assert "status: checkpoint" in interactive_contract
    assert "GPD/CONVENTIONS.md" not in interactive_contract
    assert "CHECKPOINT REACHED" not in workflow_text
    assert "gpd_return.status: checkpoint" in workflow_text


def test_new_project_notation_spawn_model_and_recovery_contract_are_conditional() -> None:
    workflow_text = _read_new_project_workflow()

    assert 'model="{NOTATION_MODEL}"' not in workflow_text
    assert 'model="$NOTATION_MODEL"' in workflow_text
    assert 'task(prompt=NOTATION_PROMPT, subagent_type="gpd-notation-coordinator", readonly=false' in workflow_text
    assert "write the returned content in the main context" not in workflow_text
    assert "re-execute the convention-establishment task in the main context" not in workflow_text
    assert "spawn one fresh `gpd-notation-coordinator` continuation" in workflow_text
    assert "fail closed" in workflow_text


def test_new_project_stage_contract_rejects_unknown_top_level_keys() -> None:
    payload = {
        "schema_version": 1,
        "workflow_id": "new-project",
        "stages": [],
        "unexpected": True,
    }

    with pytest.raises(ValueError, match="unexpected key"):
        stage_contract_module.validate_new_project_stage_contract_payload(payload)


def test_new_project_stage_contract_rejects_unknown_stage_keys() -> None:
    payload = json.loads(stage_contract_module.NEW_PROJECT_STAGE_MANIFEST_PATH.read_text(encoding="utf-8"))
    payload["stages"][0]["unexpected"] = "boom"

    with pytest.raises(ValueError, match="unexpected key"):
        stage_contract_module.validate_new_project_stage_contract_payload(payload)


def test_new_project_stage_contract_rejects_invalid_ordering(tmp_path: Path) -> None:
    payload = json.loads(stage_contract_module.NEW_PROJECT_STAGE_MANIFEST_PATH.read_text(encoding="utf-8"))
    payload["stages"][0]["order"] = 2
    payload["stages"][1]["order"] = 1
    path = tmp_path / "new-project-stage-manifest.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="stage order values"):
        stage_contract_module.load_new_project_stage_contract_from_path(path)


@pytest.mark.parametrize(
    ("mutator", "expected"),
    [
        (
            lambda payload: payload["stages"][0]["loaded_authorities"].__setitem__(0, "references/missing.md"),
            "markdown file",
        ),
        (lambda payload: payload["stages"][0]["allowed_tools"].__setitem__(0, "network"), "unknown tool name"),
        (
            lambda payload: payload["stages"][1]["required_init_fields"].__setitem__(0, "bogus_field"),
            "unknown field name",
        ),
        (
            lambda payload: payload["stages"][0]["must_not_eager_load"].append("workflows/new-project.md"),
            "overlap with must_not_eager_load",
        ),
        (
            lambda payload: payload["stages"][0]["writes_allowed"].append("../state.json"),
            "normalized relative POSIX path",
        ),
    ],
)
def test_new_project_stage_contract_rejects_validation_drift(mutator, expected: str) -> None:
    payload = json.loads(stage_contract_module.NEW_PROJECT_STAGE_MANIFEST_PATH.read_text(encoding="utf-8"))
    mutator(payload)

    with pytest.raises(ValueError, match=expected):
        stage_contract_module.validate_new_project_stage_contract_payload(payload)
