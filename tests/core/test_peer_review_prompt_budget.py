"""Prompt budget regression tests for the `peer-review` startup surface."""

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


def test_peer_review_command_stays_thin_and_only_eagerly_loads_the_workflow() -> None:
    command_text = (COMMANDS_DIR / "peer-review.md").read_text(encoding="utf-8")
    metrics = measure_prompt_surface(
        COMMANDS_DIR / "peer-review.md",
        src_root=SOURCE_ROOT,
        path_prefix=PATH_PREFIX,
    )
    workflow = measure_prompt_surface(
        WORKFLOWS_DIR / "peer-review.md",
        src_root=SOURCE_ROOT,
        path_prefix=PATH_PREFIX,
    )

    assert metrics.raw_include_count == 1
    assert "@{GPD_INSTALL_DIR}/workflows/peer-review.md" in command_text
    assert "@{GPD_INSTALL_DIR}/references/publication/peer-review-panel.md" not in command_text
    assert "@{GPD_INSTALL_DIR}/references/publication/peer-review-reliability.md" not in command_text
    assert "@{GPD_INSTALL_DIR}/templates/paper/publication-manuscript-root-preflight.md" not in command_text
    assert "@{GPD_INSTALL_DIR}/templates/paper/paper-config-schema.md" not in command_text
    assert "@{GPD_INSTALL_DIR}/templates/paper/review-ledger-schema.md" not in command_text
    assert "Follow the included workflow file exactly." in command_text
    assert metrics.expanded_line_count > workflow.expanded_line_count
    assert metrics.expanded_char_count > workflow.expanded_char_count
    assert metrics.expanded_line_count < workflow.expanded_line_count + 250
    assert metrics.expanded_char_count < workflow.expanded_char_count + 15000


def test_peer_review_workflow_defers_stage_authorities_until_the_manifest_stages_need_them() -> None:
    manifest = validate_workflow_stage_manifest_payload(
        json.loads((WORKFLOWS_DIR / "peer-review-stage-manifest.json").read_text(encoding="utf-8")),
        expected_workflow_id="peer-review",
    )

    assert manifest.stage_ids() == (
        "bootstrap",
        "preflight",
        "artifact_discovery",
        "panel_stages",
        "final_adjudication",
        "finalize",
    )

    bootstrap = manifest.stages[0]
    preflight = manifest.stages[1]
    panel_execution = manifest.stages[3]
    final_adjudication = manifest.stages[4]

    assert bootstrap.loaded_authorities == ("workflows/peer-review.md",)
    assert "references/publication/publication-review-round-artifacts.md" in bootstrap.must_not_eager_load
    assert "references/publication/publication-response-artifacts.md" in bootstrap.must_not_eager_load
    assert "references/publication/peer-review-panel.md" in bootstrap.must_not_eager_load
    assert "references/publication/peer-review-reliability.md" in bootstrap.must_not_eager_load
    assert "templates/paper/paper-config-schema.md" in bootstrap.must_not_eager_load
    assert "templates/paper/artifact-manifest-schema.md" in bootstrap.must_not_eager_load
    assert "templates/paper/bibliography-audit-schema.md" in bootstrap.must_not_eager_load
    assert "templates/paper/reproducibility-manifest.md" in bootstrap.must_not_eager_load
    assert "templates/paper/review-ledger-schema.md" in bootstrap.must_not_eager_load
    assert "templates/paper/referee-decision-schema.md" in bootstrap.must_not_eager_load

    assert preflight.loaded_authorities == (
        "workflows/peer-review.md",
        "templates/paper/publication-manuscript-root-preflight.md",
        "references/publication/peer-review-reliability.md",
        "templates/paper/paper-config-schema.md",
        "templates/paper/artifact-manifest-schema.md",
        "templates/paper/bibliography-audit-schema.md",
        "templates/paper/reproducibility-manifest.md",
    )
    assert "workflows/peer-review.md" in manifest.stages[2].loaded_authorities
    assert manifest.stages[2].loaded_authorities == (
        "workflows/peer-review.md",
        "references/publication/publication-review-round-artifacts.md",
        "references/publication/publication-response-artifacts.md",
    )
    assert panel_execution.loaded_authorities == (
        "workflows/peer-review.md",
        "references/publication/peer-review-panel.md",
    )
    assert "workflows/peer-review.md" in final_adjudication.loaded_authorities
    assert "references/publication/peer-review-panel.md" in final_adjudication.loaded_authorities
    assert "templates/paper/review-ledger-schema.md" in final_adjudication.loaded_authorities
    assert "templates/paper/referee-decision-schema.md" in final_adjudication.loaded_authorities
