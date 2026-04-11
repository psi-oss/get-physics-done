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


def test_publication_review_filename_patterns_are_centralized() -> None:
    from gpd.core.publication_review_paths import (
        AUTHOR_RESPONSE_FILENAME_RE,
        AUTHOR_RESPONSE_GLOB,
        REFEREE_DECISION_FILENAME_RE,
        REFEREE_DECISION_GLOB,
        REFEREE_RESPONSE_FILENAME_RE,
        REFEREE_RESPONSE_GLOB,
        REVIEW_LEDGER_FILENAME_RE,
        REVIEW_LEDGER_GLOB,
    )

    assert review_artifact_round(Path("REVIEW-LEDGER-R2.json"), pattern=REVIEW_LEDGER_FILENAME_RE) == (2, "-R2")
    assert review_artifact_round(Path("REFEREE-DECISION-R2.json"), pattern=REFEREE_DECISION_FILENAME_RE) == (2, "-R2")
    assert review_artifact_round(Path("AUTHOR-RESPONSE-R2.md"), pattern=AUTHOR_RESPONSE_FILENAME_RE) == (2, "-R2")
    assert review_artifact_round(Path("REFEREE_RESPONSE-R2.md"), pattern=REFEREE_RESPONSE_FILENAME_RE) == (2, "-R2")
    assert (REVIEW_LEDGER_GLOB, REFEREE_DECISION_GLOB, AUTHOR_RESPONSE_GLOB, REFEREE_RESPONSE_GLOB) == (
        "REVIEW-LEDGER*.json",
        "REFEREE-DECISION*.json",
        "AUTHOR-RESPONSE*.md",
        "REFEREE_RESPONSE*.md",
    )
