"""Focused consistency-checker vertical contract assertions."""

from __future__ import annotations

from pathlib import Path

from gpd.adapters.install_utils import expand_at_includes

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / "src" / "gpd" / "specs" / "workflows"
AGENTS_DIR = REPO_ROOT / "src" / "gpd" / "agents"


def _read_workflow(name: str) -> str:
    return (WORKFLOWS_DIR / name).read_text(encoding="utf-8")


def _read_agent(name: str) -> str:
    return (AGENTS_DIR / f"{name}.md").read_text(encoding="utf-8")


def test_validate_conventions_seam_is_one_shot_and_artifact_gated_before_notation_resolution() -> None:
    workflow = _read_workflow("validate-conventions.md")
    expanded_workflow = expand_at_includes(workflow, REPO_ROOT / "src/gpd", "/runtime/")

    assert "Spawn a fresh subagent for the task below." in expanded_workflow
    assert "This is a one-shot handoff:" in expanded_workflow
    assert "Do not make the child wait in place." in expanded_workflow
    assert "If the task produces files, verify the expected artifacts on disk before marking the handoff complete." in expanded_workflow
    assert "Always pass `readonly=false` for file-producing agents." in expanded_workflow
    assert "Thin wrapper around `gpd-consistency-checker` for convention validation." in workflow
    assert "Spawn `gpd-consistency-checker` once and let it own convention policy." in workflow
    assert "Runtime delegation rule: this is a one-shot handoff." in workflow
    assert workflow.count('subagent_type="gpd-consistency-checker"') == 1
    assert workflow.count('subagent_type="gpd-notation-coordinator"') == 0
    assert "gpd-notation-coordinator" in workflow
    assert "Route only on the canonical `gpd_return.status`:" in workflow
    assert "Do not route on checker-local text markers or headings." in workflow
    assert "If the checker's `next_actions` call for notation repair, spawn `gpd-notation-coordinator` with the checker report and the same scope." in workflow
    assert "Keep that handoff thin: the coordinator owns the repair policy, not this workflow." in workflow
    assert "If the checker returns `gpd_return.status: completed`, accept success only after verifying that:" in workflow
    assert "The same path appears in `gpd_return.files_written`." in workflow


def test_consistency_checker_and_notation_coordinator_keep_ownership_boundaries_separate() -> None:
    checker = _read_agent("gpd-consistency-checker")
    notation = _read_agent("gpd-notation-coordinator")

    assert "Scope boundary: `gpd-verifier` owns within-phase correctness. You own between-phase consistency only." in checker
    assert "status: completed | checkpoint | blocked | failed" in checker
    assert "Use `status: checkpoint` only when missing inputs or context pressure prevent a trustworthy check." in checker
    assert "Use `status: blocked` only for hard inconsistencies that need escalation." in checker
    assert "Use `status: failed` only when the scope could not be validated." in checker
    assert "shared_state_authority: return_only" in checker
    assert "Do not claim ownership of code fixes, commits, convention-authoring, or pattern-library updates." in checker

    assert "shared_state_authority: direct" in notation
    assert "This agent OWNS CONVENTIONS.md — it is the only agent that creates, modifies, or extends the conventions file." in notation
    assert "the gpd-consistency-checker DETECTS convention violations but delegates resolution to this agent" in notation
    assert "Do not act as the default writable implementation agent" in checker


def test_audit_milestone_consumes_checker_reports_without_spawning_notation_resolution() -> None:
    workflow = _read_workflow("audit-milestone.md")
    checker = _read_agent("gpd-consistency-checker")

    assert workflow.count('subagent_type="gpd-consistency-checker"') == 1
    assert "gpd-notation-coordinator" not in workflow
    assert "Consistency checker's report (notation conflicts, parameter mismatches, broken reasoning chains) — or note \"skipped\" if agent failed" in workflow
    assert "If the consistency checker agent fails to spawn or returns an error:" in workflow
    assert "status: completed | checkpoint | blocked | failed" in checker
    assert "Human-readable headings in the report are presentation only; route on `gpd_return.status`." in checker
