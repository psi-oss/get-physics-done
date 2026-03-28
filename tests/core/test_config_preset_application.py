from __future__ import annotations

import copy
import json
from pathlib import Path

from gpd.core.config import (
    AutonomyMode,
    ModelProfile,
    ResearchMode,
    ReviewCadence,
    apply_config_update,
    load_config,
    supported_config_keys,
)
from gpd.core.workflow_presets import list_workflow_presets


def _apply_preset_bundle(raw: dict[str, object], bundle: dict[str, object]) -> tuple[dict[str, object], list[str]]:
    """Apply a preset bundle as a sequence of atomic config-key updates."""
    updated = copy.deepcopy(raw)
    applied_keys: list[str] = []
    allowed = set(supported_config_keys())

    for key, value in bundle.items():
        if key not in allowed:
            continue
        updated, canonical_key = apply_config_update(updated, key, value)
        applied_keys.append(canonical_key)

    return updated, applied_keys


def test_preset_bundle_applies_atomic_supported_keys_and_preserves_unrelated_overrides(
    tmp_path: Path,
) -> None:
    preset = next(preset for preset in list_workflow_presets() if preset.id == "publication-manuscript")
    runtime_name = "codex"
    original_overrides = {
        runtime_name: {
            "tier-1": "gpt-5.4",
            "tier-2": "gpt-5.1",
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

    bundle = {
        **preset.recommended_config,
        "id": preset.id,
        "label": preset.label,
        "description": preset.description,
        "summary": preset.summary,
        "required_checks": list(preset.required_checks),
        "ready_workflows": list(preset.ready_workflows),
        "degraded_workflows": list(preset.degraded_workflows),
        "blocked_workflows": list(preset.blocked_workflows),
        "requires_extra_tooling": preset.requires_extra_tooling,
    }

    applied, applied_keys = _apply_preset_bundle(raw, bundle)

    assert applied_keys == [
        "autonomy",
        "research_mode",
        "model_profile",
        "review_cadence",
        "parallelization",
        "commit_docs",
        "research",
        "plan_checker",
        "verifier",
    ]
    assert applied["model_profile"] == "paper-writing"
    assert applied["autonomy"] == "balanced"
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
    assert "id" not in applied
    assert "label" not in applied
    assert "model_cost_posture" not in applied

    project = tmp_path / "project"
    (project / "GPD").mkdir(parents=True, exist_ok=True)
    (project / "GPD" / "config.json").write_text(json.dumps(applied), encoding="utf-8")

    cfg = load_config(project)
    assert cfg.model_profile == ModelProfile.PAPER_WRITING
    assert cfg.autonomy == AutonomyMode.BALANCED
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
    preset = next(preset for preset in list_workflow_presets() if preset.id == "core-research")
    runtime_name = "codex"
    original_overrides = {
        runtime_name: {
            "tier-1": "gpt-5.4",
            "tier-2": "gpt-5.1",
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

    bundle = {
        **preset.recommended_config,
        "label": preset.label,
        "summary": preset.summary,
        "requires_extra_tooling": preset.requires_extra_tooling,
    }

    applied, applied_keys = _apply_preset_bundle(raw, bundle)

    assert applied_keys == [
        "autonomy",
        "research_mode",
        "model_profile",
        "review_cadence",
        "parallelization",
        "commit_docs",
        "research",
        "plan_checker",
        "verifier",
    ]
    assert applied["execution"]["review_cadence"] == ReviewCadence.ADAPTIVE.value
    assert applied["commit_docs"] is True
    assert applied["research"] is True
    assert applied["plan_checker"] is True
    assert applied["verifier"] is True
    assert "planning" not in applied
    assert "workflow" not in applied
    assert applied["model_overrides"] == original_overrides
    assert "review_cadence" not in applied
    assert "label" not in applied
    assert "summary" not in applied
