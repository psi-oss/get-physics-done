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
_WOLFRAM_INTEGRATION_BOUNDARY_FILES = {
    "src/gpd/core/tool_preflight.py",
    "src/gpd/cli.py",
    "src/gpd/mcp/managed_integrations.py",
}
_WOLFRAM_INTEGRATION_BOUNDARY_PREFIXES = (
    "src/gpd/adapters/",
    "src/gpd/mcp/integrations/",
)
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
        if rel_path.parts[:2] in {("tests", "core"), ("tests", "mcp")} or (
            len(rel_path.parts) == 2 and rel_path.name.startswith("test_")
        ):
            paths.append(path)
    return tuple(paths)


_SHARED_TEST_RUNTIME_SURFACE_PATHS = _shared_runtime_facing_test_paths()
_TEXT_SURFACE_SUFFIXES = {".json", ".md", ".py"}
_SHARED_GENERIC_PROVIDER_MODEL_TEST_PATHS = (
    REPO_ROOT / "tests/core/test_health.py",
    REPO_ROOT / "tests/core/test_runtime_hints.py",
    REPO_ROOT / "tests/core/test_costs.py",
    REPO_ROOT / "tests/core/test_cli.py",
    REPO_ROOT / "tests/hooks/test_notify.py",
    REPO_ROOT / "tests/hooks/test_statusline.py",
)
_SHARED_GENERIC_PROVIDER_MODEL_LITERAL_PATTERN = re.compile(
    r"""["'](?:openai|anthropic|google|gpt-[^"']+|claude-(?!code)[^"']+|gemini-(?!cli)[^"']+)["']"""
)


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


def _runtime_fixture_values() -> tuple[str, ...]:
    values: set[str] = set()
    for descriptor in _RUNTIME_DESCRIPTORS:
        for value in (
            descriptor.runtime_name,
            descriptor.display_name,
            descriptor.config_dir_name,
            descriptor.launch_command,
            descriptor.install_flag,
            descriptor.command_prefix,
            *descriptor.selection_aliases,
            *descriptor.selection_flags,
        ):
            if value:
                values.add(value)
    return tuple(sorted(values))


def _runtime_fixture_literal_findings(content: str) -> list[str]:
    fixture_values = _runtime_fixture_values()
    block_pattern = re.compile(r"(?s)(\[[^\[\]]*\]|\{[^\{\}]*\}|\([^\(\)]*\))")
    findings: list[str] = []
    seen_blocks: set[str] = set()
    for match in block_pattern.finditer(content):
        block = match.group(0)
        if block in seen_blocks:
            continue
        seen_blocks.add(block)
        matched_values = {
            value
            for value in fixture_values
            if re.search(rf'["\']{re.escape(value)}["\']', block)
        }
        # Flag partial runtime fixture blocks once they contain more than one
        # catalog token, even if the test does not mirror the full runtime list.
        if len(matched_values) >= 2:
            findings.append(block.replace("\n", " "))
    return findings


def _readme_optional_terminal_reference() -> str:
    content = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    match = re.search(
        r"<summary><strong>Optional Terminal-Side Readiness And Troubleshooting Reference</strong></summary>\n\n(?P<body>.*?)\n</details>",
        content,
        re.DOTALL,
    )
    if match is None:
        raise AssertionError("README optional terminal-side reference block not found")
    return match.group("body")


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


def test_shared_python_modules_keep_wolfram_integration_tokens_out_of_non_boundary_files() -> None:
    wolfram_pattern = re.compile(
        r"(gpd-wolfram|gpd-mcp-wolfram|GPD_WOLFRAM_MCP_API_KEY|GPD_WOLFRAM_MCP_ENDPOINT|WOLFRAM_MCP_SERVICE_API_KEY)"
    )
    leaks = [
        (path, line_no, snippet)
        for path, line_no, snippet in _git_grep(wolfram_pattern.pattern)
        if path.suffix == ".py"
        and path.parts[:2] == ("src", "gpd")
        and not any(path.as_posix().startswith(prefix) for prefix in _WOLFRAM_INTEGRATION_BOUNDARY_PREFIXES)
        and path.as_posix() not in _WOLFRAM_INTEGRATION_BOUNDARY_FILES
    ]

    assert leaks == [], (
        "Shared Python modules should keep Wolfram integration keys inside explicit boundary files:\n"
        f"{_format_failures(leaks)}"
    )


def test_shared_runtime_facing_tests_do_not_duplicate_runtime_catalog_literals() -> None:
    leaks: list[tuple[Path, int, str]] = []
    for path in _SHARED_TEST_RUNTIME_SURFACE_PATHS:
        content = path.read_text(encoding="utf-8")
        for block in _runtime_fixture_literal_findings(content):
            leaks.append((path, 0, f"hard-coded runtime fixture block: {block[:160]}"))

    assert leaks == [], (
        "Shared runtime-facing tests should derive supported runtime sets from the runtime catalog:\n"
        f"{_format_failures(leaks)}"
    )


def test_shared_generic_tests_do_not_hardcode_provider_or_model_literals() -> None:
    leaks = _scan_paths_for_pattern(
        _SHARED_GENERIC_PROVIDER_MODEL_TEST_PATHS,
        _SHARED_GENERIC_PROVIDER_MODEL_LITERAL_PATTERN,
    )

    assert leaks == [], (
        "Shared generic tests should use catalog-driven or placeholder runtime/provider/model fixtures:\n"
        f"{_format_failures(leaks)}"
    )


def test_readme_optional_terminal_reference_uses_runtime_placeholders() -> None:
    block = _readme_optional_terminal_reference()

    assert "--codex" not in block
    assert "--runtime codex" not in block
    assert "relaunch Codex" not in block
    assert "--<runtime-flag>" in block
    assert "--runtime <runtime>" in block
