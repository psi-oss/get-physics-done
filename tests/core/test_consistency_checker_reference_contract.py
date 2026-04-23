"""Assertions for the consistency-checker reference contract wording."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SHARED_PROTOCOLS = REPO_ROOT / "src/gpd/specs/references/shared/shared-protocols.md"
AGENT_INFRASTRUCTURE = REPO_ROOT / "src/gpd/specs/references/orchestration/agent-infrastructure.md"


def test_consistency_checker_reference_contract_uses_state_json_authority_and_typed_return_envelope() -> None:
    shared = SHARED_PROTOCOLS.read_text(encoding="utf-8")
    infra = AGENT_INFRASTRUCTURE.read_text(encoding="utf-8")

    assert "Read `convention_lock` from `state.json`; `STATE.md` is the readable mirror" in shared
    assert (
        "Spawned agents that need to hand machine-readable results back to the orchestrator return a typed `gpd_return` envelope:"
        in infra
    )
    assert "structured YAML block at the end of their output" not in infra
    assert "The four base fields above are required on this envelope." in infra
