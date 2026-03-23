from __future__ import annotations

from pathlib import Path

import pytest

from gpd.core.frontmatter import validate_frontmatter, verify_summary

FIXTURES_STAGE0 = Path(__file__).resolve().parents[1] / "fixtures" / "stage0"
FIXTURES_STAGE4 = Path(__file__).resolve().parents[1] / "fixtures" / "stage4"


def _summary_with_reference_usage(*, status: str, completed_actions: str, missing_actions: str) -> str:
    return (
        (FIXTURES_STAGE4 / "summary_with_contract_results.md")
        .read_text(encoding="utf-8")
        .replace("status: completed", f"status: {status}", 1)
        .replace("completed_actions: [read, compare, cite]", f"completed_actions: {completed_actions}", 1)
        .replace("missing_actions: []", f"missing_actions: {missing_actions}", 1)
    )


def _verification_with_contract_results() -> str:
    return (
        (FIXTURES_STAGE4 / "verification_with_contract_results.md")
        .read_text(encoding="utf-8")
        .replace(
            "  forbidden_proxies:\n"
            "    fp-benchmark:\n"
            "      status: rejected\n"
            "comparison_verdicts:\n",
            "  forbidden_proxies:\n"
            "    fp-benchmark:\n"
            "      status: rejected\n"
            "  uncertainty_markers:\n"
            "    weakest_anchors: [Reference tolerance interpretation]\n"
            "    disconfirming_observations: [Benchmark agreement disappears once normalization is fixed]\n"
            "comparison_verdicts:\n",
            1,
        )
    )


def test_validate_frontmatter_summary_accepts_contract_results() -> None:
    content = (FIXTURES_STAGE4 / "summary_with_contract_results.md").read_text(encoding="utf-8")

    result = validate_frontmatter(content, "summary")

    assert result.valid is True
    assert result.errors == []


def test_validate_frontmatter_summary_rejects_missing_uncertainty_markers_for_contract_backed_summary() -> None:
    content = (FIXTURES_STAGE4 / "summary_with_contract_results.md").read_text(encoding="utf-8").replace(
        "  uncertainty_markers:\n"
        "    weakest_anchors: [Reference tolerance interpretation]\n"
        "    disconfirming_observations: [Benchmark agreement disappears once normalization is fixed]\n",
        "",
        1,
    )

    result = validate_frontmatter(content, "summary")

    assert result.valid is False
    assert any("uncertainty_markers" in error for error in result.errors)


def test_validate_frontmatter_verification_accepts_contract_results() -> None:
    content = _verification_with_contract_results()

    result = validate_frontmatter(content, "verification")

    assert result.valid is True
    assert result.errors == []


def test_validate_frontmatter_verification_rejects_missing_uncertainty_markers_for_contract_backed_verification() -> None:
    content = (FIXTURES_STAGE4 / "verification_with_contract_results.md").read_text(encoding="utf-8").replace(
        "  uncertainty_markers:\n"
        "    weakest_anchors: [Verification spot-check coverage]\n"
        "    disconfirming_observations: [Independent rerun misses the benchmark tolerance]\n",
        "",
        1,
    )

    result = validate_frontmatter(content, "verification")

    assert result.valid is False
    assert any("uncertainty_markers" in error for error in result.errors)


@pytest.mark.parametrize(
    ("schema_name", "content"),
    [
        (
            "summary",
            (FIXTURES_STAGE4 / "summary_with_contract_results.md")
            .read_text(encoding="utf-8")
            .replace(
                "    claim-benchmark:\n"
                "      status: passed\n"
                "      summary: Benchmark claim verified against the decisive anchor.\n",
                "    claim-benchmark:\n"
                "      summary: Benchmark claim verified against the decisive anchor.\n",
                1,
            ),
        ),
        (
            "verification",
            (FIXTURES_STAGE4 / "verification_with_contract_results.md")
            .read_text(encoding="utf-8")
            .replace(
                "    claim-benchmark:\n"
                "      status: passed\n"
                "      summary: Claim independently verified.\n",
                "    claim-benchmark:\n"
                "      summary: Claim independently verified.\n",
                1,
            ),
        ),
    ],
)
def test_validate_frontmatter_contract_results_rejects_omitted_status_fields(
    schema_name: str,
    content: str,
) -> None:
    result = validate_frontmatter(content, schema_name)

    assert result.valid is False
    assert any("status must be explicit in contract-backed contract_results" in error for error in result.errors)


@pytest.mark.parametrize(
    ("schema_name", "content"),
    [
        (
            "summary",
            (FIXTURES_STAGE4 / "summary_with_contract_results.md").read_text(encoding="utf-8").replace(
                "  uncertainty_markers:\n"
                "    weakest_anchors: [Reference tolerance interpretation]\n"
                "    disconfirming_observations: [Benchmark agreement disappears once normalization is fixed]\n",
                "  uncertainty_markers:\n"
                "    weakest_anchors: []\n"
                "    disconfirming_observations: []\n",
                1,
            ),
        ),
        (
            "verification",
            (FIXTURES_STAGE4 / "verification_with_contract_results.md").read_text(encoding="utf-8").replace(
                "  uncertainty_markers:\n"
                "    weakest_anchors: [Verification spot-check coverage]\n"
                "    disconfirming_observations: [Independent rerun misses the benchmark tolerance]\n",
                "  uncertainty_markers:\n"
                "    weakest_anchors: []\n"
                "    disconfirming_observations: []\n",
                1,
            ),
        ),
    ],
)
def test_validate_frontmatter_contract_results_rejects_empty_uncertainty_markers(
    schema_name: str,
    content: str,
) -> None:
    result = validate_frontmatter(content, schema_name)

    assert result.valid is False
    assert any("weakest_anchors must be non-empty" in error for error in result.errors)
    assert any("disconfirming_observations must be non-empty" in error for error in result.errors)


def test_validate_frontmatter_summary_with_source_path_checks_plan_alignment(tmp_path: Path) -> None:
    phase_dir = tmp_path / ".gpd" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    summary_path = phase_dir / "01-SUMMARY.md"
    summary_path.write_text(
        (FIXTURES_STAGE4 / "summary_with_contract_results.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    result = validate_frontmatter(summary_path.read_text(encoding="utf-8"), "summary", source_path=summary_path)

    assert result.valid is True
    assert result.errors == []


def test_validate_frontmatter_summary_with_source_path_accepts_canonical_plan_contract_ref(tmp_path: Path) -> None:
    phase_dir = tmp_path / ".gpd" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    summary_path = phase_dir / "01-SUMMARY.md"
    summary_path.write_text((FIXTURES_STAGE4 / "summary_with_contract_results.md").read_text(encoding="utf-8"), encoding="utf-8")

    result = validate_frontmatter(summary_path.read_text(encoding="utf-8"), "summary", source_path=summary_path)

    assert result.valid is True
    assert result.errors == []


@pytest.mark.parametrize(
    ("ref_kind", "expected_error"),
    [
        ("absolute", "plan_contract_ref: must reference a canonical project-root-relative .gpd PLAN path"),
        ("external", "plan_contract_ref: must reference a canonical project-root-relative .gpd PLAN path"),
        ("relative", "plan_contract_ref: must reference a canonical project-root-relative .gpd PLAN path"),
        ("traversal", "plan_contract_ref: must not traverse parent directories"),
    ],
)
def test_validate_frontmatter_summary_rejects_unsafe_plan_contract_refs(
    tmp_path: Path,
    ref_kind: str,
    expected_error: str,
) -> None:
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir(parents=True)
    plan_path = artifact_dir / "01-01-PLAN.md"
    plan_path.write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    summary_dir = artifact_dir / "nested"
    summary_dir.mkdir()
    summary_path = summary_dir / "01-SUMMARY.md"

    ref_value = {
        "absolute": f"{plan_path.resolve().as_posix()}#/contract",
        "external": "https://example.com/01-01-PLAN.md#/contract",
        "relative": "01-01-PLAN.md#/contract",
        "traversal": "../01-01-PLAN.md#/contract",
    }[ref_kind]
    summary_path.write_text(
        (FIXTURES_STAGE4 / "summary_with_contract_results.md")
        .read_text(encoding="utf-8")
        .replace(
            "plan_contract_ref: .gpd/phases/01-benchmark/01-01-PLAN.md#/contract",
            f"plan_contract_ref: {ref_value}",
            1,
        ),
        encoding="utf-8",
    )

    schema_only_result = validate_frontmatter(summary_path.read_text(encoding="utf-8"), "summary")
    validation_result = validate_frontmatter(
        summary_path.read_text(encoding="utf-8"),
        "summary",
        source_path=summary_path,
    )
    verification_result = verify_summary(summary_dir, summary_path)

    assert validation_result.valid is False
    assert schema_only_result.valid is False
    assert verification_result.passed is False
    assert any(expected_error in error for error in schema_only_result.errors)
    assert any(expected_error in error for error in validation_result.errors)
    assert any(expected_error in error for error in verification_result.errors)


def test_validate_frontmatter_summary_with_source_path_rejects_non_contract_plan_fragment(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    summary_path = artifact_dir / "01-01-SUMMARY.md"
    summary_path.write_text(
        (FIXTURES_STAGE4 / "summary_with_contract_results.md")
        .read_text(encoding="utf-8")
        .replace(
            "plan_contract_ref: .gpd/phases/01-benchmark/01-01-PLAN.md#/contract",
            "plan_contract_ref: .gpd/phases/01-benchmark/01-01-PLAN.md#/not-contract",
            1,
        ),
        encoding="utf-8",
    )

    result = validate_frontmatter(summary_path.read_text(encoding="utf-8"), "summary", source_path=summary_path)

    assert result.valid is False
    assert "plan_contract_ref: must end with '#/contract'" in result.errors


def test_validate_frontmatter_summary_with_source_path_rejects_unknown_contract_ids(tmp_path: Path) -> None:
    phase_dir = tmp_path / ".gpd" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    summary_path = phase_dir / "01-SUMMARY.md"
    summary_path.write_text(
        (FIXTURES_STAGE4 / "summary_with_contract_results.md").read_text(encoding="utf-8").replace(
            "claim-benchmark:",
            "claim-unknown:",
            1,
        ),
        encoding="utf-8",
    )

    result = validate_frontmatter(summary_path.read_text(encoding="utf-8"), "summary", source_path=summary_path)

    assert result.valid is False
    assert any("Unknown claim contract_results entry: claim-unknown" in error for error in result.errors)


def test_validate_frontmatter_summary_with_source_path_rejects_unknown_linked_ids(tmp_path: Path) -> None:
    phase_dir = tmp_path / ".gpd" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    summary_path = phase_dir / "01-SUMMARY.md"
    summary_path.write_text(
        (FIXTURES_STAGE4 / "summary_with_contract_results.md").read_text(encoding="utf-8").replace(
            "linked_ids: [deliv-figure, test-benchmark, ref-benchmark]",
            "linked_ids: [deliv-figure, test-benchmark, ref-missing]",
            1,
        ),
        encoding="utf-8",
    )

    result = validate_frontmatter(summary_path.read_text(encoding="utf-8"), "summary", source_path=summary_path)

    assert result.valid is False
    assert any(
        "claim claim-benchmark linked_ids references unknown contract id ref-missing" in error for error in result.errors
    )


def test_validate_frontmatter_summary_with_source_path_rejects_unknown_evidence_bindings(tmp_path: Path) -> None:
    phase_dir = tmp_path / ".gpd" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    summary_path = phase_dir / "01-SUMMARY.md"
    summary_path.write_text(
        (FIXTURES_STAGE4 / "summary_with_contract_results.md").read_text(encoding="utf-8").replace(
            "reference_id: ref-benchmark",
            "reference_id: ref-missing",
            1,
        ),
        encoding="utf-8",
    )

    result = validate_frontmatter(summary_path.read_text(encoding="utf-8"), "summary", source_path=summary_path)

    assert result.valid is False
    assert any(
        "claim claim-benchmark evidence references unknown reference_id ref-missing" in error for error in result.errors
    )


def test_validate_frontmatter_summary_with_source_path_accepts_forbidden_proxy_evidence_binding(
    tmp_path: Path,
) -> None:
    phase_dir = tmp_path / ".gpd" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    summary_path = phase_dir / "01-SUMMARY.md"
    summary_path.write_text(
        (FIXTURES_STAGE4 / "summary_with_contract_results.md").read_text(encoding="utf-8").replace(
            "          reference_id: ref-benchmark\n",
            "          reference_id: ref-benchmark\n"
            "          forbidden_proxy_id: fp-benchmark\n",
            1,
        ),
        encoding="utf-8",
    )

    result = validate_frontmatter(summary_path.read_text(encoding="utf-8"), "summary", source_path=summary_path)

    assert result.valid is True
    assert result.errors == []


def test_validate_frontmatter_summary_with_source_path_rejects_unknown_forbidden_proxy_evidence_binding(
    tmp_path: Path,
) -> None:
    phase_dir = tmp_path / ".gpd" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    summary_path = phase_dir / "01-SUMMARY.md"
    summary_path.write_text(
        (FIXTURES_STAGE4 / "summary_with_contract_results.md").read_text(encoding="utf-8").replace(
            "          reference_id: ref-benchmark\n",
            "          reference_id: ref-benchmark\n"
            "          forbidden_proxy_id: fp-missing\n",
            1,
        ),
        encoding="utf-8",
    )

    result = validate_frontmatter(summary_path.read_text(encoding="utf-8"), "summary", source_path=summary_path)

    assert result.valid is False
    assert any(
        "claim claim-benchmark evidence references unknown forbidden_proxy_id fp-missing" in error
        for error in result.errors
    )


def test_validate_frontmatter_summary_with_source_path_ignores_blank_optional_links_and_evidence_ids(
    tmp_path: Path,
) -> None:
    phase_dir = tmp_path / ".gpd" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    summary_path = phase_dir / "01-SUMMARY.md"
    summary_path.write_text(
        (
            (FIXTURES_STAGE4 / "summary_with_contract_results.md")
            .read_text(encoding="utf-8")
            .replace(
                "linked_ids: [deliv-figure, test-benchmark, ref-benchmark]",
                'linked_ids: [deliv-figure, "", test-benchmark, "  ", deliv-figure]',
                1,
            )
            .replace(
                "reference_id: ref-benchmark",
                'reference_id: ""',
                1,
            )
        ),
        encoding="utf-8",
    )

    result = validate_frontmatter(summary_path.read_text(encoding="utf-8"), "summary", source_path=summary_path)

    assert result.valid is True
    assert result.errors == []


def test_validate_frontmatter_summary_with_source_path_reports_unresolved_plan_contract_ref(tmp_path: Path) -> None:
    phase_dir = tmp_path / ".gpd" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    summary_path = phase_dir / "01-SUMMARY.md"
    summary_path.write_text(
        (FIXTURES_STAGE4 / "summary_with_contract_results.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    result = validate_frontmatter(summary_path.read_text(encoding="utf-8"), "summary", source_path=summary_path)

    assert result.valid is False
    assert "plan_contract_ref: could not resolve matching plan contract" in result.errors


def test_validate_frontmatter_summary_does_not_resolve_plan_contract_ref_above_project_root(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    (project_root / ".gpd").mkdir(parents=True)
    summary_dir = project_root / "artifacts" / "nested"
    summary_dir.mkdir(parents=True)
    summary_path = summary_dir / "01-SUMMARY.md"
    summary_path.write_text(
        (FIXTURES_STAGE4 / "summary_with_contract_results.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    external_phase_dir = tmp_path / ".gpd" / "phases" / "01-benchmark"
    external_phase_dir.mkdir(parents=True)
    (external_phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    validation_result = validate_frontmatter(
        summary_path.read_text(encoding="utf-8"),
        "summary",
        source_path=summary_path,
    )
    verification_result = verify_summary(summary_dir, summary_path)

    assert validation_result.valid is False
    assert verification_result.passed is False
    assert "plan_contract_ref: could not resolve matching plan contract" in validation_result.errors
    assert "plan_contract_ref: could not resolve matching plan contract" in verification_result.errors


def test_validate_frontmatter_summary_with_source_path_reports_referenced_plan_contract_schema_errors(
    tmp_path: Path,
) -> None:
    phase_dir = tmp_path / ".gpd" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md")
        .read_text(encoding="utf-8")
        .replace("must_surface: true", 'must_surface: "yes"', 1),
        encoding="utf-8",
    )
    summary_path = phase_dir / "01-SUMMARY.md"
    summary_path.write_text((FIXTURES_STAGE4 / "summary_with_contract_results.md").read_text(encoding="utf-8"), encoding="utf-8")

    result = validate_frontmatter(summary_path.read_text(encoding="utf-8"), "summary", source_path=summary_path)

    assert result.valid is False
    assert "plan_contract_ref: referenced PLAN contract: references.0.must_surface must be a boolean" in result.errors


def test_validate_frontmatter_summary_with_source_path_reports_referenced_plan_contract_semantic_errors(
    tmp_path: Path,
) -> None:
    phase_dir = tmp_path / ".gpd" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md")
        .read_text(encoding="utf-8")
        .replace(
            "  acceptance_tests:\n"
            "    - id: test-benchmark\n"
            "      subject: claim-benchmark\n"
            "      kind: benchmark\n"
            "      procedure: Compare against the benchmark reference\n"
            "      pass_condition: Matches reference within tolerance\n"
            "      evidence_required: [deliv-figure, ref-benchmark]\n",
            "  acceptance_tests: []\n",
            1,
        ),
        encoding="utf-8",
    )
    summary_path = phase_dir / "01-SUMMARY.md"
    summary_path.write_text((FIXTURES_STAGE4 / "summary_with_contract_results.md").read_text(encoding="utf-8"), encoding="utf-8")

    result = validate_frontmatter(summary_path.read_text(encoding="utf-8"), "summary", source_path=summary_path)

    assert result.valid is False
    assert "plan_contract_ref: referenced PLAN contract: missing acceptance_tests" in result.errors


def test_validate_frontmatter_verification_with_source_path_requires_contract_results(tmp_path: Path) -> None:
    phase_dir = tmp_path / ".gpd" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    verification_path = phase_dir / "01-VERIFICATION.md"
    verification_path.write_text(
        "---\n"
        "phase: 01-benchmark\n"
        "verified: 2026-03-13T00:00:00Z\n"
        "status: passed\n"
        "score: 1/1 contract targets verified\n"
        "plan_contract_ref: .gpd/phases/01-benchmark/01-01-PLAN.md#/contract\n"
        "---\n\n"
        "# Verification\n",
        encoding="utf-8",
    )

    result = validate_frontmatter(
        verification_path.read_text(encoding="utf-8"),
        "verification",
        source_path=verification_path,
    )

    assert result.valid is False
    assert "contract_results: required for contract-backed plan" in result.errors


def test_validate_frontmatter_verification_with_adjacent_contract_backed_plan_requires_plan_contract_ref(
    tmp_path: Path,
) -> None:
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    verification_path = artifact_dir / "01-VERIFICATION.md"
    verification_path.write_text(
        _verification_with_contract_results()
        .replace(
            "plan_contract_ref: .gpd/phases/01-benchmark/01-01-PLAN.md#/contract\n",
            "",
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
    assert "plan_contract_ref: required for contract-backed plan" in result.errors


def test_validate_frontmatter_verification_with_source_path_accepts_canonical_plan_contract_ref(tmp_path: Path) -> None:
    phase_dir = tmp_path / ".gpd" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    verification_path = phase_dir / "01-VERIFICATION.md"
    verification_path.write_text(_verification_with_contract_results(), encoding="utf-8")

    result = validate_frontmatter(
        verification_path.read_text(encoding="utf-8"),
        "verification",
        source_path=verification_path,
    )

    assert result.valid is True
    assert result.errors == []


def test_validate_frontmatter_verification_with_source_path_accepts_structured_suggested_contract_checks(
    tmp_path: Path,
) -> None:
    phase_dir = tmp_path / ".gpd" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    verification_path = phase_dir / "01-VERIFICATION.md"
    verification_path.write_text(
        _verification_with_contract_results()
        .replace(
            "status: passed\nscore: 3/3 contract targets verified\n",
            "status: gaps_found\nscore: 1/3 contract targets verified\n",
            1,
        )
        .replace(
            "      status: passed\n      summary: Claim independently verified.\n",
            "      status: partial\n      summary: Benchmark comparison started but is not yet decisive.\n",
            1,
        )
        .replace(
            "      status: passed\n      summary: Acceptance test executed and passed.\n",
            "      status: partial\n      summary: Initial benchmark comparison run completed.\n",
            1,
        )
        .replace(
            "    verdict: pass\n",
            "    verdict: inconclusive\n",
            1,
        )
        .replace(
            "comparison_verdicts:\n",
            "suggested_contract_checks:\n"
            "  - check: Add decisive normalization benchmark comparison\n"
            "    reason: The reported agreement depends on a normalization-sensitive benchmark that is not yet explicit\n"
            "    suggested_subject_kind: acceptance_test\n"
            "    suggested_subject_id: test-benchmark\n"
            "    evidence_path: .gpd/phases/01-benchmark/01-VERIFICATION.md\n"
            "comparison_verdicts:\n",
            1,
        ),
        encoding="utf-8",
    )

    result = validate_frontmatter(
        verification_path.read_text(encoding="utf-8"),
        "verification",
        source_path=verification_path,
    )

    assert result.valid is True
    assert result.errors == []


def test_validate_frontmatter_verification_with_source_path_accepts_partial_results_with_inconclusive_verdict(
    tmp_path: Path,
) -> None:
    phase_dir = tmp_path / ".gpd" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    verification_path = phase_dir / "01-VERIFICATION.md"
    verification_path.write_text(
        _verification_with_contract_results()
        .replace(
            "status: passed\nscore: 3/3 contract targets verified\n",
            "status: gaps_found\nscore: 1/3 contract targets verified\n",
            1,
        )
        .replace(
            "      status: passed\n      summary: Claim independently verified.\n",
            "      status: partial\n      summary: Benchmark comparison started but is not yet decisive.\n",
            1,
        )
        .replace(
            "      status: passed\n      summary: Acceptance test executed and passed.\n",
            "      status: partial\n      summary: Initial benchmark comparison run completed.\n",
            1,
        )
        .replace(
            "    verdict: pass\n",
            "    verdict: inconclusive\n",
            1,
        ),
        encoding="utf-8",
    )
    verification_path.write_text(
        verification_path.read_text(encoding="utf-8").replace(
            "comparison_verdicts:\n",
            "suggested_contract_checks:\n"
            "  - check: contract.benchmark_recovery\n"
            "    reason: Need a decisive benchmark comparison before this target can pass.\n"
            "    suggested_subject_kind: acceptance_test\n"
            "    suggested_subject_id: test-benchmark\n"
            "    evidence_path: .gpd/phases/01-benchmark/01-VERIFICATION.md\n"
            "comparison_verdicts:\n",
            1,
        ),
        encoding="utf-8",
    )

    result = validate_frontmatter(
        verification_path.read_text(encoding="utf-8"),
        "verification",
        source_path=verification_path,
    )

    assert result.valid is True
    assert result.errors == []


def test_validate_frontmatter_verification_rejects_undocumented_suggested_contract_check_shape(
    tmp_path: Path,
) -> None:
    phase_dir = tmp_path / ".gpd" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    verification_path = phase_dir / "01-VERIFICATION.md"
    verification_path.write_text(
        _verification_with_contract_results()
        .replace(
            "status: passed\nscore: 3/3 contract targets verified\n",
            "status: gaps_found\nscore: 1/3 contract targets verified\n",
            1,
        )
        .replace(
            "      status: passed\n      summary: Claim independently verified.\n",
            "      status: partial\n      summary: Benchmark comparison started but is not yet decisive.\n",
            1,
        )
        .replace(
            "      status: passed\n      summary: Acceptance test executed and passed.\n",
            "      status: partial\n      summary: Initial benchmark comparison run completed.\n",
            1,
        )
        .replace(
            "comparison_verdicts:\n",
            "suggested_contract_checks:\n"
            "  - check_id: contract.benchmark_recovery\n"
            "    reason: Need a decisive benchmark comparison before this target can pass.\n"
            "comparison_verdicts:\n",
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
    assert any("suggested_contract_checks: [0] check is required" in error for error in result.errors)


def test_validate_frontmatter_summary_rejects_plan_contract_ref_that_points_to_different_plan(
    tmp_path: Path,
) -> None:
    phase_dir = tmp_path / ".gpd" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    summary_path = phase_dir / "01-SUMMARY.md"
    summary_path.write_text(
        (FIXTURES_STAGE4 / "summary_with_contract_results.md")
        .read_text(encoding="utf-8")
        .replace("plan: 01\n", "plan: 02\n", 1),
        encoding="utf-8",
    )

    result = validate_frontmatter(summary_path.read_text(encoding="utf-8"), "summary", source_path=summary_path)

    assert result.valid is False
    assert "plan_contract_ref: could not resolve matching plan contract" in result.errors


def test_verify_summary_rejects_unresolved_plan_contract_ref(tmp_path: Path) -> None:
    plan_path = tmp_path / "01-01-PLAN.md"
    plan_path.write_text((FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"), encoding="utf-8")
    summary_path = tmp_path / "01-01-SUMMARY.md"
    summary_path.write_text(
        (FIXTURES_STAGE4 / "summary_with_contract_results.md")
        .read_text(encoding="utf-8")
        .replace(
            "plan_contract_ref: .gpd/phases/01-benchmark/01-01-PLAN.md#/contract",
            "plan_contract_ref: .gpd/phases/01-benchmark/01-02-PLAN.md#/contract",
            1,
        ),
        encoding="utf-8",
    )

    result = verify_summary(tmp_path, summary_path)

    assert result.passed is False
    assert "plan_contract_ref: could not resolve matching plan contract" in result.errors


def test_verify_summary_rejects_non_contract_plan_fragment(tmp_path: Path) -> None:
    plan_path = tmp_path / ".gpd" / "phases" / "01-benchmark" / "01-01-PLAN.md"
    plan_path.parent.mkdir(parents=True)
    plan_path.write_text((FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"), encoding="utf-8")
    summary_path = tmp_path / ".gpd" / "phases" / "01-benchmark" / "01-SUMMARY.md"
    summary_path.write_text(
        (FIXTURES_STAGE4 / "summary_with_contract_results.md")
        .read_text(encoding="utf-8")
        .replace(
            "plan_contract_ref: .gpd/phases/01-benchmark/01-01-PLAN.md#/contract",
            "plan_contract_ref: .gpd/phases/01-benchmark/01-01-PLAN.md#/summary",
            1,
        ),
        encoding="utf-8",
    )

    result = verify_summary(tmp_path, summary_path)

    assert result.passed is False
    assert "plan_contract_ref: must end with '#/contract'" in result.errors


def test_validate_frontmatter_summary_rejects_contradictory_comparison_verdict(tmp_path: Path) -> None:
    phase_dir = tmp_path / ".gpd" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    summary_path = phase_dir / "01-SUMMARY.md"
    summary_path.write_text(
        (FIXTURES_STAGE4 / "summary_with_contract_results.md")
        .read_text(encoding="utf-8")
        .replace("verdict: pass", "verdict: fail", 1),
        encoding="utf-8",
    )

    result = validate_frontmatter(summary_path.read_text(encoding="utf-8"), "summary", source_path=summary_path)

    assert result.valid is False
    assert any("contradicts passed contract_results status" in error for error in result.errors)


@pytest.mark.parametrize(
    ("status", "completed_actions", "missing_actions", "message"),
    [
        ("completed", "[read]", "[compare]", "status=completed requires missing_actions to be empty"),
        (
            "not_applicable",
            "[read]",
            "[]",
            "status=not_applicable requires completed_actions and missing_actions to be empty",
        ),
        (
            "missing",
            "[read, compare]",
            "[compare]",
            "completed_actions and missing_actions must not overlap: compare",
        ),
    ],
)
def test_validate_frontmatter_summary_rejects_contradictory_reference_action_ledger(
    tmp_path: Path,
    status: str,
    completed_actions: str,
    missing_actions: str,
    message: str,
) -> None:
    phase_dir = tmp_path / ".gpd" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    summary_path = phase_dir / "01-SUMMARY.md"
    summary_path.write_text(
        _summary_with_reference_usage(
            status=status,
            completed_actions=completed_actions,
            missing_actions=missing_actions,
        ),
        encoding="utf-8",
    )

    result = validate_frontmatter(summary_path.read_text(encoding="utf-8"), "summary", source_path=summary_path)

    assert result.valid is False
    assert any(message in error for error in result.errors)


def test_validate_frontmatter_verification_with_source_path_requires_suggested_contract_checks_for_partial_decisive_checks(
    tmp_path: Path,
) -> None:
    phase_dir = tmp_path / ".gpd" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    verification_path = phase_dir / "01-VERIFICATION.md"
    verification_path.write_text(
        _verification_with_contract_results()
        .replace(
            "status: passed\nscore: 3/3 contract targets verified\n",
            "status: gaps_found\nscore: 1/3 contract targets verified\n",
            1,
        )
        .replace(
            "      status: passed\n      summary: Claim independently verified.\n",
            "      status: partial\n      summary: Decisive benchmark comparison remains open.\n",
            1,
        )
        .replace(
            "      status: passed\n      summary: Acceptance test executed and passed.\n",
            "      status: partial\n      summary: Benchmark comparison was attempted but is still open.\n",
            1,
        )
        .replace(
            "    verdict: pass\n",
            "    verdict: inconclusive\n",
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
    assert (
        "suggested_contract_checks: required when decisive benchmark/cross-method checks remain missing, partial, or incomplete"
        in result.errors
    )


def test_verify_summary_requires_contract_results_for_contract_backed_plan(tmp_path: Path) -> None:
    plan_path = tmp_path / "01-01-PLAN.md"
    plan_path.write_text((FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"), encoding="utf-8")
    summary_path = tmp_path / "01-01-SUMMARY.md"
    summary_path.write_text(
        "---\nphase: 01-benchmark\nplan: 01\ndepth: full\nprovides: [benchmark comparison]\ncompleted: 2026-03-13\n---\n\n# Summary\n",
        encoding="utf-8",
    )

    result = verify_summary(tmp_path, summary_path)

    assert result.passed is False
    assert "contract_results: required for contract-backed plan" in result.errors


def test_verify_summary_requires_plan_contract_ref_for_contract_backed_plan(tmp_path: Path) -> None:
    plan_path = tmp_path / "01-01-PLAN.md"
    plan_path.write_text((FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"), encoding="utf-8")
    summary_path = tmp_path / "01-01-SUMMARY.md"
    summary_path.write_text(
        (
            (FIXTURES_STAGE4 / "summary_with_contract_results.md")
            .read_text(encoding="utf-8")
            .replace('plan_contract_ref: .gpd/phases/01-benchmark/01-01-PLAN.md#/contract\n', "")
        ),
        encoding="utf-8",
    )

    result = verify_summary(tmp_path, summary_path)

    assert result.passed is False
    assert "plan_contract_ref: required for contract-backed plan" in result.errors


def test_verify_summary_rejects_unknown_contract_ids(tmp_path: Path) -> None:
    phase_dir = tmp_path / ".gpd" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    plan_path = phase_dir / "01-01-PLAN.md"
    plan_path.write_text((FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"), encoding="utf-8")
    summary_content = (FIXTURES_STAGE4 / "summary_with_contract_results.md").read_text(encoding="utf-8").replace(
        "claim-benchmark:",
        "claim-unknown:",
        1,
    )
    summary_path = phase_dir / "01-01-SUMMARY.md"
    summary_path.write_text(summary_content, encoding="utf-8")
    (tmp_path / "figures").mkdir()
    (tmp_path / "figures" / "benchmark.png").write_text("placeholder", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "benchmark.py").write_text("print('ok')\n", encoding="utf-8")

    result = verify_summary(tmp_path, summary_path)

    assert result.passed is False
    assert any("Unknown claim contract_results entry: claim-unknown" in error for error in result.errors)


def test_verify_summary_allows_explicit_incomplete_contract_results_statuses(tmp_path: Path) -> None:
    phase_dir = tmp_path / ".gpd" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    plan_path = phase_dir / "01-01-PLAN.md"
    plan_path.write_text((FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"), encoding="utf-8")
    summary_content = (
        (FIXTURES_STAGE4 / "summary_with_contract_results.md")
        .read_text(encoding="utf-8")
        .replace(
            "      status: passed\n      summary: Benchmark claim verified against the decisive anchor.\n",
            "      status: partial\n      summary: Benchmark comparison is still in progress.\n",
            1,
        )
        .replace(
            "      status: passed\n      path: figures/benchmark.png\n      summary: Figure produced with uncertainty band and benchmark overlay.\n",
            "      status: not_attempted\n      path: figures/benchmark.png\n      summary: Figure regeneration is queued behind the next run.\n",
            1,
        )
        .replace(
            "      status: passed\n      summary: Benchmark reproduced within the contracted tolerance.\n",
            "      status: partial\n      summary: Initial comparison run completed but is not yet decisive.\n",
            1,
        )
        .replace(
            "      status: rejected\n      notes: Qualitative trend agreement was not accepted without the numerical benchmark check.\n",
            "      status: unresolved\n      notes: Proxy rejection will be finalized after the decisive rerun.\n",
            1,
        )
        .replace(
            "    verdict: pass\n    recommended_action: Keep this benchmark comparison in the paper.\n",
            "    verdict: inconclusive\n    recommended_action: Rerun the benchmark after the normalization fix.\n",
            1,
        )
    )
    summary_path = phase_dir / "01-01-SUMMARY.md"
    summary_path.write_text(summary_content, encoding="utf-8")
    (tmp_path / "figures").mkdir()
    (tmp_path / "figures" / "benchmark.png").write_text("placeholder", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "benchmark.py").write_text("print('ok')\n", encoding="utf-8")

    result = verify_summary(tmp_path, summary_path)

    assert result.passed is True


def test_validate_frontmatter_summary_rejects_missing_contract_results_coverage(tmp_path: Path) -> None:
    phase_dir = tmp_path / ".gpd" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    summary_path = phase_dir / "01-SUMMARY.md"
    summary_path.write_text(
        (FIXTURES_STAGE4 / "summary_with_contract_results.md").read_text(encoding="utf-8").replace(
            "  deliverables:\n"
            "    deliv-figure:\n"
            "      status: passed\n"
            "      path: figures/benchmark.png\n"
            "      summary: Figure produced with uncertainty band and benchmark overlay.\n"
            "      linked_ids: [claim-benchmark, test-benchmark]\n",
            "",
            1,
        ),
        encoding="utf-8",
    )

    result = validate_frontmatter(summary_path.read_text(encoding="utf-8"), "summary", source_path=summary_path)

    assert result.valid is False
    assert "Missing deliverable contract_results entry: deliv-figure" in result.errors


def test_validate_frontmatter_summary_rejects_mismatched_comparison_verdict_subject_kind(tmp_path: Path) -> None:
    phase_dir = tmp_path / ".gpd" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    summary_path = phase_dir / "01-SUMMARY.md"
    summary_path.write_text(
        (FIXTURES_STAGE4 / "summary_with_contract_results.md")
        .read_text(encoding="utf-8")
        .replace("subject_kind: claim", "subject_kind: deliverable", 1),
        encoding="utf-8",
    )

    result = validate_frontmatter(summary_path.read_text(encoding="utf-8"), "summary", source_path=summary_path)

    assert result.valid is False
    assert any("has subject_kind deliverable but contract id is a claim" in error for error in result.errors)


def test_validate_frontmatter_summary_rejects_non_contract_comparison_verdict_subject_kind(tmp_path: Path) -> None:
    phase_dir = tmp_path / ".gpd" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    summary_path = phase_dir / "01-SUMMARY.md"
    summary_path.write_text(
        (FIXTURES_STAGE4 / "summary_with_contract_results.md")
        .read_text(encoding="utf-8")
        .replace("subject_kind: claim", "subject_kind: artifact", 1),
        encoding="utf-8",
    )

    result = validate_frontmatter(summary_path.read_text(encoding="utf-8"), "summary", source_path=summary_path)

    assert result.valid is False
    assert any("comparison_verdicts:" in error and "acceptance_test' or 'reference'" in error for error in result.errors)


@pytest.mark.parametrize("role", ["supporting", "supplemental"])
def test_validate_frontmatter_summary_allows_non_decisive_comparison_tension_without_contradicting_passed_target(
    tmp_path: Path, role: str
) -> None:
    phase_dir = tmp_path / ".gpd" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    summary_path = phase_dir / "01-SUMMARY.md"
    summary_path.write_text(
        (FIXTURES_STAGE4 / "summary_with_contract_results.md").read_text(encoding="utf-8").replace(
            "comparison_verdicts:\n",
            "comparison_verdicts:\n"
            "  - subject_id: claim-benchmark\n"
            "    subject_kind: claim\n"
            f"    subject_role: {role}\n"
            "    reference_id: ref-benchmark\n"
            "    comparison_kind: prior_work\n"
            "    metric: chi2_ndof\n"
            '    threshold: "<= 1.5"\n'
            "    verdict: tension\n"
            "    recommended_action: Reconcile the auxiliary prior-work normalization.\n",
            1,
        ),
        encoding="utf-8",
    )

    result = validate_frontmatter(summary_path.read_text(encoding="utf-8"), "summary", source_path=summary_path)

    assert result.valid is True
    assert result.errors == []


def test_validate_frontmatter_summary_rejects_missing_subject_role_for_non_decisive_comparison_kind(
    tmp_path: Path,
) -> None:
    phase_dir = tmp_path / ".gpd" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    summary_path = phase_dir / "01-SUMMARY.md"
    summary_path.write_text(
        (FIXTURES_STAGE4 / "summary_with_contract_results.md")
        .read_text(encoding="utf-8")
        .replace(
            "comparison_verdicts:\n",
            "comparison_verdicts:\n"
            "  - subject_id: claim-benchmark\n"
            "    subject_kind: claim\n"
            "    comparison_kind: other\n"
            "    metric: chi2_ndof\n"
            '    threshold: "<= 1.5"\n'
            "    verdict: tension\n"
            "    recommended_action: Reconcile the auxiliary prior-work normalization.\n",
            1,
        ),
        encoding="utf-8",
    )

    result = validate_frontmatter(summary_path.read_text(encoding="utf-8"), "summary", source_path=summary_path)

    assert result.valid is False
    assert any("subject_role" in error for error in result.errors)


def test_validate_frontmatter_summary_requires_decisive_role_for_decisive_comparison_coverage(tmp_path: Path) -> None:
    phase_dir = tmp_path / ".gpd" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    summary_path = phase_dir / "01-SUMMARY.md"
    summary_path.write_text(
        (FIXTURES_STAGE4 / "summary_with_contract_results.md")
        .read_text(encoding="utf-8")
        .replace("subject_role: decisive", "subject_role: supporting", 1),
        encoding="utf-8",
    )

    result = validate_frontmatter(summary_path.read_text(encoding="utf-8"), "summary", source_path=summary_path)

    assert result.valid is False
    assert any("Missing decisive comparison_verdict for acceptance test test-benchmark" in error for error in result.errors)


@pytest.mark.parametrize("comparison_kind", ["benchmark", "prior_work", "experiment", "cross_method", "baseline"])
def test_validate_frontmatter_summary_rejects_missing_subject_role_for_decisive_comparison_kind(
    tmp_path: Path, comparison_kind: str
) -> None:
    phase_dir = tmp_path / ".gpd" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    reference_line = "    reference_id: ref-benchmark\n" if comparison_kind not in {"cross_method"} else ""
    summary_path = phase_dir / "01-SUMMARY.md"
    summary_path.write_text(
        (FIXTURES_STAGE4 / "summary_with_contract_results.md").read_text(encoding="utf-8").replace(
            "comparison_verdicts:\n",
            "comparison_verdicts:\n"
            "  - subject_id: claim-benchmark\n"
            "    subject_kind: claim\n"
            f"{reference_line}"
            f"    comparison_kind: {comparison_kind}\n"
            "    metric: relative_error\n"
            '    threshold: "<= 0.02"\n'
            "    verdict: pass\n"
            "    recommended_action: Keep this comparison explicit in the record.\n",
            1,
        ),
        encoding="utf-8",
    )

    result = validate_frontmatter(summary_path.read_text(encoding="utf-8"), "summary", source_path=summary_path)

    assert result.valid is False
    assert any("subject_role" in error for error in result.errors)


@pytest.mark.parametrize("comparison_kind", ["benchmark", "prior_work", "experiment", "baseline"])
def test_validate_frontmatter_summary_rejects_unanchored_decisive_external_comparison(
    tmp_path: Path, comparison_kind: str
) -> None:
    phase_dir = tmp_path / ".gpd" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    summary_path = phase_dir / "01-SUMMARY.md"
    summary_path.write_text(
        (FIXTURES_STAGE4 / "summary_with_contract_results.md").read_text(encoding="utf-8").replace(
            "comparison_verdicts:\n",
            "comparison_verdicts:\n"
            "  - subject_id: claim-benchmark\n"
            "    subject_kind: claim\n"
            "    subject_role: decisive\n"
            f"    comparison_kind: {comparison_kind}\n"
            "    metric: relative_error\n"
            '    threshold: "<= 0.02"\n'
            "    verdict: pass\n"
            "    recommended_action: Keep this comparison explicit in the record.\n",
            1,
        ),
        encoding="utf-8",
    )

    result = validate_frontmatter(summary_path.read_text(encoding="utf-8"), "summary", source_path=summary_path)

    assert result.valid is False
    assert any(
        f"must include reference_id or use subject_kind: reference for decisive {comparison_kind} comparisons"
        in error
        for error in result.errors
    )


def test_validate_frontmatter_summary_requires_reference_backed_comparison_to_use_decisive_kind(tmp_path: Path) -> None:
    phase_dir = tmp_path / ".gpd" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md")
        .read_text(encoding="utf-8")
        .replace("kind: benchmark", "kind: existence", 1)
        .replace("procedure: Compare against the benchmark reference", "procedure: Confirm the artifact exists", 1)
        .replace("pass_condition: Matches reference within tolerance", "pass_condition: Artifact exists", 1),
        encoding="utf-8",
    )
    summary_path = phase_dir / "01-SUMMARY.md"
    summary_path.write_text(
        (FIXTURES_STAGE4 / "summary_with_contract_results.md")
        .read_text(encoding="utf-8")
        .replace(
            "comparison_kind: benchmark",
            "comparison_kind: other",
            1,
        ),
        encoding="utf-8",
    )

    result = validate_frontmatter(summary_path.read_text(encoding="utf-8"), "summary", source_path=summary_path)

    assert result.valid is False
    assert "Missing decisive comparison_verdict for reference ref-benchmark" in result.errors


def test_validate_frontmatter_summary_rejects_prior_work_verdict_for_benchmark_acceptance_test(
    tmp_path: Path,
) -> None:
    phase_dir = tmp_path / ".gpd" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    summary_path = phase_dir / "01-SUMMARY.md"
    summary_path.write_text(
        (FIXTURES_STAGE4 / "summary_with_contract_results.md")
        .read_text(encoding="utf-8")
        .replace("comparison_kind: benchmark", "comparison_kind: prior_work", 1),
        encoding="utf-8",
    )

    result = validate_frontmatter(summary_path.read_text(encoding="utf-8"), "summary", source_path=summary_path)

    assert result.valid is False
    assert any("Missing decisive comparison_verdict for acceptance test test-benchmark" in error for error in result.errors)


def test_validate_frontmatter_summary_accepts_decisive_cross_method_without_reference_anchor(
    tmp_path: Path,
) -> None:
    phase_dir = tmp_path / ".gpd" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md")
        .read_text(encoding="utf-8")
        .replace("role: benchmark", "role: method", 1)
        .replace("required_actions: [read, compare, cite]", "required_actions: [read, cite]", 1)
        .replace("kind: benchmark", "kind: cross_method", 1)
        .replace("procedure: Compare against the benchmark reference", "procedure: Compare the independent methods", 1)
        .replace("pass_condition: Matches reference within tolerance", "pass_condition: Independent methods agree within tolerance", 1),
        encoding="utf-8",
    )
    summary_path = phase_dir / "01-SUMMARY.md"
    summary_path.write_text(
        (FIXTURES_STAGE4 / "summary_with_contract_results.md")
        .read_text(encoding="utf-8")
        .replace(
            "    subject_role: decisive\n"
            "    reference_id: ref-benchmark\n"
            "    comparison_kind: benchmark\n",
            "    subject_role: decisive\n"
            "    comparison_kind: cross_method\n",
            1,
        ),
        encoding="utf-8",
    )

    result = validate_frontmatter(summary_path.read_text(encoding="utf-8"), "summary", source_path=summary_path)

    assert result.valid is True
    assert result.errors == []


def test_validate_frontmatter_summary_rejects_contract_results_context_usage(tmp_path: Path) -> None:
    phase_dir = tmp_path / ".gpd" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    summary_path = phase_dir / "01-SUMMARY.md"
    summary_path.write_text(
        (FIXTURES_STAGE4 / "summary_with_contract_results.md").read_text(encoding="utf-8").replace(
            "  uncertainty_markers:\n",
            "  context_usage:\n"
            "    prior-baseline:\n"
            "      status: consulted\n"
            "      summary: Used prior baseline notes.\n"
            "  uncertainty_markers:\n",
            1,
        ),
        encoding="utf-8",
    )

    result = validate_frontmatter(summary_path.read_text(encoding="utf-8"), "summary", source_path=summary_path)

    assert result.valid is False
    assert any("contract_results:" in error and "context_usage" in error for error in result.errors)


def test_validate_frontmatter_summary_requires_decisive_verdict_even_when_comparison_not_attempted(tmp_path: Path) -> None:
    phase_dir = tmp_path / ".gpd" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    original = (
        (FIXTURES_STAGE4 / "summary_with_contract_results.md")
        .read_text(encoding="utf-8")
        .replace("status: passed\n      summary: Benchmark claim verified against the decisive anchor.\n", "status: not_attempted\n      summary: Benchmark claim remains open.\n", 1)
        .replace(
            "status: passed\n      summary: Benchmark reproduced within the contracted tolerance.\n",
            "status: not_attempted\n      summary: Benchmark comparison has not been run yet.\n",
            1,
        )
    )
    frontmatter, body = original.split("---\n\n", 1)
    trimmed_frontmatter = frontmatter.split("\ncomparison_verdicts:\n", 1)[0] + "\n---\n"
    summary_path = phase_dir / "01-SUMMARY.md"
    summary_path.write_text(trimmed_frontmatter + "\n" + body, encoding="utf-8")

    result = validate_frontmatter(summary_path.read_text(encoding="utf-8"), "summary", source_path=summary_path)

    assert result.valid is False
    assert any("Missing decisive comparison_verdict for acceptance test test-benchmark" in error for error in result.errors)


def test_validate_frontmatter_verification_rejects_mismatched_suggested_contract_check_binding(
    tmp_path: Path,
) -> None:
    phase_dir = tmp_path / ".gpd" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    verification_path = phase_dir / "01-VERIFICATION.md"
    verification_path.write_text(
        _verification_with_contract_results()
        .replace("status: passed\nscore: 3/3 contract targets verified\n", "status: gaps_found\nscore: 3/3 contract targets verified\n", 1)
        .replace(
            "comparison_verdicts:\n",
            "suggested_contract_checks:\n"
            "  - check: Add decisive benchmark rerun\n"
            "    reason: The benchmark needs a narrower comparison window.\n"
            "    suggested_subject_kind: claim\n"
            "    suggested_subject_id: test-benchmark\n"
            "comparison_verdicts:\n",
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
    assert any("references test-benchmark as claim, but the contract declares it as acceptance_test" in error for error in result.errors)


def test_validate_frontmatter_verification_rejects_half_bound_suggested_contract_check(tmp_path: Path) -> None:
    phase_dir = tmp_path / ".gpd" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    verification_path = phase_dir / "01-VERIFICATION.md"
    verification_path.write_text(
        _verification_with_contract_results()
        .replace("status: passed\nscore: 3/3 contract targets verified\n", "status: gaps_found\nscore: 3/3 contract targets verified\n", 1)
        .replace(
            "comparison_verdicts:\n",
            "suggested_contract_checks:\n"
            "  - check: Add decisive benchmark rerun\n"
            "    reason: The benchmark needs a narrower comparison window.\n"
            "    suggested_subject_kind: acceptance_test\n"
            "comparison_verdicts:\n",
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
    assert any("must provide suggested_subject_kind and suggested_subject_id together" in error for error in result.errors)


def test_validate_frontmatter_verification_rejects_extra_keys_in_suggested_contract_check(tmp_path: Path) -> None:
    phase_dir = tmp_path / ".gpd" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    verification_path = phase_dir / "01-VERIFICATION.md"
    verification_path.write_text(
        _verification_with_contract_results()
        .replace(
            "status: passed\nscore: 3/3 contract targets verified\n",
            "status: gaps_found\nscore: 1/3 contract targets verified\n",
            1,
        )
        .replace(
            "      status: passed\n      summary: Claim independently verified.\n",
            "      status: partial\n      summary: Benchmark comparison started but is not yet decisive.\n",
            1,
        )
        .replace(
            "      status: passed\n      summary: Acceptance test executed and passed.\n",
            "      status: partial\n      summary: Initial benchmark comparison run completed.\n",
            1,
        )
        .replace(
            "    verdict: pass\n",
            "    verdict: inconclusive\n",
            1,
        )
        .replace(
            "comparison_verdicts:\n",
            "suggested_contract_checks:\n"
            "  - check: Add decisive normalization benchmark comparison\n"
            "    reason: The reported agreement depends on a normalization-sensitive benchmark that is not yet explicit\n"
            "    suggested_subject_kind: acceptance_test\n"
            "    suggested_subject_id: test-benchmark\n"
            "    evidence_path: .gpd/phases/01-benchmark/01-VERIFICATION.md\n"
            "    check_id: benchmark-gap\n"
            "comparison_verdicts:\n",
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
        "suggested_contract_checks: [0] check_id: Extra inputs are not permitted" in error
        for error in result.errors
    )


def test_validate_frontmatter_verification_rejects_passed_status_with_partial_contract_results(tmp_path: Path) -> None:
    phase_dir = tmp_path / ".gpd" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    verification_path = phase_dir / "01-VERIFICATION.md"
    verification_path.write_text(
        _verification_with_contract_results()
        .replace(
            "      status: passed\n      summary: Claim independently verified.\n",
            "      status: partial\n      summary: Claim still needs the decisive rerun.\n",
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
        "status: passed is inconsistent with non-passed contract_results targets: claim claim-benchmark" in error
        for error in result.errors
    )


def test_validate_frontmatter_verification_rejects_passed_status_with_suggested_contract_checks(tmp_path: Path) -> None:
    phase_dir = tmp_path / ".gpd" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    verification_path = phase_dir / "01-VERIFICATION.md"
    verification_path.write_text(
        _verification_with_contract_results()
        .replace(
            "comparison_verdicts:\n",
            "suggested_contract_checks:\n"
            "  - check: Add decisive normalization benchmark comparison\n"
            "    reason: The decisive check is still pending.\n"
            "    suggested_subject_kind: claim\n"
            "    suggested_subject_id: claim-benchmark\n"
            "    evidence_path: .gpd/phases/01-benchmark/01-VERIFICATION.md\n"
            "comparison_verdicts:\n",
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
    assert "status: passed is inconsistent with non-empty suggested_contract_checks" in result.errors


def test_validate_frontmatter_verification_rejects_passed_status_with_unresolved_forbidden_proxy(tmp_path: Path) -> None:
    phase_dir = tmp_path / ".gpd" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    verification_path = phase_dir / "01-VERIFICATION.md"
    verification_path.write_text(
        _verification_with_contract_results()
        .replace("      status: rejected\n", "      status: unresolved\n", 1),
        encoding="utf-8",
    )

    result = validate_frontmatter(
        verification_path.read_text(encoding="utf-8"),
        "verification",
        source_path=verification_path,
    )

    assert result.valid is False
    assert "status: passed is inconsistent with unresolved forbidden_proxies: fp-benchmark" in result.errors


def test_validate_frontmatter_verification_rejects_non_canonical_status(tmp_path: Path) -> None:
    phase_dir = tmp_path / ".gpd" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    (phase_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    verification_path = phase_dir / "01-VERIFICATION.md"
    verification_path.write_text(
        _verification_with_contract_results().replace("status: passed\n", "status: validating\n", 1),
        encoding="utf-8",
    )

    result = validate_frontmatter(
        verification_path.read_text(encoding="utf-8"),
        "verification",
        source_path=verification_path,
    )

    assert result.valid is False
    assert "status: must be one of passed, gaps_found, expert_needed, human_needed" in result.errors


def test_verify_summary_requires_must_surface_reference_actions(tmp_path: Path) -> None:
    phase_dir = tmp_path / ".gpd" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    plan_path = phase_dir / "01-01-PLAN.md"
    plan_path.write_text((FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"), encoding="utf-8")
    summary_content = (FIXTURES_STAGE4 / "summary_with_contract_results.md").read_text(encoding="utf-8").replace(
        "completed_actions: [read, compare, cite]",
        "completed_actions: [read]",
        1,
    ).replace(
        "status: completed",
        "status: missing",
        1,
    ).replace(
        "missing_actions: []",
        "missing_actions: [compare, cite]",
        1,
    )
    summary_path = phase_dir / "01-01-SUMMARY.md"
    summary_path.write_text(summary_content, encoding="utf-8")

    result = verify_summary(tmp_path, summary_path)

    assert result.passed is False
    assert any("Reference ref-benchmark missing required_actions in summary" in error for error in result.errors)


def test_verify_summary_requires_decisive_comparison_verdict_when_comparison_was_attempted(tmp_path: Path) -> None:
    phase_dir = tmp_path / ".gpd" / "phases" / "01-benchmark"
    phase_dir.mkdir(parents=True)
    plan_path = phase_dir / "01-01-PLAN.md"
    plan_path.write_text((FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"), encoding="utf-8")
    original = (FIXTURES_STAGE4 / "summary_with_contract_results.md").read_text(encoding="utf-8")
    frontmatter, body = original.split("---\n\n", 1)
    trimmed_frontmatter = frontmatter.split("\ncomparison_verdicts:\n", 1)[0] + "\n---\n"
    summary_content = trimmed_frontmatter + "\n" + body
    summary_path = phase_dir / "01-01-SUMMARY.md"
    summary_path.write_text(summary_content, encoding="utf-8")

    result = verify_summary(tmp_path, summary_path)

    assert result.passed is False
    assert any("Missing decisive comparison_verdict" in error for error in result.errors)
