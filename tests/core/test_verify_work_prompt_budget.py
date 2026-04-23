"""Prompt-budget assertions for the `verify-work` startup surface."""

from __future__ import annotations

from pathlib import Path

from tests.prompt_metrics_support import measure_prompt_surface

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_DIR = REPO_ROOT / "src" / "gpd" / "commands"
WORKFLOWS_DIR = REPO_ROOT / "src" / "gpd" / "specs" / "workflows"
SOURCE_ROOT = REPO_ROOT / "src" / "gpd"
PATH_PREFIX = "/runtime/"


def test_verify_work_command_only_eagerly_loads_the_workflow() -> None:
    command_text = (COMMANDS_DIR / "verify-work.md").read_text(encoding="utf-8")
    metrics = measure_prompt_surface(
        COMMANDS_DIR / "verify-work.md",
        src_root=SOURCE_ROOT,
        path_prefix=PATH_PREFIX,
    )

    assert metrics.raw_include_count == 1
    assert "@{GPD_INSTALL_DIR}/references/verification/core/verification-core.md" not in command_text
    assert "@{GPD_INSTALL_DIR}/templates/verification-report.md" not in command_text
    assert "@{GPD_INSTALL_DIR}/templates/contract-results-schema.md" not in command_text


def test_verify_work_workflow_defers_heavy_authorities_until_later_steps() -> None:
    workflow_text = (WORKFLOWS_DIR / "verify-work.md").read_text(encoding="utf-8")
    overlay_marker = "The verification overlay is written only after authoritative verifier output is available"
    report_owner_marker = "Keep the current check display, summary, and session overlay in sync with the verifier output. The canonical verifier report content remains owned by `gpd-verifier`."

    assert "<template>" not in workflow_text
    assert "<required_reading>" not in workflow_text
    assert "research-verification.md" not in workflow_text
    assert "verification-report.md" not in workflow_text
    assert "contract-results-schema.md" not in workflow_text
    assert "error-propagation-protocol.md" not in workflow_text
    assert report_owner_marker in workflow_text
    assert overlay_marker in workflow_text
    assert workflow_text.index(report_owner_marker) < workflow_text.index(overlay_marker)
