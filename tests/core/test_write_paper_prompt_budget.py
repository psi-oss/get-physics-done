"""Prompt budget regression tests for the `write-paper` startup surface."""

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


def test_write_paper_command_stays_thin_and_only_eagerly_loads_the_workflow() -> None:
    command_text = (COMMANDS_DIR / "write-paper.md").read_text(encoding="utf-8")
    metrics = measure_prompt_surface(
        COMMANDS_DIR / "write-paper.md",
        src_root=SOURCE_ROOT,
        path_prefix=PATH_PREFIX,
    )
    workflow = measure_prompt_surface(
        WORKFLOWS_DIR / "write-paper.md",
        src_root=SOURCE_ROOT,
        path_prefix=PATH_PREFIX,
    )

    assert metrics.raw_include_count == 1
    assert "@{GPD_INSTALL_DIR}/workflows/write-paper.md" in command_text
    assert "@{GPD_INSTALL_DIR}/references/publication/publication-pipeline-modes.md" not in command_text
    assert "@{GPD_INSTALL_DIR}/references/publication/peer-review-panel.md" not in command_text
    assert "@{GPD_INSTALL_DIR}/templates/paper/paper-config-schema.md" not in command_text
    assert "@{GPD_INSTALL_DIR}/templates/paper/review-ledger-schema.md" not in command_text
    assert "required_evidence:" not in command_text
    assert "stage_artifacts:" not in command_text
    assert "GPD/review/CLAIMS{round_suffix}.json" not in command_text
    assert "GPD/review/STAGE-reader{round_suffix}.json" not in command_text
    assert "Follow the included workflow file exactly." in command_text
    assert metrics.expanded_line_count > workflow.expanded_line_count
    assert metrics.expanded_char_count > workflow.expanded_char_count
    assert metrics.expanded_line_count < workflow.expanded_line_count + 250
    assert metrics.expanded_char_count < workflow.expanded_char_count + 15000


def test_write_paper_workflow_defers_stage_authorities_until_the_manifest_stages_need_them() -> None:
    manifest = validate_workflow_stage_manifest_payload(
        json.loads((WORKFLOWS_DIR / "write-paper-stage-manifest.json").read_text(encoding="utf-8")),
        expected_workflow_id="write-paper",
    )

    assert manifest.stage_ids() == (
        "paper_bootstrap",
        "outline_and_scaffold",
        "figure_and_section_authoring",
        "consistency_and_references",
        "publication_review",
    )

    bootstrap = manifest.stages[0]
    outline = manifest.stages[1]
    figure_authoring = manifest.stages[2]
    consistency = manifest.stages[3]
    publication_review = manifest.stages[4]

    assert bootstrap.loaded_authorities == ("workflows/write-paper.md",)
    assert "references/publication/publication-pipeline-modes.md" in bootstrap.must_not_eager_load
    assert "references/publication/peer-review-panel.md" in bootstrap.must_not_eager_load
    assert "templates/paper/paper-config-schema.md" in bootstrap.must_not_eager_load
    assert "templates/paper/artifact-manifest-schema.md" in bootstrap.must_not_eager_load
    assert "templates/paper/review-ledger-schema.md" in bootstrap.must_not_eager_load
    assert "templates/paper/referee-decision-schema.md" in bootstrap.must_not_eager_load

    assert outline.loaded_authorities == (
        "workflows/write-paper.md",
        "references/publication/publication-pipeline-modes.md",
        "templates/paper/paper-config-schema.md",
        "templates/paper/artifact-manifest-schema.md",
    )
    assert figure_authoring.loaded_authorities == (
        "workflows/write-paper.md",
        "references/shared/canonical-schema-discipline.md",
        "templates/paper/figure-tracker.md",
    )
    assert consistency.loaded_authorities == (
        "workflows/write-paper.md",
        "templates/paper/bibliography-audit-schema.md",
        "templates/paper/reproducibility-manifest.md",
    )
    assert publication_review.loaded_authorities == (
        "workflows/write-paper.md",
        "references/publication/peer-review-panel.md",
        "references/publication/peer-review-reliability.md",
        "templates/paper/review-ledger-schema.md",
        "templates/paper/referee-decision-schema.md",
    )
