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
from types import SimpleNamespace

from gpd.adapters import iter_adapters
from gpd.adapters.runtime_catalog import get_shared_install_metadata, iter_runtime_descriptors
from gpd.command_labels import runtime_public_command_prefixes

REPO_ROOT = Path(__file__).resolve().parent.parent

_RUNTIME_DESCRIPTORS = iter_runtime_descriptors()
_SHARED_INSTALL = get_shared_install_metadata()


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


def _runtime_capability_surface_patterns() -> list[str]:
    patterns: set[str] = set()
    special_permission_surface_kinds = frozenset(
        descriptor.capabilities.permission_surface_kind
        for descriptor in _RUNTIME_DESCRIPTORS
        if descriptor.capabilities.permissions_surface != "config-file"
        and descriptor.capabilities.permission_surface_kind != "none"
    )
    for descriptor in _RUNTIME_DESCRIPTORS:
        capabilities = descriptor.capabilities
        for value in (
            capabilities.permission_surface_kind,
            capabilities.statusline_config_surface,
            capabilities.notify_config_surface,
        ):
            if value and value not in {"none", *special_permission_surface_kinds}:
                patterns.add(re.escape(value))
        if capabilities.permission_surface_kind in special_permission_surface_kinds:
            patterns.add(re.escape(capabilities.permission_surface_kind))
    return sorted(patterns)


def _runtime_public_command_surface_pattern() -> re.Pattern[str]:
    prefixes = runtime_public_command_prefixes()
    if not prefixes:
        return re.compile(r"$^")
    escaped_prefixes = "|".join(re.escape(prefix) for prefix in prefixes)
    return re.compile(r"(?<![A-Za-z0-9_.@/}\-])(?:" + escaped_prefixes + r")(?P<slug>[a-z0-9][a-z0-9-]*)(?!\.md\b)")


def _runtime_tool_alias_patterns() -> list[str]:
    aliases: set[str] = set()
    for adapter in iter_adapters():
        for canonical_name, runtime_name in adapter.tool_name_map.items():
            if runtime_name and runtime_name != canonical_name and re.search(r"[_-]", runtime_name):
                aliases.add(runtime_name)
    return sorted(aliases)


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
            *_runtime_capability_surface_patterns(),
            *_runtime_env_prefix_patterns(),
        ]
    )
    + ")"
)

_DOC_SUFFIXES = {".md"}
_RUNTIME_OWNED_PREFIXES = (
    *(f"{descriptor.config_dir_name}/" for descriptor in _RUNTIME_DESCRIPTORS),
    *(
        f"{descriptor.global_config.home_subpath}/"
        for descriptor in _RUNTIME_DESCRIPTORS
        if descriptor.global_config.home_subpath
    ),
    "src/gpd/adapters/",
)
_CAMPAIGN_EVIDENCE_PREFIXES = ("artifacts/bug-campaign/",)
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
_SHARED_COMMAND_SURFACE_PATTERN = _runtime_public_command_surface_pattern()
_SHARED_BOOTSTRAP_COMMAND_PATTERN = re.compile(r"(\bnpx\b|\bnpm\b|\buvx\b|\bpip\b|\bpipx\b|\bbunx\b|get-physics-done)")
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
        paths.append(path)
    return tuple(paths)


_SHARED_TEST_RUNTIME_SURFACE_PATHS = _shared_runtime_facing_test_paths()
_STRICT_SHARED_CORE_RUNTIME_SURFACE_PATHS = tuple(
    path
    for path in _SHARED_TEST_RUNTIME_SURFACE_PATHS
    if path.relative_to(REPO_ROOT).parts[:2] in {("tests", "core"), ("tests", "mcp")}
)
_STRICT_SHARED_CORE_RUNTIME_SURFACE_PATHS = (
    *_STRICT_SHARED_CORE_RUNTIME_SURFACE_PATHS,
    REPO_ROOT / "tests/test_bootstrap_installer.py",
)
_TEXT_SURFACE_SUFFIXES = {".json", ".md", ".py"}
_SHARED_GENERIC_PROVIDER_MODEL_TEST_PATHS = (
    REPO_ROOT / "tests/core/test_health.py",
    REPO_ROOT / "tests/core/test_runtime_hints.py",
    REPO_ROOT / "tests/core/test_costs.py",
    REPO_ROOT / "tests/core/test_cli.py",
    REPO_ROOT / "tests/test_cli_integration.py",
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
    return (
        rel_path.parts[:3] == ("src", "gpd", "commands")
        or rel_path.parts[:3]
        == (
            "src",
            "gpd",
            "agents",
        )
        or rel_path.parts[:3] == ("src", "gpd", "specs")
    )


def _is_test(rel_path: Path) -> bool:
    return rel_path.parts[:1] == ("tests",)


def _is_runtime_boundary_file(rel_path: Path) -> bool:
    rel = rel_path.as_posix()
    return (
        rel in _ALLOWED_RUNTIME_FILES
        or rel in _ALLOWED_RUNTIME_ADAPTER_FILES
        or any(rel.startswith(prefix) for prefix in _RUNTIME_OWNED_PREFIXES)
        or any(rel.startswith(prefix) for prefix in _CAMPAIGN_EVIDENCE_PREFIXES)
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
                candidate
                for candidate in path.rglob("*")
                if candidate.is_file() and candidate.suffix in _TEXT_SURFACE_SUFFIXES
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


def _runtime_fixture_literal_findings(content: str, *, minimum_matches: int = 2) -> list[str]:
    fixture_values = _runtime_fixture_values()
    block_pattern = re.compile(r"(?s)(\[[^\[\]]*\]|\{[^\{\}]*\}|\([^\(\)]*\))")
    findings: list[str] = []
    seen_blocks: set[str] = set()
    for match in block_pattern.finditer(content):
        block = match.group(0)
        if block in seen_blocks:
            continue
        seen_blocks.add(block)
        matched_values = {value for value in fixture_values if re.search(rf'["\']{re.escape(value)}["\']', block)}
        if len(matched_values) >= minimum_matches:
            findings.append(block.replace("\n", " "))
    return findings


def _runtime_tool_alias_literal_pattern() -> re.Pattern[str]:
    aliases = _runtime_tool_alias_patterns()
    if not aliases:
        return re.compile(r"$^")
    pieces = [rf'["\'`]{re.escape(alias)}["\'`]' for alias in aliases]
    return re.compile(rf"(?:{'|'.join(pieces)})")


def test_runtime_fixture_literal_findings_flags_single_runtime_literal_block() -> None:
    runtime_literal = _RUNTIME_DESCRIPTORS[0].runtime_name
    findings = _runtime_fixture_literal_findings(f'(["{runtime_literal}"])', minimum_matches=1)

    assert findings == [f'(["{runtime_literal}"])']


def test_runtime_pattern_includes_capability_surface_literals() -> None:
    capability_literals = (
        "settings.json:permissions.defaultMode",
        "settings.json:statusLine",
        "config.toml:approval_policy+sandbox_mode",
        "config.toml:notify",
        "opencode.json:permission",
    )

    for literal in capability_literals:
        assert re.search(_RUNTIME_PATTERN, literal) is not None


def test_loaded_runtime_descriptors_keep_public_command_surfaces_descriptor_owned() -> None:
    public_prefixes = {descriptor.public_command_surface_prefix for descriptor in _RUNTIME_DESCRIPTORS}

    assert all(public_prefixes)
    assert public_prefixes == {descriptor.command_prefix for descriptor in _RUNTIME_DESCRIPTORS}


def test_runtime_public_command_prefixes_use_descriptor_public_surface(monkeypatch) -> None:
    descriptors = (
        SimpleNamespace(public_command_surface_prefix="/public:", command_prefix="/adapter-only:"),
        SimpleNamespace(public_command_surface_prefix="$public-", command_prefix="$adapter-only-"),
    )
    monkeypatch.setattr("gpd.adapters.runtime_catalog.iter_runtime_descriptors", lambda: descriptors)
    runtime_public_command_prefixes.cache_clear()
    try:
        prefixes = runtime_public_command_prefixes()
    finally:
        runtime_public_command_prefixes.cache_clear()

    assert set(prefixes) == {"/public:", "$public-"}
    assert "/adapter-only:" not in prefixes
    assert "$adapter-only-" not in prefixes


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
        f"Runtime-specific hardcoding leaked outside adapter/runtime boundary files:\n{_format_failures(leaks)}"
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
        f"Shared adapter infrastructure should not hardcode runtime-specific terms:\n{_format_failures(leaks)}"
    )


def test_shared_adapter_infrastructure_stays_runtime_agnostic() -> None:
    leaks = [
        (path, line_no, snippet)
        for path, line_no, snippet in _git_grep(_SHARED_ADAPTER_RUNTIME_BRANCH_PATTERN)
        if path.parts[:3] == ("src", "gpd", "adapters") and path.as_posix() not in _ALLOWED_RUNTIME_ADAPTER_FILES
    ]

    assert leaks == [], (
        f"Shared adapter infrastructure should not hardcode runtime-specific terms:\n{_format_failures(leaks)}"
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


def test_shared_markdown_surfaces_do_not_hardcode_runtime_command_prefixes() -> None:
    leaks = _scan_paths_for_pattern(
        (
            REPO_ROOT / "src/gpd/commands",
            REPO_ROOT / "src/gpd/agents",
            REPO_ROOT / "src/gpd/specs",
        ),
        _SHARED_COMMAND_SURFACE_PATTERN,
    )

    assert leaks == [], (
        "Shared markdown surfaces should stay canonical instead of hardcoding runtime command prefixes:\n"
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


def test_shared_source_surfaces_do_not_hardcode_runtime_tool_alias_literals() -> None:
    alias_pattern = _runtime_tool_alias_literal_pattern()
    leaks = _scan_paths_for_pattern((REPO_ROOT / "src/gpd",), alias_pattern)
    leaks = [
        (path, line_no, snippet)
        for path, line_no, snippet in leaks
        if path.suffix in {".py", ".md", ".json", ".toml"}
        and not path.as_posix().startswith("src/gpd/adapters/")
        and path.as_posix() != "src/gpd/hooks/runtime_detect.py"
    ]

    assert leaks == [], (
        "Shared source surfaces should not hardcode runtime-specific tool aliases outside adapter files:\n"
        f"{_format_failures(leaks)}"
    )


def test_shared_builtin_server_descriptors_do_not_hardcode_bootstrap_commands() -> None:
    leaks = _scan_paths_for_pattern((REPO_ROOT / "src/gpd/mcp/builtin_servers.py",), _SHARED_BOOTSTRAP_COMMAND_PATTERN)

    assert leaks == [], (
        "Shared built-in MCP descriptors should not hardcode runtime-specific bootstrap commands:\n"
        f"{_format_failures(leaks)}"
    )


def test_shared_runtime_docs_do_not_rebuild_install_metadata_literals() -> None:
    doc_paths = (
        REPO_ROOT / "src/gpd/specs/workflows/update.md",
        REPO_ROOT / "src/gpd/specs/workflows/reapply-patches.md",
        REPO_ROOT / "src/gpd/specs/references/tooling/runtime-config-guide.md",
    )
    disallowed_literals = (
        _SHARED_INSTALL.bootstrap_command,
        _SHARED_INSTALL.latest_release_url,
        _SHARED_INSTALL.releases_api_url,
        _SHARED_INSTALL.releases_page_url,
        _SHARED_INSTALL.patches_dir_name,
    )

    leaks: list[tuple[Path, int, str]] = []
    for path in doc_paths:
        rel_path = path.relative_to(REPO_ROOT)
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if any(literal in line for literal in disallowed_literals):
                leaks.append((rel_path, line_no, line))

    assert leaks == [], (
        "Shared runtime-facing docs should consume install metadata placeholders instead of hardcoded literals:\n"
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


def test_shared_core_runtime_surface_tests_do_not_hardcode_single_runtime_catalog_literals() -> None:
    leaks: list[tuple[Path, int, str]] = []
    for path in _STRICT_SHARED_CORE_RUNTIME_SURFACE_PATHS:
        content = path.read_text(encoding="utf-8")
        for block in _runtime_fixture_literal_findings(content, minimum_matches=1):
            leaks.append((path, 0, f"hard-coded single-runtime fixture block: {block[:160]}"))

    assert leaks == [], (
        "Shared core runtime-surface tests should derive runtime literals from the runtime catalog:\n"
        f"{_format_failures(leaks)}"
    )


def test_bootstrap_installer_does_not_hardcode_runtime_name_or_display_name_literals() -> None:
    bootstrap_path = REPO_ROOT / "tests/test_bootstrap_installer.py"
    runtime_literals = tuple(
        sorted(
            {
                value
                for descriptor in _RUNTIME_DESCRIPTORS
                for value in (descriptor.runtime_name, descriptor.display_name)
                if value
            }
        )
    )
    runtime_literal_pattern = re.compile(
        r"(?<![A-Za-z0-9_.-])(?:" + "|".join(re.escape(value) for value in runtime_literals) + r")(?![A-Za-z0-9_.-])"
    )

    leaks = [
        (bootstrap_path, line_no, line)
        for line_no, line in enumerate(bootstrap_path.read_text(encoding="utf-8").splitlines(), start=1)
        if runtime_literal_pattern.search(line)
    ]

    assert leaks == [], (
        "Bootstrap installer tests should derive runtime examples from the runtime catalog instead of hardcoding names:\n"
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


def test_user_facing_runtime_command_hints_use_runtime_placeholder() -> None:
    leaks = _scan_paths_for_pattern(
        (
            REPO_ROOT / "src/gpd/cli.py",
            REPO_ROOT / "src/gpd/core/health.py",
            REPO_ROOT / "src/gpd/specs/workflows/new-project.md",
        ),
        re.compile(r"--runtime <name>"),
    )

    assert leaks == [], (
        f"User-facing runtime command hints should use the canonical <runtime> placeholder:\n{_format_failures(leaks)}"
    )
