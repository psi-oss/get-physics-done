"""Shared repo-graph contract helpers for tests and sync tooling."""

from __future__ import annotations

import json
import subprocess
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
SAME_STEM_COMMAND_WORKFLOW_START = "<!-- repo-graph-same-stem-command-workflow:start -->"
SAME_STEM_COMMAND_WORKFLOW_END = "<!-- repo-graph-same-stem-command-workflow:end -->"

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


def _is_excluded_path(path: Path) -> bool:
    return any(part in EXCLUDED_GRAPH_DIRS for part in path.parts)


def _tracked_repo_files(repo_root: Path) -> list[Path] | None:
    try:
        completed = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=repo_root,
            check=True,
            capture_output=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None

    return [Path(relative_path) for relative_path in completed.stdout.decode("utf-8").split("\0") if relative_path]


def _repo_files_in_scope(repo_root: Path) -> list[Path]:
    tracked_files = _tracked_repo_files(repo_root)
    if tracked_files is not None:
        return [
            path
            for path in tracked_files
            if not _is_excluded_path(path) and (repo_root / path).is_file()
        ]

    return [
        path.relative_to(repo_root)
        for path in repo_root.rglob("*")
        if path.is_file() and not _is_excluded_path(path.relative_to(repo_root))
    ]


def _is_under(path: Path, *parent_parts: str) -> bool:
    return path.parts[: len(parent_parts)] == parent_parts


def _has_parent(path: Path, *parent_parts: str) -> bool:
    return path.parts[:-1] == parent_parts


def _preserved_generated_on(
    scope_counts: dict[str, int],
    excluded_dirs: list[str],
    contract_path: Path,
) -> str | None:
    if not contract_path.exists():
        return None

    existing_contract = json.loads(contract_path.read_text(encoding="utf-8"))
    if not isinstance(existing_contract, dict):
        return None
    if existing_contract.get("schema_version") != SCHEMA_VERSION:
        return None
    if existing_contract.get("excluded_graph_dirs") != excluded_dirs:
        return None
    if existing_contract.get("scope_counts") != scope_counts:
        return None

    generated_on = existing_contract.get("generated_on")
    return generated_on if isinstance(generated_on, str) else None


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
    return len(_repo_files_in_scope(repo_root))


def expected_scope_counts(repo_root: Path = REPO_ROOT) -> dict[str, int]:
    repo_files = _repo_files_in_scope(repo_root)

    return {
        "Live repo files analyzed in the current tree": len(repo_files),
        "Python files under `src/` and `tests/`": sum(
            1 for path in repo_files if path.suffix == ".py" and path.parts and path.parts[0] in {"src", "tests"}
        ),
        "`src/gpd/commands/*.md`": sum(
            1 for path in repo_files if _has_parent(path, "src", "gpd", "commands") and path.suffix == ".md"
        ),
        "`src/gpd/agents/*.md`": sum(
            1 for path in repo_files if _has_parent(path, "src", "gpd", "agents") and path.suffix == ".md"
        ),
        "`src/gpd/specs/workflows/*.md`": sum(
            1
            for path in repo_files
            if _has_parent(path, "src", "gpd", "specs", "workflows") and path.suffix == ".md"
        ),
        "`src/gpd/specs/templates/**/*.md`": sum(
            1
            for path in repo_files
            if _is_under(path, "src", "gpd", "specs", "templates") and path.suffix == ".md"
        ),
        "`src/gpd/specs/references/**/*.md`": sum(
            1
            for path in repo_files
            if _is_under(path, "src", "gpd", "specs", "references") and path.suffix == ".md"
        ),
        "`src/gpd/adapters/*.py`": sum(
            1 for path in repo_files if _has_parent(path, "src", "gpd", "adapters") and path.suffix == ".py"
        ),
        "`src/gpd/hooks/*.py`": sum(
            1 for path in repo_files if _has_parent(path, "src", "gpd", "hooks") and path.suffix == ".py"
        ),
        "`src/gpd/mcp/servers/*.py`": sum(
            1
            for path in repo_files
            if _has_parent(path, "src", "gpd", "mcp", "servers") and path.suffix == ".py"
        ),
        "`tests/**` files": sum(
            1 for path in repo_files if _is_under(path, "tests")
        ),
        "`infra/gpd-*.json`": sum(
            1
            for path in repo_files
            if _has_parent(path, "infra") and path.suffix == ".json" and path.name.startswith("gpd-")
        ),
    }


def build_contract(
    repo_root: Path = REPO_ROOT,
    generated_on: str | None = None,
    contract_path: Path = CONTRACT_PATH,
) -> dict[str, object]:
    scope_counts = expected_scope_counts(repo_root)
    excluded_dirs = list(EXCLUDED_GRAPH_DIRS)
    effective_generated_on = generated_on or _preserved_generated_on(scope_counts, excluded_dirs, contract_path)

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_on": effective_generated_on or date.today().isoformat(),
        "excluded_graph_dirs": excluded_dirs,
        "scope_counts": scope_counts,
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


def render_same_stem_command_workflow_block(repo_root: Path = REPO_ROOT) -> str:
    same_stems = ",".join(
        sorted(
            {path.stem for path in (repo_root / "src" / "gpd" / "commands").glob("*.md")}
            & {path.stem for path in (repo_root / "src" / "gpd" / "specs" / "workflows").glob("*.md")}
        )
    )

    return "\n".join(
        (
            SAME_STEM_COMMAND_WORKFLOW_START,
            f"- `src/gpd/commands/{{{same_stems}}}.md -> src/gpd/specs/workflows/{{same stems}}.md`",
            SAME_STEM_COMMAND_WORKFLOW_END,
        )
    )


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
    synced = replace_marked_block(synced, SCOPE_START, SCOPE_END, render_scope_block(contract))
    return replace_marked_block(
        synced,
        SAME_STEM_COMMAND_WORKFLOW_START,
        SAME_STEM_COMMAND_WORKFLOW_END,
        render_same_stem_command_workflow_block(),
    )
