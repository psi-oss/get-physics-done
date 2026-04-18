from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / "src/gpd/specs/workflows"
AGENTS_DIR = REPO_ROOT / "src/gpd/agents"


def test_write_paper_balanced_mode_keeps_outline_as_working_draft_and_threads_mode_context() -> None:
    workflow = (WORKFLOWS_DIR / "write-paper.md").read_text(encoding="utf-8")

    assert "Do not force a routine outline-approval pause in balanced mode." in workflow
    assert 'WRITE_PAPER_ARGUMENTS="$ARGUMENTS"' in workflow
    assert "explicit `--intake path/to/paper-authoring-input.json`" in workflow
    assert "If `publication_bootstrap_mode` is `fresh_external_authoring_bootstrap`" in workflow
    assert (
        "If `autonomy=supervised`, present the outline for approval before proceeding. "
        "If `autonomy=balanced`, treat the outline as a working draft"
    ) in workflow
    assert "Present outline for approval before proceeding." not in workflow
    assert "<autonomy_mode>{AUTONOMY}</autonomy_mode>" in workflow
    assert "<research_mode>{RESEARCH_MODE}</research_mode>" in workflow
    assert workflow.count("<autonomy_mode>{AUTONOMY}</autonomy_mode>") >= 3
    assert workflow.count("<research_mode>{RESEARCH_MODE}</research_mode>") >= 3
    assert "Treat the emitted `.tex` file as the success artifact gate for each section." in workflow
    assert (
        "Treat `${PAPER_DIR}/CITATION-AUDIT.md`, the refreshed `${PAPER_DIR}/BIBLIOGRAPHY-AUDIT.json`, and the bibliographer's typed `gpd_return` envelope as the bibliography success gate; all three must be present, and the typed return must name the bibliography outputs, before the pass is accepted."
        in workflow
    )
    assert "Confirm `${PAPER_DIR}/BIBLIOGRAPHY-AUDIT.json` exists after the refresh before proceeding to reproducibility or strict review." in workflow
    assert "Do not accept a preexisting `.tex` file as a substitute for a successful spawn; a spawn error always leaves the section incomplete until a fresh typed return names the artifact and the file exists on disk." in workflow
    assert "Do not accept preexisting response files as a substitute for a successful spawn; the round remains incomplete until a fresh typed return names both outputs and both files exist on disk." in workflow
    assert "Embedded `write-paper` review parity for the bounded external-authoring lane is deferred" in workflow
    assert "route the user to standalone `gpd:peer-review`" in workflow
    assert "do not recommend `gpd:arxiv-submission` directly from this lane." in workflow


def test_respond_to_referees_balanced_mode_does_not_force_parse_confirmation() -> None:
    workflow = (WORKFLOWS_DIR / "respond-to-referees.md").read_text(encoding="utf-8")

    assert "research_mode" in workflow
    assert "RESEARCH_MODE=$(echo \"$INIT\" | gpd json get .research_mode --default balanced)" in workflow
    assert (
        "This workflow is project-aware: it may revise the active manuscript from the current GPD project or an explicit manuscript subject"
        in workflow
    )
    assert "Preferred explicit intake: `gpd:respond-to-referees --manuscript path/to/main.tex --report reviews/ref1.md --report reviews/ref2.md`" in workflow
    assert "Treat a bare positional path as a referee-report source only." in workflow
    assert (
        "Present the parsed structure. Ask for explicit user confirmation only in supervised mode or when the report source is ambiguous; "
        "balanced mode should treat the parse as working context"
    ) in workflow
    assert "Present the parsed structure for user confirmation:" not in workflow
    assert "<autonomy_mode>{AUTONOMY}</autonomy_mode>" in workflow
    assert "<research_mode>{RESEARCH_MODE}</research_mode>" in workflow
    assert "Treat `GPD/AUTHOR-RESPONSE{round_suffix}.md` and `GPD/review/REFEREE_RESPONSE{round_suffix}.md` as the response success gate." in workflow
    assert "fresh `gpd_return.files_written`" in workflow
    assert "Confirm the refreshed JSON artifact exists before treating the round as complete." in workflow
    assert "If the manuscript subject is an explicit external artifact, keep auxiliary response outputs under `GPD/`" in workflow


def test_peer_review_stage_six_requires_report_artifacts_and_threads_mode_context() -> None:
    workflow = (WORKFLOWS_DIR / "peer-review.md").read_text(encoding="utf-8")

    assert "Parse JSON for: `project_exists`, `state_exists`, `commit_docs`, `autonomy`, `research_mode`" in workflow
    assert "RESEARCH_MODE=$(echo \"$INIT\" | gpd json get .research_mode --default balanced)" in workflow
    assert "<autonomy_mode>{AUTONOMY}</autonomy_mode>" in workflow
    assert "<research_mode>{RESEARCH_MODE}</research_mode>" in workflow
    assert "Treat the referee report files as required final-stage artifacts." in workflow
    assert "confirm `GPD/REFEREE-REPORT{round_suffix}.md` and `GPD/REFEREE-REPORT{round_suffix}.tex` exist before treating the final recommendation as complete." in workflow
    assert "GPD/REFEREE-REPORT{round_suffix}.md" in workflow
    assert "GPD/REFEREE-REPORT{round_suffix}.tex" in workflow


def test_paper_writer_prompt_supports_bounded_external_authoring_without_workspace_mining() -> None:
    agent = (AGENTS_DIR / "gpd-paper-writer.md").read_text(encoding="utf-8")

    assert "for bounded external authoring, an explicit intake-manifest handoff" in agent
    assert "When `publication_bootstrap.mode` is `fresh_external_authoring_bootstrap`" in agent
    assert "the only supported non-project intake is explicit `--intake path/to/paper-authoring-input.json`" in agent
    assert "Do not scan `GPD/phases/*`, `GPD/milestones/*`, `GPD/STATE.md`, or unrelated folders to fill gaps." in agent
    assert "missing evidence bindings are hard blocks" in agent
