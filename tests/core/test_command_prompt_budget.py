"""Registry-wide expanded prompt budget coverage for commands."""

from __future__ import annotations

from math import ceil
from pathlib import Path

import pytest

from gpd import registry
from tests.prompt_metrics_support import measure_prompt_surface

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_DIR = REPO_ROOT / "src" / "gpd" / "commands"
SOURCE_ROOT = REPO_ROOT / "src" / "gpd"
PATH_PREFIX = "/runtime/"

PROMPT_BUDGET_MARGIN = 0.03
MIN_LINE_MARGIN = 20
MIN_CHAR_MARGIN = 1_000
COMMAND_NAMES = tuple(registry.list_commands())

COMMAND_BASELINES = {
    "add-phase": (170, 4_382, 1),
    "add-todo": (221, 6_401, 1),
    "arxiv-submission": (661, 47_314, 1),
    "audit-milestone": (539, 20_958, 1),
    "autonomous": (1_080, 37_060, 1),
    "branch-hypothesis": (383, 11_178, 1),
    "check-todos": (232, 6_214, 1),
    "compact-state": (259, 8_256, 1),
    "compare-branches": (395, 12_531, 1),
    "compare-experiment": (491, 22_204, 1),
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
    "explain": (403, 17_832, 1),
    "export": (508, 13_232, 1),
    "export-logs": (248, 8_165, 1),
    "graph": (337, 10_521, 1),
    "health": (103, 3_132, 0),
    "help": (1_420, 74_433, 1),
    "insert-phase": (198, 5_984, 1),
    "limiting-cases": (570, 25_674, 1),
    "list-phase-assumptions": (385, 13_881, 1),
    "literature-review": (594, 27_547, 1),
    "map-research": (614, 23_176, 1),
    "merge-phases": (387, 12_059, 1),
    "new-milestone": (852, 41_088, 1),
    "new-project": (2_406, 101_367, 1),
    "numerical-convergence": (570, 27_200, 1),
    "parameter-sweep": (840, 31_582, 1),
    "pause-work": (300, 13_612, 1),
    "peer-review": (1_148, 71_076, 1),
    "plan-milestone-gaps": (357, 11_455, 1),
    "plan-phase": (1_067, 53_460, 1),
    "progress": (605, 19_549, 1),
    "quick": (458, 19_574, 1),
    "reapply-patches": (155, 4_901, 1),
    "record-backtrack": (247, 10_276, 1),
    "record-insight": (161, 4_865, 1),
    "regression-check": (180, 6_710, 1),
    "remove-phase": (231, 6_102, 1),
    "research-phase": (433, 18_247, 2),
    "respond-to-referees": (2_438, 117_818, 2),
    "resume-work": (1_654, 81_734, 1),
    "review-knowledge": (770, 26_193, 1),
    "revise-phase": (475, 14_557, 1),
    "route": (174, 6_782, 1),
    "sensitivity-analysis": (747, 31_519, 1),
    "set-profile": (228, 10_832, 1),
    "set-tier-models": (219, 8_347, 1),
    "settings": (497, 29_348, 1),
    "show-phase": (345, 9_542, 1),
    "slides": (286, 11_499, 1),
    "start": (272, 14_136, 2),
    "suggest-next": (91, 3_083, 0),
    "sync-state": (900, 41_547, 1),
    "tangent": (207, 7_482, 1),
    "tour": (220, 9_098, 2),
    "undo": (376, 12_127, 1),
    "update": (250, 6_145, 1),
    "validate-conventions": (267, 10_133, 1),
    "verify-work": (665, 33_033, 1),
    "write-paper": (2_465, 127_530, 1),
}


def test_command_prompt_budget_registry_covers_all_command_sources() -> None:
    assert set(COMMAND_NAMES) == {path.stem for path in COMMANDS_DIR.glob("*.md")}
    assert set(COMMAND_BASELINES) == set(COMMAND_NAMES)


def _budget_from_baseline(value: int, *, minimum_margin: int) -> int:
    return value + max(minimum_margin, ceil(value * PROMPT_BUDGET_MARGIN))


@pytest.mark.parametrize("command_name", COMMAND_NAMES)
def test_expanded_command_prompt_stays_under_registry_budget(command_name: str) -> None:
    baseline_lines, baseline_chars, max_raw_includes = COMMAND_BASELINES[command_name]
    metrics = measure_prompt_surface(
        COMMANDS_DIR / f"{command_name}.md",
        src_root=SOURCE_ROOT,
        path_prefix=PATH_PREFIX,
    )

    assert metrics.raw_include_count <= max_raw_includes
    assert metrics.expanded_line_count <= _budget_from_baseline(
        baseline_lines,
        minimum_margin=MIN_LINE_MARGIN,
    )
    assert metrics.expanded_char_count <= _budget_from_baseline(
        baseline_chars,
        minimum_margin=MIN_CHAR_MARGIN,
    )
