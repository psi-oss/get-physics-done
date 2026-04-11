"""Fast inventory checks for command/workflow stage-manifest wiring."""

from __future__ import annotations

from pathlib import Path

from gpd import registry
from gpd.core.workflow_staging import (
    WORKFLOW_STAGE_MANIFEST_DIR,
    WORKFLOW_STAGE_MANIFEST_SUFFIX,
    known_init_fields_for_workflow,
    load_workflow_stage_manifest,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_COMMANDS_DIR = _REPO_ROOT / "src" / "gpd" / "commands"
_WORKFLOWS_DIR = _REPO_ROOT / "src" / "gpd" / "specs" / "workflows"


def _manifest_workflow_ids() -> set[str]:
    return {
        path.name.removesuffix(WORKFLOW_STAGE_MANIFEST_SUFFIX)
        for path in WORKFLOW_STAGE_MANIFEST_DIR.glob(f"*{WORKFLOW_STAGE_MANIFEST_SUFFIX}")
    }


def test_stage_manifest_inventory_has_command_and_workflow_peers() -> None:
    manifest_inventory = _manifest_workflow_ids()
    command_inventory = {path.stem for path in _COMMANDS_DIR.glob("*.md")}
    workflow_inventory = {path.stem for path in _WORKFLOWS_DIR.glob("*.md")}

    assert manifest_inventory
    assert manifest_inventory <= command_inventory
    assert manifest_inventory <= workflow_inventory


def test_registry_staged_loading_inventory_matches_manifest_inventory() -> None:
    manifest_inventory = _manifest_workflow_ids()

    registry.invalidate_cache()
    staged_inventory = {
        command_name
        for command_name in registry.list_commands()
        if registry.get_command(command_name).staged_loading is not None
    }

    assert staged_inventory == manifest_inventory


def test_stage_manifest_inventory_loads_with_known_init_fields() -> None:
    for workflow_id in sorted(_manifest_workflow_ids()):
        known_init_fields = known_init_fields_for_workflow(workflow_id)
        manifest = load_workflow_stage_manifest(workflow_id)

        assert known_init_fields is not None
        assert manifest.workflow_id == workflow_id
        assert manifest.stage_ids()
