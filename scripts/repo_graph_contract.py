"""Shared repo-graph contract helpers for tests and sync tooling."""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from functools import cache, lru_cache
from pathlib import Path

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

GRAPH_SCOPE_LABELS = (
    "`src/gpd/commands/*.md`",
    "`src/gpd/agents/*.md`",
    "`src/gpd/specs/workflows/*.md`",
    "`src/gpd/specs/templates/**/*.md`",
    "`src/gpd/specs/references/**/*.md`",
    "`src/gpd/adapters/*.py`",
    "`src/gpd/hooks/*.py`",
    "`src/gpd/mcp/*.py`",
    "`src/gpd/mcp/integrations/*.py`",
    "`src/gpd/mcp/servers/*.py`",
    "`infra/gpd-*.json`",
)

_NORMALIZED_SCOPE_LABELS = {
    label[1:-1] if label.startswith("`") and label.endswith("`") else label: label for label in GRAPH_SCOPE_LABELS
}


@lru_cache(maxsize=1)
def _runtime_catalog_module():
    module_path = REPO_ROOT / "src" / "gpd" / "adapters" / "runtime_catalog.py"
    spec = importlib.util.spec_from_file_location("_gpd_runtime_catalog_bootstrap", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load runtime catalog from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(spec.name, module)
    spec.loader.exec_module(module)
    return module


def iter_runtime_descriptors():
    return _runtime_catalog_module().iter_runtime_descriptors()


_LOCAL_RUNTIME_MIRROR_EXCLUDES = tuple(descriptor.config_dir_name for descriptor in iter_runtime_descriptors())

EXCLUDED_GRAPH_DIRS = (
    ".git",
    ".mcp.json",
    ".npm-cache",
    "__pycache__",
    ".venv",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "GPD",
    *_LOCAL_RUNTIME_MIRROR_EXCLUDES,
    "dist",
)


def read_graph_text() -> str:
    return GRAPH_PATH.read_text(encoding="utf-8")


def load_contract() -> dict[str, object]:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


_GRAPH_EDGE_RE = re.compile(r"^- `([^`\n]+?) -> ([^`\n]+?)`$", re.MULTILINE)


def iter_graph_edge_specs(graph_text: str | None = None) -> tuple[tuple[str, str], ...]:
    text = graph_text if graph_text is not None else read_graph_text()
    return tuple((match.group(1), match.group(2)) for match in _GRAPH_EDGE_RE.finditer(text))


@cache
def _expand_braced_edge_endpoint(endpoint: str) -> tuple[str, ...]:
    match = re.search(r"\{([^{}]+)\}", endpoint)
    if match is None:
        return (endpoint,)

    prefix = endpoint[: match.start()]
    suffix = endpoint[match.end() :]
    expansions: list[str] = []
    for option in (item.strip() for item in match.group(1).split(",")):
        if not option:
            continue
        for expanded_suffix in _expand_braced_edge_endpoint(suffix):
            expansions.append(f"{prefix}{option}{expanded_suffix}")
    return tuple(expansions)


def _edge_endpoint_matches(expected: str, rendered: str) -> bool:
    if expected == rendered:
        return True
    return expected in _expand_braced_edge_endpoint(rendered)


def graph_has_edge(source: str, target: str, graph_text: str | None = None) -> bool:
    for rendered_source, rendered_target in iter_graph_edge_specs(graph_text):
        if _edge_endpoint_matches(source, rendered_source) and _edge_endpoint_matches(target, rendered_target):
            return True
    return False


def graph_has_edge_containing(
    source_fragment: str,
    target_fragment: str,
    graph_text: str | None = None,
) -> bool:
    for rendered_source, rendered_target in iter_graph_edge_specs(graph_text):
        if source_fragment in rendered_source and target_fragment in rendered_target:
            return True
    return False


def _is_excluded_path(path: Path) -> bool:
    if not path.parts:
        return False
    return path.parts[0] in EXCLUDED_GRAPH_DIRS


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


def _untracked_repo_files(repo_root: Path) -> list[Path] | None:
    try:
        completed = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard", "-z"],
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
        return [path for path in tracked_files if not _is_excluded_path(path) and (repo_root / path).is_file()]

    return [
        path.relative_to(repo_root)
        for path in repo_root.rglob("*")
        if path.is_file() and not _is_excluded_path(path.relative_to(repo_root))
    ]


def _is_graph_scope_path(path: Path) -> bool:
    return (
        (_has_parent(path, "src", "gpd", "commands") and path.suffix == ".md")
        or (_has_parent(path, "src", "gpd", "agents") and path.suffix == ".md")
        or (_has_parent(path, "src", "gpd", "specs", "workflows") and path.suffix == ".md")
        or (_is_under(path, "src", "gpd", "specs", "templates") and path.suffix == ".md")
        or (_is_under(path, "src", "gpd", "specs", "references") and path.suffix == ".md")
        or (_has_parent(path, "src", "gpd", "adapters") and path.suffix == ".py")
        or (_has_parent(path, "src", "gpd", "hooks") and path.suffix == ".py")
        or (_has_parent(path, "src", "gpd", "mcp") and path.suffix == ".py")
        or (_has_parent(path, "src", "gpd", "mcp", "integrations") and path.suffix == ".py")
        or (_has_parent(path, "src", "gpd", "mcp", "servers") and path.suffix == ".py")
        or (_has_parent(path, "infra") and path.suffix == ".json" and path.name.startswith("gpd-"))
    )


def untracked_graph_scope_files(repo_root: Path = REPO_ROOT) -> tuple[Path, ...]:
    untracked_files = _untracked_repo_files(repo_root)
    if untracked_files is None:
        return ()
    return tuple(
        sorted(
            (
                path
                for path in untracked_files
                if not _is_excluded_path(path) and _is_graph_scope_path(path) and (repo_root / path).is_file()
            ),
            key=lambda path: path.as_posix(),
        )
    )


def _is_under(path: Path, *parent_parts: str) -> bool:
    return path.parts[: len(parent_parts)] == parent_parts


def _has_parent(path: Path, *parent_parts: str) -> bool:
    return path.parts[:-1] == parent_parts


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
        "`src/gpd/commands/*.md`": sum(
            1 for path in repo_files if _has_parent(path, "src", "gpd", "commands") and path.suffix == ".md"
        ),
        "`src/gpd/agents/*.md`": sum(
            1 for path in repo_files if _has_parent(path, "src", "gpd", "agents") and path.suffix == ".md"
        ),
        "`src/gpd/specs/workflows/*.md`": sum(
            1 for path in repo_files if _has_parent(path, "src", "gpd", "specs", "workflows") and path.suffix == ".md"
        ),
        "`src/gpd/specs/templates/**/*.md`": sum(
            1 for path in repo_files if _is_under(path, "src", "gpd", "specs", "templates") and path.suffix == ".md"
        ),
        "`src/gpd/specs/references/**/*.md`": sum(
            1 for path in repo_files if _is_under(path, "src", "gpd", "specs", "references") and path.suffix == ".md"
        ),
        "`src/gpd/adapters/*.py`": sum(
            1 for path in repo_files if _has_parent(path, "src", "gpd", "adapters") and path.suffix == ".py"
        ),
        "`src/gpd/hooks/*.py`": sum(
            1 for path in repo_files if _has_parent(path, "src", "gpd", "hooks") and path.suffix == ".py"
        ),
        "`src/gpd/mcp/*.py`": sum(
            1 for path in repo_files if _has_parent(path, "src", "gpd", "mcp") and path.suffix == ".py"
        ),
        "`src/gpd/mcp/integrations/*.py`": sum(
            1 for path in repo_files if _has_parent(path, "src", "gpd", "mcp", "integrations") and path.suffix == ".py"
        ),
        "`src/gpd/mcp/servers/*.py`": sum(
            1 for path in repo_files if _has_parent(path, "src", "gpd", "mcp", "servers") and path.suffix == ".py"
        ),
        "`infra/gpd-*.json`": sum(
            1
            for path in repo_files
            if _has_parent(path, "infra") and path.suffix == ".json" and path.name.startswith("gpd-")
        ),
    }


def build_contract(
    repo_root: Path = REPO_ROOT,
) -> dict[str, object]:
    scope_counts = expected_scope_counts(repo_root)
    excluded_dirs = list(EXCLUDED_GRAPH_DIRS)

    return {
        "schema_version": SCHEMA_VERSION,
        "excluded_graph_dirs": excluded_dirs,
        "scope_counts": scope_counts,
    }


def write_contract(contract: dict[str, object], contract_path: Path = CONTRACT_PATH) -> None:
    contract_path.write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")


def _excluded_dir_readme_pattern(path_name: str) -> str:
    return path_name if path_name == ".mcp.json" else f"{path_name}/**"


def render_generated_on_block(_contract: dict[str, object]) -> str:
    return "\n".join(
        (
            GENERATED_ON_START,
            "Only marked repo-graph blocks are generated from the current worktree via `python scripts/sync_repo_graph_contract.py`.",
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
    repo_files = _repo_files_in_scope(repo_root)
    command_stems = {
        path.stem for path in repo_files if _has_parent(path, "src", "gpd", "commands") and path.suffix == ".md"
    }
    workflow_stems = {
        path.stem
        for path in repo_files
        if _has_parent(path, "src", "gpd", "specs", "workflows") and path.suffix == ".md"
    }
    same_stems = ",".join(sorted(command_stems & workflow_stems))

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


def sync_readme_text(readme_text: str, contract: dict[str, object], repo_root: Path = REPO_ROOT) -> str:
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
        render_same_stem_command_workflow_block(repo_root),
    )
