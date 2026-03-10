"""Focused regression tests for gpd.core.observability."""

from __future__ import annotations

from unittest.mock import patch


class _DummySpan:
    def set_attribute(self, key: str, value: object) -> None:
        self.last_attribute = (key, value)


class _DummySpanContext:
    def __init__(self) -> None:
        self.span = _DummySpan()

    def __enter__(self) -> _DummySpan:
        return self.span

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def test_gpd_span_interpolates_name_and_prefixes_attrs() -> None:
    from gpd.core.observability import gpd_span

    with patch("gpd.core.observability.logfire.span", return_value=_DummySpanContext()) as span_factory:
        with gpd_span("test.span", domain="physics"):
            pass

    span_factory.assert_called_once_with(
        "gpd.test.span",
        _span_name="gpd.test.span",
        **{"gpd.span_name": "test.span", "gpd.domain": "physics"},
    )
