"""Checkpoint-batch benchmark for the Phase 17 handoff bundle.

The benchmark stays on the checkpoint-bearing subset of the handoff-bundle
fixtures and measures two paths:

* first-generation writes after the generated checkpoint shelf is cleared
* steady-state reruns after the shelf already exists

The repair-round metric is sourced from the handoff-bundle watchdog summary,
not inferred from the benchmark timings.
"""

from __future__ import annotations

import importlib.util
import json
import statistics
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest

try:  # Prefer the shared benchmark helper once it exists.
    from benchmarks import phase17_benchmark_helpers as _shared_helpers  # type: ignore
except ImportError:  # pragma: no cover - the helper is not present yet.
    _shared_helpers = None

from gpd.core.checkpoints import sync_phase_checkpoints

REPO_ROOT = Path(__file__).resolve().parents[1]
_PHASE16_HELPERS_PATH = REPO_ROOT / "tests" / "phase16_projection_oracle_helpers.py"
_PHASE16_SPEC = importlib.util.spec_from_file_location(
    "phase16_projection_oracle_helpers",
    _PHASE16_HELPERS_PATH,
)
if _PHASE16_SPEC is None or _PHASE16_SPEC.loader is None:  # pragma: no cover - import guard
    raise ImportError(f"Unable to load {_PHASE16_HELPERS_PATH}")
_PHASE16_MODULE = importlib.util.module_from_spec(_PHASE16_SPEC)
sys.modules[_PHASE16_SPEC.name] = _PHASE16_MODULE
_PHASE16_SPEC.loader.exec_module(_PHASE16_MODULE)

ProjectionOracleCase = _PHASE16_MODULE.ProjectionOracleCase
copy_case_workspace = _PHASE16_MODULE.copy_case_workspace
phase16_case_registry = _PHASE16_MODULE.phase16_case_registry

WATCHDOG_SUMMARY_PATH = REPO_ROOT / "benchmarks" / "phase17_watchdog_summary.json"
BATCH_ARTIFACT_PATH = REPO_ROOT / "benchmarks" / "phase17_experiment_checkpoints.json"
THRESHOLD_PATH = REPO_ROOT / "benchmarks" / "phase17_thresholds.json"

CHECKPOINT_BATCH_CASE_KEYS: tuple[str, ...] = (
    "completed-phase/positive",
    "plan-only/positive",
    "plan-only/mutation",
    "query-registry-drift/positive",
    "resume-handoff/positive",
    "resume-handoff/mutation",
    "placeholder-conventions/positive",
    "placeholder-conventions/mutation",
)


@dataclass(frozen=True, slots=True)
class BatchAttemptResult:
    """One benchmark sample from a batch pass."""

    attempt: int
    duration_ns: int
    generated: bool
    phase_count: int
    preserved_phase_count: int
    updated_files: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BatchTimingSummary:
    """Timing summary for a benchmark mode."""

    label: str
    warmup_count: int
    attempt_count: int
    attempt_results: tuple[BatchAttemptResult, ...]
    min_ns: int
    median_ns: int
    max_ns: int


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_thresholds() -> dict[str, object]:
    """Load the explicit Phase 17 threshold manifest when present."""

    if THRESHOLD_PATH.exists():
        return _load_json(THRESHOLD_PATH)
    return {}


def load_watchdog_summary() -> dict[str, object]:
    """Load the handoff-bundle watchdog summary."""

    return _load_json(WATCHDOG_SUMMARY_PATH)


def load_batch_artifact() -> dict[str, object]:
    """Load the handoff-bundle batch artifact used as checkpoint corpus."""

    return _load_json(BATCH_ARTIFACT_PATH)


def _default_checkpoint_batch_cases() -> tuple[ProjectionOracleCase, ...]:
    registry = {case.case_key: case for case in phase16_case_registry()}
    return tuple(registry[key] for key in CHECKPOINT_BATCH_CASE_KEYS)


def checkpoint_batch_cases() -> tuple[ProjectionOracleCase, ...]:
    """Return the checkpoint-bearing Phase 16 cases in canonical order."""

    if _shared_helpers is not None:
        shared = getattr(_shared_helpers, "checkpoint_batch_cases", None)
        if callable(shared):
            return shared()
    return _default_checkpoint_batch_cases()


def reset_generated_checkpoint_outputs(workspace_root: Path) -> None:
    """Remove generated checkpoint shelf artifacts from one workspace."""

    checkpoint_dir = workspace_root / "GPD" / "phase-checkpoints"
    index_path = workspace_root / "GPD" / "CHECKPOINTS.md"
    if checkpoint_dir.exists():
        import shutil

        shutil.rmtree(checkpoint_dir)
    if index_path.exists():
        index_path.unlink()


def _default_measure_ns(
    func: Callable[[], object],
    *,
    warmups: int = 1,
    samples: int = 5,
) -> tuple[int, ...]:
    for _ in range(warmups):
        func()

    durations: list[int] = []
    for _ in range(samples):
        started = time.perf_counter_ns()
        func()
        durations.append(time.perf_counter_ns() - started)
    return tuple(durations)


def measure_ns(
    func: Callable[[], object],
    *,
    warmups: int = 1,
    samples: int = 5,
) -> tuple[int, ...]:
    """Measure a callable with warmups and repeated perf-counter samples."""

    if _shared_helpers is not None:
        shared = getattr(_shared_helpers, "measure_ns", None)
        if callable(shared):
            result = shared(func, warmups=warmups, samples=samples)
            sample_durations = getattr(result, "sample_durations_ns", result)
            return tuple(sample_durations)
    return _default_measure_ns(func, warmups=warmups, samples=samples)


def _run_sync_batch(workspace_roots: tuple[Path, ...]) -> BatchAttemptResult:
    generated = False
    phase_count = 0
    preserved_phase_count = 0
    updated_files: list[str] = []
    for workspace_root in workspace_roots:
        result = sync_phase_checkpoints(workspace_root)
        generated = generated or bool(result.generated)
        phase_count += int(result.phase_count)
        preserved_phase_count += int(result.preserved_phase_count)
        updated_files.extend(result.updated_files)
    return BatchAttemptResult(
        attempt=0,
        duration_ns=0,
        generated=generated,
        phase_count=phase_count,
        preserved_phase_count=preserved_phase_count,
        updated_files=tuple(updated_files),
    )


def _timed_batch_pass(
    workspace_roots: tuple[Path, ...],
    *,
    label: str,
    warmups: int,
    samples: int,
    reset_before_each_sample: bool,
) -> BatchTimingSummary:
    sample_results: list[BatchAttemptResult] = []

    if reset_before_each_sample:
        reset_generated_checkpoint_outputs_for_batch(workspace_roots)

    for _ in range(warmups):
        if reset_before_each_sample:
            reset_generated_checkpoint_outputs_for_batch(workspace_roots)
        _run_sync_batch(workspace_roots)

    attempts = iter(range(1, samples + 1))

    def _sample() -> None:
        if reset_before_each_sample:
            reset_generated_checkpoint_outputs_for_batch(workspace_roots)
        attempt = next(attempts)
        batch_result = _run_sync_batch(workspace_roots)
        sample_results.append(
            BatchAttemptResult(
                attempt=attempt,
                duration_ns=0,
                generated=batch_result.generated,
                phase_count=batch_result.phase_count,
                preserved_phase_count=batch_result.preserved_phase_count,
                updated_files=batch_result.updated_files,
            )
        )

    durations = measure_ns(_sample, warmups=0, samples=samples)
    sample_results = [
        BatchAttemptResult(
            attempt=result.attempt,
            duration_ns=duration_ns,
            generated=result.generated,
            phase_count=result.phase_count,
            preserved_phase_count=result.preserved_phase_count,
            updated_files=result.updated_files,
        )
        for result, duration_ns in zip(sample_results, durations, strict=True)
    ]
    return BatchTimingSummary(
        label=label,
        warmup_count=warmups,
        attempt_count=samples,
        attempt_results=tuple(sample_results),
        min_ns=min(durations),
        median_ns=int(statistics.median(durations)),
        max_ns=max(durations),
    )


def reset_generated_checkpoint_outputs_for_batch(workspace_roots: tuple[Path, ...]) -> None:
    """Clear generated checkpoint artifacts for a batch of workspaces."""

    for workspace_root in workspace_roots:
        reset_generated_checkpoint_outputs(workspace_root)


def _batch_workspace_roots(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, ...]:
    run_root = tmp_path_factory.mktemp("phase17-checkpoint-batch")
    return tuple(copy_case_workspace(case, run_root) for case in checkpoint_batch_cases())


def _repair_round_count() -> int:
    summary = load_watchdog_summary()
    repair_rounds = summary.get("repair_rounds")
    if not isinstance(repair_rounds, int):
        raise TypeError("watchdog summary is missing an integer repair_rounds field")
    return repair_rounds


@pytest.fixture(scope="module")
def checkpoint_batch_workspace_roots(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[Path, ...]:
    return _batch_workspace_roots(tmp_path_factory)


def test_checkpoint_batch_registry_uses_the_checkpoint_bearing_subset() -> None:
    cases = checkpoint_batch_cases()
    assert tuple(case.case_key for case in cases) == CHECKPOINT_BATCH_CASE_KEYS
    assert all(case.status == "live" for case in cases)
    assert len(cases) == 8


def test_checkpoint_batch_sources_repair_rounds_from_watchdog_and_batch_artifacts() -> None:
    thresholds = load_thresholds()
    watchdog = load_watchdog_summary()
    batch_artifact = load_batch_artifact()
    threshold_repair_round_count = thresholds.get("thresholds", {}).get("repair_round_count")

    assert _repair_round_count() == 4
    assert watchdog["kind"] == "gpd-stress-test-watchdog-summary"
    assert isinstance(batch_artifact.get("experiments"), dict)
    assert threshold_repair_round_count == 4


def test_checkpoint_batch_first_generation_latency(
    checkpoint_batch_workspace_roots: tuple[Path, ...],
) -> None:
    summary = _timed_batch_pass(
        checkpoint_batch_workspace_roots,
        label="first-generation",
        warmups=1,
        samples=5,
        reset_before_each_sample=True,
    )

    assert summary.attempt_count == 5
    assert summary.warmup_count == 1
    assert summary.min_ns > 0
    assert summary.median_ns >= summary.min_ns
    assert summary.max_ns >= summary.median_ns
    assert all(result.phase_count >= 0 for result in summary.attempt_results)
    assert all(result.updated_files for result in summary.attempt_results)


def test_checkpoint_batch_steady_state_latency(
    checkpoint_batch_workspace_roots: tuple[Path, ...],
) -> None:
    reset_generated_checkpoint_outputs_for_batch(checkpoint_batch_workspace_roots)
    _run_sync_batch(checkpoint_batch_workspace_roots)

    summary = _timed_batch_pass(
        checkpoint_batch_workspace_roots,
        label="steady-state",
        warmups=1,
        samples=5,
        reset_before_each_sample=False,
    )

    assert summary.attempt_count == 5
    assert summary.warmup_count == 1
    assert summary.min_ns > 0
    assert summary.median_ns >= summary.min_ns
    assert summary.max_ns >= summary.median_ns
    assert all(not result.updated_files for result in summary.attempt_results)
