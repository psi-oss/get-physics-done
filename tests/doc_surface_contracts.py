"""Shared semantic assertions for repeated documentation surface contracts."""

from __future__ import annotations

import dataclasses
import re
from collections.abc import Iterable
from functools import lru_cache

from gpd.adapters import get_adapter, iter_runtime_descriptors
from gpd.core.public_surface_contract import (
    load_public_surface_contract,
    local_cli_cost_command,
    local_cli_doctor_command,
    local_cli_doctor_global_command,
    local_cli_doctor_local_command,
    local_cli_integrations_status_wolfram_command,
    local_cli_observe_execution_command,
    local_cli_permissions_status_command,
    local_cli_permissions_sync_command,
    local_cli_plan_preflight_command,
    local_cli_resume_command,
    local_cli_unattended_readiness_command,
    recovery_cross_workspace_command,
    recovery_local_snapshot_command,
)
from gpd.core.resume_surface import RESUME_COMPATIBILITY_ALIAS_FIELDS

_RUNTIME_NAMES = tuple(descriptor.runtime_name for descriptor in iter_runtime_descriptors())


def _doctor_runtime_scope_re() -> re.Pattern[str]:
    return re.compile(
        rf"(?:{re.escape(local_cli_doctor_local_command())}|{re.escape(local_cli_doctor_global_command())})"
    )


def _unattended_readiness_surface() -> str:
    return local_cli_unattended_readiness_command()


def _permissions_status_surface() -> str:
    return local_cli_permissions_status_command()


def _permissions_sync_surface() -> str:
    return local_cli_permissions_sync_command()


def _plan_preflight_surface() -> str:
    return local_cli_plan_preflight_command()


def _wolfram_status_surface() -> str:
    return local_cli_integrations_status_wolfram_command()


class _RegexProxy:
    def search(self, content: str, *args: object, **kwargs: object) -> re.Match[str] | None:
        return _doctor_runtime_scope_re().search(content, *args, **kwargs)

    def __getattr__(self, name: str) -> object:
        return getattr(_doctor_runtime_scope_re(), name)


DOCTOR_RUNTIME_SCOPE_RE = _RegexProxy()


def _canonical_runtime_command(action: str) -> str:
    command, separator, remainder = action.partition(" ")
    canonical = f"gpd:{command}"
    return canonical if not separator else f"{canonical} {remainder}"


def _runtime_command_variants(action: str) -> tuple[str, ...]:
    variants: list[str] = []
    seen: set[str] = set()
    canonical_command = _canonical_runtime_command(action)
    seen.add(canonical_command)
    variants.append(canonical_command)
    for runtime_name in _RUNTIME_NAMES:
        command = get_adapter(runtime_name).format_command(action)
        if command in seen:
            continue
        seen.add(command)
        variants.append(command)
    return tuple(variants)


def _runtime_command_fragments(action: str) -> tuple[str, ...]:
    fragments: list[str] = []
    seen: set[str] = set()
    for command in _runtime_command_variants(action):
        for fragment in (command, f"`{command}`"):
            if fragment in seen:
                continue
            seen.add(fragment)
            fragments.append(fragment)
    return tuple(fragments)


def _quoted_fragments(*values: str) -> tuple[str, ...]:
    fragments: list[str] = []
    seen: set[str] = set()
    for value in values:
        for fragment in (value, f"`{value}`"):
            if fragment in seen:
                continue
            seen.add(fragment)
            fragments.append(fragment)
    return tuple(fragments)


def _action_surface_fragments(action: str, *, include_bare: bool = False) -> tuple[str, ...]:
    fragments: list[str] = []
    if include_bare:
        fragments.append(f"`{action}`")
    fragments.extend(_runtime_command_fragments(action))
    return tuple(dict.fromkeys(fragments))

__all__ = [
    "DOCTOR_RUNTIME_SCOPE_RE",
    "assert_cost_advisory_contract",
    "assert_cost_surface_discoverability",
    "assert_execution_observability_surface_contract",
    "assert_health_command_public_contract",
    "assert_help_command_quick_start_extract_contract",
    "assert_help_workflow_quick_start_taxonomy_contract",
    "assert_help_workflow_runtime_reference_contract",
    "assert_install_summary_runtime_follow_up_contract",
    "assert_beginner_hub_preflight_contract",
    "assert_beginner_router_bridge_contract",
    "assert_beginner_startup_routing_contract",
    "assert_recovery_ladder_contract",
    "assert_runtime_reset_rediscovery_contract",
    "assert_resume_authority_contract",
    "assert_settings_local_terminal_follow_up_contract",
    "assert_start_workflow_router_contract",
    "assert_tour_command_surface_contract",
    "assert_unattended_readiness_contract",
    "assert_wolfram_plan_boundary_contract",
    "assert_workflow_preset_surface_contract",
    "resume_authority_public_vocabulary_intro",
    "resume_compat_alias_fields",
]


HELP_ENTRY_FRAGMENTS = (
    "`help`",
    *_runtime_command_fragments("help"),
    "run `help`",
    "help command",
)
START_ENTRY_FRAGMENTS = (
    "`start`",
    *_runtime_command_fragments("start"),
    "Run `start`",
)
TOUR_ENTRY_FRAGMENTS = (
    "`tour`",
    *_runtime_command_fragments("tour"),
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
    payload = {"schema_version": 1, **dataclasses.asdict(load_public_surface_contract())}
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
    assert isinstance(value, (list, tuple)) and value, f"{label}.{key} must be a non-empty list"
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
    }
    assert required_keys.issubset(section)
    assert not (set(section) - required_keys)
    _contract_string(section, "durable_authority_phrase", label="resume_authority")
    _contract_string(section, "public_vocabulary_intro", label="resume_authority")
    _contract_string_list(section, "public_fields", label="resume_authority")
    return section


def resume_authority_public_vocabulary_intro() -> str:
    section = _resume_authority_contract()
    return _contract_string(section, "public_vocabulary_intro", label="resume_authority")


def resume_compat_alias_fields() -> tuple[str, ...]:
    return RESUME_COMPATIBILITY_ALIAS_FIELDS


def assert_unattended_readiness_contract(content: str) -> None:
    assert _unattended_readiness_surface() in content
    assert _permissions_sync_surface() in content
    assert _permissions_status_surface() in content
    assert local_cli_doctor_command() in content
    _assert_contains_any(
        content,
        (
            "runtime-owned approval/alignment only",
            "runtime-owned permission alignment",
            "read-only runtime-owned approval/alignment snapshot",
            "runtime-owned alignment needs to be changed",
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
    assert local_cli_cost_command() in content
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
    assert local_cli_observe_execution_command() in content
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


def assert_health_command_public_contract(content: str) -> None:
    assert "Parse JSON output containing:" in content
    assert "`overall`: top-level `CheckStatus` for the full report" in content
    assert "`summary`: `HealthSummary` with `ok`, `warn`, `fail`, and `total`" in content
    assert (
        "`checks`: Array of `HealthCheck` objects with `status`, `label`, `details`, `issues`, and `warnings`"
        in content
    )
    assert "`fixes_applied`: top-level list of auto-applied fix descriptions" in content
    assert "Array of `{name, status, message, fixed}`" not in content
    assert "Object with `total`, `passed`, `warnings`, `failures`, `fixed`" not in content


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
            "Start at the workflow-owned `## Quick Start` section.",
            "workflow-owned `## Quick Start` section",
        ),
        label="help command quick-start reference anchor",
    )
    assert "## Invocation Surfaces" not in content
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
            "Stop before `## Command Index`.",
            "before `## Command Index`",
        ),
        label="help command command-index cutoff boundary",
    )
    _assert_contains_any(
        content,
        (
            *tuple(
                f"Run \\`{command}\\` for the compact command index."
                for command in _runtime_command_variants("help --all")
            ),
            *_quoted_fragments(*_runtime_command_variants("help --all")),
        ),
        label="help command compact-index follow-up",
    )


def assert_help_command_all_extract_contract(content: str) -> None:
    _assert_contains_any(
        content,
        (
            "Compact Command Index (--all)",
            "compact command index",
        ),
        label="help command compact-index heading",
    )
    _assert_contains_any(
        content,
        (
            "Include the workflow-owned `## Command Index` section.",
            "`## Command Index` section",
        ),
        label="help command command-index extract boundary",
    )
    _assert_contains_any(
        content,
        (
            "Stop before `## Detailed Command Reference`.",
            "before `## Detailed Command Reference`",
        ),
        label="help command detailed-reference cutoff boundary",
    )
    _assert_contains_any(
        content,
        (
            *tuple(
                f"Run \\`{command}\\` for detailed help on one command."
                for command in _runtime_command_variants("help --command <name>")
            ),
            *_quoted_fragments(*_runtime_command_variants("help --command <name>")),
        ),
        label="help command single-command follow-up",
    )


def assert_help_command_single_command_extract_contract(content: str) -> None:
    _assert_contains_any(
        content,
        (
            "Single Command Detail Extract (--command <name>)",
            "--command <name>",
        ),
        label="help command single-command heading",
    )
    _assert_contains_any(
        content,
        (
            "Parse the command name from `$ARGUMENTS` after `--command`.",
            "after `--command`",
        ),
        label="help command single-command parse rule",
    )
    _assert_contains_any(
        content,
        (
            "Accept either a bare command name such as `plan-phase` or a canonical runtime command such as `gpd:plan-phase`.",
            "bare command name",
            "canonical runtime command",
        ),
        label="help command single-command normalization",
    )
    _assert_contains_any(
        content,
        (
            "If the lookup includes inline flags or arguments such as `gpd:new-project --minimal`, normalize it to the base command block",
            "inline flags or arguments",
            "base command block",
        ),
        label="help command single-command flag normalization",
    )
    _assert_contains_any(
        content,
        (
            "Include the nearest containing section heading",
            "smallest matching detailed command block",
        ),
        label="help command single-command extraction boundary",
    )
    _assert_contains_any(
        content,
        (
            "Unknown command. Run `",
            *_quoted_fragments(*_runtime_command_variants("help --all")),
        ),
        label="help command single-command fallback",
    )


def assert_help_workflow_quick_start_taxonomy_contract(content: str) -> None:
    for label, options in (
        ("quick-start new-work group", ("**New work**", "New work")),
        ("quick-start existing-work group", ("**Existing work**", "Existing work")),
        ("quick-start returning-work group", ("**Returning work**", "Returning work")),
        (
            "quick-start post-startup settings group",
            (
                "**Post-startup settings**",
                "Post-startup settings",
                "**After your first successful start**",
                "After your first successful start",
            ),
        ),
    ):
        _assert_contains_any(content, options, label=label)

    for label, options in (
        ("quick-start start command", _runtime_command_fragments("start")),
        ("quick-start tour command", _runtime_command_fragments("tour")),
        ("quick-start new-project command", _runtime_command_fragments("new-project")),
        ("quick-start map-research command", _runtime_command_fragments("map-research")),
        ("quick-start resume-work command", _runtime_command_fragments("resume-work")),
        ("quick-start settings command", _runtime_command_fragments("settings")),
        ("quick-start set-tier-models command", _runtime_command_fragments("set-tier-models")),
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
    _assert_contains_any(
        content,
        (
            *_runtime_command_fragments("tangent"),
        ),
        label="quick-start tangent follow-up guidance",
    )
    _assert_contains_any(
        content,
        (
            *_runtime_command_fragments("branch-hypothesis"),
        ),
        label="quick-start branch-hypothesis follow-up guidance",
    )


def assert_help_workflow_command_index_contract(content: str) -> None:
    _assert_contains_any(
        content,
        (
            "compact grouped list of runtime commands",
            "compact grouped list",
            "normal-terminal install, readiness, and diagnostics commands",
        ),
        label="help workflow command-index framing",
    )
    for label, options in (
        ("command-index starter heading", ("### Starter commands", "Starter commands")),
        ("command-index planning heading", ("### Planning and execution", "Planning and execution")),
        ("command-index roadmap heading", ("### Roadmap and milestones", "Roadmap and milestones")),
        ("command-index validation heading", ("### Validation and analysis", "Validation and analysis")),
        ("command-index writing heading", ("### Writing and publication", "Writing and publication")),
        ("command-index tangents heading", ("### Tangents, memory, and exports", "Tangents, memory, and exports")),
        ("command-index configuration heading", ("### Configuration and maintenance", "Configuration and maintenance")),
    ):
        _assert_contains_any(content, options, label=label)

    for label, options in (
        ("command-index help surface", _runtime_command_fragments("help")),
        ("command-index start surface", _runtime_command_fragments("start")),
        ("command-index plan-phase surface", _runtime_command_fragments("plan-phase")),
        ("command-index execute-phase surface", _runtime_command_fragments("execute-phase")),
        ("command-index write-paper surface", _runtime_command_fragments("write-paper")),
        ("command-index tangent surface", _runtime_command_fragments("tangent")),
        ("command-index settings surface", _runtime_command_fragments("settings")),
    ):
        _assert_contains_any(content, options, label=label)


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
    for label, options in (
        ("tour start surface", _runtime_command_fragments("start")),
        ("tour new-project --minimal surface", _runtime_command_fragments("new-project --minimal")),
        ("tour new-project surface", _runtime_command_fragments("new-project")),
        ("tour map-research surface", _runtime_command_fragments("map-research")),
        ("tour local resume surface", _quoted_fragments(local_cli_resume_command())),
        ("tour resume-work surface", _runtime_command_fragments("resume-work")),
        ("tour suggest-next surface", _runtime_command_fragments("suggest-next")),
        ("tour progress surface", _runtime_command_fragments("progress")),
        ("tour explain surface", _runtime_command_fragments("explain")),
        ("tour quick surface", _runtime_command_fragments("quick")),
        ("tour settings surface", _runtime_command_fragments("settings")),
        ("tour help surface", _runtime_command_fragments("help")),
    ):
        _assert_contains_any(content, options, label=label)

    assert "What comes later after startup" in content
    for label, options in (
        ("tour discuss-phase surface", _runtime_command_fragments("discuss-phase")),
        ("tour write-paper surface", _runtime_command_fragments("write-paper")),
        ("tour tangent surface", _runtime_command_fragments("tangent")),
    ):
        _assert_contains_any(content, options, label=label)

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
            f"Use `{recovery_local_snapshot_command()}` first",
            f"{recovery_local_snapshot_command()}` is the normal-terminal recovery step",
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
        *_action_surface_fragments("new-project --minimal", include_bare=True),
        *_action_surface_fragments("new-project", include_bare=True),
    )
    map_research_fragments = _action_surface_fragments("map-research", include_bare=True)
    resume_work_fragments = _action_surface_fragments("resume-work", include_bare=True)

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

    for label, options in (
        ("start recommended-next-steps heading", ("Recommended next steps:",)),
        ("start other-useful-options heading", ("Other useful options",)),
        ("start resume-work surface", _runtime_command_fragments("resume-work")),
        ("start progress surface", _runtime_command_fragments("progress")),
        ("start suggest-next surface", _runtime_command_fragments("suggest-next")),
        ("start quick surface", _runtime_command_fragments("quick")),
        ("start tour surface", _runtime_command_fragments("tour")),
        ("start map-research surface", _runtime_command_fragments("map-research")),
        ("start new-project --minimal surface", _runtime_command_fragments("new-project --minimal")),
        ("start new-project surface", _runtime_command_fragments("new-project")),
        ("start explain surface", _runtime_command_fragments("explain")),
        ("start help --all surface", _runtime_command_fragments("help --all")),
        (
            "start minimal-command-contract handoff",
            tuple(
                f"Follow the installed `{command}` command contract directly"
                for command in _runtime_command_variants("new-project --minimal")
            ),
        ),
        (
            "start new-project-command-contract handoff",
            tuple(
                f"Follow the installed `{command}` command contract directly"
                for command in _runtime_command_variants("new-project")
            ),
        ),
        (
            "start help-command-contract handoff",
            tuple(
                f"Follow the installed `{command}` command contract directly"
                for command in _runtime_command_variants("help --all")
            ),
        ),
    ):
        _assert_contains_any(content, options, label=label)

    assert recovery_cross_workspace_command() in content
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
            *_action_surface_fragments("help"),
            "help command",
        ),
        label="runtime help bridge",
    )
    _assert_contains_any(
        content,
        (
            *_action_surface_fragments("start", include_bare=True),
            "runtime's `start` command",
            "use `start`",
        ),
        label="start routing surface",
    )
    _assert_contains_any(
        content,
        (
            *_action_surface_fragments("tour", include_bare=True),
            "runtime's `tour` command",
            "use `tour`",
        ),
        label="tour routing surface",
    )
    _assert_contains_any(
        content,
        (
            *_action_surface_fragments("new-project --minimal", include_bare=True),
            *_action_surface_fragments("new-project", include_bare=True),
        ),
        label="new-project routing surface",
    )
    _assert_contains_any(
        content,
        (
            *_action_surface_fragments("map-research", include_bare=True),
        ),
        label="map-research routing surface",
    )
    _assert_contains_any(
        content,
        (
            *_action_surface_fragments("resume-work", include_bare=True),
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
    assert recovery_local_snapshot_command() in content
    assert recovery_cross_workspace_command() in content
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
    assert recovery_local_snapshot_command() in content
    assert recovery_cross_workspace_command() in content
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
    compatibility_note = "Compatibility-only intake fields stay internal"
    assert _contract_string(contract, "durable_authority_phrase", label="resume_authority") in content
    assert _contract_string(contract, "public_vocabulary_intro", label="resume_authority") in content
    for field in _contract_string_list(contract, "public_fields", label="resume_authority"):
        assert f"`{field}`" in content
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
        lowered_content = content.lower()
        _assert_contains_any(
            lowered_content,
            (
                compatibility_note.lower(),
                _contract_string(contract, "public_vocabulary_intro", label="resume_authority").lower(),
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
            _unattended_readiness_surface(),
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
            _permissions_status_surface(),
            _permissions_sync_surface(),
            "sharedPermissionsStatusCommand()",
            "sharedPermissionsSyncCommand()",
            "localCliBridge.permissionsStatusCommand",
            "localCliBridge.permissionsSyncCommand",
            "runtime-owned permission alignment and sync",
            "read-only runtime-owned permission snapshot",
            "read-only runtime-owned approval/alignment snapshot",
            "runtime-owned permission alignment",
            "mirrored from canonical continuation",
            "projected from canonical continuation",
        ),
        label="runtime-owned permission handoff",
    )


def assert_help_workflow_runtime_reference_contract(
    content: str,
    *,
    resume_work_fragments: Iterable[str] = _runtime_command_fragments("resume-work"),
    suggest_next_fragments: Iterable[str] = _runtime_command_fragments("suggest-next"),
    pause_work_fragments: Iterable[str] = _runtime_command_fragments("pause-work"),
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
            "## Command Index",
            "Command Index",
        ),
        label="help workflow command-index section",
    )
    _assert_contains_any(
        content,
        (
            "## Detailed Command Reference",
            "Detailed Command Reference",
        ),
        label="help workflow detailed-reference section",
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
    assert_help_workflow_command_index_contract(content)
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
    assert "Secondary follow-up" not in content
    _assert_contains_any(
        content,
        (
            "local diagnostics and later setup",
        ),
        label="install-summary local CLI bridge",
    )
    help_fragments = tuple(fragment for fragment in runtime_help_fragments if fragment)
    if help_fragments:
        _assert_contains_any(content, help_fragments, label="runtime help follow-up surface")


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
    _assert_contains_any(
        content,
        (
            _unattended_readiness_surface(),
            "gpd validate unattended-readiness --runtime <runtime> --autonomy <mode>",
        ),
        label="settings unattended-readiness follow-up surface",
    )
    _assert_contains_any(
        content,
        (
            _permissions_status_surface(),
            _permissions_sync_surface(),
            "gpd permissions sync --runtime <runtime> --autonomy <mode>",
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
    assert _wolfram_status_surface() in content
    assert _plan_preflight_surface() in content
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
