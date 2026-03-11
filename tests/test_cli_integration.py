"""Integration tests for CLI commands with zero prior test coverage.

Each test exercises the real CLI -> core path (no mocks) using a minimal
GPD project directory created by the ``gpd_project`` fixture.  The goal is
to verify that the CLI wiring, argument parsing, and core logic all cooperate
without crashing.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from gpd.cli import app
from gpd.core.state import default_state_dict, generate_state_markdown

runner = CliRunner()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def gpd_project(tmp_path: Path) -> Path:
    """Create a minimal GPD project with all files commands might touch."""
    planning = tmp_path / ".gpd"
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
        '---\nphase: "01"\nplan: "01"\none-liner: "Set up project"\n'
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
        result = _invoke("verify-path", ".gpd/state.json")
        assert "file" in result.output.lower() or "True" in result.output or "true" in result.output

    def test_verify_existing_directory(self) -> None:
        result = _invoke("verify-path", ".gpd")
        assert "directory" in result.output.lower() or "True" in result.output or "true" in result.output

    def test_verify_nonexistent_path(self) -> None:
        result = _invoke("verify-path", "does/not/exist.txt", expect_ok=False)
        assert result.exit_code == 1
        assert "False" in result.output or "false" in result.output

    def test_verify_path_raw(self, gpd_project: Path) -> None:
        result = _invoke("--raw", "verify-path", ".gpd/state.json")
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


# ═══════════════════════════════════════════════════════════════════════════
# 5. regression-check
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

    def test_regression_check_detects_conflict(self, gpd_project: Path) -> None:
        """Inject a convention conflict across two completed phases."""
        p2 = gpd_project / ".gpd" / "phases" / "02-phase-two"

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
            '  status: completed\n  phase: "01"\n  plan: "01"\n'
            "  tasks_completed: 5\n  tasks_total: 5\n"
            "  files_written: 3\n  duration_seconds: 120\n```\n"
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
            '  status: completed\n  phase: "01"\n```\n'
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
            '  status: banana\n  phase: "01"\n  plan: "01"\n'
            "  tasks_completed: 5\n  tasks_total: 5\n```\n"
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
            '  status: completed\n  phase: "01"\n  plan: "01"\n'
            "  tasks_completed: 5\n  tasks_total: 5\n```\n"
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

    def test_config_get_nested_key(self, gpd_project: Path) -> None:
        """Test dot-path access for nested keys."""
        config_path = gpd_project / ".gpd" / "config.json"
        config_path.write_text(json.dumps({"nested": {"key": "value"}}))
        result = _invoke("--raw", "config", "get", "nested.key")
        parsed = json.loads(result.output)
        assert parsed["found"] is True
        assert parsed["value"] == "value"

    def test_config_set_new_key(self, gpd_project: Path) -> None:
        result = _invoke("--raw", "config", "set", "new_key", "new_value")
        parsed = json.loads(result.output)
        assert parsed["updated"] is True

        # Verify it persisted
        config = json.loads(
            (gpd_project / ".gpd" / "config.json").read_text()
        )
        assert config["new_key"] == "new_value"

    def test_config_set_nested_key(self, gpd_project: Path) -> None:
        _invoke("config", "set", "section.subsection", "deep_value")
        config = json.loads(
            (gpd_project / ".gpd" / "config.json").read_text()
        )
        assert config["section"]["subsection"] == "deep_value"

    def test_config_set_json_value(self, gpd_project: Path) -> None:
        """Setting a JSON value (e.g. integer, boolean) should parse it."""
        _invoke("config", "set", "count", "42")
        config = json.loads(
            (gpd_project / ".gpd" / "config.json").read_text()
        )
        assert config["count"] == 42

    def test_config_ensure_section_exists(self) -> None:
        """ensure-section with existing config.json should report created=False."""
        result = _invoke("--raw", "config", "ensure-section")
        parsed = json.loads(result.output)
        assert parsed["created"] is False

    def test_config_ensure_section_creates(self, gpd_project: Path) -> None:
        """ensure-section without config.json should create defaults."""
        (gpd_project / ".gpd" / "config.json").unlink()
        result = _invoke("--raw", "config", "ensure-section")
        parsed = json.loads(result.output)
        assert parsed["created"] is True
        config_path = gpd_project / ".gpd" / "config.json"
        assert config_path.exists()
        config = json.loads(config_path.read_text())
        assert config["autonomy"] == "balanced"
        assert config["research_mode"] == "balanced"
        assert config["parallelization"] is True
        assert config["workflow"]["plan_checker"] is True
        assert config["git"]["branching_strategy"] == "none"
        assert "brave_search" not in config
        assert "search_gitignored" not in config

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
            ".gpd/phases/01-test-phase/01-SUMMARY.md",
        )
        parsed = json.loads(result.output)
        assert parsed["one_liner"] == "Set up project"
        assert "src/main.py" in parsed["key_files"]

    def test_summary_extract_with_field_filter(self) -> None:
        result = _invoke(
            "--raw",
            "summary-extract",
            ".gpd/phases/01-test-phase/01-SUMMARY.md",
            "--field",
            "one_liner",
        )
        parsed = json.loads(result.output)
        assert "one_liner" in parsed
        assert parsed["one_liner"] == "Set up project"


class TestResolveModelCommand:
    def test_resolve_tier(self) -> None:
        result = _invoke("resolve-tier", "gpd-executor")
        assert result.output.strip() == "tier-2"

    def test_resolve_model_uses_active_runtime_override(self, gpd_project: Path) -> None:
        config_path = gpd_project / ".gpd" / "config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["model_overrides"] = {"codex": {"tier-1": "gpt-5"}}
        config_path.write_text(json.dumps(config), encoding="utf-8")
        (gpd_project / ".codex").mkdir()

        result = _invoke("resolve-model", "gpd-executor")
        assert result.output.strip() == ""

        planner_result = _invoke("resolve-model", "gpd-planner")
        assert planner_result.output.strip() == "gpt-5"
