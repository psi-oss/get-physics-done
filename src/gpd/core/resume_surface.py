"""Shared resume-surface normalization helpers.

The canonical public resume surface keeps modern continuation fields at the
top level and groups legacy raw aliases under ``compat_resume_surface``. This
module centralizes that projection so ``init_resume()``, CLI raw output, and
other public surfaces do not each reinvent compatibility handling. The compat
schema inventory lives here as the single source of truth for alias names and
wrapper aliases.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

__all__ = [
    "RESUME_COMPATIBILITY_ALIAS_FIELDS",
    "RESUME_COMPATIBILITY_SCHEMA",
    "RESUME_COMPATIBILITY_NESTED_SURFACE_ALIASES",
    "RESUME_COMPATIBILITY_WRAPPER_ALIASES",
    "RESUME_COMPATIBILITY_ALIAS_KEYS",
    "RESUME_CANDIDATE_KIND_BOUNDED_SEGMENT",
    "RESUME_CANDIDATE_KIND_CONTINUITY_HANDOFF",
    "RESUME_CANDIDATE_KIND_INTERRUPTED_AGENT",
    "RESUME_CANDIDATE_ORIGIN_COMPAT_CURRENT_EXECUTION",
    "RESUME_CANDIDATE_ORIGIN_COMPAT_SESSION_RESUME_FILE",
    "RESUME_CANDIDATE_ORIGIN_CONTINUATION_BOUNDED_SEGMENT",
    "RESUME_CANDIDATE_ORIGIN_CONTINUATION_HANDOFF",
    "RESUME_CANDIDATE_ORIGIN_INTERRUPTED_AGENT_MARKER",
    "build_resume_compat_surface",
    "build_resume_candidate",
    "build_resume_segment_candidate",
    "build_resume_static_candidate",
    "canonicalize_resume_public_payload",
    "canonicalize_resume_candidate",
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
    "resume_source_from_origin",
    "resume_payload_has_local_target",
    "resume_payload_has_local_recovery_target",
    "resolve_resume_compat_surface",
]


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

RESUME_COMPATIBILITY_WRAPPER_ALIASES: tuple[str, ...] = (
    "compat_resume_surface",
    "legacy_resume_surface",
    "compatibility_resume_surface",
)

RESUME_COMPATIBILITY_NESTED_SURFACE_ALIASES: tuple[str, ...] = (
    "resume_surface",
    "resume_surface_compat",
)

RESUME_COMPATIBILITY_SCHEMA: dict[str, tuple[str, ...] | str] = {
    "surface_key": "compat_resume_surface",
    "alias_fields": RESUME_COMPATIBILITY_ALIAS_FIELDS,
    "wrapper_aliases": RESUME_COMPATIBILITY_WRAPPER_ALIASES,
    "nested_surface_aliases": RESUME_COMPATIBILITY_NESTED_SURFACE_ALIASES,
}

# Backward-compatible alias for callers that still import the older constant name.
RESUME_COMPATIBILITY_ALIAS_KEYS: tuple[str, ...] = RESUME_COMPATIBILITY_ALIAS_FIELDS

RESUME_CANDIDATE_KIND_BOUNDED_SEGMENT = "bounded_segment"
RESUME_CANDIDATE_KIND_CONTINUITY_HANDOFF = "continuity_handoff"
RESUME_CANDIDATE_KIND_INTERRUPTED_AGENT = "interrupted_agent"

RESUME_CANDIDATE_ORIGIN_CONTINUATION_BOUNDED_SEGMENT = "continuation.bounded_segment"
RESUME_CANDIDATE_ORIGIN_CONTINUATION_HANDOFF = "continuation.handoff"
RESUME_CANDIDATE_ORIGIN_COMPAT_CURRENT_EXECUTION = "compat.current_execution"
RESUME_CANDIDATE_ORIGIN_COMPAT_SESSION_RESUME_FILE = "compat.session_resume_file"
RESUME_CANDIDATE_ORIGIN_INTERRUPTED_AGENT_MARKER = "interrupted_agent_marker"

_RESUME_CANDIDATE_ORIGIN_TO_COMPAT_SOURCE: dict[str, str] = {
    RESUME_CANDIDATE_ORIGIN_COMPAT_CURRENT_EXECUTION: "current_execution",
    RESUME_CANDIDATE_ORIGIN_COMPAT_SESSION_RESUME_FILE: "session_resume_file",
    RESUME_CANDIDATE_ORIGIN_INTERRUPTED_AGENT_MARKER: "interrupted_agent",
}

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


def _resolve_resume_surface_mapping(
    source: Mapping[str, object],
    *,
    aliases: Sequence[str],
) -> Mapping[str, object] | None:
    for key in aliases:
        value = source.get(key)
        if isinstance(value, Mapping):
            return value
    return None


def resolve_resume_compat_surface(
    *sources: Mapping[str, object] | None,
    fields: Sequence[str] = RESUME_COMPATIBILITY_ALIAS_FIELDS,
    wrapper_aliases: Sequence[str] = RESUME_COMPATIBILITY_WRAPPER_ALIASES,
    nested_surface_aliases: Sequence[str] = RESUME_COMPATIBILITY_NESTED_SURFACE_ALIASES,
) -> dict[str, object] | None:
    """Return the nested compatibility resume block for one payload."""
    if nested_surface_aliases:
        for source in sources:
            if not isinstance(source, Mapping):
                continue
            direct_surface = _resolve_resume_surface_mapping(
                source,
                aliases=(*wrapper_aliases, *nested_surface_aliases),
            )
            if isinstance(direct_surface, Mapping) and any(field in direct_surface for field in fields):
                return dict(direct_surface)

        for source in sources:
            if not isinstance(source, Mapping):
                continue
            for value in source.values():
                if not isinstance(value, Mapping):
                    continue
                nested_resume_surface = _resolve_resume_surface_mapping(
                    value,
                    aliases=nested_surface_aliases,
                )
                if isinstance(nested_resume_surface, Mapping) and any(field in nested_resume_surface for field in fields):
                    return dict(nested_resume_surface)
                if any(field in value for field in fields):
                    return dict(value)

    compat: dict[str, object] = dict.fromkeys(fields)
    found_alias_data = False

    for source in sources:
        if not isinstance(source, Mapping):
            continue
        value = _resolve_resume_surface_mapping(
            source,
            aliases=(*wrapper_aliases, *nested_surface_aliases),
        )
        if isinstance(value, Mapping):
            nested_alias_data = False
            for field in fields:
                if field in value:
                    compat[field] = value.get(field)
                    nested_alias_data = True
            if nested_alias_data:
                found_alias_data = True
        if any(key in source for key in fields):
            found_alias_data = True

    for key in fields:
        for source in sources:
            if not isinstance(source, Mapping) or key not in source:
                continue
            compat[key] = source.get(key)
            break

    return compat if found_alias_data else None


def build_resume_compat_surface(
    *sources: Mapping[str, object] | None,
    fields: Sequence[str] = RESUME_COMPATIBILITY_ALIAS_FIELDS,
) -> dict[str, object] | None:
    """Return the nested compatibility resume block for one payload."""
    return resolve_resume_compat_surface(
        *sources,
        fields=fields,
        wrapper_aliases=RESUME_COMPATIBILITY_WRAPPER_ALIASES,
        nested_surface_aliases=(),
    )


def lookup_resume_surface_text(
    payload: Mapping[str, object] | None,
    key: str,
    *,
    compat_surface: Mapping[str, object] | None = None,
    compat_key: str | None = None,
    compat_keys: Sequence[str] = (),
    prefer_compat: bool = False,
) -> str | None:
    """Return the first non-blank text value for a canonical or compat field."""
    lookup_order = ((compat_surface, (compat_key, *compat_keys)), (payload, (key,))) if prefer_compat else (
        (payload, (key,)),
        (compat_surface, (compat_key, *compat_keys)),
    )
    for source, source_keys in lookup_order:
        if not isinstance(source, Mapping):
            continue
        for source_key in source_keys:
            if source_key is None:
                continue
            value = source.get(source_key)
            if isinstance(value, str) and value.strip():
                return value
    return None


def lookup_resume_surface_value(
    payload: Mapping[str, object] | None,
    key: str,
    *,
    compat_surface: Mapping[str, object] | None = None,
    compat_key: str | None = None,
    compat_keys: Sequence[str] = (),
    prefer_compat: bool = False,
) -> object | None:
    """Return the first non-empty canonical or compat value for one field."""
    lookup_order = ((compat_surface, (compat_key, *compat_keys)), (payload, (key,))) if prefer_compat else (
        (payload, (key,)),
        (compat_surface, (compat_key, *compat_keys)),
    )
    for source, source_keys in lookup_order:
        if not isinstance(source, Mapping):
            continue
        for source_key in source_keys:
            if source_key is None or source_key not in source:
                continue
            value = source[source_key]
            if value is None:
                continue
            if isinstance(value, str) and not value.strip():
                continue
            return value
    return None


def lookup_resume_surface_mapping(
    payload: Mapping[str, object] | None,
    key: str,
    *,
    compat_surface: Mapping[str, object] | None = None,
    compat_key: str | None = None,
    compat_keys: Sequence[str] = (),
    prefer_compat: bool = False,
) -> dict[str, object] | None:
    """Return the first mapping value for a canonical or compat field."""
    lookup_order = ((compat_surface, (compat_key, *compat_keys)), (payload, (key,))) if prefer_compat else (
        (payload, (key,)),
        (compat_surface, (compat_key, *compat_keys)),
    )
    for source, source_keys in lookup_order:
        if not isinstance(source, Mapping):
            continue
        for source_key in source_keys:
            if source_key is None:
                continue
            value = source.get(source_key)
            if isinstance(value, Mapping):
                return dict(value)
    return None


def lookup_resume_surface_list(
    payload: Mapping[str, object] | None,
    key: str,
    *,
    compat_surface: Mapping[str, object] | None = None,
    compat_key: str | None = None,
    compat_keys: Sequence[str] = (),
    prefer_compat: bool = False,
) -> list[object] | None:
    """Return the first list value for a canonical or compat field."""
    lookup_order = ((compat_surface, (compat_key, *compat_keys)), (payload, (key,))) if prefer_compat else (
        (payload, (key,)),
        (compat_surface, (compat_key, *compat_keys)),
    )
    for source, source_keys in lookup_order:
        if not isinstance(source, Mapping):
            continue
        for source_key in source_keys:
            if source_key is None:
                continue
            value = source.get(source_key)
            if isinstance(value, list):
                return list(value)
    return None


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
    payload["origin"] = origin
    payload["resume_pointer"] = resume_pointer
    return payload


def canonicalize_resume_candidate(
    candidate: Mapping[str, object],
    *,
    kind: str,
    origin: str,
    resume_pointer: str | None = None,
) -> dict[str, object]:
    """Alias for :func:`build_resume_candidate` for semantically clearer call sites."""
    return build_resume_candidate(
        candidate,
        kind=kind,
        origin=origin,
        resume_pointer=resume_pointer,
    )


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
        RESUME_CANDIDATE_ORIGIN_COMPAT_CURRENT_EXECUTION,
    }:
        return RESUME_CANDIDATE_KIND_BOUNDED_SEGMENT
    if origin in {
        RESUME_CANDIDATE_ORIGIN_CONTINUATION_HANDOFF,
        RESUME_CANDIDATE_ORIGIN_COMPAT_SESSION_RESUME_FILE,
    }:
        return RESUME_CANDIDATE_KIND_CONTINUITY_HANDOFF

    source = candidate.get("source")
    return resume_candidate_kind_from_source(str(source).strip() if isinstance(source, str) else None)


def resume_origin_for_bounded_segment(
    *,
    recorded_by: str | None = None,
    source: str | None = None,
) -> str:
    """Return the canonical origin for a bounded execution candidate."""
    if (recorded_by or "").strip() == "legacy_current_execution":
        return RESUME_CANDIDATE_ORIGIN_COMPAT_CURRENT_EXECUTION
    if (source or "").strip() == "legacy":
        return RESUME_CANDIDATE_ORIGIN_COMPAT_CURRENT_EXECUTION
    return RESUME_CANDIDATE_ORIGIN_CONTINUATION_BOUNDED_SEGMENT


def resume_origin_for_handoff(
    *,
    recorded_by: str | None = None,
    source: str | None = None,
) -> str:
    """Return the canonical origin for a recorded handoff candidate."""
    if (recorded_by or "").strip() == "legacy_session":
        return RESUME_CANDIDATE_ORIGIN_COMPAT_SESSION_RESUME_FILE
    if (source or "").strip() == "legacy":
        return RESUME_CANDIDATE_ORIGIN_COMPAT_SESSION_RESUME_FILE
    return RESUME_CANDIDATE_ORIGIN_CONTINUATION_HANDOFF


def resume_origin_for_interrupted_agent() -> str:
    """Return the canonical origin for an interrupted-agent candidate."""
    return RESUME_CANDIDATE_ORIGIN_INTERRUPTED_AGENT_MARKER


def resume_candidate_origin_from_source(
    source: str | None,
    *,
    recorded_by: str | None = None,
) -> str | None:
    """Map a raw candidate source label to a canonical origin string."""
    normalized = (source or "").strip()
    if normalized == "current_execution":
        return RESUME_CANDIDATE_ORIGIN_COMPAT_CURRENT_EXECUTION
    if normalized == "session_resume_file":
        return RESUME_CANDIDATE_ORIGIN_COMPAT_SESSION_RESUME_FILE
    if normalized == "interrupted_agent":
        return resume_origin_for_interrupted_agent()
    return None


def resume_candidate_origin(candidate: Mapping[str, object]) -> str | None:
    """Return the canonical origin for one resume candidate."""
    origin = candidate.get("origin")
    if isinstance(origin, str) and origin.strip():
        return origin.strip()
    source = candidate.get("source")
    return resume_candidate_origin_from_source(
        str(source).strip() if isinstance(source, str) else None,
        recorded_by=candidate.get("recorded_by") if isinstance(candidate.get("recorded_by"), str) else None,
    )


def resume_source_from_origin(origin: str | None) -> str | None:
    """Return the compat source label for one canonical candidate origin."""
    normalized = (origin or "").strip()
    if not normalized:
        return None
    return _RESUME_CANDIDATE_ORIGIN_TO_COMPAT_SOURCE.get(normalized)


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


def resume_payload_has_local_recovery_target(
    payload: Mapping[str, object] | None,
    *,
    compat_surface: Mapping[str, object] | None = None,
) -> bool:
    """Return whether one resume payload already exposes a local recovery target."""
    if not isinstance(payload, Mapping):
        return False
    compat_surface = compat_surface if isinstance(compat_surface, Mapping) else resolve_resume_compat_surface(payload)

    if bool(
        lookup_resume_surface_value(
            payload,
            "execution_resumable",
            compat_surface=compat_surface,
            prefer_compat=False,
        )
    ):
        return True
    if bool(
        lookup_resume_surface_value(
            payload,
            "has_interrupted_agent",
            compat_surface=compat_surface,
            prefer_compat=False,
        )
    ):
        return True

    has_continuity_handoff = bool(
        lookup_resume_surface_value(
            payload,
            "has_continuity_handoff",
            compat_surface=compat_surface,
            prefer_compat=False,
        )
    )
    missing_continuity_handoff = bool(
        lookup_resume_surface_value(
            payload,
            "missing_continuity_handoff",
            compat_surface=compat_surface,
            prefer_compat=False,
        )
    )
    if lookup_resume_surface_text(
        payload,
        "missing_continuity_handoff_file",
        compat_surface=compat_surface,
        compat_key="missing_session_resume_file",
    ) is not None:
        missing_continuity_handoff = True
    if has_continuity_handoff and not missing_continuity_handoff:
        return True

    active_resume_kind = lookup_resume_surface_text(
        payload,
        "active_resume_kind",
        compat_surface=compat_surface,
    )
    active_resume_pointer = lookup_resume_surface_text(
        payload,
        "active_resume_pointer",
        compat_surface=compat_surface,
        compat_key="execution_resume_file",
    )
    if (
        active_resume_kind in {RESUME_CANDIDATE_KIND_BOUNDED_SEGMENT, RESUME_CANDIDATE_KIND_INTERRUPTED_AGENT}
        and active_resume_pointer is not None
    ):
        return True
    if lookup_resume_surface_text(
        payload,
        "continuity_handoff_file",
        compat_surface=compat_surface,
        compat_key="session_resume_file",
    ) is not None:
        return True

    candidates = lookup_resume_surface_list(
        payload,
        "resume_candidates",
        compat_surface=compat_surface,
        compat_key="segment_candidates",
    )
    if not isinstance(candidates, list):
        return False
    return any(
        isinstance(candidate, Mapping) and _resume_candidate_exposes_local_target(candidate)
        for candidate in candidates
    )


def resume_payload_has_local_target(
    payload: Mapping[str, object] | None,
    *,
    compat_surface: Mapping[str, object] | None = None,
) -> bool:
    """Backward-compatible alias for the shared local-target predicate."""
    return resume_payload_has_local_recovery_target(
        payload,
        compat_surface=compat_surface,
    )


def canonicalize_resume_public_payload(
    payload: Mapping[str, object],
    *,
    compat_fields: Sequence[str] = RESUME_COMPATIBILITY_ALIAS_FIELDS,
) -> dict[str, object]:
    """Group legacy resume aliases under ``compat_resume_surface`` only."""
    canonical = dict(payload)
    nested_sources = [
        value
        for key in RESUME_COMPATIBILITY_NESTED_SURFACE_ALIASES
        if isinstance((value := canonical.get(key)), Mapping)
    ]
    compat = build_resume_compat_surface(canonical, *nested_sources, fields=compat_fields)

    for key in RESUME_COMPATIBILITY_ALIAS_FIELDS:
        canonical.pop(key, None)
    for key in RESUME_COMPATIBILITY_WRAPPER_ALIASES:
        canonical.pop(key, None)
    for key in RESUME_COMPATIBILITY_NESTED_SURFACE_ALIASES:
        canonical.pop(key, None)

    if compat is not None:
        canonical["compat_resume_surface"] = compat
    else:
        canonical.pop("compat_resume_surface", None)

    return canonical
