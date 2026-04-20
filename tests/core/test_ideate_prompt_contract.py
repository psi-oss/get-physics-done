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


def _ideate_round_loop_is_documented(command: str, workflow: str) -> bool:
    return _contains_any_lower(
        workflow,
        "continue to next round",
        "add my thoughts",
        "review raw round",
        "pause/stop",
        "pause or stop",
    )


def _phase3_subgroup_surface_is_documented(content: str) -> bool:
    return _contains_any_lower(
        content,
        "temporary bounded subgroup",
        "temporary subgroup work",
        "subgroup micro-loop",
        "subgroup rejoin",
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


def test_ideate_command_keeps_launch_plus_round_loop_contract_when_present() -> None:
    if not IDEATE_COMMAND_PATH.exists():
        pytest.skip("ideate command/workflow has not landed yet")

    command = _read(IDEATE_COMMAND_PATH)
    workflow = _read(IDEATE_WORKFLOW_PATH)

    if not _ideate_round_loop_is_documented(command, workflow):
        pytest.skip("ideate round loop has not landed yet")

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
    assert _contains_any_lower(
        workflow,
        "temporary subgroup micro-loops",
        "subgroup micro-loops",
        "optional subgroup work",
    )


def test_ideate_workflow_preserves_launch_summary_and_round_boundary_controls_when_present() -> None:
    if not IDEATE_WORKFLOW_PATH.exists():
        pytest.skip("ideate command/workflow has not landed yet")

    command = _read(IDEATE_COMMAND_PATH)
    workflow = _read(IDEATE_WORKFLOW_PATH)

    if not _ideate_round_loop_is_documented(command, workflow):
        pytest.skip("ideate round loop has not landed yet")

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


def test_ideate_workflow_allows_only_bounded_temporary_subgroup_rejoin_when_present() -> None:
    if not IDEATE_COMMAND_PATH.exists():
        pytest.skip("ideate command/workflow has not landed yet")

    command = _read(IDEATE_COMMAND_PATH)
    workflow = _read(IDEATE_WORKFLOW_PATH)

    if not _ideate_round_loop_is_documented(command, workflow):
        pytest.skip("ideate round loop has not landed yet")

    if "subgroup_micro_loop" not in workflow and "subgroup" not in workflow.lower():
        pytest.skip("ideate phase-3 subgroup loop has not landed yet")

    assert _contains_any_lower(
        workflow,
        "subgroups are optional and only user-initiated from the existing parent round gate",
        "optional temporary subgroup micro-loops",
    )
    assert _contains_any_lower(
        workflow,
        "route subgroup setup through `adjust configuration`",
        "route subgroup setup through adjust configuration",
    )
    assert _contains_any_lower(
        workflow,
        "subgroup rounds must stay bounded; default to `2` if the user does not specify a count",
        "subgroup rounds must stay bounded; default to 2 if the user does not specify a count",
    )
    assert _contains_any_lower(
        workflow,
        "keep each subgroup batch to `1-3` rounds in this phase",
        "keep each subgroup batch to 1-3 rounds in this phase",
    )
    assert _contains_any_lower(
        workflow,
        "fold only that subgroup summary into the main shared discussion",
        "summary-first on rejoin",
        "compact rejoin packet",
    )


def test_ideate_phase3_contract_rejects_durable_subgroup_persistence_promotion_and_other_v11_features() -> None:
    if not IDEATE_COMMAND_PATH.exists():
        pytest.skip("ideate command/workflow has not landed yet")

    command = _read(IDEATE_COMMAND_PATH)
    workflow = _read(IDEATE_WORKFLOW_PATH)

    if not _ideate_round_loop_is_documented(command, workflow):
        pytest.skip("ideate round loop has not landed yet")

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
    assert _contains_any_lower(
        combined,
        "do not add `<spawn_contract>` blocks",
        "do not add spawn-contract blocks",
    )
    assert _contains_any_lower(
        combined,
        "do not create durable subgroup transcripts",
        "subgroup execution stays fileless in this phase",
    )
    assert _contains_any_lower(
        combined,
        "do not claim subgroup resumability, subgroup promotion, or independent subgroup sessions",
        "do not claim durable ideation history, subgroup transcripts, resumable session files, tags, imported-document state, or archived artifacts",
    )
    assert _contains_any_lower(
        combined,
        "do not promise durable subgroup transcripts, promotion, spawn contracts, resumable subgroup persistence",
        "do not promise durable subgroup transcripts, promotion, spawn contracts, resumable subgroup persistence, dedicated ideation state",
        "do not promise durable subgroup transcripts, promotion, spawn contracts, a dedicated ideation subtree, resumable subgroup persistence",
        "do not promise durable subgroup transcripts, promotion, spawn contracts, `gpd/ideation/` state, resumable subgroup persistence, gpd/ideation state, or ideation files in this phase",
        "do not promise durable subgroup transcripts, promotion, spawn contracts, gpd/ideation state, resumable subgroup persistence, or ideation files in this phase",
    )
    assert "resume-work" not in combined.lower()
    assert "session.json" not in combined.lower()
    assert "gpd/ideation/" not in combined.lower()


def test_ideate_public_surfaces_keep_phase3_subgroups_bounded_and_non_durable() -> None:
    if not IDEATE_COMMAND_PATH.exists():
        pytest.skip("ideate command/workflow has not landed yet")

    command = _read(IDEATE_COMMAND_PATH)
    workflow = _read(IDEATE_WORKFLOW_PATH)
    help_workflow = _read(WORKFLOWS_DIR / "help.md")

    if not _ideate_round_loop_is_documented(command, workflow):
        pytest.skip("ideate round loop has not landed yet")

    assert _phase3_subgroup_surface_is_documented(command)
    assert _phase3_subgroup_surface_is_documented(help_workflow)
    assert _contains_any_lower(
        command,
        "adjust configuration",
        "existing round-boundary control surface",
        "existing round-boundary controls",
    )
    assert _contains_any_lower(
        help_workflow,
        "adjust configuration",
        "summary-only rejoin",
        "gpd/ideation/",
    )

    public_surfaces = f"{command}\n{help_workflow}"
    assert _contains_any_lower(
        public_surfaces,
        "subgroup transcripts",
        "subgroup promotion",
        "gpd/ideation/",
    )

    for forbidden_claim in (
        "durable subgroup transcript is available",
        "subgroup transcripts are stored",
        "promote a subgroup session",
        "subgroup session promotion in true v1",
        "resumable subgroup session",
    ):
        assert forbidden_claim not in public_surfaces.lower()
