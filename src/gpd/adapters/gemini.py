"""Gemini CLI runtime adapter.

Gemini CLI uses:
- ``.md`` agent files with YAML frontmatter (tools as YAML array, no ``color:``)
- ``.toml`` command files (TOML with ``prompt`` and ``description`` fields)
- ``settings.json`` for hooks, statusline, and ``experimental.enableAgents``
- ``@`` include directives must be expanded at install time (no native support)
- ``<sub>`` HTML tags must be stripped (terminal rendering)
"""

from __future__ import annotations

import json
import logging
import re
import shlex
import shutil
import tomllib
from collections.abc import Mapping
from pathlib import Path

from gpd.adapters.base import RuntimeAdapter
from gpd.adapters.install_utils import (
    HOOK_SCRIPTS,
    MANIFEST_NAME,
    _is_hook_command_for_script,
    build_hook_command,
    compile_markdown_for_runtime,
    convert_tool_references_in_body,
    ensure_update_hook,
    hook_python_interpreter,
    parse_jsonc,
    process_attribution,
    protect_runtime_agent_prompt,
    prune_empty_ancestors,
    read_settings,
    remove_empty_json_object_file,
    remove_stale_agents,
    render_markdown_frontmatter,
    should_preserve_public_local_cli_command,
    split_markdown_frontmatter,
    strip_sub_tags,
    verify_installed,
    write_manifest,
    write_settings,
)
from gpd.adapters.install_utils import (
    finish_install as _finish_install,
)
from gpd.adapters.tool_names import build_runtime_alias_map, reference_translation_map, translate_for_runtime
from gpd.mcp import managed_integrations as _managed_integrations

logger = logging.getLogger(__name__)

_GEMINI_AGENT_FRONTMATTER_FIELDS: frozenset[str] = frozenset(
    {
        "kind",
        "name",
        "description",
        "display_name",
        "tools",
        "model",
        "temperature",
        "max_turns",
        "timeout_mins",
        "agent_card_url",
        "auth",
    }
)
# Gemini's agent loader uses a strict schema, so installs must drop any
# adapter-owned metadata keys that fall outside this allowlist.

_TOOL_NAME_MAP: dict[str, str] = {
    "file_read": "read_file",
    "file_write": "write_file",
    "file_edit": "replace",
    "shell": "run_shell_command",
    "search_files": "search_file_content",
    "find_files": "glob",
    "web_search": "google_web_search",
    "web_fetch": "web_fetch",
    "notebook_edit": "notebook_edit",
    "agent": "agent",
    "ask_user": "ask_user",
    "todo_write": "write_todos",
    "task": "task",
    "slash_command": "slash_command",
    "tool_search": "tool_search",
}
_TOOL_ALIAS_MAP = build_runtime_alias_map(_TOOL_NAME_MAP)
_AUTO_DISCOVERED_TOOLS = frozenset({"task"})
_DROP_MCP_FRONTMATTER_TOOLS = True
_TOOL_REFERENCE_MAP = reference_translation_map(
    _TOOL_NAME_MAP,
    alias_map=_TOOL_ALIAS_MAP,
    auto_discovered_tools=_AUTO_DISCOVERED_TOOLS,
    drop_mcp_frontmatter_tools=_DROP_MCP_FRONTMATTER_TOOLS,
)

_GEMINI_POLICY_DIR_NAME = "policies"
_GEMINI_POLICY_FILE_NAME = "gpd-auto-edit.toml"
_GEMINI_RUNTIME_BIN_DIR_NAME = "bin"
_GEMINI_YOLO_WRAPPER_NAME = "gemini-gpd-yolo"
_GEMINI_APPROVED_CONTRACT_PATH = "GPD/.approved-project-contract.json"
_GEMINI_STATIC_POLICY_COMMAND_PREFIXES: tuple[str, ...] = (
    "git init",
    "mkdir -p GPD",
    "mkdir -p GPD/research",
    "printf '%s\\n' \"$PROJECT_CONTRACT_JSON\"",
)
_SHELL_FENCE_LANGUAGES = frozenset({"bash", "sh", "shell", "zsh"})
_GEMINI_COMMAND_RUNTIME_NOTE = (
    "<gemini_runtime_notes>\n"
    "Gemini shell compatibility:\n"
    "- When shell steps call the GPD CLI, use {launcher} instead of the ambient `gpd` on PATH.\n"
    "- Gemini's enforced shell-prefix allowlist for GPD auto-edit mode is:\n{allowlist}\n"
    "- Gemini policy checks are syntactic in headless auto-edit mode. Prefer direct commands and reason over stdout instead of wrapping approved commands in shell variables, `$(...)`, heredocs, or extra chained blocks.\n"
    "- Any remaining `VAR=$(...)` examples in rendered workflow guidance are non-runnable shorthand; do not copy them into Gemini auto-edit mode.\n"
    "- Keep contract JSON in-memory or under `GPD/`. Do not write approved contracts to `/tmp`.\n"
    "</gemini_runtime_notes>\n\n"
)
_GEMINI_NEW_PROJECT_INIT_REPLACEMENT = """Run the init command as its own shell call in Gemini auto-edit mode. Do not wrap it in `INIT=$(...)` or an `if` block.

```bash
gpd --raw init new-project
```

If the init command fails, stop, surface the error, and do not proceed with the workflow."""
_GEMINI_NEW_PROJECT_INIT_BLOCK_RE = re.compile(
    r"```bash\n"
    r"INIT=\$\((?:gpd --raw init new-project(?: --stage [a-z_]+)?)\)\n"
    r"if \[ \$\? -ne 0 \]; then\n"
    r"  echo \"ERROR: (?:gpd )?[^\n]+: \$INIT\"\n"
    r"  # STOP — display the error to the user and do not proceed with the workflow\.\n"
    r"fi\n"
    r"```",
    re.MULTILINE,
)
_GEMINI_SET_PROFILE_BLOCK = """```bash
gpd config ensure-section
INIT=$(gpd --raw init progress --include state,config)
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $INIT"
  # STOP — display the error to the user and do not proceed.
fi
```"""
_GEMINI_SET_PROFILE_REPLACEMENT = """Run these as separate shell calls in Gemini auto-edit mode. Do not combine them into one multi-line shell block.

```bash
gpd config ensure-section
```

Then run:

```bash
gpd --raw init progress --include state,config --no-project-reentry
```

If the init command fails, stop, surface the error, and do not proceed."""
_GEMINI_SET_PROFILE_BLOCK_RE = re.compile(
    r"```bash\n"
    r"gpd config ensure-section\n"
    r"(?:#.*\n)*"
    r"INIT=\$\((?:gpd --raw init progress --include state,config(?: --no-project-reentry)?)\)\n"
    r"if \[ \$\? -ne 0 \]; then\n"
    r"  echo \"ERROR: gpd initialization failed: \$INIT\"\n"
    r"  # STOP — display the error to the user and do not proceed\.\n"
    r"fi\n"
    r"```",
    re.MULTILINE,
)
_GEMINI_MINIMAL_COMMIT_BLOCK = """```bash
mkdir -p GPD

PRE_CHECK=$(gpd pre-commit-check --files GPD/PROJECT.md GPD/REQUIREMENTS.md GPD/ROADMAP.md GPD/STATE.md GPD/state.json GPD/config.json 2>&1) || true
echo "$PRE_CHECK"

gpd commit "docs: initialize research project (minimal)" --files GPD/PROJECT.md GPD/REQUIREMENTS.md GPD/ROADMAP.md GPD/STATE.md GPD/state.json GPD/config.json
```"""
_GEMINI_MINIMAL_COMMIT_REPLACEMENT = """Create the directory structure, run the pre-check, then commit everything. In Gemini auto-edit mode, execute each shell command separately rather than pasting the whole block as one command.

```bash
mkdir -p GPD
```

Then run:

```bash
gpd pre-commit-check --files GPD/PROJECT.md GPD/REQUIREMENTS.md GPD/ROADMAP.md GPD/STATE.md GPD/state.json GPD/config.json
```

If the pre-check reports issues or exits non-zero, surface the output and continue to the commit.

```bash
gpd commit "docs: initialize research project (minimal)" --files GPD/PROJECT.md GPD/REQUIREMENTS.md GPD/ROADMAP.md GPD/STATE.md GPD/state.json GPD/config.json
```"""
_GEMINI_CONTRACT_PERSIST_SENTENCE = (
    "Write the exact approved contract JSON to "
    f"`{_GEMINI_APPROVED_CONTRACT_PATH}` using file tools, then persist it into `GPD/state.json`:"
)
_GEMINI_CONTRACT_FILE_NOTE = (
    "Do not write `/tmp` intermediates for the approved contract. In Gemini headless auto-edit mode, keep the exact approved JSON in "
    f"`{_GEMINI_APPROVED_CONTRACT_PATH}`, then validate and persist from that file using direct `gpd` commands. "
    "Do not stash the approved contract in shell variables, command substitutions, or heredocs."
)


def _convert_gemini_tool_name(tool_name: str) -> str | None:
    """Convert a canonical GPD tool name or runtime alias to Gemini CLI format.

    Returns ``None`` if the tool should be excluded from the Gemini config
    (MCP tools are auto-discovered at runtime and ``task`` is auto-registered).
    """
    return translate_for_runtime(
        tool_name,
        _TOOL_NAME_MAP,
        auto_discovered_tools=_AUTO_DISCOVERED_TOOLS,
        drop_mcp_frontmatter_tools=_DROP_MCP_FRONTMATTER_TOOLS,
    )


def _gemini_settings_shape_is_valid(settings: dict[str, object]) -> bool:
    hooks = settings.get("hooks")
    if hooks is not None and not isinstance(hooks, dict):
        return False
    if isinstance(hooks, dict):
        session_start = hooks.get("SessionStart")
        if session_start is not None and not isinstance(session_start, list):
            return False

    experimental = settings.get("experimental")
    if experimental is not None and not isinstance(experimental, dict):
        return False

    policy_paths = settings.get("policyPaths")
    if policy_paths is not None and not isinstance(policy_paths, list):
        return False

    mcp_servers = settings.get("mcpServers")
    if mcp_servers is not None and not isinstance(mcp_servers, dict):
        return False
    if isinstance(mcp_servers, dict) and any(not isinstance(entry, dict) for entry in mcp_servers.values()):
        return False

    return True


def _read_gemini_settings_state(settings_path: Path) -> tuple[dict[str, object] | None, str | None]:
    """Return parsed Gemini settings and a malformed marker when parsing fails."""
    if not settings_path.exists():
        return None, None
    try:
        parsed = parse_jsonc(settings_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None, "malformed"
    if not isinstance(parsed, dict):
        return None, "malformed"
    if not _gemini_settings_shape_is_valid(parsed):
        return None, "malformed"
    return parsed, None


def _gemini_policy_command_prefixes(bridge_command: str) -> tuple[str, ...]:
    """Return the narrow shell prefixes GPD auto-approves for Gemini."""
    return (
        bridge_command,
        *_GEMINI_STATIC_POLICY_COMMAND_PREFIXES,
    )


def _render_gemini_shell_allowlist(bridge_command: str) -> str:
    """Render the enforced Gemini shell-prefix allowlist for model-facing content."""
    return "\n".join(
        f"  - `{prefix}`"
        for prefix in _gemini_policy_command_prefixes(bridge_command)
    )


def _project_managed_mcp_servers(
    env: Mapping[str, str] | None = None,
    *,
    cwd: Path | None = None,
) -> dict[str, dict[str, object]]:
    """Project shared optional integrations into Gemini's ``mcpServers`` shape."""
    return _managed_integrations.projected_managed_optional_mcp_servers(env, cwd=cwd)


def _managed_mcp_server_keys() -> frozenset[str]:
    """Return GPD-managed Gemini MCP server keys, including optional integrations."""
    from gpd.mcp.builtin_servers import GPD_MCP_SERVER_KEYS

    return frozenset(set(GPD_MCP_SERVER_KEYS) | set(_managed_integrations.managed_optional_mcp_server_keys()))


def _rewrite_gpd_cli_invocations(content: str, bridge_command: str) -> str:
    """Rewrite shell-command ``gpd`` calls to the shared runtime CLI bridge.

    Restrict rewrites to fenced shell code blocks and command positions only.
    This keeps prose and inline code spans canonical while still rewriting
    runnable shell steps.
    """
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
            rewritten.append(_rewrite_gemini_shell_line(line, bridge_command))
            continue

        rewritten.append(line)

    return "".join(rewritten)


def _rewrite_gemini_shell_line(line: str, bridge_command: str) -> str:
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


def _inject_gemini_command_runtime_note(content: str, bridge_command: str) -> str:
    """Prepend Gemini-specific shell guidance to installed top-level commands."""
    note = _GEMINI_COMMAND_RUNTIME_NOTE.format(
        launcher=bridge_command,
        allowlist=_render_gemini_shell_allowlist(bridge_command),
    )
    preamble, frontmatter, separator, body = split_markdown_frontmatter(content)
    if not frontmatter:
        return note + content
    return render_markdown_frontmatter(preamble, frontmatter, separator, note + body)


def _validate_existing_gemini_managed_state(target_dir: Path) -> None:
    """Fail closed when the prior Gemini manifest tracks managed config with the wrong shape."""
    manifest_path = target_dir / MANIFEST_NAME
    if not manifest_path.exists():
        return

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Gemini install manifest is malformed; refusing to overwrite managed config state.") from exc
    if not isinstance(manifest, dict):
        raise RuntimeError("Gemini install manifest is malformed; refusing to overwrite managed config state.")

    managed_config = manifest.get("managed_config")
    if managed_config is not None:
        if not isinstance(managed_config, dict):
            raise RuntimeError("Gemini managed_config is malformed; refusing to overwrite managed config state.")
        enable_agents = managed_config.get("experimental.enableAgents")
        if enable_agents is not None and not isinstance(enable_agents, bool):
            raise RuntimeError("Gemini managed_config.experimental.enableAgents is malformed.")
        policy_paths = managed_config.get("policyPaths")
        if policy_paths is not None and not (
            isinstance(policy_paths, list) and all(isinstance(path, str) and path for path in policy_paths)
        ):
            raise RuntimeError("Gemini managed_config.policyPaths is malformed.")

    managed_runtime_files = manifest.get("managed_runtime_files")
    if managed_runtime_files is not None and not (
        isinstance(managed_runtime_files, list)
        and all(isinstance(path, str) and path for path in managed_runtime_files)
    ):
        raise RuntimeError("Gemini managed_runtime_files is malformed.")


def _rewrite_gemini_shell_workflow_guidance(content: str) -> str:
    """Rewrite known shell-heavy workflow snippets into Gemini-safe forms.

    Gemini CLI's policy engine validates shell commands syntactically from the
    start of each command segment. GPD's canonical markdown includes some bash
    examples that rely on shell variables, command substitution, or combined
    blocks. Those examples work for humans and more permissive runtimes, but in
    Gemini headless auto-edit they lead the model to generate commands that are
    denied before GPD ever runs.
    """
    content = _GEMINI_NEW_PROJECT_INIT_BLOCK_RE.sub(_GEMINI_NEW_PROJECT_INIT_REPLACEMENT, content)
    content = _GEMINI_SET_PROFILE_BLOCK_RE.sub(_GEMINI_SET_PROFILE_REPLACEMENT, content)
    content = content.replace(_GEMINI_MINIMAL_COMMIT_BLOCK, _GEMINI_MINIMAL_COMMIT_REPLACEMENT)
    content = re.sub(
        r'(?m)^([ \t]*)PRE_CHECK=\$\((gpd pre-commit-check --files [^\n]+) 2>&1\) \|\| true\n\1echo "\$PRE_CHECK"$',
        (
            r"\1# Gemini auto-edit: run the pre-check as its own shell call.\n"
            r"\1\2\n"
            r"\1# If the pre-check exits non-zero, surface the output and continue."
        ),
        content,
    )
    content = content.replace(
        'printf \'%s\\n\' "$PROJECT_CONTRACT_JSON" | gpd --raw validate project-contract -',
        f"gpd --raw validate project-contract {_GEMINI_APPROVED_CONTRACT_PATH}",
    )
    content = content.replace(
        'printf \'%s\\n\' "$PROJECT_CONTRACT_JSON" | gpd state set-project-contract -',
        f"gpd state set-project-contract {_GEMINI_APPROVED_CONTRACT_PATH}",
    )
    content = content.replace(
        "Persist the approved contract into `GPD/state.json` from the same stdin payload:",
        _GEMINI_CONTRACT_PERSIST_SENTENCE,
    )
    content = content.replace(
        "After validation passes, persist the approved contract into `GPD/state.json` from the same stdin payload:",
        _GEMINI_CONTRACT_PERSIST_SENTENCE,
    )
    content = content.replace(
        "Do not write `/tmp` intermediates for the approved contract. Prefer piping the exact approved JSON directly to `gpd ... -`. Only write a file if the user explicitly wants a durable saved copy, and if so place it under the project, not an OS temp directory.",
        _GEMINI_CONTRACT_FILE_NOTE,
    )
    content = _rewrite_gemini_capture_and_check_blocks(content)
    return content


def _rewrite_gemini_capture_and_check_blocks(content: str) -> str:
    """Rewrite Gemini-hostile shell capture examples into direct command guidance."""
    content = content.replace(
        """```bash
CONV_CHECK=$(gpd --raw convention check 2>/dev/null)
if [ $? -ne 0 ]; then
  echo "WARNING: Convention verification failed — unit mismatches between theory and experiment are the #1 source of false discrepancies"
  echo "$CONV_CHECK"
fi
```""",
        """```bash
# Gemini auto-edit: run convention verification directly instead of capturing it in CONV_CHECK.
gpd --raw convention check 2>/dev/null
```""",
    )
    content = content.replace(
        """```bash
CONV_CHECK=$(gpd --raw convention check 2>/dev/null)
if [ $? -ne 0 ]; then
  echo "WARNING: Convention verification failed — unit mismatches between theory and experiment are the #1 source of false discrepancies"
  echo "$CONV_CHECK"
fi
```""",
        """```bash
# Gemini auto-edit: run convention verification directly instead of capturing it in CONV_CHECK.
gpd --raw convention check 2>/dev/null
```""",
    )
    content = content.replace(
        """```bash
CONV_CHECK=$(gpd --raw convention check 2>/dev/null)
if [ $? -ne 0 ]; then
  echo "WARNING: Convention verification failed — review before writing paper"
  echo "$CONV_CHECK"
fi
```""",
        """```bash
# Gemini auto-edit: run convention verification directly instead of capturing it in CONV_CHECK.
gpd --raw convention check 2>/dev/null
```""",
    )
    content = content.replace(
        """```bash
CONTEXT=$(gpd --raw validate command-context validate-conventions "$ARGUMENTS")
if [ $? -ne 0 ]; then
  echo "$CONTEXT"
  exit 1
fi
```""",
        """```bash
# Gemini auto-edit: run the command-context validation directly instead of capturing it in CONTEXT.
gpd --raw validate command-context validate-conventions "$ARGUMENTS"
```""",
    )
    content = content.replace(
        """```bash
CONTEXT=$(gpd --raw validate command-context write-paper "$ARGUMENTS")
if [ $? -ne 0 ]; then
  echo "$CONTEXT"
  exit 1
fi
```""",
        """```bash
# Gemini auto-edit: run the command-context validation directly instead of capturing it in CONTEXT.
gpd --raw validate command-context write-paper "$ARGUMENTS"
```""",
    )
    content = content.replace(
        """```bash
QUALITY=$(gpd --raw validate paper-quality --from-project . 2>/dev/null)
```""",
        """```bash
# Gemini auto-edit: run paper-quality validation directly instead of capturing it in QUALITY.
gpd --raw validate paper-quality --from-project . 2>/dev/null
```""",
    )
    content = content.replace(
        """```bash
PRE_CHECK=$(gpd pre-commit-check --files "${COMPARISON_OUTPUT_PATH}" 2>&1) || true
echo "$PRE_CHECK"

gpd commit \
  "docs: theory-experiment comparison for {slug}" \
  --files "${COMPARISON_OUTPUT_PATH}"
```""",
        """```bash
# Gemini auto-edit: run the pre-check directly; if it fails, inspect the output before committing.
gpd pre-commit-check --files "${COMPARISON_OUTPUT_PATH}" 2>&1 || true

gpd commit \
  "docs: theory-experiment comparison for {slug}" \
  --files "${COMPARISON_OUTPUT_PATH}"
```""",
    )
    content = content.replace(
        """```bash
PRE_CHECK=$(gpd pre-commit-check --files GPD/DEPENDENCY-GRAPH.md 2>&1) || true
echo "$PRE_CHECK"

gpd commit "docs: generate dependency graph" --files GPD/DEPENDENCY-GRAPH.md
```""",
        """```bash
# Gemini auto-edit: run the pre-check directly; if it fails, inspect the output before committing.
gpd pre-commit-check --files GPD/DEPENDENCY-GRAPH.md 2>&1 || true

gpd commit "docs: generate dependency graph" --files GPD/DEPENDENCY-GRAPH.md
```""",
    )
    content = content.replace(
        """```bash
INIT=$(gpd --raw init phase-op)
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $INIT"
  # STOP — display the error to the user and do not proceed.
fi
```""",
        """```bash
# Gemini auto-edit: run initialization directly instead of capturing it in INIT.
gpd --raw init phase-op
```""",
    )
    content = content.replace(
        """```bash
INIT=$(gpd --raw init progress --include state,roadmap,config)
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $INIT"
  # STOP — display the error to the user and do not proceed.
fi
```""",
        """```bash
# Gemini auto-edit: run initialization directly instead of capturing it in INIT.
gpd --raw init progress --include state,roadmap,config
```""",
    )
    content = content.replace(
        """```bash
INIT=$(gpd --raw init progress --include state)
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $INIT"
  # STOP — display the error to the user and do not proceed.
fi
```""",
        """```bash
# Gemini auto-edit: run initialization directly instead of capturing it in INIT.
gpd --raw init progress --include state
```""",
    )
    content = content.replace(
        """```bash
INIT=$(gpd --raw init phase-op --include state,config "${PHASE_ARG:-}")
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $INIT"
  # STOP — display the error to the user and do not proceed.
fi
```""",
        """```bash
# Gemini auto-edit: run initialization directly instead of capturing it in INIT.
gpd --raw init phase-op --include state,config "${PHASE_ARG:-}"
```""",
    )
    content = content.replace(
        """```bash
INIT=$(gpd --raw init progress --include state,config)
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $INIT"
  # STOP — display the error to the user and do not proceed.
fi
```""",
        """```bash
# Gemini auto-edit: run initialization directly instead of capturing it in INIT.
gpd --raw init progress --include state,config
```""",
    )
    return _rewrite_gemini_capture_assignments(content)


_GEMINI_CAPTURE_ASSIGNMENT_RE = re.compile(
    r"^(?P<indent>[ \t]*)(?P<var>[A-Z][A-Z0-9_]*)=\$\((?P<command>gpd[^\n]*)\)(?P<suffix>[ \t]*(?:\|\|\s*true)?)$",
    re.MULTILINE,
)


def _rewrite_gemini_capture_assignments(content: str) -> str:
    """Rewrite single-line Gemini shell capture examples into direct commands."""

    def _replace(match: re.Match[str]) -> str:
        indent = match.group("indent")
        var = match.group("var")
        command = match.group("command").strip()
        suffix = match.group("suffix") or ""
        suffix = suffix.strip()
        comment = f"{indent}# Gemini auto-edit: run the command directly instead of capturing it in {var}."
        rewritten = f"{indent}{command}"
        if suffix:
            rewritten = f"{rewritten} {suffix}"
        return f"{comment}\n{rewritten}"

    return _GEMINI_CAPTURE_ASSIGNMENT_RE.sub(_replace, content)


# ---------------------------------------------------------------------------
# Frontmatter conversion
# ---------------------------------------------------------------------------


def _convert_frontmatter_to_gemini(content: str) -> str:
    """Convert canonical GPD agent/file frontmatter to Gemini CLI format.

    - ``allowed-tools:`` → ``tools:`` as YAML array
    - Tool names converted to Gemini built-in names
    - Non-Gemini agent metadata removed (Gemini validates frontmatter strictly)
    - ``mcp__*`` tools excluded (auto-discovered at runtime)
    - ``<sub>`` tags in body stripped for terminal rendering
    """
    preamble, frontmatter, separator, body = split_markdown_frontmatter(content)
    if not frontmatter:
        return strip_sub_tags(content)

    lines = frontmatter.split("\n")
    new_lines: list[str] = []
    in_allowed_tools = False
    current_field_supported = True
    tools: list[str] = []

    for line in lines:
        trimmed = line.strip()
        top_level_field_match = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if top_level_field_match:
            current_field_supported = False
            field_name, field_value = top_level_field_match.groups()

            # Convert allowed-tools YAML array to tools list
            if field_name == "allowed-tools":
                in_allowed_tools = True
                continue

            # Handle inline tools: field (comma-separated string)
            if field_name == "tools":
                if field_value:
                    parsed = [t.strip() for t in field_value.split(",") if t.strip()]
                    for t in parsed:
                        mapped = _convert_gemini_tool_name(t)
                        if mapped:
                            tools.append(mapped)
                else:
                    # tools: with no value means YAML array follows
                    in_allowed_tools = True
                continue

            if field_name not in _GEMINI_AGENT_FRONTMATTER_FIELDS:
                continue

            current_field_supported = True
            in_allowed_tools = False
            new_lines.append(line)
            continue

        if line.startswith((" ", "\t")) and not in_allowed_tools:
            if current_field_supported:
                new_lines.append(line)
            continue

        if not trimmed:
            if current_field_supported:
                new_lines.append(line)
            continue

        # Collect allowed-tools/tools array items
        if in_allowed_tools:
            if trimmed.startswith("- "):
                mapped = _convert_gemini_tool_name(trimmed[2:].strip())
                if mapped:
                    tools.append(mapped)
                continue
            elif trimmed and not trimmed.startswith("-"):
                in_allowed_tools = False

        if not in_allowed_tools and current_field_supported:
            new_lines.append(line)

    # Deduplicate tools while preserving order
    seen: set[str] = set()
    unique_tools: list[str] = []
    for tool in tools:
        if tool not in seen:
            seen.add(tool)
            unique_tools.append(tool)

    # Add tools as YAML array (Gemini requires array format)
    if unique_tools:
        new_lines.append("tools:")
        for tool in unique_tools:
            new_lines.append(f"  - {tool}")

    new_frontmatter = "\n".join(new_lines).strip()
    return render_markdown_frontmatter(preamble, new_frontmatter, separator, strip_sub_tags(body))


def _normalize_string_list(value: object) -> list[str]:
    """Return a normalized list of strings from a settings value."""
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def _merge_unique_strings(existing: object, additions: list[str]) -> tuple[list[str], list[str]]:
    """Append new string values while preserving order and existing items."""
    merged = _normalize_string_list(existing)
    seen = set(merged)
    added: list[str] = []
    for item in additions:
        if item not in seen:
            merged.append(item)
            seen.add(item)
            added.append(item)
    return merged, added


def _managed_gemini_policy_path(target_dir: Path) -> Path:
    """Return the GPD-managed Gemini policy file path."""
    return target_dir / _GEMINI_POLICY_DIR_NAME / _GEMINI_POLICY_FILE_NAME


def _managed_gemini_yolo_wrapper_path(target_dir: Path) -> Path:
    """Return the GPD-managed Gemini launch wrapper for yolo sessions."""
    return target_dir / "get-physics-done" / _GEMINI_RUNTIME_BIN_DIR_NAME / _GEMINI_YOLO_WRAPPER_NAME


def _render_gemini_yolo_wrapper() -> str:
    """Render a small launcher that starts Gemini in yolo approval mode."""
    return "#!/bin/sh\nexec gemini --approval-mode=yolo \"$@\"\n"


def _render_gemini_policy_toml(bridge_command: str) -> str:
    """Render the Gemini policy file GPD installs for headless auto-edit flows."""
    rendered_prefixes: list[str] = []
    for prefix in _gemini_policy_command_prefixes(bridge_command):
        rendered_prefixes.append(json.dumps(prefix))
    prefixes = ",\n  ".join(rendered_prefixes)
    return (
        "# Managed by Get Physics Done (GPD).\n"
        "#\n"
        "# Policy Engine rules that auto-approve the narrow set of shell commands\n"
        "# GPD's bootstrap workflows rely on. The runtime CLI bridge validates the\n"
        "# install contract and pins the active runtime before dispatching to the\n"
        "# shared CLI implementation.\n"
        "\n"
        "[[rule]]\n"
        'toolName = "run_shell_command"\n'
        "commandPrefix = [\n"
        f"  {prefixes}\n"
        "]\n"
        'decision = "allow"\n'
        "priority = 350\n"
        'modes = ["autoEdit"]\n'
        "allow_redirection = true\n"
    )


# ---------------------------------------------------------------------------
# TOML conversion for commands
# ---------------------------------------------------------------------------


def _convert_to_gemini_toml(content: str) -> str:
    """Convert Claude Code markdown command to Gemini TOML format.

    Extracts selected frontmatter fields and puts body into ``prompt``.
    Preserves non-runtime command metadata as TOML comments so installed
    Gemini commands stay inspectable and closer to the canonical source.
    Uses TOML multi-line literal strings (``'''``) to avoid escape issues
    with backslashes in LaTeX/physics content.
    """
    _preamble, frontmatter, _separator, body = split_markdown_frontmatter(content)
    if not frontmatter:
        body = content.strip()
        if "'''" in body:
            return f"prompt = {json.dumps(body, ensure_ascii=False)}\n"
        return f"prompt = '''\n{body}\n'''\n"
    body = body.strip()

    # Extract selected frontmatter fields
    description = ""
    context_mode = ""
    for line in frontmatter.split("\n"):
        trimmed = line.strip()
        if trimmed.startswith("description:"):
            description = trimmed[12:].strip()
        elif trimmed.startswith("context_mode:"):
            context_mode = trimmed[13:].strip()

    toml = ""
    metadata_comments = _render_preserved_frontmatter_comments(frontmatter)
    if metadata_comments:
        toml += metadata_comments + "\n"
    if description:
        toml += f"description = {json.dumps(description)}\n"
    if context_mode:
        toml += f"context_mode = {json.dumps(context_mode)}\n"

    # Use TOML multi-line literal strings (''') to avoid escape issues.
    # Fall back to double-quoted string with JSON-style escaping if content contains '''.
    if "'''" in body:
        toml += f"prompt = {json.dumps(body, ensure_ascii=False)}\n"
    else:
        toml += f"prompt = '''\n{body}\n'''\n"

    return toml
def _render_preserved_frontmatter_comments(frontmatter: str) -> str:
    """Render non-runtime frontmatter metadata as TOML comments.

    Gemini commands only honor a narrow TOML surface, but the canonical GPD
    markdown commands carry other important metadata such as ``name``,
    ``argument-hint``, and ``requires``. Preserve those source fields as
    comments so the installed command remains auditable without inventing new
    runtime semantics.
    """
    excluded_keys = {"allowed-tools", "tools", "color", "description", "context_mode"}
    preserved: list[str] = []
    include_current = False

    for line in frontmatter.split("\n"):
        stripped = line.strip()
        if not stripped:
            if include_current and preserved and preserved[-1] != "":
                preserved.append("")
            continue

        if line == line.lstrip() and ":" in line:
            key = line.split(":", 1)[0].strip()
            include_current = key not in excluded_keys

        if include_current:
            preserved.append(line.rstrip())

    while preserved and preserved[0] == "":
        preserved.pop(0)
    while preserved and preserved[-1] == "":
        preserved.pop()

    if not preserved:
        return ""

    comment_lines = ["# Source frontmatter preserved for parity:"]
    for line in preserved:
        comment_lines.append("#" if not line else f"# {line}")
    return "\n".join(comment_lines)


def _policy_path_matches(value: str, candidates: set[str]) -> bool:
    """Return True when a settings policy path matches a managed candidate."""
    if value in candidates:
        return True
    try:
        return str(Path(value).expanduser().resolve()) in candidates
    except OSError:
        return False


# ---------------------------------------------------------------------------
# Agent installation
# ---------------------------------------------------------------------------


def _copy_agents_gemini(
    agents_src: Path,
    agents_dest: Path,
    path_prefix: str,
    gpd_src_root: Path | None = None,
    attribution: str | None = "",
    install_scope: str | None = None,
    *,
    bridge_command: str,
) -> None:
    """Install agent .md files with Gemini-specific conversions.

    - Replace path placeholders
    - Process attribution
    - Expand ``@`` includes (Gemini doesn't support native ``@`` includes)
    - Convert frontmatter (allowed-tools → tools array, strip color)
    - Convert tool name references in body text
    - Remove stale gpd-* agents not in the new set
    """
    if not agents_src.is_dir():
        return

    agents_dest.mkdir(parents=True, exist_ok=True)
    source_root = gpd_src_root or agents_src.parent / "specs"

    new_agent_names: set[str] = set()
    for agent_md in sorted(agents_src.glob("*.md")):
        content = compile_markdown_for_runtime(
            agent_md.read_text(encoding="utf-8"),
            runtime="gemini",
            path_prefix=path_prefix,
            install_scope=install_scope,
            src_root=source_root,
        )
        content = process_attribution(content, attribution)
        content = protect_runtime_agent_prompt(content, "gemini")
        content = _convert_frontmatter_to_gemini(content)
        content = convert_tool_references_in_body(content, _TOOL_REFERENCE_MAP)
        content = _rewrite_gpd_cli_invocations(content, bridge_command)

        (agents_dest / agent_md.name).write_text(content, encoding="utf-8")
        new_agent_names.add(agent_md.name)

    remove_stale_agents(agents_dest, new_agent_names)


# ---------------------------------------------------------------------------
# Command installation (nested structure, .toml format)
# ---------------------------------------------------------------------------


def _install_commands_as_toml(
    commands_src: Path,
    commands_dest: Path,
    path_prefix: str,
    workflow_target_dir: Path,
    gpd_src_root: Path,
    attribution: str | None = "",
    install_scope: str | None = None,
    *,
    bridge_command: str,
    explicit_target: bool = False,
) -> None:
    """Install commands as .toml files in nested ``commands/gpd/`` structure.

    Gemini commands are TOML files with ``description`` and ``prompt`` fields.
    """
    if not commands_src.is_dir():
        return

    # Clean destination before copy
    if commands_dest.exists():
        shutil.rmtree(commands_dest)
    commands_dest.mkdir(parents=True, exist_ok=True)

    _copy_commands_recursive(
        commands_src,
        commands_dest,
        path_prefix,
        workflow_target_dir,
        attribution,
        gpd_src_root,
        install_scope,
        bridge_command=bridge_command,
        explicit_target=explicit_target,
    )


def _copy_commands_recursive(
    src_dir: Path,
    dest_dir: Path,
    path_prefix: str,
    workflow_target_dir: Path,
    attribution: str | None,
    gpd_src_root: Path,
    install_scope: str | None = None,
    *,
    bridge_command: str,
    explicit_target: bool = False,
) -> None:
    """Recursively copy commands, converting .md to .toml for Gemini."""
    for entry in sorted(src_dir.iterdir()):
        if entry.is_dir():
            sub_dest = dest_dir / entry.name
            sub_dest.mkdir(parents=True, exist_ok=True)
            _copy_commands_recursive(
                entry,
                sub_dest,
                path_prefix,
                workflow_target_dir,
                attribution,
                gpd_src_root,
                install_scope,
                bridge_command=bridge_command,
                explicit_target=explicit_target,
            )
        elif entry.suffix == ".md":
            content = compile_markdown_for_runtime(
                entry.read_text(encoding="utf-8"),
                runtime="gemini",
                path_prefix=path_prefix,
                install_scope=install_scope,
                src_root=gpd_src_root,
                workflow_target_dir=workflow_target_dir,
                explicit_target=explicit_target,
            )
            content = process_attribution(content, attribution)
            content = strip_sub_tags(content)
            content = convert_tool_references_in_body(content, _TOOL_REFERENCE_MAP)
            content = _rewrite_gemini_shell_workflow_guidance(content)
            content = _rewrite_gpd_cli_invocations(content, bridge_command)
            content = _inject_gemini_command_runtime_note(content, bridge_command)
            toml_content = _convert_to_gemini_toml(content)
            toml_path = dest_dir / entry.with_suffix(".toml").name
            toml_path.write_text(toml_content, encoding="utf-8")
        else:
            shutil.copy2(entry, dest_dir / entry.name)


# ---------------------------------------------------------------------------
# Adapter class
# ---------------------------------------------------------------------------


class GeminiAdapter(RuntimeAdapter):
    """Adapter for Google Gemini CLI."""

    tool_name_map = _TOOL_NAME_MAP
    auto_discovered_tools = _AUTO_DISCOVERED_TOOLS
    drop_mcp_frontmatter_tools = _DROP_MCP_FRONTMATTER_TOOLS
    strip_sub_tags_in_shared_markdown = True

    @property
    def runtime_name(self) -> str:
        return "gemini"

    def project_markdown_surface(
        self,
        content: str,
        *,
        surface_kind: str,
        path_prefix: str,
        command_name: str | None = None,
    ) -> str:
        del path_prefix, command_name
        if surface_kind != "command":
            return super().project_markdown_surface(
                content,
                surface_kind=surface_kind,
                path_prefix="",
            )
        prompt = tomllib.loads(_convert_to_gemini_toml(content)).get("prompt")
        if not isinstance(prompt, str):
            raise ValueError("gemini projected command surface must expose a prompt string")
        return prompt

    def _runtime_bridge_only_relpaths(self) -> tuple[str, ...]:
        """Return Gemini artifacts that appear only after finalize_install()."""
        return ("settings.json",)

    def runtime_install_required_relpaths(self) -> tuple[str, ...]:
        """Return Gemini-owned files required for a complete install."""
        return (
            f"{_GEMINI_POLICY_DIR_NAME}/{_GEMINI_POLICY_FILE_NAME}",
            *self._runtime_bridge_only_relpaths(),
        )

    def install(
        self,
        gpd_root: Path,
        target_dir: Path,
        *,
        is_global: bool = False,
        explicit_target: bool = False,
    ) -> dict[str, object]:
        """Install Gemini surfaces and defer settings persistence to finalization.

        Unlike Claude Code, Gemini requires ``settings.json`` to enable
        ``experimental.enableAgents`` for the installed agents to function.
        ``install()`` prepares those settings in-memory; ``finalize_install()``
        writes them to disk once the caller is ready to complete the runtime
        configuration step.
        """
        previous_finalize_pending = getattr(self, "_gemini_finalize_pending", False)
        self._gemini_finalize_pending = True
        try:
            result = super().install(gpd_root, target_dir, is_global=is_global, explicit_target=explicit_target)
        finally:
            self._gemini_finalize_pending = previous_finalize_pending

        return result

    # --- Template method hooks ---

    def _install_commands(self, gpd_root: Path, target_dir: Path, path_prefix: str, failures: list[str]) -> int:
        commands_src = gpd_root / "commands"
        commands_dest = target_dir / "commands" / "gpd"
        (target_dir / "commands").mkdir(parents=True, exist_ok=True)
        bridge_command = self.runtime_cli_bridge_command(target_dir)
        _install_commands_as_toml(
            commands_src,
            commands_dest,
            path_prefix,
            target_dir,
            gpd_root / "specs",
            attribution=self.get_commit_attribution(),
            install_scope=self._current_install_scope_flag(),
            bridge_command=bridge_command,
            explicit_target=getattr(self, "_install_explicit_target", False),
        )
        if verify_installed(commands_dest):
            logger.info("Installed commands/gpd (TOML format)")
        else:
            failures.append("commands/gpd")
        return sum(1 for f in commands_dest.rglob("*.toml") if f.is_file()) if commands_dest.exists() else 0

    def _install_agents(self, gpd_root: Path, target_dir: Path, path_prefix: str, failures: list[str]) -> int:
        agents_src = gpd_root / "agents"
        agents_dest = target_dir / "agents"
        bridge_command = self.runtime_cli_bridge_command(target_dir)
        _copy_agents_gemini(
            agents_src,
            agents_dest,
            path_prefix,
            gpd_root / "specs",
            attribution=self.get_commit_attribution(),
            install_scope=self._current_install_scope_flag(),
            bridge_command=bridge_command,
        )
        if verify_installed(agents_dest):
            logger.info("Installed agents")
        else:
            failures.append("agents")
        return sum(1 for f in agents_dest.iterdir() if f.is_file() and f.suffix == ".md") if agents_dest.exists() else 0

    def _install_content(self, gpd_root: Path, target_dir: Path, path_prefix: str, failures: list[str]) -> None:
        """Install shared specs content with Gemini-specific bridge rewrites."""
        bridge_command = self.runtime_cli_bridge_command(target_dir)

        def _translate(content: str, prefix: str, install_scope: str | None = None) -> str:
            translated = super(GeminiAdapter, self).translate_shared_markdown(
                content,
                prefix,
                install_scope=install_scope,
            )
            translated = _rewrite_gemini_shell_workflow_guidance(translated)
            return _rewrite_gpd_cli_invocations(translated, bridge_command)

        from gpd.adapters.install_utils import install_gpd_content

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

    def _configure_runtime(self, target_dir: Path, is_global: bool) -> dict[str, object]:
        settings_path = target_dir / "settings.json"
        _validate_existing_gemini_managed_state(target_dir)
        settings_state, settings_parse_error = _read_gemini_settings_state(settings_path)
        if settings_parse_error is not None:
            raise RuntimeError("Gemini settings.json is malformed; refusing to overwrite it during install.")
        settings = settings_state or {}
        self._managed_policy_paths = []
        self._managed_runtime_files = []

        # Enable experimental agents (required for custom sub-agents in Gemini CLI)
        experimental = settings.get("experimental")
        enable_agents_was_present = isinstance(experimental, dict) and experimental.get("enableAgents") is True
        if not isinstance(experimental, dict):
            experimental = {}
            settings["experimental"] = experimental
        if not experimental.get("enableAgents"):
            experimental["enableAgents"] = True
            logger.info("Enabled experimental agents")
        self._managed_enable_agents = not enable_agents_was_present

        # Build hook commands (Python hooks, same as Claude Code)
        statusline_cmd = build_hook_command(
            target_dir,
            HOOK_SCRIPTS["statusline"],
            is_global=is_global,
            config_dir_name=self.config_dir_name,
            explicit_target=getattr(self, "_install_explicit_target", False),
        )
        update_check_cmd = build_hook_command(
            target_dir,
            HOOK_SCRIPTS["check_update"],
            is_global=is_global,
            config_dir_name=self.config_dir_name,
            explicit_target=getattr(self, "_install_explicit_target", False),
        )
        ensure_update_hook(
            settings,
            update_check_cmd,
            target_dir=target_dir,
            config_dir_name=self.config_dir_name,
        )

        bridge_command = self.runtime_cli_bridge_command(target_dir)

        # Install a runtime-owned policy file so Gemini loads the minimum
        # GPD shell allowlist even while workspace policies are disabled.
        policy_path = _managed_gemini_policy_path(target_dir)
        policy_path.parent.mkdir(parents=True, exist_ok=True)
        policy_path.write_text(_render_gemini_policy_toml(bridge_command), encoding="utf-8")
        self._managed_runtime_files = [
            policy_path.relative_to(target_dir).as_posix(),
        ]

        policy_dir_setting = str(policy_path.parent.resolve())
        merged_policy_paths, added_policy_paths = _merge_unique_strings(settings.get("policyPaths"), [policy_dir_setting])
        if merged_policy_paths:
            settings["policyPaths"] = merged_policy_paths
        self._managed_policy_paths = added_policy_paths

        # Wire MCP servers into settings so they start automatically.
        from gpd.mcp.builtin_servers import build_mcp_servers_dict, merge_managed_mcp_servers

        mcp_servers = build_mcp_servers_dict(python_path=hook_python_interpreter())
        project_cwd = None if is_global or getattr(self, "_install_explicit_target", False) else target_dir.parent
        managed_mcp_servers = _project_managed_mcp_servers(cwd=project_cwd)
        if managed_mcp_servers:
            mcp_servers.update(managed_mcp_servers)
        if mcp_servers:
            existing_mcp = settings.get("mcpServers", {})
            merged_mcp = merge_managed_mcp_servers(existing_mcp, mcp_servers)
            for server_name in mcp_servers:
                existing_entry = existing_mcp.get(server_name) if isinstance(existing_mcp, dict) else None
                if not isinstance(existing_entry, dict) or "trust" not in existing_entry:
                    merged_mcp.setdefault(server_name, {})["trust"] = True
            settings["mcpServers"] = merged_mcp

        return {
            "settingsPath": str(settings_path),
            "settings": settings,
            "statuslineCommand": statusline_cmd,
            "mcpServers": len(mcp_servers),
        }

    def runtime_permissions_status(self, target_dir: Path, *, autonomy: str) -> dict[str, object]:
        """Report whether a Gemini yolo launcher is ready for the next session."""
        wrapper_path = _managed_gemini_yolo_wrapper_path(target_dir)
        wrapper_exists = wrapper_path.is_file()
        desired_mode = "yolo" if autonomy == "yolo" else "default"
        next_step: str | None = None
        message = "Gemini is using its normal approval-mode defaults."
        if desired_mode == "yolo":
            if wrapper_exists:
                message = (
                    "Gemini only supports yolo at launch time. The GPD launcher is ready for the next session."
                )
                next_step = (
                    "Exit the current Gemini session and relaunch with "
                    f"{shlex.quote(str(wrapper_path))} so the runtime itself starts in yolo mode."
                )
            else:
                message = (
                    "Gemini only supports yolo at launch time. Generate and use the GPD launcher before "
                    "expecting uninterrupted yolo execution."
                )
        return {
            "runtime": self.runtime_name,
            "desired_mode": desired_mode,
            "configured_mode": "launch-wrapper" if wrapper_exists else "default",
            "config_aligned": wrapper_exists if desired_mode == "yolo" else True,
            "requires_relaunch": wrapper_exists if desired_mode == "yolo" else False,
            "managed_by_gpd": wrapper_exists,
            "launch_command": shlex.quote(str(wrapper_path)) if wrapper_exists else None,
            "message": message,
            "next_step": next_step,
        }

    def sync_runtime_permissions(self, target_dir: Path, *, autonomy: str) -> dict[str, object]:
        """Create or remove the Gemini yolo launcher for the requested autonomy."""
        wrapper_path = _managed_gemini_yolo_wrapper_path(target_dir)
        changed = False
        if autonomy == "yolo":
            wrapper_path.parent.mkdir(parents=True, exist_ok=True)
            content = _render_gemini_yolo_wrapper()
            current = wrapper_path.read_text(encoding="utf-8") if wrapper_path.exists() else None
            if current != content:
                wrapper_path.write_text(content, encoding="utf-8")
                wrapper_path.chmod(0o755)
                changed = True
        elif wrapper_path.exists():
            wrapper_path.unlink()
            changed = True

        status = self.runtime_permissions_status(target_dir, autonomy=autonomy)
        result = {
            **status,
            "changed": changed,
            "sync_applied": bool(status.get("config_aligned")),
            "requires_relaunch": autonomy == "yolo",
        }
        if autonomy == "yolo" and status.get("launch_command"):
            result["next_step"] = (
                "Exit the current Gemini session and relaunch with "
                f"{status['launch_command']} so the runtime itself starts in yolo mode."
            )
        elif changed:
            result["next_step"] = "Future Gemini sessions will use the normal approval mode unless you re-enable yolo."
        return result

    def _write_manifest(self, target_dir: Path, version: str) -> None:
        """Record manifest metadata for shared config keys GPD actually introduced."""
        managed_config: dict[str, object] = {}
        if getattr(self, "_managed_enable_agents", False):
            managed_config["experimental.enableAgents"] = True
        if getattr(self, "_managed_policy_paths", []):
            managed_config["policyPaths"] = list(self._managed_policy_paths)
        metadata: dict[str, object] = {}
        if managed_config:
            metadata["managed_config"] = managed_config
        if getattr(self, "_managed_runtime_files", []):
            metadata["managed_runtime_files"] = list(self._managed_runtime_files)
        write_manifest(
            target_dir,
            version,
            runtime=self.runtime_name,
            metadata=metadata or None,
            install_scope=self._current_install_scope_flag(),
            explicit_target=getattr(self, "_install_explicit_target", False),
        )

    def install_verification_relpaths(self) -> tuple[str, ...]:
        """Return Gemini artifacts that must exist before ``install()`` returns."""
        return (
            *self.install_detection_relpaths(),
            f"{_GEMINI_POLICY_DIR_NAME}/{_GEMINI_POLICY_FILE_NAME}",
        )

    def finish_install(
        self,
        settings_path: str | Path,
        settings: dict[str, object],
        statusline_command: str,
        should_install_statusline: bool,
        *,
        force_statusline: bool = False,
    ) -> None:
        """Apply statusline config and write settings atomically."""
        _finish_install(
            settings_path,
            settings,
            statusline_command,
            should_install_statusline,
            force_statusline=force_statusline,
        )

    def finalize_install(
        self,
        install_result: dict[str, object],
        *,
        force_statusline: bool = False,
    ) -> None:
        """Persist Gemini settings when install produced an in-memory config."""
        if install_result.get("settingsWritten"):
            return

        settings_path = install_result.get("settingsPath")
        settings = install_result.get("settings")
        statusline_command = install_result.get("statuslineCommand")
        if isinstance(settings_path, (str, Path)) and isinstance(settings, dict) and isinstance(statusline_command, str):
            target_dir = Path(settings_path).expanduser().resolve(strict=False).parent
            _validate_existing_gemini_managed_state(target_dir)
            _, settings_parse_error = _read_gemini_settings_state(Path(settings_path))
            if settings_parse_error is not None:
                raise RuntimeError("Gemini settings.json is malformed; refusing to overwrite it during finalize.")
            self.finish_install(
                settings_path,
                settings,
                statusline_command,
                True,
                force_statusline=force_statusline,
            )
            install_result["settingsWritten"] = True

    def uninstall(self, target_dir: Path) -> dict[str, object]:
        """Remove GPD from a Gemini CLI .gemini/ directory.

        Extends base uninstall with Gemini-specific settings.json cleanup.
        """
        manifest = read_settings(target_dir / MANIFEST_NAME)
        has_authoritative_manifest = self._has_authoritative_install_manifest(target_dir)
        managed_config = manifest.get("managed_config")
        managed_runtime_files = manifest.get("managed_runtime_files")
        remove_managed_enable_agents = (
            isinstance(managed_config, dict) and managed_config.get("experimental.enableAgents") is True
        )
        managed_policy_paths = []
        if isinstance(managed_config, dict):
            managed_policy_paths = _normalize_string_list(managed_config.get("policyPaths"))

        result = super().uninstall(target_dir)

        settings_path = target_dir / "settings.json"
        if settings_path.exists():
            settings = read_settings(settings_path)
            modified = False

            # Remove GPD statusline
            status_line = settings.get("statusLine")
            if isinstance(status_line, dict):
                cmd = status_line.get("command", "")
                if _is_hook_command_for_script(
                    cmd,
                    HOOK_SCRIPTS["statusline"],
                    target_dir=target_dir,
                    config_dir_name=self.config_dir_name,
                ):
                    del settings["statusLine"]
                    modified = True

            # Remove GPD hooks from SessionStart
            hooks = settings.get("hooks")
            if isinstance(hooks, dict):
                session_start = hooks.get("SessionStart")
                if isinstance(session_start, list):
                    before = len(session_start)
                    session_start[:] = [
                        entry
                        for entry in session_start
                        if not _entry_has_gpd_hook(entry, target_dir=target_dir, config_dir_name=self.config_dir_name)
                    ]
                    if len(session_start) < before:
                        modified = True
                    if not session_start:
                        del hooks["SessionStart"]
                    if not hooks:
                        del settings["hooks"]

            # Remove experimental.enableAgents only when GPD introduced it.
            experimental = settings.get("experimental")
            if (
                remove_managed_enable_agents
                and isinstance(experimental, dict)
                and experimental.get("enableAgents") is True
            ):
                del experimental["enableAgents"]
                if not experimental:
                    del settings["experimental"]
                modified = True

            policy_paths = _normalize_string_list(settings.get("policyPaths"))
            if policy_paths:
                candidate_policy_paths = set(managed_policy_paths)
                candidate_policy_paths.add(str((_managed_gemini_policy_path(target_dir).parent).resolve()))
                filtered_policy_paths = [
                    value for value in policy_paths if not _policy_path_matches(value, candidate_policy_paths)
                ]
                if filtered_policy_paths != policy_paths:
                    modified = True
                    if filtered_policy_paths:
                        settings["policyPaths"] = filtered_policy_paths
                    else:
                        settings.pop("policyPaths", None)

            # Remove GPD MCP servers
            mcp_servers = settings.get("mcpServers")
            if isinstance(mcp_servers, dict):
                removed_keys = [key for key in list(mcp_servers) if key in _managed_mcp_server_keys()]
                if removed_keys:
                    for key in removed_keys:
                        del mcp_servers[key]
                    if not mcp_servers:
                        del settings["mcpServers"]
                    modified = True

            if modified:
                write_settings(settings_path, settings)
                logger.info("Cleaned up Gemini settings.json (statusline, hooks, experimental, MCP)")
            if has_authoritative_manifest and remove_empty_json_object_file(settings_path):
                result.setdefault("removed", []).append(settings_path.name)

        policy_dir = _managed_gemini_policy_path(target_dir).parent
        if has_authoritative_manifest:
            policy_files = _normalize_string_list(managed_runtime_files)
            if not policy_files:
                policy_files = [_managed_gemini_policy_path(target_dir).relative_to(target_dir).as_posix()]
            for rel_path in policy_files:
                candidate = target_dir / rel_path
                if candidate.exists():
                    candidate.unlink()
                    result.setdefault("removed", []).append(rel_path)
            if policy_dir.is_dir() and not any(policy_dir.iterdir()):
                policy_dir.rmdir()

        for path in (
            target_dir / "commands",
            target_dir / "agents",
            target_dir / "hooks",
            target_dir / "cache",
            policy_dir,
            target_dir,
        ):
            prune_empty_ancestors(path, stop_at=target_dir.parent)

        return result

    def _verify(self, target_dir: Path) -> None:
        """Verify the Gemini install is usable, including persisted settings."""
        super()._verify(target_dir)

        if getattr(self, "_gemini_finalize_pending", False):
            return

        settings_path = target_dir / "settings.json"
        if not settings_path.exists():
            raise RuntimeError("Gemini install incomplete: settings.json was not written")

        settings = read_settings(settings_path)
        experimental = settings.get("experimental")
        if not isinstance(experimental, dict) or experimental.get("enableAgents") is not True:
            raise RuntimeError("Gemini install incomplete: experimental.enableAgents is not enabled")

        hooks = settings.get("hooks")
        session_start = hooks.get("SessionStart") if isinstance(hooks, dict) else None
        if not isinstance(session_start, list) or not any(
            _entry_has_gpd_hook(entry, target_dir=target_dir, config_dir_name=self.config_dir_name)
            for entry in session_start
        ):
            raise RuntimeError("Gemini install incomplete: update hook not configured")

        mcp_servers = settings.get("mcpServers")
        if not isinstance(mcp_servers, dict) or not mcp_servers:
            raise RuntimeError("Gemini install incomplete: MCP servers are not configured")


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _entry_has_gpd_hook(
    entry: object,
    *,
    target_dir: Path | None,
    config_dir_name: str | None,
) -> bool:
    """Check if a hook entry contains the GPD-managed Gemini update hook."""
    if not isinstance(entry, dict):
        return False
    entry_hooks = entry.get("hooks")
    if not isinstance(entry_hooks, list):
        return False
    return any(
        isinstance(h, dict)
        and isinstance(h.get("command"), str)
        and _is_hook_command_for_script(
            h["command"],
            HOOK_SCRIPTS["check_update"],
            target_dir=target_dir,
            config_dir_name=config_dir_name,
        )
        for h in entry_hooks
    )


__all__ = ["GeminiAdapter"]
