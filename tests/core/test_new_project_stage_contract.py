"""Regression tests for the staged `new-project` contract."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests import new_project_stage_contract_support as stage_contract_module

REPO_ROOT = Path(__file__).resolve().parents[2]
NEW_PROJECT_COMMAND_PATH = REPO_ROOT / "src" / "gpd" / "commands" / "new-project.md"


def test_new_project_stage_contract_loads_and_preserves_stage_order() -> None:
    contract = stage_contract_module.load_new_project_stage_contract()

    assert contract.schema_version == 1
    assert contract.workflow_id == "new-project"
    assert contract.stage_ids() == ("scope_intake", "scope_approval", "post_scope")
    assert contract.stages[0].order == 1
    assert contract.stages[1].order == 2
    assert contract.stages[2].order == 3
    assert contract.stages[0].mode_paths == ("workflows/new-project.md",)
    assert "project_contract_gate" in contract.stages[0].required_init_fields
    assert "needs_research_map" in contract.stages[0].required_init_fields
    assert "references/research/questioning.md" in contract.stages[0].must_not_eager_load
    assert "templates/project-contract-schema.md" in contract.stages[0].must_not_eager_load
    assert "templates/project-contract-grounding-linkage.md" in contract.stages[0].must_not_eager_load
    assert contract.stages[1].loaded_authorities == (
        "templates/project-contract-schema.md",
        "templates/project-contract-grounding-linkage.md",
    )
    assert contract.stages[1].writes_allowed == ("GPD/state.json",)
    assert contract.stages[2].loaded_authorities == (
        "references/research/questioning.md",
        "references/ui/ui-brand.md",
        "templates/project.md",
        "templates/requirements.md",
    )
    assert contract.stages[2].writes_allowed == (
        "GPD/PROJECT.md",
        "GPD/REQUIREMENTS.md",
        "GPD/ROADMAP.md",
        "GPD/STATE.md",
        "GPD/config.json",
    )


def test_new_project_stage_contract_loader_is_cached() -> None:
    first = stage_contract_module.load_new_project_stage_contract()
    second = stage_contract_module.load_new_project_stage_contract()

    assert first is second


def test_new_project_command_mentions_approval_time_grounding_linkage() -> None:
    command_text = NEW_PROJECT_COMMAND_PATH.read_text(encoding="utf-8")

    assert "project-contract-schema.md" in command_text
    assert "project-contract-grounding-linkage.md" in command_text


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
