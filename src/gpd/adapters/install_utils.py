"""Shared install utilities for runtime installation and upgrades.

Every function here uses only the Python standard library (pathlib, json, hashlib,
tempfile, os, re).  No external deps allowed.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shlex
import sys
from collections.abc import Callable
from pathlib import Path, PurePosixPath

from gpd.adapters.runtime_catalog import get_runtime_descriptor, resolve_global_config_dir
from gpd.adapters.tool_names import CONTEXTUAL_TOOL_REFERENCE_NAMES
from gpd.core.constants import HOME_DATA_DIR_NAME
from gpd.core.review_contract_prompt import extract_frontmatter_block, prepend_review_contract_prompt

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PATCHES_DIR_NAME = "gpd-local-patches"
MANIFEST_NAME = "gpd-file-manifest.json"
MAX_INCLUDE_EXPANSION_DEPTH = 10
COMMANDS_DIR_NAME = "commands"
FLAT_COMMANDS_DIR_NAME = "command"
AGENTS_DIR_NAME = "agents"
HOOKS_DIR_NAME = "hooks"
GPD_INSTALL_DIR_NAME = "get-physics-done"
CACHE_DIR_NAME = "cache"
UPDATE_CACHE_FILENAME = "gpd-update-check.json"

# Subdirectories of specs/ that make up the installed get-physics-done/ content.
# Shared by all adapters.
GPD_CONTENT_DIRS = ("references", "templates", "workflows")

# Hook script filenames by purpose.
HOOK_SCRIPTS: dict[str, str] = {
    "statusline": "statusline.py",
    "check_update": "check_update.py",
    "notify": "notify.py",
    "runtime_detect": "runtime_detect.py",
}

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def expand_tilde(file_path: str | None) -> str | None:
    """Expand ``~`` to the user home directory.

    Shell does not expand ``~`` in env vars passed to Python, so this handles
    the three cases: ``None``/empty → passthrough, ``"~"`` → home,
    ``"~/..."`` → home + rest.
    """
    if not file_path:
        return file_path
    if file_path == "~":
        return str(Path.home())
    if file_path.startswith("~/"):
        return str(Path.home() / file_path[2:])
    return file_path


def _normalize_install_scope_flag(install_scope: str | None) -> str | None:
    """Normalize install scope values to bootstrap flags."""
    if install_scope in ("local", "--local"):
        return "--local"
    if install_scope in ("global", "--global"):
        return "--global"
    return install_scope


def _paths_equal(left: Path, right: Path) -> bool:
    """Return whether two paths refer to the same location when comparable."""
    try:
        return left.expanduser().resolve() == right.expanduser().resolve()
    except OSError:
        return left.expanduser() == right.expanduser()


def _default_install_target(config_dir: Path, runtime: str, scope_flag: str | None) -> Path | None:
    """Return the default install location for *runtime* and *scope_flag* when known."""
    descriptor = get_runtime_descriptor(runtime)
    if scope_flag == "--local":
        return Path.cwd() / descriptor.config_dir_name
    if scope_flag == "--global":
        return resolve_global_config_dir(descriptor)
    return None


def bundled_hooks_dir() -> Path:
    """Return the directory containing the bundled GPD hook scripts."""
    return Path(__file__).resolve().parents[1] / HOOKS_DIR_NAME


def bundled_hook_relpaths() -> tuple[str, ...]:
    """Return managed bundled hook file paths relative to a runtime config dir."""
    hooks_dir = bundled_hooks_dir()
    if not hooks_dir.is_dir():
        return ()

    relpaths: list[str] = []
    for hook_file in sorted(hooks_dir.iterdir()):
        if hook_file.is_file() and not hook_file.name.startswith("__"):
            relpaths.append(f"{HOOKS_DIR_NAME}/{hook_file.name}")
    return tuple(relpaths)


def prune_empty_ancestors(path: Path, *, stop_at: Path | None = None) -> None:
    """Remove *path* and empty ancestor directories until *stop_at* is reached."""
    current = path
    while True:
        if stop_at is not None and _paths_equal(current, stop_at):
            return
        if not current.exists() or not current.is_dir():
            return
        try:
            next(current.iterdir())
        except StopIteration:
            current.rmdir()
            current = current.parent
            continue
        return


def remove_empty_json_object_file(path: Path) -> bool:
    """Delete *path* when it contains only an empty JSON object."""
    if not path.is_file():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if payload != {}:
        return False
    path.unlink()
    return True


def remove_empty_text_file(path: Path) -> bool:
    """Delete *path* when its text content is empty after stripping whitespace."""
    if not path.is_file():
        return False
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return False
    if content.strip():
        return False
    path.unlink()
    return True


def config_dir_reference(
    target_dir: Path,
    config_dir_name: str,
    *,
    is_global: bool,
    explicit_target: bool = False,
) -> str:
    """Return the config-dir reference installed prompts should embed.

    Default local installs stay workspace-relative so installed prompt content
    remains portable across machines. Global installs and explicit targets use an
    absolute path because the config dir is not anchored to the current project.
    """
    if is_global or explicit_target:
        return str(target_dir).replace("\\", "/")
    return f"./{config_dir_name}"


def build_runtime_cli_bridge_command(
    runtime: str,
    *,
    target_dir: Path,
    config_dir_name: str,
    is_global: bool,
    explicit_target: bool = False,
) -> str:
    """Return the shell-safe runtime-agnostic GPD bridge command.

    Installed prompts author plain ``gpd`` in source form. During install, the
    adapter layer rewrites those shell invocations to this bridge command so one
    shared Python entrypoint can validate the install contract and run the CLI
    under the correct runtime pin without depending on runtime-private launcher
    files.
    """
    config_ref = config_dir_reference(
        target_dir,
        config_dir_name,
        is_global=is_global,
        explicit_target=explicit_target,
    )
    install_scope = "global" if is_global else "local"
    parts = [
        hook_python_interpreter(),
        "-m",
        "gpd.runtime_cli",
        "--runtime",
        runtime,
        "--config-dir",
        config_ref,
        "--install-scope",
        install_scope,
    ]
    if explicit_target:
        parts.append("--explicit-target")
    return " ".join(shlex.quote(part) for part in parts)


def build_runtime_install_repair_command(
    runtime: str,
    *,
    install_scope: str | None,
    target_dir: Path,
    explicit_target: bool = False,
) -> str:
    """Return the public reinstall/update command for one runtime install."""
    from gpd.adapters import get_adapter

    base = "npx -y get-physics-done"
    try:
        command = get_adapter(runtime).update_command
    except KeyError:
        command = base

    normalized_scope = _normalize_install_scope_flag(install_scope)
    if normalized_scope:
        command = f"{command} {normalized_scope}".strip()
    if explicit_target:
        command = f"{command} --target-dir {shlex.quote(str(target_dir))}"
    return command


def _replace_runtime_placeholders(
    content: str,
    path_prefix: str,
    runtime: str | None,
    install_scope: str | None = None,
) -> str:
    """Replace runtime-specific placeholders in installed prompt content."""
    scope_flag = _normalize_install_scope_flag(install_scope)
    if scope_flag:
        content = content.replace("{GPD_INSTALL_SCOPE_FLAG}", scope_flag)

    if not runtime:
        return content

    descriptor = get_runtime_descriptor(runtime)
    config_dir = path_prefix[:-1] if path_prefix.endswith("/") else path_prefix
    global_config_dir = str(Path(get_global_dir(runtime)).expanduser()).replace("\\", "/")
    install_flag = descriptor.install_flag

    content = content.replace("{GPD_CONFIG_DIR}", config_dir)
    content = content.replace("{GPD_GLOBAL_CONFIG_DIR}", global_config_dir)
    content = content.replace("{GPD_RUNTIME_FLAG}", install_flag)
    return content


def replace_placeholders(
    content: str,
    path_prefix: str,
    runtime: str | None = None,
    install_scope: str | None = None,
) -> str:
    """Replace GPD path placeholders in file content.

    Replaces ``{GPD_INSTALL_DIR}``, ``{GPD_AGENTS_DIR}``, and runtime
    placeholders with *path_prefix*.

    Source prompt/spec content should use canonical placeholders such as
    ``{GPD_CONFIG_DIR}`` so the adapter layer can rewrite them to the concrete
    runtime-specific path during installation without each prompt source
    carrying per-runtime copies.

    Used by all adapters during install to rewrite .md file references.
    """
    content = content.replace("{GPD_INSTALL_DIR}", path_prefix + "get-physics-done")
    content = content.replace("{GPD_AGENTS_DIR}", path_prefix + "agents")
    return _replace_runtime_placeholders(content, path_prefix, runtime, install_scope)


def _materialize_workflow_paths(
    content: str,
    *,
    target_dir: Path,
    runtime: str,
    install_scope: str | None,
) -> str:
    """Rewrite workflow bootstrap variables to authoritative absolute paths."""
    resolved_target = target_dir.expanduser().resolve(strict=False)
    config_dir = resolved_target.as_posix()
    install_dir = (resolved_target / GPD_INSTALL_DIR_NAME).as_posix()
    # Keep the canonical runtime-global directory distinct from an explicit
    # global install target so update/reapply workflows can still detect when
    # ``--target-dir`` is required.
    descriptor = get_runtime_descriptor(runtime)
    global_config_dir = resolve_global_config_dir(descriptor, home=Path.home()).as_posix()
    relative_config_prefix = f"./{descriptor.config_dir_name}/"

    replacements = {
        "GPD_INSTALL_DIR": install_dir,
        "GPD_CONFIG_DIR": config_dir,
        "GPD_GLOBAL_CONFIG_DIR": global_config_dir,
        "PATCHES_DIR": f"{config_dir}/gpd-local-patches",
        "GLOBAL_PATCHES_DIR": f"{global_config_dir}/gpd-local-patches",
    }
    for var, value in replacements.items():
        content = re.sub(
            rf"(?m)^(?P<indent>\s*){re.escape(var)}=\"[^\"]*\"$",
            lambda match, replacement=value, name=var: f'{match.group("indent")}{name}="{replacement}"',
            content,
            count=1,
        )
    content = content.replace(f"@{relative_config_prefix}get-physics-done/", f"@{config_dir}/get-physics-done/")
    content = content.replace(f"@{relative_config_prefix}agents/", f"@{config_dir}/agents/")
    return content


def materialize_first_round_review_schema_headings(content: str) -> str:
    """Render staged-review schema headings with first-round filenames.

    Source prompts stay round-aware via ``{round_suffix}``, but installed agent
    prompts should show the concrete first-round artifact names in the schema
    headings models read before producing those files.
    """
    replacements = {
        "Required schema for `CLAIMS{round_suffix}.json` (`ClaimIndex`):": (
            "Required schema for `CLAIMS.json` (`ClaimIndex`):"
        ),
        "Required schema for `STAGE-reader{round_suffix}.json` (`StageReviewReport`, mirroring the staged-review contract):": (
            "Required schema for `STAGE-reader.json` (`StageReviewReport`, mirroring the staged-review contract):"
        ),
        "Required schema for `STAGE-literature{round_suffix}.json` (`StageReviewReport`, mirroring the staged-review contract):": (
            "Required schema for `STAGE-literature.json` (`StageReviewReport`, mirroring the staged-review contract):"
        ),
        "Required schema for `STAGE-math{round_suffix}.json` (`StageReviewReport`, mirroring the staged-review contract):": (
            "Required schema for `STAGE-math.json` (`StageReviewReport`, mirroring the staged-review contract):"
        ),
        "Required schema for `STAGE-physics{round_suffix}.json` (`StageReviewReport`, mirroring the staged-review contract):": (
            "Required schema for `STAGE-physics.json` (`StageReviewReport`, mirroring the staged-review contract):"
        ),
        "Required schema for `STAGE-interestingness{round_suffix}.json` (`StageReviewReport`, mirroring the staged-review contract):": (
            "Required schema for `STAGE-interestingness.json` (`StageReviewReport`, mirroring the staged-review contract):"
        ),
    }
    for source, rendered in replacements.items():
        content = content.replace(source, rendered)
    return content


_BRACED_PROMPT_VAR_RE = re.compile(r"(?<!\\)\$\{([A-Za-z_][A-Za-z0-9_]*)(?:[^{}]*)\}")
_PLAIN_SHELL_VAR_RE = re.compile(r"(?<!\\)\$([A-Za-z_][A-Za-z0-9_]*)(?=[^A-Za-z0-9_-]|$)")
_INLINE_MATH_RE = re.compile(r"(?<!\\)\$(?=\S)([^$\n]*?\S)(?<!\\)\$(?![A-Za-z0-9_])")
_MARKDOWN_FRONTMATTER_RE = re.compile(
    r"^(?P<preamble>\ufeff?(?:[ \t]*\r?\n)*)---[ \t]*\r?\n(?P<frontmatter>[\s\S]*?)(?P<separator>\r?\n)---[ \t]*(?P<body_separator>\r?\n|$)"
)
_AT_INCLUDE_LINE_RE = re.compile(r"^(?:[-*+]\s+|\d+\.\s+)?`?(@[^\s`]+)`?(?:\s+.*)?$")
_COMMON_INLINE_MATH_NAMES = frozenset(
    {
        "sin",
        "cos",
        "tan",
        "cot",
        "sec",
        "csc",
        "sinh",
        "cosh",
        "tanh",
        "exp",
        "log",
        "ln",
        "det",
        "tr",
        "min",
        "max",
        "sup",
        "inf",
    }
)
_UNRESOLVED_INCLUDE_MARKERS = (
    "@ include not resolved:",
    "@ include cycle detected:",
    "@ include read error:",
    "@ include depth limit reached:",
)
_TEXT_INSTALL_ARTIFACT_SUFFIXES = frozenset({".md", ".toml"})


def protect_runtime_agent_prompt(content: str, runtime: str) -> str:
    """Rewrite agent body tokens that collide with runtime prompt templating.

    Some runtimes interpret ``$name``/``${NAME}`` inside agent bodies as prompt
    template inputs. GPD agent prompts use those forms as instructional shell
    examples, so convert them to neutral placeholders only for runtimes whose
    agent prompt engines reserve ``$``. Commands intentionally keep runtime
    placeholders such as ``$ARGUMENTS`` and should not call this helper.
    """
    if not get_runtime_descriptor(runtime).agent_prompt_uses_dollar_templates:
        return content

    frontmatter, body = _split_frontmatter(content)
    body = _BRACED_PROMPT_VAR_RE.sub(_shell_var_placeholder, body)
    body = "".join(_protect_shell_vars(line) for line in body.splitlines(keepends=True))
    return frontmatter + body


def _split_frontmatter(content: str) -> tuple[str, str]:
    """Return ``(frontmatter, body)`` while preserving the original delimiter."""
    match = _MARKDOWN_FRONTMATTER_RE.match(content)
    if match is None:
        return "", content
    return content[: match.end()], content[match.end() :]


def split_markdown_frontmatter(content: str) -> tuple[str, str, str, str]:
    """Split markdown into preamble, frontmatter, body separator, and body."""
    match = _MARKDOWN_FRONTMATTER_RE.match(content)
    if match is None:
        return "", "", "", content
    return (
        match.group("preamble"),
        match.group("frontmatter"),
        match.group("body_separator"),
        content[match.end() :],
    )


def render_markdown_frontmatter(preamble: str, frontmatter: str, separator: str, body: str) -> str:
    """Reassemble markdown content after frontmatter mutation."""
    rendered = f"{preamble}---\n{frontmatter}\n---"
    if separator:
        rendered += separator
    return rendered + body


def _inject_review_contract_prompt_from_frontmatter(content: str) -> str:
    """Front-load any review-contract block into the model-visible body once."""

    preamble, frontmatter, separator, body = split_markdown_frontmatter(content)
    if not frontmatter:
        return content
    if body.lstrip().startswith("## Review Contract"):
        return content
    return render_markdown_frontmatter(
        preamble,
        frontmatter,
        separator,
        prepend_review_contract_prompt(body, extract_frontmatter_block(frontmatter, "review-contract")),
    )


def _default_markdown_transform(runtime: str) -> Callable[[str, str, str | None], str]:
    """Resolve the adapter-owned shared-markdown transform for *runtime*."""
    from gpd.adapters import get_adapter

    try:
        adapter = get_adapter(runtime)
    except KeyError:
        return lambda content, path_prefix, install_scope: replace_placeholders(
            content,
            path_prefix,
            runtime,
            install_scope,
        )
    return adapter.translate_shared_markdown


def _shell_var_placeholder(match: re.Match[str]) -> str:
    return f"<{match.group(1)}>"


def _strip_wrapping_quotes(value: str) -> str:
    stripped = value.strip()
    if len(stripped) >= 2 and stripped[0] == stripped[-1] and stripped[0] in {'"', "'"}:
        return stripped[1:-1]
    return stripped


def _parse_frontmatter_tool_tokens(value: str) -> list[str]:
    stripped = value.strip()
    if not stripped:
        return []

    if stripped.startswith("[") and stripped.endswith("]"):
        stripped = stripped[1:-1]

    lexer = shlex.shlex(stripped, posix=True)
    lexer.whitespace = ","
    lexer.whitespace_split = True
    lexer.commenters = ""
    return [_strip_wrapping_quotes(token) for token in lexer if _strip_wrapping_quotes(token)]


def _protect_shell_vars(content: str) -> str:
    math_spans = [match.span() for match in _INLINE_MATH_RE.finditer(content)]

    def _replace(match: re.Match[str]) -> str:
        if any(start <= match.start() < end for start, end in math_spans):
            return match.group(0)

        name = match.group(1)
        if not _looks_like_shell_placeholder(name):
            return match.group(0)
        return _shell_var_placeholder(match)

    return _PLAIN_SHELL_VAR_RE.sub(_replace, content)


def _looks_like_shell_placeholder(name: str) -> bool:
    if name in _COMMON_INLINE_MATH_NAMES:
        return False

    if "_" in name:
        alpha_segments = [re.sub(r"\d", "", segment) for segment in name.split("_") if segment]
        if alpha_segments and all(len(segment) <= 1 for segment in alpha_segments):
            return False
        return True

    alpha_only = re.sub(r"\d", "", name)
    if name.isupper():
        return len(alpha_only) > 1
    if name.islower():
        return len(alpha_only) > 1
    return False


def get_global_dir(runtime: str, explicit_dir: str | None = None) -> str:
    """Resolve the global config directory for *runtime*.

    *explicit_dir* takes highest priority (from ``--config-dir`` flag).
    Then runtime-specific env vars, then defaults.
    """
    if explicit_dir:
        return expand_tilde(explicit_dir) or explicit_dir
    descriptor = get_runtime_descriptor(runtime)
    return str(resolve_global_config_dir(descriptor))


# ---------------------------------------------------------------------------
# Settings I/O  (JSON / JSONC)
# ---------------------------------------------------------------------------


def parse_jsonc(content: str) -> object:
    """Parse JSONC (JSON with Comments) by stripping comments and trailing commas.

    Handles single-line (``//``) and block (``/* */``) comments while
    preserving strings, strips BOM, and removes trailing commas before
    ``}`` or ``]``.

    Examples::

        >>> parse_jsonc('{"key": "value"}')
        {'key': 'value'}
        >>> parse_jsonc('{\\n  // comment\\n  "a": 1,\\n}')
        {'a': 1}

    Raises:
        json.JSONDecodeError: If content is not valid JSON after comment stripping.
    """
    # Strip BOM
    if content and ord(content[0]) == 0xFEFF:
        content = content[1:]

    result: list[str] = []
    in_string = False
    i = 0
    length = len(content)

    while i < length:
        char = content[i]

        if in_string:
            result.append(char)
            if char == "\\" and i + 1 < length:
                result.append(content[i + 1])
                i += 2
                continue
            if char == '"':
                in_string = False
            i += 1
        else:
            if char == '"':
                in_string = True
                result.append(char)
                i += 1
            elif char == "/" and i + 1 < length and content[i + 1] == "/":
                # Single-line comment — skip to end of line
                while i < length and content[i] != "\n":
                    i += 1
            elif char == "/" and i + 1 < length and content[i + 1] == "*":
                # Block comment — skip to closing */
                i += 2
                while i < length - 1 and not (content[i] == "*" and content[i + 1] == "/"):
                    i += 1
                i += 2  # skip closing */
            else:
                result.append(char)
                i += 1

    stripped = "".join(result)
    # Remove trailing commas before } or ]
    stripped = re.sub(r",(\s*[}\]])", r"\1", stripped)
    return json.loads(stripped)


def read_settings(settings_path: str | Path) -> dict[str, object]:
    """Read and parse a settings JSON/JSONC file.

    Returns ``{}`` if the file is missing, unreadable, malformed, or does not
    contain a top-level JSON object.
    """
    p = Path(settings_path)
    if not p.exists():
        return {}
    try:
        parsed = parse_jsonc(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def write_settings(settings_path: str | Path, settings: dict[str, object]) -> None:
    """Write *settings* as JSON atomically (write to temp, then rename).

    Raises:
        PermissionError: If the target directory or file is not writable.
    """
    p = Path(settings_path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
    except PermissionError as exc:
        raise PermissionError(f"Cannot create settings directory: {p.parent} — check permissions") from exc
    content = json.dumps(settings, indent=2) + "\n"
    tmp_path = p.with_suffix(".tmp")
    try:
        tmp_path.write_text(content, encoding="utf-8")
    except PermissionError as exc:
        raise PermissionError(f"Cannot write to settings directory {p.parent} — check permissions") from exc
    try:
        tmp_path.rename(p)
    except OSError:
        tmp_path.unlink(missing_ok=True)
        raise


# ---------------------------------------------------------------------------
# Attribution helpers
# ---------------------------------------------------------------------------


def process_settings_commit_attribution(settings_path: str | Path) -> str | None:
    """Read a settings.json-style commit attribution override."""
    settings = read_settings(settings_path)
    attribution = settings.get("attribution")
    if not isinstance(attribution, dict) or "commit" not in attribution:
        return ""
    commit_val = attribution["commit"]
    if commit_val == "":
        return None
    return str(commit_val) if commit_val else ""


def process_attribution(content: str, attribution: str | None) -> str:
    """Process Co-Authored-By lines in *content* based on *attribution*.

    *attribution* semantics:
        ``None`` → remove Co-Authored-By lines (and preceding blank line).
        ``""`` (empty string) → keep content unchanged.
        Any other string → replace the attribution name.
    """
    if attribution is None:
        # Remove Co-Authored-By lines and the preceding blank line
        return re.sub(r"(\r?\n){2}Co-Authored-By:.*$", "", content, flags=re.IGNORECASE | re.MULTILINE)

    if attribution == "":
        return content

    # Replace with custom attribution (escape backslash refs)
    safe = attribution.replace("\\", "\\\\")
    return re.sub(
        r"Co-Authored-By:.*$",
        f"Co-Authored-By: {safe}",
        content,
        flags=re.IGNORECASE | re.MULTILINE,
    )


# ---------------------------------------------------------------------------
# Content transformation helpers
# ---------------------------------------------------------------------------


def strip_sub_tags(content: str) -> str:
    """Strip HTML ``<sub>`` tags for terminal output.

    Converts ``<sub>text</sub>`` to italic ``*(text)*`` for readable output.
    """
    return re.sub(r"<sub>(.*?)</sub>", r"*(\1)*", content)


def translate_frontmatter_tool_names(
    content: str,
    translate_tool_name: Callable[[str], str | None],
) -> str:
    """Translate canonical tool names inside YAML frontmatter lists."""
    preamble, frontmatter, separator, body = split_markdown_frontmatter(content)
    if not frontmatter:
        return content

    translated_lines: list[str] = []
    in_tool_array = False

    for line in frontmatter.split("\n"):
        stripped = line.strip()
        field_match = re.match(r"^(\s*)(allowed-tools|tools):\s*(.*)$", line)
        if field_match:
            indent, key, value = field_match.groups()
            if not value:
                in_tool_array = True
                translated_lines.append(f"{indent}{key}:")
                continue

            in_tool_array = False
            parsed = _parse_frontmatter_tool_tokens(value)
            mapped = [translate_tool_name(part) for part in parsed]
            mapped = [part for part in mapped if part]
            translated_lines.append(f"{indent}{key}: {', '.join(mapped)}" if mapped else f"{indent}{key}:")
            continue

        if in_tool_array:
            item_match = re.match(r"^(\s*)-\s+(.*)$", line)
            if item_match:
                indent, tool_name = item_match.groups()
                mapped = translate_tool_name(_strip_wrapping_quotes(tool_name))
                if mapped:
                    translated_lines.append(f"{indent}- {mapped}")
                continue
            if stripped:
                in_tool_array = False

        translated_lines.append(line)

    translated_frontmatter = "\n".join(translated_lines)
    return render_markdown_frontmatter(preamble, translated_frontmatter, separator, body)


def convert_tool_references_in_body(content: str, tool_map: dict[str, str | None]) -> str:
    """Replace tool-name references in body text using *tool_map*.

    Targets contextual patterns: backtick-quoted names, "the X tool" phrases,
    "Use X to" / "using X" phrases.  Avoids replacing common English words
    (for example ``Read`` or ``shell``) when they are not clearly tool references.
    """
    for source_name, target in sorted(tool_map.items(), key=lambda item: len(item[0]), reverse=True):
        if not target or source_name == target:
            continue

        escaped = re.escape(source_name)
        if source_name not in CONTEXTUAL_TOOL_REFERENCE_NAMES:
            content = re.sub(r"\b" + escaped + r"\b", lambda m, replacement=target: replacement, content)
            continue

        # Backtick-quoted
        content = content.replace(f"`{source_name}`", f"`{target}`")
        # "the X tool"
        content = re.sub(
            r"\b(the\s+)" + escaped + r"(\s+tool)",
            lambda m, replacement=target: m.group(1) + replacement + m.group(2),
            content,
            flags=re.IGNORECASE,
        )
        # "X tool" after punctuation/start-of-line
        content = re.sub(
            r"(^|[.,:;!?\-\s])" + escaped + r"(\s+tool\b)",
            lambda m, replacement=target: m.group(1) + replacement + m.group(2),
            content,
            flags=re.MULTILINE,
        )
        # "Use X" / "using X" / "via X"
        content = re.sub(
            r"(\b(?:[Uu]se|[Uu]sing|[Vv]ia)\s+)" + escaped + r"\b",
            lambda m, replacement=target: m.group(1) + replacement,
            content,
        )
        # Function-style invocation, e.g. Task(...) or shell(...)
        content = re.sub(
            r"\b" + escaped + r"(?=\s*\()",
            lambda m, replacement=target: replacement,
            content,
        )

    return content


def compile_markdown_for_runtime(
    content: str,
    *,
    runtime: str,
    path_prefix: str,
    install_scope: str | None = None,
    src_root: str | Path | None = None,
    workflow_target_dir: Path | None = None,
    protect_agent_prompt_body: bool = False,
) -> str:
    """Compile canonical markdown into a runtime-specific installed form.

    This helper centralizes the shared install pipeline steps that were
    previously duplicated across adapters:

    - runtime/path placeholder replacement
    - capability-driven ``@`` include expansion
    - optional agent-prompt dollar-template protection

    Runtime-owned container conversions such as TOML command wrapping,
    SKILL frontmatter, or flat-command rendering stay in the adapter.
    """
    if src_root is not None and not get_runtime_descriptor(runtime).native_include_support:
        content = expand_at_includes(
            content,
            src_root,
            path_prefix,
            runtime=runtime,
            install_scope=install_scope,
        )

    content = replace_placeholders(content, path_prefix, runtime, install_scope)

    if protect_agent_prompt_body:
        content = protect_runtime_agent_prompt(content, runtime)

    if workflow_target_dir is not None:
        content = _materialize_workflow_paths(
            content,
            target_dir=workflow_target_dir,
            runtime=runtime,
            install_scope=install_scope,
        )

    return _inject_review_contract_prompt_from_frontmatter(content)


def expand_at_includes(
    content: str,
    src_root: str | Path,
    path_prefix: str,
    *,
    runtime: str | None = None,
    install_scope: str | None = None,
    depth: int = 0,
    include_stack: set[str] | None = None,
) -> str:
    """Expand ``@path/to/file`` include directives by inlining referenced file content.

    Some runtimes resolve these includes natively, while others require the
    adapter layer to inline them at install time.

    Args:
        content: File content potentially containing ``@`` include lines.
        src_root: Source root directory (repo's ``get-physics-done/`` dir).
        path_prefix: Runtime-specific config path prefix used for placeholder replacement.
        depth: Current recursion depth (for cycle protection).
        include_stack: Set of already-included absolute paths (cycle detection).

    Examples::

        >>> expand_at_includes("no includes here", "/src", "/runtime/")
        'no includes here'
        >>> expand_at_includes("@GPD/notes.md", "/src", "/runtime/")
        '@GPD/notes.md'
    """
    if depth > MAX_INCLUDE_EXPANSION_DEPTH:
        return content

    if include_stack is None:
        include_stack = set()

    src_root = Path(src_root)
    lines = content.split("\n")
    result: list[str] = []
    in_code_fence = False

    for line in lines:
        trimmed = line.strip()

        # Track code fences
        if trimmed.startswith("```"):
            in_code_fence = not in_code_fence
            result.append(line)
            continue
        if in_code_fence:
            result.append(line)
            continue

        include_match = _AT_INCLUDE_LINE_RE.match(trimmed)
        if not include_match:
            result.append(line)
            continue

        include_candidate = include_match.group(1)

        # Must start with @ followed by a path (not a BibTeX entry like @article{)
        if len(include_candidate) < 3 or include_candidate[1] == " " or re.match(r"^@\w+\{", include_candidate):
            result.append(line)
            continue

        # Extract the include path
        include_path = include_candidate[1:]
        include_path = include_path.split(" (see")[0]  # strip "(see ..." suffixes
        include_path = include_path.split(" -> ")[0]  # strip "-> Section Name" suffixes
        include_path = re.sub(r"\s+\([^)]*\)\s*$", "", include_path)  # strip trailing labels like "(main workflow)"
        include_path = include_path.strip()

        # Only treat paths that contain "/" (avoid false positives like decorators)
        if "/" not in include_path:
            result.append(line)
            continue

        # GPD/ relative paths — project-specific, skip
        if include_path.startswith("GPD/"):
            result.append(line)
            continue

        # Example paths — not real files
        if include_path.startswith("path/"):
            result.append(line)
            continue

        # Resolve against source directory
        src_path = _resolve_include_source_path(src_root, include_path)

        # Try to read and inline the file
        if src_path and src_path.exists():
            abs_key = str(src_path.resolve())
            if abs_key in include_stack:
                result.append(f"<!-- @ include cycle detected: {include_path} -->")
                continue
            if depth == MAX_INCLUDE_EXPANSION_DEPTH:
                result.append(f"<!-- @ include depth limit reached: {include_path} -->")
                continue

            include_stack.add(abs_key)
            try:
                included = src_path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError) as exc:
                result.append(f"<!-- @ include read error: {include_path} ({exc.__class__.__name__}) -->")
                include_stack.discard(abs_key)
                continue

            # Strip frontmatter from included file (only include the body)
            body = included
            _preamble, frontmatter, _separator, split_body = split_markdown_frontmatter(body)
            if frontmatter:
                body = split_body.strip()

            # Expand nested includes against canonical source paths before
            # translating placeholders into installed runtime paths.
            body = expand_at_includes(
                body,
                str(src_root),
                path_prefix,
                runtime=runtime,
                install_scope=install_scope,
                depth=depth + 1,
                include_stack=include_stack,
            )
            body = replace_placeholders(body, path_prefix, runtime, install_scope)

            result.append("")
            result.append(f"<!-- [included: {src_path.name}] -->")
            result.append(body)
            result.append("<!-- [end included] -->")
            result.append("")
            include_stack.discard(abs_key)
        else:
            result.append(f"<!-- @ include not resolved: {include_path} -->")

    return "\n".join(result)


def _resolve_include_source_path(src_root: Path, include_path: str) -> Path | None:
    """Map a canonical or installed include path back to its source file."""

    specs_root = _specs_source_root(src_root)
    agents_root = _agents_source_root(src_root)

    if include_path.startswith("{GPD_INSTALL_DIR}/"):
        relative_path = include_path[len("{GPD_INSTALL_DIR}/") :]
        return specs_root / relative_path
    if include_path.startswith("{GPD_AGENTS_DIR}/"):
        relative_path = include_path[len("{GPD_AGENTS_DIR}/") :]
        return agents_root / relative_path
    if "get-physics-done/" in include_path:
        relative_path = include_path.split("get-physics-done/", 1)[1]
        return specs_root / relative_path
    if "/agents/" in include_path:
        relative_path = include_path.split("/agents/", 1)[1]
        return agents_root / relative_path
    return None


def _specs_source_root(src_root: Path) -> Path:
    """Return the canonical source root for installed get-physics-done content."""

    specs_root = src_root / "specs"
    if specs_root.is_dir():
        return specs_root
    return src_root


def _agents_source_root(src_root: Path) -> Path:
    """Return the canonical source root for agent markdown files."""

    specs_root = _specs_source_root(src_root)
    sibling_agents = specs_root.parent / "agents"
    if sibling_agents.is_dir():
        return sibling_agents
    direct_agents = src_root / "agents"
    if direct_agents.is_dir():
        return direct_agents
    return sibling_agents


# ---------------------------------------------------------------------------
# Safe copy with path replacement
# ---------------------------------------------------------------------------


def copy_with_path_replacement(
    src_dir: str | Path,
    dest_dir: str | Path,
    path_prefix: str,
    runtime: str,
    install_scope: str | None = None,
    markdown_transform: Callable[[str, str, str | None], str] | None = None,
    *,
    workflow_paths: bool = False,
    workflow_target_dir: Path | None = None,
) -> None:
    """Safely copy *src_dir* to *dest_dir* with path replacement in ``.md`` files.

    Uses a copy-to-temp-then-swap strategy to prevent data loss if copy
    fails partway through. Symlinks in the source tree are skipped.

    Examples::

        >>> copy_with_path_replacement("src/", "dest/", "/custom/", "runtime-id")
        # Copies src/ → dest/ with placeholder replacement in .md files

    Raises:
        FileNotFoundError: If *src_dir* does not exist.
        OSError: If copying or swapping fails (original dest is preserved on error).
    """
    src_dir = Path(src_dir)
    if not src_dir.is_dir():
        raise FileNotFoundError(f"Source directory does not exist: {src_dir}")
    dest_dir = Path(dest_dir)
    pid = os.getpid()
    tmp_dir = dest_dir.with_name(f"{dest_dir.name}.tmp.{pid}")
    old_dir = dest_dir.with_name(f"{dest_dir.name}.old.{pid}")

    # Clean up leftovers from previous interrupted installs
    for d in (tmp_dir, old_dir):
        if d.exists():
            _rmtree(d)

    tmp_dir.mkdir(parents=True, exist_ok=True)

    try:
        _copy_dir_contents(
            src_dir,
            tmp_dir,
            path_prefix,
            runtime,
            install_scope,
            markdown_transform=markdown_transform,
            workflow_paths=workflow_paths,
            workflow_target_dir=workflow_target_dir,
        )

        # Swap into place
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
            _rmtree(old_dir)

    except Exception:
        # Copy or swap failed — clean up temp, leave existing install intact
        if tmp_dir.exists():
            _rmtree(tmp_dir)
        if dest_dir.exists() and old_dir.exists():
            _rmtree(old_dir)
        raise


def _copy_dir_contents(
    src_dir: Path,
    target_dir: Path,
    path_prefix: str,
    runtime: str,
    install_scope: str | None = None,
    markdown_transform: Callable[[str, str, str | None], str] | None = None,
    *,
    workflow_paths: bool = False,
    workflow_target_dir: Path | None = None,
) -> None:
    """Recursively copy directory contents with runtime translation in .md files.

    Symlinks are skipped to avoid cycles and broken links.
    """
    for entry in sorted(src_dir.iterdir()):
        if entry.is_symlink():
            continue

        dest = target_dir / entry.name

        if entry.is_dir():
            dest.mkdir(parents=True, exist_ok=True)
            _copy_dir_contents(
                entry,
                dest,
                path_prefix,
                runtime,
                install_scope,
                markdown_transform=markdown_transform,
                workflow_paths=workflow_paths,
                workflow_target_dir=workflow_target_dir,
            )
        elif entry.suffix == ".md":
            content = entry.read_text(encoding="utf-8")
            active_transform = markdown_transform or _default_markdown_transform(runtime)
            content = active_transform(content, path_prefix, install_scope=install_scope)
            if workflow_paths:
                content = _materialize_workflow_paths(
                    content,
                    target_dir=workflow_target_dir or target_dir,
                    runtime=runtime,
                    install_scope=install_scope,
                )
            content = _inject_review_contract_prompt_from_frontmatter(content)
            dest.write_text(content, encoding="utf-8")
        else:
            # Binary copy
            import shutil

            shutil.copy2(str(entry), str(dest))


# ---------------------------------------------------------------------------
# File hashing & manifest
# ---------------------------------------------------------------------------


def file_hash(file_path: str | Path) -> str:
    """Compute SHA-256 hex digest of a file's contents.

    Raises:
        FileNotFoundError: If *file_path* does not exist.
    """
    p = Path(file_path)
    if not p.exists():
        raise FileNotFoundError(f"Cannot hash non-existent file: {p}")
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def generate_manifest(directory: str | Path, base_dir: str | Path | None = None) -> dict[str, str]:
    """Recursively collect all files in *directory* with their SHA-256 hashes.

    Keys are POSIX-style relative paths from *base_dir*.
    """
    directory = Path(directory)
    if base_dir is None:
        base_dir = directory
    else:
        base_dir = Path(base_dir)

    manifest: dict[str, str] = {}
    if not directory.exists():
        return manifest

    for entry in sorted(directory.iterdir()):
        if entry.is_symlink():
            continue
        if entry.is_dir():
            manifest.update(generate_manifest(entry, base_dir))
        else:
            rel = entry.relative_to(base_dir).as_posix()
            manifest[rel] = file_hash(entry)

    return manifest


def write_manifest(
    config_dir: str | Path,
    version: str,
    *,
    runtime: str | None = None,
    skills_dir: str | Path | None = None,
    metadata: dict[str, object] | None = None,
    install_scope: str | None = None,
    explicit_target: bool | None = None,
) -> dict[str, object]:
    """Write a file manifest after installation for future modification detection.

    Returns the manifest dict.
    """
    config_dir = Path(config_dir)
    gpd_dir = config_dir / "get-physics-done"
    commands_dir = config_dir / "commands" / "gpd"
    agents_dir = config_dir / "agents"
    hooks_dir = config_dir / "hooks"

    manifest: dict[str, object] = {
        "version": version,
        "timestamp": _iso_now(),
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
        default_target = _default_install_target(config_dir, runtime.strip(), normalized_scope)
        if default_target is not None:
            manifest["explicit_target"] = not _paths_equal(config_dir, default_target)
    files: dict[str, str] = {}

    # get-physics-done/
    for rel, h in generate_manifest(gpd_dir).items():
        files["get-physics-done/" + rel] = h

    # commands/gpd/
    if commands_dir.exists():
        for rel, h in generate_manifest(commands_dir).items():
            files["commands/gpd/" + rel] = h

    # agents/gpd-*.(md|toml)
    if agents_dir.exists():
        for f in sorted(agents_dir.iterdir()):
            if f.name.startswith("gpd-") and f.suffix in {".md", ".toml"}:
                files["agents/" + f.name] = file_hash(f)

    # hooks/
    if hooks_dir.exists():
        for rel_path in bundled_hook_relpaths():
            hook_name = PurePosixPath(rel_path).name
            installed_hook = hooks_dir / hook_name
            bundled_hook = bundled_hooks_dir() / hook_name
            if not installed_hook.exists() or not bundled_hook.exists():
                continue
            if file_hash(installed_hook) == file_hash(bundled_hook):
                files[rel_path] = file_hash(installed_hook)

    # External/shared skills
    if skills_dir:
        skills = Path(skills_dir)
        if skills.exists():
            for entry in sorted(skills.iterdir()):
                if entry.is_dir() and entry.name.startswith("gpd-"):
                    skill_md = entry / "SKILL.md"
                    if skill_md.exists():
                        files[f"skills/{entry.name}/SKILL.md"] = file_hash(skill_md)

    manifest["files"] = files
    if metadata:
        manifest.update(metadata)
    manifest_path = config_dir / MANIFEST_NAME
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def _tracked_hook_paths_for_cleanup(
    config_dir: Path,
    *,
    skills_dir: str | Path | None = None,
) -> set[str]:
    """Return managed hook paths that pre-install cleanup may safely remove."""
    return managed_hook_paths(config_dir)


def tracked_hook_paths_from_manifest(config_dir: Path) -> set[str]:
    """Return hook paths explicitly tracked in the install manifest."""
    manifest_path = config_dir / MANIFEST_NAME
    if not manifest_path.exists():
        return set()

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return set()

    if not isinstance(manifest, dict):
        return set()

    raw_files = manifest.get("files")
    if not isinstance(raw_files, dict):
        return set()

    return {str(path) for path in raw_files if str(path).startswith("hooks/")}


def managed_hook_paths(config_dir: Path) -> set[str]:
    """Return bundled hook paths that are manifest-tracked or hash-matched."""
    tracked = tracked_hook_paths_from_manifest(config_dir)
    managed: set[str] = set()

    for rel_path in bundled_hook_relpaths():
        installed_hook = config_dir / rel_path
        if rel_path in tracked:
            managed.add(rel_path)
            continue
        if not installed_hook.is_file():
            continue
        bundled_hook = bundled_hooks_dir() / PurePosixPath(rel_path).name
        if not bundled_hook.is_file():
            continue
        try:
            if file_hash(installed_hook) == file_hash(bundled_hook):
                managed.add(rel_path)
        except (FileNotFoundError, OSError):
            continue

    return managed


def _managed_install_paths(
    config_dir: Path,
    *,
    skills_dir: str | Path | None = None,
) -> list[str]:
    """Return the current managed install paths when a manifest cannot be trusted."""
    managed_paths: list[str] = []

    gpd_dir = config_dir / "get-physics-done"
    for rel in generate_manifest(gpd_dir).keys():
        managed_paths.append(f"get-physics-done/{rel}")

    commands_dir = config_dir / "commands" / "gpd"
    for rel in generate_manifest(commands_dir).keys():
        managed_paths.append(f"commands/gpd/{rel}")

    command_dir = config_dir / "command"
    if command_dir.exists():
        for entry in sorted(command_dir.iterdir()):
            if entry.is_file() and entry.name.startswith("gpd-") and entry.suffix == ".md":
                managed_paths.append(f"command/{entry.name}")

    agents_dir = config_dir / "agents"
    if agents_dir.exists():
        for entry in sorted(agents_dir.iterdir()):
            if entry.is_file() and entry.name.startswith("gpd-") and entry.suffix in {".md", ".toml"}:
                managed_paths.append(f"agents/{entry.name}")

    hooks_dir = config_dir / "hooks"
    for rel in generate_manifest(hooks_dir).keys():
        managed_paths.append(f"hooks/{rel}")

    if skills_dir:
        skills = Path(skills_dir)
        if skills.exists():
            for entry in sorted(skills.iterdir()):
                if entry.is_dir() and entry.name.startswith("gpd-"):
                    skill_md = entry / "SKILL.md"
                    if skill_md.exists():
                        managed_paths.append(f"skills/{entry.name}/SKILL.md")

    return managed_paths


# ---------------------------------------------------------------------------
# Local patch persistence
# ---------------------------------------------------------------------------


def save_local_patches(
    config_dir: str | Path,
    *,
    skills_dir: str | Path | None = None,
) -> list[str]:
    """Detect user-modified GPD files and back them up before overwriting.

    Compares current files against the install manifest.  Modified files are
    copied to ``gpd-local-patches/`` with backup metadata.

    Returns a list of relative paths that were backed up.
    """
    config_dir = Path(config_dir)
    manifest_path = config_dir / MANIFEST_NAME
    if not manifest_path.exists():
        return []

    manifest_version = "unknown"
    tracked_files: dict[str, str] = {}
    fallback_snapshot = False
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        fallback_snapshot = True
    else:
        if isinstance(manifest, dict):
            manifest_version = str(manifest.get("version", "unknown"))
            raw_files = manifest.get("files") or {}
            if isinstance(raw_files, dict) and all(
                isinstance(rel_path, str) and isinstance(original_hash, str)
                for rel_path, original_hash in raw_files.items()
            ):
                tracked_files = raw_files
            else:
                fallback_snapshot = True
        else:
            fallback_snapshot = True

    if fallback_snapshot:
        tracked_files = dict.fromkeys(_managed_install_paths(config_dir, skills_dir=skills_dir), "")

    import shutil

    patches_dir = config_dir / PATCHES_DIR_NAME
    staging_dir = config_dir / f".{PATCHES_DIR_NAME}.tmp"
    previous_dir = config_dir / f".{PATCHES_DIR_NAME}.old"
    if staging_dir.exists():
        shutil.rmtree(staging_dir)
    if previous_dir.exists():
        shutil.rmtree(previous_dir)
    modified: list[str] = []

    for rel_path, original_hash in tracked_files.items():
        if rel_path.startswith("skills/"):
            if skills_dir is None:
                continue
            full_path = Path(skills_dir) / rel_path[len("skills/") :]
        else:
            full_path = config_dir / rel_path

        if not full_path.exists():
            continue

        current = file_hash(full_path)
        if fallback_snapshot or current != original_hash:
            backup_path = staging_dir / rel_path
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(full_path), str(backup_path))
            modified.append(rel_path)

    if not modified:
        if staging_dir.exists():
            shutil.rmtree(staging_dir)
        if patches_dir.exists():
            shutil.rmtree(patches_dir)
        return []

    meta = {
        "backed_up_at": _iso_now(),
        "from_version": manifest_version,
        "backup_mode": "fallback-snapshot" if fallback_snapshot else "manifest-diff",
        "files": modified,
    }
    meta_path = staging_dir / "backup-meta.json"
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    try:
        if patches_dir.exists():
            patches_dir.rename(previous_dir)
        staging_dir.rename(patches_dir)
    except Exception:
        if staging_dir.exists():
            shutil.rmtree(staging_dir)
        if previous_dir.exists() and not patches_dir.exists():
            previous_dir.rename(patches_dir)
        raise
    else:
        if previous_dir.exists():
            shutil.rmtree(previous_dir)

    return modified


# ---------------------------------------------------------------------------
# Verification helpers
# ---------------------------------------------------------------------------


def verify_installed(dir_path: str | Path, description: str) -> bool:
    """Verify a directory exists and is non-empty.

    Returns ``True`` if valid, ``False`` with a logged message otherwise.
    """
    p = Path(dir_path)
    if not p.exists():
        return False
    try:
        entries = list(p.iterdir())
        if not entries:
            return False
    except OSError:
        return False
    for artifact in p.rglob("*"):
        if not artifact.is_file() or artifact.suffix not in _TEXT_INSTALL_ARTIFACT_SUFFIXES:
            continue
        try:
            content = artifact.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        lowered = content.casefold()
        if any(marker in lowered for marker in _UNRESOLVED_INCLUDE_MARKERS):
            return False
    return True


def verify_file_installed(file_path: str | Path, description: str) -> bool:
    """Verify a file exists.  Returns ``True`` if it does."""
    return Path(file_path).exists()


# ---------------------------------------------------------------------------
# Shared install steps — used by multiple adapters
# ---------------------------------------------------------------------------

_install_logger = logging.getLogger(__name__)


def validate_package_integrity(gpd_root: Path) -> None:
    """Validate that the GPD package data directory contains required subdirs.

    Raises ``FileNotFoundError`` if commands/, agents/, hooks/, or specs/ are missing.
    """
    for required in ("commands", "agents", "hooks", "specs"):
        if not (gpd_root / required).is_dir():
            raise FileNotFoundError(
                f"Package integrity check failed: missing {required}/. Try reinstalling: npx -y get-physics-done"
            )


def compute_path_prefix(
    target_dir: Path, config_dir_name: str, *, is_global: bool, explicit_target: bool = False
) -> str:
    """Compute the path prefix for placeholder replacement.

    Global installs use absolute path; local installs use ``./.<config_dir>/``.
    """
    if is_global or explicit_target:
        return str(target_dir).replace("\\", "/") + "/"
    return f"./{config_dir_name}/"


def pre_install_cleanup(
    target_dir: Path,
    *,
    skills_dir: str | None = None,
) -> None:
    """Common pre-install cleanup: remove stale patches and current install files."""
    import shutil as _shutil

    save_local_patches(target_dir, skills_dir=skills_dir)

    gpd_dir = target_dir / "get-physics-done"
    if gpd_dir.exists():
        _shutil.rmtree(gpd_dir)

    for rel_path in sorted(_tracked_hook_paths_for_cleanup(target_dir, skills_dir=skills_dir)):
        hook_path = target_dir / rel_path
        if hook_path.exists():
            hook_path.unlink()


def install_gpd_content(
    specs_dir: Path,
    target_dir: Path,
    path_prefix: str,
    runtime: str,
    install_scope: str | None = None,
    markdown_transform: Callable[[str, str, str | None], str] | None = None,
) -> list[str]:
    """Install get-physics-done/ content from specs/ subdirectories.

    Copies references/, templates/, workflows/ with path replacement.
    Returns list of failure descriptions (empty on success).
    """
    gpd_dest = target_dir / "get-physics-done"
    gpd_dest.mkdir(parents=True, exist_ok=True)

    for subdir_name in GPD_CONTENT_DIRS:
        src_subdir = specs_dir / subdir_name
        if src_subdir.is_dir():
            copy_with_path_replacement(
                src_subdir,
                gpd_dest / subdir_name,
                path_prefix,
                runtime,
                install_scope,
                markdown_transform=markdown_transform,
                workflow_paths=subdir_name == "workflows",
                workflow_target_dir=target_dir,
            )

    if verify_installed(gpd_dest, "get-physics-done"):
        subdir_info = []
        for subdir in GPD_CONTENT_DIRS:
            subdir_path = gpd_dest / subdir
            if subdir_path.is_dir():
                count = sum(1 for f in subdir_path.rglob("*") if f.is_file())
                subdir_info.append(f"{subdir}: {count}")
        protocols_path = gpd_dest / "references" / "protocols"
        if protocols_path.is_dir():
            protocol_count = sum(1 for f in protocols_path.rglob("*") if f.is_file())
            if protocol_count:
                subdir_info.append(f"protocols: {protocol_count}")
        _install_logger.info("Installed get-physics-done (%s)", ", ".join(subdir_info))
        return []

    return ["get-physics-done"]


def write_version_file(gpd_dest: Path, version: str) -> list[str]:
    """Write VERSION file into get-physics-done/.

    Returns list of failure descriptions (empty on success).
    """
    version_dest = gpd_dest / "VERSION"
    version_dest.parent.mkdir(parents=True, exist_ok=True)
    version_dest.write_text(version, encoding="utf-8")

    if verify_file_installed(version_dest, "VERSION"):
        _install_logger.info("Wrote VERSION (%s)", version)
        return []

    return ["VERSION"]


def copy_hook_scripts(gpd_root: Path, target_dir: Path) -> list[str]:
    """Copy hook scripts from gpd_root/hooks/ to target_dir/hooks/.

    Returns list of failure descriptions (empty on success).
    """
    import shutil as _shutil

    hooks_src = gpd_root / "hooks"
    if not hooks_src.is_dir():
        return []

    manifest_path = target_dir / MANIFEST_NAME
    tracked_hook_paths: set[str] = set()
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        manifest = {}
    if isinstance(manifest, dict):
        raw_files = manifest.get("files")
        if isinstance(raw_files, dict):
            tracked_hook_paths = {str(path) for path in raw_files if str(path).startswith("hooks/")}

    hooks_dest = target_dir / "hooks"
    hooks_dest.mkdir(parents=True, exist_ok=True)
    for hook_file in hooks_src.iterdir():
        if hook_file.is_file() and not hook_file.name.startswith("__"):
            dest = hooks_dest / hook_file.name
            rel_path = f"hooks/{hook_file.name}"
            if dest.exists():
                managed_by_manifest = rel_path in tracked_hook_paths
                managed_by_hash = file_hash(dest) == file_hash(hook_file)
                if not (managed_by_manifest or managed_by_hash):
                    _install_logger.warning("Preserving unmanaged hook file during install: %s", dest)
                    continue
            _shutil.copy2(hook_file, dest)

    if verify_installed(hooks_dest, "hooks"):
        _install_logger.info("Installed hooks (bundled)")
        return []

    return ["hooks"]


def remove_stale_agents(agents_dest: Path, new_agent_names: set[str]) -> None:
    """Remove stale gpd-* agent files not in *new_agent_names*.

    Safe to call after writing new agents — removal happens after writes.
    """
    if not agents_dest.is_dir():
        return

    for existing in agents_dest.iterdir():
        if (
            existing.is_file()
            and existing.name.startswith("gpd-")
            and existing.name.endswith(".md")
            and existing.name not in new_agent_names
        ):
            existing.unlink()


def _is_hook_command_for_script(
    command: object,
    hook_filename: str,
    *,
    target_dir: Path | None = None,
    config_dir_name: str | None = None,
) -> bool:
    """Return True when *command* points at the managed hook script.

    When runtime context is available, match only the exact managed relative or
    absolute hook path. This prevents us from rewriting or uninstalling
    third-party hooks that happen to share the same filename.
    """
    if not isinstance(command, str):
        return False

    normalized_command = command.replace("\\", "/")
    managed_paths: list[str] = []

    if target_dir is not None:
        managed_paths.append(str(target_dir / "hooks" / hook_filename).replace("\\", "/"))
    if config_dir_name:
        managed_paths.append(f"{config_dir_name}/hooks/{hook_filename}")

    try:
        command_tokens = shlex.split(normalized_command)
    except ValueError:
        command_tokens = normalized_command.split()

    if managed_paths:
        managed_path_set = {path.replace("\\", "/") for path in managed_paths}
        if any(token.replace("\\", "/") in managed_path_set for token in command_tokens):
            return True

        return False

    for token in command_tokens:
        normalized_token = token.replace("\\", "/")
        if normalized_token == hook_filename:
            return True
        path = PurePosixPath(normalized_token)
        if path.name == hook_filename and path.parent.name == "hooks":
            return True

    return False


def _is_managed_statusline_command(command: object, *, target_dir: Path) -> bool:
    """Return True when *command* points at the GPD-managed statusline hook."""
    return _is_hook_command_for_script(
        command,
        HOOK_SCRIPTS["statusline"],
        target_dir=target_dir,
    )


def ensure_update_hook(
    settings: dict[str, object],
    update_check_command: str,
    *,
    target_dir: Path | None = None,
    config_dir_name: str | None = None,
) -> None:
    """Ensure SessionStart has one up-to-date GPD update-check hook.

    Rewrites stale managed commands in place so reinstalls repair interpreter
    or path drift instead of preserving broken entries forever. Also deduplicates
    multiple managed update hooks while preserving unrelated SessionStart hooks.
    """
    hooks = settings.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        hooks = {}
        settings["hooks"] = hooks

    session_start = hooks.setdefault("SessionStart", [])
    if not isinstance(session_start, list):
        session_start = []
        hooks["SessionStart"] = session_start

    normalized_session_start: list[object] = []
    managed_hook_found = False
    changed = False

    for entry in session_start:
        if not isinstance(entry, dict):
            normalized_session_start.append(entry)
            continue
        entry_hooks = entry.get("hooks")
        if not isinstance(entry_hooks, list):
            normalized_session_start.append(entry)
            continue

        normalized_hooks: list[object] = []
        for hook in entry_hooks:
            if not isinstance(hook, dict):
                normalized_hooks.append(hook)
                continue

            cmd = hook.get("command", "")
            if not _is_hook_command_for_script(
                cmd,
                HOOK_SCRIPTS["check_update"],
                target_dir=target_dir,
                config_dir_name=config_dir_name,
            ):
                normalized_hooks.append(hook)
                continue

            if managed_hook_found:
                changed = True
                continue

            managed_hook_found = True
            desired_hook = dict(hook)
            if desired_hook.get("type") != "command" or desired_hook.get("command") != update_check_command:
                desired_hook["type"] = "command"
                desired_hook["command"] = update_check_command
                changed = True
            normalized_hooks.append(desired_hook)

        if normalized_hooks != entry_hooks:
            changed = True
            if not normalized_hooks:
                continue
            normalized_entry = dict(entry)
            normalized_entry["hooks"] = normalized_hooks
            normalized_session_start.append(normalized_entry)
        else:
            normalized_session_start.append(entry)

    if not managed_hook_found:
        normalized_session_start.append({"hooks": [{"type": "command", "command": update_check_command}]})
        changed = True
        _install_logger.info("Configured update check hook")
    elif changed:
        _install_logger.info("Updated update check hook")

    if changed:
        hooks["SessionStart"] = normalized_session_start


def finish_install(
    settings_path: str | Path,
    settings: dict[str, object],
    statusline_command: str,
    should_install_statusline: bool,
    *,
    force_statusline: bool = False,
) -> None:
    """Apply statusline config and write settings atomically.

    Shared by settings-backed adapters that expose a status-line command hook.
    """
    if should_install_statusline:
        status_line = settings.get("statusLine")
        existing_cmd = status_line.get("command") if isinstance(status_line, dict) else None
        config_dir = Path(settings_path).expanduser().resolve(strict=False).parent

        if (
            isinstance(existing_cmd, str)
            and not _is_managed_statusline_command(existing_cmd, target_dir=config_dir)
            and not force_statusline
        ):
            _install_logger.warning("Skipping statusline (already configured by another tool)")
        else:
            settings["statusLine"] = {"type": "command", "command": statusline_command}
            _install_logger.info("Configured statusline")

    write_settings(Path(settings_path), settings)


def build_hook_command(
    target_dir: Path,
    hook_filename: str,
    *,
    is_global: bool,
    config_dir_name: str,
    interpreter: str | None = None,
    explicit_target: bool = False,
) -> str:
    """Build the shell command string for a hook script.

    Shared by adapters that launch Python hook scripts from a config directory.
    """
    command_interpreter = interpreter or hook_python_interpreter()
    if is_global or explicit_target:
        hooks_path = str(target_dir / "hooks" / hook_filename).replace("\\", "/")
        return f"{shlex.quote(command_interpreter)} {shlex.quote(hooks_path)}"
    return f"{shlex.quote(command_interpreter)} {shlex.quote(f'{config_dir_name}/hooks/{hook_filename}')}"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _rmtree(p: Path) -> None:
    """Recursively remove a directory tree (stdlib only)."""
    import shutil

    shutil.rmtree(str(p), ignore_errors=True)


def _gpd_home_dir() -> Path:
    """Return the managed GPD home directory."""
    raw_home = os.environ.get("GPD_HOME", "").strip()
    if raw_home:
        expanded = expand_tilde(raw_home)
        if expanded:
            return Path(expanded).expanduser()
    return Path.home() / HOME_DATA_DIR_NAME


def _managed_gpd_python() -> str | None:
    """Return the managed GPD virtualenv interpreter when it exists."""
    python_relpath = Path("Scripts/python.exe") if os.name == "nt" else Path("bin/python")
    candidate = _gpd_home_dir() / "venv" / python_relpath
    if candidate.is_file():
        return str(candidate)
    return None


def _running_from_checkout() -> bool:
    """Return whether the active install is executing from a source checkout."""
    try:
        from gpd.version import checkout_root

        return checkout_root() is not None
    except Exception:
        return False


def hook_python_interpreter() -> str:
    """Return the interpreter that should run installed GPD hook scripts.

    Hook scripts import ``gpd.*`` modules, so they need the same interpreter
    used for the active install process. Source checkouts keep using the active
    interpreter so local live-testing stays pinned to the worktree. Managed
    installs prefer the shared ``~/.gpd/venv`` interpreter when available so
    hooks and MCP servers do not inherit an unrelated ambient Python.
    """
    override = expand_tilde(os.environ.get("GPD_PYTHON", "").strip())
    if override:
        return override

    if _running_from_checkout():
        return sys.executable or "python3"

    managed_python = _managed_gpd_python()
    if managed_python:
        return managed_python

    return sys.executable or "python3"


def _iso_now() -> str:
    """Return the current UTC time in ISO 8601 format."""
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat()
