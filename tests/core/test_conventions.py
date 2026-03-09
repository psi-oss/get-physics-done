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
