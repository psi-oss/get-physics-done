"""Tests for gpd.core.health — health check dashboard."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

import gpd.core.health as health_module
from gpd.core.constants import ProjectLayout
from gpd.core.contract_validation import validate_project_contract
from gpd.core.errors import ValidationError
from gpd.core.health import (
    CheckStatus,
    DoctorReport,
    HealthCheck,
    HealthReport,
    HealthSummary,
    _doctor_check_latex_toolchain,
    _doctor_check_workflow_presets,
    build_unattended_readiness_result,
    check_checkpoint_tags,
    check_compaction_needed,
    check_config,
    check_convention_lock,
    check_environment,
    check_git_status,
    check_latest_return,
    check_orphans,
    check_plan_frontmatter,
    check_project_structure,
    check_roadmap_consistency,
    check_state_validity,
    check_storage_paths,
    extract_doctor_advisories,
    extract_doctor_blockers,
    resolve_doctor_runtime_readiness,
    run_doctor,
    run_health,
    runtime_doctor_hint,
)
from gpd.core.state import default_state_dict, generate_state_markdown, save_state_json
from gpd.core.storage_paths import ProjectStorageLayout
from gpd.hooks.install_metadata import InstallTargetAssessment
from tests.latex_test_support import toolchain_capability as _toolchain_capability
from tests.runtime_test_support import (
    FOREIGN_RUNTIME,
    PRIMARY_RUNTIME,
    runtime_config_dir_name,
    runtime_launch_executable,
    runtime_primary_config_filename,
    runtime_prompt_free_mode_value,
    runtime_target_dir,
)

_PRIMARY_CONFIG_DIR = runtime_config_dir_name(PRIMARY_RUNTIME)
_PRIMARY_PROMPT_FREE_MODE = runtime_prompt_free_mode_value(PRIMARY_RUNTIME)
_PRIMARY_TARGET_DIR = runtime_target_dir(Path("/tmp/project"), PRIMARY_RUNTIME)
_PRIMARY_LAUNCHER_PATH = f"/usr/bin/{runtime_launch_executable(PRIMARY_RUNTIME)}"
_PRIMARY_RELAUNCH_STEP = f"Exit and relaunch {PRIMARY_RUNTIME} before treating unattended use as ready."

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "stage0"


def _latex_toolchain_check(**overrides: object) -> HealthCheck:
    capability = _toolchain_capability(**overrides).model_dump(mode="python")
    status = CheckStatus.OK if capability["full_toolchain_available"] else CheckStatus.WARN
    return HealthCheck(
        status=status,
        label="LaTeX Toolchain",
        details=capability,
        warnings=list(capability.get("warnings", [])),
    )


def _draft_invalid_project_contract() -> dict[str, object]:
    contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
    contract["claims"][0]["references"] = ["missing-ref"]
    return contract


def _expected_permissions_capability_fallback_payload(*, contract_source: str, contract_error: str | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "contract_source": contract_source,
        "permissions_surface": "adapter-defined",
        "permission_surface_kind": "unknown",
        "prompt_free_mode_value": None,
        "supports_runtime_permission_sync": False,
        "supports_prompt_free_mode": False,
        "prompt_free_requires_relaunch": False,
        "statusline_surface": "unknown",
        "statusline_config_surface": "unknown",
        "notify_surface": "unknown",
        "notify_config_surface": "unknown",
        "telemetry_source": "unknown",
        "telemetry_completeness": "unknown",
        "supports_usage_tokens": False,
        "supports_cost_usd": False,
        "supports_context_meter": False,
    }
    if contract_error is not None:
        payload["contract_error"] = contract_error
    return payload


def test_doctor_active_runtime_settings_command_falls_back_to_runtime_neutral_reference(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "gpd.hooks.runtime_detect.detect_runtime_for_gpd_use",
        lambda cwd=None: (_ for _ in ()).throw(RuntimeError("no runtime")),
    )

    assert health_module._doctor_active_runtime_settings_command(cwd=Path("/tmp")) == (
        "the active runtime's `settings` command"
    )


def test_runtime_doctor_hint_uses_public_surface_contract_templates(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        health_module,
        "local_cli_doctor_local_command",
        lambda: "gpd doctor dynamic --runtime <runtime> --local",
    )
    monkeypatch.setattr(
        health_module,
        "local_cli_doctor_global_command",
        lambda: "gpd doctor dynamic --runtime <runtime> --global",
    )

    assert runtime_doctor_hint(PRIMARY_RUNTIME, install_scope="local", target_dir=Path("/tmp/doctor-target")) == (
        f"gpd doctor dynamic --runtime {PRIMARY_RUNTIME} --local --target-dir /tmp/doctor-target"
    )
    assert runtime_doctor_hint(PRIMARY_RUNTIME, install_scope="global", target_dir=None) == (
        f"gpd doctor dynamic --runtime {PRIMARY_RUNTIME} --global"
    )


def test_build_unattended_readiness_result_uses_public_surface_contract_permissions_sync_template(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        health_module,
        "local_cli_permissions_sync_command",
        lambda: "gpd permissions dynamic --runtime <runtime> --autonomy balanced",
    )
    monkeypatch.setattr(
        health_module,
        "_doctor_active_runtime_settings_command",
        lambda cwd=None: "$gpd-settings",
    )

    result = build_unattended_readiness_result(
        runtime=PRIMARY_RUNTIME,
        autonomy="yolo",
        install_scope="local",
        target_dir=None,
        doctor_report=DoctorReport(
            overall=CheckStatus.OK,
            runtime=PRIMARY_RUNTIME,
            install_scope="local",
            summary=HealthSummary(ok=1, warn=0, fail=0, total=1),
            checks=[],
        ),
        permissions_payload={
            "runtime": PRIMARY_RUNTIME,
            "autonomy": "yolo",
            "config_aligned": False,
            "status_scope": "config-only",
            "current_session_verified": False,
            "capabilities": {
                "permissions_surface": "direct-sync",
            },
        },
        live_executable_probes=False,
    )

    assert result.next_step == (
        f"Use `$gpd-settings` inside the runtime for guided changes, or run "
        f"`gpd permissions dynamic --runtime {PRIMARY_RUNTIME} --autonomy yolo` from your normal system terminal."
    )


def test_permissions_capability_payload_surfaces_unexpected_catalog_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _boom(runtime: str) -> object:
        raise RuntimeError("catalog exploded")

    monkeypatch.setattr("gpd.adapters.runtime_catalog.get_runtime_capabilities", _boom)

    payload = health_module._permissions_capability_payload(PRIMARY_RUNTIME)

    assert payload == _expected_permissions_capability_fallback_payload(
        contract_source="runtime-catalog-error",
        contract_error="RuntimeError: catalog exploded",
    )


def test_permissions_capability_payload_keeps_generic_fallback_for_unknown_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _missing(runtime: str) -> object:
        raise KeyError(runtime)

    monkeypatch.setattr("gpd.adapters.runtime_catalog.get_runtime_capabilities", _missing)

    payload = health_module._permissions_capability_payload(PRIMARY_RUNTIME)

    assert payload == _expected_permissions_capability_fallback_payload(contract_source="generic-fallback")

# ─── Model Tests ─────────────────────────────────────────────────────────────


class TestCheckStatus:
    def test_values(self):
        assert CheckStatus.OK == "ok"
        assert CheckStatus.WARN == "warn"
        assert CheckStatus.FAIL == "fail"


class TestHealthModels:
    def test_health_check_defaults(self):
        hc = HealthCheck(status=CheckStatus.OK, label="Test")
        assert hc.details == {}
        assert hc.issues == []
        assert hc.warnings == []

    def test_health_summary_defaults(self):
        hs = HealthSummary()
        assert hs.ok == 0
        assert hs.total == 0

    def test_health_report_roundtrip(self):
        report = HealthReport(
            overall=CheckStatus.OK,
            summary=HealthSummary(ok=3, warn=0, fail=0, total=3),
            checks=[HealthCheck(status=CheckStatus.OK, label="A")],
            fixes_applied=["fixed X"],
        )
        data = report.model_dump()
        restored = HealthReport.model_validate(data)
        assert restored.overall == CheckStatus.OK
        assert restored.fixes_applied == ["fixed X"]
        assert len(restored.checks) == 1

    def test_doctor_report_roundtrip_preserves_live_executable_probe_flag(self):
        report = DoctorReport(
            overall=CheckStatus.OK,
            version="0.1.0",
            summary=HealthSummary(ok=1, warn=0, fail=0, total=1),
            live_executable_probes=True,
            checks=[HealthCheck(status=CheckStatus.OK, label="A")],
        )

        restored = DoctorReport.model_validate(report.model_dump())

        assert restored.live_executable_probes is True

    def test_extract_doctor_blockers_returns_only_failures(self):
        report = DoctorReport(
            overall=CheckStatus.FAIL,
            version="0.1.0",
            summary=HealthSummary(ok=1, warn=1, fail=2, total=4),
            checks=[
                HealthCheck(status=CheckStatus.OK, label="ok"),
                HealthCheck(status=CheckStatus.WARN, label="warn"),
                HealthCheck(status=CheckStatus.FAIL, label="fail-a"),
                HealthCheck(status=CheckStatus.FAIL, label="fail-b"),
            ],
        )

        blockers = extract_doctor_blockers(report)

        assert [check.label for check in blockers] == ["fail-a", "fail-b"]

    def test_extract_doctor_advisories_deduplicates_non_blocking_messages(self):
        report = DoctorReport(
            overall=CheckStatus.WARN,
            version="0.1.0",
            summary=HealthSummary(ok=1, warn=2, fail=0, total=3),
            checks=[
                HealthCheck(status=CheckStatus.OK, label="ok", warnings=["shared warning"]),
                HealthCheck(status=CheckStatus.WARN, label="warn", warnings=["shared warning", "extra warning"]),
                HealthCheck(status=CheckStatus.WARN, label="warn-2", issues=["non-blocking issue"]),
            ],
        )

        advisories = extract_doctor_advisories(report)

        assert advisories == ["shared warning", "extra warning", "non-blocking issue"]

    def test_build_unattended_readiness_result_composes_ready_permissions_with_doctor_advisories(self):
        report = DoctorReport(
            overall=CheckStatus.WARN,
            version="0.1.0",
            summary=HealthSummary(ok=1, warn=1, fail=0, total=2),
            checks=[
                HealthCheck(status=CheckStatus.OK, label="Runtime Launcher"),
                HealthCheck(status=CheckStatus.WARN, label="LaTeX Toolchain", warnings=["LaTeX toolchain is partial."]),
            ],
        )

        result = build_unattended_readiness_result(
            runtime=PRIMARY_RUNTIME,
            autonomy=None,
            install_scope="local",
            target_dir=_PRIMARY_TARGET_DIR,
            doctor_report=report,
            permissions_payload={
                "autonomy": "balanced",
                "target": str(_PRIMARY_TARGET_DIR),
                "readiness": "ready",
                "ready": True,
                "readiness_message": "Runtime permissions are ready for unattended use.",
                "next_step": "",
                "status_scope": "config-only",
                "current_session_verified": False,
            },
            live_executable_probes=False,
            validated_surface="public_runtime_command_surface",
        )

        assert result.runtime == PRIMARY_RUNTIME
        assert result.autonomy == "balanced"
        assert result.install_scope == "local"
        assert result.target == str(_PRIMARY_TARGET_DIR)
        assert result.readiness == "ready"
        assert result.ready is True
        assert result.passed is True
        assert result.live_executable_probes is False
        assert result.status_scope == "config-only"
        assert result.current_session_verified is False
        assert result.validated_surface == "public_runtime_command_surface"
        assert result.blocking_conditions == []
        assert result.warnings == ["LaTeX toolchain is partial."]
        assert result.next_step == ""
        assert [check.__dict__ for check in result.checks] == [
            {
                "name": "permissions",
                "passed": True,
                "blocking": False,
                "detail": "Runtime permissions are ready for unattended use.",
            },
            {
                "name": "doctor",
                "passed": True,
                "blocking": False,
                "detail": "Runtime readiness checks passed with 1 advisory(s).",
            },
        ]

    def test_build_unattended_readiness_result_prefers_permissions_next_step_when_present(self):
        report = DoctorReport(
            overall=CheckStatus.OK,
            version="0.1.0",
            summary=HealthSummary(ok=2, warn=0, fail=0, total=2),
            checks=[
                HealthCheck(status=CheckStatus.OK, label="Runtime Launcher"),
                HealthCheck(status=CheckStatus.OK, label="Runtime Config Target"),
            ],
        )

        result = build_unattended_readiness_result(
            runtime=PRIMARY_RUNTIME,
            autonomy="balanced",
            install_scope="local",
            target_dir=_PRIMARY_TARGET_DIR,
            doctor_report=report,
            permissions_payload={
                "autonomy": "balanced",
                "target": str(_PRIMARY_TARGET_DIR),
                "readiness": "relaunch-required",
                "ready": False,
                "readiness_message": "Runtime permissions are aligned, but the runtime must be relaunched before unattended use.",
                "next_step": _PRIMARY_RELAUNCH_STEP,
                "status_scope": "next-launch",
                "current_session_verified": False,
            },
            live_executable_probes=False,
            validated_surface="public_runtime_command_surface",
        )

        assert result.readiness == "relaunch-required"
        assert result.ready is False
        assert result.passed is False
        assert result.next_step == _PRIMARY_RELAUNCH_STEP
        assert result.status_scope == "next-launch"
        assert result.current_session_verified is False
        assert result.validated_surface == "public_runtime_command_surface"
        assert result.blocking_conditions == [
            "Runtime permissions are aligned, but the runtime must be relaunched before unattended use."
        ]
        assert result.warnings == []
        assert [check.__dict__ for check in result.checks] == [
            {
                "name": "permissions",
                "passed": False,
                "blocking": True,
                "detail": "Runtime permissions are aligned, but the runtime must be relaunched before unattended use.",
            },
            {
                "name": "doctor",
                "passed": True,
                "blocking": False,
                "detail": "Runtime readiness checks passed.",
            },
        ]

    def test_build_unattended_readiness_result_marks_prompt_free_permissions_as_more_permissive(
        self,
    ):
        report = DoctorReport(
            overall=CheckStatus.OK,
            version="0.1.0",
            summary=HealthSummary(ok=2, warn=0, fail=0, total=2),
            checks=[
                HealthCheck(status=CheckStatus.OK, label="Runtime Launcher"),
                HealthCheck(status=CheckStatus.OK, label="Runtime Config Target"),
            ],
        )

        result = build_unattended_readiness_result(
            runtime=PRIMARY_RUNTIME,
            autonomy="balanced",
            install_scope="local",
            target_dir=_PRIMARY_TARGET_DIR,
            doctor_report=report,
            permissions_payload={
                "runtime": PRIMARY_RUNTIME,
                "autonomy": "balanced",
                "target": str(_PRIMARY_TARGET_DIR),
                "desired_mode": "default",
                "configured_mode": _PRIMARY_PROMPT_FREE_MODE,
                "config_aligned": True,
                "requires_relaunch": False,
            },
            live_executable_probes=False,
            validated_surface="public_runtime_command_surface",
        )

        assert result.readiness == "not-ready"
        assert result.ready is False
        assert result.passed is False
        assert result.blocking_conditions == [
            "Runtime permissions are more permissive than the requested autonomy, so unattended readiness is not confirmed."
        ]

    def test_build_unattended_readiness_result_falls_back_to_doctor_hint_for_blockers(self):
        report = DoctorReport(
            overall=CheckStatus.FAIL,
            version="0.1.0",
            summary=HealthSummary(ok=1, warn=0, fail=1, total=2),
            checks=[
                HealthCheck(status=CheckStatus.OK, label="Runtime Launcher"),
                HealthCheck(
                    status=CheckStatus.FAIL,
                    label="Runtime Config Target",
                    issues=["Runtime config target not writable"],
                ),
            ],
        )

        result = build_unattended_readiness_result(
            runtime=PRIMARY_RUNTIME,
            autonomy="balanced",
            install_scope="local",
            target_dir=_PRIMARY_TARGET_DIR,
            doctor_report=report,
            permissions_payload={
                "autonomy": "balanced",
                "target": str(_PRIMARY_TARGET_DIR),
                "readiness": "ready",
                "ready": True,
                "readiness_message": "Runtime permissions are ready for unattended use.",
                "status_scope": "config-only",
                "current_session_verified": False,
            },
            live_executable_probes=True,
            validated_surface="public_runtime_command_surface",
        )

        assert result.passed is False
        assert result.ready is True
        assert result.readiness == "ready"
        assert result.status_scope == "config-only"
        assert result.current_session_verified is False
        assert result.validated_surface == "public_runtime_command_surface"
        assert result.next_step == (
            f"Run `{runtime_doctor_hint(PRIMARY_RUNTIME, install_scope='local', target_dir=_PRIMARY_TARGET_DIR)}` "
            "to inspect and clear the blocking runtime-readiness issues."
        )
        assert result.blocking_conditions == ["Runtime config target not writable"]
        assert result.warnings == []
        assert [check.__dict__ for check in result.checks] == [
            {
                "name": "permissions",
                "passed": True,
                "blocking": False,
                "detail": "Runtime permissions are ready for unattended use.",
            },
            {
                "name": "doctor",
                "passed": False,
                "blocking": True,
                "detail": "Runtime config target not writable",
            },
        ]


# ─── Individual Check Tests ──────────────────────────────────────────────────


class TestCheckEnvironment:
    def test_ok_on_current_python(self):
        result = check_environment()
        assert result.label == "Environment"
        assert result.status == CheckStatus.OK
        assert "python_version" in result.details


class TestDoctorCheckLatexToolchain:
    def test_full_toolchain_reports_ok(self, monkeypatch):
        monkeypatch.setattr(
            "gpd.mcp.paper.compiler.detect_latex_toolchain",
            lambda: _toolchain_capability(),
        )

        result = _doctor_check_latex_toolchain()

        assert result.status == CheckStatus.OK
        assert result.details["available"] is True
        assert result.details["compiler_available"] is True
        assert result.details["full_toolchain_available"] is True
        assert result.details["latexmk_available"] is True
        assert result.details["bibtex_available"] is True
        assert result.details["kpsewhich_available"] is True
        assert result.details["paper_build_ready"] is True
        assert result.details["arxiv_submission_ready"] is True
        assert result.details["missing_components"] == []
        assert result.warnings == []

    def test_partial_toolchain_reports_warn(self, monkeypatch):
        monkeypatch.setattr(
            "gpd.mcp.paper.compiler.detect_latex_toolchain",
            lambda: _toolchain_capability(
                latexmk_available=False,
                kpsewhich_available=False,
                warnings=[
                    "latexmk not found; multi-pass compilation will fall back to manual passes.",
                    "kpsewhich not found; TeX resource checks will assume installed resources.",
                ],
            ),
        )

        result = _doctor_check_latex_toolchain()

        assert result.status == CheckStatus.WARN
        assert result.details["available"] is True
        assert result.details["compiler_available"] is True
        assert result.details["full_toolchain_available"] is False
        assert result.details["latexmk_available"] is False
        assert result.details["bibtex_available"] is True
        assert result.details["kpsewhich_available"] is False
        assert result.details["paper_build_ready"] is True
        assert result.details["arxiv_submission_ready"] is False
        assert result.details["missing_components"] == ["latexmk", "kpsewhich"]
        assert any("partial" in warning for warning in result.warnings)

    def test_missing_compiler_reports_warn(self, monkeypatch):
        monkeypatch.setattr(
            "gpd.mcp.paper.compiler.detect_latex_toolchain",
            lambda: _toolchain_capability(
                compiler_available=False,
                compiler_path=None,
                distribution=None,
                bibtex_available=False,
                latexmk_available=False,
                kpsewhich_available=False,
                readiness_state="blocked",
                message="No LaTeX compiler found.\nInstall a LaTeX distribution.",
                warnings=["Install a LaTeX distribution to enable paper compilation."],
            ),
        )

        result = _doctor_check_latex_toolchain()

        assert result.status == CheckStatus.WARN
        assert result.details["available"] is False
        assert result.details["compiler_available"] is False
        assert result.details["full_toolchain_available"] is False
        assert result.details["paper_build_ready"] is False
        assert result.details["arxiv_submission_ready"] is False
        assert result.details["missing_components"] == ["pdflatex"]
        assert result.details["readiness_state"] == "blocked"
        assert result.details["message"] == "No LaTeX compiler found.\nInstall a LaTeX distribution."
        assert result.warnings == ["Install a LaTeX distribution to enable paper compilation."]

    def test_import_failure_keeps_latex_capability_shape_stable(self, monkeypatch):
        import builtins

        original_import = builtins.__import__

        def _failing_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "gpd.mcp.paper.compiler":
                raise ImportError("boom")
            return original_import(name, globals, locals, fromlist, level)

        monkeypatch.setattr(builtins, "__import__", _failing_import)

        result = _doctor_check_latex_toolchain()

        assert result.status == CheckStatus.WARN
        assert result.details["available"] is False
        assert result.details["compiler_available"] is False
        assert result.details["full_toolchain_available"] is False
        assert result.details["paper_build_ready"] is False
        assert result.details["arxiv_submission_ready"] is False
        assert result.details["compiler"] == "pdflatex"
        assert result.details["latexmk_available"] is None
        assert result.details["bibtex_available"] is None
        assert result.details["kpsewhich_available"] is None
        assert result.details["readiness_state"] == "blocked"
        assert result.details["message"] == "Could not load LaTeX detection helpers."
        assert any("Could not load LaTeX detection helpers" in warning for warning in result.details["warnings"])
        assert any("Could not load LaTeX detection helpers" in warning for warning in result.warnings)

    def test_workflow_presets_do_not_backfill_publication_readiness_from_minimal_legacy_latex_payload(self) -> None:
        result = _doctor_check_workflow_presets(
            latex_check=HealthCheck(
                status=CheckStatus.OK,
                label="LaTeX Toolchain",
                details={"available": True},
                warnings=[],
            ),
            base_ready=True,
        )

        checks = {preset["id"]: preset for preset in result.details["presets"]}
        publication = checks["publication-manuscript"]

        assert publication["status"] == "degraded"
        assert publication["summary"] == (
            "degraded without bibliography tooling: draft/review remain usable, while paper-build and "
            "arxiv-submission may fail for manuscripts that require bibliography processing"
        )
        assert publication["ready_workflows"] == ["write-paper", "peer-review"]
        assert publication["blocked_workflows"] == []
        assert publication["degraded_workflows"] == ["paper-build", "arxiv-submission"]
        assert result.details["latex_capability"]["full_toolchain_available"] is False


class TestCheckProjectStructure:
    def test_missing_planning_dir(self, tmp_path: Path):
        result = check_project_structure(tmp_path)
        assert result.status == CheckStatus.FAIL
        assert len(result.issues) > 0

    def test_ok_with_full_structure(self, tmp_path: Path):
        from gpd.core.constants import REQUIRED_PLANNING_DIRS, REQUIRED_PLANNING_FILES

        planning = tmp_path / "GPD"
        planning.mkdir()
        for f in REQUIRED_PLANNING_FILES:
            (planning / f).write_text("stub")
        for d in REQUIRED_PLANNING_DIRS:
            (planning / d).mkdir(parents=True, exist_ok=True)
        result = check_project_structure(tmp_path)
        assert result.status == CheckStatus.OK


class TestCheckStoragePaths:
    def test_clean_project_is_ok(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(ProjectStorageLayout, "project_root_is_temporary", lambda self: False)
        result = check_storage_paths(_bootstrap_health_project(tmp_path))

        assert result.status == CheckStatus.OK
        assert result.details["warning_count"] == 0

    def test_temp_root_project_warns_even_without_hidden_artifacts(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        temp_root = tmp_path / "runtime-temp"
        temp_root.mkdir()
        monkeypatch.setattr(ProjectStorageLayout, "temp_roots", lambda self: (temp_root.resolve(strict=False),))
        temp_project = temp_root / "project"
        temp_project.mkdir()

        result = check_storage_paths(_bootstrap_health_project(temp_project))

        assert result.status == CheckStatus.WARN
        assert result.details["temporary_project_root"] is True
        assert any("Project root is under a temporary directory" in warning for warning in result.warnings)

    def test_hidden_results_and_scratch_outputs_warn(self, tmp_path: Path) -> None:
        cwd = _bootstrap_health_project(tmp_path)
        hidden_results = cwd / "GPD" / "phases" / "01-setup" / "results"
        hidden_results.mkdir(parents=True)
        (hidden_results / "out.json").write_text("{}", encoding="utf-8")
        scratch_file = cwd / "GPD" / "tmp" / "final.csv"
        scratch_file.parent.mkdir(parents=True)
        scratch_file.write_text("x,y\n", encoding="utf-8")

        result = check_storage_paths(cwd)

        assert result.status == CheckStatus.WARN
        assert any("GPD/phases/01-setup/results/out.json" in warning for warning in result.warnings)
        assert any("GPD/tmp/final.csv" in warning for warning in result.warnings)

    def test_repo_gitignore_does_not_hide_checkpoint_outputs_under_gpd(self, tmp_path: Path) -> None:
        repo = _init_git_repo(tmp_path)

        result = subprocess.run(
            [
                "git",
                "check-ignore",
                "-v",
                "--",
                "GPD/CHECKPOINTS.md",
                "GPD/phase-checkpoints/01-test-phase.md",
            ],
            cwd=repo,
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.stderr == ""
        if result.returncode == 1:
            assert result.stdout == ""
            return

        assert result.returncode == 0
        lines = [line for line in result.stdout.splitlines() if line.strip()]
        assert lines == [
            ".gitignore:23:!GPD/CHECKPOINTS.md\tGPD/CHECKPOINTS.md",
            ".gitignore:25:!GPD/phase-checkpoints/*.md\tGPD/phase-checkpoints/01-test-phase.md",
        ]

    def test_repo_gitignore_does_not_hide_gpd_state_surfaces(self, tmp_path: Path) -> None:
        """Regression: GPD/ files must NOT be gitignored.

        Workflow commit commands include these files; gitignoring them causes
        ``git add`` failures (exit code 1) at commit time.  A pre-commit hook
        strips GPD/ from commits to the codebase repo instead.
        """
        repo = _init_git_repo(tmp_path)

        gpd_paths = [
            "GPD/STATE.md",
            "GPD/state.json",
            "GPD/state.json.bak",
            "GPD/PROJECT.md",
            "GPD/ROADMAP.md",
            "GPD/REQUIREMENTS.md",
            "GPD/config.json",
            "GPD/CONVENTIONS.md",
        ]
        result = subprocess.run(
            ["git", "check-ignore", "--", *gpd_paths],
            cwd=repo,
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 1, (
            f"GPD files should not be gitignored but git check-ignore matched: "
            f"{result.stdout.strip()}"
        )

    def test_git_status_reports_dirty_tracked_checkpoint_artifacts(self, tmp_path: Path) -> None:
        repo = _init_git_repo(tmp_path)
        checkpoint_dir = repo / "GPD" / "phase-checkpoints"
        checkpoint_dir.mkdir(parents=True)
        root_index = repo / "GPD" / "CHECKPOINTS.md"
        phase_checkpoint = checkpoint_dir / "01-test-phase.md"
        root_index.write_text("initial index\n", encoding="utf-8")
        phase_checkpoint.write_text("initial phase checkpoint\n", encoding="utf-8")

        subprocess.run(["git", "add", "-f", "GPD/CHECKPOINTS.md", "GPD/phase-checkpoints/01-test-phase.md"], cwd=repo, check=True, capture_output=True, text=True)

        root_index.write_text("dirty index\n", encoding="utf-8")
        phase_checkpoint.write_text("dirty phase checkpoint\n", encoding="utf-8")

        result = check_git_status(repo)

        assert result.label == "Git Status"
        assert result.status == CheckStatus.OK
        assert result.details["repo_detected"] is True
        assert result.details["uncommitted_files"] == 2


class TestCheckCompaction:
    def test_no_state_file(self, tmp_path: Path):
        result = check_compaction_needed(tmp_path)
        assert result.status == CheckStatus.OK
        assert result.details.get("reason") == "no_state_file"

    def test_small_state_ok(self, tmp_path: Path):
        planning = tmp_path / "GPD"
        planning.mkdir()
        (planning / "STATE.md").write_text("# State\nShort content\n")
        result = check_compaction_needed(tmp_path)
        assert result.status == CheckStatus.OK


class TestCheckOrphans:
    def test_no_phases_dir(self, tmp_path: Path):
        result = check_orphans(tmp_path)
        assert result.status == CheckStatus.OK

    def test_empty_phase_dir_warns(self, tmp_path: Path):
        phases = tmp_path / "GPD" / "phases"
        (phases / "01-intro").mkdir(parents=True)
        result = check_orphans(tmp_path)
        assert result.status == CheckStatus.WARN
        assert any("Empty phase" in w for w in result.warnings)


class TestCheckConventionLock:
    def test_no_state_json(self, tmp_path: Path):
        result = check_convention_lock(tmp_path)
        assert result.status == CheckStatus.WARN
        assert any("state.json" in w for w in result.warnings)

    def test_no_convention_lock_key(self, tmp_path: Path):
        planning = tmp_path / "GPD"
        planning.mkdir()
        (planning / "state.json").write_text(json.dumps({"position": {}}))
        result = check_convention_lock(tmp_path)
        assert result.status == CheckStatus.WARN

    def test_convention_lock_non_dict_warns(self, tmp_path: Path):
        """A truthy non-dict convention_lock must not raise AttributeError."""
        fake_state = {"convention_lock": "not-a-dict"}
        with patch("gpd.core.health._peek_normalized_state_for_health", return_value=(fake_state, "state.json")):
            result = check_convention_lock(tmp_path)
        assert result.status == CheckStatus.WARN
        assert any("not a dict" in w for w in result.warnings)

    def test_empty_dict_falls_through_to_counting_loop(self, tmp_path: Path):
        """An empty dict {} is a valid convention_lock; should report counts, not 'No convention_lock'."""
        fake_state = {"convention_lock": {}}
        with patch("gpd.core.health._peek_normalized_state_for_health", return_value=(fake_state, "state.json")):
            result = check_convention_lock(tmp_path)
        assert "No convention_lock in state.json" not in result.warnings
        assert "set" in result.details
        assert "total" in result.details
        assert result.details["set"] == 0


class TestCheckConfig:
    def test_missing_config(self, tmp_path: Path):
        result = check_config(tmp_path)
        assert result.status == CheckStatus.WARN
        assert any("not found" in w for w in result.warnings)


class TestCheckGitStatus:
    def test_non_git_dir(self, tmp_path: Path):
        completed = subprocess.CompletedProcess(
            args=["git", "status", "--porcelain", "GPD/"],
            returncode=128,
            stdout="",
            stderr="fatal: not a git repository (or any of the parent directories): .git",
        )
        with patch("gpd.core.health.subprocess.run", return_value=completed):
            result = check_git_status(tmp_path)

        assert result.label == "Git Status"
        assert result.status == CheckStatus.WARN
        assert result.details["repo_detected"] is False
        assert any("not a git repository" in warning for warning in result.warnings)


class TestCheckCheckpointTags:
    def test_non_git_dir(self, tmp_path: Path):
        completed = subprocess.CompletedProcess(
            args=["git", "tag", "-l", "gpd-checkpoint/*"],
            returncode=128,
            stdout="",
            stderr="fatal: not a git repository (or any of the parent directories): .git",
        )
        with patch("gpd.core.health.subprocess.run", return_value=completed):
            result = check_checkpoint_tags(tmp_path)

        assert result.label == "Checkpoint Tags"
        assert result.status == CheckStatus.WARN
        assert result.details["repo_detected"] is False
        assert any("not a git repository" in warning for warning in result.warnings)

    def test_warns_on_stale_checkpoint_tags(self, tmp_path: Path):
        def _run(args: list[str], **_: object) -> subprocess.CompletedProcess[str]:
            if args[:3] == ["git", "tag", "-l"]:
                return subprocess.CompletedProcess(args=args, returncode=0, stdout="gpd-checkpoint/old\n", stderr="")
            if args[:4] == ["git", "log", "-1", "--format=%ct"]:
                return subprocess.CompletedProcess(args=args, returncode=0, stdout="0\n", stderr="")
            raise AssertionError(f"Unexpected args: {args}")

        with patch("gpd.core.health.subprocess.run", side_effect=_run):
            result = check_checkpoint_tags(tmp_path)

        assert result.status == CheckStatus.WARN
        assert result.details["stale_tags"] == ["gpd-checkpoint/old"]
        assert any("older than" in warning for warning in result.warnings)


class TestCheckRoadmapConsistency:
    def test_no_roadmap(self, tmp_path: Path):
        result = check_roadmap_consistency(tmp_path)
        assert result.status == CheckStatus.FAIL
        assert any("not found" in i for i in result.issues)

    def test_roadmap_with_matching_phases(self, tmp_path: Path):
        planning = tmp_path / "GPD"
        planning.mkdir()
        (planning / "ROADMAP.md").write_text("## Phase 1: Intro\n## Phase 2: Method\n")
        phases = planning / "phases"
        (phases / "1-intro").mkdir(parents=True)
        (phases / "2-method").mkdir(parents=True)
        result = check_roadmap_consistency(tmp_path)
        assert result.status == CheckStatus.OK


class TestCheckPlanFrontmatter:
    def test_no_phases_dir(self, tmp_path: Path):
        result = check_plan_frontmatter(tmp_path)
        assert result.status == CheckStatus.OK
        assert result.details["plans_checked"] == 0

    def test_detects_plan_numbering_gap(self, tmp_path: Path):
        """Standard plan filenames like 01-PLAN.md must be parsed by the regex."""
        phases = tmp_path / "GPD" / "phases"
        phase_dir = phases / "01-intro"
        phase_dir.mkdir(parents=True)
        # Create plans with a gap: 01, 03 (missing 02)
        plan_content = _canonical_plan_frontmatter()
        (phase_dir / "01-PLAN.md").write_text(plan_content)
        (phase_dir / "03-PLAN.md").write_text(plan_content)
        result = check_plan_frontmatter(tmp_path)
        assert result.status == CheckStatus.WARN
        assert result.details["numbering_gaps"] >= 1
        assert any("Plan numbering gap" in w for w in result.warnings)

    def test_no_gap_with_consecutive_plans(self, tmp_path: Path):
        """Consecutive plan numbers should not produce warnings."""
        phases = tmp_path / "GPD" / "phases"
        phase_dir = phases / "01-intro"
        phase_dir.mkdir(parents=True)
        plan_content = _canonical_plan_frontmatter()
        (phase_dir / "01-PLAN.md").write_text(plan_content)
        (phase_dir / "02-PLAN.md").write_text(plan_content)
        (phase_dir / "03-PLAN.md").write_text(plan_content)
        result = check_plan_frontmatter(tmp_path)
        assert result.details["numbering_gaps"] == 0
        assert not any("Plan numbering gap" in w for w in result.warnings)

    def test_missing_contract_block_fails(self, tmp_path: Path):
        phases = tmp_path / "GPD" / "phases"
        phase_dir = phases / "01-intro"
        phase_dir.mkdir(parents=True)
        plan_content = (
            "---\n"
            "phase: 01-intro\n"
            "plan: 01\n"
            "type: execute\n"
            "wave: 1\n"
            "depends_on: []\n"
            "files_modified: []\n"
            "interactive: false\n"
            "conventions:\n"
            "  units: natural\n"
            "  metric: (+,-,-,-)\n"
            "  coordinates: Cartesian\n"
            "---\n\n"
            "# Plan\n"
        )
        (phase_dir / "01-PLAN.md").write_text(plan_content)

        result = check_plan_frontmatter(tmp_path)

        assert result.status == CheckStatus.FAIL
        assert any("missing required frontmatter fields: contract" in issue for issue in result.issues)

    def test_invalid_contract_schema_fails(self, tmp_path: Path):
        phases = tmp_path / "GPD" / "phases"
        phase_dir = phases / "01-intro"
        phase_dir.mkdir(parents=True)
        plan_content = (
            "---\n"
            "phase: 01-intro\n"
            "plan: 01\n"
            "type: execute\n"
            "wave: 1\n"
            "depends_on: []\n"
            "files_modified: []\n"
            "interactive: false\n"
            "conventions:\n"
            "  units: natural\n"
            "  metric: (+,-,-,-)\n"
            "  coordinates: Cartesian\n"
            "contract: []\n"
            "---\n\n"
            "# Plan\n"
        )
        (phase_dir / "01-PLAN.md").write_text(plan_content)

        result = check_plan_frontmatter(tmp_path)

        assert result.status == CheckStatus.FAIL
        assert any("contract: expected an object" in issue for issue in result.issues)


class TestCheckStateValidityProjectContract:
    def test_promotes_approval_blockers_to_issues(self, tmp_path: Path):
        cwd = _bootstrap_health_project(tmp_path)
        contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
        contract["context_intake"] = {
            "must_read_refs": [],
            "must_include_prior_outputs": [],
            "user_asserted_anchors": [],
            "known_good_baselines": [],
            "context_gaps": [],
            "crucial_inputs": [],
        }
        contract["references"][0]["role"] = "background"
        contract["references"][0]["must_surface"] = False
        contract["references"][0]["applies_to"] = []
        contract["references"][0]["required_actions"] = []

        state = {"project_contract": contract}
        (cwd / "GPD" / "state.json").write_text(json.dumps(state), encoding="utf-8")

        approval_validation = validate_project_contract(contract, mode="approved")
        fake_state_validation = SimpleNamespace(
            issues=[],
            warnings=[f"project_contract: {error}" for error in approval_validation.errors],
        )

        with patch("gpd.core.health.state_validate", return_value=fake_state_validation):
            result = check_state_validity(cwd)

        assert result.status == CheckStatus.FAIL
        assert approval_validation.errors
        assert any(issue.startswith("project_contract: ") for issue in result.issues)
        assert not any(warning in result.warnings for warning in fake_state_validation.warnings)

    def test_accepts_project_local_prior_artifact_grounding(self, tmp_path: Path) -> None:
        cwd = _bootstrap_health_project(tmp_path)
        contract = json.loads((FIXTURES_DIR / "project_contract.json").read_text(encoding="utf-8"))
        artifact = cwd / "artifacts" / "benchmark" / "report.json"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text('{"status": "ok"}\n', encoding="utf-8")

        contract["references"][0]["kind"] = "prior_artifact"
        contract["references"][0]["locator"] = "artifacts/benchmark/report.json"
        contract["references"][0]["role"] = "benchmark"
        contract["references"][0]["must_surface"] = True
        contract["references"][0]["applies_to"] = ["claim-benchmark"]
        contract["references"][0]["required_actions"] = ["compare"]
        contract["context_intake"] = {
            "must_read_refs": [],
            "must_include_prior_outputs": [],
            "user_asserted_anchors": [],
            "known_good_baselines": [],
            "context_gaps": [],
            "crucial_inputs": [],
        }

        state = default_state_dict()
        state["project_contract"] = contract
        save_state_json(cwd, state)
        (cwd / "GPD" / "STATE.md").write_text(generate_state_markdown(state), encoding="utf-8")

        result = check_state_validity(cwd)

        assert not any(issue.startswith("project_contract: ") for issue in result.issues)
        assert not any(warning.startswith("project_contract: ") for warning in result.warnings)

    def test_draft_invalid_project_contract_is_promoted_during_health_approval_checks(self, tmp_path: Path) -> None:
        cwd = _bootstrap_health_project(tmp_path)
        state = default_state_dict()
        state["project_contract"] = _draft_invalid_project_contract()
        layout = ProjectLayout(cwd)
        layout.state_json.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        layout.state_md.write_text(generate_state_markdown(state), encoding="utf-8")

        result = check_state_validity(cwd)

        assert result.status == CheckStatus.FAIL
        assert any("project_contract: claim claim-benchmark references unknown reference missing-ref" in issue for issue in result.issues)
        assert not any(
            "project_contract: claim claim-benchmark references unknown reference missing-ref" in warning
            for warning in result.warnings
        )
        assert any(
            'schema normalization: dropped "project_contract" because contract failed draft scoping validation'
            in warning
            for warning in result.warnings
        )


class TestCheckStateValidity:
    def test_no_state_files(self, tmp_path: Path):
        result = check_state_validity(tmp_path)
        assert result.label == "State Validity"
        assert result.status == CheckStatus.FAIL
        assert result.issues

    def test_does_not_repair_state_json_while_inspecting(self, tmp_path: Path) -> None:
        state = default_state_dict()
        state["position"]["status"] = "Executing"
        save_state_json(tmp_path, state)
        layout = ProjectLayout(tmp_path)

        corrupt_state = "{bad json\n"
        backup_before = layout.state_json_backup.read_text(encoding="utf-8")
        layout.state_json.write_text(corrupt_state, encoding="utf-8")

        result = check_state_validity(tmp_path)

        assert result.status == CheckStatus.WARN
        assert layout.state_json.read_text(encoding="utf-8") == corrupt_state
        assert layout.state_json_backup.read_text(encoding="utf-8") == backup_before


# ─── run_health Integration ──────────────────────────────────────────────────


class TestRunHealth:
    def test_read_only_health_does_not_recover_intent_marker_and_keeps_state_unchanged(
        self, tmp_path: Path
    ) -> None:
        cwd = _bootstrap_health_project(tmp_path)
        layout = ProjectLayout(cwd)

        stale_state = default_state_dict()
        stale_state["position"]["current_phase"] = "01"
        recovered_state = default_state_dict()
        recovered_state["position"]["current_phase"] = "05"
        recovered_state["position"]["status"] = "Executing"
        _write_intent_recovery_state(cwd, stale_state=stale_state, recovered_state=recovered_state)

        before_state = layout.state_json.read_text(encoding="utf-8")
        before_md = layout.state_md.read_text(encoding="utf-8")

        report = run_health(cwd, fix=False)
        state_check = next(check for check in report.checks if check.label == "State Validity")

        assert layout.state_json.read_text(encoding="utf-8") == before_state
        assert layout.state_md.read_text(encoding="utf-8") == before_md
        assert layout.state_intent.exists()
        assert json.loads(layout.state_json.read_text(encoding="utf-8"))["position"]["current_phase"] == "01"
        assert state_check.details["state_source"] == "state.json"

    def test_fix_mode_regenerates_state_from_state_md_and_refreshes_report_details(self, tmp_path: Path) -> None:
        cwd = _bootstrap_health_project(tmp_path)
        layout = ProjectLayout(cwd)

        state = default_state_dict()
        state["position"]["status"] = "Executing"
        state["position"]["current_phase"] = "12"
        markdown = generate_state_markdown(state)
        layout.state_md.write_text(markdown, encoding="utf-8")

        layout.state_json.write_text("", encoding="utf-8")
        if layout.state_json_backup.exists():
            layout.state_json_backup.unlink()

        report = run_health(cwd, fix=True)
        state_check = next(check for check in report.checks if check.label == "State Validity")

        assert layout.state_json.exists()
        assert state_check.details["state_source"] == "state.json"
        assert report.fixes_applied == ["Regenerated state.json from STATE.md"]

    def test_state_validity_phase_format_warning_uses_recovered_backup_state(self, tmp_path: Path) -> None:
        cwd = _bootstrap_health_project(tmp_path)
        layout = ProjectLayout(cwd)

        backup_state = default_state_dict()
        backup_state["position"]["current_phase"] = "5"
        save_state_json(cwd, backup_state)
        layout.state_json.write_text("{bad json\n", encoding="utf-8")

        result = check_state_validity(cwd)

        assert any('phase ID format: "5" -- expected zero-padded' in warning for warning in result.warnings)

    def test_fix_mode_removes_stale_checkpoint_tags(self, tmp_path: Path):
        def _run(args: list[str], **_: object) -> subprocess.CompletedProcess[str]:
            if args == ["git", "--version"]:
                return subprocess.CompletedProcess(args=args, returncode=0, stdout="git version 2.45.0\n", stderr="")
            if args[:3] == ["git", "status", "--porcelain"]:
                return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")
            if args[:3] == ["git", "check-ignore", "--quiet"]:
                return subprocess.CompletedProcess(args=args, returncode=1, stdout="", stderr="")
            if args[:3] == ["git", "tag", "-l"]:
                return subprocess.CompletedProcess(args=args, returncode=0, stdout="gpd-checkpoint/old\n", stderr="")
            if args[:4] == ["git", "log", "-1", "--format=%ct"]:
                return subprocess.CompletedProcess(args=args, returncode=0, stdout="0\n", stderr="")
            if args[:3] == ["git", "tag", "-d"]:
                return subprocess.CompletedProcess(args=args, returncode=0, stdout="Deleted tag\n", stderr="")
            raise AssertionError(f"Unexpected args: {args}")

        with patch("gpd.core.health.subprocess.run", side_effect=_run):
            report = run_health(tmp_path, fix=True)

        assert any("Removed 1 stale checkpoint tag" in fix for fix in report.fixes_applied)
        checkpoint_check = next(check for check in report.checks if check.label == "Checkpoint Tags")
        assert checkpoint_check.status == CheckStatus.OK
        assert checkpoint_check.details["stale_tags"] == []


class TestRunDoctor:
    def _make_specs_dir(self, tmp_path: Path, *, include_templates: bool = True) -> Path:
        specs = tmp_path / "specs"
        (specs / "references" / "shared").mkdir(parents=True, exist_ok=True)
        (specs / "references" / "verification" / "core").mkdir(parents=True, exist_ok=True)
        (specs / "references" / "verification" / "errors").mkdir(parents=True, exist_ok=True)
        (specs / "workflows").mkdir(exist_ok=True)
        if include_templates:
            (specs / "templates").mkdir(exist_ok=True)

        (specs / "references" / "shared" / "shared-protocols.md").write_text("shared\n", encoding="utf-8")
        (specs / "references" / "verification" / "core" / "verification-core.md").write_text(
            "verify\n", encoding="utf-8"
        )
        (specs / "references" / "verification" / "errors" / "llm-physics-errors.md").write_text(
            "errors\n", encoding="utf-8"
        )
        (specs / "workflows" / "plan-phase.md").write_text("plan\n", encoding="utf-8")
        if include_templates:
            (specs / "templates" / "phase-prompt.md").write_text("template\n", encoding="utf-8")

        return specs

    def _run_runtime_doctor(
        self,
        tmp_path: Path,
        *,
        assessment: InstallTargetAssessment,
        target_dir: Path | None = None,
    ) -> tuple[HealthReport, dict[str, HealthCheck]]:
        specs_dir = self._make_specs_dir(tmp_path)
        selected_target = target_dir or runtime_target_dir(tmp_path, PRIMARY_RUNTIME)
        if not selected_target.exists():
            selected_target.mkdir(parents=True, exist_ok=True)

        with (
            patch("gpd.core.health._doctor_active_virtualenv", return_value=True),
            patch("gpd.core.health._doctor_which", return_value=_PRIMARY_LAUNCHER_PATH),
            patch("gpd.core.health.os.access", return_value=True),
            patch(
                "gpd.core.health._doctor_check_bootstrap_network_access",
                return_value=HealthCheck(status=CheckStatus.OK, label="Bootstrap Network Access"),
            ),
            patch(
                "gpd.core.health._doctor_check_provider_auth",
                return_value=HealthCheck(status=CheckStatus.OK, label="Provider/Auth Guidance"),
            ),
            patch(
                "gpd.core.health._doctor_check_latex_toolchain",
                return_value=_latex_toolchain_check(),
            ),
            patch("gpd.core.health.assess_install_target", return_value=assessment),
        ):
            report = run_doctor(
                specs_dir=specs_dir,
                version="0.1.0",
                runtime=PRIMARY_RUNTIME,
                install_scope="local",
                target_dir=selected_target,
                cwd=tmp_path,
            )

        checks = {check.label: check for check in report.checks}
        return report, checks

    def _assessment(
        self,
        *,
        state: str,
        target_dir: Path,
        manifest_state: str = "ok",
        manifest_runtime: str | None = None,
        has_managed_markers: bool = True,
        missing_install_artifacts: tuple[str, ...] = (),
    ) -> InstallTargetAssessment:
        return InstallTargetAssessment(
            config_dir=target_dir.resolve(strict=False),
            expected_runtime=PRIMARY_RUNTIME,
            state=state,
            manifest_state=manifest_state,
            manifest_runtime=manifest_runtime,
            has_managed_markers=has_managed_markers,
            missing_install_artifacts=missing_install_artifacts,
        )

    def test_reports_specs_structure(self, tmp_path: Path):
        report = run_doctor(specs_dir=self._make_specs_dir(tmp_path), version="0.1.0")
        checks = {check.label: check for check in report.checks}

        assert checks["Specs Structure"].status == CheckStatus.OK
        assert checks["Key References"].status == CheckStatus.OK
        assert report.mode == "installation"
        assert report.runtime is None

    def test_missing_required_specs_subdir_fails(self, tmp_path: Path):
        report = run_doctor(specs_dir=self._make_specs_dir(tmp_path, include_templates=False), version="0.1.0")
        checks = {check.label: check for check in report.checks}

        assert checks["Specs Structure"].status == CheckStatus.FAIL

    def test_missing_nested_key_reference_warns(self, tmp_path: Path):
        specs_dir = self._make_specs_dir(tmp_path)
        missing_ref = specs_dir / "references" / "verification" / "errors" / "llm-physics-errors.md"
        missing_ref.unlink()

        report = run_doctor(specs_dir=specs_dir, version="0.1.0")
        checks = {check.label: check for check in report.checks}

        assert checks["Key References"].status == CheckStatus.WARN
        assert any(
            "references/verification/errors/llm-physics-errors.md" in warning
            for warning in checks["Key References"].warnings
        )

    def test_protocol_bundles_check_validates_existing_bundle_assets(self, tmp_path: Path):
        specs_dir = self._make_specs_dir(tmp_path)
        bundles_dir = specs_dir / "bundles"
        bundles_dir.mkdir()
        (bundles_dir / "supporting-bundle.md").write_text(
            """---
bundle_id: supporting-bundle
bundle_version: 1
title: Supporting Bundle
summary: Supporting bundle referenced by the main doctor fixture.
trigger:
  any_terms:
    - supporting bundle
  min_term_matches: 1
  min_score: 3
---

# Supporting Bundle
""",
            encoding="utf-8",
        )
        (bundles_dir / "test-bundle.md").write_text(
            """---
bundle_id: test-bundle
bundle_version: 1
title: Test Bundle
summary: Minimal bundle used by doctor tests.
trigger:
  any_terms:
    - test bundle
  exclusive_with:
    - supporting-bundle
  min_term_matches: 1
  min_score: 3
assets:
  project_types:
    - path: templates/phase-prompt.md
      required: true
verifier_extensions:
  - name: convergence-audit
    rationale: Validate doctor check_id verification.
    check_ids:
      - "5.5"
---

# Test Bundle
""",
            encoding="utf-8",
        )

        report = run_doctor(specs_dir=specs_dir, version="0.1.0")
        checks = {check.label: check for check in report.checks}

        assert checks["Protocol Bundles"].status == CheckStatus.OK
        assert checks["Protocol Bundles"].details["bundle_count"] == 2
        assert checks["Protocol Bundles"].details["bundle_ids"] == ["supporting-bundle", "test-bundle"]

    def test_protocol_bundles_check_rejects_invalid_bundle_inputs(self, tmp_path: Path):
        cases: tuple[tuple[str, str | bytes, str], ...] = (
            (
                "broken-bundle.md",
                """---
bundle_id: broken-bundle
bundle_version: 1
title: Broken Bundle
summary: Bundle with a missing required asset.
trigger:
  any_terms:
    - broken bundle
  min_term_matches: 1
  min_score: 3
assets:
  project_types:
    - path: templates/missing-template.md
      required: true
---

# Broken Bundle
""",
                "templates/missing-template.md",
            ),
            (
                "path-escape-bundle.md",
                """---
bundle_id: path-escape-bundle
bundle_version: 1
title: Path Escape Bundle
summary: Bundle with an invalid asset path.
trigger:
  any_terms:
    - path escape bundle
  min_term_matches: 1
  min_score: 3
assets:
  project_types:
    - path: ../outside.md
      required: true
---

# Path Escape Bundle
""",
                "path must stay within specs dir",
            ),
            ("invalid-encoding.md", b"\xff\xfe\x80", "unreadable bundle"),
            (
                "bad-check-bundle.md",
                """---
bundle_id: bad-check-bundle
bundle_version: 1
title: Bad Check Bundle
summary: Bundle with an invalid verifier check id.
trigger:
  any_terms:
    - bad check bundle
  min_term_matches: 1
  min_score: 3
verifier_extensions:
  - name: invalid-audit
    rationale: Uses an invalid check id.
    check_ids:
      - "5.99"
---

# Bad Check Bundle
""",
                "unknown check_id '5.99'",
            ),
            (
                "bad-exclusive-bundle.md",
                """---
bundle_id: bad-exclusive-bundle
bundle_version: 1
title: Bad Exclusive Bundle
summary: Bundle with an unknown exclusive_with target.
trigger:
  any_terms:
    - bad exclusive bundle
  exclusive_with:
    - missing-bundle
  min_term_matches: 1
  min_score: 3
---

# Bad Exclusive Bundle
""",
                "unknown exclusive_with bundle missing-bundle",
            ),
        )

        for index, (filename, payload, expected_issue) in enumerate(cases, start=1):
            case_root = tmp_path / f"case-{index}"
            specs_dir = self._make_specs_dir(case_root)
            bundles_dir = specs_dir / "bundles"
            bundles_dir.mkdir()
            bundle_path = bundles_dir / filename

            if isinstance(payload, bytes):
                bundle_path.write_bytes(payload)
            else:
                bundle_path.write_text(payload, encoding="utf-8")

            report = run_doctor(specs_dir=specs_dir, version="0.1.0")
            protocol_bundles = next(check for check in report.checks if check.label == "Protocol Bundles")

            assert protocol_bundles.status == CheckStatus.FAIL
            assert any(expected_issue in issue for issue in protocol_bundles.issues)

    def test_default_mode_excludes_runtime_readiness_checks(self, tmp_path: Path):
        report = run_doctor(specs_dir=self._make_specs_dir(tmp_path), version="0.1.0")
        labels = {check.label for check in report.checks}

        assert report.mode == "installation"
        assert report.runtime is None
        assert report.install_scope is None
        assert report.target is None
        assert report.live_executable_probes is False
        assert "Runtime Launcher" not in labels
        assert "Runtime Config Target" not in labels
        assert "Bootstrap Network Access" not in labels
        assert "Provider/Auth Guidance" not in labels
        assert "LaTeX Toolchain" not in labels
        assert "Workflow Presets" not in labels
        assert "Live Executable Probes" not in labels

    def test_live_executable_probes_are_opt_in_and_recorded(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        specs_dir = self._make_specs_dir(tmp_path)

        def fake_which(binary: str) -> str | None:
            return {
                "pdflatex": "/usr/bin/pdflatex",
                "bibtex": "/usr/bin/bibtex",
                "wolframscript": None,
            }.get(binary)

        def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            if command == ["git", "--version"]:
                return subprocess.CompletedProcess(args=command, returncode=0, stdout="git version 2.47.0\n", stderr="")
            if command == [sys.executable, "-m", "gpd.cli", "--help"]:
                return subprocess.CompletedProcess(args=command, returncode=0, stdout="Usage: gpd [OPTIONS] COMMAND\n", stderr="")
            if command == ["/usr/bin/pdflatex", "--version"]:
                return subprocess.CompletedProcess(args=command, returncode=0, stdout="pdfTeX 3.14159265\n", stderr="")
            if command == ["/usr/bin/bibtex", "--version"]:
                return subprocess.CompletedProcess(args=command, returncode=0, stdout="BibTeX 0.99d\n", stderr="")
            raise AssertionError(f"Unexpected command: {command}")

        monkeypatch.setattr("gpd.core.health._doctor_which", fake_which)
        monkeypatch.setattr("gpd.core.health.subprocess.run", fake_run)

        report = run_doctor(
            specs_dir=specs_dir,
            version="0.1.0",
            live_executable_probes=True,
        )

        checks = {check.label: check for check in report.checks}
        probe_check = checks["Live Executable Probes"]

        assert report.live_executable_probes is True
        assert probe_check.status == CheckStatus.WARN
        assert probe_check.details["enabled"] is True
        assert probe_check.details["timeout_seconds"] == 5
        assert probe_check.details["mandatory_probe"] == "python -m gpd.cli --help"
        assert probe_check.details["skipped"] == ["latexmk", "kpsewhich", "wolframscript"]
        assert [probe["label"] for probe in probe_check.details["probed"]] == [
            "gpd-cli",
            "pdflatex",
            "bibtex",
            "latexmk",
            "kpsewhich",
            "wolframscript",
        ]
        assert probe_check.details["probed"][0]["status"] == "ok"
        assert probe_check.details["probed"][1]["status"] == "ok"
        assert probe_check.details["probed"][2]["status"] == "ok"
        assert probe_check.details["probed"][3]["status"] == "skipped"
        assert probe_check.details["probed"][4]["status"] == "skipped"
        assert probe_check.details["probed"][5]["status"] == "skipped"
        assert "latexmk not found on PATH" in probe_check.warnings
        assert "kpsewhich not found on PATH" in probe_check.warnings
        assert "wolframscript not found on PATH" in probe_check.warnings

    def test_runtime_mode_records_virtualenv_state_without_blocking(self, tmp_path: Path):
        target_dir = runtime_target_dir(tmp_path, PRIMARY_RUNTIME)
        specs_dir = self._make_specs_dir(tmp_path)

        with (
            patch("gpd.core.health._doctor_active_virtualenv", return_value=False),
            patch("gpd.core.health._doctor_which", return_value=_PRIMARY_LAUNCHER_PATH),
            patch(
                "gpd.core.health._doctor_check_bootstrap_network_access",
                return_value=HealthCheck(status=CheckStatus.OK, label="Bootstrap Network Access"),
            ),
            patch(
                "gpd.core.health._doctor_check_provider_auth",
                return_value=HealthCheck(status=CheckStatus.OK, label="Provider/Auth Guidance"),
            ),
            patch(
                "gpd.core.health._doctor_check_latex_toolchain",
                return_value=_latex_toolchain_check(),
            ),
        ):
            report = run_doctor(
                specs_dir=specs_dir,
                version="0.1.0",
                runtime=PRIMARY_RUNTIME,
                install_scope="global",
                target_dir=target_dir,
            )

        checks = {check.label: check for check in report.checks}

        assert report.mode == "runtime-readiness"
        assert report.runtime == PRIMARY_RUNTIME
        assert report.install_scope == "global"
        assert report.target == str(target_dir.resolve(strict=False))
        assert checks["Python Runtime"].status in {CheckStatus.OK, CheckStatus.WARN}
        assert checks["Python Runtime"].details["active_virtualenv"] is False
        assert not checks["Python Runtime"].issues
        assert checks["Runtime Launcher"].status == CheckStatus.OK
        assert checks["Runtime Config Target"].status == CheckStatus.OK
        assert checks["Workflow Presets"].status == CheckStatus.OK
        assert checks["Workflow Presets"].details["ready"] == 5
        assert checks["Workflow Presets"].details["degraded"] == 0
        publication = next(
            preset
            for preset in checks["Workflow Presets"].details["presets"]
            if preset["id"] == "publication-manuscript"
        )
        assert publication["summary"] == "ready"
        assert publication["status"] == "ready"
        assert publication["depends_on"] == ["LaTeX Toolchain"]
        assert publication["ready_workflows"] == ["write-paper", "peer-review", "paper-build", "arxiv-submission"]
        assert publication["degraded_workflows"] == []
        assert publication["blocked_workflows"] == []
        assert checks["Workflow Presets"].warnings == []

    def test_runtime_mode_fails_when_runtime_launcher_is_missing(self, tmp_path: Path):
        specs_dir = self._make_specs_dir(tmp_path)

        with (
            patch("gpd.core.health._doctor_active_virtualenv", return_value=True),
            patch("gpd.core.health._doctor_which", return_value=None),
            patch(
                "gpd.core.health._doctor_check_bootstrap_network_access",
                return_value=HealthCheck(status=CheckStatus.OK, label="Bootstrap Network Access"),
            ),
            patch(
                "gpd.core.health._doctor_check_provider_auth",
                return_value=HealthCheck(status=CheckStatus.OK, label="Provider/Auth Guidance"),
            ),
            patch(
                "gpd.core.health._doctor_check_latex_toolchain",
                return_value=_latex_toolchain_check(),
            ),
        ):
            report = run_doctor(specs_dir=specs_dir, version="0.1.0", runtime=PRIMARY_RUNTIME, install_scope="global")

        checks = {check.label: check for check in report.checks}
        launcher_check = next(check for check in report.checks if check.label == "Runtime Launcher")
        assert launcher_check.status == CheckStatus.FAIL
        assert any("not found on PATH" in issue for issue in launcher_check.issues)
        assert checks["Workflow Presets"].status == CheckStatus.WARN
        assert all(preset["status"] == "blocked" for preset in checks["Workflow Presets"].details["presets"])

    def test_runtime_mode_fails_when_target_parent_is_not_writable(self, tmp_path: Path):
        specs_dir = self._make_specs_dir(tmp_path)
        blocked_parent = tmp_path / "blocked"
        blocked_parent.mkdir()
        target_dir = blocked_parent / _PRIMARY_CONFIG_DIR
        blocked_parent_resolved = blocked_parent.resolve(strict=False)

        def _access(path: str | Path, mode: int) -> bool:
            candidate = Path(path).resolve(strict=False)
            if candidate == blocked_parent_resolved:
                return False
            return True

        with (
            patch("gpd.core.health._doctor_active_virtualenv", return_value=True),
            patch("gpd.core.health._doctor_which", return_value=_PRIMARY_LAUNCHER_PATH),
            patch("gpd.core.health.os.access", side_effect=_access),
            patch(
                "gpd.core.health._doctor_check_bootstrap_network_access",
                return_value=HealthCheck(status=CheckStatus.OK, label="Bootstrap Network Access"),
            ),
            patch(
                "gpd.core.health._doctor_check_provider_auth",
                return_value=HealthCheck(status=CheckStatus.OK, label="Provider/Auth Guidance"),
            ),
            patch(
                "gpd.core.health._doctor_check_latex_toolchain",
                return_value=_latex_toolchain_check(),
            ),
        ):
            report = run_doctor(
                specs_dir=specs_dir,
                version="0.1.0",
                runtime=PRIMARY_RUNTIME,
                install_scope="global",
                target_dir=target_dir,
            )

        target_check = next(check for check in report.checks if check.label == "Runtime Config Target")
        assert target_check.status == CheckStatus.FAIL
        assert any(str(blocked_parent_resolved) in issue for issue in target_check.issues)

    def test_runtime_advisories_are_non_blocking(self, tmp_path: Path):
        specs_dir = self._make_specs_dir(tmp_path)
        target_dir = runtime_target_dir(tmp_path, PRIMARY_RUNTIME)

        with (
            patch("gpd.core.health._doctor_active_virtualenv", return_value=True),
            patch("gpd.core.health._doctor_which", return_value=_PRIMARY_LAUNCHER_PATH),
            patch("gpd.core.health.os.access", return_value=True),
            patch(
                "gpd.core.health._doctor_check_bootstrap_network_access",
                return_value=HealthCheck(
                    status=CheckStatus.WARN,
                    label="Bootstrap Network Access",
                    warnings=["registry unavailable"],
                ),
            ),
            patch(
                "gpd.core.health._doctor_check_provider_auth",
                return_value=HealthCheck(
                    status=CheckStatus.OK,
                    label="Provider/Auth Guidance",
                    warnings=["manual verification required"],
                ),
            ),
            patch(
                "gpd.core.health._doctor_check_latex_toolchain",
                return_value=_latex_toolchain_check(
                    compiler_available=False,
                    compiler_path=None,
                    distribution=None,
                    bibtex_available=False,
                    latexmk_available=False,
                    kpsewhich_available=False,
                    readiness_state="blocked",
                    message="No LaTeX compiler found.",
                    warnings=["latex not installed"],
                ),
            ),
            patch(
                "gpd.core.health.assess_install_target",
                return_value=InstallTargetAssessment(
                    config_dir=target_dir.resolve(strict=False),
                    expected_runtime=PRIMARY_RUNTIME,
                    state="clean",
                    manifest_state="missing",
                    manifest_runtime=None,
                    has_managed_markers=False,
                ),
            ),
        ):
            report = run_doctor(
                specs_dir=specs_dir,
                version="0.1.0",
                runtime=PRIMARY_RUNTIME,
                install_scope="global",
                target_dir=target_dir,
            )

        checks = {check.label: check for check in report.checks}

        assert report.overall == CheckStatus.WARN
        assert checks["Bootstrap Network Access"].status == CheckStatus.WARN
        assert checks["Provider/Auth Guidance"].status == CheckStatus.OK
        assert checks["LaTeX Toolchain"].status == CheckStatus.WARN
        assert checks["Workflow Presets"].status == CheckStatus.WARN
        assert checks["Workflow Presets"].details["ready"] == 3
        assert checks["Workflow Presets"].details["degraded"] == 2
        publication = next(
            preset
            for preset in checks["Workflow Presets"].details["presets"]
            if preset["id"] == "publication-manuscript"
        )
        assert publication["status"] == "degraded"
        assert publication["usable"] is True
        assert publication["summary"] == "degraded without a LaTeX compiler: draft/review remain usable, but build/submission stay blocked"
        assert publication["depends_on"] == ["LaTeX Toolchain"]
        assert publication["degraded_workflows"] == [
            "write-paper",
            "peer-review",
        ]
        assert publication["blocked_workflows"] == [
            "paper-build",
            "arxiv-submission",
        ]
        assert checks["Workflow Presets"].warnings == [
            "Publication / manuscript and full research presets are degraded without a LaTeX compiler: "
            "`write-paper` and `peer-review` remain usable, but `paper-build` and `arxiv-submission` stay blocked."
        ]
        assert all(
            checks[label].status != CheckStatus.FAIL
            for label in (
                "Bootstrap Network Access",
                "Provider/Auth Guidance",
                "LaTeX Toolchain",
                "Workflow Presets",
            )
        )

    def test_runtime_mode_with_explicit_target_does_not_invent_scope(self, tmp_path: Path):
        target_dir = tmp_path / ".runtime-config"
        specs_dir = self._make_specs_dir(tmp_path)

        with (
            patch("gpd.core.health._doctor_active_virtualenv", return_value=True),
            patch("gpd.core.health._doctor_which", return_value="/usr/bin/runtime"),
            patch("gpd.core.health.os.access", return_value=True),
            patch(
                "gpd.core.health._doctor_check_bootstrap_network_access",
                return_value=HealthCheck(status=CheckStatus.OK, label="Bootstrap Network Access"),
            ),
            patch(
                "gpd.core.health._doctor_check_provider_auth",
                return_value=HealthCheck(status=CheckStatus.OK, label="Provider/Auth Guidance"),
            ),
            patch(
                "gpd.core.health._doctor_check_latex_toolchain",
                return_value=_latex_toolchain_check(),
            ),
        ):
            report = run_doctor(
                specs_dir=specs_dir,
                version="0.1.0",
                runtime=PRIMARY_RUNTIME,
                target_dir=target_dir,
            )

        assert report.mode == "runtime-readiness"
        assert report.runtime == PRIMARY_RUNTIME
        assert report.install_scope is None
        assert report.target == str(target_dir.resolve(strict=False))

    def test_runtime_resolution_anchors_relative_target_to_supplied_cwd(self, tmp_path: Path):
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        context = resolve_doctor_runtime_readiness(
            PRIMARY_RUNTIME,
            install_scope="local",
            target_dir="relative-target",
            cwd=workspace,
        )

        assert context.runtime == PRIMARY_RUNTIME
        assert context.install_scope == "local"
        assert context.target == (workspace / "relative-target").resolve(strict=False)

    def test_runtime_mode_with_explicit_local_scope_and_target_keeps_both(self, tmp_path: Path):
        target_dir = tmp_path / ".runtime-config"
        specs_dir = self._make_specs_dir(tmp_path)

        with (
            patch("gpd.core.health._doctor_active_virtualenv", return_value=True),
            patch("gpd.core.health._doctor_which", return_value="/usr/bin/runtime"),
            patch("gpd.core.health.os.access", return_value=True),
            patch(
                "gpd.core.health._doctor_check_bootstrap_network_access",
                return_value=HealthCheck(status=CheckStatus.OK, label="Bootstrap Network Access"),
            ),
            patch(
                "gpd.core.health._doctor_check_provider_auth",
                return_value=HealthCheck(status=CheckStatus.OK, label="Provider/Auth Guidance"),
            ),
            patch(
                "gpd.core.health._doctor_check_latex_toolchain",
                return_value=_latex_toolchain_check(),
            ),
        ):
            report = run_doctor(
                specs_dir=specs_dir,
                version="0.1.0",
                runtime=PRIMARY_RUNTIME,
                install_scope="local",
                target_dir=target_dir,
                cwd=tmp_path,
            )

        checks = {check.label: check for check in report.checks}
        assert report.install_scope == "local"
        assert report.target == str(target_dir.resolve(strict=False))
        assert checks["Runtime Config Target"].details["target"] == str(target_dir.resolve(strict=False))

    def test_runtime_mode_rejects_scope_without_runtime(self, tmp_path: Path):
        specs_dir = self._make_specs_dir(tmp_path)

        with pytest.raises(ValidationError, match="install_scope and target_dir require runtime"):
            run_doctor(specs_dir=specs_dir, version="0.1.0", install_scope="local")

    def test_runtime_readiness_mode_adds_selected_runtime_checks(self, tmp_path: Path, monkeypatch):
        specs_dir = self._make_specs_dir(tmp_path)
        monkeypatch.setattr("gpd.core.health._doctor_which", lambda *_args: "/usr/bin/runtime")
        monkeypatch.setattr("gpd.core.health.os.access", lambda *_args: True)
        monkeypatch.setattr(
            "gpd.core.health._doctor_check_bootstrap_network_access",
            lambda: HealthCheck(status=CheckStatus.OK, label="Bootstrap Network Access"),
        )
        monkeypatch.setattr(
            "gpd.core.health._doctor_check_latex_toolchain",
            lambda: _latex_toolchain_check(
                compiler_available=False,
                compiler_path=None,
                distribution=None,
                bibtex_available=False,
                latexmk_available=False,
                kpsewhich_available=False,
                readiness_state="blocked",
                message="No LaTeX compiler found.",
                warnings=["optional"],
            ),
        )

        report = run_doctor(
            specs_dir=specs_dir,
            version="0.1.0",
            runtime=PRIMARY_RUNTIME,
            install_scope="local",
            cwd=tmp_path,
        )

        checks = {check.label: check for check in report.checks}
        assert report.mode == "runtime-readiness"
        assert report.runtime == PRIMARY_RUNTIME
        assert report.install_scope == "local"
        assert report.target is not None
        for label in (
            "Runtime Launcher",
            "Runtime Config Target",
            "Bootstrap Network Access",
            "Provider/Auth Guidance",
            "LaTeX Toolchain",
            "Workflow Presets",
        ):
            assert label in checks
        assert checks["Runtime Launcher"].status == CheckStatus.OK
        assert checks["Runtime Config Target"].status == CheckStatus.OK
        assert checks["LaTeX Toolchain"].status == CheckStatus.WARN
        assert checks["Workflow Presets"].status == CheckStatus.WARN
        publication = next(
            preset
            for preset in checks["Workflow Presets"].details["presets"]
            if preset["id"] == "publication-manuscript"
        )
        assert publication["label"] == "Publication / manuscript"
        assert publication["status"] == "degraded"

    def test_runtime_readiness_keeps_publication_presets_ready_when_build_support_is_present_but_latexmk_is_missing(
        self, tmp_path: Path
    ):
        specs_dir = self._make_specs_dir(tmp_path)

        with (
            patch("gpd.core.health._doctor_active_virtualenv", return_value=True),
            patch("gpd.core.health._doctor_which", return_value="/usr/bin/runtime"),
            patch("gpd.core.health.os.access", return_value=True),
            patch(
                "gpd.core.health._doctor_check_bootstrap_network_access",
                return_value=HealthCheck(status=CheckStatus.OK, label="Bootstrap Network Access"),
            ),
            patch(
                "gpd.core.health._doctor_check_provider_auth",
                return_value=HealthCheck(status=CheckStatus.OK, label="Provider/Auth Guidance"),
            ),
            patch(
                "gpd.core.health.assess_install_target",
                return_value=InstallTargetAssessment(
                    config_dir=runtime_target_dir(tmp_path, PRIMARY_RUNTIME).resolve(strict=False),
                    expected_runtime=PRIMARY_RUNTIME,
                    state="clean",
                    manifest_state="missing",
                    manifest_runtime=None,
                    has_managed_markers=False,
                ),
            ),
            patch(
                "gpd.core.health._doctor_check_latex_toolchain",
                return_value=_latex_toolchain_check(
                    latexmk_available=False,
                    warnings=["latexmk missing"],
                ),
            ),
        ):
            report = run_doctor(specs_dir=specs_dir, version="0.1.0", runtime=PRIMARY_RUNTIME, install_scope="global")

        checks = {check.label: check for check in report.checks}
        publication = next(
            preset for preset in checks["Workflow Presets"].details["presets"] if preset["id"] == "publication-manuscript"
        )

        assert checks["LaTeX Toolchain"].status == CheckStatus.WARN
        assert checks["Workflow Presets"].status == CheckStatus.OK
        assert checks["Workflow Presets"].details["degraded"] == 0
        assert publication["status"] == "ready"
        assert publication["summary"] == "ready"
        assert publication["blocked_workflows"] == []
        assert publication["degraded_workflows"] == []

    def test_runtime_readiness_marks_clean_target_ready(self, tmp_path: Path) -> None:
        target_dir = runtime_target_dir(tmp_path, PRIMARY_RUNTIME)
        assessment = self._assessment(
            state="clean",
            target_dir=target_dir,
            manifest_state="missing",
            manifest_runtime=None,
            has_managed_markers=False,
        )

        _report, checks = self._run_runtime_doctor(tmp_path, assessment=assessment, target_dir=target_dir)

        assert checks["Runtime Config Target"].status == CheckStatus.OK
        assert checks["Runtime Config Target"].details["install_state"] == "clean"
        assert checks["Runtime Config Target"].issues == []
        assert checks["Runtime Config Target"].warnings == []

    def test_runtime_readiness_fails_for_non_clean_install_states(self, tmp_path: Path) -> None:
        cases = (
            (
                "owned_incomplete",
                {
                    "state": "owned_incomplete",
                    "missing_install_artifacts": (
                        "agents/gpd-help/SKILL.md",
                        runtime_primary_config_filename(PRIMARY_RUNTIME),
                    ),
                },
                "incomplete GPD install",
            ),
            (
                "foreign_runtime",
                {
                    "state": "foreign_runtime",
                    "manifest_runtime": FOREIGN_RUNTIME,
                },
                "belongs to",
            ),
            (
                "untrusted_manifest",
                {
                    "state": "untrusted_manifest",
                    "manifest_state": "corrupt",
                    "manifest_runtime": None,
                },
                "untrusted GPD manifest",
            ),
        )

        for install_state, assessment_kwargs, expected_issue in cases:
            case_root = tmp_path / install_state
            assessment = self._assessment(
                target_dir=runtime_target_dir(case_root, PRIMARY_RUNTIME),
                **assessment_kwargs,
            )
            report, checks = self._run_runtime_doctor(
                case_root,
                assessment=assessment,
                target_dir=assessment.config_dir,
            )

            assert report.overall == CheckStatus.FAIL
            assert checks["Runtime Config Target"].status == CheckStatus.FAIL
            assert checks["Runtime Config Target"].details["install_state"] == install_state
            assert any(expected_issue in issue for issue in checks["Runtime Config Target"].issues)


def _bootstrap_health_project(tmp_path: Path) -> Path:
    planning = tmp_path / "GPD"
    planning.mkdir()
    (planning / "phases").mkdir()
    (planning / "state.json").write_text("{}", encoding="utf-8")
    (planning / "config.json").write_text("{}", encoding="utf-8")
    (planning / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
    (planning / "STATE.md").write_text("# State\n", encoding="utf-8")
    (planning / "PROJECT.md").write_text("# Project\n", encoding="utf-8")
    return tmp_path


def _write_intent_recovery_state(
    cwd: Path,
    *,
    stale_state: dict[str, object],
    recovered_state: dict[str, object],
) -> None:
    save_state_json(cwd, stale_state)
    layout = ProjectLayout(cwd)
    json_tmp = layout.gpd / ".state-json-tmp"
    md_tmp = layout.gpd / ".state-md-tmp"
    json_tmp.write_text(json.dumps(recovered_state, indent=2) + "\n", encoding="utf-8")
    md_tmp.write_text(generate_state_markdown(recovered_state), encoding="utf-8")
    layout.state_intent.write_text(f"{json_tmp}\n{md_tmp}\n", encoding="utf-8")


def _init_git_repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)
    repo_root = Path(__file__).resolve().parents[2]
    (tmp_path / ".gitignore").write_text((repo_root / ".gitignore").read_text(encoding="utf-8"), encoding="utf-8")
    return tmp_path


def _canonical_plan_frontmatter() -> str:
    return (FIXTURES_DIR / "plan_with_contract.md").read_text(encoding="utf-8")


class TestCheckLatestReturn:
    def test_no_summaries_is_ok(self, tmp_path: Path) -> None:
        result = check_latest_return(_bootstrap_health_project(tmp_path))

        assert result.status == CheckStatus.OK
        assert result.details["reason"] == "no_summaries"

    def test_summary_with_valid_return_is_ok(self, tmp_path: Path) -> None:
        cwd = _bootstrap_health_project(tmp_path)
        phase_dir = cwd / "GPD" / "phases" / "01-setup"
        phase_dir.mkdir(parents=True)
        summary_content = (
            "# Summary\n\n"
            "```yaml\n"
            "gpd_return:\n"
            "  status: completed\n"
            "  files_written: [src/main.py]\n"
            "  issues: []\n"
            "  next_actions: [/gpd:verify-work 02]\n"
            "```\n"
        )
        (phase_dir / "01-setup-01-SUMMARY.md").write_text(summary_content, encoding="utf-8")

        result = check_latest_return(cwd)

        assert result.status == CheckStatus.OK
        assert result.label == "Latest Return Envelope"

    def test_summary_without_return_block_warns(self, tmp_path: Path) -> None:
        cwd = _bootstrap_health_project(tmp_path)
        phase_dir = cwd / "GPD" / "phases" / "01-setup"
        phase_dir.mkdir(parents=True)
        (phase_dir / "01-setup-01-SUMMARY.md").write_text(
            "# Summary\nJust text, no return block.\n",
            encoding="utf-8",
        )

        result = check_latest_return(cwd)

        assert result.status == CheckStatus.WARN
        assert result.warnings

    def test_summary_with_coercive_numeric_return_counts_fails(self, tmp_path: Path) -> None:
        cwd = _bootstrap_health_project(tmp_path)
        phase_dir = cwd / "GPD" / "phases" / "01-setup"
        phase_dir.mkdir(parents=True)
        (phase_dir / "01-setup-01-SUMMARY.md").write_text(
            "# Summary\n\n"
            "```yaml\n"
            "gpd_return:\n"
            "  status: completed\n"
            "  files_written: [src/main.py]\n"
            "  issues: []\n"
            "  next_actions: [/gpd:verify-work 02]\n"
            "  tasks_completed: true\n"
            "  tasks_total: 2.0\n"
            "```\n",
            encoding="utf-8",
        )

        result = check_latest_return(cwd)

        assert result.status == CheckStatus.FAIL
        assert "tasks_completed not a number" in result.issues[0] or "tasks_completed not a number" in " ".join(result.issues)
        assert "tasks_total not a number" in " ".join(result.issues)
