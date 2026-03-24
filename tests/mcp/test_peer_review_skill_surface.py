from __future__ import annotations

from pathlib import Path


def test_peer_review_skill_surfaces_reliability_reference_as_contract_document() -> None:
    from gpd.mcp.servers.skills_server import get_skill

    result = get_skill("gpd-peer-review")
    contract_documents = {Path(entry["path"]).name: entry for entry in result["contract_documents"]}

    assert "error" not in result
    assert "peer-review-panel.md" in contract_documents
    assert "peer-review-reliability.md" in contract_documents
    assert "Peer Review Phase Reliability" in contract_documents["peer-review-reliability.md"]["body"]
    assert "peer-review-reliability.md" in result["contract_references"]
