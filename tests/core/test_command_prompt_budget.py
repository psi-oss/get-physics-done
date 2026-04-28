"""Registry-wide expanded prompt budget coverage for commands."""

from __future__ import annotations

from pathlib import Path

import pytest

from gpd import registry
from gpd.adapters.runtime_catalog import iter_runtime_descriptors
from tests.prompt_metrics_support import (
    budget_from_baseline,
    expanded_include_markers,
    expanded_prompt_text,
    measure_projected_prompt_surface,
    measure_prompt_surface,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_DIR = REPO_ROOT / "src" / "gpd" / "commands"
SOURCE_ROOT = REPO_ROOT / "src" / "gpd"
PATH_PREFIX = "/runtime/"

MIN_LINE_MARGIN = 20
MIN_CHAR_MARGIN = 1_000
COMMAND_NAMES = tuple(registry.list_commands())

COMMAND_BASELINES = {
    "add-phase": (170, 4_382, 1),
    "add-todo": (221, 6_401, 1),
    "arxiv-submission": (661, 47_314, 1),
    "audit-milestone": (518, 20_069, 1),
    "autonomous": (1_080, 37_060, 1),
    "branch-hypothesis": (383, 11_178, 1),
    "check-todos": (232, 6_214, 1),
    "compact-state": (259, 8_256, 1),
    "compare-branches": (395, 12_531, 1),
    "compare-experiment": (491, 21_508, 1),
    "compare-results": (160, 6_921, 1),
    "complete-milestone": (1_557, 47_029, 3),
    "debug": (360, 16_594, 1),
    "decisions": (171, 4_289, 1),
    "derive-equation": (730, 34_842, 1),
    "digest-knowledge": (313, 12_528, 1),
    "dimensional-analysis": (413, 16_529, 1),
    "discover": (472, 18_431, 1),
    "discuss-phase": (1_074, 41_470, 2),
    "error-patterns": (261, 6_377, 1),
    "error-propagation": (436, 18_598, 1),
    "execute-phase": (2_010, 103_014, 1),
    "explain": (356, 13_192, 1),
    "export": (508, 13_232, 1),
    "export-logs": (248, 8_165, 1),
    "graph": (337, 10_521, 1),
    "health": (103, 3_132, 0),
    "help": (1_420, 74_433, 1),
    "insert-phase": (198, 5_984, 1),
    "limiting-cases": (570, 25_524, 1),
    "list-phase-assumptions": (385, 13_881, 1),
    "literature-review": (594, 27_547, 1),
    "map-research": (614, 23_176, 1),
    "merge-phases": (387, 12_059, 1),
    "new-milestone": (802, 38_778, 1),
    "new-project": (2_087, 96_950, 1),
    "numerical-convergence": (570, 27_200, 1),
    "parameter-sweep": (840, 31_582, 1),
    "pause-work": (300, 13_612, 1),
    "peer-review": (1_233, 73_521, 1),
    "plan-milestone-gaps": (357, 11_455, 1),
    "plan-phase": (1_067, 53_460, 1),
    "progress": (605, 19_549, 1),
    "quick": (434, 18_919, 1),
    "reapply-patches": (155, 4_901, 1),
    "record-backtrack": (247, 10_276, 1),
    "record-insight": (161, 4_865, 1),
    "regression-check": (180, 6_710, 1),
    "remove-phase": (231, 6_102, 1),
    "research-phase": (367, 15_316, 1),
    "respond-to-referees": (2_438, 117_818, 2),
    "resume-work": (633, 31_279, 1),
    "review-knowledge": (770, 26_193, 1),
    "revise-phase": (475, 14_557, 1),
    "route": (174, 6_782, 1),
    "sensitivity-analysis": (747, 31_519, 1),
    "set-profile": (228, 10_832, 1),
    "set-tier-models": (219, 8_347, 1),
    "settings": (522, 30_827, 1),
    "show-phase": (345, 9_542, 1),
    "slides": (286, 11_499, 1),
    "start": (310, 15_491, 2),
    "suggest-next": (91, 3_083, 0),
    "sync-state": (290, 9_592, 1),
    "tangent": (207, 7_482, 1),
    "tour": (220, 9_098, 2),
    "undo": (376, 12_127, 1),
    "update": (250, 6_145, 1),
    "validate-conventions": (267, 10_133, 1),
    "verify-work": (720, 35_132, 1),
    "write-paper": (1_992, 105_637, 1),
}
WORST_COMMAND_HARD_CAPS = {
    "write-paper": (2_550, 134_000),
    "respond-to-referees": (2_200, 112_000),
    "execute-phase": (2_100, 106_500),
    "new-project": (2_150, 101_000),
    "help": (1_460, 76_000),
    "peer-review": (1_260, 75_000),
}
PROJECTED_COMMAND_HARD_CAPS = {
    "execute-phase": (2_100, 116_000),
    "new-project": (2_200, 106_000),
    "research-phase": (430, 22_000),
    "respond-to-referees": (1_000, 61_000),
    "write-paper": (2_150, 117_000),
}
RUNTIME_NAMES = tuple(descriptor.runtime_name for descriptor in iter_runtime_descriptors())
TOP_COMMAND_HARD_CAP_COUNT = 6
BULKY_COMMAND_INCLUDE_FILES = (
    "peer-review-panel.md",
    "project-contract-schema.md",
    "contract-results-schema.md",
)

WORKFLOWS_DIR = REPO_ROOT / "src" / "gpd" / "specs" / "workflows"
WORKFLOW_NAMES = tuple(path.stem for path in sorted(WORKFLOWS_DIR.glob("*.md")))
WORKFLOW_BASELINES = {
    "add-phase": (131, 3356, 0),
    "add-todo": (180, 5106, 0),
    "arxiv-submission": (551, 44012, 3),
    "audit-milestone": (430, 15206, 1),
    "autonomous": (1028, 35321, 0),
    "branch-hypothesis": (334, 9657, 0),
    "check-todos": (196, 5207, 0),
    "compact-state": (213, 6877, 0),
    "compare-branches": (359, 11466, 0),
    "compare-experiment": (390, 17273, 0),
    "compare-results": (93, 4468, 0),
    "complete-milestone": (1178, 35882, 2),
    "debug": (308, 14683, 1),
    "decisions": (140, 3680, 0),
    "derive-equation": (649, 31756, 2),
    "digest-knowledge": (226, 9317, 0),
    "dimensional-analysis": (314, 12789, 0),
    "discover": (356, 14222, 0),
    "discuss-phase": (633, 25170, 0),
    "error-patterns": (143, 3937, 0),
    "error-propagation": (387, 17168, 0),
    "execute-phase": (1974, 102408, 2),
    "execute-plan": (802, 51666, 0),
    "explain": (269, 10580, 1),
    "export": (432, 11274, 0),
    "export-logs": (165, 5397, 0),
    "graph": (258, 8104, 0),
    "help": (1370, 72486, 2),
    "insert-phase": (151, 4365, 0),
    "limiting-cases": (464, 21443, 0),
    "list-phase-assumptions": (279, 9881, 0),
    "literature-review": (528, 25198, 1),
    "map-research": (574, 21688, 1),
    "merge-phases": (348, 11234, 0),
    "new-milestone": (727, 35998, 1),
    "new-project": (1949, 90360, 2),
    "numerical-convergence": (482, 23820, 0),
    "parameter-sweep": (748, 28648, 1),
    "pause-work": (273, 13060, 0),
    "peer-review": (1045, 63805, 2),
    "plan-milestone-gaps": (290, 7888, 0),
    "plan-phase": (1018, 51961, 1),
    "progress": (574, 19223, 0),
    "quick": (348, 15685, 1),
    "reapply-patches": (114, 3750, 0),
    "record-backtrack": (208, 9259, 0),
    "record-insight": (122, 3969, 0),
    "regression-check": (123, 4515, 0),
    "remove-phase": (184, 4612, 0),
    "research-phase": (329, 14238, 2),
    "respond-to-referees": (2029, 103819, 5),
    "resume-work": (603, 30721, 2),
    "review-knowledge": (660, 22023, 3),
    "revise-phase": (424, 12774, 0),
    "route": (119, 4607, 0),
    "sensitivity-analysis": (656, 28242, 0),
    "set-profile": (185, 8685, 0),
    "set-tier-models": (171, 6674, 0),
    "settings": (488, 29651, 2),
    "show-phase": (249, 6801, 0),
    "slides": (200, 8586, 0),
    "start": (253, 13223, 2),
    "sync-state": (253, 8776, 0),
    "tangent": (149, 5858, 0),
    "tour": (174, 7340, 1),
    "transition": (1064, 33370, 0),
    "undo": (299, 9670, 0),
    "update": (242, 6644, 0),
    "validate-conventions": (225, 8911, 1),
    "verify-phase": (2650, 135785, 8),
    "verify-work": (647, 33242, 2),
    "write-paper": (1844, 99703, 7),
}
WORST_WORKFLOW_HARD_CAPS = {
    "verify-phase": (2_700, 138_000),
    "write-paper": (2_400, 128_000),
    "respond-to-referees": (2_070, 106_500),
    "new-project": (2_020, 94_500),
    "execute-phase": (2_010, 104_500),
}
EAGER_LOADED_BULKY_REFERENCE_INCLUDE_FILES = (
    "peer-review-panel.md",
    "contradiction-resolution-example.md",
    "ising-experiment-design-example.md",
)


def test_command_prompt_budget_registry_covers_all_command_sources() -> None:
    assert set(COMMAND_NAMES) == {path.stem for path in COMMANDS_DIR.glob("*.md")}
    assert set(COMMAND_BASELINES) == set(COMMAND_NAMES)


@pytest.mark.parametrize("command_name", COMMAND_NAMES)
def test_expanded_command_prompt_stays_under_registry_budget(command_name: str) -> None:
    baseline_lines, baseline_chars, max_raw_includes = COMMAND_BASELINES[command_name]
    metrics = measure_prompt_surface(
        COMMANDS_DIR / f"{command_name}.md",
        src_root=SOURCE_ROOT,
        path_prefix=PATH_PREFIX,
    )

    assert metrics.raw_include_count <= max_raw_includes
    assert metrics.expanded_line_count <= budget_from_baseline(
        baseline_lines,
        minimum_margin=MIN_LINE_MARGIN,
    )
    assert metrics.expanded_char_count <= budget_from_baseline(
        baseline_chars,
        minimum_margin=MIN_CHAR_MARGIN,
    )


@pytest.mark.parametrize("command_name", sorted(WORST_COMMAND_HARD_CAPS))
def test_worst_expanded_command_prompts_stay_under_hard_caps(command_name: str) -> None:
    max_lines, max_chars = WORST_COMMAND_HARD_CAPS[command_name]
    metrics = measure_prompt_surface(
        COMMANDS_DIR / f"{command_name}.md",
        src_root=SOURCE_ROOT,
        path_prefix=PATH_PREFIX,
    )

    assert metrics.expanded_line_count <= max_lines
    assert metrics.expanded_char_count <= max_chars


@pytest.mark.parametrize("runtime", RUNTIME_NAMES)
@pytest.mark.parametrize("command_name", sorted(PROJECTED_COMMAND_HARD_CAPS))
def test_actual_runtime_projected_command_prompts_stay_under_hard_caps(command_name: str, runtime: str) -> None:
    max_lines, max_chars = PROJECTED_COMMAND_HARD_CAPS[command_name]
    metrics = measure_projected_prompt_surface(
        COMMANDS_DIR / f"{command_name}.md",
        runtime=runtime,
        src_root=SOURCE_ROOT,
        path_prefix=PATH_PREFIX,
        command_name=command_name,
    )

    assert metrics.expanded_line_count <= max_lines
    assert metrics.expanded_char_count <= max_chars


def test_largest_command_prompts_have_hard_caps() -> None:
    largest_commands = {
        name
        for name, _baseline in sorted(
            COMMAND_BASELINES.items(),
            key=lambda item: item[1][1],
            reverse=True,
        )[:TOP_COMMAND_HARD_CAP_COUNT]
    }

    assert largest_commands <= set(WORST_COMMAND_HARD_CAPS)


@pytest.mark.parametrize("command_name", sorted(WORST_COMMAND_HARD_CAPS))
def test_command_wrappers_do_not_eager_load_bulk_contract_templates(command_name: str) -> None:
    expanded_text = expanded_prompt_text(
        COMMANDS_DIR / f"{command_name}.md",
        src_root=SOURCE_ROOT,
        path_prefix=PATH_PREFIX,
    )
    markers = set(expanded_include_markers(expanded_text))

    for marker in BULKY_COMMAND_INCLUDE_FILES:
        assert marker not in markers


def test_workflow_prompt_budget_table_covers_all_workflow_sources() -> None:
    assert set(WORKFLOW_BASELINES) == set(WORKFLOW_NAMES)


@pytest.mark.parametrize("workflow_name", WORKFLOW_NAMES)
def test_expanded_workflow_prompt_stays_under_registry_budget(workflow_name: str) -> None:
    baseline_lines, baseline_chars, max_raw_includes = WORKFLOW_BASELINES[workflow_name]
    metrics = measure_prompt_surface(
        WORKFLOWS_DIR / f"{workflow_name}.md",
        src_root=SOURCE_ROOT,
        path_prefix=PATH_PREFIX,
    )

    assert metrics.raw_include_count <= max_raw_includes
    assert metrics.expanded_line_count <= budget_from_baseline(
        baseline_lines,
        minimum_margin=MIN_LINE_MARGIN,
    )
    assert metrics.expanded_char_count <= budget_from_baseline(
        baseline_chars,
        minimum_margin=MIN_CHAR_MARGIN,
    )


@pytest.mark.parametrize("workflow_name", sorted(WORST_WORKFLOW_HARD_CAPS))
def test_worst_expanded_workflows_stay_under_hard_caps(workflow_name: str) -> None:
    max_lines, max_chars = WORST_WORKFLOW_HARD_CAPS[workflow_name]
    metrics = measure_prompt_surface(
        WORKFLOWS_DIR / f"{workflow_name}.md",
        src_root=SOURCE_ROOT,
        path_prefix=PATH_PREFIX,
    )

    assert metrics.expanded_line_count <= max_lines
    assert metrics.expanded_char_count <= max_chars


@pytest.mark.parametrize("workflow_name", sorted(WORST_WORKFLOW_HARD_CAPS))
def test_worst_workflows_do_not_eager_load_bulky_reference_examples(workflow_name: str) -> None:
    expanded_text = expanded_prompt_text(
        WORKFLOWS_DIR / f"{workflow_name}.md",
        src_root=SOURCE_ROOT,
        path_prefix=PATH_PREFIX,
    )
    markers = set(expanded_include_markers(expanded_text))

    for marker in EAGER_LOADED_BULKY_REFERENCE_INCLUDE_FILES:
        assert marker not in markers
