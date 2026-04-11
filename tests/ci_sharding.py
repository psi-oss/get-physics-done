from __future__ import annotations

import os
import subprocess
import warnings
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from gpd.adapters.runtime_catalog import iter_runtime_descriptors

CI_CATEGORY_SHARD_COUNTS = {
    "root": 9,
    "adapters": 2,
    "hooks": 2,
    "mcp": 1,
    "core": 5,
}

CI_PYTEST_JOB_TIMEOUT_MINUTES = 30
CI_SMOKE_JOB_TIMEOUT_MINUTES = 3
CI_FAST_PRIORITY_TIMEOUT_MINUTES = 3
CI_SMOKE_TEST_TARGETS = (
    "tests/test_release_consistency.py",
    "tests/test_ci_suite_commands.py",
    "tests/test_repo_hygiene.py",
    "tests/test_schema_registry_ownership_note.py",
    "tests/test_runtime_abstraction_boundaries.py::test_runtime_specific_terms_are_confined_to_explicit_boundary_files",
    "tests/adapters/test_runtime_catalog.py::test_runtime_catalog_explicit_priority_order",
    "tests/adapters/test_runtime_catalog.py::test_runtime_descriptor_resolves_from_adapter_module",
    "tests/adapters/test_runtime_catalog.py::test_runtime_catalog_loader_validates_schema_json",
    "tests/core/test_contract_validation_fast_regressions.py",
    "tests/core/test_contract_schema_prompt_parity.py::test_plan_contract_schema_surfaces_canonical_research_contract_fields",
)
CI_TOTAL_SHARD_COUNT_TARGET = 19
CI_MAX_SHARD_COUNT_TARGET = 20

CI_FAST_PRIORITY_TEST_TARGETS = CI_SMOKE_TEST_TARGETS
CI_HOTSPOT_SPLIT_COVERAGE_MIN_TOP_FILES = 12
CI_SHARD_TARGET_RESOLVER_STEP_NAME = "Resolve pytest shard targets"
CI_PYTEST_SHARD_STEP_NAME = "Run pytest shard"
CI_SMOKE_PYTEST_STEP_NAME = "Run release/package smoke tests"
CI_RUNTIME_CATALOG_SCHEMA_STEP_NAME = "Validate runtime catalog schema"
CI_RUNTIME_CATALOG_SCHEMA_COMMAND = "uv run python scripts/validate_runtime_catalog_schema.py"
CI_PYTEST_SHARD_COMMAND_TOKENS = (
    "uv",
    "run",
    "pytest",
    "-q",
    "--durations=20",
    "--durations-min=0",
)


def ci_smoke_pytest_command() -> str:
    return " ".join(("uv", "run", "pytest", "-q", *CI_SMOKE_TEST_TARGETS))

_CI_HOT_TEST_FILE_SPLITS_BASE = {
    "test_runtime_cli.py": 10,
    "test_cli_integration.py": 4,
    "test_registry.py": 4,
    "test_cli_commands.py": 2,
    "test_install_utils_edge.py": 2,
    "test_install_edge_cases.py": 2,
    "test_update_workflow.py": 4,
    "adapters/test_runtime_projected_prompt_parity.py": 2,
    "hooks/test_runtime_detect.py": 2,
    "hooks/test_statusline.py": 2,
    "core/test_cli.py": 3,
    "core/test_contract_validation.py": 3,
    "core/test_frontmatter.py": 3,
    "core/test_context.py": 2,
    "core/test_health.py": 2,
    "core/test_state.py": 2,
    "core/test_prompt_wiring.py": 2,
    "mcp/test_servers.py": 2,
    "mcp/test_verification_contract_server_regressions.py": 2,
    "core/test_verification_contract_evidence.py": 2,
}


@cache
def _runtime_adapter_test_modules() -> tuple[str, ...]:
    try:
        return tuple(descriptor.adapter_module for descriptor in iter_runtime_descriptors())
    except FileNotFoundError:
        warnings.warn("runtime catalog is unavailable; skipping runtime adapter hotspots", stacklevel=2)
        return ()
    except PermissionError:
        warnings.warn("runtime catalog cannot be read; skipping runtime adapter hotspots", stacklevel=2)
        return ()


@cache
def _runtime_adapter_test_file_splits() -> dict[str, int]:
    return {f"adapters/test_{module}.py": 2 for module in _runtime_adapter_test_modules()}


class _LazyHotTestFileSplits(Mapping[str, int]):
    def __init__(self) -> None:
        self._cache: dict[str, int] | None = None

    def _resolved(self) -> dict[str, int]:
        if self._cache is None:
            merged = dict(_CI_HOT_TEST_FILE_SPLITS_BASE)
            merged.update(_runtime_adapter_test_file_splits())
            self._cache = merged
        return self._cache

    def __getitem__(self, key: str) -> int:
        return self._resolved()[key]

    def __iter__(self):
        return iter(self._resolved())

    def __len__(self) -> int:
        return len(self._resolved())

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self._resolved()!r})"


# Observed GitHub Actions timings on 2026-04-07 showed that these files are the
# real bottlenecks inside their category. Split them inside the file so the
# category-local planners can spread the slow work rather than pinning one
# thematic shard to a single expensive module.
CI_HOT_TEST_FILE_SPLITS: Mapping[str, int] = _LazyHotTestFileSplits()

CI_HOT_TEST_FILE_WEIGHT_MULTIPLIERS = {
    "test_runtime_cli.py": 6.0,
    "test_cli_integration.py": 3.0,
    "test_registry.py": 2.0,
    "test_cli_commands.py": 1.5,
    "test_install_utils_edge.py": 1.5,
    "test_update_workflow.py": 2.0,
    "core/test_cli.py": 1.5,
    "core/test_contract_validation.py": 1.4,
    "hooks/test_runtime_detect.py": 1.5,
    "hooks/test_statusline.py": 1.5,
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


def all_test_relpaths(*, tests_root: Path) -> tuple[str, ...]:
    return tuple(path.relative_to(tests_root).as_posix() for path in sorted(tests_root.rglob("test_*.py")))


def _normalized_repo_root(repo_root: Path | None) -> Path:
    return (Path.cwd() if repo_root is None else repo_root).resolve()


def _pytest_collect_command(repo_root: Path) -> tuple[str, ...]:
    venv_python = repo_root / ".venv" / "bin" / "python"
    return (str(venv_python), "-m", "pytest") if venv_python.exists() else ("uv", "run", "pytest")


@cache
def _collected_test_inventory_items(
    repo_root: Path,
    pytest_command: tuple[str, ...] | None = None,
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    pytest_command = pytest_command or _pytest_collect_command(repo_root)
    proc = subprocess.run(
        [
            *pytest_command,
            "tests/",
            "--collect-only",
            "-q",
            "-n",
            "0",
        ],
        cwd=repo_root,
        check=True,
        text=True,
        capture_output=True,
        env={**os.environ, "UV_CACHE_DIR": str(repo_root / "tmp" / "uv-cache")},
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


def collected_test_inventory(*, repo_root: Path | None = None) -> dict[str, tuple[str, ...]]:
    normalized_root = _normalized_repo_root(repo_root)
    return dict(_collected_test_inventory_items(normalized_root, _pytest_collect_command(normalized_root)))


def collected_test_counts_by_file(*, repo_root: Path | None = None) -> dict[str, int]:
    return {
        rel_path: len(nodeids)
        for rel_path, nodeids in collected_test_inventory(repo_root=repo_root).items()
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
        if not nodeids:
            continue
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
            inventory = collected_test_inventory(repo_root=repo_root)
        work_units = build_ci_work_units(inventory)
    if category not in CI_CATEGORY_SHARD_COUNTS:
        raise ValueError(f"unknown CI pytest category {category!r}; add it to CI_CATEGORY_SHARD_COUNTS")
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
    inventory: Mapping[str, tuple[str, ...]] | None = None,
) -> tuple[str, ...]:
    if category not in CI_CATEGORY_SHARD_COUNTS:
        raise ValueError(f"unknown CI pytest category {category!r}; add it to CI_CATEGORY_SHARD_COUNTS")
    expected_total = CI_CATEGORY_SHARD_COUNTS[category]
    if shard_total != expected_total:
        raise ValueError(f"shard_total for {category!r} must equal {expected_total}")
    if shard_index < 1 or shard_index > shard_total:
        raise ValueError("shard_index must be within shard_total")
    planned_shards = plan_category_ci_shards(category=category, repo_root=repo_root, inventory=inventory)
    return planned_shards[shard_index - 1]


def write_ci_shard_targets_file(
    *,
    target_file: Path,
    category: str,
    shard_index: int,
    shard_total: int,
    repo_root: Path | None = None,
    inventory: Mapping[str, tuple[str, ...]] | None = None,
) -> tuple[str, ...]:
    targets = select_ci_shard_targets(
        category=category,
        shard_index=shard_index,
        shard_total=shard_total,
        repo_root=repo_root,
        inventory=inventory,
    )
    target_file.write_text("\n".join(targets) + "\n", encoding="utf-8")
    return targets
