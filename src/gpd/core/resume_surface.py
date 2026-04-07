"""Shared resume-surface normalization helpers.

The public resume surface is canonical-only: modern continuation fields stay at
the top level and legacy raw aliases are stripped before payloads leave the
backend. This module centralizes that projection so ``init_resume()``, CLI raw
output, and other public surfaces do not each reinvent resume normalization.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

__all__ = [
    "RESUME_SURFACE_SCHEMA_VERSION",
    "RESUME_COMPATIBILITY_ALIAS_FIELDS",
    "RESUME_CANDIDATE_KIND_BOUNDED_SEGMENT",
    "RESUME_CANDIDATE_KIND_CONTINUITY_HANDOFF",
    "RESUME_CANDIDATE_KIND_INTERRUPTED_AGENT",
    "RESUME_CANDIDATE_ORIGIN_CONTINUATION_BOUNDED_SEGMENT",
    "RESUME_CANDIDATE_ORIGIN_CONTINUATION_HANDOFF",
    "RESUME_CANDIDATE_ORIGIN_INTERRUPTED_AGENT_MARKER",
    "build_resume_candidate",
    "build_resume_segment_candidate",
    "build_resume_static_candidate",
    "canonicalize_resume_public_payload",
    "lookup_resume_surface_list",
    "lookup_resume_surface_mapping",
    "lookup_resume_surface_text",
    "lookup_resume_surface_value",
    "resume_candidate_kind",
    "resume_candidate_origin",
    "resume_candidate_kind_from_source",
    "resume_candidate_origin_from_source",
    "resume_origin_for_bounded_segment",
    "resume_origin_for_handoff",
    "resume_origin_for_interrupted_agent",
    "resume_payload_has_local_recovery_target",
]

RESUME_SURFACE_SCHEMA_VERSION = 1

RESUME_COMPATIBILITY_ALIAS_FIELDS: tuple[str, ...] = (
    "active_execution_segment",
    "current_execution",
    "current_execution_resume_file",
    "execution_resume_file",
    "execution_resume_file_source",
    "missing_session_resume_file",
    "recorded_session_resume_file",
    "resume_mode",
    "segment_candidates",
    "session_resume_file",
)

_RESUME_LEGACY_WRAPPER_KEYS: frozenset[str] = frozenset({"compat_resume_surface", "resume_surface"})

RESUME_CANDIDATE_KIND_BOUNDED_SEGMENT = "bounded_segment"
RESUME_CANDIDATE_KIND_CONTINUITY_HANDOFF = "continuity_handoff"
RESUME_CANDIDATE_KIND_INTERRUPTED_AGENT = "interrupted_agent"

RESUME_CANDIDATE_ORIGIN_CONTINUATION_BOUNDED_SEGMENT = "continuation.bounded_segment"
RESUME_CANDIDATE_ORIGIN_CONTINUATION_HANDOFF = "continuation.handoff"
RESUME_CANDIDATE_ORIGIN_INTERRUPTED_AGENT_MARKER = "interrupted_agent_marker"

_RESUME_CANDIDATE_SEGMENT_FIELDS: tuple[str, ...] = (
    "phase",
    "plan",
    "segment_id",
    "resume_file",
    "checkpoint_reason",
    "first_result_gate_pending",
    "pre_fanout_review_pending",
    "pre_fanout_review_cleared",
    "skeptical_requestioning_required",
    "skeptical_requestioning_summary",
    "weakest_unchecked_anchor",
    "disconfirming_observation",
    "transition_id",
    "last_result_id",
    "downstream_locked",
    "waiting_reason",
    "blocked_reason",
    "last_result_label",
    "updated_at",
)


def _lookup_resume_surface_field(
    payload: Mapping[str, object] | None,
    key: str,
    *,
    accept: Callable[[object], object | None],
) -> object | None:
    if isinstance(payload, Mapping) and key in payload:
        accepted = accept(payload[key])
        if accepted is not None:
            return accepted
    return None


def lookup_resume_surface_text(
    payload: Mapping[str, object] | None,
    key: str,
) -> str | None:
    """Return the first non-blank text value for one canonical field."""
    return _lookup_resume_surface_field(
        payload,
        key,
        accept=lambda value: value if isinstance(value, str) and value.strip() else None,
    )


def lookup_resume_surface_value(
    payload: Mapping[str, object] | None,
    key: str,
) -> object | None:
    """Return the first non-empty value for one canonical field."""
    return _lookup_resume_surface_field(
        payload,
        key,
        accept=lambda value: None
        if value is None or (isinstance(value, str) and not value.strip())
        else value,
    )


def lookup_resume_surface_mapping(
    payload: Mapping[str, object] | None,
    key: str,
) -> dict[str, object] | None:
    """Return the first mapping value for one canonical field."""
    result = _lookup_resume_surface_field(
        payload,
        key,
        accept=lambda value: dict(value) if isinstance(value, Mapping) else None,
    )
    return result if isinstance(result, dict) else None


def lookup_resume_surface_list(
    payload: Mapping[str, object] | None,
    key: str,
) -> list[object] | None:
    """Return the first list value for one canonical field."""
    result = _lookup_resume_surface_field(
        payload,
        key,
        accept=lambda value: list(value) if isinstance(value, list) else None,
    )
    return result if isinstance(result, list) else None


def build_resume_segment_candidate(
    segment: Mapping[str, object],
    *,
    source: str = "current_execution",
) -> dict[str, object]:
    """Return the raw segment candidate payload used by resume synthesis."""
    candidate = {
        "source": source,
        "status": segment.get("segment_status"),
    }
    for field in _RESUME_CANDIDATE_SEGMENT_FIELDS:
        candidate[field] = segment.get(field)
    return candidate


def build_resume_static_candidate(
    *,
    source: str,
    status: object,
    resume_file: str | None = None,
    agent_id: str | None = None,
    resumable: bool | None = None,
    advisory: bool | None = None,
) -> dict[str, object]:
    """Return the raw non-segment candidate payload used by resume synthesis."""
    candidate: dict[str, object] = {
        "source": source,
        "status": status,
    }
    if resume_file is not None:
        candidate["resume_file"] = resume_file
    if agent_id is not None:
        candidate["agent_id"] = agent_id
    if resumable is not None:
        candidate["resumable"] = resumable
    if advisory is not None:
        candidate["advisory"] = advisory
    return candidate


def build_resume_candidate(
    candidate: Mapping[str, object],
    *,
    kind: str,
    origin: str,
    resume_pointer: str | None = None,
) -> dict[str, object]:
    """Return the canonical candidate shape for public resume surfaces."""
    payload = dict(candidate)
    payload.pop("source", None)
    payload["kind"] = kind
    payload["origin"] = _canonical_resume_origin(origin)
    payload["resume_pointer"] = resume_pointer
    return payload


def _canonical_resume_origin(origin: str | None) -> str | None:
    normalized = (origin or "").strip()
    if not normalized:
        return None
    if normalized == "current_execution":
        return RESUME_CANDIDATE_ORIGIN_CONTINUATION_BOUNDED_SEGMENT
    if normalized == "session_resume_file":
        return RESUME_CANDIDATE_ORIGIN_CONTINUATION_HANDOFF
    return normalized


def resume_candidate_kind_from_source(source: str | None) -> str | None:
    """Map a raw resume source label to the canonical candidate kind."""
    normalized = (source or "").strip()
    if normalized == "current_execution":
        return RESUME_CANDIDATE_KIND_BOUNDED_SEGMENT
    if normalized == "session_resume_file":
        return RESUME_CANDIDATE_KIND_CONTINUITY_HANDOFF
    if normalized == "interrupted_agent":
        return RESUME_CANDIDATE_KIND_INTERRUPTED_AGENT
    return None


def resume_candidate_kind(candidate: Mapping[str, object]) -> str | None:
    """Return the canonical family for one resume candidate."""
    kind = candidate.get("kind")
    if isinstance(kind, str):
        normalized = kind.strip()
        if normalized in {"handoff", "continuity_handoff", "missing_handoff", "missing_continuity_handoff"}:
            return RESUME_CANDIDATE_KIND_CONTINUITY_HANDOFF
        if normalized in {
            RESUME_CANDIDATE_KIND_BOUNDED_SEGMENT,
            RESUME_CANDIDATE_KIND_INTERRUPTED_AGENT,
        }:
            return normalized

    origin = resume_candidate_origin(candidate)
    if origin == RESUME_CANDIDATE_ORIGIN_INTERRUPTED_AGENT_MARKER:
        return RESUME_CANDIDATE_KIND_INTERRUPTED_AGENT
    if origin in {
        RESUME_CANDIDATE_ORIGIN_CONTINUATION_BOUNDED_SEGMENT,
    }:
        return RESUME_CANDIDATE_KIND_BOUNDED_SEGMENT
    if origin in {
        RESUME_CANDIDATE_ORIGIN_CONTINUATION_HANDOFF,
    }:
        return RESUME_CANDIDATE_KIND_CONTINUITY_HANDOFF

    source = candidate.get("source")
    return resume_candidate_kind_from_source(str(source).strip() if isinstance(source, str) else None)


def resume_origin_for_bounded_segment(
) -> str:
    """Return the canonical origin for a bounded execution candidate."""
    return RESUME_CANDIDATE_ORIGIN_CONTINUATION_BOUNDED_SEGMENT


def resume_origin_for_handoff() -> str:
    """Return the canonical origin for a recorded handoff candidate."""
    return RESUME_CANDIDATE_ORIGIN_CONTINUATION_HANDOFF


def resume_origin_for_interrupted_agent() -> str:
    """Return the canonical origin for an interrupted-agent candidate."""
    return RESUME_CANDIDATE_ORIGIN_INTERRUPTED_AGENT_MARKER


def resume_candidate_origin_from_source(
    source: str | None,
) -> str | None:
    """Map a raw candidate source label to a canonical origin string."""
    normalized = (source or "").strip()
    if normalized == "current_execution":
        return RESUME_CANDIDATE_ORIGIN_CONTINUATION_BOUNDED_SEGMENT
    if normalized == "session_resume_file":
        return RESUME_CANDIDATE_ORIGIN_CONTINUATION_HANDOFF
    if normalized == "interrupted_agent":
        return resume_origin_for_interrupted_agent()
    return None


def resume_candidate_origin(candidate: Mapping[str, object]) -> str | None:
    """Return the canonical origin for one resume candidate."""
    origin = candidate.get("origin")
    if isinstance(origin, str) and origin.strip():
        return _canonical_resume_origin(origin)
    source = candidate.get("source")
    return resume_candidate_origin_from_source(str(source).strip() if isinstance(source, str) else None)


def _resume_candidate_exposes_local_target(candidate: Mapping[str, object]) -> bool:
    kind = resume_candidate_kind(candidate)
    status = str(candidate.get("status") or "").strip()
    if status == "missing":
        return False
    if kind == RESUME_CANDIDATE_KIND_INTERRUPTED_AGENT:
        agent_id = candidate.get("agent_id")
        return isinstance(agent_id, str) and bool(agent_id.strip())
    if kind not in {
        RESUME_CANDIDATE_KIND_BOUNDED_SEGMENT,
        RESUME_CANDIDATE_KIND_CONTINUITY_HANDOFF,
    }:
        return False
    resume_file = candidate.get("resume_file")
    return isinstance(resume_file, str) and bool(resume_file.strip())


def resume_payload_has_local_recovery_target(payload: Mapping[str, object] | None) -> bool:
    """Return whether one resume payload already exposes a local recovery target."""
    if not isinstance(payload, Mapping):
        return False
    active_resume_kind = lookup_resume_surface_text(
        payload,
        "active_resume_kind",
    )
    active_resume_pointer = lookup_resume_surface_text(
        payload,
        "active_resume_pointer",
    )
    if (
        active_resume_kind
        in {
            RESUME_CANDIDATE_KIND_BOUNDED_SEGMENT,
            RESUME_CANDIDATE_KIND_CONTINUITY_HANDOFF,
            RESUME_CANDIDATE_KIND_INTERRUPTED_AGENT,
        }
        and active_resume_pointer is not None
    ):
        return True
    if lookup_resume_surface_text(
        payload,
        "continuity_handoff_file",
    ) is not None:
        return True

    candidates = lookup_resume_surface_list(payload, "resume_candidates")
    if not isinstance(candidates, list):
        return False
    return any(
        isinstance(candidate, Mapping) and _resume_candidate_exposes_local_target(candidate)
        for candidate in candidates
    )

def _strip_top_level_resume_surface_compatibility_keys(
    payload: Mapping[str, object],
    *,
    compat_fields: frozenset[str],
) -> dict[str, object]:
    """Drop only top-level legacy aliases from one public resume payload."""

    cleaned: dict[str, object] = {}
    for key, value in payload.items():
        if key in compat_fields or key in _RESUME_LEGACY_WRAPPER_KEYS:
            continue
        cleaned[key] = value
    return cleaned


def canonicalize_resume_public_payload(
    payload: Mapping[str, object],
    *,
    compat_fields: Sequence[str] = RESUME_COMPATIBILITY_ALIAS_FIELDS,
) -> dict[str, object]:
    """Strip legacy resume aliases from one public payload."""
    return _strip_top_level_resume_surface_compatibility_keys(
        dict(payload),
        compat_fields=frozenset(compat_fields),
    )
