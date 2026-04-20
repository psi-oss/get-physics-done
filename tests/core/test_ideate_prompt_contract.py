"""Focused phase-2 contract guardrails for the ideate command/workflow surface."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_DIR = REPO_ROOT / "src" / "gpd" / "commands"
WORKFLOWS_DIR = REPO_ROOT / "src" / "gpd" / "specs" / "workflows"
IDEATE_COMMAND_PATH = COMMANDS_DIR / "ideate.md"
IDEATE_WORKFLOW_PATH = WORKFLOWS_DIR / "ideate.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _contains_any(content: str, *phrases: str) -> bool:
    return any(phrase in content for phrase in phrases)


def _contains_any_lower(content: str, *phrases: str) -> bool:
    lowered = content.lower()
    return any(phrase.lower() in lowered for phrase in phrases)


def _phase2_round_loop_is_documented(command: str, workflow: str) -> bool:
    return _contains_any_lower(
        workflow,
        "continue to next round",
        "add my thoughts",
        "review raw round",
        "pause/stop",
        "pause or stop",
    )


def test_ideate_surfaces_land_together() -> None:
    assert IDEATE_COMMAND_PATH.exists() == IDEATE_WORKFLOW_PATH.exists()


def test_ideate_command_is_registered_and_projectless_when_present() -> None:
    if not IDEATE_COMMAND_PATH.exists():
        pytest.skip("ideate command/workflow has not landed yet")

    raw_command = _read(IDEATE_COMMAND_PATH)

    assert "name: gpd:ideate" in raw_command
    assert "@{GPD_INSTALL_DIR}/workflows/ideate.md" in raw_command
    assert "context_mode: projectless" in raw_command
    assert "allowed-tools:" in raw_command
    for tool in ("ask_user", "file_read", "shell"):
        assert f"  - {tool}" in raw_command


def test_ideate_phase2_command_keeps_launch_plus_round_loop_contract_when_present() -> None:
    if not IDEATE_COMMAND_PATH.exists():
        pytest.skip("ideate phase-2 command/workflow has not landed yet")

    command = _read(IDEATE_COMMAND_PATH)
    workflow = _read(IDEATE_WORKFLOW_PATH)

    if not _phase2_round_loop_is_documented(command, workflow):
        pytest.skip("ideate phase-2 round loop has not landed yet")

    assert _contains_any_lower(command, "launch summary", "launch brief", "launch packet")
    assert _contains_any_lower(
        command,
        "multi-agent ideation loop",
        "multi-agent round loop",
        "bounded ideation round",
        "bounded multi-agent round",
    )
    assert _contains_any_lower(
        command,
        "do not create durable session artifacts",
        "do not write durable session files",
        "keep orchestration in memory",
        "in-memory session",
        "should not promise durable ideation storage",
        "later-phase artifact management",
        "no durable ideation artifact system is required",
    )


def test_ideate_workflow_preserves_launch_summary_and_round_boundary_controls_when_present() -> None:
    if not IDEATE_WORKFLOW_PATH.exists():
        pytest.skip("ideate phase-2 command/workflow has not landed yet")

    command = _read(IDEATE_COMMAND_PATH)
    workflow = _read(IDEATE_WORKFLOW_PATH)

    if not _phase2_round_loop_is_documented(command, workflow):
        pytest.skip("ideate phase-2 round loop has not landed yet")

    for fragment in ("Start ideation", "Adjust launch", "Review raw context", "Stop here"):
        assert fragment in workflow

    for fragment in ("Idea", "Outcome", "Anchors", "Constraints"):
        assert fragment in workflow

    assert _contains_any(workflow, "Risks / Open Questions", "Risks/Open Questions", "Open Questions")
    assert _contains_any(workflow, "Execution Preferences", "Mode")
    assert _contains_any_lower(
        workflow,
        "multi-agent ideation loop",
        "multi-agent round loop",
        "bounded ideation round",
        "bounded multi-agent round",
        "ideation round",
    )

    for fragment in (
        "Continue to next round",
        "Add my thoughts",
        "Adjust configuration",
        "Review raw round",
    ):
        assert fragment in workflow

    assert _contains_any(workflow, "Pause/Stop", "Pause / Stop", "pause/stop")


def test_ideate_phase2_contract_does_not_backslide_to_phase1_only_or_durable_session_claims() -> None:
    if not IDEATE_COMMAND_PATH.exists():
        pytest.skip("ideate phase-2 command/workflow has not landed yet")

    command = _read(IDEATE_COMMAND_PATH)
    workflow = _read(IDEATE_WORKFLOW_PATH)

    if not _phase2_round_loop_is_documented(command, workflow):
        pytest.skip("ideate phase-2 round loop has not landed yet")

    combined = f"{command}\n{workflow}"

    assert "launch-surface only" not in combined
    assert "stops after the launch summary" not in combined
    assert "no multi-agent rounds have run" not in combined
    assert _contains_any_lower(
        combined,
        "do not create durable session artifacts",
        "do not write durable session files",
        "keep orchestration in memory",
        "in-memory session",
        "should not promise durable ideation storage",
        "later-phase artifact management",
        "no durable ideation artifact system is required",
    )
