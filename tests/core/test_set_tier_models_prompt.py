from __future__ import annotations

from pathlib import Path

from gpd.registry import get_command, list_commands

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_DIR = REPO_ROOT / "src" / "gpd" / "commands"
WORKFLOWS_DIR = REPO_ROOT / "src" / "gpd" / "specs" / "workflows"


def test_set_tier_models_command_is_registered_and_projectless() -> None:
    assert "set-tier-models" in list_commands()
    command = get_command("gpd:set-tier-models")
    assert command.name == "gpd:set-tier-models"
    assert command.context_mode == "projectless"


def test_set_tier_models_command_references_workflow() -> None:
    command_prompt = (COMMANDS_DIR / "set-tier-models.md").read_text(encoding="utf-8")
    assert "@{GPD_INSTALL_DIR}/workflows/set-tier-models.md" in command_prompt
    assert "changes only `model_overrides.<runtime>`" in command_prompt
    assert "gpd:set-profile" in command_prompt
    assert "gpd:settings" in command_prompt


def test_set_tier_models_workflow_keeps_scope_and_tradeoffs_explicit() -> None:
    workflow = (WORKFLOWS_DIR / "set-tier-models.md").read_text(encoding="utf-8")

    for fragment in (
        "tier-1",
        "tier-2",
        "tier-3",
        "strongest reasoning / highest capability, usually highest cost",
        "balanced default",
        "fastest / most economical",
        "Use runtime defaults (Recommended)",
        "Leave current setting unchanged",
        "Pin exact tier models",
        "changes only the concrete runtime-native model IDs",
        "Do **not** change:",
        "`model_profile`",
        "`execution.review_cadence`",
        "verify the updated tier mapping in `GPD/config.json`",
    ):
        assert fragment in workflow


def test_set_tier_models_workflow_does_not_reference_removed_resolve_model_wrapper() -> None:
    workflow = (WORKFLOWS_DIR / "set-tier-models.md").read_text(encoding="utf-8")

    assert "gpd resolve-model" not in workflow
