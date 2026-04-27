from __future__ import annotations

from pathlib import Path

from tests.prompt_metrics_support import count_unfenced_heading

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO_ROOT / "src" / "gpd" / "agents"


def _read_agent(name: str) -> str:
    return (AGENTS_DIR / name).read_text(encoding="utf-8")


def test_referee_routes_on_status_and_shows_base_return_fields_first() -> None:
    source = _read_agent("gpd-referee.md")

    assert (
        "The markdown headings `## REVIEW COMPLETE`, `## REVIEW INCOMPLETE`, and `## CHECKPOINT REACHED` are human-readable labels only."
        in source
    )
    assert "Route on `gpd_return.status` and the written review artifacts, not on heading text." in source
    assert count_unfenced_heading(source, "## REVIEW COMPLETE") == 0
    assert count_unfenced_heading(source, "## REVIEW INCOMPLETE") == 0
    assert count_unfenced_heading(source, "## CHECKPOINT REACHED") == 0

    base_idx = source.index("# Base fields (`status`, `files_written`, `issues`, `next_actions`) follow agent-infrastructure.md.")
    allowlist_idx = source.index("# files_written must stay within the Stage 6 allowlist")
    recommendation_idx = source.index('  recommendation: "{accept | minor_revision | major_revision | reject}"')

    assert base_idx < allowlist_idx < recommendation_idx


def test_project_researcher_uses_presentation_only_heading_mapping_and_base_fields_first() -> None:
    source = _read_agent("gpd-project-researcher.md")

    assert "gpd_return:" in source
    assert "# Base fields (`status`, `files_written`, `issues`, `next_actions`) follow agent-infrastructure.md." in source
    assert "confidence: HIGH | MEDIUM | LOW" in source
    assert "Mapping: RESEARCH COMPLETE → completed, RESEARCH BLOCKED → blocked" not in source
    assert "Headings above are presentation only; route on gpd_return.status." in source

    base_idx = source.index("  # Base fields (`status`, `files_written`, `issues`, `next_actions`) follow agent-infrastructure.md.")
    confidence_idx = source.index("  confidence: HIGH | MEDIUM | LOW")

    assert base_idx < confidence_idx


def test_plan_checker_uses_typed_status_and_drops_nested_return_payload_examples() -> None:
    source = _read_agent("gpd-plan-checker.md")

    assert (
        "Headings such as `## VERIFICATION PASSED`, `## ISSUES FOUND`, and `## PLAN_BLOCKED — Escalation to User` are presentation only."
        in source
    )
    assert "Route on `gpd_return.status`." in source
    assert "`gpd_return.status: completed`" in source
    assert "`gpd_return.status: checkpoint`" in source
    assert "`gpd_return.status: failed`" in source
    assert "`gpd_return.status: blocked`" in source
    assert count_unfenced_heading(source, "## VERIFICATION PASSED") == 0
    assert count_unfenced_heading(source, "## ISSUES FOUND") == 0

    base_idx = source.index("  # Base fields (`status`, `files_written`, `issues`, `next_actions`) follow agent-infrastructure.md.")
    files_idx = source.index("  # This read-only agent always uses files_written: [].")
    approved_idx = source.index("  approved_plans: [list of plan IDs that passed]")

    assert base_idx < files_idx < approved_idx
    assert "contract_gate_summary:" not in source
    assert "issues_found:" not in source
    assert "escalation: null | {pattern, options}" not in source
    assert "# Mapping: all_approved" not in source
