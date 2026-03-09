"""Tests for gpd.core.errors — exception hierarchy."""

from __future__ import annotations

import pytest

from gpd.core.errors import (
    ConfigError,
    ConventionError,
    DuplicateApproximationError,
    DuplicateResultError,
    ExtrasError,
    GPDError,
    PatternError,
    QueryError,
    ResultError,
    ResultNotFoundError,
    StateError,
    TraceError,
    ValidationError,
)


class TestGPDErrorHierarchy:
    """All domain errors should be catchable as GPDError."""

    @pytest.mark.parametrize(
        "exc_cls",
        [
            StateError,
            ConventionError,
            ResultError,
            ResultNotFoundError,
            DuplicateResultError,
            QueryError,
            ExtrasError,
            DuplicateApproximationError,
            PatternError,
            TraceError,
            ConfigError,
            ValidationError,
        ],
    )
    def test_inherits_gpd_error(self, exc_cls):
        assert issubclass(exc_cls, GPDError)

    def test_catch_as_gpd_error(self):
        with pytest.raises(GPDError):
            raise StateError("state broken")

    def test_catch_as_gpd_error_convention(self):
        with pytest.raises(GPDError):
            raise ConventionError("bad convention")


class TestValueErrorCompat:
    """Domain errors inheriting ValueError should be catchable as such."""

    @pytest.mark.parametrize(
        "exc_cls",
        [
            StateError,
            ConventionError,
            ResultError,
            DuplicateResultError,
            QueryError,
            ExtrasError,
            DuplicateApproximationError,
            ConfigError,
            ValidationError,
        ],
    )
    def test_inherits_value_error(self, exc_cls):
        assert issubclass(exc_cls, ValueError)

    def test_catch_as_value_error(self):
        with pytest.raises(ValueError):
            raise ConventionError("test")


class TestKeyErrorCompat:
    def test_result_not_found_is_key_error(self):
        assert issubclass(ResultNotFoundError, KeyError)

    def test_catch_as_key_error(self):
        with pytest.raises(KeyError):
            raise ResultNotFoundError("missing-id")


class TestPatternTraceNotValueError:
    """PatternError and TraceError should NOT be ValueError."""

    def test_pattern_error_not_value_error(self):
        assert not issubclass(PatternError, ValueError)

    def test_trace_error_not_value_error(self):
        assert not issubclass(TraceError, ValueError)


class TestResultNotFoundError:
    def test_message(self):
        err = ResultNotFoundError("abc123")
        assert "abc123" in str(err)
        assert err.result_id == "abc123"


class TestDuplicateResultError:
    def test_message(self):
        err = DuplicateResultError("abc123")
        assert "abc123" in str(err)
        assert err.result_id == "abc123"


class TestDuplicateApproximationError:
    def test_message(self):
        err = DuplicateApproximationError("small-angle")
        assert "small-angle" in str(err)
        assert err.name == "small-angle"
