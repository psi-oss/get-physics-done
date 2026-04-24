"""Phase 9 — end-to-end smoke test for the supervised-default stack.

The underlying workflows are LLM-driven, so this test cannot literally drive
`gpd:new-project` → `gpd:plan-phase 1` → `gpd:execute-phase 1` from an LLM.
Instead, it asserts the workflow-orchestration *contract* that Phases 1–8
ship: defaults, spec-text wiring, CLI surfaces, and cross-phase consistency.
A future run that exercises the full flow with a real agent can reuse these
fixtures and swap in live subagent calls.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from gpd.cli import app
from gpd.core.config import AutonomyMode, ReviewCadence, load_config
from gpd.core.errors import ConfigError

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS_DIR = REPO_ROOT / "src" / "gpd" / "specs" / "workflows"
AGENTS_DIR = REPO_ROOT / "src" / "gpd" / "agents"
COMMANDS_DIR = REPO_ROOT / "src" / "gpd" / "commands"
REFERENCES_DIR = REPO_ROOT / "src" / "gpd" / "specs" / "references"


def _spec(name: str, *, under: Path = WORKFLOWS_DIR) -> str:
    return (under / name).read_text(encoding="utf-8")


def _write_config(tmp_path: Path, config: dict) -> Path:
    cfg_path = tmp_path / "GPD" / "config.json"
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(json.dumps(config), encoding="utf-8")
    return cfg_path


def test_supervised_default_smoke_run(tmp_path: Path) -> None:
    """End-to-end contract: the supervised-default stack is wired top to bottom.

    Walks the 5 acceptance-criteria steps from masterplan §9.2 as spec-and-
    surface checks. Each step maps to the artifacts that a live LLM flow
    would need to work.
    """

    # ---------- Phase 1: config defaults are supervised + dense ----------
    (tmp_path / "GPD").mkdir(parents=True, exist_ok=True)
    cfg = load_config(tmp_path)
    assert cfg.autonomy is AutonomyMode.SUPERVISED
    assert cfg.review_cadence is ReviewCadence.DENSE
    assert cfg.checkpoint_after_n_tasks == 1
    assert cfg.max_unattended_minutes_per_plan == 15
    assert cfg.max_unattended_minutes_per_wave == 30
    assert cfg.checkpoint_after_first_load_bearing_result is True

    # ---------- Phase 2: scalpel-not-autopilot framing ----------
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    settings = _spec("settings.md")
    assert "scalpel, not an autopilot" in readme
    assert "scalpel, not an autopilot" in settings

    # ---------- Step 1: gpd:new-project produces shallow ROADMAP ----------
    new_project = _spec("new-project.md")
    # Shallow-mode roadmap: Phase 1 detailed, Phases 2+ stubs.
    assert "<shallow_mode>true</shallow_mode>" in new_project
    # Standard-mode Next Up recommends plan-phase 1 directly.
    standard_next_up = new_project[new_project.rindex("## >> Next Up"):]
    assert "`gpd:plan-phase 1`" in standard_next_up
    plan_idx = standard_next_up.index("`gpd:plan-phase 1`")
    discuss_idx = standard_next_up.index("`gpd:discuss-phase 1`")
    assert plan_idx < discuss_idx

    # ---------- Step 2: gpd:plan-phase exists and consults backtracks ----------
    planner = (AGENTS_DIR / "gpd-planner.md").read_text(encoding="utf-8")
    assert "GPD/BACKTRACKS.md" in planner
    assert "patterns_consulted" in planner
    assert "backtracks" in planner

    # ---------- Step 3: gpd:execute-phase — precheck + first-result gate ----------
    execute_phase = _spec("execute-phase.md")
    # Phase 5: claim↔deliverable precheck step is wired in.
    assert '<step name="claim_deliverable_alignment_check">' in execute_phase
    assert "autonomy=supervised" in execute_phase
    assert "review_cadence=dense" in execute_phase
    # Phase 4: dense override forces the first-result gate on every wave.
    assert "Dense cadence override:" in execute_phase
    assert "treat every wave as risky" in execute_phase

    # Phase 8.A: checkpoint:human-verify idiom is [Y/n/e].
    checkpoints = (REFERENCES_DIR / "orchestration" / "checkpoints.md").read_text(
        encoding="utf-8"
    )
    assert checkpoints.count("[Y/n/e]") >= 6
    convention = (REFERENCES_DIR / "orchestration" / "checkpoint-ux-convention.md").read_text(
        encoding="utf-8"
    )
    assert "[Y/n/e]" in convention

    # ---------- Step 4: gpd progress --watch read-only heartbeat ----------
    runner = CliRunner()
    help_out = runner.invoke(app, ["progress", "--help"])
    assert help_out.exit_code == 0
    assert "--watch" in help_out.stdout
    assert "--interval" in help_out.stdout
    assert "--exit-on-idle" in help_out.stdout

    # ---------- Step 5: gpd:record-backtrack writes to BACKTRACKS.md ----------
    assert (COMMANDS_DIR / "record-backtrack.md").exists()
    record_backtrack = _spec("record-backtrack.md")
    assert "GPD/BACKTRACKS.md" in record_backtrack
    # All 11 schema columns are named in the spec.
    for field in [
        "date",
        "phase",
        "stage",
        "trigger",
        "produced",
        "why_wrong",
        "counter_action",
        "category",
        "confidence",
        "promote",
        "reverted_commit",
    ]:
        assert field in record_backtrack, f"BACKTRACKS.md schema missing field: {field}"

    # gpd:undo offers the backtrack hook.
    undo = _spec("undo.md")
    assert '<step name="offer_record_backtrack">' in undo
    assert "gpd:record-backtrack" in undo

    # ---------- Phase 8.B: clean-pass wave batching under dense ----------
    execute_plan = _spec("execute-plan.md")
    assert "Clean-wave batching under dense" in execute_plan
    assert "Approve tasks" in execute_plan
    assert "collapses keystrokes, not gates" in execute_plan

    # ---------- Cross-phase: contract CLI surfaces ----------
    contract_help = runner.invoke(app, ["contract", "--help"])
    assert contract_help.exit_code == 0
    for sub in [
        "record-alignment",
        "alignment-status",
        "fingerprint",
        "context-fingerprint",
        "alignment-summary",
    ]:
        assert sub in contract_help.stdout, (
            f"gpd contract {sub} subcommand must be registered"
        )


def test_supervised_default_rejects_dense_without_first_result_gate(
    tmp_path: Path,
) -> None:
    """The Phase 4 config validator rejects review_cadence=dense paired with a
    disabled first-result gate. Guards against a config that would silently
    undo the supervised-default silent-failure mitigation."""
    _write_config(
        tmp_path,
        {
            "review_cadence": "dense",
            "checkpoint_after_first_load_bearing_result": False,
        },
    )
    with pytest.raises(ConfigError, match="dense"):
        load_config(tmp_path)
