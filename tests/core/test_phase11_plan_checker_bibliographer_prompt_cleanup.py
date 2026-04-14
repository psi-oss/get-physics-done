"""Focused regressions for Phase 11 plan-checker and bibliographer prompt cleanup."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PLAN_CHECKER = REPO_ROOT / "src/gpd/agents/gpd-plan-checker.md"
BIBLIOGRAPHER = REPO_ROOT / "src/gpd/agents/gpd-bibliographer.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


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


def test_plan_checker_prompt_uses_typed_status_and_concise_presentation_language() -> None:
    source = _read(PLAN_CHECKER)
    envelope = _gpd_return_block(source)
    top_level_keys = _top_level_keys(envelope)
    extension_keys = _extension_keys(envelope)

    assert "This is a one-shot handoff. If user input is needed, return `status: checkpoint`; do not wait inside the same run." in source
    assert "artifact_write_authority: read_only" in source
    assert "file_write" not in source
    assert "Headings above are presentation only. Route on `gpd_return.status`, the approved/blocked plan lists, and `issues`." in source
    assert "Headings above are presentation only; route on gpd_return.status." not in source
    assert "status: completed | checkpoint | blocked | failed" in envelope
    assert "files_written: []" in envelope
    assert "issues: [issue objects from Issue Format above]" in envelope
    assert "next_actions: [list of recommended follow-up actions]" in envelope
    assert "approved_plans: [list of plan IDs that passed]" in envelope
    assert "blocked_plans: [list of plan IDs needing revision or escalation]" in envelope
    assert top_level_keys[:4] == ["status", "files_written", "issues", "next_actions"]
    assert {"approved_plans", "blocked_plans"}.issubset(set(top_level_keys) | set(extension_keys))
    assert ("approved_plans" in top_level_keys) == ("blocked_plans" in top_level_keys)
    assert ("approved_plans" in extension_keys) == ("blocked_plans" in extension_keys)
    assert not ({"approved_plans", "blocked_plans"}.issubset(top_level_keys) and {"approved_plans", "blocked_plans"}.issubset(extension_keys))
    assert not ({"dimensions_checked", "revision_round", "revision_guidance"}.issubset(top_level_keys) and {"dimensions_checked", "revision_round", "revision_guidance"}.issubset(extension_keys))


def test_bibliographer_prompt_uses_typed_checkpoint_language_and_shorter_heading_note() -> None:
    source = _read(BIBLIOGRAPHER)
    envelope = _gpd_return_block(source)

    assert "Use `gpd_return.status: checkpoint` as the control surface. The `## CHECKPOINT REACHED` heading below is presentation only." in source
    assert (
        "The headings in this section are presentation only. Route on `gpd_return.status`. Use `status: completed` when the bibliography task finished, even if the human-readable heading is `## CITATION ISSUES FOUND`; use `status: checkpoint` only when researcher input is required to continue."
        in source
    )
    assert "The markdown headings in this section, including `## BIBLIOGRAPHY UPDATED`, `## CITATION ISSUES FOUND`, and `## CHECKPOINT REACHED`, are presentation only." not in source
    assert "status: completed | checkpoint | blocked | failed" in envelope
    assert "files_written: [references/references.bib, GPD/references-status.json]" in envelope
    assert "issues: [list of citation problems, if any]" in envelope
    assert "next_actions: [list of recommended follow-up actions]" in envelope
    assert "entries_added: N" in envelope
    assert "{GPD_INSTALL_DIR}/references/publication/publication-pipeline-modes.md" in source
    assert "@{GPD_INSTALL_DIR}/references/publication/publication-pipeline-modes.md" not in source
    assert _top_level_keys(envelope) == ["status", "files_written", "issues", "next_actions", "extensions"]
    assert _extension_keys(envelope) == ["entries_added"]
    assert "entries_added" not in _top_level_keys(envelope)
