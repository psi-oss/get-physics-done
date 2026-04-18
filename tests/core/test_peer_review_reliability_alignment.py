from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / "src/gpd/specs/workflows"
REFERENCES_DIR = REPO_ROOT / "src/gpd/specs/references"


def test_peer_review_workflow_references_canonical_reliability_doc_and_round_suffixed_artifacts() -> None:
    workflow = (WORKFLOWS_DIR / "peer-review.md").read_text(encoding="utf-8")

    assert "@{GPD_INSTALL_DIR}/references/publication/peer-review-reliability.md" in workflow
    assert "GPD/review/CLAIMS{round_suffix}.json" in workflow
    assert "GPD/review/STAGE-reader{round_suffix}.json" in workflow
    assert "GPD/review/STAGE-literature{round_suffix}.json" in workflow
    assert "GPD/review/STAGE-math{round_suffix}.json" in workflow
    assert "GPD/review/STAGE-physics{round_suffix}.json" in workflow
    assert "GPD/review/STAGE-interestingness{round_suffix}.json" in workflow
    assert "GPD/review/REVIEW-LEDGER{round_suffix}.json" in workflow
    assert "GPD/review/REFEREE-DECISION{round_suffix}.json" in workflow
    assert "GPD/REFEREE-REPORT{round_suffix}.md" in workflow
    assert "GPD/REFEREE-REPORT{round_suffix}.tex" in workflow
    assert "gpd validate review-ledger GPD/review/REVIEW-LEDGER{round_suffix}.json" in workflow
    assert (
        "gpd validate referee-decision GPD/review/REFEREE-DECISION{round_suffix}.json --strict --ledger "
        "GPD/review/REVIEW-LEDGER{round_suffix}.json"
    ) in workflow
    assert ".gpd/" not in workflow


def test_peer_review_reliability_reference_uses_canonical_gpd_paths_only() -> None:
    reliability = (REFERENCES_DIR / "publication" / "peer-review-reliability.md").read_text(encoding="utf-8")

    assert "Peer Review Phase Reliability" in reliability
    assert "GPD/STATE.md" in reliability
    assert "GPD/ROADMAP.md" in reliability
    assert "GPD/phases/" in reliability
    assert "GPD/review/REVIEW-LEDGER{round_suffix}.json" in reliability
    assert "GPD/review/REFEREE-DECISION{round_suffix}.json" in reliability
    assert "GPD/REFEREE-REPORT{round_suffix}.md" in reliability
    assert "GPD/AUTHOR-RESPONSE{round_suffix}.md" in reliability
    assert "GPD/review/REFEREE_RESPONSE{round_suffix}.md" in reliability
    assert "paired response artifacts are present" in reliability
    assert "gpd validate review-claim-index GPD/review/CLAIMS{round_suffix}.json" in reliability
    assert "gpd validate review-stage-report GPD/review/STAGE-<stage_id>{round_suffix}.json" in reliability
    assert "gpd validate review-ledger GPD/review/REVIEW-LEDGER{round_suffix}.json" in reliability
    assert (
        "gpd validate referee-decision GPD/review/REFEREE-DECISION{round_suffix}.json --strict --ledger "
        "GPD/review/REVIEW-LEDGER{round_suffix}.json"
    ) in reliability
    assert "bibliography_audit_clean" in reliability
    assert "reproducibility_ready" in reliability
    assert "proof_audits[]" in reliability
    assert "theorem-bearing claims" in reliability
    assert "claim record itself" in reliability
    assert "detects prior reports and author responses to increment the round number automatically" not in reliability
    assert "theorem_assumptions" not in reliability
    assert "theorem_parameters" not in reliability
    assert "`CLAIMS.json`" not in reliability
    assert "`REFEREE-DECISION.json`" not in reliability
    assert "`REVIEW-LEDGER.json`" not in reliability
    assert ".gpd/" not in reliability
