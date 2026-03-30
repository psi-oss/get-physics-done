from __future__ import annotations

import pytest

from gpd.core.workflow_presets import (
    WorkflowPresetConfigChange,
    apply_workflow_preset_config,
    get_workflow_preset,
    get_workflow_preset_config_bundle,
    list_workflow_presets,
    preview_workflow_preset_application,
    resolve_workflow_preset_readiness,
)


def _latex_capability(**overrides: object) -> dict[str, object]:
    capability = {
        "compiler_available": True,
        "compiler_path": "/usr/bin/pdflatex",
        "distribution": "TeX Live",
        "bibtex_available": True,
        "latexmk_available": True,
        "kpsewhich_available": True,
        "warnings": [],
    }
    capability.update(overrides)
    return capability


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


def test_preview_workflow_preset_application_reports_change_contract() -> None:
    raw_config = {
        "autonomy": "balanced",
        "research_mode": "explore",
        "model_profile": "review",
        "parallelization": False,
        "execution": {"review_cadence": "dense"},
        "planning": {"commit_docs": True},
        "workflow": {"research": True, "plan_checker": False, "verifier": False},
    }

    result = preview_workflow_preset_application(raw_config, "core-research")

    assert result.preset_id == "core-research"
    assert result.label == "Core research"
    assert result.applied_keys == (
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
    assert result.ignored_guidance_only_keys == ("model_cost_posture",)
    assert result.changed_keys == (
        "research_mode",
        "execution.review_cadence",
        "parallelization",
        "workflow.plan_checker",
        "workflow.verifier",
    )
    assert result.changes == (
        WorkflowPresetConfigChange(key="research_mode", before="explore", after="balanced"),
        WorkflowPresetConfigChange(key="execution.review_cadence", before="dense", after="adaptive"),
        WorkflowPresetConfigChange(key="parallelization", before=False, after=True),
        WorkflowPresetConfigChange(key="workflow.plan_checker", before=False, after=True),
        WorkflowPresetConfigChange(key="workflow.verifier", before=False, after=True),
    )
    assert result.unchanged_keys == (
        "autonomy",
        "model_profile",
        "planning.commit_docs",
        "workflow.research",
    )
    assert raw_config == {
        "autonomy": "balanced",
        "research_mode": "explore",
        "model_profile": "review",
        "parallelization": False,
        "execution": {"review_cadence": "dense"},
        "planning": {"commit_docs": True},
        "workflow": {"research": True, "plan_checker": False, "verifier": False},
    }
    assert result.updated_config["autonomy"] == "balanced"
    assert result.updated_config["research_mode"] == "balanced"
    assert result.updated_config["model_profile"] == "review"
    assert result.updated_config["parallelization"] is True
    assert result.updated_config["commit_docs"] is True
    assert result.updated_config["research"] is True
    assert result.updated_config["plan_checker"] is True
    assert result.updated_config["verifier"] is True
    assert "planning" not in result.updated_config
    assert "workflow" not in result.updated_config


def test_preview_workflow_preset_application_uses_effective_alias_and_default_values() -> None:
    raw_config = {
        "autonomy": "balanced",
        "research_mode": "balanced",
        "model_profile": "review",
        "parallelization": True,
        "review_cadence": "adaptive",
        "workflow": {"research": True, "plan_checker": True, "verifier": True},
    }

    result = preview_workflow_preset_application(raw_config, "core-research")

    assert result.changed_keys == ()
    assert result.unchanged_keys == (
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
    assert result.updated_config["execution"]["review_cadence"] == "adaptive"
    assert result.updated_config["commit_docs"] is True


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


def test_workflow_preset_readiness_is_ready_when_compiler_and_bibtex_are_present() -> None:
    readiness = resolve_workflow_preset_readiness(
        base_ready=True,
        latex_capability=_latex_capability(latexmk_available=False, kpsewhich_available=False),
    )
    statuses = {preset["id"]: preset["status"] for preset in readiness["presets"]}
    publication = next(preset for preset in readiness["presets"] if preset["id"] == "publication-manuscript")

    assert readiness["ready"] == 5
    assert readiness["degraded"] == 0
    assert readiness["blocked"] == 0
    assert readiness["latex_capability"]["paper_build_ready"] is True
    assert readiness["latex_capability"]["arxiv_submission_ready"] is True
    assert statuses["core-research"] == "ready"
    assert statuses["theory"] == "ready"
    assert statuses["numerics"] == "ready"
    assert statuses["publication-manuscript"] == "ready"
    assert statuses["full-research"] == "ready"
    assert "latexmk is missing" in publication["warnings"][0]
    assert any("kpsewhich is missing" in warning for warning in publication["warnings"])


def test_workflow_preset_readiness_degrades_publication_family_when_bibtex_is_missing() -> None:
    readiness = resolve_workflow_preset_readiness(
        base_ready=True,
        latex_capability=_latex_capability(bibtex_available=False),
    )
    statuses = {preset["id"]: preset["status"] for preset in readiness["presets"]}
    publication = next(preset for preset in readiness["presets"] if preset["id"] == "publication-manuscript")

    assert readiness["ready"] == 3
    assert readiness["degraded"] == 2
    assert readiness["blocked"] == 0
    assert readiness["latex_capability"]["paper_build_ready"] is False
    assert readiness["latex_capability"]["arxiv_submission_ready"] is False
    assert statuses["publication-manuscript"] == "degraded"
    assert statuses["full-research"] == "degraded"
    assert publication["ready_workflows"] == []
    assert publication["degraded_workflows"] == ["write-paper", "peer-review"]
    assert publication["blocked_workflows"] == ["paper-build", "arxiv-submission"]
    assert any("BibTeX support is missing" in warning for warning in publication["warnings"])


def test_workflow_preset_readiness_degrades_publication_family_when_compiler_is_missing() -> None:
    readiness = resolve_workflow_preset_readiness(
        base_ready=True,
        latex_capability=_latex_capability(
            compiler_available=False,
            compiler_path=None,
            distribution=None,
            bibtex_available=False,
            latexmk_available=False,
            kpsewhich_available=False,
        ),
    )
    publication = next(preset for preset in readiness["presets"] if preset["id"] == "publication-manuscript")

    assert readiness["ready"] == 3
    assert readiness["degraded"] == 2
    assert readiness["blocked"] == 0
    assert publication["status"] == "degraded"
    assert publication["ready_workflows"] == []
    assert publication["blocked_workflows"] == ["paper-build", "arxiv-submission"]
    assert any("No LaTeX compiler detected" in warning for warning in publication["warnings"])
    assert any("latexmk is missing" in warning for warning in publication["warnings"])
    assert any("kpsewhich is missing" in warning for warning in publication["warnings"])


def test_workflow_preset_readiness_blocks_everything_when_base_runtime_is_not_ready() -> None:
    readiness = resolve_workflow_preset_readiness(base_ready=False, latex_capability=_latex_capability())

    assert readiness["ready"] == 0
    assert readiness["degraded"] == 0
    assert readiness["blocked"] == 5
    assert all(preset["status"] == "blocked" for preset in readiness["presets"])
