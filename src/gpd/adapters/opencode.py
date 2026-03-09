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
    LEGACY_HOOK_BASENAMES,
    MANIFEST_NAME,
    PATCHES_DIR_NAME,
    file_hash,
    generate_manifest,
    get_global_dir,
    parse_jsonc,
    remove_stale_agents,
    replace_placeholders,
)
from gpd.adapters.tool_names import OPENCODE, canonical

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Claude Code tool name → OpenCode tool name (special mappings)
_CLAUDE_TO_OPENCODE: dict[str, str] = {
    "AskUserQuestion": "question",
    "Bash": "shell",
    "Edit": "edit_file",
    "Read": "read_file",
    "SlashCommand": "skill",
    "TodoWrite": "todowrite",
    "WebFetch": "webfetch",
    "WebSearch": "websearch",
    "Write": "write_file",
}

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


def convert_tool_name(claude_tool: str) -> str:
    """Convert a Claude Code tool name to OpenCode format.

    - Applies special mappings (AskUserQuestion → question, etc.)
    - MCP tools (mcp__*) keep their format
    - Default: convert to lowercase
    """
    if claude_tool in _CLAUDE_TO_OPENCODE:
        return _CLAUDE_TO_OPENCODE[claude_tool]
    if claude_tool.startswith("mcp__"):
        return claude_tool
    return claude_tool.lower()


# ---------------------------------------------------------------------------
# Frontmatter conversion
# ---------------------------------------------------------------------------


def convert_claude_to_opencode_frontmatter(content: str) -> str:
    """Convert Claude Code frontmatter to OpenCode format.

    Transformations:
    - Replace tool name references in content (AskUserQuestion→question, etc.)
    - Replace /gpd: with /gpd- (flat command structure)
    - Replace ~/.claude with ~/.config/opencode
    - Parse YAML frontmatter:
      - Strip name: field (OpenCode uses filename for command name)
      - Convert color names to hex
      - Convert allowed-tools: YAML array to tools: object with {tool: true}
    """
    converted = content
    converted = re.sub(r"\bAskUserQuestion\b", "question", converted)
    converted = re.sub(r"\bSlashCommand\b", "skill", converted)
    converted = re.sub(r"\bTodoWrite\b", "todowrite", converted)
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
            continue

        # Remove name: field — OpenCode uses filename for command name
        if trimmed.startswith("name:"):
            continue

        # Convert color names to hex for OpenCode
        if trimmed.startswith("color:"):
            color_value = trimmed[6:].strip().lower()
            hex_color = _COLOR_NAME_TO_HEX.get(color_value)
            if hex_color:
                new_lines.append(f'color: "{hex_color}"')
            elif color_value.startswith("#"):
                if _HEX_COLOR_RE.match(color_value):
                    new_lines.append(line)
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
        content = convert_claude_to_opencode_frontmatter(content)

        (agents_dest / entry.name).write_text(content, encoding="utf-8")
        new_agent_names.add(entry.name)
        count += 1

    remove_stale_agents(agents_dest, new_agent_names)

    return count


# ---------------------------------------------------------------------------
# Permission configuration
# ---------------------------------------------------------------------------


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
        raw = config_path.read_text(encoding="utf-8")
        config = parse_jsonc(raw)

    # Ensure permission structure exists
    if "permission" not in config or not isinstance(config["permission"], dict):
        config["permission"] = {}

    # Build the GPD path using the actual config directory
    default_config_dir = Path.home() / ".config" / "opencode"
    if config_dir == default_config_dir:
        gpd_path = "~/.config/opencode/get-physics-done/*"
    else:
        gpd_path = f"{str(config_dir).replace(os.sep, '/')}/get-physics-done/*"

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
            if hook_path.name in HOOK_SCRIPTS.values() or hook_path.stem in LEGACY_HOOK_BASENAMES:
                hook_path.unlink()
                counts["hooks"] += 1

    # 5. Clean up settings.json (remove GPD hooks and statusline)
    settings_path = target_dir / "settings.json"
    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            settings = None
        if not isinstance(settings, dict):
            settings = None

        if settings is not None:
            settings_modified = False

            # Remove GPD statusline
            if (
                isinstance(settings.get("statusLine"), dict)
                and isinstance(settings["statusLine"].get("command"), str)
                and (
                    "gpd-statusline" in settings["statusLine"]["command"]
                    or "statusline.py" in settings["statusLine"]["command"]
                )
            ):
                del settings["statusLine"]
                settings_modified = True

            # Remove GPD hooks from SessionStart
            if isinstance(settings.get("hooks"), dict) and isinstance(settings["hooks"].get("SessionStart"), list):
                before = len(settings["hooks"]["SessionStart"])
                settings["hooks"]["SessionStart"] = [
                    entry
                    for entry in settings["hooks"]["SessionStart"]
                    if not (
                        isinstance(entry.get("hooks"), list)
                        and any(
                            isinstance(h.get("command"), str)
                            and (
                                "gpd-check-update" in h["command"]
                                or "check_update" in h["command"]
                                or "gpd-statusline" in h["command"]
                                or "statusline.py" in h["command"]
                            )
                            for h in entry["hooks"]
                        )
                    )
                ]
                if len(settings["hooks"]["SessionStart"]) < before:
                    settings_modified = True
                if not settings["hooks"]["SessionStart"]:
                    del settings["hooks"]["SessionStart"]
                if not settings["hooks"]:
                    del settings["hooks"]

            if settings_modified:
                tmp_path = settings_path.with_suffix(".tmp")
                tmp_path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
                tmp_path.rename(settings_path)

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
            for perm_type in ("read", "external_directory"):
                perm_dict = oc_config["permission"].get(perm_type)
                if isinstance(perm_dict, dict):
                    keys_to_remove = [k for k in perm_dict if "get-physics-done" in k]
                    for k in keys_to_remove:
                        del perm_dict[k]
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

    def translate_tool_name(self, canonical_name: str) -> str:
        canon = canonical(canonical_name)
        mapped = OPENCODE.get(canon)
        if mapped:
            return mapped
        # Also check the Claude→OpenCode special mapping
        return convert_tool_name(canonical_name)

    def generate_command(self, command_def: dict[str, object], target_dir: Path) -> Path:
        """Generate a flattened OpenCode command .md file.

        OpenCode expects: command/gpd-help.md (invoked as /gpd-help)
        """
        name = str(command_def["name"])
        content = str(command_def.get("content", ""))

        command_dir = target_dir / "command"
        command_dir.mkdir(parents=True, exist_ok=True)

        # Apply frontmatter conversion
        content = convert_claude_to_opencode_frontmatter(content)

        out_path = command_dir / f"{name}.md"
        out_path.write_text(content, encoding="utf-8")
        return out_path

    def generate_agent(self, agent_def: dict[str, object], target_dir: Path) -> Path:
        """Generate an OpenCode agent .md file with converted frontmatter."""
        name = str(agent_def["name"])
        content = str(agent_def.get("content", ""))

        agents_dir = target_dir / "agents"
        agents_dir.mkdir(parents=True, exist_ok=True)

        content = convert_claude_to_opencode_frontmatter(content)

        out_path = agents_dir / f"{name}.md"
        out_path.write_text(content, encoding="utf-8")
        return out_path

    def generate_hook(self, hook_name: str, hook_config: dict[str, object]) -> dict[str, object]:
        """Generate an OpenCode hook configuration entry.

        OpenCode hooks are different from Claude's settings.json hooks.
        For now, return a dict with the hook command that can be integrated
        into the OpenCode config.
        """
        command = str(hook_config.get("command", ""))
        event = str(hook_config.get("event", ""))
        return {"hook_name": hook_name, "event": event, "command": command}

    # --- Template method hooks ---

    def _compute_path_prefix(self, target_dir: Path, is_global: bool) -> str:
        return f"{str(target_dir).replace(os.sep, '/')}/"

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
                copy_with_path_replacement(src_subdir, skill_dest / subdir_name, path_prefix)
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
        version_dest.write_text(version, encoding="utf-8")

    def _install_hooks(self, gpd_root: Path, target_dir: Path, failures: list[str]) -> None:
        hooks_src = gpd_root / "hooks"
        self._hooks_count = 0
        if hooks_src.exists():
            hooks_dest = target_dir / "hooks"
            hooks_dest.mkdir(parents=True, exist_ok=True)
            for entry in hooks_src.iterdir():
                if entry.is_file() and not entry.name.startswith("__"):
                    shutil.copy2(entry, hooks_dest / entry.name)
                    self._hooks_count += 1

    def _configure_runtime(self, target_dir: Path, is_global: bool) -> dict[str, object]:
        configure_opencode_permissions(target_dir)
        return {
            "target": str(target_dir),
            "hooks": self._hooks_count,
            "gpd_files": getattr(self, "_gpd_files_count", 0),
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
            result = uninstall_opencode(target_dir, config_dir=self.global_config_dir)
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
