"""Hermes Agent runtime adapter.

Hermes Agent (Nous Research) is an OpenAI-compatible agent runtime with a
native MCP client and a skill system. GPD keeps the same split Codex uses:

- Commands become SKILL.md files under the Hermes skills directory
  (``%LOCALAPPDATA%\\Hermes\\skills\\`` on Windows; ``$HERMES_HOME/skills``
  otherwise) for local installs, and the shared user-level skills directory
  for global installs.
- Agents install as Hermes skills too (Hermes has no separate agent-role
  surface; skill files carry role instructions plus ``metadata.hermes``
  tool requirements).
- MCP servers are registered in Hermes ``config.yaml`` under
  ``mcp_servers:`` (the native MCP client surface).

Config directory: HERMES_HOME env var > %LOCALAPPDATA%\\Hermes
Skills directory: HERMES_SKILLS_DIR env var > <config>/skills

Hermes exposes the canonical GPD tool names directly (read_file, shell,
write_file, web_search, web_fetch, search_files, find_files, tool_search),
so the tool name map is intentionally small — only legacy/alias tokens
are remapped.
"""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path

from gpd.adapters.base import RuntimeAdapter
from gpd.adapters.install_utils import (
    verify_installed,
)

logger = logging.getLogger(__name__)

_TOOL_NAME_MAP: dict[str, str] = {
    # Canonical GPD names are already Hermes tool names; this map only
    # remaps legacy/alias tokens that GPD uses in shared markdown.
    "file_read": "read_file",
    "file_write": "write_file",
    "file_edit": "apply_patch",
    "shell": "shell",
    "search_files": "search_files",
    "find_files": "find_files",
    "web_search": "web_search",
    "web_fetch": "web_fetch",
    "todo_write": "todo_list",
    "tool_search": "tool_search",
    "task": "delegate_task",
}

# Hermes surfaces ``tool_search`` etc. as first-class; nothing is
# auto-discovered at runtime (the MCP servers are static in config.yaml).
_AUTO_DISCOVERED_TOOLS = frozenset()

_GPD_MARKER = "<!-- Managed by Get Physics Done (GPD). -->"
_MANIFEST_HERMES_SKILLS_DIR_KEY = "hermes_skills_dir"


def _hermes_global_config_dir() -> Path:
    """Resolve the Hermes global config directory.

    Precedence: HERMES_HOME -> %LOCALAPPDATA%\\Hermes (Windows) ->
    ~/.hermes (POSIX).
    """
    env_home = os.environ.get("HERMES_HOME")
    if env_home:
        return Path(env_home).expanduser().resolve()
    if os.name == "nt":
        local = os.environ.get("LOCALAPPDATA")
        if local:
            return Path(local) / "Hermes"
    return Path.home() / ".hermes"


def _skill_dir_name(command_stem: str, prefix: str = "gpd") -> str:
    """Map a GPD command stem to a Hermes skill directory name.

    Example: command ``plan-phase.md`` -> skill dir ``gpd-plan-phase``.
    Nested paths (``sub/name.md``) keep their hierarchy: ``gpd-sub-name``.
    """
    parts = Path(command_stem).with_suffix("").parts
    flattened = "-".join(part for part in parts if part)
    if not flattened:
        flattened = "help"
    return f"{prefix}-{flattened}" if not flattened.startswith(prefix) else flattened


def _inject_marker_after_frontmatter(content: str) -> str:
    """Insert the GPD ownership marker after the YAML frontmatter.

    Codex does the same (marker lives between frontmatter and body) so the
    runtime YAML parser sees the frontmatter first.
    """
    if _GPD_MARKER in content:
        return content
    try:
        from gpd.adapters.install_utils import (
            render_markdown_frontmatter,
            split_markdown_frontmatter,
        )
    except Exception:  # pragma: no cover - defensive
        return f"{_GPD_MARKER}\n{content}"
    preamble, frontmatter, separator, body = split_markdown_frontmatter(content)
    if not frontmatter:
        return f"{_GPD_MARKER}\n{content}"
    return render_markdown_frontmatter(preamble, frontmatter, separator, f"{_GPD_MARKER}\n{body}")


def _copy_commands_as_skills(
    src_dir: Path,
    skills_dir: Path,
    prefix: str,
    path_prefix: str,
) -> set[str]:
    """Copy GPD command markdown into Hermes skill directories.

    Hermes expects: skills/gpd-plan-phase/SKILL.md
    Source structure: commands/plan-phase.md -> gpd-plan-phase/SKILL.md
    """
    if not src_dir.exists():
        return set()
    skills_dir.mkdir(parents=True, exist_ok=True)
    generated: set[str] = set()
    for cmd in sorted(src_dir.rglob("*.md")):
        rel = cmd.relative_to(src_dir)
        skill_name = _skill_dir_name(str(rel), prefix)
        dest = skills_dir / skill_name / "SKILL.md"
        dest.parent.mkdir(parents=True, exist_ok=True)
        content = cmd.read_text(encoding="utf-8")
        dest.write_text(_inject_marker_after_frontmatter(content), encoding="utf-8")
        generated.add(skill_name)
    return generated


def _copy_agents_as_skills(
    agents_src: Path,
    skills_dir: Path,
    prefix: str,
    path_prefix: str,
) -> set[str]:
    """Copy GPD agent role markdown into Hermes skill directories.

    Hermes has no separate agent-role surface: role briefs install as
    skills named ``gpd-agent-<name>``.
    """
    if not agents_src.exists():
        return set()
    skills_dir.mkdir(parents=True, exist_ok=True)
    generated: set[str] = set()
    for agent in sorted(agents_src.rglob("*.md")):
        skill_name = f"{prefix}-agent-{agent.stem.removeprefix('gpd-')}"
        dest = skills_dir / skill_name / "SKILL.md"
        dest.parent.mkdir(parents=True, exist_ok=True)
        content = agent.read_text(encoding="utf-8")
        dest.write_text(_inject_marker_after_frontmatter(content), encoding="utf-8")
        generated.add(skill_name)
    return generated


class HermesAdapter(RuntimeAdapter):
    """GPD runtime adapter for Hermes Agent."""

    tool_name_map: dict[str, str] = _TOOL_NAME_MAP
    auto_discovered_tools: frozenset[str] = _AUTO_DISCOVERED_TOOLS
    strip_sub_tags_in_shared_markdown: bool = False

    def __init__(self) -> None:
        super().__init__()
        self._skills_dir: Path | None = None
        self._generated_skill_dirs: set[str] = set()
        self._install_explicit_target = False

    @property
    def runtime_name(self) -> str:
        return "hermes"

    @property
    def global_config_dir(self) -> Path:
        """Hermes global config directory (HERMES_HOME)."""
        return _hermes_global_config_dir()

    @property
    def skills_dir(self) -> Path:
        """Hermes skills directory (where GPD skills get installed)."""
        env_skills = os.environ.get("HERMES_SKILLS_DIR")
        if env_skills:
            return Path(env_skills).expanduser().resolve()
        return self.global_config_dir / "skills"

    @property
    def config_file(self) -> Path:
        """Hermes config.yaml (where MCP servers get registered)."""
        return self.global_config_dir / "config.yaml"

    def local_skills_dir(self, target_dir: Path) -> Path:
        """Workspace-local skills dir (project-scoped installs).

        ``target_dir`` is already the resolved Hermes config dir
        (``<project>/.hermes`` for local installs), so skills live
        directly under it.
        """
        return target_dir / "skills"

    # -- Install surface hooks ---------------------------------------------

    def install(
        self,
        gpd_root: Path,
        target_dir: Path,
        *,
        is_global: bool = True,
        explicit_target: bool = False,
    ) -> dict[str, object]:
        """Full GPD installation into a Hermes config directory."""
        self._install_explicit_target = explicit_target
        if is_global:
            self._skills_dir = self.skills_dir
        else:
            self._skills_dir = self.local_skills_dir(target_dir)
        self._generated_skill_dirs = set()
        try:
            return super().install(gpd_root, target_dir, is_global=is_global, explicit_target=explicit_target)
        finally:
            self._skills_dir = None
            self._install_explicit_target = False

    def _compute_path_prefix(self, target_dir: Path, is_global: bool) -> str:
        if is_global or self._install_explicit_target:
            return str(target_dir).replace("\\", "/") + "/"
        return f"./{self.config_dir_name}/"

    def _install_commands(self, gpd_root: Path, target_dir: Path, path_prefix: str, failures: list[str]) -> int:
        commands_src = gpd_root / "commands"
        skills_dir = self._skills_dir
        if skills_dir is None:
            failures.append("command skills (skills_dir unset)")
            return 0
        generated = _copy_commands_as_skills(commands_src, skills_dir, "gpd", path_prefix)
        self._generated_skill_dirs = set(generated)
        if verify_installed(skills_dir):
            logger.info("Installed GPD command skills for Hermes")
        else:
            failures.append("command skills")
        return len(generated)

    def _install_agents(self, gpd_root: Path, target_dir: Path, path_prefix: str, failures: list[str]) -> int:
        agents_src = gpd_root / "agents"
        skills_dir = self._skills_dir
        if skills_dir is None:
            failures.append("agents (skills_dir unset)")
            return 0
        generated = _copy_agents_as_skills(agents_src, skills_dir, "gpd", path_prefix)
        self._generated_skill_dirs |= set(generated)
        if verify_installed(skills_dir):
            logger.info("Installed GPD agent skills for Hermes")
        else:
            failures.append("agents")
        return len(generated)

    def _preflight_runtime_config(self, target_dir: Path, is_global: bool) -> None:
        """Hermes config.yaml is only needed for MCP server registration;
        a missing file is fine (Hermes creates defaults on first launch)."""
        return None

    def missing_install_artifacts(self, target_dir: Path) -> tuple[str, ...]:
        skills_dir = self._skills_dir
        if skills_dir is None:
            return ("command skills",)
        return () if verify_installed(skills_dir) else ("command skills",)

    # -- Surface helpers ---------------------------------------------------

    def format_command(self, name: str) -> str:
        """Format a runtime-side command reference (gpd:<name>)."""
        return f"gpd:{name}"