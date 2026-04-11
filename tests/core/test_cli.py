"""Tests for gpd.cli — unified CLI entry point.

Tests use typer.testing.CliRunner which invokes the CLI in-process.
We mock the underlying gpd.core.* functions since those modules may not
be fully ported yet and have their own test suites.
"""

from __future__ import annotations

import builtins
import json
import logging
import os
import re
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock, MagicMock, call, patch

import pytest
from typer.testing import CliRunner

import gpd.cli as cli_module
import gpd.runtime_cli as runtime_cli
from gpd.adapters import get_adapter, list_runtimes
from gpd.cli import app
from gpd.core import cli_args as cli_args_module
from gpd.core.constants import STATE_JSON_BACKUP_FILENAME, ProjectLayout
from gpd.core.costs import (
    CostBudgetThresholdSummary,
    CostProjectSummary,
    CostSessionSummary,
    CostSummary,
    _profile_tier_mix,
)
from gpd.core.frontmatter import FrontmatterParseError
from gpd.core.health import (
    CheckStatus,
    DoctorReport,
    HealthCheck,
    HealthSummary,
    UnattendedReadinessCheck,
    UnattendedReadinessResult,
)
from gpd.core.project_reentry import resolve_project_reentry
from gpd.core.public_surface_contract import (
    local_cli_bridge_commands,
    local_cli_doctor_local_command,
    local_cli_install_local_example_command,
    local_cli_permissions_status_command,
    local_cli_permissions_sync_command,
    local_cli_plan_preflight_command,
    local_cli_resume_command,
    local_cli_resume_recent_command,
    local_cli_unattended_readiness_command,
    local_cli_validate_command_context_command,
)
from gpd.core.resume_surface import RESUME_COMPATIBILITY_ALIAS_FIELDS
from gpd.core.state import default_state_dict, generate_state_markdown, save_state_json, save_state_markdown
from tests.latex_test_support import toolchain_capability as _toolchain_capability
from tests.runtime_test_support import (
    FOREIGN_RUNTIME,
    PRIMARY_RUNTIME,
    runtime_config_dir_name,
    runtime_display_name,
    runtime_prompt_free_mode_value,
    runtime_target_dir,
    runtime_with_permissions_surface,
)


class _StableCliRunner(CliRunner):
    def invoke(self, *args, **kwargs):
        kwargs.setdefault("color", False)
        return super().invoke(*args, **kwargs)


runner = _StableCliRunner()

_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def _normalize_cli_output(text: str) -> str:
    return " ".join(_ANSI_ESCAPE_RE.sub("", text).split())

_COST_TEST_RUNTIME = "runtime-under-test"
_COST_TEST_MODEL = "model-under-test"
_CONFIG_FILE_RUNTIME = runtime_with_permissions_surface("config-file")
_CONFIG_FILE_PROMPT_FREE_MODE = runtime_prompt_free_mode_value(_CONFIG_FILE_RUNTIME)
_LAUNCH_WRAPPER_RUNTIME = runtime_with_permissions_surface("launch-wrapper")
FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "stage0"


def _assert_no_top_level_resume_aliases(payload: dict[str, object]) -> None:
    for key in RESUME_COMPATIBILITY_ALIAS_FIELDS:
        assert key not in payload


def _make_checkout(tmp_path: Path, version: str = "9.9.9") -> Path:
    """Create a minimal GPD source checkout for CLI version tests."""
    repo_root = tmp_path / "checkout"
    repo_root.mkdir(parents=True, exist_ok=True)
    (repo_root / "package.json").write_text(
        json.dumps(
            {
                "name": "get-physics-done",
                "version": version,
                "gpdPythonVersion": version,
            }
        ),
        encoding="utf-8",
    )
    (repo_root / "pyproject.toml").write_text(
        f'[project]\nname = "get-physics-done"\nversion = "{version}"\n',
        encoding="utf-8",
    )
    gpd_root = repo_root / "src" / "gpd"
    for subdir in ("commands", "agents", "hooks", "specs"):
        (gpd_root / subdir).mkdir(parents=True, exist_ok=True)
    return repo_root


class _ExecutionSnapshot(SimpleNamespace):
    def model_dump(self, mode: str = "json") -> dict[str, object]:
        return dict(self.__dict__)

    def __getattr__(self, name: str) -> object:
        return None


# ─── version & help ─────────────────────────────────────────────────────────


def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "gpd" in result.output


def test_version_subcommand():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "gpd" in result.output


def test_version_subcommand_prefers_checkout_version(tmp_path: Path):
    checkout = _make_checkout(tmp_path, "9.9.9")

    result = runner.invoke(app, ["--cwd", str(checkout), "version"])

    assert result.exit_code == 0
    assert "9.9.9" in result.output


def test_raw_version_option_outputs_json():
    result = runner.invoke(app, ["--raw", "--version"])
    assert result.exit_code == 0
    assert json.loads(result.output)["result"].startswith("gpd ")


def test_raw_version_subcommand_outputs_json():
    result = runner.invoke(app, ["--raw", "version"])
    assert result.exit_code == 0
    assert json.loads(result.output)["result"].startswith("gpd ")


def test_entrypoint_reexecs_from_checkout_when_running_outside_checkout(tmp_path: Path, monkeypatch) -> None:
    checkout = _make_checkout(tmp_path, "9.9.9")
    venv_python_rel = Path("Scripts") / "python.exe" if os.name == "nt" else Path("bin") / "python"
    checkout_python = checkout / ".venv" / venv_python_rel
    checkout_python.parent.mkdir(parents=True)
    checkout_python.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    managed_cli = tmp_path / "managed" / "site-packages" / "gpd" / "cli.py"
    managed_cli.parent.mkdir(parents=True, exist_ok=True)
    managed_cli.write_text("# managed copy placeholder\n", encoding="utf-8")

    monkeypatch.chdir(checkout)
    monkeypatch.setattr(cli_module, "__file__", str(managed_cli))
    monkeypatch.setattr(cli_module.sys, "argv", ["gpd", "version"])

    captured: dict[str, object] = {}

    def fake_execve(executable: str, argv: list[str], env: dict[str, str]) -> None:
        captured["executable"] = executable
        captured["argv"] = argv
        captured["env"] = env
        raise SystemExit(0)

    monkeypatch.setattr(cli_module.os, "execve", fake_execve)

    with patch.object(cli_module, "app", side_effect=AssertionError("entrypoint should re-exec before running app")):
        with patch.dict(os.environ, {}, clear=True):
            try:
                cli_module.entrypoint()
            except SystemExit as exc:
                assert exc.code == 0

    assert captured["executable"] == str(checkout_python)
    assert captured["argv"] == [str(checkout_python), "-m", "gpd.cli", "version"]
    env = captured["env"]
    assert isinstance(env, dict)
    assert env["GPD_DISABLE_CHECKOUT_REEXEC"] == "1"
    assert env["PYTHONPATH"].split(os.pathsep)[0] == str(checkout / "src")


def test_help_surfaces_core_and_auxiliary_commands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "observe" in result.output
    assert "state" in result.output
    assert "phase" in result.output
    assert "health" in result.output
    assert "paper-build" in result.output
    assert "doctor" in result.output
    assert "Check GPD installation and environment health" in result.output
    assert "inspect runtime readiness" in result.output
    assert "install" in result.output
    assert "Install GPD skills, agents, and hooks into runtime" in result.output
    assert "uninstall" in result.output
    assert "Remove GPD skills, agents, and hooks from runtime" in result.output
    assert "init" in result.output
    assert "validate" in result.output
    assert "readiness" in result.output
    assert "observability" in result.output
    normalized_output = _normalize_cli_output(result.output)
    assert "permissions" in normalized_output
    assert "Runtime permission readiness and sync" in normalized_output
    assert "gpd doctor" in normalized_output
    assert local_cli_unattended_readiness_command() in normalized_output
    assert local_cli_permissions_status_command() in normalized_output
    assert local_cli_permissions_sync_command() in normalized_output
    assert "gpd observe execution" in normalized_output

    assert local_cli_resume_recent_command() in normalized_output
    assert local_cli_install_local_example_command() in normalized_output
    assert local_cli_doctor_local_command() in normalized_output
    assert local_cli_validate_command_context_command() in normalized_output

    for command in local_cli_bridge_commands():
        assert command in normalized_output
    assert "presets" in normalized_output
    assert "Workflow presets for local CLI preview" in normalized_output
    assert "application" in normalized_output
    assert "integrations" in normalized_output
    assert "Optional shared capability integrations" in normalized_output


def test_install_help_uses_public_surface_examples() -> None:
    result = runner.invoke(app, ["install", "--help"])

    assert result.exit_code == 0
    normalized_output = _normalize_cli_output(result.output)
    assert local_cli_install_local_example_command() in normalized_output
    assert "gpd install <runtime> # single runtime, local" not in normalized_output


def test_workflow_presets_help_surfaces_apply_command() -> None:
    result = runner.invoke(app, ["presets", "apply", "--help"])
    assert result.exit_code == 0
    normalized_output = _normalize_cli_output(result.output)
    assert "--dry-run" in normalized_output
    assert "Show a diff-oriented preview without writing it" in normalized_output


def test_workflow_presets_surface_lists_catalog() -> None:
    result = runner.invoke(app, ["presets", "list"])
    assert result.exit_code == 0
    assert "Workflow Presets" in result.output
    assert "core-research" in result.output
    assert "Core research" in result.output


def test_integrations_status_reports_effective_project_local_state_and_plan_readiness(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / "GPD").mkdir()

    result = runner.invoke(app, ["--cwd", str(project_root), "--raw", "integrations", "status", "wolfram"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["integration"] == "wolfram"
    assert payload["configured"] is False
    assert payload["enabled"] is True
    assert payload["ready"] is False
    assert payload["state"] == "missing-api-key"
    assert payload["scope"] == "project-local"
    assert payload["plan_readiness_command"] == local_cli_plan_preflight_command()
    assert payload["api_key_env"] == "GPD_WOLFRAM_MCP_API_KEY"
    assert "GPD_WOLFRAM_MCP_API_KEY" in payload["next_step"]
    assert "Mathematica" in payload["local_mathematica_note"]


def test_integrations_enable_and_disable_wolfram_persist_project_local_config(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / "GPD").mkdir()

    enable_result = runner.invoke(app, ["--cwd", str(project_root), "--raw", "integrations", "enable", "wolfram"])
    assert enable_result.exit_code == 0
    enable_payload = json.loads(enable_result.output)
    assert enable_payload["enabled"] is True
    assert enable_payload["scope"] == "project-local"

    config_path = project_root / "GPD" / "integrations.json"
    assert config_path.exists()
    saved = json.loads(config_path.read_text(encoding="utf-8"))
    assert saved["wolfram"]["enabled"] is True

    disable_result = runner.invoke(app, ["--cwd", str(project_root), "--raw", "integrations", "disable", "wolfram"])
    assert disable_result.exit_code == 0
    disable_payload = json.loads(disable_result.output)
    assert disable_payload["enabled"] is False

    status_result = runner.invoke(app, ["--cwd", str(project_root), "--raw", "integrations", "status", "wolfram"])
    assert status_result.exit_code == 0
    status_payload = json.loads(status_result.output)
    assert status_payload["enabled"] is False
    assert status_payload["state"] == "disabled"


@pytest.mark.parametrize("command", ("status", "enable", "disable"))
def test_integrations_commands_fail_outside_real_project(tmp_path: Path, command: str) -> None:
    result = runner.invoke(app, ["--cwd", str(tmp_path), "--raw", "integrations", command, "wolfram"])

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert "real GPD project root" in payload["error"]
    assert not (tmp_path / "GPD").exists()


def test_integrations_commands_use_project_root_config_from_nested_workspace(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    nested_workspace = project_root / "notes" / "scratch"
    nested_workspace.mkdir(parents=True)
    config_path = project_root / "GPD" / "integrations.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text('{"wolfram":{"enabled":false}}', encoding="utf-8")

    status_result = runner.invoke(app, ["--cwd", str(nested_workspace), "--raw", "integrations", "status", "wolfram"])

    assert status_result.exit_code == 0
    status_payload = json.loads(status_result.output)
    assert status_payload["enabled"] is False
    assert status_payload["config_path"] == str(config_path)

    enable_result = runner.invoke(app, ["--cwd", str(nested_workspace), "--raw", "integrations", "enable", "wolfram"])

    assert enable_result.exit_code == 0
    saved = json.loads(config_path.read_text(encoding="utf-8"))
    assert saved["wolfram"]["enabled"] is True
    assert not (nested_workspace / "GPD").exists()


def test_integrations_status_rejects_legacy_api_key_env_field(tmp_path: Path) -> None:
    config_path = tmp_path / "GPD" / "integrations.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        '{"wolfram":{"enabled":true,"api_key_env":"WOLFRAM_MCP_SERVICE_API_KEY"}}',
        encoding="utf-8",
    )

    result = runner.invoke(app, ["--cwd", str(tmp_path), "--raw", "integrations", "status", "wolfram"])

    assert result.exit_code != 0
    assert "integrations.wolfram contains unsupported keys: api_key_env" in _normalize_cli_output(result.output)


@pytest.mark.parametrize(
    ("raw_config", "expected_error"),
    (
        ('{"wolfram":{"enabled":"yes"}}', "integrations.wolfram.enabled must be a boolean"),
        ('{"wolfram":[\n', "Malformed integrations config:"),
    ),
)
def test_integrations_status_fails_closed_for_invalid_project_config(
    tmp_path: Path,
    raw_config: str,
    expected_error: str,
) -> None:
    config_path = tmp_path / "GPD" / "integrations.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(raw_config, encoding="utf-8")

    result = runner.invoke(app, ["--cwd", str(tmp_path), "--raw", "integrations", "status", "wolfram"])

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert expected_error in payload["error"]


@pytest.mark.parametrize("command", ("enable", "disable"))
def test_integrations_toggle_fails_closed_for_invalid_project_config(tmp_path: Path, command: str) -> None:
    config_path = tmp_path / "GPD" / "integrations.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text('{"wolfram":{"enabled":"yes"}}', encoding="utf-8")
    before = config_path.read_text(encoding="utf-8")

    result = runner.invoke(app, ["--cwd", str(tmp_path), "--raw", "integrations", command, "wolfram"])

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["error"] == "integrations.wolfram.enabled must be a boolean"
    assert config_path.read_text(encoding="utf-8") == before


def test_workflow_preset_show_raw_outputs_central_contract() -> None:
    result = runner.invoke(app, ["--raw", "presets", "show", "core-research"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["id"] == "core-research"
    assert payload["label"] == "Core research"
    assert payload["required_checks"] == []
    assert payload["recommended_config"]["model_profile"] == "review"
    assert payload["summary"] == "Balanced default workflow for planning, execution, and verification."


def test_workflow_preset_apply_dry_run_previews_changed_knobs(tmp_path: Path) -> None:
    config_dir = tmp_path / "GPD"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.json"
    original_config = {
        "autonomy": "supervised",
        "research_mode": "balanced",
        "model_profile": "review",
        "parallelization": False,
        "execution": {
            "review_cadence": "sparse",
            "checkpoint_after_n_tasks": 7,
            "checkpoint_before_downstream_dependent_tasks": False,
        },
        "planning": {"commit_docs": False},
        "workflow": {"research": False, "plan_checker": False, "verifier": False},
    }
    config_path.write_text(json.dumps(original_config), encoding="utf-8")

    result = runner.invoke(app, ["--cwd", str(tmp_path), "--raw", "presets", "apply", "core-research", "--dry-run"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["preset"] == "core-research"
    assert payload["label"] == "Core research"
    assert payload["dry_run"] is True
    assert payload["applied_keys"] == [
        "autonomy",
        "research_mode",
        "model_profile",
        "execution.review_cadence",
        "parallelization",
        "planning.commit_docs",
        "workflow.research",
        "workflow.plan_checker",
        "workflow.verifier",
    ]
    assert payload["changed_keys"] == [
        "autonomy",
        "execution.review_cadence",
        "parallelization",
        "planning.commit_docs",
        "workflow.research",
        "workflow.plan_checker",
        "workflow.verifier",
    ]
    assert payload["ignored_keys"] == ["model_cost_posture"]
    assert payload["unchanged_keys"] == ["research_mode", "model_profile"]
    assert payload["changes"] == [
        {"key": "autonomy", "before": "supervised", "after": "balanced"},
        {"key": "execution.review_cadence", "before": "sparse", "after": "adaptive"},
        {"key": "parallelization", "before": False, "after": True},
        {"key": "planning.commit_docs", "before": False, "after": True},
        {"key": "workflow.research", "before": False, "after": True},
        {"key": "workflow.plan_checker", "before": False, "after": True},
        {"key": "workflow.verifier", "before": False, "after": True},
    ]
    resulting_config = payload["resulting_config"]
    assert resulting_config["autonomy"] == "balanced"
    assert resulting_config["research_mode"] == "balanced"
    assert resulting_config["model_profile"] == "review"
    assert resulting_config["parallelization"] is True
    assert resulting_config["commit_docs"] is True
    assert resulting_config["execution"]["review_cadence"] == "adaptive"
    assert resulting_config["execution"]["checkpoint_after_n_tasks"] == 7
    assert resulting_config["execution"]["checkpoint_before_downstream_dependent_tasks"] is False
    assert resulting_config["research"] is True
    assert resulting_config["plan_checker"] is True
    assert resulting_config["verifier"] is True
    assert "planning" not in resulting_config
    assert "workflow" not in resulting_config
    assert json.loads(config_path.read_text(encoding="utf-8")) == original_config


def test_workflow_preset_apply_writes_merged_config(tmp_path: Path) -> None:
    config_dir = tmp_path / "GPD"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "autonomy": "supervised",
                "research_mode": "adaptive",
                "model_profile": "review",
                "parallelization": False,
                "execution": {
                    "review_cadence": "dense",
                    "checkpoint_after_n_tasks": 11,
                },
                "workflow": {"research": False, "plan_checker": False, "verifier": False},
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["--cwd", str(tmp_path), "--raw", "presets", "apply", "publication-manuscript"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["preset"] == "publication-manuscript"
    assert payload["dry_run"] is False
    assert payload["updated"] is True
    assert payload["ignored_keys"] == ["model_cost_posture"]
    assert payload["applied_keys"] == [
        "autonomy",
        "research_mode",
        "model_profile",
        "execution.review_cadence",
        "parallelization",
        "planning.commit_docs",
        "workflow.research",
        "workflow.plan_checker",
        "workflow.verifier",
    ]
    assert payload["changed_keys"] == [
        "autonomy",
        "research_mode",
        "model_profile",
        "workflow.research",
        "workflow.plan_checker",
        "workflow.verifier",
    ]
    assert payload["unchanged_keys"] == [
        "execution.review_cadence",
        "parallelization",
        "planning.commit_docs",
    ]

    written = json.loads(config_path.read_text(encoding="utf-8"))
    assert written["autonomy"] == "balanced"
    assert written["research_mode"] == "exploit"
    assert written["model_profile"] == "paper-writing"
    assert written["parallelization"] is False
    assert written["commit_docs"] is True
    assert written["execution"]["review_cadence"] == "dense"
    assert written["execution"]["checkpoint_after_n_tasks"] == 11
    assert written["research"] is True
    assert written["plan_checker"] is True
    assert written["verifier"] is True
    assert "planning" not in written
    assert "workflow" not in written


def _sample_cost_summary(workspace: Path) -> CostSummary:
    workspace_text = str(workspace)
    project = CostProjectSummary(
        project_root=workspace_text,
        record_count=2,
        usage_status="measured",
        cost_status="unavailable",
        interpretation="tokens measured; USD unavailable",
        input_tokens=1200,
        output_tokens=300,
        total_tokens=1500,
        cost_usd=None,
        last_recorded_at="2026-03-27T00:00:00+00:00",
        runtimes=[_COST_TEST_RUNTIME],
        models=[_COST_TEST_MODEL],
    )
    current_session = CostSessionSummary(
        session_id="session-123",
        project_root=workspace_text,
        record_count=1,
        usage_status="measured",
        cost_status="unavailable",
        interpretation="tokens measured; USD unavailable",
        input_tokens=800,
        output_tokens=200,
        total_tokens=1000,
        cost_usd=None,
        last_recorded_at="2026-03-27T00:00:00+00:00",
        runtimes=[_COST_TEST_RUNTIME],
        models=[_COST_TEST_MODEL],
    )
    return CostSummary(
        project_root=workspace_text,
        active_runtime=_COST_TEST_RUNTIME,
        active_runtime_capabilities={
            "permissions_surface": "config-file",
            "statusline_surface": "none",
            "notify_surface": "explicit",
            "telemetry_source": "notify-hook",
            "telemetry_completeness": "best-effort",
        },
        model_profile="review",
        runtime_model_selection="runtime defaults",
        profile_tier_mix=_profile_tier_mix("review"),
        current_session_id="session-123",
        project=project,
        current_session=current_session,
        recent_sessions=[current_session],
        budget_thresholds=[
            CostBudgetThresholdSummary(
                scope="project",
                config_key="project_usd_budget",
                budget_usd=1.0,
                spent_usd=0.85,
                remaining_usd=0.15,
                percent_used=85.0,
                cost_status="measured",
                comparison_exact=True,
                state="near_budget",
                message=(
                    "Configured project USD budget is nearing budget based on measured local USD telemetry; "
                    "it stays advisory only and never stops work automatically."
                ),
            )
        ],
        guidance=[
            f"Current model posture: profile `review` with {_COST_TEST_RUNTIME} runtime defaults. Use `gpd:set-tier-models` to pin explicit tier-1, tier-2, and tier-3 model IDs.",
        ],
    )


def _assert_cost_posture_semantics(output: str) -> None:
    assert _COST_TEST_RUNTIME in output
    assert "review" in output
    assert "runtime defaults" in output
    assert "tier-1=13, tier-2=10, tier-3=1" in output
    assert "Advisory only; counts profile-to-tier assignments" in output
    assert "set-tier-models" in output


def test_cost_help_surfaces_machine_local_advisory_role() -> None:
    result = runner.invoke(app, ["cost", "--help"])
    assert result.exit_code == 0
    normalized_output = _normalize_cli_output(result.output)
    assert "Show machine-local usage and cost summaries" in normalized_output
    assert "--last-sessions" in normalized_output
    assert "Show the most recent N recorded usage" in normalized_output
    assert "[default: 5]" in normalized_output


def test_cost_raw_outputs_summary_payload(tmp_path: Path) -> None:
    summary = _sample_cost_summary(tmp_path)

    with patch("gpd.core.costs.build_cost_summary", return_value=summary) as mock_build:
        result = runner.invoke(app, ["--cwd", str(tmp_path), "--raw", "cost", "--last-sessions", "2"])

    assert result.exit_code == 0
    mock_build.assert_called_once_with(tmp_path, last_sessions=2)
    payload = json.loads(result.output)
    assert payload["project_root"] == str(tmp_path)
    assert "workspace_root" not in payload
    assert payload["active_runtime"] == _COST_TEST_RUNTIME
    assert payload["active_runtime_capabilities"]["telemetry_completeness"] == "best-effort"
    assert payload["active_runtime_capabilities"]["telemetry_source"] == "notify-hook"
    assert payload["model_profile"] == "review"
    assert payload["runtime_model_selection"] == "runtime defaults"
    assert payload["profile_tier_mix"] == _profile_tier_mix("review")
    assert payload["profile_tier_mix_interpretation"].startswith("Advisory only; counts profile-to-tier assignments")
    assert payload["budget_thresholds"][0]["scope"] == "project"
    assert payload["budget_thresholds"][0]["config_key"] == "project_usd_budget"
    assert payload["budget_thresholds"][0]["advisory_only"] is True
    assert payload["budget_thresholds"][0]["comparison_exact"] is True
    assert payload["budget_thresholds"][0]["state"] == "near_budget"
    assert "nearing budget" in payload["budget_thresholds"][0]["message"]
    assert payload["advisory"]["state"] == "near_budget"
    assert payload["advisory"]["scope"] == "project"
    assert payload["advisory"]["next_action"] == "Run `gpd cost` for the local usage/cost summary and any USD budget warnings."
    assert payload["project"]["usage_status"] == "measured"
    assert payload["project"]["cost_status"] == "unavailable"
    assert payload["project"]["interpretation"] == "tokens measured; USD unavailable"
    assert payload["project"]["total_tokens"] == 1500
    assert payload["project"]["cost_usd"] is None
    assert payload["recent_sessions"][0]["session_id"] == "session-123"
    assert payload["recent_sessions"][0]["total_tokens"] == 1000

def test_cost_human_output_stays_read_only_and_advisory(tmp_path: Path) -> None:
    summary = _sample_cost_summary(tmp_path)

    with patch("gpd.core.costs.build_cost_summary", return_value=summary):
        result = runner.invoke(app, ["--cwd", str(tmp_path), "cost", "--last-sessions", "1"])

    assert result.exit_code == 0
    assert "Cost Summary" in result.output
    assert "Read-only machine-local usage/cost summary." in result.output
    assert "clearly labels estimates or unavailable values" in result.output
    assert "best-effort via notify-hook" in result.output
    assert "Scope" in result.output
    assert "Used" in result.output
    assert "85.00%" in result.output
    assert "Configured project USD budget is nearing budget" in result.output
    assert "Pricing snapshot" in result.output
    assert "not configured" in result.output
    assert "Current project" in result.output
    assert "Recent sessions" in result.output
    assert "Interpretation" in result.output
    assert "tokens measured; USD unavailable" in result.output
    assert "Measured tokens are available, but no pricing snapshot is configured" not in result.output
    _assert_cost_posture_semantics(result.output)


def test_permissions_status_raw_includes_runtime_capabilities(tmp_path: Path) -> None:
    runtime = _LAUNCH_WRAPPER_RUNTIME
    target_dir = runtime_target_dir(tmp_path, runtime)
    with (
        patch("gpd.cli._resolve_permissions_runtime_name", return_value=runtime),
        patch("gpd.cli._resolve_permissions_target_dir", return_value=target_dir),
        patch("gpd.cli._resolve_permissions_autonomy", return_value="yolo"),
        patch(
            "gpd.adapters.get_adapter",
            return_value=MagicMock(
                runtime_permissions_status=MagicMock(
                    return_value={
                        "runtime": runtime,
                        "desired_mode": "yolo",
                        "configured_mode": "launch-wrapper",
                        "config_aligned": True,
                        "requires_relaunch": True,
                        "managed_by_gpd": True,
                        "message": f"{runtime_display_name(runtime)} only supports yolo at launch time.",
                        "next_step": None,
                    }
                )
            ),
        ),
    ):
        result = runner.invoke(
            app,
            ["--raw", "permissions", "status", "--runtime", runtime, "--autonomy", "yolo"],
        )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["readiness"] == "relaunch-required"
    assert payload["capabilities"]["permissions_surface"] == "launch-wrapper"
    assert payload["capabilities"]["statusline_surface"] == "explicit"
    assert payload["capabilities"]["telemetry_completeness"] == "none"


def test_observe_help_surfaces_read_only_execution_snapshot_command() -> None:
    result = runner.invoke(app, ["observe", "execution", "--help"])
    assert result.exit_code == 0
    assert "Show the current local execution status without modifying project state." in result.output


def test_doctor_help_surfaces_runtime_readiness_mode() -> None:
    result = runner.invoke(app, ["doctor", "--help"])
    normalized_output = _normalize_cli_output(result.output)
    assert result.exit_code == 0
    assert "Check GPD installation and environment health" in normalized_output
    assert "inspect runtime readiness" in normalized_output
    assert "--live-executable-probes" in normalized_output
    assert "--runtime" in normalized_output
    assert "--local" in normalized_output
    assert "--global" in normalized_output
    assert "--target-dir" in normalized_output


def test_permissions_help_surfaces_status_and_sync_roles() -> None:
    result = runner.invoke(app, ["permissions", "--help"])
    assert result.exit_code == 0
    assert "Runtime permission readiness and sync" in result.output
    assert "status" in result.output
    assert "ready for unattended use" in result.output
    assert "sync" in result.output
    assert "active runtime's `settings` command" in result.output


def test_permissions_status_help_surfaces_readiness_options() -> None:
    result = runner.invoke(app, ["permissions", "status", "--help"])
    normalized_output = _normalize_cli_output(result.output)
    assert result.exit_code == 0
    assert "ready for unattended use" in normalized_output
    assert "requested autonomy" in normalized_output
    assert "--runtime" in normalized_output
    assert "--autonomy" in normalized_output
    assert "--target-dir" in normalized_output


def test_permissions_sync_help_surfaces_guided_runtime_changes() -> None:
    result = runner.invoke(app, ["permissions", "sync", "--help"])
    normalized_output = _normalize_cli_output(result.output)
    assert result.exit_code == 0
    assert "persist runtime-owned permission settings" in normalized_output
    assert "active runtime's `settings` command" in normalized_output
    assert "--runtime" in normalized_output
    assert "--autonomy" in normalized_output
    assert "--target-dir" in normalized_output


def test_active_runtime_settings_command_falls_back_to_runtime_neutral_reference(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("gpd.hooks.runtime_detect.detect_runtime_for_gpd_use", lambda cwd=None: None)

    assert cli_module._active_runtime_settings_command(cwd=Path("/tmp")) == "the active runtime's `settings` command"


def test_permissions_runtime_resolution_prefers_installed_runtime_selector_when_requested(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = Path("/tmp/permissions-runtime-resolution")

    monkeypatch.setattr(cli_module, "_get_cwd", lambda: workspace)
    monkeypatch.setattr(
        "gpd.hooks.runtime_detect.detect_active_runtime",
        lambda cwd=None: (_ for _ in ()).throw(AssertionError("active runtime selector should not be used")),
    )
    monkeypatch.setattr(
        "gpd.hooks.runtime_detect.detect_runtime_for_gpd_use",
        lambda cwd=None: FOREIGN_RUNTIME,
    )

    resolved = cli_module._resolve_permissions_runtime_name(
        None,
        prefer_installed_runtime=True,
    )

    assert resolved == FOREIGN_RUNTIME


def test_permissions_status_surfaces_runtime_capabilities_and_config_scope() -> None:
    runtime = _CONFIG_FILE_RUNTIME
    target_dir = runtime_target_dir(Path("/tmp"), runtime)

    class _DummyAdapter:
        def runtime_permissions_status(self, target_dir: Path, *, autonomy: str) -> dict[str, object]:
            return {
                "runtime": runtime,
                "desired_mode": "default",
                "configured_mode": "on-request/workspace-write",
                "config_aligned": True,
                "requires_relaunch": False,
                "managed_by_gpd": False,
                "approval_policy": "on-request",
                "sandbox_mode": "workspace-write",
                "message": f"{runtime_display_name(runtime)} is using its normal approval and sandbox defaults.",
            }

    with (
        patch("gpd.cli._resolve_permissions_runtime_name", return_value=runtime),
        patch("gpd.cli._resolve_permissions_target_dir", return_value=target_dir),
        patch("gpd.cli._resolve_permissions_autonomy", return_value="balanced"),
        patch("gpd.adapters.get_adapter", return_value=_DummyAdapter()),
    ):
        result = runner.invoke(app, ["--raw", "permissions", "status", "--runtime", runtime, "--autonomy", "balanced"])

    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert parsed["capabilities"]["contract_source"] == "runtime-catalog"
    assert parsed["capabilities"]["permissions_surface"] == "config-file"
    assert parsed["requested_surface"] == "ordinary-unattended"
    assert parsed["status_scope"] == "config-only"
    assert parsed["current_session_verified"] is False
    assert parsed["more_permissive_than_requested"] is False
    assert parsed["readiness"] == "ready"


def test_permissions_status_marks_known_more_permissive_runtime_not_ready() -> None:
    runtime = _CONFIG_FILE_RUNTIME
    target_dir = runtime_target_dir(Path("/tmp"), runtime)

    class _DummyAdapter:
        def runtime_permissions_status(self, target_dir: Path, *, autonomy: str) -> dict[str, object]:
            return {
                "runtime": runtime,
                "desired_mode": "default",
                "configured_mode": _CONFIG_FILE_PROMPT_FREE_MODE,
                "config_aligned": True,
                "requires_relaunch": False,
                "managed_by_gpd": False,
                "message": (
                    f"Runtime is still configured for {_CONFIG_FILE_PROMPT_FREE_MODE}, "
                    "but GPD left it untouched because that setting was not created by a prior GPD yolo sync."
                ),
            }

    with (
        patch("gpd.cli._resolve_permissions_runtime_name", return_value=runtime),
        patch("gpd.cli._resolve_permissions_target_dir", return_value=target_dir),
        patch("gpd.cli._resolve_permissions_autonomy", return_value="balanced"),
        patch("gpd.adapters.get_adapter", return_value=_DummyAdapter()),
    ):
        result = runner.invoke(
            app,
            ["--raw", "permissions", "status", "--runtime", runtime, "--autonomy", "balanced"],
        )

    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert parsed["capabilities"]["permissions_surface"] == "config-file"
    assert parsed["more_permissive_than_requested"] is True
    assert parsed["readiness"] == "not-ready"
    assert parsed["ready"] is False
    assert parsed["readiness_message"] == (
        "Runtime permissions are more permissive than the requested autonomy, so unattended readiness is not confirmed."
    )


def test_runtime_permissions_sync_payload_surfaces_launch_wrapper_scope() -> None:
    runtime = _LAUNCH_WRAPPER_RUNTIME
    target_dir = runtime_target_dir(Path("/tmp"), runtime)

    class _DummyAdapter:
        def sync_runtime_permissions(self, target_dir: Path, *, autonomy: str) -> dict[str, object]:
            return {
                "runtime": runtime,
                "desired_mode": "yolo",
                "configured_mode": "launch-wrapper",
                "config_aligned": True,
                "requires_relaunch": True,
                "managed_by_gpd": True,
                "launch_command": str(target_dir / "get-physics-done" / "bin" / f"{runtime}-gpd-yolo"),
                "message": f"{runtime_display_name(runtime)} only supports yolo at launch time. The GPD launcher is ready for the next session.",
            }

    with (
        patch("gpd.cli._resolve_permissions_runtime_name", return_value=runtime),
        patch("gpd.cli._resolve_permissions_target_dir", return_value=target_dir),
        patch("gpd.cli._resolve_permissions_autonomy", return_value="yolo"),
        patch("gpd.adapters.get_adapter", return_value=_DummyAdapter()),
    ):
        payload = cli_module._runtime_permissions_payload(
            runtime=runtime,
            autonomy="yolo",
            target_dir=None,
            apply_sync=True,
            strict=True,
        )

    assert payload["capabilities"]["contract_source"] == "runtime-catalog"
    assert payload["capabilities"]["permissions_surface"] == "launch-wrapper"
    assert payload["requested_surface"] == "prompt-free"
    assert payload["status_scope"] == "next-launch"
    assert payload["current_session_verified"] is False


def _write_install_manifest(config_dir: Path, *, runtime: str, install_scope: str = "local", raw: str | None = None) -> None:
    config_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = config_dir / "gpd-file-manifest.json"
    if raw is not None:
        manifest_path.write_text(raw, encoding="utf-8")
        return
    manifest_path.write_text(
        json.dumps(
            {
                "runtime": runtime,
                "install_scope": install_scope,
            }
        ),
        encoding="utf-8",
    )


class _PermissionsTargetAdapter:
    def __init__(
        self,
        *,
        local_target: Path,
        global_target: Path,
        missing_install_artifacts: tuple[str, ...] = (),
    ) -> None:
        self.runtime_name = PRIMARY_RUNTIME
        self.display_name = runtime_display_name(PRIMARY_RUNTIME)
        self._local_target = local_target
        self._global_target = global_target
        self._missing_install_artifacts = missing_install_artifacts

    def resolve_target_dir(self, is_global: bool, cwd: Path) -> Path:
        return self._global_target if is_global else self._local_target

    def validate_target_runtime(self, target_dir: Path, *, action: str) -> None:
        return None

    def missing_install_artifacts(self, target_dir: Path) -> tuple[str, ...]:
        if target_dir == self._local_target:
            return self._missing_install_artifacts
        return ()

    def runtime_permissions_status(self, target_dir: Path, *, autonomy: str) -> dict[str, object]:
        return {
            "runtime": self.runtime_name,
            "desired_mode": autonomy,
            "configured_mode": "default",
            "config_aligned": True,
            "requires_relaunch": False,
            "managed_by_gpd": False,
            "message": "configured",
        }

    def sync_runtime_permissions(self, target_dir: Path, *, autonomy: str) -> dict[str, object]:
        return self.runtime_permissions_status(target_dir, autonomy=autonomy)


def test_permissions_status_reports_incomplete_owned_install_instead_of_generic_missing(
    tmp_path: Path,
) -> None:
    local_target = runtime_target_dir(tmp_path, PRIMARY_RUNTIME)
    global_target = tmp_path / f"{runtime_config_dir_name(PRIMARY_RUNTIME)}-global"
    _write_install_manifest(local_target, runtime=PRIMARY_RUNTIME)
    global_target.mkdir(parents=True, exist_ok=True)
    adapter = _PermissionsTargetAdapter(
        local_target=local_target,
        global_target=global_target,
        missing_install_artifacts=("agents/gpd-help/SKILL.md",),
    )

    with (
        patch("gpd.cli._resolve_permissions_runtime_name", return_value=PRIMARY_RUNTIME),
        patch("gpd.cli._resolve_permissions_autonomy", return_value="balanced"),
        patch("gpd.hooks.runtime_detect.detect_runtime_install_target", return_value=None),
        patch("gpd.hooks.runtime_detect.detect_install_scope", return_value=None),
        patch("gpd.adapters.get_adapter", return_value=adapter),
    ):
        result = runner.invoke(app, ["--raw", "permissions", "status", "--runtime", PRIMARY_RUNTIME, "--autonomy", "balanced"])

    assert result.exit_code == 1
    parsed = json.loads(result.output)
    assert "incomplete GPD install" in parsed["error"]
    assert "Missing artifacts:" in parsed["error"]
    assert "No GPD install found" not in parsed["error"]


def test_permissions_status_reports_foreign_install_explicitly(tmp_path: Path) -> None:
    target = runtime_target_dir(tmp_path, PRIMARY_RUNTIME)
    _write_install_manifest(target, runtime=FOREIGN_RUNTIME)
    adapter = _PermissionsTargetAdapter(local_target=target, global_target=target)

    with (
        patch("gpd.cli._resolve_permissions_runtime_name", return_value=PRIMARY_RUNTIME),
        patch("gpd.cli._resolve_permissions_autonomy", return_value="balanced"),
        patch("gpd.adapters.get_adapter", return_value=adapter),
    ):
        result = runner.invoke(
            app,
            ["--raw", "permissions", "status", "--runtime", PRIMARY_RUNTIME, "--target-dir", str(target), "--autonomy", "balanced"],
        )

    assert result.exit_code == 1
    parsed = json.loads(result.output)
    assert f"belongs to runtime '{FOREIGN_RUNTIME}'" in parsed["error"]
    assert "No GPD install found" not in parsed["error"]


def test_permissions_sync_reports_untrusted_manifest_explicitly(tmp_path: Path) -> None:
    target = runtime_target_dir(tmp_path, PRIMARY_RUNTIME)
    _write_install_manifest(target, runtime=PRIMARY_RUNTIME, raw="{")
    adapter = _PermissionsTargetAdapter(local_target=target, global_target=target)

    with (
        patch("gpd.cli._resolve_permissions_runtime_name", return_value=PRIMARY_RUNTIME),
        patch("gpd.cli._resolve_permissions_autonomy", return_value="balanced"),
        patch("gpd.adapters.get_adapter", return_value=adapter),
    ):
        result = runner.invoke(
            app,
            ["--raw", "permissions", "sync", "--runtime", PRIMARY_RUNTIME, "--target-dir", str(target), "--autonomy", "balanced"],
        )

    assert result.exit_code == 1
    parsed = json.loads(result.output)
    assert "manifest state is 'corrupt'" in parsed["error"]
    assert "No GPD install found" not in parsed["error"]


def test_init_help_surfaces_local_onboarding_entrypoints() -> None:
    result = runner.invoke(app, ["init", "--help"])
    assert result.exit_code == 0
    assert "Assemble context for AI agent workflows" in result.output
    assert "new-project" in result.output
    assert "resume" in result.output
    assert "map-research" in result.output
    assert "verify-work" in result.output


def test_resume_help_surfaces_read_only_local_recovery_role() -> None:
    result = runner.invoke(app, ["resume", "--help"])
    assert result.exit_code == 0
    normalized = _normalize_cli_output(result.output)
    assert "--recent" in normalized
    assert "Summarize local recovery state or list machine-local recent projects." in normalized


def test_resume_recovery_advice_uses_resolved_runtime_commands(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        cli_module,
        "_resume_runtime_commands",
        lambda cwd=None: ("/gpd:resume-work", "/gpd:suggest-next"),
    )

    advice = cli_module._resume_recovery_advice(
        resume_payload={
            "resume_candidates": [
                {
                    "kind": "continuity_handoff",
                    "status": "handoff",
                    "resume_file": "GPD/phases/01/.continue-here.md",
                    "resumable": False,
                    "origin": "canonical_continuation",
                }
            ],
            "active_resume_kind": "continuity_handoff",
            "active_resume_origin": "canonical_continuation",
            "active_resume_pointer": "GPD/phases/01/.continue-here.md",
            "continuity_handoff_file": "GPD/phases/01/.continue-here.md",
        },
        recent_rows=[],
        cwd=Path("/tmp/runtime-advice"),
    )

    assert advice.continue_command == "/gpd:resume-work"
    assert advice.fast_next_command == "/gpd:suggest-next"
    assert advice.mode == "current-workspace"
    assert advice.primary_command == local_cli_resume_command()


def test_resume_recovery_advice_keeps_recent_projects_fallbacks_distinct(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli_module, "_resume_runtime_commands", lambda cwd=None: (None, None))

    advice = cli_module._resume_recovery_advice(
        recent_rows=[{"project_root": "/tmp/project-a", "available": True, "resumable": True}],
        force_recent=True,
        cwd=Path("/tmp/runtime-advice-fallback"),
    )

    assert advice.continue_command == "runtime `resume-work`"
    assert advice.fast_next_command == "runtime `suggest-next`"
    assert advice.mode == "recent-projects"
    assert advice.primary_command == local_cli_resume_recent_command()


def test_resume_runtime_commands_logs_runtime_resolution_failures(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    def _boom(*args, **kwargs):
        raise RuntimeError("runtime detection exploded")

    monkeypatch.setattr("gpd.hooks.runtime_detect.detect_runtime_for_gpd_use", _boom)

    with caplog.at_level(logging.WARNING, logger="gpd.cli"):
        commands = cli_module._resume_runtime_commands(cwd=Path("/tmp/runtime-advice"))

    assert commands == (None, None)
    assert any("Failed to resolve runtime-specific resume commands" in record.message for record in caplog.records)


def test_resume_origin_label_no_longer_exposes_legacy_session_alias() -> None:
    assert cli_module._resume_origin_label("legacy_session") == "Unknown"


def test_resume_recent_raw_surfaces_machine_local_recent_projects(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "home"
    recent_index_dir = home / ".gpd" / "recent-projects"
    recent_index_dir.mkdir(parents=True, exist_ok=True)

    resumable_root = tmp_path / "projects" / "alpha"
    resumable_root.mkdir(parents=True, exist_ok=True)
    (resumable_root / "GPD" / "phases" / "04").mkdir(parents=True, exist_ok=True)
    (resumable_root / "GPD" / "phases" / "04" / ".continue-here.md").write_text("resume\n", encoding="utf-8")
    unavailable_root = tmp_path / "projects" / "beta-missing"

    (recent_index_dir / "index.json").write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "project_root": str(unavailable_root),
                        "last_session_at": "2026-03-20T09:00:00+00:00",
                        "stopped_at": "Phase 2",
                        "resumable": False,
                    },
                    {
                        "project_root": str(resumable_root),
                        "last_session_at": "2026-03-21T10:30:00+00:00",
                        "stopped_at": "Phase 4",
                        "resume_file": "GPD/phases/04/.continue-here.md",
                        "resumable": True,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(cli_module.Path, "home", lambda: home)
    monkeypatch.delenv("GPD_DATA_DIR", raising=False)

    result = runner.invoke(app, ["--raw", "resume", "--recent"])
    parsed = json.loads(result.output)

    assert parsed["count"] == 2
    assert parsed["projects"][0]["project_root"] == resumable_root.as_posix()
    assert parsed["projects"][0]["resumable"] is True
    assert parsed["projects"][0]["status"] == "resumable"
    assert parsed["projects"][1]["project_root"] == unavailable_root.as_posix()
    assert parsed["projects"][1]["available"] is False
    assert parsed["projects"][1]["status"] == "unavailable"


def test_resume_recent_human_output_surfaces_command_and_missing_projects(
    tmp_path: Path, monkeypatch
) -> None:
    resumable_root = tmp_path / "projects" / "gamma"
    resumable_root.mkdir(parents=True, exist_ok=True)
    (resumable_root / "GPD" / "phases" / "04").mkdir(parents=True, exist_ok=True)
    (resumable_root / "GPD" / "phases" / "04" / ".continue-here.md").write_text("resume\n", encoding="utf-8")
    missing_root = tmp_path / "projects" / "delta-missing"
    monkeypatch.setattr(
        "gpd.core.recent_projects.list_recent_projects",
        lambda store_root=None, last=None: [
            {
                "project_root": str(resumable_root),
                "last_session_at": "2026-03-21T11:00:00+00:00",
                "stopped_at": "Phase 1",
                "resume_file": "GPD/phases/04/.continue-here.md",
                "resumable": True,
            },
            {
                "project_root": str(missing_root),
                "last_session_at": "2026-03-19T08:00:00+00:00",
                "stopped_at": "Phase 3",
                "resumable": False,
            },
        ],
    )

    result = runner.invoke(app, ["resume", "--recent"])

    assert result.exit_code == 0
    normalized = " ".join(result.output.split())
    assert "Recent Projects" in result.output
    assert "Next here" in result.output
    assert "Resume:" in result.output
    assert "gpd --cwd" in result.output
    assert "continue there with `resume-work`" in result.output
    assert "resume-work" in result.output
    assert "suggest-next" in result.output
    assert "Why shown: shown because it still has a usable handoff target" in result.output
    assert "ready to reopen" in result.output
    assert "Inspect:" not in result.output
    assert "inspect the selected workspace" not in normalized
    assert "project root missing" in result.output or "project unavailable on this machine" in result.output


def test_resume_recent_raw_downgrades_missing_handoff_rows_to_non_resumable(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "home"
    recent_index_dir = home / ".gpd" / "recent-projects"
    recent_index_dir.mkdir(parents=True, exist_ok=True)

    project_root = tmp_path / "projects" / "epsilon"
    project_root.mkdir(parents=True, exist_ok=True)

    (recent_index_dir / "index.json").write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "project_root": str(project_root),
                        "last_session_at": "2026-03-21T11:00:00+00:00",
                        "stopped_at": "Phase 1",
                        "resume_file": "GPD/phases/01/.continue-here.md",
                        "resumable": True,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(cli_module.Path, "home", lambda: home)
    monkeypatch.delenv("GPD_DATA_DIR", raising=False)

    result = runner.invoke(app, ["--raw", "resume", "--recent"])
    parsed = json.loads(result.output)

    assert parsed["count"] == 1
    assert parsed["projects"][0]["project_root"] == project_root.as_posix()
    assert parsed["projects"][0]["resume_file_available"] is False
    assert parsed["projects"][0]["resume_file_reason"] == "resume file missing"
    assert parsed["projects"][0]["resumable"] is False
    assert parsed["recovery_advice"]["resume_surface_schema_version"] == 1
    assert "compat_resume_surface" not in parsed["recovery_advice"]


def test_resume_plain_output_hints_recent_when_workspace_is_missing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "gpd.core.context.init_resume",
        lambda _cwd: {
            "planning_exists": False,
            "state_exists": False,
            "roadmap_exists": False,
            "project_exists": False,
            "segment_candidates": [],
            "has_live_execution": False,
            "resume_mode": None,
            "execution_resume_file": None,
            "execution_paused_at": None,
            "autonomy": None,
            "research_mode": None,
            "active_execution_segment": None,
        },
    )

    result = runner.invoke(app, ["resume"])

    assert result.exit_code == 0
    assert "No GPD planning directory" in result.output
    assert local_cli_resume_recent_command() in result.output


def test_resume_plain_output_surfaces_auto_selected_recent_project(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "outside"
    workspace.mkdir()
    project_root = tmp_path / "project"
    monkeypatch.chdir(workspace)
    monkeypatch.setattr(
        "gpd.core.context.init_resume",
        lambda _cwd: {
            "workspace_root": workspace.as_posix(),
            "project_root": project_root.as_posix(),
            "project_root_source": "recent_project",
            "project_root_auto_selected": True,
            "project_label": "Alpha project",
            "project_summary": "Working through the verification sweep",
            "project_reentry_mode": "auto-recent-project",
            "project_reentry_requires_selection": False,
            "project_reentry_candidates": [],
            "planning_exists": True,
            "state_exists": True,
            "roadmap_exists": True,
            "project_exists": True,
            "resume_candidates": [
                {
                    "kind": "bounded_segment",
                    "status": "paused",
                    "phase": "03",
                    "plan": "01",
                    "segment_id": "seg-3",
                    "resume_file": "GPD/phases/03/.continue-here.md",
                    "resumable": True,
                    "origin": "canonical_continuation",
                }
            ],
            "active_bounded_segment": {
                "phase": "03",
                "plan": "01",
                "segment_id": "seg-3",
                "segment_status": "waiting_review",
                "resume_file": "GPD/phases/03/.continue-here.md",
            },
            "derived_execution_head": {
                "phase": "03",
                "plan": "01",
                "segment_id": "seg-3",
                "segment_status": "waiting_review",
                "resume_file": "GPD/phases/03/.continue-here.md",
            },
            "active_resume_kind": "bounded_segment",
            "active_resume_origin": "canonical_continuation",
            "active_resume_pointer": "GPD/phases/03/.continue-here.md",
            "has_live_execution": True,
            "execution_resumable": True,
            "execution_paused_at": None,
            "autonomy": None,
            "research_mode": None,
        },
    )

    result = runner.invoke(app, ["resume"])

    assert result.exit_code == 0
    assert "Project" in result.output
    assert "Project label" in result.output
    assert "Project summary" in result.output
    assert "auto-selected recent project" in result.output
    assert "machine-local recent-project index" in result.output


def test_resume_plain_output_keeps_recent_project_selection_explicit_when_not_auto_selected(
    tmp_path: Path, monkeypatch
) -> None:
    workspace = tmp_path / "outside-explicit"
    workspace.mkdir()
    project_root = tmp_path / "project-explicit"
    monkeypatch.chdir(workspace)
    monkeypatch.setattr(
        "gpd.core.context.init_resume",
        lambda _cwd: {
            "workspace_root": workspace.as_posix(),
            "project_root": project_root.as_posix(),
            "project_root_source": "recent_project",
            "project_root_auto_selected": False,
            "project_reentry_mode": "ambiguous-recent-projects",
            "project_reentry_requires_selection": True,
            "project_reentry_candidates": [],
            "planning_exists": True,
            "state_exists": True,
            "roadmap_exists": True,
            "project_exists": True,
            "resume_candidates": [
                {
                    "kind": "bounded_segment",
                    "status": "paused",
                    "phase": "03",
                    "plan": "01",
                    "segment_id": "seg-3",
                    "resume_file": "GPD/phases/03/.continue-here.md",
                    "resumable": True,
                    "origin": "canonical_continuation",
                }
            ],
            "active_bounded_segment": {
                "phase": "03",
                "plan": "01",
                "segment_id": "seg-3",
                "segment_status": "waiting_review",
                "resume_file": "GPD/phases/03/.continue-here.md",
            },
            "active_resume_kind": "bounded_segment",
            "active_resume_origin": "canonical_continuation",
            "active_resume_pointer": "GPD/phases/03/.continue-here.md",
            "has_live_execution": True,
            "execution_resumable": True,
            "execution_paused_at": None,
            "autonomy": None,
            "research_mode": None,
        },
    )

    result = runner.invoke(app, ["resume"])

    assert result.exit_code == 0
    assert "Project" in result.output
    assert "auto-selected recent project" not in result.output
    assert "recent project selected explicitly" in result.output


def test_load_recent_projects_rows_returns_canonical_display_rows(tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / "recent-project"
    project_root.mkdir()

    canonical_row = SimpleNamespace(
        model_dump=lambda mode="json": {
            "schema_version": 1,
            "project_root": project_root.resolve(strict=False).as_posix(),
            "last_session_at": "2026-03-28T12:00:00+00:00",
            "last_seen_at": "2026-03-28T12:00:00+00:00",
            "stopped_at": "Phase 02",
            "resume_file": "GPD/phases/02/.continue-here.md",
            "resumable": True,
        }
    )
    monkeypatch.setattr("gpd.core.recent_projects.list_recent_projects", lambda store_root=None, last=None: [canonical_row])

    rows = cli_module._load_recent_projects_rows()

    assert len(rows) == 1
    assert rows[0]["project_root"] == project_root.resolve(strict=False).as_posix()
    assert rows[0]["last_session_at"] == "2026-03-28T12:00:00+00:00"
    assert rows[0]["last_seen_at"] == "2026-03-28T12:00:00+00:00"
    assert "workspace_root" not in rows[0]
    assert "cwd" not in rows[0]
    assert "path" not in rows[0]
    assert "state" not in rows[0]
    assert "can_resume" not in rows[0]
    assert "last_event_at" not in rows[0]


def test_load_recent_projects_rows_rejects_malformed_helper_rows(tmp_path: Path, monkeypatch) -> None:
    canonical_row = SimpleNamespace(
        model_dump=lambda mode="json": {
            "workspace_root": (tmp_path / "recent-project").resolve(strict=False).as_posix(),
            "cwd": (tmp_path / "recent-project").resolve(strict=False).as_posix(),
            "path": (tmp_path / "recent-project").resolve(strict=False).as_posix(),
            "resume_file": "GPD/phases/02/.continue-here.md",
            "can_resume": True,
            "last_event_at": "2026-03-28T12:00:00+00:00",
        }
    )
    monkeypatch.setattr("gpd.core.recent_projects.list_recent_projects", lambda store_root=None, last=None: [canonical_row])

    with pytest.raises(cli_module.GPDError, match="unexpected field"):
        cli_module._load_recent_projects_rows()


def test_load_recent_projects_rows_prefers_stronger_recovery_over_newer_weaker_target(
    tmp_path: Path,
    monkeypatch,
) -> None:
    stronger_root = tmp_path / "stronger-project"
    stronger_root.mkdir()
    (stronger_root / "GPD" / "phases" / "02").mkdir(parents=True)
    (stronger_root / "GPD" / "phases" / "02" / ".continue-here.md").write_text("resume", encoding="utf-8")

    weaker_root = tmp_path / "weaker-project"
    weaker_root.mkdir()
    (weaker_root / "NEXT.md").write_text("handoff", encoding="utf-8")

    stronger_row = SimpleNamespace(
        model_dump=lambda mode="json": {
            "schema_version": 1,
            "project_root": stronger_root.resolve(strict=False).as_posix(),
            "last_session_at": "2026-03-28T12:00:00+00:00",
            "last_seen_at": "2026-03-28T12:00:00+00:00",
            "resume_file": "GPD/phases/02/.continue-here.md",
            "resume_target_kind": "bounded_segment",
            "resume_target_recorded_at": "2026-03-28T12:05:00+00:00",
            "resumable": True,
        }
    )
    weaker_row = SimpleNamespace(
        model_dump=lambda mode="json": {
            "schema_version": 1,
            "project_root": weaker_root.resolve(strict=False).as_posix(),
            "last_session_at": "2026-03-29T12:00:00+00:00",
            "last_seen_at": "2026-03-29T12:00:00+00:00",
            "resume_file": "NEXT.md",
            "resume_target_kind": "handoff",
            "resume_target_recorded_at": "2026-03-29T12:05:00+00:00",
            "resumable": True,
        }
    )
    monkeypatch.setattr(
        "gpd.core.recent_projects.list_recent_projects",
        lambda store_root=None, last=None: [weaker_row, stronger_row],
    )

    rows = cli_module._load_recent_projects_rows()

    assert [Path(str(row["project_root"])).name for row in rows] == ["stronger-project", "weaker-project"]


def test_load_recent_projects_rows_matches_canonical_project_reentry_sorting(
    tmp_path: Path,
    monkeypatch,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    first_project = tmp_path / "recent-alpha"
    second_project = tmp_path / "recent-beta"
    for project in (first_project, second_project):
        handoff = project / "GPD" / "phases" / "01" / ".continue-here.md"
        handoff.parent.mkdir(parents=True, exist_ok=True)
        handoff.write_text("resume", encoding="utf-8")

    recent_rows = [
        {
            "schema_version": 1,
            "project_root": first_project.resolve(strict=False).as_posix(),
            "last_session_at": "2026-03-28T12:00:00+00:00",
            "source_recorded_at": "2026-03-29T12:00:00+00:00",
            "resume_file": "GPD/phases/01/.continue-here.md",
            "resumable": True,
        },
        {
            "schema_version": 1,
            "project_root": second_project.resolve(strict=False).as_posix(),
            "last_session_at": "2026-03-29T12:00:00+00:00",
            "source_recorded_at": "2026-03-28T12:00:00+00:00",
            "resume_file": "GPD/phases/01/.continue-here.md",
            "resumable": True,
        },
    ]
    monkeypatch.setattr(
        "gpd.core.recent_projects.list_recent_projects",
        lambda store_root=None, last=None: list(recent_rows),
    )

    cli_rows = cli_module._load_recent_projects_rows()
    canonical_rows = resolve_project_reentry(workspace, recent_rows=recent_rows).candidates

    assert [Path(str(row["project_root"])).name for row in cli_rows] == [
        Path(candidate.project_root).name for candidate in canonical_rows
    ]
    assert [Path(str(row["project_root"])).name for row in cli_rows] == ["recent-alpha", "recent-beta"]


def test_normalize_recent_project_row_preserves_non_directory_unavailability() -> None:
    project_root = Path("/tmp/not-a-project-file")
    row = {
        "schema_version": 1,
        "project_root": project_root.as_posix(),
        "available": False,
        "availability_reason": "project root is not a directory",
        "resumable": True,
    }

    normalized = cli_module._normalize_recent_project_row(row)

    assert normalized is not None
    assert normalized["available"] is False
    assert normalized["missing"] is True
    assert normalized["availability_reason"] == "project root is not a directory"
    assert normalized["resumable"] is False
    assert normalized["status"] == "unavailable"


def test_resume_recent_surfaces_recovery_error_annotation_when_introspection_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = tmp_path / "recent-error"
    handoff = project_root / "GPD" / "phases" / "01" / ".continue-here.md"
    handoff.parent.mkdir(parents=True, exist_ok=True)
    handoff.write_text("resume", encoding="utf-8")
    save_state_json(project_root, default_state_dict())

    recent_rows = [
        {
            "schema_version": 1,
            "project_root": project_root.resolve(strict=False).as_posix(),
            "last_session_at": "2026-03-28T12:00:00+00:00",
            "source_recorded_at": "2026-03-28T13:00:00+00:00",
            "resume_file": "GPD/phases/01/.continue-here.md",
            "resumable": True,
        }
    ]
    monkeypatch.setattr(
        "gpd.core.recent_projects.list_recent_projects",
        lambda store_root=None, last=None: list(recent_rows),
    )
    monkeypatch.setattr("gpd.core.context.init_resume", lambda _cwd: (_ for _ in ()).throw(RuntimeError("boom")))

    result = runner.invoke(app, ["--raw", "resume", "--recent"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    project = payload["projects"][0]
    assert project["recovery_status"] == "recovery-error"
    assert project["recovery_status_label"] == "Recovery error"
    assert project["recovery_error_type"] == "RuntimeError"
    assert project["recovery_error"] == "boom"
    assert "boom" in project["recovery_note"]


def test_resume_plain_output_surfaces_session_handoff_status(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "gpd.core.context.init_resume",
        lambda _cwd: {
            "planning_exists": True,
            "state_exists": True,
            "roadmap_exists": True,
            "project_exists": True,
            "resume_candidates": [
                {
                    "kind": "continuity_handoff",
                    "status": "handoff",
                    "resume_file": "GPD/phases/01/.continue-here.md",
                    "resumable": False,
                    "origin": "canonical_continuation",
                }
            ],
            "continuity_handoff_file": "GPD/phases/01/.continue-here.md",
            "active_resume_kind": "continuity_handoff",
            "active_resume_origin": "canonical_continuation",
            "active_resume_pointer": "GPD/phases/01/.continue-here.md",
            "has_live_execution": False,
            "execution_paused_at": None,
            "autonomy": None,
            "research_mode": None,
        },
    )

    result = runner.invoke(app, ["resume"])

    assert result.exit_code == 0
    normalized = " ".join(result.output.split())
    assert "A continuity handoff is available" in normalized
    assert "continuity_handoff" in result.output
    assert "no resumable bounded segment is currently active." in normalized
    assert "Recovery context is available, but no live bounded segment is currently resumable." not in result.output


def test_resume_candidate_rerun_anchor_uses_last_result_id() -> None:
    assert cli_module._resume_candidate_rerun_anchor({"last_result_id": "R-bridge-01"}) == "rerun anchor: R-bridge-01"


def test_resume_candidate_notes_prefers_hydrated_result_context() -> None:
    notes = cli_module._resume_candidate_notes(
        {
            "last_result_id": "R-bridge-01",
            "last_result": {
                "id": "R-bridge-01",
                "description": "Benchmark reproduction",
                "equation": "F = ma",
                "verified": True,
            },
        },
        active_execution=None,
        current_execution=None,
    )

    assert "Benchmark reproduction" in notes
    assert "R-bridge-01" in notes


def test_resume_candidate_origin_uses_canonical_user_facing_labels() -> None:
    origin, label = cli_module._resume_candidate_origin(
        {"source": "current_execution"},
        active_execution={"resume_file": "GPD/phases/02/.continue-here.md"},
        current_execution={"resume_file": "GPD/phases/02/alternate.md"},
    )

    assert origin == "canonical_continuation"
    assert label == "canonical continuation; current execution points at a different handoff file"


def test_resume_candidate_notes_use_canonical_continuation_wording_for_missing_handoff() -> None:
    notes = cli_module._resume_candidate_notes(
        {"kind": "continuity_handoff", "status": "missing"},
        active_execution=None,
        current_execution=None,
    )

    assert notes == "Recorded in canonical continuation state, but the handoff file is missing from this workspace."


def test_resume_plain_output_surfaces_hydrated_last_result_context(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    hydrated_result = {
        "id": "R-bridge-01",
        "description": "Benchmark reproduction",
        "equation": "F = ma",
        "verified": True,
    }
    monkeypatch.setattr(
        "gpd.core.context.init_resume",
        lambda _cwd: {
            "planning_exists": True,
            "state_exists": True,
            "roadmap_exists": True,
            "project_exists": True,
            "resume_candidates": [
                {
                    "kind": "continuity_handoff",
                    "status": "handoff",
                    "resume_file": "GPD/phases/01/.continue-here.md",
                    "resumable": False,
                    "origin": "canonical_continuation",
                    "last_result_id": "R-bridge-01",
                    "last_result": hydrated_result,
                }
            ],
            "active_resume_result": hydrated_result,
            "continuity_handoff_file": "GPD/phases/01/.continue-here.md",
            "active_resume_kind": "continuity_handoff",
            "active_resume_origin": "canonical_continuation",
            "active_resume_pointer": "GPD/phases/01/.continue-here.md",
            "has_live_execution": False,
            "execution_resumable": False,
            "execution_paused_at": None,
            "autonomy": None,
            "research_mode": None,
        },
    )

    result = runner.invoke(app, ["resume"])

    assert result.exit_code == 0
    normalized = " ".join(result.output.split())
    assert "Resume Summary" in result.output
    assert "Benchmark reproduction" in result.output
    assert "R-bridge-01" in result.output
    assert "A continuity handoff is available" in normalized


def test_resume_plain_output_surfaces_bounded_segment_status_from_canonical_resume_mode(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "gpd.core.context.init_resume",
        lambda _cwd: {
            "planning_exists": True,
            "state_exists": True,
            "roadmap_exists": True,
            "project_exists": True,
            "resume_candidates": [
                {
                    "kind": "bounded_segment",
                    "status": "paused",
                    "phase": "03",
                    "plan": "01",
                    "segment_id": "seg-4",
                    "resume_file": "GPD/phases/03/.continue-here.md",
                    "resumable": True,
                    "origin": "canonical_continuation",
                }
            ],
            "active_bounded_segment": {
                "phase": "03",
                "plan": "01",
                "segment_id": "seg-4",
                "segment_status": "waiting_review",
                "resume_file": "GPD/phases/03/.continue-here.md",
            },
            "active_resume_kind": "bounded_segment",
            "active_resume_origin": "canonical_continuation",
            "active_resume_pointer": "GPD/phases/03/.continue-here.md",
            "has_live_execution": True,
            "execution_resumable": True,
            "execution_paused_at": None,
            "autonomy": None,
            "research_mode": None,
        },
    )

    result = runner.invoke(app, ["resume"])

    assert result.exit_code == 0
    normalized = " ".join(result.output.split())
    assert "A bounded segment is resumable from the current workspace state." in normalized
    assert "resume-work" in result.output
    assert "suggest-next" in result.output


def test_resume_plain_output_surfaces_canonical_bounded_segment_without_live_snapshot(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "gpd.core.context.init_resume",
        lambda _cwd: {
            "planning_exists": True,
            "state_exists": True,
            "roadmap_exists": True,
            "project_exists": True,
            "resume_candidates": [
                {
                    "kind": "bounded_segment",
                    "status": "paused",
                    "phase": "06",
                    "plan": "01",
                    "segment_id": "seg-6",
                    "resume_file": "GPD/phases/06/.continue-here.md",
                    "resumable": True,
                    "origin": "canonical_continuation",
                }
            ],
            "active_bounded_segment": {
                "phase": "06",
                "plan": "01",
                "segment_id": "seg-6",
                "segment_status": "paused",
                "resume_file": "GPD/phases/06/.continue-here.md",
            },
            "active_resume_kind": "bounded_segment",
            "active_resume_origin": "canonical_continuation",
            "active_resume_pointer": "GPD/phases/06/.continue-here.md",
            "has_live_execution": False,
            "execution_resumable": True,
            "execution_paused_at": None,
            "autonomy": None,
            "research_mode": None,
        },
    )

    result = runner.invoke(app, ["resume"])

    assert result.exit_code == 0
    normalized = " ".join(result.output.split())
    assert "A bounded segment is resumable from the current workspace state." in normalized
    assert "resume-work" in result.output
    assert "suggest-next" in result.output


def test_resume_plain_output_surfaces_interrupted_agent_status_from_candidate(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "gpd.core.context.init_resume",
        lambda _cwd: {
            "planning_exists": True,
            "state_exists": True,
            "roadmap_exists": True,
            "project_exists": True,
            "resume_candidates": [
                {
                    "kind": "interrupted_agent",
                    "status": "interrupted",
                    "agent_id": "agent-123",
                    "origin": "interrupted_agent",
                }
            ],
            "has_interrupted_agent": True,
            "has_live_execution": False,
            "execution_paused_at": None,
            "autonomy": None,
            "research_mode": None,
        },
    )

    result = runner.invoke(app, ["resume"])

    assert result.exit_code == 0
    normalized = " ".join(result.output.split())
    assert "An interrupted agent marker is present, but no bounded resume segment is active." in normalized


def test_resume_plain_output_surfaces_machine_change_as_advisory_status(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "gpd.core.context.init_resume",
        lambda _cwd: {
            "planning_exists": True,
            "state_exists": True,
            "roadmap_exists": True,
            "project_exists": True,
            "resume_candidates": [],
            "has_live_execution": False,
            "execution_paused_at": None,
            "autonomy": None,
            "research_mode": None,
            "machine_change_notice": (
                "Machine change detected: last active on old-host (Linux 5.15 x86_64); "
                "current machine new-host (Linux 6.1 x86_64). The project state is portable and does not require repair. "
                "Rerun the installer if runtime-local config may be stale on this machine."
            ),
        },
    )

    result = runner.invoke(app, ["resume"])

    assert result.exit_code == 0
    normalized = " ".join(result.output.split())
    assert "A machine change was detected" in normalized
    assert "the project state is portable and does not require repair." in normalized
    assert "Rerun the installer" in normalized
    assert "resume-work" not in result.output
    assert "suggest-next" not in result.output
    assert "No recent local recovery target is currently recorded." not in result.output


def test_resume_plain_output_keeps_machine_change_notice_when_session_handoff_is_primary(
    tmp_path: Path, monkeypatch
) -> None:
    # Compatibility-only guard: this still exercises the legacy session mirror while the public surface ages out.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "gpd.core.context.init_resume",
        lambda _cwd: {
            "planning_exists": True,
            "state_exists": True,
            "roadmap_exists": True,
            "project_exists": True,
            "resume_candidates": [
                {
                    "kind": "continuity_handoff",
                    "source": "session_resume_file",
                    "status": "handoff",
                    "resume_file": "GPD/phases/04/.continue-here.md",
                    "resumable": False,
                    "origin": "canonical_continuation",
                }
            ],
            "continuity_handoff_file": "GPD/phases/04/.continue-here.md",
            "active_resume_kind": "continuity_handoff",
            "active_resume_origin": "canonical_continuation",
            "active_resume_pointer": "GPD/phases/04/.continue-here.md",
            "has_live_execution": False,
            "execution_paused_at": None,
            "autonomy": None,
            "research_mode": None,
            "machine_change_notice": (
                "Machine change detected: last active on old-host (Linux 5.15 x86_64); "
                "current machine new-host (Linux 6.1 x86_64). The project state is portable and does not require repair. "
                "Rerun the installer if runtime-local config may be stale on this machine."
            ),
        },
    )

    result = runner.invoke(app, ["resume"])

    assert result.exit_code == 0
    normalized = " ".join(result.output.split())
    assert "A continuity handoff is available" in normalized
    assert "continuity_handoff" in result.output
    assert "Rerun the installer" in normalized
    assert "resume-work" in result.output
    assert "suggest-next" in result.output


def test_resume_plain_output_surfaces_advisory_live_execution_status(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "gpd.core.context.init_resume",
        lambda _cwd: {
            "planning_exists": True,
            "state_exists": True,
            "roadmap_exists": True,
            "project_exists": True,
            "resume_candidates": [],
            "has_live_execution": True,
            "derived_execution_head": {
                "phase": "03",
                "plan": "01",
                "segment_id": "seg-3",
                "segment_status": "active",
            },
            "execution_paused_at": None,
            "autonomy": None,
            "research_mode": None,
        },
    )

    result = runner.invoke(app, ["resume"])

    assert result.exit_code == 0
    normalized = " ".join(result.output.split())
    assert "A live execution snapshot exists" in normalized
    assert "it is advisory only and does not expose a portable bounded-segment target." in normalized
    assert "resume-work" not in result.output
    assert "suggest-next" not in result.output


def test_resume_plain_output_surfaces_missing_handoff_status(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "gpd.core.context.init_resume",
        lambda _cwd: {
            "planning_exists": True,
            "state_exists": True,
            "roadmap_exists": True,
            "project_exists": True,
            "resume_candidates": [
                {
                    "kind": "continuity_handoff",
                    "source": "session_resume_file",
                    "status": "missing",
                    "resume_file": "GPD/phases/04/.continue-here.md",
                    "resumable": False,
                    "advisory": True,
                    "origin": "canonical_continuation",
                }
            ],
            "missing_continuity_handoff_file": "GPD/phases/04/.continue-here.md",
            "has_live_execution": False,
            "execution_paused_at": None,
            "autonomy": None,
            "research_mode": None,
        },
    )

    result = runner.invoke(app, ["resume"])

    assert result.exit_code == 0
    normalized = " ".join(result.output.split())
    assert "Canonical recovery metadata exists" in normalized
    assert "continuity_handoff" in result.output
    assert "the continuity handoff file is missing." in normalized
    assert "resume-work" not in result.output
    assert "suggest-next" not in result.output


def test_resume_raw_adds_canonical_recovery_projection_fields(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    resume_file = "GPD/phases/01/.continue-here.md"
    monkeypatch.setattr(
        "gpd.core.context.init_resume",
        lambda _cwd: {
            "planning_exists": True,
            "state_exists": True,
            "roadmap_exists": True,
            "project_exists": True,
            "resume_candidates": [
                {
                    "source": "session_resume_file",
                    "status": "handoff",
                    "resume_file": resume_file,
                    "resumable": False,
                    "kind": "continuity_handoff",
                    "origin": "canonical_continuation",
                    "resume_pointer": resume_file,
                }
            ],
            "has_live_execution": False,
            "active_resume_kind": "continuity_handoff",
            "active_resume_origin": "canonical_continuation",
            "active_resume_pointer": resume_file,
            "execution_paused_at": None,
            "autonomy": None,
            "research_mode": None,
            "active_execution_segment": None,
        },
    )

    result = runner.invoke(app, ["--raw", "resume"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    _assert_no_top_level_resume_aliases(payload)
    assert payload["recovery_advice"]["resume_surface_schema_version"] == 1
    assert "compat_resume_surface" not in payload["recovery_advice"]
    for key in RESUME_COMPATIBILITY_ALIAS_FIELDS:
        assert key not in payload["recovery_advice"]
    assert payload["active_resume_kind"] == "continuity_handoff"
    assert payload["active_resume_origin"] == "canonical_continuation"
    assert payload["active_resume_pointer"] == resume_file
    assert payload["recovery_status"] == "session-handoff"
    assert payload["recovery_status_label"] == "Continuity handoff"
    assert payload["recovery_summary"] == (
        "A continuity handoff is available, but no resumable bounded segment is currently active."
    )
    assert "compat_resume_surface" not in payload
    assert payload.get("resume_mode_label", "none") == "none"
    assert payload["resume_candidates"][0]["origin"] == "canonical_continuation"
    assert payload["recovery_candidates"][0]["kind"] == "continuity_handoff"
    assert payload["recovery_candidates"][0]["kind_label"] == "Continuity handoff"
    assert payload["recovery_candidates"][0]["origin"] == "canonical_continuation"
    assert payload["primary_recovery_target"]["target"] == "./GPD/phases/01/.continue-here.md"


def test_resume_raw_keeps_derived_execution_head_origin_when_only_live_snapshot_exists(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    resume_file = "GPD/phases/03/.continue-here.md"
    monkeypatch.setattr(
        "gpd.core.context.init_resume",
        lambda _cwd: {
            "planning_exists": True,
            "state_exists": True,
            "roadmap_exists": True,
            "project_exists": True,
            "resume_candidates": [
                {
                    "source": "current_execution",
                    "status": "paused",
                    "resume_file": resume_file,
                    "resumable": True,
                    "kind": "bounded_segment",
                    "origin": "current_execution",
                    "resume_pointer": resume_file,
                }
            ],
            "derived_execution_head": {
                "phase": "03",
                "plan": "01",
                "segment_id": "seg-derived",
                "segment_status": "paused",
                "resume_file": resume_file,
            },
            "has_live_execution": True,
            "execution_resumable": True,
            "active_resume_kind": "bounded_segment",
            "active_resume_origin": "current_execution",
            "active_resume_pointer": resume_file,
            "execution_paused_at": None,
            "autonomy": None,
            "research_mode": None,
        },
    )

    result = runner.invoke(app, ["--raw", "resume"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    _assert_no_top_level_resume_aliases(payload)
    assert payload["active_resume_kind"] == "bounded_segment"
    assert payload["active_resume_origin"] == "derived_execution_head"
    assert payload["resume_candidates"][0]["origin"] == "derived_execution_head"
    assert payload["recovery_candidates"][0]["origin"] == "derived_execution_head"
    assert payload["primary_recovery_target"]["origin"] == "derived_execution_head"
    assert "compat_resume_surface" not in payload


def test_resume_raw_keeps_derived_execution_head_origin_when_active_bounded_segment_is_projected(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    resume_file = "GPD/phases/03/.continue-here.md"
    monkeypatch.setattr(
        "gpd.core.context.init_resume",
        lambda _cwd: {
            "planning_exists": True,
            "state_exists": True,
            "roadmap_exists": True,
            "project_exists": True,
            "resume_candidates": [
                {
                    "source": "current_execution",
                    "status": "paused",
                    "resume_file": resume_file,
                    "resumable": True,
                    "kind": "bounded_segment",
                    "origin": "current_execution",
                    "resume_pointer": resume_file,
                }
            ],
            "active_bounded_segment": {
                "phase": "03",
                "plan": "01",
                "segment_id": "seg-projected",
                "segment_status": "paused",
                "resume_file": resume_file,
            },
            "derived_execution_head": {
                "phase": "03",
                "plan": "01",
                "segment_id": "seg-projected",
                "segment_status": "paused",
                "resume_file": resume_file,
            },
            "has_live_execution": True,
            "execution_resumable": True,
            "active_resume_kind": "bounded_segment",
            "active_resume_origin": "current_execution",
            "active_resume_pointer": resume_file,
            "execution_paused_at": None,
            "autonomy": None,
            "research_mode": None,
        },
    )

    result = runner.invoke(app, ["--raw", "resume"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    _assert_no_top_level_resume_aliases(payload)
    assert payload["active_resume_origin"] == "derived_execution_head"
    assert payload["resume_candidates"][0]["origin"] == "derived_execution_head"
    assert payload["recovery_candidates"][0]["origin"] == "derived_execution_head"
    assert payload["primary_recovery_target"]["origin"] == "derived_execution_head"


def test_resume_raw_drops_malformed_resume_candidates_from_public_output(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    resume_file = "GPD/phases/01/.continue-here.md"
    monkeypatch.setattr(
        "gpd.core.context.init_resume",
        lambda _cwd: {
            "planning_exists": True,
            "state_exists": True,
            "roadmap_exists": True,
            "project_exists": True,
            "resume_candidates": [
                {
                    "source": "session_resume_file",
                    "status": "handoff",
                    "resume_file": resume_file,
                    "resumable": False,
                    "kind": "continuity_handoff",
                    "origin": "canonical_continuation",
                    "resume_pointer": resume_file,
                },
                "not-a-candidate",
                None,
                ["still-not-a-candidate"],
            ],
            "has_live_execution": False,
            "active_resume_kind": "continuity_handoff",
            "active_resume_origin": "canonical_continuation",
            "active_resume_pointer": resume_file,
            "execution_paused_at": None,
            "autonomy": None,
            "research_mode": None,
            "active_execution_segment": None,
        },
    )

    result = runner.invoke(app, ["--raw", "resume"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    _assert_no_top_level_resume_aliases(payload)
    assert payload["resume_candidates"] == [
        {
            "source": "session_resume_file",
            "status": "handoff",
            "resume_file": resume_file,
            "resumable": False,
            "kind": "continuity_handoff",
            "origin": "canonical_continuation",
            "resume_pointer": resume_file,
        }
    ]
    assert len(payload["recovery_candidates"]) == 1
    assert payload["recovery_candidates"][0]["kind"] == "continuity_handoff"
    assert payload["recovery_candidates"][0]["kind_label"] == "Continuity handoff"
    assert payload["recovery_candidates"][0]["origin"] == "canonical_continuation"
    assert payload["recovery_candidates"][0]["origin_label"] == "canonical continuation"
    assert payload["recovery_candidates"][0]["target"] == "./GPD/phases/01/.continue-here.md"
    assert payload["recovery_candidates"][0]["notes"] == "Recorded in canonical continuation state."
    assert payload["recovery_candidates"][0]["advisory"] is None
    assert payload["primary_recovery_target"] == payload["recovery_candidates"][0]


def test_command_supports_project_reentry_prefers_explicit_metadata() -> None:
    assert (
        cli_module._command_supports_project_reentry(
            SimpleNamespace(name="gpd:custom", context_mode="project-required", project_reentry_capable=True)
        )
        is True
    )
    assert (
        cli_module._command_supports_project_reentry(
            SimpleNamespace(name="gpd:progress", context_mode="project-required", project_reentry_capable=False)
        )
        is False
    )
    assert (
        cli_module._command_supports_project_reentry(
            SimpleNamespace(name="gpd:progress", context_mode="project-required")
        )
        is False
    )


def test_command_supports_project_reentry_requires_explicit_positive_metadata() -> None:
    assert (
        cli_module._command_supports_project_reentry(
            SimpleNamespace(name="gpd:plan-phase", context_mode="project-required")
        )
        is False
    )


def test_observe_execution_help_surfaces_read_only_local_status_role() -> None:
    result = runner.invoke(app, ["observe", "execution", "--help"])
    assert result.exit_code == 0
    assert "Show the current local execution status without modifying project state." in result.output
    assert "possibly stalled" not in result.output.lower()


def test_validate_help_surfaces_command_context_preflight_entrypoint() -> None:
    result = runner.invoke(app, ["validate", "--help"])
    assert result.exit_code == 0
    assert "Validation checks" in result.output
    assert "command-context" in result.output
    assert "plan-preflight" in result.output
    assert "review-preflight" in result.output
    assert "project-contract" in result.output


def test_validate_project_contract_help_surfaces_proof_obligation_visibility() -> None:
    result = runner.invoke(app, ["validate", "project-contract", "--help"])

    assert result.exit_code == 0
    normalized_output = _normalize_cli_output(result.output)
    assert "Validate a project-scoping contract before downstream artifact generation" in normalized_output
    assert "proof-obligation observables" in normalized_output


def test_validate_verification_contract_help_surfaces_stale_proof_gate_visibility() -> None:
    result = runner.invoke(app, ["validate", "verification-contract", "--help"])

    assert result.exit_code == 0
    normalized_output = _normalize_cli_output(result.output)
    assert "Validate VERIFICATION frontmatter and contract-result alignment" in normalized_output
    assert "stale proof-audit blockers when recorded" in normalized_output


def test_validate_command_context_help_surfaces_registry_argument_name() -> None:
    result = runner.invoke(app, ["validate", "command-context", "--help"])
    assert result.exit_code == 0
    assert "Run centralized command-context preflight based on command metadata." in result.output
    assert "Command registry key or gpd:name" in result.output


@patch("gpd.core.contract_validation.validate_project_contract")
def test_validate_project_contract_uses_ancestor_project_root_from_nested_cwd(
    mock_validate_contract,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    nested_cwd = project_root / "workspace" / "nested"
    (project_root / "GPD").mkdir(parents=True, exist_ok=True)
    nested_cwd.mkdir(parents=True, exist_ok=True)
    contract_path = nested_cwd / "contract.json"
    contract_path.write_text((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"), encoding="utf-8")

    validation_result = MagicMock()
    validation_result.valid = True
    validation_result.model_dump.return_value = {"valid": True}
    mock_validate_contract.return_value = validation_result

    result = runner.invoke(
        app,
        ["--cwd", str(nested_cwd), "validate", "project-contract", contract_path.name],
    )

    assert result.exit_code == 0
    mock_validate_contract.assert_called_once()
    _, validate_kwargs = mock_validate_contract.call_args
    assert validate_kwargs["project_root"] == project_root.resolve()
    assert validate_kwargs["mode"] == "approved"


def test_validate_project_contract_accepts_proof_obligation_observable_fixture(tmp_path: Path) -> None:
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["scope"]["question"] = "Does the reviewed proof establish the theorem for every named parameter, including r_0?"
    contract["observables"][0] = {
        "id": "obs-proof",
        "name": "full theorem proof obligation",
        "kind": "proof_obligation",
        "definition": "Prove the theorem for the full stated hypothesis set and every named parameter, including r_0.",
        "regime": "all stated parameter regimes",
    }
    contract["claims"][0]["statement"] = "The theorem is proved for all stated hypotheses and named parameters, including nonzero r_0."
    contract["claims"][0]["claim_kind"] = "theorem"
    contract["claims"][0]["observables"] = ["obs-proof"]
    contract["claims"][0]["proof_deliverables"] = ["deliv-figure"]
    contract["claims"][0]["parameters"] = [
        {"symbol": "r_0", "domain_or_type": "nonnegative real"}
    ]
    contract["claims"][0]["hypotheses"] = [
        {"id": "hyp-r0", "text": "r_0 >= 0", "symbols": ["r_0"]}
    ]
    contract["claims"][0]["conclusion_clauses"] = [
        {
            "id": "concl-proof",
            "text": "The theorem holds for the full stated hypothesis set and every named parameter, including nonzero r_0.",
        }
    ]
    contract["deliverables"][0]["kind"] = "derivation"
    contract["deliverables"][0]["path"] = "proofs/full-theorem-proof.tex"
    contract["deliverables"][0]["description"] = "Formal proof artifact for the theorem claim audit"
    contract["deliverables"][0]["must_contain"] = [
        "theorem statement with hypotheses",
        "explicit use or discharge of r_0",
        "red-team proof audit notes",
    ]
    contract["acceptance_tests"][0]["kind"] = "claim_to_proof_alignment"
    contract["acceptance_tests"][0]["procedure"] = (
        "Adversarially review the theorem proof against every named hypothesis and parameter, including r_0."
    )
    contract["acceptance_tests"][0]["pass_condition"] = (
        "Proof covers the full stated theorem rather than a silently narrowed subcase."
    )
    contract["acceptance_tests"][0]["automation"] = "hybrid"
    contract["references"][0]["role"] = "definition"
    contract["references"][0]["why_it_matters"] = "Anchors the theorem statement and parameterization being audited."
    contract["uncertainty_markers"]["weakest_anchors"] = [
        "A named theorem parameter could disappear from the proof without being noticed."
    ]
    contract["uncertainty_markers"]["disconfirming_observations"] = [
        "The derivation only proves the r_0 = 0 subcase while claiming the full theorem."
    ]

    contract_path = tmp_path / "proof-project-contract.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")

    result = runner.invoke(
        app,
        ["--cwd", str(tmp_path), "--raw", "validate", "project-contract", str(contract_path), "--mode", "approved"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["valid"] is True
    assert payload["question"] == contract["scope"]["question"]
    assert payload["mode"] == "approved"
    assert payload["decisive_target_count"] > 0
    assert payload["guidance_signal_count"] > 0


def test_validate_project_contract_raw_failure_surfaces_schema_reference(tmp_path: Path) -> None:
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["context_intake"]["must_include_prior_outputs"] = []
    contract["context_intake"]["user_asserted_anchors"] = []
    contract["context_intake"]["known_good_baselines"] = []
    contract["references"][0]["must_surface"] = False

    contract_path = tmp_path / "project-contract-invalid.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")

    result = runner.invoke(
        app,
        ["--raw", "validate", "project-contract", str(contract_path), "--mode", "approved"],
        catch_exceptions=False,
    )

    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    assert payload["valid"] is False
    assert payload["schema_reference"].endswith("project-contract-schema.md")
    assert any("approved project contract requires at least one concrete anchor" in error for error in payload["errors"])


def _plan_with_tool_requirements(tool_requirements_block: str) -> str:
    fixture = (
        Path(__file__).resolve().parents[1] / "fixtures" / "stage0" / "plan_with_contract.md"
    ).read_text(encoding="utf-8")
    return fixture.replace("interactive: false\n", f"interactive: false\n{tool_requirements_block}", 1)


def _plan_with_knowledge_controls(
    *,
    knowledge_gate: str | None = None,
    knowledge_deps: list[str] | None = None,
) -> str:
    fixture = (
        Path(__file__).resolve().parents[1] / "fixtures" / "stage0" / "plan_with_contract.md"
    ).read_text(encoding="utf-8")
    metadata_block = ""
    if knowledge_gate is not None:
        metadata_block += f"knowledge_gate: {knowledge_gate}\n"
    if knowledge_deps is not None:
        metadata_block += "knowledge_deps:\n"
        for dep in knowledge_deps:
            metadata_block += f"  - {dep}\n"
    return fixture.replace("interactive: false\n", f"interactive: false\n{metadata_block}", 1)


def test_validate_plan_preflight_passes_when_no_specialized_tools_are_declared(tmp_path: Path) -> None:
    plan_path = tmp_path / "01-01-PLAN.md"
    plan_path.write_text(
        (Path(__file__).resolve().parents[1] / "fixtures" / "stage0" / "plan_with_contract.md").read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["--raw", "validate", "plan-preflight", str(plan_path)])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["passed"] is True
    assert payload["requirements"] == []
    assert payload["guidance"] == "No machine-checkable specialized tool requirements declared."


def test_validate_plan_preflight_blocks_on_missing_required_wolfram(
    tmp_path: Path,
    monkeypatch,
) -> None:
    plan_path = tmp_path / "01-01-PLAN.md"
    plan_path.write_text(
        _plan_with_tool_requirements(
            "tool_requirements:\n"
            "  - id: wolfram-cas\n"
            "    tool: wolfram\n"
            "    purpose: Symbolic tensor reduction\n"
            "    required: true\n"
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("gpd.core.tool_preflight.shutil.which", lambda _binary: None)

    result = runner.invoke(app, ["--raw", "validate", "plan-preflight", str(plan_path)])

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["passed"] is False
    assert payload["requirements"][0]["tool"] == "wolfram"
    assert payload["requirements"][0]["blocking"] is True
    assert "wolframscript not found on PATH" in payload["blocking_conditions"][0]


def test_validate_plan_preflight_allows_missing_optional_wolfram_with_fallback(
    tmp_path: Path,
    monkeypatch,
) -> None:
    plan_path = tmp_path / "01-01-PLAN.md"
    plan_path.write_text(
        _plan_with_tool_requirements(
            "tool_requirements:\n"
            "  - id: wolfram-cas\n"
            "    tool: mathematica\n"
            "    purpose: Symbolic tensor reduction\n"
            "    required: false\n"
            "    fallback: Use SymPy and record any simplification gaps\n"
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("gpd.core.tool_preflight.shutil.which", lambda _binary: None)

    result = runner.invoke(app, ["--raw", "validate", "plan-preflight", str(plan_path)])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["passed"] is True
    assert payload["requirements"][0]["tool"] == "wolfram"
    assert payload["requirements"][0]["blocking"] is False


def test_validate_plan_preflight_warns_on_missing_knowledge_dependency(
    tmp_path: Path,
) -> None:
    plan_path = tmp_path / "01-01-PLAN.md"
    plan_path.write_text(
        _plan_with_knowledge_controls(
            knowledge_gate="warn",
            knowledge_deps=["K-missing-dependency"],
        ),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["--raw", "validate", "plan-preflight", str(plan_path)])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["knowledge_gate"] == "warn"
    assert payload["passed"] is True
    assert payload["knowledge_dependency_checks"][0]["status"] == "missing"
    assert any("K-missing-dependency" in warning for warning in payload["warnings"])


def test_validate_plan_preflight_blocks_on_missing_knowledge_dependency(
    tmp_path: Path,
) -> None:
    plan_path = tmp_path / "01-01-PLAN.md"
    plan_path.write_text(
        _plan_with_knowledge_controls(
            knowledge_gate="block",
            knowledge_deps=["K-missing-dependency"],
        ),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["--raw", "validate", "plan-preflight", str(plan_path)])

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["knowledge_gate"] == "block"
    assert payload["passed"] is False
    assert payload["knowledge_dependency_checks"][0]["status"] == "missing"
    assert any("K-missing-dependency" in blocker for blocker in payload["blocking_conditions"])


def test_resolve_model_help_lists_supported_runtime_ids():
    result = runner.invoke(app, ["resolve-model", "--help"])
    assert result.exit_code == 0
    for runtime_name in list_runtimes():
        assert runtime_name in result.output


def test_state_help():
    result = runner.invoke(app, ["state", "--help"])
    assert result.exit_code == 0
    assert "load" in result.output
    assert "get" in result.output
    assert "update" in result.output


def test_phase_help():
    result = runner.invoke(app, ["phase", "--help"])
    assert result.exit_code == 0
    assert "list" in result.output
    assert "add" in result.output
    assert "complete" in result.output


def test_session_command_is_not_exposed():
    result = runner.invoke(app, ["session", "--help"])
    assert result.exit_code != 0
    assert "No such command 'session'" in result.output


def test_view_command_is_not_exposed():
    result = runner.invoke(app, ["view", "--help"])
    assert result.exit_code != 0
    assert "No such command 'view'" in result.output


# ─── state subcommands ──────────────────────────────────────────────────────


@patch("gpd.core.state.state_load")
def test_state_load(mock_load):
    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"position": {"current_phase": "42"}}
    mock_load.return_value = mock_result
    result = runner.invoke(app, ["state", "load"])
    assert result.exit_code == 0
    mock_load.assert_called_once()


@patch("gpd.core.state.state_load")
def test_state_load_uses_ancestor_project_root_from_nested_cwd(mock_load, tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    nested_cwd = project_root / "workspace" / "nested"
    (project_root / "GPD").mkdir(parents=True, exist_ok=True)
    nested_cwd.mkdir(parents=True, exist_ok=True)

    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"position": {"current_phase": "42"}}
    mock_load.return_value = mock_result

    result = runner.invoke(app, ["--cwd", str(nested_cwd), "state", "load"])

    assert result.exit_code == 0
    mock_load.assert_called_once_with(project_root.resolve())


@patch("gpd.core.state.state_get")
def test_state_get_section(mock_get):
    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"section": "position", "data": {}}
    mock_get.return_value = mock_result
    result = runner.invoke(app, ["state", "get", "position"])
    assert result.exit_code == 0
    mock_get.assert_called_once()


@patch("gpd.core.state.state_get")
def test_state_active_hypothesis(mock_get):
    mock_result = MagicMock()
    mock_result.value = "**Branch:** hypothesis/alt-method\n**Description:** investigate a fallback"
    mock_result.error = None
    mock_get.return_value = mock_result

    result = runner.invoke(app, ["--raw", "state", "active-hypothesis"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload == {
        "found": True,
        "branch": "hypothesis/alt-method",
        "branch_slug": "alt-method",
        "section": mock_result.value,
    }


@patch("gpd.core.state.state_get")
def test_state_active_hypothesis_missing_section(mock_get):
    mock_result = MagicMock()
    mock_result.value = None
    mock_result.error = "Section or field \"Active Hypothesis\" not found"
    mock_get.return_value = mock_result

    result = runner.invoke(app, ["--raw", "state", "active-hypothesis"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["found"] is False
    assert payload["branch"] is None
    assert payload["branch_slug"] is None
    assert "Active Hypothesis" in payload["error"]


@patch("gpd.core.state.state_update")
def test_state_update(mock_update):
    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"updated": True}
    mock_update.return_value = mock_result
    result = runner.invoke(app, ["state", "update", "status", "executing"])
    assert result.exit_code == 0
    mock_update.assert_called_once()


@patch("gpd.core.state.state_update")
def test_state_update_uses_workspace_cwd_when_no_project_root_is_verified(mock_update, tmp_path: Path) -> None:
    workspace_cwd = tmp_path / "wrong-folder"
    workspace_cwd.mkdir()
    other_project = tmp_path / "other-project"
    (other_project / "GPD").mkdir(parents=True)

    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"updated": True}
    mock_update.return_value = mock_result

    with (
        patch("gpd.cli.resolve_project_root", return_value=None),
        patch("gpd.cli._status_command_cwd", return_value=other_project.resolve(strict=False)),
    ):
        result = runner.invoke(app, ["--cwd", str(workspace_cwd), "state", "update", "status", "executing"])

    assert result.exit_code == 0
    mock_update.assert_called_once_with(workspace_cwd.resolve(), "status", "executing")


@patch("gpd.core.state.state_set_project_contract")
@patch("gpd.core.contract_validation.validate_project_contract")
def test_state_set_project_contract_uses_ancestor_project_root_from_nested_cwd(
    mock_validate_contract,
    mock_set_project_contract,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    nested_cwd = project_root / "workspace" / "nested"
    (project_root / "GPD").mkdir(parents=True, exist_ok=True)
    nested_cwd.mkdir(parents=True, exist_ok=True)
    contract_path = nested_cwd / "contract.json"
    contract_path.write_text((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"), encoding="utf-8")

    validation_result = MagicMock()
    validation_result.valid = True
    validation_result.model_dump.return_value = {"valid": True}
    mock_validate_contract.return_value = validation_result

    write_result = MagicMock()
    write_result.updated = True
    write_result.unchanged = False
    write_result.model_dump.return_value = {"updated": True}
    mock_set_project_contract.return_value = write_result

    result = runner.invoke(
        app,
        ["--cwd", str(nested_cwd), "state", "set-project-contract", contract_path.name],
    )

    assert result.exit_code == 0
    mock_validate_contract.assert_called_once()
    _, validate_kwargs = mock_validate_contract.call_args
    assert validate_kwargs["project_root"] == project_root.resolve()
    assert validate_kwargs["mode"] == "approved"
    mock_set_project_contract.assert_called_once()
    assert mock_set_project_contract.call_args.args[0] == project_root.resolve()


@patch("gpd.core.state.state_record_session")
def test_state_record_session_forwards_last_result_id(mock_record_session):
    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"recorded": True, "updated": ["Last result ID"]}
    mock_record_session.return_value = mock_result

    result = runner.invoke(
        app,
        [
            "state",
            "record-session",
            "--stopped-at",
            "Paused at task 2/5",
            "--resume-file",
            "GPD/phases/01-test-phase/.continue-here.md",
            "--last-result-id",
            "R-bridge-01",
        ],
    )

    assert result.exit_code == 0
    mock_record_session.assert_called_once()
    _, kwargs = mock_record_session.call_args
    assert kwargs["stopped_at"] == "Paused at task 2/5"
    assert kwargs["resume_file"] == "GPD/phases/01-test-phase/.continue-here.md"
    assert kwargs["last_result_id"] == "R-bridge-01"


@patch("gpd.core.state.state_record_session")
def test_state_record_session_exits_nonzero_for_invalid_last_result_id(mock_record_session):
    mock_result = MagicMock()
    mock_result.model_dump.return_value = {
        "recorded": False,
        "error": "Unknown canonical result ID: R-missing",
    }
    mock_record_session.return_value = mock_result

    result = runner.invoke(
        app,
        [
            "state",
            "record-session",
            "--stopped-at",
            "Paused at task 2/5",
            "--resume-file",
            "GPD/phases/01-test-phase/.continue-here.md",
            "--last-result-id",
            "R-missing",
        ],
    )

    assert result.exit_code == 1
    mock_record_session.assert_called_once()
    _, kwargs = mock_record_session.call_args
    assert kwargs["stopped_at"] == "Paused at task 2/5"
    assert kwargs["resume_file"] == "GPD/phases/01-test-phase/.continue-here.md"
    assert kwargs["last_result_id"] == "R-missing"
    assert "Unknown canonical result ID: R-missing" in result.output


@patch("gpd.core.state.state_validate")
def test_state_validate_pass(mock_validate):
    mock_result = MagicMock()
    mock_result.valid = True
    mock_result.model_dump.return_value = {"valid": True, "issues": []}
    mock_validate.return_value = mock_result
    result = runner.invoke(app, ["state", "validate"])
    assert result.exit_code == 0


@patch("gpd.core.state.state_validate")
def test_state_validate_fail(mock_validate):
    mock_result = MagicMock()
    mock_result.valid = False
    mock_result.model_dump.return_value = {"valid": False, "issues": ["bad"]}
    mock_validate.return_value = mock_result
    result = runner.invoke(app, ["state", "validate"])
    assert result.exit_code == 1


# ─── phase subcommands ──────────────────────────────────────────────────────


@patch("gpd.core.phases.list_phases")
def test_phase_list(mock_list):
    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"phases": []}
    mock_list.return_value = mock_result
    result = runner.invoke(app, ["phase", "list"])
    assert result.exit_code == 0
    mock_list.assert_called_once()


@patch("gpd.core.phases.list_phase_files")
def test_phase_list_with_filters_uses_file_listing(mock_list_files):
    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"files": ["01-test-PLAN.md"], "count": 1, "phase_dir": "01-test"}
    mock_list_files.return_value = mock_result

    result = runner.invoke(app, ["phase", "list", "--type", "plans", "--phase", "01"])

    assert result.exit_code == 0
    mock_list_files.assert_called_once_with(ANY, file_type="plans", phase="01")


@patch("gpd.core.phases.phase_add")
def test_phase_add(mock_add):
    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"phase": "43", "added": True}
    mock_add.return_value = mock_result
    result = runner.invoke(app, ["phase", "add", "Compute", "cross", "section"])
    assert result.exit_code == 0
    # Verify the description was joined
    args = mock_add.call_args
    assert "Compute cross section" in args[0][1]


@patch("gpd.core.phases.phase_complete")
def test_phase_complete(mock_complete):
    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"completed": True}
    mock_complete.return_value = mock_result
    result = runner.invoke(app, ["phase", "complete", "42"])
    assert result.exit_code == 0
    mock_complete.assert_called_once()


def test_phase_normalize_command():
    result = runner.invoke(app, ["phase", "normalize", "3.1"])

    assert result.exit_code == 0
    assert "03.1" in result.output


@patch("gpd.core.phases.validate_phase_waves")
def test_phase_validate_waves_pass(mock_validate):
    mock_result = MagicMock()
    mock_result.validation.valid = True
    mock_result.model_dump.return_value = {"phase": "42", "validation": {"valid": True, "errors": []}}
    mock_validate.return_value = mock_result

    result = runner.invoke(app, ["phase", "validate-waves", "42"])

    assert result.exit_code == 0
    mock_validate.assert_called_once()


@patch("gpd.core.phases.validate_phase_waves")
def test_phase_validate_waves_fail(mock_validate):
    mock_result = MagicMock()
    mock_result.validation.valid = False
    mock_result.model_dump.return_value = {"phase": "42", "validation": {"valid": False, "errors": ["cycle"]}}
    mock_validate.return_value = mock_result

    result = runner.invoke(app, ["phase", "validate-waves", "42"])

    assert result.exit_code == 1
    mock_validate.assert_called_once()


def test_validate_phase_artifacts_reports_expected_frontmatter_errors(tmp_path: Path) -> None:
    phases_dir = tmp_path / "GPD" / "phases" / "01-test"
    phases_dir.mkdir(parents=True)
    summary_path = phases_dir / "01-test-SUMMARY.md"
    summary_path.write_text("---\nnot: valid\n", encoding="utf-8")

    with patch("gpd.core.frontmatter.validate_frontmatter", side_effect=FrontmatterParseError("bad yaml")):
        failures = cli_module._validate_phase_artifacts(tmp_path / "GPD" / "phases", "summary")

    assert failures == [f"{cli_module._format_display_path(summary_path)}: could not validate frontmatter (bad yaml)"]


def test_validate_phase_artifacts_does_not_swallow_programmer_errors(tmp_path: Path) -> None:
    phases_dir = tmp_path / "GPD" / "phases" / "01-test"
    phases_dir.mkdir(parents=True)
    summary_path = phases_dir / "01-test-SUMMARY.md"
    summary_path.write_text("---\nnot: valid\n", encoding="utf-8")

    with patch("gpd.core.frontmatter.validate_frontmatter", side_effect=RuntimeError("boom")):
        with pytest.raises(RuntimeError, match="boom"):
            cli_module._validate_phase_artifacts(tmp_path / "GPD" / "phases", "summary")


# ─── raw output ─────────────────────────────────────────────────────────────


@patch("gpd.core.state.state_load")
def test_raw_json_output(mock_load):
    mock_load.return_value = {"position": {"current_phase": "42"}}
    result = runner.invoke(app, ["--raw", "state", "load"])
    assert result.exit_code == 0
    assert "current_phase" in result.output


def test_raw_json_get_outputs_literal_json_value():
    result = runner.invoke(app, ["--raw", "json", "get", ".x"], input='{"x": 1}\n')
    assert result.exit_code == 0
    assert json.loads(result.output) == "1"


def test_raw_json_get_error_outputs_json():
    result = runner.invoke(app, ["--raw", "json", "get", ".x"], input="not json\n")
    assert result.exit_code == 1
    assert "Invalid JSON input" in json.loads(result.output)["error"]


def test_normalize_global_cli_options_moves_trailing_root_options(tmp_path: Path) -> None:
    argv = ["progress", "bar", "--cwd", str(tmp_path), "--raw"]

    assert cli_module._normalize_global_cli_options(argv) == [
        "--cwd",
        str(tmp_path),
        "--raw",
        "progress",
        "bar",
    ]


def test_normalize_global_cli_options_respects_double_dash() -> None:
    argv = ["json", "get", ".x", "--", "--raw"]

    assert cli_module._normalize_global_cli_options(argv) == argv


def test_resolve_cli_cwd_from_argv_supports_trailing_cwd(tmp_path: Path) -> None:
    resolved = cli_module._resolve_cli_cwd_from_argv(["progress", "bar", "--cwd", str(tmp_path)])

    assert resolved == tmp_path.resolve()


def test_shared_root_global_cli_helpers_match_cli_and_bridge_wrappers(tmp_path: Path, monkeypatch) -> None:
    launcher = tmp_path / "launcher"
    launcher.mkdir()
    nested = tmp_path / "workspace" / "nested"
    nested.mkdir(parents=True)
    monkeypatch.chdir(launcher)

    argv = ["state", "load", "--cwd", str(nested), "--raw"]

    assert cli_args_module.split_root_global_cli_options(argv) == cli_module._split_global_cli_options(argv)
    assert cli_args_module.normalize_root_global_cli_options(argv) == cli_module._normalize_global_cli_options(argv)
    assert cli_args_module.resolve_root_global_cli_cwd_from_argv(argv) == cli_module._resolve_cli_cwd_from_argv(argv)
    assert cli_args_module.resolve_root_global_cli_cwd_from_argv(argv) == runtime_cli._resolve_cli_cwd_from_argv(argv)


def test_entrypoint_normalizes_trailing_global_options(monkeypatch) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(cli_module, "_maybe_reexec_from_checkout", lambda: None)
    monkeypatch.setattr(cli_module.sys, "argv", ["gpd", "progress", "bar", "--cwd", "/tmp/demo", "--raw"])

    def fake_app(*, args: list[str] | None = None) -> int:
        captured["args"] = args
        return 0

    monkeypatch.setattr(cli_module, "app", fake_app)

    assert cli_module.entrypoint() == 0
    assert captured["args"] == ["--cwd", "/tmp/demo", "--raw", "progress", "bar"]


@pytest.mark.parametrize("root_flag", ["--version", "-v"])
def test_entrypoint_normalizes_trailing_root_global_flags(monkeypatch, root_flag: str) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(cli_module, "_maybe_reexec_from_checkout", lambda: None)
    monkeypatch.setattr(cli_module.sys, "argv", ["gpd", "progress", "bar", root_flag])

    def fake_app(*, args: list[str] | None = None) -> int:
        captured["args"] = args
        return 0

    monkeypatch.setattr(cli_module, "app", fake_app)

    assert cli_module.entrypoint() == 0
    assert captured["args"] == [root_flag, "progress", "bar"]


@patch("gpd.core.phases.progress_render")
def test_app_call_accepts_trailing_raw_and_cwd(
    mock_progress,
    tmp_path: Path,
    capsys,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_progress.return_value = {"bar": "ok"}
    monkeypatch.setenv("GPD_DATA_DIR", str(tmp_path / "data"))

    try:
        cli_module.app(args=["progress", "bar", "--cwd", str(tmp_path), "--raw"])
    except SystemExit as exc:
        assert exc.code == 0

    captured = capsys.readouterr()
    assert json.loads(captured.out)["bar"] == "ok"
    mock_progress.assert_called_once_with(tmp_path.resolve(), "bar")


@patch("gpd.core.phases.progress_render")
def test_progress_uses_workspace_cwd_when_no_project_root_is_verified(
    mock_progress,
    tmp_path: Path,
) -> None:
    workspace_cwd = tmp_path / "wrong-folder"
    workspace_cwd.mkdir()
    mock_progress.return_value = {"bar": "ok"}

    with (
        patch("gpd.cli.resolve_project_root", return_value=None),
        patch("gpd.cli._status_command_cwd", side_effect=AssertionError("unexpected reentry lookup")),
    ):
        result = runner.invoke(app, ["--cwd", str(workspace_cwd), "--raw", "progress", "bar"])

    assert result.exit_code == 0
    assert json.loads(result.output)["bar"] == "ok"
    mock_progress.assert_called_once_with(workspace_cwd.resolve(), "bar")


def test_validate_command_context_accepts_tokenized_standalone_arguments(tmp_path: Path) -> None:
    empty_dir = tmp_path / "empty-context"
    empty_dir.mkdir()

    result = runner.invoke(
        app,
        [
            "--raw",
            "--cwd",
            str(empty_dir),
            "validate",
            "command-context",
            "discover",
            "finite-temperature",
            "RG",
            "flow",
            "--depth",
            "deep",
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["command"] == "gpd:discover"
    assert payload["context_mode"] == "project-aware"
    assert payload["passed"] is True


def test_validate_command_context_accepts_tokenized_explain_arguments(tmp_path: Path) -> None:
    empty_dir = tmp_path / "empty-context"
    empty_dir.mkdir()

    result = runner.invoke(
        app,
        [
            "--raw",
            "--cwd",
            str(empty_dir),
            "validate",
            "command-context",
            "explain",
            "Berry",
            "curvature",
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["command"] == "gpd:explain"
    assert payload["context_mode"] == "project-aware"
    assert payload["passed"] is True


def test_pre_commit_check_recurses_into_directory_inputs(tmp_path: Path) -> None:
    directory = tmp_path / "docs"
    directory.mkdir()
    (directory / "state.md").write_text("# ok\n", encoding="utf-8")

    result = runner.invoke(
        app,
        ["--raw", "--cwd", str(tmp_path), "pre-commit-check", "--files", str(directory)],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["passed"] is True
    assert payload["files_checked"] == 1
    assert payload["details"][0]["file"].endswith("docs/state.md")


def test_pre_commit_check_fails_for_unreadable_inputs(tmp_path: Path) -> None:
    target = tmp_path / "state.md"
    target.write_text("# ok\n", encoding="utf-8")

    with patch("gpd.core.git_ops.Path.read_text", side_effect=OSError("denied")):
        result = runner.invoke(
            app,
            ["--raw", "--cwd", str(tmp_path), "pre-commit-check", "--files", str(target)],
            catch_exceptions=False,
        )

    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    assert payload["passed"] is False
    assert payload["details"][0]["readable"] is False


# ─── convention subcommands ─────────────────────────────────────────────────


@patch("gpd.core.conventions.convention_list")
def test_convention_list(mock_list):
    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"conventions": {}}
    mock_list.return_value = mock_result
    result = runner.invoke(app, ["convention", "list"])
    assert result.exit_code == 0
    mock_list.assert_called_once()


@patch("gpd.core.conventions.convention_list")
def test_convention_list_does_not_recover_intent_during_read_only_snapshot(
    mock_list: MagicMock,
    tmp_path: Path,
) -> None:
    stale_state = default_state_dict()
    stale_state["convention_lock"]["metric_signature"] = "(+,-,-,-)"
    save_state_json(tmp_path, stale_state)

    layout = ProjectLayout(tmp_path)
    recovered_state = default_state_dict()
    recovered_state["convention_lock"]["metric_signature"] = "(-,+,+,+)"
    json_tmp = layout.gpd / ".state-json-tmp"
    md_tmp = layout.gpd / ".state-md-tmp"
    json_tmp.write_text(json.dumps(recovered_state, indent=2) + "\n", encoding="utf-8")
    md_tmp.write_text(generate_state_markdown(recovered_state), encoding="utf-8")
    layout.state_intent.write_text(f"{json_tmp}\n{md_tmp}\n", encoding="utf-8")

    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"conventions": {}}
    mock_list.return_value = mock_result

    before_state = layout.state_json.read_text(encoding="utf-8")

    result = runner.invoke(app, ["--cwd", str(tmp_path), "convention", "list"])

    assert result.exit_code == 0, result.output
    lock = mock_list.call_args.args[0]
    assert lock.metric_signature == "(+,-,-,-)"
    assert layout.state_intent.exists()
    assert layout.state_json.read_text(encoding="utf-8") == before_state


def test_convention_list_fails_closed_for_malformed_primary_state(tmp_path: Path) -> None:
    backup_state = default_state_dict()
    backup_state["position"]["current_phase"] = "10"
    _write_recoverable_result_state(tmp_path, backup_state)

    result = runner.invoke(app, ["--cwd", str(tmp_path), "convention", "list"], catch_exceptions=False)

    assert result.exit_code == 1
    assert "Malformed state.json" in result.output
    assert "state.json.bak" in result.output


# ─── result subcommands ──────────────────────────────────────────────────────


@patch("gpd.core.results.result_search", create=True)
def test_result_search(mock_search):
    mock_result = MagicMock()
    mock_result.model_dump.return_value = {
        "matches": [
            {
                "id": "R-01",
                "equation": "E = mc^2",
                "description": "Energy-mass equivalence",
                "phase": "1",
                "depends_on": [],
                "verified": True,
            }
        ],
        "total": 1,
    }
    mock_search.return_value = mock_result

    result = runner.invoke(
        app,
        ["result", "search", "--equation", "E = mc^2", "--phase", "1", "--verified"],
    )

    assert result.exit_code == 0
    mock_search.assert_called_once()
    _, kwargs = mock_search.call_args
    assert kwargs["equation"] == "E = mc^2"
    assert kwargs["phase"] == "1"
    assert kwargs["verified"] is True
    assert kwargs.get("unverified") in (False, None)


@patch("gpd.core.results.result_search", create=True)
def test_result_search_raw_outputs_json_list(mock_search):
    mock_result = MagicMock()
    mock_result.model_dump.return_value = {
        "matches": [
            {
                "id": "R-02",
                "equation": "a = b + c",
                "description": "Derived quantity",
                "phase": "2",
                "depends_on": ["R-01"],
                "verified": False,
            }
        ],
        "total": 1,
    }
    mock_search.return_value = mock_result

    result = runner.invoke(
        app,
        ["--raw", "result", "search", "--text", "derived", "--unverified"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload == {
        "matches": [
            {
                "id": "R-02",
                "equation": "a = b + c",
                "description": "Derived quantity",
                "phase": "2",
                "depends_on": ["R-01"],
                "verified": False,
            }
        ],
        "total": 1,
    }
    mock_search.assert_called_once()
    _, kwargs = mock_search.call_args
    assert kwargs["text"] == "derived"
    assert kwargs["unverified"] is True


def test_result_help_surfaces_show_command_and_dependency_chain() -> None:
    result = runner.invoke(app, ["result", "--help"])

    assert result.exit_code == 0
    normalized_output = " ".join(result.output.split())
    assert "show" in normalized_output
    assert "downstream" in normalized_output
    assert "Show a canonical result" in normalized_output
    assert "direct/transitive" in normalized_output


def test_result_show_help_surfaces_required_result_id_argument() -> None:
    result = runner.invoke(app, ["result", "show", "--help"])

    assert result.exit_code == 0
    normalized_output = _normalize_cli_output(result.output)
    assert "Show a canonical result and its direct/transitive dependency chain." in normalized_output
    assert "RESULT_ID" in normalized_output
    assert "Canonical result ID [required]" in normalized_output


def test_result_downstream_help_surfaces_required_result_id_argument() -> None:
    result = runner.invoke(app, ["result", "downstream", "--help"])

    assert result.exit_code == 0
    normalized_output = _normalize_cli_output(result.output)
    assert "Show the direct and transitive dependents of a canonical result." in normalized_output
    assert "RESULT_ID" in normalized_output
    assert "Canonical result ID [required]" in normalized_output


def _write_recoverable_result_state(tmp_path: Path, state: dict[str, object]) -> None:
    planning = tmp_path / "GPD"
    planning.mkdir(parents=True, exist_ok=True)
    (planning / "state.json").write_text("{not valid json", encoding="utf-8")
    (planning / STATE_JSON_BACKUP_FILENAME).write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def _write_markdown_recoverable_result_state(tmp_path: Path, state: dict[str, object]) -> None:
    save_state_json(tmp_path, state)
    save_state_markdown(tmp_path, generate_state_markdown(state))
    planning = tmp_path / "GPD"
    (planning / "state.json").write_text("{not valid json", encoding="utf-8")
    (planning / STATE_JSON_BACKUP_FILENAME).write_text("{also not valid json", encoding="utf-8")


@patch("gpd.core.results.result_upsert", create=True)
def test_result_upsert_with_explicit_id(mock_upsert, tmp_path: Path):
    mock_result = MagicMock()
    mock_result.model_dump.return_value = {
        "action": "updated",
        "result": {
            "id": "R-02",
            "equation": "E = mc^2",
            "description": "Energy-mass equivalence",
            "phase": "2",
            "depends_on": ["R-01"],
            "verified": False,
        },
        "updated_fields": ["equation", "description"],
    }
    mock_upsert.return_value = mock_result
    planning = tmp_path / "GPD"
    planning.mkdir()
    (planning / "state.json").write_text("{}", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "--cwd",
            str(tmp_path),
            "result",
            "upsert",
            "--id",
            "R-02",
            "--equation",
            "E = mc^2",
            "--description",
            "Energy-mass equivalence",
            "--phase",
            "2",
            "--depends-on",
            "R-01",
        ],
    )

    assert result.exit_code == 0
    mock_upsert.assert_called_once()
    _, kwargs = mock_upsert.call_args
    assert kwargs["result_id"] == "R-02"
    assert kwargs["equation"] == "E = mc^2"
    assert kwargs["description"] == "Energy-mass equivalence"
    assert kwargs["phase"] == "2"
    assert kwargs["depends_on"] == ["R-01"]


@patch("gpd.core.results.result_upsert", create=True)
def test_result_upsert_without_explicit_id(mock_upsert, tmp_path: Path):
    mock_result = MagicMock()
    mock_result.model_dump.return_value = {
        "action": "updated",
        "updated_fields": ["equation", "description"],
        "result": {
            "id": "R-02",
            "equation": "a = b + c",
            "description": "Canonical quantity",
            "phase": "2",
            "depends_on": ["R-01"],
            "verified": False,
        },
    }
    mock_upsert.return_value = mock_result
    planning = tmp_path / "GPD"
    planning.mkdir()
    (planning / "state.json").write_text("{}", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "--cwd",
            str(tmp_path),
            "result",
            "upsert",
            "--equation",
            "a = b + c",
            "--description",
            "Canonical quantity",
            "--phase",
            "2",
            "--depends-on",
            "R-01",
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    mock_upsert.assert_called_once()
    _, kwargs = mock_upsert.call_args
    assert kwargs["equation"] == "a = b + c"
    assert kwargs["description"] == "Canonical quantity"
    assert kwargs["phase"] == "2"
    assert kwargs["depends_on"] == ["R-01"]


@patch("gpd.core.results.result_upsert", create=True)
def test_result_upsert_recovers_from_malformed_primary_state(mock_upsert, tmp_path: Path) -> None:
    backup_state = default_state_dict()
    backup_state["position"]["current_phase"] = "07"
    backup_state["session"]["last_result_id"] = "R-backup"
    _write_recoverable_result_state(tmp_path, backup_state)

    mock_result = MagicMock()
    mock_result.model_dump.return_value = {
        "action": "updated",
        "updated_fields": ["equation"],
        "result": {
            "id": "R-07",
            "equation": "E = mc^2",
            "description": "Recovered state",
            "phase": "07",
            "depends_on": [],
            "verified": False,
        },
    }
    mock_upsert.return_value = mock_result

    result = runner.invoke(
        app,
        [
            "--cwd",
            str(tmp_path),
            "result",
            "upsert",
            "--id",
            "R-07",
            "--equation",
            "E = mc^2",
            "--description",
            "Recovered state",
            "--phase",
            "07",
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.output
    mock_upsert.assert_called_once()
    state_arg = mock_upsert.call_args.args[0]
    assert state_arg["position"]["current_phase"] == "07"
    assert state_arg["continuation"]["handoff"]["last_result_id"] is None
    assert state_arg["session"]["last_result_id"] is None


@patch("gpd.core.state.save_state_json_locked")
@patch("gpd.core.observability.sync_execution_visibility_from_canonical_continuation", create=True)
@patch("gpd.core.results.result_upsert", create=True)
def test_result_upsert_projects_execution_visibility_after_save(
    mock_upsert,
    mock_sync_visibility,
    mock_save_state,
    tmp_path: Path,
):
    mock_result = MagicMock()
    mock_result.model_dump.return_value = {
        "action": "updated",
        "updated_fields": ["description"],
        "result": {
            "id": "R-02",
            "equation": "a = b + c",
            "description": "Canonical quantity",
            "phase": "2",
            "depends_on": ["R-01"],
            "verified": False,
        },
    }
    mock_upsert.return_value = mock_result
    ordered_calls = MagicMock()
    ordered_calls.attach_mock(mock_save_state, "save")
    ordered_calls.attach_mock(mock_sync_visibility, "sync")
    planning = tmp_path / "GPD"
    planning.mkdir()
    (planning / "state.json").write_text("{}", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "--raw",
            "--cwd",
            str(tmp_path),
            "result",
            "upsert",
            "--id",
            "R-02",
            "--description",
            "Canonical quantity",
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["action"] == "updated"
    assert payload["updated_fields"] == ["description"]
    assert payload["result"]["id"] == "R-02"
    assert payload["result"]["description"] == "Canonical quantity"
    assert "observability_synced" not in payload
    mock_save_state.assert_called_once()
    mock_sync_visibility.assert_called_once()
    sync_args, sync_kwargs = mock_sync_visibility.call_args
    assert sync_args[0] == tmp_path
    assert sync_kwargs["state_obj"] is not None
    save_args, _save_kwargs = mock_save_state.call_args
    assert save_args[0] == tmp_path
    assert save_args[1] is sync_kwargs["state_obj"]
    assert ordered_calls.mock_calls == [
        call.save(tmp_path, ANY),
        call.sync(tmp_path, state_obj=ANY),
    ]


@patch("gpd.core.observability.sync_execution_visibility_from_canonical_continuation", side_effect=RuntimeError("boom"))
@patch("gpd.core.results.result_upsert", create=True)
def test_result_upsert_continues_when_visibility_projection_fails(
    mock_upsert,
    _mock_sync_visibility,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
):
    mock_result = MagicMock()
    mock_result.model_dump.return_value = {
        "action": "updated",
        "updated_fields": ["description"],
        "result": {
            "id": "R-02",
            "equation": "a = b + c",
            "description": "Canonical quantity",
            "phase": "2",
            "depends_on": ["R-01"],
            "verified": False,
        },
    }
    mock_upsert.return_value = mock_result
    planning = tmp_path / "GPD"
    planning.mkdir()
    (planning / "state.json").write_text("{}", encoding="utf-8")

    with caplog.at_level(logging.WARNING, logger="gpd.cli"):
        result = runner.invoke(
            app,
            [
                "--raw",
                "--cwd",
                str(tmp_path),
                "result",
                "upsert",
                "--id",
                "R-02",
                "--description",
                "Canonical quantity",
            ],
            catch_exceptions=False,
        )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["action"] == "updated"
    assert payload["result"]["id"] == "R-02"
    assert payload["result"]["description"] == "Canonical quantity"
    assert any("Failed to sync execution visibility projection" in record.message for record in caplog.records)


@patch("gpd.core.results.result_verify", create=True)
def test_result_verify_recovers_from_malformed_primary_state(mock_verify, tmp_path: Path) -> None:
    backup_state = default_state_dict()
    backup_state["position"]["current_phase"] = "08"
    backup_state["intermediate_results"] = [
        {
            "id": "R-08",
            "equation": "a = b",
            "description": "Recoverable result",
            "phase": "08",
            "depends_on": [],
            "verified": False,
        }
    ]
    _write_recoverable_result_state(tmp_path, backup_state)

    mock_result = MagicMock()
    mock_result.model_dump.return_value = {
        "id": "R-08",
        "equation": "a = b",
        "description": "Recoverable result",
        "phase": "08",
        "depends_on": [],
        "verified": True,
    }
    mock_verify.return_value = mock_result

    result = runner.invoke(
        app,
        [
            "--cwd",
            str(tmp_path),
            "result",
            "verify",
            "R-08",
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.output
    mock_verify.assert_called_once()
    state_arg = mock_verify.call_args.args[0]
    assert state_arg["position"]["current_phase"] == "08"
    assert state_arg["intermediate_results"][0]["id"] == "R-08"


@patch("gpd.cli._resolve_derived_result_id")
@patch("gpd.core.state.state_carry_forward_continuation_last_result_id")
@patch("gpd.core.observability.sync_execution_visibility_from_canonical_continuation", create=True)
@patch("gpd.core.results.result_upsert_derived", create=True)
def test_result_persist_derived_forwards_parsed_options_and_derivation_slug(
    mock_upsert_derived,
    mock_sync_visibility,
    mock_carry_forward,
    mock_resolve,
    tmp_path: Path,
):
    mock_result = MagicMock()
    mock_result.model_dump.return_value = {
        "status": "persisted",
        "result": {
            "id": "R-02",
            "equation": "a = b + c",
            "description": "Canonical quantity",
            "phase": "2",
            "depends_on": ["R-01"],
            "verified": False,
        },
        "updated_fields": ["equation", "description"],
    }
    mock_upsert_derived.return_value = mock_result
    mock_carry_forward.return_value = MagicMock(updated=False)
    mock_resolve.return_value = "R-02-effective-mass"
    ordered_calls = MagicMock()
    ordered_calls.attach_mock(mock_carry_forward, "carry")
    ordered_calls.attach_mock(mock_sync_visibility, "sync")
    planning = tmp_path / "GPD"
    planning.mkdir()
    (planning / "state.json").write_text("{}", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "--cwd",
            str(tmp_path),
            "result",
            "persist-derived",
            "--equation",
            "a = b + c",
            "--description",
            "Canonical quantity",
            "--phase",
            "2",
            "--depends-on",
            "R-01",
            "--derivation-slug",
            "effective-mass",
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.output
    mock_resolve.assert_called_once()
    _, resolve_kwargs = mock_resolve.call_args
    assert resolve_kwargs["result_id"] is None
    assert resolve_kwargs["derivation_slug"] == "effective-mass"
    assert resolve_kwargs["equation"] == "a = b + c"
    assert resolve_kwargs["description"] == "Canonical quantity"
    assert resolve_kwargs["phase"] == "2"

    mock_upsert_derived.assert_called_once()
    _, kwargs = mock_upsert_derived.call_args
    assert kwargs["result_id"] == "R-02-effective-mass"
    assert kwargs["derivation_slug"] == "effective-mass"
    assert kwargs["equation"] == "a = b + c"
    assert kwargs["description"] == "Canonical quantity"
    assert kwargs["phase"] == "2"
    assert kwargs["depends_on"] == ["R-01"]
    mock_carry_forward.assert_called_once()
    carry_args, carry_kwargs = mock_carry_forward.call_args
    assert carry_args[1] == "R-02"
    assert carry_kwargs["state_obj"] is not None
    mock_sync_visibility.assert_called_once()
    sync_args, sync_kwargs = mock_sync_visibility.call_args
    assert sync_args[0] == tmp_path
    assert sync_kwargs["state_obj"] is not None
    assert ordered_calls.mock_calls == [
        call.carry(ANY, "R-02", state_obj=ANY),
        call.sync(ANY, state_obj=ANY),
    ]


@patch("gpd.cli._resolve_derived_result_id")
@patch("gpd.core.state.state_carry_forward_continuation_last_result_id")
@patch("gpd.core.observability.sync_execution_visibility_from_canonical_continuation", create=True)
@patch("gpd.core.results.result_upsert_derived", create=True)
def test_result_persist_derived_auto_seeds_continuity_anchor_from_actual_result_id(
    mock_upsert_derived,
    mock_sync_visibility,
    mock_carry_forward,
    mock_resolve,
    tmp_path: Path,
):
    mock_result = MagicMock()
    mock_result.model_dump.return_value = {
        "status": "persisted",
        "result": {
            "id": "R-01",
            "equation": "a = b + c",
            "description": "Canonical quantity",
            "phase": "2",
            "depends_on": ["R-01"],
            "verified": False,
        },
        "updated_fields": ["equation", "description"],
    }
    mock_upsert_derived.return_value = mock_result
    mock_carry_forward.return_value = MagicMock(updated=True)
    mock_resolve.return_value = "R-02-effective-mass"
    planning = tmp_path / "GPD"
    planning.mkdir()
    (planning / "state.json").write_text("{}", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "--raw",
            "--cwd",
            str(tmp_path),
            "result",
            "persist-derived",
            "--equation",
            "a = b + c",
            "--description",
            "Canonical quantity",
            "--phase",
            "2",
            "--derivation-slug",
            "effective-mass",
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["requested_result_id"] == "R-02-effective-mass"
    assert payload["result_id"] == "R-01"
    assert payload["requested_result_redirected"] is True
    assert payload["continuity_last_result_id"] == "R-01"
    assert payload["continuity_recorded"] is True
    assert "observability_synced" not in payload
    mock_carry_forward.assert_called_once()
    carry_args, carry_kwargs = mock_carry_forward.call_args
    assert carry_args[1] == "R-01"
    assert carry_kwargs["state_obj"] is not None
    mock_sync_visibility.assert_called_once()
    sync_args, sync_kwargs = mock_sync_visibility.call_args
    assert sync_args[0] == tmp_path
    assert sync_kwargs["state_obj"] is not None


def test_result_persist_derived_uses_resolved_result_id_for_real_state_write(
    tmp_path: Path,
    state_project_factory,
) -> None:
    cwd = state_project_factory(tmp_path, current_phase="02", status="Executing")

    first = runner.invoke(
        app,
        [
            "--raw",
            "--cwd",
            str(cwd),
            "result",
            "persist-derived",
            "--equation",
            "a = b + c",
            "--description",
            "Canonical quantity",
            "--phase",
            "2",
            "--derivation-slug",
            "effective-mass",
        ],
        catch_exceptions=False,
    )

    assert first.exit_code == 0, first.output
    first_payload = json.loads(first.output)
    assert first_payload["requested_result_id"] == "R-02-effective-mass"
    assert first_payload["result_id"] == "R-02-effective-mass"
    assert first_payload["requested_result_redirected"] is False
    assert first_payload["result"]["id"] == "R-02-effective-mass"

    second = runner.invoke(
        app,
        [
            "--raw",
            "--cwd",
            str(cwd),
            "result",
            "persist-derived",
            "--equation",
            "a = b + c",
            "--description",
            "Canonical quantity",
            "--phase",
            "2",
            "--derivation-slug",
            "effective-mass",
        ],
        catch_exceptions=False,
    )

    assert second.exit_code == 0, second.output
    second_payload = json.loads(second.output)
    assert second_payload["requested_result_id"] == "R-02-effective-mass"
    assert second_payload["result_id"] == "R-02-effective-mass"
    assert second_payload["requested_result_redirected"] is False
    assert second_payload["continuity_last_result_id"] == "R-02-effective-mass"
    assert second_payload["continuity_recorded"] is False
    assert second_payload["result"]["id"] == "R-02-effective-mass"

    state = json.loads((cwd / "GPD" / "state.json").read_text(encoding="utf-8"))
    assert [item["id"] for item in state["intermediate_results"]] == ["R-02-effective-mass"]
    assert state["session"]["last_result_id"] is None
    assert state["continuation"]["handoff"]["last_result_id"] is None


@patch("gpd.core.results.result_upsert_derived", create=True)
def test_result_persist_derived_recovers_from_markdown_when_json_and_backup_are_unreadable(
    mock_upsert_derived,
    tmp_path: Path,
) -> None:
    recovered_state = default_state_dict()
    recovered_state["position"]["current_phase"] = "11"
    recovered_state["position"]["status"] = "Executing"
    _write_markdown_recoverable_result_state(tmp_path, recovered_state)

    mock_result = MagicMock()
    mock_result.model_dump.return_value = {
        "status": "persisted",
        "result": {
            "id": "R-11-effective-mass",
            "equation": "a = b + c",
            "description": "Markdown recovery",
            "phase": "11",
            "depends_on": [],
            "verified": False,
        },
        "updated_fields": ["equation", "description"],
    }
    mock_upsert_derived.return_value = mock_result

    result = runner.invoke(
        app,
        [
            "--cwd",
            str(tmp_path),
            "result",
            "persist-derived",
            "--equation",
            "a = b + c",
            "--description",
            "Markdown recovery",
            "--phase",
            "11",
            "--derivation-slug",
            "effective-mass",
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.output
    mock_upsert_derived.assert_called_once()
    state_arg = mock_upsert_derived.call_args.args[0]
    assert state_arg["position"]["current_phase"] == "11"
    assert state_arg["position"]["status"] == "Executing"


@patch("gpd.core.results.result_update", create=True)
def test_result_update_recovers_from_malformed_primary_state(mock_result_update, tmp_path: Path) -> None:
    backup_state = default_state_dict()
    backup_state["position"]["current_phase"] = "09"
    backup_state["intermediate_results"] = [
        {
            "id": "R-09",
            "equation": "a = b + c",
            "description": "Recoverable update target",
            "phase": "09",
            "depends_on": ["R-08"],
            "verified": False,
        }
    ]
    _write_recoverable_result_state(tmp_path, backup_state)

    mock_result = MagicMock()
    mock_result.model_dump.return_value = {
        "id": "R-09",
        "equation": "a = b + c",
        "description": "Updated recoverable result",
        "phase": "09",
        "depends_on": ["R-08"],
        "verified": False,
    }
    mock_result_update.return_value = (["description"], mock_result)

    result = runner.invoke(
        app,
        [
            "--cwd",
            str(tmp_path),
            "result",
            "update",
            "R-09",
            "--description",
            "Updated recoverable result",
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.output
    mock_result_update.assert_called_once()
    state_arg = mock_result_update.call_args.args[0]
    assert state_arg["position"]["current_phase"] == "09"
    assert state_arg["intermediate_results"][0]["id"] == "R-09"


@patch("gpd.core.results.result_add", create=True)
def test_result_add_recovers_from_malformed_primary_state(mock_result_add, tmp_path: Path) -> None:
    backup_state = default_state_dict()
    backup_state["position"]["current_phase"] = "10"
    backup_state["session"]["last_result_id"] = "R-recovered"
    _write_recoverable_result_state(tmp_path, backup_state)

    mock_result = MagicMock()
    mock_result.model_dump.return_value = {
        "id": "R-10",
        "equation": "a = b + c",
        "description": "Recovered add target",
        "phase": "10",
        "depends_on": [],
        "verified": False,
    }
    mock_result_add.return_value = mock_result

    result = runner.invoke(
        app,
        [
            "--cwd",
            str(tmp_path),
            "result",
            "add",
            "--id",
            "R-10",
            "--equation",
            "a = b + c",
            "--description",
            "Recovered add target",
            "--phase",
            "10",
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.output
    mock_result_add.assert_called_once()
    state_arg = mock_result_add.call_args.args[0]
    assert state_arg["position"]["current_phase"] == "10"
    assert state_arg["continuation"]["handoff"]["last_result_id"] is None
    assert state_arg["session"]["last_result_id"] is None


@pytest.mark.parametrize(
    ("patch_target", "argv"),
    [
        ("gpd.core.extras.approximation_add", ["approximation", "add", "adiabatic"]),
        ("gpd.core.extras.uncertainty_add", ["uncertainty", "add", "mass", "--phase", "10"]),
        ("gpd.core.extras.question_add", ["question", "add", "Why", "does", "it", "drift?"]),
        ("gpd.core.extras.question_resolve", ["question", "resolve", "Why", "does", "it", "drift?"]),
        ("gpd.core.extras.calculation_add", ["calculation", "add", "Evaluate", "kernel"]),
        ("gpd.core.extras.calculation_complete", ["calculation", "complete", "Evaluate", "kernel"]),
    ],
)
def test_auxiliary_mutation_commands_recover_from_malformed_primary_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    patch_target: str,
    argv: list[str],
) -> None:
    backup_state = default_state_dict()
    backup_state["position"]["current_phase"] = "10"
    backup_state["session"]["last_result_id"] = "R-recovered"
    _write_recoverable_result_state(tmp_path, backup_state)

    captured: dict[str, object] = {}

    def _fake_mutation(state: dict[str, object], *args: object, **kwargs: object) -> str:
        captured["state"] = state
        captured["args"] = args
        captured["kwargs"] = kwargs
        return "ok"

    monkeypatch.setattr(patch_target, _fake_mutation)

    result = runner.invoke(
        app,
        ["--cwd", str(tmp_path), *argv],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.output
    state_arg = captured["state"]
    assert isinstance(state_arg, dict)
    assert state_arg["position"]["current_phase"] == "10"
    assert state_arg["continuation"]["handoff"]["last_result_id"] is None
    assert state_arg["session"]["last_result_id"] is None


@patch("gpd.core.state.save_state_json_locked")
def test_convention_set_fails_closed_for_malformed_primary_state(
    mock_save_state_json_locked,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    backup_state = default_state_dict()
    backup_state["position"]["current_phase"] = "10"
    backup_state["session"]["last_result_id"] = "R-recovered"
    _write_recoverable_result_state(tmp_path, backup_state)

    def _fake_convention_set(lock: object, key: str, value: str, *, force: bool = False) -> object:
        setattr(lock, key, value)
        return SimpleNamespace(updated=True)

    monkeypatch.setattr("gpd.core.conventions.convention_set", _fake_convention_set)

    result = runner.invoke(
        app,
        ["--cwd", str(tmp_path), "convention", "set", "metric_signature", "mostly-plus"],
        catch_exceptions=False,
    )

    assert result.exit_code == 1, result.output
    assert "Malformed state.json" in result.output
    mock_save_state_json_locked.assert_not_called()


@patch("gpd.core.state.save_state_json_locked")
@patch("gpd.core.observability.sync_execution_visibility_from_canonical_continuation", create=True)
@patch("gpd.core.results.result_update", create=True)
def test_result_update_projects_execution_visibility_after_save(
    mock_result_update,
    mock_sync_visibility,
    mock_save_state,
    tmp_path: Path,
):
    mock_result = MagicMock()
    mock_result.model_dump.return_value = {
        "id": "R-02",
        "equation": "a = b + c",
        "description": "Updated quantity",
        "phase": "2",
        "depends_on": ["R-01"],
        "verified": False,
    }
    mock_result_update.return_value = (["description"], mock_result)
    ordered_calls = MagicMock()
    ordered_calls.attach_mock(mock_save_state, "save")
    ordered_calls.attach_mock(mock_sync_visibility, "sync")
    planning = tmp_path / "GPD"
    planning.mkdir()
    (planning / "state.json").write_text("{}", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "--raw",
            "--cwd",
            str(tmp_path),
            "result",
            "update",
            "R-02",
            "--description",
            "Updated quantity",
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    mock_result_update.assert_called_once()
    assert payload["id"] == "R-02"
    assert payload["description"] == "Updated quantity"
    assert payload["equation"] == "a = b + c"
    assert "observability_synced" not in payload
    mock_save_state.assert_called_once()
    mock_sync_visibility.assert_called_once()
    sync_args, sync_kwargs = mock_sync_visibility.call_args
    assert sync_args[0] == tmp_path
    assert sync_kwargs["state_obj"] is not None
    save_args, _save_kwargs = mock_save_state.call_args
    assert save_args[0] == tmp_path
    assert save_args[1] is sync_kwargs["state_obj"]
    assert ordered_calls.mock_calls == [
        call.save(tmp_path, ANY),
        call.sync(tmp_path, state_obj=ANY),
    ]


def test_result_persist_derived_raw_skips_cleanly_without_project_state(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "--raw",
            "--cwd",
            str(tmp_path),
            "result",
            "persist-derived",
            "--equation",
            "a = b + c",
            "--description",
            "Canonical quantity",
            "--phase",
            "2",
            "--derivation-slug",
            "effective-mass",
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "skipped"
    assert payload["reason"] == "no_recoverable_project_state"
    assert payload["state_exists"] is False
    assert payload["recoverable_state_exists"] is False
    assert not (tmp_path / "GPD" / "state.json").exists()


# ─── query subcommands ──────────────────────────────────────────────────────


@patch("gpd.core.query.query_deps")
def test_query_deps(mock_deps):
    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"deps": []}
    mock_deps.return_value = mock_result
    result = runner.invoke(app, ["query", "deps", "42"])
    assert result.exit_code == 0
    mock_deps.assert_called_once()


# ─── health / doctor ────────────────────────────────────────────────────────


@patch("gpd.core.health.run_health")
def test_health(mock_health):
    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"passed": True, "checks": []}
    mock_health.return_value = mock_result
    result = runner.invoke(app, ["health"])
    assert result.exit_code == 0
    mock_health.assert_called_once()


@patch("gpd.core.health.run_doctor")
def test_doctor(mock_doctor):
    from gpd.specs import SPECS_DIR

    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"ok": True}
    mock_doctor.return_value = mock_result
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    mock_doctor.assert_called_once()
    assert mock_doctor.call_args.kwargs == {
        "specs_dir": SPECS_DIR,
        "live_executable_probes": False,
    }


def test_doctor_live_executable_probes_pass_through(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from gpd.specs import SPECS_DIR

    captured: dict[str, object] = {}

    def fake_run_doctor(
        *,
        specs_dir: Path | None = None,
        version: str | None = None,
        runtime: str | None = None,
        install_scope: str | None = None,
        target_dir: str | Path | None = None,
        cwd: Path | None = None,
        live_executable_probes: bool = False,
    ) -> MagicMock:
        captured["kwargs"] = {
            "specs_dir": specs_dir,
            "version": version,
            "runtime": runtime,
            "install_scope": install_scope,
            "target_dir": target_dir,
            "cwd": cwd,
            "live_executable_probes": live_executable_probes,
        }
        mock_result = MagicMock()
        mock_result.model_dump.return_value = {"mode": "runtime-readiness", "overall": "ok"}
        return mock_result

    monkeypatch.setattr("gpd.core.health.run_doctor", fake_run_doctor)

    result = runner.invoke(app, ["--cwd", str(tmp_path), "--raw", "doctor", "--live-executable-probes"])

    assert result.exit_code == 0
    assert json.loads(result.output) == {"mode": "runtime-readiness", "overall": "ok"}
    assert captured["kwargs"] == {
        "specs_dir": SPECS_DIR,
        "version": None,
        "runtime": None,
        "install_scope": None,
        "target_dir": None,
        "cwd": None,
        "live_executable_probes": True,
    }


@patch("gpd.core.health.run_doctor")
def test_doctor_runtime_mode_uses_run_doctor(mock_doctor, tmp_path: Path) -> None:
    from gpd.specs import SPECS_DIR

    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"mode": "runtime-readiness", "overall": "ok"}
    mock_doctor.return_value = mock_result

    result = runner.invoke(app, ["--cwd", str(tmp_path), "--raw", "doctor", "--runtime", PRIMARY_RUNTIME, "--local"])

    assert result.exit_code == 0
    assert json.loads(result.output) == {"mode": "runtime-readiness", "overall": "ok"}
    mock_doctor.assert_called_once_with(
        specs_dir=SPECS_DIR,
        runtime=PRIMARY_RUNTIME,
        install_scope="local",
        target_dir=None,
        cwd=tmp_path,
        live_executable_probes=False,
    )


@patch("gpd.core.health.run_doctor")
def test_doctor_runtime_readiness_mode(mock_doctor, tmp_path: Path):
    from gpd.specs import SPECS_DIR

    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"mode": "runtime-readiness", "overall": "ok"}
    mock_doctor.return_value = mock_result
    runtime_name = list_runtimes()[0]

    result = runner.invoke(app, ["--cwd", str(tmp_path), "--raw", "doctor", "--runtime", runtime_name, "--global"])

    assert result.exit_code == 0
    assert json.loads(result.output) == {"mode": "runtime-readiness", "overall": "ok"}
    mock_doctor.assert_called_once_with(
        specs_dir=SPECS_DIR,
        runtime=runtime_name,
        install_scope="global",
        target_dir=None,
        cwd=tmp_path,
        live_executable_probes=False,
    )


@patch("gpd.core.health.run_doctor")
def test_doctor_target_dir_infers_install_scope(mock_doctor, tmp_path: Path) -> None:
    from gpd.specs import SPECS_DIR

    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"mode": "runtime-readiness", "overall": "ok"}
    mock_doctor.return_value = mock_result
    runtime_name = list_runtimes()[0]
    target_dir = tmp_path / ".gpd-target"

    with patch("gpd.cli._target_dir_matches_global", return_value=True) as mock_matches_global:
        result = runner.invoke(
            app,
            ["--cwd", str(tmp_path), "--raw", "doctor", "--runtime", runtime_name, "--target-dir", str(target_dir)],
        )

    assert result.exit_code == 0
    assert json.loads(result.output) == {"mode": "runtime-readiness", "overall": "ok"}
    mock_matches_global.assert_called_once_with(runtime_name, str(target_dir), action="doctor")
    mock_doctor.assert_called_once_with(
        specs_dir=SPECS_DIR,
        runtime=runtime_name,
        install_scope="global",
        target_dir=target_dir.resolve(strict=False),
        cwd=tmp_path,
        live_executable_probes=False,
    )


@patch("gpd.core.health.run_doctor")
def test_doctor_target_dir_stays_local_when_target_is_not_global(mock_doctor, tmp_path: Path) -> None:
    from gpd.specs import SPECS_DIR

    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"mode": "runtime-readiness", "overall": "ok"}
    mock_doctor.return_value = mock_result
    runtime_name = list_runtimes()[0]
    target_dir = tmp_path / ".gpd-target"

    with patch("gpd.cli._target_dir_matches_global", return_value=False) as mock_matches_global:
        result = runner.invoke(
            app,
            ["--cwd", str(tmp_path), "--raw", "doctor", "--runtime", runtime_name, "--target-dir", str(target_dir)],
        )

    assert result.exit_code == 0
    assert json.loads(result.output) == {"mode": "runtime-readiness", "overall": "ok"}
    mock_matches_global.assert_called_once_with(runtime_name, str(target_dir), action="doctor")
    mock_doctor.assert_called_once_with(
        specs_dir=SPECS_DIR,
        runtime=runtime_name,
        install_scope="local",
        target_dir=target_dir.resolve(strict=False),
        cwd=tmp_path,
        live_executable_probes=False,
    )


@patch("gpd.core.health.run_doctor")
def test_doctor_runtime_mode_defaults_to_local_target_when_scope_is_unspecified(
    mock_doctor, tmp_path: Path
) -> None:
    from gpd.specs import SPECS_DIR

    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"mode": "runtime-readiness", "overall": "ok"}
    mock_doctor.return_value = mock_result
    runtime_name = list_runtimes()[0]
    local_target = cli_module._get_adapter_or_error(runtime_name, action="doctor").resolve_target_dir(False, tmp_path)

    with patch(
        "gpd.hooks.runtime_detect.detect_runtime_install_target",
        return_value=SimpleNamespace(config_dir=tmp_path / "runtime-global-target", install_scope="global"),
    ):
        result = runner.invoke(app, ["--cwd", str(tmp_path), "--raw", "doctor", "--runtime", runtime_name])

    assert result.exit_code == 0
    assert json.loads(result.output) == {"mode": "runtime-readiness", "overall": "ok"}
    mock_doctor.assert_called_once_with(
        specs_dir=SPECS_DIR,
        runtime=runtime_name,
        install_scope="local",
        target_dir=local_target,
        cwd=tmp_path,
        live_executable_probes=False,
    )


def test_doctor_rejects_scope_without_runtime() -> None:
    result = runner.invoke(app, ["doctor", "--global"])

    assert result.exit_code == 1
    assert "--runtime is required" in result.output


def test_doctor_rejects_target_dir_without_runtime(tmp_path: Path) -> None:
    result = runner.invoke(app, ["doctor", "--target-dir", str(tmp_path / ".gpd-target")])

    assert result.exit_code == 1
    assert "--runtime is required" in result.output


def test_validate_unattended_readiness_requires_runtime() -> None:
    result = runner.invoke(app, ["validate", "unattended-readiness"])

    assert result.exit_code != 0
    assert "--runtime" in _normalize_cli_output(result.output)


def test_validate_unattended_readiness_wires_local_runtime_scope_through_health_builder(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from gpd.specs import SPECS_DIR

    runtime_name = list_runtimes()[0]
    expected_target = get_adapter(runtime_name).resolve_target_dir(False, tmp_path)
    captured: dict[str, object] = {}
    doctor_report = DoctorReport(
        overall=CheckStatus.WARN,
        version="0.1.0",
        runtime=runtime_name,
        install_scope="local",
        target=str(expected_target),
        summary=HealthSummary(ok=1, warn=1, fail=0, total=2),
        checks=[
            HealthCheck(status=CheckStatus.OK, label="Runtime Launcher"),
            HealthCheck(status=CheckStatus.WARN, label="LaTeX Toolchain", warnings=["LaTeX toolchain is partial."]),
        ],
    )
    permissions_payload = {
        "runtime": runtime_name,
        "target": str(expected_target),
        "autonomy": "balanced",
        "readiness": "ready",
        "ready": True,
        "readiness_message": "Runtime permissions are ready for unattended use.",
        "next_step": "",
        "status_scope": "config-only",
        "current_session_verified": False,
    }
    expected_result = UnattendedReadinessResult(
        runtime=runtime_name,
        autonomy="balanced",
        install_scope="local",
        target=str(expected_target),
        readiness="ready",
        ready=True,
        passed=True,
        readiness_message="Runtime permissions are ready for unattended use.",
        live_executable_probes=False,
        checks=[
            UnattendedReadinessCheck(
                name="permissions",
                passed=True,
                blocking=False,
                detail="Runtime permissions are ready for unattended use.",
            )
        ],
        blocking_conditions=[],
        warnings=["LaTeX toolchain is partial."],
        status_scope="config-only",
        current_session_verified=False,
        validated_surface="runtime-surface-test",
    )

    def fake_run_doctor(
        *,
        specs_dir: Path | None = None,
        version: str | None = None,
        runtime: str | None = None,
        install_scope: str | None = None,
        target_dir: str | Path | None = None,
        cwd: Path | None = None,
        live_executable_probes: bool = False,
    ) -> MagicMock:
        captured["doctor_kwargs"] = {
            "specs_dir": specs_dir,
            "version": version,
            "runtime": runtime,
            "install_scope": install_scope,
            "target_dir": target_dir,
            "cwd": cwd,
            "live_executable_probes": live_executable_probes,
        }
        return doctor_report

    def fake_permissions_status_payload(*, runtime: str | None, autonomy: str | None, target_dir: str | None) -> dict[str, object]:
        captured["permissions_kwargs"] = {
            "runtime": runtime,
            "autonomy": autonomy,
            "target_dir": target_dir,
        }
        return permissions_payload

    def fake_build_unattended_readiness_result(**kwargs) -> UnattendedReadinessResult:
        captured["builder_kwargs"] = kwargs
        return expected_result

    monkeypatch.setattr("gpd.core.health.run_doctor", fake_run_doctor)
    monkeypatch.setattr("gpd.core.health.build_unattended_readiness_result", fake_build_unattended_readiness_result)
    monkeypatch.setattr(cli_module, "_permissions_status_payload", fake_permissions_status_payload)
    monkeypatch.setattr(cli_module, "_validated_runtime_surface", lambda cwd=None: "runtime-surface-test")
    result = runner.invoke(
        app,
        ["--cwd", str(tmp_path), "--raw", "validate", "unattended-readiness", "--runtime", runtime_name, "--local"],
    )

    assert result.exit_code == 0
    assert json.loads(result.output) == {
        "runtime": runtime_name,
        "autonomy": "balanced",
        "install_scope": "local",
        "target": str(expected_target),
        "readiness": "ready",
        "ready": True,
        "passed": True,
        "readiness_message": "Runtime permissions are ready for unattended use.",
        "live_executable_probes": False,
        "checks": [
            {
                "name": "permissions",
                "passed": True,
                "blocking": False,
                "detail": "Runtime permissions are ready for unattended use.",
            }
        ],
        "blocking_conditions": [],
        "warnings": ["LaTeX toolchain is partial."],
        "next_step": "",
        "status_scope": "config-only",
        "current_session_verified": False,
        "validated_surface": "runtime-surface-test",
    }
    assert captured["doctor_kwargs"] == {
        "specs_dir": SPECS_DIR,
        "version": None,
        "runtime": runtime_name,
        "install_scope": "local",
        "target_dir": None,
        "cwd": tmp_path,
        "live_executable_probes": False,
    }
    assert captured["permissions_kwargs"] == {
        "runtime": runtime_name,
        "autonomy": None,
        "target_dir": str(expected_target),
    }
    assert captured["builder_kwargs"] == {
        "runtime": runtime_name,
        "autonomy": None,
        "install_scope": "local",
        "target_dir": None,
        "doctor_report": doctor_report,
        "permissions_payload": permissions_payload,
        "live_executable_probes": False,
        "validated_surface": "runtime-surface-test",
    }


def test_validate_unattended_readiness_uses_detected_installed_target_when_scope_is_unspecified(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from gpd.specs import SPECS_DIR

    runtime_name = list_runtimes()[0]
    detected_target = tmp_path / "runtime-global-target"
    doctor_report = DoctorReport(
        overall=CheckStatus.OK,
        version="0.1.0",
        runtime=runtime_name,
        install_scope="global",
        target=str(detected_target),
        summary=HealthSummary(ok=2, warn=0, fail=0, total=2),
        checks=[
            HealthCheck(status=CheckStatus.OK, label="Runtime Launcher"),
            HealthCheck(status=CheckStatus.OK, label="Runtime Config Target"),
        ],
    )
    permissions_payload = {
        "runtime": runtime_name,
        "target": str(detected_target),
        "autonomy": "balanced",
        "readiness": "ready",
        "ready": True,
        "readiness_message": "Runtime permissions are ready for unattended use.",
        "next_step": "",
        "status_scope": "config-only",
        "current_session_verified": False,
    }
    expected_result = UnattendedReadinessResult(
        runtime=runtime_name,
        autonomy="balanced",
        install_scope="global",
        target=str(detected_target),
        readiness="ready",
        ready=True,
        passed=True,
        readiness_message="Runtime permissions are ready for unattended use.",
        live_executable_probes=False,
        checks=[
            UnattendedReadinessCheck(
                name="permissions",
                passed=True,
                blocking=False,
                detail="Runtime permissions are ready for unattended use.",
            )
        ],
        blocking_conditions=[],
        warnings=[],
        next_step="",
        status_scope="config-only",
        current_session_verified=False,
        validated_surface="runtime-surface-test",
    )

    captured: dict[str, object] = {}

    def fake_run_doctor(
        *,
        specs_dir: Path | None = None,
        version: str | None = None,
        runtime: str | None = None,
        install_scope: str | None = None,
        target_dir: str | Path | None = None,
        cwd: Path | None = None,
        live_executable_probes: bool = False,
    ) -> MagicMock:
        captured["doctor_kwargs"] = {
            "specs_dir": specs_dir,
            "version": version,
            "runtime": runtime,
            "install_scope": install_scope,
            "target_dir": target_dir,
            "cwd": cwd,
            "live_executable_probes": live_executable_probes,
        }
        return doctor_report

    def fake_permissions_status_payload(*, runtime: str | None, autonomy: str | None, target_dir: str | None) -> dict[str, object]:
        captured["permissions_kwargs"] = {
            "runtime": runtime,
            "autonomy": autonomy,
            "target_dir": target_dir,
        }
        return permissions_payload

    def fake_build_unattended_readiness_result(**kwargs) -> UnattendedReadinessResult:
        captured["builder_kwargs"] = kwargs
        return expected_result

    monkeypatch.setattr("gpd.core.health.run_doctor", fake_run_doctor)
    monkeypatch.setattr("gpd.core.health.build_unattended_readiness_result", fake_build_unattended_readiness_result)
    monkeypatch.setattr(cli_module, "_permissions_status_payload", fake_permissions_status_payload)
    monkeypatch.setattr(cli_module, "_validated_runtime_surface", lambda cwd=None: "runtime-surface-test")

    with patch(
        "gpd.hooks.runtime_detect.detect_runtime_install_target",
        return_value=SimpleNamespace(config_dir=detected_target, install_scope="global"),
    ):
        result = runner.invoke(
            app,
            ["--cwd", str(tmp_path), "--raw", "validate", "unattended-readiness", "--runtime", runtime_name],
        )

    assert result.exit_code == 0
    assert json.loads(result.output) == {
        "runtime": runtime_name,
        "autonomy": "balanced",
        "install_scope": "global",
        "target": str(detected_target),
        "readiness": "ready",
        "ready": True,
        "passed": True,
        "readiness_message": "Runtime permissions are ready for unattended use.",
        "live_executable_probes": False,
        "checks": [
            {
                "name": "permissions",
                "passed": True,
                "blocking": False,
                "detail": "Runtime permissions are ready for unattended use.",
            }
        ],
        "blocking_conditions": [],
        "warnings": [],
        "next_step": "",
        "status_scope": "config-only",
        "current_session_verified": False,
        "validated_surface": "runtime-surface-test",
    }
    assert captured["doctor_kwargs"] == {
        "specs_dir": SPECS_DIR,
        "version": None,
        "runtime": runtime_name,
        "install_scope": "global",
        "target_dir": detected_target,
        "cwd": tmp_path,
        "live_executable_probes": False,
    }
    assert captured["permissions_kwargs"] == {
        "runtime": runtime_name,
        "autonomy": None,
        "target_dir": str(detected_target),
    }
    assert captured["builder_kwargs"] == {
        "runtime": runtime_name,
        "autonomy": None,
        "install_scope": "global",
        "target_dir": detected_target,
        "doctor_report": doctor_report,
        "permissions_payload": permissions_payload,
        "live_executable_probes": False,
        "validated_surface": "runtime-surface-test",
    }


def test_validate_unattended_readiness_infers_global_target_scope_and_propagates_failed_result(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from gpd.specs import SPECS_DIR

    runtime_name = list_runtimes()[0]
    target_dir = tmp_path / ".gpd-target"
    resolved_target = target_dir.resolve(strict=False)
    captured: dict[str, object] = {}
    doctor_report = DoctorReport(
        overall=CheckStatus.FAIL,
        version="0.1.0",
        runtime=runtime_name,
        install_scope="global",
        target=str(resolved_target),
        live_executable_probes=True,
        summary=HealthSummary(ok=0, warn=1, fail=1, total=2),
        checks=[
            HealthCheck(status=CheckStatus.FAIL, label="Runtime Launcher", issues=["Runtime launcher not found on PATH"]),
            HealthCheck(status=CheckStatus.WARN, label="LaTeX Toolchain", warnings=["LaTeX toolchain is partial."]),
        ],
    )
    permissions_payload = {
        "runtime": runtime_name,
        "target": str(resolved_target),
        "autonomy": "balanced",
        "readiness": "ready",
        "ready": True,
        "readiness_message": "Runtime permissions are ready for unattended use.",
        "next_step": "",
        "status_scope": "config-only",
        "current_session_verified": False,
    }
    expected_result = UnattendedReadinessResult(
        runtime=runtime_name,
        autonomy="balanced",
        install_scope="global",
        target=str(resolved_target),
        readiness="ready",
        ready=True,
        passed=False,
        readiness_message="Runtime permissions are ready for unattended use.",
        live_executable_probes=True,
        checks=[
            UnattendedReadinessCheck(
                name="doctor",
                passed=False,
                blocking=True,
                detail="Runtime launcher not found on PATH",
            )
        ],
        blocking_conditions=["Runtime launcher not found on PATH"],
        warnings=["LaTeX toolchain is partial."],
        next_step="Inspect the runtime-specific doctor output before retrying unattended use.",
        status_scope="config-only",
        current_session_verified=False,
        validated_surface="runtime-surface-test",
    )

    def fake_run_doctor(
        *,
        specs_dir: Path | None = None,
        version: str | None = None,
        runtime: str | None = None,
        install_scope: str | None = None,
        target_dir: str | Path | None = None,
        cwd: Path | None = None,
        live_executable_probes: bool = False,
    ) -> MagicMock:
        captured["doctor_kwargs"] = {
            "specs_dir": specs_dir,
            "version": version,
            "runtime": runtime,
            "install_scope": install_scope,
            "target_dir": target_dir,
            "cwd": cwd,
            "live_executable_probes": live_executable_probes,
        }
        return doctor_report

    def fake_permissions_status_payload(*, runtime: str | None, autonomy: str | None, target_dir: str | None) -> dict[str, object]:
        captured["permissions_kwargs"] = {
            "runtime": runtime,
            "autonomy": autonomy,
            "target_dir": target_dir,
        }
        return permissions_payload

    def fake_build_unattended_readiness_result(**kwargs) -> UnattendedReadinessResult:
        captured["builder_kwargs"] = kwargs
        return expected_result

    monkeypatch.setattr("gpd.core.health.run_doctor", fake_run_doctor)
    monkeypatch.setattr("gpd.core.health.build_unattended_readiness_result", fake_build_unattended_readiness_result)
    monkeypatch.setattr(cli_module, "_permissions_status_payload", fake_permissions_status_payload)
    monkeypatch.setattr(cli_module, "_validated_runtime_surface", lambda cwd=None: "runtime-surface-test")
    with patch("gpd.cli._target_dir_matches_global", return_value=True) as mock_matches_global:
        result = runner.invoke(
            app,
            [
                "--cwd",
                str(tmp_path),
                "--raw",
                "validate",
                "unattended-readiness",
                "--runtime",
                runtime_name,
                "--target-dir",
                str(target_dir),
                "--live-executable-probes",
            ],
        )

    assert result.exit_code == 1
    mock_matches_global.assert_called_once_with(runtime_name, str(target_dir), action="validate unattended-readiness")
    assert json.loads(result.output) == {
        "runtime": runtime_name,
        "autonomy": "balanced",
        "install_scope": "global",
        "target": str(resolved_target),
        "readiness": "ready",
        "ready": True,
        "passed": False,
        "readiness_message": "Runtime permissions are ready for unattended use.",
        "live_executable_probes": True,
        "checks": [
            {
                "name": "doctor",
                "passed": False,
                "blocking": True,
                "detail": "Runtime launcher not found on PATH",
            }
        ],
        "blocking_conditions": ["Runtime launcher not found on PATH"],
        "warnings": ["LaTeX toolchain is partial."],
        "next_step": "Inspect the runtime-specific doctor output before retrying unattended use.",
        "status_scope": "config-only",
        "current_session_verified": False,
        "validated_surface": "runtime-surface-test",
    }
    assert captured["doctor_kwargs"] == {
        "specs_dir": SPECS_DIR,
        "version": None,
        "runtime": runtime_name,
        "install_scope": "global",
        "target_dir": resolved_target,
        "cwd": tmp_path,
        "live_executable_probes": True,
    }
    assert captured["permissions_kwargs"] == {
        "runtime": runtime_name,
        "autonomy": None,
        "target_dir": str(resolved_target),
    }
    assert captured["builder_kwargs"] == {
        "runtime": runtime_name,
        "autonomy": None,
        "install_scope": "global",
        "target_dir": resolved_target,
        "doctor_report": doctor_report,
        "permissions_payload": permissions_payload,
        "live_executable_probes": True,
        "validated_surface": "runtime-surface-test",
    }


def test_runtime_surface_helpers_track_the_active_runtime_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime_name = list_runtimes()[0]
    adapter = get_adapter(runtime_name)
    prefix = adapter.command_prefix
    workspace = Path("/tmp/runtime-surface")

    monkeypatch.setattr(cli_module, "detect_runtime_for_gpd_use", lambda cwd=None: runtime_name)
    monkeypatch.setattr("gpd.hooks.runtime_detect.detect_runtime_for_gpd_use", lambda cwd=None: runtime_name)

    assert cli_module._active_runtime_command_prefix(cwd=workspace) == prefix
    assert cli_module._active_runtime_command_family(cwd=workspace) == prefix
    assert cli_module._active_runtime_new_project_command(cwd=workspace) == adapter.format_command("new-project")
    assert cli_module._runtime_surface_dispatch_note(cwd=workspace) == (
        f"This preflight validates the public command surface rooted at `{prefix}` from the command registry. "
        "It does not guarantee a same-name local `gpd` subcommand exists."
    )

    validated_surface = cli_module._validated_runtime_surface(cwd=workspace)
    assert validated_surface == adapter.runtime_descriptor.validated_command_surface


def test_runtime_surface_helpers_fall_back_when_runtime_resolution_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = Path("/tmp/runtime-surface-fallback")
    monkeypatch.setattr(cli_module, "detect_runtime_for_gpd_use", lambda cwd=None: None)
    monkeypatch.setattr("gpd.hooks.runtime_detect.detect_runtime_for_gpd_use", lambda cwd=None: None)

    assert cli_module._active_runtime_command_prefix(cwd=workspace) is None
    assert cli_module._active_runtime_command_family(cwd=workspace) == "the active runtime command surface"
    assert cli_module._active_runtime_new_project_command(cwd=workspace) == "the active runtime's `new-project` command"
    assert cli_module._runtime_surface_dispatch_note(cwd=workspace) == (
        "This preflight validates the active runtime command surface from the command registry. "
        "It does not guarantee a same-name local `gpd` subcommand exists."
    )
    assert cli_module._validated_runtime_surface(cwd=workspace) == "public_runtime_command_surface"


def test_runtime_surface_helpers_fall_back_on_unexpected_detection_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = Path("/tmp/runtime-surface-failure")

    def _raise_runtime_error(cwd=None) -> str:
        raise RuntimeError("runtime resolution failed")

    monkeypatch.setattr(cli_module, "detect_runtime_for_gpd_use", _raise_runtime_error)
    assert cli_module._active_runtime_command_prefix(cwd=workspace) is None
    assert cli_module._active_runtime_validated_surface(cwd=workspace) is None
    assert cli_module._active_runtime_new_project_command(cwd=workspace) == "the active runtime's `new-project` command"


# ─── trace subcommands ──────────────────────────────────────────────────────


@patch("gpd.core.trace.trace_start")
def test_trace_start(mock_start):
    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"started": True}
    mock_start.return_value = mock_result
    result = runner.invoke(app, ["trace", "start", "42", "plan-a"])
    assert result.exit_code == 0
    mock_start.assert_called_once()


@patch("gpd.core.trace.trace_stop")
def test_trace_stop(mock_stop):
    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"stopped": True}
    mock_stop.return_value = mock_result
    result = runner.invoke(app, ["trace", "stop"])
    assert result.exit_code == 0
    mock_stop.assert_called_once()


def test_observe_sessions_reads_local_metadata(tmp_path: Path) -> None:
    planning = tmp_path / "GPD" / "observability" / "sessions"
    planning.mkdir(parents=True)
    (planning / "cli-session-1.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "timestamp": "2026-03-10T00:00:00+00:00",
                        "event_id": "evt-1",
                        "session_id": "cli-session-1",
                        "category": "session",
                        "name": "lifecycle",
                        "action": "start",
                        "status": "active",
                        "command": "timestamp",
                        "data": {"cwd": str(tmp_path), "source": "cli", "pid": 123, "metadata": {}},
                    }
                ),
                json.dumps(
                    {
                        "timestamp": "2026-03-10T00:00:01+00:00",
                        "event_id": "evt-2",
                        "session_id": "cli-session-1",
                        "category": "session",
                        "name": "lifecycle",
                        "action": "finish",
                        "status": "ok",
                        "command": "timestamp",
                        "data": {"ended_at": "2026-03-10T00:00:01+00:00", "ended_by": {"name": "command"}},
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["--raw", "--cwd", str(tmp_path), "observe", "sessions"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["count"] >= 1
    assert any(session["session_id"] == "cli-session-1" for session in payload["sessions"])
    assert any(session.get("command") == "timestamp" for session in payload["sessions"])


def test_observe_execution_raw_reads_local_visibility_snapshot(tmp_path: Path) -> None:
    observability = tmp_path / "GPD" / "observability"
    observability.mkdir(parents=True)
    (observability / "current-execution.json").write_text(
        json.dumps(
            {
                "session_id": "cli-session-1",
                "phase": "03",
                "plan": "02",
                "segment_status": "active",
                "current_task": "Benchmark reproduction",
                "updated_at": "2000-01-01T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["--raw", "--cwd", str(tmp_path), "observe", "execution"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["found"] is True
    assert payload["status_classification"] == "active"
    assert payload["assessment"] == "possibly stalled"
    assert payload["possibly_stalled"] is True
    assert payload["stale_after_minutes"] == 30
    assert payload["current_task"] == "Benchmark reproduction"
    assert payload["next_check_command"] == "gpd observe show --session cli-session-1 --last 20"
    assert "execution event trail" in payload["next_check_reason"]
    assert payload["suggested_next_steps"]
    assert any("gpd observe show --session cli-session-1 --last 20" in step for step in payload["suggested_next_steps"])


def test_observe_execution_raw_prefers_lineage_head_over_legacy_current_execution_snapshot(
    tmp_path: Path,
) -> None:
    observability = tmp_path / "GPD" / "observability"
    observability.mkdir(parents=True)
    (observability / "current-execution.json").write_text(
        json.dumps(
            {
                "session_id": "legacy-session",
                "phase": "09",
                "plan": "02",
                "segment_status": "paused",
                "current_task": "Legacy snapshot task",
                "updated_at": "2026-03-27T12:01:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    head_snapshot = _ExecutionSnapshot(
        session_id="lineage-session",
        phase="09",
        plan="02",
        segment_status="blocked",
        blocked_reason="manual stop required",
        current_task="Lineage head task",
        updated_at="2026-03-27T12:03:00+00:00",
    )

    with patch("gpd.core.observability.get_current_execution", return_value=head_snapshot):
        result = runner.invoke(app, ["--raw", "--cwd", str(tmp_path), "observe", "execution"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["status_classification"] == "blocked"
    assert payload["current_task"] == "Lineage head task"
    assert payload["current_execution"]["current_task"] == "Lineage head task"
    assert payload["current_execution"]["segment_status"] == "blocked"
    assert payload["current_task"] != "Legacy snapshot task"


def test_observe_execution_human_output_keeps_waiting_state_distinct_from_possibly_stalled(tmp_path: Path) -> None:
    observability = tmp_path / "GPD" / "observability"
    observability.mkdir(parents=True)
    (observability / "current-execution.json").write_text(
        json.dumps(
            {
                "session_id": "cli-session-1",
                "phase": "03",
                "plan": "02",
                "segment_status": "waiting_review",
                "waiting_for_review": True,
                "checkpoint_reason": "first_result",
                "first_result_gate_pending": True,
                "updated_at": "2000-01-01T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["--cwd", str(tmp_path), "observe", "execution"])

    assert result.exit_code == 0
    assert "Execution Status" in result.output
    assert "Check next" in result.output
    assert local_cli_resume_command() in result.output
    assert "waiting" in result.output.lower()
    assert "possibly stalled" not in result.output.lower()


def test_observe_execution_human_output_humanizes_budget_wait_reason(tmp_path: Path) -> None:
    observability = tmp_path / "GPD" / "observability"
    observability.mkdir(parents=True)
    (observability / "current-execution.json").write_text(
        json.dumps(
            {
                "session_id": "cli-session-2",
                "phase": "03",
                "plan": "03",
                "segment_status": "waiting_review",
                "waiting_reason": "time_budget_exceeded",
                "updated_at": "2000-01-01T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["--cwd", str(tmp_path), "observe", "execution"])

    assert result.exit_code == 0
    assert "time budget exceeded" in result.output.lower()


def test_observe_execution_raw_surfaces_tangent_proposal_without_replacing_primary_next_check(tmp_path: Path) -> None:
    observability = tmp_path / "GPD" / "observability"
    observability.mkdir(parents=True)
    (observability / "current-execution.json").write_text(
        json.dumps(
            {
                "session_id": "cli-session-3",
                "phase": "03",
                "plan": "04",
                "segment_status": "waiting_review",
                "waiting_for_review": True,
                "checkpoint_reason": "pre_fanout",
                "tangent_summary": "Check whether the 2D case is degenerate",
                "tangent_decision": "branch_later",
                "updated_at": "2000-01-01T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["--raw", "--cwd", str(tmp_path), "observe", "execution"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["status_classification"] == "waiting"
    assert payload["tangent_summary"] == "Check whether the 2D case is degenerate"
    assert payload["tangent_decision"] == "branch_later"
    assert payload["tangent_decision_label"] == "branch later"
    assert payload["tangent_pending"] is False
    assert payload["next_check_command"] == local_cli_resume_command()
    assert payload["tangent_follow_up"] == [
        "Use the runtime `tangent` command to keep the chooser explicit for this alternative path.",
        "Use the runtime `branch-hypothesis` command only if you decide to open a git-backed alternative path after this bounded stop.",
    ]


def test_observe_execution_human_output_surfaces_branch_later_tangent_follow_up(tmp_path: Path) -> None:
    observability = tmp_path / "GPD" / "observability"
    observability.mkdir(parents=True)
    (observability / "current-execution.json").write_text(
        json.dumps(
            {
                "session_id": "cli-session-4",
                "phase": "03",
                "plan": "05",
                "segment_status": "waiting_review",
                "waiting_for_review": True,
                "checkpoint_reason": "pre_fanout",
                "tangent_summary": "Check whether the 2D case is degenerate",
                "tangent_decision": "branch_later",
                "updated_at": "2000-01-01T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["--cwd", str(tmp_path), "observe", "execution"])

    assert result.exit_code == 0
    assert "Tangent proposal" in result.output
    assert "branch later" in result.output.lower()
    assert "Tangent follow-up" in result.output
    assert "runtime `tangent` command" in result.output
    assert "runtime `branch-hypothesis` command" in result.output
    assert local_cli_resume_command() in result.output
    assert "possibly stalled" not in result.output.lower()


def test_observe_show_filters_events(tmp_path: Path) -> None:
    sessions_dir = tmp_path / "GPD" / "observability" / "sessions"
    sessions_dir.mkdir(parents=True)
    (sessions_dir / "cli-a.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "timestamp": "2026-03-10T00:00:00+00:00",
                        "event_id": "evt-1",
                        "session_id": "cli-a",
                        "category": "cli",
                        "name": "command",
                        "action": "start",
                        "status": "active",
                        "command": "timestamp",
                    }
                ),
                json.dumps(
                    {
                        "timestamp": "2026-03-10T00:00:01+00:00",
                        "event_id": "evt-2",
                        "session_id": "cli-a",
                        "category": "trace",
                        "name": "trace_start",
                        "action": "log",
                        "status": "ok",
                        "command": "trace start",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        ["--raw", "--cwd", str(tmp_path), "observe", "show", "--category", "cli", "--command", "timestamp"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["count"] == 1
    assert payload["events"][0]["category"] == "cli"
    assert payload["events"][0]["command"] == "timestamp"


def test_observe_show_falls_back_to_session_logs(tmp_path: Path) -> None:
    """show_events reads per-session logs when filtering observability data."""
    sessions_dir = tmp_path / "GPD" / "observability" / "sessions"
    sessions_dir.mkdir(parents=True)
    (sessions_dir / "cli-a.jsonl").write_text(
        json.dumps(
            {
                "timestamp": "2026-03-10T00:00:00+00:00",
                "event_id": "evt-1",
                "session_id": "cli-a",
                "category": "cli",
                "name": "command",
                "action": "start",
                "status": "active",
                "command": "timestamp",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    # The CLI invocation may create a global events file as a side effect of
    # its own observability, so test the core function directly instead.
    from gpd.core.observability import show_events

    result = show_events(tmp_path, category="cli", command="timestamp")
    assert result.count == 1
    assert result.events[0]["session_id"] == "cli-a"


def test_observe_export_resolves_output_dir_relative_to_cwd(tmp_path: Path) -> None:
    (tmp_path / "GPD").mkdir()

    captured: dict[str, object] = {}

    def fake_export_logs(cwd: Path, **kwargs: object) -> SimpleNamespace:
        captured["cwd"] = cwd
        captured.update(kwargs)
        return SimpleNamespace(exported=True)

    with (
        patch("gpd.core.observability.export_logs", side_effect=fake_export_logs),
        patch("gpd.cli._output"),
    ):
        result = runner.invoke(
            app,
            [
                "--raw",
                "--cwd",
                str(tmp_path),
                "observe",
                "export",
                "--output-dir",
                "exports/logs",
            ],
        )

    assert result.exit_code == 0
    assert captured["cwd"] == tmp_path.resolve()
    assert captured["output_dir"] == str((tmp_path / "exports" / "logs").resolve(strict=False))


def test_observe_event_appends_event(tmp_path: Path) -> None:
    (tmp_path / "GPD").mkdir()

    result = runner.invoke(
        app,
        [
            "--raw",
            "--cwd",
            str(tmp_path),
            "observe",
            "event",
            "workflow",
            "wave-start",
            "--action",
            "start",
            "--status",
            "active",
            "--command",
            "execute-phase",
            "--phase",
            "03",
            "--plan",
            "01",
            "--data",
            '{"wave": 2}',
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["category"] == "workflow"
    assert payload["name"] == "wave-start"
    assert payload["data"]["wave"] == 2
    sessions_dir = tmp_path / "GPD" / "observability" / "sessions"
    session_logs = sorted(sessions_dir.glob("*.jsonl"))
    assert len(session_logs) == 1
    events = [json.loads(line) for line in session_logs[0].read_text(encoding="utf-8").splitlines() if line.strip()]
    assert any(event["category"] == "workflow" and event["name"] == "wave-start" for event in events)
    assert not (tmp_path / "GPD" / "observability" / "events.jsonl").exists()


def test_cli_invocation_does_not_write_observability_files_without_explicit_events(tmp_path: Path) -> None:
    (tmp_path / "GPD").mkdir()

    result = runner.invoke(app, ["--cwd", str(tmp_path), "timestamp"])

    assert result.exit_code == 0
    obs_dir = tmp_path / "GPD" / "observability"
    assert not obs_dir.exists()


# ─── suggest ────────────────────────────────────────────────────────────────


@patch("gpd.core.suggest.suggest_next")
def test_suggest_uses_ancestor_project_root_from_nested_cwd(mock_suggest, tmp_path: Path, monkeypatch) -> None:
    project_root = tmp_path / "project"
    nested_cwd = project_root / "work" / "nested"
    (project_root / "GPD").mkdir(parents=True, exist_ok=True)
    nested_cwd.mkdir(parents=True, exist_ok=True)

    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"suggestions": []}
    mock_suggest.return_value = mock_result

    monkeypatch.chdir(nested_cwd)
    result = runner.invoke(app, ["suggest"])

    assert result.exit_code == 0
    mock_suggest.assert_called_once_with(project_root.resolve())


@patch("gpd.core.suggest.suggest_next")
def test_suggest_uses_ancestor_project_root_from_cleared_cwd(mock_suggest, tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    nested_cwd = project_root / "work" / "nested"
    (project_root / "GPD").mkdir(parents=True, exist_ok=True)
    nested_cwd.mkdir(parents=True, exist_ok=True)
    nested_cwd.rmdir()

    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"suggestions": []}
    mock_suggest.return_value = mock_result

    result = runner.invoke(app, ["--cwd", str(nested_cwd), "suggest"])

    assert result.exit_code == 0
    mock_suggest.assert_called_once_with(project_root.resolve())


@patch("gpd.core.suggest.suggest_next")
def test_suggest_forwards_limit_and_serializes_raw_output_from_nested_cwd(
    mock_suggest, tmp_path: Path
) -> None:
    project_root = tmp_path / "project"
    nested_cwd = project_root / "work" / "nested"
    (project_root / "GPD").mkdir(parents=True, exist_ok=True)
    nested_cwd.mkdir(parents=True, exist_ok=True)

    payload = {
        "suggestions": [],
        "total_suggestions": 0,
        "suggestion_count": 0,
        "top_action": None,
        "context": {},
    }
    mock_result = MagicMock()
    mock_result.model_dump.return_value = payload
    mock_suggest.return_value = mock_result

    result = runner.invoke(app, ["--raw", "--cwd", str(nested_cwd), "suggest", "--limit", "2"])

    assert result.exit_code == 0
    mock_suggest.assert_called_once_with(project_root.resolve(), limit=2)
    mock_result.model_dump.assert_called_once_with(mode="json", by_alias=True)
    assert json.loads(result.output) == payload


@patch("gpd.core.suggest.suggest_next")
def test_suggest_uses_workspace_cwd_when_no_project_root_is_verified(
    mock_suggest,
    tmp_path: Path,
) -> None:
    workspace_cwd = tmp_path / "wrong-folder"
    workspace_cwd.mkdir()

    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"suggestions": []}
    mock_suggest.return_value = mock_result

    with (
        patch("gpd.cli.resolve_project_root", return_value=None),
        patch("gpd.cli._status_command_cwd", side_effect=AssertionError("unexpected reentry lookup")),
    ):
        result = runner.invoke(app, ["--cwd", str(workspace_cwd), "suggest"])

    assert result.exit_code == 0
    mock_suggest.assert_called_once_with(workspace_cwd.resolve())


# ─── pattern subcommands ────────────────────────────────────────────────────


@patch("gpd.core.patterns.pattern_init")
def test_pattern_init(mock_init):
    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"initialized": True}
    mock_init.return_value = mock_result
    result = runner.invoke(app, ["pattern", "init"])
    assert result.exit_code == 0
    mock_init.assert_called_once()


@patch("gpd.core.patterns.pattern_search")
def test_pattern_search(mock_search):
    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"results": []}
    mock_search.return_value = mock_result
    result = runner.invoke(app, ["pattern", "search", "sign", "convention"])
    assert result.exit_code == 0
    # Verify query was joined
    args = mock_search.call_args
    assert "sign convention" in args[0][0]


# ─── init subcommands ───────────────────────────────────────────────────────


@patch("gpd.core.context.init_execute_phase")
def test_init_execute_phase(mock_init):
    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"context": "..."}
    mock_init.return_value = mock_result
    result = runner.invoke(app, ["init", "execute-phase", "42"])
    assert result.exit_code == 0
    mock_init.assert_called_once()


@patch("gpd.core.context.init_execute_phase")
def test_init_execute_phase_forwards_stage_option(mock_init):
    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"context": "..."}
    mock_init.return_value = mock_result
    result = runner.invoke(app, ["init", "execute-phase", "42", "--stage", "phase_bootstrap"])
    assert result.exit_code == 0
    mock_init.assert_called_once()
    assert mock_init.call_args.args == (cli_module._get_cwd(), "42")
    assert mock_init.call_args.kwargs == {"includes": set(), "stage": "phase_bootstrap"}


@patch("gpd.core.context.init_new_project")
def test_init_new_project(mock_init):
    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"context": "..."}
    mock_init.return_value = mock_result
    result = runner.invoke(app, ["init", "new-project"])
    assert result.exit_code == 0
    mock_init.assert_called_once()
    assert len(mock_init.call_args.args) == 1
    assert mock_init.call_args.kwargs == {}


@patch("gpd.core.context.init_new_project")
def test_init_new_project_stage(mock_init):
    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"context": "..."}
    mock_init.return_value = mock_result
    result = runner.invoke(app, ["init", "new-project", "--stage", "scope_intake"])
    assert result.exit_code == 0
    mock_init.assert_called_once()
    assert len(mock_init.call_args.args) == 1
    assert mock_init.call_args.kwargs == {"stage": "scope_intake"}


@patch("gpd.core.context.init_new_project", side_effect=ValueError("Unknown new-project stage 'bogus'."))
def test_init_new_project_rejects_invalid_stage(mock_init):
    result = runner.invoke(app, ["init", "new-project", "--stage", "bogus"])
    assert result.exit_code == 1
    assert "Unknown new-project stage 'bogus'." in result.output


def test_init_verify_work_preserves_plain_call_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[Path, str | None, str | None]] = []

    def fake_init(cwd: Path, phase: str | None, stage: str | None = None):
        calls.append((cwd, phase, stage))
        mock_result = MagicMock()
        mock_result.model_dump.return_value = {"context": "..."}
        return mock_result

    monkeypatch.setattr("gpd.core.context.init_verify_work", fake_init)
    result = runner.invoke(app, ["init", "verify-work", "01"])

    assert result.exit_code == 0
    assert len(calls) == 1
    cwd, phase, stage = calls[0]
    assert cwd == cli_module._get_cwd()
    assert phase == "01"
    assert stage is None


def test_init_verify_work_forwards_stage_option(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[Path, str | None, str | None]] = []

    def fake_init(cwd: Path, phase: str | None, stage: str | None = None):
        calls.append((cwd, phase, stage))
        mock_result = MagicMock()
        mock_result.model_dump.return_value = {"context": "..."}
        return mock_result

    monkeypatch.setattr("gpd.core.context.init_verify_work", fake_init)
    result = runner.invoke(app, ["init", "verify-work", "01", "--stage", "session_router"])

    assert result.exit_code == 0
    assert len(calls) == 1
    cwd, phase, stage = calls[0]
    assert cwd == cli_module._get_cwd()
    assert phase == "01"
    assert stage == "session_router"


def test_init_plan_phase_preserves_plain_call_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[Path, str | None, set[str] | None, str | None]] = []

    def fake_init(
        cwd: Path,
        phase: str | None,
        includes: set[str] | None = None,
        stage: str | None = None,
    ):
        calls.append((cwd, phase, includes, stage))
        mock_result = MagicMock()
        mock_result.model_dump.return_value = {"context": "..."}
        return mock_result

    monkeypatch.setattr("gpd.core.context.init_plan_phase", fake_init)
    result = runner.invoke(app, ["init", "plan-phase", "02", "--include", "state,research"])

    assert result.exit_code == 0
    assert len(calls) == 1
    cwd, phase, includes, stage = calls[0]
    assert cwd == cli_module._get_cwd()
    assert phase == "02"
    assert includes == {"state", "research"}
    assert stage is None


def test_init_plan_phase_forwards_stage_option(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[Path, str | None, set[str] | None, str | None]] = []

    def fake_init(
        cwd: Path,
        phase: str | None,
        includes: set[str] | None = None,
        stage: str | None = None,
    ):
        calls.append((cwd, phase, includes, stage))
        mock_result = MagicMock()
        mock_result.model_dump.return_value = {"context": "..."}
        return mock_result

    monkeypatch.setattr("gpd.core.context.init_plan_phase", fake_init)
    result = runner.invoke(app, ["init", "plan-phase", "02", "--stage", "phase_bootstrap"])

    assert result.exit_code == 0
    assert len(calls) == 1
    cwd, phase, includes, stage = calls[0]
    assert cwd == cli_module._get_cwd()
    assert phase == "02"
    assert includes == set()
    assert stage == "phase_bootstrap"


def test_init_plan_phase_rejects_stage_and_include_mix(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_init(
        cwd: Path,
        phase: str | None,
        includes: set[str] | None = None,
        stage: str | None = None,
    ):
        raise ValueError(
            "gpd init plan-phase does not allow --include together with --stage; "
            "stage payloads already declare their required context."
        )

    monkeypatch.setattr("gpd.core.context.init_plan_phase", fake_init)
    result = runner.invoke(app, ["init", "plan-phase", "02", "--include", "state", "--stage", "phase_bootstrap"])

    assert result.exit_code == 1
    assert "does not allow --include together with --stage" in result.output


def test_init_plan_phase_rejects_invalid_stage(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_init(
        cwd: Path,
        phase: str | None,
        includes: set[str] | None = None,
        stage: str | None = None,
    ):
        raise ValueError("Unknown plan-phase stage 'bogus'. Allowed values: phase_bootstrap.")

    monkeypatch.setattr("gpd.core.context.init_plan_phase", fake_init)
    result = runner.invoke(app, ["init", "plan-phase", "02", "--stage", "bogus"])

    assert result.exit_code == 1
    assert "Unknown plan-phase stage 'bogus'" in result.output


def test_init_resume_help_surfaces_recovery_snapshot_entrypoint() -> None:
    result = runner.invoke(app, ["init", "resume", "--help"])

    assert result.exit_code == 0
    normalized_output = _normalize_cli_output(result.output)
    assert "Usage: gpd init resume" in normalized_output
    assert "Assemble context for resuming previous work." in normalized_output


@patch("gpd.core.context.init_resume")
def test_init_resume(mock_init):
    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"segment_candidates": []}
    mock_init.return_value = mock_result

    result = runner.invoke(app, ["init", "resume"])

    assert result.exit_code == 0
    mock_init.assert_called_once()


def test_paper_build_uses_default_config_surface(tmp_path: Path):
    nested_cwd = tmp_path / "notes"
    nested_cwd.mkdir()
    (tmp_path / "GPD").mkdir()
    paper_dir = tmp_path / "paper"
    paper_dir.mkdir()
    (paper_dir / "PAPER-CONFIG.json").write_text(
        json.dumps(
            {
                "title": "Configured Paper",
                "authors": [{"name": "A. Researcher"}],
                "abstract": "Abstract.",
                "sections": [{"title": "Intro", "content": "Hello."}],
                "figures": [{"path": "figures/plot.png", "caption": "Plot", "label": "plot"}],
            }
        ),
        encoding="utf-8",
    )
    references_dir = tmp_path / "references"
    references_dir.mkdir()
    (references_dir / "references.bib").write_text(
        "@article{einstein1905,\n  author={Einstein, Albert},\n  title={Relativity},\n  year={1905}\n}\n",
        encoding="utf-8",
    )

    result_payload = MagicMock()
    result_payload.tex_path = paper_dir / "configured_paper.tex"
    result_payload.manifest_path = paper_dir / "ARTIFACT-MANIFEST.json"
    result_payload.bibliography_audit_path = None
    result_payload.bibliography_audit = SimpleNamespace(
        entries=[
            SimpleNamespace(
                key="einstein1905",
                reference_id="lit-ref-einstein-1905",
            )
        ]
    )
    result_payload.pdf_path = paper_dir / "configured_paper.pdf"
    result_payload.success = True
    result_payload.errors = []

    with (
        patch("gpd.mcp.paper.compiler.detect_latex_toolchain", return_value=_toolchain_capability()),
        patch("gpd.mcp.paper.compiler.build_paper", new=AsyncMock(return_value=result_payload)) as mock_build,
    ):
        result = runner.invoke(app, ["--raw", "--cwd", str(nested_cwd), "paper-build"], catch_exceptions=False)

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["config_path"] == "../paper/PAPER-CONFIG.json"
    assert payload["output_dir"] == "../paper"
    assert payload["tex_path"] == "../paper/configured_paper.tex"
    assert payload["bibliography_source"] == "../references/references.bib"
    assert payload["reference_bibtex_bridge"] == [{"reference_id": "lit-ref-einstein-1905", "bibtex_key": "einstein1905"}]
    assert payload["manifest_path"] == "../paper/ARTIFACT-MANIFEST.json"
    assert payload["pdf_path"] == "../paper/configured_paper.pdf"
    assert payload["toolchain"] == {
        "compiler": "pdflatex",
        "available": True,
        "compiler_available": True,
        "full_toolchain_available": True,
        "compiler_path": "/usr/bin/pdflatex",
        "distribution": "TeX Live",
        "latexmk_available": True,
        "bibtex_available": True,
        "bibliography_support_available": True,
        "kpsewhich_available": True,
        "readiness_state": "ready",
        "message": "pdflatex found (TeX Live): /usr/bin/pdflatex",
        "paper_build_ready": True,
        "arxiv_submission_ready": True,
        "warnings": [],
    }
    assert len(payload["warnings"]) == 1
    assert "temporary directory" in payload["warnings"][0]

    args = mock_build.await_args.args
    kwargs = mock_build.await_args.kwargs
    assert args[1] == paper_dir.resolve(strict=False)
    assert args[0].figures[0].path == (paper_dir / "figures" / "plot.png").resolve(strict=False)
    assert kwargs["bib_data"] is not None
    assert kwargs["citation_sources"] is None
    assert kwargs["enrich_bibliography"] is True


def test_paper_build_rejects_ambiguous_supported_config_roots_without_a_resolved_manuscript(tmp_path: Path) -> None:
    paper_dir = tmp_path / "paper"
    paper_dir.mkdir()
    manuscript_dir = tmp_path / "manuscript"
    manuscript_dir.mkdir()
    draft_dir = tmp_path / "draft"
    draft_dir.mkdir()

    (paper_dir / "PAPER-CONFIG.json").write_text(
        json.dumps(
            {
                "title": "paper-uppercase",
                "authors": [{"name": "A. Researcher"}],
                "abstract": "Abstract.",
                "sections": [{"title": "Intro", "content": "Hello."}],
                "figures": [],
            }
        ),
        encoding="utf-8",
    )
    (manuscript_dir / "PAPER-CONFIG.json").write_text(
        json.dumps(
            {
                "title": "manuscript-uppercase",
                "authors": [{"name": "B. Researcher"}],
                "abstract": "Abstract.",
                "sections": [{"title": "Intro", "content": "Hello."}],
                "figures": [],
            }
        ),
        encoding="utf-8",
    )
    (draft_dir / "PAPER-CONFIG.json").write_text(
        json.dumps(
            {
                "title": "draft-uppercase",
                "authors": [{"name": "D. Researcher"}],
                "abstract": "Abstract.",
                "sections": [{"title": "Intro", "content": "Hello."}],
                "figures": [],
            }
        ),
        encoding="utf-8",
    )

    with patch("gpd.mcp.paper.compiler.build_paper", new=AsyncMock()) as mock_build:
        result = runner.invoke(app, ["--raw", "--cwd", str(tmp_path), "paper-build"])

    assert result.exit_code == 1
    assert isinstance(result.exception, cli_module.GPDError)
    assert "Ambiguous paper config across supported manuscript roots" in str(result.exception)
    mock_build.assert_not_called()


def test_paper_build_rejects_manuscript_vs_draft_ambiguity_without_a_resolved_manuscript(tmp_path: Path) -> None:
    manuscript_dir = tmp_path / "manuscript"
    manuscript_dir.mkdir()
    draft_dir = tmp_path / "draft"
    draft_dir.mkdir()

    (manuscript_dir / "PAPER-CONFIG.json").write_text(
        json.dumps(
            {
                "title": "manuscript-uppercase",
                "authors": [{"name": "A. Researcher"}],
                "abstract": "Abstract.",
                "sections": [{"title": "Intro", "content": "Hello."}],
                "figures": [],
            }
        ),
        encoding="utf-8",
    )
    (draft_dir / "PAPER-CONFIG.json").write_text(
        json.dumps(
            {
                "title": "draft-uppercase",
                "authors": [{"name": "B. Researcher"}],
                "abstract": "Abstract.",
                "sections": [{"title": "Intro", "content": "Hello."}],
                "figures": [],
            }
        ),
        encoding="utf-8",
    )

    with patch("gpd.mcp.paper.compiler.build_paper", new=AsyncMock()) as mock_build:
        result = runner.invoke(app, ["--raw", "--cwd", str(tmp_path), "paper-build"])

    assert result.exit_code == 1
    assert isinstance(result.exception, cli_module.GPDError)
    assert "Ambiguous paper config across supported manuscript roots" in str(result.exception)
    mock_build.assert_not_called()


def test_validate_paper_quality_from_project_rejects_ambiguous_manuscript_roots(tmp_path: Path) -> None:
    def write_manuscript_root(root_name: str, stem: str) -> None:
        manuscript_dir = tmp_path / root_name
        manuscript_dir.mkdir()
        (manuscript_dir / f"{stem}.tex").write_text("\\documentclass{article}\\begin{document}Hi\\end{document}\n", encoding="utf-8")
        (manuscript_dir / "PAPER-CONFIG.json").write_text(
            json.dumps(
                {
                    "title": f"{root_name.title()} Manuscript",
                    "output_filename": stem,
                    "authors": [{"name": "A. Researcher"}],
                    "abstract": "Abstract.",
                    "sections": [{"title": "Intro", "content": "Hello."}],
                    "figures": [],
                }
            ),
            encoding="utf-8",
        )
        (manuscript_dir / "ARTIFACT-MANIFEST.json").write_text(
            json.dumps(
                {
                    "version": 1,
                    "paper_title": f"{root_name.title()} Manuscript",
                    "journal": "jhep",
                    "created_at": "2026-04-03T00:00:00Z",
                    "artifacts": [
                        {
                            "artifact_id": f"{root_name}-manuscript",
                            "category": "tex",
                            "path": f"{stem}.tex",
                            "sha256": "0" * 64,
                            "produced_by": "test",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

    write_manuscript_root("paper", "paper_manuscript")
    write_manuscript_root("manuscript", "manuscript_manuscript")

    result = runner.invoke(app, ["--raw", "validate", "paper-quality", "--from-project", str(tmp_path)])

    assert result.exit_code == 1
    assert isinstance(result.exception, cli_module.GPDError)
    assert "validate paper-quality --from-project requires exactly one resolved manuscript root" in str(
        result.exception
    )
    assert "multiple manuscript roots resolve" in str(result.exception)


def test_validate_paper_quality_from_project_rejects_missing_manuscript_root(tmp_path: Path) -> None:
    result = runner.invoke(app, ["--raw", "validate", "paper-quality", "--from-project", str(tmp_path)])

    assert result.exit_code == 1
    assert isinstance(result.exception, cli_module.GPDError)
    assert "validate paper-quality --from-project requires exactly one resolved manuscript root" in str(
        result.exception
    )
    assert "found missing" in str(result.exception)
    assert "no manuscript entrypoint found under paper/, manuscript/, or draft/" in str(result.exception)


def test_paper_build_does_not_discover_legacy_planning_configs(tmp_path: Path, capsys) -> None:
    planning_paper_dir = tmp_path / "GPD" / "paper"
    planning_paper_dir.mkdir(parents=True)
    (planning_paper_dir / "PAPER-CONFIG.json").write_text(
        json.dumps(
            {
                "title": "planning-uppercase",
                "authors": [{"name": "A. Researcher"}],
                "abstract": "Abstract.",
                "sections": [{"title": "Intro", "content": "Hello."}],
                "figures": [],
            }
        ),
        encoding="utf-8",
    )

    try:
        cli_module.app(args=["--raw", "--cwd", str(tmp_path), "paper-build"])
    except SystemExit as exc:
        assert exc.code == 1

    captured = capsys.readouterr()
    payload = json.loads(captured.err)
    assert "No paper config found" in payload["error"]
    assert "GPD/paper" not in payload["error"]


def test_paper_build_rejects_explicit_legacy_planning_config_path(tmp_path: Path, capsys) -> None:
    planning_paper_dir = tmp_path / "GPD" / "paper"
    planning_paper_dir.mkdir(parents=True)
    (planning_paper_dir / "PAPER-CONFIG.json").write_text(
        json.dumps(
            {
                "title": "planning-uppercase",
                "authors": [{"name": "A. Researcher"}],
                "abstract": "Abstract.",
                "sections": [{"title": "Intro", "content": "Hello."}],
                "figures": [],
            }
        ),
        encoding="utf-8",
    )

    try:
        cli_module.app(args=["--raw", "--cwd", str(tmp_path), "paper-build", "GPD/paper/PAPER-CONFIG.json"])
    except SystemExit as exc:
        assert exc.code == 1

    captured = capsys.readouterr()
    payload = json.loads(captured.err)
    assert "no longer supported" in payload["error"]


def test_paper_build_rejects_explicit_legacy_hidden_planning_config_path(tmp_path: Path, capsys) -> None:
    planning_paper_dir = tmp_path / ".gpd" / "paper"
    planning_paper_dir.mkdir(parents=True)
    (tmp_path / ".gpd" / "state.json").write_text("{}\n", encoding="utf-8")
    (planning_paper_dir / "PAPER-CONFIG.json").write_text(
        json.dumps(
            {
                "title": "planning-lowercase",
                "authors": [{"name": "A. Researcher"}],
                "abstract": "Abstract.",
                "sections": [{"title": "Intro", "content": "Hello."}],
                "figures": [],
            }
        ),
        encoding="utf-8",
    )

    try:
        cli_module.app(args=["--raw", "--cwd", str(tmp_path), "paper-build", ".gpd/paper/PAPER-CONFIG.json"])
    except SystemExit as exc:
        assert exc.code == 1

    captured = capsys.readouterr()
    payload = json.loads(captured.err)
    assert ".gpd/paper" in payload["error"]
    assert "no longer supported" in payload["error"]


def test_paper_build_preserves_explicit_relative_config_path_from_nested_cwd(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    nested_cwd = project_root / "notes"
    nested_cwd.mkdir(parents=True)
    (project_root / "GPD").mkdir()
    paper_dir = project_root / "paper"
    paper_dir.mkdir()
    (paper_dir / "PAPER-CONFIG.json").write_text(
        json.dumps(
            {
                "title": "Configured Paper",
                "authors": [{"name": "A. Researcher"}],
                "abstract": "Abstract.",
                "sections": [{"title": "Intro", "content": "Hello."}],
                "figures": [],
            }
        ),
        encoding="utf-8",
    )

    result_payload = MagicMock()
    result_payload.tex_path = paper_dir / "configured_paper.tex"
    result_payload.manifest_path = paper_dir / "ARTIFACT-MANIFEST.json"
    result_payload.bibliography_audit_path = None
    result_payload.pdf_path = paper_dir / "configured_paper.pdf"
    result_payload.success = True
    result_payload.errors = []

    with patch("gpd.mcp.paper.compiler.build_paper", new=AsyncMock(return_value=result_payload)) as mock_build:
        result = runner.invoke(
            app,
            [
                "--raw",
                "--cwd",
                str(nested_cwd),
                "paper-build",
                "../paper/PAPER-CONFIG.json",
            ],
            catch_exceptions=False,
        )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["config_path"] == "../paper/PAPER-CONFIG.json"
    assert payload["output_dir"] == "../paper"
    assert mock_build.await_args.args[1] == paper_dir.resolve(strict=False)


def test_paper_build_prefers_config_dir_bibliography_before_output_and_references(tmp_path: Path) -> None:
    paper_dir = tmp_path / "paper"
    paper_dir.mkdir()
    (paper_dir / "PAPER-CONFIG.json").write_text(
        json.dumps(
            {
                "title": "Configured Paper",
                "authors": [{"name": "A. Researcher"}],
                "abstract": "Abstract.",
                "sections": [{"title": "Intro", "content": "Hello."}],
                "figures": [],
            }
        ),
        encoding="utf-8",
    )
    (paper_dir / "references.bib").write_text(
        "@article{configsource,\n  author={Config, Source},\n  title={Config},\n  year={1905}\n}\n",
        encoding="utf-8",
    )

    output_dir = tmp_path / "output"
    output_dir.mkdir()
    (output_dir / "references.bib").write_text(
        "@article{outsource,\n  author={Output, Source},\n  title={Output},\n  year={1906}\n}\n",
        encoding="utf-8",
    )

    references_dir = tmp_path / "references"
    references_dir.mkdir()
    (references_dir / "references.bib").write_text(
        "@article{refsource,\n  author={References, Source},\n  title={References},\n  year={1907}\n}\n",
        encoding="utf-8",
    )

    result_payload = MagicMock()
    result_payload.manifest_path = output_dir / "ARTIFACT-MANIFEST.json"
    result_payload.bibliography_audit_path = output_dir / "BIBLIOGRAPHY-AUDIT.json"
    result_payload.pdf_path = output_dir / "configured_paper.pdf"
    result_payload.success = True
    result_payload.errors = []

    with patch("gpd.mcp.paper.compiler.build_paper", new=AsyncMock(return_value=result_payload)) as mock_build:
        result = runner.invoke(
            app,
            ["--raw", "--cwd", str(tmp_path), "paper-build", "--output-dir", str(output_dir)],
            catch_exceptions=False,
        )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["bibliography_source"] == "./paper/references.bib"
    assert payload["bibliography_audit_path"] == "./output/BIBLIOGRAPHY-AUDIT.json"
    assert "configsource" in mock_build.await_args.kwargs["bib_data"].entries


def test_resolve_review_preflight_publication_artifacts_bundle(tmp_path: Path) -> None:
    manuscript_dir = tmp_path / "paper"
    manuscript_dir.mkdir()
    manuscript = manuscript_dir / "curvature_flow_bounds.tex"
    manuscript.write_text("\\documentclass{article}\\begin{document}Hello\\end{document}", encoding="utf-8")
    (manuscript_dir / "ARTIFACT-MANIFEST.json").write_text("{}", encoding="utf-8")
    (manuscript_dir / "BIBLIOGRAPHY-AUDIT.json").write_text("{}", encoding="utf-8")
    (manuscript_dir / "reproducibility-manifest.json").write_text("{}", encoding="utf-8")

    bundle = cli_module._resolve_review_preflight_publication_artifacts(manuscript)

    assert bundle.artifact_manifest == manuscript_dir / "ARTIFACT-MANIFEST.json"
    assert bundle.bibliography_audit == manuscript_dir / "BIBLIOGRAPHY-AUDIT.json"
    assert bundle.reproducibility_manifest == manuscript_dir / "reproducibility-manifest.json"


def test_resolve_review_preflight_manuscript_directory_uses_manifest_declared_entrypoint(tmp_path: Path) -> None:
    manuscript_dir = tmp_path / "paper"
    manuscript_dir.mkdir()
    manuscript = manuscript_dir / "curvature_flow_bounds.tex"
    manuscript.write_text("\\documentclass{article}\\begin{document}Hello\\end{document}", encoding="utf-8")
    (manuscript_dir / "ARTIFACT-MANIFEST.json").write_text(
        json.dumps(
            {
                "version": 1,
                "paper_title": "Curvature Flow Bounds",
                "journal": "prl",
                "created_at": "2026-04-02T00:00:00+00:00",
                "artifacts": [
                    {
                        "artifact_id": "tex-paper",
                        "category": "tex",
                        "path": "curvature_flow_bounds.tex",
                        "sha256": "0" * 64,
                        "produced_by": "test",
                        "sources": [],
                        "metadata": {},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    resolved, detail = cli_module._resolve_review_preflight_manuscript(
        tmp_path,
        "paper",
        allow_markdown=True,
    )

    assert resolved == manuscript
    assert "/paper resolved to" in detail
    assert "curvature_flow_bounds.tex" in detail


def test_resolve_review_preflight_manuscript_reports_ambiguous_project_state(tmp_path: Path) -> None:
    for root_name in ("paper", "manuscript"):
        manuscript_dir = tmp_path / root_name
        manuscript_dir.mkdir()
        manuscript = manuscript_dir / "curvature_flow_bounds.tex"
        manuscript.write_text("\\documentclass{article}\\begin{document}Hello\\end{document}", encoding="utf-8")
        (manuscript_dir / "ARTIFACT-MANIFEST.json").write_text(
            json.dumps(
                {
                    "version": 1,
                    "paper_title": "Curvature Flow Bounds",
                    "journal": "prl",
                    "created_at": "2026-04-02T00:00:00+00:00",
                    "artifacts": [
                        {
                            "artifact_id": f"tex-{root_name}",
                            "category": "tex",
                            "path": "curvature_flow_bounds.tex",
                            "sha256": "0" * 64,
                            "produced_by": "test",
                            "sources": [],
                            "metadata": {},
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

    resolved, detail = cli_module._resolve_review_preflight_manuscript(
        tmp_path,
        None,
        allow_markdown=True,
    )

    assert resolved is None
    assert "ambiguous or inconsistent manuscript roots" in detail
    assert "multiple manuscript roots resolve" in detail


def test_resolve_review_preflight_manuscript_explicit_supported_root_bypasses_project_ambiguity(
    tmp_path: Path,
) -> None:
    for root_name in ("paper", "manuscript"):
        root = tmp_path / root_name
        root.mkdir()
        manuscript = root / "curvature_flow_bounds.tex"
        manuscript.write_text("\\documentclass{article}\\begin{document}Hello\\end{document}", encoding="utf-8")
        (root / "ARTIFACT-MANIFEST.json").write_text(
            json.dumps(
                {
                    "version": 1,
                    "paper_title": "Curvature Flow Bounds",
                    "journal": "prl",
                    "created_at": "2026-04-02T00:00:00+00:00",
                    "artifacts": [
                        {
                            "artifact_id": f"tex-{root_name}",
                            "category": "tex",
                            "path": "curvature_flow_bounds.tex",
                            "sha256": "0" * 64,
                            "produced_by": "test",
                            "sources": [],
                            "metadata": {},
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

    resolved, detail = cli_module._resolve_review_preflight_manuscript(
        tmp_path,
        "paper",
        allow_markdown=True,
        restrict_to_supported_roots=True,
    )

    assert resolved == tmp_path / "paper" / "curvature_flow_bounds.tex"
    assert "resolved to" in detail
    assert "curvature_flow_bounds.tex" in detail


def test_resolve_review_preflight_manuscript_explicit_supported_file_requires_matching_root_resolution(
    tmp_path: Path,
) -> None:
    manuscript_dir = tmp_path / "paper"
    manuscript_dir.mkdir()
    manuscript = manuscript_dir / "curvature_flow_bounds.tex"
    manuscript.write_text("\\documentclass{article}\\begin{document}Hello\\end{document}", encoding="utf-8")
    (manuscript_dir / "ARTIFACT-MANIFEST.json").write_text(
        json.dumps(
            {
                "version": 1,
                "paper_title": "Curvature Flow Bounds",
                "journal": "prl",
                "created_at": "2026-04-02T00:00:00+00:00",
                "artifacts": [
                    {
                        "artifact_id": "tex-paper",
                        "category": "tex",
                        "path": "curvature_flow_bounds.tex",
                        "sha256": "0" * 64,
                        "produced_by": "test",
                        "sources": [],
                        "metadata": {},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (manuscript_dir / "PAPER-CONFIG.json").write_text(
        json.dumps(
            {
                "title": "Alternate Title",
                "authors": [{"name": "A. Researcher"}],
                "abstract": "Abstract.",
                "sections": [{"heading": "Intro", "content": "Hello."}],
            }
        ),
        encoding="utf-8",
    )

    resolved, detail = cli_module._resolve_review_preflight_manuscript(
        tmp_path,
        "paper/curvature_flow_bounds.tex",
        allow_markdown=True,
        restrict_to_supported_roots=True,
    )

    assert resolved is None
    assert "/paper is ambiguous or inconsistent" in detail
    assert "does not resolve to a readable manuscript entrypoint" in detail


def test_resolve_review_preflight_manuscript_uses_workspace_cwd_for_relative_targets(
    tmp_path: Path,
) -> None:
    manuscript_dir = tmp_path / "paper"
    nested_cwd = tmp_path / "notes"
    nested_cwd.mkdir()
    manuscript = manuscript_dir / "curvature_flow_bounds.tex"
    manuscript_dir.mkdir()
    manuscript.write_text("\\documentclass{article}\\begin{document}Hello\\end{document}", encoding="utf-8")
    (manuscript_dir / "ARTIFACT-MANIFEST.json").write_text(
        json.dumps(
            {
                "version": 1,
                "paper_title": "Curvature Flow Bounds",
                "journal": "prl",
                "created_at": "2026-04-02T00:00:00+00:00",
                "artifacts": [
                    {
                        "artifact_id": "tex-paper",
                        "category": "tex",
                        "path": "curvature_flow_bounds.tex",
                        "sha256": "0" * 64,
                        "produced_by": "test",
                        "sources": [],
                        "metadata": {},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    resolved, detail = cli_module._resolve_review_preflight_manuscript(
        tmp_path,
        "../paper/curvature_flow_bounds.tex",
        allow_markdown=True,
        restrict_to_supported_roots=True,
        workspace_cwd=nested_cwd,
    )

    assert resolved == manuscript
    assert detail.endswith("present")
    assert "curvature_flow_bounds.tex" in detail


def test_resolve_review_preflight_manuscript_nested_supported_directory_resolves_via_supported_root(
    tmp_path: Path,
) -> None:
    manuscript_dir = tmp_path / "paper"
    sections_dir = manuscript_dir / "sections"
    sections_dir.mkdir(parents=True)
    manuscript = sections_dir / "curvature_flow_bounds.tex"
    manuscript.write_text("\\documentclass{article}\\begin{document}Hello\\end{document}", encoding="utf-8")
    (manuscript_dir / "ARTIFACT-MANIFEST.json").write_text(
        json.dumps(
            {
                "version": 1,
                "paper_title": "Curvature Flow Bounds",
                "journal": "prl",
                "created_at": "2026-04-02T00:00:00+00:00",
                "artifacts": [
                    {
                        "artifact_id": "tex-paper",
                        "category": "tex",
                        "path": "sections/curvature_flow_bounds.tex",
                        "sha256": "0" * 64,
                        "produced_by": "test",
                        "sources": [],
                        "metadata": {},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    resolved, detail = cli_module._resolve_review_preflight_manuscript(
        tmp_path,
        "paper/sections",
        allow_markdown=True,
        restrict_to_supported_roots=True,
    )

    assert resolved == manuscript
    assert "paper/sections resolved to" in detail
    assert "curvature_flow_bounds.tex" in detail


def test_resolve_review_preflight_manuscript_rejects_nested_supported_directory_when_entrypoint_lives_elsewhere(
    tmp_path: Path,
) -> None:
    manuscript_dir = tmp_path / "paper"
    sections_dir = manuscript_dir / "sections"
    sections_dir.mkdir(parents=True)
    manuscript = manuscript_dir / "main.tex"
    manuscript.write_text("\\documentclass{article}\\begin{document}Hello\\end{document}", encoding="utf-8")
    (manuscript_dir / "ARTIFACT-MANIFEST.json").write_text(
        json.dumps(
            {
                "version": 1,
                "paper_title": "Curvature Flow Bounds",
                "journal": "prl",
                "created_at": "2026-04-02T00:00:00+00:00",
                "artifacts": [
                    {
                        "artifact_id": "tex-paper",
                        "category": "tex",
                        "path": "main.tex",
                        "sha256": "0" * 64,
                        "produced_by": "test",
                        "sources": [],
                        "metadata": {},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    resolved, detail = cli_module._resolve_review_preflight_manuscript(
        tmp_path,
        "paper/sections",
        allow_markdown=True,
        restrict_to_supported_roots=True,
    )

    assert resolved is None
    assert "does not contain the resolved manuscript entrypoint" in detail


def test_resolve_review_preflight_manuscript_rejects_missing_out_of_root_target_before_existence_check(
    tmp_path: Path,
) -> None:
    resolved, detail = cli_module._resolve_review_preflight_manuscript(
        tmp_path,
        "submission/missing.tex",
        allow_markdown=True,
        restrict_to_supported_roots=True,
    )

    assert resolved is None
    assert detail == "explicit manuscript target must stay under `paper/`, `manuscript/`, or `draft/` inside the current project"


def test_resolve_review_preflight_manuscript_reports_inconsistent_project_state(tmp_path: Path) -> None:
    manuscript_dir = tmp_path / "paper"
    manuscript_dir.mkdir()
    manuscript = manuscript_dir / "curvature_flow_bounds.tex"
    manuscript.write_text("\\documentclass{article}\\begin{document}Hello\\end{document}", encoding="utf-8")
    (manuscript_dir / "ARTIFACT-MANIFEST.json").write_text(
        json.dumps(
            {
                "version": 1,
                "paper_title": "Curvature Flow Bounds",
                "journal": "prl",
                "created_at": "2026-04-02T00:00:00+00:00",
                "artifacts": [
                    {
                        "artifact_id": "tex-paper",
                        "category": "tex",
                        "path": "curvature_flow_bounds.tex",
                        "sha256": "0" * 64,
                        "produced_by": "test",
                        "sources": [],
                        "metadata": {},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (manuscript_dir / "PAPER-CONFIG.json").write_text(
        json.dumps(
            {
                "title": "Alternate Title",
                "authors": [{"name": "A. Researcher"}],
                "abstract": "Abstract.",
                "sections": [{"heading": "Intro", "content": "Hello."}],
            }
        ),
        encoding="utf-8",
    )

    resolved, detail = cli_module._resolve_review_preflight_manuscript(
        tmp_path,
        None,
        allow_markdown=True,
    )

    assert resolved is None
    assert "ambiguous or inconsistent manuscript roots" in detail
    assert "does not resolve to a readable manuscript entrypoint" in detail


def test_resolve_review_preflight_manuscript_rejects_unsupported_explicit_target_before_project_scan(
    tmp_path: Path,
) -> None:
    paper_dir = tmp_path / "paper"
    paper_dir.mkdir()
    (paper_dir / "ARTIFACT-MANIFEST.json").write_text(
        json.dumps(
            {
                "version": 1,
                "paper_title": "Curvature Flow Bounds",
                "journal": "prl",
                "created_at": "2026-04-02T00:00:00+00:00",
                "artifacts": [
                    {
                        "artifact_id": "tex-paper",
                        "category": "tex",
                        "path": "curvature_flow_bounds.tex",
                        "sha256": "0" * 64,
                        "produced_by": "test",
                        "sources": [],
                        "metadata": {},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    submission_dir = tmp_path / "submission"
    submission_dir.mkdir()
    explicit_target = submission_dir / "curvature_flow_bounds.tex"
    explicit_target.write_text("\\documentclass{article}\\begin{document}Hello\\end{document}", encoding="utf-8")

    resolved, detail = cli_module._resolve_review_preflight_manuscript(
        tmp_path,
        "submission/curvature_flow_bounds.tex",
        allow_markdown=False,
        restrict_to_supported_roots=True,
    )

    assert resolved is None
    assert "must stay under `paper/`, `manuscript/`, or `draft/`" in detail


def test_paper_build_without_bibliography_does_not_import_pybtex(tmp_path: Path, monkeypatch) -> None:
    import gpd.mcp.paper.compiler  # noqa: F401

    paper_dir = tmp_path / "paper"
    paper_dir.mkdir()
    (paper_dir / "PAPER-CONFIG.json").write_text(
        json.dumps(
            {
                "title": "Configured Paper",
                "authors": [{"name": "A. Researcher"}],
                "abstract": "Abstract.",
                "sections": [{"title": "Intro", "content": "Hello."}],
                "figures": [],
            }
        ),
        encoding="utf-8",
    )

    real_import = builtins.__import__

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):  # type: ignore[no-untyped-def]
        if name.startswith("pybtex"):
            raise AssertionError("pybtex should not be imported when no bibliography source exists")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded_import)

    result_payload = MagicMock()
    result_payload.manifest_path = paper_dir / "ARTIFACT-MANIFEST.json"
    result_payload.bibliography_audit_path = None
    result_payload.pdf_path = paper_dir / "configured_paper.pdf"
    result_payload.success = True
    result_payload.errors = []

    with patch("gpd.mcp.paper.compiler.build_paper", new=AsyncMock(return_value=result_payload)) as mock_build:
        result = runner.invoke(app, ["--raw", "--cwd", str(tmp_path), "paper-build"], catch_exceptions=False)

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["bibliography_source"] == ""
    assert payload["reference_bibtex_bridge"] == []
    assert mock_build.await_args.kwargs["bib_data"] is None


def test_paper_build_auto_discovers_single_literature_citation_sources_sidecar(tmp_path: Path) -> None:
    nested_cwd = tmp_path / "notes"
    nested_cwd.mkdir()
    (tmp_path / "GPD").mkdir()
    paper_dir = tmp_path / "paper"
    paper_dir.mkdir()
    (paper_dir / "PAPER-CONFIG.json").write_text(
        json.dumps(
            {
                "title": "Configured Paper",
                "authors": [{"name": "A. Researcher"}],
                "abstract": "Abstract.",
                "sections": [{"title": "Intro", "content": "Hello."}],
                "figures": [],
            }
        ),
        encoding="utf-8",
    )

    literature_dir = tmp_path / "GPD" / "literature"
    literature_dir.mkdir(parents=True)
    (literature_dir / "topic-CITATION-SOURCES.json").write_text(
        json.dumps(
                [
                    {
                        "reference_id": "ref-auto",
                        "source_type": "paper",
                        "title": "Auto Reference",
                        "authors": ["A. Author"],
                        "year": "2024",
                    }
            ]
        ),
        encoding="utf-8",
    )

    result_payload = MagicMock()
    result_payload.manifest_path = paper_dir / "ARTIFACT-MANIFEST.json"
    result_payload.bibliography_audit_path = None
    result_payload.pdf_path = paper_dir / "configured_paper.pdf"
    result_payload.success = True
    result_payload.errors = []

    with (
        patch("gpd.mcp.paper.compiler.detect_latex_toolchain", return_value=_toolchain_capability()),
        patch("gpd.mcp.paper.compiler.build_paper", new=AsyncMock(return_value=result_payload)) as mock_build,
    ):
        result = runner.invoke(app, ["--raw", "--cwd", str(nested_cwd), "paper-build"], catch_exceptions=False)

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["bibliography_source"] == ""
    assert payload["citation_sources_path"] == "../GPD/literature/topic-CITATION-SOURCES.json"
    assert any("temporary directory" in warning for warning in payload["warnings"])
    assert mock_build.await_args.kwargs["citation_sources"] is not None
    assert mock_build.await_args.kwargs["citation_sources"][0].title == "Auto Reference"


def test_paper_build_auto_discovers_legacy_research_citation_sources_sidecar_when_literature_is_missing(
    tmp_path: Path,
) -> None:
    nested_cwd = tmp_path / "notes"
    nested_cwd.mkdir()
    (tmp_path / "GPD").mkdir()
    paper_dir = tmp_path / "paper"
    paper_dir.mkdir()
    (paper_dir / "PAPER-CONFIG.json").write_text(
        json.dumps(
            {
                "title": "Configured Paper",
                "authors": [{"name": "A. Researcher"}],
                "abstract": "Abstract.",
                "sections": [{"title": "Intro", "content": "Hello."}],
                "figures": [],
            }
        ),
        encoding="utf-8",
    )

    research_dir = tmp_path / "GPD" / "research"
    research_dir.mkdir(parents=True)
    (research_dir / "topic-CITATION-SOURCES.json").write_text(
        json.dumps(
            [
                {
                    "reference_id": "ref-legacy",
                    "source_type": "paper",
                    "title": "Legacy Reference",
                    "authors": ["A. Author"],
                    "year": "2023",
                }
            ]
        ),
        encoding="utf-8",
    )

    result_payload = MagicMock()
    result_payload.manifest_path = paper_dir / "ARTIFACT-MANIFEST.json"
    result_payload.bibliography_audit_path = None
    result_payload.pdf_path = paper_dir / "configured_paper.pdf"
    result_payload.success = True
    result_payload.errors = []

    with (
        patch("gpd.mcp.paper.compiler.detect_latex_toolchain", return_value=_toolchain_capability()),
        patch("gpd.mcp.paper.compiler.build_paper", new=AsyncMock(return_value=result_payload)) as mock_build,
    ):
        result = runner.invoke(app, ["--raw", "--cwd", str(nested_cwd), "paper-build"], catch_exceptions=False)

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["citation_sources_path"] == "../GPD/research/topic-CITATION-SOURCES.json"
    assert any("temporary directory" in warning for warning in payload["warnings"])
    assert mock_build.await_args.kwargs["citation_sources"] is not None
    assert mock_build.await_args.kwargs["citation_sources"][0].title == "Legacy Reference"


def test_paper_build_warns_when_multiple_literature_citation_sidecars_exist(tmp_path: Path) -> None:
    paper_dir = tmp_path / "paper"
    paper_dir.mkdir()
    (paper_dir / "PAPER-CONFIG.json").write_text(
        json.dumps(
            {
                "title": "Configured Paper",
                "authors": [{"name": "A. Researcher"}],
                "abstract": "Abstract.",
                "sections": [{"title": "Intro", "content": "Hello."}],
                "figures": [],
            }
        ),
        encoding="utf-8",
    )

    literature_dir = tmp_path / "GPD" / "literature"
    literature_dir.mkdir(parents=True)
    for name in ("alpha-CITATION-SOURCES.json", "beta-CITATION-SOURCES.json"):
        (literature_dir / name).write_text(
            json.dumps(
                [
                    {
                        "reference_id": f"ref-{name.removesuffix('-CITATION-SOURCES.json')}",
                        "source_type": "paper",
                        "title": f"Reference {name}",
                        "authors": ["A. Author"],
                        "year": "2024",
                    }
                ]
            ),
            encoding="utf-8",
        )

    result_payload = MagicMock()
    result_payload.manifest_path = paper_dir / "ARTIFACT-MANIFEST.json"
    result_payload.bibliography_audit_path = None
    result_payload.pdf_path = paper_dir / "configured_paper.pdf"
    result_payload.success = True
    result_payload.errors = []

    with (
        patch("gpd.mcp.paper.compiler.detect_latex_toolchain", return_value=_toolchain_capability()),
        patch("gpd.mcp.paper.compiler.build_paper", new=AsyncMock(return_value=result_payload)) as mock_build,
    ):
        result = runner.invoke(app, ["--raw", "--cwd", str(tmp_path), "paper-build"], catch_exceptions=False)

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["citation_sources_path"] == ""
    assert any("Multiple literature-review citation-source sidecars found" in warning for warning in payload["warnings"])
    assert mock_build.await_args.kwargs["citation_sources"] is None


def test_paper_build_rejects_citation_sidecar_entries_without_reference_id(tmp_path: Path) -> None:
    paper_dir = tmp_path / "paper"
    paper_dir.mkdir()
    (paper_dir / "PAPER-CONFIG.json").write_text(
        json.dumps(
            {
                "title": "Configured Paper",
                "authors": [{"name": "A. Researcher"}],
                "abstract": "Abstract.",
                "sections": [{"title": "Intro", "content": "Hello."}],
                "figures": [],
            }
        ),
        encoding="utf-8",
    )

    citation_source_path = tmp_path / "citation-sources.json"
    citation_source_path.write_text(
        json.dumps(
            [
                {
                    "source_type": "paper",
                    "title": "Broken Reference",
                    "authors": ["A. Author"],
                    "year": "2024",
                }
            ]
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "--raw",
            "--cwd",
            str(tmp_path),
            "paper-build",
            "--citation-sources",
            str(citation_source_path),
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 1
    assert "citation source ./citation-sources.json[0].reference_id must be a non-empty string" in result.output


def test_paper_build_rejects_citation_sidecar_entries_without_title(tmp_path: Path) -> None:
    paper_dir = tmp_path / "paper"
    paper_dir.mkdir()
    (paper_dir / "PAPER-CONFIG.json").write_text(
        json.dumps(
            {
                "title": "Configured Paper",
                "authors": [{"name": "A. Researcher"}],
                "abstract": "Abstract.",
                "sections": [{"title": "Intro", "content": "Hello."}],
                "figures": [],
            }
        ),
        encoding="utf-8",
    )

    citation_source_path = tmp_path / "citation-sources.json"
    citation_source_path.write_text(
        json.dumps(
            [
                {
                    "reference_id": "ref-broken",
                    "source_type": "paper",
                    "title": "   ",
                    "authors": ["A. Author"],
                    "year": "2024",
                }
            ]
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "--raw",
            "--cwd",
            str(tmp_path),
            "paper-build",
            "--citation-sources",
            str(citation_source_path),
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 1
    assert "citation source" in result.output
    assert "title must be a non-empty string" in result.output


def test_paper_build_surfaces_toolchain_failure_details(tmp_path: Path) -> None:
    paper_dir = tmp_path / "paper"
    paper_dir.mkdir()
    (paper_dir / "PAPER-CONFIG.json").write_text(
        json.dumps(
            {
                "title": "Configured Paper",
                "authors": [{"name": "A. Researcher"}],
                "abstract": "Abstract.",
                "sections": [{"title": "Intro", "content": "Hello."}],
                "figures": [],
            }
        ),
        encoding="utf-8",
    )

    result_payload = MagicMock()
    result_payload.manifest_path = paper_dir / "ARTIFACT-MANIFEST.json"
    result_payload.bibliography_audit_path = None
    result_payload.pdf_path = None
    result_payload.success = False
    result_payload.errors = ["Compiler 'pdflatex' not found."]

    mock_toolchain = _toolchain_capability(
        compiler_available=False,
        compiler_path=None,
        distribution=None,
        bibtex_available=False,
        latexmk_available=False,
        kpsewhich_available=False,
        readiness_state="blocked",
        message="No LaTeX compiler found.",
        warnings=["Install a LaTeX distribution to enable paper compilation."],
    )

    with (
        patch("gpd.mcp.paper.compiler.detect_latex_toolchain", return_value=mock_toolchain),
        patch("gpd.mcp.paper.compiler.build_paper", new=AsyncMock(return_value=result_payload)),
    ):
        result = runner.invoke(app, ["--raw", "--cwd", str(tmp_path), "paper-build"], catch_exceptions=False)

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["success"] is False
    assert payload["errors"] == ["Compiler 'pdflatex' not found."]
    assert payload["toolchain"]["available"] is False
    assert payload["toolchain"]["compiler_available"] is False
    assert payload["toolchain"]["compiler"] == "pdflatex"
    assert payload["toolchain"]["full_toolchain_available"] is False
    assert payload["toolchain"]["readiness_state"] == "blocked"
    assert payload["toolchain"]["message"] == "No LaTeX compiler found."
    assert payload["toolchain"]["paper_build_ready"] is False
    assert payload["toolchain"]["arxiv_submission_ready"] is False
    assert payload["toolchain"]["warnings"] == ["Install a LaTeX distribution to enable paper compilation."]
    assert any("temporary directory" in warning for warning in payload["warnings"])
    assert any(warning == "Install a LaTeX distribution to enable paper compilation." for warning in payload["warnings"])


def test_paper_build_surfaces_partial_toolchain_warnings(tmp_path: Path) -> None:
    paper_dir = tmp_path / "paper"
    paper_dir.mkdir()
    (paper_dir / "PAPER-CONFIG.json").write_text(
        json.dumps(
            {
                "title": "Configured Paper",
                "authors": [{"name": "A. Researcher"}],
                "abstract": "Abstract.",
                "sections": [{"title": "Intro", "content": "Hello."}],
                "figures": [],
            }
        ),
        encoding="utf-8",
    )

    result_payload = MagicMock()
    result_payload.manifest_path = paper_dir / "ARTIFACT-MANIFEST.json"
    result_payload.bibliography_audit_path = None
    result_payload.pdf_path = paper_dir / "configured-paper.pdf"
    result_payload.success = True
    result_payload.errors = []

    mock_toolchain = _toolchain_capability(
        latexmk_available=False,
        kpsewhich_available=False,
        warnings=[
            "latexmk not found; multi-pass compilation will fall back to manual passes.",
            "kpsewhich not found; TeX resource checks will assume installed resources.",
        ],
    )

    with (
        patch("gpd.mcp.paper.compiler.detect_latex_toolchain", return_value=mock_toolchain),
        patch("gpd.mcp.paper.compiler.build_paper", new=AsyncMock(return_value=result_payload)),
    ):
        result = runner.invoke(app, ["--raw", "--cwd", str(tmp_path), "paper-build"], catch_exceptions=False)

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["toolchain"]["paper_build_ready"] is True
    assert payload["toolchain"]["arxiv_submission_ready"] is False
    assert payload["toolchain"]["warnings"] == [
        "latexmk not found; multi-pass compilation will fall back to manual passes.",
        "kpsewhich not found; TeX resource checks will assume installed resources.",
        "latexmk not found; repeated LaTeX passes may be degraded.",
        "kpsewhich not found; TeX resource checks may be best-effort only.",
    ]
    assert any(
        warning == "latexmk not found; repeated LaTeX passes may be degraded."
        for warning in payload["warnings"]
    )
    assert any(
        warning == "kpsewhich not found; TeX resource checks may be best-effort only."
        for warning in payload["warnings"]
    )


def test_paper_build_toolchain_payload_surfaces_missing_bibtex_as_hard_failure_risk() -> None:
    with patch(
        "gpd.mcp.paper.compiler.detect_latex_toolchain",
        return_value=_toolchain_capability(
            bibtex_available=False,
            warnings=[
                "bibtex not found; bibliography-free builds may still work, but citation-bearing builds and submission prep can fail without bibtex."
            ],
        ),
    ):
        payload = cli_module._paper_build_toolchain_payload()

    assert payload["paper_build_ready"] is True
    assert payload["bibliography_support_available"] is False
    assert (
        "bibtex not found; bibliography-free builds may still work, but citation-bearing builds and submission prep can fail without bibtex."
        in payload["warnings"]
    )


# ─── ported command subcommands ─────────────────────────────────────────────


@patch("gpd.core.commands.cmd_current_timestamp")
def test_timestamp_subcommand(mock_ts):
    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"timestamp": "2026-03-04T12:00:00+00:00"}
    mock_ts.return_value = mock_result
    result = runner.invoke(app, ["timestamp", "full"])
    assert result.exit_code == 0
    mock_ts.assert_called_once_with("full")


@patch("gpd.core.commands.cmd_generate_slug")
def test_slug_subcommand(mock_slug):
    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"slug": "hello-world"}
    mock_slug.return_value = mock_result
    result = runner.invoke(app, ["slug", "Hello World"])
    assert result.exit_code == 0
    mock_slug.assert_called_once_with("Hello World")


@patch("gpd.core.commands.cmd_verify_path_exists")
def test_verify_path_subcommand(mock_verify):
    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"exists": True, "type": "file"}
    mock_verify.return_value = mock_result
    result = runner.invoke(app, ["verify-path", "some/path"])
    assert result.exit_code == 0
    mock_verify.assert_called_once()


@patch("gpd.core.commands.cmd_history_digest")
def test_history_digest_subcommand(mock_digest):
    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"phases": {}, "decisions": [], "methods": []}
    mock_digest.return_value = mock_result
    result = runner.invoke(app, ["history-digest"])
    assert result.exit_code == 0
    mock_digest.assert_called_once()


@patch("gpd.core.checkpoints.sync_phase_checkpoints")
def test_sync_phase_checkpoints_subcommand(mock_sync):
    mock_result = MagicMock()
    mock_result.model_dump.return_value = {
        "generated": True,
        "phase_count": 1,
        "preserved_phase_count": 0,
        "checkpoint_dir": "GPD/phase-checkpoints",
        "root_index": "GPD/CHECKPOINTS.md",
        "updated_files": ["GPD/phase-checkpoints/01-test-phase.md", "GPD/CHECKPOINTS.md"],
        "removed_files": [],
    }
    mock_sync.return_value = mock_result
    result = runner.invoke(app, ["sync-phase-checkpoints"])
    assert result.exit_code == 0
    mock_sync.assert_called_once()


@patch("gpd.core.commands.cmd_regression_check")
def test_regression_check_subcommand_passing(mock_check):
    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"passed": True, "issues": [], "phases_checked": 2}
    mock_result.passed = True
    mock_check.return_value = mock_result
    result = runner.invoke(app, ["regression-check"])
    assert result.exit_code == 0


@patch("gpd.core.commands.cmd_regression_check")
def test_regression_check_subcommand_failing(mock_check):
    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"passed": False, "issues": [{"type": "conflict"}], "phases_checked": 2}
    mock_result.passed = False
    mock_check.return_value = mock_result
    result = runner.invoke(app, ["regression-check"])
    assert result.exit_code == 1
