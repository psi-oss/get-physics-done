from __future__ import annotations

import re
import subprocess
from pathlib import Path

from gpd.adapters.runtime_catalog import iter_runtime_descriptors

REPO_ROOT = Path(__file__).resolve().parent.parent

_CACHE_DIRS = {".ruff_cache", ".pytest_cache", ".mypy_cache", ".npm-cache"}
_RUNTIME_CONFIG_DIRS = {
    ".agents",
    *(descriptor.config_dir_name for descriptor in iter_runtime_descriptors()),
}
_GENERATED_GPD_FILES = {"STATE.md", "state.json", "state.json.bak"}
_LOCAL_RUNTIME_FILES = {".env", ".mcp.json"}


def _tracked_paths() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--full-name"],
        check=True,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    return [Path(line) for line in result.stdout.splitlines() if line]


def _is_hygiene_artifact(rel_path: Path) -> bool:
    parts = rel_path.parts

    if "__pycache__" in parts or rel_path.suffix in {".pyc", ".pyo", ".pyd"}:
        return True

    if any(part in _CACHE_DIRS for part in parts):
        return True

    if any(part == ".venv" for part in parts):
        return True

    if any(part in {"build", "dist"} for part in parts):
        return True

    if any(part.endswith(".egg-info") for part in parts):
        return True

    if parts and parts[0] in _RUNTIME_CONFIG_DIRS:
        return True

    if parts[:1] == ("GPD",) and rel_path.name in _GENERATED_GPD_FILES:
        return True

    if rel_path.name in _LOCAL_RUNTIME_FILES or rel_path.suffix == ".log":
        return True

    return False


def _read_command_workflow_allowlist() -> tuple[set[str], set[str]]:
    allowlist_path = REPO_ROOT / "docs" / "command-workflow-allowlist.md"
    commands: set[str] = set()
    workflows: set[str] = set()
    section: str | None = None

    for raw_line in allowlist_path.read_text().splitlines():
        line = raw_line.strip()

        if line.startswith("## Command-only"):
            section = "command"
            continue
        if line.startswith("## Workflow-only"):
            section = "workflow"
            continue
        if line.startswith("##"):
            section = None
            continue

        if not line.startswith("-") or section is None:
            continue

        match = re.match(r"- `(?P<slug>[a-z0-9-]+)`", line)
        if not match:
            continue

        slug = match.group("slug")
        if section == "command":
            commands.add(slug)
        elif section == "workflow":
            workflows.add(slug)

    return commands, workflows


def test_repo_hygiene_does_not_track_ignored_or_runtime_owned_artifacts() -> None:
    offenders = [path.as_posix() for path in _tracked_paths() if _is_hygiene_artifact(path)]

    assert not offenders, (
        "Tracked ignored/runtime-owned artifacts found in git index:\n"
        + "\n".join(f"- {path}" for path in offenders)
    )


def test_readme_focused_smoke_command_references_existing_tests() -> None:
    readme = (REPO_ROOT / "tests" / "README.md").read_text()
    match = re.search(r"focused local contract-visibility smoke pass, run `uv run pytest (?P<paths>.*?) -q`", readme)
    assert match is not None

    for path in match.group("paths").split():
        assert (REPO_ROOT / path).is_file(), f"stale tests/README.md smoke reference: {path}"


def test_gpd_utils_package_exposes_only_live_utility_modules() -> None:
    utils_dir = REPO_ROOT / "src" / "gpd" / "utils"
    package_init = utils_dir / "__init__.py"

    assert package_init.read_text().strip() == '"""Shared utility helpers for GPD internals."""\n\n__all__: list[str] = []'
    assert sorted(path.name for path in utils_dir.glob("*.py")) == ["__init__.py", "latex.py"]


def test_repo_hygiene_no_python_bytecode_tracked() -> None:
    offenders = [
        path.as_posix()
        for path in _tracked_paths()
        if "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo", ".pyd"}
    ]

    assert not offenders, (
        "Tracked bytecode or __pycache__ directories found in git index:\n"
        + "\n".join(f"- {path}" for path in offenders)
    )


def test_command_workflow_parity_matches_allowlist() -> None:
    command_docs = {path.stem for path in (REPO_ROOT / "src" / "gpd" / "commands").glob("*.md")}
    workflow_docs = {
        path.stem
        for path in (REPO_ROOT / "src" / "gpd" / "specs" / "workflows").glob("*.md")
    }

    commands_without_workflow = command_docs - workflow_docs
    workflows_without_command = workflow_docs - command_docs
    allowed_commands, allowed_workflows = _read_command_workflow_allowlist()

    assert commands_without_workflow == allowed_commands
    assert workflows_without_command == allowed_workflows
