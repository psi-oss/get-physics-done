from __future__ import annotations

import pytest

from gpd.core.workflow_presets import (
    apply_workflow_preset_config,
    get_workflow_preset,
    get_workflow_preset_config_bundle,
    list_workflow_presets,
    resolve_workflow_preset_readiness,
)


def test_workflow_preset_inventory_is_stable_and_non_persisted() -> None:
    presets = list_workflow_presets()

    assert [preset.id for preset in presets] == [
        "core-research",
        "theory",
        "numerics",
        "publication-manuscript",
        "full-research",
    ]
    assert get_workflow_preset("publication-manuscript") is not None
    assert get_workflow_preset("missing") is None
    assert all("model_cost_posture" in preset.recommended_config for preset in presets)
    assert get_workflow_preset_config_bundle("missing") is None


def test_workflow_preset_config_bundle_contains_only_writable_config_keys() -> None:
    bundle = get_workflow_preset_config_bundle("publication-manuscript")
    assert bundle is not None

    assert "model_cost_posture" not in bundle
    assert bundle == {
        "autonomy": "balanced",
        "research_mode": "exploit",
        "model_profile": "paper-writing",
        "execution.review_cadence": "dense",
        "parallelization": False,
        "planning.commit_docs": True,
        "workflow.research": True,
        "workflow.plan_checker": True,
        "workflow.verifier": True,
    }


def test_apply_workflow_preset_config_is_atomic_and_does_not_mutate_input() -> None:
    raw_config = {
        "autonomy": "supervised",
        "research_mode": "explore",
        "model_profile": "review",
        "parallelization": True,
        "workflow": {"research": False},
    }

    updated, preset_id = apply_workflow_preset_config(raw_config, "core-research")

    assert preset_id == "core-research"
    assert raw_config == {
        "autonomy": "supervised",
        "research_mode": "explore",
        "model_profile": "review",
        "parallelization": True,
        "workflow": {"research": False},
    }
    assert updated["autonomy"] == "balanced"
    assert updated["research_mode"] == "balanced"
    assert updated["model_profile"] == "review"
    assert updated["parallelization"] is True
    assert updated["commit_docs"] is True
    assert updated["research"] is True
    assert updated["plan_checker"] is True
    assert updated["verifier"] is True


def test_apply_workflow_preset_config_rejects_unknown_preset() -> None:
    with pytest.raises(ValueError, match="Unknown workflow preset"):
        apply_workflow_preset_config({}, "missing")


def test_publication_and_full_presets_are_the_only_verified_tooling_presets() -> None:
    presets = {preset.id: preset for preset in list_workflow_presets()}

    assert presets["publication-manuscript"].required_checks == ("LaTeX Toolchain",)
    assert presets["full-research"].required_checks == ("LaTeX Toolchain",)
    assert presets["theory"].required_checks == ()
    assert presets["numerics"].required_checks == ()


def test_workflow_preset_readiness_degrades_only_publication_family_without_latex() -> None:
    readiness = resolve_workflow_preset_readiness(base_ready=True, latex_available=False)
    statuses = {preset["id"]: preset["status"] for preset in readiness["presets"]}

    assert readiness["ready"] == 3
    assert readiness["degraded"] == 2
    assert readiness["blocked"] == 0
    assert statuses["core-research"] == "ready"
    assert statuses["theory"] == "ready"
    assert statuses["numerics"] == "ready"
    assert statuses["publication-manuscript"] == "degraded"
    assert statuses["full-research"] == "degraded"


def test_workflow_preset_readiness_blocks_everything_when_base_runtime_is_not_ready() -> None:
    readiness = resolve_workflow_preset_readiness(base_ready=False, latex_available=True)

    assert readiness["ready"] == 0
    assert readiness["degraded"] == 0
    assert readiness["blocked"] == 5
    assert all(preset["status"] == "blocked" for preset in readiness["presets"])
