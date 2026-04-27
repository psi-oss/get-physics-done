"""Prompt metric helper assertions."""

from __future__ import annotations

from gpd.adapters.install_utils import parse_at_include_path
from tests.prompt_metrics_support import count_raw_includes


def test_count_raw_includes_matches_installer_include_line_forms() -> None:
    text = """
@{GPD_INSTALL_DIR}/references/plain.md
- @{GPD_INSTALL_DIR}/references/bulleted.md -- with label
- `@{GPD_INSTALL_DIR}/references/backticked.md` -- with label
1. `@{GPD_INSTALL_DIR}/references/numbered.md` (main workflow)
```markdown
@{GPD_INSTALL_DIR}/references/in-code-fence.md
```
Follow @{GPD_INSTALL_DIR}/references/inline.md
@GPD/project-local.md
@path/example.md
@article{key,
"""

    assert count_raw_includes(text) == 4


def test_prompt_metrics_uses_production_include_parser() -> None:
    assert parse_at_include_path("- `@{GPD_INSTALL_DIR}/references/numbered.md` (main workflow)") == (
        "{GPD_INSTALL_DIR}/references/numbered.md"
    )
    assert parse_at_include_path("@GPD/project-local.md") is None
    assert parse_at_include_path("@article{key,") is None
