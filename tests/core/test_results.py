"""Tests for gpd.core.results — intermediate result tracking."""

from __future__ import annotations

import pytest

from gpd.core.errors import DuplicateResultError, ResultError, ResultNotFoundError
from gpd.core.results import (
    IntermediateResult,
    MissingDep,
    ResultDeps,
    result_add,
    result_deps,
    result_list,
    result_update,
    result_verify,
)

# ─── result_add ──────────────────────────────────────────────────────────────


def test_result_add_basic():
    state: dict = {}
    result = result_add(state, equation="E=mc^2", description="Energy-mass", result_id="R-01")
    assert isinstance(result, IntermediateResult)
    assert result.id == "R-01"
    assert result.equation == "E=mc^2"
    assert result.verified is False
    assert len(state["intermediate_results"]) == 1


def test_result_add_auto_id():
    state: dict = {"position": {"current_phase": "3"}}
    result = result_add(state, description="auto-id test")
    assert result.id.startswith("R-03-")


def test_result_add_duplicate_raises():
    state: dict = {}
    result_add(state, result_id="R-01")
    with pytest.raises(DuplicateResultError):
        result_add(state, result_id="R-01")


def test_result_add_empty_id_raises():
    state: dict = {}
    with pytest.raises(ResultError):
        result_add(state, result_id="   ")


def test_result_add_depends_on_string():
    state: dict = {}
    result = result_add(state, result_id="R-02", depends_on="R-01")
    assert result.depends_on == ["R-01"]


def test_result_add_inherits_phase_from_position():
    state: dict = {"position": {"current_phase": "5"}}
    result = result_add(state, result_id="R-05-01")
    assert result.phase == "5"


# ─── result_list ─────────────────────────────────────────────────────────────


def test_result_list_empty():
    state: dict = {}
    assert result_list(state) == []


def test_result_list_all():
    state: dict = {}
    result_add(state, result_id="R-01", phase="1")
    result_add(state, result_id="R-02", phase="2")
    results = result_list(state)
    assert len(results) == 2


def test_result_list_filter_phase():
    state: dict = {}
    result_add(state, result_id="R-01", phase="1")
    result_add(state, result_id="R-02", phase="2")
    results = result_list(state, phase="1")
    assert len(results) == 1
    assert results[0].id == "R-01"


def test_result_list_filter_verified():
    state: dict = {}
    result_add(state, result_id="R-01", verified=True)
    result_add(state, result_id="R-02", verified=False)
    results = result_list(state, verified=True)
    assert len(results) == 1
    assert results[0].id == "R-01"


def test_result_list_filter_unverified():
    state: dict = {}
    result_add(state, result_id="R-01", verified=True)
    result_add(state, result_id="R-02", verified=False)
    results = result_list(state, unverified=True)
    assert len(results) == 1
    assert results[0].id == "R-02"


# ─── result_deps ─────────────────────────────────────────────────────────────


def test_result_deps_no_deps():
    state: dict = {}
    result_add(state, result_id="R-01")
    deps = result_deps(state, "R-01")
    assert isinstance(deps, ResultDeps)
    assert deps.result.id == "R-01"
    assert deps.direct_deps == []
    assert deps.transitive_deps == []


def test_result_deps_with_direct():
    state: dict = {}
    result_add(state, result_id="R-01")
    result_add(state, result_id="R-02", depends_on=["R-01"])
    deps = result_deps(state, "R-02")
    assert len(deps.direct_deps) == 1
    assert deps.direct_deps[0].id == "R-01"


def test_result_deps_with_transitive():
    state: dict = {}
    result_add(state, result_id="R-01")
    result_add(state, result_id="R-02", depends_on=["R-01"])
    result_add(state, result_id="R-03", depends_on=["R-02"])
    deps = result_deps(state, "R-03")
    assert len(deps.direct_deps) == 1
    assert deps.direct_deps[0].id == "R-02"
    assert len(deps.transitive_deps) == 1
    assert deps.transitive_deps[0].id == "R-01"


def test_result_deps_missing_dep():
    state: dict = {}
    result_add(state, result_id="R-02", depends_on=["R-missing"])
    deps = result_deps(state, "R-02")
    assert len(deps.direct_deps) == 1
    assert isinstance(deps.direct_deps[0], MissingDep)
    assert deps.direct_deps[0].id == "R-missing"


def test_result_deps_not_found():
    state: dict = {}
    with pytest.raises(ResultNotFoundError):
        result_deps(state, "R-nonexistent")


# ─── result_verify ───────────────────────────────────────────────────────────


def test_result_verify():
    state: dict = {}
    result_add(state, result_id="R-01")
    result = result_verify(state, "R-01")
    assert result.verified is True
    assert state["intermediate_results"][0]["verified"] is True


def test_result_verify_not_found():
    state: dict = {}
    with pytest.raises(ResultNotFoundError):
        result_verify(state, "R-nonexistent")


# ─── result_update ───────────────────────────────────────────────────────────


def test_result_update_fields():
    state: dict = {}
    result_add(state, result_id="R-01", equation="old")
    fields, result = result_update(state, "R-01", equation="new", description="updated")
    assert "equation" in fields
    assert "description" in fields
    assert result.equation == "new"
    assert result.description == "updated"


def test_result_update_no_recognized_fields():
    state: dict = {}
    result_add(state, result_id="R-01")
    with pytest.raises(ResultError, match="No recognized fields"):
        result_update(state, "R-01", unknown_field="value")


def test_result_update_not_found():
    state: dict = {}
    with pytest.raises(ResultNotFoundError):
        result_update(state, "R-nonexistent", equation="new")
