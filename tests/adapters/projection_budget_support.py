"""Shared budget ceilings for staged runtime projection adapter tests."""

from __future__ import annotations

from gpd.adapters.runtime_catalog import iter_runtime_descriptors

_RUNTIME_DESCRIPTORS = iter_runtime_descriptors()

RUNTIME_PROJECTION_TARGETS = tuple(descriptor.runtime_name for descriptor in _RUNTIME_DESCRIPTORS)
NON_NATIVE_RUNTIME_PROJECTION_TARGETS = tuple(
    descriptor.runtime_name for descriptor in _RUNTIME_DESCRIPTORS if not descriptor.native_include_support
)

STAGED_INIT_COMMAND_PROJECTION_BUDGETS = {
    "plan-phase": {
        "claude-code": 4_550,
        "codex": 6_900,
        "copilot-cli": 6_700,
        "gemini": 7_400,
        "opencode": 6_900,
    },
    "execute-phase": {
        "claude-code": 3_426,
        "codex": 6_005,
        "copilot-cli": 5_900,
        "gemini": 6_496,
        "opencode": 5_920,
    },
    "new-project": {
        "claude-code": 7_500,
        "codex": 9_300,
        "copilot-cli": 9_000,
        "gemini": 9_800,
        "opencode": 9_200,
    },
    "write-paper": {
        "claude-code": 13_076,
        "codex": 12_251,
        "copilot-cli": 15_200,
        "gemini": 12_692,
        "opencode": 15_578,
    },
}
STAGED_INIT_TARGET_COMMANDS = tuple(STAGED_INIT_COMMAND_PROJECTION_BUDGETS)
STAGED_PROJECTED_COMMAND_CHAR_BUDGET = 20_000

COMPACT_WORKFLOW_REFERENCE_COMMAND_PROJECTION_BUDGETS = {
    "compare-experiment": {
        "codex": {"chars": 7_750, "lines": 150},
        "copilot-cli": {"chars": 8_000, "lines": 150},
        "gemini": {"chars": 8_400, "lines": 150},
        "opencode": {"chars": 7_950, "lines": 160},
    },
    "dimensional-analysis": {
        "codex": {"chars": 7_100, "lines": 145},
        "copilot-cli": {"chars": 7_200, "lines": 145},
        "gemini": {"chars": 8_000, "lines": 145},
        "opencode": {"chars": 7_300, "lines": 160},
    },
    "review-knowledge": {
        "codex": {"chars": 9_800, "lines": 170},
        "copilot-cli": {"chars": 10_800, "lines": 205},
        "gemini": {"chars": 9_700, "lines": 165},
        "opencode": {"chars": 11_200, "lines": 220},
    },
}
COMPACT_WORKFLOW_REFERENCE_TARGET_COMMANDS = tuple(COMPACT_WORKFLOW_REFERENCE_COMMAND_PROJECTION_BUDGETS)

TARGET_AGENT_PROJECTION_BUDGETS = {
    "gpd-planner": {"lines": 600, "chars": 33_000},
    "gpd-research-synthesizer": {"lines": 520, "chars": 29_000},
    "gpd-roadmapper": {"lines": 520, "chars": 27_500},
}
TARGET_AGENT_COMBINED_NON_NATIVE_PROJECTION_CHAR_BUDGET = 86_000

SELECTED_AGENT_PROJECTION_BUDGETS = {
    "gpd-executor": {"lines": 670, "chars": 39_500},
    "gpd-experiment-designer": {"lines": 460, "chars": 27_000},
    "gpd-plan-checker": {"lines": 450, "chars": 25_500},
    **TARGET_AGENT_PROJECTION_BUDGETS,
    "gpd-project-researcher": {"lines": 380, "chars": 17_000},
    "gpd-research-mapper": {"lines": 460, "chars": 25_000},
    "gpd-verifier": {"lines": 440, "chars": 30_000},
}
SELECTED_AGENT_PROJECTION_TARGETS = tuple(SELECTED_AGENT_PROJECTION_BUDGETS)

NATIVE_AGENT_PROJECTION_BUDGETS = {
    "gpd-verifier": {"lines": 500, "chars": 35_000},
}
