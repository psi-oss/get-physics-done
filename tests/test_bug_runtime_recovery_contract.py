"""Phase 15 runtime recovery contract tests."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

import gpd.runtime_cli as runtime_cli
from gpd.adapters.runtime_catalog import iter_runtime_descriptors
from gpd.cli import app
from gpd.core.observability import (
    derive_execution_visibility,
    project_execution_lineage_head,
    write_execution_lineage_head,
)
from gpd.core.state import default_state_dict
from gpd.core.suggest import suggest_next

REPO_ROOT = Path(__file__).resolve().parent
HANDOFF_BUNDLE_FIXTURES = REPO_ROOT / "fixtures" / "handoff-bundle"
RUNNER = CliRunner()
BRIDGE_RUNTIME_DESCRIPTOR = iter_runtime_descriptors()[0]


class _DoctorModelDumpResult:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def model_dump(self, *args, **kwargs) -> dict[str, object]:
        return dict(self._payload)


def _copy_fixture_workspace(tmp_path: Path, slug: str, variant: str = "positive") -> Path:
    source = HANDOFF_BUNDLE_FIXTURES / slug / variant / "workspace"
    target = tmp_path / f"{slug}-{variant}"
    shutil.copytree(source, target)
    return target


def _write_runtime_manifest(config_dir: Path, runtime_name: str, install_scope: str = "local") -> None:
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / runtime_cli.get_shared_install_metadata().manifest_name).write_text(
        json.dumps(
            {
                "runtime": runtime_name,
                "install_scope": install_scope,
                "install_target_dir": str(config_dir),
            }
        ),
        encoding="utf-8",
    )


@pytest.mark.parametrize(
    ("manifest_payload", "artifact_override", "expected_kind", "expected_phrase"),
    [
        (
            {"runtime": BRIDGE_RUNTIME_DESCRIPTOR.runtime_name},
            None,
            runtime_cli._BridgeFailureKind.MISSING_INSTALL_SCOPE,
            "The manifest must declare a non-empty `install_scope` field.",
        ),
        (
            {
                "runtime": next(
                    item.runtime_name
                    for item in iter_runtime_descriptors()
                    if item.runtime_name != BRIDGE_RUNTIME_DESCRIPTOR.runtime_name
                ),
                "install_scope": "local",
            },
            None,
            runtime_cli._BridgeFailureKind.RUNTIME_MISMATCH,
            "GPD runtime bridge mismatch",
        ),
        (
            {"runtime": BRIDGE_RUNTIME_DESCRIPTOR.runtime_name, "install_scope": "local"},
            ("missing-artifact.txt",),
            runtime_cli._BridgeFailureKind.MISSING_INSTALL_ARTIFACTS,
            "Missing required install artifacts",
        ),
    ],
)
def test_runtime_bridge_recovery_contract_classifies_failures_and_keeps_valid_handoff(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    manifest_payload: dict[str, object],
    artifact_override: tuple[str, ...] | None,
    expected_kind: runtime_cli._BridgeFailureKind,
    expected_phrase: str,
) -> None:
    runtime_name = BRIDGE_RUNTIME_DESCRIPTOR.runtime_name
    adapter = runtime_cli.get_adapter(runtime_name)
    config_dir = tmp_path / BRIDGE_RUNTIME_DESCRIPTOR.config_dir_name
    _write_runtime_manifest(config_dir, runtime_name, install_scope=str(manifest_payload.get("install_scope") or "local"))
    (config_dir / runtime_cli.get_shared_install_metadata().manifest_name).write_text(
        json.dumps(manifest_payload),
        encoding="utf-8",
    )

    if artifact_override is not None:
        monkeypatch.setattr(adapter, "missing_install_artifacts", lambda target_dir: artifact_override)
    monkeypatch.setattr("gpd.runtime_cli._maybe_reexec_from_checkout", lambda *_args, **_kwargs: None)
    monkeypatch.chdir(tmp_path)

    manifest_status, _manifest_payload, manifest_runtime = runtime_cli.load_install_manifest_runtime_status(config_dir)
    manifest_scope_status, manifest_scope_payload, manifest_install_scope = runtime_cli.load_install_manifest_scope_status(
        config_dir
    )
    if manifest_scope_status == "ok":
        manifest_install_scope = manifest_scope_payload.get("install_scope")
        if not isinstance(manifest_install_scope, str):
            manifest_install_scope = None

    failure = runtime_cli._classify_bridge_failure(
        runtime=runtime_name,
        config_dir=config_dir,
        install_scope="local",
        explicit_target=False,
        cli_cwd=tmp_path,
        manifest_status=manifest_status,
        manifest_runtime=manifest_runtime,
        manifest_scope_status=manifest_scope_status,
        manifest_install_scope=manifest_install_scope,
        missing=artifact_override,
        has_managed_install_markers=runtime_cli.config_dir_has_managed_install_markers(config_dir),
    )

    assert failure is not None
    assert failure.kind is expected_kind
    assert expected_phrase in failure.message

    exit_code = runtime_cli.main(
        [
            "--runtime",
            runtime_name,
            "--config-dir",
            str(config_dir),
            "--install-scope",
            "local",
            "state",
            "load",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 127
    assert expected_phrase in captured.err


def test_runtime_bridge_recovery_contract_hands_off_to_cli_on_fixture_workspace(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    workspace = _copy_fixture_workspace(tmp_path, "bridge-vs-cli")
    runtime_name = BRIDGE_RUNTIME_DESCRIPTOR.runtime_name
    adapter = runtime_cli.get_adapter(runtime_name)
    config_dir = workspace / BRIDGE_RUNTIME_DESCRIPTOR.config_dir_name
    _write_runtime_manifest(config_dir, runtime_name, install_scope="local")

    observed: dict[str, object] = {}

    def fake_entrypoint() -> int:
        observed["argv"] = list(runtime_cli.sys.argv)
        return 0

    monkeypatch.chdir(workspace)
    monkeypatch.setattr("gpd.runtime_cli._maybe_reexec_from_checkout", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("gpd.runtime_cli.get_adapter", lambda _runtime_name: adapter)
    monkeypatch.setattr(adapter, "missing_install_artifacts", lambda target_dir: ())
    monkeypatch.setattr("gpd.cli.entrypoint", fake_entrypoint)

    exit_code = runtime_cli.main(
        [
            "--runtime",
            runtime_name,
            "--config-dir",
            str(config_dir),
            "--install-scope",
            "local",
            "state",
            "load",
        ]
    )

    assert exit_code == 0
    assert observed["argv"] == ["gpd", "state", "load"]


def test_doctor_runtime_recovery_contract_defaults_to_local_target_when_scope_is_unspecified(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from gpd.specs import SPECS_DIR

    workspace = _copy_fixture_workspace(tmp_path, "config-readback")
    runtime_name = BRIDGE_RUNTIME_DESCRIPTOR.runtime_name
    mock_result = _DoctorModelDumpResult({"mode": "runtime-readiness", "overall": "ok"})

    with (
        patch(
            "gpd.hooks.runtime_detect.resolve_runtime_target_dir",
            side_effect=AssertionError(
                "doctor should stay local-first and must not consult detected install targets "
                "when scope is unspecified"
            ),
        ),
        patch("gpd.core.health.run_doctor", return_value=mock_result) as mock_doctor,
    ):
        result = RUNNER.invoke(app, ["--cwd", str(workspace), "--raw", "doctor", "--runtime", runtime_name])

    assert result.exit_code == 0
    assert json.loads(result.output) == {"mode": "runtime-readiness", "overall": "ok"}
    mock_doctor.assert_called_once_with(
        specs_dir=SPECS_DIR,
        runtime=runtime_name,
        install_scope="local",
        target_dir=None,
        cwd=workspace,
        live_executable_probes=False,
    )


@pytest.mark.parametrize(
    ("current_payload", "head_payload", "expected_mode", "expected_classification", "expected_note_fragment"),
    [
        (
            {
                "session_id": "sess-snapshot-only",
                "phase": "03",
                "plan": "01",
                "segment_status": "active",
                "current_task": "Inspect a live segment",
                "updated_at": "2026-04-09T12:01:00+00:00",
            },
            "{not valid json}",
            "snapshot-only",
            "active",
            "execution-head.json",
        ),
        (
            "{not valid json}",
            {
                "session_id": "sess-trace-only",
                "phase": "03",
                "plan": "01",
                "segment_status": "waiting_review",
                "waiting_for_review": True,
                "updated_at": "2026-04-09T12:03:00+00:00",
            },
            "trace-only",
            "waiting",
            "current-execution.json",
        ),
        (
            "{not valid json}",
            "{also not valid json}",
            "degraded",
            "degraded",
            "current-execution.json",
        ),
    ],
)
def test_observability_recovery_contract_marks_partial_telemetry_conservatively(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    current_payload: object,
    head_payload: object,
    expected_mode: str,
    expected_classification: str,
    expected_note_fragment: str,
) -> None:
    project = tmp_path / "project"
    (project / "GPD" / "observability").mkdir(parents=True, exist_ok=True)
    (project / "GPD" / "lineage").mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(project)

    current_path = project / "GPD" / "observability" / "current-execution.json"
    head_path = project / "GPD" / "lineage" / "execution-head.json"
    if isinstance(current_payload, dict):
        current_path.write_text(json.dumps(current_payload), encoding="utf-8")
    else:
        current_path.write_text(current_payload, encoding="utf-8")
    if isinstance(head_payload, dict):
        write_execution_lineage_head(
            project,
            project_execution_lineage_head(
                head_payload,
                last_applied_seq=1,
                last_applied_event_id="evt-1",
                recorded_at="2026-04-09T12:03:00+00:00",
            ),
        )
    else:
        head_path.write_text(head_payload, encoding="utf-8")

    visibility = derive_execution_visibility(project)

    assert visibility is not None
    assert visibility.visibility_mode == expected_mode
    assert visibility.status_classification == expected_classification
    assert visibility.visibility_note is not None
    assert expected_note_fragment in visibility.visibility_note
    assert visibility.suggested_next_commands[0].command == "gpd observe sessions --last 5"
    assert all("--session" not in suggestion.command for suggestion in visibility.suggested_next_commands)


def test_paused_work_recovery_contract_keeps_resume_above_convention_cleanup(tmp_path: Path) -> None:
    project = tmp_path / "project"
    planning = project / "GPD"
    planning.mkdir(parents=True, exist_ok=True)
    (planning / "PROJECT.md").write_text("# Recovery Project\n", encoding="utf-8")
    (planning / "ROADMAP.md").write_text("# Roadmap\n\n## Phase 1\n", encoding="utf-8")
    state = default_state_dict()
    state["position"].update({"status": "Paused", "paused_at": "2026-01-15T10:00:00Z"})
    state["convention_lock"] = {"metric_signature": "(-,+,+,+)"}
    (planning / "state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
    (planning / "STATE.md").write_text(json.dumps(state), encoding="utf-8")

    result = suggest_next(project)
    actions = [suggestion.action for suggestion in result.suggestions]

    assert result.top_action is not None
    assert result.top_action.action == "resume"
    assert "resume" in result.top_action.command
    assert "set-conventions" not in actions
    assert result.context.missing_conventions == ()
    assert result.context.paused_at == "2026-01-15T10:00:00Z"
