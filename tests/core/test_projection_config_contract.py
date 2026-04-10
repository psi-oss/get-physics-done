"""Phase 16 config/runtime/convention projection oracle."""

from __future__ import annotations

import json
import shutil
from enum import Enum
from pathlib import Path

import pytest

from gpd.contracts import ConventionLock
from gpd.core.config import load_config as load_structured_config
from gpd.core.context import init_progress
from gpd.core.context import load_config as load_context_config
from gpd.core.conventions import KNOWN_CONVENTIONS, convention_check, convention_list, is_bogus_value
from gpd.core.health import check_config, check_convention_lock, resolve_doctor_runtime_readiness
from tests.runtime_test_support import PRIMARY_RUNTIME, runtime_config_dir_name

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures" / "handoff-bundle"

_PROGRESS_CONFIG_FIELDS = (
    "commit_docs",
    "autonomy",
    "review_cadence",
    "research_mode",
)

_EXPECTED_MISSING_CONVENTION_KEYS = tuple(
    key
    for key in KNOWN_CONVENTIONS
    if key not in {"metric_signature", "natural_units", "coordinate_system"}
)


def _copy_fixture_workspace(tmp_path: Path, fixture_relpath: str) -> Path:
    source = FIXTURES_DIR / fixture_relpath / "workspace"
    destination = tmp_path / fixture_relpath.replace("/", "-")
    shutil.copytree(source, destination)
    return destination


def _normalize_model_dump(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    return value


def _normalize_config_projection(config: dict[str, object]) -> dict[str, object]:
    return {key: _normalize_model_dump(value) for key, value in config.items()}


def _expected_config_projection(*, commit_docs: bool) -> dict[str, object]:
    return {
        "model_profile": "review",
        "autonomy": "balanced",
        "review_cadence": "adaptive",
        "research_mode": "balanced",
        "commit_docs": commit_docs,
        "research": True,
        "plan_checker": True,
        "verifier": True,
        "parallelization": True,
        "max_unattended_minutes_per_plan": 45,
        "max_unattended_minutes_per_wave": 90,
        "checkpoint_after_n_tasks": 3,
        "checkpoint_after_first_load_bearing_result": True,
        "checkpoint_before_downstream_dependent_tasks": True,
        "project_usd_budget": None,
        "session_usd_budget": None,
        "branching_strategy": "none",
        "phase_branch_template": "gpd/phase-{phase}-{slug}",
        "milestone_branch_template": "gpd/{milestone}-{slug}",
        "model_overrides": None,
    }


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


def _normalize_placeholder_value(value: object | None) -> object | None:
    return None if is_bogus_value(value) else value


def _config_projection(root: Path) -> dict[str, object]:
    structured_config = _normalize_config_projection(
        load_structured_config(root).model_dump(mode="python")
    )
    context_config = load_context_config(root)
    progress = init_progress(root, includes={"config"}, include_project_reentry=False)
    config_path = root / "GPD" / "config.json"
    readiness = resolve_doctor_runtime_readiness(PRIMARY_RUNTIME, cwd=root)

    return {
        "structured_config": structured_config,
        "context_config": context_config,
        "progress_config": {key: progress[key] for key in _PROGRESS_CONFIG_FIELDS},
        "project_root_source": progress["project_root_source"],
        "project_root": progress["project_root"],
        "config_content": progress["config_content"],
        "config_text": config_path.read_text(encoding="utf-8"),
        "runtime": readiness.runtime,
        "install_scope": readiness.install_scope,
        "target": readiness.target,
        "expected_target": root / runtime_config_dir_name(PRIMARY_RUNTIME),
        "health_status": check_config(root).status,
        "health_details": check_config(root).details,
    }


def _convention_projection(root: Path) -> dict[str, object]:
    lock = _load_convention_lock(root)
    list_result = convention_list(lock)
    check_result = convention_check(lock)
    health_result = check_convention_lock(root)
    fourier_entry = list_result.conventions["fourier_convention"]

    return {
        "set_count": list_result.set_count,
        "unset_count": list_result.unset_count,
        "total": list_result.total,
        "canonical_total": list_result.canonical_total,
        "complete": check_result.complete,
        "missing_count": check_result.missing_count,
        "missing_keys": tuple(entry.key for entry in check_result.missing),
        "health_status": health_result.status,
        "health_set": health_result.details["set"],
        "health_total": health_result.details["total"],
        "raw_fourier_value": fourier_entry.value,
        "raw_fourier_is_set": fourier_entry.is_set,
        "normalized_fourier_value": _normalize_placeholder_value(fourier_entry.value),
    }


def test_config_readback_projection_oracle_normalizes_config_runtime_and_readiness_surface(
    tmp_path: Path,
) -> None:
    root = _copy_fixture_workspace(tmp_path, "config-readback/positive")
    projection = _config_projection(root)
    expected = _expected_config_projection(commit_docs=False)
    context_expected = {key: value for key, value in expected.items() if key != "model_overrides"}

    assert projection["structured_config"] == expected
    assert projection["context_config"] == context_expected
    assert projection["progress_config"] == {key: context_expected[key] for key in _PROGRESS_CONFIG_FIELDS}
    assert projection["project_root_source"] == "workspace"
    assert projection["project_root"] == root.resolve(strict=False).as_posix()
    assert projection["config_content"] == projection["config_text"]
    assert projection["runtime"] == PRIMARY_RUNTIME
    assert projection["install_scope"] == "local"
    assert projection["target"] == projection["expected_target"]
    assert projection["health_status"] == "ok"
    assert projection["health_details"] == {
        "commit_docs": False,
        "model_profile": "review",
        "autonomy": "balanced",
        "research_mode": "balanced",
    }


@pytest.mark.parametrize(
    ("fixture_relpath", "inject_placeholders", "expected_raw_fourier_value"),
    [
        ("placeholder-conventions/positive", False, None),
        ("placeholder-conventions/mutation", True, "not set"),
    ],
)
def test_placeholder_conventions_projection_oracle_treats_literal_not_set_as_unset(
    tmp_path: Path,
    fixture_relpath: str,
    inject_placeholders: bool,
    expected_raw_fourier_value: object | None,
) -> None:
    root = _copy_fixture_workspace(tmp_path, fixture_relpath)
    if inject_placeholders:
        _inject_literal_not_set_placeholders(root)

    projection = _convention_projection(root)

    assert projection["set_count"] == 3
    assert projection["unset_count"] == 15
    assert projection["total"] == 18
    assert projection["canonical_total"] == 18
    assert projection["complete"] is False
    assert projection["missing_count"] == 15
    assert projection["missing_keys"] == _EXPECTED_MISSING_CONVENTION_KEYS
    assert projection["health_status"] == "warn"
    assert projection["health_set"] == 3
    assert projection["health_total"] == 18
    assert projection["raw_fourier_value"] == expected_raw_fourier_value
    assert projection["raw_fourier_is_set"] is False
    assert projection["normalized_fourier_value"] is None
