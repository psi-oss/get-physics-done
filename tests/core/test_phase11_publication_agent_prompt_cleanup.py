"""Focused assertions for the Phase 11 publication-agent prompt cleanup."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PAPER_WRITER = REPO_ROOT / "src/gpd/agents/gpd-paper-writer.md"
BIBLIOGRAPHER = REPO_ROOT / "src/gpd/agents/gpd-bibliographer.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _gpd_return_block(path: Path) -> str:
    source = _read(path)
    return source.split("gpd_return:\n", 1)[1].split("```", 1)[0]


def test_paper_writer_prompt_uses_typed_status_and_one_shot_checkpoint_language() -> None:
    source = _read(PAPER_WRITER)

    assert "return `gpd_return.status: checkpoint` and stop" in source
    assert "This is a one-shot checkpoint handoff." in source
    assert "do not wait for user input inside the current run" not in source
    assert "Use `gpd_return.status: checkpoint` as the control surface." in source
    assert "The `## CHECKPOINT REACHED` heading below is presentation only." in source
    assert (
        "The markdown headings in this section, including `## SECTION DRAFTED`, `## CHECKPOINT REACHED`, and `## WRITING BLOCKED`, are presentation only."
        in source
    )
    assert "return with CHECKPOINT status" not in source
    assert "Return WRITING BLOCKED." not in source


def test_paper_writer_return_example_defers_base_fields_and_keeps_extensions() -> None:
    source = _read(PAPER_WRITER)
    envelope = _gpd_return_block(PAPER_WRITER)

    assert "Report section outputs against the resolved manuscript root rather than a hardcoded `paper/` subtree." in source
    assert (
        "Use the actual resolved manuscript-root path in `files_written`, for example `paper/results.tex` or `GPD/publication/{subject_slug}/manuscript/results.tex`."
        in source
    )
    assert "# Base fields (`status`, `files_written`, `issues`, `next_actions`) follow agent-infrastructure.md." in envelope
    assert "# files_written uses the actual resolved manuscript-root path." in envelope
    assert 'section_name: "{section drafted}"' in envelope
    assert envelope.index(
        "# Base fields (`status`, `files_written`, `issues`, `next_actions`) follow agent-infrastructure.md."
    ) < envelope.index(
        "# files_written uses the actual resolved manuscript-root path."
    )
    assert envelope.index("# files_written uses the actual resolved manuscript-root path.") < envelope.index(
        'section_name: "{section drafted}"'
    )


def test_bibliographer_prompt_uses_typed_status_and_deferred_base_fields() -> None:
    source = _read(BIBLIOGRAPHER)
    envelope = _gpd_return_block(BIBLIOGRAPHER)

    assert "This is a one-shot checkpoint handoff: do not wait for user input inside the current run." in source
    assert "Use `gpd_return.status: checkpoint` as the control surface." in source
    assert "The `## CHECKPOINT REACHED` heading below is presentation only." in source
    assert (
        "Return `gpd_return.status: completed`; use a `## BIBLIOGRAPHY UPDATED` or `## CITATION ISSUES FOUND` heading only as a human-readable presentation choice."
        in source
    )
    assert (
        "Use `status: completed` when the bibliography task finished, even if the human-readable heading is `## CITATION ISSUES FOUND`"
        in source
    )
    assert "Return BIBLIOGRAPHY UPDATED or CITATION ISSUES FOUND" not in source
    assert "# Base fields (`status`, `files_written`, `issues`, `next_actions`) follow agent-infrastructure.md." in envelope
    assert "# files_written names references/references.bib and GPD/references-status.json when written." in envelope
    assert "entries_added: N" in envelope
    assert envelope.index(
        "# Base fields (`status`, `files_written`, `issues`, `next_actions`) follow agent-infrastructure.md."
    ) < envelope.index(
        "# files_written names references/references.bib and GPD/references-status.json when written."
    )
    assert envelope.index(
        "# files_written names references/references.bib and GPD/references-status.json when written."
    ) < envelope.index(
        "entries_added: N"
    )
