from __future__ import annotations

import pytest

from gpd.core.context import init_progress, init_resume
from gpd.core.recent_projects import recent_projects_index_path
from gpd.core.recovery_advice import RecoveryAdvice, serialize_recovery_advice
from gpd.core.resume_surface import (
    RESUME_SURFACE_SCHEMA_VERSION,
    build_resume_candidate,
    build_resume_segment_candidate,
    canonicalize_resume_public_payload,
    lookup_resume_surface_list,
    lookup_resume_surface_mapping,
    lookup_resume_surface_text,
    resume_candidate_kind,
    resume_candidate_origin,
    resume_candidate_origin_from_source,
    resume_origin_for_bounded_segment,
    resume_origin_for_handoff,
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


def test_resume_surface_schema_version_uses_shared_constant(tmp_path) -> None:
    advice_payload = serialize_recovery_advice(RecoveryAdvice())
    resume_payload = init_resume(tmp_path, data_root=tmp_path / "data")

    assert advice_payload["resume_surface_schema_version"] == RESUME_SURFACE_SCHEMA_VERSION
    assert resume_payload["resume_surface_schema_version"] == RESUME_SURFACE_SCHEMA_VERSION


def test_init_resume_and_progress_degrade_when_recent_project_index_is_malformed(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    data_root = tmp_path / "data"
    index_path = recent_projects_index_path(data_root)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text("{ not-json", encoding="utf-8")

    resume_payload = init_resume(workspace, data_root=data_root)
    progress_payload = init_progress(workspace, data_root=data_root)

    assert resume_payload["project_reentry_mode"] == "no-recovery"
    assert resume_payload["project_reentry_candidates"] == []
    assert len(resume_payload["project_reentry_diagnostics"]) == 1
    assert "Malformed recent-project index" in resume_payload["project_reentry_diagnostics"][0]
    assert resume_payload["project_root"] is None
    assert progress_payload["project_reentry_mode"] == "no-recovery"
    assert progress_payload["project_reentry_candidates"] == []
    assert len(progress_payload["project_reentry_diagnostics"]) == 1
    assert "Malformed recent-project index" in progress_payload["project_reentry_diagnostics"][0]
    assert progress_payload["project_root"] is None


def test_init_resume_does_not_recover_state_json_only_ancestor(tmp_path) -> None:
    project = tmp_path / "project"
    planning = project / "GPD"
    nested = project / "workspace" / "notes"
    planning.mkdir(parents=True)
    nested.mkdir(parents=True)
    (planning / "state.json").write_text("{}\n", encoding="utf-8")

    resume_payload = init_resume(nested, data_root=tmp_path / "data")

    assert resume_payload["project_reentry_mode"] == "no-recovery"
    assert resume_payload["project_reentry_candidates"] == []
    assert resume_payload["project_root"] is None


def test_resume_candidate_helpers_normalize_raw_and_canonical_shapes_to_canonical_origins() -> None:
    raw_candidate = {
        "source": "handoff_resume_file",
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
    assert resume_candidate_origin_from_source("handoff_resume_file") == "continuation.handoff"
    assert resume_candidate_origin_from_source("interrupted_agent") == "interrupted_agent_marker"
    assert resume_candidate_kind(canonical_candidate) == "continuity_handoff"
    assert resume_candidate_origin(canonical_candidate) == "continuation.handoff"


def test_resume_origin_helpers_return_canonical_origins_without_provenance_inputs() -> None:
    assert resume_origin_for_bounded_segment() == "continuation.bounded_segment"
    assert resume_origin_for_handoff() == "continuation.handoff"


def test_resume_payload_has_local_recovery_target_recognizes_supported_resume_families() -> None:
    bounded_payload = {
        "active_resume_kind": "bounded_segment",
        "active_resume_pointer": "GPD/phases/03/.continue-here.md",
    }
    continuity_payload = {
        "active_resume_kind": "continuity_handoff",
        "active_resume_pointer": "GPD/phases/04/.continue-here.md",
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
    assert resume_payload_has_local_recovery_target(continuity_payload) is True
    assert resume_payload_has_local_recovery_target(handoff_payload) is True
    assert resume_payload_has_local_recovery_target(interrupted_payload) is True


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


def test_canonicalize_resume_public_payload_keeps_canonical_fields_and_strips_internal_fields() -> None:
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
        "resume_surface": {
            "active_resume_result": {
                "id": "wrapped-result",
                "description": "Wrapped result",
            },
            "resume_candidates": [{"kind": "bounded_segment"}],
            "handoff_resume_file": "GPD/phases/04/.continue-here.md",
        },
        "resume_mode": "continuity_handoff",
        "segment_candidates": [
            {
                "source": "handoff_resume_file",
                "status": "handoff",
                "resume_file": "GPD/phases/04/.continue-here.md",
            }
        ],
        "handoff_resume_file": "GPD/phases/04/.continue-here.md",
        "resume_candidates": [continuity_candidate],
    }

    canonical = canonicalize_resume_public_payload(payload)

    assert canonical["active_resume_kind"] == "continuity_handoff"
    assert canonical["active_resume_origin"] == "continuation.handoff"
    assert canonical["active_resume_pointer"] == "GPD/phases/04/.continue-here.md"
    assert canonical["resume_candidates"] == [continuity_candidate]
    assert canonical["active_resume_result"]["id"] == "result-canonical"
    assert "segment_candidates" not in canonical
    assert "resume_mode" not in canonical
    assert "handoff_resume_file" not in canonical
    assert "resume_surface" not in canonical
    assert payload["resume_surface"]["resume_candidates"][0]["kind"] == "bounded_segment"
    assert payload["resume_surface"]["active_resume_result"]["id"] == "wrapped-result"


def test_canonicalize_resume_public_payload_preserves_nested_business_data_with_internal_like_keys() -> None:
    payload = {
        "active_resume_result": {
            "id": "result-canonical",
            "resume_surface": {"note": "nested result metadata must survive"},
            "current_execution": {"phase": "04"},
        },
        "recovery": {
            "resume_mode": "keep-this-nested-value",
            "handoff_resume_file": "not-a-top-level-alias",
        },
        "resume_mode": "continuity_handoff",
        "handoff_resume_file": "GPD/phases/04/.continue-here.md",
    }

    canonical = canonicalize_resume_public_payload(payload)

    assert "resume_mode" not in canonical
    assert "handoff_resume_file" not in canonical
    assert canonical["active_resume_result"]["resume_surface"] == {"note": "nested result metadata must survive"}
    assert canonical["active_resume_result"]["current_execution"] == {"phase": "04"}
    assert canonical["recovery"]["resume_mode"] == "keep-this-nested-value"
    assert canonical["recovery"]["handoff_resume_file"] == "not-a-top-level-alias"
