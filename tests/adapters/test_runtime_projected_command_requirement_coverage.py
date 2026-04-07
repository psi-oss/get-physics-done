"""Fast coverage for runtime-projected command requirement wrappers."""

from __future__ import annotations

from pathlib import Path

import pytest

from gpd import registry
from gpd.adapters.install_utils import project_markdown_for_runtime
from gpd.adapters.runtime_catalog import iter_runtime_descriptors
from gpd.core.model_visible_text import command_visibility_note

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_DIR = REPO_ROOT / "src/gpd/commands"
RUNTIMES = tuple(descriptor.runtime_name for descriptor in iter_runtime_descriptors())
COMMANDS_WITH_REQUIREMENTS = tuple(
    command_name for command_name in registry.list_commands() if registry.get_command(command_name).requires
)
REVIEW_COMMANDS = set(registry.list_review_commands())


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _project_command(command_name: str, runtime: str) -> str:
    projected = project_markdown_for_runtime(
        _read(COMMANDS_DIR / f"{command_name}.md"),
        runtime=runtime,
        path_prefix="/runtime/",
        src_root=REPO_ROOT / "src/gpd",
        protect_agent_prompt_body=False,
        command_name=command_name,
    )

    assert isinstance(projected, str)
    return projected


@pytest.mark.parametrize("runtime", RUNTIMES)
@pytest.mark.parametrize("command_name", COMMANDS_WITH_REQUIREMENTS)
def test_runtime_projected_commands_keep_requirements_visible(command_name: str, runtime: str) -> None:
    command = registry.get_command(command_name)
    projected = _project_command(command_name, runtime)

    assert command_visibility_note() in projected
    assert projected.count("## Command Requirements") == 1

    for require_key, require_value in command.requires.items():
        assert str(require_key) in projected
        if isinstance(require_value, list):
            for item in require_value:
                assert str(item) in projected
        else:
            assert str(require_value) in projected


@pytest.mark.parametrize("runtime", RUNTIMES)
@pytest.mark.parametrize("command_name", tuple(name for name in COMMANDS_WITH_REQUIREMENTS if name in REVIEW_COMMANDS))
def test_runtime_projected_review_commands_keep_requirements_before_review_contract(
    command_name: str,
    runtime: str,
) -> None:
    projected = _project_command(command_name, runtime)

    assert "## Command Requirements" in projected
    assert "## Review Contract" in projected
    assert projected.index("## Command Requirements") < projected.index("## Review Contract")
