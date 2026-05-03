from __future__ import annotations

import json
from pathlib import Path

from gpd.adapters.install_utils import parse_at_include_path
from gpd.core.workflow_staging import (
    WRITE_PAPER_MANAGED_INTAKE_ROOT,
    WRITE_PAPER_MANAGED_MANUSCRIPT_ROOT,
    validate_workflow_stage_manifest_payload,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / "src" / "gpd" / "specs" / "workflows"
REFERENCES_DIR = REPO_ROOT / "src" / "gpd" / "specs" / "references" / "publication"
RAW_INCLUDE_ALLOWED_DEFERRED_AUTHORITIES = {
    "references/orchestration/runtime-delegation-note.md",
}


def _load_manifest(workflow_name: str) -> object:
    return validate_workflow_stage_manifest_payload(
        json.loads((WORKFLOWS_DIR / f"{workflow_name}-stage-manifest.json").read_text(encoding="utf-8")),
        expected_workflow_id=workflow_name,
    )


def _canonical_include_relpath(include_path: str) -> str:
    if include_path.startswith("{GPD_INSTALL_DIR}/"):
        return include_path[len("{GPD_INSTALL_DIR}/") :]
    if "get-physics-done/" in include_path:
        return include_path.split("get-physics-done/", 1)[1]
    return include_path


def _raw_projection_include_relpaths(source: str) -> tuple[tuple[int, str], ...]:
    includes: list[tuple[int, str]] = []
    active_fence_marker: str | None = None

    for line_number, line in enumerate(source.splitlines(), start=1):
        stripped = line.strip()
        fence_marker = None
        if stripped.startswith("```"):
            fence_marker = "```"
        elif stripped.startswith("~~~"):
            fence_marker = "~~~"
        if fence_marker is not None:
            if active_fence_marker is None:
                active_fence_marker = fence_marker
            elif active_fence_marker == fence_marker:
                active_fence_marker = None
            continue
        if active_fence_marker is not None:
            continue

        include_path = parse_at_include_path(stripped)
        if include_path is not None:
            includes.append((line_number, _canonical_include_relpath(include_path)))

    return tuple(includes)


def test_stage_one_deferred_authorities_are_not_raw_projection_includes() -> None:
    offenders: list[str] = []

    for manifest_path in sorted(WORKFLOWS_DIR.glob("*-stage-manifest.json")):
        workflow_name = manifest_path.name.removesuffix("-stage-manifest.json")
        workflow_path = WORKFLOWS_DIR / f"{workflow_name}.md"
        if not workflow_path.is_file():
            continue

        manifest = _load_manifest(workflow_name)
        stage_ids = manifest.stage_ids()
        if not stage_ids:
            continue
        first_stage = manifest.stage(stage_ids[0])
        deferred_authorities = set(first_stage.must_not_eager_load)
        if not deferred_authorities:
            continue

        for line_number, include_relpath in _raw_projection_include_relpaths(workflow_path.read_text(encoding="utf-8")):
            if include_relpath in deferred_authorities:
                if include_relpath in RAW_INCLUDE_ALLOWED_DEFERRED_AUTHORITIES:
                    continue
                offenders.append(f"{workflow_path.name}:{line_number}:{include_relpath}")

    assert offenders == []


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
    for stage in (bootstrap, outline, authoring, consistency, publication_review):
        assert "write_paper_argument_input" in stage.required_init_fields
    assert outline.writes_allowed[0] == WRITE_PAPER_MANAGED_MANUSCRIPT_ROOT
    assert WRITE_PAPER_MANAGED_INTAKE_ROOT in outline.writes_allowed
    assert authoring.writes_allowed[0] == WRITE_PAPER_MANAGED_MANUSCRIPT_ROOT
    assert consistency.writes_allowed[0] == WRITE_PAPER_MANAGED_MANUSCRIPT_ROOT
    assert publication_review.writes_allowed[0] == WRITE_PAPER_MANAGED_MANUSCRIPT_ROOT
    assert "selected_review_root" in publication_review.required_init_fields
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
    for field in (
        "manuscript_root",
        "manuscript_entrypoint",
        "artifact_manifest_path",
        "bibliography_audit_path",
        "reproducibility_manifest_path",
    ):
        assert field in panel_stages.required_init_fields
        assert field in final_adjudication.required_init_fields
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

    assert manifest.prompt_usage == "staged_init"
    assert "arxiv_submission_argument_input" in bootstrap.required_init_fields
    assert "publication_subject_slug" in bootstrap.required_init_fields
    assert "publication_lane_kind" in bootstrap.required_init_fields
    assert "publication_lane_owner" in bootstrap.required_init_fields
    assert "managed_publication_root" in bootstrap.required_init_fields
    assert "selected_publication_root" in bootstrap.required_init_fields
    assert "selected_review_root" in bootstrap.required_init_fields
    assert "latest_response_round" in bootstrap.required_init_fields
    assert "latest_response_artifacts" in bootstrap.required_init_fields
    assert "latest_response_requires_fresh_review" in bootstrap.required_init_fields
    assert "latest_response_freshness" in bootstrap.required_init_fields
    assert package.writes_allowed == ("GPD/publication/{subject_slug}/arxiv",)
    for stage_id in manifest.stage_ids():
        assert "arxiv_submission_argument_input" in manifest.stage(stage_id).required_init_fields


def test_respond_to_referees_stage_manifest_uses_publication_response_contracts() -> None:
    manifest = _load_manifest("respond-to-referees")

    assert manifest.stage_ids() == (
        "bootstrap",
        "report_triage",
        "revision_planning",
        "response_authoring",
        "finalize",
    )

    bootstrap = manifest.stage("bootstrap")
    report_triage = manifest.stage("report_triage")
    revision_planning = manifest.stage("revision_planning")
    response_authoring = manifest.stage("response_authoring")
    finalize = manifest.stage("finalize")

    assert "references/publication/publication-bootstrap-preflight.md" in bootstrap.loaded_authorities
    assert "references/publication/publication-response-writer-handoff.md" in bootstrap.must_not_eager_load
    assert "project_root" in bootstrap.required_init_fields
    assert "response_intake_input" in bootstrap.required_init_fields
    assert "publication_subject_slug" in bootstrap.required_init_fields
    assert "publication_lane_kind" in bootstrap.required_init_fields
    assert "selected_publication_root" in bootstrap.required_init_fields
    assert "selected_review_root" in bootstrap.required_init_fields
    assert "latest_response_artifacts" in bootstrap.required_init_fields

    assert report_triage.loaded_authorities == (
        "workflows/respond-to-referees.md",
        "references/publication/peer-review-reliability.md",
        "references/publication/publication-response-writer-handoff.md",
    )
    assert "reference_artifacts_content" in revision_planning.required_init_fields
    for stage_id in manifest.stage_ids()[1:]:
        assert "response_intake_input" in manifest.stage(stage_id).required_init_fields
    assert "templates/paper/referee-response.md" in response_authoring.loaded_authorities
    assert "templates/paper/author-response.md" in response_authoring.loaded_authorities
    assert "GPD/AUTHOR-RESPONSE{round_suffix}.md" in response_authoring.writes_allowed
    assert "GPD/review/REFEREE_RESPONSE{round_suffix}.md" in response_authoring.writes_allowed
    assert "GPD/publication/{subject_slug}/AUTHOR-RESPONSE{round_suffix}.md" in response_authoring.writes_allowed
    assert "GPD/publication/{subject_slug}/review/REFEREE_RESPONSE{round_suffix}.md" in finalize.writes_allowed


def test_respond_to_referees_workflow_uses_staged_init_without_inline_field_list() -> None:
    workflow = (WORKFLOWS_DIR / "respond-to-referees.md").read_text(encoding="utf-8")

    assert "gpd --raw init respond-to-referees --stage bootstrap" in workflow
    assert "gpd --raw init phase-op --include config" not in workflow
    assert "respond-to-referees-stage-manifest.json" in workflow
    assert "INIT.staged_loading.required_init_fields" in workflow
    assert "Parse JSON for: `commit_docs`, `state_exists`, `project_exists`" not in workflow


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
