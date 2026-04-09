from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / "src/gpd/specs/workflows"
COMMANDS_DIR = REPO_ROOT / "src/gpd/commands"


def _workflow_text(name: str) -> str:
    return (WORKFLOWS_DIR / name).read_text(encoding="utf-8")


def _command_text(name: str) -> str:
    return (COMMANDS_DIR / name).read_text(encoding="utf-8")


def test_write_paper_workflow_runs_centralized_review_preflight() -> None:
    workflow = _workflow_text("write-paper.md")

    assert "gpd validate review-preflight write-paper --strict" in workflow
    assert "Run the centralized review preflight before continuing:" in workflow
    assert "Do not satisfy that gate with legacy publication artifacts from a different manuscript directory" in workflow
    assert "Strict review for that resume path uses `${PAPER_DIR}/ARTIFACT-MANIFEST.json`" in workflow
    assert "missing manuscript" not in workflow
    assert 'PAPER_DIR="$DIR"' in workflow
    assert 'PAPER_DIR="paper"' in workflow
    assert '${PAPER_DIR}/{topic_specific_stem}.tex' in workflow


def test_respond_to_referees_workflow_runs_centralized_review_preflight() -> None:
    workflow = _workflow_text("respond-to-referees.md")

    assert 'gpd validate review-preflight respond-to-referees "$ARGUMENTS" --strict' in workflow
    assert "gpd validate review-preflight respond-to-referees --strict" in workflow
    assert "missing referee report source when provided as a path" in workflow
    assert "Any spawned agent that needs user input must return `status: checkpoint` and stop" in workflow
    assert "Do not ask the child agent to wait inside the same run" in workflow
    assert "Treat those files as complete only if the expected mirrored artifacts exist on disk" in workflow
    assert "${PAPER_DIR}/response-letter.tex" in workflow
    assert "${PAPER_DIR}/{section}.tex" in workflow


def test_arxiv_submission_workflow_runs_centralized_review_preflight() -> None:
    workflow = _workflow_text("arxiv-submission.md")

    assert 'gpd validate review-preflight arxiv-submission "$ARGUMENTS" --strict' in workflow
    assert "gpd validate review-preflight arxiv-submission --strict" in workflow
    assert "Strict preflight also requires `ARTIFACT-MANIFEST.json` and `BIBLIOGRAPHY-AUDIT.json` beside the resolved manuscript entry point." in workflow
    assert "not from legacy `GPD/paper/` copies or some other manuscript directory" in workflow
    assert "Strict preflight also requires the latest round-specific `GPD/review/REVIEW-LEDGER*.json` / `GPD/review/REFEREE-DECISION*.json` pair as authoritative submission-gate input." in workflow
    assert "latest recommendation is `accept` or `minor_revision` with no unresolved blocking issues" in workflow
    assert "`manuscript_proof_review` must also already be cleared" in workflow
    assert "The same resolved manuscript root is also the strict preflight source of truth for `ARTIFACT-MANIFEST.json`, `BIBLIOGRAPHY-AUDIT.json`, and the compiled PDF." in workflow
    assert "If `$ARGUMENTS` specifies a `.tex` file, set `resolved_main_tex` to that file" in workflow
    assert "canonical manuscript `.tex` entrypoint under that directory" in workflow
    assert 'MAIN_SOURCE="${resolved_main_tex}"' in workflow


def test_peer_review_workflow_runs_centralized_review_preflight_with_explicit_arguments() -> None:
    workflow = _workflow_text("peer-review.md")

    assert 'gpd validate review-preflight peer-review "$ARGUMENTS" --strict' in workflow
    assert "gpd validate review-preflight peer-review --strict" not in workflow
    assert "If any spawned reviewer or proof auditor needs user input, it must return `status: checkpoint` and stop." in workflow
    assert "Do not keep the same spawned run alive waiting for confirmation." in workflow
    assert "Do not trust the referee's success text until the ledger, decision, and report files all exist on disk and validate." in workflow


def test_publication_review_wrappers_reference_shared_wrapper_guidance() -> None:
    shared_include = "@{GPD_INSTALL_DIR}/references/publication/publication-review-wrapper-guidance.md"

    for command_name in ("write-paper.md", "peer-review.md"):
        assert shared_include not in _command_text(command_name)
    assert shared_include in _command_text("respond-to-referees.md")


def test_verify_work_workflow_runs_centralized_review_preflight() -> None:
    workflow = _workflow_text("verify-work.md")

    assert 'gpd validate review-preflight verify-work "${PHASE_ARG}" --strict' in workflow
    assert "gpd validate review-preflight verify-work --strict" in workflow
