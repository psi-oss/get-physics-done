from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / "src/gpd/specs/workflows"
REFERENCES_DIR = REPO_ROOT / "src/gpd/specs/references"
AGENTS_DIR = REPO_ROOT / "src/gpd/agents"


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
    assert "GPD/CONSISTENCY-REPORT.md" in reliability
    assert "GPD/AUTHOR-RESPONSE{round_suffix}.md" in reliability
    assert "GPD/review/REFEREE_RESPONSE{round_suffix}.md" in reliability
    assert "paired response artifacts are present" in reliability
    assert "Stage 6 Artifact Boundary" in reliability
    assert "fresh `gpd_return.files_written`" in reliability
    assert "gpd_return.status: blocked" in reliability
    assert "read-only upstream artifacts during Stage 6" in reliability
    assert "Stage 6 repaired upstream artifacts" in reliability
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


def test_peer_review_stage_six_boundary_aligns_reliability_workflow_panel_and_referee() -> None:
    workflow = (WORKFLOWS_DIR / "peer-review.md").read_text(encoding="utf-8")
    panel = (REFERENCES_DIR / "publication" / "peer-review-panel.md").read_text(encoding="utf-8")
    reliability = (REFERENCES_DIR / "publication" / "peer-review-reliability.md").read_text(encoding="utf-8")
    referee = (AGENTS_DIR / "gpd-referee.md").read_text(encoding="utf-8")

    stage_six_outputs = (
        "GPD/REFEREE-REPORT{round_suffix}.md",
        "GPD/REFEREE-REPORT{round_suffix}.tex",
        "GPD/review/REVIEW-LEDGER{round_suffix}.json",
        "GPD/review/REFEREE-DECISION{round_suffix}.json",
        "GPD/CONSISTENCY-REPORT.md",
    )
    for artifact in stage_six_outputs:
        assert artifact in workflow
        assert artifact in panel
        assert artifact in reliability
        assert artifact in referee

    assert "fresh `gpd_return.files_written`" in workflow
    assert "fresh `gpd_return.files_written`" in reliability
    assert "fresh `gpd_return.files_written`" in referee

    assert (
        "Do not modify `GPD/review/CLAIMS{round_suffix}.json`, any `GPD/review/STAGE-*.json`, "
        "or `GPD/review/PROOF-REDTEAM{round_suffix}.md`."
    ) in workflow
    assert (
        "Treat `GPD/review/CLAIMS{round_suffix}.json`, every `GPD/review/STAGE-*.json`, and "
        "`GPD/review/PROOF-REDTEAM{round_suffix}.md` as read-only upstream evidence."
    ) in panel
    assert (
        "Treat `GPD/review/CLAIMS{round_suffix}.json`, any `GPD/review/STAGE-*.json`, and "
        "`GPD/review/PROOF-REDTEAM{round_suffix}.md` as read-only upstream artifacts during Stage 6."
    ) in reliability
    assert (
        "Never modify upstream staged-review inputs such as `GPD/review/CLAIMS{round_suffix}.json`, "
        "any `GPD/review/STAGE-*.json`, or `GPD/review/PROOF-REDTEAM{round_suffix}.md`."
    ) in referee

    assert "return `gpd_return.status: blocked`" in workflow
    assert "route the inconsistency back to the earliest failing upstream stage" in panel
    assert "gpd_return.status: blocked" in reliability
    assert "return `gpd_return.status: blocked`" in referee
    assert "Stage 6 repaired upstream artifacts" in reliability


def test_peer_review_reliability_reference_documents_runtime_neutral_stage_cleanup() -> None:
    workflow = (WORKFLOWS_DIR / "peer-review.md").read_text(encoding="utf-8")
    reliability = (REFERENCES_DIR / "publication" / "peer-review-reliability.md").read_text(encoding="utf-8")

    assert "Each stage runs in a fresh subagent context and writes a compact artifact." in workflow
    assert "fresh continuation handoff" in workflow

    assert "Runtime-Neutral Stage Cleanup" in reliability
    assert "Every spawned reviewer, proof critic, or referee run is a one-shot child handoff." in reliability
    assert "the child is closed/retired for the active review round" in reliability
    assert "validate or classify the persisted artifact boundary in the orchestrator" in reliability
    assert "close/retire the finished child before spawning any retry, continuation, or downstream stage" in reliability
    assert "start retries and checkpoint continuations from persisted artifacts and declared carry-forward inputs only" in reliability
    assert (
        "do not reuse live child memory, pending tool state, or any other transient execution state "
        "across stage boundaries"
    ) in reliability
    assert "Stage 2 / Stage 3 / proof-review parallel wave" in reliability
    assert "Sequential fallback must emulate the same cleanup boundary between stages." in reliability
    assert "The retry is a fresh run." in reliability
    assert "Do not resume the failed child in place" in reliability
    assert "persisted artifacts and typed return data already captured for that stage" in reliability


def test_peer_review_references_keep_generic_claim_kind_out_of_default_theorem_bearing_classification() -> None:
    reliability = (REFERENCES_DIR / "publication" / "peer-review-reliability.md").read_text(encoding="utf-8")
    panel = (REFERENCES_DIR / "publication" / "peer-review-panel.md").read_text(encoding="utf-8")
    referee = (REPO_ROOT / "src" / "gpd" / "agents" / "gpd-referee.md").read_text(encoding="utf-8")

    assert "theorem-bearing claims in the claim record" in reliability
    assert "The runtime determines theorem-bearing coverage from the claim record itself" in reliability
    assert "claim_kind:" not in reliability

    assert "The theorem-style `claim_kind` values are limited to `theorem`, `lemma`, `corollary`, and `proposition`." in panel
    assert "Do not treat `claim_kind: claim` as theorem-bearing by default." in panel
    assert "non-theorem-style kinds such as `claim`, `result`, or `other` become theorem-bearing only" in referee
    assert "including a generic `claim_kind: claim`" in referee
