"""Tests for the shared command token helpers."""

from __future__ import annotations

from gpd.adapters.command_tokens import is_gpd_command_start, is_gpd_token_end
from gpd.adapters.runtime_catalog import iter_runtime_descriptors

BOUNDARY_CONTEXTS = ["", " ", "\t", "| ", "; ", "( ", "&& ", "|| ", "$("]


def test_gpd_command_start_accepts_shell_boundaries() -> None:
    for context in BOUNDARY_CONTEXTS:
        line = f"{context}gpd"
        index = line.index("gpd")
        assert is_gpd_command_start(line, index)


def test_gpd_command_start_rejects_non_boundary() -> None:
    line = "agpd"
    index = line.index("gpd")
    assert not is_gpd_command_start(line, index)


def test_gpd_token_end_honors_terminators() -> None:
    terminators = [" ", "\t", "\n", '"', "'", "`", ";", "|", "&", ")", "<", ">"]
    for separator in terminators:
        line = f"gpd{separator}"
        end_index = len("gpd")
        assert is_gpd_token_end(line, end_index)

    assert not is_gpd_token_end("gpdX", len("gpd"))


def _collect_runtime_command_tokens() -> list[str]:
    tokens: set[str] = set()
    for descriptor in iter_runtime_descriptors():
        tokens.add(descriptor.command_prefix)
        tokens.add(descriptor.install_flag)
        tokens.update(descriptor.selection_flags)
        tokens.update(descriptor.selection_aliases)
    return sorted(token for token in tokens if token)


def test_catalog_commands_preserve_gpd_boundaries() -> None:
    tokens = _collect_runtime_command_tokens()
    for token in tokens:
        line = f"gpd {token}"
        index = line.index("gpd")
        assert is_gpd_command_start(line, index)
        assert is_gpd_token_end(line, index + len("gpd"))
