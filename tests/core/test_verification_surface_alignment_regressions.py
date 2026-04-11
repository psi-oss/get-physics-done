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

    assert "Allowed body enum values:" in research_verification
    assert expected_enum in research_verification
    assert expected_enum not in verify_workflow
    assert research_verification.count(omit_instruction) == 1
    assert research_verification.count(paired_id_instruction) == 1
    assert "Update the session overlay only." in verify_workflow
    assert "The wrapper should present verifier-produced evidence exactly once per check." in verify_workflow


def test_verification_report_strict_pass_guidance_includes_reference_coverage_rules() -> None:
    verification_report = _read("src/gpd/specs/templates/verification-report.md")

    assert "status: passed` is strict" in verification_report
    assert "structured `suggested_contract_checks`" in verification_report
    assert "Legacy frontmatter aliases are forbidden in model-facing output" in verification_report
    assert "Proof-backed claims follow the proof-audit rules in the canonical schema" in verification_report


def test_verification_guidance_surfaces_the_same_canonical_suggestion_contract() -> None:
    research_verification = _read("src/gpd/specs/templates/research-verification.md")
    verify_workflow = _read("src/gpd/specs/workflows/verify-work.md")
    verifier_prompt = _read("src/gpd/agents/gpd-verifier.md")

    expected_suggestion = "suggested_contract_checks"

    assert expected_suggestion in research_verification
    assert expected_suggestion not in verify_workflow
    assert "canonical verifier report content remains owned by `gpd-verifier`" in verify_workflow
    for schema_key in (
        "request_template",
        "required_request_fields",
        "schema_required_request_fields",
        "schema_required_request_anyof_fields",
        "supported_binding_fields",
    ):
        assert schema_key in verify_workflow
        assert schema_key in verifier_prompt


def test_verify_work_current_check_overlay_stays_separate_from_verifier_scaffold() -> None:
    verify_workflow = _read("src/gpd/specs/workflows/verify-work.md")

    assert "Read the verifier-supplied current check from the verification file or report state." in verify_workflow
    assert "The wrapper should present verifier-produced evidence exactly once per check." in verify_workflow
    assert "Update the session overlay only. The canonical verifier verdict remains verifier-owned." in verify_workflow
    assert "one-shot delegation" in verify_workflow
    assert "summary: \"verification not started yet\"" not in verify_workflow


def test_verify_work_gap_repair_uses_explicit_stage_route_and_stays_fail_closed() -> None:
    verify_workflow = _read("src/gpd/specs/workflows/verify-work.md")

    assert 'gpd --raw init verify-work "${PHASE_ARG}" --stage gap_repair' in verify_workflow
    assert "Do not fall through to gap verification on the basis of preexisting `PLAN.md` files alone." in verify_workflow
    assert "skipping gap closure" not in verify_workflow


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
    assert "comparison_verdicts" in verifier_prompt
    assert "subject_role: decisive" in verifier_prompt


def test_research_verification_template_keeps_source_as_yaml_list() -> None:
    research_verification = _read("src/gpd/specs/templates/research-verification.md")

    assert 'source:\n  - "[SUMMARY.md file validated]"' in research_verification
    assert 'source:\n  - "03-01-SUMMARY.md"\n  - "03-02-SUMMARY.md"\n  - "03-03-SUMMARY.md"' in research_verification
    assert "keep this as a YAML list even when only one SUMMARY path is present" in research_verification
    assert "source: 03-01-SUMMARY.md, 03-02-SUMMARY.md, 03-03-SUMMARY.md" not in research_verification


def test_research_verification_template_keeps_contract_results_and_scalar_examples_copy_safe() -> None:
    research_verification = _read("src/gpd/specs/templates/research-verification.md")

    assert "evidence:\n        - verifier: gpd-verifier" in research_verification
    assert "Legacy frontmatter aliases are forbidden in model-facing output" in research_verification
    assert "Before generating the report, make the strict `contract_results` requirements visible" in research_verification
    assert "fill every required ledger bucket" in research_verification
    for legacy_alias in ("must_haves", "verification_inputs", "contract_evidence", "independently_confirmed"):
        assert legacy_alias not in research_verification


def test_research_verification_template_requires_transforming_raw_contract_check_suggestions() -> None:
    research_verification = _read("src/gpd/specs/templates/research-verification.md")

    assert "Raw `suggest_contract_checks(contract)` output is verifier-tool metadata" in research_verification
    assert "transform it before writing projected report schemas" in research_verification
    assert "copying returned `check_key` into `check` and dropping unsupported keys" in research_verification


def test_project_contract_schema_explains_project_root_dependent_grounding() -> None:
    project_contract_schema = _read("src/gpd/specs/templates/project-contract-schema.md")

    assert "Project-local paths in `locator` or `applies_to[]` evidence require project-root-aware validation" in project_contract_schema
    assert "validation cannot prove artifact grounding without that resolved project context" in project_contract_schema


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
