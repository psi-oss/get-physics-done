"""Cross-language parity tests for JS <-> Python GPD state operations.

Loads shared JSON fixtures from tests/fixtures/parity/ and validates that
Python produces results matching the expected outputs. The same fixtures
can be loaded by a JS test suite to ensure both implementations agree.

Fixture format:
  {
    "_description": "Human-readable explanation",
    "cases": [
      {
        "name": "test_case_name",
        "input": { ... },
        "expected": { ... }
      }
    ]
  }

Covers:
- Divergence 1 (FIXED): Convention label casing matches JS exactly
- Divergence 2 (FIXED): convention_diff_phases extracts from summaries like JS
- Divergence 6 (FIXED): ID generation uses base-36 timestamp suffix like JS
- Divergence 3 (DOCUMENTED): Key aliases are intentional Python enhancement
- Divergence 4 (DOCUMENTED): Value aliases are intentional Python enhancement
- Divergence 5 (DOCUMENTED): ASSERT_CONVENTION is intentional Python enhancement
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from gpd.contracts import ConventionLock
from gpd.core.conventions import (
    CONVENTION_LABELS,
    KEY_ALIASES,
    KNOWN_CONVENTIONS,
    VALUE_ALIASES,
    convention_check,
    convention_diff,
    convention_list,
    convention_set,
    normalize_key,
    normalize_value,
    parse_assert_conventions,
)
from gpd.core.results import _auto_generate_id, _int_to_base36

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "parity"


def _load_fixture(name: str) -> dict:
    """Load a JSON parity fixture by name."""
    path = FIXTURES_DIR / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _make_lock(data: dict) -> ConventionLock:
    """Create a ConventionLock from fixture data."""
    custom = data.pop("custom_conventions", {})
    lock = ConventionLock(**data)
    lock.custom_conventions.update(custom)
    return lock


# --- Divergence 1 (FIXED): Convention label casing ---


class TestConventionLabelParity:
    """Convention labels must match JS CONVENTION_LABELS exactly."""

    def test_labels_match_fixture(self):
        fixture = _load_fixture("convention_labels")
        for key, expected_label in fixture["labels"].items():
            assert CONVENTION_LABELS[key] == expected_label, (
                f"Label mismatch for {key}: Python={CONVENTION_LABELS[key]!r}, expected={expected_label!r}"
            )

    def test_levi_civita_proper_casing(self):
        assert CONVENTION_LABELS["levi_civita_sign"] == "Levi-Civita sign"

    def test_creation_annihilation_slash(self):
        assert CONVENTION_LABELS["creation_annihilation_order"] == "Creation/annihilation order"

    def test_all_known_conventions_have_labels(self):
        for key in KNOWN_CONVENTIONS:
            assert key in CONVENTION_LABELS, f"Missing label for {key}"


# --- Known conventions parity ---


class TestKnownConventionsParity:
    """Both JS and Python must recognize the same 18 canonical fields."""

    def test_known_conventions_match_fixture(self):
        fixture = _load_fixture("known_conventions")
        assert KNOWN_CONVENTIONS == fixture["known_conventions"]

    def test_convention_count(self):
        assert len(KNOWN_CONVENTIONS) == 18


# --- Convention set parity ---


class TestConventionSetParity:
    """Convention set operation produces the same result structure."""

    @pytest.fixture()
    def fixture(self):
        return _load_fixture("convention_set")

    def test_set_canonical(self, fixture):
        case = next(c for c in fixture["cases"] if c["name"] == "set_canonical_convention")
        lock = _make_lock(dict(case["input"]["lock"]))
        result = convention_set(lock, case["input"]["key"], case["input"]["value"])
        expected = case["expected"]
        assert result.updated == expected["updated"]
        assert result.key == expected["key"]
        assert result.value == expected["value"]
        assert result.custom == expected["custom"]

    def test_set_custom(self, fixture):
        case = next(c for c in fixture["cases"] if c["name"] == "set_custom_convention")
        lock = _make_lock(dict(case["input"]["lock"]))
        result = convention_set(lock, case["input"]["key"], case["input"]["value"])
        expected = case["expected"]
        assert result.updated == expected["updated"]
        assert result.key == expected["key"]
        assert result.custom == expected["custom"]

    def test_immutability_gate(self, fixture):
        case = next(c for c in fixture["cases"] if c["name"] == "immutability_gate_blocks_overwrite")
        lock = _make_lock(dict(case["input"]["lock"]))
        result = convention_set(lock, case["input"]["key"], case["input"]["value"], force=case["input"]["force"])
        expected = case["expected"]
        assert result.updated == expected["updated"]
        assert result.reason == expected["reason"]

    def test_force_overwrite(self, fixture):
        case = next(c for c in fixture["cases"] if c["name"] == "force_overwrite")
        lock = _make_lock(dict(case["input"]["lock"]))
        result = convention_set(lock, case["input"]["key"], case["input"]["value"], force=case["input"]["force"])
        expected = case["expected"]
        assert result.updated == expected["updated"]
        assert result.value == expected["value"]


# --- Convention check parity ---


class TestConventionCheckParity:
    """Convention check produces the same completeness result."""

    @pytest.fixture()
    def fixture(self):
        return _load_fixture("convention_check")

    def test_empty_lock(self, fixture):
        case = next(c for c in fixture["cases"] if c["name"] == "empty_lock_all_missing")
        lock = _make_lock(dict(case["input"]["lock"]))
        result = convention_check(lock)
        expected = case["expected"]
        assert result.complete == expected["complete"]
        assert result.set_count == expected["set_count"]
        assert result.missing_count == expected["missing_count"]
        assert result.total == expected["total"]
        assert result.custom_count == expected["custom_count"]

    def test_partial_lock(self, fixture):
        case = next(c for c in fixture["cases"] if c["name"] == "partial_lock")
        lock = _make_lock(dict(case["input"]["lock"]))
        result = convention_check(lock)
        expected = case["expected"]
        assert result.complete == expected["complete"]
        assert result.set_count == expected["set_count"]
        assert result.missing_count == expected["missing_count"]

    def test_bogus_values(self, fixture):
        case = next(c for c in fixture["cases"] if c["name"] == "bogus_values_treated_as_unset")
        lock = _make_lock(dict(case["input"]["lock"]))
        result = convention_check(lock)
        expected = case["expected"]
        assert result.complete == expected["complete"]
        assert result.set_count == expected["set_count"]


# --- Convention diff parity ---


class TestConventionDiffParity:
    """Convention diff produces the same change sets."""

    @pytest.fixture()
    def fixture(self):
        return _load_fixture("convention_diff")

    def _run_case(self, fixture, case_name):
        case = next(c for c in fixture["cases"] if c["name"] == case_name)
        lock_a = _make_lock(dict(case["input"]["lock_a"]))
        lock_b = _make_lock(dict(case["input"]["lock_b"]))
        result = convention_diff(lock_a, lock_b)
        expected = case["expected"]
        assert len(result.changed) == expected["changed_count"]
        assert len(result.added) == expected["added_count"]
        assert len(result.removed) == expected["removed_count"]
        if "changed_keys" in expected:
            assert [d.key for d in result.changed] == expected["changed_keys"]
        if "added_keys" in expected:
            assert [d.key for d in result.added] == expected["added_keys"]
        if "removed_keys" in expected:
            assert [d.key for d in result.removed] == expected["removed_keys"]

    def test_no_changes(self, fixture):
        self._run_case(fixture, "no_changes")

    def test_detect_change(self, fixture):
        self._run_case(fixture, "detect_change")

    def test_detect_addition(self, fixture):
        self._run_case(fixture, "detect_addition")

    def test_detect_removal(self, fixture):
        self._run_case(fixture, "detect_removal")

    def test_multiple_changes(self, fixture):
        self._run_case(fixture, "multiple_changes")


# --- Convention list parity ---


class TestConventionListParity:
    """Convention list produces the same structure."""

    @pytest.fixture()
    def fixture(self):
        return _load_fixture("convention_list")

    def test_empty_lock(self, fixture):
        case = next(c for c in fixture["cases"] if c["name"] == "empty_lock")
        lock = _make_lock(dict(case["input"]["lock"]))
        result = convention_list(lock)
        expected = case["expected"]
        assert result.total == expected["total"]
        assert result.set_count == expected["set_count"]
        assert result.unset_count == expected["unset_count"]
        assert result.canonical_total == expected["canonical_total"]

    def test_one_set_convention(self, fixture):
        case = next(c for c in fixture["cases"] if c["name"] == "one_set_convention")
        lock = _make_lock(dict(case["input"]["lock"]))
        result = convention_list(lock)
        expected = case["expected"]
        assert result.set_count == expected["set_count"]
        entry = result.conventions["metric_signature"]
        expected_entry = expected["set_entries"]["metric_signature"]
        assert entry.label == expected_entry["label"]
        assert entry.value == expected_entry["value"]
        assert entry.is_set == expected_entry["is_set"]
        assert entry.canonical == expected_entry["canonical"]

    def test_with_custom(self, fixture):
        case = next(c for c in fixture["cases"] if c["name"] == "with_custom_convention")
        lock = _make_lock(dict(case["input"]["lock"]))
        result = convention_list(lock)
        expected = case["expected"]
        assert result.total == expected["total"]
        assert result.set_count == expected["set_count"]


# --- Divergence 6 (FIXED): ID generation format ---


class TestResultIdFormatParity:
    """Result IDs use R-{phase}-{seq}-{7char} with base-36 timestamp suffix."""

    @pytest.fixture()
    def fixture(self):
        return _load_fixture("result_id_format")

    def test_id_matches_pattern(self, fixture):
        pattern = fixture["format"]["pattern"]
        for case in fixture["cases"]:
            state = dict(case["input"]["state"])
            state["intermediate_results"] = list(state.get("intermediate_results", []))
            generated_id = _auto_generate_id(state)
            assert re.match(pattern, generated_id), (
                f"ID {generated_id!r} does not match pattern {pattern!r} for case {case['name']!r}"
            )

    def test_id_prefix(self, fixture):
        for case in fixture["cases"]:
            state = dict(case["input"]["state"])
            state["intermediate_results"] = list(state.get("intermediate_results", []))
            generated_id = _auto_generate_id(state)
            expected_prefix = case["expected"]["id_prefix"]
            assert generated_id.startswith(expected_prefix), (
                f"ID {generated_id!r} does not start with {expected_prefix!r} for case {case['name']!r}"
            )

    def test_suffix_length(self, fixture):
        for case in fixture["cases"]:
            state = dict(case["input"]["state"])
            state["intermediate_results"] = list(state.get("intermediate_results", []))
            generated_id = _auto_generate_id(state)
            # Suffix is the part after the last hyphen in the expected prefix
            expected_prefix = case["expected"]["id_prefix"]
            suffix = generated_id[len(expected_prefix) :]
            expected_len = case["expected"]["suffix_length"]
            assert len(suffix) == expected_len, (
                f"Suffix {suffix!r} has length {len(suffix)}, expected {expected_len} for case {case['name']!r}"
            )

    def test_base36_conversion(self):
        """Verify base-36 encoder matches JS Number.toString(36) behavior."""
        assert _int_to_base36(0) == "0"
        assert _int_to_base36(35) == "z"
        assert _int_to_base36(36) == "10"
        assert _int_to_base36(255) == "73"
        assert _int_to_base36(1000) == "rs"


# --- Divergences 3, 4, 5 (DOCUMENTED): Intentional Python enhancements ---


class TestIntentionalEnhancements:
    """Verify that documented Python enhancements work as specified."""

    @pytest.fixture()
    def fixture(self):
        return _load_fixture("intentional_enhancements")

    def test_key_aliases_match_docs(self, fixture):
        """Divergence 3: Key aliases are an intentional Python enhancement."""
        enhancement = next(e for e in fixture["enhancements"] if e["id"] == "key_aliases")
        for alias, canonical in enhancement["aliases"].items():
            assert normalize_key(alias) == canonical, f"Alias {alias!r} should resolve to {canonical!r}"
            assert alias not in KNOWN_CONVENTIONS, f"Alias {alias!r} should NOT be a known convention"
            assert canonical in KNOWN_CONVENTIONS, f"Canonical {canonical!r} MUST be a known convention"

    def test_key_aliases_complete(self, fixture):
        """All documented aliases are implemented."""
        enhancement = next(e for e in fixture["enhancements"] if e["id"] == "key_aliases")
        for alias in enhancement["aliases"]:
            assert alias in KEY_ALIASES, f"Documented alias {alias!r} not found in KEY_ALIASES"

    def test_value_aliases_match_docs(self, fixture):
        """Divergence 4: Value aliases are an intentional Python enhancement."""
        enhancement = next(e for e in fixture["enhancements"] if e["id"] == "value_aliases")
        for field, normalizations in enhancement["example_normalizations"].items():
            for raw, expected in normalizations.items():
                assert normalize_value(field, raw) == expected, (
                    f"normalize_value({field!r}, {raw!r}) should be {expected!r}"
                )

    def test_value_aliases_metric_complete(self, fixture):
        """All documented metric normalizations are implemented."""
        enhancement = next(e for e in fixture["enhancements"] if e["id"] == "value_aliases")
        metric_norms = enhancement["example_normalizations"]["metric_signature"]
        for raw in metric_norms:
            assert raw in VALUE_ALIASES["metric_signature"], f"Documented normalization {raw!r} not in VALUE_ALIASES"

    def test_assert_convention_formats(self, fixture):
        """Divergence 5: ASSERT_CONVENTION parsing works for all documented formats."""
        enhancement = next(e for e in fixture["enhancements"] if e["id"] == "assert_convention")
        for fmt in enhancement["supported_formats"]:
            # Replace placeholder with a real key=value
            test_content = fmt.replace("key=value", "metric_signature=mostly-plus")
            pairs = parse_assert_conventions(test_content)
            assert len(pairs) >= 1, f"parse_assert_conventions should find assertion in {test_content!r}"
            assert pairs[0][0] == "metric_signature"
            assert pairs[0][1] == "mostly-plus"
