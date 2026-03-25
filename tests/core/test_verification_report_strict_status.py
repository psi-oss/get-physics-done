from pathlib import Path

TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "src" / "gpd" / "specs" / "templates"


def test_verification_report_strict_pass_mentions_required_reference_coverage() -> None:
    verification_report = (TEMPLATES_DIR / "verification-report.md").read_text(encoding="utf-8")

    assert "`status: passed` is strict" in verification_report
    assert "every reference entry is `completed`" in verification_report
    assert "every `must_surface` reference has all `required_actions` recorded in `completed_actions`" in verification_report
    assert "every forbidden_proxy is `rejected` or `not_applicable`" in verification_report
    assert "If any contract target is `partial`, `failed`, `blocked`, `missing`, or `unresolved`, use `gaps_found`, `expert_needed`, or `human_needed` instead of `passed`." in verification_report
