"""Tests for gpd.core.utils — utility functions."""

from __future__ import annotations

import json
import math
import threading
from pathlib import Path

import pytest

from gpd.core.utils import (
    atomic_write,
    compare_phase_numbers,
    file_lock,
    format_progress_bar,
    generate_slug,
    is_phase_complete,
    phase_normalize,
    phase_top_level,
    phase_unpad,
    safe_parse_int,
    safe_parse_json,
    safe_parse_yaml,
    safe_read_file,
    safe_read_file_truncated,
    walk_for_nan,
)


# ---------------------------------------------------------------------------
# phase_normalize
# ---------------------------------------------------------------------------


class TestPhaseNormalize:
    def test_single_digit(self):
        assert phase_normalize("3") == "03"

    def test_two_digits(self):
        assert phase_normalize("12") == "12"

    def test_multi_level(self):
        assert phase_normalize("3.1.2") == "03.1.2"

    def test_already_padded(self):
        assert phase_normalize("03") == "03"

    def test_non_numeric(self):
        assert phase_normalize("abc") == "abc"

    def test_empty_string(self):
        assert phase_normalize("") == ""

    def test_zero(self):
        assert phase_normalize("0") == "00"

    def test_with_suffix(self):
        # Only the numeric prefix is normalized; the suffix after it is dropped
        # because the regex only captures digits and dots
        assert phase_normalize("3-setup") == "03"

    def test_large_number(self):
        assert phase_normalize("100") == "100"


# ---------------------------------------------------------------------------
# phase_unpad
# ---------------------------------------------------------------------------


class TestPhaseUnpad:
    def test_padded(self):
        assert phase_unpad("03") == "3"

    def test_unpadded(self):
        assert phase_unpad("3") == "3"

    def test_multi_level(self):
        assert phase_unpad("08.1.1") == "8.1.1"

    def test_non_numeric(self):
        assert phase_unpad("abc") == "abc"

    def test_empty(self):
        assert phase_unpad("") == ""

    def test_zero(self):
        assert phase_unpad("00") == "0"

    def test_mixed(self):
        assert phase_unpad("01.02.03") == "1.2.3"


# ---------------------------------------------------------------------------
# phase_top_level
# ---------------------------------------------------------------------------


class TestPhaseTopLevel:
    def test_simple(self):
        assert phase_top_level("2") == 2

    def test_multi_level(self):
        assert phase_top_level("2.1.1") == 2

    def test_padded(self):
        assert phase_top_level("03") == 3

    def test_non_numeric(self):
        assert phase_top_level("abc") is None

    def test_empty(self):
        assert phase_top_level("") is None


# ---------------------------------------------------------------------------
# compare_phase_numbers
# ---------------------------------------------------------------------------


class TestComparePhaseNumbers:
    def test_equal(self):
        assert compare_phase_numbers("1", "1") == 0

    def test_less_than(self):
        assert compare_phase_numbers("1", "2") < 0

    def test_greater_than(self):
        assert compare_phase_numbers("3", "1") > 0

    def test_multi_level_equal(self):
        assert compare_phase_numbers("2.1", "2.1") == 0

    def test_multi_level_less(self):
        assert compare_phase_numbers("2.1", "2.2") < 0

    def test_multi_level_deep(self):
        assert compare_phase_numbers("2.1.2", "2.1.10") < 0

    def test_different_depths(self):
        assert compare_phase_numbers("2", "2.1") < 0

    def test_non_numeric(self):
        # Non-numeric falls back to "0"
        assert compare_phase_numbers("abc", "1") < 0

    def test_both_non_numeric(self):
        assert compare_phase_numbers("abc", "abc") == 0


# ---------------------------------------------------------------------------
# is_phase_complete
# ---------------------------------------------------------------------------


class TestIsPhaseComplete:
    def test_complete(self):
        assert is_phase_complete(3, 3) is True

    def test_extra_summaries(self):
        assert is_phase_complete(2, 5) is True

    def test_no_plans(self):
        assert is_phase_complete(0, 0) is False

    def test_missing_summaries(self):
        assert is_phase_complete(3, 1) is False


# ---------------------------------------------------------------------------
# generate_slug
# ---------------------------------------------------------------------------


class TestGenerateSlug:
    def test_basic(self):
        assert generate_slug("Hello World!") == "hello-world"

    def test_empty(self):
        assert generate_slug("") is None

    def test_special_chars(self):
        assert generate_slug("Foo@Bar#Baz") == "foo-bar-baz"

    def test_only_special(self):
        assert generate_slug("@#$%") is None

    def test_leading_trailing_special(self):
        assert generate_slug("---hello---") == "hello"

    def test_spaces(self):
        assert generate_slug("a  b  c") == "a-b-c"

    def test_unicode(self):
        # Non-ASCII stripped, hyphens collapsed
        result = generate_slug("café latte")
        assert result is not None
        assert result.startswith("caf")


# ---------------------------------------------------------------------------
# format_progress_bar
# ---------------------------------------------------------------------------


class TestFormatProgressBar:
    def test_zero(self):
        bar = format_progress_bar(0.0)
        assert bar.startswith("[")
        assert "0%" in bar

    def test_full(self):
        bar = format_progress_bar(1.0)
        assert "100%" in bar

    def test_half(self):
        bar = format_progress_bar(0.5)
        assert "50%" in bar

    def test_clamps_above_one(self):
        bar = format_progress_bar(1.5)
        assert "100%" in bar

    def test_clamps_below_zero(self):
        bar = format_progress_bar(-0.5)
        assert "0%" in bar

    def test_custom_width(self):
        bar = format_progress_bar(0.5, width=20)
        # 20 chars for the bar itself
        assert len(bar) > 20


# ---------------------------------------------------------------------------
# safe_parse_int
# ---------------------------------------------------------------------------


class TestSafeParseInt:
    def test_valid(self):
        assert safe_parse_int("42") == 42

    def test_none(self):
        assert safe_parse_int(None) == 0

    def test_invalid(self):
        assert safe_parse_int("abc") == 0

    def test_custom_default(self):
        assert safe_parse_int("abc", default=None) is None

    def test_float_string(self):
        # "3.14" is not a valid int
        assert safe_parse_int("3.14") == 0

    def test_negative(self):
        assert safe_parse_int("-5") == -5


# ---------------------------------------------------------------------------
# safe_parse_json
# ---------------------------------------------------------------------------


class TestSafeParseJson:
    def test_valid_dict(self):
        assert safe_parse_json('{"a": 1}') == {"a": 1}

    def test_valid_list_returns_none(self):
        # Only dicts are accepted
        assert safe_parse_json("[1, 2, 3]") is None

    def test_invalid(self):
        assert safe_parse_json("not json") is None

    def test_empty(self):
        assert safe_parse_json("") is None

    def test_nested(self):
        result = safe_parse_json('{"a": {"b": [1, 2]}}')
        assert result == {"a": {"b": [1, 2]}}

    def test_none_type_returns_none(self):
        assert safe_parse_json(None) is None  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# safe_parse_yaml
# ---------------------------------------------------------------------------


class TestSafeParseYaml:
    def test_valid(self):
        assert safe_parse_yaml("key: value") == {"key": "value"}

    def test_non_dict(self):
        assert safe_parse_yaml("- item1\n- item2") is None

    def test_invalid(self):
        # Truly invalid YAML that PyYAML rejects
        assert safe_parse_yaml(":\n  :\n    - :\n  bad: [") is None

    def test_empty(self):
        # Empty YAML is None in PyYAML
        assert safe_parse_yaml("") is None

    def test_nested(self):
        result = safe_parse_yaml("a:\n  b: 1\n  c: 2")
        assert result == {"a": {"b": 1, "c": 2}}


# ---------------------------------------------------------------------------
# walk_for_nan
# ---------------------------------------------------------------------------


class TestWalkForNan:
    def test_no_nan(self):
        assert walk_for_nan({"a": 1, "b": "hello"}, "root") == []

    def test_nan_in_dict(self):
        result = walk_for_nan({"a": float("nan")}, "root")
        assert result == ["root.a"]

    def test_nan_in_list(self):
        result = walk_for_nan([1.0, float("nan"), 3.0], "arr")
        assert result == ["arr[1]"]

    def test_nested_nan(self):
        result = walk_for_nan({"a": {"b": [float("nan")]}}, "root")
        assert result == ["root.a.b[0]"]

    def test_none_input(self):
        assert walk_for_nan(None, "root") == []

    def test_empty_dict(self):
        assert walk_for_nan({}, "root") == []

    def test_multiple_nans(self):
        data = {"x": float("nan"), "y": [float("nan")]}
        result = walk_for_nan(data, "root")
        assert len(result) == 2

    def test_inf_is_not_nan(self):
        assert walk_for_nan({"x": float("inf")}, "root") == []


# ---------------------------------------------------------------------------
# safe_read_file
# ---------------------------------------------------------------------------


class TestSafeReadFile:
    def test_existing_file(self, tmp_path: Path):
        f = tmp_path / "test.txt"
        f.write_text("hello")
        assert safe_read_file(f) == "hello"

    def test_missing_file(self, tmp_path: Path):
        assert safe_read_file(tmp_path / "nope.txt") is None

    def test_directory(self, tmp_path: Path):
        assert safe_read_file(tmp_path) is None


# ---------------------------------------------------------------------------
# safe_read_file_truncated
# ---------------------------------------------------------------------------


class TestSafeReadFileTruncated:
    def test_short_file(self, tmp_path: Path):
        f = tmp_path / "short.txt"
        f.write_text("hi")
        assert safe_read_file_truncated(f, max_chars=100) == "hi"

    def test_truncation(self, tmp_path: Path):
        f = tmp_path / "long.txt"
        f.write_text("a" * 1000)
        result = safe_read_file_truncated(f, max_chars=50)
        assert result is not None
        assert "truncated" in result
        assert len(result) < 1000

    def test_missing_file(self, tmp_path: Path):
        assert safe_read_file_truncated(tmp_path / "nope.txt") is None


# ---------------------------------------------------------------------------
# atomic_write
# ---------------------------------------------------------------------------


class TestAtomicWrite:
    def test_creates_file(self, tmp_path: Path):
        f = tmp_path / "out.txt"
        atomic_write(f, "content")
        assert f.read_text() == "content"

    def test_overwrites_existing(self, tmp_path: Path):
        f = tmp_path / "out.txt"
        f.write_text("old")
        atomic_write(f, "new")
        assert f.read_text() == "new"

    def test_creates_parent_dirs(self, tmp_path: Path):
        f = tmp_path / "sub" / "dir" / "out.txt"
        atomic_write(f, "nested")
        assert f.read_text() == "nested"

    def test_no_partial_write_on_disk(self, tmp_path: Path):
        """After atomic_write, no temp files should be left behind."""
        f = tmp_path / "out.txt"
        atomic_write(f, "data")
        tmp_files = list(tmp_path.glob(".tmp_*"))
        assert tmp_files == []


# ---------------------------------------------------------------------------
# file_lock
# ---------------------------------------------------------------------------


class TestFileLock:
    def test_basic_lock(self, tmp_path: Path):
        target = tmp_path / "state.json"
        target.write_text("{}")
        with file_lock(target):
            # We hold the lock — write should succeed
            target.write_text('{"locked": true}')
        assert json.loads(target.read_text()) == {"locked": True}

    def test_lock_file_cleanup(self, tmp_path: Path):
        target = tmp_path / "state.json"
        target.write_text("{}")
        with file_lock(target):
            pass
        # Lock file should be cleaned up
        lock_path = target.with_suffix(".json.lock")
        assert not lock_path.exists()

    def test_concurrent_locks(self, tmp_path: Path):
        """Two threads should serialize access through the lock."""
        target = tmp_path / "counter.txt"
        target.write_text("0")
        results = []

        def increment():
            with file_lock(target, timeout=10.0):
                val = int(target.read_text())
                val += 1
                target.write_text(str(val))
                results.append(val)

        threads = [threading.Thread(target=increment) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15)

        assert int(target.read_text()) == 5
        assert sorted(results) == [1, 2, 3, 4, 5]

    def test_timeout_raises(self, tmp_path: Path):
        """If a lock can't be acquired in time, TimeoutError is raised."""
        import fcntl

        target = tmp_path / "blocked.txt"
        target.write_text("")
        lock_path = target.with_suffix(".txt.lock")
        lock_path.parent.mkdir(parents=True, exist_ok=True)

        # Hold the lock externally
        held = open(lock_path, "w")
        fcntl.flock(held.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            with pytest.raises(TimeoutError):
                with file_lock(target, timeout=0.1):
                    pass  # pragma: no cover
        finally:
            fcntl.flock(held.fileno(), fcntl.LOCK_UN)
            held.close()
