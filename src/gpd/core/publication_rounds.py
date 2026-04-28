"""Shared publication review/response round artifact discovery."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from gpd.core.constants import ProjectLayout
from gpd.core.manuscript_artifacts import (
    _supported_manuscript_root_for_target as resolve_supported_manuscript_root_for_target,
)
from gpd.core.proof_review import publication_lineage_roots
from gpd.core.publication_review_paths import review_artifact_round, review_round_suffix

__all__ = [
    "PublicationResponseRoundArtifacts",
    "PublicationReviewRoundArtifacts",
    "latest_publication_round_number",
    "publication_lineage_search_roots",
    "publication_response_round_path_maps",
    "publication_review_round_artifacts",
    "publication_review_round_path_maps",
    "resolve_latest_publication_response_round_artifacts",
    "resolve_latest_publication_review_round_artifacts",
]

_REVIEW_LEDGER_FILENAME_RE = re.compile(r"^REVIEW-LEDGER(?P<round_suffix>-R(?P<round>\d+))?\.json$")
_REFEREE_DECISION_FILENAME_RE = re.compile(r"^REFEREE-DECISION(?P<round_suffix>-R(?P<round>\d+))?\.json$")
_AUTHOR_RESPONSE_FILENAME_RE = re.compile(r"^AUTHOR-RESPONSE(?P<round_suffix>-R(?P<round>\d+))?\.md$")
_REFEREE_RESPONSE_FILENAME_RE = re.compile(r"^REFEREE_RESPONSE(?P<round_suffix>-R(?P<round>\d+))?\.md$")


@dataclass(frozen=True, slots=True)
class PublicationReviewRoundArtifacts:
    """Review-round artifacts without manuscript freshness validation."""

    round_number: int
    round_suffix: str
    review_ledger: Path | None
    referee_decision: Path | None


@dataclass(frozen=True, slots=True)
class PublicationResponseRoundArtifacts:
    """Response-round artifacts without review freshness validation."""

    round_number: int
    round_suffix: str
    author_response: Path | None
    referee_response: Path | None


def _unique_paths(*paths: Path) -> tuple[Path, ...]:
    return tuple(dict.fromkeys(paths))


def latest_publication_round_number(*round_maps: dict[int, Path | None]) -> int | None:
    """Return the latest round number present across one or more artifact maps."""

    rounds: set[int] = set()
    for round_map in round_maps:
        rounds.update(round_map)
    if not rounds:
        return None
    return max(rounds)


def _round_file_map(
    *search_roots: Path,
    filename_pattern: re.Pattern[str],
    glob_pattern: str,
) -> dict[int, Path]:
    round_map: dict[int, Path] = {}
    for root in search_roots:
        if not root.is_dir():
            continue
        for path in sorted(root.glob(glob_pattern)):
            details = review_artifact_round(path, pattern=filename_pattern)
            if details is None:
                continue
            round_number, _round_suffix = details
            round_map.setdefault(round_number, path)
    return round_map


def publication_lineage_search_roots(
    project_root: Path,
    *,
    manuscript: Path | None = None,
    include_global_fallback_for_external: bool = False,
) -> tuple[tuple[Path, ...], tuple[Path, ...]]:
    """Return publication and review search roots for one manuscript subject."""

    layout = ProjectLayout(project_root)
    if manuscript is None:
        return (layout.gpd,), (layout.review_dir,)

    publication_root, review_root = publication_lineage_roots(project_root, manuscript)
    if not include_global_fallback_for_external:
        return (publication_root,), (review_root,)

    supported_root = resolve_supported_manuscript_root_for_target(project_root, manuscript)
    if publication_root == layout.gpd or supported_root is not None:
        return (publication_root,), (review_root,)

    return _unique_paths(publication_root, layout.gpd), _unique_paths(review_root, layout.review_dir)


def publication_review_round_path_maps(
    project_root: Path,
    *,
    manuscript: Path | None = None,
    include_global_fallback_for_external: bool = False,
) -> tuple[dict[int, Path], dict[int, Path]]:
    """Return staged review-artifact maps rooted at the manuscript's publication lineage."""

    _publication_roots, review_roots = publication_lineage_search_roots(
        project_root,
        manuscript=manuscript,
        include_global_fallback_for_external=include_global_fallback_for_external,
    )
    return (
        _round_file_map(
            *review_roots,
            filename_pattern=_REVIEW_LEDGER_FILENAME_RE,
            glob_pattern="REVIEW-LEDGER*.json",
        ),
        _round_file_map(
            *review_roots,
            filename_pattern=_REFEREE_DECISION_FILENAME_RE,
            glob_pattern="REFEREE-DECISION*.json",
        ),
    )


def publication_response_round_path_maps(
    project_root: Path,
    *,
    manuscript: Path | None = None,
    include_global_fallback_for_external: bool = False,
    include_review_roots_for_author_response: bool = False,
) -> tuple[dict[int, Path], dict[int, Path]]:
    """Return paired response-artifact maps rooted at the manuscript's publication lineage."""

    publication_roots, review_roots = publication_lineage_search_roots(
        project_root,
        manuscript=manuscript,
        include_global_fallback_for_external=include_global_fallback_for_external,
    )
    author_response_roots = publication_roots
    if include_review_roots_for_author_response:
        author_response_roots = _unique_paths(*publication_roots, *review_roots)
    return (
        _round_file_map(
            *author_response_roots,
            filename_pattern=_AUTHOR_RESPONSE_FILENAME_RE,
            glob_pattern="AUTHOR-RESPONSE*.md",
        ),
        _round_file_map(
            *review_roots,
            filename_pattern=_REFEREE_RESPONSE_FILENAME_RE,
            glob_pattern="REFEREE_RESPONSE*.md",
        ),
    )


def publication_review_round_artifacts(
    round_number: int,
    *,
    review_ledger_by_round: dict[int, Path],
    referee_decision_by_round: dict[int, Path],
) -> PublicationReviewRoundArtifacts:
    """Return one staged review round bundle from precomputed round maps."""

    return PublicationReviewRoundArtifacts(
        round_number=round_number,
        round_suffix=review_round_suffix(round_number),
        review_ledger=review_ledger_by_round.get(round_number),
        referee_decision=referee_decision_by_round.get(round_number),
    )


def resolve_latest_publication_review_round_artifacts(
    project_root: Path,
    *,
    manuscript: Path | None = None,
    include_global_fallback_for_external: bool = False,
) -> PublicationReviewRoundArtifacts | None:
    """Return the newest staged review round without enforcing manuscript-path matching."""

    review_ledger_by_round, referee_decision_by_round = publication_review_round_path_maps(
        project_root,
        manuscript=manuscript,
        include_global_fallback_for_external=include_global_fallback_for_external,
    )
    round_number = latest_publication_round_number(review_ledger_by_round, referee_decision_by_round)
    if round_number is None:
        return None
    return publication_review_round_artifacts(
        round_number,
        review_ledger_by_round=review_ledger_by_round,
        referee_decision_by_round=referee_decision_by_round,
    )


def resolve_latest_publication_response_round_artifacts(
    project_root: Path,
    *,
    manuscript: Path | None = None,
    include_global_fallback_for_external: bool = False,
    include_review_roots_for_author_response: bool = False,
) -> PublicationResponseRoundArtifacts | None:
    """Return the newest paired-response round without assuming fresh review clearance exists."""

    author_response_by_round, referee_response_by_round = publication_response_round_path_maps(
        project_root,
        manuscript=manuscript,
        include_global_fallback_for_external=include_global_fallback_for_external,
        include_review_roots_for_author_response=include_review_roots_for_author_response,
    )
    round_number = latest_publication_round_number(author_response_by_round, referee_response_by_round)
    if round_number is None:
        return None
    return PublicationResponseRoundArtifacts(
        round_number=round_number,
        round_suffix=review_round_suffix(round_number),
        author_response=author_response_by_round.get(round_number),
        referee_response=referee_response_by_round.get(round_number),
    )
