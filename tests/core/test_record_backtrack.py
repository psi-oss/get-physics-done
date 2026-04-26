"""Phase 7 spec-text contract tests for the ``gpd:record-backtrack`` workflow."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / "src" / "gpd" / "specs" / "workflows"


BACKTRACK_COLUMNS = (
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
FINAL_BACKTRACK_FIELDS = tuple(f"FINAL_{column.upper()}" for column in BACKTRACK_COLUMNS)


def _step_body(text: str, step_name: str) -> str:
    start_marker = f'<step name="{step_name}">'
    start = text.index(start_marker)
    end = text.find("</step>", start)
    assert end != -1, f"{step_name} step is missing a closing </step> tag"
    return text[start:end]


def test_record_backtrack_creates_file_and_appends_row() -> None:
    spec_path = WORKFLOWS_DIR / "record-backtrack.md"
    assert spec_path.exists(), (
        f"record-backtrack workflow spec missing at {spec_path}"
    )

    text = spec_path.read_text(encoding="utf-8")

    assert "# Project Backtracks" in text, (
        "record-backtrack.md must embed the '# Project Backtracks' template header"
    )

    schema_header = "| " + " | ".join(BACKTRACK_COLUMNS) + " |"
    assert schema_header in text, (
        "record-backtrack.md must define the exact 11-column BACKTRACKS.md table schema"
    )

    assert '<step name="check_backtracks_file">' in text, (
        "record-backtrack.md must define a '<step name=\"check_backtracks_file\">' step"
    )
    assert '<step name="append_backtrack">' in text, (
        "record-backtrack.md must define a '<step name=\"append_backtrack\">' step"
    )
    collect_body = _step_body(text, "collect_backtrack_fields")
    assert "Do not run dedupe from raw prefill values." in collect_body

    append_body = _step_body(text, "append_backtrack")
    row_format = "| " + " | ".join(f"{{{field}}}" for field in FINAL_BACKTRACK_FIELDS) + " |"
    assert row_format in append_body, (
        "append_backtrack must append exactly one row using the 11-column schema order"
    )


def test_record_backtrack_dedupes_on_identical_trigger_plus_why() -> None:
    spec_path = WORKFLOWS_DIR / "record-backtrack.md"
    text = spec_path.read_text(encoding="utf-8")

    assert '<step name="check_duplicates">' in text, (
        "record-backtrack.md must define a '<step name=\"check_duplicates\">' step"
    )

    body = _step_body(text, "check_duplicates")

    assert "phase` + `trigger` + `why_wrong`" in body, (
        "check_duplicates must dedupe on the intended phase+trigger+why_wrong tuple"
    )
    assert '-v ph="$FINAL_PHASE"' in body
    assert '-v tr="$FINAL_TRIGGER"' in body
    assert '-v ww="$FINAL_WHY_WRONG"' in body
    assert "trim($3) == ph" in body
    assert "tolower(trim($5)) == tolower(tr)" in body
    assert "tolower(trim($7)) == tolower(ww)" in body


def test_record_backtrack_auto_copies_to_insights_when_promote_candidate() -> None:
    spec_path = WORKFLOWS_DIR / "record-backtrack.md"
    text = spec_path.read_text(encoding="utf-8")

    assert '<step name="promote_to_insights">' in text, (
        "record-backtrack.md must define a '<step name=\"promote_to_insights\">' step"
    )

    body = _step_body(text, "promote_to_insights")

    assert ("promote=true" in body) or ("promote: true" in body), (
        "promote_to_insights step must be conditional on 'promote=true' or 'promote: true'"
    )
    assert "GPD/INSIGHTS.md" in body, (
        "promote_to_insights step must reference GPD/INSIGHTS.md as the target file"
    )
    assert "Execution Deviations" in body, (
        "promote_to_insights step must target the '## Execution Deviations' section"
    )
