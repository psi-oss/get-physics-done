"""Phase 7 spec-text contract tests for the ``gpd:record-backtrack`` workflow."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / "src" / "gpd" / "specs" / "workflows"
AGENTS_DIR = REPO_ROOT / "src" / "gpd" / "agents"


def test_record_backtrack_creates_file_and_appends_row() -> None:
    spec_path = WORKFLOWS_DIR / "record-backtrack.md"
    assert spec_path.exists(), (
        f"record-backtrack workflow spec missing at {spec_path}"
    )

    text = spec_path.read_text(encoding="utf-8")

    assert "# Project Backtracks" in text, (
        "record-backtrack.md must embed the '# Project Backtracks' template header"
    )

    required_columns = (
        "date",
        "phase",
        "stage",
        "trigger",
        "produced",
        "why_wrong",
        "counter_action",
        "category",
        "confidence",
        "promote",
        "reverted_commit",
    )
    for column in required_columns:
        assert column in text, (
            f"record-backtrack.md is missing the '{column}' schema column"
        )

    assert '<step name="check_backtracks_file">' in text, (
        "record-backtrack.md must define a '<step name=\"check_backtracks_file\">' step"
    )
    assert '<step name="append_backtrack">' in text, (
        "record-backtrack.md must define a '<step name=\"append_backtrack\">' step"
    )


def test_record_backtrack_dedupes_on_identical_trigger_plus_why() -> None:
    spec_path = WORKFLOWS_DIR / "record-backtrack.md"
    text = spec_path.read_text(encoding="utf-8")

    assert '<step name="check_duplicates">' in text, (
        "record-backtrack.md must define a '<step name=\"check_duplicates\">' step"
    )

    start = text.index('<step name="check_duplicates">')
    end = text.find("</step>", start)
    assert end != -1, "check_duplicates step is missing a closing </step> tag"
    body = text[start:end]

    assert "trigger" in body, (
        "check_duplicates step body must reference the 'trigger' field"
    )
    assert "why_wrong" in body, (
        "check_duplicates step body must reference the 'why_wrong' field"
    )


def test_record_backtrack_auto_copies_to_insights_when_promote_candidate() -> None:
    spec_path = WORKFLOWS_DIR / "record-backtrack.md"
    text = spec_path.read_text(encoding="utf-8")

    assert '<step name="promote_to_insights">' in text, (
        "record-backtrack.md must define a '<step name=\"promote_to_insights\">' step"
    )

    start = text.index('<step name="promote_to_insights">')
    end = text.find("</step>", start)
    assert end != -1, "promote_to_insights step is missing a closing </step> tag"
    body = text[start:end]

    assert ("promote=true" in body) or ("promote: true" in body), (
        "promote_to_insights step must be conditional on 'promote=true' or 'promote: true'"
    )
    assert "GPD/INSIGHTS.md" in body, (
        "promote_to_insights step must reference GPD/INSIGHTS.md as the target file"
    )
    assert "Execution Deviations" in body, (
        "promote_to_insights step must target the '## Execution Deviations' section"
    )
