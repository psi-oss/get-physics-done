"""Shared semantic assertions for repeated documentation surface contracts."""

from __future__ import annotations

from collections.abc import Iterable
import re

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
    "assert_recovery_ladder_contract",
    "_assert_cost_advisory_contract",
    "_assert_cost_advisory_guardrail",
    "_assert_shared_preset_surface_contract",
    "_assert_unattended_readiness_boundary",
    "_assert_unattended_readiness_surface",
    "_assert_wolfram_plan_boundary",
    "assert_cost_advisory_contract",
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
_assert_cost_advisory_contract = assert_cost_advisory_contract
_assert_cost_advisory_guardrail = assert_cost_advisory_contract
_assert_shared_preset_surface_contract = assert_workflow_preset_surface_contract
_assert_unattended_readiness_boundary = assert_unattended_readiness_contract
_assert_unattended_readiness_surface = assert_unattended_readiness_contract
_assert_wolfram_plan_boundary = assert_wolfram_plan_boundary_contract
