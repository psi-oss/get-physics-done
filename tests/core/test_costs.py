from __future__ import annotations

import json
from pathlib import Path

import pytest

import gpd.core.costs as costs
from gpd.core.costs import (
    build_cost_summary,
    list_usage_records,
    pricing_snapshot_path,
    record_usage_from_runtime_payload,
    usage_ledger_path,
)


def _bootstrap_project(tmp_path: Path, name: str = "project") -> Path:
    project = tmp_path / name
    (project / "GPD").mkdir(parents=True, exist_ok=True)
    return project


def _write_current_execution(project: Path, payload: dict[str, object]) -> None:
    observability_dir = project / "GPD" / "observability"
    observability_dir.mkdir(parents=True, exist_ok=True)
    (observability_dir / "current-execution.json").write_text(json.dumps(payload), encoding="utf-8")


def _payload(
    *,
    model: str = "gpt-5.4",
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    total_tokens: int | None = None,
    cached_input_tokens: int | None = None,
    cache_write_input_tokens: int | None = None,
    cost_usd: float | None = None,
    extra: dict[str, object] | None = None,
) -> dict[str, object]:
    usage: dict[str, object] = {}
    if input_tokens is not None:
        usage["input_tokens"] = input_tokens
    if output_tokens is not None:
        usage["output_tokens"] = output_tokens
    if total_tokens is not None:
        usage["total_tokens"] = total_tokens
    if cached_input_tokens is not None:
        usage["cached_input_tokens"] = cached_input_tokens
    if cache_write_input_tokens is not None:
        usage["cache_write_input_tokens"] = cache_write_input_tokens
    if cost_usd is not None:
        usage["cost_usd"] = cost_usd
    payload = {
        "type": "response.completed",
        "model": model,
        "usage": usage,
    }
    if extra:
        payload.update(extra)
    return payload


def _write_pricing_snapshot(data_root: Path) -> None:
    snapshot_path = pricing_snapshot_path(data_root)
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text(
        json.dumps(
            {
                "source": "fixture-pricing",
                "as_of": "2026-03-27",
                "currency": "USD",
                "entries": [
                    {
                        "runtime": "codex",
                        "model": "gpt-5.4",
                        "input_per_million_usd": 3.0,
                        "output_per_million_usd": 15.0,
                        "cached_input_per_million_usd": 0.3,
                        "cache_write_input_per_million_usd": 3.75,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_record_usage_writes_measured_records_and_builds_project_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_root = tmp_path / "data"
    project = _bootstrap_project(tmp_path, "project-a")
    other_project = _bootstrap_project(tmp_path, "project-b")

    current_session = {"value": "sess-a"}
    timestamps = iter(
        [
            "2026-03-27T12:00:00+00:00",
            "2026-03-27T12:01:00+00:00",
            "2026-03-27T12:02:00+00:00",
        ]
    )
    monkeypatch.setattr(costs, "_now_iso", lambda: next(timestamps))
    monkeypatch.setattr(costs, "get_current_session_id", lambda _root: current_session["value"])

    record_usage_from_runtime_payload(
        _payload(input_tokens=100, output_tokens=25, cost_usd=0.01),
        runtime="codex",
        cwd=project,
        data_root=data_root,
    )
    current_session["value"] = "sess-b"
    record_usage_from_runtime_payload(
        _payload(input_tokens=200, output_tokens=50, cost_usd=0.02),
        runtime="codex",
        cwd=project,
        data_root=data_root,
    )
    current_session["value"] = "sess-c"
    record_usage_from_runtime_payload(
        _payload(input_tokens=300, output_tokens=75, cost_usd=0.03),
        runtime="codex",
        cwd=other_project,
        data_root=data_root,
    )

    records = list_usage_records(data_root)
    assert len(records) == 3
    assert all(record.agent_scope == "main_agent" for record in records)
    assert all(record.agent_attribution_source == "default-main" for record in records)

    current_session["value"] = "sess-b"
    summary = build_cost_summary(project, data_root=data_root, last_sessions=5)

    assert summary.workspace_root == project.resolve(strict=False).as_posix()
    assert summary.project.project_root == project.resolve(strict=False).as_posix()
    assert summary.project.record_count == 2
    assert summary.project.usage_status == "measured"
    assert summary.project.cost_status == "measured"
    assert summary.project.input_tokens == 300
    assert summary.project.output_tokens == 75
    assert summary.project.total_tokens == 375
    assert summary.project.cost_usd == pytest.approx(0.03)
    assert summary.current_session is not None
    assert summary.current_session.session_id == "sess-b"
    assert summary.current_session.record_count == 1
    assert summary.current_session.total_tokens == 250
    assert [row.session_id for row in summary.recent_sessions] == ["sess-c", "sess-b", "sess-a"]


def test_record_usage_keeps_explicit_subagent_identity_from_payload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_root = tmp_path / "data"
    project = _bootstrap_project(tmp_path)
    monkeypatch.setattr(costs, "get_current_session_id", lambda _root: "sess-agent")
    monkeypatch.setattr(costs, "_now_iso", lambda: "2026-03-27T12:10:00+00:00")

    record = record_usage_from_runtime_payload(
        _payload(
            input_tokens=120,
            output_tokens=30,
            cost_usd=0.02,
            extra={"subagent": {"id": "agent-42", "name": "gpd-executor"}},
        ),
        runtime="codex",
        cwd=project,
        data_root=data_root,
    )

    assert record is not None
    assert record.agent_id == "agent-42"
    assert record.agent_name == "gpd-executor"
    assert record.agent_kind == "subagent"
    assert record.agent_id_source == "payload.subagent.id"
    assert record.agent_name_source == "payload.subagent.name"
    assert record.agent_kind_source == "payload.subagent"


def test_record_usage_prefers_explicit_payload_attribution_over_workspace_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_root = tmp_path / "data"
    project = _bootstrap_project(tmp_path)
    monkeypatch.setattr(costs, "get_current_session_id", lambda _root: "sess-agent")
    monkeypatch.setattr(costs, "_now_iso", lambda: "2026-03-27T12:11:00+00:00")
    (project / "GPD" / "current-agent-id.txt").write_text("agent-fallback\n", encoding="utf-8")
    _write_current_execution(
        project,
        {
            "session_id": "sess-agent",
            "segment_status": "active",
            "current_task": "Run executor task",
        },
    )

    record = record_usage_from_runtime_payload(
        _payload(
            input_tokens=120,
            output_tokens=30,
            cost_usd=0.02,
            extra={"subagent_id": "agent-explicit", "subagent_type": "gpd-executor"},
        ),
        runtime="codex",
        cwd=project,
        data_root=data_root,
    )

    assert record is not None
    assert record.agent_id == "agent-explicit"
    assert record.agent_name == "gpd-executor"
    assert record.agent_kind == "subagent"
    assert record.agent_id_source == "payload.subagent_id"
    assert record.agent_name_source == "payload.subagent_type"
    assert record.agent_kind_source == "payload.subagent_type"


def test_record_usage_falls_back_to_current_agent_file_when_active_session_matches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_root = tmp_path / "data"
    project = _bootstrap_project(tmp_path)
    monkeypatch.setattr(costs, "get_current_session_id", lambda _root: "sess-fallback")
    monkeypatch.setattr(costs, "_now_iso", lambda: "2026-03-27T12:12:00+00:00")
    (project / "GPD" / "current-agent-id.txt").write_text("agent-fallback\n", encoding="utf-8")
    _write_current_execution(
        project,
        {
            "session_id": "sess-fallback",
            "segment_status": "active",
            "current_task": "Run executor task",
        },
    )

    record = record_usage_from_runtime_payload(
        _payload(input_tokens=120, output_tokens=30, cost_usd=0.02),
        runtime="codex",
        cwd=project,
        data_root=data_root,
    )

    assert record is not None
    assert record.agent_id == "agent-fallback"
    assert record.agent_name is None
    assert record.agent_kind is None
    assert record.agent_id_source == "workspace.current-agent-id"
    assert record.agent_name_source is None
    assert record.agent_kind_source is None


def test_record_usage_does_not_claim_workspace_agent_id_without_matching_active_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_root = tmp_path / "data"
    project = _bootstrap_project(tmp_path)
    monkeypatch.setattr(costs, "get_current_session_id", lambda _root: "sess-live")
    monkeypatch.setattr(costs, "_now_iso", lambda: "2026-03-27T12:13:00+00:00")
    (project / "GPD" / "current-agent-id.txt").write_text("agent-stale\n", encoding="utf-8")
    _write_current_execution(
        project,
        {
            "session_id": "sess-other",
            "segment_status": "active",
            "current_task": "Run executor task",
        },
    )

    record = record_usage_from_runtime_payload(
        _payload(input_tokens=120, output_tokens=30, cost_usd=0.02),
        runtime="codex",
        cwd=project,
        data_root=data_root,
    )

    assert record is not None
    assert record.agent_id is None
    assert record.agent_name is None
    assert record.agent_kind is None
    assert record.agent_id_source is None


def test_record_usage_skips_when_runtime_payload_has_no_usage_signal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_root = tmp_path / "data"
    project = _bootstrap_project(tmp_path)
    monkeypatch.setattr(costs, "get_current_session_id", lambda _root: "sess-empty")

    record = record_usage_from_runtime_payload(
        {"type": "response.completed", "model": "gpt-5.4", "usage": {}},
        runtime="codex",
        cwd=project,
        data_root=data_root,
    )

    assert record is None
    assert list_usage_records(data_root) == []
    assert not usage_ledger_path(data_root).exists()


def test_record_usage_skips_runtime_without_declared_telemetry_collection_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_root = tmp_path / "data"
    project = _bootstrap_project(tmp_path)
    monkeypatch.setattr(costs, "get_current_session_id", lambda _root: "sess-claude")

    record = record_usage_from_runtime_payload(
        _payload(input_tokens=100, output_tokens=25, cost_usd=0.01),
        runtime="claude-code",
        cwd=project,
        data_root=data_root,
    )

    assert record is None
    assert list_usage_records(data_root) == []
    assert not usage_ledger_path(data_root).exists()


def test_record_usage_estimates_cost_from_pricing_snapshot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data_root = tmp_path / "data"
    project = _bootstrap_project(tmp_path)
    _write_pricing_snapshot(data_root)
    monkeypatch.setattr(costs, "get_current_session_id", lambda _root: "sess-priced")
    monkeypatch.setattr(costs, "_now_iso", lambda: "2026-03-27T13:00:00+00:00")

    record = record_usage_from_runtime_payload(
        _payload(
            input_tokens=1_000,
            output_tokens=500,
            cached_input_tokens=100,
            cache_write_input_tokens=50,
        ),
        runtime="codex",
        cwd=project,
        data_root=data_root,
    )

    expected_cost = round(
        (1_000 / 1_000_000) * 3.0 + (500 / 1_000_000) * 15.0 + (100 / 1_000_000) * 0.3 + (50 / 1_000_000) * 3.75,
        6,
    )

    assert record is not None
    assert record.cost_status == "estimated"
    assert record.cost_source == "pricing-snapshot"
    assert record.cost_usd == expected_cost
    assert record.pricing_snapshot_source == "fixture-pricing"
    assert record.pricing_snapshot_as_of == "2026-03-27"

    summary = build_cost_summary(project, data_root=data_root, last_sessions=3)
    assert summary.pricing_snapshot_configured is True
    assert summary.pricing_snapshot_source == "fixture-pricing"
    assert summary.pricing_snapshot_as_of == "2026-03-27"
    assert summary.project.cost_status == "estimated"
    assert summary.project.cost_usd == expected_cost


def test_record_usage_dedupes_identical_payloads_within_window(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data_root = tmp_path / "data"
    project = _bootstrap_project(tmp_path)
    monkeypatch.setattr(costs, "get_current_session_id", lambda _root: "sess-dedupe")
    monkeypatch.setattr(costs, "_now_iso", lambda: "2026-03-27T14:00:00+00:00")

    payload = _payload(input_tokens=400, output_tokens=100, cost_usd=0.04)
    first = record_usage_from_runtime_payload(
        payload,
        runtime="codex",
        cwd=project,
        data_root=data_root,
    )
    second = record_usage_from_runtime_payload(
        payload,
        runtime="codex",
        cwd=project,
        data_root=data_root,
    )

    assert first is not None
    assert second is not None
    assert second.record_id == first.record_id
    records = list_usage_records(data_root)
    assert len(records) == 1
    assert records[0].total_tokens == 500


def test_record_usage_marks_workspace_fallback_as_subagent_scope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_root = tmp_path / "data"
    project = _bootstrap_project(tmp_path)
    monkeypatch.setattr(costs, "get_current_session_id", lambda _root: "sess-fallback")
    monkeypatch.setattr(costs, "_now_iso", lambda: "2026-03-27T14:05:00+00:00")
    (project / "GPD" / "current-agent-id.txt").write_text("agent-fallback\n", encoding="utf-8")
    _write_current_execution(
        project,
        {
            "session_id": "sess-fallback",
            "segment_status": "active",
            "current_task": "Run executor task",
        },
    )

    record = record_usage_from_runtime_payload(
        _payload(input_tokens=120, output_tokens=30, cost_usd=0.02),
        runtime="codex",
        cwd=project,
        data_root=data_root,
    )

    assert record is not None
    assert record.agent_scope == "subagent"
    assert record.agent_attribution_source == "workspace-state"


def test_record_usage_preserves_explicit_workspace_and_project_roots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_root = tmp_path / "data"
    project = _bootstrap_project(tmp_path)
    nested = project / "src"
    nested.mkdir()
    monkeypatch.setattr(costs, "get_current_session_id", lambda _root: "sess-roots")
    monkeypatch.setattr(costs, "_now_iso", lambda: "2026-03-27T14:06:00+00:00")

    record = record_usage_from_runtime_payload(
        _payload(input_tokens=120, output_tokens=30, cost_usd=0.02),
        runtime="codex",
        cwd=nested,
        workspace_root=nested,
        project_root=project,
        data_root=data_root,
    )

    assert record is not None
    assert record.workspace_root == nested.resolve(strict=False).as_posix()
    assert record.project_root == project.resolve(strict=False).as_posix()


def test_build_cost_summary_marks_mixed_measured_and_estimated_usd_as_advisory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_root = tmp_path / "data"
    project = _bootstrap_project(tmp_path)
    _write_pricing_snapshot(data_root)

    session_ids = iter(["sess-measured", "sess-estimated"])
    monkeypatch.setattr(costs, "get_current_session_id", lambda _root: next(session_ids))
    timestamps = iter(
        [
            "2026-03-27T15:00:00+00:00",
            "2026-03-27T15:01:00+00:00",
        ]
    )
    monkeypatch.setattr(costs, "_now_iso", lambda: next(timestamps))

    record_usage_from_runtime_payload(
        _payload(input_tokens=400, output_tokens=100, cost_usd=0.04),
        runtime="codex",
        cwd=project,
        data_root=data_root,
    )
    record_usage_from_runtime_payload(
        _payload(input_tokens=1_000, output_tokens=500),
        runtime="codex",
        cwd=project,
        data_root=data_root,
    )
    monkeypatch.setattr(costs, "get_current_session_id", lambda _root: "sess-estimated")

    summary = build_cost_summary(project, data_root=data_root, last_sessions=5)

    expected_estimated = round((1_000 / 1_000_000) * 3.0 + (500 / 1_000_000) * 15.0, 6)

    assert summary.project.cost_status == "mixed"
    assert summary.project.cost_usd == pytest.approx(round(0.04 + expected_estimated, 6))
    assert any("mixes measured runtime telemetry with pricing-snapshot estimates" in item for item in summary.guidance)


def test_build_cost_summary_surfaces_advisory_budget_thresholds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_root = tmp_path / "data"
    project = _bootstrap_project(tmp_path)
    (project / "GPD" / "config.json").write_text(
        json.dumps(
            {
                "execution": {
                    "project_usd_budget": 1.0,
                    "session_usd_budget": 0.3,
                }
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(costs, "get_current_session_id", lambda _root: "sess-budget")
    monkeypatch.setattr(costs, "_now_iso", lambda: "2026-03-27T16:00:00+00:00")

    record_usage_from_runtime_payload(
        _payload(input_tokens=600, output_tokens=400, cost_usd=0.25),
        runtime="codex",
        cwd=project,
        data_root=data_root,
    )

    summary = build_cost_summary(project, data_root=data_root, last_sessions=5)
    thresholds = {threshold.config_key: threshold for threshold in summary.budget_thresholds}

    assert set(thresholds) == {"project_usd_budget", "session_usd_budget"}

    project_threshold = thresholds["project_usd_budget"]
    assert project_threshold.scope == "project"
    assert project_threshold.advisory_only is True
    assert project_threshold.budget_usd == 1.0
    assert project_threshold.spent_usd == pytest.approx(0.25)
    assert project_threshold.remaining_usd == pytest.approx(0.75)
    assert project_threshold.percent_used == pytest.approx(25.0)
    assert project_threshold.cost_status == "measured"
    assert project_threshold.comparison_exact is True
    assert project_threshold.state == "within_budget"
    assert "within budget based on measured local USD telemetry" in project_threshold.message

    session_threshold = thresholds["session_usd_budget"]
    assert session_threshold.scope == "session"
    assert session_threshold.budget_usd == 0.3
    assert session_threshold.spent_usd == pytest.approx(0.25)
    assert session_threshold.remaining_usd == pytest.approx(0.05)
    assert session_threshold.percent_used == pytest.approx(83.33)
    assert session_threshold.cost_status == "measured"
    assert session_threshold.comparison_exact is True
    assert session_threshold.state == "near_budget"
    assert "nearing budget based on measured local USD telemetry" in session_threshold.message


def test_build_cost_summary_marks_configured_budgets_unavailable_without_spend(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _bootstrap_project(tmp_path)
    (project / "GPD" / "config.json").write_text(
        json.dumps(
            {
                "execution": {
                    "project_usd_budget": 1.0,
                    "session_usd_budget": 0.5,
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(costs, "get_current_session_id", lambda _root: None)

    summary = build_cost_summary(project, data_root=tmp_path / "data", last_sessions=5)
    thresholds = {threshold.config_key: threshold for threshold in summary.budget_thresholds}

    assert thresholds["project_usd_budget"].spent_usd is None
    assert thresholds["project_usd_budget"].remaining_usd is None
    assert thresholds["project_usd_budget"].percent_used is None
    assert thresholds["project_usd_budget"].cost_status == "unavailable"
    assert thresholds["project_usd_budget"].comparison_exact is False
    assert thresholds["project_usd_budget"].state == "unavailable"
    assert "comparison is unavailable" in thresholds["project_usd_budget"].message
    assert thresholds["session_usd_budget"].spent_usd is None
    assert thresholds["session_usd_budget"].comparison_exact is False
    assert thresholds["session_usd_budget"].state == "unavailable"


def test_build_cost_summary_marks_budget_overrun_when_spend_reaches_threshold(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_root = tmp_path / "data"
    project = _bootstrap_project(tmp_path)
    (project / "GPD" / "config.json").write_text(
        json.dumps({"execution": {"project_usd_budget": 0.25}}),
        encoding="utf-8",
    )

    monkeypatch.setattr(costs, "get_current_session_id", lambda _root: "sess-overrun")
    monkeypatch.setattr(costs, "_now_iso", lambda: "2026-03-27T16:00:00+00:00")

    record_usage_from_runtime_payload(
        _payload(input_tokens=600, output_tokens=400, cost_usd=0.25),
        runtime="codex",
        cwd=project,
        data_root=data_root,
    )

    summary = build_cost_summary(project, data_root=data_root, last_sessions=5)
    project_threshold = next(
        threshold for threshold in summary.budget_thresholds if threshold.config_key == "project_usd_budget"
    )

    assert project_threshold.state == "at_or_over_budget"
    assert project_threshold.remaining_usd == pytest.approx(0.0)
    assert "at or over budget" in project_threshold.message


def test_build_cost_summary_marks_cost_only_records_as_token_incomplete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_root = tmp_path / "data"
    project = _bootstrap_project(tmp_path)
    monkeypatch.setattr(costs, "get_current_session_id", lambda _root: "sess-cost-only")
    timestamps = iter(
        [
            "2026-03-27T14:00:00+00:00",
            "2026-03-27T14:01:00+00:00",
        ]
    )
    monkeypatch.setattr(costs, "_now_iso", lambda: next(timestamps))

    record_usage_from_runtime_payload(
        _payload(cost_usd=0.25),
        runtime="codex",
        cwd=project,
        data_root=data_root,
    )

    summary = build_cost_summary(project, data_root=data_root, last_sessions=5)

    assert summary.project.usage_status == "unavailable"
    assert summary.project.cost_status == "measured"
    assert summary.project.interpretation == "USD measured; token counts unavailable"
    assert summary.current_session is not None
    assert summary.current_session.interpretation == "USD measured; token counts unavailable"


def test_build_cost_summary_surfaces_active_runtime_capabilities_in_guidance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _bootstrap_project(tmp_path)
    monkeypatch.setattr(costs, "get_current_session_id", lambda _root: None)

    class _Config:
        model_profile = "review"
        model_overrides = {}

    monkeypatch.setattr("gpd.core.config.load_config", lambda _cwd: _Config())
    monkeypatch.setattr("gpd.hooks.runtime_detect.detect_runtime_for_gpd_use", lambda cwd=None: "claude-code")

    summary = build_cost_summary(project, data_root=tmp_path / "data", last_sessions=5)

    assert summary.active_runtime == "claude-code"
    assert summary.active_runtime_capabilities["telemetry_completeness"] == "none"
    assert summary.active_runtime_capabilities["statusline_surface"] == "explicit"
    assert any(
        "does not currently expose a GPD-managed usage telemetry collection path" in item for item in summary.guidance
    )
    assert not any(
        "No measured usage telemetry is recorded for this workspace yet." in item for item in summary.guidance
    )


def test_build_cost_summary_surfaces_best_effort_runtime_guidance_without_generic_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _bootstrap_project(tmp_path)
    monkeypatch.setattr(costs, "get_current_session_id", lambda _root: None)

    class _Config:
        model_profile = "review"
        model_overrides = {}

    monkeypatch.setattr("gpd.core.config.load_config", lambda _cwd: _Config())
    monkeypatch.setattr("gpd.hooks.runtime_detect.detect_runtime_for_gpd_use", lambda cwd=None: "codex")

    summary = build_cost_summary(project, data_root=tmp_path / "data", last_sessions=5)

    assert summary.active_runtime == "codex"
    assert summary.active_runtime_capabilities["telemetry_source"] == "notify-hook"
    assert summary.active_runtime_capabilities["telemetry_completeness"] == "best-effort"
    assert any("only exposes best-effort usage telemetry through notify-hook" in item for item in summary.guidance)
    assert not any(
        "No measured usage telemetry is recorded for this workspace yet." in item for item in summary.guidance
    )
