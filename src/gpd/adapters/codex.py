"""OpenAI Codex CLI runtime adapter.

Codex CLI separates discoverable skills from runtime configuration. GPD keeps
that split explicit:

- Commands become skill directories under repo-local ``.agents/skills/`` for
  local installs and the shared user-level skills directory for global installs.
- Agents install only as Codex roles under ``.codex/agents/`` plus
  ``config.toml`` registrations.

Config directory: CODEX_CONFIG_DIR env var > ~/.codex
Global skills directory: CODEX_SKILLS_DIR env var > ~/.agents/skills/

Hooks, feature flags, and agent role registrations go into config.toml
(TOML format), not settings.json.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import tempfile
import tomllib
from pathlib import Path, PurePosixPath

from gpd.adapters.base import RuntimeAdapter
from gpd.adapters.install_utils import (
    CACHE_DIR_NAME,
    HOOK_SCRIPTS,
    MANIFEST_NAME,
    PATCHES_DIR_NAME,
    UPDATE_CACHE_FILENAME,
    compile_markdown_for_runtime,
    convert_tool_references_in_body,
    expand_tilde,
    get_global_dir,
    hook_python_interpreter,
    managed_hook_paths,
    materialize_first_round_review_schema_headings,
    pre_install_cleanup,
    prune_empty_ancestors,
    remove_empty_text_file,
    remove_stale_agents,
    render_markdown_frontmatter,
    split_markdown_frontmatter,
    verify_installed,
    write_manifest,
)
from gpd.adapters.tool_names import build_runtime_alias_map, reference_translation_map, translate_for_runtime
from gpd.core.observability import gpd_span
from gpd.registry import AgentDef, load_agents_from_dir

logger = logging.getLogger(__name__)

_TOOL_NAME_MAP: dict[str, str] = {
    "file_read": "read_file",
    "file_write": "write_file",
    "file_edit": "apply_patch",
    "shell": "shell",
    "search_files": "grep",
    "find_files": "glob",
    "web_search": "web_search",
    "web_fetch": "web_fetch",
    "notebook_edit": "notebook_edit",
    "agent": "agent",
    "ask_user": "ask_user",
    "todo_write": "todo",
    "task": "task",
    "slash_command": "slash_command",
    "tool_search": "tool_search",
}
_TOOL_ALIAS_MAP = build_runtime_alias_map(_TOOL_NAME_MAP)
_AUTO_DISCOVERED_TOOLS = frozenset({"task"})
_GPD_NOTIFY_COMMENT = "# GPD update notification"
_GPD_NOTIFY_BACKUP_PREFIX = "# GPD original notify: "
_GPD_NOTIFY_WRAPPER_MARKER = "gpd-codex-notify-wrapper-v1"
_GPD_MULTI_AGENT_COMMENT = "# GPD multi-agent support"
_GPD_MULTI_AGENT_BACKUP_PREFIX = "# GPD original multi_agent: "
_GPD_APPROVAL_POLICY_COMMENT = "# GPD runtime approval policy"
_GPD_APPROVAL_POLICY_BACKUP_PREFIX = "# GPD original approval_policy: "
_GPD_SANDBOX_MODE_COMMENT = "# GPD runtime sandbox mode"
_GPD_SANDBOX_MODE_BACKUP_PREFIX = "# GPD original sandbox_mode: "
_GPD_AGENT_ROLES_COMMENT = "# GPD agent roles"
_MANIFEST_CODEX_SKILLS_DIR_KEY = "codex_skills_dir"
_MANIFEST_CODEX_GENERATED_SKILL_DIRS_KEY = "codex_generated_skill_dirs"
_CODEX_DEFAULT_SANDBOX_MODE = "workspace-write"
_CODEX_YOLO_APPROVAL_POLICY = "never"
_CODEX_YOLO_SANDBOX_MODE = "danger-full-access"
_TOOL_REFERENCE_MAP = reference_translation_map(
    _TOOL_NAME_MAP,
    alias_map=_TOOL_ALIAS_MAP,
    auto_discovered_tools=_AUTO_DISCOVERED_TOOLS,
)
_CODEX_MCP_STARTUP_TIMEOUT_SEC = 30
_SHELL_FENCE_LANGUAGES = frozenset({"bash", "sh", "shell", "zsh"})
_CODEX_COMMAND_RUNTIME_NOTE = (
    "<codex_runtime_notes>\n"
    "Codex shell compatibility:\n"
    "- When shell steps call the GPD CLI, use {launcher} instead of the ambient `gpd` on PATH.\n"
    "- The bridge already pins Codex and validates the install contract, so keep using it for normal CLI execution.\n"
    "</codex_runtime_notes>\n\n"
)
_INLINE_GPD_COMMAND_RE = re.compile(r"`(?P<command>gpd(?=\s)[^`]*?)`")
_CODEX_QUESTION_MARKERS = (
    "Use ask_user",
    "ask_user(",
    "ask_user([",
    "Ask inline (freeform, NOT ask_user):",
    "Ask ONE question inline (freeform, NOT ask_user):",
)
_CODEX_QUESTION_RUNTIME_NOTE = (
    "<codex_questioning>\n"
    "- Ask each user-facing question exactly once.\n"
    "- Present options once.\n"
    "- Do not restate the prompt or add meta narration.\n"
    "</codex_questioning>\n\n"
)
_CODEX_ASK_USER_PLATFORM_NOTE_RE = re.compile(
    r"^\s*>\s+\*\*Platform note:\*\* If `ask_user` is not available,[^\n]*\n(?:\s*\n)?",
    re.IGNORECASE | re.MULTILINE,
)
_CODEX_HELP_WORDING_RE = re.compile(r"\bslash-command\b")


# ─── Directory helpers ──────────────────────────────────────────────────────


def get_codex_global_dir() -> Path:
    """Get the global config directory for Codex CLI.

    Priority: CODEX_CONFIG_DIR > ~/.codex
    """
    return Path(get_global_dir("codex"))


def get_codex_skills_dir() -> Path:
    """Get the global skills directory for Codex CLI.

    Skills are stored in ~/.agents/skills/ (separate from config).
    Priority: CODEX_SKILLS_DIR > ~/.agents/skills
    """
    env_dir = os.environ.get("CODEX_SKILLS_DIR")
    if env_dir:
        expanded = expand_tilde(env_dir) or env_dir
        return Path(expanded)
    return Path.home() / ".agents" / "skills"


def _default_local_codex_skills_dir(target_dir: Path) -> Path:
    """Return the repo-scoped Codex skills dir adjacent to *target_dir*."""
    return target_dir.parent / ".agents" / "skills"


def _resolve_codex_skills_dir(target_dir: Path, *, is_global: bool, skills_dir: Path | None = None) -> Path:
    """Resolve the skills directory for an install/uninstall target.

    Global installs default to the shared user-level skills directory. Local
    installs default to a repo-scoped ``.agents/skills`` sibling so the skill
    surface stays aligned with the matching ``.codex`` config tree.
    """
    if skills_dir is not None:
        return skills_dir
    if not is_global:
        return _default_local_codex_skills_dir(target_dir)
    return get_codex_skills_dir()


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


def _load_manifest_codex_generated_skill_dirs(target_dir: Path) -> tuple[str, ...]:
    """Return tracked Codex skill directory names from the local manifest."""
    manifest_path = target_dir / MANIFEST_NAME
    if not manifest_path.exists():
        return ()

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return ()

    if not isinstance(manifest, dict):
        return ()

    metadata_dirs = manifest.get(_MANIFEST_CODEX_GENERATED_SKILL_DIRS_KEY)
    if isinstance(metadata_dirs, list):
        names = [str(name) for name in metadata_dirs if isinstance(name, str) and name.strip()]
        if names:
            return tuple(dict.fromkeys(names))

    raw_files = manifest.get("files")
    if not isinstance(raw_files, dict):
        return ()

    names: list[str] = []
    for rel_path in raw_files:
        if not isinstance(rel_path, str):
            continue
        rel = PurePosixPath(rel_path)
        parts = rel.parts
        if len(parts) == 3 and parts[0] == "skills" and parts[2] == "SKILL.md" and parts[1]:
            names.append(parts[1])
    return tuple(dict.fromkeys(names))


def _load_manifest_install_scope(target_dir: Path) -> str | None:
    """Return the install scope recorded in the local manifest, if present."""
    manifest_path = target_dir / MANIFEST_NAME
    if not manifest_path.exists():
        return None

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    if not isinstance(manifest, dict):
        return None

    install_scope = manifest.get("install_scope")
    if install_scope in {"local", "global"}:
        return str(install_scope)
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
    return translate_for_runtime(
        tool_name,
        _TOOL_NAME_MAP,
        auto_discovered_tools=_AUTO_DISCOVERED_TOOLS,
    )


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

    preamble, frontmatter, separator, body = split_markdown_frontmatter(converted)
    if not frontmatter:
        return f"---\nname: {skill_name}\ndescription: GPD skill - {skill_name}\n---\n{converted}"

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
    return render_markdown_frontmatter(preamble, new_frontmatter, separator or "\n", body)


def _rewrite_codex_help_wording(content: str) -> str:
    """Remove slash-command wording from the installed Codex help surface."""
    return _CODEX_HELP_WORDING_RE.sub("command", content)


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


def _inject_codex_command_runtime_note(content: str, launcher: str) -> str:
    """Prepend Codex-specific shell guidance to installed command skills."""
    note = _CODEX_COMMAND_RUNTIME_NOTE.format(launcher=launcher)
    preamble, frontmatter, separator, body = split_markdown_frontmatter(content)
    if not frontmatter:
        return note + content
    return render_markdown_frontmatter(preamble, frontmatter, separator, note + body)


def _rewrite_codex_gpd_cli_invocations(content: str, launcher: str) -> str:
    """Rewrite direct shell ``gpd`` calls to the shared runtime CLI bridge."""
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
            rewritten.append(_rewrite_codex_shell_line(line, launcher))
            continue

        rewritten.append(_rewrite_codex_inline_gpd_commands(line, launcher))

    return "".join(rewritten)


def _rewrite_codex_inline_gpd_commands(content: str, launcher: str) -> str:
    """Rewrite inline markdown code spans that execute ``gpd`` commands."""
    return _INLINE_GPD_COMMAND_RE.sub(lambda match: f"`{launcher}{match.group('command')[3:]}`", content)


def _normalize_codex_questioning(content: str) -> str:
    """Rewrite mixed ask_user/freeform guidance into a single Codex style."""
    lowered = content.casefold()
    if not any(marker.casefold() in lowered for marker in _CODEX_QUESTION_MARKERS):
        return content

    rewritten = _CODEX_ASK_USER_PLATFORM_NOTE_RE.sub("", content)
    rewritten = re.sub(
        r"(?im)^(\s*)ask one question inline \(freeform, not ask_user\):",
        r"\1Ask exactly one inline freeform question with no preamble or restatement:",
        rewritten,
    )
    rewritten = re.sub(
        r"(?im)^(\s*)ask inline \(freeform, not ask_user\):",
        r"\1Ask one inline freeform question with no preamble or restatement:",
        rewritten,
    )
    rewritten = re.sub(
        r"(?im)^(\s*)use ask_user with current values pre-selected:\s*$",
        r"\1Present these options in plain text with current values pre-selected:",
        rewritten,
    )
    rewritten = re.sub(
        r"(?im)^(\s*)if overlapping, use ask_user:\s*$",
        r"\1If overlapping, present the duplicate choices in plain text:",
        rewritten,
    )
    rewritten = re.sub(
        r"(?im)^(\s*)use ask_user:\s*$",
        r"\1Ask the user once using a single compact prompt block:",
        rewritten,
    )
    rewritten = re.sub(
        r"(?im)^(\s*)based on what they said, ask follow-up questions that dig into their response\.\s*use ask_user with options that probe what they mentioned — interpretations, clarifications, concrete examples\.\s*$",
        r"\1Based on what they said, ask follow-up questions that dig into their response. Keep the options in plain text and probe what they mentioned - interpretations, clarifications, concrete examples.",
        rewritten,
    )
    rewritten = re.sub(
        r"(?im)^(\s*)when you could write a clear scoping contract, use ask_user:\s*$",
        r"\1When you could write a clear scoping contract, ask the user inline:",
        rewritten,
    )

    if "use ask_user with current values pre-selected:" in lowered:
        rewritten = re.sub(r"(?im)^(\s*)ask_user\(", r"\1plain_text_prompt(", rewritten)

    preamble, frontmatter, separator, body = split_markdown_frontmatter(rewritten)
    if _CODEX_QUESTION_RUNTIME_NOTE in body:
        return rewritten
    if not frontmatter:
        return _CODEX_QUESTION_RUNTIME_NOTE + rewritten
    return render_markdown_frontmatter(
        preamble,
        frontmatter,
        separator,
        _CODEX_QUESTION_RUNTIME_NOTE + body,
    )


def _rewrite_codex_shell_line(line: str, launcher: str) -> str:
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
            pieces.append(launcher)
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
    return line[end_index].isspace() or line[end_index] in {'"', "'", "`"}


# ─── Adapter Class ───────────────────────────────────────────────────────────


class CodexAdapter(RuntimeAdapter):
    """Adapter for OpenAI Codex CLI.

    Codex uses distinct discovery/configuration surfaces:
    - Commands -> skill directories under repo/user .agents/skills/<name>/SKILL.md
    - Agents -> agent .md + role .toml files under .codex/agents/
    - Hooks -> config.toml ``notify`` array (not settings.json)
    - Config -> ~/.codex/ (CODEX_CONFIG_DIR env var)
    - Skills -> repo-local .agents/skills/ for local installs, ~/.agents/skills/ for global installs
    """

    tool_name_map = _TOOL_NAME_MAP
    auto_discovered_tools = _AUTO_DISCOVERED_TOOLS
    strip_sub_tags_in_shared_markdown = True

    @property
    def runtime_name(self) -> str:
        return "codex"

    def format_command(self, action: str) -> str:
        return f"$gpd-{action}"

    def translate_shared_command_references(self, content: str) -> str:
        return content.replace("/gpd:", self.command_prefix)

    def get_commit_attribution(self, *, explicit_config_dir: str | None = None) -> str | None:
        """Codex uses the runtime default commit attribution behavior."""
        return ""

    def _gpd_shell_launcher(self, target_dir: Path) -> str:
        """Return the shared runtime CLI bridge command for installed shell calls."""
        return self.runtime_cli_bridge_command(target_dir)

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
        prev_generated_skill_dirs = getattr(self, "_generated_skill_dirs", None)
        self._skills_dir = _resolve_codex_skills_dir(target_dir, is_global=is_global, skills_dir=skills_dir)
        self._generated_skill_dirs = ()
        try:
            return super().install(gpd_root, target_dir, is_global=is_global, explicit_target=explicit_target)
        finally:
            self._skills_dir = prev_skills_dir
            self._generated_skill_dirs = prev_generated_skill_dirs

    # --- Template method hooks ---

    def _compute_path_prefix(self, target_dir: Path, is_global: bool) -> str:
        if is_global or getattr(self, "_install_explicit_target", False):
            return str(target_dir).replace("\\", "/") + "/"
        return f"./{self.config_dir_name}/"

    def _pre_cleanup(self, target_dir: Path) -> None:
        pre_install_cleanup(target_dir, skills_dir=str(self._skills_dir))

    def _install_commands(self, gpd_root: Path, target_dir: Path, path_prefix: str, failures: list[str]) -> int:
        commands_src = gpd_root / "commands"
        launcher = self._gpd_shell_launcher(target_dir)
        self._skills_dir.mkdir(parents=True, exist_ok=True)
        generated_skill_dirs = _copy_commands_as_skills(
            commands_src,
            self._skills_dir,
            "gpd",
            path_prefix,
            gpd_root / "specs",
            self._current_install_scope_flag(),
            launcher=launcher,
        )
        self._generated_skill_dirs = tuple(sorted(generated_skill_dirs))
        if verify_installed(self._skills_dir, "command skills"):
            logger.info("Installed command skills")
        else:
            failures.append("command skills")
        skill_count = sum(1 for d in self._skills_dir.iterdir() if d.is_dir() and d.name.startswith("gpd-"))
        return skill_count

    def _install_content(self, gpd_root: Path, target_dir: Path, path_prefix: str, failures: list[str]) -> None:
        """Install shared specs content with Codex runtime-aware shell rewrites."""
        launcher = self._gpd_shell_launcher(target_dir)

        def _translate(content: str, prefix: str, install_scope: str | None = None) -> str:
            translated = super(CodexAdapter, self).translate_shared_markdown(
                content,
                prefix,
                install_scope=install_scope,
            )
            translated = _rewrite_codex_gpd_cli_invocations(translated, launcher)
            return _normalize_codex_questioning(translated)

        from gpd.adapters.install_utils import install_gpd_content

        failures.extend(
            install_gpd_content(
                gpd_root / "specs",
                target_dir,
                path_prefix,
                self.runtime_name,
                install_scope=self._current_install_scope_flag(),
                markdown_transform=_translate,
            )
        )

    def _install_agents(self, gpd_root: Path, target_dir: Path, path_prefix: str, failures: list[str]) -> int:
        agents_src = gpd_root / "agents"
        gpd_specs_root = gpd_root / "specs"
        launcher = self._gpd_shell_launcher(target_dir)
        runtime_agents = self.load_runtime_agents(gpd_root)
        agent_count = len(runtime_agents)

        # Install agents only as Codex role briefs plus role config TOMLs.
        if agents_src.is_dir():
            agents_dest = target_dir / "agents"
            _copy_agents_as_agent_files(
                agents_src,
                agents_dest,
                path_prefix,
                gpd_specs_root,
                self._current_install_scope_flag(),
                launcher=launcher,
            )
            _write_codex_agent_role_files(agents_dest, runtime_agents)
            if verify_installed(agents_dest, "agents"):
                logger.info("Installed Codex agent role files")
            else:
                failures.append("agents")

        return agent_count

    def _install_version(self, target_dir: Path, version: str, failures: list[str]) -> None:
        """Write VERSION into the shared GPD content tree."""
        super()._install_version(target_dir, version, failures)

    def _configure_runtime(self, target_dir: Path, is_global: bool) -> dict[str, object]:
        _configure_config_toml(
            target_dir,
            is_global,
            explicit_target=getattr(self, "_install_explicit_target", False),
        )
        config_toml = target_dir / "config.toml"
        sandbox_mode = _CODEX_DEFAULT_SANDBOX_MODE
        approval_policy: str | None = None
        if config_toml.exists():
            try:
                parsed = tomllib.loads(config_toml.read_text(encoding="utf-8"))
            except (OSError, tomllib.TOMLDecodeError):
                parsed = {}
            sandbox_value = parsed.get("sandbox_mode")
            approval_value = parsed.get("approval_policy")
            if isinstance(sandbox_value, str):
                sandbox_mode = sandbox_value
            if isinstance(approval_value, str):
                approval_policy = approval_value
        _rewrite_codex_agent_role_runtime_modes(
            target_dir / "agents",
            sandbox_mode=sandbox_mode,
            approval_policy=approval_policy,
        )

        # Wire MCP servers into config.toml.
        from gpd.mcp.builtin_servers import build_mcp_servers_dict

        mcp_servers = build_mcp_servers_dict(python_path=hook_python_interpreter())
        mcp_count = 0
        if mcp_servers:
            mcp_count = _write_mcp_servers_codex_toml(target_dir, mcp_servers)
        agent_role_count = _write_codex_agent_roles_toml(target_dir)

        return {
            "target": str(target_dir),
            "skills_dir": str(self._skills_dir),
            "skills": sum(1 for d in self._skills_dir.iterdir() if d.is_dir() and d.name.startswith("gpd-")),
            "mcpServers": mcp_count,
            "agentRoles": agent_role_count,
        }

    def runtime_permissions_status(self, target_dir: Path, *, autonomy: str) -> dict[str, object]:
        """Report whether Codex approvals/sandbox are aligned with GPD autonomy."""
        config_path = target_dir / "config.toml"
        approval_policy: str | None = None
        sandbox_mode: str = _CODEX_DEFAULT_SANDBOX_MODE
        root_managed = False
        if config_path.exists():
            content = config_path.read_text(encoding="utf-8")
            try:
                parsed = tomllib.loads(content)
            except tomllib.TOMLDecodeError:
                parsed = {}
            approval_value = parsed.get("approval_policy")
            sandbox_value = parsed.get("sandbox_mode")
            if isinstance(approval_value, str):
                approval_policy = approval_value
            if isinstance(sandbox_value, str):
                sandbox_mode = sandbox_value
            root_managed = _root_assignment_has_gpd_marker(
                content,
                _GPD_APPROVAL_POLICY_COMMENT,
                _GPD_APPROVAL_POLICY_BACKUP_PREFIX,
            ) or _root_assignment_has_gpd_marker(
                content,
                _GPD_SANDBOX_MODE_COMMENT,
                _GPD_SANDBOX_MODE_BACKUP_PREFIX,
            )

        agents_dir = target_dir / "agents"
        role_sandbox_mode, role_approval_policy = _codex_agent_role_runtime_summary(agents_dir)
        has_role_files = any(agents_dir.glob("gpd-*.toml")) if agents_dir.exists() else False
        desired_mode = "yolo" if autonomy == "yolo" else "default"
        managed_state = self._runtime_permissions_manifest_state(target_dir) or {}
        managed_by_gpd = managed_state.get("mode") == "yolo" or root_managed

        if desired_mode == "yolo":
            root_aligned = (
                approval_policy == _CODEX_YOLO_APPROVAL_POLICY
                and sandbox_mode == _CODEX_YOLO_SANDBOX_MODE
            )
            roles_aligned = (
                not has_role_files
                or (
                    role_sandbox_mode == _CODEX_YOLO_SANDBOX_MODE
                    and role_approval_policy == _CODEX_YOLO_APPROVAL_POLICY
                )
            )
            config_aligned = root_aligned and roles_aligned
            if config_aligned:
                message = (
                    "Codex is configured for prompt-free approvals and danger-full-access sandboxing "
                    "for the next session."
                )
            elif not root_aligned and not roles_aligned:
                message = (
                    "Codex is not yet configured for yolo mode in either config.toml or the GPD-managed role files."
                )
            elif not root_aligned:
                message = "Codex root config.toml is not yet configured for yolo approval and sandbox settings."
            else:
                message = "Codex GPD-managed role files are not yet configured for yolo approval and sandbox settings."
        else:
            config_aligned = not managed_by_gpd
            if managed_by_gpd:
                message = (
                    "Codex is still pinned to GPD-managed never/danger-full-access defaults from an earlier yolo sync."
                )
            elif approval_policy == _CODEX_YOLO_APPROVAL_POLICY and sandbox_mode == _CODEX_YOLO_SANDBOX_MODE:
                message = (
                    "Codex is still configured for never/danger-full-access, but GPD left it untouched because "
                    "that setting was not created by a prior GPD yolo sync."
                )
            else:
                message = "Codex is using its normal approval and sandbox defaults."

        configured_mode = (
            "yolo"
            if approval_policy == _CODEX_YOLO_APPROVAL_POLICY and sandbox_mode == _CODEX_YOLO_SANDBOX_MODE
            else f"{approval_policy or 'unset'}/{sandbox_mode}"
        )
        return {
            "runtime": self.runtime_name,
            "desired_mode": desired_mode,
            "configured_mode": configured_mode,
            "config_aligned": config_aligned,
            "managed_by_gpd": managed_by_gpd,
            "settings_path": str(config_path),
            "approval_policy": approval_policy or "unset",
            "sandbox_mode": sandbox_mode,
            "agent_role_approval_policy": role_approval_policy or "unset",
            "agent_role_sandbox_mode": role_sandbox_mode or "mixed",
            "message": message,
        }

    def sync_runtime_permissions(self, target_dir: Path, *, autonomy: str) -> dict[str, object]:
        """Align Codex approvals/sandbox settings with the requested autonomy."""
        config_path = target_dir / "config.toml"
        toml_content = config_path.read_text(encoding="utf-8") if config_path.exists() else ""
        changed = False
        if autonomy == "yolo":
            updated = toml_content
            if _root_assignment_line(updated, "approval_policy") != f'approval_policy = "{_CODEX_YOLO_APPROVAL_POLICY}"':
                updated = _install_gpd_root_string_setting(
                    updated,
                    key="approval_policy",
                    value=_CODEX_YOLO_APPROVAL_POLICY,
                    comment=_GPD_APPROVAL_POLICY_COMMENT,
                    backup_prefix=_GPD_APPROVAL_POLICY_BACKUP_PREFIX,
                )
            if _root_assignment_line(updated, "sandbox_mode") != f'sandbox_mode = "{_CODEX_YOLO_SANDBOX_MODE}"':
                updated = _install_gpd_root_string_setting(
                    updated,
                    key="sandbox_mode",
                    value=_CODEX_YOLO_SANDBOX_MODE,
                    comment=_GPD_SANDBOX_MODE_COMMENT,
                    backup_prefix=_GPD_SANDBOX_MODE_BACKUP_PREFIX,
                )
            if updated != toml_content:
                config_path.write_text(updated, encoding="utf-8")
                changed = True

            roles_changed = _rewrite_codex_agent_role_runtime_modes(
                target_dir / "agents",
                sandbox_mode=_CODEX_YOLO_SANDBOX_MODE,
                approval_policy=_CODEX_YOLO_APPROVAL_POLICY,
            )
            changed = changed or roles_changed
            if changed:
                self._set_runtime_permissions_manifest_state(target_dir, {"mode": "yolo"})

            status = self.runtime_permissions_status(target_dir, autonomy=autonomy)
            sync_applied = bool(status.get("config_aligned"))
            return {
                **status,
                "changed": changed,
                "sync_applied": sync_applied,
                "requires_relaunch": changed,
                "next_step": (
                    "Restart Codex so the current session picks up the persisted yolo approval and sandbox settings."
                )
                if changed
                else None,
            }

        managed_state = self._runtime_permissions_manifest_state(target_dir) or {}
        if managed_state.get("mode") == "yolo":
            updated = _remove_gpd_root_string_setting(
                toml_content,
                key="approval_policy",
                comment=_GPD_APPROVAL_POLICY_COMMENT,
                backup_prefix=_GPD_APPROVAL_POLICY_BACKUP_PREFIX,
            )
            updated = _remove_gpd_root_string_setting(
                updated,
                key="sandbox_mode",
                comment=_GPD_SANDBOX_MODE_COMMENT,
                backup_prefix=_GPD_SANDBOX_MODE_BACKUP_PREFIX,
            )
            if updated != toml_content:
                config_path.write_text(updated, encoding="utf-8")
                changed = True
            roles_changed = _rewrite_codex_agent_role_runtime_modes(
                target_dir / "agents",
                sandbox_mode=_CODEX_DEFAULT_SANDBOX_MODE,
                approval_policy=None,
            )
            changed = changed or roles_changed
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
            result["next_step"] = "Restart Codex to return the session to its normal approval and sandbox defaults."
        return result

    def _verify(self, target_dir: Path) -> None:
        """Verify the Codex install includes its required role and config surfaces."""
        super()._verify(target_dir)
        agents_dir = target_dir / "agents"
        installed_agent_names = {path.stem for path in agents_dir.glob("gpd-*.md")}
        installed_role_names = {path.stem for path in agents_dir.glob("gpd-*.toml")}
        if installed_agent_names and installed_role_names != installed_agent_names:
            raise RuntimeError("Codex install incomplete: GPD agent role files are not installed")
        config_toml = target_dir / "config.toml"
        if not config_toml.exists():
            raise RuntimeError("Codex install incomplete: config.toml is not installed")
        try:
            parsed = tomllib.loads(config_toml.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as exc:
            raise RuntimeError("Codex install incomplete: config.toml is invalid") from exc
        agents = parsed.get("agents")
        registered_roles = {
            name for name, value in agents.items() if name.startswith("gpd-") and isinstance(value, dict)
        } if isinstance(agents, dict) else set()
        if installed_agent_names and not installed_agent_names.issubset(registered_roles):
            raise RuntimeError("Codex install incomplete: GPD agent roles are not registered")

    def install_completeness_relpaths(self) -> tuple[str, ...]:
        """Return Codex-specific artifacts required for a usable install."""
        return (*super().install_completeness_relpaths(), "config.toml")

    def missing_install_artifacts(self, target_dir: Path) -> tuple[str, ...]:
        """Return missing Codex install artifacts, including the shared skills dir."""
        missing = list(super().missing_install_artifacts(target_dir))

        skills_dir = _load_manifest_codex_skills_dir(target_dir)
        if skills_dir is None:
            manifest_install_scope = _load_manifest_install_scope(target_dir)
            skills_dir = _resolve_codex_skills_dir(
                target_dir,
                is_global=manifest_install_scope == "global" if manifest_install_scope is not None else _is_global_codex_target(target_dir),
            )

        tracked_skill_dirs = _load_manifest_codex_generated_skill_dirs(target_dir)
        try:
            if tracked_skill_dirs:
                has_gpd_skills = skills_dir.is_dir() and all((skills_dir / name).is_dir() for name in tracked_skill_dirs)
            else:
                has_gpd_skills = skills_dir.is_dir() and any(
                    entry.is_dir() and entry.name.startswith("gpd-") for entry in skills_dir.iterdir()
                )
        except OSError:
            has_gpd_skills = False

        if not has_gpd_skills:
            missing.append(str(skills_dir))

        return tuple(missing)

    def _write_manifest(self, target_dir: Path, version: str) -> None:
        write_manifest(
            target_dir,
            version,
            runtime=self.runtime_name,
            skills_dir=str(self._skills_dir),
            metadata={
                _MANIFEST_CODEX_SKILLS_DIR_KEY: str(self._skills_dir),
                _MANIFEST_CODEX_GENERATED_SKILL_DIRS_KEY: list(getattr(self, "_generated_skill_dirs", ())),
            },
            install_scope=self._current_install_scope_flag(),
            explicit_target=getattr(self, "_install_explicit_target", False),
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
        with gpd_span("adapter.uninstall", runtime=self.runtime_name, target=str(target_dir)) as span:
            self._validate_target_runtime(target_dir, action="uninstall from")
            if skills_dir is None:
                skills_dir = _resolve_codex_uninstall_skills_dir(
                    target_dir,
                    is_global=_is_global_codex_target(target_dir),
                )
            removed: list[str] = []
            counts: dict[str, int] = {"skills": 0, "agents": 0, "hooks": 0}
            managed_hooks = managed_hook_paths(target_dir)
            tracked_skill_dirs = _load_manifest_codex_generated_skill_dirs(target_dir)

            # 1. Remove only skill directories tracked as generated in the manifest.
            if skills_dir.exists() and tracked_skill_dirs:
                for skill_name in tracked_skill_dirs:
                    entry = skills_dir / skill_name
                    if entry.is_dir():
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

            # 4. Remove GPD agent files (gpd-*.md and managed role .toml files)
            agents_dir = target_dir / "agents"
            if agents_dir.exists():
                for f in list(agents_dir.iterdir()):
                    if f.is_file() and f.name.startswith("gpd-") and f.suffix in {".md", ".toml"}:
                        f.unlink()
                        counts["agents"] += 1

            # 5. Remove GPD hooks
            hooks_dir = target_dir / "hooks"
            if hooks_dir.exists():
                for rel_path in sorted(managed_hooks):
                    hook_path = target_dir / rel_path
                    if hook_path.is_file():
                        hook_path.unlink()
                        counts["hooks"] += 1

            # 6. Remove GPD update cache files.
            cache_dir = target_dir / CACHE_DIR_NAME
            removed_cache = False
            for cache_path in (
                cache_dir / UPDATE_CACHE_FILENAME,
                cache_dir / f"{UPDATE_CACHE_FILENAME}.inflight",
            ):
                if cache_path.is_file():
                    cache_path.unlink()
                    removed_cache = True
            if removed_cache:
                removed.append(f"{CACHE_DIR_NAME}/{UPDATE_CACHE_FILENAME}")

            # 7. Remove GPD MCP servers from config.toml
            config_toml_mcp = target_dir / "config.toml"
            if config_toml_mcp.exists():
                toml_mcp = config_toml_mcp.read_text(encoding="utf-8")
                cleaned_mcp = _remove_gpd_mcp_toml_sections(toml_mcp)
                if cleaned_mcp != toml_mcp:
                    config_toml_mcp.write_text(cleaned_mcp, encoding="utf-8")
                    removed.append("config.toml MCP servers")

            # 8. Clean up config.toml
            config_toml = target_dir / "config.toml"
            if config_toml.exists():
                toml_content = config_toml.read_text(encoding="utf-8")
                cleaned = _remove_gpd_notify_config(toml_content, target_dir=target_dir)
                cleaned = _remove_gpd_multi_agent_config(cleaned)
                cleaned = _remove_gpd_root_string_setting(
                    cleaned,
                    key="approval_policy",
                    comment=_GPD_APPROVAL_POLICY_COMMENT,
                    backup_prefix=_GPD_APPROVAL_POLICY_BACKUP_PREFIX,
                )
                cleaned = _remove_gpd_root_string_setting(
                    cleaned,
                    key="sandbox_mode",
                    comment=_GPD_SANDBOX_MODE_COMMENT,
                    backup_prefix=_GPD_SANDBOX_MODE_BACKUP_PREFIX,
                )
                cleaned = _remove_gpd_agent_role_sections(cleaned)
                if cleaned != toml_content:
                    config_toml.write_text(cleaned, encoding="utf-8")
                    removed.append("config.toml GPD entries")
                if remove_empty_text_file(config_toml):
                    removed.append("config.toml")

            for path in (
                target_dir / "agents",
                target_dir / "hooks",
                target_dir / "cache",
                target_dir,
            ):
                prune_empty_ancestors(path, stop_at=target_dir.parent)
            prune_empty_ancestors(skills_dir, stop_at=skills_dir.parent.parent)

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
    *,
    launcher: str,
) -> set[str]:
    """Copy commands as Codex skill directories.

    Codex expects: ~/.agents/skills/gpd-help/SKILL.md
    Source structure: commands/help.md -> gpd-help/SKILL.md
    Nested: commands/sub/help.md -> gpd-sub-help/SKILL.md (preserves hierarchy)
    """
    if not src_dir.exists():
        return set()

    skills_parent = skills_dir.parent
    skills_parent.mkdir(parents=True, exist_ok=True)

    staging_root = Path(tempfile.mkdtemp(prefix=f".{skills_dir.name}GPD-", dir=str(skills_parent)))
    staged_skills_dir = staging_root / skills_dir.name
    staged_skills_dir.mkdir(parents=True, exist_ok=True)

    live_backup: Path | None = None
    generated_skill_dirs: set[str] = set()
    try:
        if skills_dir.exists():
            for entry in sorted(skills_dir.iterdir()):
                if entry.name.startswith(f"{prefix}-"):
                    continue
                _copy_preserved_skill_entry(entry, staged_skills_dir / entry.name)

        generated_skill_dirs = _render_commands_as_skills(
            src_dir,
            staged_skills_dir,
            prefix,
            path_prefix,
            gpd_src_root,
            install_scope,
            launcher=launcher,
        )

        if skills_dir.exists():
            live_backup = staging_root / f"{skills_dir.name}.backup"
            skills_dir.rename(live_backup)
        staged_skills_dir.rename(skills_dir)
    except Exception:
        if live_backup is not None and live_backup.exists() and not skills_dir.exists():
            live_backup.rename(skills_dir)
        raise
    finally:
        if live_backup is not None and live_backup.exists():
            try:
                shutil.rmtree(live_backup)
            except OSError:
                logger.warning("Failed to remove backup skills dir %s", live_backup)
        if staging_root.exists():
            try:
                shutil.rmtree(staging_root)
            except OSError:
                logger.warning("Failed to clean staging skills dir %s", staging_root)
    return generated_skill_dirs


def _copy_preserved_skill_entry(src: Path, dest: Path) -> None:
    """Copy a non-GPD skill entry into a staged skills directory."""
    if src.is_symlink():
        dest.symlink_to(src.readlink())
        return
    if src.is_dir():
        shutil.copytree(src, dest, symlinks=True)
        return
    shutil.copy2(src, dest)


def _render_commands_as_skills(
    src_dir: Path,
    skills_dir: Path,
    prefix: str,
    path_prefix: str,
    gpd_src_root: Path | None = None,
    install_scope: str | None = None,
    *,
    launcher: str,
) -> set[str]:
    """Render command markdown into a skills directory without mutating the live tree."""
    generated_skill_dirs: set[str] = set()
    for entry in sorted(src_dir.iterdir()):
        if entry.is_dir():
            generated_skill_dirs.update(
                _render_commands_as_skills(
                    entry,
                    skills_dir,
                    f"{prefix}-{entry.name}",
                    path_prefix,
                    gpd_src_root,
                    install_scope,
                    launcher=launcher,
                )
            )
        elif entry.suffix == ".md":
            base_name = entry.stem
            skill_name = f"{prefix}-{base_name}"
            skill_dir = skills_dir / skill_name
            skill_dir.mkdir(parents=True, exist_ok=True)
            generated_skill_dirs.add(skill_name)

            content = compile_markdown_for_runtime(
                entry.read_text(encoding="utf-8"),
                runtime="codex",
                path_prefix=path_prefix,
                install_scope=install_scope,
                src_root=gpd_src_root,
            )
            content = _convert_to_codex_skill(content, skill_name)
            content = convert_tool_references_in_body(content, _TOOL_REFERENCE_MAP)
            content = _rewrite_codex_gpd_cli_invocations(content, launcher)
            content = _normalize_codex_questioning(content)
            content = _inject_codex_command_runtime_note(content, launcher)
            if skill_name == "gpd-help":
                content = _rewrite_codex_help_wording(content)

            (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")
    return generated_skill_dirs


def _copy_agents_as_agent_files(
    agents_src: Path,
    agents_dest: Path,
    path_prefix: str,
    gpd_content_dir: Path | None = None,
    install_scope: str | None = None,
    *,
    launcher: str,
) -> None:
    """Copy agents as runtime agent markdown files for Codex.

    Applies placeholder expansion, @-include expansion, and tool reference translation.
    """
    if not agents_src.exists():
        return
    agents_dest.mkdir(parents=True, exist_ok=True)
    source_root = gpd_content_dir or agents_src.parent / "specs"

    new_agent_names: set[str] = set()

    for entry in sorted(agents_src.iterdir()):
        if not entry.is_file() or entry.suffix != ".md":
            continue

        content = compile_markdown_for_runtime(
            entry.read_text(encoding="utf-8"),
            runtime="codex",
            path_prefix=path_prefix,
            install_scope=install_scope,
            src_root=source_root,
            protect_agent_prompt_body=True,
        )
        content = materialize_first_round_review_schema_headings(content)
        content = convert_tool_references_in_body(content, _TOOL_REFERENCE_MAP)
        content = _rewrite_codex_gpd_cli_invocations(content, launcher)
        content = _normalize_codex_questioning(content)

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


def _parse_toml_string_assignment(line: str, key: str) -> str | None:
    stripped = line.strip()
    if not (stripped.startswith(f"{key} ") or stripped.startswith(f"{key}=")):
        return None
    try:
        parsed = tomllib.loads(f"[section]\n{stripped}\n")
    except tomllib.TOMLDecodeError:
        return None
    section = parsed.get("section")
    if not isinstance(section, dict):
        return None
    value = section.get(key)
    return value if isinstance(value, str) else None


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


def _codex_agent_role_config_rel_path(agent_name: str) -> str:
    return f"agents/{agent_name}.toml"


def _codex_agent_role_config_path(target_dir: Path, agent_name: str) -> Path:
    return target_dir / "agents" / f"{agent_name}.toml"


def _build_codex_agent_role_instructions(agent_name: str, agent_markdown_path: Path) -> str:
    agent_path = agent_markdown_path.resolve(strict=False).as_posix()
    return (
        f"You are the `{agent_name}` role for Get Physics Done (GPD).\n"
        f'Before doing any substantive work, read and follow the installed role brief at "{agent_path}".\n'
        "Treat that markdown file as the authoritative role contract for scope, workflow, and output expectations."
    )


def _render_codex_agent_role_lines(
    *,
    developer_instructions: str,
    sandbox_mode: str = "workspace-write",
    approval_policy: str | None = None,
) -> list[str]:
    lines = [
        "# Managed by Get Physics Done (GPD).",
        f'sandbox_mode = "{sandbox_mode}"',
    ]
    if approval_policy:
        lines.append(f'approval_policy = "{approval_policy}"')
    lines.append(f"developer_instructions = {_toml_string(developer_instructions)}")
    return lines


def _write_codex_agent_role_files(
    agents_dest: Path,
    runtime_agents: tuple[AgentDef, ...],
    *,
    sandbox_mode: str = "workspace-write",
    approval_policy: str | None = None,
) -> None:
    """Write role-specific Codex config layers alongside installed agent briefs."""
    if not agents_dest.exists():
        return

    managed_role_names: set[str] = set()
    for agent in runtime_agents:
        role_path = agents_dest / f"{agent.name}.toml"
        agent_markdown_path = agents_dest / f"{agent.name}.md"
        lines = _render_codex_agent_role_lines(
            developer_instructions=_build_codex_agent_role_instructions(agent.name, agent_markdown_path),
            sandbox_mode=sandbox_mode,
            approval_policy=approval_policy,
        )
        role_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        managed_role_names.add(role_path.name)

    for existing in agents_dest.iterdir():
        if (
            existing.is_file()
            and existing.name.startswith("gpd-")
            and existing.suffix == ".toml"
            and existing.name not in managed_role_names
        ):
            existing.unlink()


def _rewrite_codex_agent_role_runtime_modes(
    agents_dest: Path,
    *,
    sandbox_mode: str,
    approval_policy: str | None,
) -> bool:
    """Rewrite installed GPD role TOMLs to the requested sandbox/approval mode."""
    changed = False
    if not agents_dest.exists():
        return changed

    for role_path in sorted(agents_dest.glob("gpd-*.toml")):
        try:
            content = role_path.read_text(encoding="utf-8")
            parsed = tomllib.loads(content)
        except (OSError, tomllib.TOMLDecodeError):
            continue
        developer_instructions = parsed.get("developer_instructions")
        if not isinstance(developer_instructions, str):
            continue
        rendered = "\n".join(
            _render_codex_agent_role_lines(
                developer_instructions=developer_instructions,
                sandbox_mode=sandbox_mode,
                approval_policy=approval_policy,
            )
        ) + "\n"
        if content != rendered:
            role_path.write_text(rendered, encoding="utf-8")
            changed = True
    return changed


def _codex_agent_role_runtime_summary(agents_dest: Path) -> tuple[str | None, str | None]:
    """Return shared sandbox/approval settings when all GPD role files agree."""
    if not agents_dest.exists():
        return None, None

    sandbox_modes: set[str] = set()
    approval_policies: set[str] = set()
    for role_path in sorted(agents_dest.glob("gpd-*.toml")):
        try:
            parsed = tomllib.loads(role_path.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError):
            continue
        sandbox_mode = parsed.get("sandbox_mode")
        approval_policy_value = parsed.get("approval_policy")
        if isinstance(sandbox_mode, str):
            sandbox_modes.add(sandbox_mode)
        if isinstance(approval_policy_value, str):
            approval_policies.add(approval_policy_value)

    sandbox_summary = sandbox_modes.pop() if len(sandbox_modes) == 1 else None
    approval_summary = approval_policies.pop() if len(approval_policies) == 1 else None
    return sandbox_summary, approval_summary


def _is_managed_codex_agent_role_section(existing_body: list[str] | None, agent_name: str) -> bool:
    if existing_body is None:
        return False
    expected_config = _codex_agent_role_config_rel_path(agent_name)
    for line in existing_body:
        config_path = _parse_toml_string_assignment(line, "config_file")
        if config_path == expected_config:
            return True
    return False


def _build_codex_agent_role_section_lines(agent: AgentDef, *, existing_body: list[str] | None) -> list[str]:
    preserved_lines, _ = _split_preserved_toml_lines(
        existing_body,
        managed_keys={"description", "config_file"},
    )
    lines = [f"\n[agents.{agent.name}]"]
    lines.append(f"description = {_toml_string(agent.description)}")
    lines.append(f"config_file = {_toml_string(_codex_agent_role_config_rel_path(agent.name))}")
    lines.extend(preserved_lines)
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


def _write_codex_agent_roles_toml(target_dir: Path) -> int:
    """Ensure Codex agent role registrations exist for installed GPD agents."""
    config_toml = target_dir / "config.toml"
    target_dir.mkdir(parents=True, exist_ok=True)

    content = ""
    if config_toml.exists():
        content = config_toml.read_text(encoding="utf-8")
    existing_content = content
    content = _remove_gpd_agent_role_sections(content)

    installed_agents = load_agents_from_dir(target_dir / "agents")
    managed_sections: list[str] = []
    for _, agent in sorted(installed_agents.items()):
        _, existing_body, _ = _split_toml_section(existing_content, f"agents.{agent.name}")
        if existing_body is not None and not _is_managed_codex_agent_role_section(existing_body, agent.name):
            continue
        if not managed_sections:
            managed_sections.append(_GPD_AGENT_ROLES_COMMENT)
        managed_sections.extend(
            _build_codex_agent_role_section_lines(
                agent,
                existing_body=existing_body,
            )
        )

    if content and managed_sections and not content.endswith("\n"):
        content += "\n"
    if managed_sections:
        content += "\n".join(managed_sections) + "\n"
    config_toml.write_text(content, encoding="utf-8")
    return len(installed_agents)


def _remove_gpd_mcp_toml_sections(content: str) -> str:
    """Remove GPD MCP server sections from TOML content."""
    from gpd.mcp.builtin_servers import GPD_MCP_SERVER_KEYS

    # Remove the header comment and all [mcp_serversGPD-*] sections.
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


def _remove_gpd_agent_role_sections(content: str) -> str:
    """Remove GPD-managed Codex agent role registrations from TOML content."""
    cleaned: list[str] = []
    lines = content.splitlines()
    idx = 0
    while idx < len(lines):
        line = lines[idx]
        stripped = line.strip()
        if stripped == _GPD_AGENT_ROLES_COMMENT:
            idx += 1
            continue

        section_name = _parse_section_name(line)
        if section_name is not None and section_name.startswith("agents.gpd-"):
            end = len(lines)
            for scan in range(idx + 1, len(lines)):
                if _parse_section_name(lines[scan]) is not None:
                    end = scan
                    break
            existing_body = lines[idx + 1 : end]
            agent_name = section_name[len("agents.") :]
            if _is_managed_codex_agent_role_section(existing_body, agent_name):
                idx = end
                continue

        cleaned.append(line)
        idx += 1

    return re.sub(r"\n{3,}", "\n\n", _serialize_toml_lines(cleaned))


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


def _root_assignment_line(toml_content: str, key: str) -> str | None:
    """Return the top-level assignment line for *key*, if present."""
    for line in toml_content.splitlines():
        stripped = line.strip()
        if _parse_section_name(stripped) is not None:
            break
        if _toml_assignment_key(stripped) == key:
            return stripped
    return None


def _root_assignment_has_gpd_marker(toml_content: str, comment: str, backup_prefix: str) -> bool:
    """Return True when a GPD-managed root assignment block is present."""
    for line in toml_content.splitlines():
        stripped = line.strip()
        if _parse_section_name(stripped) is not None:
            break
        if stripped == comment or stripped.startswith(backup_prefix):
            return True
    return False


def _install_gpd_root_string_setting(
    toml_content: str,
    *,
    key: str,
    value: str,
    comment: str,
    backup_prefix: str,
) -> str:
    """Install a managed top-level string assignment while preserving the original line."""
    desired_line = f'{key} = "{value}"'
    cleaned_lines: list[str] = []
    insert_at: int | None = None
    original_line: str | None = None

    past_first_section = False
    for line in toml_content.splitlines():
        stripped = line.strip()
        if _parse_section_name(stripped) is not None:
            past_first_section = True
        if not past_first_section and _toml_assignment_key(stripped) == key:
            if insert_at is None:
                insert_at = len(cleaned_lines)
            original_line = stripped
            continue
        cleaned_lines.append(line)

    block: list[str] = [comment]
    if original_line is not None:
        block.append(backup_prefix + original_line)
    block.append(desired_line)

    if insert_at is None:
        insert_at = _first_section_index(cleaned_lines)
        if insert_at > 0 and cleaned_lines[insert_at - 1].strip() != "":
            block = [""] + block
        cleaned_lines[insert_at:insert_at] = block + [""]
    else:
        cleaned_lines[insert_at:insert_at] = block

    return _serialize_toml_lines(cleaned_lines)


def _remove_gpd_root_string_setting(
    toml_content: str,
    *,
    key: str,
    comment: str,
    backup_prefix: str,
) -> str:
    """Remove a managed top-level string assignment and restore its backup when present."""
    cleaned_lines: list[str] = []
    insert_at: int | None = None
    original_line: str | None = None
    pending_managed_block = False
    past_first_section = False
    had_managed_block = False

    for line in toml_content.splitlines():
        stripped = line.strip()
        if _parse_section_name(stripped) is not None:
            past_first_section = True
        if not past_first_section and stripped == comment:
            had_managed_block = True
            pending_managed_block = True
            if insert_at is None:
                insert_at = len(cleaned_lines)
            continue
        if not past_first_section and stripped.startswith(backup_prefix):
            had_managed_block = True
            pending_managed_block = True
            original_line = stripped[len(backup_prefix) :].strip()
            if insert_at is None:
                insert_at = len(cleaned_lines)
            continue
        if not past_first_section and _toml_assignment_key(stripped) == key and pending_managed_block:
            had_managed_block = True
            pending_managed_block = False
            if insert_at is None:
                insert_at = len(cleaned_lines)
            continue
        pending_managed_block = False
        cleaned_lines.append(line)

    if not had_managed_block:
        return toml_content

    if original_line is not None:
        position = insert_at if insert_at is not None else len(cleaned_lines)
        cleaned_lines[position:position] = [original_line]

    return re.sub(r"\n{3,}", "\n\n", _serialize_toml_lines(cleaned_lines))


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

    notify_hook = HOOK_SCRIPTS["notify"]

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
    parsed = _parse_notify_assignment(line)
    return _notify_assignment_is_gpd_managed(parsed)


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
    wrapper_script = (
        "import json, subprocess, sys\n"
        "payload = sys.stdin.buffer.read()\n"
        "existing = json.loads(sys.argv[1])\n"
        "gpd_path = sys.argv[2]\n"
        "for command in (existing, [sys.executable, gpd_path]):\n"
        "    try:\n"
        "        subprocess.run(command, input=payload, check=False)\n"
        "    except OSError:\n"
        "        pass\n"
    )
    parts = [
        _toml_string(hook_python_interpreter()),
        _toml_string("-c"),
        _toml_string(wrapper_script),
        _toml_string(json.dumps(existing_notify)),
        _toml_string(desired_path),
        _toml_string(_GPD_NOTIFY_WRAPPER_MARKER),
    ]
    return f"notify = [{', '.join(parts)}]"


def _managed_notify_paths(target_dir: Path | None = None) -> set[str]:
    paths = {".codex/hooks/notify.py"}
    if target_dir is not None:
        paths.add(str(target_dir / "hooks" / HOOK_SCRIPTS["notify"]).replace("\\", "/"))
    return paths


def _notify_assignment_is_gpd_managed(parsed_notify: list[str] | None, *, target_dir: Path | None = None) -> bool:
    if not parsed_notify:
        return False
    if _GPD_NOTIFY_WRAPPER_MARKER in parsed_notify:
        return True

    managed_paths = _managed_notify_paths(target_dir)
    return len(parsed_notify) == 2 and parsed_notify[1] in managed_paths


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
    pending_managed_block = False

    past_first_section = False
    for line in toml_content.splitlines():
        stripped = line.strip()
        if _parse_section_name(stripped) is not None:
            past_first_section = True
        if not past_first_section and (
            stripped == _GPD_NOTIFY_COMMENT or stripped.startswith(_GPD_NOTIFY_BACKUP_PREFIX)
        ):
            if insert_at is None:
                insert_at = len(cleaned_lines)
            pending_managed_block = True
            continue
        # Only match top-level notify (before any section header)
        if not past_first_section and stripped.startswith("notify"):
            if insert_at is None:
                insert_at = len(cleaned_lines)
            parsed = _parse_notify_assignment(line)
            if pending_managed_block or _notify_assignment_is_gpd_managed(parsed):
                pending_managed_block = False
                continue
            if parsed is not None:
                existing_notify = parsed
                pending_managed_block = False
                continue
        pending_managed_block = False
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


def _remove_gpd_notify_config(toml_content: str, *, target_dir: Path | None = None) -> str:
    cleaned_lines: list[str] = []
    insert_at: int | None = None
    original_notify: str | None = None
    pending_managed_block = False

    for line in toml_content.splitlines():
        stripped = line.strip()
        if stripped == _GPD_NOTIFY_COMMENT:
            if insert_at is None:
                insert_at = len(cleaned_lines)
            pending_managed_block = True
            continue
        if stripped.startswith(_GPD_NOTIFY_BACKUP_PREFIX):
            if insert_at is None:
                insert_at = len(cleaned_lines)
            original_notify = stripped[len(_GPD_NOTIFY_BACKUP_PREFIX) :].strip()
            pending_managed_block = True
            continue
        parsed = _parse_notify_assignment(line)
        if stripped.startswith("notify") and (
            pending_managed_block or _notify_assignment_is_gpd_managed(parsed, target_dir=target_dir)
        ):
            if insert_at is None:
                insert_at = len(cleaned_lines)
            pending_managed_block = False
            continue
        pending_managed_block = False
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
