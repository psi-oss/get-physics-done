"""Prompt metric helper assertions."""

from __future__ import annotations

from gpd.adapters.install_utils import expand_at_includes, parse_at_include_path
from tests.prompt_metrics_support import count_raw_includes, count_unfenced_heading


def test_count_raw_includes_matches_installer_include_line_forms() -> None:
    text = """
@{GPD_INSTALL_DIR}/references/plain.md
- @{GPD_INSTALL_DIR}/references/bulleted.md -- with label
- `@{GPD_INSTALL_DIR}/references/backticked.md` -- with label
1. `@{GPD_INSTALL_DIR}/references/numbered.md` (main workflow)
```markdown
@{GPD_INSTALL_DIR}/references/in-code-fence.md
```
~~~markdown
@{GPD_INSTALL_DIR}/references/in-tilde-fence.md
~~~
Follow @{GPD_INSTALL_DIR}/references/inline.md
@GPD/project-local.md
@path/example.md
@article{key,
"""

    assert count_raw_includes(text) == 2


def test_expand_at_includes_ignores_tilde_fenced_paths(tmp_path) -> None:
    include_path = tmp_path / "references" / "plain.md"
    include_path.parent.mkdir()
    include_path.write_text("# Included\n\nLoaded body.\n", encoding="utf-8")
    text = """
~~~markdown
@{GPD_INSTALL_DIR}/references/plain.md
~~~
@{GPD_INSTALL_DIR}/references/plain.md
"""

    expanded = expand_at_includes(text, tmp_path, "/runtime/")

    assert expanded.count("<!-- [included: plain.md] -->") == 1
    assert "~~~markdown\n@{GPD_INSTALL_DIR}/references/plain.md\n~~~" in expanded


def test_count_raw_includes_ignores_lightweight_reference_list_paths() -> None:
    text = """
- `{GPD_INSTALL_DIR}/references/shared/shared-protocols.md` -- metadata-only path mention
- `@{GPD_INSTALL_DIR}/references/orchestration/agent-infrastructure.md` -- metadata-only path mention
"""

    assert parse_at_include_path("- `{GPD_INSTALL_DIR}/references/shared/shared-protocols.md` -- path") is None
    assert parse_at_include_path("- `@{GPD_INSTALL_DIR}/references/orchestration/agent-infrastructure.md` -- path") is None
    assert count_raw_includes(text) == 0


def test_prompt_metrics_uses_production_include_parser() -> None:
    assert parse_at_include_path("- `@{GPD_INSTALL_DIR}/references/numbered.md` (main workflow)") is None
    assert parse_at_include_path("- @{GPD_INSTALL_DIR}/references/bulleted.md -- with label") == (
        "{GPD_INSTALL_DIR}/references/bulleted.md"
    )
    assert parse_at_include_path("@GPD/project-local.md") is None
    assert parse_at_include_path("@article{key,") is None


def test_count_unfenced_heading_ignores_example_blocks() -> None:
    text = """
## Outside

```markdown
## Outside
## Inside Only
```

~~~markdown
## Outside
## Tilde Inside Only
~~~

## Outside
"""

    assert count_unfenced_heading(text, "## Outside") == 2
    assert count_unfenced_heading(text, "## Inside Only") == 0
    assert count_unfenced_heading(text, "## Tilde Inside Only") == 0
