"""Phase 11 assertions for the durable child-return continuation boundary."""

from __future__ import annotations

import json
from pathlib import Path

from gpd.core.commands import cmd_apply_return_updates
from gpd.core.return_contract import validate_gpd_return_markdown
from gpd.core.state import default_state_dict, generate_state_markdown


def _write_project_state(tmp_path: Path) -> Path:
    gpd_dir = tmp_path / "GPD"
    gpd_dir.mkdir()
    state = default_state_dict()
    (gpd_dir / "state.json").write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    (gpd_dir / "STATE.md").write_text(generate_state_markdown(state), encoding="utf-8")
    return gpd_dir


def _wrap_return_block(yaml_body: str) -> str:
    return f"```yaml\ngpd_return:\n{yaml_body}```\n"


def test_validate_and_apply_the_same_durable_continuation_payload(tmp_path: Path) -> None:
    gpd_dir = _write_project_state(tmp_path)
    return_file = tmp_path / "durable_return.md"
    return_file.write_text(
        _wrap_return_block(
            "  status: checkpoint\n"
            "  files_written: [GPD/state.json]\n"
            "  issues: []\n"
            "  next_actions: [/gpd:resume-work]\n"
            "  continuation_update:\n"
            "    handoff:\n"
            "      stopped_at: Completed phase 01\n"
            "      resume_file: GPD/phases/01-test-phase/.continue-here.md\n"
            "    bounded_segment:\n"
            "      resume_file: GPD/phases/01-test-phase/.continue-here.md\n"
            "      phase: 01\n"
            "      plan: 01\n"
            "      segment_id: seg-01\n"
            "      segment_status: paused\n"
            "      checkpoint_reason: segment_boundary\n"
        ),
        encoding="utf-8",
    )

    validation = validate_gpd_return_markdown(return_file.read_text(encoding="utf-8"))
    assert validation.passed is True
    assert validation.fields["continuation_update"]["handoff"]["stopped_at"] == "Completed phase 01"
    assert validation.fields["continuation_update"]["bounded_segment"]["segment_id"] == "seg-01"

    result = cmd_apply_return_updates(tmp_path, return_file)

    assert result.passed is True
    assert result.applied_continuation_operations == ["record_session", "set_bounded_segment"]

    updated_state = json.loads((gpd_dir / "state.json").read_text(encoding="utf-8"))
    assert updated_state["continuation"]["handoff"]["recorded_by"] == "state_record_session"
    assert updated_state["continuation"]["bounded_segment"]["segment_id"] == "seg-01"
