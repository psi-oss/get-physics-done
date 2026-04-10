"""OpenCode runtime adapter.

Handles:
- XDG Base Directory config path resolution (5-level precedence)
- Flat command structure: commands/gpd/help.md → command/gpd-help.md
- Frontmatter conversion: allowed-tools → tools map, color name→hex, strip name field
- Tool name mapping: AskUserQuestion→question, /gpd:→/gpd-
- opencode.json permission configuration (read + external_directory)
- Agent file conversion with OpenCode frontmatter
- Full install/uninstall support with file manifest
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
from collections.abc import Mapping
from pathlib import Path

from gpd.adapters.base import RuntimeAdapter
from gpd.adapters.install_utils import (
    CACHE_DIR_NAME,
    MANIFEST_NAME,
    PATCHES_DIR_NAME,
    UPDATE_CACHE_FILENAME,
    _default_install_target,
    _normalize_install_scope_flag,
    _paths_equal,
    compile_markdown_for_runtime,
    compute_path_prefix,
    convert_tool_references_in_body,
    file_hash,
    generate_manifest,
    get_global_dir,
    hook_python_interpreter,
    install_gpd_content,
    managed_hook_paths,
    parse_jsonc,
    prune_empty_ancestors,
    remove_empty_json_object_file,
    remove_stale_agents,
    render_markdown_frontmatter,
    replace_placeholders,
    should_preserve_public_local_cli_command,
    split_markdown_frontmatter,
    strip_sub_tags,
)
from gpd.adapters.tool_names import build_runtime_alias_map, reference_translation_map, translate_for_runtime
from gpd.mcp import managed_integrations as _managed_integrations

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_TOOL_NAME_MAP: dict[str, str] = {
    "file_read": "read_file",
    "file_write": "write_file",
    "file_edit": "edit_file",
    "shell": "shell",
    "search_files": "grep",
    "find_files": "glob",
    "web_search": "websearch",
    "web_fetch": "webfetch",
    "notebook_edit": "notebookedit",
    "agent": "agent",
    "ask_user": "question",
    "todo_write": "todowrite",
    "task": "task",
    "slash_command": "skill",
    "tool_search": "toolsearch",
}
_TOOL_ALIAS_MAP = build_runtime_alias_map(_TOOL_NAME_MAP)
_TOOL_REFERENCE_MAP = reference_translation_map(_TOOL_NAME_MAP, alias_map=_TOOL_ALIAS_MAP)

# Color name → hex for OpenCode compatibility
_COLOR_NAME_TO_HEX: dict[str, str] = {
    "cyan": "#00FFFF",
    "red": "#FF0000",
    "green": "#00FF00",
    "blue": "#0000FF",
    "yellow": "#FFFF00",
    "magenta": "#FF00FF",
    "orange": "#FFA500",
    "purple": "#800080",
    "pink": "#FFC0CB",
    "white": "#FFFFFF",
    "black": "#000000",
    "gray": "#808080",
    "grey": "#808080",
}

_HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{3}$|^#[0-9a-fA-F]{6}$")
_SHELL_FENCE_LANGUAGES = frozenset({"bash", "sh", "shell", "zsh"})
_GPD_SLASH_COMMAND_RE = re.compile(r"(?<![A-Za-z0-9/_.-])/gpd:(?P<command>[A-Za-z][A-Za-z0-9-]*)\b")
_OPENCODE_PERMISSION_DECISIONS = frozenset({"allow", "ask", "deny"})
_OPENCODE_YOLO_PERMISSION = "allow"
_MANIFEST_OPENCODE_GENERATED_COMMAND_FILES_KEY = "opencode_generated_command_files"

# ---------------------------------------------------------------------------
# XDG config directory resolution
# ---------------------------------------------------------------------------


def get_opencode_global_dir(explicit_dir: str | None = None) -> Path:
    """Resolve the global config directory for OpenCode.

    Delegates to ``install_utils.get_global_dir`` which implements the full
    XDG Base Directory spec with 5-level precedence:
    1. explicit_dir (from --config-dir flag)
    2. OPENCODE_CONFIG_DIR env var
    3. dirname(OPENCODE_CONFIG) env var
    4. XDG_CONFIG_HOME/opencode when XDG_CONFIG_HOME is set
    5. ~/.config/opencode when XDG_CONFIG_HOME is unset
    """
    return Path(get_global_dir("opencode", explicit_dir))


# ---------------------------------------------------------------------------
# Tool name conversion
# ---------------------------------------------------------------------------


def convert_tool_name(tool_name: str) -> str:
    """Convert a canonical GPD tool name or runtime alias to OpenCode format.

    OpenCode keeps MCP tools as-is, so this never returns ``None``.
    """
    mapped = translate_for_runtime(tool_name, _TOOL_NAME_MAP)
    return mapped if mapped is not None else tool_name


def _project_managed_mcp_servers(
    env: Mapping[str, str] | None = None,
    *,
    cwd: Path | None = None,
) -> dict[str, dict[str, object]]:
    """Project shared optional integrations into OpenCode's neutral MCP shape."""
    return _managed_integrations.projected_managed_optional_mcp_servers(env, cwd=cwd)


def _managed_mcp_server_keys() -> frozenset[str]:
    """Return GPD-managed OpenCode MCP server keys, including optional integrations."""
    from gpd.mcp.builtin_servers import GPD_MCP_SERVER_KEYS

    return frozenset(set(GPD_MCP_SERVER_KEYS) | set(_managed_integrations.managed_optional_mcp_server_keys()))


# ---------------------------------------------------------------------------
# Frontmatter conversion
# ---------------------------------------------------------------------------


def convert_claude_to_opencode_frontmatter(content: str, path_prefix: str | None = None) -> str:
    """Convert canonical GPD frontmatter to OpenCode format.

    Transformations:
    - Replace tool name references in content
    - Replace /gpd: with /gpd- (flat command structure)
    - Replace bare ~/.claude references with the resolved OpenCode config dir
    - Parse YAML frontmatter:
      - Strip name: field (OpenCode uses filename for command name)
      - Convert color names to hex
      - Convert allowed-tools: YAML array to tools: object with {tool: true}
    """
    resolved_config_dir = path_prefix[:-1] if path_prefix and path_prefix.endswith("/") else path_prefix
    if not resolved_config_dir:
        resolved_config_dir = "~/.config/opencode"

    converted = content
    converted = convert_tool_references_in_body(converted, _TOOL_REFERENCE_MAP)
    converted = _GPD_SLASH_COMMAND_RE.sub(r"/gpd-\g<command>", converted)
    converted = re.sub(r"~/\.claude\b", lambda m: resolved_config_dir, converted)

    preamble, frontmatter, separator, body = split_markdown_frontmatter(converted)
    if not frontmatter:
        return converted

    lines = frontmatter.split("\n")
    new_lines: list[str] = []
    in_allowed_tools = False
    allowed_tools: list[str] = []

    for line in lines:
        trimmed = line.strip()

        # Detect start of allowed-tools array
        if trimmed.startswith("allowed-tools:"):
            in_allowed_tools = True
            continue

        # Detect inline tools: field (comma-separated string)
        if trimmed.startswith("tools:"):
            tools_value = trimmed[6:].strip()
            if tools_value:
                tools = [t.strip() for t in tools_value.split(",") if t.strip()]
                allowed_tools.extend(tools)
            else:
                in_allowed_tools = True
            continue

        # Remove name: field — OpenCode uses filename for command name
        if trimmed.startswith("name:"):
            continue

        # Convert color names to hex for OpenCode
        if trimmed.startswith("color:"):
            color_raw = trimmed[6:].strip()
            color_value = color_raw.lower()
            hex_color = _COLOR_NAME_TO_HEX.get(color_value)
            if hex_color:
                new_lines.append(f'color: "{hex_color}"')
            elif color_value.startswith("#"):
                if _HEX_COLOR_RE.match(color_value):
                    new_lines.append(f'color: "{color_raw}"')
                # Skip invalid hex colors
            # Skip unknown color names
            continue

        # Collect allowed-tools items
        if in_allowed_tools:
            if trimmed.startswith("- "):
                allowed_tools.append(trimmed[2:].strip())
                continue
            elif trimmed and not trimmed.startswith("-"):
                in_allowed_tools = False

        if not in_allowed_tools:
            new_lines.append(line)

    # Add tools object if we had allowed-tools or tools
    if allowed_tools:
        new_lines.append("tools:")
        for tool in allowed_tools:
            new_lines.append(f"  {convert_tool_name(tool)}: true")

    new_frontmatter = "\n".join(new_lines).strip()
    return render_markdown_frontmatter(preamble, new_frontmatter, separator, body)


def _rewrite_gpd_cli_invocations(content: str, bridge_command: str) -> str:
    """Rewrite fenced-shell command-position ``gpd`` calls to the runtime bridge."""
    rewritten: list[str] = []
    in_shell_fence = False

    for line in content.splitlines(keepends=True):
        stripped = line.lstrip()
        if stripped.startswith("```"):
            if in_shell_fence:
                in_shell_fence = False
            else:
                fence_language = stripped[3:].strip().lower()
                in_shell_fence = fence_language in _SHELL_FENCE_LANGUAGES
            rewritten.append(line)
            continue

        if in_shell_fence:
            rewritten.append(_rewrite_gpd_shell_line(line, bridge_command))
            continue

        rewritten.append(line)

    return "".join(rewritten)


def _rewrite_gpd_shell_line(line: str, bridge_command: str) -> str:
    """Rewrite only command-position ``gpd`` tokens on a shell line."""
    pieces: list[str] = []
    index = 0
    in_single = False
    in_double = False

    while index < len(line):
        char = line[index]
        previous = line[index - 1] if index > 0 else ""

        if char == "'" and not in_double:
            in_single = not in_single
            pieces.append(char)
            index += 1
            continue

        if char == '"' and not in_single and previous != "\\":
            in_double = not in_double
            pieces.append(char)
            index += 1
            continue

        if (
            not in_single
            and not in_double
            and line.startswith("gpd", index)
            and _is_gpd_command_start(line, index)
            and _is_gpd_token_end(line, index + 3)
        ):
            if should_preserve_public_local_cli_command(line[index:]):
                pieces.append("gpd")
                index += 3
                continue
            pieces.append(bridge_command)
            index += 3
            continue

        pieces.append(char)
        index += 1

    return "".join(pieces)


def _is_gpd_command_start(line: str, index: int) -> bool:
    """Return whether ``gpd`` starts a shell command token at *index*."""
    probe = index - 1
    while probe >= 0 and line[probe] in " \t":
        probe -= 1

    if probe < 0:
        return True

    if line[probe] in "|;(!":
        return True

    if probe >= 1 and line[probe - 1 : probe + 1] in {"&&", "||", "$("}:
        return True

    return False


def _is_gpd_token_end(line: str, end_index: int) -> bool:
    """Return whether the token ending at *end_index* is a standalone ``gpd``."""
    if end_index >= len(line):
        return True
    return line[end_index].isspace() or line[end_index] in {'"', "'", "`", ";", "|", "&", ")", "<", ">"}


# ---------------------------------------------------------------------------
# Command copying (flattened structure)
# ---------------------------------------------------------------------------


def copy_flattened_commands(
    src_dir: Path,
    dest_dir: Path,
    prefix: str,
    path_prefix: str,
    workflow_target_dir: Path | None = None,
    gpd_src_root: Path | None = None,
    install_scope: str | None = None,
    bridge_command: str | None = None,
    *,
    explicit_target: bool = False,
    managed_command_files: set[str] | None = None,
) -> int:
    """Copy commands to a flat structure for OpenCode.

    OpenCode expects: command/gpd-help.md (invoked as /gpd-help)
    Source structure: commands/gpd/help.md

    Returns the count of files written.
    """
    if not src_dir.exists():
        return 0

    dest_dir.mkdir(parents=True, exist_ok=True)
    manifest_root = workflow_target_dir or dest_dir.parent
    tracked_command_files = set(_load_manifest_opencode_generated_command_files(manifest_root))
    # Remove only previously generated command files before copying new ones.
    if tracked_command_files:
        for name in tracked_command_files:
            command_path = dest_dir / name
            if command_path.is_file():
                command_path.unlink()

    count = 0
    for entry in sorted(src_dir.iterdir()):
        if entry.is_dir():
            count += copy_flattened_commands(
                entry,
                dest_dir,
                f"{prefix}-{entry.name}",
                path_prefix,
                workflow_target_dir,
                gpd_src_root,
                install_scope,
                bridge_command,
                explicit_target=explicit_target,
                managed_command_files=managed_command_files,
            )
        elif entry.name.endswith(".md"):
            base_name = entry.stem
            dest_name = f"{prefix}-{base_name}.md"
            dest_path = dest_dir / dest_name

            content = compile_markdown_for_runtime(
                entry.read_text(encoding="utf-8"),
                runtime="opencode",
                path_prefix=path_prefix,
                install_scope=install_scope,
                src_root=gpd_src_root,
                workflow_target_dir=workflow_target_dir,
                explicit_target=explicit_target,
            )
            if bridge_command:
                content = _rewrite_gpd_cli_invocations(content, bridge_command)
            content = convert_claude_to_opencode_frontmatter(content, path_prefix)

            dest_path.write_text(content, encoding="utf-8")
            if managed_command_files is not None and dest_name.startswith("gpd-"):
                managed_command_files.add(dest_name)
            count += 1

    return count


# ---------------------------------------------------------------------------
# Agent copying
# ---------------------------------------------------------------------------


def copy_agents_as_agent_files(
    agents_src: Path,
    agents_dest: Path,
    path_prefix: str,
    gpd_src_root: Path | None = None,
    install_scope: str | None = None,
    bridge_command: str | None = None,
) -> int:
    """Copy agent .md files with OpenCode frontmatter conversion.

    Writes new agents first, then removes stale ones (safe order prevents data loss).
    Returns the count of agents written.
    """
    if not agents_src.exists():
        return 0

    agents_dest.mkdir(parents=True, exist_ok=True)
    source_root = gpd_src_root or agents_src.parent / "specs"

    new_agent_names: set[str] = set()
    count = 0

    for entry in sorted(agents_src.iterdir()):
        if not entry.is_file() or not entry.name.endswith(".md"):
            continue

        content = compile_markdown_for_runtime(
            entry.read_text(encoding="utf-8"),
            runtime="opencode",
            path_prefix=path_prefix,
            install_scope=install_scope,
            src_root=source_root,
            protect_agent_prompt_body=True,
        )
        if bridge_command:
            content = _rewrite_gpd_cli_invocations(content, bridge_command)
        content = convert_claude_to_opencode_frontmatter(content, path_prefix)

        (agents_dest / entry.name).write_text(content, encoding="utf-8")
        new_agent_names.add(entry.name)
        count += 1

    remove_stale_agents(agents_dest, new_agent_names)

    return count


# ---------------------------------------------------------------------------
# Permission configuration
# ---------------------------------------------------------------------------


def _opencode_managed_permission_keys(config_dir: Path) -> tuple[str, ...]:
    """Return the managed permission key for *config_dir*."""
    actual_config_dir = config_dir.expanduser()
    return (f"{actual_config_dir.as_posix()}/get-physics-done/*",)


def _write_opencode_config(config_dir: Path, config: dict[str, object]) -> None:
    """Persist OpenCode config as normalized JSON."""
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "opencode.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")


def _read_opencode_config_state(config_dir: Path) -> tuple[dict[str, object] | None, str | None]:
    """Return parsed OpenCode config and a malformed marker when parsing fails."""
    config_path = config_dir / "opencode.json"
    if not config_path.exists():
        return None, None
    try:
        parsed = parse_jsonc(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, ValueError):
        return None, "malformed"
    if not isinstance(parsed, dict):
        return None, "malformed"
    if not _opencode_permission_shape_is_valid(parsed.get("permission")):
        return None, "malformed"
    if not _opencode_mcp_shape_is_valid(parsed.get("mcp")):
        return None, "malformed"
    return parsed, None


def _load_manifest_opencode_generated_command_files(target_dir: Path) -> tuple[str, ...]:
    """Return tracked OpenCode command filenames from the local manifest metadata."""
    manifest_path = target_dir / MANIFEST_NAME
    if not manifest_path.exists():
        return ()

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return ()

    if not isinstance(manifest, dict):
        return ()

    command_files = manifest.get(_MANIFEST_OPENCODE_GENERATED_COMMAND_FILES_KEY)
    if not isinstance(command_files, list):
        return ()

    tracked: list[str] = []
    for entry in command_files:
        if isinstance(entry, str) and entry.startswith("gpd-") and entry.endswith(".md"):
            tracked.append(entry)
    return tuple(dict.fromkeys(tracked))


def _load_manifest_opencode_command_files(target_dir: Path) -> tuple[str, ...]:
    """Return tracked OpenCode command filenames, falling back to manifest files entries."""
    generated_command_files = _load_manifest_opencode_generated_command_files(target_dir)
    if generated_command_files:
        return generated_command_files

    manifest_path = target_dir / MANIFEST_NAME
    if not manifest_path.exists():
        return ()

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return ()

    if not isinstance(manifest, dict):
        return ()

    manifest_files = manifest.get("files")
    if not isinstance(manifest_files, dict):
        return ()

    tracked: list[str] = []
    for rel_path in manifest_files:
        if not isinstance(rel_path, str) or not rel_path.startswith("command/"):
            continue
        name = rel_path.removeprefix("command/")
        if name.startswith("gpd-") and name.endswith(".md"):
            tracked.append(name)
    return tuple(dict.fromkeys(tracked))


def _clone_json_value(value: object) -> object:
    """Deep-copy JSON-compatible values."""
    return json.loads(json.dumps(value))


def _opencode_permission_shape_is_valid(permission_value: object) -> bool:
    if permission_value is None:
        return True
    if isinstance(permission_value, dict):
        return True
    return isinstance(permission_value, str) and permission_value in _OPENCODE_PERMISSION_DECISIONS


def _opencode_mcp_shape_is_valid(mcp_value: object) -> bool:
    if mcp_value is None:
        return True
    if not isinstance(mcp_value, dict):
        return False
    return all(isinstance(entry, dict) for entry in mcp_value.values())


def _normalize_opencode_permission_value(permission_value: object) -> tuple[dict[str, object], bool]:
    """Return permission config as an object plus whether coercion occurred."""
    if isinstance(permission_value, dict):
        return dict(permission_value), False
    if isinstance(permission_value, str) and permission_value in _OPENCODE_PERMISSION_DECISIONS:
        return {"*": permission_value}, True
    return {}, permission_value is not None


def _opencode_permission_rule_is_allow(rule: object) -> bool:
    """Return whether a permission rule resolves entirely to allow."""
    if isinstance(rule, str):
        return rule == "allow"
    if isinstance(rule, dict):
        return all(_opencode_permission_rule_is_allow(value) for value in rule.values())
    return False


def _opencode_permission_is_yolo(permission_value: object) -> bool:
    """Return whether the permission config represents prompt-free allow-all."""
    if permission_value == _OPENCODE_YOLO_PERMISSION:
        return True
    if isinstance(permission_value, dict) and permission_value.get("*") == "allow":
        return all(_opencode_permission_rule_is_allow(value) for value in permission_value.values())
    return False


def configure_opencode_permissions(config_dir: Path) -> bool:
    """Configure OpenCode permissions to allow reading GPD reference docs.

    Modifies opencode.json to add permission.read and permission.external_directory
    grants for the GPD path. Returns True if config was modified.
    """
    config_state, config_parse_error = _read_opencode_config_state(config_dir)
    if config_parse_error is not None:
        raise RuntimeError("OpenCode opencode.json is malformed; refusing to overwrite it during install.")
    config = config_state or {}
    permission_value = config.get("permission")
    if _opencode_permission_is_yolo(permission_value):
        return False

    permission_config, coerced = _normalize_opencode_permission_value(permission_value)
    if permission_value is None:
        coerced = False
    if permission_value is None or coerced:
        config["permission"] = permission_config

    managed_keys = _opencode_managed_permission_keys(config_dir)
    gpd_path = managed_keys[0]

    modified = permission_value is None or coerced

    # Configure read permission
    read_permissions = permission_config.get("read")
    if not isinstance(read_permissions, dict):
        read_permissions = {}
        permission_config["read"] = read_permissions
        modified = True
    if read_permissions.get(gpd_path) != "allow":
        read_permissions[gpd_path] = "allow"
        modified = True

    # Configure external_directory permission
    external_permissions = permission_config.get("external_directory")
    if not isinstance(external_permissions, dict):
        external_permissions = {}
        permission_config["external_directory"] = external_permissions
        modified = True
    if external_permissions.get(gpd_path) != "allow":
        external_permissions[gpd_path] = "allow"
        modified = True

    if modified:
        config["permission"] = permission_config
        _write_opencode_config(config_dir, config)

    return modified


# ---------------------------------------------------------------------------
# Manifest (OpenCode-specific: uses command/ not commands/gpd/)
# ---------------------------------------------------------------------------


def write_manifest(
    config_dir: Path,
    version: str,
    *,
    runtime: str | None = None,
    install_scope: str | None = None,
    explicit_target: bool | None = None,
    managed_command_file_names: tuple[str, ...] | None = None,
) -> dict:
    """Write file manifest after installation for future modification detection.

    OpenCode-specific: scans ``command/gpd-*.md`` (flat) instead of
    ``commands/gpd/`` (nested).
    """
    from datetime import UTC, datetime

    gpd_dir = config_dir / "get-physics-done"
    command_dir = config_dir / "command"
    agents_dir = config_dir / "agents"
    hooks_dir = config_dir / "hooks"

    manifest: dict = {
        "version": version,
        "timestamp": datetime.now(UTC).isoformat(),
        "files": {},
    }
    if isinstance(runtime, str) and runtime.strip():
        manifest["runtime"] = runtime.strip()
    normalized_scope = _normalize_install_scope_flag(install_scope)
    if normalized_scope == "--local":
        manifest["install_scope"] = "local"
    elif normalized_scope == "--global":
        manifest["install_scope"] = "global"
    manifest["install_target_dir"] = str(config_dir)
    if explicit_target is not None:
        manifest["explicit_target"] = bool(explicit_target)
    elif isinstance(runtime, str) and runtime.strip() and normalized_scope in {"--local", "--global"}:
        default_target = _default_install_target(runtime.strip(), normalized_scope)
        if default_target is not None:
            manifest["explicit_target"] = not _paths_equal(config_dir, default_target)
    if managed_command_file_names:
        manifest[_MANIFEST_OPENCODE_GENERATED_COMMAND_FILES_KEY] = sorted(
            {
                name
                for name in managed_command_file_names
                if isinstance(name, str) and name.startswith("gpd-") and name.endswith(".md")
            }
        )

    # get-physics-done/ files
    gpd_hashes = generate_manifest(gpd_dir)
    for rel, h in gpd_hashes.items():
        manifest["files"]["get-physics-done/" + rel] = h

    # command/gpd-*.md files (OpenCode flat structure)
    command_names = managed_command_file_names
    if command_names is None:
        command_names = tuple(
            sorted(
                f.name
                for f in command_dir.iterdir()
                if f.name.startswith("gpd-") and f.name.endswith(".md")
            )
        ) if command_dir.exists() else ()
    for name in command_names:
        command_path = command_dir / name
        if command_path.is_file():
            manifest["files"]["command/" + name] = file_hash(command_path)

    # agents/gpd-*.md files
    if agents_dir.exists():
        for f in sorted(agents_dir.iterdir()):
            if f.name.startswith("gpd-") and f.name.endswith(".md"):
                manifest["files"]["agents/" + f.name] = file_hash(f)

    # hooks/ files
    if hooks_dir.exists():
        for rel, h in generate_manifest(hooks_dir).items():
            manifest["files"]["hooks/" + rel] = h

    manifest_path = config_dir / MANIFEST_NAME
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


# ---------------------------------------------------------------------------
# Copy directory with path replacement (OpenCode-specific)
# ---------------------------------------------------------------------------


def _copy_dir_contents(
    src_dir: Path,
    target_dir: Path,
    path_prefix: str,
    install_scope: str | None = None,
) -> None:
    """Recursively copy directory contents with path replacement in .md files.

    OpenCode-specific: applies frontmatter conversion to all .md files.
    """
    for entry in sorted(src_dir.iterdir()):
        dest_path = target_dir / entry.name
        if entry.is_dir():
            dest_path.mkdir(parents=True, exist_ok=True)
            _copy_dir_contents(entry, dest_path, path_prefix, install_scope)
        elif entry.name.endswith(".md"):
            content = entry.read_text(encoding="utf-8")
            content = replace_placeholders(content, path_prefix, "opencode", install_scope)
            content = convert_claude_to_opencode_frontmatter(content, path_prefix)
            content = strip_sub_tags(content)
            dest_path.write_text(content, encoding="utf-8")
        else:
            shutil.copy2(entry, dest_path)


def copy_with_path_replacement(
    src_dir: Path,
    dest_dir: Path,
    path_prefix: str,
    install_scope: str | None = None,
) -> None:
    """Safely copy directory with path replacement, using copy-to-temp-then-swap.

    Prevents data loss if the copy fails partway through.
    OpenCode-specific: uses ``_copy_dir_contents`` which applies frontmatter conversion.
    """
    tmp_dir = dest_dir.parent / f"{dest_dir.name}.tmp.{os.getpid()}"
    old_dir = dest_dir.parent / f"{dest_dir.name}.old.{os.getpid()}"

    # Clean up any leftover dirs from a previous interrupted install
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    if old_dir.exists():
        shutil.rmtree(old_dir)

    tmp_dir.mkdir(parents=True, exist_ok=True)

    try:
        _copy_dir_contents(src_dir, tmp_dir, path_prefix, install_scope)

        # Swap into place: rename-old-then-rename-new
        if dest_dir.exists():
            dest_dir.rename(old_dir)
        try:
            tmp_dir.rename(dest_dir)
        except OSError:
            # Rename failed — restore old directory
            if old_dir.exists():
                old_dir.rename(dest_dir)
            raise

        # Swap succeeded — clean up old
        if old_dir.exists():
            shutil.rmtree(old_dir)
    except Exception:
        # Copy or swap failed — clean up temp, leave existing install intact
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir)
        if dest_dir.exists() and old_dir.exists():
            shutil.rmtree(old_dir)
        raise


# ---------------------------------------------------------------------------
# Uninstall
# ---------------------------------------------------------------------------


def uninstall_opencode(target_dir: Path, *, config_dir: Path, allow_empty_config_removal: bool) -> dict[str, int]:
    """Uninstall GPD from an OpenCode config directory.

    Removes GPD-specific files/directories, preserves user content.
    Returns a dict with counts of removed items.
    """
    counts: dict[str, int] = {"commands": 0, "agents": 0, "hooks": 0, "dirs": 0, "permissions": 0}
    managed_hooks = managed_hook_paths(target_dir)
    runtime_permission_state: dict[str, object] | None = None
    tracked_command_files = _load_manifest_opencode_command_files(target_dir)

    # 1. Remove command/gpd-*.md files
    command_dir = target_dir / "command"
    if command_dir.exists() and tracked_command_files:
        for name in tracked_command_files:
            command_path = command_dir / name
            if command_path.is_file():
                command_path.unlink()
                counts["commands"] += 1

    # 2. Remove get-physics-done directory
    gpd_dir = target_dir / "get-physics-done"
    if gpd_dir.exists():
        shutil.rmtree(gpd_dir)
        counts["dirs"] += 1

    # 2b. Remove file manifest and local patches
    manifest_file = target_dir / MANIFEST_NAME
    if manifest_file.exists():
        try:
            manifest_payload = json.loads(manifest_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            manifest_payload = {}
        if isinstance(manifest_payload, dict):
            state = manifest_payload.get("gpd_runtime_permissions")
            if isinstance(state, dict):
                runtime_permission_state = state
        manifest_file.unlink()
    patches_path = target_dir / PATCHES_DIR_NAME
    if patches_path.exists():
        shutil.rmtree(patches_path)

    # 3. Remove GPD agent files (gpd-*.md only)
    agents_dir = target_dir / "agents"
    if agents_dir.exists():
        for f in agents_dir.iterdir():
            if f.name.startswith("gpd-") and f.name.endswith(".md"):
                f.unlink()
                counts["agents"] += 1

    # 4. Remove GPD hooks
    hooks_dir = target_dir / "hooks"
    if hooks_dir.exists():
        for rel_path in sorted(managed_hooks):
            hook_path = target_dir / rel_path
            if hook_path.is_file():
                hook_path.unlink()
                counts["hooks"] += 1

    # 4b. Remove GPD update cache files.
    cache_dir = target_dir / CACHE_DIR_NAME
    for cache_path in (
        cache_dir / UPDATE_CACHE_FILENAME,
        cache_dir / f"{UPDATE_CACHE_FILENAME}.inflight",
    ):
        if cache_path.is_file():
            cache_path.unlink()

    # 5. Remove GPD MCP servers from opencode.json (uses "mcp" key, not "mcpServers")
    oc_config_dir_mcp = config_dir
    oc_config_path_mcp = oc_config_dir_mcp / "opencode.json"
    if oc_config_path_mcp.exists():
        try:
            oc_mcp = parse_jsonc(oc_config_path_mcp.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            oc_mcp = None
        if isinstance(oc_mcp, dict) and isinstance(oc_mcp.get("mcp"), dict):
            gpd_keys = [k for k in oc_mcp["mcp"] if k in _managed_mcp_server_keys()]
            for k in gpd_keys:
                del oc_mcp["mcp"][k]
            if gpd_keys:
                if not oc_mcp["mcp"]:
                    del oc_mcp["mcp"]
                oc_config_path_mcp.write_text(json.dumps(oc_mcp, indent=2) + "\n", encoding="utf-8")

    # 6. Clean up permissions from opencode.json
    oc_config_dir = config_dir
    oc_config_path = oc_config_dir / "opencode.json"
    if oc_config_path.exists():
        try:
            oc_config = parse_jsonc(oc_config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            oc_config = None
        if not isinstance(oc_config, dict):
            oc_config = None
        modified = False

        restore_state = (
            runtime_permission_state.get("restore")
            if isinstance(runtime_permission_state, dict) and runtime_permission_state.get("mode") == "yolo"
            else None
        )
        if isinstance(restore_state, dict):
            if oc_config is None:
                oc_config = {}
            if restore_state.get("had_permission"):
                oc_config["permission"] = _clone_json_value(restore_state.get("permission"))
            else:
                oc_config.pop("permission", None)
            modified = True

        if oc_config is not None and isinstance(oc_config.get("permission"), dict):
            managed_keys = _opencode_managed_permission_keys(oc_config_dir)
            for perm_type in ("read", "external_directory"):
                perm_dict = oc_config["permission"].get(perm_type)
                if isinstance(perm_dict, dict):
                    for managed_key in managed_keys:
                        if managed_key in perm_dict:
                            del perm_dict[managed_key]
                            modified = True
                    if not perm_dict:
                        del oc_config["permission"][perm_type]
            if not oc_config["permission"]:
                del oc_config["permission"]

        if modified:
            oc_config_path.write_text(json.dumps(oc_config, indent=2) + "\n", encoding="utf-8")
            counts["permissions"] += 1
        if allow_empty_config_removal:
            remove_empty_json_object_file(oc_config_path)

    for path in (
        target_dir / "command",
        target_dir / "agents",
        target_dir / "hooks",
        target_dir / "cache",
        target_dir,
    ):
        prune_empty_ancestors(path, stop_at=target_dir.parent)

    return counts


# ---------------------------------------------------------------------------
# Adapter class
# ---------------------------------------------------------------------------


def _write_mcp_servers_opencode(config_dir: Path, servers: dict[str, dict[str, object]]) -> int:
    """Write MCP server entries into opencode.json.

    OpenCode uses a different format from Claude Code / Gemini:
    - Key is ``mcp`` (not ``mcpServers``)
    - Each server has ``type: "local"``, ``command`` as an array, ``environment`` (not ``env``)
    """
    config_path = config_dir / "opencode.json"
    config_dir.mkdir(parents=True, exist_ok=True)

    config_state, config_parse_error = _read_opencode_config_state(config_dir)
    if config_parse_error is not None:
        raise RuntimeError("OpenCode opencode.json is malformed; refusing to overwrite it during install.")
    config = config_state or {}

    existing_mcp = config.get("mcp", {})
    if not isinstance(existing_mcp, dict):
        existing_mcp = {}

    from gpd.mcp.builtin_servers import merge_managed_mcp_entry

    for name, entry in servers.items():
        cmd = str(entry.get("command", ""))
        raw_args = entry.get("args", [])
        args_list = list(raw_args) if isinstance(raw_args, list) else []
        # OpenCode wants command as a single array: ["executable", "arg1", "arg2"]
        command_array = [cmd] + [str(a) for a in args_list]

        managed_entry: dict[str, object] = {
            "type": "local",
            "command": command_array,
        }
        raw_env = entry.get("env", {})
        if isinstance(raw_env, dict) and raw_env:
            managed_entry["environment"] = dict(raw_env)

        oc_entry = merge_managed_mcp_entry(
            existing_mcp.get(name),
            managed_entry,
            merge_mapping_keys=frozenset({"environment"}),
        )
        if not isinstance(oc_entry.get("enabled"), bool):
            oc_entry["enabled"] = True

        existing_mcp[name] = oc_entry

    config["mcp"] = existing_mcp
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    return len(servers)


class OpenCodeAdapter(RuntimeAdapter):
    """Adapter for OpenCode."""

    tool_name_map = _TOOL_NAME_MAP
    strip_sub_tags_in_shared_markdown = True

    @property
    def runtime_name(self) -> str:
        return "opencode"

    def project_markdown_surface(
        self,
        content: str,
        *,
        surface_kind: str,
        path_prefix: str,
        command_name: str | None = None,
    ) -> str:
        del command_name
        if surface_kind != "command":
            return super().project_markdown_surface(
                content,
                surface_kind=surface_kind,
                path_prefix=path_prefix,
            )
        return convert_claude_to_opencode_frontmatter(content, path_prefix)

    def translate_shared_command_references(self, content: str) -> str:
        return content.replace("/gpd:", self.public_command_surface_prefix)

    def get_commit_attribution(self, *, explicit_config_dir: str | None = None) -> str | None:
        """OpenCode opts out when `disable_ai_attribution` is enabled."""
        config_dir = Path(explicit_config_dir).expanduser() if explicit_config_dir else self.resolve_global_config_dir()
        config_path = config_dir / "opencode.json"
        if not config_path.exists():
            return ""
        try:
            parsed = parse_jsonc(config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return ""
        if isinstance(parsed, dict) and parsed.get("disable_ai_attribution") is True:
            return None
        return ""

    # --- Template method hooks ---

    def _compute_path_prefix(self, target_dir: Path, is_global: bool) -> str:
        return compute_path_prefix(
            target_dir,
            self.config_dir_name,
            is_global=is_global,
            explicit_target=getattr(self, "_install_explicit_target", False),
        )

    def runtime_install_required_relpaths(self) -> tuple[str, ...]:
        """Return OpenCode-owned files required for a complete install."""
        return ("opencode.json",)

    def missing_install_artifacts(self, target_dir: Path) -> tuple[str, ...]:
        """Return missing OpenCode install artifacts, including the command surface."""
        missing = list(super().missing_install_artifacts(target_dir))
        command_dir = target_dir / "command"
        tracked_command_files = _load_manifest_opencode_generated_command_files(target_dir)

        if not tracked_command_files:
            missing.append("command/gpd-*.md")
            return tuple(dict.fromkeys(missing))

        missing_command_files: list[str] = []
        for name in tracked_command_files:
            command_path = command_dir / name
            try:
                if not command_path.is_file():
                    missing_command_files.append(f"command/{name}")
            except OSError:
                missing_command_files.append(f"command/{name}")

        if not command_dir.is_dir():
            missing_command_files.append("command/gpd-*.md")

        if missing_command_files and "command/gpd-*.md" not in missing_command_files:
            missing_command_files.append("command/gpd-*.md")

        missing.extend(missing_command_files)
        return tuple(dict.fromkeys(missing))

    def _install_commands(self, gpd_root: Path, target_dir: Path, path_prefix: str, failures: list[str]) -> int:
        commands_src = gpd_root / "commands"
        command_dir = target_dir / "command"
        command_dir.mkdir(parents=True, exist_ok=True)
        bridge_command = self.runtime_cli_bridge_command(target_dir)
        generated_command_files: set[str] = set()
        count = copy_flattened_commands(
            commands_src,
            command_dir,
            "gpd",
            path_prefix,
            target_dir,
            gpd_root / "specs",
            self._current_install_scope_flag(),
            bridge_command,
            explicit_target=getattr(self, "_install_explicit_target", False),
            managed_command_files=generated_command_files,
        )
        self._generated_command_files = tuple(sorted(generated_command_files))
        return count

    def _install_content(self, gpd_root: Path, target_dir: Path, path_prefix: str, failures: list[str]) -> None:
        bridge_command = self.runtime_cli_bridge_command(target_dir)

        def _translate(content: str, prefix: str, install_scope: str | None = None) -> str:
            translated = super(OpenCodeAdapter, self).translate_shared_markdown(
                content,
                prefix,
                install_scope=install_scope,
            )
            return _rewrite_gpd_cli_invocations(translated, bridge_command)

        failures.extend(
            install_gpd_content(
                gpd_root / "specs",
                target_dir,
                path_prefix,
                self.runtime_name,
                install_scope=self._current_install_scope_flag(),
                markdown_transform=_translate,
                explicit_target=getattr(self, "_install_explicit_target", False),
            )
        )
        skill_dest = target_dir / "get-physics-done"
        self._gpd_files_count = sum(1 for _ in skill_dest.rglob("*") if _.is_file())

    def _install_agents(self, gpd_root: Path, target_dir: Path, path_prefix: str, failures: list[str]) -> int:
        agents_src = gpd_root / "agents"
        if agents_src.exists():
            agents_dest = target_dir / "agents"
            bridge_command = self.runtime_cli_bridge_command(target_dir)
            return copy_agents_as_agent_files(
                agents_src,
                agents_dest,
                path_prefix,
                gpd_root / "specs",
                self._current_install_scope_flag(),
                bridge_command,
            )
        return 0

    def _install_version(self, target_dir: Path, version: str, failures: list[str]) -> None:
        skill_dest = target_dir / "get-physics-done"
        skill_dest.mkdir(parents=True, exist_ok=True)
        version_dest = skill_dest / "VERSION"
        try:
            version_dest.write_text(version, encoding="utf-8")
        except Exception as exc:
            failures.append(f"VERSION: {exc}")

    def _install_hooks(self, gpd_root: Path, target_dir: Path, failures: list[str]) -> None:
        del gpd_root, target_dir, failures
        # OpenCode does not wire any bundled Python hook surface.
        self._hooks_count = 0

    def _configure_runtime(self, target_dir: Path, is_global: bool) -> dict[str, object]:
        _, config_parse_error = _read_opencode_config_state(target_dir)
        if config_parse_error is not None:
            raise RuntimeError("OpenCode opencode.json is malformed; refusing to overwrite it during install.")
        configure_opencode_permissions(target_dir)

        # Wire MCP servers into opencode.json.
        from gpd.mcp.builtin_servers import build_mcp_servers_dict

        mcp_servers = build_mcp_servers_dict(python_path=hook_python_interpreter())
        project_cwd = None if is_global or getattr(self, "_install_explicit_target", False) else target_dir.parent
        managed_mcp_servers = _project_managed_mcp_servers(cwd=project_cwd)
        if managed_mcp_servers:
            mcp_servers.update(managed_mcp_servers)
        mcp_count = 0
        if mcp_servers:
            mcp_count = _write_mcp_servers_opencode(target_dir, mcp_servers)

        return {
            "target": str(target_dir),
            "hooks": getattr(self, "_hooks_count", 0),
            "gpd_files": getattr(self, "_gpd_files_count", 0),
            "mcpServers": mcp_count,
        }

    def runtime_permissions_status(self, target_dir: Path, *, autonomy: str) -> dict[str, object]:
        """Report whether OpenCode permissions are aligned with GPD autonomy."""
        config_path = target_dir / "opencode.json"
        config, config_parse_error = _read_opencode_config_state(target_dir)
        config_valid = config_parse_error is None
        config = config or {}
        permission_value = config.get("permission")
        desired_mode = "yolo" if autonomy == "yolo" else "default"
        managed_state = self._runtime_permissions_manifest_state(target_dir) or {}
        managed_by_gpd = managed_state.get("mode") == "yolo"
        configured_mode = "malformed" if not config_valid else "yolo" if _opencode_permission_is_yolo(permission_value) else "default"
        requires_relaunch = False
        next_step: str | None = None

        if not config_valid:
            config_aligned = False
            message = "OpenCode opencode.json is malformed; GPD will not treat it as a defaulted permission state."
        elif desired_mode == "yolo":
            config_aligned = configured_mode == "yolo"
            requires_relaunch = config_aligned
            message = (
                "OpenCode is configured for prompt-free permissions on the next session."
                if config_aligned
                else 'OpenCode is not yet configured for prompt-free execution; set `permission` to `"allow"`.'
            )
            if config_aligned:
                next_step = (
                    "Restart OpenCode so the current session picks up the prompt-free permission setting."
                )
        else:
            config_aligned = not managed_by_gpd
            if managed_by_gpd:
                message = "OpenCode is still pinned to a GPD-managed `permission = allow` setting from an earlier yolo sync."
            elif configured_mode == "yolo":
                message = (
                    "OpenCode is still configured for `permission = allow`, but GPD left it untouched because "
                    "that setting was not created by a prior GPD yolo sync."
                )
            else:
                message = "OpenCode is using its normal permission configuration."

        return {
            "runtime": self.runtime_name,
            "desired_mode": desired_mode,
            "configured_mode": configured_mode,
            "config_aligned": config_aligned,
            "requires_relaunch": requires_relaunch,
            "managed_by_gpd": managed_by_gpd,
            "settings_path": str(config_path),
            "config_valid": config_valid,
            "config_parse_error": config_parse_error,
            "message": message,
            "next_step": next_step,
        }

    def sync_runtime_permissions(self, target_dir: Path, *, autonomy: str) -> dict[str, object]:
        """Align OpenCode permissions with the requested autonomy mode."""
        config, config_parse_error = _read_opencode_config_state(target_dir)
        if config_parse_error is not None:
            status = self.runtime_permissions_status(target_dir, autonomy=autonomy)
            return {
                **status,
                "changed": False,
                "sync_applied": False,
                "requires_relaunch": False,
                "warning": "OpenCode opencode.json is malformed; GPD will not overwrite it.",
            }
        config = config or {}
        changed = False

        if autonomy == "yolo":
            current_permission = config.get("permission")
            if not _opencode_permission_is_yolo(current_permission):
                restore_state = {
                    "had_permission": "permission" in config,
                    "permission": _clone_json_value(current_permission),
                }
                config["permission"] = _OPENCODE_YOLO_PERMISSION
                _write_opencode_config(target_dir, config)
                self._set_runtime_permissions_manifest_state(
                    target_dir,
                    {
                        "mode": "yolo",
                        "restore": restore_state,
                    },
                )
                changed = True

            status = self.runtime_permissions_status(target_dir, autonomy=autonomy)
            sync_applied = bool(status.get("config_aligned"))
            return {
                **status,
                "changed": changed,
                "sync_applied": sync_applied,
                "requires_relaunch": changed,
                "next_step": "Restart OpenCode so the current session picks up the prompt-free permission setting."
                if changed
                else None,
            }

        managed_state = self._runtime_permissions_manifest_state(target_dir) or {}
        restore_state = managed_state.get("restore") if isinstance(managed_state, dict) else None
        if managed_state.get("mode") == "yolo" and isinstance(restore_state, dict):
            if restore_state.get("had_permission"):
                config["permission"] = _clone_json_value(restore_state.get("permission"))
            else:
                config.pop("permission", None)
            _write_opencode_config(target_dir, config)
            changed = True
            if configure_opencode_permissions(target_dir):
                changed = True
            self._set_runtime_permissions_manifest_state(target_dir, None)

        status = self.runtime_permissions_status(target_dir, autonomy=autonomy)
        sync_applied = bool(status.get("config_aligned"))
        result = {
            **status,
            "changed": changed,
            "sync_applied": sync_applied,
            "requires_relaunch": changed,
        }
        if changed:
            result["next_step"] = "Restart OpenCode to return the session to its normal permission configuration."
        return result

    def _write_manifest(self, target_dir: Path, version: str) -> None:
        write_manifest(
            target_dir,
            version,
            runtime=self.runtime_name,
            install_scope=self._current_install_scope_flag(),
            explicit_target=getattr(self, "_install_explicit_target", False),
            managed_command_file_names=getattr(self, "_generated_command_files", ()),
        )

    def uninstall(self, target_dir: Path) -> dict[str, object]:
        """Remove GPD from an OpenCode config directory.

        OpenCode-specific cleanup:
        - command/gpd-*.md (flat structure, not commands/gpd/)
        - opencode.json permission entries
        - Standard GPD dirs (get-physics-done/, agents/, hooks/)
        """
        from gpd.core.observability import gpd_span

        with gpd_span("adapter.uninstall", runtime=self.runtime_name, target=str(target_dir)) as span:
            self._validate_target_runtime(target_dir, action="uninstall from")
            result = uninstall_opencode(
                target_dir,
                config_dir=target_dir,
                allow_empty_config_removal=self._has_authoritative_install_manifest(target_dir),
            )
            removed: list[str] = []
            if result["commands"]:
                removed.append(f"{result['commands']} GPD commands")
            if result["dirs"]:
                removed.append("get-physics-done/")
            if result["agents"]:
                removed.append(f"{result['agents']} GPD agents")
            if result["hooks"]:
                removed.append(f"{result['hooks']} GPD hooks")
            if result["permissions"]:
                removed.append("opencode.json permissions")

            span.set_attribute("gpd.removed_count", len(removed))
            logger.info("Uninstalled GPD from %s: removed %d items", self.runtime_name, len(removed))

            return {"runtime": self.runtime_name, "target": str(target_dir), "removed": removed}


__all__ = [
    "OpenCodeAdapter",
    "get_opencode_global_dir",
    "convert_tool_name",
    "convert_claude_to_opencode_frontmatter",
    "configure_opencode_permissions",
    "copy_flattened_commands",
    "copy_agents_as_agent_files",
    "copy_with_path_replacement",
    "write_manifest",
    "uninstall_opencode",
]
