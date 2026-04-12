from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from gpd.contracts import CONTRACT_LINK_RELATION_VALUES, CONTRACT_REFERENCE_ACTION_VALUES

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "src" / "gpd" / "specs" / "templates"
_CONTRACT_TEMPLATES: dict[str, dict[str, str]] = {
    "project-contract-schema.md": {},
    "plan-contract-schema.md": {"type": "plan-contract-schema"},
    "contract-results-schema.md": {"type": "contract-results-schema"},
    "proof-redteam-schema.md": {"type": "proof-redteam-schema"},
}

_REPO_ROOT = Path(__file__).resolve().parent.parent
_WORKFLOWS_DIR = _REPO_ROOT / "src" / "gpd" / "specs" / "workflows"
_CONTRACT_RESULTS_STAGE_MANIFESTS = (
    "execute-phase-stage-manifest.json",
    "verify-work-stage-manifest.json",
)
CONTRACT_RESULTS_SCHEMA_REF = "@{GPD_INSTALL_DIR}/templates/contract-results-schema.md"
CONTRACT_RESULTS_STAGE_TEMPLATE = "templates/contract-results-schema.md"


def _load_frontmatter(path: Path) -> dict[str, object]:
    contents = path.read_text(encoding="utf-8")
    assert contents.startswith("---"), f"{path} is missing front matter"
    parts = contents.split("---", 2)
    assert len(parts) == 3, f"{path} has malformed front matter"
    frontmatter = parts[1].strip()
    return yaml.safe_load(frontmatter) or {}


def test_contract_schema_templates_keep_template_version_and_type() -> None:
    for relpath, expectations in _CONTRACT_TEMPLATES.items():
        template_path = _TEMPLATES_DIR / relpath
        assert template_path.is_file(), f"{relpath} disappeared"

        frontmatter = _load_frontmatter(template_path)
        assert frontmatter.get("template_version") == 1

        expected_type = expectations.get("type")
        if expected_type is not None:
            assert frontmatter.get("type") == expected_type


def test_state_schema_references_project_contract_schema_without_forking_it() -> None:
    state_schema = (_TEMPLATES_DIR / "state-json-schema.md").read_text(encoding="utf-8")

    assert "@{GPD_INSTALL_DIR}/templates/project-contract-schema.md" in state_schema
    assert "This state schema intentionally does not restate" in state_schema
    assert "\"observables\": [" not in state_schema
    assert "Project Contract Object Rules" not in state_schema


def test_new_project_workflow_loads_canonical_project_contract_schema() -> None:
    workflow = (
        Path(__file__).resolve().parent.parent / "src" / "gpd" / "specs" / "workflows" / "new-project.md"
    ).read_text(encoding="utf-8")

    assert "Project contract schema visibility" in workflow
    assert "ensure `@{GPD_INSTALL_DIR}/templates/project-contract-schema.md` is loaded" in workflow
    assert "do not restate or fork the contract schema here" in workflow
    assert "Project contract schema-critical excerpt" not in workflow


def test_summary_template_surfaces_required_frontmatter_fields() -> None:
    summary_template = (_TEMPLATES_DIR / "summary.md").read_text(encoding="utf-8")

    required_tokens = (
        "## Required Frontmatter",
        "`phase`",
        "`plan`",
        "`depth`",
        "minimal | standard | full | complex",
        "`provides`",
        "`completed`",
        "`plan_contract_ref`",
    )

    for token in required_tokens:
        assert token in summary_template


def test_verification_template_surfaces_required_frontmatter_fields() -> None:
    verification_template = (_TEMPLATES_DIR / "verification-report.md").read_text(encoding="utf-8")

    required_tokens = (
        "## Required Frontmatter",
        "`phase`",
        "`verified`",
        "`status`",
        "passed | gaps_found | expert_needed | human_needed",
        "`score`",
        "`plan_contract_ref`",
    )

    for token in required_tokens:
        assert token in verification_template


def test_prompt_workflow_verbosity_trims_stay_concise() -> None:
    root = Path(__file__).resolve().parent.parent
    execute_phase = (root / "src/gpd/specs/workflows/execute-phase.md").read_text(encoding="utf-8")
    new_project = (root / "src/gpd/specs/workflows/new-project.md").read_text(encoding="utf-8")
    planner = (root / "src/gpd/agents/gpd-planner.md").read_text(encoding="utf-8")

    assert "Parse JSON for: `executor_model`" not in execute_phase
    assert "Parse JSON for: `selected_protocol_bundle_ids`" not in execute_phase
    assert "project_contract` payload is the `ResearchContract` object" not in new_project
    assert "perform ONE confirmatory web_search" not in planner


def test_state_schema_uses_concise_continuation_compatibility_tables() -> None:
    schema = (_TEMPLATES_DIR / "state-json-schema.md").read_text(encoding="utf-8")

    assert "| Rule | Requirement |" in schema
    assert "| Direction | Allowed behavior |" in schema
    assert "| Source | Status |" in schema
    assert "Older `session` payloads may hydrate only missing canonical handoff or machine fields" in schema
    assert "Populated canonical fields must not be overwritten by stale `session` data" in schema
    assert "Derived compatibility mirror from execution lineage; advisory only and never a second authority" in schema
    assert "Raw compatibility cues are backend-only intake signals" in schema
    assert "`session` stores the markdown-compatible session timestamp" not in schema
    assert "STATE.md and the legacy `session` object are projections of this authority" not in schema


def test_verify_work_contract_floor_uses_parsed_init_fields_without_placeholders() -> None:
    workflow = (
        Path(__file__).resolve().parent.parent / "src" / "gpd" / "specs" / "workflows" / "verify-work.md"
    ).read_text(encoding="utf-8")

    init_parse = workflow.index("Parse the init JSON for the wrapper-facing fields only")
    contract_floor = workflow.index("After parsing init, preserve these contract-critical fields")

    assert contract_floor > init_parse
    assert "<shared_contract_floor>" not in workflow
    assert "{project_contract_gate}" not in workflow[:contract_floor]
    assert "{project_contract_load_info}" not in workflow[:contract_floor]
    assert "{contract_intake}" not in workflow[:contract_floor]


def test_contract_results_schema_keeps_required_vocab_without_legacy_compatibility_wording() -> None:
    schema = (_TEMPLATES_DIR / "contract-results-schema.md").read_text(encoding="utf-8")

    required_tokens = (
        "`contract_results`",
        "`comparison_verdicts`",
        "`proof_audit`",
        "claims|deliverables|acceptance_tests -> passed|partial|failed|blocked|not_attempted",
        "references -> completed|missing|not_applicable",
        "forbidden_proxies -> rejected|violated|unresolved|not_applicable",
        "proof_audit.completeness: complete | incomplete",
        "proof_audit.quantifier_status: matched | narrowed | mismatched | unclear",
        "proof_audit.scope_status: matched | narrower_than_claim | mismatched | unclear",
        "proof_audit.counterexample_status: none_found | counterexample_found | not_attempted | narrowed_claim",
        "verdict: pass|tension|fail|inconclusive",
        "suggested_contract_checks",
    )

    for token in required_tokens:
        assert token in schema

    assert "compatible with `verification-report.md`" not in schema
    assert "Author canonical form" in schema
    assert "salvage narrow singleton string/list drift and closed-enum case drift" in schema
    assert "do not rely on salvage" in schema

    placeholder_fragments = (
        "[what was actually established]",
        "[what the adversarial proof review concluded]",
        "[optional artifact sha256 for stale-audit detection]",
        "[sha256 of the canonical proof-redteam artifact]",
        "[required when a proof-bearing claim passes]",
        "[what artifact exists and why it matters]",
        "[what decisive test happened and what it showed]",
        "[how the anchor was surfaced]",
        "[why this proxy was or was not allowed]",
        "path/to/artifact",
    )
    for placeholder in placeholder_fragments:
        assert placeholder not in schema


def test_plan_prompt_keeps_canonical_schema_visible_before_contract_output() -> None:
    phase_prompt = (_TEMPLATES_DIR / "phase-prompt.md").read_text(encoding="utf-8")

    schema_ref = "@{GPD_INSTALL_DIR}/templates/plan-contract-schema.md"
    first_contract_block = phase_prompt.index("\ncontract:")
    pre_contract_text = phase_prompt[:first_contract_block]

    assert phase_prompt.index(schema_ref) < first_contract_block
    assert pre_contract_text.count(schema_ref) == 1
    assert pre_contract_text.index(schema_ref) < pre_contract_text.index("schema_version: 1")
    assert "Project Contract Object Rules" not in pre_contract_text

    for token in _phase_prompt_pre_contract_tokens():
        assert token in pre_contract_text, f"{token!r} is not model-visible before the PLAN contract example"


def test_plan_prompt_pre_contract_guidance_stays_compact_and_non_forked() -> None:
    phase_prompt = (_TEMPLATES_DIR / "phase-prompt.md").read_text(encoding="utf-8")
    first_contract_block = phase_prompt.index("\ncontract:")
    pre_contract_text = phase_prompt[:first_contract_block]

    assert len(pre_contract_text) < 3_500
    assert pre_contract_text.count("@{GPD_INSTALL_DIR}/templates/plan-contract-schema.md") == 1
    assert pre_contract_text.count("schema_version: 1") == 1
    assert pre_contract_text.count("acceptance_tests") <= 3
    assert "observables:" not in pre_contract_text
    assert "Project Contract Object Rules" not in pre_contract_text


def test_planner_subagent_excerpt_tracks_plan_contract_schema_vocabulary() -> None:
    canonical_schema = (_TEMPLATES_DIR / "plan-contract-schema.md").read_text(encoding="utf-8")
    subagent_prompt = (_TEMPLATES_DIR / "planner-subagent-prompt.md").read_text(encoding="utf-8")

    excerpt_start = subagent_prompt.index("**PLAN contract schema-critical excerpt:**")
    output_start = subagent_prompt.index("**Project State:**")
    excerpt = subagent_prompt[excerpt_start:output_start]

    assert "@{GPD_INSTALL_DIR}/templates/plan-contract-schema.md" in subagent_prompt[:excerpt_start]
    assert subagent_prompt.index("@{GPD_INSTALL_DIR}/templates/plan-contract-schema.md") < excerpt_start
    assert "Project Contract Object Rules" not in excerpt
    assert excerpt.count("claims") <= 4

    for token in _plan_contract_schema_critical_tokens():
        assert token in canonical_schema, f"canonical schema no longer defines {token!r}"
        assert token in excerpt, f"planner subagent excerpt no longer surfaces {token!r}"

    claim_kind_enum = _extract_backtick_enum(canonical_schema, "claim_kind")
    for token in claim_kind_enum:
        assert token in excerpt, f"planner subagent excerpt no longer surfaces claim_kind value {token!r}"


def test_phase_prompt_pre_contract_surfaces_link_relation_and_action_vocab() -> None:
    phase_prompt = (_TEMPLATES_DIR / "phase-prompt.md").read_text(encoding="utf-8")
    first_contract_block = phase_prompt.index("\ncontract:")
    pre_contract_text = phase_prompt[:first_contract_block]

    link_enum = " | ".join(CONTRACT_LINK_RELATION_VALUES)
    reference_action_enum = " | ".join(CONTRACT_REFERENCE_ACTION_VALUES)
    assert f"`links[].relation` uses `{link_enum}`" in pre_contract_text
    assert f"`references[].required_actions` uses `{reference_action_enum}`" in pre_contract_text


def test_phase_prompt_pre_contract_avoids_relisting_full_contract_enums() -> None:
    phase_prompt = (_TEMPLATES_DIR / "phase-prompt.md").read_text(encoding="utf-8")
    first_contract_block = phase_prompt.index("\ncontract:")
    pre_contract_text = phase_prompt[:first_contract_block]

    for fragment in (
        "`claim_kind:",
        "`kind: scalar",
        "`kind: figure",
        "`kind: paper",
        "`role: definition",
    ):
        assert fragment not in pre_contract_text


def test_review_agents_reference_return_envelope_schema() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    agents_dir = repo_root / "src" / "gpd" / "agents"

    for agent in ("gpd-review-physics.md", "gpd-review-math.md"):
        text = (agents_dir / agent).read_text(encoding="utf-8")
        assert "@{GPD_INSTALL_DIR}/references/orchestration/agent-infrastructure.md" in text
        assert "gpd_return" in text


def test_planner_subagent_excerpt_surfaces_link_relation_and_action_vocab() -> None:
    subagent_prompt = (_TEMPLATES_DIR / "planner-subagent-prompt.md").read_text(encoding="utf-8")

    excerpt_start = subagent_prompt.index("**PLAN contract schema-critical excerpt:**")
    excerpt_end = subagent_prompt.index("**Project State:**")
    excerpt = subagent_prompt[excerpt_start:excerpt_end]

    link_enum = " | ".join(CONTRACT_LINK_RELATION_VALUES)
    reference_action_enum = " | ".join(CONTRACT_REFERENCE_ACTION_VALUES)
    assert f"Link relations use `{link_enum}`" in excerpt
    assert f"reference actions use `{reference_action_enum}`" in excerpt


def test_planner_subagent_excerpt_highlights_durable_grounding() -> None:
    subagent_prompt = (_TEMPLATES_DIR / "planner-subagent-prompt.md").read_text(encoding="utf-8")

    excerpt_start = subagent_prompt.index("**PLAN contract schema-critical excerpt:**")
    excerpt_end = subagent_prompt.index("**Project State:**")
    excerpt = subagent_prompt[excerpt_start:excerpt_end]

    assert "_has_contract_grounding_context" in excerpt
    assert "must_surface: true" in excerpt


def test_plan_contract_schema_describes_grounding_and_uncertainty_gates() -> None:
    plan_schema = (_TEMPLATES_DIR / "plan-contract-schema.md").read_text(encoding="utf-8")

    assert "_has_contract_grounding_context" in plan_schema
    assert "collect_plan_contract_integrity_errors" in plan_schema
    assert "_collect_strict_contract_results_errors" in plan_schema


def test_execute_plan_contract_results_schema_precedes_contract_results() -> None:
    content = (_WORKFLOWS_DIR / "execute-plan.md").read_text(encoding="utf-8")
    _assert_schema_precedes_first_contract_marker(content, CONTRACT_RESULTS_SCHEMA_REF)


def test_execute_phase_contract_results_schema_precedes_contract_results() -> None:
    content = (_WORKFLOWS_DIR / "execute-phase.md").read_text(encoding="utf-8")
    _assert_schema_precedes_first_contract_marker(content, CONTRACT_RESULTS_SCHEMA_REF)


def test_stage_manifests_keep_contract_results_schema_reference() -> None:
    for manifest_filename in _CONTRACT_RESULTS_STAGE_MANIFESTS:
        manifest_path = _WORKFLOWS_DIR / manifest_filename
        assert manifest_path.exists(), f"{manifest_filename} missing"
        assert _stage_manifest_has_template(manifest_path, CONTRACT_RESULTS_STAGE_TEMPLATE), (
            f"{manifest_filename} dropped {CONTRACT_RESULTS_STAGE_TEMPLATE}"
        )


def _assert_schema_precedes_first_contract_marker(content: str, schema_ref: str, marker: str = "contract_results") -> None:
    marker_index = content.find(marker)
    assert marker_index != -1, "Content lacks contract_results marker"
    schema_index = content.find(schema_ref)
    assert schema_index != -1, f"{schema_ref} missing from content"
    assert schema_index < marker_index, f"{schema_ref} must appear before the first {marker}"


def _stage_manifest_has_template(manifest_path: Path, template: str) -> bool:
    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    for stage in manifest_data.get("stages", []):
        authorities = stage.get("loaded_authorities", []) + stage.get("must_not_eager_load", [])
        if template in authorities:
            return True
    return False


def _plan_contract_schema_critical_tokens() -> tuple[str, ...]:
    return (
        "schema_version: 1",
        "scope",
        "context_intake",
        "uncertainty_markers",
        "claims",
        "deliverables",
        "acceptance_tests",
        "forbidden_proxies",
        "references",
        "approach_policy",
        "observables",
        "links",
        "scope.question",
        "scope.in_scope",
        "claim_kind",
        "proof_deliverables",
        "parameters",
        "hypotheses",
        "conclusion_clauses",
        "proof_obligation",
        "must_surface",
        "required_actions",
        "applies_to",
        "carry_forward_to",
    )


def _phase_prompt_pre_contract_tokens() -> tuple[str, ...]:
    return (
        "schema_version: 1",
        "tool_requirements",
        "researcher_setup",
        "scope.in_scope",
        "context_intake",
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
        "approach_policy",
        "proof_obligation",
    )


def _extract_backtick_enum(markdown: str, field_name: str) -> tuple[str, ...]:
    match = re.search(rf"- `{re.escape(field_name)}: ([^`]+)`", markdown)
    assert match is not None, f"could not find backtick enum for {field_name}"
    return tuple(value.strip() for value in match.group(1).split("|") if value.strip())
