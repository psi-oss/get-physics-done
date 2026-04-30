"""Stage-contract assertions for the `map-research` workflow."""

from __future__ import annotations

import json
from pathlib import Path

from gpd.core.workflow_staging import validate_workflow_stage_manifest_payload

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / "src" / "gpd" / "specs" / "workflows"


def test_map_research_stage_manifest_defers_heavy_context_and_delegation_until_authoring() -> None:
    manifest = validate_workflow_stage_manifest_payload(
        json.loads((WORKFLOWS_DIR / "map-research-stage-manifest.json").read_text(encoding="utf-8")),
        expected_workflow_id="map-research",
    )

    assert manifest.stage_ids() == (
        "map_bootstrap",
        "mapper_authoring",
    )

    bootstrap = manifest.stage("map_bootstrap")
    authoring = manifest.stage("mapper_authoring")

    assert bootstrap.loaded_authorities == ("workflows/map-research.md",)
    assert "project_root" in bootstrap.required_init_fields
    assert "project_root_source" in bootstrap.required_init_fields
    assert "project_root_auto_selected" in bootstrap.required_init_fields
    assert "workspace_root" in bootstrap.required_init_fields
    assert "research_map_dir_absolute" in bootstrap.required_init_fields
    assert "reference_artifacts_content" not in bootstrap.required_init_fields
    assert "references/orchestration/runtime-delegation-note.md" in bootstrap.must_not_eager_load
    assert bootstrap.writes_allowed == (
        "GPD/research-map",
        "GPD/research-map.archive-*",
    )

    assert authoring.loaded_authorities == (
        "workflows/map-research.md",
        "references/orchestration/runtime-delegation-note.md",
    )
    assert "reference_artifacts_content" in authoring.required_init_fields
    assert "GPD/research-map/FORMALISM.md" in authoring.writes_allowed
    assert "GPD/research-map/CONCERNS.md" in authoring.writes_allowed


def test_map_research_workflow_uses_project_rooted_map_targets_for_side_effects() -> None:
    text = (WORKFLOWS_DIR / "map-research.md").read_text(encoding="utf-8")

    assert 'PROJECT_ROOT=$(echo "$BOOTSTRAP_INIT" | gpd json get .project_root --default "")' in text
    assert (
        'RESEARCH_MAP_DIR_ABS=$(echo "$BOOTSTRAP_INIT" | gpd json get .research_map_dir_absolute --default "")' in text
    )
    assert 'mkdir -p "$RESEARCH_MAP_DIR_ABS"' in text
    assert 'mv "$RESEARCH_MAP_DIR_ABS" "$RESEARCH_MAP_ARCHIVE_DIR"' in text
    assert 'ls -la "$RESEARCH_MAP_DIR_ABS/"' in text
    assert 'gpd --cwd "$PROJECT_ROOT" commit "docs: map existing research project" --files "$RESEARCH_MAP_DIR"' in text
    assert "option_id: refresh_archive" in text
    assert "option_id: update_selected" in text
    assert "option_id: skip_existing" in text
    assert "route by exact `option_id`, not option number or label" in text
    assert "Record the selected list as `UPDATE_SELECTED_DOCS`" in text
    assert "Spawn only mapper slices that own at least one selected document" in text
    assert "Keep unselected map documents byte-for-byte unchanged" in text
    assert "If any unselected file changes, fail closed" in text
    assert "Delete GPD/research-map" not in text
    assert "mkdir -p GPD/research-map" not in text
    assert "rm -rf GPD/research-map" not in text
