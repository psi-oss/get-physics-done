"""Load and aggregate benchmark task suites from the tasks/ directory.

Provides functions to discover task files, load individual suites,
and assemble a combined suite across all physics subfields.
"""

from __future__ import annotations

from pathlib import Path

from benchmarks.schema import BenchmarkSuite, BenchmarkTask, Difficulty, TaskType, load_suite

TASKS_DIR = Path(__file__).resolve().parent / "tasks"


def discover_task_files() -> list[Path]:
    """Return sorted list of JSON task files in the tasks/ directory."""
    if not TASKS_DIR.is_dir():
        return []
    return sorted(TASKS_DIR.glob("*.json"))


def load_all_suites() -> list[BenchmarkSuite]:
    """Load all benchmark suites from the tasks/ directory."""
    suites: list[BenchmarkSuite] = []
    for path in discover_task_files():
        suites.append(load_suite(path))
    return suites


def load_combined_suite() -> BenchmarkSuite:
    """Load all task files and combine into a single suite."""
    all_tasks: list[BenchmarkTask] = []
    for suite in load_all_suites():
        all_tasks.extend(suite.tasks)
    return BenchmarkSuite(
        name="GPD Physics Benchmark -- Combined",
        version="0.1.0",
        description="Combined benchmark suite across all physics subfields.",
        tasks=all_tasks,
    )


def load_suite_by_subfield(subfield: str) -> BenchmarkSuite:
    """Load the combined suite and filter to a single subfield."""
    combined = load_combined_suite()
    return combined.filter_by_subfield(subfield)


def load_suite_by_difficulty(difficulty: str) -> BenchmarkSuite:
    """Load the combined suite and filter to a single difficulty level."""
    combined = load_combined_suite()
    return combined.filter_by_difficulty(Difficulty(difficulty))


def load_suite_by_task_type(task_type: str) -> BenchmarkSuite:
    """Load the combined suite and filter to a single task type."""
    combined = load_combined_suite()
    return combined.filter_by_task_type(TaskType(task_type))


def print_inventory() -> str:
    """Return a human-readable summary of the benchmark inventory."""
    combined = load_combined_suite()
    lines = [
        f"GPD Physics Benchmark Suite v{combined.version}",
        f"Total tasks: {len(combined.tasks)}",
        "",
        "By subfield:",
    ]
    for sf in combined.subfields:
        count = len(combined.filter_by_subfield(sf).tasks)
        lines.append(f"  {sf}: {count}")
    lines.append("")
    lines.append("By difficulty:")
    for d in combined.difficulties:
        count = len(combined.filter_by_difficulty(d).tasks)
        lines.append(f"  {d.value}: {count}")
    lines.append("")
    lines.append("By task type:")
    for tt in combined.task_types:
        count = len(combined.filter_by_task_type(tt).tasks)
        lines.append(f"  {tt.value}: {count}")
    return "\n".join(lines)
