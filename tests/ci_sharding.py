from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path

CI_CATEGORY_SHARD_COUNTS = {
    "root": 9,
    "adapters": 2,
    "hooks": 2,
    "mcp": 2,
    "core": 5,
}
CI_FAST_SUITE_BUDGET_SECONDS = 180
CI_PYTEST_SHARD_RESOLUTION_TIMEOUT_MINUTES = 3
CI_PYTEST_SHARD_TIMEOUT_MINUTES = 10
CI_SHARD_WEIGHT_SPREAD_TOLERANCE = 0.2

# Observed GitHub Actions timings on 2026-04-07 showed that these files are the
# real bottlenecks inside their category. Split them inside the file so the
# category-local planners can spread the slow work rather than pinning one
# thematic shard to a single expensive module.
CI_HOT_TEST_FILE_SPLITS = {
    "test_runtime_cli.py": 10,
    "test_cli_integration.py": 4,
    "test_registry.py": 4,
    "test_cli_commands.py": 2,
    "test_install_utils_edge.py": 2,
    "test_install_edge_cases.py": 2,
    "test_update_workflow.py": 4,
    "test_release_consistency.py": 3,
    "adapters/test_claude_code.py": 2,
    "adapters/test_codex.py": 2,
    "adapters/test_gemini.py": 2,
    "adapters/test_opencode.py": 2,
    "hooks/test_notify.py": 2,
    "hooks/test_runtime_detect.py": 2,
    "hooks/test_runtime_lookup.py": 2,
    "hooks/test_statusline.py": 2,
    "hooks/test_todo_resolution.py": 2,
    "hooks/test_update_resolution.py": 2,
    "mcp/test_servers.py": 6,
    "mcp/test_verification_contract_server_regressions.py": 6,
    "mcp/test_tool_contract_visibility.py": 3,
    "mcp/test_servers_integration.py": 3,
    "mcp/test_skills_server_tool_lists.py": 2,
    "mcp/test_server_regressions.py": 2,
    "core/test_cli.py": 3,
    "core/test_contract_validation.py": 3,
    "core/test_frontmatter.py": 3,
    "core/test_context.py": 2,
    "core/test_state.py": 2,
    "core/test_prompt_wiring.py": 2,
}

CI_HOT_TEST_FILE_WEIGHT_MULTIPLIERS = {
    "test_runtime_cli.py": 6.0,
    "test_cli_integration.py": 3.0,
    "test_registry.py": 2.0,
    "test_cli_commands.py": 1.5,
    "test_install_utils_edge.py": 1.5,
    "test_update_workflow.py": 2.0,
    "test_release_consistency.py": 2.0,
    "adapters/test_claude_code.py": 1.5,
    "adapters/test_codex.py": 2.0,
    "adapters/test_gemini.py": 2.0,
    "adapters/test_opencode.py": 2.0,
    "core/test_cli.py": 1.5,
    "core/test_contract_validation.py": 1.4,
    "hooks/test_notify.py": 2.0,
    "hooks/test_runtime_detect.py": 1.5,
    "hooks/test_runtime_lookup.py": 2.0,
    "hooks/test_statusline.py": 1.5,
    "hooks/test_todo_resolution.py": 2.0,
    "hooks/test_update_resolution.py": 2.0,
    "mcp/test_servers.py": 4.0,
    "mcp/test_verification_contract_server_regressions.py": 4.0,
    "mcp/test_tool_contract_visibility.py": 2.0,
    "mcp/test_servers_integration.py": 2.0,
    "mcp/test_skills_server_tool_lists.py": 1.5,
    "mcp/test_server_regressions.py": 1.5,
}


@dataclass(frozen=True)
class CIShardSpec:
    slug: str
    category: str
    shard_index: int
    shard_total: int

    @property
    def display_name(self) -> str:
        if self.shard_total == 1:
            return self.category
        return f"{self.category} {self.shard_index}/{self.shard_total}"


@dataclass(frozen=True)
class CIWorkUnit:
    label: str
    category: str
    targets: tuple[str, ...]
    weight: float


def category_for_test_relpath(rel_path: str) -> str:
    return rel_path.split("/", 1)[0] if "/" in rel_path else "root"


def ci_shard_specs() -> tuple[CIShardSpec, ...]:
    specs: list[CIShardSpec] = []
    for category, shard_total in CI_CATEGORY_SHARD_COUNTS.items():
        for shard_index in range(1, shard_total + 1):
            slug = category if shard_total == 1 else f"{category}-{shard_index}"
            specs.append(
                CIShardSpec(
                    slug=slug,
                    category=category,
                    shard_index=shard_index,
                    shard_total=shard_total,
                )
            )
    return tuple(specs)


def expected_ci_shard_matrix() -> tuple[tuple[str, str, int, int], ...]:
    return tuple((spec.display_name, spec.category, spec.shard_index, spec.shard_total) for spec in ci_shard_specs())


def synthetic_test_inventory() -> dict[str, tuple[str, ...]]:
    """Return a small deterministic inventory that exercises all shard shapes."""

    def _nodeids(rel_path: str, count: int) -> tuple[str, ...]:
        return tuple(f"tests/{rel_path}::test_{index:02d}" for index in range(1, count + 1))

    inventory: dict[str, tuple[str, ...]] = {
        rel_path: _nodeids(rel_path, split_count) for rel_path, split_count in CI_HOT_TEST_FILE_SPLITS.items()
    }
    inventory["test_smoke.py"] = _nodeids("test_smoke.py", 2)
    inventory["mcp/test_wolfram.py"] = ("tests/mcp/test_wolfram.py::test_smoke",)
    return inventory


def _workflow_job(workflow: dict[str, object], job_name: str) -> dict[str, object]:
    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)
    job = jobs[job_name]
    assert isinstance(job, dict)
    return job


def workflow_job_steps(workflow: dict[str, object], job_name: str) -> list[dict[str, object]]:
    job = _workflow_job(workflow, job_name)
    steps = job["steps"]
    assert isinstance(steps, list)
    assert all(isinstance(step, dict) for step in steps)
    return steps


def pytest_matrix_include(workflow: dict[str, object]) -> list[dict[str, object]]:
    pytest_job = _workflow_job(workflow, "pytest")
    strategy = pytest_job["strategy"]
    assert isinstance(strategy, dict)
    matrix = strategy["matrix"]
    assert isinstance(matrix, dict)
    include = matrix["include"]
    assert isinstance(include, list)
    assert all(isinstance(entry, dict) for entry in include)
    return include


def actual_ci_shard_matrix(workflow: dict[str, object]) -> tuple[tuple[str, str, int, int], ...]:
    return tuple(
        (
            str(entry["display_name"]),
            str(entry["category"]),
            int(entry["shard_index"]),
            int(entry["shard_total"]),
        )
        for entry in pytest_matrix_include(workflow)
    )


def assert_ci_workflow_pytest_shard_policy(workflow: dict[str, object], *, pyproject_text: str) -> None:
    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)

    pytest_steps = workflow_job_steps(workflow, "pytest")
    pytest_step_names = [str(step.get("name", "")) for step in pytest_steps]
    pytest_run_steps = {str(step.get("name", "")): str(step.get("run", "")) for step in pytest_steps if "run" in step}
    matrix_include = pytest_matrix_include(workflow)
    pytest_job = _workflow_job(workflow, "pytest")
    strategy = pytest_job["strategy"]
    assert isinstance(strategy, dict)

    assert pytest_job.get("needs") is None
    assert strategy["fail-fast"] is False
    assert actual_ci_shard_matrix(workflow) == expected_ci_shard_matrix()
    assert len(matrix_include) == sum(CI_CATEGORY_SHARD_COUNTS.values())

    # trigger-staging-rebuild moved to staging-rebuild.yml (workflow_run trigger)
    # to avoid showing as a skipped check on PRs.
    assert "trigger-staging-rebuild" not in jobs

    assert "Set up Node.js" in pytest_step_names
    assert pytest_step_names.index("Set up Node.js") < pytest_step_names.index("Install dependencies")
    resolve_targets_step = next(step for step in pytest_steps if step.get("name") == "Resolve pytest shard targets")
    resolve_targets_command = pytest_run_steps["Resolve pytest shard targets"]
    pytest_shard_command = pytest_run_steps["Run pytest shard"]
    assert resolve_targets_step["timeout-minutes"] == CI_PYTEST_SHARD_RESOLUTION_TIMEOUT_MINUTES
    assert "from tests.ci_sharding import write_ci_shard_targets_file" in resolve_targets_command
    assert "import time" in resolve_targets_command
    assert "started_at = time.perf_counter()" in resolve_targets_command
    assert "elapsed_seconds = time.perf_counter() - started_at" in resolve_targets_command
    assert "PYTEST_CATEGORY" in resolve_targets_command
    assert "PYTEST_SHARD_TARGET_FILE" in resolve_targets_command
    assert "Resolved {len(targets)} pytest targets for {os.environ['PYTEST_CATEGORY']}" in resolve_targets_command
    assert "shard {os.environ['PYTEST_SHARD_INDEX']}/{os.environ['PYTEST_SHARD_TOTAL']}" in resolve_targets_command
    assert "in {elapsed_seconds:.2f}s" in resolve_targets_command
    assert 'mapfile -t PYTEST_TARGETS < "$PYTEST_SHARD_TARGET_FILE"' in pytest_shard_command
    assert pytest_steps[-1]["timeout-minutes"] == CI_PYTEST_SHARD_TIMEOUT_MINUTES
    assert pytest_steps[-1]["env"]["GPD_FAST_SUITE_BUDGET_SECONDS"] == str(CI_FAST_SUITE_BUDGET_SECONDS)
    assert "Fast suite advisory target" not in pytest_shard_command
    assert (
        f"Fast suite budget: ${{GPD_FAST_SUITE_BUDGET_SECONDS}}s enforced per pytest shard; "
        f"job timeout: {CI_PYTEST_SHARD_TIMEOUT_MINUTES} minutes"
    ) in pytest_shard_command
    assert (
        'timeout "${GPD_FAST_SUITE_BUDGET_SECONDS}s" '
        'uv run pytest -q --durations=20 --durations-min=1.0 "${PYTEST_TARGETS[@]}"'
    ) in pytest_shard_command
    assert 'if [ "$pytest_status" -eq 124 ]; then' in pytest_shard_command
    assert (
        'echo "::error::pytest shard exceeded enforced ${GPD_FAST_SUITE_BUDGET_SECONDS}s fast-suite budget"'
    ) in pytest_shard_command
    assert 'exit "$pytest_status"' in pytest_shard_command
    assert '--durations=20 --durations-min=1.0 "${PYTEST_TARGETS[@]}"' in pytest_shard_command
    assert pytest_steps[-1]["name"] == "Run pytest shard"
    assert pytest_steps[-1]["run"] == pytest_shard_command
    checkout_step = next(step for step in pytest_steps if step.get("name") == "Check out repository")
    assert checkout_step["uses"] == "actions/checkout@v6"
    node_step = next(step for step in pytest_steps if step.get("name") == "Set up Node.js")
    assert node_step["uses"] == "actions/setup-node@v6"
    assert node_step["with"]["node-version"] == "20"
    assert 'addopts = "-n auto --dist=worksteal"' in pyproject_text
    assert "pytest-xdist>=3.8.0" in pyproject_text


def assert_tests_readme_documents_ci_shard_policy(tests_readme: str) -> None:
    assert "Default `uv run pytest` runs the full checked-in suite" in tests_readme
    assert "`uv run pytest -q` does the same with quieter output" in tests_readme
    assert "Both inherit `-n auto --dist=worksteal` from `pyproject.toml`" in tests_readme
    assert "raises xdist auto-worker selection toward the current CI shard fanout" in tests_readme
    assert "override that default explicitly with `uv run pytest -n 0`" in tests_readme
    assert "The 180 second fast-suite budget is enforced per CI pytest shard" in tests_readme
    assert "10 minute job timeout remains the outer failure boundary" in tests_readme
    assert "Shard target resolution has its own 3 minute timeout and logs elapsed seconds" in tests_readme
    assert "advisory full-suite wall-clock target" not in tests_readme
    assert "GitHub Actions workflow runs that same full suite as category-named runtime-informed shards" in tests_readme
    assert (
        "`root 1/9` through `root 9/9`, `adapters 1/2` through `adapters 2/2`, "
        "`hooks 1/2` through `hooks 2/2`, `mcp 1/2` through `mcp 2/2`, "
        "and `core 1/5` through `core 5/5`"
    ) in tests_readme
    assert "boosts root modules that have been slow on GitHub Actions" in tests_readme
    assert (
        "splits known hotspot modules such as `tests/test_runtime_cli.py`, `tests/test_registry.py`, "
        "`tests/test_update_workflow.py`, `tests/hooks/test_runtime_detect.py`, and "
        "`tests/mcp/test_verification_contract_server_regressions.py`"
    ) in tests_readme
    assert "greedily rebalances those work units inside each category" in tests_readme


def assert_contributing_documents_current_pytest_commands(contributing: str) -> None:
    assert "uv run pytest tests/ -q" in contributing
    assert "`uv run pytest tests/ -q` is the fast local full checked-in suite" in contributing
    assert "tests/ci_sharding.py" in contributing
    assert 'uv run pytest -q --durations=20 --durations-min=1.0 "${PYTEST_TARGETS[@]}"' in contributing
    assert "180 second per-shard budget" in contributing
    assert "complementary_heavy_suite_ignore_args" not in contributing
    assert "HEAVY_SUITE_IGNORE_ARGS" not in contributing
    assert "--full-suite" not in contributing
    assert "GPD_TEST_FULL" not in contributing


def _test_relpaths_from_git_lines(lines: tuple[str, ...]) -> tuple[str, ...]:
    relpaths: list[str] = []
    for line in lines:
        if not line:
            continue
        path = Path(line)
        if path.parts[:1] != ("tests",):
            continue
        if path.suffix != ".py" or not path.name.startswith("test_"):
            continue
        relpaths.append(Path(*path.parts[1:]).as_posix())
    return tuple(sorted(relpaths))


def _test_python_relpaths_from_git_lines(lines: tuple[str, ...]) -> tuple[str, ...]:
    relpaths: list[str] = []
    for line in lines:
        if not line:
            continue
        path = Path(line)
        if path.parts[:1] != ("tests",):
            continue
        if path.suffix != ".py":
            continue
        relpaths.append(Path(*path.parts[1:]).as_posix())
    return tuple(sorted(relpaths))


def _git_test_relpaths(repo_root: Path, *ls_files_args: str) -> tuple[str, ...]:
    proc = subprocess.run(
        ["git", "ls-files", "--full-name", *ls_files_args, "--", "tests"],
        cwd=repo_root,
        check=True,
        text=True,
        capture_output=True,
    )
    return _test_relpaths_from_git_lines(tuple(proc.stdout.splitlines()))


def checked_in_test_relpaths(
    *,
    repo_root: Path | None = None,
    category: str | None = None,
) -> tuple[str, ...]:
    relpaths = _git_test_relpaths(_normalized_repo_root(repo_root), "--cached")
    if category is not None:
        relpaths = tuple(relpath for relpath in relpaths if category_for_test_relpath(relpath) == category)
    return relpaths


def untracked_non_ignored_test_relpaths(
    *,
    repo_root: Path | None = None,
) -> tuple[str, ...]:
    proc = subprocess.run(
        ["git", "ls-files", "--full-name", "--others", "--exclude-standard", "--", "tests"],
        cwd=_normalized_repo_root(repo_root),
        check=True,
        text=True,
        capture_output=True,
    )
    return _test_python_relpaths_from_git_lines(tuple(proc.stdout.splitlines()))


def all_test_relpaths(*, tests_root: Path) -> tuple[str, ...]:
    return checked_in_test_relpaths(repo_root=tests_root.resolve().parent)


def _normalized_repo_root(repo_root: Path | str | None) -> Path:
    return (Path.cwd() if repo_root is None else Path(repo_root)).resolve()


def _pytest_collection_targets(repo_root: Path, *, category: str | None = None) -> tuple[str, ...]:
    return tuple(f"tests/{relpath}" for relpath in checked_in_test_relpaths(repo_root=repo_root, category=category))


@cache
def _collected_test_inventory_items(
    repo_root: Path,
    category: str | None = None,
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    collection_targets = _pytest_collection_targets(repo_root, category=category)
    if not collection_targets:
        return ()

    env = os.environ.copy()
    env.pop("PYTEST_ADDOPTS", None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "no:cacheprovider",
            *collection_targets,
            "--collect-only",
            "-q",
            "-n",
            "0",
        ],
        cwd=repo_root,
        env=env,
        check=True,
        text=True,
        capture_output=True,
    )

    inventory: dict[str, list[str]] = {}
    for line in proc.stdout.splitlines():
        if "::" not in line:
            continue
        path_text = line.split("::", 1)[0]
        if path_text.startswith("tests/"):
            path_text = path_text[len("tests/") :]
        inventory.setdefault(path_text, []).append(line)
    return tuple((rel_path, tuple(nodeids)) for rel_path, nodeids in sorted(inventory.items()))


def collected_test_inventory(
    *,
    repo_root: Path | None = None,
    category: str | None = None,
) -> dict[str, tuple[str, ...]]:
    return dict(_collected_test_inventory_items(_normalized_repo_root(repo_root), category))


def collected_test_counts_by_file(
    *,
    repo_root: Path | None = None,
    category: str | None = None,
) -> dict[str, int]:
    return {
        rel_path: len(nodeids)
        for rel_path, nodeids in collected_test_inventory(repo_root=repo_root, category=category).items()
    }


def _split_nodeids_round_robin(nodeids: tuple[str, ...], *, parts: int) -> tuple[tuple[str, ...], ...]:
    if parts < 1:
        raise ValueError("parts must be positive")
    buckets: list[list[str]] = [[] for _ in range(parts)]
    for index, nodeid in enumerate(nodeids):
        buckets[index % parts].append(nodeid)
    return tuple(tuple(bucket) for bucket in buckets if bucket)


def _file_weight(rel_path: str, *, test_count: int) -> float:
    return test_count * CI_HOT_TEST_FILE_WEIGHT_MULTIPLIERS.get(rel_path, 1.0)


def build_ci_work_units(
    inventory: Mapping[str, tuple[str, ...]],
) -> tuple[CIWorkUnit, ...]:
    work_units: list[CIWorkUnit] = []

    for rel_path, nodeids in inventory.items():
        category = category_for_test_relpath(rel_path)
        split_parts = CI_HOT_TEST_FILE_SPLITS.get(rel_path, 1)
        split_groups = _split_nodeids_round_robin(nodeids, parts=split_parts)
        total_weight = _file_weight(rel_path, test_count=len(nodeids))
        scale = total_weight / len(nodeids)

        if len(split_groups) == 1:
            work_units.append(
                CIWorkUnit(
                    label=rel_path,
                    category=category,
                    targets=(f"tests/{rel_path}",),
                    weight=total_weight,
                )
            )
            continue

        for group_index, group in enumerate(split_groups, start=1):
            work_units.append(
                CIWorkUnit(
                    label=f"{rel_path} [{group_index}/{len(split_groups)}]",
                    category=category,
                    targets=group,
                    weight=len(group) * scale,
                )
            )

    return tuple(sorted(work_units, key=lambda unit: (-unit.weight, unit.label)))


def plan_work_units_into_shards(
    work_units: tuple[CIWorkUnit, ...],
    *,
    shard_total: int,
) -> tuple[tuple[str, ...], ...]:
    if shard_total < 1:
        raise ValueError("shard_total must be positive")

    shard_targets: list[list[str]] = [[] for _ in range(shard_total)]
    shard_weights = [0.0] * shard_total

    for unit in work_units:
        shard_index = min(
            range(shard_total),
            key=lambda index: (shard_weights[index], len(shard_targets[index]), index),
        )
        shard_targets[shard_index].extend(unit.targets)
        shard_weights[shard_index] += unit.weight

    return tuple(tuple(targets) for targets in shard_targets)


def plan_category_ci_shards(
    *,
    category: str,
    repo_root: Path | None = None,
    inventory: Mapping[str, tuple[str, ...]] | None = None,
    work_units: tuple[CIWorkUnit, ...] | None = None,
) -> tuple[tuple[str, ...], ...]:
    if work_units is None:
        if inventory is None:
            inventory = collected_test_inventory(repo_root=repo_root, category=category)
        work_units = build_ci_work_units(inventory)
    category_work_units = tuple(unit for unit in work_units if unit.category == category)
    if not category_work_units:
        raise ValueError(f"no work units matched category {category!r}")
    return plan_work_units_into_shards(category_work_units, shard_total=CI_CATEGORY_SHARD_COUNTS[category])


def expand_ci_targets_to_nodeids(
    targets: tuple[str, ...],
    *,
    inventory: Mapping[str, tuple[str, ...]],
) -> tuple[str, ...]:
    expanded: list[str] = []
    for target in targets:
        if "::" in target:
            expanded.append(target)
            continue
        rel_path = target[len("tests/") :] if target.startswith("tests/") else target
        expanded.extend(inventory[rel_path])
    return tuple(expanded)


def select_ci_shard_targets(
    *,
    category: str,
    shard_index: int,
    shard_total: int,
    repo_root: Path | None = None,
) -> tuple[str, ...]:
    if category not in CI_CATEGORY_SHARD_COUNTS:
        raise ValueError(f"unknown CI pytest category {category!r}")
    expected_total = CI_CATEGORY_SHARD_COUNTS[category]
    if shard_total != expected_total:
        raise ValueError(f"shard_total for {category!r} must equal {expected_total}")
    if shard_index < 1 or shard_index > shard_total:
        raise ValueError("shard_index must be within shard_total")
    planned_shards = plan_category_ci_shards(category=category, repo_root=repo_root)
    return planned_shards[shard_index - 1]


def write_ci_shard_targets_file(
    *,
    target_file: Path,
    category: str,
    shard_index: int,
    shard_total: int,
    repo_root: Path | None = None,
) -> tuple[str, ...]:
    targets = select_ci_shard_targets(
        category=category,
        shard_index=shard_index,
        shard_total=shard_total,
        repo_root=repo_root,
    )
    target_file.write_text("\n".join(targets) + "\n", encoding="utf-8")
    return targets
