"""Integration tests for CLI commands with zero prior test coverage.

Each test exercises the real CLI -> core path (no mocks) using a minimal
GPD project directory created by the ``gpd_project`` fixture.  The goal is
to verify that the CLI wiring, argument parsing, and core logic all cooperate
without crashing.
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from gpd.adapters import get_adapter
from gpd.adapters.runtime_catalog import iter_runtime_descriptors
from gpd.cli import app
from gpd.core.constants import AGENT_ID_FILENAME, ENV_DATA_DIR
from gpd.core.costs import UsageRecord, usage_ledger_path
from gpd.core.state import default_state_dict, generate_state_markdown
from tests.runtime_install_helpers import seed_complete_runtime_install

runner = CliRunner()
_RUNTIME_DESCRIPTORS = iter_runtime_descriptors()
_DOLLAR_COMMAND_DESCRIPTOR = next(descriptor for descriptor in _RUNTIME_DESCRIPTORS if descriptor.command_prefix.startswith("$"))
_SLASH_COMMAND_DESCRIPTOR = next(
    descriptor
    for descriptor in _RUNTIME_DESCRIPTORS
    if descriptor.command_prefix.startswith("/") and descriptor.runtime_name != _DOLLAR_COMMAND_DESCRIPTOR.runtime_name
)
_ENV_OVERRIDE_DESCRIPTOR = next(
    descriptor
    for descriptor in _RUNTIME_DESCRIPTORS
    if (
        descriptor.global_config.env_var
        or descriptor.global_config.env_dir_var
        or descriptor.global_config.env_file_var
    )
)
_SECONDARY_PERMISSIONS_DESCRIPTOR = next(
    descriptor
    for descriptor in _RUNTIME_DESCRIPTORS
    if descriptor.runtime_name != _ENV_OVERRIDE_DESCRIPTOR.runtime_name
)


@pytest.fixture()
def codex_command_prefix(monkeypatch: pytest.MonkeyPatch) -> str:
    """Force the integration preflight surface to resolve the Codex runtime."""
    monkeypatch.setattr("gpd.cli.detect_runtime_for_gpd_use", lambda cwd=None: _DOLLAR_COMMAND_DESCRIPTOR.runtime_name)
    return get_adapter(_DOLLAR_COMMAND_DESCRIPTOR.runtime_name).command_prefix


@pytest.fixture()
def claude_code_command_prefix(monkeypatch: pytest.MonkeyPatch) -> str:
    """Force the integration preflight surface to resolve the Claude Code runtime."""
    monkeypatch.setattr("gpd.cli.detect_runtime_for_gpd_use", lambda cwd=None: _SLASH_COMMAND_DESCRIPTOR.runtime_name)
    return get_adapter(_SLASH_COMMAND_DESCRIPTOR.runtime_name).command_prefix

def _runtime_env_prefixes() -> tuple[str, ...]:
    prefixes: set[str] = set()
    for descriptor in _RUNTIME_DESCRIPTORS:
        for env_var in descriptor.activation_env_vars:
            prefixes.add(env_var)
            prefixes.add(env_var.rsplit("_", 1)[0] if "_" in env_var else env_var)
    return tuple(sorted(prefixes, key=len, reverse=True))


_RUNTIME_ENV_PREFIXES = _runtime_env_prefixes()


def _runtime_env_vars_to_clear() -> set[str]:
    env_vars = {"GPD_ACTIVE_RUNTIME", "XDG_CONFIG_HOME"}
    for descriptor in _RUNTIME_DESCRIPTORS:
        global_config = descriptor.global_config
        for env_var in (global_config.env_var, global_config.env_dir_var, global_config.env_file_var):
            if env_var:
                env_vars.add(env_var)
    return env_vars


_RUNTIME_ENV_VARS_TO_CLEAR = _runtime_env_vars_to_clear()


@pytest.fixture(autouse=True)
def _reset_runtime_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep CLI integration tests isolated from prior runtime env overrides."""
    for key in list(os.environ):
        if key.startswith(_RUNTIME_ENV_PREFIXES) or key in _RUNTIME_ENV_VARS_TO_CLEAR:
            monkeypatch.delenv(key, raising=False)


def _install_runtime(
    project_root: Path,
    descriptor,
    *,
    target: Path | None = None,
    is_global: bool = False,
    explicit_target: bool = False,
):
    adapter = get_adapter(descriptor.runtime_name)
    install_target = target or (project_root / descriptor.config_dir_name)
    install_target.mkdir(parents=True, exist_ok=True)
    gpd_root = Path(__file__).resolve().parents[1] / "src" / "gpd"
    adapter.install(gpd_root, install_target, is_global=is_global, explicit_target=explicit_target)
    return adapter, install_target


def _break_install_completeness(target: Path, adapter) -> None:
    """Remove one required artifact so the install remains owned but incomplete."""
    missing_relpath = adapter.install_completeness_relpaths()[0]
    missing_path = target / missing_relpath
    if missing_path.is_dir():
        shutil.rmtree(missing_path)
    elif missing_path.exists():
        missing_path.unlink()
    else:
        raise AssertionError(f"Expected install artifact {missing_relpath!r} to exist under {target}")


def _set_runtime_config_override(monkeypatch: pytest.MonkeyPatch, descriptor, target: Path) -> None:
    env_var = (
        descriptor.global_config.env_var
        or descriptor.global_config.env_dir_var
        or descriptor.global_config.env_file_var
    )
    assert env_var is not None
    env_value = str(target / "config.json") if env_var == descriptor.global_config.env_file_var else str(target)
    monkeypatch.setenv(env_var, env_value)


def _target_file_snapshot(target: Path) -> dict[str, bytes]:
    snapshot: dict[str, bytes] = {}
    for path in sorted(target.rglob("*")):
        if path.is_file():
            snapshot[str(path.relative_to(target))] = path.read_bytes()
    return snapshot


def _activate_runtime(monkeypatch: pytest.MonkeyPatch, descriptor, value: str = "active") -> None:
    assert descriptor.activation_env_vars
    monkeypatch.setenv(descriptor.activation_env_vars[0], value)


def _expose_runtime_launcher(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, descriptor) -> Path:
    """Place a stub runtime launcher on PATH so doctor can validate the runtime surface."""
    launch_argv = shlex.split(descriptor.launch_command)
    launch_executable = launch_argv[0] if launch_argv else descriptor.launch_command.strip()
    assert launch_executable
    bin_dir = tmp_path / "runtime-bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    launcher_path = bin_dir / launch_executable
    launcher_path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    launcher_path.chmod(0o755)
    current_path = os.environ.get("PATH", "")
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{current_path}" if current_path else str(bin_dir))
    return launcher_path


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def gpd_project(tmp_path: Path) -> Path:
    """Create a minimal GPD project with all files commands might touch."""
    planning = tmp_path / "GPD"
    planning.mkdir()

    state = default_state_dict()
    state["position"].update(
        {
            "current_phase": "01",
            "current_phase_name": "Test Phase",
            "total_phases": 2,
            "status": "Executing",
        }
    )
    state["convention_lock"].update(
        {
            "metric_signature": "(-,+,+,+)",
            "coordinate_system": "Cartesian",
            "custom_conventions": {"my_custom": "value"},
        }
    )
    (planning / "state.json").write_text(json.dumps(state, indent=2))
    (planning / "STATE.md").write_text(generate_state_markdown(state))
    (planning / "PROJECT.md").write_text(
        "# Test Project\n\n## Core Research Question\nWhat is physics?\n"
    )
    (planning / "REQUIREMENTS.md").write_text(
        "# Requirements\n\n- [ ] **REQ-01**: Do the thing\n"
    )
    (planning / "ROADMAP.md").write_text(
        "# Roadmap\n\n## Phase 1: Test Phase\nGoal: Test\nRequirements: REQ-01\n"
        "\n## Phase 2: Phase Two\nGoal: More tests\nRequirements: REQ-01\n"
    )
    (planning / "CONVENTIONS.md").write_text(
        "# Conventions\n\n- Metric: (-,+,+,+)\n- Coordinates: Cartesian\n"
    )
    (planning / "config.json").write_text(
        json.dumps(
            {
                "autonomy": "yolo",
                "research_mode": "balanced",
                "parallelization": True,
                "commit_docs": True,
                "model_profile": "review",
                "workflow": {
                    "research": True,
                    "plan_checker": True,
                    "verifier": True,
                },
            }
        )
    )

    # Phase directories
    p1 = planning / "phases" / "01-test-phase"
    p1.mkdir(parents=True)
    (p1 / "README.md").write_text("# Phase 1: Test Phase\n")
    (p1 / "01-PLAN.md").write_text(
        "---\nphase: '01'\nplan: '01'\nwave: 1\n---\n\n# Plan A\n\n## Tasks\n\n- Task 1\n"
    )
    (p1 / "01-SUMMARY.md").write_text(
        '---\nphase: "01"\nplan: "01"\ndepth: "full"\nprovides: ["main-module"]\ncompleted: "2026-03-22"\none-liner: "Set up project"\n'
        "key-files:\n  - src/main.py\n"
        "dependency-graph:\n  provides:\n    - main-module\n  affects:\n    - phase-2\n"
        "patterns-established:\n  - modular-design\n"
        "key-decisions:\n  - Use SI units\n"
        "methods:\n  added:\n    - finite-element\n"
        "conventions:\n  metric: (-,+,+,+)\n"
        "---\n\n# Summary\n\n**Set up the project.**\n\n"
        "## Key Results\n\nWe got results.\n\n## Equations Derived\n\nE = mc^2\n"
    )

    p2 = planning / "phases" / "02-phase-two"
    p2.mkdir(parents=True)
    (p2 / "README.md").write_text("# Phase 2: Phase Two\n")

    return tmp_path


@pytest.fixture(autouse=True)
def _chdir(gpd_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """All tests run from the project directory."""
    monkeypatch.chdir(gpd_project)


def _invoke(*args: str, expect_ok: bool = True) -> object:
    """Invoke a gpd CLI command and return the CliRunner result."""
    result = runner.invoke(app, list(args), catch_exceptions=False)
    if expect_ok:
        assert result.exit_code == 0, (
            f"gpd {' '.join(args)} failed (exit {result.exit_code}):\n{result.output}"
        )
    return result


def _iso_minutes_ago(minutes: int) -> str:
    return (datetime.now(UTC) - timedelta(minutes=minutes)).isoformat()


def _bootstrap_recent_project(root: Path, *, phase_slug: str, title: str) -> Path:
    planning = root / "GPD"
    phase_dir = planning / "phases" / phase_slug
    phase_dir.mkdir(parents=True, exist_ok=True)
    (planning / "PROJECT.md").write_text(
        f"# {title}\n\n## What This Is\n\nRecent recovery test project.\n",
        encoding="utf-8",
    )
    (planning / "ROADMAP.md").write_text("# Roadmap\n\n- Phase 1\n", encoding="utf-8")
    state = default_state_dict()
    state["position"]["current_phase"] = "1"
    state["position"]["status"] = "Paused"
    planning.mkdir(parents=True, exist_ok=True)
    (planning / "state.json").write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    (planning / "STATE.md").write_text(generate_state_markdown(state), encoding="utf-8")
    (phase_dir / ".continue-here.md").write_text("resume\n", encoding="utf-8")
    return root


# ═══════════════════════════════════════════════════════════════════════════
# 1. timestamp
# ═══════════════════════════════════════════════════════════════════════════


class TestTimestamp:
    def test_timestamp_default(self) -> None:
        result = _invoke("timestamp")
        assert "timestamp" in result.output.lower() or "T" in result.output

    def test_timestamp_full(self) -> None:
        result = _invoke("timestamp", "full")
        # ISO 8601 contains 'T' separator
        assert "T" in result.output or "timestamp" in result.output

    def test_timestamp_date(self) -> None:
        result = _invoke("timestamp", "date")
        # Should contain a date-like string YYYY-MM-DD
        assert "-" in result.output

    def test_timestamp_filename(self) -> None:
        result = _invoke("timestamp", "filename")
        assert "T" in result.output or "timestamp" in result.output

    def test_timestamp_raw(self) -> None:
        result = _invoke("--raw", "timestamp", "full")
        parsed = json.loads(result.output)
        assert "timestamp" in parsed
        assert "T" in parsed["timestamp"]


class TestResume:
    def test_resume_raw_surfaces_ranked_candidates(self, gpd_project: Path) -> None:
        handoff = gpd_project / "GPD" / "phases" / "01-test-phase" / ".continue-here.md"
        handoff.write_text("resume\n", encoding="utf-8")
        state_path = gpd_project / "GPD" / "state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["position"]["status"] = "Paused"
        state["session"]["resume_file"] = "GPD/phases/01-test-phase/.continue-here.md"
        state_path.write_text(json.dumps(state), encoding="utf-8")

        result = _invoke("--raw", "resume")
        parsed = json.loads(result.output)

        assert parsed["resume_mode"] is None
        assert parsed["execution_resume_file"] == "GPD/phases/01-test-phase/.continue-here.md"
        assert parsed["segment_candidates"] == [
            {
                "source": "session_resume_file",
                "status": "handoff",
                "resume_file": "GPD/phases/01-test-phase/.continue-here.md",
                "resumable": False,
            }
        ]

    def test_resume_human_output_surfaces_public_and_backend_commands(self, gpd_project: Path) -> None:
        handoff = gpd_project / "GPD" / "phases" / "01-test-phase" / ".continue-here.md"
        handoff.write_text("resume\n", encoding="utf-8")
        state_path = gpd_project / "GPD" / "state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["position"]["status"] = "Paused"
        state["session"]["resume_file"] = "GPD/phases/01-test-phase/.continue-here.md"
        state_path.write_text(json.dumps(state), encoding="utf-8")

        result = _invoke("resume")
        normalized = " ".join(result.output.split())

        assert "Resume Summary" in result.output
        assert "Read-only local recovery snapshot for this workspace." in result.output
        assert "A recorded session handoff is available" in normalized
        assert "no resumable live execution snapshot is currently active." in normalized
        assert "gpd resume" in result.output
        assert "gpd resume --recent" in result.output
        assert "gpd init resume" in result.output
        assert "resume-work" in result.output
        assert "suggest-next" in result.output

    def test_resume_human_output_marks_missing_session_handoff_as_advisory(self, gpd_project: Path) -> None:
        state_path = gpd_project / "GPD" / "state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["position"]["status"] = "Paused"
        state["session"]["resume_file"] = "GPD/phases/01-test-phase/.continue-here.md"
        state_path.write_text(json.dumps(state), encoding="utf-8")

        result = _invoke("resume")

        assert "Recorded session handoff is missing:" in result.output
        assert "missing" in result.output
        assert "./GPD/phases/01-test-phase/.continue-here.md" in result.output

    def test_resume_recent_lists_recent_projects_in_recency_order(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        data_dir = tmp_path / "gpd-data"
        monkeypatch.setenv("GPD_DATA_DIR", str(data_dir))

        older_project = _bootstrap_recent_project(
            tmp_path / "recent-alpha",
            phase_slug="01-alpha",
            title="Recent Alpha Project",
        )
        newer_project = _bootstrap_recent_project(
            tmp_path / "recent-beta",
            phase_slug="01-beta",
            title="Recent Beta Project",
        )

        monkeypatch.chdir(older_project)
        _invoke(
            "state",
            "record-session",
            "--stopped-at",
            "Alpha stop",
            "--resume-file",
            "GPD/phases/01-alpha/.continue-here.md",
        )
        monkeypatch.chdir(newer_project)
        _invoke(
            "state",
            "record-session",
            "--stopped-at",
            "Beta stop",
            "--resume-file",
            "GPD/phases/01-beta/.continue-here.md",
        )

        outside = tmp_path / "outside"
        outside.mkdir()
        monkeypatch.chdir(outside)

        result = _invoke("resume", "--recent")

        beta_marker = "Beta stop"
        alpha_marker = "Alpha stop"

        assert beta_marker in result.output
        assert alpha_marker in result.output
        assert result.output.index(beta_marker) < result.output.index(alpha_marker)

    def test_resume_outside_project_hints_recent_selector(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        outside = tmp_path / "outside"
        outside.mkdir()
        monkeypatch.chdir(outside)

        result = _invoke("resume")

        assert "gpd resume --recent" in result.output


class TestObserveExecution:
    def test_observe_execution_raw_surfaces_possibly_stalled_active_segment_without_mutating_state(
        self, gpd_project: Path
    ) -> None:
        observability = gpd_project / "GPD" / "observability"
        observability.mkdir(parents=True, exist_ok=True)
        (observability / "current-execution.json").write_text(
            json.dumps(
                {
                    "session_id": "sess-1",
                    "phase": "01",
                    "plan": "02",
                    "segment_id": "seg-4",
                    "segment_status": "active",
                    "current_task": "Inspect a long-running segment",
                    "updated_at": _iso_minutes_ago(31),
                }
            ),
            encoding="utf-8",
        )
        snapshot_before = _target_file_snapshot(gpd_project / "GPD")

        result = _invoke("--raw", "observe", "execution")
        parsed = json.loads(result.output)

        assert parsed["found"] is True
        assert parsed["current_state"] == "active"
        assert parsed["assessment"] == "possibly stalled"
        assert parsed["last_update_age_minutes"] >= 30
        assert parsed["current_task"] == "Inspect a long-running segment"
        assert parsed["next_check_command"] == "gpd observe show --session sess-1 --last 20"
        assert "has stalled" in parsed["next_check_reason"]
        assert parsed["suggested_next_steps"]
        assert any("gpd observe show --session sess-1 --last 20" in step for step in parsed["suggested_next_steps"])
        assert parsed["suggested_next_commands"]
        assert _target_file_snapshot(gpd_project / "GPD") == snapshot_before

    def test_observe_execution_raw_surfaces_tangent_branch_later_follow_up_without_mutating_state(
        self, gpd_project: Path
    ) -> None:
        observability = gpd_project / "GPD" / "observability"
        observability.mkdir(parents=True, exist_ok=True)
        (observability / "current-execution.json").write_text(
            json.dumps(
                {
                    "session_id": "sess-2",
                    "phase": "01",
                    "plan": "03",
                    "segment_id": "seg-5",
                    "segment_status": "waiting_review",
                    "waiting_for_review": True,
                    "checkpoint_reason": "pre_fanout",
                    "tangent_summary": "Check whether the 2D case is degenerate",
                    "tangent_decision": "branch_later",
                    "updated_at": _iso_minutes_ago(5),
                }
            ),
            encoding="utf-8",
        )
        snapshot_before = _target_file_snapshot(gpd_project / "GPD")

        result = _invoke("--raw", "observe", "execution")
        parsed = json.loads(result.output)

        assert parsed["found"] is True
        assert parsed["status_classification"] == "waiting"
        assert parsed["tangent_summary"] == "Check whether the 2D case is degenerate"
        assert parsed["tangent_decision"] == "branch_later"
        assert parsed["tangent_decision_label"] == "branch later"
        assert parsed["next_check_command"] == "gpd resume"
        assert parsed["tangent_follow_up"] == [
            "Use the runtime `tangent` command to keep the chooser explicit for this alternative path.",
            "Use the runtime `branch-hypothesis` command only if you decide to open a git-backed alternative path after this bounded stop.",
        ]
        assert _target_file_snapshot(gpd_project / "GPD") == snapshot_before


# ═══════════════════════════════════════════════════════════════════════════
# 2. slug
# ═══════════════════════════════════════════════════════════════════════════


class TestSlug:
    def test_slug_basic(self) -> None:
        result = _invoke("slug", "Hello World")
        assert "hello-world" in result.output.lower()

    def test_slug_with_special_chars(self) -> None:
        result = _invoke("slug", "Quantum Field Theory (QFT)")
        output_lower = result.output.lower()
        assert "quantum" in output_lower
        assert "field" in output_lower

    def test_slug_raw(self) -> None:
        result = _invoke("--raw", "slug", "Test Slug")
        parsed = json.loads(result.output)
        assert "slug" in parsed
        assert "test-slug" in parsed["slug"]


# ═══════════════════════════════════════════════════════════════════════════
# 3. verify-path
# ═══════════════════════════════════════════════════════════════════════════


class TestVerifyPath:
    def test_verify_existing_file(self, gpd_project: Path) -> None:
        result = _invoke("verify-path", "GPD/state.json")
        assert "file" in result.output.lower() or "True" in result.output or "true" in result.output

    def test_verify_existing_directory(self) -> None:
        result = _invoke("verify-path", "GPD")
        assert "directory" in result.output.lower() or "True" in result.output or "true" in result.output

    def test_verify_nonexistent_path(self) -> None:
        result = _invoke("verify-path", "does/not/exist.txt", expect_ok=False)
        assert result.exit_code == 1
        assert "False" in result.output or "false" in result.output

    def test_verify_path_raw(self, gpd_project: Path) -> None:
        result = _invoke("--raw", "verify-path", "GPD/state.json")
        parsed = json.loads(result.output)
        assert parsed["exists"] is True
        assert parsed["type"] == "file"

    def test_verify_path_raw_nonexistent(self) -> None:
        result = _invoke("--raw", "verify-path", "nope.txt", expect_ok=False)
        assert result.exit_code == 1
        parsed = json.loads(result.output)
        assert parsed["exists"] is False


# ═══════════════════════════════════════════════════════════════════════════
# 4. history-digest
# ═══════════════════════════════════════════════════════════════════════════


class TestHistoryDigest:
    def test_history_digest_basic(self) -> None:
        result = _invoke("history-digest")
        # Should succeed and contain some output
        assert result.exit_code == 0

    def test_history_digest_raw(self) -> None:
        result = _invoke("--raw", "history-digest")
        parsed = json.loads(result.output)
        assert "phases" in parsed
        assert "decisions" in parsed
        assert "methods" in parsed

    def test_history_digest_finds_phase_data(self) -> None:
        result = _invoke("--raw", "history-digest")
        parsed = json.loads(result.output)
        # Phase 01 has a SUMMARY.md with frontmatter
        assert "01" in parsed["phases"] or "1" in parsed["phases"]

    def test_history_digest_extracts_methods(self) -> None:
        result = _invoke("--raw", "history-digest")
        parsed = json.loads(result.output)
        assert "finite-element" in parsed["methods"]

    def test_history_digest_extracts_decisions(self) -> None:
        result = _invoke("--raw", "history-digest")
        parsed = json.loads(result.output)
        assert len(parsed["decisions"]) > 0
        decision_texts = [d["decision"] for d in parsed["decisions"]]
        assert any("SI" in t for t in decision_texts)


# ═══════════════════════════════════════════════════════════════════════════
# 4b. observe
# ═══════════════════════════════════════════════════════════════════════════


class TestObserve:
    def test_observe_sessions_filters_by_command(self) -> None:
        _invoke(
            "--raw",
            "observe",
            "event",
            "cli",
            "command",
            "--action",
            "start",
            "--status",
            "active",
            "--command",
            "timestamp",
        )
        result = _invoke("--raw", "observe", "sessions", "--command", "timestamp")
        parsed = json.loads(result.output)
        assert parsed["count"] >= 1
        assert all(session["command"] == "timestamp" for session in parsed["sessions"])

    def test_observe_show_filters_by_session(self) -> None:
        event_result = _invoke(
            "--raw",
            "observe",
            "event",
            "cli",
            "command",
            "--action",
            "start",
            "--status",
            "active",
            "--command",
            "timestamp",
        )
        event_payload = json.loads(event_result.output)
        sessions = json.loads(_invoke("--raw", "observe", "sessions", "--command", "timestamp").output)
        assert any(session["session_id"] == event_payload["session_id"] for session in sessions["sessions"])
        session_id = sessions["sessions"][0]["session_id"]
        result = _invoke("--raw", "observe", "show", "--session", session_id, "--category", "cli")
        parsed = json.loads(result.output)
        assert parsed["count"] >= 1
        assert all(event["session_id"] == session_id for event in parsed["events"])
        assert all(event["category"] == "cli" for event in parsed["events"])

    def test_observe_event_writes_custom_event(self) -> None:
        result = _invoke(
            "--raw",
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
            "01",
            "--plan",
            "01",
            "--data",
            '{"wave": 1}',
        )
        parsed = json.loads(result.output)
        assert parsed["category"] == "workflow"
        assert parsed["name"] == "wave-start"
        observed = json.loads(_invoke("--raw", "observe", "show", "--category", "workflow", "--name", "wave-start").output)
        assert observed["count"] >= 1
        assert any(event.get("data", {}).get("wave") == 1 for event in observed["events"])


class TestFrontmatterValidate:
    def test_frontmatter_validate_invalid_schema_returns_exit_code_one(self, gpd_project: Path) -> None:
        summary = gpd_project / "invalid-summary.md"
        summary.write_text(
            "---\nphase: '01'\nplan: '01'\n---\n\n# Summary\n",
            encoding="utf-8",
        )

        result = _invoke(
            "--raw",
            "frontmatter",
            "validate",
            str(summary.relative_to(gpd_project)),
            "--schema",
            "summary",
            expect_ok=False,
        )

        assert result.exit_code == 1
        payload = json.loads(result.output)
        assert payload["valid"] is False
        assert sorted(payload["missing"]) == ["completed", "depth", "provides"]


# ═══════════════════════════════════════════════════════════════════════════
# 5. init include parsing + command-context surface
# ═══════════════════════════════════════════════════════════════════════════


class TestInitIncludeParsing:
    def test_init_progress_include_trims_whitespace_and_drops_empty_entries(self) -> None:
        result = _invoke("--raw", "init", "progress", "--include", " state, roadmap, , ")
        payload = json.loads(result.output)

        assert payload["state_content"] is not None
        assert payload["roadmap_content"] is not None

    def test_init_progress_include_rejects_unknown_values(self) -> None:
        result = _invoke("--raw", "init", "progress", "--include", "state, bogus", expect_ok=False)

        assert result.exit_code == 1
        payload = json.loads(result.output)
        assert payload["error"] == (
            "Unknown --include value(s) for gpd init progress: bogus. "
            "Allowed values: config, project, roadmap, state."
        )

    def test_init_resume_is_read_only_and_returns_ranked_candidates(self, gpd_project: Path) -> None:
        planning = gpd_project / "GPD"
        phase_dir = planning / "phases" / "01-test-phase"
        live_resume = phase_dir / ".continue-here.md"
        handoff_resume = phase_dir / "alternate.md"
        live_resume.write_text("resume\n", encoding="utf-8")
        handoff_resume.write_text("alternate\n", encoding="utf-8")

        _invoke(
            "state",
            "record-session",
            "--stopped-at",
            "Paused in phase 01",
            "--resume-file",
            "GPD/phases/01-test-phase/alternate.md",
        )

        observability = planning / "observability"
        observability.mkdir(parents=True, exist_ok=True)
        (observability / "current-execution.json").write_text(
            json.dumps(
                {
                    "session_id": "sess-1",
                    "phase": "01",
                    "plan": "02",
                    "segment_id": "seg-4",
                    "segment_status": "paused",
                    "resume_file": "GPD/phases/01-test-phase/.continue-here.md",
                    "updated_at": "2026-03-10T12:00:00+00:00",
                }
            ),
            encoding="utf-8",
        )
        (planning / AGENT_ID_FILENAME).write_text("agent-77\n", encoding="utf-8")
        snapshot_before = _target_file_snapshot(planning)

        result = _invoke("--raw", "init", "resume")
        payload = json.loads(result.output)

        assert payload["resume_mode"] == "bounded_segment"
        assert payload["execution_resumable"] is True
        assert payload["execution_resume_file_source"] == "current_execution"
        assert payload["execution_resume_file"] == "GPD/phases/01-test-phase/.continue-here.md"
        assert payload["session_resume_file"] == "GPD/phases/01-test-phase/alternate.md"
        assert payload["has_interrupted_agent"] is True
        assert [candidate["source"] for candidate in payload["segment_candidates"]] == [
            "current_execution",
            "session_resume_file",
            "interrupted_agent",
        ]
        assert payload["segment_candidates"][0]["resume_file"] == "GPD/phases/01-test-phase/.continue-here.md"
        assert payload["segment_candidates"][1]["resume_file"] == "GPD/phases/01-test-phase/alternate.md"
        assert payload["segment_candidates"][2]["agent_id"] == "agent-77"
        assert _target_file_snapshot(planning) == snapshot_before

    def test_observe_execution_reports_waiting_without_marking_it_possibly_stalled(self, gpd_project: Path) -> None:
        observability = gpd_project / "GPD" / "observability"
        observability.mkdir(parents=True, exist_ok=True)
        (observability / "current-execution.json").write_text(
            json.dumps(
                {
                    "session_id": "sess-1",
                    "phase": "04",
                    "plan": "03",
                    "segment_status": "waiting_review",
                    "checkpoint_reason": "first_result",
                    "waiting_for_review": True,
                    "first_result_gate_pending": True,
                    "updated_at": "2000-01-01T00:00:00+00:00",
                }
            ),
            encoding="utf-8",
        )

        result = _invoke("--raw", "observe", "execution")
        payload = json.loads(result.output)

        assert payload["found"] is True
        assert payload["status_classification"] == "waiting"
        assert payload["assessment"] == "waiting"
        assert payload["possibly_stalled"] is False
        assert payload["review_reason"] == "first-result review pending"

    def test_observe_execution_treats_awaiting_user_as_paused_or_resumable(self, gpd_project: Path) -> None:
        observability = gpd_project / "GPD" / "observability"
        observability.mkdir(parents=True, exist_ok=True)
        (observability / "current-execution.json").write_text(
            json.dumps(
                {
                    "session_id": "sess-2",
                    "phase": "04",
                    "plan": "04",
                    "segment_status": "awaiting_user",
                    "resume_file": "GPD/phases/04-test-phase/.continue-here.md",
                    "updated_at": "2000-01-01T00:00:00+00:00",
                }
            ),
            encoding="utf-8",
        )

        result = _invoke("--raw", "observe", "execution")
        payload = json.loads(result.output)

        assert payload["found"] is True
        assert payload["status_classification"] == "paused-or-resumable"
        assert payload["assessment"] == "paused or resumable"
        assert payload["possibly_stalled"] is False

    def test_observe_execution_without_snapshot_reports_idle(self, gpd_project: Path) -> None:
        result = _invoke("--raw", "observe", "execution")
        payload = json.loads(result.output)

        assert payload["found"] is False
        assert payload["status_classification"] == "idle"
        assert payload["assessment"] == "idle"
        assert payload["possibly_stalled"] is False


class TestCommandContextSurface:
    def test_validate_command_context_reports_runtime_command_surface(self, codex_command_prefix: str) -> None:
        result = _invoke("--raw", "validate", "command-context", "gpd:settings")
        payload = json.loads(result.output)

        assert payload["command"] == "gpd:settings"
        assert payload["validated_surface"] == "public_runtime_dollar_command"
        assert payload["local_cli_equivalence_guaranteed"] is False
        assert f"public `{codex_command_prefix}*` runtime command surface" in payload["dispatch_note"]
        assert "same-name local `gpd` subcommand" in payload["dispatch_note"]

    def test_validate_command_context_reports_slash_runtime_surface(
        self, claude_code_command_prefix: str
    ) -> None:
        result = _invoke("--raw", "validate", "command-context", "gpd:settings")
        payload = json.loads(result.output)

        assert payload["command"] == "gpd:settings"
        assert payload["validated_surface"] == "public_runtime_slash_command"
        assert payload["local_cli_equivalence_guaranteed"] is False
        assert f"public `{claude_code_command_prefix}*` runtime command surface" in payload["dispatch_note"]
        assert "same-name local `gpd` subcommand" in payload["dispatch_note"]

    def test_validate_command_context_falls_back_when_runtime_resolution_fails(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _raise_runtime_error(cwd=None) -> str:
            raise RuntimeError("runtime resolution failed")

        monkeypatch.setattr("gpd.cli.detect_runtime_for_gpd_use", _raise_runtime_error)

        result = _invoke("--raw", "validate", "command-context", "gpd:settings")
        payload = json.loads(result.output)

        assert payload["command"] == "gpd:settings"
        assert payload["validated_surface"] == "public_runtime_command_surface"
        assert payload["local_cli_equivalence_guaranteed"] is False
        assert "the active runtime command surface" in payload["dispatch_note"]


# ═══════════════════════════════════════════════════════════════════════════
# 6. regression-check
# ═══════════════════════════════════════════════════════════════════════════


class TestRegressionCheck:
    def test_regression_check_passing(self) -> None:
        """No completed phases with conflicting conventions => pass."""
        result = _invoke("regression-check")
        assert result.exit_code == 0

    def test_regression_check_raw(self) -> None:
        result = _invoke("--raw", "regression-check")
        parsed = json.loads(result.output)
        assert "passed" in parsed
        assert "issues" in parsed
        assert "phases_checked" in parsed

    def test_regression_check_quick(self) -> None:
        result = _invoke("regression-check", "--quick")
        assert result.exit_code == 0

    def test_regression_check_phase_scope(self, gpd_project: Path) -> None:
        p2 = gpd_project / "GPD" / "phases" / "02-phase-two"
        (p2 / "01-PLAN.md").write_text("---\nphase: '02'\n---\n# Plan\n")
        (p2 / "01-SUMMARY.md").write_text(
            '---\nphase: "02"\nplan: "01"\n'
            "conventions:\n  metric: (+,-,-,-)\n"
            "---\n\n# Summary\n"
        )

        result = _invoke("--raw", "regression-check", "1")
        parsed = json.loads(result.output)
        assert result.exit_code == 0
        assert parsed["passed"] is True
        assert parsed["phases_checked"] == 1

    def test_regression_check_detects_conflict(self, gpd_project: Path) -> None:
        """Inject a convention conflict across two completed phases."""
        p2 = gpd_project / "GPD" / "phases" / "02-phase-two"

        # Make phase 2 look completed with a conflicting convention
        (p2 / "01-PLAN.md").write_text("---\nphase: '02'\n---\n# Plan\n")
        (p2 / "01-SUMMARY.md").write_text(
            '---\nphase: "02"\nplan: "01"\n'
            "conventions:\n  metric: (+,-,-,-)\n"
            "---\n\n# Summary\n"
        )

        result = runner.invoke(app, ["--raw", "regression-check"], catch_exceptions=False)
        parsed = json.loads(result.output)
        # Both phases are now completed (have plan+summary), with conflicting metric
        assert not parsed["passed"], "Expected regression check to detect convention conflict"
        issues = parsed["issues"]
        conflict_types = [i["type"] for i in issues]
        assert "convention_conflict" in conflict_types


# ═══════════════════════════════════════════════════════════════════════════
# 6. validate-return
# ═══════════════════════════════════════════════════════════════════════════


class TestValidateReturn:
    def test_validate_return_valid(self, gpd_project: Path) -> None:
        """A file with a valid gpd_return block should pass."""
        return_file = gpd_project / "valid_return.md"
        return_file.write_text(
            "# Summary\n\n```yaml\ngpd_return:\n"
            '  status: completed\n  files_written: ["src/main.py"]\n'
            "  issues: []\n"
            '  next_actions: ["/gpd:verify-work 01"]\n'
            "  duration_seconds: 120\n```\n"
        )
        result = _invoke("--raw", "validate-return", str(return_file))
        parsed = json.loads(result.output)
        assert parsed["passed"] is True
        assert len(parsed["errors"]) == 0

    def test_validate_return_missing_fields(self, gpd_project: Path) -> None:
        """A file with missing required fields should fail."""
        return_file = gpd_project / "incomplete_return.md"
        return_file.write_text(
            "# Summary\n\n```yaml\ngpd_return:\n"
            '  status: completed\n```\n'
        )
        result = runner.invoke(
            app,
            ["--raw", "validate-return", str(return_file)],
            catch_exceptions=False,
        )
        assert result.exit_code == 1
        parsed = json.loads(result.output)
        assert parsed["passed"] is False
        assert len(parsed["errors"]) > 0

    def test_validate_return_no_block(self, gpd_project: Path) -> None:
        """A file without a gpd_return block should fail."""
        return_file = gpd_project / "no_block.md"
        return_file.write_text("# Just a regular file\n\nNo return block here.\n")
        result = runner.invoke(
            app,
            ["--raw", "validate-return", str(return_file)],
            catch_exceptions=False,
        )
        assert result.exit_code == 1
        parsed = json.loads(result.output)
        assert parsed["passed"] is False
        assert any("No gpd_return" in e for e in parsed["errors"])

    def test_validate_return_invalid_status(self, gpd_project: Path) -> None:
        """A file with an invalid status should report errors."""
        return_file = gpd_project / "bad_status.md"
        return_file.write_text(
            "# Summary\n\n```yaml\ngpd_return:\n"
            '  status: banana\n  files_written: ["src/main.py"]\n'
            "  issues: []\n"
            '  next_actions: ["/gpd:verify-work 01"]\n```\n'
        )
        result = runner.invoke(
            app,
            ["--raw", "validate-return", str(return_file)],
            catch_exceptions=False,
        )
        assert result.exit_code == 1
        parsed = json.loads(result.output)
        assert parsed["passed"] is False
        assert any("Invalid status" in e for e in parsed["errors"])

    def test_validate_return_warnings(self, gpd_project: Path) -> None:
        """Missing recommended fields should produce warnings, not errors."""
        return_file = gpd_project / "warns.md"
        return_file.write_text(
            "# Summary\n\n```yaml\ngpd_return:\n"
            '  status: completed\n  files_written: ["src/main.py"]\n'
            "  issues: []\n"
            '  next_actions: ["/gpd:verify-work 01"]\n```\n'
        )
        result = _invoke("--raw", "validate-return", str(return_file))
        parsed = json.loads(result.output)
        assert parsed["passed"] is True
        assert parsed["warning_count"] > 0


# ═══════════════════════════════════════════════════════════════════════════
# 7. config subcommands
# ═══════════════════════════════════════════════════════════════════════════


class TestConfigCommands:
    def test_config_get_existing_key(self) -> None:
        result = _invoke("--raw", "config", "get", "autonomy")
        parsed = json.loads(result.output)
        assert parsed["found"] is True
        assert parsed["value"] == "yolo"

    def test_config_get_missing_key(self) -> None:
        result = _invoke("--raw", "config", "get", "nonexistent")
        parsed = json.loads(result.output)
        assert parsed["found"] is False

    def test_config_get_alias_key_reads_effective_value(self, gpd_project: Path) -> None:
        """Alias keys should resolve through the canonical config surface."""
        config_path = gpd_project / "GPD" / "config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["commit_docs"] = False
        config_path.write_text(json.dumps(config), encoding="utf-8")

        result = _invoke("--raw", "config", "get", "planning.commit_docs")
        parsed = json.loads(result.output)
        assert parsed["found"] is True
        assert parsed["value"] is False

    def test_config_get_returns_defaults_when_config_is_missing(self, gpd_project: Path) -> None:
        (gpd_project / "GPD" / "config.json").unlink()

        result = _invoke("--raw", "config", "get", "autonomy")
        parsed = json.loads(result.output)

        assert parsed["found"] is True
        assert parsed["value"] == "balanced"

    def test_config_set_rejects_unsupported_key(self, gpd_project: Path) -> None:
        result = _invoke("--raw", "config", "set", "new_key", "new_value", expect_ok=False)
        parsed = json.loads(result.output)
        assert "Unsupported config key" in parsed["error"]

        config = json.loads((gpd_project / "GPD" / "config.json").read_text(encoding="utf-8"))
        assert "new_key" not in config

    def test_config_set_nested_alias_updates_canonical_value(self, gpd_project: Path) -> None:
        _invoke("--raw", "config", "set", "planning.commit_docs", "false")
        config = json.loads((gpd_project / "GPD" / "config.json").read_text(encoding="utf-8"))
        assert config["commit_docs"] is False
        assert "planning" not in config

        get_result = _invoke("--raw", "config", "get", "planning.commit_docs")
        parsed = json.loads(get_result.output)
        assert parsed["found"] is True
        assert parsed["value"] is False

    def test_config_set_json_value(self, gpd_project: Path) -> None:
        """Setting a JSON value (e.g. integer, boolean) should parse it."""
        _invoke("config", "set", "parallelization", "false")
        config = json.loads((gpd_project / "GPD" / "config.json").read_text(encoding="utf-8"))
        assert config["parallelization"] is False

    def test_config_set_rejects_legacy_autonomy_value(self, gpd_project: Path) -> None:
        result = _invoke("--raw", "config", "set", "autonomy", "guided", expect_ok=False)

        parsed = json.loads(result.output)
        assert "Invalid config.json values" in parsed["error"]

        config = json.loads((gpd_project / "GPD" / "config.json").read_text(encoding="utf-8"))
        assert config["autonomy"] == "yolo"

    def test_config_ensure_section_exists(self) -> None:
        """ensure-section with existing config.json should report created=False."""
        result = _invoke("--raw", "config", "ensure-section")
        parsed = json.loads(result.output)
        assert parsed["created"] is False

    def test_config_ensure_section_creates(self, gpd_project: Path) -> None:
        """ensure-section without config.json should create defaults."""
        (gpd_project / "GPD" / "config.json").unlink()
        result = _invoke("--raw", "config", "ensure-section")
        parsed = json.loads(result.output)
        assert parsed["created"] is True
        config_path = gpd_project / "GPD" / "config.json"
        assert config_path.exists()
        config = json.loads(config_path.read_text())
        assert config["autonomy"] == "balanced"
        assert config["execution"]["review_cadence"] == "adaptive"
        assert config["research_mode"] == "balanced"
        assert config["parallelization"] is True
        assert config["workflow"]["plan_checker"] is True
        assert config["git"]["branching_strategy"] == "none"
        assert "brave_search" not in config
        assert "search_gitignored" not in config

    def test_permissions_sync_updates_installed_runtime(self, gpd_project: Path) -> None:
        adapter, target = _install_runtime(gpd_project, _ENV_OVERRIDE_DESCRIPTOR)

        result = _invoke("--raw", "permissions", "sync", "--runtime", _ENV_OVERRIDE_DESCRIPTOR.runtime_name, "--autonomy", "yolo")
        parsed = json.loads(result.output)
        status = adapter.runtime_permissions_status(target, autonomy="yolo")

        assert parsed["runtime"] == _ENV_OVERRIDE_DESCRIPTOR.runtime_name
        assert parsed["sync_applied"] is True
        assert status["config_aligned"] is True

    def test_permissions_sync_then_unattended_readiness_surfaces_composed_relaunch_required_verdict(
        self,
        gpd_project: Path,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        _install_runtime(gpd_project, _ENV_OVERRIDE_DESCRIPTOR)
        _expose_runtime_launcher(monkeypatch, tmp_path, _ENV_OVERRIDE_DESCRIPTOR)

        sync_result = _invoke(
            "--raw",
            "permissions",
            "sync",
            "--runtime",
            _ENV_OVERRIDE_DESCRIPTOR.runtime_name,
            "--autonomy",
            "yolo",
        )
        sync_payload = json.loads(sync_result.output)

        status_result = _invoke(
            "--raw",
            "validate",
            "unattended-readiness",
            "--runtime",
            _ENV_OVERRIDE_DESCRIPTOR.runtime_name,
            "--autonomy",
            "yolo",
            expect_ok=False,
        )
        status_payload = json.loads(status_result.output)

        assert sync_payload["runtime"] == _ENV_OVERRIDE_DESCRIPTOR.runtime_name
        assert sync_payload["sync_applied"] is True
        assert status_result.exit_code == 1
        assert status_payload["runtime"] == _ENV_OVERRIDE_DESCRIPTOR.runtime_name
        assert status_payload["readiness"] == "relaunch-required"
        assert status_payload["ready"] is False
        assert status_payload["passed"] is False
        assert status_payload["checks"][0]["name"] == "permissions"
        assert status_payload["checks"][0]["passed"] is False
        assert status_payload["checks"][1]["name"] == "doctor"
        assert status_payload["checks"][1]["passed"] is True
        assert status_payload["readiness_message"] == (
            "Runtime permissions are aligned, but the runtime must be relaunched before unattended use."
        )
        next_step = str(status_payload["next_step"]).lower()
        assert "restart" in next_step or "relaunch" in next_step

    def test_permissions_sync_accepts_display_name_runtime(self, gpd_project: Path) -> None:
        adapter, target = _install_runtime(gpd_project, _ENV_OVERRIDE_DESCRIPTOR)

        result = _invoke("--raw", "permissions", "sync", "--runtime", _ENV_OVERRIDE_DESCRIPTOR.display_name, "--autonomy", "yolo")
        parsed = json.loads(result.output)
        status = adapter.runtime_permissions_status(target, autonomy="yolo")

        assert parsed["runtime"] == _ENV_OVERRIDE_DESCRIPTOR.runtime_name
        assert parsed["sync_applied"] is True
        assert status["config_aligned"] is True

    def test_permissions_sync_accepts_alias_runtime(self, gpd_project: Path) -> None:
        adapter, target = _install_runtime(gpd_project, _ENV_OVERRIDE_DESCRIPTOR)
        alias = _ENV_OVERRIDE_DESCRIPTOR.selection_aliases[0]

        result = _invoke("--raw", "permissions", "sync", "--runtime", alias, "--autonomy", "yolo")
        parsed = json.loads(result.output)
        status = adapter.runtime_permissions_status(target, autonomy="yolo")

        assert parsed["runtime"] == _ENV_OVERRIDE_DESCRIPTOR.runtime_name
        assert parsed["sync_applied"] is True
        assert status["config_aligned"] is True

    def test_permissions_status_and_sync_use_explicit_local_install_target(
        self,
        gpd_project: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        target = gpd_project / "external" / f"{_ENV_OVERRIDE_DESCRIPTOR.config_dir_name.lstrip('.')}-config"
        adapter, target = _install_runtime(gpd_project, _ENV_OVERRIDE_DESCRIPTOR, target=target, explicit_target=True)
        _set_runtime_config_override(monkeypatch, _ENV_OVERRIDE_DESCRIPTOR, target)

        status_result = _invoke("--raw", "permissions", "status", "--runtime", _ENV_OVERRIDE_DESCRIPTOR.runtime_name)
        parsed_status = json.loads(status_result.output)
        expected_status = adapter.runtime_permissions_status(target, autonomy="yolo")
        doctor_result = _invoke(
            "--raw",
            "doctor",
            "--runtime",
            _ENV_OVERRIDE_DESCRIPTOR.runtime_name,
            "--target-dir",
            str(target),
        )
        parsed_doctor = json.loads(doctor_result.output)
        runtime_target_check = next(
            check for check in parsed_doctor["checks"] if check["label"] == "Runtime Config Target"
        )

        assert parsed_status["runtime"] == _ENV_OVERRIDE_DESCRIPTOR.runtime_name
        assert parsed_status["target"] == str(target)
        assert parsed_status["settings_path"] == expected_status["settings_path"]
        assert parsed_doctor["target"] == str(target)
        assert runtime_target_check["details"]["target"] == str(target)

        sync_result = _invoke("--raw", "permissions", "sync", "--runtime", _ENV_OVERRIDE_DESCRIPTOR.runtime_name, "--autonomy", "yolo")
        parsed_sync = json.loads(sync_result.output)
        synced_status = adapter.runtime_permissions_status(target, autonomy="yolo")

        assert parsed_sync["runtime"] == _ENV_OVERRIDE_DESCRIPTOR.runtime_name
        assert parsed_sync["target"] == str(target)
        assert parsed_sync["sync_applied"] is True
        assert synced_status["config_aligned"] is True

    def test_permissions_status_distinguishes_absent_install_from_owned_incomplete_install(
        self,
        gpd_project: Path,
    ) -> None:
        fake_home = gpd_project / "_fake_home_permissions_resolution"
        fake_home.mkdir()

        with patch("pathlib.Path.home", return_value=fake_home):
            absent_result = _invoke(
                "--raw",
                "permissions",
                "status",
                "--runtime",
                _ENV_OVERRIDE_DESCRIPTOR.runtime_name,
                "--autonomy",
                "balanced",
                expect_ok=False,
            )
            absent_payload = json.loads(absent_result.output)
            assert absent_result.exit_code == 1
            assert absent_payload["error"] == (
                f"No GPD install found for runtime '{_ENV_OVERRIDE_DESCRIPTOR.runtime_name}'. "
                f"Run `gpd install {_ENV_OVERRIDE_DESCRIPTOR.runtime_name}` first."
            )

            adapter, target = _install_runtime(gpd_project, _ENV_OVERRIDE_DESCRIPTOR)
            _break_install_completeness(target, adapter)

            incomplete_result = _invoke(
                "--raw",
                "permissions",
                "status",
                "--runtime",
                _ENV_OVERRIDE_DESCRIPTOR.runtime_name,
                "--autonomy",
                "balanced",
                expect_ok=False,
            )
            incomplete_payload = json.loads(incomplete_result.output)

        assert incomplete_result.exit_code == 1
        assert incomplete_payload["error"] != absent_payload["error"]
        assert "No GPD install found" not in incomplete_payload["error"]
        assert "incomplete" in incomplete_payload["error"].lower() or "repair" in incomplete_payload["error"].lower()

    def test_permissions_status_uses_public_adapter_target_validation_contract(
        self,
        gpd_project: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import gpd.adapters as adapters_module

        descriptor = _DOLLAR_COMMAND_DESCRIPTOR
        target = gpd_project / "external" / f"{descriptor.runtime_name}-config"
        target.mkdir(parents=True)
        validation_calls: list[tuple[Path, str]] = []

        class _FakeAdapter:
            runtime_name = descriptor.runtime_name
            display_name = descriptor.display_name

            def validate_target_runtime(self, target_dir: Path, *, action: str) -> None:
                validation_calls.append((target_dir, action))

            def has_complete_install(self, target_dir: Path) -> bool:
                return True

            def runtime_permissions_status(self, target_dir: Path, *, autonomy: str) -> dict[str, object]:
                return {
                    "runtime": descriptor.runtime_name,
                    "desired_mode": "default",
                    "configured_mode": "default",
                    "config_aligned": True,
                    "requires_relaunch": False,
                    "managed_by_gpd": False,
                    "message": f"validated {target_dir.name} for {autonomy}",
                }

        monkeypatch.setattr(adapters_module, "get_adapter", lambda runtime_name: _FakeAdapter())

        result = _invoke(
            "--raw",
            "permissions",
            "status",
            "--runtime",
            descriptor.runtime_name,
            "--target-dir",
            str(target),
            "--autonomy",
            "balanced",
        )
        parsed = json.loads(result.output)

        assert validation_calls == [(target.resolve(strict=False), "inspect runtime permissions on")]
        assert parsed["runtime"] == descriptor.runtime_name
        assert parsed["target"] == str(target.resolve(strict=False))
        assert parsed["message"] == f"validated {target.name} for balanced"

    def test_permissions_status_marks_unaligned_runtime_not_ready(self, gpd_project: Path) -> None:
        _install_runtime(gpd_project, _ENV_OVERRIDE_DESCRIPTOR)

        result = _invoke(
            "--raw",
            "permissions",
            "status",
            "--runtime",
            _ENV_OVERRIDE_DESCRIPTOR.runtime_name,
            "--autonomy",
            "yolo",
        )
        parsed = json.loads(result.output)

        assert parsed["runtime"] == _ENV_OVERRIDE_DESCRIPTOR.runtime_name
        assert parsed["config_aligned"] is False
        assert parsed["readiness"] == "not-ready"
        assert parsed["ready"] is False
        assert parsed["readiness_message"] == (
            "Runtime permissions are not ready for unattended use under the requested autonomy."
        )

    def test_permissions_status_marks_default_runtime_ready(self, gpd_project: Path) -> None:
        _install_runtime(gpd_project, _ENV_OVERRIDE_DESCRIPTOR)

        result = _invoke(
            "--raw",
            "permissions",
            "status",
            "--runtime",
            _ENV_OVERRIDE_DESCRIPTOR.runtime_name,
            "--autonomy",
            "balanced",
        )
        parsed = json.loads(result.output)

        assert parsed["runtime"] == _ENV_OVERRIDE_DESCRIPTOR.runtime_name
        assert parsed["config_aligned"] is True
        assert parsed["readiness"] == "ready"
        assert parsed["ready"] is True
        assert parsed["readiness_message"] == "Runtime permissions are ready for unattended use."

    def test_permissions_status_marks_synced_yolo_runtime_relaunch_required(self, gpd_project: Path) -> None:
        adapter, target = _install_runtime(gpd_project, _ENV_OVERRIDE_DESCRIPTOR)
        adapter.sync_runtime_permissions(target, autonomy="yolo")

        result = _invoke(
            "--raw",
            "permissions",
            "status",
            "--runtime",
            _ENV_OVERRIDE_DESCRIPTOR.runtime_name,
            "--autonomy",
            "yolo",
        )
        parsed = json.loads(result.output)

        assert parsed["runtime"] == _ENV_OVERRIDE_DESCRIPTOR.runtime_name
        assert parsed["target"] == str(target)
        assert parsed["config_aligned"] is True
        assert parsed["requires_relaunch"] is True
        assert parsed["readiness"] == "relaunch-required"
        assert parsed["ready"] is False
        assert parsed["readiness_message"] == (
            "Runtime permissions are aligned, but the runtime must be relaunched before unattended use."
        )
        assert parsed["next_step"]

    @pytest.mark.parametrize("command", ["status", "sync"])
    def test_permissions_reject_foreign_manifest_target(
        self,
        gpd_project: Path,
        command: str,
    ) -> None:
        _, target = _install_runtime(gpd_project, _ENV_OVERRIDE_DESCRIPTOR)
        snapshot_before = _target_file_snapshot(target)
        action = "sync" if command == "sync" else "inspect"

        result = _invoke(
            "--raw",
            "permissions",
            command,
            "--runtime",
            _SECONDARY_PERMISSIONS_DESCRIPTOR.runtime_name,
            "--target-dir",
            str(target),
            "--autonomy",
            "yolo",
            expect_ok=False,
        )
        parsed = json.loads(result.output)

        assert result.exit_code == 1
        assert parsed["error"].startswith(f"Refusing to {action} runtime permissions on")
        assert f"`{_ENV_OVERRIDE_DESCRIPTOR.runtime_name}`" in parsed["error"]
        assert f"`{_SECONDARY_PERMISSIONS_DESCRIPTOR.runtime_name}`" in parsed["error"]
        assert _target_file_snapshot(target) == snapshot_before

    def test_config_set_autonomy_attempts_runtime_permission_sync(
        self,
        gpd_project: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        adapter, target = _install_runtime(gpd_project, _ENV_OVERRIDE_DESCRIPTOR)
        adapter.sync_runtime_permissions(target, autonomy="yolo")
        monkeypatch.setenv("GPD_ACTIVE_RUNTIME", _ENV_OVERRIDE_DESCRIPTOR.runtime_name)

        result = _invoke("--raw", "config", "set", "autonomy", "balanced")
        parsed = json.loads(result.output)
        status = adapter.runtime_permissions_status(target, autonomy="balanced")

        assert parsed["value"] == "balanced"
        assert parsed["runtime_permissions"]["runtime"] == _ENV_OVERRIDE_DESCRIPTOR.runtime_name
        assert parsed["runtime_permissions"]["sync_applied"] is True
        assert status["config_aligned"] is True

    def test_permissions_sync_prefers_active_runtime_over_other_installed_runtime(
        self,
        gpd_project: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _, target = _install_runtime(gpd_project, _SECONDARY_PERMISSIONS_DESCRIPTOR)
        fake_home = gpd_project / "_fake_home_permissions"
        fake_home.mkdir()
        _activate_runtime(monkeypatch, _ENV_OVERRIDE_DESCRIPTOR)
        snapshot_before = _target_file_snapshot(target)

        with patch("pathlib.Path.home", return_value=fake_home):
            result = _invoke("--raw", "permissions", "sync", "--autonomy", "yolo", expect_ok=False)

        parsed = json.loads(result.output)

        assert parsed["error"] == (
            f"No GPD install found for runtime '{_ENV_OVERRIDE_DESCRIPTOR.runtime_name}'. "
            f"Run `gpd install {_ENV_OVERRIDE_DESCRIPTOR.runtime_name}` first."
        )
        assert _target_file_snapshot(target) == snapshot_before

    def test_config_set_autonomy_does_not_sync_other_installed_runtime(
        self,
        gpd_project: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _, target = _install_runtime(gpd_project, _SECONDARY_PERMISSIONS_DESCRIPTOR)
        fake_home = gpd_project / "_fake_home_config_set"
        fake_home.mkdir()
        _activate_runtime(monkeypatch, _ENV_OVERRIDE_DESCRIPTOR)
        snapshot_before = _target_file_snapshot(target)

        with patch("pathlib.Path.home", return_value=fake_home):
            result = _invoke("--raw", "config", "set", "autonomy", "yolo")

        parsed = json.loads(result.output)

        assert parsed["value"] == "yolo"
        assert parsed["runtime_permissions"]["runtime"] == _ENV_OVERRIDE_DESCRIPTOR.runtime_name
        assert parsed["runtime_permissions"]["sync_applied"] is False
        assert parsed["runtime_permissions"]["changed"] is False
        assert parsed["runtime_permissions"]["message"] == (
            f"No GPD install found for runtime '{_ENV_OVERRIDE_DESCRIPTOR.runtime_name}'. "
            f"Run `gpd install {_ENV_OVERRIDE_DESCRIPTOR.runtime_name}` first."
        )
        assert _target_file_snapshot(target) == snapshot_before

    def test_config_help(self) -> None:
        result = _invoke("config", "--help")
        assert "get" in result.output
        assert "set" in result.output


# ═══════════════════════════════════════════════════════════════════════════
# 8. json subcommands
# ═══════════════════════════════════════════════════════════════════════════


class TestJsonCommands:
    def test_json_get(self) -> None:
        """json get should extract a value from stdin JSON."""
        input_json = json.dumps({"name": "physics", "version": 2})
        result = runner.invoke(
            app, ["json", "get", ".name"], input=input_json, catch_exceptions=False
        )
        assert result.exit_code == 0
        assert "physics" in result.output

    def test_json_get_nested(self) -> None:
        input_json = json.dumps({"a": {"b": {"c": "deep"}}})
        result = runner.invoke(
            app, ["json", "get", ".a.b.c"], input=input_json, catch_exceptions=False
        )
        assert result.exit_code == 0
        assert "deep" in result.output

    def test_json_get_default(self) -> None:
        input_json = json.dumps({"name": "physics"})
        result = runner.invoke(
            app,
            ["json", "get", ".missing", "--default", "fallback"],
            input=input_json,
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        assert "fallback" in result.output

    def test_json_keys(self) -> None:
        input_json = json.dumps({"waves": {"w1": 1, "w2": 2, "w3": 3}})
        result = runner.invoke(
            app, ["json", "keys", ".waves"], input=input_json, catch_exceptions=False
        )
        assert result.exit_code == 0
        assert "w1" in result.output
        assert "w2" in result.output
        assert "w3" in result.output

    def test_json_list(self) -> None:
        input_json = json.dumps({"items": ["alpha", "beta", "gamma"]})
        result = runner.invoke(
            app, ["json", "list", ".items"], input=input_json, catch_exceptions=False
        )
        assert result.exit_code == 0
        assert "alpha" in result.output
        assert "beta" in result.output
        assert "gamma" in result.output

    def test_json_pluck(self) -> None:
        input_json = json.dumps(
            {"phases": [{"name": "setup"}, {"name": "compute"}, {"name": "verify"}]}
        )
        result = runner.invoke(
            app,
            ["json", "pluck", ".phases", "name"],
            input=input_json,
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        assert "setup" in result.output
        assert "compute" in result.output
        assert "verify" in result.output

    def test_json_set(self, gpd_project: Path) -> None:
        target = str(gpd_project / "test_output.json")
        result = _invoke("json", "set", "--file", target, "--path", ".key", "--value", '"hello"')
        assert result.exit_code == 0
        data = json.loads(Path(target).read_text())
        assert data["key"] == "hello"

    def test_json_set_nested(self, gpd_project: Path) -> None:
        target = str(gpd_project / "test_nested.json")
        _invoke("json", "set", "--file", target, "--path", ".a.b", "--value", "42")
        data = json.loads(Path(target).read_text())
        assert data["a"]["b"] == 42

    def test_json_merge_files(self, gpd_project: Path) -> None:
        f1 = gpd_project / "merge1.json"
        f2 = gpd_project / "merge2.json"
        out = gpd_project / "merged.json"
        f1.write_text(json.dumps({"a": 1, "b": 2}))
        f2.write_text(json.dumps({"c": 3, "d": 4}))
        result = _invoke(
            "--raw",
            "json",
            "merge-files",
            str(f1),
            str(f2),
            "--out",
            str(out),
        )
        parsed = json.loads(result.output)
        assert parsed["merged"] == 2
        merged_data = json.loads(out.read_text())
        assert merged_data == {"a": 1, "b": 2, "c": 3, "d": 4}

    def test_json_sum_lengths(self) -> None:
        input_json = json.dumps(
            {"items": [1, 2, 3], "tags": ["a", "b"]}
        )
        result = runner.invoke(
            app,
            ["json", "sum-lengths", ".items", ".tags"],
            input=input_json,
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        assert "5" in result.output

    def test_json_help(self) -> None:
        result = _invoke("json", "--help")
        assert "get" in result.output
        assert "keys" in result.output
        assert "list" in result.output
        assert "pluck" in result.output
        assert "set" in result.output


# ═══════════════════════════════════════════════════════════════════════════
# Extra coverage: summary-extract, resolve-model
# ═══════════════════════════════════════════════════════════════════════════

class TestSummaryExtractCommand:
    def test_summary_extract(self) -> None:
        result = _invoke(
            "--raw",
            "summary-extract",
            "GPD/phases/01-test-phase/01-SUMMARY.md",
        )
        parsed = json.loads(result.output)
        assert parsed["one_liner"] == "Set up project"
        assert "src/main.py" in parsed["key_files"]

    def test_summary_extract_with_field_filter(self) -> None:
        result = _invoke(
            "--raw",
            "summary-extract",
            "GPD/phases/01-test-phase/01-SUMMARY.md",
            "--field",
            "one_liner",
        )
        parsed = json.loads(result.output)
        assert "one_liner" in parsed
        assert parsed["one_liner"] == "Set up project"


class TestSyncPhaseCheckpointsCommand:
    def test_sync_phase_checkpoints(self, gpd_project: Path) -> None:
        phase_dir = gpd_project / "GPD" / "phases" / "01-test-phase"
        (phase_dir / "01-VERIFICATION.md").write_text("# Verification\n\nPassed.\n", encoding="utf-8")

        result = _invoke("--raw", "sync-phase-checkpoints")

        parsed = json.loads(result.output)
        assert parsed["phase_count"] == 1
        assert (gpd_project / "GPD" / "phase-checkpoints" / "01-test-phase.md").exists()
        assert (gpd_project / "GPD" / "CHECKPOINTS.md").exists()


class TestResolveModelCommand:
    def test_resolve_tier(self) -> None:
        result = _invoke("resolve-tier", "gpd-executor")
        assert result.output.strip() == "tier-2"

    def test_resolve_tier_rejects_unknown_agent(self) -> None:
        result = _invoke("--raw", "resolve-tier", "not-an-agent", expect_ok=False)
        parsed = json.loads(result.output)
        assert parsed["error"] == "Unknown agent 'not-an-agent'"

    @pytest.mark.parametrize("descriptor", _RUNTIME_DESCRIPTORS, ids=lambda descriptor: descriptor.runtime_name)
    def test_resolve_model_prefers_installed_runtime_override(self, gpd_project: Path, descriptor) -> None:
        config_path = gpd_project / "GPD" / "config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["model_overrides"] = {
            descriptor.runtime_name: {
                "tier-1": f"{descriptor.runtime_name}-planner-model",
                "tier-2": f"{descriptor.runtime_name}-executor-model",
            }
        }
        config_path.write_text(json.dumps(config), encoding="utf-8")
        seed_complete_runtime_install(gpd_project / descriptor.config_dir_name, runtime=descriptor.runtime_name)
        fake_home = gpd_project / "_fake_home"
        fake_home.mkdir()
        with patch("pathlib.Path.home", return_value=fake_home):
            result = _invoke("resolve-model", "gpd-executor")
            assert result.output.strip() == f"{descriptor.runtime_name}-executor-model"

            planner_result = _invoke("resolve-model", "gpd-planner")
            assert planner_result.output.strip() == f"{descriptor.runtime_name}-planner-model"

    @pytest.mark.parametrize("descriptor", _RUNTIME_DESCRIPTORS, ids=lambda descriptor: descriptor.runtime_name)
    def test_init_execute_phase_prefers_installed_runtime_for_model_fields(
        self,
        gpd_project: Path,
        descriptor,
    ) -> None:
        config_path = gpd_project / "GPD" / "config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["model_overrides"] = {
            descriptor.runtime_name: {
                "tier-1": f"{descriptor.runtime_name}-planner-model",
                "tier-2": f"{descriptor.runtime_name}-executor-model",
            }
        }
        config_path.write_text(json.dumps(config), encoding="utf-8")
        seed_complete_runtime_install(gpd_project / descriptor.config_dir_name, runtime=descriptor.runtime_name)

        fake_home = gpd_project / "_fake_home"
        fake_home.mkdir()
        with patch("pathlib.Path.home", return_value=fake_home):
            result = _invoke("--raw", "init", "execute-phase", "1")
            payload = json.loads(result.output)

            assert payload["executor_model"] == f"{descriptor.runtime_name}-executor-model"
            assert payload["verifier_model"] == f"{descriptor.runtime_name}-planner-model"

    def test_resolve_model_rejects_unknown_agent(self) -> None:
        result = _invoke(
            "--raw",
            "resolve-model",
            "not-an-agent",
            "--runtime",
            _RUNTIME_DESCRIPTORS[0].runtime_name,
            expect_ok=False,
        )
        parsed = json.loads(result.output)
        assert parsed["error"] == "Unknown agent 'not-an-agent'"


def test_cost_human_output_without_usage_ledger_stays_read_only_and_advisory(
    gpd_project: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data_root = tmp_path / "machine-data"
    monkeypatch.setenv(ENV_DATA_DIR, str(data_root))
    ledger_path = usage_ledger_path(data_root)
    config_path = gpd_project / "GPD" / "config.json"
    config_before = config_path.read_text(encoding="utf-8")

    result = _invoke("cost")
    normalized_output = " ".join(result.output.split())

    assert "Cost Summary" in result.output
    assert "Read-only machine-local usage/cost summary." in normalized_output
    assert "GPD reports measured telemetry when available" in normalized_output
    assert "clearly labels estimates or unavailable values." in normalized_output
    assert "Budget guardrails" in result.output
    assert "No optional USD budget guardrails are configured for this workspace." in result.output
    assert "Profile tier mix" in result.output
    assert "Advisory only; counts profile-to-tier assignments" in result.output
    assert "No measured usage telemetry is recorded for this workspace yet." in result.output
    assert not ledger_path.exists()
    assert config_path.read_text(encoding="utf-8") == config_before

def test_cost_raw_keeps_tokens_measured_but_usd_unavailable_without_pricing_snapshot(
    gpd_project: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data_root = tmp_path / "machine-data"
    monkeypatch.setenv(ENV_DATA_DIR, str(data_root))
    ledger_path = usage_ledger_path(data_root)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    workspace_root = gpd_project.resolve(strict=False).as_posix()
    record = UsageRecord(
        record_id="usage-1",
        recorded_at="2026-03-27T00:00:00+00:00",
        runtime="codex",
        provider="openai",
        model="gpt-5.4",
        session_id="session-1",
        workspace_root=workspace_root,
        project_root=workspace_root,
        usage_status="measured",
        cost_status="unavailable",
        input_tokens=1200,
        output_tokens=300,
        total_tokens=1500,
    )
    ledger_path.write_text(record.model_dump_json() + "\n", encoding="utf-8")
    ledger_before = ledger_path.read_text(encoding="utf-8")

    result = _invoke("--raw", "cost", "--last-sessions", "1")
    payload = json.loads(result.output)

    assert payload["project_root"] == workspace_root
    assert "workspace_root" not in payload
    assert payload["project"]["record_count"] == 1
    assert payload["project"]["usage_status"] == "measured"
    assert payload["project"]["cost_status"] == "unavailable"
    assert payload["project"]["interpretation"] == "tokens measured; USD unavailable"
    assert payload["project"]["total_tokens"] == 1500
    assert payload["project"]["cost_usd"] is None
    assert payload["profile_tier_mix"] == {"tier-1": 12, "tier-2": 10, "tier-3": 1}
    assert payload["profile_tier_mix_interpretation"].startswith("Advisory only; counts profile-to-tier assignments")
    assert payload["budget_thresholds"] == []
    assert payload["recent_sessions"][0]["session_id"] == "session-1"
    assert payload["recent_sessions"][0]["usage_status"] == "measured"
    assert payload["recent_sessions"][0]["cost_status"] == "unavailable"
    assert payload["recent_sessions"][0]["interpretation"] == "tokens measured; USD unavailable"
    assert payload["recent_sessions"][0]["cost_usd"] is None
    assert any("no pricing snapshot is configured" in item for item in payload["guidance"])
    assert ledger_path.read_text(encoding="utf-8") == ledger_before
