"""Shared semantic assertions for repeated documentation surface contracts."""

from __future__ import annotations

from collections.abc import Iterable
import re

from gpd.core.onboarding_surfaces import beginner_startup_ladder_text
from gpd.core.surface_phrases import post_start_settings_note, post_start_settings_recommendation

DOCTOR_RUNTIME_SCOPE_RE = re.compile(r"gpd doctor --runtime <runtime> --local\|--global")
UNATTENDED_READINESS_SURFACE = "gpd validate unattended-readiness"
PERMISSIONS_SYNC_SURFACE = "gpd permissions sync --runtime <runtime> --autonomy balanced"
PLAN_PREFLIGHT_SURFACE = "gpd validate plan-preflight <PLAN.md>"
WOLFRAM_STATUS_SURFACE = "gpd integrations status wolfram"

__all__ = [
    "DOCTOR_RUNTIME_SCOPE_RE",
    "PERMISSIONS_SYNC_SURFACE",
    "PLAN_PREFLIGHT_SURFACE",
    "UNATTENDED_READINESS_SURFACE",
    "WOLFRAM_STATUS_SURFACE",
    "assert_optional_paper_workflow_guidance_contract",
    "assert_publication_toolchain_boundary_contract",
    "assert_recovery_ladder_contract",
    "assert_runtime_readiness_handoff_contract",
    "assert_settings_local_terminal_follow_up_contract",
    "_assert_cost_surface_discoverability",
    "_assert_cost_advisory_contract",
    "_assert_cost_advisory_guardrail",
    "assert_cost_surface_discoverability",
    "_assert_shared_preset_surface_contract",
    "_assert_unattended_readiness_boundary",
    "_assert_unattended_readiness_surface",
    "_assert_wolfram_plan_boundary",
    "assert_cost_advisory_contract",
    "assert_beginner_startup_routing_contract",
    "assert_execution_observability_surface_contract",
    "assert_install_summary_runtime_follow_up_contract",
    "assert_shared_preset_surface_contract",
    "assert_unattended_readiness_boundary",
    "assert_unattended_readiness_contract",
    "assert_wolfram_plan_boundary",
    "assert_wolfram_plan_boundary_contract",
    "assert_workflow_preset_surface_contract",
]


def _assert_contains_any(content: str, fragments: Iterable[str], *, label: str) -> None:
    options = tuple(fragments)
    assert any(fragment in content for fragment in options), f"expected {label}; wanted one of {options!r}"


def assert_unattended_readiness_contract(content: str) -> None:
    assert UNATTENDED_READINESS_SURFACE in content
    assert PERMISSIONS_SYNC_SURFACE in content
    assert "gpd doctor" in content
    _assert_contains_any(
        content,
        (
            "runtime-owned approval/alignment only",
            "runtime-owned permission alignment",
            "Runtime permissions are",
        ),
        label="runtime-owned permissions/alignment boundary",
    )


def assert_cost_advisory_contract(content: str) -> None:
    assert_cost_surface_discoverability(content)
    _assert_contains_any(
        content,
        (
            "advisory only",
            "partial or estimated rather than exact",
            "partial or estimated when telemetry is missing",
            "estimated rather than exact",
            "not live budget enforcement",
            "billing truth",
        ),
        label="non-authoritative cost wording",
    )


def assert_cost_surface_discoverability(content: str) -> None:
    assert "gpd cost" in content
    _assert_contains_any(
        content,
        (
            "normal system terminal",
            "normal terminal",
            "Local CLI bridge",
            "after runs",
        ),
        label="local CLI cost surface",
    )
    _assert_contains_any(
        content,
        (
            "read-only machine-local usage / cost summary",
            "read-only machine-local usage/cost summary",
            "machine-local usage / cost",
            "machine-local usage/cost",
            "recorded local telemetry",
            "recorded local usage / cost",
            "recorded local usage/cost",
        ),
        label="machine-local usage/cost surface",
    )


def assert_execution_observability_surface_contract(content: str) -> None:
    assert "gpd observe execution" in content
    _assert_contains_any(
        content,
        (
            "progress / waiting state",
            "progress/waiting state",
        ),
        label="execution progress/waiting wording",
    )
    assert "possibly stalled" in content
    _assert_contains_any(
        content,
        (
            "read-only checks",
            "suggested read-only checks",
        ),
        label="read-only execution checks wording",
    )


def assert_beginner_startup_routing_contract(content: str) -> None:
    ladder = beginner_startup_ladder_text()
    _assert_contains_any(
        content,
        (
            ladder,
            ladder.strip("`"),
            "If you just installed GPD, use this order first:",
            "If you only remember one order, use this:",
        ),
        label="startup order surface",
    )
    _assert_contains_any(
        content,
        (
            "`start`",
            "/gpd:start",
            "$gpd-start",
            "/gpd-start",
            "Run `start`",
        ),
        label="start entry point",
    )
    _assert_contains_any(
        content,
        (
            "`tour`",
            "/gpd:tour",
            "$gpd-tour",
            "/gpd-tour",
            "Run `tour`",
        ),
        label="tour entry point",
    )
    _assert_contains_any(
        content,
        (
            "`new-project --minimal`",
            "/gpd:new-project --minimal",
            "$gpd-new-project --minimal",
            "/gpd-new-project --minimal",
            "`new-project`",
            "/gpd:new-project",
        ),
        label="new-project entry point",
    )
    _assert_contains_any(
        content,
        (
            "`map-research`",
            "/gpd:map-research",
            "$gpd-map-research",
            "/gpd-map-research",
        ),
        label="map-research entry point",
    )
    _assert_contains_any(
        content,
        (
            "`resume-work`",
            "/gpd:resume-work",
            "$gpd-resume-work",
            "/gpd-resume-work",
        ),
        label="resume-work entry point",
    )


def assert_recovery_ladder_contract(
    content: str,
    *,
    resume_work_fragments: Iterable[str],
    suggest_next_fragments: Iterable[str],
    pause_work_fragments: Iterable[str],
) -> None:
    assert "gpd resume" in content
    assert "gpd resume --recent" in content
    _assert_contains_any(
        content,
        (
            "current-workspace read-only recovery snapshot",
            "current recovery snapshot for this workspace",
        ),
        label="current-workspace recovery snapshot wording",
    )
    _assert_contains_any(
        content,
        (
            "find the workspace first",
            "find the workspace before resuming it",
            "wrong workspace",
            "find the workspace you want to reopen",
            "find the workspace you need to reopen",
        ),
        label="cross-workspace recovery discovery wording",
    )
    _assert_contains_any(content, tuple(resume_work_fragments), label="resume-work continuation surface")
    _assert_contains_any(
        content,
        (
            "continue from the selected project state",
            "continue there",
            "continue inside that workspace",
            "continue paused work",
        ),
        label="resume continuation semantics",
    )
    _assert_contains_any(content, tuple(suggest_next_fragments), label="post-resume next-command surface")
    _assert_contains_any(
        content,
        (
            "fastest next command",
            "fastest post-resume next command",
            "fastest post-resume command when you only need the next action",
            "when you only need the next action",
        ),
        label="fast post-resume next-command wording",
    )
    _assert_contains_any(content, tuple(pause_work_fragments), label="pause-work handoff surface")
    _assert_contains_any(
        content,
        (
            "explicit handoff to restore",
            "context handoff",
            "session continuity",
        ),
        label="pause/resume handoff semantics",
    )


def assert_runtime_readiness_handoff_contract(content: str) -> None:
    assert "gpd doctor" in content
    assert UNATTENDED_READINESS_SURFACE in content
    _assert_contains_any(
        content,
        (
            "install and runtime-local readiness",
            "runtime-local readiness",
            "runtime-readiness check",
        ),
        label="runtime-local readiness handoff",
    )
    _assert_contains_any(
        content,
        (
            "gpd permissions ...",
            PERMISSIONS_SYNC_SURFACE,
            "runtime-owned permission alignment and sync",
            "runtime-owned permission alignment",
        ),
        label="runtime-owned permission handoff",
    )


def assert_install_summary_runtime_follow_up_contract(
    content: str,
    *,
    runtime_help_fragments: Iterable[str] = (),
) -> None:
    assert "gpd --help" in content
    _assert_contains_any(
        content,
        (
            "local install, readiness, validation, permissions, observability, and diagnostics",
            "local install/readiness/permissions/diagnostics surface directly",
            "local CLI for install, readiness checks, permissions, observability, validation, and diagnostics",
        ),
        label="local CLI install/readiness follow-up surface",
    )
    help_fragments = tuple(fragment for fragment in runtime_help_fragments if fragment)
    if help_fragments:
        _assert_contains_any(content, help_fragments, label="runtime help follow-up surface")
    assert "gpd doctor" in content
    _assert_contains_any(
        content,
        (
            "Verify or troubleshoot this machine",
            "focused readiness check",
            "gpd doctor --runtime",
        ),
        label="doctor follow-up surface",
    )
    assert post_start_settings_note() in content
    assert post_start_settings_recommendation() in content
    _assert_contains_any(
        content,
        (
            "paper/manuscript workflows",
            "Paper/manuscript workflows",
        ),
        label="paper/manuscript workflow follow-up",
    )
    assert "Workflow Presets" in content
    assert "LaTeX Toolchain" in content
    _assert_contains_any(
        content,
        (
            "before publication work",
            "check whether `Workflow Presets` is `ready` or `degraded`",
        ),
        label="publication workflow follow-up timing",
    )
    assert "gpd presets list" in content
    _assert_contains_any(
        content,
        (
            "workflow preset surface",
            "workflow preset catalog",
        ),
        label="workflow preset follow-up",
    )


def assert_settings_local_terminal_follow_up_contract(content: str) -> None:
    assert "gpd --help" in content
    _assert_contains_any(
        content,
        (
            "Terminal follow-ups for these settings",
            "normal-terminal follow-up",
            "normal terminal",
            "normal system terminal",
            "local CLI entrypoint",
        ),
        label="settings local terminal follow-up framing",
    )
    assert UNATTENDED_READINESS_SURFACE in content
    _assert_contains_any(
        content,
        (
            PERMISSIONS_SYNC_SURFACE,
            "gpd permissions sync --runtime <runtime> --autonomy <mode>",
            "gpd permissions status --runtime <runtime> --autonomy balanced",
        ),
        label="settings runtime-permission follow-up surface",
    )
    assert "gpd cost" in content
    assert "gpd doctor" in content
    assert PLAN_PREFLIGHT_SURFACE in content
    assert WOLFRAM_STATUS_SURFACE in content
    assert "gpd presets list" in content
    assert "gpd presets show <preset>" in content
    assert "gpd presets apply <preset> --dry-run" in content


def assert_optional_paper_workflow_guidance_contract(content: str) -> None:
    _assert_contains_any(
        content,
        (
            "Paper/manuscript workflows",
            "paper/manuscript workflows",
            "plan paper/manuscript workflows",
            "plan to use that preset",
        ),
        label="paper/manuscript workflow mention",
    )
    _assert_contains_any(
        content,
        (
            "paper-toolchain readiness",
            "check whether `Workflow Presets` is `ready` or `degraded`.",
            "Workflow Presets",
        ),
        label="paper workflow readiness surface",
    )
    _assert_contains_any(
        content,
        (
            "Missing preset tooling degrades that preset; it does not block the base GPD install.",
            "degrade `write-paper`",
            "degraded readiness for `write-paper`",
            "Without LaTeX, the paper/manuscript and full research presets remain usable for `write-paper` and `peer-review`",
        ),
        label="optional paper workflow degradation guidance",
    )

def assert_publication_toolchain_boundary_contract(content: str) -> None:
    _assert_contains_any(
        content,
        (
            "Use `gpd paper-build` to judge whether the manuscript scaffold is buildable.",
            "`paper-build` remains the build contract",
            "`paper-build` and `arxiv-submission` require the `LaTeX Toolchain`.",
            "but `paper-build` and `arxiv-submission` require the `LaTeX Toolchain`.",
        ),
        label="paper-build boundary",
    )
    _assert_contains_any(
        content,
        (
            "`arxiv-submission` requires the built manuscript",
            "`paper-build` and `arxiv-submission` require the `LaTeX Toolchain`.",
            "but `paper-build` and `arxiv-submission` require the `LaTeX Toolchain`.",
        ),
        label="arxiv-submission boundary",
    )


def assert_workflow_preset_surface_contract(content: str) -> None:
    assert "gpd presets list" in content
    assert "gpd presets show <preset>" in content
    assert "gpd presets apply <preset>" in content
    _assert_contains_any(
        content,
        (
            "existing config keys",
            "bundles over the existing config keys only",
        ),
        label="existing-config-key wording",
    )
    _assert_contains_any(
        content,
        (
            "separate persisted preset block",
            "do not add a separate persisted preset block",
            "separate preset schema",
            "preset block",
        ),
        label="no separate preset persistence/schema wording",
    )


def assert_wolfram_plan_boundary_contract(content: str) -> None:
    assert WOLFRAM_STATUS_SURFACE in content
    assert PLAN_PREFLIGHT_SURFACE in content
    _assert_contains_any(
        content,
        (
            "Mathematica",
            "local Mathematica",
            "Wolfram Language",
            "shared Wolfram integration",
        ),
        label="local Mathematica boundary",
    )
    _assert_contains_any(
        content,
        (
            "plan readiness",
            "plan is ready to run",
            "plan gate",
            "does not replace `gpd validate plan-preflight <PLAN.md>`",
            "stays separate from `gpd validate plan-preflight <PLAN.md>`",
        ),
        label="plan-readiness boundary",
    )


assert_shared_preset_surface_contract = assert_workflow_preset_surface_contract
assert_unattended_readiness_boundary = assert_unattended_readiness_contract
assert_wolfram_plan_boundary = assert_wolfram_plan_boundary_contract
_assert_cost_surface_discoverability = assert_cost_surface_discoverability
_assert_cost_advisory_contract = assert_cost_advisory_contract
_assert_cost_advisory_guardrail = assert_cost_advisory_contract
_assert_shared_preset_surface_contract = assert_workflow_preset_surface_contract
_assert_settings_local_terminal_follow_up_contract = assert_settings_local_terminal_follow_up_contract
_assert_unattended_readiness_boundary = assert_unattended_readiness_contract
_assert_unattended_readiness_surface = assert_unattended_readiness_contract
_assert_wolfram_plan_boundary = assert_wolfram_plan_boundary_contract
