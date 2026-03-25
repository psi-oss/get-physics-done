from __future__ import annotations

from pathlib import Path

from gpd import registry

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_DIR = REPO_ROOT / "src/gpd/commands"
REFERENCES_DIR = REPO_ROOT / "src/gpd/specs/references"
TEMPLATES_DIR = REPO_ROOT / "src/gpd/specs/templates"


def _read_command(name: str) -> str:
    return (COMMANDS_DIR / f"{name}.md").read_text(encoding="utf-8")


def test_review_grade_commands_surface_registry_contract_requirements_in_source() -> None:
    command_names = ("write-paper", "respond-to-referees", "verify-work", "arxiv-submission")

    for command_name in command_names:
        source = _read_command(command_name)
        contract = registry.get_command(command_name).review_contract

        assert contract is not None
        assert "review-contract:" in source
        assert f"review_mode: {contract.review_mode}" in source

        for output in contract.required_outputs:
            assert output in source
        for evidence in contract.required_evidence:
            assert evidence in source
        for blocker in contract.blocking_conditions:
            assert blocker in source
        for check in contract.preflight_checks:
            assert check in source

        if contract.required_state:
            assert f"required_state: {contract.required_state}" in source


def test_verify_work_review_contract_uses_phase_scoped_output_path() -> None:
    contract = registry.get_command("verify-work").review_contract

    assert contract is not None
    assert contract.required_outputs == ["GPD/phases/XX-name/XX-VERIFICATION.md"]
    assert "GPD/phases/XX-name/XX-VERIFICATION.md" in _read_command("verify-work")


def test_respond_to_referees_review_contract_uses_round_suffixed_output_paths() -> None:
    contract = registry.get_command("respond-to-referees").review_contract

    assert contract is not None
    assert contract.required_outputs == [
        "GPD/paper/REFEREE_RESPONSE{round_suffix}.md",
        "GPD/AUTHOR-RESPONSE{round_suffix}.md",
    ]
    assert "GPD/paper/REFEREE_RESPONSE{round_suffix}.md" in _read_command("respond-to-referees")
    assert "GPD/AUTHOR-RESPONSE{round_suffix}.md" in _read_command("respond-to-referees")


def test_summary_template_surfaces_plan_contract_ref_rule_for_contract_ledgers() -> None:
    summary_template = (TEMPLATES_DIR / "summary.md").read_text(encoding="utf-8")

    assert "If `contract_results` or `comparison_verdicts` are present, `plan_contract_ref` is also required." in summary_template
    assert "plan_contract_ref (required when `contract_results` or `comparison_verdicts` are present)" in summary_template
    assert "Reload `@{GPD_INSTALL_DIR}/templates/contract-results-schema.md` immediately before writing the YAML" in summary_template
    assert "canonical project-root-relative `GPD/phases/XX-name/{phase}-{plan}-PLAN.md#/contract` path" in summary_template
    assert "Choose the depth explicitly" in summary_template
    assert "default: full" not in summary_template
    assert "Keep `uncertainty_markers` explicit and user-visible" in summary_template
    assert "uncertainty_markers:" in summary_template
    assert "weakest_anchors: [anchor-1]" in summary_template
    assert "disconfirming_observations: [observation-1]" in summary_template
    assert "For contract-backed summaries, `contract_results` is required" in summary_template
    assert "It must not be absolute, parent-traversing, or collapse to a bare sibling reference." in summary_template
    assert "`completed` needs non-empty `completed_actions`" in summary_template
    assert "If a decisive external anchor was used, include `reference_id`" in summary_template
    assert "Do not invent extra keys in `contract_results`, `comparison_verdicts`, or `suggested_contract_checks`" in summary_template


def test_verification_template_surfaces_strict_passed_and_blocked_semantics() -> None:
    verification_template = (TEMPLATES_DIR / "verification-report.md").read_text(encoding="utf-8")

    assert "status: passed` is strict" in verification_template
    assert "every claim, deliverable, and acceptance_test entry in `contract_results` is `passed`" in verification_template
    assert "If any contract target is `partial`, `failed`, `blocked`, `missing`, or `unresolved`, use `gaps_found`, `expert_needed`, or `human_needed` instead of `passed`." in verification_template
    assert "every reference entry is `completed`" in verification_template
    assert "every `must_surface` reference has all `required_actions` recorded in `completed_actions`" in verification_template
    assert "Reload `@{GPD_INSTALL_DIR}/templates/contract-results-schema.md` immediately before writing the YAML" in verification_template
    assert "verification-side `suggested_contract_checks`" in verification_template
    assert "same canonical schema surface as the rest of the verification ledger" in verification_template
    assert "uncertainty_markers:" in verification_template
    assert "weakest_anchors: [anchor-1]" in verification_template
    assert "disconfirming_observations: [observation-1]" in verification_template


def test_research_verification_template_surfaces_non_empty_uncertainty_markers() -> None:
    research_verification = (TEMPLATES_DIR / "research-verification.md").read_text(encoding="utf-8")

    assert "Use `@{GPD_INSTALL_DIR}/templates/verification-report.md` for the canonical verification frontmatter contract." in research_verification
    assert "verification-side `suggested_contract_checks` entries are part of the same canonical schema surface" in research_verification
    assert "comparison_kind: [benchmark | prior_work | experiment | cross_method | baseline | other]" in research_verification
    assert "comparison_kind: [benchmark | prior_work | experiment | cross_method | baseline | other | \"\"]" not in research_verification
    assert "comparison_kind: benchmark | prior_work | experiment | cross_method | baseline | other" in research_verification
    assert 'comparison_kind: "benchmark | prior_work | experiment | cross_method | baseline | other"' in research_verification
    assert "omit both `comparison_kind` and `comparison_reference_id` instead of leaving blank placeholders" in research_verification
    assert "uncertainty_markers:" in research_verification
    assert "weakest_anchors: [anchor-1]" in research_verification
    assert "disconfirming_observations: [observation-1]" in research_verification


def test_write_paper_prompt_discovers_plan_scoped_phase_summaries() -> None:
    source = _read_command("write-paper")

    assert "ls GPD/phases/*/*-SUMMARY.md 2>/dev/null" in source


def test_write_paper_prompt_loads_figure_tracker_schema_before_updating_tracker() -> None:
    source = _read_command("write-paper")

    assert "@{GPD_INSTALL_DIR}/templates/paper/figure-tracker.md" in source
    assert "GPD/paper/FIGURE_TRACKER.md" in source
    assert "canonical schema/template surfaces it loads there" in source


def test_comparison_templates_match_full_comparison_verdict_subject_kind_enum() -> None:
    expected = "subject_kind: claim|deliverable|acceptance_test|reference"
    expected_kind = "comparison_kind: benchmark|prior_work|experiment|cross_method|baseline|other"
    internal = (TEMPLATES_DIR / "paper" / "internal-comparison.md").read_text(encoding="utf-8")
    experimental = (TEMPLATES_DIR / "paper" / "experimental-comparison.md").read_text(encoding="utf-8")
    contract_results = (TEMPLATES_DIR / "contract-results-schema.md").read_text(encoding="utf-8")

    assert expected in internal
    assert expected in experimental
    assert expected_kind in internal
    assert expected_kind in experimental
    assert expected_kind in contract_results
    assert "uncertainty_markers:" in contract_results
    assert "weakest_anchors: [anchor-1]" in contract_results
    assert "disconfirming_observations: [observation-1]" in contract_results
    assert "Only `subject_role: decisive` closes a decisive requirement" in internal
    assert "Only `subject_role: decisive` closes a decisive requirement" in experimental
    assert "Must be the canonical project-root-relative `GPD/phases/XX-name/XX-YY-PLAN.md#/contract` path" in contract_results


def test_contract_ledgers_surface_decisive_only_verdict_rules_and_strict_suggested_check_keys() -> None:
    contract_results = (TEMPLATES_DIR / "contract-results-schema.md").read_text(encoding="utf-8")
    verification_template = (TEMPLATES_DIR / "verification-report.md").read_text(encoding="utf-8")

    assert "Do not invent `artifact` or `other` subject kinds" in contract_results
    assert "Only `subject_role: decisive` satisfies a required decisive comparison" in contract_results
    assert "`subject_role` must be explicit on every verdict" in contract_results
    assert "canonical project-root-relative `GPD/phases/XX-name/XX-YY-PLAN.md#/contract` path" in contract_results
    assert "If a decisive external anchor was used, include `reference_id`" in contract_results
    assert "reference-backed decisive comparison is required" in contract_results
    assert "acceptance test with `kind: benchmark` or `kind: cross_method`" in contract_results
    assert "`contract_results` and every nested entry use a closed schema" in contract_results
    assert "uncertainty_markers:" in contract_results
    assert "weakest_anchors: [anchor-1]" in contract_results
    assert "disconfirming_observations: [observation-1]" in contract_results
    assert "Invented keys such as `check_id` fail validation." in contract_results
    assert "Allowed keys are exactly `check`, `reason`, `suggested_subject_kind`, `suggested_subject_id`, and `evidence_path`." in verification_template


def test_contract_ledgers_surface_forbidden_proxy_bindings_and_action_vocabulary() -> None:
    summary_template = (TEMPLATES_DIR / "summary.md").read_text(encoding="utf-8")
    contract_results = (TEMPLATES_DIR / "contract-results-schema.md").read_text(encoding="utf-8")
    state_schema = (TEMPLATES_DIR / "state-json-schema.md").read_text(encoding="utf-8")

    assert "forbidden_proxy_id" in summary_template
    assert "forbidden_proxy_id" in contract_results
    assert "action vocabulary: `read`, `use`, `compare`, `cite`, `avoid`" in summary_template
    assert "closed action vocabulary: `read`, `use`, `compare`, `cite`, `avoid`" in contract_results
    assert "completed_actions: [read, use, compare, cite, avoid]" in summary_template
    assert "uncertainty_markers:" in summary_template
    assert "weakest_anchors: [anchor-1]" in summary_template
    assert "disconfirming_observations: [observation-1]" in summary_template
    assert "uncertainty_markers.weakest_anchors" in state_schema
    assert "uncertainty_markers.disconfirming_observations" in state_schema
    assert "`GPD/phases/.../*-SUMMARY.md` or `paper/main.tex`" in state_schema
    assert "`GPD/phases/.../SUMMARY.md`" not in state_schema


def test_referee_schema_and_panel_surface_strict_stage_artifact_naming_and_round_suffix_rules() -> None:
    referee_schema = (TEMPLATES_DIR / "paper" / "referee-decision-schema.md").read_text(encoding="utf-8")
    review_ledger_schema = (TEMPLATES_DIR / "paper" / "review-ledger-schema.md").read_text(encoding="utf-8")
    panel = (REFERENCES_DIR / "publication" / "peer-review-panel.md").read_text(encoding="utf-8")

    assert "GPD/review/REFEREE-DECISION{round_suffix}.json" in referee_schema
    assert "GPD/REFEREE-REPORT{round_suffix}.md" in referee_schema
    assert "REVIEW-LEDGER{round_suffix}.json" in referee_schema
    assert "STAGE-(reader|literature|math|physics|interestingness)(-R<round>)?.json" in referee_schema
    assert "same optional `-R<round>` suffix" in referee_schema
    assert "`{round_suffix}` in path examples means empty for initial review and `-R<round>`" in referee_schema
    assert "GPD/review/REVIEW-LEDGER{round_suffix}.json" in review_ledger_schema
    assert "`manuscript_path` must be non-empty" in review_ledger_schema
    assert "REFEREE-DECISION{round_suffix}.json" in review_ledger_schema
    assert "GPD/review/CLAIMS{round_suffix}.json" in panel
    assert "GPD/review/STAGE-reader{round_suffix}.json" in panel
    assert "Strict-stage specialist artifacts must use canonical names `STAGE-reader`, `STAGE-literature`, `STAGE-math`, `STAGE-physics`, `STAGE-interestingness`." in panel
    assert "all five must share the same optional `-R<round>` suffix." in panel


def test_executor_completion_reference_requires_loading_contract_schema_before_summary_frontmatter() -> None:
    completion = (REFERENCES_DIR / "execution" / "executor-completion.md").read_text(encoding="utf-8")

    assert "Canonical ledger schema to load before writing SUMMARY frontmatter:" in completion
    assert "@{GPD_INSTALL_DIR}/templates/contract-results-schema.md" in completion
