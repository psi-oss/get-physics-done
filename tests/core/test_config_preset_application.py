from __future__ import annotations

import copy
import json
from pathlib import Path

from gpd.core.config import (
    AutonomyMode,
    ModelProfile,
    ResearchMode,
    ReviewCadence,
    load_config,
)
from gpd.core.workflow_presets import (
    apply_workflow_preset_config,
    get_workflow_preset,
    preview_workflow_preset_application,
)
from tests.runtime_test_support import PRIMARY_RUNTIME


def test_preset_bundle_applies_atomic_supported_keys_and_preserves_unrelated_overrides(
    tmp_path: Path,
) -> None:
    preset = get_workflow_preset("publication-manuscript")
    assert preset is not None
    runtime_name = PRIMARY_RUNTIME
    original_overrides = {
        runtime_name: {
            "tier-1": "runtime-tier-1-model",
            "tier-2": "runtime-tier-2-model",
        }
    }

    raw = {
        "model_profile": "review",
        "autonomy": "supervised",
        "research_mode": "balanced",
        "review_cadence": "sparse",
        "commit_docs": False,
        "parallelization": True,
        "checkpoint_after_n_tasks": 7,
        "checkpoint_before_downstream_dependent_tasks": False,
        "max_unattended_minutes_per_plan": 60,
        "max_unattended_minutes_per_wave": 120,
        "model_overrides": original_overrides,
        "execution": {
            "review_cadence": "sparse",
            "checkpoint_after_n_tasks": 7,
            "checkpoint_before_downstream_dependent_tasks": False,
            "max_unattended_minutes_per_plan": 60,
            "max_unattended_minutes_per_wave": 120,
        },
        "planning": {"commit_docs": False},
        "workflow": {"research": False, "plan_checker": False, "verifier": False},
    }

    preview = preview_workflow_preset_application(raw, preset.id)
    applied = preview.updated_config

    assert preview.preset_id == "publication-manuscript"
    assert preview.label == "Publication / manuscript"
    assert preview.applied_keys == (
        "autonomy",
        "research_mode",
        "model_profile",
        "execution.review_cadence",
        "parallelization",
        "planning.commit_docs",
        "workflow.research",
        "workflow.plan_checker",
        "workflow.verifier",
    )
    assert preview.ignored_guidance_only_keys == ("model_cost_posture",)
    assert applied["model_profile"] == "paper-writing"
    assert applied["autonomy"] == "supervised"
    assert applied["research_mode"] == "exploit"
    assert applied["parallelization"] is False
    assert applied["model_overrides"] == original_overrides
    assert applied["checkpoint_after_n_tasks"] == 7
    assert applied["checkpoint_before_downstream_dependent_tasks"] is False
    assert applied["max_unattended_minutes_per_plan"] == 60
    assert applied["max_unattended_minutes_per_wave"] == 120
    assert applied["execution"]["review_cadence"] == ReviewCadence.DENSE.value
    assert applied["commit_docs"] is True
    assert applied["research"] is True
    assert applied["plan_checker"] is True
    assert applied["verifier"] is True
    assert "planning" not in applied
    assert "workflow" not in applied
    assert "review_cadence" not in applied
    assert "model_cost_posture" not in applied

    project = tmp_path / "project"
    (project / "GPD").mkdir(parents=True, exist_ok=True)
    (project / "GPD" / "config.json").write_text(json.dumps(applied), encoding="utf-8")

    cfg = load_config(project)
    assert cfg.model_profile == ModelProfile.PAPER_WRITING
    assert cfg.autonomy == AutonomyMode.SUPERVISED
    assert cfg.research_mode == ResearchMode.EXPLOIT
    assert cfg.review_cadence == ReviewCadence.DENSE
    assert cfg.commit_docs is True
    assert cfg.parallelization is False
    assert cfg.research is True
    assert cfg.plan_checker is True
    assert cfg.verifier is True
    assert cfg.checkpoint_after_n_tasks == 7
    assert cfg.checkpoint_before_downstream_dependent_tasks is False
    assert cfg.max_unattended_minutes_per_plan == 60
    assert cfg.max_unattended_minutes_per_wave == 120
    assert cfg.model_overrides == original_overrides


def test_atomic_application_preserves_existing_runtime_override_and_nested_config_sections(
    tmp_path: Path,
) -> None:
    preset = get_workflow_preset("core-research")
    assert preset is not None
    runtime_name = PRIMARY_RUNTIME
    original_overrides = {
        runtime_name: {
            "tier-1": "runtime-tier-1-model",
            "tier-2": "runtime-tier-2-model",
        }
    }

    raw = {
        "review_cadence": "dense",
        "commit_docs": True,
        "model_overrides": original_overrides,
        "execution": {"review_cadence": "dense"},
        "planning": {"commit_docs": True},
        "workflow": {"research": False, "plan_checker": False, "verifier": False},
    }

    original_raw = copy.deepcopy(raw)
    preview = preview_workflow_preset_application(raw, preset.id)
    applied, preset_id = apply_workflow_preset_config(raw, preset.id)

    assert preset_id == "core-research"
    assert raw == original_raw
    assert applied == preview.updated_config
    assert preview.applied_keys == (
        "autonomy",
        "research_mode",
        "model_profile",
        "execution.review_cadence",
        "parallelization",
        "planning.commit_docs",
        "workflow.research",
        "workflow.plan_checker",
        "workflow.verifier",
    )
    assert applied["execution"]["review_cadence"] == ReviewCadence.DENSE.value
    assert applied["commit_docs"] is True
    assert applied["research"] is True
    assert applied["plan_checker"] is True
    assert applied["verifier"] is True
    assert "planning" not in applied
    assert "workflow" not in applied
    assert applied["model_overrides"] == original_overrides
    assert "review_cadence" not in applied
    assert preview.ignored_guidance_only_keys == ("model_cost_posture",)
