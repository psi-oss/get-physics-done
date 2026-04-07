"""GitHub Copilot CLI runtime adapter.

Handles:
- Flat command structure: commands/gpd/help.md -> command/gpd-help.md
- Frontmatter conversion: allowed-tools -> tools map, strip name field
- Tool name mapping (follows OpenCode conventions as Copilot CLI tool
  surface is not yet fully documented)
- copilot.json configuration (MCP server definitions)
- Agent file conversion with translated frontmatter
- Full install/uninstall support with file manifest

Assumptions:
- GitHub Copilot CLI uses a .copilot config directory
- Configuration is stored in copilot.json (JSON format)
- Command files use flat naming like OpenCode (command/gpd-help.md)
- MCP server definitions follow the common {command, args, env} shape
"""

from __future__ import annotations

import json
import logging
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
    hook_python_interpreter,
    install_gpd_content,
    managed_hook_paths,
    prune_empty_ancestors,
    remove_empty_json_object_file,
    remove_stale_agents,
    render_markdown_frontmatter,
    replace_placeholders,
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
    "web_search": "web_search",
    "web_fetch": "web_fetch",
    "notebook_edit": "notebook_edit",
    "agent": "agent",
    "ask_user": "ask_user",
    "todo_write": "todo_write",
    "task": "task",
    "slash_command": "skill",
    "tool_search": "tool_search",
}
_TOOL_ALIAS_MAP = build_runtime_alias_map(_TOOL_NAME_MAP)
_TOOL_REFERENCE_MAP = reference_translation_map(_TOOL_NAME_MAP, alias_map=_TOOL_ALIAS_MAP)

_GPD_SLASH_COMMAND_RE = re.compile(r"(?<![A-Za-z0-9/_.-])/gpd:(?P<command>[A-Za-z][A-Za-z0-9-]*)\b")
_MANIFEST_COPILOT_GENERATED_COMMAND_FILES_KEY = "copilot_generated_command_files"

# ---------------------------------------------------------------------------
# Tool name conversion
# ---------------------------------------------------------------------------


def convert_tool_name(tool_name: str) -> str:
    """Convert a canonical GPD tool name or runtime alias to Copilot CLI format.

    Copilot CLI keeps MCP tools as-is, so this never returns ``None``.
    """
    mapped = translate_for_runtime(tool_name, _TOOL_NAME_MAP)
    return mapped if mapped is not None else tool_name


def _project_managed_mcp_servers(
    env: Mapping[str, str] | None = None,
    *,
    cwd: Path | None = None,
) -> dict[str, dict[str, object]]:
    """Project shared optional integrations into Copilot CLI's neutral MCP shape."""
    return _managed_integrations.projected_managed_optional_mcp_servers(env, cwd=cwd)


def _managed_mcp_server_keys() -> frozenset[str]:
    """Return GPD-managed Copilot CLI MCP server keys, including optional integrations."""
    from gpd.mcp.builtin_servers import GPD_MCP_SERVER_KEYS

    return frozenset(set(GPD_MCP_SERVER_KEYS) | set(_managed_integrations.managed_optional_mcp_server_keys()))


# ---------------------------------------------------------------------------
# Frontmatter conversion
# ---------------------------------------------------------------------------


def convert_to_copilot_frontmatter(content: str, path_prefix: str | None = None) -> str:
    """Convert canonical GPD frontmatter to Copilot CLI format.

    Transformations:
    - Replace tool name references in content
    - Replace /gpd: with /gpd- (flat command structure)
    - Replace bare ~/.claude references with the resolved Copilot CLI config dir
    - Parse YAML frontmatter:
      - Strip name: field (Copilot CLI uses filename for command name)
      - Convert allowed-tools: YAML array to tools: object with {tool: true}
    """
    resolved_config_dir = path_prefix[:-1] if path_prefix and path_prefix.endswith("/") else path_prefix
    if not resolved_config_dir:
        resolved_config_dir = "~/.copilot"

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

        # Remove name: field -- Copilot CLI uses filename for command name
        if trimmed.startswith("name:"):
            continue

        # Strip color: field -- Copilot CLI does not support color in frontmatter
        if trimmed.startswith("color:"):
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
    """Copy commands to a flat structure for Copilot CLI.

    Copilot CLI expects: command/gpd-help.md (invoked as /gpd-help)
    Source structure: commands/gpd/help.md

    Returns the count of files written.
    """
    if not src_dir.exists():
        return 0

    dest_dir.mkdir(parents=True, exist_ok=True)
    manifest_root = workflow_target_dir or dest_dir.parent
    tracked_command_files = set(_load_manifest_copilot_generated_command_files(manifest_root))
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
                runtime="copilot-cli",
                path_prefix=path_prefix,
                install_scope=install_scope,
                src_root=gpd_src_root,
                workflow_target_dir=workflow_target_dir,
                explicit_target=explicit_target,
            )
            content = convert_to_copilot_frontmatter(content, path_prefix)

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
    """Copy agent .md files with Copilot CLI frontmatter conversion.

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
            runtime="copilot-cli",
            path_prefix=path_prefix,
            install_scope=install_scope,
            src_root=source_root,
            protect_agent_prompt_body=True,
        )
        content = convert_to_copilot_frontmatter(content, path_prefix)

        (agents_dest / entry.name).write_text(content, encoding="utf-8")
        new_agent_names.add(entry.name)
        count += 1

    remove_stale_agents(agents_dest, new_agent_names)

    return count


# ---------------------------------------------------------------------------
# Config management
# ---------------------------------------------------------------------------


def _write_copilot_config(config_dir: Path, config: dict[str, object]) -> None:
    """Persist Copilot CLI config as normalized JSON."""
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "copilot.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")


def _read_copilot_config(config_dir: Path) -> tuple[dict[str, object] | None, str | None]:
    """Return parsed Copilot CLI config and a malformed marker when parsing fails."""
    config_path = config_dir / "copilot.json"
    if not config_path.exists():
        return None, None
    try:
        raw = config_path.read_text(encoding="utf-8")
        parsed = json.loads(raw)
    except (json.JSONDecodeError, OSError, ValueError):
        return None, "malformed"
    if not isinstance(parsed, dict):
        return None, "malformed"
    if not _copilot_mcp_shape_is_valid(parsed.get("mcp")):
        return None, "malformed"
    return parsed, None


def _copilot_mcp_shape_is_valid(mcp_value: object) -> bool:
    if mcp_value is None:
        return True
    if not isinstance(mcp_value, dict):
        return False
    return all(isinstance(entry, dict) for entry in mcp_value.values())


def configure_copilot_mcp(config_dir: Path) -> bool:
    """Configure Copilot CLI MCP servers for GPD.

    Writes MCP server definitions into copilot.json.
    Returns True if config was modified.
    """
    config, config_parse_error = _read_copilot_config(config_dir)
    if config_parse_error is not None:
        raise RuntimeError("Copilot CLI copilot.json is malformed; refusing to overwrite it during install.")
    config = config or {}

    from gpd.mcp.builtin_servers import build_mcp_servers_dict

    mcp_servers = build_mcp_servers_dict(python_path=hook_python_interpreter())
    if not mcp_servers:
        return False

    existing_mcp = config.get("mcp")
    if not isinstance(existing_mcp, dict):
        existing_mcp = {}

    modified = False
    for key, server_def in mcp_servers.items():
        if existing_mcp.get(key) != server_def:
            existing_mcp[key] = server_def
            modified = True

    if modified:
        config["mcp"] = existing_mcp
        _write_copilot_config(config_dir, config)

    return modified


def _write_mcp_servers_copilot(
    config_dir: Path,
    mcp_servers: dict[str, dict[str, object]],
) -> int:
    """Write MCP server definitions into copilot.json.

    Returns the number of servers written.
    """
    config, config_parse_error = _read_copilot_config(config_dir)
    if config_parse_error is not None:
        raise RuntimeError("Copilot CLI copilot.json is malformed; refusing to overwrite it during install.")
    config = config or {}

    existing_mcp = config.get("mcp")
    if not isinstance(existing_mcp, dict):
        existing_mcp = {}

    managed_keys = _managed_mcp_server_keys()
    # Remove previously managed keys that are no longer in the new set.
    for key in list(existing_mcp):
        if key in managed_keys and key not in mcp_servers:
            del existing_mcp[key]

    count = 0
    for key, server_def in mcp_servers.items():
        existing_mcp[key] = server_def
        count += 1

    config["mcp"] = existing_mcp
    _write_copilot_config(config_dir, config)
    return count


def _cleanup_copilot_config(config_dir: Path) -> list[str]:
    """Remove GPD-managed entries from copilot.json.

    Returns a list of descriptions of removed entries.
    """
    config, config_parse_error = _read_copilot_config(config_dir)
    if config_parse_error is not None or config is None:
        return []

    removed: list[str] = []
    managed_keys = _managed_mcp_server_keys()

    mcp = config.get("mcp")
    if isinstance(mcp, dict):
        mcp_removed = 0
        for key in list(mcp):
            if key in managed_keys:
                del mcp[key]
                mcp_removed += 1
        if mcp_removed:
            removed.append(f"{mcp_removed} MCP servers from copilot.json")

    if removed:
        if not config.get("mcp"):
            config.pop("mcp", None)
        _write_copilot_config(config_dir, config)
        remove_empty_json_object_file(config_dir / "copilot.json")

    return removed


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------


def _load_manifest_copilot_generated_command_files(target_dir: Path) -> tuple[str, ...]:
    """Return tracked Copilot CLI command filenames from the local manifest metadata."""
    manifest_path = target_dir / MANIFEST_NAME
    if not manifest_path.exists():
        return ()

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return ()

    if not isinstance(manifest, dict):
        return ()

    command_files = manifest.get(_MANIFEST_COPILOT_GENERATED_COMMAND_FILES_KEY)
    if not isinstance(command_files, list):
        return ()

    tracked: list[str] = []
    for entry in command_files:
        if isinstance(entry, str) and entry.startswith("gpd-") and entry.endswith(".md"):
            tracked.append(entry)
    return tuple(dict.fromkeys(tracked))


def _load_manifest_copilot_command_files(target_dir: Path) -> tuple[str, ...]:
    """Return tracked Copilot CLI command filenames, falling back to manifest files entries."""
    generated_command_files = _load_manifest_copilot_generated_command_files(target_dir)
    if generated_command_files:
        return generated_command_files

    manifest_path = target_dir / MANIFEST_NAME
    if not manifest_path.exists():
        return ()

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
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

    Copilot CLI-specific: scans ``command/gpd-*.md`` (flat) instead of
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
        manifest[_MANIFEST_COPILOT_GENERATED_COMMAND_FILES_KEY] = sorted(
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

    # command/gpd-*.md files (flat structure)
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
# Uninstall
# ---------------------------------------------------------------------------


def uninstall_copilot_cli(
    target_dir: Path,
    *,
    config_dir: Path,
    allow_empty_config_removal: bool,
) -> dict[str, int]:
    """Uninstall GPD from a Copilot CLI config directory.

    Removes GPD-specific files/directories, preserves user content.
    Returns a dict with counts of removed items.
    """
    counts: dict[str, int] = {"commands": 0, "agents": 0, "hooks": 0, "dirs": 0, "mcp_servers": 0}
    managed_hooks = managed_hook_paths(target_dir)
    tracked_command_files = _load_manifest_copilot_command_files(target_dir)

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

    # 5. Remove GPD-managed MCP servers from copilot.json
    removed_config = _cleanup_copilot_config(config_dir)
    if removed_config:
        counts["mcp_servers"] += len(removed_config)

    # Prune empty directories
    for path in (
        command_dir,
        agents_dir,
        hooks_dir,
        cache_dir,
        target_dir,
    ):
        prune_empty_ancestors(path, stop_at=target_dir.parent)

    # Remove copilot.json if empty
    if allow_empty_config_removal:
        remove_empty_json_object_file(config_dir / "copilot.json")

    return counts


# ---------------------------------------------------------------------------
# Adapter class
# ---------------------------------------------------------------------------


class CopilotCliAdapter(RuntimeAdapter):
    """Adapter for GitHub Copilot CLI."""

    tool_name_map = _TOOL_NAME_MAP
    strip_sub_tags_in_shared_markdown = True

    @property
    def runtime_name(self) -> str:
        return "copilot-cli"

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
        return convert_to_copilot_frontmatter(content, path_prefix)

    def translate_shared_command_references(self, content: str) -> str:
        return content.replace("/gpd:", self.public_command_surface_prefix)

    # --- Template method hooks ---

    def _compute_path_prefix(self, target_dir: Path, is_global: bool) -> str:
        return compute_path_prefix(
            target_dir,
            self.config_dir_name,
            is_global=is_global,
            explicit_target=getattr(self, "_install_explicit_target", False),
        )

    def runtime_install_required_relpaths(self) -> tuple[str, ...]:
        """Return Copilot CLI-owned files required for a complete install."""
        return ("copilot.json",)

    def missing_install_artifacts(self, target_dir: Path) -> tuple[str, ...]:
        """Return missing Copilot CLI install artifacts, including the command surface."""
        missing = list(super().missing_install_artifacts(target_dir))
        command_dir = target_dir / "command"
        tracked_command_files = _load_manifest_copilot_generated_command_files(target_dir)

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
        failures.extend(
            install_gpd_content(
                gpd_root / "specs",
                target_dir,
                path_prefix,
                self.runtime_name,
                install_scope=self._current_install_scope_flag(),
                markdown_transform=self.translate_shared_markdown,
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
        # Copilot CLI does not wire any bundled Python hook surface.
        self._hooks_count = 0

    def _configure_runtime(self, target_dir: Path, is_global: bool) -> dict[str, object]:
        _, config_parse_error = _read_copilot_config(target_dir)
        if config_parse_error is not None:
            raise RuntimeError("Copilot CLI copilot.json is malformed; refusing to overwrite it during install.")

        # Wire MCP servers into copilot.json.
        from gpd.mcp.builtin_servers import build_mcp_servers_dict

        mcp_servers = build_mcp_servers_dict(python_path=hook_python_interpreter())
        project_cwd = None if is_global or getattr(self, "_install_explicit_target", False) else target_dir.parent
        managed_mcp_servers = _project_managed_mcp_servers(cwd=project_cwd)
        if managed_mcp_servers:
            mcp_servers.update(managed_mcp_servers)
        mcp_count = 0
        if mcp_servers:
            mcp_count = _write_mcp_servers_copilot(target_dir, mcp_servers)

        return {
            "target": str(target_dir),
            "hooks": getattr(self, "_hooks_count", 0),
            "gpd_files": getattr(self, "_gpd_files_count", 0),
            "mcpServers": mcp_count,
        }

    def runtime_permissions_status(self, target_dir: Path, *, autonomy: str) -> dict[str, object]:
        """Report Copilot CLI permission status.

        Copilot CLI does not have a documented approval/permission control,
        but the adapter exposes copilot.json as its config-file surface so
        that MCP server management works through the standard config path.
        """
        config_path = target_dir / "copilot.json"
        desired_mode = "yolo" if autonomy == "yolo" else "default"
        return {
            "runtime": self.runtime_name,
            "desired_mode": desired_mode,
            "configured_mode": "default",
            "config_aligned": True,
            "requires_relaunch": False,
            "managed_by_gpd": False,
            "settings_path": str(config_path),
            "message": f"{self.display_name} does not expose a runtime-managed permission surface; MCP servers are configured in copilot.json.",
        }

    def sync_runtime_permissions(self, target_dir: Path, *, autonomy: str) -> dict[str, object]:
        """Copilot CLI does not support runtime permission sync."""
        status = self.runtime_permissions_status(target_dir, autonomy=autonomy)
        return {
            **status,
            "changed": False,
            "sync_applied": False,
        }

    def _cleanup_runtime_config(self, target_dir: Path) -> list[str]:
        return _cleanup_copilot_config(target_dir)

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
        """Remove GPD from a Copilot CLI config directory."""
        from gpd.core.observability import gpd_span

        with gpd_span("adapter.uninstall", runtime=self.runtime_name, target=str(target_dir)) as span:
            self._validate_target_runtime(target_dir, action="uninstall from")
            result = uninstall_copilot_cli(
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
            if result["mcp_servers"]:
                removed.append("copilot.json MCP servers")

            span.set_attribute("gpd.removed_count", len(removed))
            logger.info("Uninstalled GPD from %s: removed %d items", self.runtime_name, len(removed))

            return {"runtime": self.runtime_name, "target": str(target_dir), "removed": removed}


__all__ = [
    "CopilotCliAdapter",
    "convert_tool_name",
    "convert_to_copilot_frontmatter",
    "configure_copilot_mcp",
    "copy_flattened_commands",
    "copy_agents_as_agent_files",
    "write_manifest",
    "uninstall_copilot_cli",
]
