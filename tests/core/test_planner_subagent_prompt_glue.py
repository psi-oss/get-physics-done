"""Assertions for planner subagent prompt glue and fail-closed behavior."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PLANNER_SUBAGENT_PROMPT = REPO_ROOT / "src" / "gpd" / "specs" / "templates" / "planner-subagent-prompt.md"


def test_planner_subagent_prompt_stays_thin_and_fail_closed() -> None:
    prompt = PLANNER_SUBAGENT_PROMPT.read_text(encoding="utf-8")

    assert prompt.count("{GPD_INSTALL_DIR}/templates/plan-contract-schema.md") == 1
    assert "Use `@{GPD_INSTALL_DIR}/templates/plan-contract-schema.md` as the canonical contract source." in prompt
    assert "project_contract_gate.authoritative" in prompt
    assert "project_contract_load_info.status" in prompt
    assert "project_contract_validation.valid" in prompt
    assert prompt.count("gpd_return.status: checkpoint") >= 3
    assert "execute-plan.md" not in prompt
    assert "summary.md" not in prompt
    assert "order-of-limits.md" not in prompt
    assert "staged_loading" not in prompt


def test_planner_subagent_prompt_keeps_scope_selection_and_revision_glue_only() -> None:
    prompt = PLANNER_SUBAGENT_PROMPT.read_text(encoding="utf-8")

    assert "Keep this prompt for scope selection, mode flags, and return conventions only." in prompt
    assert "Planner policy" not in prompt
    assert "## Standard Planning Template" in prompt
    assert "## Revision Template" in prompt
    assert (
        "Treat stable knowledge docs surfaced through `active_reference_context` and `reference_artifacts_content` as "
        "reviewed background syntheses."
    ) in prompt
    assert (
        "Use explicit `knowledge_deps` when a plan materially depends on a reviewed knowledge doc and downstream gating should be enforced; keep implicit stable background advisory only."
    ) in prompt
    assert "do not invent a separate knowledge authority or ledger." in prompt
    assert (
        "If `{project_contract}` is empty, stale, or too underspecified to identify the phase contract slice, return "
        "`gpd_return.status: checkpoint` rather than guessing."
    ) in prompt
    assert (
        "If the approved project contract is missing or no longer sufficient to identify the right phase slice, return "
        "`gpd_return.status: checkpoint` instead of patching around guessed scope."
    ) in prompt
