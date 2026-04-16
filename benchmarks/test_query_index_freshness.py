"""Freshness benchmark for the phase-summary query/index path.

The benchmark mutates a summary file outside the timed window, then measures
only the read path while recording explicit fresh-read and stale-read counts.
It keeps the workspace copy and mutation setup separate from the hot path.
"""

from __future__ import annotations

import importlib.util
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from time import perf_counter_ns

import pytest

from gpd.core.query import query, query_assumptions, query_deps


def _load_module_from_path(module_name: str, path: Path) -> object:
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {module_name} from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


REPO_ROOT = Path(__file__).resolve().parents[1]
_phase16_helpers = _load_module_from_path(
    "_phase16_projection_oracle_helpers",
    REPO_ROOT / "tests" / "phase16_projection_oracle_helpers.py",
)
copy_fixture_workspace = _phase16_helpers.copy_fixture_workspace

_phase17_helper_path = REPO_ROOT / "benchmarks" / "phase17_benchmark_helpers.py"
if _phase17_helper_path.exists():  # pragma: no cover - helper lands in the full phase-17 tree
    try:
        _phase17_helpers = _load_module_from_path(
            "_phase17_benchmark_helpers",
            _phase17_helper_path,
        )
    except Exception:  # pragma: no cover - optional helper can stay out of the test path
        _summarize_ns_samples = None
    else:
        _summarize_ns_samples = _phase17_helpers.summarize_ns_samples
else:  # pragma: no cover - local fallback until the helper exists
    _summarize_ns_samples = None


QUERY_INDEX_FIXTURE_SLUG = "query-registry-drift"
QUERY_INDEX_FIXTURE_VARIANT = "positive"
QUERY_INDEX_SUMMARY_RELATIVE_PATH = Path("GPD/phases/01-literature-anchors-and-entangled-cft-setup/01-SUMMARY.md")
QUERY_INDEX_BASE_PROVIDES_LINE = "provides: [literature map, benchmark anchors, scope limits]"
QUERY_INDEX_BASE_TOKEN = "benchmark anchors"
QUERY_INDEX_SAMPLE_COUNT = 7
QUERY_INDEX_WARMUP_COUNT = 2


@dataclass(frozen=True, slots=True)
class QueryIndexSurfaceSpec:
    """One read surface that should observe the mutated summary immediately."""

    name: str
    reader: Callable[[Path, str], object]
    fresh_hit: Callable[[object], bool]
    stale_hit: Callable[[object], bool]


@dataclass(frozen=True, slots=True)
class QueryIndexFreshnessMetrics:
    """Latency and freshness counters for one query/index surface."""

    surface: str
    sample_count: int
    fresh_reads: int
    stale_reads: int
    timings_ns: tuple[int, ...]
    median_ns: int
    p95_ns: int

    def as_dict(self) -> dict[str, object]:
        return {
            "surface": self.surface,
            "sample_count": self.sample_count,
            "fresh_reads": self.fresh_reads,
            "stale_reads": self.stale_reads,
            "timings_ns": self.timings_ns,
            "median_ns": self.median_ns,
            "p95_ns": self.p95_ns,
        }


def _summarize_ns(values: list[int]) -> tuple[int, int]:
    if not values:
        raise ValueError("at least one timing sample is required")
    ordered = sorted(values)
    p95_index = min(len(ordered) - 1, max(0, int((len(ordered) * 95 + 99) / 100) - 1))
    return int(median(ordered)), int(ordered[p95_index])


def _summarize_samples(values: list[int]) -> tuple[int, int]:
    if _summarize_ns_samples is not None:  # pragma: no branch - helper exists in the full phase-17 tree
        summary = _summarize_ns_samples(values)
        if isinstance(summary, dict):
            median_ns = summary.get("median_ns", summary.get("median", 0))
            p95_ns = summary.get("p95_ns", summary.get("p95", 0))
            return int(median_ns), int(p95_ns)
        if isinstance(summary, tuple) and len(summary) >= 2:
            return int(summary[0]), int(summary[1])
    return _summarize_ns(values)


def _query_search(workspace_root: Path, token: str) -> object:
    return query(workspace_root, text=token)


def _query_deps(workspace_root: Path, token: str) -> object:
    return query_deps(workspace_root, token)


def _query_assumptions(workspace_root: Path, token: str) -> object:
    return query_assumptions(workspace_root, token)


QUERY_INDEX_SURFACES: tuple[QueryIndexSurfaceSpec, ...] = (
    QueryIndexSurfaceSpec(
        name="query.search",
        reader=_query_search,
        fresh_hit=lambda result: getattr(result, "total", 0) > 0,
        stale_hit=lambda result: getattr(result, "total", 0) > 0,
    ),
    QueryIndexSurfaceSpec(
        name="query.deps",
        reader=_query_deps,
        fresh_hit=lambda result: getattr(result, "provides_by", None) is not None,
        stale_hit=lambda result: getattr(result, "provides_by", None) is not None,
    ),
    QueryIndexSurfaceSpec(
        name="query.assumptions",
        reader=_query_assumptions,
        fresh_hit=lambda result: getattr(result, "total", 0) > 0,
        stale_hit=lambda result: getattr(result, "total", 0) > 0,
    ),
)


def _sample_token(surface_name: str, sample_index: int) -> str:
    surface_token = surface_name.replace(".", " ")
    return f"gpd query freshness {surface_token} {sample_index:02d}"


def _mutated_summary_text(base_text: str, token: str) -> str:
    replacement = f'provides: [literature map, "{token}", scope limits]'
    if base_text.count(QUERY_INDEX_BASE_PROVIDES_LINE) != 1:
        raise AssertionError("expected exactly one query-index provides line in the benchmark fixture")
    mutated_text = base_text.replace(QUERY_INDEX_BASE_PROVIDES_LINE, replacement, 1)
    if token not in mutated_text:
        raise AssertionError("mutated summary did not retain the fresh token")
    return mutated_text


def _run_query_index_surface_benchmark(
    workspace_root: Path,
    surface: QueryIndexSurfaceSpec,
) -> QueryIndexFreshnessMetrics:
    summary_path = workspace_root / QUERY_INDEX_SUMMARY_RELATIVE_PATH
    original_text = summary_path.read_text(encoding="utf-8")

    try:
        for _ in range(QUERY_INDEX_WARMUP_COUNT):
            warmup_result = surface.reader(workspace_root, QUERY_INDEX_BASE_TOKEN)
            assert surface.fresh_hit(warmup_result), f"{surface.name} warmup did not see the baseline token"

        timings_ns: list[int] = []
        fresh_reads = 0
        stale_reads = 0

        for sample_index in range(QUERY_INDEX_SAMPLE_COUNT):
            token = _sample_token(surface.name, sample_index)
            summary_path.write_text(_mutated_summary_text(original_text, token), encoding="utf-8")

            start_ns = perf_counter_ns()
            fresh_result = surface.reader(workspace_root, token)
            timings_ns.append(perf_counter_ns() - start_ns)

            fresh_hit = surface.fresh_hit(fresh_result)
            fresh_reads += int(fresh_hit)
            assert fresh_hit, f"{surface.name} missed the fresh token {token}"

            stale_result = surface.reader(workspace_root, QUERY_INDEX_BASE_TOKEN)
            stale_hit = surface.stale_hit(stale_result)
            stale_reads += int(stale_hit)
            assert not stale_hit, f"{surface.name} observed a stale read after mutating {token}"

        median_ns, p95_ns = _summarize_samples(timings_ns)
        return QueryIndexFreshnessMetrics(
            surface=surface.name,
            sample_count=QUERY_INDEX_SAMPLE_COUNT,
            fresh_reads=fresh_reads,
            stale_reads=stale_reads,
            timings_ns=tuple(timings_ns),
            median_ns=median_ns,
            p95_ns=p95_ns,
        )
    finally:
        summary_path.write_text(original_text, encoding="utf-8")


@pytest.mark.parametrize("surface", QUERY_INDEX_SURFACES, ids=lambda surface: surface.name)
def test_query_index_freshness_benchmark(
    tmp_path: Path,
    surface: QueryIndexSurfaceSpec,
) -> None:
    workspace_root = copy_fixture_workspace(
        tmp_path,
        QUERY_INDEX_FIXTURE_SLUG,
        QUERY_INDEX_FIXTURE_VARIANT,
    )
    metrics = _run_query_index_surface_benchmark(workspace_root, surface)

    assert metrics.surface == surface.name
    assert metrics.sample_count == QUERY_INDEX_SAMPLE_COUNT
    assert metrics.fresh_reads == QUERY_INDEX_SAMPLE_COUNT
    assert metrics.stale_reads == 0
    assert len(metrics.timings_ns) == QUERY_INDEX_SAMPLE_COUNT
    assert all(sample > 0 for sample in metrics.timings_ns)
    assert metrics.median_ns > 0
    assert metrics.p95_ns >= metrics.median_ns
