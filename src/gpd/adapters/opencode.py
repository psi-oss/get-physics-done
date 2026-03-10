"""OpenCode runtime adapter.

Handles:
- XDG Base Directory config path resolution (4-level precedence)
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
from pathlib import Path

from gpd.adapters.base import RuntimeAdapter
from gpd.adapters.install_utils import (
    HOOK_SCRIPTS,
    MANIFEST_NAME,
    PATCHES_DIR_NAME,
    compute_path_prefix,
    convert_tool_references_in_body,
    expand_at_includes,
    file_hash,
    generate_manifest,
    get_global_dir,
    parse_jsonc,
    remove_stale_agents,
    replace_placeholders,
)
from gpd.adapters.tool_names import reference_translation_map, translate_for_runtime

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_TOOL_REFERENCE_MAP = reference_translation_map("opencode")

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

# ---------------------------------------------------------------------------
# XDG config directory resolution
# ---------------------------------------------------------------------------


def get_opencode_global_dir(explicit_dir: str | None = None) -> Path:
    """Resolve the global config directory for OpenCode.

    Delegates to ``install_utils.get_global_dir`` which implements the full
    XDG Base Directory spec with 4-level precedence:
    1. explicit_dir (from --config-dir flag)
    2. OPENCODE_CONFIG_DIR env var
    3. dirname(OPENCODE_CONFIG) env var
    4. XDG_CONFIG_HOME/opencode env var
    5. ~/.config/opencode (XDG default)
    """
    return Path(get_global_dir("opencode", explicit_dir))


# ---------------------------------------------------------------------------
# Tool name conversion
# ---------------------------------------------------------------------------


def convert_tool_name(tool_name: str) -> str:
    """Convert a canonical GPD tool name or runtime alias to OpenCode format.

    OpenCode keeps MCP tools as-is, so this never returns ``None``.
    """
    mapped = translate_for_runtime(tool_name, "opencode")
    return mapped if mapped is not None else tool_name


# ---------------------------------------------------------------------------
# Frontmatter conversion
# ---------------------------------------------------------------------------


def convert_claude_to_opencode_frontmatter(content: str) -> str:
    """Convert canonical GPD frontmatter to OpenCode format.

    Transformations:
    - Replace tool name references in content
    - Replace /gpd: with /gpd- (flat command structure)
    - Replace ~/.claude with ~/.config/opencode
    - Parse YAML frontmatter:
      - Strip name: field (OpenCode uses filename for command name)
      - Convert color names to hex
      - Convert allowed-tools: YAML array to tools: object with {tool: true}
    """
    converted = content
    converted = convert_tool_references_in_body(converted, _TOOL_REFERENCE_MAP)
    converted = converted.replace("/gpd:", "/gpd-")
    converted = re.sub(r"~/\.claude\b", "~/.config/opencode", converted)

    if not converted.startswith("---"):
        return converted

    end_index = converted.find("---", 3)
    if end_index == -1:
        return converted

    frontmatter = converted[3:end_index].strip()
    body = converted[end_index + 3 :]

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
    return f"---\n{new_frontmatter}\n---{body}"


# ---------------------------------------------------------------------------
# Command copying (flattened structure)
# ---------------------------------------------------------------------------


def copy_flattened_commands(
    src_dir: Path,
    dest_dir: Path,
    prefix: str,
    path_prefix: str,
) -> int:
    """Copy commands to a flat structure for OpenCode.

    OpenCode expects: command/gpd-help.md (invoked as /gpd-help)
    Source structure: commands/gpd/help.md

    Returns the count of files written.
    """
    if not src_dir.exists():
        return 0

    # Remove old gpd-*.md files before copying new ones
    if dest_dir.exists():
        for f in dest_dir.iterdir():
            if f.name.startswith(f"{prefix}-") and f.name.endswith(".md"):
                f.unlink()
    else:
        dest_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for entry in sorted(src_dir.iterdir()):
        if entry.is_dir():
            count += copy_flattened_commands(
                entry,
                dest_dir,
                f"{prefix}-{entry.name}",
                path_prefix,
            )
        elif entry.name.endswith(".md"):
            base_name = entry.stem
            dest_name = f"{prefix}-{base_name}.md"
            dest_path = dest_dir / dest_name

            content = entry.read_text(encoding="utf-8")
            content = replace_placeholders(content, path_prefix)
            content = convert_claude_to_opencode_frontmatter(content)

            dest_path.write_text(content, encoding="utf-8")
            count += 1

    return count


# ---------------------------------------------------------------------------
# Agent copying
# ---------------------------------------------------------------------------


def copy_agents_as_agent_files(
    agents_src: Path,
    agents_dest: Path,
    path_prefix: str,
) -> int:
    """Copy agent .md files with OpenCode frontmatter conversion.

    Writes new agents first, then removes stale ones (safe order prevents data loss).
    Returns the count of agents written.
    """
    if not agents_src.exists():
        return 0

    agents_dest.mkdir(parents=True, exist_ok=True)

    new_agent_names: set[str] = set()
    count = 0

    for entry in sorted(agents_src.iterdir()):
        if not entry.is_file() or not entry.name.endswith(".md"):
            continue

        content = entry.read_text(encoding="utf-8")
        content = replace_placeholders(content, path_prefix)
        content = expand_at_includes(content, str(agents_dest.parent / "get-physics-done"), path_prefix)
        content = convert_claude_to_opencode_frontmatter(content)

        (agents_dest / entry.name).write_text(content, encoding="utf-8")
        new_agent_names.add(entry.name)
        count += 1

    remove_stale_agents(agents_dest, new_agent_names)

    return count


# ---------------------------------------------------------------------------
# Permission configuration
# ---------------------------------------------------------------------------


def _opencode_managed_permission_key(config_dir: Path) -> str:
    """Return the exact permission key managed by GPD for *config_dir*."""
    actual_config_dir = config_dir.expanduser()
    default_config_dir = (Path.home() / ".config" / "opencode").expanduser()
    try:
        is_default_config_dir = actual_config_dir.resolve() == default_config_dir.resolve()
    except OSError:
        is_default_config_dir = actual_config_dir == default_config_dir

    if is_default_config_dir:
        return "~/.config/opencode/get-physics-done/*"

    return f"{actual_config_dir.as_posix()}/get-physics-done/*"


def configure_opencode_permissions(config_dir: Path) -> bool:
    """Configure OpenCode permissions to allow reading GPD reference docs.

    Modifies opencode.json to add permission.read and permission.external_directory
    grants for the GPD path. Returns True if config was modified.
    """
    config_path = config_dir / "opencode.json"

    # Ensure config directory exists
    config_dir.mkdir(parents=True, exist_ok=True)

    # Read existing config or create empty object
    config: dict = {}
    if config_path.exists():
        try:
            raw = config_path.read_text(encoding="utf-8")
            config = parse_jsonc(raw)
        except (json.JSONDecodeError, ValueError):
            config = {}

    # Ensure permission structure exists
    if "permission" not in config or not isinstance(config["permission"], dict):
        config["permission"] = {}

    gpd_path = _opencode_managed_permission_key(config_dir)

    modified = False

    # Configure read permission
    if "read" not in config["permission"] or not isinstance(config["permission"]["read"], dict):
        config["permission"]["read"] = {}
    if config["permission"]["read"].get(gpd_path) != "allow":
        config["permission"]["read"][gpd_path] = "allow"
        modified = True

    # Configure external_directory permission
    if "external_directory" not in config["permission"] or not isinstance(
        config["permission"]["external_directory"], dict
    ):
        config["permission"]["external_directory"] = {}
    if config["permission"]["external_directory"].get(gpd_path) != "allow":
        config["permission"]["external_directory"][gpd_path] = "allow"
        modified = True

    if modified:
        config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

    return modified


# ---------------------------------------------------------------------------
# Manifest (OpenCode-specific: uses command/ not commands/gpd/)
# ---------------------------------------------------------------------------


def write_manifest(config_dir: Path, version: str) -> dict:
    """Write file manifest after installation for future modification detection.

    OpenCode-specific: scans ``command/gpd-*.md`` (flat) instead of
    ``commands/gpd/`` (nested).
    """
    from datetime import UTC, datetime

    gpd_dir = config_dir / "get-physics-done"
    command_dir = config_dir / "command"
    agents_dir = config_dir / "agents"

    manifest: dict = {
        "version": version,
        "timestamp": datetime.now(UTC).isoformat(),
        "files": {},
    }

    # get-physics-done/ files
    gpd_hashes = generate_manifest(gpd_dir)
    for rel, h in gpd_hashes.items():
        manifest["files"]["get-physics-done/" + rel] = h

    # command/gpd-*.md files (OpenCode flat structure)
    if command_dir.exists():
        for f in sorted(command_dir.iterdir()):
            if f.name.startswith("gpd-") and f.name.endswith(".md"):
                manifest["files"]["command/" + f.name] = file_hash(f)

    # agents/gpd-*.md files
    if agents_dir.exists():
        for f in sorted(agents_dir.iterdir()):
            if f.name.startswith("gpd-") and f.name.endswith(".md"):
                manifest["files"]["agents/" + f.name] = file_hash(f)

    manifest_path = config_dir / MANIFEST_NAME
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


# ---------------------------------------------------------------------------
# Copy directory with path replacement (OpenCode-specific)
# ---------------------------------------------------------------------------


def _copy_dir_contents(src_dir: Path, target_dir: Path, path_prefix: str) -> None:
    """Recursively copy directory contents with path replacement in .md files.

    OpenCode-specific: applies frontmatter conversion to all .md files.
    """
    for entry in sorted(src_dir.iterdir()):
        dest_path = target_dir / entry.name
        if entry.is_dir():
            dest_path.mkdir(parents=True, exist_ok=True)
            _copy_dir_contents(entry, dest_path, path_prefix)
        elif entry.name.endswith(".md"):
            content = entry.read_text(encoding="utf-8")
            content = replace_placeholders(content, path_prefix)
            content = convert_claude_to_opencode_frontmatter(content)
            dest_path.write_text(content, encoding="utf-8")
        else:
            shutil.copy2(entry, dest_path)


def copy_with_path_replacement(src_dir: Path, dest_dir: Path, path_prefix: str) -> None:
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
        _copy_dir_contents(src_dir, tmp_dir, path_prefix)

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


def uninstall_opencode(target_dir: Path, config_dir: Path | None = None) -> dict[str, int]:
    """Uninstall GPD from an OpenCode config directory.

    Removes GPD-specific files/directories, preserves user content.
    Returns a dict with counts of removed items.
    """
    counts: dict[str, int] = {"commands": 0, "agents": 0, "hooks": 0, "dirs": 0, "permissions": 0}

    # 1. Remove command/gpd-*.md files
    command_dir = target_dir / "command"
    if command_dir.exists():
        for f in command_dir.iterdir():
            if f.name.startswith("gpd-") and f.name.endswith(".md"):
                f.unlink()
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
        for hook_path in hooks_dir.iterdir():
            if not hook_path.is_file():
                continue
            if hook_path.name in HOOK_SCRIPTS.values():
                hook_path.unlink()
                counts["hooks"] += 1

    # 5. Remove GPD MCP servers from opencode.json (uses "mcp" key, not "mcpServers")
    oc_config_dir_mcp = config_dir or get_opencode_global_dir()
    oc_config_path_mcp = oc_config_dir_mcp / "opencode.json"
    if oc_config_path_mcp.exists():
        try:
            oc_mcp = parse_jsonc(oc_config_path_mcp.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            oc_mcp = None
        if isinstance(oc_mcp, dict) and isinstance(oc_mcp.get("mcp"), dict):
            from gpd.mcp.builtin_servers import GPD_MCP_SERVER_KEYS

            gpd_keys = [k for k in oc_mcp["mcp"] if k in GPD_MCP_SERVER_KEYS]
            for k in gpd_keys:
                del oc_mcp["mcp"][k]
            if gpd_keys:
                if not oc_mcp["mcp"]:
                    del oc_mcp["mcp"]
                oc_config_path_mcp.write_text(json.dumps(oc_mcp, indent=2) + "\n", encoding="utf-8")

    # 6. Clean up permissions from opencode.json
    oc_config_dir = config_dir or get_opencode_global_dir()
    oc_config_path = oc_config_dir / "opencode.json"
    if oc_config_path.exists():
        try:
            oc_config = parse_jsonc(oc_config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            oc_config = None
        if not isinstance(oc_config, dict):
            oc_config = None
        modified = False

        if oc_config is not None and isinstance(oc_config.get("permission"), dict):
            managed_key = _opencode_managed_permission_key(oc_config_dir)
            for perm_type in ("read", "external_directory"):
                perm_dict = oc_config["permission"].get(perm_type)
                if isinstance(perm_dict, dict):
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

    config: dict = {}
    if config_path.exists():
        config = parse_jsonc(config_path.read_text(encoding="utf-8"))

    existing_mcp = config.get("mcp", {})
    if not isinstance(existing_mcp, dict):
        existing_mcp = {}

    for name, entry in servers.items():
        cmd = str(entry.get("command", ""))
        raw_args = entry.get("args", [])
        args_list = list(raw_args) if isinstance(raw_args, list) else []
        # OpenCode wants command as a single array: ["executable", "arg1", "arg2"]
        command_array = [cmd] + [str(a) for a in args_list]

        oc_entry: dict[str, object] = {
            "type": "local",
            "command": command_array,
            "enabled": True,
        }
        raw_env = entry.get("env", {})
        if isinstance(raw_env, dict) and raw_env:
            oc_entry["environment"] = dict(raw_env)

        existing_mcp[name] = oc_entry

    config["mcp"] = existing_mcp
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    return len(servers)


class OpenCodeAdapter(RuntimeAdapter):
    """Adapter for OpenCode."""

    @property
    def runtime_name(self) -> str:
        return "opencode"

    @property
    def display_name(self) -> str:
        return "OpenCode"

    @property
    def config_dir_name(self) -> str:
        return ".opencode"

    @property
    def help_command(self) -> str:
        return "/gpd-help"

    @property
    def global_config_dir(self) -> Path:
        """OpenCode uses XDG Base Directory spec with env var precedence."""
        return get_opencode_global_dir()

    # --- Template method hooks ---

    def _compute_path_prefix(self, target_dir: Path, is_global: bool) -> str:
        return compute_path_prefix(
            target_dir,
            self.config_dir_name,
            is_global=is_global,
            explicit_target=getattr(self, "_install_explicit_target", False),
        )

    def _install_commands(self, gpd_root: Path, target_dir: Path, path_prefix: str, failures: list[str]) -> int:
        commands_src = gpd_root / "commands"
        command_dir = target_dir / "command"
        command_dir.mkdir(parents=True, exist_ok=True)
        return copy_flattened_commands(commands_src, command_dir, "gpd", path_prefix)

    def _install_content(self, gpd_root: Path, target_dir: Path, path_prefix: str, failures: list[str]) -> None:
        specs_dir = gpd_root / "specs"
        skill_dest = target_dir / "get-physics-done"
        skill_dest.mkdir(parents=True, exist_ok=True)
        for subdir_name in ("references", "templates", "workflows"):
            src_subdir = specs_dir / subdir_name
            if src_subdir.is_dir():
                try:
                    copy_with_path_replacement(src_subdir, skill_dest / subdir_name, path_prefix)
                except Exception as exc:
                    failures.append(f"get-physics-done/{subdir_name}: {exc}")
        self._gpd_files_count = sum(1 for _ in skill_dest.rglob("*") if _.is_file())

    def _install_agents(self, gpd_root: Path, target_dir: Path, path_prefix: str, failures: list[str]) -> int:
        agents_src = gpd_root / "agents"
        if agents_src.exists():
            agents_dest = target_dir / "agents"
            return copy_agents_as_agent_files(agents_src, agents_dest, path_prefix)
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
        hooks_src = gpd_root / "hooks"
        self._hooks_count = 0
        if hooks_src.exists():
            hooks_dest = target_dir / "hooks"
            hooks_dest.mkdir(parents=True, exist_ok=True)
            try:
                for entry in hooks_src.iterdir():
                    if entry.is_file() and not entry.name.startswith("__"):
                        shutil.copy2(entry, hooks_dest / entry.name)
                        self._hooks_count += 1
            except Exception as exc:
                failures.append(f"hooks: {exc}")

    def _configure_runtime(self, target_dir: Path, is_global: bool) -> dict[str, object]:
        configure_opencode_permissions(target_dir)

        # Wire MCP servers into opencode.json.
        import sys

        from gpd.mcp.builtin_servers import build_mcp_servers_dict

        mcp_servers = build_mcp_servers_dict(python_path=sys.executable)
        mcp_count = 0
        if mcp_servers:
            mcp_count = _write_mcp_servers_opencode(target_dir, mcp_servers)

        return {
            "target": str(target_dir),
            "hooks": getattr(self, "_hooks_count", 0),
            "gpd_files": getattr(self, "_gpd_files_count", 0),
            "mcpServers": mcp_count,
        }

    def _write_manifest(self, target_dir: Path, version: str) -> None:
        write_manifest(target_dir, version)

    def uninstall(self, target_dir: Path) -> dict[str, object]:
        """Remove GPD from an OpenCode config directory.

        OpenCode-specific cleanup:
        - command/gpd-*.md (flat structure, not commands/gpd/)
        - opencode.json permission entries
        - Standard GPD dirs (get-physics-done/, agents/, hooks/)
        """
        from gpd.core.observability import gpd_span

        with gpd_span("adapter.uninstall", runtime=self.runtime_name, target=str(target_dir)) as span:
            result = uninstall_opencode(target_dir, config_dir=target_dir)
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
