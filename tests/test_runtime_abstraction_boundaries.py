"""Guard runtime-specific vocabulary boundaries in the tracked repo.

These tests intentionally allow runtime hardcoding only in explicit boundary
layers:

- runtime adapters
- runtime-detection / runtime-specific hook shims
- checked-in runtime-owned mirrors and config snapshots
- repo metadata that intentionally ignores runtime-owned mirrors

Everywhere else, shared code should stay runtime-agnostic.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

_RUNTIME_PATTERN = (
    r"(Claude Code|Gemini CLI|Codex|OpenCode|claude-code|gemini|codex|opencode|"
    r"\.claude|\.gemini|\.codex|\.opencode|"
    r"CLAUDE_[A-Z0-9_]*|GEMINI_[A-Z0-9_]*|CODEX_[A-Z0-9_]*|OPENCODE_[A-Z0-9_]*|"
    r"codex_notify\.py)"
)

_DOC_SUFFIXES = {".md"}
_RUNTIME_OWNED_PREFIXES = (
    ".claude/",
    ".codex/",
    ".gemini/",
    ".opencode/",
    "src/gpd/adapters/",
)
_ALLOWED_RUNTIME_FILES = {
    "CITATION.cff",
    ".gitignore",
    "package.json",
    "pyproject.toml",
    "src/gpd/hooks/runtime_detect.py",
}
_ALLOWED_SHARED_PYTHON_RUNTIME_FILES = {
    "src/gpd/hooks/runtime_detect.py",
}
_SHARED_ADAPTER_INFRA_FILES = {
    "src/gpd/adapters/__init__.py",
    "src/gpd/adapters/base.py",
    "src/gpd/adapters/install_utils.py",
    "src/gpd/adapters/tool_names.py",
}
_ALLOWED_RUNTIME_ADAPTER_FILES = {
    "src/gpd/adapters/claude_code.py",
    "src/gpd/adapters/codex.py",
    "src/gpd/adapters/gemini.py",
    "src/gpd/adapters/opencode.py",
    "src/gpd/adapters/runtime_catalog.py",
    "src/gpd/adapters/runtime_catalog.json",
}
_SHARED_ADAPTER_RUNTIME_BRANCH_PATTERN = (
    r'(runtime\s*==\s*"|runtime\s+in\s+\(|runtime_name\s*==\s*"|runtime_name\s+in\s+\()'
)
_RUNTIME_INSTALL_ARTIFACT_PATTERN = re.compile(
    r"(SKILL\.md|CODEX_SKILLS_DIR|~\/\.agents/skills|\.claude/agents|\.codex/agents|"
    r"\.gemini/agents|\.opencode/agents|\.claude/commands|\.gemini/commands|\.opencode/commands)"
)
_SHARED_RUNTIME_AGNOSTIC_PATHS = (
    REPO_ROOT / "src/gpd/agents",
    REPO_ROOT / "src/gpd/commands",
    REPO_ROOT / "src/gpd/specs",
    REPO_ROOT / "src/gpd/registry.py",
    REPO_ROOT / "src/gpd/mcp/servers/skills_server.py",
)
_TEXT_SURFACE_SUFFIXES = {".md", ".py"}


def _git_grep(pattern: str) -> list[tuple[Path, int, str]]:
    result = subprocess.run(
        ["git", "grep", "-n", "-I", "-E", pattern],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode not in (0, 1):
        raise AssertionError(result.stderr or result.stdout)

    matches: list[tuple[Path, int, str]] = []
    for line in result.stdout.splitlines():
        rel_path_str, line_no_str, snippet = line.split(":", 2)
        matches.append((Path(rel_path_str), int(line_no_str), snippet))
    return matches


def _is_doc(rel_path: Path) -> bool:
    return rel_path.suffix.lower() in _DOC_SUFFIXES


def _is_installed_shared_markdown(rel_path: Path) -> bool:
    return rel_path.parts[:3] == ("src", "gpd", "commands") or rel_path.parts[:3] == (
        "src",
        "gpd",
        "agents",
    ) or rel_path.parts[:3] == ("src", "gpd", "specs")


def _is_test(rel_path: Path) -> bool:
    return rel_path.parts[:1] == ("tests",)


def _is_runtime_boundary_file(rel_path: Path) -> bool:
    rel = rel_path.as_posix()
    return (
        rel in _ALLOWED_RUNTIME_FILES
        or rel in _ALLOWED_RUNTIME_ADAPTER_FILES
        or any(rel.startswith(prefix) for prefix in _RUNTIME_OWNED_PREFIXES)
    )


def _is_allowed_shared_python_runtime_file(rel_path: Path) -> bool:
    return rel_path.as_posix() in _ALLOWED_SHARED_PYTHON_RUNTIME_FILES


def _format_failures(matches: list[tuple[Path, int, str]]) -> str:
    lines = [f"{path}:{line_no}: {snippet}" for path, line_no, snippet in matches]
    return "\n".join(lines)


def _scan_paths_for_pattern(paths: tuple[Path, ...], pattern: re.Pattern[str]) -> list[tuple[Path, int, str]]:
    matches: list[tuple[Path, int, str]] = []
    for path in paths:
        if path.is_file():
            candidates = [path]
        else:
            candidates = sorted(
                candidate for candidate in path.rglob("*") if candidate.is_file() and candidate.suffix in _TEXT_SURFACE_SUFFIXES
            )
        for candidate in candidates:
            if candidate.suffix not in _TEXT_SURFACE_SUFFIXES:
                continue
            rel_path = candidate.relative_to(REPO_ROOT)
            for line_no, line in enumerate(candidate.read_text(encoding="utf-8").splitlines(), start=1):
                if pattern.search(line):
                    matches.append((rel_path, line_no, line))
    return matches


def test_runtime_specific_terms_are_confined_to_explicit_boundary_files() -> None:
    leaks = [
        (path, line_no, snippet)
        for path, line_no, snippet in _git_grep(_RUNTIME_PATTERN)
        if not _is_test(path)
        and not _is_runtime_boundary_file(path)
        and (not _is_doc(path) or _is_installed_shared_markdown(path))
    ]

    assert leaks == [], (
        "Runtime-specific hardcoding leaked outside adapter/runtime boundary files:\n"
        f"{_format_failures(leaks)}"
    )


def test_shared_python_modules_do_not_hardcode_runtime_terms() -> None:
    leaks = [
        (path, line_no, snippet)
        for path, line_no, snippet in _git_grep(_RUNTIME_PATTERN)
        if path.suffix == ".py"
        and path.parts[:2] == ("src", "gpd")
        and not path.as_posix().startswith("src/gpd/adapters/")
        and not _is_allowed_shared_python_runtime_file(path)
    ]

    assert leaks == [], (
        "Shared Python modules should stay runtime-agnostic outside explicit boundary files:\n"
        f"{_format_failures(leaks)}"
    )


def test_shared_adapter_infrastructure_avoids_runtime_specific_hardcoding() -> None:
    leaks = [
        (path, line_no, snippet)
        for path, line_no, snippet in _git_grep(_RUNTIME_PATTERN)
        if path.as_posix() in _SHARED_ADAPTER_INFRA_FILES
    ]

    assert leaks == [], (
        "Shared adapter infrastructure should not hardcode runtime-specific terms:\n"
        f"{_format_failures(leaks)}"
    )


def test_shared_adapter_infrastructure_stays_runtime_agnostic() -> None:
    leaks = [
        (path, line_no, snippet)
        for path, line_no, snippet in _git_grep(_SHARED_ADAPTER_RUNTIME_BRANCH_PATTERN)
        if path.parts[:3] == ("src", "gpd", "adapters")
        and path.as_posix() not in _ALLOWED_RUNTIME_ADAPTER_FILES
    ]

    assert leaks == [], (
        "Shared adapter infrastructure should not hardcode runtime-specific terms:\n"
        f"{_format_failures(leaks)}"
    )


def test_shared_canonical_surfaces_do_not_reference_runtime_install_artifacts() -> None:
    leaks = _scan_paths_for_pattern(_SHARED_RUNTIME_AGNOSTIC_PATHS, _RUNTIME_INSTALL_ARTIFACT_PATTERN)

    assert leaks == [], (
        "Shared commands, agents, specs, and canonical registry/MCP surfaces should not reference runtime install artifacts:\n"
        f"{_format_failures(leaks)}"
    )
