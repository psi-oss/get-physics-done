"""Tests for gpd.core.scorecard — research quality / dollar-efficiency timeseries."""

from __future__ import annotations

import json
from pathlib import Path

import gpd.core.scorecard as scorecard_module
from gpd.core.costs import usage_ledger_path
from gpd.core.scorecard import (
    QUALITY_RUBRIC_VERSION,
    annotate_latest,
    append_snapshot,
    build_snapshot,
    compute_objective_quality,
    load_snapshots,
    maybe_autocapture,
    read_cost_window,
    render_trend_text,
    snapshots_to_csv,
)


def _project(tmp_path: Path, *, state: dict | None = None) -> Path:
    project = tmp_path / "project"
    (project / "GPD").mkdir(parents=True, exist_ok=True)
    if state is not None:
        (project / "GPD" / "state.json").write_text(json.dumps(state), encoding="utf-8")
    return project


def _add_verification(project: Path, phase: str, plan: str, status: str) -> None:
    phase_dir = project / "GPD" / "phases" / phase
    phase_dir.mkdir(parents=True, exist_ok=True)
    (phase_dir / f"{plan}-VERIFICATION.md").write_text(f"---\nstatus: {status}\n---\nbody\n", encoding="utf-8")


def _write_usage(data_root: Path, project: Path, records: list[dict]) -> None:
    ledger = usage_ledger_path(data_root)
    ledger.parent.mkdir(parents=True, exist_ok=True)
    proj = project.resolve(strict=False).as_posix()
    lines = []
    for i, r in enumerate(records):
        base = {
            "record_id": f"usage-{i}",
            "recorded_at": f"2026-06-04T10:{i:02d}:00Z",
            "project_root": proj,
        }
        lines.append(json.dumps({**base, **r}))
    ledger.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ── objective quality ────────────────────────────────────────────────────


def test_objective_quality_blends_verified_ratio_and_verification_status(tmp_path: Path) -> None:
    state = {
        "position": {"current_phase": "03"},
        "intermediate_results": [
            {"id": "R1", "verified": True},
            {"id": "R2", "verified": True},
            {"id": "R3", "verified": False},
            {"id": "R4", "verified": False},
        ],
    }
    project = _project(tmp_path, state=state)
    _add_verification(project, "03-deriv", "01", "passed")
    _add_verification(project, "03-deriv", "02", "gaps_found")

    bd = compute_objective_quality(project, project_root=project)

    assert bd.results_total == 4
    assert bd.results_verified == 2
    assert bd.verified_ratio == 0.5
    assert bd.verification_status_counts == {"passed": 1, "gaps_found": 1}
    # mean status score = (1.0 + 0.4) / 2 = 0.7
    assert bd.verification_score == 0.7
    # blend = 0.5*0.5 + 0.5*0.7 = 0.6
    assert bd.objective_quality == 0.6
    assert bd.signal == "ok"
    assert bd.rubric_version == QUALITY_RUBRIC_VERSION


def test_objective_quality_reallocates_weight_when_a_component_is_absent(tmp_path: Path) -> None:
    # Results but no verification reports -> quality equals the verified ratio.
    state = {"intermediate_results": [{"id": "R1", "verified": True}, {"id": "R2", "verified": False}]}
    project = _project(tmp_path, state=state)

    bd = compute_objective_quality(project, project_root=project)

    assert bd.verified_ratio == 0.5
    assert bd.verification_score is None
    assert bd.objective_quality == 0.5
    assert bd.signal == "ok"


def test_objective_quality_insufficient_when_no_signal(tmp_path: Path) -> None:
    project = _project(tmp_path, state={"intermediate_results": []})

    bd = compute_objective_quality(project, project_root=project)

    assert bd.objective_quality is None
    assert bd.signal == "insufficient"


# ── cost window ────────────────────────────────────────────────────────────


def test_read_cost_window_rolls_up_measured_usage(tmp_path: Path) -> None:
    project = _project(tmp_path, state={})
    data_root = tmp_path / "data"
    _write_usage(
        data_root,
        project,
        [
            {
                "input_tokens": 8000,
                "output_tokens": 2000,
                "total_tokens": 10000,
                "cost_usd": 0.12,
                "cost_status": "measured",
            },
            {
                "input_tokens": 40000,
                "output_tokens": 10000,
                "total_tokens": 50000,
                "cost_usd": 0.60,
                "cost_status": "measured",
            },
        ],
    )

    cw = read_cost_window(project, project_root=project, data_root=data_root)

    assert cw.record_count == 2
    assert cw.total_tokens == 60000
    assert cw.input_tokens == 48000
    assert cw.cost_usd == 0.72
    assert cw.cost_status == "measured"


def test_read_cost_window_unavailable_without_records(tmp_path: Path) -> None:
    project = _project(tmp_path, state={})
    data_root = tmp_path / "data"

    cw = read_cost_window(project, project_root=project, data_root=data_root)

    assert cw.record_count == 0
    assert cw.cost_usd is None
    assert cw.cost_status == "unavailable"


# ── snapshot + efficiency ────────────────────────────────────────────────


def test_build_snapshot_computes_both_efficiency_units(tmp_path: Path) -> None:
    state = {"intermediate_results": [{"id": "R1", "verified": True}, {"id": "R2", "verified": True}]}
    project = _project(tmp_path, state=state)
    data_root = tmp_path / "data"
    _write_usage(
        data_root,
        project,
        [
            {
                "input_tokens": 50000,
                "output_tokens": 10000,
                "total_tokens": 60000,
                "cost_usd": 0.72,
                "cost_status": "measured",
            }
        ],
    )

    snap = build_snapshot(project, project_root=project, include_judge=False, data_root=data_root)

    assert snap.objective_quality == 1.0
    assert snap.quality == 1.0
    assert snap.total_tokens == 60000
    # quality / cost = 1.0 / 0.72
    assert snap.efficiency_per_usd == round(1.0 / 0.72, 6)
    # quality / (tokens/1000) = 1.0 / 60
    assert snap.efficiency_per_1k_tokens == round(1.0 / 60.0, 6)
    assert snap.judge_status == "absent"


def test_build_snapshot_marks_judge_stale_when_requested(tmp_path: Path) -> None:
    project = _project(tmp_path, state={"intermediate_results": [{"id": "R1", "verified": True}]})

    snap = build_snapshot(project, project_root=project, include_judge=True)

    assert snap.judge_status == "stale"
    assert snap.judge_quality is None
    assert snap.cost_status == "unavailable"
    assert snap.efficiency_per_usd is None  # no cost -> no dollar efficiency


# ── ledger I/O + annotate ────────────────────────────────────────────────


def test_append_and_load_roundtrip(tmp_path: Path) -> None:
    project = _project(tmp_path, state={"intermediate_results": [{"id": "R1", "verified": True}]})

    first = build_snapshot(project, project_root=project, include_judge=False)
    append_snapshot(first, project, project_root=project)
    second = build_snapshot(project, project_root=project, include_judge=False)
    append_snapshot(second, project, project_root=project)

    loaded = load_snapshots(project, project_root=project)
    assert len(loaded) == 2
    assert [s.snapshot_id for s in loaded] == [first.snapshot_id, second.snapshot_id]


def test_annotate_latest_applies_judge_and_recomputes_efficiency(tmp_path: Path) -> None:
    state = {"intermediate_results": [{"id": "R1", "verified": True}, {"id": "R2", "verified": False}]}
    project = _project(tmp_path, state=state)
    data_root = tmp_path / "data"
    _write_usage(
        data_root,
        project,
        [
            {
                "input_tokens": 5000,
                "output_tokens": 5000,
                "total_tokens": 10000,
                "cost_usd": 0.50,
                "cost_status": "measured",
            }
        ],
    )

    snap = build_snapshot(project, project_root=project, include_judge=True, data_root=data_root)
    append_snapshot(snap, project, project_root=project)
    assert snap.objective_quality == 0.5

    updated = annotate_latest(project, judge_quality=0.9, rubric_version="judge-1", project_root=project)

    assert updated is not None
    assert updated.judge_quality == 0.9
    assert updated.judge_status == "fresh"
    assert updated.judge_rubric_version == "judge-1"
    assert updated.quality == 0.9  # headline switches to judge score
    assert updated.efficiency_per_usd == round(0.9 / 0.50, 6)
    # objective layer is preserved
    assert updated.objective_quality == 0.5
    # persisted
    assert load_snapshots(project, project_root=project)[-1].judge_quality == 0.9


def test_annotate_latest_returns_none_when_empty(tmp_path: Path) -> None:
    project = _project(tmp_path, state={})

    assert annotate_latest(project, judge_quality=0.5, rubric_version="judge-1", project_root=project) is None


# ── rendering ──────────────────────────────────────────────────────────────


def test_render_trend_text_flags_unavailable_cost(tmp_path: Path) -> None:
    project = _project(tmp_path, state={"intermediate_results": [{"id": "R1", "verified": True}]})
    snap = build_snapshot(project, project_root=project, include_judge=False)
    append_snapshot(snap, project, project_root=project)

    text = render_trend_text(load_snapshots(project, project_root=project))

    assert "Research Scorecard" in text
    assert "unavailable" in text


def test_render_trend_text_empty() -> None:
    assert "No scorecard snapshots" in render_trend_text([])


# ── auto-capture ───────────────────────────────────────────────────────────


def _autocap_project(tmp_path: Path) -> Path:
    return _project(tmp_path, state={"intermediate_results": [{"id": "R1", "verified": True}]})


def test_maybe_autocapture_skips_below_threshold(tmp_path: Path) -> None:
    project = _autocap_project(tmp_path)
    data_root = tmp_path / "data"
    _write_usage(data_root, project, [{"total_tokens": 30000, "cost_usd": 0.3, "cost_status": "measured"}])

    result = maybe_autocapture(project, project_root=project, interval=50000, data_root=data_root)

    assert result is None
    assert load_snapshots(project, project_root=project) == []


def test_maybe_autocapture_fires_at_threshold_with_auto_trigger(tmp_path: Path) -> None:
    project = _autocap_project(tmp_path)
    data_root = tmp_path / "data"
    _write_usage(
        data_root,
        project,
        [
            {"total_tokens": 30000, "cost_usd": 0.3, "cost_status": "measured"},
            {"total_tokens": 30000, "cost_usd": 0.3, "cost_status": "measured"},
        ],
    )

    result = maybe_autocapture(project, project_root=project, interval=50000, data_root=data_root)

    assert result is not None
    assert result.trigger == "auto"
    assert result.judge_status == "absent"  # no LLM judge in the hook path
    assert result.total_tokens == 60000
    assert len(load_snapshots(project, project_root=project)) == 1


def test_maybe_autocapture_no_double_capture_without_new_tokens(tmp_path: Path) -> None:
    project = _autocap_project(tmp_path)
    data_root = tmp_path / "data"
    _write_usage(data_root, project, [{"total_tokens": 60000, "cost_usd": 0.6, "cost_status": "measured"}])

    first = maybe_autocapture(project, project_root=project, interval=50000, data_root=data_root)
    second = maybe_autocapture(project, project_root=project, interval=50000, data_root=data_root)

    assert first is not None
    assert second is None  # marker advanced; no new tokens since
    assert len(load_snapshots(project, project_root=project)) == 1


def test_maybe_autocapture_fires_again_after_next_interval(tmp_path: Path) -> None:
    project = _autocap_project(tmp_path)
    data_root = tmp_path / "data"
    _write_usage(data_root, project, [{"total_tokens": 60000, "cost_usd": 0.6, "cost_status": "measured"}])
    assert maybe_autocapture(project, project_root=project, interval=50000, data_root=data_root) is not None

    # Cumulative climbs past the next interval boundary.
    _write_usage(
        data_root,
        project,
        [
            {"total_tokens": 60000, "cost_usd": 0.6, "cost_status": "measured"},
            {"total_tokens": 60000, "cost_usd": 0.6, "cost_status": "measured"},
        ],
    )
    second = maybe_autocapture(project, project_root=project, interval=50000, data_root=data_root)

    assert second is not None
    assert second.total_tokens == 120000
    assert len(load_snapshots(project, project_root=project)) == 2


def test_maybe_autocapture_skips_without_token_signal(tmp_path: Path) -> None:
    project = _autocap_project(tmp_path)
    data_root = tmp_path / "data"  # no usage ledger written

    assert maybe_autocapture(project, project_root=project, interval=50000, data_root=data_root) is None


def test_maybe_autocapture_skips_uninitialized_project(tmp_path: Path) -> None:
    # No GPD/ state.json -> nothing to score.
    bare = tmp_path / "bare"
    (bare / "GPD").mkdir(parents=True)
    data_root = tmp_path / "data"
    _write_usage(data_root, bare, [{"total_tokens": 99999, "cost_usd": 1.0, "cost_status": "measured"}])

    assert maybe_autocapture(bare, project_root=bare, interval=50000, data_root=data_root) is None


def test_maybe_autocapture_swallows_errors(tmp_path: Path, monkeypatch) -> None:
    project = _autocap_project(tmp_path)
    data_root = tmp_path / "data"
    _write_usage(data_root, project, [{"total_tokens": 60000, "cost_usd": 0.6, "cost_status": "measured"}])

    def _boom(*args, **kwargs):
        raise RuntimeError("snapshot build failed")

    monkeypatch.setattr(scorecard_module, "build_snapshot", _boom)

    # Must not raise into the caller (the notify hook).
    assert maybe_autocapture(project, project_root=project, interval=50000, data_root=data_root) is None


def test_snapshots_to_csv_has_header_and_rows(tmp_path: Path) -> None:
    project = _project(tmp_path, state={"intermediate_results": [{"id": "R1", "verified": True}]})
    snap = build_snapshot(project, project_root=project, include_judge=False)
    append_snapshot(snap, project, project_root=project)

    csv = snapshots_to_csv(load_snapshots(project, project_root=project))
    lines = csv.strip().splitlines()

    assert lines[0].startswith("recorded_at,trigger,commit")
    assert len(lines) == 2
    assert "efficiency_per_1k_tokens" in lines[0]
