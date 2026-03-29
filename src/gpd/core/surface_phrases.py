"""Canonical user-facing phrases for repeated command ladders.

Keep this module small and textual. It exists so core payload builders can
share one source of truth for recovery, visibility, preset, and cost honesty
phrasing without dragging docs or CLI renderers into the dependency surface.
"""

from __future__ import annotations

from collections.abc import Iterable

from gpd.core.workflow_presets import list_workflow_presets

__all__ = [
    "cost_after_runs_guidance",
    "cost_after_run_action",
    "cost_inspect_action",
    "cost_summary_surface_note",
    "local_cli_bridge_note",
    "observe_execution_action",
    "observe_execution_surface_note",
    "observe_tangent_routing_note",
    "recovery_ladder_note",
    "recovery_continue_action",
    "recovery_fast_next_action",
    "recovery_next_actions",
    "recovery_recent_action",
    "recovery_resume_action",
    "workflow_preset_storage_note",
    "workflow_preset_surface_note",
]


def _command_phrase(command: str) -> str:
    return command if command.startswith(("runtime `", "the runtime `", "`")) else f"`{command}`"


def recovery_resume_action() -> str:
    return "Run `gpd resume` to inspect the current-workspace read-only recovery snapshot."


def recovery_recent_action() -> str:
    return "Run `gpd resume --recent` to find the workspace first when you need to reopen a different one."


def recovery_continue_action(*, mode: str, continue_command: str) -> str:
    continue_phrase = _command_phrase(continue_command)
    if mode == "current-workspace":
        return f"{continue_phrase} continues in-runtime from the selected project state."
    return f"After selecting a workspace, use {continue_phrase} there to continue from the selected project state."


def recovery_fast_next_action(*, fast_next_command: str) -> str:
    fast_next_phrase = _command_phrase(fast_next_command)
    return f"{fast_next_phrase} is the fastest post-resume next command when you only need the next action."


def recovery_next_actions(
    *,
    primary_command: str | None,
    mode: str,
    continue_command: str | None = None,
    fast_next_command: str | None = None,
    existing_actions: Iterable[str] = (),
) -> list[str]:
    existing = {action.strip() for action in existing_actions if action.strip()}
    actions: list[str] = []

    if primary_command == "gpd resume":
        resume_action = recovery_resume_action()
        if resume_action not in existing:
            actions.append(resume_action)
    elif primary_command == "gpd resume --recent":
        recent_action = recovery_recent_action()
        if recent_action not in existing:
            actions.append(recent_action)
        return actions

    if mode != "current-workspace":
        return actions

    if isinstance(continue_command, str) and continue_command.strip():
        actions.append(recovery_continue_action(mode=mode, continue_command=continue_command.strip()))

    if isinstance(fast_next_command, str) and fast_next_command.strip():
        actions.append(recovery_fast_next_action(fast_next_command=fast_next_command.strip()))

    return actions


def observe_execution_action() -> str:
    return "Run `gpd observe execution` for read-only long-run visibility from your normal terminal."


def observe_execution_surface_note() -> str:
    return (
        "Read-only long-run visibility from your normal terminal; use this for progress / waiting state, "
        "conservative `possibly stalled` wording, and the next read-only checks."
    )


def observe_tangent_routing_note(*, tangent_phrase: str, branch_phrase: str) -> str:
    tangent_text = tangent_phrase if tangent_phrase.startswith(("runtime `", "the runtime `", "`")) else f"`{tangent_phrase}`"
    branch_text = branch_phrase if branch_phrase.startswith(("runtime `", "the runtime `", "`")) else f"`{branch_phrase}`"
    return (
        "If `gpd observe execution` surfaces an alternative-path follow-up or `branch later` recommendation, "
        f"route it through {tangent_text} first; use {branch_text} only after that explicit choice."
    )


def cost_inspect_action() -> str:
    return "Run `gpd cost` for the local usage/cost summary and any USD budget warnings."


def cost_after_run_action() -> str:
    return "After a run, check `gpd cost` for local usage/cost and any USD budget warnings."


def cost_after_runs_guidance() -> str:
    return (
        "Use `gpd cost` after runs to inspect recorded local usage / cost, optional USD budget guardrails, "
        "and the current profile tier mix instead of treating posture labels as billing truth."
    )


def cost_summary_surface_note() -> str:
    return (
        "Read-only machine-local usage / cost summary from recorded local telemetry, optional USD budget "
        "guardrails, and the current profile tier mix; advisory only, not live budget enforcement or provider "
        "billing truth. If telemetry is missing, the USD view stays partial or estimated rather than exact."
    )


def local_cli_bridge_note() -> str:
    return (
        "Use `gpd --help`, `gpd validate unattended-readiness --runtime <runtime> --autonomy balanced`, "
        "`gpd permissions status --runtime <runtime> --autonomy balanced`, "
        "`gpd permissions sync --runtime <runtime> --autonomy balanced`, `gpd resume`, "
        "`gpd resume --recent`, `gpd observe execution`, `gpd cost`, `gpd presets list`, and "
        "`gpd integrations status wolfram` from your normal terminal when you want the broader local "
        "diagnostics, readiness, recovery, visibility, cost, preset, and shared Wolfram integration surface."
    )


def recovery_ladder_note(
    *,
    resume_work_phrase: str,
    suggest_next_phrase: str,
    pause_work_phrase: str,
) -> str:
    return (
        "Recovery ladder: use `gpd resume` for the current-workspace read-only recovery snapshot. If that is "
        "the wrong workspace, use `gpd resume --recent` to find the workspace first, then continue inside "
        f"that workspace with {resume_work_phrase}. After resuming, {suggest_next_phrase} is the fastest next "
        f"command. Before stepping away mid-phase, run {pause_work_phrase} so that ladder has an explicit "
        "handoff to restore."
    )


def workflow_preset_storage_note() -> str:
    return "Workflow presets are bundles over the existing config keys only; they do not add a separate persisted preset block."


def workflow_preset_surface_note() -> str:
    preset_labels = ", ".join(preset.id for preset in list_workflow_presets())
    return (
        "Use `gpd presets list` to inspect the workflow preset catalog "
        f"({preset_labels}), `gpd presets show <preset>` to preview one bundle, "
        "and `gpd presets apply <preset> --dry-run` to preview the changed knobs "
        "before writing them."
    )
