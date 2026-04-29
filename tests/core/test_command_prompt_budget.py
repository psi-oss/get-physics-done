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
    "add-phase": (170, 4_372, 1),
    "add-todo": (221, 6_389, 1),
    "arxiv-submission": (418, 20_587, 1),
    "audit-milestone": (518, 20_069, 1),
    "autonomous": (1_080, 37_040, 1),
    "branch-hypothesis": (383, 11_132, 1),
    "check-todos": (232, 6_202, 1),
    "compact-state": (259, 8_315, 1),
    "compare-branches": (395, 12_486, 1),
    "compare-experiment": (482, 21_045, 1),
    "compare-results": (160, 6_877, 1),
    "complete-milestone": (1_240, 37_879, 3),
    "debug": (359, 16_565, 1),
    "decisions": (171, 4_277, 1),
    "derive-equation": (731, 35_563, 1),
    "digest-knowledge": (313, 12_500, 1),
    "dimensional-analysis": (406, 16_163, 1),
    "discover": (474, 18_904, 1),
    "discuss-phase": (1_074, 41_469, 2),
    "error-patterns": (261, 6_377, 1),
    "error-propagation": (436, 18_588, 1),
    "execute-phase": (2_027, 101_820, 1),
    "explain": (356, 13_192, 1),
    "export": (488, 12_880, 1),
    "export-logs": (260, 8_323, 1),
    "graph": (337, 10_487, 1),
    "health": (103, 3_132, 0),
    "help": (1_427, 74_980, 1),
    "insert-phase": (198, 5_945, 1),
    "limiting-cases": (543, 23_645, 1),
    "list-phase-assumptions": (385, 13_881, 1),
    "literature-review": (578, 27_305, 1),
    "map-research": (551, 23_104, 1),
    "merge-phases": (387, 12_144, 1),
    "new-milestone": (802, 38_778, 1),
    "new-project": (2_097, 97_272, 1),
    "numerical-convergence": (570, 27_150, 1),
    "parameter-sweep": (829, 30_745, 1),
    "pause-work": (300, 13_599, 1),
    "peer-review": (1_238, 71_171, 1),
    "plan-milestone-gaps": (357, 11_407, 1),
    "plan-phase": (1_066, 53_581, 1),
    "progress": (612, 20_396, 1),
    "quick": (434, 18_919, 1),
    "reapply-patches": (151, 4_511, 1),
    "record-backtrack": (247, 10_264, 1),
    "record-insight": (161, 4_853, 1),
    "regression-check": (180, 6_665, 1),
    "remove-phase": (231, 6_061, 1),
    "research-phase": (375, 15_527, 1),
    "respond-to-referees": (890, 50_699, 2),
    "resume-work": (605, 30_515, 1),
    "review-knowledge": (332, 12_854, 1),
    "revise-phase": (475, 14_516, 1),
    "route": (174, 6_770, 1),
    "sensitivity-analysis": (745, 31_658, 1),
    "set-profile": (162, 8_861, 1),
    "set-tier-models": (219, 8_220, 1),
    "settings": (506, 29_869, 1),
    "show-phase": (345, 9_503, 1),
    "slides": (286, 11_462, 1),
    "start": (315, 15_859, 2),
    "suggest-next": (91, 3_059, 0),
    "sync-state": (301, 10_047, 1),
    "tangent": (207, 7_444, 1),
    "tour": (222, 8_946, 2),
    "undo": (348, 11_419, 1),
    "update": (267, 7_109, 1),
    "validate-conventions": (266, 10_102, 1),
    "verify-work": (726, 36_091, 1),
    "write-paper": (1_484, 86_007, 1),
}
WORST_COMMAND_HARD_CAPS = {
    "write-paper": (1_600, 91_000),
    "plan-phase": (1_110, 56_000),
    "execute-phase": (2_050, 106_000),
    "new-project": (2_150, 101_000),
    "help": (1_480, 78_000),
    "peer-review": (1_280, 74_000),
}
PROJECTED_COMMAND_HARD_CAPS = {
    "execute-phase": (2_100, 116_000),
    "new-project": (2_200, 107_000),
    "research-phase": (430, 22_000),
    "respond-to-referees": (1_000, 62_000),
    "write-paper": (1_700, 100_000),
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
    "add-phase": (131, 3358, 0),
    "add-todo": (180, 5106, 0),
    "arxiv-submission": (293, 16_009, 1),
    "audit-milestone": (430, 15206, 1),
    "autonomous": (1028, 35321, 0),
    "branch-hypothesis": (334, 9657, 0),
    "check-todos": (196, 5207, 0),
    "compact-state": (213, 6948, 0),
    "compare-branches": (359, 11466, 0),
    "compare-experiment": (390, 17283, 0),
    "compare-results": (93, 4468, 0),
    "complete-milestone": (861, 26726, 0),
    "debug": (308, 14683, 1),
    "decisions": (140, 3680, 0),
    "derive-equation": (651, 32342, 2),
    "digest-knowledge": (226, 9334, 0),
    "dimensional-analysis": (314, 12789, 0),
    "discover": (356, 14222, 0),
    "discuss-phase": (633, 25169, 0),
    "error-patterns": (143, 3937, 0),
    "error-propagation": (387, 17168, 0),
    "execute-phase": (1_986, 100_768, 2),
    "execute-plan": (802, 51664, 0),
    "explain": (269, 10580, 1),
    "export": (432, 11274, 0),
    "export-logs": (169, 5446, 0),
    "graph": (258, 8104, 0),
    "help": (1357, 71431, 1),
    "insert-phase": (151, 4367, 0),
    "limiting-cases": (464, 21443, 0),
    "list-phase-assumptions": (279, 9881, 0),
    "literature-review": (531, 25778, 1),
    "map-research": (512, 21_663, 1),
    "merge-phases": (348, 11234, 0),
    "new-milestone": (727, 35998, 1),
    "new-project": (1_959, 90_682, 2),
    "numerical-convergence": (482, 23820, 0),
    "parameter-sweep": (748, 28648, 1),
    "pause-work": (273, 13059, 0),
    "peer-review": (1050, 61424, 2),
    "plan-milestone-gaps": (290, 7888, 0),
    "plan-phase": (1018, 51986, 1),
    "progress": (576, 19413, 0),
    "quick": (348, 15685, 1),
    "reapply-patches": (114, 3750, 0),
    "record-backtrack": (208, 9259, 0),
    "record-insight": (122, 3969, 0),
    "regression-check": (123, 4515, 0),
    "remove-phase": (184, 4612, 0),
    "research-phase": (329, 14238, 2),
    "respond-to-referees": (774, 45122, 2),
    "resume-work": (575, 29949, 2),
    "review-knowledge": (223, 8376, 0),
    "revise-phase": (424, 12774, 0),
    "route": (119, 4607, 0),
    "sensitivity-analysis": (656, 28242, 0),
    "set-profile": (125, 6743, 0),
    "set-tier-models": (171, 6674, 0),
    "settings": (472, 28693, 1),
    "show-phase": (249, 6801, 0),
    "slides": (200, 8586, 0),
    "start": (258, 13591, 2),
    "sync-state": (259, 9110, 0),
    "tangent": (149, 5858, 0),
    "tour": (169, 7018, 1),
    "transition": (1064, 33368, 0),
    "undo": (299, 9670, 0),
    "update": (242, 6644, 0),
    "validate-conventions": (225, 8911, 1),
    "verify-phase": (681, 41_946, 0),
    "verify-work": (653, 34201, 2),
    "write-paper": (1336, 80049, 2),
}
WORST_WORKFLOW_HARD_CAPS = {
    "verify-phase": (720, 44_000),
    "write-paper": (1_420, 85_000),
    "respond-to-referees": (800, 46_000),
    "new-project": (2_020, 94_000),
    "execute-phase": (2_010, 104_500),
    "help": (1_420, 74_000),
}
EAGER_LOADED_BULKY_REFERENCE_INCLUDE_FILES = (
    "peer-review-panel.md",
    "contradiction-resolution-example.md",
    "ising-experiment-design-example.md",
)


def _assert_prompt_baseline_is_current(
    *,
    baseline_lines: int,
    baseline_chars: int,
    measured_lines: int,
    measured_chars: int,
) -> None:
    assert baseline_lines <= budget_from_baseline(
        measured_lines,
        minimum_margin=MIN_LINE_MARGIN,
    )
    assert baseline_chars <= budget_from_baseline(
        measured_chars,
        minimum_margin=MIN_CHAR_MARGIN,
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
    _assert_prompt_baseline_is_current(
        baseline_lines=baseline_lines,
        baseline_chars=baseline_chars,
        measured_lines=metrics.expanded_line_count,
        measured_chars=metrics.expanded_char_count,
    )
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
    _assert_prompt_baseline_is_current(
        baseline_lines=baseline_lines,
        baseline_chars=baseline_chars,
        measured_lines=metrics.expanded_line_count,
        measured_chars=metrics.expanded_char_count,
    )
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
