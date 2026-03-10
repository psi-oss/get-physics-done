"""OpenAI Codex CLI runtime adapter.

Codex CLI uses SKILLS (not commands). Each skill is a directory under
~/.agents/skills/<skill-name>/SKILL.md with YAML frontmatter.

Config directory: CODEX_CONFIG_DIR env var > ~/.codex
Skills directory: CODEX_SKILLS_DIR env var > ~/.agents/skills/

Hooks and feature flags go into config.toml (TOML format), not settings.json.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shlex
import shutil
import sys
import tomllib
from pathlib import Path

from gpd.adapters.base import RuntimeAdapter
from gpd.adapters.install_utils import (
    HOOK_SCRIPTS,
    MANIFEST_NAME,
    PATCHES_DIR_NAME,
    convert_tool_references_in_body,
    expand_at_includes,
    hook_python_interpreter,
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
from gpd.adapters.tool_names import reference_translation_map, translate_for_runtime
from gpd.core.observability import gpd_span

logger = logging.getLogger(__name__)

_GPD_NOTIFY_COMMENT = "# GPD update notification"
_GPD_NOTIFY_BACKUP_PREFIX = "# GPD original notify: "
_GPD_MULTI_AGENT_COMMENT = "# GPD multi-agent support"
_GPD_MULTI_AGENT_BACKUP_PREFIX = "# GPD original multi_agent: "
_MANIFEST_CODEX_SKILLS_DIR_KEY = "codex_skills_dir"
_TOOL_REFERENCE_MAP = reference_translation_map("codex")
_CODEX_MCP_STARTUP_TIMEOUT_SEC = 30


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


def _resolve_codex_skills_dir(target_dir: Path, *, is_global: bool, skills_dir: Path | None = None) -> Path:
    """Resolve the skills directory for an install/uninstall target.

    Global installs use the shared Codex skills directory. Local installs stay
    self-contained under the target config dir unless the caller overrides it.
    """
    if skills_dir is not None:
        return skills_dir
    if is_global:
        return get_codex_skills_dir()
    return target_dir / "skills"


def _load_manifest_codex_skills_dir(target_dir: Path) -> Path | None:
    """Return the install-time Codex skills dir recorded in the local manifest."""
    manifest_path = target_dir / MANIFEST_NAME
    if not manifest_path.exists():
        return None

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    if not isinstance(manifest, dict):
        return None

    manifest_skills_dir = manifest.get(_MANIFEST_CODEX_SKILLS_DIR_KEY)
    if isinstance(manifest_skills_dir, str) and manifest_skills_dir:
        return Path(manifest_skills_dir)

    return None


def _resolve_codex_uninstall_skills_dir(target_dir: Path, *, is_global: bool, skills_dir: Path | None = None) -> Path:
    """Resolve the skills dir to clean during uninstall.

    Prefer the install-time path captured in the manifest so global uninstalls
    still remove the correct shared skills even if env vars drift later.
    """
    if skills_dir is not None:
        return skills_dir

    manifest_skills_dir = _load_manifest_codex_skills_dir(target_dir)
    if manifest_skills_dir is not None:
        return manifest_skills_dir

    return _resolve_codex_skills_dir(target_dir, is_global=is_global)


def _is_global_codex_target(target_dir: Path) -> bool:
    """Return True when *target_dir* is the resolved global Codex config dir."""
    try:
        return target_dir.expanduser().resolve() == get_codex_global_dir().expanduser().resolve()
    except OSError:
        return target_dir.expanduser() == get_codex_global_dir().expanduser()


# ─── Codex-specific content conversion ─────────────────────────────────────


def _convert_codex_tool_name(tool_name: str) -> str | None:
    """Convert a canonical GPD tool name or runtime alias to Codex format.

    Returns ``None`` if the tool should be excluded (for example ``task``,
    which Codex auto-discovers).
    """
    return translate_for_runtime(tool_name, "codex")


def _convert_to_codex_skill(content: str, skill_name: str) -> str:
    """Convert Claude Code markdown command/agent to Codex SKILL.md format.

    Codex skills use SKILL.md with YAML frontmatter:
    - name: must be hyphen-case (a-z0-9-)
    - description: primary triggering mechanism (1-1024 chars)
    - allowed-tools: optional tool restrictions
    - color: removed (not supported by Codex CLI)
    """
    # Replace /gpd: with $gpd- for Codex skill invocation syntax
    converted = content.replace("/gpd:", "$gpd-")

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

    # Deduplicate tools while preserving order
    seen: set[str] = set()
    unique_tools: list[str] = []
    for tool in tools:
        if tool not in seen:
            seen.add(tool)
            unique_tools.append(tool)

    # Add allowed-tools as YAML array
    if unique_tools:
        new_lines.append("allowed-tools:")
        for tool in unique_tools:
            new_lines.append(f"  - {tool}")

    new_frontmatter = "\n".join(new_lines).strip()
    return f"---\n{new_frontmatter}\n---{body}"


def _toml_string(value: str) -> str:
    """Serialize a Python string as a TOML basic string."""
    return json.dumps(value, ensure_ascii=False)


def _toml_value(value: object) -> str:
    """Serialize a scalar Python value as TOML."""
    if isinstance(value, str):
        return _toml_string(value)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    raise TypeError(f"Unsupported TOML scalar value: {value!r}")


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
    def activation_env_vars(self) -> tuple[str, ...]:
        return ("CODEX_SESSION", "CODEX_CLI")

    def resolve_global_config_dir(self, *, home: Path | None = None) -> Path:
        env = os.environ.get("CODEX_CONFIG_DIR")
        if env:
            return Path(env).expanduser()
        return (home or Path.home()) / ".codex"

    def format_command(self, action: str) -> str:
        return f"$gpd-{action}"

    def install(
        self,
        gpd_root: Path,
        target_dir: Path,
        *,
        # is_global defaults to True here (base class defaults to False) because
        # Codex CLI typically installs globally to ~/.codex + ~/.agents/skills/.
        is_global: bool = True,
        skills_dir: Path | None = None,
        explicit_target: bool = False,
    ) -> dict[str, object]:
        """Full GPD installation into a Codex CLI configuration directory.

        Stores *skills_dir* for use by template method hooks, then delegates
        to the base class template method.
        """
        prev_skills_dir = getattr(self, "_skills_dir", None)
        self._skills_dir = _resolve_codex_skills_dir(target_dir, is_global=is_global, skills_dir=skills_dir)
        try:
            return super().install(gpd_root, target_dir, is_global=is_global, explicit_target=explicit_target)
        finally:
            self._skills_dir = prev_skills_dir

    # --- Template method hooks ---

    def _compute_path_prefix(self, target_dir: Path, is_global: bool) -> str:
        if is_global or getattr(self, "_install_explicit_target", False):
            return str(target_dir).replace("\\", "/") + "/"
        return f"./{self.config_dir_name}/"

    def _pre_cleanup(self, target_dir: Path) -> None:
        pre_install_cleanup(target_dir, codex_skills_dir=str(self._skills_dir))

    def _install_commands(self, gpd_root: Path, target_dir: Path, path_prefix: str, failures: list[str]) -> int:
        commands_src = gpd_root / "commands"
        self._skills_dir.mkdir(parents=True, exist_ok=True)
        _copy_commands_as_skills(
            commands_src,
            self._skills_dir,
            "gpd",
            path_prefix,
            gpd_root / "specs",
            self._current_install_scope_flag(),
        )
        if verify_installed(self._skills_dir, "command skills"):
            logger.info("Installed command skills")
        else:
            failures.append("command skills")
        skill_count = sum(1 for d in self._skills_dir.iterdir() if d.is_dir() and d.name.startswith("gpd-"))
        return skill_count

    def _install_agents(self, gpd_root: Path, target_dir: Path, path_prefix: str, failures: list[str]) -> int:
        agents_src = gpd_root / "agents"
        gpd_dest = target_dir / "get-physics-done"
        agent_count = 0

        # Install agents as Codex skill directories
        if agents_src.is_dir():
            _copy_agents_as_skills(
                agents_src,
                self._skills_dir,
                path_prefix,
                gpd_dest,
                self._current_install_scope_flag(),
            )
            agent_count = sum(
                1 for f in agents_src.iterdir() if f.is_file() and f.name.startswith("gpd-") and f.suffix == ".md"
            )
            logger.info("Installed %d agent skills", agent_count)

        # Also install agents as agent .md files
        if agents_src.is_dir():
            agents_dest = target_dir / "agents"
            _copy_agents_as_agent_files(
                agents_src,
                agents_dest,
                path_prefix,
                gpd_dest,
                self._current_install_scope_flag(),
            )
            if verify_installed(agents_dest, "agents"):
                logger.info("Installed agents")
            else:
                failures.append("agents")

        return agent_count

    def _configure_runtime(self, target_dir: Path, is_global: bool) -> dict[str, object]:
        _configure_config_toml(
            target_dir,
            is_global,
            explicit_target=getattr(self, "_install_explicit_target", False),
        )

        # Wire MCP servers into config.toml.
        from gpd.mcp.builtin_servers import build_mcp_servers_dict

        mcp_servers = build_mcp_servers_dict(python_path=sys.executable)
        mcp_count = 0
        if mcp_servers:
            mcp_count = _write_mcp_servers_codex_toml(target_dir, mcp_servers)

        return {
            "target": str(target_dir),
            "skills_dir": str(self._skills_dir),
            "skills": sum(1 for d in self._skills_dir.iterdir() if d.is_dir() and d.name.startswith("gpd-")),
            "mcpServers": mcp_count,
        }

    def _write_manifest(self, target_dir: Path, version: str) -> None:
        write_manifest(
            target_dir,
            version,
            codex_skills_dir=str(self._skills_dir),
            install_scope=self._current_install_scope_flag(),
        )

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
            skills_dir = _resolve_codex_uninstall_skills_dir(
                target_dir,
                is_global=_is_global_codex_target(target_dir),
            )

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

            # 5. Remove GPD hooks
            hooks_dir = target_dir / "hooks"
            if hooks_dir.exists():
                for hook_path in hooks_dir.iterdir():
                    if not hook_path.is_file():
                        continue
                    if hook_path.name in HOOK_SCRIPTS.values():
                        hook_path.unlink()
                        counts["hooks"] += 1

            # 6. Remove GPD MCP servers from config.toml
            config_toml_mcp = target_dir / "config.toml"
            if config_toml_mcp.exists():
                toml_mcp = config_toml_mcp.read_text(encoding="utf-8")
                cleaned_mcp = _remove_gpd_mcp_toml_sections(toml_mcp)
                if cleaned_mcp != toml_mcp:
                    config_toml_mcp.write_text(cleaned_mcp, encoding="utf-8")
                    removed.append("config.toml MCP servers")

            # 7. Clean up config.toml
            config_toml = target_dir / "config.toml"
            if config_toml.exists():
                toml_content = config_toml.read_text(encoding="utf-8")
                cleaned = _remove_gpd_notify_config(toml_content)
                cleaned = _remove_gpd_multi_agent_config(cleaned)
                if cleaned != toml_content:
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
    gpd_src_root: Path | None = None,
    install_scope: str | None = None,
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
            _copy_commands_as_skills(
                entry,
                skills_dir,
                f"{prefix}-{entry.name}",
                path_prefix,
                gpd_src_root,
                install_scope,
            )
        elif entry.suffix == ".md":
            base_name = entry.stem
            skill_name = f"{prefix}-{base_name}"
            skill_dir = skills_dir / skill_name
            skill_dir.mkdir(parents=True, exist_ok=True)

            content = entry.read_text(encoding="utf-8")
            if gpd_src_root:
                content = expand_at_includes(
                    content,
                    str(gpd_src_root),
                    path_prefix,
                    runtime="codex",
                    install_scope=install_scope,
                )
            content = replace_placeholders(content, path_prefix, "codex", install_scope)
            content = _convert_to_codex_skill(content, skill_name)
            content = convert_tool_references_in_body(content, _TOOL_REFERENCE_MAP)

            (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")


def _copy_agents_as_skills(
    src_dir: Path,
    skills_dir: Path,
    path_prefix: str,
    gpd_content_dir: Path | None = None,
    install_scope: str | None = None,
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
        content = replace_placeholders(content, path_prefix, "codex", install_scope)

        # Expand @ includes (Codex doesn't support @ file inclusion)
        if gpd_content_dir:
            content = expand_at_includes(
                content,
                str(gpd_content_dir),
                path_prefix,
                runtime="codex",
                install_scope=install_scope,
            )

        content = _convert_to_codex_skill(content, skill_name)
        content = convert_tool_references_in_body(content, _TOOL_REFERENCE_MAP)

        (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")


def _copy_agents_as_agent_files(
    agents_src: Path,
    agents_dest: Path,
    path_prefix: str,
    gpd_content_dir: Path | None = None,
    install_scope: str | None = None,
) -> None:
    """Copy agents as runtime agent markdown files for Codex.

    Applies placeholder expansion, @-include expansion, and tool reference translation.
    """
    if not agents_src.exists():
        return
    agents_dest.mkdir(parents=True, exist_ok=True)

    new_agent_names: set[str] = set()

    for entry in sorted(agents_src.iterdir()):
        if not entry.is_file() or entry.suffix != ".md":
            continue

        content = entry.read_text(encoding="utf-8")
        content = replace_placeholders(content, path_prefix, "codex", install_scope)

        # Expand @ includes for Codex
        if gpd_content_dir:
            content = expand_at_includes(
                content,
                str(gpd_content_dir),
                path_prefix,
                runtime="codex",
                install_scope=install_scope,
            )

        content = convert_tool_references_in_body(content, _TOOL_REFERENCE_MAP)

        (agents_dest / entry.name).write_text(content, encoding="utf-8")
        new_agent_names.add(entry.name)

    remove_stale_agents(agents_dest, new_agent_names)


_TOML_ASSIGNMENT_RE = re.compile(r"^([A-Za-z0-9_-]+)\s*=")


def _toml_assignment_key(line: str) -> str | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None
    match = _TOML_ASSIGNMENT_RE.match(stripped)
    return match.group(1) if match else None


def _split_preserved_toml_lines(
    existing_lines: list[str] | None,
    *,
    managed_keys: set[str],
) -> tuple[list[str], dict[str, str]]:
    preserved_lines: list[str] = []
    preserved_assignments: dict[str, str] = {}

    if existing_lines is None:
        return preserved_lines, preserved_assignments

    for line in existing_lines:
        key = _toml_assignment_key(line)
        if key is not None and key in managed_keys:
            preserved_assignments[key] = line.strip()
            continue
        preserved_lines.append(line)

    while preserved_lines and preserved_lines[0] == "":
        preserved_lines.pop(0)
    while preserved_lines and preserved_lines[-1] == "":
        preserved_lines.pop()

    return preserved_lines, preserved_assignments


def _build_codex_mcp_server_section_lines(
    name: str,
    entry: dict[str, object],
    *,
    existing_base_body: list[str] | None,
    existing_env_body: list[str] | None,
) -> list[str]:
    base_section_name = f"mcp_servers.{name}"
    managed_entry = dict(entry)
    managed_entry.setdefault("startup_timeout_sec", _CODEX_MCP_STARTUP_TIMEOUT_SEC)

    lines = [f"\n[{base_section_name}]"]
    cmd = str(managed_entry.get("command", ""))
    args = managed_entry.get("args", [])
    args_list = list(args) if isinstance(args, list) else []
    lines.append(f"command = {_toml_string(cmd)}")
    args_toml = ", ".join(_toml_string(str(arg)) for arg in args_list)
    lines.append(f"args = [{args_toml}]")

    extra_keys = sorted(key for key in managed_entry if key not in {"command", "args", "env"})
    preserved_base_lines, preserved_base_assignments = _split_preserved_toml_lines(
        existing_base_body,
        managed_keys={"command", "args", *extra_keys},
    )
    for key in extra_keys:
        existing_line = preserved_base_assignments.get(key)
        if existing_line is not None:
            lines.append(existing_line)
            continue
        lines.append(f"{key} = {_toml_value(managed_entry[key])}")
    lines.extend(preserved_base_lines)

    raw_env = managed_entry.get("env", {})
    managed_env = dict(raw_env) if isinstance(raw_env, dict) else {}
    preserved_env_lines, preserved_env_assignments = _split_preserved_toml_lines(
        existing_env_body,
        managed_keys=set(managed_env),
    )

    env_lines: list[str] = []
    for key, value in managed_env.items():
        existing_line = preserved_env_assignments.get(key)
        if existing_line is not None:
            env_lines.append(existing_line)
            continue
        env_lines.append(f"{key} = {_toml_string(str(value))}")
    env_lines.extend(preserved_env_lines)

    if env_lines:
        lines.append(f"\n[{base_section_name}.env]")
        lines.extend(env_lines)

    return lines


def _write_mcp_servers_codex_toml(target_dir: Path, servers: dict[str, dict[str, object]]) -> int:
    """Append MCP server entries to Codex config.toml without clobbering user overrides."""
    config_toml = target_dir / "config.toml"
    target_dir.mkdir(parents=True, exist_ok=True)

    content = ""
    if config_toml.exists():
        content = config_toml.read_text(encoding="utf-8")
    existing_content = content

    # Remove existing GPD MCP sections before rewriting.
    content = _remove_gpd_mcp_toml_sections(content)

    # Append new MCP server sections.
    lines: list[str] = []
    if content and not content.endswith("\n"):
        content += "\n"
    lines.append("# GPD MCP servers")
    for name, entry in sorted(servers.items()):
        _, existing_base_body, _ = _split_toml_section(existing_content, f"mcp_servers.{name}")
        _, existing_env_body, _ = _split_toml_section(existing_content, f"mcp_servers.{name}.env")
        lines.extend(
            _build_codex_mcp_server_section_lines(
                name,
                entry,
                existing_base_body=existing_base_body,
                existing_env_body=existing_env_body,
            )
        )

    content += "\n".join(lines) + "\n"
    config_toml.write_text(content, encoding="utf-8")
    return len(servers)


def _remove_gpd_mcp_toml_sections(content: str) -> str:
    """Remove GPD MCP server sections from TOML content."""
    from gpd.mcp.builtin_servers import GPD_MCP_SERVER_KEYS

    # Remove the header comment and all [mcp_servers.gpd-*] sections.
    content = re.sub(r"^# GPD MCP servers\n", "", content, flags=re.MULTILINE)
    for key in GPD_MCP_SERVER_KEYS:
        escaped = re.escape(key)
        # Remove [mcp_servers.key] and [mcp_servers.key.env] sections until the next section.
        content = re.sub(
            rf"^\[mcp_servers\.{escaped}(?:\.env)?\]\n(?:(?!\[)[^\n]*\n)*",
            "",
            content,
            flags=re.MULTILINE,
        )
    # Clean up excessive blank lines.
    content = re.sub(r"\n{3,}", "\n\n", content)
    return content


def _parse_section_name(line: str) -> str | None:
    stripped = line.strip()
    if not stripped.startswith("[") or not stripped.endswith("]") or stripped.startswith("[["):
        return None
    return stripped[1:-1].strip()


def _split_toml_section(toml_content: str, section_name: str) -> tuple[list[str], list[str] | None, list[str]]:
    lines = toml_content.splitlines()
    start: int | None = None

    for idx, line in enumerate(lines):
        if _parse_section_name(line) == section_name:
            start = idx
            break

    if start is None:
        return lines, None, []

    end = len(lines)
    for idx in range(start + 1, len(lines)):
        if _parse_section_name(lines[idx]) is not None:
            end = idx
            break

    return lines[:start], lines[start + 1 : end], lines[end:]


def _parse_feature_bool_assignment(line: str, key: str) -> bool | None:
    stripped = line.strip()
    if not (stripped.startswith(f"{key} ") or stripped.startswith(f"{key}=")):
        return None
    try:
        parsed = tomllib.loads(f"[features]\n{stripped}\n")
    except tomllib.TOMLDecodeError:
        return None
    features = parsed.get("features")
    if not isinstance(features, dict):
        return None
    value = features.get(key)
    return value if isinstance(value, bool) else None


def _build_multi_agent_block(
    existing_line: str | None,
    *,
    had_managed_block: bool,
    backup_line: str | None,
) -> list[str]:
    desired_line = "multi_agent = true"

    if had_managed_block:
        block = [_GPD_MULTI_AGENT_COMMENT]
        if backup_line is not None:
            block.append(_GPD_MULTI_AGENT_BACKUP_PREFIX + backup_line)
        block.append(desired_line)
        return block

    if existing_line is None:
        return [_GPD_MULTI_AGENT_COMMENT, desired_line]

    if _parse_feature_bool_assignment(existing_line, "multi_agent") is True:
        return [existing_line]

    return [
        _GPD_MULTI_AGENT_COMMENT,
        _GPD_MULTI_AGENT_BACKUP_PREFIX + existing_line,
        desired_line,
    ]


def _install_gpd_multi_agent_config(toml_content: str) -> str:
    before, body, after = _split_toml_section(toml_content, "features")
    desired_line = "multi_agent = true"

    if body is None:
        lines = before[:]
        if lines and lines[-1] != "":
            lines.append("")
        lines.extend(["[features]", _GPD_MULTI_AGENT_COMMENT, desired_line])
        return _serialize_toml_lines(lines)

    cleaned: list[str] = []
    existing_line: str | None = None
    backup_line: str | None = None
    had_managed_block = False
    pending_managed_block = False
    insert_at: int | None = None

    for line in body:
        stripped = line.strip()
        if stripped == _GPD_MULTI_AGENT_COMMENT:
            had_managed_block = True
            pending_managed_block = True
            if insert_at is None:
                insert_at = len(cleaned)
            continue
        if stripped.startswith(_GPD_MULTI_AGENT_BACKUP_PREFIX):
            had_managed_block = True
            pending_managed_block = True
            backup_line = stripped[len(_GPD_MULTI_AGENT_BACKUP_PREFIX) :].strip()
            if insert_at is None:
                insert_at = len(cleaned)
            continue
        if _parse_feature_bool_assignment(line, "multi_agent") is not None:
            if pending_managed_block:
                had_managed_block = True
                pending_managed_block = False
                if insert_at is None:
                    insert_at = len(cleaned)
                continue
            existing_line = stripped
            if insert_at is None:
                insert_at = len(cleaned)
            continue
        pending_managed_block = False
        cleaned.append(line)

    if insert_at is None:
        insert_at = len(cleaned)
    cleaned[insert_at:insert_at] = _build_multi_agent_block(
        existing_line,
        had_managed_block=had_managed_block,
        backup_line=backup_line,
    )
    return _serialize_toml_lines(before + ["[features]"] + cleaned + after)


def _remove_gpd_multi_agent_config(toml_content: str) -> str:
    before, body, after = _split_toml_section(toml_content, "features")
    if body is None:
        return toml_content

    cleaned: list[str] = []
    original_line: str | None = None
    insert_at: int | None = None
    had_managed_block = False
    pending_managed_block = False

    for line in body:
        stripped = line.strip()
        if stripped == _GPD_MULTI_AGENT_COMMENT:
            had_managed_block = True
            pending_managed_block = True
            if insert_at is None:
                insert_at = len(cleaned)
            continue
        if stripped.startswith(_GPD_MULTI_AGENT_BACKUP_PREFIX):
            had_managed_block = True
            pending_managed_block = True
            original_line = stripped[len(_GPD_MULTI_AGENT_BACKUP_PREFIX) :].strip()
            if insert_at is None:
                insert_at = len(cleaned)
            continue
        if _parse_feature_bool_assignment(line, "multi_agent") is not None and pending_managed_block:
            had_managed_block = True
            pending_managed_block = False
            if insert_at is None:
                insert_at = len(cleaned)
            continue
        pending_managed_block = False
        cleaned.append(line)

    if not had_managed_block:
        return toml_content

    if original_line is not None:
        position = insert_at if insert_at is not None else len(cleaned)
        cleaned[position:position] = [original_line]

    lines = before[:]
    if any(line.strip() for line in cleaned):
        lines.extend(["[features]", *cleaned])
    lines.extend(after)
    return re.sub(r"\n{3,}", "\n\n", _serialize_toml_lines(lines))


def _configure_config_toml(
    target_dir: Path,
    is_global: bool,
    *,
    explicit_target: bool = False,
) -> None:
    """Configure GPD runtime settings in Codex config.toml."""
    config_toml = target_dir / "config.toml"
    toml_content = ""
    if config_toml.exists():
        toml_content = config_toml.read_text(encoding="utf-8")

    notify_hook = HOOK_SCRIPTS["codex_notify"]

    if is_global or explicit_target:
        desired_path = str(target_dir / "hooks" / notify_hook).replace("\\", "/")
    else:
        desired_path = f".codex/hooks/{notify_hook}"
    configured = _install_gpd_notify_config(
        toml_content,
        desired_path=desired_path,
    )
    config_toml.write_text(
        _install_gpd_multi_agent_config(configured),
        encoding="utf-8",
    )


def _line_contains_gpd_notify(line: str) -> bool:
    return "codex_notify.py" in line


def _parse_notify_assignment(line: str) -> list[str] | None:
    stripped = line.strip()
    if not stripped.startswith("notify"):
        return None
    try:
        parsed = tomllib.loads(stripped + "\n")
    except tomllib.TOMLDecodeError:
        return None
    value = parsed.get("notify")
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return list(value)
    return None


def _build_notify_line(desired_path: str) -> str:
    return f"notify = [{_toml_string(hook_python_interpreter())}, {_toml_string(desired_path)}]"


def _build_notify_wrapper_line(existing_notify: list[str], desired_path: str) -> str:
    existing_cmd = " ".join(shlex.quote(arg) for arg in existing_notify)
    gpd_cmd = f"{shlex.quote(hook_python_interpreter())} {shlex.quote(desired_path)}"
    shell_script = (
        'tmp="$(mktemp "${TMPDIR:-/tmp}/gpd-codex-notify.XXXXXX")" || exit 0; '
        'cat > "$tmp"; '
        f"{existing_cmd} < \"$tmp\" || true; "
        f"{gpd_cmd} < \"$tmp\" || true; "
        'rm -f "$tmp"'
    )
    return f'notify = ["sh", "-c", {json.dumps(shell_script)}]'


def _serialize_toml_lines(lines: list[str]) -> str:
    content = "\n".join(lines).rstrip()
    return f"{content}\n" if content else ""


def _first_section_index(lines: list[str]) -> int:
    """Return the index of the first TOML section header, or len(lines) if none."""
    for idx, line in enumerate(lines):
        if _parse_section_name(line) is not None:
            return idx
    return len(lines)


def _install_gpd_notify_config(
    toml_content: str,
    *,
    desired_path: str,
) -> str:
    desired_line = _build_notify_line(desired_path)
    cleaned_lines: list[str] = []
    insert_at: int | None = None
    existing_notify: list[str] | None = None

    for line in toml_content.splitlines():
        stripped = line.strip()
        if stripped == _GPD_NOTIFY_COMMENT or stripped.startswith(_GPD_NOTIFY_BACKUP_PREFIX):
            if insert_at is None:
                insert_at = len(cleaned_lines)
            continue
        # Only match top-level notify (before any section header or at known position)
        if stripped.startswith("notify") and _parse_section_name(stripped) is None:
            if insert_at is None:
                insert_at = len(cleaned_lines)
            if _line_contains_gpd_notify(line):
                continue
            parsed = _parse_notify_assignment(line)
            if parsed is not None:
                existing_notify = parsed
                continue
        cleaned_lines.append(line)

    notify_block: list[str]
    if existing_notify is not None:
        notify_block = [
            _GPD_NOTIFY_COMMENT,
            _GPD_NOTIFY_BACKUP_PREFIX + json.dumps(existing_notify),
            _build_notify_wrapper_line(existing_notify, desired_path),
        ]
    else:
        notify_block = [_GPD_NOTIFY_COMMENT, desired_line]

    if insert_at is not None:
        # Ensure insert position is at root level (before first section header)
        first_section = _first_section_index(cleaned_lines)
        if insert_at > first_section:
            insert_at = first_section
        cleaned_lines[insert_at:insert_at] = notify_block
    else:
        # No existing notify — insert before first section header to stay at root level
        first_section = _first_section_index(cleaned_lines)
        if first_section > 0 and cleaned_lines[first_section - 1].strip() != "":
            notify_block = [""] + notify_block
        cleaned_lines[first_section:first_section] = notify_block + [""]

    return _serialize_toml_lines(cleaned_lines)


def _remove_gpd_notify_config(toml_content: str) -> str:
    cleaned_lines: list[str] = []
    insert_at: int | None = None
    original_notify: str | None = None

    for line in toml_content.splitlines():
        stripped = line.strip()
        if stripped == _GPD_NOTIFY_COMMENT:
            if insert_at is None:
                insert_at = len(cleaned_lines)
            continue
        if stripped.startswith(_GPD_NOTIFY_BACKUP_PREFIX):
            if insert_at is None:
                insert_at = len(cleaned_lines)
            original_notify = stripped[len(_GPD_NOTIFY_BACKUP_PREFIX) :].strip()
            continue
        if stripped.startswith("notify") and _line_contains_gpd_notify(line):
            if insert_at is None:
                insert_at = len(cleaned_lines)
            continue
        cleaned_lines.append(line)

    if original_notify:
        restore_line = f"notify = {original_notify}"
        position = insert_at if insert_at is not None else len(cleaned_lines)
        cleaned_lines[position:position] = [restore_line]

    return _serialize_toml_lines(cleaned_lines)


__all__ = [
    "CodexAdapter",
    "get_codex_global_dir",
    "get_codex_skills_dir",
]
