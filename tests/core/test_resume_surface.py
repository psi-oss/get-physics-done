from __future__ import annotations

from copy import deepcopy

import pytest

from gpd.core.resume_surface import (
    build_resume_candidate,
    build_resume_segment_candidate,
    canonicalize_resume_public_payload,
    lookup_resume_surface_list,
    lookup_resume_surface_mapping,
    lookup_resume_surface_text,
    resume_candidate_kind,
    resume_candidate_origin,
    resume_candidate_origin_from_source,
    resume_payload_has_local_recovery_target,
)


def test_lookup_resume_surface_helpers_prefer_canonical_values() -> None:
    payload = {
        "active_resume_pointer": "GPD/phases/07/.continue-here.md",
        "active_bounded_segment": {"segment_id": "seg-canonical"},
        "resume_candidates": [{"kind": "bounded_segment"}],
    }

    assert lookup_resume_surface_text(payload, "active_resume_pointer") == "GPD/phases/07/.continue-here.md"
    assert lookup_resume_surface_mapping(payload, "active_bounded_segment") == {"segment_id": "seg-canonical"}
    assert lookup_resume_surface_list(payload, "resume_candidates") == [{"kind": "bounded_segment"}]


def test_resume_candidate_helpers_normalize_raw_and_canonical_shapes_to_canonical_origins() -> None:
    raw_candidate = {
        "source": "session_resume_file",
        "status": "handoff",
        "resume_file": "GPD/phases/03/.continue-here.md",
    }
    canonical_candidate = build_resume_candidate(
        raw_candidate,
        kind="continuity_handoff",
        origin="continuation.handoff",
        resume_pointer="GPD/phases/03/.continue-here.md",
    )

    assert resume_candidate_kind(raw_candidate) == "continuity_handoff"
    assert resume_candidate_origin(raw_candidate) == "continuation.handoff"
    assert resume_candidate_origin_from_source("current_execution") == "continuation.bounded_segment"
    assert resume_candidate_origin_from_source("session_resume_file") == "continuation.handoff"
    assert resume_candidate_origin_from_source("interrupted_agent") == "interrupted_agent_marker"
    assert resume_candidate_kind(canonical_candidate) == "continuity_handoff"
    assert resume_candidate_origin(canonical_candidate) == "continuation.handoff"


def test_resume_payload_has_local_recovery_target_recognizes_supported_resume_families() -> None:
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

    assert resume_payload_has_local_recovery_target(bounded_payload) is True
    assert resume_payload_has_local_recovery_target(handoff_payload) is True
    assert resume_payload_has_local_recovery_target(interrupted_payload) is True


def test_resume_payload_has_local_recovery_target_rejects_missing_handoff_only_state() -> None:
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

    assert resume_payload_has_local_recovery_target(payload) is False


@pytest.mark.parametrize(
    ("resume_payload", "expected"),
    [
        ({"execution_resumable": True}, False),
        ({"has_interrupted_agent": True}, False),
        ({"has_continuity_handoff": True}, False),
        ({"active_resume_kind": "bounded_segment"}, False),
        ({"active_resume_kind": "interrupted_agent"}, False),
    ],
)
def test_resume_payload_has_local_recovery_target_requires_concrete_targets(
    resume_payload: dict[str, object],
    expected: bool,
) -> None:
    assert resume_payload_has_local_recovery_target(resume_payload) is expected


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
def test_resume_payload_has_local_recovery_target_classifies_supported_resume_families(
    resume_payload: dict[str, object],
    expected: bool,
) -> None:
    assert resume_payload_has_local_recovery_target(resume_payload) is expected


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


def test_canonicalize_resume_public_payload_keeps_canonical_fields_and_strips_legacy_aliases() -> None:
    continuity_candidate = build_resume_candidate(
        {"status": "handoff", "resume_file": "GPD/phases/04/.continue-here.md"},
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
        "resume_mode": "continuity_handoff",
        "segment_candidates": [
            {
                "source": "session_resume_file",
                "status": "handoff",
                "resume_file": "GPD/phases/04/.continue-here.md",
            }
        ],
        "session_resume_file": "GPD/phases/04/.continue-here.md",
        "compat_resume_surface": {"resume_mode": "continuity_handoff"},
        "resume_candidates": [continuity_candidate],
    }

    canonical = canonicalize_resume_public_payload(payload)

    assert canonical["active_resume_kind"] == "continuity_handoff"
    assert canonical["active_resume_origin"] == "continuation.handoff"
    assert canonical["active_resume_pointer"] == "GPD/phases/04/.continue-here.md"
    assert canonical["resume_candidates"] == [continuity_candidate]
    assert "compat_resume_surface" not in canonical
    assert "segment_candidates" not in canonical
    assert "resume_mode" not in canonical
    assert "session_resume_file" not in canonical


def test_canonicalize_resume_public_payload_is_idempotent() -> None:
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
        "execution_resume_file": "GPD/phases/04/.continue-here.md",
        "execution_resume_file_source": "session_resume_file",
        "resume_mode": "continuity_handoff",
        "session_resume_file": "GPD/phases/04/.continue-here.md",
    }

    once = canonicalize_resume_public_payload(payload)
    twice = canonicalize_resume_public_payload(deepcopy(once))

    assert once == twice
    assert once["active_resume_kind"] == "continuity_handoff"
    assert once["active_resume_origin"] == "continuation.handoff"
    assert once["active_resume_pointer"] == "GPD/phases/04/.continue-here.md"
    assert "resume_mode" not in once
    assert "execution_resume_file" not in once
    assert "execution_resume_file_source" not in once
    assert "compat_resume_surface" not in once
