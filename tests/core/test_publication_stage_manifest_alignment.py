from __future__ import annotations

import json
from pathlib import Path

from gpd.core.workflow_staging import (
    WRITE_PAPER_MANAGED_INTAKE_ROOT,
    WRITE_PAPER_MANAGED_MANUSCRIPT_ROOT,
    validate_workflow_stage_manifest_payload,
)

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
    outline = manifest.stage("outline_and_scaffold")
    authoring = manifest.stage("figure_and_section_authoring")
    consistency = manifest.stage("consistency_and_references")
    publication_review = manifest.stage("publication_review")

    assert "publication_subject_status" in bootstrap.required_init_fields
    assert "publication_bootstrap_mode" in bootstrap.required_init_fields
    assert "publication_bootstrap_root" in bootstrap.required_init_fields
    assert "artifact_manifest_path" in bootstrap.required_init_fields
    assert bootstrap.writes_allowed == ()
    assert "contract_intake" in bootstrap.required_init_fields
    assert "effective_reference_intake" in bootstrap.required_init_fields
    assert "publication_subject_slug" in bootstrap.required_init_fields
    assert "publication_lane_kind" in bootstrap.required_init_fields
    assert "publication_lane_owner" in bootstrap.required_init_fields
    assert "selected_publication_root" in bootstrap.required_init_fields
    assert "publication_intake_root" in bootstrap.required_init_fields
    assert "managed_publication_root" in bootstrap.required_init_fields
    assert "managed_manuscript_root" in bootstrap.required_init_fields
    assert outline.writes_allowed[0] == WRITE_PAPER_MANAGED_MANUSCRIPT_ROOT
    assert WRITE_PAPER_MANAGED_INTAKE_ROOT in outline.writes_allowed
    assert authoring.writes_allowed[0] == WRITE_PAPER_MANAGED_MANUSCRIPT_ROOT
    assert consistency.writes_allowed[0] == WRITE_PAPER_MANAGED_MANUSCRIPT_ROOT
    assert publication_review.writes_allowed[0] == WRITE_PAPER_MANAGED_MANUSCRIPT_ROOT
    assert "GPD/references-status.json" in consistency.writes_allowed
    assert "GPD/AUTHOR-RESPONSE.md" in publication_review.writes_allowed
    assert "GPD/REFEREE-REPORT.tex" in publication_review.writes_allowed

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
    panel_stages = manifest.stage("panel_stages")
    final_adjudication = manifest.stage("final_adjudication")

    assert "references/publication/publication-review-round-artifacts.md" in bootstrap.must_not_eager_load
    assert "references/publication/publication-response-artifacts.md" in bootstrap.must_not_eager_load
    assert "publication_subject_slug" in bootstrap.required_init_fields
    assert "publication_lane_kind" in bootstrap.required_init_fields
    assert "publication_lane_owner" in bootstrap.required_init_fields
    assert "managed_publication_root" in bootstrap.required_init_fields
    assert "selected_publication_root" in bootstrap.required_init_fields
    assert "selected_review_root" in bootstrap.required_init_fields

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
    assert "GPD/review/CLAIMS{round_suffix}.json" in panel_stages.writes_allowed
    assert "GPD/publication/{subject_slug}/review/CLAIMS{round_suffix}.json" in panel_stages.writes_allowed
    assert "GPD/publication/{subject_slug}/review/PROOF-REDTEAM{round_suffix}.md" in panel_stages.writes_allowed
    assert "references/publication/peer-review-panel.md" in final_adjudication.loaded_authorities
    assert "templates/paper/review-ledger-schema.md" in final_adjudication.loaded_authorities
    assert "templates/paper/referee-decision-schema.md" in final_adjudication.loaded_authorities
    assert "GPD/review/REVIEW-LEDGER{round_suffix}.json" in final_adjudication.writes_allowed
    assert "GPD/publication/{subject_slug}/review/REVIEW-LEDGER{round_suffix}.json" in final_adjudication.writes_allowed
    assert "GPD/publication/{subject_slug}/REFEREE-REPORT{round_suffix}.md" in final_adjudication.writes_allowed


def test_arxiv_submission_stage_manifest_surfaces_publication_routing() -> None:
    manifest = _load_manifest("arxiv-submission")
    bootstrap = manifest.stage("bootstrap")
    package = manifest.stage("package")

    assert "publication_subject_slug" in bootstrap.required_init_fields
    assert "publication_lane_kind" in bootstrap.required_init_fields
    assert "publication_lane_owner" in bootstrap.required_init_fields
    assert "managed_publication_root" in bootstrap.required_init_fields
    assert "selected_publication_root" in bootstrap.required_init_fields
    assert "selected_review_root" in bootstrap.required_init_fields
    assert package.writes_allowed == ("GPD/publication/{subject_slug}/arxiv",)


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
