"""Guardrails for the checked-in repository graph README."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GRAPH_PATH = REPO_ROOT / "tests" / "README.md"
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
    "dist",
}


def _graph_text() -> str:
    return GRAPH_PATH.read_text(encoding="utf-8")


def _scope_count(label: str) -> int:
    match = re.search(rf"^- {re.escape(label)}: `(\d+)`$", _graph_text(), re.MULTILINE)
    assert match is not None, f"Missing scope count for {label}"
    return int(match.group(1))


def _live_repo_file_count() -> int:
    return sum(
        1
        for path in REPO_ROOT.rglob("*")
        if path.is_file() and not any(part in EXCLUDED_GRAPH_DIRS for part in path.parts)
    )


def test_graph_scope_counts_match_live_prompt_inventory() -> None:
    expected = {
        "Live repo files analyzed in the current tree": _live_repo_file_count(),
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
        "`src/gpd/adapters/*.py`": len(list((REPO_ROOT / "src/gpd/adapters").glob("*.py"))),
        "`src/gpd/hooks/*.py`": len(list((REPO_ROOT / "src/gpd/hooks").glob("*.py"))),
        "`src/gpd/mcp/servers/*.py`": len(list((REPO_ROOT / "src/gpd/mcp/servers").glob("*.py"))),
        "`tests/**` files": sum(
            1
            for path in (REPO_ROOT / "tests").rglob("*")
            if path.is_file() and not any(part in EXCLUDED_GRAPH_DIRS for part in path.parts)
        ),
        "`infra/gpd-*.json`": len(list((REPO_ROOT / "infra").glob("gpd-*.json"))),
    }

    mismatches = [
        f"{label}: graph={_scope_count(label)} live={count}"
        for label, count in expected.items()
        if _scope_count(label) != count
    ]

    assert not mismatches, "Graph scope counts are stale:\n" + "\n".join(mismatches)


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


def test_graph_captures_paper_build_prompt_edges() -> None:
    graph = _graph_text()
    expected_edges = [
        "`src/gpd/commands/write-paper.md -> gpd paper-build paper/PAPER-CONFIG.json`",
        "`src/gpd/commands/write-paper.md -> paper/{PAPER-CONFIG.json,main.tex,ARTIFACT-MANIFEST.json}`",
        "`src/gpd/commands/peer-review.md -> candidate manuscript roots {paper/main.tex, manuscript/main.tex, draft/main.tex}`",
        "`src/gpd/specs/workflows/write-paper.md -> src/gpd/cli.py::paper_build`",
        "`src/gpd/specs/workflows/write-paper.md -> paper/{PAPER-CONFIG.json,main.tex,ARTIFACT-MANIFEST.json}`",
        "`src/gpd/specs/workflows/peer-review.md -> candidate manuscript roots {paper/main.tex, manuscript/main.tex, draft/main.tex}`",
        "`src/gpd/specs/workflows/peer-review.md -> paper/{PAPER-CONFIG.json,ARTIFACT-MANIFEST.json,BIBLIOGRAPHY-AUDIT.json}`",
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


def test_graph_test_file_references_exist() -> None:
    missing = sorted(
        {
            ref
            for ref in re.findall(r"tests/[A-Za-z0-9_./-]+\.py", _graph_text())
            if not (REPO_ROOT / ref).is_file()
        }
    )

    assert missing == []


def test_graph_claude_artifact_language_matches_tree() -> None:
    graph = _graph_text()

    assert "## Installed Runtime Artifact Family: `.claude/**`" in graph
    assert ".claude/settings.local.json" not in graph
    assert "## Checked-In Installed Snapshot: `.claude/**`" not in graph
    assert "checked-in installed artifacts like `.claude/**`" not in graph

    if not (REPO_ROOT / ".claude").exists():
        assert "- `.claude/commands/gpd/*.md`" not in graph
        assert "- `.claude/agents/*.md`" not in graph
        assert "- `.claude/get-physics-done/workflows/**/*.md`" not in graph
        assert "- `.claude/get-physics-done/templates/**/*.md`" not in graph
        assert "- `.claude/get-physics-done/references/**/*.md`" not in graph
