from __future__ import annotations

from pathlib import Path

import pytest

from gpd.core.commands import cmd_summary_extract
from gpd.core.errors import ValidationError

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "stage4"
PLAN_FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "stage0"


def _summary_with_reference_usage(*, status: str, completed_actions: str, missing_actions: str) -> str:
    return (
        (FIXTURES_DIR / "summary_with_contract_results.md")
        .read_text(encoding="utf-8")
        .replace("status: completed", f"status: {status}", 1)
        .replace("completed_actions: [read, compare, cite]", f"completed_actions: {completed_actions}", 1)
        .replace("missing_actions: []", f"missing_actions: {missing_actions}", 1)
    )


def _write_matching_plan_contract(tmp_path: Path, *, required_actions: list[str] | None = None) -> None:
    plan_path = tmp_path / "GPD" / "phases" / "01-benchmark" / "01-01-PLAN.md"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_text = (PLAN_FIXTURES_DIR / "plan_with_contract.md").read_text(encoding="utf-8")
    if required_actions is not None:
        plan_text = plan_text.replace(
            "required_actions: [read, compare, cite]",
            "required_actions: [" + ", ".join(required_actions) + "]",
            1,
        )
    plan_path.write_text(plan_text, encoding="utf-8")


def _write_contract_backed_summary(
    tmp_path: Path,
    summary_text: str,
    *,
    filename: str = "01-SUMMARY.md",
    required_actions: list[str] | None = None,
) -> Path:
    _write_matching_plan_contract(tmp_path, required_actions=required_actions)
    summary_path = tmp_path / filename
    summary_path.write_text(summary_text, encoding="utf-8")
    return summary_path


def test_summary_extract_parses_contract_results_and_comparison_verdicts(tmp_path: Path) -> None:
    _write_contract_backed_summary(tmp_path, (FIXTURES_DIR / "summary_with_contract_results.md").read_text(encoding="utf-8"))

    result = cmd_summary_extract(tmp_path, "01-SUMMARY.md")

    assert result.key_files == ["figures/benchmark.png", "src/benchmark.py"]
    assert result.key_files_created == ["figures/benchmark.png"]
    assert result.key_files_modified == ["src/benchmark.py"]
    assert result.plan_contract_ref == "GPD/phases/01-benchmark/01-01-PLAN.md#/contract"
    assert result.contract_results is not None
    assert result.contract_results.claims["claim-benchmark"].status == "passed"
    assert result.contract_results.references["ref-benchmark"].completed_actions == ["read", "compare", "cite"]
    assert result.comparison_verdicts[0].subject_id == "claim-benchmark"
    assert result.comparison_verdicts[0].verdict == "pass"


def test_summary_extract_field_filter_returns_contract_results(tmp_path: Path) -> None:
    _write_contract_backed_summary(tmp_path, (FIXTURES_DIR / "summary_with_contract_results.md").read_text(encoding="utf-8"))

    result = cmd_summary_extract(tmp_path, "01-SUMMARY.md", fields=["contract_results", "comparison_verdicts"])

    assert isinstance(result, dict)
    assert result["contract_results"]["claims"]["claim-benchmark"]["status"] == "passed"
    assert result["comparison_verdicts"][0]["subject_role"] == "decisive"


@pytest.mark.parametrize("placeholder", ["[]", "null"])
def test_summary_extract_rejects_placeholder_contract_results_section_shapes(
    tmp_path: Path,
    placeholder: str,
) -> None:
    summary_text = (FIXTURES_DIR / "summary_with_contract_results.md").read_text(encoding="utf-8")
    summary_text = summary_text.replace(
        "  claims:\n"
        "    claim-benchmark:\n"
        "      status: passed\n"
        "      summary: Benchmark claim verified against the decisive anchor.\n"
        "      linked_ids: [deliv-figure, test-benchmark, ref-benchmark]\n"
        "      evidence:\n"
        "        - verifier: gpd-verifier\n"
        "          method: benchmark reproduction\n"
        "          confidence: high\n"
        "          claim_id: claim-benchmark\n"
        "          deliverable_id: deliv-figure\n"
        "          acceptance_test_id: test-benchmark\n"
        "          reference_id: ref-benchmark\n"
        "          evidence_path: GPD/phases/01-benchmark/01-VERIFICATION.md\n",
        f"  claims: {placeholder}\n",
        1,
    )
    _write_contract_backed_summary(tmp_path, summary_text, filename="broken-SUMMARY.md")

    with pytest.raises(ValidationError, match="claims"):
        cmd_summary_extract(tmp_path, "broken-SUMMARY.md")


def test_summary_extract_requires_explicit_uncertainty_markers(tmp_path: Path) -> None:
    summary_text = (FIXTURES_DIR / "summary_with_contract_results.md").read_text(encoding="utf-8").replace(
        "  uncertainty_markers:\n"
        "    weakest_anchors: [Reference tolerance interpretation]\n"
        "    disconfirming_observations: [Benchmark agreement disappears once normalization is fixed]\n",
        "",
        1,
    )
    _write_contract_backed_summary(tmp_path, summary_text, filename="broken-SUMMARY.md")

    with pytest.raises(ValidationError, match="uncertainty_markers"):
        cmd_summary_extract(tmp_path, "broken-SUMMARY.md")


def test_summary_extract_normalizes_reference_action_ledgers(tmp_path: Path) -> None:
    _write_contract_backed_summary(
        tmp_path,
        _summary_with_reference_usage(
            status="completed",
            completed_actions='[" read ", compare, cite, " ", cite]',
            missing_actions="[]",
        ),
        required_actions=["read"],
    )

    result = cmd_summary_extract(tmp_path, "01-SUMMARY.md")

    assert result.contract_results is not None
    assert result.contract_results.references["ref-benchmark"].completed_actions == ["read", "compare", "cite"]
    assert result.contract_results.references["ref-benchmark"].missing_actions == []


def test_summary_extract_rejects_scalar_reference_action_ledgers_for_contract_backed_summary(
    tmp_path: Path,
) -> None:
    _write_contract_backed_summary(
        tmp_path,
        _summary_with_reference_usage(
            status="Completed",
            completed_actions="Read",
            missing_actions="[]",
        ),
        required_actions=["read"],
    )

    with pytest.raises(ValidationError) as excinfo:
        cmd_summary_extract(tmp_path, "01-SUMMARY.md")

    message = str(excinfo.value)
    assert "completed_actions must be a list, not str" in message


@pytest.mark.parametrize(
    ("status", "completed_actions", "missing_actions", "expected_completed", "expected_missing"),
    [
        ("completed", '[" read ", READ, "read"]', "[]", ["read"], []),
    ],
)
def test_summary_extract_normalizes_case_variant_reference_action_ledgers(
    tmp_path: Path,
    status: str,
    completed_actions: str,
    missing_actions: str,
    expected_completed: list[str],
    expected_missing: list[str],
) -> None:
    _write_contract_backed_summary(
        tmp_path,
        _summary_with_reference_usage(
            status=status,
            completed_actions=completed_actions,
            missing_actions=missing_actions,
        ),
        required_actions=["read"],
    )

    result = cmd_summary_extract(tmp_path, "01-SUMMARY.md")

    assert result.contract_results is not None
    assert result.contract_results.references["ref-benchmark"].status == status.casefold()
    assert result.contract_results.references["ref-benchmark"].completed_actions == expected_completed
    assert result.contract_results.references["ref-benchmark"].missing_actions == expected_missing


@pytest.mark.parametrize(
    ("status", "completed_actions", "missing_actions", "message"),
    [
        ("completed", "[]", "[]", "status=completed requires completed_actions"),
        ("completed", "[read]", "[compare]", "status=completed requires missing_actions to be empty"),
        ("missing", "[read]", "[]", "status=missing requires missing_actions"),
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
def test_summary_extract_rejects_contradictory_reference_action_ledgers(
    tmp_path: Path,
    status: str,
    completed_actions: str,
    missing_actions: str,
    message: str,
) -> None:
    _write_contract_backed_summary(
        tmp_path,
        _summary_with_reference_usage(
            status=status,
            completed_actions=completed_actions,
            missing_actions=missing_actions,
        ),
        required_actions=["read"],
    )

    with pytest.raises(ValidationError) as excinfo:
        cmd_summary_extract(tmp_path, "01-SUMMARY.md")

    assert message in str(excinfo.value)


def test_summary_extract_rejects_unresolved_plan_contract_ref(tmp_path: Path) -> None:
    summary_path = tmp_path / "01-SUMMARY.md"
    summary_path.write_text((FIXTURES_DIR / "summary_with_contract_results.md").read_text(encoding="utf-8"), encoding="utf-8")

    with pytest.raises(ValidationError, match="could not resolve matching plan contract"):
        cmd_summary_extract(tmp_path, "01-SUMMARY.md")


def test_summary_extract_rejects_unknown_contract_ids(tmp_path: Path) -> None:
    summary_text = (FIXTURES_DIR / "summary_with_contract_results.md").read_text(encoding="utf-8").replace(
        "claim-benchmark",
        "claim-unknown",
        1,
    )
    _write_contract_backed_summary(tmp_path, summary_text)

    with pytest.raises(ValidationError, match="Unknown claim contract_results entry: claim-unknown"):
        cmd_summary_extract(tmp_path, "01-SUMMARY.md")


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


def test_summary_extract_rejects_missing_required_summary_fields_without_contract_metadata(tmp_path: Path) -> None:
    summary_path = tmp_path / "broken-SUMMARY.md"
    summary_path.write_text(
        "---\n"
        "phase: 01\n"
        "plan: 01\n"
        "provides: []\n"
        "completed: 2026-03-22\n"
        "---\n\n"
        "# Summary\n",
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match=r"Invalid summary frontmatter.*depth"):
        cmd_summary_extract(tmp_path, "broken-SUMMARY.md")


def test_summary_extract_rejects_unsupported_legacy_summary_fields_without_contract_metadata(tmp_path: Path) -> None:
    summary_path = tmp_path / "broken-SUMMARY.md"
    summary_path.write_text(
        "---\n"
        "phase: 01\n"
        "plan: 01\n"
        "depth: standard\n"
        "provides: []\n"
        "completed: 2026-03-22\n"
        "verification_inputs:\n"
        "  truths: []\n"
        "---\n\n"
        "# Summary\n",
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match=r"verification_inputs"):
        cmd_summary_extract(tmp_path, "broken-SUMMARY.md")
