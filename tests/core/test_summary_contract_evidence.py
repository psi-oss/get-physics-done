from __future__ import annotations

from pathlib import Path

import pytest

from gpd.core.commands import cmd_summary_extract
from gpd.core.errors import ValidationError

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "stage4"


def test_summary_extract_parses_contract_results_and_comparison_verdicts(tmp_path: Path) -> None:
    summary_path = tmp_path / "01-SUMMARY.md"
    summary_path.write_text((FIXTURES_DIR / "summary_with_contract_results.md").read_text(encoding="utf-8"), encoding="utf-8")

    result = cmd_summary_extract(tmp_path, "01-SUMMARY.md")

    assert result.key_files == ["figures/benchmark.png", "src/benchmark.py"]
    assert result.key_files_created == ["figures/benchmark.png"]
    assert result.key_files_modified == ["src/benchmark.py"]
    assert result.plan_contract_ref == ".gpd/phases/01-benchmark/01-01-PLAN.md#/contract"
    assert result.contract_results is not None
    assert result.contract_results.claims["claim-benchmark"].status == "passed"
    assert result.contract_results.references["ref-benchmark"].completed_actions == ["read", "compare", "cite"]
    assert result.comparison_verdicts[0].subject_id == "claim-benchmark"
    assert result.comparison_verdicts[0].verdict == "pass"


def test_summary_extract_field_filter_returns_contract_results(tmp_path: Path) -> None:
    summary_path = tmp_path / "01-SUMMARY.md"
    summary_path.write_text((FIXTURES_DIR / "summary_with_contract_results.md").read_text(encoding="utf-8"), encoding="utf-8")

    result = cmd_summary_extract(tmp_path, "01-SUMMARY.md", fields=["contract_results", "comparison_verdicts"])

    assert isinstance(result, dict)
    assert result["contract_results"]["claims"]["claim-benchmark"]["status"] == "passed"
    assert result["comparison_verdicts"][0]["subject_role"] == "decisive"


def test_summary_extract_normalizes_empty_contract_results_section_lists(tmp_path: Path) -> None:
    summary_path = tmp_path / "broken-SUMMARY.md"
    summary_path.write_text(
        "---\nphase: 01\nplan: 01\ndepth: full\nprovides: []\ncompleted: 2026-03-13\ncontract_results:\n  claims: []\n---\n\n# Summary\n",
        encoding="utf-8",
    )

    result = cmd_summary_extract(tmp_path, "broken-SUMMARY.md")

    assert result.contract_results is not None
    assert result.contract_results.claims == {}


def test_summary_extract_rejects_non_list_comparison_verdicts(tmp_path: Path) -> None:
    summary_path = tmp_path / "broken-SUMMARY.md"
    summary_path.write_text(
        "---\n"
        "phase: 01\n"
        "plan: 01\n"
        "depth: full\n"
        "provides: []\n"
        "completed: 2026-03-13\n"
        "comparison_verdicts:\n"
        "  claim-benchmark:\n"
        "    verdict: pass\n"
        "---\n\n"
        "# Summary\n",
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="expected a list"):
        cmd_summary_extract(tmp_path, "broken-SUMMARY.md")
