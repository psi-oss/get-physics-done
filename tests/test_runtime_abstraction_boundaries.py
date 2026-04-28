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

import ast
import json
import re
import subprocess
from dataclasses import fields
from pathlib import Path
from types import SimpleNamespace

from gpd.adapters import get_adapter, iter_adapters
from gpd.adapters.base import RuntimeAdapter
from gpd.adapters.runtime_catalog import (
    ManagedInstallSurfacePolicy,
    get_hook_payload_policy,
    get_shared_install_metadata,
    iter_runtime_descriptors,
)
from gpd.command_labels import runtime_public_command_prefixes

REPO_ROOT = Path(__file__).resolve().parent.parent

_RUNTIME_DESCRIPTORS = iter_runtime_descriptors()
_SHARED_INSTALL = get_shared_install_metadata()
_RUNTIME_COMMAND_SURFACE_LEFT_BOUNDARY = r"(^|[^A-Za-z0-9_.@/}\-])"


def _runtime_command_surface_prefix_literal_pattern(prefix: str) -> str:
    return _RUNTIME_COMMAND_SURFACE_LEFT_BOUNDARY + re.escape(prefix)


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
        for prefix in (descriptor.command_prefix, descriptor.public_command_surface_prefix):
            if prefix:
                patterns.add(_runtime_command_surface_prefix_literal_pattern(prefix))
        for value in descriptor.selection_flags:
            patterns.add(re.escape(value))
        for value in descriptor.selection_aliases:
            patterns.add(re.escape(value))
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
_COMMANDS_DIR = REPO_ROOT / "src/gpd/commands"
_RAW_PROJECT_INCLUDE_PATTERN = re.compile(r"@GPD/")


def _command_context_mode(path: Path) -> str | None:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return None
    frontmatter_end = text.find("\n---", 4)
    if frontmatter_end == -1:
        return None
    frontmatter = text[4:frontmatter_end]
    match = re.search(r"(?m)^context_mode:\s*(?P<mode>[a-z-]+)\s*$", frontmatter)
    if match is None:
        return None
    return match.group("mode")


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
_ROOT_RUNTIME_SURFACE_TEST_NAME_TOKENS = ("runtime", "install", "registry", "update")
_EXPLICIT_ROOT_RUNTIME_SURFACE_TESTS = {
    "tests/test_command_label_normalization.py",
    "tests/test_cli_integration.py",
}
_STRICT_ROOT_RUNTIME_LITERAL_ALLOWLIST: frozenset[str] = frozenset()


def _is_root_runtime_surface_test(path: Path) -> bool:
    rel_path = path.relative_to(REPO_ROOT)
    if len(rel_path.parts) != 2 or rel_path.parts[0] != "tests" or not rel_path.name.startswith("test_"):
        return False
    return rel_path.as_posix() in _EXPLICIT_ROOT_RUNTIME_SURFACE_TESTS or any(
        token in rel_path.name for token in _ROOT_RUNTIME_SURFACE_TEST_NAME_TOKENS
    )


def _is_root_shared_test_helper(path: Path) -> bool:
    rel_path = path.relative_to(REPO_ROOT)
    return len(rel_path.parts) == 2 and rel_path.parts[0] == "tests" and not rel_path.name.startswith("test_")


_BOOTSTRAP_INSTALLER_TEST_PATH = REPO_ROOT / "tests/test_bootstrap_installer.py"
_STRICT_SHARED_CORE_RUNTIME_SURFACE_PATHS = tuple(
    path
    for path in _SHARED_TEST_RUNTIME_SURFACE_PATHS
    if path.relative_to(REPO_ROOT).parts[:2] in {("tests", "core"), ("tests", "mcp")}
    or _is_root_shared_test_helper(path)
    or (
        _is_root_runtime_surface_test(path)
        and path.relative_to(REPO_ROOT).as_posix() not in _STRICT_ROOT_RUNTIME_LITERAL_ALLOWLIST
    )
)
_STRICT_SHARED_CORE_RUNTIME_SURFACE_PATHS = tuple(
    dict.fromkeys((*_STRICT_SHARED_CORE_RUNTIME_SURFACE_PATHS, _BOOTSTRAP_INSTALLER_TEST_PATH))
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
_SHARED_HOOK_PAYLOAD_POLICY_CONSUMER_PATHS = (
    REPO_ROOT / "src/gpd/hooks/notify.py",
    REPO_ROOT / "src/gpd/hooks/payload_roots.py",
    REPO_ROOT / "src/gpd/hooks/statusline.py",
    REPO_ROOT / "tests/hooks/test_notify.py",
    REPO_ROOT / "tests/hooks/test_payload_roots.py",
    REPO_ROOT / "tests/hooks/test_statusline.py",
)
_RUNTIME_ADAPTER_IMPLEMENTATION_PATHS = tuple(
    REPO_ROOT / f"src/gpd/adapters/{adapter.__class__.__module__.rsplit('.', 1)[-1]}.py" for adapter in iter_adapters()
)
_RUNTIME_ADAPTER_MODULE_NAMES = frozenset(adapter.__class__.__module__ for adapter in iter_adapters())
_ADAPTER_PRIVATE_IMPORT_ALLOWLIST: frozenset[tuple[str, str, str]] = frozenset()
_RUNTIME_BRIDGE_SHELL_FENCE_LANGUAGES = frozenset({"bash", "sh", "shell", "zsh"})


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
    )


def _is_allowed_shared_python_runtime_file(rel_path: Path) -> bool:
    return rel_path.as_posix() in _ALLOWED_SHARED_PYTHON_RUNTIME_FILES


def _format_failures(matches: list[tuple[Path, int, str]]) -> str:
    lines = [f"{path}:{line_no}: {snippet}" for path, line_no, snippet in matches]
    return "\n".join(lines)


def _non_adapter_test_python_paths() -> tuple[Path, ...]:
    paths: list[Path] = []
    for path in sorted((REPO_ROOT / "tests").rglob("*.py")):
        rel_path = path.relative_to(REPO_ROOT)
        if rel_path == Path("tests/test_runtime_abstraction_boundaries.py"):
            continue
        if rel_path.parts[:2] == ("tests", "adapters"):
            continue
        paths.append(path)
    return tuple(paths)


def _is_allowed_adapter_private_import(rel_path: Path, module_name: str, symbol_name: str) -> bool:
    return (rel_path.as_posix(), module_name, symbol_name) in _ADAPTER_PRIVATE_IMPORT_ALLOWLIST


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


def _runtime_name_or_display_literal_values() -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                value
                for descriptor in _RUNTIME_DESCRIPTORS
                for value in (descriptor.runtime_name, descriptor.display_name)
                if value
            }
        )
    )


def _runtime_command_surface_prefix_values() -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                prefix
                for descriptor in _RUNTIME_DESCRIPTORS
                for prefix in (descriptor.command_prefix, descriptor.public_command_surface_prefix)
                if prefix
            }
        )
    )


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


def _standalone_runtime_name_or_display_literal_findings(content: str) -> list[tuple[int, str]]:
    tree = ast.parse(content)
    runtime_literals = set(_runtime_name_or_display_literal_values())
    findings: list[tuple[int, str]] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in runtime_literals:
            findings.append((node.lineno, node.value))

    return findings


def _runtime_tool_alias_literal_pattern() -> re.Pattern[str]:
    aliases = _runtime_tool_alias_patterns()
    if not aliases:
        return re.compile(r"$^")
    pieces = [rf'["\'`]{re.escape(alias)}["\'`]' for alias in aliases]
    return re.compile(rf"(?:{'|'.join(pieces)})")


def _literal_string_tuple(node: ast.AST) -> tuple[str, ...] | None:
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "frozenset"
        and len(node.args) == 1
        and not node.keywords
    ):
        return _literal_string_tuple(node.args[0])
    if not isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return None

    values: list[str] = []
    for element in node.elts:
        if not isinstance(element, ast.Constant) or not isinstance(element.value, str):
            return None
        values.append(element.value)
    return tuple(values)


def _assignment_target_names(node: ast.Assign | ast.AnnAssign) -> tuple[str, ...]:
    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
    names: list[str] = []

    def collect(target: ast.AST) -> None:
        if isinstance(target, ast.Name):
            names.append(target.id)
        elif isinstance(target, ast.Attribute):
            names.append(target.attr)
        elif isinstance(target, (ast.Tuple, ast.List)):
            for element in target.elts:
                collect(element)

    for target in targets:
        collect(target)
    return tuple(names)


def _runtime_hook_payload_key_tuples() -> dict[tuple[str, ...], set[str]]:
    key_tuples: dict[tuple[str, ...], set[str]] = {}
    for descriptor in _RUNTIME_DESCRIPTORS:
        for field in fields(descriptor.hook_payload):
            if not field.name.endswith("_keys"):
                continue
            values = getattr(descriptor.hook_payload, field.name)
            if values:
                key_tuples.setdefault(tuple(values), set()).add(field.name)
    return key_tuples


def _runtime_hook_payload_key_literals() -> set[str]:
    literals: set[str] = set()
    for descriptor in _RUNTIME_DESCRIPTORS:
        for field in fields(descriptor.hook_payload):
            if not field.name.endswith("_keys"):
                continue
            literals.update(getattr(descriptor.hook_payload, field.name))
    return literals


def test_merged_hook_payload_policy_is_descriptor_wise_union_for_every_field() -> None:
    merged_policy = get_hook_payload_policy()

    for field in fields(merged_policy):
        expected_values: list[str] = []
        for descriptor in _RUNTIME_DESCRIPTORS:
            for value in getattr(descriptor.hook_payload, field.name):
                if value not in expected_values:
                    expected_values.append(value)

        assert getattr(merged_policy, field.name) == tuple(expected_values)


def test_shared_hook_policy_consumers_do_not_duplicate_catalog_hook_payload_key_tuples() -> None:
    catalog_key_tuples = _runtime_hook_payload_key_tuples()
    leaks: list[tuple[Path, int, str]] = []

    for path in _SHARED_HOOK_PAYLOAD_POLICY_CONSUMER_PATHS:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        rel_path = path.relative_to(REPO_ROOT)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            target_names = _assignment_target_names(node)
            if not any("key" in name.casefold() for name in target_names):
                continue
            literal = _literal_string_tuple(node.value)
            if literal not in catalog_key_tuples:
                continue
            fields_text = ", ".join(sorted(catalog_key_tuples[literal]))
            leaks.append(
                (
                    rel_path,
                    node.lineno,
                    f"{', '.join(target_names)} duplicates runtime_catalog hook_payload {fields_text}",
                )
            )

    assert leaks == [], (
        "Shared hooks and hook tests should consume hook payload keys from runtime_catalog policies instead of duplicating them:\n"
        f"{_format_failures(leaks)}"
    )


def test_notify_and_statusline_do_not_hardcode_project_dir_payload_key() -> None:
    leaks: list[tuple[Path, int, str]] = []

    catalog_key_literals = _runtime_hook_payload_key_literals()
    consumer_paths = (
        REPO_ROOT / "src/gpd/hooks/notify.py",
        REPO_ROOT / "src/gpd/hooks/statusline.py",
    )
    for path in consumer_paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        rel_path = path.relative_to(REPO_ROOT)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            is_payload_lookup = (isinstance(func, ast.Attribute) and func.attr == "get") or (
                isinstance(func, ast.Name) and func.id in {"_first_string", "_first_value"}
            )
            if not is_payload_lookup:
                continue
            for argument in node.args:
                if isinstance(argument, ast.Constant) and argument.value in catalog_key_literals:
                    leaks.append((rel_path, argument.lineno, f"hard-coded payload key {argument.value!r}"))

    assert leaks == [], (
        "shared hook consumers must read runtime payload keys through runtime_catalog hook_payload policies:\n"
        f"{_format_failures(leaks)}"
    )


def test_runtime_adapters_use_shared_shell_fence_language_constant() -> None:
    leaks: list[tuple[Path, int, str]] = []
    for path in _RUNTIME_ADAPTER_IMPLEMENTATION_PATHS:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        rel_path = path.relative_to(REPO_ROOT)
        for node in ast.walk(tree):
            literal = _literal_string_tuple(node)
            if literal is not None and frozenset(literal) == _RUNTIME_BRIDGE_SHELL_FENCE_LANGUAGES:
                leaks.append((rel_path, node.lineno, "duplicate runtime bridge shell fence languages literal"))

    assert leaks == [], (
        "Runtime adapters should use DEFAULT_RUNTIME_BRIDGE_SHELL_FENCE_LANGUAGES from install_utils:\n"
        f"{_format_failures(leaks)}"
    )


def test_non_adapter_tests_do_not_import_runtime_adapter_private_symbols() -> None:
    runtime_adapter_modules = _RUNTIME_ADAPTER_MODULE_NAMES
    runtime_adapter_module_by_leaf = {
        module_name.rsplit(".", 1)[-1]: module_name for module_name in runtime_adapter_modules
    }
    private_path_pattern = re.compile(
        r"\b(?P<module>"
        + "|".join(re.escape(module_name) for module_name in sorted(runtime_adapter_modules))
        + r")\.(?P<symbol>_[A-Za-z][A-Za-z0-9_]*)"
    )
    leaks: list[tuple[Path, int, str]] = []

    for path in _non_adapter_test_python_paths():
        rel_path = path.relative_to(REPO_ROOT)
        content = path.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(path))
        adapter_module_aliases: dict[str, str] = {}

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in runtime_adapter_modules:
                        adapter_module_aliases[alias.asname or alias.name.rsplit(".", 1)[-1]] = alias.name
            elif isinstance(node, ast.ImportFrom):
                if node.module in runtime_adapter_modules:
                    for alias in node.names:
                        symbol_name = alias.name
                        if symbol_name == "*" or symbol_name.startswith("_"):
                            if not _is_allowed_adapter_private_import(rel_path, node.module, symbol_name):
                                leaks.append(
                                    (
                                        rel_path,
                                        node.lineno,
                                        f"imports private runtime adapter symbol {node.module}.{symbol_name}",
                                    )
                                )
                elif node.module == "gpd.adapters":
                    for alias in node.names:
                        module_name = runtime_adapter_module_by_leaf.get(alias.name)
                        if module_name is not None:
                            adapter_module_aliases[alias.asname or alias.name] = module_name

        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Attribute)
                and node.attr.startswith("_")
                and isinstance(node.value, ast.Name)
                and node.value.id in adapter_module_aliases
                and not _is_allowed_adapter_private_import(rel_path, adapter_module_aliases[node.value.id], node.attr)
            ):
                leaks.append(
                    (
                        rel_path,
                        node.lineno,
                        f"accesses private runtime adapter symbol {adapter_module_aliases[node.value.id]}.{node.attr}",
                    )
                )
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                for match in private_path_pattern.finditer(node.value):
                    module_name = match.group("module")
                    symbol_name = match.group("symbol")
                    if _is_allowed_adapter_private_import(rel_path, module_name, symbol_name):
                        continue
                    leaks.append(
                        (
                            rel_path,
                            node.lineno,
                            f"references private runtime adapter symbol {module_name}.{symbol_name}",
                        )
                    )

    assert leaks == [], (
        "Non-adapter tests should exercise runtime adapter internals only through tests/adapters "
        "or public adapter APIs:\n"
        f"{_format_failures(leaks)}"
    )


def test_runtime_fixture_literal_findings_flags_single_runtime_literal_block() -> None:
    runtime_literal = _RUNTIME_DESCRIPTORS[0].runtime_name
    findings = _runtime_fixture_literal_findings(f'(["{runtime_literal}"])', minimum_matches=1)

    assert findings == [f'(["{runtime_literal}"])']


def test_standalone_runtime_literal_findings_flags_single_runtime_display_literal() -> None:
    runtime_literal = next(
        descriptor.display_name
        for descriptor in _RUNTIME_DESCRIPTORS
        if descriptor.display_name != descriptor.runtime_name
    )
    findings = _standalone_runtime_name_or_display_literal_findings(f'assert "{runtime_literal}" not in content\n')

    assert findings == [(1, runtime_literal)]


def test_runtime_pattern_includes_capability_surface_literals() -> None:
    capability_literals = tuple(
        sorted(
            {
                value
                for descriptor in _RUNTIME_DESCRIPTORS
                for value in (
                    descriptor.capabilities.permission_surface_kind,
                    descriptor.capabilities.statusline_config_surface,
                    descriptor.capabilities.notify_config_surface,
                )
                if value and value != "none"
            }
        )
    )

    assert capability_literals
    for literal in capability_literals:
        assert re.search(_RUNTIME_PATTERN, literal) is not None


def test_runtime_pattern_includes_descriptor_command_surface_prefix_literals() -> None:
    prefixes = _runtime_command_surface_prefix_values()

    assert prefixes
    for prefix in prefixes:
        assert re.search(_RUNTIME_PATTERN, prefix) is not None


def test_runtime_pattern_includes_bare_slash_command_surface_prefix_literals() -> None:
    slash_prefixes = tuple(prefix for prefix in _runtime_command_surface_prefix_values() if prefix.startswith("/"))

    assert slash_prefixes
    for prefix in slash_prefixes:
        assert re.search(_RUNTIME_PATTERN, prefix) is not None


def test_loaded_runtime_descriptors_keep_public_command_surfaces_descriptor_owned() -> None:
    public_prefixes = {descriptor.public_command_surface_prefix for descriptor in _RUNTIME_DESCRIPTORS}
    command_prefixes = {descriptor.command_prefix for descriptor in _RUNTIME_DESCRIPTORS}

    assert all(public_prefixes)
    assert all(command_prefixes)
    assert all(descriptor.public_command_surface_prefix for descriptor in _RUNTIME_DESCRIPTORS)


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


def test_strict_runtime_literal_guard_covers_root_level_runtime_facing_tests() -> None:
    strict_relpaths = {path.relative_to(REPO_ROOT).as_posix() for path in _STRICT_SHARED_CORE_RUNTIME_SURFACE_PATHS}
    expected_root_relpaths = {
        path.relative_to(REPO_ROOT).as_posix()
        for path in _SHARED_TEST_RUNTIME_SURFACE_PATHS
        if _is_root_runtime_surface_test(path)
    }

    assert _STRICT_ROOT_RUNTIME_LITERAL_ALLOWLIST == frozenset()
    assert expected_root_relpaths - _STRICT_ROOT_RUNTIME_LITERAL_ALLOWLIST <= strict_relpaths
    assert not (_STRICT_ROOT_RUNTIME_LITERAL_ALLOWLIST & strict_relpaths)
    assert {
        "tests/test_runtime_cli.py",
        "tests/test_runtime_catalog_bootstrap_contract.py",
        "tests/test_command_label_normalization.py",
        "tests/test_cli_integration.py",
        "tests/test_registry.py",
        "tests/test_update_workflow.py",
    } <= strict_relpaths


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


def test_projectless_and_global_commands_do_not_eagerly_include_project_files() -> None:
    leaks: list[tuple[Path, int, str]] = []
    for path in sorted(_COMMANDS_DIR.glob("*.md")):
        context_mode = _command_context_mode(path)
        if context_mode not in {"projectless", "global"}:
            continue
        rel_path = path.relative_to(REPO_ROOT)
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if _RAW_PROJECT_INCLUDE_PATTERN.search(line):
                leaks.append((rel_path, line_no, line))

    assert leaks == [], (
        "Projectless/global command prompts should let workflows or CLI inspect GPD files conditionally:\n"
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
        for line_no, literal in _standalone_runtime_name_or_display_literal_findings(content):
            leaks.append(
                (
                    path,
                    line_no,
                    f"hard-coded standalone runtime name/display literal: {literal!r}",
                )
            )

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


def test_autonomous_success_criteria_do_not_hardcode_provider_literals() -> None:
    workflow = (REPO_ROOT / "src/gpd/specs/workflows/autonomous.md").read_text(encoding="utf-8")
    success_criteria = workflow.split("<success_criteria>", 1)[1].split("</success_criteria>", 1)[0]

    provider_literals = ("Anthropic", "OpenAI", "Google", "Claude", "Gemini")
    leaks = [literal for literal in provider_literals if literal in success_criteria]

    assert "runtime/provider-neutral" in success_criteria
    assert leaks == []


def test_readme_optional_terminal_reference_uses_runtime_placeholders() -> None:
    block = _readme_optional_terminal_reference()

    for descriptor in _RUNTIME_DESCRIPTORS:
        assert descriptor.install_flag not in block
        assert f"--runtime {descriptor.runtime_name}" not in block
        assert f"relaunch {descriptor.display_name}" not in block
    assert "--<runtime-flag>" in block
    assert "--runtime <runtime>" in block


def test_base_uninstall_removes_shared_surfaces_from_catalog_globs(tmp_path: Path, monkeypatch) -> None:
    adapter = get_adapter(_RUNTIME_DESCRIPTORS[0].runtime_name)
    target = tmp_path / "runtime-config"
    nested_command = target / "slash-commands" / "gpd" / "help.md"
    flat_command = target / "shortcut" / "gpd-help.md"
    managed_agent = target / "roles" / "gpd-worker.txt"
    user_agent = target / "roles" / "custom.txt"
    for path in (nested_command, flat_command, managed_agent, user_agent):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("content\n", encoding="utf-8")
    (target / _SHARED_INSTALL.manifest_name).write_text(
        json.dumps({"runtime": adapter.runtime_name, "install_scope": "local", "explicit_target": False}),
        encoding="utf-8",
    )
    policy = ManagedInstallSurfacePolicy(
        nested_command_globs=("slash-commands/gpd/**/*",),
        flat_command_globs=("shortcut/gpd-*.md",),
        managed_agent_globs=("roles/gpd-*.txt",),
    )
    monkeypatch.setattr("gpd.adapters.base.get_managed_install_surface_policy", lambda runtime=None: policy)

    result = RuntimeAdapter.uninstall(adapter, target)

    assert "slash-commands/gpd/" in result["removed"]
    assert "1 flat GPD commands" in result["removed"]
    assert "1 GPD agents" in result["removed"]
    assert not nested_command.exists()
    assert not flat_command.exists()
    assert not managed_agent.exists()
    assert user_agent.exists()


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
