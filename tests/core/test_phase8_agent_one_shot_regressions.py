"""Phase 8 assertions for one-shot delegation cleanup."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO_ROOT / "src" / "gpd" / "agents"


def _read_agent(name: str) -> str:
    return (AGENTS_DIR / f"{name}.md").read_text(encoding="utf-8")


def test_notation_coordinator_requires_checkpoint_and_fresh_continuation_for_write_approval() -> None:
    content = _read_agent("gpd-notation-coordinator")

    assert "fresh continuation handoff" in content
    assert "Wait for user decision" not in content
    assert "Wait for user decision before proceeding" not in content
    assert "Return a checkpoint with the options and stop" in content


def test_debugger_uses_one_shot_checkpoint_handoff_instead_of_in_run_waiting() -> None:
    content = _read_agent("gpd-debugger")

    assert "one-shot handoff" in content
    assert "fresh continuation handoff" in content
    assert "### Fresh Continuation" in content
    assert "You are not resumed in the same run." in content
    assert "active sessions" not in content


def test_roadmapper_makes_checkpoint_revision_flow_explicit() -> None:
    content = _read_agent("gpd-roadmapper")

    assert "fresh continuation" in content
    assert "### Fresh Continuation" in content
    assert "Approve roadmap or provide feedback for a fresh continuation revision pass." in content
    assert "same-run wait" in content


def test_experiment_designer_supervised_mode_mentions_fresh_continuation() -> None:
    content = _read_agent("gpd-experiment-designer")

    assert "fresh continuation" in content
    assert "Return a checkpoint with the cost estimate for user approval before writing" in content
    assert "spawns a fresh continuation for the write pass" in content
