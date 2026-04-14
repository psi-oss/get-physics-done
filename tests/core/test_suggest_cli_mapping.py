"""Coverage for suggest local CLI command mappings."""

from gpd.core import suggest as suggest_module
from gpd.core.public_surface_contract import local_cli_resume_command


def test_suggest_local_cli_resume_uses_public_surface_contract() -> None:
    assert suggest_module._format_local_cli_command("resume") == local_cli_resume_command()
    assert suggest_module._format_local_cli_command("resume-work") == local_cli_resume_command()
