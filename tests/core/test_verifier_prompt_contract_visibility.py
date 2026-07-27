from __future__ import annotations

import re
from pathlib import Path
from typing import Literal, get_args, get_origin

from gpd.adapters.install_utils import expand_at_includes
from gpd.contracts import (
    CONTRACT_REFERENCE_ACTION_VALUES,
    ComparisonVerdict,
    ContractProofAudit,
    SuggestedContractCheck,
)
from gpd.core.frontmatter import extract_frontmatter, validate_frontmatter
from gpd.core.strict_yaml import load_strict_yaml
from tests.assertion_taxonomy_support import MatchMode, assert_prompt_contracts, semantic_concept
from tests.workflow_authority_support import workflow_authority_text

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO_ROOT / "src/gpd/agents"
TEMPLATES_DIR = REPO_ROOT / "src/gpd/specs/templates"
WORKFLOWS_DIR = REPO_ROOT / "src/gpd/specs/workflows"
VERIFICATION_STATUS_AUTHORITY = REPO_ROOT / "src/gpd/specs/references/verification/verification-status-authority.md"


def _read_verifier_prompt() -> str:
    return (AGENTS_DIR / "gpd-verifier.md").read_text(encoding="utf-8")


def _read_verification_template() -> str:
    return (TEMPLATES_DIR / "verification-report.md").read_text(encoding="utf-8")


def _read_research_verification_template() -> str:
    return (TEMPLATES_DIR / "research-verification.md").read_text(encoding="utf-8")


def _read_verify_work_template() -> str:
    return workflow_authority_text(WORKFLOWS_DIR, "verify-work")


def _read_expanded_verifier_prompt() -> str:
    return expand_at_includes(_read_verifier_prompt(), REPO_ROOT / "src/gpd", "/runtime/")


def _read_markdown_example(path: Path) -> str:
    content = path.read_text(encoding="utf-8")
    match = re.search(r"```markdown\n(.*?)\n```", content, re.S)
    assert match is not None
    return match.group(1)


def _read_example_frontmatter(path: Path) -> str:
    return _read_markdown_example(path)


def _markdown_section(text: str, heading: str) -> str:
    match = re.search(rf"(?m)^{re.escape(heading)}[ \t]*$", text)
    assert match is not None, f"missing markdown section: {heading}"
    level = len(heading) - len(heading.lstrip("#"))
    next_match = re.search(rf"(?m)^#{{{level}}}\s+", text[match.end() :])
    if next_match is None:
        return text[match.end() :]
    return text[match.end() : match.end() + next_match.start()]


def _between_markers(text: str, start_marker: str, end_marker: str) -> str:
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    return text[start:end]


def _paragraph_containing(text: str, marker: str) -> str:
    marker_index = text.index(marker)
    start = text.rfind("\n\n", 0, marker_index)
    end = text.find("\n\n", marker_index)
    if start == -1:
        start = 0
    if end == -1:
        end = len(text)
    return text[start:end]


def _tag_section(text: str, tag_name: str) -> str:
    start_marker = f'<step name="{tag_name}">'
    start = text.index(start_marker)
    end = text.index("</step>", start)
    return text[start:end]


def _assert_contains_all(text: str, fragments: tuple[str, ...]) -> None:
    missing = [fragment for fragment in fragments if fragment not in text]
    assert missing == []


def _assert_not_contains_any(text: str, fragments: tuple[str, ...]) -> None:
    present = [fragment for fragment in fragments if fragment in text]
    assert present == []


def _assert_semantic_contract(
    text: str,
    label: str,
    *,
    required: tuple[str, ...] = (),
    forbidden: tuple[str, ...] = (),
) -> None:
    assert_prompt_contracts(
        text,
        *semantic_concept(
            label,
            required=required or None,
            forbidden=forbidden or None,
            match=MatchMode.CASEFOLD_NORMALIZED,
            context=label,
        ),
    )


def _literal_values(annotation: object) -> tuple[str, ...]:
    origin = get_origin(annotation)
    if origin is Literal:
        return tuple(arg for arg in get_args(annotation) if isinstance(arg, str))
    values: list[str] = []
    for arg in get_args(annotation):
        values.extend(_literal_values(arg))
    return tuple(values)


def _parse_yaml_fence_containing(text: str, marker: str) -> object:
    for match in re.finditer(r"```yaml\n(.*?)\n```", text, re.S):
        if marker in match.group(1):
            parsed = load_strict_yaml(match.group(1))
            assert parsed is not None
            return parsed
    raise AssertionError(f"missing yaml fence containing: {marker}")


def _parse_yaml_fragment(fragment: str) -> object:
    without_comments = re.sub(r"<!--.*?-->", "", fragment, flags=re.S).strip()
    parsed = load_strict_yaml(without_comments)
    assert parsed is not None
    return parsed


def _research_verification_example() -> tuple[dict, str]:
    return extract_frontmatter(_read_markdown_example(TEMPLATES_DIR / "research-verification.md"))


def test_verifier_prompt_points_to_canonical_verification_schema_sources() -> None:
    verifier = _read_verifier_prompt()
    expanded_verifier = _read_expanded_verifier_prompt()
    expanded_lines = expanded_verifier.splitlines()
    agent_frontmatter, _ = extract_frontmatter(verifier)
    canonical_authoring = _between_markers(verifier, "Canonical verification report authoring", "Schema guard:")
    create_report = _markdown_section(verifier, "## Create VERIFICATION.md")

    assert "templates/verification-report.md" in verifier
    assert "templates/contract-results-schema.md" in verifier
    assert "references/shared/canonical-schema-discipline.md" in verifier
    _assert_contains_all(
        canonical_authoring,
        (
            "report helper",
            "primary frontmatter writer",
            "writer_command",
            "skeleton_command",
            "body-only evidence",
            "body-only Markdown",
        ),
    )
    _assert_contains_all(
        canonical_authoring,
        (
            "`gpd verification-report skeleton ... --write --body-file ... --validate contract`",
            "`gpd verification-report finalize ... --patch ... --body-file ... --validate contract`",
        ),
    )
    _assert_contains_all(
        verifier,
        (
            "gpd --raw verify contract-check",
            "gpd --raw verify suggest-checks",
            "gpd --raw verify bundle-checklist",
        ),
    )
    assert "@{GPD_INSTALL_DIR}/templates/verification-report.md" not in verifier
    assert "@{GPD_INSTALL_DIR}/templates/contract-results-schema.md" not in verifier
    assert "# Verification Report Template" not in expanded_verifier
    assert "# Contract Results Schema" not in expanded_verifier
    assert "## Canonical LLM Error References" in verifier
    _assert_contains_all(
        create_report,
        (
            "ASSERT_CONVENTION",
            "YAML frontmatter",
            "VERIFICATION.md",
            "gpd pre-commit-check",
        ),
    )
    assert "Prefer copy-pasteable GPD commands" not in verifier
    assert "## Data Boundary" not in verifier
    _assert_not_contains_any(
        verifier,
        ("must_haves", "verification_inputs", "contract_evidence", "independently_confirmed"),
    )
    assert verifier.count("templates/verification-report.md") == 1
    assert verifier.count("templates/contract-results-schema.md") == 1
    assert verifier.count("references/shared/canonical-schema-discipline.md") == 1
    assert "verifier-profile-checks.md" not in expanded_lines


def test_verifier_prompt_surfaces_validator_enforced_contract_ledger_rules() -> None:
    verifier = _read_verifier_prompt()
    contract_results_schema = (TEMPLATES_DIR / "contract-results-schema.md").read_text(encoding="utf-8")
    schema_guard = _paragraph_containing(verifier, "Schema guard:")
    gap_output = _markdown_section(verifier, "## Step 10: Structure Gap Output (If Gaps Found)")
    plan_ref_example = _parse_yaml_fence_containing(contract_results_schema, "plan_contract_ref:")
    contract_results_example = _parse_yaml_fence_containing(contract_results_schema, "contract_results:")
    gap_example = _parse_yaml_fence_containing(contract_results_schema, "status: gaps_found")
    verdict_example = _parse_yaml_fence_containing(contract_results_schema, "metric: relative_error")

    for contract_anchor in (
        "`plan_contract_ref`",
        "`contract_results`",
        "`contract_results.uncertainty_markers`",
        "`comparison_verdicts`",
        "`suggested_contract_checks`",
        "proof-audit linkage",
    ):
        assert contract_anchor in verifier
    _assert_contains_all(
        schema_guard,
        (
            "helper/validator-owned",
            "`gaps_found`",
            "`subject_role: decisive`",
            "`gpd_return`",
            "computational-oracle/runtime details",
            "body or return envelope",
            "project-only IDs",
            "body/unbound suggestions",
        ),
    )
    assert (
        "If `contract_results` or `comparison_verdicts` are present, `plan_contract_ref` is required." not in verifier
    )
    assert "Schema guard:" in verifier
    assert plan_ref_example == {"plan_contract_ref": "GPD/phases/XX-name/XX-YY-PLAN.md#/contract"}
    assert isinstance(contract_results_example, dict)
    contract_results = contract_results_example["contract_results"]
    assert set(contract_results) == {
        "claims",
        "deliverables",
        "acceptance_tests",
        "references",
        "forbidden_proxies",
        "uncertainty_markers",
    }
    assert contract_results["claims"]["claim-main"]["status"] == "passed"
    assert contract_results["claims"]["claim-main"]["evidence"][0]["verifier"] == "gpd-verifier"
    assert contract_results["claims"]["claim-main"]["evidence"][0]["confidence"] == "high"
    assert contract_results["deliverables"]["deliv-main"]["path"] == "path/to/artifact"
    assert contract_results["references"]["ref-main"]["completed_actions"] == ["read", "compare", "cite"]
    assert contract_results["forbidden_proxies"]["fp-main"]["status"] == "rejected"
    assert contract_results["uncertainty_markers"]["weakest_anchors"] == ["anchor-1"]
    assert isinstance(gap_example, dict)
    assert gap_example["status"] == "gaps_found"
    assert gap_example["contract_results"]["claims"]["claim-main"]["status"] == "blocked"
    assert gap_example["contract_results"]["references"]["ref-main"]["missing_actions"] == ["read", "compare"]
    assert gap_example["comparison_verdicts"][0]["subject_role"] == "decisive"
    assert gap_example["comparison_verdicts"][0]["verdict"] == "inconclusive"
    assert isinstance(verdict_example, dict)
    verdict = verdict_example["comparison_verdicts"][0]
    assert verdict["subject_kind"] == "claim"
    assert verdict["subject_role"] == "decisive"
    assert verdict["comparison_kind"] == "benchmark"
    assert verdict["verdict"] == "pass"
    _assert_semantic_contract(
        contract_results_schema,
        "contract results are keyed to plan contract",
        required=("contract_results", "plan_contract_ref", "project-only IDs", "body"),
    )
    assert "never `kind`, `path`, `source`, `summary`, `actual_output`, or `command`" in contract_results_schema
    _assert_semantic_contract(
        contract_results_schema,
        "contract results schema preserves complete contract coverage",
        required=(
            "every declared claim",
            "deliverable",
            "acceptance test",
            "reference",
            "forbidden proxy",
            "matching section",
            "uncertainty_markers",
            "contract-backed outputs",
        ),
    )
    comparison_kind_values = _literal_values(ComparisonVerdict.model_fields["comparison_kind"].annotation)
    for comparison_kind in comparison_kind_values:
        assert comparison_kind in contract_results_schema
    _assert_semantic_contract(
        contract_results_schema,
        "decisive comparison rules stay schema visible",
        required=(
            "subject_role: decisive",
            "required decisive comparison",
            "pass/fail consistency",
            "comparison_kind: other",
            "does not satisfy",
        ),
    )
    assert SuggestedContractCheck.model_config["extra"] == "forbid"
    assert set(SuggestedContractCheck.model_fields) == {
        "check",
        "reason",
        "suggested_subject_kind",
        "suggested_subject_id",
        "evidence_path",
    }
    for field_name in SuggestedContractCheck.model_fields:
        assert f"`{field_name}`" in contract_results_schema
    assert (
        "Copy the `check_key` returned by `gpd --raw verify suggest-checks --contract <file|-> --project-dir DIR` into the frontmatter `check` field"
        in contract_results_schema
    )
    _assert_semantic_contract(
        contract_results_schema,
        "suggested contract check target binding is paired",
        required=(
            "suggested_contract_checks",
            "known contract target",
            "suggested_subject_kind",
            "suggested_subject_id",
            "together",
        ),
    )
    _assert_contains_all(
        verifier,
        (
            "gpd --raw verify suggest-checks --contract",
            "`request_template`",
            "`required_request_fields`",
            "`schema_required_request_fields`",
            "`schema_required_request_anyof_fields`",
            "`supported_binding_fields`",
            "the payload's `binding` object",
            "`project_dir`",
            # Regression lock: dropping --project-dir from the suggest-checks
            # invocation silently nulls contract_warnings (no anchor grounding).
            "gpd --raw verify suggest-checks --contract <file|-> --project-dir DIR",
        ),
    )
    assert "Execute each check with `gpd --raw verify contract-check --payload" in verifier
    _assert_contains_all(
        gap_output,
        (
            "contract target",
            "expectation",
            "failed/partial check",
            "category",
            "computation evidence",
            "affected artifacts",
            "missing fix",
            "severity",
        ),
    )
    assert "`suggested_contract_check`" not in verifier


def test_verifier_prompt_keeps_passed_verification_frontmatter_helper_owned() -> None:
    verifier = _read_verifier_prompt()
    schema_guard = _paragraph_containing(verifier, "Schema guard:")
    create_report = _markdown_section(verifier, "## Create VERIFICATION.md")

    _assert_contains_all(
        schema_guard,
        (
            "Passed verification frontmatter is helper/validator-owned",
            "do not hand-author `status: passed` YAML",
            "Keep `gpd_return`, computational-oracle/runtime details, command transcripts, hashes, and prose-only evidence out of frontmatter",
        ),
    )
    _assert_contains_all(
        create_report,
        (
            "verification-report writer helper",
            "not by hand-authoring YAML",
            "let `gpd verification-report skeleton --write --body-file ... --validate contract` serialize the frontmatter",
        ),
    )
    _assert_not_contains_any(
        verifier,
        (
            "Structure gaps in YAML frontmatter",
            "Gaps structured in YAML frontmatter with severity, category, and computation_evidence",
            "hand-author passed verification YAML",
            "hand-authored passed verification YAML",
        ),
    )


def test_verifier_prompt_keeps_reference_actions_within_the_canonical_enum() -> None:
    verifier = _read_verifier_prompt()
    reference_action_line = _paragraph_containing(verifier, "Verify the required action")
    visible_actions = set(re.findall(r"`([^`]+)`", reference_action_line))

    assert {"read", "compare", "cite"} <= visible_actions
    assert visible_actions <= set(CONTRACT_REFERENCE_ACTION_VALUES)
    _assert_semantic_contract(
        reference_action_line,
        "reference actions stay in canonical enum",
        required=("required action", "actually completed"),
        forbidden=("reproduce",),
    )


def test_verifier_prompt_loads_conventions_from_state_json_with_degraded_state_md_fallback() -> None:
    verifier = _read_verifier_prompt()
    convention_loading = _markdown_section(verifier, "## Convention Loading Protocol")

    _assert_contains_all(
        convention_loading,
        (
            "`state.json`",
            "`convention_lock`",
            "machine-readable source of truth",
            "`STATE.md`",
            "degraded fallback",
            "WARNING: No machine-readable convention lock found",
        ),
    )
    assert "Do NOT parse STATE.md for conventions" not in verifier


def test_verifier_prompt_reloads_the_canonical_schema_files_once() -> None:
    verifier = _read_verifier_prompt()
    canonical_authoring = _between_markers(verifier, "Canonical verification report authoring", "Schema guard:")

    assert verifier.count("templates/verification-report.md") == 1
    assert verifier.count("templates/contract-results-schema.md") == 1
    assert verifier.count("references/shared/canonical-schema-discipline.md") == 1
    _assert_contains_all(
        canonical_authoring,
        (
            "report helper",
            "frontmatter writer",
            "authority references",
            "helper or validator errors",
            "do not inline",
        ),
    )
    assert "from Step 2" not in verifier


def test_verifier_prompt_surfaces_schema_sources_before_the_verification_writer_section() -> None:
    verifier = _read_verifier_prompt()
    create_verification_section = verifier.index("## Create VERIFICATION.md")

    assert verifier.index("templates/verification-report.md") < create_verification_section
    assert verifier.index("templates/contract-results-schema.md") < create_verification_section
    assert verifier.index("references/shared/canonical-schema-discipline.md") < create_verification_section


def test_verifier_prompt_frontmatter_example_includes_contract_ledgers() -> None:
    verifier = _read_verifier_prompt()
    verification_template = _read_verification_template()
    report_surface = _markdown_section(verification_template, "## Canonical Report Surface")
    validation_stop = _markdown_section(verifier, "### Validation Stop Rule")
    body_evidence = _markdown_section(verifier, "### Body-Only Evidence")

    assert "plan_contract_ref" in verifier
    assert "contract_results" in verifier
    assert "comparison_verdicts" in verifier
    assert "suggested_contract_checks" in verifier
    assert "\nindependently_confirmed:" not in verifier
    assert (
        "<!-- ASSERT_CONVENTION: natural_units=natural, metric_signature=mostly-minus, fourier_convention=physics -->"
        in verifier
    )
    assert "filler placeholders" not in verifier
    _assert_contains_all(
        body_evidence,
        (
            "body-only Markdown",
            "`gpd verification-report skeleton --write --body-file ... --validate contract`",
            "frontmatter",
            "decisive evidence",
            "computational verification details",
        ),
    )
    _assert_contains_all(
        validation_stop,
        (
            "gpd frontmatter validate ${phase_dir}/${phase_number}-VERIFICATION.md --schema verification",
            "gpd validate verification-contract ${phase_dir}/${phase_number}-VERIFICATION.md",
            "one bounded repair pass",
            "stop blocked with latest errors",
            "frontmatter",
            "aliases",
            "empty evidence",
        ),
    )
    assert "### Frontmatter Schema (YAML)" not in verifier
    _assert_contains_all(
        report_surface,
        (
            "plan_contract_ref",
            "contract_results",
            "comparison_verdicts",
            "suggested_contract_checks",
            "status",
            "gpd_return",
            "computational_oracle",
            "runtime scratch",
            "oracle in body",
            "return after",
        ),
    )


def test_shipped_verification_examples_roundtrip_through_the_verification_validator() -> None:
    example = _read_example_frontmatter(TEMPLATES_DIR / "research-verification.md")
    frontmatter, body = extract_frontmatter(example)
    result = validate_frontmatter(example, "verification")

    assert result.valid is True
    assert result.errors == []
    assert "gpd_return" not in frontmatter
    assert "computational_oracle" not in frontmatter
    assert "runtime_scratch" not in frontmatter
    assert "gpd_return:" not in body


def test_verifier_prompt_uses_canonical_include_for_worked_examples() -> None:
    verifier = _read_verifier_prompt()
    status_authority = VERIFICATION_STATUS_AUTHORITY.read_text(encoding="utf-8")
    artifact_level_section = _markdown_section(verifier, "### Level 2: Substantive Content")

    _assert_contains_all(
        artifact_level_section,
        (
            "Stub detection patterns extracted",
            "references/verification/examples/verifier-worked-examples.md",
            "Physics",
            "Derivation",
            "Numerical",
            "BLOCKER",
            "WARNING",
            "INFO",
        ),
    )
    assert "## Physics Stub Detection Patterns" not in verifier
    assert "verification-status-authority.md" in verifier
    _assert_semantic_contract(
        status_authority,
        "passed status requires substantive decisive artifact checks",
        required=("supporting artifacts", "substantive", "decisive checks"),
    )


def test_verifier_prompt_surfaces_missing_parameter_proof_audit_and_stale_review_gate() -> None:
    verifier = _read_verifier_prompt()
    contract_results_schema = (TEMPLATES_DIR / "contract-results-schema.md").read_text(encoding="utf-8")
    verification_template = _read_verification_template()
    status_authority = VERIFICATION_STATUS_AUTHORITY.read_text(encoding="utf-8")
    research_frontmatter, _ = _research_verification_example()
    report_surface = _markdown_section(verification_template, "## Canonical Report Surface")
    claim = research_frontmatter["contract_results"]["claims"]["claim-main"]
    proof_audit = claim["proof_audit"]

    assert "## Physics Stub Detection Patterns" not in verifier
    assert "references/verification/examples/verifier-worked-examples.md" in verifier
    _assert_contains_all(
        _paragraph_containing(verifier, "Schema guard:"),
        ("proof-audit linkage", "status vocabularies", "ID linkage", "stale-audit handling"),
    )
    _assert_semantic_contract(
        verifier,
        "staged peer-review theorem prose stays out of verifier prompt",
        forbidden=(
            "Every named theorem parameter or hypothesis is used or explicitly discharged",
            "no theorem symbol may disappear",
        ),
    )
    _assert_semantic_contract(
        contract_results_schema,
        "verification proof audit follows project contract semantics",
        required=(
            "ProjectContract",
            "ContractClaim",
            "proof_audit.quantifier_status",
            "unquantified proof-bearing claims",
            "proof_deliverables",
            "proof-redteam artifact",
            "proof-specific acceptance test",
            "do not substitute",
            "Paper `ClaimRecord`",
        ),
    )
    for field_name in (
        "proof_artifact_path",
        "proof_artifact_sha256",
        "audit_artifact_path",
        "audit_artifact_sha256",
        "claim_statement_sha256",
    ):
        assert field_name in ContractProofAudit.model_fields
        assert f"`{field_name}`" in contract_results_schema or f"`proof_audit.{field_name}`" in contract_results_schema
    _assert_contains_all(
        report_surface,
        (
            "schema-owned ledgers",
            "status",
            "passed",
            "every required decisive comparison",
            "suggested_contract_checks",
            "Proof-backed claims",
            "proof-audit rules",
            "stale-audit handling",
        ),
    )
    assert "completed_actions: []" not in verification_template
    assert "missing_actions: [read]" not in verification_template
    assert research_frontmatter["phase"] == "01-benchmark"
    assert research_frontmatter["status"] == "gaps_found"
    assert research_frontmatter["plan_contract_ref"] == "GPD/phases/01-benchmark/01-plan-PLAN.md#/contract"
    assert claim["status"] == "not_attempted"
    assert proof_audit["reviewer"] == "gpd-check-proof"
    assert proof_audit["summary"] == "[what the adversarial proof review concluded]"
    assert proof_audit["proof_artifact_path"] == "derivations/main-proof.tex"
    assert proof_audit["audit_artifact_path"] == "GPD/phases/01-benchmark/01-PROOF-REDTEAM.md"
    assert proof_audit["covered_parameter_symbols"] == []
    assert proof_audit["missing_parameter_symbols"] == []
    assert proof_audit["quantifier_status"] == "unclear"
    assert proof_audit["scope_status"] == "unclear"
    assert proof_audit["counterexample_status"] == "not_attempted"
    assert proof_audit["stale"] is False
    assert research_frontmatter["comparison_verdicts"][0]["recommended_action"] == (
        "collect one more benchmark point before marking the claim as passed"
    )
    assert "verification-status-authority.md" in verifier
    _assert_semantic_contract(
        status_authority,
        "verification status requires passed proof-redteam artifacts",
        required=("proof-bearing work", "passed", "proof-redteam artifacts"),
    )
    assert "all artifacts pass levels 1-3" not in verifier


def test_research_verification_template_uses_concrete_example_values() -> None:
    research_verification = _read_research_verification_template()
    frontmatter, body = _research_verification_example()
    current_check = _parse_yaml_fragment(_markdown_section(body, "## Current Check"))
    benchmark_check = _parse_yaml_fragment(_markdown_section(body, "### 1. Benchmark Comparison"))
    summary = _parse_yaml_fragment(_markdown_section(body, "## Summary"))
    comparison_section = _markdown_section(body, "## Comparison Verdicts").split("Allowed `subject_kind` values:", 1)[0]
    body_comparison_verdicts = _parse_yaml_fragment(comparison_section)
    gaps = _parse_yaml_fragment(_markdown_section(body, "## Gaps"))

    assert "phase: 01-benchmark" in research_verification
    assert frontmatter["phase"] == "01-benchmark"
    assert frontmatter["source"] == ["[SUMMARY.md file validated]"]
    assert frontmatter["session_status"] == "validating"
    assert current_check["name"] == "benchmark comparison"
    assert current_check["check_subject_kind"] == "claim"
    assert current_check["subject_id"] == "claim-main"
    assert current_check["claim_id"] == "claim-main"
    assert current_check["reference_ids"] == ["reference-main"]
    assert current_check["comparison_kind"] == "benchmark"
    assert current_check["comparison_reference_id"] == "reference-main"
    assert "within 1%" in current_check["expected"]
    assert benchmark_check["expected"] == "The benchmark comparison should land within the 1% tolerance."
    assert benchmark_check["result"] == "pending"
    assert summary == {
        "total": 4,
        "passed": 1,
        "issues": 1,
        "pending": 1,
        "skipped": 1,
        "comparison_verdicts_recorded": 0,
        "forbidden_proxies_rejected": 0,
    }
    assert isinstance(body_comparison_verdicts, list)
    assert body_comparison_verdicts[0]["subject_role"] == "decisive"
    assert body_comparison_verdicts[0]["comparison_kind"] == "benchmark"
    assert body_comparison_verdicts[0]["verdict"] == "inconclusive"
    assert isinstance(gaps, list)
    assert gaps[0]["gap_subject_kind"] == "claim"
    assert gaps[0]["subject_id"] == "claim-main"
    assert gaps[0]["reference_ids"] == ["reference-main"]
    assert gaps[0]["comparison_kind"] == "benchmark"
    assert gaps[0]["comparison_reference_id"] == "reference-main"
    assert gaps[0]["status"] == "failed"
    assert gaps[0]["severity"] == "major"


def test_verify_work_template_keeps_session_overlay_after_verifier_output() -> None:
    verify_work = _read_verify_work_template()
    verifier_handoff = _markdown_section(verify_work, "## Delegate Verification")
    fallback = verifier_handoff
    completion = _tag_section(verify_work, "complete_session")

    _assert_contains_all(
        verifier_handoff,
        (
            "`project_contract`",
            "`project_contract_gate.authoritative`",
            "protocol_bundle_verifier_extensions",
            "Keep decisive comparison gaps legible",
            "headings, marker strings",
            "canonical verification frontmatter",
            "`gpd_return.status`",
            "Spawn `gpd-verifier` once",
            "fresh verifier continuation",
        ),
    )
    _assert_contains_all(
        fallback,
        (
            "verification_report_skeleton_bridge",
            "skeleton bridge only for conservative gap reports",
            "gpd verification-report finalize",
            "Verification-report YAML",
            "transcripts",
            "hashes",
            "oracle details",
            "prose-only evidence",
            "runtime return envelopes",
            "in YAML",
            "do not wrapper-repair the canonical report",
        ),
    )
    _assert_contains_all(
        completion,
        (
            "record-verification",
            "uses the canonical status reader",
            "`passed` -> `Verified`",
            "non-passed -> `Blocked`",
            "Do not relax verifier fail-closed results",
        ),
    )
    _assert_semantic_contract(
        verify_work,
        "verify-work keeps background synthesis non-decisive",
        required=("stable knowledge docs", "reviewed background synthesis", "stronger sources", "decisive evidence"),
    )
    _assert_semantic_contract(
        verify_work,
        "verify-work overlay and child handoff ownership",
        required=(
            "session overlay",
            "canonical verifier verdict",
            "verifier-owned",
            "canonical verifier report content",
            "gpd-verifier",
            "child handoff",
            "one-shot",
        ),
    )
    assert "research_mode=balanced" not in verify_work


def test_verifier_protocol_bundle_guidance_is_manifest_first_for_domain_status() -> None:
    verifier = _read_verifier_prompt()
    protocol_guidance = _between_markers(verifier, "**Protocol bundle guidance", "**Fallback")

    assert_prompt_contracts(
        protocol_guidance,
        *semantic_concept(
            "verifier domain status opens selected verification domain handles",
            required=(
                "protocol_bundle_verifier_extensions",
                "protocol_bundle_load_manifest",
                "do not use `protocol_bundle_context` from init JSON as the first judgment source",
                "Before",
                "assigning",
                "domain-specific",
                "physics status",
                "verification_domains",
                "portable_path",
                "gpd --raw verify bundle-checklist",
                "fallback/check",
            ),
            forbidden=(
                "prefer `protocol_bundle_verifier_extensions` and `protocol_bundle_context`",
                "run `gpd --raw verify bundle-checklist` before assigning",
            ),
        ),
    )
    assert protocol_guidance.index("protocol_bundle_load_manifest") < protocol_guidance.index("Before")
    assert protocol_guidance.index("Before") < protocol_guidance.index("gpd --raw verify bundle-checklist")
