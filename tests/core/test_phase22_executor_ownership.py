"""Phase 22 regressions for executor ownership cleanup."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO_ROOT / "src" / "gpd" / "agents"
REFERENCES_DIR = REPO_ROOT / "src" / "gpd" / "specs" / "references"


def _read_executor_prompt() -> str:
    return (AGENTS_DIR / "gpd-executor.md").read_text(encoding="utf-8")


def _between(text: str, start: str, end: str) -> str:
    _, start_marker, tail = text.partition(start)
    assert start_marker, f"Missing marker: {start}"
    body, end_marker, _ = tail.partition(end)
    assert end_marker, f"Missing marker: {end}"
    return body


def test_executor_bootstrap_role_stays_worker_facing() -> None:
    executor = _read_executor_prompt()
    role = _between(executor, "<role>", "</role>")

    assert "return shared-state updates to the orchestrator instead of writing `STATE.md` directly." in role
    assert "Pattern A:" not in role
    assert "Pattern B:" not in role
    assert "Pattern C:" not in role
    assert "Pattern D:" not in role
    assert "first-result" not in role
    assert "pre-fanout" not in role
    assert "bounded execution segment envelope" not in role


def test_executor_retains_worker_return_envelope_and_bounded_stop_contract() -> None:
    executor = _read_executor_prompt()
    completion = (
        REFERENCES_DIR / "execution" / "executor-completion.md"
    ).read_text(encoding="utf-8")

    assert "Pattern D: Auto-bounded" in executor
    assert "bounded execution segment envelope" in executor
    assert "Do NOT write `GPD/STATE.md` directly" in executor
    assert "gpd_return.state_updates" in executor
    assert "state_updates:" in completion
    assert "continuation_update:" in completion
