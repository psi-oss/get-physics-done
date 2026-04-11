from __future__ import annotations

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from gpd.core.small_utils import (
    first_nonempty_string,
    first_nonempty_stripped_string,
    first_strict_bool,
    paths_equal,
    strict_bool_value,
    utc_now_iso,
)


def test_paths_equal_compares_resolved_equivalent_paths(tmp_path: Path) -> None:
    child = tmp_path / "child"
    child.mkdir()
    assert paths_equal(child, child / ".." / "child") is True


def test_strict_bool_value_rejects_bool_like_aliases() -> None:
    assert strict_bool_value(True) is True
    assert strict_bool_value(False) is False
    assert strict_bool_value("true") is None
    assert strict_bool_value(1) is None


def test_utc_now_iso_returns_timezone_aware_utc_timestamp() -> None:
    parsed = datetime.fromisoformat(utc_now_iso())
    assert parsed.tzinfo is not None
    assert parsed.utcoffset().total_seconds() == 0


def test_first_string_payload_accessors_preserve_empty_and_strip_variants() -> None:
    payload = {"blank": "", "spaced": " value ", "fallback": "next"}
    assert first_nonempty_string(payload, "blank", "spaced") == " value "
    assert first_nonempty_stripped_string(payload, "blank", "spaced") == "value"
    assert first_nonempty_string(SimpleNamespace(name="runtime"), "name") == "runtime"
    assert first_strict_bool({"flag": "true", "fallback": False}, "flag", "fallback") is False
