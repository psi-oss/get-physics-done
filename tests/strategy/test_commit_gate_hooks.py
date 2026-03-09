"""Tests for CommitGate invariant check hooks.

Covers:
- _check_assert_conventions: directive parsing + lock validation
- _check_metric_sign_patterns: diag() pattern detection
- _check_natural_units: natural/explicit unit mixing
- _extract_text_values / _walk_strings: recursive payload text extraction
- _matches_detection_strategy: error catalog heuristic matching
- convention_invariant_check: full convention check pipeline
- physics_invariant_check: full physics check pipeline
- create_gpd_invariant_checks: factory with conventions + error catalog
- _has_any_convention: lock emptiness detection
"""

from __future__ import annotations

import pytest
from psi_contracts.gpd import ConventionLock, ErrorClass

from gpd.strategy.commit_gate_hooks import (
    _check_assert_conventions,
    _check_metric_sign_patterns,
    _check_natural_units,
    _extract_text_values,
    _has_any_convention,
    _matches_detection_strategy,
    convention_invariant_check,
    create_gpd_invariant_checks,
    physics_invariant_check,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_lock(**kwargs: object) -> ConventionLock:
    return ConventionLock(**kwargs)


def _make_error(
    *,
    id: int = 1,
    name: str = "Test error",
    description: str = "A test error",
    detection_strategy: str = "Look for pattern",
    example: str = "",
    domains: list[str] | None = None,
) -> ErrorClass:
    return ErrorClass(
        id=id,
        name=name,
        description=description,
        detection_strategy=detection_strategy,
        example=example,
        domains=domains or ["general"],
    )


def _payload(text: str) -> dict[str, object]:
    """Wrap text in a minimal payload dict."""
    return {"solution": {"text": text}}


# ---------------------------------------------------------------------------
# _extract_text_values
# ---------------------------------------------------------------------------


class TestExtractTextValues:
    def test_flat_dict(self):
        texts = _extract_text_values({"a": "hello world", "b": "short"})
        assert "hello world" in texts
        # "short" is only 5 chars, below _MIN_TEXT_LENGTH=6
        assert "short" not in texts

    def test_nested_dict(self):
        texts = _extract_text_values({"outer": {"inner": "deeply nested value"}})
        assert "deeply nested value" in texts

    def test_list_values(self):
        texts = _extract_text_values({"items": ["first item value", "second item value"]})
        assert len(texts) == 2

    def test_mixed_types_skipped(self):
        texts = _extract_text_values({"num": 42, "flag": True, "none": None, "text": "valid text"})
        assert texts == ["valid text"]

    def test_empty_payload(self):
        assert _extract_text_values({}) == []

    def test_deeply_nested(self):
        payload = {"a": {"b": {"c": {"d": "deep string value"}}}}
        texts = _extract_text_values(payload)
        assert "deep string value" in texts


# ---------------------------------------------------------------------------
# _check_assert_conventions
# ---------------------------------------------------------------------------


class TestCheckAssertConventions:
    def test_matching_convention_no_violation(self):
        lock = _make_lock(metric_signature="mostly-plus")
        violations: list[str] = []
        content = "# ASSERT_CONVENTION: metric_signature=mostly-plus\nSome physics."
        _check_assert_conventions(content, lock, violations)
        assert violations == []

    def test_mismatched_convention_produces_violation(self):
        lock = _make_lock(metric_signature="mostly-plus")
        violations: list[str] = []
        content = "# ASSERT_CONVENTION: metric_signature=mostly-minus\nSome physics."
        _check_assert_conventions(content, lock, violations)
        assert len(violations) == 1
        assert "ASSERT_CONVENTION mismatch" in violations[0]
        assert "metric_signature" in violations[0]

    def test_unlocked_convention_skipped(self):
        """If the lock has no value for the asserted key, no violation."""
        lock = _make_lock()  # all None
        violations: list[str] = []
        content = "# ASSERT_CONVENTION: metric_signature=mostly-plus\nSome physics."
        _check_assert_conventions(content, lock, violations)
        assert violations == []

    def test_multiple_directives(self):
        lock = _make_lock(metric_signature="mostly-plus", natural_units="c=hbar=1")
        violations: list[str] = []
        content = "# ASSERT_CONVENTION: metric_signature=mostly-plus\n# ASSERT_CONVENTION: natural_units=CGS\n"
        _check_assert_conventions(content, lock, violations)
        # metric_signature matches, natural_units mismatches
        assert len(violations) == 1
        assert "natural_units" in violations[0]

    def test_custom_convention_match(self):
        lock = _make_lock(custom_conventions={"my_key": "my_value"})
        violations: list[str] = []
        content = "# ASSERT_CONVENTION: my_key=my_value\nWork."
        _check_assert_conventions(content, lock, violations)
        assert violations == []

    def test_custom_convention_mismatch(self):
        lock = _make_lock(custom_conventions={"my_key": "expected"})
        violations: list[str] = []
        content = "# ASSERT_CONVENTION: my_key=wrong\nWork."
        _check_assert_conventions(content, lock, violations)
        assert len(violations) == 1

    def test_no_directives_no_violations(self):
        lock = _make_lock(metric_signature="mostly-plus")
        violations: list[str] = []
        _check_assert_conventions("Plain text with no directives.", lock, violations)
        assert violations == []

    def test_latex_directive_format(self):
        lock = _make_lock(metric_signature="mostly-plus")
        violations: list[str] = []
        content = "% ASSERT_CONVENTION: metric_signature=mostly-minus\nLaTeX content."
        _check_assert_conventions(content, lock, violations)
        assert len(violations) == 1

    def test_html_directive_format(self):
        lock = _make_lock(metric_signature="mostly-plus")
        violations: list[str] = []
        content = "<!-- ASSERT_CONVENTION: metric_signature=mostly-minus -->\nHTML."
        _check_assert_conventions(content, lock, violations)
        assert len(violations) == 1


# ---------------------------------------------------------------------------
# _check_metric_sign_patterns
# ---------------------------------------------------------------------------


class TestCheckMetricSignPatterns:
    def test_no_metric_lock_skips(self):
        lock = _make_lock()  # metric_signature is None
        violations: list[str] = []
        _check_metric_sign_patterns("diag(+, -, -, -)", lock, violations)
        assert violations == []

    def test_mostly_plus_correct_pattern(self):
        lock = _make_lock(metric_signature="mostly-plus")
        violations: list[str] = []
        _check_metric_sign_patterns("The metric is diag(-, +, +, +).", lock, violations)
        assert violations == []

    def test_mostly_plus_wrong_pattern(self):
        """Content uses mostly-minus pattern but lock says mostly-plus."""
        lock = _make_lock(metric_signature="mostly-plus")
        violations: list[str] = []
        _check_metric_sign_patterns("The metric is diag(+, -, -, -).", lock, violations)
        assert len(violations) == 1
        assert "Metric sign inconsistency" in violations[0]
        assert "mostly-minus" in violations[0]

    def test_mostly_minus_correct_pattern(self):
        lock = _make_lock(metric_signature="mostly-minus")
        violations: list[str] = []
        _check_metric_sign_patterns("The metric is diag(+, -, -, -).", lock, violations)
        assert violations == []

    def test_mostly_minus_wrong_pattern(self):
        lock = _make_lock(metric_signature="mostly-minus")
        violations: list[str] = []
        _check_metric_sign_patterns("The metric is diag(-, +, +, +).", lock, violations)
        assert len(violations) == 1
        assert "mostly-plus" in violations[0]

    def test_no_diag_pattern_no_violation(self):
        lock = _make_lock(metric_signature="mostly-plus")
        violations: list[str] = []
        _check_metric_sign_patterns("No metric pattern in this text.", lock, violations)
        assert violations == []

    def test_spacing_variations(self):
        """diag with various whitespace should still match."""
        lock = _make_lock(metric_signature="mostly-plus")
        violations: list[str] = []
        _check_metric_sign_patterns("diag( + , - , - , - )", lock, violations)
        assert len(violations) == 1

    def test_alias_normalization(self):
        """(-,+,+,+) should normalize to mostly-plus."""
        lock = _make_lock(metric_signature="(-,+,+,+)")
        violations: list[str] = []
        # Content uses the opposite sign convention
        _check_metric_sign_patterns("diag(+, -, -, -)", lock, violations)
        assert len(violations) == 1


# ---------------------------------------------------------------------------
# _check_natural_units
# ---------------------------------------------------------------------------


class TestCheckNaturalUnits:
    def test_no_lock_skips(self):
        lock = _make_lock()  # natural_units is None
        violations: list[str] = []
        _check_natural_units("hbar = 1 and 5 eV", lock, violations)
        assert violations == []

    def test_natural_units_with_explicit_symbols_violation(self):
        """When lock says natural units but content mixes hbar=1 with eV."""
        lock = _make_lock(natural_units="c=hbar=1")
        violations: list[str] = []
        content = "We set hbar = 1 and the energy is 5 eV."
        _check_natural_units(content, lock, violations)
        assert len(violations) == 1
        assert "Natural units inconsistency" in violations[0]

    def test_natural_units_without_explicit_symbols_ok(self):
        """Natural unit declaration without explicit unit symbols is fine."""
        lock = _make_lock(natural_units="c=hbar=1")
        violations: list[str] = []
        content = "We set hbar = 1 and the energy is dimensionless."
        _check_natural_units(content, lock, violations)
        assert violations == []

    def test_natural_units_without_declaration_ok(self):
        """Explicit unit symbols without hbar=1 declaration is fine."""
        lock = _make_lock(natural_units="c=hbar=1")
        violations: list[str] = []
        content = "The energy is 5 eV in this calculation."
        _check_natural_units(content, lock, violations)
        assert violations == []

    def test_hbar_c_1_keyword(self):
        lock = _make_lock(natural_units="hbar=c=1")
        violations: list[str] = []
        content = "Setting c = 1, we measure mass in GeV."
        _check_natural_units(content, lock, violations)
        assert len(violations) == 1

    def test_natural_keyword(self):
        lock = _make_lock(natural_units="natural")
        violations: list[str] = []
        content = "Using ℏ = 1 we get energy in MeV."
        _check_natural_units(content, lock, violations)
        assert len(violations) == 1

    def test_non_natural_units_lock_skips(self):
        """If lock value doesn't contain natural unit keywords, skip check."""
        lock = _make_lock(natural_units="CGS")
        violations: list[str] = []
        content = "hbar = 1 and energy 5 eV"
        _check_natural_units(content, lock, violations)
        assert violations == []

    def test_various_unit_symbols(self):
        """Various explicit unit symbols should trigger."""
        lock = _make_lock(natural_units="c=hbar=1")
        for unit in ("kg", "meter", "second", "joule", "GeV", "MeV", "keV", "TeV"):
            violations: list[str] = []
            content = f"hbar = 1 and mass is 5 {unit}"
            _check_natural_units(content, lock, violations)
            assert len(violations) == 1, f"Expected violation for unit: {unit}"

    def test_various_natural_declarations(self):
        """Various natural unit declarations should trigger."""
        lock = _make_lock(natural_units="c=hbar=1")
        for decl in ("hbar = 1", "\\hbar = 1", "ℏ = 1", "c = 1", "k_B = 1"):
            violations: list[str] = []
            content = f"We set {decl} and the mass is 5 GeV."
            _check_natural_units(content, lock, violations)
            assert len(violations) == 1, f"Expected violation for declaration: {decl}"


# ---------------------------------------------------------------------------
# _matches_detection_strategy
# ---------------------------------------------------------------------------


class TestMatchesDetectionStrategy:
    def test_example_substring_match(self):
        error = _make_error(example="exp(+i omega t)")
        assert _matches_detection_strategy("The propagator uses exp(+i omega t) convention.", error)

    def test_short_example_ignored(self):
        """Examples shorter than _MIN_EXAMPLE_LENGTH (11) are skipped."""
        error = _make_error(example="short")
        assert not _matches_detection_strategy("short text", error)

    def test_example_case_insensitive(self):
        error = _make_error(example="Fourier Transform Convention")
        assert _matches_detection_strategy("Apply the fourier transform convention here.", error)

    def test_name_word_match(self):
        """Multi-word name match: >=2 significant words (>=4 chars, not stop words)."""
        error = _make_error(name="Normalization Factor Missing")
        assert _matches_detection_strategy("The normalization factor is missing from this result.", error)

    def test_name_single_word_no_match(self):
        """Single significant word isn't enough for a match."""
        error = _make_error(name="Normalization")
        assert not _matches_detection_strategy("Check normalization carefully.", error)

    def test_name_stop_words_filtered(self):
        """Stop words (errors, wrong, common, etc.) are excluded."""
        error = _make_error(name="Wrong Field Errors")
        # "wrong" and "errors" are stop words; "field" is also a stop word
        # So 0 significant words → no match
        assert not _matches_detection_strategy("wrong field errors in the model", error)

    def test_name_with_short_words_filtered(self):
        """Words shorter than 4 chars are excluded."""
        error = _make_error(name="Bad QFT UV Divergence")
        # "bad"=3, "qft"=3, "uv"=2 → too short; only "divergence" >= 4
        # 1 significant word < _MIN_NAME_WORD_MATCHES (2) → no match
        assert not _matches_detection_strategy("qft uv divergence in the calculation", error)

    def test_no_example_no_name(self):
        error = _make_error(name="", example="")
        assert not _matches_detection_strategy("anything here", error)

    def test_example_exactly_at_min_length(self):
        """Example of exactly 11 chars should be checked."""
        error = _make_error(example="12345678901")  # 11 chars
        assert _matches_detection_strategy("contains 12345678901 pattern", error)

    def test_example_one_below_min_length(self):
        """Example of 10 chars should be skipped."""
        error = _make_error(example="1234567890")  # 10 chars
        assert not _matches_detection_strategy("contains 1234567890 pattern", error)


# ---------------------------------------------------------------------------
# convention_invariant_check (full pipeline)
# ---------------------------------------------------------------------------


class TestConventionInvariantCheck:
    def test_clean_payload_no_violations(self):
        lock = _make_lock(metric_signature="mostly-plus")
        payload = _payload("# ASSERT_CONVENTION: metric_signature=mostly-plus\ndiag(-, +, +, +)")
        violations = convention_invariant_check(payload, {}, lock)
        assert violations == []

    def test_mismatch_in_nested_payload(self):
        lock = _make_lock(metric_signature="mostly-plus")
        payload = {"solution": {"text": "# ASSERT_CONVENTION: metric_signature=mostly-minus\nResult."}}
        violations = convention_invariant_check(payload, {}, lock)
        assert len(violations) >= 1

    def test_metric_sign_violation_in_payload(self):
        lock = _make_lock(metric_signature="mostly-plus")
        payload = _payload("The metric tensor is diag(+, -, -, -).")
        violations = convention_invariant_check(payload, {}, lock)
        assert any("Metric sign inconsistency" in v for v in violations)

    def test_natural_units_violation_in_payload(self):
        lock = _make_lock(natural_units="c=hbar=1")
        payload = _payload("We set hbar = 1, so the mass is 5 GeV.")
        violations = convention_invariant_check(payload, {}, lock)
        assert any("Natural units inconsistency" in v for v in violations)

    def test_empty_payload_no_violations(self):
        lock = _make_lock(metric_signature="mostly-plus")
        violations = convention_invariant_check({}, {}, lock)
        assert violations == []

    def test_multiple_violations_aggregated(self):
        lock = _make_lock(metric_signature="mostly-plus", natural_units="c=hbar=1")
        payload = _payload(
            "# ASSERT_CONVENTION: metric_signature=mostly-minus\ndiag(+, -, -, -)\nSetting hbar = 1, energy is 5 GeV."
        )
        violations = convention_invariant_check(payload, {}, lock)
        # Should have: assert mismatch, metric sign, natural units
        assert len(violations) >= 3

    def test_action_id_in_ctx(self):
        """ctx with action_id should not cause errors."""
        lock = _make_lock(metric_signature="mostly-plus")
        payload = _payload("diag(+, -, -, -)")
        ctx = {"action_id": "test_action"}
        violations = convention_invariant_check(payload, ctx, lock)
        assert len(violations) >= 1


# ---------------------------------------------------------------------------
# physics_invariant_check
# ---------------------------------------------------------------------------


class TestPhysicsInvariantCheck:
    def test_empty_payload_no_violations(self):
        errors = [_make_error()]
        violations = physics_invariant_check({}, {}, errors)
        assert violations == []

    def test_empty_text_no_violations(self):
        errors = [_make_error()]
        payload = _payload("   ")  # whitespace only but >= 6 chars
        violations = physics_invariant_check(payload, {}, errors)
        assert violations == []

    def test_error_catalog_match(self):
        error = _make_error(
            id=42,
            name="Fourier Phase Convention",
            example="exp(+i omega t) instead of exp(-i omega t)",
        )
        payload = _payload("We use exp(+i omega t) instead of exp(-i omega t) convention.")
        violations = physics_invariant_check(payload, {}, [error])
        assert any("[42]" in v for v in violations)

    def test_common_pattern_factor_of_2(self):
        payload = _payload("The result is 1/2 times the integral, multiplied by 2 for spin.")
        violations = physics_invariant_check(payload, {}, [])
        assert any("factor-of-2" in v for v in violations)

    def test_common_pattern_exponential_sign(self):
        payload = _payload("The propagator is e^{+ i k x} in momentum space.")
        violations = physics_invariant_check(payload, {}, [])
        assert any("sign in exponential" in v for v in violations)

    def test_common_pattern_4pi_r2(self):
        payload = _payload("The surface area is 4 pi r^2 for a sphere.")
        violations = physics_invariant_check(payload, {}, [])
        assert any("4*pi*r^2" in v for v in violations)

    def test_no_common_patterns_clean(self):
        payload = _payload("The Hamiltonian is H = p^2/(2m) + V(x).")
        violations = physics_invariant_check(payload, {}, [])
        assert violations == []

    def test_empty_error_catalog(self):
        payload = _payload("Some physics content without common patterns here.")
        violations = physics_invariant_check(payload, {}, [])
        assert violations == []


# ---------------------------------------------------------------------------
# create_gpd_invariant_checks (factory)
# ---------------------------------------------------------------------------


class TestCreateGPDInvariantChecks:
    def test_empty_lock_empty_catalog(self):
        checks = create_gpd_invariant_checks(ConventionLock(), [])
        assert checks == []

    def test_convention_lock_only(self):
        lock = _make_lock(metric_signature="mostly-plus")
        checks = create_gpd_invariant_checks(lock, [])
        assert len(checks) == 1
        # The check should be callable with the CommitGate signature
        result = checks[0](_payload("clean text"), {})
        assert isinstance(result, list)

    def test_error_catalog_only(self):
        errors = [_make_error()]
        checks = create_gpd_invariant_checks(ConventionLock(), errors)
        assert len(checks) == 1

    def test_both_convention_and_catalog(self):
        lock = _make_lock(metric_signature="mostly-plus")
        errors = [_make_error()]
        checks = create_gpd_invariant_checks(lock, errors)
        assert len(checks) == 2

    def test_convention_check_closure_captures_lock(self):
        """The convention check closure should use the lock it was created with."""
        lock = _make_lock(metric_signature="mostly-plus")
        checks = create_gpd_invariant_checks(lock, [])
        payload = _payload("diag(+, -, -, -)")  # wrong sign for mostly-plus
        violations = checks[0](payload, {})
        assert any("Metric sign inconsistency" in v for v in violations)

    def test_physics_check_closure_captures_catalog(self):
        """The physics check closure should use the error catalog it was created with."""
        error = _make_error(
            id=7,
            name="Fourier Phase Convention",
            example="exp(+i omega t) instead of exp(-i omega t)",
        )
        checks = create_gpd_invariant_checks(ConventionLock(), [error])
        payload = _payload("We use exp(+i omega t) instead of exp(-i omega t).")
        violations = checks[0](payload, {})
        assert any("[7]" in v for v in violations)

    def test_custom_convention_produces_check(self):
        lock = _make_lock(custom_conventions={"my_key": "val"})
        checks = create_gpd_invariant_checks(lock, [])
        assert len(checks) == 1


# ---------------------------------------------------------------------------
# _has_any_convention
# ---------------------------------------------------------------------------


class TestHasAnyConvention:
    def test_empty_lock(self):
        assert not _has_any_convention(ConventionLock())

    def test_canonical_field_set(self):
        assert _has_any_convention(_make_lock(metric_signature="mostly-plus"))

    def test_custom_convention_set(self):
        assert _has_any_convention(_make_lock(custom_conventions={"k": "v"}))

    def test_empty_custom_conventions(self):
        assert not _has_any_convention(_make_lock(custom_conventions={}))

    @pytest.mark.parametrize(
        "field",
        [
            "metric_signature",
            "fourier_convention",
            "natural_units",
            "gauge_choice",
            "regularization_scheme",
            "renormalization_scheme",
            "coordinate_system",
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
        ],
    )
    def test_each_canonical_field(self, field: str):
        """Every canonical convention field should make _has_any_convention True."""
        assert _has_any_convention(_make_lock(**{field: "some_value"}))
