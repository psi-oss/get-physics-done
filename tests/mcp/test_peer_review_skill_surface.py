from __future__ import annotations

from pathlib import Path


def test_peer_review_skill_surfaces_reliability_reference_as_contract_document() -> None:
    from gpd.mcp.servers.skills_server import get_skill

    result = get_skill("gpd-peer-review")
    contract_documents = {Path(entry["path"]).name: entry for entry in result["contract_documents"]}

    assert "error" not in result
    assert result["context_mode"] == "project-aware"
    assert "peer-review-panel.md" in contract_documents
    assert "peer-review-reliability.md" in contract_documents
    assert "Peer Review Phase Reliability" in contract_documents["peer-review-reliability.md"]["body"]
    assert any(path.endswith("peer-review-reliability.md") for path in result["contract_references"])
    assert result["review_contract"]["required_evidence"] == [
        "resolved manuscript target",
        "project-backed review: phase summaries or milestone digest",
        "project-backed review: verification reports",
        "project-backed review: manuscript-root bibliography audit",
        "project-backed review: manuscript-root artifact manifest",
        "project-backed review: manuscript-root reproducibility manifest",
        "explicit external-artifact review: manuscript-local publication artifacts when present",
    ]
    assert result["review_contract"]["blocking_conditions"] == [
        "missing manuscript",
        "project-backed review missing project state",
        "project-backed review missing roadmap",
        "project-backed review missing conventions",
        "project-backed review missing research artifacts or verification reports",
        "project-backed review missing required manuscript-root publication artifacts",
        "degraded review integrity",
        "unsupported physical significance claims",
        "collapsed novelty or venue fit",
    ]
