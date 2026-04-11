from __future__ import annotations

import re
from pathlib import Path

import yaml

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "src" / "gpd" / "specs" / "templates"
_CONTRACT_TEMPLATES: dict[str, dict[str, str]] = {
    "project-contract-schema.md": {},
    "plan-contract-schema.md": {"type": "plan-contract-schema"},
    "contract-results-schema.md": {"type": "contract-results-schema"},
    "proof-redteam-schema.md": {"type": "proof-redteam-schema"},
}


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

    assert "Before you draft the first `PROJECT_CONTRACT_JSON` payload, load the full" in workflow
    assert "active runtime's file-read tool" in workflow
    assert "Project contract schema visibility" in workflow
    assert "do not restate or fork the contract schema here" in workflow
    assert "Project contract schema-critical excerpt" not in workflow


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


def test_plan_prompt_keeps_canonical_schema_visible_before_contract_output() -> None:
    phase_prompt = (_TEMPLATES_DIR / "phase-prompt.md").read_text(encoding="utf-8")

    schema_ref = "@{GPD_INSTALL_DIR}/templates/plan-contract-schema.md"
    first_contract_block = phase_prompt.index("\ncontract:")

    assert phase_prompt.index(schema_ref) < first_contract_block
    assert "Use the canonical schema below before drafting any `contract:` block." in phase_prompt[:first_contract_block]
    assert "Quick contract rules:" in phase_prompt[:first_contract_block]

    pre_contract_text = phase_prompt[:first_contract_block]
    for token in _phase_prompt_pre_contract_tokens():
        assert token in pre_contract_text, f"{token!r} is not model-visible before the PLAN contract example"


def test_planner_subagent_excerpt_tracks_plan_contract_schema_vocabulary() -> None:
    canonical_schema = (_TEMPLATES_DIR / "plan-contract-schema.md").read_text(encoding="utf-8")
    subagent_prompt = (_TEMPLATES_DIR / "planner-subagent-prompt.md").read_text(encoding="utf-8")

    excerpt_start = subagent_prompt.index("**PLAN contract schema-critical excerpt:**")
    output_start = subagent_prompt.index("**Project State:**")
    excerpt = subagent_prompt[excerpt_start:output_start]

    assert "Do not rely on that path reference alone" in subagent_prompt[:excerpt_start]
    assert subagent_prompt.index("@{GPD_INSTALL_DIR}/templates/plan-contract-schema.md") < excerpt_start

    for token in _plan_contract_schema_critical_tokens():
        assert token in canonical_schema, f"canonical schema no longer defines {token!r}"
        assert token in excerpt, f"planner subagent excerpt no longer surfaces {token!r}"

    claim_kind_enum = _extract_backtick_enum(canonical_schema, "claim_kind")
    for token in claim_kind_enum:
        assert token in excerpt, f"planner subagent excerpt no longer surfaces claim_kind value {token!r}"


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
