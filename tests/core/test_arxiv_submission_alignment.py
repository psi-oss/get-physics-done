"""Regression checks for arxiv submission prompt/workflow alignment."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gpd.core.workflow_staging import resolve_workflow_stage_manifest_path, validate_workflow_stage_manifest_payload

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_DIR = REPO_ROOT / "src/gpd/commands"
WORKFLOWS_DIR = REPO_ROOT / "src/gpd/specs/workflows"


def test_arxiv_submission_command_declares_manuscript_root_gates_without_first_match_discovery() -> None:
    command = (COMMANDS_DIR / "arxiv-submission.md").read_text(encoding="utf-8")

    assert "context_mode: project-aware" in command
    assert "command-policy:" in command
    assert "allow_external_subjects: true" in command
    assert "allow_interactive_without_subject: false" in command
    assert "bootstrap_allowed: false" in command
    assert "default_output_subtree: GPD/publication/{subject_slug}/arxiv" in command
    assert "manuscript-root artifact manifest" in command
    assert "manuscript-root bibliography audit" in command
    assert "Follow `@{GPD_INSTALL_DIR}/workflows/arxiv-submission.md` exactly." in command
    assert "artifact_manifest" in command
    assert "bibliography_audit" in command
    assert "bibliography_audit_clean" in command
    assert "Paper target: $ARGUMENTS (optional; when omitted, the workflow resolves the manuscript root)." in command
    assert "Explicit external subjects are allowed only for `.tex` entrypoints" in command
    assert "do not switch to standalone interactive intake" in command
    assert "@{GPD_INSTALL_DIR}/templates/paper/publication-manuscript-root-preflight.md" not in command
    assert "@{GPD_INSTALL_DIR}/references/publication/publication-review-round-artifacts.md" not in command
    assert "@{GPD_INSTALL_DIR}/references/publication/publication-response-artifacts.md" not in command
    assert "@{GPD_INSTALL_DIR}/references/publication/publication-bootstrap-preflight.md" not in command


def test_arxiv_submission_workflow_resolves_manifest_based_manuscript_root_without_globbing() -> None:
    workflow = (WORKFLOWS_DIR / "arxiv-submission.md").read_text(encoding="utf-8")

    assert "Use the shared publication bootstrap reference as the source of truth" in workflow
    assert "@{GPD_INSTALL_DIR}/references/publication/publication-bootstrap-preflight.md" in workflow
    assert "@{GPD_INSTALL_DIR}/references/publication/publication-review-round-artifacts.md" in workflow
    assert "@{GPD_INSTALL_DIR}/references/publication/peer-review-reliability.md" in workflow
    assert "@{GPD_INSTALL_DIR}/references/publication/publication-response-artifacts.md" not in workflow
    assert "@{GPD_INSTALL_DIR}/references/publication/publication-response-writer-handoff.md" not in workflow
    assert "ARTIFACT-MANIFEST.json" in workflow
    assert "BIBLIOGRAPHY-AUDIT.json" in workflow
    assert "bibliography_audit_clean" in workflow
    assert "gpd paper-build" in workflow
    assert "STOP and require an explicit manuscript path or a repaired manuscript-root state" in workflow
    assert "Do not fall back to `find` or arbitrary wildcard matching outside the documented default roots." in workflow
    assert "If that file lives outside `paper/`, `manuscript/`, or `draft/`, treat it as an explicit external publication subject." in workflow
    assert "Do not prompt for standalone intake when no explicit target is supplied." in workflow
    assert 'PACKAGE_ROOT="GPD/publication/${subject_slug}/arxiv"' in workflow
    assert 'PACKAGE_TARBALL="${PACKAGE_ROOT}/arxiv-submission.tar.gz"' in workflow
    assert "Do not write proof-review manifests, package staging trees, or tarballs beside an explicit external manuscript subject." in workflow
    assert 'ls "${DIR}"/*.tex' not in workflow


def test_arxiv_submission_stage_manifest_path_is_resolved_and_loadable_when_present() -> None:
    manifest_path = resolve_workflow_stage_manifest_path("arxiv-submission")

    assert manifest_path == WORKFLOWS_DIR / "arxiv-submission-stage-manifest.json"

    if not manifest_path.exists():
        pytest.skip("arxiv-submission stage manifest has not landed yet")

    manifest = validate_workflow_stage_manifest_payload(
        json.loads(manifest_path.read_text(encoding="utf-8")),
        expected_workflow_id="arxiv-submission",
    )

    assert manifest.stage_ids() == (
        "bootstrap",
        "manuscript_preflight",
        "review_gate",
        "package",
        "finalize",
    )
    assert "references/publication/publication-bootstrap-preflight.md" in manifest.stage("bootstrap").loaded_authorities
    assert "managed publication output root state" in manifest.stage("bootstrap").produced_state
    assert "references/publication/publication-review-round-artifacts.md" in manifest.stage("review_gate").loaded_authorities
    assert "references/publication/peer-review-reliability.md" in manifest.stage("review_gate").loaded_authorities
    assert "references/publication/publication-response-writer-handoff.md" not in manifest.stage("review_gate").loaded_authorities
    assert manifest.stage("package").writes_allowed == ("GPD/publication/{subject_slug}/arxiv",)
    assert manifest.stage("finalize").writes_allowed == ("GPD/publication/{subject_slug}/arxiv",)
