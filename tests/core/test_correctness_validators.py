from __future__ import annotations

from pathlib import Path
from textwrap import dedent

from typer.testing import CliRunner

from gpd.cli import app
from gpd.core.correctness_validators import (
    validate_comparison_contract,
    validate_verification_oracle_evidence,
)

runner = CliRunner()


def _verification_report(body: str) -> str:
    return f"---\nphase: 01-demo\nverified: 2026-04-29T00:00:00Z\nstatus: passed\nscore: 1/1\n---\n\n{body}"


def _valid_oracle_body() -> str:
    return dedent(
        """\
        # Verification

        ## Computational Verification Details

        ```python
        value = 2 + 2
        print(value)
        ```

        **Output:**

        ```output
        4
        ```

        Verdict: PASS. The independent arithmetic check matches the expected value.
        """
    )


def _valid_comparison_artifact() -> str:
    return dedent(
        """\
        ---
        comparison_kind: cross_method
        comparison_sources:
          - label: analytic
            kind: derivation
            path: GPD/phases/01-demo/01-SUMMARY.md
          - label: numeric
            kind: verification
            path: GPD/phases/01-demo/01-VERIFICATION.md
        comparison_verdicts:
          - subject_id: test-cross-check
            subject_kind: acceptance_test
            subject_role: decisive
            comparison_kind: cross_method
            metric: relative_error
            threshold: "<= 0.01"
            verdict: pass
        ---

        # Internal Comparison
        """
    )


def test_verification_oracle_validator_requires_code_output_and_verdict() -> None:
    result = validate_verification_oracle_evidence(
        _verification_report(
            dedent(
                """\
                # Verification

                The expression was checked by inspection and should pass.
                """
            )
        )
    )

    assert result.valid is False
    assert result.evidence_count == 0
    assert "computational_oracle" in result.errors[0]


def test_verification_oracle_validator_accepts_executed_output_block() -> None:
    result = validate_verification_oracle_evidence(_verification_report(_valid_oracle_body()))

    assert result.valid is True
    assert result.evidence_count == 1
    assert result.errors == []


def test_verification_oracle_validator_requires_explicit_verdict_after_output() -> None:
    result = validate_verification_oracle_evidence(
        _verification_report(
            dedent(
                """\
                # Verification

                ```python
                print("PASS")
                ```

                **Output:**

                ```output
                PASS
                ```
                """
            )
        )
    )

    assert result.valid is False
    assert result.evidence_count == 0
    assert "PASS/FAIL/INCONCLUSIVE verdict" in result.errors[0]


def test_validate_verification_contract_cli_rejects_missing_oracle(tmp_path: Path) -> None:
    report = tmp_path / "01-VERIFICATION.md"
    report.write_text(_verification_report("# Verification\n\nNo executable check.\n"), encoding="utf-8")

    result = runner.invoke(app, ["--raw", "validate", "verification-contract", str(report)])

    assert result.exit_code == 1, result.output
    assert "computational_oracle" in result.output


def test_validate_verification_contract_cli_accepts_oracle(tmp_path: Path) -> None:
    report = tmp_path / "01-VERIFICATION.md"
    report.write_text(_verification_report(_valid_oracle_body()), encoding="utf-8")

    result = runner.invoke(app, ["--raw", "validate", "verification-contract", str(report)])

    assert result.exit_code == 0, result.output
    assert '"oracle_evidence_count": 1' in result.output


def test_comparison_contract_validator_accepts_strict_verdict_ledger(tmp_path: Path) -> None:
    comparison_path = tmp_path / "GPD" / "comparisons" / "demo-COMPARISON.md"
    comparison_path.parent.mkdir(parents=True)
    content = _valid_comparison_artifact()

    result = validate_comparison_contract(content, source_path=comparison_path)

    assert result.valid is True
    assert result.verdict_count == 1
    assert result.errors == []


def test_validate_comparison_contract_cli_rejects_malformed_verdict(tmp_path: Path) -> None:
    comparison_path = tmp_path / "GPD" / "comparisons" / "demo-COMPARISON.md"
    comparison_path.parent.mkdir(parents=True)
    comparison_path.write_text(
        _valid_comparison_artifact().replace("    verdict: pass\n", "    verdict: pass\n    extra: no\n"),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["--raw", "validate", "comparison-contract", str(comparison_path)])

    assert result.exit_code == 1, result.output
    assert "comparison_verdicts" in result.output
    assert "Extra inputs are not permitted" in result.output


def test_validate_comparison_contract_cli_requires_verdicts(tmp_path: Path) -> None:
    comparison_path = tmp_path / "GPD" / "comparisons" / "demo-COMPARISON.md"
    comparison_path.parent.mkdir(parents=True)
    comparison_path.write_text(
        dedent(
            """\
            ---
            comparison_kind: cross_method
            comparison_sources:
              - label: analytic
                kind: derivation
                path: GPD/phases/01-demo/01-SUMMARY.md
            ---

            # Internal Comparison
            """
        ),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["--raw", "validate", "comparison-contract", str(comparison_path)])

    assert result.exit_code == 1, result.output
    assert "comparison_verdicts: required" in result.output
