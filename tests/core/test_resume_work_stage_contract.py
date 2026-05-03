"""Assertions for the staged `resume-work` contract."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from gpd.cli import app
from gpd.core.workflow_staging import (
    known_init_fields_for_workflow,
    load_workflow_stage_manifest,
    validate_workflow_stage_manifest_payload,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / "src" / "gpd" / "specs" / "workflows"
RUNNER = CliRunner()


def _workflow_step(text: str, step_name: str) -> str:
    start = text.index(f'<step name="{step_name}">')
    end = text.index("</step>", start)
    return text[start:end]


def _workflow_block(text: str, block_name: str) -> str:
    start = text.index(f"<{block_name}>")
    end = text.index(f"</{block_name}>", start)
    return text[start:end]


def test_resume_work_stage_manifest_loads_and_preserves_stage_order() -> None:
    manifest = load_workflow_stage_manifest("resume-work")

    assert manifest.workflow_id == "resume-work"
    assert manifest.stage_ids() == ("resume_bootstrap", "state_restore", "derivation_restore", "resume_routing")

    bootstrap = manifest.get_stage("resume_bootstrap")
    state_restore = manifest.get_stage("state_restore")
    derivation_restore = manifest.get_stage("derivation_restore")
    resume_routing = manifest.get_stage("resume_routing")

    assert bootstrap.loaded_authorities == (
        "workflows/resume-work.md",
        "references/orchestration/resume-vocabulary.md",
    )
    assert "templates/state-json-schema.md" in bootstrap.must_not_eager_load
    assert "reference_artifacts_content" not in bootstrap.required_init_fields
    assert "project_contract_gate" not in bootstrap.required_init_fields
    assert "state_json_backup_exists" in bootstrap.required_init_fields

    assert state_restore.loaded_authorities == ("references/orchestration/state-portability.md",)
    assert "project_contract_gate" in state_restore.required_init_fields
    assert "state_content" in state_restore.required_init_fields
    assert "project_content" in state_restore.required_init_fields
    assert "reference_artifacts_content" not in state_restore.required_init_fields

    assert derivation_restore.loaded_authorities == ("references/orchestration/continuation-format.md",)
    assert derivation_restore.required_init_fields == (
        "derived_convention_lock",
        "derived_convention_lock_count",
        "derived_intermediate_results",
        "derived_intermediate_result_count",
        "derived_approximations",
        "derived_approximation_count",
        "derivation_state_content",
        "continuity_handoff_content",
    )
    assert derivation_restore.writes_allowed == ()
    assert "file_write" not in derivation_restore.allowed_tools

    assert "project_contract_gate" in resume_routing.required_init_fields
    assert "roadmap_content" in resume_routing.required_init_fields
    assert "continuity_handoff_content" in resume_routing.required_init_fields

    known_fields = known_init_fields_for_workflow("resume-work")
    assert known_fields is not None
    assert "state_json_backup_exists" in known_fields


def test_resume_work_stage_manifest_rejects_invalid_field_drift() -> None:
    payload = json.loads((WORKFLOWS_DIR / "resume-work-stage-manifest.json").read_text(encoding="utf-8"))
    payload["stages"][0]["required_init_fields"][0] = "bogus_field"

    with pytest.raises(ValueError, match="unknown field name"):
        validate_workflow_stage_manifest_payload(payload, expected_workflow_id="resume-work")


def test_resume_work_workflow_uses_public_init_resume_for_staged_payloads() -> None:
    text = (WORKFLOWS_DIR / "resume-work.md").read_text(encoding="utf-8")

    assert "INIT=$(gpd --raw init resume --stage resume_bootstrap)" in text
    assert "STATE_RESTORE_INIT=$(gpd --raw init resume --stage state_restore)" in text
    assert "DERIVATION_RESTORE_INIT=$(gpd --raw init resume --stage derivation_restore)" in text
    assert "RESUME_ROUTING_INIT=$(gpd --raw init resume --stage resume_routing)" in text
    assert "gpd --raw init resume-work" not in text
    assert "@{GPD_INSTALL_DIR}/references/orchestration/continuation-format.md" not in text
    assert "@{GPD_INSTALL_DIR}/references/orchestration/state-portability.md" not in text
    assert "@{GPD_INSTALL_DIR}/templates/state-json-schema.md" not in text


def test_resume_work_derivation_restore_does_not_rewrite_derivation_state() -> None:
    text = (WORKFLOWS_DIR / "resume-work.md").read_text(encoding="utf-8")
    section = _workflow_step(text, "restore_persistent_state")

    assert "Do not prune, rewrite, replace, or otherwise modify `GPD/DERIVATION-STATE.md`" in section
    assert "This is a report-only check." in section
    assert "Read and summarize the file as-is" in section
    assert "TMP_FILE" not in section
    assert "Pruning oldest" not in section
    assert "Pruned file" not in section
    forbidden_write_patterns = (
        r">\s*GPD/DERIVATION-STATE\.md",
        r">>\s*GPD/DERIVATION-STATE\.md",
        r">\s*\"\$TMP_FILE\"",
        r"\bcp\b[^\n]*GPD/DERIVATION-STATE\.md",
        r"\bmv\b[^\n]*GPD/DERIVATION-STATE\.md",
        r"\bsed\s+-i\b[^\n]*GPD/DERIVATION-STATE\.md",
    )
    for pattern in forbidden_write_patterns:
        assert re.search(pattern, section) is None


def test_resume_work_transition_reference_uses_installed_workflow_path() -> None:
    text = (WORKFLOWS_DIR / "resume-work.md").read_text(encoding="utf-8")

    assert "- **Transition** -> `{GPD_INSTALL_DIR}/workflows/transition.md`" in text
    assert "- **Transition** -> ./transition.md" not in text


def test_resume_work_quick_resume_refuses_auto_selected_recent_projects() -> None:
    text = (WORKFLOWS_DIR / "resume-work.md").read_text(encoding="utf-8")
    initialize = _workflow_step(text, "initialize")
    quick_resume = _workflow_block(text, "quick_resume")

    ambiguity_gate = "**If `project_reentry_requires_selection` is true"
    auto_recent_gate = "**If `project_root_auto_selected` is true"
    new_project_gate = "**If `planning_exists` is false and no recent-project selection is required:**"

    assert ambiguity_gate in initialize
    assert auto_recent_gate in initialize
    assert new_project_gate in initialize
    assert initialize.index(ambiguity_gate) < initialize.index(new_project_gate)
    assert initialize.index(auto_recent_gate) < initialize.index(new_project_gate)
    assert "quick resume is disabled" in quick_resume
    assert "do not continue automatically" in quick_resume


def test_init_resume_invokes_resume_context(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str | None] = []

    def fake_init_resume(cwd: Path, *, stage: str | None = None) -> dict[str, object]:
        calls.append(stage)
        return {"stage": stage}

    monkeypatch.setattr("gpd.core.context.init_resume", fake_init_resume)

    result = RUNNER.invoke(app, ["--raw", "init", "resume", "--stage", "resume_bootstrap"])

    assert result.exit_code == 0
    assert calls == ["resume_bootstrap"]
    assert json.loads(result.output)["stage"] == "resume_bootstrap"


def test_init_resume_work_alias_delegates_to_resume() -> None:
    expected = RUNNER.invoke(app, ["--raw", "init", "resume", "--stage", "resume_bootstrap"])
    result = RUNNER.invoke(app, ["--raw", "init", "resume-work", "--stage", "resume_bootstrap"])

    assert expected.exit_code == 0
    assert result.exit_code == 0
    assert json.loads(result.output) == json.loads(expected.output)
