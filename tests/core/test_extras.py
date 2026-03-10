"""Tests for gpd.core.extras — approximations, uncertainties, questions, calculations."""

from __future__ import annotations

import pytest

from gpd.core.errors import DuplicateApproximationError, ExtrasError
from gpd.core.extras import (
    Approximation,
    ApproximationCheckResult,
    Uncertainty,
    approximation_add,
    approximation_check,
    approximation_list,
    calculation_add,
    calculation_complete,
    calculation_list,
    check_approximation_validity,
    question_add,
    question_list,
    question_resolve,
    uncertainty_add,
    uncertainty_list,
)

# ─── check_approximation_validity ────────────────────────────────────────────


def test_validity_much_less_than():
    assert check_approximation_validity(0.005, "x << 1") == "valid"
    assert check_approximation_validity(0.3, "x << 1") == "marginal"
    assert check_approximation_validity(0.8, "x << 1") == "invalid"


def test_validity_much_greater_than():
    assert check_approximation_validity(200, "x >> 1") == "valid"
    assert check_approximation_validity(5, "x >> 1") == "marginal"
    assert check_approximation_validity(0.5, "x >> 1") == "invalid"


def test_validity_double_bounded():
    assert check_approximation_validity(5.0, "0 < x < 10") == "valid"
    assert check_approximation_validity(1.0, "0 < x < 10") == "marginal"
    assert check_approximation_validity(15.0, "0 < x < 10") == "invalid"


def test_validity_approx_equal():
    assert check_approximation_validity(1.0, "x ~ 1") == "valid"
    assert check_approximation_validity(0.2, "x ~ 1") == "marginal"
    assert check_approximation_validity(100.0, "x ~ 1") == "invalid"


def test_validity_less_than():
    assert check_approximation_validity(3.0, "x < 10") == "valid"
    assert check_approximation_validity(9.0, "x < 10") == "marginal"
    assert check_approximation_validity(15.0, "x < 10") == "invalid"


def test_validity_greater_than():
    assert check_approximation_validity(15.0, "x > 10") == "valid"
    assert check_approximation_validity(11.0, "x > 10") == "marginal"
    assert check_approximation_validity(5.0, "x > 10") == "invalid"


def test_validity_double_bounded_much_less_than():
    """Double-bounded with << operators must not be preempted by single-bound <<.

    With the semantics fix, '0 << x << 10' means 'val >> 0 AND val << 10'.
    The thresholds are strict: val must be much greater than the lower bound
    AND much less than the upper bound.
    """
    # val=0.05: lower (0 << x => val >> 0): val>10 => valid, val>1 => marginal => invalid (0.05<1)
    #           upper (x << 10 => val << 10): abs(0.05) < 0.1*10=1 => valid
    #           worst = invalid
    assert check_approximation_validity(0.05, "0 << x << 10") == "invalid"
    # val=5: lower (0 << x => val >> 0): 5>1 => marginal
    #        upper (x << 10 => val << 10): abs(5)<1? No. abs(5)<5? No. => invalid
    #        worst = invalid
    assert check_approximation_validity(5, "0 << x << 10") == "invalid"
    # val=15: exceeds upper bound completely => invalid
    assert check_approximation_validity(15, "0 << x << 10") == "invalid"
    # A value that satisfies both: val >> 0 (val > 10) AND val << 10 (abs(val) < 1)
    # These constraints are contradictory for "0 << x << 10", so no value is valid.
    # Use a wider range instead: "0.01 << x << 1000"
    assert check_approximation_validity(5.0, "0.01 << x << 1000") == "valid"


def test_validity_single_bound_much_less_than_still_works():
    """Single-bound << must still work after double-bounded reorder."""
    assert check_approximation_validity(0.05, "x << 1") == "valid"


def test_validity_empty_range():
    assert check_approximation_validity(1.0, "") is None


def test_validity_unparseable():
    assert check_approximation_validity(1.0, "banana") is None


# ─── approximation_add / list / check ───────────────────────────────────────


def test_approximation_add():
    state: dict = {}
    approx = approximation_add(state, name="Born approx", validity_range="x << 1", current_value="0.01")
    assert isinstance(approx, Approximation)
    assert approx.name == "Born approx"
    assert len(state["approximations"]) == 1


def test_approximation_add_empty_name():
    with pytest.raises(ExtrasError):
        approximation_add({}, name="")


def test_approximation_add_duplicate():
    state: dict = {}
    approximation_add(state, name="Born approx")
    with pytest.raises(DuplicateApproximationError):
        approximation_add(state, name="born approx")  # case-insensitive


def test_approximation_list():
    state: dict = {}
    approximation_add(state, name="A1")
    approximation_add(state, name="A2")
    result = approximation_list(state)
    assert len(result) == 2


def test_approximation_list_empty():
    assert approximation_list({}) == []


def test_approximation_check():
    state: dict = {}
    approximation_add(state, name="Valid", validity_range="x << 1", current_value="0.01")
    approximation_add(state, name="Invalid", validity_range="x << 1", current_value="0.8")
    approximation_add(state, name="Unchecked", validity_range="", current_value="")
    result = approximation_check(state)
    assert isinstance(result, ApproximationCheckResult)
    assert len(result.valid) == 1
    assert len(result.invalid) == 1
    assert len(result.unchecked) == 1


# ─── uncertainty_add / list ──────────────────────────────────────────────────


def test_uncertainty_add():
    state: dict = {}
    u = uncertainty_add(state, quantity="mass", value="1.0", uncertainty="0.1")
    assert isinstance(u, Uncertainty)
    assert u.quantity == "mass"
    assert len(state["propagated_uncertainties"]) == 1


def test_uncertainty_add_update_existing():
    state: dict = {}
    uncertainty_add(state, quantity="mass", value="1.0", uncertainty="0.1")
    uncertainty_add(state, quantity="Mass", value="2.0", uncertainty="0.2")
    assert len(state["propagated_uncertainties"]) == 1
    assert state["propagated_uncertainties"][0]["value"] == "2.0"


def test_uncertainty_add_empty_quantity():
    with pytest.raises(ExtrasError):
        uncertainty_add({}, quantity="")


def test_uncertainty_list():
    state: dict = {}
    uncertainty_add(state, quantity="mass")
    uncertainty_add(state, quantity="charge")
    result = uncertainty_list(state)
    assert len(result) == 2


def test_uncertainty_list_empty():
    assert uncertainty_list({}) == []


# ─── question_add / list / resolve ───────────────────────────────────────────


def test_question_add():
    state: dict = {}
    text = question_add(state, "What is the coupling constant?")
    assert text == "What is the coupling constant?"
    assert len(state["open_questions"]) == 1


def test_question_add_empty():
    with pytest.raises(ExtrasError):
        question_add({}, "")


def test_question_list():
    state: dict = {}
    question_add(state, "Q1")
    question_add(state, "Q2")
    assert question_list(state) == ["Q1", "Q2"]


def test_question_list_empty():
    assert question_list({}) == []


def test_question_resolve_exact():
    state: dict = {}
    question_add(state, "What is the coupling?")
    removed = question_resolve(state, "What is the coupling?")
    assert removed == 1
    assert len(state["open_questions"]) == 0


def test_question_resolve_substring():
    state: dict = {}
    question_add(state, "What is the coupling constant in QCD?")
    removed = question_resolve(state, "coupling constant")
    assert removed == 1


def test_question_resolve_no_match():
    state: dict = {}
    question_add(state, "Some question")
    removed = question_resolve(state, "nonexistent query")
    assert removed == 0


def test_question_resolve_empty():
    with pytest.raises(ExtrasError):
        question_resolve({}, "")


def test_question_resolve_too_short():
    with pytest.raises(ExtrasError):
        question_resolve({}, "ab")


# ─── calculation_add / list / complete ───────────────────────────────────────


def test_calculation_add():
    state: dict = {}
    text = calculation_add(state, "Computing loop integrals")
    assert text == "Computing loop integrals"
    assert len(state["active_calculations"]) == 1


def test_calculation_add_empty():
    with pytest.raises(ExtrasError):
        calculation_add({}, "")


def test_calculation_list():
    state: dict = {}
    calculation_add(state, "C1")
    calculation_add(state, "C2")
    assert calculation_list(state) == ["C1", "C2"]


def test_calculation_list_empty():
    assert calculation_list({}) == []


def test_calculation_complete_exact():
    state: dict = {}
    calculation_add(state, "Loop integrals")
    removed = calculation_complete(state, "Loop integrals")
    assert removed == 1
    assert len(state["active_calculations"]) == 0


def test_calculation_complete_substring():
    state: dict = {}
    calculation_add(state, "Computing loop integrals for QCD")
    removed = calculation_complete(state, "loop integrals")
    assert removed == 1


def test_calculation_complete_no_match():
    state: dict = {}
    calculation_add(state, "Some calc")
    removed = calculation_complete(state, "nonexistent calc")
    assert removed == 0


def test_calculation_complete_empty():
    with pytest.raises(ExtrasError):
        calculation_complete({}, "")


def test_calculation_complete_too_short():
    with pytest.raises(ExtrasError):
        calculation_complete({}, "ab")


# ─── dict-item support for questions and calculations ─────────────────────


def test_question_resolve_with_dict_items():
    """question_resolve should handle dict items via _item_text()."""
    state = {"open_questions": [{"text": "What is the coupling constant?"}]}
    removed = question_resolve(state, "What is the coupling constant?")
    assert removed == 1
    assert len(state["open_questions"]) == 0


def test_question_resolve_substring_with_dict_items():
    """question_resolve substring match should work with dict items."""
    state = {"open_questions": [{"text": "What is the coupling constant in QCD?"}]}
    removed = question_resolve(state, "coupling constant")
    assert removed == 1


def test_question_resolve_mixed_str_and_dict():
    """question_resolve should handle a mix of str and dict items."""
    state = {
        "open_questions": [
            "plain string question",
            {"text": "dict question about quarks"},
        ]
    }
    removed = question_resolve(state, "dict question about quarks")
    assert removed == 1
    assert len(state["open_questions"]) == 1
    assert state["open_questions"][0] == "plain string question"


def test_calculation_complete_with_dict_items():
    """calculation_complete should handle dict items via _item_text()."""
    state = {"active_calculations": [{"text": "Loop integrals"}]}
    removed = calculation_complete(state, "Loop integrals")
    assert removed == 1
    assert len(state["active_calculations"]) == 0


def test_calculation_complete_substring_with_dict_items():
    """calculation_complete substring match should work with dict items."""
    state = {"active_calculations": [{"text": "Computing loop integrals for QCD"}]}
    removed = calculation_complete(state, "loop integrals")
    assert removed == 1


def test_calculation_complete_mixed_str_and_dict():
    """calculation_complete should handle a mix of str and dict items."""
    state = {
        "active_calculations": [
            "plain string calc",
            {"text": "dict calc about renormalization"},
        ]
    }
    removed = calculation_complete(state, "dict calc about renormalization")
    assert removed == 1
    assert len(state["active_calculations"]) == 1
    assert state["active_calculations"][0] == "plain string calc"
