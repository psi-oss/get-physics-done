from __future__ import annotations

from pathlib import Path

import pytest

from gpd.core.utils import (
    compare_phase_numbers,
    file_lock,
    phase_normalize,
    phase_unpad,
    safe_parse_int,
    safe_read_file,
    safe_read_file_truncated,
)


def _sign(value: int) -> int:
    return (value > 0) - (value < 0)


@pytest.mark.parametrize(
    ("left", "right", "expected"),
    [
        ("2", "2", 0),
        ("1", "3", -1),
        ("5", "2", 1),
        ("2.1.3", "2.1.3", 0),
        ("2.1", "2.10", -1),
        ("2.10", "2.1", 1),
        ("2", "2.1", -1),
        ("2", "2.0", 0),
        ("abc", "def", -1),
        ("def", "abc", 1),
        ("02", "2", 0),
        ("2", "02", 0),
        ("1.2.3", "1.2.4", -1),
        ("1.3.0", "1.2.9", 1),
    ],
)
def test_compare_phase_numbers(left: str, right: str, expected: int) -> None:
    assert _sign(compare_phase_numbers(left, right)) == expected


@pytest.mark.parametrize(
    ("raw", "normalized"),
    [
        ("3", "03"),
        ("12", "12"),
        ("3.1.2", "03.1.2"),
        ("03", "03"),
        ("intro", "intro"),
        ("", ""),
        ("0", "00"),
    ],
)
def test_phase_normalize(raw: str, normalized: str) -> None:
    assert phase_normalize(raw) == normalized


@pytest.mark.parametrize(
    ("raw", "display"),
    [
        ("03", "3"),
        ("08.1.1", "8.1.1"),
        ("12", "12"),
        ("intro", "intro"),
        ("", ""),
    ],
)
def test_phase_unpad(raw: str, display: str) -> None:
    assert phase_unpad(raw) == display


@pytest.mark.parametrize(("raw", "canonical"), [("3", "3"), ("03.1.2", "3.1.2"), ("12.5", "12.5")])
def test_phase_round_trip(raw: str, canonical: str) -> None:
    assert phase_unpad(phase_normalize(raw)) == canonical


@pytest.mark.parametrize(
    ("value", "default", "expected"),
    [
        ("42", 0, 42),
        (7, 0, 7),
        (True, 0, 1),
        (None, 0, 0),
        (None, -1, -1),
        ("abc", 0, 0),
        ("xyz", None, None),
        ("3.14", 0, 0),
        (3.9, 0, 3),
        ("", 0, 0),
        ("-5", 0, -5),
        ("0", 0, 0),
    ],
)
def test_safe_parse_int(value: object, default: int | None, expected: int | None) -> None:
    assert safe_parse_int(value, default=default) == expected


def test_safe_read_file_reads_existing_text_file(tmp_path: Path) -> None:
    target = tmp_path / "test.txt"
    target.write_text("hello world", encoding="utf-8")
    assert safe_read_file(target) == "hello world"


@pytest.mark.parametrize("target", ["missing.txt", "."])
def test_safe_read_file_returns_none_for_missing_paths_and_directories(tmp_path: Path, target: str) -> None:
    path = tmp_path / target
    assert safe_read_file(path) is None


def test_safe_read_file_truncated_reads_small_files_fully(tmp_path: Path) -> None:
    target = tmp_path / "small.txt"
    target.write_text("short content", encoding="utf-8")
    assert safe_read_file_truncated(target) == "short content"


def test_safe_read_file_truncated_marks_large_files(tmp_path: Path) -> None:
    target = tmp_path / "large.txt"
    target.write_text("x" * 1000, encoding="utf-8")

    result = safe_read_file_truncated(target, max_chars=100)

    assert result is not None
    assert result.startswith("x" * 100)
    assert "truncated" in result


def test_safe_read_file_truncated_returns_none_for_missing_files(tmp_path: Path) -> None:
    assert safe_read_file_truncated(tmp_path / "missing.txt") is None


def test_file_lock_allows_writes_while_held(tmp_path: Path) -> None:
    target = tmp_path / "lockable.json"
    target.write_text("{}", encoding="utf-8")

    with file_lock(target):
        target.write_text('{"locked": true}', encoding="utf-8")

    assert '"locked": true' in target.read_text(encoding="utf-8")


def test_file_lock_creates_and_cleans_up_lock_file(tmp_path: Path) -> None:
    target = tmp_path / "test.json"
    target.write_text("{}", encoding="utf-8")
    lock_path = target.with_suffix(".json.lock")

    with file_lock(target):
        assert lock_path.exists()

    assert not lock_path.exists()


def test_file_lock_creates_parent_directories_for_missing_targets(tmp_path: Path) -> None:
    target = tmp_path / "subdir" / "deep" / "test.json"

    with file_lock(target):
        assert target.parent.exists()
        target.write_text("{}", encoding="utf-8")

    assert target.exists()
