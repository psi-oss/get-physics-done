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

from gpd.adapters import iter_adapters
from gpd.adapters.runtime_catalog import iter_runtime_descriptors

REPO_ROOT = Path(__file__).resolve().parent.parent

_RUNTIME_DESCRIPTORS = iter_runtime_descriptors()


def _runtime_env_prefix_patterns() -> list[str]:
    patterns: set[str] = set()
    for descriptor in _RUNTIME_DESCRIPTORS:
        for env_var in descriptor.activation_env_vars:
            patterns.add(re.escape(env_var))
            prefix = env_var.rsplit("_", 1)[0] if "_" in env_var else env_var
            patterns.add(rf"{re.escape(prefix)}_[A-Z0-9_]*")
        global_config = descriptor.global_config
        for env_var in (global_config.env_var, global_config.env_dir_var, global_config.env_file_var):
            if env_var:
                patterns.add(re.escape(env_var))
    return sorted(patterns)


def _runtime_literal_patterns() -> list[str]:
    patterns: set[str] = set()
    for descriptor in _RUNTIME_DESCRIPTORS:
        for value in (
            descriptor.display_name,
            descriptor.runtime_name,
            descriptor.config_dir_name,
            descriptor.launch_command,
            descriptor.install_flag,
            descriptor.global_config.env_var,
            descriptor.global_config.env_dir_var,
            descriptor.global_config.env_file_var,
            descriptor.global_config.home_subpath,
            descriptor.global_config.xdg_subdir,
        ):
            if value:
                patterns.add(re.escape(value))
        for value in descriptor.selection_flags:
            patterns.add(re.escape(value))
        for value in descriptor.selection_aliases:
            patterns.add(re.escape(value))
            if descriptor.command_prefix == "$gpd-":
                patterns.add(re.escape(descriptor.command_prefix))
    return sorted(patterns)


def _runtime_command_prefix_patterns() -> list[str]:
    return sorted({re.escape(descriptor.command_prefix) for descriptor in _RUNTIME_DESCRIPTORS if descriptor.command_prefix})


def _runtime_owned_path_patterns() -> list[str]:
    patterns: set[str] = set()
    for descriptor in _RUNTIME_DESCRIPTORS:
        for base in (descriptor.config_dir_name, descriptor.global_config.home_subpath):
            if not base:
                continue
            escaped_base = re.escape(base)
            patterns.add(rf"{escaped_base}/agents")
            patterns.add(rf"{escaped_base}/commands")
            patterns.add(rf"{escaped_base}/command")
    return sorted(patterns)

_RUNTIME_PATTERN = (
    "("
    + "|".join(
        [
            *_runtime_literal_patterns(),
            *_runtime_env_prefix_patterns(),
        ]
    )
    + ")"
)

_DOC_SUFFIXES = {".md"}
_RUNTIME_OWNED_PREFIXES = (
    *(f"{descriptor.config_dir_name}/" for descriptor in _RUNTIME_DESCRIPTORS),
    *(f"{descriptor.global_config.home_subpath}/" for descriptor in _RUNTIME_DESCRIPTORS if descriptor.global_config.home_subpath),
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
    *(f"src/gpd/adapters/{adapter.__class__.__module__.rsplit('.', 1)[-1]}.py" for adapter in iter_adapters()),
    "src/gpd/adapters/runtime_catalog.py",
    "src/gpd/adapters/runtime_catalog.json",
}
_SHARED_ADAPTER_RUNTIME_BRANCH_PATTERN = (
    r'(runtime\s*==\s*"|runtime\s+in\s+\(|runtime_name\s*==\s*"|runtime_name\s+in\s+\()'
)
_RUNTIME_INSTALL_ARTIFACT_PATTERN = re.compile(
    "("
    + "|".join(
        [
            r"SKILL\.md",
            r"CODEX_SKILLS_DIR",
            r"~\/\.agents/skills",
            *_runtime_owned_path_patterns(),
        ]
    )
    + ")"
)
_SHARED_COMMAND_SURFACE_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_.-])(?:"
    + "|".join(_runtime_command_prefix_patterns())
    + ")"
)
_SHARED_BOOTSTRAP_COMMAND_PATTERN = re.compile(
    r"(\bnpx\b|\bnpm\b|\buvx\b|\bpip\b|\bpipx\b|\bbunx\b|get-physics-done)"
)
_SHARED_RUNTIME_AGNOSTIC_PATHS = (
    REPO_ROOT / "src/gpd/agents",
    REPO_ROOT / "src/gpd/commands",
    REPO_ROOT / "src/gpd/specs",
    REPO_ROOT / "infra",
    REPO_ROOT / "src/gpd/registry.py",
    REPO_ROOT / "src/gpd/mcp/servers/skills_server.py",
)
def _shared_runtime_facing_test_paths() -> tuple[Path, ...]:
    paths: list[Path] = []
    for path in sorted((REPO_ROOT / "tests").rglob("*.py")):
        rel_path = path.relative_to(REPO_ROOT)
        if rel_path == Path("tests/test_runtime_abstraction_boundaries.py"):
            continue
        if rel_path.parts[:2] in {("tests", "adapters"), ("tests", "hooks")}:
            continue
        if rel_path.parts[:2] == ("tests", "core") or (len(rel_path.parts) == 2 and rel_path.name.startswith("test_")):
            paths.append(path)
    return tuple(paths)


_SHARED_TEST_RUNTIME_SURFACE_PATHS = _shared_runtime_facing_test_paths()
_TEXT_SURFACE_SUFFIXES = {".json", ".md", ".py"}


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


def _runtime_literal_sequence_pattern(values: tuple[str, ...]) -> re.Pattern[str]:
    quoted_values = [rf'["\']{re.escape(value)}["\']' for value in values]
    return re.compile(r"[\[(]\s*" + r"\s*,\s*".join(quoted_values) + r"\s*[\])]", re.DOTALL)


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


def test_shared_mcp_python_surfaces_do_not_hardcode_runtime_command_prefixes() -> None:
    leaks = _scan_paths_for_pattern((REPO_ROOT / "src/gpd/mcp",), _SHARED_COMMAND_SURFACE_PATTERN)

    assert leaks == [], (
        "Shared MCP Python surfaces should stay canonical instead of hardcoding runtime command prefixes:\n"
        f"{_format_failures(leaks)}"
    )


def test_shared_python_surfaces_do_not_hardcode_runtime_command_prefixes() -> None:
    leaks = _scan_paths_for_pattern((REPO_ROOT / "src/gpd",), _SHARED_COMMAND_SURFACE_PATTERN)
    leaks = [
        (path, line_no, snippet)
        for path, line_no, snippet in leaks
        if path.suffix == ".py"
        and not path.as_posix().startswith("src/gpd/adapters/")
        and not _is_allowed_shared_python_runtime_file(path)
    ]

    assert leaks == [], (
        "Shared Python surfaces should stay canonical instead of hardcoding runtime command prefixes:\n"
        f"{_format_failures(leaks)}"
    )


def test_shared_builtin_server_descriptors_do_not_hardcode_bootstrap_commands() -> None:
    leaks = _scan_paths_for_pattern((REPO_ROOT / "src/gpd/mcp/builtin_servers.py",), _SHARED_BOOTSTRAP_COMMAND_PATTERN)

    assert leaks == [], (
        "Shared built-in MCP descriptors should not hardcode runtime-specific bootstrap commands:\n"
        f"{_format_failures(leaks)}"
    )


def test_shared_runtime_facing_tests_do_not_duplicate_runtime_catalog_literals() -> None:
    runtime_names = tuple(descriptor.runtime_name for descriptor in _RUNTIME_DESCRIPTORS)
    install_flags = tuple(descriptor.install_flag for descriptor in _RUNTIME_DESCRIPTORS)
    name_pattern = _runtime_literal_sequence_pattern(runtime_names)
    flag_pattern = _runtime_literal_sequence_pattern(install_flags)

    leaks: list[tuple[Path, int, str]] = []
    for path in _SHARED_TEST_RUNTIME_SURFACE_PATHS:
        content = path.read_text(encoding="utf-8")
        if name_pattern.search(content):
            leaks.append((path, 0, "hard-coded supported runtime name tuple/list literal"))
        if flag_pattern.search(content):
            leaks.append((path, 0, "hard-coded supported runtime flag tuple/list literal"))

    assert leaks == [], (
        "Shared runtime-facing tests should derive supported runtime sets from the runtime catalog:\n"
        f"{_format_failures(leaks)}"
    )
