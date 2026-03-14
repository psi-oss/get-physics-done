from __future__ import annotations

from pathlib import Path

from gpd import registry

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_DIR = REPO_ROOT / "src/gpd/commands"
TEMPLATES_DIR = REPO_ROOT / "src/gpd/specs/templates"


def _read_command(name: str) -> str:
    return (COMMANDS_DIR / f"{name}.md").read_text(encoding="utf-8")


def test_review_grade_commands_surface_registry_contract_requirements_in_source() -> None:
    command_names = ("write-paper", "respond-to-referees", "verify-work", "arxiv-submission")

    for command_name in command_names:
        source = _read_command(command_name)
        contract = registry.get_command(command_name).review_contract

        assert contract is not None
        assert "review-contract:" in source
        assert f"review_mode: {contract.review_mode}" in source

        for output in contract.required_outputs:
            assert output in source
        for evidence in contract.required_evidence:
            assert evidence in source
        for blocker in contract.blocking_conditions:
            assert blocker in source
        for check in contract.preflight_checks:
            assert check in source

        if contract.required_state:
            assert f"required_state: {contract.required_state}" in source


def test_verify_work_review_contract_uses_phase_scoped_output_path() -> None:
    contract = registry.get_command("verify-work").review_contract

    assert contract is not None
    assert contract.required_outputs == [".gpd/phases/XX-name/{phase}-VERIFICATION.md"]
    assert ".gpd/phases/XX-name/{phase}-VERIFICATION.md" in _read_command("verify-work")


def test_summary_template_surfaces_plan_contract_ref_rule_for_contract_ledgers() -> None:
    summary_template = (TEMPLATES_DIR / "summary.md").read_text(encoding="utf-8")

    assert "If `contract_results` or `comparison_verdicts` are present, `plan_contract_ref` is also required." in summary_template
    assert "plan_contract_ref (required when `contract_results` or `comparison_verdicts` are present)" in summary_template
    assert "For contract-backed summaries, `contract_results` is required" in summary_template


def test_write_paper_prompt_discovers_plan_scoped_and_legacy_phase_summaries() -> None:
    source = _read_command("write-paper")

    assert "ls .gpd/phases/*/SUMMARY.md .gpd/phases/*/*-SUMMARY.md 2>/dev/null" in source


def test_comparison_templates_match_full_comparison_verdict_subject_kind_enum() -> None:
    expected = "subject_kind: claim|deliverable|acceptance_test|reference|artifact|other"
    internal = (TEMPLATES_DIR / "paper" / "internal-comparison.md").read_text(encoding="utf-8")
    experimental = (TEMPLATES_DIR / "paper" / "experimental-comparison.md").read_text(encoding="utf-8")

    assert expected in internal
    assert expected in experimental
