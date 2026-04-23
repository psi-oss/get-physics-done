"""Assertions for write-paper handoff and artifact-gate semantics."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / "src" / "gpd" / "specs" / "workflows" / "write-paper.md"


def test_write_paper_writer_completion_requires_typed_status_files_written_and_disk_artifact() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")

    assert "Check the writer's typed `gpd_return.status` first." in source
    assert "If the writer returned `status: completed`, verify that `gpd_return.files_written` names the expected `.tex` file" in source
    assert "If the writer returned `status: checkpoint`, treat it as an incomplete handoff" in source
    assert "Treat the emitted `.tex` file as the success artifact gate for each section" in source


def test_write_paper_bibliography_completion_requires_typed_status_files_written_and_disk_artifacts() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")

    assert "Use `status: completed` when the bibliography task finished" in source
    assert "A completed return must list `references/references.bib` and `GPD/references-status.json` in `gpd_return.files_written`" in source
    assert "Treat `${PAPER_DIR}/CITATION-AUDIT.md`, the refreshed `${PAPER_DIR}/BIBLIOGRAPHY-AUDIT.json`, and the bibliographer's typed `gpd_return` envelope as the bibliography success gate" in source
    assert "does not name the bibliography outputs" in source


def test_write_paper_response_artifact_completion_requires_typed_status_files_written_and_disk_artifacts() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")

    assert "Check the agent's typed `gpd_return.status` first." in source
    assert "If it returned `status: completed`, verify that `gpd_return.files_written` names both `GPD/AUTHOR-RESPONSE{round_suffix}.md` and `GPD/review/REFEREE_RESPONSE{round_suffix}.md`" in source
    assert "If it returned `status: checkpoint`, treat that as a fresh continuation handoff rather than completion." in source
    assert "Treat `GPD/AUTHOR-RESPONSE{round_suffix}.md`, `GPD/review/REFEREE_RESPONSE{round_suffix}.md`, and the writer's typed `gpd_return` envelope as the response success gate." in source


def test_write_paper_bootstrap_contract_is_explicit_about_project_and_bounded_external_lanes() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")

    assert "Use `publication_subject*`, `manuscript_*`, and `publication_bootstrap*` from init / strict preflight" in source
    assert "The resolved manuscript root may already be the managed project lane `GPD/publication/{subject_slug}/manuscript`" in source
    assert "If `publication_bootstrap_mode` is `fresh_external_authoring_bootstrap`" in source
    assert "`GPD/publication/{subject_slug}/intake/` is intake/provenance state only; it must not participate in manuscript-root discovery" in source
    assert "a resolved `${PAPER_DIR}` under `GPD/publication/{subject_slug}/manuscript` may be either the managed project lane or the bounded external-authoring lane" in source
    assert "do not mine generic folders or widen into arbitrary external-manuscript discovery; the only non-project lane is explicit `--intake`" in source
    assert "do not invent an external-manuscript `write-paper` flow or relax the project-required contract" not in source


def test_write_paper_external_lane_stops_at_manuscript_root_handoff_and_routes_to_peer_review() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")

    assert "**External-authoring lane:** do **not** run the embedded staged panel here." in source
    assert "Embedded `write-paper` review parity for the bounded external-authoring lane is deferred" in source
    assert "`${PAPER_DIR}/PAPER-CONFIG.json`" in source
    assert "`${PAPER_DIR}/ARTIFACT-MANIFEST.json`" in source
    assert "`${PAPER_DIR}/BIBLIOGRAPHY-AUDIT.json`" in source
    assert "`${PAPER_DIR}/reproducibility-manifest.json`" in source
    assert "route the user to standalone `gpd:peer-review`" in source
    assert "do not recommend `gpd:arxiv-submission` directly from this lane" in source
