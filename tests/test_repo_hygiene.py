from __future__ import annotations

import ast
import re
import subprocess
from collections import defaultdict
from pathlib import Path

from gpd.adapters.runtime_catalog import iter_runtime_descriptors

REPO_ROOT = Path(__file__).resolve().parent.parent

_GENERATED_ARTIFACT_DIRS = {
    ".mypy_cache",
    ".nox",
    ".npm-cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".uv-cache",
    "htmlcov",
    "node_modules",
}
_GENERATED_ARTIFACT_FILE_NAMES = {
    ".coverage",
    "coverage.xml",
    "junit.xml",
    "pytest-report.xml",
}
_GENERATED_ARTIFACT_NAME_PREFIXES = ("GPD-FIX-REPORT",)
_GENERATED_ARTIFACT_SUFFIXES = {".prof", ".profraw", ".profdata"}
_RUNTIME_CONFIG_DIRS = {
    ".agents",
    *(descriptor.config_dir_name for descriptor in iter_runtime_descriptors()),
}
_GENERATED_GPD_FILES = {"STATE.md", "state.json", "state.json.bak", "state.json.lock"}
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


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )


def _tracked_test_python_paths() -> list[Path]:
    return [
        path
        for path in _tracked_paths()
        if path.parts[:1] == ("tests",)
        and path.suffix == ".py"
        and path.name.startswith("test_")
        and (REPO_ROOT / path).is_file()
    ]


def _is_hygiene_artifact(rel_path: Path) -> bool:
    parts = rel_path.parts

    if "__pycache__" in parts or rel_path.suffix in {".pyc", ".pyo", ".pyd"}:
        return True

    if any(part in _GENERATED_ARTIFACT_DIRS for part in parts):
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

    if (
        rel_path.name in _GENERATED_ARTIFACT_FILE_NAMES
        or rel_path.name.startswith(".coverage.")
        or rel_path.name.startswith(_GENERATED_ARTIFACT_NAME_PREFIXES)
        or rel_path.suffix in _GENERATED_ARTIFACT_SUFFIXES
    ):
        return True

    if rel_path.name in _LOCAL_RUNTIME_FILES or rel_path.suffix == ".log":
        return True

    return False


def _is_gpd_runtime_artifact(rel_path: Path) -> bool:
    parts = rel_path.parts

    return (
        parts[:1] == ("GPD",)
        or bool(parts and parts[0] in _RUNTIME_CONFIG_DIRS)
        or rel_path.name in _LOCAL_RUNTIME_FILES
    )


def _parse_test_file(rel_path: Path) -> ast.Module:
    return ast.parse((REPO_ROOT / rel_path).read_text(encoding="utf-8"), filename=rel_path.as_posix())


def _literal_only_assert_locations(rel_path: Path) -> list[str]:
    offenders: list[str] = []
    for node in ast.walk(_parse_test_file(rel_path)):
        if not isinstance(node, ast.Assert):
            continue
        try:
            ast.literal_eval(node.test)
        except (ValueError, SyntaxError):
            continue
        offenders.append(f"{rel_path.as_posix()}:{node.lineno}: assert {ast.unparse(node.test)}")
    return offenders


def _duplicate_test_definition_locations(rel_path: Path) -> list[str]:
    offenders: list[str] = []
    tree = _parse_test_file(rel_path)
    scoped_bodies: list[tuple[str, list[ast.stmt]]] = [("<module>", tree.body)]
    scoped_bodies.extend((node.name, node.body) for node in ast.walk(tree) if isinstance(node, ast.ClassDef))

    for scope_name, body in scoped_bodies:
        definitions: dict[str, list[int]] = defaultdict(list)
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
                definitions[node.name].append(node.lineno)
        for name, line_numbers in sorted(definitions.items()):
            if len(line_numbers) > 1:
                joined_lines = ", ".join(str(line_number) for line_number in line_numbers)
                offenders.append(f"{rel_path.as_posix()}:{scope_name}: duplicate {name} at lines {joined_lines}")
    return offenders


def test_repo_hygiene_does_not_track_ignored_or_runtime_owned_artifacts() -> None:
    offenders = [path.as_posix() for path in _tracked_paths() if _is_hygiene_artifact(path)]

    assert not offenders, "Tracked ignored/runtime-owned artifacts found in git index:\n" + "\n".join(
        f"- {path}" for path in offenders
    )


def test_tracked_paths_do_not_include_gpd_runtime_artifacts() -> None:
    offenders = [path.as_posix() for path in _tracked_paths() if _is_gpd_runtime_artifact(path)]

    assert not offenders, "Tracked GPD runtime artifacts found in git index:\n" + "\n".join(
        f"- {path}" for path in offenders
    )


def test_gitignore_covers_literal_shell_tmpdir_debris(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    (repo / ".gitignore").write_text((REPO_ROOT / ".gitignore").read_text(encoding="utf-8"), encoding="utf-8")

    ignored_relpaths = ("$tmpdir/install.log", '"$tmpdir"/install.log')
    for relpath in ignored_relpaths:
        path = repo / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("generated install debris\n", encoding="utf-8")

    for relpath in ignored_relpaths:
        _git(repo, "check-ignore", "--quiet", "--", relpath)


def test_gitignore_covers_generated_local_artifact_families(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    (repo / ".gitignore").write_text((REPO_ROOT / ".gitignore").read_text(encoding="utf-8"), encoding="utf-8")

    ignored_relpaths = (
        ".uv-cache/archive-v0/cache.db",
        ".tox/py312/.coverage",
        ".nox/tests/tmp.txt",
        "htmlcov/index.html",
        ".coverage",
        ".coverage.local",
        "coverage.xml",
        "junit.xml",
        "pytest-report.xml",
        "profile.prof",
        "coverage.profraw",
        "coverage.profdata",
        "GPD-FIX-REPORT-20260427.md",
        "GPD-FIX-REPORT/report.json",
        "GPD-FIX-REPORT-20260427/details.json",
        "GPD/state.json.bak",
        "GPD/state.json.lock",
    )
    for relpath in ignored_relpaths:
        path = repo / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("generated local artifact\n", encoding="utf-8")

    for relpath in ignored_relpaths:
        _git(repo, "check-ignore", "--quiet", "--", relpath)


def test_block_gpd_commit_hook_handles_staged_gpd_paths_with_spaces(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    (repo / "README.md").write_text("base\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "-c", "user.name=GPD Test", "-c", "user.email=gpd-test@example.invalid", "commit", "-m", "init")

    gpd_path = repo / "GPD" / "phase one" / "notes with spaces.md"
    keep_path = repo / "keep with spaces.txt"
    gpd_path.parent.mkdir(parents=True)
    gpd_path.write_text("runtime-owned\n", encoding="utf-8")
    keep_path.write_text("keep\n", encoding="utf-8")
    _git(repo, "add", str(gpd_path.relative_to(repo)), str(keep_path.relative_to(repo)))

    result = subprocess.run(
        ["bash", str(REPO_ROOT / "scripts" / "block-gpd-commit.sh")],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    staged = _git(repo, "diff", "--cached", "--name-only").stdout.splitlines()
    assert staged == ["keep with spaces.txt"]
    assert "GPD/phase one/notes with spaces.md" in result.stdout


def test_repo_hygiene_rejects_literal_only_asserts_in_tests() -> None:
    offenders = [
        location for rel_path in _tracked_test_python_paths() for location in _literal_only_assert_locations(rel_path)
    ]

    assert not offenders, "Literal-only asserts in tests are no-ops or unconditional failures:\n" + "\n".join(
        f"- {location}" for location in offenders
    )


def test_repo_hygiene_rejects_duplicate_test_definitions_in_same_scope() -> None:
    offenders = [
        location
        for rel_path in _tracked_test_python_paths()
        for location in _duplicate_test_definition_locations(rel_path)
    ]

    assert not offenders, "Duplicate test definitions in the same module/class scope hide earlier tests:\n" + "\n".join(
        f"- {location}" for location in offenders
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
