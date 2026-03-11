"""Tests for gpd.core.conventions — convention lock management."""

from __future__ import annotations

import pytest

from gpd.contracts import ConventionLock
from gpd.core.conventions import (
    KNOWN_CONVENTIONS,
    AssertionMismatch,
    ConventionCheckResult,
    ConventionDiffResult,
    ConventionEntry,
    ConventionListResult,
    ConventionSetResult,
    convention_check,
    convention_diff,
    convention_list,
    convention_set,
    is_bogus_value,
    normalize_key,
    normalize_value,
    parse_assert_conventions,
    sanitize_value,
    validate_assertions,
)
from gpd.core.errors import ConventionError

# ─── normalize_key ────────────────────────────────────────────────────────────


def test_normalize_key_alias():
    assert normalize_key("metric") == "metric_signature"
    assert normalize_key("fourier") == "fourier_convention"
    assert normalize_key("units") == "natural_units"


def test_normalize_key_passthrough():
    assert normalize_key("metric_signature") == "metric_signature"
    assert normalize_key("unknown_key") == "unknown_key"


# ─── normalize_value ─────────────────────────────────────────────────────────


def test_normalize_value_metric():
    assert normalize_value("metric_signature", "(+,-,-,-)") == "mostly-minus"
    assert normalize_value("metric_signature", "(-,+,+,+)") == "mostly-plus"
    assert normalize_value("metric_signature", "++++") == "euclidean"


def test_normalize_value_passthrough():
    assert normalize_value("metric_signature", "custom-value") == "custom-value"
    assert normalize_value("unknown_field", "anything") == "anything"


# ─── is_bogus_value ──────────────────────────────────────────────────────────


def test_bogus_values():
    assert is_bogus_value(None) is True
    assert is_bogus_value("") is True
    assert is_bogus_value("null") is True
    assert is_bogus_value("undefined") is True
    assert is_bogus_value("none") is True
    assert is_bogus_value("  None  ") is True


def test_non_bogus_values():
    assert is_bogus_value("mostly-plus") is False
    assert is_bogus_value("0") is False


# ─── sanitize_value ──────────────────────────────────────────────────────────


def test_sanitize_value_strips_whitespace():
    assert sanitize_value("  hello  ") == "hello"


def test_sanitize_value_collapses_newlines():
    assert sanitize_value("line1\nline2\r\nline3") == "line1 line2 line3"


def test_sanitize_value_rejects_bogus():
    with pytest.raises(ConventionError):
        sanitize_value("")
    with pytest.raises(ConventionError):
        sanitize_value("null")


# ─── convention_set ──────────────────────────────────────────────────────────


def test_convention_set_canonical():
    lock = ConventionLock()
    result = convention_set(lock, "metric_signature", "mostly-plus")
    assert isinstance(result, ConventionSetResult)
    assert result.updated is True
    assert result.key == "metric_signature"
    assert result.value == "mostly-plus"
    assert lock.metric_signature == "mostly-plus"


def test_convention_set_alias():
    lock = ConventionLock()
    result = convention_set(lock, "metric", "mostly-minus")
    assert result.updated is True
    assert result.key == "metric_signature"
    assert lock.metric_signature == "mostly-minus"


def test_convention_set_immutability_gate():
    lock = ConventionLock()
    convention_set(lock, "metric_signature", "mostly-plus")
    result = convention_set(lock, "metric_signature", "mostly-minus")
    assert result.updated is False
    assert result.reason == "convention_already_set"
    assert lock.metric_signature == "mostly-plus"


def test_convention_set_force_overwrite():
    lock = ConventionLock()
    convention_set(lock, "metric_signature", "mostly-plus")
    result = convention_set(lock, "metric_signature", "mostly-minus", force=True)
    assert result.updated is True
    assert lock.metric_signature == "mostly-minus"


def test_convention_set_custom():
    lock = ConventionLock()
    result = convention_set(lock, "my_custom_convention", "some-value")
    assert result.updated is True
    assert result.custom is True
    assert lock.custom_conventions["my_custom_convention"] == "some-value"


# ─── convention_list ─────────────────────────────────────────────────────────


def test_convention_list_empty():
    lock = ConventionLock()
    result = convention_list(lock)
    assert isinstance(result, ConventionListResult)
    assert result.set_count == 0
    assert result.total == len(KNOWN_CONVENTIONS)
    assert result.unset_count == len(KNOWN_CONVENTIONS)


def test_convention_list_with_values():
    lock = ConventionLock(metric_signature="mostly-plus")
    result = convention_list(lock)
    assert result.set_count == 1
    entry = result.conventions["metric_signature"]
    assert isinstance(entry, ConventionEntry)
    assert entry.is_set is True
    assert entry.value == "mostly-plus"


# ─── convention_diff ─────────────────────────────────────────────────────────


def test_convention_diff_no_changes():
    lock_a = ConventionLock()
    lock_b = ConventionLock()
    result = convention_diff(lock_a, lock_b)
    assert isinstance(result, ConventionDiffResult)
    assert len(result.changed) == 0
    assert len(result.added) == 0
    assert len(result.removed) == 0


def test_convention_diff_detects_changes():
    lock_a = ConventionLock(metric_signature="mostly-plus")
    lock_b = ConventionLock(metric_signature="mostly-minus")
    result = convention_diff(lock_a, lock_b)
    assert len(result.changed) == 1
    assert result.changed[0].key == "metric_signature"
    assert result.changed[0].from_value == "mostly-plus"
    assert result.changed[0].to_value == "mostly-minus"


def test_convention_diff_detects_additions():
    lock_a = ConventionLock()
    lock_b = ConventionLock(metric_signature="mostly-plus")
    result = convention_diff(lock_a, lock_b)
    assert len(result.added) == 1
    assert result.added[0].key == "metric_signature"


def test_convention_diff_detects_removals():
    lock_a = ConventionLock(metric_signature="mostly-plus")
    lock_b = ConventionLock()
    result = convention_diff(lock_a, lock_b)
    assert len(result.removed) == 1
    assert result.removed[0].key == "metric_signature"


# ─── convention_check ────────────────────────────────────────────────────────


def test_convention_check_incomplete():
    lock = ConventionLock()
    result = convention_check(lock)
    assert isinstance(result, ConventionCheckResult)
    assert result.complete is False
    assert result.missing_count == len(KNOWN_CONVENTIONS)
    assert result.set_count == 0


def test_convention_check_with_custom():
    lock = ConventionLock()
    lock.custom_conventions["my_custom"] = "value"
    result = convention_check(lock)
    assert result.custom_count == 1


# ─── parse_assert_conventions ────────────────────────────────────────────────


def test_parse_assert_markdown():
    content = "<!-- ASSERT_CONVENTION: metric=mostly-plus, fourier=physics -->"
    pairs = parse_assert_conventions(content)
    assert ("metric_signature", "mostly-plus") in pairs
    assert ("fourier_convention", "physics") in pairs


def test_parse_assert_latex():
    content = "% ASSERT_CONVENTION: units=natural"
    pairs = parse_assert_conventions(content)
    assert ("natural_units", "natural") in pairs


def test_parse_assert_python():
    content = "# ASSERT_CONVENTION: gauge=Lorenz"
    pairs = parse_assert_conventions(content)
    assert ("gauge_choice", "Lorenz") in pairs


def test_parse_assert_no_assertions():
    content = "Just regular text with no assertions."
    pairs = parse_assert_conventions(content)
    assert pairs == []


# ─── validate_assertions ────────────────────────────────────────────────────


def test_validate_assertions_match():
    lock = ConventionLock(metric_signature="mostly-plus")
    content = "<!-- ASSERT_CONVENTION: metric=mostly-plus -->"
    mismatches = validate_assertions(content, lock, filename="test.md")
    assert mismatches == []


def test_validate_assertions_mismatch():
    lock = ConventionLock(metric_signature="mostly-plus")
    content = "<!-- ASSERT_CONVENTION: metric=mostly-minus -->"
    mismatches = validate_assertions(content, lock, filename="test.md")
    assert len(mismatches) == 1
    assert isinstance(mismatches[0], AssertionMismatch)
    assert mismatches[0].key == "metric_signature"
    assert mismatches[0].file_value == "mostly-minus"
    assert mismatches[0].lock_value == "mostly-plus"


def test_validate_assertions_unset_convention_skipped():
    lock = ConventionLock()
    content = "<!-- ASSERT_CONVENTION: metric=mostly-plus -->"
    mismatches = validate_assertions(content, lock, filename="test.md")
    assert mismatches == []


# ─── Edge cases: empty/unicode/long values ────────────────────────────────


def test_convention_set_empty_string_rejected():
    """Empty string must be treated as bogus and rejected."""
    lock = ConventionLock()
    with pytest.raises(ConventionError):
        convention_set(lock, "metric_signature", "")


def test_convention_set_whitespace_only_rejected():
    """Whitespace-only string collapses to empty and is rejected."""
    lock = ConventionLock()
    with pytest.raises(ConventionError):
        convention_set(lock, "metric_signature", "   ")


def test_convention_set_newlines_collapsed():
    """Newlines in values are collapsed to spaces."""
    lock = ConventionLock()
    result = convention_set(lock, "metric_signature", "mostly\n-plus")
    assert result.updated is True
    assert result.value == "mostly -plus"


def test_convention_set_unicode_key_as_custom():
    """Unicode keys not in KNOWN_CONVENTIONS are treated as custom."""
    lock = ConventionLock()
    result = convention_set(lock, "\u00e9lectrique", "oui")
    assert result.updated is True
    assert result.custom is True
    assert lock.custom_conventions["\u00e9lectrique"] == "oui"


def test_convention_set_very_long_value():
    """Very long values are accepted (no truncation)."""
    lock = ConventionLock()
    long_val = "x" * 10_000
    result = convention_set(lock, "metric_signature", long_val)
    assert result.updated is True
    assert lock.metric_signature == long_val


def test_is_bogus_value_case_insensitive():
    """Bogus value detection is case-insensitive."""
    assert is_bogus_value("NULL") is True
    assert is_bogus_value("None") is True
    assert is_bogus_value("UNDEFINED") is True
    assert is_bogus_value("Null") is True


def test_is_bogus_value_with_whitespace():
    """Leading/trailing whitespace still detects bogus values."""
    assert is_bogus_value("  null  ") is True
    assert is_bogus_value("\tnone\t") is True
    assert is_bogus_value(" ") is True


def test_sanitize_value_rejects_none_variants():
    """Sanitize rejects all _BOGUS_VALUES variants."""
    for bogus in ("", "null", "undefined", "none"):
        with pytest.raises(ConventionError):
            sanitize_value(bogus)


# ─── Edge cases: convention_check validates all 18 fields ─────────────────


def test_convention_check_all_18_set():
    """When all 18 canonical fields are set, check reports complete."""
    lock = ConventionLock(
        metric_signature="mostly-plus",
        fourier_convention="physics",
        natural_units="natural",
        gauge_choice="Lorenz",
        regularization_scheme="dim-reg",
        renormalization_scheme="MS-bar",
        coordinate_system="spherical",
        spin_basis="helicity",
        state_normalization="relativistic",
        coupling_convention="alpha",
        index_positioning="NW-SE",
        time_ordering="T-product",
        commutation_convention="canonical",
        levi_civita_sign="+1",
        generator_normalization="standard",
        covariant_derivative_sign="+",
        gamma_matrix_convention="Dirac",
        creation_annihilation_order="normal",
    )
    result = convention_check(lock)
    assert result.complete is True
    assert result.missing_count == 0
    assert result.set_count == 18
    assert result.total == 18


def test_convention_check_partial():
    """Partial lock correctly reports set/missing counts."""
    lock = ConventionLock(metric_signature="mostly-plus", gauge_choice="Lorenz")
    result = convention_check(lock)
    assert result.complete is False
    assert result.set_count == 2
    assert result.missing_count == 16


# ─── Edge cases: parse_assert_conventions with indentation ───────────────


def test_parse_assert_indented_python():
    """Indented Python comments are parsed (e.g. inside a function)."""
    content = "    # ASSERT_CONVENTION: metric=mostly-plus"
    pairs = parse_assert_conventions(content)
    assert ("metric_signature", "mostly-plus") in pairs


def test_parse_assert_indented_latex():
    """Indented LaTeX comments are parsed."""
    content = "  % ASSERT_CONVENTION: gauge=Lorenz"
    pairs = parse_assert_conventions(content)
    assert ("gauge_choice", "Lorenz") in pairs


def test_parse_assert_indented_html():
    """Indented HTML comments are parsed."""
    content = "  <!-- ASSERT_CONVENTION: units=natural -->"
    pairs = parse_assert_conventions(content)
    assert ("natural_units", "natural") in pairs


def test_parse_assert_tab_indented():
    """Tab-indented comments are parsed."""
    content = "\t# ASSERT_CONVENTION: spin=helicity"
    pairs = parse_assert_conventions(content)
    assert ("spin_basis", "helicity") in pairs


# ─── Edge case: immutability gate with same value is a no-op ─────────────


def test_convention_set_same_value_no_force_needed():
    """Re-setting same value succeeds without force."""
    lock = ConventionLock()
    convention_set(lock, "metric_signature", "mostly-plus")
    result = convention_set(lock, "metric_signature", "mostly-plus")
    assert result.updated is True  # same value, no conflict


# ─── Edge case: custom convention immutability ────────────────────────────


def test_convention_set_custom_immutability_gate():
    """Custom conventions also require force to overwrite."""
    lock = ConventionLock()
    convention_set(lock, "my_custom", "value1")
    result = convention_set(lock, "my_custom", "value2")
    assert result.updated is False
    assert result.reason == "convention_already_set"


def test_convention_set_custom_force_overwrite():
    """Custom conventions can be overwritten with force."""
    lock = ConventionLock()
    convention_set(lock, "my_custom", "value1")
    result = convention_set(lock, "my_custom", "value2", force=True)
    assert result.updated is True
    assert lock.custom_conventions["my_custom"] == "value2"


# ─── convention_diff_phases ──────────────────────────────────────────────────


class TestConventionDiffPhases:
    """Tests for convention_diff_phases."""

    def test_missing_phase_ids_returns_empty(self, tmp_path):
        """convention_diff_phases with missing phase IDs returns empty result."""
        from gpd.core.conventions import convention_diff_phases
        gpd_dir = tmp_path / ".gpd"
        gpd_dir.mkdir()

        result = convention_diff_phases(tmp_path, phase1=None, phase2="1")
        assert result.changed == []
        assert result.added == []
        assert result.removed == []

    def test_nonexistent_phases_returns_empty(self, tmp_path):
        """convention_diff_phases with nonexistent phases returns empty result."""
        from gpd.core.conventions import convention_diff_phases
        gpd_dir = tmp_path / ".gpd" / "phases"
        gpd_dir.mkdir(parents=True)

        result = convention_diff_phases(tmp_path, phase1="99", phase2="98")
        assert result.changed == []
        assert result.added == []
        assert result.removed == []
