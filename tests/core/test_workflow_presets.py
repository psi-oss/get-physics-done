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
from tests.latex_test_support import latex_capability_payload as _latex_capability


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


def test_workflow_preset_readiness_degrades_publication_family_when_arxiv_submission_support_is_missing() -> None:
    readiness = resolve_workflow_preset_readiness(
        base_ready=True,
        latex_capability=_latex_capability(latexmk_available=False, kpsewhich_available=False),
    )
    statuses = {preset["id"]: preset["status"] for preset in readiness["presets"]}
    publication = next(preset for preset in readiness["presets"] if preset["id"] == "publication-manuscript")

    assert readiness["ready"] == 3
    assert readiness["degraded"] == 2
    assert readiness["blocked"] == 0
    assert readiness["latex_capability"]["compiler"] == "pdflatex"
    assert readiness["latex_capability"]["readiness_state"] == "ready"
    assert readiness["latex_capability"]["message"] == "pdflatex found (TeX Live): /usr/bin/pdflatex"
    assert readiness["latex_capability"]["bibliography_support_available"] is True
    assert readiness["latex_capability"]["paper_build_ready"] is True
    assert readiness["latex_capability"]["arxiv_submission_ready"] is False
    assert readiness["latex_capability"]["full_toolchain_available"] is False
    assert statuses["core-research"] == "ready"
    assert statuses["theory"] == "ready"
    assert statuses["numerics"] == "ready"
    assert statuses["publication-manuscript"] == "degraded"
    assert statuses["full-research"] == "degraded"
    assert publication["ready_workflows"] == ["write-paper", "peer-review", "paper-build"]
    assert publication["degraded_workflows"] == []
    assert publication["blocked_workflows"] == ["arxiv-submission"]
    assert any("latexmk is missing" in warning for warning in publication["warnings"])
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
    assert readiness["latex_capability"]["bibliography_support_available"] is False
    assert readiness["latex_capability"]["paper_build_ready"] is True
    assert readiness["latex_capability"]["arxiv_submission_ready"] is False
    assert readiness["latex_capability"]["full_toolchain_available"] is False
    assert statuses["publication-manuscript"] == "degraded"
    assert statuses["full-research"] == "degraded"
    assert publication["ready_workflows"] == ["write-paper", "peer-review"]
    assert publication["degraded_workflows"] == ["paper-build", "arxiv-submission"]
    assert publication["blocked_workflows"] == []
    assert any("BibTeX support is missing" in warning for warning in publication["warnings"])


def test_workflow_preset_readiness_degrades_peer_review_pdf_intake_when_pdftotext_is_missing() -> None:
    readiness = resolve_workflow_preset_readiness(
        base_ready=True,
        latex_capability=_latex_capability(pdftotext_available=False),
    )
    statuses = {preset["id"]: preset["status"] for preset in readiness["presets"]}
    publication = next(preset for preset in readiness["presets"] if preset["id"] == "publication-manuscript")

    assert readiness["ready"] == 3
    assert readiness["degraded"] == 2
    assert readiness["blocked"] == 0
    assert readiness["latex_capability"]["paper_build_ready"] is True
    assert readiness["latex_capability"]["arxiv_submission_ready"] is True
    assert readiness["latex_capability"]["pdf_review_ready"] is False
    assert readiness["latex_capability"]["full_toolchain_available"] is False
    assert statuses["publication-manuscript"] == "degraded"
    assert statuses["full-research"] == "degraded"
    assert publication["ready_workflows"] == ["write-paper", "paper-build", "arxiv-submission"]
    assert publication["degraded_workflows"] == ["peer-review"]
    assert publication["blocked_workflows"] == []
    assert any("pdftotext is missing" in warning for warning in publication["warnings"])


def test_workflow_preset_readiness_ignores_malformed_pdftotext_and_contradictory_state_overrides() -> None:
    readiness = resolve_workflow_preset_readiness(
        base_ready=True,
        latex_capability={
            "compiler_available": False,
            "pdftotext_available": "yes",
            "full_toolchain_available": True,
            "readiness_state": "ready",
        },
    )
    publication = next(preset for preset in readiness["presets"] if preset["id"] == "publication-manuscript")

    assert readiness["latex_capability"]["available"] is False
    assert readiness["latex_capability"]["compiler_available"] is False
    assert readiness["latex_capability"]["pdftotext_available"] is None
    assert readiness["latex_capability"]["pdf_review_ready"] is False
    assert readiness["latex_capability"]["paper_build_ready"] is False
    assert readiness["latex_capability"]["full_toolchain_available"] is False
    assert readiness["latex_capability"]["readiness_state"] == "blocked"
    assert publication["status"] == "degraded"
    assert publication["ready_workflows"] == []


def test_workflow_preset_readiness_does_not_backfill_legacy_paper_build_flag_to_ready() -> None:
    readiness = resolve_workflow_preset_readiness(base_ready=True, latex_capability={"paper_build_ready": True})
    publication = next(preset for preset in readiness["presets"] if preset["id"] == "publication-manuscript")

    assert readiness["ready"] == 3
    assert readiness["degraded"] == 2
    assert readiness["latex_capability"]["paper_build_ready"] is False
    assert readiness["latex_capability"]["arxiv_submission_ready"] is False
    assert readiness["latex_capability"]["full_toolchain_available"] is False
    assert readiness["latex_capability"]["bibliography_support_available"] is False
    assert publication["status"] == "degraded"
    assert publication["ready_workflows"] == []
    assert publication["blocked_workflows"] == ["paper-build", "arxiv-submission"]


def test_workflow_preset_readiness_rejects_string_booleans_in_latex_capability() -> None:
    readiness = resolve_workflow_preset_readiness(
        base_ready=True,
        latex_capability={
            "compiler_available": "false",
            "bibtex_available": "false",
            "latexmk_available": "false",
            "kpsewhich_available": "false",
        },
    )
    publication = next(preset for preset in readiness["presets"] if preset["id"] == "publication-manuscript")

    assert readiness["latex_capability"]["available"] is False
    assert readiness["latex_capability"]["compiler_available"] is False
    assert readiness["latex_capability"]["bibtex_available"] is None
    assert readiness["latex_capability"]["latexmk_available"] is None
    assert readiness["latex_capability"]["kpsewhich_available"] is None
    assert readiness["latex_capability"]["bibliography_support_available"] is False
    assert readiness["latex_capability"]["paper_build_ready"] is False
    assert readiness["latex_capability"]["arxiv_submission_ready"] is False
    assert readiness["latex_capability"]["full_toolchain_available"] is False
    assert publication["status"] == "degraded"
    assert any("No LaTeX compiler detected" in warning for warning in publication["warnings"])


@pytest.mark.parametrize("latex_capability", [True, {"legacy_available": True}])
def test_workflow_preset_readiness_ignores_legacy_compiler_availability_shapes(
    latex_capability: object,
) -> None:
    readiness = resolve_workflow_preset_readiness(base_ready=True, latex_capability=latex_capability)
    publication = next(preset for preset in readiness["presets"] if preset["id"] == "publication-manuscript")

    assert readiness["latex_capability"]["available"] is False
    assert readiness["latex_capability"]["compiler_available"] is False
    assert readiness["latex_capability"]["paper_build_ready"] is False
    assert readiness["latex_capability"]["arxiv_submission_ready"] is False
    assert publication["status"] == "degraded"


def test_workflow_preset_readiness_normalizes_unknown_bibtex_without_none_full_toolchain() -> None:
    readiness = resolve_workflow_preset_readiness(
        base_ready=True,
        latex_capability={
            "compiler": "pdflatex",
            "compiler_available": True,
            "bibtex_available": None,
            "latexmk_available": True,
            "kpsewhich_available": True,
            "readiness_state": "degraded",
            "message": "pdflatex found, but bibliography tooling is unknown.",
            "warnings": ["bibtex probe unavailable"],
        },
    )

    assert readiness["latex_capability"]["full_toolchain_available"] is False
    assert readiness["latex_capability"]["paper_build_ready"] is True
    assert readiness["latex_capability"]["arxiv_submission_ready"] is False
    assert readiness["latex_capability"]["bibtex_available"] is None
    assert readiness["latex_capability"]["bibliography_support_available"] is False


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
    assert readiness["latex_capability"]["full_toolchain_available"] is False


def test_workflow_preset_readiness_surfaces_explicit_full_toolchain_flag_when_all_helpers_are_present() -> None:
    readiness = resolve_workflow_preset_readiness(base_ready=True, latex_capability=_latex_capability())

    assert readiness["latex_capability"]["available"] is True
    assert readiness["latex_capability"]["compiler_available"] is True
    assert readiness["latex_capability"]["full_toolchain_available"] is True
    assert readiness["latex_capability"]["paper_build_ready"] is True
    assert readiness["latex_capability"]["arxiv_submission_ready"] is True


def test_workflow_preset_readiness_blocks_everything_when_base_runtime_is_not_ready() -> None:
    readiness = resolve_workflow_preset_readiness(base_ready=False, latex_capability=_latex_capability())

    assert readiness["ready"] == 0
    assert readiness["degraded"] == 0
    assert readiness["blocked"] == 5
    assert all(preset["status"] == "blocked" for preset in readiness["presets"])
