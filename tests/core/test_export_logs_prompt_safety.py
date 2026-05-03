from __future__ import annotations

import json
import tomllib
from pathlib import Path

from typer.testing import CliRunner

from gpd.adapters.claude_code import ClaudeCodeAdapter
from gpd.adapters.gemini import GeminiAdapter
from gpd.cli import app

REPO_ROOT = Path(__file__).resolve().parents[2]
GPD_ROOT = REPO_ROOT / "src" / "gpd"
COMMANDS_DIR = GPD_ROOT / "commands"
WORKFLOWS_DIR = GPD_ROOT / "specs" / "workflows"

UNSAFE_EXPORT_LOG_PATTERNS = (
    "observe export $ARGUMENTS",
    "observe export ${ARGUMENTS",
    "EXPORT_ARGS=\"\"",
    "$EXPORT_ARGS",
    "--format $FORMAT",
    "--session $SESSION",
    "--last $LAST",
    "--command $COMMAND",
    "--phase $PHASE",
    "--category $CATEGORY",
    "--output-dir $OUTPUT_DIR",
)


def _assert_export_log_prompt_safe(text: str) -> None:
    for pattern in UNSAFE_EXPORT_LOG_PATTERNS:
        assert pattern not in text
    assert "`eval`" not in text
    assert "sh -c" not in text


def _write_minimal_session(project: Path) -> None:
    gpd_dir = project / "GPD"
    gpd_dir.mkdir()
    (gpd_dir / "PROJECT.md").write_text("# Project\n", encoding="utf-8")
    sessions_dir = gpd_dir / "observability" / "sessions"
    sessions_dir.mkdir(parents=True)
    sessions_dir.joinpath("session-export.jsonl").write_text(
        json.dumps(
            {
                "timestamp": "2026-03-10T00:00:00+00:00",
                "event_id": "evt-1",
                "session_id": "session-export",
                "category": "session",
                "name": "lifecycle",
                "action": "start",
                "status": "active",
                "command": "execute-phase",
                "data": {"cwd": str(project), "source": "cli", "pid": 100, "metadata": {}},
            }
        )
        + "\n",
        encoding="utf-8",
    )


def test_export_logs_source_prompts_do_not_reconstruct_shell_args() -> None:
    command = (COMMANDS_DIR / "export-logs.md").read_text(encoding="utf-8")
    workflow = (WORKFLOWS_DIR / "export-logs.md").read_text(encoding="utf-8")

    for text in (command, workflow):
        _assert_export_log_prompt_safe(text)
        assert '--output-dir "$OUTPUT_DIR"' in text
        assert "Never pass raw `$ARGUMENTS` to `observe export`" in text


def test_claude_rendered_export_logs_prompts_do_not_reconstruct_shell_args(tmp_path: Path) -> None:
    target = tmp_path / ".claude"
    target.mkdir()
    ClaudeCodeAdapter().install(GPD_ROOT, target)

    command_prompt = (target / "commands" / "gpd" / "export-logs.md").read_text(encoding="utf-8")
    workflow_prompt = (target / "get-physics-done" / "workflows" / "export-logs.md").read_text(encoding="utf-8")

    _assert_export_log_prompt_safe(command_prompt)
    _assert_export_log_prompt_safe(workflow_prompt)
    assert '--output-dir "$OUTPUT_DIR"' in command_prompt
    assert '--output-dir "$OUTPUT_DIR"' in workflow_prompt


def test_gemini_rendered_export_logs_prompt_does_not_reconstruct_shell_args(tmp_path: Path) -> None:
    target = tmp_path / ".gemini"
    target.mkdir()
    GeminiAdapter().install(GPD_ROOT, target)

    command_toml = (target / "commands" / "gpd" / "export-logs.toml").read_text(encoding="utf-8")
    command_prompt = tomllib.loads(command_toml)["prompt"]
    workflow_prompt = (target / "get-physics-done" / "workflows" / "export-logs.md").read_text(encoding="utf-8")

    _assert_export_log_prompt_safe(command_prompt)
    _assert_export_log_prompt_safe(workflow_prompt)
    assert '--output-dir "$OUTPUT_DIR"' in command_prompt
    assert '--output-dir "$OUTPUT_DIR"' in workflow_prompt


def test_observe_export_cli_handles_spaced_output_dir_as_one_path(tmp_path: Path) -> None:
    _write_minimal_session(tmp_path)
    output_dir = "GPD exports/logs with spaces"

    result = CliRunner().invoke(
        app,
        [
            "--raw",
            "--cwd",
            str(tmp_path),
            "observe",
            "export",
            "--format",
            "jsonl",
            "--output-dir",
            output_dir,
        ],
        color=False,
    )

    resolved_output_dir = tmp_path / output_dir
    assert result.exit_code == 0, result.output
    assert resolved_output_dir.is_dir()
    assert list(resolved_output_dir.glob("sessions-*.jsonl"))
    assert list(resolved_output_dir.glob("events-*.jsonl"))


def test_observe_export_cli_treats_shell_shaped_output_dir_as_literal_path(tmp_path: Path) -> None:
    _write_minimal_session(tmp_path)
    output_dir = "GPD exports/logs; touch shell-marker"

    result = CliRunner().invoke(
        app,
        [
            "--raw",
            "--cwd",
            str(tmp_path),
            "observe",
            "export",
            "--format",
            "jsonl",
            "--output-dir",
            output_dir,
        ],
        color=False,
    )

    assert result.exit_code == 0, result.output
    assert (tmp_path / output_dir).is_dir()
    assert not (tmp_path / "shell-marker").exists()
