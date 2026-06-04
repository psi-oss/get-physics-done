from __future__ import annotations

from pathlib import Path

from gpd.registry import get_command
from tests.assertion_taxonomy_support import assert_prompt_contracts, semantic_concept

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_DIR = REPO_ROOT / "src" / "gpd" / "commands"
WORKFLOWS_DIR = REPO_ROOT / "src" / "gpd" / "specs" / "workflows"


def test_historical_roast_command_is_registered_with_single_roaster_spec_argument() -> None:
    command = get_command("historical-roast")

    assert command.name == "gpd:historical-roast"
    assert command.context_mode == "project-aware"
    assert command.argument_hint == '"<historical physicist[, physicist...]>" [target]'
    assert "web_search" in command.allowed_tools
    assert "web_fetch" in command.allowed_tools
    assert command.help is not None
    assert command.help.display_signature == 'gpd:historical-roast "<historical physicist[, physicist...]>" [target]'


def test_historical_roast_prompt_uses_comma_panel_not_flags() -> None:
    command_text = (COMMANDS_DIR / "historical-roast.md").read_text(encoding="utf-8")
    workflow_text = (WORKFLOWS_DIR / "historical-roast.md").read_text(encoding="utf-8")

    assert_prompt_contracts(
        command_text,
        *semantic_concept(
            "historical-roast command contract",
            required=(
                "@{GPD_INSTALL_DIR}/workflows/historical-roast.md",
                "comma-separated list",
                "Do not use separate `--reviewer` or `--panel` flags",
                "comma-separated name activates panel mode",
                "one roaster spec",
                "source-backed dossiers",
            ),
        ),
    )

    assert_prompt_contracts(
        workflow_text,
        *semantic_concept(
            "historical-roast workflow comma parsing",
            required=(
                'gpd:historical-roast "Noether, Feynman, Dirac" path/to/target',
                "split roaster spec on commas",
                "two or more names",
                "panel mode",
            ),
        ),
    )


def test_historical_roast_workflow_keeps_auxiliary_roast_boundary() -> None:
    workflow_text = (WORKFLOWS_DIR / "historical-roast.md").read_text(encoding="utf-8")

    assert_prompt_contracts(
        workflow_text,
        *semantic_concept(
            "historical-roast auxiliary boundary",
            required=(
                "not `gpd:peer-review`",
                "does not write `REFEREE-DECISION.json`",
                "GPD/historical-roast/{run-slug}/HISTORICAL-ROAST.md",
                "Use `web_search`",
                "Do not fabricate",
                "direct quotes",
            ),
        ),
    )
