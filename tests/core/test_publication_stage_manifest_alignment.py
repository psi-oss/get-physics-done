from __future__ import annotations

import json
from pathlib import Path

from gpd.core.workflow_staging import validate_workflow_stage_manifest_payload

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / "src" / "gpd" / "specs" / "workflows"
REFERENCES_DIR = REPO_ROOT / "src" / "gpd" / "specs" / "references" / "publication"


def _load_manifest(workflow_name: str) -> object:
    return validate_workflow_stage_manifest_payload(
        json.loads((WORKFLOWS_DIR / f"{workflow_name}-stage-manifest.json").read_text(encoding="utf-8")),
        expected_workflow_id=workflow_name,
    )


def test_write_paper_stage_manifest_uses_canonical_publication_contracts() -> None:
    manifest = _load_manifest("write-paper")

    assert manifest.stage_ids() == (
        "paper_bootstrap",
        "outline_and_scaffold",
        "figure_and_section_authoring",
        "consistency_and_references",
        "publication_review",
    )

    bootstrap = manifest.stage("paper_bootstrap")
    consistency = manifest.stage("consistency_and_references")
    publication_review = manifest.stage("publication_review")

    assert "references/publication/publication-review-round-artifacts.md" in bootstrap.must_not_eager_load
    assert "references/publication/publication-response-artifacts.md" in bootstrap.must_not_eager_load

    assert consistency.loaded_authorities == (
        "workflows/write-paper.md",
        "templates/paper/bibliography-audit-schema.md",
        "templates/paper/reproducibility-manifest.md",
    )
    assert publication_review.loaded_authorities == (
        "workflows/write-paper.md",
        "references/publication/publication-review-round-artifacts.md",
        "references/publication/publication-response-artifacts.md",
        "references/publication/peer-review-panel.md",
        "references/publication/peer-review-reliability.md",
        "templates/paper/review-ledger-schema.md",
        "templates/paper/referee-decision-schema.md",
    )
    assert "references/publication/publication-review-round-artifacts.md" in publication_review.loaded_authorities
    assert "references/publication/publication-response-artifacts.md" in publication_review.loaded_authorities
    assert "references/publication/peer-review-panel.md" in publication_review.loaded_authorities
    assert "references/publication/peer-review-reliability.md" in publication_review.loaded_authorities
    assert "templates/paper/review-ledger-schema.md" in publication_review.loaded_authorities
    assert "templates/paper/referee-decision-schema.md" in publication_review.loaded_authorities


def test_peer_review_stage_manifest_uses_canonical_publication_contracts() -> None:
    manifest = _load_manifest("peer-review")

    assert manifest.stage_ids() == (
        "bootstrap",
        "preflight",
        "artifact_discovery",
        "panel_stages",
        "final_adjudication",
        "finalize",
    )

    bootstrap = manifest.stage("bootstrap")
    preflight = manifest.stage("preflight")
    artifact_discovery = manifest.stage("artifact_discovery")
    final_adjudication = manifest.stage("final_adjudication")

    assert "references/publication/publication-review-round-artifacts.md" in bootstrap.must_not_eager_load
    assert "references/publication/publication-response-artifacts.md" in bootstrap.must_not_eager_load

    assert preflight.loaded_authorities[0] == "workflows/peer-review.md"
    assert "references/publication/peer-review-reliability.md" in preflight.loaded_authorities
    assert "templates/paper/paper-config-schema.md" in preflight.loaded_authorities
    assert "templates/paper/artifact-manifest-schema.md" in preflight.loaded_authorities
    assert "templates/paper/bibliography-audit-schema.md" in preflight.loaded_authorities
    assert "templates/paper/reproducibility-manifest.md" in preflight.loaded_authorities
    assert artifact_discovery.loaded_authorities == (
        "workflows/peer-review.md",
        "references/publication/publication-review-round-artifacts.md",
        "references/publication/publication-response-artifacts.md",
    )
    assert "references/publication/peer-review-panel.md" in final_adjudication.loaded_authorities
    assert "templates/paper/review-ledger-schema.md" in final_adjudication.loaded_authorities
    assert "templates/paper/referee-decision-schema.md" in final_adjudication.loaded_authorities


def test_publication_bootstrap_preflight_uses_canonical_publication_contracts() -> None:
    source = (REFERENCES_DIR / "publication-bootstrap-preflight.md").read_text(encoding="utf-8")

    assert "Canonical workflow-facing bootstrap and preflight reference for publication tasks." in source
    assert "publication-manuscript-root-preflight.md" in source
    assert "publication-review-round-artifacts.md" in source
    assert "publication-response-artifacts.md" in source
    assert "publication-artifact-gates.md" not in source


def test_publication_response_writer_handoff_uses_canonical_completion_gate() -> None:
    source = (REFERENCES_DIR / "publication-response-writer-handoff.md").read_text(encoding="utf-8")

    assert "Canonical workflow-facing handoff and completion reference for spawned response-writing work." in source
    assert "publication-response-artifacts.md" in source
    assert "status: checkpoint" in source
    assert "gpd_return.files_written" in source
    assert "publication-artifact-gates.md" not in source


def test_publication_review_wrapper_guidance_points_to_the_new_shared_refs() -> None:
    source = (REFERENCES_DIR / "publication-review-wrapper-guidance.md").read_text(encoding="utf-8")

    assert "publication-bootstrap-preflight.md" in source
    assert "publication-response-writer-handoff.md" in source
    assert "publication-artifact-gates.md" not in source
