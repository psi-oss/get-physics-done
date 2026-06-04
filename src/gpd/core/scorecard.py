"""Research-quality / dollar-efficiency scorecard.

Records a timeseries of *how good the research output is* (quality) against
*what it cost to produce* (tokens and USD), so the efficiency of a project can
be graphed as it evolves.

Two quality layers, by design:

* **Objective quality** — derived deterministically from existing GPD
  artifacts (verified-result ratio + phase verification-report status mix).
  Cheap, reproducible, and computable with no model call, so the auto-capture
  path can record it.
* **Judge quality** — an optional LLM-judge score (rigor / novelty /
  significance) layered on at skill-invocation time via :func:`annotate_latest`.
  It is gated on artifact change, never recomputed on a blind timer.

Cost comes from the measured machine-local usage ledger (``gpd cost``); it is
``unavailable`` when the runtime emits no telemetry, and the scorecard degrades
gracefully rather than inventing numbers.

The headline ``quality`` is the judge score when present, else the objective
score. Efficiency is reported in both requested units — quality-per-USD
(headline) and quality-per-1k-tokens (always available when tokens are).
"""

from __future__ import annotations

import json
import secrets
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from gpd.core.constants import (
    SCORECARD_DEFAULT_TOKEN_INTERVAL,
    STANDALONE_VERIFICATION,
    VERIFICATION_SUFFIX,
    ProjectLayout,
)
from gpd.core.costs import list_usage_records
from gpd.core.registry_frontmatter import _parse_frontmatter
from gpd.core.results import _has_verification_evidence
from gpd.core.root_resolution import resolve_project_root
from gpd.core.state import load_state_json_readonly
from gpd.core.utils import atomic_write, file_lock, safe_read_file

__all__ = [
    "QUALITY_RUBRIC_VERSION",
    "CostWindow",
    "QualityBreakdown",
    "ScorecardSnapshot",
    "ScorecardTrend",
    "annotate_latest",
    "append_snapshot",
    "build_snapshot",
    "compute_objective_quality",
    "load_snapshots",
    "maybe_autocapture",
    "read_cost_window",
    "render_trend_text",
    "snapshots_to_csv",
]

SCORECARD_SCHEMA_VERSION = 1
"""Schema version stamped on every snapshot for forward-compatible reads."""

QUALITY_RUBRIC_VERSION = "obj-1"
"""Version tag for the objective-quality formula. Bump when weights/inputs
change so trend comparisons across rubric revisions stay interpretable."""

# Maps a phase verification-report status to a quality contribution in [0, 1].
_VERIFICATION_STATUS_SCORE: dict[str, float] = {
    "passed": 1.0,
    "expert_needed": 0.5,
    "gaps_found": 0.4,
    "human_needed": 0.3,
}

# Blend weights for objective quality. Reallocated when a component is absent.
_WEIGHT_VERIFIED_RATIO = 0.5
_WEIGHT_VERIFICATION_STATUS = 0.5


class QualityBreakdown(BaseModel):
    """Deterministic objective-quality components for one project snapshot."""

    model_config = ConfigDict(frozen=True)

    rubric_version: str = QUALITY_RUBRIC_VERSION
    results_total: int = 0
    results_verified: int = 0
    verified_ratio: float | None = None
    verification_reports_total: int = 0
    verification_status_counts: dict[str, int] = Field(default_factory=dict)
    verification_score: float | None = None
    objective_quality: float | None = None
    signal: str = "insufficient"  # "ok" | "insufficient"


class CostWindow(BaseModel):
    """Rolled-up usage/cost for a project (optionally a recent window)."""

    model_config = ConfigDict(frozen=True)

    record_count: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float | None = None
    cost_status: str = "unavailable"  # "measured" | "estimated" | "unavailable"


class ScorecardSnapshot(BaseModel):
    """One point in the quality/efficiency timeseries."""

    model_config = ConfigDict(frozen=True)

    schema_version: int = SCORECARD_SCHEMA_VERSION
    snapshot_id: str
    recorded_at: str
    trigger: str = "manual"  # "manual" | "auto"
    commit: str | None = None
    milestone: str | None = None
    phase: str | None = None

    # Quality layers.
    objective_quality: float | None = None
    judge_quality: float | None = None
    judge_status: str = "absent"  # "absent" | "stale" | "fresh"
    judge_rubric_version: str | None = None
    quality: float | None = None  # headline: judge if present else objective
    quality_breakdown: QualityBreakdown | None = None

    # Cost.
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float | None = None
    cost_status: str = "unavailable"

    # Efficiency (both requested units; None when the denominator is missing).
    efficiency_per_usd: float | None = None
    efficiency_per_1k_tokens: float | None = None


class ScorecardTrend(BaseModel):
    """Loaded timeseries plus convenience deltas for rendering."""

    model_config = ConfigDict(frozen=True)

    project_root: str | None = None
    snapshots: list[ScorecardSnapshot] = Field(default_factory=list)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _new_id() -> str:
    return f"sc-{int(datetime.now(UTC).timestamp() * 1000)}-{secrets.token_hex(3)}"


def _round(value: float | None, digits: int = 4) -> float | None:
    return None if value is None else round(value, digits)


# ── Quality ────────────────────────────────────────────────────────────────


def _iter_verification_reports(layout: ProjectLayout) -> list[Path]:
    """Return every phase verification report file under the project."""
    phases_dir = layout.phases_dir
    if not phases_dir.exists():
        return []
    reports: list[Path] = []
    for path in sorted(phases_dir.rglob("*.md")):
        name = path.name
        if name == STANDALONE_VERIFICATION or name.endswith(VERIFICATION_SUFFIX):
            reports.append(path)
    return reports


def _verification_status(path: Path) -> str | None:
    content = safe_read_file(path)
    if content is None:
        return None
    try:
        meta, _body = _parse_frontmatter(content)
    except ValueError:
        return None
    status = meta.get("status")
    if isinstance(status, str) and status.strip():
        return status.strip()
    return None


def compute_objective_quality(
    cwd: Path,
    *,
    project_root: Path | None = None,
) -> QualityBreakdown:
    """Derive a deterministic objective-quality score from GPD artifacts.

    Blends the verified-result ratio (from the results registry) with the mean
    verification-report status score (from phase ``*-VERIFICATION.md`` files).
    A missing component reallocates its weight to the present one; when neither
    is present the score is ``None`` and ``signal`` is ``"insufficient"``.
    """
    root = project_root or resolve_project_root(cwd) or cwd
    layout = ProjectLayout(root)

    # Verified-result ratio.
    state = load_state_json_readonly(root) or {}
    raw_results = state.get("intermediate_results")
    results = [r for r in raw_results if isinstance(r, dict)] if isinstance(raw_results, list) else []
    results_total = len(results)
    results_verified = sum(1 for r in results if _has_verification_evidence(r))
    verified_ratio = (results_verified / results_total) if results_total else None

    # Verification-report status mix.
    status_counts: dict[str, int] = {}
    status_scores: list[float] = []
    for report in _iter_verification_reports(layout):
        status = _verification_status(report)
        if status is None:
            continue
        status_counts[status] = status_counts.get(status, 0) + 1
        status_scores.append(_VERIFICATION_STATUS_SCORE.get(status, 0.4))
    verification_total = sum(status_counts.values())
    verification_score = (sum(status_scores) / len(status_scores)) if status_scores else None

    # Weighted blend with reallocation for absent components.
    components: list[tuple[float, float]] = []
    if verified_ratio is not None:
        components.append((_WEIGHT_VERIFIED_RATIO, verified_ratio))
    if verification_score is not None:
        components.append((_WEIGHT_VERIFICATION_STATUS, verification_score))

    if components:
        weight_sum = sum(w for w, _ in components)
        objective = sum(w * v for w, v in components) / weight_sum
        signal = "ok"
    else:
        objective = None
        signal = "insufficient"

    return QualityBreakdown(
        results_total=results_total,
        results_verified=results_verified,
        verified_ratio=_round(verified_ratio),
        verification_reports_total=verification_total,
        verification_status_counts=status_counts,
        verification_score=_round(verification_score),
        objective_quality=_round(objective),
        signal=signal,
    )


# ── Cost ─────────────────────────────────────────────────────────────────


def read_cost_window(
    cwd: Path,
    *,
    project_root: Path | None = None,
    data_root: Path | None = None,
) -> CostWindow:
    """Roll up measured usage/cost for the project from the usage ledger."""
    root = project_root or resolve_project_root(cwd) or cwd
    records = list_usage_records(data_root, project_root=root)
    if not records:
        return CostWindow()

    input_tokens = sum(int(r.input_tokens or 0) for r in records)
    output_tokens = sum(int(r.output_tokens or 0) for r in records)
    total_tokens = sum(int(r.total_tokens or 0) for r in records)
    if total_tokens == 0 and (input_tokens or output_tokens):
        total_tokens = input_tokens + output_tokens

    measured = [r.cost_usd for r in records if r.cost_status == "measured" and r.cost_usd is not None]
    estimated = [r.cost_usd for r in records if r.cost_status == "estimated" and r.cost_usd is not None]
    if measured or estimated:
        cost_usd = round(sum(measured) + sum(estimated), 6)
        cost_status = "measured" if measured and not estimated else "estimated"
    else:
        cost_usd = None
        cost_status = "unavailable"

    return CostWindow(
        record_count=len(records),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        cost_usd=cost_usd,
        cost_status=cost_status,
    )


# ── Efficiency ─────────────────────────────────────────────────────────────


def _efficiency(quality: float | None, cost: CostWindow) -> tuple[float | None, float | None]:
    """Return (quality-per-USD, quality-per-1k-tokens)."""
    if quality is None:
        return None, None
    per_usd = (quality / cost.cost_usd) if cost.cost_usd else None
    per_1k = (quality / (cost.total_tokens / 1000.0)) if cost.total_tokens else None
    return _round(per_usd, 6), _round(per_1k, 6)


# ── Snapshot assembly ────────────────────────────────────────────────────


def _git_short_sha(root: Path) -> str | None:
    from gpd.core.git_ops import _exec_git

    try:
        rc, sha, _ = _exec_git(root, ["rev-parse", "--short", "HEAD"])
    except Exception:
        return None
    sha = (sha or "").strip()
    return sha if rc == 0 and sha else None


def _current_phase(project_root: Path) -> str | None:
    state = load_state_json_readonly(project_root) or {}
    position = state.get("position") if isinstance(state.get("position"), dict) else {}
    phase = position.get("current_phase") if isinstance(position, dict) else None
    return str(phase) if phase is not None else None


def build_snapshot(
    cwd: Path,
    *,
    project_root: Path | None = None,
    trigger: str = "manual",
    include_judge: bool = True,
    data_root: Path | None = None,
) -> ScorecardSnapshot:
    """Assemble a snapshot from objective quality + cost (no judge call here).

    ``include_judge`` only sets ``judge_status`` to ``"stale"`` (signalling that
    a fresh judge pass is wanted); the actual judge score is written later by
    :func:`annotate_latest`. With ``include_judge=False`` the snapshot is final.
    """
    root = project_root or resolve_project_root(cwd) or cwd
    breakdown = compute_objective_quality(cwd, project_root=root)
    cost = read_cost_window(cwd, project_root=root, data_root=data_root)

    quality = breakdown.objective_quality
    per_usd, per_1k = _efficiency(quality, cost)

    return ScorecardSnapshot(
        snapshot_id=_new_id(),
        recorded_at=_now_iso(),
        trigger=trigger,
        commit=_git_short_sha(root),
        milestone=None,
        phase=_current_phase(root),
        objective_quality=breakdown.objective_quality,
        judge_quality=None,
        judge_status="stale" if include_judge else "absent",
        judge_rubric_version=None,
        quality=quality,
        quality_breakdown=breakdown,
        input_tokens=cost.input_tokens,
        output_tokens=cost.output_tokens,
        total_tokens=cost.total_tokens,
        cost_usd=cost.cost_usd,
        cost_status=cost.cost_status,
        efficiency_per_usd=per_usd,
        efficiency_per_1k_tokens=per_1k,
    )


def _with_judge(
    snapshot: ScorecardSnapshot,
    *,
    judge_quality: float,
    rubric_version: str,
) -> ScorecardSnapshot:
    """Return a copy of ``snapshot`` with the judge layer applied as headline."""
    quality = judge_quality
    cost = CostWindow(
        input_tokens=snapshot.input_tokens,
        output_tokens=snapshot.output_tokens,
        total_tokens=snapshot.total_tokens,
        cost_usd=snapshot.cost_usd,
        cost_status=snapshot.cost_status,
    )
    per_usd, per_1k = _efficiency(quality, cost)
    return snapshot.model_copy(
        update={
            "judge_quality": _round(judge_quality),
            "judge_status": "fresh",
            "judge_rubric_version": rubric_version,
            "quality": _round(quality),
            "efficiency_per_usd": per_usd,
            "efficiency_per_1k_tokens": per_1k,
        }
    )


# ── Ledger I/O ───────────────────────────────────────────────────────────


def load_snapshots(cwd: Path, *, project_root: Path | None = None) -> list[ScorecardSnapshot]:
    """Load the scorecard timeseries oldest-first; tolerate malformed lines."""
    root = project_root or resolve_project_root(cwd) or cwd
    content = safe_read_file(ProjectLayout(root).scorecard_ledger)
    if content is None:
        return []
    snapshots: list[ScorecardSnapshot] = []
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            snapshots.append(ScorecardSnapshot.model_validate_json(stripped))
        except ValueError:
            continue
    return snapshots


def append_snapshot(
    snapshot: ScorecardSnapshot,
    cwd: Path,
    *,
    project_root: Path | None = None,
) -> ScorecardSnapshot:
    """Append one snapshot to the project-local JSONL timeseries."""
    root = project_root or resolve_project_root(cwd) or cwd
    ledger = ProjectLayout(root).scorecard_ledger
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with file_lock(ledger):
        existing = load_snapshots(root, project_root=root)
        lines = [s.model_dump_json() for s in existing]
        lines.append(snapshot.model_dump_json())
        atomic_write(ledger, "\n".join(lines) + "\n")
    return snapshot


def annotate_latest(
    cwd: Path,
    *,
    judge_quality: float,
    rubric_version: str,
    project_root: Path | None = None,
) -> ScorecardSnapshot | None:
    """Apply a judge-quality score to the most recent snapshot in place.

    Returns the updated snapshot, or ``None`` when the ledger is empty.
    """
    root = project_root or resolve_project_root(cwd) or cwd
    ledger = ProjectLayout(root).scorecard_ledger
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with file_lock(ledger):
        existing = load_snapshots(root, project_root=root)
        if not existing:
            return None
        existing[-1] = _with_judge(
            existing[-1],
            judge_quality=judge_quality,
            rubric_version=rubric_version,
        )
        lines = [s.model_dump_json() for s in existing]
        atomic_write(ledger, "\n".join(lines) + "\n")
        return existing[-1]


# ── Auto-capture ─────────────────────────────────────────────────────────


def _read_autocapture_marker(layout: ProjectLayout) -> int:
    """Return the cumulative token count at the last auto-capture, or 0."""
    content = safe_read_file(layout.scorecard_autocapture_marker)
    if content is None:
        return 0
    try:
        payload = json.loads(content)
    except (ValueError, TypeError):
        return 0
    value = payload.get("captured_at_total_tokens") if isinstance(payload, dict) else None
    return int(value) if isinstance(value, (int, float)) else 0


def _write_autocapture_marker(layout: ProjectLayout, *, total_tokens: int, snapshot_id: str) -> None:
    marker = layout.scorecard_autocapture_marker
    marker.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(
        marker,
        json.dumps(
            {
                "captured_at_total_tokens": total_tokens,
                "captured_at": _now_iso(),
                "snapshot_id": snapshot_id,
            }
        ),
    )


def maybe_autocapture(
    cwd: Path,
    *,
    project_root: Path | None = None,
    interval: int = SCORECARD_DEFAULT_TOKEN_INTERVAL,
    data_root: Path | None = None,
) -> ScorecardSnapshot | None:
    """Append an objective-only snapshot when cumulative tokens cross an interval.

    Designed to be called from the notify hook on each usage event. It records
    an ``auto``-triggered point (objective quality + cost, no LLM judge — a hook
    has no model turn) once cumulative project tokens advance by ``interval``
    since the last auto-capture. Returns the snapshot when one is recorded, else
    ``None``. It never raises: any failure is swallowed so it cannot break the
    caller.
    """
    try:
        root = project_root or resolve_project_root(cwd) or cwd
        layout = ProjectLayout(root)
        # Only auto-capture for an initialized project with state to score.
        if not layout.gpd.is_dir() or not layout.state_json.exists():
            return None
        if interval <= 0:
            return None

        cost = read_cost_window(root, project_root=root, data_root=data_root)
        current = cost.total_tokens
        if current <= 0:
            return None  # no measured token signal yet

        marker = layout.scorecard_autocapture_marker
        marker.parent.mkdir(parents=True, exist_ok=True)
        with file_lock(marker):
            last = _read_autocapture_marker(layout)
            if current - last < interval:
                return None
            snapshot = build_snapshot(
                root,
                project_root=root,
                trigger="auto",
                include_judge=False,
                data_root=data_root,
            )
            append_snapshot(snapshot, root, project_root=root)
            _write_autocapture_marker(layout, total_tokens=current, snapshot_id=snapshot.snapshot_id)
            return snapshot
    except Exception:
        return None


# ── Rendering ──────────────────────────────────────────────────────────────

_SPARK_TICKS = "▁▂▃▄▅▆▇█"


def _sparkline(values: list[float | None]) -> str:
    present = [v for v in values if v is not None]
    if not present:
        return ""
    lo, hi = min(present), max(present)
    span = hi - lo
    out: list[str] = []
    for v in values:
        if v is None:
            out.append(" ")
            continue
        idx = 0 if span == 0 else round((v - lo) / span * (len(_SPARK_TICKS) - 1))
        out.append(_SPARK_TICKS[idx])
    return "".join(out)


def _fmt_q(value: float | None) -> str:
    return "—" if value is None else f"{value:.3f}"


def _fmt_usd(value: float | None) -> str:
    return "—" if value is None else f"${value:,.4f}"


def render_trend_text(snapshots: list[ScorecardSnapshot]) -> str:
    """Render an ASCII trend (sparklines + per-point table) for the terminal."""
    if not snapshots:
        return "No scorecard snapshots recorded yet. Run a snapshot to start the timeseries."

    quality_series = [s.quality for s in snapshots]
    eff_usd_series = [s.efficiency_per_usd for s in snapshots]

    lines: list[str] = []
    lines.append("Research Scorecard — quality & dollar efficiency over time")
    lines.append("")
    lines.append(f"  Quality        {_sparkline(quality_series)}")
    lines.append(f"  Quality/USD    {_sparkline(eff_usd_series)}")
    lines.append("")
    header = f"  {'when':<20} {'phase':<7} {'qual':>6} {'judge':>6} {'tokens':>10} {'cost':>11} {'q/$':>9} {'q/1k':>8}"
    lines.append(header)
    lines.append("  " + "-" * (len(header) - 2))
    for s in snapshots:
        when = s.recorded_at.replace("T", " ").rstrip("Z")[:19]
        lines.append(
            f"  {when:<20} {(s.phase or '—'):<7} "
            f"{_fmt_q(s.objective_quality):>6} {_fmt_q(s.judge_quality):>6} "
            f"{s.total_tokens:>10,} {_fmt_usd(s.cost_usd):>11} "
            f"{_fmt_q(s.efficiency_per_usd):>9} {_fmt_q(s.efficiency_per_1k_tokens):>8}"
        )

    latest = snapshots[-1]
    lines.append("")
    lines.append(
        f"  Latest: quality={_fmt_q(latest.quality)} "
        f"(objective={_fmt_q(latest.objective_quality)}, judge={_fmt_q(latest.judge_quality)}/{latest.judge_status}) "
        f"cost={_fmt_usd(latest.cost_usd)} [{latest.cost_status}]"
    )
    if latest.cost_status == "unavailable":
        lines.append(
            "  Note: no usage telemetry for this project yet, so dollar/token efficiency is unavailable. "
            "Quality is still tracked."
        )
    return "\n".join(lines)


def snapshots_to_csv(snapshots: list[ScorecardSnapshot]) -> str:
    """Serialize the timeseries to CSV for external graphing."""
    columns = [
        "recorded_at",
        "trigger",
        "commit",
        "milestone",
        "phase",
        "objective_quality",
        "judge_quality",
        "judge_status",
        "quality",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "cost_usd",
        "cost_status",
        "efficiency_per_usd",
        "efficiency_per_1k_tokens",
    ]
    rows = [",".join(columns)]
    for s in snapshots:
        data = s.model_dump(mode="json")
        rows.append(",".join("" if data.get(c) is None else str(data.get(c)) for c in columns))
    return "\n".join(rows) + "\n"
