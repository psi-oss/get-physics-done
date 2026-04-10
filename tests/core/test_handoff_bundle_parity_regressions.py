"""Fixture-backed regressions for handoff-bundle context and suggestion parity."""

from __future__ import annotations

import json
import shutil
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context
from pathlib import Path

from gpd.contracts import ConventionLock
from gpd.core.conventions import convention_check, convention_list
from gpd.core.suggest import suggest_next

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures" / "handoff-bundle"


def _copy_fixture_workspace(
    tmp_path: Path,
    fixture_slug: str,
    variant: str = "positive",
    *,
    suffix: str = "",
) -> Path:
    source = FIXTURES_DIR / fixture_slug / variant / "workspace"
    destination = tmp_path / f"{fixture_slug}-{variant}{suffix}"
    shutil.copytree(source, destination)
    return destination


def _inject_literal_not_set_placeholders(root: Path) -> None:
    state_path = root / "GPD" / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    convention_lock = state["convention_lock"]
    for key, value in list(convention_lock.items()):
        if value is None:
            convention_lock[key] = "not set"
    state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def _load_convention_lock(root: Path) -> ConventionLock:
    state = json.loads((root / "GPD" / "state.json").read_text(encoding="utf-8"))
    return ConventionLock.model_validate(state["convention_lock"])


def _run_isolated(func, *args):
    with ProcessPoolExecutor(max_workers=1, mp_context=get_context("spawn")) as executor:
        return executor.submit(func, *args).result()


def _collect_convention_surface(root: str) -> dict[str, object]:
    lock = _load_convention_lock(Path(root))
    list_result = convention_list(lock)
    check_result = convention_check(lock)
    return {
        "set_count": list_result.set_count,
        "unset_count": list_result.unset_count,
        "fourier_is_set": list_result.conventions["fourier_convention"].is_set,
        "fourier_value": list_result.conventions["fourier_convention"].value,
        "missing_count": check_result.missing_count,
        "missing_keys": [entry.key for entry in check_result.missing],
    }


def _collect_suggestion_surface(root: str) -> dict[str, object]:
    result = suggest_next(Path(root))
    return {
        "actions": [suggestion.action for suggestion in result.suggestions],
        "current_phase": result.context.current_phase,
        "status": result.context.status,
        "completed_phases": result.context.completed_phases,
        "progress_percent": result.context.progress_percent,
        "missing_conventions": tuple(result.context.missing_conventions),
    }


def test_resume_recent_noise_positive_workspace_reports_material_convention_counts(tmp_path: Path) -> None:
    root = _copy_fixture_workspace(tmp_path, "resume-recent-noise")

    surface = _run_isolated(_collect_convention_surface, str(root))

    assert surface["set_count"] == 3
    assert surface["unset_count"] == 15
    assert surface["missing_count"] == 15


def test_resume_recent_noise_positive_workspace_keeps_resume_suggestion_surface_stable(
    tmp_path: Path,
) -> None:
    root = _copy_fixture_workspace(tmp_path, "resume-recent-noise")

    surface = _run_isolated(_collect_suggestion_surface, str(root))

    assert surface["actions"] == ["execute-phase", "verify-results", "set-conventions", "address-questions"]
    assert surface["current_phase"] == "01"
    assert surface["status"] == "Ready to execute"
    assert len(surface["missing_conventions"]) == 15
    assert surface["missing_conventions"][0] == "fourier_convention"


def test_placeholder_conventions_positive_workspace_treats_literal_not_set_values_as_unset(
    tmp_path: Path,
) -> None:
    root = _copy_fixture_workspace(tmp_path, "placeholder-conventions")
    _inject_literal_not_set_placeholders(root)

    surface = _run_isolated(_collect_convention_surface, str(root))

    assert surface["set_count"] == 3
    assert surface["unset_count"] == 15
    assert surface["fourier_is_set"] is False
    assert surface["fourier_value"] == "not set"

    assert surface["missing_count"] == 15
    assert surface["missing_keys"] == [
        "fourier_convention",
        "gauge_choice",
        "regularization_scheme",
        "renormalization_scheme",
        "spin_basis",
        "state_normalization",
        "coupling_convention",
        "index_positioning",
        "time_ordering",
        "commutation_convention",
        "levi_civita_sign",
        "generator_normalization",
        "covariant_derivative_sign",
        "gamma_matrix_convention",
        "creation_annihilation_order",
    ]


def test_placeholder_conventions_positive_workspace_surfaces_missing_convention_gap(
    tmp_path: Path,
) -> None:
    root = _copy_fixture_workspace(tmp_path, "placeholder-conventions")
    _inject_literal_not_set_placeholders(root)

    surface = _run_isolated(_collect_suggestion_surface, str(root))

    assert surface["actions"] == ["verify-work", "continue-calculations", "set-conventions", "address-questions"]
    assert surface["current_phase"] == "02"
    assert surface["status"] == "Ready to plan"
    assert surface["progress_percent"] == 25
    assert len(surface["missing_conventions"]) == 15
    assert surface["missing_conventions"][0] == "fourier_convention"
    assert "set-conventions" in surface["actions"]


def test_bridge_vs_cli_positive_workspace_reports_material_convention_counts(tmp_path: Path) -> None:
    root = _copy_fixture_workspace(tmp_path, "bridge-vs-cli")

    surface = _run_isolated(_collect_convention_surface, str(root))

    assert surface["set_count"] == 3
    assert surface["unset_count"] == 15
    assert surface["missing_count"] == 15


def test_bridge_vs_cli_positive_workspace_keeps_complete_suggestion_surface(tmp_path: Path) -> None:
    root = _copy_fixture_workspace(tmp_path, "bridge-vs-cli")

    surface = _run_isolated(_collect_suggestion_surface, str(root))

    assert surface["actions"] == ["continue-calculations", "verify-results", "set-conventions", "address-questions"]
    assert surface["current_phase"] == "01"
    assert surface["status"] == "Complete"
    assert surface["completed_phases"] == 1
    assert surface["progress_percent"] == 100
    assert len(surface["missing_conventions"]) == 15
    assert surface["missing_conventions"][0] == "fourier_convention"
