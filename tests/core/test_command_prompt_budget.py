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
    "add-phase": (170, 4_340, 1),
    "add-todo": (227, 6_977, 1),
    "arxiv-submission": (267, 11_390, 1),
    "audit-milestone": (518, 20_292, 1),
    "autonomous": (77, 2_089, 1),
    "branch-hypothesis": (383, 11_072, 1),
    "build-persona": (173, 7_123, 1),
    "check-todos": (241, 6_763, 1),
    "compact-state": (259, 8_283, 1),
    "compare-branches": (395, 12_490, 1),
    "compare-experiment": (492, 21_327, 1),
    "compare-results": (169, 7_268, 1),
    "complete-milestone": (343, 10_395, 1),
    "debug": (362, 16_984, 1),
    "decisions": (171, 4_277, 1),
    "derive-equation": (412, 18_028, 1),
    "digest-knowledge": (313, 12_468, 1),
    "dimensional-analysis": (406, 16_131, 1),
    "discover": (474, 18_872, 1),
    "discuss-phase": (301, 9_815, 1),
    "error-patterns": (258, 6_372, 1),
    "error-propagation": (436, 18_556, 1),
    "execute-phase": (166, 5_602, 1),
    "explain": (357, 13_532, 1),
    "export": (463, 13_951, 1),
    "export-logs": (248, 9_260, 1),
    "graph": (337, 10_491, 1),
    "health": (103, 3_132, 0),
    "help": (124, 6_778, 0),
    "insert-phase": (198, 5_913, 1),
    "limiting-cases": (317, 11_484, 1),
    "list-phase-assumptions": (393, 14_092, 1),
    "literature-review": (168, 6_959, 1),
    "map-research": (196, 7_309, 1),
    "merge-phases": (387, 12_144, 1),
    "new-milestone": (146, 5_328, 1),
    "new-project": (188, 8_478, 1),
    "numerical-convergence": (302, 11_669, 1),
    "parameter-sweep": (363, 14_334, 1),
    "pause-work": (302, 13_207, 1),
    "peer-review": (307, 15_265, 1),
    "plan-milestone-gaps": (357, 11_407, 1),
    "plan-phase": (186, 9_088, 1),
    "progress": (373, 15_281, 1),
    "quick": (182, 8_746, 1),
    "reapply-patches": (151, 4_511, 1),
    "record-backtrack": (247, 10_264, 1),
    "record-insight": (161, 4_853, 1),
    "regression-check": (180, 6_665, 1),
    "remove-phase": (231, 6_029, 1),
    "research-phase": (216, 7_402, 1),
    "respond-to-referees": (296, 13_294, 1),
    "resume-work": (115, 6_339, 1),
    "review-knowledge": (332, 12_826, 1),
    "revise-phase": (475, 14_484, 1),
    "route": (185, 7_305, 1),
    "sensitivity-analysis": (319, 12_142, 1),
    "set-profile": (171, 9_451, 1),
    "set-tier-models": (215, 8_447, 1),
    "settings": (372, 19_230, 1),
    "show-phase": (345, 9_471, 1),
    "slides": (251, 11_802, 1),
    "start": (294, 19_921, 2),
    "suggest-next": (95, 3_258, 0),
    "sync-state": (108, 3_637, 1),
    "tangent": (211, 8_206, 1),
    "tour": (228, 10_119, 2),
    "undo": (348, 11_419, 1),
    "update": (269, 7_655, 1),
    "validate-conventions": (271, 10_556, 1),
    "verify-work": (228, 8_001, 1),
    "write-paper": (332, 14_789, 1),
}
WORST_COMMAND_HARD_CAPS = {
    "compare-experiment": (540, 22_500),
    "build-persona": (200, 8_200),
    "audit-milestone": (560, 21_500),
    "start": (330, 21_000),
    "settings": (400, 20_500),
    "discover": (510, 20_000),
    "error-propagation": (470, 19_700),
}
PROJECTED_COMMAND_HARD_CAPS = {
    "execute-phase": (140, 7_500),
    "new-project": (180, 10_500),
    "research-phase": (140, 7_700),
    "respond-to-referees": (260, 13_500),
    "verify-work": (200, 10_000),
    "write-paper": (340, 15_500),
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
    "add-phase": (131, 3_326, 0),
    "add-todo": (186, 5_694, 0),
    "arxiv-submission": (31, 1_773, 0),
    "audit-milestone": (430, 15_421, 1),
    "autonomous": (43, 2_023, 0),
    "branch-hypothesis": (334, 9_597, 0),
    "build-persona": (316, 15_374, 0),
    "check-todos": (205, 5_768, 0),
    "compact-state": (213, 6_916, 0),
    "compare-branches": (359, 11_470, 0),
    "compare-experiment": (400, 17_557, 0),
    "compare-results": (102, 4_851, 0),
    "complete-milestone": (282, 8_933, 0),
    "debug": (311, 15_102, 1),
    "decisions": (140, 3_680, 0),
    "derive-equation": (338, 15_266, 2),
    "digest-knowledge": (226, 9_302, 0),
    "dimensional-analysis": (314, 12_757, 0),
    "discover": (356, 14_190, 0),
    "discuss-phase": (248, 8_232, 0),
    "error-patterns": (143, 3_937, 0),
    "error-propagation": (387, 17_136, 0),
    "execute-phase": (29, 1_702, 0),
    "execute-plan": (341, 23_920, 0),
    "explain": (270, 10_920, 1),
    "export": (404, 12_181, 0),
    "export-logs": (170, 6_195, 0),
    "graph": (258, 8_108, 0),
    "help": (441, 32_986, 0),
    "insert-phase": (151, 4_335, 0),
    "limiting-cases": (238, 9_282, 0),
    "list-phase-assumptions": (279, 9_881, 0),
    "literature-review": (22, 1_280, 0),
    "map-research": (21, 1_179, 0),
    "merge-phases": (348, 11_234, 0),
    "new-milestone": (23, 1_399, 0),
    "new-project": (45, 2_106, 1),
    "numerical-convergence": (216, 8_729, 0),
    "parameter-sweep": (282, 12_229, 1),
    "pause-work": (275, 12_667, 0),
    "peer-review": (28, 1_211, 0),
    "plan-milestone-gaps": (290, 7_888, 0),
    "plan-phase": (21, 1_349, 0),
    "progress": (337, 14_298, 0),
    "quick": (16, 859, 0),
    "reapply-patches": (114, 3_750, 0),
    "record-backtrack": (208, 9_259, 0),
    "record-insight": (122, 3_969, 0),
    "regression-check": (123, 4_515, 0),
    "remove-phase": (184, 4_580, 0),
    "research-phase": (23, 1_131, 0),
    "respond-to-referees": (36, 2_486, 0),
    "resume-work": (22, 1_323, 0),
    "review-knowledge": (223, 8_344, 0),
    "revise-phase": (424, 12_742, 0),
    "route": (130, 5_142, 0),
    "sensitivity-analysis": (232, 9_181, 0),
    "set-profile": (134, 7_229, 0),
    "set-tier-models": (167, 6_901, 0),
    "settings": (338, 18_054, 1),
    "show-phase": (249, 6_769, 0),
    "slides": (165, 8_926, 0),
    "start": (241, 16_680, 2),
    "sync-state": (25, 1_384, 0),
    "tangent": (152, 6_349, 0),
    "tour": (173, 7_924, 1),
    "transition": (270, 8_759, 0),
    "undo": (299, 9_670, 0),
    "update": (244, 7_190, 0),
    "validate-conventions": (230, 9_365, 1),
    "verify-phase": (377, 20_313, 0),
    "verify-work": (16, 755, 0),
    "write-paper": (31, 1_661, 0),
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
