"""Planner artifact freshness and ``gpd_return.files_written`` reconciliation helpers.

The planner wrappers need one shared place to decide whether a returned plan
artifact is actually fresh. The contract here is intentionally small and
fail-closed:

- expected artifact paths must exist on disk
- the returned ``files_written`` set must name exactly those artifacts
- any mismatch is reported as stale or missing rather than being inferred
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from gpd.core.path_labels import normalize_posix_path_label

__all__ = [
    "PlannerArtifactFreshnessResult",
    "resolve_planner_artifact_freshness",
]

PlannerArtifactFreshnessState = Literal["fresh", "stale", "missing", "invalid"]


@dataclass(frozen=True, slots=True)
class PlannerArtifactFreshnessResult:
    """Outcome of reconciling expected planner artifacts with ``files_written``."""

    passed: bool
    state: PlannerArtifactFreshnessState
    detail: str
    expected_paths: tuple[Path, ...] = ()
    reported_paths: tuple[Path, ...] = ()
    missing_on_disk: tuple[Path, ...] = ()
    missing_from_return: tuple[Path, ...] = ()
    unexpected_reported_paths: tuple[Path, ...] = ()


def resolve_planner_artifact_freshness(
    cwd: Path,
    expected_artifacts: Sequence[Path | str],
    files_written: Sequence[str],
) -> PlannerArtifactFreshnessResult:
    """Check that expected planner artifacts exist and are named in ``files_written``.

    The comparison is normalized against ``cwd`` and is exact for the expected
    artifact set. Extra return paths are treated as stale rather than being
    silently ignored.
    """

    resolved_cwd = cwd.expanduser().resolve(strict=False)
    expected_paths = tuple(
        dict.fromkeys(
            path
            for path in (_resolve_path(resolved_cwd, artifact) for artifact in expected_artifacts)
            if path is not None
        )
    )
    reported_paths = tuple(
        dict.fromkeys(
            path for path in (_resolve_path(resolved_cwd, artifact) for artifact in files_written) if path is not None
        )
    )

    if not expected_paths:
        return PlannerArtifactFreshnessResult(
            passed=False,
            state="invalid",
            detail="planner artifact freshness requires at least one expected artifact path",
            reported_paths=reported_paths,
        )

    expected_set = set(expected_paths)
    reported_set = set(reported_paths)
    missing_on_disk = tuple(path for path in expected_paths if not path.exists() or not path.is_file())
    missing_from_return = tuple(path for path in expected_paths if path not in reported_set)
    unexpected_reported_paths = tuple(path for path in reported_paths if path not in expected_set)

    if missing_on_disk:
        return PlannerArtifactFreshnessResult(
            passed=False,
            state="missing",
            detail=_build_detail(
                "expected planner artifact(s) are missing on disk",
                resolved_cwd,
                missing_on_disk=missing_on_disk,
                missing_from_return=missing_from_return,
                unexpected_reported_paths=unexpected_reported_paths,
            ),
            expected_paths=expected_paths,
            reported_paths=reported_paths,
            missing_on_disk=missing_on_disk,
            missing_from_return=missing_from_return,
            unexpected_reported_paths=unexpected_reported_paths,
        )

    if missing_from_return or unexpected_reported_paths:
        return PlannerArtifactFreshnessResult(
            passed=False,
            state="stale",
            detail=_build_detail(
                "planner artifact set does not match gpd_return.files_written",
                resolved_cwd,
                missing_from_return=missing_from_return,
                unexpected_reported_paths=unexpected_reported_paths,
            ),
            expected_paths=expected_paths,
            reported_paths=reported_paths,
            missing_from_return=missing_from_return,
            unexpected_reported_paths=unexpected_reported_paths,
        )

    return PlannerArtifactFreshnessResult(
        passed=True,
        state="fresh",
        detail=_build_detail(
            "planner artifact(s) are present on disk and reconciled with gpd_return.files_written",
            resolved_cwd,
            missing_from_return=(),
            unexpected_reported_paths=(),
        ),
        expected_paths=expected_paths,
        reported_paths=reported_paths,
    )


def _resolve_path(cwd: Path, value: Path | str) -> Path | None:
    if isinstance(value, Path):
        candidate = value.expanduser()
    elif isinstance(value, str):
        normalized = _normalize_path_text(value)
        if not normalized:
            return None
        candidate = Path(normalized).expanduser()
    else:
        return None

    if not candidate.is_absolute():
        candidate = cwd / candidate
    return candidate.resolve(strict=False)


def _normalize_path_text(value: str) -> str:
    return normalize_posix_path_label(value)


def _display_path(cwd: Path, path: Path) -> str:
    try:
        return path.relative_to(cwd).as_posix()
    except ValueError:
        return path.as_posix()


def _build_detail(
    prefix: str,
    cwd: Path,
    *,
    missing_on_disk: Sequence[Path] = (),
    missing_from_return: Sequence[Path] = (),
    unexpected_reported_paths: Sequence[Path] = (),
) -> str:
    parts: list[str] = [prefix]
    if missing_on_disk:
        parts.append(
            "missing on disk: " + ", ".join(_display_path(cwd, path) for path in missing_on_disk[:3])
        )
    if missing_from_return:
        parts.append(
            "missing from gpd_return.files_written: "
            + ", ".join(_display_path(cwd, path) for path in missing_from_return[:3])
        )
    if unexpected_reported_paths:
        parts.append(
            "unexpected files_written entries: "
            + ", ".join(_display_path(cwd, path) for path in unexpected_reported_paths[:3])
        )
    return "; ".join(parts)
