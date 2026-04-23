"""Focused assertions for Phase 11 execution-state ownership cleanup."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
EXECUTE_PHASE = REPO_ROOT / "src/gpd/specs/workflows/execute-phase.md"
AGENT_INFRASTRUCTURE = REPO_ROOT / "src/gpd/specs/references/orchestration/agent-infrastructure.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_execute_phase_only_applies_child_return_state_once() -> None:
    text = _read(EXECUTE_PHASE)

    assert "gpd --raw apply-return-updates" in text
    assert "The orchestrator applies them through `gpd apply-return-updates`" in text
    assert "gpd state advance immediately" not in text
    assert "gpd state record-metric" not in text


def test_agent_infrastructure_points_spawned_child_returns_at_canonical_applicator() -> None:
    text = _read(AGENT_INFRASTRUCTURE)

    assert "gpd apply-return-updates <summary-file>" in text
    assert "gpd state advance" not in text

