"""Real-command review-contract compilation regressions across runtime wrappers."""

from __future__ import annotations

import pytest

from gpd import registry
from gpd.adapters.runtime_catalog import iter_runtime_descriptors
from gpd.core.review_contract_prompt import render_review_contract_prompt, review_contract_payload
from tests.adapters.review_contract_test_utils import (
    compile_review_contract_command_for_runtime,
    extract_review_contract_section,
)

REVIEW_COMMANDS = tuple(registry.list_review_commands())
REVIEW_COMMAND_SLUGS = tuple(command_name.removeprefix("gpd:") for command_name in REVIEW_COMMANDS)
RUNTIMES = tuple(descriptor.runtime_name for descriptor in iter_runtime_descriptors())


@pytest.mark.parametrize("command_name", REVIEW_COMMAND_SLUGS)
def test_registry_rendered_review_contract_matches_the_canonical_dataclass_payload(command_name: str) -> None:
    command = registry.get_command(command_name)
    contract = command.review_contract

    assert contract is not None
    expected_section = render_review_contract_prompt(review_contract_payload(contract))

    assert extract_review_contract_section(command.content) == expected_section
    assert command.content.count("## Review Contract") == 1


@pytest.mark.parametrize("command_name", REVIEW_COMMAND_SLUGS)
@pytest.mark.parametrize("runtime", RUNTIMES)
def test_real_review_command_sources_compile_across_runtime_wrappers_without_losing_review_contract(
    command_name: str,
    runtime: str,
) -> None:
    command = registry.get_command(command_name)
    contract = command.review_contract

    assert contract is not None
    expected_section = render_review_contract_prompt(review_contract_payload(contract))
    compiled = compile_review_contract_command_for_runtime(command_name, runtime)

    assert extract_review_contract_section(compiled) == expected_section
    assert compiled.count("## Review Contract") == 1
