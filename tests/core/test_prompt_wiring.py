"""Assertions for prompt/template wiring."""

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
from gpd.core.workflow_staging import load_workflow_stage_manifest, validate_workflow_stage_manifest_payload
from gpd.registry import _parse_frontmatter, _parse_tools
from tests.assertion_taxonomy_support import (
    FragmentAssertion,
    FragmentMode,
    MatchMode,
    assert_prompt_contracts,
    forbidden_duplicate,
    fragment_count,
    machine_exact,
    public_exact,
    semantic_anchor,
    semantic_concept,
)
from tests.core.test_spawn_contracts import _find_single_task
from tests.doc_surface_contracts import (
    assert_cost_surface_discoverability,
    assert_execution_observability_surface_contract,
    assert_help_command_all_extract_contract,
    assert_help_command_quick_start_extract_contract,
    assert_help_command_single_command_extract_contract,
    assert_help_workflow_quick_start_taxonomy_contract,
    assert_help_workflow_runtime_reference_contract,
    assert_publication_lane_boundary_contract,
    assert_recovery_ladder_contract,
    assert_resume_authority_contract,
    assert_runtime_reset_rediscovery_contract,
)
from tests.stage_authority_test_support import (
    assert_conditional_authorities as _assert_conditional_authorities,
)
from tests.stage_authority_test_support import (
    assert_loaded_authorities as _assert_loaded_authorities,
)
from tests.stage_authority_test_support import (
    assert_write_paper_publication_review_authorities as _assert_write_paper_publication_review_authorities,
)
from tests.workflow_authority_support import (
    STAGED_WORKFLOW_AUTHORITY_NAMES,
    expanded_workflow_authority_text,
    workflow_authority_text,
)


@pytest.fixture(autouse=True)
def _clean_registry_cache():
    """Ensure fresh registry cache for each test."""
    from gpd import registry

    registry.invalidate_cache()
    yield
    registry.invalidate_cache()


REPO_ROOT = Path(__file__).resolve().parents[2]
README_PATH = REPO_ROOT / "README.md"
TEMPLATES_DIR = REPO_ROOT / "src/gpd/specs/templates"
WORKFLOWS_DIR = REPO_ROOT / "src/gpd/specs/workflows"
COMMANDS_DIR = REPO_ROOT / "src/gpd/commands"
AGENTS_DIR = REPO_ROOT / "src/gpd/agents"
REFERENCES_DIR = REPO_ROOT / "src/gpd/specs/references"
CONTRACT_BASELINE_FIXTURES = REPO_ROOT / "tests" / "fixtures" / "stage0"
CONTRACT_RESULT_FIXTURES = REPO_ROOT / "tests" / "fixtures" / "stage4"
PUBLICATION_SHARED_PREFLIGHT_INCLUDE = "@{GPD_INSTALL_DIR}/templates/paper/publication-manuscript-root-preflight.md"
PUBLICATION_BOOTSTRAP_PREFLIGHT_INCLUDE = "@{GPD_INSTALL_DIR}/references/publication/publication-bootstrap-preflight.md"
PUBLICATION_BOOTSTRAP_PREFLIGHT_PATH = "{GPD_INSTALL_DIR}/references/publication/publication-bootstrap-preflight.md"
PUBLICATION_RESPONSE_WRITER_HANDOFF_INCLUDE = (
    "{GPD_INSTALL_DIR}/references/publication/publication-response-writer-handoff.md"
)
PUBLICATION_ROUND_ARTIFACTS_INCLUDE = "{GPD_INSTALL_DIR}/references/publication/publication-review-round-artifacts.md"
PUBLICATION_ROUND_ARTIFACTS_PATH = "{GPD_INSTALL_DIR}/references/publication/publication-review-round-artifacts.md"
PUBLICATION_REVIEW_RELIABILITY_INCLUDE = "{GPD_INSTALL_DIR}/references/publication/peer-review-reliability.md"
PUBLICATION_REVIEW_RELIABILITY_INLINE = "{GPD_INSTALL_DIR}/references/publication/peer-review-reliability.md"
PROJECT_BACKED_MANUSCRIPT_EVIDENCE = (
    "phase summaries or milestone digest",
    "verification reports",
    "manuscript-root bibliography audit",
    "manuscript-root artifact manifest",
    "manuscript-root reproducibility manifest",
    "manuscript-root publication artifacts",
)
PROJECT_BACKED_MANUSCRIPT_PREFLIGHTS = (
    "project_state",
    "roadmap",
    "conventions",
    "research_artifacts",
    "verification_reports",
    "artifact_manifest",
    "bibliography_audit",
    "bibliography_audit_clean",
    "reproducibility_manifest",
    "reproducibility_ready",
)
PEER_REVIEW_CONDITIONAL_REQUIREMENTS = [
    {
        "when": "project-backed manuscript review",
        "required_outputs": [],
        "required_evidence": list(PROJECT_BACKED_MANUSCRIPT_EVIDENCE),
        "blocking_conditions": [
            "missing project state",
            "missing roadmap",
            "missing conventions",
            "no research artifacts",
        ],
        "preflight_checks": list(PROJECT_BACKED_MANUSCRIPT_PREFLIGHTS),
        "blocking_preflight_checks": list(PROJECT_BACKED_MANUSCRIPT_PREFLIGHTS),
        "stage_artifacts": [],
    },
    {
        "when": "theorem-bearing claims are present",
        "required_outputs": ["${REVIEW_ROOT}/PROOF-REDTEAM{round_suffix}.md"],
        "required_evidence": [],
        "blocking_conditions": [],
        "preflight_checks": [],
        "blocking_preflight_checks": [],
        "stage_artifacts": ["${REVIEW_ROOT}/PROOF-REDTEAM{round_suffix}.md"],
    },
]
ARXIV_CONDITIONAL_REQUIREMENTS = [
    {
        "when": "theorem-bearing manuscripts are present",
        "required_outputs": [],
        "required_evidence": ["cleared manuscript proof review for theorem-bearing manuscripts"],
        "blocking_conditions": ["missing or stale manuscript proof review for theorem-bearing manuscripts"],
        "blocking_preflight_checks": ["manuscript_proof_review"],
        "stage_artifacts": [],
    }
]


def _assert_contains_fragments(text: str, *fragments: str) -> None:
    missing = [fragment for fragment in fragments if fragment not in text]
    assert not missing, "Missing expected prompt fragments:\n" + "\n".join(missing)


def _assert_exact_items(collection, *items: str, context: str) -> None:
    missing = [item for item in items if item not in collection]
    assert not missing, f"{context} missing exact items: {missing}"


def _review_requirement_rows(requirements, fields: tuple[str, ...]) -> list[dict[str, object]]:
    return [
        {
            field: getattr(requirement, field) if field == "when" else list(getattr(requirement, field))
            for field in fields
        }
        for requirement in requirements
    ]


def _assert_prompt_contracts(text: str, *assertions: FragmentAssertion) -> None:
    for assertion in assertions:
        assertion.check(text)


def _assert_fragment_groups(*groups) -> None:
    for helper, text, context, *fragments in groups:
        if len(fragments) == 1 and isinstance(fragments[0], tuple):
            fragments = fragments[0]
        helper(text, *fragments, context=context)


def _assert_machine_fragments(text: str, *fragments: str, context: str) -> None:
    _assert_prompt_contracts(text, machine_exact(context, fragments, context=context))


def _assert_public_fragments(text: str, *fragments: str, context: str) -> None:
    _assert_prompt_contracts(text, public_exact(context, fragments, context=context))


def _assert_semantic_fragments(text: str, *fragments: str, context: str) -> None:
    _assert_prompt_contracts(
        text, semantic_anchor(context, fragments, match=MatchMode.CASEFOLD_NORMALIZED, context=context)
    )


def _assert_semantic_concepts(
    text: str,
    concepts: dict[str, tuple[str, ...]],
    *,
    context: str,
) -> None:
    _assert_prompt_contracts(
        text,
        *(
            semantic_anchor(concept, fragments, match=MatchMode.CASEFOLD_NORMALIZED, context=context)
            for concept, fragments in concepts.items()
        ),
    )


def _assert_semantic_concept(
    text: str,
    label: str,
    *,
    required: str | tuple[str, ...] | None = None,
    forbidden: str | tuple[str, ...] | None = None,
    match: MatchMode | str = MatchMode.CASEFOLD_NORMALIZED,
    context: str,
) -> None:
    _assert_prompt_contracts(
        text,
        *semantic_concept(label, required=required, forbidden=forbidden, match=match, context=context),
    )


def _assert_init_placeholders_visible(text: str, fields: tuple[str, ...], *, context: str) -> None:
    _mf(text, *(f"{{{field}}}" for field in fields), context=context)


def _assert_command_delegates_to_workflow(
    command_text: str,
    workflow_id: str,
    *,
    semantic_fragments: tuple[str, ...] = (),
    stale_fragments: tuple[str, ...] = (),
    context: str | None = None,
) -> None:
    context = context or f"{workflow_id} command workflow delegation"
    include_fragments = [
        f"@{{GPD_INSTALL_DIR}}/workflows/{workflow_id}.md",
        f"{{GPD_INSTALL_DIR}}/workflows/{workflow_id}.md",
    ]
    manifest_path = WORKFLOWS_DIR / f"{workflow_id}-stage-manifest.json"
    if manifest_path.is_file():
        manifest = load_workflow_stage_manifest(workflow_id)
        include_fragments.extend(
            f"@{{GPD_INSTALL_DIR}}/{path}" for stage in manifest.stages for path in stage.mode_paths
        )

    _assert_prompt_contracts(
        command_text,
        machine_exact(
            f"{workflow_id} workflow include", tuple(include_fragments), mode=FragmentMode.ANY, context=context
        ),
    )
    if semantic_fragments:
        _sf(command_text, *semantic_fragments, context=context)
    if stale_fragments:
        _ff(command_text, *stale_fragments, context=context)


def _assert_forbidden_fragments(text: str, *fragments: str, context: str) -> None:
    _assert_prompt_contracts(
        text,
        *(
            forbidden_duplicate(f"{context} forbidden fragment {index}", fragment, max_count=0, context=context)
            for index, fragment in enumerate(fragments, start=1)
        ),
    )


_mf = _assert_machine_fragments
_pf = _assert_public_fragments
_sf = _assert_semantic_fragments
_ff = _assert_forbidden_fragments


def _m(text: str, context: str, *fragments: str) -> None:
    _mf(text, *fragments, context=context)


def _p(text: str, context: str, *fragments: str) -> None:
    _pf(text, *fragments, context=context)


def _s(text: str, context: str, *fragments: str) -> None:
    _sf(text, *fragments, context=context)


def _f(text: str, context: str, *fragments: str) -> None:
    _ff(text, *fragments, context=context)


def _workflow_authority_text(name: str) -> str:
    return workflow_authority_text(WORKFLOWS_DIR, name)


def _expanded_workflow_authority_text(name: str, *, runtime: str | None = None) -> str:
    return expanded_workflow_authority_text(
        WORKFLOWS_DIR,
        name,
        src_root=REPO_ROOT / "src/gpd",
        path_prefix="/runtime/",
        runtime=runtime,
    )


def _autonomous_authority_text() -> str:
    paths = [WORKFLOWS_DIR / "autonomous.md"]
    stage_dir = WORKFLOWS_DIR / "autonomous"
    if stage_dir.is_dir():
        paths.extend(sorted(stage_dir.glob("*.md")))
    return "\n\n".join(path.read_text(encoding="utf-8") for path in paths)


def _success_criteria_sections(text: str) -> str:
    sections = re.findall(r"<success_criteria>(.*?)</success_criteria>", text, flags=re.DOTALL)
    return "\n\n".join(sections) if sections else text


def _assert_help_usage_line(text: str, command_name: str, *argument_fragments: str) -> None:
    pattern = rf"(?:^|\n)(?:- )?(?:Usage: )?`gpd:{re.escape(command_name)}(?P<arguments>[^`]*)`"
    matches = tuple(re.finditer(pattern, text))

    assert matches, f"missing help usage line for gpd:{command_name}"
    argument_options = tuple(match.group("arguments").strip() for match in matches)
    explicit_options = tuple(arguments for arguments in argument_options if arguments)
    assert explicit_options, f"usage line for gpd:{command_name} must include explicit input"
    if argument_fragments:
        assert any(all(fragment in arguments for fragment in argument_fragments) for arguments in explicit_options), (
            f"usage line for gpd:{command_name} missing argument fragments: {argument_fragments}"
        )


def _assert_slides_public_label_local_preflight_guidance(text: str, *, shared_source: bool = False) -> None:
    _assert_contains_fragments(
        text,
        "validate command-context",
        "`slides`",
    )
    if shared_source:
        _assert_contains_fragments(
            text,
            "this shared workflow is `gpd:slides`",
            "active runtime's native command label",
            "bare registry slug `slides`",
        )
        assert "$gpd-slides" not in text
    else:
        assert "this shared workflow is `gpd:slides`" in text or (
            "public runtime label" in text and "$gpd-slides" in text
        )
    assert "bare" in text.lower()
    assert any(
        fragment in text
        for fragment in (
            "local command-context bridge argument",
            "shell/local bridge",
            "bare registry slug",
        )
    )


def _assert_workflow_calls_staged_init_for_manifest_stages(workflow_id: str, workflow_text: str) -> None:
    staged_loading = registry.get_command(workflow_id).staged_loading

    assert staged_loading is not None
    for stage_id in staged_loading.stage_ids():
        pattern = rf"gpd --raw init {re.escape(workflow_id)}[\s\S]{{0,120}}--stage {re.escape(stage_id)}"
        helper_call = f"load_{workflow_id.replace('-', '_')}_stage {stage_id}"
        assert re.search(pattern, workflow_text) or helper_call in workflow_text, (
            f"missing staged init call for {workflow_id}:{stage_id}"
        )


COMMAND_SPAWN_TOKENS = {
    "explain.md": ["gpd-explainer", "gpd-bibliographer"],
    "debug.md": ["gpd-debugger"],
    "plan-phase.md": ["gpd-planner"],
    "quick.md": ["gpd-planner", "gpd-executor"],
}

WORKFLOW_SPAWN_TOKENS = {
    "derive-equation.md": ["gpd-check-proof"],
    "explain.md": ["gpd-explainer", "gpd-bibliographer"],
    "plan-phase.md": ["gpd-phase-researcher", "gpd-planner", "gpd-plan-checker"],
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
        "Public production boundary: public writable production agent specialized for discrepancy investigation and bounded repair work.",
        "On demand only: shared protocols, verification core, physics subfields, agent infrastructure, and cross-project patterns.",
        "Keep work in `gpd-debugger` while the task is root-cause isolation, validation, or a bounded repair tied to that investigation.",
        'Do not update `session_status` to "diagnosed" in `GPD/debug/{slug}.md`; that field belongs to verification artifacts.',
        "goal: find_root_cause_only",
        "goal: find_and_correct",
    ],
    "gpd-executor.md": [
        "references/shared/shared-protocols.md",
        "references/shared/reward-hacking-self-check.md",
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
        "references/shared/reward-hacking-self-check.md",
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
        "references/shared/reward-hacking-self-check.md",
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
    if path.parent == WORKFLOWS_DIR and path.stem in STAGED_WORKFLOW_AUTHORITY_NAMES:
        content = _workflow_authority_text(path.stem)
    else:
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


def _normalized_prompt_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _assert_prompt_concepts(
    text: str,
    concepts: dict[str, tuple[str, ...]],
    *,
    context: str,
) -> None:
    _assert_semantic_concepts(text, concepts, context=context)


def _assert_ordered_prompt_fragments(text: str, fragments: tuple[str, ...], *, context: str) -> None:
    normalized = _normalized_prompt_text(text)
    position = -1
    for fragment in fragments:
        next_position = normalized.find(_normalized_prompt_text(fragment), position + 1)
        assert next_position != -1, f"{context} missing ordered fragment after {position}: {fragment}"
        position = next_position


def _plan_with_contract_text() -> str:
    return (CONTRACT_BASELINE_FIXTURES / "plan_with_contract.md").read_text(encoding="utf-8")


def test_planner_templates_exist():
    planner_prompt = TEMPLATES_DIR / "planner-subagent-prompt.md"
    phase_prompt = TEMPLATES_DIR / "phase-prompt.md"

    assert planner_prompt.exists()
    assert phase_prompt.exists()
    planner_text = planner_prompt.read_text(encoding="utf-8")
    phase_text = phase_prompt.read_text(encoding="utf-8")
    # fmt: off
    _m(planner_text, "planner template machine markers", "template_version: 1", "<planning_context>")
    _m(phase_text, "phase prompt schema markers", "template_version: 1", "contract:", "acceptance_tests:", "uncertainty_markers:")
    # fmt: on


def test_referee_latex_template_exists() -> None:
    referee_template = TEMPLATES_DIR / "paper" / "referee-report.tex"
    assert referee_template.exists()
    content = referee_template.read_text(encoding="utf-8")
    _mf(content, "template_version: 1", "\\RecommendationBadge", context="referee report recommendation badge")


def test_shared_protocols_require_permission_before_dependency_installs() -> None:
    shared = (REFERENCES_DIR / "shared" / "shared-protocols.md").read_text(encoding="utf-8")
    checkpoints = (REFERENCES_DIR / "orchestration" / "checkpoints.md").read_text(encoding="utf-8")
    verifier_raw = (AGENTS_DIR / "gpd-verifier.md").read_text(encoding="utf-8")
    verifier = expand_at_includes(verifier_raw, REPO_ROOT / "src/gpd", "/runtime/")
    planner = (AGENTS_DIR / "gpd-planner.md").read_text(encoding="utf-8")
    planner_execution = (REFERENCES_DIR / "planning" / "planner-execution-procedure.md").read_text(encoding="utf-8")

    _sf(
        shared,
        "NEVER install dependencies silently",
        "Ask the user before any install attempt",
        "BasicTeX",
        context="shared protocols dependency install permission gate",
    )
    # fmt: off
    _f(checkpoints, "checkpoint dependency install stale wording", "Never install TeX automatically.", "install silently")
    # fmt: on
    _ff(
        verifier_raw,
        "## Data Boundary",
        "## GPD CLI Commit Protocol",
        "@{GPD_INSTALL_DIR}/references/orchestration/agent-infrastructure.md",
        context="verifier raw prompt dependency install include boundary",
    )
    # fmt: off
    _s(verifier_raw, "verifier dependency install permission gate", "Ask the user before any install attempt", "permission-gated")
    _s(verifier.lower(), "expanded verifier dependency install permission gate", "ask the user before any install attempt")
    _s(planner + planner_execution, "planner dependency install permission gate", "permission-gated")
    # fmt: on


def test_agent_infrastructure_requires_concrete_next_actions_and_continuation_block() -> None:
    infra = (REFERENCES_DIR / "orchestration" / "agent-infrastructure.md").read_text(encoding="utf-8")

    _mf(
        infra,
        "Prefer copy-pasteable GPD commands",
        "references/orchestration/continuation-format.md",
        "## > Next Up",
        context="agent infrastructure next actions and continuation block",
    )


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
        _mf(writer_text, lightweight, context=f"paper writer lightweight reference pack {path}")
        _ff(writer_text, eager, context=f"paper writer eager reference pack {path}")


def test_paper_writer_keeps_cookbook_material_lazy_loaded() -> None:
    writer_text = (AGENTS_DIR / "gpd-paper-writer.md").read_text(encoding="utf-8")
    cookbook = (REFERENCES_DIR / "publication" / "paper-writer-cookbook.md").read_text(encoding="utf-8")

    _mf(writer_text, "<writing_reference_packs>", context="paper writer lightweight reference pack marker")
    _ff(
        writer_text,
        "<figure_design>",
        "<supplemental_material>",
        "Journal-Specific Figure Requirements",
        context="paper writer lazy-loaded cookbook sections",
    )
    _mf(
        cookbook,
        "Abstract And Section Shape",
        "Equation And Figure Details",
        "Supplemental Material Placement",
        context="paper writer cookbook lazy-loaded headings",
    )


def test_reward_hacking_self_check_reference_exists_and_is_wired() -> None:
    """The reward-hacking integrity gate is required by RES-904.

    The spec must exist as a shared reference, be loaded by the agents that
    finalize content (paper-writer, executor, referee), and be invoked as a
    workflow step in write-paper before pre_submission_review.
    """

    spec_path = REFERENCES_DIR / "shared" / "reward-hacking-self-check.md"
    assert spec_path.exists(), "reward-hacking-self-check.md missing"
    spec_text = spec_path.read_text(encoding="utf-8")

    # The spec must define the five-item gate and the four scientific-writing rules.
    for fragment in (
        "Literal vs. spirit",
        "Cheap wins and loopholes",
        "Adversarial self-review",
        "Uncertainty disclosure",
        "Revise or refuse",
        "S1. Speculative pathways are not established feasibility",
        "S2. Citation confidence threshold",
        "S3. Distinguish analytic, numerical, and experimental evidence",
        "S4. Confidence-to-language mapping",
    ):
        assert fragment in spec_text, f"reward-hacking spec missing fragment: {fragment}"

    # Agents that finalize content must reference the gate.
    for agent_name in ("gpd-paper-writer.md", "gpd-executor.md", "gpd-referee.md"):
        agent_text = (AGENTS_DIR / agent_name).read_text(encoding="utf-8")
        assert "references/shared/reward-hacking-self-check.md" in agent_text, (
            f"{agent_name} does not reference the reward-hacking self-check"
        )

    # Paper-writer, executor, and referee must declare the gate is required before completion.
    paper_writer = (AGENTS_DIR / "gpd-paper-writer.md").read_text(encoding="utf-8")
    executor = (AGENTS_DIR / "gpd-executor.md").read_text(encoding="utf-8")
    referee = (AGENTS_DIR / "gpd-referee.md").read_text(encoding="utf-8")
    for surface in (paper_writer, executor, referee):
        assert "<integrity_gate>" in surface
        assert "integrity_gate:" in surface
        assert "items_failed" in surface

    # The write-paper workflow must run the integrity gate before pre_submission_review.
    # The workflow has been split into stage authorities; the integrity gate lives in the
    # publication-review-finalization stage authority (the same stage that owns
    # pre_submission_review).
    publication_stage = (
        WORKFLOWS_DIR / "write-paper" / "publication-review-finalization.md"
    ).read_text(encoding="utf-8")
    assert "<reward_hacking_integrity_gate>" in publication_stage
    gate_idx = publication_stage.index("<reward_hacking_integrity_gate>")
    review_idx = publication_stage.index("<pre_submission_review>")
    assert gate_idx < review_idx, (
        "reward_hacking_integrity_gate must run before pre_submission_review"
    )
    assert "INTEGRITY-GATE.json" in publication_stage
    assert "overall_passed" in publication_stage


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
        _mf(bibliographer_text, lightweight, context=f"bibliographer lightweight reference pack {path}")
        _ff(bibliographer_text, eager, context=f"bibliographer eager reference pack {path}")


def test_continuation_format_scopes_clear_to_resolved_runtime_followups() -> None:
    continuation = (REFERENCES_DIR / "orchestration" / "continuation-format.md").read_text(encoding="utf-8")

    assert_runtime_reset_rediscovery_contract(continuation)
    _sf(
        continuation,
        "presentation layer only",
        "Start a fresh context window",
        "next command",
        "project rediscovery",
        context="continuation format runtime followups",
    )
    _f(continuation, "continuation format stale clear recovery wording", "/clear")


def test_plan_phase_applies_planner_roadmap_updates_in_orchestrator() -> None:
    plan_phase = _workflow_authority_text("plan-phase")

    _sf(
        plan_phase,
        "gpd_return.roadmap_updates",
        "planner returns",
        "roadmap edits",
        "orchestrator applies",
        "GPD/ROADMAP.md",
        "fresh `*-PLAN.md` artifacts",
        context="plan-phase roadmap update orchestration",
    )


def test_plan_phase_uses_manifest_owned_staged_init_access() -> None:
    plan_phase = _workflow_authority_text("plan-phase")
    manifest = load_workflow_stage_manifest("plan-phase")

    _assert_workflow_calls_staged_init_for_manifest_stages("plan-phase", plan_phase)
    _f(plan_phase, "plan-phase staged init manifest access", "bind_plan_phase_init")
    assert all(
        "project_contract_gate" in manifest.stage(stage_id).required_init_fields
        for stage_id in ("phase_bootstrap", "checker_revision")
    )
    _assert_prompt_concepts(
        plan_phase,
        {
            "manifest owns active field access": (
                "Stage authorities and the manifest own required fields",
                "later stage loading is manifest-owned",
            ),
        },
        context="plan-phase staged init manifest access",
    )
    _mf(
        plan_phase,
        'gpd --raw init plan-phase "$PHASE" --stage planner_authoring',
        'gpd --raw init plan-phase "$PHASE" --stage checker_revision',
        context="plan-phase staged init manifest access",
    )


def test_executor_completion_examples_use_command_based_next_actions() -> None:
    completion = (REFERENCES_DIR / "execution" / "executor-completion.md").read_text(encoding="utf-8")

    _mf(
        completion,
        '"gpd:execute-phase {phase}"',
        '"gpd:show-phase {phase}"',
        "gpd state validate",
        "gpd:sync-state",
        context="executor completion command based next actions",
    )
    _ff(completion, "file_edit tool", context="executor completion command based next actions")


def test_referee_workflow_mentions_optional_pdf_compile_and_missing_tex_prompt() -> None:
    referee = (AGENTS_DIR / "gpd-referee.md").read_text(encoding="utf-8")
    peer_review = _workflow_authority_text("peer-review")

    _sf(
        referee,
        "compile",
        "referee-report `.tex`",
        "matching `.pdf`",
        "Do NOT install TeX yourself",
        context="referee optional pdf compile guidance",
    )
    _sf(
        peer_review,
        "Continue now",
        "${PUBLICATION_ROOT}/REFEREE-REPORT{round_suffix}.md",
        "${PUBLICATION_ROOT}/REFEREE-REPORT{round_suffix}.tex",
        context="peer-review missing tex continuation",
    )
    _s(peer_review, "peer-review optional pdf compile guidance", "authorize", "install TeX")


def test_executor_prompt_defaults_to_return_only_shared_state_updates() -> None:
    executor = (AGENTS_DIR / "gpd-executor.md").read_text(encoding="utf-8")
    executor_completion = (REFERENCES_DIR / "execution" / "executor-completion.md").read_text(encoding="utf-8")

    _sf(
        executor,
        "return shared-state updates to the orchestrator",
        "instead of writing `STATE.md` directly",
        context="executor return-only shared state updates",
    )
    _f(
        executor,
        "executor stale direct shared-state writing role",
        "Your job: Execute the research plan completely, checkpoint each step, create SUMMARY.md, update STATE.md.",
    )
    # fmt: off
    _m(executor, "executor return fields", "state_updates", "contract_updates", "decisions", "blockers", "continuation_update")
    # fmt: on
    _s(executor, "executor child return timestamp ownership", "omit `recorded_at`", "`recorded_by`", "child returns")
    _f(executor, "executor child timestamp ownership", 'recorded_at: "{timestamp}"', 'recorded_by: "gpd-executor"')
    _mf(
        executor_completion,
        "state_updates:",
        "contract_updates:",
        "decisions:",
        "blockers:",
        "continuation_update:",
        context="executor completion return fields",
    )
    _sf(
        executor_completion,
        "omit `recorded_at`",
        "`recorded_by`",
        "child returns",
        context="executor completion child return timestamp ownership",
    )
    _f(
        executor_completion,
        "executor completion child timestamp ownership",
        'recorded_at: "{timestamp}"',
        'recorded_by: "gpd-executor"',
    )


def test_return_only_planner_and_executor_do_not_commit_shared_state_files_by_default() -> None:
    planner = (AGENTS_DIR / "gpd-planner.md").read_text(encoding="utf-8")
    planner_execution = (REFERENCES_DIR / "planning" / "planner-execution-procedure.md").read_text(encoding="utf-8")
    executor = (AGENTS_DIR / "gpd-executor.md").read_text(encoding="utf-8")
    executor_completion = (REFERENCES_DIR / "execution" / "executor-completion.md").read_text(encoding="utf-8")
    planner_commit_blocks = re.findall(r"```bash\n(gpd commit[\s\S]*?)\n```", planner + "\n" + planner_execution)
    executor_commit_blocks = re.findall(r"```bash\n(gpd commit[\s\S]*?)\n```", executor + "\n" + executor_completion)

    assert planner_commit_blocks
    assert executor_commit_blocks
    assert all("GPD/STATE.md" not in block and "GPD/ROADMAP.md" not in block for block in planner_commit_blocks)
    assert all("GPD/STATE.md" not in block for block in executor_commit_blocks)
    _f(
        planner,
        "planner return-only shared-state authority",
        "Authority: use the frontmatter-derived Agent Requirements block",
    )
    _mf(
        registry.get_agent("gpd-planner").system_prompt,
        "shared_state_authority: return_only",
        context="planner shared state authority",
    )
    _mf(planner, "roadmap_updates", context="planner roadmap update return field")
    _f(
        executor,
        "executor return-only shared-state authority",
        "Authority: use the frontmatter-derived Agent Requirements block",
    )
    _mf(
        registry.get_agent("gpd-executor").system_prompt,
        "shared_state_authority: return_only",
        context="executor shared state authority",
    )


def test_read_only_plan_checker_and_research_mapper_tool_policy_are_contract_aligned() -> None:
    checker = (AGENTS_DIR / "gpd-plan-checker.md").read_text(encoding="utf-8")
    mapper = (AGENTS_DIR / "gpd-research-mapper.md").read_text(encoding="utf-8")

    _ff(checker, "Return changed paths in `gpd_return.files_written`", context="plan checker read-only policy")
    _mf(checker, "files_written: []", "artifact_write_authority: read_only", context="plan checker read-only policy")
    _m(
        mapper,
        "research mapper status-only web tools",
        "All tools declared in frontmatter are available to this agent.",
    )
    _s(mapper, "research mapper status-only web tools", "Reserve `web_search`", "`web_fetch`", "`status` focus")
    _f(mapper, "research mapper status-only web tools", "`status`: the same tools plus `web_search` and `web_fetch`")


def test_referee_prompt_no_longer_claims_read_only_artifact_policy() -> None:
    referee = (AGENTS_DIR / "gpd-referee.md").read_text(encoding="utf-8")

    _s(
        referee,
        "referee writable review artifact policy",
        "Stage 6 owns only the allowlisted review artifacts",
        "changed Stage 6 outputs",
        "return file list",
    )
    _f(referee, "referee writable review artifact policy", "No files modified (read-only agent)")


def test_prompt_sources_do_not_use_stale_agent_install_paths():
    files = [
        REPO_ROOT / "src/gpd/specs/references/orchestration/agent-delegation.md",
        REPO_ROOT / "src/gpd/specs/templates/continuation-prompt.md",
    ]

    for path in files:
        _ff(path.read_text(encoding="utf-8"), "{GPD_INSTALL_DIR}/agents/", context=str(path.relative_to(REPO_ROOT)))


def test_prompt_sources_use_real_pattern_library_description():
    verifier_files = [REPO_ROOT / "src/gpd/agents/gpd-verifier.md"]

    for path in verifier_files:
        content = path.read_text(encoding="utf-8")
        _ff(content, "{GPD_INSTALL_DIR}/learned-patterns/", context=str(path.relative_to(REPO_ROOT)))
        _mf(content, "GPD_PATTERNS_ROOT", context=str(path.relative_to(REPO_ROOT)))

    learned_pattern_template = (TEMPLATES_DIR / "learned-pattern.md").read_text(encoding="utf-8")
    _m(learned_pattern_template, "learned pattern template domain library path", "learned-patterns/patterns-by-domain/")


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
        content = command_path.read_text(encoding="utf-8")
        expected_standalone = f"@{{GPD_INSTALL_DIR}}/workflows/{command_path.stem}.md"
        expected_inline = f"{{GPD_INSTALL_DIR}}/workflows/{command_path.stem}.md"
        if expected_standalone in content or expected_inline in content:
            continue
        manifest_path = WORKFLOWS_DIR / f"{command_path.stem}-stage-manifest.json"
        if manifest_path.is_file():
            manifest = validate_workflow_stage_manifest_payload(
                json.loads(manifest_path.read_text(encoding="utf-8")),
                expected_workflow_id=command_path.stem,
            )
            first_stage_include = f"@{{GPD_INSTALL_DIR}}/{manifest.stages[0].mode_paths[0]}"
            if first_stage_include in content:
                continue
        raise AssertionError(command_path)


def test_commands_are_workflow_backed_or_explicitly_exempt() -> None:
    workflow_stems = {path.stem for path in WORKFLOWS_DIR.glob("*.md")}
    command_stems = {path.stem for path in COMMANDS_DIR.glob("*.md")}

    exempt_commands = registry.LOCAL_CLI_BRIDGE_WORKFLOW_EXEMPT_COMMANDS
    assert command_stems - workflow_stems == exempt_commands

    for command_stem in sorted(exempt_commands):
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
        agent = registry.get_agent(Path(agent_name).stem)
        source_and_generated = f"{(AGENTS_DIR / agent_name).read_text(encoding='utf-8')}\n{agent.system_prompt}"
        missing = [token for token in reference_tokens if token not in source_and_generated]
        assert missing == [], f"src/gpd/agents/{agent_name} missing {missing}"


def test_consistency_checker_prompt_keeps_the_canonical_contract_and_stays_least_privileged() -> None:
    source = (AGENTS_DIR / "gpd-consistency-checker.md").read_text(encoding="utf-8")

    _mf(
        source,
        "one-shot handoff",
        "status: completed",
        "files_written:\n    - GPD/phases/03-conventions/CONSISTENCY-CHECK.md",
        "GPD/CONSISTENCY-CHECK.md",
        context="consistency checker handoff contract",
    )
    _ff(
        source,
        "@{GPD_INSTALL_DIR}",
        "Authority: use the frontmatter-derived Agent Requirements block",
        context="consistency checker least-privileged source",
    )
    assert "shared_state_authority: return_only" in registry.get_agent("gpd-consistency-checker").system_prompt
    _sf(
        source,
        "Do not claim ownership",
        "code fixes",
        "commits",
        "convention-authoring",
        "pattern-library updates",
        context="consistency checker least-privileged scope",
    )
    _f(source, "consistency checker stale template authoring", "Create it from the template")
    _ff(
        source,
        "gpd pattern add",
        "Step 0.5",
        "CONVENTIONS.md does not exist",
        context="consistency checker stale template authoring",
    )


def test_review_commands_expose_typed_contracts() -> None:
    write_paper = registry.get_command("gpd:write-paper")
    peer_review = registry.get_command("peer-review")
    arxiv_submission = registry.get_command("arxiv-submission")
    verify_work = registry.get_command("verify-work")
    respond_to_referees = registry.get_command("respond-to-referees")
    write_paper_contract = write_paper.review_contract
    peer_review_contract = peer_review.review_contract
    arxiv_contract = arxiv_submission.review_contract
    verify_work_contract = verify_work.review_contract
    respond_contract = respond_to_referees.review_contract

    assert write_paper_contract is not None
    assert write_paper_contract.review_mode == "publication"
    _assert_exact_items(
        write_paper_contract.required_outputs,
        "${PAPER_DIR}/ARTIFACT-MANIFEST.json",
        "${PAPER_DIR}/BIBLIOGRAPHY-AUDIT.json",
        "${PAPER_DIR}/reproducibility-manifest.json",
        "GPD/review/REVIEW-LEDGER{round_suffix}.json",
        "GPD/review/REFEREE-DECISION{round_suffix}.json",
        "GPD/REFEREE-REPORT{round_suffix}.md",
        "GPD/REFEREE-REPORT{round_suffix}.tex",
        context="write-paper required publication outputs",
    )
    assert write_paper_contract.required_evidence == [
        "project-backed lane: research artifacts and verification reports",
        "external-authoring lane: explicit `--intake` manifest with claim-to-evidence bindings",
        "bibliography / citation-source input",
    ]
    _assert_exact_items(
        write_paper_contract.preflight_checks,
        "command_context",
        "verification_reports",
        "manuscript",
        "artifact_manifest",
        "bibliography_audit",
        "bibliography_audit_clean",
        "reproducibility_manifest",
        "reproducibility_ready",
        "manuscript_proof_review",
        context="write-paper publication preflight checks",
    )
    assert write_paper_contract.stage_artifacts == []
    assert _review_requirement_rows(write_paper_contract.conditional_requirements, ("when", "required_outputs")) == [
        {
            "when": "theorem-bearing claims are present",
            "required_outputs": ["GPD/review/PROOF-REDTEAM{round_suffix}.md"],
        }
    ]

    assert peer_review_contract is not None
    assert peer_review_contract.review_mode == "publication"
    _assert_exact_items(
        peer_review_contract.required_outputs,
        "${PUBLICATION_ROOT}/REFEREE-REPORT{round_suffix}.md",
        "${PUBLICATION_ROOT}/REFEREE-REPORT{round_suffix}.tex",
        "${REVIEW_ROOT}/CLAIMS{round_suffix}.json",
        "${REVIEW_ROOT}/STAGE-interestingness{round_suffix}.json",
        "${REVIEW_ROOT}/REFEREE-DECISION{round_suffix}.json",
        context="peer-review required publication outputs",
    )
    assert peer_review_contract.required_evidence == ["existing manuscript or explicit external artifact target"]
    assert peer_review_contract.blocking_conditions == [
        "missing manuscript or explicit external artifact target",
        "degraded review integrity",
        "unsupported physical significance claims",
        "collapsed novelty or venue fit",
    ]
    assert peer_review_contract.preflight_checks == [
        "command_context",
        "manuscript",
        "manuscript_proof_review",
    ]
    assert peer_review_contract.stage_artifacts == [
        "${REVIEW_ROOT}/CLAIMS{round_suffix}.json",
        "${REVIEW_ROOT}/STAGE-reader{round_suffix}.json",
        "${REVIEW_ROOT}/STAGE-literature{round_suffix}.json",
        "${REVIEW_ROOT}/STAGE-math{round_suffix}.json",
        "${REVIEW_ROOT}/STAGE-physics{round_suffix}.json",
        "${REVIEW_ROOT}/STAGE-interestingness{round_suffix}.json",
        "${REVIEW_ROOT}/REVIEW-LEDGER{round_suffix}.json",
        "${REVIEW_ROOT}/REFEREE-DECISION{round_suffix}.json",
    ]
    assert (
        _review_requirement_rows(
            peer_review_contract.conditional_requirements, tuple(PEER_REVIEW_CONDITIONAL_REQUIREMENTS[0])
        )
        == PEER_REVIEW_CONDITIONAL_REQUIREMENTS
    )

    assert arxiv_contract is not None
    assert arxiv_contract.review_mode == "publication"
    _assert_exact_items(
        arxiv_contract.preflight_checks,
        "command_context",
        "artifact_manifest",
        "bibliography_audit",
        "bibliography_audit_clean",
        "publication_blockers",
        "manuscript_proof_review",
        context="arxiv publication preflight checks",
    )
    assert (
        _review_requirement_rows(arxiv_contract.conditional_requirements, tuple(ARXIV_CONDITIONAL_REQUIREMENTS[0]))
        == ARXIV_CONDITIONAL_REQUIREMENTS
    )

    assert verify_work_contract is not None
    assert verify_work_contract.required_state == "phase_executed"
    _assert_exact_items(
        verify_work_contract.preflight_checks,
        "command_context",
        "phase_lookup",
        "phase_artifacts",
        "phase_summaries",
        "phase_proof_review",
        context="verify-work phase preflight checks",
    )

    assert respond_contract is not None
    _assert_exact_items(
        respond_contract.required_outputs,
        "GPD/review/REFEREE_RESPONSE{round_suffix}.md",
        "GPD/AUTHOR-RESPONSE{round_suffix}.md",
        context="respond-to-referees required outputs",
    )
    _assert_exact_items(
        respond_contract.preflight_checks,
        "command_context",
        context="respond-to-referees preflight checks",
    )
    assert respond_contract.required_evidence == [
        "existing manuscript",
        "referee report source when provided as a path",
    ]
    _assert_exact_items(
        registry.list_review_commands(),
        "gpd:peer-review",
        "gpd:write-paper",
        "gpd:respond-to-referees",
        "gpd:verify-work",
        context="review command registry",
    )


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
    assert peer_review.preflight_checks == [
        "command_context",
        "manuscript",
        "manuscript_proof_review",
    ]
    _assert_exact_items(peer_review.preflight_checks, "manuscript_proof_review", context="peer-review preflight checks")
    assert (
        _review_requirement_rows(peer_review.conditional_requirements, tuple(PEER_REVIEW_CONDITIONAL_REQUIREMENTS[0]))
        == PEER_REVIEW_CONDITIONAL_REQUIREMENTS
    )
    assert (
        _review_requirement_rows(arxiv_submission.conditional_requirements, tuple(ARXIV_CONDITIONAL_REQUIREMENTS[0]))
        == ARXIV_CONDITIONAL_REQUIREMENTS
    )
    _assert_exact_items(
        arxiv_submission.preflight_checks,
        "manuscript_proof_review",
        context="arxiv submission preflight checks",
    )


def test_representative_commands_expose_expected_context_modes() -> None:
    assert registry.get_command("help").context_mode == "global"
    assert registry.get_command("health").context_mode == "projectless"
    assert registry.get_command("start").context_mode == "projectless"
    start_description = registry.get_command("start").description
    assert "first" in start_description.lower()
    _s(start_description, "start command projectless context description", "route", "real workflow")
    _f(start_description, "start command projectless context description", "without taking action")
    assert registry.get_command("tour").context_mode == "projectless"
    tour_description = registry.get_command("tour").description
    assert "guided beginner walkthrough" in tour_description
    assert "core GPD commands" in tour_description
    assert "without taking action" in tour_description
    _f(tour_description, "tour command projectless context description", "route into the real workflow")
    assert registry.get_command("compare-results").context_mode == "project-aware"
    assert registry.get_command("map-research").context_mode == "projectless"
    assert registry.get_command("slides").context_mode == "projectless"
    assert registry.get_command("discover").context_mode == "project-aware"
    assert registry.get_command("explain").context_mode == "project-aware"
    assert registry.get_command("parameter-sweep").context_mode == "project-aware"
    assert registry.get_command("suggest-next").context_mode == "projectless"
    assert registry.get_command("peer-review").context_mode == "project-aware"


def test_readme_command_context_taxonomy_surfaces_global_mode_and_project_aware_publication_entrypoints() -> None:
    readme = README_PATH.read_text(encoding="utf-8")
    command_context = readme.split("### Command Context", 1)[1].split("The full in-runtime reference", 1)[0]

    assert "| `Global` |" in command_context
    assert "| `Projectless` |" in command_context
    assert "| `Project-aware` |" in command_context
    assert "| `Project-required` |" in command_context
    project_aware_line = next(line for line in command_context.splitlines() if line.startswith("| `Project-aware` |"))
    project_required_line = next(
        line for line in command_context.splitlines() if line.startswith("| `Project-required` |")
    )
    assert "explicit current-workspace inputs" in project_aware_line
    for command_name in (
        "compare-experiment",
        "compare-results",
        "discover",
        "digest-knowledge",
        "explain",
        "parameter-sweep",
        "review-knowledge",
        "literature-review",
        "peer-review",
        "write-paper --intake intake/write-paper-authoring-input.json",
    ):
        assert command_name in project_aware_line
    _sf(
        command_context,
        "Project-aware commands",
        "current workspace",
        "relaxed technical-analysis lane",
        context="README command context taxonomy",
    )
    for command_name in (
        "derive-equation",
        "dimensional-analysis",
        "limiting-cases",
        "numerical-convergence",
        "parameter-sweep",
        "sensitivity-analysis",
    ):
        assert command_name in command_context
    assert "GPD/analysis/" in command_context
    assert "GPD/sweeps/" in command_context
    _sf(
        command_context,
        "`graph`",
        "`error-propagation`",
        "not part of this relaxed current-workspace lane",
        context="README relaxed technical-analysis lane exclusions",
    )
    assert "gpd:peer-review" not in project_required_line
    assert "gpd:write-paper" not in project_required_line
    assert (
        "Passing a manuscript path to a project-required command such as `gpd:peer-review paper/` selects the manuscript target, but does not bypass project initialization."
        not in command_context
    )


def test_readme_and_help_workflow_surface_publication_lane_boundary_without_claiming_root_migration() -> None:
    readme = README_PATH.read_text(encoding="utf-8")
    help_workflow = (WORKFLOWS_DIR / "help.md").read_text(encoding="utf-8")

    assert_publication_lane_boundary_contract(readme)
    assert_publication_lane_boundary_contract(help_workflow)


def test_slides_workflow_references_templates_and_existing_output_policy() -> None:
    workflow = (WORKFLOWS_DIR / "slides.md").read_text(encoding="utf-8")

    _assert_slides_public_label_local_preflight_guidance(workflow, shared_source=True)
    _mf(
        workflow,
        "{GPD_INSTALL_DIR}/templates/slides/presentation-brief.md",
        "{GPD_INSTALL_DIR}/templates/slides/outline.md",
        "{GPD_INSTALL_DIR}/templates/slides/slides.md",
        "{GPD_INSTALL_DIR}/templates/slides/speaker-notes.md",
        "{GPD_INSTALL_DIR}/templates/slides/main.tex",
        "1. Refresh",
        "2. Update",
        "3. Skip",
        "main.nav",
        "main.snm",
        context="slides template and cleanup machine tokens",
    )
    assert "source-bound skeleton" in workflow
    assert "selected_publication_root" not in workflow
    assert "selected_review_root" not in workflow


def test_slides_prompt_covers_cleanup_non_git_and_thin_source_boundaries() -> None:
    workflow = (WORKFLOWS_DIR / "slides.md").read_text(encoding="utf-8")

    _assert_slides_public_label_local_preflight_guidance(workflow, shared_source=True)
    _sf(
        workflow,
        "workspace is not a git checkout",
        "runtime-native deletion",
        "source-bound skeleton",
        context="slides cleanup non-git and source boundaries",
    )
    _m(workflow, "slides cleanup known aux files", "main.nav", "main.snm")


def test_publication_workflows_surface_no_write_stop_contracts_from_committed_sources() -> None:
    peer_review = _workflow_authority_text("peer-review")
    arxiv = _workflow_authority_text("arxiv-submission")
    slides = (WORKFLOWS_DIR / "slides.md").read_text(encoding="utf-8")

    _assert_contains_fragments(
        peer_review,
        "STOP at `manuscript_required`",
        "`next_step: none`",
    )
    _assert_contains_fragments(
        arxiv,
        "command_execution_state:",
        "blocked_before_write",
        "`response_gate`",
        "`review_state: stale`",
        "`response_state: requires_fresh_review`",
    )
    _assert_contains_fragments(
        slides,
        "`checkpoint: none`",
        "`next_step: none`",
        "`review_state: not_required`",
    )


def test_export_workflow_keeps_outputs_under_exports_without_satisfying_publication_gates() -> None:
    workflow = (WORKFLOWS_DIR / "export.md").read_text(encoding="utf-8")

    _sf(
        workflow,
        "`exports/`",
        "only durable write root",
        "Do not write generated export files",
        "GPD/publication/",
        "GPD/review/",
        "must not satisfy",
        "publication",
        "peer-review",
        "arXiv-package",
        "slides gates",
        context="export workflow durable root boundary",
    )


def test_representative_prompts_use_centralized_command_context_preflight() -> None:
    expected = {
        COMMANDS_DIR / "compare-experiment.md": "gpd --raw validate command-context compare-experiment",
        COMMANDS_DIR / "compare-results.md": "gpd --raw validate command-context compare-results",
        COMMANDS_DIR / "derive-equation.md": "gpd --raw validate command-context derive-equation",
        COMMANDS_DIR / "dimensional-analysis.md": "gpd --raw validate command-context dimensional-analysis",
        COMMANDS_DIR / "explain.md": "gpd --raw validate command-context explain",
        COMMANDS_DIR / "limiting-cases.md": "gpd --raw validate command-context limiting-cases",
        COMMANDS_DIR / "literature-review.md": "gpd --raw validate command-context literature-review",
        COMMANDS_DIR / "numerical-convergence.md": "gpd --raw validate command-context numerical-convergence",
        COMMANDS_DIR / "parameter-sweep.md": "gpd --raw validate command-context parameter-sweep",
        COMMANDS_DIR / "sensitivity-analysis.md": "gpd --raw validate command-context sensitivity-analysis",
        WORKFLOWS_DIR / "peer-review.md": "gpd --raw validate command-context peer-review",
        WORKFLOWS_DIR / "progress.md": "gpd --raw validate command-context progress",
    }

    for path, token in expected.items():
        text = _workflow_authority_text(path.stem) if path.parent == WORKFLOWS_DIR else path.read_text(encoding="utf-8")
        assert token in text, path


def test_current_workspace_project_aware_workflows_disable_recent_project_reentry() -> None:
    compare_experiment = (WORKFLOWS_DIR / "compare-experiment.md").read_text(encoding="utf-8")
    compare_results = (WORKFLOWS_DIR / "compare-results.md").read_text(encoding="utf-8")
    digest_knowledge = (WORKFLOWS_DIR / "digest-knowledge.md").read_text(encoding="utf-8")
    explain = (WORKFLOWS_DIR / "explain.md").read_text(encoding="utf-8")
    review_knowledge = (WORKFLOWS_DIR / "review-knowledge.md").read_text(encoding="utf-8")

    assert "INIT=$(gpd --raw init progress --include state,protocols --no-project-reentry)" in compare_experiment
    assert "INIT=$(gpd --raw init progress --include state --no-project-reentry)" in compare_results
    assert "INIT=$(gpd --raw init progress --include state,config,references --no-project-reentry)" in digest_knowledge
    assert "INIT=$(gpd --raw init progress --include project,state,roadmap,config --no-project-reentry)" in explain
    assert "INIT=$(gpd --raw init progress --include state,config --no-project-reentry)" in review_knowledge


def test_compare_commands_expose_typed_policy_for_interactive_intake_and_gpd_outputs() -> None:
    compare_results = registry.get_command("compare-results")
    compare_experiment = registry.get_command("compare-experiment")

    for command, resolution_mode, explicit_input in (
        (
            compare_results,
            "explicit_or_interactive_internal_comparison",
            "comparison target, phase, artifact path, or source-a vs source-b",
        ),
        (
            compare_experiment,
            "explicit_or_interactive_theory_data_comparison",
            "prediction, dataset path, phase identifier, or comparison target",
        ),
    ):
        assert command.command_policy is not None
        assert command.command_policy.schema_version == 1
        assert command.command_policy.subject_policy is not None
        assert command.command_policy.subject_policy.subject_kind == "comparison"
        assert command.command_policy.subject_policy.resolution_mode == resolution_mode
        assert command.command_policy.subject_policy.explicit_input_kinds == [explicit_input]
        assert command.command_policy.subject_policy.allow_external_subjects is True
        assert command.command_policy.subject_policy.allow_interactive_without_subject is True
        assert command.command_policy.supporting_context_policy is not None
        assert command.command_policy.supporting_context_policy.project_context_mode == "project-aware"
        assert command.command_policy.supporting_context_policy.project_reentry_mode == "disallowed"
        assert command.command_policy.output_policy is not None
        assert command.command_policy.output_policy.output_mode == "managed"
        assert command.command_policy.output_policy.managed_root_kind == "gpd_managed_durable"
        assert command.command_policy.output_policy.default_output_subtree == "GPD/comparisons"


def test_list_review_commands_contains_all_expected_commands() -> None:
    """Assert list_review_commands covers gpd:peer-review, gpd:write-paper,
    gpd:respond-to-referees, and gpd:verify-work without duplication."""
    review_cmds = registry.list_review_commands()
    expected = {"gpd:peer-review", "gpd:write-paper", "gpd:respond-to-referees", "gpd:verify-work"}
    assert expected <= set(review_cmds), f"Missing review commands: {expected - set(review_cmds)}"


def test_parameter_sweep_command_uses_project_aware_gpd_sweeps_output_policy() -> None:
    command = registry.get_command("parameter-sweep")

    assert command.context_mode == "project-aware"
    assert command.command_policy is not None
    assert command.command_policy.schema_version == 1
    assert command.command_policy.supporting_context_policy is not None
    assert command.command_policy.supporting_context_policy.project_context_mode == "project-aware"
    assert command.command_policy.supporting_context_policy.project_reentry_mode == "disallowed"
    assert command.command_policy.output_policy is not None
    assert command.command_policy.output_policy.output_mode == "managed"
    assert command.command_policy.output_policy.managed_root_kind == "gpd_managed_durable"
    assert command.command_policy.output_policy.default_output_subtree == "GPD/sweeps"


def test_list_review_commands_no_duplicates() -> None:
    """Each review command should appear exactly once."""
    review_cmds = registry.list_review_commands()
    assert len(review_cmds) == len(set(review_cmds))


def test_respond_to_referees_references_staged_review_artifacts() -> None:
    command_text = (COMMANDS_DIR / "respond-to-referees.md").read_text(encoding="utf-8")
    workflow_text = _workflow_authority_text("respond-to-referees")
    writer_text = (AGENTS_DIR / "gpd-paper-writer.md").read_text(encoding="utf-8")

    _pf(
        command_text,
        'argument-hint: "[--manuscript PATH] (--report PATH [--report PATH...] | paste)"',
        context="respond command public report source hint",
    )
    _m(
        command_text,
        "respond command first-stage include",
        "@{GPD_INSTALL_DIR}/workflows/respond-to-referees/bootstrap.md",
    )
    _ff(
        command_text,
        "@{GPD_INSTALL_DIR}/references/publication/publication-review-wrapper-guidance.md",
        context="respond command wrapper guidance no longer frontloaded",
    )
    _sf(
        command_text,
        "Referee report source",
        "$ARGUMENTS",
        "file path",
        "paste",
        "subject-owned publication root",
        "GPD/publication/{subject_slug}",
        context="respond command staged review artifact source",
    )
    _sf(
        workflow_text,
        "literal `paste` sentinel",
        "REVIEW-LEDGER*.json",
        "REFEREE-DECISION*.json",
        context="respond workflow staged review artifacts",
    )
    _mf(
        writer_text,
        "review_ledger_path",
        "referee_decision_path",
        "author_response_path",
        "referee_response_path",
        context="paper writer response path fields",
    )


def test_publication_review_round_detection_prompts_are_shell_safe_and_pair_response_artifacts() -> None:
    peer_review = _workflow_authority_text("peer-review")
    referee = (AGENTS_DIR / "gpd-referee.md").read_text(encoding="utf-8")
    respond = _workflow_authority_text("respond-to-referees")
    reliability = (REFERENCES_DIR / "publication" / "peer-review-reliability.md").read_text(encoding="utf-8")

    for content in (peer_review, referee):
        _ff(
            content,
            "ls GPD/REFEREE-REPORT*.md 2>/dev/null",
            "ls GPD/AUTHOR-RESPONSE*.md 2>/dev/null",
            context="publication review round shell-safe detection",
        )

    _f(referee, "referee shell-safe response artifact detection", "ls GPD/review/REFEREE_RESPONSE*.md 2>/dev/null")
    _ff(
        respond,
        "ls GPD/review/REFEREE_RESPONSE*.md 2>/dev/null",
        "ls GPD/review/REVIEW-LEDGER*.json 2>/dev/null",
        "ls GPD/review/REFEREE-DECISION*.json 2>/dev/null",
        context="respond shell-safe response artifact detection",
    )

    _mf(
        peer_review,
        "${PUBLICATION_ROOT}/REFEREE-REPORT{round_suffix}.md",
        "${PUBLICATION_ROOT}/AUTHOR-RESPONSE{round_suffix}.md",
        "${REVIEW_ROOT}/REFEREE_RESPONSE{round_suffix}.md",
        context="peer-review round-suffixed response artifacts",
    )
    _sf(
        peer_review,
        "Repair the target-bound response artifacts",
        "Do not require a response package",
        context="peer-review response package fail-closed policy",
    )

    _s(referee, "referee paired response package detection", "matching paired response package", "same round")
    assert re.search(
        r"If one response artifact is missing[\s\S]{0,140}stop fail-closed and report the incomplete response package",
        referee,
    )
    assert (
        "A completed review without that package stays valid for internal review, accept/no-change outcomes, "
        "and fresh clearance reruns" in reliability
    )
    assert (
        "`${selected_publication_root}/AUTHOR-RESPONSE{round_suffix}.md` plus "
        "`${selected_review_root}/REFEREE_RESPONSE{round_suffix}.md`" in reliability
    )

    assert re.search(r"\bfind\b[\s\S]{0,160}-name ['\"]REFEREE_RESPONSE\*\.md['\"]", respond)
    assert re.search(r"\bfind\b[\s\S]{0,160}-name ['\"]AUTHOR-RESPONSE\*\.md['\"]", respond)
    assert re.search(r"\bfind\b[\s\S]{0,160}-name ['\"]REVIEW-LEDGER\*\.json['\"]", respond)
    assert re.search(r"\bfind\b[\s\S]{0,160}-name ['\"]REFEREE-DECISION\*\.json['\"]", respond)


def test_review_workflows_keep_round_suffix_artifacts_visible_and_anchor_response_outputs() -> None:
    peer_review = (COMMANDS_DIR / "peer-review.md").read_text(encoding="utf-8")
    workflow = _workflow_authority_text("peer-review")
    respond = _workflow_authority_text("respond-to-referees")
    write_paper = _workflow_authority_text("write-paper")
    write_paper_expanded = expand_at_includes(write_paper, REPO_ROOT / "src" / "gpd", "/runtime/")
    panel = (REFERENCES_DIR / "publication" / "peer-review-panel.md").read_text(encoding="utf-8")

    _mf(
        peer_review,
        "${REVIEW_ROOT}/CLAIMS{round_suffix}.json",
        "${REVIEW_ROOT}/REVIEW-LEDGER{round_suffix}.json",
        "${REVIEW_ROOT}/REFEREE-DECISION{round_suffix}.json",
        context="peer-review round-suffixed review artifacts",
    )
    _m(workflow, "peer-review publication report artifact", "${PUBLICATION_ROOT}/REFEREE-REPORT{round_suffix}.md")
    _mf(
        panel,
        "${PUBLICATION_ROOT}/REFEREE-REPORT{round_suffix}.tex",
        "`manuscript_path` must be non-empty",
        context="peer-review panel round-suffixed artifacts",
    )
    _sf(
        panel,
        "Stage 1",
        "CLAIMS{round_suffix}.json",
        "ClaimIndex",
        "closed schema",
        "JSON `round` field",
        "sibling `CLAIMS{round_suffix}.json`",
        context="peer-review panel claim index contract",
    )
    _ff(
        panel,
        "Stage 1 `CLAIMS.json` must follow this compact `ClaimIndex` shape:",
        context="peer-review panel stale unsuffixed claim index contract",
    )

    _sf(
        respond,
        "resolved section file",
        "manuscript tree rooted at `${PAPER_DIR}`",
        "${PAPER_DIR}/BIBLIOGRAPHY-AUDIT.json",
        "optional manuscript-local response-letter",
        "${RESPONSE_REFEREE_PATH}",
        "${RESPONSE_AUTHOR_PATH}",
        "selected_publication_root",
        "selected_review_root",
        "Do not duplicate the pair",
        context="respond round-suffixed response outputs",
    )
    _m(respond, "respond response output templates", "templates/paper/author-response.md", "needs-calculation")

    _assert_write_paper_publication_review_authorities()
    _mf(
        write_paper_expanded,
        "REVIEW-LEDGER{round_suffix}.json",
        "REFEREE-DECISION{round_suffix}.json",
        "${selected_publication_root}/REFEREE-REPORT{round_suffix}.md",
        context="expanded write-paper round-suffixed response outputs",
    )


def test_publication_commands_accept_documented_manuscript_layouts() -> None:
    write_paper = (COMMANDS_DIR / "write-paper.md").read_text(encoding="utf-8")
    peer_review = (COMMANDS_DIR / "peer-review.md").read_text(encoding="utf-8")
    publication_modes = (REFERENCES_DIR / "publication" / "publication-pipeline-modes.md").read_text(encoding="utf-8")
    respond = (COMMANDS_DIR / "respond-to-referees.md").read_text(encoding="utf-8")
    arxiv = (COMMANDS_DIR / "arxiv-submission.md").read_text(encoding="utf-8")
    respond_command = registry.get_command("respond-to-referees")

    _m(
        write_paper,
        "write-paper documented manuscript layouts",
        "context_mode: project-aware",
        "--intake path/to/write-paper-authoring-input.json",
    )
    _sf(
        write_paper,
        "GPD-authored outputs",
        "GPD/publication/{subject_slug}",
        "intake/provenance",
        "Project-backed review/response/package outputs",
        context="write-paper documented manuscript layouts",
    )
    _m(
        peer_review,
        "peer-review documented manuscript layouts",
        "`paper/`, `manuscript/`, and `draft/`",
        "{GPD_INSTALL_DIR}/references/publication/publication-pipeline-modes.md",
    )
    _m(
        publication_modes,
        "publication modes documented manuscript layouts",
        "subject-owned publication root at `GPD/publication/{subject_slug}`",
    )
    _f(
        peer_review,
        "peer-review stale global publication layout",
        "current global `GPD/` / `GPD/review/` round-artifact layout",
    )
    assert respond_command.argument_hint == "[--manuscript PATH] (--report PATH [--report PATH...] | paste)"
    assert respond_command.command_policy is not None
    assert respond_command.command_policy.subject_policy is not None
    assert respond_command.command_policy.subject_policy.explicit_input_kinds == [
        "manuscript_path",
        "referee_report_path",
        "paste_referee_report",
    ]
    assert respond_command.command_policy.subject_policy.supported_roots == ["paper", "manuscript", "draft"]
    _m(respond, "respond external subject policy", "allow_external_subjects: true")
    _f(respond, "respond stale subject requirements key", "requires:")
    _sf(
        respond,
        "bounded continuation path",
        "not a full relocation",
        "manuscript-local publication artifacts",
        context="respond bounded publication continuation",
    )
    _m(
        arxiv,
        "arxiv documented manuscript layouts",
        'files: ["paper/*.tex", "manuscript/*.tex", "draft/*.tex", "GPD/publication/*/manuscript/*.tex"]',
    )

    _m(
        peer_review,
        "peer-review conditional manuscript requirements",
        "conditional_requirements:",
        "when: project-backed manuscript review",
    )
    _sf(
        peer_review,
        "existing manuscript",
        "explicit external artifact target",
        "theorem-bearing claims",
        context="peer-review conditional manuscript requirements",
    )
    _m(
        peer_review,
        "peer-review theorem proof requirements",
        "${REVIEW_ROOT}/PROOF-REDTEAM{round_suffix}.md",
        "gpd-check-proof",
    )
    _m(arxiv, "arxiv theorem proof requirements", "conditional_requirements:")
    _s(
        arxiv,
        "arxiv conditional theorem requirements",
        "theorem-bearing manuscripts",
        "cleared manuscript proof review",
    )
    _m(
        arxiv,
        "arxiv latest peer-review evidence",
        "latest peer-review review ledger",
        "latest peer-review referee decision",
    )
    _sf(
        arxiv,
        "missing latest staged peer-review decision evidence",
        "resolved manuscript root",
        "build",
        "reproducibility",
        "staged-review artifacts",
        "workflow gates",
        "wrapper thin",
        "workflow own validation",
        context="arxiv publication gate evidence",
    )
    _f(arxiv, "arxiv stale tex discovery", 'find . -name "main.tex"', "first-match")
    _f(write_paper, "write-paper stale tex discovery", 'find . -name "*.tex"')


def test_proof_contract_prompts_surface_explicit_theorem_fields_and_review_bindings() -> None:
    plan_schema = _expand_prompt_surface(TEMPLATES_DIR / "plan-contract-schema.md")
    proof_schema = (TEMPLATES_DIR / "proof-redteam-schema.md").read_text(encoding="utf-8")
    proof_protocol = (REFERENCES_DIR / "verification" / "core" / "proof-redteam-protocol.md").read_text(
        encoding="utf-8"
    )
    peer_review = _workflow_authority_text("peer-review")
    check_proof = (AGENTS_DIR / "gpd-check-proof.md").read_text(encoding="utf-8")

    _mf(
        plan_schema,
        "claim_kind",
        "parameters[]",
        "hypotheses[]",
        "quantifiers[]",
        "conclusion_clauses[]",
        "proof_deliverables[]",
        "proof_hypothesis_coverage",
        "proof_parameter_coverage",
        "proof_quantifier_domain",
        "claim_to_proof_alignment",
        "lemma_dependency_closure",
        "counterexample_search",
        context="plan contract proof theorem fields",
    )
    _f(plan_schema, "plan contract proof theorem fields", "schema lacks dedicated theorem fields")

    _sf(
        peer_review,
        "When theorem-bearing claims are present, run `gpd-check-proof`",
        "copy active `manuscript_path`",
        "`manuscript_sha256`",
        "round",
        "theorem-bearing `claim_ids`",
        "`proof_artifact_paths`",
        context="peer-review proof task binding",
    )
    assert "from `${REVIEW_ROOT}/CLAIMS{round_suffix}.json`" in peer_review
    _sf(
        peer_review,
        "same-round theorem binding",
        "frontmatter",
        "`claim_ids`",
        "`proof_artifact_paths`",
        context="peer-review theorem-binding frontmatter",
    )
    _sf(
        peer_review,
        "Stage 3 math",
        "exactly one `proof_audits[]` entry",
        "reviewed theorem-bearing claim",
        context="peer-review proof audit binding",
    )
    assert "`proof_audits[].claim_id`" in peer_review
    assert "`claims_reviewed`" in peer_review

    assert "{GPD_INSTALL_DIR}/templates/proof-redteam-schema.md" in check_proof
    assert "{GPD_INSTALL_DIR}/references/verification/core/proof-redteam-protocol.md" in check_proof
    assert "@{GPD_INSTALL_DIR}/references/publication/peer-review-panel.md" not in check_proof
    assert "proof_artifact_paths: [path, ...]" in proof_schema
    assert "manuscript_path" in proof_schema
    assert "manuscript_sha256" in proof_schema
    assert "round" in proof_schema
    _s(proof_protocol, "proof redteam one-shot audit policy", "proof audit", "one-shot run")
    assert "`peer-review` owns manuscript binding" in proof_protocol


def test_peer_review_prompt_surfaces_generic_claim_kind_as_non_theorem_bearing_by_default() -> None:
    panel = (REFERENCES_DIR / "publication" / "peer-review-panel.md").read_text(encoding="utf-8")
    referee = (AGENTS_DIR / "gpd-referee.md").read_text(encoding="utf-8")
    stale_theorem_boundary = (
        "Treat theorem-bearing status from the full Stage 1 claim record, not only from non-empty "
        "`theorem_assumptions` / `theorem_parameters` arrays: theorem-style `claim_kind` values and theorem-like "
        "statement text still require proof audits even when extraction is incomplete."
    )

    _assert_semantic_concept(
        panel,
        "panel theorem-bearing claim-kind boundary",
        required=(
            "Treat theorem-bearing status from the full Stage 1 Paper `ClaimRecord`",
            "`ProjectContract` `ContractClaim` vocabulary",
            "`claim_kind: theorem | lemma | corollary | proposition`",
            "kind alone",
            "`claim_kind: claim | result | other`",
            "theorem metadata or theorem-like text",
            "proof obligation explicit",
            "The theorem-style `claim_kind` values are limited to `theorem`, `lemma`, `corollary`, and `proposition`.",
            "Do not treat `claim_kind: claim` as theorem-bearing by default.",
            "This Paper `ClaimRecord` rule is intentionally different from `ProjectContract.claims[]`",
        ),
        forbidden=stale_theorem_boundary,
        context="peer-review generic claim theorem-bearing boundary",
    )

    _assert_semantic_concept(
        referee,
        "referee theorem-bearing claim-kind boundary",
        required=(
            "only `claim_kind: theorem | lemma | corollary | proposition` is theorem-bearing by kind alone",
            "while non-theorem-style kinds such as `claim`, `result`, or `other` become theorem-bearing only when "
            "non-empty theorem metadata or theorem-like statement text makes the proof obligation explicit.",
            "Do not upclassify a non-theorem-style claim record, including a generic `claim_kind: claim`, into "
            "theorem-bearing status unless the Stage 1 claim record also carries theorem metadata or theorem-like "
            "statement text.",
        ),
        forbidden=stale_theorem_boundary,
        context="referee generic claim theorem-bearing boundary",
    )


def test_write_paper_and_arxiv_submission_keep_the_build_boundary_explicit() -> None:
    write_paper = _workflow_authority_text("write-paper")
    arxiv = _workflow_authority_text("arxiv-submission")

    assert 'gpd paper-build "${PAPER_DIR}/PAPER-CONFIG.json" --output-dir "${PAPER_DIR}"' in write_paper
    _sf(
        write_paper,
        "This emits `${PAPER_DIR}/{topic_specific_stem}.tex`",
        "manuscript-root",
        "artifact manifest",
        "`${PAPER_DIR}/ARTIFACT-MANIFEST.json`",
        context="write-paper paper-build boundary",
    )
    _sf(
        write_paper,
        "local compilation smoke checks are skipped",
        "`.tex` generation still proceeds",
        "`gpd paper-build`",
        "canonical manuscript scaffold contract",
        context="write-paper paper-build nonblocking compile",
    )
    assert 'gpd paper-build "${PAPER_DIR}/PAPER-CONFIG.json" --output-dir "${PAPER_DIR}"' in arxiv
    _sf(
        arxiv,
        "`pdflatex` is available",
        "local smoke check",
        "`pdflatex` is not available",
        "smoke check was skipped",
        "Do not package stale audit artifacts",
        context="arxiv paper-build compile and stale audit policy",
    )


def test_write_paper_source_distinguishes_overclaim_pressure_from_bounded_resume_narrowing() -> None:
    write_paper = _workflow_authority_text("write-paper")

    _sf(
        write_paper,
        "unsupported-strengthening pressure",
        "strengthen unsupported theorem, general-proof",
        "submission-readiness claims",
        "citation",
        "adversarial overclaim pressure",
        "explicitly asks to narrow, qualify, or repair the claim",
        "Reject before manuscript writes",
        "claim_state: overclaim_blocked",
        "command_execution_state: blocked_before_write",
        "checkpoint: claim_evidence_gate",
        "files_written: none",
        "Do not convert adversarial overclaim pressure into a safe-narrowing rewrite",
        "Ordinary bounded resume narrowing remains allowed",
        "evidence requires a narrower claim",
        "no-write `overclaim_blocked` rule",
        context="write-paper overclaim versus safe narrowing",
    )


def test_arxiv_submission_documents_conservative_response_freshness_policy() -> None:
    command = (COMMANDS_DIR / "arxiv-submission.md").read_text(encoding="utf-8")
    workflow = _workflow_authority_text("arxiv-submission")

    _assert_semantic_concept(
        command,
        "arxiv command response freshness gate",
        required=(
            "latest response-round freshness status",
            "same-round or newer response artifacts without newer staged peer-review clearance",
        ),
        context="arxiv response freshness gate",
    )
    _assert_semantic_concept(
        workflow,
        "arxiv workflow conservative response freshness gate",
        required=(
            "all-response freshness policy",
            "response artifacts as revision records",
            "durable manuscript-change scope metadata",
        ),
        context="arxiv response freshness gate",
    )
    _mf(
        workflow,
        "response_freshness",
        "latest_response_requires_fresh_review=true",
        "response_gate",
        "review_state: stale",
        "response_state: requires_fresh_review",
        "claim_state: not_applicable",
        context="arxiv response freshness machine markers",
    )


def test_remove_phase_workflow_stages_checkpoint_shelf_updates() -> None:
    workflow = (WORKFLOWS_DIR / "remove-phase.md").read_text(encoding="utf-8")

    assert "checkpoint shelf artifacts" in workflow
    assert "GPD/CHECKPOINTS.md" in workflow
    assert "GPD/phase-checkpoints" in workflow


def test_new_project_surfaces_supervised_default_and_core_research_preset_preview() -> None:
    workflow_text = _workflow_authority_text("new-project")

    # The minimal-mode config.json template emits the supervised default explicitly.
    assert '"autonomy": "supervised"' in workflow_text
    assert '"review_cadence": "dense"' in workflow_text

    # The preset catalog is still present, with the core-research preset recommended.
    assert "Which starting workflow preset should GPD use for `GPD/config.json`?" in workflow_text
    assert '"Core research (Recommended)"' in workflow_text
    assert '"Theory"' in workflow_text
    assert '"Numerics"' in workflow_text
    assert '"Publication / manuscript"' in workflow_text
    assert '"Full research"' in workflow_text

    # The core-research preset aligns with the Phase-1 defaults
    # (autonomy=supervised, review_cadence=dense), so its preview surfaces
    # those values rather than weaker overrides.
    _mf(
        workflow_text,
        '"autonomy": "supervised"',
        '"research_mode": "balanced"',
        '"parallelization": true',
        '"commit_docs": true',
        '"review_cadence": "dense"',
        context="new-project core-research preset machine preview",
    )
    _sf(
        workflow_text,
        "Config:",
        "Supervised autonomy",
        "Dense review cadence",
        "Balanced research mode",
        "Parallel",
        "All agents",
        "Review profile",
        context="new-project core-research preset preview",
    )

    _ff(
        workflow_text,
        "Recommended defaults use YOLO autonomy",
        "Config: YOLO autonomy | Balanced research mode | Parallel | All agents | Review profile",
        context="new-project stale YOLO preset copy",
    )


def test_settings_and_new_project_surface_runtime_permission_sync_for_yolo() -> None:
    new_project = _workflow_authority_text("new-project")
    settings = (WORKFLOWS_DIR / "settings.md").read_text(encoding="utf-8")
    permissions_sync = re.compile(
        r"gpd --raw permissions sync\b"
        r"(?=[^\n]*--runtime \"\$SELECTED_RUNTIME\")"
        r"(?=[^\n]*--autonomy \"\$SELECTED_AUTONOMY\")"
    )

    assert permissions_sync.search(new_project)
    assert permissions_sync.search(settings)
    assert 'gpd --raw permissions sync --autonomy "$SELECTED_AUTONOMY"' not in new_project
    assert 'gpd --raw permissions sync --autonomy "$SELECTED_AUTONOMY"' not in settings
    _mf(
        new_project,
        "SELECTED_RUNTIME",
        "runtime-owned permission settings",
        "base install",
        "tool readiness",
        "workflow readiness",
        "If `requires_relaunch` is `true`, show `next_step` verbatim",
        context="new-project runtime permission sync fields",
    )
    _s(new_project, "new-project runtime permission sync", "sync runtime-owned permissions", "selected autonomy")
    _mf(
        settings,
        "model_overrides.<SELECTED_RUNTIME>",
        "runtime-owned permission settings",
        "install health",
        "workflow/tool readiness",
        "| Runtime Permissions  | {aligned / changed / manual follow-up required} |",
        context="settings runtime permission sync fields",
    )
    _s(settings, "settings runtime permission sync", "syncs the runtime", "most autonomous permission mode")


def test_new_project_requires_scoping_contract_across_setup_modes() -> None:
    workflow_text = _workflow_authority_text("new-project")
    command_text = (COMMANDS_DIR / "new-project.md").read_text(encoding="utf-8")

    _assert_contains_fragments(
        workflow_text,
        "scoping contract",
        "explicit approval",
        "decisive outputs",
        "anchors",
        "prior outputs",
        "stop conditions",
        "rethink triggers",
        "`context_intake`",
        "`approach_policy`",
        "`uncertainty_markers`",
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
    workflow_text = _workflow_authority_text("new-project")
    scope_intake_text = (WORKFLOWS_DIR / "new-project" / "scope-intake.md").read_text(encoding="utf-8")
    command_text = (COMMANDS_DIR / "new-project.md").read_text(encoding="utf-8")
    manifest = validate_workflow_stage_manifest_payload(
        json.loads((WORKFLOWS_DIR / "new-project-stage-manifest.json").read_text(encoding="utf-8")),
        expected_workflow_id="new-project",
    )
    scope_intake = manifest.stage("scope_intake")

    _mf(
        workflow_text,
        "gpd state set-project-contract",
        "gpd --raw validate project-contract - --mode approved",
        "gpd state set-project-contract -",
        context="new-project contract persistence wiring",
    )
    scope_intake_context = "new-project scope-intake active-stage field access"
    _sf(scope_intake_text, "SCOPE_INIT.staged_loading.field_access_instruction", context=scope_intake_context)
    _ff(
        workflow_text,
        "/tmp/gpd-project-contract.json",
        "temporary JSON file if needed",
        context="new-project stale contract persistence flow",
    )
    _f(scope_intake_text, "new-project scope intake stale JSON parsing", "Parse JSON for:")
    for field in (
        "commit_docs",
        "autonomy",
        "research_mode",
        "project_exists",
        "has_research_map",
        "planning_exists",
        "has_research_files",
        "research_file_samples",
        "has_project_manifest",
        "needs_research_map",
        "has_git",
        "project_contract",
        "project_contract_gate",
        "project_contract_load_info",
        "project_contract_validation",
    ):
        assert field in scope_intake.required_init_fields
    _mf(
        workflow_text,
        "SCOPE_APPROVAL_INIT=$(gpd --raw init new-project --stage scope_approval)",
        "MINIMAL_ARTIFACTS_INIT=$(gpd --raw init new-project --stage minimal_artifacts)",
        "WORKFLOW_PREFS_INIT=$(gpd --raw init new-project --stage workflow_preferences)",
        "roadmapper_model",
        context="new-project staged init wiring",
    )
    _f(
        workflow_text,
        "new-project removed post-scope init",
        "POST_SCOPE_INIT=$(gpd --raw init new-project --stage post_scope)",
    )
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
    workflow_text = _workflow_authority_text("new-project")
    workflow_preferences = (WORKFLOWS_DIR / "new-project" / "workflow-preferences.md").read_text(encoding="utf-8")
    project_artifacts = (WORKFLOWS_DIR / "new-project" / "project-artifacts.md").read_text(encoding="utf-8")
    command_text = (COMMANDS_DIR / "new-project.md").read_text(encoding="utf-8")

    _assert_contains_fragments(
        workflow_preferences,
        "GPD/config.json",
        "scope approval",
        "before downstream project artifacts",
    )
    _ff(
        workflow_text,
        "## 2.5 Early Workflow Setup",
        "If Step 2.5 already captured provisional setup preferences",
        context="new-project deferred workflow setup stale text",
    )
    _s(workflow_text, "new-project scope-first intake semantics", "Describe your research project in one pass")
    _assert_contains_fragments(
        project_artifacts,
        "If `GPD/config.json` is missing",
        "workflow_preferences",
        "After `GPD/config.json` exists",
    )
    _sf(
        command_text,
        "start with physics questioning",
        "surface a preset choice before workflow preferences",
        "before the first project-artifact commit",
        context="new-project command defers workflow setup",
    )


def test_new_project_command_avoids_stale_workflow_line_counts() -> None:
    command_text = (COMMANDS_DIR / "new-project.md").read_text(encoding="utf-8")

    _assert_semantic_concept(
        command_text,
        "new-project command delegates stage details",
        required="read the included stage authority",
        forbidden=("step-by-step instructions", "lines)"),
        context="new-project command stale line counts",
    )


def test_questioning_guide_requires_anchors_and_disconfirming_questions() -> None:
    guide_text = (REFERENCES_DIR / "research" / "questioning.md").read_text(encoding="utf-8")
    how_to_question = _extract_between(guide_text, "<how_to_question>", "</how_to_question>")
    question_types = _extract_between(guide_text, "<question_types>", "</question_types>")
    context_checklist = _extract_between(guide_text, "<context_checklist>", "</context_checklist>")
    decision_gate = _extract_between(guide_text, "<decision_gate>", "</decision_gate>")

    _assert_prompt_concepts(
        how_to_question,
        {
            "early anchors": ("references", "prior outputs", "benchmarks", "smoking-gun signal"),
            "preserve user guidance": ("figure", "dataset", "paper", "stop condition", "recognizable"),
            "pressure-test framing": ("working hypothesis", "narrow", "overturn", "falsify"),
            "avoid fake decomposition": ("roadmap is still fuzzy", "open decomposition question", "fake phases"),
        },
        context="questioning guide how_to_question",
    )
    _assert_prompt_concepts(
        question_types,
        {
            "ground-truth anchors": ("Ground-truth anchors", "known result", "prior output", "trusted anchor"),
            "disconfirmation": ("Disconfirmation and failure", "wrong or incomplete", "should not count as success"),
        },
        context="questioning guide question_types",
    )
    _assert_prompt_concepts(
        context_checklist,
        {
            "background anchor checks": ("background checklist", "known result", "prior output", "misleading proxy"),
        },
        context="questioning guide context_checklist",
    )
    _assert_prompt_concepts(
        decision_gate,
        {
            "coarse scope can proceed": ("Lack of a full phase list", "first grounded investigation chunk"),
            "no mechanical turn count": ("Do not count turns mechanically", "materially sharpening"),
        },
        context="questioning guide decision_gate",
    )


def test_new_project_questioning_requires_smoking_gun_and_rejects_proxy_only_readiness() -> None:
    scope_intake = (WORKFLOWS_DIR / "new-project" / "scope-intake.md").read_text(encoding="utf-8")
    scope_approval = (WORKFLOWS_DIR / "new-project" / "scope-approval.md").read_text(encoding="utf-8")
    guide_text = (REFERENCES_DIR / "research" / "questioning.md").read_text(encoding="utf-8")
    guide_decision_gate = _extract_between(guide_text, "<decision_gate>", "</decision_gate>")
    guide_question_types = _extract_between(guide_text, "<question_types>", "</question_types>")

    _assert_prompt_concepts(
        scope_intake,
        {
            "decisive intake": ("output, claim, or deliverable", "anchor", "baseline", "rethink"),
            "single repair": ("missing", "blocks a coherent scoping contract", "one narrow repair question"),
        },
        context="new-project deep questioning",
    )
    _assert_prompt_concepts(
        scope_approval,
        {
            "user anchor preservation": ("concrete anchor", "reference", "prior-output constraint", "baseline"),
            "no invented grounding": ("Do not invent anchors", "references", "baselines", "prior outputs"),
        },
        context="new-project Step M1.5 contract",
    )
    _assert_prompt_concepts(
        guide_text,
        {
            "hard correctness anchor": ("hard correctness check", "smoking-gun signal", "generic limiting cases"),
        },
        context="questioning guide smoking-gun policy",
    )
    _assert_prompt_concepts(
        guide_question_types,
        {
            "smoking-gun question": ("smoking-gun observable", "scaling law", "curve", "benchmark"),
            "sanity check is not enough": ("limiting cases", "sanity checks", "missed the smoking-gun check"),
        },
        context="questioning guide success and anchors",
    )
    _assert_prompt_concepts(
        guide_decision_gate,
        {
            "proxy-only gate rejection": (
                "proxy checks",
                "sanity checks",
                "limiting cases",
                "no decisive smoking-gun observable",
            ),
            "missing-anchor note is insufficient": (
                "missing-anchor note",
                "concrete reference",
                "prior-output",
                "baseline grounding",
            ),
        },
        context="questioning guide decision gate",
    )


def test_project_and_context_templates_surface_contract_and_skeptical_review() -> None:
    project_text = (TEMPLATES_DIR / "project.md").read_text(encoding="utf-8")
    context_text = (TEMPLATES_DIR / "context.md").read_text(encoding="utf-8")
    requirements_text = (TEMPLATES_DIR / "requirements.md").read_text(encoding="utf-8")
    state_schema_text = _expand_prompt_surface(TEMPLATES_DIR / "state-json-schema.md")

    _mf(
        project_text,
        "## Scoping Contract Summary",
        "### Contract Coverage",
        "### Active Anchor Registry",
        "### User Guidance To Preserve",
        "### Skeptical Review",
        context="project template contract sections",
    )
    _mf(
        context_text,
        "## Contract Coverage",
        "## Active Anchor Registry",
        "## User Guidance To Preserve",
        "## Skeptical Review",
        context="context template contract sections",
    )
    _mf(requirements_text, "## Contract Coverage", context="requirements template contract sections")
    assert "disconfirming_observations" in state_schema_text


def test_discuss_and_assumption_workflows_surface_anchors_and_fast_falsifiers() -> None:
    discuss_text = (WORKFLOWS_DIR / "discuss-phase.md").read_text(encoding="utf-8")
    assumptions_text = (WORKFLOWS_DIR / "list-phase-assumptions.md").read_text(encoding="utf-8")

    _sf(
        discuss_text,
        "prior output",
        "benchmark",
        "reference",
        "look wrong or incomplete early",
        "## User Guidance To Preserve",
        "## Contract Coverage",
        "## Active Anchor Registry",
        "## Skeptical Review",
        context="discuss-phase anchor and falsifier intake",
    )
    _pf(
        assumptions_text,
        "User Guidance I Am Treating As Binding",
        "### Anchor Inputs",
        "**Fast falsifier:**",
        "**False progress:**",
        context="list-phase-assumptions anchor and falsifier sections",
    )


def test_discuss_and_plan_workflows_resolve_roadmap_only_phases() -> None:
    discuss_text = (WORKFLOWS_DIR / "discuss-phase.md").read_text(encoding="utf-8")
    plan_text = _workflow_authority_text("plan-phase")

    _f(discuss_text, "discuss-phase stale roadmap phase failure", "Phase [X] not found in roadmap.")
    _mf(
        discuss_text,
        'ROADMAP_INFO=$(gpd --raw roadmap get-phase "${PHASE}")',
        'phase_slug=$(gpd slug "$phase_name")',
        context="discuss-phase roadmap-only phase resolution",
    )
    _s(discuss_text, "discuss-phase roadmap-only phase resolution", "check_existing", "roadmap-derived phase metadata")
    _mf(
        plan_text,
        'REQUESTED_PHASE="${PHASE}"',
        'PHASE=$(echo "$INIT" | gpd json get .phase_number --default "${REQUESTED_PHASE}")',
        context="plan-phase roadmap-only phase resolution",
    )
    _sf(
        plan_text,
        "roadmap",
        "phase_number",
        "phase_name",
        "goal",
        "PHASE_DIR",
        context="plan-phase roadmap-only phase resolution",
    )


def test_planning_and_phase_templates_surface_active_reference_context() -> None:
    planner_prompt = (TEMPLATES_DIR / "planner-subagent-prompt.md").read_text(encoding="utf-8")
    phase_prompt = (TEMPLATES_DIR / "phase-prompt.md").read_text(encoding="utf-8")
    workflow_text = _workflow_authority_text("plan-phase")

    _s(planner_prompt, "planner prompt active reference context", "approved `project_contract`")
    _assert_init_placeholders_visible(
        planner_prompt,
        (
            "project_contract",
            "project_contract_gate",
            "project_contract_load_info",
            "project_contract_validation",
            "active_reference_context",
        ),
        context="planner prompt active reference placeholders",
    )
    assert "@path/to/reference-or-benchmark-anchor.md" in phase_prompt
    assert "Planning requires an approved scoping contract in `GPD/state.json`" in workflow_text
    assert "project_contract_gate" in workflow_text
    assert "project_contract_validation" in workflow_text
    assert "project_contract_load_info" in workflow_text
    _sf(
        workflow_text,
        "project_contract_gate.authoritative",
        "Use `contract_gate_stop`",
        "Planning requires an approved scoping contract in `GPD/state.json`",
        "**Anchor and protocol coverage:**",
        "Required references",
        context="plan-phase active reference context",
    )
    _assert_init_placeholders_visible(
        workflow_text,
        ("project_contract", "active_reference_context"),
        context="plan-phase active reference placeholders",
    )


def test_progress_workflow_surfaces_contract_load_and_validation_state() -> None:
    workflow_text = (WORKFLOWS_DIR / "progress.md").read_text(encoding="utf-8")
    command_text = (COMMANDS_DIR / "progress.md").read_text(encoding="utf-8")

    _mf(
        workflow_text,
        "project_contract_validation",
        "project_contract_load_info",
        "knowledge_doc_count",
        "stable_knowledge_doc_count",
        "knowledge_doc_status_counts",
        "derived_knowledge_doc_count",
        "knowledge_doc_warnings",
        context="progress workflow contract and knowledge fields",
    )
    _sf(
        workflow_text,
        "structured load status",
        "warnings",
        "blockers",
        "contract",
        "authoritative",
        "`project_contract_gate.authoritative`",
        context="progress workflow contract load state",
    )
    status_scan = 'grep -l -E "^(status: (gaps_found|human_needed|expert_needed)|session_status: diagnosed)$"'
    assert status_scan in workflow_text
    assert status_scan not in command_text
    _s(command_text, "progress command thin wrapper", "included workflow", "Do not duplicate", "workflow logic")
    assert "INIT=$(gpd --raw init progress --include state,roadmap,project,config,references)" not in command_text
    assert 'CONTEXT=$(gpd --raw validate command-context progress "$ARGUMENTS")' not in command_text
    assert "status: (gaps_found|diagnosed|human_needed|expert_needed)" not in workflow_text
    assert "status: (gaps_found|diagnosed|human_needed|expert_needed)" not in command_text
    _mf(
        workflow_text,
        "`session_status: diagnosed`",
        "HEALTH.summary.warn > 0",
        "HEALTH.summary.fail > 0",
        "## Knowledge Status",
        "GPD/phases/[current-phase-dir]/*-VERIFICATION.md",
        context="progress workflow status and health fields",
    )
    assert "`session_status: diagnosed`" not in command_text
    assert "non-empty `issues` array" not in workflow_text
    assert "GPD/phases/[current-phase-dir]/*-VERIFICATION.md" not in command_text


def test_progress_workflow_uses_read_only_health_for_compaction_status() -> None:
    workflow_text = (WORKFLOWS_DIR / "progress.md").read_text(encoding="utf-8")

    _mf(
        workflow_text,
        "gpd --raw health",
        "HEALTH_JSON=$(gpd --raw health 2>/dev/null || true)",
        "HEALTH=$(gpd --raw health 2>/dev/null || true)",
        context="progress read-only health command",
    )
    _sf(
        workflow_text,
        "exit 1",
        "parseable JSON",
        "raw health returned nonzero",
        context="progress workflow read-only health compaction status",
    )
    _sf(
        workflow_text,
        "`State Compaction` check",
        "Report only",
        "`gpd:progress` did not modify it",
        context="progress workflow state compaction status",
    )
    _ff(workflow_text, "gpd --raw state compact", context="progress workflow read-only state compaction")


def test_planning_prompts_keep_contract_gate_in_light_mode_and_all_modes() -> None:
    planner_prompt = (TEMPLATES_DIR / "planner-subagent-prompt.md").read_text(encoding="utf-8")
    planner_agent = (AGENTS_DIR / "gpd-planner.md").read_text(encoding="utf-8")
    checker_agent = (AGENTS_DIR / "gpd-plan-checker.md").read_text(encoding="utf-8")
    workflow_text = _workflow_authority_text("plan-phase")
    checker_routing = (WORKFLOWS_DIR / "plan-phase" / "checker-return-routing.md").read_text(encoding="utf-8")

    assert "{GPD_INSTALL_DIR}/templates/plan-contract-schema.md" in planner_prompt
    assert (
        "Use `@{GPD_INSTALL_DIR}/templates/plan-contract-schema.md` as the canonical contract source." in planner_prompt
    )
    _sf(
        planner_prompt,
        "approach_policy",
        "execution policy only",
        "Light mode",
        "body verbosity",
        context="planner light mode contract gate",
    )
    _sf(
        planner_agent,
        "Profiles",
        "compress detail",
        "do NOT relax contract completeness",
        context="planner agent profile contract completeness",
    )
    _sf(
        workflow_text,
        "All modes",
        "contract completeness",
        "decisive outputs",
        "required anchors",
        "forbidden-proxy",
        "disconfirming paths",
        context="plan-phase all-mode contract completeness",
    )
    assert "gpd_return.status: completed" in planner_prompt
    _sf(
        planner_prompt,
        "## PLANNING COMPLETE",
        "## CHECKPOINT REACHED",
        "## PLANNING INCONCLUSIVE",
        "human-readable labels only",
        context="planner presentation headings are non-authority",
    )
    assert "gpd_return.status: completed" in workflow_text
    _sf(
        checker_routing,
        "Checker presentation headings",
        "non-authority",
        "`gpd_return.status`",
        "structured `approved_plans`",
        context="plan-phase checker presentation headings are non-authority",
    )
    _s(checker_agent, "plan checker contract completeness", "Human review", "does not replace", "requirements")


def test_stable_knowledge_remains_background_only_across_planning_verification_and_execution() -> None:
    planner_prompt = (TEMPLATES_DIR / "planner-subagent-prompt.md").read_text(encoding="utf-8")
    plan_phase = _workflow_authority_text("plan-phase")
    verify_workflow = _workflow_authority_text("verify-work")
    verify_phase = (WORKFLOWS_DIR / "verify-phase.md").read_text(encoding="utf-8")
    execute_plan = (WORKFLOWS_DIR / "execute-plan.md").read_text(encoding="utf-8")
    execute_phase = _workflow_authority_text("execute-phase")

    _sf(
        planner_prompt,
        "stable knowledge docs",
        "`active_reference_context`",
        "`reference_artifacts_content`",
        "reviewed background",
        "`knowledge_deps`",
        "advisory",
        "do not override",
        context="planner stable knowledge boundary",
    )
    _sf(
        plan_phase,
        "Stable knowledge docs",
        "advisory",
        "explicit `knowledge_deps`",
        "never override",
        "`convention_lock`",
        "`project_contract`",
        "direct evidence",
        context="plan-phase stable knowledge boundary",
    )
    _sf(
        verify_workflow,
        "Stable knowledge docs",
        "reviewed background synthesis",
        "stronger sources",
        "never as decisive evidence",
        context="verify-work stable knowledge boundary",
    )
    _sf(
        verify_phase,
        "Stable knowledge docs",
        "reviewed background synthesis",
        "check selection",
        "do not override",
        "decisive evidence",
        context="verify-phase stable knowledge boundary",
    )
    _sf(
        execute_plan,
        "Stable knowledge docs",
        "reviewed background",
        "do not override",
        "contract",
        "decisive evidence",
        context="execute-plan stable knowledge boundary",
    )
    _sf(
        execute_phase,
        "Stable knowledge docs",
        "shared reference surfaces",
        "reviewed background",
        "not become a separate authority tier",
        "do not override",
        "proof audits",
        "decisive evidence",
        context="execute-phase stable knowledge boundary",
    )


def test_plan_checker_requires_contract_gate_and_reference_artifacts() -> None:
    checker_agent = (AGENTS_DIR / "gpd-plan-checker.md").read_text(encoding="utf-8")
    workflow_text = _workflow_authority_text("plan-phase")

    assert "## Dimension 0: Contract Gate" in checker_agent
    assert "{GPD_INSTALL_DIR}/templates/plan-contract-schema.md" in checker_agent
    _assert_prompt_contracts(
        checker_agent,
        machine_exact(
            "plan checker continuation boundary reference",
            "{GPD_INSTALL_DIR}/references/orchestration/continuation-boundary.md",
        ),
        semantic_anchor(
            "plan checker checkpoint handoff stop",
            ("one-shot handoff", "user input", "typed checkpoint", "stop"),
            context="plan-checker contract gate",
        ),
    )
    _mf(
        checker_agent,
        "contract_decisive_output",
        "contract_anchor_coverage",
        "proxy_only_success_path",
        context="plan checker contract dimensions",
    )
    _assert_init_placeholders_visible(
        workflow_text,
        (
            "project_contract_gate",
            "project_contract_load_info",
            "project_contract_validation",
            "contract_intake",
            "effective_reference_intake",
            "reference_artifact_files",
        ),
        context="plan-phase contract gate placeholders",
    )
    _s(workflow_text, "plan-phase decisive output checks", "Decisive outputs", "decisive claims and deliverables")
    _sf(
        workflow_text,
        "Acceptance tests",
        "executable or reviewable test",
        "Forbidden proxies",
        "Proxy-only success conditions",
        context="plan-phase decisive acceptance and proxy checks",
    )


def test_roadmap_template_and_workflows_surface_phase_contract_coverage() -> None:
    roadmap_template = (TEMPLATES_DIR / "roadmap.md").read_text(encoding="utf-8")
    state_template = (TEMPLATES_DIR / "state.md").read_text(encoding="utf-8")
    roadmapper_agent = registry.get_agent("gpd-roadmapper").system_prompt
    new_project = _workflow_authority_text("new-project")
    new_milestone = _workflow_authority_text("new-milestone")
    new_project_roadmapper = _find_single_task(WORKFLOWS_DIR / "new-project.md", "gpd-roadmapper").text

    _pf(
        roadmap_template,
        "## Contract Overview",
        "**Contract Coverage:**",
        context="roadmap template public contract headings",
    )
    _assert_semantic_concept(
        roadmap_template,
        "roadmap phase titles are objective driven",
        required="Phase titles should be objective-driven, not template-driven",
        forbidden=(
            "Standard physics research flow",
            "Literature Review",
            "Formalism Development",
            "Calculation / Simulation",
            "Validation & Cross-checks",
            "Paper Writing",
        ),
        match=MatchMode.EXACT,
        context="roadmap template objective-driven phases",
    )
    assert_prompt_contracts(
        roadmapper_agent,
        forbidden_duplicate(
            "roadmapper defers roadmap template body",
            "@{GPD_INSTALL_DIR}/templates/roadmap.md",
            max_count=0,
        ),
        forbidden_duplicate(
            "roadmapper defers state template body",
            "@{GPD_INSTALL_DIR}/templates/state.md",
            max_count=0,
        ),
        semantic_anchor(
            "roadmapper keeps late-loaded roadmap and state templates visible",
            (
                "{GPD_INSTALL_DIR}/templates/roadmap.md",
                "{GPD_INSTALL_DIR}/templates/state.md",
                "file_read",
            ),
        ),
    )
    _mf(
        roadmapper_agent,
        "## Step 3: Load Research Context (if exists)",
        "Contract coverage",
        "Machine-Readable Return Envelope",
        "gpd_return:",
        "status: completed",
        "files_written:",
        "GPD/ROADMAP.md",
        "GPD/STATE.md",
        "GPD/REQUIREMENTS.md",
        "phases_created: 4",
        context="roadmapper return and coverage fields",
    )
    _m(
        new_project_roadmapper,
        "new-project roadmapper artifact gate",
        "gpd_return.files_written",
        "GPD/REQUIREMENTS.md",
    )
    _s(new_project_roadmapper, "new-project roadmapper artifact gate", "do not rely on runtime completion text alone")
    _mf(
        new_milestone,
        "expected_artifacts:",
        'freshness_marker: "after $MILESTONE_ROADMAPPER_HANDOFF_STARTED_AT"',
        context="new-milestone roadmapper artifact gate",
    )
    _pf(state_template, "Intermediate Results", context="state template progress heading")
    _assert_semantic_concept(
        roadmapper_agent,
        "roadmapper stops with blocked return when contract is underspecified",
        required=(
            "approved project contract is missing",
            "decisive outputs / deliverables plus anchor guidance",
            "stop with a blocked return",
            "status-routing",
        ),
        context="roadmapper blocked return status",
    )
    _assert_semantic_concept(
        roadmapper_agent,
        "roadmapper treats contract intake as binding user guidance",
        required=(
            "`context_intake.must_read_refs`",
            "`must_include_prior_outputs`",
            "`user_asserted_anchors`",
            "`known_good_baselines`",
            "`crucial_inputs`",
            "binding user guidance",
        ),
        context="roadmapper binding user guidance",
    )
    # new-project uses shallow mode by default — Phase 1 only carries full coverage.
    # new-milestone keeps full-detail roadmap for scoped continuations.
    _sf(
        new_project,
        "For Phase 1",
        "explicit contract coverage",
        "ROADMAP.md",
        "requirements or contract demand",
        "contract-critical identity",
        context="new-project roadmap contract coverage",
    )
    _s(new_milestone, "new-milestone roadmap coverage", "For each phase", "explicit contract coverage", "ROADMAP.md")


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
    workflow_text = _workflow_authority_text("new-project")
    scope_intake = (WORKFLOWS_DIR / "new-project" / "scope-intake.md").read_text(encoding="utf-8")
    scope_approval = (WORKFLOWS_DIR / "new-project" / "scope-approval.md").read_text(encoding="utf-8")
    roadmap_authoring = (WORKFLOWS_DIR / "new-project" / "roadmap-authoring.md").read_text(encoding="utf-8")
    planner_prompt = (TEMPLATES_DIR / "planner-subagent-prompt.md").read_text(encoding="utf-8")
    roadmap_instructions = _extract_between(roadmap_authoring, "<instructions>", "</instructions>")

    _s(scope_intake, "new-project unknown anchor response", "anchor", "unknown")
    _assert_prompt_concepts(
        scope_approval,
        {
            "unknown anchor fields": (
                "anchor",
                "context_intake",
                "uncertainty_markers",
                "missing-anchor uncertainty",
            ),
            "no invented grounding": ("Do not invent anchors", "references", "baselines", "prior outputs"),
        },
        context="new-project approval contract",
    )
    _assert_prompt_concepts(
        workflow_text,
        {
            "missing anchor is carried": ("anchor is unknown", "unknown-anchor gap"),
            "coarse stage gate": ("single phase", "coarse early roadmap", "smallest decomposition"),
        },
        context="new-project missing-anchor approval gate",
    )
    _assert_prompt_concepts(
        roadmap_instructions,
        {
            "smallest supported roadmap": ("smallest decomposition", "single phase", "coarse early roadmap"),
            "no invented phase families": ("Do NOT invent", "literature", "numerics", "paper phases"),
        },
        context="new-project roadmap instructions",
    )
    _mf(planner_prompt, "## CHECKPOINT REACHED", context="planner checkpoint marker")
    _s(planner_prompt, "planner phase slice checkpoint semantics", "missing", "phase slice")


def test_reference_workflows_require_anchor_registry_propagation() -> None:
    literature_workflow = _workflow_authority_text("literature-review")
    literature_command = (COMMANDS_DIR / "literature-review.md").read_text(encoding="utf-8")
    literature_agent = (AGENTS_DIR / "gpd-literature-reviewer.md").read_text(encoding="utf-8")
    bibliographer_agent = (AGENTS_DIR / "gpd-bibliographer.md").read_text(encoding="utf-8")
    compare_workflow = (WORKFLOWS_DIR / "compare-results.md").read_text(encoding="utf-8")
    map_workflow = _workflow_authority_text("map-research")
    map_command = (COMMANDS_DIR / "map-research.md").read_text(encoding="utf-8")
    mapper_agent = (AGENTS_DIR / "gpd-research-mapper.md").read_text(encoding="utf-8")

    literature_bootstrap_fields = (
        load_workflow_stage_manifest("literature-review").stage("review_bootstrap").required_init_fields
    )
    assert "project_contract_load_info" in literature_bootstrap_fields
    assert "project_contract_validation" in literature_bootstrap_fields
    _assert_prompt_concepts(
        literature_workflow,
        {
            "contract-gated anchor scope": (
                "contract-critical anchors",
                "project_contract_gate.authoritative",
                "authoritative",
            ),
            "defer heavy artifacts until scoped": (
                "frontload reference artifacts",
                "scope is fixed",
                "reference_artifact_files",
                "reference_artifacts_content",
            ),
        },
        context="literature-review workflow anchor propagation",
    )
    _sf(
        literature_workflow,
        "load_scoped_reference_artifacts",
        "include `bibtex_key`",
        "known and verified",
        context="literature-review scoped citation artifacts",
    )
    assert "reference_artifact_files" not in literature_bootstrap_fields
    assert "reference_artifacts_content" not in literature_bootstrap_fields
    _assert_command_delegates_to_workflow(
        literature_command,
        "literature-review",
        semantic_fragments=("staged workflow owns", "scope fixing", "artifact gating", "citation verification"),
        stale_fragments=(
            "First, read {GPD_AGENTS_DIR}/gpd-literature-reviewer.md for your role and instructions",
            "Write to: GPD/literature/{slug}-REVIEW.md",
        ),
    )
    assert "Active Anchor Registry" not in literature_command
    _mf(
        literature_agent,
        "active_anchors",
        "GPD/literature/{slug}-CITATION-SOURCES.json",
        "gpd paper-build --citation-sources",
        "reference_id",
        context="literature reviewer citation sidecar fields",
    )
    _sf(
        literature_agent,
        "compatible with the `CitationSource` shape",
        "`bibtex_key` as an optional preferred key",
        "Keep `bibtex_key` stable",
        context="literature reviewer bibtex key stability",
    )
    _assert_prompt_concepts(
        bibliographer_agent,
        {
            "bibtex manuscript bridge": ("preferred `bibtex_key`", "manuscript bridge candidate"),
            "mode matrix reference": ("mode specification matrix", "publication-pipeline-modes.md"),
        },
        context="bibliographer anchor propagation",
    )
    _mf(
        compare_workflow,
        "project_contract_load_info",
        "project_contract_validation",
        "active_reference_context",
        context="compare-results reference fields",
    )
    _assert_prompt_concepts(
        compare_workflow,
        {
            "comparison scope authority gate": (
                "contract authority gate",
                "project_contract",
                "comparison scope",
                "project_contract_gate.authoritative",
            ),
        },
        context="compare-results workflow anchor propagation",
    )
    _mf(
        map_workflow,
        "active_references",
        "effective_reference_intake",
        "project_contract_load_info",
        "project_contract_validation",
        "reference_artifact_files",
        "protocol_bundle_load_manifest",
        "protocol_bundle_verifier_extensions",
        context="map-research reference fields",
    )
    _assert_prompt_concepts(
        map_workflow,
        {
            "map-research authority gate": ("authoritative", "project_contract_gate.authoritative"),
        },
        context="map-research workflow anchor propagation",
    )
    _assert_command_delegates_to_workflow(
        map_command,
        "map-research",
        semantic_fragments=("workflow", "staged init", "mapper fanout", "return routing"),
        stale_fragments=("project_contract_load_info", "reference_artifacts_content"),
    )
    assert "REFERENCES.md is an anchor registry" in mapper_agent


def test_literature_review_stage_manifest_keeps_citation_audit_write_visible() -> None:
    literature_workflow = _workflow_authority_text("literature-review")
    literature_staging = validate_workflow_stage_manifest_payload(
        json.loads((WORKFLOWS_DIR / "literature-review-stage-manifest.json").read_text(encoding="utf-8")),
        expected_workflow_id="literature-review",
    )

    assert literature_staging.stage_ids() == (
        "review_bootstrap",
        "scope_locked",
        "review_handoff",
        "completion_gate",
    )
    assert "GPD/literature/{slug}-CITATION-AUDIT.md" in literature_workflow
    assert "GPD/literature/slug-CITATION-AUDIT.md" in literature_staging.stage("review_handoff").writes_allowed


def test_file_producing_command_surfaces_use_canonical_spawn_contract() -> None:
    literature = (COMMANDS_DIR / "literature-review.md").read_text(encoding="utf-8")
    debug = (COMMANDS_DIR / "debug.md").read_text(encoding="utf-8")
    respond = (COMMANDS_DIR / "respond-to-referees.md").read_text(encoding="utf-8")

    for content, agent_name, file_token in ((debug, "gpd-debugger", "GPD/debug/{slug}.md"),):
        assert f"{{GPD_AGENTS_DIR}}/{agent_name}.md" in content
        assert "role and instructions" in content
        assert file_token in content
        assert "before continuing" in content
        assert f"@{file_token}" not in content
    assert "Fresh 200k context" not in content

    assert "gpd --raw validate command-context literature-review" in literature
    _assert_command_delegates_to_workflow(
        literature,
        "literature-review",
        semantic_fragments=("staged workflow", "artifact gating", "citation verification"),
        stale_fragments=(
            "First, read {GPD_AGENTS_DIR}/gpd-literature-reviewer.md for your role and instructions",
            "Write to: GPD/literature/{slug}-REVIEW.md",
        ),
    )

    assert "Fresh 200k context" not in respond


def test_research_phase_command_delegates_file_path_and_return_routing_to_the_workflow() -> None:
    command = (COMMANDS_DIR / "research-phase.md").read_text(encoding="utf-8")
    workflow = _workflow_authority_text("research-phase")

    _assert_command_delegates_to_workflow(
        command,
        "research-phase",
        semantic_fragments=("workflow-owned staged init", "typed-return routing", "artifact gating", "research_mode"),
        stale_fragments=(
            "gpd --raw init phase-op --include state,config",
            "gpd_return.status: completed",
            "gpd_return.files_written",
        ),
    )
    _mf(
        workflow,
        'BOOTSTRAP_INIT=$(load_research_phase_stage phase_bootstrap "${PHASE}")',
        'HANDOFF_INIT=$(load_research_phase_stage research_handoff "${phase_number}")',
        'gpd --raw init research-phase "${phase_arg}" --stage "${stage_name}"',
        "Write to: {phase_dir}/{phase_number}-RESEARCH.md",
        "gpd_return.files_written",
        'RESEARCH_MODE=$(echo "$BOOTSTRAP_INIT" | gpd json get .research_mode --default balanced)',
        context="research-phase workflow staged routing",
    )


def test_revision_and_audit_workflows_verify_artifacts_before_trusting_success_text() -> None:
    respond = _workflow_authority_text("respond-to-referees")
    audit = (WORKFLOWS_DIR / "audit-milestone.md").read_text(encoding="utf-8")
    stage_gate = (REPO_ROOT / "src/gpd/specs/references/publication/stage-recovery-gate.md").read_text(encoding="utf-8")

    _mf(
        respond,
        "templates/paper/author-response.md",
        "needs-calculation",
        "stage-recovery-gate.md",
        "`${RESPONSE_AUTHOR_PATH}`",
        "`${RESPONSE_REFEREE_PATH}`",
        context="respond artifact gate fields",
    )
    _s(respond, "respond artifact gate semantics", "expected_artifacts", "fresh child handoff", "files_written")
    _s(stage_gate, "stage recovery gate freshness", "Do not accept stale preexisting files", "current-run completion")
    _sf(
        audit,
        "Verify the promised referee artifacts",
        "Confirm `GPD/v{milestone_version}-MILESTONE-REFEREE-REPORT.md`",
        "agent reported success",
        "artifact is missing",
        "peer review as failed",
        context="audit milestone artifact gate",
    )


def test_audit_milestone_surfaces_contract_gate_and_milestone_review_namespace() -> None:
    audit = (WORKFLOWS_DIR / "audit-milestone.md").read_text(encoding="utf-8")

    _mf(
        audit,
        "project_contract_load_info",
        "project_contract_validation",
        "active_reference_context",
        context="audit milestone contract gate fields",
    )
    _sf(audit, "Apply the shared contract authority gate", context="audit milestone gate semantics")
    _sf(
        audit,
        "project_contract` is approved milestone scope only when `project_contract_gate.authoritative` is true",
        "skip mock peer review and note that the contract gate must be repaired before milestone publishability review",
        context="audit milestone approved-scope contract gate",
    )
    _mf(
        audit,
        "GPD/v{milestone_version}-MILESTONE-REFEREE-REPORT.md",
        "GPD/v{milestone_version}-MILESTONE-REFEREE-REPORT.tex",
        "Project contract load info: {project_contract_load_info}",
        "Project contract validation: {project_contract_validation}",
        "Active references: {active_reference_context}",
        context="audit milestone review report and context wiring",
    )


def test_audit_milestone_uses_canonical_phase_helpers_instead_of_raw_glob_discovery() -> None:
    audit = (WORKFLOWS_DIR / "audit-milestone.md").read_text(encoding="utf-8")

    assert "gpd phase list" in audit
    assert "gpd:show-phase <phase-number>" in audit
    assert "gpd show-phase <phase-number>" not in audit
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
    required_machine_fragments = (
        (
            _workflow_authority_text("research-phase"),
            (
                'PHASE_INFO=$(gpd --raw roadmap get-phase "${phase_number}")',
                'gpd --raw state snapshot | gpd json get .decisions --default "[]"',
                'BOOTSTRAP_INIT=$(load_research_phase_stage phase_bootstrap "${PHASE}")',
                'HANDOFF_INIT=$(load_research_phase_stage research_handoff "${phase_number}")',
                'RESEARCH_MODE=$(echo "$BOOTSTRAP_INIT" | gpd json get .research_mode --default balanced)',
            ),
            "research-phase raw json plumbing",
        ),
        (
            _workflow_authority_text("map-research"),
            (
                "BOOTSTRAP_INIT=$(load_map_research_stage map_bootstrap)",
                "MAPPER_AUTHORING_INIT=$(load_map_research_stage mapper_authoring)",
                'gpd --raw --cwd "$target_cwd" init map-research --stage "${stage_name}" -- "${ARGUMENTS:-}"',
                'RESEARCH_MODE=$(echo "$BOOTSTRAP_INIT" | gpd json get .research_mode --default balanced)',
                "Map focus:",
                "{map_focus}",
            ),
            "map-research raw json plumbing",
        ),
        (
            (WORKFLOWS_DIR / "progress.md").read_text(encoding="utf-8"),
            (
                "ROADMAP=$(gpd --raw roadmap analyze)",
                'gpd --raw summary-extract <path> --field one_liner | gpd json get .one_liner --default ""',
            ),
            "progress raw json plumbing",
        ),
        (
            _workflow_authority_text("execute-phase"),
            (
                "Load plan inventory with wave grouping from `gpd phase index {phase_number}`.",
                "`objective`",
                "summary-extract for one-liners",
            ),
            "execute-phase raw json plumbing",
        ),
        (
            (WORKFLOWS_DIR / "complete-milestone.md").read_text(encoding="utf-8"),
            (
                "ROADMAP=$(gpd --raw roadmap analyze)",
                'gpd --raw summary-extract "$summary" --field one_liner | gpd json get .one_liner --default ""',
            ),
            "complete-milestone raw json plumbing",
        ),
        (
            (WORKFLOWS_DIR / "show-phase.md").read_text(encoding="utf-8"),
            ('PHASE_INFO=$(gpd --raw roadmap get-phase "${phase_number}")', "ROADMAP=$(gpd --raw roadmap analyze)"),
            "show-phase raw json plumbing",
        ),
    )
    for text, fragments, context in required_machine_fragments:
        _mf(text, *fragments, context=context)

    for filename in ("graph.md", "validate-conventions.md", "export.md"):
        _mf(
            (WORKFLOWS_DIR / filename).read_text(encoding="utf-8"),
            "ROADMAP=$(gpd --raw roadmap analyze)",
            context=f"{filename} raw json plumbing",
        )

    _mf(
        (WORKFLOWS_DIR / "plan-milestone-gaps.md").read_text(encoding="utf-8"),
        "PHASES=$(gpd --raw phase list)",
        context="plan-milestone-gaps raw json plumbing",
    )
    _assert_prompt_contracts(
        (WORKFLOWS_DIR / "transition.md").read_text(encoding="utf-8"),
        fragment_count(
            "transition workflow roadmap analyze call count",
            "ROADMAP=$(gpd --raw roadmap analyze)",
            expected_count=2,
            context="transition workflow roadmap helpers",
        ),
    )
    _mf(
        (WORKFLOWS_DIR / "verify-phase.md").read_text(encoding="utf-8"),
        'gpd --raw roadmap get-phase "${phase_number}"',
        context="verify-phase raw json plumbing",
    )
    _m(
        _workflow_authority_text("verify-work"),
        "verify-work raw json plumbing",
        'gpd --raw roadmap get-phase "${PHASE_ARG}"',
    )

    for text, fragments, context in (
        (
            _workflow_authority_text("research-phase"),
            ("gpd --raw config get research_mode",),
            "research-phase raw json stale config reads",
        ),
        (
            (COMMANDS_DIR / "research-phase.md").read_text(encoding="utf-8"),
            ('gpd --raw init phase-op --include state,config "${PHASE}"',),
            "research-phase command duplicated init",
        ),
        (
            _workflow_authority_text("map-research"),
            ("MAP_RESEARCH_FOCUS=", "MAP_FOCUS=", "MAP_FOCUS_PROVIDED=", "gpd --raw config get research_mode"),
            "map-research stale focus/config reads",
        ),
        (
            (COMMANDS_DIR / "map-research.md").read_text(encoding="utf-8"),
            ("gpd --raw init map-research",),
            "map-research command duplicated init",
        ),
        (
            (COMMANDS_DIR / "progress.md").read_text(encoding="utf-8"),
            ("ROADMAP=$(gpd --raw roadmap analyze)",),
            "progress command duplicated roadmap read",
        ),
    ):
        _ff(text, *fragments, context=context)

    _s(
        _workflow_authority_text("map-research"),
        "map-research provided focus semantics",
        "If `map_focus_provided` is true",
    )
    _sf(
        (COMMANDS_DIR / "progress.md").read_text(encoding="utf-8"),
        "Follow the included workflow exactly",
        "Do not duplicate",
        context="progress command wrapper semantics",
    )


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
    research_workflow = _workflow_authority_text("research-phase")
    research_command = (COMMANDS_DIR / "research-phase.md").read_text(encoding="utf-8")

    assert "Write to: {phase_dir}/{phase_number}-RESEARCH.md" in research_workflow
    _assert_command_delegates_to_workflow(
        research_command,
        "research-phase",
        semantic_fragments=("workflow", "staged init", "return routing"),
        stale_fragments=(
            "Write to: {phase_dir}/{phase_number}-RESEARCH.md",
            "Research file path: {phase_dir}/{phase_number}-RESEARCH.md",
        ),
    )
    assert "GPD/phases/${PHASE}-{slug}/${PHASE}-RESEARCH.md" not in research_workflow
    assert "GPD/phases/${PHASE}-{slug}/${PHASE}-RESEARCH.md" not in research_command


def test_audit_milestone_command_does_not_preload_raw_verification_globs() -> None:
    audit_command = (COMMANDS_DIR / "audit-milestone.md").read_text(encoding="utf-8")

    assert "find_files: GPD/phases/*/*SUMMARY.md" in audit_command
    assert "gpd phase list" in audit_command
    assert "gpd:show-phase <phase-number>" in audit_command
    assert "gpd show-phase <phase-number>" not in audit_command
    assert "find_files: GPD/phases/*/*-VERIFICATION.md" not in audit_command


def test_sensitivity_analysis_workflow_uses_canonical_cli_commands() -> None:
    workflow = (WORKFLOWS_DIR / "sensitivity-analysis.md").read_text(encoding="utf-8")

    _mf(
        workflow,
        "gpd --raw init progress --include state,config",
        "gpd --raw init phase-op",
        "gpd uncertainty add",
        "gpd commit",
        context="sensitivity-analysis canonical CLI commands",
    )
    _ff(
        workflow,
        "gpd CLI init progress",
        "gpd CLI init phase-op",
        "gpd CLI uncertainty add",
        "gpd CLI commit",
        context="sensitivity-analysis stale CLI wording",
    )


def test_phase_research_and_verification_surfaces_keep_anchor_checks_mandatory() -> None:
    phase_researcher = (AGENTS_DIR / "gpd-phase-researcher.md").read_text(encoding="utf-8")
    planner_agent = (AGENTS_DIR / "gpd-planner.md").read_text(encoding="utf-8")
    planner_execution = (REFERENCES_DIR / "planning" / "planner-execution-procedure.md").read_text(encoding="utf-8")
    planner_surface = planner_agent + "\n" + planner_execution
    verify_workflow = _workflow_authority_text("verify-work")
    verify_workflow_expanded = expand_at_includes(verify_workflow, REPO_ROOT / "src/gpd", "/runtime/")

    _assert_prompt_concepts(
        phase_researcher,
        {
            "active anchor section": ("## Active Anchor References",),
            "mandatory anchor inputs": ("contract-critical anchors", "mandatory inputs"),
        },
        context="phase researcher anchor checks",
    )
    assert "FORMALISM.md" in planner_execution
    _assert_prompt_concepts(
        planner_surface,
        {
            "derivation reference table row": ("derivation, analytical, symbolic", "CONVENTIONS.md", "FORMALISM.md"),
            "validation reference table row": ("validation, testing, benchmarks", "VALIDATION.md", "REFERENCES.md"),
        },
        context="planner anchor reference table",
    )
    _assert_prompt_concepts(
        verify_workflow,
        {
            "mandatory contract anchors": ("anchor obligations", "explicit"),
            "blocked contract repair": ("visible-but-blocked contract", "repaired", "authoritative verification scope"),
        },
        context="verify-work anchor checks",
    )
    assert "active_references" in verify_workflow
    assert "project_contract_gate" in verify_workflow
    assert "project_contract_validation" in verify_workflow
    assert "project_contract_load_info" in verify_workflow
    assert "gpd --raw verify suggest-checks --contract" in verify_workflow
    _assert_prompt_contracts(
        verify_workflow,
        fragment_count(
            "verify-work raw project contract gate block count",
            "**Project Contract Gate:** {project_contract_gate}",
            expected_count=2,
            context="verify-work contract gate block",
        ),
    )
    _s(
        verify_workflow_expanded,
        "expanded verify-work contract gate block",
        "**Project Contract Gate:** {project_contract_gate}",
    )
    _assert_prompt_concepts(
        verify_workflow,
        {
            "structured anchor source": (
                "effective_reference_intake",
                "structured source",
                "carry-forward anchors",
                "active_references",
                "compact routing handles",
            ),
        },
        context="verify-work effective reference intake",
    )


def test_phase_researcher_prompt_keeps_the_one_shot_handoff_and_return_contract_visible() -> None:
    phase_researcher = (AGENTS_DIR / "gpd-phase-researcher.md").read_text(encoding="utf-8")
    research_workflow = _workflow_authority_text("research-phase")
    research_command = (COMMANDS_DIR / "research-phase.md").read_text(encoding="utf-8")

    _mf(
        phase_researcher,
        "## RESEARCH COMPLETE",
        "## RESEARCH BLOCKED",
        "gpd_return:",
        "status: completed",
        "GPD/phases/03-spectral-form-factor/03-RESEARCH.md",
        context="phase researcher return envelope",
    )
    _mf(
        research_workflow,
        "references/orchestration/continuation-boundary.md",
        "expected_artifacts",
        "child-artifact-gate.md",
        "gpd_return.files_written",
        context="research workflow handoff artifact gate",
    )
    _s(research_workflow, "research workflow continuation handoff", "fresh continuation handoff")
    _assert_command_delegates_to_workflow(
        research_command,
        "research-phase",
        semantic_fragments=("workflow", "staged init", "return routing"),
    )
    assert 'gpd --raw init research-phase "${phase_arg}" --stage "${stage_name}"' in research_workflow


def test_workflows_surface_structured_proof_review_statuses() -> None:
    verify_workflow = _workflow_authority_text("verify-work")
    verify_phase = (WORKFLOWS_DIR / "verify-phase.md").read_text(encoding="utf-8")
    write_paper = _workflow_authority_text("write-paper")
    peer_review = _workflow_authority_text("peer-review")
    respond_to_referees = _workflow_authority_text("respond-to-referees")
    arxiv_submission = _workflow_authority_text("arxiv-submission")

    _m(
        verify_workflow,
        "verify-work proof review status",
        "phase_proof_review_status",
        "proof-review freshness summary",
    )
    for text, context in (
        (verify_phase, "verify-phase proof review status"),
        (write_paper, "write-paper proof review status"),
        (peer_review, "peer-review proof review status"),
        (respond_to_referees, "respond proof review status"),
        (arxiv_submission, "arxiv proof review status"),
    ):
        _mf(text, "derived_manuscript_proof_review_status", context=context)
    _s(verify_phase, "verify-phase proof review semantics", "manuscript-local proof-bearing artifact")
    # fmt: off
    _s(write_paper, "write-paper proof review semantics", "derived_manuscript_proof_review_status", "theorem-bearing claim freshness")
    # fmt: on
    _sf(peer_review, "theorem/proof freshness", context="peer-review proof review semantics")
    _s(
        respond_to_referees,
        "respond proof review semantics",
        "derived_manuscript_proof_review_status",
        "quick status summaries",
    )
    _s(arxiv_submission, "arxiv proof review semantics", "theorem-proof freshness", "resolved manuscript")


def test_verify_phase_and_gap_reverify_prompts_surface_contract_context_before_contract_checks() -> None:
    verify_phase = (WORKFLOWS_DIR / "verify-phase.md").read_text(encoding="utf-8")
    execute_phase = _workflow_authority_text("execute-phase")

    _mf(
        verify_phase,
        "project_contract_gate",
        "contract_intake",
        "effective_reference_intake",
        "active_reference_context",
        "reference_artifacts_content",
        "protocol_bundle_context",
        context="verify-phase contract context fields",
    )
    assert verify_phase.index("project_contract_gate") < verify_phase.index("gpd --raw verify suggest-checks")
    _mf(
        execute_phase,
        "{GPD_INSTALL_DIR}/workflows/verify-phase.md",
        "{GPD_INSTALL_DIR}/templates/verification-report.md",
        "{GPD_INSTALL_DIR}/templates/contract-results-schema.md",
        "gpd --raw init phase-op {PHASE_NUMBER}",
        "active_references",
        "protocol_bundle_load_manifest",
        "protocol_bundle_verifier_extensions",
        context="execute-phase verify-phase wiring",
    )


def test_templates_and_workflows_surface_contract_results_and_verdict_ledgers() -> None:
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
        "reload `{GPD_INSTALL_DIR}/templates/contract-results-schema.md` immediately before writing" in summary_template
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


def test_convention_templates_are_state_lock_projections_not_authorities() -> None:
    conventions = (TEMPLATES_DIR / "conventions.md").read_text(encoding="utf-8")
    notation = (TEMPLATES_DIR / "notation-glossary.md").read_text(encoding="utf-8")
    mapper = (AGENTS_DIR / "gpd-research-mapper.md").read_text(encoding="utf-8")
    infra = (REFERENCES_DIR / "orchestration" / "agent-infrastructure.md").read_text(encoding="utf-8")

    paper_writer = (AGENTS_DIR / "gpd-paper-writer.md").read_text(encoding="utf-8")

    _sf(
        conventions,
        "human-readable projection and audit surface",
        "not the source\n> of truth",
        context="conventions template projection semantics",
    )
    _m(
        conventions,
        "conventions template state lock pointer",
        "**Authoritative lock:** `GPD/state.json` -> `convention_lock`",
    )
    _s(notation, "notation glossary authority boundary", "This glossary is not a second convention authority")
    _mf(
        paper_writer,
        "`state.json.convention_lock` plus the `GPD/CONVENTIONS.md` / `GPD/NOTATION_GLOSSARY.md` projections",
        context="paper writer convention projection pointers",
    )
    _m(mapper, "research mapper convention lock command", "state.json.convention_lock` through `gpd convention set`")
    _f(mapper, "research mapper stale convention authority claim", "authoritative project-level convention lock")
    _assert_semantic_concept(
        infra,
        "agent infrastructure convention writers",
        required="Agents that write or verify equations",
        forbidden=("Direct-commit allowlist:", "Agents: project-researcher"),
        context="agent infrastructure convention-writer policy",
    )


def test_verification_report_top_level_status_excludes_partial_while_nested_contracts_keep_it() -> None:
    verification_template = (TEMPLATES_DIR / "verification-report.md").read_text(encoding="utf-8")

    _mf(
        verification_template,
        "Top-level `status` is limited to `passed`, `gaps_found`, `expert_needed`, or `human_needed`",
        "Nested `contract_results` entries",
        context="verification report status enum boundary",
    )
    _assert_semantic_concept(
        verification_template,
        "nested contract partial status remains valid",
        required="including `partial` when a specific claim, deliverable, or acceptance test is only partly satisfied",
        forbidden="use `partial`, `gaps_found`",
        context="verification report nested contract status boundary",
    )


def test_plan_tool_preflight_surfaces_across_planning_and_execution_prompts() -> None:
    phase_prompt = (TEMPLATES_DIR / "phase-prompt.md").read_text(encoding="utf-8")
    planner_agent = (AGENTS_DIR / "gpd-planner.md").read_text(encoding="utf-8")
    planner_prompt_template = (TEMPLATES_DIR / "planner-subagent-prompt.md").read_text(encoding="utf-8")
    plan_checker = (AGENTS_DIR / "gpd-plan-checker.md").read_text(encoding="utf-8")
    executor_agent = (AGENTS_DIR / "gpd-executor.md").read_text(encoding="utf-8")
    execute_plan = (WORKFLOWS_DIR / "execute-plan.md").read_text(encoding="utf-8")
    execute_phase = _workflow_authority_text("execute-phase")
    tooling_ref = (REFERENCES_DIR / "tooling" / "tool-integration.md").read_text(encoding="utf-8")
    summary_template = (TEMPLATES_DIR / "summary.md").read_text(encoding="utf-8")
    verification_template = (TEMPLATES_DIR / "verification-report.md").read_text(encoding="utf-8")
    research_verification = (TEMPLATES_DIR / "research-verification.md").read_text(encoding="utf-8")
    verify_workflow = _workflow_authority_text("verify-work")
    verify_phase = (WORKFLOWS_DIR / "verify-phase.md").read_text(encoding="utf-8")
    verifier_agent = (AGENTS_DIR / "gpd-verifier.md").read_text(encoding="utf-8")
    compare_workflow = (WORKFLOWS_DIR / "compare-experiment.md").read_text(encoding="utf-8")
    comparison_template = (TEMPLATES_DIR / "paper" / "experimental-comparison.md").read_text(encoding="utf-8")
    internal_comparison_template = (TEMPLATES_DIR / "paper" / "internal-comparison.md").read_text(encoding="utf-8")

    _mf(
        phase_prompt,
        "# tool_requirements: # Optional machine-checkable specialized tools. Omit entirely if none.",
        '#     tool: "command"',
        '#     command: "pdflatex --version"',
        "`required` defaults to true when omitted",
        "Quick contract rules:",
        context="phase prompt tool requirements",
    )
    _mf(
        planner_agent,
        "machine-checkable prerequisites in `tool_requirements`",
        "validator-accepted tools (`wolfram`, `command`)",
        "`command` tools require a `command` field",
        "`required` defaults to `true`",
        context="planner agent tool requirements",
    )
    _mf(plan_checker, "declare them in `tool_requirements`", context="plan checker tools")
    _m(
        executor_agent,
        "executor plan-preflight",
        "Run `gpd validate plan-preflight <PLAN.md path>` from the local CLI.",
    )
    _m(
        execute_plan,
        "execute-plan plan-preflight",
        'PLAN_PREFLIGHT=$(gpd --raw validate plan-preflight "${PLAN_PATH}")',
    )
    _ff(execute_plan, "gpd validate plan-preflight <PLAN.md>", context="execute-plan stale preflight spelling")
    _s(phase_prompt, "phase-prompt tool fallback semantics", "fallback", "missing required tool", "non-blocking")
    _mf(
        execute_phase,
        'PLAN_PREFLIGHT=$(gpd --raw validate plan-preflight "$plan")',
        "Repair invalid plans with `gpd:plan-phase {N}`",
        context="execute-phase plan-preflight",
    )
    _sf(
        planner_prompt_template,
        "`tool_requirements`",
        "`gpd validate plan-preflight <PLAN.md>`",
        "execution-ready",
        context="planner template plan-preflight",
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
    assert plan_phase_manifest.stages[0].loaded_authorities == ("workflows/plan-phase/phase-bootstrap.md",)
    assert "templates/planner-subagent-prompt.md" in plan_phase_manifest.stage("planner_authoring").loaded_authorities
    checker_conditionals = {
        authority
        for conditional in plan_phase_manifest.stage("checker_revision").conditional_authorities
        for authority in conditional.authorities
    }
    assert "templates/planner-subagent-prompt.md" in checker_conditionals

    _sf(
        execute_phase,
        "`VERIFICATION.md`",
        "schema-owned ledgers",
        "`plan_contract_ref`",
        "`contract_results`",
        "`comparison_verdicts`",
        "`suggested_contract_checks`",
        "verifier-local aliases",
        context="execute-phase verification contract fields",
    )
    _mf(tooling_ref, "declare it as `tool: wolfram` in `tool_requirements`", context="tool integration requirements")
    _ff(
        summary_template,
        "must_haves",
        "verification_inputs",
        "contract_evidence",
        "independently_confirmed",
        context="summary removed verification aliases",
    )
    _sf(
        summary_template,
        "`suggested_contract_checks`",
        "verification-only",
        "does not belong in summaries",
        context="summary contract fields",
    )
    _sf(
        verification_template,
        "contract_results",
        "machine-readable surface",
        "schema-owned ledgers",
        "verification-side `suggested_contract_checks`",
        context="verification report schema fields",
    )
    _assert_prompt_contracts(
        research_verification,
        machine_exact(
            "research verification report template path",
            "{GPD_INSTALL_DIR}/templates/verification-report.md",
        ),
        semantic_anchor(
            "research verification uses canonical frontmatter contract",
            ("canonical verification frontmatter contract",),
            context="research verification template",
        ),
    )
    _mf(
        research_verification,
        "status: gaps_found",
        "# Allowed status values: passed|gaps_found|expert_needed|human_needed",
        "comparison_verdicts:",
        "subject_role: decisive",
        "comparison_kind: benchmark",
        "`comparison_kind`: benchmark|prior_work|experiment|cross_method|baseline|other",
        "suggested_contract_checks:",
        "uncertainty_markers:",
        context="research verification schema examples",
    )
    _assert_prompt_contracts(
        verify_workflow,
        fragment_count(
            "verify-work planner template authority count",
            "templates/planner-subagent-prompt.md",
            expected_count=2,
            context="verify-work planner wiring",
        ),
        fragment_count(
            "verify-work planner role instruction count",
            "First, read {GPD_AGENTS_DIR}/gpd-planner.md for your role and instructions.",
            expected_count=1,
            context="verify-work planner wiring",
        ),
    )
    _mf(
        verify_workflow,
        "tool_requirements",
        "gap_closure",
        "Use `templates/planner-subagent-prompt.md`",
        "Run `gpd validate verification-contract",
        context="verify-work planner and schema wiring",
    )
    _ff(
        verify_workflow,
        "## CHECKPOINT REACHED",
        "The shared planner template owns the canonical planning policy and contract gate.",
        "The shared planner template owns the canonical planning and revision policy.",
        "status: gaps_found",
        "uncertainty_markers:",
        "Allowed body enum values:",
        "suggested_contract_checks:",
        "`suggested_contract_check`",
        "independently_confirmed",
        context="verify-work stale duplicated schema content",
    )
    _mf(
        verify_phase,
        "Return status (`passed` | `gaps_found` | `expert_needed` | `human_needed`)",
        "gpd verification-report skeleton PLAN.md --write --output",
        "contract_results",
        "Verification targets must stay user-visible",
        "request_template",
        "required_request_fields",
        "supported_binding_fields",
        "gpd --raw verify contract-check --payload",
        "copy the returned `check_key` into the frontmatter `check` field",
        "schema_required_request_fields",
        "schema_required_request_anyof_fields",
        "project_dir",
        context="verify-phase schema and helper wiring",
    )
    _sf(
        verify_phase,
        "helper owns frontmatter shape",
        "`plan_contract_ref`",
        "`contract_results`",
        "`comparison_verdicts`",
        "`suggested_contract_checks`",
        "validation",
        context="verify-phase verification helper",
    )
    _ff(
        verify_phase,
        "frontmatter (phase/timestamp/status/score",
        "independently_confirmed",
        "`suggested_contract_check`",
        "must_haves",
        context="verify-phase removed schema aliases",
    )
    _mf(
        verifier_agent,
        "Use the verification-report helper to serialize the gap ledger",
        "The body must still make every gap actionable",
        "Verification Status:** {passed | gaps_found | expert_needed | human_needed}",
        "schema_required_request_fields",
        "schema_required_request_anyof_fields",
        "project_dir",
        context="verifier schema helper wiring",
    )
    _f(verifier_agent, "verifier removed schema aliases", "Each gap has: `subject_kind`", "`suggested_contract_check`")
    _mf(
        execute_plan,
        "`contract_results` is authoritative.",
        "project_contract_validation",
        "project_contract_load_info",
        "visible-but-blocked contract is still not an approved execution contract",
        context="execute-plan contract results wiring",
    )
    _sf(
        execute_plan,
        "Autonomy mode",
        "profile",
        "do NOT relax contract-result emission",
        "comparison_verdicts`",
        "decisive",
        "required or attempted",
        "emit `verdict: inconclusive`",
        "`verdict: tension`",
        "instead of omitting",
        context="execute-plan comparison verdicts",
    )
    _assert_prompt_contracts(
        execute_plan,
        machine_exact(
            "execute-plan contract results schema path",
            "{GPD_INSTALL_DIR}/templates/contract-results-schema.md",
        ),
        semantic_anchor(
            "execute-plan reapplies contract-results schema before frontmatter",
            ("Immediately before writing frontmatter", "re-open", "apply it literally"),
            context="execute-plan contract results",
        ),
    )
    _mf(
        compare_workflow,
        "comparison_verdicts",
        "project_contract_load_info",
        "project_contract_validation",
        "selected_protocol_bundle_ids",
        "protocol_bundle_context",
        "active_reference_context",
        "subject_kind: claim",
        "subject_role: decisive",
        "comparison_kind: experiment",
        "verdict: pass",
        "omit `protocol_bundle_ids` and `bundle_expectations` entirely",
        context="compare-experiment contract wiring",
    )
    _s(
        compare_workflow,
        "compare-experiment contract gate",
        "approved contract",
        "`project_contract_gate.authoritative`",
        "true",
    )
    _ff(
        compare_workflow,
        "protocol_bundle_ids (optional):",
        "bundle_expectations (optional):",
        "subject_kind: claim|deliverable|acceptance_test|reference",
        "comparison_kind: benchmark|prior_work|experiment|cross_method|baseline|other",
        "verdict: pass | tension | fail | inconclusive",
        context="compare-experiment removed comparison aliases",
    )
    for context, text, comparison_kind in (
        ("experimental comparison template", comparison_template, "experiment"),
        ("internal comparison template", internal_comparison_template, "cross_method"),
    ):
        _mf(
            text,
            "`comparison_verdicts` is a closed schema",
            "subject_kind: claim",
            "subject_role: decisive",
            f"comparison_kind: {comparison_kind}",
            "verdict: pass",
            "omit `protocol_bundle_ids` and `bundle_expectations` entirely",
            context=context,
        )
        _ff(
            text,
            "protocol_bundle_ids (optional):",
            "bundle_expectations (optional):",
            "subject_kind: claim|deliverable|acceptance_test|reference",
            "comparison_kind: benchmark|prior_work|experiment|cross_method|baseline|other",
            "verdict: pass | tension | fail | inconclusive",
            "verdict: pass|tension|fail|inconclusive",
            context=context,
        )
    _s(
        executor_agent,
        "executor contract results",
        "Profiles",
        "autonomy modes",
        "do NOT relax contract-result emission",
    )
    _sf(
        verifier_agent,
        "Use claim IDs",
        "deliverable IDs",
        "acceptance test IDs",
        "reference IDs",
        "forbidden proxy IDs",
        "directly from the `contract` block",
        context="verifier contract IDs",
    )


def test_execute_phase_workflow_surfaces_project_contract_validation_gate() -> None:
    execute_workflow = _workflow_authority_text("execute-phase")
    execute_manifest = load_workflow_stage_manifest("execute-phase")
    bootstrap_fields = set(execute_manifest.stage("phase_bootstrap").required_init_fields)

    assert {"project_contract_validation", "project_contract_load_info"} <= bootstrap_fields
    assert "project_contract_gate" in execute_workflow
    _mf(
        execute_workflow,
        "contract_gate_stop:",
        "trigger=blocked load | invalid validation | non-authoritative gate",
        "primary=gpd:sync-state|gpd:new-project",
        "rerun=gpd:execute-phase ${PHASE_ARG}",
        context="execute-phase contract gate stop tuple",
    )

    # The claim<->deliverable alignment precheck is wired into execute-phase.md
    # and references the helpers/CLI provided by the contract alignment layer.
    alignment_step = _extract_between(
        execute_workflow,
        '<step name="claim_deliverable_alignment_check">',
        "</step>",
    )
    _mf(
        alignment_step,
        "gpd contract alignment-status",
        "gpd contract fingerprint",
        "gpd contract context-fingerprint",
        "gpd contract alignment-summary",
        'gpd contract record-alignment --contract-hash "$CONTRACT_HASH" --context-hash "$CONTEXT_HASH"',
        "claim_deliverable_alignment_check: skipped (already confirmed this session)",
        context="execute-phase claim deliverable alignment commands",
    )


def test_execute_and_autonomous_gate_execution_before_plan_work() -> None:
    execute_phase = _workflow_authority_text("execute-phase")
    autonomous = _autonomous_authority_text()

    execute_gate = _extract_between(
        execute_phase,
        '<step name="validate_selected_plans_before_execution" priority="first">',
        "</step>",
    )
    _assert_prompt_concepts(
        execute_gate,
        {
            "blocks execution-side work before validation": (
                "workspace scripts",
                "numerical computations",
                "task dispatches",
                "subagents",
                "artifact writes",
            ),
            "plan repair route": ("gpd:plan-phase {N}", "Repair invalid plans"),
        },
        context="execute-phase selected-plan gate",
    )
    _mf(
        execute_gate,
        'gpd validate plan-contract "$plan"',
        'if ! gpd verify plan "$plan"; then',
        'PLAN_PREFLIGHT=$(gpd --raw validate plan-preflight "$plan")',
        'gpd verify references "$plan"',
        'gpd phase validate-waves "$phase_number"',
        context="execute-phase selected-plan gate commands",
    )

    _assert_prompt_concepts(
        autonomous,
        {
            "lifecycle gate before execute-phase": (
                "lifecycle gate",
                "execute-phase",
            ),
            "stop before execution-side work": (
                "stop before",
                "workspace scripts",
                "numerical computations",
                "task dispatches",
                "subagents",
                "artifact writes",
            ),
            "repair goes through child commands": ("gpd:plan-phase ${PHASE_NUM}", "gpd:execute-phase ${PHASE_NUM}"),
        },
        context="autonomous execution-before-plan gate",
    )
    _mf(
        autonomous,
        'gpd --raw validate lifecycle-contract-gate execute-phase "${PHASE_NUM}"',
        'gpd --raw validate lifecycle-contract-gate plan-phase "${PHASE_NUM}"',
        "gpd:plan-phase",
        "gpd:execute-phase",
        context="autonomous lifecycle contract gate commands",
    )
    _ff(execute_phase, "--revise", context="execute-phase stale revise flag")
    _ff(autonomous, "--revise", context="autonomous stale revise flag")


def test_execute_phase_and_execute_plan_use_staged_execution_bootstrap_instead_of_monolithic_init() -> None:
    execute_workflow = _workflow_authority_text("execute-phase")
    execute_plan = (WORKFLOWS_DIR / "execute-plan.md").read_text(encoding="utf-8")

    _assert_workflow_calls_staged_init_for_manifest_stages("execute-phase", execute_workflow)
    assert 'gpd --raw init execute-phase "${phase}" --include state,config' not in execute_plan
    assert 'gpd --raw init execute-phase "${phase}" --stage phase_bootstrap' in execute_plan
    assert 'gpd --raw init execute-phase "${phase}" --stage phase_classification' in execute_plan
    assert 'gpd --raw init execute-phase "${phase}" --stage wave_planning' in execute_plan
    assert 'gpd --raw init execute-phase "${phase}" --stage aggregate_and_verify' in execute_plan


def test_execute_phase_and_execute_plan_surface_required_reference_and_state_ownership_guidance() -> None:
    execute_command = (COMMANDS_DIR / "execute-phase.md").read_text(encoding="utf-8")
    execute_workflow = _workflow_authority_text("execute-phase")
    execute_plan = (WORKFLOWS_DIR / "execute-plan.md").read_text(encoding="utf-8")

    _mf(
        execute_workflow,
        "{GPD_INSTALL_DIR}/references/orchestration/artifact-surfacing.md",
        "gpd apply-return-updates",
        context="execute-phase state ownership wiring",
    )
    _mf(
        execute_plan,
        "{GPD_INSTALL_DIR}/references/execution/github-lifecycle.md",
        "continuation_update",
        context="execute-plan lifecycle reference wiring",
    )
    _sf(
        execute_plan,
        "substitute the repository's actual default branch and remote names",
        context="execute-plan branch remote substitution guidance",
    )
    _s(execute_command, "execute command state ownership summary", "update state, resume")
    _sf(
        execute_workflow,
        "orchestrator applies them",
        "after each agent completes",
        "By the time the wave-complete report is emitted",
        context="execute-phase return update timing",
    )
    _f(execute_command, "execute command stale state update prose", "STATE.md is updated after each wave completes")
    _f(execute_plan, "execute-plan stale session update key", "session_update")


def test_verification_prompts_keep_suggested_contract_check_bindings_schema_tight() -> None:
    verification_template = (TEMPLATES_DIR / "verification-report.md").read_text(encoding="utf-8")
    research_verification = (TEMPLATES_DIR / "research-verification.md").read_text(encoding="utf-8")
    verify_workflow = _workflow_authority_text("verify-work")
    verifier_agent = (AGENTS_DIR / "gpd-verifier.md").read_text(encoding="utf-8")

    _f(verification_template, "verification report stale suggested subject fallback", 'suggested_subject_id: ""')
    _f(
        research_verification,
        "research verification stale suggested subject fallback",
        'suggested_subject_id: [contract id or ""]',
    )
    _mf(
        research_verification,
        "suggested_subject_id: acceptance-test-main",
        "suggested_subject_id: reference-main",
        "acceptance-test-main",
        context="research verification suggested contract check ids",
    )
    _ff(
        verify_workflow,
        'suggested_subject_id: [contract id or ""]',
        "suggested_subject_id: acceptance-test-main",
        "suggested_subject_id: reference-main",
        context="verify-work avoids example suggested contract ids",
    )
    _mf(
        verification_template,
        "suggested_contract_checks",
        "{GPD_INSTALL_DIR}/templates/contract-results-schema.md",
        context="verification report suggested contract schema wiring",
    )
    _sf(
        verification_template,
        "Reload `{GPD_INSTALL_DIR}/templates/contract-results-schema.md` immediately before writing",
        "proof-audit rules in the canonical schema",
        context="verification report suggested contract schema semantics",
    )
    _mf(
        verifier_agent,
        "{GPD_INSTALL_DIR}/templates/verification-report.md",
        "{GPD_INSTALL_DIR}/templates/contract-results-schema.md",
        "Verification Status:** {passed | gaps_found | expert_needed | human_needed}",
        context="verifier agent schema path and status wiring",
    )
    _ff(
        verifier_agent,
        "@{GPD_INSTALL_DIR}/templates/verification-report.md",
        "@{GPD_INSTALL_DIR}/templates/contract-results-schema.md",
        "Each gap has: `subject_kind`",
        context="verifier agent stale schema include and gap aliases",
    )
    _sf(
        verifier_agent,
        "do not inline or recreate their full YAML",
        "proof-audit linkage",
        "verification-report helper to serialize the gap ledger",
        "The body must still make every gap actionable",
        context="verifier agent suggested contract check semantics",
    )


def test_lane5_prompt_examples_keep_schema_valid_contract_fields_visible() -> None:
    planner = (AGENTS_DIR / "gpd-planner.md").read_text(encoding="utf-8")
    plan_checker = (AGENTS_DIR / "gpd-plan-checker.md").read_text(encoding="utf-8")
    parameter_sweep = (WORKFLOWS_DIR / "parameter-sweep.md").read_text(encoding="utf-8")
    research_verification = (TEMPLATES_DIR / "research-verification.md").read_text(encoding="utf-8")
    verify_work = _workflow_authority_text("verify-work")
    verifier = (AGENTS_DIR / "gpd-verifier.md").read_text(encoding="utf-8")
    executor_example = (REFERENCES_DIR / "execution" / "executor-worked-example.md").read_text(encoding="utf-8")
    phase_prompt = _expand_prompt_surface(TEMPLATES_DIR / "phase-prompt.md")

    _mf(planner, "context_intake:", 'must_read_refs: ["ref-textbook"]', context="planner benchmark intake")
    _mf(phase_prompt, 'references: ["ref-main"]', context="phase prompt reference example")
    _mf(
        plan_checker,
        "context_intake:",
        "why_it_matters:",
        "required_actions: [read, compare, cite]",
        context="plan checker benchmark intake",
    )
    _sf(plan_checker, "procedure:", "computed value", "benchmark anchor", "tolerance", context="plan checker benchmark")
    _mf(
        parameter_sweep,
        "context_intake:",
        "must_read_refs: [ref-sweep-anchor]",
        context="parameter sweep reference intake",
    )
    _mf(
        research_verification,
        "reference-main",
        "acceptance-test-main",
        "linked_ids: [deliverable-main, acceptance-test-main, reference-main]",
        "evidence:\n        - verifier: gpd-verifier",
        'evidence_path: "GPD/phases/01-benchmark/01-VERIFICATION.md"',
        "started:",
        "updated:",
        context="research verification benchmark example",
    )
    _ff(research_verification, "test-benchmark", context="research verification invalid benchmark id")
    _ff(verify_work, "reference-main", "acceptance-test-main", "test-benchmark", context="verify-work staged inputs")
    _mf(
        verifier,
        "{GPD_INSTALL_DIR}/templates/verification-report.md",
        "{GPD_INSTALL_DIR}/templates/contract-results-schema.md",
        context="verifier lightweight schema paths",
    )
    _ff(
        verifier,
        "@{GPD_INSTALL_DIR}/templates/verification-report.md",
        "@{GPD_INSTALL_DIR}/templates/contract-results-schema.md",
        "reference-main",
        "acceptance-test-main",
        "test-benchmark",
        context="verifier lazy schema and no example leakage",
    )
    _mf(
        executor_example,
        "deliverables:",
        "references:",
        'reference_id: "reference-qed-benchmark"',
        context="executor worked example reference fields",
    )
    assert "deliverable-self-energy-derivation" in executor_example


def test_verification_prompt_wiring_rejects_invalid_reference_and_proxy_scaffolds(tmp_path: Path) -> None:
    phase_dir = tmp_path / "GPD" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        _plan_with_contract_text(),
        encoding="utf-8",
    )
    verification_path = phase_dir / "01-VERIFICATION.md"
    verification_path.write_text(
        (CONTRACT_RESULT_FIXTURES / "verification_with_contract_results.md")
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
        _plan_with_contract_text(),
        encoding="utf-8",
    )
    verification_path = phase_dir / "01-VERIFICATION.md"
    verification_path.write_text(
        (CONTRACT_RESULT_FIXTURES / "verification_with_contract_results.md")
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


def test_verifier_entry_points_use_cli_contract_check_commands() -> None:
    verify_work_meta, _ = _parse_frontmatter((COMMANDS_DIR / "verify-work.md").read_text(encoding="utf-8"))
    verifier_meta, verifier_body = _parse_frontmatter((AGENTS_DIR / "gpd-verifier.md").read_text(encoding="utf-8"))

    verify_work_tools = verify_work_meta.get("allowed-tools", [])
    verifier_tools = _parse_tools(verifier_meta.get("tools"))

    assert "shell" in verify_work_tools
    assert "shell" in verifier_tools
    for tool_name in (*verify_work_tools, *verifier_tools):
        assert not str(tool_name).startswith("mcp__gpd_")
    for cli_invocation in (
        "gpd --raw verify suggest-checks",
        "gpd --raw verify contract-check",
        "gpd --raw verify bundle-checklist",
    ):
        assert cli_invocation in verifier_body


def test_manuscript_documentation_uses_current_manuscript_root_paths_only() -> None:
    explain = (WORKFLOWS_DIR / "explain.md").read_text(encoding="utf-8")
    manuscript_outline = (TEMPLATES_DIR / "paper" / "manuscript-outline.md").read_text(encoding="utf-8")
    execute_phase = _workflow_authority_text("execute-phase")
    figure_tracker = (TEMPLATES_DIR / "paper" / "figure-tracker.md").read_text(encoding="utf-8")

    assert "GPD/paper/" not in explain
    assert "GPD/paper/" not in manuscript_outline
    assert "paper/EXPERIMENTAL_COMPARISON.md" in execute_phase
    assert "${PAPER_DIR}/EXPERIMENTAL_COMPARISON.md" not in execute_phase
    assert "GPD/paper/EXPERIMENTAL_COMPARISON.md" not in execute_phase
    assert "fig-main.pdf" not in figure_tracker


def test_explain_surfaces_keep_workspace_rooted_outputs_and_honest_standalone_targeting() -> None:
    explain_command = (COMMANDS_DIR / "explain.md").read_text(encoding="utf-8")
    explain_workflow = (WORKFLOWS_DIR / "explain.md").read_text(encoding="utf-8")

    _sf(
        explain_command,
        "standalone question with an explicit topic",
        "empty in standalone mode",
        "ask the user to rerun with an explicit concept/topic",
        context="explain command honest standalone targeting",
    )
    _m(explain_command, "explain command workspace-rooted outputs", "GPD/explanations/")
    _sf(
        explain_workflow,
        "standalone explanations only when the standalone request already names an explicit target",
        "Do not promise that an empty standalone launch can be clarified later",
        context="explain workflow honest standalone targeting",
    )
    _m(explain_workflow, "explain workflow workspace-rooted outputs", "GPD/explanations/")


def test_publication_workflows_describe_recursive_manuscript_tree_inputs() -> None:
    arxiv_submission = _workflow_authority_text("arxiv-submission")
    write_paper = _workflow_authority_text("write-paper")
    respond = _workflow_authority_text("respond-to-referees")

    _m(arxiv_submission, "arxiv submission manuscript tree exact tokens", "`\\input{}`", "`\\include{}`", "`paper/`")
    _sf(
        arxiv_submission,
        "every source file is packaged",
        "stage the package in a temporary submission tree",
        context="arxiv submission recursive manuscript packaging",
    )
    _m(write_paper, "write-paper recursive manuscript tree tokens", "`.tex`", "`${PAPER_DIR}`")
    _s(write_paper, "write-paper recursive manuscript tree semantics", "Manuscript tree", "recursively")
    _m(respond, "respond-to-referees manuscript tree root token", "`${PAPER_DIR}`")
    _s(
        respond,
        "respond-to-referees recursive manuscript tree semantics",
        "resolved section file within the manuscript tree",
    )


def test_review_and_verification_prompts_explicitly_surface_schema_sources_and_contract_context() -> None:
    peer_review = _workflow_authority_text("peer-review")
    peer_review_command = (COMMANDS_DIR / "peer-review.md").read_text(encoding="utf-8")
    verify_command = (COMMANDS_DIR / "verify-work.md").read_text(encoding="utf-8")
    verify_workflow = _workflow_authority_text("verify-work")
    write_paper = _workflow_authority_text("write-paper")
    write_paper_command = (COMMANDS_DIR / "write-paper.md").read_text(encoding="utf-8")
    respond_to_referees = _workflow_authority_text("respond-to-referees")
    sync_state = _workflow_authority_text("sync-state")
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

    _assert_fragment_groups(
        (
            _sf,
            peer_review,
            "peer-review carry-forward context",
            "Reader-visible claims",
            "surfaced evidence",
            "first-class",
            "compact `REVIEW_CARRY_FORWARD`",
            "before spawning panel stages",
            "Do not repeat",
            "full contract/reference payloads",
            "every child prompt",
        ),
        (
            _mf,
            peer_review,
            "peer-review contract context",
            "effective_reference_intake",
            "project_contract_validation",
            "project_contract_load_info",
            "Carry-forward packet: {REVIEW_CARRY_FORWARD}",
            "project_contract_gate.authoritative",
        ),
    )
    _f(peer_review, "peer-review carry-forward payload", "reference artifacts content {reference_artifacts_content}")
    _assert_prompt_contracts(
        peer_review,
        semantic_anchor(
            "peer-review treats project contract gate as authoritative only when approved",
            (
                "`project_contract_gate`",
                "authoritative",
                "`project_contract_gate.authoritative`",
                "diagnostics/context",
                "carry-forward evidence",
            ),
            context="peer-review project contract gate",
        ),
        forbidden_duplicate(
            "peer-review single contract gate authority note",
            "Treat `project_contract_gate` as authoritative.",
            context="peer-review project contract gate",
        ),
    )
    _assert_fragment_groups(
        (
            _mf,
            respond_to_referees,
            "respond-to-referees contract gate",
            "project_contract_gate",
            "project_contract_load_info",
            "project_contract_validation",
            "Treat the project contract as authoritative only when",
            "`project_contract_gate.authoritative` is true",
        ),
        (
            _ff,
            peer_review_command,
            "peer-review command wrapper schema bodies",
            "templates/paper/review-ledger-schema.md",
            "templates/paper/referee-decision-schema.md",
            "references/publication/peer-review-panel.md",
        ),
        (
            _ff,
            verify_command,
            "verify-work command wrapper schema bodies",
            "templates/verification-report.md",
            "templates/contract-results-schema.md",
            "Severity Classification",
            "One check at a time, plain text responses, no interrogation.",
            "Physics verification is not binary:",
            "For deeper focused analysis",
        ),
    )
    _assert_command_delegates_to_workflow(
        verify_command,
        "verify-work",
        semantic_fragments=(
            "staged workflow authorities own",
            "detailed check taxonomy",
            "bootstraps the canonical verification surface",
            "delegates the physics checks",
        ),
        context="verify-work command wrapper",
    )
    _sf(
        verify_workflow,
        "Load the staged researcher-session scaffold",
        "session overlay frontmatter",
        "compatible",
        "authoritative verification report",
        context="verify-work interactive validation stage",
    )
    interactive_conditionals = tuple(
        authority
        for conditional in interactive_validation.conditional_authorities
        for authority in conditional.authorities
    )
    assert {"templates/verification-report.md", "templates/contract-results-schema.md"} <= set(interactive_conditionals)
    assert any(
        "references/verification/meta/verification-independence.md" in row.authorities
        for row in inventory_build.conditional_authorities
    )
    _assert_fragment_groups(
        (
            _ff,
            write_paper_command,
            "write-paper command wrapper schema bodies",
            "templates/paper/review-ledger-schema.md",
            "templates/paper/referee-decision-schema.md",
            "references/publication/peer-review-panel.md",
        ),
        (
            _mf,
            write_paper,
            "write-paper reproducibility schema",
            "Canonical schema for `${PAPER_DIR}/reproducibility-manifest.json`:",
        ),
        (
            _mf,
            sync_state,
            "sync-state reconciliation",
            "Canonical reconciliation contract:",
            "state-json-schema.md",
            "state.json is authoritative for structured fields",
            "optional_commit",
            'gpd --raw --cwd "$PROJECT_ROOT" state repair-sync',
        ),
        (
            _ff,
            sync_state,
            "sync-state stale reconciliation flow",
            "gpd --raw state snapshot",
            "Proceed with reconciliation? (y/n)",
            "determine which source is more recent",
        ),
        (_sf, peer_review, "peer-review blocked contract", "repair it before retrying"),
        (
            _mf,
            review_reader,
            "review reader schema paths",
            "${REVIEW_ROOT}/CLAIMS{round_suffix}.json",
            "${REVIEW_ROOT}/STAGE-reader{round_suffix}.json",
        ),
    )
    _s(sync_state, "sync-state reconciliation", "workflow", "fail-closed")
    _s(sync_state, "sync-state reconciliation", "Do not", "move or delete files", "prompt")
    _assert_fragment_groups(
        (
            _sf,
            review_reader,
            "review reader schema visibility",
            "shared source of truth",
            "`ClaimIndex`",
            "`StageReviewReport`",
            "Stage 1",
            "${REVIEW_ROOT}/CLAIMS{round_suffix}.json",
        ),
        (
            _sf,
            review_reader,
            "review reader claim structure",
            "theorem kind",
            "explicit hypotheses",
            "free target parameters",
            "theorem-like claims",
        ),
        (
            _sf,
            review_reader,
            "review reader findings",
            "`findings`",
            "overclaiming",
            "missing promised deliverables",
            "claim-structure blockers",
        ),
    )
    for label, text, output_path in (
        ("literature", review_literature, "${REVIEW_ROOT}/STAGE-literature{round_suffix}.json"),
        ("math", review_math, "${REVIEW_ROOT}/STAGE-math{round_suffix}.json"),
        ("physics", review_physics, "${REVIEW_ROOT}/STAGE-physics{round_suffix}.json"),
        ("significance", review_significance, "${REVIEW_ROOT}/STAGE-interestingness{round_suffix}.json"),
    ):
        _mf(text, output_path, context=f"review {label} output path")
        _s(text, f"review {label} schema visibility", "shared source of truth", "`StageReviewReport` contract")
    _assert_fragment_groups(
        (
            _sf,
            review_literature,
            "literature review findings",
            "`findings`",
            "claimed advance",
            "prior work",
            "novelty assessment",
            "`reject`",
            "`major_revision`",
        ),
        (
            _sf,
            review_math,
            "math review recommendation ceiling",
            "theorem-bearing Stage 1 claim",
            "exactly one `proof_audits[]` entry",
            "`claim_id`",
            "`claims_reviewed`",
            "Do not emit proof audits",
            "unreviewed claims",
            "do not repeat `claim_id` values",
            "theorem-to-proof audit",
            "what the proof actually uses",
            "silently specializes away",
            "coverage gaps",
            "`recommendation_ceiling`",
            "`major_revision`",
            "`reject`",
            "central theorem-proof gaps",
        ),
        (
            _sf,
            review_physics,
            "physics review findings",
            "`findings`",
            "physical assumptions",
            "regime of validity",
            "supported physical conclusions",
            "overstated connections",
        ),
        (
            _sf,
            review_physics,
            "physics review recommendation ceiling",
            "`recommendation_ceiling`",
            "`major_revision`",
            "physical conclusions",
            "actual evidence",
        ),
        (
            _sf,
            review_significance,
            "significance review findings",
            "`findings`",
            "why the result might matter",
            "venue fit",
            "claim proportionality",
        ),
        (
            _sf,
            review_significance,
            "significance review recommendation ceiling",
            "`recommendation_ceiling`",
            "`reject`",
            "significance",
            "venue fit",
            "`major_revision`",
            "technically competent",
            "physically uninteresting",
            "overclaimed",
        ),
    )
    for text in (review_reader, review_literature, review_math, review_physics, review_significance):
        _f(
            text,
            "review agent schema prose duplication",
            "Required schema for",
            "closed schema; do not invent extra keys",
        )
    _m(referee, "referee panel reopen", "re-open `{GPD_INSTALL_DIR}/references/publication/peer-review-panel.md`")


def test_peer_review_prompt_includes_concise_stage_map_for_users() -> None:
    peer_review_command = (COMMANDS_DIR / "peer-review.md").read_text(encoding="utf-8")
    peer_review_workflow = _workflow_authority_text("peer-review")

    _assert_prompt_concepts(
        peer_review_command,
        {
            "user-facing stage map": ("announcing the panel", "each stage", "concise sentence"),
        },
        context="peer-review command stage map",
    )
    _assert_prompt_concepts(
        peer_review_workflow,
        {
            "pre-spawn stage map": ("Before spawning", "reviewer", "concise stage map"),
        },
        context="peer-review workflow stage map",
    )
    stage_map = {
        "Stage 1": ("Stage 1", "claims"),
        "Stages 2-3": ("Stages 2-3", "prior work", "mathematical soundness", "parallel"),
        "Stage 4": ("Stage 4", "physical interpretation", "supported"),
        "Stage 5": ("Stage 5", "significance", "venue fit"),
        "Stage 6": ("Stage 6", "synthesizes", "final recommendation"),
    }
    _assert_prompt_concepts(peer_review_command, stage_map, context="peer-review command stage roles")
    _assert_prompt_concepts(peer_review_workflow, stage_map, context="peer-review workflow stage roles")
    _assert_ordered_prompt_fragments(
        peer_review_command,
        ("Stage 1", "Stages 2-3", "Stage 4", "Stage 5", "Stage 6"),
        context="peer-review command stage order",
    )
    _assert_ordered_prompt_fragments(
        peer_review_workflow,
        ("Stage 1", "Stages 2-3", "Stage 4", "Stage 5", "Stage 6"),
        context="peer-review workflow stage order",
    )


def test_peer_review_command_limits_default_manuscript_targets_to_canonical_roots() -> None:
    peer_review_command = (COMMANDS_DIR / "peer-review.md").read_text(encoding="utf-8")

    _sf(
        peer_review_command,
        "default in-project manuscript family",
        "`paper/`",
        "`manuscript/`",
        "`draft/`",
        "PAPER-CONFIG.json",
        "canonical current manuscript entrypoint rules",
        context="peer-review command manuscript roots",
    )

    _sf(
        peer_review_command,
        "Explicit external artifact intake",
        "`.tex`",
        "`.md`",
        "`.pdf`",
        "`.docx`",
        "`.xlsx`",
        "manifest/config-resolved",
        "Do not use ad hoc wildcard discovery",
        "specific artifact path",
        context="peer-review command manuscript roots",
    )
    _f(peer_review_command, "peer-review command manuscript roots", "find paper manuscript draft", "find . -maxdepth 3")


def test_peer_review_referee_surface_fail_closed_final_adjudication_contract() -> None:
    referee = (AGENTS_DIR / "gpd-referee.md").read_text(encoding="utf-8")
    peer_review = _workflow_authority_text("peer-review")
    panel = (REFERENCES_DIR / "publication" / "peer-review-panel.md").read_text(encoding="utf-8")
    reliability = (REFERENCES_DIR / "publication" / "peer-review-reliability.md").read_text(encoding="utf-8")

    _assert_prompt_concepts(
        peer_review,
        {
            "fail closed before recommendation": (
                "required staged-review artifact",
                "missing",
                "malformed",
                "wrong-round",
                "STOP",
                "final recommendation",
            ),
            "blank manuscript path fails validation": (
                "blank `manuscript_path`",
                "${REVIEW_ROOT}/REVIEW-LEDGER{round_suffix}.json",
                "${REVIEW_ROOT}/REFEREE-DECISION{round_suffix}.json",
                "validation failures",
            ),
        },
        context="peer-review workflow fail-closed final adjudication",
    )
    _s(referee, "peer-review referee fail-closed final adjudication", "Do not fall back", "standalone review")
    _f(referee, "peer-review referee fail-closed final adjudication", "fall back to direct standalone review")
    _assert_prompt_concepts(
        reliability,
        {
            "strict referee decision validation": (
                "gpd validate referee-decision",
                "--strict",
                "--ledger",
                "manuscript_path",
            ),
            "strict ledger validation": ("gpd validate review-ledger", "non-empty `manuscript_path`"),
            "blank manuscript path contract failure": ("blank `manuscript_path`", "contract failure"),
        },
        context="peer-review reliability final adjudication",
    )
    _m(
        reliability,
        "peer-review reliability final adjudication fields",
        "bibliography_audit_clean",
        "reproducibility_ready",
    )
    _assert_prompt_concepts(
        panel,
        {
            "Stage 6 owns only adjudication output": ("Stage 6", "write only", "adjudication artifacts", "Output"),
            "upstream evidence is read-only": (
                "${REVIEW_ROOT}/CLAIMS{round_suffix}.json",
                "${REVIEW_ROOT}/STAGE-*.json",
                "${REVIEW_ROOT}/PROOF-REDTEAM{round_suffix}.md",
                "read-only upstream evidence",
            ),
            "fail closed routes upstream": (
                "missing",
                "malformed",
                "stale",
                "mutually inconsistent",
                "Stage 6",
                "fail closed",
                "earliest failing upstream stage",
            ),
            "consistency report is sidecar": (
                "${PUBLICATION_ROOT}/CONSISTENCY-REPORT.md",
                "diagnostic sidecar",
            ),
            "no upstream repair": ("Do not repair", "upstream stage artifacts", "final adjudication"),
        },
        context="peer-review panel Stage 6 boundary",
    )


def test_publication_prompts_surface_strict_semantic_manuscript_gates() -> None:
    arxiv = (COMMANDS_DIR / "arxiv-submission.md").read_text(encoding="utf-8")
    respond = (COMMANDS_DIR / "respond-to-referees.md").read_text(encoding="utf-8")
    peer_review_workflow = _workflow_authority_text("peer-review")
    peer_review_index = (WORKFLOWS_DIR / "peer-review.md").read_text(encoding="utf-8")
    respond_workflow = _workflow_authority_text("respond-to-referees")
    arxiv_workflow = _workflow_authority_text("arxiv-submission")
    shared_preflight = (TEMPLATES_DIR / "paper" / "publication-manuscript-root-preflight.md").read_text(
        encoding="utf-8"
    )

    _f(peer_review_index, "peer-review workflow publication preflight include", PUBLICATION_SHARED_PREFLIGHT_INCLUDE)
    _mf(
        peer_review_workflow,
        "{GPD_INSTALL_DIR}/templates/paper/publication-manuscript-root-preflight.md",
        context="peer-review workflow publication preflight include",
    )
    _assert_loaded_authorities(
        "peer-review",
        "artifact_discovery",
        "references/publication/publication-review-round-artifacts.md",
    )
    _assert_loaded_authorities("write-paper", "paper_bootstrap", "references/publication/publication-bootstrap-preflight.md")
    _assert_write_paper_publication_review_authorities()
    for content in (respond, arxiv):
        _ff(
            content,
            PUBLICATION_SHARED_PREFLIGHT_INCLUDE,
            PUBLICATION_BOOTSTRAP_PREFLIGHT_INCLUDE,
            PUBLICATION_RESPONSE_WRITER_HANDOFF_INCLUDE,
            PUBLICATION_ROUND_ARTIFACTS_INCLUDE,
            PUBLICATION_REVIEW_RELIABILITY_INCLUDE,
            "@{GPD_INSTALL_DIR}/references/shared/canonical-schema-discipline.md",
            "templates/paper/review-ledger-schema.md",
            "templates/paper/referee-decision-schema.md",
            context="thin publication command wrapper",
        )
    _mf(
        respond_workflow,
        PUBLICATION_BOOTSTRAP_PREFLIGHT_PATH,
        PUBLICATION_RESPONSE_WRITER_HANDOFF_INCLUDE,
        PUBLICATION_REVIEW_RELIABILITY_INLINE,
        context="respond workflow publication authorities",
    )
    _f(respond_workflow, "respond workflow publication authorities", PUBLICATION_ROUND_ARTIFACTS_INCLUDE)
    _mf(
        arxiv_workflow,
        PUBLICATION_BOOTSTRAP_PREFLIGHT_PATH,
        PUBLICATION_ROUND_ARTIFACTS_INCLUDE,
        context="arxiv workflow publication authorities",
    )
    _ff(
        arxiv_workflow,
        PUBLICATION_RESPONSE_WRITER_HANDOFF_INCLUDE,
        PUBLICATION_REVIEW_RELIABILITY_INCLUDE,
        context="arxiv workflow publication authorities",
    )
    _s(arxiv_workflow, "arxiv staged reliability reference", "staged", "peer-review-reliability.md", "reference")
    _assert_loaded_authorities(
        "arxiv-submission",
        "manuscript_preflight",
        "templates/paper/publication-manuscript-root-preflight.md",
    )
    _assert_loaded_authorities(
        "respond-to-referees",
        "bootstrap",
        "references/publication/publication-bootstrap-preflight.md",
    )
    _sf(
        shared_preflight,
        "strict preflight reads",
        "resolved manuscript directory",
        "ARTIFACT-MANIFEST.json",
        "BIBLIOGRAPHY-AUDIT.json",
        "reproducibility-manifest.json",
        "PAPER-CONFIG.json",
        "wildcard discovery",
        "first-match filename scans",
        context="publication manuscript preflight",
    )

    _sf(
        shared_preflight,
        "canonical manuscript family",
        "`paper/`",
        "`manuscript/`",
        "`draft/`",
        "explicit-artifact mode",
        "`.pdf`",
        "does not widen",
        "resolved `.tex` / `.md` entrypoint path",
        context="publication manuscript preflight",
    )

    _sf(
        shared_preflight,
        "nearby `ARTIFACT-MANIFEST.json`",
        "additive when present",
        "same explicit manuscript directory",
        "copied from another manuscript root",
        "gpd paper-build",
        "regenerates",
        context="publication manuscript preflight",
    )
    _m(
        shared_preflight,
        "publication preflight review contract fields",
        "bibliography_audit_clean",
        "reproducibility_ready",
    )


def test_publication_command_contexts_surface_schema_docs_before_generation() -> None:
    write_paper = (COMMANDS_DIR / "write-paper.md").read_text(encoding="utf-8")
    peer_review = (COMMANDS_DIR / "peer-review.md").read_text(encoding="utf-8")
    arxiv = (COMMANDS_DIR / "arxiv-submission.md").read_text(encoding="utf-8")
    respond = (COMMANDS_DIR / "respond-to-referees.md").read_text(encoding="utf-8")
    peer_review_workflow = _workflow_authority_text("peer-review")
    peer_review_index = (WORKFLOWS_DIR / "peer-review.md").read_text(encoding="utf-8")
    respond_workflow = _workflow_authority_text("respond-to-referees")
    arxiv_workflow = _workflow_authority_text("arxiv-submission")
    peer_review_workflow_expanded = _expanded_workflow_authority_text("peer-review")
    shared_preflight_include = "@{GPD_INSTALL_DIR}/templates/paper/publication-manuscript-root-preflight.md"
    bootstrap_preflight_path = "{GPD_INSTALL_DIR}/references/publication/publication-bootstrap-preflight.md"

    for content in (write_paper, peer_review, arxiv, respond):
        _ff(
            content,
            "templates/paper/paper-config-schema.md",
            "templates/paper/artifact-manifest-schema.md",
            "templates/paper/bibliography-audit-schema.md",
            "templates/paper/reproducibility-manifest.md",
            PUBLICATION_REVIEW_RELIABILITY_INCLUDE,
            shared_preflight_include,
            PUBLICATION_BOOTSTRAP_PREFLIGHT_INCLUDE,
            PUBLICATION_RESPONSE_WRITER_HANDOFF_INCLUDE,
            PUBLICATION_ROUND_ARTIFACTS_INCLUDE,
            context="thin publication command schema staging",
        )
    for content in (write_paper, peer_review):
        _ff(
            content,
            "templates/paper/review-ledger-schema.md",
            "templates/paper/referee-decision-schema.md",
            "references/publication/peer-review-panel.md",
            "references/publication/peer-review-reliability.md",
            context="thin publication command review schema staging",
        )
    _assert_loaded_authorities(
        "write-paper",
        "paper_bootstrap",
        "references/publication/publication-bootstrap-preflight.md",
        "templates/paper/publication-manuscript-root-preflight.md",
    )
    _assert_conditional_authorities(
        "write-paper",
        "outline_and_scaffold",
        "paper_builder_config_or_artifact_manifest_write",
        "templates/paper/paper-config-schema.md",
        "templates/paper/artifact-manifest-schema.md",
    )
    _assert_loaded_authorities(
        "write-paper",
        "consistency_and_references",
        "templates/paper/bibliography-audit-schema.md",
        "templates/paper/reproducibility-manifest.md",
    )
    _assert_write_paper_publication_review_authorities()
    _ff(
        peer_review_index,
        PUBLICATION_SHARED_PREFLIGHT_INCLUDE,
        PUBLICATION_BOOTSTRAP_PREFLIGHT_INCLUDE,
        PUBLICATION_RESPONSE_WRITER_HANDOFF_INCLUDE,
        context="peer-review workflow staged schema docs",
    )
    _mf(
        peer_review_workflow,
        "{GPD_INSTALL_DIR}/templates/paper/publication-manuscript-root-preflight.md",
        context="peer-review workflow staged schema docs",
    )
    _assert_loaded_authorities(
        "peer-review",
        "final_adjudication",
        "templates/paper/review-ledger-schema.md",
    )
    _assert_loaded_authorities(
        "peer-review",
        "final_adjudication",
        "templates/paper/referee-decision-schema.md",
    )
    _assert_loaded_authorities(
        "peer-review",
        "artifact_discovery",
        "references/publication/publication-review-round-artifacts.md",
    )
    _mf(
        peer_review_workflow_expanded,
        "bibliography_audit_clean",
        "reproducibility_ready",
        context="peer-review expanded review contract fields",
    )
    _mf(
        respond_workflow,
        "templates/paper/author-response.md",
        "templates/paper/referee-response.md",
        bootstrap_preflight_path,
        PUBLICATION_RESPONSE_WRITER_HANDOFF_INCLUDE,
        PUBLICATION_REVIEW_RELIABILITY_INLINE,
        context="respond workflow staged schema docs",
    )
    _assert_loaded_authorities(
        "respond-to-referees",
        "bootstrap",
        "references/publication/publication-bootstrap-preflight.md",
    )
    _m(arxiv_workflow, "arxiv workflow staged schema docs", bootstrap_preflight_path, PUBLICATION_ROUND_ARTIFACTS_INCLUDE)
    _f(
        arxiv_workflow,
        "arxiv workflow staged schema docs",
        PUBLICATION_RESPONSE_WRITER_HANDOFF_INCLUDE,
        PUBLICATION_REVIEW_RELIABILITY_INCLUDE,
    )
    _s(arxiv_workflow, "arxiv workflow staged reliability note", "staged", "peer-review-reliability.md", "reference")
    _assert_loaded_authorities(
        "arxiv-submission",
        "manuscript_preflight",
        "templates/paper/publication-manuscript-root-preflight.md",
    )
    _assert_loaded_authorities(
        "write-paper",
        "figure_and_section_authoring",
        "references/shared/canonical-schema-discipline.md",
    )
    for content in (respond, arxiv):
        _ff(
            content,
            shared_preflight_include,
            PUBLICATION_BOOTSTRAP_PREFLIGHT_INCLUDE,
            PUBLICATION_RESPONSE_WRITER_HANDOFF_INCLUDE,
            PUBLICATION_ROUND_ARTIFACTS_INCLUDE,
            PUBLICATION_REVIEW_RELIABILITY_INCLUDE,
            context="publication command wrapper staged include absence",
        )


def test_staged_publication_and_quick_workflow_prompts_match_executable_init_paths() -> None:
    write_paper_workflow = _workflow_authority_text("write-paper")
    peer_review_workflow = _workflow_authority_text("peer-review")
    quick_workflow = _workflow_authority_text("quick")
    arxiv_workflow = _workflow_authority_text("arxiv-submission")
    arxiv_staging = registry.get_command("arxiv-submission").staged_loading

    _assert_workflow_calls_staged_init_for_manifest_stages("write-paper", write_paper_workflow)
    _assert_workflow_calls_staged_init_for_manifest_stages("peer-review", peer_review_workflow)
    _assert_workflow_calls_staged_init_for_manifest_stages("quick", quick_workflow)
    execute_phase_workflow = _workflow_authority_text("execute-phase")
    _assert_workflow_calls_staged_init_for_manifest_stages("execute-phase", execute_phase_workflow)
    _assert_workflow_calls_staged_init_for_manifest_stages("arxiv-submission", arxiv_workflow)

    assert arxiv_staging is not None
    assert arxiv_staging.stage_ids() == (
        "bootstrap",
        "manuscript_preflight",
        "review_gate",
        "package",
        "finalize",
    )
    _mf(
        arxiv_workflow,
        "gpd --raw init arxiv-submission --stage bootstrap",
        "gpd --raw validate command-context arxiv-submission",
        "gpd --raw validate review-preflight arxiv-submission",
        context="arxiv staged init public command wiring",
    )
    _ff(
        arxiv_workflow,
        "metadata-only for the prompt path today",
        "no public staged init CLI command",
        context="arxiv staged init stale command visibility",
    )


def test_research_verification_body_scaffold_keeps_body_only_subject_labels_distinct() -> None:
    research_verification = (TEMPLATES_DIR / "research-verification.md").read_text(encoding="utf-8")

    _mf(
        research_verification,
        "Allowed body enum values:",
        "suggested_subject_kind",
        'gap_subject_kind: "claim"',
        "forbidden_proxy_id",
        context="research verification body-only subject fields",
    )
    _assert_prompt_contracts(
        research_verification,
        fragment_count(
            "research verification repeats check_subject_kind claim examples",
            "check_subject_kind: claim",
            expected_count=2,
            context="research verification body-only subject examples",
        ),
    )
    _sf(
        research_verification,
        "Use `check_subject_kind` for body-only verification checkpoints",
        "Use `gap_subject_kind` for the body scaffold",
        "aligned with the canonical frontmatter-safe subject vocabulary",
        "explicit proxy-rejection gaps",
        context="research verification body-only subject semantics",
    )
    _ff(
        research_verification,
        "\nsubject_kind: [claim | deliverable | acceptance_test | reference | forbidden_proxy | suggested_contract_check]",
        "# Allowed check_subject_kind values: claim|deliverable|acceptance_test|reference",
        "check_subject_kind: [claim | deliverable | acceptance_test | reference]",
        "check_subject_kind: [claim | deliverable | acceptance_test | reference | forbidden_proxy | suggested_contract_check]",
        'gap_subject_kind: "claim | deliverable | acceptance_test | reference"',
        'gap_subject_kind: "claim | deliverable | acceptance_test | reference | forbidden_proxy | suggested_contract_check"',
        context="research verification stale body subject aliases",
    )


def test_verify_work_workflow_uses_body_only_subject_kind_fields() -> None:
    verify_work = _workflow_authority_text("verify-work")

    _mf(
        verify_work,
        "Load the staged researcher-session scaffold and canonical schema pack at this stage.",
        "Keep body-only session-overlay fields aligned with the staged researcher-session scaffold.",
        "Write to `${PHASE_DIR_ABS}/${phase_number}-VERIFICATION.md`",
        'gpd validate verification-contract "${PHASE_DIR_ABS}/${phase_number}-VERIFICATION.md"',
        'gpd commit "verify(${phase_number}): complete research validation - {passed} passed, {issues} issues" --files "${PHASE_DIR_ABS}/${phase_number}-VERIFICATION.md"',
        "Use `phase_dir_abs` for shell/file IO",
        "Read PLAN.md files in `${PHASE_DIR_ABS}/` with `file_read`.",
        context="verify-work body-only subject and path wiring",
    )
    _sf(
        verify_work,
        "Use `forbidden_proxy_id`",
        "explicit proxy-rejection checks",
        "instead of inventing extra body subject kinds",
        context="verify-work forbidden proxy subject boundary",
    )
    _ff(
        verify_work,
        "check_subject_kind: `claim|deliverable|acceptance_test|reference`",
        "Allowed body enum values:",
        "check_subject_kind: claim",
        "`check_subject_kind`: claim|deliverable|acceptance_test|reference",
        'gap_subject_kind: "claim"',
        "# Allowed check_subject_kind values: claim|deliverable|acceptance_test|reference",
        "check_subject_kind: [claim | deliverable | acceptance_test | reference]",
        "{phase}",
        "GPD/phases/{phase_dir}",
        "${phase_dir}/",
        "{phase_dir}/",
        "\nsubject_kind: [claim | deliverable | acceptance_test | reference | forbidden_proxy | suggested_contract_check]",
        "check_subject_kind: `claim | deliverable | acceptance_test | reference | forbidden_proxy | suggested_contract_check`",
        "check_subject_kind: [claim | deliverable | acceptance_test | reference | forbidden_proxy | suggested_contract_check]",
        context="verify-work removed body subject aliases",
    )


def test_verify_work_active_sessions_use_canonical_verification_path_and_keep_status_separate() -> None:
    verify_work = _workflow_authority_text("verify-work")

    _mf(
        verify_work,
        "active_verification_sessions",
        "SESSION_ROUTER_INIT",
        "session_status",
        "validating",
        "diagnosed",
        "status",
        "routing_status",
        context="verify-work active session status fields",
    )
    _assert_semantic_concept(
        verify_work,
        "verify-work keeps session progress separate from canonical status",
        required=(
            "Active sessions are payload entries",
            "Route on each entry's canonical",
            "never let `session_status` overwrite `status`",
        ),
        forbidden=(
            'gpd frontmatter get "$file" --field session_status',
            "`session_status` if present, otherwise `status`",
        ),
        context="verify-work active session status separation",
    )


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

    def _all_stage_authorities(skill: dict[str, object]) -> set[str]:
        stages = skill.get("staged_loading", {}).get("stages", [])
        return {
            authority
            for stage in stages
            for authority in (
                *stage.get("loaded_authorities", []),
                *(item for row in stage.get("conditional_authorities", []) for item in row.get("authorities", [])),
            )
        }

    write_paper_stage_authorities = _all_stage_authorities(write_paper)
    peer_review_stage_authorities = _all_stage_authorities(peer_review)

    assert "error" not in write_paper
    assert "error" not in peer_review
    assert "error" not in arxiv_submission
    assert "error" not in respond_to_referees
    assert any(path.endswith("paper-config-schema.md") for path in write_paper_stage_authorities)
    assert any(path.endswith("artifact-manifest-schema.md") for path in write_paper_stage_authorities)
    assert any(path.endswith("bibliography-audit-schema.md") for path in write_paper_stage_authorities)
    assert any(path.endswith("publication-review-round-artifacts.md") for path in write_paper_stage_authorities)
    assert any(path.endswith("review-ledger-schema.md") for path in peer_review_stage_authorities)
    assert any(path.endswith("referee-decision-schema.md") for path in peer_review_stage_authorities)
    assert any(path.endswith("publication-review-round-artifacts.md") for path in peer_review_stage_authorities)
    assert any(path.endswith("peer-review-panel.md") for path in peer_review_stage_authorities)
    assert any(path.endswith("peer-review-reliability.md") for path in peer_review_stage_authorities)
    arxiv_stage_authorities = {
        authority
        for stage in arxiv_submission.get("staged_loading", {}).get("stages", [])
        for authority in stage.get("loaded_authorities", [])
    }
    assert any(path.endswith("publication-bootstrap-preflight.md") for path in arxiv_stage_authorities)
    assert any(path.endswith("publication-review-round-artifacts.md") for path in arxiv_stage_authorities)
    assert any(path.endswith("reproducibility-manifest.md") for path in write_paper_stage_authorities)
    assert not any(path.endswith("peer-review-panel.md") for path in write_paper_stage_authorities)
    assert write_paper_schema_documents == {}
    assert peer_review_contract_documents == {}
    assert arxiv_contract_documents == {}
    assert respond_contract_documents == {}
    _m(write_paper["loading_hint"], "write-paper skill loading hint keys", "content", "referenced_files")
    _sf(
        write_paper["loading_hint"],
        "wrapper/context surface",
        "external markdown dependencies",
        context="write-paper skill loading hint semantics",
    )
    _ff(
        write_paper["loading_hint"],
        "Load `schema_documents` and `contract_documents` too when present",
        "transitive_schema_documents",
        "transitive_contract_documents",
        context="write-paper skill stale transitive loading hints",
    )


def test_peer_review_workflow_and_generated_skill_surface_keep_lifecycle_cleanup_contract() -> None:
    from gpd.mcp.servers.skills_server import get_skill

    peer_review_workflow = _workflow_authority_text("peer-review")
    peer_review_skill_content = get_skill("gpd-peer-review")["content"]

    _sf(
        peer_review_workflow,
        "stage-recovery-gate.md",
        "Launching the six-stage review panel",
        "stale-output rejection",
        "declared carry-forward inputs",
        "Apply the `peer_review_stage6_referee` tuple",
        context="peer-review lifecycle cleanup contract",
    )
    _sf(
        peer_review_skill_content,
        "staged_loading",
        "artifact_discovery",
        "final_adjudication",
        context="generated peer-review lifecycle cleanup contract",
    )


def test_peer_review_spawned_stage_prompts_keep_stage_identity_callsite_owned() -> None:
    peer_review = _workflow_authority_text("peer-review")

    assert '<step name="child_return_contract">' in peer_review or "<child_return_contract>" in peer_review
    _sf(
        peer_review,
        "Stage identity",
        "tuple role",
        "expected paths",
        "write allowlist",
        "validators",
        "never trust a stage label",
        context="peer-review stage identity contract",
    )
    assert "peer_review_stage6_referee" in peer_review

    expected_stage_contracts = (
        "peer_review_stage1_reader",
        "stage_id=reader and stage_kind=reader",
        "peer_review_stage2_literature",
        "stage_id=literature and stage_kind=literature",
        "peer_review_stage3_math",
        "stage_id=math and stage_kind=math",
        "peer_review_proof_redteam",
        "${REVIEW_ROOT}/PROOF-REDTEAM{round_suffix}.md",
        "peer_review_stage4_physics",
        "stage_id=physics and stage_kind=physics",
        "peer_review_stage5_significance",
        "stage_id=interestingness and stage_kind=interestingness",
        "peer_review_stage6_referee",
        "`gpd_return.files_written` stays within the Stage 6 write allowlist",
    )
    _assert_contains_fragments(peer_review, *expected_stage_contracts)


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
    assert {entry["path"].split("}/", 1)[1] for entry in bibliographer["referenced_files"]} == direct_reference_suffixes


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

    _mf(
        review_reader_raw,
        "{GPD_INSTALL_DIR}/references/publication/peer-review-panel.md",
        context="review reader peer-review panel path",
    )
    _mf(
        referee_raw,
        "{GPD_INSTALL_DIR}/references/publication/peer-review-panel.md",
        "{GPD_INSTALL_DIR}/templates/paper/review-ledger-schema.md",
        "{GPD_INSTALL_DIR}/templates/paper/referee-decision-schema.md",
        context="referee schema source paths",
    )
    _ff(review_reader, "Peer Review Panel Protocol", context="review reader lazy peer-review panel body")
    _mf(
        review_literature,
        "{GPD_INSTALL_DIR}/references/publication/peer-review-panel.md",
        context="review literature peer-review panel path",
    )
    _ff(review_literature, "Peer Review Panel Protocol", context="review literature lazy peer-review panel body")
    _ff(referee, "Review Ledger Schema", "Referee Decision Schema", context="referee lazy schema bodies")


def test_verification_and_agent_reference_prompts_expand_or_stage_required_reference_bodies() -> None:
    verify_work = _expand_prompt_surface(WORKFLOWS_DIR / "verify-work.md")
    verify_phase = _expand_prompt_surface(WORKFLOWS_DIR / "verify-phase.md")
    phase_researcher = _expand_prompt_surface(AGENTS_DIR / "gpd-phase-researcher.md")
    planner = _expand_prompt_surface(AGENTS_DIR / "gpd-planner.md")
    verify_work_staging = registry.get_command("verify-work").staged_loading
    assert verify_work_staging is not None
    inventory_build = next(stage for stage in verify_work_staging.stages if stage.id == "inventory_build")
    interactive_validation = next(stage for stage in verify_work_staging.stages if stage.id == "interactive_validation")

    _ff(
        verify_work,
        "Verification Independence",
        "# Contract Results Schema",
        context="verify-work staged reference raw include boundaries",
    )
    assert any(
        "references/verification/meta/verification-independence.md" in row.authorities
        for row in inventory_build.conditional_authorities
    )
    interactive_conditionals = tuple(
        authority
        for conditional in interactive_validation.conditional_authorities
        for authority in conditional.authorities
    )
    assert {"templates/contract-results-schema.md"} <= set(interactive_conditionals)
    _ff(
        verify_phase,
        "Verification Independence",
        "# Contract Results Schema",
        "@{GPD_INSTALL_DIR}/references/verification/core/verification-core.md",
        "@{GPD_INSTALL_DIR}/templates/contract-results-schema.md",
        context="verify-phase staged reference raw include boundaries",
    )
    _sf(
        verify_phase,
        "Do not raw-include the verification reference library at workflow load.",
        "standalone `gpd:verify-work` workflow reuses the same verification criteria",
        context="verify-phase staged verification semantics",
    )
    _mf(
        verify_phase,
        "{GPD_INSTALL_DIR}/references/verification/meta/verification-independence.md",
        "{GPD_INSTALL_DIR}/templates/contract-results-schema.md",
        'VERIFICATION_FILE="${phase_dir}/${phase_number}-VERIFICATION.md"',
        "Return status (`passed` | `gaps_found` | `expert_needed` | `human_needed`)",
        context="verify-phase staged verification exact wiring",
    )
    _m(
        phase_researcher,
        "phase researcher shared protocol include",
        "- `@{GPD_INSTALL_DIR}/references/shared/shared-protocols.md`",
    )
    _ff(
        phase_researcher,
        "# Shared Research Philosophy and Protocols",
        "# Agent Infrastructure Protocols",
        context="phase researcher expanded reference headings",
    )
    _mf(
        planner,
        "Shared Protocols",
        "{GPD_INSTALL_DIR}/references/orchestration/agent-infrastructure.md",
        context="planner staged reference labels",
    )
    _f(verify_work.lower(), "verify-work resolved includes", "@ include not resolved:")
    _f(verify_phase.lower(), "verify-phase resolved includes", "@ include not resolved:")
    _f(phase_researcher.lower(), "phase researcher resolved includes", "@ include not resolved:")
    _f(planner.lower(), "planner resolved includes", "@ include not resolved:")


def test_verification_independence_reference_examples_keep_required_contract_fields_visible() -> None:
    reference = (REFERENCES_DIR / "verification" / "meta" / "verification-independence.md").read_text(encoding="utf-8")

    _assert_prompt_contracts(
        reference,
        fragment_count(
            "verification independence includes two contract examples",
            "contract:\n  schema_version: 1",
            expected_count=2,
            context="verification independence examples",
        ),
    )
    assert "context_intake:" in reference
    assert "forbidden_proxies:" in reference
    assert "uncertainty_markers:" in reference


def test_planner_and_summary_prompt_surfaces_expand_contract_schema_bodies() -> None:
    phase_prompt = _expand_prompt_surface(TEMPLATES_DIR / "phase-prompt.md")
    planner_prompt = _expand_prompt_surface(TEMPLATES_DIR / "planner-subagent-prompt.md")
    summary_template = _expand_prompt_surface(TEMPLATES_DIR / "summary.md")

    _mf(
        phase_prompt,
        "# PLAN Contract Schema",
        "schema_version: 1",
        "in_scope:",
        "context_intake:",
        "Quick contract rules:",
        context="expanded phase prompt plan contract schema",
    )
    _assert_prompt_contracts(
        phase_prompt,
        fragment_count(
            "expanded phase prompt has one quick contract rules block",
            "Quick contract rules:",
            expected_count=1,
            context="expanded phase prompt contract schema",
        ),
    )
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
    _mf(
        phase_prompt,
        'must_include_prior_outputs: ["GPD/phases/00-baseline/00-01-SUMMARY.md"]',
        'user_asserted_anchors: ["GPD/phases/00-baseline/00-01-SUMMARY.md#vacuum-polarization-normalization"]',
        "claims:",
        "observables: [obs-main]",
        "### `forbidden_proxies[]`",
        "### `links[]`",
        context="expanded phase prompt contract examples",
    )
    _assert_prompt_contracts(
        planner_prompt,
        fragment_count(
            "planner prompt standard planning template heading count",
            "## Standard Planning Template",
            expected_count=1,
            context="expanded planner prompt schema includes",
        ),
        fragment_count(
            "planner prompt revision template heading count",
            "## Revision Template",
            expected_count=1,
            context="expanded planner prompt schema includes",
        ),
        fragment_count(
            "planner prompt plan contract schema include count",
            "{GPD_INSTALL_DIR}/templates/plan-contract-schema.md",
            expected_count=1,
            context="expanded planner prompt schema includes",
        ),
    )
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
    _m(phase_prompt, "expanded phase prompt unresolved question field", "scope.unresolved_questions")
    _assert_semantic_concept(
        phase_prompt,
        "expanded phase prompt stable id rules",
        required=(
            "Every claim must declare a stable `id`.",
            "Do not reuse the same ID across `observables[]`, `claims[]`, `deliverables[]`, `acceptance_tests[]`, "
            "`references[]`, `forbidden_proxies[]`, or `links[]`",
        ),
        context="expanded phase prompt stable id rules",
    )
    _m(summary_template, "expanded summary template schema include", "contract-results-schema.md")
    _assert_semantic_concept(
        summary_template,
        "summary template defers contract rules to schema include",
        required="single detailed rule source",
        context="expanded summary template schema include",
    )


def test_sync_state_defers_state_schema_while_write_paper_expands_required_schema_bodies() -> None:
    sync_state = _expand_prompt_surface(COMMANDS_DIR / "sync-state.md")
    sync_state_workflow = _expanded_workflow_authority_text("sync-state")
    write_paper = _expanded_workflow_authority_text("write-paper")

    _mf(sync_state, "state-json-schema.md", context="sync-state schema path")
    _ff(
        sync_state,
        "# state.json Schema",
        "Authoritative vs Derived",
        "`convention_lock`",
        context="sync-state body deferral",
    )
    _mf(
        sync_state_workflow,
        "`convention_lock`",
        context="sync-state workflow expands state schema field",
    )
    _mf(
        write_paper,
        "templates/paper/reproducibility-manifest.md",
        "bibliography audit refresh",
        "publication-pipeline-modes.md",
        context="write-paper schema source expansion",
    )
    _ff(write_paper, "Reproducibility Manifest Template", context="write-paper lazy reproducibility body")
    _sf(
        write_paper,
        "bounded external-authoring lane",
        "accepts one explicit",
        "intake manifest only",
        context="write-paper external authoring intake",
    )
    _mf(write_paper, "GPD/publication/{subject_slug}/intake/", context="write-paper external authoring intake")
    _ff(
        write_paper,
        '"execution_steps"',
        "random_seeds[].computation",
        "resource_requirements[].step",
        context="write-paper deferred reproducibility body fields",
    )


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


def test_state_json_schema_surfaces_stdin_contract_persistence_and_model_normalization_rules() -> None:
    state_schema = _expand_prompt_surface(TEMPLATES_DIR / "state-json-schema.md")

    _mf(
        state_schema,
        "printf '%s\\n' \"$PROJECT_CONTRACT_JSON\" | gpd --raw validate project-contract -",
        "printf '%s\\n' \"$PROJECT_CONTRACT_JSON\" | gpd state set-project-contract -",
        "temporary file",
        "`schema_version` must be the integer `1`.",
        '"required_actions": ["read", "compare", "cite", "avoid"]',
        "Blank-after-trim values are invalid",
        context="state schema project contract stdin persistence",
    )
    _sf(
        state_schema,
        "grounding fields",
        "concrete enough to re-find later",
        "missing `must_surface: true` reference",
        "warning",
        context="state schema project contract grounding",
    )


def test_phase_prompt_surfaces_validation_critical_plan_contract_rules() -> None:
    phase_prompt = (TEMPLATES_DIR / "phase-prompt.md").read_text(encoding="utf-8")

    assert "Quick contract rules:" in phase_prompt
    _assert_prompt_contracts(
        phase_prompt,
        fragment_count(
            "phase prompt has one quick contract rules block",
            "Quick contract rules:",
            expected_count=1,
            context="phase-prompt contract rules",
        ),
    )
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

    _mf(
        review_ledger_schema,
        "`issue_id` must match `REF-[A-Za-z0-9][A-Za-z0-9_-]*`",
        "Every `claim_ids[]` entry must match `CLM-[A-Za-z0-9][A-Za-z0-9_-]*`.",
        context="review ledger id format regexes",
    )


def test_contract_models_match_prompted_schema_contracts() -> None:
    acceptance_test_fields = ResearchContract.model_fields["acceptance_tests"].annotation.__args__[0].model_fields
    reference_fields = ResearchContract.model_fields["references"].annotation.__args__[0].model_fields

    assert "automation" in acceptance_test_fields
    assert "aliases" in reference_fields
    assert "carry_forward_to" in reference_fields
    assert ResearchContract.model_fields["schema_version"].annotation == Literal[1]
    assert VerificationEvidence.model_config.get("extra") == "forbid"


def test_execution_surfaces_use_bounded_review_cadence_and_first_result_gates() -> None:
    execute_phase = _workflow_authority_text("execute-phase")
    execute_plan = (WORKFLOWS_DIR / "execute-plan.md").read_text(encoding="utf-8")
    resume_work = expand_at_includes(
        _workflow_authority_text("resume-work"),
        REPO_ROOT / "src/gpd",
        "/runtime/",
    )
    continuation = (TEMPLATES_DIR / "continuation-prompt.md").read_text(encoding="utf-8")
    checkpoints = (REFERENCES_DIR / "orchestration" / "checkpoints.md").read_text(encoding="utf-8")
    checkpoint_flow = (REFERENCES_DIR / "execution" / "execute-plan-checkpoints.md").read_text(encoding="utf-8")
    executor_agent = (AGENTS_DIR / "gpd-executor.md").read_text(encoding="utf-8")

    _mf(
        execute_phase,
        "review_cadence",
        "FIRST_RESULT_GATE_REQUIRED",
        "probe_then_fanout",
        "bounded_execution",
        "pre_execution_specialists",
        'gpd --raw init execute-phase "${PHASE_ARG}" --stage pre_execution_specialists',
        context="execute-phase bounded review cadence",
    )
    _assert_prompt_contracts(
        execute_plan,
        semantic_anchor(
            "execute-plan honors dense-forced first-result gate",
            ("do not recompute", "treat `FIRST_RESULT_GATE_REQUIRED=true` as forced"),
            mode="any",
            context="execute-plan first-result gate",
        ),
    )
    _sf(
        execute_plan,
        "autonomy",
        "does NOT disable first-result sanity checks",
        "Required first-result sanity gate",
        "phase ordering",
        "prior momentum",
        "never waive",
        "required bounded stop",
        "`MAX_UNATTENDED_MINUTES_PER_PLAN`",
        context="execute-plan bounded review cadence",
    )
    _s(execute_phase, "execute-phase bounded review scope", "Do NOT narrow", "wave advanced", "one proxy passed")
    _ff(
        execute_phase,
        '# task(subagent_type="gpd-notation-coordinator"',
        '# task(subagent_type="gpd-experiment-designer"',
        "| `completed`    | -> update_roadmap (interactive verify-work equivalent)",
        "| `diagnosed`    | Gaps were debugged; review fixes, then -> update_roadmap",
        "| `validating`   | Verification in progress; wait or re-run verify-phase",
        context="execute-phase bounded review stale branches",
    )
    _sf(
        resume_work,
        "What decisive evidence is still owed before downstream work is trustworthy?",
        context="resume-work continuation vocabulary",
    )
    _assert_resume_canonical_note(resume_work)
    _ff(
        resume_work,
        "public top-level resume vocabulary",
        "`resume_surface`",
        "gpd init resume",
        context="resume-work stale continuation vocabulary",
    )
    _mf(executor_agent, "Pattern D: Auto-bounded", context="executor bounded pattern")
    _mf(continuation, "execution_segment", context="continuation prompt bounded segment")
    _mf(checkpoints, "Required Checkpoint Payload", context="checkpoint payload prompt")
    _mf(checkpoint_flow, "rollback primitive", context="execute-plan checkpoint flow")
    _sf(
        execute_phase,
        "`session_status: validating|completed|diagnosed`",
        "conversational progress only",
        context="execute-phase verification status boundary",
    )
    _m(
        execute_phase,
        "execute-phase session status boundary",
        "If the prior report carries `session_status: diagnosed`",
    )


def test_show_phase_workflow_distinguishes_verification_status_from_session_status() -> None:
    show_phase = (WORKFLOWS_DIR / "show-phase.md").read_text(encoding="utf-8")

    _mf(
        show_phase,
        "`*-VERIFICATION.md`",
        "`status`",
        "`session_status`",
        "`passed`",
        "`gaps_found`",
        "`expert_needed`",
        "`human_needed`",
        "`session_status: validating|completed|diagnosed`",
        context="show-phase verification and session status tokens",
    )
    _assert_semantic_concept(
        show_phase,
        "show-phase separates verification status from session progress",
        required=(
            "read frontmatter to extract canonical verification",
            "Automated verification uses",
            "researcher-session progress uses",
        ),
        forbidden=(
            "Automated verification uses `passed`/`gaps_found`/`human_needed`",
            "interactive validation uses `validating`/`completed`/`diagnosed`",
        ),
        context="show-phase verification status separation",
    )


def test_execute_phase_and_related_agents_surface_only_plan_scoped_verification_artifacts() -> None:
    execute_phase = _workflow_authority_text("execute-phase")
    planner_gap_policy = (REFERENCES_DIR / "planning" / "planner-gap-and-revision-policy.md").read_text(
        encoding="utf-8"
    )
    verifier = (AGENTS_DIR / "gpd-verifier.md").read_text(encoding="utf-8")
    audit_milestone = (WORKFLOWS_DIR / "audit-milestone.md").read_text(encoding="utf-8")

    assert "- Verification: {phase_dir}/{phase}-VERIFICATION.md" in execute_phase
    assert '"$phase_dir"/VERIFICATION.md "$phase_dir"/*-VERIFICATION.md' not in execute_phase
    assert 'ls "$phase_dir"/*-VERIFICATION.md 2>/dev/null' in planner_gap_policy
    assert 'find_files("$PHASE_DIR/*-VERIFICATION.md")' in verifier
    assert "`find_files` `GPD/phases/*/*-VERIFICATION.md` by hand" in audit_milestone
    assert "GPD/phases/01-*/VERIFICATION.md" not in audit_milestone


def test_debug_prompts_use_session_status_for_diagnosis_progress() -> None:
    debug_workflow = (WORKFLOWS_DIR / "debug.md").read_text(encoding="utf-8")
    debugger = (AGENTS_DIR / "gpd-debugger.md").read_text(encoding="utf-8")

    _m(debug_workflow, "debug workflow diagnosis session status", "session_status: diagnosed")
    _f(debug_workflow, "debug workflow stale canonical status mutation", 'Update status in frontmatter to "diagnosed"')
    _m(debugger, "debugger diagnosis session status", "`session_status`", '"diagnosed"')
    _f(debugger, "debugger stale canonical status mutation", 'Update status to "diagnosed"')


def test_debug_command_and_workflow_wire_directly_to_gpd_debugger() -> None:
    debug_command = (COMMANDS_DIR / "debug.md").read_text(encoding="utf-8")
    debug_workflow = (WORKFLOWS_DIR / "debug.md").read_text(encoding="utf-8")
    debugger = (AGENTS_DIR / "gpd-debugger.md").read_text(encoding="utf-8")

    _m(
        debug_command,
        "debug command debugger model wiring",
        "gpd-debugger",
        "DEBUGGER_MODEL=$(gpd resolve-model gpd-debugger)",
    )
    _assert_command_delegates_to_workflow(
        debug_command,
        "debug",
        semantic_fragments=("workflow owns", "workspace bootstrap", "active-session handling", "symptom gathering"),
        stale_fragments=("Use ask_user for each.",),
    )
    _m(
        debug_workflow,
        "debug workflow debugger subagent wiring",
        'subagent_type="gpd-debugger"',
        "{GPD_AGENTS_DIR}/gpd-debugger.md",
    )
    _sf(
        debug_workflow,
        "Interactive mode",
        "do not parse `VERIFICATION.md`",
        "Interactive symptom fields:",
        "offer: Fix now, Plan fix, Manual fix",
        context="debug workflow interactive mode semantics",
    )
    _s(
        debugger,
        "debugger agent specialization",
        "public writable production agent specialized for discrepancy investigation",
    )


def test_resume_workflow_surfaces_contract_load_and_validation_state() -> None:
    raw_resume_work = _workflow_authority_text("resume-work")
    resume_work = expand_at_includes(raw_resume_work, REPO_ROOT / "src/gpd", "/runtime/")
    resume_vocabulary = (REFERENCES_DIR / "orchestration" / "resume-vocabulary.md").read_text(encoding="utf-8")

    assert "{GPD_INSTALL_DIR}/templates/state-json-schema.md" in raw_resume_work
    assert "@{GPD_INSTALL_DIR}/templates/state-json-schema.md" not in raw_resume_work
    _mf(
        resume_work,
        "project_contract_validation",
        "project_contract_load_info",
        "workspace_state_exists",
        "workspace_roadmap_exists",
        "workspace_project_exists",
        "workspace_planning_exists",
        context="resume core workspace fields",
    )
    assert_resume_authority_contract(
        resume_vocabulary,
        allow_explicit_alias_examples=False,
        require_canonical_note=False,
    )
    _s(resume_work, "resume-work continuation authority", "canonical continuation", "recovery authority")
    _assert_resume_canonical_note(resume_work)
    assert "public top-level resume vocabulary" not in resume_work
    _mf(
        resume_work,
        "continuity_handoff_file",
        "recorded_continuity_handoff_file",
        "missing_continuity_handoff_file",
        "machine_change_detected",
        "machine_change_notice",
        "current/session hostname and platform",
        context="resume continuity and machine fields",
    )
    _sf(
        resume_work,
        "workspace_*",
        "user-requested workspace",
        "recent-project list is advisory",
        "machine-local",
        "reloads",
        "canonical state",
        "`project_contract_gate.authoritative` is true",
        "visible gate inputs and diagnostics",
        "`project_contract_gate.authoritative` is false",
        "visible-but-blocked",
        context="resume workspace and contract authority",
    )
    _sf(
        resume_work,
        "Contract repair required",
        "blocked contract",
        "state-integrity issue",
        "before planning or execution",
        context="resume contract repair gate",
    )


def _assert_resume_canonical_note(text: str) -> None:
    _s(text, "resume canonical public vocabulary", "Canonical continuation fields", "public resume vocabulary")


def test_resume_command_keeps_internal_resume_backend_details_out_of_public_prompt_surface() -> None:
    resume_command = expand_at_includes(
        (COMMANDS_DIR / "resume-work.md").read_text(encoding="utf-8"),
        REPO_ROOT / "src/gpd",
        "/runtime/",
    )

    _assert_resume_canonical_note(resume_command)
    assert "`resume_surface`" not in resume_command
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
        _workflow_authority_text("resume-work"),
        REPO_ROOT / "src/gpd",
        "/runtime/",
    )

    _assert_command_delegates_to_workflow(
        help_command,
        "help",
        semantic_fragments=("GPD help", "delegating", "workflow-owned help surface"),
    )
    assert_execution_observability_surface_contract(help_workflow)
    assert_cost_surface_discoverability(help_workflow)
    _s(help_command, "help command extraction boundary", "workflow-owned stable markers", "extraction boundaries")
    assert "When STATE.md appears out of sync with disk reality" in progress
    assert "advisory context only" in resume_work
    _sf(
        resume_work,
        "not a ranked bounded-segment resume candidate",
        'does not justify `active_resume_kind="bounded_segment"`',
        context="resume stall advisory boundary",
    )


def test_pause_resume_and_help_wiring_keep_runtime_handoff_and_local_snapshot_boundary() -> None:
    pause_work = (WORKFLOWS_DIR / "pause-work.md").read_text(encoding="utf-8")
    resume_work = expand_at_includes(
        _workflow_authority_text("resume-work"),
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
    _sf(
        resume_work,
        "guided runtime path",
        "public local read-only summary",
        "cross-project discovery surface",
        "advisory and machine-local",
        "reloads",
        "canonical state",
        context="resume public local snapshot boundary",
    )
    _assert_resume_canonical_note(resume_work)
    assert "resume_candidates" in resume_work
    assert "`resume_surface`" not in resume_work
    _assert_resume_canonical_note(help_workflow)
    _sf(
        resume_work,
        "Do NOT invent additional candidates",
        "plan files without summaries",
        "auto-checkpoints",
        "ad hoc checkpoints",
        context="resume candidate source boundary",
    )
    assert "gpd:resume-work" in pause_work
    assert "gpd resume" in pause_work
    assert "gpd resume --recent" in pause_work
    _s(pause_work, "pause-work canonical handoff artifact", "canonical recorded handoff artifact", "current phase")
    _assert_prompt_contracts(
        pause_work,
        semantic_anchor(
            "pause-work continuity wording",
            ("continuation handoff artifact", "session continuity"),
            mode=FragmentMode.ANY,
            match=MatchMode.CASEFOLD_NORMALIZED,
            context="pause-work continuity wording",
        ),
    )
    assert "session.resume_file" not in pause_work
    _assert_resume_canonical_note(help_workflow)
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

    _assert_resume_canonical_note(state_portability)
    assert "public top-level resume vocabulary" not in state_portability
    _m(help_workflow, "help workflow observe execution command", "gpd observe execution")
    _s(
        help_workflow,
        "help workflow observe execution terminal guidance",
        "next read-only checks from your normal terminal",
    )


def test_pause_resume_and_derivation_templates_preserve_result_id_continuity() -> None:
    pause_work = (WORKFLOWS_DIR / "pause-work.md").read_text(encoding="utf-8")
    resume_work = _workflow_authority_text("resume-work")
    continue_here = (TEMPLATES_DIR / "continue-here.md").read_text(encoding="utf-8")
    derivation_state = (TEMPLATES_DIR / "DERIVATION-STATE.md").read_text(encoding="utf-8")

    _mf(
        pause_work,
        "state.json",
        "result IDs",
        "<persistent_state>",
        "<intermediate_results>",
        ".continue-here.md",
        "DERIVATION-STATE.md",
        'gpd state record-session "${record_session_args[@]}"',
        "--last-result-id",
        "last_result_id",
        context="pause-work result-id continuity exact tokens",
    )
    _sf(
        pause_work,
        "manual repair path",
        "active bounded-segment continuity already carries a canonical",
        "let the automatic continuity path",
        context="pause-work result-id continuity semantics",
    )
    _m(resume_work, "resume-work canonical result id token", "canonical `last_result_id`")
    _s(resume_work, "resume-work result id continuity semantics", "preferred continuity anchor")
    _m(continue_here, "continue-here result id state keys", "state.json", "intermediate_results")
    _s(
        continue_here,
        "continue-here result id continuity semantics",
        "Reference the result IDs",
        "Each entry links back",
    )
    _m(derivation_state, "derivation state result id state keys", "state.json", "intermediate_results")
    _assert_semantic_concept(
        derivation_state,
        "derivation state resume-work continuity",
        required="resume-work reads it without mutation",
        forbidden="By resume-work workflow: applies pruning rules",
        context="derivation state resume-work continuity semantics",
    )


def test_state_compaction_lifecycle_docs_do_not_claim_progress_mutates_state() -> None:
    compact_state = (WORKFLOWS_DIR / "compact-state.md").read_text(encoding="utf-8")
    help_workflow = (WORKFLOWS_DIR / "help.md").read_text(encoding="utf-8")

    assert "Triggered automatically when progress.md detects" not in compact_state
    assert "Triggered automatically when STATE.md exceeds 1500 lines" not in help_workflow
    assert "Suggested by progress.md" in compact_state
    assert "Suggested by `gpd:progress`" in help_workflow


def test_protocol_bundle_context_surfaces_across_planning_execution_and_verification() -> None:
    planner_prompt = (TEMPLATES_DIR / "planner-subagent-prompt.md").read_text(encoding="utf-8")
    plan_phase = _workflow_authority_text("plan-phase")
    research_phase = _workflow_authority_text("research-phase")
    execute_phase = _workflow_authority_text("execute-phase")
    execute_plan = (WORKFLOWS_DIR / "execute-plan.md").read_text(encoding="utf-8")
    verify_phase = (WORKFLOWS_DIR / "verify-phase.md").read_text(encoding="utf-8")
    verify_work = _workflow_authority_text("verify-work")
    continuation = (TEMPLATES_DIR / "continuation-prompt.md").read_text(encoding="utf-8")
    planner_agent = (AGENTS_DIR / "gpd-planner.md").read_text(encoding="utf-8")
    checker_agent = (AGENTS_DIR / "gpd-plan-checker.md").read_text(encoding="utf-8")
    executor_agent = (AGENTS_DIR / "gpd-executor.md").read_text(encoding="utf-8")
    verifier_agent = (AGENTS_DIR / "gpd-verifier.md").read_text(encoding="utf-8")
    executor_guide = (REFERENCES_DIR / "execution" / "executor-subfield-guide.md").read_text(encoding="utf-8")

    bundle_fragments = (
        "<selected_protocol_bundle_ids>",
        "{selected_protocol_bundle_ids}",
        "<protocol_bundle_load_manifest>",
        "{protocol_bundle_load_manifest}",
        "<protocol_bundle_context>",
        "{protocol_bundle_context}",
        "<protocol_bundle_verifier_extensions>",
        "{protocol_bundle_verifier_extensions}",
    )
    for text in (planner_prompt, continuation):
        _mf(text, *bundle_fragments, context="protocol bundle prompt placeholders")
    assert "<protocol_bundles>" not in continuation

    _sf(
        plan_phase,
        "Use the protocol bundle handoff as the primary specialized method/domain surface",
        context="plan-phase protocol bundle handoff semantics",
    )
    _mf(
        plan_phase,
        "- `{selected_protocol_bundle_ids}` -> {selected_protocol_bundle_ids}",
        "- `{protocol_bundle_load_manifest}` -> {protocol_bundle_load_manifest}",
        "- `{protocol_bundle_verifier_extensions}` -> {protocol_bundle_verifier_extensions}",
        "<protocol_bundle_load_manifest>",
        context="plan-phase protocol bundle fields",
    )
    _mf(
        research_phase,
        "`selected_protocol_bundle_ids`, `protocol_bundle_load_manifest`, and `protocol_bundle_verifier_extensions`",
        "<protocol_bundle_verifier_extensions>",
        context="research-phase protocol bundle fields",
    )
    _sf(
        research_phase,
        "selected_protocol_bundle_ids` is non-empty",
        "protocol_bundle_load_manifest",
        "verifier_extensions",
        context="research-phase protocol bundle semantics",
    )
    _mf(
        execute_phase,
        "<selected_protocol_bundle_ids>{selected_protocol_bundle_ids}</selected_protocol_bundle_ids>",
        "<protocol_bundle_load_manifest>{protocol_bundle_load_manifest}</protocol_bundle_load_manifest>",
        "<protocol_bundle_verifier_extensions>{protocol_bundle_verifier_extensions}</protocol_bundle_verifier_extensions>",
        "`{protocol_bundle_verifier_extensions}`: From checkpoint_resume init JSON",
        context="execute-phase protocol bundle fields",
    )
    _s(execute_phase, "execute-phase protocol bundle semantics", "protocol verifier extensions")
    _m(
        execute_plan,
        "execute-plan protocol bundle fields",
        "protocol_bundle_load_manifest",
        "protocol_bundle_verifier_extensions",
    )
    _m(verify_phase, "verify-phase protocol bundle fields", "protocol_bundle_verifier_extensions")
    _m(
        verify_work,
        "verify-work protocol bundle fields",
        "protocol_bundle_verifier_extensions",
        "<protocol_bundle_load_manifest>",
    )
    _sf(
        verify_work,
        "primary bundle-extension surface",
        "protocol_bundle_verifier_extensions",
        context="verify-work protocol bundle checklist source",
    )
    _sf(planner_agent, "selected protocol bundle context", context="planner protocol bundle context")
    _mf(checker_agent, "protocol_bundle_coverage", context="plan checker protocol bundle field")
    _s(
        executor_agent,
        "executor protocol bundle routing",
        "additive routing hints",
        "first additive specialization pass",
    )
    _sf(
        verifier_agent,
        "bundle checklist extensions",
        "prefer `protocol_bundle_verifier_extensions`",
        "`protocol_bundle_context` from init JSON",
        context="verifier protocol bundle checklist",
    )
    _sf(
        executor_guide,
        "fallback index",
        "manual cross-check",
        "not a default route",
        context="executor subfield guide protocol bundle fallback",
    )


def test_quick_reference_context_passes_protocol_bundle_fields_but_default_stays_free() -> None:
    quick = _workflow_authority_text("quick")

    planner_reference_branch = re.search(
        r"If `TASK_AUTHORING_INIT\.staged_loading\.stage_id` is `reference_context`, append this selected reference payload:(.*?)</planning_context>",
        quick,
        flags=re.DOTALL,
    )
    assert planner_reference_branch is not None
    _mf(
        planner_reference_branch.group(1),
        "<selected_protocol_bundle_ids>",
        "{selected_protocol_bundle_ids}",
        "<protocol_bundle_load_manifest>",
        "{protocol_bundle_load_manifest}",
        "<protocol_bundle_verifier_extensions>",
        "{protocol_bundle_verifier_extensions}",
        context="quick planner reference protocol bundle placeholders",
    )
    assert "<protocol_bundle_context>" not in planner_reference_branch.group(1)

    executor_reference_branch = re.search(
        r"If the selected planner stage was `reference_context`, pass through the selected reference payload:(.*?)<constraints>",
        quick,
        flags=re.DOTALL,
    )
    assert executor_reference_branch is not None
    _mf(
        executor_reference_branch.group(1),
        "<selected_protocol_bundle_ids>",
        "{selected_protocol_bundle_ids}",
        "<protocol_bundle_load_manifest>",
        "{protocol_bundle_load_manifest}",
        "<protocol_bundle_verifier_extensions>",
        "{protocol_bundle_verifier_extensions}",
        context="quick executor reference protocol bundle placeholders",
    )
    assert "<protocol_bundle_context>" not in executor_reference_branch.group(1)

    default_prefix = quick.split(
        "If `TASK_AUTHORING_INIT.staged_loading.stage_id` is `reference_context`, append this selected reference payload:",
        1,
    )[0]
    _m(default_prefix, "quick command task-authoring default reference runtime", "`task_authoring`")
    _s(
        default_prefix,
        "quick command task-authoring default reference semantics",
        "Default Reference Runtime",
        "not loaded",
    )
    _ff(
        default_prefix,
        "{selected_protocol_bundle_ids}",
        "{protocol_bundle_context}",
        context="quick command pre-reference bundle placeholders",
    )


def test_executor_bundle_fallback_stays_generic_when_no_bundle_fits() -> None:
    executor_agent = (AGENTS_DIR / "gpd-executor.md").read_text(encoding="utf-8")
    executor_guide = (REFERENCES_DIR / "execution" / "executor-subfield-guide.md").read_text(encoding="utf-8")

    _sf(
        executor_agent,
        "If no bundle is selected",
        "generic execution flow",
        "contract-backed anchors and checks",
        "instead of forcing the work into a topic bucket",
        "Do not stay trapped",
        "fallback subfield",
        context="executor generic fallback when no bundle fits",
    )
    _sf(
        executor_guide,
        "If no row cleanly fits",
        "generic execution guidance",
        "core verification expectations",
        "instead of guessing",
        context="executor guide generic fallback when no bundle fits",
    )


def test_runtime_parity_docs_use_canonical_model_resolution_and_generic_handoff_rules() -> None:
    model_resolution = (REFERENCES_DIR / "orchestration" / "model-profile-resolution.md").read_text(encoding="utf-8")
    agent_delegation = (REFERENCES_DIR / "orchestration" / "agent-delegation.md").read_text(encoding="utf-8")
    execute_phase = _workflow_authority_text("execute-phase")
    execute_plan = (WORKFLOWS_DIR / "execute-plan.md").read_text(encoding="utf-8")
    quick = _workflow_authority_text("quick")

    _s(model_resolution, "model profile resolution", "Do not scrape", "`GPD/config.json`", "directly in workflows")
    _m(model_resolution, "model profile resolution commands", "gpd resolve-tier", "gpd resolve-model")
    _s(agent_delegation, "agent delegation parity", "Delegation Contract", "Return-envelope parity")
    _s(
        execute_plan,
        "execute-plan handoff authority",
        "control decision authority throughout execution",
        "Handoff verification",
    )
    _sf(execute_phase, "Handoff verification", context="execute-phase handoff authority")
    _s(
        execute_phase,
        "execute-phase false failure guard",
        "false failure",
        "delivered work",
        "child-listed",
        "artifacts",
    )
    _m(quick, "quick planner delegation", "First, read {GPD_AGENTS_DIR}/gpd-planner.md for your role and instructions.")
    _sf(quick, "Handoff verification", context="quick handoff verification")
    _sf(
        quick,
        "staged quick init",
        "task-bootstrap",
        "default small-task path",
        "`reference_context`",
        "tasks that need active project anchors",
        context="quick staged loading",
    )
    _mf(
        quick,
        'gpd --raw init quick "$DESCRIPTION" --stage task_bootstrap',
        'gpd --raw init quick "$DESCRIPTION" --stage task_authoring',
        'gpd --raw init quick "$DESCRIPTION" --stage reference_context',
        "project_contract_load_info.status",
        "project_contract_validation.valid",
        "project_contract_validation",
        "project_contract_load_info",
        context="quick staged init commands and fields",
    )
    _sf(
        quick,
        "Quick mode",
        "Inherit `project_contract`",
        "`project_contract_gate.authoritative`",
        "true",
        context="quick project contract gate",
    )

    _s(quick, "quick reference context", "default small-task path", "Reference runtime:", "not loaded")
    _assert_init_placeholders_visible(
        quick,
        (
            "project_contract_gate",
            "project_contract_load_info",
            "project_contract_validation",
            "contract_intake",
        ),
        context="quick contract gate placeholders",
    )
    assert "gpd validate plan-preflight" in quick
    assert "references/orchestration/continuation-boundary.md" in quick
    assert "classifyHandoffIfNeeded" not in execute_phase
    assert "classifyHandoffIfNeeded" not in execute_plan
    assert "classifyHandoffIfNeeded" not in quick
    assert "cat GPD/config.json" not in model_resolution
    assert "print(c.get('model_profile', 'review'))" not in execute_phase


def test_verify_work_gap_closure_delegation_surfaces_contract_gate_inputs() -> None:
    verify_work = _workflow_authority_text("verify-work")

    _assert_init_placeholders_visible(
        verify_work,
        (
            "project_contract_gate",
            "project_contract_load_info",
            "project_contract_validation",
            "contract_intake",
            "effective_reference_intake",
        ),
        context="verify-work contract gate placeholders",
    )
    _m(verify_work, "verify-work tool requirement key", "tool_requirements")
    _assert_semantic_concept(
        verify_work,
        "verify-work owns local hard requirements",
        required="hard requirements explicit",
        forbidden="The shared planner template owns the canonical planning policy and contract gate.",
        context="verify-work hard requirement planning boundary",
    )


def test_decisive_comparisons_paper_quality_artifacts_and_profile_invariants_are_visible() -> None:
    compare_command = (COMMANDS_DIR / "compare-results.md").read_text(encoding="utf-8")
    compare_workflow = (WORKFLOWS_DIR / "compare-results.md").read_text(encoding="utf-8")
    internal_template = (TEMPLATES_DIR / "paper" / "internal-comparison.md").read_text(encoding="utf-8")
    figure_tracker = (TEMPLATES_DIR / "paper" / "figure-tracker.md").read_text(encoding="utf-8")
    write_paper = _workflow_authority_text("write-paper")
    new_project = _workflow_authority_text("new-project")
    execute_phase = _workflow_authority_text("execute-phase")
    scoring = (REFERENCES_DIR / "publication" / "paper-quality-scoring.md").read_text(encoding="utf-8")
    settings = (WORKFLOWS_DIR / "settings.md").read_text(encoding="utf-8")
    profiles = (REFERENCES_DIR / "orchestration" / "model-profiles.md").read_text(encoding="utf-8")
    artifact_surfacing = (REFERENCES_DIR / "orchestration" / "artifact-surfacing.md").read_text(encoding="utf-8")
    hypothesis_protocol = (REFERENCES_DIR / "protocols" / "hypothesis-driven-research.md").read_text(encoding="utf-8")
    quick_reference = (REFERENCES_DIR / "verification" / "core" / "verification-quick-reference.md").read_text(
        encoding="utf-8"
    )
    verifier_profiles = (REFERENCES_DIR / "verification" / "meta" / "verifier-profile-checks.md").read_text(
        encoding="utf-8"
    )
    planner = (AGENTS_DIR / "gpd-planner.md").read_text(encoding="utf-8")
    executor = (AGENTS_DIR / "gpd-executor.md").read_text(encoding="utf-8")
    verifier_agent = (AGENTS_DIR / "gpd-verifier.md").read_text(encoding="utf-8")

    _sf(compare_command, "emit decisive verdicts", context="compare-results command verdicts")
    _m(compare_workflow, "compare-results workflow artifact path", "GPD/comparisons/[slug]-COMPARISON.md")
    assert "GPD/analysis/comparison-{slug}.md" not in compare_workflow
    _mf(internal_template, "comparison_verdicts", context="internal comparison verdict field")
    _mf(
        figure_tracker,
        "figure_registry",
        "role: smoking_gun|benchmark|comparison|sanity_check|publication_polish|other",
        "`${PAPER_DIR}/FIGURE_TRACKER.md`",
        context="figure tracker schema fields",
    )
    _sf(figure_tracker, "canonical schema source of truth", context="figure tracker schema authority")
    _mf(
        write_paper,
        "validate paper-quality --from-project .",
        "`${PAPER_DIR}/FIGURE_TRACKER.md`",
        context="write-paper paper-quality figure tracker",
    )
    _mf(new_project, '"review_cadence": "dense"', "Dense review cadence", context="dense review default")
    _sf(
        execute_phase,
        "prior decisive `contract_results`",
        "decisive `comparison_verdicts`",
        "explicit approach lock",
        context="execute-phase decisive prior evidence",
    )
    _mf(execute_phase, "paper/FIGURE_TRACKER.md", context="execute-phase figure tracker path")
    assert "GPD/paper/FIGURE_TRACKER.md" not in execute_phase
    _mf(scoring, "figure_registry", "manuscript-root `FIGURE_TRACKER.md`", context="scoring figure fields")
    _m(artifact_surfacing, "artifact surfacing paper outputs", "paper/<topic_stem>.tex", "paper/<topic_stem>.pdf")
    _mf(hypothesis_protocol, "ARTIFACT-MANIFEST.json", "MANUSCRIPT_TEX", context="hypothesis protocol manifest fields")
    assert "main.tex" not in hypothesis_protocol
    _mf(settings, "Review (Recommended)", context="settings review profile")
    _sf(profiles, "all required contract-aware checks", context="model profile yolo gates")
    _mf(quick_reference, "current registry: 5.1-5.19", context="verification quick reference registry")
    _s(
        verifier_profiles,
        "verifier profile yolo contract-aware checks",
        "still run every contract-aware check required by the plan",
    )
    _assert_prompt_concepts(
        planner,
        {
            "yolo gates": ("first-result gates", "anchor checks", "pre-fanout gates"),
        },
        context="planner autonomy gates",
    )
    _sf(planner, "Do NOT change conventions mid-project", "explicit checkpoint", context="planner convention lock")
    _s(executor, "executor yolo gates", "Required first-result, anchor, and pre-fanout gates", "yolo mode")
    _mf(verifier_agent, "suggested_contract_checks", context="verifier suggested contract checks")


def test_publication_workflows_refresh_bibliography_audit_after_bibliography_changes() -> None:
    write_paper = _workflow_authority_text("write-paper")
    respond = _workflow_authority_text("respond-to-referees")
    peer_review = _workflow_authority_text("peer-review")
    peer_review_index = (WORKFLOWS_DIR / "peer-review.md").read_text(encoding="utf-8")
    arxiv_submission = _workflow_authority_text("arxiv-submission")
    shared_preflight = (TEMPLATES_DIR / "paper" / "publication-manuscript-root-preflight.md").read_text(
        encoding="utf-8"
    )

    _sf(
        write_paper,
        "gpd paper-build",
        "${PAPER_DIR}/BIBLIOGRAPHY-AUDIT.json",
        "reference_id -> bibtex_key",
        "bibliography or citation set changes",
        "strict review",
        context="write-paper bibliography audit refresh",
    )
    _sf(
        respond,
        "refresh",
        "${PAPER_DIR}/BIBLIOGRAPHY-AUDIT.json",
        "response letter",
        "complete",
        context="respond bibliography audit refresh",
    )
    _f(peer_review_index, "peer-review shared preflight include form", PUBLICATION_SHARED_PREFLIGHT_INCLUDE)
    _mf(
        peer_review,
        "{GPD_INSTALL_DIR}/templates/paper/publication-manuscript-root-preflight.md",
        "bibliography_audit_clean",
        "reproducibility_ready",
        context="peer-review bibliography audit strict fields",
    )
    _assert_loaded_authorities(
        "peer-review",
        "artifact_discovery",
        "references/publication/publication-review-round-artifacts.md",
    )
    _s(peer_review, "peer-review bibliography audit strict fields", "review-ready", "merely present")
    _sf(
        shared_preflight,
        "gpd paper-build",
        "regenerates",
        "ARTIFACT-MANIFEST.json",
        "BIBLIOGRAPHY-AUDIT.json",
        context="publication preflight paper-build authority",
    )
    _mf(
        write_paper,
        "{GPD_INSTALL_DIR}/references/publication/publication-bootstrap-preflight.md",
        PUBLICATION_RESPONSE_WRITER_HANDOFF_INCLUDE,
        context="write-paper bibliography workflow includes",
    )
    _mf(
        respond,
        PUBLICATION_BOOTSTRAP_PREFLIGHT_PATH,
        PUBLICATION_RESPONSE_WRITER_HANDOFF_INCLUDE,
        context="respond bibliography workflow includes",
    )
    _mf(
        arxiv_submission,
        PUBLICATION_BOOTSTRAP_PREFLIGHT_PATH,
        PUBLICATION_ROUND_ARTIFACTS_INCLUDE,
        context="arxiv bibliography workflow includes",
    )
    _f(arxiv_submission, "arxiv bibliography workflow includes", PUBLICATION_RESPONSE_WRITER_HANDOFF_INCLUDE)


def test_publication_workflows_keep_manuscript_local_reference_status_rooted_at_the_resolved_manuscript_directory() -> (
    None
):
    write_paper = _workflow_authority_text("write-paper")
    peer_review = _workflow_authority_text("peer-review")
    respond = _workflow_authority_text("respond-to-referees")
    arxiv_submission = _workflow_authority_text("arxiv-submission")

    _mf(
        write_paper,
        "{GPD_INSTALL_DIR}/references/publication/publication-bootstrap-preflight.md",
        PUBLICATION_RESPONSE_WRITER_HANDOFF_INCLUDE,
        context="write-paper manuscript-local support includes",
    )
    _sf(
        peer_review,
        "After resolution",
        "manuscript-local support artifacts",
        "same explicit manuscript directory",
        "BIBLIOGRAPHY_AUDIT_PATH",
        "bibliography_audit_path",
        "${MANUSCRIPT_ROOT}/BIBLIOGRAPHY-AUDIT.json",
        context="peer-review manuscript-local support artifacts",
    )
    _sf(
        respond,
        "refresh",
        "${PAPER_DIR}/BIBLIOGRAPHY-AUDIT.json",
        "response letter",
        "complete",
        "optional manuscript-local response-letter",
        context="respond manuscript-local support artifacts",
    )
    _mf(
        respond,
        PUBLICATION_BOOTSTRAP_PREFLIGHT_PATH,
        PUBLICATION_RESPONSE_WRITER_HANDOFF_INCLUDE,
        context="respond manuscript-local support includes",
    )
    _m(arxiv_submission, "arxiv manuscript-local support includes", PUBLICATION_BOOTSTRAP_PREFLIGHT_PATH)
    _sf(
        arxiv_submission,
        "Strict preflight reads",
        "ARTIFACT-MANIFEST.json",
        "BIBLIOGRAPHY-AUDIT.json",
        "reproducibility-manifest.json",
        "resolved manuscript root",
        "source of truth for packaging",
        context="arxiv manuscript-local support artifacts",
    )


def test_respond_to_referees_arxiv_handoff_uses_public_positional_arxiv_target() -> None:
    respond = _workflow_authority_text("respond-to-referees")
    help_workflow = (WORKFLOWS_DIR / "help.md").read_text(encoding="utf-8")
    arxiv_command = (COMMANDS_DIR / "arxiv-submission.md").read_text(encoding="utf-8")
    arxiv_workflow = _workflow_authority_text("arxiv-submission")
    arxiv_help_block = help_workflow.split(
        "**`gpd:arxiv-submission [manuscript root or .tex entrypoint]`**",
        1,
    )[1].split("**`gpd:explain", 1)[0]

    _pf(
        arxiv_command,
        'argument-hint: "[manuscript root or .tex entrypoint]"',
        "Paper target: $ARGUMENTS (optional manuscript root or `.tex` entrypoint",
        context="arxiv public positional manuscript target",
    )
    _s(
        arxiv_workflow,
        "arxiv public positional manuscript target",
        "Resolve manuscript target",
        "raw preflight",
        "$ARGUMENTS",
    )
    _p(arxiv_help_block, "arxiv help positional manuscript target", "`gpd:arxiv-submission paper/`")
    _f(arxiv_help_block, "arxiv help positional manuscript target", "--manuscript")

    _pf(
        respond,
        "`gpd:arxiv-submission <resolved-manuscript>`",
        "`gpd:arxiv-submission paper/curvature_flow_bounds.tex`",
        context="respond public arxiv positional handoff",
    )
    _ff(
        respond,
        "`$gpd-arxiv-submission <resolved-manuscript>`",
        "`$gpd-arxiv-submission paper/curvature_flow_bounds.tex`",
        "`gpd:arxiv-submission --manuscript",
        "`$gpd-arxiv-submission --manuscript",
        context="respond public arxiv positional handoff",
    )


def test_adaptive_mode_and_review_cadence_docs_stay_aligned() -> None:
    research_phase = _workflow_authority_text("research-phase")
    verify_work = _workflow_authority_text("verify-work")
    plan_phase = _workflow_authority_text("plan-phase")
    new_project = _workflow_authority_text("new-project")
    new_milestone = _workflow_authority_text("new-milestone")
    set_profile = (WORKFLOWS_DIR / "set-profile.md").read_text(encoding="utf-8")
    settings = (WORKFLOWS_DIR / "settings.md").read_text(encoding="utf-8")
    planning_config = (REFERENCES_DIR / "planning" / "planning-config.md").read_text(encoding="utf-8")
    research_modes = (REFERENCES_DIR / "research" / "research-modes.md").read_text(encoding="utf-8")
    meta_orchestration = (REFERENCES_DIR / "orchestration" / "meta-orchestration.md").read_text(encoding="utf-8")

    expected_anchor = "prior decisive evidence or an explicit approach lock"

    _s(research_phase, "adaptive mode decisive evidence anchor", "decisive prior evidence", "explicit approach lock")
    for text in (research_modes, meta_orchestration):
        _s(text, "adaptive mode decisive evidence anchor", expected_anchor)
    _assert_semantic_concept(
        plan_phase,
        "plan-phase adaptive mode evidence gate",
        required=("decisive evidence", "explicit approach lock"),
        forbidden=("phase 1-2", "phase 3+", "N≥3"),
        context="plan-phase adaptive mode stale thresholds",
    )
    _s(new_project, "new-project adaptive mode gate", "adaptive", "Research mode", "Review cadence")
    _sf(
        new_milestone,
        "adaptive starts",
        "prior decisive evidence",
        "project_contract_validation",
        "project_contract_load_info",
        "project_contract_gate.authoritative",
        "checkpoint with the user",
        "repair the stored contract",
        context="new-milestone adaptive mode gate",
    )
    _s(verify_work, "verify-work review cadence floor", "same contract-critical floor")
    _m(set_profile, "set-profile review cadence field boundary", "does NOT rewrite `execution.review_cadence`")
    _f(set_profile, "set-profile stale cadence field", "verify_between_waves")
    _s(settings, "settings review cadence independence", "independent of `model_profile`", "`research_mode`")
    _sf(
        planning_config,
        "wall-clock",
        "task budgets",
        "bounded segments",
        "phase number",
        "wave number",
        "`model_profile`",
        "do not create or retire these gates",
        context="planning config review cadence invariants",
    )
    _s(
        research_modes,
        "research-modes adaptive transition boundary",
        "There is no separate `adaptive_transition` block",
    )
    _sf(
        meta_orchestration,
        "evidence-driven",
        "phase-count-driven",
        "Proxy-only",
        "sanity-only",
        context="meta-orchestration adaptive mode gate",
    )


def test_settings_command_keeps_wrapper_thin_and_delegates_manual_to_workflow() -> None:
    settings_command = (COMMANDS_DIR / "settings.md").read_text(encoding="utf-8")

    _m(settings_command, "settings command workflow include", "@{GPD_INSTALL_DIR}/workflows/settings.md")
    _sf(
        settings_command,
        "wrapper thin",
        "parallel settings flow",
        "preset",
        "model-posture",
        "tier-model",
        "budget",
        "permission-sync",
        "local CLI bridge",
        context="settings command wrapper boundary",
    )


def test_help_surfaces_distinguish_runtime_slash_commands_from_local_cli_subcommands() -> None:
    help_command = (COMMANDS_DIR / "help.md").read_text(encoding="utf-8")
    help_workflow = (WORKFLOWS_DIR / "help.md").read_text(encoding="utf-8")

    _s(help_command, "help command workflow delegation", "GPD help", "delegating", "workflow-owned help surface")
    _mf(
        help_command,
        "@{GPD_INSTALL_DIR}/workflows/help.md",
        "## Step 2: Quick Start Extract (Default Output)",
        "## Step 3: Compact Command Index (--all)",
        "## Step 4: Single Command Detail Extract (--command <name>)",
        context="help command extraction markers",
    )

    assert_help_workflow_runtime_reference_contract(help_workflow)
    _m(help_workflow, "help workflow command context validator", "gpd validate command-context <name>")


def test_help_command_keeps_static_quick_start_while_workflow_owns_full_reference() -> None:
    help_command = (COMMANDS_DIR / "help.md").read_text(encoding="utf-8")
    help_workflow = (WORKFLOWS_DIR / "help.md").read_text(encoding="utf-8")
    quick_start_reference = _extract_between(help_workflow, "## Quick Start", "## Command Index")

    _m(help_command, "help command workflow include", "@{GPD_INSTALL_DIR}/workflows/help.md")
    assert_help_command_quick_start_extract_contract(help_command)
    assert_help_command_all_extract_contract(help_command)
    assert_help_command_single_command_extract_contract(help_command)
    _s(help_command, "help command wrapper-owned quick-start line", "Append", "wrapper-owned line")
    assert_help_workflow_runtime_reference_contract(help_workflow)
    _pf(
        help_workflow,
        "## Detailed Command Reference",
        context="help workflow command reference heading",
    )
    assert_help_workflow_quick_start_taxonomy_contract(quick_start_reference)


def test_help_workflow_uses_reachable_quick_start_for_resume_branch() -> None:
    help_workflow = (WORKFLOWS_DIR / "help.md").read_text(encoding="utf-8")
    quick_start = _extract_between(help_workflow, "## Quick Start", "## Command Index")
    returning_work = _extract_between(quick_start, "**Returning work**", "**Post-startup settings**")

    assert_runtime_reset_rediscovery_contract(
        help_workflow,
        extra_reset_fragments=("then run gpd resume in your normal terminal",),
        extra_reset_not_recovery_fragments=("then run gpd resume in your normal terminal",),
    )
    _ff(
        help_workflow,
        "## Contextual Help (State-Aware Variant)",
        context="help workflow stale contextual help branch",
    )
    _p(quick_start, "help quick start returning work branch", "Returning work", "gpd:resume-work")
    assert returning_work.index("gpd resume --recent") < returning_work.index("gpd:resume-work")
    _p(returning_work, "help quick start returning work commands", "gpd:progress", "gpd:suggest-next")
    _p(help_workflow, "help workflow tangent command", "gpd:tangent")


def test_help_and_execution_surfaces_wire_tangent_control_path() -> None:
    help_workflow = (WORKFLOWS_DIR / "help.md").read_text(encoding="utf-8")
    plan_phase = _workflow_authority_text("plan-phase")
    execute_phase = _workflow_authority_text("execute-phase")
    execute_plan = (WORKFLOWS_DIR / "execute-plan.md").read_text(encoding="utf-8")
    tangent_workflow = (WORKFLOWS_DIR / "tangent.md").read_text(encoding="utf-8")

    _p(help_workflow, "help tangent command surface", "gpd:tangent")
    assert re.search(
        r"gpd:tangent[^\n]*?(?:tangent|side investigation|alternative direction|parallel)", help_workflow, re.I
    )
    _p(plan_phase, "plan-phase tangent command surface", "gpd:tangent")
    assert re.search(r"gpd:tangent.*?(?:side|alternative|parallel|branch)", plan_phase, re.I | re.S)
    _p(execute_phase, "execute-phase tangent command surface", "gpd:tangent")
    assert re.search(r"gpd:tangent.*?(?:branch|follow-up|alternative)", execute_phase, re.I | re.S)
    _m(execute_phase, "execute-phase tangent return fields", "tangent_summary", "tangent_decision")
    _assert_prompt_concepts(
        execute_phase,
        {
            "live execution tangent bridge": (
                "tangent proposal",
                "tangent_summary",
                "tangent_decision",
            ),
            "no executor-initiated side work": ("executor initiative",),
        },
        context="execute-phase tangent control",
    )
    _m(execute_plan, "execute-plan tangent return fields", "tangent_summary", "tangent_decision")
    _assert_prompt_concepts(
        execute_plan,
        {
            "bounded stop tangent payload": (
                "bounded stop",
                "same execution payload",
                "new event family",
                "tangent_summary",
                "tangent_decision",
            ),
            "telemetry cannot auto-branch": ("existing `execution` payload", "Do not auto-branch", "side work"),
        },
        context="execute-plan tangent control",
    )
    _mf(
        tangent_workflow,
        "{GPD_INSTALL_DIR}/workflows/quick.md",
        "{GPD_INSTALL_DIR}/workflows/add-todo.md",
        "{GPD_INSTALL_DIR}/workflows/branch-hypothesis.md",
        context="tangent workflow command includes",
    )
    _assert_prompt_concepts(
        tangent_workflow,
        {
            "decision before selected command": (
                "$TANGENT_DECISION",
                "do not name",
                "gpd:quick",
                "gpd:add-todo",
                "gpd:branch-hypothesis",
                "gpd:execute-phase",
            ),
        },
        context="tangent workflow chooser",
    )
    _assert_prompt_concepts(
        (COMMANDS_DIR / "tangent.md").read_text(encoding="utf-8"),
        {
            "command stays at chooser until explicit outcome": (
                "exactly one tangent outcome",
                "do not present",
                "gpd:quick",
                "gpd:add-todo",
                "gpd:branch-hypothesis",
                "gpd:execute-phase",
                "gpd:tangent",
            ),
        },
        context="tangent command chooser",
    )


def test_planner_and_plan_phase_keep_no_silent_branching_and_exploit_tangent_suppression() -> None:
    planner = (REPO_ROOT / "src/gpd/agents/gpd-planner.md").read_text(encoding="utf-8")
    tangent_model = (REFERENCES_DIR / "planning" / "planner-tangent-decision-model.md").read_text(encoding="utf-8")
    plan_phase = _workflow_authority_text("plan-phase")
    for content in (planner + "\n" + tangent_model, plan_phase):
        _s(content, "planner no silent tangent branching", "silently", "gpd:tangent", "gpd:branch-hypothesis")
    _s(
        tangent_model,
        "planner tangent exploration boundary",
        "Explore mode",
        "analysis and comparison",
        "not branch creation",
    )
    _assert_prompt_concepts(
        tangent_model,
        {
            "explicit tangent branch outcome": ("Hypothesis branches", "explicit tangent outcome"),
        },
        context="planner tangent branch policy",
    )
    _assert_prompt_concepts(
        planner + "\n" + tangent_model,
        {
            "optional tangent suppression": (
                "Exploit suppresses optional tangents",
                "physics-validity failure blocks the current approach",
            ),
        },
        context="planner optional tangent suppression",
    )
    _sf(
        plan_phase,
        "do not auto-create",
        "git-backed branches",
        "git.branching_strategy",
        "suppresses optional tangents",
        "user explicitly requests",
        "gpd:branch-hypothesis",
        "exploit mode",
        context="plan-phase tangent suppression",
    )


def test_help_surfaces_describe_regression_check_as_metadata_scan_not_full_reverification() -> None:
    help_workflow = (WORKFLOWS_DIR / "help.md").read_text(encoding="utf-8")

    _sf(
        help_workflow,
        "SUMMARY",
        "frontmatter",
        "convention conflicts",
        "VERIFICATION",
        "canonical statuses",
        context="help regression check metadata scan",
    )
    _ff(
        help_workflow,
        "re-runs dimensional analysis",
        "re-runs limiting cases",
        "re-runs numerical checks",
        context="help regression check avoids full reverification",
    )


def test_help_surfaces_use_projectless_examples_that_satisfy_command_context_predicates() -> None:
    help_workflow = (WORKFLOWS_DIR / "help.md").read_text(encoding="utf-8")

    _assert_help_usage_line(help_workflow, "derive-equation")
    _assert_help_usage_line(help_workflow, "discover", "--depth")
    _assert_help_usage_line(help_workflow, "dimensional-analysis", ".md")
    _assert_help_usage_line(help_workflow, "limiting-cases", ".md")
    _assert_help_usage_line(help_workflow, "numerical-convergence", ".csv")
    _assert_help_usage_line(help_workflow, "parameter-sweep", "--param", "--range")
    _assert_help_usage_line(help_workflow, "compare-experiment", ".csv")
    _assert_help_usage_line(help_workflow, "compare-results", ".md")
    _assert_help_usage_line(help_workflow, "explain")
    _assert_help_usage_line(help_workflow, "literature-review")
    _assert_help_usage_line(help_workflow, "digest-knowledge")
    _assert_help_usage_line(help_workflow, "review-knowledge", "GPD/knowledge/")
    _assert_help_usage_line(help_workflow, "sensitivity-analysis", "--target", "--params", "--method")


def test_help_surfaces_frame_relaxed_technical_analysis_lane_honestly() -> None:
    help_workflow = (WORKFLOWS_DIR / "help.md").read_text(encoding="utf-8")

    _sf(
        help_workflow,
        "Project-aware technical-analysis lane",
        "GPD/analysis/",
        "GPD/sweeps/",
        "gpd:graph",
        "gpd:error-propagation",
        "not part of this relaxed current-workspace lane",
        context="help relaxed technical-analysis lane",
    )

    _sf(
        help_workflow,
        "Current-workspace durable outputs",
        "outside a project",
        "explicit derivation target",
        "explicit file path",
        "--param",
        "--range",
        "--target",
        "--params",
        context="help relaxed technical-analysis lane",
    )


def test_expanded_artifact_intake_surfaces_use_cli_text_extraction_helper() -> None:
    peer_review_workflow = _workflow_authority_text("peer-review")
    help_workflow = (WORKFLOWS_DIR / "help.md").read_text(encoding="utf-8")
    digest_command = (COMMANDS_DIR / "digest-knowledge.md").read_text(encoding="utf-8")
    digest_workflow = (WORKFLOWS_DIR / "digest-knowledge.md").read_text(encoding="utf-8")
    referee = (AGENTS_DIR / "gpd-referee.md").read_text(encoding="utf-8")
    peer_review_help_block = help_workflow.split(
        "**`gpd:peer-review [paper directory | manuscript path | explicit artifact path]`**",
        1,
    )[1].split("**`gpd:respond-to-referees", 1)[0]
    review_suffixes = ("`.tex`", "`.md`", "`.txt`", "`.pdf`", "`.docx`", "`.csv`", "`.tsv`", "`.xlsx`", "`.xlsm`")
    digest_suffixes = ("`.md`", "`.txt`", "`.pdf`", "`.docx`", "`.csv`", "`.tsv`", "`.xlsx`")
    plain_digest_suffixes = ("`.md`", "`.txt`", "`.csv`", "`.tsv`")
    extracted_digest_suffixes = ("`.pdf`", "`.docx`", "`.xlsx`")
    artifact_text_command = "`gpd validate artifact-text <path> --output <txt-path>`"

    _assert_fragment_groups(
        (_sf, peer_review_workflow, "peer-review artifact intake", (*review_suffixes, "manuscript directory path")),
        (
            _sf,
            peer_review_workflow,
            "peer-review artifact intake",
            ("centralized target-aware init", "command-context preflight", "authoritative manuscript resolver"),
        ),
        (
            _sf,
            peer_review_workflow,
            "peer-review artifact intake",
            ("project-backed manuscript review", "`paper/`", "`manuscript/`", "`draft/`"),
        ),
        (
            _sf,
            peer_review_workflow,
            "peer-review artifact intake",
            (
                "points at one artifact path",
                "Explicit external artifact intake",
                "must not widen",
                "default in-project manuscript family",
            ),
        ),
        (
            _mf,
            peer_review_workflow,
            "peer-review artifact text validator",
            ('gpd validate artifact-text "$RESOLVED_MANUSCRIPT" --output ${REVIEW_ROOT}/MANUSCRIPT-TEXT.txt',),
        ),
        (
            _pf,
            help_workflow,
            "peer-review help public command line",
            ("- `gpd:peer-review [paper directory | manuscript path | explicit artifact path]`",),
        ),
        (
            _sf,
            help_workflow,
            "peer-review help explicit artifact suffix policy",
            ("command-policy supported suffixes", "publication-artifact paths"),
        ),
        (
            _ff,
            peer_review_help_block,
            "peer-review help explicit artifact suffix policy",
            ("`.txt`, `.pdf`, `.docx`, `.csv`, `.tsv`, `.xlsx`, and `.xlsm`", "pdftotext"),
        ),
        (
            _mf,
            peer_review_help_block,
            "peer-review help artifact text validator",
            ("gpd validate artifact-text <path> --output <txt-path>",),
        ),
        (
            _mf,
            peer_review_help_block,
            "peer-review help explicit artifact example",
            ("`gpd:peer-review data/observables.csv`",),
        ),
        (
            _sf,
            help_workflow,
            "digest help explicit source examples",
            ("Example document source", "gpd:digest-knowledge", ".docx", "Example tabular source", ".csv"),
        ),
        (_sf, digest_command, "digest-knowledge source intake", ("explicit source-file intake", *digest_suffixes)),
        (
            _sf,
            digest_command,
            "digest-knowledge source intake",
            ("text extraction", "inside the workflow", artifact_text_command),
        ),
        (_sf, digest_workflow, "digest-knowledge workflow source intake", ("`source_path` suffixes", *digest_suffixes)),
        (
            _sf,
            digest_workflow,
            "digest workflow plain text source intake",
            ("read", *plain_digest_suffixes, "directly as source surfaces"),
        ),
        (
            _sf,
            digest_workflow,
            "digest-knowledge workflow source intake",
            (*extracted_digest_suffixes, "working text surface", artifact_text_command),
        ),
        (
            _sf,
            digest_workflow,
            "digest-knowledge workflow source intake",
            ("source began", *extracted_digest_suffixes, "preserve the original artifact path", "metadata"),
        ),
        (
            _sf,
            referee,
            "referee artifact intake",
            (
                "standalone `.txt`, `.csv`, or `.tsv`",
                "extracted text surface",
                "`.pdf`, `.docx`, `.xlsx`, or `.xlsm`",
                "primary review surface",
            ),
        ),
    )
    _s(
        peer_review_workflow,
        "peer-review artifact intake staged init",
        "gpd --raw init peer-review",
        "--stage bootstrap",
    )
    _f(peer_review_workflow, "peer-review artifact text validator", "pdftotext")
    _assert_help_usage_line(peer_review_help_block, "peer-review", ".docx")
