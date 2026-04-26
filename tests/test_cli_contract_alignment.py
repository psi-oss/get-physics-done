"""CLI tests for the `gpd contract` alignment-gate subcommands.

Covers `record-alignment` round-trip persistence, `alignment-status` JSON
output (unrecorded and post-record), `context-fingerprint` auto-resolution
from the active phase plus the explicit-path branch, and `alignment-summary`
round-trip against a stage-0 fixture plus the missing-contract error path.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from gpd.cli import app
from gpd.contracts import ResearchContract
from gpd.core.contract_validation import contract_fingerprint
from gpd.core.state import (
    default_state_dict,
    generate_state_markdown,
    state_record_contract_alignment,  # noqa: F401  (import smoke-tests availability)
)


class _StableCliRunner(CliRunner):
    def invoke(self, *args, **kwargs):
        kwargs.setdefault("color", False)
        return super().invoke(*args, **kwargs)


runner = _StableCliRunner()
_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_HELLO_CONTEXT_SHA256 = (
    "sha256:d73aac31ef8d5329cb61f8941219af525b2547d60ee159353b88cd4bb8e31e14"
)
_EXPLICIT_CONTEXT_SHA256 = (
    "sha256:a22bdbf5bf3e84c661ebfbfaf3d296bd2cd7bbc73a64d5cce003a9508f65b1ae"
)
_NESTED_CONTEXT_SHA256 = (
    "sha256:adf69e91b95e6ad45a5e2a057add1708c2b9f34b199657407b89e62fb0240d21"
)


def _strip_ansi(text: str) -> str:
    return _ANSI_ESCAPE_RE.sub("", text)


@pytest.fixture()
def gpd_project(tmp_path: Path) -> Path:
    """Create a minimal GPD project with enough scaffolding for state_load."""
    planning = tmp_path / "GPD"
    planning.mkdir()

    state = default_state_dict()
    state["position"].update(
        {
            "current_phase": "01",
            "current_phase_name": "Test Phase",
            "total_phases": 1,
            "status": "Planning",
        }
    )
    (planning / "state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
    (planning / "STATE.md").write_text(generate_state_markdown(state), encoding="utf-8")
    (planning / "PROJECT.md").write_text(
        "# Test Project\n\n## Core Research Question\nWhat is physics?\n", encoding="utf-8"
    )
    (planning / "REQUIREMENTS.md").write_text(
        "# Requirements\n\n- [ ] **REQ-01**: Do the thing\n", encoding="utf-8"
    )
    (planning / "ROADMAP.md").write_text(
        "# Roadmap\n\n## Phase 1: Test Phase\nGoal: Test\nRequirements: REQ-01\n",
        encoding="utf-8",
    )
    (planning / "config.json").write_text(
        json.dumps({"autonomy": "yolo", "research_mode": "balanced"}),
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture(autouse=True)
def _chdir(gpd_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(gpd_project)


def test_cli_contract_record_alignment_round_trip(gpd_project: Path) -> None:
    """Recording via CLI must persist the hashes into state.json."""
    contract_hash = "sha256:" + "a" * 64
    context_hash = "sha256:" + "b" * 64

    result = runner.invoke(
        app,
        [
            "contract",
            "record-alignment",
            "--contract-hash",
            contract_hash,
            "--context-hash",
            context_hash,
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, f"record-alignment failed: {result.output}"
    assert "recorded" in _strip_ansi(result.output)

    state = json.loads((gpd_project / "GPD" / "state.json").read_text(encoding="utf-8"))
    alignment = state.get("contract_alignment") or {}
    assert alignment.get("confirmed_contract_hash") == contract_hash
    assert alignment.get("confirmed_context_hash") == context_hash
    assert alignment.get("confirmed_at") is not None


def test_cli_contract_alignment_status_returns_none_when_unrecorded(gpd_project: Path) -> None:
    """Fresh project: all three JSON keys must be null and exit 0."""
    result = runner.invoke(
        app,
        ["contract", "alignment-status"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, f"alignment-status failed: {result.output}"

    payload = json.loads(_strip_ansi(result.output))
    assert payload == {
        "confirmed_at": None,
        "confirmed_contract_hash": None,
        "confirmed_context_hash": None,
    }


def test_cli_contract_context_fingerprint_auto_resolves_active_phase(
    gpd_project: Path,
) -> None:
    """With no path argument, the CLI resolves CONTEXT.md from the active phase."""
    phase_dir = gpd_project / "GPD" / "phases" / "01-test-phase"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-CONTEXT.md").write_text("hello context", encoding="utf-8")

    result = runner.invoke(
        app,
        ["contract", "context-fingerprint"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, _strip_ansi(result.output)
    assert _strip_ansi(result.output).strip() == _HELLO_CONTEXT_SHA256


def test_cli_contract_context_fingerprint_explicit_path(
    gpd_project: Path, tmp_path: Path
) -> None:
    """An explicit path argument still fingerprints the given file."""
    target = tmp_path / "explicit-context.md"
    target.write_text("explicit context text", encoding="utf-8")

    result = runner.invoke(
        app,
        ["contract", "context-fingerprint", str(target)],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, _strip_ansi(result.output)
    assert _strip_ansi(result.output).strip() == _EXPLICIT_CONTEXT_SHA256


def test_cli_contract_context_fingerprint_explicit_relative_path_uses_cli_cwd(
    gpd_project: Path,
) -> None:
    """A relative explicit CONTEXT.md path is anchored at --cwd, not process cwd."""
    nested = gpd_project / "nested"
    target = nested / "relative" / "CONTEXT.md"
    target.parent.mkdir(parents=True)
    target.write_text("nested explicit context", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "--cwd",
            str(nested),
            "contract",
            "context-fingerprint",
            "relative/CONTEXT.md",
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, _strip_ansi(result.output)
    assert _strip_ansi(result.output).strip() == _NESTED_CONTEXT_SHA256


def test_cli_contract_context_fingerprint_raw_wraps_result(gpd_project: Path) -> None:
    """Raw context-fingerprint output follows the standard CLI JSON envelope."""
    target = gpd_project / "explicit-context.md"
    target.write_text("explicit context text", encoding="utf-8")

    result = runner.invoke(
        app,
        ["--raw", "contract", "context-fingerprint", str(target)],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, _strip_ansi(result.output)
    assert json.loads(_strip_ansi(result.output)) == {"result": _EXPLICIT_CONTEXT_SHA256}


def test_cli_contract_fingerprint_raw_wraps_result(gpd_project: Path) -> None:
    """Raw contract fingerprint output follows the standard CLI JSON envelope."""
    fixture_path = (
        Path(__file__).resolve().parent / "fixtures" / "stage0" / "project_contract.json"
    )
    contract = json.loads(fixture_path.read_text(encoding="utf-8"))
    state_path = gpd_project / "GPD" / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["project_contract"] = contract
    state_path.write_text(json.dumps(state), encoding="utf-8")

    result = runner.invoke(
        app,
        ["--raw", "contract", "fingerprint"],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, _strip_ansi(result.output)
    expected = contract_fingerprint(ResearchContract.model_validate(contract))
    assert json.loads(_strip_ansi(result.output)) == {"result": expected}


def test_cli_contract_alignment_status_after_record(gpd_project: Path) -> None:
    """After recording, alignment-status must echo the persisted hashes."""
    contract_hash = "sha256:" + "c" * 64
    context_hash = "sha256:" + "d" * 64

    record_result = runner.invoke(
        app,
        [
            "contract",
            "record-alignment",
            "--contract-hash",
            contract_hash,
            "--context-hash",
            context_hash,
        ],
        catch_exceptions=False,
    )
    assert record_result.exit_code == 0, f"record-alignment failed: {record_result.output}"

    status_result = runner.invoke(
        app,
        ["contract", "alignment-status"],
        catch_exceptions=False,
    )
    assert status_result.exit_code == 0, f"alignment-status failed: {status_result.output}"

    payload = json.loads(_strip_ansi(status_result.output))
    assert payload["confirmed_contract_hash"] == contract_hash
    assert payload["confirmed_context_hash"] == context_hash
    assert payload["confirmed_at"] is not None


def test_cli_contract_alignment_summary_returns_rows_json(
    gpd_project: Path,
) -> None:
    """`gpd contract alignment-summary` emits one row per claim from state."""
    fixture_path = (
        Path(__file__).resolve().parent / "fixtures" / "stage0" / "project_contract.json"
    )
    contract = json.loads(fixture_path.read_text(encoding="utf-8"))
    state_path = gpd_project / "GPD" / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["project_contract"] = contract
    state_path.write_text(json.dumps(state), encoding="utf-8")

    result = runner.invoke(app, ["contract", "alignment-summary"], catch_exceptions=False)
    assert result.exit_code == 0, _strip_ansi(result.output)

    payload = json.loads(_strip_ansi(result.output))
    assert "rows" in payload
    assert len(payload["rows"]) == 1
    row = payload["rows"][0]
    assert row["claim"]
    assert row["deliverable"] == "Benchmark comparison figure"
    assert row["acceptance_test"] == "Matches reference within tolerance"


def test_cli_contract_alignment_summary_errors_when_contract_missing(
    gpd_project: Path,
) -> None:
    """Without `project_contract` in state, the command must exit non-zero."""
    # The `gpd_project` fixture writes `state.json` without a `project_contract`.
    result = runner.invoke(app, ["contract", "alignment-summary"], catch_exceptions=False)
    assert result.exit_code != 0
    assert "No project contract" in _strip_ansi(result.output)
