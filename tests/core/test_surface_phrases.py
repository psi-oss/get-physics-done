from __future__ import annotations

from gpd.core.surface_phrases import (
    cost_after_run_action,
    cost_after_runs_guidance,
    cost_inspect_action,
    cost_summary_surface_note,
    local_cli_bridge_note,
    recovery_continue_action,
    recovery_fast_next_action,
    recovery_ladder_note,
    recovery_recent_action,
    recovery_resume_action,
    workflow_preset_storage_note,
    workflow_preset_surface_note,
)


def test_cost_surface_phrases_stay_conservative_and_advisory() -> None:
    assert "gpd cost" in cost_inspect_action()
    assert "machine-local usage / cost" in cost_inspect_action()
    assert "gpd cost" in cost_after_run_action()
    assert "After a run" in cost_after_run_action()
    assert "gpd cost" in cost_after_runs_guidance()
    assert "billing truth" in cost_after_runs_guidance()
    assert "advisory only" in cost_summary_surface_note()
    assert "provider billing truth" in cost_summary_surface_note()
    assert "partial or estimated rather than exact" in cost_summary_surface_note()


def test_recovery_surface_phrases_cover_current_and_cross_project_paths() -> None:
    assert "gpd resume" in recovery_resume_action()
    assert "gpd resume --recent" in recovery_recent_action()
    assert (
        recovery_continue_action(mode="current-workspace", continue_command="codex-resume-work")
        == "`codex-resume-work` continues paused work inside this workspace."
    )
    assert (
        recovery_continue_action(mode="recent-projects", continue_command="runtime `resume-work`")
        == "After selecting a workspace, use runtime `resume-work` there to continue paused work."
    )
    assert (
        recovery_fast_next_action(fast_next_command="/gpd:suggest-next")
        == "`/gpd:suggest-next` is the fastest post-resume command when you only need the next action."
    )
    assert (
        recovery_ladder_note(
            resume_work_phrase="`/gpd:resume-work`",
            suggest_next_phrase="`/gpd:suggest-next`",
            pause_work_phrase="`/gpd:pause-work`",
        )
        == "Recovery ladder: use `gpd resume` for the current-workspace read-only recovery snapshot. If that is the wrong workspace, use `gpd resume --recent` to find the workspace first, then continue inside that workspace with `/gpd:resume-work`. After resuming, `/gpd:suggest-next` is the fastest next command. Before stepping away mid-phase, run `/gpd:pause-work` so that ladder has an explicit handoff to restore."
    )


def test_preset_and_local_bridge_phrases_remain_command_oriented() -> None:
    assert workflow_preset_storage_note() == (
        "Workflow presets are bundles over the existing config keys only; they do not add a separate persisted preset block."
    )
    preset_note = workflow_preset_surface_note()
    for token in (
        "gpd presets list",
        "gpd presets show <preset>",
        "gpd presets apply <preset> --dry-run",
        "core-research",
        "theory",
        "numerics",
        "publication-manuscript",
        "full-research",
    ):
        assert token in preset_note

    bridge_note = local_cli_bridge_note()
    for token in (
        "gpd --help",
        "gpd validate unattended-readiness --runtime <runtime> --autonomy balanced",
        "gpd permissions status --runtime <runtime> --autonomy balanced",
        "gpd permissions sync --runtime <runtime> --autonomy balanced",
        "gpd resume",
        "gpd resume --recent",
        "gpd observe execution",
        "gpd cost",
        "gpd presets list",
        "gpd integrations status wolfram",
    ):
        assert token in bridge_note
