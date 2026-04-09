"""Stage-contract regressions for the `map-research` workflow."""

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
    assert "reference_artifacts_content" not in bootstrap.required_init_fields
    assert "references/orchestration/runtime-delegation-note.md" in bootstrap.must_not_eager_load

    assert authoring.loaded_authorities == (
        "workflows/map-research.md",
        "references/orchestration/runtime-delegation-note.md",
    )
    assert "reference_artifacts_content" in authoring.required_init_fields
    assert "GPD/research-map/FORMALISM.md" in authoring.writes_allowed
    assert "GPD/research-map/CONCERNS.md" in authoring.writes_allowed
