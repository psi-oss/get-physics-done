"""Regression tests for json_utils and git_ops bug fixes (audit round 4).

Fix 1: json_set returns an "error" key when the final set fails due to a
       type mismatch (e.g., trying to set a string key on a list).
Fix 2: _check_frontmatter no longer assigns to an unused ``meta`` variable.
"""

from __future__ import annotations

import json
from pathlib import Path

from gpd.core.git_ops import FileCheckDetail, _check_frontmatter
from gpd.core.json_utils import json_set

# ---------------------------------------------------------------------------
# Fix 1: json_set type-mismatch error key
# ---------------------------------------------------------------------------


class TestJsonSetTypeMismatchError:
    """json_set must include an 'error' key when updated is False."""

    def test_string_key_on_list_returns_error(self, tmp_path: Path) -> None:
        """Setting a dict-style key where the value is a list should fail
        with updated=False and include an 'error' key."""
        fp = tmp_path / "data.json"
        fp.write_text(json.dumps({"items": [1, 2, 3]}))
        result = json_set(str(fp), "items.foo", '"bar"')
        assert result["updated"] is False
        assert "error" in result

    def test_list_index_path_still_works(self, tmp_path: Path) -> None:
        """Normal list-index set should still succeed."""
        fp = tmp_path / "data.json"
        fp.write_text(json.dumps({"items": ["a", "b", "c"]}))
        result = json_set(str(fp), "items[1]", '"replaced"')
        assert result["updated"] is True
        data = json.loads(fp.read_text())
        assert data["items"][1] == "replaced"

    def test_error_key_absent_on_success(self, tmp_path: Path) -> None:
        """Successful json_set should NOT include an 'error' key."""
        fp = str(tmp_path / "ok.json")
        result = json_set(fp, "key", '"value"')
        assert result["updated"] is True
        assert "error" not in result


# ---------------------------------------------------------------------------
# Fix 2: _check_frontmatter unused meta variable
# ---------------------------------------------------------------------------


class TestCheckFrontmatter:
    """_check_frontmatter should validate frontmatter via extract_frontmatter."""

    def test_valid_frontmatter_sets_valid_true(self) -> None:
        content = "---\nstatus: active\n---\n\n# Title\n"
        detail = FileCheckDetail(file="test.md")
        _check_frontmatter(content, detail)
        assert detail.frontmatter_valid is True
        assert detail.warnings == []

    def test_invalid_frontmatter_sets_valid_false(self) -> None:
        content = "---\n: bad: yaml: [unclosed\n---\n\n# Oops\n"
        detail = FileCheckDetail(file="bad.md")
        _check_frontmatter(content, detail)
        assert detail.frontmatter_valid is False
        assert any("parse error" in w.lower() or "yaml" in w.lower() for w in detail.warnings)

    def test_no_frontmatter_still_valid(self) -> None:
        """Markdown with no frontmatter block is valid (returns empty dict)."""
        content = "# Just a heading\n\nSome text.\n"
        detail = FileCheckDetail(file="plain.md")
        _check_frontmatter(content, detail)
        assert detail.frontmatter_valid is True

    def test_empty_frontmatter_valid(self) -> None:
        content = "---\n---\n\nBody.\n"
        detail = FileCheckDetail(file="empty_fm.md")
        _check_frontmatter(content, detail)
        assert detail.frontmatter_valid is True
