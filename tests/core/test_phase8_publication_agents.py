from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO_ROOT / "src" / "gpd" / "agents"


def _read_agent(name: str) -> str:
    return (AGENTS_DIR / name).read_text(encoding="utf-8")


def test_paper_writer_balanced_mode_avoids_in_run_approval_language() -> None:
    source = _read_agent("gpd-paper-writer.md")

    assert "proceed unless objected" not in source
    assert "Draft the outline, self-review it, and pause only if the narrative or claims need user judgment" in source
    assert "Balanced mode follows the publication-pipeline matrix" in source
    assert "Checkpoint ownership is orchestrator-side" in source
    assert "fresh continuation handoff" in source


def test_bibliographer_balanced_mode_adds_verified_citations_without_approval_loop() -> None:
    source = _read_agent("gpd-bibliographer.md")

    assert "Present a batch for approval" not in source
    assert "Add verified citations automatically; pause only for uncertain matches, borderline relevance, or citation-scope changes." in source
    assert "| Citation addition |" in source
    assert "Checkpoint ownership is orchestrator-side" in source
    assert "fresh continuation handoff" in source


def test_referee_checkpoint_ownership_and_mode_routing_are_explicit() -> None:
    source = _read_agent("gpd-referee.md")

    assert "Checkpoint ownership is orchestrator-side" in source
    assert "fresh continuation handoff" in source
    assert "publication-pipeline-modes.md" in source


def test_peer_review_and_referee_skill_surfaces_keep_lifecycle_cleanup_boundary() -> None:
    from gpd.mcp.servers.skills_server import get_skill

    peer_review = get_skill("gpd-peer-review")
    referee = get_skill("gpd-referee")
    peer_review_content = peer_review["content"]
    referee_content = referee["content"]

    assert "error" not in peer_review
    assert "error" not in referee
    assert "treated that finished child as closed and retired" in peer_review_content
    assert "transient execution state, scratch reasoning, and live conversation context must not be reused" in peer_review_content
    assert "retire each finished child handoff" in peer_review_content
    assert "do not keep the adjudication run live while deciding what to do next" in peer_review_content
    assert "Checkpoint ownership is orchestrator-side" in referee_content
    assert "owns the fresh continuation handoff" in referee_content
    assert "Preexisting files are stale unless the same paths appear in fresh `gpd_return.files_written` from this run." in referee_content
    assert "For all statuses, `files_written` must list only files actually written in this run from the Stage 6 allowlist." in referee_content
