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
    plan_path = tmp_path / "01-01-PLAN.md"
    plan_path.write_text((FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"), encoding="utf-8")
    summary_content = (FIXTURES_STAGE4 / "summary_with_contract_results.md").read_text(encoding="utf-8").replace(
        "claim-benchmark:",
        "claim-unknown:",
        1,
    )
    summary_path = tmp_path / "01-01-SUMMARY.md"
    summary_path.write_text(summary_content, encoding="utf-8")
    (tmp_path / "figures").mkdir()
    (tmp_path / "figures" / "benchmark.png").write_text("placeholder", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "benchmark.py").write_text("print('ok')\n", encoding="utf-8")

    result = verify_summary(tmp_path, summary_path)

    assert result.passed is False
    assert any("Unknown claim contract_results entry: claim-unknown" in error for error in result.errors)


def test_verify_summary_allows_partial_contract_results_ledgers(tmp_path: Path) -> None:
    plan_path = tmp_path / "01-01-PLAN.md"
    plan_path.write_text((FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"), encoding="utf-8")
    summary_content = (
        (FIXTURES_STAGE4 / "summary_with_contract_results.md")
        .read_text(encoding="utf-8")
        .replace(
            "contract_results:\n"
            "  claims:\n"
            "    claim-benchmark:\n"
            "      status: passed\n"
            "      summary: Benchmark reproduced within tolerance\n"
            "      linked_ids: [deliv-figure, test-benchmark, ref-benchmark]\n"
            "      path: figures/benchmark.png\n"
            "  deliverables:\n"
            "    deliv-figure:\n"
            "      status: passed\n"
            "      summary: Figure generated\n"
            "      path: figures/benchmark.png\n"
            "  acceptance_tests:\n"
            "    test-benchmark:\n"
            "      status: passed\n"
            "      summary: Comparison check passed\n"
            "      linked_ids: [claim-benchmark, ref-benchmark]\n"
            "  references:\n"
            "    ref-benchmark:\n"
            "      status: completed\n"
            "      completed_actions: [read, compare, cite]\n"
            "      missing_actions: []\n"
            "      summary: Read and compared benchmark reference\n"
            "  forbidden_proxies:\n"
            "    fp-benchmark:\n"
            "      status: rejected\n"
            "      notes: Explicit numerical comparison was completed\n",
            "contract_results:\n"
            "  claims:\n"
            "    claim-benchmark:\n"
            "      status: partial\n"
            "      summary: Benchmark comparison is in progress\n"
            "      linked_ids: [deliv-figure, test-benchmark]\n"
            "  acceptance_tests:\n"
            "    test-benchmark:\n"
            "      status: partial\n"
            "      summary: Initial comparison run completed\n"
            "      linked_ids: [claim-benchmark]\n"
            "  references:\n"
            "    ref-benchmark:\n"
            "      status: completed\n"
            "      completed_actions: [read, compare, cite]\n"
            "      missing_actions: []\n"
            "      summary: Read and compared benchmark reference\n",
            1,
        )
    )
    summary_path = tmp_path / "01-01-SUMMARY.md"
    summary_path.write_text(summary_content, encoding="utf-8")
    (tmp_path / "figures").mkdir()
    (tmp_path / "figures" / "benchmark.png").write_text("placeholder", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "benchmark.py").write_text("print('ok')\n", encoding="utf-8")

    result = verify_summary(tmp_path, summary_path)

    assert result.passed is True


def test_verify_summary_requires_must_surface_reference_actions(tmp_path: Path) -> None:
    plan_path = tmp_path / "01-01-PLAN.md"
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
    summary_path = tmp_path / "01-01-SUMMARY.md"
    summary_path.write_text(summary_content, encoding="utf-8")

    result = verify_summary(tmp_path, summary_path)

    assert result.passed is False
    assert any("Reference ref-benchmark missing required_actions in summary" in error for error in result.errors)


def test_verify_summary_requires_decisive_comparison_verdict_when_comparison_was_attempted(tmp_path: Path) -> None:
    plan_path = tmp_path / "01-01-PLAN.md"
    plan_path.write_text((FIXTURES_STAGE0 / "plan_with_contract.md").read_text(encoding="utf-8"), encoding="utf-8")
    original = (FIXTURES_STAGE4 / "summary_with_contract_results.md").read_text(encoding="utf-8")
    frontmatter, body = original.split("---\n\n", 1)
    trimmed_frontmatter = frontmatter.split("\ncomparison_verdicts:\n", 1)[0] + "\n---\n"
    summary_content = trimmed_frontmatter + "\n" + body
    summary_path = tmp_path / "01-01-SUMMARY.md"
    summary_path.write_text(summary_content, encoding="utf-8")

    result = verify_summary(tmp_path, summary_path)

    assert result.passed is False
    assert any("Missing decisive comparison_verdict" in error for error in result.errors)
