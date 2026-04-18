from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REFERENCES_DIR = REPO_ROOT / "src" / "gpd" / "specs" / "references" / "publication"
WORKFLOWS_DIR = REPO_ROOT / "src" / "gpd" / "specs" / "workflows"
AGENTS_DIR = REPO_ROOT / "src" / "gpd" / "agents"


def test_publication_bootstrap_preflight_defines_the_shared_publication_gate() -> None:
    source = (REFERENCES_DIR / "publication-bootstrap-preflight.md").read_text(encoding="utf-8")

    assert "Canonical workflow-facing bootstrap and preflight reference for publication tasks." in source
    assert "publication-manuscript-root-preflight.md" in source
    assert "publication-review-round-artifacts.md" in source
    assert "publication-response-artifacts.md" in source
    assert "publication-artifact-gates.md" not in source


def test_publication_response_writer_handoff_defines_one_shot_child_returns() -> None:
    source = (REFERENCES_DIR / "publication-response-writer-handoff.md").read_text(encoding="utf-8")

    assert "Canonical workflow-facing handoff and completion reference for spawned response-writing work." in source
    assert "A spawned response writer is one-shot. If user input is needed, it returns `status: checkpoint` and stops." in source
    assert "The orchestrator resumes with a fresh continuation handoff. It does not wait inside the same run." in source
    assert (
        "`status: completed` is provisional until the expected response files exist on disk and are named in fresh typed `gpd_return.files_written`."
        in source
    )
    assert "status: checkpoint" in source
    assert "gpd_return.files_written" in source
    assert "GPD/AUTHOR-RESPONSE{round_suffix}.md" in source
    assert "GPD/review/REFEREE_RESPONSE{round_suffix}.md" in source
    assert "Do not treat prose-only status messages or stale preexisting files as proof of completion." in source
    assert "publication-artifact-gates.md" not in source


def test_publication_review_wrapper_guidance_points_to_the_new_shared_refs() -> None:
    source = (REFERENCES_DIR / "publication-review-wrapper-guidance.md").read_text(encoding="utf-8")

    assert "publication-bootstrap-preflight.md" in source
    assert "publication-response-writer-handoff.md" in source
    assert "publication-artifact-gates.md" not in source


def test_publication_review_round_artifacts_define_canonical_round_family() -> None:
    source = (REFERENCES_DIR / "publication-review-round-artifacts.md").read_text(encoding="utf-8")

    assert "Canonical round-suffix and sibling-artifact contract for publication review rounds." in source
    assert "Round 1 uses `round_suffix=\"\"`." in source
    assert "Round `N` for `N >= 2` uses `round_suffix=\"-R{N}\"`." in source
    assert "GPD/REFEREE-REPORT{round_suffix}.md" in source
    assert "GPD/review/REVIEW-LEDGER{round_suffix}.json" in source
    assert "GPD/review/REFEREE-DECISION{round_suffix}.json" in source
    assert "GPD/AUTHOR-RESPONSE{round_suffix}.md" in source
    assert "GPD/review/REFEREE_RESPONSE{round_suffix}.md" in source
    assert "GPD/review/PROOF-REDTEAM{round_suffix}.md" in source
    assert "review-round-artifact-contract.md" not in source
    assert "publication-artifact-gates.md" not in source


def test_publication_response_artifacts_define_paired_completion_gate() -> None:
    source = (REFERENCES_DIR / "publication-response-artifacts.md").read_text(encoding="utf-8")

    assert "Canonical paired response-artifact and one-shot child-return contract for referee-response work." in source
    assert (
        "If a spawned writer needs user input, it returns `status: checkpoint` and stops. "
        "The orchestrator resumes with a fresh continuation; it does not wait inside the same run."
        in source
    )
    assert (
        "A reported `status: completed` is provisional until the response pair exists on disk and those same fresh paths appear in typed `gpd_return.files_written`."
        in source
    )
    assert "GPD/AUTHOR-RESPONSE{round_suffix}.md" in source
    assert "GPD/review/REFEREE_RESPONSE{round_suffix}.md" in source
    assert "Treat the two files as one success gate" in source
    assert "do not mark the round complete when only one of them is current" in source
    assert "Successful response-round completion requires both" in source
    assert "status: checkpoint" in source
    assert "gpd_return.files_written" in source
    assert "Do not accept stale preexisting files" in source
    assert "response-artifact-contract.md" not in source
    assert "publication-artifact-gates.md" not in source


def test_referee_revision_mode_requires_a_paired_response_package() -> None:
    referee = (AGENTS_DIR / "gpd-referee.md").read_text(encoding="utf-8")

    assert "paired response package" in referee
    assert "GPD/AUTHOR-RESPONSE.md" in referee
    assert "GPD/AUTHOR-RESPONSE-R{N}.md" in referee
    assert "GPD/review/REFEREE_RESPONSE.md" in referee
    assert "GPD/review/REFEREE_RESPONSE-R{N}.md" in referee
    assert "suffixes disagree" in referee
    assert "incomplete response package" in referee


def test_paper_writer_and_referee_load_the_canonical_publication_response_contracts() -> None:
    paper_writer = (AGENTS_DIR / "gpd-paper-writer.md").read_text(encoding="utf-8")
    referee = (AGENTS_DIR / "gpd-referee.md").read_text(encoding="utf-8")
    write_paper = (WORKFLOWS_DIR / "write-paper.md").read_text(encoding="utf-8")
    respond = (WORKFLOWS_DIR / "respond-to-referees.md").read_text(encoding="utf-8")

    for source in (paper_writer, referee):
        assert "publication-artifact-gates.md" not in source
        assert "response-artifact-contract.md" not in source
        assert "review-round-artifact-contract.md" not in source

    assert "publication-response-writer-handoff.md" in paper_writer
    assert "publication-response-artifacts.md" not in paper_writer
    assert "publication-review-round-artifacts.md" not in paper_writer
    assert "publication-response-artifacts.md" in referee
    assert "publication-review-round-artifacts.md" in referee
    assert "fixed" in paper_writer and "on disk" in paper_writer
    assert "fixed" in referee and "on disk" in referee
    assert "gpd_return.files_written" in write_paper
    assert "both outputs and both files exist on disk" in write_paper
    assert "publication-bootstrap-preflight.md" in write_paper
    assert "publication-response-writer-handoff.md" in write_paper
    assert "publication-bootstrap-preflight.md" in respond
    assert "publication-response-writer-handoff.md" in respond
    assert "publication-response-artifacts.md" not in write_paper
    assert "publication-response-artifacts.md" not in respond
    assert "fresh child `gpd_return.files_written`" in respond
    assert "revised section file plus both response artifacts" in respond


def test_peer_review_stage_six_requires_fresh_referee_return_and_artifacts() -> None:
    workflow = (WORKFLOWS_DIR / "peer-review.md").read_text(encoding="utf-8")

    assert "status: checkpoint" in workflow
    assert "Do not keep the same spawned run alive waiting for confirmation." in workflow
    assert "fresh continuation handoff" in workflow


def test_peer_review_parallel_wave_stops_terminal_children_before_stage_4() -> None:
    workflow = (WORKFLOWS_DIR / "peer-review.md").read_text(encoding="utf-8")

    assert (
        "If the runtime supports parallel subagent execution, run Stage 2, Stage 3, and the conditional proof-critique pass in parallel when theorem-bearing claims are present."
        in workflow
    )
    assert "If literature, math, or the conditional proof-critique stage fails, STOP and report the failure." in workflow
    assert "Stages 2-3 recovery -- Validate literature and math outputs before proceeding." in workflow
    assert (
        "Re-run only the failed stage subagent with the same inputs and an explicit reminder to match the `StageReviewReport` JSON schema from `peer-review-panel.md`"
        in workflow
    )
    assert "Do not proceed to Stage 4." in workflow
    assert (
        "If the proof-redteam artifact is missing, malformed, lacks the canonical frontmatter, or omits required sections, retry `gpd-check-proof` once with the same inputs"
        in workflow
    )
    assert "If the retry also fails, STOP the pipeline and report that proof review could not be completed." in workflow


def test_peer_review_later_stages_restart_from_fresh_context_and_written_artifacts() -> None:
    workflow = (WORKFLOWS_DIR / "peer-review.md").read_text(encoding="utf-8")

    assert "Operate in physical-soundness stage mode with a fresh context." in workflow
    assert "Operate in interestingness-and-venue-fit stage mode with a fresh context." in workflow
    assert "GPD/review/STAGE-math{round_suffix}.json" in workflow
    assert "GPD/review/STAGE-literature{round_suffix}.json" in workflow
    assert "GPD/review/PROOF-REDTEAM{round_suffix}.md` if proof-bearing review is active" in workflow
    assert "GPD/review/STAGE-physics{round_suffix}.json" in workflow
    assert "Stage 4 recovery -- Validate the physics output before proceeding." in workflow
    assert "Do not proceed to Stage 5." in workflow
    assert "Stage 5 recovery -- Validate the significance output before proceeding." in workflow
    assert "Do not proceed to Stage 6 adjudication." in workflow


def test_referee_stage_six_files_written_must_be_fresh_current_run_outputs() -> None:
    referee = (AGENTS_DIR / "gpd-referee.md").read_text(encoding="utf-8")

    assert "Preexisting files are stale unless the same paths appear in fresh `gpd_return.files_written` from this run." in referee
    assert "For all statuses, `files_written` must list only files actually written in this run from the Stage 6 allowlist." in referee
    assert (
        "For `blocked` returns caused by upstream staged-review artifact failures, keep `files_written` empty "
        "unless you wrote only `GPD/CONSISTENCY-REPORT.md`."
    ) in referee


def test_referee_stage_six_write_allowlist_stops_before_upstream_repairs() -> None:
    referee = (AGENTS_DIR / "gpd-referee.md").read_text(encoding="utf-8")

    assert "Stage 6 writable allowlist" in referee
    assert "GPD/REFEREE-REPORT{round_suffix}.md" in referee
    assert "GPD/REFEREE-REPORT{round_suffix}.tex" in referee
    assert "GPD/review/REVIEW-LEDGER{round_suffix}.json" in referee
    assert "GPD/review/REFEREE-DECISION{round_suffix}.json" in referee
    assert "GPD/CONSISTENCY-REPORT.md" in referee
    assert "never rewrite `GPD/review/CLAIMS{round_suffix}.json`" in referee
    assert "any `GPD/review/STAGE-*.json`" in referee
    assert "`GPD/review/PROOF-REDTEAM{round_suffix}.md`" in referee
    assert (
        "If an upstream staged-review artifact is missing, malformed, stale, suffix-inconsistent, "
        "manuscript-inconsistent, or mutually inconsistent, return `gpd_return.status: blocked`"
    ) in referee


def test_stage_six_handoff_closure_and_retry_freshness_remain_explicit() -> None:
    workflow = (WORKFLOWS_DIR / "peer-review.md").read_text(encoding="utf-8")
    referee = (AGENTS_DIR / "gpd-referee.md").read_text(encoding="utf-8")

    assert "Do not trust the referee's success text until that typed return, the on-disk files, and the validators all agree." in workflow
    assert (
        "Treat the Stage 6 return as incomplete if the fresh `gpd_return.files_written` set omits a Stage 6 artifact written in this run or lists any upstream staged-review artifact path."
        in workflow
    )
    assert "Only retry Stage 6 for Stage 6-owned artifacts." in workflow
    assert "Do not retry Stage 6 as an upstream repair step." in workflow
    assert "If the eligible Stage 6 retry also fails," in workflow
    assert "Do not proceed to report summarization." in workflow
    assert "Checkpoint ownership is orchestrator-side: when you stop, the orchestrator presents the issue and owns the fresh continuation handoff." in referee
    assert (
        "`gpd_return.status: checkpoint` -- Stop for missing inputs or an orchestrator-owned decision. Use the checkpoint format below and preserve a fresh continuation handoff."
        in referee
    )
    assert (
        "`gpd_return.status: completed` -- Final review finished. Write the full report plus any decision/ledger artifacts produced in this run, and treat completion as valid only when the fresh `gpd_return.files_written` names only Stage 6-owned artifacts from this run and they exist on disk."
        in referee
    )
