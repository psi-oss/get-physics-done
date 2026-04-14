"""Focused regressions for host-independent frontmatter path handling."""

from __future__ import annotations

import pytest

from gpd.core.frontmatter import _is_absolute_path


@pytest.mark.parametrize(
    ("path_text", "expected"),
    [
        ("/tmp/x", True),
        ("C:/tmp/x", True),
        (r"C:\tmp\x", True),
        (r"\\server\share\dir", True),
        ("C:tmp/x", False),
        (r"C:tmp\x", False),
        ("relative/path", False),
    ],
)
def test_is_absolute_path_is_host_independent(path_text: str, expected: bool) -> None:
    assert _is_absolute_path(path_text) is expected
