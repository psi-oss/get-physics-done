"""Focused assertions for the Phase 11 debug-wrapper typed child-return cleanup."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMAND_PATH = REPO_ROOT / "src/gpd/commands/debug.md"


def test_debug_wrapper_routes_on_typed_child_return_contract() -> None:
    text = COMMAND_PATH.read_text(encoding="utf-8")

    assert "@{GPD_INSTALL_DIR}/workflows/debug.md" in text
    assert "The workflow owns workspace bootstrap, active-session handling, symptom gathering" in text
    assert "typed child-return routing" in text
    assert "gpd_return.status" in text
    assert "verifies the debug session artifact before treating a root cause as confirmed" in text
    assert "goal: find_root_cause_only" in text
    assert "Debug session artifact: `GPD/debug/{slug}.md`" in text

    for marker in (
        "ROOT CAUSE FOUND",
        "CHECKPOINT REACHED",
        "INVESTIGATION INCONCLUSIVE",
        "goal: find_and_fix",
        "Physics debugging follows a hierarchy of checks",
        "Use ask_user for each.",
        "Check Active Sessions",
    ):
        assert marker not in text


def test_debug_wrapper_checkpoint_continuation_stays_file_backed_and_fresh() -> None:
    text = COMMAND_PATH.read_text(encoding="utf-8")

    assert "Continuations are file-backed" in text
    assert "the child reads `GPD/debug/{slug}.md` before continuing" in text
    assert "instead of relying on an inline `@...` attachment." in text
    assert "@GPD/debug/{slug}.md" not in text
    assert "goal: find_root_cause_only" in text
