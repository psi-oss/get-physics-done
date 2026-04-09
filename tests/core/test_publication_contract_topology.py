from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / "src" / "gpd" / "specs" / "workflows"
AGENTS_DIR = REPO_ROOT / "src" / "gpd" / "agents"
REFERENCES_DIR = REPO_ROOT / "src" / "gpd" / "specs" / "references" / "publication"
TEMPLATES_DIR = REPO_ROOT / "src" / "gpd" / "specs" / "templates" / "paper"


def test_publication_contract_files_use_canonical_names_without_compatibility_shims() -> None:
    round_contract = (REFERENCES_DIR / "publication-review-round-artifacts.md").read_text(encoding="utf-8")
    response_contract = (REFERENCES_DIR / "publication-response-artifacts.md").read_text(encoding="utf-8")
    bootstrap_preflight = (REFERENCES_DIR / "publication-bootstrap-preflight.md").read_text(encoding="utf-8")
    response_handoff = (REFERENCES_DIR / "publication-response-writer-handoff.md").read_text(encoding="utf-8")
    wrapper_guidance = (REFERENCES_DIR / "publication-review-wrapper-guidance.md").read_text(encoding="utf-8")
    manuscript_preflight = (TEMPLATES_DIR / "publication-manuscript-root-preflight.md").read_text(encoding="utf-8")

    assert "Canonical round-suffix and sibling-artifact contract for publication review rounds." in round_contract
    assert "GPD/REFEREE-REPORT{round_suffix}.md" in round_contract
    assert "GPD/AUTHOR-RESPONSE{round_suffix}.md" in round_contract
    assert "review-round-artifact-contract.md" not in round_contract

    assert "Canonical paired response-artifact and one-shot child-return contract for referee-response work." in response_contract
    assert "gpd_return.files_written" in response_contract
    assert "response-artifact-contract.md" not in response_contract

    assert "Canonical workflow-facing bootstrap and preflight reference for publication tasks." in bootstrap_preflight
    assert "publication-artifact-gates.md" not in bootstrap_preflight
    assert "Canonical workflow-facing handoff and completion reference for spawned response-writing work." in response_handoff
    assert "publication-artifact-gates.md" not in response_handoff
    assert "publication-bootstrap-preflight.md" in wrapper_guidance
    assert "publication-response-writer-handoff.md" in wrapper_guidance
    assert "publication-artifact-gates.md" not in wrapper_guidance

    assert "gpd paper-build" in manuscript_preflight
    assert "bibliography_audit_clean" in manuscript_preflight
    assert "reproducibility_ready" in manuscript_preflight
    assert "publication-artifact-gates.md" not in manuscript_preflight


def test_publication_workflows_and_agents_reference_only_the_canonical_publication_contracts() -> None:
    for path in (
        AGENTS_DIR / "gpd-paper-writer.md",
        AGENTS_DIR / "gpd-referee.md",
        WORKFLOWS_DIR / "write-paper.md",
        WORKFLOWS_DIR / "respond-to-referees.md",
        WORKFLOWS_DIR / "peer-review.md",
        WORKFLOWS_DIR / "arxiv-submission.md",
    ):
        text = path.read_text(encoding="utf-8")
        assert "publication-artifact-gates.md" not in text, path
        assert "review-round-artifact-contract.md" not in text, path
        assert "response-artifact-contract.md" not in text, path

    paper_writer = (AGENTS_DIR / "gpd-paper-writer.md").read_text(encoding="utf-8")
    referee = (AGENTS_DIR / "gpd-referee.md").read_text(encoding="utf-8")

    assert "publication-response-writer-handoff.md" in paper_writer
    assert "publication-response-artifacts.md" not in paper_writer
    assert "publication-review-round-artifacts.md" not in paper_writer
    assert "publication-review-round-artifacts.md" in referee
    assert "publication-response-artifacts.md" in referee


def test_publication_workflow_prompt_surfaces_surface_the_shared_manuscript_root_contract_before_round_or_response_policy() -> None:
    write_paper = (WORKFLOWS_DIR / "write-paper.md").read_text(encoding="utf-8")
    respond = (WORKFLOWS_DIR / "respond-to-referees.md").read_text(encoding="utf-8")
    peer_review = (WORKFLOWS_DIR / "peer-review.md").read_text(encoding="utf-8")
    arxiv = (WORKFLOWS_DIR / "arxiv-submission.md").read_text(encoding="utf-8")
    bootstrap_include = "@{GPD_INSTALL_DIR}/references/publication/publication-bootstrap-preflight.md"
    handoff_include = "@{GPD_INSTALL_DIR}/references/publication/publication-response-writer-handoff.md"

    assert bootstrap_include in write_paper
    assert bootstrap_include in respond
    assert bootstrap_include in arxiv
    assert "templates/paper/publication-manuscript-root-preflight.md" in peer_review
    assert handoff_include in write_paper
    assert handoff_include in respond
    assert "publication-response-artifacts.md" not in peer_review
    assert "publication-response-artifacts.md" not in arxiv
