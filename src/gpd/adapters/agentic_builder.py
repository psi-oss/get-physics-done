"""Agentic Builder runtime adapter — the definitive Python API for PSI agentic-builder.

Provides system prompts, tool lists, action specs, MCP configs, and convention
lock extraction for direct Python consumption by the MCTS solver.

Content discovery delegates to ``gpd.registry`` (parse-once, cache, typed dataclasses).
This module adds placeholder resolution, tool-name translation, and the adapter class.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from gpd.adapters.base import RuntimeAdapter
from gpd.adapters.tool_names import AGENTIC_BUILDER, canonical, translate_list
from gpd.registry import get_agent as _reg_get_agent
from gpd.registry import get_command as _reg_get_command
from gpd.registry import list_agents as _reg_list_agents
from gpd.registry import list_commands as _reg_list_commands

# ─── Package-level directories ────────────────────────────────────────────────

_PKG_ROOT = Path(__file__).resolve().parent.parent  # gpd/
_INFRA_DIR = _PKG_ROOT.parent.parent / "infra"  # packages/gpd/infra/

# Placeholder regex: {name} but not inside backticks
_PLACEHOLDER_RE = re.compile(r"\{(\w+)\}")


# ─── Placeholder resolution ──────────────────────────────────────────────────


def _resolve_placeholders(text: str, context: dict[str, str]) -> str:
    """Resolve {placeholder} patterns in text using context dict.

    Unresolved placeholders are left as-is.
    """

    def _replacer(m: re.Match) -> str:
        key = m.group(1)
        return context.get(key, m.group(0))

    return _PLACEHOLDER_RE.sub(_replacer, text)


# ─── Public API Functions (delegate to registry) ─────────────────────────────


def list_available_agents() -> list[str]:
    """Return sorted list of all GPD agent names."""
    return _reg_list_agents()


def list_available_commands() -> list[str]:
    """Return sorted list of all GPD command names."""
    return _reg_list_commands()


def get_agent_prompt(
    name: str,
    *,
    placeholder_context: dict[str, str] | None = None,
) -> str:
    """Return the full system prompt text for an agent, with placeholders resolved.

    Raises KeyError if the agent doesn't exist.
    """
    agent = _reg_get_agent(name)
    prompt = agent.system_prompt
    if placeholder_context:
        prompt = _resolve_placeholders(prompt, placeholder_context)
    return prompt


def get_agent_spec(
    name: str,
    *,
    placeholder_context: dict[str, str] | None = None,
) -> dict[str, object]:
    """Return full structured agent definition with placeholders resolved.

    Returns dict with: name, description, system_prompt, tools, tools_translated,
    color, path.
    """
    agent = _reg_get_agent(name)
    prompt = agent.system_prompt
    if placeholder_context:
        prompt = _resolve_placeholders(prompt, placeholder_context)

    spec: dict[str, object] = {
        "name": agent.name,
        "description": agent.description,
        "system_prompt": prompt,
        "tools": list(agent.tools),
        "color": agent.color,
        "path": agent.path,
    }

    # Add translated tool names for agentic-builder runtime
    spec["tools_translated"] = translate_list([canonical(t) for t in agent.tools], "agentic-builder")
    return spec


def get_command_spec(
    name: str,
    *,
    placeholder_context: dict[str, str] | None = None,
) -> dict[str, object]:
    """Return structured command definition with placeholders resolved.

    Returns dict with: name, description, argument_hint, requires,
    allowed_tools, allowed_tools_translated, content, path.
    """
    cmd = _reg_get_command(name)
    content = cmd.content
    if placeholder_context:
        content = _resolve_placeholders(content, placeholder_context)

    spec: dict[str, object] = {
        "name": cmd.name,
        "description": cmd.description,
        "argument_hint": cmd.argument_hint,
        "requires": dict(cmd.requires),
        "allowed_tools": list(cmd.allowed_tools),
        "content": content,
        "path": cmd.path,
    }

    # Add translated tool names
    spec["allowed_tools_translated"] = translate_list([canonical(t) for t in cmd.allowed_tools], "agentic-builder")
    return spec


def get_mcp_configs() -> list[dict[str, object]]:
    """Return all MCP tool configurations from infra/*.json."""
    if not _INFRA_DIR.is_dir():
        return []

    configs: list[dict[str, object]] = []
    for json_path in sorted(_INFRA_DIR.glob("*.json")):
        raw = json.loads(json_path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            configs.append(raw)
    return configs


def get_convention_lock_summary(project_dir: Path) -> dict[str, object]:
    """Extract convention lock state from a GPD project directory.

    Returns a dict with set_count, total, conventions (key->value mapping),
    and missing (list of unset canonical keys).
    """
    state_path = project_dir / ".planning" / "state.json"
    if not state_path.is_file():
        return {"set_count": 0, "total": 0, "conventions": {}, "missing": []}

    state_data = json.loads(state_path.read_text(encoding="utf-8"))
    lock_data = state_data.get("convention_lock", {})

    from gpd.contracts import ConventionLock
    from gpd.core.conventions import convention_list

    lock = ConventionLock(**{k: v for k, v in lock_data.items() if k in ConventionLock.model_fields})
    result = convention_list(lock)

    set_conventions = {entry.key: entry.value for entry in result.conventions.values() if entry.is_set}
    missing_keys = [entry.key for entry in result.conventions.values() if not entry.is_set and entry.canonical]

    return {
        "set_count": result.set_count,
        "total": result.total,
        "conventions": set_conventions,
        "missing": missing_keys,
    }


def build_placeholder_context(
    gpd_install_dir: Path | None = None,
    convention_context: str = "",
    role_identity: str = "",
    extra: dict[str, str] | None = None,
) -> dict[str, str]:
    """Build a standard placeholder context dict for prompt resolution.

    Standard placeholders:
    - GPD_INSTALL_DIR: path to GPD package installation
    - convention_context: serialized convention lock state
    - role_identity: agent role description
    """
    ctx: dict[str, str] = {}

    if gpd_install_dir is not None:
        ctx["GPD_INSTALL_DIR"] = str(gpd_install_dir)
    else:
        ctx["GPD_INSTALL_DIR"] = str(_PKG_ROOT)

    if convention_context:
        ctx["convention_context"] = convention_context
    if role_identity:
        ctx["role_identity"] = role_identity

    if extra:
        ctx.update(extra)

    return ctx


# ─── Adapter Class ───────────────────────────────────────────────────────────


class AgenticBuilderAdapter(RuntimeAdapter):
    """Adapter for PSI agentic-builder (direct Python consumption)."""

    @property
    def runtime_name(self) -> str:
        return "agentic-builder"

    @property
    def display_name(self) -> str:
        return "Agentic Builder"

    @property
    def config_dir_name(self) -> str:
        return ".psi"

    @property
    def help_command(self) -> str:
        return "gpd help"

    def translate_tool_name(self, canonical_name: str) -> str:
        canon = canonical(canonical_name)
        return AGENTIC_BUILDER.get(canon, canon)

    def generate_command(self, command_def: dict[str, object], target_dir: Path) -> Path:
        """Extract command content as a plain text prompt file."""
        name = str(command_def["name"])
        content = str(command_def.get("content", ""))

        prompts_dir = target_dir / "prompts"
        prompts_dir.mkdir(parents=True, exist_ok=True)
        out_path = prompts_dir / f"{name}.txt"
        out_path.write_text(content, encoding="utf-8")
        return out_path

    def generate_agent(self, agent_def: dict[str, object], target_dir: Path) -> Path:
        """Generate an agent config as a plain text system prompt."""
        name = str(agent_def["name"])
        content = str(agent_def.get("content", ""))

        agents_dir = target_dir / "agents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        out_path = agents_dir / f"{name}.txt"
        out_path.write_text(content, encoding="utf-8")
        return out_path

    def generate_hook(self, hook_name: str, hook_config: dict[str, object]) -> dict[str, object]:
        """Hooks are not applicable to agentic-builder — return empty config."""
        return {}

    def install(self, gpd_root: Path, target_dir: Path, *, is_global: bool = False) -> dict[str, object]:
        """Install GPD specs as structured prompts + configs for agentic-builder.

        Writes to target_dir (.psi/):
        - agents/<name>.txt — system prompts with placeholders resolved
        - prompts/<name>.txt — command/skill content
        - mcp/<name>.json — MCP tool configurations
        """
        import logging

        from gpd.core.observability import gpd_span

        logger = logging.getLogger(__name__)

        with gpd_span("adapter.install", runtime=self.runtime_name, target=str(target_dir)) as span:
            ctx = build_placeholder_context(gpd_install_dir=gpd_root)
            counts: dict[str, int] = {"agents": 0, "commands": 0, "mcp_configs": 0}

            # 1. Install all agents (registry merges agents/ + specs/agents/)
            for agent_name in list_available_agents():
                spec = get_agent_spec(agent_name, placeholder_context=ctx)
                self.generate_agent(
                    {"name": agent_name, "content": spec["system_prompt"]},
                    target_dir,
                )
                counts["agents"] += 1

            # 2. Install all commands (registry merges commands/ + specs/skills/)
            for cmd_name in list_available_commands():
                spec = get_command_spec(cmd_name, placeholder_context=ctx)
                self.generate_command(
                    {"name": cmd_name, "content": spec["content"]},
                    target_dir,
                )
                counts["commands"] += 1

            # 3. Install MCP tool configs → mcp/
            mcp_configs = get_mcp_configs()
            if mcp_configs:
                mcp_dir = target_dir / "mcp"
                mcp_dir.mkdir(parents=True, exist_ok=True)
                for config in mcp_configs:
                    name = str(config.get("name", "unknown"))
                    out_path = mcp_dir / f"{name}.json"
                    out_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
                    counts["mcp_configs"] += 1

            span.set_attribute("gpd.commands_count", counts["commands"])
            span.set_attribute("gpd.agents_count", counts["agents"])
            logger.info(
                "Installed GPD for %s: %d agents, %d commands, %d MCP configs",
                self.runtime_name,
                counts["agents"],
                counts["commands"],
                counts["mcp_configs"],
            )

            return {"runtime": self.runtime_name, "target": str(target_dir), **counts}

    def uninstall(self, target_dir: Path) -> dict[str, object]:
        """Remove GPD from an agentic-builder .psi/ directory.

        Agentic-builder uses prompts/*.txt, agents/*.txt, and mcp/*.json
        instead of the base class's commands/gpd/ and agents/*.md layout.
        """
        import logging
        import shutil

        from gpd.core.observability import gpd_span

        logger = logging.getLogger(__name__)

        with gpd_span("adapter.uninstall", runtime=self.runtime_name, target=str(target_dir)) as span:
            removed: list[str] = []

            # Remove prompts/ directory (command content)
            prompts_dir = target_dir / "prompts"
            if prompts_dir.is_dir():
                shutil.rmtree(prompts_dir)
                removed.append("prompts/")

            # Remove agents/ directory (.txt system prompts)
            agents_dir = target_dir / "agents"
            if agents_dir.is_dir():
                shutil.rmtree(agents_dir)
                removed.append("agents/")

            # Remove mcp/ directory (MCP tool configs)
            mcp_dir = target_dir / "mcp"
            if mcp_dir.is_dir():
                shutil.rmtree(mcp_dir)
                removed.append("mcp/")

            # Remove conventions.json if present
            conventions = target_dir / "conventions.json"
            if conventions.exists():
                conventions.unlink()
                removed.append("conventions.json")

            span.set_attribute("gpd.removed_count", len(removed))
            logger.info("Uninstalled GPD from %s: removed %d items", self.runtime_name, len(removed))

            return {"runtime": self.runtime_name, "target": str(target_dir), "removed": removed}


__all__ = [
    "AgenticBuilderAdapter",
    "build_placeholder_context",
    "get_agent_prompt",
    "get_agent_spec",
    "get_command_spec",
    "get_convention_lock_summary",
    "get_mcp_configs",
    "list_available_agents",
    "list_available_commands",
]
