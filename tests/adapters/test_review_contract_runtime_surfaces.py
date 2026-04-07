from __future__ import annotations

from pathlib import Path

import pytest

from gpd import registry
from gpd.adapters.install_utils import project_markdown_for_runtime
from gpd.adapters.runtime_catalog import iter_runtime_descriptors
from tests.adapters.review_contract_test_utils import extract_review_contract_section

RUNTIMES = tuple(descriptor.runtime_name for descriptor in iter_runtime_descriptors())
REVIEW_COMMANDS = tuple(command_name.removeprefix("gpd:") for command_name in registry.list_review_commands())


def _transform_registry_command_content(command_name: str, runtime: str) -> str:
    content = registry.get_command(command_name).content
    return project_markdown_for_runtime(
        content,
        runtime=runtime,
        path_prefix="/runtime/",
        src_root=Path(__file__).resolve().parents[2] / "src/gpd",
        command_name=command_name,
    )


@pytest.mark.parametrize(
    "command_name",
    REVIEW_COMMANDS,
)
@pytest.mark.parametrize("runtime", RUNTIMES)
def test_review_contract_section_matches_registry_across_runtime_wrappers(
    command_name: str,
    runtime: str,
) -> None:
    expected_section = extract_review_contract_section(registry.get_command(command_name).content)
    transformed_content = _transform_registry_command_content(command_name, runtime)

    assert extract_review_contract_section(transformed_content) == expected_section
    assert transformed_content.count("## Review Contract") == 1
