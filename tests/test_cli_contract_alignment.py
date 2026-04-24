"""CLI tests for the `gpd contract` alignment-gate subcommands.

These tests exercise the Phase 5 claim-deliverable precheck wiring:

- `gpd contract record-alignment --contract-hash ... --context-hash ...`
- `gpd contract alignment-status`

The backing persistence helper (`state_record_contract_alignment`) is owned
by lane E1. Tests that depend on it will skip cleanly if the helper is not
yet importable.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from gpd.cli import app
from gpd.core.state import default_state_dict, generate_state_markdown


class _StableCliRunner(CliRunner):
    def invoke(self, *args, **kwargs):
        kwargs.setdefault("color", False)
        return super().invoke(*args, **kwargs)


runner = _StableCliRunner()
_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def _strip_ansi(text: str) -> str:
    return _ANSI_ESCAPE_RE.sub("", text)


def _has_record_helper() -> bool:
    """Check whether lane E1's persistence helper has landed."""
    try:
        from gpd.core.state import state_record_contract_alignment  # noqa: F401
    except ImportError:
        return False
    return True


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


@pytest.mark.skipif(
    not _has_record_helper(),
    reason="lane E1 has not landed state_record_contract_alignment yet",
)
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
    assert _strip_ansi(result.output).strip().startswith("sha256:")


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
    assert _strip_ansi(result.output).strip().startswith("sha256:")


@pytest.mark.skipif(
    not _has_record_helper(),
    reason="lane E1 has not landed state_record_contract_alignment yet",
)
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
