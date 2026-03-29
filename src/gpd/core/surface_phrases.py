"""Canonical user-facing phrases for repeated command ladders.

Keep this module small and textual. It exists so core payload builders can
share one source of truth for recovery, visibility, preset, and cost honesty
phrasing without dragging docs or CLI renderers into the dependency surface.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from gpd.core.public_surface_contract import (
    local_cli_bridge_note as _public_local_cli_bridge_note,
    post_start_settings_note as _public_post_start_settings_note,
    post_start_settings_recommendation as _public_post_start_settings_recommendation,
)
from gpd.core.workflow_presets import list_workflow_presets

__all__ = [
    "command_follow_up_action",
    "cost_after_runs_guidance",
    "cost_after_run_action",
    "cost_inspect_action",
    "cost_summary_surface_note",
    "local_cli_bridge_note",
    "observe_execution_action",
    "observe_execution_surface_note",
    "observe_tangent_routing_note",
    "post_start_settings_note",
    "post_start_settings_recommendation",
    "recovery_action_lines",
    "recovery_ladder_note",
    "recovery_continue_action",
    "recovery_fast_next_action",
    "recovery_next_actions",
    "recovery_recent_action",
    "recovery_resume_action",
    "tangent_branch_later_action",
    "tangent_branch_later_follow_up_lines",
    "tangent_chooser_action",
    "workflow_preset_storage_note",
    "workflow_preset_surface_note",
]


def _command_phrase(command: str) -> str:
    return command if command.startswith(("runtime `", "the runtime `", "`")) else f"`{command}`"


def command_follow_up_action(*, command: str, reason: str) -> str:
    return f"Run `{command}` to {reason}."


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


def _action_field(action: object, field: str) -> str | None:
    if isinstance(action, Mapping):
        value = action.get(field)
    else:
        value = getattr(action, field, None)
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def recovery_action_lines(
    *,
    actions: Iterable[object],
    mode: str,
    existing_actions: Iterable[str] = (),
    allowed_availability: Iterable[str] | None = None,
    include_primary: bool = True,
) -> list[str]:
    existing = {action.strip() for action in existing_actions if action.strip()}
    allowed = {value.strip() for value in allowed_availability or () if isinstance(value, str) and value.strip()} or None
    rendered: list[str] = []

    for action in actions:
        availability = _action_field(action, "availability") or "now"
        if allowed is not None and availability not in allowed:
            continue

        kind = _action_field(action, "kind")
        command = _action_field(action, "command")
        line: str | None = None

        if kind == "primary":
            if not include_primary:
                continue
            if command == "gpd resume":
                line = recovery_resume_action()
            elif command == "gpd resume --recent":
                line = recovery_recent_action()
        elif kind == "continue" and command is not None:
            line = recovery_continue_action(mode=mode, continue_command=command)
        elif kind == "fast-next" and command is not None:
            line = recovery_fast_next_action(fast_next_command=command)

        if line is None or line in existing or line in rendered:
            continue
        rendered.append(line)

    return rendered


def recovery_next_actions(
    *,
    primary_command: str | None,
    mode: str,
    continue_command: str | None = None,
    fast_next_command: str | None = None,
    existing_actions: Iterable[str] = (),
) -> list[str]:
    structured_actions: list[dict[str, str]] = []
    if primary_command in {"gpd resume", "gpd resume --recent"}:
        structured_actions.append(
            {
                "kind": "primary",
                "command": primary_command,
                "availability": "now",
            }
        )

    if mode == "current-workspace":
        availability = "now"
    elif mode == "recent-projects":
        availability = "after_selection"
    else:
        availability = None

    if availability is not None:
        if isinstance(continue_command, str) and continue_command.strip():
            structured_actions.append(
                {
                    "kind": "continue",
                    "command": continue_command.strip(),
                    "availability": availability,
                }
            )
        if isinstance(fast_next_command, str) and fast_next_command.strip():
            structured_actions.append(
                {
                    "kind": "fast-next",
                    "command": fast_next_command.strip(),
                    "availability": availability,
                }
            )

    return recovery_action_lines(
        actions=structured_actions,
        mode=mode,
        existing_actions=existing_actions,
        allowed_availability={"now"},
        include_primary=True,
    )


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


def tangent_chooser_action() -> str:
    return (
        "Inside the runtime, use the `tangent` command to choose stay on the main path, "
        "run a bounded quick check, capture and defer, or open a hypothesis branch."
    )


def tangent_branch_later_action(
    *,
    tangent_phrase: str = "the runtime `tangent`",
    branch_phrase: str = "the runtime `branch-hypothesis`",
) -> str:
    tangent_text = _command_phrase(tangent_phrase)
    branch_text = _command_phrase(branch_phrase)
    return (
        f"After the bounded stop, use {tangent_text} command to keep the chooser explicit for this alternative path; "
        f"use {branch_text} command only if you decide to open a git-backed alternative path."
    )


def tangent_branch_later_follow_up_lines(
    *,
    tangent_phrase: str = "the runtime `tangent`",
    branch_phrase: str = "the runtime `branch-hypothesis`",
) -> list[str]:
    tangent_text = _command_phrase(tangent_phrase)
    branch_text = _command_phrase(branch_phrase)
    return [
        f"Use {tangent_text} command to keep the chooser explicit for this alternative path.",
        f"Use {branch_text} command only if you decide to open a git-backed alternative path after this bounded stop.",
    ]


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
    return _public_local_cli_bridge_note()


def post_start_settings_note() -> str:
    return _public_post_start_settings_note()


def post_start_settings_recommendation() -> str:
    return _public_post_start_settings_recommendation()


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
