from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_DIR = REPO_ROOT / "src/gpd/commands"
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

    assert "current GPD project or an explicit external artifact" in command
    assert "standalone external artifact review" in command
    assert "standalone skeptical peer review" not in workflow
    assert "current GPD project manuscript" in workflow
    assert "explicit external artifact" in workflow
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
    assert "GPD-authored auxiliary outputs for a review round live under `GPD/` or `GPD/review/`" in round_artifacts
    assert "Do not copy manuscript-local artifacts into `GPD/` to satisfy strict review or submission gates." in round_artifacts
    assert "optional manuscript-local response-letter companion such as `response-letter.tex` is additive only" in response_artifacts
    assert "That output policy does not relocate the manuscript draft or manuscript-root manifests" in reliability
    assert "copied stand-ins under `GPD/` do not satisfy strict gates" in reliability
    assert "Do not imply full external-subject support or manuscript-root migration unless the workflow/runtime actually provides it." in wrapper_guidance
