"""Prompt budget assertions for the `respond-to-referees` startup surface."""

from __future__ import annotations

from pathlib import Path

from tests.prompt_metrics_support import measure_prompt_surface

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_DIR = REPO_ROOT / "src" / "gpd" / "commands"
WORKFLOWS_DIR = REPO_ROOT / "src" / "gpd" / "specs" / "workflows"
SOURCE_ROOT = REPO_ROOT / "src" / "gpd"
PATH_PREFIX = "/runtime/"


def test_respond_to_referees_command_stays_thin_and_only_eagerly_loads_the_workflow() -> None:
    command_text = (COMMANDS_DIR / "respond-to-referees.md").read_text(encoding="utf-8")
    metrics = measure_prompt_surface(
        COMMANDS_DIR / "respond-to-referees.md",
        src_root=SOURCE_ROOT,
        path_prefix=PATH_PREFIX,
    )
    workflow = measure_prompt_surface(
        WORKFLOWS_DIR / "respond-to-referees.md",
        src_root=SOURCE_ROOT,
        path_prefix=PATH_PREFIX,
    )

    assert metrics.raw_include_count <= 2
    assert "@{GPD_INSTALL_DIR}/workflows/respond-to-referees.md" in command_text
    assert "Keep the wrapper focused on referee triage, revision routing, and synchronized response artifacts while the workflow owns the full revision pipeline." in command_text
    assert "@{GPD_INSTALL_DIR}/references/publication/publication-review-wrapper-guidance.md" in command_text
    assert "@{GPD_INSTALL_DIR}/templates/paper/publication-manuscript-root-preflight.md" not in command_text
    assert "@{GPD_INSTALL_DIR}/references/publication/publication-review-round-artifacts.md" not in command_text
    assert "@{GPD_INSTALL_DIR}/references/publication/publication-response-artifacts.md" not in command_text
    assert "@{GPD_INSTALL_DIR}/references/publication/peer-review-reliability.md" not in command_text
    assert "@{GPD_INSTALL_DIR}/templates/paper/publication-manuscript-root-preflight.md" not in command_text
    assert "@{GPD_INSTALL_DIR}/references/shared/canonical-schema-discipline.md" not in command_text
    assert "@{GPD_INSTALL_DIR}/templates/paper/review-ledger-schema.md" not in command_text
    assert "@{GPD_INSTALL_DIR}/templates/paper/referee-decision-schema.md" not in command_text
    assert "Follow the included respond-to-referees workflow exactly." in command_text
    assert metrics.expanded_line_count > workflow.expanded_line_count
    assert metrics.expanded_char_count > workflow.expanded_char_count
    assert metrics.expanded_line_count < workflow.expanded_line_count + 120
    assert metrics.expanded_char_count < workflow.expanded_char_count + 7000
