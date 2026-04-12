"""Shared resume candidate filtering helpers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from gpd.core.resume_surface import resume_candidate_kind, resume_candidate_origin

__all__ = (
    "candidate_text",
    "find_resume_candidate",
    "has_resume_candidate",
)


def _normalize_text(value: object | None) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def candidate_text(candidate: Mapping[str, object], field: str) -> str | None:
    if not isinstance(candidate, Mapping):
        return None
    return _normalize_text(candidate.get(field))


def _iter_candidates(candidates: object) -> Sequence[Mapping[str, object]]:
    if not isinstance(candidates, Sequence) or isinstance(candidates, (str, bytes)):
        return []
    return [item for item in candidates if isinstance(item, Mapping)]


def _normalize_expected(value: str | None) -> str | None:
    return _normalize_text(value)


def _matches_candidate(
    candidate: Mapping[str, object],
    *,
    source: str | None = None,
    kind: str | None = None,
    origin: str | None = None,
    status: str | None = None,
    resume_file: str | None = None,
    resume_pointer: str | None = None,
    agent_id: str | None = None,
) -> bool:
    expected_source = _normalize_expected(source)
    if expected_source is not None and candidate_text(candidate, "source") != expected_source:
        return False

    expected_kind = _normalize_expected(kind)
    if expected_kind is not None and resume_candidate_kind(candidate) != expected_kind:
        return False

    expected_origin = _normalize_expected(origin)
    if expected_origin is not None and resume_candidate_origin(candidate) != expected_origin:
        return False

    expected_status = _normalize_expected(status)
    if expected_status is not None and candidate_text(candidate, "status") != expected_status:
        return False

    expected_resume_file = _normalize_expected(resume_file)
    if expected_resume_file is not None and candidate_text(candidate, "resume_file") != expected_resume_file:
        return False

    expected_resume_pointer = _normalize_expected(resume_pointer)
    if expected_resume_pointer is not None and candidate_text(candidate, "resume_pointer") != expected_resume_pointer:
        return False

    expected_agent_id = _normalize_expected(agent_id)
    if expected_agent_id is not None and candidate_text(candidate, "agent_id") != expected_agent_id:
        return False

    return True


def find_resume_candidate(
    candidates: object,
    *,
    source: str | None = None,
    kind: str | None = None,
    origin: str | None = None,
    status: str | None = None,
    resume_file: str | None = None,
    resume_pointer: str | None = None,
    agent_id: str | None = None,
) -> Mapping[str, object] | None:
    for candidate in _iter_candidates(candidates):
        if _matches_candidate(
            candidate,
            source=source,
            kind=kind,
            origin=origin,
            status=status,
            resume_file=resume_file,
            resume_pointer=resume_pointer,
            agent_id=agent_id,
        ):
            return candidate
    return None


def has_resume_candidate(
    candidates: object,
    *,
    source: str | None = None,
    kind: str | None = None,
    origin: str | None = None,
    status: str | None = None,
    resume_file: str | None = None,
    resume_pointer: str | None = None,
    agent_id: str | None = None,
) -> bool:
    return find_resume_candidate(
        candidates,
        source=source,
        kind=kind,
        origin=origin,
        status=status,
        resume_file=resume_file,
        resume_pointer=resume_pointer,
        agent_id=agent_id,
    ) is not None
