from __future__ import annotations

from pathlib import Path

from gpd.core.continuation import (
    ContinuationResumeSource,
    ContinuationSource,
    canonical_bounded_segment_from_execution_snapshot,
    normalize_continuation,
    normalize_continuation_reference,
    normalize_continuation_with_issues,
    resolve_continuation,
    synthesize_legacy_continuation,
)


def _write_resume(project_root: Path, relative_path: str) -> Path:
    resume_path = project_root / relative_path
    resume_path.parent.mkdir(parents=True, exist_ok=True)
    resume_path.write_text("resume\n", encoding="utf-8")
    return resume_path


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


def test_resolve_continuation_prefers_canonical_state_over_legacy_inputs(tmp_path: Path) -> None:
    _write_resume(tmp_path, "GPD/phases/03-analysis/.continue-here.md")
    _write_resume(tmp_path, "GPD/phases/03-analysis/handoff.md")
    _write_resume(tmp_path, "GPD/phases/03-analysis/legacy.md")

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
                "resume_file": "GPD/phases/03-analysis/legacy.md",
                "stopped_at": "Legacy handoff",
            },
        },
        current_execution={
            "resume_file": "GPD/phases/03-analysis/legacy.md",
            "segment_status": "paused",
            "segment_id": "legacy-seg",
            "transition_id": "transition-legacy",
            "last_result_id": "result-legacy",
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
            "transition_id": "transition-legacy",
            "last_result_id": "result-legacy",
        },
    )

    assert projection.source == ContinuationSource.CANONICAL
    assert projection.continuation.handoff.stopped_at == "Canonical handoff"
    assert projection.continuation.bounded_segment is None
    assert projection.active_resume_source == ContinuationResumeSource.HANDOFF
    assert projection.active_resume_file == "GPD/phases/03-analysis/handoff.md"
    assert projection.handoff_resume_file == "GPD/phases/03-analysis/handoff.md"
    assert projection.resumable is False


def test_resolve_continuation_surfaces_invalid_canonical_resume_pointer_without_falling_back_to_legacy(
    tmp_path: Path,
) -> None:
    external_root = tmp_path.parent / f"{tmp_path.name}-external"
    external_resume = external_root / ".continue-here.md"
    external_resume.parent.mkdir(parents=True, exist_ok=True)
    external_resume.write_text("resume\n", encoding="utf-8")
    _write_resume(tmp_path, "GPD/phases/03-analysis/legacy.md")

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
                "resume_file": "GPD/phases/03-analysis/legacy.md",
                "stopped_at": "Legacy handoff",
            },
        },
        current_execution={
            "resume_file": "GPD/phases/03-analysis/legacy.md",
            "segment_status": "paused",
            "segment_id": "legacy-seg",
        },
    )

    assert projection.source == ContinuationSource.CANONICAL
    assert projection.continuation.is_empty is True
    assert projection.recorded_handoff_resume_file is None
    assert projection.handoff_resume_file is None
    assert projection.active_resume_file is None
    assert projection.active_resume_source is None
    assert projection.resumable is False


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


def test_synthesize_legacy_continuation_uses_portable_current_execution_and_session(tmp_path: Path) -> None:
    _write_resume(tmp_path, "GPD/phases/03-analysis/.continue-here.md")
    _write_resume(tmp_path, "GPD/phases/03-analysis/handoff.md")

    continuation = synthesize_legacy_continuation(
        tmp_path,
        session={
            "last_date": "2026-03-29T12:00:00+00:00",
            "hostname": "builder-01",
            "platform": "Linux 6.1 x86_64",
            "stopped_at": "Phase 03 Plan 02 Task 04",
            "resume_file": "GPD/phases/03-analysis/handoff.md",
        },
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

    assert continuation.machine.recorded_at == "2026-03-29T12:00:00+00:00"
    assert continuation.machine.hostname == "builder-01"
    assert continuation.handoff.resume_file == "GPD/phases/03-analysis/handoff.md"
    assert continuation.handoff.recorded_by == "legacy_session"
    assert continuation.bounded_segment is not None
    assert continuation.bounded_segment.resume_file == "GPD/phases/03-analysis/.continue-here.md"
    assert continuation.bounded_segment.phase == "03"
    assert continuation.bounded_segment.plan == "02"
    assert continuation.bounded_segment.pre_fanout_review_pending is True

    projection = resolve_continuation(
        tmp_path,
        state={
            "session": {
                "last_date": continuation.machine.recorded_at,
                "hostname": continuation.machine.hostname,
                "platform": continuation.machine.platform,
                "stopped_at": continuation.handoff.stopped_at,
                "resume_file": continuation.handoff.resume_file,
            }
        },
        current_execution={
            "session_id": "sess-1",
            "phase": "3",
            "plan": "2",
            "segment_id": "seg-4",
            "segment_status": "paused",
            "resume_file": "GPD/phases/03-analysis/.continue-here.md",
        },
    )

    assert projection.source == ContinuationSource.LEGACY
    assert projection.active_resume_source == ContinuationResumeSource.BOUNDED_SEGMENT
    assert projection.handoff_resume_file == "GPD/phases/03-analysis/handoff.md"
    assert projection.active_resume_file == "GPD/phases/03-analysis/.continue-here.md"
    assert projection.resumable is True


def test_synthesize_legacy_continuation_preserves_session_last_result_id(tmp_path: Path) -> None:
    continuation = synthesize_legacy_continuation(
        tmp_path,
        session={
            "last_date": "2026-03-29T12:00:00+00:00",
            "last_result_id": "result-03",
        },
    )

    assert continuation.handoff.last_result_id == "result-03"
    assert continuation.handoff.recorded_by == "legacy_session"

    projection = resolve_continuation(
        tmp_path,
        state={
            "session": {
                "last_date": "2026-03-29T12:00:00+00:00",
                "last_result_id": "result-03",
            }
        },
    )

    assert projection.source == ContinuationSource.LEGACY
    assert projection.continuation.handoff.last_result_id == "result-03"


def test_synthesize_legacy_continuation_ignores_nonportable_or_missing_live_snapshot(tmp_path: Path) -> None:
    _write_resume(tmp_path, "GPD/phases/03-analysis/handoff.md")
    external_root = tmp_path.parent / f"{tmp_path.name}-external"
    external_resume = external_root / ".continue-here.md"
    external_resume.parent.mkdir(parents=True, exist_ok=True)
    external_resume.write_text("resume\n", encoding="utf-8")

    continuation = synthesize_legacy_continuation(
        tmp_path,
        session={"resume_file": "GPD/phases/03-analysis/handoff.md"},
        current_execution={
            "segment_status": "paused",
            "segment_id": "seg-4",
            "resume_file": str(external_resume),
        },
    )

    assert continuation.bounded_segment is None
    assert continuation.handoff.resume_file == "GPD/phases/03-analysis/handoff.md"

    projection = resolve_continuation(
        tmp_path,
        state={"session": {"resume_file": "GPD/phases/03-analysis/handoff.md"}},
        current_execution={
            "segment_status": "paused",
            "segment_id": "seg-4",
            "resume_file": str(external_resume),
        },
    )

    assert projection.source == ContinuationSource.LEGACY
    assert projection.active_resume_source == ContinuationResumeSource.HANDOFF
    assert projection.active_resume_file == "GPD/phases/03-analysis/handoff.md"
    assert projection.resumable is False


def test_resolve_continuation_surfaces_missing_handoff_pointer_without_promoting_it(tmp_path: Path) -> None:
    projection = resolve_continuation(
        tmp_path,
        state={
            "session": {
                "last_date": "2026-03-29T12:00:00+00:00",
                "resume_file": "GPD/phases/03-analysis/handoff.md",
                "stopped_at": "Paused after Task 4",
            }
        },
    )

    assert projection.source == ContinuationSource.LEGACY
    assert projection.recorded_handoff_resume_file == "GPD/phases/03-analysis/handoff.md"
    assert projection.handoff_resume_file is None
    assert projection.missing_handoff_resume_file == "GPD/phases/03-analysis/handoff.md"
    assert projection.active_resume_file is None
    assert projection.active_resume_source is None
    assert projection.resumable is False


def test_resolve_continuation_returns_empty_projection_without_canonical_or_legacy_state(tmp_path: Path) -> None:
    projection = resolve_continuation(tmp_path)

    assert projection.source == ContinuationSource.EMPTY
    assert projection.continuation.is_empty is True
    assert projection.active_resume_file is None
    assert projection.active_resume_source is None
    assert projection.resumable is False


def test_resolve_continuation_ignores_empty_canonical_state_and_falls_back_to_legacy_inputs(tmp_path: Path) -> None:
    _write_resume(tmp_path, "GPD/phases/03-analysis/.continue-here.md")
    _write_resume(tmp_path, "GPD/phases/03-analysis/handoff.md")

    projection = resolve_continuation(
        tmp_path,
        state={
            "continuation": {"schema_version": 1},
            "session": {
                "last_date": "2026-03-29T12:00:00+00:00",
                "hostname": "builder-01",
                "platform": "Linux 6.1 x86_64",
                "stopped_at": "Paused after Task 4",
                "resume_file": "GPD/phases/03-analysis/handoff.md",
            },
        },
        current_execution={
            "session_id": "sess-1",
            "phase": "3",
            "plan": "2",
            "segment_id": "seg-4",
            "segment_status": "paused",
            "resume_file": "GPD/phases/03-analysis/.continue-here.md",
        },
    )

    assert projection.source == ContinuationSource.LEGACY
    assert projection.active_resume_source == ContinuationResumeSource.BOUNDED_SEGMENT
    assert projection.active_resume_file == "GPD/phases/03-analysis/.continue-here.md"
    assert projection.handoff_resume_file == "GPD/phases/03-analysis/handoff.md"


def test_resolve_continuation_preserves_partial_canonical_state_without_falling_back_to_session(
    tmp_path: Path,
) -> None:
    _write_resume(tmp_path, "GPD/phases/03-analysis/canonical-handoff.md")
    _write_resume(tmp_path, "GPD/phases/03-analysis/legacy-session.md")

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
                "resume_file": "GPD/phases/03-analysis/legacy-session.md",
                "stopped_at": "Legacy stop",
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
