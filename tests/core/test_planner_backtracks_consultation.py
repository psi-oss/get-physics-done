"""Phase 7 spec-text contract test for planner BACKTRACKS.md consultation."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / "src" / "gpd" / "specs" / "workflows"
AGENTS_DIR = REPO_ROOT / "src" / "gpd" / "agents"


def test_planner_reads_backtracks_when_present() -> None:
    planner_path = AGENTS_DIR / "gpd-planner.md"
    assert planner_path.exists(), f"planner agent spec missing at {planner_path}"

    text = planner_path.read_text(encoding="utf-8")

    assert "GPD/BACKTRACKS.md" in text, (
        "gpd-planner.md must reference GPD/BACKTRACKS.md in the discovery loop"
    )

    # Decision matrix row for BACKTRACKS.md should place the filename next to
    # an EXISTS / skip token on the same markdown line.
    matrix_lines = [
        line
        for line in text.splitlines()
        if "BACKTRACKS.md" in line and ("EXISTS" in line or "Missing" in line)
    ]
    assert matrix_lines, (
        "gpd-planner.md must contain a decision-matrix row for BACKTRACKS.md "
        "(expected 'BACKTRACKS.md' adjacent to an 'EXISTS' / 'Missing' token)"
    )

    assert "patterns_consulted" in text, (
        "gpd-planner.md must reference 'patterns_consulted' (frontmatter record)"
    )

    # The `backtracks` key should live near the patterns_consulted anchor so
    # the frontmatter record extension is real rather than a stray mention.
    anchor = text.index("patterns_consulted")
    window = text[anchor : anchor + 600]
    assert "backtracks" in window, (
        "gpd-planner.md must list 'backtracks' inside the patterns_consulted frontmatter block"
    )
