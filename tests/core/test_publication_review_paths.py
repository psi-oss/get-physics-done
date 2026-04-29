from __future__ import annotations

import re
from pathlib import Path

from gpd.core.publication_review_paths import (
    manuscript_matches_review_artifact_path,
    normalize_review_path_label,
    review_artifact_round,
)


def test_review_artifact_round_defaults_to_round_one_without_suffix() -> None:
    pattern = re.compile(r"^REFEREE-DECISION(?P<round_suffix>-R(?P<round>\d+))?\.json$")

    assert review_artifact_round(Path("REFEREE-DECISION.json"), pattern=pattern) == (1, "")


def test_review_artifact_round_rejects_noncanonical_suffixed_rounds() -> None:
    pattern = re.compile(r"^REFEREE-DECISION(?P<round_suffix>-R(?P<round>\d+))?\.json$")

    assert review_artifact_round(Path("REFEREE-DECISION-R0.json"), pattern=pattern) is None
    assert review_artifact_round(Path("REFEREE-DECISION-R1.json"), pattern=pattern) is None
    assert review_artifact_round(Path("REFEREE-DECISION-R01.json"), pattern=pattern) is None
    assert review_artifact_round(Path("REFEREE-DECISION-R2.json"), pattern=pattern) == (2, "-R2")


def test_manuscript_matches_review_artifact_path_accepts_relative_and_normalized_forms(tmp_path: Path) -> None:
    manuscript = tmp_path / "paper" / "main.tex"
    manuscript.parent.mkdir(parents=True)
    manuscript.write_text("\\documentclass{article}\n", encoding="utf-8")

    assert manuscript_matches_review_artifact_path("paper/main.tex", manuscript, cwd=tmp_path)
    assert manuscript_matches_review_artifact_path(".\\paper\\main.tex", manuscript, cwd=tmp_path)
    assert manuscript_matches_review_artifact_path(str(manuscript.resolve(strict=False)), manuscript, cwd=tmp_path)
    assert not manuscript_matches_review_artifact_path("paper/other.tex", manuscript, cwd=tmp_path)


def test_normalize_review_path_label_trims_and_normalizes_separators() -> None:
    assert normalize_review_path_label("  .\\paper\\subdir\\..\\main.tex  ") == "paper/main.tex"


def test_publication_core_modules_delegate_review_roots_to_layout_helpers() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    checked_paths = (
        repo_root / "src" / "gpd" / "core" / "publication_rounds.py",
        repo_root / "src" / "gpd" / "core" / "publication_runtime.py",
        repo_root / "src" / "gpd" / "core" / "proof_review.py",
    )
    forbidden_snippets = (
        'layout.gpd / "review"',
        "layout.gpd / 'review'",
        'publication_root / "review"',
        "publication_root / 'review'",
    )
    offenders: list[str] = []
    for path in checked_paths:
        source = path.read_text(encoding="utf-8")
        offenders.extend(
            f"{path.relative_to(repo_root).as_posix()}: {snippet}"
            for snippet in forbidden_snippets
            if snippet in source
        )

    assert offenders == []


def test_proof_review_managed_publication_lane_uses_layout_manuscript_constant() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    source = (repo_root / "src" / "gpd" / "core" / "proof_review.py").read_text(encoding="utf-8")

    assert 'relative.parts[3] == "manuscript"' not in source
    assert "PUBLICATION_MANUSCRIPT_DIR_NAME" in source
