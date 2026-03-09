"""OpenAI Codex CLI runtime adapter — full install/uninstall parity with old install.js.

Codex CLI uses SKILLS (not commands). Each skill is a directory under
~/.agents/skills/<skill-name>/SKILL.md with YAML frontmatter.

Config directory: CODEX_CONFIG_DIR env var > ~/.codex
Skills directory: CODEX_SKILLS_DIR env var > ~/.agents/skills/

Hooks go into config.toml (TOML format), not settings.json.
"""

from __future__ import annotations

import logging
import re
import shutil
from pathlib import Path

from gpd.adapters.base import RuntimeAdapter
from gpd.adapters.install_utils import (
    HOOK_SCRIPTS,
    MANIFEST_NAME,
    PATCHES_DIR_NAME,
    convert_tool_references_in_body,
    expand_at_includes,
    pre_install_cleanup,
    remove_stale_agents,
    replace_placeholders,
    verify_installed,
    write_manifest,
)
from gpd.adapters.install_utils import (
    get_codex_global_dir as _get_codex_global_dir_str,
)
from gpd.adapters.install_utils import (
    get_codex_skills_dir as _get_codex_skills_dir_str,
)
from gpd.adapters.tool_names import CODEX, canonical
from gpd.core.observability import gpd_span

logger = logging.getLogger(__name__)

# ─── Claude Code → Codex tool name mapping (for body text conversion) ─────────

_CLAUDE_TO_CODEX: dict[str, str | None] = {
    "Bash": "shell",
    "Read": "read_file",
    "Write": "write_file",
    "Edit": "apply_patch",
    "Glob": "glob",
    "Grep": "grep",
    "WebSearch": "web_search",
    "WebFetch": "web_fetch",
    "TodoWrite": "todo",
    "AskUserQuestion": "ask_user",
    "Task": None,  # Excluded — auto-discovered by Codex
}


# ─── Directory helpers ──────────────────────────────────────────────────────


def get_codex_global_dir() -> Path:
    """Get the global config directory for Codex CLI.

    Priority: CODEX_CONFIG_DIR > ~/.codex
    """
    return Path(_get_codex_global_dir_str())


def get_codex_skills_dir() -> Path:
    """Get the global skills directory for Codex CLI.

    Skills are stored in ~/.agents/skills/ (separate from config).
    Priority: CODEX_SKILLS_DIR > ~/.agents/skills
    """
    return Path(_get_codex_skills_dir_str())


# ─── Codex-specific content conversion ─────────────────────────────────────


def _convert_codex_tool_name(claude_tool: str) -> str | None:
    """Convert a Claude Code tool name to Codex CLI format.

    Returns None if the tool should be excluded (e.g. Task — auto-discovered).
    """
    if claude_tool == "Task":
        return None
    # MCP tools keep their format (Codex supports MCP natively)
    if claude_tool.startswith("mcp__"):
        return claude_tool
    if claude_tool in _CLAUDE_TO_CODEX:
        return _CLAUDE_TO_CODEX[claude_tool]
    # Default: lowercase
    return claude_tool.lower()


def _convert_to_codex_skill(content: str, skill_name: str) -> str:
    """Convert Claude Code markdown command/agent to Codex SKILL.md format.

    Codex skills use SKILL.md with YAML frontmatter:
    - name: must be hyphen-case (a-z0-9-)
    - description: primary triggering mechanism (1-1024 chars)
    - allowed-tools: optional tool restrictions
    - color: removed (not supported by Codex CLI)
    """
    # Replace path references
    converted = content.replace("~/.claude/", "~/.codex/")
    # Replace /gpd: with $gpd- for Codex skill invocation syntax
    converted = converted.replace("/gpd:", "$gpd-")

    if not converted.startswith("---"):
        return f"---\nname: {skill_name}\ndescription: GPD skill - {skill_name}\n---\n{converted}"

    end_index = converted.find("---", 3)
    if end_index == -1:
        return f"---\nname: {skill_name}\ndescription: GPD skill - {skill_name}\n---\n{converted}"

    frontmatter = converted[3:end_index].strip()
    body = converted[end_index + 3 :]

    fm_lines = frontmatter.split("\n")
    new_lines: list[str] = []
    in_allowed_tools = False
    tools: list[str] = []
    has_name = False
    has_description = False

    for line in fm_lines:
        trimmed = line.strip()

        # Convert name to hyphen-case for Codex
        if trimmed.startswith("name:"):
            has_name = True
            new_lines.append(f"name: {skill_name}")
            continue

        # Keep description
        if trimmed.startswith("description:"):
            has_description = True
            new_lines.append(line)
            continue

        # Strip color field (not supported by Codex CLI)
        if trimmed.startswith("color:"):
            continue

        # Convert allowed-tools YAML array
        if trimmed.startswith("allowed-tools:"):
            in_allowed_tools = True
            continue

        # Handle inline tools: field
        if trimmed.startswith("tools:"):
            tools_value = trimmed[6:].strip()
            if tools_value:
                parsed = [t.strip() for t in tools_value.split(",") if t.strip()]
                for t in parsed:
                    mapped = _convert_codex_tool_name(t)
                    if mapped:
                        tools.append(mapped)
            else:
                in_allowed_tools = True
            continue

        # Collect array items
        if in_allowed_tools:
            if trimmed.startswith("- "):
                mapped = _convert_codex_tool_name(trimmed[2:].strip())
                if mapped:
                    tools.append(mapped)
                continue
            elif trimmed and not trimmed.startswith("-"):
                in_allowed_tools = False

        if not in_allowed_tools:
            new_lines.append(line)

    # Ensure required fields
    if not has_name:
        new_lines.insert(0, f"name: {skill_name}")
    if not has_description:
        new_lines.insert(1, f"description: GPD skill - {skill_name}")

    # Add allowed-tools as YAML array
    if tools:
        new_lines.append("allowed-tools:")
        for tool in tools:
            new_lines.append(f"  - {tool}")

    new_frontmatter = "\n".join(new_lines).strip()
    return f"---\n{new_frontmatter}\n---{body}"


# ─── Adapter Class ───────────────────────────────────────────────────────────


class CodexAdapter(RuntimeAdapter):
    """Adapter for OpenAI Codex CLI.

    Codex uses a SKILLS model:
    - Commands -> skill directories under ~/.agents/skills/<name>/SKILL.md
    - Agents -> also skill directories + agent .md files under ~/.codex/agents/
    - Hooks -> config.toml ``notify`` array (not settings.json)
    - Config -> ~/.codex/ (CODEX_CONFIG_DIR env var)
    - Skills -> ~/.agents/skills/ (CODEX_SKILLS_DIR env var)
    """

    @property
    def runtime_name(self) -> str:
        return "codex"

    @property
    def display_name(self) -> str:
        return "Codex"

    @property
    def config_dir_name(self) -> str:
        return ".codex"

    @property
    def help_command(self) -> str:
        return "$gpd-help"

    @property
    def global_config_dir(self) -> Path:
        return get_codex_global_dir()

    def translate_tool_name(self, canonical_name: str) -> str:
        canon = canonical(canonical_name)
        return CODEX.get(canon, canon)

    def generate_command(self, command_def: dict[str, object], target_dir: Path) -> Path:
        """Generate a Codex skill directory from a GPD command definition.

        Creates: target_dir/<skill-name>/SKILL.md
        """
        name = str(command_def["name"])
        content = str(command_def.get("content", ""))

        skill_dir = target_dir / name
        skill_dir.mkdir(parents=True, exist_ok=True)
        out_path = skill_dir / "SKILL.md"
        skill_content = _convert_to_codex_skill(content, name)
        skill_content = convert_tool_references_in_body(skill_content, _CLAUDE_TO_CODEX)
        out_path.write_text(skill_content, encoding="utf-8")
        return out_path

    def generate_agent(self, agent_def: dict[str, object], target_dir: Path) -> Path:
        """Generate a Codex agent as a skill directory.

        Creates: target_dir/<name>/SKILL.md (skill format)
        """
        name = str(agent_def["name"])
        content = str(agent_def.get("content", ""))

        skill_dir = target_dir / name
        skill_dir.mkdir(parents=True, exist_ok=True)
        out_path = skill_dir / "SKILL.md"
        skill_content = _convert_to_codex_skill(content, name)
        skill_content = convert_tool_references_in_body(skill_content, _CLAUDE_TO_CODEX)
        out_path.write_text(skill_content, encoding="utf-8")
        return out_path

    def generate_hook(self, hook_name: str, hook_config: dict[str, object]) -> dict[str, object]:
        """Generate a Codex config.toml hook entry.

        Returns dict with 'notify' key containing the command array.
        """
        command = hook_config.get("command", "")
        return {"notify": ["python3", str(command)]}

    def install(
        self,
        gpd_root: Path,
        target_dir: Path,
        *,
        is_global: bool = True,
        skills_dir: Path | None = None,
    ) -> dict[str, object]:
        """Full GPD installation into a Codex CLI configuration directory.

        Stores *skills_dir* for use by template method hooks, then delegates
        to the base class template method.
        """
        self._skills_dir = skills_dir if skills_dir is not None else get_codex_skills_dir()
        return super().install(gpd_root, target_dir, is_global=is_global)

    # --- Template method hooks ---

    def _compute_path_prefix(self, target_dir: Path, is_global: bool) -> str:
        return str(target_dir).replace("\\", "/") + "/" if is_global else f"./{self.config_dir_name}/"

    def _pre_cleanup(self, target_dir: Path) -> None:
        pre_install_cleanup(target_dir, codex_skills_dir=str(self._skills_dir))

    def _install_commands(self, gpd_root: Path, target_dir: Path, path_prefix: str, failures: list[str]) -> int:
        commands_src = gpd_root / "commands"
        self._skills_dir.mkdir(parents=True, exist_ok=True)
        _copy_commands_as_skills(commands_src, self._skills_dir, "gpd", path_prefix)
        skill_count = sum(1 for d in self._skills_dir.iterdir() if d.is_dir() and d.name.startswith("gpd-"))
        logger.info("Installed %d command skills", skill_count)
        return skill_count

    def _install_agents(self, gpd_root: Path, target_dir: Path, path_prefix: str, failures: list[str]) -> int:
        agents_src = gpd_root / "agents"
        gpd_dest = target_dir / "get-physics-done"
        agent_count = 0

        # Install agents as Codex skill directories
        if agents_src.is_dir():
            _copy_agents_as_skills(agents_src, self._skills_dir, path_prefix, gpd_dest)
            agent_count = sum(
                1 for f in agents_src.iterdir() if f.is_file() and f.name.startswith("gpd-") and f.suffix == ".md"
            )
            logger.info("Installed %d agent skills", agent_count)

        # Also install agents as agent .md files
        if agents_src.is_dir():
            agents_dest = target_dir / "agents"
            _copy_agents_as_agent_files(agents_src, agents_dest, path_prefix, gpd_dest)
            if verify_installed(agents_dest, "agents"):
                logger.info("Installed agents")
            else:
                failures.append("agents")

        return agent_count

    def _configure_runtime(self, target_dir: Path, is_global: bool) -> dict[str, object]:
        _configure_config_toml(target_dir, is_global)
        return {
            "target": str(target_dir),
            "skills_dir": str(self._skills_dir),
            "skills": sum(1 for d in self._skills_dir.iterdir() if d.is_dir() and d.name.startswith("gpd-")),
        }

    def _write_manifest(self, target_dir: Path, version: str) -> None:
        write_manifest(target_dir, version, codex_skills_dir=str(self._skills_dir))

    def uninstall(
        self,
        target_dir: Path,
        *,
        skills_dir: Path | None = None,
    ) -> dict[str, object]:
        """Uninstall GPD from a Codex CLI configuration directory.

        Removes only GPD-specific files/directories, preserves user content.
        """
        if skills_dir is None:
            skills_dir = get_codex_skills_dir()

        with gpd_span("adapter.uninstall", runtime=self.runtime_name, target=str(target_dir)) as span:
            removed: list[str] = []
            counts: dict[str, int] = {"skills": 0, "agents": 0, "hooks": 0}

            # 1. Remove gpd-* skill directories from skills_dir
            if skills_dir.exists():
                for entry in list(skills_dir.iterdir()):
                    if entry.is_dir() and entry.name.startswith("gpd-"):
                        shutil.rmtree(entry)
                        counts["skills"] += 1

            # 2. Remove get-physics-done directory
            gpd_dir = target_dir / "get-physics-done"
            if gpd_dir.exists():
                shutil.rmtree(gpd_dir)
                removed.append("get-physics-done/")

            # 3. Remove file manifest and local patches
            manifest = target_dir / MANIFEST_NAME
            if manifest.exists():
                manifest.unlink()
                removed.append(MANIFEST_NAME)
            patches = target_dir / PATCHES_DIR_NAME
            if patches.exists():
                shutil.rmtree(patches)
                removed.append(f"{PATCHES_DIR_NAME}/")

            # 4. Remove GPD agent files (gpd-*.md only)
            agents_dir = target_dir / "agents"
            if agents_dir.exists():
                for f in list(agents_dir.iterdir()):
                    if f.is_file() and f.name.startswith("gpd-") and f.suffix == ".md":
                        f.unlink()
                        counts["agents"] += 1

            # 5. Remove GPD hooks (both Python and legacy JS)
            hooks_dir = target_dir / "hooks"
            if hooks_dir.exists():
                gpd_hooks = [name for h in HOOK_SCRIPTS.values() for name in (h["current"], h["legacy"])]
                for hook_name in gpd_hooks:
                    hook_path = hooks_dir / hook_name
                    if hook_path.exists():
                        hook_path.unlink()
                        counts["hooks"] += 1

            # 6. Clean up config.toml
            config_toml = target_dir / "config.toml"
            if config_toml.exists():
                toml_content = config_toml.read_text(encoding="utf-8")
                if "gpd-" in toml_content or "codex_notify" in toml_content:
                    cleaned = re.sub(r"^.*(?:gpd-|codex_notify).*$", "", toml_content, flags=re.MULTILINE)
                    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
                    config_toml.write_text(cleaned, encoding="utf-8")
                    removed.append("config.toml GPD entries")

            # Build "removed" list matching base class return shape
            if counts["skills"]:
                removed.append(f"{counts['skills']} GPD skills")
            if counts["agents"]:
                removed.append(f"{counts['agents']} GPD agents")
            if counts["hooks"]:
                removed.append(f"{counts['hooks']} GPD hooks")

            span.set_attribute("gpd.removed_count", len(removed))
            logger.info("Uninstalled GPD from %s: removed %d items", self.runtime_name, len(removed))

            return {
                "runtime": self.runtime_name,
                "target": str(target_dir),
                "removed": removed,
                **counts,
            }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _copy_commands_as_skills(
    src_dir: Path,
    skills_dir: Path,
    prefix: str,
    path_prefix: str,
) -> None:
    """Copy commands as Codex skill directories.

    Codex expects: ~/.agents/skills/gpd-help/SKILL.md
    Source structure: commands/help.md -> gpd-help/SKILL.md
    Nested: commands/sub/help.md -> gpd-sub-help/SKILL.md (preserves hierarchy)
    """
    if not src_dir.exists():
        return

    # Remove old gpd-* skill directories before copying (clean slate)
    if skills_dir.exists():
        for entry in list(skills_dir.iterdir()):
            if entry.is_dir() and entry.name.startswith(f"{prefix}-"):
                shutil.rmtree(entry)
    else:
        skills_dir.mkdir(parents=True, exist_ok=True)

    for entry in sorted(src_dir.iterdir()):
        if entry.is_dir():
            # Recurse into subdirectories, adding to prefix
            _copy_commands_as_skills(entry, skills_dir, f"{prefix}-{entry.name}", path_prefix)
        elif entry.suffix == ".md":
            base_name = entry.stem
            skill_name = f"{prefix}-{base_name}"
            skill_dir = skills_dir / skill_name
            skill_dir.mkdir(parents=True, exist_ok=True)

            content = entry.read_text(encoding="utf-8")
            content = replace_placeholders(content, path_prefix)
            content = _convert_to_codex_skill(content, skill_name)
            content = convert_tool_references_in_body(content, _CLAUDE_TO_CODEX)

            (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")


def _copy_agents_as_skills(
    src_dir: Path,
    skills_dir: Path,
    path_prefix: str,
    gpd_content_dir: Path | None = None,
) -> None:
    """Copy agents as Codex skill directories.

    Codex expects: ~/.agents/skills/gpd-verifier/SKILL.md
    Source structure: agents/gpd-verifier.md -> gpd-verifier/SKILL.md
    """
    if not src_dir.exists():
        return
    skills_dir.mkdir(parents=True, exist_ok=True)

    for entry in sorted(src_dir.iterdir()):
        if not entry.is_file() or not entry.name.startswith("gpd-") or entry.suffix != ".md":
            continue

        skill_name = entry.stem
        skill_dir = skills_dir / skill_name

        # Remove existing skill dir for clean write
        if skill_dir.exists():
            shutil.rmtree(skill_dir)
        skill_dir.mkdir(parents=True, exist_ok=True)

        content = entry.read_text(encoding="utf-8")
        content = replace_placeholders(content, path_prefix)

        # Expand @ includes (Codex doesn't support @ file inclusion)
        if gpd_content_dir:
            content = expand_at_includes(content, str(gpd_content_dir), path_prefix)

        content = _convert_to_codex_skill(content, skill_name)
        content = convert_tool_references_in_body(content, _CLAUDE_TO_CODEX)

        (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")


def _copy_agents_as_agent_files(
    agents_src: Path,
    agents_dest: Path,
    path_prefix: str,
    gpd_content_dir: Path | None = None,
) -> None:
    """Copy agents as runtime agent markdown files for Codex.

    Applies Codex-specific frontmatter conversion and tool reference translation.
    """
    if not agents_src.exists():
        return
    agents_dest.mkdir(parents=True, exist_ok=True)

    new_agent_names: set[str] = set()

    for entry in sorted(agents_src.iterdir()):
        if not entry.is_file() or entry.suffix != ".md":
            continue

        content = entry.read_text(encoding="utf-8")
        content = replace_placeholders(content, path_prefix)

        # Expand @ includes for Codex
        if gpd_content_dir:
            content = expand_at_includes(content, str(gpd_content_dir), path_prefix)

        content = _convert_to_codex_skill(content, entry.stem)
        content = convert_tool_references_in_body(content, _CLAUDE_TO_CODEX)

        (agents_dest / entry.name).write_text(content, encoding="utf-8")
        new_agent_names.add(entry.name)

    remove_stale_agents(agents_dest, new_agent_names)


def _configure_config_toml(
    target_dir: Path,
    is_global: bool,
) -> None:
    """Configure the notify hook in Codex config.toml.

    Codex expects notify hooks as a TOML array of commands:
      notify = ["python3", "/path/to/codex_notify.py"]
    """
    config_toml = target_dir / "config.toml"
    toml_content = ""
    if config_toml.exists():
        toml_content = config_toml.read_text(encoding="utf-8")

    notify_hook = HOOK_SCRIPTS["codex_notify"]["current"]
    legacy_hooks = [HOOK_SCRIPTS["codex_notify"]["legacy"], HOOK_SCRIPTS["check_update"]["legacy"]]

    if is_global:
        desired_path = str(target_dir / "hooks" / notify_hook).replace("\\", "/")
    else:
        desired_path = f".codex/hooks/{notify_hook}"

    # Replace legacy JS hook references with Python hook
    for legacy in legacy_hooks:
        if legacy in toml_content:
            toml_content = toml_content.replace(legacy, notify_hook)
            if '"node"' in toml_content:
                toml_content = toml_content.replace('"node"', '"python3"')

    if "notify" not in toml_content:
        toml_content += f'\n# GPD update notification\nnotify = ["python3", "{desired_path}"]\n'

    config_toml.write_text(toml_content, encoding="utf-8")


__all__ = [
    "CodexAdapter",
    "get_codex_global_dir",
    "get_codex_skills_dir",
]
