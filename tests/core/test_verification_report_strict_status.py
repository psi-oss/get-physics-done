from pathlib import Path

TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "src" / "gpd" / "specs" / "templates"


def test_verification_report_strict_pass_mentions_required_reference_coverage() -> None:
    verification_report = (TEMPLATES_DIR / "verification-report.md").read_text(encoding="utf-8")

    assert "`status: passed` is strict" in verification_report
    assert "every required decisive comparison is decisive" in verification_report
    assert "comparison_verdicts" in verification_report
    assert "structured `suggested_contract_checks`" in verification_report
    assert "Proof-backed claims follow the proof-audit rules in the canonical schema" in verification_report
    assert "If decisive work remains open, use `partial`, `gaps_found`, `expert_needed`, or `human_needed`" in verification_report
