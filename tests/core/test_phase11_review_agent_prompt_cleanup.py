from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO_ROOT / "src" / "gpd" / "agents"


def _read_agent(name: str) -> str:
    return (AGENTS_DIR / name).read_text(encoding="utf-8")


def _gpd_return_block(source: str) -> str:
    return source.split("gpd_return:\n", 1)[1].split("```", 1)[0]


def _top_level_keys(block: str) -> list[str]:
    return [
        line.strip().split(":", 1)[0]
        for line in block.splitlines()
        if line.startswith("  ") and not line.startswith("    ") and ":" in line and not line.lstrip().startswith("#")
    ]


def _extension_keys(block: str) -> list[str]:
    extension_keys: list[str] = []
    in_extensions = False
    for line in block.splitlines():
        if line.startswith("  ") and not line.startswith("    "):
            in_extensions = line.strip() == "extensions:"
            continue
        if in_extensions and line.startswith("    ") and ":" in line and not line.lstrip().startswith("#"):
            extension_keys.append(line.strip().split(":", 1)[0])
    return extension_keys


def test_referee_routes_on_status_and_shows_base_return_fields_first() -> None:
    source = _read_agent("gpd-referee.md")
    envelope = _gpd_return_block(source)

    assert (
        "The markdown headings `## REVIEW COMPLETE`, `## REVIEW INCOMPLETE`, and `## CHECKPOINT REACHED` are human-readable labels only."
        in source
    )
    assert "Route on `gpd_return.status` and the written review artifacts, not on heading text." in source

    status_idx = envelope.index("  status: completed | checkpoint | blocked | failed")
    files_idx = envelope.index("  files_written:")
    issues_idx = envelope.index("  issues: [list of blocking or unresolved review issues, if any]")
    next_actions_idx = envelope.index("  next_actions: [list of recommended follow-up actions]")
    recommendation_idx = envelope.index('    recommendation: "{accept | minor_revision | major_revision | reject}"')

    assert status_idx < files_idx < issues_idx < next_actions_idx < recommendation_idx
    assert _top_level_keys(envelope) == ["status", "files_written", "issues", "next_actions", "extensions"]
    assert _extension_keys(envelope)[:2] == ["recommendation", "confidence"]
    assert "recommendation" not in _top_level_keys(envelope)
    assert "confidence" not in _top_level_keys(envelope)


def test_project_researcher_uses_presentation_only_heading_mapping_and_base_fields_first() -> None:
    source = _read_agent("gpd-project-researcher.md")
    envelope = _gpd_return_block(source)

    assert "gpd_return:" in source
    assert "status: completed | checkpoint | blocked | failed" in source
    assert "files_written: [GPD/literature/SUMMARY.md, GPD/literature/METHODS.md, ...]" in source
    assert "issues: [list of issues encountered, if any]" in source
    assert "next_actions: [list of recommended follow-up actions]" in source
    assert "confidence: HIGH | MEDIUM | LOW" in source
    assert "Mapping: RESEARCH COMPLETE → completed, RESEARCH BLOCKED → blocked" not in source
    assert "Headings above are presentation only; route on gpd_return.status." in source

    status_idx = envelope.index("  status: completed | checkpoint | blocked | failed")
    files_idx = envelope.index("  files_written: [GPD/literature/SUMMARY.md, GPD/literature/METHODS.md, ...]")
    issues_idx = envelope.index("  issues: [list of issues encountered, if any]")
    next_actions_idx = envelope.index("  next_actions: [list of recommended follow-up actions]")
    confidence_idx = envelope.index("    confidence: HIGH | MEDIUM | LOW")

    assert status_idx < files_idx < issues_idx < next_actions_idx < confidence_idx
    assert _top_level_keys(envelope) == ["status", "files_written", "issues", "next_actions", "extensions"]
    assert _extension_keys(envelope) == ["confidence"]
    assert "confidence" not in _top_level_keys(envelope)


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

    status_idx = source.index("  status: completed | checkpoint | blocked | failed")
    files_idx = source.index("  files_written: []")
    issues_idx = source.index("  issues: [issue objects from Issue Format above]")
    next_actions_idx = source.index("  next_actions: [list of recommended follow-up actions]")
    approved_idx = source.index("  approved_plans: [list of plan IDs that passed]")

    assert status_idx < files_idx < issues_idx < next_actions_idx < approved_idx
    assert "contract_gate_summary:" not in source
    assert "issues_found:" not in source
    assert "escalation: null | {pattern, options}" not in source
    assert "# Mapping: all_approved" not in source
