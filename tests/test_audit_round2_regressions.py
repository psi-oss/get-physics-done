"""Regression tests for bug fixes found in the second 12-agent codebase audit.

Each test targets a specific bug fix and verifies the corrected behavior.
"""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Bug 1: Escaped pipe parsing in error catalog tables
# ---------------------------------------------------------------------------


class TestEscapedPipeParsing:
    """_parse_table_rows must split on unescaped pipes only and unescape \\| to |."""

    def test_escaped_pipe_produces_correct_cell_count(self) -> None:
        from gpd.mcp.servers.errors_mcp import _parse_table_rows

        body = "| 1 | Foo \\| Bar | Baz |"
        rows = _parse_table_rows(body)
        assert len(rows) == 1
        assert len(rows[0]) == 3

    def test_escaped_pipe_unescaped_in_cell_content(self) -> None:
        from gpd.mcp.servers.errors_mcp import _parse_table_rows

        body = "| 1 | Foo \\| Bar | Baz |"
        rows = _parse_table_rows(body)
        cells = rows[0]
        assert cells[0] == "1"
        assert cells[1] == "Foo | Bar"
        assert cells[2] == "Baz"

    def test_multiple_escaped_pipes_in_one_cell(self) -> None:
        from gpd.mcp.servers.errors_mcp import _parse_table_rows

        body = "| A \\| B \\| C | D |"
        rows = _parse_table_rows(body)
        assert len(rows[0]) == 2
        assert rows[0][0] == "A | B | C"
        assert rows[0][1] == "D"

    def test_separator_lines_are_skipped(self) -> None:
        from gpd.mcp.servers.errors_mcp import _parse_table_rows

        body = "| Header1 | Header2 |\n|---|---|\n| val1 | val2 |"
        rows = _parse_table_rows(body)
        # Header + data = 2 rows (separator skipped)
        assert len(rows) == 2

    def test_no_escaped_pipe_normal_split(self) -> None:
        from gpd.mcp.servers.errors_mcp import _parse_table_rows

        body = "| A | B | C | D |"
        rows = _parse_table_rows(body)
        assert len(rows) == 1
        assert len(rows[0]) == 4


# ---------------------------------------------------------------------------
# Bug 2: Checkbox regex word boundary in phases.py
# ---------------------------------------------------------------------------


class TestCheckboxWordBoundary:
    """Phase 1 checkbox should not match Phase 10."""

    def _make_project(self, tmp_path: Path, roadmap_content: str) -> Path:
        """Set up a minimal GPD project with the given roadmap content."""
        gpd_dir = tmp_path / ".gpd"
        gpd_dir.mkdir()
        phases_dir = gpd_dir / "phases"
        phases_dir.mkdir()
        roadmap = gpd_dir / "ROADMAP.md"
        roadmap.write_text(roadmap_content, encoding="utf-8")
        return tmp_path

    def test_phase1_not_matched_by_phase10(self, tmp_path: Path) -> None:
        from gpd.core.phases import roadmap_analyze

        roadmap = (
            "# Roadmap\n\n"
            "- [ ] Phase 1: Setup\n"
            "- [x] Phase 10: Final\n\n"
            "## Phase 1: Setup\n\n"
            "**Goal:** Setup things\n"
            "**Depends on:** None\n\n"
            "## Phase 10: Final\n\n"
            "**Goal:** Wrap up\n"
            "**Depends on:** Phase 9\n"
        )
        cwd = self._make_project(tmp_path, roadmap)
        result = roadmap_analyze(cwd)

        phase1 = next((p for p in result.phases if p.number == "1"), None)
        phase10 = next((p for p in result.phases if p.number == "10"), None)

        assert phase1 is not None, "Phase 1 should be parsed"
        assert phase10 is not None, "Phase 10 should be parsed"
        assert phase1.roadmap_complete is False, "Phase 1 is unchecked"
        assert phase10.roadmap_complete is True, "Phase 10 is checked"

    def test_phase1_checked_independently_of_phase10(self, tmp_path: Path) -> None:
        from gpd.core.phases import roadmap_analyze

        roadmap = (
            "# Roadmap\n\n"
            "- [x] Phase 1: Setup\n"
            "- [ ] Phase 10: Final\n\n"
            "## Phase 1: Setup\n\n"
            "**Goal:** Setup\n\n"
            "## Phase 10: Final\n\n"
            "**Goal:** Final\n"
        )
        cwd = self._make_project(tmp_path, roadmap)
        result = roadmap_analyze(cwd)

        phase1 = next((p for p in result.phases if p.number == "1"), None)
        phase10 = next((p for p in result.phases if p.number == "10"), None)

        assert phase1 is not None
        assert phase10 is not None
        assert phase1.roadmap_complete is True
        assert phase10.roadmap_complete is False


# ---------------------------------------------------------------------------
# Bug 3: None slug in phase directory names
# ---------------------------------------------------------------------------


class TestNoneSlugDirectory:
    """When generate_slug returns None the dir name must NOT contain 'None'."""

    def _make_project(self, tmp_path: Path) -> Path:
        gpd_dir = tmp_path / ".gpd"
        gpd_dir.mkdir()
        phases_dir = gpd_dir / "phases"
        phases_dir.mkdir()
        roadmap = gpd_dir / "ROADMAP.md"
        roadmap.write_text(
            "# Roadmap\n\n## Phase 1: Existing\n\n"
            "**Goal:** Existing phase\n"
            "**Depends on:** None\n",
            encoding="utf-8",
        )
        return tmp_path

    def test_dir_name_no_none_string_when_slug_is_none(self, tmp_path: Path) -> None:
        from gpd.core.phases import phase_add

        cwd = self._make_project(tmp_path)

        with patch("gpd.core.phases.generate_slug", return_value=None):
            result = phase_add(cwd, "!!!")

        assert "None" not in result.directory, (
            f"Directory should not contain literal 'None', got: {result.directory}"
        )
        # The directory on disk should also not contain "None"
        phases_dir = tmp_path / ".gpd" / "phases"
        created_dirs = [d.name for d in phases_dir.iterdir() if d.is_dir()]
        for d in created_dirs:
            assert "None" not in d, f"Directory name on disk contains 'None': {d}"


# ---------------------------------------------------------------------------
# Bug 4: "Phase 0" depends-on for first phase
# ---------------------------------------------------------------------------


class TestPhaseZeroDependsOn:
    """Adding the first phase to an empty roadmap should say depends-on None, not Phase 0."""

    def test_first_phase_depends_on_none(self, tmp_path: Path) -> None:
        from gpd.core.phases import phase_add

        gpd_dir = tmp_path / ".gpd"
        gpd_dir.mkdir()
        phases_dir = gpd_dir / "phases"
        phases_dir.mkdir()
        roadmap = gpd_dir / "ROADMAP.md"
        roadmap.write_text("# Roadmap\n\n", encoding="utf-8")

        result = phase_add(cwd=tmp_path, description="First phase")

        assert result.phase_number == 1

        updated_roadmap = roadmap.read_text(encoding="utf-8")
        assert "**Depends on:** None" in updated_roadmap
        assert "Phase 0" not in updated_roadmap


# ---------------------------------------------------------------------------
# Bug 5: Symmetry check substring matching
# ---------------------------------------------------------------------------


class TestSymmetrySubstringMatching:
    """Short symmetry names like 'T' must not substring-match longer strategy keys."""

    def test_T_does_not_match_lorentz(self) -> None:
        from gpd.mcp.servers.verification_server import _symmetry_check_inner

        result = _symmetry_check_inner("some expression", ["T"])
        sym_result = result["results"][0]

        # "T" is only 1 character, shorter than the minimum length of 3 for
        # substring matching. It should NOT match "lorentz".
        matched = sym_result.get("matched_type")
        assert matched != "lorentz", (
            f"Symmetry 'T' incorrectly matched strategy for '{matched}'"
        )

    def test_short_symmetry_C_does_not_match_conformal(self) -> None:
        from gpd.mcp.servers.verification_server import _symmetry_check_inner

        result = _symmetry_check_inner("some expression", ["C"])
        sym_result = result["results"][0]
        matched = sym_result.get("matched_type")
        assert matched != "conformal", (
            f"Symmetry 'C' incorrectly matched strategy for '{matched}'"
        )

    def test_full_name_lorentz_still_matches(self) -> None:
        from gpd.mcp.servers.verification_server import _symmetry_check_inner

        result = _symmetry_check_inner("some expression", ["Lorentz invariance"])
        sym_result = result["results"][0]
        matched = sym_result.get("matched_type")
        assert matched == "lorentz"

    def test_parity_matches_correctly(self) -> None:
        from gpd.mcp.servers.verification_server import _symmetry_check_inner

        result = _symmetry_check_inner("some expression", ["parity"])
        sym_result = result["results"][0]
        assert sym_result["matched_type"] == "parity"


# ---------------------------------------------------------------------------
# Bug 6: safe_read_file UnicodeDecodeError
# ---------------------------------------------------------------------------


class TestSafeReadFileBinary:
    """safe_read_file should return None for files with invalid UTF-8 bytes."""

    def test_returns_none_for_binary_file(self, tmp_path: Path) -> None:
        from gpd.core.utils import safe_read_file

        binary_file = tmp_path / "data.bin"
        binary_file.write_bytes(b"\x80\x81\x82\xff\xfe")

        result = safe_read_file(binary_file)
        assert result is None

    def test_returns_none_for_nonexistent_file(self, tmp_path: Path) -> None:
        from gpd.core.utils import safe_read_file

        result = safe_read_file(tmp_path / "no_such_file.txt")
        assert result is None

    def test_returns_content_for_valid_utf8(self, tmp_path: Path) -> None:
        from gpd.core.utils import safe_read_file

        valid_file = tmp_path / "valid.txt"
        valid_file.write_text("hello world", encoding="utf-8")

        result = safe_read_file(valid_file)
        assert result == "hello world"

    def test_returns_none_for_directory(self, tmp_path: Path) -> None:
        from gpd.core.utils import safe_read_file

        result = safe_read_file(tmp_path)
        assert result is None


# ---------------------------------------------------------------------------
# Bug 7: ResultNotFoundError.__str__ should not have surrounding quotes
# ---------------------------------------------------------------------------


class TestResultNotFoundErrorStr:
    """str(ResultNotFoundError('R-1')) should not have KeyError-style surrounding quotes."""

    def test_str_has_no_surrounding_single_quotes(self) -> None:
        from gpd.core.errors import ResultNotFoundError

        err = ResultNotFoundError("R-1")
        s = str(err)
        assert s == 'Result "R-1" not found'
        # Specifically, it must NOT be wrapped in additional single quotes
        # like KeyError does: "'Result \"R-1\" not found'"
        assert not s.startswith("'"), f"str() has leading quote: {s!r}"
        assert not s.endswith("'"), f"str() has trailing quote: {s!r}"

    def test_str_matches_exception_str(self) -> None:
        from gpd.core.errors import ResultNotFoundError

        err = ResultNotFoundError("R-1")
        # The fix delegates to Exception.__str__ explicitly
        assert str(err) == Exception.__str__(err)

    def test_result_id_attribute(self) -> None:
        from gpd.core.errors import ResultNotFoundError

        err = ResultNotFoundError("R-1")
        assert err.result_id == "R-1"

    def test_is_key_error(self) -> None:
        from gpd.core.errors import ResultNotFoundError

        err = ResultNotFoundError("R-1")
        assert isinstance(err, KeyError)

    def test_key_error_str_differs(self) -> None:
        """KeyError.__str__ wraps the message in quotes; our __str__ must not."""
        from gpd.core.errors import ResultNotFoundError

        err = ResultNotFoundError("R-1")
        key_str = KeyError.__str__(err)
        our_str = str(err)
        # KeyError adds quotes; our override should strip them
        assert our_str != key_str
