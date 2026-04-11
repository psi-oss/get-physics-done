"""Regression guard for package-data command <-> workflow delegation."""

from __future__ import annotations

import re
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
COMMANDS_DIR = REPO_ROOT / "src" / "gpd" / "commands"
WORKFLOWS_DIR = REPO_ROOT / "src" / "gpd" / "specs" / "workflows"


def _delegated_stem_names() -> tuple[str, ...]:
    readme = (TESTS_DIR / "README.md").read_text(encoding="utf-8")
    pattern = re.compile(
        r"<!-- repo-graph-same-stem-command-workflow:start -->\n"
        r"- `src/gpd/commands/{(?P<names>[^}]*)}\.md -> src/gpd/specs/workflows/{same stems}\.md`\n"
        r"<!-- repo-graph-same-stem-command-workflow:end -->"
    )
    match = pattern.search(readme)
    if match is None:
        raise AssertionError("README lacks repo-graph same-stem command workflow block")

    stems = [stem.strip() for stem in match.group("names").split(",") if stem.strip()]
    if not stems:
        raise AssertionError("README command-workflow delegation list is empty")

    return tuple(stems)


def test_package_data_reuses_same_stem_command_workflows() -> None:
    """Ensure each documented same-stem command has matching workflow data."""

    for stem in _delegated_stem_names():
        command_path = COMMANDS_DIR / f"{stem}.md"
        workflow_path = WORKFLOWS_DIR / f"{stem}.md"

        assert command_path.is_file(), f"Missing command spec for {stem}"
        assert workflow_path.is_file(), f"Missing workflow spec for {stem}"
