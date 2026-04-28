from __future__ import annotations

from pathlib import Path


def test_peer_review_skill_surfaces_reliability_reference_as_contract_document() -> None:
    from gpd.mcp.servers.skills_server import get_skill

    result = get_skill("gpd-peer-review")
    contract_documents = {Path(entry["path"]).name: entry for entry in result["contract_documents"]}

    assert "error" not in result
    assert result["context_mode"] == "project-aware"
    assert contract_documents == {}
    assert any(path.endswith("peer-review-panel.md") for path in result["contract_references"])
    assert any(path.endswith("peer-review-reliability.md") for path in result["contract_references"])
    assert result["review_contract"]["required_evidence"] == [
        "existing manuscript or explicit external artifact target",
    ]
    assert result["review_contract"]["blocking_conditions"] == [
        "missing manuscript or explicit external artifact target",
        "degraded review integrity",
        "unsupported physical significance claims",
        "collapsed novelty or venue fit",
    ]
    assert result["review_contract"]["conditional_requirements"][0]["when"] == "project-backed manuscript review"
    assert any(
        variant["scope"] == "explicit_artifact" for variant in result["review_contract"].get("scope_variants", [])
    )
