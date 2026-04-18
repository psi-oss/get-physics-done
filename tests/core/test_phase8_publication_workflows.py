from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / "src/gpd/specs/workflows"


def test_write_paper_balanced_mode_keeps_outline_as_working_draft_and_threads_mode_context() -> None:
    workflow = (WORKFLOWS_DIR / "write-paper.md").read_text(encoding="utf-8")

    assert "Do not force a routine outline-approval pause in balanced mode." in workflow
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


def test_respond_to_referees_balanced_mode_does_not_force_parse_confirmation() -> None:
    workflow = (WORKFLOWS_DIR / "respond-to-referees.md").read_text(encoding="utf-8")

    assert "research_mode" in workflow
    assert "RESEARCH_MODE=$(echo \"$INIT\" | gpd json get .research_mode --default balanced)" in workflow
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


def test_peer_review_stage_six_limits_writes_to_stage6_owned_artifacts() -> None:
    workflow = (WORKFLOWS_DIR / "peer-review.md").read_text(encoding="utf-8")

    assert "Your writable scope is limited to Stage 6-owned adjudication artifacts for this round:" in workflow
    assert "GPD/review/REVIEW-LEDGER{round_suffix}.json" in workflow
    assert "GPD/review/REFEREE-DECISION{round_suffix}.json" in workflow
    assert "GPD/CONSISTENCY-REPORT.md" in workflow
    assert "Do not modify `GPD/review/CLAIMS{round_suffix}.json`, any `GPD/review/STAGE-*.json`, or `GPD/review/PROOF-REDTEAM{round_suffix}.md`." in workflow
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
