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


def test_repo_hygiene_does_not_track_ignored_or_runtime_owned_artifacts() -> None:
    offenders = [path.as_posix() for path in _tracked_paths() if _is_hygiene_artifact(path)]

    assert not offenders, (
        "Tracked ignored/runtime-owned artifacts found in git index:\n"
        + "\n".join(f"- {path}" for path in offenders)
    )


def test_readme_focused_smoke_command_references_existing_tests() -> None:
    readme = (REPO_ROOT / "tests" / "README.md").read_text()
    match = re.search(r"focused smoke pass, run `uv run pytest (?P<paths>.*?) -q`", readme)
    assert match is not None

    for path in match.group("paths").split():
        assert (REPO_ROOT / path).is_file(), f"stale tests/README.md smoke reference: {path}"


def test_gpd_utils_package_exposes_only_live_utility_modules() -> None:
    utils_dir = REPO_ROOT / "src" / "gpd" / "utils"
    package_init = utils_dir / "__init__.py"

    assert package_init.read_text().strip() == ""
    assert sorted(path.name for path in utils_dir.glob("*.py")) == ["__init__.py", "latex.py"]
