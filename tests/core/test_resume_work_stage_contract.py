"""Assertions for the staged `resume-work` contract."""

from __future__ import annotations

import json
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


def test_resume_work_workflow_uses_compatible_init_alias_for_staged_payloads() -> None:
    text = (WORKFLOWS_DIR / "resume-work.md").read_text(encoding="utf-8")

    assert "INIT=$(gpd --raw init resume-work --stage resume_bootstrap)" in text
    assert "STATE_RESTORE_INIT=$(gpd --raw init resume-work --stage state_restore)" in text
    assert "DERIVATION_RESTORE_INIT=$(gpd --raw init resume-work --stage derivation_restore)" in text
    assert "RESUME_ROUTING_INIT=$(gpd --raw init resume-work --stage resume_routing)" in text
    assert "gpd init resume" not in text
    assert "@{GPD_INSTALL_DIR}/references/orchestration/continuation-format.md" not in text
    assert "@{GPD_INSTALL_DIR}/references/orchestration/state-portability.md" not in text
    assert "@{GPD_INSTALL_DIR}/templates/state-json-schema.md" not in text


def test_init_resume_work_hidden_alias_invokes_resume_context(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str | None] = []

    def fake_init_resume(cwd: Path, *, stage: str | None = None) -> dict[str, object]:
        calls.append(stage)
        return {"stage": stage}

    monkeypatch.setattr("gpd.core.context.init_resume", fake_init_resume)

    result = RUNNER.invoke(app, ["--raw", "init", "resume-work", "--stage", "resume_bootstrap"])

    assert result.exit_code == 0
    assert calls == ["resume_bootstrap"]
    assert json.loads(result.output)["stage"] == "resume_bootstrap"
