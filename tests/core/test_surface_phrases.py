from __future__ import annotations

from gpd.core.surface_phrases import (
    command_follow_up_action,
    cost_after_run_action,
    cost_after_runs_guidance,
    cost_inspect_action,
    cost_summary_surface_note,
    local_cli_bridge_note,
    observe_execution_action,
    observe_execution_surface_note,
    observe_tangent_routing_note,
    recovery_action_lines,
    recovery_continue_action,
    recovery_fast_next_action,
    recovery_ladder_note,
    recovery_next_actions,
    recovery_recent_action,
    recovery_resume_action,
    tangent_chooser_action,
    workflow_preset_storage_note,
    workflow_preset_surface_note,
)


def test_cost_surface_phrases_stay_conservative_and_advisory() -> None:
    assert "gpd cost" in cost_inspect_action()
    assert "local usage/cost summary" in cost_inspect_action()
    assert "USD budget warnings" in cost_inspect_action()
    assert "gpd cost" in cost_after_run_action()
    assert "After a run" in cost_after_run_action()
    assert "local usage/cost" in cost_after_run_action()
    assert "USD budget warnings" in cost_after_run_action()
    assert "gpd cost" in cost_after_runs_guidance()
    assert "budget guardrails" in cost_after_runs_guidance()
    assert "billing truth" in cost_after_runs_guidance()
    assert "advisory only" in cost_summary_surface_note()
    assert "budget guardrails" in cost_summary_surface_note()
    assert "provider billing truth" in cost_summary_surface_note()
    assert "partial or estimated rather than exact" in cost_summary_surface_note()


def test_recovery_surface_phrases_cover_current_and_cross_project_paths() -> None:
    assert "gpd resume" in recovery_resume_action()
    assert "gpd resume --recent" in recovery_recent_action()
    assert (
        recovery_continue_action(mode="current-workspace", continue_command="codex-resume-work")
        == "`codex-resume-work` continues in-runtime from the selected project state."
    )
    assert (
        recovery_continue_action(mode="recent-projects", continue_command="runtime `resume-work`")
        == "After selecting a workspace, use runtime `resume-work` there to continue from the selected project state."
    )
    assert (
        recovery_fast_next_action(fast_next_command="/gpd:suggest-next")
        == "`/gpd:suggest-next` is the fastest post-resume next command when you only need the next action."
    )
    assert (
        recovery_ladder_note(
            resume_work_phrase="`/gpd:resume-work`",
            suggest_next_phrase="`/gpd:suggest-next`",
            pause_work_phrase="`/gpd:pause-work`",
        )
        == "Recovery ladder: use `gpd resume` for the current-workspace read-only recovery snapshot. If that is the wrong workspace, use `gpd resume --recent` to find the workspace first, then continue inside that workspace with `/gpd:resume-work`. After resuming, `/gpd:suggest-next` is the fastest next command. Before stepping away mid-phase, run `/gpd:pause-work` so that ladder has an explicit handoff to restore."
    )


def test_recovery_next_actions_respect_local_target_gating_and_resume_dedup() -> None:
    assert recovery_next_actions(
        primary_command="gpd resume",
        mode="current-workspace",
        continue_command="runtime `resume-work`",
        fast_next_command="runtime `suggest-next`",
        existing_actions=[recovery_resume_action()],
    ) == [
        recovery_continue_action(mode="current-workspace", continue_command="runtime `resume-work`"),
        recovery_fast_next_action(fast_next_command="runtime `suggest-next`"),
    ]


def test_recovery_action_lines_render_structured_actions_with_availability_filter() -> None:
    actions = [
        {"kind": "primary", "command": "gpd resume --recent", "availability": "now"},
        {"kind": "continue", "command": "runtime `resume-work`", "availability": "after_selection"},
        {"kind": "fast-next", "command": "runtime `suggest-next`", "availability": "after_selection"},
    ]

    assert recovery_action_lines(actions=actions, mode="recent-projects") == [
        recovery_recent_action(),
        recovery_continue_action(mode="recent-projects", continue_command="runtime `resume-work`"),
        recovery_fast_next_action(fast_next_command="runtime `suggest-next`"),
    ]
    assert recovery_action_lines(
        actions=actions,
        mode="recent-projects",
        allowed_availability={"now"},
    ) == [recovery_recent_action()]


def test_observe_surface_phrases_stay_read_only_and_route_follow_ups_explicitly() -> None:
    assert command_follow_up_action(command="gpd observe show --last 20", reason="inspect the recent execution trail") == (
        "Run `gpd observe show --last 20` to inspect the recent execution trail."
    )
    assert observe_execution_action() == (
        "Run `gpd observe execution` for read-only long-run visibility from your normal terminal."
    )
    assert observe_execution_surface_note() == (
        "Read-only long-run visibility from your normal terminal; use this for progress / waiting state, "
        "conservative `possibly stalled` wording, and the next read-only checks."
    )
    assert (
        observe_tangent_routing_note(
            tangent_phrase="/gpd:tangent",
            branch_phrase="/gpd:branch-hypothesis",
        )
        == "If `gpd observe execution` surfaces an alternative-path follow-up or `branch later` recommendation, route it through `/gpd:tangent` first; use `/gpd:branch-hypothesis` only after that explicit choice."
    )
    assert (
        observe_tangent_routing_note(
            tangent_phrase="runtime `tangent`",
            branch_phrase="runtime `branch-hypothesis`",
        )
        == "If `gpd observe execution` surfaces an alternative-path follow-up or `branch later` recommendation, route it through runtime `tangent` first; use runtime `branch-hypothesis` only after that explicit choice."
    )
    assert tangent_chooser_action() == (
        "Inside the runtime, use the `tangent` command to choose stay on the main path, "
        "run a bounded quick check, capture and defer, or open a hypothesis branch."
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
