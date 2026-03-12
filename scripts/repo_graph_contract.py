"""Shared repo-graph contract helpers for tests and sync tooling."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from gpd.adapters.runtime_catalog import iter_runtime_descriptors

REPO_ROOT = Path(__file__).resolve().parent.parent
GRAPH_PATH = REPO_ROOT / "tests" / "README.md"
CONTRACT_PATH = REPO_ROOT / "tests" / "repo_graph_contract.json"
SCHEMA_VERSION = 1

GENERATED_ON_START = "<!-- repo-graph-generated-on:start -->"
GENERATED_ON_END = "<!-- repo-graph-generated-on:end -->"
SCOPE_START = "<!-- repo-graph-scope:start -->"
SCOPE_END = "<!-- repo-graph-scope:end -->"

_LOCAL_RUNTIME_MIRROR_EXCLUDES = tuple(
    descriptor.config_dir_name
    for descriptor in iter_runtime_descriptors()
)

EXCLUDED_GRAPH_DIRS = (
    ".git",
    ".mcp.json",
    ".npm-cache",
    "__pycache__",
    ".venv",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".gpd",
    *_LOCAL_RUNTIME_MIRROR_EXCLUDES,
    "dist",
)

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


def load_contract() -> dict[str, object]:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def canonical_scope_label(label: str) -> str:
    normalized = label.strip()
    if normalized.startswith("`") and normalized.endswith("`"):
        normalized = normalized[1:-1]
    return _NORMALIZED_SCOPE_LABELS.get(normalized, label)


def parse_scope_count(label: str) -> int:
    canonical_label = canonical_scope_label(label)
    scope_counts = load_contract()["scope_counts"]
    assert isinstance(scope_counts, dict), "repo graph contract scope counts must be a mapping"
    value = scope_counts.get(canonical_label)
    assert isinstance(value, int), f"Missing scope count for {canonical_label}"
    return value


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


def build_contract(repo_root: Path = REPO_ROOT, generated_on: str | None = None) -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_on": generated_on or date.today().isoformat(),
        "excluded_graph_dirs": list(EXCLUDED_GRAPH_DIRS),
        "scope_counts": expected_scope_counts(repo_root),
    }


def write_contract(contract: dict[str, object], contract_path: Path = CONTRACT_PATH) -> None:
    contract_path.write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")


def _excluded_dir_readme_pattern(path_name: str) -> str:
    return path_name if path_name == ".mcp.json" else f"{path_name}/**"


def render_generated_on_block(contract: dict[str, object]) -> str:
    generated_on = contract["generated_on"]
    assert isinstance(generated_on, str), "generated_on must be a string"
    return "\n".join(
        (
            GENERATED_ON_START,
            f"Generated on `{generated_on}` from the current worktree.",
            GENERATED_ON_END,
        )
    )


def render_scope_block(contract: dict[str, object]) -> str:
    scope_counts = contract["scope_counts"]
    excluded_dirs = contract["excluded_graph_dirs"]
    assert isinstance(scope_counts, dict), "scope_counts must be a mapping"
    assert isinstance(excluded_dirs, list), "excluded_graph_dirs must be a list"

    lines = [SCOPE_START, ""]
    for label in GRAPH_SCOPE_LABELS:
        value = scope_counts.get(label)
        assert isinstance(value, int), f"Missing scope count for {label}"
        lines.append(f"- {label}: `{value}`")

    lines.extend(
        (
            "",
            "Excluded as noise from node counting, but still modeled where contractually relevant:",
            "",
        )
    )
    lines.extend(f"- `{_excluded_dir_readme_pattern(path_name)}`" for path_name in excluded_dirs)
    lines.append(SCOPE_END)
    return "\n".join(lines)


def extract_marked_block(text: str, start_marker: str, end_marker: str) -> str:
    start = text.index(start_marker)
    end = text.index(end_marker, start) + len(end_marker)
    return text[start:end]


def replace_marked_block(text: str, start_marker: str, end_marker: str, replacement: str) -> str:
    start = text.index(start_marker)
    end = text.index(end_marker, start) + len(end_marker)
    return text[:start] + replacement + text[end:]


def sync_readme_text(readme_text: str, contract: dict[str, object]) -> str:
    synced = replace_marked_block(
        readme_text,
        GENERATED_ON_START,
        GENERATED_ON_END,
        render_generated_on_block(contract),
    )
    return replace_marked_block(synced, SCOPE_START, SCOPE_END, render_scope_block(contract))
