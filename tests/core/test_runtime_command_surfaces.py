"""Tests for shared active-runtime command formatting."""

from __future__ import annotations

import importlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from gpd.adapters.runtime_catalog import iter_runtime_descriptors
from gpd.core import public_surface_contract as public_surface_contract_module
from gpd.core import runtime_command_surfaces as runtime_command_surfaces_module
from gpd.core.runtime_command_surfaces import format_active_runtime_command, resolve_active_runtime_descriptor


def test_format_active_runtime_command_uses_descriptor_public_surface(monkeypatch) -> None:
    descriptor = SimpleNamespace(
        runtime_name="runtime-a",
        public_command_surface_prefix="/public:",
        command_prefix="/adapter-only:",
    )
    monkeypatch.setattr(
        runtime_command_surfaces_module,
        "resolve_active_runtime_descriptor",
        lambda **kwargs: descriptor,
    )
    monkeypatch.setattr(
        "gpd.adapters.get_adapter",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("adapter formatting should not be used")),
    )

    assert format_active_runtime_command("help") == "/public:help"


def test_resolve_active_runtime_descriptor_normalizes_aliases_before_lookup() -> None:
    descriptor = next(
        item
        for item in iter_runtime_descriptors()
        if any(alias.casefold() != item.runtime_name.casefold() for alias in item.selection_aliases)
    )
    alias = descriptor.selection_aliases[0]

    resolved = resolve_active_runtime_descriptor(
        detect_runtime=lambda **kwargs: f"  {alias.upper()}  ",
    )

    assert resolved is not None
    assert resolved.runtime_name == descriptor.runtime_name


def test_active_runtime_command_prefix_rejects_descriptor_missing_public_surface(monkeypatch) -> None:
    descriptor = SimpleNamespace(
        runtime_name="runtime-a",
        public_command_surface_prefix="",
        command_prefix="/fallback:",
    )
    monkeypatch.setattr(
        public_surface_contract_module, "local_cli_install_local_example_command", lambda: "install stub"
    )
    monkeypatch.setattr(public_surface_contract_module, "local_cli_doctor_local_command", lambda: "doctor stub")
    monkeypatch.setattr(public_surface_contract_module, "local_cli_bridge_commands", lambda: ("bridge stub",))
    monkeypatch.setattr(
        public_surface_contract_module,
        "local_cli_validate_command_context_command",
        lambda: "validate stub",
    )
    cli_module = importlib.import_module("gpd.cli")
    monkeypatch.setattr(cli_module, "resolve_active_runtime_descriptor", lambda **kwargs: descriptor)

    with pytest.raises(ValueError, match="missing a public command surface prefix"):
        cli_module._active_runtime_command_prefix(cwd=Path("/tmp"))
