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
        "    resume_contract:\n"
        "      next_step: continue\n"
        "      required_artifacts:\n"
        "        - GPD/STATE.md\n"
        "    execution_segment:\n"
        "      current_cursor: 3\n"
        "      completed_tasks:\n"
        "        - task-1\n"
    )

    result = validate_gpd_return_markdown(content)

    assert result.passed is True
    assert result.fields["state_updates"]["advance_plan"] is True
    assert result.fields["state_updates"]["update_progress"] is True
    assert result.fields["continuation_update"]["execution_segment"]["current_cursor"] == 3


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
    assert any("continuation_update" in error and "mapping" in error for error in result.errors)
