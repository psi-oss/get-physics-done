"""Focused assertions for the verify-work command wrapper surface."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMAND_PATH = REPO_ROOT / "src/gpd/commands/verify-work.md"
WORKFLOW_PATH = REPO_ROOT / "src/gpd/specs/workflows/verify-work.md"


def test_verify_work_command_wrapper_stays_thin_and_delegates_policy_to_workflow() -> None:
    text = COMMAND_PATH.read_text(encoding="utf-8")

    assert "@{GPD_INSTALL_DIR}/workflows/verify-work.md" in text
    assert "The workflow file owns the detailed check taxonomy; this wrapper only bootstraps the canonical verification surfaces and delegates the physics checks." in text
    assert "Severity Classification" not in text
    assert "One check at a time, plain text responses, no interrogation." not in text
    assert "Physics verification is not binary:" not in text
    assert "For deeper focused analysis" not in text


def test_verify_work_workflow_loads_staged_init_payloads_on_demand() -> None:
    text = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert 'SESSION_ROUTER_INIT=$(gpd --raw init verify-work "${PHASE_ARG}" --stage session_router)' in text
    assert 'PHASE_BOOTSTRAP_INIT=$(gpd --raw init verify-work "${PHASE_ARG}" --stage phase_bootstrap)' in text
    assert 'INVENTORY_BUILD_INIT=$(gpd --raw init verify-work "${PHASE_ARG}" --stage inventory_build)' in text
    assert (
        'INTERACTIVE_VALIDATION_INIT=$(gpd --raw init verify-work "${PHASE_ARG}" --stage interactive_validation)'
        in text
    )
    assert 'GAP_REPAIR_INIT=$(gpd --raw init verify-work "${PHASE_ARG}" --stage gap_repair)' in text
    assert 'INIT=$(gpd --raw init verify-work "${PHASE_ARG}")' not in text
    assert "Do not assume reference ledgers, protocol bundles, or report-writing schemas are loaded during session routing." in text
