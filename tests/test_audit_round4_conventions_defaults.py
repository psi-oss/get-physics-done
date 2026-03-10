"""Regression tests for SUBFIELD_DEFAULTS normalization consistency.

Ensures that every metric_signature value in SUBFIELD_DEFAULTS is already
in its normalized (post-VALUE_ALIASES) form, so that convention_set
round-trips produce identical values.
"""

from __future__ import annotations

import pytest

from gpd.core.conventions import VALUE_ALIASES
from gpd.mcp.servers.conventions_server import SUBFIELD_DEFAULTS


class TestSubfieldDefaultsNormalized:
    """SUBFIELD_DEFAULTS metric_signature values must be post-normalization."""

    def test_metric_values_are_not_alias_keys(self) -> None:
        """No metric_signature default should appear as a key in VALUE_ALIASES.

        If a value appears as a key in VALUE_ALIASES["metric_signature"], it
        means it is a pre-normalization form that would be transformed by
        normalize_value, causing a mismatch between the default and the
        stored convention after a convention_set round-trip.
        """
        alias_keys = set(VALUE_ALIASES.get("metric_signature", {}).keys())
        violations: list[str] = []

        for subfield, defaults in SUBFIELD_DEFAULTS.items():
            metric_val = defaults.get("metric_signature")
            if metric_val is not None and metric_val in alias_keys:
                normalized = VALUE_ALIASES["metric_signature"][metric_val]
                violations.append(
                    f"{subfield}: metric_signature={metric_val!r} "
                    f"is a pre-normalization alias (normalizes to {normalized!r})"
                )

        assert violations == [], (
            "SUBFIELD_DEFAULTS contains pre-normalization metric_signature values:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )

    @pytest.mark.parametrize(
        "subfield",
        sorted(SUBFIELD_DEFAULTS.keys()),
    )
    def test_each_subfield_metric_is_normalized(self, subfield: str) -> None:
        """Per-subfield check: metric_signature value is already normalized."""
        defaults = SUBFIELD_DEFAULTS[subfield]
        metric_val = defaults.get("metric_signature")
        if metric_val is None:
            pytest.skip(f"{subfield} has no metric_signature default")

        alias_keys = VALUE_ALIASES.get("metric_signature", {})
        assert metric_val not in alias_keys, (
            f"SUBFIELD_DEFAULTS[{subfield!r}]['metric_signature'] = {metric_val!r} "
            f"is a pre-normalization alias; expected the normalized form "
            f"{alias_keys[metric_val]!r}"
        )

    def test_metric_values_are_known_normalized_forms(self) -> None:
        """All metric_signature defaults should be one of the known normalized forms."""
        # The normalized forms are the *values* (not keys) of VALUE_ALIASES
        normalized_forms = set(VALUE_ALIASES.get("metric_signature", {}).values())

        for subfield, defaults in SUBFIELD_DEFAULTS.items():
            metric_val = defaults.get("metric_signature")
            if metric_val is not None:
                assert metric_val in normalized_forms, (
                    f"SUBFIELD_DEFAULTS[{subfield!r}]['metric_signature'] = {metric_val!r} "
                    f"is not one of the known normalized forms: {sorted(normalized_forms)}"
                )

    def test_round_trip_preserves_defaults(self) -> None:
        """Setting each default via convention_set should yield the same value."""
        from gpd.contracts import ConventionLock
        from gpd.core.conventions import convention_set

        for subfield, defaults in SUBFIELD_DEFAULTS.items():
            lock = ConventionLock()
            for key, value in defaults.items():
                result = convention_set(lock, key, value)
                assert result.updated, (
                    f"convention_set failed for {subfield}.{key}={value!r}"
                )
                assert result.value == value, (
                    f"Round-trip mismatch for {subfield}.{key}: "
                    f"default={value!r}, after set={result.value!r}"
                )
