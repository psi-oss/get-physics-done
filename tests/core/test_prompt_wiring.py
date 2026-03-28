"""Regression tests for prompt/template wiring."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

import pytest

from gpd import registry
from gpd.adapters.install_utils import expand_at_includes
from gpd.adapters.runtime_catalog import iter_runtime_descriptors
from gpd.contracts import ResearchContract, VerificationEvidence
from gpd.core.frontmatter import validate_frontmatter
from gpd.core.surface_phrases import (
    cost_after_runs_guidance,
    cost_summary_surface_note,
    local_cli_bridge_note,
    recovery_ladder_note,
)
from gpd.registry import _parse_frontmatter, _parse_tools
from scripts.repo_graph_contract import parse_scope_count


@pytest.fixture(autouse=True)
def _clean_registry_cache():
    """Ensure fresh registry cache for each test."""
    from gpd import registry
    registry.invalidate_cache()
    yield
    registry.invalidate_cache()


REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATES_DIR = REPO_ROOT / "src/gpd/specs/templates"
WORKFLOWS_DIR = REPO_ROOT / "src/gpd/specs/workflows"
COMMANDS_DIR = REPO_ROOT / "src/gpd/commands"
AGENTS_DIR = REPO_ROOT / "src/gpd/agents"
REFERENCES_DIR = REPO_ROOT / "src/gpd/specs/references"
FIXTURES_STAGE0 = REPO_ROOT / "tests" / "fixtures" / "stage0"
FIXTURES_STAGE4 = REPO_ROOT / "tests" / "fixtures" / "stage4"
GRAPH_PATH = REPO_ROOT / "tests" / "README.md"
WORKFLOW_EXEMPT_COMMANDS = frozenset({"health", "suggest-next"})

COMMAND_SPAWN_TOKENS = {
    "explain.md": ["gpd-explainer", "gpd-bibliographer"],
    "literature-review.md": ["gpd-literature-reviewer"],
    "debug.md": ["gpd-debugger"],
    "map-research.md": ["gpd-research-mapper"],
    "plan-phase.md": ["gpd-planner", "gpd-plan-checker"],
    "quick.md": ["gpd-planner", "gpd-executor"],
    "research-phase.md": ["gpd-phase-researcher"],
    "write-paper.md": [
        "gpd-paper-writer",
        "gpd-bibliographer",
        "gpd-review-reader",
        "gpd-review-literature",
        "gpd-review-math",
        "gpd-review-physics",
        "gpd-review-significance",
        "gpd-referee",
    ],
    "peer-review.md": [
        "gpd-review-reader",
        "gpd-review-literature",
        "gpd-review-math",
        "gpd-review-physics",
        "gpd-review-significance",
        "gpd-referee",
    ],
}

WORKFLOW_SPAWN_TOKENS = {
    "explain.md": ["gpd-explainer", "gpd-bibliographer"],
    "plan-phase.md": ["gpd-phase-researcher", "gpd-planner", "gpd-plan-checker", "gpd-experiment-designer"],
    "execute-phase.md": [
        "gpd-executor",
        "gpd-debugger",
        "gpd-verifier",
        "gpd-consistency-checker",
        "gpd-notation-coordinator",
        "gpd-experiment-designer",
    ],
    "verify-work.md": ["gpd-planner", "gpd-plan-checker"],
    "write-paper.md": ["gpd-paper-writer", "gpd-bibliographer", "gpd-referee"],
    "peer-review.md": [
        "gpd-review-reader",
        "gpd-review-literature",
        "gpd-review-math",
        "gpd-review-physics",
        "gpd-review-significance",
        "gpd-referee",
    ],
    "new-project.md": [
        "gpd-project-researcher",
        "gpd-research-synthesizer",
        "gpd-roadmapper",
        "gpd-notation-coordinator",
    ],
    "new-milestone.md": ["gpd-project-researcher", "gpd-research-synthesizer", "gpd-roadmapper"],
}

AGENT_REFERENCE_TOKENS = {
    "gpd-bibliographer.md": [
        "references/shared/shared-protocols.md",
        "references/orchestration/agent-infrastructure.md",
        "references/physics-subfields.md",
        "references/publication/publication-pipeline-modes.md",
        "templates/notation-glossary.md",
        "references/publication/bibtex-standards.md",
    ],
    "gpd-explainer.md": [
        "references/shared/shared-protocols.md",
        "references/orchestration/agent-infrastructure.md",
        "references/physics-subfields.md",
        "templates/notation-glossary.md",
    ],
    "gpd-consistency-checker.md": [
        "references/shared/shared-protocols.md",
        "references/orchestration/agent-infrastructure.md",
        "references/physics-subfields.md",
        "references/verification/core/verification-core.md",
        "references/shared/cross-project-patterns.md",
        "references/examples/contradiction-resolution-example.md",
        "references/verification/meta/verification-hierarchy-mapping.md",
        "templates/uncertainty-budget.md",
        "templates/conventions.md",
    ],
    "gpd-debugger.md": [
        "references/shared/shared-protocols.md",
        "references/orchestration/agent-infrastructure.md",
        "references/physics-subfields.md",
        "references/verification/core/verification-core.md",
        "references/shared/cross-project-patterns.md",
        "workflows/record-insight.md",
    ],
    "gpd-executor.md": [
        "references/shared/shared-protocols.md",
        "references/orchestration/agent-infrastructure.md",
        "references/shared/cross-project-patterns.md",
        "references/tooling/tool-integration.md",
        "references/execution/executor-index.md",
        "references/execution/executor-subfield-guide.md",
        "references/execution/executor-deviation-rules.md",
        "references/execution/executor-verification-flows.md",
        "references/execution/executor-task-checkpoints.md",
        "references/execution/executor-completion.md",
        "references/execution/executor-worked-example.md",
        "references/protocols/order-of-limits.md",
        "references/methods/approximation-selection.md",
        "references/verification/errors/llm-physics-errors.md",
        "references/verification/core/code-testing-physics.md",
        "references/orchestration/checkpoints.md",
        "templates/state-machine.md",
        "templates/summary.md",
        "templates/contract-results-schema.md",
        "templates/calculation-log.md",
    ],
    "gpd-experiment-designer.md": [
        "references/shared/shared-protocols.md",
        "references/orchestration/agent-infrastructure.md",
        "references/examples/ising-experiment-design-example.md",
    ],
    "gpd-notation-coordinator.md": [
        "references/shared/shared-protocols.md",
        "references/orchestration/agent-infrastructure.md",
        "references/conventions/subfield-convention-defaults.md",
        "templates/conventions.md",
    ],
    "gpd-paper-writer.md": [
        "references/shared/shared-protocols.md",
        "references/orchestration/agent-infrastructure.md",
        "references/publication/publication-pipeline-modes.md",
        "templates/notation-glossary.md",
        "templates/latex-preamble.md",
        "references/publication/figure-generation-templates.md",
    ],
    "gpd-review-reader.md": [
        "references/shared/shared-protocols.md",
        "references/orchestration/agent-infrastructure.md",
        "references/publication/peer-review-panel.md",
    ],
    "gpd-review-literature.md": [
        "references/shared/shared-protocols.md",
        "references/orchestration/agent-infrastructure.md",
        "references/publication/publication-pipeline-modes.md",
        "references/publication/peer-review-panel.md",
    ],
    "gpd-review-math.md": [
        "references/shared/shared-protocols.md",
        "references/physics-subfields.md",
        "references/verification/core/verification-core.md",
        "references/publication/peer-review-panel.md",
    ],
    "gpd-review-physics.md": [
        "references/shared/shared-protocols.md",
        "references/physics-subfields.md",
        "references/verification/core/verification-core.md",
        "references/publication/peer-review-panel.md",
    ],
    "gpd-review-significance.md": [
        "references/shared/shared-protocols.md",
        "references/orchestration/agent-infrastructure.md",
        "references/publication/publication-pipeline-modes.md",
        "references/publication/peer-review-panel.md",
    ],
    "gpd-phase-researcher.md": [
        "references/shared/shared-protocols.md",
        "references/orchestration/agent-infrastructure.md",
        "references/physics-subfields.md",
        "references/research/research-modes.md",
    ],
    "gpd-plan-checker.md": [
        "references/shared/shared-protocols.md",
        "references/orchestration/agent-infrastructure.md",
        "references/physics-subfields.md",
        "references/verification/core/verification-core.md",
    ],
    "gpd-planner.md": [
        "references/shared/shared-protocols.md",
        "references/orchestration/agent-infrastructure.md",
        "references/physics-subfields.md",
        "references/verification/core/verification-core.md",
        "templates/planner-subagent-prompt.md",
        "templates/phase-prompt.md",
        "templates/parameter-table.md",
        "templates/summary.md",
        "workflows/execute-plan.md",
        "references/protocols/order-of-limits.md",
        "references/methods/approximation-selection.md",
        "references/verification/core/code-testing-physics.md",
        "references/orchestration/checkpoints.md",
        "references/planning/planner-conventions.md",
        "references/planning/planner-approximations.md",
        "references/planning/planner-scope-examples.md",
        "references/planning/planner-tdd.md",
        "references/planning/planner-iterative.md",
        "references/protocols/hypothesis-driven-research.md",
    ],
    "gpd-project-researcher.md": [
        "references/shared/shared-protocols.md",
        "references/orchestration/agent-infrastructure.md",
        "references/research/research-modes.md",
    ],
    "gpd-referee.md": [
        "references/shared/shared-protocols.md",
        "references/orchestration/agent-infrastructure.md",
        "references/physics-subfields.md",
        "references/verification/core/verification-core.md",
        "references/publication/publication-pipeline-modes.md",
        "references/publication/peer-review-panel.md",
        "templates/paper/referee-report.tex",
    ],
    "gpd-research-synthesizer.md": [
        "references/shared/shared-protocols.md",
        "references/orchestration/agent-infrastructure.md",
        "templates/research-project/SUMMARY.md",
    ],
    "gpd-roadmapper.md": [
        "references/shared/shared-protocols.md",
        "references/orchestration/agent-infrastructure.md",
        "templates/roadmap.md",
        "templates/state.md",
    ],
    "gpd-research-mapper.md": [
        "references/shared/shared-protocols.md",
        "references/orchestration/agent-infrastructure.md",
        "references/physics-subfields.md",
        "references/templates/research-mapper/FORMALISM.md",
        "references/templates/research-mapper/REFERENCES.md",
        "references/templates/research-mapper/ARCHITECTURE.md",
        "references/templates/research-mapper/STRUCTURE.md",
        "references/templates/research-mapper/CONVENTIONS.md",
        "references/templates/research-mapper/VALIDATION.md",
        "references/templates/research-mapper/CONCERNS.md",
    ],
    "gpd-verifier.md": [
        "references/shared/shared-protocols.md",
        "references/physics-subfields.md",
        "references/verification/core/verification-core.md",
        "references/research/research-modes.md",
        "references/verification/meta/verification-hierarchy-mapping.md",
        "references/verification/core/computational-verification-templates.md",
    ],
}


def _assert_contains_tokens(path: Path, tokens: list[str]) -> None:
    content = path.read_text(encoding="utf-8")
    missing = [token for token in tokens if token not in content]
    assert missing == [], f"{path.relative_to(REPO_ROOT)} missing {missing}"


def _expand_prompt_surface(path: Path) -> str:
    return expand_at_includes(
        path.read_text(encoding="utf-8"),
        REPO_ROOT / "src/gpd/specs",
        "/runtime/",
    )


def _extract_between(content: str, start_marker: str, end_marker: str) -> str:
    start = content.index(start_marker) + len(start_marker)
    end = content.index(end_marker, start)
    return content[start:end]


def test_planner_templates_exist():
    planner_prompt = TEMPLATES_DIR / "planner-subagent-prompt.md"
    phase_prompt = TEMPLATES_DIR / "phase-prompt.md"

    assert planner_prompt.exists()
    assert phase_prompt.exists()
    assert "template_version: 1" in planner_prompt.read_text(encoding="utf-8")
    assert "template_version: 1" in phase_prompt.read_text(encoding="utf-8")
    assert "<planning_context>" in planner_prompt.read_text(encoding="utf-8")
    assert "contract:" in phase_prompt.read_text(encoding="utf-8")
    assert "acceptance_tests:" in phase_prompt.read_text(encoding="utf-8")
    assert "uncertainty_markers:" in phase_prompt.read_text(encoding="utf-8")


def test_referee_latex_template_exists() -> None:
    referee_template = TEMPLATES_DIR / "paper" / "referee-report.tex"
    assert referee_template.exists()
    content = referee_template.read_text(encoding="utf-8")
    assert "template_version: 1" in content
    assert "\\RecommendationBadge" in content


def test_shared_protocols_require_permission_before_dependency_installs() -> None:
    shared = (REFERENCES_DIR / "shared" / "shared-protocols.md").read_text(encoding="utf-8")
    checkpoints = (REFERENCES_DIR / "orchestration" / "checkpoints.md").read_text(encoding="utf-8")
    verifier = (AGENTS_DIR / "gpd-verifier.md").read_text(encoding="utf-8")
    planner = (AGENTS_DIR / "gpd-planner.md").read_text(encoding="utf-8")

    assert "Agents must NEVER install dependencies silently." in shared
    assert "Ask the user before any install attempt" in shared
    assert "BasicTeX yourself (small macOS option, about 100MB)" in shared
    assert "Never install TeX automatically." not in checkpoints
    assert "install silently" not in checkpoints
    assert "ask the user before any install attempt" in checkpoints
    assert "ask the user before any install attempt" in verifier
    assert "permission-gated" in planner


def test_agent_infrastructure_requires_concrete_next_actions_and_continuation_block() -> None:
    infra = (REFERENCES_DIR / "orchestration" / "agent-infrastructure.md").read_text(encoding="utf-8")

    assert "Prefer copy-pasteable GPD commands" in infra
    assert "references/orchestration/continuation-format.md" in infra
    assert "## > Next Up" in infra


def test_executor_completion_examples_use_command_based_next_actions() -> None:
    completion = (REFERENCES_DIR / "execution" / "executor-completion.md").read_text(encoding="utf-8")

    assert '"/gpd:execute-phase {phase}"' in completion
    assert '"/gpd:show-phase {phase}"' in completion
    assert "gpd state validate" in completion
    assert "/gpd:sync-state" in completion
    assert "file_edit tool" not in completion


def test_referee_workflow_mentions_optional_pdf_compile_and_missing_tex_prompt() -> None:
    referee = (AGENTS_DIR / "gpd-referee.md").read_text(encoding="utf-8")
    peer_review = (WORKFLOWS_DIR / "peer-review.md").read_text(encoding="utf-8")

    assert "compile the latest referee-report `.tex` file to a matching `.pdf`" in referee
    assert "Do NOT install TeX yourself" in referee
    assert "Continue now with `GPD/REFEREE-REPORT{round_suffix}.md` + `GPD/REFEREE-REPORT{round_suffix}.tex` only" in peer_review
    assert "Authorize the agent to install TeX now" in peer_review


def test_executor_prompt_defaults_to_return_only_shared_state_updates() -> None:
    executor = (AGENTS_DIR / "gpd-executor.md").read_text(encoding="utf-8")

    assert "return shared-state updates to the orchestrator instead of writing `STATE.md` directly" in executor
    assert "Your job: Execute the research plan completely, checkpoint each step, create SUMMARY.md, update STATE.md." not in executor


def test_referee_prompt_no_longer_claims_read_only_artifact_policy() -> None:
    referee = (AGENTS_DIR / "gpd-referee.md").read_text(encoding="utf-8")

    assert "Only scoped review artifacts written, and changed paths reported in `gpd_return.files_written`" in referee
    assert "No files modified (read-only agent)" not in referee


def test_prompt_sources_do_not_use_stale_agent_install_paths():
    files = [
        REPO_ROOT / "src/gpd/specs/references/orchestration/agent-delegation.md",
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


def test_commands_reference_same_stem_workflows() -> None:
    workflow_stems = {path.stem for path in WORKFLOWS_DIR.glob("*.md")}

    for command_path in sorted(COMMANDS_DIR.glob("*.md")):
        if command_path.stem not in workflow_stems:
            continue
        expected = f"@{{GPD_INSTALL_DIR}}/workflows/{command_path.stem}.md"
        assert expected in command_path.read_text(encoding="utf-8"), command_path


def test_commands_are_workflow_backed_or_explicitly_exempt() -> None:
    workflow_stems = {path.stem for path in WORKFLOWS_DIR.glob("*.md")}
    command_stems = {path.stem for path in COMMANDS_DIR.glob("*.md")}

    assert command_stems - workflow_stems == WORKFLOW_EXEMPT_COMMANDS

    for command_stem in sorted(WORKFLOW_EXEMPT_COMMANDS):
        command_text = (COMMANDS_DIR / f"{command_stem}.md").read_text(encoding="utf-8")
        if command_stem == "health":
            assert "gpd --raw health" in command_text
            assert "@{GPD_INSTALL_DIR}/workflows/health.md" not in command_text
        elif command_stem == "suggest-next":
            assert "gpd --raw suggest" in command_text
            assert "Local CLI fallback: `gpd --raw suggest`" in command_text
            assert "@{GPD_INSTALL_DIR}/workflows/suggest-next.md" not in command_text


def test_commands_reference_expected_spawn_agents() -> None:
    for command_name, agent_tokens in COMMAND_SPAWN_TOKENS.items():
        _assert_contains_tokens(COMMANDS_DIR / command_name, agent_tokens)


def test_workflows_reference_expected_spawn_agents() -> None:
    for workflow_name, agent_tokens in WORKFLOW_SPAWN_TOKENS.items():
        _assert_contains_tokens(WORKFLOWS_DIR / workflow_name, agent_tokens)


def test_agents_reference_expected_shared_specs() -> None:
    for agent_name, reference_tokens in AGENT_REFERENCE_TOKENS.items():
        _assert_contains_tokens(AGENTS_DIR / agent_name, reference_tokens)


def test_review_commands_expose_typed_contracts() -> None:
    write_paper = registry.get_command("gpd:write-paper")
    peer_review = registry.get_command("peer-review")
    verify_work = registry.get_command("verify-work")
    respond_to_referees = registry.get_command("respond-to-referees")

    assert write_paper.review_contract is not None
    assert write_paper.review_contract.review_mode == "publication"
    assert "manuscript scaffold target (existing draft or bootstrap target)" in write_paper.review_contract.required_evidence
    assert "artifact manifest" in write_paper.review_contract.required_evidence
    assert "reproducibility manifest" in write_paper.review_contract.required_evidence
    assert "GPD/REFEREE-REPORT{round_suffix}.md" in write_paper.review_contract.required_outputs
    assert "GPD/REFEREE-REPORT{round_suffix}.tex" in write_paper.review_contract.required_outputs
    assert "manuscript" in write_paper.review_contract.preflight_checks

    assert peer_review.review_contract is not None
    assert peer_review.review_contract.review_mode == "publication"
    assert "GPD/REFEREE-REPORT{round_suffix}.md" in peer_review.review_contract.required_outputs
    assert "GPD/REFEREE-REPORT{round_suffix}.tex" in peer_review.review_contract.required_outputs
    assert "GPD/review/CLAIMS{round_suffix}.json" in peer_review.review_contract.required_outputs
    assert "GPD/review/STAGE-interestingness{round_suffix}.json" in peer_review.review_contract.required_outputs
    assert "GPD/review/REFEREE-DECISION{round_suffix}.json" in peer_review.review_contract.required_outputs
    assert "manuscript" in peer_review.review_contract.preflight_checks
    assert peer_review.review_contract.stage_ids == [
        "reader",
        "literature",
        "math",
        "physics",
        "interestingness",
        "meta",
    ]
    assert peer_review.review_contract.requires_fresh_context_per_stage is True
    assert peer_review.review_contract.stage_artifacts == [
        "GPD/review/CLAIMS{round_suffix}.json",
        "GPD/review/STAGE-reader{round_suffix}.json",
        "GPD/review/STAGE-literature{round_suffix}.json",
        "GPD/review/STAGE-math{round_suffix}.json",
        "GPD/review/STAGE-physics{round_suffix}.json",
        "GPD/review/STAGE-interestingness{round_suffix}.json",
        "GPD/review/REVIEW-LEDGER{round_suffix}.json",
        "GPD/review/REFEREE-DECISION{round_suffix}.json",
    ]
    assert peer_review.review_contract.final_decision_output == "GPD/review/REFEREE-DECISION{round_suffix}.json"

    assert verify_work.review_contract is not None
    assert verify_work.review_contract.required_state == "phase_executed"
    assert "phase_artifacts" in verify_work.review_contract.preflight_checks

    assert respond_to_referees.review_contract is not None
    assert "GPD/paper/REFEREE_RESPONSE{round_suffix}.md" in respond_to_referees.review_contract.required_outputs
    assert "GPD/AUTHOR-RESPONSE{round_suffix}.md" in respond_to_referees.review_contract.required_outputs
    assert "structured referee issues" in respond_to_referees.review_contract.required_evidence
    assert "peer-review review ledger when available" in respond_to_referees.review_contract.required_evidence
    assert "peer-review decision artifacts when available" in respond_to_referees.review_contract.required_evidence
    assert "gpd:peer-review" in registry.list_review_commands()
    assert "gpd:write-paper" in registry.list_review_commands()
    assert "gpd:respond-to-referees" in registry.list_review_commands()
    assert "gpd:verify-work" in registry.list_review_commands()


def test_representative_commands_expose_expected_context_modes() -> None:
    assert registry.get_command("help").context_mode == "global"
    assert registry.get_command("health").context_mode == "projectless"
    assert registry.get_command("compare-results").context_mode == "project-aware"
    assert registry.get_command("map-research").context_mode == "projectless"
    assert registry.get_command("slides").context_mode == "projectless"
    assert registry.get_command("discover").context_mode == "project-aware"
    assert registry.get_command("explain").context_mode == "project-aware"
    assert registry.get_command("suggest-next").context_mode == "projectless"
    assert registry.get_command("peer-review").context_mode == "project-required"


def test_slides_workflow_references_templates_and_existing_output_policy() -> None:
    workflow = (WORKFLOWS_DIR / "slides.md").read_text(encoding="utf-8")

    assert "{GPD_INSTALL_DIR}/templates/slides/presentation-brief.md" in workflow
    assert "{GPD_INSTALL_DIR}/templates/slides/outline.md" in workflow
    assert "{GPD_INSTALL_DIR}/templates/slides/slides.md" in workflow
    assert "{GPD_INSTALL_DIR}/templates/slides/speaker-notes.md" in workflow
    assert "{GPD_INSTALL_DIR}/templates/slides/main.tex" in workflow
    assert "1. Refresh" in workflow
    assert "2. Update" in workflow
    assert "3. Skip" in workflow


def test_representative_prompts_use_centralized_command_context_preflight() -> None:
    expected = {
        COMMANDS_DIR / "compare-experiment.md": "gpd --raw validate command-context compare-experiment",
        COMMANDS_DIR / "compare-results.md": "gpd --raw validate command-context compare-results",
        COMMANDS_DIR / "dimensional-analysis.md": "gpd --raw validate command-context dimensional-analysis",
        COMMANDS_DIR / "explain.md": "gpd --raw validate command-context explain",
        COMMANDS_DIR / "limiting-cases.md": "gpd --raw validate command-context limiting-cases",
        COMMANDS_DIR / "literature-review.md": "gpd --raw validate command-context literature-review",
        COMMANDS_DIR / "sensitivity-analysis.md": "gpd --raw validate command-context sensitivity-analysis",
        WORKFLOWS_DIR / "peer-review.md": "gpd --raw validate command-context peer-review",
        WORKFLOWS_DIR / "progress.md": "gpd --raw validate command-context progress",
    }

    for path, token in expected.items():
        assert token in path.read_text(encoding="utf-8"), path


def test_list_review_commands_contains_all_expected_commands() -> None:
    """Regression: line 307 duplicated the gpd:peer-review check instead of
    testing gpd:respond-to-referees and gpd:verify-work."""
    review_cmds = registry.list_review_commands()
    expected = {"gpd:peer-review", "gpd:write-paper", "gpd:respond-to-referees", "gpd:verify-work"}
    assert expected <= set(review_cmds), f"Missing review commands: {expected - set(review_cmds)}"


def test_list_review_commands_no_duplicates() -> None:
    """Each review command should appear exactly once."""
    review_cmds = registry.list_review_commands()
    assert len(review_cmds) == len(set(review_cmds))


def test_respond_to_referees_references_staged_review_artifacts() -> None:
    command_text = (COMMANDS_DIR / "respond-to-referees.md").read_text(encoding="utf-8")
    workflow_text = (WORKFLOWS_DIR / "respond-to-referees.md").read_text(encoding="utf-8")
    writer_text = (AGENTS_DIR / "gpd-paper-writer.md").read_text(encoding="utf-8")

    assert "argument-hint: \"[path to referee report or 'paste']\"" in command_text
    assert "GPD/review/REVIEW-LEDGER{round_suffix}.json" in command_text
    assert "GPD/review/REFEREE-DECISION{round_suffix}.json" in command_text
    assert "Use the literal `paste` sentinel" in workflow_text
    assert "REVIEW-LEDGER*.json" in workflow_text
    assert "REFEREE-DECISION*.json" in workflow_text
    assert "REVIEW-LEDGER{-RN}.json" in writer_text
    assert "REFEREE-DECISION{-RN}.json" in writer_text


def test_review_workflows_keep_round_suffix_artifacts_visible_and_anchor_response_outputs() -> None:
    peer_review = (COMMANDS_DIR / "peer-review.md").read_text(encoding="utf-8")
    respond = (WORKFLOWS_DIR / "respond-to-referees.md").read_text(encoding="utf-8")
    write_paper = (WORKFLOWS_DIR / "write-paper.md").read_text(encoding="utf-8")
    panel = (REFERENCES_DIR / "publication" / "peer-review-panel.md").read_text(encoding="utf-8")

    assert "GPD/review/CLAIMS{round_suffix}.json" in peer_review
    assert "GPD/review/REVIEW-LEDGER{round_suffix}.json" in peer_review
    assert "GPD/review/REFEREE-DECISION{round_suffix}.json" in peer_review
    assert "GPD/REFEREE-REPORT{round_suffix}.md" in peer_review
    assert "GPD/REFEREE-REPORT{round_suffix}.tex" in panel
    assert "Stage 1 `CLAIMS{round_suffix}.json` must follow this compact `ClaimIndex` shape:" in panel
    assert "ClaimIndex` and every nested `ClaimRecord` use a closed schema; do not invent extra keys" in panel
    assert "`manuscript_path` must be non-empty" in panel
    assert "JSON `round` field must agree" in panel
    assert "must exactly match the sibling `CLAIMS{round_suffix}.json`" in panel
    assert "Stage 1 `CLAIMS.json` must follow this compact `ClaimIndex` shape:" not in panel

    assert "${PAPER_DIR}/{section}.tex" in respond
    assert "${PAPER_DIR}/BIBLIOGRAPHY-AUDIT.json" in respond
    assert "${PAPER_DIR}/response-letter.tex" in respond
    assert "GPD/paper/REFEREE_RESPONSE{round_suffix}.md" in respond
    assert "GPD/AUTHOR-RESPONSE{round_suffix}.md" in respond

    assert "CLAIMS{round_suffix}.json" in write_paper
    assert "REVIEW-LEDGER{round_suffix}.json" in write_paper
    assert "REFEREE-DECISION{round_suffix}.json" in write_paper
    assert "GPD/REFEREE-REPORT{round_suffix}.md" in write_paper


def test_publication_commands_accept_documented_manuscript_layouts() -> None:
    peer_review = (COMMANDS_DIR / "peer-review.md").read_text(encoding="utf-8")
    respond = (COMMANDS_DIR / "respond-to-referees.md").read_text(encoding="utf-8")
    arxiv = (COMMANDS_DIR / "arxiv-submission.md").read_text(encoding="utf-8")

    for content in (peer_review, respond, arxiv):
        assert 'files: ["paper/*.tex", "manuscript/*.tex", "draft/*.tex"]' in content

    assert "peer-review review ledger when available" in arxiv
    assert "peer-review referee decision when available" in arxiv
    assert "latest `REVIEW-LEDGER{round_suffix}.json` / `REFEREE-DECISION{round_suffix}.json` outcome" in arxiv
    assert "resolve only from `paper/`, `manuscript/`, or `draft/`" in arxiv
    assert 'find . -name "main.tex"' not in arxiv


def test_write_paper_and_arxiv_submission_keep_the_build_boundary_explicit() -> None:
    write_paper = (WORKFLOWS_DIR / "write-paper.md").read_text(encoding="utf-8")
    arxiv = (WORKFLOWS_DIR / "arxiv-submission.md").read_text(encoding="utf-8")

    assert 'gpd paper-build "${PAPER_DIR}/PAPER-CONFIG.json" --output-dir "${PAPER_DIR}"' in write_paper
    assert "This emits `${PAPER_DIR}/main.tex`, writes the artifact manifest" in write_paper
    assert (
        "The workflow continues without local compilation smoke checks — .tex file generation does not require "
        "pdflatex, and `gpd paper-build` remains the canonical manuscript scaffold contract."
    ) in write_paper
    assert 'gpd paper-build "${PAPER_DIR}/PAPER-CONFIG.json" --output-dir "${PAPER_DIR}"' in arxiv
    assert "WARNING: pdflatex is not available, so local compilation smoke checks will be skipped." in arxiv
    assert "The paper-build artifact contract still allows packaging to continue." in arxiv
    assert "Do not treat manual `pdflatex` runs as the source of build truth." in arxiv


def test_remove_phase_workflow_stages_checkpoint_shelf_updates() -> None:
    workflow = (WORKFLOWS_DIR / "remove-phase.md").read_text(encoding="utf-8")

    assert "checkpoint shelf artifacts" in workflow
    assert "GPD/CHECKPOINTS.md" in workflow
    assert "GPD/phase-checkpoints" in workflow


def test_new_project_recommended_autonomy_matches_balanced_default() -> None:
    workflow_text = (WORKFLOWS_DIR / "new-project.md").read_text(encoding="utf-8")

    assert workflow_text.count('"autonomy": "balanced"') >= 2
    assert "Which starting workflow preset should GPD use for `GPD/config.json`?" in workflow_text
    assert '"Core research (Recommended)"' in workflow_text
    assert '"Theory"' in workflow_text
    assert '"Numerics"' in workflow_text
    assert '"Publication / manuscript"' in workflow_text
    assert '"Full research"' in workflow_text
    assert (
        "`autonomy=balanced`, `research_mode=balanced`, `parallelization=true`, "
        "`planning.commit_docs=true`, `execution.review_cadence=adaptive`"
    ) in workflow_text
    assert (
        "Config: Balanced autonomy | Adaptive review cadence | Balanced research mode | Parallel | All agents | Review profile"
        in workflow_text
    )
    assert "Recommended defaults use YOLO autonomy" not in workflow_text
    assert "Config: YOLO autonomy | Balanced research mode | Parallel | All agents | Review profile" not in workflow_text


def test_settings_and_new_project_surface_runtime_permission_sync_for_yolo() -> None:
    new_project = (WORKFLOWS_DIR / "new-project.md").read_text(encoding="utf-8")
    settings = (WORKFLOWS_DIR / "settings.md").read_text(encoding="utf-8")

    assert 'gpd --raw permissions sync --autonomy "$SELECTED_AUTONOMY"' in new_project
    assert 'gpd --raw permissions sync --autonomy "$SELECTED_AUTONOMY"' in settings
    assert "sync the active runtime to its most autonomous permission mode when supported" in new_project
    assert "syncs the runtime to its most autonomous permission mode when supported" in settings
    assert "This sync only updates runtime-owned permission settings; it does not create or validate the base install or workflow-tool readiness." in new_project
    assert "This sync only updates runtime-owned permission settings; it does not validate install health or workflow/tool readiness." in settings
    assert "| Runtime Permissions  | {aligned / changed / manual follow-up required} |" in settings
    assert "If `requires_relaunch` is `true`, show `next_step` verbatim" in new_project


def test_new_project_requires_scoping_contract_across_setup_modes() -> None:
    workflow_text = (WORKFLOWS_DIR / "new-project.md").read_text(encoding="utf-8")
    command_text = (COMMANDS_DIR / "new-project.md").read_text(encoding="utf-8")

    assert "Auto mode compresses intake; it does not override autonomy review gates after the scoping contract is approved" in workflow_text
    assert "Require one explicit scoping approval gate before requirements and roadmap generation" in workflow_text
    assert "Roadmap approval: Auto-approve only for `balanced` / `yolo`; if `autonomy=supervised`, present the draft roadmap before commit" in workflow_text
    assert "Minimal mode is still allowed to be lean, but it is not allowed to be contract-free." in workflow_text
    assert "At least one concrete anchor, reference, prior-output constraint, or baseline" in workflow_text
    assert "If the decisive anchor is still unknown, keep that blocker explicit" in workflow_text
    assert "scope.unresolved_questions`, `context_intake.context_gaps`, or `uncertainty_markers.weakest_anchors`" in workflow_text
    assert "Do not approve a scoping contract that strips decisive outputs, anchors, prior outputs, or review/stop triggers down to generic placeholders." in workflow_text
    assert "Do NOT skip the initial scoping-contract approval gate." in workflow_text
    assert "scoping contract with decisive outputs, anchors, and explicit approval" in command_text


def test_new_project_wiring_mentions_contract_persistence_and_contract_first_downstream_generation() -> None:
    workflow_text = (WORKFLOWS_DIR / "new-project.md").read_text(encoding="utf-8")
    command_text = (COMMANDS_DIR / "new-project.md").read_text(encoding="utf-8")

    assert "gpd state set-project-contract" in workflow_text
    assert "gpd --raw validate project-contract -" in workflow_text
    assert "gpd state set-project-contract -" in workflow_text
    assert "/tmp/gpd-project-contract.json" not in workflow_text
    assert "temporary JSON file if needed" not in workflow_text
    assert "Parse JSON for: `researcher_model`, `synthesizer_model`, `roadmapper_model`, `commit_docs`, `autonomy`, `research_mode`, `project_exists`, `has_research_map`, `planning_exists`, `has_research_files`, `has_project_manifest`, `has_existing_project`, `needs_research_map`, `has_git`, `project_contract`, `project_contract_load_info`, `project_contract_validation`." in workflow_text
    assert "If `project_contract` is present in the init JSON, keep `project_contract`, `project_contract_load_info`, and `project_contract_validation` visible while deciding whether this is fresh work or a continuation." in workflow_text
    assert "If the init JSON already contains `project_contract`, `project_contract_load_info`, or `project_contract_validation`, preserve that state in the approval gate and continuation decision." in workflow_text
    assert "Read PROJECT.md and `GPD/state.json` and extract" in workflow_text
    assert "Derive phases from requirements AND the approved project contract" in workflow_text
    assert "If auto mode and `autonomy` is not `supervised`" in workflow_text
    assert "@{GPD_INSTALL_DIR}/templates/state-json-schema.md" in command_text


def test_new_project_defers_workflow_setup_until_after_scope_approval() -> None:
    workflow_text = (WORKFLOWS_DIR / "new-project.md").read_text(encoding="utf-8")
    command_text = (COMMANDS_DIR / "new-project.md").read_text(encoding="utf-8")

    assert "Before `GPD/config.json` exists, the `autonomy` and `research_mode` values from `gpd init new-project` are temporary defaults" in workflow_text
    assert "## 2.5 Early Workflow Setup" not in workflow_text
    assert "What physics problem do you want to investigate?" in workflow_text
    assert "If `GPD/config.json` does not exist yet, run Step 5 now before generating or committing `PROJECT.md`." in workflow_text
    assert "Run this step after scope approval and before the first project-artifact commit whenever `GPD/config.json` does not exist yet." in workflow_text
    assert "If Step 2.5 already captured provisional setup preferences" not in workflow_text
    assert "workflow opens with the physics-questioning pass" in command_text
    assert "surfaces a preset choice before writing workflow preferences" in command_text
    assert "only asks the detailed config questions after scope approval" in command_text


def test_questioning_guide_requires_anchors_and_disconfirming_questions() -> None:
    guide_text = (REFERENCES_DIR / "research" / "questioning.md").read_text(encoding="utf-8")

    assert "Surface anchors early." in guide_text
    assert "Preserve the user's guidance." in guide_text
    assert "Pressure-test the first story." in guide_text
    assert "Once you have a plausible framing on the table" in guide_text
    assert "Do not force decomposition too early." in guide_text
    assert "Ground-truth anchors -- what reality should constrain this:" in guide_text
    assert "Disconfirmation and failure -- how the current framing could be wrong:" in guide_text
    assert "Lack of a full phase list is not itself a blocker." in guide_text
    assert "Do not count turns mechanically." in guide_text
    assert "What would be a misleading proxy for success" in guide_text


def test_new_project_questioning_requires_smoking_gun_and_rejects_proxy_only_readiness() -> None:
    workflow_text = (WORKFLOWS_DIR / "new-project.md").read_text(encoding="utf-8")
    guide_text = (REFERENCES_DIR / "research" / "questioning.md").read_text(encoding="utf-8")

    assert "What first smoking-gun observable, curve, benchmark reproduction, or scaling law they would trust before softer sanity checks" in workflow_text
    assert "Whether passing limiting cases, generic expectations, or qualitative agreement without that smoking gun should still count as failure" in workflow_text
    assert 'Demand the smoking gun ("What exact check would make you trust this over softer sanity checks?")' in workflow_text
    assert "If you only have limiting cases, sanity checks, or generic benchmark language with no decisive smoking-gun observable" in workflow_text
    assert "especially the first smoking-gun check they would trust over softer proxies or limiting cases" in workflow_text
    assert "If the only checks captured so far are limiting cases, sanity checks, or qualitative expectations, treat the contract as still underspecified" in workflow_text
    assert "Push until you know the first hard correctness check or smoking-gun signal they would trust" in guide_text
    assert "What is the first smoking-gun observable, scaling law, curve, or benchmark" in guide_text
    assert "If the result passed a few limiting cases or sanity checks but missed the smoking-gun check" in guide_text
    assert (
        "Do not offer the gate if you only have proxy checks, sanity checks, or limiting cases and still lack "
        "concrete reference/prior-output/baseline grounding, even when the missing anchor is noted explicitly."
        in guide_text
    )


def test_project_and_context_templates_surface_contract_and_skeptical_review() -> None:
    project_text = (TEMPLATES_DIR / "project.md").read_text(encoding="utf-8")
    context_text = (TEMPLATES_DIR / "context.md").read_text(encoding="utf-8")
    requirements_text = (TEMPLATES_DIR / "requirements.md").read_text(encoding="utf-8")
    state_schema_text = (TEMPLATES_DIR / "state-json-schema.md").read_text(encoding="utf-8")

    assert "## Scoping Contract Summary" in project_text
    assert "### Contract Coverage" in project_text
    assert "### Active Anchor Registry" in project_text
    assert "### User Guidance To Preserve" in project_text
    assert "### Skeptical Review" in project_text
    assert "## Contract Coverage" in context_text
    assert "## Active Anchor Registry" in context_text
    assert "## User Guidance To Preserve" in context_text
    assert "## Skeptical Review" in context_text
    assert "## Contract Coverage" in requirements_text
    assert "disconfirming_observations" in state_schema_text


def test_discuss_and_assumption_workflows_surface_anchors_and_fast_falsifiers() -> None:
    discuss_text = (WORKFLOWS_DIR / "discuss-phase.md").read_text(encoding="utf-8")
    assumptions_text = (WORKFLOWS_DIR / "list-phase-assumptions.md").read_text(encoding="utf-8")

    assert "What prior output, benchmark, or reference must stay visible here?" in discuss_text
    assert "What would make this approach look wrong or incomplete early?" in discuss_text
    assert "## User Guidance To Preserve" in discuss_text
    assert "## Contract Coverage" in discuss_text
    assert "## Active Anchor Registry" in discuss_text
    assert "## Skeptical Review" in discuss_text
    assert "User Guidance I Am Treating As Binding" in assumptions_text
    assert "### Anchor Inputs" in assumptions_text
    assert "**Fast falsifier:**" in assumptions_text
    assert "**False progress:**" in assumptions_text


def test_discuss_and_plan_workflows_resolve_roadmap_only_phases() -> None:
    discuss_text = (WORKFLOWS_DIR / "discuss-phase.md").read_text(encoding="utf-8")
    plan_text = (WORKFLOWS_DIR / "plan-phase.md").read_text(encoding="utf-8")

    assert "Phase [X] not found in roadmap." not in discuss_text
    assert 'ROADMAP_INFO=$(gpd roadmap get-phase "${PHASE}")' in discuss_text
    assert 'phase_slug=$(gpd slug "$phase_name")' in discuss_text
    assert "Continue to check_existing using the roadmap-derived phase metadata." in discuss_text
    assert 'REQUESTED_PHASE="${PHASE}"' in plan_text
    assert 'PHASE=$(echo "$INIT" | gpd json get .phase_number --default "${REQUESTED_PHASE}")' in plan_text
    assert 'PHASE_INFO=$(gpd roadmap get-phase "${PHASE}")' in plan_text
    assert 'PHASE_SLUG=$(gpd slug "$PHASE_NAME")' in plan_text
    assert "Use these resolved values for all later references to `PHASE_DIR`, `PHASE_SLUG`, and `PADDED_PHASE`." in plan_text


def test_planning_and_phase_templates_surface_active_reference_context() -> None:
    planner_prompt = (TEMPLATES_DIR / "planner-subagent-prompt.md").read_text(encoding="utf-8")
    phase_prompt = (TEMPLATES_DIR / "phase-prompt.md").read_text(encoding="utf-8")
    workflow_text = (WORKFLOWS_DIR / "plan-phase.md").read_text(encoding="utf-8")

    assert "Planning requires an approved scoping contract." in planner_prompt
    assert "**Project Contract:** {project_contract}" in planner_prompt
    assert "**Active References:** {active_reference_context}" in planner_prompt
    assert "@path/to/reference-or-benchmark-anchor.md" in phase_prompt
    assert "Planning requires an approved scoping contract in `GPD/state.json`" in workflow_text
    assert "project_contract_validation" in workflow_text
    assert "project_contract_load_info" in workflow_text
    assert "visible-but-blocked contract is not an approved planning contract" in workflow_text
    assert "**Project Contract:** {project_contract}" in workflow_text
    assert "**Active References:** {active_reference_context}" in workflow_text
    assert "**Anchor coverage:** Required references, baselines, and prior outputs are surfaced" in workflow_text


def test_progress_workflow_surfaces_contract_load_and_validation_state() -> None:
    workflow_text = (WORKFLOWS_DIR / "progress.md").read_text(encoding="utf-8")
    command_text = (COMMANDS_DIR / "progress.md").read_text(encoding="utf-8")

    assert "project_contract_validation" in workflow_text
    assert "project_contract_load_info" in workflow_text
    assert "authoritative only when `project_contract_load_info` is clean and `project_contract_validation` passes" in workflow_text
    assert "structured load status, warnings, and blockers for the contract" in workflow_text
    status_scan = 'grep -l -E "^(status: (gaps_found|human_needed|expert_needed)|session_status: diagnosed)$"'
    assert status_scan in workflow_text
    assert status_scan in command_text
    assert 'status: (gaps_found|diagnosed|human_needed|expert_needed)' not in workflow_text
    assert 'status: (gaps_found|diagnosed|human_needed|expert_needed)' not in command_text
    assert "`session_status: diagnosed`" in workflow_text
    assert "`session_status: diagnosed`" in command_text
    assert "GPD/phases/[current-phase-dir]/*-VERIFICATION.md" in workflow_text
    assert "GPD/phases/[current-phase-dir]/*-VERIFICATION.md" in command_text


def test_planning_prompts_keep_contract_gate_in_light_mode_and_all_modes() -> None:
    planner_prompt = (TEMPLATES_DIR / "planner-subagent-prompt.md").read_text(encoding="utf-8")
    planner_agent = (AGENTS_DIR / "gpd-planner.md").read_text(encoding="utf-8")
    checker_agent = (AGENTS_DIR / "gpd-plan-checker.md").read_text(encoding="utf-8")
    workflow_text = (WORKFLOWS_DIR / "plan-phase.md").read_text(encoding="utf-8")

    assert "Light mode changes verbosity, not contract completeness." in planner_prompt
    assert "Autonomy mode and model profile may change cadence or detail, but they do NOT relax contract completeness." in planner_prompt
    assert "Profiles may compress detail, but they do NOT relax contract completeness." in planner_agent
    assert "All modes still require contract completeness, decisive outputs, required anchors, forbidden-proxy handling, and disconfirming paths before execution starts." in workflow_text
    assert "Human review does not replace those requirements." in checker_agent


def test_plan_checker_requires_contract_gate_and_reference_artifacts() -> None:
    checker_agent = (AGENTS_DIR / "gpd-plan-checker.md").read_text(encoding="utf-8")
    workflow_text = (WORKFLOWS_DIR / "plan-phase.md").read_text(encoding="utf-8")

    assert "## Dimension 0: Contract Gate" in checker_agent
    assert "contract_decisive_output" in checker_agent
    assert "contract_anchor_coverage" in checker_agent
    assert "proxy_only_success_path" in checker_agent
    assert "**Reference Artifacts:** {reference_artifacts_content}" in workflow_text
    assert "**Decisive outputs:** The plan set covers decisive claims and deliverables" in workflow_text
    assert "**Acceptance tests:** Every decisive claim or deliverable has at least one executable or reviewable test" in workflow_text
    assert "**Forbidden proxies:** Proxy-only success conditions are rejected explicitly" in workflow_text


def test_roadmap_template_and_workflows_surface_phase_contract_coverage() -> None:
    roadmap_template = (TEMPLATES_DIR / "roadmap.md").read_text(encoding="utf-8")
    state_template = (TEMPLATES_DIR / "state.md").read_text(encoding="utf-8")
    roadmapper_agent = (AGENTS_DIR / "gpd-roadmapper.md").read_text(encoding="utf-8")
    new_project = (WORKFLOWS_DIR / "new-project.md").read_text(encoding="utf-8")
    new_milestone = (WORKFLOWS_DIR / "new-milestone.md").read_text(encoding="utf-8")

    assert "## Contract Overview" in roadmap_template
    assert "**Contract Coverage:**" in roadmap_template
    assert "@{GPD_INSTALL_DIR}/templates/roadmap.md" in roadmapper_agent
    assert "@{GPD_INSTALL_DIR}/templates/state.md" in roadmapper_agent
    assert "Contract coverage" in roadmapper_agent
    assert "Phase Details" in roadmapper_agent
    assert "Active Calculations" in roadmapper_agent
    assert "Intermediate Results" in state_template
    assert "forbidden proxies a phase must carry" in roadmapper_agent
    assert "Phase counts are heuristics, not quotas" in roadmapper_agent
    assert "Do not pad the roadmap with speculative phases just to make it look complete." in roadmapper_agent
    assert "return `## ROADMAP BLOCKED`" in roadmapper_agent
    assert (
        "Treat `context_intake.must_read_refs`, `must_include_prior_outputs`, "
        "`user_asserted_anchors`, `known_good_baselines`, and `crucial_inputs` "
        "as binding user guidance"
    ) in roadmapper_agent
    assert "For each phase, include explicit contract coverage in ROADMAP.md" in new_project
    assert "For each phase, include explicit contract coverage in ROADMAP.md" in new_milestone
    assert "Do NOT skip the initial scoping-contract approval gate." in new_project
    assert "Do NOT skip the requirement to show contract coverage in the roadmap." in new_project


def test_new_project_minimal_mode_and_planning_wiring_allow_coarse_scoped_decomposition() -> None:
    workflow_text = (WORKFLOWS_DIR / "new-project.md").read_text(encoding="utf-8")
    planner_prompt = (TEMPLATES_DIR / "planner-subagent-prompt.md").read_text(encoding="utf-8")

    assert "whether the anchor is still unknown" in workflow_text
    assert "Do not force a phase list just to make the scoping contract look complete." in workflow_text
    assert (
        "If the user does not know the anchor yet, preserve that explicitly in `scope.unresolved_questions`, "
        "`context_intake.context_gaps`, or `uncertainty_markers.weakest_anchors` rather than inventing a paper, "
        "benchmark, or baseline."
        in workflow_text
    )
    assert 'If the user named a prior output, review checkpoint, or "come back to me before continuing" condition, carry it into `context_intake.must_include_prior_outputs` or `context_intake.crucial_inputs` rather than leaving it only in prose.' in workflow_text
    assert "A full phase breakdown is not required at this stage;" in workflow_text
    assert "Use the coarsest decomposition the approved contract actually supports." in workflow_text
    assert "Do NOT invent literature, numerics, or paper phases unless the requirements or contract demand them." in workflow_text
    assert "If `project_contract` is empty, stale, or too underspecified to identify the phase contract slice, return `## CHECKPOINT REACHED`" in planner_prompt


def test_reference_workflows_require_anchor_registry_propagation() -> None:
    literature_workflow = (WORKFLOWS_DIR / "literature-review.md").read_text(encoding="utf-8")
    literature_command = (COMMANDS_DIR / "literature-review.md").read_text(encoding="utf-8")
    literature_agent = (AGENTS_DIR / "gpd-literature-reviewer.md").read_text(encoding="utf-8")
    compare_workflow = (WORKFLOWS_DIR / "compare-results.md").read_text(encoding="utf-8")
    map_workflow = (WORKFLOWS_DIR / "map-research.md").read_text(encoding="utf-8")
    map_command = (COMMANDS_DIR / "map-research.md").read_text(encoding="utf-8")
    mapper_agent = (AGENTS_DIR / "gpd-research-mapper.md").read_text(encoding="utf-8")

    assert "contract-critical anchors" in literature_workflow
    assert "project_contract_load_info" in literature_workflow
    assert "project_contract_validation" in literature_workflow
    assert "authoritative only when `project_contract_load_info` is clean and `project_contract_validation` passes" in literature_workflow
    assert "Active Anchor Registry" in literature_command
    assert "active_anchors" in literature_agent
    assert "project_contract_load_info" in compare_workflow
    assert "project_contract_validation" in compare_workflow
    assert "active_reference_context" in compare_workflow
    assert "Treat `project_contract` as authoritative only when `project_contract_load_info` is clean and `project_contract_validation` passes." in compare_workflow
    assert "active_reference_context" in map_workflow
    assert "effective_reference_intake" in map_workflow
    assert "project_contract_load_info" in map_workflow
    assert "project_contract_validation" in map_workflow
    assert "reference_artifacts_content" in map_workflow
    assert "authoritative only when `project_contract_load_info` is clean and `project_contract_validation` passes" in map_workflow
    assert "Contract-critical anchors, decisive benchmarks, prior artifacts" in map_command
    assert "REFERENCES.md is an anchor registry" in mapper_agent


def test_file_producing_command_surfaces_use_canonical_spawn_contract() -> None:
    literature = (COMMANDS_DIR / "literature-review.md").read_text(encoding="utf-8")
    debug = (COMMANDS_DIR / "debug.md").read_text(encoding="utf-8")
    research = (COMMANDS_DIR / "research-phase.md").read_text(encoding="utf-8")

    for content, agent_name, file_token in (
        (literature, "gpd-literature-reviewer", "GPD/literature/{slug}-REVIEW.md"),
        (debug, "gpd-debugger", "GPD/debug/{slug}.md"),
        (research, "gpd-phase-researcher", "GPD/phases/${PHASE}-{slug}/${PHASE}-RESEARCH.md"),
    ):
        assert f'read {{GPD_AGENTS_DIR}}/{agent_name}.md for your role and instructions' in content
        assert "readonly=false" in content
        assert f"{file_token}\nRead that file before continuing" in content
        assert f"@{file_token}" not in content


def test_revision_and_audit_workflows_verify_artifacts_before_trusting_success_text() -> None:
    respond = (WORKFLOWS_DIR / "respond-to-referees.md").read_text(encoding="utf-8")
    audit = (WORKFLOWS_DIR / "audit-milestone.md").read_text(encoding="utf-8")

    assert "response_to: REFEREE-REPORT{round_suffix}.md" in respond
    assert "## Point-by-Point Responses" in respond
    assert "**Classification:** fixed" in respond
    assert "Use `**Evidence:**` blocks for rebuttals" in respond
    assert "verify the promised artifacts before trusting the handoff text" in respond
    assert "If the agent claimed success but the files did not change, treat that section as failed" in respond
    assert "Re-open `GPD/AUTHOR-RESPONSE{round_suffix}.md` and `GPD/paper/REFEREE_RESPONSE{round_suffix}.md`" in respond

    assert "Verify the promised referee artifacts before trusting the handoff text" in audit
    assert "Confirm `GPD/v{milestone_version}-MILESTONE-REFEREE-REPORT.md` exists" in audit
    assert "If the agent reported success but either artifact is missing, treat peer review as failed" in audit


def test_audit_milestone_surfaces_contract_gate_and_milestone_review_namespace() -> None:
    audit = (WORKFLOWS_DIR / "audit-milestone.md").read_text(encoding="utf-8")

    assert "project_contract_load_info" in audit
    assert "project_contract_validation" in audit
    assert "active_reference_context" in audit
    assert "Treat `project_contract` as authoritative only when `project_contract_load_info` is clean and `project_contract_validation` passes." in audit
    assert "skip mock peer review and note that the contract gate must be repaired before milestone publishability review" in audit
    assert "GPD/v{milestone_version}-MILESTONE-REFEREE-REPORT.md" in audit
    assert "GPD/v{milestone_version}-MILESTONE-REFEREE-REPORT.tex" in audit
    assert "Project contract load info: {project_contract_load_info}" in audit
    assert "Project contract validation: {project_contract_validation}" in audit
    assert "Active references: {active_reference_context}" in audit


def test_phase_research_and_verification_surfaces_keep_anchor_checks_mandatory() -> None:
    phase_researcher = (AGENTS_DIR / "gpd-phase-researcher.md").read_text(encoding="utf-8")
    planner_agent = (AGENTS_DIR / "gpd-planner.md").read_text(encoding="utf-8")
    verify_workflow = (WORKFLOWS_DIR / "verify-work.md").read_text(encoding="utf-8")

    assert "## Active Anchor References" in phase_researcher
    assert "contract-critical anchors as mandatory inputs" in phase_researcher
    assert "FORMALISM.md" in planner_agent
    assert "| derivation, analytical, symbolic   | CONVENTIONS.md, FORMALISM.md    |" in planner_agent
    assert "| validation, testing, benchmarks    | VALIDATION.md, REFERENCES.md    |" in planner_agent
    assert "Do NOT skip contract-critical anchors" in verify_workflow
    assert "active_reference_context" in verify_workflow
    assert "project_contract_validation" in verify_workflow
    assert "project_contract_load_info" in verify_workflow
    assert "visible-but-blocked contract must be repaired before it is used as authoritative verification scope" in verify_workflow
    assert "suggest_contract_checks(contract)" in verify_workflow


def test_stage4_templates_and_workflows_surface_contract_results_and_verdict_ledgers() -> None:
    _contract_results_schema = (TEMPLATES_DIR / "contract-results-schema.md").read_text(encoding="utf-8")
    summary_template = (TEMPLATES_DIR / "summary.md").read_text(encoding="utf-8")
    _verification_template = (TEMPLATES_DIR / "verification-report.md").read_text(encoding="utf-8")
    _research_verification = (TEMPLATES_DIR / "research-verification.md").read_text(encoding="utf-8")
    _execute_plan = (WORKFLOWS_DIR / "execute-plan.md").read_text(encoding="utf-8")
    _verify_workflow = (WORKFLOWS_DIR / "verify-work.md").read_text(encoding="utf-8")
    _verify_phase = (WORKFLOWS_DIR / "verify-phase.md").read_text(encoding="utf-8")
    _compare_workflow = (WORKFLOWS_DIR / "compare-experiment.md").read_text(encoding="utf-8")
    _comparison_template = (
        TEMPLATES_DIR / "paper" / "experimental-comparison.md"
    ).read_text(encoding="utf-8")
    _executor_agent = (AGENTS_DIR / "gpd-executor.md").read_text(encoding="utf-8")
    _verifier_agent = (AGENTS_DIR / "gpd-verifier.md").read_text(encoding="utf-8")

    assert "contract_results" in summary_template
    assert "comparison_verdicts" in summary_template
    assert "plan_contract_ref" in summary_template
    assert "Keep this ledger user-visible" in summary_template
    assert "Reload `@{GPD_INSTALL_DIR}/templates/contract-results-schema.md` immediately before writing the YAML" in summary_template
    assert "canonical project-root-relative `GPD/phases/XX-name/{phase}-{plan}-PLAN.md#/contract` path" in summary_template
    assert "Choose the depth explicitly" in summary_template
    assert "default: full" not in summary_template
    assert "Keep `uncertainty_markers` explicit and user-visible" in summary_template
    assert "uncertainty_markers:" in summary_template
    assert "weakest_anchors: [anchor-1]" in summary_template
    assert "disconfirming_observations: [observation-1]" in summary_template
    assert "omitting the corresponding `comparison_verdicts` entry makes the summary incomplete" in summary_template


def test_plan_tool_preflight_surfaces_across_planning_and_execution_prompts() -> None:
    phase_prompt = (TEMPLATES_DIR / "phase-prompt.md").read_text(encoding="utf-8")
    planner_agent = (AGENTS_DIR / "gpd-planner.md").read_text(encoding="utf-8")
    plan_checker = (AGENTS_DIR / "gpd-plan-checker.md").read_text(encoding="utf-8")
    executor_agent = (AGENTS_DIR / "gpd-executor.md").read_text(encoding="utf-8")
    execute_plan = (WORKFLOWS_DIR / "execute-plan.md").read_text(encoding="utf-8")
    execute_phase = (WORKFLOWS_DIR / "execute-phase.md").read_text(encoding="utf-8")
    plan_phase = (WORKFLOWS_DIR / "plan-phase.md").read_text(encoding="utf-8")
    tooling_ref = (REFERENCES_DIR / "tooling" / "tool-integration.md").read_text(encoding="utf-8")
    summary_template = (TEMPLATES_DIR / "summary.md").read_text(encoding="utf-8")
    verification_template = (TEMPLATES_DIR / "verification-report.md").read_text(encoding="utf-8")
    contract_results_schema = (TEMPLATES_DIR / "contract-results-schema.md").read_text(encoding="utf-8")
    research_verification = (TEMPLATES_DIR / "research-verification.md").read_text(encoding="utf-8")
    verify_workflow = (WORKFLOWS_DIR / "verify-work.md").read_text(encoding="utf-8")
    verify_phase = (WORKFLOWS_DIR / "verify-phase.md").read_text(encoding="utf-8")
    verifier_agent = (AGENTS_DIR / "gpd-verifier.md").read_text(encoding="utf-8")
    compare_workflow = (WORKFLOWS_DIR / "compare-experiment.md").read_text(encoding="utf-8")
    comparison_template = (TEMPLATES_DIR / "paper" / "experimental-comparison.md").read_text(encoding="utf-8")
    verify_phase = (WORKFLOWS_DIR / "verify-phase.md").read_text(encoding="utf-8")
    verifier_agent = (AGENTS_DIR / "gpd-verifier.md").read_text(encoding="utf-8")

    assert "# tool_requirements: # Optional machine-checkable specialized tools. Omit entirely if none." in phase_prompt
    assert "# tool_requirements: # Machine-checkable specialized tools (omit entirely if none)" in planner_agent
    assert "| `tool_requirements` | No       | Machine-checkable specialized tool requirements |" in planner_agent
    assert "declare them in `tool_requirements`" in plan_checker
    assert "Run `gpd validate plan-preflight <PLAN.md path>` from the local CLI." in executor_agent
    assert "A declared fallback does not override a blocking `required: true` requirement." in executor_agent
    assert 'PLAN_PREFLIGHT=$(gpd --raw validate plan-preflight "${PLAN_PATH}")' in execute_plan
    assert "Use declared fallbacks automatically only for non-blocking preferred tools (`required: false`)" in execute_plan
    assert "gpd validate plan-preflight <PLAN.md>" not in execute_plan
    assert "require that the selected `PLAN.md` passes `gpd validate plan-preflight <PLAN.md>`" in execute_phase
    assert "gpd validate plan-preflight <PLAN.md>" in plan_phase
    assert "declare it as `tool: wolfram` in `tool_requirements`" in tooling_ref
    assert "verification_inputs" not in summary_template
    assert "contract_results" in verification_template
    assert "comparison_verdicts" in verification_template
    assert "Subject Role" in verification_template
    assert "subject_role: decisive" in verification_template
    assert "Record only user-visible contract targets here" in verification_template
    assert "status: passed` is strict" in verification_template
    assert "absence of a verdict is itself a gap" in verification_template
    assert "Reload `@{GPD_INSTALL_DIR}/templates/contract-results-schema.md` immediately before writing the YAML" in verification_template
    assert "verification-side `suggested_contract_checks`" in verification_template
    assert "uncertainty_markers:" in verification_template
    assert "weakest_anchors: [anchor-1]" in verification_template
    assert "disconfirming_observations: [observation-1]" in verification_template
    assert "every reference entry is `completed`" in verification_template
    assert "every `must_surface` reference has all `required_actions` recorded in `completed_actions`" in verification_template
    assert "Benchmark acceptance tests require `comparison_kind: benchmark`" in verification_template
    assert "cross-method acceptance tests require `comparison_kind: cross_method`" in verification_template
    assert "Section-specific status vocabularies are mandatory" in contract_results_schema
    assert "`references` use `completed`, `missing`, or `not_applicable`" in contract_results_schema
    assert "`forbidden_proxies` use `rejected`, `violated`, `unresolved`, or `not_applicable`" in contract_results_schema
    assert "The same requirement applies when a benchmark-style reference anchors the subject" in contract_results_schema
    assert "The same structured suggestion is required when a benchmark-style reference anchors the subject" in verification_template
    assert "Include a `suggested_contract_checks` entry whenever a decisive benchmark / cross-method comparison is still partial or unresolved" in verification_template
    assert "Use `@{GPD_INSTALL_DIR}/templates/verification-report.md` for the canonical verification frontmatter contract." in research_verification
    assert "status: passed | gaps_found | expert_needed | human_needed" in research_verification
    assert "deliverables: {}" not in research_verification
    assert "acceptance_tests: {}" not in research_verification
    assert "references: {}" not in research_verification
    assert "forbidden_proxies: {}" not in research_verification
    assert "deliverable-main" in research_verification
    assert "acceptance-test-main" in research_verification
    assert "reference-main" in research_verification
    assert "forbidden-proxy-main" in research_verification
    assert "comparison_verdicts:" in research_verification
    assert "subject_role: decisive" in research_verification
    assert "comparison_kind: benchmark" in research_verification
    assert "comparison_kind: [benchmark | prior_work | experiment | cross_method | baseline | other]" in research_verification
    assert "comparison_kind: [benchmark | prior_work | experiment | cross_method | baseline | other | \"\"]" not in research_verification
    assert "omit both `comparison_kind` and `comparison_reference_id` instead of leaving blank placeholders" in research_verification
    assert "comparison_kind: benchmark | prior_work | experiment | cross_method | baseline | other" in research_verification
    assert 'comparison_kind: "benchmark | prior_work | experiment | cross_method | baseline | other"' in research_verification
    assert "verification-side `suggested_contract_checks` entries are part of the same canonical schema surface" in research_verification
    assert "suggested_contract_checks:" in research_verification
    assert "uncertainty_markers:" in research_verification
    assert "weakest_anchors: [anchor-1]" in research_verification
    assert "disconfirming_observations: [observation-1]" in research_verification
    assert "session_status: validating | completed | diagnosed" in research_verification
    assert "verified: 2026-03-15T14:45:00Z" in research_verification
    assert "score: 3/4 contract targets verified" in research_verification
    assert "session_status: diagnosed" in research_verification
    assert "\nstatus: diagnosed\n" not in research_verification
    assert 'status -> "completed"' not in research_verification
    assert '`session_status` -> "diagnosed"' in research_verification
    assert 'status -> "diagnosed"' not in research_verification
    assert "The frontmatter `comparison_verdicts` ledger is authoritative" in research_verification
    assert "subject_role: decisive | supporting | supplemental | other" in research_verification
    assert "Only `subject_role: decisive` closes a required decisive comparison" in research_verification
    assert "decisive benchmark / cross-method check remains partial, not attempted, or still lacks a decisive verdict" in research_verification
    assert "even a single item must stay a YAML list" in contract_results_schema
    assert "scalar strings are invalid" in contract_results_schema
    assert "Even singleton values must stay YAML lists in strict contract-backed ledgers" in summary_template
    assert "Even singleton values must stay YAML lists in strict contract-backed ledgers" in verification_template
    assert "Benchmark acceptance tests require `comparison_kind: benchmark`" in contract_results_schema
    assert "cross-method acceptance tests require `comparison_kind: cross_method`" in contract_results_schema
    assert "claim_id" in research_verification
    assert "acceptance_test_id" in research_verification
    assert "frontmatter contract compatible with `@{GPD_INSTALL_DIR}/templates/verification-report.md`" in verify_workflow
    assert "status: passed | gaps_found | expert_needed | human_needed" in verify_workflow
    assert "session_status: validating" in verify_workflow
    assert "uncertainty_markers:" in verify_workflow
    assert "weakest_anchors: [anchor-1]" in verify_workflow
    assert "disconfirming_observations: [observation-1]" in verify_workflow
    assert "weakest_anchors: []" not in verify_workflow
    assert "disconfirming_observations: []" not in verify_workflow
    assert "Mirror decisive verdicts into frontmatter `comparison_verdicts`." in verify_workflow
    assert "structured `suggested_contract_checks` entry before final validation" in verify_workflow
    assert "request_template" in verify_workflow
    assert "required_request_fields" in verify_workflow
    assert "supported_binding_fields" in verify_workflow
    assert "run_contract_check(request=...)" in verify_workflow
    assert "Benchmark acceptance tests require `comparison_kind: benchmark`" in verify_workflow
    assert "cross-method acceptance tests require `comparison_kind: cross_method`" in verify_workflow
    assert "deliverables: {}" not in verify_workflow
    assert "acceptance_tests: {}" not in verify_workflow
    assert "references: {}" not in verify_workflow
    assert "forbidden_proxies: {}" not in verify_workflow
    assert "deliverable-id" in verify_workflow
    assert "acceptance-test-id" in verify_workflow
    assert "reference-id" in verify_workflow
    assert "forbidden-proxy-id" in verify_workflow
    assert "comparison_verdicts:" in verify_workflow
    assert "subject_role: decisive" in verify_workflow
    assert "comparison_kind: benchmark" in verify_workflow
    assert "comparison_kind: [benchmark | prior_work | experiment | cross_method | baseline | other]" in verify_workflow
    assert "comparison_kind: [benchmark | prior_work | experiment | cross_method | baseline | \"\"]" not in verify_workflow
    assert "omit both `comparison_kind` and `comparison_reference_id` instead of leaving blank placeholders" in verify_workflow
    assert "suggested_contract_checks:" in verify_workflow
    assert "`suggested_contract_check`" not in verify_workflow
    assert "Return status (`passed` | `gaps_found` | `expert_needed` | `human_needed`)" in verify_phase
    assert "contract_results including `uncertainty_markers`" in verify_phase
    assert "`suggested_contract_check`" not in verify_phase
    assert "gap_subject_kind" in verifier_agent
    assert "Each gap has: `gap_subject_kind`" in verifier_agent
    assert "Each gap has: `subject_kind`" not in verifier_agent
    assert "Verification Status:** {passed | gaps_found | expert_needed | human_needed}" in verifier_agent
    assert "uncertainty_markers:" in verifier_agent
    assert "weakest_anchors: [anchor-1]" in verifier_agent
    assert "disconfirming_observations: [observation-1]" in verifier_agent
    assert "weakest_anchors: []" not in verifier_agent
    assert "disconfirming_observations: []" not in verifier_agent
    assert "`suggested_contract_check`" not in verifier_agent
    assert "`contract_results` is authoritative." in execute_plan
    assert "project_contract_validation" in execute_plan
    assert "project_contract_load_info" in execute_plan
    assert "visible-but-blocked contract is still not an approved execution contract" in execute_plan
    assert "Autonomy mode (`supervised` / `balanced` / `yolo`) and profile may change cadence or verbosity, but they do NOT relax contract-result emission." in execute_plan
    assert "comparison_verdicts` for decisive internal/external comparisons that were required or attempted" in execute_plan
    assert "emit `verdict: inconclusive` or `verdict: tension` instead of omitting the entry" in execute_plan
    assert "Immediately before writing frontmatter, re-open `@{GPD_INSTALL_DIR}/templates/contract-results-schema.md` and apply it literally." in execute_plan
    assert "contract_results" in verify_phase
    assert "Verification targets must stay user-visible" in verify_phase
    assert "must_haves" not in verify_phase
    assert "request_template" in verify_phase
    assert "required_request_fields" in verify_phase
    assert "supported_binding_fields" in verify_phase
    assert "run_contract_check(request=...)" in verify_phase
    assert "comparison_verdicts" in compare_workflow
    assert "project_contract_load_info" in compare_workflow
    assert "project_contract_validation" in compare_workflow
    assert "authoritative only when `project_contract_load_info` is clean and `project_contract_validation` passes" in compare_workflow
    assert "selected_protocol_bundle_ids" in compare_workflow
    assert "protocol_bundle_context" in compare_workflow
    assert "active_reference_context" in compare_workflow
    assert "protocol_bundle_ids (optional):" in compare_workflow
    assert "bundle_expectations (optional):" in compare_workflow
    assert "comparison_kind: benchmark|prior_work|experiment|cross_method|baseline|other" in compare_workflow
    assert "comparison_kind: benchmark|prior_work|experiment|cross_method|baseline|other" in comparison_template
    assert "`comparison_verdicts` is a closed schema" in comparison_template
    internal_comparison_template = (TEMPLATES_DIR / "paper" / "internal-comparison.md").read_text(encoding="utf-8")
    assert "`comparison_verdicts` is a closed schema" in internal_comparison_template
    assert "subject_role" in comparison_template
    assert "Profiles and autonomy modes may compress prose or cadence, but they do NOT relax contract-result emission" in executor_agent
    assert "Use claim IDs, deliverable IDs, acceptance test IDs, reference IDs, and forbidden proxy IDs directly from the `contract` block." in verifier_agent


def test_execute_phase_workflow_surfaces_project_contract_validation_gate() -> None:
    execute_workflow = (WORKFLOWS_DIR / "execute-phase.md").read_text(encoding="utf-8")

    assert "project_contract_validation" in execute_workflow
    assert "project_contract_load_info" in execute_workflow
    assert "visible-but-blocked contract as an approved execution contract" in execute_workflow


def test_execute_phase_and_execute_plan_surface_required_reference_and_state_ownership_guidance() -> None:
    execute_command = (COMMANDS_DIR / "execute-phase.md").read_text(encoding="utf-8")
    execute_workflow = (WORKFLOWS_DIR / "execute-phase.md").read_text(encoding="utf-8")
    execute_plan = (WORKFLOWS_DIR / "execute-plan.md").read_text(encoding="utf-8")

    assert "@{GPD_INSTALL_DIR}/references/orchestration/artifact-surfacing.md" in execute_workflow
    assert "{GPD_INSTALL_DIR}/references/execution/github-lifecycle.md" in execute_plan
    assert (
        "substitute the repository's actual default branch and remote names for "
        "`<default-branch>` and `<remote-name>`"
    ) in execute_plan
    assert "applies returned shared-state updates after each successfully completed plan" in execute_command
    assert "STATE.md is updated after each wave completes" not in execute_command
    assert "By the time the wave-complete report is emitted" in execute_workflow


def test_verification_prompts_keep_suggested_contract_check_bindings_schema_tight() -> None:
    verification_template = (TEMPLATES_DIR / "verification-report.md").read_text(encoding="utf-8")
    research_verification = (TEMPLATES_DIR / "research-verification.md").read_text(encoding="utf-8")
    verify_workflow = (WORKFLOWS_DIR / "verify-work.md").read_text(encoding="utf-8")
    verifier_agent = (AGENTS_DIR / "gpd-verifier.md").read_text(encoding="utf-8")

    assert 'suggested_subject_id: ""' not in verification_template
    assert 'suggested_subject_id: [contract id or ""]' not in research_verification
    assert 'suggested_subject_id: [contract id or ""]' not in verify_workflow
    assert 'suggested_subject_id: "matching contract id"' in research_verification
    assert 'suggested_subject_id: "matching contract id"' in verify_workflow
    assert "acceptance-test-id" in verification_template
    assert "acceptance-test-main" in research_verification
    assert "acceptance-test-id" in verifier_agent
    assert "omit both keys instead of leaving one blank" in verification_template
    assert "omit both keys instead of leaving one blank" in research_verification
    assert "verification-side `suggested_contract_checks`" in verification_template
    assert "verification-side `suggested_contract_checks` entries are part of the same canonical schema surface" in research_verification
    assert "omit both keys instead of leaving one blank" in verify_workflow
    assert "omit both keys instead of leaving one blank" in verifier_agent
    assert "gap_subject_kind" in verifier_agent
    assert "Each gap has: `gap_subject_kind`" in verifier_agent
    assert "Each gap has: `subject_kind`" not in verifier_agent
    assert "Verification Status:** {passed | gaps_found | expert_needed | human_needed}" in verifier_agent


def test_lane5_prompt_examples_keep_schema_valid_contract_fields_visible() -> None:
    planner = (AGENTS_DIR / "gpd-planner.md").read_text(encoding="utf-8")
    plan_checker = (AGENTS_DIR / "gpd-plan-checker.md").read_text(encoding="utf-8")
    parameter_sweep = (WORKFLOWS_DIR / "parameter-sweep.md").read_text(encoding="utf-8")
    research_verification = (TEMPLATES_DIR / "research-verification.md").read_text(encoding="utf-8")
    verify_work = (WORKFLOWS_DIR / "verify-work.md").read_text(encoding="utf-8")
    verifier = (AGENTS_DIR / "gpd-verifier.md").read_text(encoding="utf-8")
    executor_example = (REFERENCES_DIR / "execution" / "executor-worked-example.md").read_text(encoding="utf-8")

    assert "context_intake:" in planner
    assert 'must_read_refs: ["ref-textbook"]' in planner
    assert "references: [ref-uehling]" in planner
    assert "context_intake:" in plan_checker
    assert "why_it_matters:" in plan_checker
    assert "required_actions: [read, compare, cite]" in plan_checker
    assert "procedure: \"Compare the computed value against the benchmark anchor within tolerance.\"" in plan_checker
    assert "context_intake:" in parameter_sweep
    assert "must_read_refs: [ref-sweep-anchor]" in parameter_sweep
    assert "reference-main" in research_verification
    assert "acceptance-test-main" in research_verification
    assert "linked_ids: [deliverable-main, acceptance-test-main, reference-main]" in research_verification
    assert "evidence:\n        - verifier: gpd-verifier" in research_verification
    assert 'evidence_path: "[artifact path or expected evidence path]"' in research_verification
    assert 'started: "ISO timestamp"' in research_verification
    assert 'updated: "ISO timestamp"' in research_verification
    assert "test-benchmark" not in research_verification
    assert "reference-id" in verify_work
    assert "acceptance-test-id" in verify_work
    assert "test-benchmark" not in verify_work
    assert "reference-id" in verifier
    assert "acceptance-test-id" in verifier
    assert "test-benchmark" not in verifier
    assert "deliverables:" in executor_example
    assert "references:" in executor_example
    assert 'reference_id: "reference-qed-benchmark"' in executor_example
    assert "deliverable-self-energy-derivation" in executor_example


def test_verification_prompt_wiring_rejects_invalid_reference_and_proxy_scaffolds(tmp_path: Path) -> None:
    phase_dir = tmp_path / "GPD" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    verification_path = phase_dir / "01-VERIFICATION.md"
    verification_path.write_text(
        (FIXTURES_STAGE4 / "verification_with_contract_results.md")
        .read_text(encoding="utf-8")
        .replace(
            "  references:\n"
            "    ref-benchmark:\n"
            "      status: completed\n"
            "      completed_actions: [read, compare, cite]\n"
            "      missing_actions: []\n"
            "      summary: Benchmark anchor was surfaced.\n",
            "  references:\n"
            "    ref-benchmark:\n"
            "      completed_actions: [read, cite]\n"
            "      missing_actions: [compare]\n"
            "      summary: Benchmark anchor was surfaced.\n",
            1,
        )
        .replace(
            "  forbidden_proxies:\n"
            "    fp-benchmark:\n"
            "      status: rejected\n",
            "  forbidden_proxies:\n"
            "    fp-benchmark:\n"
            "      notes: Proxy scaffold left status unspecified.\n",
            1,
        ),
        encoding="utf-8",
    )

    result = validate_frontmatter(
        verification_path.read_text(encoding="utf-8"),
        "verification",
        source_path=verification_path,
    )

    assert result.valid is False
    assert any(
        "references.ref-benchmark.status must be explicit in contract-backed contract_results" in error
        for error in result.errors
    )
    assert any(
        "forbidden_proxies.fp-benchmark.status must be explicit in contract-backed contract_results" in error
        for error in result.errors
    )


def test_verification_prompt_wiring_requires_suggested_checks_for_compare_required_references(
    tmp_path: Path,
) -> None:
    phase_dir = tmp_path / "GPD" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    verification_path = phase_dir / "01-VERIFICATION.md"
    verification_path.write_text(
        (FIXTURES_STAGE4 / "verification_with_contract_results.md")
        .read_text(encoding="utf-8")
        .replace(
            "status: passed\nscore: 3/3 contract targets verified\n",
            "status: gaps_found\nscore: 2/3 contract targets verified\n",
            1,
        )
        .replace(
            "  references:\n"
            "    ref-benchmark:\n"
            "      status: completed\n"
            "      completed_actions: [read, compare, cite]\n"
            "      missing_actions: []\n"
            "      summary: Benchmark anchor was surfaced.\n",
            "  references:\n"
            "    ref-benchmark:\n"
            "      status: completed\n"
            "      completed_actions: [read, cite]\n"
            "      missing_actions: []\n"
            "      summary: Benchmark anchor was surfaced.\n",
            1,
        ),
        encoding="utf-8",
    )

    result = validate_frontmatter(
        verification_path.read_text(encoding="utf-8"),
        "verification",
        source_path=verification_path,
    )

    assert result.valid is False
    assert any(
        "suggested_contract_checks: required when decisive benchmark/cross-method checks remain missing, partial, or incomplete"
        in error
        for error in result.errors
    )


def test_verifier_entry_points_expose_contract_check_tools() -> None:
    verify_work_meta, _ = _parse_frontmatter((COMMANDS_DIR / "verify-work.md").read_text(encoding="utf-8"))
    verifier_meta, _ = _parse_frontmatter((AGENTS_DIR / "gpd-verifier.md").read_text(encoding="utf-8"))

    verify_work_tools = verify_work_meta.get("allowed-tools", [])
    verifier_tools = _parse_tools(verifier_meta.get("tools"))

    for tool_name in (
        "mcp__gpd_verification__get_bundle_checklist",
        "mcp__gpd_verification__suggest_contract_checks",
        "mcp__gpd_verification__run_contract_check",
    ):
        assert tool_name in verify_work_tools
        assert tool_name in verifier_tools


def test_contract_schema_references_stay_wired_into_templates_and_review_docs() -> None:
    phase_prompt = (TEMPLATES_DIR / "phase-prompt.md").read_text(encoding="utf-8")
    summary_template = (TEMPLATES_DIR / "summary.md").read_text(encoding="utf-8")
    verification_template = (TEMPLATES_DIR / "verification-report.md").read_text(encoding="utf-8")
    contract_results_schema = (TEMPLATES_DIR / "contract-results-schema.md").read_text(encoding="utf-8")
    executor_completion = (REFERENCES_DIR / "execution" / "executor-completion.md").read_text(encoding="utf-8")
    referee = (AGENTS_DIR / "gpd-referee.md").read_text(encoding="utf-8")
    peer_review = (WORKFLOWS_DIR / "peer-review.md").read_text(encoding="utf-8")
    panel = (REFERENCES_DIR / "publication" / "peer-review-panel.md").read_text(encoding="utf-8")
    scoring = (REFERENCES_DIR / "publication" / "paper-quality-scoring.md").read_text(encoding="utf-8")
    referee_decision_schema = (TEMPLATES_DIR / "paper" / "referee-decision-schema.md").read_text(encoding="utf-8")
    paper_config_schema = (TEMPLATES_DIR / "paper" / "paper-config-schema.md").read_text(encoding="utf-8")
    reproducibility_template = (TEMPLATES_DIR / "paper" / "reproducibility-manifest.md").read_text(encoding="utf-8")
    reproducibility_protocol = (REFERENCES_DIR / "protocols" / "reproducibility.md").read_text(encoding="utf-8")
    execute_plan = (WORKFLOWS_DIR / "execute-plan.md").read_text(encoding="utf-8")
    verify_work = (WORKFLOWS_DIR / "verify-work.md").read_text(encoding="utf-8")
    plan_phase = (WORKFLOWS_DIR / "plan-phase.md").read_text(encoding="utf-8")
    write_paper = (WORKFLOWS_DIR / "write-paper.md").read_text(encoding="utf-8")

    assert "templates/plan-contract-schema.md" in phase_prompt
    assert "templates/contract-results-schema.md" in summary_template
    assert "templates/contract-results-schema.md" in verification_template
    assert "templates/paper/review-ledger-schema.md" in referee
    assert "templates/paper/referee-decision-schema.md" in referee
    assert "fall back to direct standalone review" not in referee
    assert "Do not fall back to standalone review" in referee
    assert "gpd validate review-claim-index" in peer_review
    assert "gpd validate review-stage-report" in peer_review
    assert "gpd validate review-ledger" in peer_review
    assert "--ledger GPD/review/REVIEW-LEDGER{round_suffix}.json" in peer_review
    assert "before trusting any final recommendation" in peer_review
    assert "Keep `manuscript_path` non-empty and identical across `GPD/review/REVIEW-LEDGER{round_suffix}.json`" in peer_review
    assert "templates/paper/review-ledger-schema.md" in panel
    assert "templates/paper/referee-decision-schema.md" in panel
    assert "--ledger GPD/review/REVIEW-LEDGER{round_suffix}.json" in panel
    assert "templates/paper/paper-quality-input-schema.md" in scoring
    assert '"journal": "prl"' in paper_config_schema
    assert '"authors"' in paper_config_schema
    assert '"sections"' in paper_config_schema
    assert "XX-YY-SUMMARY.md" in contract_results_schema
    assert "XX-VERIFICATION.md" in contract_results_schema
    assert "Must be the canonical project-root-relative `GPD/phases/XX-name/XX-YY-PLAN.md#/contract` path" in contract_results_schema
    assert "`uncertainty_markers` must remain explicit in contract-backed outputs" in contract_results_schema
    assert "weakest_anchors: [anchor-1]" in contract_results_schema
    assert "disconfirming_observations: [observation-1]" in contract_results_schema
    assert "forbidden_proxy_id: fp-main" in contract_results_schema
    assert "closed action vocabulary: `read`, `use`, `compare`, `cite`, `avoid`" in contract_results_schema
    assert "forbidden_proxy_id: forbidden-proxy-id" in summary_template
    assert "templates/contract-results-schema.md" in executor_completion
    assert "claim_id: claim-main" in executor_completion
    assert "completed_actions: [read, compare, cite]" in executor_completion
    assert "`completed` requires non-empty `completed_actions`" in executor_completion
    assert "`subject_role` explicitly" in executor_completion
    assert "forbidden_proxies:" in executor_completion
    assert "uncertainty_markers:" in executor_completion
    assert "REFEREE-DECISION{round_suffix}.json --strict --ledger" in referee_decision_schema
    assert "STAGE-(reader|literature|math|physics|interestingness)(-R<round>)?.json" in referee_decision_schema
    assert "same optional `-R<round>` suffix" in referee_decision_schema
    assert "manuscript_path` must be non-empty" in referee_decision_schema
    assert "must align with the matching `CLAIMS{round_suffix}.json` claim index" in referee_decision_schema
    assert "GPD/review/STAGE-reader{round_suffix}.json" in panel
    assert "GPD/review/CLAIMS{round_suffix}.json" in panel
    assert "random_seeds[].computation" in reproducibility_template
    assert "resource_requirements[].step" in reproducibility_template
    assert "Strict validation fails on warnings, not only on hard errors." in reproducibility_template
    assert "Draft-only approximate output checksums still emit warnings and therefore block strict review." in reproducibility_template
    assert "Every stochastic `execution_steps[].name` must have a matching `random_seeds[].computation`" in reproducibility_template
    assert "templates/paper/reproducibility-manifest.md" in reproducibility_protocol
    assert "templates/paper/paper-config-schema.md" in write_paper
    assert "templates/paper/figure-tracker.md" in write_paper
    assert "templates/paper/reproducibility-manifest.md" in write_paper
    assert "gpd paper-build paper/PAPER-CONFIG.json" in paper_config_schema
    assert "paper/reproducibility-manifest.json" in write_paper
    assert "gpd --raw validate reproducibility-manifest paper/reproducibility-manifest.json --strict" in write_paper
    assert "gpd validate summary-contract" in execute_plan
    assert "gpd validate verification-contract" in verify_work
    assert "gpd validate plan-contract" in plan_phase
    assert "Contract Intake:" in plan_phase
    assert "Effective Reference Intake:" in plan_phase
    assert "Contract Intake:" in verify_work
    assert "Effective Reference Intake:" in verify_work


def test_review_and_verification_prompts_explicitly_surface_schema_sources_and_contract_context() -> None:
    peer_review = (WORKFLOWS_DIR / "peer-review.md").read_text(encoding="utf-8")
    verify_command = (COMMANDS_DIR / "verify-work.md").read_text(encoding="utf-8")
    write_paper = (WORKFLOWS_DIR / "write-paper.md").read_text(encoding="utf-8")
    respond_to_referees = (WORKFLOWS_DIR / "respond-to-referees.md").read_text(encoding="utf-8")
    sync_state = (WORKFLOWS_DIR / "sync-state.md").read_text(encoding="utf-8")
    review_reader = (AGENTS_DIR / "gpd-review-reader.md").read_text(encoding="utf-8")
    review_literature = (AGENTS_DIR / "gpd-review-literature.md").read_text(encoding="utf-8")
    review_math = (AGENTS_DIR / "gpd-review-math.md").read_text(encoding="utf-8")
    review_physics = (AGENTS_DIR / "gpd-review-physics.md").read_text(encoding="utf-8")
    review_significance = (AGENTS_DIR / "gpd-review-significance.md").read_text(encoding="utf-8")
    referee = (AGENTS_DIR / "gpd-referee.md").read_text(encoding="utf-8")

    assert "Project Contract:\n{project_contract}" in peer_review
    assert "Project Contract Load Info:\n{project_contract_load_info}" in peer_review
    assert "Project Contract Validation:\n{project_contract_validation}" in peer_review
    assert "Active References:\n{active_reference_context}" in peer_review
    assert "Contract Intake:\n{contract_intake}" in peer_review
    assert "Effective Reference Intake:\n{effective_reference_intake}" in peer_review
    assert "Reference Artifacts Content:\n{reference_artifacts_content}" in peer_review
    assert "project_contract_validation" in peer_review
    assert "project_contract_load_info" in peer_review
    assert (
        "Treat `project_contract_load_info` and `project_contract_validation` as the authoritative contract gate state."
        in peer_review
    )
    assert (
        "Treat `project_contract` and `contract_intake` as approved evidence only when that gate is clean and passing."
        in peer_review
    )
    assert (
        "Treat `effective_reference_intake`, `reference_artifacts_content`, and `active_reference_context` as binding carry-forward evidence even when the contract gate is blocked."
        in peer_review
    )
    assert "project_contract_load_info" in write_paper
    assert "project_contract_validation" in write_paper
    assert "authoritative only when `project_contract_load_info` is clean and `project_contract_validation` passes" in write_paper
    assert "project_contract_load_info" in respond_to_referees
    assert "project_contract_validation" in respond_to_referees
    assert "authoritative only when `project_contract_load_info` is clean and `project_contract_validation` passes" in respond_to_referees
    assert "templates/paper/review-ledger-schema.md" in peer_review
    assert "templates/paper/referee-decision-schema.md" in peer_review
    assert "references/publication/peer-review-panel.md" in peer_review
    assert "templates/verification-report.md" in verify_command
    assert "templates/contract-results-schema.md" in verify_command
    assert "Canonical schema for `paper/reproducibility-manifest.json`:" in write_paper
    assert "Canonical reconciliation contract:" in sync_state
    assert "state-json-schema.md` itself" in sync_state
    assert "save_state_markdown" in sync_state
    assert "gpd --raw state snapshot" not in sync_state
    assert (
        "Keep the current `project_contract`, `project_contract_load_info`, `project_contract_validation`, "
        "and `active_reference_context` visible throughout the staged review"
        in write_paper
    )
    assert peer_review.count("Project Contract:\n{project_contract}") >= 5
    assert peer_review.count("Project Contract Load Info:\n{project_contract_load_info}") >= 5
    assert peer_review.count("Project Contract Validation:\n{project_contract_validation}") >= 5
    assert peer_review.count("Active References:\n{active_reference_context}") >= 5
    assert peer_review.count("Contract Intake:\n{contract_intake}") >= 5
    assert peer_review.count("Effective Reference Intake:\n{effective_reference_intake}") >= 5
    assert peer_review.count("Reference Artifacts Content:\n{reference_artifacts_content}") >= 5
    assert peer_review.count("Treat `project_contract` and `contract_intake` as approved evidence only when that gate is clean and passing.") >= 5
    assert (
        peer_review.count(
            "Treat `effective_reference_intake`, `reference_artifacts_content`, and `active_reference_context` as binding carry-forward evidence even when the contract gate is blocked."
        )
        >= 5
    )
    assert "repair the blocked contract before retrying" in peer_review
    assert "peer-review-panel.md` directly" in review_reader
    assert "peer-review-panel.md` directly" in review_literature
    assert "GPD/review/CLAIMS{round_suffix}.json" in review_reader
    assert "GPD/review/STAGE-reader{round_suffix}.json" in review_reader
    assert "closed schema; do not invent extra keys" in review_reader
    assert "CLAIMS.json" not in review_reader
    assert "STAGE-reader.json" not in review_reader
    assert "round-specific variant when instructed" not in review_reader
    assert "GPD/review/STAGE-literature{round_suffix}.json" in review_literature
    assert "GPD/review/STAGE-math{round_suffix}.json" in review_math
    assert "GPD/review/STAGE-physics{round_suffix}.json" in review_physics
    assert "GPD/review/STAGE-interestingness{round_suffix}.json" in review_significance
    assert "Required schema for `STAGE-math{round_suffix}.json` (`StageReviewReport`, mirroring the staged-review contract):" in review_math
    assert "Required schema for `STAGE-physics{round_suffix}.json` (`StageReviewReport`, mirroring the staged-review contract):" in review_physics
    assert (
        "Required schema for `STAGE-interestingness{round_suffix}.json` (`StageReviewReport`, mirroring the staged-review contract):"
        in review_significance
    )
    assert "STAGE-literature.json" not in review_literature
    assert "STAGE-math.json" not in review_math
    assert "STAGE-physics.json" not in review_physics
    assert "STAGE-interestingness.json" not in review_significance
    assert "round-specific variant" not in review_literature
    assert "round-specific variant" not in review_math
    assert "round-specific variant" not in review_physics
    assert "round-specific variant" not in review_significance
    assert "re-open `@{GPD_INSTALL_DIR}/references/publication/peer-review-panel.md`" in referee


def test_peer_review_prompt_includes_concise_stage_map_for_users() -> None:
    peer_review_command = (COMMANDS_DIR / "peer-review.md").read_text(encoding="utf-8")
    peer_review_workflow = (WORKFLOWS_DIR / "peer-review.md").read_text(encoding="utf-8")

    assert "When announcing the panel to the user, say what each stage does in one concise sentence" in peer_review_command
    assert "Before spawning any reviewer, give the user a concise stage map" in peer_review_workflow
    for token in (
        "Stage 1 maps the paper's claims",
        "Stages 2-3 check prior work and mathematical soundness in parallel",
        "Stage 4 checks whether the physical interpretation is supported",
        "Stage 5 judges significance and venue fit",
        "Stage 6 synthesizes everything into the final recommendation",
    ):
        assert token in peer_review_command
        assert token in peer_review_workflow


def test_peer_review_command_limits_default_manuscript_targets_to_canonical_roots() -> None:
    peer_review_command = (COMMANDS_DIR / "peer-review.md").read_text(encoding="utf-8")

    assert "ls paper/main.tex manuscript/main.tex draft/main.tex 2>/dev/null" in peer_review_command
    assert "find . -maxdepth 3" not in peer_review_command
    assert "pass an explicit manuscript path or paper directory" in peer_review_command


def test_peer_review_referee_surface_fail_closed_stage6_contract() -> None:
    referee = (AGENTS_DIR / "gpd-referee.md").read_text(encoding="utf-8")
    peer_review = (WORKFLOWS_DIR / "peer-review.md").read_text(encoding="utf-8")
    reliability = (REFERENCES_DIR / "publication" / "peer-review-reliability.md").read_text(encoding="utf-8")

    assert "If any required staged-review artifact is missing, malformed, or uses the wrong round suffix, STOP" in peer_review
    assert "before trusting any final recommendation" in peer_review
    assert "Treat blank `manuscript_path` values in either `GPD/review/REVIEW-LEDGER{round_suffix}.json`" in peer_review
    assert "Do not fall back to standalone review" in referee
    assert "fall back to direct standalone review" not in referee
    assert "passes `gpd validate referee-decision ... --strict --ledger ...`" in reliability
    assert "passes `gpd validate review-ledger ...`, including a non-empty `manuscript_path`" in reliability
    assert "A blank `manuscript_path` in the review ledger or referee decision is a contract failure" in reliability


def test_research_verification_body_scaffold_keeps_body_only_subject_labels_distinct() -> None:
    research_verification = (TEMPLATES_DIR / "research-verification.md").read_text(encoding="utf-8")

    assert "check_subject_kind: [claim | deliverable | acceptance_test | reference]" in research_verification
    assert 'gap_subject_kind: "claim | deliverable | acceptance_test | reference"' in research_verification
    assert "Use `check_subject_kind` for body-only verification checkpoints" in research_verification
    assert "Use `gap_subject_kind` for the body scaffold" in research_verification
    assert "Keep `check_subject_kind` and `gap_subject_kind` aligned with the canonical frontmatter-safe subject vocabulary" in research_verification
    assert "use `forbidden_proxy_id` for explicit proxy-rejection gaps" in research_verification
    assert "\nsubject_kind: [claim | deliverable | acceptance_test | reference | forbidden_proxy | suggested_contract_check]" not in research_verification
    assert "check_subject_kind: [claim | deliverable | acceptance_test | reference | forbidden_proxy | suggested_contract_check]" not in research_verification
    assert 'gap_subject_kind: "claim | deliverable | acceptance_test | reference | forbidden_proxy | suggested_contract_check"' not in research_verification


def test_verify_work_workflow_uses_body_only_subject_kind_fields() -> None:
    verify_work = (WORKFLOWS_DIR / "verify-work.md").read_text(encoding="utf-8")

    assert "check_subject_kind: `claim | deliverable | acceptance_test | reference`" in verify_work
    assert "check_subject_kind: [claim | deliverable | acceptance_test | reference]" in verify_work
    assert 'gap_subject_kind: "{check_subject_kind}"' in verify_work
    assert "Use `forbidden_proxy_id` for explicit proxy-rejection checks" in verify_work
    assert "instead of inventing extra body subject kinds" in verify_work
    assert "{phase}" not in verify_work
    assert "GPD/phases/{phase_dir}" not in verify_work
    assert 'Write to `${phase_dir}/${phase_number}-VERIFICATION.md`' in verify_work
    assert 'gpd validate verification-contract "${phase_dir}/${phase_number}-VERIFICATION.md"' in verify_work
    assert 'gpd commit "verify(${phase_number}): complete research validation - {passed} passed, {issues} issues" --files "${phase_dir}/${phase_number}-VERIFICATION.md"' in verify_work
    assert "Read all PLAN.md files in ${phase_dir}/ using the file_read tool." in verify_work
    assert "\nsubject_kind: [claim | deliverable | acceptance_test | reference | forbidden_proxy | suggested_contract_check]" not in verify_work
    assert "check_subject_kind: `claim | deliverable | acceptance_test | reference | forbidden_proxy | suggested_contract_check`" not in verify_work
    assert "check_subject_kind: [claim | deliverable | acceptance_test | reference | forbidden_proxy | suggested_contract_check]" not in verify_work


def test_verify_work_active_sessions_use_canonical_verification_path_and_keep_status_separate() -> None:
    verify_work = (WORKFLOWS_DIR / "verify-work.md").read_text(encoding="utf-8")

    assert "rg -l '^session_status: (validating|diagnosed)$' GPD/phases/*/*-VERIFICATION.md 2>/dev/null | sort | head -5" in verify_work
    assert "Only treat files with `session_status: validating` or `session_status: diagnosed` as active researcher sessions." in verify_work
    assert "extract canonical verification `status`, `session_status`, `phase`, and the Current Check section" in verify_work
    assert "`session_status` replace or overwrite the canonical verification `status`" in verify_work
    assert '`session_status` if present, otherwise `status`' not in verify_work


def test_skill_surface_exposes_contract_references_for_paper_and_review_workflows() -> None:
    from gpd.mcp.servers.skills_server import get_skill

    write_paper = get_skill("gpd-write-paper")
    peer_review = get_skill("gpd-peer-review")
    write_paper_schema_documents = {Path(entry["path"]).name: entry for entry in write_paper["schema_documents"]}
    peer_review_contract_documents = {Path(entry["path"]).name: entry for entry in peer_review["contract_documents"]}

    assert "error" not in write_paper
    assert "error" not in peer_review
    assert any(path.endswith("paper-config-schema.md") for path in write_paper["schema_references"])
    assert any(path.endswith("reproducibility-manifest.md") for path in write_paper["contract_references"])
    assert any(path.endswith("peer-review-panel.md") for path in write_paper["contract_references"])
    assert any(path.endswith("peer-review-panel.md") for path in peer_review["contract_references"])
    assert "Paper Config Schema" in write_paper_schema_documents["paper-config-schema.md"]["body"]
    assert "Peer Review Panel Protocol" in peer_review_contract_documents["peer-review-panel.md"]["body"]
    assert "schema_documents and contract_documents already include" in write_paper["loading_hint"]


def test_review_and_execution_prompts_expand_required_schema_sources() -> None:
    src_root = REPO_ROOT / "src/gpd/specs"

    review_reader = expand_at_includes(
        (AGENTS_DIR / "gpd-review-reader.md").read_text(encoding="utf-8"),
        src_root,
        "/runtime/",
    )
    review_literature = expand_at_includes(
        (AGENTS_DIR / "gpd-review-literature.md").read_text(encoding="utf-8"),
        src_root,
        "/runtime/",
    )
    referee = expand_at_includes(
        (AGENTS_DIR / "gpd-referee.md").read_text(encoding="utf-8"),
        src_root,
        "/runtime/",
    )
    executor = expand_at_includes(
        (AGENTS_DIR / "gpd-executor.md").read_text(encoding="utf-8"),
        src_root,
        "/runtime/",
    )

    assert "Peer Review Panel Protocol" in review_reader
    assert "Peer Review Panel Protocol" in review_literature
    assert "Review Ledger Schema" in referee
    assert "Referee Decision Schema" in referee
    assert "Summary Template" in executor
    assert "Contract Results Schema" in executor


def test_verification_and_agent_reference_prompts_expand_required_reference_bodies() -> None:
    verify_work = _expand_prompt_surface(WORKFLOWS_DIR / "verify-work.md")
    verify_phase = _expand_prompt_surface(WORKFLOWS_DIR / "verify-phase.md")
    phase_researcher = _expand_prompt_surface(AGENTS_DIR / "gpd-phase-researcher.md")
    planner = _expand_prompt_surface(AGENTS_DIR / "gpd-planner.md")

    assert "Verification Independence" in verify_work
    assert "# Contract Results Schema" in verify_work
    assert "Verification Independence" in verify_phase
    assert "# Contract Results Schema" in verify_phase
    assert "Shared Research Philosophy and Protocols" in phase_researcher
    assert "Agent Infrastructure Protocols" in phase_researcher
    assert "Shared Protocols" in planner
    assert "Agent Infrastructure Protocols" in planner
    assert "@ include not resolved:" not in verify_work.lower()
    assert "@ include not resolved:" not in verify_phase.lower()
    assert "@ include not resolved:" not in phase_researcher.lower()
    assert "@ include not resolved:" not in planner.lower()
    assert "The standalone `/gpd:verify-work` workflow reuses the same verification criteria through `verify-work.md`; this file itself is executed by the execute-phase orchestrator." in verify_phase
    assert "VERIFICATION_FILE=\"${phase_dir}/${phase_number}-VERIFICATION.md\"" in verify_phase
    assert "Return status (`passed` | `gaps_found` | `expert_needed` | `human_needed`)" in verify_phase


def test_planner_and_summary_prompt_surfaces_expand_contract_schema_bodies() -> None:
    phase_prompt = _expand_prompt_surface(TEMPLATES_DIR / "phase-prompt.md")
    planner_prompt = _expand_prompt_surface(TEMPLATES_DIR / "planner-subagent-prompt.md")
    summary_template = _expand_prompt_surface(TEMPLATES_DIR / "summary.md")

    assert "# PLAN Contract Schema" in phase_prompt
    assert "schema_version: 1" in phase_prompt
    assert "in_scope:" in phase_prompt
    assert "context_intake:" in phase_prompt
    assert "non-empty `context_intake`" in phase_prompt
    assert "must_include_prior_outputs: [\"Phase 00 benchmark table\"]" in phase_prompt
    assert "user_asserted_anchors: [\"Use the lattice normalization from the user notes\"]" in phase_prompt
    assert "claims:" in phase_prompt
    assert "observables: [obs-main]" in phase_prompt
    assert "### `forbidden_proxies[]`" in phase_prompt
    assert "### `links[]`" in phase_prompt
    assert "# PLAN Contract Schema" in planner_prompt
    assert "non-empty `context_intake` object" in planner_prompt
    assert "Omit `kind`, `role`, or `relation` only when the schema default `other` is genuinely intended" in planner_prompt
    assert "scope.unresolved_questions" in planner_prompt
    assert "Every claim must declare a stable `id`." in planner_prompt
    assert (
        "Do not reuse the same ID across `claims[]`, `deliverables[]`, `acceptance_tests[]`, or `references[]`; "
        "target resolution becomes ambiguous."
        in planner_prompt
    )
    assert "If `must_surface: true`, `required_actions` must not be empty." in planner_prompt
    assert "# Contract Results Schema" in summary_template
    assert "Missing contract-backed `contract_results` is invalid." in summary_template
    assert "Do not invent `artifact` or `other` subject kinds" in summary_template


def test_sync_state_and_write_paper_command_prompts_expand_required_schema_bodies() -> None:
    sync_state = _expand_prompt_surface(COMMANDS_DIR / "sync-state.md")
    write_paper = _expand_prompt_surface(COMMANDS_DIR / "write-paper.md")

    assert "# state.json Schema" in sync_state
    assert "Authoritative vs Derived" in sync_state
    assert "`project_contract`" in sync_state
    assert (
        "Do not reuse the same ID across `claims[]`, `deliverables[]`, `acceptance_tests[]`, or `references[]`; "
        "target resolution becomes ambiguous."
        in sync_state
    )
    assert "`convention_lock`" in sync_state
    assert "Reproducibility Manifest Template" in write_paper
    assert '"execution_steps"' in write_paper
    assert "random_seeds[].computation" in write_paper
    assert "resource_requirements[].step" in write_paper


def test_non_adapter_sources_do_not_hardcode_runtime_names() -> None:
    runtime_terms = {
        descriptor.runtime_name
        for descriptor in iter_runtime_descriptors()
    }
    runtime_terms.update(
        alias
        for descriptor in iter_runtime_descriptors()
        for alias in descriptor.selection_aliases
        if alias.strip()
    )
    runtime_name_re = re.compile(
        rf"\b(?:{'|'.join(re.escape(term) for term in sorted(runtime_terms, key=len, reverse=True))})\b",
        re.IGNORECASE,
    )
    offenders: list[str] = []

    for path in sorted((REPO_ROOT / "src" / "gpd").rglob("*")):
        if not path.is_file() or path.suffix not in {".py", ".md"}:
            continue
        if path.is_relative_to(REPO_ROOT / "src" / "gpd" / "adapters"):
            continue
        content = path.read_text(encoding="utf-8")
        if runtime_name_re.search(content):
            offenders.append(str(path.relative_to(REPO_ROOT)))

    assert offenders == []


def test_plan_contract_schema_surfaces_downstream_contract_fields_and_normalization_rules() -> None:
    plan_schema = (TEMPLATES_DIR / "plan-contract-schema.md").read_text(encoding="utf-8")

    assert "schema_version: 1" in plan_schema
    assert "scope:" in plan_schema
    assert "in_scope: [\"[Optional boundary or objective]\"]" in plan_schema
    assert "unresolved_questions: [\"[Optional open question that still blocks planning]\"]" in plan_schema
    assert "context_intake:" in plan_schema
    assert "`context_intake` is required and must be a non-empty object, not a string or list." in plan_schema
    assert "must_read_refs: [ref-main]" in plan_schema
    assert "must_include_prior_outputs: [\"Phase 00 benchmark table\"]" in plan_schema
    assert "user_asserted_anchors: [\"Use the lattice normalization from the user notes\"]" in plan_schema
    assert "known_good_baselines: [\"Published large-N curve from Smith et al.\"]" in plan_schema
    assert "context_gaps: [\"Comparison source still undecided before planning\"]" in plan_schema
    assert "crucial_inputs: [\"Check the user's finite-volume cutoff choice before proceeding\"]" in plan_schema
    assert "approach_policy:" in plan_schema
    assert "allowed_fit_families: [power_law]" in plan_schema
    assert "`observables[]` may only reference declared `observables[].id`." in plan_schema
    assert "observables: [obs-main]" in plan_schema
    assert "aliases: [\"optional stable label or citation shorthand\"]" in plan_schema
    assert "carry_forward_to: [planning, verification]" in plan_schema
    assert "automation: automated | hybrid | human" in plan_schema
    assert "`kind` is optional and defaults to `other`; set it when the plan knows a more specific semantic category." in plan_schema
    assert "`kind` and `role` are optional and default to `other`; set them when the anchor semantics are already known." in plan_schema
    assert "`relation` is optional and defaults to `other`; set it when the dependency type is already known." in plan_schema
    assert "required_actions: [read, compare, cite, avoid]" in plan_schema
    assert "`required_actions[]` values must use the closed action vocabulary: `read`, `use`, `compare`, `cite`, `avoid`." in plan_schema
    assert "For non-scoping plans, `claims[]`, `deliverables[]`, `acceptance_tests[]`, and `forbidden_proxies[]` are all required." in plan_schema
    assert "### `forbidden_proxies[]`" in plan_schema
    assert "### `links[]`" in plan_schema
    assert "unvalidated_assumptions" in plan_schema
    assert "competing_explanations" in plan_schema
    assert "All ID cross-links must resolve to declared IDs." in plan_schema
    assert (
        "Do not reuse the same ID across `claims[]`, `deliverables[]`, `acceptance_tests[]`, or `references[]`; "
        "target resolution becomes ambiguous."
        in plan_schema
    )
    assert "`deliverables[]` must not be empty." in plan_schema
    assert "`acceptance_tests[]` must not be empty." in plan_schema
    assert "If `must_surface: true`, `applies_to[]` must not be empty." in plan_schema
    assert "If `references[]` is non-empty, at least one reference must set `must_surface: true`." in plan_schema
    assert "blank-after-trim values are invalid" in plan_schema


def test_state_json_schema_surfaces_stdin_contract_persistence_and_model_normalization_rules() -> None:
    state_schema = (TEMPLATES_DIR / "state-json-schema.md").read_text(encoding="utf-8")

    assert 'printf \'%s\\n\' "$PROJECT_CONTRACT_JSON" | gpd --raw validate project-contract -' in state_schema
    assert 'printf \'%s\\n\' "$PROJECT_CONTRACT_JSON" | gpd state set-project-contract -' in state_schema
    assert "temporary file" in state_schema
    assert "`schema_version` must be `1`." in state_schema
    assert "Approved project contracts must include at least one observable, claim, or deliverable." in state_schema
    assert "`uncertainty_markers.weakest_anchors` and `uncertainty_markers.disconfirming_observations` must both be non-empty." in state_schema
    assert "`scope.in_scope` must name at least one project boundary or objective." in state_schema
    assert (
        "If a project contract has any `references[]` and does not already carry concrete prior-output, "
        "user-anchor, or baseline grounding, at least one reference must set `must_surface: true`."
        in state_schema
    )
    assert "a missing `must_surface: true` reference is still a warning" in state_schema
    assert "If a project-contract reference sets `must_surface: true`, `applies_to[]` must not be empty." in state_schema
    assert "If a project-contract reference sets `must_surface: true`, `required_actions[]` must not be empty." in state_schema
    assert '"required_actions": ["read", "compare", "cite", "avoid"]' in state_schema
    assert "`required_actions[]` uses the same closed action vocabulary enforced downstream in contract ledgers: `read`, `use`, `compare`, `cite`, `avoid`." in state_schema
    assert (
        "Do not reuse the same ID across `claims[]`, `deliverables[]`, `acceptance_tests[]`, or `references[]`; "
        "target resolution becomes ambiguous."
        in state_schema
    )
    assert "`scope.unresolved_questions`, `context_intake.context_gaps`, or `uncertainty_markers.weakest_anchors`" in state_schema
    assert "Which reference should serve as the decisive benchmark anchor?" in state_schema
    assert "Blank-after-trim values are invalid" in state_schema


def test_phase_prompt_surfaces_validation_critical_plan_contract_rules() -> None:
    phase_prompt = (TEMPLATES_DIR / "phase-prompt.md").read_text(encoding="utf-8")

    assert "the contract must carry non-empty claims, deliverables, acceptance tests, forbidden proxies" in phase_prompt
    assert "If references are present, at least one must set `must_surface: true`." in phase_prompt
    assert "Semantic enum fields with schema defaults may be omitted when `other` is actually intended." in phase_prompt
    assert "If the plan is intentionally scoping-only" in phase_prompt


def test_review_ledger_schema_surfaces_enforced_id_formats() -> None:
    review_ledger_schema = (TEMPLATES_DIR / "paper" / "review-ledger-schema.md").read_text(encoding="utf-8")

    assert "`issue_id` must match `REF-[A-Za-z0-9][A-Za-z0-9_-]*`" in review_ledger_schema
    assert "Every `claim_ids[]` entry must match `CLM-[A-Za-z0-9][A-Za-z0-9_-]*`." in review_ledger_schema


def test_contract_models_match_prompted_schema_contracts() -> None:
    acceptance_test_fields = ResearchContract.model_fields["acceptance_tests"].annotation.__args__[0].model_fields
    reference_fields = ResearchContract.model_fields["references"].annotation.__args__[0].model_fields

    assert "automation" in acceptance_test_fields
    assert "aliases" in reference_fields
    assert "carry_forward_to" in reference_fields
    assert ResearchContract.model_fields["schema_version"].annotation == Literal[1]
    assert VerificationEvidence.model_config.get("extra") == "forbid"


def test_stage5_execution_surfaces_use_bounded_review_cadence_and_first_result_gates() -> None:
    execute_phase = (WORKFLOWS_DIR / "execute-phase.md").read_text(encoding="utf-8")
    execute_plan = (WORKFLOWS_DIR / "execute-plan.md").read_text(encoding="utf-8")
    resume_work = (WORKFLOWS_DIR / "resume-work.md").read_text(encoding="utf-8")
    continuation = (TEMPLATES_DIR / "continuation-prompt.md").read_text(encoding="utf-8")
    checkpoints = (REFERENCES_DIR / "orchestration" / "checkpoints.md").read_text(encoding="utf-8")
    checkpoint_flow = (REFERENCES_DIR / "execution" / "execute-plan-checkpoints.md").read_text(encoding="utf-8")
    executor_agent = (AGENTS_DIR / "gpd-executor.md").read_text(encoding="utf-8")

    assert "review_cadence" in execute_phase
    assert "FIRST_RESULT_GATE_REQUIRED" in execute_phase
    assert "probe_then_fanout" in execute_phase
    assert "bounded_execution" in execute_phase
    assert "autonomy` changes who is asked and when. It does NOT disable first-result sanity checks" in execute_plan
    assert "Required first-result sanity gate" in execute_plan
    assert "phase ordering, prior momentum, or \"we are already deep into execution\" never waive a required bounded stop" in execute_plan
    assert "uninterrupted wall-clock time since the current segment started reaches `MAX_UNATTENDED_MINUTES_PER_PLAN`" in execute_plan
    assert "Do NOT narrow just because a wave advanced or one proxy passed." in execute_phase
    assert "What decisive evidence is still owed before downstream work is trustworthy?" in resume_work
    assert "Pattern D: Auto-bounded" in executor_agent
    assert "active_execution_segment" in resume_work
    assert "execution_segment" in continuation
    assert "Required Checkpoint Payload" in checkpoints
    assert "rollback primitive" in checkpoint_flow
    assert "| `completed`    | -> update_roadmap (interactive verify-work equivalent)" not in execute_phase
    assert "| `diagnosed`    | Gaps were debugged; review fixes, then -> update_roadmap" not in execute_phase
    assert "| `validating`   | Verification in progress; wait or re-run verify-phase" not in execute_phase
    assert "If the same report also carries `session_status: validating|completed|diagnosed`, treat that as conversational progress only." in execute_phase
    assert "If the prior report carries `session_status: diagnosed`" in execute_phase


def test_show_phase_workflow_distinguishes_verification_status_from_session_status() -> None:
    show_phase = (WORKFLOWS_DIR / "show-phase.md").read_text(encoding="utf-8")

    assert "`*-VERIFICATION.md`" in show_phase
    assert "read frontmatter to extract canonical verification `status`, plus `session_status` when present" in show_phase
    assert "Automated verification uses `passed`/`gaps_found`/`expert_needed`/`human_needed`" in show_phase
    assert "researcher-session progress uses `session_status: validating|completed|diagnosed`" in show_phase
    assert "Automated verification uses `passed`/`gaps_found`/`human_needed`" not in show_phase
    assert "interactive validation uses `validating`/`completed`/`diagnosed`" not in show_phase


def test_execute_phase_and_related_agents_surface_only_plan_scoped_verification_artifacts() -> None:
    execute_phase = (WORKFLOWS_DIR / "execute-phase.md").read_text(encoding="utf-8")
    planner = (AGENTS_DIR / "gpd-planner.md").read_text(encoding="utf-8")
    verifier = (AGENTS_DIR / "gpd-verifier.md").read_text(encoding="utf-8")
    audit_milestone = (WORKFLOWS_DIR / "audit-milestone.md").read_text(encoding="utf-8")

    assert '"$phase_dir"/*-VERIFICATION.md' in execute_phase
    assert '"$phase_dir"/VERIFICATION.md "$phase_dir"/*-VERIFICATION.md' not in execute_phase
    assert 'ls "$phase_dir"/*-VERIFICATION.md 2>/dev/null' in planner
    assert 'find_files("$PHASE_DIR/*-VERIFICATION.md")' in verifier
    assert 'cat GPD/phases/01-*/*-VERIFICATION.md' in audit_milestone
    assert 'GPD/phases/01-*/VERIFICATION.md' not in audit_milestone


def test_debug_prompts_use_session_status_for_diagnosis_progress() -> None:
    debug_workflow = (WORKFLOWS_DIR / "debug.md").read_text(encoding="utf-8")
    debugger = (AGENTS_DIR / "gpd-debugger.md").read_text(encoding="utf-8")

    assert 'set `session_status: diagnosed`' in debug_workflow
    assert 'Update status in frontmatter to "diagnosed"' not in debug_workflow
    assert 'update `session_status` to "diagnosed"' in debugger
    assert 'Update status to "diagnosed"' not in debugger


def test_resume_workflow_surfaces_contract_load_and_validation_state() -> None:
    resume_work = (WORKFLOWS_DIR / "resume-work.md").read_text(encoding="utf-8")

    assert "@{GPD_INSTALL_DIR}/templates/state-json-schema.md" in resume_work
    assert "project_contract_validation" in resume_work
    assert "project_contract_load_info" in resume_work
    assert "execution_resume_file_source" in resume_work
    assert "session_resume_file" in resume_work
    assert "machine_change_detected" in resume_work
    assert "machine_change_notice" in resume_work
    assert "current_hostname" in resume_work
    assert "current_platform" in resume_work
    assert "session_hostname" in resume_work
    assert "session_platform" in resume_work
    assert "only when `project_contract_load_info` is clean and `project_contract_validation` passes" in resume_work
    assert "records whether that contract loaded cleanly and what blocked it if not." in resume_work
    assert "approval gate for treating the structured contract as authoritative" in resume_work
    assert "Contract repair required:" in resume_work
    assert "Repair the blocked contract or state-integrity issue before planning or execution" in resume_work


def test_execution_observability_and_resume_surfaces_stay_conservative_about_stalls() -> None:
    help_command = (COMMANDS_DIR / "help.md").read_text(encoding="utf-8")
    help_workflow = (WORKFLOWS_DIR / "help.md").read_text(encoding="utf-8")
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    progress = (WORKFLOWS_DIR / "progress.md").read_text(encoding="utf-8")
    resume_work = (WORKFLOWS_DIR / "resume-work.md").read_text(encoding="utf-8")

    assert "gpd observe execution" in help_command
    assert "progress / waiting state" in help_command
    assert "possibly stalled" in help_command
    assert "read-only checks" in help_command
    assert "gpd cost" in help_command
    assert cost_summary_surface_note() in help_command
    assert "gpd observe execution" in help_workflow
    assert "progress / waiting state" in help_workflow
    assert "read-only checks" in help_workflow
    assert "gpd cost" in help_workflow
    assert cost_summary_surface_note() in help_workflow
    assert "For read-only long-run visibility from your normal system terminal, use `gpd observe execution`." in readme
    assert "conservatively say `possibly stalled` instead of relying on runtime hotkeys" in readme
    assert "Start with `gpd observe show --last 20` when you need the recent event trail" in readme
    assert "route it through the runtime `tangent` command first" in readme
    assert "For a read-only machine-local usage / cost summary from your normal system terminal, use `gpd cost`." in readme
    assert "advisory only" in readme or "billing truth" in readme
    assert "gpd resume --recent" in help_command
    assert "gpd resume --recent" in help_workflow
    assert "gpd resume --recent" in readme
    assert "When STATE.md appears out of sync with disk reality" in progress
    assert "advisory context only" in resume_work
    assert "it is not a ranked bounded-segment resume candidate and does not justify `resume_mode=\"bounded_segment\"`." in resume_work


def test_pause_resume_and_help_wiring_keep_runtime_handoff_and_local_snapshot_boundary() -> None:
    pause_work = (WORKFLOWS_DIR / "pause-work.md").read_text(encoding="utf-8")
    resume_work = (WORKFLOWS_DIR / "resume-work.md").read_text(encoding="utf-8")
    help_workflow = (WORKFLOWS_DIR / "help.md").read_text(encoding="utf-8")

    assert "/gpd:resume-work" in resume_work
    assert "gpd resume" in resume_work
    assert "gpd resume --recent" in resume_work
    assert "`gpd init resume`" in resume_work
    assert "guided runtime path" in resume_work
    assert "public local read-only summary" in resume_work
    assert "cross-project discovery surface" in resume_work
    assert "machine-readable intake" in resume_work
    assert "segment_candidates" in resume_work
    assert "Do NOT invent additional candidates from plan files without summaries, auto-checkpoints, or other ad hoc checkpoints." in resume_work
    assert "/gpd:resume-work" in pause_work
    assert "gpd resume" in pause_work
    assert "gpd resume --recent" in pause_work
    assert "This is the canonical pause/resume handoff for the current phase." in pause_work
    assert "context handoff" in pause_work or "session continuity" in pause_work
    assert "/gpd:resume-work" in help_workflow
    assert "current-workspace read-only recovery snapshot" in help_workflow
    assert "gpd resume" in help_workflow
    assert recovery_ladder_note(
        resume_work_phrase="`/gpd:resume-work`",
        suggest_next_phrase="`/gpd:suggest-next`",
        pause_work_phrase="`/gpd:pause-work`",
    ) in help_workflow
    assert "gpd observe execution" in help_workflow
    assert "suggested read-only checks rather than runtime hotkeys" in help_workflow


def test_stage6_surfaces_protocol_bundle_context_across_planning_execution_and_verification() -> None:
    planner_prompt = (TEMPLATES_DIR / "planner-subagent-prompt.md").read_text(encoding="utf-8")
    execute_phase = (WORKFLOWS_DIR / "execute-phase.md").read_text(encoding="utf-8")
    execute_plan = (WORKFLOWS_DIR / "execute-plan.md").read_text(encoding="utf-8")
    verify_work = (WORKFLOWS_DIR / "verify-work.md").read_text(encoding="utf-8")
    continuation = (TEMPLATES_DIR / "continuation-prompt.md").read_text(encoding="utf-8")
    planner_agent = (AGENTS_DIR / "gpd-planner.md").read_text(encoding="utf-8")
    checker_agent = (AGENTS_DIR / "gpd-plan-checker.md").read_text(encoding="utf-8")
    executor_agent = (AGENTS_DIR / "gpd-executor.md").read_text(encoding="utf-8")
    verifier_agent = (AGENTS_DIR / "gpd-verifier.md").read_text(encoding="utf-8")
    executor_guide = (REFERENCES_DIR / "execution" / "executor-subfield-guide.md").read_text(encoding="utf-8")

    assert "**Protocol Bundles:** {protocol_bundle_context}" in planner_prompt
    assert "protocol_bundle_context" in execute_phase
    assert "selected_protocol_bundle_ids" in execute_plan
    assert "protocol_bundle_verifier_extensions" in verify_work
    assert "primary source for bundle checklist extensions" in verify_work
    assert "{protocol_bundle_context}" in continuation
    assert "selected protocol bundle context" in planner_agent
    assert "protocol_bundle_coverage" in checker_agent
    assert "additive routing hints" in executor_agent
    assert "first additive specialization pass" in executor_agent
    assert "bundle checklist extensions" in verifier_agent
    assert "prefer `protocol_bundle_verifier_extensions` and `protocol_bundle_context` from init JSON" in verifier_agent
    assert "fallback index or a manual cross-check" in executor_guide
    assert "not a default route" in executor_guide


def test_stage6_executor_bundle_fallback_stays_generic_when_no_bundle_fits() -> None:
    executor_agent = (AGENTS_DIR / "gpd-executor.md").read_text(encoding="utf-8")
    executor_guide = (REFERENCES_DIR / "execution" / "executor-subfield-guide.md").read_text(encoding="utf-8")

    assert "If no bundle is selected" in executor_agent
    assert "stay with the generic execution flow plus contract-backed anchors and checks" in executor_agent
    assert "instead of forcing the work into a topic bucket" in executor_agent
    assert "Do not stay trapped in the original bundle or fallback subfield" in executor_agent
    assert "If no row cleanly fits, stay with generic execution guidance plus core verification expectations instead of guessing." in executor_guide


def test_stage7_runtime_parity_docs_use_canonical_model_resolution_and_generic_handoff_rules() -> None:
    model_resolution = (
        REFERENCES_DIR / "orchestration" / "model-profile-resolution.md"
    ).read_text(encoding="utf-8")
    agent_delegation = (REFERENCES_DIR / "orchestration" / "agent-delegation.md").read_text(encoding="utf-8")
    execute_phase = (WORKFLOWS_DIR / "execute-phase.md").read_text(encoding="utf-8")
    execute_plan = (WORKFLOWS_DIR / "execute-plan.md").read_text(encoding="utf-8")
    quick = (WORKFLOWS_DIR / "quick.md").read_text(encoding="utf-8")

    assert "Do not scrape `GPD/config.json` directly in workflows." in model_resolution
    assert "gpd resolve-tier" in model_resolution
    assert "gpd resolve-model" in model_resolution
    assert "Delegation Contract" in agent_delegation
    assert "Return-envelope parity" in agent_delegation
    assert "control decision authority throughout execution" in execute_plan
    assert "Handoff verification" in execute_plan
    assert "Handoff verification" in execute_phase
    assert "False failure report despite delivered work" in execute_phase
    assert "Handoff verification" in quick
    assert "templates/planner-subagent-prompt.md" in quick
    assert "templates/phase-prompt.md" in quick
    assert "templates/plan-contract-schema.md" in quick
    assert "project_contract_load_info.status" in quick
    assert "project_contract_validation.valid" in quick
    assert "project_contract_validation" in quick
    assert "project_contract_load_info" in quick
    assert "Quick mode still inherits the approved `project_contract` only when `project_contract_load_info` is clean and `project_contract_validation` passes" in quick
    assert "**Project Contract Load Info:** {project_contract_load_info}" in quick
    assert "**Project Contract Validation:** {project_contract_validation}" in quick
    assert "## CHECKPOINT REACHED" in quick
    assert "classifyHandoffIfNeeded" not in execute_phase
    assert "classifyHandoffIfNeeded" not in execute_plan
    assert "classifyHandoffIfNeeded" not in quick
    assert "cat GPD/config.json" not in model_resolution
    assert "print(c.get('model_profile', 'review'))" not in execute_phase


def test_stage8_surfaces_decisive_comparisons_paper_quality_artifacts_and_profile_invariants() -> None:
    compare_command = (COMMANDS_DIR / "compare-results.md").read_text(encoding="utf-8")
    compare_workflow = (WORKFLOWS_DIR / "compare-results.md").read_text(encoding="utf-8")
    internal_template = (TEMPLATES_DIR / "paper" / "internal-comparison.md").read_text(encoding="utf-8")
    figure_tracker = (TEMPLATES_DIR / "paper" / "figure-tracker.md").read_text(encoding="utf-8")
    write_paper = (WORKFLOWS_DIR / "write-paper.md").read_text(encoding="utf-8")
    new_project = (WORKFLOWS_DIR / "new-project.md").read_text(encoding="utf-8")
    execute_phase = (WORKFLOWS_DIR / "execute-phase.md").read_text(encoding="utf-8")
    scoring = (REFERENCES_DIR / "publication" / "paper-quality-scoring.md").read_text(encoding="utf-8")
    settings = (WORKFLOWS_DIR / "settings.md").read_text(encoding="utf-8")
    profiles = (REFERENCES_DIR / "orchestration" / "model-profiles.md").read_text(encoding="utf-8")
    quick_reference = (REFERENCES_DIR / "verification" / "core" / "verification-quick-reference.md").read_text(
        encoding="utf-8"
    )
    verifier_profiles = (
        REFERENCES_DIR / "verification" / "meta" / "verifier-profile-checks.md"
    ).read_text(encoding="utf-8")
    planner = (AGENTS_DIR / "gpd-planner.md").read_text(encoding="utf-8")
    executor = (AGENTS_DIR / "gpd-executor.md").read_text(encoding="utf-8")
    verifier_agent = (AGENTS_DIR / "gpd-verifier.md").read_text(encoding="utf-8")

    assert "emit decisive verdicts" in compare_command
    assert "GPD/comparisons/[slug]-COMPARISON.md" in compare_workflow
    assert "GPD/analysis/comparison-{slug}.md" not in compare_workflow
    assert "comparison_verdicts" in internal_template
    assert "figure_registry" in figure_tracker
    assert "role: smoking_gun|benchmark|comparison|sanity_check|publication_polish|other" in figure_tracker
    assert "canonical schema source of truth" in figure_tracker
    assert "validate paper-quality --from-project ." in write_paper
    assert "Before reading or updating `GPD/paper/FIGURE_TRACKER.md`, load" in write_paper
    assert '"review_cadence": "adaptive"' in new_project
    assert "Adaptive review cadence" in new_project
    assert "prior decisive `contract_results`, decisive `comparison_verdicts`, or an explicit approach lock" in execute_phase
    assert "figure_registry" in scoring
    assert "Review (Recommended)" in settings
    assert "all required contract-aware checks" in profiles
    assert "current registry: 5.1-5.19" in quick_reference
    assert "still run every contract-aware check required by the plan" in verifier_profiles
    assert "required first-result, anchor, and pre-fanout checkpoints" in planner
    assert "Do NOT change conventions mid-project without an explicit checkpoint" in planner
    assert "Required first-result, anchor, and pre-fanout gates still apply even in yolo mode" in executor
    assert "live machine source of truth is the verifier registry" in verifier_agent


def test_publication_workflows_refresh_bibliography_audit_after_bibliography_changes() -> None:
    write_paper = (WORKFLOWS_DIR / "write-paper.md").read_text(encoding="utf-8")
    respond = (WORKFLOWS_DIR / "respond-to-referees.md").read_text(encoding="utf-8")
    peer_review = (WORKFLOWS_DIR / "peer-review.md").read_text(encoding="utf-8")

    assert "If the bibliography changed after the last audit, refresh `paper/BIBLIOGRAPHY-AUDIT.json` before strict review." in write_paper
    assert "Refresh `paper/BIBLIOGRAPHY-AUDIT.json` after the bibliography changes before entering strict review or `pre_submission_review`." in write_paper
    assert "If the manuscript bibliography or citation set changed after the last audit, refresh `paper/BIBLIOGRAPHY-AUDIT.json` before building the reproducibility manifest." in write_paper
    assert "refresh `${PAPER_DIR}/BIBLIOGRAPHY-AUDIT.json` before generating the response letter or proceeding to final review" in respond
    assert "If the manuscript bibliography changed after the last audit, refresh `BIBLIOGRAPHY_AUDIT_PATH` before proceeding." in peer_review
    assert "absent, stale, or not review-ready" in peer_review


def test_stage9_adaptive_mode_and_review_cadence_docs_stay_aligned() -> None:
    research_phase = (WORKFLOWS_DIR / "research-phase.md").read_text(encoding="utf-8")
    verify_work = (WORKFLOWS_DIR / "verify-work.md").read_text(encoding="utf-8")
    plan_phase = (WORKFLOWS_DIR / "plan-phase.md").read_text(encoding="utf-8")
    new_project = (WORKFLOWS_DIR / "new-project.md").read_text(encoding="utf-8")
    new_milestone = (WORKFLOWS_DIR / "new-milestone.md").read_text(encoding="utf-8")
    set_profile = (WORKFLOWS_DIR / "set-profile.md").read_text(encoding="utf-8")
    settings = (WORKFLOWS_DIR / "settings.md").read_text(encoding="utf-8")
    planning_config = (REFERENCES_DIR / "planning" / "planning-config.md").read_text(encoding="utf-8")
    research_modes = (REFERENCES_DIR / "research" / "research-modes.md").read_text(encoding="utf-8")
    meta_orchestration = (REFERENCES_DIR / "orchestration" / "meta-orchestration.md").read_text(encoding="utf-8")

    expected_anchor = "prior decisive evidence or an explicit approach lock"

    assert expected_anchor in research_phase
    assert expected_anchor in plan_phase
    assert expected_anchor in research_modes
    assert expected_anchor in meta_orchestration
    assert "anchors or decisive evidence make one method family clearly preferable" in new_project
    assert "prior milestones already provide decisive evidence or an explicit approach lock" in new_milestone
    assert "project_contract_validation" in new_milestone
    assert "project_contract_load_info" in new_milestone
    assert "project_contract_load_info.status" in new_milestone
    assert "project_contract_validation.valid" in new_milestone
    assert "only when `project_contract_load_info` is clean and `project_contract_validation.valid` is true" in new_milestone
    assert "checkpoint with the user and repair the stored contract before using it for milestone scope" in new_milestone
    assert "same contract-critical floor at all times" in verify_work
    assert "phase 1-2" not in plan_phase
    assert "phase 3+" not in plan_phase
    assert "N≥3" not in plan_phase
    assert "does NOT rewrite `execution.review_cadence`" in set_profile
    assert "verify_between_waves" not in set_profile
    assert "independent of `model_profile` and `research_mode`" in settings
    assert "wall-clock and task budgets still create bounded segments in every autonomy mode" in planning_config
    assert "phase number, wave number, and `model_profile` do not create or retire these gates by themselves" in planning_config
    assert "There is no separate `adaptive_transition` block" in research_modes
    assert "The decision is evidence-driven, not phase-count-driven." in meta_orchestration
    assert "Proxy-only or sanity-only passes do NOT satisfy this." in meta_orchestration


def test_settings_workflow_surfaces_qualitative_model_cost_onboarding_and_runtime_defaults() -> None:
    settings_command = (COMMANDS_DIR / "settings.md").read_text(encoding="utf-8")
    settings_workflow = (WORKFLOWS_DIR / "settings.md").read_text(encoding="utf-8")

    assert "**Model cost posture**: Max quality / Balanced / Budget-aware" in settings_command
    assert "Prefer runtime defaults unless the user explicitly wants pinned tier overrides" in settings_command
    assert "Treat `Balanced` as the default qualitative posture" in settings_command
    assert "dollar" not in settings_command.lower()

    assert "Balanced (Recommended)" in settings_workflow
    assert "runtime defaults" in settings_workflow
    assert "tier-1" in settings_workflow
    assert "tier-2" in settings_workflow
    assert "tier-3" in settings_workflow
    assert cost_after_runs_guidance() in settings_workflow
    assert "dollar" not in settings_workflow.lower()

    assert "Tier models for the active runtime" in settings_command
    assert "Tier Models" in settings_workflow
    assert "Step-by-step setup for runtime-specific tier-1, tier-2, and tier-3 model strings" in settings_workflow
    assert "use runtime defaults" in settings_command
    assert "Use runtime defaults" in settings_workflow
    assert "configure explicit tier-1, tier-2, tier-3 model strings" in settings_command
    assert "Configure explicit tier models" in settings_workflow
    assert "advisory only" in settings_command
    assert "Local CLI bridge" in settings_workflow
    assert "gpd --help" in settings_workflow
    assert f"Local CLI bridge: {local_cli_bridge_note()}" in settings_workflow
    assert "gpd permissions sync --runtime <runtime> --autonomy balanced" in settings_workflow
    assert "This sync only updates runtime-owned permission settings; it does not validate install health or workflow/tool readiness." in settings_workflow
    assert "current profile tier mix" in settings_workflow
    assert "gpd presets show <preset>" in settings_workflow
    assert "gpd presets apply <preset> --dry-run" in settings_workflow


def test_help_surfaces_distinguish_runtime_slash_commands_from_local_cli_subcommands() -> None:
    help_command = (COMMANDS_DIR / "help.md").read_text(encoding="utf-8")
    help_workflow = (WORKFLOWS_DIR / "help.md").read_text(encoding="utf-8")

    for content in (help_command, help_workflow):
        assert "`/gpd:*`" in content
        assert "in-runtime" in content
        assert "slash-command" in content
        assert "local `gpd` CLI" in content
        assert "gpd --help" in content
        assert "gpd permissions sync --runtime <runtime> --autonomy balanced" in content
        assert "install/readiness/permissions/diagnostics surface directly" in content
        assert "`gpd doctor` checks the selected install target and runtime-local readiness signals." in content
        assert "`gpd permissions ...` checks runtime-owned approval/alignment only." in content
        assert "gpd validate command-context gpd:<name>" in content
        assert "gpd observe execution" in content


def test_help_command_keeps_static_quick_start_while_workflow_owns_full_reference() -> None:
    help_command = (COMMANDS_DIR / "help.md").read_text(encoding="utf-8")
    help_workflow = (WORKFLOWS_DIR / "help.md").read_text(encoding="utf-8")
    quick_start = _extract_between(
        help_command,
        "## Step 2: Quick Start (Default Output)",
        "## Step 3: Full Command Reference (--all)",
    )

    assert "@{GPD_INSTALL_DIR}/workflows/help.md" in help_command
    assert "## Invocation Surfaces" not in quick_start
    assert "## Invocation Surfaces" in help_workflow
    assert "## Core Workflow" in help_workflow
    assert "Choose the path that matches your starting point:" in quick_start
    assert "Choose the path that matches your starting point:" in help_workflow
    for token in (
        "/gpd:new-project",
        "/gpd:new-project --minimal",
        "/gpd:map-research",
        "/gpd:resume-work",
        "gpd resume --recent",
        "gpd --help",
        "gpd permissions sync --runtime <runtime> --autonomy balanced",
        "gpd presets show <preset>",
        "gpd observe execution",
        "/gpd:suggest-next",
        "/gpd:tangent",
        "/gpd:settings",
        "/gpd:help --all",
    ):
        assert token in quick_start
        assert token in help_workflow


def test_help_workflow_state_aware_variant_surfaces_paused_resume_branch() -> None:
    help_workflow = (WORKFLOWS_DIR / "help.md").read_text(encoding="utf-8")

    assert "**Project exists, paused or resumable:**" in help_workflow
    assert "gpd resume --recent" in help_workflow
    assert "/gpd:resume-work" in help_workflow
    assert "/gpd:progress" in help_workflow
    assert "/gpd:suggest-next" in help_workflow
    assert "/gpd:tangent" in help_workflow


def test_help_and_execution_surfaces_wire_tangent_control_path() -> None:
    help_workflow = (WORKFLOWS_DIR / "help.md").read_text(encoding="utf-8")
    plan_phase = (WORKFLOWS_DIR / "plan-phase.md").read_text(encoding="utf-8")
    execute_phase = (WORKFLOWS_DIR / "execute-phase.md").read_text(encoding="utf-8")
    execute_plan = (WORKFLOWS_DIR / "execute-plan.md").read_text(encoding="utf-8")
    tangent_workflow = (WORKFLOWS_DIR / "tangent.md").read_text(encoding="utf-8")

    assert "/gpd:tangent" in help_workflow
    assert re.search(r"/gpd:tangent[^\n]*?(?:tangent|side investigation|alternative direction|parallel)", help_workflow, re.I)
    assert "/gpd:tangent" in plan_phase
    assert re.search(r"/gpd:tangent.*?(?:side|alternative|parallel|branch)", plan_phase, re.I | re.S)
    assert "/gpd:tangent" in execute_phase
    assert re.search(r"/gpd:tangent.*?(?:branch|follow-up|alternative)", execute_phase, re.I | re.S)
    assert "tangent_summary" in execute_phase
    assert "tangent_decision" in execute_phase
    assert "optional `tangent_summary` and `tangent_decision`" in execute_phase
    assert "keep it inside the same live execution payload instead of inventing a new tangent state machine" in execute_phase
    assert "Do not create a new branch, child plan, or side subagent from executor initiative alone." in execute_phase
    assert "tangent_summary" in execute_plan
    assert "tangent_decision" in execute_plan
    assert "keep it in the same execution payload rather than inventing a new event family. Optional fields:" in execute_plan
    assert (
        "keep the optional `tangent_summary` / `tangent_decision` fields on the existing `execution` payload until "
        "that review stop is explicitly resolved. Do not auto-branch or create side work from telemetry alone."
    ) in execute_plan
    assert "{GPD_INSTALL_DIR}/workflows/quick.md" in tangent_workflow
    assert "{GPD_INSTALL_DIR}/workflows/add-todo.md" in tangent_workflow
    assert "{GPD_INSTALL_DIR}/workflows/branch-hypothesis.md" in tangent_workflow


def test_planner_and_plan_phase_keep_no_silent_branching_and_exploit_tangent_suppression() -> None:
    planner = (REPO_ROOT / "src/gpd/agents/gpd-planner.md").read_text(encoding="utf-8")
    plan_phase = (WORKFLOWS_DIR / "plan-phase.md").read_text(encoding="utf-8")

    for content in (planner, plan_phase):
        assert "do NOT silently" in content
        assert "/gpd:tangent" in content
        assert "/gpd:branch-hypothesis" in content

    assert "Explore mode widens analysis and comparison, not branch creation." in planner
    assert "Explore mode alone does not authorize git-backed branches" in planner
    assert (
        "Suppress optional tangent surfacing unless the user explicitly requests it or the current approach is blocked"
        in planner
    )
    assert "do not auto-create git-backed branches or branch-like plans" in plan_phase
    assert "`git.branching_strategy` does not override this rule." in plan_phase
    assert "suppress optional tangents entirely unless the user explicitly requests them" in plan_phase
    assert "Do not volunteer `/gpd:branch-hypothesis` as the default response in exploit mode." in plan_phase


def test_help_surfaces_describe_regression_check_as_metadata_scan_not_full_reverification() -> None:
    help_command = (COMMANDS_DIR / "help.md").read_text(encoding="utf-8")
    help_workflow = (WORKFLOWS_DIR / "help.md").read_text(encoding="utf-8")

    for content in (help_command, help_workflow):
        assert "SUMMARY" in content
        assert "frontmatter" in content
        assert "convention conflicts" in content
        assert "VERIFICATION" in content
        assert "canonical statuses" in content
        assert "re-runs dimensional analysis" not in content
        assert "re-runs limiting cases" not in content
        assert "re-runs numerical checks" not in content


def test_help_surfaces_use_projectless_examples_that_satisfy_command_context_predicates() -> None:
    help_command = (COMMANDS_DIR / "help.md").read_text(encoding="utf-8")
    help_workflow = (WORKFLOWS_DIR / "help.md").read_text(encoding="utf-8")

    for content in (help_command, help_workflow):
        assert 'Usage: `/gpd:derive-equation "derive the one-loop beta function"`' in content
        assert "Usage: `/gpd:dimensional-analysis 3`" in content
        assert "Usage: `/gpd:limiting-cases 3`" in content
        assert "Usage: `/gpd:numerical-convergence 3`" in content
        assert "Usage: `/gpd:compare-experiment predictions.csv experiment.csv`" in content
        assert "Usage: `/gpd:sensitivity-analysis --target cross_section --params g,m,Lambda --method numerical`" in content


def test_verification_and_publication_prompts_keep_decisive_contract_targets_reader_visible() -> None:
    verify_work = (WORKFLOWS_DIR / "verify-work.md").read_text(encoding="utf-8")
    write_paper = (WORKFLOWS_DIR / "write-paper.md").read_text(encoding="utf-8")
    peer_review = (WORKFLOWS_DIR / "peer-review.md").read_text(encoding="utf-8")
    respond = (WORKFLOWS_DIR / "respond-to-referees.md").read_text(encoding="utf-8")

    assert "researcher can recognize in the phase promise" in verify_work
    assert "Do not mark the parent claim or acceptance test as passed until that decisive comparison is resolved." in verify_work
    assert "Missing generic `verification_status` / `confidence` tags alone are not blockers." in write_paper
    assert "Only require the manuscript to surface decisive comparisons for claims it actually makes." in write_paper
    assert "Do not enter `pre_submission_review` with a missing or non-review-ready reproducibility manifest" in write_paper
    assert "Review-support artifacts are scaffolding, not substitutes for contract-backed evidence." in peer_review
    assert "Treat referee requests beyond the manuscript's honest scope as optional unless they expose a real support gap" in respond


def test_repo_graph_prompt_scope_counts_match_repo_inventory() -> None:
    assert parse_scope_count("src/gpd/commands/*.md") == len(list(COMMANDS_DIR.glob("*.md")))
    assert parse_scope_count("src/gpd/agents/*.md") == len(list(AGENTS_DIR.glob("*.md")))
    assert parse_scope_count("src/gpd/specs/workflows/*.md") == len(list(WORKFLOWS_DIR.glob("*.md")))
    assert parse_scope_count("src/gpd/specs/templates/**/*.md") == len(list(TEMPLATES_DIR.rglob("*.md")))
    assert parse_scope_count("src/gpd/specs/references/**/*.md") == len(list(REFERENCES_DIR.rglob("*.md")))


def test_repo_graph_same_stem_command_inventory_matches_repo() -> None:
    graph_text = GRAPH_PATH.read_text(encoding="utf-8")
    match = re.search(
        r"src/gpd/commands/\{([^}]*)\}\.md -> src/gpd/specs/workflows/\{same stems\}\.md",
        graph_text,
    )
    assert match is not None, "Missing same-stem command inventory in tests README graph"

    graph_stems = {stem.strip() for stem in match.group(1).split(",") if stem.strip()}
    repo_stems = {path.stem for path in COMMANDS_DIR.glob("*.md")} & {path.stem for path in WORKFLOWS_DIR.glob("*.md")}
    assert graph_stems == repo_stems


def test_repo_graph_tracks_staged_review_panel_wiring() -> None:
    graph_text = GRAPH_PATH.read_text(encoding="utf-8")
    review_agents = [
        "gpd-review-reader",
        "gpd-review-literature",
        "gpd-review-math",
        "gpd-review-physics",
        "gpd-review-significance",
    ]

    for agent_name in review_agents:
        assert agent_name in graph_text, f"Tests README graph is missing {agent_name}"

    assert (
        "src/gpd/commands/peer-review.md -> src/gpd/agents/"
        "{gpd-review-reader,gpd-review-literature,gpd-review-math,gpd-review-physics,gpd-review-significance,gpd-referee}.md"
    ) in graph_text
    assert (
        "src/gpd/specs/workflows/peer-review.md -> src/gpd/agents/"
        "{gpd-review-reader,gpd-review-literature,gpd-review-math,gpd-review-physics,gpd-review-significance,gpd-referee}.md"
    ) in graph_text
    assert (
        "src/gpd/agents/{gpd-review-reader,gpd-review-literature,gpd-review-math,"
        "gpd-review-physics,gpd-review-significance,gpd-referee}.md"
        " -> src/gpd/specs/references/publication/peer-review-panel.md"
    ) in graph_text
