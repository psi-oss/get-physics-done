from __future__ import annotations

from pathlib import Path

from gpd.core.frontmatter import validate_frontmatter, verify_summary

FIXTURES_STAGE0 = Path(__file__).resolve().parents[1] / "fixtures" / "stage0"
FIXTURES_STAGE4 = Path(__file__).resolve().parents[1] / "fixtures" / "stage4"


def test_validate_frontmatter_summary_accepts_contract_results() -> None:
    content = (FIXTURES_STAGE4 / "summary_with_contract_results.md").read_text(encoding="utf-8")

    result = validate_frontmatter(content, "summary")

    assert result.valid is True
    assert result.errors == []


def test_validate_frontmatter_verification_accepts_contract_results() -> None:
    content = (FIXTURES_STAGE4 / "verification_with_contract_results.md").read_text(encoding="utf-8")

    result = validate_frontmatter(content, "verification")

    assert result.valid is True
    assert result.errors == []


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


def test_validate_frontmatter_summary_with_source_path_accepts_sibling_plan_contract_ref(tmp_path: Path) -> None:
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
            "plan_contract_ref: 01-01-PLAN.md#/contract",
            1,
        ),
        encoding="utf-8",
    )

    result = validate_frontmatter(summary_path.read_text(encoding="utf-8"), "summary", source_path=summary_path)

    assert result.valid is True
    assert result.errors == []


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


def test_validate_frontmatter_verification_with_source_path_accepts_sibling_plan_contract_ref(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "01-01-PLAN.md").write_text(
        (FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    verification_path = artifact_dir / "01-VERIFICATION.md"
    verification_path.write_text(
        (FIXTURES_STAGE4 / "verification_with_contract_results.md")
        .read_text(encoding="utf-8")
        .replace(
            "plan_contract_ref: .gpd/phases/01-benchmark/01-01-PLAN.md#/contract",
            "plan_contract_ref: 01-01-PLAN.md#/contract",
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
        (FIXTURES_STAGE4 / "verification_with_contract_results.md")
        .read_text(encoding="utf-8")
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
        (FIXTURES_STAGE4 / "verification_with_contract_results.md")
        .read_text(encoding="utf-8")
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
        (FIXTURES_STAGE4 / "verification_with_contract_results.md")
        .read_text(encoding="utf-8")
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
    assert any("suggested_contract_checks:" in error and "Field required" in error for error in result.errors)


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
        (FIXTURES_STAGE4 / "verification_with_contract_results.md")
        .read_text(encoding="utf-8")
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
    assert "Contract-backed plan requires summary contract_results" in result.errors


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
    assert "Contract-backed plan requires summary plan_contract_ref" in result.errors


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
        (FIXTURES_STAGE4 / "verification_with_contract_results.md")
        .read_text(encoding="utf-8")
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
        (FIXTURES_STAGE4 / "verification_with_contract_results.md")
        .read_text(encoding="utf-8")
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
