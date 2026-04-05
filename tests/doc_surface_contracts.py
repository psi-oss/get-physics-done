"""Shared semantic assertions for repeated documentation surface contracts."""

from __future__ import annotations

import re
from collections.abc import Iterable
from functools import lru_cache

from gpd.core.public_surface_contract import load_public_surface_contract
from gpd.core.resume_surface import RESUME_COMPATIBILITY_ALIAS_FIELDS
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
    "assert_cost_advisory_contract",
    "assert_cost_surface_discoverability",
    "assert_execution_observability_surface_contract",
    "assert_help_command_quick_start_extract_contract",
    "assert_help_start_tour_ordering_contract",
    "assert_help_workflow_quick_start_taxonomy_contract",
    "assert_help_workflow_runtime_reference_contract",
    "assert_install_summary_runtime_follow_up_contract",
    "assert_optional_paper_workflow_guidance_contract",
    "assert_post_start_settings_bridge_contract",
    "assert_publication_toolchain_boundary_contract",
    "assert_beginner_caveat_follow_up_contract",
    "assert_beginner_help_bridge_contract",
    "assert_beginner_hub_preflight_contract",
    "assert_beginner_preflight_notice_contract",
    "assert_beginner_router_bridge_contract",
    "assert_beginner_startup_routing_contract",
    "assert_recovery_ladder_contract",
    "assert_runtime_reset_rediscovery_contract",
    "assert_resume_authority_contract",
    "assert_runtime_readiness_handoff_contract",
    "assert_settings_local_terminal_follow_up_contract",
    "assert_start_workflow_router_contract",
    "assert_tour_command_surface_contract",
    "assert_tour_read_only_teaching_contract",
    "assert_unattended_readiness_contract",
    "assert_wolfram_plan_boundary_contract",
    "assert_workflow_preset_surface_contract",
    "resume_authority_public_vocabulary_intro",
    "resume_compat_alias_fields",
]


HELP_ENTRY_FRAGMENTS = (
    "`help`",
    "/gpd:help",
    "$gpd-help",
    "/gpd-help",
    "run `help`",
    "help command",
)
START_ENTRY_FRAGMENTS = (
    "`start`",
    "/gpd:start",
    "$gpd-start",
    "/gpd-start",
    "Run `start`",
)
TOUR_ENTRY_FRAGMENTS = (
    "`tour`",
    "/gpd:tour",
    "$gpd-tour",
    "/gpd-tour",
    "Run `tour`",
)


def _assert_contains_any(content: str, fragments: Iterable[str], *, label: str) -> None:
    options = tuple(fragments)
    assert any(fragment in content for fragment in options), f"expected {label}; wanted one of {options!r}"


def _first_index_of_any(content: str, fragments: Iterable[str], *, label: str) -> int:
    options = tuple(fragments)
    positions = [content.index(fragment) for fragment in options if fragment in content]
    assert positions, f"expected {label}; wanted one of {options!r}"
    return min(positions)


@lru_cache(maxsize=1)
def _public_surface_contract_payload() -> dict[str, object]:
    contract = load_public_surface_contract()
    payload = {
        "schema_version": 1,
        "beginner_onboarding": {
            "hub_url": contract.beginner_onboarding.hub_url,
            "preflight_requirements": list(contract.beginner_onboarding.preflight_requirements),
            "caveats": list(contract.beginner_onboarding.caveats),
            "startup_ladder": list(contract.beginner_onboarding.startup_ladder),
        },
        "local_cli_bridge": {
            "commands": list(contract.local_cli_bridge.commands),
            "named_commands": {
                "help": contract.local_cli_bridge.named_commands.help,
                "doctor": contract.local_cli_bridge.named_commands.doctor,
                "unattended_readiness": contract.local_cli_bridge.named_commands.unattended_readiness,
                "permissions_status": contract.local_cli_bridge.named_commands.permissions_status,
                "permissions_sync": contract.local_cli_bridge.named_commands.permissions_sync,
                "resume": contract.local_cli_bridge.named_commands.resume,
                "resume_recent": contract.local_cli_bridge.named_commands.resume_recent,
                "observe_execution": contract.local_cli_bridge.named_commands.observe_execution,
                "cost": contract.local_cli_bridge.named_commands.cost,
                "presets_list": contract.local_cli_bridge.named_commands.presets_list,
                "integrations_status_wolfram": contract.local_cli_bridge.named_commands.integrations_status_wolfram,
            },
            "terminal_phrase": contract.local_cli_bridge.terminal_phrase,
            "purpose_phrase": contract.local_cli_bridge.purpose_phrase,
        },
        "post_start_settings": {
            "primary_sentence": contract.post_start_settings.primary_sentence,
            "default_sentence": contract.post_start_settings.default_sentence,
        },
        "resume_authority": {
            "durable_authority_phrase": contract.resume_authority.durable_authority_phrase,
            "public_vocabulary_intro": contract.resume_authority.public_vocabulary_intro,
            "public_fields": list(contract.resume_authority.public_fields),
            "top_level_boundary_phrase": contract.resume_authority.top_level_boundary_phrase,
        },
        "recovery_ladder": {
            "title": contract.recovery_ladder.title,
            "local_snapshot_command": contract.recovery_ladder.local_snapshot_command,
            "local_snapshot_phrase": contract.recovery_ladder.local_snapshot_phrase,
            "cross_workspace_command": contract.recovery_ladder.cross_workspace_command,
            "cross_workspace_phrase": contract.recovery_ladder.cross_workspace_phrase,
            "resume_phrase": contract.recovery_ladder.resume_phrase,
            "next_phrase": contract.recovery_ladder.next_phrase,
            "pause_phrase": contract.recovery_ladder.pause_phrase,
        },
    }
    assert isinstance(payload, dict), "public surface contract must be a JSON object"
    assert set(payload) == {
        "schema_version",
        "beginner_onboarding",
        "local_cli_bridge",
        "post_start_settings",
        "resume_authority",
        "recovery_ladder",
    }
    assert payload["schema_version"] == 1
    return payload


def _contract_section(name: str) -> dict[str, object]:
    section = _public_surface_contract_payload()[name]
    assert isinstance(section, dict), f"{name} must be a JSON object"
    return dict(section)


def _contract_string(section: dict[str, object], key: str, *, label: str) -> str:
    value = section[key]
    assert isinstance(value, str) and value.strip(), f"{label}.{key} must be a non-empty string"
    return value.strip()


def _contract_string_list(section: dict[str, object], key: str, *, label: str) -> tuple[str, ...]:
    value = section[key]
    assert isinstance(value, list) and value, f"{label}.{key} must be a non-empty list"
    items: list[str] = []
    seen: set[str] = set()
    for item in value:
        assert isinstance(item, str) and item.strip(), f"{label}.{key} entries must be non-empty strings"
        normalized = item.strip()
        if normalized in seen:
            continue
        seen.add(normalized)
        items.append(normalized)
    return tuple(items)


def beginner_preflight_requirements() -> tuple[str, ...]:
    section = _contract_section("beginner_onboarding")
    return _contract_string_list(section, "preflight_requirements", label="beginner_onboarding")


def beginner_onboarding_caveats() -> tuple[str, ...]:
    section = _contract_section("beginner_onboarding")
    return _contract_string_list(section, "caveats", label="beginner_onboarding")


def beginner_startup_ladder() -> tuple[str, ...]:
    section = _contract_section("beginner_onboarding")
    return _contract_string_list(section, "startup_ladder", label="beginner_onboarding")


def beginner_startup_ladder_text() -> str:
    return "`" + " -> ".join(beginner_startup_ladder()) + "`"


def _resume_authority_contract() -> dict[str, object]:
    section = _contract_section("resume_authority")
    required_keys = {
        "durable_authority_phrase",
        "public_vocabulary_intro",
        "public_fields",
        "top_level_boundary_phrase",
    }
    assert required_keys.issubset(section)
    assert not (set(section) - required_keys)
    _contract_string(section, "durable_authority_phrase", label="resume_authority")
    _contract_string(section, "public_vocabulary_intro", label="resume_authority")
    _contract_string_list(section, "public_fields", label="resume_authority")
    _contract_string(section, "top_level_boundary_phrase", label="resume_authority")
    return section


def resume_authority_public_vocabulary_intro() -> str:
    section = _resume_authority_contract()
    return _contract_string(section, "public_vocabulary_intro", label="resume_authority")


def resume_compat_alias_fields() -> tuple[str, ...]:
    return RESUME_COMPATIBILITY_ALIAS_FIELDS


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


def assert_help_start_tour_ordering_contract(content: str) -> None:
    help_index = _first_index_of_any(content, HELP_ENTRY_FRAGMENTS, label="help entry point")
    start_index = _first_index_of_any(content, START_ENTRY_FRAGMENTS, label="start entry point")
    tour_index = _first_index_of_any(content, TOUR_ENTRY_FRAGMENTS, label="tour entry point")

    assert help_index < start_index
    assert start_index < tour_index


def assert_help_command_quick_start_extract_contract(content: str) -> None:
    _assert_contains_any(
        content,
        (
            "workflow-owned reference",
            "workflow-owned `## Quick Start` section",
        ),
        label="help command quick-start wrapper framing",
    )
    _assert_contains_any(
        content,
        (
            "Start at `# GPD Command Reference`.",
            "Start at `# GPD Command Reference`",
        ),
        label="help command quick-start reference anchor",
    )
    _assert_contains_any(
        content,
        (
            "Include the workflow-owned `## Invocation Surfaces` section.",
            "`## Invocation Surfaces` section",
        ),
        label="help command invocation-surfaces extract boundary",
    )
    _assert_contains_any(
        content,
        (
            "Include the workflow-owned `## Quick Start` section.",
            "`## Quick Start` section",
        ),
        label="help command quick-start extract boundary",
    )
    _assert_contains_any(
        content,
        (
            "Stop before `## Core Workflow`.",
            "before `## Core Workflow`",
        ),
        label="help command core-workflow cutoff boundary",
    )
    _assert_contains_any(
        content,
        (
            "Run \\`/gpd:help --all\\` for the full command reference.",
            "`/gpd:help --all` for the full command reference",
            "`/gpd:help --all`",
        ),
        label="help command full-reference follow-up",
    )


def assert_help_workflow_quick_start_taxonomy_contract(content: str) -> None:
    for label, options in (
        ("quick-start new-work group", ("**New work**", "New work")),
        ("quick-start existing-work group", ("**Existing work**", "Existing work")),
        ("quick-start returning-work group", ("**Returning work**", "Returning work")),
        ("quick-start post-startup settings group", ("**Post-startup settings**", "Post-startup settings")),
        ("quick-start tangents group", ("**Tangents**", "Tangents")),
        ("quick-start workflow presets group", ("**Workflow presets**", "Workflow presets")),
        ("quick-start Wolfram integration group", ("**Wolfram integration**", "Wolfram integration")),
    ):
        _assert_contains_any(content, options, label=label)

    for label, options in (
        ("quick-start start command", ("/gpd:start", "`/gpd:start`")),
        ("quick-start tour command", ("/gpd:tour", "`/gpd:tour`")),
        ("quick-start new-project command", ("/gpd:new-project", "`/gpd:new-project`")),
        ("quick-start map-research command", ("/gpd:map-research", "`/gpd:map-research`")),
        ("quick-start resume-work command", ("/gpd:resume-work", "`/gpd:resume-work`")),
        ("quick-start settings command", ("/gpd:settings", "`/gpd:settings`")),
    ):
        _assert_contains_any(content, options, label=label)

    _assert_contains_any(
        content,
        (
            "Primary guided unattended/autonomy setup after project creation",
            "guided unattended/autonomy setup",
            "after your first successful start or later",
        ),
        label="quick-start post-startup settings guidance",
    )


def assert_tour_read_only_teaching_contract(content: str) -> None:
    _assert_contains_any(
        content,
        (
            "guided tour",
            "guided beginner walkthrough",
            "read-only tour of the main GPD commands",
            "read-only overview of the broader command surface",
        ),
        label="tour teaching surface",
    )
    _assert_contains_any(
        content,
        (
            "read-only tour",
            "read-only walkthrough",
            "without taking action",
            "not change your files",
        ),
        label="tour read-only framing",
    )
    _assert_contains_any(
        content,
        (
            "Teach what the main commands do, when to use them",
            "what the main commands do",
            "what GPD can do before choosing",
            "overview before I continue",
        ),
        label="tour teaching semantics",
    )
    _assert_contains_any(
        content,
        (
            "not a chooser",
            "does not create files, change project",
            "route into another workflow",
            "without changing anything",
        ),
        label="tour non-routing boundary",
    )


def assert_tour_command_surface_contract(content: str) -> None:
    assert_tour_read_only_teaching_contract(content)
    for token in (
        "/gpd:start",
        "/gpd:new-project --minimal",
        "/gpd:new-project",
        "/gpd:map-research",
        "gpd resume",
        "/gpd:resume-work",
        "/gpd:suggest-next",
        "/gpd:progress",
        "/gpd:explain",
        "/gpd:quick",
        "/gpd:settings",
        "/gpd:help",
    ):
        assert token in content

    assert "What comes later after startup" in content
    for token in ("/gpd:discuss-phase", "/gpd:write-paper", "/gpd:tangent"):
        assert token in content

    _assert_contains_any(
        content,
        (
            "Normal terminal vs runtime",
            "the normal terminal, where you install GPD",
            "the runtime, where you use the GPD command prefix",
        ),
        label="tour terminal/runtime distinction",
    )
    _assert_contains_any(
        content,
        (
            "Use `gpd resume` first",
            "gpd resume` is the normal-terminal recovery step",
            "resume-work` is the in-runtime continue command",
        ),
        label="tour resume boundary",
    )
    _assert_contains_any(
        content,
        (
            "after your first successful start or later",
            "change autonomy, permissions, or runtime preferences",
            "change permissions, autonomy, or runtime preferences",
        ),
        label="tour settings follow-up boundary",
    )
    assert "Do not ask the user to pick a branch and do not continue into another workflow." in content


def assert_beginner_startup_routing_contract(content: str) -> None:
    ladder = beginner_startup_ladder_text()
    startup_markers = (
        ladder,
        ladder.strip("`"),
        "If you just installed GPD, use this order first:",
        "If you only remember one order, use this:",
    )
    new_project_fragments = (
        "`new-project --minimal`",
        "/gpd:new-project --minimal",
        "$gpd-new-project --minimal",
        "/gpd-new-project --minimal",
        "`new-project`",
        "/gpd:new-project",
    )
    map_research_fragments = (
        "`map-research`",
        "/gpd:map-research",
        "$gpd-map-research",
        "/gpd-map-research",
    )
    resume_work_fragments = (
        "`resume-work`",
        "/gpd:resume-work",
        "$gpd-resume-work",
        "/gpd-resume-work",
    )

    _assert_contains_any(
        content,
        startup_markers,
        label="startup order surface",
    )
    startup_anchor = min(content.index(marker) for marker in startup_markers if marker in content)
    startup_content = content[startup_anchor:]

    assert_help_start_tour_ordering_contract(startup_content)
    tour_index = _first_index_of_any(startup_content, TOUR_ENTRY_FRAGMENTS, label="tour entry point")
    new_project_index = _first_index_of_any(startup_content, new_project_fragments, label="new-project entry point")
    map_research_index = _first_index_of_any(startup_content, map_research_fragments, label="map-research entry point")
    resume_work_index = _first_index_of_any(startup_content, resume_work_fragments, label="resume-work entry point")

    assert tour_index < new_project_index
    assert tour_index < map_research_index
    assert tour_index < resume_work_index


def assert_start_workflow_router_contract(content: str) -> None:
    _assert_contains_any(
        content,
        (
            "Give a first-run chooser for people who may not know GPD yet.",
            "first-run chooser",
        ),
        label="start chooser purpose",
    )
    _assert_contains_any(
        content,
        (
            "Explain the folder state in plain English",
            "plain English summaries",
            "plain English",
        ),
        label="start plain-English routing",
    )
    _assert_contains_any(
        content,
        (
            "chooser, not a second implementation",
            "not a parallel onboarding state machine",
            "first-stop chooser",
        ),
        label="start chooser-vs-executor boundary",
    )
    _assert_contains_any(
        content,
        (
            "Reply with the number or the option name.",
            "Ask for exactly one choice.",
        ),
        label="start single-choice prompt",
    )

    for token in (
        "Recommended next steps:",
        "Other useful options",
        "/gpd:resume-work",
        "/gpd:progress",
        "/gpd:suggest-next",
        "/gpd:quick",
        "/gpd:tour",
        "/gpd:map-research",
        "/gpd:new-project --minimal",
        "/gpd:new-project",
        "/gpd:explain",
        "/gpd:help --all",
        "Follow the installed `/gpd:new-project --minimal` command contract directly",
        "Follow the installed `/gpd:new-project` command contract directly",
        "Follow the installed `/gpd:help --all` command contract directly",
    ):
        assert token in content

    assert "gpd resume --recent" in content
    _assert_contains_any(
        content,
        (
            "normal-terminal recovery command",
            "normal terminal to find the project first",
            "This is a normal-terminal recovery command",
            "normal-terminal recent-project picker",
            "choose the project explicitly",
        ),
        label="start normal-terminal recovery boundary",
    )
    _assert_contains_any(
        content,
        (
            "broader capability overview",
            "planning phases, verifying work, writing papers, and handling tangents",
        ),
        label="start tour handoff boundary",
    )
    _assert_contains_any(
        content,
        (
            "workflow-exempt command",
            "not a parallel onboarding state machine",
            "chooser, not a second implementation",
        ),
        label="start routing/chooser boundary",
    )


def assert_beginner_router_bridge_contract(content: str) -> None:
    assert "npx -y get-physics-done" in content
    _assert_contains_any(
        content,
        (
            "Use this post-install order:",
            "Run its help command first:",
            "Then choose the path that matches your starting point:",
            "Open your runtime, run its help command first",
        ),
        label="beginner router framing",
    )
    _assert_contains_any(
        content,
        (
            "/gpd:help",
            "$gpd-help",
            "/gpd-help",
            "help command",
        ),
        label="runtime help bridge",
    )
    _assert_contains_any(
        content,
        (
            "`start`",
            "/gpd:start",
            "$gpd-start",
            "/gpd-start",
            "runtime's `start` command",
            "use `start`",
        ),
        label="start routing surface",
    )
    _assert_contains_any(
        content,
        (
            "`tour`",
            "/gpd:tour",
            "$gpd-tour",
            "/gpd-tour",
            "runtime's `tour` command",
            "use `tour`",
        ),
        label="tour routing surface",
    )
    _assert_contains_any(
        content,
        (
            "`new-project --minimal`",
            "`new-project`",
            "/gpd:new-project",
            "$gpd-new-project",
            "/gpd-new-project",
        ),
        label="new-project routing surface",
    )
    _assert_contains_any(
        content,
        (
            "`map-research`",
            "/gpd:map-research",
            "$gpd-map-research",
            "/gpd-map-research",
        ),
        label="map-research routing surface",
    )
    _assert_contains_any(
        content,
        (
            "`resume-work`",
            "/gpd:resume-work",
            "$gpd-resume-work",
            "/gpd-resume-work",
        ),
        label="resume-work routing surface",
    )
    assert "gpd --help" in content
    _assert_contains_any(
        content,
        (
            "Use your runtime-specific `settings` command",
            "runtime's `settings` command",
            "For post-startup configuration, use your runtime's `settings` command",
        ),
        label="post-startup settings bridge",
    )


def assert_post_start_settings_bridge_contract(content: str) -> None:
    _assert_contains_any(
        content,
        (
            post_start_settings_note(),
            "After your first successful start or later, use your runtime's `settings` command",
            "For post-startup configuration, use your runtime's `settings` command",
        ),
        label="post-start settings bridge",
    )


def assert_beginner_help_bridge_contract(content: str) -> None:
    _assert_contains_any(
        content,
        (
            "Run its help command first:",
            "Open your runtime, run its help command first",
            "help command",
        ),
        label="beginner help bridge framing",
    )
    _assert_contains_any(
        content,
        (
            "/gpd:help",
            "$gpd-help",
            "/gpd-help",
            "help command",
        ),
        label="runtime help bridge",
    )
    assert "gpd --help" in content
    _assert_contains_any(
        content,
        (
            "normal system terminal",
            "normal terminal",
        ),
        label="local cli bridge",
    )


def assert_beginner_preflight_notice_contract(content: str) -> None:
    _assert_contains_any(
        content,
        (
            "Bootstrap preflight checks runtime launcher/target blockers only",
            "runtime launcher/target blockers only",
        ),
        label="bootstrap preflight scope",
    )
    _assert_contains_any(
        content,
        (
            "do the first successful startup before changing unattended behavior",
            "first successful startup before changing unattended behavior",
        ),
        label="bootstrap preflight startup caveat",
    )


def assert_beginner_caveat_follow_up_contract(content: str) -> None:
    _assert_contains_any(
        content,
        (
            "Recommended unattended default: Balanced autonomy (`balanced`).",
            "Balanced autonomy (`balanced`)",
        ),
        label="balanced unattended default",
    )
    assert_optional_paper_workflow_guidance_contract(content)
    assert_publication_toolchain_boundary_contract(content)


def assert_beginner_hub_preflight_contract(content: str) -> None:
    assert "## Before you open the guides" in content
    for requirement in beginner_preflight_requirements():
        assert requirement in content
    _assert_contains_any(
        content,
        (
            "Use `--local` while learning",
            "`--local` while learning",
        ),
        label="local install learning guidance",
    )
    assert "What this hub does not do" in content
    for caveat in beginner_onboarding_caveats():
        assert caveat in content
    assert content.index("## Before you open the guides") < content.index("## First: terminal vs runtime")


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
            "choose the project explicitly",
            "select the project explicitly",
            "pick the right project first",
            "choose one of the recent projects",
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
            "single recoverable recent project",
            "auto-selected recent project",
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
            "continuation handoff artifact",
            "recorded handoff artifact",
            "projected handoff",
            "projected from canonical continuation",
            "mirrored from canonical continuation",
            "usable recovery target",
        ),
        label="pause/resume handoff semantics",
    )


def assert_runtime_reset_rediscovery_contract(
    content: str,
    *,
    extra_reset_fragments: Iterable[str] = (),
    extra_reset_not_recovery_fragments: Iterable[str] = (),
) -> None:
    assert "/clear" in content
    assert "gpd resume" in content
    assert "gpd resume --recent" in content
    _assert_contains_any(
        content,
        (
            "fresh-context reset",
            "fresh context window",
            "reset the runtime window",
            "reset the runtime to a fresh context window",
            "`/clear` first, then run `{next command}`",
            *tuple(extra_reset_fragments),
        ),
        label="runtime reset wording",
    )
    _assert_contains_any(
        content,
        (
            "normal terminal",
            "your normal terminal",
            "before reopening the runtime",
        ),
        label="rediscovery-before-runtime boundary",
    )
    _assert_contains_any(
        content,
        (
            "not as a recovery step",
            "instead of implying that `/clear` performs recovery",
            *tuple(extra_reset_not_recovery_fragments),
        ),
        label="reset-not-recovery wording",
    )


def assert_resume_authority_contract(
    content: str,
    *,
    allow_explicit_alias_examples: bool,
    require_generic_compatibility_note: bool = False,
) -> None:
    contract = _resume_authority_contract()
    compatibility_note = (
        "Compatibility-only intake fields stay internal and are not part of the public top-level resume vocabulary"
    )
    assert _contract_string(contract, "durable_authority_phrase", label="resume_authority") in content
    assert _contract_string(contract, "public_vocabulary_intro", label="resume_authority") in content
    for field in _contract_string_list(contract, "public_fields", label="resume_authority"):
        assert f"`{field}`" in content
    _assert_contains_any(
        content,
        (
            _contract_string(contract, "top_level_boundary_phrase", label="resume_authority"),
        ),
        label="resume top-level boundary",
    )
    if allow_explicit_alias_examples:
        _assert_contains_any(
            content,
            (
                compatibility_note,
                "Compatibility-only backend intake (`gpd init resume` only):",
            ),
            label="resume compatibility phrase",
        )
        _assert_contains_any(
            content,
            (
                "session.resume_file",
                "session_resume_file",
                "current_execution",
                "interrupted_agent",
            ),
            label="compatibility alias examples",
        )
    else:
        assert "compat_resume_surface" not in content
        for alias in resume_compat_alias_fields():
            assert alias not in content
        assert "Compatibility-only backend intake (`gpd init resume` only):" not in content
    if require_generic_compatibility_note:
        _assert_contains_any(
            content,
            (
                compatibility_note,
                _contract_string(contract, "top_level_boundary_phrase", label="resume_authority"),
            ),
            label="generic compatibility note",
        )


def assert_runtime_readiness_handoff_contract(content: str) -> None:
    _assert_contains_any(
        content,
        (
            "gpd doctor",
            "sharedDoctorCommand()",
            "localCliBridge.doctorCommand",
        ),
        label="doctor surface",
    )
    _assert_contains_any(
        content,
        (
            UNATTENDED_READINESS_SURFACE,
            "sharedUnattendedReadinessCommand()",
            "localCliBridge.unattendedReadinessCommand",
        ),
        label="unattended readiness surface",
    )
    _assert_contains_any(
        content,
        (
            "install and runtime-local readiness",
            "runtime-local readiness",
            "runtime-readiness check",
            "continuation handoff artifact",
            "projected handoff",
        ),
        label="runtime-local readiness handoff",
    )
    _assert_contains_any(
        content,
        (
            "gpd permissions ...",
            PERMISSIONS_SYNC_SURFACE,
            "sharedPermissionsSyncCommand()",
            "localCliBridge.permissionsSyncCommand",
            "runtime-owned permission alignment and sync",
            "runtime-owned permission alignment",
            "mirrored from canonical continuation",
            "projected from canonical continuation",
        ),
        label="runtime-owned permission handoff",
    )


def assert_help_workflow_runtime_reference_contract(
    content: str,
    *,
    resume_work_fragments: Iterable[str] = ("/gpd:resume-work",),
    suggest_next_fragments: Iterable[str] = ("/gpd:suggest-next",),
    pause_work_fragments: Iterable[str] = ("/gpd:pause-work",),
) -> None:
    _assert_contains_any(
        content,
        (
            "## Invocation Surfaces",
            "Invocation Surfaces",
        ),
        label="help workflow invocation surfaces section",
    )
    _assert_contains_any(
        content,
        (
            "## Quick Start",
            "Quick Start",
        ),
        label="help workflow quick-start section",
    )
    _assert_contains_any(
        content,
        (
            "`/gpd:*`",
            "canonical in-runtime command names",
            "slash prefixes",
            "dollar prefixes",
        ),
        label="runtime command-surface framing",
    )
    _assert_contains_any(
        content,
        (
            "gpd --help",
            "local `gpd` CLI",
            "local CLI",
        ),
        label="local CLI bridge framing",
    )
    assert_beginner_startup_routing_contract(content)
    assert_runtime_readiness_handoff_contract(content)
    assert_recovery_ladder_contract(
        content,
        resume_work_fragments=resume_work_fragments,
        suggest_next_fragments=suggest_next_fragments,
        pause_work_fragments=pause_work_fragments,
    )
    assert_execution_observability_surface_contract(content)
    assert_cost_surface_discoverability(content)
    assert_workflow_preset_surface_contract(content)
    assert_optional_paper_workflow_guidance_contract(content)
    assert_publication_toolchain_boundary_contract(content)
    assert_wolfram_plan_boundary_contract(content)


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
    """Assert the slim settings-owned local-terminal follow-up surface."""
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
