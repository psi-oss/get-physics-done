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

    expected_enum = "comparison_kind: [benchmark | prior_work | experiment | cross_method | baseline | other]"
    omit_instruction = "omit both `comparison_kind` and `comparison_reference_id` instead of leaving blank placeholders"

    assert expected_enum in research_verification
    assert expected_enum in verify_workflow
    assert "comparison_kind: [benchmark | prior_work | experiment | cross_method | baseline | other | \"\"]" not in research_verification
    assert "comparison_kind: [benchmark | prior_work | experiment | cross_method | baseline | other | \"\"]" not in verify_workflow
    assert omit_instruction in research_verification
    assert omit_instruction in verify_workflow


def test_verification_report_strict_pass_guidance_includes_reference_coverage_rules() -> None:
    verification_report = _read("src/gpd/specs/templates/verification-report.md")

    assert "status: passed` is strict" in verification_report
    assert "every claim, deliverable, and acceptance_test entry in `contract_results` is `passed`" in verification_report
    assert "every reference entry is `completed`" in verification_report
    assert "every `must_surface` reference has all `required_actions` recorded in `completed_actions`" in verification_report
    assert "linked_ids: [deliverable-id, acceptance-test-id, reference-id]" in verification_report
    assert "evidence:\n        - verifier: gpd-verifier" in verification_report
    assert "linked_ids: [claim-id, acceptance-test-id]" in verification_report
    assert "linked_ids: [claim-id, deliverable-id, reference-id]" in verification_report
    assert "suggested_contract_checks" in verification_report
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
    assert "linked_ids: [deliverable-id, acceptance-test-id, reference-id]" in verification_report
    assert "evidence:\n        - verifier: gpd-verifier" in verification_report
    assert "linked_ids: [claim-id, acceptance-test-id]" in verification_report
    assert "linked_ids: [claim-id, deliverable-id, reference-id]" in verification_report
    assert "linked_ids: [deliverable-id, acceptance-test-id, reference-id]" in verifier_prompt
    assert "evidence:\n        - verifier: gpd-verifier" in verifier_prompt
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
