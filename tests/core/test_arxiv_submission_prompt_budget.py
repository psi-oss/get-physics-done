"""Prompt budget regression tests for the `arxiv-submission` startup surface."""

from __future__ import annotations

from pathlib import Path

from tests.prompt_metrics_support import measure_prompt_surface

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_DIR = REPO_ROOT / "src" / "gpd" / "commands"
WORKFLOWS_DIR = REPO_ROOT / "src" / "gpd" / "specs" / "workflows"
SOURCE_ROOT = REPO_ROOT / "src" / "gpd"
PATH_PREFIX = "/runtime/"


def test_arxiv_submission_command_stays_thin_and_only_eagerly_loads_the_workflow() -> None:
    command_text = (COMMANDS_DIR / "arxiv-submission.md").read_text(encoding="utf-8")
    metrics = measure_prompt_surface(
        COMMANDS_DIR / "arxiv-submission.md",
        src_root=SOURCE_ROOT,
        path_prefix=PATH_PREFIX,
    )
    workflow = measure_prompt_surface(
        WORKFLOWS_DIR / "arxiv-submission.md",
        src_root=SOURCE_ROOT,
        path_prefix=PATH_PREFIX,
    )

    assert metrics.raw_include_count == 1
    assert "@{GPD_INSTALL_DIR}/workflows/arxiv-submission.md" in command_text
    assert "Keep the wrapper thin and let the workflow own validation, packaging, and submission-gate details." in command_text
    assert "Paper target: $ARGUMENTS (optional; when omitted, the workflow resolves the manuscript root)." in command_text
    assert "@{GPD_INSTALL_DIR}/templates/paper/publication-manuscript-root-preflight.md" not in command_text
    assert "@{GPD_INSTALL_DIR}/references/publication/publication-review-round-artifacts.md" not in command_text
    assert "@{GPD_INSTALL_DIR}/references/publication/publication-response-artifacts.md" not in command_text
    assert "@{GPD_INSTALL_DIR}/references/publication/peer-review-reliability.md" not in command_text
    assert "@{GPD_INSTALL_DIR}/references/publication/publication-bootstrap-preflight.md" not in command_text
    assert "@{GPD_INSTALL_DIR}/references/shared/canonical-schema-discipline.md" not in command_text
    assert "@{GPD_INSTALL_DIR}/templates/paper/paper-config-schema.md" not in command_text
    assert "@{GPD_INSTALL_DIR}/templates/paper/artifact-manifest-schema.md" not in command_text
    assert "@{GPD_INSTALL_DIR}/templates/paper/bibliography-audit-schema.md" not in command_text
    assert "@{GPD_INSTALL_DIR}/templates/paper/review-ledger-schema.md" not in command_text
    assert "@{GPD_INSTALL_DIR}/templates/paper/referee-decision-schema.md" not in command_text
    assert metrics.expanded_line_count > workflow.expanded_line_count
    assert metrics.expanded_char_count > workflow.expanded_char_count
    assert metrics.expanded_line_count < workflow.expanded_line_count + 180
    assert metrics.expanded_char_count < workflow.expanded_char_count + 9000
