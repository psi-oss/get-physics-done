"""Regression tests for verification scaffold and workflow surface alignment."""

from __future__ import annotations

from pathlib import Path

TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "src" / "gpd" / "specs" / "templates"
WORKFLOWS_DIR = Path(__file__).resolve().parents[2] / "src" / "gpd" / "specs" / "workflows"


def _read(relative_path: str) -> str:
    return (Path(__file__).resolve().parents[2] / relative_path).read_text(encoding="utf-8")


def test_verification_scaffolds_surface_closed_comparison_kind_enum_without_blank_placeholder() -> None:
    research_verification = _read("src/gpd/specs/templates/research-verification.md")
    verify_workflow = _read("src/gpd/specs/workflows/verify-work.md")

    expected_enum = "`comparison_kind`: benchmark|prior_work|experiment|cross_method|baseline|other"
    omit_instruction = "omit both `comparison_kind` and `comparison_reference_id` instead of leaving blank placeholders"
    paired_id_instruction = "omit both keys instead of leaving one blank"
    subject_id_instruction = (
        "omit unused `subject_id`, `claim_id`, `deliverable_id`, `acceptance_test_id`, "
        "and `forbidden_proxy_id` fields instead of leaving blank placeholders."
    )
    verify_subject_id_instruction = "follow the omission rule from current check instead of leaving blank placeholder strings."
    normalized_verify_workflow = " ".join(verify_workflow.lower().split())

    assert "Allowed body enum values:" in research_verification
    assert "Allowed body enum values:" in verify_workflow
    assert expected_enum in research_verification
    assert expected_enum in verify_workflow
    assert "comparison_kind: benchmark" in research_verification
    assert "comparison_kind: benchmark" in verify_workflow
    assert "comparison_kind: [benchmark | prior_work | experiment | cross_method | baseline | other]" not in research_verification
    assert "comparison_kind: [benchmark | prior_work | experiment | cross_method | baseline | other]" not in verify_workflow
    assert "comparison_kind: [benchmark | prior_work | experiment | cross_method | baseline | other | \"\"]" not in research_verification
    assert "comparison_kind: [benchmark | prior_work | experiment | cross_method | baseline | other | \"\"]" not in verify_workflow
    assert research_verification.count(omit_instruction) == 1
    assert verify_workflow.count(omit_instruction) == 1
    assert research_verification.count(paired_id_instruction) == 1
    assert verify_workflow.count(paired_id_instruction) == 1
    assert research_verification.count(subject_id_instruction) == 1
    assert normalized_verify_workflow.count(subject_id_instruction) == 1
    assert normalized_verify_workflow.count(verify_subject_id_instruction) == 1
    assert "Same rule as above: keep only the ID keys that actually bind this check." not in research_verification


def test_verification_report_strict_pass_guidance_includes_reference_coverage_rules() -> None:
    verification_report = _read("src/gpd/specs/templates/verification-report.md")

    assert "status: passed` is strict" in verification_report
    assert "every required decisive comparison is decisive" in verification_report
    assert "Proof-backed claims follow the proof-audit rules in the canonical schema" in verification_report
    assert "structured `suggested_contract_checks`" in verification_report
    assert "Legacy frontmatter aliases are forbidden in model-facing output" in verification_report
    assert "status: passed" in verification_report


def test_verification_guidance_surfaces_the_same_canonical_suggestion_contract() -> None:
    research_verification = _read("src/gpd/specs/templates/research-verification.md")
    verify_workflow = _read("src/gpd/specs/workflows/verify-work.md")

    expected_suggestion = "suggested_contract_checks"
    decisive_gap_text = "required_actions including `compare` is still incomplete"

    assert expected_suggestion in research_verification
    assert expected_suggestion in verify_workflow
    assert decisive_gap_text in research_verification
    assert decisive_gap_text in verify_workflow
    assert "same canonical schema surface" in research_verification
    assert "frontmatter contract compatible with `@{GPD_INSTALL_DIR}/templates/verification-report.md`" in verify_workflow


def test_verify_work_scaffold_uses_yaml_strings_for_scalar_examples_without_blank_id_placeholders() -> None:
    verify_workflow = _read("src/gpd/specs/workflows/verify-work.md")

    assert 'summary: "verification not started yet"' in verify_workflow
    assert 'notes: "verification not started yet"' in verify_workflow
    assert 'recommended_action: "close the decisive benchmark once the evidence is written"' in verify_workflow
    assert 'evidence_path: "artifact path or expected evidence path"' in verify_workflow
    assert 'source: ["list of phase-summary files"]' in verify_workflow
    assert 'started: "ISO timestamp"' in verify_workflow
    assert 'updated: "ISO timestamp"' in verify_workflow
    assert "Omit unused `subject_id`, `claim_id`, `deliverable_id`, `acceptance_test_id`," in verify_workflow
    assert 'subject_id: "claim-main"' in verify_workflow
    assert 'expected: "verifiable physics outcome"' in verify_workflow
    assert 'computation: "specific numerical test performed"' in verify_workflow
    assert 'result: "pending"' in verify_workflow
    assert 'summary: [verification not started yet]' not in verify_workflow
    assert 'notes: [verification not started yet]' not in verify_workflow
    assert 'check: [missing decisive check]' not in verify_workflow
    assert 'reason: [why the missing check matters]' not in verify_workflow
    assert 'evidence_path: [artifact path or expected evidence path]' not in verify_workflow
    assert 'subject_id: "contract id or \\"\\""' not in verify_workflow
    assert 'subject_id: [contract id or ""]' not in verify_workflow
    assert 'expected: [verifiable physics outcome]' not in verify_workflow
    assert 'computation: [specific numerical test performed]' not in verify_workflow
    assert "independently_confirmed" not in verify_workflow


def test_model_visible_worked_examples_keep_summary_and_verdict_shapes_copy_safe() -> None:
    executor_example = _read("src/gpd/specs/references/execution/executor-worked-example.md")
    verification_report = _read("src/gpd/specs/templates/verification-report.md")
    verifier_prompt = _read("src/gpd/agents/gpd-verifier.md")

    assert "depth: full" in executor_example
    assert "completed: 2026-03-15" in executor_example
    assert "evidence:" in executor_example
    assert "verifier: gpd-verifier" in executor_example
    assert 'recommended_action: "Keep the benchmark coefficient comparison explicit in the verification report."' in executor_example
    assert 'notes: "Exact pole agreement closes the decisive benchmark requirement for this claim."' in executor_example
    assert "comparison_verdicts" in verification_report
    assert "subject_role: decisive" in verification_report
    assert "comparison_verdicts" in verifier_prompt
    assert "subject_role: decisive" in verifier_prompt
    assert 'recommended_action: "[what to do next]"' in verifier_prompt
    assert 'notes: "[optional context]"' in verifier_prompt


def test_research_verification_template_keeps_source_as_yaml_list() -> None:
    research_verification = _read("src/gpd/specs/templates/research-verification.md")

    assert 'source:\n  - "[SUMMARY.md file validated]"' in research_verification
    assert 'source:\n  - "03-01-SUMMARY.md"\n  - "03-02-SUMMARY.md"\n  - "03-03-SUMMARY.md"' in research_verification
    assert "keep this as a YAML list even when only one SUMMARY path is present" in research_verification
    assert "source: 03-01-SUMMARY.md, 03-02-SUMMARY.md, 03-03-SUMMARY.md" not in research_verification


def test_research_verification_template_keeps_contract_results_and_scalar_examples_copy_safe() -> None:
    research_verification = _read("src/gpd/specs/templates/research-verification.md")

    assert "linked_ids: [deliverable-main, acceptance-test-main, reference-main]" in research_verification
    assert "linked_ids: [claim-main, acceptance-test-main]" in research_verification
    assert "linked_ids: [claim-main, deliverable-main, reference-main]" in research_verification
    assert "evidence:\n        - verifier: gpd-verifier" in research_verification
    assert 'summary: "[what the adversarial proof review concluded]"' in research_verification
    assert "Legacy frontmatter aliases are forbidden in model-facing output" in research_verification
    for legacy_alias in ("must_haves", "verification_inputs", "contract_evidence", "independently_confirmed"):
        assert legacy_alias not in research_verification
    assert 'evidence_path: "GPD/phases/XX-name/{phase}-VERIFICATION.md"' in research_verification
    assert 'evidence_path: "[artifact path or expected evidence path]"' in research_verification
    assert 'started: "ISO timestamp"' in research_verification
    assert 'updated: "ISO timestamp"' in research_verification
    assert "Omit unused `subject_id`, `claim_id`, `deliverable_id`, `acceptance_test_id`," in research_verification
    assert 'subject_id: "claim-main"' in research_verification
    assert ".gpd/phases/" not in research_verification
    assert 'evidence_path: [artifact path or expected evidence path]' not in research_verification
    assert 'started: [ISO timestamp]' not in research_verification
    assert 'updated: [ISO timestamp]' not in research_verification
    assert 'subject_id: "contract id or \\"\\""' not in research_verification
    assert 'subject_id: [contract id or ""]' not in research_verification


def test_summary_template_keeps_reference_action_ledger_and_legacy_alias_note() -> None:
    summary_template = _read("src/gpd/specs/templates/summary.md")

    assert "single detailed rule source" in summary_template
    assert "plan_contract_ref" in summary_template
    assert "contract_results" in summary_template
    assert "comparison_verdicts" in summary_template
    assert "suggested_contract_checks" in summary_template
    assert "Legacy frontmatter aliases are forbidden in model-facing output" in summary_template
    for legacy_alias in ("must_haves", "verification_inputs", "contract_evidence", "independently_confirmed"):
        assert legacy_alias not in summary_template
