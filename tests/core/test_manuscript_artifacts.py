from __future__ import annotations

import hashlib
import json
from pathlib import Path

from gpd.core.manuscript_artifacts import (
    ManuscriptArtifacts,
    ManuscriptResolution,
    ManuscriptRootResolution,
    PublicationSubjectResolution,
    locate_publication_artifact,
    publication_root_for_subject,
    resolve_current_manuscript_artifacts,
    resolve_current_manuscript_entrypoint,
    resolve_current_manuscript_resolution,
    resolve_current_manuscript_root,
    resolve_current_publication_subject,
    resolve_explicit_publication_subject,
    resolve_manuscript_entrypoint_from_root,
    resolve_publication_bootstrap_resolution,
    resolve_publication_subject_artifact,
    review_dir_for_subject,
)


def _write(path: Path, content: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _sha256_text(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _artifact_manifest_json(
    manuscript_path: Path,
    *,
    artifact_path: str | None = None,
    artifact_id: str = "tex-paper",
    title: str = "Curvature Flow Bounds",
    journal: str = "jhep",
) -> str:
    digest = hashlib.sha256(manuscript_path.read_bytes()).hexdigest()
    return (
        json.dumps(
            {
                "version": 1,
                "paper_title": title,
                "journal": journal,
                "created_at": "2026-04-02T00:00:00+00:00",
                "manuscript_sha256": digest,
                "manuscript_mtime_ns": manuscript_path.stat().st_mtime_ns,
                "artifacts": [
                    {
                        "artifact_id": artifact_id,
                        "category": "tex",
                        "path": artifact_path or manuscript_path.name,
                        "sha256": digest,
                        "produced_by": "test",
                        "sources": [],
                        "metadata": {},
                    }
                ],
            }
        )
        + "\n"
    )


def test_resolve_current_manuscript_artifacts_prefers_manifest_declared_entrypoint(tmp_path: Path) -> None:
    manuscript_content = "\\documentclass{article}\\begin{document}Hi\\end{document}\n"
    _write(tmp_path / "paper" / "curvature_flow_bounds.tex", manuscript_content)
    _write(
        tmp_path / "paper" / "ARTIFACT-MANIFEST.json",
        json.dumps(
            {
                "version": 1,
                "paper_title": "Curvature Flow Bounds",
                "journal": "prl",
                "created_at": "2026-04-02T00:00:00+00:00",
                "manuscript_sha256": _sha256_text(manuscript_content),
                "manuscript_mtime_ns": (tmp_path / "paper" / "curvature_flow_bounds.tex").stat().st_mtime_ns,
                "artifacts": [
                    {
                        "artifact_id": "tex-paper",
                        "category": "tex",
                        "path": "curvature_flow_bounds.tex",
                        "sha256": "0" * 64,
                        "produced_by": "test",
                        "sources": [],
                        "metadata": {},
                    }
                ],
            }
        )
        + "\n",
    )
    _write(tmp_path / "paper" / "BIBLIOGRAPHY-AUDIT.json", "{}\n")
    _write(tmp_path / "paper" / "reproducibility-manifest.json", "{}\n")

    artifacts = resolve_current_manuscript_artifacts(tmp_path)

    assert isinstance(artifacts, ManuscriptArtifacts)
    assert artifacts.manuscript_entrypoint == tmp_path / "paper" / "curvature_flow_bounds.tex"
    assert artifacts.manuscript_root == tmp_path / "paper"
    assert artifacts.artifact_manifest == tmp_path / "paper" / "ARTIFACT-MANIFEST.json"
    assert artifacts.bibliography_audit == tmp_path / "paper" / "BIBLIOGRAPHY-AUDIT.json"
    assert artifacts.reproducibility_manifest == tmp_path / "paper" / "reproducibility-manifest.json"
    assert resolve_current_manuscript_entrypoint(tmp_path) == tmp_path / "paper" / "curvature_flow_bounds.tex"
    assert resolve_current_manuscript_root(tmp_path) == tmp_path / "paper"


def test_resolve_current_manuscript_resolution_rejects_checksum_stale_manifest_entrypoint(
    tmp_path: Path,
) -> None:
    manuscript = tmp_path / "paper" / "curvature_flow_bounds.tex"
    _write(manuscript, "\\documentclass{article}\\begin{document}Edited after build.\\end{document}\n")
    _write(
        tmp_path / "paper" / "ARTIFACT-MANIFEST.json",
        json.dumps(
            {
                "version": 1,
                "paper_title": "Curvature Flow Bounds",
                "journal": "prl",
                "created_at": "2026-04-02T00:00:00+00:00",
                "manuscript_sha256": hashlib.sha256(b"previous build").hexdigest(),
                "manuscript_mtime_ns": manuscript.stat().st_mtime_ns,
                "artifacts": [
                    {
                        "artifact_id": "tex-paper",
                        "category": "tex",
                        "path": "curvature_flow_bounds.tex",
                        "sha256": hashlib.sha256(b"previous build").hexdigest(),
                        "produced_by": "test",
                        "sources": [],
                        "metadata": {},
                    }
                ],
            }
        )
        + "\n",
    )

    resolution = resolve_current_manuscript_resolution(tmp_path)

    assert resolution.status == "invalid"
    assert resolution.manuscript_entrypoint is None
    assert "ARTIFACT-MANIFEST.json is stale" in resolution.detail
    assert "manuscript_sha256 does not match the active manuscript snapshot" in resolution.detail
    assert resolve_current_manuscript_entrypoint(tmp_path) is None


def test_resolve_current_manuscript_artifacts_supports_config_derived_markdown_and_canonical_reproducibility(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / "manuscript" / "PAPER-CONFIG.json",
        json.dumps(
            {
                "title": "Asymptotic Matching Note",
                "authors": [{"name": "A. Researcher"}],
                "abstract": "Abstract.",
                "sections": [{"heading": "Intro", "content": "Hello."}],
            }
        )
        + "\n",
    )
    _write(tmp_path / "manuscript" / "asymptotic_matching_note.md", "# Manuscript\n")
    _write(tmp_path / "manuscript" / "ARTIFACT-MANIFEST.json", "{}\n")
    _write(tmp_path / "manuscript" / "BIBLIOGRAPHY-AUDIT.json", "{}\n")
    _write(tmp_path / "manuscript" / "reproducibility-manifest.json", "{}\n")

    artifacts = resolve_current_manuscript_artifacts(tmp_path)

    assert artifacts.manuscript_entrypoint == tmp_path / "manuscript" / "asymptotic_matching_note.md"
    assert artifacts.manuscript_root == tmp_path / "manuscript"
    assert artifacts.reproducibility_manifest == tmp_path / "manuscript" / "reproducibility-manifest.json"


def test_resolve_current_manuscript_artifacts_keep_supported_root_for_nested_manifest_entrypoint(
    tmp_path: Path,
) -> None:
    manuscript = tmp_path / "paper" / "sections" / "curvature_flow_bounds.tex"
    _write(
        manuscript,
        "\\documentclass{article}\\begin{document}Hi\\end{document}\n",
    )
    _write(
        tmp_path / "paper" / "ARTIFACT-MANIFEST.json",
        _artifact_manifest_json(manuscript, artifact_path="sections/curvature_flow_bounds.tex", journal="prl"),
    )
    _write(tmp_path / "paper" / "BIBLIOGRAPHY-AUDIT.json", "{}\n")
    _write(tmp_path / "paper" / "reproducibility-manifest.json", "{}\n")

    artifacts = resolve_current_manuscript_artifacts(tmp_path)

    assert artifacts.manuscript_entrypoint == tmp_path / "paper" / "sections" / "curvature_flow_bounds.tex"
    assert artifacts.manuscript_root == tmp_path / "paper"
    assert artifacts.artifact_manifest == tmp_path / "paper" / "ARTIFACT-MANIFEST.json"
    assert artifacts.bibliography_audit == tmp_path / "paper" / "BIBLIOGRAPHY-AUDIT.json"
    assert artifacts.reproducibility_manifest == tmp_path / "paper" / "reproducibility-manifest.json"
    assert resolve_current_manuscript_root(tmp_path) == tmp_path / "paper"
    assert (
        locate_publication_artifact(
            tmp_path / "paper" / "sections" / "curvature_flow_bounds.tex",
            "ARTIFACT-MANIFEST.json",
        )
        == tmp_path / "paper" / "ARTIFACT-MANIFEST.json"
    )


def test_resolve_current_publication_subject_surfaces_artifact_base_and_path_semantics(tmp_path: Path) -> None:
    manuscript = tmp_path / "paper" / "sections" / "curvature_flow_bounds.tex"
    _write(
        manuscript,
        "\\documentclass{article}\\begin{document}Hi\\end{document}\n",
    )
    _write(
        tmp_path / "paper" / "ARTIFACT-MANIFEST.json",
        _artifact_manifest_json(manuscript, artifact_path="sections/curvature_flow_bounds.tex", journal="prl"),
    )
    _write(tmp_path / "paper" / "BIBLIOGRAPHY-AUDIT.json", "{}\n")
    _write(tmp_path / "paper" / "reproducibility-manifest.json", "{}\n")

    subject = resolve_current_publication_subject(tmp_path)

    assert isinstance(subject, PublicationSubjectResolution)
    assert subject.status == "resolved"
    assert subject.source == "current_project"
    assert subject.manuscript_root == tmp_path / "paper"
    assert subject.manuscript_entrypoint == tmp_path / "paper" / "sections" / "curvature_flow_bounds.tex"
    assert subject.artifact_base == tmp_path / "paper"
    assert subject.artifact_manifest == tmp_path / "paper" / "ARTIFACT-MANIFEST.json"
    assert subject.path_semantics is not None
    assert subject.publication_lane_kind == "canonical_project_manuscript"
    assert subject.publication_lane_owner == "project_managed"
    assert subject.publication_subject_slug is not None
    assert subject.publication_root == tmp_path / "GPD"
    assert subject.review_dir == tmp_path / "GPD" / "review"
    assert subject.managed_publication_root == tmp_path / "GPD" / "publication" / subject.publication_subject_slug
    assert subject.managed_intake_root == subject.managed_publication_root / "intake"
    assert subject.managed_manuscript_root == subject.managed_publication_root / "manuscript"
    assert publication_root_for_subject(subject) == subject.publication_root
    assert review_dir_for_subject(subject) == subject.review_dir
    assert subject.path_semantics.artifact_base_path == "paper"
    assert subject.path_semantics.manuscript_entrypoint_path == "paper/sections/curvature_flow_bounds.tex"
    assert subject.path_semantics.subject_relative_entrypoint_path == "sections/curvature_flow_bounds.tex"
    subject_context = subject.to_context_dict()
    assert subject_context["publication_root"] == "GPD"
    assert subject_context["review_dir"] == "GPD/review"
    bootstrap_context = subject.to_bootstrap_context_dict()
    assert bootstrap_context["publication_subject_status"] == "resolved"
    assert bootstrap_context["publication_subject_source"] == "current_project"
    assert bootstrap_context["publication_subject_slug"] == subject.publication_subject_slug
    assert bootstrap_context["publication_lane_kind"] == "canonical_project_manuscript"
    assert bootstrap_context["publication_lane_owner"] == "project_managed"
    assert bootstrap_context["publication_artifact_base"] == "paper"
    assert bootstrap_context["publication_root"] == "GPD"
    assert bootstrap_context["review_dir"] == "GPD/review"
    assert bootstrap_context["manuscript_entrypoint"] == "paper/sections/curvature_flow_bounds.tex"
    assert bootstrap_context["managed_publication_root"] == f"GPD/publication/{subject.publication_subject_slug}"
    assert bootstrap_context["managed_intake_root"] == f"GPD/publication/{subject.publication_subject_slug}/intake"
    assert bootstrap_context["managed_manuscript_root"] == (
        f"GPD/publication/{subject.publication_subject_slug}/manuscript"
    )
    assert resolve_publication_subject_artifact(subject, "BIBLIOGRAPHY-AUDIT.json") == (
        tmp_path / "paper" / "BIBLIOGRAPHY-AUDIT.json"
    )


def test_resolve_current_publication_subject_supports_managed_project_manuscript_lane(tmp_path: Path) -> None:
    manuscript_root = tmp_path / "GPD" / "publication" / "curvature-flow-bounds" / "manuscript"
    manuscript = manuscript_root / "main.tex"
    _write(
        manuscript,
        "\\documentclass{article}\\begin{document}Hi\\end{document}\n",
    )
    _write(
        manuscript_root / "ARTIFACT-MANIFEST.json",
        _artifact_manifest_json(manuscript, journal="prl"),
    )
    _write(manuscript_root / "BIBLIOGRAPHY-AUDIT.json", "{}\n")
    _write(manuscript_root / "reproducibility-manifest.json", "{}\n")

    subject = resolve_current_publication_subject(tmp_path)

    assert subject.status == "resolved"
    assert subject.source == "current_project"
    assert subject.manuscript_root == manuscript_root
    assert subject.manuscript_entrypoint == manuscript_root / "main.tex"
    assert subject.artifact_base == manuscript_root
    assert subject.publication_subject_slug == "curvature-flow-bounds"
    assert subject.publication_lane_kind == "managed_publication_manuscript"
    assert subject.publication_lane_owner == "project_managed"
    assert subject.managed_publication_root == tmp_path / "GPD" / "publication" / "curvature-flow-bounds"
    assert subject.publication_root == subject.managed_publication_root
    assert subject.review_dir == subject.managed_publication_root / "review"
    assert subject.managed_intake_root == subject.managed_publication_root / "intake"
    assert subject.managed_manuscript_root == manuscript_root
    assert resolve_current_manuscript_root(tmp_path) == manuscript_root
    assert resolve_current_manuscript_entrypoint(tmp_path) == manuscript_root / "main.tex"


def test_resolve_current_publication_subject_fails_closed_when_canonical_and_managed_lanes_both_resolve(
    tmp_path: Path,
) -> None:
    paper_manuscript = tmp_path / "paper" / "main.tex"
    _write(
        paper_manuscript,
        "\\documentclass{article}\\begin{document}Paper\\end{document}\n",
    )
    _write(
        tmp_path / "paper" / "ARTIFACT-MANIFEST.json",
        _artifact_manifest_json(paper_manuscript, artifact_id="paper-main", journal="prl"),
    )
    manuscript_root = tmp_path / "GPD" / "publication" / "curvature-flow-bounds" / "manuscript"
    managed_manuscript = manuscript_root / "main.tex"
    _write(
        managed_manuscript,
        "\\documentclass{article}\\begin{document}Managed\\end{document}\n",
    )
    _write(
        manuscript_root / "ARTIFACT-MANIFEST.json",
        _artifact_manifest_json(managed_manuscript, artifact_id="managed-main", journal="prl"),
    )

    subject = resolve_current_publication_subject(tmp_path)

    assert subject.status == "ambiguous"
    assert subject.manuscript_root is None
    assert subject.manuscript_entrypoint is None
    assert "multiple manuscript roots resolve" in subject.detail
    assert resolve_current_manuscript_entrypoint(tmp_path) is None


def test_resolve_publication_bootstrap_resolution_defaults_to_fresh_project_bootstrap(tmp_path: Path) -> None:
    bootstrap = resolve_publication_bootstrap_resolution(tmp_path)

    assert bootstrap.mode == "fresh_project_bootstrap"
    assert bootstrap.bootstrap_root == tmp_path / "paper"
    assert "current write-paper bootstrap remains at" in bootstrap.detail
    assert bootstrap.to_context_dict()["bootstrap_root"] == "paper"


def test_resolve_publication_bootstrap_resolution_prefers_unique_managed_lane_candidate(tmp_path: Path) -> None:
    manuscript_root = tmp_path / "GPD" / "publication" / "curvature-flow-bounds" / "manuscript"
    _write(
        manuscript_root / "PAPER-CONFIG.json",
        json.dumps(
            {
                "title": "Curvature Flow Bounds",
                "authors": [{"name": "A. Researcher"}],
                "abstract": "Abstract.",
                "sections": [{"heading": "Intro", "content": "Hello."}],
            }
        )
        + "\n",
    )

    bootstrap = resolve_publication_bootstrap_resolution(tmp_path)

    assert bootstrap.mode == "fresh_project_bootstrap"
    assert bootstrap.publication_subject.status == "missing"
    assert bootstrap.publication_subject.publication_subject_slug == "curvature-flow-bounds"
    assert bootstrap.publication_subject.publication_lane_kind == "managed_publication_manuscript"
    assert bootstrap.publication_subject.managed_intake_root == manuscript_root.parent / "intake"
    assert bootstrap.publication_subject.managed_manuscript_root == manuscript_root
    assert bootstrap.bootstrap_root == manuscript_root
    assert "managed manuscript lane" in bootstrap.detail


def test_resolve_publication_bootstrap_resolution_blocks_on_ambiguous_manuscript_state(tmp_path: Path) -> None:
    _write(tmp_path / "paper" / "main.tex", "\\documentclass{article}\\begin{document}Main\\end{document}\n")
    _write(
        tmp_path / "paper" / "ARTIFACT-MANIFEST.json",
        json.dumps(
            {
                "version": 1,
                "paper_title": "Paper A",
                "journal": "jhep",
                "created_at": "2026-04-02T00:00:00+00:00",
                "artifacts": [
                    {
                        "artifact_id": "tex-paper",
                        "category": "tex",
                        "path": "main.tex",
                        "sha256": "0" * 64,
                        "produced_by": "test",
                        "sources": [],
                        "metadata": {},
                    }
                ],
            }
        )
        + "\n",
    )
    _write(tmp_path / "manuscript" / "main.tex", "\\documentclass{article}\\begin{document}Other\\end{document}\n")
    _write(
        tmp_path / "manuscript" / "ARTIFACT-MANIFEST.json",
        json.dumps(
            {
                "version": 1,
                "paper_title": "Paper B",
                "journal": "jhep",
                "created_at": "2026-04-02T00:00:00+00:00",
                "artifacts": [
                    {
                        "artifact_id": "tex-manuscript",
                        "category": "tex",
                        "path": "main.tex",
                        "sha256": "1" * 64,
                        "produced_by": "test",
                        "sources": [],
                        "metadata": {},
                    }
                ],
            }
        )
        + "\n",
    )

    bootstrap = resolve_publication_bootstrap_resolution(tmp_path)

    assert bootstrap.mode == "blocked"
    assert bootstrap.bootstrap_root is None
    assert "publication bootstrap is blocked" in bootstrap.detail


def test_resolve_publication_bootstrap_resolution_blocks_when_multiple_bootstrap_roots_compete(tmp_path: Path) -> None:
    _write(
        tmp_path / "paper" / "PAPER-CONFIG.json",
        json.dumps(
            {
                "title": "Curvature Flow Bounds",
                "authors": [{"name": "A. Researcher"}],
                "abstract": "Abstract.",
                "sections": [{"heading": "Intro", "content": "Hello."}],
            }
        )
        + "\n",
    )
    _write(
        tmp_path / "GPD" / "publication" / "curvature-flow-bounds" / "manuscript" / "PAPER-CONFIG.json",
        json.dumps(
            {
                "title": "Curvature Flow Bounds",
                "authors": [{"name": "A. Researcher"}],
                "abstract": "Abstract.",
                "sections": [{"heading": "Intro", "content": "Hello."}],
            }
        )
        + "\n",
    )

    bootstrap = resolve_publication_bootstrap_resolution(tmp_path)

    assert bootstrap.mode == "blocked"
    assert bootstrap.bootstrap_root is None
    assert "multiple manuscript bootstrap roots are present" in bootstrap.detail


def test_resolve_explicit_publication_subject_accepts_explicit_entrypoint_and_uses_its_artifact_base(
    tmp_path: Path,
) -> None:
    manuscript = tmp_path / "manuscript" / "curvature_flow_bounds.tex"
    _write(
        manuscript,
        "\\documentclass{article}\\begin{document}Hi\\end{document}\n",
    )
    _write(
        tmp_path / "manuscript" / "ARTIFACT-MANIFEST.json",
        _artifact_manifest_json(manuscript, artifact_id="tex-manuscript"),
    )
    _write(tmp_path / "manuscript" / "BIBLIOGRAPHY-AUDIT.json", "{}\n")

    subject = resolve_explicit_publication_subject(tmp_path, "manuscript/curvature_flow_bounds.tex")

    assert subject.status == "resolved"
    assert subject.source == "explicit_target"
    assert subject.target_path == tmp_path / "manuscript" / "curvature_flow_bounds.tex"
    assert subject.manuscript_root == tmp_path / "manuscript"
    assert subject.manuscript_entrypoint == tmp_path / "manuscript" / "curvature_flow_bounds.tex"
    assert subject.artifact_base == tmp_path / "manuscript"
    assert subject.bibliography_audit == tmp_path / "manuscript" / "BIBLIOGRAPHY-AUDIT.json"
    assert subject.publication_root == tmp_path / "GPD"
    assert subject.review_dir == tmp_path / "GPD" / "review"
    assert publication_root_for_subject(subject) == tmp_path / "GPD"
    assert review_dir_for_subject(subject) == tmp_path / "GPD" / "review"


def test_resolve_explicit_external_publication_subject_exposes_subject_owned_publication_root_and_review_dir(
    tmp_path: Path,
) -> None:
    external_root = tmp_path / "external-draft"
    _write(
        external_root / "main.tex",
        "\\documentclass{article}\\begin{document}External\\end{document}\n",
    )
    _write(
        external_root / "ARTIFACT-MANIFEST.json",
        json.dumps(
            {
                "version": 1,
                "paper_title": "External Draft",
                "journal": "jhep",
                "created_at": "2026-04-02T00:00:00+00:00",
                "artifacts": [
                    {
                        "artifact_id": "tex-manuscript",
                        "category": "tex",
                        "path": "main.tex",
                        "sha256": "0" * 64,
                        "produced_by": "test",
                        "sources": [],
                        "metadata": {},
                    }
                ],
            }
        )
        + "\n",
    )

    subject = resolve_explicit_publication_subject(tmp_path, external_root / "main.tex")

    assert subject.status == "resolved"
    assert subject.source == "explicit_target"
    assert subject.manuscript_root == external_root
    assert subject.manuscript_entrypoint == external_root / "main.tex"
    assert subject.artifact_base == external_root
    assert subject.publication_lane_kind == "external_artifact"
    assert subject.publication_lane_owner == "external_artifact"
    assert subject.publication_subject_slug is not None
    assert subject.managed_publication_root == tmp_path / "GPD" / "publication" / subject.publication_subject_slug
    assert subject.managed_intake_root == subject.managed_publication_root / "intake"
    assert subject.managed_manuscript_root is None
    assert subject.publication_root == subject.managed_publication_root
    assert subject.review_dir == subject.publication_root / "review"
    assert publication_root_for_subject(subject) == subject.publication_root
    assert review_dir_for_subject(subject) == subject.review_dir
    subject_context = subject.to_context_dict()
    assert subject_context["publication_root"] == f"GPD/publication/{subject.publication_subject_slug}"
    assert subject_context["review_dir"] == f"GPD/publication/{subject.publication_subject_slug}/review"
    assert subject_context["managed_publication_root"] == f"GPD/publication/{subject.publication_subject_slug}"
    assert subject_context["managed_intake_root"] == f"GPD/publication/{subject.publication_subject_slug}/intake"
    assert subject_context["managed_manuscript_root"] is None


def test_resolve_current_manuscript_resolution_ignores_publication_intake_roots(tmp_path: Path) -> None:
    intake_root = tmp_path / "GPD" / "publication" / "curvature-flow-bounds" / "intake"
    _write(
        intake_root / "PAPER-CONFIG.json",
        json.dumps(
            {
                "title": "Curvature Flow Bounds",
                "authors": [{"name": "A. Researcher"}],
                "abstract": "Abstract.",
                "sections": [{"heading": "Intro", "content": "Hello."}],
            }
        )
        + "\n",
    )
    _write(intake_root / "main.tex", "\\documentclass{article}\\begin{document}Intake\\end{document}\n")

    resolution = resolve_current_manuscript_resolution(tmp_path)
    bootstrap = resolve_publication_bootstrap_resolution(tmp_path)

    assert resolution.status == "missing"
    assert resolution.manuscript_root is None
    assert resolution.manuscript_entrypoint is None
    assert resolve_current_manuscript_entrypoint(tmp_path) is None
    assert resolve_current_manuscript_root(tmp_path) is None
    assert bootstrap.mode == "fresh_project_bootstrap"
    assert bootstrap.bootstrap_root == tmp_path / "paper"


def test_resolve_explicit_publication_subject_rejects_noncanonical_entrypoint_under_supported_root(
    tmp_path: Path,
) -> None:
    main = tmp_path / "paper" / "main.tex"
    _write(main, "\\documentclass{article}\\begin{document}Main\\end{document}\n")
    _write(tmp_path / "paper" / "appendix.tex", "\\documentclass{article}\\begin{document}Appendix\\end{document}\n")
    _write(
        tmp_path / "paper" / "ARTIFACT-MANIFEST.json",
        _artifact_manifest_json(main),
    )

    subject = resolve_explicit_publication_subject(tmp_path, tmp_path / "paper" / "appendix.tex")

    assert subject.status == "invalid"
    assert subject.source == "explicit_target"
    assert "does not match the resolved manuscript entrypoint" in subject.detail


def test_resolve_explicit_publication_subject_rejects_noncanonical_entrypoint_under_managed_lane(
    tmp_path: Path,
) -> None:
    manuscript_root = tmp_path / "GPD" / "publication" / "curvature-flow-bounds" / "manuscript"
    main = manuscript_root / "main.tex"
    _write(main, "\\documentclass{article}\\begin{document}Main\\end{document}\n")
    _write(manuscript_root / "appendix.tex", "\\documentclass{article}\\begin{document}Appendix\\end{document}\n")
    _write(
        manuscript_root / "ARTIFACT-MANIFEST.json",
        _artifact_manifest_json(main),
    )

    subject = resolve_explicit_publication_subject(tmp_path, manuscript_root / "appendix.tex")

    assert subject.status == "invalid"
    assert subject.source == "explicit_target"
    assert "does not match the resolved manuscript entrypoint" in subject.detail


def test_resolve_current_manuscript_artifacts_ignores_uppercase_reproducibility_manifest_alias(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _write(
        tmp_path / "manuscript" / "PAPER-CONFIG.json",
        json.dumps(
            {
                "title": "Asymptotic Matching Note",
                "authors": [{"name": "A. Researcher"}],
                "abstract": "Abstract.",
                "sections": [{"heading": "Intro", "content": "Hello."}],
            }
        )
        + "\n",
    )
    _write(tmp_path / "manuscript" / "asymptotic_matching_note.md", "# Manuscript\n")
    _write(tmp_path / "manuscript" / "REPRODUCIBILITY-MANIFEST.json", "{}\n")

    requested_filenames: list[tuple[str, ...]] = []

    def fake_locate_publication_artifact(manuscript_root: Path, *filenames: str) -> Path | None:
        requested_filenames.append(filenames)
        if filenames == ("ARTIFACT-MANIFEST.json",):
            return manuscript_root / "ARTIFACT-MANIFEST.json"
        if filenames == ("BIBLIOGRAPHY-AUDIT.json",):
            return manuscript_root / "BIBLIOGRAPHY-AUDIT.json"
        if filenames == ("reproducibility-manifest.json",):
            return manuscript_root / "reproducibility-manifest.json"
        return None

    monkeypatch.setattr("gpd.core.manuscript_artifacts.locate_publication_artifact", fake_locate_publication_artifact)

    artifacts = resolve_current_manuscript_artifacts(tmp_path)

    assert artifacts.manuscript_entrypoint == tmp_path / "manuscript" / "asymptotic_matching_note.md"
    assert requested_filenames == [
        ("ARTIFACT-MANIFEST.json",),
        ("BIBLIOGRAPHY-AUDIT.json",),
        ("reproducibility-manifest.json",),
    ]
    assert artifacts.reproducibility_manifest == tmp_path / "manuscript" / "reproducibility-manifest.json"


def test_resolve_current_manuscript_entrypoint_ignores_manifest_paths_outside_root(tmp_path: Path) -> None:
    _write(
        tmp_path / "submission" / "curvature_flow_bounds.tex",
        "\\documentclass{article}\\begin{document}Hi\\end{document}\n",
    )
    _write(
        tmp_path / "paper" / "ARTIFACT-MANIFEST.json",
        json.dumps(
            {
                "version": 1,
                "paper_title": "Curvature Flow Bounds",
                "journal": "prl",
                "created_at": "2026-04-02T00:00:00+00:00",
                "artifacts": [
                    {
                        "artifact_id": "tex-paper",
                        "category": "tex",
                        "path": "../submission/curvature_flow_bounds.tex",
                        "sha256": "0" * 64,
                        "produced_by": "test",
                        "sources": [],
                        "metadata": {},
                    }
                ],
            }
        )
        + "\n",
    )

    resolution = resolve_current_manuscript_resolution(tmp_path)

    assert resolution.status == "missing"
    assert resolution.manuscript_root is None
    assert resolution.manuscript_entrypoint is None
    assert resolve_current_manuscript_entrypoint(tmp_path) is None


def test_resolve_current_manuscript_entrypoint_fails_closed_when_multiple_roots_resolve(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / "paper" / "curvature_flow_bounds.tex",
        "\\documentclass{article}\\begin{document}Paper\\end{document}\n",
    )
    _write(
        tmp_path / "paper" / "ARTIFACT-MANIFEST.json",
        json.dumps(
            {
                "version": 1,
                "paper_title": "Curvature Flow Bounds",
                "journal": "jhep",
                "created_at": "2026-04-02T00:00:00+00:00",
                "artifacts": [
                    {
                        "artifact_id": "tex-paper",
                        "category": "tex",
                        "path": "curvature_flow_bounds.tex",
                        "sha256": "0" * 64,
                        "produced_by": "test",
                        "sources": [],
                        "metadata": {},
                    }
                ],
            }
        )
        + "\n",
    )
    _write(
        tmp_path / "manuscript" / "curvature_flow_bounds.tex",
        "\\documentclass{article}\\begin{document}Manuscript\\end{document}\n",
    )
    _write(
        tmp_path / "manuscript" / "ARTIFACT-MANIFEST.json",
        json.dumps(
            {
                "version": 1,
                "paper_title": "Curvature Flow Bounds",
                "journal": "jhep",
                "created_at": "2026-04-02T00:00:00+00:00",
                "artifacts": [
                    {
                        "artifact_id": "tex-manuscript",
                        "category": "tex",
                        "path": "curvature_flow_bounds.tex",
                        "sha256": "0" * 64,
                        "produced_by": "test",
                        "sources": [],
                        "metadata": {},
                    }
                ],
            }
        )
        + "\n",
    )

    assert resolve_current_manuscript_entrypoint(tmp_path) is None
    assert resolve_current_manuscript_root(tmp_path) is None


def test_resolve_current_manuscript_resolution_marks_multiple_roots_ambiguous(tmp_path: Path) -> None:
    paper_manuscript = tmp_path / "paper" / "curvature_flow_bounds.tex"
    _write(
        paper_manuscript,
        "\\documentclass{article}\\begin{document}Paper\\end{document}\n",
    )
    _write(
        tmp_path / "paper" / "ARTIFACT-MANIFEST.json",
        _artifact_manifest_json(paper_manuscript),
    )
    manuscript = tmp_path / "manuscript" / "curvature_flow_bounds.tex"
    _write(
        manuscript,
        "\\documentclass{article}\\begin{document}Manuscript\\end{document}\n",
    )
    _write(
        tmp_path / "manuscript" / "ARTIFACT-MANIFEST.json",
        _artifact_manifest_json(manuscript, artifact_id="tex-manuscript"),
    )

    resolution = resolve_current_manuscript_resolution(tmp_path)

    assert isinstance(resolution, ManuscriptResolution)
    assert resolution.status == "ambiguous"
    assert resolution.manuscript_entrypoint is None
    assert {root_resolution.status for root_resolution in resolution.root_resolutions} == {"resolved", "missing"}
    assert any(isinstance(root_resolution, ManuscriptRootResolution) for root_resolution in resolution.root_resolutions)
    assert "multiple manuscript roots resolve" in resolution.detail


def test_resolve_current_manuscript_resolution_marks_root_mismatch_invalid(tmp_path: Path) -> None:
    manuscript = tmp_path / "paper" / "curvature_flow_bounds.tex"
    _write(
        manuscript, "\\documentclass{article}\\begin{document}Hi\\end{document}\n"
    )
    _write(
        tmp_path / "paper" / "ARTIFACT-MANIFEST.json",
        _artifact_manifest_json(manuscript, journal="prl"),
    )
    _write(
        tmp_path / "paper" / "PAPER-CONFIG.json",
        json.dumps(
            {
                "title": "Alternate Title",
                "authors": [{"name": "A. Researcher"}],
                "abstract": "Abstract.",
                "sections": [{"heading": "Intro", "content": "Hello."}],
            }
        )
        + "\n",
    )

    resolution = resolve_current_manuscript_resolution(tmp_path)

    assert resolution.status == "invalid"
    assert resolution.manuscript_entrypoint is None
    assert any(root_resolution.status == "invalid" for root_resolution in resolution.root_resolutions)
    assert "resolves to" in resolution.detail


def test_resolve_current_manuscript_resolution_fails_closed_when_manifest_is_invalid(
    tmp_path: Path,
) -> None:
    _write(tmp_path / "paper" / "config-entry.tex", "\\documentclass{article}\\begin{document}Hi\\end{document}\n")
    _write(tmp_path / "paper" / "manifest-entry.tex", "\\documentclass{article}\\begin{document}Hi\\end{document}\n")
    _write(
        tmp_path / "paper" / "ARTIFACT-MANIFEST.json",
        json.dumps(
            {
                "version": 1,
                "paper_title": "Curvature Flow Bounds",
                "journal": "prd",
                "created_at": "2026-04-02T00:00:00+00:00",
                "artifacts": [
                    {
                        "artifact_id": "tex-paper",
                        "category": "tex",
                        "path": "manifest-entry.tex",
                        "sha256": "0" * 64,
                        "produced_by": "test",
                        "sources": [],
                        "metadata": {},
                    }
                ],
            }
        )
        + "\n",
    )
    _write(
        tmp_path / "paper" / "PAPER-CONFIG.json",
        json.dumps(
            {
                "title": "Config Entry",
                "output_filename": "config-entry",
                "authors": [{"name": "A. Researcher"}],
                "abstract": "Abstract.",
                "sections": [{"heading": "Intro", "content": "Hello."}],
            }
        )
        + "\n",
    )

    resolution = resolve_current_manuscript_resolution(tmp_path)

    assert resolution.status == "invalid"
    assert resolution.manuscript_entrypoint is None
    assert any(root_resolution.status == "invalid" for root_resolution in resolution.root_resolutions)
    assert "ARTIFACT-MANIFEST.json is invalid" in resolution.detail
    assert "journal" in resolution.detail


def test_resolve_current_manuscript_resolution_fails_closed_when_manifest_json_is_corrupt(
    tmp_path: Path,
) -> None:
    _write(tmp_path / "paper" / "config-entry.tex", "\\documentclass{article}\\begin{document}Hi\\end{document}\n")
    _write(tmp_path / "paper" / "ARTIFACT-MANIFEST.json", "{not valid json")
    _write(
        tmp_path / "paper" / "PAPER-CONFIG.json",
        json.dumps(
            {
                "title": "Config Entry",
                "output_filename": "config-entry",
                "authors": [{"name": "A. Researcher"}],
                "abstract": "Abstract.",
                "sections": [{"heading": "Intro", "content": "Hello."}],
            }
        )
        + "\n",
    )

    resolution = resolve_current_manuscript_resolution(tmp_path)

    assert resolution.status == "invalid"
    assert resolution.manuscript_entrypoint is None
    assert "ARTIFACT-MANIFEST.json is invalid" in resolution.detail


def test_resolve_current_manuscript_resolution_prefers_single_resolved_root_over_stale_invalid_sibling(
    tmp_path: Path,
) -> None:
    _write(tmp_path / "paper" / "paper-entry.tex", "\\documentclass{article}\\begin{document}Hi\\end{document}\n")
    _write(
        tmp_path / "paper" / "PAPER-CONFIG.json",
        json.dumps(
            {
                "title": "Config Entry",
                "output_filename": "paper-entry",
                "authors": [{"name": "A. Researcher"}],
                "abstract": "Abstract.",
                "sections": [{"heading": "Intro", "content": "Hello."}],
            }
        )
        + "\n",
    )
    _write(
        tmp_path / "draft" / "ARTIFACT-MANIFEST.json",
        json.dumps(
            {
                "version": 1,
                "paper_title": "Curvature Flow Bounds",
                "journal": "prl",
                "created_at": "2026-04-02T00:00:00+00:00",
                "artifacts": [
                    {
                        "artifact_id": "tex-paper",
                        "category": "tex",
                        "path": "draft-entry.tex",
                        "sha256": "0" * 64,
                        "produced_by": "test",
                        "sources": [],
                        "metadata": {},
                    }
                ],
            }
        )
        + "\n",
    )
    _write(tmp_path / "draft" / "draft-entry.tex", "\\documentclass{article}\\begin{document}Hi\\end{document}\n")
    _write(tmp_path / "draft" / "other-entry.tex", "\\documentclass{article}\\begin{document}Hi\\end{document}\n")
    _write(
        tmp_path / "draft" / "PAPER-CONFIG.json",
        json.dumps(
            {
                "title": "Mismatched Draft",
                "output_filename": "other-entry",
                "authors": [{"name": "A. Researcher"}],
                "abstract": "Abstract.",
                "sections": [{"heading": "Intro", "content": "Hello."}],
            }
        )
        + "\n",
    )

    resolution = resolve_current_manuscript_resolution(tmp_path)

    assert resolution.status == "resolved"
    assert resolution.manuscript_entrypoint == tmp_path / "paper" / "paper-entry.tex"
    assert "paper config" in resolution.detail


def test_resolve_current_manuscript_resolution_fails_closed_on_invalid_manifest_without_config(
    tmp_path: Path,
) -> None:
    _write(tmp_path / "paper" / "manifest-entry.tex", "\\documentclass{article}\\begin{document}Hi\\end{document}\n")
    _write(
        tmp_path / "paper" / "ARTIFACT-MANIFEST.json",
        json.dumps(
            {
                "version": 1,
                "paper_title": "Curvature Flow Bounds",
                "journal": "prd",
                "created_at": "2026-04-02T00:00:00+00:00",
                "artifacts": [
                    {
                        "artifact_id": "tex-paper",
                        "category": "tex",
                        "path": "manifest-entry.tex",
                        "sha256": "0" * 64,
                        "produced_by": "test",
                        "sources": [],
                        "metadata": {},
                    }
                ],
            }
        )
        + "\n",
    )

    resolution = resolve_current_manuscript_resolution(tmp_path)

    assert resolution.status == "invalid"
    assert resolution.manuscript_entrypoint is None
    assert "ARTIFACT-MANIFEST.json is invalid" in resolution.detail


def test_resolve_current_manuscript_resolution_marks_missing_when_no_manuscript_exists(tmp_path: Path) -> None:
    resolution = resolve_current_manuscript_resolution(tmp_path)

    assert resolution.status == "missing"
    assert resolution.manuscript_entrypoint is None
    assert resolution.detail.startswith("no manuscript entrypoint")


def test_resolve_current_manuscript_resolution_treats_stale_manifest_without_output_as_missing(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path / "paper" / "ARTIFACT-MANIFEST.json",
        json.dumps(
            {
                "version": 1,
                "paper_title": "Curvature Flow Bounds",
                "journal": "prl",
                "created_at": "2026-04-02T00:00:00+00:00",
                "artifacts": [
                    {
                        "artifact_id": "tex-paper",
                        "category": "tex",
                        "path": "curvature_flow_bounds.tex",
                        "sha256": "0" * 64,
                        "produced_by": "test",
                        "sources": [],
                        "metadata": {},
                    }
                ],
            }
        )
        + "\n",
    )
    _write(
        tmp_path / "paper" / "PAPER-CONFIG.json",
        json.dumps(
            {
                "title": "Curvature Flow Bounds",
                "authors": [{"name": "A. Researcher"}],
                "abstract": "Abstract.",
                "sections": [{"heading": "Intro", "content": "Hello."}],
            }
        )
        + "\n",
    )

    resolution = resolve_current_manuscript_resolution(tmp_path)

    assert resolution.status == "missing"
    assert resolution.manuscript_entrypoint is None
    assert "no manuscript entrypoint found" in resolution.detail


def test_resolve_current_manuscript_resolution_prefers_config_output_when_manifest_is_stale(
    tmp_path: Path,
) -> None:
    _write(tmp_path / "paper" / "curvature_flow_bounds.md", "# Draft\n")
    _write(
        tmp_path / "paper" / "ARTIFACT-MANIFEST.json",
        json.dumps(
            {
                "version": 1,
                "paper_title": "Curvature Flow Bounds",
                "journal": "prl",
                "created_at": "2026-04-02T00:00:00+00:00",
                "artifacts": [
                    {
                        "artifact_id": "tex-paper",
                        "category": "tex",
                        "path": "curvature_flow_bounds.tex",
                        "sha256": "0" * 64,
                        "produced_by": "test",
                        "sources": [],
                        "metadata": {},
                    }
                ],
            }
        )
        + "\n",
    )
    _write(
        tmp_path / "paper" / "PAPER-CONFIG.json",
        json.dumps(
            {
                "title": "Curvature Flow Bounds",
                "authors": [{"name": "A. Researcher"}],
                "abstract": "Abstract.",
                "sections": [{"heading": "Intro", "content": "Hello."}],
            }
        )
        + "\n",
    )

    resolution = resolve_current_manuscript_resolution(tmp_path)

    assert resolution.status == "resolved"
    assert resolution.manuscript_entrypoint == tmp_path / "paper" / "curvature_flow_bounds.md"
    assert resolution.detail.endswith("resolved from paper config")


def test_resolve_manuscript_entrypoint_from_root_returns_invalid_when_manifest_and_config_disagree(
    tmp_path: Path,
) -> None:
    manuscript_root = tmp_path / "paper"
    _write(
        manuscript_root / "curvature_flow_bounds.tex", "\\documentclass{article}\\begin{document}Hi\\end{document}\n"
    )
    _write(
        manuscript_root / "ARTIFACT-MANIFEST.json",
        json.dumps(
            {
                "version": 1,
                "paper_title": "Curvature Flow Bounds",
                "journal": "prl",
                "created_at": "2026-04-02T00:00:00+00:00",
                "artifacts": [
                    {
                        "artifact_id": "tex-paper",
                        "category": "tex",
                        "path": "curvature_flow_bounds.tex",
                        "sha256": "0" * 64,
                        "produced_by": "test",
                        "sources": [],
                        "metadata": {},
                    }
                ],
            }
        )
        + "\n",
    )
    _write(
        manuscript_root / "PAPER-CONFIG.json",
        json.dumps(
            {
                "title": "Alternate Title",
                "authors": [{"name": "A. Researcher"}],
                "abstract": "Abstract.",
                "sections": [{"heading": "Intro", "content": "Hello."}],
            }
        )
        + "\n",
    )

    assert resolve_manuscript_entrypoint_from_root(manuscript_root) is None


def test_locate_publication_artifact_accepts_named_entrypoint_path(tmp_path: Path) -> None:
    manuscript = tmp_path / "draft" / "scalar_gap_bounds.tex"
    _write(manuscript, "\\documentclass{article}\\begin{document}Hi\\end{document}\n")
    _write(tmp_path / "draft" / "ARTIFACT-MANIFEST.json", "{}\n")

    assert (
        locate_publication_artifact(manuscript, "ARTIFACT-MANIFEST.json")
        == tmp_path / "draft" / "ARTIFACT-MANIFEST.json"
    )


def test_resolve_current_manuscript_artifacts_does_not_fall_back_to_legacy_main_entrypoint(
    tmp_path: Path,
) -> None:
    _write(tmp_path / "draft" / "main.tex", "\\documentclass{article}\\begin{document}Hi\\end{document}\n")

    assert resolve_current_manuscript_entrypoint(tmp_path) is None


def test_resolve_current_manuscript_artifacts_requires_manifest_or_config_for_topic_stem_entrypoint(
    tmp_path: Path,
) -> None:
    manuscript = tmp_path / "draft" / "curvature_flow_bounds.tex"
    _write(
        manuscript, "\\documentclass{article}\\begin{document}Hi\\end{document}\n"
    )
    _write(
        tmp_path / "draft" / "ARTIFACT-MANIFEST.json",
        _artifact_manifest_json(manuscript, artifact_id="tex-draft"),
    )

    assert resolve_current_manuscript_entrypoint(tmp_path) == tmp_path / "draft" / "curvature_flow_bounds.tex"


def test_resolve_current_manuscript_entrypoint_fails_closed_when_manifest_and_config_disagree(tmp_path: Path) -> None:
    _write(
        tmp_path / "paper" / "curvature_flow_bounds.tex", "\\documentclass{article}\\begin{document}Hi\\end{document}\n"
    )
    _write(tmp_path / "paper" / "alternate_title.tex", "\\documentclass{article}\\begin{document}Hi\\end{document}\n")
    _write(
        tmp_path / "paper" / "ARTIFACT-MANIFEST.json",
        json.dumps(
            {
                "version": 1,
                "paper_title": "Curvature Flow Bounds",
                "journal": "jhep",
                "created_at": "2026-04-02T00:00:00+00:00",
                "artifacts": [
                    {
                        "artifact_id": "tex-paper",
                        "category": "tex",
                        "path": "curvature_flow_bounds.tex",
                        "sha256": "0" * 64,
                        "produced_by": "test",
                        "sources": [],
                        "metadata": {},
                    }
                ],
            }
        )
        + "\n",
    )
    _write(
        tmp_path / "paper" / "PAPER-CONFIG.json",
        json.dumps(
            {
                "title": "Alternate Title",
                "authors": [{"name": "A. Researcher"}],
                "abstract": "Abstract.",
                "sections": [{"heading": "Intro", "content": "Hello."}],
            }
        )
        + "\n",
    )

    assert resolve_current_manuscript_entrypoint(tmp_path) is None
    assert resolve_current_manuscript_root(tmp_path) is None


def test_resolve_current_manuscript_artifacts_returns_none_when_missing(tmp_path: Path) -> None:
    artifacts = resolve_current_manuscript_artifacts(tmp_path)

    assert artifacts == ManuscriptArtifacts(
        project_root=tmp_path,
        manuscript_root=None,
        manuscript_entrypoint=None,
        artifact_manifest=None,
        bibliography_audit=None,
        reproducibility_manifest=None,
    )
    assert resolve_current_manuscript_entrypoint(tmp_path) is None
    assert resolve_current_manuscript_root(tmp_path) is None
