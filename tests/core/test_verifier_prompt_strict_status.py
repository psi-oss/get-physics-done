from pathlib import Path

AGENTS_DIR = Path(__file__).resolve().parents[2] / "src" / "gpd" / "agents"


def test_verifier_prompt_strict_pass_matches_verification_report_reference_rules() -> None:
    verifier_prompt = (AGENTS_DIR / "gpd-verifier.md").read_text(encoding="utf-8")

    assert "**Status: passed** -- All decisive contract targets VERIFIED" in verifier_prompt
    assert "every reference entry is `completed`" in verifier_prompt
    assert "every `must_surface` reference has all `required_actions` recorded in `completed_actions`" in verifier_prompt
    assert "linked_ids: [deliverable-id, acceptance-test-id, reference-id]" in verifier_prompt
    assert "evidence:\n        - verifier: gpd-verifier" in verifier_prompt
    assert "required comparison verdicts acceptable" in verifier_prompt
    assert "required references handled" not in verifier_prompt
