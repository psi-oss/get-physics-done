"""Regression tests for prompt/template wiring."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Literal

import pytest

from gpd import registry
from gpd.adapters.install_utils import expand_at_includes
from gpd.adapters.runtime_catalog import iter_runtime_descriptors
from gpd.contracts import ResearchContract, VerificationEvidence
from gpd.core.frontmatter import validate_frontmatter
from gpd.core.workflow_staging import validate_workflow_stage_manifest_payload
from gpd.registry import _parse_frontmatter, _parse_tools
from tests.core.test_spawn_contracts import _find_single_task
from tests.doc_surface_contracts import (
    assert_cost_surface_discoverability,
    assert_execution_observability_surface_contract,
    assert_help_command_all_extract_contract,
    assert_help_command_quick_start_extract_contract,
    assert_help_command_single_command_extract_contract,
    assert_help_workflow_quick_start_taxonomy_contract,
    assert_help_workflow_runtime_reference_contract,
    assert_recovery_ladder_contract,
    assert_resume_authority_contract,
    assert_runtime_reset_rediscovery_contract,
)


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
WORKFLOW_EXEMPT_COMMANDS = frozenset({"health", "suggest-next"})
PUBLICATION_SHARED_PREFLIGHT_INCLUDE = "@{GPD_INSTALL_DIR}/templates/paper/publication-manuscript-root-preflight.md"
PUBLICATION_BOOTSTRAP_PREFLIGHT_INCLUDE = (
    "@{GPD_INSTALL_DIR}/references/publication/publication-bootstrap-preflight.md"
)
PUBLICATION_RESPONSE_WRITER_HANDOFF_INCLUDE = (
    "@{GPD_INSTALL_DIR}/references/publication/publication-response-writer-handoff.md"
)
PUBLICATION_ROUND_ARTIFACTS_INCLUDE = (
    "@{GPD_INSTALL_DIR}/references/publication/publication-review-round-artifacts.md"
)
PUBLICATION_ROUND_ARTIFACTS_PATH = "{GPD_INSTALL_DIR}/references/publication/publication-review-round-artifacts.md"
PUBLICATION_REVIEW_RELIABILITY_INCLUDE = "@{GPD_INSTALL_DIR}/references/publication/peer-review-reliability.md"


def _assert_contains_fragments(text: str, *fragments: str) -> None:
    missing = [fragment for fragment in fragments if fragment not in text]
    assert not missing, "Missing expected prompt fragments:\n" + "\n".join(missing)


COMMAND_SPAWN_TOKENS = {
    "explain.md": ["gpd-explainer", "gpd-bibliographer"],
    "debug.md": ["gpd-debugger"],
    "plan-phase.md": ["gpd-planner"],
    "quick.md": ["gpd-planner", "gpd-executor"],
}

WORKFLOW_SPAWN_TOKENS = {
    "derive-equation.md": ["gpd-check-proof"],
    "explain.md": ["gpd-explainer", "gpd-bibliographer"],
    "plan-phase.md": ["gpd-phase-researcher", "gpd-planner", "gpd-plan-checker", "gpd-experiment-designer"],
    "execute-phase.md": [
        "gpd-executor",
        "gpd-check-proof",
        "gpd-debugger",
        "gpd-verifier",
        "gpd-consistency-checker",
        "gpd-notation-coordinator",
        "gpd-experiment-designer",
    ],
    "verify-work.md": ["gpd-check-proof", "gpd-verifier", "gpd-planner", "gpd-plan-checker"],
    "write-paper.md": ["gpd-paper-writer", "gpd-bibliographer", "gpd-referee"],
    "peer-review.md": [
        "gpd-review-reader",
        "gpd-review-literature",
        "gpd-review-math",
        "gpd-check-proof",
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
        "references/publication/bibliography-advanced-search.md",
        "templates/notation-glossary.md",
        "references/publication/bibtex-standards.md",
    ],
    "gpd-explainer.md": [
        "references/shared/shared-protocols.md",
        "references/orchestration/agent-infrastructure.md",
        "references/physics-subfields.md",
        "templates/notation-glossary.md",
    ],
    "gpd-debugger.md": [
        "Spawned by the debug orchestrator workflow.",
        "Agent surface: public writable production agent specialized for discrepancy investigation and bounded repair work.",
        "On demand only: shared protocols, verification core, physics subfields, agent infrastructure, and cross-project patterns.",
        "Keep work in `gpd-debugger` while the task is root-cause isolation, validation, or a bounded repair tied to that investigation.",
        "After root cause is confirmed, update `session_status` to \"diagnosed\".",
        "goal: find_root_cause_only",
        "goal: find_and_correct",
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
        "references/publication/paper-writer-cookbook.md",
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
    "gpd-check-proof.md": [
        "references/shared/shared-protocols.md",
        "references/orchestration/agent-infrastructure.md",
        "references/physics-subfields.md",
        "references/verification/core/verification-core.md",
        "templates/proof-redteam-schema.md",
        "references/verification/core/proof-redteam-protocol.md",
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
    ],
    "gpd-plan-checker.md": [
        "references/shared/shared-protocols.md",
        "references/orchestration/agent-infrastructure.md",
        "references/physics-subfields.md",
        "references/verification/core/verification-core.md",
        "templates/plan-contract-schema.md",
    ],
    "gpd-planner.md": [
        "references/shared/shared-protocols.md",
        "references/orchestration/agent-infrastructure.md",
        "references/physics-subfields.md",
        "references/verification/core/verification-core.md",
        "templates/planner-subagent-prompt.md",
        "templates/phase-prompt.md",
        "templates/parameter-table.md",
        "references/planning/planner-conventions.md",
        "references/protocols/hypothesis-driven-research.md",
    ],
    "gpd-project-researcher.md": [
        "references/shared/shared-protocols.md",
        "references/orchestration/agent-infrastructure.md",
    ],
    "gpd-referee.md": [
        "references/shared/shared-protocols.md",
        "references/orchestration/agent-infrastructure.md",
        "references/physics-subfields.md",
        "references/verification/core/verification-core.md",
        "references/publication/publication-pipeline-modes.md",
        "references/publication/referee-review-playbook.md",
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
    verifier_raw = (AGENTS_DIR / "gpd-verifier.md").read_text(encoding="utf-8")
    verifier = expand_at_includes(verifier_raw, REPO_ROOT / "src/gpd", "/runtime/")
    planner = (AGENTS_DIR / "gpd-planner.md").read_text(encoding="utf-8")

    assert "Agents must NEVER install dependencies silently." in shared
    assert "Ask the user before any install attempt" in shared
    assert "BasicTeX yourself (small macOS option, about 100MB)" in shared
    assert "Never install TeX automatically." not in checkpoints
    assert "install silently" not in checkpoints
    assert "## Data Boundary" not in verifier_raw
    assert "## GPD CLI Commit Protocol" not in verifier_raw
    assert "@{GPD_INSTALL_DIR}/references/orchestration/agent-infrastructure.md" not in verifier_raw
    assert "Ask the user before any install attempt; keep dependency changes permission-gated." in verifier_raw
    assert "ask the user before any install attempt" in verifier.lower()
    assert "permission-gated" in planner


def test_agent_infrastructure_requires_concrete_next_actions_and_continuation_block() -> None:
    infra = (REFERENCES_DIR / "orchestration" / "agent-infrastructure.md").read_text(encoding="utf-8")

    assert "Prefer copy-pasteable GPD commands" in infra
    assert "references/orchestration/continuation-format.md" in infra
    assert "## > Next Up" in infra


def test_paper_writer_uses_lightweight_path_mentions_for_metadata_only_reference_packs() -> None:
    writer_text = (AGENTS_DIR / "gpd-paper-writer.md").read_text(encoding="utf-8")

    for path in (
        "references/shared/shared-protocols.md",
        "references/orchestration/agent-infrastructure.md",
        "templates/notation-glossary.md",
        "templates/latex-preamble.md",
    ):
        lightweight = f"{{GPD_INSTALL_DIR}}/{path}"
        eager = f"@{{GPD_INSTALL_DIR}}/{path}"
        assert lightweight in writer_text
        assert eager not in writer_text


def test_bibliographer_uses_lightweight_path_mentions_for_metadata_only_reference_packs() -> None:
    bibliographer_text = (AGENTS_DIR / "gpd-bibliographer.md").read_text(encoding="utf-8")

    for path in (
        "references/shared/shared-protocols.md",
        "references/physics-subfields.md",
        "templates/notation-glossary.md",
        "references/orchestration/agent-infrastructure.md",
        "references/publication/bibtex-standards.md",
        "references/publication/publication-pipeline-modes.md",
        "references/publication/bibliography-advanced-search.md",
    ):
        lightweight = f"{{GPD_INSTALL_DIR}}/{path}"
        eager = f"@{{GPD_INSTALL_DIR}}/{path}"
        assert lightweight in bibliographer_text
        assert eager not in bibliographer_text


def test_continuation_format_scopes_clear_to_resolved_runtime_followups() -> None:
    continuation = (REFERENCES_DIR / "orchestration" / "continuation-format.md").read_text(encoding="utf-8")

    assert_runtime_reset_rediscovery_contract(continuation)
    assert "This format is a presentation layer only" in continuation
    assert "`/clear` first, then run `{next command}`" in continuation
    assert "If project rediscovery is still required" in continuation


def test_executor_completion_examples_use_command_based_next_actions() -> None:
    completion = (REFERENCES_DIR / "execution" / "executor-completion.md").read_text(encoding="utf-8")

    assert '"gpd:execute-phase {phase}"' in completion
    assert '"gpd:show-phase {phase}"' in completion
    assert "gpd state validate" in completion
    assert "gpd:sync-state" in completion
    assert "file_edit tool" not in completion


def test_referee_workflow_mentions_optional_pdf_compile_and_missing_tex_prompt() -> None:
    referee = (AGENTS_DIR / "gpd-referee.md").read_text(encoding="utf-8")
    peer_review = (WORKFLOWS_DIR / "peer-review.md").read_text(encoding="utf-8")

    assert "compile the latest referee-report `.tex` file to a matching `.pdf`" in referee
    assert "Do NOT install TeX yourself" in referee
    assert (
        "Continue now with `GPD/REFEREE-REPORT{round_suffix}.md` + `GPD/REFEREE-REPORT{round_suffix}.tex` only"
        in peer_review
    )
    assert "Authorize the agent to install TeX now" in peer_review


def test_executor_prompt_defaults_to_return_only_shared_state_updates() -> None:
    executor = (AGENTS_DIR / "gpd-executor.md").read_text(encoding="utf-8")
    executor_completion = (REFERENCES_DIR / "execution" / "executor-completion.md").read_text(encoding="utf-8")

    assert "return shared-state updates to the orchestrator instead of writing `STATE.md` directly" in executor
    assert (
        "Your job: Execute the research plan completely, checkpoint each step, create SUMMARY.md, update STATE.md."
        not in executor
    )
    assert "state_updates" in executor
    assert "contract_updates" in executor
    assert "decisions" in executor
    assert "blockers" in executor
    assert "continuation_update" in executor
    assert "state_updates:" in executor_completion
    assert "contract_updates:" in executor_completion
    assert "decisions:" in executor_completion
    assert "blockers:" in executor_completion
    assert "continuation_update:" in executor_completion


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


def test_consistency_checker_prompt_keeps_the_canonical_contract_and_stays_least_privileged() -> None:
    source = (AGENTS_DIR / "gpd-consistency-checker.md").read_text(encoding="utf-8")

    assert "one-shot handoff" in source
    assert "status: completed | checkpoint | blocked | failed" in source
    assert "files_written: [GPD/phases/{scope}/CONSISTENCY-CHECK.md]" in source
    assert "GPD/CONSISTENCY-CHECK.md" in source
    assert "@{GPD_INSTALL_DIR}" not in source
    assert "Do not act as the default writable implementation agent" in source
    assert "Do not claim ownership of code fixes, commits, convention-authoring, or pattern-library updates." in source
    assert "Create it from the template" not in source
    assert "gpd pattern add" not in source
    assert "Step 0.5" not in source
    assert "CONVENTIONS.md does not exist" not in source


def test_review_commands_expose_typed_contracts() -> None:
    write_paper = registry.get_command("gpd:write-paper")
    peer_review = registry.get_command("peer-review")
    arxiv_submission = registry.get_command("arxiv-submission")
    verify_work = registry.get_command("verify-work")
    respond_to_referees = registry.get_command("respond-to-referees")

    assert write_paper.review_contract is not None
    assert write_paper.review_contract.review_mode == "publication"
    assert "${PAPER_DIR}/ARTIFACT-MANIFEST.json" in write_paper.review_contract.required_outputs
    assert "${PAPER_DIR}/BIBLIOGRAPHY-AUDIT.json" in write_paper.review_contract.required_outputs
    assert "${PAPER_DIR}/reproducibility-manifest.json" in write_paper.review_contract.required_outputs
    assert "GPD/review/REVIEW-LEDGER{round_suffix}.json" in write_paper.review_contract.required_outputs
    assert "GPD/review/REFEREE-DECISION{round_suffix}.json" in write_paper.review_contract.required_outputs
    assert "GPD/REFEREE-REPORT{round_suffix}.md" in write_paper.review_contract.required_outputs
    assert "GPD/REFEREE-REPORT{round_suffix}.tex" in write_paper.review_contract.required_outputs
    assert write_paper.review_contract.required_evidence == []
    assert "command_context" in write_paper.review_contract.preflight_checks
    assert "verification_reports" in write_paper.review_contract.preflight_checks
    assert "manuscript" in write_paper.review_contract.preflight_checks
    assert "artifact_manifest" in write_paper.review_contract.preflight_checks
    assert "bibliography_audit" in write_paper.review_contract.preflight_checks
    assert "bibliography_audit_clean" in write_paper.review_contract.preflight_checks
    assert "reproducibility_manifest" in write_paper.review_contract.preflight_checks
    assert "reproducibility_ready" in write_paper.review_contract.preflight_checks
    assert "manuscript_proof_review" in write_paper.review_contract.preflight_checks
    assert write_paper.review_contract.stage_artifacts == []
    assert [
        {
            "when": requirement.when,
            "required_outputs": list(requirement.required_outputs),
        }
        for requirement in write_paper.review_contract.conditional_requirements
    ] == [
        {
            "when": "theorem-bearing claims are present",
            "required_outputs": ["GPD/review/PROOF-REDTEAM{round_suffix}.md"],
        }
    ]

    assert peer_review.review_contract is not None
    assert peer_review.review_contract.review_mode == "publication"
    assert "GPD/REFEREE-REPORT{round_suffix}.md" in peer_review.review_contract.required_outputs
    assert "GPD/REFEREE-REPORT{round_suffix}.tex" in peer_review.review_contract.required_outputs
    assert "GPD/review/CLAIMS{round_suffix}.json" in peer_review.review_contract.required_outputs
    assert "GPD/review/STAGE-interestingness{round_suffix}.json" in peer_review.review_contract.required_outputs
    assert "GPD/review/REFEREE-DECISION{round_suffix}.json" in peer_review.review_contract.required_outputs
    assert "command_context" in peer_review.review_contract.preflight_checks
    assert "verification_reports" in peer_review.review_contract.preflight_checks
    assert "manuscript" in peer_review.review_contract.preflight_checks
    assert "artifact_manifest" in peer_review.review_contract.preflight_checks
    assert "bibliography_audit" in peer_review.review_contract.preflight_checks
    assert "bibliography_audit_clean" in peer_review.review_contract.preflight_checks
    assert "reproducibility_manifest" in peer_review.review_contract.preflight_checks
    assert "reproducibility_ready" in peer_review.review_contract.preflight_checks
    assert "manuscript_proof_review" in peer_review.review_contract.preflight_checks
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
    assert [
        {
            "when": requirement.when,
            "required_outputs": list(requirement.required_outputs),
            "required_evidence": list(requirement.required_evidence),
            "blocking_conditions": list(requirement.blocking_conditions),
            "blocking_preflight_checks": list(requirement.blocking_preflight_checks),
            "stage_artifacts": list(requirement.stage_artifacts),
        }
        for requirement in peer_review.review_contract.conditional_requirements
    ] == [
        {
            "when": "theorem-bearing claims are present",
            "required_outputs": ["GPD/review/PROOF-REDTEAM{round_suffix}.md"],
            "required_evidence": [],
            "blocking_conditions": [],
            "blocking_preflight_checks": [],
            "stage_artifacts": ["GPD/review/PROOF-REDTEAM{round_suffix}.md"],
        }
    ]

    assert arxiv_submission.review_contract is not None
    assert arxiv_submission.review_contract.review_mode == "publication"
    assert "command_context" in arxiv_submission.review_contract.preflight_checks
    assert "artifact_manifest" in arxiv_submission.review_contract.preflight_checks
    assert "bibliography_audit" in arxiv_submission.review_contract.preflight_checks
    assert "bibliography_audit_clean" in arxiv_submission.review_contract.preflight_checks
    assert "publication_blockers" in arxiv_submission.review_contract.preflight_checks
    assert "manuscript_proof_review" in arxiv_submission.review_contract.preflight_checks
    assert [
        {
            "when": requirement.when,
            "required_outputs": list(requirement.required_outputs),
            "required_evidence": list(requirement.required_evidence),
            "blocking_conditions": list(requirement.blocking_conditions),
            "blocking_preflight_checks": list(requirement.blocking_preflight_checks),
            "stage_artifacts": list(requirement.stage_artifacts),
        }
        for requirement in arxiv_submission.review_contract.conditional_requirements
    ] == [
        {
            "when": "theorem-bearing manuscripts are present",
            "required_outputs": [],
            "required_evidence": ["cleared manuscript proof review for theorem-bearing manuscripts"],
            "blocking_conditions": ["missing or stale manuscript proof review for theorem-bearing manuscripts"],
            "blocking_preflight_checks": ["manuscript_proof_review"],
            "stage_artifacts": [],
        }
    ]

    assert verify_work.review_contract is not None
    assert verify_work.review_contract.required_state == "phase_executed"
    assert "command_context" in verify_work.review_contract.preflight_checks
    assert "phase_lookup" in verify_work.review_contract.preflight_checks
    assert "phase_artifacts" in verify_work.review_contract.preflight_checks
    assert "phase_summaries" in verify_work.review_contract.preflight_checks
    assert "phase_proof_review" in verify_work.review_contract.preflight_checks

    assert respond_to_referees.review_contract is not None
    assert "GPD/review/REFEREE_RESPONSE{round_suffix}.md" in respond_to_referees.review_contract.required_outputs
    assert "GPD/AUTHOR-RESPONSE{round_suffix}.md" in respond_to_referees.review_contract.required_outputs
    assert "command_context" in respond_to_referees.review_contract.preflight_checks
    assert respond_to_referees.review_contract.required_evidence == [
        "existing manuscript",
        "referee report source when provided as a path",
    ]
    assert "gpd:peer-review" in registry.list_review_commands()
    assert "gpd:write-paper" in registry.list_review_commands()
    assert "gpd:respond-to-referees" in registry.list_review_commands()
    assert "gpd:verify-work" in registry.list_review_commands()


def test_conditional_review_contract_requirements_do_not_hide_runtime_blockers() -> None:
    peer_review = registry.get_command("peer-review").review_contract
    arxiv_submission = registry.get_command("arxiv-submission").review_contract

    assert peer_review is not None
    assert arxiv_submission is not None
    for field_name in (
        "stage_ids",
        "final_decision_output",
        "requires_fresh_context_per_stage",
        "max_review_rounds",
    ):
        assert not hasattr(peer_review, field_name)
    assert peer_review.conditional_requirements == [
        registry.ReviewContractConditionalRequirement(
            when="theorem-bearing claims are present",
            required_outputs=["GPD/review/PROOF-REDTEAM{round_suffix}.md"],
            stage_artifacts=["GPD/review/PROOF-REDTEAM{round_suffix}.md"],
        )
    ]
    assert arxiv_submission.conditional_requirements == [
        registry.ReviewContractConditionalRequirement(
            when="theorem-bearing manuscripts are present",
            required_evidence=["cleared manuscript proof review for theorem-bearing manuscripts"],
            blocking_conditions=["missing or stale manuscript proof review for theorem-bearing manuscripts"],
            blocking_preflight_checks=["manuscript_proof_review"],
        )
    ]
    assert "manuscript_proof_review" in arxiv_submission.preflight_checks


def test_representative_commands_expose_expected_context_modes() -> None:
    assert registry.get_command("help").context_mode == "global"
    assert registry.get_command("health").context_mode == "projectless"
    assert registry.get_command("start").context_mode == "projectless"
    start_description = registry.get_command("start").description
    assert "first" in start_description.lower()
    assert "route into the real workflow" in start_description
    assert "without taking action" not in start_description
    assert registry.get_command("tour").context_mode == "projectless"
    tour_description = registry.get_command("tour").description
    assert "guided beginner walkthrough" in tour_description
    assert "core GPD commands" in tour_description
    assert "without taking action" in tour_description
    assert "route into the real workflow" not in tour_description
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
    assert "@{GPD_INSTALL_DIR}/references/publication/publication-review-wrapper-guidance.md" in command_text
    assert "Referee report source: $ARGUMENTS (file path or `paste`)." in command_text
    assert "Use the literal `paste` sentinel" in workflow_text
    assert "REVIEW-LEDGER*.json" in workflow_text
    assert "REFEREE-DECISION*.json" in workflow_text
    assert "GPD/review/REVIEW-LEDGER{round_suffix}.json" in writer_text
    assert "GPD/review/REFEREE-DECISION{round_suffix}.json" in writer_text


def test_review_workflows_keep_round_suffix_artifacts_visible_and_anchor_response_outputs() -> None:
    peer_review = (COMMANDS_DIR / "peer-review.md").read_text(encoding="utf-8")
    respond = (WORKFLOWS_DIR / "respond-to-referees.md").read_text(encoding="utf-8")
    write_paper = (WORKFLOWS_DIR / "write-paper.md").read_text(encoding="utf-8")
    write_paper_expanded = expand_at_includes(write_paper, REPO_ROOT / "src" / "gpd", "/runtime/")
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

    assert "resolved section file within the manuscript tree rooted at `${PAPER_DIR}`" in respond
    assert "${PAPER_DIR}/BIBLIOGRAPHY-AUDIT.json" in respond
    assert "${PAPER_DIR}/response-letter.tex" in respond
    assert "GPD/review/REFEREE_RESPONSE{round_suffix}.md" in respond
    assert "GPD/AUTHOR-RESPONSE{round_suffix}.md" in respond
    assert "templates/paper/author-response.md" in respond
    assert "needs-calculation" in respond

    assert PUBLICATION_ROUND_ARTIFACTS_INCLUDE in write_paper
    assert "REVIEW-LEDGER{round_suffix}.json" in write_paper_expanded
    assert "REFEREE-DECISION{round_suffix}.json" in write_paper_expanded
    assert "GPD/REFEREE-REPORT{round_suffix}.md" in write_paper_expanded
    assert "templates/paper/author-response.md" in write_paper
    assert "needs-calculation" in write_paper


def test_publication_commands_accept_documented_manuscript_layouts() -> None:
    write_paper = (COMMANDS_DIR / "write-paper.md").read_text(encoding="utf-8")
    peer_review = (COMMANDS_DIR / "peer-review.md").read_text(encoding="utf-8")
    respond = (COMMANDS_DIR / "respond-to-referees.md").read_text(encoding="utf-8")
    arxiv = (COMMANDS_DIR / "arxiv-submission.md").read_text(encoding="utf-8")

    for content in (peer_review, respond):
        assert (
            'files: ["paper/*.tex", "paper/*.md", "manuscript/*.tex", "manuscript/*.md", "draft/*.tex", "draft/*.md"]'
            in content
        )
    assert 'files: ["paper/*.tex", "manuscript/*.tex", "draft/*.tex"]' in arxiv

    assert "conditional_requirements:" in peer_review
    assert "when: theorem-bearing claims are present" in peer_review
    assert "GPD/review/PROOF-REDTEAM{round_suffix}.md" in peer_review
    assert "gpd-check-proof" in peer_review
    assert "conditional_requirements:" in arxiv
    assert "when: theorem-bearing manuscripts are present" in arxiv
    assert "cleared manuscript proof review for theorem-bearing manuscripts" in arxiv
    assert "latest peer-review review ledger" in arxiv
    assert "latest peer-review referee decision" in arxiv
    assert "missing latest staged peer-review decision evidence" in arxiv
    assert "The resolved manuscript root and its build artifacts satisfied the workflow gates" in arxiv
    assert "Keep the wrapper thin and let the workflow own validation, packaging, and submission-gate details." in arxiv
    assert 'find . -name "main.tex"' not in arxiv
    assert 'find . -name "*.tex"' not in write_paper
    assert "first-match" not in arxiv


def test_proof_contract_prompts_surface_explicit_theorem_fields_and_review_bindings() -> None:
    plan_schema = (TEMPLATES_DIR / "plan-contract-schema.md").read_text(encoding="utf-8")
    proof_schema = (TEMPLATES_DIR / "proof-redteam-schema.md").read_text(encoding="utf-8")
    proof_protocol = (
        REFERENCES_DIR / "verification" / "core" / "proof-redteam-protocol.md"
    ).read_text(encoding="utf-8")
    peer_review = (WORKFLOWS_DIR / "peer-review.md").read_text(encoding="utf-8")
    check_proof = (AGENTS_DIR / "gpd-check-proof.md").read_text(encoding="utf-8")

    assert "claim_kind" in plan_schema
    assert "parameters[]" in plan_schema
    assert "hypotheses[]" in plan_schema
    assert "quantifiers[]" in plan_schema
    assert "conclusion_clauses[]" in plan_schema
    assert "proof_deliverables[]" in plan_schema
    assert "proof_hypothesis_coverage" in plan_schema
    assert "proof_parameter_coverage" in plan_schema
    assert "proof_quantifier_domain" in plan_schema
    assert "claim_to_proof_alignment" in plan_schema
    assert "lemma_dependency_closure" in plan_schema
    assert "counterexample_search" in plan_schema
    assert "schema lacks dedicated theorem fields" not in plan_schema

    assert (
        "the `gpd-check-proof` task must carry the active `manuscript_path`, `manuscript_sha256`, `round`, theorem-bearing `claim_ids`, and `proof_artifact_paths`"
        in peer_review
    )
    assert "copy exactly from `GPD/review/CLAIMS{round_suffix}.json`" in peer_review
    assert "theorem-binding frontmatter (`claim_ids` and non-empty `proof_artifact_paths`)" in peer_review
    assert (
        "the Stage 3 math artifact must emit exactly one `proof_audits[]` entry for each reviewed theorem-bearing claim"
        in peer_review
    )
    assert "every `proof_audits[].claim_id` must also appear in `claims_reviewed`" in peer_review

    assert "{GPD_INSTALL_DIR}/templates/proof-redteam-schema.md" in check_proof
    assert "{GPD_INSTALL_DIR}/references/verification/core/proof-redteam-protocol.md" in check_proof
    assert "@{GPD_INSTALL_DIR}/references/publication/peer-review-panel.md" not in check_proof
    assert "proof_artifact_paths: [path, ...]" in proof_schema
    assert "manuscript_path" in proof_schema
    assert "manuscript_sha256" in proof_schema
    assert "round" in proof_schema
    assert "Treat each proof audit as a one-shot run." in proof_protocol
    assert "`peer-review` owns manuscript binding" in proof_protocol


def test_write_paper_and_arxiv_submission_keep_the_build_boundary_explicit() -> None:
    write_paper = (WORKFLOWS_DIR / "write-paper.md").read_text(encoding="utf-8")
    arxiv = (WORKFLOWS_DIR / "arxiv-submission.md").read_text(encoding="utf-8")

    assert 'gpd paper-build "${PAPER_DIR}/PAPER-CONFIG.json" --output-dir "${PAPER_DIR}"' in write_paper
    assert (
        "This emits `${PAPER_DIR}/{topic_specific_stem}.tex`, writes the manuscript-root artifact manifest"
        in write_paper
    )
    assert (
        "The workflow continues without local compilation smoke checks — .tex file generation does not require "
        "pdflatex, and `gpd paper-build` remains the canonical manuscript scaffold contract."
    ) in write_paper
    assert 'gpd paper-build "${PAPER_DIR}/PAPER-CONFIG.json" --output-dir "${PAPER_DIR}"' in arxiv
    assert "If `pdflatex` is available, run a local smoke check after the refreshed manuscript is in place." in arxiv
    assert "`pdflatex` is not available, report that the smoke check was skipped" in arxiv
    assert "Do not package stale audit artifacts." in arxiv


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
    assert (
        "Config: YOLO autonomy | Balanced research mode | Parallel | All agents | Review profile" not in workflow_text
    )


def test_settings_and_new_project_surface_runtime_permission_sync_for_yolo() -> None:
    new_project = (WORKFLOWS_DIR / "new-project.md").read_text(encoding="utf-8")
    settings = (WORKFLOWS_DIR / "settings.md").read_text(encoding="utf-8")

    assert 'gpd --raw permissions sync --autonomy "$SELECTED_AUTONOMY"' in new_project
    assert 'gpd --raw permissions sync --autonomy "$SELECTED_AUTONOMY"' in settings
    assert "sync the active runtime to its most autonomous permission mode when supported" in new_project
    assert "syncs the runtime to its most autonomous permission mode when supported" in settings
    assert (
        "This sync only updates runtime-owned permission settings; it does not create or validate the base install or workflow-tool readiness."
        in new_project
    )
    assert (
        "This sync only updates runtime-owned permission settings; it does not validate install health or workflow/tool readiness."
        in settings
    )
    assert "| Runtime Permissions  | {aligned / changed / manual follow-up required} |" in settings
    assert "If `requires_relaunch` is `true`, show `next_step` verbatim" in new_project


def test_new_project_requires_scoping_contract_across_setup_modes() -> None:
    workflow_text = (WORKFLOWS_DIR / "new-project.md").read_text(encoding="utf-8")
    command_text = (COMMANDS_DIR / "new-project.md").read_text(encoding="utf-8")

    _assert_contains_fragments(
        workflow_text,
        "scoping contract",
        "approval gate",
        "decisive outputs",
        "anchors",
        "prior outputs",
        "review/stop triggers",
        "contract-free",
        "scope.unresolved_questions",
        "context_intake.context_gaps",
        "uncertainty_markers.weakest_anchors",
    )
    _assert_contains_fragments(
        command_text,
        "scoping contract",
        "decisive outputs",
        "anchors",
        "one explicit scope approval",
        "scoping approval gate",
        "staged roadmap/conventions handoff",
    )


def _assert_parse_line_includes_tokens(parse_line: str, fields: tuple[str, ...]) -> None:
    for field in fields:
        assert f"`{field}`" in parse_line


def test_new_project_wiring_mentions_contract_persistence_and_contract_first_downstream_generation() -> None:
    workflow_text = (WORKFLOWS_DIR / "new-project.md").read_text(encoding="utf-8")
    command_text = (COMMANDS_DIR / "new-project.md").read_text(encoding="utf-8")
    parse_line = next(line for line in workflow_text.splitlines() if line.startswith("Parse JSON for:"))

    assert "gpd state set-project-contract" in workflow_text
    assert "gpd --raw validate project-contract - --mode approved" in workflow_text
    assert "gpd state set-project-contract -" in workflow_text
    assert "/tmp/gpd-project-contract.json" not in workflow_text
    assert "temporary JSON file if needed" not in workflow_text
    _assert_parse_line_includes_tokens(
        parse_line,
        (
            "researcher_model",
            "synthesizer_model",
            "commit_docs",
            "autonomy",
            "research_mode",
            "project_exists",
            "has_research_map",
            "planning_exists",
            "has_research_files",
            "has_project_manifest",
            "needs_research_map",
            "has_git",
            "project_contract",
            "project_contract_gate",
            "project_contract_load_info",
            "project_contract_validation",
        ),
    )
    assert "POST_SCOPE_INIT=$(gpd --raw init new-project --stage post_scope)" in workflow_text
    assert "roadmapper_model" in workflow_text
    _assert_contains_fragments(
        workflow_text,
        "project_contract_gate.authoritative",
        "approved scope",
        "contract coverage",
        "ROADMAP.md",
        "REQUIREMENTS.md",
    )
    _assert_contains_fragments(
        command_text,
        "scoping contract",
        "roadmap generation",
        "one explicit scope approval",
        "scoping approval gate",
    )


def test_new_project_defers_workflow_setup_until_after_scope_approval() -> None:
    workflow_text = (WORKFLOWS_DIR / "new-project.md").read_text(encoding="utf-8")
    command_text = (COMMANDS_DIR / "new-project.md").read_text(encoding="utf-8")

    _assert_contains_fragments(
        workflow_text,
        "GPD/config.json",
        "temporary defaults",
        "scope approval",
        "first project-artifact commit",
    )
    assert "## 2.5 Early Workflow Setup" not in workflow_text
    assert "What physics problem do you want to investigate?" in workflow_text
    _assert_contains_fragments(
        workflow_text,
        "If `GPD/config.json` does not exist yet",
        "scope approval",
        "before the first project-artifact commit",
    )
    assert "If Step 2.5 already captured provisional setup preferences" not in workflow_text
    assert "start with physics questioning" in command_text
    assert "surface a preset choice before workflow preferences" in command_text
    assert "before the first project-artifact commit" in command_text


def test_new_project_command_avoids_stale_workflow_line_counts() -> None:
    command_text = (COMMANDS_DIR / "new-project.md").read_text(encoding="utf-8")

    assert "Read {GPD_INSTALL_DIR}/workflows/new-project.md first and follow it exactly." in command_text
    assert "step-by-step instructions" not in command_text
    assert "lines)" not in command_text


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

    assert (
        "What exact smoking-gun observable, curve, benchmark reproduction, or scaling law they would trust before softer sanity checks"
        in workflow_text
    )
    assert (
        'Demand the smoking gun ("What exact check would make you trust this over softer sanity checks?")'
        in workflow_text
    )
    assert (
        "If you only have limiting cases, sanity checks, or generic benchmark language with no decisive smoking-gun observable, curve, or benchmark reproduction, keep exploring unless the user explicitly says that is the decisive standard."
        in workflow_text
    )
    assert (
        "especially the first smoking-gun check they would trust over softer proxies or limiting cases" in workflow_text
    )
    assert (
        "If the only checks captured so far are limiting cases, sanity checks, or qualitative expectations, treat the contract as still underspecified"
        in workflow_text
    )
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
    assert 'ROADMAP_INFO=$(gpd --raw roadmap get-phase "${PHASE}")' in discuss_text
    assert 'phase_slug=$(gpd slug "$phase_name")' in discuss_text
    assert "Continue to check_existing using the roadmap-derived phase metadata." in discuss_text
    assert 'REQUESTED_PHASE="${PHASE}"' in plan_text
    assert 'PHASE=$(echo "$INIT" | gpd json get .phase_number --default "${REQUESTED_PHASE}")' in plan_text
    assert 'PHASE_INFO=$(gpd --raw roadmap get-phase "${PHASE}")' in plan_text
    assert 'PHASE_SLUG=$(gpd slug "$PHASE_NAME")' in plan_text
    assert (
        "Use these resolved values for all later references to `PHASE_DIR`, `PHASE_SLUG`, and `PADDED_PHASE`."
        in plan_text
    )


def test_planning_and_phase_templates_surface_active_reference_context() -> None:
    planner_prompt = (TEMPLATES_DIR / "planner-subagent-prompt.md").read_text(encoding="utf-8")
    phase_prompt = (TEMPLATES_DIR / "phase-prompt.md").read_text(encoding="utf-8")
    workflow_text = (WORKFLOWS_DIR / "plan-phase.md").read_text(encoding="utf-8")

    assert "Planning requires an approved `project_contract`." in planner_prompt
    assert "**Project Contract:** {project_contract}" in planner_prompt
    assert "**Project Contract Gate:** {project_contract_gate}" in planner_prompt
    assert "**Project Contract Load Info:** {project_contract_load_info}" in planner_prompt
    assert "**Project Contract Validation:** {project_contract_validation}" in planner_prompt
    assert "**Active References:** {active_reference_context}" in planner_prompt
    assert "@path/to/reference-or-benchmark-anchor.md" in phase_prompt
    assert "Planning requires an approved scoping contract in `GPD/state.json`" in workflow_text
    assert "project_contract_gate" in workflow_text
    assert "project_contract_validation" in workflow_text
    assert "project_contract_load_info" in workflow_text
    assert (
        "Treat `project_contract` as authoritative only when `project_contract_gate.authoritative` is true."
        in workflow_text
    )
    assert "visible-but-blocked contract is not an approved planning contract" in workflow_text
    assert "**Project Contract:** {project_contract}" in workflow_text
    assert "**Active References:** {active_reference_context}" in workflow_text
    assert "**Anchor coverage:** Required references, baselines, and prior outputs are surfaced" in workflow_text


def test_progress_workflow_surfaces_contract_load_and_validation_state() -> None:
    workflow_text = (WORKFLOWS_DIR / "progress.md").read_text(encoding="utf-8")
    command_text = (COMMANDS_DIR / "progress.md").read_text(encoding="utf-8")

    assert "project_contract_validation" in workflow_text
    assert "project_contract_load_info" in workflow_text
    assert "knowledge_doc_count" in workflow_text
    assert "stable_knowledge_doc_count" in workflow_text
    assert "knowledge_doc_status_counts" in workflow_text
    assert "derived_knowledge_doc_count" in workflow_text
    assert "knowledge_doc_warnings" in workflow_text
    assert "authoritative only when `project_contract_gate.authoritative` is true" in workflow_text
    assert "structured load status, warnings, and blockers for the contract" in workflow_text
    status_scan = 'grep -l -E "^(status: (gaps_found|human_needed|expert_needed)|session_status: diagnosed)$"'
    assert status_scan in workflow_text
    assert status_scan not in command_text
    assert (
        "Read `{GPD_INSTALL_DIR}/workflows/progress.md` with the file-read tool and follow it exactly." in command_text
    )
    assert "INIT=$(gpd --raw init progress --include state,roadmap,project,config)" not in command_text
    assert 'CONTEXT=$(gpd --raw validate command-context progress "$ARGUMENTS")' not in command_text
    assert "status: (gaps_found|diagnosed|human_needed|expert_needed)" not in workflow_text
    assert "status: (gaps_found|diagnosed|human_needed|expert_needed)" not in command_text
    assert "`session_status: diagnosed`" in workflow_text
    assert "`session_status: diagnosed`" not in command_text
    assert "HEALTH.summary.warn > 0" in workflow_text
    assert "HEALTH.summary.fail > 0" in workflow_text
    assert "non-empty `issues` array" not in workflow_text
    assert "## Knowledge Status" in workflow_text
    assert "GPD/phases/[current-phase-dir]/*-VERIFICATION.md" in workflow_text
    assert "GPD/phases/[current-phase-dir]/*-VERIFICATION.md" not in command_text


def test_planning_prompts_keep_contract_gate_in_light_mode_and_all_modes() -> None:
    planner_prompt = (TEMPLATES_DIR / "planner-subagent-prompt.md").read_text(encoding="utf-8")
    planner_agent = (AGENTS_DIR / "gpd-planner.md").read_text(encoding="utf-8")
    checker_agent = (AGENTS_DIR / "gpd-plan-checker.md").read_text(encoding="utf-8")
    workflow_text = (WORKFLOWS_DIR / "plan-phase.md").read_text(encoding="utf-8")

    assert "@{GPD_INSTALL_DIR}/templates/plan-contract-schema.md" in planner_prompt
    assert (
        "Use `@{GPD_INSTALL_DIR}/templates/plan-contract-schema.md` as the canonical contract source." in planner_prompt
    )
    assert "Treat `approach_policy` as execution policy only." in planner_prompt
    assert "Light mode changes body verbosity only." in planner_prompt
    assert "Profiles may compress detail, but they do NOT relax contract completeness." in planner_agent
    assert (
        "All modes still require contract completeness, decisive outputs, required anchors, forbidden-proxy handling, and disconfirming paths before execution starts."
        in workflow_text
    )
    assert "gpd_return.status: completed" in planner_prompt
    assert "The markdown headings `## PLANNING COMPLETE`, `## CHECKPOINT REACHED`, and `## PLANNING INCONCLUSIVE` are human-readable labels only." in planner_prompt
    assert "gpd_return.status: completed" in workflow_text
    assert "Human-readable headings such as `## VERIFICATION PASSED`, `## ISSUES FOUND`, and `## PARTIAL APPROVAL` are presentation only." in workflow_text
    assert "Human review does not replace those requirements." in checker_agent


def test_stable_knowledge_remains_background_only_across_planning_verification_and_execution() -> None:
    planner_prompt = (TEMPLATES_DIR / "planner-subagent-prompt.md").read_text(encoding="utf-8")
    plan_phase = (WORKFLOWS_DIR / "plan-phase.md").read_text(encoding="utf-8")
    verify_workflow = (WORKFLOWS_DIR / "verify-work.md").read_text(encoding="utf-8")
    verify_phase = (WORKFLOWS_DIR / "verify-phase.md").read_text(encoding="utf-8")
    execute_plan = (WORKFLOWS_DIR / "execute-plan.md").read_text(encoding="utf-8")
    execute_phase = (WORKFLOWS_DIR / "execute-phase.md").read_text(encoding="utf-8")

    assert "Treat stable knowledge docs surfaced through `active_reference_context` and `reference_artifacts_content` as reviewed background syntheses." in planner_prompt
    assert (
        "Use explicit `knowledge_deps` when a plan materially depends on a reviewed knowledge doc and downstream gating should be enforced; keep implicit stable background advisory only."
        in planner_prompt
    )
    assert (
        "they do not override `convention_lock`, `project_contract`, the PLAN `contract`, `contract_results`, `comparison_verdicts`, proof-review artifacts, or direct benchmark/result evidence."
        in planner_prompt
    )
    assert "Stable knowledge docs may appear inside `{active_reference_context}` and `{reference_artifacts_content}`." in plan_phase
    assert (
        "If a plan materially depends on a reviewed knowledge doc and that reliance must be gateable downstream, express it with explicit `knowledge_deps`; keep implicit stable background advisory only."
        in plan_phase
    )
    assert (
        "they do not override `convention_lock`, `project_contract`, the PLAN `contract`, or direct evidence."
        in plan_phase
    )
    assert (
        "Stable knowledge docs that appear there are reviewed background synthesis: use them to clarify definitions, assumptions, and caveats only when they agree with stronger sources, and never as decisive evidence on their own."
        in verify_workflow
    )
    assert (
        "Stable knowledge docs that surface through this context are reviewed background synthesis only: they may guide check selection and interpretation, but they do not override the contract, the gate, or decisive evidence."
        in verify_phase
    )
    assert (
        "Stable knowledge docs may be present in that content as reviewed background, but they do not override the contract, conventions, or decisive evidence requirements."
        in execute_plan
    )
    assert (
        "Stable knowledge docs may appear only through those shared reference surfaces as reviewed background; they do not become a separate authority tier."
        in execute_phase
    )
    assert (
        "Treat any stable knowledge docs surfaced in those fields as reviewed background only: they may inform interpretation, but they do not override the contract, proof audits, or decisive evidence."
        in execute_phase
    )


def test_plan_checker_requires_contract_gate_and_reference_artifacts() -> None:
    checker_agent = (AGENTS_DIR / "gpd-plan-checker.md").read_text(encoding="utf-8")
    workflow_text = (WORKFLOWS_DIR / "plan-phase.md").read_text(encoding="utf-8")

    assert "## Dimension 0: Contract Gate" in checker_agent
    assert "{GPD_INSTALL_DIR}/templates/plan-contract-schema.md" in checker_agent
    assert "This is a one-shot handoff. If user input is needed, return `status: checkpoint`; do not wait inside the same run." in checker_agent
    assert "contract_decisive_output" in checker_agent
    assert "contract_anchor_coverage" in checker_agent
    assert "proxy_only_success_path" in checker_agent
    assert "**Project Contract Gate:** {project_contract_gate}" in workflow_text
    assert "**Project Contract Load Info:** {project_contract_load_info}" in workflow_text
    assert "**Project Contract Validation:** {project_contract_validation}" in workflow_text
    assert "**Contract Intake:** {contract_intake}" in workflow_text
    assert "**Effective Reference Intake:** {effective_reference_intake}" in workflow_text
    assert "**Reference Artifacts:** {reference_artifacts_content}" in workflow_text
    assert "**Decisive outputs:** The plan set covers decisive claims and deliverables" in workflow_text
    assert (
        "**Acceptance tests:** Every decisive claim or deliverable has at least one executable or reviewable test"
        in workflow_text
    )
    assert "**Forbidden proxies:** Proxy-only success conditions are rejected explicitly" in workflow_text


def test_roadmap_template_and_workflows_surface_phase_contract_coverage() -> None:
    roadmap_template = (TEMPLATES_DIR / "roadmap.md").read_text(encoding="utf-8")
    state_template = (TEMPLATES_DIR / "state.md").read_text(encoding="utf-8")
    roadmapper_agent = (AGENTS_DIR / "gpd-roadmapper.md").read_text(encoding="utf-8")
    new_project = (WORKFLOWS_DIR / "new-project.md").read_text(encoding="utf-8")
    new_milestone = (WORKFLOWS_DIR / "new-milestone.md").read_text(encoding="utf-8")
    new_project_roadmapper = _find_single_task(WORKFLOWS_DIR / "new-project.md", "gpd-roadmapper").text
    new_milestone_roadmapper = _find_single_task(WORKFLOWS_DIR / "new-milestone.md", "gpd-roadmapper").text

    assert "## Contract Overview" in roadmap_template
    assert "**Contract Coverage:**" in roadmap_template
    assert "Phase titles should be objective-driven, not template-driven" in roadmap_template
    assert "Standard physics research flow" not in roadmap_template
    assert "Literature Review" not in roadmap_template
    assert "Formalism Development" not in roadmap_template
    assert "Calculation / Simulation" not in roadmap_template
    assert "Validation & Cross-checks" not in roadmap_template
    assert "Paper Writing" not in roadmap_template
    assert "@{GPD_INSTALL_DIR}/templates/roadmap.md" in roadmapper_agent
    assert "@{GPD_INSTALL_DIR}/templates/state.md" in roadmapper_agent
    assert "## Step 3: Load Research Context (if exists)" in roadmapper_agent
    assert "Contract coverage" in roadmapper_agent
    assert "Machine-Readable Return Envelope" in roadmapper_agent
    assert "gpd_return:" in roadmapper_agent
    assert "status: completed | checkpoint | blocked | failed" in roadmapper_agent
    assert "files_written: [ROADMAP.md, STATE.md]" in roadmapper_agent
    assert "phases_created: {count}" in roadmapper_agent
    assert "gpd_return.files_written" in new_project_roadmapper
    assert "GPD/REQUIREMENTS.md" in new_project_roadmapper
    assert "do not rely on runtime completion text alone." in new_project_roadmapper
    assert "gpd_return.files_written" in new_milestone_roadmapper
    assert "treat existing files as stale unless the same paths appear in `gpd_return.files_written`" in (
        new_milestone_roadmapper
    )
    assert "Intermediate Results" in state_template
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


def test_research_prompt_surfaces_use_canonical_literature_outputs() -> None:
    project_researcher = (AGENTS_DIR / "gpd-project-researcher.md").read_text(encoding="utf-8")
    research_synthesizer = (AGENTS_DIR / "gpd-research-synthesizer.md").read_text(encoding="utf-8")
    phase_researcher = (AGENTS_DIR / "gpd-phase-researcher.md").read_text(encoding="utf-8")
    roadmapper_agent = (AGENTS_DIR / "gpd-roadmapper.md").read_text(encoding="utf-8")

    for content in (project_researcher, research_synthesizer, phase_researcher, roadmapper_agent):
        assert "GPD/research/" not in content

    assert "GPD/literature/" in project_researcher
    assert "GPD/literature/SUMMARY.md" in research_synthesizer
    assert "GPD/literature/SUMMARY.md" in phase_researcher
    assert "literature/SUMMARY.md" in roadmapper_agent


def test_new_project_minimal_mode_and_planning_wiring_allow_coarse_scoped_decomposition() -> None:
    workflow_text = (WORKFLOWS_DIR / "new-project.md").read_text(encoding="utf-8")
    planner_prompt = (TEMPLATES_DIR / "planner-subagent-prompt.md").read_text(encoding="utf-8")

    assert "whether the anchor is still unknown" in workflow_text
    assert "Do not force a phase list just to make the scoping contract look complete." in workflow_text
    assert (
        "If the user does not know the anchor yet, preserve that explicitly in `scope.unresolved_questions`, "
        "`context_intake.context_gaps`, or `uncertainty_markers.weakest_anchors` rather than inventing a paper, "
        "benchmark, or baseline." in workflow_text
    )
    assert "put it in `context_intake.must_include_prior_outputs`" in workflow_text
    assert (
        "`context_intake.crucial_inputs` for user-stated observables, stop conditions, review requests, or constraints"
        in workflow_text
    )
    assert "Missing-anchor notes preserve uncertainty, but they do not satisfy approval on their own." in workflow_text
    assert "A full phase breakdown is not required at this stage;" in workflow_text
    assert "Use the coarsest decomposition the approved contract actually supports." in workflow_text
    assert (
        "Do NOT invent literature, numerics, or paper phases unless the requirements or contract demand them."
        in workflow_text
    )
    assert "## CHECKPOINT REACHED" in planner_prompt
    assert "missing or no longer sufficient to identify the right phase slice" in planner_prompt


def test_reference_workflows_require_anchor_registry_propagation() -> None:
    literature_workflow = (WORKFLOWS_DIR / "literature-review.md").read_text(encoding="utf-8")
    literature_command = (COMMANDS_DIR / "literature-review.md").read_text(encoding="utf-8")
    literature_agent = (AGENTS_DIR / "gpd-literature-reviewer.md").read_text(encoding="utf-8")
    bibliographer_agent = (AGENTS_DIR / "gpd-bibliographer.md").read_text(encoding="utf-8")
    compare_workflow = (WORKFLOWS_DIR / "compare-results.md").read_text(encoding="utf-8")
    map_workflow = (WORKFLOWS_DIR / "map-research.md").read_text(encoding="utf-8")
    map_command = (COMMANDS_DIR / "map-research.md").read_text(encoding="utf-8")
    mapper_agent = (AGENTS_DIR / "gpd-research-mapper.md").read_text(encoding="utf-8")

    assert "contract-critical anchors" in literature_workflow
    assert "project_contract_load_info" in literature_workflow
    assert "project_contract_validation" in literature_workflow
    assert "authoritative only when `project_contract_gate.authoritative` is true" in literature_workflow
    assert "Do not frontload reference artifacts before the scope is fixed." in literature_workflow
    assert "Do not use `reference_artifact_files` or `reference_artifacts_content` yet." in literature_workflow
    assert "load_scoped_reference_artifacts" in literature_workflow
    assert "include `bibtex_key` only when it is already known and verified" in literature_workflow
    load_context_line = next(line for line in literature_workflow.splitlines() if "Parse JSON for:" in line)
    assert "reference_artifact_files" not in load_context_line
    assert "reference_artifacts_content" not in load_context_line
    assert "Follow `@{GPD_INSTALL_DIR}/workflows/literature-review.md` exactly." in literature_command
    assert "The workflow owns staged loading, scope fixing, artifact gating, and citation verification." in literature_command
    assert "Active Anchor Registry" not in literature_command
    assert "active_anchors" in literature_agent
    assert "GPD/literature/{slug}-CITATION-SOURCES.json" in literature_agent
    assert "compatible with the `CitationSource` shape" in literature_agent
    assert "gpd paper-build --citation-sources" in literature_agent
    assert "reference_id" in literature_agent
    assert "include `bibtex_key` as an optional preferred key" in literature_agent
    assert "Keep `bibtex_key` stable across reruns when present" in literature_agent
    assert "preferred `bibtex_key`, treat it as the manuscript bridge candidate" in bibliographer_agent
    assert (
        "For the full mode specification matrix, see `{GPD_INSTALL_DIR}/references/publication/publication-pipeline-modes.md`."
        in bibliographer_agent
    )
    assert "project_contract_load_info" in compare_workflow
    assert "project_contract_validation" in compare_workflow
    assert "active_reference_context" in compare_workflow
    assert (
        "Treat `project_contract` as authoritative only when `project_contract_gate.authoritative` is true."
        in compare_workflow
    )
    assert "active_reference_context" in map_workflow
    assert "effective_reference_intake" in map_workflow
    assert "project_contract_load_info" in map_workflow
    assert "project_contract_validation" in map_workflow
    assert "reference_artifacts_content" in map_workflow
    assert "authoritative only when `project_contract_gate.authoritative` is true" in map_workflow
    assert "Follow the workflow at `@{GPD_INSTALL_DIR}/workflows/map-research.md`." in map_command
    assert "project_contract_load_info" not in map_command
    assert "reference_artifacts_content" not in map_command
    assert "REFERENCES.md is an anchor registry" in mapper_agent


def test_file_producing_command_surfaces_use_canonical_spawn_contract() -> None:
    literature = (COMMANDS_DIR / "literature-review.md").read_text(encoding="utf-8")
    debug = (COMMANDS_DIR / "debug.md").read_text(encoding="utf-8")
    respond = (COMMANDS_DIR / "respond-to-referees.md").read_text(encoding="utf-8")

    for content, agent_name, file_token in (
        (debug, "gpd-debugger", "GPD/debug/{slug}.md"),
    ):
        assert f"read {{GPD_AGENTS_DIR}}/{agent_name}.md for your role and instructions" in content
        assert "readonly=false" in content
        assert f"{file_token}\nRead that file before continuing" in content
        assert f"@{file_token}" not in content
        assert "Fresh 200k context" not in content

    assert "gpd --raw validate command-context literature-review" in literature
    assert "Follow `@{GPD_INSTALL_DIR}/workflows/literature-review.md` exactly." in literature
    assert "First, read {GPD_AGENTS_DIR}/gpd-literature-reviewer.md for your role and instructions" not in literature
    assert "Write to: GPD/literature/{slug}-REVIEW.md" not in literature

    assert "Fresh 200k context" not in respond


def test_research_phase_command_delegates_file_path_and_return_routing_to_the_workflow() -> None:
    command = (COMMANDS_DIR / "research-phase.md").read_text(encoding="utf-8")
    workflow = (WORKFLOWS_DIR / "research-phase.md").read_text(encoding="utf-8")

    assert "Follow the workflow at `@{GPD_INSTALL_DIR}/workflows/research-phase.md`." in command
    assert "gpd --raw init phase-op --include state,config" not in command
    assert "Research depth follows the workflow-owned `research_mode`." in command
    assert "gpd_return.status: completed" not in command
    assert "gpd_return.files_written" not in command
    assert 'BOOTSTRAP_INIT=$(load_research_phase_stage phase_bootstrap "${PHASE}")' in workflow
    assert 'HANDOFF_INIT=$(load_research_phase_stage research_handoff "${phase_number}")' in workflow
    assert 'gpd --raw init research-phase "${phase_arg}" --stage "${stage_name}"' in workflow
    assert "Write to: {phase_dir}/{phase_number}-RESEARCH.md" in workflow
    assert "gpd_return.files_written" in workflow
    assert 'RESEARCH_MODE=$(echo "$BOOTSTRAP_INIT" | gpd json get .research_mode --default balanced)' in workflow


def test_revision_and_audit_workflows_verify_artifacts_before_trusting_success_text() -> None:
    respond = (WORKFLOWS_DIR / "respond-to-referees.md").read_text(encoding="utf-8")
    audit = (WORKFLOWS_DIR / "audit-milestone.md").read_text(encoding="utf-8")

    assert "templates/paper/author-response.md" in respond
    assert "needs-calculation" in respond
    assert "Use `**Evidence:**` blocks for rebuttals" in respond
    assert "verify the promised artifacts before trusting the handoff text" in respond
    assert "If the agent claimed success but the files did not change, treat that section as failed" in respond
    assert (
        "Re-open `GPD/AUTHOR-RESPONSE{round_suffix}.md` and `GPD/review/REFEREE_RESPONSE{round_suffix}.md`" in respond
    )

    assert "Verify the promised referee artifacts before trusting the handoff text" in audit
    assert "Confirm `GPD/v{milestone_version}-MILESTONE-REFEREE-REPORT.md` exists" in audit
    assert "If the agent reported success but either artifact is missing, treat peer review as failed" in audit


def test_audit_milestone_surfaces_contract_gate_and_milestone_review_namespace() -> None:
    audit = (WORKFLOWS_DIR / "audit-milestone.md").read_text(encoding="utf-8")

    assert "project_contract_load_info" in audit
    assert "project_contract_validation" in audit
    assert "active_reference_context" in audit
    assert "Treat `project_contract` as authoritative only when `project_contract_gate.authoritative` is true." in audit
    assert (
        "skip mock peer review and note that the contract gate must be repaired before milestone publishability review"
        in audit
    )
    assert "GPD/v{milestone_version}-MILESTONE-REFEREE-REPORT.md" in audit
    assert "GPD/v{milestone_version}-MILESTONE-REFEREE-REPORT.tex" in audit
    assert "Project contract load info: {project_contract_load_info}" in audit
    assert "Project contract validation: {project_contract_validation}" in audit
    assert "Active references: {active_reference_context}" in audit


def test_audit_milestone_uses_canonical_phase_helpers_instead_of_raw_glob_discovery() -> None:
    audit = (WORKFLOWS_DIR / "audit-milestone.md").read_text(encoding="utf-8")

    assert "gpd phase list" in audit
    assert "gpd show-phase <phase-number>" in audit
    assert "`find_files` `GPD/phases/*/*-VERIFICATION.md` by hand" in audit
    assert "cat GPD/phases/01-*/*-VERIFICATION.md" not in audit
    assert "cat GPD/phases/02-*/*-VERIFICATION.md" not in audit


def test_discover_command_does_not_emit_phase_only_commit_placeholders_for_standalone_mode() -> None:
    discover = (COMMANDS_DIR / "discover.md").read_text(encoding="utf-8")

    _assert_contains_fragments(
        discover,
        "Produces RESEARCH.md",
        "Do not commit `RESEARCH.md` separately.",
        "phase-only commit messages or file paths",
    )
    assert 'gpd commit "discover(${phase_number})' not in discover
    assert "GPD/phases/${padded_phase}-${phase_slug}/RESEARCH.md" not in discover
    assert "DISCOVERY.md" not in discover


def test_workflows_use_raw_json_when_shell_snippets_pipe_cli_output_into_gpd_json_get() -> None:
    research_workflow = (WORKFLOWS_DIR / "research-phase.md").read_text(encoding="utf-8")
    research_command = (COMMANDS_DIR / "research-phase.md").read_text(encoding="utf-8")
    map_workflow = (WORKFLOWS_DIR / "map-research.md").read_text(encoding="utf-8")
    map_command = (COMMANDS_DIR / "map-research.md").read_text(encoding="utf-8")
    progress_workflow = (WORKFLOWS_DIR / "progress.md").read_text(encoding="utf-8")
    progress_command = (COMMANDS_DIR / "progress.md").read_text(encoding="utf-8")
    gaps_workflow = (WORKFLOWS_DIR / "plan-milestone-gaps.md").read_text(encoding="utf-8")
    execute_workflow = (WORKFLOWS_DIR / "execute-phase.md").read_text(encoding="utf-8")
    milestone_workflow = (WORKFLOWS_DIR / "complete-milestone.md").read_text(encoding="utf-8")
    graph_workflow = (WORKFLOWS_DIR / "graph.md").read_text(encoding="utf-8")
    validate_conventions = (WORKFLOWS_DIR / "validate-conventions.md").read_text(encoding="utf-8")
    transition_workflow = (WORKFLOWS_DIR / "transition.md").read_text(encoding="utf-8")
    export_workflow = (WORKFLOWS_DIR / "export.md").read_text(encoding="utf-8")
    show_phase = (WORKFLOWS_DIR / "show-phase.md").read_text(encoding="utf-8")
    verify_phase = (WORKFLOWS_DIR / "verify-phase.md").read_text(encoding="utf-8")
    verify_work = (WORKFLOWS_DIR / "verify-work.md").read_text(encoding="utf-8")

    assert 'PHASE_INFO=$(gpd --raw roadmap get-phase "${phase_number}")' in research_workflow
    assert 'gpd --raw state snapshot | gpd json get .decisions --default "[]"' in research_workflow
    assert 'BOOTSTRAP_INIT=$(load_research_phase_stage phase_bootstrap "${PHASE}")' in research_workflow
    assert 'HANDOFF_INIT=$(load_research_phase_stage research_handoff "${phase_number}")' in research_workflow
    assert 'RESEARCH_MODE=$(echo "$BOOTSTRAP_INIT" | gpd json get .research_mode --default balanced)' in research_workflow
    assert 'gpd --raw config get research_mode' not in research_workflow
    assert 'gpd --raw init phase-op --include state,config "${PHASE}"' not in research_command
    assert 'BOOTSTRAP_INIT=$(load_map_research_stage map_bootstrap)' in map_workflow
    assert 'MAPPER_AUTHORING_INIT=$(load_map_research_stage mapper_authoring)' in map_workflow
    assert 'gpd --raw init map-research --stage "${stage_name}"' in map_workflow
    assert 'RESEARCH_MODE=$(echo "$BOOTSTRAP_INIT" | gpd json get .research_mode --default balanced)' in map_workflow
    assert 'gpd --raw config get research_mode' not in map_workflow
    assert 'gpd --raw init map-research' not in map_command
    assert "ROADMAP=$(gpd --raw roadmap analyze)" in progress_workflow
    assert "ROADMAP=$(gpd --raw roadmap analyze)" not in progress_command
    assert (
        "Read `{GPD_INSTALL_DIR}/workflows/progress.md` with the file-read tool and follow it exactly."
        in progress_command
    )
    assert (
        'gpd --raw summary-extract <path> --field one_liner | gpd json get .one_liner --default ""' in progress_workflow
    )
    assert "PHASES=$(gpd --raw phase list)" in gaps_workflow
    assert (
        'PHASE_GOAL=$(gpd --raw roadmap get-phase "${phase_number}" | gpd json get .goal --default "")'
        in execute_workflow
    )
    assert (
        'gpd --raw summary-extract "$summary" --field one_liner | gpd json get .one_liner --default ""'
        in execute_workflow
    )
    assert "ROADMAP=$(gpd --raw roadmap analyze)" in milestone_workflow
    assert (
        'gpd --raw summary-extract "$summary" --field one_liner | gpd json get .one_liner --default ""'
        in milestone_workflow
    )
    assert "ROADMAP=$(gpd --raw roadmap analyze)" in graph_workflow
    assert "ROADMAP=$(gpd --raw roadmap analyze)" in validate_conventions
    assert transition_workflow.count("ROADMAP=$(gpd --raw roadmap analyze)") == 2
    assert "ROADMAP=$(gpd --raw roadmap analyze)" in export_workflow
    assert 'PHASE_INFO=$(gpd --raw roadmap get-phase "${phase_number}")' in show_phase
    assert "ROADMAP=$(gpd --raw roadmap analyze)" in show_phase
    assert 'gpd --raw roadmap get-phase "${phase_number}"' in verify_phase
    assert 'gpd --raw roadmap get-phase "${phase_number}"' in verify_work


def test_workflow_and_command_docs_use_raw_output_for_machine_parsed_cli_json() -> None:
    offenders: list[str] = []
    shell_languages = {"bash", "sh", "shell", "zsh"}

    prompt_paths = [
        *sorted(WORKFLOWS_DIR.glob("*.md")),
        *sorted(COMMANDS_DIR.glob("*.md")),
        *sorted(AGENTS_DIR.glob("*.md")),
        *sorted(TEMPLATES_DIR.rglob("*.md")),
        *sorted(REFERENCES_DIR.rglob("*.md")),
    ]

    for path in prompt_paths:
        in_shell_fence = False
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            stripped = line.lstrip()
            if stripped.startswith("```"):
                if in_shell_fence:
                    in_shell_fence = False
                else:
                    in_shell_fence = stripped[3:].strip().lower() in shell_languages
                continue

            if not in_shell_fence:
                continue

            if re.search(r"\bgpd init\b", line) and "gpd --raw init" not in line:
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{line_number}: {line.strip()}")
            if re.search(r"\bgpd summary-extract\b", line) and "gpd --raw summary-extract" not in line:
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{line_number}: {line.strip()}")
            if re.search(r"\bgpd state compact\b", line) and "gpd --raw state compact" not in line:
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{line_number}: {line.strip()}")

    assert not offenders, "Found machine-parsed CLI snippets missing --raw:\n" + "\n".join(offenders)


def test_planner_subagent_prompt_uses_raw_init_placeholder_source() -> None:
    planner_subagent_prompt = (TEMPLATES_DIR / "planner-subagent-prompt.md").read_text(encoding="utf-8")

    assert "| `{phase_number}` | `gpd --raw init plan-phase` |" in planner_subagent_prompt


def test_research_phase_uses_resolved_phase_dir_for_artifact_paths_and_context_lookups() -> None:
    research_workflow = (WORKFLOWS_DIR / "research-phase.md").read_text(encoding="utf-8")
    research_command = (COMMANDS_DIR / "research-phase.md").read_text(encoding="utf-8")

    assert "Write to: {phase_dir}/{phase_number}-RESEARCH.md" in research_workflow
    assert "Follow the workflow at `@{GPD_INSTALL_DIR}/workflows/research-phase.md`." in research_command
    assert "Write to: {phase_dir}/{phase_number}-RESEARCH.md" not in research_command
    assert "Research file path: {phase_dir}/{phase_number}-RESEARCH.md" not in research_command
    assert "GPD/phases/${PHASE}-{slug}/${PHASE}-RESEARCH.md" not in research_workflow
    assert "GPD/phases/${PHASE}-{slug}/${PHASE}-RESEARCH.md" not in research_command


def test_audit_milestone_command_does_not_preload_raw_verification_globs() -> None:
    audit_command = (COMMANDS_DIR / "audit-milestone.md").read_text(encoding="utf-8")

    assert "find_files: GPD/phases/*/*SUMMARY.md" in audit_command
    assert "gpd phase list" in audit_command
    assert "gpd show-phase <phase-number>" in audit_command
    assert "find_files: GPD/phases/*/*-VERIFICATION.md" not in audit_command


def test_sensitivity_analysis_workflow_uses_canonical_cli_commands() -> None:
    workflow = (WORKFLOWS_DIR / "sensitivity-analysis.md").read_text(encoding="utf-8")

    assert "gpd --raw init progress --include state,config" in workflow
    assert "gpd --raw init phase-op" in workflow
    assert "gpd uncertainty add" in workflow
    assert "gpd commit" in workflow
    assert "gpd CLI init progress" not in workflow
    assert "gpd CLI init phase-op" not in workflow
    assert "gpd CLI uncertainty add" not in workflow
    assert "gpd CLI commit" not in workflow


def test_phase_research_and_verification_surfaces_keep_anchor_checks_mandatory() -> None:
    phase_researcher = (AGENTS_DIR / "gpd-phase-researcher.md").read_text(encoding="utf-8")
    planner_agent = (AGENTS_DIR / "gpd-planner.md").read_text(encoding="utf-8")
    verify_workflow = (WORKFLOWS_DIR / "verify-work.md").read_text(encoding="utf-8")
    verify_workflow_expanded = expand_at_includes(verify_workflow, REPO_ROOT / "src/gpd", "/runtime/")

    assert "## Active Anchor References" in phase_researcher
    assert "contract-critical anchors as mandatory inputs" in phase_researcher
    assert "FORMALISM.md" in planner_agent
    assert "| derivation, analytical, symbolic   | CONVENTIONS.md, FORMALISM.md    |" in planner_agent
    assert "| validation, testing, benchmarks    | VALIDATION.md, REFERENCES.md    |" in planner_agent
    assert "Do NOT skip contract-critical anchors" in verify_workflow
    assert "active_reference_context" in verify_workflow
    assert "project_contract_gate" in verify_workflow
    assert "project_contract_validation" in verify_workflow
    assert "project_contract_load_info" in verify_workflow
    assert (
        "visible-but-blocked contract must be repaired before it is used as authoritative verification scope"
        in verify_workflow
    )
    assert "suggest_contract_checks(contract)" in verify_workflow
    assert verify_workflow.count("**Project Contract Gate:** {project_contract_gate}") == 1
    assert verify_workflow_expanded.count("**Project Contract Gate:** {project_contract_gate}") >= 1
    assert (
        verify_workflow.count(
            "Treat `effective_reference_intake` as the structured source of carry-forward anchors; "
            "`active_reference_context` is the readable projection, not the source of truth."
        )
        == 2
    )


def test_phase_researcher_prompt_keeps_the_one_shot_handoff_and_return_contract_visible() -> None:
    phase_researcher = (AGENTS_DIR / "gpd-phase-researcher.md").read_text(encoding="utf-8")
    research_workflow = (WORKFLOWS_DIR / "research-phase.md").read_text(encoding="utf-8")
    research_command = (COMMANDS_DIR / "research-phase.md").read_text(encoding="utf-8")

    assert "## RESEARCH COMPLETE" in phase_researcher
    assert "## RESEARCH BLOCKED" in phase_researcher
    assert "gpd_return:" in phase_researcher
    assert "status: completed | checkpoint | blocked | failed" in phase_researcher
    assert "This is a one-shot handoff" in research_workflow
    assert "return a checkpoint rather than wait in place" in research_workflow
    assert "expected_artifacts" in research_workflow
    assert "Do not trust the runtime handoff status by itself." in research_workflow
    assert "gpd_return.files_written" in research_workflow
    assert "Follow the workflow at `@{GPD_INSTALL_DIR}/workflows/research-phase.md`." in research_command
    assert 'gpd --raw init research-phase "${phase_arg}" --stage "${stage_name}"' in research_workflow


def test_workflows_surface_structured_proof_review_statuses() -> None:
    verify_workflow = (WORKFLOWS_DIR / "verify-work.md").read_text(encoding="utf-8")
    verify_phase = (WORKFLOWS_DIR / "verify-phase.md").read_text(encoding="utf-8")
    write_paper = (WORKFLOWS_DIR / "write-paper.md").read_text(encoding="utf-8")
    peer_review = (WORKFLOWS_DIR / "peer-review.md").read_text(encoding="utf-8")
    respond_to_referees = (WORKFLOWS_DIR / "respond-to-referees.md").read_text(encoding="utf-8")
    arxiv_submission = (WORKFLOWS_DIR / "arxiv-submission.md").read_text(encoding="utf-8")

    assert "phase_proof_review_status" in verify_workflow
    assert "structured freshness summary for the phase proof-review manifest" in verify_workflow
    assert "derived_manuscript_proof_review_status" in verify_phase
    assert "manuscript-local proof-bearing artifact" in verify_phase
    assert "derived_manuscript_proof_review_status" in write_paper
    assert "proof-review freshness for theorem-bearing results" in write_paper
    assert "derived_manuscript_proof_review_status" in peer_review
    assert "theorem/proof freshness" in peer_review
    assert "derived_manuscript_proof_review_status" in respond_to_referees
    assert "proof-review freshness for theorem-bearing revisions" in respond_to_referees
    assert "derived_manuscript_proof_review_status" in arxiv_submission
    assert "theorem-proof freshness for the resolved manuscript" in arxiv_submission


def test_verify_phase_and_gap_reverify_prompts_surface_contract_context_before_contract_checks() -> None:
    verify_phase = (WORKFLOWS_DIR / "verify-phase.md").read_text(encoding="utf-8")
    execute_phase = (WORKFLOWS_DIR / "execute-phase.md").read_text(encoding="utf-8")

    assert "project_contract_gate" in verify_phase
    assert "contract_intake" in verify_phase
    assert "effective_reference_intake" in verify_phase
    assert "active_reference_context" in verify_phase
    assert "reference_artifacts_content" in verify_phase
    assert "protocol_bundle_context" in verify_phase
    assert verify_phase.index("project_contract_gate") < verify_phase.index("suggest_contract_checks(contract)")
    assert "{GPD_INSTALL_DIR}/workflows/verify-phase.md" in execute_phase
    assert "{GPD_INSTALL_DIR}/templates/verification-report.md" in execute_phase
    assert "{GPD_INSTALL_DIR}/templates/contract-results-schema.md" in execute_phase
    assert "gpd --raw init phase-op {PHASE_NUMBER}" in execute_phase
    assert "active_reference_context" in execute_phase
    assert "protocol_bundle_context" in execute_phase


def test_stage4_templates_and_workflows_surface_contract_results_and_verdict_ledgers() -> None:
    summary_template = (TEMPLATES_DIR / "summary.md").read_text(encoding="utf-8")

    assert "contract_results" in summary_template
    assert "comparison_verdicts" in summary_template
    assert "plan_contract_ref" in summary_template
    assert "subsystem (optional):" not in summary_template
    assert "tags (optional):" not in summary_template
    assert "plan_contract_ref (required" not in summary_template
    assert "contract_results (required" not in summary_template
    assert "comparison_verdicts (required" not in summary_template
    assert (
        "reload `@{GPD_INSTALL_DIR}/templates/contract-results-schema.md` immediately before writing"
        in summary_template
    )
    assert "uncertainty_markers" in summary_template


def test_validator_backed_examples_use_concrete_machine_readable_values() -> None:
    assert '"stage_id": "reader | literature | math | physics | interestingness"' not in (
        REFERENCES_DIR / "publication" / "peer-review-panel.md"
    ).read_text(encoding="utf-8")
    assert (
        '"claim_type": "main_result | novelty | significance | physical_interpretation | generality | method"'
        not in (REFERENCES_DIR / "publication" / "peer-review-panel.md").read_text(encoding="utf-8")
    )
    assert "claim_kind: theorem | lemma | corollary | proposition | result | claim | other" not in (
        TEMPLATES_DIR / "plan-contract-schema.md"
    ).read_text(encoding="utf-8")
    assert "status: passed|partial|failed|blocked|not_attempted" not in (
        TEMPLATES_DIR / "contract-results-schema.md"
    ).read_text(encoding="utf-8")
    assert "status: passed | gaps_found | expert_needed | human_needed" not in (
        TEMPLATES_DIR / "verification-report.md"
    ).read_text(encoding="utf-8")


def test_plan_tool_preflight_surfaces_across_planning_and_execution_prompts() -> None:
    phase_prompt = (TEMPLATES_DIR / "phase-prompt.md").read_text(encoding="utf-8")
    planner_agent = (AGENTS_DIR / "gpd-planner.md").read_text(encoding="utf-8")
    planner_prompt_template = (TEMPLATES_DIR / "planner-subagent-prompt.md").read_text(encoding="utf-8")
    plan_checker = (AGENTS_DIR / "gpd-plan-checker.md").read_text(encoding="utf-8")
    executor_agent = (AGENTS_DIR / "gpd-executor.md").read_text(encoding="utf-8")
    execute_plan = (WORKFLOWS_DIR / "execute-plan.md").read_text(encoding="utf-8")
    execute_phase = (WORKFLOWS_DIR / "execute-phase.md").read_text(encoding="utf-8")
    tooling_ref = (REFERENCES_DIR / "tooling" / "tool-integration.md").read_text(encoding="utf-8")
    summary_template = (TEMPLATES_DIR / "summary.md").read_text(encoding="utf-8")
    verification_template = (TEMPLATES_DIR / "verification-report.md").read_text(encoding="utf-8")
    research_verification = (TEMPLATES_DIR / "research-verification.md").read_text(encoding="utf-8")
    verify_workflow = (WORKFLOWS_DIR / "verify-work.md").read_text(encoding="utf-8")
    verify_phase = (WORKFLOWS_DIR / "verify-phase.md").read_text(encoding="utf-8")
    verifier_agent = (AGENTS_DIR / "gpd-verifier.md").read_text(encoding="utf-8")
    compare_workflow = (WORKFLOWS_DIR / "compare-experiment.md").read_text(encoding="utf-8")
    comparison_template = (TEMPLATES_DIR / "paper" / "experimental-comparison.md").read_text(encoding="utf-8")
    verify_phase = (WORKFLOWS_DIR / "verify-phase.md").read_text(encoding="utf-8")
    verifier_agent = (AGENTS_DIR / "gpd-verifier.md").read_text(encoding="utf-8")

    assert "# tool_requirements: # Optional machine-checkable specialized tools. Omit entirely if none." in phase_prompt
    assert '#     tool: "command"' in phase_prompt
    assert '#     command: "pdflatex --version"' in phase_prompt
    assert "`required` defaults to true when omitted" in phase_prompt
    assert "fallback does not make a missing required tool non-blocking" in phase_prompt
    assert "Quick contract rules:" in phase_prompt
    assert "# tool_requirements: # Machine-checkable specialized tools (omit entirely if none)" in planner_agent
    assert "tool: command" in planner_agent
    assert "Use only the closed tool vocabulary the validator accepts" in planner_agent
    assert "| `tool_requirements` | No       | Machine-checkable specialized tool requirements |" in planner_agent
    assert "declare them in `tool_requirements`" in plan_checker
    assert "Run `gpd validate plan-preflight <PLAN.md path>` from the local CLI." in executor_agent
    assert "A declared fallback does not override a blocking `required: true` requirement." in executor_agent
    assert 'PLAN_PREFLIGHT=$(gpd --raw validate plan-preflight "${PLAN_PATH}")' in execute_plan
    assert (
        "Use declared fallbacks automatically only for non-blocking preferred tools (`required: false`)" in execute_plan
    )
    assert "gpd validate plan-preflight <PLAN.md>" not in execute_plan
    assert "require that the selected `PLAN.md` passes `gpd validate plan-preflight <PLAN.md>`" in execute_phase
    assert (
        "`tool_requirements` pass `gpd validate plan-preflight <PLAN.md>` before the plan is treated as execution-ready"
        in planner_prompt_template
    )
    plan_phase_manifest = validate_workflow_stage_manifest_payload(
        json.loads((REPO_ROOT / "src/gpd/specs/workflows/plan-phase-stage-manifest.json").read_text(encoding="utf-8")),
        expected_workflow_id="plan-phase",
    )
    assert plan_phase_manifest.stage_ids() == (
        "phase_bootstrap",
        "research_routing",
        "planner_authoring",
        "checker_revision",
    )
    assert plan_phase_manifest.stages[0].loaded_authorities == ("workflows/plan-phase.md",)
    assert "templates/planner-subagent-prompt.md" in plan_phase_manifest.stages[2].loaded_authorities
    assert "templates/planner-subagent-prompt.md" in plan_phase_manifest.stages[3].loaded_authorities
    assert (
        "Treat `VERIFICATION.md` as contract-backed only through the schema-owned ledgers `plan_contract_ref`, `contract_results`, `comparison_verdicts`, and `suggested_contract_checks`; do not expect verifier-local aliases or ad hoc machine-readable artifact fields."
        in execute_phase
    )
    assert "declare it as `tool: wolfram` in `tool_requirements`" in tooling_ref
    for legacy_alias in ("must_haves", "verification_inputs", "contract_evidence", "independently_confirmed"):
        assert legacy_alias not in summary_template
    assert "`suggested_contract_checks` is verification-only and does not belong in summaries." in summary_template
    assert "contract_results" in verification_template
    assert "machine-readable surface limited to the schema-owned ledgers" in verification_template
    assert "verification-side `suggested_contract_checks`" in verification_template
    assert (
        "Use `@{GPD_INSTALL_DIR}/templates/verification-report.md` for the canonical verification frontmatter contract."
        in research_verification
    )
    assert "status: gaps_found" in research_verification
    assert "# Allowed status values: passed|gaps_found|expert_needed|human_needed" in research_verification
    assert "deliverable-main" in research_verification
    assert "acceptance-test-main" in research_verification
    assert "reference-main" in research_verification
    assert "## CHECKPOINT REACHED" not in verify_workflow
    assert verify_workflow.count("templates/planner-subagent-prompt.md") == 2
    assert verify_workflow.count("First, read {GPD_AGENTS_DIR}/gpd-planner.md for your role and instructions.") == 2
    for token in (
        "tool_requirements",
        "gap_closure",
    ):
        assert token in verify_workflow
    assert "The shared planner template owns the canonical planning policy and contract gate." not in verify_workflow
    assert "The shared planner template owns the canonical planning and revision policy." not in verify_workflow
    assert "forbidden-proxy-main" in research_verification
    assert "comparison_verdicts:" in research_verification
    assert "subject_role: decisive" in research_verification
    assert "comparison_kind: benchmark" in research_verification
    assert "Allowed body enum values:" in research_verification
    assert "`comparison_kind`: benchmark|prior_work|experiment|cross_method|baseline|other" in research_verification
    assert (
        "Allowed `comparison_kind` values: `benchmark|prior_work|experiment|cross_method|baseline|other`."
        in research_verification
    )
    assert (
        "comparison_kind: [benchmark | prior_work | experiment | cross_method | baseline | other]"
        not in research_verification
    )
    assert (
        'comparison_kind: [benchmark | prior_work | experiment | cross_method | baseline | other | ""]'
        not in research_verification
    )
    assert "suggested_contract_checks:" in research_verification
    assert "uncertainty_markers:" in research_verification
    assert "claim_id" in research_verification
    assert "acceptance_test_id" in research_verification
    assert "Load the staged researcher-session scaffold and canonical schema pack at this stage." in verify_workflow
    assert "Keep the session overlay frontmatter compatible with the authoritative verification report." in verify_workflow
    assert "status: gaps_found" not in verify_workflow
    assert "uncertainty_markers:" not in verify_workflow
    assert "Allowed body enum values:" not in verify_workflow
    assert "suggested_contract_checks:" not in verify_workflow
    assert "`suggested_contract_check`" not in verify_workflow
    assert "independently_confirmed" not in verify_workflow
    assert "Return status (`passed` | `gaps_found` | `expert_needed` | `human_needed`)" in verify_phase
    assert "contract_results including `uncertainty_markers`" in verify_phase
    assert "frontmatter (phase/verified/status/score/plan_contract_ref/contract_results" in verify_phase
    assert "frontmatter (phase/timestamp/status/score" not in verify_phase
    assert "independently_confirmed" not in verify_phase
    assert "`suggested_contract_check`" not in verify_phase
    assert "gap_subject_kind" in verifier_agent
    assert "Each gap has: `gap_subject_kind`" in verifier_agent
    assert "Each gap has: `subject_kind`" not in verifier_agent
    assert "Verification Status:** {passed | gaps_found | expert_needed | human_needed}" in verifier_agent
    assert "`suggested_contract_check`" not in verifier_agent
    assert "`contract_results` is authoritative." in execute_plan
    assert "project_contract_validation" in execute_plan
    assert "project_contract_load_info" in execute_plan
    assert "visible-but-blocked contract is still not an approved execution contract" in execute_plan
    assert (
        "Autonomy mode (`supervised` / `balanced` / `yolo`) and profile may change cadence or verbosity, but they do NOT relax contract-result emission."
        in execute_plan
    )
    assert (
        "comparison_verdicts` for decisive internal/external comparisons that were required or attempted"
        in execute_plan
    )
    assert "emit `verdict: inconclusive` or `verdict: tension` instead of omitting the entry" in execute_plan
    assert (
        "Immediately before writing frontmatter, re-open `@{GPD_INSTALL_DIR}/templates/contract-results-schema.md` and apply it literally."
        in execute_plan
    )
    assert "contract_results" in verify_phase
    assert "Verification targets must stay user-visible" in verify_phase
    assert "must_haves" not in verify_phase
    assert "request_template" in verify_phase
    assert "required_request_fields" in verify_phase
    assert "supported_binding_fields" in verify_phase
    assert "run_contract_check(request=..., project_dir=...)" in verify_phase
    assert "copy the returned `check_key` into the frontmatter `check` field" in verify_phase
    assert "comparison_verdicts" in compare_workflow
    assert "project_contract_load_info" in compare_workflow
    assert "project_contract_validation" in compare_workflow
    assert "authoritative only when `project_contract_gate.authoritative` is true" in compare_workflow
    assert "selected_protocol_bundle_ids" in compare_workflow
    assert "protocol_bundle_context" in compare_workflow
    assert "active_reference_context" in compare_workflow
    assert "protocol_bundle_ids (optional):" not in compare_workflow
    assert "bundle_expectations (optional):" not in compare_workflow
    assert "subject_kind: claim|deliverable|acceptance_test|reference" not in compare_workflow
    assert "comparison_kind: benchmark|prior_work|experiment|cross_method|baseline|other" not in compare_workflow
    assert "verdict: pass | tension | fail | inconclusive" not in compare_workflow
    assert "subject_kind: claim" in compare_workflow
    assert "subject_role: decisive" in compare_workflow
    assert "comparison_kind: experiment" in compare_workflow
    assert "schema_required_request_fields" in verify_phase
    assert "schema_required_request_anyof_fields" in verify_phase
    assert "project_dir" in verify_phase
    assert "schema_required_request_fields" in verifier_agent
    assert "schema_required_request_anyof_fields" in verifier_agent
    assert "project_dir" in verifier_agent
    assert "verdict: pass" in compare_workflow
    assert "omit `protocol_bundle_ids` and `bundle_expectations` entirely" in compare_workflow
    assert "protocol_bundle_ids (optional):" not in comparison_template
    assert "bundle_expectations (optional):" not in comparison_template
    assert "subject_kind: claim|deliverable|acceptance_test|reference" not in comparison_template
    assert "comparison_kind: benchmark|prior_work|experiment|cross_method|baseline|other" not in comparison_template
    assert "verdict: pass | tension | fail | inconclusive" not in comparison_template
    assert "subject_kind: claim" in comparison_template
    assert "subject_role: decisive" in comparison_template
    assert "comparison_kind: experiment" in comparison_template
    assert "verdict: pass" in comparison_template
    assert "omit `protocol_bundle_ids` and `bundle_expectations` entirely" in comparison_template
    assert "`comparison_verdicts` is a closed schema" in comparison_template
    internal_comparison_template = (TEMPLATES_DIR / "paper" / "internal-comparison.md").read_text(encoding="utf-8")
    assert "`comparison_verdicts` is a closed schema" in internal_comparison_template
    assert "protocol_bundle_ids (optional):" not in internal_comparison_template
    assert "bundle_expectations (optional):" not in internal_comparison_template
    assert "subject_kind: claim|deliverable|acceptance_test|reference" not in internal_comparison_template
    assert (
        "comparison_kind: benchmark|prior_work|experiment|cross_method|baseline|other"
        not in internal_comparison_template
    )
    assert "verdict: pass|tension|fail|inconclusive" not in internal_comparison_template
    assert "comparison_kind: cross_method" in internal_comparison_template
    assert "subject_kind: claim" in internal_comparison_template
    assert "subject_role: decisive" in internal_comparison_template
    assert "verdict: pass" in internal_comparison_template
    assert "omit `protocol_bundle_ids` and `bundle_expectations` entirely" in internal_comparison_template
    assert "subject_role" in comparison_template
    assert (
        "Profiles and autonomy modes may compress prose or cadence, but they do NOT relax contract-result emission"
        in executor_agent
    )
    assert (
        "Use claim IDs, deliverable IDs, acceptance test IDs, reference IDs, and forbidden proxy IDs directly from the `contract` block."
        in verifier_agent
    )


def test_execute_phase_workflow_surfaces_project_contract_validation_gate() -> None:
    execute_workflow = (WORKFLOWS_DIR / "execute-phase.md").read_text(encoding="utf-8")

    assert "project_contract_validation" in execute_workflow
    assert "project_contract_load_info" in execute_workflow
    assert "visible-but-blocked contract as an approved execution contract" in execute_workflow


def test_execute_phase_and_execute_plan_use_staged_execution_bootstrap_instead_of_monolithic_init() -> None:
    execute_workflow = (WORKFLOWS_DIR / "execute-phase.md").read_text(encoding="utf-8")
    execute_plan = (WORKFLOWS_DIR / "execute-plan.md").read_text(encoding="utf-8")

    assert "BOOTSTRAP_INIT=$(load_execute_phase_stage phase_bootstrap)" in execute_workflow
    assert "WAVE_PLANNING_INIT=$(load_execute_phase_stage wave_planning)" in execute_workflow
    assert "WAVE_DISPATCH_INIT=$(load_execute_phase_stage wave_dispatch)" in execute_workflow
    assert "gpd --raw init execute-phase \"${phase}\" --include state,config" not in execute_plan
    assert 'gpd --raw init execute-phase "${phase}" --stage phase_bootstrap' in execute_plan
    assert 'gpd --raw init execute-phase "${phase}" --stage phase_classification' in execute_plan
    assert 'gpd --raw init execute-phase "${phase}" --stage wave_planning' in execute_plan
    assert 'gpd --raw init execute-phase "${phase}" --stage aggregate_and_verify' in execute_plan


def test_execute_phase_and_execute_plan_surface_required_reference_and_state_ownership_guidance() -> None:
    execute_command = (COMMANDS_DIR / "execute-phase.md").read_text(encoding="utf-8")
    execute_workflow = (WORKFLOWS_DIR / "execute-phase.md").read_text(encoding="utf-8")
    execute_plan = (WORKFLOWS_DIR / "execute-plan.md").read_text(encoding="utf-8")

    assert "@{GPD_INSTALL_DIR}/references/orchestration/artifact-surfacing.md" in execute_workflow
    assert "{GPD_INSTALL_DIR}/references/execution/github-lifecycle.md" in execute_plan
    assert (
        "substitute the repository's actual default branch and remote names for `<default-branch>` and `<remote-name>`"
    ) in execute_plan
    assert "Shared-state updates land after each completed plan" in execute_command
    assert "STATE.md is updated after each wave completes" not in execute_command
    assert "By the time the wave-complete report is emitted" in execute_workflow
    assert "continuation_update" in execute_plan
    assert "session_update" not in execute_plan


def test_verification_prompts_keep_suggested_contract_check_bindings_schema_tight() -> None:
    verification_template = (TEMPLATES_DIR / "verification-report.md").read_text(encoding="utf-8")
    research_verification = (TEMPLATES_DIR / "research-verification.md").read_text(encoding="utf-8")
    verify_workflow = (WORKFLOWS_DIR / "verify-work.md").read_text(encoding="utf-8")
    verifier_agent = (AGENTS_DIR / "gpd-verifier.md").read_text(encoding="utf-8")

    assert 'suggested_subject_id: ""' not in verification_template
    assert 'suggested_subject_id: [contract id or ""]' not in research_verification
    assert 'suggested_subject_id: [contract id or ""]' not in verify_workflow
    assert "suggested_subject_id: acceptance-test-main" in research_verification
    assert "suggested_subject_id: reference-main" in research_verification
    assert "suggested_subject_id: acceptance-test-main" not in verify_workflow
    assert "suggested_subject_id: reference-main" not in verify_workflow
    assert "acceptance-test-main" in research_verification
    assert "acceptance-test-main" in verifier_agent
    assert "suggested_contract_checks" in verification_template
    assert (
        "Reload `@{GPD_INSTALL_DIR}/templates/contract-results-schema.md` immediately before writing"
        in verification_template
    )
    assert "proof-audit rules in the canonical schema" in verification_template
    assert "proof_artifact_path` matches a declared `proof_deliverables` path" in verifier_agent
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
    phase_prompt = _expand_prompt_surface(TEMPLATES_DIR / "phase-prompt.md")

    assert "context_intake:" in planner
    assert 'must_read_refs: ["ref-textbook"]' in planner
    assert 'references: ["ref-main"]' in phase_prompt
    assert "context_intake:" in plan_checker
    assert "why_it_matters:" in plan_checker
    assert "required_actions: [read, compare, cite]" in plan_checker
    assert 'procedure: "Compare the computed value against the benchmark anchor within tolerance."' in plan_checker
    assert "context_intake:" in parameter_sweep
    assert "must_read_refs: [ref-sweep-anchor]" in parameter_sweep
    assert "reference-main" in research_verification
    assert "acceptance-test-main" in research_verification
    assert "linked_ids: [deliverable-main, acceptance-test-main, reference-main]" in research_verification
    assert "evidence:\n        - verifier: gpd-verifier" in research_verification
    assert 'evidence_path: "GPD/phases/01-benchmark/01-VERIFICATION.md"' in research_verification
    assert "started:" in research_verification
    assert "updated:" in research_verification
    assert "test-benchmark" not in research_verification
    assert "reference-main" not in verify_work
    assert "acceptance-test-main" not in verify_work
    assert "test-benchmark" not in verify_work
    assert "reference-main" in verifier
    assert "acceptance-test-main" in verifier
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
            "  forbidden_proxies:\n    fp-benchmark:\n      status: rejected\n",
            "  forbidden_proxies:\n    fp-benchmark:\n      notes: Proxy scaffold left status unspecified.\n",
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
    artifact_manifest_schema = (TEMPLATES_DIR / "paper" / "artifact-manifest-schema.md").read_text(encoding="utf-8")
    bibliography_audit_schema = (TEMPLATES_DIR / "paper" / "bibliography-audit-schema.md").read_text(encoding="utf-8")
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
    assert (
        "Keep `manuscript_path` non-empty and identical across `GPD/review/REVIEW-LEDGER{round_suffix}.json`"
        in peer_review
    )
    assert "REPRODUCIBILITY-MANIFEST.json" not in peer_review
    assert "templates/paper/review-ledger-schema.md" in panel
    assert "templates/paper/referee-decision-schema.md" in panel
    assert "--ledger GPD/review/REVIEW-LEDGER{round_suffix}.json" in panel
    assert "templates/paper/paper-quality-input-schema.md" in scoring
    assert '"journal": "prl"' in paper_config_schema
    assert '"authors"' in paper_config_schema
    assert '"sections"' in paper_config_schema
    assert '"content": "State the problem, stakes, and contract-backed claim."' in paper_config_schema
    assert '"label": "intro"' in paper_config_schema
    assert '"label": "benchmark"' in paper_config_schema
    assert '"label": "derivation"' in paper_config_schema
    assert "`content` is the section body only" in paper_config_schema
    assert "`label` values are stored bare" in paper_config_schema
    assert "renderer adds the `sec:` / `fig:` prefix" in paper_config_schema
    assert "label: string such as `sec:intro`" not in paper_config_schema
    assert "label: LaTeX label such as `fig:benchmark`" not in paper_config_schema
    assert "XX-YY-SUMMARY.md" in contract_results_schema
    assert "XX-VERIFICATION.md" in contract_results_schema
    assert (
        "Must be the canonical project-root-relative `GPD/phases/XX-name/XX-YY-PLAN.md#/contract` path"
        in contract_results_schema
    )
    assert "`uncertainty_markers` must remain explicit in contract-backed outputs" in contract_results_schema
    assert "weakest_anchors: [anchor-1]" in contract_results_schema
    assert "disconfirming_observations: [observation-1]" in contract_results_schema
    assert "forbidden_proxy_id: fp-main" in contract_results_schema
    assert "closed action vocabulary: `read`, `use`, `compare`, `cite`, `avoid`" in contract_results_schema
    assert "forbidden_proxy_id" in summary_template
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
    assert (
        "Draft-only approximate output checksums still emit warnings and therefore block strict review."
        in reproducibility_template
    )
    assert (
        "Every stochastic `execution_steps[].name` must have a matching `random_seeds[].computation`"
        in reproducibility_template
    )
    assert "templates/paper/reproducibility-manifest.md" in reproducibility_protocol
    assert "templates/paper/paper-config-schema.md" in write_paper
    assert "templates/paper/artifact-manifest-schema.md" in write_paper
    assert "templates/paper/bibliography-audit-schema.md" in write_paper
    assert "templates/paper/figure-tracker.md" in write_paper
    assert "templates/paper/reproducibility-manifest.md" in write_paper
    assert 'gpd paper-build "${PAPER_DIR}/PAPER-CONFIG.json"' in paper_config_schema
    assert '"artifact_id": "tex-paper"' in artifact_manifest_schema
    assert '"category": "audit"' in artifact_manifest_schema
    assert "Do not write unsupported scoring-only journal labels" in artifact_manifest_schema
    assert '"resolution_status": "provided"' in bibliography_audit_schema
    assert '"verification_status": "partial"' in bibliography_audit_schema
    assert "Manual JSON is also the only supported path today for scoring-only profiles" in scoring
    assert "${PAPER_DIR}/reproducibility-manifest.json" in write_paper
    assert (
        'gpd --raw validate reproducibility-manifest "${PAPER_DIR}/reproducibility-manifest.json" --strict'
        in write_paper
    )
    assert "gpd validate summary-contract" in execute_plan
    assert "gpd validate verification-contract" in verify_work
    assert "gpd validate plan-contract" in plan_phase
    assert "Render the template's `## Standard Planning Template` into `filled_prompt`" in plan_phase
    assert "Render the template's `## Revision Template` into `revision_prompt`" in plan_phase
    assert "Do not restate template-owned contract gates" in plan_phase
    assert "{contract_intake}" in plan_phase
    assert "{effective_reference_intake}" in plan_phase
    assert "Contract Intake:" in verify_work
    assert "Effective Reference Intake:" in verify_work


def test_manuscript_documentation_uses_current_manuscript_root_paths_only() -> None:
    explain = (WORKFLOWS_DIR / "explain.md").read_text(encoding="utf-8")
    manuscript_outline = (TEMPLATES_DIR / "paper" / "manuscript-outline.md").read_text(encoding="utf-8")
    execute_phase = (WORKFLOWS_DIR / "execute-phase.md").read_text(encoding="utf-8")
    figure_tracker = (TEMPLATES_DIR / "paper" / "figure-tracker.md").read_text(encoding="utf-8")

    assert "GPD/paper/" not in explain
    assert "GPD/paper/" not in manuscript_outline
    assert "paper/EXPERIMENTAL_COMPARISON.md" in execute_phase
    assert "${PAPER_DIR}/EXPERIMENTAL_COMPARISON.md" not in execute_phase
    assert "GPD/paper/EXPERIMENTAL_COMPARISON.md" not in execute_phase
    assert "fig-main.pdf" not in figure_tracker


def test_publication_workflows_describe_recursive_manuscript_tree_inputs() -> None:
    arxiv_submission = (WORKFLOWS_DIR / "arxiv-submission.md").read_text(encoding="utf-8")
    write_paper = (WORKFLOWS_DIR / "write-paper.md").read_text(encoding="utf-8")
    respond = (WORKFLOWS_DIR / "respond-to-referees.md").read_text(encoding="utf-8")

    assert "Flatten all `\\input{}` and `\\include{}` chains into a single submission root file." in arxiv_submission
    assert "If the manuscript root is not already `paper/`, stage the package in a temporary submission tree" in arxiv_submission
    assert "Manuscript tree: all `.tex` files under `${PAPER_DIR}` recursively" in write_paper
    assert "Manuscript tree: all .tex files under ${PAPER_DIR} recursively" in write_paper
    assert "resolved section file within the manuscript tree rooted at `${PAPER_DIR}`" in respond


def test_review_and_verification_prompts_explicitly_surface_schema_sources_and_contract_context() -> None:
    peer_review = (WORKFLOWS_DIR / "peer-review.md").read_text(encoding="utf-8")
    peer_review_command = (COMMANDS_DIR / "peer-review.md").read_text(encoding="utf-8")
    verify_command = (COMMANDS_DIR / "verify-work.md").read_text(encoding="utf-8")
    verify_workflow = (WORKFLOWS_DIR / "verify-work.md").read_text(encoding="utf-8")
    write_paper = (WORKFLOWS_DIR / "write-paper.md").read_text(encoding="utf-8")
    write_paper_command = (COMMANDS_DIR / "write-paper.md").read_text(encoding="utf-8")
    respond_to_referees = (WORKFLOWS_DIR / "respond-to-referees.md").read_text(encoding="utf-8")
    sync_state = (WORKFLOWS_DIR / "sync-state.md").read_text(encoding="utf-8")
    review_reader = (AGENTS_DIR / "gpd-review-reader.md").read_text(encoding="utf-8")
    review_literature = (AGENTS_DIR / "gpd-review-literature.md").read_text(encoding="utf-8")
    review_math = (AGENTS_DIR / "gpd-review-math.md").read_text(encoding="utf-8")
    review_physics = (AGENTS_DIR / "gpd-review-physics.md").read_text(encoding="utf-8")
    review_significance = (AGENTS_DIR / "gpd-review-significance.md").read_text(encoding="utf-8")
    referee = (AGENTS_DIR / "gpd-referee.md").read_text(encoding="utf-8")
    verify_work_staging = registry.get_command("verify-work").staged_loading
    assert verify_work_staging is not None
    interactive_validation = next(stage for stage in verify_work_staging.stages if stage.id == "interactive_validation")
    inventory_build = next(stage for stage in verify_work_staging.stages if stage.id == "inventory_build")

    assert "Reader-visible claims and surfaced evidence remain first-class" in peer_review
    assert "effective_reference_intake" in peer_review
    assert "project_contract_validation" in peer_review
    assert "project_contract_load_info" in peer_review
    assert (
        "Carry-forward context: project contract {project_contract}; project contract gate {project_contract_gate}; project contract load info {project_contract_load_info}; project contract validation {project_contract_validation};"
        in peer_review
    )
    contract_gate_note = (
        "Treat `project_contract_gate` as authoritative. Use `project_contract` and `contract_intake` only when "
        "`project_contract_gate.authoritative` is true; otherwise keep them as diagnostics/context and rely on "
        "`effective_reference_intake`, `reference_artifacts_content`, and `active_reference_context` as carry-forward evidence."
    )
    assert contract_gate_note in peer_review
    assert "project_contract_gate.authoritative" in peer_review
    assert "project_contract_gate" in write_paper
    assert "project_contract_load_info" in write_paper
    assert "project_contract_validation" in write_paper
    assert "authoritative only when `project_contract_gate.authoritative` is true" in write_paper
    assert "project_contract_gate" in respond_to_referees
    assert "project_contract_load_info" in respond_to_referees
    assert "project_contract_validation" in respond_to_referees
    assert "authoritative only when `project_contract_gate.authoritative` is true" in respond_to_referees
    assert "templates/paper/review-ledger-schema.md" not in peer_review_command
    assert "templates/paper/referee-decision-schema.md" not in peer_review_command
    assert "references/publication/peer-review-panel.md" not in peer_review_command
    assert "templates/verification-report.md" not in verify_command
    assert "templates/contract-results-schema.md" not in verify_command
    assert "Follow the included workflow file exactly." in verify_command
    assert (
        "The workflow file owns the detailed check taxonomy; this wrapper only bootstraps the canonical "
        "verification surfaces and delegates the physics checks."
        in verify_command
    )
    assert "Severity Classification" not in verify_command
    assert "One check at a time, plain text responses, no interrogation." not in verify_command
    assert "Physics verification is not binary:" not in verify_command
    assert "For deeper focused analysis" not in verify_command
    assert "Load the staged researcher-session scaffold and canonical schema pack at this stage." in verify_workflow
    assert "Keep the session overlay frontmatter compatible with the authoritative verification report." in verify_workflow
    assert "templates/verification-report.md" in interactive_validation.loaded_authorities
    assert "templates/contract-results-schema.md" in interactive_validation.loaded_authorities
    assert "references/verification/meta/verification-independence.md" in inventory_build.loaded_authorities
    assert "templates/paper/review-ledger-schema.md" not in write_paper_command
    assert "templates/paper/referee-decision-schema.md" not in write_paper_command
    assert "references/publication/peer-review-panel.md" not in write_paper_command
    assert "Canonical schema for `${PAPER_DIR}/reproducibility-manifest.json`:" in write_paper
    assert "Canonical reconciliation contract:" in sync_state
    assert "state-json-schema.md` itself" in sync_state
    assert "state.json is authoritative for structured fields" in sync_state
    assert "This workflow is intentionally fail-closed" in sync_state
    assert "optional_commit" in sync_state
    assert "save_state_markdown" in sync_state
    assert "gpd --raw state snapshot" not in sync_state
    assert "Proceed with reconciliation? (y/n)" not in sync_state
    assert "determine which source is more recent" not in sync_state
    assert (
        "Keep the current `project_contract`, `project_contract_gate`, `project_contract_load_info`, `project_contract_validation`, "
        "and `active_reference_context` visible throughout the staged review" in write_paper
    )
    assert peer_review.count(contract_gate_note) >= 1
    assert "repair the blocked contract before retrying" in peer_review
    write_paper_staging = registry.get_command("write-paper").staged_loading
    peer_review_staging = registry.get_command("peer-review").staged_loading

    assert write_paper_staging is not None
    assert peer_review_staging is not None
    assert write_paper_staging.stage_ids() == (
        "paper_bootstrap",
        "outline_and_scaffold",
        "figure_and_section_authoring",
        "consistency_and_references",
        "publication_review",
    )
    assert peer_review_staging.stage_ids() == (
        "bootstrap",
        "preflight",
        "artifact_discovery",
        "panel_stages",
        "final_adjudication",
        "finalize",
    )

    write_paper_bootstrap = write_paper_staging.stage("paper_bootstrap")
    write_paper_outline = write_paper_staging.stage("outline_and_scaffold")
    write_paper_figures = write_paper_staging.stage("figure_and_section_authoring")
    write_paper_consistency = write_paper_staging.stage("consistency_and_references")
    write_paper_review = write_paper_staging.stage("publication_review")
    peer_review_bootstrap = peer_review_staging.stage("bootstrap")
    peer_review_preflight = peer_review_staging.stage("preflight")
    peer_review_artifacts = peer_review_staging.stage("artifact_discovery")
    peer_review_panel = peer_review_staging.stage("panel_stages")
    peer_review_final = peer_review_staging.stage("final_adjudication")
    peer_review_finalize = peer_review_staging.stage("finalize")

    assert "workflows/write-paper.md" in write_paper_bootstrap.loaded_authorities
    assert "references/publication/publication-pipeline-modes.md" in write_paper_outline.loaded_authorities
    assert "templates/paper/paper-config-schema.md" in write_paper_outline.loaded_authorities
    assert "templates/paper/artifact-manifest-schema.md" in write_paper_outline.loaded_authorities
    assert "templates/paper/figure-tracker.md" in write_paper_figures.loaded_authorities
    assert "templates/paper/bibliography-audit-schema.md" in write_paper_consistency.loaded_authorities
    assert "templates/paper/reproducibility-manifest.md" in write_paper_consistency.loaded_authorities
    assert "references/publication/peer-review-panel.md" in write_paper_review.loaded_authorities
    assert "references/publication/peer-review-reliability.md" in write_paper_review.loaded_authorities
    assert "references/publication/publication-review-round-artifacts.md" in write_paper_review.loaded_authorities
    assert "references/publication/publication-response-artifacts.md" in write_paper_review.loaded_authorities
    assert "templates/paper/review-ledger-schema.md" in write_paper_review.loaded_authorities
    assert "templates/paper/referee-decision-schema.md" in write_paper_review.loaded_authorities

    assert "workflows/peer-review.md" in peer_review_bootstrap.loaded_authorities
    assert "references/publication/peer-review-reliability.md" in peer_review_preflight.loaded_authorities
    assert "templates/paper/publication-manuscript-root-preflight.md" in peer_review_preflight.loaded_authorities
    assert "references/publication/publication-artifact-gates.md" not in peer_review_preflight.loaded_authorities
    assert "templates/paper/paper-config-schema.md" in peer_review_preflight.loaded_authorities
    assert "templates/paper/artifact-manifest-schema.md" in peer_review_preflight.loaded_authorities
    assert "templates/paper/bibliography-audit-schema.md" in peer_review_preflight.loaded_authorities
    assert "templates/paper/reproducibility-manifest.md" in peer_review_preflight.loaded_authorities
    assert peer_review_artifacts.loaded_authorities == (
        "workflows/peer-review.md",
        "references/publication/publication-review-round-artifacts.md",
        "references/publication/publication-response-artifacts.md",
    )
    assert "references/publication/peer-review-panel.md" in peer_review_panel.loaded_authorities
    assert "references/publication/peer-review-panel.md" in peer_review_final.loaded_authorities
    assert "templates/paper/review-ledger-schema.md" in peer_review_final.loaded_authorities
    assert "templates/paper/referee-decision-schema.md" in peer_review_final.loaded_authorities
    assert peer_review_finalize.loaded_authorities == ("workflows/peer-review.md",)
    assert "GPD/review/CLAIMS{round_suffix}.json" in review_reader
    assert "GPD/review/STAGE-reader{round_suffix}.json" in review_reader
    assert "shared source of truth for the full `ClaimIndex` and `StageReviewReport` contracts" in review_reader
    assert "Stage 1 must also emit `GPD/review/CLAIMS{round_suffix}.json`." in review_reader
    assert (
        "Capture theorem kind, explicit hypotheses, and free target parameters for theorem-like claims."
        in review_reader
    )
    assert "Keep `proof_audits` empty in this stage." in review_reader
    assert (
        "Focus `findings` on overclaiming, missing promised deliverables, and claim-structure blockers."
        in review_reader
    )
    assert "Required schema for" not in review_reader
    assert "closed schema; do not invent extra keys" not in review_reader
    assert "GPD/review/STAGE-literature{round_suffix}.json" in review_literature
    assert "GPD/review/STAGE-math{round_suffix}.json" in review_math
    assert "GPD/review/STAGE-physics{round_suffix}.json" in review_physics
    assert "GPD/review/STAGE-interestingness{round_suffix}.json" in review_significance
    assert "shared source of truth for the full `StageReviewReport` contract" in review_literature
    assert "shared source of truth for the full `StageReviewReport` contract" in review_math
    assert "shared source of truth for the full `StageReviewReport` contract" in review_physics
    assert "shared source of truth for the full `StageReviewReport` contract" in review_significance
    assert "Keep `proof_audits` empty in this stage." in review_literature
    assert (
        "Focus `findings` on claimed advance, directly relevant prior work, missing or misused citations, and novelty assessment."
        in review_literature
    )
    assert (
        "Escalate to `reject` when prior work already contains the main result or the novelty framing is materially false."
        in review_literature
    )
    assert "Escalate to `major_revision` when literature positioning needs substantial repair." in review_literature
    assert (
        "For every reviewed theorem-bearing Stage 1 claim, emit exactly one `proof_audits[]` entry whose `claim_id` is also present in `claims_reviewed`."
        in review_math
    )
    assert "Do not emit proof audits for unreviewed claims, and do not repeat `claim_id` values." in review_math
    assert (
        "The theorem-to-proof audit must record what the proof actually uses, what it silently specializes away, and any remaining coverage gaps."
        in review_math
    )
    assert (
        "Keep the focus on key equations, limits, cross-checks, approximation notes, and theorem-to-proof alignment."
        in review_math
    )
    assert (
        "`recommendation_ceiling` must drop to `major_revision` or `reject` for central theorem-proof gaps or missing audits."
        in review_math
    )
    assert (
        "Keep `proof_audits` empty in this stage unless the workflow explicitly asks for a theorem-to-proof spot check."
        in review_physics
    )
    assert (
        "Focus `findings` on stated physical assumptions, regime of validity, supported physical conclusions, and unsupported or overstated connections."
        in review_physics
    )
    assert "Treat formal resemblance as insufficient evidence for a physical conclusion." in review_physics
    assert (
        "Escalate `recommendation_ceiling` to `major_revision` or worse whenever central physical conclusions outrun the actual evidence."
        in review_physics
    )
    assert "Keep `proof_audits` empty in this stage." in review_significance
    assert (
        "Focus `findings` on why the result might matter, why it might not, venue fit, and claim proportionality."
        in review_significance
    )
    assert "Be explicit when the paper is technically competent but scientifically mediocre." in review_significance
    assert (
        "Escalate `recommendation_ceiling` to `reject` for PRL/Nature-style venues when significance or venue fit is weak."
        in review_significance
    )
    assert (
        "Escalate to at least `major_revision` when the paper is technically competent but physically uninteresting or overclaimed."
        in review_significance
    )
    for text in (review_reader, review_literature, review_math, review_physics, review_significance):
        assert "Required schema for" not in text
        assert "closed schema; do not invent extra keys" not in text
    assert "re-open `{GPD_INSTALL_DIR}/references/publication/peer-review-panel.md`" in referee


def test_peer_review_prompt_includes_concise_stage_map_for_users() -> None:
    peer_review_command = (COMMANDS_DIR / "peer-review.md").read_text(encoding="utf-8")
    peer_review_workflow = (WORKFLOWS_DIR / "peer-review.md").read_text(encoding="utf-8")

    assert (
        "When announcing the panel to the user, say what each stage does in one concise sentence" in peer_review_command
    )
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

    assert "The default manuscript family is limited to `paper/`, `manuscript/`, and `draft/`." in peer_review_command
    assert "then `PAPER-CONFIG.json`, then the canonical current manuscript entrypoint rules" in peer_review_command
    assert "Do not use ad hoc wildcard discovery." in peer_review_command
    assert "find paper manuscript draft" not in peer_review_command
    assert "find . -maxdepth 3" not in peer_review_command
    assert "pass an explicit manuscript path or paper directory" in peer_review_command


def test_peer_review_referee_surface_fail_closed_stage6_contract() -> None:
    referee = (AGENTS_DIR / "gpd-referee.md").read_text(encoding="utf-8")
    peer_review = (WORKFLOWS_DIR / "peer-review.md").read_text(encoding="utf-8")
    reliability = (REFERENCES_DIR / "publication" / "peer-review-reliability.md").read_text(encoding="utf-8")

    assert (
        "If any required staged-review artifact is missing, malformed, or uses the wrong round suffix, STOP"
        in peer_review
    )
    assert "before trusting any final recommendation" in peer_review
    assert "Treat blank `manuscript_path` values in either `GPD/review/REVIEW-LEDGER{round_suffix}.json`" in peer_review
    assert "Do not fall back to standalone review" in referee
    assert "fall back to direct standalone review" not in referee
    assert "passes `gpd validate referee-decision ... --strict --ledger ...`" in reliability
    assert "passes `gpd validate review-ledger ...`, including a non-empty `manuscript_path`" in reliability
    assert "A blank `manuscript_path` in the review ledger or referee decision is a contract failure" in reliability
    assert "bibliography_audit_clean" in reliability
    assert "reproducibility_ready" in reliability


def test_publication_prompts_surface_strict_semantic_manuscript_gates() -> None:
    arxiv = (COMMANDS_DIR / "arxiv-submission.md").read_text(encoding="utf-8")
    respond = (COMMANDS_DIR / "respond-to-referees.md").read_text(encoding="utf-8")
    peer_review_workflow = (WORKFLOWS_DIR / "peer-review.md").read_text(encoding="utf-8")
    write_paper_workflow = (WORKFLOWS_DIR / "write-paper.md").read_text(encoding="utf-8")
    respond_workflow = (WORKFLOWS_DIR / "respond-to-referees.md").read_text(encoding="utf-8")
    arxiv_workflow = (WORKFLOWS_DIR / "arxiv-submission.md").read_text(encoding="utf-8")
    respond_workflow_expanded = _expand_prompt_surface(WORKFLOWS_DIR / "respond-to-referees.md")
    arxiv_workflow_expanded = _expand_prompt_surface(WORKFLOWS_DIR / "arxiv-submission.md")
    shared_preflight = (TEMPLATES_DIR / "paper" / "publication-manuscript-root-preflight.md").read_text(
        encoding="utf-8"
    )

    assert PUBLICATION_SHARED_PREFLIGHT_INCLUDE in peer_review_workflow
    peer_review_staging = registry.get_command("peer-review").staged_loading

    assert peer_review_staging is not None
    assert "references/publication/publication-review-round-artifacts.md" in peer_review_staging.stage(
        "artifact_discovery"
    ).loaded_authorities
    assert PUBLICATION_BOOTSTRAP_PREFLIGHT_INCLUDE in write_paper_workflow
    assert PUBLICATION_RESPONSE_WRITER_HANDOFF_INCLUDE in write_paper_workflow
    assert PUBLICATION_ROUND_ARTIFACTS_INCLUDE in write_paper_workflow
    for content in (respond, arxiv):
        assert PUBLICATION_SHARED_PREFLIGHT_INCLUDE not in content
        assert PUBLICATION_BOOTSTRAP_PREFLIGHT_INCLUDE not in content
        assert PUBLICATION_RESPONSE_WRITER_HANDOFF_INCLUDE not in content
        assert PUBLICATION_ROUND_ARTIFACTS_INCLUDE not in content
        assert PUBLICATION_REVIEW_RELIABILITY_INCLUDE not in content
        assert "@{GPD_INSTALL_DIR}/references/shared/canonical-schema-discipline.md" not in content
        assert "templates/paper/review-ledger-schema.md" not in content
        assert "templates/paper/referee-decision-schema.md" not in content
    for content in (respond_workflow, arxiv_workflow):
        assert PUBLICATION_BOOTSTRAP_PREFLIGHT_INCLUDE in content
        if content is respond_workflow:
            assert PUBLICATION_RESPONSE_WRITER_HANDOFF_INCLUDE in content
            assert PUBLICATION_REVIEW_RELIABILITY_INCLUDE in content
            assert PUBLICATION_ROUND_ARTIFACTS_INCLUDE not in content
        else:
            assert PUBLICATION_RESPONSE_WRITER_HANDOFF_INCLUDE not in content
            assert PUBLICATION_ROUND_ARTIFACTS_INCLUDE in content
            assert PUBLICATION_REVIEW_RELIABILITY_INCLUDE in content
    for content in (respond_workflow_expanded, arxiv_workflow_expanded):
        assert "bibliography_audit_clean" in content
        assert "reproducibility_ready" in content
    assert (
        "For a resumed manuscript, strict preflight reads `ARTIFACT-MANIFEST.json`, `BIBLIOGRAPHY-AUDIT.json`, and "
        "`reproducibility-manifest.json` from the resolved manuscript directory itself. Use `ARTIFACT-MANIFEST.json` "
        "first and `PAPER-CONFIG.json` second when selecting the active manuscript entry point. Do not use ad hoc "
        "wildcard discovery or first-match filename scans."
        in shared_preflight
    )
    assert (
        "Resolve exactly one active manuscript root from the canonical manuscript family: `paper/`, `manuscript/`, or `draft/`."
        in shared_preflight
    )
    assert (
        "Keep all manuscript-local support artifacts rooted at the same explicit manuscript directory, and do not satisfy "
        "strict review or packaging with artifacts copied from another manuscript root."
        in shared_preflight
    )
    assert (
        "Treat `gpd paper-build` as the authoritative step that regenerates the resolved manuscript-root "
        "`ARTIFACT-MANIFEST.json` and `BIBLIOGRAPHY-AUDIT.json`."
        in shared_preflight
    )
    assert "Do not use ad hoc wildcard discovery or first-match filename scans." in shared_preflight
    assert "and do not satisfy strict review or packaging with artifacts copied from another manuscript root." in shared_preflight
    assert "bibliography_audit_clean" in shared_preflight
    assert "reproducibility_ready" in shared_preflight


def test_publication_command_contexts_surface_schema_docs_before_generation() -> None:
    write_paper = (COMMANDS_DIR / "write-paper.md").read_text(encoding="utf-8")
    peer_review = (COMMANDS_DIR / "peer-review.md").read_text(encoding="utf-8")
    arxiv = (COMMANDS_DIR / "arxiv-submission.md").read_text(encoding="utf-8")
    respond = (COMMANDS_DIR / "respond-to-referees.md").read_text(encoding="utf-8")
    write_paper_workflow = (WORKFLOWS_DIR / "write-paper.md").read_text(encoding="utf-8")
    peer_review_workflow = (WORKFLOWS_DIR / "peer-review.md").read_text(encoding="utf-8")
    respond_workflow = (WORKFLOWS_DIR / "respond-to-referees.md").read_text(encoding="utf-8")
    arxiv_workflow = (WORKFLOWS_DIR / "arxiv-submission.md").read_text(encoding="utf-8")
    write_paper_workflow_expanded = _expand_prompt_surface(WORKFLOWS_DIR / "write-paper.md")
    peer_review_workflow_expanded = _expand_prompt_surface(WORKFLOWS_DIR / "peer-review.md")
    respond_workflow_expanded = _expand_prompt_surface(WORKFLOWS_DIR / "respond-to-referees.md")
    arxiv_workflow_expanded = _expand_prompt_surface(WORKFLOWS_DIR / "arxiv-submission.md")
    shared_preflight_include = "@{GPD_INSTALL_DIR}/templates/paper/publication-manuscript-root-preflight.md"
    bootstrap_preflight_include = "@{GPD_INSTALL_DIR}/references/publication/publication-bootstrap-preflight.md"
    response_handoff_include = "@{GPD_INSTALL_DIR}/references/publication/publication-response-writer-handoff.md"
    round_artifacts_include = "@{GPD_INSTALL_DIR}/references/publication/publication-review-round-artifacts.md"
    write_paper_staging = registry.get_command("write-paper").staged_loading

    assert write_paper_staging is not None

    for content in (write_paper, peer_review, arxiv, respond):
        assert "templates/paper/paper-config-schema.md" not in content
        assert "templates/paper/artifact-manifest-schema.md" not in content
        assert "templates/paper/bibliography-audit-schema.md" not in content
        assert "templates/paper/reproducibility-manifest.md" not in content
        assert PUBLICATION_REVIEW_RELIABILITY_INCLUDE not in content
        assert shared_preflight_include not in content
        assert bootstrap_preflight_include not in content
        assert response_handoff_include not in content
        assert round_artifacts_include not in content
    for content in (write_paper, peer_review):
        assert "templates/paper/review-ledger-schema.md" not in content
        assert "templates/paper/referee-decision-schema.md" not in content
        assert "references/publication/peer-review-panel.md" not in content
        assert "references/publication/peer-review-reliability.md" not in content
    for content in (write_paper_workflow,):
        assert "templates/paper/paper-config-schema.md" in content
        assert "templates/paper/artifact-manifest-schema.md" in content
        assert "templates/paper/bibliography-audit-schema.md" in content
    assert "templates/paper/reproducibility-manifest.md" in write_paper_workflow
    assert bootstrap_preflight_include in write_paper_workflow
    assert response_handoff_include in write_paper_workflow
    assert round_artifacts_include in write_paper_workflow
    assert "bibliography_audit_clean" in write_paper_workflow_expanded
    assert "reproducibility_ready" in write_paper_workflow_expanded
    assert PUBLICATION_SHARED_PREFLIGHT_INCLUDE in peer_review_workflow
    assert "templates/paper/review-ledger-schema.md" in peer_review_workflow
    assert "templates/paper/referee-decision-schema.md" in peer_review_workflow
    assert "templates/paper/review-ledger-schema.md" in peer_review_workflow
    assert "templates/paper/referee-decision-schema.md" in peer_review_workflow
    peer_review_staging = registry.get_command("peer-review").staged_loading

    assert peer_review_staging is not None
    assert "references/publication/publication-review-round-artifacts.md" in peer_review_staging.stage(
        "artifact_discovery"
    ).loaded_authorities
    assert bootstrap_preflight_include not in peer_review_workflow
    assert response_handoff_include not in peer_review_workflow
    assert "bibliography_audit_clean" in peer_review_workflow_expanded
    assert "reproducibility_ready" in peer_review_workflow_expanded
    assert "templates/paper/author-response.md" in respond_workflow
    assert "templates/paper/referee-response.md" in respond_workflow
    assert bootstrap_preflight_include in respond_workflow
    assert response_handoff_include in respond_workflow
    assert PUBLICATION_REVIEW_RELIABILITY_INCLUDE in respond_workflow
    assert "bibliography_audit_clean" in respond_workflow_expanded
    assert "reproducibility_ready" in respond_workflow_expanded
    assert bootstrap_preflight_include in arxiv_workflow
    assert round_artifacts_include in arxiv_workflow
    assert response_handoff_include not in arxiv_workflow
    assert PUBLICATION_REVIEW_RELIABILITY_INCLUDE in arxiv_workflow
    assert "bibliography_audit_clean" in arxiv_workflow_expanded
    assert "reproducibility_ready" in arxiv_workflow_expanded
    assert (
        "references/shared/canonical-schema-discipline.md"
        in write_paper_staging.stage("figure_and_section_authoring").loaded_authorities
    )
    for content in (respond, arxiv):
        assert shared_preflight_include not in content
        assert bootstrap_preflight_include not in content
        assert response_handoff_include not in content
        assert round_artifacts_include not in content
        assert PUBLICATION_REVIEW_RELIABILITY_INCLUDE not in content


def test_research_verification_body_scaffold_keeps_body_only_subject_labels_distinct() -> None:
    research_verification = (TEMPLATES_DIR / "research-verification.md").read_text(encoding="utf-8")

    assert "Allowed body enum values:" in research_verification
    assert "check_subject_kind: claim" in research_verification
    assert "check_subject_kind: claim" in research_verification
    assert "suggested_subject_kind" in research_verification
    assert 'gap_subject_kind: "claim"' in research_verification
    assert "Use `check_subject_kind` for body-only verification checkpoints" in research_verification
    assert "Use `gap_subject_kind` for the body scaffold" in research_verification
    assert (
        "Keep `check_subject_kind` and `gap_subject_kind` aligned with the canonical frontmatter-safe subject vocabulary"
        in research_verification
    )
    assert "use `forbidden_proxy_id` for explicit proxy-rejection gaps" in research_verification
    assert (
        "\nsubject_kind: [claim | deliverable | acceptance_test | reference | forbidden_proxy | suggested_contract_check]"
        not in research_verification
    )
    assert (
        "# Allowed check_subject_kind values: claim|deliverable|acceptance_test|reference" not in research_verification
    )
    assert "check_subject_kind: [claim | deliverable | acceptance_test | reference]" not in research_verification
    assert (
        "check_subject_kind: [claim | deliverable | acceptance_test | reference | forbidden_proxy | suggested_contract_check]"
        not in research_verification
    )
    assert 'gap_subject_kind: "claim | deliverable | acceptance_test | reference"' not in research_verification
    assert (
        'gap_subject_kind: "claim | deliverable | acceptance_test | reference | forbidden_proxy | suggested_contract_check"'
        not in research_verification
    )


def test_verify_work_workflow_uses_body_only_subject_kind_fields() -> None:
    verify_work = (WORKFLOWS_DIR / "verify-work.md").read_text(encoding="utf-8")

    assert "Load the staged researcher-session scaffold and canonical schema pack at this stage." in verify_work
    assert "Keep body-only session-overlay fields aligned with the staged researcher-session scaffold." in verify_work
    assert "check_subject_kind: `claim|deliverable|acceptance_test|reference`" not in verify_work
    assert "Allowed body enum values:" not in verify_work
    assert "check_subject_kind: claim" not in verify_work
    assert "`check_subject_kind`: claim|deliverable|acceptance_test|reference" not in verify_work
    assert 'gap_subject_kind: "claim"' not in verify_work
    assert "Use `forbidden_proxy_id` for explicit proxy-rejection checks" in verify_work
    assert "instead of inventing extra body subject kinds" in verify_work
    assert "# Allowed check_subject_kind values: claim|deliverable|acceptance_test|reference" not in verify_work
    assert "check_subject_kind: [claim | deliverable | acceptance_test | reference]" not in verify_work
    assert "{phase}" not in verify_work
    assert "GPD/phases/{phase_dir}" not in verify_work
    assert "Write to `${phase_dir}/${phase_number}-VERIFICATION.md`" in verify_work
    assert (
        "Changed verification files fail `gpd pre-commit-check` when this header is missing or mismatched against the active lock."
        in verify_work
    )
    assert 'gpd validate verification-contract "${phase_dir}/${phase_number}-VERIFICATION.md"' in verify_work
    assert (
        'gpd commit "verify(${phase_number}): complete research validation - {passed} passed, {issues} issues" --files "${phase_dir}/${phase_number}-VERIFICATION.md"'
        in verify_work
    )
    assert "Read all PLAN.md files in ${phase_dir}/ using the file_read tool." in verify_work
    assert (
        "\nsubject_kind: [claim | deliverable | acceptance_test | reference | forbidden_proxy | suggested_contract_check]"
        not in verify_work
    )
    assert (
        "check_subject_kind: `claim | deliverable | acceptance_test | reference | forbidden_proxy | suggested_contract_check`"
        not in verify_work
    )
    assert (
        "check_subject_kind: [claim | deliverable | acceptance_test | reference | forbidden_proxy | suggested_contract_check]"
        not in verify_work
    )


def test_verify_work_active_sessions_use_canonical_verification_path_and_keep_status_separate() -> None:
    verify_work = (WORKFLOWS_DIR / "verify-work.md").read_text(encoding="utf-8")

    assert "gpd frontmatter get \"$file\" --field session_status" in verify_work
    assert "Only treat files whose frontmatter `session_status` is `validating` or `diagnosed` as active researcher sessions." in verify_work
    assert (
        "extract canonical verification `status`, `session_status`, `phase`, and the Current Check section"
        in verify_work
    )
    assert "`session_status` replace or overwrite the canonical verification `status`" in verify_work
    assert "`session_status` if present, otherwise `status`" not in verify_work


def test_skill_surface_exposes_contract_references_for_paper_and_review_workflows() -> None:
    from gpd.mcp.servers.skills_server import get_skill

    write_paper = get_skill("gpd-write-paper")
    peer_review = get_skill("gpd-peer-review")
    arxiv_submission = get_skill("gpd-arxiv-submission")
    respond_to_referees = get_skill("gpd-respond-to-referees")
    write_paper_schema_documents = {Path(entry["path"]).name: entry for entry in write_paper["schema_documents"]}
    peer_review_contract_documents = {Path(entry["path"]).name: entry for entry in peer_review["contract_documents"]}
    arxiv_contract_documents = {Path(entry["path"]).name: entry for entry in arxiv_submission["contract_documents"]}
    respond_contract_documents = {
        Path(entry["path"]).name: entry for entry in respond_to_referees["contract_documents"]
    }
    write_paper_stage_authorities = {
        authority
        for stage in write_paper.get("staged_loading", {}).get("stages", [])
        for authority in stage.get("loaded_authorities", [])
    }
    peer_review_stage_authorities = {
        authority
        for stage in peer_review.get("staged_loading", {}).get("stages", [])
        for authority in stage.get("loaded_authorities", [])
    }

    assert "error" not in write_paper
    assert "error" not in peer_review
    assert "error" not in arxiv_submission
    assert "error" not in respond_to_referees
    assert any(path.endswith("paper-config-schema.md") for path in write_paper["schema_references"])
    assert any(path.endswith("artifact-manifest-schema.md") for path in write_paper_stage_authorities)
    assert any(path.endswith("bibliography-audit-schema.md") for path in write_paper_stage_authorities)
    assert any(path.endswith("review-ledger-schema.md") for path in write_paper_stage_authorities)
    assert any(path.endswith("referee-decision-schema.md") for path in write_paper_stage_authorities)
    assert any(path.endswith("publication-review-round-artifacts.md") for path in write_paper_stage_authorities)
    assert any(path.endswith("publication-response-artifacts.md") for path in write_paper_stage_authorities)
    assert any(path.endswith("review-ledger-schema.md") for path in peer_review_stage_authorities)
    assert any(path.endswith("referee-decision-schema.md") for path in peer_review_stage_authorities)
    assert any(path.endswith("publication-review-round-artifacts.md") for path in peer_review_stage_authorities)
    arxiv_stage_authorities = {
        authority
        for stage in arxiv_submission.get("staged_loading", {}).get("stages", [])
        for authority in stage.get("loaded_authorities", [])
    }
    assert any(path.endswith("publication-bootstrap-preflight.md") for path in arxiv_stage_authorities)
    assert any(path.endswith("publication-review-round-artifacts.md") for path in arxiv_stage_authorities)
    assert any(path.endswith("author-response.md") for path in respond_to_referees["schema_references"])
    assert any(path.endswith("reproducibility-manifest.md") for path in write_paper_stage_authorities)
    assert any(path.endswith("peer-review-panel.md") for path in write_paper_stage_authorities)
    assert any(path.endswith("peer-review-panel.md") for path in peer_review["contract_references"])
    assert any(path.endswith("peer-review-reliability.md") for path in peer_review["contract_references"])
    assert "Paper Config Schema" in write_paper_schema_documents["paper-config-schema.md"]["body"]
    assert "Reproducibility Manifest Template" in write_paper_schema_documents["reproducibility-manifest.md"]["body"]
    assert "Peer Review Panel Protocol" in peer_review_contract_documents["peer-review-panel.md"]["body"]
    assert "Peer Review Phase Reliability" in peer_review_contract_documents["peer-review-reliability.md"]["body"]
    assert arxiv_contract_documents == {}
    assert set(respond_contract_documents) == {"peer-review-reliability.md"}
    assert any(path.endswith("peer-review-reliability.md") for path in respond_to_referees["contract_references"])
    assert "Peer Review Phase Reliability" in respond_contract_documents["peer-review-reliability.md"]["body"]
    assert "Treat `content` as the wrapper/context surface." in write_paper["loading_hint"]
    assert "Load `schema_documents` and `contract_documents` too when present" in write_paper["loading_hint"]


def test_bibliographer_skill_surface_stays_direct_only() -> None:
    from gpd.mcp.servers.skills_server import get_skill

    bibliographer = get_skill("gpd-bibliographer")
    direct_reference_suffixes = {
        "references/shared/shared-protocols.md",
        "references/physics-subfields.md",
        "references/orchestration/agent-infrastructure.md",
        "templates/notation-glossary.md",
        "references/publication/bibtex-standards.md",
        "references/publication/publication-pipeline-modes.md",
        "references/publication/bibliography-advanced-search.md",
    }

    assert "error" not in bibliographer
    assert bibliographer["reference_count"] == len(direct_reference_suffixes)
    assert {
        entry["path"].split("}/", 1)[1] for entry in bibliographer["referenced_files"]
    } == direct_reference_suffixes


def test_review_and_execution_prompts_expand_required_schema_sources() -> None:
    src_root = REPO_ROOT / "src/gpd/specs"

    review_reader_raw = (AGENTS_DIR / "gpd-review-reader.md").read_text(encoding="utf-8")
    referee_raw = (AGENTS_DIR / "gpd-referee.md").read_text(encoding="utf-8")
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

    assert "{GPD_INSTALL_DIR}/references/publication/peer-review-panel.md" in review_reader_raw
    assert "{GPD_INSTALL_DIR}/references/publication/peer-review-panel.md" in referee_raw
    assert "{GPD_INSTALL_DIR}/templates/paper/review-ledger-schema.md" in referee_raw
    assert "{GPD_INSTALL_DIR}/templates/paper/referee-decision-schema.md" in referee_raw
    assert "Peer Review Panel Protocol" not in review_reader
    assert "Peer Review Panel Protocol" in review_literature
    assert "Review Ledger Schema" not in referee
    assert "Referee Decision Schema" not in referee


def test_verification_and_agent_reference_prompts_expand_or_stage_required_reference_bodies() -> None:
    verify_work = _expand_prompt_surface(WORKFLOWS_DIR / "verify-work.md")
    verify_phase = _expand_prompt_surface(WORKFLOWS_DIR / "verify-phase.md")
    phase_researcher = _expand_prompt_surface(AGENTS_DIR / "gpd-phase-researcher.md")
    planner = _expand_prompt_surface(AGENTS_DIR / "gpd-planner.md")
    verify_work_staging = registry.get_command("verify-work").staged_loading
    assert verify_work_staging is not None
    inventory_build = next(stage for stage in verify_work_staging.stages if stage.id == "inventory_build")
    interactive_validation = next(stage for stage in verify_work_staging.stages if stage.id == "interactive_validation")

    assert "Verification Independence" not in verify_work
    assert "# Contract Results Schema" not in verify_work
    assert "references/verification/meta/verification-independence.md" in inventory_build.loaded_authorities
    assert "templates/contract-results-schema.md" in interactive_validation.loaded_authorities
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
    assert (
        "The standalone `gpd:verify-work` workflow reuses the same verification criteria through `verify-work.md`; this file itself is executed by the execute-phase orchestrator."
        in verify_phase
    )
    assert 'VERIFICATION_FILE="${phase_dir}/${phase_number}-VERIFICATION.md"' in verify_phase
    assert "Return status (`passed` | `gaps_found` | `expert_needed` | `human_needed`)" in verify_phase


def test_verification_independence_reference_examples_keep_required_contract_fields_visible() -> None:
    reference = (REFERENCES_DIR / "verification" / "meta" / "verification-independence.md").read_text(encoding="utf-8")

    assert reference.count("contract:\n  schema_version: 1") >= 2
    assert "context_intake:" in reference
    assert "forbidden_proxies:" in reference
    assert "uncertainty_markers:" in reference


def test_planner_and_summary_prompt_surfaces_expand_contract_schema_bodies() -> None:
    phase_prompt = _expand_prompt_surface(TEMPLATES_DIR / "phase-prompt.md")
    planner_prompt = _expand_prompt_surface(TEMPLATES_DIR / "planner-subagent-prompt.md")
    summary_template = _expand_prompt_surface(TEMPLATES_DIR / "summary.md")

    assert "# PLAN Contract Schema" in phase_prompt
    assert "schema_version: 1" in phase_prompt
    assert "in_scope:" in phase_prompt
    assert "context_intake:" in phase_prompt
    assert "Quick contract rules:" in phase_prompt
    assert phase_prompt.count("Quick contract rules:") == 1
    for token in (
        "tool_requirements",
        "researcher_setup",
        "scope.in_scope",
        "claim_kind",
        "observables[].kind",
        "deliverables[].kind",
        "acceptance_tests[].kind",
        "references[].kind",
        "references[].role",
        "links[].relation",
        "must_surface",
        "required_actions[]",
        "applies_to[]",
        "carry_forward_to[]",
        "uncertainty_markers",
    ):
        assert token in phase_prompt
    assert 'must_include_prior_outputs: ["GPD/phases/00-baseline/00-01-SUMMARY.md"]' in phase_prompt
    assert (
        "user_asserted_anchors: "
        '["GPD/phases/00-baseline/00-01-SUMMARY.md#vacuum-polarization-normalization"]' in phase_prompt
    )
    assert "claims:" in phase_prompt
    assert "observables: [obs-main]" in phase_prompt
    assert "### `forbidden_proxies[]`" in phase_prompt
    assert "### `links[]`" in phase_prompt
    assert planner_prompt.count("## Standard Planning Template") == 1
    assert planner_prompt.count("## Revision Template") == 1
    assert planner_prompt.count("@{GPD_INSTALL_DIR}/templates/plan-contract-schema.md") == 1
    for token in (
        "project_contract_gate.authoritative",
        "project_contract_load_info.status",
        "project_contract_validation.valid",
        "project_contract",
        "effective_reference_intake",
        "active_reference_context",
        "approach_policy",
        "scope.in_scope",
        "contract.context_intake",
        "claim_kind",
    ):
        assert token in planner_prompt
    assert "scope.unresolved_questions" in phase_prompt
    assert "Every claim must declare a stable `id`." in phase_prompt
    assert (
        "Do not reuse the same ID across `claims[]`, `deliverables[]`, `acceptance_tests[]`, or `references[]`"
        in phase_prompt
    )
    assert "contract-results-schema.md" in summary_template
    assert "single detailed rule source" in summary_template


def test_sync_state_and_write_paper_command_prompts_expand_required_schema_bodies() -> None:
    sync_state = _expand_prompt_surface(COMMANDS_DIR / "sync-state.md")
    write_paper = _expand_prompt_surface(COMMANDS_DIR / "write-paper.md")

    assert "# state.json Schema" in sync_state
    assert "Authoritative vs Derived" in sync_state
    assert "`project_contract`" in sync_state
    assert (
        "Do not reuse the same ID across `claims[]`, `deliverables[]`, `acceptance_tests[]`, or `references[]`; "
        "target resolution becomes ambiguous." in sync_state
    )
    assert "`convention_lock`" in sync_state
    assert "Reproducibility Manifest Template" in write_paper
    assert "bibliographer search breadth" in write_paper
    assert "paper-writer style by mode" in write_paper
    assert '"execution_steps"' in write_paper
    assert "random_seeds[].computation" in write_paper
    assert "resource_requirements[].step" in write_paper


def test_non_adapter_sources_do_not_hardcode_runtime_names() -> None:
    runtime_terms = {descriptor.runtime_name for descriptor in iter_runtime_descriptors()}
    runtime_terms.update(
        alias for descriptor in iter_runtime_descriptors() for alias in descriptor.selection_aliases if alias.strip()
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
    assert 'in_scope: ["Recover the benchmark curve within tolerance"]' in plan_schema
    assert 'unresolved_questions: ["[Optional open question that still blocks planning]"]' in plan_schema
    assert "context_intake:" in plan_schema
    assert "`contract.context_intake` is required and must be a non-empty object, not a string or list." in plan_schema
    assert "must_read_refs: [ref-main]" in plan_schema
    assert 'must_include_prior_outputs: ["GPD/phases/00-baseline/00-01-SUMMARY.md"]' in plan_schema
    assert 'user_asserted_anchors: ["GPD/phases/00-baseline/00-01-SUMMARY.md#lattice-normalization"]' in plan_schema
    assert 'known_good_baselines: ["GPD/phases/00-baseline/00-01-SUMMARY.md#published-large-n-curve"]' in plan_schema
    assert 'context_gaps: ["Comparison source still undecided before planning"]' in plan_schema
    assert 'crucial_inputs: ["Check the user\'s finite-volume cutoff choice before proceeding"]' in plan_schema
    assert "Use concrete anchors in `must_read_refs[]`" in plan_schema
    assert "preserve uncertainty and workflow visibility" in plan_schema
    assert "do not satisfy the hard grounding requirement by themselves" in plan_schema
    assert "approach_policy:" in plan_schema
    assert "allowed_fit_families: [power_law]" in plan_schema
    assert "`observables[]` may only reference declared `observables[].id`." in plan_schema
    assert "observables: [obs-main]" in plan_schema
    assert 'aliases: ["optional stable label or citation shorthand"]' in plan_schema
    assert "carry_forward_to: [planning, verification]" in plan_schema
    assert "automation: automated" in plan_schema
    assert (
        "`kind` is optional and defaults to `other`; set it when the plan knows a more specific semantic category."
        in plan_schema
    )
    assert (
        "`kind` and `role` are optional and default to `other`; set them when the anchor semantics are already known."
        in plan_schema
    )
    assert (
        "`relation` is optional and defaults to `other`; set it when the dependency type is already known."
        in plan_schema
    )
    assert "Proof-bearing claims must use an explicit non-`other` `claim_kind`" in plan_schema
    assert "required_actions: [read, compare, cite, avoid]" in plan_schema
    assert (
        "`required_actions[]` values must use the closed action vocabulary: `read`, `use`, `compare`, `cite`, `avoid`."
        in plan_schema
    )
    assert (
        "For non-scoping plans, `claims[]`, `deliverables[]`, `acceptance_tests[]`, and `forbidden_proxies[]` are all required."
        in plan_schema
    )
    assert "### `forbidden_proxies[]`" in plan_schema
    assert "### `links[]`" in plan_schema
    assert "unvalidated_assumptions" in plan_schema
    assert "competing_explanations" in plan_schema
    assert (
        "If `must_surface: true`, the locator must still be concrete enough to re-find later: a citation, DOI, arXiv identifier, durable external URL, or project-local artifact path."
        in plan_schema
    )
    assert "All ID cross-links must resolve to declared IDs." in plan_schema
    assert (
        "Do not reuse the same ID across `claims[]`, `deliverables[]`, `acceptance_tests[]`, or `references[]`; "
        "target resolution becomes ambiguous." in plan_schema
    )
    assert "`deliverables[]` must not be empty." in plan_schema
    assert "`acceptance_tests[]` must not be empty." in plan_schema
    assert "If `must_surface: true`, `applies_to[]` must not be empty." in plan_schema
    assert (
        "If `references[]` is non-empty and the contract does not already carry concrete grounding elsewhere, "
        "at least one reference must set `must_surface: true`." in plan_schema
    )
    assert "a missing `must_surface: true` reference is a warning, not a blocker" in plan_schema
    assert "blank-after-trim values are invalid" in plan_schema


def test_state_json_schema_surfaces_stdin_contract_persistence_and_model_normalization_rules() -> None:
    state_schema = _expand_prompt_surface(TEMPLATES_DIR / "state-json-schema.md")

    assert "printf '%s\\n' \"$PROJECT_CONTRACT_JSON\" | gpd --raw validate project-contract -" in state_schema
    assert "printf '%s\\n' \"$PROJECT_CONTRACT_JSON\" | gpd state set-project-contract -" in state_schema
    assert "temporary file" in state_schema
    assert "`schema_version` must be the integer `1`." in state_schema
    assert "Project contracts must include at least one observable, claim, or deliverable." in state_schema
    assert (
        "`uncertainty_markers.weakest_anchors` and `uncertainty_markers.disconfirming_observations` must both be non-empty."
        in state_schema
    )
    assert "`scope.in_scope` must name at least one project boundary or objective." in state_schema
    assert 'claim_kind": "theorem"' in state_schema
    assert '"proof_deliverables": ["deliv-proof-main"]' in state_schema
    assert '"kind": "claim_to_proof_alignment"' in state_schema
    assert "grounding fields must be concrete enough to re-find later" in state_schema
    assert (
        "If a project contract has any `references[]` and does not already carry concrete prior-output, "
        "user-anchor, or baseline grounding, at least one reference must set `must_surface: true`." in state_schema
    )
    assert "a missing `must_surface: true` reference is still a warning" in state_schema
    assert (
        "If a project-contract reference sets `must_surface: true`, `applies_to[]` must not be empty." in state_schema
    )
    assert (
        "If a project-contract reference sets `must_surface: true`, `required_actions[]` must not be empty."
        in state_schema
    )
    assert '"required_actions": ["read", "compare", "cite", "avoid"]' in state_schema
    assert (
        "`required_actions[]` uses the same closed action vocabulary enforced downstream in contract ledgers: `read`, `use`, `compare`, `cite`, `avoid`."
        in state_schema
    )
    assert (
        "Do not reuse the same ID across `claims[]`, `deliverables[]`, `acceptance_tests[]`, or `references[]`; "
        "target resolution becomes ambiguous." in state_schema
    )
    assert (
        "`scope.unresolved_questions`, `context_intake.context_gaps`, or `uncertainty_markers.weakest_anchors`"
        in state_schema
    )
    assert "Which reference should serve as the decisive benchmark anchor?" in state_schema
    assert "Blank-after-trim values are invalid" in state_schema


def test_phase_prompt_surfaces_validation_critical_plan_contract_rules() -> None:
    phase_prompt = (TEMPLATES_DIR / "phase-prompt.md").read_text(encoding="utf-8")

    assert "Quick contract rules:" in phase_prompt
    assert phase_prompt.count("Quick contract rules:") == 1
    for token in (
        "tool_requirements",
        "researcher_setup",
        "type: execute",
        "gap_closure: true",
        "scope.in_scope",
        "claim_kind",
        "observables[].kind",
        "deliverables[].kind",
        "acceptance_tests[].kind",
        "references[].kind",
        "references[].role",
        "links[].relation",
        "must_surface",
        "required_actions[]",
        "applies_to[]",
        "carry_forward_to[]",
        "uncertainty_markers",
    ):
        assert token in phase_prompt


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
    resume_work = expand_at_includes(
        (WORKFLOWS_DIR / "resume-work.md").read_text(encoding="utf-8"),
        REPO_ROOT / "src/gpd",
        "/runtime/",
    )
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
    assert (
        'phase ordering, prior momentum, or "we are already deep into execution" never waive a required bounded stop'
        in execute_plan
    )
    assert (
        "uninterrupted wall-clock time since the current segment started reaches `MAX_UNATTENDED_MINUTES_PER_PLAN`"
        in execute_plan
    )
    assert "Do NOT narrow just because a wave advanced or one proxy passed." in execute_phase
    assert "pre_execution_specialists" in execute_phase
    assert "PRE_EXECUTION_INIT=$(load_execute_phase_stage pre_execution_specialists)" in execute_phase
    assert '# task(subagent_type="gpd-notation-coordinator"' not in execute_phase
    assert '# task(subagent_type="gpd-experiment-designer"' not in execute_phase
    assert "What decisive evidence is still owed before downstream work is trustworthy?" in resume_work
    assert "Pattern D: Auto-bounded" in executor_agent
    assert "Canonical continuation fields define the public resume vocabulary" in resume_work
    assert "public top-level resume vocabulary" not in resume_work
    assert "compat_resume_surface" not in resume_work
    assert "gpd init resume" not in resume_work
    assert "execution_segment" in continuation
    assert "Required Checkpoint Payload" in checkpoints
    assert "rollback primitive" in checkpoint_flow
    assert "| `completed`    | -> update_roadmap (interactive verify-work equivalent)" not in execute_phase
    assert "| `diagnosed`    | Gaps were debugged; review fixes, then -> update_roadmap" not in execute_phase
    assert "| `validating`   | Verification in progress; wait or re-run verify-phase" not in execute_phase
    assert (
        "If the same report also carries `session_status: validating|completed|diagnosed`, treat that as conversational progress only."
        in execute_phase
    )
    assert "If the prior report carries `session_status: diagnosed`" in execute_phase


def test_show_phase_workflow_distinguishes_verification_status_from_session_status() -> None:
    show_phase = (WORKFLOWS_DIR / "show-phase.md").read_text(encoding="utf-8")

    assert "`*-VERIFICATION.md`" in show_phase
    assert (
        "read frontmatter to extract canonical verification `status`, plus `session_status` when present" in show_phase
    )
    assert "Automated verification uses `passed`/`gaps_found`/`expert_needed`/`human_needed`" in show_phase
    assert "researcher-session progress uses `session_status: validating|completed|diagnosed`" in show_phase
    assert "Automated verification uses `passed`/`gaps_found`/`human_needed`" not in show_phase
    assert "interactive validation uses `validating`/`completed`/`diagnosed`" not in show_phase


def test_execute_phase_and_related_agents_surface_only_plan_scoped_verification_artifacts() -> None:
    execute_phase = (WORKFLOWS_DIR / "execute-phase.md").read_text(encoding="utf-8")
    planner = (AGENTS_DIR / "gpd-planner.md").read_text(encoding="utf-8")
    verifier = (AGENTS_DIR / "gpd-verifier.md").read_text(encoding="utf-8")
    audit_milestone = (WORKFLOWS_DIR / "audit-milestone.md").read_text(encoding="utf-8")

    assert "- Verification: {phase_dir}/{phase}-VERIFICATION.md" in execute_phase
    assert '"$phase_dir"/VERIFICATION.md "$phase_dir"/*-VERIFICATION.md' not in execute_phase
    assert 'ls "$phase_dir"/*-VERIFICATION.md 2>/dev/null' in planner
    assert 'find_files("$PHASE_DIR/*-VERIFICATION.md")' in verifier
    assert "`find_files` `GPD/phases/*/*-VERIFICATION.md` by hand" in audit_milestone
    assert "GPD/phases/01-*/VERIFICATION.md" not in audit_milestone


def test_debug_prompts_use_session_status_for_diagnosis_progress() -> None:
    debug_workflow = (WORKFLOWS_DIR / "debug.md").read_text(encoding="utf-8")
    debugger = (AGENTS_DIR / "gpd-debugger.md").read_text(encoding="utf-8")

    assert "set `session_status: diagnosed`" in debug_workflow
    assert 'Update status in frontmatter to "diagnosed"' not in debug_workflow
    assert 'update `session_status` to "diagnosed"' in debugger
    assert 'Update status to "diagnosed"' not in debugger


def test_debug_command_and_workflow_wire_directly_to_gpd_debugger() -> None:
    debug_command = (COMMANDS_DIR / "debug.md").read_text(encoding="utf-8")
    debug_workflow = (WORKFLOWS_DIR / "debug.md").read_text(encoding="utf-8")
    debugger = (AGENTS_DIR / "gpd-debugger.md").read_text(encoding="utf-8")

    assert "gpd-debugger" in debug_command
    assert 'DEBUGGER_MODEL=$(gpd resolve-model gpd-debugger)' in debug_command
    assert 'subagent_type="gpd-debugger"' in debug_workflow
    assert "First, read {GPD_AGENTS_DIR}/gpd-debugger.md" in debug_workflow
    assert "public writable production agent specialized for discrepancy investigation" in debugger


def test_resume_workflow_surfaces_contract_load_and_validation_state() -> None:
    raw_resume_work = (WORKFLOWS_DIR / "resume-work.md").read_text(encoding="utf-8")
    resume_work = expand_at_includes(raw_resume_work, REPO_ROOT / "src/gpd", "/runtime/")
    resume_vocabulary = (REFERENCES_DIR / "orchestration" / "resume-vocabulary.md").read_text(encoding="utf-8")

    assert "@{GPD_INSTALL_DIR}/templates/state-json-schema.md" in raw_resume_work
    assert "project_contract_validation" in resume_work
    assert "project_contract_load_info" in resume_work
    assert "workspace_state_exists" in resume_work
    assert "workspace_roadmap_exists" in resume_work
    assert "workspace_project_exists" in resume_work
    assert "workspace_planning_exists" in resume_work
    assert_resume_authority_contract(
        resume_vocabulary,
        allow_explicit_alias_examples=False,
        require_generic_compatibility_note=False,
    )
    assert "Canonical continuation and recovery authority:" in resume_work
    assert "Canonical continuation fields define the public resume vocabulary" in resume_work
    _assert_resume_compatibility_note(resume_work)
    assert "public top-level resume vocabulary" not in resume_work
    assert "continuity_handoff_file" in resume_work
    assert "recorded_continuity_handoff_file" in resume_work
    assert "missing_continuity_handoff_file" in resume_work
    assert "machine_change_detected" in resume_work
    assert "Use `workspace_*` to judge the user-requested workspace before auto-selection" in resume_work
    assert "machine_change_notice" in resume_work
    assert "current_hostname" in resume_work
    assert "current_platform" in resume_work
    assert "session_hostname" in resume_work
    assert "session_platform" in resume_work
    assert "The recent-project list is advisory and machine-local" in resume_work
    assert "reloads that project's canonical state" in resume_work
    assert "only when `project_contract_gate.authoritative` is true" in resume_work
    assert "remain visible gate inputs and diagnostics" in resume_work
    assert (
        "If `project_contract_gate.authoritative` is false, present that contract as visible-but-blocked" in resume_work
    )
    assert "Contract repair required:" in resume_work
    assert "Repair the blocked contract or state-integrity issue before planning or execution" in resume_work


def _assert_resume_compatibility_note(text: str) -> None:
    assert "compatibility-only intake fields stay internal" in text.lower()


def test_resume_command_keeps_internal_resume_backend_details_out_of_public_prompt_surface() -> None:
    resume_command = expand_at_includes(
        (COMMANDS_DIR / "resume-work.md").read_text(encoding="utf-8"),
        REPO_ROOT / "src/gpd",
        "/runtime/",
    )

    assert "Canonical continuation fields define the public resume vocabulary" in resume_command
    _assert_resume_compatibility_note(resume_command)
    assert "compat_resume_surface" not in resume_command
    assert "gpd init resume" not in resume_command


def test_execution_observability_and_resume_workflow_surfaces_stay_conservative_about_stalls() -> None:
    help_command = (COMMANDS_DIR / "help.md").read_text(encoding="utf-8")
    help_workflow = expand_at_includes(
        (WORKFLOWS_DIR / "help.md").read_text(encoding="utf-8"),
        REPO_ROOT / "src/gpd",
        "/runtime/",
    )
    progress = (WORKFLOWS_DIR / "progress.md").read_text(encoding="utf-8")
    resume_work = expand_at_includes(
        (WORKFLOWS_DIR / "resume-work.md").read_text(encoding="utf-8"),
        REPO_ROOT / "src/gpd",
        "/runtime/",
    )

    assert "Display GPD help by delegating to the workflow-owned help surface." in help_command
    assert "@{GPD_INSTALL_DIR}/workflows/help.md" in help_command
    assert_execution_observability_surface_contract(help_workflow)
    assert_cost_surface_discoverability(help_workflow)
    assert "Start at the workflow-owned `## Quick Start` section." in help_command
    assert "When STATE.md appears out of sync with disk reality" in progress
    assert "advisory context only" in resume_work
    assert (
        'it is not a ranked bounded-segment resume candidate and does not justify `active_resume_kind="bounded_segment"`.'
        in resume_work
    )


def test_pause_resume_and_help_wiring_keep_runtime_handoff_and_local_snapshot_boundary() -> None:
    pause_work = (WORKFLOWS_DIR / "pause-work.md").read_text(encoding="utf-8")
    resume_work = expand_at_includes(
        (WORKFLOWS_DIR / "resume-work.md").read_text(encoding="utf-8"),
        REPO_ROOT / "src/gpd",
        "/runtime/",
    )
    help_workflow = expand_at_includes(
        (WORKFLOWS_DIR / "help.md").read_text(encoding="utf-8"),
        REPO_ROOT / "src/gpd",
        "/runtime/",
    )

    assert "gpd:resume-work" in resume_work
    assert "gpd resume" in resume_work
    assert "gpd resume --recent" in resume_work
    assert "gpd init resume" not in resume_work
    assert "guided runtime path" in resume_work
    assert "public local read-only summary" in resume_work
    assert "cross-project discovery surface" in resume_work
    assert "advisory and machine-local" in resume_work
    assert "reloads that project's canonical state" in resume_work
    assert "Canonical continuation fields define the public resume vocabulary" in resume_work
    assert "resume_candidates" in resume_work
    assert "compat_resume_surface" not in resume_work
    assert "Canonical continuation fields define the public resume vocabulary" in help_workflow
    assert (
        "Do NOT invent additional candidates from plan files without summaries, auto-checkpoints, or other ad hoc checkpoints."
        in resume_work
    )
    assert "gpd:resume-work" in pause_work
    assert "gpd resume" in pause_work
    assert "gpd resume --recent" in pause_work
    assert "This is the canonical recorded handoff artifact for the current phase." in pause_work
    assert "continuation handoff artifact" in pause_work or "session continuity" in pause_work
    assert "session.resume_file" not in pause_work
    assert "Canonical continuation fields define the public resume vocabulary" in help_workflow
    _assert_resume_compatibility_note(help_workflow)
    assert_recovery_ladder_contract(
        help_workflow,
        resume_work_fragments=("gpd:resume-work",),
        suggest_next_fragments=("gpd:suggest-next",),
        pause_work_fragments=("gpd:pause-work",),
    )


def test_state_portability_reference_keeps_resume_public_vocabulary_note_compact() -> None:
    state_portability = expand_at_includes(
        (REFERENCES_DIR / "orchestration" / "state-portability.md").read_text(encoding="utf-8"),
        REPO_ROOT / "src/gpd",
        "/runtime/",
    )
    help_workflow = expand_at_includes(
        (WORKFLOWS_DIR / "help.md").read_text(encoding="utf-8"),
        REPO_ROOT / "src/gpd",
        "/runtime/",
    )

    assert "Canonical continuation fields define the public resume vocabulary" in state_portability
    _assert_resume_compatibility_note(state_portability)
    assert "public top-level resume vocabulary" not in state_portability
    assert "gpd observe execution" in help_workflow
    assert "suggested read-only checks rather than runtime hotkeys" in help_workflow


def test_pause_resume_and_derivation_templates_preserve_result_id_continuity() -> None:
    pause_work = (WORKFLOWS_DIR / "pause-work.md").read_text(encoding="utf-8")
    resume_work = (WORKFLOWS_DIR / "resume-work.md").read_text(encoding="utf-8")
    continue_here = (TEMPLATES_DIR / "continue-here.md").read_text(encoding="utf-8")
    derivation_state = (TEMPLATES_DIR / "DERIVATION-STATE.md").read_text(encoding="utf-8")

    assert "Every intermediate result added to state.json (with result IDs)" in pause_work
    assert (
        "The `<persistent_state>` and `<intermediate_results>` sections in `.continue-here.md` are filled (documenting what was appended to DERIVATION-STATE.md)"
        in pause_work
    )
    assert "gpd state record-session \\" in pause_work
    assert "Treat an explicit `--last-result-id` override as a manual repair path" in pause_work
    assert (
        "If the active bounded-segment continuity already carries a canonical `last_result_id`, omit `--last-result-id`"
        in pause_work
    )
    assert "canonical `last_result_id`" in resume_work
    assert "preferred continuity anchor" in resume_work
    assert "Reference the result IDs added to state.json this session" in continue_here
    assert "Each entry links back to the state.json intermediate_results key" in continue_here
    assert "Result IDs should match those in state.json intermediate_results" in derivation_state


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
    assert (
        "If no row cleanly fits, stay with generic execution guidance plus core verification expectations instead of guessing."
        in executor_guide
    )


def test_stage7_runtime_parity_docs_use_canonical_model_resolution_and_generic_handoff_rules() -> None:
    model_resolution = (REFERENCES_DIR / "orchestration" / "model-profile-resolution.md").read_text(encoding="utf-8")
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
    assert "First, read {GPD_AGENTS_DIR}/gpd-planner.md for your role and instructions." in quick
    assert "supports staged planner loading when available" in quick
    assert "project_contract_load_info.status" in quick
    assert "project_contract_validation.valid" in quick
    assert "project_contract_validation" in quick
    assert "project_contract_load_info" in quick
    assert (
        "Quick mode still inherits the approved `project_contract` only when `project_contract_gate.authoritative` is true"
        in quick
    )
    assert "**Project Contract Gate:** {project_contract_gate}" in quick
    assert "**Project Contract Load Info:** {project_contract_load_info}" in quick
    assert "**Project Contract Validation:** {project_contract_validation}" in quick
    assert "**Contract Intake:** {contract_intake}" in quick
    assert "Contract intake: {contract_intake}" in quick
    assert "Project contract gate: {project_contract_gate}" in quick
    assert "gpd validate plan-preflight" in quick
    assert "## CHECKPOINT REACHED" in quick
    assert "classifyHandoffIfNeeded" not in execute_phase
    assert "classifyHandoffIfNeeded" not in execute_plan
    assert "classifyHandoffIfNeeded" not in quick
    assert "cat GPD/config.json" not in model_resolution
    assert "print(c.get('model_profile', 'review'))" not in execute_phase


def test_verify_work_gap_closure_delegation_surfaces_contract_gate_inputs() -> None:
    verify_work = (WORKFLOWS_DIR / "verify-work.md").read_text(encoding="utf-8")

    assert "**Project Contract Gate:** {project_contract_gate}" in verify_work
    assert "**Project Contract Load Info:** {project_contract_load_info}" in verify_work
    assert "**Project Contract Validation:** {project_contract_validation}" in verify_work
    assert "**Contract Intake:** {contract_intake}" in verify_work
    assert "**Effective Reference Intake:** {effective_reference_intake}" in verify_work
    assert "tool_requirements" in verify_work
    assert "machine-checkable hard requirements" in verify_work
    assert "The shared planner template owns the canonical planning policy and contract gate." not in verify_work


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
    verifier_profiles = (REFERENCES_DIR / "verification" / "meta" / "verifier-profile-checks.md").read_text(
        encoding="utf-8"
    )
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
    assert "`${PAPER_DIR}/FIGURE_TRACKER.md`" in figure_tracker
    assert "validate paper-quality --from-project ." in write_paper
    assert "Before reading or updating `${PAPER_DIR}/FIGURE_TRACKER.md`, load" in write_paper
    assert '"review_cadence": "adaptive"' in new_project
    assert "Adaptive review cadence" in new_project
    assert (
        "prior decisive `contract_results`, decisive `comparison_verdicts`, or an explicit approach lock"
        in execute_phase
    )
    assert "paper/FIGURE_TRACKER.md" in execute_phase
    assert "GPD/paper/FIGURE_TRACKER.md" not in execute_phase
    assert "figure_registry" in scoring
    assert "manuscript-root `FIGURE_TRACKER.md`" in scoring
    assert "paper/<topic_stem>.tex" in (REFERENCES_DIR / "orchestration" / "artifact-surfacing.md").read_text(
        encoding="utf-8"
    )
    assert "paper/<topic_stem>.pdf" in (REFERENCES_DIR / "orchestration" / "artifact-surfacing.md").read_text(
        encoding="utf-8"
    )
    assert "ARTIFACT-MANIFEST.json" in (REFERENCES_DIR / "protocols" / "hypothesis-driven-research.md").read_text(
        encoding="utf-8"
    )
    assert "MANUSCRIPT_TEX" in (REFERENCES_DIR / "protocols" / "hypothesis-driven-research.md").read_text(
        encoding="utf-8"
    )
    assert "main.tex" not in (REFERENCES_DIR / "protocols" / "hypothesis-driven-research.md").read_text(
        encoding="utf-8"
    )
    assert "Review (Recommended)" in settings
    assert "all required contract-aware checks" in profiles
    assert "current registry: 5.1-5.19" in quick_reference
    assert "still run every contract-aware check required by the plan" in verifier_profiles
    assert "required first-result, anchor, and pre-fanout checkpoints" in planner
    assert "Do NOT change conventions mid-project without an explicit checkpoint" in planner
    assert "Required first-result, anchor, and pre-fanout gates still apply even in yolo mode" in executor
    assert "suggested_contract_checks" in verifier_agent


def test_publication_workflows_refresh_bibliography_audit_after_bibliography_changes() -> None:
    write_paper = (WORKFLOWS_DIR / "write-paper.md").read_text(encoding="utf-8")
    respond = (WORKFLOWS_DIR / "respond-to-referees.md").read_text(encoding="utf-8")
    peer_review = (WORKFLOWS_DIR / "peer-review.md").read_text(encoding="utf-8")
    arxiv_submission = (WORKFLOWS_DIR / "arxiv-submission.md").read_text(encoding="utf-8")
    shared_preflight = (TEMPLATES_DIR / "paper" / "publication-manuscript-root-preflight.md").read_text(
        encoding="utf-8"
    )

    assert "`gpd paper-build` is the authoritative step that regenerates `${PAPER_DIR}/BIBLIOGRAPHY-AUDIT.json`" in write_paper
    assert "the derived `reference_id -> bibtex_key` bridge" in write_paper
    assert (
        "Prefer the `reference_id -> bibtex_key` mapping surfaced by `gpd paper-build` over reconstructing manuscript keys manually from prose or source ordering"
        in write_paper
    )
    assert "Rerun it whenever the bibliography or citation set changes before strict review." in write_paper
    assert (
        "For the default bootstrap path, this means: rerun `paper-build` so `${PAPER_DIR}/BIBLIOGRAPHY-AUDIT.json` reflects the current bibliography before strict review."
        in write_paper
    )
    assert (
        "refresh `${PAPER_DIR}/BIBLIOGRAPHY-AUDIT.json` before generating the response letter or proceeding to final review"
        in respond
    )
    assert PUBLICATION_SHARED_PREFLIGHT_INCLUDE in peer_review
    peer_review_staging = registry.get_command("peer-review").staged_loading

    assert peer_review_staging is not None
    assert "references/publication/publication-review-round-artifacts.md" in peer_review_staging.stage(
        "artifact_discovery"
    ).loaded_authorities
    assert "absent, stale, or not review-ready" in peer_review
    assert "bibliography_audit_clean" in peer_review
    assert "reproducibility_ready" in peer_review
    assert (
        "Treat `gpd paper-build` as the authoritative step that regenerates the resolved manuscript-root "
        "`ARTIFACT-MANIFEST.json` and `BIBLIOGRAPHY-AUDIT.json`."
        in shared_preflight
    )
    assert PUBLICATION_BOOTSTRAP_PREFLIGHT_INCLUDE in write_paper
    assert PUBLICATION_RESPONSE_WRITER_HANDOFF_INCLUDE in write_paper
    assert PUBLICATION_BOOTSTRAP_PREFLIGHT_INCLUDE in respond
    assert PUBLICATION_RESPONSE_WRITER_HANDOFF_INCLUDE in respond
    assert PUBLICATION_BOOTSTRAP_PREFLIGHT_INCLUDE in arxiv_submission
    assert PUBLICATION_ROUND_ARTIFACTS_INCLUDE in arxiv_submission
    assert PUBLICATION_RESPONSE_WRITER_HANDOFF_INCLUDE not in arxiv_submission


def test_publication_workflows_keep_manuscript_local_reference_status_rooted_at_the_resolved_manuscript_directory() -> (
    None
):
    write_paper = (WORKFLOWS_DIR / "write-paper.md").read_text(encoding="utf-8")
    peer_review = (WORKFLOWS_DIR / "peer-review.md").read_text(encoding="utf-8")
    respond = (WORKFLOWS_DIR / "respond-to-referees.md").read_text(encoding="utf-8")
    arxiv_submission = (WORKFLOWS_DIR / "arxiv-submission.md").read_text(encoding="utf-8")

    assert PUBLICATION_BOOTSTRAP_PREFLIGHT_INCLUDE in write_paper
    assert PUBLICATION_RESPONSE_WRITER_HANDOFF_INCLUDE in write_paper
    assert (
        "After resolution, keep all manuscript-local support artifacts rooted at the same explicit manuscript directory:"
        in peer_review
    )
    assert "- `BIBLIOGRAPHY_AUDIT_PATH` = `${MANUSCRIPT_ROOT}/BIBLIOGRAPHY-AUDIT.json`" in peer_review
    assert (
        "refresh `${PAPER_DIR}/BIBLIOGRAPHY-AUDIT.json` before generating the response letter or proceeding to final review"
        in respond
    )
    assert PUBLICATION_BOOTSTRAP_PREFLIGHT_INCLUDE in respond
    assert PUBLICATION_RESPONSE_WRITER_HANDOFF_INCLUDE in respond
    assert PUBLICATION_BOOTSTRAP_PREFLIGHT_INCLUDE in arxiv_submission
    assert (
        "Strict preflight reads `ARTIFACT-MANIFEST.json`, `BIBLIOGRAPHY-AUDIT.json`, and `reproducibility-manifest.json` from the resolved manuscript directory itself."
        in arxiv_submission
    )
    assert (
        "The same resolved manuscript root is also the strict preflight source of truth for packaging."
        in arxiv_submission
    )


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
    assert "only when `project_contract_gate.authoritative` is true" in new_milestone
    assert (
        "checkpoint with the user and repair the stored contract before using it for milestone scope" in new_milestone
    )
    assert "same contract-critical floor at all times" in verify_work
    assert "phase 1-2" not in plan_phase
    assert "phase 3+" not in plan_phase
    assert "N≥3" not in plan_phase
    assert "does NOT rewrite `execution.review_cadence`" in set_profile
    assert "verify_between_waves" not in set_profile
    assert "independent of `model_profile` and `research_mode`" in settings
    assert "wall-clock and task budgets still create bounded segments in every autonomy mode" in planning_config
    assert (
        "phase number, wave number, and `model_profile` do not create or retire these gates by themselves"
        in planning_config
    )
    assert "There is no separate `adaptive_transition` block" in research_modes
    assert "The decision is evidence-driven, not phase-count-driven." in meta_orchestration
    assert "Proxy-only or sanity-only passes do NOT satisfy this." in meta_orchestration


def test_settings_command_keeps_wrapper_thin_and_delegates_manual_to_workflow() -> None:
    settings_command = (COMMANDS_DIR / "settings.md").read_text(encoding="utf-8")

    assert "@{GPD_INSTALL_DIR}/workflows/settings.md" in settings_command
    assert "Keep this wrapper thin" in settings_command
    assert "Do not invent a parallel settings flow" in settings_command
    assert (
        "preset, model-posture, tier-model, budget, permission-sync, and local CLI bridge wording" in settings_command
    )


def test_help_surfaces_distinguish_runtime_slash_commands_from_local_cli_subcommands() -> None:
    help_command = (COMMANDS_DIR / "help.md").read_text(encoding="utf-8")
    help_workflow = (WORKFLOWS_DIR / "help.md").read_text(encoding="utf-8")

    assert "Display GPD help by delegating to the workflow-owned help surface." in help_command
    assert "@{GPD_INSTALL_DIR}/workflows/help.md" in help_command
    assert "## Step 2: Quick Start Extract (Default Output)" in help_command
    assert "## Step 3: Compact Command Index (--all)" in help_command
    assert "## Step 4: Single Command Detail Extract (--command <name>)" in help_command

    assert_help_workflow_runtime_reference_contract(help_workflow)
    assert "gpd validate command-context gpd:<name>" in help_workflow


def test_help_command_keeps_static_quick_start_while_workflow_owns_full_reference() -> None:
    help_command = (COMMANDS_DIR / "help.md").read_text(encoding="utf-8")
    help_workflow = (WORKFLOWS_DIR / "help.md").read_text(encoding="utf-8")
    quick_start_reference = _extract_between(help_workflow, "## Quick Start", "## Command Index")

    assert "@{GPD_INSTALL_DIR}/workflows/help.md" in help_command
    assert_help_command_quick_start_extract_contract(help_command)
    assert_help_command_all_extract_contract(help_command)
    assert_help_command_single_command_extract_contract(help_command)
    assert "Append this one wrapper-owned line:" in help_command
    assert_help_workflow_runtime_reference_contract(help_workflow)
    assert "## Detailed Command Reference" in help_workflow
    assert_help_workflow_quick_start_taxonomy_contract(quick_start_reference)


def test_help_workflow_state_aware_variant_surfaces_paused_resume_branch() -> None:
    help_workflow = (WORKFLOWS_DIR / "help.md").read_text(encoding="utf-8")

    assert_runtime_reset_rediscovery_contract(
        help_workflow,
        extra_reset_fragments=("then run gpd resume in your normal terminal",),
        extra_reset_not_recovery_fragments=("then run gpd resume in your normal terminal",),
    )
    assert "## Contextual Help (State-Aware Variant)" in help_workflow
    assert "Returning to work:" in help_workflow
    assert "gpd:resume-work" in help_workflow
    assert (
        "gpd:resume-work       # Continue in-runtime from the reopened project's canonical state after reopening that workspace"
        in help_workflow
    )
    assert help_workflow.index("gpd resume --recent") < help_workflow.index("gpd:resume-work")
    assert "gpd:progress" in help_workflow
    assert "gpd:suggest-next" in help_workflow
    assert "gpd:tangent" in help_workflow


def test_help_and_execution_surfaces_wire_tangent_control_path() -> None:
    help_workflow = (WORKFLOWS_DIR / "help.md").read_text(encoding="utf-8")
    plan_phase = (WORKFLOWS_DIR / "plan-phase.md").read_text(encoding="utf-8")
    execute_phase = (WORKFLOWS_DIR / "execute-phase.md").read_text(encoding="utf-8")
    execute_plan = (WORKFLOWS_DIR / "execute-plan.md").read_text(encoding="utf-8")
    tangent_workflow = (WORKFLOWS_DIR / "tangent.md").read_text(encoding="utf-8")

    assert "gpd:tangent" in help_workflow
    assert re.search(
        r"gpd:tangent[^\n]*?(?:tangent|side investigation|alternative direction|parallel)", help_workflow, re.I
    )
    assert "gpd:tangent" in plan_phase
    assert re.search(r"gpd:tangent.*?(?:side|alternative|parallel|branch)", plan_phase, re.I | re.S)
    assert "gpd:tangent" in execute_phase
    assert re.search(r"gpd:tangent.*?(?:branch|follow-up|alternative)", execute_phase, re.I | re.S)
    assert "tangent_summary" in execute_phase
    assert "tangent_decision" in execute_phase
    assert "optional `tangent_summary` and `tangent_decision`" in execute_phase
    assert (
        "keep it inside the same live execution payload instead of inventing a new tangent state machine"
        in execute_phase
    )
    assert "Do not create a new branch, child plan, or side subagent from executor initiative alone." in execute_phase
    assert "tangent_summary" in execute_plan
    assert "tangent_decision" in execute_plan
    assert (
        "keep it in the same execution payload rather than inventing a new event family. Optional fields:"
        in execute_plan
    )
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
        assert "gpd:tangent" in content
        assert "gpd:branch-hypothesis" in content

    assert "Explore mode widens analysis and comparison, not branch creation." in planner
    assert "Explore mode alone does not authorize git-backed branches" in planner
    assert (
        "Suppress optional tangent surfacing unless the user explicitly requests it or the current approach is blocked"
        in planner
    )
    assert "do not auto-create git-backed branches or branch-like plans" in plan_phase
    assert "`git.branching_strategy` does not override this rule." in plan_phase
    assert "suppress optional tangents entirely unless the user explicitly requests them" in plan_phase
    assert "Do not volunteer `gpd:branch-hypothesis` as the default response in exploit mode." in plan_phase


def test_help_surfaces_describe_regression_check_as_metadata_scan_not_full_reverification() -> None:
    help_workflow = (WORKFLOWS_DIR / "help.md").read_text(encoding="utf-8")

    assert "SUMMARY" in help_workflow
    assert "frontmatter" in help_workflow
    assert "convention conflicts" in help_workflow
    assert "VERIFICATION" in help_workflow
    assert "canonical statuses" in help_workflow
    assert "re-runs dimensional analysis" not in help_workflow
    assert "re-runs limiting cases" not in help_workflow
    assert "re-runs numerical checks" not in help_workflow


def test_help_surfaces_use_projectless_examples_that_satisfy_command_context_predicates() -> None:
    help_workflow = (WORKFLOWS_DIR / "help.md").read_text(encoding="utf-8")

    assert 'Usage: `gpd:derive-equation "derive the one-loop beta function"`' in help_workflow
    assert "Usage: `gpd:dimensional-analysis 3`" in help_workflow
    assert "Usage: `gpd:limiting-cases 3`" in help_workflow
    assert "Usage: `gpd:numerical-convergence 3`" in help_workflow
    assert "Usage: `gpd:compare-experiment predictions.csv experiment.csv`" in help_workflow
    assert (
        "Usage: `gpd:sensitivity-analysis --target cross_section --params g,m,Lambda --method numerical`"
        in help_workflow
    )


def test_verification_and_publication_prompts_keep_decisive_contract_targets_reader_visible() -> None:
    verify_work = (WORKFLOWS_DIR / "verify-work.md").read_text(encoding="utf-8")
    write_paper = (WORKFLOWS_DIR / "write-paper.md").read_text(encoding="utf-8")
    peer_review = (WORKFLOWS_DIR / "peer-review.md").read_text(encoding="utf-8")
    respond = (WORKFLOWS_DIR / "respond-to-referees.md").read_text(encoding="utf-8")

    assert "researcher can recognize in the phase promise" in verify_work
    assert (
        "Do not mark the parent claim or acceptance test as passed until that decisive comparison is resolved."
        in verify_work
    )
    assert "Missing generic `verification_status` / `confidence` tags alone are not blockers." in write_paper
    assert "Only require the manuscript to surface decisive comparisons for claims it actually makes." in write_paper
    assert (
        "Do not enter `pre_submission_review` with a missing or non-review-ready reproducibility manifest"
        in write_paper
    )
    assert "review-support artifacts are scaffolding" in peer_review
    assert (
        "Treat referee requests beyond the manuscript's honest scope as optional unless they expose a real support gap"
        in respond
    )
