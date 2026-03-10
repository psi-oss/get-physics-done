"""Regression tests for prompt/template wiring."""

from __future__ import annotations

import re
from pathlib import Path

from gpd import registry

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATES_DIR = REPO_ROOT / "src/gpd/specs/templates"
WORKFLOWS_DIR = REPO_ROOT / "src/gpd/specs/workflows"


def test_planner_templates_exist():
    planner_prompt = TEMPLATES_DIR / "planner-subagent-prompt.md"
    phase_prompt = TEMPLATES_DIR / "phase-prompt.md"

    assert planner_prompt.exists()
    assert phase_prompt.exists()
    assert "template_version: 1" in planner_prompt.read_text(encoding="utf-8")
    assert "template_version: 1" in phase_prompt.read_text(encoding="utf-8")
    assert "<planning_context>" in planner_prompt.read_text(encoding="utf-8")
    assert "must_haves:" in phase_prompt.read_text(encoding="utf-8")


def test_prompt_sources_do_not_use_stale_agent_install_paths():
    files = [
        REPO_ROOT / "src/gpd/specs/references/agent-delegation.md",
        REPO_ROOT / "src/gpd/specs/templates/continuation-prompt.md",
    ]

    for path in files:
        assert "{GPD_INSTALL_DIR}/agents/" not in path.read_text(encoding="utf-8"), path


def test_prompt_sources_use_real_pattern_library_description():
    verifier_files = [REPO_ROOT / "src/gpd/agents/gpd-verifier.md"]

    for path in verifier_files:
        content = path.read_text(encoding="utf-8")
        assert "{GPD_INSTALL_DIR}/learned-patterns/" not in content, path
        assert "GPD_PATTERNS_ROOT" in content, path

    learned_pattern_template = (TEMPLATES_DIR / "learned-pattern.md").read_text(encoding="utf-8")
    assert "learned-patterns/patterns-by-domain/" in learned_pattern_template


def test_workflow_task_prompts_do_not_embed_at_references() -> None:
    invalid: list[str] = []

    for path in sorted(WORKFLOWS_DIR.rglob("*.md")):
        content = path.read_text(encoding="utf-8")
        for match in re.finditer(r"task\([\s\S]*?\)", content):
            if "@{GPD_INSTALL_DIR}" in match.group(0):
                invalid.append(str(path.relative_to(REPO_ROOT)))
                break

    assert invalid == []


def test_review_commands_expose_typed_contracts() -> None:
    write_paper = registry.get_command("gpd:write-paper")
    peer_review = registry.get_command("peer-review")
    verify_work = registry.get_command("verify-work")
    respond_to_referees = registry.get_command("respond-to-referees")

    assert write_paper.review_contract is not None
    assert write_paper.review_contract.review_mode == "publication"
    assert "artifact manifest" in write_paper.review_contract.required_evidence

    assert peer_review.review_contract is not None
    assert peer_review.review_contract.review_mode == "publication"
    assert ".gpd/REFEREE-REPORT.md" in peer_review.review_contract.required_outputs
    assert "manuscript" in peer_review.review_contract.preflight_checks

    assert verify_work.review_contract is not None
    assert verify_work.review_contract.required_state == "phase_executed"
    assert "phase_artifacts" in verify_work.review_contract.preflight_checks

    assert respond_to_referees.review_contract is not None
    assert "structured referee issues" in respond_to_referees.review_contract.required_evidence
    assert "gpd:write-paper" in registry.list_review_commands()
    assert "gpd:peer-review" in registry.list_review_commands()
