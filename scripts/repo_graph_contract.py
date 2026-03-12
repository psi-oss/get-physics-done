"""Shared repo-graph contract helpers for tests and sync tooling."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GRAPH_PATH = REPO_ROOT / "tests" / "README.md"

EXCLUDED_GRAPH_DIRS = {
    ".git",
    ".mcp.json",
    ".npm-cache",
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

GRAPH_SCOPE_LABELS = (
    "Live repo files analyzed in the current tree",
    "Python files under `src/` and `tests/`",
    "`src/gpd/commands/*.md`",
    "`src/gpd/agents/*.md`",
    "`src/gpd/specs/workflows/*.md`",
    "`src/gpd/specs/templates/**/*.md`",
    "`src/gpd/specs/references/**/*.md`",
    "`src/gpd/adapters/*.py`",
    "`src/gpd/hooks/*.py`",
    "`src/gpd/mcp/servers/*.py`",
    "`tests/**` files",
    "`infra/gpd-*.json`",
)

_NORMALIZED_SCOPE_LABELS = {
    label[1:-1] if label.startswith("`") and label.endswith("`") else label: label
    for label in GRAPH_SCOPE_LABELS
}


def read_graph_text() -> str:
    return GRAPH_PATH.read_text(encoding="utf-8")


def canonical_scope_label(label: str) -> str:
    normalized = label.strip()
    if normalized.startswith("`") and normalized.endswith("`"):
        normalized = normalized[1:-1]
    return _NORMALIZED_SCOPE_LABELS.get(normalized, label)


def parse_scope_count(label: str) -> int:
    canonical_label = canonical_scope_label(label)
    match = re.search(rf"^- {re.escape(canonical_label)}: `(\d+)`$", read_graph_text(), re.MULTILINE)
    assert match is not None, f"Missing scope count for {canonical_label}"
    return int(match.group(1))


def live_repo_file_count(repo_root: Path = REPO_ROOT) -> int:
    return sum(
        1
        for path in repo_root.rglob("*")
        if path.is_file() and not any(part in EXCLUDED_GRAPH_DIRS for part in path.parts)
    )


def expected_scope_counts(repo_root: Path = REPO_ROOT) -> dict[str, int]:
    return {
        "Live repo files analyzed in the current tree": live_repo_file_count(repo_root),
        "Python files under `src/` and `tests/`": sum(
            1
            for root in (repo_root / "src", repo_root / "tests")
            for _path in root.rglob("*.py")
        ),
        "`src/gpd/commands/*.md`": len(list((repo_root / "src/gpd/commands").glob("*.md"))),
        "`src/gpd/agents/*.md`": len(list((repo_root / "src/gpd/agents").glob("*.md"))),
        "`src/gpd/specs/workflows/*.md`": len(list((repo_root / "src/gpd/specs/workflows").glob("*.md"))),
        "`src/gpd/specs/templates/**/*.md`": len(list((repo_root / "src/gpd/specs/templates").rglob("*.md"))),
        "`src/gpd/specs/references/**/*.md`": len(list((repo_root / "src/gpd/specs/references").rglob("*.md"))),
        "`src/gpd/adapters/*.py`": len(list((repo_root / "src/gpd/adapters").glob("*.py"))),
        "`src/gpd/hooks/*.py`": len(list((repo_root / "src/gpd/hooks").glob("*.py"))),
        "`src/gpd/mcp/servers/*.py`": len(list((repo_root / "src/gpd/mcp/servers").glob("*.py"))),
        "`tests/**` files": sum(
            1
            for path in (repo_root / "tests").rglob("*")
            if path.is_file() and not any(part in EXCLUDED_GRAPH_DIRS for part in path.parts)
        ),
        "`infra/gpd-*.json`": len(list((repo_root / "infra").glob("gpd-*.json"))),
    }
