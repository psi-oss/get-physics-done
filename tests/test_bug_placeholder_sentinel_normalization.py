"""Phase 15 contract for the placeholder / sentinel normalization family."""

from __future__ import annotations

import json
import shutil
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context
from pathlib import Path

from gpd.contracts import ConventionLock
from gpd.core.conventions import KNOWN_CONVENTIONS, convention_check, convention_list, convention_set
from gpd.core.suggest import suggest_next

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures" / "handoff-bundle"


def _copy_fixture_workspace(tmp_path: Path) -> Path:
    source = FIXTURES_DIR / "placeholder-conventions" / "positive" / "workspace"
    destination = tmp_path / "placeholder-conventions-positive"
    shutil.copytree(source, destination)
    return destination


def _expected_missing_conventions(root: Path) -> tuple[str, ...]:
    state = json.loads((root / "GPD" / "state.json").read_text(encoding="utf-8"))
    convention_lock = state["convention_lock"]
    return tuple(key for key in KNOWN_CONVENTIONS if convention_lock.get(key) is None)


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


def _collect_suggestion_surface(root: str) -> dict[str, object]:
    result = suggest_next(Path(root))
    return {
        "actions": [suggestion.action for suggestion in result.suggestions],
        "current_phase": result.context.current_phase,
        "status": result.context.status,
        "missing_conventions": tuple(result.context.missing_conventions),
    }


def test_placeholder_sentinel_normalization_contract(tmp_path: Path) -> None:
    root = _copy_fixture_workspace(tmp_path)
    expected_missing = _expected_missing_conventions(root)
    placeholder_key = expected_missing[0]

    _inject_literal_not_set_placeholders(root)

    lock = _load_convention_lock(root)
    list_result = convention_list(lock)
    check_result = convention_check(lock)

    assert list_result.set_count == 3
    assert list_result.unset_count == 15
    assert list_result.conventions[placeholder_key].is_set is False
    assert list_result.conventions[placeholder_key].value == "not set"

    assert check_result.complete is False
    assert check_result.set_count == 3
    assert check_result.missing_count == len(expected_missing)
    assert tuple(entry.key for entry in check_result.missing) == expected_missing

    set_lock = _load_convention_lock(root)
    set_result = convention_set(set_lock, placeholder_key, "physics")

    assert set_result.updated is True
    assert set_result.previous == "not set"
    assert getattr(set_lock, placeholder_key) == "physics"

    surface = _run_isolated(_collect_suggestion_surface, str(root))

    assert surface["actions"] == ["verify-work", "continue-calculations", "set-conventions", "address-questions"]
    assert surface["current_phase"] == "02"
    assert surface["status"] == "Ready to plan"
    assert surface["missing_conventions"] == expected_missing
