from __future__ import annotations

import re
from pathlib import Path

from gpd.core.workflow_staging import load_workflow_stage_manifest

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / "src/gpd/specs/workflows"
REFERENCES_DIR = REPO_ROOT / "src/gpd/specs/references/orchestration"
EXECUTION_REFERENCES_DIR = REPO_ROOT / "src/gpd/specs/references/execution"


def test_execute_phase_loads_artifact_surfacing_before_using_it() -> None:
    execute_phase = (WORKFLOWS_DIR / "execute-phase.md").read_text(encoding="utf-8")

    required_reading = "{GPD_INSTALL_DIR}/references/orchestration/artifact-surfacing.md"
    later_reference = "See `references/orchestration/artifact-surfacing.md` for artifact class definitions and review priority rules."

    assert required_reading in execute_phase
    assert execute_phase.index(required_reading) < execute_phase.index(later_reference)
    assert "contract deliverable that is the `subject` of an acceptance test" in execute_phase
    assert "contract deliverable tagged as an acceptance test" not in execute_phase


def test_artifact_surfacing_uses_canonical_paths_and_contract_terms() -> None:
    artifact_surfacing = (REFERENCES_DIR / "artifact-surfacing.md").read_text(encoding="utf-8")

    assert "GPD/phases/01-*/01-01-PLAN.md" in artifact_surfacing
    assert "GPD/review/CLAIMS{round_suffix}.json" in artifact_surfacing
    assert "GPD/review/STAGE-reader{round_suffix}.json" in artifact_surfacing
    assert "GPD/review/STAGE-interestingness{round_suffix}.json" in artifact_surfacing
    assert "GPD/review/REFEREE-DECISION{round_suffix}.json" in artifact_surfacing
    assert "GPD/REFEREE-REPORT{round_suffix}.md" in artifact_surfacing
    assert "GPD/REFEREE-REPORT{round_suffix}.tex" in artifact_surfacing
    assert "GPD/review/REVIEW-LEDGER{round_suffix}.json" in artifact_surfacing
    assert "`.md`, `.tex`, `.json`" in artifact_surfacing
    assert "Contract deliverables that are the `subject` of an acceptance test" in artifact_surfacing
    assert ".gpd/" not in artifact_surfacing


def test_artifact_surfacing_no_longer_promises_dead_progress_or_checkpoint_shapes() -> None:
    artifact_surfacing = (REFERENCES_DIR / "artifact-surfacing.md").read_text(encoding="utf-8")

    assert "/gpd:progress" not in artifact_surfacing
    assert "<artifacts>" not in artifact_surfacing
    assert "checkpoint:human-verify" not in artifact_surfacing


def test_execute_plan_surfaces_github_lifecycle_wiring() -> None:
    execute_plan = (WORKFLOWS_DIR / "execute-plan.md").read_text(encoding="utf-8")
    github_lifecycle = (EXECUTION_REFERENCES_DIR / "github-lifecycle.md").read_text(encoding="utf-8")

    required_reading = "{GPD_INSTALL_DIR}/references/execution/github-lifecycle.md"

    assert required_reading in execute_plan
    assert execute_plan.index(required_reading) < execute_plan.index('<step name="create_checkpoint">')
    assert "<default-branch>" in github_lifecycle
    assert "<remote-name>" in github_lifecycle
    assert "default branch (`main`)" not in github_lifecycle
    assert "git branch --merged main" not in github_lifecycle
    assert "git push origin <tag-name>" not in github_lifecycle
    assert "git push origin --tags" not in github_lifecycle


def test_execute_plan_uses_staged_execution_bootstrap_and_late_context_refreshes() -> None:
    execute_plan = (WORKFLOWS_DIR / "execute-plan.md").read_text(encoding="utf-8")
    manifest_stage_ids = set(load_workflow_stage_manifest("execute-phase").stage_ids())
    requested_stage_ids = set(re.findall(r"--stage\s+(?:\"([^\"]+)\"|([A-Za-z0-9_]+))", execute_plan))
    requested_stage_ids = {match[0] or match[1] for match in requested_stage_ids}

    assert requested_stage_ids
    assert requested_stage_ids <= manifest_stage_ids
    assert "plan_bootstrap" not in requested_stage_ids
    assert "contract_anchor_gate" not in requested_stage_ids
    assert "segment_execution" not in requested_stage_ids
    assert "summary_finalize" not in requested_stage_ids
    assert 'gpd --raw init execute-phase "${phase}" --include state,config' not in execute_plan
    assert "summary-schema loads until the stage that actually consumes them" in execute_plan


def test_execute_phase_loader_does_not_silently_fallback_to_full_init() -> None:
    execute_phase = (WORKFLOWS_DIR / "execute-phase.md").read_text(encoding="utf-8")

    assert "staged gpd initialization failed for stage" in execute_phase
    assert 'if [ $? -ne 0 ] || [ -z "$init_payload" ]; then' in execute_phase
    assert 'if [ $? -eq 0 ] && [ -n "$init_payload" ]; then' not in execute_phase
