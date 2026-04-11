"""Regression test for runtime wrapper dry-run contract truthfulness."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
WRAPPER_FILES = (
    "src/gpd/commands/complete-milestone.md",
    "src/gpd/commands/remove-phase.md",
    "src/gpd/commands/merge-phases.md",
    "src/gpd/commands/undo.md",
)


def test_runtime_wrapper_docs_do_not_claim_unsupported_dry_run_support() -> None:
    for relative_path in WRAPPER_FILES:
        text = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
        assert "--dry-run" not in text, f"{relative_path} still claims dry-run support"
        assert "runs the" in text and "workflow directly" in text, f"{relative_path} missing truthful contract note"
