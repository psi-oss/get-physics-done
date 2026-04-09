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
    assert "status: checkpoint" in source
    assert "gpd_return.files_written" in source
    assert "GPD/AUTHOR-RESPONSE{round_suffix}.md" in source
    assert "GPD/review/REFEREE_RESPONSE{round_suffix}.md" in source
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
    assert "GPD/AUTHOR-RESPONSE{round_suffix}.md" in source
    assert "GPD/review/REFEREE_RESPONSE{round_suffix}.md" in source
    assert "status: checkpoint" in source
    assert "gpd_return.files_written" in source
    assert "Do not accept stale preexisting files" in source
    assert "response-artifact-contract.md" not in source
    assert "publication-artifact-gates.md" not in source


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
