"""Focused regressions for the canonical ``gpd_return`` contract."""

from __future__ import annotations

from gpd.core.return_contract import validate_gpd_return_markdown


def _wrap_return_block(yaml_body: str) -> str:
    return f"```yaml\ngpd_return:\n{yaml_body}```\n"


def test_accepts_nested_state_and_continuation_payloads() -> None:
    content = _wrap_return_block(
        "  status: checkpoint\n"
        "  files_written: [src/main.py]\n"
        "  issues: []\n"
        "  next_actions: [/gpd:resume-work]\n"
        "  state_updates:\n"
        "    advance_plan: true\n"
        "    update_progress: true\n"
        "  continuation_update:\n"
        "    handoff:\n"
        "      recorded_at: 2026-04-08T12:00:00Z\n"
        "      recorded_by: execute-plan\n"
        "      stopped_at: Completed phase 01\n"
        "      resume_file: GPD/phases/01-test-phase/.continue-here.md\n"
        "    bounded_segment:\n"
        "      resume_file: GPD/phases/01-test-phase/.continue-here.md\n"
        "      phase: 01\n"
        "      plan: 01\n"
        "      segment_id: seg-01\n"
        "      segment_status: paused\n"
        "      checkpoint_reason: segment_boundary\n"
    )

    result = validate_gpd_return_markdown(content)

    assert result.passed is True
    assert result.fields["state_updates"]["advance_plan"] is True
    assert result.fields["state_updates"]["update_progress"] is True
    assert result.fields["continuation_update"]["handoff"]["recorded_by"] == "execute-plan"
    assert result.fields["continuation_update"]["bounded_segment"]["segment_id"] == "seg-01"


def test_accepts_typed_checker_plan_lists() -> None:
    content = _wrap_return_block(
        "  status: checkpoint\n"
        "  files_written: []\n"
        "  issues: []\n"
        "  next_actions: [/gpd:plan-phase]\n"
        "  approved_plans: [plan-01, plan-03]\n"
        "  blocked_plans: [plan-02]\n"
    )

    result = validate_gpd_return_markdown(content)

    assert result.passed is True
    assert result.fields["approved_plans"] == ["plan-01", "plan-03"]
    assert result.fields["blocked_plans"] == ["plan-02"]


def test_rejects_scalar_where_list_field_is_required() -> None:
    content = _wrap_return_block(
        "  status: completed\n"
        "  files_written: src/main.py\n"
        "  issues: []\n"
        "  next_actions: [/gpd:verify-work]\n"
    )

    result = validate_gpd_return_markdown(content)

    assert result.passed is False
    assert any("files_written" in error and "list" in error for error in result.errors)


def test_rejects_malformed_checker_plan_lists() -> None:
    content = _wrap_return_block(
        "  status: checkpoint\n"
        "  files_written: []\n"
        "  issues: []\n"
        "  next_actions: [/gpd:plan-phase]\n"
        "  approved_plans: plan-01\n"
        "  blocked_plans:\n"
        "    - plan-02\n"
        "    - 3\n"
    )

    result = validate_gpd_return_markdown(content)

    assert result.passed is False
    assert any("approved_plans" in error and "list" in error for error in result.errors)
    assert any("blocked_plans" in error and "string" in error for error in result.errors)


def test_rejects_state_updates_when_not_a_mapping() -> None:
    content = _wrap_return_block(
        "  status: checkpoint\n"
        "  files_written: [src/main.py]\n"
        "  issues: []\n"
        "  next_actions: [/gpd:resume-work]\n"
        "  state_updates:\n"
        "    - advance_plan: true\n"
    )

    result = validate_gpd_return_markdown(content)

    assert result.passed is False
    assert any("state_updates" in error and "mapping" in error for error in result.errors)


def test_rejects_transport_execution_segment_inside_durable_continuation_update() -> None:
    content = _wrap_return_block(
        "  status: checkpoint\n"
        "  files_written: [src/main.py]\n"
        "  issues: []\n"
        "  next_actions: [/gpd:resume-work]\n"
        "  continuation_update:\n"
        "    execution_segment:\n"
        "      current_cursor: 3\n"
    )

    result = validate_gpd_return_markdown(content)

    assert result.passed is False
    assert any("continuation_update" in error and "execution_segment" in error for error in result.errors)


def test_rejects_scalar_where_continuation_update_requires_mapping() -> None:
    content = _wrap_return_block(
        "  status: blocked\n"
        "  files_written: []\n"
        "  issues: []\n"
        "  next_actions: []\n"
        "  blockers:\n"
        "    - missing input data\n"
        "  continuation_update: checkpoint\n"
    )

    result = validate_gpd_return_markdown(content)

    assert result.passed is False
    assert any("continuation_update" in error for error in result.errors)


def test_accepts_synthesizer_style_completed_return_with_summary_only_file_list() -> None:
    content = _wrap_return_block(
        "  status: completed\n"
        "  files_written: [GPD/literature/SUMMARY.md]\n"
        "  issues: []\n"
        "  next_actions: []\n"
    )

    result = validate_gpd_return_markdown(content)

    assert result.passed is True
    assert result.fields["status"] == "completed"
    assert result.fields["files_written"] == ["GPD/literature/SUMMARY.md"]
    assert result.fields["issues"] == []
    assert result.fields["next_actions"] == []
