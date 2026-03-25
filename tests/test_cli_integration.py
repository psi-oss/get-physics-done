"""Integration tests for CLI commands with zero prior test coverage.

Each test exercises the real CLI -> core path (no mocks) using a minimal
GPD project directory created by the ``gpd_project`` fixture.  The goal is
to verify that the CLI wiring, argument parsing, and core logic all cooperate
without crashing.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from gpd.adapters import get_adapter
from gpd.adapters.runtime_catalog import iter_runtime_descriptors
from gpd.cli import app
from gpd.core.state import default_state_dict, generate_state_markdown

runner = CliRunner()
_RUNTIME_DESCRIPTORS = iter_runtime_descriptors()


@pytest.fixture()
def codex_command_prefix(monkeypatch: pytest.MonkeyPatch) -> str:
    """Force the integration preflight surface to resolve the Codex runtime."""
    monkeypatch.setattr("gpd.cli.detect_runtime_for_gpd_use", lambda cwd=None: "codex")
    return get_adapter("codex").command_prefix


@pytest.fixture()
def claude_code_command_prefix(monkeypatch: pytest.MonkeyPatch) -> str:
    """Force the integration preflight surface to resolve the Claude Code runtime."""
    monkeypatch.setattr("gpd.cli.detect_runtime_for_gpd_use", lambda cwd=None: "claude-code")
    return get_adapter("claude-code").command_prefix

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


def _mark_complete_runtime_install(config_dir: Path, *, runtime: str, install_scope: str = "local") -> None:
    """Create the concrete install markers real runtime installs write."""
    adapter = get_adapter(runtime)
    config_dir.mkdir(parents=True, exist_ok=True)
    for relpath in adapter.install_completeness_relpaths():
        if relpath == "gpd-file-manifest.json":
            continue
        artifact = config_dir / relpath
        artifact.parent.mkdir(parents=True, exist_ok=True)
        if artifact.suffix:
            artifact.write_text("{}\n" if artifact.suffix == ".json" else "# test\n", encoding="utf-8")
        else:
            artifact.mkdir(parents=True, exist_ok=True)
    explicit_target = config_dir.name != adapter.config_dir_name
    manifest: dict[str, object] = {
        "runtime": runtime,
        "install_scope": install_scope,
        "explicit_target": explicit_target,
        "install_target_dir": str(config_dir),
    }
    if runtime == "codex":
        skills_dir = config_dir.parent / ".agents" / "skills"
        help_skill_dir = skills_dir / "gpd-help"
        help_skill_dir.mkdir(parents=True, exist_ok=True)
        (help_skill_dir / "SKILL.md").write_text("# test\n", encoding="utf-8")
        manifest["codex_skills_dir"] = str(skills_dir)
        manifest["codex_generated_skill_dirs"] = ["gpd-help"]
    (config_dir / "gpd-file-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


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
        from gpd.adapters.claude_code import ClaudeCodeAdapter

        target = gpd_project / ".claude"
        target.mkdir()
        gpd_root = Path(__file__).resolve().parents[1] / "src" / "gpd"
        ClaudeCodeAdapter().install(gpd_root, target)

        result = _invoke("--raw", "permissions", "sync", "--runtime", "claude-code", "--autonomy", "yolo")
        parsed = json.loads(result.output)
        settings = json.loads((target / "settings.json").read_text(encoding="utf-8"))

        assert parsed["runtime"] == "claude-code"
        assert parsed["sync_applied"] is True
        assert settings["permissions"]["defaultMode"] == "bypassPermissions"

    def test_permissions_sync_accepts_display_name_runtime(self, gpd_project: Path) -> None:
        from gpd.adapters.claude_code import ClaudeCodeAdapter

        target = gpd_project / ".claude"
        target.mkdir()
        gpd_root = Path(__file__).resolve().parents[1] / "src" / "gpd"
        ClaudeCodeAdapter().install(gpd_root, target)

        result = _invoke("--raw", "permissions", "sync", "--runtime", "Claude Code", "--autonomy", "yolo")
        parsed = json.loads(result.output)
        settings = json.loads((target / "settings.json").read_text(encoding="utf-8"))

        assert parsed["runtime"] == "claude-code"
        assert parsed["sync_applied"] is True
        assert settings["permissions"]["defaultMode"] == "bypassPermissions"

    def test_permissions_sync_accepts_alias_runtime(self, gpd_project: Path) -> None:
        from gpd.adapters.claude_code import ClaudeCodeAdapter

        target = gpd_project / ".claude"
        target.mkdir()
        gpd_root = Path(__file__).resolve().parents[1] / "src" / "gpd"
        ClaudeCodeAdapter().install(gpd_root, target)

        result = _invoke("--raw", "permissions", "sync", "--runtime", "claude", "--autonomy", "yolo")
        parsed = json.loads(result.output)
        settings = json.loads((target / "settings.json").read_text(encoding="utf-8"))

        assert parsed["runtime"] == "claude-code"
        assert parsed["sync_applied"] is True
        assert settings["permissions"]["defaultMode"] == "bypassPermissions"

    def test_permissions_status_and_sync_use_explicit_local_install_target(
        self,
        gpd_project: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from gpd.adapters.claude_code import ClaudeCodeAdapter

        target = gpd_project / "external" / "claude-config"
        target.mkdir(parents=True)
        gpd_root = Path(__file__).resolve().parents[1] / "src" / "gpd"
        ClaudeCodeAdapter().install(gpd_root, target, is_global=False, explicit_target=True)
        monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(target))

        status_result = _invoke("--raw", "permissions", "status", "--runtime", "claude-code")
        parsed_status = json.loads(status_result.output)
        assert parsed_status["runtime"] == "claude-code"
        assert parsed_status["target"] == str(target)
        assert parsed_status["settings_path"] == str(target / "settings.json")

        sync_result = _invoke("--raw", "permissions", "sync", "--runtime", "claude-code", "--autonomy", "yolo")
        parsed_sync = json.loads(sync_result.output)
        settings = json.loads((target / "settings.json").read_text(encoding="utf-8"))

        assert parsed_sync["runtime"] == "claude-code"
        assert parsed_sync["target"] == str(target)
        assert parsed_sync["sync_applied"] is True
        assert settings["permissions"]["defaultMode"] == "bypassPermissions"

    def test_permissions_status_uses_public_adapter_target_validation_contract(
        self,
        gpd_project: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import gpd.adapters as adapters_module

        target = gpd_project / "external" / "codex-config"
        target.mkdir(parents=True)
        validation_calls: list[tuple[Path, str]] = []

        class _FakeAdapter:
            runtime_name = "codex"
            display_name = "Codex"

            def validate_target_runtime(self, target_dir: Path, *, action: str) -> None:
                validation_calls.append((target_dir, action))

            def has_complete_install(self, target_dir: Path) -> bool:
                return True

            def runtime_permissions_status(self, target_dir: Path, *, autonomy: str) -> dict[str, object]:
                return {
                    "runtime": "codex",
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
            "codex",
            "--target-dir",
            str(target),
            "--autonomy",
            "balanced",
        )
        parsed = json.loads(result.output)

        assert validation_calls == [(target.resolve(strict=False), "inspect runtime permissions on")]
        assert parsed["runtime"] == "codex"
        assert parsed["target"] == str(target.resolve(strict=False))
        assert parsed["message"] == "validated codex-config for balanced"

    @pytest.mark.parametrize("command", ["status", "sync"])
    def test_permissions_reject_foreign_manifest_target(
        self,
        gpd_project: Path,
        command: str,
    ) -> None:
        from gpd.adapters.claude_code import ClaudeCodeAdapter

        target = gpd_project / ".claude"
        target.mkdir()
        gpd_root = Path(__file__).resolve().parents[1] / "src" / "gpd"
        ClaudeCodeAdapter().install(gpd_root, target)

        manifest_before = (target / "gpd-file-manifest.json").read_text(encoding="utf-8")
        config_toml = target / "config.toml"
        config_toml_existed_before = config_toml.exists()
        action = "sync" if command == "sync" else "inspect"

        result = _invoke(
            "--raw",
            "permissions",
            command,
            "--runtime",
            "codex",
            "--target-dir",
            str(target),
            "--autonomy",
            "yolo",
            expect_ok=False,
        )
        parsed = json.loads(result.output)

        assert result.exit_code == 1
        assert parsed["error"].startswith(f"Refusing to {action} runtime permissions on")
        assert "`claude-code`" in parsed["error"]
        assert "`codex`" in parsed["error"]
        assert (target / "gpd-file-manifest.json").read_text(encoding="utf-8") == manifest_before
        assert config_toml.exists() == config_toml_existed_before

    def test_config_set_autonomy_attempts_runtime_permission_sync(
        self,
        gpd_project: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from gpd.adapters.claude_code import ClaudeCodeAdapter

        target = gpd_project / ".claude"
        target.mkdir()
        gpd_root = Path(__file__).resolve().parents[1] / "src" / "gpd"
        adapter = ClaudeCodeAdapter()
        adapter.install(gpd_root, target)
        adapter.sync_runtime_permissions(target, autonomy="yolo")
        monkeypatch.setenv("GPD_ACTIVE_RUNTIME", "claude-code")

        result = _invoke("--raw", "config", "set", "autonomy", "balanced")
        parsed = json.loads(result.output)
        settings = json.loads((target / "settings.json").read_text(encoding="utf-8"))

        assert parsed["value"] == "balanced"
        assert parsed["runtime_permissions"]["runtime"] == "claude-code"
        assert parsed["runtime_permissions"]["sync_applied"] is True
        assert settings.get("permissions", {}).get("defaultMode") != "bypassPermissions"

    def test_permissions_sync_prefers_active_runtime_over_other_installed_runtime(
        self,
        gpd_project: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from gpd.adapters.codex import CodexAdapter

        target = gpd_project / ".codex"
        target.mkdir()
        gpd_root = Path(__file__).resolve().parents[1] / "src" / "gpd"
        CodexAdapter().install(gpd_root, target)
        fake_home = gpd_project / "_fake_home_permissions"
        fake_home.mkdir()
        monkeypatch.setenv("CLAUDE_CODE_SESSION", "active")

        with patch("pathlib.Path.home", return_value=fake_home):
            result = _invoke("--raw", "permissions", "sync", "--autonomy", "yolo", expect_ok=False)

        parsed = json.loads(result.output)
        manifest = json.loads((target / "gpd-file-manifest.json").read_text(encoding="utf-8"))
        config_toml = (target / "config.toml").read_text(encoding="utf-8")

        assert parsed["error"] == "No GPD install found for runtime 'claude-code'. Run `gpd install claude-code` first."
        assert "gpd_runtime_permissions" not in manifest
        assert 'approval_policy = "never"' not in config_toml
        assert 'sandbox_mode = "danger-full-access"' not in config_toml

    def test_config_set_autonomy_does_not_sync_other_installed_runtime(
        self,
        gpd_project: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from gpd.adapters.codex import CodexAdapter

        target = gpd_project / ".codex"
        target.mkdir()
        gpd_root = Path(__file__).resolve().parents[1] / "src" / "gpd"
        CodexAdapter().install(gpd_root, target)
        fake_home = gpd_project / "_fake_home_config_set"
        fake_home.mkdir()
        monkeypatch.setenv("CLAUDE_CODE_SESSION", "active")

        with patch("pathlib.Path.home", return_value=fake_home):
            result = _invoke("--raw", "config", "set", "autonomy", "yolo")

        parsed = json.loads(result.output)
        manifest = json.loads((target / "gpd-file-manifest.json").read_text(encoding="utf-8"))
        config_toml = (target / "config.toml").read_text(encoding="utf-8")

        assert parsed["value"] == "yolo"
        assert parsed["runtime_permissions"]["runtime"] == "claude-code"
        assert parsed["runtime_permissions"]["sync_applied"] is False
        assert parsed["runtime_permissions"]["changed"] is False
        assert parsed["runtime_permissions"]["message"] == (
            "No GPD install found for runtime 'claude-code'. Run `gpd install claude-code` first."
        )
        assert "gpd_runtime_permissions" not in manifest
        assert 'approval_policy = "never"' not in config_toml
        assert 'sandbox_mode = "danger-full-access"' not in config_toml

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
        _mark_complete_runtime_install(gpd_project / descriptor.config_dir_name, runtime=descriptor.runtime_name)
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
        _mark_complete_runtime_install(gpd_project / descriptor.config_dir_name, runtime=descriptor.runtime_name)

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
