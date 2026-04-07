"""Tests for gpd.core.results — intermediate result tracking."""

from __future__ import annotations

import pytest

from gpd.core.errors import DuplicateResultError, ResultError, ResultNotFoundError
from gpd.core.results import (
    IntermediateResult,
    MissingDep,
    ResultDeps,
    ResultSearchResult,
    ResultUpsertResult,
    _int_to_base36,
    result_add,
    result_deps,
    result_list,
    result_search,
    result_update,
    result_upsert,
    result_upsert_derived,
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
    assert result.verification_records == []
    assert len(state["intermediate_results"]) == 1


def test_result_add_auto_id():
    state: dict = {"position": {"current_phase": "3"}}
    result = result_add(state, description="auto-id test")
    assert result.id.startswith("R-03-")


def test_result_add_auto_id_ignores_string_entries():
    state: dict = {
        "position": {"current_phase": "3"},
        "intermediate_results": ["markdown bullet", {"id": "R-03-01-abcd", "phase": "3"}],
    }
    result = result_add(state, description="auto-id test")
    assert result.id.startswith("R-03-02-")


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


def test_result_list_ignores_string_entries():
    state: dict = {
        "intermediate_results": [
            "markdown bullet",
            {"id": "R-01", "phase": "1", "verified": False, "verification_records": []},
        ]
    }
    results = result_list(state)
    assert len(results) == 1
    assert results[0].id == "R-01"


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


def test_result_list_filter_unverified_ignores_results_with_verification_records():
    state: dict = {
        "intermediate_results": [
            {
                "id": "R-01",
                "verified": False,
                "verification_records": [{"verifier": "auditor", "method": "manual", "confidence": "low"}],
            },
            {"id": "R-02", "verified": False, "verification_records": []},
        ]
    }
    results = result_list(state, unverified=True)
    assert len(results) == 1
    assert results[0].id == "R-02"


# ─── result_search ───────────────────────────────────────────────────────────


def test_result_search_empty_state_returns_empty_list():
    result = result_search({})
    assert isinstance(result, ResultSearchResult)
    assert result.matches == []
    assert result.total == 0


def test_result_search_missing_registry_returns_empty_list():
    result = result_search({"position": {"current_phase": "1"}})
    assert result.matches == []
    assert result.total == 0


def test_result_search_ignores_string_entries():
    state: dict = {
        "intermediate_results": [
            "legacy markdown bullet",
            {"id": "R-01", "equation": "E = mc^2", "description": "energy", "phase": "1"},
        ]
    }

    results = result_search(state, text="legacy markdown bullet")

    assert results.matches == []
    assert results.total == 0


def test_result_search_matches_text_and_equation_fields():
    state: dict = {
        "intermediate_results": [
            {"id": "R-01", "equation": "E = mc^2", "description": "rest energy", "phase": "1"},
            {"id": "R-02", "equation": "p^2/2m", "description": "kinetic energy", "phase": "2"},
        ]
    }

    equation_matches = result_search(state, equation="p^2/2m")
    text_matches = result_search(state, text="kinetic")

    assert [result.id for result in equation_matches.matches] == ["R-02"]
    assert equation_matches.total == 1
    assert [result.id for result in text_matches.matches] == ["R-02"]
    assert text_matches.total == 1


def test_result_search_matches_exact_ids():
    state: dict = {
        "intermediate_results": [
            {"id": "R-01", "equation": "E = mc^2", "phase": "1"},
            {"id": "R-02", "equation": "F = ma", "phase": "2"},
        ]
    }

    matches = result_search(state, id="r 01")

    assert [result.id for result in matches.matches] == ["R-01"]
    assert matches.total == 1


def test_result_upsert_adds_new_result_when_no_match_exists():
    state: dict = {"position": {"current_phase": "2"}}

    result = result_upsert(
        state,
        equation="E = mc^2",
        description="Mass-energy relation",
        phase="2",
    )

    assert isinstance(result, ResultUpsertResult)
    assert result.action == "added"
    assert result.matched_by is None
    assert result.result.equation == "E = mc^2"
    assert len(state["intermediate_results"]) == 1


def test_result_upsert_updates_existing_result_by_explicit_id():
    state: dict = {}
    result_add(state, result_id="R-01", equation="E = mc^2", description="Old description", phase="1")

    result = result_upsert(
        state,
        result_id="R-01",
        equation="E=mc^2",
        description="Updated description",
        validity="rest frame",
    )

    assert result.action == "updated"
    assert result.matched_by == "id"
    assert set(result.updated_fields) == {"equation", "description", "validity"}
    assert result.result.description == "Updated description"
    assert result.result.validity == "rest frame"
    assert len(state["intermediate_results"]) == 1


def test_result_upsert_reuses_unique_equation_match_when_preferred_id_is_new():
    state: dict = {}
    result_add(state, result_id="R-01", equation="E = mc^2", description="Original", phase="1")

    result = result_upsert(
        state,
        result_id="R-new",
        equation="E=mc^2",
        description="Canonical description",
        phase="1",
    )

    assert result.action == "updated"
    assert result.matched_by == "equation"
    assert result.result.id == "R-01"
    assert result.result.description == "Canonical description"
    assert len(state["intermediate_results"]) == 1


def test_result_upsert_updates_existing_result_by_exact_equation_match():
    state: dict = {}
    result_add(state, result_id="R-01", equation="E = mc^2", description="Original", phase="1")

    result = result_upsert(
        state,
        equation="E=mc^2",
        description="Canonical description",
        phase="1",
    )

    assert result.action == "updated"
    assert result.result.id == "R-01"
    assert result.result.description == "Canonical description"
    assert len(state["intermediate_results"]) == 1


def test_result_upsert_raises_for_ambiguous_equation_match():
    state: dict = {}
    result_add(state, result_id="R-01", equation="E = mc^2", phase="1")
    result_add(state, result_id="R-02", equation="E=mc^2", phase="2")

    with pytest.raises(ResultError, match="Multiple existing results match this equation"):
        result_upsert(state, equation="E = mc^2")


def test_result_upsert_phase_filter_disambiguates_equation_match():
    state: dict = {}
    result_add(state, result_id="R-01", equation="E = mc^2", description="phase one", phase="1")
    result_add(state, result_id="R-02", equation="E=mc^2", description="phase two", phase="2")

    result = result_upsert(state, equation="E = mc^2", description="updated two", phase="2")

    assert result.action == "updated"
    assert result.result.id == "R-02"
    assert result.result.description == "updated two"
    assert len(state["intermediate_results"]) == 2


def test_result_upsert_updates_existing_result_by_description_match():
    state: dict = {}
    result_add(state, result_id="R-01", description="critical coupling", phase="1")

    result = result_upsert(
        state,
        description="Critical coupling",
        validity="g << 1",
        phase="1",
    )

    assert result.action == "updated"
    assert result.matched_by == "description"
    assert result.result.id == "R-01"
    assert result.result.validity == "g << 1"
    assert len(state["intermediate_results"]) == 1


def test_result_upsert_reuses_unique_description_match_when_preferred_id_is_new():
    state: dict = {}
    result_add(state, result_id="R-01", description="critical coupling", phase="1")

    result = result_upsert(
        state,
        result_id="R-new",
        description="Critical coupling",
        validity="g << 1",
        phase="1",
    )

    assert result.action == "updated"
    assert result.matched_by == "description"
    assert result.result.id == "R-01"
    assert result.result.validity == "g << 1"
    assert len(state["intermediate_results"]) == 1


def test_result_upsert_raises_for_ambiguous_description_match():
    state: dict = {}
    result_add(state, result_id="R-01", description="critical coupling", phase="1")
    result_add(state, result_id="R-02", description="Critical coupling", phase="2")

    with pytest.raises(ResultError, match="Multiple existing results match this description"):
        result_upsert(state, description="critical coupling")


# ─── result_upsert_derived ──────────────────────────────────────────────────


def test_result_upsert_derived_reuses_explicit_result_id_when_present():
    state: dict = {}

    result = result_upsert_derived(
        state,
        result_id="R-keep",
        derivation_slug="effective-mass",
        phase="3",
        description="Mass-energy relation",
    )

    assert result.action == "added"
    assert result.result.id == "R-keep"
    assert len(state["intermediate_results"]) == 1
    assert state["intermediate_results"][0]["id"] == "R-keep"


def test_result_upsert_derived_uses_stable_slug_based_result_id():
    state_a: dict = {"position": {"current_phase": "3"}}
    state_b: dict = {"position": {"current_phase": "3"}}
    state_c: dict = {"position": {"current_phase": "3"}}

    first = result_upsert_derived(state_a, derivation_slug="Effective mass from self-energy")
    second = result_upsert_derived(state_b, derivation_slug="Effective mass from self-energy")
    third = result_upsert_derived(state_c, derivation_slug="Different derivation")

    assert first.result.id == "R-03-effective-mass-from-self-energy"
    assert second.result.id == first.result.id
    assert third.result.id != first.result.id


@pytest.mark.parametrize(
    "seed_result, call_kwargs, expected_matched_by",
    [
        (
            {
                "id": "R-01",
                "equation": "E = mc^2",
                "description": "Original description",
                "phase": "1",
                "depends_on": [],
                "verified": False,
                "verification_records": [],
            },
            {
                "equation": "E=mc^2",
                "description": "Canonical description",
                "phase": "1",
            },
            "equation",
        ),
        (
            {
                "id": "R-01",
                "description": "critical coupling",
                "phase": "1",
                "depends_on": [],
                "verified": False,
                "verification_records": [],
            },
            {
                "description": "Critical coupling",
                "validity": "g << 1",
                "phase": "1",
            },
            "description",
        ),
    ],
)
def test_result_upsert_derived_reuses_unique_existing_matches(
    seed_result: dict[str, object],
    call_kwargs: dict[str, object],
    expected_matched_by: str,
):
    state: dict = {"intermediate_results": [seed_result]}

    result = result_upsert_derived(state, derivation_slug="fresh-derivation", **call_kwargs)

    assert result.action == "updated"
    assert result.matched_by == expected_matched_by
    assert result.result.id == "R-01"
    assert len(state["intermediate_results"]) == 1


@pytest.mark.parametrize(
    "seed_results, call_kwargs, expected_match_phrase",
    [
        (
            [
                {
                    "id": "R-01",
                    "equation": "E = mc^2",
                    "phase": "1",
                    "depends_on": [],
                    "verified": False,
                    "verification_records": [],
                },
                {
                    "id": "R-02",
                    "equation": "E=mc^2",
                    "phase": "2",
                    "depends_on": [],
                    "verified": False,
                    "verification_records": [],
                },
            ],
            {"equation": "E = mc^2"},
            "equation",
        ),
        (
            [
                {
                    "id": "R-01",
                    "description": "critical coupling",
                    "phase": "1",
                    "depends_on": [],
                    "verified": False,
                    "verification_records": [],
                },
                {
                    "id": "R-02",
                    "description": "Critical coupling",
                    "phase": "2",
                    "depends_on": [],
                    "verified": False,
                    "verification_records": [],
                },
            ],
            {"description": "critical coupling"},
            "description",
        ),
    ],
)
def test_result_upsert_derived_raises_for_ambiguous_matches(
    seed_results: list[dict[str, object]],
    call_kwargs: dict[str, object],
    expected_match_phrase: str,
):
    state: dict = {"intermediate_results": seed_results}

    with pytest.raises(ResultError, match=f"Multiple existing results match this {expected_match_phrase}"):
        result_upsert_derived(state, derivation_slug="ambiguous-derivation", **call_kwargs)


def test_result_search_normalizes_phase_filters():
    state: dict = {
        "intermediate_results": [
            {"id": "R-01", "equation": "E = mc^2", "phase": "1"},
            {"id": "R-02", "equation": "F = ma", "phase": "02"},
        ]
    }

    one_phase = result_search(state, phase="01")
    two_phase = result_search(state, phase="2")

    assert [result.id for result in one_phase.matches] == ["R-01"]
    assert one_phase.total == 1
    assert [result.id for result in two_phase.matches] == ["R-02"]
    assert two_phase.total == 1


def test_result_search_filters_verified_state():
    state: dict = {
        "intermediate_results": [
            {
                "id": "R-01",
                "equation": "E = mc^2",
                "phase": "1",
                "verified": False,
                "verification_records": [{"verifier": "auditor", "method": "manual", "confidence": "high"}],
            },
            {"id": "R-02", "equation": "F = ma", "phase": "2", "verified": False, "verification_records": []},
        ]
    }

    verified = result_search(state, verified=True)
    unverified = result_search(state, unverified=True)

    assert [result.id for result in verified.matches] == ["R-01"]
    assert verified.total == 1
    assert [result.id for result in unverified.matches] == ["R-02"]
    assert unverified.total == 1


def test_result_search_rejects_conflicting_verification_filters():
    with pytest.raises(ResultError, match="Cannot filter by both verified=True and unverified=True"):
        result_search({}, verified=True, unverified=True)


def test_result_search_matches_transitive_depends_on_identifiers():
    state: dict = {
        "intermediate_results": [
            {"id": "R-01", "equation": "A", "phase": "1", "depends_on": []},
            {"id": "R-02", "equation": "B", "phase": "2", "depends_on": ["R-01"]},
            {"id": "R-03", "equation": "C", "phase": "3", "depends_on": ["R-02"]},
        ]
    }

    matches = result_search(state, depends_on="r 01")

    assert [result.id for result in matches.matches] == ["R-02", "R-03"]
    assert matches.total == 2


def test_result_search_matches_transitive_depends_on_across_phase_filter():
    state: dict = {
        "intermediate_results": [
            {"id": "R-01", "equation": "A", "phase": "1", "depends_on": []},
            {"id": "R-02", "equation": "B", "phase": "2", "depends_on": ["R-01"]},
            {"id": "R-03", "equation": "C", "phase": "3", "depends_on": ["R-02"]},
            {"id": "R-04", "equation": "D", "phase": "4", "depends_on": ["R-03"]},
        ]
    }

    matches = result_search(state, depends_on="R-01", phase="3")

    assert [result.id for result in matches.matches] == ["R-03"]
    assert matches.total == 1


def test_result_search_handles_raw_string_depends_on_field():
    state: dict = {
        "intermediate_results": [
            {"id": "R-01", "equation": "A", "phase": "1", "depends_on": []},
            {"id": "R-02", "equation": "B", "phase": "2", "depends_on": "R-01"},
        ]
    }

    matches = result_search(state, depends_on="R-01")

    assert [result.id for result in matches.matches] == ["R-02"]
    assert matches.total == 1


def test_result_search_preserves_registry_order():
    state: dict = {
        "intermediate_results": [
            {"id": "R-02", "equation": "shared term", "phase": "2"},
            {"id": "R-01", "equation": "shared term", "phase": "1"},
            {"id": "R-03", "equation": "shared term", "phase": "3"},
        ]
    }

    results = result_search(state, text="shared term")

    assert [result.id for result in results.matches] == ["R-02", "R-01", "R-03"]
    assert results.total == 3


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


def test_result_deps_ignores_string_entries():
    state: dict = {
        "intermediate_results": [
            "markdown bullet",
            {"id": "R-01", "depends_on": [], "verified": False, "verification_records": []},
            {"id": "R-02", "depends_on": ["R-01"], "verified": False, "verification_records": []},
        ]
    }
    deps = result_deps(state, "R-02")
    assert len(deps.direct_deps) == 1
    assert deps.direct_deps[0].id == "R-01"


def test_result_deps_handles_raw_string_depends_on_field():
    state: dict = {
        "intermediate_results": [
            {"id": "R-01", "depends_on": [], "verified": False, "verification_records": []},
            {"id": "R-02", "depends_on": "R-01", "verified": False, "verification_records": []},
        ]
    }

    deps = result_deps(state, "R-02")

    assert deps.depends_on == ["R-01"]
    assert len(deps.direct_deps) == 1
    assert deps.direct_deps[0].id == "R-01"


def test_result_deps_not_found():
    state: dict = {}
    with pytest.raises(ResultNotFoundError):
        result_deps(state, "R-nonexistent")


# ─── result_verify ───────────────────────────────────────────────────────────


def test_result_verify():
    state: dict = {}
    result_add(state, result_id="R-01")
    result = result_verify(
        state,
        "R-01",
        verifier="gpd-verifier",
        method="numerical-spot-check",
        confidence="high",
        evidence_path="artifacts/checks/R-01.txt",
        trace_id="trace-1",
    )
    assert result.verified is True
    assert state["intermediate_results"][0]["verified"] is True
    records = state["intermediate_results"][0]["verification_records"]
    assert len(records) == 1
    assert records[0]["verifier"] == "gpd-verifier"
    assert records[0]["method"] == "numerical-spot-check"
    assert records[0]["confidence"] == "high"


def test_result_verify_supports_full_contract_binding_set():
    state: dict = {}
    result_add(state, result_id="R-01")

    result = result_verify(
        state,
        "R-01",
        verifier="gpd-verifier",
        claim_id="claim-benchmark",
        deliverable_id="deliv-figure",
        acceptance_test_id="test-benchmark",
        reference_id="ref-benchmark",
        forbidden_proxy_id="fp-benchmark",
    )

    record = result.verification_records[0]
    assert record.claim_id == "claim-benchmark"
    assert record.deliverable_id == "deliv-figure"
    assert record.acceptance_test_id == "test-benchmark"
    assert record.reference_id == "ref-benchmark"
    assert record.forbidden_proxy_id == "fp-benchmark"

    listed = result_list(state, verified=True)
    assert listed[0].verification_records[0].forbidden_proxy_id == "fp-benchmark"


def test_result_add_with_verification_records_sets_verified():
    state: dict = {}
    result = result_add(
        state,
        result_id="R-02",
        verification_records=[{"verifier": "gpd-verifier", "method": "limit-check", "confidence": "medium"}],
    )
    assert result.verified is True
    assert len(result.verification_records) == 1


@pytest.mark.parametrize(
    "verification_records",
    [
        ["not a dict"],
        [{"verifier": "auditor", "method": "manual", "confidence": 17}],
    ],
)
def test_result_add_rejects_malformed_verification_records(verification_records):
    state: dict = {}

    with pytest.raises(ResultError, match="verification_records"):
        result_add(state, result_id="R-02a", verification_records=verification_records)


def test_result_update_verification_records_normalizes_and_marks_verified():
    state: dict = {}
    result_add(state, result_id="R-03", verified=False)
    fields, result = result_update(
        state,
        "R-03",
        verification_records=[{"verifier": "auditor", "method": "manual", "confidence": "low"}],
    )
    assert "verification_records" in fields
    assert result.verified is True
    assert len(result.verification_records) == 1


def test_result_update_clearing_verification_records_clears_verified():
    state: dict = {}
    result_add(
        state,
        result_id="R-04",
        verification_records=[{"verifier": "gpd-verifier", "method": "limit-check", "confidence": "medium"}],
    )

    fields, result = result_update(state, "R-04", verification_records=[])

    assert "verification_records" in fields
    assert "verified" in fields
    assert result.verified is False
    assert result.verification_records == []


def test_result_update_rejects_conflicting_verified_and_verification_records():
    state: dict = {}
    result_add(
        state,
        result_id="R-05",
        verification_records=[{"verifier": "gpd-verifier", "method": "limit-check", "confidence": "medium"}],
    )

    with pytest.raises(ResultError, match="verified must match whether verification_records is empty"):
        result_update(state, "R-05", verified=True, verification_records=[])


def test_result_update_rejects_false_verified_when_existing_records_remain():
    state: dict = {}
    result_add(
        state,
        result_id="R-05a",
        verification_records=[{"verifier": "gpd-verifier", "method": "limit-check", "confidence": "medium"}],
    )

    with pytest.raises(ResultError, match="verified cannot be false when verification_records are present"):
        result_update(state, "R-05a", verified=False)


def test_result_update_rejects_string_verified_values():
    state: dict = {}
    result_add(state, result_id="R-05b")

    with pytest.raises(ResultError, match="verified must be a boolean"):
        result_update(state, "R-05b", verified="false")


@pytest.mark.parametrize("verified", ["false", "maybe", 1, None])
def test_result_update_rejects_non_boolean_verified_values(verified):
    state: dict = {}
    result_add(state, result_id="R-05c")

    with pytest.raises(ResultError, match="verified must be a boolean"):
        result_update(state, "R-05c", verified=verified)


@pytest.mark.parametrize(
    "verification_records",
    [
        ["not a dict"],
        [{"verifier": "auditor", "method": "manual", "confidence": 17}],
    ],
)
def test_result_update_rejects_malformed_verification_records(verification_records):
    state: dict = {}
    result_add(state, result_id="R-05d")

    with pytest.raises(ResultError, match="verification_records"):
        result_update(state, "R-05d", verification_records=verification_records)


def test_result_verify_not_found():
    state: dict = {}
    with pytest.raises(ResultNotFoundError):
        result_verify(state, "R-nonexistent")


def test_result_verify_rejects_existing_malformed_verification_records():
    state: dict = {
        "intermediate_results": [
            {
                "id": "R-verify-bad",
                "description": "Bad stored evidence",
                "verified": False,
                "verification_records": ["oops"],
            }
        ]
    }

    with pytest.raises(ResultError, match="Existing verification_records for R-verify-bad are invalid"):
        result_verify(state, "R-verify-bad")


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


# ─── Bug-fix regression tests ───────────────────────────────────────────────


def test_result_list_verified_and_unverified_raises_result_error():
    """result_list(verified=True, unverified=True) must raise ResultError, not ValueError."""
    state: dict = {}
    result_add(state, result_id="R-01")
    with pytest.raises(ResultError, match="Cannot filter by both"):
        result_list(state, verified=True, unverified=True)


def test_int_to_base36_negative_raises():
    """_int_to_base36 must reject negative input with ValueError."""
    with pytest.raises(ValueError, match="non-negative"):
        _int_to_base36(-1)


def test_result_verify_invalid_confidence_raises_result_error():
    """result_verify must raise ResultError for invalid confidence values."""
    state: dict = {}
    result_add(state, result_id="R-01")
    with pytest.raises(ResultError, match="Invalid confidence"):
        result_verify(state, "R-01", confidence="very-high")
