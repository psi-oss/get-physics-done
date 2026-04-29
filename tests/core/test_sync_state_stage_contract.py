"""Assertions for the staged `sync-state` contract."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gpd.core.workflow_staging import load_workflow_stage_manifest, validate_workflow_stage_manifest_payload

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / "src" / "gpd" / "specs" / "workflows"


def test_sync_state_stage_manifest_loads_and_preserves_stage_order() -> None:
    manifest = load_workflow_stage_manifest("sync-state")

    assert manifest.workflow_id == "sync-state"
    assert manifest.stage_ids() == (
        "sync_bootstrap",
        "single_source_recovery",
        "conflict_analysis",
        "reconcile_and_validate",
    )

    bootstrap = manifest.get_stage("sync_bootstrap")
    recovery = manifest.get_stage("single_source_recovery")
    conflict = manifest.get_stage("conflict_analysis")
    reconcile = manifest.get_stage("reconcile_and_validate")

    assert bootstrap.loaded_authorities == ("workflows/sync-state.md",)
    assert bootstrap.required_init_fields == (
        "project_root",
        "state_md_exists",
        "state_json_exists",
        "state_json_backup_exists",
        "state_load_source",
        "state_integrity_issues",
        "platform",
    )
    assert "templates/state-json-schema.md" in bootstrap.must_not_eager_load

    assert recovery.loaded_authorities == ("templates/state-json-schema.md",)
    assert "state_md_content" in recovery.required_init_fields
    assert "state_json_content" in recovery.required_init_fields
    assert "project_contract_gate" in recovery.required_init_fields

    assert conflict.loaded_authorities == ("templates/state-json-schema.md",)
    assert "project_contract_validation" in conflict.required_init_fields
    assert "state_json_backup_content" in conflict.required_init_fields

    assert reconcile.loaded_authorities == ("templates/state-json-schema.md",)
    assert reconcile.writes_allowed == (
        "GPD/STATE.md",
        "GPD/state.json",
        "GPD/state.json.bak",
    )


def test_sync_state_stage_manifest_rejects_invalid_field_drift() -> None:
    payload = json.loads((WORKFLOWS_DIR / "sync-state-stage-manifest.json").read_text(encoding="utf-8"))
    payload["stages"][0]["required_init_fields"][0] = "bogus_field"

    with pytest.raises(ValueError, match="unknown field name"):
        validate_workflow_stage_manifest_payload(payload, expected_workflow_id="sync-state")


def test_sync_state_workflow_uses_staged_fields_instead_of_manual_state_probing() -> None:
    text = (WORKFLOWS_DIR / "sync-state.md").read_text(encoding="utf-8")

    assert "SYNC_BOOTSTRAP_INIT=$(gpd --raw init sync-state --stage sync_bootstrap)" in text
    assert "SINGLE_SOURCE_RECOVERY_INIT=$(gpd --raw init sync-state --stage single_source_recovery)" in text
    assert "CONFLICT_ANALYSIS_INIT=$(gpd --raw init sync-state --stage conflict_analysis)" in text
    assert "RECONCILE_INIT=$(gpd --raw init sync-state --stage reconcile_and_validate)" in text
    assert 'PROJECT_ROOT=$(echo "$SYNC_BOOTSTRAP_INIT" | gpd json get .project_root)' in text
    assert 'cwd = Path(".")' not in text
    assert 'gpd --raw --cwd "$PROJECT_ROOT" state repair-sync' in text
    assert 'gpd --raw --cwd "$PROJECT_ROOT" state validate' in text
    assert "gpd --raw state validate" not in text
    assert "json.loads" not in text
    assert "save_state_markdown" not in text
    assert "save_state_json" not in text
    assert "--prefer" not in text
    assert "Do not re-probe `GPD/STATE.md`, `GPD/state.json`, or `GPD/state.json.bak` by hand during routing." in text
    assert "Do not re-read the mirrored files by hand for comparison." in text
    assert "@{GPD_INSTALL_DIR}/templates/state-json-schema.md" not in text
    assert "MD_EXISTS=$(test -f" not in text
    assert "JSON_EXISTS=$(test -f" not in text
    assert "cat GPD/STATE.md" not in text
    assert "cat GPD/state.json" not in text
