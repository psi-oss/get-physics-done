"""Regression tests for prompt/template wiring."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from gpd import registry
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
GRAPH_PATH = REPO_ROOT / "tests" / "README.md"

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


def test_referee_workflow_mentions_optional_pdf_compile_and_missing_tex_prompt() -> None:
    referee = (AGENTS_DIR / "gpd-referee.md").read_text(encoding="utf-8")
    peer_review = (WORKFLOWS_DIR / "peer-review.md").read_text(encoding="utf-8")

    assert "compile the latest referee-report `.tex` file to a matching `.pdf`" in referee
    assert "Do NOT install TeX yourself" in referee
    assert "Continue now with `.gpd/REFEREE-REPORT.md` + `.gpd/REFEREE-REPORT.tex` only" in peer_review
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
    assert "artifact manifest" in write_paper.review_contract.required_evidence
    assert ".gpd/REFEREE-REPORT.tex" in write_paper.review_contract.required_outputs

    assert peer_review.review_contract is not None
    assert peer_review.review_contract.review_mode == "publication"
    assert ".gpd/REFEREE-REPORT.md" in peer_review.review_contract.required_outputs
    assert ".gpd/REFEREE-REPORT.tex" in peer_review.review_contract.required_outputs
    assert ".gpd/review/CLAIMS.json" in peer_review.review_contract.required_outputs
    assert ".gpd/review/STAGE-interestingness.json" in peer_review.review_contract.required_outputs
    assert ".gpd/review/REFEREE-DECISION.json" in peer_review.review_contract.required_outputs
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
        ".gpd/review/CLAIMS.json",
        ".gpd/review/STAGE-reader.json",
        ".gpd/review/STAGE-literature.json",
        ".gpd/review/STAGE-math.json",
        ".gpd/review/STAGE-physics.json",
        ".gpd/review/STAGE-interestingness.json",
        ".gpd/review/REVIEW-LEDGER.json",
        ".gpd/review/REFEREE-DECISION.json",
    ]
    assert peer_review.review_contract.final_decision_output == ".gpd/review/REFEREE-DECISION.json"

    assert verify_work.review_contract is not None
    assert verify_work.review_contract.required_state == "phase_executed"
    assert "phase_artifacts" in verify_work.review_contract.preflight_checks

    assert respond_to_referees.review_contract is not None
    assert ".gpd/paper/REFEREE_RESPONSE.md" in respond_to_referees.review_contract.required_outputs
    assert ".gpd/AUTHOR-RESPONSE.md" in respond_to_referees.review_contract.required_outputs
    assert "structured referee issues" in respond_to_referees.review_contract.required_evidence
    assert "peer-review review ledger when available" in respond_to_referees.review_contract.required_evidence
    assert "peer-review decision artifacts when available" in respond_to_referees.review_contract.required_evidence
    assert "gpd:peer-review" in registry.list_review_commands()
    assert "gpd:write-paper" in registry.list_review_commands()
    assert "gpd:respond-to-referees" in registry.list_review_commands()
    assert "gpd:verify-work" in registry.list_review_commands()


def test_representative_commands_expose_expected_context_modes() -> None:
    assert registry.get_command("help").context_mode == "global"
    assert registry.get_command("compare-results").context_mode == "project-aware"
    assert registry.get_command("map-research").context_mode == "projectless"
    assert registry.get_command("slides").context_mode == "projectless"
    assert registry.get_command("discover").context_mode == "project-aware"
    assert registry.get_command("explain").context_mode == "project-aware"
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

    assert ".gpd/review/REVIEW-LEDGER.json" in command_text
    assert ".gpd/review/REFEREE-DECISION.json" in command_text
    assert "REVIEW-LEDGER*.json" in workflow_text
    assert "REFEREE-DECISION*.json" in workflow_text
    assert "REVIEW-LEDGER{-RN}.json" in writer_text
    assert "REFEREE-DECISION{-RN}.json" in writer_text


def test_new_project_recommended_autonomy_matches_balanced_default() -> None:
    workflow_text = (WORKFLOWS_DIR / "new-project.md").read_text(encoding="utf-8")

    assert workflow_text.count('"autonomy": "balanced"') >= 2
    assert "Recommended defaults use Balanced autonomy" in workflow_text
    assert (
        "Config: Balanced autonomy | Adaptive review cadence | Balanced research mode | Parallel | All agents | Review profile"
        in workflow_text
    )
    assert "Recommended defaults use YOLO autonomy" not in workflow_text
    assert "Config: YOLO autonomy | Balanced research mode | Parallel | All agents | Review profile" not in workflow_text


def test_new_project_requires_scoping_contract_across_setup_modes() -> None:
    workflow_text = (WORKFLOWS_DIR / "new-project.md").read_text(encoding="utf-8")
    command_text = (COMMANDS_DIR / "new-project.md").read_text(encoding="utf-8")

    assert "Auto mode compresses intake; it does not override autonomy review gates after the scoping contract is approved" in workflow_text
    assert "Require one explicit scoping approval gate before requirements and roadmap generation" in workflow_text
    assert "Roadmap approval: Auto-approve only for `balanced` / `yolo`; if `autonomy=babysit`, present the draft roadmap before commit" in workflow_text
    assert "Minimal mode is still allowed to be lean, but it is not allowed to be contract-free." in workflow_text
    assert "Do NOT skip the initial scoping-contract approval gate." in workflow_text
    assert "scoping contract with decisive outputs, anchors, and explicit approval" in command_text


def test_new_project_wiring_mentions_contract_persistence_and_contract_first_downstream_generation() -> None:
    workflow_text = (WORKFLOWS_DIR / "new-project.md").read_text(encoding="utf-8")
    command_text = (COMMANDS_DIR / "new-project.md").read_text(encoding="utf-8")

    assert "gpd state set-project-contract" in workflow_text
    assert "gpd --raw validate project-contract /tmp/gpd-project-contract.json" in workflow_text
    assert "Read PROJECT.md and `.gpd/state.json` and extract" in workflow_text
    assert "Derive phases from requirements AND the approved project contract" in workflow_text
    assert "If auto mode and `autonomy` is not `babysit`" in workflow_text
    assert "@{GPD_INSTALL_DIR}/templates/state-json-schema.md" in command_text


def test_questioning_guide_requires_anchors_and_disconfirming_questions() -> None:
    guide_text = (REFERENCES_DIR / "research" / "questioning.md").read_text(encoding="utf-8")

    assert "Surface anchors early." in guide_text
    assert "Pressure-test the first story." in guide_text
    assert "Once you have a plausible framing on the table" in guide_text
    assert "Ground-truth anchors -- what reality should constrain this:" in guide_text
    assert "Disconfirmation and failure -- how the current framing could be wrong:" in guide_text
    assert "Do not count turns mechanically." in guide_text
    assert "What would be a misleading proxy for success" in guide_text


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


def test_planning_and_phase_templates_surface_active_reference_context() -> None:
    planner_prompt = (TEMPLATES_DIR / "planner-subagent-prompt.md").read_text(encoding="utf-8")
    phase_prompt = (TEMPLATES_DIR / "phase-prompt.md").read_text(encoding="utf-8")
    workflow_text = (WORKFLOWS_DIR / "plan-phase.md").read_text(encoding="utf-8")

    assert "Planning requires an approved scoping contract." in planner_prompt
    assert "**Project Contract:** {project_contract}" in planner_prompt
    assert "**Active References:** {active_reference_context}" in planner_prompt
    assert "@path/to/reference-or-benchmark-anchor.md" in phase_prompt
    assert "Planning requires an approved scoping contract in `.gpd/state.json`" in workflow_text
    assert "**Project Contract:** {project_contract}" in workflow_text
    assert "**Active References:** {active_reference_context}" in workflow_text
    assert "**Anchor coverage:** Required references, baselines, and prior outputs are surfaced" in workflow_text


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
    roadmapper_agent = (AGENTS_DIR / "gpd-roadmapper.md").read_text(encoding="utf-8")
    new_project = (WORKFLOWS_DIR / "new-project.md").read_text(encoding="utf-8")
    new_milestone = (WORKFLOWS_DIR / "new-milestone.md").read_text(encoding="utf-8")

    assert "## Contract Overview" in roadmap_template
    assert "**Contract Coverage:**" in roadmap_template
    assert "Contract coverage" in roadmapper_agent
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

    assert "At least one major phase, stage, or clearly defined first investigation chunk" in workflow_text
    assert "Use the coarsest decomposition the approved contract actually supports." in workflow_text
    assert "Do NOT invent literature, numerics, or paper phases unless the requirements or contract demand them." in workflow_text
    assert "If `project_contract` is empty, stale, or too underspecified to identify the phase contract slice, return `## CHECKPOINT REACHED`" in planner_prompt


def test_reference_workflows_require_anchor_registry_propagation() -> None:
    literature_workflow = (WORKFLOWS_DIR / "literature-review.md").read_text(encoding="utf-8")
    literature_command = (COMMANDS_DIR / "literature-review.md").read_text(encoding="utf-8")
    literature_agent = (AGENTS_DIR / "gpd-literature-reviewer.md").read_text(encoding="utf-8")
    map_workflow = (WORKFLOWS_DIR / "map-research.md").read_text(encoding="utf-8")
    map_command = (COMMANDS_DIR / "map-research.md").read_text(encoding="utf-8")
    mapper_agent = (AGENTS_DIR / "gpd-research-mapper.md").read_text(encoding="utf-8")

    assert "contract-critical anchors" in literature_workflow
    assert "Active Anchor Registry" in literature_command
    assert "active_anchors" in literature_agent
    assert "active_reference_context" in map_workflow
    assert "Contract-critical anchors, decisive benchmarks, prior artifacts" in map_command
    assert "REFERENCES.md is an anchor registry" in mapper_agent


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
    assert "suggest_contract_checks(contract)" in verify_workflow


def test_stage4_templates_and_workflows_surface_contract_results_and_verdict_ledgers() -> None:
    summary_template = (TEMPLATES_DIR / "summary.md").read_text(encoding="utf-8")
    verification_template = (TEMPLATES_DIR / "verification-report.md").read_text(encoding="utf-8")
    research_verification = (TEMPLATES_DIR / "research-verification.md").read_text(encoding="utf-8")
    execute_plan = (WORKFLOWS_DIR / "execute-plan.md").read_text(encoding="utf-8")
    verify_phase = (WORKFLOWS_DIR / "verify-phase.md").read_text(encoding="utf-8")
    compare_workflow = (WORKFLOWS_DIR / "compare-experiment.md").read_text(encoding="utf-8")
    comparison_template = (
        TEMPLATES_DIR / "paper" / "experimental-comparison.md"
    ).read_text(encoding="utf-8")
    executor_agent = (AGENTS_DIR / "gpd-executor.md").read_text(encoding="utf-8")
    verifier_agent = (AGENTS_DIR / "gpd-verifier.md").read_text(encoding="utf-8")

    assert "contract_results" in summary_template
    assert "comparison_verdicts" in summary_template
    assert "plan_contract_ref" in summary_template
    assert "Keep this ledger user-visible" in summary_template
    assert "omitting the corresponding `comparison_verdicts` entry makes the summary incomplete" in summary_template
    assert "verification_inputs" not in summary_template
    assert "contract_results" in verification_template
    assert "comparison_verdicts" in verification_template
    assert "Record only user-visible contract targets here" in verification_template
    assert "absence of a verdict is itself a gap" in verification_template
    assert "claim_id" in research_verification
    assert "acceptance_test_id" in research_verification
    assert "`contract_results` is authoritative." in execute_plan
    assert "Autonomy mode (`babysit` / `balanced` / `yolo`) and profile may change cadence or verbosity, but they do NOT relax contract-result emission." in execute_plan
    assert "contract_results" in verify_phase
    assert "Verification targets must stay user-visible" in verify_phase
    assert "must_haves" not in verify_phase
    assert "comparison_verdicts" in compare_workflow
    assert "subject_role" in comparison_template
    assert "Profiles and autonomy modes may compress prose or cadence, but they do NOT relax contract-result emission" in executor_agent
    assert "Use claim IDs, deliverable IDs, acceptance test IDs, reference IDs, and forbidden proxy IDs directly from the `contract` block." in verifier_agent


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
    assert "Pattern D: Auto-bounded" in executor_agent
    assert "active_execution_segment" in resume_work
    assert "execution_segment" in continuation
    assert "Required Checkpoint Payload" in checkpoints
    assert "rollback primitive" in checkpoint_flow


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
    assert "{protocol_bundle_context}" in continuation
    assert "selected protocol bundle context" in planner_agent
    assert "protocol_bundle_coverage" in checker_agent
    assert "selected protocol bundles first" in executor_agent
    assert "bundle checklist extensions" in verifier_agent
    assert "preferred way to decide which specialized files to load" in executor_guide


def test_stage7_runtime_parity_docs_use_canonical_model_resolution_and_generic_handoff_rules() -> None:
    model_resolution = (
        REFERENCES_DIR / "orchestration" / "model-profile-resolution.md"
    ).read_text(encoding="utf-8")
    agent_delegation = (REFERENCES_DIR / "orchestration" / "agent-delegation.md").read_text(encoding="utf-8")
    execute_phase = (WORKFLOWS_DIR / "execute-phase.md").read_text(encoding="utf-8")
    execute_plan = (WORKFLOWS_DIR / "execute-plan.md").read_text(encoding="utf-8")
    quick = (WORKFLOWS_DIR / "quick.md").read_text(encoding="utf-8")

    assert "Do not scrape `.gpd/config.json` directly in workflows." in model_resolution
    assert "gpd resolve-tier" in model_resolution
    assert "gpd resolve-model" in model_resolution
    assert "Delegation Contract" in agent_delegation
    assert "Return-envelope parity" in agent_delegation
    assert "control decision authority throughout execution" in execute_plan
    assert "Handoff verification" in execute_plan
    assert "Handoff verification" in execute_phase
    assert "False failure report despite delivered work" in execute_phase
    assert "Handoff verification" in quick
    assert "classifyHandoffIfNeeded" not in execute_phase
    assert "classifyHandoffIfNeeded" not in execute_plan
    assert "classifyHandoffIfNeeded" not in quick
    assert "cat .gpd/config.json" not in model_resolution
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
    assert ".gpd/comparisons/[slug]-COMPARISON.md" in compare_workflow
    assert "comparison_verdicts" in internal_template
    assert "figure_registry" in figure_tracker
    assert "role: smoking_gun|benchmark|comparison|sanity_check|publication_polish|other" in figure_tracker
    assert "validate paper-quality --from-project ." in write_paper
    assert '"review_cadence": "adaptive"' in new_project
    assert "Adaptive review cadence" in new_project
    assert "Start with explore-style coverage, then switch to exploit" in execute_phase
    assert "figure_registry" in scoring
    assert "Review (Recommended)" in settings
    assert "all required contract-aware checks" in profiles
    assert "current registry: 5.1-5.19" in quick_reference
    assert "still run every contract-aware check required by the plan" in verifier_profiles
    assert "required first-result, anchor, and pre-fanout checkpoints" in planner
    assert "Do NOT change conventions mid-project without an explicit checkpoint" in planner
    assert "Required first-result, anchor, and pre-fanout gates still apply even in yolo mode" in executor
    assert "live machine source of truth is the verifier registry" in verifier_agent


def test_stage9_adaptive_mode_and_review_cadence_docs_stay_aligned() -> None:
    research_phase = (WORKFLOWS_DIR / "research-phase.md").read_text(encoding="utf-8")
    verify_work = (WORKFLOWS_DIR / "verify-work.md").read_text(encoding="utf-8")
    new_project = (WORKFLOWS_DIR / "new-project.md").read_text(encoding="utf-8")
    new_milestone = (WORKFLOWS_DIR / "new-milestone.md").read_text(encoding="utf-8")
    set_profile = (WORKFLOWS_DIR / "set-profile.md").read_text(encoding="utf-8")
    settings = (WORKFLOWS_DIR / "settings.md").read_text(encoding="utf-8")
    research_modes = (REFERENCES_DIR / "research" / "research-modes.md").read_text(encoding="utf-8")
    meta_orchestration = (REFERENCES_DIR / "orchestration" / "meta-orchestration.md").read_text(encoding="utf-8")

    expected_anchor = "prior decisive evidence or an explicit approach lock"

    assert expected_anchor in research_phase
    assert expected_anchor in research_modes
    assert expected_anchor in meta_orchestration
    assert "anchors or decisive evidence make one method family clearly preferable" in new_project
    assert "prior milestones already provide decisive evidence or an explicit approach lock" in new_milestone
    assert "same contract-critical floor at all times" in verify_work
    assert "does NOT rewrite `execution.review_cadence`" in set_profile
    assert "verify_between_waves" not in set_profile
    assert "independent of `model_profile` and `research_mode`" in settings
    assert "There is no separate `adaptive_transition` block" in research_modes


def test_verification_and_publication_prompts_keep_decisive_contract_targets_reader_visible() -> None:
    verify_work = (WORKFLOWS_DIR / "verify-work.md").read_text(encoding="utf-8")
    write_paper = (WORKFLOWS_DIR / "write-paper.md").read_text(encoding="utf-8")
    peer_review = (WORKFLOWS_DIR / "peer-review.md").read_text(encoding="utf-8")
    respond = (WORKFLOWS_DIR / "respond-to-referees.md").read_text(encoding="utf-8")

    assert "researcher can recognize in the phase promise" in verify_work
    assert "Do not mark the parent claim or acceptance test as passed until that decisive comparison is resolved." in verify_work
    assert "Missing generic `verification_status` / `confidence` tags alone are not blockers." in write_paper
    assert "Only require the manuscript to surface decisive comparisons for claims it actually makes." in write_paper
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
