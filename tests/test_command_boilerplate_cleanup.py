"""Regression test for command prompt boilerplate cleanup."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
COMMANDS_DIR = REPO_ROOT / "src" / "gpd" / "commands"

LEGACY_COMMENT_FRAGMENTS = (
    "Tool names and @ includes are platform-specific.",
    "Allowed-tools are runtime-specific.",
)


def test_command_sources_do_not_keep_runtime_boilerplate_html_comments() -> None:
    for path in sorted(COMMANDS_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        for fragment in LEGACY_COMMENT_FRAGMENTS:
            assert fragment not in text, f"{path.relative_to(REPO_ROOT)} still contains: {fragment}"
