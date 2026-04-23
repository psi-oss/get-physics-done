"""Focused assertions for the verify-work command wrapper surface."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMAND_PATH = REPO_ROOT / "src/gpd/commands/verify-work.md"


def test_verify_work_command_wrapper_stays_thin_and_delegates_policy_to_workflow() -> None:
    text = COMMAND_PATH.read_text(encoding="utf-8")

    assert "@{GPD_INSTALL_DIR}/workflows/verify-work.md" in text
    assert "The workflow file owns the detailed check taxonomy; this wrapper only bootstraps the canonical verification surfaces and delegates the physics checks." in text
    assert "Severity Classification" not in text
    assert "One check at a time, plain text responses, no interrogation." not in text
    assert "Physics verification is not binary:" not in text
    assert "For deeper focused analysis" not in text
