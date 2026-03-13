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

    result = verify_summary(tmp_path, summary_path)

    assert result.passed is False
    assert any("Unknown claim contract_results entry: claim-unknown" in error for error in result.errors)


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
