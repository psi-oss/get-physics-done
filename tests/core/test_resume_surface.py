from __future__ import annotations

from copy import deepcopy

import pytest

from gpd.core.resume_surface import (
    RESUME_COMPATIBILITY_ALIAS_KEYS,
    build_resume_candidate,
    build_resume_compat_surface,
    build_resume_segment_candidate,
    canonicalize_resume_public_payload,
    lookup_resume_surface_list,
    lookup_resume_surface_mapping,
    lookup_resume_surface_text,
    resolve_resume_compat_surface,
    resume_candidate_kind,
    resume_candidate_origin,
    resume_payload_has_local_target,
    resume_source_from_origin,
)


def test_build_resume_compat_surface_returns_none_without_compat_aliases() -> None:
    payload = {
        "active_resume_kind": "bounded_segment",
        "active_resume_origin": "compat.current_execution",
        "active_resume_pointer": "GPD/phases/03/.continue-here.md",
    }

    assert build_resume_compat_surface(payload) is None


def test_build_resume_compat_surface_extracts_top_level_legacy_fields() -> None:
    payload = {
        "current_execution": {"resume_file": "GPD/phases/03/.continue-here.md"},
        "active_execution_segment": {"segment_id": "seg-1"},
        "current_execution_resume_file": "GPD/phases/03/.continue-here.md",
        "execution_resume_file": "GPD/phases/03/.continue-here.md",
        "execution_resume_file_source": "current_execution",
        "missing_session_resume_file": "GPD/phases/03/alternate.md",
        "recorded_session_resume_file": "GPD/phases/03/alternate.md",
        "resume_mode": "bounded_segment",
        "segment_candidates": [{"source": "current_execution"}],
        "session_resume_file": "GPD/phases/03/alternate.md",
    }

    compat = build_resume_compat_surface(payload)

    assert compat is not None
    assert set(compat) == set(RESUME_COMPATIBILITY_ALIAS_KEYS)
    assert compat["current_execution"] == {"resume_file": "GPD/phases/03/.continue-here.md"}
    assert compat["active_execution_segment"] == {"segment_id": "seg-1"}
    assert compat["execution_resume_file"] == "GPD/phases/03/.continue-here.md"
    assert compat["execution_resume_file_source"] == "current_execution"
    assert compat["missing_session_resume_file"] == "GPD/phases/03/alternate.md"
    assert compat["recorded_session_resume_file"] == "GPD/phases/03/alternate.md"
    assert compat["resume_mode"] == "bounded_segment"
    assert compat["segment_candidates"] == [{"source": "current_execution"}]
    assert compat["session_resume_file"] == "GPD/phases/03/alternate.md"


@pytest.mark.parametrize(
    "wrapper_key",
    ["compat_resume_surface", "legacy_resume_surface", "compatibility_resume_surface"],
)
def test_build_resume_compat_surface_extracts_wrapper_aliases(wrapper_key: str) -> None:
    payload = {
        wrapper_key: {
            "execution_resume_file": "GPD/phases/04/.continue-here.md",
            "execution_resume_file_source": "session_resume_file",
            "resume_mode": "continuity_handoff",
            "segment_candidates": [{"source": "session_resume_file", "status": "handoff"}],
            "session_resume_file": "GPD/phases/04/.continue-here.md",
        }
    }

    compat = build_resume_compat_surface(payload)

    assert compat is not None
    assert compat["execution_resume_file"] == "GPD/phases/04/.continue-here.md"
    assert compat["execution_resume_file_source"] == "session_resume_file"
    assert compat["resume_mode"] == "continuity_handoff"
    assert compat["segment_candidates"] == [{"source": "session_resume_file", "status": "handoff"}]
    assert compat["session_resume_file"] == "GPD/phases/04/.continue-here.md"


def test_build_resume_compat_surface_merges_sources_with_explicit_precedence() -> None:
    payload_one = {
        "compat_resume_surface": {
            "execution_resume_file": "GPD/phases/01/.continue-here.md",
            "session_resume_file": "GPD/phases/01/legacy.md",
        },
    }
    payload_two = {
        "compatibility_resume_surface": {
            "session_resume_file": "GPD/phases/02/legacy.md",
            "execution_resume_file_source": "session_resume_file",
        }
    }
    payload_three = {
        "legacy_resume_surface": {
            "recorded_session_resume_file": "GPD/phases/03/legacy.md",
            "session_resume_file": "GPD/phases/03/legacy.md",
        },
        "execution_resume_file": "GPD/phases/03/.continue-here.md",
        "resume_mode": "continuity_handoff",
    }

    compat = build_resume_compat_surface(payload_one, payload_two, payload_three)

    assert compat is not None
    assert compat["execution_resume_file"] == "GPD/phases/03/.continue-here.md"
    assert compat["execution_resume_file_source"] == "session_resume_file"
    assert compat["resume_mode"] == "continuity_handoff"
    assert compat["recorded_session_resume_file"] == "GPD/phases/03/legacy.md"
    assert compat["session_resume_file"] == "GPD/phases/03/legacy.md"


def test_resolve_resume_compat_surface_discovers_nested_resume_surface_wrapper() -> None:
    payload = {
        "recovery": {
            "resume_surface": {
                "execution_resume_file": "GPD/phases/05/.continue-here.md",
                "execution_resume_file_source": "current_execution",
                "segment_candidates": [{"source": "current_execution", "status": "paused"}],
            }
        }
    }

    compat = resolve_resume_compat_surface(payload)

    assert compat is not None
    assert compat["execution_resume_file"] == "GPD/phases/05/.continue-here.md"
    assert compat["execution_resume_file_source"] == "current_execution"
    assert compat["segment_candidates"] == [{"source": "current_execution", "status": "paused"}]


def test_lookup_resume_surface_helpers_respect_canonical_and_compat_precedence() -> None:
    payload = {
        "active_resume_pointer": "GPD/phases/07/.continue-here.md",
        "active_bounded_segment": {"segment_id": "seg-canonical"},
        "resume_candidates": [{"kind": "bounded_segment"}],
    }
    compat = {
        "execution_resume_file": "GPD/phases/07/legacy.md",
        "current_execution": {"segment_id": "seg-legacy"},
        "segment_candidates": [{"source": "current_execution"}],
    }

    assert lookup_resume_surface_text(
        payload,
        "active_resume_pointer",
        compat_surface=compat,
        compat_keys=("execution_resume_file",),
    ) == "GPD/phases/07/.continue-here.md"
    assert lookup_resume_surface_text(
        payload,
        "active_resume_pointer",
        compat_surface=compat,
        compat_keys=("execution_resume_file",),
        prefer_compat=True,
    ) == "GPD/phases/07/legacy.md"
    assert lookup_resume_surface_mapping(
        payload,
        "active_bounded_segment",
        compat_surface=compat,
        compat_keys=("current_execution",),
    ) == {"segment_id": "seg-canonical"}
    assert lookup_resume_surface_mapping(
        payload,
        "active_bounded_segment",
        compat_surface=compat,
        compat_keys=("current_execution",),
        prefer_compat=True,
    ) == {"segment_id": "seg-legacy"}
    assert lookup_resume_surface_list(
        payload,
        "resume_candidates",
        compat_surface=compat,
        compat_keys=("segment_candidates",),
    ) == [{"kind": "bounded_segment"}]
    assert lookup_resume_surface_list(
        payload,
        "resume_candidates",
        compat_surface=compat,
        compat_keys=("segment_candidates",),
        prefer_compat=True,
    ) == [{"source": "current_execution"}]


def test_resume_candidate_helpers_normalize_legacy_and_canonical_shapes() -> None:
    legacy_candidate = {
        "source": "session_resume_file",
        "status": "handoff",
        "resume_file": "GPD/phases/03/.continue-here.md",
    }
    canonical_candidate = build_resume_candidate(
        legacy_candidate,
        kind="continuity_handoff",
        origin="continuation.handoff",
        resume_pointer="GPD/phases/03/.continue-here.md",
    )

    assert resume_candidate_kind(legacy_candidate) == "continuity_handoff"
    assert resume_candidate_origin(legacy_candidate) == "compat.session_resume_file"
    assert resume_candidate_kind(canonical_candidate) == "continuity_handoff"
    assert resume_candidate_origin(canonical_candidate) == "continuation.handoff"
    assert resume_source_from_origin("compat.current_execution") == "current_execution"
    assert resume_source_from_origin("continuation.handoff") is None


def test_resume_payload_has_local_target_recognizes_bounded_segment_handoff_and_interrupted_agent() -> None:
    bounded_payload = {
        "active_resume_kind": "bounded_segment",
        "active_resume_pointer": "GPD/phases/03/.continue-here.md",
    }
    handoff_payload = {
        "continuity_handoff_file": "GPD/phases/04/.continue-here.md",
        "resume_candidates": [
            {
                "kind": "continuity_handoff",
                "origin": "continuation.handoff",
                "status": "handoff",
                "resume_file": "GPD/phases/04/.continue-here.md",
            }
        ],
    }
    interrupted_payload = {
        "has_interrupted_agent": True,
        "resume_candidates": [
            {
                "kind": "interrupted_agent",
                "origin": "interrupted_agent_marker",
                "status": "interrupted",
                "agent_id": "agent-42",
            }
        ],
    }

    assert resume_payload_has_local_target(bounded_payload) is True
    assert resume_payload_has_local_target(handoff_payload) is True
    assert resume_payload_has_local_target(interrupted_payload) is True


def test_resume_payload_has_local_target_rejects_missing_handoff_only_state() -> None:
    payload = {
        "has_continuity_handoff": True,
        "recorded_continuity_handoff_file": "GPD/phases/05/.continue-here.md",
        "missing_continuity_handoff_file": "GPD/phases/05/.continue-here.md",
        "resume_candidates": [
            {
                "kind": "continuity_handoff",
                "origin": "continuation.handoff",
                "status": "missing",
                "resume_file": "GPD/phases/05/.continue-here.md",
            }
        ],
    }

    assert resume_payload_has_local_target(payload) is False


@pytest.mark.parametrize(
    ("resume_payload", "expected"),
    [
        (
            {
                "resume_candidates": [
                    {
                        "kind": "bounded_segment",
                        "status": "paused",
                        "resume_file": "GPD/phases/03/.continue-here.md",
                    }
                ]
            },
            True,
        ),
        (
            {
                "resume_candidates": [
                    {
                        "kind": "continuity_handoff",
                        "status": "handoff",
                        "resume_file": "GPD/phases/04/.continue-here.md",
                    }
                ]
            },
            True,
        ),
        (
            {
                "resume_candidates": [
                    {
                        "kind": "interrupted_agent",
                        "status": "interrupted",
                        "agent_id": "agent-77",
                    }
                ]
            },
            True,
        ),
        (
            {
                "resume_candidates": [
                    {
                        "kind": "continuity_handoff",
                        "status": "missing",
                        "resume_file": "GPD/phases/05/.continue-here.md",
                    }
                ],
                "missing_continuity_handoff_file": "GPD/phases/05/.continue-here.md",
            },
            False,
        ),
    ],
)
def test_resume_payload_has_local_target_classifies_supported_resume_families(
    resume_payload: dict[str, object],
    expected: bool,
) -> None:
    assert resume_payload_has_local_target(resume_payload) is expected


def test_build_resume_segment_candidate_projects_segment_fields_into_raw_resume_shape() -> None:
    candidate = build_resume_segment_candidate(
        {
            "phase": "03",
            "plan": "02",
            "segment_id": "seg-7",
            "segment_status": "waiting_review",
            "resume_file": "GPD/phases/03/.continue-here.md",
            "transition_id": "transition-8",
            "last_result_id": "result-9",
        }
    )

    assert candidate["source"] == "current_execution"
    assert candidate["status"] == "waiting_review"
    assert candidate["phase"] == "03"
    assert candidate["plan"] == "02"
    assert candidate["segment_id"] == "seg-7"
    assert candidate["resume_file"] == "GPD/phases/03/.continue-here.md"
    assert candidate["transition_id"] == "transition-8"
    assert candidate["last_result_id"] == "result-9"


def test_canonicalize_resume_public_payload_keeps_candidate_continuity_nested_without_adding_top_level_fields() -> None:
    continuity_candidate = build_resume_candidate(
        {
            "status": "handoff",
            "resume_file": "GPD/phases/04/.continue-here.md",
        },
        kind="continuity_handoff",
        origin="continuation.handoff",
        resume_pointer="GPD/phases/04/.continue-here.md",
    )
    payload = {
        "active_resume_result": {
            "id": "result-canonical",
            "description": "Hydrated canonical result",
            "equation": "E = mc^2",
            "phase": "04",
            "verified": True,
        },
        "active_resume_kind": "continuity_handoff",
        "active_resume_origin": "continuation.handoff",
        "active_resume_pointer": "GPD/phases/04/.continue-here.md",
        "compat_resume_surface": {
            "resume_mode": "continuity_handoff",
            "segment_candidates": [
                {
                    "source": "session_resume_file",
                    "status": "handoff",
                    "resume_file": "GPD/phases/04/.continue-here.md",
                }
            ],
            "session_resume_file": "GPD/phases/04/.continue-here.md",
        },
        "resume_candidates": [continuity_candidate],
    }

    canonical = canonicalize_resume_public_payload(payload)

    assert canonical["active_resume_kind"] == "continuity_handoff"
    assert canonical["active_resume_origin"] == "continuation.handoff"
    assert canonical["active_resume_pointer"] == "GPD/phases/04/.continue-here.md"
    assert canonical["active_resume_result"] == {
        "id": "result-canonical",
        "description": "Hydrated canonical result",
        "equation": "E = mc^2",
        "phase": "04",
        "verified": True,
    }
    assert "compat_resume_surface" in canonical
    assert "resume_candidates" in canonical
    assert canonical["resume_candidates"] == [continuity_candidate]
    assert canonical["resume_candidates"][0]["kind"] == "continuity_handoff"
    assert canonical["resume_candidates"][0]["origin"] == "continuation.handoff"
    assert canonical["resume_candidates"][0]["resume_pointer"] == "GPD/phases/04/.continue-here.md"
    assert "active_resume_result" not in canonical["compat_resume_surface"]
    assert "segment_candidates" not in canonical
    assert "resume_mode" not in canonical
    assert "session_resume_file" not in canonical


def test_canonicalize_resume_public_payload_removes_legacy_top_level_aliases_and_preserves_canonical_fields() -> None:
    payload = {
        "active_resume_kind": "bounded_segment",
        "active_resume_origin": "compat.current_execution",
        "active_resume_pointer": "GPD/phases/03/.continue-here.md",
        "active_resume_result": {
            "id": "result-hydrated",
            "description": "Hydrated canonical result",
            "equation": "x = y",
            "phase": "03",
            "verified": False,
        },
        "execution_resumable": True,
        "execution_resume_file": "GPD/phases/03/.continue-here.md",
        "execution_resume_file_source": "current_execution",
        "resume_mode": "bounded_segment",
        "segment_candidates": [{"source": "current_execution"}],
        "session_resume_file": "GPD/phases/03/legacy.md",
        "resume_surface": {
            "recorded_session_resume_file": "GPD/phases/03/legacy.md",
        },
        "compat_resume_surface": {
            "session_resume_file": "GPD/phases/03/legacy.md",
            "resume_mode": "bounded_segment",
        },
    }

    canonical = canonicalize_resume_public_payload(payload)

    assert canonical["active_resume_kind"] == "bounded_segment"
    assert canonical["active_resume_origin"] == "compat.current_execution"
    assert canonical["active_resume_pointer"] == "GPD/phases/03/.continue-here.md"
    assert canonical["active_resume_result"] == {
        "id": "result-hydrated",
        "description": "Hydrated canonical result",
        "equation": "x = y",
        "phase": "03",
        "verified": False,
    }
    assert canonical["execution_resumable"] is True
    assert "execution_resume_file" not in canonical
    assert "execution_resume_file_source" not in canonical
    assert "resume_mode" not in canonical
    assert "segment_candidates" not in canonical
    assert "session_resume_file" not in canonical
    assert "resume_surface" not in canonical
    assert canonical["compat_resume_surface"]["execution_resume_file"] == "GPD/phases/03/.continue-here.md"
    assert canonical["compat_resume_surface"]["execution_resume_file_source"] == "current_execution"
    assert canonical["compat_resume_surface"]["resume_mode"] == "bounded_segment"
    assert canonical["compat_resume_surface"]["segment_candidates"] == [{"source": "current_execution"}]
    assert canonical["compat_resume_surface"]["session_resume_file"] == "GPD/phases/03/legacy.md"
    assert canonical["compat_resume_surface"]["recorded_session_resume_file"] == "GPD/phases/03/legacy.md"
    assert canonical["compat_resume_surface"]["missing_session_resume_file"] is None


def test_canonicalize_resume_public_payload_is_idempotent_on_already_canonical_payload() -> None:
    payload = {
        "active_resume_kind": "continuity_handoff",
        "active_resume_origin": "continuation.handoff",
        "active_resume_pointer": "GPD/phases/04/.continue-here.md",
        "active_resume_result": {
            "id": "result-idempotent",
            "description": "Hydrated canonical result",
            "equation": "a = b",
            "phase": "04",
            "verified": True,
        },
        "has_continuity_handoff": True,
        "compat_resume_surface": {
            "execution_resume_file": "GPD/phases/04/.continue-here.md",
            "execution_resume_file_source": "session_resume_file",
            "resume_mode": "continuity_handoff",
            "session_resume_file": "GPD/phases/04/.continue-here.md",
        },
    }

    once = canonicalize_resume_public_payload(payload)
    twice = canonicalize_resume_public_payload(deepcopy(once))

    assert once == twice
    assert once["active_resume_kind"] == "continuity_handoff"
    assert once["active_resume_origin"] == "continuation.handoff"
    assert once["active_resume_pointer"] == "GPD/phases/04/.continue-here.md"
    assert once["active_resume_result"] == {
        "id": "result-idempotent",
        "description": "Hydrated canonical result",
        "equation": "a = b",
        "phase": "04",
        "verified": True,
    }
    assert "resume_mode" not in once
    assert "execution_resume_file" not in once
    assert "execution_resume_file_source" not in once
    assert once["compat_resume_surface"]["execution_resume_file"] == "GPD/phases/04/.continue-here.md"
    assert once["compat_resume_surface"]["execution_resume_file_source"] == "session_resume_file"
    assert once["compat_resume_surface"]["resume_mode"] == "continuity_handoff"
    assert once["compat_resume_surface"]["session_resume_file"] == "GPD/phases/04/.continue-here.md"
    assert once["compat_resume_surface"]["segment_candidates"] is None
    assert once["compat_resume_surface"]["recorded_session_resume_file"] is None
