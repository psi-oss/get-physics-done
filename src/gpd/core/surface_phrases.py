"""Canonical user-facing phrases for repeated command ladders.

Keep this module small and textual. It exists so core payload builders can
share one source of truth for recovery, visibility, preset, and cost honesty
phrasing without dragging docs or CLI renderers into the dependency surface.
"""

from __future__ import annotations

from gpd.core.workflow_presets import list_workflow_presets

__all__ = [
    "cost_after_runs_guidance",
    "cost_after_run_action",
    "cost_inspect_action",
    "cost_summary_surface_note",
    "local_cli_bridge_note",
    "recovery_ladder_note",
    "recovery_continue_action",
    "recovery_fast_next_action",
    "recovery_recent_action",
    "recovery_resume_action",
    "workflow_preset_storage_note",
    "workflow_preset_surface_note",
]


def recovery_resume_action() -> str:
    return "Run `gpd resume` to inspect the current recovery snapshot for this workspace."


def recovery_recent_action() -> str:
    return "Run `gpd resume --recent` to find the workspace you want to reopen on this machine."


def recovery_continue_action(*, mode: str, continue_command: str) -> str:
    continue_phrase = continue_command if continue_command.startswith("runtime `") else f"`{continue_command}`"
    if mode == "current-workspace":
        return f"{continue_phrase} continues paused work inside this workspace."
    return f"After selecting a workspace, use {continue_phrase} there to continue paused work."


def recovery_fast_next_action(*, fast_next_command: str) -> str:
    fast_next_phrase = fast_next_command if fast_next_command.startswith("runtime `") else f"`{fast_next_command}`"
    return f"{fast_next_phrase} is the fastest post-resume command when you only need the next action."


def cost_inspect_action() -> str:
    return (
        "Run `gpd cost` to inspect recorded machine-local usage / cost, optional USD budget guardrails, "
        "and the current profile tier mix for this workspace."
    )


def cost_after_run_action() -> str:
    return (
        "After a run, use `gpd cost` to inspect recorded machine-local usage / cost, optional USD budget "
        "guardrails, and the current profile tier mix for this workspace."
    )


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
