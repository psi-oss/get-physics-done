from __future__ import annotations

import json
import re
from pathlib import Path

from gpd.core.manuscript_artifacts import resolve_current_manuscript_artifacts
from gpd.core.publication_review_paths import manuscript_matches_review_artifact_path, review_artifact_round
from gpd.core.reproducibility import compute_sha256


def _write(path: Path, content: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_publication_artifact_resolution_uses_the_active_manuscript_root_only(tmp_path: Path) -> None:
    manuscript = tmp_path / "paper" / "curvature_flow_bounds.tex"
    _write(manuscript, "\\documentclass{article}\\begin{document}Hi\\end{document}\n")
    manuscript_sha256 = compute_sha256(manuscript)
    _write(
        tmp_path / "paper" / "ARTIFACT-MANIFEST.json",
        json.dumps(
            {
                "version": 1,
                "paper_title": "Curvature Flow Bounds",
                "journal": "prl",
                "created_at": "2026-04-02T00:00:00+00:00",
                "manuscript_sha256": manuscript_sha256,
                "manuscript_mtime_ns": manuscript.stat().st_mtime_ns,
                "artifacts": [
                    {
                        "artifact_id": "tex-paper",
                        "category": "tex",
                        "path": "curvature_flow_bounds.tex",
                        "sha256": manuscript_sha256,
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
    _write(tmp_path / "draft" / "curvature_flow_bounds.tex", "\\documentclass{article}\\begin{document}Other\\end{document}\n")

    artifacts = resolve_current_manuscript_artifacts(tmp_path)

    assert artifacts.manuscript_root == tmp_path / "paper"
    assert artifacts.manuscript_entrypoint == tmp_path / "paper" / "curvature_flow_bounds.tex"
    assert artifacts.artifact_manifest == tmp_path / "paper" / "ARTIFACT-MANIFEST.json"
    assert artifacts.bibliography_audit == tmp_path / "paper" / "BIBLIOGRAPHY-AUDIT.json"
    assert artifacts.reproducibility_manifest == tmp_path / "paper" / "reproducibility-manifest.json"


def test_publication_review_round_suffix_canonicalization_rejects_noncanonical_suffixes() -> None:
    pattern = re.compile(r"^REFEREE-DECISION(?P<round_suffix>-R(?P<round>\d+))?\.json$")

    assert review_artifact_round(Path("REFEREE-DECISION.json"), pattern=pattern) == (1, "")
    assert review_artifact_round(Path("REFEREE-DECISION-R0.json"), pattern=pattern) is None
    assert review_artifact_round(Path("REFEREE-DECISION-R1.json"), pattern=pattern) is None
    assert review_artifact_round(Path("REFEREE-DECISION-R01.json"), pattern=pattern) is None
    assert review_artifact_round(Path("REFEREE-DECISION-R2.json"), pattern=pattern) == (2, "-R2")


def test_publication_review_path_matching_accepts_normalized_windows_separators(tmp_path: Path) -> None:
    manuscript = tmp_path / "paper" / "main.tex"
    manuscript.parent.mkdir(parents=True)
    manuscript.write_text("\\documentclass{article}\n", encoding="utf-8")

    assert manuscript_matches_review_artifact_path("paper/main.tex", manuscript, cwd=tmp_path)
    assert manuscript_matches_review_artifact_path(".\\paper\\main.tex", manuscript, cwd=tmp_path)
    assert manuscript_matches_review_artifact_path(str(manuscript.resolve(strict=False)), manuscript, cwd=tmp_path)
    assert not manuscript_matches_review_artifact_path("paper/other.tex", manuscript, cwd=tmp_path)
