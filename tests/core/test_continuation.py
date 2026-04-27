from __future__ import annotations

import re
from pathlib import Path

from gpd.core.continuation import (
    ContinuationBoundedSegment,
    ContinuationResumeSource,
    ContinuationSource,
    canonical_bounded_segment_from_execution_snapshot,
    normalize_continuation,
    normalize_continuation_reference,
    normalize_continuation_with_issues,
    resolve_continuation,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _write_resume(project_root: Path, relative_path: str) -> Path:
    resume_path = project_root / relative_path
    resume_path.parent.mkdir(parents=True, exist_ok=True)
    resume_path.write_text("resume\n", encoding="utf-8")
    return resume_path


def _documented_bounded_segment_fields(text: str) -> list[str]:
    match = re.search(r"Persisted bounded-segment fields:\s*(?P<fields>.+?)\.", text, re.DOTALL)
    assert match is not None
    return re.findall(r"`([a-z_]+)`", match.group("fields"))


def test_normalize_continuation_reference_normalizes_project_local_absolute_path(tmp_path: Path) -> None:
    resume_path = _write_resume(tmp_path, "GPD/phases/03-analysis/.continue-here.md")

    normalized = normalize_continuation_reference(tmp_path, str(resume_path))

    assert normalized == "GPD/phases/03-analysis/.continue-here.md"


def test_normalize_continuation_reference_rejects_external_absolute_path(tmp_path: Path) -> None:
    external_root = tmp_path.parent / f"{tmp_path.name}-external"
    external_resume = external_root / ".continue-here.md"
    external_resume.parent.mkdir(parents=True, exist_ok=True)
    external_resume.write_text("resume\n", encoding="utf-8")

    assert normalize_continuation_reference(tmp_path, str(external_resume)) is None


def test_normalize_continuation_normalizes_canonical_references(tmp_path: Path) -> None:
    resume_path = _write_resume(tmp_path, "GPD/phases/03-analysis/.continue-here.md")

    continuation = normalize_continuation(
        tmp_path,
        {
            "schema_version": 1,
            "handoff": {"resume_file": str(resume_path), "stopped_at": "Phase 03 Plan 02"},
            "bounded_segment": {
                "resume_file": str(resume_path),
                "phase": "3",
                "plan": "2",
                "segment_id": "seg-4",
                "segment_status": "paused",
            },
            "machine": {"recorded_at": "2026-03-29T12:00:00+00:00"},
        },
    )

    assert continuation.handoff.resume_file == "GPD/phases/03-analysis/.continue-here.md"
    assert continuation.bounded_segment is not None
    assert continuation.bounded_segment.resume_file == "GPD/phases/03-analysis/.continue-here.md"
    assert continuation.bounded_segment.phase == "03"
    assert continuation.bounded_segment.plan == "02"


def test_canonical_bounded_segment_field_inventory_matches_documented_payload() -> None:
    checkpoints = (REPO_ROOT / "src/gpd/specs/references/orchestration/checkpoints.md").read_text(encoding="utf-8")
    continuation_prompt = (REPO_ROOT / "src/gpd/specs/templates/continuation-prompt.md").read_text(encoding="utf-8")
    expected_fields = list(ContinuationBoundedSegment.model_fields)

    assert _documented_bounded_segment_fields(checkpoints) == expected_fields
    assert _documented_bounded_segment_fields(continuation_prompt) == expected_fields


def test_normalize_continuation_with_issues_drops_malformed_boolean_gate_fields(tmp_path: Path) -> None:
    continuation, issues = normalize_continuation_with_issues(
        tmp_path,
        {
            "bounded_segment": {
                "resume_file": "GPD/phases/03-analysis/.continue-here.md",
                "segment_status": "paused",
                "waiting_for_review": "yes",
            }
        },
    )

    assert continuation.bounded_segment is not None
    assert continuation.bounded_segment.waiting_for_review is False
    assert any(
        'schema normalization: dropped malformed "continuation.bounded_segment.waiting_for_review"'
        in issue
        for issue in issues
    )


def test_canonical_bounded_segment_from_execution_snapshot_normalizes_lineage_fields(
    tmp_path: Path,
) -> None:
    resume_path = _write_resume(tmp_path, "GPD/phases/03-analysis/.continue-here.md")

    segment = canonical_bounded_segment_from_execution_snapshot(
        tmp_path,
        {
            "session_id": "sess-1",
            "phase": "3",
            "plan": "2",
            "segment_id": "seg-4",
            "segment_status": "waiting_review",
            "resume_file": str(resume_path),
            "transition_id": "transition-9",
            "last_result_id": "result-12",
            "updated_at": "2026-03-29T12:00:00+00:00",
        },
    )

    assert segment is not None
    assert segment.resume_file == "GPD/phases/03-analysis/.continue-here.md"
    assert segment.phase == "03"
    assert segment.plan == "02"
    assert segment.transition_id == "transition-9"
    assert segment.last_result_id == "result-12"


def test_resolve_continuation_prefers_canonical_state_over_stale_inputs(tmp_path: Path) -> None:
    _write_resume(tmp_path, "GPD/phases/03-analysis/.continue-here.md")
    _write_resume(tmp_path, "GPD/phases/03-analysis/handoff.md")
    _write_resume(tmp_path, "GPD/phases/03-analysis/canonical.md")

    projection = resolve_continuation(
        tmp_path,
        state={
            "continuation": {
                "schema_version": 1,
                "handoff": {
                    "resume_file": "GPD/phases/03-analysis/handoff.md",
                    "stopped_at": "Canonical handoff",
                    "recorded_at": "2026-03-29T12:00:00+00:00",
                },
                "bounded_segment": {
                    "resume_file": "GPD/phases/03-analysis/.continue-here.md",
                    "phase": "3",
                    "plan": "2",
                    "segment_id": "seg-4",
                    "segment_status": "paused",
                    "transition_id": "transition-3",
                    "last_result_id": "result-8",
                },
                "machine": {"hostname": "builder-01", "platform": "Linux 6.1 x86_64"},
            },
            "session": {
                "resume_file": "GPD/phases/03-analysis/canonical.md",
                "stopped_at": "Stale handoff",
            },
        },
        current_execution={
            "resume_file": "GPD/phases/03-analysis/canonical.md",
            "segment_status": "paused",
            "segment_id": "recorded-seg",
            "transition_id": "transition-recorded",
            "last_result_id": "result-recorded",
        },
    )

    assert projection.source == ContinuationSource.CANONICAL
    assert projection.continuation.handoff.stopped_at == "Canonical handoff"
    assert projection.continuation.bounded_segment is not None
    assert projection.continuation.bounded_segment.phase == "03"
    assert projection.continuation.bounded_segment.transition_id == "transition-3"
    assert projection.continuation.bounded_segment.last_result_id == "result-8"
    assert projection.active_resume_source == ContinuationResumeSource.BOUNDED_SEGMENT
    assert projection.active_resume_file == "GPD/phases/03-analysis/.continue-here.md"
    assert projection.handoff_resume_file == "GPD/phases/03-analysis/handoff.md"
    assert projection.resumable is True


def test_resolve_continuation_keeps_canonical_handoff_when_live_bounded_segment_exists(
    tmp_path: Path,
) -> None:
    _write_resume(tmp_path, "GPD/phases/03-analysis/.continue-here.md")
    _write_resume(tmp_path, "GPD/phases/03-analysis/handoff.md")

    projection = resolve_continuation(
        tmp_path,
        state={
            "continuation": {
                "schema_version": 1,
                "handoff": {
                    "resume_file": "GPD/phases/03-analysis/handoff.md",
                    "stopped_at": "Canonical handoff",
                },
                "machine": {"hostname": "builder-01", "platform": "Linux 6.1 x86_64"},
            }
        },
        current_execution={
            "session_id": "sess-1",
            "phase": "3",
            "plan": "2",
            "segment_id": "seg-4",
            "segment_status": "paused",
            "resume_file": "GPD/phases/03-analysis/.continue-here.md",
            "transition_id": "transition-recorded",
            "last_result_id": "result-recorded",
        },
    )

    assert projection.source == ContinuationSource.CANONICAL
    assert projection.continuation.handoff.stopped_at == "Canonical handoff"
    assert projection.continuation.bounded_segment is None
    assert projection.active_resume_source == ContinuationResumeSource.HANDOFF
    assert projection.active_resume_file == "GPD/phases/03-analysis/handoff.md"
    assert projection.handoff_resume_file == "GPD/phases/03-analysis/handoff.md"
    assert projection.resumable is False


def test_resolve_continuation_projects_live_execution_when_canonical_pointer_is_invalid(
    tmp_path: Path,
) -> None:
    external_root = tmp_path.parent / f"{tmp_path.name}-external"
    external_resume = external_root / ".continue-here.md"
    external_resume.parent.mkdir(parents=True, exist_ok=True)
    external_resume.write_text("resume\n", encoding="utf-8")
    _write_resume(tmp_path, "GPD/phases/03-analysis/canonical.md")
    _write_resume(tmp_path, "GPD/phases/03-analysis/live.md")

    raw_continuation = {
        "schema_version": 1,
        "bounded_segment": {
            "resume_file": str(external_resume),
        },
    }

    continuation, issues = normalize_continuation_with_issues(tmp_path, raw_continuation)

    assert continuation.is_empty is True
    assert any("continuation.bounded_segment.resume_file" in issue for issue in issues)

    projection = resolve_continuation(
        tmp_path,
        state={
            "continuation": raw_continuation,
            "session": {
                "resume_file": "GPD/phases/03-analysis/canonical.md",
                "stopped_at": "Stale handoff",
            },
        },
        current_execution={
            "resume_file": "GPD/phases/03-analysis/live.md",
            "segment_status": "paused",
            "segment_id": "live-seg",
        },
    )

    assert projection.source == ContinuationSource.DERIVED_EXECUTION
    assert projection.continuation.is_empty is False
    assert projection.continuation.bounded_segment is not None
    assert projection.continuation.bounded_segment.resume_file == "GPD/phases/03-analysis/live.md"
    assert projection.recorded_handoff_resume_file is None
    assert projection.handoff_resume_file is None
    assert projection.active_resume_file == "GPD/phases/03-analysis/live.md"
    assert projection.active_resume_source == ContinuationResumeSource.BOUNDED_SEGMENT
    assert projection.resumable is True


def test_resolve_continuation_falls_back_to_handoff_when_canonical_bounded_segment_pointer_is_missing(
    tmp_path: Path,
) -> None:
    projection = resolve_continuation(
        tmp_path,
        state={
            "continuation": {
                "handoff": {"resume_file": "GPD/phases/03-analysis/handoff.md"},
                "bounded_segment": {
                    "resume_file": "GPD/phases/03-analysis/.continue-here.md",
                    "segment_status": "paused",
                    "segment_id": "seg-4",
                },
            }
        },
    )

    assert projection.source == ContinuationSource.CANONICAL
    assert projection.recorded_handoff_resume_file == "GPD/phases/03-analysis/handoff.md"
    assert projection.missing_handoff_resume_file == "GPD/phases/03-analysis/handoff.md"
    assert projection.bounded_segment_resume_file is None
    assert projection.active_resume_file is None
    assert projection.active_resume_source is None
    assert projection.resumable is False


def test_resolve_continuation_uses_live_bounded_segment_when_recorded_handoff_file_is_missing(
    tmp_path: Path,
) -> None:
    _write_resume(tmp_path, "GPD/phases/03-analysis/live.md")

    projection = resolve_continuation(
        tmp_path,
        state={
            "continuation": {
                "handoff": {
                    "resume_file": "GPD/phases/03-analysis/missing-handoff.md",
                    "stopped_at": "Canonical handoff",
                    "recorded_at": "2026-03-29T12:00:00+00:00",
                },
                "machine": {"hostname": "builder-01"},
            }
        },
        current_execution={
            "session_id": "sess-1",
            "phase": "3",
            "plan": "2",
            "segment_id": "live-seg",
            "segment_status": "paused",
            "resume_file": "GPD/phases/03-analysis/live.md",
        },
    )

    assert projection.source == ContinuationSource.DERIVED_EXECUTION
    assert projection.recorded_handoff_resume_file == "GPD/phases/03-analysis/missing-handoff.md"
    assert projection.missing_handoff_resume_file == "GPD/phases/03-analysis/missing-handoff.md"
    assert projection.continuation.handoff.stopped_at == "Canonical handoff"
    assert projection.continuation.machine.hostname == "builder-01"
    assert projection.continuation.bounded_segment is not None
    assert projection.continuation.bounded_segment.segment_id == "live-seg"
    assert projection.bounded_segment_resume_file == "GPD/phases/03-analysis/live.md"
    assert projection.active_resume_file == "GPD/phases/03-analysis/live.md"
    assert projection.active_resume_source == ContinuationResumeSource.BOUNDED_SEGMENT
    assert projection.resumable is True


def test_resolve_continuation_projects_portable_current_execution_when_canonical_continuation_is_missing(
    tmp_path: Path,
) -> None:
    _write_resume(tmp_path, "GPD/phases/03-analysis/.continue-here.md")

    projection = resolve_continuation(
        tmp_path,
        current_execution={
            "session_id": "sess-1",
            "phase": "3",
            "plan": "2",
            "segment_id": "seg-4",
            "segment_status": "paused",
            "resume_file": "GPD/phases/03-analysis/.continue-here.md",
            "updated_at": "2026-03-29T12:05:00+00:00",
            "pre_fanout_review_pending": True,
        },
    )

    assert projection.source == ContinuationSource.DERIVED_EXECUTION
    assert projection.continuation.handoff.is_empty is True
    assert projection.continuation.bounded_segment is not None
    assert projection.continuation.bounded_segment.recorded_by == "derived_execution_head"
    assert projection.continuation.bounded_segment.resume_file == "GPD/phases/03-analysis/.continue-here.md"
    assert projection.continuation.bounded_segment.phase == "03"
    assert projection.continuation.bounded_segment.plan == "02"
    assert projection.continuation.bounded_segment.pre_fanout_review_pending is True
    assert projection.active_resume_source == ContinuationResumeSource.BOUNDED_SEGMENT
    assert projection.handoff_resume_file is None
    assert projection.active_resume_file == "GPD/phases/03-analysis/.continue-here.md"
    assert projection.resumable is True


def test_resolve_continuation_ignores_nonportable_or_missing_live_snapshot_without_promoting_session_handoff(
    tmp_path: Path,
) -> None:
    external_root = tmp_path.parent / f"{tmp_path.name}-external"
    external_resume = external_root / ".continue-here.md"
    external_resume.parent.mkdir(parents=True, exist_ok=True)
    external_resume.write_text("resume\n", encoding="utf-8")

    projection = resolve_continuation(
        tmp_path,
        state={"session": {"resume_file": "GPD/phases/03-analysis/handoff.md"}},
        current_execution={
            "segment_status": "paused",
            "segment_id": "seg-4",
            "resume_file": str(external_resume),
        },
    )

    assert projection.source == ContinuationSource.EMPTY
    assert projection.handoff_resume_file is None
    assert projection.active_resume_source is None
    assert projection.active_resume_file is None
    assert projection.resumable is False


def test_resolve_continuation_preserves_partial_canonical_state_without_falling_back_to_session(
    tmp_path: Path,
) -> None:
    _write_resume(tmp_path, "GPD/phases/03-analysis/canonical-handoff.md")
    _write_resume(tmp_path, "GPD/phases/03-analysis/session-handoff.md")

    projection = resolve_continuation(
        tmp_path,
        state={
            "continuation": {
                "schema_version": 1,
                "handoff": {
                    "resume_file": "GPD/phases/03-analysis/canonical-handoff.md",
                    "stopped_at": "Canonical stop",
                },
                "bounded_segment": "not-an-object",
                "machine": {"hostname": "builder-01", "platform": "Linux 6.1 x86_64"},
            },
            "session": {
                "resume_file": "GPD/phases/03-analysis/session-handoff.md",
                "stopped_at": "Stale stop",
            },
        },
    )

    assert projection.source == ContinuationSource.CANONICAL
    assert projection.continuation.handoff.resume_file == "GPD/phases/03-analysis/canonical-handoff.md"
    assert projection.continuation.handoff.stopped_at == "Canonical stop"
    assert projection.continuation.bounded_segment is None
    assert projection.active_resume_file == "GPD/phases/03-analysis/canonical-handoff.md"
    assert projection.handoff_resume_file == "GPD/phases/03-analysis/canonical-handoff.md"
    assert projection.recorded_handoff_resume_file == "GPD/phases/03-analysis/canonical-handoff.md"


def test_normalize_continuation_salvages_partial_child_objects(tmp_path: Path) -> None:
    _write_resume(tmp_path, "GPD/phases/03-analysis/canonical-handoff.md")

    continuation = normalize_continuation(
        tmp_path,
        {
            "schema_version": 1,
            "handoff": {
                "resume_file": "GPD/phases/03-analysis/canonical-handoff.md",
                "stopped_at": "Canonical stop",
                "recorded_by": "state_record_session",
            },
            "bounded_segment": {
                "resume_file": "GPD/phases/03-analysis/canonical-handoff.md",
                "segment_status": "paused",
                "segment_id": "seg-1",
                "unexpected_flag": "ignored",
            },
            "machine": {"hostname": "builder-01", "platform": "Linux 6.1 x86_64"},
        },
    )

    assert continuation.handoff.resume_file == "GPD/phases/03-analysis/canonical-handoff.md"
    assert continuation.handoff.stopped_at == "Canonical stop"
    assert continuation.machine.hostname == "builder-01"
    assert continuation.machine.platform == "Linux 6.1 x86_64"
    assert continuation.bounded_segment is not None
    assert continuation.bounded_segment.resume_file == "GPD/phases/03-analysis/canonical-handoff.md"
    assert continuation.bounded_segment.segment_status == "paused"
    assert continuation.bounded_segment.segment_id == "seg-1"
