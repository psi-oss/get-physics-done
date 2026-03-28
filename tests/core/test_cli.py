"""Tests for gpd.cli — unified CLI entry point.

Tests use typer.testing.CliRunner which invokes the CLI in-process.
We mock the underlying gpd.core.* functions since those modules may not
be fully ported yet and have their own test suites.
"""

from __future__ import annotations

import builtins
import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

import gpd.cli as cli_module
import gpd.runtime_cli as runtime_cli
from gpd.adapters import get_adapter, list_runtimes
from gpd.cli import app
from gpd.core import cli_args as cli_args_module
from gpd.core.costs import CostProjectSummary, CostSessionSummary, CostSummary

runner = CliRunner()


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

    assert captured["argv"] == [cli_module.sys.executable, "-m", "gpd.cli", "version"]
    env = captured["env"]
    assert isinstance(env, dict)
    assert env["GPD_DISABLE_CHECKOUT_REEXEC"] == "1"
    assert env["PYTHONPATH"].split(os.pathsep)[0] == str(checkout / "src")


def test_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "observe" in result.output
    assert "state" in result.output
    assert "phase" in result.output
    assert "health" in result.output
    assert "paper-build" in result.output


def test_help_surfaces_local_setup_and_preflight_commands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
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


def test_help_surfaces_permissions_readiness_commands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    normalized_output = " ".join(result.output.split())
    assert "permissions" in normalized_output
    assert "Runtime permission readiness and sync" in normalized_output
    assert "gpd doctor --runtime <runtime> --local" in normalized_output
    assert "gpd permissions status --runtime <runtime> --autonomy balanced" in normalized_output
    assert "gpd observe execution" in normalized_output
    assert "gpd resume --recent" in normalized_output


def test_help_surfaces_workflow_presets_surface() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    normalized_output = " ".join(result.output.split())
    assert "presets" in normalized_output
    assert "Workflow presets for local CLI preview" in normalized_output
    assert "application" in normalized_output


def test_help_surfaces_integrations_surface() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    normalized_output = " ".join(result.output.split())
    assert "integrations" in normalized_output
    assert "Optional shared capability integrations" in normalized_output


def test_workflow_presets_help_surfaces_apply_command() -> None:
    result = runner.invoke(app, ["presets", "apply", "--help"])
    assert result.exit_code == 0
    normalized_output = " ".join(result.output.split())
    assert "--dry-run" in normalized_output
    assert "Show the merged config without writing it" in normalized_output


def test_workflow_presets_surface_lists_catalog() -> None:
    result = runner.invoke(app, ["presets", "list"])
    assert result.exit_code == 0
    assert "Workflow Presets" in result.output
    assert "core-research" in result.output
    assert "Core research" in result.output


def test_integrations_status_reports_config_only_and_plan_readiness(tmp_path: Path) -> None:
    result = runner.invoke(app, ["--cwd", str(tmp_path), "--raw", "integrations", "status", "wolfram"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["integration"] == "wolfram"
    assert payload["configured"] is False
    assert payload["enabled"] is False
    assert payload["state"] == "disabled"
    assert payload["scope"] == "config-only"
    assert payload["plan_readiness_command"] == "gpd validate plan-preflight <PLAN.md>"
    assert "plan-preflight" in payload["next_step"]
    assert "Mathematica" in payload["local_mathematica_note"]


def test_integrations_enable_and_disable_wolfram_persist_project_local_config(tmp_path: Path) -> None:
    enable_result = runner.invoke(app, ["--cwd", str(tmp_path), "--raw", "integrations", "enable", "wolfram"])
    assert enable_result.exit_code == 0
    enable_payload = json.loads(enable_result.output)
    assert enable_payload["enabled"] is True
    assert enable_payload["scope"] == "config-only"

    config_path = tmp_path / "GPD" / "integrations.json"
    assert config_path.exists()
    saved = json.loads(config_path.read_text(encoding="utf-8"))
    assert saved["wolfram"]["enabled"] is True

    disable_result = runner.invoke(app, ["--cwd", str(tmp_path), "--raw", "integrations", "disable", "wolfram"])
    assert disable_result.exit_code == 0
    disable_payload = json.loads(disable_result.output)
    assert disable_payload["enabled"] is False

    status_result = runner.invoke(app, ["--cwd", str(tmp_path), "--raw", "integrations", "status", "wolfram"])
    assert status_result.exit_code == 0
    status_payload = json.loads(status_result.output)
    assert status_payload["enabled"] is False
    assert status_payload["state"] == "disabled"


def test_workflow_preset_show_raw_outputs_central_contract() -> None:
    result = runner.invoke(app, ["--raw", "presets", "show", "core-research"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["id"] == "core-research"
    assert payload["label"] == "Core research"
    assert payload["required_checks"] == []
    assert payload["recommended_config"]["model_profile"] == "review"
    assert payload["summary"] == "Balanced default workflow for planning, execution, and verification."


def test_workflow_preset_apply_dry_run_previews_merged_config(tmp_path: Path) -> None:
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
    assert payload["ignored_keys"] == ["model_cost_posture"]
    preview = payload["preview_config"]
    assert preview["autonomy"] == "balanced"
    assert preview["research_mode"] == "balanced"
    assert preview["model_profile"] == "review"
    assert preview["parallelization"] is True
    assert preview["commit_docs"] is True
    assert preview["execution"]["review_cadence"] == "adaptive"
    assert preview["execution"]["checkpoint_after_n_tasks"] == 7
    assert preview["execution"]["checkpoint_before_downstream_dependent_tasks"] is False
    assert preview["research"] is True
    assert preview["plan_checker"] is True
    assert preview["verifier"] is True
    assert "planning" not in preview
    assert "workflow" not in preview
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
        input_tokens=1200,
        output_tokens=300,
        total_tokens=1500,
        cost_usd=None,
        last_recorded_at="2026-03-27T00:00:00+00:00",
        runtimes=["codex"],
        models=["gpt-5.4"],
    )
    current_session = CostSessionSummary(
        session_id="session-123",
        project_root=workspace_text,
        record_count=1,
        usage_status="measured",
        cost_status="unavailable",
        input_tokens=800,
        output_tokens=200,
        total_tokens=1000,
        cost_usd=None,
        last_recorded_at="2026-03-27T00:00:00+00:00",
        runtimes=["codex"],
        models=["gpt-5.4"],
    )
    return CostSummary(
        workspace_root=workspace_text,
        active_runtime="codex",
        active_runtime_capabilities={
            "permissions_surface": "config-file",
            "statusline_surface": "none",
            "notify_surface": "explicit",
            "telemetry_source": "notify-hook",
            "telemetry_completeness": "best-effort",
        },
        model_profile="review",
        runtime_model_selection="runtime defaults",
        current_session_id="session-123",
        project=project,
        current_session=current_session,
        recent_sessions=[current_session],
        guidance=[
            "Measured tokens are available, but no pricing snapshot is configured at the machine-local cost root, so USD cost is unavailable.",
            "Current model posture: profile `review` with codex runtime defaults. Use the runtime `settings` command only if you want explicit tier-model overrides.",
        ],
    )


def test_cost_help_surfaces_machine_local_advisory_role() -> None:
    result = runner.invoke(app, ["cost", "--help"])
    assert result.exit_code == 0
    normalized_output = " ".join(result.output.split())
    assert "Show machine-local usage and cost summaries" in normalized_output
    assert "--last-sessions" in result.output
    assert "Show the most recent N recorded usage" in normalized_output
    assert "[default: 5]" in normalized_output


def test_cost_raw_outputs_summary_payload(tmp_path: Path) -> None:
    summary = _sample_cost_summary(tmp_path)

    with patch("gpd.core.costs.build_cost_summary", return_value=summary) as mock_build:
        result = runner.invoke(app, ["--cwd", str(tmp_path), "--raw", "cost", "--last-sessions", "2"])

    assert result.exit_code == 0
    mock_build.assert_called_once_with(tmp_path, last_sessions=2)
    payload = json.loads(result.output)
    assert payload["workspace_root"] == str(tmp_path)
    assert payload["active_runtime"] == "codex"
    assert payload["active_runtime_capabilities"]["telemetry_completeness"] == "best-effort"
    assert payload["active_runtime_capabilities"]["telemetry_source"] == "notify-hook"
    assert payload["model_profile"] == "review"
    assert payload["runtime_model_selection"] == "runtime defaults"
    assert payload["project"]["usage_status"] == "measured"
    assert payload["project"]["cost_status"] == "unavailable"
    assert payload["project"]["total_tokens"] == 1500
    assert payload["project"]["cost_usd"] is None
    assert payload["recent_sessions"][0]["session_id"] == "session-123"
    assert payload["recent_sessions"][0]["total_tokens"] == 1000
    assert any("no pricing snapshot is configured" in item for item in payload["guidance"])


def test_cost_human_output_stays_read_only_and_advisory(tmp_path: Path) -> None:
    summary = _sample_cost_summary(tmp_path)

    with patch("gpd.core.costs.build_cost_summary", return_value=summary):
        result = runner.invoke(app, ["--cwd", str(tmp_path), "cost", "--last-sessions", "1"])

    assert result.exit_code == 0
    assert "Cost Summary" in result.output
    assert "Read-only machine-local usage/cost summary." in result.output
    assert "clearly labels estimates or unavailable values" in result.output
    assert "Current posture" in result.output
    assert "Telemetry support" in result.output
    assert "best-effort via notify-hook" in result.output
    assert "Pricing snapshot" in result.output
    assert "not configured" in result.output
    assert "Current project" in result.output
    assert "Recent sessions" in result.output
    assert "Measured tokens are available, but no pricing snapshot is configured" in result.output
    assert "Current model posture: profile `review` with codex runtime defaults." in result.output


def test_permissions_status_raw_includes_runtime_capabilities(tmp_path: Path) -> None:
    with (
        patch("gpd.cli._resolve_permissions_runtime_name", return_value="gemini"),
        patch("gpd.cli._resolve_permissions_target_dir", return_value=tmp_path / ".gemini"),
        patch("gpd.cli._resolve_permissions_autonomy", return_value="yolo"),
        patch(
            "gpd.adapters.get_adapter",
            return_value=MagicMock(
                runtime_permissions_status=MagicMock(
                    return_value={
                        "runtime": "gemini",
                        "desired_mode": "yolo",
                        "configured_mode": "launch-wrapper",
                        "config_aligned": True,
                        "requires_relaunch": True,
                        "managed_by_gpd": True,
                        "message": "Gemini only supports yolo at launch time.",
                        "next_step": None,
                    }
                )
            ),
        ),
    ):
        result = runner.invoke(
            app,
            ["--raw", "permissions", "status", "--runtime", "gemini", "--autonomy", "yolo"],
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
    assert result.exit_code == 0
    assert "Check GPD installation and environment health" in result.output
    assert "inspect runtime readiness" in result.output
    assert "--live-executable-probes" in result.output
    assert "--runtime" in result.output
    assert "--local" in result.output
    assert "--global" in result.output
    assert "--target-dir" in result.output


def test_permissions_help_surfaces_status_and_sync_roles() -> None:
    result = runner.invoke(app, ["permissions", "--help"])
    assert result.exit_code == 0
    assert "Runtime permission readiness and sync" in result.output
    assert "status" in result.output
    assert "ready for unattended use" in result.output
    assert "sync" in result.output
    assert "gpd:settings" in result.output


def test_permissions_status_help_surfaces_readiness_options() -> None:
    result = runner.invoke(app, ["permissions", "status", "--help"])
    assert result.exit_code == 0
    assert "ready for unattended use" in result.output
    assert "requested autonomy" in result.output
    assert "--runtime" in result.output
    assert "--autonomy" in result.output
    assert "--target-dir" in result.output


def test_permissions_sync_help_surfaces_guided_runtime_changes() -> None:
    result = runner.invoke(app, ["permissions", "sync", "--help"])
    assert result.exit_code == 0
    assert "persist runtime-owned permission settings" in result.output
    assert "gpd:settings" in result.output
    assert "--runtime" in result.output
    assert "--autonomy" in result.output
    assert "--target-dir" in result.output


def test_permissions_status_surfaces_runtime_capabilities_and_config_scope() -> None:
    class _DummyAdapter:
        def runtime_permissions_status(self, target_dir: Path, *, autonomy: str) -> dict[str, object]:
            return {
                "runtime": "codex",
                "desired_mode": "default",
                "configured_mode": "on-request/workspace-write",
                "config_aligned": True,
                "requires_relaunch": False,
                "managed_by_gpd": False,
                "approval_policy": "on-request",
                "sandbox_mode": "workspace-write",
                "message": "Codex is using its normal approval and sandbox defaults.",
            }

    with (
        patch("gpd.cli._resolve_permissions_runtime_name", return_value="codex"),
        patch("gpd.cli._resolve_permissions_target_dir", return_value=Path("/tmp/.codex")),
        patch("gpd.cli._resolve_permissions_autonomy", return_value="balanced"),
        patch("gpd.adapters.get_adapter", return_value=_DummyAdapter()),
    ):
        result = runner.invoke(app, ["--raw", "permissions", "status", "--runtime", "codex", "--autonomy", "balanced"])

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
    class _DummyAdapter:
        def runtime_permissions_status(self, target_dir: Path, *, autonomy: str) -> dict[str, object]:
            return {
                "runtime": "claude-code",
                "desired_mode": "default",
                "configured_mode": "bypassPermissions",
                "config_aligned": True,
                "requires_relaunch": False,
                "managed_by_gpd": False,
                "message": (
                    "Claude Code is still configured for bypassPermissions, but GPD left it untouched because "
                    "that setting was not created by a prior GPD yolo sync."
                ),
            }

    with (
        patch("gpd.cli._resolve_permissions_runtime_name", return_value="claude-code"),
        patch("gpd.cli._resolve_permissions_target_dir", return_value=Path("/tmp/.claude")),
        patch("gpd.cli._resolve_permissions_autonomy", return_value="balanced"),
        patch("gpd.adapters.get_adapter", return_value=_DummyAdapter()),
    ):
        result = runner.invoke(
            app,
            ["--raw", "permissions", "status", "--runtime", "claude-code", "--autonomy", "balanced"],
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
    class _DummyAdapter:
        def sync_runtime_permissions(self, target_dir: Path, *, autonomy: str) -> dict[str, object]:
            return {
                "runtime": "gemini",
                "desired_mode": "yolo",
                "configured_mode": "launch-wrapper",
                "config_aligned": True,
                "requires_relaunch": True,
                "managed_by_gpd": True,
                "launch_command": "/tmp/.gemini/get-physics-done/bin/gemini-gpd-yolo",
                "message": "Gemini only supports yolo at launch time. The GPD launcher is ready for the next session.",
            }

    with (
        patch("gpd.cli._resolve_permissions_runtime_name", return_value="gemini"),
        patch("gpd.cli._resolve_permissions_target_dir", return_value=Path("/tmp/.gemini")),
        patch("gpd.cli._resolve_permissions_autonomy", return_value="yolo"),
        patch("gpd.adapters.get_adapter", return_value=_DummyAdapter()),
    ):
        payload = cli_module._runtime_permissions_payload(
            runtime="gemini",
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
        self.runtime_name = "codex"
        self.display_name = "Codex"
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
    local_target = tmp_path / ".codex"
    global_target = tmp_path / ".codex-global"
    _write_install_manifest(local_target, runtime="codex")
    global_target.mkdir(parents=True, exist_ok=True)
    adapter = _PermissionsTargetAdapter(
        local_target=local_target,
        global_target=global_target,
        missing_install_artifacts=("agents/gpd-help/SKILL.md",),
    )

    with (
        patch("gpd.cli._resolve_permissions_runtime_name", return_value="codex"),
        patch("gpd.cli._resolve_permissions_autonomy", return_value="balanced"),
        patch("gpd.hooks.runtime_detect.detect_runtime_install_target", return_value=None),
        patch("gpd.hooks.runtime_detect.detect_install_scope", return_value=None),
        patch("gpd.adapters.get_adapter", return_value=adapter),
    ):
        result = runner.invoke(app, ["--raw", "permissions", "status", "--runtime", "codex", "--autonomy", "balanced"])

    assert result.exit_code == 1
    parsed = json.loads(result.output)
    assert "incomplete GPD install" in parsed["error"]
    assert "Missing artifacts:" in parsed["error"]
    assert "No GPD install found" not in parsed["error"]


def test_permissions_status_reports_foreign_install_explicitly(tmp_path: Path) -> None:
    target = tmp_path / ".codex"
    _write_install_manifest(target, runtime="claude-code")
    adapter = _PermissionsTargetAdapter(local_target=target, global_target=target)

    with (
        patch("gpd.cli._resolve_permissions_runtime_name", return_value="codex"),
        patch("gpd.cli._resolve_permissions_autonomy", return_value="balanced"),
        patch("gpd.adapters.get_adapter", return_value=adapter),
    ):
        result = runner.invoke(
            app,
            ["--raw", "permissions", "status", "--runtime", "codex", "--target-dir", str(target), "--autonomy", "balanced"],
        )

    assert result.exit_code == 1
    parsed = json.loads(result.output)
    assert "belongs to runtime 'claude-code'" in parsed["error"]
    assert "No GPD install found" not in parsed["error"]


def test_permissions_sync_reports_untrusted_manifest_explicitly(tmp_path: Path) -> None:
    target = tmp_path / ".codex"
    _write_install_manifest(target, runtime="codex", raw="{")
    adapter = _PermissionsTargetAdapter(local_target=target, global_target=target)

    with (
        patch("gpd.cli._resolve_permissions_runtime_name", return_value="codex"),
        patch("gpd.cli._resolve_permissions_autonomy", return_value="balanced"),
        patch("gpd.adapters.get_adapter", return_value=adapter),
    ):
        result = runner.invoke(
            app,
            ["--raw", "permissions", "sync", "--runtime", "codex", "--target-dir", str(target), "--autonomy", "balanced"],
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
    assert "--recent" in result.output
    assert "List recent GPD projects on this machine" in result.output


def test_resume_recent_raw_surfaces_machine_local_recent_projects(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "home"
    recent_index_dir = home / ".gpd" / "recent-projects"
    recent_index_dir.mkdir(parents=True, exist_ok=True)

    resumable_root = tmp_path / "projects" / "alpha"
    resumable_root.mkdir(parents=True, exist_ok=True)
    unavailable_root = tmp_path / "projects" / "beta-missing"

    (recent_index_dir / "index.json").write_text(
        json.dumps(
            {
                "projects": [
                    {
                        "project_root": str(unavailable_root),
                        "last_session_at": "2026-03-20T09:00:00+00:00",
                        "stopped_at": "Phase 2",
                        "status": "paused",
                        "resumable": False,
                    },
                    {
                        "project_root": str(resumable_root),
                        "last_session_at": "2026-03-21T10:30:00+00:00",
                        "stopped_at": "Phase 4",
                        "status": "paused",
                        "resumable": True,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(cli_module.Path, "home", lambda: home)

    result = runner.invoke(app, ["--raw", "resume", "--recent"])
    parsed = json.loads(result.output)

    assert parsed["count"] == 2
    assert parsed["projects"][0]["project_root"] == str(resumable_root)
    assert parsed["projects"][0]["resumable"] is True
    assert parsed["projects"][0]["status"] == "paused"
    assert parsed["projects"][1]["project_root"] == str(unavailable_root)
    assert parsed["projects"][1]["available"] is False
    assert parsed["projects"][1]["status"] == "unavailable"


def test_resume_recent_human_output_surfaces_command_and_missing_projects(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "home"
    recent_index_dir = home / ".gpd" / "recent-projects"
    recent_index_dir.mkdir(parents=True, exist_ok=True)

    resumable_root = tmp_path / "projects" / "gamma"
    resumable_root.mkdir(parents=True, exist_ok=True)
    missing_root = tmp_path / "projects" / "delta-missing"

    (recent_index_dir / "index.json").write_text(
        json.dumps(
            {
                "projects": [
                    {
                        "project_root": str(resumable_root),
                        "last_session_at": "2026-03-21T11:00:00+00:00",
                        "stopped_at": "Phase 1",
                        "status": "paused",
                        "resumable": True,
                    },
                    {
                        "project_root": str(missing_root),
                        "last_session_at": "2026-03-19T08:00:00+00:00",
                        "stopped_at": "Phase 3",
                        "status": "paused",
                        "resumable": False,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(cli_module.Path, "home", lambda: home)

    result = runner.invoke(app, ["resume", "--recent"])

    assert result.exit_code == 0
    assert "Recent Projects" in result.output
    assert "gpd --cwd" in result.output


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
                "projects": [
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

    result = runner.invoke(app, ["--raw", "resume", "--recent"])
    parsed = json.loads(result.output)

    assert parsed["count"] == 1
    assert parsed["projects"][0]["project_root"] == str(project_root)
    assert parsed["projects"][0]["resume_file_available"] is False
    assert parsed["projects"][0]["resume_file_reason"] == "resume file missing"
    assert parsed["projects"][0]["resumable"] is False


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
    assert "gpd resume --recent" in result.output


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


def test_validate_command_context_help_surfaces_registry_argument_name() -> None:
    result = runner.invoke(app, ["validate", "command-context", "--help"])
    assert result.exit_code == 0
    assert "Run centralized command-context preflight based on command metadata." in result.output
    assert "Command registry key or gpd:name" in result.output


def _plan_with_tool_requirements(tool_requirements_block: str) -> str:
    fixture = (
        Path(__file__).resolve().parents[1] / "fixtures" / "stage0" / "plan_with_contract.md"
    ).read_text(encoding="utf-8")
    return fixture.replace("interactive: false\n", f"interactive: false\n{tool_requirements_block}", 1)


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


@patch("gpd.core.state.state_get")
def test_state_get_section(mock_get):
    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"section": "position", "data": {}}
    mock_get.return_value = mock_result
    result = runner.invoke(app, ["state", "get", "position"])
    assert result.exit_code == 0
    mock_get.assert_called_once()


@patch("gpd.core.state.state_update")
def test_state_update(mock_update):
    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"updated": True}
    mock_update.return_value = mock_result
    result = runner.invoke(app, ["state", "update", "status", "executing"])
    assert result.exit_code == 0
    mock_update.assert_called_once()


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


@patch("gpd.core.phases.progress_render")
def test_app_call_accepts_trailing_raw_and_cwd(mock_progress, tmp_path: Path, capsys) -> None:
    mock_progress.return_value = {"bar": "ok"}

    try:
        cli_module.app(args=["progress", "bar", "--cwd", str(tmp_path), "--raw"])
    except SystemExit as exc:
        assert exc.code == 0

    captured = capsys.readouterr()
    assert json.loads(captured.out)["bar"] == "ok"
    mock_progress.assert_called_once_with(tmp_path.resolve(), "bar")


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

    result = runner.invoke(app, ["--cwd", str(tmp_path), "--raw", "doctor", "--runtime", "codex", "--local"])

    assert result.exit_code == 0
    assert json.loads(result.output) == {"mode": "runtime-readiness", "overall": "ok"}
    mock_doctor.assert_called_once_with(
        specs_dir=SPECS_DIR,
        runtime="codex",
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


def test_doctor_rejects_scope_without_runtime() -> None:
    result = runner.invoke(app, ["doctor", "--global"])

    assert result.exit_code == 1
    assert "--runtime is required" in result.output


def test_doctor_rejects_target_dir_without_runtime(tmp_path: Path) -> None:
    result = runner.invoke(app, ["doctor", "--target-dir", str(tmp_path / ".gpd-target")])

    assert result.exit_code == 1
    assert "--runtime is required" in result.output


def test_runtime_surface_helpers_track_the_active_runtime_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime_name = list_runtimes()[0]
    prefix = get_adapter(runtime_name).command_prefix
    workspace = Path("/tmp/runtime-surface")

    monkeypatch.setattr(cli_module, "detect_runtime_for_gpd_use", lambda cwd=None: runtime_name)

    assert cli_module._active_runtime_command_prefix(cwd=workspace) == prefix
    assert cli_module._active_runtime_command_family(cwd=workspace) == f"{prefix}*"
    assert cli_module._active_runtime_new_project_command(cwd=workspace) == f"{prefix}new-project"
    assert cli_module._runtime_surface_dispatch_note(cwd=workspace) == (
        f"This preflight validates the public `{prefix}*` runtime command surface from the command registry. "
        "It does not guarantee a same-name local `gpd` subcommand exists."
    )

    validated_surface = cli_module._validated_runtime_surface(cwd=workspace)
    assert validated_surface in {
        "public_runtime_command_surface",
        "public_runtime_slash_command",
        "public_runtime_dollar_command",
    }
    if prefix.startswith("/"):
        assert validated_surface == "public_runtime_slash_command"
    elif prefix.startswith("$"):
        assert validated_surface == "public_runtime_dollar_command"
    else:
        assert validated_surface == "public_runtime_command_surface"


def test_runtime_surface_helpers_fall_back_when_runtime_resolution_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = Path("/tmp/runtime-surface-fallback")

    def _raise_runtime_error(cwd=None) -> str:
        raise RuntimeError("runtime resolution failed")

    monkeypatch.setattr(cli_module, "detect_runtime_for_gpd_use", _raise_runtime_error)

    assert cli_module._active_runtime_command_prefix(cwd=workspace) is None
    assert cli_module._active_runtime_command_family(cwd=workspace) == "the active runtime command surface"
    assert cli_module._active_runtime_new_project_command(cwd=workspace) == "the active runtime's `new-project` command"
    assert cli_module._runtime_surface_dispatch_note(cwd=workspace) == (
        "This preflight validates the active runtime command surface from the command registry. "
        "It does not guarantee a same-name local `gpd` subcommand exists."
    )
    assert cli_module._validated_runtime_surface(cwd=workspace) == "public_runtime_command_surface"


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
    assert "waiting" in result.output.lower()
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
def test_suggest(mock_suggest):
    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"suggestions": []}
    mock_suggest.return_value = mock_result
    result = runner.invoke(app, ["suggest"])
    assert result.exit_code == 0
    mock_suggest.assert_called_once()


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


@patch("gpd.core.context.init_new_project")
def test_init_new_project(mock_init):
    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"context": "..."}
    mock_init.return_value = mock_result
    result = runner.invoke(app, ["init", "new-project"])
    assert result.exit_code == 0
    mock_init.assert_called_once()


def test_init_resume_help_surfaces_recovery_snapshot_entrypoint() -> None:
    result = runner.invoke(app, ["init", "resume", "--help"])

    assert result.exit_code == 0
    assert "Usage: gpd init resume" in result.output
    assert "Assemble context for resuming previous work." in result.output


@patch("gpd.core.context.init_resume")
def test_init_resume(mock_init):
    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"segment_candidates": []}
    mock_init.return_value = mock_result

    result = runner.invoke(app, ["init", "resume"])

    assert result.exit_code == 0
    mock_init.assert_called_once()


def test_paper_build_uses_default_config_surface(tmp_path: Path):
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
    result_payload.manifest_path = paper_dir / "ARTIFACT-MANIFEST.json"
    result_payload.bibliography_audit_path = None
    result_payload.pdf_path = paper_dir / "main.pdf"
    result_payload.success = True
    result_payload.errors = []

    with (
        patch("gpd.cli.shutil.which", side_effect=lambda binary: {
            "latexmk": "/usr/bin/latexmk",
            "bibtex": "/usr/bin/bibtex",
            "kpsewhich": "/usr/bin/kpsewhich",
        }.get(binary)),
        patch("gpd.mcp.paper.compiler.detect_latex_toolchain") as mock_detect,
        patch("gpd.mcp.paper.compiler.build_paper", new=AsyncMock(return_value=result_payload)) as mock_build,
    ):
        mock_detect.return_value.available = True
        mock_detect.return_value.compiler_path = "/usr/bin/pdflatex"
        mock_detect.return_value.distribution = "TeX Live"
        mock_detect.return_value.message = "pdflatex found (TeX Live): /usr/bin/pdflatex"
        result = runner.invoke(app, ["--raw", "--cwd", str(tmp_path), "paper-build"], catch_exceptions=False)

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["config_path"] == "./paper/PAPER-CONFIG.json"
    assert payload["output_dir"] == "./paper"
    assert payload["tex_path"] == "./paper/main.tex"
    assert payload["bibliography_source"] == "./references/references.bib"
    assert payload["manifest_path"] == "./paper/ARTIFACT-MANIFEST.json"
    assert payload["pdf_path"] == "./paper/main.pdf"
    assert payload["toolchain"] == {
        "compiler_available": True,
        "compiler_path": "/usr/bin/pdflatex",
        "distribution": "TeX Live",
        "latexmk_available": True,
        "bibtex_available": True,
        "kpsewhich_available": True,
        "compile_checks_available": True,
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


def test_paper_build_prefers_paper_dir_before_later_config_roots(tmp_path: Path) -> None:
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

    result_payload = MagicMock()
    result_payload.manifest_path = paper_dir / "ARTIFACT-MANIFEST.json"
    result_payload.bibliography_audit_path = None
    result_payload.pdf_path = paper_dir / "main.pdf"
    result_payload.success = True
    result_payload.errors = []

    with patch("gpd.mcp.paper.compiler.build_paper", new=AsyncMock(return_value=result_payload)) as mock_build:
        result = runner.invoke(app, ["--raw", "--cwd", str(tmp_path), "paper-build"], catch_exceptions=False)

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["config_path"] == "./paper/PAPER-CONFIG.json"
    assert mock_build.await_args.args[0].title == "paper-uppercase"


def test_paper_build_prefers_manuscript_before_draft(tmp_path: Path) -> None:
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

    result_payload = MagicMock()
    result_payload.manifest_path = manuscript_dir / "ARTIFACT-MANIFEST.json"
    result_payload.bibliography_audit_path = None
    result_payload.pdf_path = manuscript_dir / "main.pdf"
    result_payload.success = True
    result_payload.errors = []

    with patch("gpd.mcp.paper.compiler.build_paper", new=AsyncMock(return_value=result_payload)) as mock_build:
        result = runner.invoke(app, ["--raw", "--cwd", str(tmp_path), "paper-build"], catch_exceptions=False)

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["config_path"] == "./manuscript/PAPER-CONFIG.json"
    assert mock_build.await_args.args[0].title == "manuscript-uppercase"


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
    result_payload.bibliography_audit_path = None
    result_payload.pdf_path = output_dir / "main.pdf"
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
    assert "configsource" in mock_build.await_args.kwargs["bib_data"].entries


def test_paper_build_without_bibliography_does_not_import_pybtex(tmp_path: Path, monkeypatch) -> None:
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
    result_payload.pdf_path = paper_dir / "main.pdf"
    result_payload.success = True
    result_payload.errors = []

    with patch("gpd.mcp.paper.compiler.build_paper", new=AsyncMock(return_value=result_payload)) as mock_build:
        result = runner.invoke(app, ["--raw", "--cwd", str(tmp_path), "paper-build"], catch_exceptions=False)

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["bibliography_source"] == ""
    assert mock_build.await_args.kwargs["bib_data"] is None


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

    mock_toolchain = MagicMock()
    mock_toolchain.available = False
    mock_toolchain.compiler_path = None
    mock_toolchain.distribution = None
    mock_toolchain.message = "No LaTeX compiler found."

    with (
        patch("gpd.cli.shutil.which", return_value=None),
        patch("gpd.mcp.paper.compiler.detect_latex_toolchain", return_value=mock_toolchain),
        patch("gpd.mcp.paper.compiler.build_paper", new=AsyncMock(return_value=result_payload)),
    ):
        result = runner.invoke(app, ["--raw", "--cwd", str(tmp_path), "paper-build"], catch_exceptions=False)

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["success"] is False
    assert payload["errors"] == ["Compiler 'pdflatex' not found."]
    assert payload["toolchain"]["compiler_available"] is False
    assert payload["toolchain"]["paper_build_ready"] is False
    assert payload["toolchain"]["arxiv_submission_ready"] is False
    assert payload["toolchain"]["warnings"] == ["No LaTeX compiler found."]
    assert any("temporary directory" in warning for warning in payload["warnings"])
    assert any(warning == "No LaTeX compiler found." for warning in payload["warnings"])


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
