"""Focused assertions for Phase 10 execution return application wiring."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXECUTE_PHASE = ROOT / "src" / "gpd" / "specs" / "workflows" / "execute-phase.md"
EXECUTE_PLAN = ROOT / "src" / "gpd" / "specs" / "workflows" / "execute-plan.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _section(text: str, start_marker: str, end_marker: str | None = None) -> str:
    start = text.index(start_marker)
    if end_marker is None:
        return text[start:]
    end = text.index(end_marker, start)
    return text[start:end]


def test_execute_phase_uses_canonical_apply_return_updates_path() -> None:
    text = _read(EXECUTE_PHASE)

    assert "apply-return-updates" in text
    assert "validate-return" not in text
    assert "WARNING: validate-return failed" not in text


def test_execute_phase_keeps_artifact_gates_explicit() -> None:
    text = _read(EXECUTE_PHASE)

    assert "proof_redteam_gate" in text
    assert "-PROOF-REDTEAM.md" in text
    assert "status: passed" in text
    assert "gpd-check-proof" in text


def test_execute_plan_update_current_position_uses_canonical_applicator() -> None:
    text = _read(EXECUTE_PLAN)
    section = _section(text, "<step name=\"update_current_position\">", "</step>")

    assert "gpd apply-return-updates" in section
    assert "gpd state advance" not in section
    assert "gpd state record-metric" not in section


def test_execute_plan_decision_and_continuation_handoffs_use_canonical_applicator() -> None:
    text = _read(EXECUTE_PLAN)
    decisions = _section(text, "<step name=\"extract_decisions_and_issues\">", "</step>")
    continuation = _section(text, "<step name=\"update_continuation\">", "</step>")

    assert "gpd apply-return-updates" in decisions
    assert "gpd state add-decision" not in decisions
    assert "gpd state add-blocker" not in decisions

    assert "gpd apply-return-updates" in continuation
    assert "gpd state record-session" not in continuation
    assert "do not include `recorded_at` or `recorded_by` in child returns" in continuation
    assert "recorded_at:" not in continuation
    assert "recorded_by:" not in continuation


def test_execute_plan_routes_state_application_through_canonical_applicator() -> None:
    text = _read(EXECUTE_PLAN)

    assert "gpd apply-return-updates" in text
    assert "contract_updates:" in text
    assert "continuation_update:" in text
