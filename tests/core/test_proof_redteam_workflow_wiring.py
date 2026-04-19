"""Regression checks for fail-closed proof redteam workflow wiring."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / "src/gpd/specs/workflows"


def _read(name: str) -> str:
    return (WORKFLOWS_DIR / name).read_text(encoding="utf-8")


def test_plan_and_execute_phase_require_proof_redteam_gates() -> None:
    plan_phase = _read("plan-phase.md")
    execute_phase = _read("execute-phase.md")

    assert "## 1.5 Proof-Obligation Planning Gate" in plan_phase
    assert "`--skip-verify` does NOT waive checker review" in plan_phase
    assert "{plan_id}-PROOF-REDTEAM.md" in plan_phase

    assert "<step name=\"detect_proof_obligation_work\">" in execute_phase
    assert "workflow.verifier=false" in execute_phase
    assert "sibling `{plan_id}-PROOF-REDTEAM.md` artifact" in execute_phase
    assert "`gpd-check-proof` is the canonical owner" in execute_phase
    assert 'task(\n     subagent_type="gpd-check-proof"' in execute_phase
    assert "If any executed plan is proof-bearing, proof verification still runs" in execute_phase


def test_verification_workflows_fail_closed_on_missing_proof_coverage() -> None:
    verify_phase = _read("verify-phase.md")
    verify_work = _read("verify-work.md")
    derive_equation = _read("derive-equation.md")

    assert "theorem-to-proof audit plus an adversarial special-case" in verify_phase
    assert "<step name=\"proof_obligation_gate\">" in verify_phase
    assert "fail the target if a named parameter or hypothesis disappears from the proof" in verify_phase
    assert "spawn `gpd-check-proof` once to repair that gap" in verify_phase
    assert "wait for user confirmation" not in verify_phase
    assert "ask the user then continue" not in verify_phase
    assert "pause here for approval" not in verify_phase

    assert "Targeted flags narrow the optional check mix only." in verify_work
    assert "require a canonical `*-PROOF-REDTEAM.md` artifact" in verify_work
    assert "CHECK_PROOF_MODEL=$(gpd resolve-model gpd-check-proof)" in verify_work
    assert 'task(\n  subagent_type="gpd-check-proof"' in verify_work
    assert "additional mandatory floor applies" in verify_work

    assert "<step name=\"proof_obligation_screen\">" in derive_equation
    assert "DERIVATION-{slug}-PROOF-REDTEAM.md" in derive_equation
    assert "gpd-check-proof" in derive_equation
    assert "CHECK_PROOF_MODEL=$(gpd resolve-model gpd-check-proof)" in derive_equation
    assert 'task(\n  subagent_type="gpd-check-proof"' in derive_equation
    assert "Proof-bearing derivations fail closed" in derive_equation


def test_quick_publication_and_settings_surfaces_block_proof_bypass() -> None:
    quick = _read("quick.md")
    write_paper = _read("write-paper.md")
    peer_review = _read("peer-review.md")
    settings = _read("settings.md")

    assert "Quick mode is NOT authorized to close theorem-style or `proof_obligation` work." in quick
    assert "Proof-obligation command block:" in quick
    assert "quick mode is blocked pending the full proof-redteam workflow" in quick

    assert "### Check 7: Proof-obligation coverage" in write_paper
    assert "GPD/review/PROOF-REDTEAM{round_suffix}.md" in write_paper
    assert "must not strengthen, generalize, or rhetorically smooth theorem-style claims" in write_paper

    assert "<step name=\"detect_proof_bearing_manuscript\">" in peer_review
    assert "${REVIEW_ROOT}/PROOF-REDTEAM{round_suffix}.md" in peer_review
    assert "gpd-check-proof" in peer_review
    assert "may be running in parallel" in peer_review
    assert "do not wait on that artifact to begin the math review" in peer_review
    assert "expect a sibling `GPD/review/PROOF-REDTEAM{round_suffix}.md` artifact" not in peer_review
    assert "Recommendation floor: `major_revision` or `reject`." in peer_review

    assert "this does NOT disable mandatory proof red-teaming" in settings
    assert "Sparse cadence does not waive proof red-teaming" in settings


def test_proof_obligation_detection_lists_include_claim_language() -> None:
    quick = _read("quick.md")
    plan_phase = _read("plan-phase.md")
    execute_phase = _read("execute-phase.md")
    derive_equation = _read("derive-equation.md")
    verify_phase = _read("verify-phase.md")
    verify_work = _read("verify-work.md")
    peer_review = _read("peer-review.md")
    write_paper = _read("write-paper.md")

    for content in (
        quick,
        plan_phase,
        execute_phase,
        derive_equation,
        verify_phase,
        verify_work,
        peer_review,
        write_paper,
    ):
        assert "`claim`" in content
