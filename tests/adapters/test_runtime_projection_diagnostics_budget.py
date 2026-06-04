"""Guardrails for non-native runtime projection diagnostics."""

from __future__ import annotations

from pathlib import Path

from gpd.adapters.runtime_catalog import iter_runtime_descriptors
from gpd.core import prompt_diagnostics
from tests.adapters.projection_budget_support import (
    COMPACT_WORKFLOW_REFERENCE_COMMAND_PROJECTION_BUDGETS,
    NON_NATIVE_RUNTIME_PROJECTION_TARGETS,
    RUNTIME_PROJECTION_TARGETS,
    SELECTED_AGENT_PROJECTION_BUDGETS,
    STAGED_PROJECTED_COMMAND_CHAR_BUDGET,
    TARGET_AGENT_COMBINED_NON_NATIVE_PROJECTION_CHAR_BUDGET,
    TARGET_AGENT_PROJECTION_BUDGETS,
)
from tests.adapters.projection_test_utils import normalized_runtime_projection_char_count

REPO_ROOT = Path(__file__).resolve().parents[2]
KNOWN_PROJECTION_HOTSPOTS = {
    "execute-phase",
    "gpd-executor",
    "gpd-planner",
    "gpd-roadmapper",
    "new-project",
    "write-paper",
}
COMMAND_ONLY_RUNTIME_PRESSURE_BUDGETS = {
    "claude-code": {
        "shell_fence_count": 27,
        "shell_rewrite_count": 22,
        "bridge_command_occurrences": 32,
        "runtime_note_count": 1,
    },
    "codex": {
        "shell_fence_count": 31,
        "shell_rewrite_count": 31,
        "bridge_command_occurrences": 246,
        "runtime_note_count": 2,
    },
    "copilot-cli": {
        "shell_fence_count": 31,
        "shell_rewrite_count": 31,
        "bridge_command_occurrences": 174,
        "runtime_note_count": 2,
    },
    "gemini": {
        "shell_fence_count": 95,
        "shell_rewrite_count": 88,
        "bridge_command_occurrences": 300,
        "runtime_note_count": 58,
    },
    "opencode": {
        "shell_fence_count": 31,
        "shell_rewrite_count": 31,
        "bridge_command_occurrences": 174,
        "runtime_note_count": 2,
    },
}
ADDITIONAL_COMPACT_WORKFLOW_REFERENCE_COMMAND_PROJECTION_BUDGETS = {
    "export": {
        "codex": {"chars": 5_400, "lines": 105},
        "copilot-cli": {"chars": 5_100, "lines": 100},
        "gemini": {"chars": 4_900, "lines": 90},
        "opencode": {"chars": 5_200, "lines": 100},
    },
    "explain": {
        "codex": {"chars": 6_150, "lines": 130},
        "copilot-cli": {"chars": 6_470, "lines": 145},
        "gemini": {"chars": 6_950, "lines": 130},
        "opencode": {"chars": 6_550, "lines": 145},
    },
    "list-phase-assumptions": {
        "codex": {"chars": 7_900, "lines": 155},
        "copilot-cli": {"chars": 7_700, "lines": 160},
        "gemini": {"chars": 7_400, "lines": 140},
        "opencode": {"chars": 7_850, "lines": 160},
    },
}
COMPACT_WORKFLOW_REFERENCE_PROJECTION_BUDGETS = {
    **COMPACT_WORKFLOW_REFERENCE_COMMAND_PROJECTION_BUDGETS,
    **ADDITIONAL_COMPACT_WORKFLOW_REFERENCE_COMMAND_PROJECTION_BUDGETS,
}
COMPACT_WORKFLOW_REFERENCE_PROJECTION_TARGET_COMMANDS = tuple(COMPACT_WORKFLOW_REFERENCE_PROJECTION_BUDGETS)
STAGED_INIT_COMMAND_PROJECTION_RATCHET_BUDGETS = {
    "plan-phase": {
        "claude-code": 4_500,
        "codex": 6_650,
        "copilot-cli": 6_600,
        "gemini": 7_150,
        "opencode": 6_650,
    },
    "execute-phase": {
        "claude-code": 3_450,
        "codex": 5_900,
        "copilot-cli": 5_800,
        "gemini": 6_400,
        "opencode": 5_850,
    },
    "new-project": {
        "claude-code": 7_300,
        "codex": 9_050,
        "copilot-cli": 8_800,
        "gemini": 9_550,
        "opencode": 8_950,
    },
    "write-paper": {
        "claude-code": 12_950,
        "codex": 11_850,
        "copilot-cli": 15_100,
        "gemini": 12_300,
        "opencode": 15_250,
    },
}


def _non_negative_int(row: dict[str, object], key: str) -> int:
    value = row.get(key)
    assert isinstance(value, int), f"{key} should be an int in {row!r}"
    assert value >= 0, f"{key} should be non-negative in {row!r}"
    return value


def test_projection_budget_fixture_tracks_runtime_catalog() -> None:
    descriptors = iter_runtime_descriptors()
    runtime_names = tuple(descriptor.runtime_name for descriptor in descriptors)
    non_native_names = tuple(
        descriptor.runtime_name for descriptor in descriptors if not descriptor.native_include_support
    )

    assert RUNTIME_PROJECTION_TARGETS == runtime_names
    assert NON_NATIVE_RUNTIME_PROJECTION_TARGETS == non_native_names
    for command_name, budget_by_runtime in STAGED_INIT_COMMAND_PROJECTION_RATCHET_BUDGETS.items():
        assert set(budget_by_runtime) == set(runtime_names), command_name
    for command_name, budget_by_runtime in COMPACT_WORKFLOW_REFERENCE_PROJECTION_BUDGETS.items():
        assert set(budget_by_runtime) == set(non_native_names), command_name


def test_report_to_dict_exposes_non_native_runtime_top_prompt_hotspots() -> None:
    report = prompt_diagnostics.build_prompt_surface_report(
        REPO_ROOT,
        surfaces=("command", "agent"),
        runtime_names=NON_NATIVE_RUNTIME_PROJECTION_TARGETS,
        include_tests=False,
        include_runtime_projections=True,
    )

    payload = prompt_diagnostics.report_to_dict(report)

    assert "runtime_top_prompts" in payload
    runtime_top_prompts = payload["runtime_top_prompts"]
    assert isinstance(runtime_top_prompts, dict)
    assert set(NON_NATIVE_RUNTIME_PROJECTION_TARGETS) <= set(runtime_top_prompts)

    hotspot_names: set[str] = set()
    saw_bridge_pressure = False
    saw_shell_rewrite_pressure = False
    for runtime in NON_NATIVE_RUNTIME_PROJECTION_TARGETS:
        rows = runtime_top_prompts[runtime]
        assert isinstance(rows, list)
        assert rows, f"{runtime} should expose at least one runtime top prompt row"

        projected_char_counts: list[int] = []
        for row in rows:
            assert isinstance(row, dict)
            assert row["runtime"] == runtime
            assert row["native_include_support"] is False
            assert row["kind"] in {"command", "agent"}
            assert isinstance(row["name"], str)
            assert row["name"]
            assert isinstance(row["path"], str)
            assert row["path"].endswith(".md")

            projected_char_counts.append(_non_negative_int(row, "projected_char_count"))
            _non_negative_int(row, "projected_line_count")
            _non_negative_int(row, "expanded_char_count")
            _non_negative_int(row, "expanded_line_count")
            _non_negative_int(row, "include_count")
            _non_negative_int(row, "runtime_note_count")
            _non_negative_int(row, "shell_fence_count")
            shell_rewrite_count = _non_negative_int(row, "shell_rewrite_count")
            bridge_command_occurrences = _non_negative_int(row, "bridge_command_occurrences")

            saw_bridge_pressure = saw_bridge_pressure or bridge_command_occurrences > 0
            saw_shell_rewrite_pressure = saw_shell_rewrite_pressure or shell_rewrite_count > 0
            if row["name"] in KNOWN_PROJECTION_HOTSPOTS:
                hotspot_names.add(row["name"])

        assert projected_char_counts == sorted(projected_char_counts, reverse=True)

    assert hotspot_names, "runtime_top_prompts should surface at least one known prompt-size hotspot"
    assert saw_bridge_pressure, "runtime_top_prompts should expose nonzero bridge-command pressure"
    assert saw_shell_rewrite_pressure, "runtime_top_prompts should expose nonzero shell rewrite pressure"


def test_command_runtime_projection_shell_and_bridge_pressure_stays_under_advisory_baselines() -> None:
    report = prompt_diagnostics.build_prompt_surface_report(
        REPO_ROOT,
        surfaces=("command",),
        runtime_names=RUNTIME_PROJECTION_TARGETS,
        include_tests=False,
        include_runtime_projections=True,
    )
    payload = prompt_diagnostics.report_to_dict(report)
    totals = payload["totals"]
    assert isinstance(totals, dict)
    runtime_projection = totals["runtime_projection"]
    assert isinstance(runtime_projection, dict)

    assert set(COMMAND_ONLY_RUNTIME_PRESSURE_BUDGETS) <= set(runtime_projection)
    for runtime, pressure_budgets in COMMAND_ONLY_RUNTIME_PRESSURE_BUDGETS.items():
        runtime_totals = runtime_projection[runtime]
        assert isinstance(runtime_totals, dict)
        for field_name, advisory_budget in pressure_budgets.items():
            observed = _non_negative_int(runtime_totals, field_name)
            assert observed <= advisory_budget, (
                f"{runtime} command projection {field_name} advisory budget exceeded: "
                f"observed={observed} max={advisory_budget}; "
                "reduce prompt-local shell fences or repeated runtime bridge snippets"
            )

        if runtime in NON_NATIVE_RUNTIME_PROJECTION_TARGETS:
            assert _non_negative_int(runtime_totals, "include_count") == 0
            assert _non_negative_int(runtime_totals, "bridge_command_occurrences") > 0


def test_target_command_runtime_projection_diagnostics_stay_under_baseline_budgets() -> None:
    report = prompt_diagnostics.build_prompt_surface_report(
        REPO_ROOT,
        surfaces=("command",),
        runtime_names=RUNTIME_PROJECTION_TARGETS,
        include_tests=False,
        include_runtime_projections=True,
    )

    items_by_name = {item.name: item for item in report.items if item.kind == "command"}
    missing = sorted(set(STAGED_INIT_COMMAND_PROJECTION_RATCHET_BUDGETS) - set(items_by_name))
    assert missing == []

    shell_rewrites_by_runtime = dict.fromkeys(NON_NATIVE_RUNTIME_PROJECTION_TARGETS, 0)
    for command_name, budget_by_runtime in STAGED_INIT_COMMAND_PROJECTION_RATCHET_BUDGETS.items():
        item = items_by_name[command_name]
        metrics_by_runtime = {metric.runtime: metric for metric in item.runtime_projection}
        assert set(RUNTIME_PROJECTION_TARGETS) <= set(metrics_by_runtime)

        for runtime, budget in budget_by_runtime.items():
            metric = metrics_by_runtime[runtime]
            assert normalized_runtime_projection_char_count(metric) <= budget
            assert metric.char_count <= STAGED_PROJECTED_COMMAND_CHAR_BUDGET
            if runtime in NON_NATIVE_RUNTIME_PROJECTION_TARGETS:
                assert metric.bridge_command_occurrences > 0
                shell_rewrites_by_runtime[runtime] += metric.shell_rewrite_count

    for runtime, shell_rewrite_count in shell_rewrites_by_runtime.items():
        assert shell_rewrite_count > 0, f"{runtime} staged command targets should retain shell rewrite diagnostics"


def test_compact_workflow_reference_command_diagnostics_stay_under_baseline_budgets() -> None:
    report = prompt_diagnostics.build_prompt_surface_report(
        REPO_ROOT,
        surfaces=("command",),
        runtime_names=NON_NATIVE_RUNTIME_PROJECTION_TARGETS,
        include_tests=False,
        include_runtime_projections=True,
    )

    items_by_name = {item.name: item for item in report.items if item.kind == "command"}
    missing = sorted(set(COMPACT_WORKFLOW_REFERENCE_PROJECTION_TARGET_COMMANDS) - set(items_by_name))
    assert missing == []

    for command_name, budget_by_runtime in COMPACT_WORKFLOW_REFERENCE_PROJECTION_BUDGETS.items():
        item = items_by_name[command_name]
        metrics_by_runtime = {metric.runtime: metric for metric in item.runtime_projection}
        assert set(NON_NATIVE_RUNTIME_PROJECTION_TARGETS) <= set(metrics_by_runtime)

        for runtime, budget in budget_by_runtime.items():
            metric = metrics_by_runtime[runtime]
            assert metric.native_include_support is False
            assert metric.include_count == 0
            assert metric.char_count <= budget["chars"]
            assert metric.line_count <= budget["lines"]


def test_selected_agent_runtime_projection_diagnostics_stay_under_baseline_budgets() -> None:
    report = prompt_diagnostics.build_prompt_surface_report(
        REPO_ROOT,
        surfaces=("agent",),
        runtime_names=NON_NATIVE_RUNTIME_PROJECTION_TARGETS,
        include_tests=False,
        include_runtime_projections=True,
    )

    items_by_name = {item.name: item for item in report.items if item.kind == "agent"}
    missing = sorted(set(SELECTED_AGENT_PROJECTION_BUDGETS) - set(items_by_name))
    assert missing == []

    target_agent_max_chars: dict[str, int] = {}
    for agent_name, budget in SELECTED_AGENT_PROJECTION_BUDGETS.items():
        item = items_by_name[agent_name]
        metrics_by_runtime = {metric.runtime: metric for metric in item.runtime_projection}
        assert set(NON_NATIVE_RUNTIME_PROJECTION_TARGETS) <= set(metrics_by_runtime)

        max_chars = 0
        for runtime in NON_NATIVE_RUNTIME_PROJECTION_TARGETS:
            metric = metrics_by_runtime[runtime]
            assert metric.native_include_support is False
            assert metric.line_count <= budget["lines"]
            assert metric.char_count <= budget["chars"]
            assert metric.runtime_note_count == 0
            max_chars = max(max_chars, metric.char_count)

        if agent_name in TARGET_AGENT_PROJECTION_BUDGETS:
            target_agent_max_chars[agent_name] = max_chars

    assert sum(target_agent_max_chars.values()) <= TARGET_AGENT_COMBINED_NON_NATIVE_PROJECTION_CHAR_BUDGET
