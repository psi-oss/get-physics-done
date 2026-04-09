"""Stage-manifest regressions for the `literature-review` startup surface."""

from __future__ import annotations

import json
from pathlib import Path

from gpd.core.workflow_staging import validate_workflow_stage_manifest_payload
from tests.prompt_metrics_support import measure_prompt_surface

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_DIR = REPO_ROOT / "src" / "gpd" / "commands"
WORKFLOWS_DIR = REPO_ROOT / "src" / "gpd" / "specs" / "workflows"
SOURCE_ROOT = REPO_ROOT / "src" / "gpd"
PATH_PREFIX = "/runtime/"


def test_literature_review_stage_manifest_defers_reference_artifacts_and_delegation_authorities() -> None:
    manifest = validate_workflow_stage_manifest_payload(
        json.loads((WORKFLOWS_DIR / "literature-review-stage-manifest.json").read_text(encoding="utf-8")),
        expected_workflow_id="literature-review",
    )

    assert manifest.stage_ids() == (
        "review_bootstrap",
        "scope_locked",
        "review_handoff",
        "completion_gate",
    )

    bootstrap = manifest.stage("review_bootstrap")
    scope_locked = manifest.stage("scope_locked")
    review_handoff = manifest.stage("review_handoff")
    completion_gate = manifest.stage("completion_gate")

    assert bootstrap.loaded_authorities == ("workflows/literature-review.md",)
    assert "reference_artifact_files" not in bootstrap.required_init_fields
    assert "reference_artifacts_content" not in bootstrap.required_init_fields
    assert "references/orchestration/runtime-delegation-note.md" in bootstrap.must_not_eager_load

    assert "reference_artifact_files" in scope_locked.required_init_fields
    assert "reference_artifacts_content" in scope_locked.required_init_fields
    assert scope_locked.loaded_authorities == ("workflows/literature-review.md",)

    assert review_handoff.loaded_authorities == (
        "workflows/literature-review.md",
        "references/orchestration/runtime-delegation-note.md",
    )
    assert "GPD/literature/slug-REVIEW.md" in review_handoff.writes_allowed
    assert "GPD/literature/slug-CITATION-SOURCES.json" in review_handoff.writes_allowed

    assert completion_gate.loaded_authorities == ("workflows/literature-review.md",)
    assert completion_gate.writes_allowed == ()


def test_literature_review_command_prompt_budget_stays_close_to_the_workflow_surface() -> None:
    command_text = (COMMANDS_DIR / "literature-review.md").read_text(encoding="utf-8")
    metrics = measure_prompt_surface(
        COMMANDS_DIR / "literature-review.md",
        src_root=SOURCE_ROOT,
        path_prefix=PATH_PREFIX,
    )
    workflow = measure_prompt_surface(
        WORKFLOWS_DIR / "literature-review.md",
        src_root=SOURCE_ROOT,
        path_prefix=PATH_PREFIX,
    )

    assert metrics.raw_include_count == 1
    assert "@{GPD_INSTALL_DIR}/workflows/literature-review.md" in command_text
    assert "@{GPD_INSTALL_DIR}/references/orchestration/runtime-delegation-note.md" not in command_text
    assert metrics.expanded_line_count > workflow.expanded_line_count
    assert metrics.expanded_char_count > workflow.expanded_char_count
    assert metrics.expanded_line_count < workflow.expanded_line_count + 250
    assert metrics.expanded_char_count < workflow.expanded_char_count + 15000
