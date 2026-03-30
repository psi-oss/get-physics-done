from __future__ import annotations

from pathlib import Path

from gpd.core.manuscript_artifacts import (
    ManuscriptArtifacts,
    locate_publication_artifact,
    resolve_current_manuscript_artifacts,
    resolve_current_manuscript_entrypoint,
    resolve_current_manuscript_root,
)


def _write(path: Path, content: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_resolve_current_manuscript_artifacts_prefers_paper_tex(tmp_path: Path) -> None:
    _write(tmp_path / "paper" / "main.tex", "\\documentclass{article}\\begin{document}Hi\\end{document}\n")
    _write(tmp_path / "paper" / "ARTIFACT-MANIFEST.json", "{}\n")
    _write(tmp_path / "paper" / "BIBLIOGRAPHY-AUDIT.json", "{}\n")
    _write(tmp_path / "paper" / "reproducibility-manifest.json", "{}\n")

    artifacts = resolve_current_manuscript_artifacts(tmp_path)

    assert isinstance(artifacts, ManuscriptArtifacts)
    assert artifacts.manuscript_entrypoint == tmp_path / "paper" / "main.tex"
    assert artifacts.manuscript_root == tmp_path / "paper"
    assert artifacts.artifact_manifest == tmp_path / "paper" / "ARTIFACT-MANIFEST.json"
    assert artifacts.bibliography_audit == tmp_path / "paper" / "BIBLIOGRAPHY-AUDIT.json"
    assert artifacts.reproducibility_manifest == tmp_path / "paper" / "reproducibility-manifest.json"
    assert resolve_current_manuscript_entrypoint(tmp_path) == tmp_path / "paper" / "main.tex"
    assert resolve_current_manuscript_root(tmp_path) == tmp_path / "paper"


def test_resolve_current_manuscript_artifacts_supports_markdown_and_uppercase_reproducibility(tmp_path: Path) -> None:
    _write(tmp_path / "manuscript" / "main.md", "# Manuscript\n")
    _write(tmp_path / "manuscript" / "ARTIFACT-MANIFEST.json", "{}\n")
    _write(tmp_path / "manuscript" / "BIBLIOGRAPHY-AUDIT.json", "{}\n")
    _write(tmp_path / "manuscript" / "REPRODUCIBILITY-MANIFEST.json", "{}\n")

    artifacts = resolve_current_manuscript_artifacts(tmp_path)

    assert artifacts.manuscript_entrypoint == tmp_path / "manuscript" / "main.md"
    assert artifacts.manuscript_root == tmp_path / "manuscript"
    assert artifacts.reproducibility_manifest in {
        tmp_path / "manuscript" / "reproducibility-manifest.json",
        tmp_path / "manuscript" / "REPRODUCIBILITY-MANIFEST.json",
    }


def test_locate_publication_artifact_accepts_entrypoint_path(tmp_path: Path) -> None:
    manuscript = tmp_path / "draft" / "main.tex"
    _write(manuscript, "\\documentclass{article}\\begin{document}Hi\\end{document}\n")
    _write(tmp_path / "draft" / "ARTIFACT-MANIFEST.json", "{}\n")

    assert locate_publication_artifact(manuscript, "ARTIFACT-MANIFEST.json") == tmp_path / "draft" / "ARTIFACT-MANIFEST.json"


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
