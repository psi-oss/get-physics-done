"""Tests for result_downstream — reverse dependency tracing."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from gpd.core.errors import ResultNotFoundError
from gpd.core.results import (
    IntermediateResult,
    ResultDownstream,
    result_add,
    result_downstream,
)

# ─── result_downstream ──────────────────────────────────────────────────────


def test_result_downstream_no_dependents():
    state: dict = {}
    result_add(state, result_id="R-01", equation="E=mc^2")
    downstream = result_downstream(state, "R-01")
    assert isinstance(downstream, ResultDownstream)
    assert downstream.result.id == "R-01"
    assert downstream.direct_dependents == []
    assert downstream.transitive_dependents == []


def test_result_downstream_direct_dependents_only():
    state: dict = {}
    result_add(state, result_id="R-01")
    result_add(state, result_id="R-02", depends_on=["R-01"])
    result_add(state, result_id="R-03", depends_on=["R-01"])
    downstream = result_downstream(state, "R-01")
    assert downstream.result.id == "R-01"
    assert [d.id for d in downstream.direct_dependents] == ["R-02", "R-03"]
    assert downstream.transitive_dependents == []


def test_result_downstream_transitive_chain():
    """A -> B -> C: downstream of A should return B (direct) and C (transitive)."""
    state: dict = {}
    result_add(state, result_id="A")
    result_add(state, result_id="B", depends_on=["A"])
    result_add(state, result_id="C", depends_on=["B"])
    downstream = result_downstream(state, "A")
    assert downstream.result.id == "A"
    assert [d.id for d in downstream.direct_dependents] == ["B"]
    assert [d.id for d in downstream.transitive_dependents] == ["C"]


def test_result_downstream_diamond():
    """Diamond: A -> B, A -> C, B -> D, C -> D.

    Downstream of A: direct = [B, C], transitive = [D].
    """
    state: dict = {}
    result_add(state, result_id="A")
    result_add(state, result_id="B", depends_on=["A"])
    result_add(state, result_id="C", depends_on=["A"])
    result_add(state, result_id="D", depends_on=["B", "C"])
    downstream = result_downstream(state, "A")
    assert [d.id for d in downstream.direct_dependents] == ["B", "C"]
    assert [d.id for d in downstream.transitive_dependents] == ["D"]


def test_result_downstream_dedupes_duplicate_direct_dependents():
    state: dict = {
        "intermediate_results": [
            {"id": "R-01", "depends_on": []},
            {"id": "R-02", "depends_on": ["R-01", "R-01"]},
            {"id": "R-03", "depends_on": ["R-01"]},
        ]
    }

    downstream = result_downstream(state, "R-01")

    assert [d.id for d in downstream.direct_dependents] == ["R-02", "R-03"]
    assert downstream.transitive_dependents == []


def test_result_downstream_not_found():
    state: dict = {}
    with pytest.raises(ResultNotFoundError):
        result_downstream(state, "R-nonexistent")


def test_result_downstream_circular_dependency():
    """Circular deps should not cause an infinite loop."""
    state: dict = {
        "intermediate_results": [
            {"id": "R-01", "depends_on": ["R-02"]},
            {"id": "R-02", "depends_on": ["R-01"]},
        ]
    }
    downstream = result_downstream(state, "R-01")
    assert downstream.result.id == "R-01"
    # R-02 depends on R-01, so it is a direct dependent.
    assert [d.id for d in downstream.direct_dependents] == ["R-02"]
    # R-01 itself should not appear in transitive (it's the root).
    assert downstream.transitive_dependents == []


def test_result_downstream_ignores_string_entries():
    state: dict = {
        "intermediate_results": [
            "markdown bullet",
            {"id": "R-01", "depends_on": []},
            {"id": "R-02", "depends_on": ["R-01"]},
        ]
    }
    downstream = result_downstream(state, "R-01")
    assert [d.id for d in downstream.direct_dependents] == ["R-02"]
    assert downstream.transitive_dependents == []


def test_result_downstream_handles_missing_depends_on_field():
    state: dict = {
        "intermediate_results": [
            {"id": "R-01"},
            {"id": "R-02", "depends_on": ["R-01"]},
        ]
    }

    downstream = result_downstream(state, "R-01")

    assert [d.id for d in downstream.direct_dependents] == ["R-02"]
    assert downstream.transitive_dependents == []


def test_result_downstream_handles_raw_string_depends_on_field():
    state: dict = {
        "intermediate_results": [
            {"id": "R-01", "depends_on": []},
            {"id": "R-02", "depends_on": "R-01"},
        ]
    }

    downstream = result_downstream(state, "R-01")

    assert [d.id for d in downstream.direct_dependents] == ["R-02"]
    assert downstream.transitive_dependents == []


def test_result_downstream_deep_chain():
    """A -> B -> C -> D -> E: downstream of A returns B (direct), C/D/E (transitive)."""
    state: dict = {}
    result_add(state, result_id="A")
    result_add(state, result_id="B", depends_on=["A"])
    result_add(state, result_id="C", depends_on=["B"])
    result_add(state, result_id="D", depends_on=["C"])
    result_add(state, result_id="E", depends_on=["D"])
    downstream = result_downstream(state, "A")
    assert [d.id for d in downstream.direct_dependents] == ["B"]
    assert [d.id for d in downstream.transitive_dependents] == ["C", "D", "E"]


def test_result_downstream_model_is_frozen():
    state: dict = {}
    result_add(state, result_id="R-01")
    downstream = result_downstream(state, "R-01")
    assert isinstance(downstream, ResultDownstream)
    assert isinstance(downstream.result, IntermediateResult)
    with pytest.raises(ValidationError, match="Instance is frozen"):
        downstream.result = None
