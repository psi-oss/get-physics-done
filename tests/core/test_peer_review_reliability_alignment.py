from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_DIR = REPO_ROOT / "src/gpd/commands"
WORKFLOWS_DIR = REPO_ROOT / "src/gpd/specs/workflows"
REFERENCES_DIR = REPO_ROOT / "src/gpd/specs/references"
AGENTS_DIR = REPO_ROOT / "src/gpd/agents"


def test_peer_review_workflow_references_canonical_reliability_doc_and_round_suffixed_artifacts() -> None:
    workflow = (WORKFLOWS_DIR / "peer-review.md").read_text(encoding="utf-8")

    assert "{GPD_INSTALL_DIR}/references/publication/peer-review-reliability.md" in workflow
    assert "${REVIEW_ROOT}/CLAIMS{round_suffix}.json" in workflow
    assert "${REVIEW_ROOT}/STAGE-reader{round_suffix}.json" in workflow
    assert "${REVIEW_ROOT}/STAGE-literature{round_suffix}.json" in workflow
    assert "${REVIEW_ROOT}/STAGE-math{round_suffix}.json" in workflow
    assert "${REVIEW_ROOT}/STAGE-physics{round_suffix}.json" in workflow
    assert "${REVIEW_ROOT}/STAGE-interestingness{round_suffix}.json" in workflow
    assert "${REVIEW_ROOT}/REVIEW-LEDGER{round_suffix}.json" in workflow
    assert "${REVIEW_ROOT}/REFEREE-DECISION{round_suffix}.json" in workflow
    assert "${PUBLICATION_ROOT}/REFEREE-REPORT{round_suffix}.md" in workflow
    assert "${PUBLICATION_ROOT}/REFEREE-REPORT{round_suffix}.tex" in workflow
    assert "gpd validate review-ledger ${REVIEW_ROOT}/REVIEW-LEDGER{round_suffix}.json" in workflow
    assert (
        "gpd validate referee-decision ${REVIEW_ROOT}/REFEREE-DECISION{round_suffix}.json --strict --ledger "
        "${REVIEW_ROOT}/REVIEW-LEDGER{round_suffix}.json"
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

def test_peer_review_surfaces_describe_dual_mode_project_and_external_artifact_review() -> None:
    command = (COMMANDS_DIR / "peer-review.md").read_text(encoding="utf-8")
    workflow = (WORKFLOWS_DIR / "peer-review.md").read_text(encoding="utf-8")
    reliability = (REFERENCES_DIR / "publication" / "peer-review-reliability.md").read_text(encoding="utf-8")
    publication_modes = (REFERENCES_DIR / "publication" / "publication-pipeline-modes.md").read_text(encoding="utf-8")

    assert "current GPD project or an explicit external artifact" in command
    assert "standalone external artifact review" in command
    assert "{GPD_INSTALL_DIR}/references/publication/publication-pipeline-modes.md" in command
    assert "subject-owned publication root at `GPD/publication/{subject_slug}`" in publication_modes
    assert "do not infer a full publication-tree relocation from that one continuation path" in command
    assert "standalone skeptical peer review" not in workflow
    assert "current GPD project manuscript" in workflow
    assert "explicit manuscript artifact" in workflow
    assert "reviewing the current GPD project manuscript" in reliability
    assert "explicit external artifact review" in reliability


def test_publication_reference_docs_keep_gpd_aux_outputs_separate_from_manuscript_root_contract() -> None:
    preflight = (
        REPO_ROOT / "src/gpd/specs/templates/paper/publication-manuscript-root-preflight.md"
    ).read_text(encoding="utf-8")
    bootstrap = (REFERENCES_DIR / "publication" / "publication-bootstrap-preflight.md").read_text(
        encoding="utf-8"
    )
    round_artifacts = (REFERENCES_DIR / "publication" / "publication-review-round-artifacts.md").read_text(
        encoding="utf-8"
    )
    response_artifacts = (REFERENCES_DIR / "publication" / "publication-response-artifacts.md").read_text(
        encoding="utf-8"
    )
    reliability = (REFERENCES_DIR / "publication" / "peer-review-reliability.md").read_text(encoding="utf-8")
    wrapper_guidance = (
        REFERENCES_DIR / "publication" / "publication-review-wrapper-guidance.md"
    ).read_text(encoding="utf-8")

    assert "does not by itself authorize standalone external-subject support for every publication command" in preflight
    assert "Keep GPD-authored auxiliary review, response, and packaging outputs under `GPD/`" in preflight
    assert "It does not decide whether a command may accept a standalone external manuscript/artifact" in bootstrap
    assert "Do not infer standalone external-artifact support from this pack alone." in bootstrap
    assert "current project-backed canonical layout" in round_artifacts
    assert "GPD-authored auxiliary outputs for a review round live under `GPD/` or `GPD/review/`" in round_artifacts
    assert "subject-owned publication root `GPD/publication/{subject_slug}`" in round_artifacts
    assert "does not by itself promise a full relocation" in round_artifacts
    assert "Do not copy manuscript-local artifacts into `GPD/` to satisfy strict review or submission gates." in round_artifacts
    assert "optional manuscript-local response-letter companion such as `response-letter.tex` is additive only" in response_artifacts
    assert "same paired response artifacts may instead bind under the subject-owned publication root" in response_artifacts
    assert "does not imply a full relocation" in response_artifacts
    assert "That output policy does not relocate the manuscript draft or manuscript-root manifests" in reliability
    assert "copied stand-ins under `GPD/` do not satisfy strict gates" in reliability
    assert "Do not imply full external-subject support or manuscript-root migration unless the workflow/runtime actually provides it." in wrapper_guidance


def test_peer_review_stage_six_boundary_aligns_reliability_workflow_panel_and_referee() -> None:
    workflow = (WORKFLOWS_DIR / "peer-review.md").read_text(encoding="utf-8")
    panel = (REFERENCES_DIR / "publication" / "peer-review-panel.md").read_text(encoding="utf-8")
    reliability = (REFERENCES_DIR / "publication" / "peer-review-reliability.md").read_text(encoding="utf-8")
    referee = (AGENTS_DIR / "gpd-referee.md").read_text(encoding="utf-8")

    stage_six_outputs = (
        "${PUBLICATION_ROOT}/REFEREE-REPORT{round_suffix}.md",
        "${PUBLICATION_ROOT}/REFEREE-REPORT{round_suffix}.tex",
        "${REVIEW_ROOT}/REVIEW-LEDGER{round_suffix}.json",
        "${REVIEW_ROOT}/REFEREE-DECISION{round_suffix}.json",
        "${PUBLICATION_ROOT}/CONSISTENCY-REPORT.md",
    )
    for artifact in stage_six_outputs:
        assert artifact in workflow
    for artifact in (
        "${REVIEW_ROOT}/REVIEW-LEDGER{round_suffix}.json",
        "${REVIEW_ROOT}/REFEREE-DECISION{round_suffix}.json",
    ):
        assert artifact in panel
    for artifact in (
        "GPD/review/REVIEW-LEDGER{round_suffix}.json",
        "GPD/review/REFEREE-DECISION{round_suffix}.json",
    ):
        assert artifact in reliability
    for artifact in (
        "${selected_review_root}/REVIEW-LEDGER{round_suffix}.json",
        "${selected_review_root}/REFEREE-DECISION{round_suffix}.json",
    ):
        assert artifact in referee

    assert "fresh `gpd_return.files_written`" in workflow
    assert "fresh `gpd_return.files_written`" in reliability
    assert "fresh `gpd_return.files_written`" in referee

    assert (
        "Do not modify `${REVIEW_ROOT}/CLAIMS{round_suffix}.json`, any `${REVIEW_ROOT}/STAGE-*.json`, "
        "or `${REVIEW_ROOT}/PROOF-REDTEAM{round_suffix}.md`."
    ) in workflow
    assert (
        "Treat `${REVIEW_ROOT}/CLAIMS{round_suffix}.json`, every `${REVIEW_ROOT}/STAGE-*.json`, and "
        "`${REVIEW_ROOT}/PROOF-REDTEAM{round_suffix}.md` as read-only upstream evidence."
    ) in panel
    assert (
        "Treat `GPD/review/CLAIMS{round_suffix}.json`, any `GPD/review/STAGE-*.json`, and "
        "`GPD/review/PROOF-REDTEAM{round_suffix}.md` as read-only upstream artifacts during Stage 6."
    ) in reliability
    assert (
        "Never modify upstream staged-review inputs such as `${selected_review_root}/CLAIMS{round_suffix}.json`, "
        "any `${selected_review_root}/STAGE-*.json`, or `${selected_review_root}/PROOF-REDTEAM{round_suffix}.md`."
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

    assert "Treat theorem-bearing status from the full Stage 1 Paper `ClaimRecord`, not from the `ProjectContract` `ContractClaim` vocabulary" in panel
    assert "The theorem-style `claim_kind` values are limited to `theorem`, `lemma`, `corollary`, and `proposition`." in panel
    assert "Do not treat `claim_kind: claim` as theorem-bearing by default." in panel
    assert "This Paper `ClaimRecord` rule is intentionally different from `ProjectContract.claims[]`" in panel
    assert "non-theorem-style kinds such as `claim`, `result`, or `other` become theorem-bearing only" in referee
    assert "including a generic `claim_kind: claim`" in referee
