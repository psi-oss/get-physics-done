"""Shared helpers for the Phase 17 benchmark spine.

The helper stays intentionally thin. It reuses the Phase 16 handoff-bundle
registry and workspace-copy helpers, exposes an explicit pilot/full registry,
loads the checked-in threshold schema, and provides ``perf_counter_ns`` based
timing utilities for the explicit benchmark modules.
"""

from __future__ import annotations

import json
import math
import statistics
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from types import MappingProxyType
from typing import TypeVar

from tests.phase16_projection_oracle_helpers import (
    PHASE16_EXPECTED_CASE_KEYS,
    ProjectionOracleCase,
    build_case_record,
    copy_case_workspace,
    copy_fixture_workspace,
    get_projection_oracle_case,
    load_fixture_metadata,
    phase16_case_keys,
    phase16_case_registry,
    phase16_cases,
)  # noqa: F401

REPO_ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_ROOT = Path(__file__).resolve().parent
PHASE17_THRESHOLDS_PATH = BENCHMARK_ROOT / "phase17_thresholds.json"
WATCHDOG_SUMMARY_PATH = BENCHMARK_ROOT / "phase17_watchdog_summary.json"
EXPERIMENT_CHECKPOINTS_PATH = BENCHMARK_ROOT / "phase17_experiment_checkpoints.json"

PHASE17_DEFAULT_MODE = "pilot"
PHASE17_PILOT_CASE_KEYS: tuple[str, ...] = (
    "completed-phase/positive",
    "empty-phase/mutation",
    "query-registry-drift/positive",
    "summary-missing-return/mutation",
    "resume-recent-noise/mutation",
    "placeholder-conventions/mutation",
    "bridge-vs-cli/mutation",
)
PHASE17_FULL_CASE_KEYS: tuple[str, ...] = PHASE16_EXPECTED_CASE_KEYS
PHASE17_CHECKPOINT_CASE_KEYS: tuple[str, ...] = PHASE17_FULL_CASE_KEYS
PHASE17_REQUIRED_THRESHOLD_KEYS: tuple[str, ...] = (
    "p95_latency_ms",
    "index_freshness_stale_reads",
    "resume_recent_noise_count",
    "repair_round_count",
)
PHASE17_REQUIRED_REGISTRY_MODES: tuple[str, ...] = (
    "pilot",
    "full",
    "checkpoint",
)

T = TypeVar("T")
Phase17CaseRef = ProjectionOracleCase | str


@dataclass(frozen=True, slots=True)
class Phase17ThresholdSchema:
    """Checked-in benchmark threshold schema."""

    schema_version: int
    default_mode: str
    registry: Mapping[str, tuple[str, ...]]
    thresholds: Mapping[str, int | float]
    metric_sources: Mapping[str, str]
    timing: Mapping[str, int | str]

    @property
    def pilot_case_keys(self) -> tuple[str, ...]:
        return self.registry["pilot"]

    @property
    def full_case_keys(self) -> tuple[str, ...]:
        return self.registry["full"]

    @property
    def checkpoint_case_keys(self) -> tuple[str, ...]:
        return self.registry["checkpoint"]


@dataclass(frozen=True, slots=True)
class BenchmarkTimingResult:
    """Timing summary produced by :func:`measure_ns`."""

    warmup_runs: int
    sample_runs: int
    sample_durations_ns: tuple[int, ...]
    total_ns: int
    min_ns: int
    median_ns: int
    p95_ns: int
    mean_ns: float

    @property
    def median_ms(self) -> float:
        return ns_to_ms(self.median_ns)

    @property
    def p95_ms(self) -> float:
        return ns_to_ms(self.p95_ns)

    @property
    def mean_ms(self) -> float:
        return ns_to_ms(self.mean_ns)

    def __len__(self) -> int:
        """Return the number of measured samples for tuple-like compatibility."""

        return len(self.sample_durations_ns)

    def __iter__(self) -> Iterator[int]:
        """Iterate over measured sample durations for tuple-like compatibility."""

        return iter(self.sample_durations_ns)

    def __getitem__(self, index: int | slice) -> int | tuple[int, ...]:
        """Index measured sample durations for tuple-like compatibility."""

        return self.sample_durations_ns[index]


def _as_path(path: Path | str) -> Path:
    return path if isinstance(path, Path) else Path(path)


def load_json_document(path: Path | str) -> object:
    """Load a JSON document from disk."""

    return json.loads(_as_path(path).read_text(encoding="utf-8"))


def load_watchdog_summary(path: Path | str | None = None) -> dict[str, object]:
    """Load the checked-in watchdog summary used for repair-round metrics."""

    payload = load_json_document(WATCHDOG_SUMMARY_PATH if path is None else path)
    if not isinstance(payload, dict):
        raise TypeError("watchdog summary must be a JSON object")
    return payload


def load_experiment_checkpoints(path: Path | str | None = None) -> dict[str, object]:
    """Load the checkpoint batch payload used for repair-round derivation."""

    payload = load_json_document(EXPERIMENT_CHECKPOINTS_PATH if path is None else path)
    if not isinstance(payload, dict):
        raise TypeError("experiment checkpoint payload must be a JSON object")
    return payload


def _coerce_case_key(case_key: str) -> str:
    text = case_key.strip()
    if not text:
        raise ValueError("case key cannot be blank")
    return text


def _normalize_case_key(value: Phase17CaseRef, variant: str | None = None) -> tuple[str, str]:
    if isinstance(value, ProjectionOracleCase):
        return value.fixture_slug, value.variant
    if variant is not None:
        return _coerce_case_key(value), _coerce_case_key(variant)
    if "/" in value:
        fixture_slug, variant = value.rsplit("/", 1)
        return _coerce_case_key(fixture_slug), _coerce_case_key(variant)
    return _coerce_case_key(value), "positive"


def resolve_phase17_case(case: Phase17CaseRef, variant: str | None = None) -> ProjectionOracleCase:
    """Resolve a Phase 17 case by object, case key, or slug/variant pair."""

    fixture_slug, resolved_variant = _normalize_case_key(case, variant)
    return get_projection_oracle_case(fixture_slug, resolved_variant)


@cache
def _phase17_registry_keys_by_mode() -> dict[str, tuple[str, ...]]:
    schema = load_phase17_thresholds()
    return {mode: tuple(keys) for mode, keys in schema.registry.items()}


@cache
def phase17_case_keys(mode: str = PHASE17_DEFAULT_MODE) -> tuple[str, ...]:
    """Return the explicit case keys for a benchmark mode."""

    registry = _phase17_registry_keys_by_mode()
    try:
        return registry[mode]
    except KeyError as exc:  # pragma: no cover - defensive helper path
        raise KeyError(f"unknown Phase 17 mode: {mode}") from exc


@cache
def phase17_case_registry(mode: str = PHASE17_DEFAULT_MODE) -> tuple[ProjectionOracleCase, ...]:
    """Return the canonical Phase 17 case registry for a benchmark mode."""

    return tuple(resolve_phase17_case(case_key) for case_key in phase17_case_keys(mode))


def phase17_cases(mode: str = PHASE17_DEFAULT_MODE) -> tuple[ProjectionOracleCase, ...]:
    """Alias for :func:`phase17_case_registry`."""

    return phase17_case_registry(mode)


def select_phase17_cases(*case_refs: Phase17CaseRef, mode: str | None = None) -> tuple[ProjectionOracleCase, ...]:
    """Select an explicit Phase 17 case subset.

    When ``case_refs`` is empty, the helper falls back to the requested mode
    registry. When explicit case references are supplied, the helper preserves
    their order and rejects duplicates. Passing ``mode`` in that form limits the
    explicit selection to the requested registry.
    """

    if not case_refs:
        return phase17_case_registry(PHASE17_DEFAULT_MODE if mode is None else mode)

    resolved = tuple(resolve_phase17_case(case_ref) for case_ref in case_refs)
    seen: set[str] = set()
    duplicate_keys: list[str] = []
    for case in resolved:
        if case.case_key in seen:
            duplicate_keys.append(case.case_key)
            continue
        seen.add(case.case_key)
    if duplicate_keys:
        raise ValueError(f"duplicate Phase 17 case selection: {sorted(set(duplicate_keys))}")

    if mode is not None:
        allowed = set(phase17_case_keys(mode))
        outside = [case.case_key for case in resolved if case.case_key not in allowed]
        if outside:
            raise KeyError(f"cases are not part of Phase 17 mode {mode!r}: {outside}")

    return resolved


@cache
def load_phase17_thresholds(path: Path | str | None = None) -> Phase17ThresholdSchema:
    """Load and validate the checked-in Phase 17 threshold schema."""

    schema_path = PHASE17_THRESHOLDS_PATH if path is None else _as_path(path)
    payload = load_json_document(schema_path)
    if not isinstance(payload, dict):
        raise TypeError("phase 17 threshold schema must be a JSON object")

    schema_version = int(payload.get("schema_version", 0))
    if schema_version != 1:
        raise ValueError("phase 17 threshold schema has unexpected schema_version")

    default_mode = str(payload.get("default_mode", PHASE17_DEFAULT_MODE))
    registry_payload = payload.get("registry")
    thresholds_payload = payload.get("thresholds")
    metric_sources_payload = payload.get("metric_sources")
    timing_payload = payload.get("timing")

    if not isinstance(registry_payload, dict):
        raise TypeError("phase 17 threshold schema missing registry block")
    if not isinstance(thresholds_payload, dict):
        raise TypeError("phase 17 threshold schema missing thresholds block")
    if not isinstance(metric_sources_payload, dict):
        raise TypeError("phase 17 threshold schema missing metric_sources block")
    if not isinstance(timing_payload, dict):
        raise TypeError("phase 17 threshold schema missing timing block")
    if default_mode not in PHASE17_REQUIRED_REGISTRY_MODES:
        raise ValueError("phase 17 threshold schema default_mode is not recognized")

    registry: dict[str, tuple[str, ...]] = {}
    if set(registry_payload) != set(PHASE17_REQUIRED_REGISTRY_MODES):
        raise ValueError("phase 17 threshold registry has unexpected keys")
    for mode in PHASE17_REQUIRED_REGISTRY_MODES:
        value = registry_payload.get(mode)
        if not isinstance(value, list) or not all(isinstance(entry, str) for entry in value):
            raise TypeError(f"phase 17 threshold registry[{mode!r}] must be a list[str]")
        registry[mode] = tuple(value)

    if registry["pilot"] != PHASE17_PILOT_CASE_KEYS:
        raise ValueError("phase 17 pilot registry does not match the curated pilot set")
    if registry["full"] != PHASE17_FULL_CASE_KEYS:
        raise ValueError("phase 17 full registry does not match the Phase 16 registry")
    if registry["checkpoint"] != registry["full"]:
        raise ValueError("phase 17 checkpoint registry must mirror the full registry")

    threshold_keys = tuple(thresholds_payload.keys())
    if tuple(sorted(threshold_keys)) != tuple(sorted(PHASE17_REQUIRED_THRESHOLD_KEYS)):
        raise ValueError("phase 17 threshold keys are incomplete or unexpected")
    thresholds: dict[str, int | float] = {}
    for key in PHASE17_REQUIRED_THRESHOLD_KEYS:
        value = thresholds_payload[key]
        if not isinstance(value, (int, float)):
            raise TypeError(f"phase 17 threshold {key!r} must be numeric")
        thresholds[key] = value

    if set(metric_sources_payload) != set(PHASE17_REQUIRED_THRESHOLD_KEYS):
        raise ValueError("phase 17 metric_sources keys are incomplete or unexpected")
    metric_sources = {str(key): str(metric_sources_payload[key]) for key in PHASE17_REQUIRED_THRESHOLD_KEYS}

    if set(timing_payload) != {"clock", "warmup_runs", "sample_runs"}:
        raise ValueError("phase 17 timing block has unexpected keys")
    timing = {
        "clock": str(timing_payload["clock"]),
        "warmup_runs": int(timing_payload["warmup_runs"]),
        "sample_runs": int(timing_payload["sample_runs"]),
    }

    return Phase17ThresholdSchema(
        schema_version=schema_version,
        default_mode=default_mode,
        registry=MappingProxyType(registry),
        thresholds=MappingProxyType(thresholds),
        metric_sources=MappingProxyType(metric_sources),
        timing=MappingProxyType(timing),
    )


PHASE17_THRESHOLD_SCHEMA = load_phase17_thresholds()
PHASE17_REGISTRY_BY_MODE: Mapping[str, tuple[str, ...]] = PHASE17_THRESHOLD_SCHEMA.registry
PHASE17_PILOT_CASE_REGISTRY = phase17_case_registry("pilot")
PHASE17_FULL_CASE_REGISTRY = phase17_case_registry("full")
PHASE17_CHECKPOINT_CASE_REGISTRY = phase17_case_registry("checkpoint")


def copy_phase17_case_workspace(
    case: Phase17CaseRef,
    tmp_path: Path,
    *,
    suffix: str = "",
    variant: str | None = None,
) -> Path:
    """Copy one benchmark workspace into a temporary location."""

    resolved = resolve_phase17_case(case, variant)
    return copy_case_workspace(resolved, tmp_path, suffix=suffix)


def copy_phase17_fixture_workspace(
    tmp_path: Path,
    fixture_slug: str,
    variant: str = "positive",
    *,
    suffix: str = "",
) -> Path:
    """Copy one benchmark fixture workspace into a temporary location."""

    return copy_fixture_workspace(tmp_path, fixture_slug, variant, suffix=suffix)


def load_phase17_case_metadata(case: Phase17CaseRef, variant: str | None = None) -> dict[str, object]:
    """Load the raw ``fixture.json`` payload for a benchmark case."""

    resolved = resolve_phase17_case(case, variant)
    return load_fixture_metadata(resolved)


def phase17_case_record(case: Phase17CaseRef, variant: str | None = None) -> dict[str, object]:
    """Build a JSON-friendly registry record for a benchmark case."""

    resolved = resolve_phase17_case(case, variant)
    return build_case_record(resolved)


def phase17_case_records(mode: str = PHASE17_DEFAULT_MODE) -> tuple[dict[str, object], ...]:
    """Return JSON-friendly registry records for a benchmark mode."""

    return tuple(phase17_case_record(case) for case in phase17_case_registry(mode))


def ns_to_ms(duration_ns: int | float) -> float:
    """Convert nanoseconds to milliseconds."""

    return float(duration_ns) / 1_000_000.0


def _percentile_ns(samples: Sequence[int], percentile: float = 95.0) -> int:
    if not samples:
        raise ValueError("at least one timing sample is required")
    if percentile < 0 or percentile > 100:
        raise ValueError("percentile must be between 0 and 100")

    ordered = sorted(int(sample) for sample in samples)
    if len(ordered) == 1:
        return ordered[0]

    rank = max(1, math.ceil((percentile / 100.0) * len(ordered)))
    index = min(len(ordered) - 1, rank - 1)
    return ordered[index]


def summarize_ns_samples(samples: Sequence[int], *, warmup_runs: int = 0) -> BenchmarkTimingResult:
    """Summarize a set of raw nanosecond timings."""

    if not samples:
        raise ValueError("at least one timing sample is required")
    raw_samples = tuple(int(sample) for sample in samples)
    ordered = tuple(sorted(int(sample) for sample in samples))
    return BenchmarkTimingResult(
        warmup_runs=warmup_runs,
        sample_runs=len(ordered),
        sample_durations_ns=raw_samples,
        total_ns=sum(ordered),
        min_ns=ordered[0],
        median_ns=int(statistics.median_low(ordered)),
        p95_ns=_percentile_ns(ordered, 95.0),
        mean_ns=float(statistics.fmean(ordered)),
    )


def summarize_ns(samples: Sequence[int] | BenchmarkTimingResult) -> dict[str, int]:
    """Return a compact timing summary for benchmark assertions."""

    summary = samples if isinstance(samples, BenchmarkTimingResult) else summarize_ns_samples(samples)
    return {
        "count": summary.sample_runs,
        "min_ns": summary.min_ns,
        "median_ns": summary.median_ns,
        "p95_ns": summary.p95_ns,
        "max_ns": max(summary.sample_durations_ns),
    }


def measure_ns(
    operation: Callable[[], T],
    *,
    warmup_runs: int | None = None,
    sample_runs: int | None = None,
    warmups: int | None = None,
    samples: int | None = None,
    warmup_rounds: int | None = None,
    sample_rounds: int | None = None,
) -> BenchmarkTimingResult:
    """Measure an operation with warmup plus repeated ``perf_counter_ns`` samples."""

    if warmup_runs is None:
        warmup_runs = 1
        if warmups is not None:
            warmup_runs = warmups
        if warmup_rounds is not None:
            if warmups is not None and warmup_rounds != warmups:
                raise ValueError("warmups and warmup_rounds disagree")
            warmup_runs = warmup_rounds
    elif (warmups is not None and warmups != warmup_runs) or (
        warmup_rounds is not None and warmup_rounds != warmup_runs
    ):
        raise ValueError("warmup_runs aliases disagree")
    if sample_runs is None:
        sample_runs = 7
        if samples is not None:
            sample_runs = samples
        if sample_rounds is not None:
            if samples is not None and sample_rounds != samples:
                raise ValueError("samples and sample_rounds disagree")
            sample_runs = sample_rounds
    elif (samples is not None and samples != sample_runs) or (
        sample_rounds is not None and sample_rounds != sample_runs
    ):
        raise ValueError("sample_runs aliases disagree")

    if warmup_runs < 0:
        raise ValueError("warmup_runs cannot be negative")
    if sample_runs < 1:
        raise ValueError("sample_runs must be at least 1")

    for _ in range(warmup_runs):
        operation()

    samples: list[int] = []
    for _ in range(sample_runs):
        start = time.perf_counter_ns()
        operation()
        samples.append(time.perf_counter_ns() - start)
    return summarize_ns_samples(samples, warmup_runs=warmup_runs)


def measure_case_ns(
    case: Phase17CaseRef,
    operation: Callable[[ProjectionOracleCase], T],
    *,
    warmup_runs: int = 1,
    sample_runs: int = 7,
    variant: str | None = None,
) -> BenchmarkTimingResult:
    """Measure a case-aware operation while keeping the timed region small."""

    resolved = resolve_phase17_case(case, variant)
    return measure_ns(lambda: operation(resolved), warmup_runs=warmup_runs, sample_runs=sample_runs)


def count_recent_project_noise_rows(payload: Mapping[str, object] | Path | str) -> int:
    """Count machine-local recent-project noise rows from a JSON payload."""

    data = load_json_document(payload) if isinstance(payload, (Path, str)) else payload
    if not isinstance(data, Mapping):
        raise TypeError("recent-project payload must be a mapping")
    entries = data.get("entries", [])
    if not isinstance(entries, Sequence) or isinstance(entries, (str, bytes)):
        raise TypeError("recent-project payload missing entries sequence")
    return sum(1 for entry in entries if isinstance(entry, Mapping) and str(entry.get("path", "")).strip())


def derive_repair_round_count(*payloads: Mapping[str, object] | Path | str) -> int:
    """Derive repair rounds from watchdog or batch artifacts.

    The helper prefers the explicit ``repair_rounds`` field. If that is not
    present, it falls back to the batch-level ``attempt_count`` or the length of
    ``attempt_results`` and subtracts the baseline attempt so the first pass does
    not count as a repair round.
    """

    if not payloads:
        raise ValueError("at least one payload is required")

    def _loaded(payload: Mapping[str, object] | Path | str) -> Mapping[str, object]:
        data = load_json_document(payload) if isinstance(payload, (Path, str)) else payload
        if not isinstance(data, Mapping):
            raise TypeError("repair-round payload must be a mapping")
        return data

    loaded_payloads = tuple(_loaded(payload) for payload in payloads)
    for payload in loaded_payloads:
        repair_rounds = payload.get("repair_rounds")
        if isinstance(repair_rounds, (int, float)):
            return int(repair_rounds)

    for payload in loaded_payloads:
        attempt_count = payload.get("attempt_count")
        if isinstance(attempt_count, (int, float)):
            return max(0, int(attempt_count) - 1)

        attempt_results = payload.get("attempt_results")
        if isinstance(attempt_results, Sequence) and not isinstance(attempt_results, (str, bytes)):
            return max(0, len(attempt_results) - 1)

    raise ValueError("unable to derive repair round count from the supplied payloads")


def load_phase17_watchdog_repair_rounds(path: Path | str | None = None) -> int:
    """Load the checked-in watchdog summary and return its repair-round count."""

    return derive_repair_round_count(load_watchdog_summary(path))


def load_phase17_batch_repair_rounds(path: Path | str | None = None) -> int:
    """Load the checkpoint batch payload and return its repair-round count.

    The checked-in batch payload may not expose round counters directly yet, so
    the helper falls back to the watchdog summary when the batch payload is too
    sparse to derive a round count on its own.
    """

    try:
        return derive_repair_round_count(load_experiment_checkpoints(path))
    except ValueError:
        return load_phase17_watchdog_repair_rounds()


def phase17_threshold_value(name: str) -> int | float:
    """Return one threshold value by name."""

    try:
        return PHASE17_THRESHOLD_SCHEMA.thresholds[name]
    except KeyError as exc:  # pragma: no cover - defensive helper path
        raise KeyError(f"unknown Phase 17 threshold: {name}") from exc


def phase17_metric_source(name: str) -> str:
    """Return one threshold source description by name."""

    try:
        return PHASE17_THRESHOLD_SCHEMA.metric_sources[name]
    except KeyError as exc:  # pragma: no cover - defensive helper path
        raise KeyError(f"unknown Phase 17 metric source: {name}") from exc


__all__ = [
    "BENCHMARK_ROOT",
    "EXPERIMENT_CHECKPOINTS_PATH",
    "PHASE17_BATCH_REPAIR_ROUND_COUNT",
    "PHASE17_CHECKPOINT_CASE_KEYS",
    "PHASE17_CHECKPOINT_CASE_REGISTRY",
    "PHASE17_DEFAULT_MODE",
    "PHASE17_FULL_CASE_KEYS",
    "PHASE17_FULL_CASE_REGISTRY",
    "PHASE17_PILOT_CASE_KEYS",
    "PHASE17_PILOT_CASE_REGISTRY",
    "PHASE17_REGISTRY_BY_MODE",
    "PHASE17_REQUIRED_REGISTRY_MODES",
    "PHASE17_REQUIRED_THRESHOLD_KEYS",
    "PHASE17_THRESHOLD_SCHEMA",
    "PHASE17_THRESHOLDS_PATH",
    "Phase17CaseRef",
    "Phase17ThresholdSchema",
    "BenchmarkTimingResult",
    "WATCHDOG_SUMMARY_PATH",
    "count_recent_project_noise_rows",
    "copy_phase17_case_workspace",
    "copy_phase17_fixture_workspace",
    "derive_repair_round_count",
    "load_experiment_checkpoints",
    "load_json_document",
    "load_phase17_batch_repair_rounds",
    "load_phase17_case_metadata",
    "load_phase17_thresholds",
    "load_phase17_watchdog_repair_rounds",
    "load_watchdog_summary",
    "measure_case_ns",
    "measure_ns",
    "ns_to_ms",
    "phase16_case_keys",
    "phase16_case_registry",
    "phase16_cases",
    "phase17_case_keys",
    "phase17_case_record",
    "phase17_case_records",
    "phase17_case_registry",
    "phase17_cases",
    "phase17_metric_source",
    "phase17_threshold_value",
    "resolve_phase17_case",
    "select_phase17_cases",
    "summarize_ns",
    "summarize_ns_samples",
]


PHASE17_BATCH_REPAIR_ROUND_COUNT = load_phase17_batch_repair_rounds()
