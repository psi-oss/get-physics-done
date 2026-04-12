from __future__ import annotations

from gpd.core.public_surface_contract import load_public_surface_contract


def test_public_surface_contract_smoke_surfaces_current_resume_authority_phrase() -> None:
    contract = load_public_surface_contract()

    intro = contract.resume_authority.public_vocabulary_intro
    assert intro
    assert "resume" in intro.lower()
    assert contract.resume_authority.public_fields
    assert all(field.isidentifier() for field in contract.resume_authority.public_fields)


def test_public_surface_contract_smoke_keeps_bridge_commands_and_named_commands_aligned() -> None:
    contract = load_public_surface_contract()

    assert contract.local_cli_bridge.commands == contract.local_cli_bridge.named_commands.ordered()
    assert all(command.startswith("gpd ") for command in contract.local_cli_bridge.commands)
    assert contract.local_cli_bridge.named_commands.help.startswith("gpd --help")
    assert contract.local_cli_bridge.named_commands.resume.startswith("gpd resume")

    assert "<runtime>" in contract.local_cli_bridge.install_local_example
    assert "gpd install" in contract.local_cli_bridge.install_local_example
    assert "<runtime>" in contract.local_cli_bridge.doctor_local_command
    assert "<runtime>" in contract.local_cli_bridge.doctor_global_command
    assert contract.local_cli_bridge.doctor_local_command.startswith("gpd doctor")
    assert contract.local_cli_bridge.doctor_global_command.startswith("gpd doctor")
    assert "gpd validate command-context" in contract.local_cli_bridge.validate_command_context_command
    assert "gpd:<name>" in contract.local_cli_bridge.validate_command_context_command
