"""Behavioral consistency checks for the state MCP server."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import anyio
import pytest

from gpd.core.errors import GPDError
from gpd.core.health import CheckStatus, HealthCheck, HealthReport, HealthSummary
from gpd.core.state import default_state_dict
from gpd.mcp.servers.state_server import (
    advance_plan,
    apply_return_updates,
    get_config,
    get_phase_info,
    get_progress,
    get_state,
    load_state_json,
    mcp,
    run_health_check,
    validate_state,
)
from tests.mcp.conftest import FAKE_PROJECT_DIR


async def _tool_names() -> list[str]:
    tools = await mcp.list_tools()
    return [tool.name for tool in tools]


def test_state_server_exposes_expected_tool_names() -> None:
    names = anyio.run(_tool_names)

    assert {
        "get_state",
        "get_phase_info",
        "advance_plan",
        "get_progress",
        "validate_state",
        "run_health_check",
        "get_config",
    } == set(names)


def test_state_server_apply_return_updates_wraps_canonical_command(monkeypatch, tmp_path: Path) -> None:
    mock_result = SimpleNamespace(
        model_dump=lambda: {
            "passed": True,
            "status": "applied",
            "files_written": ["GPD/phases/01-foundations/01-foundations-01-SUMMARY.md"],
        }
    )
    monkeypatch.setattr(
        "gpd.mcp.servers.state_server.cmd_apply_return_updates",
        lambda *_args, **_kwargs: mock_result,
    )

    result = apply_return_updates(str(tmp_path), "GPD/phases/01-foundations/01-foundations-01-SUMMARY.md")

    assert result["schema_version"] == 1
    assert result["passed"] is True
    assert result["status"] == "applied"
    assert result["files_written"] == ["GPD/phases/01-foundations/01-foundations-01-SUMMARY.md"]


def test_state_server_apply_return_updates_rejects_relative_project_dir(monkeypatch) -> None:
    monkeypatch.setattr(
        "gpd.mcp.servers.state_server.cmd_apply_return_updates",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should not run")),
    )

    result = apply_return_updates("relative/project", "GPD/phases/01-foundations/01-foundations-01-SUMMARY.md")

    assert result == {"error": "project_dir must be an absolute path", "schema_version": 1}


@pytest.mark.parametrize(
    ("tool_fn", "kwargs"),
    [
        (get_state, {"project_dir": "relative/project"}),
        (get_phase_info, {"project_dir": "relative/project", "phase": "01"}),
        (advance_plan, {"project_dir": "relative/project"}),
        (get_progress, {"project_dir": "relative/project"}),
        (validate_state, {"project_dir": "relative/project"}),
        (run_health_check, {"project_dir": "relative/project", "fix": False}),
        (get_config, {"project_dir": "relative/project"}),
    ],
)
def test_state_server_tools_reject_non_absolute_project_dirs(tool_fn, kwargs: dict[str, object]) -> None:
    result = tool_fn(**kwargs)

    assert result == {"error": "project_dir must be an absolute path", "schema_version": 1}


@pytest.mark.parametrize(
    ("tool_fn", "patch_target", "kwargs"),
    [
        (get_state, "gpd.mcp.servers.state_server.load_state_json", {"project_dir": FAKE_PROJECT_DIR}),
        (get_phase_info, "gpd.core.phases.find_phase", {"project_dir": FAKE_PROJECT_DIR, "phase": "01"}),
        (advance_plan, "gpd.mcp.servers.state_server.state_advance_plan", {"project_dir": FAKE_PROJECT_DIR}),
        (get_progress, "gpd.mcp.servers.state_server.progress_render", {"project_dir": FAKE_PROJECT_DIR}),
        (validate_state, "gpd.mcp.servers.state_server.state_validate", {"project_dir": FAKE_PROJECT_DIR}),
        (run_health_check, "gpd.mcp.servers.state_server.run_health", {"project_dir": FAKE_PROJECT_DIR, "fix": False}),
        (get_config, "gpd.mcp.servers.state_server.load_config", {"project_dir": FAKE_PROJECT_DIR}),
    ],
)
@pytest.mark.parametrize("error_factory", [lambda: GPDError("boom"), lambda: OSError("missing"), lambda: ValueError("bad")])
def test_state_server_tools_return_stable_error_envelopes(tool_fn, patch_target: str, kwargs: dict[str, object], error_factory, monkeypatch) -> None:
    monkeypatch.setattr(
        patch_target,
        lambda *_args, **_kwargs: (_ for _ in ()).throw(error_factory()),
    )

    result = tool_fn(**kwargs)

    assert result["schema_version"] == 1
    assert result["error"] in {"boom", "missing", "bad"}


def test_load_state_json_strips_legacy_session_and_surfaces_contract_gate(monkeypatch, tmp_path: Path) -> None:
    state_obj = {
        "position": {"current_phase": "01"},
        "decisions": [],
        "blockers": [],
        "session": {"last_date": "2026-01-01"},
    }

    monkeypatch.setattr(
        "gpd.mcp.servers.state_server.peek_state_json",
        lambda *_args, **_kwargs: (state_obj, [], "state.json"),
    )
    monkeypatch.setattr(
        "gpd.mcp.servers.state_server._project_contract_runtime_payload_for_state",
        lambda *_args, **_kwargs: (
            {"status": "loaded"},
            {"valid": True},
            {"authoritative": True},
        ),
    )

    result = load_state_json(tmp_path)

    assert result is not None
    assert "session" not in result
    assert result["position"]["current_phase"] == "01"
    assert result["project_contract_load_info"]["status"] == "loaded"
    assert result["project_contract_validation"]["valid"] is True
    assert result["project_contract_gate"]["authoritative"] is True


def test_load_state_json_uses_read_only_peek_without_locking(monkeypatch, tmp_path: Path) -> None:
    state_obj = {
        "position": {"current_phase": "01"},
        "decisions": [],
        "blockers": [],
    }

    seen: dict[str, object] = {}

    def _peek_state_json(*args, **kwargs):
        seen["args"] = args
        seen["kwargs"] = kwargs
        return state_obj, [], "state.json"

    monkeypatch.setattr("gpd.mcp.servers.state_server.peek_state_json", _peek_state_json)
    monkeypatch.setattr(
        "gpd.mcp.servers.state_server._project_contract_runtime_payload_for_state",
        lambda *_args, **_kwargs: (
            {"status": "loaded"},
            {"valid": True},
            {"authoritative": True},
        ),
    )

    result = load_state_json(tmp_path)

    assert result is not None
    assert seen["args"] == (tmp_path,)
    assert seen["kwargs"]["recover_intent"] is False
    assert seen["kwargs"]["surface_blocked_project_contract"] is True
    assert seen["kwargs"]["acquire_lock"] is False


def test_get_state_reports_current_project_state_guidance(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("gpd.mcp.servers.state_server.load_state_json", lambda *_args, **_kwargs: None)

    result = get_state(str(tmp_path))

    assert result == {
        "error": "No project state found. Run 'gpd init new-project' to initialize a GPD project state.",
        "schema_version": 1,
    }


def test_run_health_check_preserves_latest_return_failure_details(monkeypatch, fake_project_dir) -> None:
    failing_check = HealthCheck(
        status=CheckStatus.FAIL,
        label="Latest Return Envelope",
        details={
            "file": "01-setup/01-setup-01-SUMMARY.md",
            "fields_found": [],
            "warning_count": 0,
        },
        issues=["01-setup/01-setup-01-SUMMARY.md: gpd_return YAML parse error: malformed envelope"],
    )
    mock_report = HealthReport(
        overall=CheckStatus.FAIL,
        summary=HealthSummary(ok=0, warn=0, fail=1, total=1),
        checks=[failing_check],
        fixes_applied=[],
    )

    monkeypatch.setattr("gpd.mcp.servers.state_server.run_health", lambda *_args, **_kwargs: mock_report)

    result = run_health_check(fake_project_dir)

    assert result["checks"][0]["label"] == "Latest Return Envelope"
    assert result["checks"][0]["details"]["file"] == "01-setup/01-setup-01-SUMMARY.md"
    assert result["checks"][0]["issues"][0].endswith("malformed envelope")


def test_health_peek_normalized_state_uses_read_only_peek_without_locking(monkeypatch, tmp_path: Path) -> None:
    from gpd.core.health import _peek_normalized_state_for_health

    state_obj = {"position": {"current_phase": "01"}}
    seen: dict[str, object] = {}

    def _peek_state_json(*args, **kwargs):
        seen["args"] = args
        seen["kwargs"] = kwargs
        return state_obj, [], "STATE.md"

    monkeypatch.setattr("gpd.core.health.peek_state_json", _peek_state_json)

    result, source = _peek_normalized_state_for_health(tmp_path)

    assert result == state_obj
    assert source == "STATE.md"
    assert seen["args"] == (tmp_path,)
    assert seen["kwargs"]["recover_intent"] is False
    assert seen["kwargs"]["surface_blocked_project_contract"] is True
    assert seen["kwargs"]["acquire_lock"] is False


def test_get_progress_does_not_mutate_checkpoint_shelf_artifacts(tmp_path: Path) -> None:
    """Progress reads should not create, update, or delete checkpoint shelf files."""
    cwd = tmp_path
    planning = cwd / "GPD"
    planning.mkdir()
    (planning / "phases").mkdir()
    (planning / "state.json").write_text(json.dumps(default_state_dict(), indent=2), encoding="utf-8")

    phase_one = planning / "phases" / "01-foundations"
    phase_one.mkdir()
    (phase_one / "PLAN.md").write_text("# plan\n", encoding="utf-8")
    (phase_one / "SUMMARY.md").write_text("# summary\n", encoding="utf-8")

    phase_two = planning / "phases" / "02-analysis"
    phase_two.mkdir()
    (phase_two / "PLAN.md").write_text("# plan\n", encoding="utf-8")
    (phase_two / "SUMMARY.md").write_text("# summary\n", encoding="utf-8")

    checkpoint_dir = cwd / "GPD" / "phase-checkpoints"
    checkpoint_dir.mkdir()
    stale_checkpoint = checkpoint_dir / "99-old-phase.md"
    stale_checkpoint.write_text("stale checkpoint\n", encoding="utf-8")
    checkpoints_index = cwd / "GPD" / "CHECKPOINTS.md"
    checkpoints_index.write_text("stale index\n", encoding="utf-8")

    result = get_progress(str(cwd))

    assert result["percent"] == 100
    assert result["total_plans"] == 2
    assert result["total_summaries"] == 2
    assert "checkpoint_files" not in result
    assert not (checkpoint_dir / "01-foundations.md").exists()
    assert not (checkpoint_dir / "02-analysis.md").exists()
    assert stale_checkpoint.read_text(encoding="utf-8") == "stale checkpoint\n"
    assert stale_checkpoint.exists()
    assert checkpoints_index.read_text(encoding="utf-8") == "stale index\n"


def test_get_phase_info_counts_only_matching_summary_identities(tmp_path: Path) -> None:
    cwd = tmp_path
    planning = cwd / "GPD"
    planning.mkdir()
    (planning / "phases").mkdir()
    phase_dir = cwd / "GPD" / "phases" / "01-setup"
    phase_dir.mkdir()
    (phase_dir / "PLAN.md").write_text("# plan\n", encoding="utf-8")
    (phase_dir / "01-setup-02-PLAN.md").write_text("# plan\n", encoding="utf-8")
    (phase_dir / "SUMMARY.md").write_text("# summary\n", encoding="utf-8")
    (phase_dir / "01-setup-99-SUMMARY.md").write_text("# summary\n", encoding="utf-8")

    result = get_phase_info(str(cwd), "01")

    assert result["plan_count"] == 2
    assert result["summary_count"] == 1
    assert result["complete"] is False
