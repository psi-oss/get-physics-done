"""Registry-wide expanded prompt budget coverage for commands."""

from __future__ import annotations

from pathlib import Path

import pytest

from gpd import registry
from tests.prompt_metrics_support import measure_prompt_surface

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_DIR = REPO_ROOT / "src" / "gpd" / "commands"
SOURCE_ROOT = REPO_ROOT / "src" / "gpd"
PATH_PREFIX = "/runtime/"

MAX_COMMAND_RAW_INCLUDES = 4
MAX_COMMAND_LINES = 3_000
MAX_COMMAND_CHARS = 150_000
COMMAND_NAMES = tuple(registry.list_commands())


def test_command_prompt_budget_registry_covers_all_command_sources() -> None:
    assert set(COMMAND_NAMES) == {path.stem for path in COMMANDS_DIR.glob("*.md")}


@pytest.mark.parametrize("command_name", COMMAND_NAMES)
def test_expanded_command_prompt_stays_under_registry_budget(command_name: str) -> None:
    metrics = measure_prompt_surface(
        COMMANDS_DIR / f"{command_name}.md",
        src_root=SOURCE_ROOT,
        path_prefix=PATH_PREFIX,
    )

    assert metrics.raw_include_count <= MAX_COMMAND_RAW_INCLUDES
    assert metrics.expanded_line_count <= MAX_COMMAND_LINES
    assert metrics.expanded_char_count <= MAX_COMMAND_CHARS
