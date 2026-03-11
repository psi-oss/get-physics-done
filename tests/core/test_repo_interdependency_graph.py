"""Guardrails for the checked-in repository interdependency graph."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GRAPH_PATH = REPO_ROOT / "REPO_INTERDEPENDENCY_GRAPH.md"
EXCLUDED_GRAPH_DIRS = {
    ".git",
    "__pycache__",
    ".venv",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".gpd",
    ".codex",
    ".gemini",
    ".opencode",
}


def _graph_text() -> str:
    return GRAPH_PATH.read_text(encoding="utf-8")


def _scope_count(label: str) -> int:
    match = re.search(rf"^- {re.escape(label)}: `(\d+)`$", _graph_text(), re.MULTILINE)
    assert match is not None, f"Missing scope count for {label}"
    return int(match.group(1))


def _count_repo_files() -> int:
    return sum(
        1
        for path in REPO_ROOT.rglob("*")
        if path.is_file() and not any(part in EXCLUDED_GRAPH_DIRS for part in path.parts)
    )


def test_graph_scope_counts_match_live_prompt_inventory() -> None:
    expected = {
        "Live repo files analyzed in the current tree": _count_repo_files(),
        "Python files under `src/` and `tests/`": sum(
            1
            for root in (REPO_ROOT / "src", REPO_ROOT / "tests")
            for _path in root.rglob("*.py")
        ),
        "`src/gpd/commands/*.md`": len(list((REPO_ROOT / "src/gpd/commands").glob("*.md"))),
        "`src/gpd/agents/*.md`": len(list((REPO_ROOT / "src/gpd/agents").glob("*.md"))),
        "`src/gpd/specs/workflows/*.md`": len(list((REPO_ROOT / "src/gpd/specs/workflows").glob("*.md"))),
        "`src/gpd/specs/templates/**/*.md`": len(list((REPO_ROOT / "src/gpd/specs/templates").rglob("*.md"))),
        "`src/gpd/specs/references/**/*.md`": len(list((REPO_ROOT / "src/gpd/specs/references").rglob("*.md"))),
        "`tests/**` files": sum(
            1
            for path in (REPO_ROOT / "tests").rglob("*")
            if path.is_file() and not any(part in EXCLUDED_GRAPH_DIRS for part in path.parts)
        ),
        "`.claude/commands/gpd/*.md`": len(list((REPO_ROOT / ".claude/commands/gpd").glob("*.md"))),
        "`.claude/agents/*.md`": len(list((REPO_ROOT / ".claude/agents").glob("gpd-*.md"))),
        "`.claude/get-physics-done/workflows/**/*.md`": len(
            list((REPO_ROOT / ".claude/get-physics-done/workflows").rglob("*.md"))
        ),
        "`.claude/get-physics-done/templates/**/*.md`": len(
            list((REPO_ROOT / ".claude/get-physics-done/templates").rglob("*.md"))
        ),
        "`.claude/get-physics-done/references/**/*.md`": len(
            list((REPO_ROOT / ".claude/get-physics-done/references").rglob("*.md"))
        ),
    }

    for label, count in expected.items():
        assert _scope_count(label) == count, label


def test_graph_same_stem_command_workflow_inventory_matches_tree() -> None:
    graph = _graph_text()
    match = re.search(
        r"src/gpd/commands/\{([^}]*)\}\.md -> src/gpd/specs/workflows/\{same stems\}\.md",
        graph,
    )
    assert match is not None, "Missing same-stem command/workflow edge inventory"

    graph_stems = [stem.strip() for stem in match.group(1).split(",") if stem.strip()]
    actual_stems = sorted(
        {path.stem for path in (REPO_ROOT / "src/gpd/commands").glob("*.md")}
        & {path.stem for path in (REPO_ROOT / "src/gpd/specs/workflows").glob("*.md")}
    )

    assert graph_stems == actual_stems


def test_graph_captures_staged_review_prompt_edges() -> None:
    graph = _graph_text()
    expected_edges = [
        "`src/gpd/commands/write-paper.md -> src/gpd/agents/{gpd-paper-writer,gpd-bibliographer,gpd-review-reader,gpd-review-literature,gpd-review-math,gpd-review-physics,gpd-review-significance,gpd-referee}.md`",
        "`src/gpd/commands/peer-review.md -> src/gpd/agents/{gpd-review-reader,gpd-review-literature,gpd-review-math,gpd-review-physics,gpd-review-significance,gpd-referee}.md`",
        "`src/gpd/specs/workflows/write-paper.md -> src/gpd/specs/workflows/peer-review.md`",
        "`src/gpd/specs/workflows/peer-review.md -> src/gpd/agents/{gpd-review-reader,gpd-review-literature,gpd-review-math,gpd-review-physics,gpd-review-significance,gpd-referee}.md`",
        "`src/gpd/agents/{gpd-review-reader,gpd-review-literature,gpd-review-math,gpd-review-physics,gpd-review-significance,gpd-referee}.md -> src/gpd/specs/references/publication/peer-review-panel.md`",
    ]

    for edge in expected_edges:
        assert edge in graph


def test_graph_captures_hook_runtime_wiring_edges() -> None:
    graph = _graph_text()
    expected_edges = [
        "`src/gpd/hooks/statusline.py -> src/gpd/hooks/runtime_detect.py`",
        "`src/gpd/hooks/statusline.py -> src/gpd/adapters/__init__.py`",
        "`src/gpd/hooks/check_update.py -> src/gpd/hooks/runtime_detect.py`",
        "`src/gpd/hooks/notify.py -> src/gpd/hooks/check_update.py`",
        "`src/gpd/hooks/notify.py -> src/gpd/hooks/runtime_detect.py`",
    ]

    unexpected_edges = [
        "`src/gpd/hooks/notify.py -> src/gpd/adapters/__init__.py`",
    ]

    for edge in expected_edges:
        assert edge in graph

    for edge in unexpected_edges:
        assert edge not in graph
