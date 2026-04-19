from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / "src/gpd/specs/workflows"
COMMANDS_DIR = REPO_ROOT / "src/gpd/commands"
PUBLICATION_BOOTSTRAP_PREFLIGHT_INCLUDE = (
    "@{GPD_INSTALL_DIR}/references/publication/publication-bootstrap-preflight.md"
)
PUBLICATION_RESPONSE_WRITER_HANDOFF_INCLUDE = (
    "@{GPD_INSTALL_DIR}/references/publication/publication-response-writer-handoff.md"
)
PUBLICATION_ROUND_ARTIFACTS_INCLUDE = (
    "@{GPD_INSTALL_DIR}/references/publication/publication-review-round-artifacts.md"
)
PUBLICATION_REVIEW_RELIABILITY_INCLUDE = "@{GPD_INSTALL_DIR}/references/publication/peer-review-reliability.md"


def _workflow_text(name: str) -> str:
    return (WORKFLOWS_DIR / name).read_text(encoding="utf-8")


def _command_text(name: str) -> str:
    return (COMMANDS_DIR / name).read_text(encoding="utf-8")


def test_write_paper_workflow_runs_centralized_review_preflight() -> None:
    workflow = _workflow_text("write-paper.md")
    shared_preflight = (
        REPO_ROOT / "src/gpd/specs/templates/paper/publication-manuscript-root-preflight.md"
    ).read_text(encoding="utf-8")

    assert "gpd validate review-preflight write-paper --strict" in workflow
    assert "Run the centralized review preflight before continuing:" in workflow
    assert PUBLICATION_BOOTSTRAP_PREFLIGHT_INCLUDE in workflow
    assert PUBLICATION_RESPONSE_WRITER_HANDOFF_INCLUDE in workflow
    assert PUBLICATION_ROUND_ARTIFACTS_INCLUDE in workflow
    assert "artifacts copied from another manuscript root" in shared_preflight
    assert "Do not use ad hoc wildcard discovery or first-match filename scans." in shared_preflight
    assert "gpd paper-build" in shared_preflight
    assert "bibliography_audit_clean" in shared_preflight
    assert "reproducibility_ready" in shared_preflight
    assert "missing manuscript" not in workflow
    assert 'PAPER_DIR="${publication_bootstrap_root}"' in workflow
    assert '# e.g. PAPER_DIR="paper" or PAPER_DIR="GPD/publication/${subject_slug}/manuscript"' in workflow
    assert '${PAPER_DIR}/{topic_specific_stem}.tex' in workflow


def test_respond_to_referees_workflow_runs_centralized_review_preflight() -> None:
    workflow = _workflow_text("respond-to-referees.md")
    command = _command_text("respond-to-referees.md")
    shared_preflight = (
        REPO_ROOT / "src/gpd/specs/templates/paper/publication-manuscript-root-preflight.md"
    ).read_text(encoding="utf-8")

    assert "context_mode: project-aware" in command
    assert "argument-hint: \"[--manuscript PATH] (--report PATH [--report PATH...] | paste)\"" in command
    assert "command-policy:" in command
    assert "subject_kind: publication" in command
    assert "explicit_input_kinds:" in command
    assert "- manuscript_path" in command
    assert "- referee_report_path" in command
    assert "- paste_referee_report" in command
    assert "GPD/publication/*/manuscript/*.tex" in command
    assert "GPD/publication/*/manuscript/*.md" in command
    assert "default_output_subtree: GPD" in command
    assert "scope_variants:" in command
    assert "scope: explicit_external_manuscript" in command
    assert "Project-backed response rounds keep the current global `GPD/` / `GPD/review/` ownership." in command
    assert "subject-owned publication root at `GPD/publication/{subject_slug}`" in command
    assert "Set `PREFLIGHT_ARGUMENTS` to the validator-safe normalized intake string before shelling out." in workflow
    assert "Preferred explicit intake: `gpd:respond-to-referees --manuscript path/to/main.tex --report reviews/ref1.md --report reviews/ref2.md`" in workflow
    assert 'gpd --raw validate command-context respond-to-referees -- "$PREFLIGHT_ARGUMENTS"' in workflow
    assert 'gpd validate review-preflight respond-to-referees "$ARGUMENTS" --strict' in workflow
    assert 'gpd validate review-preflight respond-to-referees --strict -- "$PREFLIGHT_ARGUMENTS"' in workflow
    assert "gpd validate review-preflight respond-to-referees --strict" in workflow
    assert "Treat a bare positional path as a referee-report source only." in workflow
    assert "the end-of-options marker is mandatory in both validator calls" in workflow
    assert "missing referee report source when provided as a path" in workflow
    assert "In explicit external-manuscript mode, `project_state` and `conventions` are advisory only." in workflow
    assert "Any spawned agent that needs user input must return `status: checkpoint` and stop" in workflow
    assert "Do not ask the child agent to wait inside the same run" in workflow
    assert "Apply the shared publication bootstrap preflight exactly:" in workflow
    assert PUBLICATION_BOOTSTRAP_PREFLIGHT_INCLUDE in workflow
    assert PUBLICATION_RESPONSE_WRITER_HANDOFF_INCLUDE in workflow
    assert "bibliography_audit_clean" in shared_preflight
    assert "reproducibility_ready" in shared_preflight
    assert "Treat those files as complete only if the expected mirrored artifacts exist on disk" in workflow
    assert "import or normalize it into `GPD/REFEREE-REPORT{round_suffix}.md` before parsing comments" in workflow
    assert "Do not write `AUTHOR-RESPONSE*` or `REFEREE_RESPONSE*` beside `${PAPER_DIR}` or beside the imported report source." in workflow
    assert "keep auxiliary response outputs under `GPD/`" in workflow
    assert "managed subject-owned publication root at `GPD/publication/{subject_slug}`" in workflow
    assert "Do not duplicate the pair into both the subject-owned root and the global project root in one run." in workflow
    assert "${PAPER_DIR}/response-letter.tex" in workflow
    assert "${PAPER_DIR}/{section}.tex" in workflow


def test_arxiv_submission_workflow_runs_centralized_review_preflight() -> None:
    workflow = _workflow_text("arxiv-submission.md")
    shared_preflight = (
        REPO_ROOT / "src/gpd/specs/templates/paper/publication-manuscript-root-preflight.md"
    ).read_text(encoding="utf-8")

    assert 'gpd validate review-preflight arxiv-submission "$ARGUMENTS" --strict' in workflow
    assert "gpd validate review-preflight arxiv-submission --strict" in workflow
    assert "Use the shared publication bootstrap reference as the source of truth" in workflow
    assert "@{GPD_INSTALL_DIR}/references/publication/publication-bootstrap-preflight.md" in workflow
    assert PUBLICATION_REVIEW_RELIABILITY_INCLUDE in workflow
    assert PUBLICATION_ROUND_ARTIFACTS_INCLUDE in workflow
    assert PUBLICATION_RESPONSE_WRITER_HANDOFF_INCLUDE not in workflow
    assert (
        "For a resumed manuscript, strict preflight reads `ARTIFACT-MANIFEST.json`, `BIBLIOGRAPHY-AUDIT.json`, and "
        "`reproducibility-manifest.json` from the resolved manuscript directory itself."
        in shared_preflight
    )
    assert "bibliography_audit_clean" in shared_preflight
    assert "reproducibility_ready" in shared_preflight
    assert "Strict preflight also requires `ARTIFACT-MANIFEST.json` and `BIBLIOGRAPHY-AUDIT.json` beside the resolved manuscript entry point." in workflow
    assert "Strict preflight also requires the latest round-specific staged `REVIEW-LEDGER*.json` / `REFEREE-DECISION*.json` pair as authoritative submission-gate input." in workflow
    assert "latest recommendation is `accept` or `minor_revision` and there are no unresolved blocking issues" in workflow
    assert "`manuscript_proof_review` must also already be cleared" in workflow
    assert "The same resolved manuscript root is also the strict preflight source of truth" in workflow
    assert "If `$ARGUMENTS` specifies a `.tex` file, set `resolved_main_tex` to that file" in workflow
    assert "That file must already live under `paper/`, `manuscript/`, `draft/`, or `GPD/publication/<subject_slug>/manuscript/`." in workflow
    assert "canonical manuscript `.tex` entrypoint under that supported root" in workflow
    assert "Do not accept arbitrary external directories or standalone `.tex` entrypoints outside those supported roots." in workflow
    assert 'MAIN_SOURCE="${resolved_main_tex}"' in workflow
    assert 'PACKAGE_ROOT="GPD/publication/${subject_slug}/arxiv"' in workflow
    assert 'SUBMISSION_DIR="${PACKAGE_ROOT}/submission"' in workflow
    assert 'PACKAGE_TARBALL="${PACKAGE_ROOT}/arxiv-submission.tar.gz"' in workflow
    assert "Do not write proof-review manifests, package staging trees, or tarballs beside the manuscript root itself." in workflow


def test_peer_review_workflow_runs_centralized_review_preflight_with_explicit_arguments() -> None:
    workflow = _workflow_text("peer-review.md")

    assert 'gpd validate review-preflight peer-review "$REVIEW_TARGET" --strict' in workflow
    assert "gpd validate review-preflight peer-review --strict" not in workflow
    assert "If any spawned reviewer or proof auditor needs user input, it must return `status: checkpoint` and stop." in workflow
    assert "Do not keep the same spawned run alive waiting for confirmation." in workflow
    assert "Do not trust the referee's success text until that typed return, the on-disk files, and the validators all agree." in workflow


def test_publication_review_workflows_reference_shared_manuscript_root_contract() -> None:
    for command_name in ("respond-to-referees.md", "arxiv-submission.md"):
        command_text = _command_text(command_name)
        assert PUBLICATION_BOOTSTRAP_PREFLIGHT_INCLUDE not in command_text
        assert PUBLICATION_ROUND_ARTIFACTS_INCLUDE not in command_text
        assert PUBLICATION_RESPONSE_WRITER_HANDOFF_INCLUDE not in command_text
        assert PUBLICATION_REVIEW_RELIABILITY_INCLUDE not in command_text

    for workflow_name in ("respond-to-referees.md", "arxiv-submission.md"):
        workflow_text = _workflow_text(workflow_name)
        assert PUBLICATION_BOOTSTRAP_PREFLIGHT_INCLUDE in workflow_text
        if workflow_name == "respond-to-referees.md":
            assert PUBLICATION_RESPONSE_WRITER_HANDOFF_INCLUDE in workflow_text
        else:
            assert PUBLICATION_RESPONSE_WRITER_HANDOFF_INCLUDE not in workflow_text
            assert PUBLICATION_ROUND_ARTIFACTS_INCLUDE in workflow_text
        assert PUBLICATION_REVIEW_RELIABILITY_INCLUDE in workflow_text


def test_verify_work_workflow_runs_centralized_review_preflight() -> None:
    workflow = _workflow_text("verify-work.md")

    assert 'gpd validate review-preflight verify-work "${PHASE_ARG}" --strict' in workflow
    assert "gpd validate review-preflight verify-work --strict" in workflow


def test_review_knowledge_workflow_keeps_strict_current_workspace_canonical_target_contract() -> None:
    workflow = _workflow_text("review-knowledge.md")
    command = _command_text("review-knowledge.md")

    assert "context_mode: project-aware" in command
    assert "review_mode: review" in command
    assert "knowledge_target" in command
    assert "knowledge_document" in command
    assert "knowledge_review_freshness" in command
    assert "missing project state" not in command
    assert "GPD/knowledge/reviews/{knowledge_id}-R{review_round}-REVIEW.md" in command
    assert "{round_suffix}" not in command
    assert "Keep this init bound to the workspace the user invoked from." in workflow
    assert "do not auto-reenter a different recent project here." in workflow
    assert 'CONTEXT=$(gpd --raw validate command-context review-knowledge "$ARGUMENTS")' in workflow
    assert 'REVIEW_PREFLIGHT=$(gpd --raw validate review-preflight review-knowledge "$ARGUMENTS" --strict)' in workflow
    assert 'echo "$REVIEW_PREFLIGHT"' in workflow
    assert "Accept only:" in workflow
    assert "an exact current-workspace `GPD/knowledge/{knowledge_id}.md` path" in workflow
    assert "a canonical `K-*` knowledge_id that resolves uniquely to that path" in workflow
    assert "Do not guess from fuzzy topic text, stem similarity, or filename ordering." in workflow
