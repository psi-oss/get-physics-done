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

    assert "Parse bootstrap JSON for: `project_exists`, `state_exists`, `commit_docs`, `autonomy`, `research_mode`" in workflow
    assert "RESEARCH_MODE=$(echo \"$BOOTSTRAP\" | gpd json get .research_mode --default balanced)" in workflow
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


def test_peer_review_workflow_retires_finished_handoffs_and_clears_transient_state() -> None:
    workflow = (WORKFLOWS_DIR / "peer-review.md").read_text(encoding="utf-8")

    assert (
        "A spawned handoff is not complete until the orchestrator has captured its typed return, "
        "verified the stage-owned artifact boundary on disk, and then treated that finished child "
        "as closed and retired." in workflow
    )
    assert (
        "Once retired, its transient execution state, scratch reasoning, and live conversation "
        "context must not be reused." in workflow
    )
    assert (
        "Every downstream stage must begin from persisted artifacts plus the explicitly declared "
        "carry-forward inputs for that stage." in workflow
    )
    assert (
        "If subagent spawning is unavailable and the workflow falls back to sequential execution "
        "in the main context, emulate the same boundary discipline: finish one stage, persist and "
        "verify its artifacts, clear the stage-local transient state, and begin the next stage "
        "only from those persisted outputs and declared carry-forward inputs." in workflow
    )


def test_peer_review_workflow_requires_barriers_and_cleanup_before_downstream_stage_spawns() -> None:
    workflow = (WORKFLOWS_DIR / "peer-review.md").read_text(encoding="utf-8")

    assert "Treat this recovery step as the Stage 2 / Stage 3 / proof-review branch barrier." in workflow
    assert (
        "Before Stage 4 can spawn, the orchestrator must capture the typed return from every "
        "launched branch in the wave, confirm that the persisted artifacts for this round exist "
        "and validate, and then retire each finished child handoff." in workflow
    )
    assert (
        "Later stages and retries must restart from the written artifacts above plus the declared "
        "carry-forward inputs, not from branch-local live context." in workflow
    )
    assert (
        "After the Stage 4 typed return is captured and "
        "`${REVIEW_ROOT}/STAGE-physics{round_suffix}.json` validates, treat the finished Stage 4 "
        "handoff as closed and retired before spawning Stage 5." in workflow
    )
    assert "Stage 5 must start from the persisted stage artifacts and declared carry-forward inputs only." in workflow
    assert (
        "After the Stage 5 typed return is captured and "
        "`${REVIEW_ROOT}/STAGE-interestingness{round_suffix}.json` validates, treat the finished "
        "Stage 5 handoff as closed and retired before spawning Stage 6." in workflow
    )
    assert "Stage 6 must begin from the persisted stage artifacts and declared carry-forward inputs only." in workflow
    assert (
        "Capture the Stage 6 typed return first, then treat the finished adjudication handoff as "
        "closed and retired before classifying the outcome as recovery-eligible, upstream-blocked, "
        "or complete." in workflow
    )


def test_peer_review_stage_six_limits_writes_to_stage6_owned_artifacts() -> None:
    workflow = (WORKFLOWS_DIR / "peer-review.md").read_text(encoding="utf-8")

    assert "Your writable scope is limited to Stage 6-owned adjudication artifacts for this round:" in workflow
    assert "${REVIEW_ROOT}/REVIEW-LEDGER{round_suffix}.json" in workflow
    assert "${REVIEW_ROOT}/REFEREE-DECISION{round_suffix}.json" in workflow
    assert "GPD/CONSISTENCY-REPORT.md" in workflow
    assert "Do not modify `${REVIEW_ROOT}/CLAIMS{round_suffix}.json`, any `${REVIEW_ROOT}/STAGE-*.json`, or `${REVIEW_ROOT}/PROOF-REDTEAM{round_suffix}.md`." in workflow
    assert "Treat any `gpd_return.files_written` entry outside the Stage 6 allowlist as a failed handoff" in workflow
    assert "Require the fresh `gpd_return.files_written` set to stay within the Stage 6-owned allowlist:" in workflow
    assert (
        "Treat the Stage 6 return as incomplete if the fresh `gpd_return.files_written` set omits a Stage 6 artifact written in this run or lists any upstream staged-review artifact path."
        in workflow
    )


def test_peer_review_stage_six_fails_back_to_earliest_upstream_stage_on_inconsistent_inputs() -> None:
    workflow = (WORKFLOWS_DIR / "peer-review.md").read_text(encoding="utf-8")

    assert "return `gpd_return.status: blocked` and hand the failure back to the earliest failing upstream stage" in workflow
    assert "Do not retry Stage 6 as an upstream repair step." in workflow
    assert "Use this upstream fail-back routing:" in workflow
    assert "`CLAIMS{round_suffix}.json` or `STAGE-reader{round_suffix}.json` -> rerun Stage 1" in workflow
    assert "`STAGE-math{round_suffix}.json` or `PROOF-REDTEAM{round_suffix}.md` -> rerun Stage 3" in workflow
    assert "`STAGE-interestingness{round_suffix}.json` -> rerun Stage 5" in workflow
    assert "If multiple upstream artifacts disagree, rerun the earliest stage in that list." in workflow
