"""Runtime and spec-surface assertions for the dense-cadence first-result gate invariant."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gpd.core.config import ReviewCadence, load_config
from gpd.core.errors import ConfigError
from gpd.core.observability import (
    ensure_session,
    get_current_execution,
    observe_event,
)


def _create_config(tmp_path: Path, config: dict) -> Path:
    """Write config.json and return its path."""
    config_path = tmp_path / "GPD" / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config), encoding="utf-8")
    return config_path


def test_dense_cadence_forces_first_result_gate_required_on_low_risk_wave(
    tmp_path: Path, monkeypatch
) -> None:
    _create_config(tmp_path, {"review_cadence": "dense"})
    monkeypatch.chdir(tmp_path)

    cfg = load_config(tmp_path)
    assert cfg.review_cadence == ReviewCadence.DENSE

    session = ensure_session(tmp_path, source="cli", command="execute-phase")
    assert session is not None

    observe_event(
        tmp_path,
        category="execution",
        name="result",
        action="produce",
        status="ok",
        command="execute-phase",
        phase="03",
        plan="01",
        session_id=session.session_id,
        data={
            "execution": {
                "workflow": "execute-phase",
                "segment_id": "seg-01",
                "load_bearing": False,
                "last_result_label": "Low-risk proxy check",
            }
        },
    )

    snapshot = get_current_execution(tmp_path)
    assert snapshot is not None
    assert snapshot.first_result_gate_pending is True


def test_dense_cadence_trips_gate_on_nonloadbearing_result_event(
    tmp_path: Path, monkeypatch
) -> None:
    # Part 1: dense + result/log + load_bearing=False → gate trips.
    dense_project = tmp_path / "dense"
    dense_project.mkdir()
    _create_config(dense_project, {"review_cadence": "dense"})
    monkeypatch.chdir(dense_project)

    dense_cfg = load_config(dense_project)
    assert dense_cfg.review_cadence == ReviewCadence.DENSE

    dense_session = ensure_session(dense_project, source="cli", command="execute-phase")
    assert dense_session is not None

    observe_event(
        dense_project,
        category="execution",
        name="result",
        action="log",
        status="ok",
        command="execute-phase",
        phase="03",
        plan="01",
        session_id=dense_session.session_id,
        data={
            "execution": {
                "workflow": "execute-phase",
                "segment_id": "seg-dense-01",
                "load_bearing": False,
                "last_result_label": "Dense log-style result",
            }
        },
    )

    dense_snapshot = get_current_execution(dense_project)
    assert dense_snapshot is not None
    assert dense_snapshot.first_result_gate_pending is True

    # Part 2: adaptive + result/produce + load_bearing=False → gate stays quiet.
    adaptive_project = tmp_path / "adaptive"
    adaptive_project.mkdir()
    _create_config(adaptive_project, {"review_cadence": "adaptive"})
    monkeypatch.chdir(adaptive_project)

    adaptive_cfg = load_config(adaptive_project)
    assert adaptive_cfg.review_cadence == ReviewCadence.ADAPTIVE

    adaptive_session = ensure_session(adaptive_project, source="cli", command="execute-phase")
    assert adaptive_session is not None

    observe_event(
        adaptive_project,
        category="execution",
        name="result",
        action="produce",
        status="ok",
        command="execute-phase",
        phase="03",
        plan="01",
        session_id=adaptive_session.session_id,
        data={
            "execution": {
                "workflow": "execute-phase",
                "segment_id": "seg-adaptive-01",
                "review_cadence": "adaptive",
                "load_bearing": False,
                "last_result_label": "Adaptive non-load-bearing result",
            }
        },
    )

    adaptive_snapshot = get_current_execution(adaptive_project)
    assert adaptive_snapshot is not None
    assert adaptive_snapshot.first_result_gate_pending is False


def test_dense_cadence_forces_pre_fanout_review_required() -> None:
    execute_phase = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "gpd"
        / "specs"
        / "workflows"
        / "execute-phase.md"
    ).read_text(encoding="utf-8")

    assert "Dense cadence override:" in execute_phase
    assert "FIRST_RESULT_GATE_REQUIRED=true" in execute_phase
    assert "PRE_FANOUT_REVIEW_REQUIRED=true" in execute_phase

    # Both invariants must live inside the same paragraph as the override header.
    override_index = execute_phase.index("Dense cadence override:")
    paragraph_end = execute_phase.find("\n\n", override_index)
    if paragraph_end == -1:
        paragraph_end = len(execute_phase)
    override_paragraph = execute_phase[override_index:paragraph_end]
    assert "FIRST_RESULT_GATE_REQUIRED=true" in override_paragraph
    assert "PRE_FANOUT_REVIEW_REQUIRED=true" in override_paragraph


def test_dense_cadence_cannot_be_overridden_to_disable_gate(tmp_path: Path) -> None:
    _create_config(
        tmp_path,
        {
            "review_cadence": "dense",
            "checkpoint_after_first_load_bearing_result": False,
        },
    )

    with pytest.raises(ConfigError, match="dense"):
        load_config(tmp_path)


def test_clean_wave_under_dense_batches_post_task_checkpoints() -> None:
    """Under supervised + dense, a wave whose tasks all pass cleanly collapses
    per-task checkpoints into one batch approval; any deviation reverts to
    per-task. Pinned in execute-plan.md so the orchestrator respects it."""
    execute_plan = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "gpd"
        / "specs"
        / "workflows"
        / "execute-plan.md"
    ).read_text(encoding="utf-8")

    # Cadence table row (L155) describes dense clean-pass batching.
    assert "review_cadence=dense" in execute_plan
    assert "Approve tasks" in execute_plan
    assert "clean pass" in execute_plan.lower()

    # Supervised post-task block (L412-414) documents the batching rule + fallback.
    assert "Clean-wave batching under dense" in execute_plan

    # Deviation fallback is explicit: any deviation flips back to per-task.
    assert (
        "reverts to per-task" in execute_plan
        or "reverts the wave" in execute_plan
        or "falls back to per-task" in execute_plan
        or "no partial batching" in execute_plan
    )

    # Batching must not relax gates — Phase 4 invariant.
    assert "collapses keystrokes, not gates" in execute_plan


def test_result_verb_whitelist_is_produce_and_log_only() -> None:
    """Pin the canonical verb set that triggers the first-result guard.
    Changing this silently would let a new result verb bypass Phase 4."""
    from gpd.core.observability import _RESULT_VERBS

    assert _RESULT_VERBS == frozenset({"produce", "log"})


def test_dense_gate_clears_cleanly_on_gate_clear_after_result_produce(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Under dense, first-result gate trip must fully reset on gate/clear
    with checkpoint_reason=first_result. Closes the S3.10 coverage gap."""
    _create_config(tmp_path, {"review_cadence": "dense"})
    monkeypatch.chdir(tmp_path)

    session = ensure_session(tmp_path, source="cli", command="execute-phase")

    observe_event(
        tmp_path,
        category="execution",
        name="result",
        action="produce",
        status="ok",
        command="execute-phase",
        phase="03",
        plan="01",
        session_id=session.session_id,
        data={"execution": {"load_bearing": False}},
    )

    snapshot = get_current_execution(tmp_path)
    assert snapshot.first_result_gate_pending is True
    assert snapshot.waiting_for_review is True

    observe_event(
        tmp_path,
        category="execution",
        name="gate",
        action="clear",
        status="ok",
        command="execute-phase",
        phase="03",
        plan="01",
        session_id=session.session_id,
        data={"execution": {"checkpoint_reason": "first_result"}},
    )

    cleared = get_current_execution(tmp_path)
    assert cleared.first_result_gate_pending is False
    assert cleared.waiting_for_review is False
    assert cleared.review_required is False
