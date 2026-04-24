"""Phase 7 spec-text contract test for the ``gpd:undo`` backtrack hook."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / "src" / "gpd" / "specs" / "workflows"
AGENTS_DIR = REPO_ROOT / "src" / "gpd" / "agents"


def test_undo_offers_record_backtrack_post_step() -> None:
    spec_path = WORKFLOWS_DIR / "undo.md"
    assert spec_path.exists(), f"undo workflow spec missing at {spec_path}"

    text = spec_path.read_text(encoding="utf-8")

    assert '<step name="offer_record_backtrack">' in text, (
        "undo.md must define a '<step name=\"offer_record_backtrack\">' post-step"
    )

    offer_start = text.index('<step name="offer_record_backtrack">')
    offer_end = text.find("</step>", offer_start)
    assert offer_end != -1, (
        "offer_record_backtrack step is missing a closing </step> tag"
    )
    body = text[offer_start:offer_end]

    assert "gpd:record-backtrack" in body, (
        "offer_record_backtrack step must reference 'gpd:record-backtrack'"
    )
    assert "[Y/n]" in body or "[Y/n/e]" in body, (
        "offer_record_backtrack step must use the '[Y/n]' or '[Y/n/e]' Enter-is-accept convention"
    )

    # The hook is specified to run AFTER the completion step. If the completion
    # step is present, offer_record_backtrack should appear after it.
    completion_marker = '<step name="completion">'
    if completion_marker in text:
        assert text.index(completion_marker) < offer_start, (
            "offer_record_backtrack must appear after the completion step"
        )
