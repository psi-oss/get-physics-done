"""Assertions for arxiv submission prompt/workflow alignment."""

from __future__ import annotations

import json
import tarfile
from pathlib import Path

from gpd.core.arxiv_package import ARXIV_TARBALL_NAME, validate_arxiv_package
from gpd.core.workflow_staging import resolve_workflow_stage_manifest_path, validate_workflow_stage_manifest_payload

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_DIR = REPO_ROOT / "src/gpd/commands"
WORKFLOWS_DIR = REPO_ROOT / "src/gpd/specs/workflows"


def _check_by_name(result: object, name: str) -> object:
    return next(check for check in result.checks if check.name == name)


def test_arxiv_submission_command_declares_manuscript_root_gates_without_first_match_discovery() -> None:
    command = (COMMANDS_DIR / "arxiv-submission.md").read_text(encoding="utf-8")

    assert "context_mode: project-aware" in command
    assert "command-policy:" in command
    assert "allow_external_subjects: false" in command
    assert "allow_interactive_without_subject: false" in command
    assert "bootstrap_allowed: false" in command
    assert "default_output_subtree: GPD/publication/{subject_slug}/arxiv" in command
    assert "GPD/publication/*/manuscript/*.tex" in command
    assert "manuscript-root artifact manifest" in command
    assert "manuscript-root bibliography audit" in command
    assert "Follow the included arxiv-submission workflow exactly." in command
    assert "artifact_manifest" in command
    assert "bibliography_audit" in command
    assert "bibliography_audit_clean" in command
    assert (
        "Paper target: $ARGUMENTS (optional manuscript root or `.tex` entrypoint; "
        "when omitted, the workflow resolves the active GPD-owned manuscript root)."
    ) in command
    assert (
        "Explicit manuscript subjects must stay under `paper/`, `manuscript/`, `draft/`, or `GPD/publication/{subject_slug}/manuscript/`."
        in command
    )
    assert "do not switch to standalone interactive intake or arbitrary external directories" in command
    assert "scope_variants:" not in command
    assert "@{GPD_INSTALL_DIR}/templates/paper/publication-manuscript-root-preflight.md" not in command
    assert "@{GPD_INSTALL_DIR}/references/publication/publication-review-round-artifacts.md" not in command
    assert "@{GPD_INSTALL_DIR}/references/publication/publication-response-artifacts.md" not in command
    assert "@{GPD_INSTALL_DIR}/references/publication/publication-bootstrap-preflight.md" not in command


def test_arxiv_submission_workflow_resolves_manifest_based_manuscript_root_without_globbing() -> None:
    workflow = (WORKFLOWS_DIR / "arxiv-submission.md").read_text(encoding="utf-8")

    assert "gpd --raw init arxiv-submission --stage bootstrap" in workflow
    assert 'gpd --raw init arxiv-submission --stage bootstrap -- "$ARGUMENTS"' in workflow
    assert 'gpd --raw init arxiv-submission --stage manuscript_preflight -- "$ARGUMENTS"' in workflow
    assert 'gpd --raw init arxiv-submission --stage review_gate -- "$ARGUMENTS"' in workflow
    assert 'gpd --raw init arxiv-submission --stage package -- "$ARGUMENTS"' in workflow
    assert 'gpd --raw init arxiv-submission --stage finalize -- "$ARGUMENTS"' in workflow
    assert "metadata-only" not in workflow
    assert "Use the shared publication bootstrap reference as the source of truth" in workflow
    assert "@{GPD_INSTALL_DIR}/references/publication/publication-bootstrap-preflight.md" in workflow
    assert "{GPD_INSTALL_DIR}/references/publication/publication-review-round-artifacts.md" in workflow
    assert "{GPD_INSTALL_DIR}/references/publication/peer-review-reliability.md" not in workflow
    assert "staged `peer-review-reliability.md` reference" in workflow
    assert "@{GPD_INSTALL_DIR}/references/publication/publication-response-artifacts.md" not in workflow
    assert "@{GPD_INSTALL_DIR}/references/publication/publication-response-writer-handoff.md" not in workflow
    assert "ARTIFACT-MANIFEST.json" in workflow
    assert "BIBLIOGRAPHY-AUDIT.json" in workflow
    assert "bibliography_audit_clean" in workflow
    assert "gpd paper-build" in workflow
    assert "STOP and require an explicit manuscript path or a repaired manuscript-root state" in workflow
    assert "Do not fall back to `find` or arbitrary wildcard matching outside the documented default roots." in workflow
    assert (
        "it must match that resolved entrypoint and already live under `paper/`, `manuscript/`, `draft/`, or `GPD/publication/<subject_slug>/manuscript/`."
        in workflow
    )
    assert (
        "Do not accept arbitrary external directories or standalone `.tex` entrypoints outside those supported roots."
        in workflow
    )
    assert 'PACKAGE_ROOT="${PUBLICATION_ROOT}/arxiv"' in workflow
    assert 'PACKAGE_TARBALL="${PACKAGE_ROOT}/arxiv-submission.tar.gz"' in workflow
    assert (
        'gpd --raw validate arxiv-package --materialize --submission-dir "$SUBMISSION_DIR" --tarball "$PACKAGE_TARBALL"'
        in workflow
    )
    assert "reruns strict `arxiv-submission` review preflight internally" in workflow
    assert "the executable arXiv package validator must pass" in workflow
    assert "latest-response discovery" in workflow
    assert "latest response artifacts already reached" not in workflow
    assert (
        "Do not write proof-review manifests, package staging trees, or tarballs beside the manuscript root itself."
        in workflow
    )
    assert "Even for an explicit external manuscript subject" not in workflow
    assert 'ls "${DIR}"/*.tex' not in workflow


def test_arxiv_submission_stage_manifest_path_is_resolved_and_loadable() -> None:
    manifest_path = resolve_workflow_stage_manifest_path("arxiv-submission")

    assert manifest_path == WORKFLOWS_DIR / "arxiv-submission-stage-manifest.json"
    assert manifest_path.exists()

    manifest = validate_workflow_stage_manifest_payload(
        json.loads(manifest_path.read_text(encoding="utf-8")),
        expected_workflow_id="arxiv-submission",
    )

    assert manifest.prompt_usage == "staged_init"
    assert manifest.stage_ids() == (
        "bootstrap",
        "manuscript_preflight",
        "review_gate",
        "package",
        "finalize",
    )
    for stage_id in manifest.stage_ids():
        assert "arxiv_submission_argument_input" in manifest.stage(stage_id).required_init_fields
    assert "references/publication/publication-bootstrap-preflight.md" in manifest.stage("bootstrap").loaded_authorities
    assert "managed publication output root state" in manifest.stage("bootstrap").produced_state
    assert (
        "references/publication/publication-review-round-artifacts.md"
        in manifest.stage("review_gate").loaded_authorities
    )
    assert "references/publication/peer-review-reliability.md" in manifest.stage("review_gate").loaded_authorities
    assert (
        "references/publication/publication-response-writer-handoff.md"
        not in manifest.stage("review_gate").loaded_authorities
    )
    assert manifest.stage("package").writes_allowed == ("GPD/publication/{subject_slug}/arxiv",)
    assert manifest.stage("finalize").writes_allowed == ("GPD/publication/{subject_slug}/arxiv",)


def test_arxiv_package_validator_detects_citations_in_included_tex_files(tmp_path: Path) -> None:
    submission_dir = tmp_path / "GPD" / "publication" / "paper" / "arxiv" / "submission"
    submission_dir.mkdir(parents=True)
    (submission_dir / "main.tex").write_text(
        "\\documentclass{article}\\begin{document}\\input{section}\\end{document}\n",
        encoding="utf-8",
    )
    (submission_dir / "section.tex").write_text(
        "The result follows prior work \\cite{known-result}.\n", encoding="utf-8"
    )

    result = validate_arxiv_package(
        project_root=tmp_path,
        subject_slug="paper",
        manuscript_entrypoint="paper/main.tex",
    )

    tex_check = _check_by_name(result, "submission_tex_ready")
    assert tex_check.passed is False
    assert "citation commands but no inlined thebibliography or packaged .bbl material" in tex_check.detail


def test_arxiv_package_validator_accepts_included_tex_bibliography_material(tmp_path: Path) -> None:
    submission_dir = tmp_path / "GPD" / "publication" / "paper" / "arxiv" / "submission"
    submission_dir.mkdir(parents=True)
    (submission_dir / "main.tex").write_text(
        "\\documentclass{article}\\begin{document}\\input{section}\\end{document}\n",
        encoding="utf-8",
    )
    (submission_dir / "section.tex").write_text(
        (
            "The result follows prior work \\cite{known-result}.\n"
            "\\begin{thebibliography}{1}\n"
            "\\bibitem{known-result} Known Result.\n"
            "\\end{thebibliography}\n"
        ),
        encoding="utf-8",
    )

    result = validate_arxiv_package(
        project_root=tmp_path,
        subject_slug="paper",
        manuscript_entrypoint="paper/main.tex",
    )

    assert _check_by_name(result, "submission_tex_ready").passed is True


def test_arxiv_package_materialize_refuses_submission_tree_outside_managed_root(tmp_path: Path) -> None:
    outside_submission_dir = tmp_path / "outside-submission"
    outside_submission_dir.mkdir()
    (outside_submission_dir / "main.tex").write_text(
        "\\documentclass{article}\\begin{document}Ready.\\end{document}\n",
        encoding="utf-8",
    )
    tarball = tmp_path / "GPD" / "publication" / "paper" / "arxiv" / ARXIV_TARBALL_NAME

    result = validate_arxiv_package(
        project_root=tmp_path,
        subject_slug="paper",
        manuscript_entrypoint="paper/main.tex",
        submission_dir=outside_submission_dir,
        tarball=tarball,
        materialize=True,
    )

    assert result.materialized is False
    assert not tarball.exists()
    assert _check_by_name(result, "submission_dir_under_managed_arxiv_root").passed is False
    assert _check_by_name(result, "tarball_materialized").passed is False


def test_arxiv_package_validator_rejects_unsafe_publication_subject_slug(tmp_path: Path) -> None:
    submission_dir = tmp_path / "GPD" / "escape" / "arxiv" / "submission"
    submission_dir.mkdir(parents=True)
    (submission_dir / "main.tex").write_text(
        "\\documentclass{article}\\begin{document}Ready.\\end{document}\n",
        encoding="utf-8",
    )
    tarball = tmp_path / "GPD" / "escape" / "arxiv" / ARXIV_TARBALL_NAME
    with tarfile.open(tarball, "w:gz") as archive:
        archive.add(submission_dir / "main.tex", arcname="main.tex", recursive=False)

    result = validate_arxiv_package(
        project_root=tmp_path,
        subject_slug="../escape",
        manuscript_entrypoint="paper/main.tex",
        submission_dir=submission_dir,
        tarball=tarball,
    )

    check = _check_by_name(result, "managed_arxiv_root")
    assert check.passed is False
    assert "publication subject slug" in check.detail
